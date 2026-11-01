"""Tests of the read-only policy (HU-05-07 / T002 / FR-001, FR-002).

``ReadOnlyPolicy`` denies every call except those to the tools it is given as reads and the
commands its classifier says are reads; for those it returns the answer of the wrapped policy.
"""

from __future__ import annotations

from typing import Any

import pytest

from harness_agent.core import PermissionDecision, ReadOnlyPolicy, ToolCall
from tests.doubles import ScriptedPolicy

ALLOW, ASK, DENY = PermissionDecision.ALLOW, PermissionDecision.ASK, PermissionDecision.DENY


def call(name: str, **arguments: Any) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments)


def policy(inner: ScriptedPolicy | None = None, **options: Any) -> ReadOnlyPolicy:
    defaults: dict[str, Any] = {
        "command_tool": "run",
        "command_argument": "text",
        "is_read_command": lambda text: text.startswith("look"),
    }
    defaults.update(options)
    return ReadOnlyPolicy(
        inner if inner is not None else ScriptedPolicy({"read": ALLOW, "run": ALLOW}),
        {"read", "list"},
        **defaults,
    )


class TestReadTools:
    @pytest.mark.parametrize("decision", [ALLOW, ASK, DENY])
    def test_a_read_tool_gets_the_answer_of_the_wrapped_policy(
        self, decision: PermissionDecision
    ) -> None:
        assert policy(ScriptedPolicy({"read": decision})).evaluate(call("read")) is decision

    def test_a_tool_outside_the_set_is_denied_even_if_the_inner_allows_it(self) -> None:
        assert policy(ScriptedPolicy({"write": ALLOW})).evaluate(call("write")) is DENY

    def test_a_tool_that_nobody_knows_is_denied(self) -> None:
        assert policy().evaluate(call("mcp_tool")) is DENY


class TestCommands:
    def test_a_read_command_gets_the_answer_of_the_wrapped_policy(self) -> None:
        assert policy().evaluate(call("run", text="look here")) is ALLOW
        assert policy(ScriptedPolicy({"run": ASK})).evaluate(call("run", text="look")) is ASK

    def test_a_command_that_is_not_a_read_is_denied(self) -> None:
        assert policy().evaluate(call("run", text="rm x")) is DENY

    @pytest.mark.parametrize("arguments", [{}, {"text": 3}, {"text": None}, {"other": "look"}])
    def test_a_missing_or_odd_command_is_denied(self, arguments: dict[str, Any]) -> None:
        assert policy().evaluate(call("run", **arguments)) is DENY

    @pytest.mark.parametrize("verdict", [1, "True", None, object()])
    def test_only_an_exact_true_from_the_classifier_opens_the_door(self, verdict: object) -> None:
        assert policy(is_read_command=lambda _text: verdict).evaluate(call("run", text="x")) is DENY

    def test_a_classifier_that_raises_is_a_denial(self) -> None:
        def boom(_text: str) -> bool:
            raise RuntimeError("x")

        assert policy(is_read_command=boom).evaluate(call("run", text="look")) is DENY

    def test_without_a_command_tool_no_command_runs(self) -> None:
        bare = ReadOnlyPolicy(ScriptedPolicy({"run": ALLOW}), {"read"})

        assert bare.evaluate(call("run", text="look")) is DENY

    def test_a_command_tool_without_classifier_is_denied(self) -> None:
        half = ReadOnlyPolicy(
            ScriptedPolicy({"run": ALLOW}), {"read"}, command_tool="run", command_argument="text"
        )

        assert half.evaluate(call("run", text="look")) is DENY


class TestFailClosed:
    def test_an_exception_of_the_inner_policy_is_a_denial(self) -> None:
        assert policy(ScriptedPolicy({"read": RuntimeError("x")})).evaluate(call("read")) is DENY

    def test_an_answer_that_is_not_a_decision_is_a_denial(self) -> None:
        assert policy(ScriptedPolicy({"read": "allow"})).evaluate(call("read")) is DENY

    def test_a_call_that_is_not_a_tool_call_is_a_denial(self) -> None:
        assert policy().evaluate("read") is DENY  # type: ignore[arg-type]

    def test_a_call_with_odd_arguments_is_a_denial(self) -> None:
        odd = ToolCall(id="c1", name="run", arguments=None)  # type: ignore[arg-type]

        assert policy().evaluate(odd) is DENY


class TestConstruction:
    def test_the_wrapped_policy_must_be_a_policy(self) -> None:
        with pytest.raises(TypeError):
            ReadOnlyPolicy(object(), {"read"})  # type: ignore[arg-type]

    def test_a_single_text_is_not_a_set_of_names(self) -> None:
        with pytest.raises(TypeError):
            ReadOnlyPolicy(ScriptedPolicy({}), "read")

    @pytest.mark.parametrize("names", [[""], [3], [" "]])
    def test_the_names_must_be_texts(self, names: list[Any]) -> None:
        with pytest.raises(TypeError):
            ReadOnlyPolicy(ScriptedPolicy({}), names)

    def test_the_command_tool_and_argument_go_together(self) -> None:
        with pytest.raises(TypeError):
            ReadOnlyPolicy(ScriptedPolicy({}), {"read"}, command_tool="run")
        with pytest.raises(TypeError):
            ReadOnlyPolicy(ScriptedPolicy({}), {"read"}, command_argument="text")

    @pytest.mark.parametrize(("tool", "argument"), [("", "text"), ("run", " "), (3, "text")])
    def test_the_command_tool_and_argument_must_be_names(self, tool: Any, argument: Any) -> None:
        with pytest.raises(TypeError):
            ReadOnlyPolicy(
                ScriptedPolicy({}), {"read"}, command_tool=tool, command_argument=argument
            )

    def test_the_classifier_must_be_callable(self) -> None:
        with pytest.raises(TypeError):
            ReadOnlyPolicy(
                ScriptedPolicy({}),
                {"read"},
                command_tool="run",
                command_argument="text",
                is_read_command="x",  # type: ignore[arg-type]
            )
