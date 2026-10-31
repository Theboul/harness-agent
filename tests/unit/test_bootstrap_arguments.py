"""Command line and ``.env`` of ``main`` (proposed HU-00-08.1).

``parse_arguments`` is pure; ``main`` is driven with an injected ``argv``, environment, streams,
provider and ``gh`` runner: no network, key, console or real ``gh``.
"""

from __future__ import annotations

import io
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from harness_agent.bootstrap import (
    EXIT_STARTUP,
    StartupArguments,
    StartupError,
    entry,
    main,
    parse_arguments,
)
from harness_agent.config import HarnessConfig
from tests.unit.bootstrap_support import SENTINEL, scripted
from tests.unit.test_bootstrap_main import write_toml

TASK_TEXT = (
    "# TAREA-41\n## Objetivo\nValidar el correo\n"
    "## Criterios de aceptación\n- El mensaje de error es claro\n"
)
FAILURE = "No se pudo iniciar: "


class TestParseArguments:
    def test_no_arguments_start_a_plain_session(self) -> None:
        assert parse_arguments([]) == StartupArguments()

    def test_task_file_in_both_spellings(self) -> None:
        assert parse_arguments(["--tarea", "t.md"]).task_file == "t.md"
        assert parse_arguments(["--tarea=t.md"]).task_file == "t.md"

    def test_issue_number_and_url(self) -> None:
        by_number = parse_arguments(["--issue", "12"])
        by_url = parse_arguments(["--issue=https://github.com/dueno/repo-1/issues/34/"])

        assert (by_number.issue_number, by_number.issue_repo) == (12, None)
        assert (by_url.issue_number, by_url.issue_repo) == (34, "dueno/repo-1")

    @pytest.mark.parametrize(
        "argv",
        [
            [f"--raro-{SENTINEL}"],
            ["--tarea"],
            ["--tarea="],
            ["--issue", "no-es-numero"],
            ["--issue", "0"],
            ["--issue", "https://example.com/a/b/issues/3"],
            ["--issue", "http://github.com/a/b/issues/3"],
            ["--tarea", "t.md", "--issue", "3"],
            ["--tarea", "a.md", "--tarea", "b.md"],
            [f"suelto-{SENTINEL}"],
        ],
    )
    def test_invalid_arguments_fail_without_repeating_them(self, argv: Sequence[str]) -> None:
        with pytest.raises(StartupError) as raised:
            parse_arguments(argv)

        assert SENTINEL not in str(raised.value) and "\n" not in str(raised.value)


