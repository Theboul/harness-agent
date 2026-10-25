"""Keeps the Python children started by the shell tests out of the coverage plugin.

The tests start real Python processes. If they inherit the variables of ``pytest-cov``, each child
writes a ``.coverage.*`` data file in the repository root. The variables are removed for the
processes the tests start; the coverage of the test process itself is not affected.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def children_without_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith(("COV_CORE", "COVERAGE")):
            monkeypatch.delenv(name)
