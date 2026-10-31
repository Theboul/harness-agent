"""Tests for the ask ceiling (HU-08-03 / FR-001).

``AskCeilingPolicy`` may only lower an ``ALLOW`` to ``ASK``, and only for the names it is given.
"""

from __future__ import annotations

import pytest

from harness_agent.core import AskCeilingPolicy, PermissionDecision, ToolCall
from tests.doubles import ScriptedPolicy

ALLOW, ASK, DENY = PermissionDecision.ALLOW, PermissionDecision.ASK, PermissionDecision.DENY


def call(name: str) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments={})


class TestCeiling:
    def test_an_allow_for_a_capped_name_becomes_ask(self) -> None:
        policy = AskCeilingPolicy(ScriptedPolicy({"remote": ALLOW}), {"remote"})

        assert policy.evaluate(call("remote")) is ASK

    @pytest.mark.parametrize("decision", [ASK, DENY])
    def test_ask_and_deny_pass_unchanged(self, decision: PermissionDecision) -> None:
        policy = AskCeilingPolicy(ScriptedPolicy({"remote": decision}), {"remote"})

        assert policy.evaluate(call("remote")) is decision

    @pytest.mark.parametrize("decision", [ALLOW, ASK, DENY])
    def test_a_name_outside_the_set_is_left_alone(self, decision: PermissionDecision) -> None:
        policy = AskCeilingPolicy(ScriptedPolicy({"native": decision}), {"remote"})

        assert policy.evaluate(call("native")) is decision

    def test_the_set_is_live(self) -> None:
        names: set[str] = set()
        policy = AskCeilingPolicy(ScriptedPolicy({"remote": ALLOW}), names)
        assert policy.evaluate(call("remote")) is ALLOW

        names.add("remote")

        assert policy.evaluate(call("remote")) is ASK


class TestFailClosed:
    def test_an_exception_of_the_inner_policy_is_a_denial(self) -> None:
        policy = AskCeilingPolicy(ScriptedPolicy({"remote": RuntimeError("x")}), {"remote"})

        assert policy.evaluate(call("remote")) is DENY

    def test_a_value_that_is_not_a_decision_is_a_denial(self) -> None:
        policy = AskCeilingPolicy(ScriptedPolicy({"remote": "allow"}), {"remote"})

        assert policy.evaluate(call("remote")) is DENY

    def test_a_malformed_call_is_a_denial(self) -> None:
        policy = AskCeilingPolicy(ScriptedPolicy({"remote": ALLOW}), {"remote"})

        assert policy.evaluate("remote") is DENY  # type: ignore[arg-type]

    def test_the_inner_policy_must_be_a_policy(self) -> None:
        with pytest.raises(TypeError):
            AskCeilingPolicy(object(), set())  # type: ignore[arg-type]

    def test_the_names_must_be_a_container_of_texts(self) -> None:
        with pytest.raises(TypeError):
            AskCeilingPolicy(ScriptedPolicy(), 5)  # type: ignore[arg-type]
