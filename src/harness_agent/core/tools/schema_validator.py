"""Minimal JSON Schema support for the argument schemas of tools (HU-01-02).

``check_schema`` validates the *definition* of a schema when a tool is registered. It accepts
only the subset of JSON Schema that the argument validator understands and rejects every other
keyword by name, so that a restriction is never silently ignored (fail closed).

``validate_arguments`` validates the *arguments* of a call against a schema that ``check_schema``
already accepted.

Standard library only.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from typing import Any

from harness_agent.core.tools.errors import Violation, clip

MAX_SCHEMA_DEPTH = 32
MAX_ENUM_VALUES_SHOWN = 10
MAX_ENUM_VALUE_DISPLAY = 40

_SchemaPath = tuple[str, ...]
_ArgPath = tuple[str | int, ...]

_ROOT_PLACE = "(raíz)"

_TYPE_NAMES = ("string", "integer", "number", "boolean", "array", "object", "null")

_VALIDATION_KEYWORDS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "enum",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "items",
        "minItems",
        "maxItems",
    }
)
_ANNOTATION_KEYWORDS = frozenset(
    {"description", "title", "default", "examples", "$comment", "$schema"}
)
_SUPPORTED_KEYWORDS = _VALIDATION_KEYWORDS | _ANNOTATION_KEYWORDS

_ROOT_TYPE_TEXT = "la raíz debe declarar 'type': 'object'."
_UNKNOWN_TYPE_TEXT = f"el tipo no es uno de los soportados: {', '.join(_TYPE_NAMES)}."
_BAD_TYPE_TEXT = "debe ser el nombre de un tipo o una lista de nombres de tipo."
_DUPLICATED_TYPES_TEXT = "la lista de tipos no puede tener elementos repetidos."
_BAD_PROPERTIES_TEXT = "debe ser un objeto que asigna a cada campo su subesquema."
_FINITE_NUMBER_TEXT = "debe ser un número finito."
_NON_NEGATIVE_INT_TEXT = "debe ser un entero no negativo."
_ITEMS_LIST_TEXT = "la forma de lista de esquemas no está soportada; use un único subesquema."
_DEPTH_TEXT = f"se supera la profundidad máxima de {MAX_SCHEMA_DEPTH} niveles de anidamiento."

# How a declared type is shown after "se esperaba": alone it takes an article ("un entero"); in a
# union only the bare labels are listed ("uno de: entero, nulo").
_TYPE_ARTICLES = {
    "string": "una cadena de texto",
    "integer": "un entero",
    "number": "un número",
    "boolean": "un booleano",
    "array": "una lista",
    "object": "un objeto",
    "null": "nulo",
}
_TYPE_LABELS = {
    "string": "cadena de texto",
    "integer": "entero",
    "number": "número",
    "boolean": "booleano",
    "array": "lista",
    "object": "objeto",
    "null": "nulo",
}
_NOT_AN_OBJECT_TEXT = "los argumentos deben ser un objeto."
_MISSING_FIELD_TEXT = "falta el campo requerido."
_UNDECLARED_FIELD_TEXT = "campo no declarado en el esquema."

_LENGTH_KEYWORDS = ("minLength", "maxLength")
_ITEM_COUNT_KEYWORDS = ("minItems", "maxItems")
_CHARACTERS = ("carácter", "caracteres")  # (singular, plural)
_ITEMS = ("elemento", "elementos")


def check_schema(schema: object) -> list[str]:
    """Return the problems of a tool argument schema; an empty list means it is valid.

    Every problem is a complete Spanish sentence that ends with a period and starts with the
    place inside the schema: ``(raíz)`` for the root schema, the path of the schema
    (``properties.limite``) for a defect of the schema itself such as an unsupported keyword,
    or the path of the keyword (``properties.limite.minimum``) for an invalid keyword value.
    Problems never reproduce values. The registry prepends ``esquema `` to them, so this
    function does not.

    Nesting deeper than ``MAX_SCHEMA_DEPTH`` levels (the root is level 1) is reported once, at
    the first schema that exceeds it, and is not explored any further. That also stops circular
    schemas.
    """
    problems: list[str] = []
    _check_node(schema, (), 1, problems)
    return problems


def _problem(path: _SchemaPath, text: str) -> str:
    place = ".".join(path) if path else _ROOT_PLACE
    return f"{place}: {text}"


def _check_node(node: object, path: _SchemaPath, depth: int, problems: list[str]) -> None:
    if depth > MAX_SCHEMA_DEPTH:
        problems.append(_problem(path, _DEPTH_TEXT))
        return
    if not isinstance(node, dict):
        problems.append(_problem(path, "el esquema debe ser un objeto."))
        return
    for keyword in node:
        if keyword not in _SUPPORTED_KEYWORDS:
            problems.append(_problem(path, f"palabra clave no soportada '{keyword}'."))
    _check_type(node, path, problems)
    _check_properties(node, path, depth, problems)
    _check_required(node, path, problems)
    _check_additional_properties(node, path, problems)
    _check_enum(node, path, problems)
    _check_bounds(node, path, problems)
    _check_items(node, path, depth, problems)


def _check_type(node: dict[Any, Any], path: _SchemaPath, problems: list[str]) -> None:
    if "type" not in node:
        if not path:
            problems.append(_problem(path, _ROOT_TYPE_TEXT))
        return
    declared = node["type"]
    if not _check_type_declaration(declared, (*path, "type"), problems):
        return
    if not path and declared != "object":
        problems.append(_problem(path, _ROOT_TYPE_TEXT))


def _check_type_declaration(declared: object, place: _SchemaPath, problems: list[str]) -> bool:
    """Report what is wrong with a ``type`` value and say whether it is well formed."""
    if isinstance(declared, str):
        if declared in _TYPE_NAMES:
            return True
        problems.append(_problem(place, _UNKNOWN_TYPE_TEXT))
        return False
    if isinstance(declared, list):
        if not declared:
            problems.append(_problem(place, "la lista de tipos no puede estar vacía."))
            return False
        valid = True
        names = [name for name in declared if isinstance(name, str) and name in _TYPE_NAMES]
        if len(names) != len(declared):
            problems.append(_problem(place, _UNKNOWN_TYPE_TEXT))
            valid = False
        if len(set(names)) != len(names):
            problems.append(_problem(place, _DUPLICATED_TYPES_TEXT))
            valid = False
        return valid
    problems.append(_problem(place, _BAD_TYPE_TEXT))
    return False


def _check_properties(
    node: dict[Any, Any], path: _SchemaPath, depth: int, problems: list[str]
) -> None:
    if "properties" not in node:
        return
    place = (*path, "properties")
    properties = node["properties"]
    if not isinstance(properties, dict):
        problems.append(_problem(place, _BAD_PROPERTIES_TEXT))
        return
    for name, subschema in properties.items():
        _check_node(subschema, (*place, str(name)), depth + 1, problems)


def _check_required(node: dict[Any, Any], path: _SchemaPath, problems: list[str]) -> None:
    if "required" not in node:
        return
    place = (*path, "required")
    required = node["required"]
    if not isinstance(required, list):
        problems.append(_problem(place, "debe ser una lista de nombres de campo."))
        return
    names = [name for name in required if isinstance(name, str)]
    if len(names) != len(required):
        problems.append(_problem(place, "debe contener solo nombres de campo (texto)."))
    if len(set(names)) != len(names):
        problems.append(_problem(place, "no puede tener nombres repetidos."))
    properties = node.get("properties", {})
    if not isinstance(properties, dict):
        return  # Already reported; do not add noise about which fields are declared.
    for name in dict.fromkeys(names):
        if name not in properties:
            text = f"el campo '{name}' es requerido pero no está declarado en properties."
            problems.append(_problem(place, text))


def _check_additional_properties(
    node: dict[Any, Any], path: _SchemaPath, problems: list[str]
) -> None:
    if "additionalProperties" in node and not isinstance(node["additionalProperties"], bool):
        problems.append(
            _problem(
                (*path, "additionalProperties"),
                "debe ser true o false; un subesquema no está soportado.",
            )
        )


def _check_enum(node: dict[Any, Any], path: _SchemaPath, problems: list[str]) -> None:
    if "enum" not in node:
        return
    place = (*path, "enum")
    values = node["enum"]
    if not isinstance(values, list):
        problems.append(_problem(place, "debe ser una lista de valores permitidos."))
    elif not values:
        problems.append(_problem(place, "no puede estar vacía."))


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True  # An integer is always finite; math.isfinite overflows on huge ones.
    return isinstance(value, float) and math.isfinite(value)


def _is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _check_bounds(node: dict[Any, Any], path: _SchemaPath, problems: list[str]) -> None:
    _check_bound_pair(
        node, path, problems, ("minimum", "maximum"), _is_finite_number, _FINITE_NUMBER_TEXT
    )
    for pair in (("minLength", "maxLength"), ("minItems", "maxItems")):
        _check_bound_pair(node, path, problems, pair, _is_non_negative_int, _NON_NEGATIVE_INT_TEXT)


def _check_bound_pair(
    node: dict[Any, Any],
    path: _SchemaPath,
    problems: list[str],
    pair: tuple[str, str],
    is_valid: Callable[[object], bool],
    requirement: str,
) -> None:
    """Check a ``(minimum keyword, maximum keyword)`` pair: each value, then their order."""
    low, high = pair
    valid: dict[str, Any] = {}
    for keyword in pair:
        if keyword not in node:
            continue
        if is_valid(node[keyword]):
            valid[keyword] = node[keyword]
        else:
            problems.append(_problem((*path, keyword), requirement))
    if low in valid and high in valid and valid[low] > valid[high]:
        problems.append(_problem((*path, low), f"no puede ser mayor que {high}."))


def _check_items(node: dict[Any, Any], path: _SchemaPath, depth: int, problems: list[str]) -> None:
    if "items" not in node:
        return
    place = (*path, "items")
    items = node["items"]
    if isinstance(items, list):
        problems.append(_problem(place, _ITEMS_LIST_TEXT))
        return
    _check_node(items, place, depth + 1, problems)


def validate_arguments(schema: dict[str, Any], args: object) -> list[Violation]:
    """Return every violation of ``args`` against ``schema``; an empty list means they comply.

    ``schema`` must already have been accepted by ``check_schema``. The walk follows the structure
    of the schema (at most ``MAX_SCHEMA_DEPTH`` levels), never that of the arguments, so deeply
    nested or circular arguments cannot make it recurse. ``args`` is only read, never modified, and
    the same input always gives the same result.

    Violations come in a deterministic order: in each object, first the missing required fields
    (in the order of ``required``), then the declared fields that are present (in the order of
    ``properties``, each followed by its own nested violations), then the undeclared fields (in
    the order of the arguments). A field of the wrong type gets one violation and none of its other
    restrictions are evaluated. Otherwise a field is checked against ``enum`` first and then against
    the restrictions of its kind of value: ``minimum`` and ``maximum`` for numbers (never for a
    boolean), ``minLength`` and ``maxLength`` for strings, ``minItems`` and ``maxItems`` for lists
    followed by each item in index order. Every violation is returned: the cap on what the error
    text shows is applied later, by the error. Reasons never reproduce received values; the allowed
    values of an ``enum`` shown in a reason come from the schema.
    """
    if not isinstance(args, dict):
        return [Violation("", _NOT_AN_OBJECT_TEXT)]
    violations: list[Violation] = []
    _validate_value(args, schema, (), violations)
    return violations


def _path_text(path: _ArgPath) -> str:
    """Join the path of a field: ``a.b``; a list position is written in brackets: ``a[2].b``."""
    text = ""
    for segment in path:
        if isinstance(segment, int):
            text += f"[{segment}]"
        else:
            text += f".{segment}" if text else segment
    return text


def _validate_value(
    value: object, node: dict[str, Any], path: _ArgPath, violations: list[Violation]
) -> None:
    declared = node.get("type")
    if declared is not None and not _matches_declared_type(value, declared):
        violations.append(Violation(_path_text(path), f"se esperaba {_expected_text(declared)}."))
        return
    _check_allowed_values(value, node, path, violations)
    if isinstance(value, str):
        _check_count(len(value), node, path, violations, _LENGTH_KEYWORDS, _CHARACTERS)
    elif isinstance(value, list):
        _check_count(len(value), node, path, violations, _ITEM_COUNT_KEYWORDS, _ITEMS)
        _validate_items(value, node, path, violations)
    elif isinstance(value, dict):
        _validate_object(value, node, path, violations)
    else:
        _check_numeric_bounds(value, node, path, violations)


def _check_allowed_values(
    value: object, node: dict[str, Any], path: _ArgPath, violations: list[Violation]
) -> None:
    allowed = node.get("enum")
    if allowed is None or any(_json_equal(value, candidate) for candidate in allowed):
        return
    text = f"valor no permitido; valores permitidos: {_allowed_values_text(allowed)}."
    violations.append(Violation(_path_text(path), text))


def _allowed_values_text(allowed: list[Any]) -> str:
    """The first allowed values of the schema, each clipped, and a count of the rest."""
    shown = ", ".join(
        clip(_json_text(candidate), MAX_ENUM_VALUE_DISPLAY)
        for candidate in allowed[:MAX_ENUM_VALUES_SHOWN]
    )
    hidden = len(allowed) - MAX_ENUM_VALUES_SHOWN
    return f"{shown}, … y {hidden} más" if hidden > 0 else shown


def _json_equal(left: object, right: object) -> bool:
    """JSON equality: like ``==``, but a boolean is never equal to a number at any nesting level."""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _json_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return bool(left == right)


def _json_text(value: object) -> str:
    """How a value of the schema is shown in a reason: as JSON, readable and deterministic."""
    return json.dumps(value, ensure_ascii=False, default=str)


def _check_numeric_bounds(
    value: object, node: dict[str, Any], path: _ArgPath, violations: list[Violation]
) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return  # Only numbers have numeric bounds, and a boolean is never a number.
    minimum = node.get("minimum")
    # The comparisons are negated so that NaN, for which every comparison is false, fails too.
    if minimum is not None and not value >= minimum:
        text = f"debe ser mayor o igual que {_json_text(minimum)}."
        violations.append(Violation(_path_text(path), text))
    maximum = node.get("maximum")
    if maximum is not None and not value <= maximum:
        text = f"debe ser menor o igual que {_json_text(maximum)}."
        violations.append(Violation(_path_text(path), text))


def _check_count(
    count: int,
    node: dict[str, Any],
    path: _ArgPath,
    violations: list[Violation],
    keywords: tuple[str, str],
    unit: tuple[str, str],
) -> None:
    """Check a number of characters or items against a ``(minimum, maximum)`` pair of keywords."""
    minimum = node.get(keywords[0])
    if minimum is not None and count < minimum:
        text = f"debe tener al menos {_count_text(minimum, unit)}."
        violations.append(Violation(_path_text(path), text))
    maximum = node.get(keywords[1])
    if maximum is not None and count > maximum:
        text = f"debe tener como máximo {_count_text(maximum, unit)}."
        violations.append(Violation(_path_text(path), text))


def _count_text(number: int, unit: tuple[str, str]) -> str:
    """``1 carácter`` but ``0 caracteres`` and ``3 caracteres``."""
    return f"{number} {unit[0] if number == 1 else unit[1]}"


def _validate_items(
    value: list[Any], node: dict[str, Any], path: _ArgPath, violations: list[Violation]
) -> None:
    items = node.get("items")
    if items is None:
        return
    for index, element in enumerate(value):
        _validate_value(element, items, (*path, index), violations)


def _validate_object(
    value: dict[Any, Any], node: dict[str, Any], path: _ArgPath, violations: list[Violation]
) -> None:
    properties: dict[str, Any] = node.get("properties", {})
    for name in node.get("required", []):
        if name not in value:
            violations.append(Violation(_path_text((*path, name)), _MISSING_FIELD_TEXT))
    for name, subschema in properties.items():
        if name in value:
            _validate_value(value[name], subschema, (*path, name), violations)
    if node.get("additionalProperties") is True:
        return
    for key in value:
        if key not in properties:
            violations.append(Violation(_path_text((*path, str(key))), _UNDECLARED_FIELD_TEXT))


def _matches_declared_type(value: object, declared: str | list[str]) -> bool:
    names = [declared] if isinstance(declared, str) else declared
    return any(_matches_type(value, name) for name in names)


def _matches_type(value: object, name: str) -> bool:
    if name == "string":
        return isinstance(value, str)
    if name == "integer":
        return _is_integer(value)
    if name == "number":
        return _is_finite_number(value)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "array":
        return isinstance(value, list)
    if name == "object":
        return isinstance(value, dict)
    return value is None  # "null"


def _is_integer(value: object) -> bool:
    """An ``int`` or an integral ``float`` (``3.0``), never a ``bool`` (a subclass of ``int``)."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and value.is_integer()  # False for NaN and infinities


def _expected_text(declared: str | list[str]) -> str:
    names = [declared] if isinstance(declared, str) else declared
    if len(names) == 1:
        return _TYPE_ARTICLES[names[0]]
    return "uno de: " + ", ".join(_TYPE_LABELS[name] for name in names)
