"""Runs a verification command through the registered shell tool and reads the result (HU-11-04.1).

The command goes the same way as a shell call of the agent: arguments validated by the registry
and the tool of the registry (so the output limit, the work area, the time limit, the hiding of
URL credentials and the cancellation hook all apply). ``ShellTool`` answers with a labelled text;
``outcome_from_result`` turns it into a ``CommandOutcome`` for the core. The labels are pinned by
``tests/unit/adapters/tools/test_shell_outcome.py``, which runs the real tool.
"""

from __future__ import annotations

import copy
import re

from harness_agent.core import (
    CommandOutcome,
    CommandRunner,
    ToolCall,
    ToolRegistry,
    ToolResult,
)

_NO_OUTPUT = "(sin salida)"
_SUCCESS = "Código de salida: 0"
_EXIT = re.compile(r"\[codigo_de_salida=(-?[0-9]{1,12})\] ")
_TIMEOUT = re.compile(r"\[tiempo_agotado\] El comando superó los ([0-9]+(?:\.[0-9]+)?) s ")


def _output_of(content: str) -> str:
    _, _, rest = content.partition("\n")
    return "" if rest == _NO_OUTPUT else rest


def outcome_from_result(result: object) -> CommandOutcome:
    """What the ``ToolResult`` of the shell tool says; anything unknown is "did not run"."""
    if not isinstance(result, ToolResult) or not isinstance(result.content, str):
        return CommandOutcome(ran=False)
    content = result.content
    if content.startswith(_SUCCESS + "\n") or content == _SUCCESS:
        return CommandOutcome(ran=True, exit_code=0, output=_output_of(content))
    exit_match = _EXIT.match(content)
    if exit_match is not None:
        return CommandOutcome(
            ran=True, exit_code=int(exit_match.group(1)), output=_output_of(content)
        )
    timeout_match = _TIMEOUT.match(content)
    if timeout_match is not None:
        return CommandOutcome(
            ran=True,
            exit_code=None,
            timed_out=True,
            output=_output_of(content),
            timeout_seconds=float(timeout_match.group(1)),
        )
    return CommandOutcome(ran=False)


def make_command_runner(registry: ToolRegistry, tool_name: str) -> CommandRunner:
    """A runner that executes calls with the tool ``tool_name`` of ``registry``.

    Arguments that do not validate, a tool that is not registered and any ordinary failure of the
    tool are "did not run"; cancellation always propagates.
    """

    async def run(call: ToolCall) -> CommandOutcome:
        try:
            arguments = registry.validate_args(tool_name, copy.deepcopy(call.arguments))
            tool = registry.get(tool_name)
            if tool is None:
                return CommandOutcome(ran=False)
            result = await tool.run(arguments)
        except Exception:
            return CommandOutcome(ran=False)
        return outcome_from_result(result)

    return run
