"""Tests for ``validate_arguments``: part 1 (T011) types, required and undeclared fields; part 2
(T012) ``enum``, numeric, length and item-count bounds, and ``items``.

``validate_arguments`` returns every violation of the arguments of a call against a tool schema
that ``check_schema`` already accepted. A ``Violation`` has the path of the field (``""`` for the
arguments as a whole) and a reason in Spanish that ends with a period and never reproduces a
received value. Violations come in a deterministic order: missing required fields (in the order of
``required``), then the declared fields that are present (in the order of ``properties``), then the
undeclared fields (in the order of the arguments).
"""

from __future__ import annotations

import copy
import time
from typing import Any

import pytest

from harness_agent.core.tools.errors import Violation
from harness_agent.core.tools.schema_validator import validate_arguments

SENTINEL = "SECRETO-123"
UNDECLARED = "campo no declarado en el esquema."


def check(schema: dict[str, Any], args: object) -> list[Violation]:
    """Validate and assert, on EVERY violation returned, that it is a clean sentence.

    Each message ends with a period, and neither the message nor the path contains the sentinel
    value that the tests hide in the offending values or in sibling fields.
    """
    violations = validate_arguments(schema, args)
    for violation in violations:
        assert violation.message.endswith("."), violation
        assert SENTINEL not in violation.message, violation
        assert SENTINEL not in violation.path, violation
    return violations


def obj(
    properties: dict[str, Any] | None = None,
    *,
    required: list[str] | None = None,
    additional: bool | None = None,
) -> dict[str, Any]:
    """Root object schema."""
    schema: dict[str, Any] = {"type": "object", "properties": properties or {}}
    if required is not None:
        schema["required"] = required
    if additional is not None:
        schema["additionalProperties"] = additional
    return schema


def field(declared: Any) -> dict[str, Any]:
    """Root schema with a single property ``campo`` of the given ``type``."""
    return obj({"campo": {"type": declared}})


# (type, a value of another type -- the sentinel is hidden in it when possible, expected reason)
WRONG_TYPE_CASES: list[tuple[str, Any, str]] = [
    ("string", [SENTINEL], "se esperaba una cadena de texto."),
    ("integer", SENTINEL, "se esperaba un entero."),
    ("number", SENTINEL, "se esperaba un número."),
    ("boolean", SENTINEL, "se esperaba un booleano."),
    ("array", SENTINEL, "se esperaba una lista."),
    ("object", SENTINEL, "se esperaba un objeto."),
    ("null", SENTINEL, "se esperaba nulo."),
]

RIGHT_TYPE_CASES: list[tuple[str, Any]] = [
    ("string", "texto"),
    ("integer", 3),
    ("number", 2.5),
    ("number", 3),
    ("boolean", False),
    ("array", [1, "a"]),
    ("object", {}),
    ("null", None),
]


