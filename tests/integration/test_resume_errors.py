"""The errors of /reanudar and the mark «sin detalle» (HU-03-04 / T010d), on files and processes.

A past session is left in a database file in ``tmp_path``; compositions on the same file try to
resume it, and a child Python process does the same, which is what a new run of the program is.
Nothing reaches the network: the model is a local double or a ``FakeProvider``.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from harness_agent import bootstrap
from harness_agent.adapters.storage import SqliteMessageStore, SqliteSessionStore
from harness_agent.bootstrap import Composition
from harness_agent.core import (
    Event,
    Message,
    MessageRecord,
    ProviderResponse,
    Role,
    SessionDetailMissing,
    ToolCall,
    ToolResult,
    resume_session,
)
from tests.doubles import FakeProvider
from tests.integration.test_essential_context_agent_loop import make_task
from tests.integration.test_resume_agent_loop import database, process, rebuilt
from tests.unit.bootstrap_support import SENTINEL, build, make_config
from tests.unit.resume_support import MODEL, seed_session

ROOT = Path(__file__).resolve().parents[2]
FIXED = "No se pudo guardar un mensaje de la conversación; la sesión no podrá reanudarse."
NO_DETAIL = "Esa sesión se guardó sin el detalle de sus mensajes y no se puede reanudar."
INCOHERENT = "Los mensajes guardados de la sesión no son coherentes y no se puede reanudar."
TASK = "Las sesiones de tarea no se pueden reanudar todavía."
CALL = ToolCall("k1", "leer_archivo", {"path": "a.txt"})
PAST = [
    Message(Role.USER, "haz"),
    Message(Role.ASSISTANT, "", (CALL,)),
    Message(Role.TOOL, "ok", tool_result=ToolResult("k1", "ok")),
    Message(Role.ASSISTANT, "listo"),
]
CHILD = """
import asyncio, io, sys
from pathlib import Path
from harness_agent.bootstrap import compose, run_session
from harness_agent.core import ProviderResponse
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import make_config

