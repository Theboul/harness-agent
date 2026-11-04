"""Tests for ``memoria``, the persistent memory tool (HU-04-02)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import pytest

from harness_agent.adapters.tools import MemoryTool
from harness_agent.core import (
    DefaultPermissionPolicy,
    InMemoryToolRegistry,
    MemoryFull,
    MemoryItem,
    MemorySettings,
    PermissionDecision,
    RiskLevel,
    SecretRedactor,
    ToolCall,
    ToolValidationError,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
# A value with the shape of a key, built in parts so the repository never holds one.
KEY_SHAPED = "sk-" + "A1b2C3d4E5f6G7h8I9j0K1l2"


class FakeLog:
    """A ``MemoryLog`` that records what it is asked to store and fails on demand."""

    def __init__(self, failure: BaseException | None = None) -> None:
        self.stored: dict[str, str] = {}
        self.calls: list[tuple[str, ...]] = []
        self.failure = failure

    def remember(self, key: str, content: str) -> None:
        self.calls.append(("remember", key, content))
        if self.failure is not None:
            raise self.failure
        self.stored[key] = content

    def forget(self, key: str) -> bool:
        self.calls.append(("forget", key))
        if self.failure is not None:
            raise self.failure
        return self.stored.pop(key, None) is not None

    def recent(self) -> Sequence[MemoryItem]:  # pragma: no cover - the tool never reads
        raise AssertionError("the tool never reads the memory")


def tool(log: FakeLog | None = None, **settings: Any) -> tuple[MemoryTool, FakeLog]:
    used = log or FakeLog()
    return MemoryTool(used, MemorySettings(enabled=True, **settings), SecretRedactor()), used


def run(memory: MemoryTool, **args: Any) -> Any:
    return asyncio.run(memory.run(args))


# --- what the tool is -------------------------------------------------------------------------


def test_the_tool_is_called_memoria_and_has_a_high_risk() -> None:
    memory, _ = tool()

    assert memory.name == "memoria"
    assert memory.risk is RiskLevel.HIGH
    assert "instrucciones" in memory.description


def test_the_schema_has_the_action_the_key_and_the_text_with_the_configured_cap() -> None:
    memory, _ = tool(max_content_chars=123)
    schema = memory.schema

    assert schema["properties"]["accion"]["enum"] == ["guardar", "olvidar"]
    assert schema["properties"]["texto"]["maxLength"] == 123
    assert schema["properties"]["clave"]["maxLength"] == 60
    assert schema["required"] == ["accion", "clave"]
    assert schema["additionalProperties"] is False


def test_the_registry_validates_the_arguments_of_the_schema() -> None:
    registry = InMemoryToolRegistry()
    memory, _ = tool(max_content_chars=50)
    registry.register(memory)

    registry.validate_args("memoria", {"accion": "guardar", "clave": "a", "texto": "x" * 50})
    for bad in (
        {"accion": "guardar", "clave": "a", "texto": "x" * 51},
        {"accion": "borrar", "clave": "a"},
        {"clave": "a"},
        {"accion": "guardar", "clave": "a", "extra": 1},
        {"accion": "guardar", "clave": "k" * 61},
    ):
        with pytest.raises(ToolValidationError):
            registry.validate_args("memoria", bad)


def test_the_default_policy_asks_for_every_call_and_never_allows_it_alone() -> None:
    registry = InMemoryToolRegistry()
    memory, _ = tool()
    registry.register(memory)
    policy = DefaultPermissionPolicy(registry)

    for arguments in (
        {"accion": "guardar", "clave": "a", "texto": "x"},
        {"accion": "olvidar", "clave": "a"},
        {"accion": "guardar", "clave": "a", "texto": "x", "path": "a.txt"},
    ):
        assert policy.evaluate(ToolCall("c1", "memoria", arguments)) is PermissionDecision.ASK


# --- guardar ----------------------------------------------------------------------------------


def test_saving_stores_a_clean_line_under_the_lower_case_key() -> None:
    memory, log = tool()

    result = run(memory, accion="guardar", clave="Estilo", texto="  tabs\n de   4 ")

    assert log.stored == {"estilo": "tabs de 4"}
    assert result.is_error is False
    assert result.content == "Guardado en la memoria: estilo."
    assert "tabs" not in result.content


def test_a_secret_is_hidden_before_it_reaches_the_log_and_the_result_says_so() -> None:
    memory, log = tool()

    result = run(memory, accion="guardar", clave="k", texto=f"la clave es {KEY_SHAPED} y ya")

    assert KEY_SHAPED not in log.stored["k"] and "<secreto oculto>" in log.stored["k"]
    assert "Se ocultaron datos con forma de credencial" in result.content
    assert KEY_SHAPED not in result.content


def test_the_same_key_replaces_the_text() -> None:
    memory, log = tool()

    run(memory, accion="guardar", clave="k", texto="uno")
    run(memory, accion="guardar", clave="k", texto="dos")

    assert log.stored == {"k": "dos"}


@pytest.mark.parametrize(
    "args",
    [
        {"accion": "guardar", "clave": "mala clave", "texto": "x"},
        {"accion": "guardar", "clave": "", "texto": "x"},
        {"accion": "guardar", "clave": "k"},
        {"accion": "guardar", "clave": "k", "texto": "   "},
        {"accion": "guardar", "clave": "k", "texto": 5},
        {"accion": "guardar", "clave": "k", "texto": "x" * 501},
    ],
)
def test_a_bad_key_or_text_is_a_fixed_error_and_the_log_is_not_called(args: dict[str, Any]) -> None:
    memory, log = tool()

    result = run(memory, **args)

    assert result.is_error is True and result.content.startswith("[memoria_invalida] ")
    assert log.calls == []


def test_the_result_of_a_refusal_never_repeats_what_was_sent() -> None:
    memory, _ = tool()

    result = run(memory, accion="guardar", clave=SENTINEL, texto="x")
    long_text = run(memory, accion="guardar", clave="k", texto=SENTINEL * 100)

    assert SENTINEL not in result.content and SENTINEL not in long_text.content


def test_an_unknown_action_is_a_fixed_error() -> None:
    memory, log = tool()

    result = run(memory, accion=SENTINEL, clave="k")

    assert result.content.startswith("[accion_invalida] ") and SENTINEL not in result.content
    assert log.calls == []


def test_a_full_memory_is_a_tagged_error() -> None:
    memory, _ = tool(FakeLog(MemoryFull()))

    result = run(memory, accion="guardar", clave="k", texto="x")

    assert result.is_error and result.content.startswith("[memoria_llena] ")
    assert "olvidar" in result.content


def test_a_store_that_fails_is_a_fixed_error_without_what_it_said() -> None:
    memory, _ = tool(FakeLog(RuntimeError(f"disco {SENTINEL}")))

    result = run(memory, accion="guardar", clave="k", texto="x")
    forgotten = run(memory, accion="olvidar", clave="k")

    for answer in (result, forgotten):
        assert answer.is_error and answer.content.startswith("[memoria_error] ")
        assert SENTINEL not in answer.content


@pytest.mark.parametrize("failure", [asyncio.CancelledError(), KeyboardInterrupt()])
def test_a_cancellation_or_an_interrupt_goes_up(failure: BaseException) -> None:
    memory, _ = tool(FakeLog(failure))

    with pytest.raises(type(failure)):
        run(memory, accion="guardar", clave="k", texto="x")


# --- olvidar ----------------------------------------------------------------------------------


def test_forgetting_deletes_by_key_and_a_missing_key_is_not_an_error() -> None:
    memory, log = tool()
    run(memory, accion="guardar", clave="k", texto="x")

    deleted = run(memory, accion="olvidar", clave="K")
    missing = run(memory, accion="olvidar", clave="k")

    assert log.stored == {}
    assert deleted.is_error is False and deleted.content == "Borrado de la memoria: k."
    assert missing.is_error is False and "No había ninguna entrada" in missing.content


def test_forgetting_with_a_bad_key_is_a_fixed_error() -> None:
    memory, log = tool()

    result = run(memory, accion="olvidar", clave="mala clave")

    assert result.is_error and result.content.startswith("[memoria_invalida] ")
    assert log.calls == []
