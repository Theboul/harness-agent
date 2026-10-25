"""Composition root (propuesta HU-00-08 / T004, T005, T007): the session and the command.

``run_session`` runs the terminal cycle over a composition; ``main`` loads the configuration,
composes, runs and translates the startup failures. Input and output are in-memory streams, the
provider is an injected ``FakeProvider`` and the database is a temporary file.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.adapters.providers.litellm_provider import ProviderDependencyError
from harness_agent.adapters.storage import SessionStoreError, SqliteSessionStore
from harness_agent.bootstrap import (
    EXIT_INTERRUPTED,
    EXIT_STARTUP,
    NO_AREA_NOTICE,
    TEST_ONLY_PROVIDER_MESSAGE,
    Composition,
    main,
    run_session,
)
from harness_agent.config import HarnessConfig
from harness_agent.core import (
    Event,
    EventType,
    PermissionRules,
    Provider,
    ProviderResponse,
    Role,
    ToolCall,
)
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import SENTINEL, build, make_config, scripted
from tests.unit.config_support import SECRET_FIELD, toml_with_field

EXIT_TEXT = "Sesión terminada."


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


async def session(composition: Composition, text: str) -> tuple[int, str]:
    output = io.StringIO()
    code = await run_session(composition, input_stream=io.StringIO(text), output=output)
    return code, output.getvalue()


class TestRunSession:
    async def test_the_notices_come_before_the_first_prompt(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=None))

        code, text = await session(composition, "/salir\n")

        assert code == 0
        assert text.startswith(NO_AREA_NOTICE + "\n")
        assert text.index("tarea> ") > len(NO_AREA_NOTICE)

    async def test_a_notice_that_the_stream_cannot_encode_is_written_with_replacements(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=None))
        raw = io.BytesIO()
        output = io.TextIOWrapper(raw, encoding="ascii", errors="strict")

        code = await run_session(composition, input_stream=io.StringIO("/salir\n"), output=output)
        output.flush()

        assert code == 0
        assert raw.getvalue().startswith(b"Aviso: no hay ")

    async def test_the_history_continues_between_the_lines_of_one_session(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider = scripted("respuesta uno", "respuesta dos")
        composition = build(opened, make_config(tmp_path, workspace=tmp_path), provider)

        code, _text = await session(composition, "primera tarea\nsegunda tarea\n/salir\n")

        assert code == 0
        assert provider.call_count == 2
        second_call = [m.content for m in provider.received[1]]
        assert second_call == ["primera tarea", "respuesta uno", "segunda tarea"]

    async def test_slash_exit_and_the_end_of_the_input_return_zero(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path))

        code_exit, text_exit = await session(composition, "/salir\n")
        code_end, _text_end = await session(composition, "")

        assert code_exit == 0
        assert EXIT_TEXT in text_exit
        assert code_end == 0

    async def test_a_turn_that_raises_an_ordinary_exception_returns_one(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path))

        def failing_subscriber(_event: Event) -> None:
            raise RuntimeError("fallo de prueba")

        composition.bus.subscribe(EventType.USER_MESSAGE, failing_subscriber)

        code, text = await session(composition, "una tarea\n/salir\n")

        assert code == 1
        assert "EventDeliveryError" in text
        assert "fallo de prueba" not in text

    async def test_an_action_that_asks_for_approval_is_denied_with_a_reason(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider = FakeProvider(
            [
                ProviderResponse(
                    tool_calls=[ToolCall(id="c1", name="leer_archivo", arguments={"path": "a.txt"})]
                ),
                ProviderResponse(content="listo"),
            ]
        )
        config = make_config(
            tmp_path, workspace=tmp_path, permissions=PermissionRules(ask=("leer_archivo",))
        )
        composition = build(opened, config, provider)

        code, _text = await session(composition, "lee a.txt\n/salir\n")

        assert code == 0
        answered = [m for m in provider.received[1] if m.role is Role.TOOL]
        assert answered[0].content.startswith("[approval_required_unavailable]")

    async def test_an_input_closed_before_the_first_task_saves_no_events(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path))

        code, _text = await session(composition, "")

        assert code == 0
        assert composition.store.load_session(composition.session_id) == []


def write_toml(tmp_path: Path, workspace: Path | None = None) -> Path:
    lines = ['model = "openai/modelo-de-prueba"', "", "[paths]"]
    lines.append(f'sessions_db = "{(tmp_path / "datos" / "sesiones.db").as_posix()}"')
    if workspace is not None:
        lines.append(f'workspace_root = "{workspace.as_posix()}"')
    target = tmp_path / "config.toml"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return target


class TestMainHappyPath:
    def run(
        self, tmp_path: Path, text: str, provider: Provider | None = None, **kwargs: Any
    ) -> tuple[int, str, str]:
        output, error = io.StringIO(), io.StringIO()
        chosen = provider if provider is not None else scripted("listo")
        code = main(
            environ=kwargs.pop("environ", {"OPENAI_API_KEY": SENTINEL}),
            config_path=write_toml(tmp_path, workspace=tmp_path),
            input_stream=io.StringIO(text),
            output=output,
            error=error,
            provider_factory=lambda _config: chosen,
            **kwargs,
        )
        return code, output.getvalue(), error.getvalue()

    def test_a_valid_configuration_and_slash_exit_return_zero(self, tmp_path: Path) -> None:
        code, text, error = self.run(tmp_path, "/salir\n")

        assert code == 0
        assert EXIT_TEXT in text
        assert error == ""

    def test_the_session_and_its_events_are_saved(self, tmp_path: Path) -> None:
        code, _text, _error = self.run(tmp_path, "una tarea\n/salir\n")

        assert code == 0
        with SqliteSessionStore(tmp_path / "datos" / "sesiones.db") as store:
            sessions = store.list_sessions()
            assert len(sessions) == 1
            assert store.load_session(sessions[0].id) != []

    def test_the_store_is_closed_when_the_command_ends(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stores: list[SqliteSessionStore] = []

        class RecordingStore(SqliteSessionStore):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                stores.append(self)

        monkeypatch.setattr(bootstrap, "SqliteSessionStore", RecordingStore)

        self.run(tmp_path, "/salir\n")

        assert len(stores) == 1
        with pytest.raises(SessionStoreError):
            stores[0].get_session("lo-que-sea")

    def test_the_key_comes_from_the_injected_environment_not_from_the_real_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        received: list[HarnessConfig] = []

        def factory(config: HarnessConfig) -> Provider:
            received.append(config)
            return scripted("listo")

        code = main(
            environ={"OPENAI_API_KEY": SENTINEL},
            config_path=write_toml(tmp_path, workspace=tmp_path),
            input_stream=io.StringIO("/salir\n"),
            output=io.StringIO(),
            provider_factory=factory,
        )

        assert code == 0
        assert received[0].key_variable == "OPENAI_API_KEY"
        assert received[0].api_key is not None
        assert received[0].api_key.reveal() == SENTINEL


PREFIX = "No se pudo iniciar: "


class Startup:
    """Run ``main`` to a startup failure and keep what it wrote."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.output = io.StringIO()
        self.error = io.StringIO()

    def write_config(self, text: str) -> Path:
        path = self.tmp_path / "config.toml"
        path.write_text(text, encoding="utf-8", newline="")
        return path

    def go(
        self,
        *,
        toml: str | None = None,
        environ: dict[str, str] | None = None,
        factory: Any = None,
        config_path: Path | None = None,
    ) -> int:
        if config_path is None:
            config_path = self.tmp_path / "config.toml"
            text = toml if toml is not None else 'model = "openai/modelo-de-prueba"\n'
            config_path.write_text(text, encoding="utf-8", newline="")
        return main(
            environ={"OPENAI_API_KEY": SENTINEL} if environ is None else environ,
            config_path=config_path,
            input_stream=io.StringIO("una tarea\n/salir\n"),
            output=self.output,
            error=self.error,
            provider_factory=factory if factory is not None else (lambda _c: scripted("x")),
        )

    def assert_clean_failure(self) -> str:
        message = self.error.getvalue()
        assert message.startswith(PREFIX)
        assert message.endswith("\n") and message.count("\n") == 1
        assert "Traceback" not in message
        assert self.output.getvalue() == ""
        assert SENTINEL not in message
        return message


