"""AC-01 and AC-02 of HU-03-04 with the real loop and the real SQLite file (T010).

``compose()`` builds the system, ``run_session`` drives it and the database is a file in
``tmp_path``. The model is a local double that answers from what it receives: a request becomes a
tool call (the odd ones with no text) and a tool result becomes a padded answer, so the context
grows and the compaction happens when the threshold says so; a summary request gets a summary.
Nothing reaches the network.
"""

from __future__ import annotations

import io
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.storage import SqliteMessageStore, SqliteSessionStore
from harness_agent.bootstrap import Composition, run_session
from harness_agent.config import Limits
from harness_agent.core import (
    ContextSettings,
    EventType,
    Message,
    ProviderResponse,
    Role,
    ToolCall,
    ToolDefinition,
    check_structure,
    is_summary,
    resume_session,
)
from harness_agent.core.interfaces import Provider
from tests.integration.test_context_compaction_agent_loop import PAD, SUMMARY_START
from tests.unit.bootstrap_support import build, make_config

MODEL = "openai/modelo-de-prueba"
OTHER_MODEL = "openai/otro-modelo"
ABOVE = "Aviso: el contexto sigue por encima del umbral"


def settings() -> ContextSettings:
    return ContextSettings(
        window_tokens=3_000,
        threshold_percent=50,
        recent_percent=5,
        min_recent_messages=4,
        summary_tokens=100,
    )


class Smart(Provider):
    """Answers from the context it receives; records every request."""

    def __init__(self, prefix: str = "a") -> None:
        self.prefix = prefix
        self.received: list[list[Message]] = []
        self.summaries = 0
        self.requests = 0

    async def complete(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None
    ) -> ProviderResponse:
        self.received.append(list(messages))
        first = messages[0]
        if first.role is Role.SYSTEM and first.content.startswith(SUMMARY_START):
            self.summaries += 1
            return ProviderResponse(content=f"Resumen {self.prefix}{self.summaries} de lo hecho.")
        if messages[-1].role is Role.TOOL:
            return ProviderResponse(content=f"respuesta {self.requests} {PAD}")
        self.requests += 1
        text = "" if self.requests % 2 else f"reviso {self.requests} {PAD}"
        call = ToolCall(f"{self.prefix}{self.requests}", "listar_archivos", {"path": "."})
        return ProviderResponse(content=text, tool_calls=[call])

    def summary_calls(self) -> list[int]:
        return [
            index
            for index, messages in enumerate(self.received)
            if messages[0].role is Role.SYSTEM and messages[0].content.startswith(SUMMARY_START)
        ]


class SpyLoop:
    """Hands the real loop through and keeps the history list the session works on."""

    def __init__(self, real: Any) -> None:
        self.real = real
        self.history: list[Message] = []

    async def run_turn(self, **options: Any) -> Any:
        self.history = options["history"]
        return await self.real.run_turn(**options)


@dataclass
class Lived:
    """One process: its composition, its model, what it printed and the history at the exit."""

    composition: Composition
    provider: Smart
    spy: SpyLoop
    output: str = ""

    @property
    def session_id(self) -> str:
        return self.composition.session_id

    async def run(self, *lines: str) -> int:
        out = io.StringIO()
        code = await run_session(
            replace(self.composition, loop=self.spy),  # type: ignore[arg-type]
            input_stream=io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir"))),
            output=out,
        )
        self.output += out.getvalue()
        return code


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def process(
    tmp_path: Path,
    opened: list[Composition],
    *,
    prefix: str = "a",
    model: str = MODEL,
    context: ContextSettings | None = None,
    provider: Smart | None = None,
) -> Lived:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "a.txt").write_text("contenido", encoding="utf-8")
    config = replace(
        make_config(tmp_path, workspace=workspace, model=model),
        limits=Limits(max_turns=500, max_output_tokens=777),
        context=context if context is not None else settings(),
    )
    chosen = provider if provider is not None else Smart(prefix)
    composition = build(opened, config, chosen, system_name="Linux")
    return Lived(composition, chosen, SpyLoop(composition.loop))


async def live(
    lived: Lived, lines: int, *, resume: str | None = None, summaries: int | None = None
) -> None:
    """One session of the terminal with ``lines`` requests (after resuming ``resume``)."""
    commands = [] if resume is None else [f"/reanudar {resume}"]
    assert await lived.run(*commands, *[f"tarea {n}" for n in range(1, lines + 1)]) == 0
    if summaries is not None:
        assert lived.provider.summaries == summaries


LINES = {0: 3, 1: 9, 2: 15}  # measured: the threshold is passed before the 9th and the 15th


