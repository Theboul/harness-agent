"""compose() and run_session() wire the essential context of a task (HU-02-06.1 / T007 and T007b).

The provider is a ``FakeProvider`` or a double; the database is a temporary file; the shell is a
double that never runs. Nothing reaches the network.
"""

from __future__ import annotations

import asyncio
import dataclasses
import io
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.adapters.storage import SessionStoreError, SqliteSessionStore
from harness_agent.bootstrap import Composition, StartupError
from harness_agent.core import (
    MARK,
    CommandKind,
    ContextSettings,
    CriterionDefinition,
    EssentialContextTooLarge,
    EssentialContextUnavailable,
    EssentialItem,
    EssentialRenewer,
    EventType,
    Message,
    ProviderResponse,
    Role,
    Shell,
    ShellResult,
    TaskCommand,
    TaskDefinition,
)
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import build, make_config

SENTINEL = "VALOR-DE-PRUEBA-123"
CAP = "El elemento «{element}» del contexto esencial supera el tope de {limit} {unit}."


class NoShell(Shell):
    @property
    def interpreter_name(self) -> str:
        return "bash"

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        raise AssertionError("no command runs in these tests")

    def terminate_running(self) -> None:
        """Nothing runs."""


@pytest.fixture(autouse=True)
def no_real_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: NoShell())


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def make_task(**changes: Any) -> TaskDefinition:
    task = TaskDefinition(
        title="TAREA-14: Validar el correo",
        objective="Rechazar correos sin dominio en el formulario de alta.",
        context="contexto libre que no entra en el bloque",
        rules="No tocar el esquema de la base.\nMantener la API pública.",
        criteria=(
            CriterionDefinition("El validador rechaza a@ y a@b", "check-ok", "codigo_salida == 0"),
            CriterionDefinition("Se ve bien"),
        ),
    )
    return dataclasses.replace(task, **changes)


def compose_with(
    tmp_path: Path,
    opened: list[Composition],
    task: TaskDefinition | None,
    *,
    context: ContextSettings | None = None,
    provider: FakeProvider | None = None,
) -> Composition:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(parents=True, exist_ok=True)
    config = make_config(tmp_path, workspace=workspace)
    if context is not None:
        config = dataclasses.replace(config, context=context)
    return build(opened, config, provider, task=task, system_name="Linux")


def rows(composition: Composition) -> list[tuple[Any, ...]]:
    cursor = composition.store.connection().execute(
        "SELECT clave, orden, valor, origen FROM contexto_esencial WHERE sesion_id = ? "
        "ORDER BY clave, orden",
        (composition.session_id,),
    )
    return cursor.fetchall()


def values(composition: Composition, key: str) -> list[str]:
    return [row[2] for row in rows(composition) if row[0] == key]


# --- compose with a task: the elements are stored ---------------------------------------------


