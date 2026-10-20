"""Tests for the optional ``schema`` parameter of the DummyTool test double (HU-01-02 / T001).

Later HU-01-02 tests need tools that declare their own JSON Schema, and one of them mutates
the schema after registration to prove the registry validates against a snapshot.
"""

from __future__ import annotations

import inspect
from typing import Any

from harness_agent.core.interfaces.tool import RiskLevel
from tests.doubles.dummy_tool import DummyTool

DEFAULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "input": {"type": "string"},
        "call_id": {"type": "string"},
    },
}


def test_schema_is_the_last_constructor_parameter_and_defaults_to_none() -> None:
    parameters = list(inspect.signature(DummyTool.__init__).parameters.values())

    assert parameters[-1].name == "schema"
    assert parameters[-1].default is None


def test_default_schema_is_unchanged_when_no_schema_is_given() -> None:
    assert DummyTool().schema == DEFAULT_SCHEMA


def test_default_schema_is_not_shared_between_accesses() -> None:
    tool = DummyTool()

    tool.schema["properties"]["extra"] = {"type": "string"}

    assert tool.schema == DEFAULT_SCHEMA


def test_given_schema_is_returned_as_the_same_object() -> None:
    custom: dict[str, Any] = {"type": "object", "properties": {}}

    tool = DummyTool(schema=custom)

    assert tool.schema is custom


def test_empty_given_schema_is_not_replaced_by_the_default() -> None:
    custom: dict[str, Any] = {}

    tool = DummyTool(schema=custom)

    assert tool.schema is custom


def test_given_schema_can_be_mutated_after_construction() -> None:
    custom: dict[str, Any] = {"type": "object", "properties": {}}
    tool = DummyTool(schema=custom)

    custom["required"] = ["name"]

    assert tool.schema["required"] == ["name"]


def test_other_constructor_arguments_keep_working_with_a_custom_schema() -> None:
    tool = DummyTool(
        name="custom",
        description="Custom tool",
        risk=RiskLevel.HIGH,
        schema={"type": "object"},
    )

    assert tool.name == "custom"
    assert tool.description == "Custom tool"
    assert tool.risk is RiskLevel.HIGH
    assert tool.schema == {"type": "object"}
