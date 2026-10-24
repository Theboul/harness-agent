"""Composition root (propuesta HU-00-08 / T004, T005, T007): the session and the command.

``run_session`` runs the terminal cycle over a composition; ``main`` loads the configuration,
composes, runs and translates the startup failures. Input and output are in-memory streams, the
provider is an injected ``FakeProvider`` and the database is a temporary file.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.bootstrap import NO_AREA_NOTICE, Composition, run_session
from harness_agent.core import Event, EventType, PermissionRules, ProviderResponse, Role, ToolCall
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import build, make_config, scripted

EXIT_TEXT = "Sesión terminada."


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


async def session(composition: Composition, text: str) -> tuple[int, str]:
    output = io.StringIO()
    code = await run_session(composition, input_stream=io.StringIO(text), output=output)
    return code, output.getvalue()


class TestRunSession:
    async def test_the_notices_come_before_the_first_prompt(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=None))

        code, text = await session(composition, "/salir\n")

        assert code == 0
        assert text.startswith(NO_AREA_NOTICE + "\n")
        assert text.index("tarea> ") > len(NO_AREA_NOTICE)

    async def test_a_notice_that_the_stream_cannot_encode_is_written_with_replacements(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=None))
        raw = io.BytesIO()
        output = io.TextIOWrapper(raw, encoding="ascii", errors="strict")

        code = await run_session(composition, input_stream=io.StringIO("/salir\n"), output=output)
        output.flush()

        assert code == 0
        assert raw.getvalue().startswith(b"Aviso: no hay ")

    async def test_the_history_continues_between_the_lines_of_one_session(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider = scripted("respuesta uno", "respuesta dos")
        composition = build(opened, make_config(tmp_path, workspace=tmp_path), provider)

        code, _text = await session(composition, "primera tarea\nsegunda tarea\n/salir\n")

        assert code == 0
        assert provider.call_count == 2
        second_call = [m.content for m in provider.received[1]]
        assert second_call == ["primera tarea", "respuesta uno", "segunda tarea"]

    async def test_slash_exit_and_the_end_of_the_input_return_zero(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path))

        code_exit, text_exit = await session(composition, "/salir\n")
        code_end, _text_end = await session(composition, "")

        assert code_exit == 0
        assert EXIT_TEXT in text_exit
        assert code_end == 0

    async def test_a_turn_that_raises_an_ordinary_exception_returns_one(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path))

        def failing_subscriber(_event: Event) -> None:
            raise RuntimeError("fallo de prueba")

        composition.bus.subscribe(EventType.USER_MESSAGE, failing_subscriber)

        code, text = await session(composition, "una tarea\n/salir\n")

        assert code == 1
        assert "EventDeliveryError" in text
        assert "fallo de prueba" not in text

    async def test_an_action_that_asks_for_approval_is_denied_with_a_reason(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider = FakeProvider(
            [
                ProviderResponse(
                    tool_calls=[ToolCall(id="c1", name="leer_archivo", arguments={"path": "a.txt"})]
                ),
                ProviderResponse(content="listo"),
            ]
        )
        config = make_config(
            tmp_path, workspace=tmp_path, permissions=PermissionRules(ask=("leer_archivo",))
        )
        composition = build(opened, config, provider)

        code, _text = await session(composition, "lee a.txt\n/salir\n")

        assert code == 0
        answered = [m for m in provider.received[1] if m.role is Role.TOOL]
        assert answered[0].content.startswith("[approval_required_unavailable]")

    async def test_an_input_closed_before_the_first_task_saves_no_events(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path))

        code, _text = await session(composition, "")

        assert code == 0
        assert composition.store.load_session(composition.session_id) == []