def test_with_a_task_the_elements_are_stored_with_their_origin(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = compose_with(tmp_path, opened, make_task())

    stored = rows(composition)

    assert [(row[0], row[1], row[3]) for row in stored] == [
        ("criterios_ref", 1, "criterios protegidos (HU-11-01)"),
        ("instrucciones", 1, "entorno"),
        ("instrucciones", 2, "git"),
        ("objetivo", 1, "tarea (objetivo)"),
        ("reglas", 1, "tarea (reglas)"),
        ("ticket", 1, "tarea (título)"),
    ]
    assert values(composition, "ticket") == ["TAREA-14: Validar el correo"]
    assert values(composition, "objetivo") == [
        "Rechazar correos sin dominio en el formulario de alta."
    ]
    assert values(composition, "reglas") == [
        "No tocar el esquema de la base.\nMantener la API pública."
    ]
    assert values(composition, "criterios_ref") == [composition.session_id]
    assert "contexto libre" not in repr(stored)  # the free context of the task stays out


def test_the_instructions_are_the_exact_texts_of_the_prefix_and_the_prefix_is_unchanged(
    tmp_path: Path, opened: list[Composition]
) -> None:
    plain = compose_with(tmp_path / "plain", opened, None)
    composition = compose_with(tmp_path / "task", opened, make_task())

    assert values(composition, "instrucciones") == [m.content for m in composition.history_prefix]
    assert len(composition.history_prefix) == 2
    assert composition.history_prefix == plain.history_prefix  # FR-022: the prefix does not change


def test_with_the_commands_of_the_task_the_third_instruction_is_recorded_as_commands(
    tmp_path: Path, opened: list[Composition]
) -> None:
    task = make_task(commands=(TaskCommand(CommandKind.TESTS, "check-ok", 300),))

    composition = compose_with(tmp_path, opened, task)

    assert [row[3] for row in rows(composition) if row[0] == "instrucciones"] == [
        "entorno",
        "git",
        "comandos",
    ]
    assert values(composition, "instrucciones") == [m.content for m in composition.history_prefix]
    assert len(composition.history_prefix) == 3


def test_a_credential_of_a_url_in_the_objective_is_stored_hidden(
    tmp_path: Path, opened: list[Composition]
) -> None:
    url = "https://" + "usuario" + ":" + SENTINEL + "@servidor.example/r.git"

    composition = compose_with(tmp_path, opened, make_task(objective="Clonar " + url))

    assert values(composition, "objetivo") == [
        "Clonar https://<secreto oculto>@servidor.example/r.git"
    ]
    assert SENTINEL not in repr(rows(composition))


def test_without_a_title_or_rules_those_rows_do_not_exist(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = compose_with(tmp_path, opened, make_task(title=None, rules=""))

    assert {row[0] for row in rows(composition)} == {"criterios_ref", "instrucciones", "objetivo"}


def test_without_a_task_nothing_is_stored(tmp_path: Path, opened: list[Composition]) -> None:
    composition = compose_with(tmp_path, opened, None)

    count = composition.store.connection().execute("SELECT count(*) FROM contexto_esencial")
    assert count.fetchone() == (0,)
    assert composition.task is None


# --- validation before anything is opened -----------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "element"),
    [
        ({"objective": "a" * 8_001}, "objetivo"),
        ({"rules": "a" * 8_001}, "reglas"),
        ({"title": "a" * 8_001}, "ticket"),
    ],
)
def test_an_element_over_its_cap_stops_the_start_before_the_store_is_opened(
    tmp_path: Path, opened: list[Composition], changes: dict[str, Any], element: str
) -> None:
    changes = {key: SENTINEL + value for key, value in changes.items()}

    with pytest.raises(StartupError) as raised:
        compose_with(tmp_path, opened, make_task(**changes))

    assert str(raised.value) == CAP.format(element=element, limit=8000, unit="caracteres")
    assert SENTINEL not in str(raised.value)
    assert not (tmp_path / "datos").exists()  # no database was created


def test_a_block_that_does_not_fit_the_threshold_stops_the_start_before_the_store_is_opened(
    tmp_path: Path, opened: list[Composition]
) -> None:
    tiny = ContextSettings(window_tokens=1_000, threshold_percent=45)  # the block may weigh 90

    with pytest.raises(StartupError) as raised:
        compose_with(tmp_path, opened, make_task(), context=tiny)

    assert str(raised.value) == CAP.format(element="bloque completo", limit=90, unit="tokens")
    assert not (tmp_path / "datos").exists()


# --- the second save fails after start_task (R17) ---------------------------------------------


def test_a_failed_second_save_stops_the_start_and_leaves_no_usable_session(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    stores: list[SqliteSessionStore] = []

    class RecordingStore(SqliteSessionStore):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            stores.append(self)

    class FailingEssential:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def save_items(self, session_id: str, items: list[EssentialItem]) -> None:
            raise SessionStoreError("fallo de prueba")

        def items(self, session_id: str) -> list[EssentialItem]:  # pragma: no cover
            return []

    monkeypatch.setattr(bootstrap, "SqliteSessionStore", RecordingStore)
    monkeypatch.setattr(bootstrap, "SqliteEssentialStore", FailingEssential)

    with pytest.raises(SessionStoreError):
        compose_with(tmp_path, opened, make_task())

    assert len(stores) == 1 and opened == []  # no composition was handed back
    with pytest.raises(SessionStoreError):
        stores[0].get_session("lo-que-sea")  # the store was closed
    raw = sqlite3.connect(tmp_path / "datos" / "sesiones.db")
    try:
        assert raw.execute("SELECT count(*) FROM contexto_esencial").fetchone() == (0,)
        # the session of start_task stays in the database: a known, documented orphan (R17)
        assert raw.execute("SELECT count(*) FROM sessions").fetchone() == (1,)
    finally:
        raw.close()


# --- T007b: the renewal in run_session and in the rounds --------------------------------------

MISSING = "Faltan elementos del contexto esencial de la tarea; la petición no se envía."
UNREADABLE = "No se pudo leer el contexto esencial de la tarea; la petición no se envía."


class ScriptedShell(NoShell):
    """Answers each command with its list of exit codes, one per run; records the runs."""

    def __init__(self, codes: dict[str, list[int]]) -> None:
        self.codes = {command: list(values) for command, values in codes.items()}
        self.calls: list[str] = []
        self.after: dict[str, Any] = {}

    def execute(self, command: str, timeout_seconds: float) -> ShellResult:
        self.calls.append(command)
        code = self.codes[command].pop(0)
        if command in self.after:
            self.after[command]()
        return ShellResult(exit_code=code, output="salida")


def two_criteria_task() -> TaskDefinition:
    return make_task(
        criteria=(
            CriterionDefinition("El validador rechaza a@", "check-a", "codigo_salida == 0"),
            CriterionDefinition(
                "Pasan las pruebas del formulario", "check-b", "codigo_salida == 0"
            ),
        ),
        commands=(
            TaskCommand(CommandKind.TESTS, "check-a", 300),
            TaskCommand(CommandKind.LINT, "check-b", 300),
        ),
    )


def blocks_of(messages: list[Message]) -> list[Message]:
    return [m for m in messages if m.role is Role.SYSTEM and m.content.startswith(MARK)]


def run_lines(composition: Composition, text: str) -> tuple[int, str]:
    output = io.StringIO()
    code = asyncio.run(
        bootstrap.run_session(composition, input_stream=io.StringIO(text), output=output)
    )
    return code, output.getvalue()


def replies(count: int) -> FakeProvider:
    return FakeProvider([ProviderResponse(content="listo") for _ in range(count)])


def test_with_a_task_the_composition_has_a_renewer_and_without_one_it_has_none(
    tmp_path: Path, opened: list[Composition]
) -> None:
    with_task = compose_with(tmp_path / "a", opened, make_task())
    without = compose_with(tmp_path / "b", opened, None)

    assert isinstance(with_task.essential, EssentialRenewer)
    assert without.essential is None


def test_the_block_reaches_the_model_after_the_provisional_messages_and_before_the_request(
    tmp_path: Path, opened: list[Composition]
) -> None:
    provider = replies(1)
    composition = compose_with(tmp_path, opened, make_task(), provider=provider)

    code, _ = run_lines(composition, "mi petición\n/salir\n")

    assert code == 0
    sent = provider.received[0]
    prefix = list(composition.history_prefix)
    assert sent[: len(prefix)] == prefix
    assert sent[len(prefix)].role is Role.SYSTEM and sent[len(prefix)].content.startswith(MARK)
    assert sent[len(prefix) + 1] == Message(Role.USER, "mi petición")
    assert len(blocks_of(sent)) == 1
    assert "Objetivo:\nRechazar correos sin dominio" in sent[len(prefix)].content


def test_the_renewal_comes_before_the_compaction(tmp_path: Path, opened: list[Composition]) -> None:
    seen: list[bool] = []

    class RecordingCompactor:
        async def before_turn(self, history: list[Message]) -> None:
            seen.append(bool(blocks_of(history)))

    composition = compose_with(tmp_path, opened, make_task(), provider=replies(1))
    composition = dataclasses.replace(composition, compactor=RecordingCompactor())  # type: ignore[arg-type]

    run_lines(composition, "mi petición\n/salir\n")

    assert seen == [True]  # when the compactor ran, the block was already in the history


def test_between_two_rounds_the_block_shows_the_criterion_that_the_verifier_marked(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    shell = ScriptedShell({"check-a": [0, 0], "check-b": [1, 0]})
    monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: shell)
    provider = replies(2)
    composition = compose_with(tmp_path, opened, two_criteria_task(), provider=provider)
    history = list(composition.history_prefix)
    assert composition.runner is not None

    asyncio.run(composition.runner.run("trabaja", history))

    first, second = provider.received
    assert len(blocks_of(first)) == len(blocks_of(second)) == 1  # never two blocks
    assert "1. [pendiente] El validador rechaza a@" in blocks_of(first)[0].content
    assert "1. [cumplido] El validador rechaza a@" in blocks_of(second)[0].content
    assert "2. [pendiente] Pasan las pruebas" in blocks_of(second)[0].content
    assert len(blocks_of(history)) == 1 and shell.calls[:2] == ["check-a", "check-b"]


def test_a_task_without_its_elements_does_not_send_the_request_and_ends_with_failure(
    tmp_path: Path, opened: list[Composition]
) -> None:
    provider = replies(1)
    composition = compose_with(tmp_path, opened, make_task(), provider=provider)
    composition.store.connection().execute("DELETE FROM contexto_esencial")
    composition.store.connection().commit()

    code, output = run_lines(composition, "mi petición\n/salir\n")

    assert code == 1
    assert output.count(MISSING) == 1
    assert provider.call_count == 0  # never taken for a session without a task


@pytest.mark.parametrize(
    ("error", "text"),
    [
        (EssentialContextUnavailable(), UNREADABLE),
        (
            EssentialContextTooLarge("bloque completo", 90, "tokens"),
            CAP.format(element="bloque completo", limit=90, unit="tokens"),
        ),
    ],
)
def test_the_fixed_message_of_any_renewal_failure_is_written_and_the_session_ends(
    tmp_path: Path, opened: list[Composition], error: Exception, text: str
) -> None:
    class Failing:
        def renew(self, history: list[Message]) -> None:
            raise error

    provider = replies(1)
    composition = compose_with(tmp_path, opened, make_task(), provider=provider)
    composition = dataclasses.replace(composition, essential=Failing())  # type: ignore[arg-type]

    code, output = run_lines(composition, "mi petición\n/salir\n")

    assert code == 1 and output.count(text) == 1 and provider.call_count == 0


def test_a_failure_before_a_round_is_reported_and_the_round_is_not_sent(
    tmp_path: Path, opened: list[Composition], monkeypatch: pytest.MonkeyPatch
) -> None:
    shell = ScriptedShell({"check-a": [0], "check-b": [1]})
    monkeypatch.setattr(bootstrap, "select_shell", lambda *a, **k: shell)
    holder: list[Composition] = []

    class LosingTheRows(FakeProvider):
        async def complete(self, messages: list[Message], tools: Any = None) -> ProviderResponse:
            response = await super().complete(messages, tools)
            if self.call_count == 1:  # the rows disappear after the first round has gone out
                connection = holder[0].store.connection()
                connection.execute("DELETE FROM contexto_esencial")
                connection.commit()
            return response

    provider = LosingTheRows([ProviderResponse(content="listo"), ProviderResponse(content="x")])
    composition = compose_with(tmp_path, opened, two_criteria_task(), provider=provider)
    holder.append(composition)
    sink = io.StringIO()
    composition.warning_sink.stream = sink
    history = list(composition.history_prefix)
    assert composition.runner is not None

    with pytest.raises(EssentialContextUnavailable):
        asyncio.run(composition.runner.run("trabaja", history))

    assert MISSING in sink.getvalue() and provider.call_count == 1  # the second round never left


def test_without_a_task_there_is_no_block_and_the_request_goes_out(
    tmp_path: Path, opened: list[Composition]
) -> None:
    provider = replies(1)
    composition = compose_with(tmp_path, opened, None, provider=provider)

    code, _ = run_lines(composition, "mi petición\n/salir\n")

    assert code == 0 and provider.call_count == 1
    assert blocks_of(provider.received[0]) == []
    assert provider.received[0] == [*composition.history_prefix, Message(Role.USER, "mi petición")]


def test_the_renewal_publishes_no_event_of_its_own(
    tmp_path: Path, opened: list[Composition]
) -> None:
    composition = compose_with(tmp_path, opened, make_task(), provider=replies(1))
    seen: list[EventType] = []
    for event_type in EventType:
        composition.bus.subscribe(event_type, lambda event: seen.append(event.type))

    run_lines(composition, "mi petición\n/salir\n")

    others = {EventType.CONTEXT_COMPACTED, EventType.PROVIDER_ERROR, EventType.CRITERIA_TAMPERED}
    assert not others & set(seen) and EventType.USER_MESSAGE in seen
