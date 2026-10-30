"""The optional dependency of the LiteLLM adapter is declared once and pinned (HU-07-02 / FR-017).

``pyproject.toml`` declares the extra ``litellm`` (``dependencies`` stays empty: the harness runs
without it) and ``requirements-dev.txt`` pins the same version, plus the dependencies that pip
resolved for it, because that is what the CI installs. These tests keep both files in step.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest

from harness_agent.adapters.providers.litellm_provider import (
    LiteLLMProvider,
    ProviderDependencyError,
)

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
REQUIREMENTS = ROOT / "requirements-dev.txt"
CI = ROOT / ".github" / "workflows" / "ci.yml"
EXACT = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)(?P<extras>\[[A-Za-z0-9_,.-]+\])?==(?P<version>\S+)$"
)
PINNED_LITELLM = re.compile(r"^litellm\[mcp\]==(?P<version>\d+(?:\.\d+)+)$")
RELEVANT = {"openai", "pydantic", "httpx", "mcp"}


def declared_requirements() -> list[str]:
    lines = [line.strip() for line in REQUIREMENTS.read_text("utf-8").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


def names_in_requirements() -> set[str]:
    names = set()
    for line in declared_requirements():
        match = EXACT.match(line)
        assert match, line
        names.add(match["name"].lower().replace("_", "-"))
    return names


def project() -> dict[str, object]:
    return tomllib.loads(PYPROJECT.read_text("utf-8"))["project"]  # type: ignore[no-any-return]


class TestPyproject:
    def test_the_harness_still_has_no_runtime_dependencies(self) -> None:
        assert project()["dependencies"] == []

    def test_the_extra_holds_exactly_one_exact_pin_of_litellm_with_mcp(self) -> None:
        extras = project()["optional-dependencies"]
        assert isinstance(extras, dict)

        (requirement,) = extras["litellm"]

        assert PINNED_LITELLM.match(requirement), requirement

    def test_the_development_extra_does_not_pull_litellm(self) -> None:
        extras = project()["optional-dependencies"]
        assert isinstance(extras, dict)

        assert not any("litellm" in item for item in extras["dev"])


class TestTheMcpExtra:
    """The MCP adapter (HU-08-01) declares its own extra: it must not depend on ``litellm``."""

    def test_the_extra_holds_exactly_one_exact_pin_of_mcp(self) -> None:
        extras = project()["optional-dependencies"]
        assert isinstance(extras, dict)

        (requirement,) = extras["mcp"]

        assert re.fullmatch(r"mcp==\d+(?:\.\d+)+", requirement), requirement

    def test_requirements_dev_pins_the_same_version(self) -> None:
        extras = project()["optional-dependencies"]
        assert isinstance(extras, dict)

        assert extras["mcp"][0] in declared_requirements()

    def test_the_development_extra_does_not_pull_mcp(self) -> None:
        extras = project()["optional-dependencies"]
        assert isinstance(extras, dict)

        assert not any(item.startswith("mcp") for item in extras["dev"])


class TestRequirementsDev:
    def test_there_is_exactly_one_line_for_litellm_and_it_has_the_same_pin(self) -> None:
        lines = [line for line in declared_requirements() if line.lower().startswith("litellm")]
        extras = project()["optional-dependencies"]
        assert isinstance(extras, dict)

        assert lines == extras["litellm"]

    def test_every_requirement_is_pinned_to_an_exact_version(self) -> None:
        for line in declared_requirements():
            assert EXACT.match(line), f"not pinned with ==: {line}"

    def test_there_are_no_duplicates(self) -> None:
        lines = names_in_requirements()

        assert len(lines) == len(declared_requirements())

    def test_the_dependencies_pip_resolved_for_litellm_are_pinned_too(self) -> None:
        assert RELEVANT <= names_in_requirements()

    def test_the_tools_of_the_quality_gates_are_still_pinned(self) -> None:
        assert {"pytest", "pytest-asyncio", "pytest-cov", "mypy", "ruff"} <= names_in_requirements()


class TestTheCi:
    def test_the_ci_installs_requirements_dev_and_not_the_extra(self) -> None:
        text = CI.read_text("utf-8")

        assert "pip install -r requirements-dev.txt" in text
        assert ".[litellm]" not in text

    def test_the_ci_runs_on_both_systems(self) -> None:
        text = CI.read_text("utf-8")

        assert "ubuntu-latest" in text
        assert "windows-latest" in text


class TestTheInstallCommandMatchesTheExtra:
    def test_the_message_of_a_missing_library_names_the_extra_that_exists(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "litellm", None)
        extras = project()["optional-dependencies"]
        assert isinstance(extras, dict)

        with pytest.raises(ProviderDependencyError) as raised:
            LiteLLMProvider("proveedor/modelo", max_output_tokens=10)

        assert "litellm" in extras
        assert '".[litellm]"' in str(raised.value)
