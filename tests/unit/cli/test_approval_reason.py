"""ConsoleApprover asks for the rejection reason after option 3 (HU-05-04)."""

from __future__ import annotations

import io
from typing import Any

import pytest

from harness_agent.cli import ConsoleApprover
from harness_agent.core import ApprovalAction, ApprovalResult, ToolCall

PROMPT = "motivo (opcional, Enter para omitir)> "
SENTINEL = "VALOR-DE-PRUEBA-123"


async def ask(typed: str) -> tuple[ApprovalResult, str, io.StringIO]:
    stream = io.StringIO(typed)
    output = io.StringIO()
    details: dict[str, Any] = {"tool": "shell", "arguments": {"command": "ls"}, "risk": "high"}
    result = await ConsoleApprover(stream, output).request(
        ToolCall(id="c1", name="shell", arguments={"command": "ls"}), details
    )
    return result, output.getvalue(), stream


async def test_option_three_asks_for_the_reason_and_returns_it() -> None:
    result, shown, _ = await ask("3\nusa pytest\n")

    assert result == ApprovalResult(ApprovalAction.REJECT, "usa pytest")
    assert PROMPT in shown


@pytest.mark.parametrize("typed", ["3\n\n", "3\n   \n", "3\n", "3\n/salir\n"])
async def test_an_empty_line_the_end_of_input_or_exit_gives_no_reason(typed: str) -> None:
    result, shown, _ = await ask(typed)

    assert result == ApprovalResult(ApprovalAction.REJECT)
    assert result.reason is None
    assert PROMPT in shown


@pytest.mark.parametrize("option", ["1", "2"])
async def test_approving_never_asks_for_a_reason(option: str) -> None:
    result, shown, stream = await ask(f"{option}\nsobra\n")

    assert result.action is not ApprovalAction.REJECT
    assert result.reason is None
    assert "motivo" not in shown
    assert stream.readline() == "sobra\n"


async def test_a_pasted_reason_with_control_characters_is_cleaned() -> None:
    result, _, _ = await ask(
        "3\nuno" + chr(27) + "[31m" + chr(0x202E) + " dos" + chr(0x200B) + "\n"
    )

    assert result.reason == "uno[31m dos"


async def test_the_reason_is_never_written_to_the_output() -> None:
    result, shown, _ = await ask(f"3\n{SENTINEL}\n")

    assert result.reason == SENTINEL
    assert SENTINEL not in shown


async def test_a_huge_reason_is_bounded() -> None:
    result, _, _ = await ask("3\n" + "x" * 50_000 + "\n")

    assert result.reason is not None
    assert len(result.reason) <= 200


async def test_an_invalid_option_does_not_ask_for_a_reason() -> None:
    result, shown, _ = await ask("9\n9\n9\n")

    assert result == ApprovalResult(ApprovalAction.REJECT)
    assert "motivo" not in shown
