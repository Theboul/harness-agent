"""The console commands of HU-06-05 through ``run_session`` (T010 to T012).

Real SQLite in a temporary folder, a ``FakeProvider`` and in-memory streams: no network, key or
console.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from harness_agent import bootstrap
from harness_agent.adapters.storage import SessionStoreError, SqliteSessionStore
from harness_agent.bootstrap import Composition, run_session
from harness_agent.config import HarnessConfig, Limits, Secret
from harness_agent.core import Message, ProviderResponse, ProviderUnavailable, Role
from tests.doubles import FakeProvider
from tests.integration.test_essential_context_agent_loop import (
    S_CRITERION,
    S_OBJECTIVE,
    S_RULES,
    S_TICKET,
    NoShell,
    Recorder,
    blocks_of,
    make_task,
    model_calls,
    tasks,
)
from tests.unit.bootstrap_support import SENTINEL, build, make_config

MODEL = "openai/modelo-de-prueba"
LIST_FAILED = "No se pudo leer la lista de sesiones."


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def config_for(tmp_path: Path, **options: object) -> HarnessConfig:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(exist_ok=True)
    return make_config(tmp_path, workspace=workspace, model=MODEL, **options)  # type: ignore[arg-type]


def make(
    tmp_path: Path, opened: list[Composition], *texts: str, config: HarnessConfig | None = None
) -> tuple[Composition, FakeProvider]:
    provider = FakeProvider([ProviderResponse(content=text) for text in texts or ("hecho",)])
    chosen = config if config is not None else config_for(tmp_path)
    return build(opened, chosen, provider, system_name="Linux"), provider


async def drive(composition: Composition, *lines: str) -> str:
    output = io.StringIO()
    await run_session(
        composition,
        input_stream=io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir"))),
        output=output,
    )
    return output.getvalue()


class TestHelp:
    async def test_the_new_commands_are_listed_in_the_help(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, _ = make(tmp_path, opened)

        shown = await drive(composition, "/ayuda")

        assert "  /sesiones  Lista las sesiones guardadas." in shown
        assert "  /model  Muestra el modelo y los límites." in shown


class TestSessionsCommand:
    async def test_it_lists_the_saved_sessions_newest_first_and_marks_the_current(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        past, _ = make(tmp_path, opened, "uno")
        await drive(past, "algo que hacer")
        past.close()
        current, _ = make(tmp_path, opened)

        shown = await drive(current, "/sesiones")

        lines = [line for line in shown.splitlines() if "UTC" in line]
        assert len(lines) == 2
        assert lines[0].startswith(f"* {current.session_id}")
        assert lines[1].startswith(f"  {past.session_id}")
        assert "algo que hacer" not in shown or "algo que hacer" in lines[1]
        assert "Para continuar una: /reanudar <id>." in shown

    async def test_the_sessions_of_subagents_are_not_listed(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, _ = make(tmp_path, opened)
        child = composition.store.create_session(model=MODEL, parent_id=composition.session_id).id

        shown = await drive(composition, "/sesiones")

        assert child not in shown
        assert composition.session_id in shown

    async def test_a_store_that_fails_gives_one_fixed_line(
        self, tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        composition, _ = make(tmp_path, opened)

        def broken(_store: object) -> list[object]:
            raise SessionStoreError(f"falla {SENTINEL}")

        monkeypatch.setattr(SqliteSessionStore, "list_sessions", broken)

        shown = await drive(composition, "/sesiones")

        assert f"tarea> {LIST_FAILED}" in shown.splitlines()
        assert "Traceback" not in shown
        assert SENTINEL not in shown

    async def test_it_writes_nothing_in_the_store(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, _ = make(tmp_path, opened)
        count = "SELECT count(*) FROM sessions"
        before = composition.store.connection().execute(count).fetchone()[0]

        await drive(composition, "/sesiones", "/sesiones")

        assert composition.store.connection().execute(count).fetchone()[0] == before


class TestModelCommand:
    async def test_it_shows_the_model_and_the_limits(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        config = config_for(tmp_path)
        config = replace(config, limits=replace(config.limits, max_turns=7))
        composition, _ = make(tmp_path, opened, config=config)

        shown = await drive(composition, "/model")

        assert f"Modelo: {MODEL}" in shown
        assert "Límites de la sesión: 7 turnos," in shown
        assert "Máximo por respuesta del modelo: 777 tokens" in shown

    async def test_it_never_shows_the_key(self, tmp_path: Path, opened: list[Composition]) -> None:
        key = Secret(SENTINEL)
        config = replace(config_for(tmp_path), api_key=key)
        composition, _ = make(tmp_path, opened, config=config)

        shown = await drive(composition, "/model", "/sesiones", "/ayuda")

        assert SENTINEL not in shown

    async def test_a_composition_without_the_view_says_so(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, _ = make(tmp_path, opened)

        shown = await drive(replace(composition, model_view=None), "/model")

        assert "tarea> Modelo no disponible en esta ejecución." in shown.splitlines()


NEW_NOT_AVAILABLE = "Nueva sesión no está disponible en esta ejecución."
NEW_FAILED = "No se pudo crear la sesión nueva; la sesión actual sigue sin cambios."


def texts(messages: list[Message]) -> list[str]:
    return [m.content for m in messages if m.role is not Role.SYSTEM]


def count(composition: Composition, sql: str, *params: object) -> int:
    row = composition.store.connection().execute(sql, params).fetchone()
    return int(row[0])


class TestNewCommand:
    async def test_it_is_listed_in_the_help(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, _ = make(tmp_path, opened)

        shown = await drive(composition, "/ayuda")

        assert "  /nueva  Empieza una sesión nueva." in shown

    async def test_the_next_task_starts_with_a_clean_history_in_another_session(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, provider = make(tmp_path, opened, "uno", "dos")

        shown = await drive(composition, "primera", "/nueva", "segunda")

        new_id = next(line for line in shown.splitlines() if "Sesión nueva: " in line)
        new_id = new_id.split("Sesión nueva: ")[1].split(".")[0]
        assert new_id != composition.session_id
        assert texts(provider.received[0]) == ["primera"]
        assert texts(provider.received[1]) == ["segunda"]
        assert provider.received[1][0].role is Role.SYSTEM  # the prefix is kept
        saved = "SELECT count(*) FROM mensajes WHERE sesion_id = ?"
        assert count(composition, saved, new_id) == 2  # the request and the answer
        assert count(composition, saved, composition.session_id) == 2
        events = "SELECT count(*) FROM events WHERE session_id = ?"
        assert count(composition, events, new_id) > 0

    async def test_nothing_is_written_to_the_new_session_until_the_first_task(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, _ = make(tmp_path, opened)
        before = count(composition, "SELECT count(*) FROM sessions")

        await drive(composition, "/nueva")

        assert count(composition, "SELECT count(*) FROM sessions") == before + 1
        assert count(composition, "SELECT count(*) FROM mensajes") == 0

    async def test_the_previous_session_can_be_resumed_afterwards(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, provider = make(tmp_path, opened, "uno", "dos")
        old = composition.session_id

        await drive(composition, "primera", "/nueva", f"/reanudar {old}", "tercera")

        assert texts(provider.received[-1]) == ["primera", "uno", "tercera"]

    async def test_the_session_model_is_the_one_of_the_run(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, _ = make(tmp_path, opened)

        await drive(composition, "/nueva")

        models = composition.store.connection().execute("SELECT model FROM sessions").fetchall()
        assert {model for (model,) in models} == {MODEL}

    async def test_with_a_task_it_is_refused_and_nothing_changes(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider = FakeProvider([ProviderResponse(content="listo")])
        composition = build(
            opened, config_for(tmp_path), provider, task=make_task(), system_name="Linux"
        )
        before = count(composition, "SELECT count(*) FROM sessions")

        shown = await drive(composition, "/nueva")

        assert f"tarea> {NEW_NOT_AVAILABLE}" in shown.splitlines()
        assert count(composition, "SELECT count(*) FROM sessions") == before

    async def test_without_the_message_capture_it_is_not_available(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, _ = make(tmp_path, opened)

        shown = await drive(replace(composition, capture=None), "/nueva")

        assert f"tarea> {NEW_NOT_AVAILABLE}" in shown.splitlines()

    async def test_a_store_that_fails_leaves_the_current_session_as_it_was(
        self, tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        composition, provider = make(tmp_path, opened, "uno", "dos")

        def broken(_store: object, **_options: object) -> object:
            raise SessionStoreError(f"falla {SENTINEL}")

        monkeypatch.setattr(SqliteSessionStore, "create_session", broken)
        shown = await drive(composition, "primera", "/nueva", "segunda")

        assert f"tarea> {NEW_FAILED}" in shown.splitlines()
        assert SENTINEL not in shown
        assert texts(provider.received[1]) == ["primera", "uno", "segunda"]


LONG = "palabra " * 150
COMPACTED = re.compile(
    r"Contexto compactado: ~([\d.]+) → ~([\d.]+) tokens \(historial original conservado\)\."
)
NOT_COMPACTED = "tarea> No se compactó: no hay mensajes antiguos que resumir (o el resumen falló)."


def tokens(text: str) -> int:
    return int(text.replace(".", ""))


async def long_session(composition: Composition, *lines: str) -> str:
    return await drive(composition, *(f"{line} {LONG}" for line in ("a", "b", "c", "d")), *lines)


class TestCompactCommand:
    async def test_it_is_listed_in_the_help(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, _ = make(tmp_path, opened)

        shown = await drive(composition, "/ayuda")

        assert "  /compactar  Compacta el contexto ahora." in shown

    async def test_without_a_manual_compactor_it_is_not_available(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, _ = make(tmp_path, opened)

        shown = await drive(replace(composition, manual_compactor_for=None), "/compactar")

        assert "tarea> Compactar no está disponible en esta ejecución." in shown.splitlines()

    async def test_it_compacts_below_the_automatic_threshold_and_reports_the_estimates(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, provider = make(
            tmp_path, opened, "r1", "r2", "r3", "r4", "RESUMEN-VIEJO", "r5"
        )

        shown = await long_session(composition, "/compactar", f"e {LONG}")

        found = COMPACTED.search(shown)
        assert found is not None
        assert tokens(found.group(1)) > tokens(found.group(2))
        assert count(composition, "SELECT count(*) FROM resumenes") == 1
        # the history is kept: nothing is deleted, the covered events are only marked
        marked = "SELECT count(*) FROM events WHERE compacted_by IS NOT NULL"
        assert count(composition, marked) > 0
        # the next request carries the summary and no longer the oldest answers
        last = texts(provider.received[-1])
        assert any("RESUMEN-VIEJO" in text for text in last)
        assert "r1" not in last
        assert last[-1] == f"e {LONG}"

    async def test_the_automatic_threshold_is_not_changed_by_the_command(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, _ = make(tmp_path, opened, "r1", "r2", "r3", "r4", "RESUMEN", "r5", "r6")

        await long_session(composition, "/compactar", f"e {LONG}", f"f {LONG}")

        assert count(composition, "SELECT count(*) FROM resumenes") == 1

    async def test_with_nothing_to_summarize_it_says_so_and_does_not_call_the_model(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition, provider = make(tmp_path, opened)

        shown = await drive(composition, "/compactar")

        assert NOT_COMPACTED in shown.splitlines()
        assert provider.received == []
        assert count(composition, "SELECT count(*) FROM resumenes") == 0

    async def test_a_provider_failure_leaves_no_partial_state(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider = FakeProvider(
            [
                *(ProviderResponse(content=text) for text in ("r1", "r2", "r3", "r4")),
                ProviderUnavailable(f"caído {SENTINEL}"),
                ProviderResponse(content="r5"),
            ]
        )
        composition = build(opened, config_for(tmp_path), provider, system_name="Linux")

        shown = await long_session(composition, "/compactar", "e")

        # the failure is reported by the compactor on its own line, before the answer
        assert NOT_COMPACTED.removeprefix("tarea> ") in shown.splitlines()
        assert SENTINEL not in shown
        assert count(composition, "SELECT count(*) FROM resumenes") == 0
        assert count(composition, "SELECT count(*) FROM events WHERE compacted_by IS NOT NULL") == 0
        assert [t for t in texts(provider.received[-1]) if t.startswith("r")] == [
            "r1",
            "r2",
            "r3",
            "r4",
        ]

    async def test_with_an_active_task_the_essential_block_survives_the_compaction(
        self, tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: NoShell())
        workspace = tmp_path / "trabajo"
        workspace.mkdir()
        (workspace / "a.txt").write_text("contenido", encoding="utf-8")
        config = replace(
            make_config(tmp_path, workspace=workspace, model=MODEL),
            limits=Limits(max_turns=2_000, max_output_tokens=777),
        )
        provider = Recorder()
        composition = build(opened, config, provider, task=make_task(), system_name="Linux")
        output = io.StringIO()

        lines = (*tasks(5), "/compactar", *tasks(1), "/salir")
        await bootstrap.run_session(
            composition,
            input_stream=io.StringIO("".join(f"{line}\n" for line in lines)),
            output=output,
        )

        assert COMPACTED.search(output.getvalue()) is not None
        assert len(provider.summaries) == 1
        for messages in model_calls(provider)[-1:]:
            found = blocks_of(messages)
            assert len(found) == 1
            for sentinel in (S_TICKET, S_OBJECTIVE, S_RULES, S_CRITERION):
                assert sentinel in found[0].content
