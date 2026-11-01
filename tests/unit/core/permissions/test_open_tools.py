"""Tests for the open tools policy (HU-06-02 / FR-007).

``OpenToolsPolicy`` turns an ``ASK`` into ``ALLOW`` only for the names it is given.
"""

from __future__ import annotations

import pytest

from harness_agent.core import OpenToolsPolicy, PermissionDecision, ToolCall
from tests.doubles import ScriptedPolicy

ALLOW, ASK, DENY = PermissionDecision.ALLOW, PermissionDecision.ASK, PermissionDecision.DENY


def call(name: str) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments={})


class TestOpening:
    def test_an_ask_for_an_open_name_becomes_allow(self) -> None:
        policy = OpenToolsPolicy(ScriptedPolicy({"preguntar": ASK}), {"preguntar"})

        assert policy.evaluate(call("preguntar")) is ALLOW

    def test_deny_is_kept_for_an_open_name(self) -> None:
        policy = OpenToolsPolicy(ScriptedPolicy({"preguntar": DENY}), {"preguntar"})

        assert policy.evaluate(call("preguntar")) is DENY

    @pytest.mark.parametrize("decision", [ALLOW, ASK, DENY])
    def test_a_name_outside_the_set_is_left_alone(self, decision: PermissionDecision) -> None:
        policy = OpenToolsPolicy(ScriptedPolicy({"otra": decision}), {"preguntar"})

        assert policy.evaluate(call("otra")) is decision

    def test_a_name_in_the_ask_list_stays_asked(self) -> None:
        policy = OpenToolsPolicy(
            ScriptedPolicy({"preguntar": ASK}), {"preguntar"}, ask_names=("preguntar",)
        )

        assert policy.evaluate(call("preguntar")) is ASK


class TestFailClosed:
    def test_an_exception_of_the_inner_policy_is_a_denial(self) -> None:
        policy = OpenToolsPolicy(ScriptedPolicy({"preguntar": RuntimeError("x")}), {"preguntar"})

        assert policy.evaluate(call("preguntar")) is DENY

    def test_an_answer_that_is_not_a_decision_is_a_denial(self) -> None:
        policy = OpenToolsPolicy(ScriptedPolicy({"preguntar": "allow"}), {"preguntar"})

        assert policy.evaluate(call("preguntar")) is DENY

    def test_a_call_that_is_not_a_tool_call_is_a_denial(self) -> None:
        policy = OpenToolsPolicy(ScriptedPolicy({}), {"preguntar"})

        assert policy.evaluate("preguntar") is DENY  # type: ignore[arg-type]


class TestConstruction:
    def test_the_inner_policy_must_be_a_policy(self) -> None:
        with pytest.raises(TypeError):
            OpenToolsPolicy(object(), {"preguntar"})  # type: ignore[arg-type]

    def test_the_names_must_not_be_a_bare_string(self) -> None:
        with pytest.raises(TypeError):
            OpenToolsPolicy(ScriptedPolicy({}), "preguntar")

    def test_the_ask_list_must_not_be_a_bare_string(self) -> None:
        with pytest.raises(TypeError):
            OpenToolsPolicy(ScriptedPolicy({}), {"preguntar"}, ask_names="preguntar")
