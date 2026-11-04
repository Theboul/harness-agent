"""``/auditoria [id]`` and ``/trazas [id]`` (HU-05-05, HU-10-01 / T009).

Two commands registered by ``run_session``: the session in force by default, an identifier
optional, a short table, never an exception and never a write. The text comes from the core;
``cli/`` is not touched.
"""

from __future__ import annotations

import dataclasses
import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.bootstrap import Composition, run_session
from harness_agent.config import TraceSettings
from harness_agent.core import (
    AUDIT_READ_FAILED,
    NO_AUDIT_ROWS,
    NO_TRACE_ROWS,
    TRACE_READ_FAILED,
    TRACES_OFF,
    ProviderResponse,
    Shell,
    ShellResult,
    ToolCall,
)
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import build, make_config

SENTINEL = "VALOR-DE-PRUEBA-123"
READING = ProviderResponse(
    content="", tool_calls=[ToolCall("r1", "leer_archivo", {"path": "notas.txt"})]
)
DONE = ProviderResponse(content="listo")


class NoShell(Shell):
    @property
    def interpreter_name(self) -> str:
        return "bash"

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        raise AssertionError("no command runs in these tests")

    def terminate_running(self) -> None:
        """Nothing runs."""


@pytest.fixture(autouse=True)
def no_real_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: NoShell())


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def compose_with(
    tmp_path: Path,
    opened: list[Composition],
    *script: ProviderResponse,
    traces: TraceSettings = TraceSettings(),  # noqa: B008 (immutable)
) -> Composition:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "notas.txt").write_text("hola", encoding="utf-8")
    config = dataclasses.replace(make_config(tmp_path, workspace=workspace), traces=traces)
    return build(opened, config, FakeProvider(list(script) or [DONE]), system_name="Linux")


async def drive(composition: Composition, *lines: str) -> str:
    output = io.StringIO()
    await run_session(
        composition,
        input_stream=io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir"))),
        output=output,
    )
    return output.getvalue().replace("tarea> ", "")


def rows_written(composition: Composition) -> tuple[Any, Any]:
    connection = composition.store.connection()
    return (
        connection.execute("SELECT COUNT(*) FROM auditoria").fetchone()[0],
        connection.execute("SELECT COUNT(*) FROM trazas").fetchone()[0],
    )


# --- /auditoria -------------------------------------------------------------------------------


