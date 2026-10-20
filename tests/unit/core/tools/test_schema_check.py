"""Tests for ``check_schema``: validation of a tool's argument schema at registration (T005).

``check_schema`` returns one problem per defect. Every problem is a complete Spanish sentence
that ends with a period and starts with the place inside the schema:

* ``(raíz)`` for the root schema;
* the path of the schema (``properties.limite``) when the defect is about the schema itself,
  for example an unsupported keyword;
* the path of the keyword (``properties.limite.minimum``) when the defect is about its value.

The registry will prepend ``esquema `` later, so problems never start with it.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from harness_agent.core.tools.schema_validator import check_schema

ROOT = "(raíz)"
DEPTH_LIMIT = 32
DEPTH_SENTENCE = "se supera la profundidad máxima de 32 niveles de anidamiento."
UNSUPPORTED_KEYWORDS = [
    "$ref",
    "$defs",
    "anyOf",
    "oneOf",
    "allOf",
    "not",
    "pattern",
    "format",
    "const",
    "if",
    "then",
    "else",
]


def obj(**properties: Any) -> dict[str, Any]:
    """Root object schema whose properties are the given sub-schemas."""
    return {"type": "object", "properties": dict(properties)}


def assert_single_problem(problems: list[str], place: str, fragment: str) -> None:
    assert len(problems) == 1, problems
    problem = problems[0]
    assert problem.startswith(f"{place}: "), problem
    assert fragment in problem, problem
    assert problem.endswith("."), problem


def assert_well_formed(problems: list[str]) -> None:
    """Every problem is `<place>: <sentence>.` and carries no registry prefix."""
    assert problems
    for problem in problems:
        assert ": " in problem, problem
        assert problem.endswith("."), problem
        assert not problem.startswith("esquema "), problem


def nested_by_properties(levels: int) -> dict[str, Any]:
    """Object schema with ``levels`` schema levels in total; the root is the first level."""
    schema: dict[str, Any] = {"type": "object"}
    for _ in range(levels - 1):
        schema = {"type": "object", "properties": {"child": schema}}
    return schema


def nested_by_items(levels: int) -> dict[str, Any]:
    """Root object whose ``lista`` property nests arrays through ``items`` down to ``levels``."""
    inner: dict[str, Any] = {"type": "string"}
    for _ in range(levels - 2):
        inner = {"type": "array", "items": inner}
    return {"type": "object", "properties": {"lista": inner}}


def circular_by_properties() -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "object", "properties": {}}
    schema["properties"]["self"] = schema
    return schema


def circular_by_items() -> dict[str, Any]:
    array: dict[str, Any] = {"type": "array"}
    array["items"] = array
    return {"type": "object", "properties": {"lista": array}}


class TestEstructura:
    """Root, types, properties, required, additionalProperties and unsupported keywords."""

    # --- Valid schemas -------------------------------------------------------------------

    def test_minimal_schema_is_valid(self) -> None:
        assert check_schema({"type": "object"}) == []

    def test_realistic_schema_is_valid(self) -> None:
        schema = {
            "type": "object",
            "description": "Lee un archivo.",
            "properties": {
                "ruta": {"type": "string", "description": "Ruta relativa."},
                "limite": {"type": ["integer", "null"], "default": None},
                "opciones": {
                    "type": "object",
                    "properties": {"tiempo_maximo": {"type": "number"}},
                    "required": ["tiempo_maximo"],
                    "additionalProperties": False,
                },
            },
            "required": ["ruta"],
            "additionalProperties": True,
        }

        assert check_schema(schema) == []

    @pytest.mark.parametrize(
        "keyword, value",
        [
            ("description", "Texto"),
            ("title", "Título"),
            ("default", 1),
            ("examples", [1, 2]),
            ("$comment", "nota"),
            ("$schema", "https://json-schema.org/draft/2020-12/schema"),
        ],
    )
    def test_inert_annotations_are_accepted_at_the_root_and_nested(
        self, keyword: str, value: Any
    ) -> None:
        schema = {
            "type": "object",
            keyword: value,
            "properties": {"campo": {"type": "string", keyword: value}},
        }

        assert check_schema(schema) == []

    @pytest.mark.parametrize(
        "declared",
        [["string", "null"], ["integer", "number"], ["string"], "string", "null"],
    )
    def test_type_names_and_unions_of_type_names_are_valid(self, declared: Any) -> None:
        assert check_schema(obj(campo={"type": declared})) == []

    def test_field_names_are_not_mistaken_for_keywords(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "enum": {"type": "string"},
                "$ref": {"type": "string"},
                "type": {"type": "string"},
            },
            "required": ["pattern", "type"],
        }

        assert check_schema(schema) == []

    def test_empty_required_list_is_valid(self) -> None:
        assert check_schema({"type": "object", "required": []}) == []

    @pytest.mark.parametrize("value", [True, False])
    def test_boolean_additional_properties_is_valid(self, value: bool) -> None:
        assert check_schema({"type": "object", "additionalProperties": value}) == []

    # --- Root ----------------------------------------------------------------------------

    @pytest.mark.parametrize("bad", [None, [], "object", 42, True])
    def test_root_must_be_a_mapping(self, bad: Any) -> None:
        assert_single_problem(check_schema(bad), ROOT, "debe ser un objeto")

    @pytest.mark.parametrize("schema", [{}, {"properties": {}}, {"description": "sin tipo"}])
    def test_root_must_declare_its_type(self, schema: dict[str, Any]) -> None:
        assert_single_problem(check_schema(schema), ROOT, "'type': 'object'")

    @pytest.mark.parametrize(
        "declared", ["string", "array", ["object", "null"], ["object"], "null"]
    )
    def test_root_type_must_be_exactly_object(self, declared: Any) -> None:
        assert_single_problem(check_schema({"type": declared}), ROOT, "'type': 'object'")

    def test_invalid_root_type_is_reported_only_once(self) -> None:
        assert_single_problem(
            check_schema({"type": "banana"}), "type", "no es uno de los soportados"
        )

    # --- type ----------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "declared, fragment",
        [
            ("banana", "no es uno de los soportados"),
            ("", "no es uno de los soportados"),
            (["string", "banana"], "no es uno de los soportados"),
            ([1], "no es uno de los soportados"),
            ([["x"]], "no es uno de los soportados"),
            ([{"a": 1}], "no es uno de los soportados"),
            ([], "vacía"),
            (["string", "string"], "repetidos"),
            (42, "debe ser el nombre de un tipo"),
            (None, "debe ser el nombre de un tipo"),
            ({"a": 1}, "debe ser el nombre de un tipo"),
        ],
    )
    def test_invalid_type_values_are_reported_at_the_type_keyword(
        self, declared: Any, fragment: str
    ) -> None:
        problems = check_schema(obj(limite={"type": declared}))

        assert_single_problem(problems, "properties.limite.type", fragment)

    def test_unknown_type_name_is_not_echoed_in_the_problem(self) -> None:
        problems = check_schema(obj(limite={"type": "SECRETO-123"}))

        assert_single_problem(problems, "properties.limite.type", "no es uno de los soportados")
        assert "SECRETO-123" not in problems[0]

    # --- properties ----------------------------------------------------------------------

    @pytest.mark.parametrize("bad", [None, [], "campo", 42])
    def test_properties_must_be_a_mapping(self, bad: Any) -> None:
        schema = {"type": "object", "properties": bad}

        assert_single_problem(check_schema(schema), "properties", "debe ser un objeto")

    @pytest.mark.parametrize("bad", ["string", None, ["string"], 7, True])
    def test_every_property_must_be_a_schema_object(self, bad: Any) -> None:
        problems = check_schema(obj(limite=bad))

        assert_single_problem(problems, "properties.limite", "debe ser un objeto")

    def test_problems_inside_nested_properties_use_the_full_path(self) -> None:
        schema = obj(
            opciones={"type": "object", "properties": {"tiempo": {"type": "banana"}}},
        )

        assert_single_problem(
            check_schema(schema),
            "properties.opciones.properties.tiempo.type",
            "no es uno de los soportados",
        )

    # --- required ------------------------------------------------------------------------

    @pytest.mark.parametrize("bad", ["ruta", None, 3, {"ruta": True}])
    def test_required_must_be_a_list(self, bad: Any) -> None:
        schema = {**obj(ruta={"type": "string"}), "required": bad}

        assert_single_problem(check_schema(schema), "required", "debe ser una lista de nombres")

    def test_required_must_contain_only_text(self) -> None:
        schema = {**obj(ruta={"type": "string"}), "required": ["ruta", 1]}

        assert_single_problem(check_schema(schema), "required", "solo nombres de campo")

    def test_required_must_not_repeat_names(self) -> None:
        schema = {**obj(ruta={"type": "string"}), "required": ["ruta", "ruta"]}

        assert_single_problem(check_schema(schema), "required", "repetidos")

    def test_required_field_missing_from_properties_names_the_field(self) -> None:
        schema = {**obj(ruta={"type": "string"}), "required": ["ruta", "otro"]}

        problems = check_schema(schema)

        assert_single_problem(problems, "required", "'otro'")
        assert "no está declarado en properties" in problems[0]

    def test_every_undeclared_required_field_gets_its_own_problem_in_order(self) -> None:
        schema = {**obj(ruta={"type": "string"}), "required": ["b", "ruta", "a"]}

        problems = check_schema(schema)

        assert len(problems) == 2
        assert "'b'" in problems[0]
        assert "'a'" in problems[1]

    def test_required_without_properties_reports_the_undeclared_field(self) -> None:
        assert_single_problem(
            check_schema({"type": "object", "required": ["x"]}), "required", "'x'"
        )

    def test_nested_required_uses_the_path_of_the_nested_schema(self) -> None:
        schema = obj(opciones={"type": "object", "required": ["tiempo"]})

        assert_single_problem(check_schema(schema), "properties.opciones.required", "'tiempo'")

    def test_invalid_properties_do_not_add_noise_about_required_fields(self) -> None:
        schema = {"type": "object", "properties": None, "required": ["x"]}

        assert_single_problem(check_schema(schema), "properties", "debe ser un objeto")

    # --- additionalProperties ------------------------------------------------------------

    @pytest.mark.parametrize("bad", [{}, {"type": "string"}, "false", 0, 1, None])
    def test_additional_properties_must_be_a_boolean(self, bad: Any) -> None:
        schema = {"type": "object", "additionalProperties": bad}

        assert_single_problem(check_schema(schema), "additionalProperties", "true o false")

    # --- Unsupported keywords ------------------------------------------------------------

    @pytest.mark.parametrize("keyword", UNSUPPORTED_KEYWORDS)
    def test_unsupported_keyword_at_the_root_names_the_keyword(self, keyword: str) -> None:
        schema = {"type": "object", keyword: {}}

        assert_single_problem(check_schema(schema), ROOT, f"palabra clave no soportada '{keyword}'")

    @pytest.mark.parametrize("keyword", UNSUPPORTED_KEYWORDS)
    def test_unsupported_keyword_in_a_property_names_the_place_and_the_keyword(
        self, keyword: str
    ) -> None:
        schema = obj(limite={"type": "integer", keyword: {}})

        assert_single_problem(
            check_schema(schema), "properties.limite", f"palabra clave no soportada '{keyword}'"
        )

    def test_contract_example_is_produced_verbatim(self) -> None:
        schema = obj(limite={"type": "integer", "pattern": "^[0-9]+$"})

        assert check_schema(schema) == ["properties.limite: palabra clave no soportada 'pattern'."]

    def test_unsupported_keyword_deeply_nested_uses_the_full_path(self) -> None:
        schema = obj(
            opciones={
                "type": "object",
                "properties": {"campo": {"type": "string", "format": "date"}},
            },
        )

        assert check_schema(schema) == [
            "properties.opciones.properties.campo: palabra clave no soportada 'format'."
        ]

    def test_each_unsupported_keyword_gets_its_own_problem_in_order(self) -> None:
        schema = {"type": "object", "oneOf": [], "pattern": "x", "not": {}}

        assert check_schema(schema) == [
            "(raíz): palabra clave no soportada 'oneOf'.",
            "(raíz): palabra clave no soportada 'pattern'.",
            "(raíz): palabra clave no soportada 'not'.",
        ]

    # --- General -------------------------------------------------------------------------

    def test_all_defects_are_reported_together_in_a_deterministic_order(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "a": {"type": "banana"},
                "b": {"type": "string", "pattern": "x"},
            },
            "required": ["c"],
        }

        problems = check_schema(schema)

        assert len(problems) == 3
        assert problems[0].startswith("properties.a.type: ")
        assert problems[1] == "properties.b: palabra clave no soportada 'pattern'."
        assert problems[2].startswith("required: ")
        assert check_schema(schema) == problems

    def test_the_schema_is_not_modified(self) -> None:
        schema = {
            "type": "object",
            "properties": {"a": {"type": "banana"}, "b": {"pattern": "x"}},
            "required": ["c"],
        }
        original = copy.deepcopy(schema)

        check_schema(schema)

        assert schema == original

    @pytest.mark.parametrize(
        "schema",
        [
            None,
            {},
            {"type": "banana"},
            {"type": "object", "oneOf": []},
            {"type": "object", "required": "x"},
            {"type": "object", "additionalProperties": {}},
            obj(a={"type": []}, b="x"),
            obj(opciones={"type": "object", "required": ["z"]}),
        ],
    )
    def test_every_problem_is_a_complete_sentence_with_its_place(self, schema: Any) -> None:
        assert_well_formed(check_schema(schema))


class TestRestricciones:
    """enum, numeric bounds, length and item counts, items and the maximum depth."""

    # --- enum ----------------------------------------------------------------------------

    @pytest.mark.parametrize("values", [[1], ["a", "b"], [None], [True, 1], [{"a": 1}], [[1, 2]]])
    def test_non_empty_enum_lists_are_valid(self, values: list[Any]) -> None:
        assert check_schema(obj(modo={"enum": values})) == []

    def test_empty_enum_is_rejected(self) -> None:
        problems = check_schema(obj(modo={"enum": []}))

        assert_single_problem(problems, "properties.modo.enum", "no puede estar vacía")

    @pytest.mark.parametrize("bad", ["a", None, 3, {"a": 1}])
    def test_enum_must_be_a_list(self, bad: Any) -> None:
        problems = check_schema(obj(modo={"enum": bad}))

        assert_single_problem(problems, "properties.modo.enum", "debe ser una lista de valores")

    # --- minimum / maximum ---------------------------------------------------------------

    @pytest.mark.parametrize("value", [0, -3, 2.5, 10**400, -(10**400)])
    def test_finite_numbers_are_valid_bounds_even_when_huge(self, value: float) -> None:
        schema = obj(n={"type": "number", "minimum": value, "maximum": value})

        assert check_schema(schema) == []

    @pytest.mark.parametrize("keyword", ["minimum", "maximum"])
    @pytest.mark.parametrize(
        "bad",
        [True, False, "1", None, [1], float("nan"), float("inf"), float("-inf")],
    )
    def test_non_numeric_or_non_finite_bounds_are_rejected(self, keyword: str, bad: Any) -> None:
        problems = check_schema(obj(n={"type": "number", keyword: bad}))

        assert_single_problem(problems, f"properties.n.{keyword}", "número finito")

    def test_minimum_greater_than_maximum_is_rejected(self) -> None:
        problems = check_schema(obj(n={"type": "number", "minimum": 5, "maximum": 1}))

        assert_single_problem(problems, "properties.n.minimum", "no puede ser mayor que maximum")

    def test_minimum_equal_to_maximum_is_valid(self) -> None:
        assert check_schema(obj(n={"type": "number", "minimum": 3, "maximum": 3})) == []

    def test_an_invalid_bound_does_not_trigger_the_comparison(self) -> None:
        problems = check_schema(obj(n={"type": "number", "minimum": "x", "maximum": 1}))

        assert_single_problem(problems, "properties.n.minimum", "número finito")

    # --- minLength / maxLength / minItems / maxItems -------------------------------------

    @pytest.mark.parametrize("keyword", ["minLength", "maxLength", "minItems", "maxItems"])
    @pytest.mark.parametrize("value", [0, 7, 10**30])
    def test_non_negative_integers_are_valid_counts(self, keyword: str, value: int) -> None:
        assert check_schema(obj(n={keyword: value})) == []

    @pytest.mark.parametrize("keyword", ["minLength", "maxLength", "minItems", "maxItems"])
    @pytest.mark.parametrize("bad", [-1, True, 1.5, "3", None, [2]])
    def test_invalid_counts_are_rejected(self, keyword: str, bad: Any) -> None:
        problems = check_schema(obj(n={keyword: bad}))

        assert_single_problem(problems, f"properties.n.{keyword}", "entero no negativo")

    @pytest.mark.parametrize("low, high", [("minLength", "maxLength"), ("minItems", "maxItems")])
    def test_minimum_count_greater_than_maximum_count_is_rejected(
        self, low: str, high: str
    ) -> None:
        problems = check_schema(obj(n={low: 5, high: 1}))

        assert_single_problem(problems, f"properties.n.{low}", f"no puede ser mayor que {high}")

    @pytest.mark.parametrize("low, high", [("minLength", "maxLength"), ("minItems", "maxItems")])
    def test_equal_minimum_and_maximum_counts_are_valid(self, low: str, high: str) -> None:
        assert check_schema(obj(n={low: 2, high: 2})) == []

    # --- items ---------------------------------------------------------------------------

    def test_single_schema_items_is_valid(self) -> None:
        schema = obj(lista={"type": "array", "items": {"type": "string"}, "minItems": 1})

        assert check_schema(schema) == []

    def test_list_form_items_is_rejected(self) -> None:
        problems = check_schema(obj(lista={"type": "array", "items": [{"type": "string"}]}))

        assert_single_problem(problems, "properties.lista.items", "lista de esquemas")

    @pytest.mark.parametrize("bad", ["string", True, None, 3])
    def test_items_must_be_a_schema_object(self, bad: Any) -> None:
        problems = check_schema(obj(lista={"type": "array", "items": bad}))

        assert_single_problem(problems, "properties.lista.items", "debe ser un objeto")

    def test_problems_inside_items_use_the_items_path(self) -> None:
        problems = check_schema(obj(lista={"type": "array", "items": {"type": "banana"}}))

        assert_single_problem(
            problems, "properties.lista.items.type", "no es uno de los soportados"
        )

    def test_unsupported_keyword_inside_items_is_reported(self) -> None:
        schema = obj(lista={"type": "array", "items": {"type": "string", "pattern": "x"}})

        assert check_schema(schema) == [
            "properties.lista.items: palabra clave no soportada 'pattern'."
        ]

    def test_items_nested_in_items_extend_the_path(self) -> None:
        schema = obj(
            lista={"type": "array", "items": {"type": "array", "items": {"type": "banana"}}}
        )

        assert_single_problem(
            check_schema(schema),
            "properties.lista.items.items.type",
            "no es uno de los soportados",
        )

    # --- Maximum depth -------------------------------------------------------------------

    def test_max_schema_depth_constant_is_32(self) -> None:
        from harness_agent.core.tools import schema_validator

        assert schema_validator.MAX_SCHEMA_DEPTH == DEPTH_LIMIT

    def test_exactly_the_maximum_depth_through_properties_is_valid(self) -> None:
        assert check_schema(nested_by_properties(DEPTH_LIMIT)) == []

    def test_one_level_over_the_maximum_through_properties_is_rejected(self) -> None:
        problems = check_schema(nested_by_properties(DEPTH_LIMIT + 1))

        assert len(problems) == 1
        assert problems[0].startswith("properties.child.properties.child.")
        assert problems[0].endswith(DEPTH_SENTENCE)

    def test_exactly_the_maximum_depth_through_items_is_valid(self) -> None:
        assert check_schema(nested_by_items(DEPTH_LIMIT)) == []

    def test_one_level_over_the_maximum_through_items_is_rejected(self) -> None:
        problems = check_schema(nested_by_items(DEPTH_LIMIT + 1))

        assert len(problems) == 1
        assert problems[0].startswith("properties.lista.items.items.")
        assert problems[0].endswith(DEPTH_SENTENCE)

    def test_circular_schema_through_properties_yields_one_problem(self) -> None:
        problems = check_schema(circular_by_properties())

        assert len(problems) == 1
        assert problems[0].endswith(DEPTH_SENTENCE)

    def test_circular_schema_through_items_yields_one_problem(self) -> None:
        problems = check_schema(circular_by_items())

        assert len(problems) == 1
        assert problems[0].endswith(DEPTH_SENTENCE)

    # --- General -------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "schema",
        [
            obj(modo={"enum": []}),
            obj(n={"type": "number", "minimum": float("nan")}),
            obj(n={"minLength": -1}),
            obj(n={"minItems": 5, "maxItems": 1}),
            obj(lista={"type": "array", "items": [{"type": "string"}]}),
            nested_by_properties(DEPTH_LIMIT + 1),
            circular_by_properties(),
        ],
    )
    def test_every_problem_is_a_complete_sentence_with_its_place(
        self, schema: dict[str, Any]
    ) -> None:
        assert_well_formed(check_schema(schema))
