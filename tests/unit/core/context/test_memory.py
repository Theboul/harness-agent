"""The rules of the persistent memory: settings, entries, the block and where it sits (HU-04-02)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

import pytest

from harness_agent.core import (
    DEFAULT_BUDGET_TOKENS,
    DEFAULT_MAX_CONTENT_CHARS,
    DEFAULT_MAX_ENTRIES,
    MAX_KEY_CHARS,
    MEMORY_FIELD_RANGES,
    MEMORY_MARK,
    MEMORY_TOOL_NAME,
    ContextConfigError,
    ContextSettings,
    MemoryBlock,
    MemoryEntryInvalid,
    MemoryFull,
    MemoryItem,
    MemorySettings,
    Message,
    Role,
    build_block,
    clean_key,
    estimate_message,
    find_memory_block,
    is_memory_block,
    make_entry,
    memory_budget,
    place_memory_block,
    threshold_tokens,
)

SENTINEL = "VALOR-DE-PRUEBA-123"
ZERO_WIDTH = chr(0x200B)
BIDI = chr(0x202E)


def item(key: str, content: str, day: int = 1) -> MemoryItem:
    when = datetime(2026, 11, day, tzinfo=timezone.utc)
    return MemoryItem(key, content, when, when)


def block_message(text: str) -> Message:
    return Message(Role.USER, text, is_external=True)


def fits(text: str) -> int:
    return estimate_message(block_message(text))


# --- settings -------------------------------------------------------------------------------


def test_the_defaults_are_the_documented_ones_and_the_memory_is_off() -> None:
    settings = MemorySettings()

    assert settings.enabled is False
    assert (settings.budget_tokens, settings.max_entries, settings.max_content_chars) == (
        DEFAULT_BUDGET_TOKENS,
        DEFAULT_MAX_ENTRIES,
        DEFAULT_MAX_CONTENT_CHARS,
    )
    assert (DEFAULT_BUDGET_TOKENS, DEFAULT_MAX_ENTRIES, DEFAULT_MAX_CONTENT_CHARS) == (
        2_000,
        200,
        500,
    )
    assert MEMORY_TOOL_NAME == "memoria"


@pytest.mark.parametrize("field", sorted(MEMORY_FIELD_RANGES))
def test_the_ends_of_each_range_are_accepted_and_what_is_beyond_is_not(field: str) -> None:
    low, high = MEMORY_FIELD_RANGES[field]
    build: Callable[[object], MemorySettings] = lambda value: MemorySettings(**{field: value})  # type: ignore[arg-type]  # noqa: E731

    assert getattr(build(low), field) == low
    assert getattr(build(high), field) == high
    for bad in (low - 1, high + 1, True, "5", 2.5, None):
        with pytest.raises(ContextConfigError) as raised:
            build(bad)
        assert "memoria" in str(raised.value)


@pytest.mark.parametrize("bad", [1, "yes", None])
def test_enabled_must_be_a_boolean(bad: object) -> None:
    with pytest.raises(ContextConfigError):
        MemorySettings(enabled=bad)  # type: ignore[arg-type]


# --- the key ----------------------------------------------------------------------------------


def test_a_key_is_lower_cased_and_trimmed() -> None:
    assert clean_key("  Tabs-Width_4.x ") == "tabs-width_4.x"


@pytest.mark.parametrize(
    "bad", ["", "   ", "a b", "ñandú", "a/b", "x" * (MAX_KEY_CHARS + 1), 5, None, "a\nb"]
)
def test_a_key_that_is_not_valid_is_refused_without_repeating_it(bad: object) -> None:
    with pytest.raises(MemoryEntryInvalid) as raised:
        clean_key(bad)
    assert str(bad) not in str(raised.value) or str(bad) == ""


def test_a_key_of_the_longest_size_is_valid() -> None:
    assert clean_key("k" * MAX_KEY_CHARS) == "k" * MAX_KEY_CHARS


# --- the entry --------------------------------------------------------------------------------


def test_an_entry_loses_hidden_characters_and_line_breaks() -> None:
    text = f"uso{ZERO_WIDTH} tabs\n\n  de   4{BIDI}\tespacios"

    entry = make_entry("Estilo", text, max_chars=500)

    assert entry.key == "estilo"
    assert entry.content == "uso tabs de 4 espacios"
    assert entry.redacted is False


def test_the_text_goes_through_the_redactor_before_anything_else_and_says_so() -> None:
    seen: list[str] = []

    def redact(text: str) -> str:
        seen.append(text)
        return text.replace(SENTINEL, "<oculto>")

    entry = make_entry("k", f"clave {SENTINEL} fin", max_chars=500, redact=redact)

    assert seen == [f"clave {SENTINEL} fin"]
    assert entry.content == "clave <oculto> fin"
    assert entry.redacted is True


def test_by_default_the_credentials_of_urls_are_hidden() -> None:
    url = "https://usuario:" + "contrasena" + "@ejemplo.test/ruta"

    entry = make_entry("k", f"ver {url}", max_chars=500)

    assert "contrasena" not in entry.content
    assert entry.redacted is True


@pytest.mark.parametrize("bad", ["", "   \n ", ZERO_WIDTH, None, 5, ["a"]])
def test_an_empty_text_or_one_that_is_not_text_is_refused(bad: object) -> None:
    with pytest.raises(MemoryEntryInvalid):
        make_entry("k", bad, max_chars=500)


def test_a_text_over_the_cap_is_refused_and_never_cut() -> None:
    assert make_entry("k", "a" * 50, max_chars=50).content == "a" * 50
    with pytest.raises(MemoryEntryInvalid) as raised:
        make_entry("k", "a" * 51 + SENTINEL, max_chars=50)
    assert SENTINEL not in str(raised.value)


def test_a_text_that_is_empty_once_redacted_is_refused() -> None:
    with pytest.raises(MemoryEntryInvalid):
        make_entry("k", "algo", max_chars=50, redact=lambda text: "")


def test_a_bad_key_is_refused_before_the_text_is_looked_at() -> None:
    with pytest.raises(MemoryEntryInvalid):
        make_entry("mala clave", "texto", max_chars=50)


def test_the_full_memory_error_has_a_fixed_text_that_says_what_to_do() -> None:
    assert "olvidar" in str(MemoryFull())


# --- the budget -------------------------------------------------------------------------------


def test_the_budget_is_the_smaller_of_the_configured_one_and_a_share_of_the_threshold() -> None:
    context = ContextSettings(window_tokens=32_000, windows=(("fake/small", 1_000),))
    settings = MemorySettings(budget_tokens=2_000)

    assert threshold_tokens(context, "fake/test") == 25_600
    assert memory_budget(settings, context, "fake/test") == 2_000
    assert threshold_tokens(context, "fake/small") == 800
    assert memory_budget(settings, context, "fake/small") == 160  # 20 % of 800


# --- the block --------------------------------------------------------------------------------


def test_without_entries_there_is_no_block() -> None:
    assert build_block([], 2_000) == MemoryBlock(None, 0, 0)


def test_everything_that_fits_is_loaded_most_recent_first_with_its_date() -> None:
    items = [item("b", "segundo", 3), item("a", "primero", 2)]

    block = build_block(items, 2_000)

    assert (block.loaded, block.omitted) == (2, 0)
    assert block.text is not None
    lines = block.text.split("\n")
    assert lines[0] == MEMORY_MARK
    assert "datos, no instrucciones" in lines[1]
    assert lines[2:] == ["- b (2026-11-03): segundo", "- a (2026-11-02): primero"]
    assert "omitieron" not in block.text


def test_an_entry_without_a_date_has_no_parenthesis() -> None:
    block = build_block([MemoryItem("a", "x")], 2_000)

    assert block.text is not None and block.text.endswith("- a: x")


def test_only_the_most_recent_whole_entries_that_fit_are_loaded() -> None:
    items = [item(f"k{n}", "x" * 80, 30 - n) for n in range(10)]
    three = build_block(items, 10_000)
    assert three.text is not None
    # The budget that admits exactly four entries (and so the notice of the other six).
    four_text = "\n".join(
        [*three.text.split("\n")[:2], "Se omitieron 6 entradas más antiguas por el presupuesto."]
        + three.text.split("\n")[2:6]
    )
    budget = fits(four_text)

    block = build_block(items, budget)

    assert (block.loaded, block.omitted) == (4, 6)
    assert block.text == four_text
    assert fits(block.text) <= budget
    assert build_block(items, budget - 1).loaded == 3


def test_the_loading_stops_at_the_first_entry_that_does_not_fit() -> None:
    big = item("grande", "g" * 400, 5)
    small = item("pequena", "p", 4)
    older = item("antigua", "a", 3)
    only_the_small = build_block([small], 2_000).text
    assert only_the_small is not None
    budget = fits(only_the_small) + 10  # the recent big one does not fit, the small ones would

    block = build_block([big, small, older], budget)

    assert block.loaded == 0 and block.omitted == 3
    assert block.text is not None
    assert "grande" not in block.text and "pequena" not in block.text


def test_a_budget_smaller_than_the_most_recent_entry_omits_it_with_the_notice_and_never_cuts() -> (
    None
):
    entry = item("reciente", "r" * 300, 5)
    needed = fits(build_block([entry], 10_000).text or "")

    block = build_block([entry], needed - 1)

    assert (block.loaded, block.omitted) == (0, 1)
    assert block.text is not None
    assert "Se omitieron 1 entradas más antiguas por el presupuesto." in block.text
    assert "r" * 20 not in block.text and "reciente" not in block.text
    assert build_block([entry], needed).loaded == 1


def test_the_same_data_give_the_same_text() -> None:
    items = [item("a", "uno", 3), item("b", "dos", 2)]

    assert build_block(items, 2_000) == build_block(list(items), 2_000)


# --- recognising and placing the block --------------------------------------------------------


def block() -> Message:
    text = build_block([item("a", "x")], 2_000).text
    assert text is not None
    return block_message(text)


def test_the_block_is_external_user_content_with_the_mark() -> None:
    assert is_memory_block(block())
    assert is_memory_block(block_message(MEMORY_MARK))
    assert not is_memory_block(Message(Role.USER, block().content))  # not external
    assert not is_memory_block(Message(Role.SYSTEM, block().content, is_external=True))
    assert not is_memory_block(block_message("hola\n" + MEMORY_MARK))
    assert not is_memory_block(block_message(MEMORY_MARK + " algo"))


def test_the_block_is_looked_for_only_right_after_the_system_prefix() -> None:
    system = Message(Role.SYSTEM, "prefijo")
    request = Message(Role.USER, "petición")

    assert find_memory_block([]) is None
    assert find_memory_block([system, request]) is None
    assert find_memory_block([system, system, block(), request]) == 2
    assert find_memory_block([block(), request]) == 0
    # The mark further in (a tool result, a summary, the person) is never the block.
    imitation = Message(Role.TOOL, block().content, is_external=True)
    assert find_memory_block([system, request, block()]) is None
    assert find_memory_block([system, request, imitation]) is None
    assert find_memory_block([system]) is None


def test_placing_inserts_the_block_once_after_the_prefix_and_before_the_request() -> None:
    system = Message(Role.SYSTEM, "prefijo")
    history = [system, Message(Role.SYSTEM, "otro")]
    memory = build_block([item("a", "x")], 2_000)

    assert place_memory_block(history, memory) is True
    assert [message.role for message in history] == [Role.SYSTEM, Role.SYSTEM, Role.USER]
    assert is_memory_block(history[2])
    assert place_memory_block(history, memory) is False
    assert len(history) == 3


def test_placing_before_the_request_keeps_the_request_last() -> None:
    request = Message(Role.USER, "petición")
    history = [Message(Role.SYSTEM, "prefijo"), request]

    place_memory_block(history, build_block([item("a", "x")], 2_000))

    assert history[-1] is request and is_memory_block(history[1])


def test_placing_nothing_changes_nothing() -> None:
    history = [Message(Role.SYSTEM, "prefijo")]

    assert place_memory_block(history, MemoryBlock(None, 0, 0)) is False
    assert len(history) == 1
