"""Architecture guard of the failover between models (HU-07-05).

``core/failover.py`` holds the rule (which errors switch, what a turn has tried). Rules:

* it imports only the standard library and ``harness_agent.core``: never ``adapters``, ``cli``,
  ``config``, ``bootstrap``, ``observability`` or ``core.loop``; no SDK, no stdlib I/O;
* it reads no configuration or environment, uses no terminal and knows no event (the composition
  root publishes ``PROVIDER_SWITCHED``).

``adapters/providers/failover_provider.py`` (and the new error of ``errors.py``):

* imports only the standard library, the public API of the core and its own package: no
  ``config``, ``cli``, ``bootstrap`` or other adapter;
* knows nothing of events (the observer is a plain callable) and never blocks the loop;
* never swallows a cancellation: the only handlers are ``Exception`` and ``ModelSwitchError``
  (``CancelledError`` is a ``BaseException``); no bare ``except:`` and no ``BaseException``;
* names no provider and no key variable in a literal (they come from the configuration);
* nothing but the composition root builds it, and the exports of the packages name it.

Each rule has a self-test on synthetic fragments and a mutation test on a copy of the real module.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pytest

from tests.architecture.test_core_no_terminal import terminal_uses
from tests.architecture.test_core_reads_no_config import find_config_reads
from tests.architecture.test_core_tools_stdlib_only import find_import_violations
from tests.architecture.test_limits_boundaries import event_uses, io_stdlib_imports
from tests.architecture.test_loop_boundaries import forbidden_imports
from tests.architecture.test_model_switch_boundaries import literal_matches
from tests.architecture.test_retry_boundaries import (
    blocking_imports,
    event_imports,
    foreign_imports,
)
from tests.architecture.test_review_boundaries import names_any

SRC = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
RULE = SRC / "core" / "failover.py"
CORE_PACKAGE = "harness_agent.core"
FORBIDDEN_LAYERS = {"adapters", "cli", "config", "bootstrap", "observability"}
FORBIDDEN_CORE_MODULES = {"harness_agent.core.loop"}
WRAPPER = SRC / "adapters" / "providers" / "failover_provider.py"
ERRORS = SRC / "adapters" / "providers" / "errors.py"
BOOTSTRAP = SRC / "bootstrap.py"
ALLOWED_HANDLERS = {"ModelSwitchError", "Exception"}
PROVIDER_NAMES = {"openai", "anthropic", "gemini", "groq", "ollama", "openrouter", "fake"}
NAMES = {"FailoverProvider", "Switched", "Switchable"}
EXPORTS = {SRC / "core" / "__init__.py"}


def layer_imports(source: str) -> list[str]:
    """Imports of the outer layers or of the loop: the rule must not depend on any of them."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level:
            # A relative import in ``core`` could only reach the core itself.
            modules = [node.module or ""]
        else:
            continue
        for module in modules:
            parts = module.split(".")
            if parts[0] == "harness_agent" and len(parts) > 1 and parts[1] in FORBIDDEN_LAYERS:
                found.append(f"{module} at line {node.lineno}")
            elif module in FORBIDDEN_CORE_MODULES:
                found.append(f"{module} at line {node.lineno}")
    return found


def scan_rule(source: str, name: str = "failover.py") -> list[str]:
    violations = layer_imports(source)
    violations.extend(forbidden_imports(source))
    violations.extend(find_import_violations(source, name))
    violations.extend(io_stdlib_imports(source))
    violations.extend(find_config_reads(source, name, CORE_PACKAGE))
    violations.extend(terminal_uses(source))
    violations.extend(event_uses(source))
    return violations