def events_of(path: Path, session: str) -> list[tuple[Any, ...]]:
    store = SqliteSessionStore(path)
    try:
        cursor = store.connection().execute(
            "SELECT id, session_id, seq, type, content, created_at, compacted_by "
            "FROM events WHERE session_id = ? ORDER BY seq",
            (session,),
        )
        return cursor.fetchall()
    finally:
        store.close()


def database(tmp_path: Path) -> Path:
    return tmp_path / "datos" / "sesiones.db"


def rebuilt(path: Path, session: str, prefix: Sequence[Message], model: str = MODEL) -> Any:
    """What a new process rebuilds: a fresh connection to the file."""
    store = SqliteSessionStore(path)
    try:
        return resume_session(
            SqliteMessageStore(store),
            session,
            prefix=prefix,
            current_model=model,
            current_session_id="otra",
        )
    finally:
        store.close()


# --- AC-01: what is rebuilt is what the process had ----------------------------------------------


@pytest.mark.parametrize("compactions", [0, 1, 2])
async def test_ac01_the_rebuilt_history_is_the_one_in_memory_before_exit_message_by_message(
    tmp_path: Path, opened: list[Composition], compactions: int
) -> None:
    lived = process(tmp_path, opened)
    await live(lived, LINES[compactions], summaries=compactions)
    in_memory = list(lived.spy.history)
    assert sum(1 for m in in_memory if is_summary(m)) == (1 if compactions else 0)

    from_the_file = rebuilt(database(tmp_path), lived.session_id, lived.composition.history_prefix)
    from_the_same_store = resume_session(
        lived.composition.messages,  # type: ignore[arg-type]
        lived.session_id,
        prefix=lived.composition.history_prefix,
        current_model=MODEL,
        current_session_id="otra",
    )

    assert list(from_the_file.history) == in_memory  # a new connection, a new process
    assert list(from_the_same_store.history) == in_memory
    assert from_the_file.closed_calls == () and check_structure(from_the_file.history) is None
    assert from_the_file.has_summary is bool(compactions)


async def test_the_full_history_stays_stored_and_intact_after_the_compactions(
    tmp_path: Path, opened: list[Composition]
) -> None:
    lived = process(tmp_path, opened)
    await live(lived, 15, summaries=2)

    path = database(tmp_path)
    store = SqliteSessionStore(path)
    try:
        rows = (
            store.connection()
            .execute(
                "SELECT contenido FROM mensajes WHERE sesion_id = ? ORDER BY posicion",
                (lived.session_id,),
            )
            .fetchall()
        )
    finally:
        store.close()
    texts = " ".join(text for (text,) in rows)
    assert "tarea 1" in texts and "respuesta 1" in texts  # the oldest ones were compacted away
    assert len(rows) > len(lived.spy.history) - len(lived.composition.history_prefix)


# --- continuing the session --------------------------------------------------------------------


async def test_the_first_request_after_resuming_carries_the_history_to_the_same_session(
    tmp_path: Path, opened: list[Composition]
) -> None:
    first = process(tmp_path, opened)
    await first.run("tarea 1", "tarea 2")
    before_exit = list(first.spy.history)
    path = database(tmp_path)
    events_before = events_of(path, first.session_id)
    first.composition.close()

    second = process(tmp_path, opened, prefix="b")
    code = await second.run(f"/reanudar {first.session_id}", "tarea 3")

    assert code == 0
    sent = second.provider.received[0]
    assert sent == [*before_exit, Message(Role.USER, "tarea 3")]
    after = events_of(path, first.session_id)
    assert [row[:6] for row in after[: len(events_before)]] == [row[:6] for row in events_before]
    assert [row[2] for row in after] == list(range(1, len(after) + 1))  # no hole, no repeat
    assert len({row[0] for row in after}) == len(after)  # no duplicated event
    assert len(after) > len(events_before)
    assert events_of(path, second.session_id) == []  # nothing for the session that was left


async def test_resuming_publishes_nothing_and_writes_nothing_until_a_request_comes(
    tmp_path: Path, opened: list[Composition]
) -> None:
    first = process(tmp_path, opened)
    await first.run("tarea 1")
    path = database(tmp_path)
    first.composition.close()
    second = process(tmp_path, opened, prefix="b")
    connection = second.composition.store.connection()

    def snapshot() -> list[Any]:
        names = ("sessions", "events", "mensajes", "resumenes")
        return [connection.execute(f"SELECT * FROM {n} ORDER BY 1, 2").fetchall() for n in names]

    before = snapshot()
    await second.run(f"/reanudar {first.session_id}")

    assert snapshot() == before and second.provider.received == []
    assert path.exists()


# --- AC-02: the compaction of the first request after resuming ---------------------------------


