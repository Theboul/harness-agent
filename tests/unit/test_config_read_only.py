"""``[permissions] read_only`` of the configuration (HU-05-07 / T003)."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness_agent.config import HarnessConfig, InvalidConfigError, load_config
from tests.unit.config_support import MINIMAL_CONFIG, write_config


def load(tmp_path: Path, extra: str) -> HarnessConfig:
    return load_config(write_config(tmp_path, MINIMAL_CONFIG + extra), environ={})


def test_it_is_off_by_default(tmp_path: Path) -> None:
    assert load(tmp_path, "").read_only is False
    assert load(tmp_path, "[permissions]\ndeny = []\n").read_only is False


def test_it_can_be_turned_on_and_off(tmp_path: Path) -> None:
    assert load(tmp_path, "[permissions]\nread_only = true\n").read_only is True
    assert load(tmp_path, "[permissions]\nread_only = false\n").read_only is False


@pytest.mark.parametrize("value", ['"si"', "1", "[]", '"true"'])
def test_it_must_be_a_real_boolean(tmp_path: Path, value: str) -> None:
    path = write_config(tmp_path, MINIMAL_CONFIG + f"[permissions]\nread_only = {value}\n")

    with pytest.raises(InvalidConfigError) as info:
        load_config(path, environ={})

    (problem,) = info.value.problems
    assert problem.field == "permissions.read_only"
    assert problem.message == "debe ser true o false."


def test_the_template_documents_the_switch() -> None:
    template = Path(__file__).resolve().parents[2] / "config.example.toml"

    assert "# read_only = false" in template.read_text(encoding="utf-8")