class Harness:
    """Runs ``main`` over a temporary folder with in-memory streams."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.output = io.StringIO()
        self.error = io.StringIO()
        self.configs: list[HarnessConfig] = []

    def run(
        self,
        text: str = "/salir\n",
        *,
        argv: Sequence[str] | None = None,
        environ: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> int:
        def factory(config: HarnessConfig) -> Any:
            self.configs.append(config)
            return scripted("listo")

        return main(
            argv=argv,
            environ={"OPENAI_API_KEY": SENTINEL} if environ is None else environ,
            config_path=write_toml(self.tmp_path, workspace=self.tmp_path),
            input_stream=io.StringIO(text),
            output=self.output,
            error=self.error,
            provider_factory=factory,
            **kwargs,
        )

    def write_task(self, text: str = TASK_TEXT) -> str:
        target = self.tmp_path / "tarea.md"
        target.write_text(text, encoding="utf-8", newline="")
        return str(target)


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


class TestTaskFromTheCommand:
    def test_without_arguments_nothing_changes(self, harness: Harness) -> None:
        assert harness.run("/criterios\n/salir\n", argv=[]) == 0
        assert "Todavía no se ha verificado" not in harness.output.getvalue()
        assert list(harness.tmp_path.rglob("criterios.json")) == []

    def test_a_valid_task_file_starts_the_session_with_its_criteria(self, harness: Harness) -> None:
        code = harness.run("/criterios\n/salir\n", argv=["--tarea", harness.write_task()])

        assert code == 0 and harness.error.getvalue() == ""
        assert "Todavía no se ha verificado" in harness.output.getvalue()  # /criterios exists
        assert len(list(harness.tmp_path.rglob("criterios.json"))) == 1

    @pytest.mark.parametrize("kind", ["missing", "invalid", "not-utf8"])
    def test_a_bad_task_file_is_a_one_line_startup_failure(
        self, harness: Harness, tmp_path: Path, kind: str
    ) -> None:
        target = tmp_path / "tarea.md"
        if kind == "invalid":
            target.write_text(f"{SENTINEL} sin formato", encoding="utf-8")
        elif kind == "not-utf8":
            target.write_bytes(b"\xff\xfe" + SENTINEL.encode())

        code = harness.run(argv=["--tarea", str(target)])

        shown = harness.error.getvalue()
        assert code == EXIT_STARTUP
        assert shown.startswith(FAILURE) and shown.count("\n") == 1
        assert SENTINEL not in shown and str(tmp_path) not in shown
        assert harness.output.getvalue() == ""

    def test_a_bad_argument_is_a_startup_failure(self, harness: Harness) -> None:
        code = harness.run(argv=["--tarea"])

        assert code == EXIT_STARTUP and harness.error.getvalue().startswith(FAILURE)

    def test_an_issue_is_read_with_the_injected_gh(self, harness: Harness) -> None:
        calls: list[Sequence[str]] = []

        def runner(args: Sequence[str]) -> str:
            calls.append(args)
            return json.dumps({"title": "TAREA-7", "body": TASK_TEXT.split("\n", 1)[1]})

        code = harness.run("/criterios\n/salir\n", argv=["--issue", "7"], gh_runner=runner)

        assert code == 0
        assert calls == [["issue", "view", "7", "--json", "title,body"]]
        assert len(list(harness.tmp_path.rglob("criterios.json"))) == 1

    def test_an_issue_url_passes_the_repository_to_gh(self, harness: Harness) -> None:
        calls: list[Sequence[str]] = []

        def runner(args: Sequence[str]) -> str:
            calls.append(args)
            return json.dumps({"title": "T-8", "body": TASK_TEXT.split("\n", 1)[1]})

        url = "https://github.com/dueno/repo/issues/8"
        assert harness.run(argv=["--issue", url], gh_runner=runner) == 0
        assert calls[0][-2:] == ["--repo", "dueno/repo"]

    def test_gh_that_is_not_installed_fails_clearly_and_runs_nothing_else(
        self, harness: Harness, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempts: list[list[str]] = []

        def missing(command: list[str], **_kwargs: Any) -> Any:
            attempts.append(command)
            raise FileNotFoundError(SENTINEL)

        monkeypatch.setattr(subprocess, "run", missing)

        code = harness.run(argv=["--issue", "7"])

        shown = harness.error.getvalue()
        assert code == EXIT_STARTUP and "gh" in shown and SENTINEL not in shown
        assert attempts == [["gh", "issue", "view", "7", "--json", "title,body"]]

    def test_a_gh_answer_that_is_not_a_task_fails_without_reproducing_it(
        self, harness: Harness
    ) -> None:
        def runner(_args: Sequence[str]) -> str:
            return json.dumps({"title": "T", "body": f"{SENTINEL} sin formato"})

        code = harness.run(argv=["--issue", "7"], gh_runner=runner)

        assert code == EXIT_STARTUP and SENTINEL not in harness.error.getvalue()


class TestDotenv:
    def test_the_key_comes_from_the_dotenv_next_to_the_config(
        self, harness: Harness, tmp_path: Path
    ) -> None:
        (tmp_path / ".env").write_text(f"OPENAI_API_KEY={SENTINEL}\n", encoding="utf-8")

        code = harness.run(environ={})

        assert code == 0 and harness.error.getvalue() == ""
        assert harness.configs[0].api_key is not None
        assert harness.configs[0].api_key.reveal() == SENTINEL
        assert SENTINEL not in harness.output.getvalue()

    def test_the_real_environment_wins_over_the_dotenv(
        self, harness: Harness, tmp_path: Path
    ) -> None:
        (tmp_path / ".env").write_text("OPENAI_API_KEY=del-archivo\n", encoding="utf-8")

        assert harness.run(environ={"OPENAI_API_KEY": "real"}) == 0
        assert harness.configs[0].api_key is not None
        assert harness.configs[0].api_key.reveal() == "real"

    def test_without_a_dotenv_nothing_is_said(self, harness: Harness) -> None:
        assert harness.run() == 0 and harness.error.getvalue() == ""

    def test_odd_lines_give_a_fixed_warning_and_the_valid_ones_apply(
        self, harness: Harness, tmp_path: Path
    ) -> None:
        (tmp_path / ".env").write_text(
            f"OPENAI_API_KEY={SENTINEL}\nraro {SENTINEL}\n", encoding="utf-8"
        )

        code = harness.run(environ={})

        warning = harness.error.getvalue()
        assert code == 0 and warning.startswith("Aviso: ") and ".env" in warning
        assert SENTINEL not in warning and SENTINEL not in harness.output.getvalue()

    def test_an_unreadable_dotenv_does_not_stop_the_start(
        self, harness: Harness, tmp_path: Path
    ) -> None:
        (tmp_path / ".env").write_bytes(b"\xff\xfe" + SENTINEL.encode())

        code = harness.run(environ={"OPENAI_API_KEY": "real"})

        assert code == 0 and harness.error.getvalue().startswith("Aviso: ")
        assert SENTINEL not in harness.error.getvalue()

    def test_a_missing_key_still_stops_the_start_without_leaking_values(
        self, harness: Harness, tmp_path: Path
    ) -> None:
        (tmp_path / ".env").write_text(f"GROQ_API_KEY={SENTINEL}\n", encoding="utf-8")

        code = harness.run(environ={})

        assert code == EXIT_STARTUP and SENTINEL not in harness.error.getvalue()

    def test_the_process_environment_is_not_modified(
        self, harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        (tmp_path / ".env").write_text(f"OPENAI_API_KEY={SENTINEL}\n", encoding="utf-8")

        assert harness.run(environ={}) == 0

        import os

        assert "OPENAI_API_KEY" not in os.environ

    def test_the_dotenv_is_looked_up_next_to_harness_config(
        self, harness: Harness, tmp_path: Path
    ) -> None:
        elsewhere = tmp_path / "otra"
        elsewhere.mkdir()
        (elsewhere / ".env").write_text(f"OPENAI_API_KEY={SENTINEL}\n", encoding="utf-8")
        config = write_toml(tmp_path, workspace=tmp_path)
        moved = elsewhere / "config.toml"
        moved.write_text(config.read_text(encoding="utf-8"), encoding="utf-8")

        code = main(
            environ={"HARNESS_CONFIG": str(moved)},
            input_stream=io.StringIO("/salir\n"),
            output=harness.output,
            error=harness.error,
            provider_factory=lambda _config: scripted("x"),
        )

        assert code == 0 and harness.error.getvalue() == ""


def test_entry_passes_the_command_line_to_main(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    from harness_agent import bootstrap

    seen: list[Sequence[str] | None] = []

    def fake_main(*, argv: Sequence[str] | None = None) -> int:
        seen.append(argv)
        return 0

    monkeypatch.setattr(bootstrap, "main", fake_main)
    monkeypatch.setattr(sys, "argv", ["harness", "--tarea", "t.md"])

    assert entry() == 0 and seen == [["--tarea", "t.md"]]
