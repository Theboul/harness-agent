"""The ``preguntar_usuario`` tool with the real loop, policy chain and console (HU-06-02).

AC-01: three options and a choice come back as a tool result. AC-02: a free answer is accepted
too. The tool never asks for approval, and without an answer nothing is chosen by default.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.bootstrap import Composition, console_ask
from harness_agent.cli import ConsoleQuestioner
from harness_agent.cli.style import PLAIN
from harness_agent.core import (
    ApprovalAction,
    Event,
    EventType,
    PermissionRules,
    ProviderResponse,
    Role,
    ToolCall,
)
from tests.doubles import DummyApprover, FakeProvider
from tests.unit.bootstrap_support import SENTINEL, build, make_config, one_turn

OPTIONS = ["informe.md", "resultados/", "otra ruta"]


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def asking_provider(**extra: object) -> FakeProvider:
    arguments = {"pregunta": "¿Dónde guardo el resultado?", "opciones": OPTIONS, **extra}
    return FakeProvider(
        [
            ProviderResponse(
                tool_calls=[ToolCall(id="c1", name="preguntar_usuario", arguments=arguments)]
            ),
            ProviderResponse(content="listo"),
        ]
    )


def answer_seen(provider: FakeProvider) -> tuple[str, bool, bool]:
    message = next(m for m in provider.received[1] if m.role is Role.TOOL)
    assert message.tool_result is not None
    return message.content, message.tool_result.is_error, message.tool_result.call_id == "c1"


def console(typed: str, shown: io.StringIO) -> ConsoleQuestioner:
    return ConsoleQuestioner(io.StringIO(typed), shown, style=PLAIN)


async def ask_once(
    tmp_path: Path,
    opened: list[Composition],
    typed: str,
    *,
    permissions: PermissionRules = PermissionRules(),  # noqa: B008 (immutable)
    approver: DummyApprover | None = None,
    **extra: object,
) -> tuple[FakeProvider, io.StringIO, list[Event]]:
    provider = asking_provider(**extra)
    shown = io.StringIO()
    config = make_config(tmp_path, workspace=tmp_path, permissions=permissions)
    composition = build(
        opened, config, provider, ask=console_ask(console(typed, shown)), approver=approver
    )
    events: list[Event] = []
    for event_type in EventType:
        composition.bus.subscribe(event_type, events.append)
    await one_turn(composition)
    return provider, shown, events


class TestChoice:
    async def test_choosing_an_option_comes_back_as_the_tool_result(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider, shown, _ = await ask_once(tmp_path, opened, "2\n")

        content, is_error, same_call = answer_seen(provider)
        assert "resultados/" in content and not is_error and same_call
        assert "[1] informe.md" in shown.getvalue() and "[3] otra ruta" in shown.getvalue()

    async def test_the_question_is_a_tool_of_the_model(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider, _, _ = await ask_once(tmp_path, opened, "1\n")

        assert "preguntar_usuario" in {tool.name for tool in provider.received_tools[0] or []}

    async def test_a_free_answer_is_accepted(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider, _, _ = await ask_once(tmp_path, opened, "en docs/salida.txt\n")

        content, is_error, _ = answer_seen(provider)
        assert "docs/salida.txt" in content and not is_error


class TestNoDefault:
    async def test_end_of_input_is_an_error_and_no_option(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider, _, _ = await ask_once(tmp_path, opened, "")

        content, is_error, _ = answer_seen(provider)
        assert is_error and content.startswith("[sin_respuesta]")
        assert not any(option in content for option in OPTIONS)

    async def test_free_text_is_refused_when_the_question_is_closed(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider, shown, _ = await ask_once(
            tmp_path, opened, f"{SENTINEL}\n" * 3, permitir_texto_libre=False
        )

        content, is_error, _ = answer_seen(provider)
        assert is_error and SENTINEL not in content and SENTINEL not in shown.getvalue()


class TestPermissionsAndEvents:
    async def test_the_tool_does_not_ask_for_approval(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        approver = DummyApprover(ApprovalAction.REJECT)

        provider, _, events = await ask_once(tmp_path, opened, "1\n", approver=approver)

        assert approver.recorded_requests == []
        assert not answer_seen(provider)[1]
        assert EventType.APPROVAL_REQUESTED not in {event.type for event in events}

    async def test_a_name_in_the_ask_list_is_still_asked(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        approver = DummyApprover(ApprovalAction.REJECT)
        permissions = PermissionRules(ask=("preguntar_usuario",))

        provider, _, _ = await ask_once(
            tmp_path, opened, "1\n", permissions=permissions, approver=approver
        )

        assert len(approver.recorded_requests) == 1
        assert answer_seen(provider)[0].startswith("[approval_rejected]")

    async def test_a_name_in_the_deny_list_is_denied(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider, shown, _ = await ask_once(
            tmp_path, opened, "1\n", permissions=PermissionRules(deny=("preguntar_usuario",))
        )

        assert answer_seen(provider)[0].startswith("[permission_denied]")
        assert shown.getvalue() == ""

    async def test_events_carry_neither_question_nor_answer(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        _, _, events = await ask_once(tmp_path, opened, f"{SENTINEL}\n", pregunta="¿QUIEN-ES?")

        assert SENTINEL not in repr([event.payload for event in events])
        assert "QUIEN-ES" not in repr([event.payload for event in events])


class TestWithoutAsk:
    async def test_without_ask_the_tool_does_not_exist(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider = asking_provider()
        composition = build(opened, make_config(tmp_path, workspace=tmp_path), provider)

        await one_turn(composition)

        content, is_error, _ = answer_seen(provider)
        assert is_error and content.startswith("[unknown_tool]")
