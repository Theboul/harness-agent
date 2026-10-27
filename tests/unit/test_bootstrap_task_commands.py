"""Composition root (HU-11-03 / T004): the commands of the task are allowed exactly.

``compose(..., task=)`` turns each command of the task into an ``AllowedCall`` for the ``shell``
tool and puts ``ExactCallPolicy`` between the protection of HU-11-01 and the default policy, so
deny > ask > allow holds. It also tells the model which commands it has (a system message after
the environment notice). Without commands nothing changes.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.tools import (
    COMMAND_ARGUMENT,
    DEFAULT_SHELL_TIMEOUT_SECONDS,
    MAX_COMMAND_CHARS,
    MAX_SHELL_TIMEOUT_SECONDS,
    TIMEOUT_ARGUMENT,
    ShellTool,
)
from harness_agent.bootstrap import Composition
from harness_agent.core import (
    MAX_COMMAND_TIMEOUT_SECONDS,
    CommandKind,
    PermissionRules,
    ProviderResponse,
    Role,
    TaskCommand,
    TaskDefinition,
    ToolCall,
    commands_notice,
)
from harness_agent.core.tasks import MAX_COMMAND_TEXT_CHARS
from tests.doubles import FakeProvider
from tests.unit.adapters.storage.task_support import TASK
from tests.unit.bootstrap_support import SENTINEL, build, make_config, one_turn

COMMAND = "echo listo-de-prueba"
APPROVAL_UNAVAILABLE = "[approval_required_unavailable]"
DENIED = "[permission_denied]"


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def task_with(*commands: TaskCommand) -> TaskDefinition:
    return dataclasses.replace(TASK, commands=commands)


def shell_call(**arguments: Any) -> FakeProvider:
    return FakeProvider(
        [
            ProviderResponse(tool_calls=[ToolCall(id="c1", name="shell", arguments=arguments)]),
            ProviderResponse(content="listo"),
        ]
    )


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    return workspace


async def shell_answer(
    tmp_path: Path,
    opened: list[Composition],
    task: TaskDefinition,
    rules: PermissionRules = PermissionRules(),  # noqa: B008 (immutable)
    **arguments: Any,
) -> str:
    config = make_config(tmp_path, workspace=make_workspace(tmp_path), permissions=rules)
    composition = build(opened, config, shell_call(**arguments), task=task)
    result = await one_turn(composition)
    return str([m for m in result.history if m.role is Role.TOOL][0].content)


TESTS = TaskCommand(CommandKind.TESTS, COMMAND, 60)


# --- the exact command runs without an approver --------------------------------------------


async def test_the_exact_command_of_the_task_runs_without_asking(
    tmp_path: Path, opened: list[Composition]
) -> None:
    answer = await shell_answer(
        tmp_path, opened, task_with(TESTS), command=COMMAND, timeout_seconds=60
    )

    assert answer.startswith("Código de salida: 0")
    assert "listo-de-prueba" in answer


async def test_outer_spaces_and_a_time_within_the_limit_still_match(
    tmp_path: Path, opened: list[Composition]
) -> None:
    answer = await shell_answer(
        tmp_path, opened, task_with(TESTS), command=f"  {COMMAND} ", timeout_seconds=60
    )

    assert answer.startswith("Código de salida: 0")


async def test_without_a_time_the_default_of_the_shell_must_fit(
    tmp_path: Path, opened: list[Composition]
) -> None:
    # The command allows 60 s and the shell applies 120 s when the call has no time.
    answer = await shell_answer(tmp_path, opened, task_with(TESTS), command=COMMAND)

    assert DEFAULT_SHELL_TIMEOUT_SECONDS > TESTS.timeout_seconds
    assert answer.startswith(APPROVAL_UNAVAILABLE)


async def test_with_the_default_time_limit_a_call_without_time_runs(
    tmp_path: Path, opened: list[Composition]
) -> None:
    command = TaskCommand(CommandKind.LINT, COMMAND)

    answer = await shell_answer(tmp_path, opened, task_with(command), command=COMMAND)

    assert answer.startswith("Código de salida: 0")


@pytest.mark.parametrize(
    "arguments",
    [
        {"command": f"{COMMAND} && echo {SENTINEL}", "timeout_seconds": 60},
        {"command": f"{COMMAND}; echo {SENTINEL}", "timeout_seconds": 60},
        {"command": COMMAND.upper(), "timeout_seconds": 60},
        {"command": COMMAND, "timeout_seconds": 61},
    ],
)
async def test_a_variation_is_not_allowed(
    tmp_path: Path, opened: list[Composition], arguments: dict[str, Any]
) -> None:
    answer = await shell_answer(tmp_path, opened, task_with(TESTS), **arguments)

    assert answer.startswith(APPROVAL_UNAVAILABLE)
    assert SENTINEL not in answer


# --- precedence -------------------------------------------------------------------------------


async def test_the_ask_list_wins(tmp_path: Path, opened: list[Composition]) -> None:
    answer = await shell_answer(
        tmp_path,
        opened,
        task_with(TESTS),
        PermissionRules(ask=("shell",)),
        command=COMMAND,
        timeout_seconds=60,
    )

    assert answer.startswith(APPROVAL_UNAVAILABLE)


async def test_the_deny_list_wins(tmp_path: Path, opened: list[Composition]) -> None:
    answer = await shell_answer(
        tmp_path,
        opened,
        task_with(TESTS),
        PermissionRules(deny=("shell",)),
        command=COMMAND,
        timeout_seconds=60,
    )

    assert answer.startswith(DENIED)


async def test_the_protected_area_wins(tmp_path: Path, opened: list[Composition]) -> None:
    command = "echo sesiones.db"

    answer = await shell_answer(
        tmp_path,
        opened,
        task_with(TaskCommand(CommandKind.TESTS, command)),
        command=command,
        timeout_seconds=60,
    )

    assert answer.startswith(DENIED)


# --- without commands nothing changes ----------------------------------------------------------


async def test_without_commands_the_shell_is_still_asked(
    tmp_path: Path, opened: list[Composition]
) -> None:
    answer = await shell_answer(tmp_path, opened, TASK, command=COMMAND, timeout_seconds=60)

    assert TASK.commands == ()
    assert answer.startswith(APPROVAL_UNAVAILABLE)


async def test_the_commands_of_the_criteria_are_not_allowed(
    tmp_path: Path, opened: list[Composition]
) -> None:
    criterion = next(c for c in TASK.criteria if c.command is not None)
    assert criterion.command is not None

    answer = await shell_answer(tmp_path, opened, TASK, command=criterion.command)

    assert answer.startswith(APPROVAL_UNAVAILABLE)


# --- the model is told which commands it has ---------------------------------------------------


def test_with_commands_a_system_message_lists_them(
    tmp_path: Path, opened: list[Composition]
) -> None:
    task = task_with(TESTS, TaskCommand(CommandKind.LINT, "ruff check ."))
    config = make_config(tmp_path, workspace=make_workspace(tmp_path))

    composition = build(opened, config, task=task)

    assert len(composition.history_prefix) == 3
    notice = composition.history_prefix[2]
    assert notice.role is Role.SYSTEM
    assert notice.content == commands_notice(task.commands)


@pytest.mark.parametrize("with_task", [False, True])
def test_without_commands_the_prefix_is_only_the_environment_notice(
    tmp_path: Path, opened: list[Composition], with_task: bool
) -> None:
    config = make_config(tmp_path, workspace=make_workspace(tmp_path))

    composition = build(opened, config, task=TASK if with_task else None)

    assert len(composition.history_prefix) == 2


# --- the names and limits agree with the shell tool -------------------------------------------


def test_the_limits_of_the_task_agree_with_the_shell() -> None:
    assert MAX_COMMAND_TIMEOUT_SECONDS == MAX_SHELL_TIMEOUT_SECONDS
    assert MAX_COMMAND_TEXT_CHARS <= MAX_COMMAND_CHARS


def test_the_argument_names_are_the_ones_of_the_shell_schema() -> None:
    properties = ShellTool(None, None).schema["properties"]

    assert COMMAND_ARGUMENT in properties
    assert TIMEOUT_ARGUMENT in properties
    assert ShellTool(None, None).schema["required"] == [COMMAND_ARGUMENT]