class TestTiposYRequeridos:
    """Types, required fields, undeclared fields, nesting, ordering and general properties."""

    # --- Valid arguments -----------------------------------------------------------------

    def test_arguments_that_match_the_schema_are_valid(self) -> None:
        schema = obj(
            {
                "ruta": {"type": "string"},
                "limite": {"type": ["integer", "null"]},
                "opciones": obj({"tiempo_maximo": {"type": "number"}}, required=["tiempo_maximo"]),
            },
            required=["ruta"],
        )
        args = {"ruta": "a.txt", "limite": None, "opciones": {"tiempo_maximo": 2.5}}

        assert check(schema, args) == []

    def test_empty_arguments_are_valid_when_nothing_is_required(self) -> None:
        assert check(obj({"a": {"type": "string"}}), {}) == []

    # --- Required fields -----------------------------------------------------------------

    def test_missing_required_field_is_reported_with_the_contract_text(self) -> None:
        schema = obj({"ruta": {"type": "string"}}, required=["ruta"])

        assert check(schema, {}) == [Violation("ruta", "falta el campo requerido.")]

    def test_none_in_a_required_string_field_is_a_type_violation(self) -> None:
        schema = obj({"ruta": {"type": "string"}}, required=["ruta"])

        assert check(schema, {"ruta": None}) == [
            Violation("ruta", "se esperaba una cadena de texto.")
        ]

    def test_missing_required_fields_follow_the_order_of_required(self) -> None:
        properties = {name: {"type": "string"} for name in ("a", "b", "c")}
        schema = obj(properties, required=["c", "a", "b"])

        violations = check(schema, {})

        assert [violation.path for violation in violations] == ["c", "a", "b"]

    # --- Types ---------------------------------------------------------------------------

    @pytest.mark.parametrize("declared, value", RIGHT_TYPE_CASES)
    def test_values_of_the_declared_type_are_valid(self, declared: str, value: Any) -> None:
        assert check(field(declared), {"campo": value}) == []

    @pytest.mark.parametrize("declared, value, reason", WRONG_TYPE_CASES)
    def test_value_of_another_type_names_the_expected_type(
        self, declared: str, value: Any, reason: str
    ) -> None:
        assert check(field(declared), {"campo": value}) == [Violation("campo", reason)]

    @pytest.mark.parametrize("value", [True, False])
    @pytest.mark.parametrize(
        "declared, reason",
        [("integer", "se esperaba un entero."), ("number", "se esperaba un número.")],
    )
    def test_boolean_is_neither_integer_nor_number(
        self, declared: str, reason: str, value: bool
    ) -> None:
        assert check(field(declared), {"campo": value}) == [Violation("campo", reason)]

    @pytest.mark.parametrize("value", [3, -7, 0, 10**30, 3.0, 1e20])
    def test_integer_accepts_integers_and_integral_floats(self, value: float) -> None:
        assert check(field("integer"), {"campo": value}) == []

    @pytest.mark.parametrize("value", [3.5, "3", SENTINEL, [3], None])
    def test_integer_rejects_fractions_and_other_types(self, value: Any) -> None:
        assert check(field("integer"), {"campo": value}) == [
            Violation("campo", "se esperaba un entero.")
        ]

    @pytest.mark.parametrize("value", [0, 3, 2.5, -1e10, 10**30])
    def test_number_accepts_integers_and_finite_floats(self, value: float) -> None:
        assert check(field("number"), {"campo": value}) == []

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    @pytest.mark.parametrize(
        "declared, reason",
        [("integer", "se esperaba un entero."), ("number", "se esperaba un número.")],
    )
    def test_nan_and_infinities_are_rejected(
        self, declared: str, reason: str, value: float
    ) -> None:
        assert check(field(declared), {"campo": value}) == [Violation("campo", reason)]

    # --- Unions of types -----------------------------------------------------------------

    @pytest.mark.parametrize("value", [5, None])
    def test_union_accepts_any_of_its_types(self, value: Any) -> None:
        assert check(field(["integer", "null"]), {"campo": value}) == []

    def test_union_violation_lists_the_types(self) -> None:
        assert check(field(["integer", "null"]), {"campo": SENTINEL}) == [
            Violation("campo", "se esperaba uno de: entero, nulo.")
        ]

    def test_union_violation_keeps_the_declared_order(self) -> None:
        schema = field(["string", "integer", "null"])

        assert check(schema, {"campo": [SENTINEL]}) == [
            Violation("campo", "se esperaba uno de: cadena de texto, entero, nulo.")
        ]

    def test_boolean_is_not_accepted_by_a_numeric_union(self) -> None:
        assert check(field(["integer", "number"]), {"campo": True}) == [
            Violation("campo", "se esperaba uno de: entero, número.")
        ]

    # --- Arguments that are not an object ------------------------------------------------

    @pytest.mark.parametrize("args", [None, [], SENTINEL, 42, True, ()])
    def test_arguments_that_are_not_a_mapping_give_a_single_root_violation(
        self, args: object
    ) -> None:
        schema = obj({"a": {"type": "string"}}, required=["a"])

        assert check(schema, args) == [Violation("", "los argumentos deben ser un objeto.")]

    # --- A wrong type stops the evaluation of that field ---------------------------------

    def test_a_wrong_type_stops_the_evaluation_of_the_nested_object(self) -> None:
        nested = obj({"t": {"type": "integer"}}, required=["t"], additional=False)
        schema = obj({"opciones": nested})

        assert check(schema, {"opciones": SENTINEL}) == [
            Violation("opciones", "se esperaba un objeto.")
        ]

    def test_a_wrong_type_stops_the_evaluation_of_a_union_of_objects(self) -> None:
        nested = {"type": ["object", "null"], "required": ["t"], "properties": {"t": {}}}
        schema = obj({"opciones": nested})

        assert check(schema, {"opciones": SENTINEL}) == [
            Violation("opciones", "se esperaba uno de: objeto, nulo.")
        ]

    def test_a_mapping_in_a_text_field_is_one_type_violation_not_undeclared_fields(self) -> None:
        assert check(field("string"), {"campo": {"a": 1, "b": 2}}) == [
            Violation("campo", "se esperaba una cadena de texto.")
        ]

    # --- Undeclared fields ---------------------------------------------------------------

    def test_undeclared_field_is_rejected_by_default(self) -> None:
        schema = obj({"ruta": {"type": "string"}})

        assert check(schema, {"ruta": "a", "extra": 1}) == [Violation("extra", UNDECLARED)]

    def test_undeclared_field_is_rejected_when_additional_properties_is_false(self) -> None:
        schema = obj({"ruta": {"type": "string"}}, additional=False)

        assert check(schema, {"ruta": "a", "extra": 1}) == [Violation("extra", UNDECLARED)]

    def test_additional_properties_true_allows_undeclared_fields(self) -> None:
        schema = obj({"ruta": {"type": "string"}}, additional=True)

        assert check(schema, {"ruta": "a", "extra": SENTINEL, "otro": [1]}) == []

    def test_undeclared_field_in_a_nested_object_uses_the_full_path(self) -> None:
        schema = obj({"opciones": obj({"t": {"type": "integer"}})})

        assert check(schema, {"opciones": {"t": 1, "extra": 2}}) == [
            Violation("opciones.extra", UNDECLARED)
        ]

    def test_additional_properties_only_applies_to_its_own_object(self) -> None:
        schema = obj({"opciones": obj(additional=True)})

        assert check(schema, {"opciones": {"x": 1}, "otro": 2}) == [Violation("otro", UNDECLARED)]

    def test_tool_without_arguments_accepts_only_empty_arguments(self) -> None:
        schema: dict[str, Any] = {"type": "object"}

        assert check(schema, {}) == []
        assert check(schema, {"x": 1}) == [Violation("x", UNDECLARED)]

    def test_a_key_that_is_not_text_is_reported_without_crashing(self) -> None:
        assert check(obj(), {1: "x"}) == [Violation("1", UNDECLARED)]

    # --- Untyped sub-schemas -------------------------------------------------------------

    @pytest.mark.parametrize("value", [5, "texto", None, [1], True])
    def test_a_property_without_type_accepts_any_value_that_is_not_a_mapping(
        self, value: Any
    ) -> None:
        assert check(obj({"libre": {}}), {"libre": value}) == []

    def test_a_mapping_in_an_untyped_property_still_rejects_undeclared_fields(self) -> None:
        assert check(obj({"libre": {}}), {"libre": {"a": 1}}) == [Violation("libre.a", UNDECLARED)]

    def test_an_untyped_property_can_allow_any_mapping_explicitly(self) -> None:
        schema = obj({"libre": {"additionalProperties": True}})

        assert check(schema, {"libre": {"a": 1, "b": {"c": SENTINEL}}}) == []

    # --- Nested paths --------------------------------------------------------------------

    def test_nested_type_violation_uses_the_full_path(self) -> None:
        schema = obj({"opciones": obj({"tiempo_maximo": {"type": "number"}})})

        assert check(schema, {"opciones": {"tiempo_maximo": SENTINEL}}) == [
            Violation("opciones.tiempo_maximo", "se esperaba un número.")
        ]

    def test_missing_required_field_in_a_nested_object_uses_the_full_path(self) -> None:
        schema = obj({"opciones": obj({"t": {"type": "number"}}, required=["t"])})

        assert check(schema, {"opciones": {}}) == [
            Violation("opciones.t", "falta el campo requerido.")
        ]

    def test_three_levels_of_nesting_are_joined_with_dots(self) -> None:
        schema = obj({"a": obj({"b": obj({"c": {"type": "integer"}})})})

        assert check(schema, {"a": {"b": {"c": SENTINEL}}}) == [
            Violation("a.b.c", "se esperaba un entero.")
        ]

    # --- Order ---------------------------------------------------------------------------

    def test_violations_follow_missing_then_declared_then_undeclared(self) -> None:
        properties = {name: {"type": "integer"} for name in ("a", "b", "c", "d")}
        schema = obj(properties, required=["d", "b"])
        args = {"c": SENTINEL, "a": True, "zeta": 1, "alfa": 2}

        violations = check(schema, args)

        assert [violation.path for violation in violations] == ["d", "b", "a", "c", "zeta", "alfa"]
        assert [violation.message for violation in violations] == [
            "falta el campo requerido.",
            "falta el campo requerido.",
            "se esperaba un entero.",
            "se esperaba un entero.",
            UNDECLARED,
            UNDECLARED,
        ]

    def test_nested_violations_appear_at_the_position_of_their_field(self) -> None:
        inner = obj({"x": {"type": "integer"}}, required=["x"])
        schema = obj({"a": inner, "b": {"type": "integer"}})
        args = {"extra": 1, "b": SENTINEL, "a": {}}

        violations = check(schema, args)

        assert [violation.path for violation in violations] == ["a.x", "b", "extra"]

    # --- Several violations in one response ----------------------------------------------

    def test_every_violation_is_reported_in_a_single_response(self) -> None:
        schema = obj(
            {"a": {"type": "integer"}, "b": {"type": "string"}, "c": {"type": "boolean"}},
            required=["a", "b", "c"],
        )

        violations = check(schema, {"a": SENTINEL, "c": [SENTINEL], "d": 1})

        assert [(v.path, v.message) for v in violations] == [
            ("b", "falta el campo requerido."),
            ("a", "se esperaba un entero."),
            ("c", "se esperaba un booleano."),
            ("d", UNDECLARED),
        ]

    # --- General properties --------------------------------------------------------------

    def test_the_same_input_gives_exactly_the_same_result(self) -> None:
        schema = obj({"a": {"type": "integer"}}, required=["a", "b"])
        args = {"a": SENTINEL, "z": 1}

        assert check(schema, args) == check(schema, args)

    def test_neither_the_arguments_nor_the_schema_are_modified(self) -> None:
        nested = obj({"x": {"type": "string"}})
        schema = obj({"a": {"type": "integer"}, "o": nested}, required=["a"])
        args = {"a": SENTINEL, "o": {"x": 1, "y": [1, {"z": None}]}, "extra": {"k": 1}}
        schema_before, args_before = copy.deepcopy(schema), copy.deepcopy(args)

        assert check(schema, args)

        assert schema == schema_before
        assert args == args_before

    def test_received_values_never_appear_in_the_violations(self) -> None:
        nested = obj({"d": {"type": "integer"}})
        schema = obj(
            {"a": {"type": "integer"}, "b": {"type": "boolean"}, "c": nested},
            required=["a"],
        )
        args = {"a": SENTINEL, "b": [SENTINEL], "c": {"d": SENTINEL}, "extra": SENTINEL}

        violations = check(schema, args)  # `check` asserts the sentinel is nowhere

        assert [violation.path for violation in violations] == ["a", "b", "c.d", "extra"]

    # --- The descent follows the schema, never the arguments -----------------------------

    def test_deeply_nested_arguments_in_a_free_form_field_are_not_explored(self) -> None:
        deep: dict[str, Any] = {}
        cursor = deep
        for _ in range(5000):
            cursor["k"] = {}
            cursor = cursor["k"]
        schema = obj({"libre": {"type": "object", "additionalProperties": True}})

        assert check(schema, {"libre": deep}) == []

    def test_circular_arguments_in_a_free_form_field_do_not_loop(self) -> None:
        loop: dict[str, Any] = {}
        loop["self"] = loop
        schema = obj({"libre": {"type": "object", "additionalProperties": True}})

        assert check(schema, {"libre": loop}) == []

    def test_circular_arguments_are_a_plain_undeclared_field_when_not_allowed(self) -> None:
        loop: dict[str, Any] = {}
        loop["self"] = loop
        schema = obj({"libre": obj()})

        assert check(schema, {"libre": loop}) == [Violation("libre.self", UNDECLARED)]