class TestMainStartupFailures:
    def test_a_missing_configuration_file_stops_before_any_prompt(self, tmp_path: Path) -> None:
        startup = Startup(tmp_path)

        code = startup.go(config_path=tmp_path / "no-existe.toml")

        assert code == EXIT_STARTUP == 2
        assert "config" in startup.assert_clean_failure().lower()

    def test_an_invalid_field_is_reported_in_one_line(self, tmp_path: Path) -> None:
        startup = Startup(tmp_path)

        code = startup.go(toml='model = "openai/x"\n[limits]\nmax_turns = 0\n')

        assert code == EXIT_STARTUP
        assert "max_turns" in startup.assert_clean_failure()

    def test_a_key_written_in_the_file_is_rejected_without_showing_its_value(
        self, tmp_path: Path
    ) -> None:
        startup = Startup(tmp_path)

        code = startup.go(toml='model = "openai/x"\n' + toml_with_field(SECRET_FIELD))

        assert code == EXIT_STARTUP
        startup.assert_clean_failure()

    def test_a_missing_key_names_the_variable_never_a_value(self, tmp_path: Path) -> None:
        startup = Startup(tmp_path)

        code = startup.go(environ={})

        assert code == EXIT_STARTUP
        assert "OPENAI_API_KEY" in startup.assert_clean_failure()

    def test_a_missing_provider_dependency_shows_the_install_command_on_one_line(
        self, tmp_path: Path
    ) -> None:
        def factory(_config: HarnessConfig) -> Provider:
            raise ProviderDependencyError('Falta la dependencia.\nInstálela con: pip install "x"')

        startup = Startup(tmp_path)

        code = startup.go(factory=factory)

        assert code == EXIT_STARTUP
        assert "Falta la dependencia. Instálela con: pip install" in startup.assert_clean_failure()

    def test_a_database_that_is_not_a_database_is_reported_and_left_untouched(
        self, tmp_path: Path
    ) -> None:
        database = tmp_path / "sesiones.db"
        database.write_bytes(b"esto no es una base de datos de SQLite")
        toml = f'model = "openai/x"\n[paths]\nsessions_db = "{database.as_posix()}"\n'
        startup = Startup(tmp_path)

        code = startup.go(toml=toml)

        assert code == EXIT_STARTUP
        startup.assert_clean_failure()
        assert database.read_bytes() == b"esto no es una base de datos de SQLite"

    def test_the_simulated_provider_is_refused_with_a_clear_line(self, tmp_path: Path) -> None:
        startup = Startup(tmp_path)

        code = main(
            environ={},
            config_path=startup.write_config('model = "fake/test"\n'),
            input_stream=io.StringIO("/salir\n"),
            output=startup.output,
            error=startup.error,
        )

        assert code == EXIT_STARTUP
        assert startup.assert_clean_failure() == PREFIX + TEST_ONLY_PROVIDER_MESSAGE + "\n"

    def test_an_unexpected_error_is_reduced_to_its_type(self, tmp_path: Path) -> None:
        def factory(_config: HarnessConfig) -> Provider:
            raise RuntimeError(SENTINEL)

        startup = Startup(tmp_path)

        code = startup.go(factory=factory)

        assert code == EXIT_STARTUP
        assert startup.assert_clean_failure() == PREFIX + "error inesperado (RuntimeError).\n"

    def test_the_default_error_stream_is_standard_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main(
            environ={},
            config_path=tmp_path / "no-existe.toml",
            input_stream=io.StringIO(""),
            output=io.StringIO(),
        )

        assert code == EXIT_STARTUP
        assert capsys.readouterr().err.startswith(PREFIX)


