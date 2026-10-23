"""Tests of ``PermissionRules``: the immutable lists of denied and asked tools (HU-05-01 / T002).

There is no field to allow: the rules can only make the policy stricter (spec FR-022, R-3 of the
data model). The error messages are in Spanish and never reproduce the invalid value.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from harness_agent.core.permissions import PermissionRules
from tests.unit.core.permissions.support import SENTINEL


class TestValoresPorDefecto:
    def test_the_rules_are_empty_by_default(self) -> None:
        rules = PermissionRules()

        assert rules.deny == ()
        assert rules.ask == ()
        assert rules == PermissionRules((), ())

    def test_there_is_no_field_to_allow(self) -> None:
        names = {field.name for field in dataclasses.fields(PermissionRules)}

        assert names == {"deny", "ask"}
        with pytest.raises(TypeError):
            PermissionRules(allow=("a",))  # type: ignore[call-arg]


class TestInmutabilidad:
    def test_the_rules_are_frozen_hashable_and_without_a_dict(self) -> None:
        rules = PermissionRules(("a",), ("b",))

        with pytest.raises(dataclasses.FrozenInstanceError):
            rules.deny = ("c",)  # type: ignore[misc]
        assert hash(rules) == hash(PermissionRules(("a",), ("b",)))
        assert not hasattr(rules, "__dict__")

    def test_the_lists_are_stored_as_tuples(self) -> None:
        rules = PermissionRules(deny=["a", "b"], ask=["c"])  # type: ignore[arg-type]

        assert rules.deny == ("a", "b")
        assert rules.ask == ("c",)
        assert isinstance(rules.deny, tuple)


class TestNombresValidos:
    def test_the_names_are_kept_as_they_are_and_in_order(self) -> None:
        names = ("Escribir", "leer-archivo", "una herramienta", "x_1")

        assert PermissionRules(deny=names).deny == names

    def test_the_duplicates_are_dropped_keeping_the_first_order(self) -> None:
        rules = PermissionRules(deny=("b", "a", "b", "a", "c"))

        assert rules.deny == ("b", "a", "c")
        assert PermissionRules(("a", "a")) == PermissionRules(("a",))

    def test_a_name_may_be_in_both_lists(self) -> None:
        rules = PermissionRules(deny=("a",), ask=("a",))

        assert rules.deny == rules.ask == ("a",)


class TestNombresInvalidos:
    @pytest.mark.parametrize("bad", [None, 5, "", "   ", "\t\n", b"abc", ["x"]])
    @pytest.mark.parametrize("field", ["deny", "ask"])
    def test_an_element_that_is_not_a_non_empty_text_is_rejected(
        self, field: str, bad: Any
    ) -> None:
        with pytest.raises(ValueError) as raised:
            PermissionRules(**{field: ("valido", bad)})

        assert str(raised.value) == (
            f"La lista '{field}' tiene un elemento no válido en la posición 1: "
            "debe ser un texto no vacío."
        )

    def test_the_message_never_reproduces_the_value(self) -> None:
        with pytest.raises(ValueError) as raised:
            PermissionRules(ask=({"valor": SENTINEL},))  # type: ignore[arg-type]

        assert SENTINEL not in str(raised.value)

    @pytest.mark.parametrize("bad", ["abc", b"abc", None, 5, {"a"}, frozenset({"a"})])
    @pytest.mark.parametrize("field", ["deny", "ask"])
    def test_something_that_is_not_a_tuple_or_a_list_is_rejected(
        self, field: str, bad: Any
    ) -> None:
        with pytest.raises(TypeError) as raised:
            PermissionRules(**{field: bad})

        assert str(raised.value).startswith(f"La lista '{field}' debe ser una secuencia de textos")
        assert "'str'" in str(raised.value) or "no '" in str(raised.value)

    def test_a_bare_string_is_not_iterated_by_characters(self) -> None:
        with pytest.raises(TypeError):
            PermissionRules(deny="escribir")  # type: ignore[arg-type]
