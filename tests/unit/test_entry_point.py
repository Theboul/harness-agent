"""Entry point of the harness (propuesta HU-00-08 / T005).

Covers ``python -m harness_agent`` and the ``harness`` command declared in ``pyproject.toml``.
"""

from __future__ import annotations

import importlib
import runpy
import tomllib
from pathlib import Path

import pytest

from harness_agent import bootstrap

ROOT = Path(__file__).resolve().parents[2]


class TestTheModuleEntry:
    def test_running_the_package_calls_the_entry_and_exits_with_its_code(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[object, ...]] = []

        def fake_entry(*args: object, **kwargs: object) -> int:
            calls.append((args, tuple(kwargs.items())))
            return 7

        monkeypatch.setattr(bootstrap, "entry", fake_entry)

        with pytest.raises(SystemExit) as raised:
            runpy.run_module("harness_agent", run_name="__main__")

        assert raised.value.code == 7
        assert calls == [((), ())]


class TestTheCommand:
    def test_pyproject_declares_the_harness_command(self) -> None:
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        assert data["project"]["scripts"] == {"harness": "harness_agent.bootstrap:entry"}

    def test_the_declared_target_exists_and_is_the_entry(self) -> None:
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        module_name, _, function_name = data["project"]["scripts"]["harness"].partition(":")

        target = getattr(importlib.import_module(module_name), function_name)

        assert target is bootstrap.entry
