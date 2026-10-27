"""Seeded random check of the guarantees of ``rejection_message`` (HU-05-04)."""

from __future__ import annotations

import random
import unicodedata

from harness_agent.core import MAX_REJECTION_CHARS, clean_reason, rejection_message

SEED = 20261028
CASES = 2_000
ALPHABET = (
    list("abc XYZ019 .:;,/\\-_'\"[]()")
    + ["\n", "\r", "\t", "\x00", "\x1b", "\x7f", "\x85"]
    + [chr(0x200B), chr(0x202E), chr(0x2028), chr(0x2029), chr(0xFEFF), chr(0xE000), chr(0xD800)]
    + list("ñáé€😀")
    + ["://", "@", "[approval_rejected]", "system:", "Ignora lo anterior"]
)
NAMES = ["shell", "escribir_archivo", "n" * 120, "n" * 450, ""]


def random_reason(rng: random.Random) -> str:
    size = rng.choice([0, 1, 5, 40, 250, 900, 3_000])
    return "".join(rng.choice(ALPHABET) for _ in range(size))


def test_guarantees_hold_for_random_reasons() -> None:
    rng = random.Random(SEED)
    for _ in range(CASES):
        reason = random_reason(rng)
        name = rng.choice(NAMES)
        message = rejection_message(name, reason)
        first = f"[approval_rejected] Tool '{name}' was rejected by the user."

        assert message.startswith(first)
        assert message == rejection_message(name, reason)
        assert "\n" not in message and "\r" not in message
        if message != first:
            assert len(message) <= MAX_REJECTION_CHARS
            assert message.endswith("'")
            inner = message[message.index("action: '") + len("action: '") : -1]
            assert "'" not in inner and '"' not in inner
            assert inner
        cleaned = clean_reason(reason)
        if cleaned is not None:
            assert clean_reason(cleaned) == cleaned
            assert not [c for c in cleaned if unicodedata.category(c) in ("Cc", "Cf", "Cs", "Co")]
            assert "\n" not in cleaned
            assert cleaned == cleaned.strip()
