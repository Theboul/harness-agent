"""The four file tools in the real registry and under the real policy (HU-01-03 / T013, Sp1-21).

The permission policy classifies a call by the risk the tool declares and by its ``path`` argument
(``specs/007-permission-policy/contracts/path_argument_convention.md``). These tests pin that
contract with the real registry, the real policy and a real area.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.adapters.system import WorkspaceArea
from harness_agent.adapters.tools.list_files import ListFilesTool
from harness_agent.adapters.tools.read_file import ReadFileTool
from harness_agent.adapters.tools.search_text import SearchTextTool
from harness_agent.adapters.tools.write_file import WriteFileTool
from harness_agent.core import (
    DefaultPermissionPolicy,
    InMemoryToolRegistry,
    PermissionDecision,
    PermissionRules,
    RiskLevel,
    Tool,
    ToolCall,
    ToolValidationError,
)

EXPECTED_RISK = {
    "leer_archivo": RiskLevel.LOW,
    "listar_archivos": RiskLevel.LOW,
    "buscar_texto": RiskLevel.LOW,
    "escribir_archivo": RiskLevel.MEDIUM,
}


@pytest.fixture
def area(tmp_path: Path) -> WorkspaceArea:
    (tmp_path / "area").mkdir()
    return WorkspaceArea(tmp_path / "area")


@pytest.fixture
def tools(area: WorkspaceArea) -> list[Tool]:
    return [ReadFileTool(area), WriteFileTool(area), ListFilesTool(area), SearchTextTool(area)]


@pytest.fixture
def registry(tools: list[Tool]) -> InMemoryToolRegistry:
    registry = InMemoryToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def call(name: str, **arguments: object) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=dict(arguments))


class TestRegistration:
    def test_the_four_tools_register_with_unique_names(
        self, registry: InMemoryToolRegistry
    ) -> None:
        names = [tool.name for tool in registry.list()]

        assert sorted(names) == sorted(EXPECTED_RISK)
        assert len(set(names)) == 4

    def test_every_tool_is_found_by_name(self, registry: InMemoryToolRegistry) -> None:
        for name in EXPECTED_RISK:
            found = registry.get(name)
            assert found is not None
            assert found.name == name

    def test_registering_a_second_copy_is_a_collision(self, tools: list[Tool]) -> None:
        registry = InMemoryToolRegistry()
        registry.register(tools[0])

        with pytest.raises(ValueError):
            registry.register(tools[0])


class TestDeclaredRisk:
    @pytest.mark.parametrize(("name", "risk"), sorted(EXPECTED_RISK.items()))
    def test_each_tool_declares_its_risk(
        self, registry: InMemoryToolRegistry, name: str, risk: RiskLevel
    ) -> None:
        tool = registry.get(name)

        assert tool is not None
        assert tool.risk is risk

    def test_only_writing_is_medium_risk_and_nothing_is_high(
        self, registry: InMemoryToolRegistry
    ) -> None:
        risks = {tool.name: tool.risk for tool in registry.list()}

        assert [n for n, r in risks.items() if r is RiskLevel.MEDIUM] == ["escribir_archivo"]
        assert RiskLevel.HIGH not in risks.values()


class TestArgumentsAreValidatedByTheRegistry:
    @pytest.mark.parametrize(
        ("name", "arguments"),
        [
            ("leer_archivo", {}),
            ("leer_archivo", {"path": ""}),
            ("leer_archivo", {"path": 42}),
            ("leer_archivo", {"path": "x", "extra": "no"}),
            ("leer_archivo", {"path": "x", "source": "otra"}),
            ("escribir_archivo", {"path": "x"}),
            ("escribir_archivo", {"path": "x", "content": 5}),
            ("escribir_archivo", {"path": "x", "content": "y", "destino": "z"}),
            ("listar_archivos", {"path": None}),
            ("buscar_texto", {"path": "x"}),
            ("buscar_texto", {"path": "x", "query": ""}),
            ("buscar_texto", {"path": "x", "query": "q" * 201}),
        ],
    )
    def test_malformed_arguments_are_rejected_before_the_tool(
        self, registry: InMemoryToolRegistry, name: str, arguments: dict[str, object]
    ) -> None:
        with pytest.raises(ToolValidationError):
            registry.validate_args(name, arguments)

    @pytest.mark.parametrize(
        ("name", "arguments"),
        [
            ("leer_archivo", {"path": "a.txt"}),
            ("escribir_archivo", {"path": "a.txt", "content": ""}),
            ("listar_archivos", {"path": "."}),
            ("buscar_texto", {"path": ".", "query": "q"}),
        ],
    )
    def test_well_formed_arguments_pass(
        self, registry: InMemoryToolRegistry, name: str, arguments: dict[str, object]
    ) -> None:
        assert registry.validate_args(name, arguments) == arguments

    def test_the_only_path_like_argument_is_called_path(self, tools: list[Tool]) -> None:
        for tool in tools:
            properties = tool.schema["properties"]
            assert "path" in properties
            assert [k for k in properties if k not in {"path", "content", "query"}] == []


class TestPolicyDecisionPerTool:
    @pytest.fixture
    def policy(
        self, registry: InMemoryToolRegistry, area: WorkspaceArea
    ) -> DefaultPermissionPolicy:
        return DefaultPermissionPolicy(registry, area, PermissionRules())

    @pytest.mark.parametrize("name", sorted(EXPECTED_RISK))
    def test_a_path_inside_the_area_is_allowed(
        self, policy: DefaultPermissionPolicy, name: str
    ) -> None:
        assert policy.evaluate(call(name, path="src/main.py")) is PermissionDecision.ALLOW

    @pytest.mark.parametrize("name", sorted(EXPECTED_RISK))
    def test_a_path_outside_the_area_is_asked(
        self, policy: DefaultPermissionPolicy, name: str
    ) -> None:
        assert policy.evaluate(call(name, path="../fuera.txt")) is PermissionDecision.ASK

    @pytest.mark.parametrize("name", sorted(EXPECTED_RISK))
    @pytest.mark.parametrize("path", [42, "", "   ", "a\x00b"])
    def test_a_malformed_path_is_denied(
        self, policy: DefaultPermissionPolicy, name: str, path: object
    ) -> None:
        assert policy.evaluate(call(name, path=path)) is PermissionDecision.DENY

    def test_a_write_without_a_path_is_denied_and_a_read_without_one_is_asked(
        self, policy: DefaultPermissionPolicy
    ) -> None:
        # the registry rejects both before the policy sees them; this pins the policy's own rule
        assert policy.evaluate(call("escribir_archivo", content="x")) is PermissionDecision.DENY
        assert policy.evaluate(call("leer_archivo")) is PermissionDecision.ASK

    def test_without_an_area_every_tool_is_asked(self, registry: InMemoryToolRegistry) -> None:
        policy = DefaultPermissionPolicy(registry, None, PermissionRules())

        for name in EXPECTED_RISK:
            assert policy.evaluate(call(name, path="a.txt")) is PermissionDecision.ASK

    def test_the_read_rule_can_be_turned_off_and_writing_still_works(
        self, registry: InMemoryToolRegistry, area: WorkspaceArea
    ) -> None:
        policy = DefaultPermissionPolicy(
            registry, area, PermissionRules(), allow_reads_in_area=False
        )

        assert policy.evaluate(call("leer_archivo", path="a.txt")) is PermissionDecision.ASK
        assert policy.evaluate(call("buscar_texto", path=".", query="q")) is PermissionDecision.ASK
        assert policy.evaluate(call("escribir_archivo", path="a.txt")) is PermissionDecision.ALLOW

    def test_changing_a_tool_risk_would_change_the_decision(self, area: WorkspaceArea) -> None:
        """Documents why the declared risk matters: a high-risk tool is always asked."""

        class RiskyWrite(WriteFileTool):
            @property
            def risk(self) -> RiskLevel:
                return RiskLevel.HIGH

        registry = InMemoryToolRegistry()
        registry.register(RiskyWrite(area))
        policy = DefaultPermissionPolicy(registry, area, PermissionRules())

        assert policy.evaluate(call("escribir_archivo", path="a.txt")) is PermissionDecision.ASK
