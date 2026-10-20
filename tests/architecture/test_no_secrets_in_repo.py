"""AC-02: no secret in the versioned files (HU-00-04 / T018).

The check reads ``git ls-files`` and fails if a versioned file has the name of a secret file or a
content that looks like a key. The detector is tested with synthetic examples that are built at run
time by concatenation, so that this file does not contain a detectable literal itself. The history
of the repository is checked by hand (``specs/010-file-env-configuration/quickstart.md``, 4.2).
Without a git repository (or without git) the tests are skipped with the reason, unless ``CI`` is
defined: there they fail, so a pipeline can never skip the check without anybody noticing.
"""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import NoReturn

import pytest

ROOT = Path(__file__).resolve().parents[2]

KEY_PATTERNS: dict[str, re.Pattern[str]] = {
    "clave con prefijo sk": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "clave de acceso de AWS": re.compile(r"AKIA[0-9A-Z]{16}"),
    "clave de Google": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "token de GitHub": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    "token de Slack": re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),
    "clave privada": re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
    "asignación de clave": re.compile(
        r"(api[_-]?key|secret|token|password|passwd)[\"']?\s*[:=]\s*[^\s]{17,}",
        re.IGNORECASE,
    ),
}
SECRET_FILE_NAMES = (
    ".env",
    ".env.*",
    "config.toml",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
    "*.p12",
    "*.pfx",
)
ALLOWED_FILE_NAMES = {".env.example"}

# One synthetic example per pattern, built at run time (no literal of this file is detectable).
SYNTHETIC_EXAMPLES = {
    "clave con prefijo sk": "s" + "k-" + "a" * 24,
    "clave de acceso de AWS": "AK" + "IA" + "A" * 16,
    "clave de Google": "AI" + "za" + "a" * 35,
    "token de GitHub": "gh" + "p_" + "a" * 36,
    "token de Slack": "xo" + "xb-" + "1" * 12,
    "clave privada": "-----BEGIN " + "RSA PRIV" + "ATE KEY-----",
    "asignación de clave": "api_" + "key" + ' = "' + "a" * 20 + '"',
}
CLEAN_TEXT = (
    'model = "fake/test"\nmax_tokens = 200000\ntoken: str\nEl campo debe ser un texto no vacío.\n'
)


def secret_patterns_in(text: str) -> list[str]:
    """The names of the key patterns found in ``text`` (never the matched values)."""
    return [label for label, pattern in KEY_PATTERNS.items() if pattern.search(text)]


def is_secret_file_name(path: str) -> bool:
    name = PurePosixPath(path.replace("\\", "/")).name.lower()
    if name in ALLOWED_FILE_NAMES:
        return False
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in SECRET_FILE_NAMES)


def unavailable(reason: str) -> NoReturn:
    """Skip with the reason, or fail if the check runs in a pipeline (``CI`` defined)."""
    if os.environ.get("CI"):
        pytest.fail(f"AC-02 no se puede comprobar en la CI: {reason}.")
    pytest.skip(f"AC-02 no se puede comprobar: {reason}.")


def git(*args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)
    except FileNotFoundError:
        unavailable("git no está instalado")


def versioned_files() -> list[str]:
    result = git("ls-files", "-z")
    if result.returncode != 0:
        unavailable("la carpeta del proyecto no es un repositorio git")
    names = result.stdout.decode("utf-8", errors="surrogateescape").split("\0")
    return [name for name in names if name]


def is_ignored(path: str) -> bool:
    result = git("check-ignore", "-q", "--", path)
    if result.returncode not in (0, 1):
        unavailable("git check-ignore no se pudo ejecutar")
    return result.returncode == 0


class TestAutopruebaDelDetector:
    @pytest.mark.parametrize("label", sorted(SYNTHETIC_EXAMPLES))
    def test_each_pattern_detects_its_synthetic_example(self, label: str) -> None:
        assert label in secret_patterns_in(f"valor = {SYNTHETIC_EXAMPLES[label]}\n")

    def test_a_clean_text_gives_no_match(self) -> None:
        assert secret_patterns_in(CLEAN_TEXT) == []

    def test_there_is_one_example_for_every_pattern(self) -> None:
        assert set(SYNTHETIC_EXAMPLES) == set(KEY_PATTERNS)

    @pytest.mark.parametrize(
        "path",
        [".env", ".env.local", "config.toml", "sub/.env", "claves.pem", "server.key", "id_rsa"],
    )
    def test_the_names_of_secret_files_are_detected(self, path: str) -> None:
        assert is_secret_file_name(path)

    @pytest.mark.parametrize(
        "path", [".env.example", "config.example.toml", "src/harness_agent/config.py", "README.md"]
    )
    def test_the_names_of_the_templates_and_of_the_code_are_not_detected(self, path: str) -> None:
        assert not is_secret_file_name(path)


class TestArchivosVersionados:
    def test_no_versioned_file_has_a_secret_name(self) -> None:
        names = versioned_files()

        found = [name for name in names if is_secret_file_name(name)]

        assert found == [], f"Archivos versionados con nombre de secreto: {found}"

    def test_no_versioned_file_has_content_that_looks_like_a_key(self) -> None:
        names = versioned_files()
        assert names, "git ls-files no devolvió ningún archivo"

        found: list[str] = []
        for name in names:
            path = ROOT / name
            if not path.is_file():
                continue
            try:
                text = path.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                continue
            found.extend(f"{name}: {label}" for label in secret_patterns_in(text))

        assert found == [], "Archivos versionados con forma de clave:\n" + "\n".join(found)


class TestGitignore:
    @pytest.mark.parametrize("path", [".env", ".env.local", "config.toml", ".harness/x"])
    def test_the_real_files_and_the_local_data_are_ignored(self, path: str) -> None:
        assert is_ignored(path)

    @pytest.mark.parametrize("path", [".env.example", "config.example.toml"])
    def test_the_templates_are_not_ignored(self, path: str) -> None:
        assert not is_ignored(path)
