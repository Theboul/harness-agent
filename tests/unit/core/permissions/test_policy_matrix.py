"""Exhaustive matrix of the permission policy (HU-05-01 / T006).

Every combination of risk, lists, path, area, area answer and read rule is evaluated and compared
with a reference function written here, independently of the implementation and following the
decision table of ``specs/007-permission-policy/contracts/policy_contract.md``. Properties:
ALLOW only when every condition holds and always after asking the area with the path of the call
(AC-04); deny prevails over ask and ask over allow (AC-02); nothing ever raises (SC-004).
"""

from __future__ import annotations

import itertools
import time
from typing import Any

import pytest

from harness_agent.core import PermissionDecision, RiskLevel
from harness_agent.core.permissions import DefaultPermissionPolicy, PermissionRules
from tests.unit.core.permissions.support import AreaStub, RiskTool, make_call, make_registry

PD = PermissionDecision
INSIDE = "/area/proyecto/notas.txt"
OUTSIDE = "/etc/hosts"

RISKS = ["LOW", "MEDIUM", "HIGH", "unregistered", "invalid"]
PATHS: dict[str, Any] = {
    "absent": None,
    "inside": INSIDE,
    "outside": OUTSIDE,
    "non_text": 5,
    "empty": "",
    "nul": "a\x00b",
}
AREAS = ["none", "configured"]
ANSWERS = ["membership", "always_true", "false", "non_bool", "raises"]


def answer_function(kind: str) -> Any:
    def boom(_path: object) -> bool:
        raise RuntimeError("falla del área")

    return {
        "membership": lambda p: p == INSIDE,
        "always_true": lambda _p: True,
        "false": lambda _p: False,
        "non_bool": lambda _p: 1,
        "raises": boom,
    }[kind]


def reference(
    risk: str, in_deny: bool, in_ask: bool, path: str, area: str, answer: str, reads: bool
) -> PermissionDecision:
    """The decision table of the contract, written from scratch."""
    if in_deny:
        return PD.DENY
    if in_ask:
        return PD.ASK
    if risk in ("unregistered", "invalid", "HIGH"):
        return PD.ASK
    if risk == "LOW" and (not reads or path == "absent"):
        return PD.ASK
    # the rule of the area: a write (medium) or a read with a path (low)
    if path in ("absent", "non_text", "empty", "nul"):
        return PD.DENY
    if area == "none":
        return PD.ASK
    if answer == "raises":
        return PD.DENY
    if answer == "always_true":
        return PD.ALLOW
    if answer == "membership":
        return PD.ALLOW if path == "inside" else PD.ASK
    return PD.ASK  # "false" and "non_bool" (only an exact True allows)


def build(
    risk: str, in_deny: bool, in_ask: bool, area: str, answer: str, reads: bool
) -> tuple[DefaultPermissionPolicy, AreaStub | None]:
    tools: list[RiskTool] = []
    if risk in ("LOW", "MEDIUM", "HIGH"):
        tools.append(RiskTool("t", RiskLevel[risk]))
    elif risk == "invalid":
        tools.append(RiskTool("t", "raro"))
    stub = None if area == "none" else AreaStub(result=answer_function(answer))
    rules = PermissionRules(deny=("t",) if in_deny else (), ask=("t",) if in_ask else ())
    return (
        DefaultPermissionPolicy(make_registry(*tools), stub, rules, allow_reads_in_area=reads),
        stub,
    )


def arguments(path: str) -> dict[str, Any]:
    return {} if path == "absent" else {"path": PATHS[path]}


COMBINATIONS = list(
    itertools.product(
        RISKS, [False, True], [False, True], list(PATHS), AREAS, ANSWERS, [True, False]
    )
)


class TestMatrizExhaustiva:
    def test_every_combination_matches_the_reference_and_never_raises(self) -> None:
        mismatches: list[tuple[Any, ...]] = []
        for combo in COMBINATIONS:
            risk, in_deny, in_ask, path, area, answer, reads = combo
            policy, _stub = build(risk, in_deny, in_ask, area, answer, reads)

            decision = policy.evaluate(make_call("t", **arguments(path)))

            if decision is not reference(*combo):
                mismatches.append((combo, decision))
        assert len(COMBINATIONS) == 5 * 2 * 2 * 6 * 2 * 5 * 2
        assert mismatches == [], mismatches[:5]

    def test_allow_only_when_every_condition_holds_and_after_asking_the_area(self) -> None:
        allowed = 0
        for combo in COMBINATIONS:
            risk, in_deny, in_ask, path, area, answer, reads = combo
            policy, stub = build(risk, in_deny, in_ask, area, answer, reads)

            decision = policy.evaluate(make_call("t", **arguments(path)))

            if decision is PD.ALLOW:
                allowed += 1
                assert risk in ("LOW", "MEDIUM"), combo
                assert not in_deny and not in_ask, combo
                assert risk == "MEDIUM" or (reads and path != "absent"), combo
                assert stub is not None, combo
                assert stub.calls == [PATHS[path]], combo  # the area was asked, with that path
                assert answer in ("membership", "always_true"), combo
        assert allowed > 0

    def test_no_decision_is_allow_when_the_area_was_never_asked(self) -> None:
        for combo in COMBINATIONS:
            risk, in_deny, in_ask, path, area, answer, reads = combo
            policy, stub = build(risk, in_deny, in_ask, area, answer, reads)

            decision = policy.evaluate(make_call("t", **arguments(path)))

            if stub is None or not stub.calls:
                assert decision is not PD.ALLOW, combo


class TestPrecedencia:
    ALLOWING = [
        ("MEDIUM", "inside", "membership", True),
        ("LOW", "inside", "membership", True),
        ("MEDIUM", "inside", "always_true", True),
    ]

    @pytest.mark.parametrize(("risk", "path", "answer", "reads"), ALLOWING)
    def test_deny_prevails_over_ask_and_allow(
        self, risk: str, path: str, answer: str, reads: bool
    ) -> None:
        for in_ask in (False, True):
            policy, _ = build(risk, True, in_ask, "configured", answer, reads)

            assert policy.evaluate(make_call("t", **arguments(path))) is PD.DENY

    @pytest.mark.parametrize(("risk", "path", "answer", "reads"), ALLOWING)
    def test_ask_prevails_over_allow(self, risk: str, path: str, answer: str, reads: bool) -> None:
        policy, stub = build(risk, False, True, "configured", answer, reads)

        assert policy.evaluate(make_call("t", **arguments(path))) is PD.ASK
        assert stub is not None and stub.calls == []

    @pytest.mark.parametrize(("risk", "path", "answer", "reads"), ALLOWING)
    def test_without_lists_the_same_call_is_allowed(
        self, risk: str, path: str, answer: str, reads: bool
    ) -> None:
        policy, _ = build(risk, False, False, "configured", answer, reads)

        assert policy.evaluate(make_call("t", **arguments(path))) is PD.ALLOW


class TestRendimiento:
    def test_smoke_an_evaluation_costs_less_than_a_millisecond(self) -> None:
        policy, _ = build("MEDIUM", False, False, "configured", "membership", True)
        call = make_call("t", path=INSIDE)
        policy.evaluate(call)  # warm-up
        evaluations = 1000

        start = time.perf_counter()
        for _ in range(evaluations):
            policy.evaluate(call)
        average = (time.perf_counter() - start) / evaluations

        assert average < 0.001