# --- Part 2 (T012): enum, bounds and lists --------------------------------------------------------

ENUM_PREFIX = "valor no permitido; valores permitidos: "


def node(**keywords: Any) -> dict[str, Any]:
    """Root schema whose single property ``campo`` has the given keywords."""
    return obj({"campo": dict(keywords)})


def one(path: str, message: str) -> list[Violation]:
    return [Violation(path, message)]


def perf_schema() -> dict[str, Any]:
    """A schema with 20 fields of varied types and restrictions."""
    return obj(
        {
            "nombre": {"type": "string", "minLength": 1, "maxLength": 50},
            "descripcion": {"type": "string", "maxLength": 200},
            "ruta": {"type": "string", "minLength": 1},
            "modo": {"type": "string", "enum": ["lectura", "escritura", "anexar"]},
            "limite": {"type": "integer", "minimum": 1, "maximum": 1000},
            "desplazamiento": {"type": "integer", "minimum": 0},
            "tiempo": {"type": "number", "minimum": 0, "maximum": 3600.5},
            "ratio": {"type": "number", "minimum": 0, "maximum": 1},
            "activo": {"type": "boolean"},
            "recursivo": {"type": "boolean"},
            "etiquetas": {
                "type": "array",
                "items": {"type": "string", "maxLength": 20},
                "maxItems": 10,
            },
            "numeros": {
                "type": "array",
                "items": {"type": "integer", "minimum": 0},
                "maxItems": 50,
            },
            "opcional": {"type": ["string", "null"], "maxLength": 10},
            "prioridad": {"type": ["integer", "null"], "minimum": 0},
            "opciones": obj({"a": {"type": "integer"}, "b": {"type": "string"}}, required=["a"]),
            "archivos": {
                "type": "array",
                "items": obj(
                    {"ruta": {"type": "string"}, "tamano": {"type": "integer", "minimum": 0}},
                    required=["ruta"],
                ),
            },
            "formato": {"enum": ["json", "texto"]},
            "nivel": {"type": "integer", "enum": [1, 2, 3]},
            "version": {"type": "string", "minLength": 1, "maxLength": 20},
            "ayuda": {"type": "string"},
        },
        required=["nombre", "ruta"],
    )