async def test_ac02_a_long_session_is_compacted_before_the_first_request_after_resuming(
    tmp_path: Path, opened: list[Composition]
) -> None:
    first = process(tmp_path, opened)
    await first.run(*[f"tarea {n}" for n in range(1, 9)])
    assert first.provider.summaries == 0  # lived below the threshold
    first.composition.close()

    second = process(tmp_path, opened, prefix="b")
    await second.run(f"/reanudar {first.session_id}", "tarea 9")

    assert second.provider.summary_calls() == [0]  # one summary call, before the first request
    sent = second.provider.received[1]  # the first call of the loop
    assert sum(1 for m in sent if is_summary(m)) == 1
    assert ABOVE not in second.output  # and it came below the threshold
    connection = second.composition.store.connection()
    assert connection.execute("SELECT sesion_id FROM resumenes").fetchall() == [(first.session_id,)]
    types = [
        kind
        for (kind,) in connection.execute(
            "SELECT type FROM events WHERE session_id = ?", (first.session_id,)
        )
    ]
    assert "context_compacted" in types and "provider_error" not in types


async def test_a_short_session_is_resumed_without_any_summary_call(
    tmp_path: Path, opened: list[Composition]
) -> None:
    first = process(tmp_path, opened)
    await first.run("tarea 1", "tarea 2")
    first.composition.close()

    second = process(tmp_path, opened, prefix="b")
    await second.run(f"/reanudar {first.session_id}", "tarea 3")

    assert second.provider.summary_calls() == []
    assert second.composition.store.connection().execute(
        "SELECT count(*) FROM resumenes"
    ).fetchone() == (0,)


async def test_a_compacted_session_comes_back_as_the_summary_and_the_uncovered_messages(
    tmp_path: Path, opened: list[Composition]
) -> None:
    first = process(tmp_path, opened)
    await live(first, 15, summaries=2)
    before_exit = list(first.spy.history)
    first.composition.close()

    second = process(tmp_path, opened, prefix="b")
    await second.run(f"/reanudar {first.session_id}", "sigue")

    sent = second.provider.received[0]
    assert sent[: len(before_exit)] == before_exit  # the view the process had when it left
    assert sum(1 for m in sent if is_summary(m)) == 1  # a single summary, the newest one
    assert second.provider.summary_calls() in ([], [0])


async def test_after_resuming_the_compaction_keeps_working_and_belongs_to_the_resumed_session(
    tmp_path: Path, opened: list[Composition]
) -> None:
    first = process(tmp_path, opened)
    await live(first, 15, summaries=2)
    first.composition.close()
    second = process(tmp_path, opened, prefix="b")

    await live(second, 12, resume=first.session_id)

    assert second.provider.summaries >= 1

    connection = second.composition.store.connection()
    owners = [sid for (sid,) in connection.execute("SELECT sesion_id FROM resumenes")]
    assert set(owners) == {first.session_id} and len(owners) == 2 + second.provider.summaries
    assert "provider_error" not in [
        kind for (kind,) in connection.execute("SELECT type FROM events")
    ]


async def test_a_different_model_in_the_configuration_is_told_and_the_first_request_still_compacts(
    tmp_path: Path, opened: list[Composition]
) -> None:
    first = process(tmp_path, opened)
    await first.run(*[f"tarea {n}" for n in range(1, 9)])
    first.composition.close()

    second = process(tmp_path, opened, prefix="b", model=OTHER_MODEL)
    await second.run(f"/reanudar {first.session_id}", "tarea 9")

    assert "El modelo configurado difiere del de la sesión." in second.output
    assert second.provider.summary_calls() == [0]


# --- SC-007: a very long session -----------------------------------------------------------------


def test_a_session_of_five_thousand_messages_is_rebuilt_in_seconds(tmp_path: Path) -> None:
    path = database(tmp_path)
    store = SqliteSessionStore(path)
    try:
        session = store.create_session(model=MODEL).id
        connection = store.connection()
        events, rows = [], []
        for n in range(1, 5_001):
            user = n % 2 == 1
            kind = EventType.USER_MESSAGE if user else EventType.ASSISTANT_MESSAGE
            event_id = f"ev-{n}"
            events.append((event_id, session, n, kind.value, "{}", "2026-10-27T12:00:00+00:00"))
            rows.append(
                (
                    session,
                    n,
                    "user" if user else "assistant",
                    f"mensaje {n}",
                    event_id,
                    "2026-10-27T12:00:00+00:00",
                )
            )
        connection.executemany(
            "INSERT INTO events (id, session_id, seq, type, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            events,
        )
        connection.executemany(
            "INSERT INTO mensajes (sesion_id, posicion, rol, contenido, evento_id, creado) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        connection.commit()
    finally:
        store.close()
    prefix = (Message(Role.SYSTEM, "prefijo"),)

    started = time.perf_counter()
    resumed = rebuilt(path, session, prefix)
    elapsed = time.perf_counter() - started

    assert len(resumed.history) == 5_001 and resumed.message_count == 5_000
    assert elapsed < 5.0, elapsed
