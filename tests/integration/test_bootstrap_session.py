"""Composition root end to end (propuesta HU-00-08 / T006 and T008): the real loop, tools and store.

``compose`` and ``run_session`` build the system exactly as the ``harness`` command does, with two
things injected: the provider (``FakeProvider``, scripted) and the streams (in memory). The real
``AgentLoop``, tools, ``WorkspaceArea``, ``DefaultPermissionPolicy``, event bus, SQLite store and
CLI take part. External network access is blocked for the whole module.
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import subprocess
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

import harness_agent
from harness_agent.adapters.storage import SqliteSessionStore
from harness_agent.bootstrap import NO_AREA_NOTICE, Composition, run_session
from harness_agent.core import (
    Event,
    EventType,
    Message,
    PermissionRules,
    Provider,
    ProviderError,
    ProviderResponse,
    QuotaExceeded,
    Role,
    ToolCall,
    ToolDefinition,
)
from tests.doubles import FakeProvider
from tests.integration.test_fake_provider_agent_loop import blocked_network  # noqa: F401
from tests.unit.bootstrap_support import FIXED_TIME, build, make_config

TIMEOUT = 5.0


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def call(call_id: str, name: str, **arguments: Any) -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=dict(arguments))


def write_note(call_id: str = "c1", path: str = "notas.txt", content: str = "hola") -> ToolCall:
    return call(call_id, "escribir_archivo", path=path, content=content)


class Run:
    """One composition, a recorder of everything the bus emitted, and the terminal streams."""

    def __init__(
        self,
        opened: list[Composition],
        tmp_path: Path,
        script: Sequence[ProviderResponse | ProviderError],
        *,
        workspace: Path | None,
        permissions: PermissionRules = PermissionRules(),  # noqa: B008 (immutable)
    ) -> None:
        self.provider = FakeProvider(script)
        config = make_config(tmp_path, workspace=workspace, permissions=permissions)
        self.composition = build(
            opened,
            config,
            self.provider,
            clock=lambda: FIXED_TIME,
            id_factory=lambda: "sesion-fija",
        )
        self.emitted: list[Event] = []
        for event_type in EventType:
            self.composition.bus.subscribe(event_type, self.emitted.append)
        self.output = io.StringIO()

    async def go(self, text: str) -> int:
        async with asyncio.timeout(TIMEOUT):
            return await run_session(
                self.composition, input_stream=io.StringIO(text), output=self.output
            )

    def saved(self) -> list[Event]:
        return self.composition.store.load_session(self.composition.session_id)

    def tool_answers(self) -> list[str]:
        """What the model received as tool results, over every call to the provider."""
        return [
            message.content
            for messages in self.provider.received
            for message in messages
            if message.role is Role.TOOL
        ]


@pytest.fixture
def area(tmp_path: Path) -> Path:
    folder = tmp_path / "area"
    folder.mkdir()
    return folder


class TestATaskFromStartToFinish:
    async def test_a_task_writes_a_file_inside_the_area_and_the_terminal_shows_the_steps(
        self,
        tmp_path: Path,
        area: Path,
        opened: list[Composition],
        blocked_network: None,  # noqa: F811
    ) -> None:
        run = Run(
            opened,
            tmp_path,
            [ProviderResponse(tool_calls=[write_note()]), ProviderResponse(content="listo")],
            workspace=area,
        )

        code = await run.go("crea notas.txt con un saludo\n/salir\n")

        assert code == 0
        assert (area / "notas.txt").read_text(encoding="utf-8") == "hola"
        shown = run.output.getvalue()
        assert "escribir_archivo" in shown
        assert "Sesión terminada." in shown

    async def test_every_emitted_event_is_saved_in_order_under_one_session(
        self,
        tmp_path: Path,
        area: Path,
        opened: list[Composition],
        blocked_network: None,  # noqa: F811
    ) -> None:
        run = Run(
            opened,
            tmp_path,
            [ProviderResponse(tool_calls=[write_note()]), ProviderResponse(content="listo")],
            workspace=area,
        )

        await run.go("crea notas.txt\n/salir\n")

        saved = run.saved()
        assert len(saved) == len(run.emitted) > 3
        assert [(e.id, e.type, e.payload) for e in saved] == [
            (e.id, e.type, e.payload) for e in run.emitted
        ]
        assert {e.session_id for e in saved} == {"sesion-fija"}

    async def test_the_second_task_sees_what_the_first_one_did(
        self,
        tmp_path: Path,
        area: Path,
        opened: list[Composition],
        blocked_network: None,  # noqa: F811
    ) -> None:
        run = Run(
            opened,
            tmp_path,
            [
                ProviderResponse(tool_calls=[write_note()]),
                ProviderResponse(content="escrito"),
                ProviderResponse(tool_calls=[call("c2", "leer_archivo", path="notas.txt")]),
                ProviderResponse(content="leído"),
            ],
            workspace=area,
        )

        await run.go("escribe notas.txt\nlee notas.txt\n/salir\n")

        assert "hola" in run.tool_answers()
        fourth_call = [m.content for m in run.provider.received[3]]
        # The history opens with the environment notice (HU-01-04); the first task follows it.
        assert fourth_call[0].startswith("Entorno de ejecución")
        assert fourth_call[2] == "escribe notas.txt"
        assert "lee notas.txt" in fourth_call


class TestNothingHappensOutsideTheArea:
    async def test_a_write_outside_the_area_is_denied_and_creates_nothing(
        self,
        tmp_path: Path,
        area: Path,
        opened: list[Composition],
        blocked_network: None,  # noqa: F811
    ) -> None:
        run = Run(
            opened,
            tmp_path,
            [
                ProviderResponse(tool_calls=[write_note(path="../fuera.txt")]),
                ProviderResponse(content="no pude"),
            ],
            workspace=area,
        )

        code = await run.go("escribe fuera del área\n/salir\n")

        assert code == 0
        assert not (tmp_path / "fuera.txt").exists()
        assert run.tool_answers()[0].startswith("[")
        assert not run.tool_answers()[0].lower().startswith("archivo")

    async def test_without_an_area_there_is_a_notice_and_the_write_is_denied(
        self,
        tmp_path: Path,
        opened: list[Composition],
        blocked_network: None,  # noqa: F811
    ) -> None:
        run = Run(
            opened,
            tmp_path,
            [ProviderResponse(tool_calls=[write_note()]), ProviderResponse(content="no pude")],
            workspace=None,
        )

        code = await run.go("escribe notas.txt\n/salir\n")

        assert code == 0
        assert run.output.getvalue().startswith(NO_AREA_NOTICE + "\n")
        assert run.tool_answers()[0].startswith("[approval_required_unavailable]")
        assert not any(path.name == "notas.txt" for path in tmp_path.rglob("*"))

    async def test_an_action_that_asks_for_approval_is_denied_with_a_reason(
        self,
        tmp_path: Path,
        area: Path,
        opened: list[Composition],
        blocked_network: None,  # noqa: F811
    ) -> None:
        (area / "notas.txt").write_text("contenido", encoding="utf-8", newline="")
        run = Run(
            opened,
            tmp_path,
            [
                ProviderResponse(tool_calls=[call("c1", "leer_archivo", path="notas.txt")]),
                ProviderResponse(content="no pude"),
            ],
            workspace=area,
            permissions=PermissionRules(ask=("leer_archivo",)),
        )

        await run.go("lee notas.txt\n/salir\n")

        assert run.tool_answers()[0].startswith("[approval_required_unavailable]")
        assert "contenido" not in run.tool_answers()[0]


class TestFailuresDuringTheSession:
    async def test_a_provider_error_is_saved_and_the_session_goes_on(
        self,
        tmp_path: Path,
        area: Path,
        opened: list[Composition],
        blocked_network: None,  # noqa: F811
    ) -> None:
        run = Run(
            opened,
            tmp_path,
            [
                ProviderResponse(tool_calls=[write_note()]),
                QuotaExceeded("cuota agotada"),
                ProviderResponse(content="seguimos"),
            ],
            workspace=area,
        )

        code = await run.go("primera\nsegunda\n/salir\n")

        assert code == 0
        errors = [e for e in run.saved() if e.type is EventType.PROVIDER_ERROR]
        assert [e.payload["error_type"] for e in errors] == ["QuotaExceeded"]
        assert run.provider.call_count == 3

    async def test_an_interruption_in_the_middle_of_a_turn_saves_the_interrupted_event(
        self,
        tmp_path: Path,
        area: Path,
        opened: list[Composition],
        blocked_network: None,  # noqa: F811
    ) -> None:
        waiting = asyncio.Event()

        class NeverAnswers(Provider):
            async def complete(
                self, messages: list[Message], tools: list[ToolDefinition] | None = None
            ) -> ProviderResponse:
                waiting.set()
                await asyncio.Event().wait()
                raise AssertionError("unreachable")

        composition = build(opened, make_config(tmp_path, workspace=area), NeverAnswers())
        task = asyncio.create_task(
            run_session(composition, input_stream=io.StringIO("una tarea\n"), output=io.StringIO())
        )
        async with asyncio.timeout(TIMEOUT):
            await waiting.wait()

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            async with asyncio.timeout(TIMEOUT):
                await task

        types = [e.type for e in composition.store.load_session(composition.session_id)]
        assert EventType.INTERRUPTED in types
        composition.close()


RUNS = 20


class TestTheSameSessionTwentyTimes:
    async def test_the_output_the_events_and_the_file_are_identical_in_every_run(
        self,
        tmp_path: Path,
        opened: list[Composition],
        blocked_network: None,  # noqa: F811
    ) -> None:
        signatures: list[tuple[Any, ...]] = []
        for index in range(RUNS):
            folder = tmp_path / f"ejecucion-{index}"
            folder.mkdir()
            run = Run(
                opened,
                folder,
                [
                    ProviderResponse(tool_calls=[write_note()]),
                    ProviderResponse(content="listo"),
                    ProviderResponse(tool_calls=[call("c2", "leer_archivo", path="notas.txt")]),
                    ProviderResponse(content="leído"),
                ],
                workspace=folder,
            )

            code = await run.go("escribe notas.txt\nlee notas.txt\n/salir\n")

            signatures.append(
                (
                    code,
                    re.sub(r" \(\d+ ms\)", "", run.output.getvalue()),
                    [(e.type, e.payload) for e in run.saved()],
                    run.provider.received,
                    (folder / "notas.txt").read_text(encoding="utf-8"),
                )
            )

        assert len(signatures) == RUNS
        assert all(signature == signatures[0] for signature in signatures[1:])
        assert signatures[0][0] == 0


class TestSprintOneDemoOutsideTheArea:
    """Demo criterion 4: «..», an absolute path or a symbolic link are rejected before writing."""

    async def test_an_absolute_path_outside_is_denied_before_writing_and_the_decision_is_saved(
        self,
        tmp_path: Path,
        area: Path,
        opened: list[Composition],
        blocked_network: None,  # noqa: F811
    ) -> None:
        outside = tmp_path / "fuera-absoluta.txt"
        run = Run(
            opened,
            tmp_path,
            [
                ProviderResponse(tool_calls=[write_note(path=str(outside))]),
                ProviderResponse(content="no pude"),
            ],
            workspace=area,
        )

        await run.go("escribe fuera del área\n/salir\n")

        assert not outside.exists()
        assert run.tool_answers()[0].startswith("[")
        decisions = [e for e in run.saved() if e.type is EventType.PERMISSION_DECIDED]
        assert [d.payload["name"] for d in decisions] == ["escribir_archivo"]
        assert decisions[0].payload["decision"] != "allow"

    async def test_a_dot_dot_path_is_denied_and_the_decision_is_saved(
        self,
        tmp_path: Path,
        area: Path,
        opened: list[Composition],
        blocked_network: None,  # noqa: F811
    ) -> None:
        run = Run(
            opened,
            tmp_path,
            [
                ProviderResponse(tool_calls=[write_note(path="../fuera-relativa.txt")]),
                ProviderResponse(content="no pude"),
            ],
            workspace=area,
        )

        await run.go("escribe fuera del área\n/salir\n")

        assert not (tmp_path / "fuera-relativa.txt").exists()
        decisions = [e for e in run.saved() if e.type is EventType.PERMISSION_DECIDED]
        assert [d.payload["decision"] != "allow" for d in decisions] == [True]

    async def test_a_symbolic_link_that_leaves_the_area_is_denied_before_writing(
        self,
        tmp_path: Path,
        area: Path,
        opened: list[Composition],
        blocked_network: None,  # noqa: F811
    ) -> None:
        elsewhere = tmp_path / "otra-carpeta"
        elsewhere.mkdir()
        try:
            (area / "enlace").symlink_to(elsewhere, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("El sistema no permite crear enlaces simbólicos.")
        run = Run(
            opened,
            tmp_path,
            [
                ProviderResponse(tool_calls=[write_note(path="enlace/escapado.txt")]),
                ProviderResponse(content="no pude"),
            ],
            workspace=area,
        )

        await run.go("escribe a través del enlace\n/salir\n")

        assert not (elsewhere / "escapado.txt").exists()
        decisions = [e for e in run.saved() if e.type is EventType.PERMISSION_DECIDED]
        assert [d.payload["decision"] != "allow" for d in decisions] == [True]


SRC_DIR = str(Path(harness_agent.__file__).resolve().parents[1])
KILLED_RUNS = 5

# Child program: the real ``main`` with a provider that asks to write a file in the first call
# and kills the whole process (``os._exit``, no ``close``) in the second one.
KILLED_CHILD = r"""
import os
import sys

