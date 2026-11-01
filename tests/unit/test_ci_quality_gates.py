"""The CI enforces a minimum coverage and runs the clean-install check (HU-00-07).

The workflow is the single place where the coverage threshold lives (a ``fail_under`` in
``pyproject.toml`` would also fail every partial local run such as ``pytest path -k name``).
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI = (ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
BUSINESS_MINIMUM = 60
THRESHOLD = re.compile(r"--cov-fail-under=(?P<value>\d+)")


def threshold() -> int:
    found = THRESHOLD.findall(CI)
    assert len(found) == 1, "the CI must set the coverage threshold exactly once"
    return int(found[0])


def test_ci_sets_a_threshold_at_or_above_the_business_minimum() -> None:
    assert BUSINESS_MINIMUM <= threshold() <= 100


def test_threshold_is_set_on_the_step_that_runs_the_whole_suite() -> None:
    line = next(line for line in CI.splitlines() if "--cov-fail-under" in line)
    assert "pytest" in line
    assert "--cov=harness_agent" in line


def test_ci_runs_the_install_check_on_both_operating_systems() -> None:
    assert "pytest -m install --no-cov tests/install" in CI
    assert "ubuntu-latest" in CI and "windows-latest" in CI
    assert 'python-version: ["3.12"]' in CI


def test_install_tests_are_excluded_from_the_default_run() -> None:
    options = PYPROJECT["tool"]["pytest"]["ini_options"]
    assert "not install" in options["addopts"]
    assert any(marker.startswith("install:") for marker in options["markers"])
