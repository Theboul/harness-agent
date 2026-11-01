"""Architecture guard of the redaction of secrets (HU-10-02 / T005).

* ``core/secret_redaction.py`` is pure: standard library and ``core.redaction`` only, no I/O, no
  environment, no terminal, nothing asynchronous, no catching of ``BaseException``;
* **only the composition root** builds a ``SecretRedactor``, and in ``compose()`` the three write
  points (messages, events, summaries) receive it: a write point without it would silently store
  secrets again;
* the module never names the ``adapters``, the loop or ``config``.

Each rule is proved on the real files and on a mutated copy that breaks it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.test_approvals_boundaries import catches_cancellation, imported_modules
from tests.architecture.test_compaction_boundaries import mutate
from tests.architecture.test_conversation_boundaries import uses_of
from tests.architecture.test_essential_boundaries import asynchronous, purity_problems

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
MODULE = SRC / "core" / "secret_redaction.py"
BOOTSTRAP = SRC / "bootstrap.py"
MAY_NAME_IT = {MODULE, BOOTSTRAP, SRC / "core" / "__init__.py"}
ALLOWED_IMPORTS = {"harness_agent.core.redaction"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def keyword_calls(source: str, function: str, keyword: str) -> list[bool]:
    """For every call to ``function`` whether it passes ``keyword``."""
    found: list[bool] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name == function:
                found.append(any(k.arg == keyword for k in node.keywords))
    return found


def harness_imports(source: str) -> set[str]:
    return {m for m in imported_modules(source) if m.startswith("harness_agent")}


# --- the real files ---------------------------------------------------------------------------


def test_the_module_only_uses_the_standard_library_and_the_core() -> None:
    assert purity_problems(read(MODULE), MODULE.name) == []
    assert harness_imports(read(MODULE)) <= ALLOWED_IMPORTS


def test_the_module_is_synchronous_and_never_catches_the_cancellation() -> None:
    assert asynchronous(read(MODULE)) == []
    assert catches_cancellation(read(MODULE)) == []


def test_only_the_composition_root_builds_a_redactor() -> None:
    offenders = [
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if path not in MAY_NAME_IT and uses_of(read(path), ("SecretRedactor",))
    ]
    assert offenders == []


def test_compose_gives_the_redactor_to_the_three_write_points() -> None:
    source = read(BOOTSTRAP)
    assert keyword_calls(source, "ConversationCapture", "redact") == [True]
    assert keyword_calls(source, "attach_event_recorder", "redact") == [True]
    assert keyword_calls(source, "_compactor", "redact") == [True, True, True]


# --- the detectors catch a broken copy ---------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "import os; os.environ.get('HOME')",
        "import sqlite3",
        "from harness_agent.config import Secret",
        "from harness_agent.adapters.storage import SqliteSessionStore",
    ],
)
def test_an_import_that_breaks_the_purity_is_detected(line: str) -> None:
    broken = line + "\n" + read(MODULE)
    caught = purity_problems(broken, MODULE.name) or (harness_imports(broken) - ALLOWED_IMPORTS)
    assert caught


def test_asynchronous_code_is_detected() -> None:
    broken = mutate(read(MODULE), "def is_secret_name", "async def is_secret_name")
    assert asynchronous(broken)


def test_a_write_point_without_the_redactor_is_detected() -> None:
    broken = mutate(read(BOOTSTRAP), "redact=redactor.value", "skip_nothing=True")
    assert keyword_calls(broken, "attach_event_recorder", "redact") == [False]
    broken = mutate(read(BOOTSTRAP), "                redact=redactor,\n            )", ")")
    assert keyword_calls(broken, "ConversationCapture", "redact") == [False]


def test_another_module_building_a_redactor_is_detected() -> None:
    assert uses_of(
        "from harness_agent.core import SecretRedactor\nSecretRedactor()", ("SecretRedactor",)
    )
