"""The renewer fails closed (HU-02-06.1 / T004b, decision R15 and R16).

A session with a task whose elements are not there, or cannot be read, is never taken for a session
without a task: the renewer raises a fixed message and does not touch the history.
"""

from __future__ import annotations

import asyncio

import pytest

from harness_agent.core import (
    ContextSettings,
    EssentialContextTooLarge,
    EssentialContextUnavailable,
    Message,
    Role,
    TaskCriteriaItem,
    block_message,
    find_blocks,
)
from tests.unit.core.context.essential_support import (
    TINY,
    FakeCriteria,
    FakeSource,
    make_renewer,
    pending,
    stored_items,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
UNREADABLE = "No se pudo leer el contexto esencial de la tarea; la petición no se envía."
MISSING = "Faltan elementos del contexto esencial de la tarea; la petición no se envía."


class CriteriaIntegrityError(Exception):
    """Named like the error of the criteria store, which the core must not know."""


def history() -> list[Message]:
    return [
        Message(Role.SYSTEM, "entorno"),
        block_message("[contexto esencial de la tarea]\nviejo"),
        Message(Role.USER, "petición"),
    ]


def assert_closed(error: EssentialContextUnavailable, *, missing: bool) -> None:
    assert error.missing is missing
    assert str(error) == (MISSING if missing else UNREADABLE)
    assert SENTINEL not in str(error) + repr(error.args)
    assert error.__cause__ is None and error.__context__ is None  # the original is not kept


# --- a source or a reader that cannot be read -------------------------------------------------


@pytest.mark.parametrize("where", ["source", "reader", "model"])
def test_a_failure_of_what_it_reads_is_an_unreadable_context(where: str) -> None:
    def broken_model() -> str:
        raise RuntimeError(SENTINEL)

    keeper, source, reader = make_renewer(model=broken_model if where == "model" else lambda: "x/y")
    if where == "source":
        source.failure = RuntimeError(SENTINEL)
    if where == "reader":
        reader.failure = CriteriaIntegrityError(SENTINEL)
    before = history()
    target = list(before)

    with pytest.raises(EssentialContextUnavailable) as raised:
        keeper.renew(target)

    assert_closed(raised.value, missing=False)
    assert target == before and all(a is b for a, b in zip(target, before, strict=True))


def test_a_family_of_domain_errors_is_not_swallowed_into_another_message() -> None:
    keeper, _, _ = make_renewer(settings=TINY)

    with pytest.raises(EssentialContextTooLarge):
        keeper.renew([])


# --- a task whose elements are not there (never a session without a task) ---------------------


def test_with_a_task_and_no_elements_it_fails_closed() -> None:
    keeper, _, _ = make_renewer(FakeSource(()))
    target = history()
    before = list(target)

    with pytest.raises(EssentialContextUnavailable) as raised:
        keeper.renew(target)

    assert_closed(raised.value, missing=True)
    assert target == before and find_blocks(target) == [
        1
    ]  # the old block is not trusted nor touched


@pytest.mark.parametrize("gone", ["objetivo", "criterios_ref", "instrucciones"])
def test_each_obligatory_element_is_required_on_its_own(gone: str) -> None:
    remaining = tuple(item for item in stored_items() if item.key != gone)
    keeper, _, _ = make_renewer(FakeSource(remaining))
    target = history()
    before = list(target)

    with pytest.raises(EssentialContextUnavailable) as raised:
        keeper.renew(target)

    assert_closed(raised.value, missing=True)
    assert target == before


def test_the_optional_elements_may_be_missing() -> None:
    remaining = tuple(item for item in stored_items() if item.key not in ("ticket", "reglas"))
    keeper, _, _ = make_renewer(FakeSource(remaining))

    keeper.renew(history())  # no error


def test_one_instruction_is_enough() -> None:
    items = tuple(
        item for item in stored_items() if not (item.key == "instrucciones" and item.order == 2)
    )
    keeper, _, _ = make_renewer(FakeSource(items))

    keeper.renew(history())


# --- it does not fit --------------------------------------------------------------------------


def test_a_block_over_its_share_of_the_threshold_names_the_block_and_the_tokens() -> None:
    keeper, _, _ = make_renewer(settings=TINY)
    target = history()
    before = list(target)

    with pytest.raises(EssentialContextTooLarge) as raised:
        keeper.renew(target)

    assert str(raised.value) == (
        "El elemento «bloque completo» del contexto esencial supera el tope de 90 tokens."
    )
    assert target == before


def test_a_section_of_criteria_over_8000_characters_names_the_criteria() -> None:
    huge = [TaskCriteriaItem("1", SENTINEL + "a" * 9_000)]
    keeper, _, _ = make_renewer(criteria=FakeCriteria(huge))

    with pytest.raises(EssentialContextTooLarge) as raised:
        keeper.renew(history())

    assert str(raised.value) == (
        "El elemento «criterios» del contexto esencial supera el tope de 8000 caracteres."
    )
    assert SENTINEL not in str(raised.value) + repr(raised.value.args)


def test_the_threshold_is_the_one_of_the_model_returned_at_each_call() -> None:
    settings = ContextSettings(
        window_tokens=1_000, windows=(("grande/m", 1_000_000),), threshold_percent=45
    )
    chosen = ["grande/m"]
    keeper, _, _ = make_renewer(settings=settings, model=lambda: chosen[0])
    target = history()

    keeper.renew(target)  # fits with the big window
    chosen[0] = "pequeno/m"

    with pytest.raises(EssentialContextTooLarge):
        keeper.renew(target)
    chosen[0] = "grande/m"
    keeper.renew(target)  # and fits again when the model goes back


# --- what is not caught -----------------------------------------------------------------------


@pytest.mark.parametrize("signal", [asyncio.CancelledError, KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("where", ["source", "reader"])
def test_a_cancellation_or_an_interrupt_is_never_caught(
    signal: type[BaseException], where: str
) -> None:
    keeper, source, reader = make_renewer()
    (source if where == "source" else reader).failure = signal()

    with pytest.raises(signal):
        keeper.renew(history())


def test_a_good_renewal_still_works_after_a_failure() -> None:
    keeper, source, _ = make_renewer()
    source.failure = RuntimeError(SENTINEL)
    target = history()
    with pytest.raises(EssentialContextUnavailable):
        keeper.renew(target)
    source.failure = None

    keeper.renew(target)

    assert find_blocks(target) == [1] and pending()[0].description in target[1].content