def perf_args() -> dict[str, Any]:
    return {
        "nombre": "leer",
        "descripcion": "Lee un archivo del área autorizada.",
        "ruta": "src/main.py",
        "modo": "lectura",
        "limite": 100,
        "desplazamiento": 0,
        "tiempo": 12.5,
        "ratio": 0.25,
        "activo": True,
        "recursivo": False,
        "etiquetas": ["a", "b", "c", "d"],
        "numeros": [1, 2, 3, 4, 5, 6],
        "opcional": None,
        "prioridad": 3,
        "opciones": {"a": 1, "b": "x"},
        "archivos": [{"ruta": "a.txt", "tamano": 10}, {"ruta": "b.txt"}, {"ruta": "c.txt"}],
        "formato": "json",
        "nivel": 2,
        "version": "1.0.0",
        "ayuda": "Texto de ayuda.",
    }


class TestRestriccionesYListas:
    """enum, numeric bounds, length and item-count bounds, items, order and performance."""

    # --- enum ----------------------------------------------------------------------------

    @pytest.mark.parametrize(
        "allowed, value",
        [
            (["lectura", "escritura"], "lectura"),
            ([1, 2, 3], 2),
            ([1, 2, 3], 2.0),
            ([None, "x"], None),
            ([True], True),
            ([False, 0.5], False),
            ([[1, 2], [3]], [3]),
            ([[True, [1, {"k": None}]]], [True, [1, {"k": None}]]),
        ],
    )
    def test_values_in_the_enum_are_valid(self, allowed: list[Any], value: Any) -> None:
        # Not a mapping value: a mapping in an untyped node is validated as an object (see below).
        assert check(node(enum=allowed), {"campo": value}) == []

    def test_a_mapping_in_the_enum_is_valid_when_the_node_allows_its_fields(self) -> None:
        schema = node(enum=[{"a": 1}, {"b": [True]}], additionalProperties=True)

        assert check(schema, {"campo": {"b": [True]}}) == []

    def test_value_outside_the_enum_lists_the_allowed_values_of_the_schema(self) -> None:
        schema = node(enum=["lectura", "escritura"])

        assert check(schema, {"campo": SENTINEL}) == one(
            "campo", ENUM_PREFIX + '"lectura", "escritura".'
        )

    def test_a_list_holding_the_sentinel_is_outside_the_enum_without_echoing_it(self) -> None:
        schema = node(enum=["lectura"])

        assert check(schema, {"campo": [SENTINEL]}) == one("campo", ENUM_PREFIX + '"lectura".')

    def test_allowed_values_are_shown_as_json_in_the_order_of_the_schema(self) -> None:
        allowed = ["b", "a", 1, 2.5, None, True, [1, "x"], {"k": 1}, "café"]
        schema = node(enum=allowed, additionalProperties=True)

        expected = ENUM_PREFIX + '"b", "a", 1, 2.5, null, true, [1, "x"], {"k": 1}, "café".'
        assert check(schema, {"campo": SENTINEL}) == one("campo", expected)

    def test_the_message_is_identical_for_any_rejected_value(self) -> None:
        schema = node(enum=["a", "b"])

        first = check(schema, {"campo": "uno"})
        second = check(schema, {"campo": [SENTINEL, 2, None]})

        assert [violation.path for violation in first] == ["campo"]
        assert [violation.message for violation in first] == [
            violation.message for violation in second
        ]

    @pytest.mark.parametrize(
        "allowed, value",
        [([1], True), ([0], False), ([True], 1), ([False], 0), ([1.0], True), ([True], 1.0)],
    )
    def test_true_is_not_one_and_false_is_not_zero(self, allowed: list[Any], value: Any) -> None:
        violations = check(node(enum=allowed), {"campo": value})

        assert [violation.path for violation in violations] == ["campo"]
        assert violations[0].message.startswith(ENUM_PREFIX)

    @pytest.mark.parametrize(
        "allowed, value",
        [
            ([[1]], [True]),
            ([[True]], [1]),
            ([[0, 1]], [False, True]),
            ([[1, [2]]], [1, [True]]),
            ([[1, [True]]], [1, [2]]),
        ],
    )
    def test_bool_and_number_stay_different_inside_nested_lists(
        self, allowed: list[Any], value: Any
    ) -> None:
        violations = check(node(enum=allowed), {"campo": value})

        assert [violation.path for violation in violations] == ["campo"]
        assert violations[0].message.startswith(ENUM_PREFIX)

    @pytest.mark.parametrize(
        "allowed, value",
        [
            ({"a": 1}, {"a": True}),
            ({"a": True}, {"a": 1}),
            ({"a": [1, {"b": False}]}, {"a": [1, {"b": 0}]}),
        ],
    )
    def test_bool_and_number_stay_different_inside_nested_mappings(
        self, allowed: dict[str, Any], value: dict[str, Any]
    ) -> None:
        schema = node(enum=[allowed], additionalProperties=True)

        violations = check(schema, {"campo": value})

        assert [violation.path for violation in violations] == ["campo"]
        assert violations[0].message.startswith(ENUM_PREFIX)

    def test_a_wrong_type_is_the_only_violation_even_when_the_enum_also_fails(self) -> None:
        schema = node(type="string", enum=["a"])

        assert check(schema, {"campo": 5}) == one("campo", "se esperaba una cadena de texto.")

    # --- enum: cap on the values shown (adjustment of T015) -------------------------------

    def test_ten_allowed_values_are_all_shown_without_a_suffix(self) -> None:
        violations = check(node(enum=list(range(10))), {"campo": SENTINEL})

        assert violations == one("campo", ENUM_PREFIX + "0, 1, 2, 3, 4, 5, 6, 7, 8, 9.")

    def test_eleven_values_show_the_first_ten_of_the_schema_and_count_one_more(self) -> None:
        allowed = list(range(20, 9, -1))  # 20, 19, ..., 10: the first ten, not the smallest ten

        violations = check(node(enum=allowed), {"campo": SENTINEL})

        expected = ENUM_PREFIX + "20, 19, 18, 17, 16, 15, 14, 13, 12, 11, … y 1 más."
        assert violations == one("campo", expected)

    def test_the_suffix_counts_every_value_that_is_not_shown(self) -> None:
        allowed = [f"v{number}" for number in range(1000)]

        violations = check(node(enum=allowed), {"campo": SENTINEL})

        shown = ", ".join(f'"v{number}"' for number in range(10))
        assert violations == one("campo", f"{ENUM_PREFIX}{shown}, … y 990 más.")

    def test_a_value_that_is_not_shown_never_appears_in_the_message(self) -> None:
        allowed = [*range(10), "oculto"]

        violations = check(node(enum=allowed), {"campo": SENTINEL})

        assert "oculto" not in violations[0].message

    @pytest.mark.parametrize(
        "text_length, expected",
        [
            (40, '"' + "x" * 38 + '"'),  # exactly 40 characters: shown as it is
            (41, '"' + "x" * 38 + "…"),  # 41 characters: 39 of them and the ellipsis, 40 in all
            (102, '"' + "x" * 38 + "…"),
        ],
    )
    def test_a_long_value_is_clipped_to_forty_characters_counting_the_ellipsis(
        self, text_length: int, expected: str
    ) -> None:
        long_value = "x" * (text_length - 2)  # the two quotes of the JSON text make up the rest
        schema = node(enum=[long_value, "b"])

        violations = check(schema, {"campo": SENTINEL})

        assert violations == one("campo", f'{ENUM_PREFIX}{expected}, "b".')
        assert len(expected) == 40

    def test_a_long_list_in_the_enum_is_clipped_like_any_other_value(self) -> None:
        schema = node(enum=[list(range(30)), 1], additionalProperties=True)

        violations = check(schema, {"campo": SENTINEL})

        clipped = "[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, …"  # 39 characters and the ellipsis
        assert violations == one("campo", f"{ENUM_PREFIX}{clipped}, 1.")
        assert len(clipped) == 40

    def test_the_clip_and_the_cap_apply_together_and_the_message_ends_with_a_period(self) -> None:
        allowed = ["y" * 60 for _ in range(15)]
        clipped = '"' + "y" * 38 + "…"

        violations = check(node(enum=allowed), {"campo": [SENTINEL]})

        expected = ", ".join([clipped] * 10)
        assert violations == one("campo", f"{ENUM_PREFIX}{expected}, … y 5 más.")

    # --- minimum / maximum ---------------------------------------------------------------

    @pytest.mark.parametrize("value", [1, 1.0, 5, 10, 10.0, 2.5])
    def test_values_within_the_inclusive_bounds_are_valid(self, value: float) -> None:
        assert check(node(minimum=1, maximum=10), {"campo": value}) == []

    @pytest.mark.parametrize("value", [0, 0.999, -5, -(10**30)])
    def test_a_value_below_the_minimum_is_rejected(self, value: float) -> None:
        assert check(node(minimum=1, maximum=10), {"campo": value}) == one(
            "campo", "debe ser mayor o igual que 1."
        )

    @pytest.mark.parametrize("value", [10.001, 11, 10**30])
    def test_a_value_above_the_maximum_is_rejected(self, value: float) -> None:
        assert check(node(minimum=1, maximum=10), {"campo": value}) == one(
            "campo", "debe ser menor o igual que 10."
        )

    def test_the_bound_is_shown_as_written_in_the_schema(self) -> None:
        schema = node(minimum=2.5, maximum=3.5)

        assert check(schema, {"campo": 2}) == one("campo", "debe ser mayor o igual que 2.5.")
        assert check(schema, {"campo": 4}) == one("campo", "debe ser menor o igual que 3.5.")

    def test_bounds_apply_to_typed_integers_and_numbers_too(self) -> None:
        assert check(node(type="integer", minimum=1), {"campo": 0}) == one(
            "campo", "debe ser mayor o igual que 1."
        )
        assert check(node(type="number", maximum=1), {"campo": 1.5}) == one(
            "campo", "debe ser menor o igual que 1."
        )

    def test_a_wrong_type_is_the_only_violation_even_when_bounds_are_declared(self) -> None:
        schema = node(type="integer", minimum=1, maximum=10)

        assert check(schema, {"campo": SENTINEL}) == one("campo", "se esperaba un entero.")

    @pytest.mark.parametrize("value", [True, False])
    @pytest.mark.parametrize("keywords", [{"minimum": 5}, {"maximum": -1}, {"minimum": 0}])
    def test_a_boolean_never_counts_as_a_number(
        self, keywords: dict[str, Any], value: bool
    ) -> None:
        assert check(node(**keywords), {"campo": value}) == []

    @pytest.mark.parametrize("value", ["x", [1], None])
    def test_numeric_bounds_are_not_evaluated_on_values_that_are_not_numbers(
        self, value: Any
    ) -> None:
        assert check(node(minimum=5, maximum=6), {"campo": value}) == []

    @pytest.mark.parametrize(
        "keywords, value, reason",
        [
            ({"minimum": 1}, float("nan"), "debe ser mayor o igual que 1."),
            ({"maximum": 1}, float("nan"), "debe ser menor o igual que 1."),
            ({"maximum": 1}, float("inf"), "debe ser menor o igual que 1."),
            ({"minimum": 1}, float("-inf"), "debe ser mayor o igual que 1."),
        ],
    )
    def test_nan_and_infinities_cannot_slip_through_the_bounds_of_an_untyped_node(
        self, keywords: dict[str, Any], value: float, reason: str
    ) -> None:
        assert check(node(**keywords), {"campo": value}) == one("campo", reason)

    @pytest.mark.parametrize(
        "keywords, value",
        [({"minimum": 1}, float("inf")), ({"maximum": 1}, float("-inf"))],
    )
    def test_an_infinity_on_the_allowed_side_of_a_bound_is_valid_when_untyped(
        self, keywords: dict[str, Any], value: float
    ) -> None:
        assert check(node(**keywords), {"campo": value}) == []

    def test_huge_integers_are_compared_exactly(self) -> None:
        schema = node(type="integer", minimum=10**30, maximum=10**30 + 2)

        assert check(schema, {"campo": 10**30 + 2}) == []
        assert check(schema, {"campo": 10**30 + 3}) == one(
            "campo", f"debe ser menor o igual que {10**30 + 2}."
        )

    def test_a_union_with_null_skips_the_bounds_for_null(self) -> None:
        schema = node(type=["integer", "null"], minimum=1)

        assert check(schema, {"campo": None}) == []
        assert check(schema, {"campo": 5}) == []
        assert check(schema, {"campo": 0}) == one("campo", "debe ser mayor o igual que 1.")

    def test_numeric_violations_do_not_leak_the_values_of_sibling_fields(self) -> None:
        schema = obj({"campo": {"minimum": 1}, "etiqueta": {"type": "string"}})

        violations = check(schema, {"campo": 0, "etiqueta": SENTINEL})

        assert violations == one("campo", "debe ser mayor o igual que 1.")

    # --- minLength / maxLength -----------------------------------------------------------

    @pytest.mark.parametrize("value", ["abc", "abcde", "áéíóú", "😀😀😀"])
    def test_strings_within_the_inclusive_length_bounds_are_valid(self, value: str) -> None:
        assert check(node(type="string", minLength=3, maxLength=5), {"campo": value}) == []

    @pytest.mark.parametrize("value", ["", "ab", "😀😀"])
    def test_a_string_that_is_too_short_is_rejected_counting_characters(self, value: str) -> None:
        schema = node(type="string", minLength=3, maxLength=5)

        assert check(schema, {"campo": value}) == one("campo", "debe tener al menos 3 caracteres.")

    @pytest.mark.parametrize("value", ["abcdef", SENTINEL])
    def test_a_string_that_is_too_long_is_rejected_without_echoing_it(self, value: str) -> None:
        schema = node(type="string", minLength=3, maxLength=5)

        assert check(schema, {"campo": value}) == one(
            "campo", "debe tener como máximo 5 caracteres."
        )

    def test_a_string_shorter_than_the_minimum_does_not_echo_the_sentinel(self) -> None:
        schema = node(type="string", minLength=50)

        assert check(schema, {"campo": SENTINEL}) == one(
            "campo", "debe tener al menos 50 caracteres."
        )

    def test_the_singular_form_is_used_for_one_character(self) -> None:
        assert check(node(minLength=1), {"campo": ""}) == one(
            "campo", "debe tener al menos 1 carácter."
        )
        assert check(node(maxLength=1), {"campo": "ab"}) == one(
            "campo", "debe tener como máximo 1 carácter."
        )

    def test_zero_is_plural(self) -> None:
        assert check(node(maxLength=0), {"campo": "a"}) == one(
            "campo", "debe tener como máximo 0 caracteres."
        )

    @pytest.mark.parametrize("value", [12345, [1], None, True])
    def test_length_bounds_are_not_evaluated_on_values_that_are_not_strings(
        self, value: Any
    ) -> None:
        assert check(node(minLength=10, maxLength=2), {"campo": value}) == []

    def test_a_wrong_type_is_the_only_violation_even_when_length_bounds_are_declared(
        self,
    ) -> None:
        schema = node(type="string", minLength=50)

        assert check(schema, {"campo": [SENTINEL]}) == one(
            "campo", "se esperaba una cadena de texto."
        )

    # --- minItems / maxItems -------------------------------------------------------------

    @pytest.mark.parametrize("value", [[1, 2], [1, 2, 3]])
    def test_lists_within_the_inclusive_item_bounds_are_valid(self, value: list[int]) -> None:
        assert check(node(type="array", minItems=2, maxItems=3), {"campo": value}) == []

    @pytest.mark.parametrize("value", [[], [SENTINEL]])
    def test_a_list_with_too_few_items_is_rejected(self, value: list[str]) -> None:
        schema = node(type="array", minItems=2, maxItems=3)

        assert check(schema, {"campo": value}) == one("campo", "debe tener al menos 2 elementos.")

    def test_a_list_with_too_many_items_is_rejected_without_echoing_them(self) -> None:
        schema = node(type="array", minItems=2, maxItems=3)

        assert check(schema, {"campo": [SENTINEL] * 4}) == one(
            "campo", "debe tener como máximo 3 elementos."
        )

    def test_the_singular_form_is_used_for_one_item(self) -> None:
        assert check(node(minItems=1), {"campo": []}) == one(
            "campo", "debe tener al menos 1 elemento."
        )
        assert check(node(maxItems=1), {"campo": [1, 2]}) == one(
            "campo", "debe tener como máximo 1 elemento."
        )

    def test_zero_items_is_plural(self) -> None:
        assert check(node(maxItems=0), {"campo": [1]}) == one(
            "campo", "debe tener como máximo 0 elementos."
        )

    @pytest.mark.parametrize("value", ["abc", 12345, None, True])
    def test_item_bounds_are_not_evaluated_on_values_that_are_not_lists(self, value: Any) -> None:
        assert check(node(minItems=5, maxItems=1), {"campo": value}) == []

    # --- items ---------------------------------------------------------------------------

    @pytest.mark.parametrize("value", [[], ["a"], ["a", "b", "c"]])
    def test_every_item_matching_the_item_schema_is_valid(self, value: list[str]) -> None:
        schema = node(type="array", items={"type": "string"})

        assert check(schema, {"campo": value}) == []

    def test_a_list_without_an_item_schema_accepts_any_items(self) -> None:
        assert check(node(type="array"), {"campo": [1, "a", None, [2]]}) == []

    def test_an_invalid_item_is_reported_with_its_index_in_the_path(self) -> None:
        schema = node(type="array", items={"type": "string"})

        assert check(schema, {"campo": ["a", "b", 5]}) == one(
            "campo[2]", "se esperaba una cadena de texto."
        )

    def test_the_sentinel_inside_an_invalid_item_is_not_echoed(self) -> None:
        schema = node(type="array", items={"type": "integer"})

        assert check(schema, {"campo": [1, SENTINEL]}) == one("campo[1]", "se esperaba un entero.")

    def test_a_field_of_an_item_uses_the_index_and_the_field_name(self) -> None:
        archivos = {"type": "array", "items": obj({"ruta": {"type": "string"}}, required=["ruta"])}
        schema = obj({"archivos": archivos})
        args = {"archivos": [{"ruta": "a"}, {"ruta": "b"}, {}]}

        assert check(schema, args) == one("archivos[2].ruta", "falta el campo requerido.")

    def test_a_wrong_type_and_an_undeclared_field_inside_items_use_the_full_path(self) -> None:
        archivos = {"type": "array", "items": obj({"ruta": {"type": "string"}})}
        schema = obj({"archivos": archivos})
        args = {"archivos": [{"ruta": SENTINEL}, {"ruta": 5, "extra": 1}]}

        assert check(schema, args) == [
            Violation("archivos[1].ruta", "se esperaba una cadena de texto."),
            Violation("archivos[1].extra", UNDECLARED),
        ]

    def test_nested_lists_chain_their_indexes(self) -> None:
        inner = {"type": "array", "items": {"type": "integer"}}
        schema = obj({"matriz": {"type": "array", "items": inner}})

        assert check(schema, {"matriz": [[1, 2], [3, "x"]]}) == one(
            "matriz[1][1]", "se esperaba un entero."
        )

    def test_items_are_visited_by_index_in_order(self) -> None:
        schema = node(type="array", items={"type": "integer"})

        violations = check(schema, {"campo": ["a", 1, 2, "b", 3, "c"]})

        assert [violation.path for violation in violations] == ["campo[0]", "campo[3]", "campo[5]"]

    def test_every_violation_is_returned_without_the_cap_of_the_error_text(self) -> None:
        schema = node(type="array", items={"type": "integer"})

        violations = check(schema, {"campo": [SENTINEL] * 30})

        assert len(violations) == 30
        assert [violation.path for violation in violations] == [f"campo[{i}]" for i in range(30)]

    def test_item_count_violations_come_before_the_violations_of_the_items(self) -> None:
        schema = node(type="array", items={"type": "integer"}, minItems=3)

        assert check(schema, {"campo": [SENTINEL]}) == [
            Violation("campo", "debe tener al menos 3 elementos."),
            Violation("campo[0]", "se esperaba un entero."),
        ]

    def test_the_restrictions_of_the_item_schema_apply_to_each_item(self) -> None:
        schema = node(type="array", items={"type": "integer", "minimum": 0})

        assert check(schema, {"campo": [1, -1, 2]}) == one(
            "campo[1]", "debe ser mayor o igual que 0."
        )

    def test_enum_inside_items_reports_the_index(self) -> None:
        schema = node(type="array", items={"enum": ["r", "w"]})

        assert check(schema, {"campo": ["r", SENTINEL]}) == one(
            "campo[1]", ENUM_PREFIX + '"r", "w".'
        )

    def test_the_item_schema_is_ignored_for_a_value_that_is_not_a_list(self) -> None:
        assert check(node(items={"type": "integer"}), {"campo": "abc"}) == []

    # --- Order and general properties ----------------------------------------------------

    def test_the_restrictions_of_one_field_come_in_a_fixed_order(self) -> None:
        schema = node(type="integer", enum=[1, 2], minimum=2)

        assert check(schema, {"campo": 0}) == [
            Violation("campo", ENUM_PREFIX + "1, 2."),
            Violation("campo", "debe ser mayor o igual que 2."),
        ]

    def test_the_same_input_gives_exactly_the_same_result(self) -> None:
        schema = obj(
            {
                "a": {"enum": ["x", "y"]},
                "b": {"type": "array", "items": {"type": "integer", "minimum": 1}, "maxItems": 2},
            }
        )
        args = {"a": SENTINEL, "b": [0, SENTINEL, 3]}

        assert check(schema, args) == check(schema, args)

    def test_neither_the_arguments_nor_the_schema_are_modified(self) -> None:
        schema = obj(
            {
                "a": {"enum": ["x", {"k": [True]}], "additionalProperties": True},
                "b": {"type": "array", "items": {"type": "string", "maxLength": 2}},
            }
        )
        args = {"a": {"k": [1]}, "b": ["abc", SENTINEL, 5]}
        schema_before, args_before = copy.deepcopy(schema), copy.deepcopy(args)

        assert check(schema, args)

        assert schema == schema_before
        assert args == args_before

    # --- Performance ---------------------------------------------------------------------

    def test_validation_stays_well_under_ten_milliseconds_on_average(self) -> None:
        schema, args = perf_schema(), perf_args()
        assert validate_arguments(schema, args) == []  # warm-up run; also proves the case is valid

        runs = 200
        start = time.perf_counter()
        for _ in range(runs):
            validate_arguments(schema, args)
        average = (time.perf_counter() - start) / runs

        assert average < 0.010, f"{average * 1000:.3f} ms per validation"