class TestMainInterruption:
    def test_an_interruption_while_starting_returns_130_without_a_trace(
        self, tmp_path: Path
    ) -> None:
        def factory(_config: HarnessConfig) -> Provider:
            raise KeyboardInterrupt

        startup = Startup(tmp_path)

        code = startup.go(factory=factory)

        assert code == EXIT_INTERRUPTED == 130
        assert startup.error.getvalue() == ""

    def test_an_interruption_during_a_turn_returns_130_and_closes_the_store(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stores: list[SqliteSessionStore] = []

        class RecordingStore(SqliteSessionStore):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                stores.append(self)

        class Interrupted(Provider):
            async def complete(self, messages: Any, tools: Any = None) -> ProviderResponse:
                raise KeyboardInterrupt

        monkeypatch.setattr(bootstrap, "SqliteSessionStore", RecordingStore)
        startup = Startup(tmp_path)

        code = startup.go(factory=lambda _config: Interrupted())

        assert code == EXIT_INTERRUPTED
        assert startup.error.getvalue() == ""
        with pytest.raises(SessionStoreError):
            stores[0].get_session("lo-que-sea")

    def test_the_four_exit_codes_are_different(self) -> None:
        assert len({0, 1, EXIT_STARTUP, EXIT_INTERRUPTED}) == 4