from harness_agent.bootstrap import main
from harness_agent.core import Provider, ProviderResponse, ToolCall

config_path, text = sys.argv[1], sys.argv[2]


class KillsTheProcess(Provider):
    def __init__(self):
        self.calls = 0

    async def complete(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            call = ToolCall(
                id="c1", name="escribir_archivo", arguments={"path": "notas.txt", "content": "hola"}
            )
            return ProviderResponse(tool_calls=[call])
        os._exit(0)


import io

code = main(
    environ={"OPENAI_API_KEY": "x"},
    config_path=config_path,
    input_stream=io.StringIO(text),
    output=io.StringIO(),
    error=sys.stderr,
    provider_factory=lambda _config: KillsTheProcess(),
)
sys.exit(code)
"""


class TestSprintOneDemoKilledProcess:
    """Demo criterion 3: if the process is killed in the middle, the events that happened stay."""

    @pytest.mark.parametrize("attempt", range(KILLED_RUNS))
    def test_the_events_before_the_kill_are_in_the_database_and_the_file_is_written(
        self, tmp_path: Path, attempt: int
    ) -> None:
        area = tmp_path / f"area-{attempt}"
        area.mkdir()
        database = tmp_path / f"sesiones-{attempt}.db"
        config = tmp_path / f"config-{attempt}.toml"
        config.write_text(
            f'model = "openai/modelo-de-prueba"\n\n[paths]\n'
            f'workspace_root = "{area.as_posix()}"\n'
            f'sessions_db = "{database.as_posix()}"\n',
            encoding="utf-8",
            newline="",
        )
        environment = {**os.environ, "PYTHONPATH": SRC_DIR}

        result = subprocess.run(
            [sys.executable, "-c", KILLED_CHILD, str(config), "crea notas.txt\n"],
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert (area / "notas.txt").read_text(encoding="utf-8") == "hola"
        with SqliteSessionStore(database) as reopened:
            sessions = reopened.list_sessions()
            assert len(sessions) == 1
            types = [e.type for e in reopened.load_session(sessions[0].id)]
        assert types[0] is EventType.USER_MESSAGE
        assert EventType.PERMISSION_DECIDED in types
        assert EventType.TOOL_FINISHED in types
        assert EventType.INTERRUPTED not in types
