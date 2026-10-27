"""``hide_url_credentials`` costs time in proportion to the size of its input, and it did not.

The previous version was one regular expression that, for every letter of a long word, tried to
read the whole word again looking for ``://`` (quadratic). The performance tests compare the time
for an input and for double the input instead of reading a fine clock, and the differential test
compares the new function with a copy of the previous one over seeded random inputs.
"""

from __future__ import annotations

import random
import re
import time
from collections.abc import Callable

import pytest

from harness_agent.core import HIDDEN_SECRET, hide_url_credentials

# The previous implementation, kept here only as the reference of the differential test.
_REFERENCE = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*://)[^\s/@]+@")


def reference(text: str) -> str:
    return _REFERENCE.sub(lambda found: f"{found.group(1)}{HIDDEN_SECRET}@", text)


# --- performance --------------------------------------------------------------------------------

BASE = 40_000
BIG = 1_000_000
SHAPES: dict[str, Callable[[int], str]] = {
    "letters": lambda n: "x" * n,
    "letters-then-scheme": lambda n: "x" * n + "://" + "y" * n,
    "many-schemes": lambda n: "a://" * (n // 4),
    "many-at-signs": lambda n: "a://" + "@" * n,
    "many-urls-with-credentials": lambda n: "a://u" + "p@h/" * (n // 4),
    "unclosed-url": lambda n: "http://" + "u" * n,
    "digits-and-dots": lambda n: "1.2.3." * (n // 6) + "://",
    "spaces-and-colons": lambda n: "a: " * (n // 3),
}


def best_time(function: Callable[[str], str], text: str) -> float:
    times = []
    for _ in range(3):
        start = time.perf_counter()
        function(text)
        times.append(time.perf_counter() - start)
    return min(times)


@pytest.mark.parametrize("shape", SHAPES)
def test_doubling_the_input_does_not_multiply_the_time(shape: str) -> None:
    make = SHAPES[shape]
    small = best_time(hide_url_credentials, make(BASE))
    double = best_time(hide_url_credentials, make(2 * BASE))

    # Linear: about 2x. The absolute slack keeps tiny times from making a noisy ratio.
    assert double <= 3 * small + 0.05, (shape, small, double)


@pytest.mark.parametrize("shape", SHAPES)
def test_a_megabyte_is_fast(shape: str) -> None:
    text = SHAPES[shape](BIG)

    start = time.perf_counter()
    hide_url_credentials(text)

    assert time.perf_counter() - start < 1.0, shape


# --- differential test --------------------------------------------------------------------------

SEED = 20261030
TOKENS = [
    "http", "https", "ftp", "a", "x1", "1a", "9", "+", "-.", "A", "HTTP", "ssh+git",
    "://", ":", "//", "/", "@", "@@", " ", "\t", "\n", "?", "#", ".",
    "user", "pw", "u:p", "token", "host", "r.git",
    "é", "日本", "ñ", "Ω", "ß",
    chr(0xA0), chr(0x2028), chr(0x1C), chr(0x3000), chr(0x200B), chr(0x202E), chr(0),
    "http://", "https://", "a://", "ftp://u", "://@", "://:@",
]  # fmt: skip


def random_text(rng: random.Random, longest: int) -> str:
    return "".join(rng.choice(TOKENS) for _ in range(rng.randint(0, longest)))


def test_the_new_function_gives_the_same_text_as_the_previous_one() -> None:
    rng = random.Random(SEED)
    inputs = [random_text(rng, 12) for _ in range(3_000)]
    inputs += [random_text(rng, 60) for _ in range(1_000)]

    differences = [text for text in inputs if hide_url_credentials(text) != reference(text)]

    assert differences == []
    assert any(HIDDEN_SECRET in hide_url_credentials(text) for text in inputs)  # it does hide


@pytest.mark.parametrize(
    "text",
    [
        "",
        "sin urls",
        "https://usuario:clave@host/r.git y http://publico/x",
        "a://@",
        "a://b@",
        "a://b@c://d@e",
        "xxhttp://u@h",
        "1http://u@h",
        "9://u@h",
        "http://u:p@h http://v@h",
        "http:// u@h",
        "http://u /x@h",
        "ftp://" + chr(0xA0) + "u@h",
        "\n://u@h",
    ],
)
def test_the_known_corner_cases_agree(text: str) -> None:
    assert hide_url_credentials(text) == reference(text)


def test_the_marker_and_the_type_error_are_unchanged() -> None:
    assert HIDDEN_SECRET == "<secreto oculto>"
    with pytest.raises(TypeError):
        hide_url_credentials(5)  # type: ignore[arg-type]
