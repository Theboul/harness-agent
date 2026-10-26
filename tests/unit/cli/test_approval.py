"""ConsoleApprover: shows the detail of the request and reads the user's choice (HU-05-03)."""

from __future__ import annotations

import io
from typing import Any

import pytest

from harness_agent.cli import ConsoleApprover
from harness_agent.core import ApprovalAction, ApprovalResult, Approver, ToolCall

SENTINEL = "VALOR-DE-PRUEBA-123"


def make_call(**arguments: Any) -> ToolCall:
    return ToolCall(id="c1", name="shell", arguments=arguments)


def make_details(**arguments: Any) -> dict[str, Any]:
    return {
        "tool": "shell",
        "arguments": dict(arguments),
        "effect": "Runs a command in the work area",
        "risk": "high",
    }


async def ask(
    typed: str, details: dict[str, Any] | None = None, attempts: int = 3
) -> tuple[ApprovalResult, str]:
    output = io.StringIO()
    approver = ConsoleApprover(io.StringIO(typed), output, max_attempts=attempts)
    result = await approver.request(make_call(), details or make_details(command="ls"))
    return result, output.getvalue()


def test_it_is_an_approver() -> None:
    assert isinstance(ConsoleApprover(io.StringIO(), io.StringIO()), Approver)


class TestDetail:
    async def test_it_shows_the_tool_every_argument_the_effect_and_the_options(self) -> None:
        _, shown = await ask("3\n", make_details(command="pip install requests", cwd="."))

        assert "El agente quiere ejecutar: shell" in shown
        assert "command: pip install requests" in shown
        assert "cwd: ." in shown
        assert "efecto: Runs a command in the work area (riesgo: alto)" in shown
        assert "[1] aprobar una vez" in shown
        assert "[2] aprobar para la sesión" in shown
        assert "[3] rechazar" in shown

    async def test_the_detail_comes_before_the_prompt(self) -> None:
        _, shown = await ask("1\n")

        assert shown.index("command: ls") < shown.index("opción>")

    @pytest.mark.parametrize(
        "name", ["api_key", "Secret", "access_token", "PASSWORD", "authorization"]
    )
    async def test_values_of_keys_that_look_like_secrets_are_hidden(self, name: str) -> None:
        _, shown = await ask("3\n", make_details(**{name: SENTINEL}))

        assert SENTINEL not in shown
        assert f"{name}: ***" in shown

    async def test_long_values_are_bounded_and_control_characters_removed(self) -> None:
        _, shown = await ask("3\n", make_details(command="a\x1b[31m" + "x" * 500 + "\nrm"))

        assert "\x1b" not in shown
        assert "x" * 300 not in shown
        assert "..." in shown

    async def test_many_arguments_are_summarized(self) -> None:
        arguments = {f"k{i}": i for i in range(30)}
        _, shown = await ask("3\n", make_details(**arguments))

        assert "k0: 0" in shown
        assert "k29" not in shown
        assert "10 más" in shown

    async def test_a_missing_effect_and_an_unknown_risk_are_shown_neutrally(self) -> None:
        details = {"tool": "shell", "arguments": {}, "effect": "", "risk": "weird"}
        _, shown = await ask("3\n", details)

        assert "efecto: (sin descripción) (riesgo: desconocido)" in shown

    async def test_details_that_are_malformed_do_not_break_the_prompt(self) -> None:
        output = io.StringIO()
        approver = ConsoleApprover(io.StringIO("3\n"), output)

        result = await approver.request(make_call(), {"arguments": 5, "effect": 3, "risk": None})

        assert result.action is ApprovalAction.REJECT
        assert "El agente quiere ejecutar: shell" in output.getvalue()


class TestChoice:
    @pytest.mark.parametrize(
        ("typed", "action"),
        [
            ("1\n", ApprovalAction.APPROVE_ONCE),
            ("2\n", ApprovalAction.APPROVE_SESSION),
            ("3\n", ApprovalAction.REJECT),
            ("  2  \r\n", ApprovalAction.APPROVE_SESSION),
        ],
        ids=["once", "session", "reject", "spaces-and-crlf"],
    )
    async def test_each_option_maps_to_its_action(self, typed: str, action: ApprovalAction) -> None:
        result, _ = await ask(typed)

        assert result == ApprovalResult(action)

    async def test_an_invalid_option_is_asked_again_without_echoing_it(self) -> None:
        result, shown = await ask(f"{SENTINEL}\n1\n")

        assert result.action is ApprovalAction.APPROVE_ONCE
        assert "Opción no válida" in shown
        assert SENTINEL not in shown

    async def test_after_the_attempts_it_rejects(self) -> None:
        result, shown = await ask("x\ny\nz\n1\n")

        assert result.action is ApprovalAction.REJECT
        assert shown.count("Opción no válida") == 3

    async def test_the_end_of_the_input_rejects(self) -> None:
        result, _ = await ask("")

        assert result.action is ApprovalAction.REJECT

    async def test_slash_exit_rejects_at_once_without_reading_more(self) -> None:
        result, shown = await ask("/salir\n1\n")

        assert result.action is ApprovalAction.REJECT
        assert "Opción no válida" not in shown

    async def test_a_blank_line_is_invalid_not_an_approval(self) -> None:
        result, _ = await ask("\n\n\n")

        assert result.action is ApprovalAction.REJECT

    def test_it_requires_at_least_one_attempt(self) -> None:
        with pytest.raises(ValueError):
            ConsoleApprover(io.StringIO(), io.StringIO(), max_attempts=0)


class TestStreams:
    async def test_it_uses_the_standard_streams_when_none_are_given(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output = io.StringIO()
        monkeypatch.setattr("sys.stdin", io.StringIO("1\n"))
        monkeypatch.setattr("sys.stdout", output)

        result = await ConsoleApprover().request(make_call(), make_details(command="ls"))

        assert result.action is ApprovalAction.APPROVE_ONCE
        assert "El agente quiere ejecutar" in output.getvalue()

    async def test_a_failing_input_stream_raises_so_the_gate_fails_closed(self) -> None:
        class Broken(io.StringIO):
            def readline(self, size: int | None = -1) -> str:  # type: ignore[override]
                raise OSError("no console")

        approver = ConsoleApprover(Broken(), io.StringIO())

        with pytest.raises(OSError):
            await approver.request(make_call(), make_details())