async def test_without_an_identifier_the_audit_of_the_current_session_is_shown(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = compose_with(tmp_path, opened, READING, DONE)

    shown = await drive(composition, "lee", "/auditoria")

    assert f"Auditoría de la sesión {composition.session_id} (1 registro)." in shown
    assert "leer_archivo" in shown and "permitida" in shown and "agente" in shown
    assert '{"path": "notas.txt"}' in shown


async def test_with_an_identifier_the_audit_of_that_session_is_shown(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = compose_with(tmp_path, opened, READING, DONE)
    await drive(past, "lee")
    current = compose_with(tmp_path, opened)

    shown = await drive(current, f"/auditoria {past.session_id}", "/auditoria")

    assert f"Auditoría de la sesión {past.session_id} (1 registro)." in shown
    assert NO_AUDIT_ROWS in shown  # the current session has none yet


async def test_after_new_the_session_in_force_is_the_new_one(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = compose_with(tmp_path, opened, READING, DONE)

    shown = await drive(
        composition, "lee", "/nueva", f"/auditoria {composition.session_id}", "/auditoria"
    )

    assert f"Auditoría de la sesión {composition.session_id} (1 registro)." in shown
    assert shown.count(NO_AUDIT_ROWS) == 1  # the new session, with no decision yet


@pytest.mark.parametrize(
    "argument", [f"id con espacios {SENTINEL}", "a/b", "x" * 300, f"{SENTINEL}!"]
)
async def test_an_identifier_that_is_not_one_is_a_fixed_line_that_does_not_repeat_it(
    tmp_path: Path, opened: list[Composition], argument: str
) -> None:
    composition = compose_with(tmp_path, opened)

    shown = await drive(composition, f"/auditoria {argument}")

    assert "El identificador de sesión no es válido." in shown
    assert SENTINEL not in shown and "x" * 100 not in shown


async def test_an_unknown_identifier_has_no_rows_and_the_audit_of_a_failed_read_is_a_fixed_line(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = compose_with(tmp_path, opened, READING, DONE)
    await drive(composition, "lee")
    assert composition.audit is not None

    assert NO_AUDIT_ROWS in await drive(composition, "/auditoria no-existe")

    composition.store.connection().execute("DROP TABLE auditoria")
    shown = await drive(composition, "/auditoria", "/ayuda")
    assert AUDIT_READ_FAILED in shown and "/auditoria" in shown  # the session goes on


async def test_the_audit_command_writes_nothing(tmp_path: Path, opened: list[Composition]) -> None:
    composition = compose_with(tmp_path, opened, READING, DONE)
    await drive(composition, "lee")
    before = rows_written(composition)

    await drive(composition, "/auditoria", "/auditoria no-existe", "/auditoria con espacios")

    assert rows_written(composition) == before


# --- /trazas ----------------------------------------------------------------------------------


async def test_without_an_identifier_the_traces_of_the_current_session_are_shown(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = compose_with(tmp_path, opened, READING, DONE)

    shown = await drive(composition, "lee", "/trazas")

    assert f"Trazas de la sesión {composition.session_id} (3 llamadas)." in shown
    assert "leer_archivo" in shown and "modelo" in shown and "sin dato" in shown


async def test_with_an_identifier_the_traces_of_that_session_are_shown(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = compose_with(tmp_path, opened, DONE)
    await drive(past, "hola")
    current = compose_with(tmp_path, opened)

    shown = await drive(current, f"/trazas {past.session_id}", "/trazas")

    assert f"Trazas de la sesión {past.session_id} (1 llamada)." in shown
    assert NO_TRACE_ROWS in shown


@pytest.mark.parametrize("argument", [f"id con espacios {SENTINEL}", "a/b", f"{SENTINEL}!"])
async def test_a_bad_identifier_for_the_traces_is_a_fixed_line(
    tmp_path: Path, opened: list[Composition], argument: str
) -> None:
    composition = compose_with(tmp_path, opened)

    shown = await drive(composition, f"/trazas {argument}")

    assert "El identificador de sesión no es válido." in shown and SENTINEL not in shown


async def test_with_the_traces_off_the_command_says_so_and_writes_nothing(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = compose_with(tmp_path, opened, READING, DONE, traces=TraceSettings(enabled=False))

    shown = await drive(composition, "lee", "/trazas", f"/trazas {composition.session_id}")

    assert shown.count(TRACES_OFF) == 2
    assert rows_written(composition)[1] == 0


async def test_a_failed_read_of_the_traces_is_a_fixed_line_and_the_session_goes_on(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = compose_with(tmp_path, opened, READING, DONE)
    await drive(composition, "lee")
    composition.store.connection().execute("DROP TABLE trazas")

    shown = await drive(composition, "/trazas", "/ayuda")

    assert TRACE_READ_FAILED in shown and "/trazas" in shown
    assert "trazas" not in TRACE_READ_FAILED.replace("las trazas", "")


async def test_the_help_lists_both_commands(tmp_path: Path, opened: list[Composition]) -> None:
    composition = compose_with(tmp_path, opened)

    shown = await drive(composition, "/ayuda")

    assert "  /auditoria  " in shown and "  /trazas  " in shown


async def test_a_composition_without_the_logs_says_so_instead_of_failing(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = compose_with(tmp_path, opened)
    bare = dataclasses.replace(composition, audit=None, traces=None)

    shown = await drive(bare, "/auditoria", "/trazas")

    assert AUDIT_READ_FAILED in shown and TRACES_OFF in shown
