"""The only message a subagent starts with: the task it was given (HU-09-01 / T004)."""

from __future__ import annotations

import json

from harness_agent.core import Message, Role
from harness_agent.core.subagents.result import RESULT_SCHEMA
from harness_agent.core.subagents.task import MAX_CONTEXT_CHARS, MAX_GOAL_CHARS, build_task

SENTINEL = "VALOR-DE-PRUEBA-123"


def user(text: str, *, external: bool = False) -> Message:
    return Message(Role.USER, text, is_external=external)


def test_the_task_has_the_goal_and_the_schema_of_the_answer() -> None:
    task = build_task("Resume el módulo de permisos.", [], RESULT_SCHEMA)

    assert "Resume el módulo de permisos." in task
    assert json.dumps(RESULT_SCHEMA, ensure_ascii=False) in task


def test_the_subagent_is_told_to_answer_only_with_the_object_and_not_to_delegate() -> None:
    task = build_task("x", [], RESULT_SCHEMA)

    assert "SOLO con un objeto JSON" in task
    assert "no puedes delegar" in task


def test_the_context_goes_in_order_and_only_what_the_user_role_wrote() -> None:
    context = [
        user("primero"),
        Message(Role.ASSISTANT, "historial del orquestador " + SENTINEL),
        Message(Role.SYSTEM, "instrucciones " + SENTINEL),
        user("dato de una herramienta " + SENTINEL, external=True),
        Message(Role.TOOL, "resultado " + SENTINEL),
        user("segundo"),
    ]

    task = build_task("x", context, RESULT_SCHEMA)

    assert task.index("primero") < task.index("segundo")
    assert SENTINEL not in task


def test_without_context_there_is_no_context_section() -> None:
    assert "## Contexto" not in build_task("x", [], RESULT_SCHEMA)
    assert "## Contexto" not in build_task("x", [user("   ")], RESULT_SCHEMA)
    assert "## Contexto" in build_task("x", [user("algo")], RESULT_SCHEMA)


def test_the_task_is_the_same_every_time_and_the_context_is_not_changed() -> None:
    context = [user("a"), user("b")]

    first = build_task("meta", context, RESULT_SCHEMA)

    assert first == build_task("meta", context, RESULT_SCHEMA)
    assert [m.content for m in context] == ["a", "b"]


def test_a_huge_goal_and_a_huge_context_are_cut_with_a_mark() -> None:
    task = build_task("g" * (MAX_GOAL_CHARS + 500), [user("c" * (MAX_CONTEXT_CHARS + 500))], {})

    assert "g" * MAX_GOAL_CHARS not in task and "c" * MAX_CONTEXT_CHARS not in task
    assert task.count("…") >= 2
