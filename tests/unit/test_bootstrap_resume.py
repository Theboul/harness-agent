"""run_session() offers /reanudar and switches the session (HU-03-04 / T009b).

A session is first lived and closed; a second composition on the same database resumes it. The
provider is a ``FakeProvider`` and records what it receives.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from harness_agent.adapters.storage import SessionStoreError
from harness_agent.bootstrap import Composition, run_session
from harness_agent.config import HarnessConfig
from harness_agent.core import (
    ContextCompactor,
    Message,
    ProviderResponse,
    Role,
    StoredConversation,
)
from tests.doubles import FakeProvider
from tests.integration.test_essential_context_agent_loop import make_task
from tests.unit.bootstrap_support import SENTINEL, build, make_config

MODEL = "openai/modelo-de-prueba"
NOT_AVAILABLE = "Reanudar no está disponible en esta sesión."
READ_FAILED = "No se pudo leer la sesión; la sesión actual sigue sin cambios."


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def config_for(tmp_path: Path, **limits: int) -> HarnessConfig:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(exist_ok=True)
    config = make_config(tmp_path, workspace=workspace, model=MODEL)
    return replace(config, limits=replace(config.limits, **limits)) if limits else config


def make(
    tmp_path: Path, opened: list[Composition], *texts: str, **limits: int
) -> tuple[Composition, FakeProvider]:
    provider = FakeProvider([ProviderResponse(content=text) for text in texts or ("hecho",)])
    composition = build(opened, config_for(tmp_path, **limits), provider, system_name="Linux")
    return composition, provider


async def drive(composition: Composition, *lines: str) -> tuple[int, str]:
    output = io.StringIO()
    code = await run_session(
        composition,
        input_stream=io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir"))),
        output=output,
    )
    return code, output.getvalue()


async def live(tmp_path: Path, opened: list[Composition]) -> str:
    """A past session with two exchanges; returns its identifier."""
    past, _ = make(tmp_path, opened, "uno", "dos")
    await drive(past, "primera", "segunda")
    past.close()
    return str(past.session_id)


def dump(composition: Composition) -> dict[str, list[tuple[object, ...]]]:
    connection = composition.store.connection()
    names = [
        n
        for (n,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return {n: connection.execute(f"SELECT * FROM {n} ORDER BY 1, 2").fetchall() for n in names}


def contents(messages: list[Message]) -> list[str]:
    return [m.content for m in messages if m.role is not Role.SYSTEM]


async def test_the_command_is_in_the_help_of_a_session_without_a_task(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition, _ = make(tmp_path, opened)

    _, shown = await drive(composition, "/ayuda")

    assert "  /reanudar  Reanuda una sesión guardada por su identificador." in shown


async def test_a_session_with_a_task_answers_that_it_is_not_available_and_changes_nothing(
    tmp_path: Path, opened: list[Composition]
) -> None:
    provider = FakeProvider([ProviderResponse(content="listo")])
    composition = build(
        opened, config_for(tmp_path), provider, task=make_task(), system_name="Linux"
    )
    before = dump(composition)

    _, shown = await drive(composition, "/reanudar cualquiera")

    assert NOT_AVAILABLE in shown and composition.essential is not None
    assert dump(composition) == before


@pytest.mark.parametrize(
    ("argument", "line"),
    [
        ("", "Uso: /reanudar <identificador de la sesión>."),
        ("../x", "El identificador de sesión no es válido."),
        ("no-existe", "No existe una sesión con ese identificador."),
    ],
)
async def test_an_error_gives_its_fixed_line_and_the_current_session_is_untouched(
    tmp_path: Path, opened: list[Composition], argument: str, line: str
) -> None:
    await live(tmp_path, opened)
    current, provider = make(tmp_path, opened, "hecho")
    before = dump(current)

    _, shown = await drive(current, f"/reanudar {argument}".rstrip(), "ahora")

    assert line in shown and shown.count(line) == 1
    assert contents(provider.received[0]) == ["ahora"]  # the history is exactly the new request
    assert current.capture is not None and current.capture.session_id == current.session_id
    after = dump(current)
    for table in ("sessions", "criterios", "resumenes", "contexto_esencial"):
        assert after[table] == before[table]


async def test_a_task_session_and_a_session_with_a_missing_detail_are_refused(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = await live(tmp_path, opened)
    current, provider = make(tmp_path, opened, "hecho")
    connection = current.store.connection()
    connection.execute(
        "INSERT INTO sessions (id, created_at, status) VALUES ('de-tarea', 't', 'active')"
    )
    connection.execute(
        "INSERT INTO criterios (sesion_id, orden, descripcion, tipo) "
        "VALUES ('de-tarea', 1, 'x', 'semantico')"
    )
    connection.execute("DELETE FROM mensajes WHERE sesion_id = ? AND posicion = 2", (past,))
    connection.commit()

    _, shown = await drive(current, "/reanudar de-tarea", f"/reanudar {past}")

    assert "Las sesiones de tarea no se pueden reanudar todavía." in shown
    assert "Esa sesión se guardó sin el detalle de sus mensajes y no se puede reanudar." in shown
    assert provider.received == []


async def test_resuming_replaces_the_history_and_the_next_request_carries_it(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = await live(tmp_path, opened)
    current, provider = make(tmp_path, opened, "tercera respuesta")

    _, shown = await drive(current, f"/reanudar {past}", "tercera")

    assert "Sesión reanudada: 4 mensajes." in shown
    assert contents(provider.received[0]) == ["primera", "uno", "segunda", "dos", "tercera"]
    assert provider.received[0][0].role is Role.SYSTEM  # the prefix of the composition


async def test_resuming_writes_nothing_and_publishes_nothing(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = await live(tmp_path, opened)
    current, _ = make(tmp_path, opened)
    before = dump(current)

    _, shown = await drive(current, f"/reanudar {past}")

    assert dump(current) == before
    lines = [line for line in shown.splitlines() if "reanudada" in line]
    assert len(lines) == 1 and "primera" not in shown and "uno" not in shown


async def test_the_new_events_go_to_the_resumed_session_and_the_numbers_continue(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = await live(tmp_path, opened)
    current, _ = make(tmp_path, opened, "tercera respuesta")
    last = (
        current.store.connection()
        .execute("SELECT max(seq) FROM events WHERE session_id = ?", (past,))
        .fetchone()[0]
    )

    await drive(current, f"/reanudar {past}", "tercera")

    seqs = [
        s
        for (s,) in current.store.connection().execute(
            "SELECT seq FROM events WHERE session_id = ? ORDER BY seq", (past,)
        )
    ]
    assert seqs == list(range(1, len(seqs) + 1)) and len(seqs) > last
    own = (
        current.store.connection()
        .execute("SELECT count(*) FROM events WHERE session_id = ?", (current.session_id,))
        .fetchone()[0]
    )
    assert own == 0  # nothing was written to the session that was abandoned
    rows = (
        current.store.connection()
        .execute("SELECT posicion FROM mensajes WHERE sesion_id = ? ORDER BY posicion", (past,))
        .fetchall()
    )
    assert [p for (p,) in rows] == [1, 2, 3, 4, 5, 6]


async def test_the_compactor_of_the_resumed_session_comes_from_the_factory(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = await live(tmp_path, opened)
    current, _ = make(tmp_path, opened, "hecho")
    asked: list[str] = []
    original = current.compactor_for
    assert original is not None

    def factory(session_id: str) -> ContextCompactor:
        asked.append(session_id)
        return original(session_id)

    await drive(replace(current, compactor_for=factory), f"/reanudar {past}", "otra")

    assert asked == [past]


async def test_resuming_the_current_session_is_refused_and_going_back_and_forth_works(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = await live(tmp_path, opened)
    other = await live(tmp_path, opened)
    current, _ = make(tmp_path, opened)
    before = dump(current)

    _, shown = await drive(
        current,
        f"/reanudar {current.session_id}",
        f"/reanudar {past}",
        f"/reanudar {past}",
        f"/reanudar {other}",
        f"/reanudar {past}",
    )

    lines = shown.splitlines()
    assert sum(line.endswith("Esa ya es la sesión actual.") for line in lines) == 2
    assert sum("Sesión reanudada:" in line for line in lines) == 3
    assert dump(current) == before


async def test_the_limits_of_the_run_are_not_reset_by_resuming(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = await live(tmp_path, opened)
    current, provider = make(tmp_path, opened, "uno", "dos", "tres", max_turns=2)

    await drive(current, "a", f"/reanudar {past}", "b", "c")

    assert len(provider.received) == 2  # the third request found the budget spent


async def test_a_source_that_fails_gives_the_read_line_and_changes_nothing(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = await live(tmp_path, opened)
    current, provider = make(tmp_path, opened, "hecho")

    class Broken:
        def __init__(self, real: object) -> None:
            self.real = real

        def last_position(self, session_id: str) -> int:
            return int(self.real.last_position(session_id))  # type: ignore[attr-defined]

        def load_conversation(self, session_id: str) -> StoredConversation | None:
            raise SessionStoreError(SENTINEL)

    broken = replace(current, messages=Broken(current.messages))  # type: ignore[arg-type]
    _, shown = await drive(broken, f"/reanudar {past}", "x")

    assert READ_FAILED in shown and SENTINEL not in shown
    assert contents(provider.received[0]) == ["x"]


async def test_an_unexpected_failure_while_reading_is_also_the_read_line(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = await live(tmp_path, opened)
    current, _ = make(tmp_path, opened)

    class Broken:
        def last_position(self, session_id: str) -> int:
            return 0

        def load_conversation(self, session_id: str) -> StoredConversation | None:
            raise RuntimeError(SENTINEL)

    _, shown = await drive(replace(current, messages=Broken()), f"/reanudar {past}")  # type: ignore[arg-type]

    assert READ_FAILED in shown and SENTINEL not in shown
