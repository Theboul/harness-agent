"""Clean-install check (HU-00-07 / AC-02): the package installs and starts in a fresh environment.

These tests create a temporary virtual environment, install the checkout into it with
``--no-deps`` and run the installed entry points. pip needs the network once, to fetch the
build backend, so the tests carry the ``install`` marker and are excluded from the normal run
(``addopts`` has ``-m "not install"``). Run them with::

    pytest -m install --no-cov tests/install

The environment lives under a short path (``HARNESS_INSTALL_ROOT`` or the system temporary
folder) because Windows limits paths to 260 characters.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.install

ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_SECONDS = 600
STARTUP_FAILURE = "No se pudo iniciar"
COLD_IMPORT_SNIPPET = (
    "import sys, harness_agent, harness_agent.bootstrap;"
    "loaded = [n for n in ('litellm', 'mcp', 'openai', 'anthropic') if n in sys.modules];"
    "print(','.join(loaded)); sys.exit(1 if loaded else 0)"
)


def run(
    command: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
        check=False,
    )


def clean_environment(venv: Path) -> dict[str, str]:
    """The environment of the installed program: no configuration, no keys, no inherited paths."""
    keep = ("SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "TMPDIR", "PATHEXT", "COMSPEC")
    env = {name: os.environ[name] for name in keep if name in os.environ}
    scripts = venv / ("Scripts" if os.name == "nt" else "bin")
    env["PATH"] = str(scripts)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


@pytest.fixture(scope="module")
def venv() -> Iterator[Path]:
    base = os.environ.get("HARNESS_INSTALL_ROOT")
    root = Path(tempfile.mkdtemp(prefix="hi", dir=base))
    environment = root / "v"
    try:
        created = run([sys.executable, "-m", "venv", str(environment)], cwd=root)
        assert created.returncode == 0, created.stderr
        interpreter = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        installed = run(
            [str(interpreter), "-m", "pip", "install", "--no-deps", str(ROOT)],
            cwd=root,
            env=clean_environment(environment),
        )
        assert installed.returncode == 0, installed.stderr[-2000:]
        yield environment
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def empty_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "empty"
    folder.mkdir()
    return folder


def python_of(venv: Path) -> str:
    return str(venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))


def command_of(venv: Path) -> str:
    return str(venv / ("Scripts/harness.exe" if os.name == "nt" else "bin/harness"))


def assert_clean_startup_failure(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 2
    assert STARTUP_FAILURE in result.stderr
    assert "Traceback" not in result.stderr
    assert "Traceback" not in result.stdout


def test_harness_command_fails_closed_without_configuration(venv: Path, empty_folder: Path) -> None:
    result = run([command_of(venv)], cwd=empty_folder, env=clean_environment(venv))
    assert_clean_startup_failure(result)


def test_module_entry_fails_closed_without_configuration(venv: Path, empty_folder: Path) -> None:
    result = run(
        [python_of(venv), "-m", "harness_agent"], cwd=empty_folder, env=clean_environment(venv)
    )
    assert_clean_startup_failure(result)


def test_import_does_not_load_optional_dependencies(venv: Path, empty_folder: Path) -> None:
    result = run(
        [python_of(venv), "-c", COLD_IMPORT_SNIPPET],
        cwd=empty_folder,
        env=clean_environment(venv),
    )
    assert result.returncode == 0, f"optional modules loaded: {result.stdout.strip()}"


def test_installed_package_is_the_installed_copy(venv: Path, empty_folder: Path) -> None:
    result = run(
        [python_of(venv), "-c", "import harness_agent; print(harness_agent.__file__)"],
        cwd=empty_folder,
        env=clean_environment(venv),
    )
    assert result.returncode == 0, result.stderr
    assert "site-packages" in result.stdout
