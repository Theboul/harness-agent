"""The structured result of a subagent: parsing, validation and shortening (HU-09-03 / T002)."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from harness_agent.core.subagents.result import (
    INVALID_RESULT,
    LIMIT_REACHED,
    MAX_ERROR_CHARS,
    MAX_ITEM_CHARS,
    MAX_ITEMS,
    MAX_RESULT_CHARS,
    RESULT_SCHEMA,
    failure_output,
    limit_code,
    parse_result,
    partial_output,
    shorten_output,
)
from harness_agent.core.tools.schema_validator import check_schema

SENTINEL = "VALOR-DE-PRUEBA-123"
KEYS = ["resultado", "hallazgos_clave", "fuentes", "error", "parcial"]


def answer(**changes: Any) -> str:
    data: dict[str, Any] = {"resultado": "listo", "hallazgos_clave": ["uno"], "fuentes": ["a.py"]}
    data.update(changes)
    return json.dumps(data)


def test_the_schema_is_one_the_validator_accepts() -> None:
    assert check_schema(RESULT_SCHEMA) == []


def test_a_valid_object_is_returned_as_it_came() -> None:
    parsed = parse_result(answer(error=None), RESULT_SCHEMA)

    assert parsed == {
        "resultado": "listo",
        "hallazgos_clave": ["uno"],
        "fuentes": ["a.py"],
        "error": None,
    }


@pytest.mark.parametrize("fence", ["```json\n{body}\n```", "```\n{body}\n```", "  \n{body}\n  "])
def test_the_object_may_come_in_a_code_block_or_with_blank_lines(fence: str) -> None:
    assert parse_result(fence.format(body=answer()), RESULT_SCHEMA) is not None


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "listo, terminé",
        "[1, 2]",
        '"solo un texto"',
        "null",
        "{",
        '{"resultado": "x"}',  # missing keys
        answer(extra="no declarado"),
        answer(resultado=3),
        answer(resultado=None),
        answer(hallazgos_clave="uno"),
        answer(hallazgos_clave=[1]),
        answer(fuentes=[None]),
        answer(error=5),
        "x" * 200_001,
        "[" * 5000,
    ],
    ids=[
        "empty",
        "blank",
        "prose",
        "list",
        "string",
        "null",
        "truncated",
        "missing",
        "extra-key",
        "number-result",
        "null-result",
        "string-findings",
        "number-finding",
        "null-source",
        "number-error",
        "huge",
        "deep",
    ],
)
def test_anything_else_is_not_a_result(text: str) -> None:
    assert parse_result(text, RESULT_SCHEMA) is None


def test_a_value_that_is_not_text_is_not_a_result() -> None:
    assert parse_result(None, RESULT_SCHEMA) is None  # type: ignore[arg-type]
    assert parse_result(b"{}", RESULT_SCHEMA) is None  # type: ignore[arg-type]


def test_a_schema_the_validator_does_not_accept_fails_closed() -> None:
    assert parse_result(answer(), {"type": "object", "oneOf": []}) is None


def test_the_schema_given_to_the_caller_can_be_changed_without_changing_the_constant() -> None:
    copied = copy.deepcopy(RESULT_SCHEMA)
    copied["properties"]["resultado"]["type"] = "integer"

    assert parse_result(answer(resultado=1), copied) is not None
    assert parse_result(answer(resultado=1), RESULT_SCHEMA) is None


def test_shortening_adds_the_five_keys_in_order_and_is_not_partial() -> None:
    shortened = shorten_output({"resultado": "ok", "hallazgos_clave": [], "fuentes": []})

    assert list(shortened) == KEYS
    assert shortened["error"] is None and shortened["parcial"] is False


def test_shortening_cuts_each_text_and_each_list_and_marks_the_cut() -> None:
    long_item = "a" * (MAX_ITEM_CHARS + 50)
    shortened = shorten_output(
        {
            "resultado": "r" * (MAX_RESULT_CHARS + 10),
            "hallazgos_clave": [long_item] * (MAX_ITEMS + 5),
            "fuentes": [long_item] * (MAX_ITEMS + 5),
            "error": "e" * (MAX_ERROR_CHARS + 10),
        }
    )

    assert len(shortened["resultado"]) == MAX_RESULT_CHARS
    assert shortened["resultado"].endswith("…")
    assert len(shortened["hallazgos_clave"]) == MAX_ITEMS == len(shortened["fuentes"])
    assert all(len(item) == MAX_ITEM_CHARS for item in shortened["hallazgos_clave"])
    assert shortened["hallazgos_clave"][0].endswith("…")
    assert len(shortened["error"]) == MAX_ERROR_CHARS


def test_shortening_leaves_a_short_text_alone_and_ignores_a_blank_error() -> None:
    shortened = shorten_output(
        {"resultado": "ok", "hallazgos_clave": ["x"], "fuentes": ["y"], "error": "   "}
    )

    assert shortened["resultado"] == "ok" and shortened["hallazgos_clave"] == ["x"]
    assert shortened["error"] is None


def test_shortening_does_not_trust_a_loose_input() -> None:
    shortened = shorten_output({"hallazgos_clave": "no es una lista", "otra": SENTINEL})

    assert shortened == failure_output_like(None)
    assert SENTINEL not in json.dumps(shortened)


def failure_output_like(error: str | None) -> dict[str, Any]:
    return {
        "resultado": "",
        "hallazgos_clave": [],
        "fuentes": [],
        "error": error,
        "parcial": False,
    }


def test_a_failure_has_the_five_keys_and_only_its_code() -> None:
    output = failure_output(INVALID_RESULT)

    assert list(output) == KEYS
    assert output == failure_output_like(INVALID_RESULT)


def test_a_partial_result_carries_the_last_text_cut_and_the_limit() -> None:
    output = partial_output("t" * (MAX_RESULT_CHARS + 5), f"{LIMIT_REACHED}:turns")

    assert list(output) == KEYS
    assert output["parcial"] is True and output["error"] == "limite_alcanzado:turns"
    assert len(output["resultado"]) == MAX_RESULT_CHARS
    assert output["hallazgos_clave"] == [] and output["fuentes"] == []


def test_a_partial_result_without_text_has_an_empty_result() -> None:
    assert partial_output(None, LIMIT_REACHED)["resultado"] == ""


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Session limit 'turns' reached (2 of 2).", "limite_alcanzado:turns"),
        ("Session limit 'time' reached (301 of 300).", "limite_alcanzado:time"),
        ("Session limit 'tokens' reached (9 of 8).", "limite_alcanzado:tokens"),
        ("Session limit 'otra cosa' reached.", "limite_alcanzado"),
        (None, "limite_alcanzado"),
        ("", "limite_alcanzado"),
    ],
)
def test_the_limit_comes_from_the_turn_only_when_it_is_a_known_one(
    message: str | None, expected: str
) -> None:
    assert limit_code(message) == expected
