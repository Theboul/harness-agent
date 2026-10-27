"""Seeded random check of the condition grammar (HU-11-04.1)."""

from __future__ import annotations

import random

from harness_agent.core import MAX_EXIT_CODE, Condition, condition_met, parse_condition

SEED = 20261029
CASES = 2_000
SPACES = ["", " ", "  ", "\t"]
ALIEN = list("abcxyzABC-+.,;:<>=!()[]{}'\"\\/%$#@~|&*?_") + [
    "\n",
    "\r",
    "\x00",
    "\x1b",
    "é",
    chr(0x202E),
]


def constructed(rng: random.Random) -> tuple[str, Condition]:
    operator = rng.choice(["==", "!="])
    value = rng.choice([0, 1, 2, 127, 255, 65_535, rng.randint(0, MAX_EXIT_CODE), MAX_EXIT_CODE])
    digits = str(value).rjust(rng.randint(len(str(value)), 10), "0")
    text = (
        rng.choice(SPACES)
        + "codigo_salida"
        + rng.choice(SPACES)
        + operator
        + rng.choice(SPACES)
        + digits
        + rng.choice(SPACES)
    )
    return text, Condition(operator, value)


def test_a_constructed_valid_text_is_parsed_exactly() -> None:
    rng = random.Random(SEED)
    for _ in range(CASES):
        text, expected = constructed(rng)
        assert parse_condition(text) == expected


def test_a_foreign_character_makes_the_text_invalid() -> None:
    rng = random.Random(SEED + 1)
    for _ in range(CASES):
        text, _ = constructed(rng)
        stripped = text.strip()
        position = rng.randint(1, len(stripped) - 1)  # inside: the edges are trimmed
        broken = stripped[:position] + rng.choice(ALIEN) + stripped[position:]
        assert parse_condition(broken) is None, repr(broken)


def test_nothing_ever_raises() -> None:
    rng = random.Random(SEED + 2)
    for _ in range(CASES):
        size = rng.choice([0, 1, 5, 30, 200])
        text = "".join(rng.choice(ALIEN + list("0123456789 =")) for _ in range(size))
        condition = parse_condition(text)
        assert condition is None or isinstance(condition, Condition)
        assert condition_met(Condition("==", 0), rng.choice([None, 0, 1, -1, MAX_EXIT_CODE])) in (
            True,
            False,
        )