def risky_handlers(source: str) -> list[str]:
    """Handlers that could swallow a cancellation or that catch something not on the list."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ExceptHandler):
            continue
        if node.type is None:
            found.append(f"bare except at line {node.lineno}")
        elif not (isinstance(node.type, ast.Name) and node.type.id in ALLOWED_HANDLERS):
            found.append(f"except {ast.dump(node.type)} at line {node.lineno}")
    return found


def scan_wrapper(source: str) -> list[str]:
    violations = foreign_imports(source)
    violations.extend(event_imports(source))
    violations.extend(blocking_imports(source))
    violations.extend(terminal_uses(source))
    violations.extend(
        find_config_reads(source, "failover_provider.py", "harness_agent.adapters.providers")
    )
    violations.extend(literal_matches(source, PROVIDER_NAMES))
    violations.extend(risky_handlers(source))
    return violations


# --- the real code --------------------------------------------------------------------------


def test_the_rule_exists() -> None:
    assert RULE.is_file()


def test_the_rule_is_pure_domain_logic() -> None:
    assert scan_rule(RULE.read_text(encoding="utf-8")) == []


def test_the_core_imports_no_adapter_and_no_cli_anywhere_for_this_feature() -> None:
    """The whole ``core`` stays free of the outer layers (the rule of this story included)."""
    offenders = [
        f"{path.relative_to(SRC).as_posix()}: {found}"
        for path in sorted((SRC / "core").rglob("*.py"))
        for found in layer_imports(path.read_text(encoding="utf-8"))
        if found.split(" at line")[0].split(".")[1] in {"adapters", "cli"}
    ]
    assert offenders == []


def test_the_rule_is_exported_by_the_core() -> None:
    init = (SRC / "core" / "__init__.py").read_text(encoding="utf-8")
    for name in ("ELIGIBLE_ERRORS", "FailoverTurn", "is_failover_eligible"):
        assert f'"{name}"' in init, name


def test_the_wrapper_exists() -> None:
    assert WRAPPER.is_file()


def test_the_wrapper_follows_the_rules() -> None:
    assert scan_wrapper(WRAPPER.read_text(encoding="utf-8")) == []


def test_the_new_error_follows_the_rules_of_the_adapter() -> None:
    source = ERRORS.read_text(encoding="utf-8")
    assert foreign_imports(source) == []
    assert risky_handlers(source) == []


def test_only_the_composition_root_builds_the_wrapper() -> None:
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if path in {BOOTSTRAP, WRAPPER} or path in EXPORTS:
            continue
        if names_any(path.read_text(encoding="utf-8"), NAMES):
            offenders.append(path.relative_to(SRC).as_posix())
    assert offenders == []


# --- the detectors detect -------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "from harness_agent.adapters.providers import errors\n",
        "import harness_agent.adapters.providers.errors\n",
        "from harness_agent.cli import render\n",
        "from harness_agent.config import load_config\n",
        "from harness_agent.bootstrap import compose\n",
        "from harness_agent.core.loop import AgentLoop\n",
        "import sqlite3\n",
        "import os\n",
        "import litellm\n",
        "import os\nos.environ['X']\n",
        "print('hola')\n",
        "from harness_agent.core.events import EventType\nx = EventType.PROVIDER_SWITCHED\n",
    ],
    ids=[
        "adapters",
        "adapters-plain",
        "cli",
        "config",
        "bootstrap",
        "loop",
        "sqlite",
        "os",
        "sdk",
        "environ",
        "terminal",
        "event",
    ],
)
def test_the_rule_scan_flags_violations(source: str) -> None:
    assert scan_rule(source) != []


def test_the_rule_scan_accepts_the_allowed_imports() -> None:
    source = (
        "from __future__ import annotations\n"
        "from collections.abc import Iterable\n"
        "from harness_agent.core.interfaces.provider import QuotaExceeded\n"
    )
    assert scan_rule(source) == []


@pytest.mark.parametrize(
    "addition",
    [
        "\nfrom harness_agent.adapters.providers.errors import RateLimited\n",
        "\nfrom harness_agent.cli import render\n",
        "\nimport sqlite3\n",
        "\nprint('hola')\n",
    ],
    ids=["adapters", "cli", "sqlite", "terminal"],
)
def test_the_rule_fails_on_a_mutation_of_the_real_module(tmp_path: Path, addition: str) -> None:
    copy = tmp_path / RULE.name
    shutil.copyfile(RULE, copy)
    copy.write_text(copy.read_text(encoding="utf-8") + addition, encoding="utf-8")

    assert scan_rule(copy.read_text(encoding="utf-8")) != []


@pytest.mark.parametrize(
    "source",
    [
        "from harness_agent.config import Secret\n",
        "from harness_agent.cli import render\n",
        "from harness_agent.bootstrap import compose\n",
        "import time\n",
        "from threading import Lock\n",
        "from harness_agent.core import EventType\n",
        "from harness_agent.core import Event\n",
        "print('hola')\n",
        "x = 'groq'\n",
        "x = 'gemini'\n",
        "try:\n    pass\nexcept BaseException:\n    pass\n",
        "try:\n    pass\nexcept:\n    pass\n",
        "try:\n    pass\nexcept (Exception, asyncio.CancelledError):\n    pass\n",
        "try:\n    pass\nexcept ValueError:\n    pass\n",
    ],
    ids=[
        "config",
        "cli",
        "bootstrap",
        "time",
        "threading",
        "event-type",
        "event",
        "terminal",
        "provider-groq",
        "provider-gemini",
        "base-exception",
        "bare",
        "cancelled-in-tuple",
        "value-error",
    ],
)
def test_the_wrapper_rules_flag_violations(source: str) -> None:
    assert scan_wrapper(source) != []


def test_the_wrapper_scan_accepts_the_allowed_handlers() -> None:
    assert risky_handlers("try:\n    pass\nexcept Exception:\n    pass\n") == []
    assert risky_handlers("try:\n    pass\nexcept ModelSwitchError:\n    pass\n") == []


def test_the_builder_detector_flags_a_use_of_the_wrapper() -> None:
    assert names_any("from x import FailoverProvider\n", NAMES)
    assert names_any("y = Switched('a', 'b', 'c')\n", NAMES)
    assert not names_any("from x import RetryingProvider\n", NAMES)


@pytest.mark.parametrize(
    "addition",
    [
        "\nimport time\n",
        "\nfrom harness_agent.config import Secret\n",
        "\nfrom harness_agent.core import EventType\n",
        "\nPROVIDER = 'groq'\n",
        "\ntry:\n    pass\nexcept BaseException:\n    pass\n",
    ],
    ids=["blocking", "config", "events", "provider-name", "cancellation"],
)
def test_the_wrapper_fails_on_a_mutation_of_the_real_module(tmp_path: Path, addition: str) -> None:
    copy = tmp_path / WRAPPER.name
    shutil.copyfile(WRAPPER, copy)
    copy.write_text(copy.read_text(encoding="utf-8") + addition, encoding="utf-8")

    assert scan_wrapper(copy.read_text(encoding="utf-8")) != []
