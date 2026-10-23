"""Unit tests of ``DefaultPermissionPolicy`` (HU-05-01 / T003 and T004).

The behaviour clause by clause is in ``tests/contracts/test_permission_policy_contract.py``;
here: the construction, the exceptions that must not be caught and what the policy never touches.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

import harness_agent.core as core
from harness_agent.core import PermissionDecision, PermissionPolicy, RiskLevel
from harness_agent.core.permissions import DefaultPermissionPolicy, PermissionRules
from tests.doubles.dummy_authorized_area import DummyAuthorizedArea
from tests.unit.core.permissions.support import (
    SENTINEL,
    AreaStub,
    RiskTool,
    make_call,
    make_registry,
)

PD = PermissionDecision


class TestConstruccion:
    def test_it_implements_the_port(self) -> None:
        policy = DefaultPermissionPolicy(make_registry())

        assert isinstance(policy, PermissionPolicy)

    @pytest.mark.parametrize("registry", [None, "registro", 5, object()])
    def test_the_registry_must_be_a_tool_registry(self, registry: Any) -> None:
        with pytest.raises(TypeError) as raised:
            DefaultPermissionPolicy(registry)

        assert str(raised.value).startswith("El registro de herramientas debe ser un ToolRegistry")

    @pytest.mark.parametrize("area", ["/area", 5, object()])
    def test_the_area_must_be_an_authorized_area_or_none(self, area: Any) -> None:
        with pytest.raises(TypeError) as raised:
            DefaultPermissionPolicy(make_registry(), area)

        assert str(raised.value).startswith("El área autorizada debe ser un AuthorizedArea o None")

    @pytest.mark.parametrize("rules", [("a",), ["a"], {"deny": ["a"]}, "a", 5])
    def test_the_rules_must_be_permission_rules(self, rules: Any) -> None:
        with pytest.raises(TypeError) as raised:
            DefaultPermissionPolicy(make_registry(), None, rules)

        assert str(raised.value).startswith("Las reglas deben ser un PermissionRules")

    def test_the_construction_messages_do_not_reproduce_the_value(self) -> None:
        with pytest.raises(TypeError) as raised:
            DefaultPermissionPolicy(SENTINEL)  # type: ignore[arg-type]

        assert SENTINEL not in str(raised.value)
        assert "'str'" in str(raised.value)

    def test_the_area_and_the_rules_are_optional(self) -> None:
        policy = DefaultPermissionPolicy(make_registry(RiskTool("x", RiskLevel.HIGH)))

        assert policy.evaluate(make_call("x")) is PD.ASK
        policy = DefaultPermissionPolicy(make_registry(), AreaStub(), PermissionRules())
        assert policy.evaluate(make_call("x")) is PD.ASK


class TestExcepciones:
    def test_an_ordinary_exception_is_converted_into_deny(self) -> None:
        class Broken(RiskTool):
            @property
            def risk(self) -> RiskLevel:
                raise ValueError(SENTINEL)

        policy = DefaultPermissionPolicy(make_registry(Broken("rota")))

        assert policy.evaluate(make_call("rota")) is PD.DENY

    @pytest.mark.parametrize("error", [KeyboardInterrupt, SystemExit, GeneratorExit])
    def test_an_exception_that_is_not_ordinary_is_not_caught(
        self, error: type[BaseException]
    ) -> None:
        class Interrupting(RiskTool):
            @property
            def risk(self) -> RiskLevel:
                raise error()

        policy = DefaultPermissionPolicy(make_registry(Interrupting("t")))

        with pytest.raises(error):
            policy.evaluate(make_call("t"))


class TestPurezaDeLaEvaluacion:
    def test_the_arguments_of_the_call_are_not_modified(self) -> None:
        policy = DefaultPermissionPolicy(make_registry(RiskTool("t", RiskLevel.HIGH)))
        call = make_call("t", path="/a/b", extra={"anidado": [1, 2, {"x": SENTINEL}]})
        before = copy.deepcopy(call)

        policy.evaluate(call)

        assert call == before

    def test_the_same_call_gives_the_same_decision_every_time(self) -> None:
        policy = DefaultPermissionPolicy(
            make_registry(RiskTool("a", RiskLevel.HIGH), RiskTool("b", RiskLevel.LOW)),
            None,
            PermissionRules(deny=("c",), ask=("d",)),
        )
        calls = [make_call(name) for name in ("a", "b", "c", "d", "zzz")]

        first = [policy.evaluate(call) for call in calls]
        second = [policy.evaluate(call) for call in calls]

        assert first == second == [PD.ASK, PD.ASK, PD.DENY, PD.ASK, PD.ASK]

    def test_two_equal_policies_decide_the_same(self) -> None:
        def build() -> DefaultPermissionPolicy:
            return DefaultPermissionPolicy(
                make_registry(RiskTool("a", RiskLevel.HIGH)), None, PermissionRules(deny=("c",))
            )

        assert build().evaluate(make_call("c")) is build().evaluate(make_call("c")) is PD.DENY


class TestAreaReal:
    """The same rules with an area that resolves paths (the contract double, over ``tmp_path``)."""

    def build(self, tmp_path: Path, risk: RiskLevel) -> DefaultPermissionPolicy:
        root = tmp_path / "proyecto"
        root.mkdir()
        return DefaultPermissionPolicy(
            make_registry(RiskTool("t", risk)), DummyAuthorizedArea(root), PermissionRules()
        )

    @pytest.mark.parametrize("risk", [RiskLevel.MEDIUM, RiskLevel.LOW])
    def test_a_path_inside_is_allowed_and_one_that_escapes_is_asked(
        self, tmp_path: Path, risk: RiskLevel
    ) -> None:
        policy = self.build(tmp_path, risk)
        root = tmp_path / "proyecto"

        assert policy.evaluate(make_call("t", path=str(root / "notas.txt"))) is PD.ALLOW
        assert policy.evaluate(make_call("t", path="notas.txt")) is PD.ALLOW  # relative to root
        assert policy.evaluate(make_call("t", path=str(root / ".." / "otro.txt"))) is PD.ASK
        assert policy.evaluate(make_call("t", path="../otro.txt")) is PD.ASK
        assert policy.evaluate(make_call("t", path=str(tmp_path / "fuera.txt"))) is PD.ASK

    def test_a_symbolic_link_that_leaves_the_area_is_asked(self, tmp_path: Path) -> None:
        policy = self.build(tmp_path, RiskLevel.MEDIUM)
        outside = tmp_path / "fuera"
        outside.mkdir()
        link = tmp_path / "proyecto" / "enlace"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("symbolic links are not available here")

        assert policy.evaluate(make_call("t", path=str(link / "x.txt"))) is PD.ASK


class TestTodoPermitirPasaPorElArea:
    """Every ALLOW is preceded by a question to the area with the path that came in the call."""

    @pytest.mark.parametrize("risk", [RiskLevel.MEDIUM, RiskLevel.LOW])
    def test_allow_only_after_the_area_was_asked_with_the_unmodified_path(
        self, risk: RiskLevel
    ) -> None:
        path = "  ./dentro/../dentro/notas.txt  "
        area = AreaStub((path,))
        policy = DefaultPermissionPolicy(
            make_registry(RiskTool("t", risk)), area, PermissionRules()
        )

        assert policy.evaluate(make_call("t", path=path)) is PD.ALLOW
        assert area.calls == [path]


class TestExportacion:
    def test_the_policy_and_the_rules_are_exported_from_core(self) -> None:
        assert core.DefaultPermissionPolicy is DefaultPermissionPolicy
        assert core.PermissionRules is PermissionRules
        for name in ("DefaultPermissionPolicy", "PermissionRules"):
            assert core.__all__.count(name) == 1
