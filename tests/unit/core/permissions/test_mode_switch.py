"""Tests of the read-only switch and the switchable policy (HU-06-06 / T001 / FR-004).

``SwitchablePolicy`` asks the restricted policy while the switch is on and the open one while it is
off; ``ReadOnlySwitch`` cannot be turned off when it was locked at the start.
"""

from __future__ import annotations

from typing import Any

import pytest

from harness_agent.core import (
    PermissionDecision,
    PermissionPolicy,
    ReadOnlySwitch,
    SwitchablePolicy,
    ToolCall,
)
from tests.doubles import ScriptedPolicy

ALLOW, ASK, DENY = PermissionDecision.ALLOW, PermissionDecision.ASK, PermissionDecision.DENY
CALL = ToolCall(id="c1", name="write", arguments={})


class Exploding(PermissionPolicy):
    def evaluate(self, call: ToolCall) -> PermissionDecision:
        raise RuntimeError("boom")


class Nonsense(PermissionPolicy):
    def evaluate(self, call: ToolCall) -> Any:
        return "allow"


class TestReadOnlySwitch:
    def test_starts_off_and_unlocked_by_default(self) -> None:
        switch = ReadOnlySwitch()
        assert (switch.enabled, switch.locked) == (False, False)

    def test_enable_and_disable(self) -> None:
        switch = ReadOnlySwitch()
        switch.enable()
        assert switch.enabled is True
        assert switch.disable() is True
        assert switch.enabled is False

    def test_a_locked_switch_stays_on(self) -> None:
        switch = ReadOnlySwitch(enabled=True, locked=True)
        assert switch.disable() is False
        assert switch.enabled is True

    def test_a_locked_switch_that_is_off_can_still_be_turned_on(self) -> None:
        switch = ReadOnlySwitch(locked=True)
        switch.enable()
        assert switch.enabled is True

    def test_locked_means_on(self) -> None:
        assert ReadOnlySwitch(locked=True).enabled is True


class TestSwitchablePolicy:
    def policy(self, switch: ReadOnlySwitch) -> SwitchablePolicy:
        return SwitchablePolicy(
            ScriptedPolicy({"write": DENY}), ScriptedPolicy({"write": ALLOW}), switch
        )

    def test_the_open_policy_answers_while_off(self) -> None:
        assert self.policy(ReadOnlySwitch()).evaluate(CALL) is ALLOW

    def test_the_restricted_policy_answers_while_on(self) -> None:
        assert self.policy(ReadOnlySwitch(enabled=True)).evaluate(CALL) is DENY

    def test_it_follows_the_switch_at_every_call(self) -> None:
        switch = ReadOnlySwitch()
        policy = self.policy(switch)
        switch.enable()
        assert policy.evaluate(CALL) is DENY
        switch.disable()
        assert policy.evaluate(CALL) is ALLOW

    @pytest.mark.parametrize("enabled", [True, False])
    def test_a_failing_policy_is_a_denial(self, enabled: bool) -> None:
        policy = SwitchablePolicy(Exploding(), Exploding(), ReadOnlySwitch(enabled=enabled))
        assert policy.evaluate(CALL) is DENY

    @pytest.mark.parametrize("enabled", [True, False])
    def test_an_answer_that_is_not_a_decision_is_a_denial(self, enabled: bool) -> None:
        policy = SwitchablePolicy(Nonsense(), Nonsense(), ReadOnlySwitch(enabled=enabled))
        assert policy.evaluate(CALL) is DENY

    @pytest.mark.parametrize(
        ("restricted", "open_", "switch"),
        [
            ("x", ScriptedPolicy({}), ReadOnlySwitch()),
            (ScriptedPolicy({}), "x", ReadOnlySwitch()),
            (ScriptedPolicy({}), ScriptedPolicy({}), "x"),
        ],
    )
    def test_wrong_collaborators_are_rejected(
        self, restricted: Any, open_: Any, switch: Any
    ) -> None:
        with pytest.raises(TypeError):
            SwitchablePolicy(restricted, open_, switch)