tmp = Path(sys.argv[1])
config = make_config(tmp, workspace=tmp / "trabajo", model="openai/modelo-de-prueba")
provider = FakeProvider([ProviderResponse(content="respuesta del otro proceso")])
composition = compose(config, provider_factory=lambda _c: provider, system_name="Linux")
text = "".join(line + chr(10) for line in sys.argv[2:]) + "/salir" + chr(10)
out = io.StringIO()
code = asyncio.run(run_session(composition, input_stream=io.StringIO(text), output=out))
composition.close()
sys.stdout.write(out.getvalue())
sys.exit(code)
"""


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def other_process(tmp_path: Path, *lines: str) -> subprocess.CompletedProcess[str]:
    """A new run of the program on the same files: a child Python process."""
    (tmp_path / "trabajo").mkdir(exist_ok=True)
    environment = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    return subprocess.run(
        [sys.executable, "-c", CHILD, str(tmp_path), *lines],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env=environment,
        timeout=180,
        check=False,
    )


def counts(path: Path, session: str) -> tuple[int, int]:
    connection = sqlite3.connect(path)
    try:
        events = connection.execute(
            "SELECT count(*) FROM events WHERE session_id = ?", (session,)
        ).fetchone()[0]
        rows = connection.execute(
            "SELECT count(*) FROM mensajes WHERE sesion_id = ?", (session,)
        ).fetchone()[0]
        return int(events), int(rows)
    finally:
        connection.close()


# --- the identifier ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("argument", "line"),
    [
        ("", "Uso: /reanudar <identificador de la sesión>."),
        ("no-existe", "No existe una sesión con ese identificador."),
        ("../x", "El identificador de sesión no es válido."),
        ("a" * 129, "El identificador de sesión no es válido."),
        ("con espacio", "El identificador de sesión no es válido."),
        (f"{SENTINEL}/otra", "El identificador de sesión no es válido."),
        (SENTINEL, "No existe una sesión con ese identificador."),
    ],
)
async def test_a_bad_identifier_gets_its_fixed_line_without_echo_and_changes_nothing(
    tmp_path: Path, opened: list[Composition], argument: str, line: str
) -> None:
    seed_session(database(tmp_path), PAST)
    current = process(tmp_path, opened, prefix="b")
    before = counts(database(tmp_path), current.session_id)

    await current.run(f"/reanudar {argument}".rstrip(), "ahora")

    assert line in current.output and SENTINEL not in current.output
    assert counts(database(tmp_path), current.session_id)[1] > before[1]  # only its own request
    first_call = current.provider.received[0]
    assert [m.content for m in first_call if m.role is not Role.SYSTEM] == ["ahora"]


async def test_the_session_that_is_already_the_current_one_is_refused_without_writing(
    tmp_path: Path, opened: list[Composition]
) -> None:
    current = process(tmp_path, opened)
    before = counts(database(tmp_path), current.session_id)

    await current.run(f"/reanudar {current.session_id}")

    assert "Esa ya es la sesión actual." in current.output
    assert counts(database(tmp_path), current.session_id) == before


# --- a session with a task ----------------------------------------------------------------------


async def test_a_session_with_a_task_is_refused_also_when_its_essential_context_is_gone(
    tmp_path: Path, opened: list[Composition]
) -> None:
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    config = make_config(tmp_path, workspace=workspace, model=MODEL)
    with_task = build(
        opened,
        config,
        FakeProvider([ProviderResponse(content="listo")]),
        task=make_task(),
        system_name="Linux",
    )
    task_session = with_task.session_id
    current = process(tmp_path, opened, prefix="b")

    await current.run(f"/reanudar {task_session}")
    connection = sqlite3.connect(database(tmp_path))
    connection.execute("DELETE FROM contexto_esencial WHERE sesion_id = ?", (task_session,))
    connection.commit()
    connection.close()  # an orphan: criteria left, essential context lost
    await current.run(f"/reanudar {task_session}")

    assert current.output.count(TASK) == 2
    assert current.provider.received == []


# --- no detail, incoherent, empty --------------------------------------------------------------


async def test_a_session_from_before_this_story_has_events_and_no_messages_and_is_refused(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = seed_session(database(tmp_path), PAST)
    connection = sqlite3.connect(database(tmp_path))
    connection.execute("DELETE FROM mensajes WHERE sesion_id = ?", (past,))
    connection.commit()
    connection.close()
    current = process(tmp_path, opened, prefix="b")

    await current.run(f"/reanudar {past}")

    assert NO_DETAIL in current.output and current.provider.received == []


@pytest.mark.parametrize(
    "damage",
    [
        "UPDATE mensajes SET rol = 'assistant' WHERE posicion = 1",
        "UPDATE mensajes SET resultado_id = 'zzz' WHERE posicion = 3",
        "UPDATE mensajes SET llamadas = NULL WHERE posicion = 2",
    ],
    ids=["the request is not a request", "a result without its call", "a call that vanished"],
)
async def test_altered_rows_are_never_sent_to_the_model(
    tmp_path: Path, opened: list[Composition], damage: str
) -> None:
    past = seed_session(database(tmp_path), PAST)
    connection = sqlite3.connect(database(tmp_path))
    connection.execute(damage)
    connection.commit()
    connection.close()
    current = process(tmp_path, opened, prefix="b")

    await current.run(f"/reanudar {past}", "sigue")

    assert INCOHERENT in current.output
    assert [m.content for m in current.provider.received[0] if m.role is not Role.SYSTEM] == [
        "sigue"
    ]


async def test_a_session_with_no_messages_resumes_as_a_new_one(
    tmp_path: Path, opened: list[Composition]
) -> None:
    store = SqliteSessionStore(database(tmp_path))
    empty = store.create_session(model=MODEL).id
    store.close()
    current = process(tmp_path, opened, prefix="b")

    await current.run(f"/reanudar {empty}", "hola")

    assert "no tenía mensajes; se empieza de nuevo." in current.output
    assert counts(database(tmp_path), empty)[1] == 4  # the request, the tool and the answers


async def test_a_message_whose_event_was_never_stored_is_a_tail_and_the_session_resumes(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = seed_session(database(tmp_path), PAST, unsaved_events_from=3)
    current = process(tmp_path, opened, prefix="b")

    await current.run(f"/reanudar {past}", "sigue")

    assert "Sesión reanudada" in current.output and NO_DETAIL not in current.output
    assert len(current.provider.received) >= 1


async def test_an_event_of_a_message_whose_row_is_missing_fails_closed(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past = seed_session(database(tmp_path), PAST)
    connection = sqlite3.connect(database(tmp_path))
    connection.execute("DELETE FROM mensajes WHERE sesion_id = ? AND posicion = 4", (past,))
    connection.commit()
    connection.close()
    current = process(tmp_path, opened, prefix="b")

    await current.run(f"/reanudar {past}")

    assert NO_DETAIL in current.output


# --- the mark «sin detalle» cannot be skipped ----------------------------------------------------


class Switch:
    armed = False


def break_the_stores(monkeypatch: pytest.MonkeyPatch, *, events_too: bool) -> None:
    Switch.armed = False

    class FailingMessages(SqliteMessageStore):
        def append(self, session_id: str, records: Sequence[MessageRecord]) -> None:
            if Switch.armed:
                raise RuntimeError(SENTINEL)
            super().append(session_id, records)

    monkeypatch.setattr(bootstrap, "SqliteMessageStore", FailingMessages)
    if events_too:

        class FailingEvents(SqliteSessionStore):
            def save_event(self, event: Event) -> None:
                if Switch.armed:
                    raise RuntimeError(SENTINEL)
                super().save_event(event)

        monkeypatch.setattr(bootstrap, "SqliteSessionStore", FailingEvents)


async def test_a_message_that_could_not_be_saved_marks_the_session_for_every_reader(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    break_the_stores(monkeypatch, events_too=False)
    failed = process(tmp_path, opened)
    await failed.run("tarea 1")
    saved = counts(database(tmp_path), failed.session_id)

    Switch.armed = True
    code = await failed.run("tarea 2")
    Switch.armed = False

    assert code == 1 and failed.output.count(FIXED) == 1 and SENTINEL not in failed.output
    events, rows = counts(database(tmp_path), failed.session_id)
    assert rows == saved[1]  # not a message more was saved after the failure
    assert events > saved[0]  # but the recorder did store the event
    with pytest.raises(SessionDetailMissing):
        rebuilt(database(tmp_path), failed.session_id, failed.composition.history_prefix)
    child = other_process(tmp_path, f"/reanudar {failed.session_id}")
    assert child.returncode == 0, child.stderr
    assert NO_DETAIL in child.stdout and SENTINEL not in child.stdout + child.stderr


async def test_in_the_same_run_a_failed_session_is_refused_even_if_the_file_looks_whole(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    break_the_stores(monkeypatch, events_too=True)
    failed = process(tmp_path, opened)
    await failed.run("tarea 1")
    saved = counts(database(tmp_path), failed.session_id)
    Switch.armed = True
    assert await failed.run("tarea 2") == 1
    Switch.armed = False
    other = seed_session(database(tmp_path), PAST)

    await failed.run(f"/reanudar {other}", f"/reanudar {failed.session_id}")

    assert counts(database(tmp_path), failed.session_id) == saved  # the file is a clean prefix
    assert failed.output.count(NO_DETAIL) == 1  # and still, in this run, it is refused
    assert failed.composition.capture is not None
    assert failed.composition.capture.incomplete_sessions == frozenset({failed.session_id})
    # the documented limit: a new run sees only a valid prefix, like after any cut
    prefix = failed.composition.history_prefix
    assert rebuilt(database(tmp_path), failed.session_id, prefix).message_count > 0


# --- another process continues the same session ------------------------------------------------


async def test_a_session_resumed_by_another_process_continues_with_the_next_numbers(
    tmp_path: Path, opened: list[Composition]
) -> None:
    first = process(tmp_path, opened)
    await first.run("tarea 1", "tarea 2")
    path = database(tmp_path)
    first.composition.close()
    store = sqlite3.connect(path)
    before = store.execute(
        "SELECT id, session_id, seq, type, content, created_at FROM events "
        "WHERE session_id = ? ORDER BY seq",
        (first.session_id,),
    ).fetchall()
    positions = store.execute(
        "SELECT posicion FROM mensajes WHERE sesion_id = ?", (first.session_id,)
    ).fetchall()
    store.close()

    child = other_process(tmp_path, f"/reanudar {first.session_id}", "tarea 3")

    assert child.returncode == 0, child.stderr
    assert "Sesión reanudada: 8 mensajes." in child.stdout or "Sesión reanudada:" in child.stdout
    store = sqlite3.connect(path)
    after = store.execute(
        "SELECT id, session_id, seq, type, content, created_at FROM events "
        "WHERE session_id = ? ORDER BY seq",
        (first.session_id,),
    ).fetchall()
    rows = store.execute(
        "SELECT posicion FROM mensajes WHERE sesion_id = ? ORDER BY posicion",
        (first.session_id,),
    ).fetchall()
    store.close()
    assert after[: len(before)] == before  # nothing before was rewritten
    assert [row[2] for row in after] == list(range(1, len(after) + 1))
    assert len(after) > len(before) and len({row[0] for row in after}) == len(after)
    assert [p for (p,) in rows] == list(range(1, len(rows) + 1)) and len(rows) > len(positions)


def test_resuming_an_unknown_identifier_with_a_fresh_store_is_the_same_error(
    tmp_path: Path,
) -> None:
    store = SqliteSessionStore(database(tmp_path))
    try:
        with pytest.raises(Exception) as caught:
            resume_session(
                SqliteMessageStore(store),
                "no-existe",
                prefix=(),
                current_model=MODEL,
                current_session_id="otra",
            )
    finally:
        store.close()

    assert str(caught.value) == "No existe una sesión con ese identificador."
