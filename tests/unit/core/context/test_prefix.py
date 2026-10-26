"""Stable prefix description and rendering (HU-02-01, Sp2-10)."""

from __future__ import annotations

import dataclasses

import pytest

from harness_agent.core import Role, ToolDefinition
from harness_agent.core.context import ContextConfigError
from harness_agent.core.context.prefix import PrefixSpec, build_prefix

SENTINEL = "VALOR-DE-PRUEBA-123"


def make_spec(**overrides: object) -> PrefixSpec:
    values: dict[str, object] = {
        "instructions": "Be precise.",
        "rules": ("Never guess paths.", "Ask before deleting."),
        "os_name": "Windows 11",
        "interpreter": "PowerShell",
    }
    values.update(overrides)
    return PrefixSpec(**values)  # type: ignore[arg-type]


TOOLS = (
    ToolDefinition("listar_archivos", "List files.", {"type": "object"}),
    ToolDefinition("buscar_texto", "Search text.", {"type": "object", "required": ["q"]}),
    ToolDefinition("leer_archivo", "Read a file.", {"type": "object"}),
)


def test_the_system_message_has_fixed_sections_in_order() -> None:
    prefix = build_prefix(make_spec(), TOOLS)
    assert prefix.system_message.role is Role.SYSTEM
    text = prefix.system_message.content
    assert text.index("## Instrucciones") < text.index("## Reglas") < text.index("## Entorno")
    assert "Be precise." in text
    assert "- Never guess paths.\n- Ask before deleting." in text
    assert "Sistema operativo: Windows 11" in text
    assert "Intérprete de comandos: PowerShell" in text


def test_no_rules_keeps_the_section_shape() -> None:
    text = build_prefix(make_spec(rules=()), TOOLS).system_message.content
    assert "## Reglas\n(ninguna)" in text


def test_tools_are_sorted_by_name() -> None:
    prefix = build_prefix(make_spec(), TOOLS)
    assert [t.name for t in prefix.tools] == ["buscar_texto", "leer_archivo", "listar_archivos"]


def test_registration_order_does_not_change_the_fingerprint() -> None:
    forward = build_prefix(make_spec(), TOOLS)
    backward = build_prefix(make_spec(), tuple(reversed(TOOLS)))
    assert forward.fingerprint == backward.fingerprint
    assert forward == backward


def test_fingerprint_is_a_sha256_hex_digest() -> None:
    fingerprint = build_prefix(make_spec(), TOOLS).fingerprint
    assert len(fingerprint) == 64
    int(fingerprint, 16)


@pytest.mark.parametrize(
    "overrides",
    [
        {"instructions": "Be brief."},
        {"rules": ("Only one rule.",)},
        {"os_name": "Ubuntu 24.04"},
        {"interpreter": "bash"},
    ],
    ids=["instructions", "rules", "os", "interpreter"],
)
def test_any_change_in_the_spec_changes_the_fingerprint(overrides: dict[str, object]) -> None:
    assert (
        build_prefix(make_spec(), TOOLS).fingerprint
        != build_prefix(make_spec(**overrides), TOOLS).fingerprint
    )


def test_a_change_in_a_tool_changes_the_fingerprint() -> None:
    changed = (*TOOLS[:2], ToolDefinition("leer_archivo", "Read a file!", {"type": "object"}))
    assert (
        build_prefix(make_spec(), TOOLS).fingerprint
        != build_prefix(make_spec(), changed).fingerprint
    )


def test_the_prefix_is_immutable() -> None:
    prefix = build_prefix(make_spec(), TOOLS)
    with pytest.raises(dataclasses.FrozenInstanceError):
        prefix.fingerprint = "x"  # type: ignore[misc]


@pytest.mark.parametrize(
    "overrides",
    [
        {"instructions": ""},
        {"instructions": "   \n"},
        {"os_name": " "},
        {"interpreter": ""},
        {"rules": ("ok", "")},
        {"rules": ("ok", "  ")},
    ],
)
def test_invalid_spec_values_are_rejected_without_echoing_them(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ContextConfigError) as raised:
        make_spec(**overrides)
    assert "vac" in str(raised.value)


def test_error_messages_do_not_reproduce_the_received_value() -> None:
    with pytest.raises(ContextConfigError) as raised:
        make_spec(rules=(SENTINEL, ""))
    assert SENTINEL not in str(raised.value)
    with pytest.raises(ContextConfigError) as dup:
        build_prefix(make_spec(), (ToolDefinition(SENTINEL, "a"), ToolDefinition(SENTINEL, "b")))
    assert SENTINEL not in str(dup.value)


def test_duplicate_or_empty_tool_names_are_rejected() -> None:
    with pytest.raises(ContextConfigError, match="duplicad"):
        build_prefix(make_spec(), (ToolDefinition("t", "a"), ToolDefinition("t", "b")))
    with pytest.raises(ContextConfigError, match="vacío"):
        build_prefix(make_spec(), (ToolDefinition("", "a"),))


def test_unserializable_tool_parameters_are_rejected() -> None:
    with pytest.raises(ContextConfigError, match="serializ"):
        build_prefix(make_spec(), (ToolDefinition("t", "a", {"v": object()}),))


def test_no_tools_is_valid() -> None:
    prefix = build_prefix(make_spec(), ())
    assert prefix.tools == ()
