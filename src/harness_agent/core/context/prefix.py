"""Stable prompt prefix: instructions, rules, environment and tool definitions (HU-02-01).

The prefix is one ``SYSTEM`` message with sections in a fixed order, plus the tool definitions
sorted by name. Equal inputs always produce byte-identical output, whatever the registration
order of the tools, so the provider can cache it (RNF-4). Tool definitions travel in the
``tools`` argument of ``Provider.complete`` and are not repeated in the message text.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass

from harness_agent.core.context.errors import ContextConfigError
from harness_agent.core.entities import Message, Role
from harness_agent.core.interfaces.provider import ToolDefinition

NO_RULES = "(ninguna)"


@dataclass(frozen=True)
class PrefixSpec:
    """Values the composition root provides to build the prefix.

    Attributes:
        instructions: Base instructions for the model.
        rules: Rules the agent must follow, in the order they are shown.
        os_name: Operating system the shell runs on.
        interpreter: Shell interpreter used by the shell tool (``Shell.interpreter_name``).
    """

    instructions: str
    rules: tuple[str, ...]
    os_name: str
    interpreter: str

    def __post_init__(self) -> None:
        for label, value in (
            ("instrucciones", self.instructions),
            ("sistema operativo", self.os_name),
            ("intérprete", self.interpreter),
        ):
            if not value.strip():
                raise ContextConfigError(f"El campo '{label}' del prefijo no puede estar vacío.")
        object.__setattr__(self, "rules", tuple(self.rules))
        if any(not rule.strip() for rule in self.rules):
            raise ContextConfigError("Las reglas del prefijo no pueden estar vacías.")


@dataclass(frozen=True)
class StablePrefix:
    """The fixed part of the context: system message, sorted tools and a fingerprint."""

    system_message: Message
    tools: tuple[ToolDefinition, ...]
    fingerprint: str


def _render(spec: PrefixSpec) -> str:
    rules = "\n".join(f"- {rule}" for rule in spec.rules) if spec.rules else NO_RULES
    return (
        f"## Instrucciones\n{spec.instructions}\n\n"
        f"## Reglas\n{rules}\n\n"
        f"## Entorno\nSistema operativo: {spec.os_name}\n"
        f"Intérprete de comandos: {spec.interpreter}"
    )


def _sorted_tools(definitions: Sequence[ToolDefinition]) -> tuple[ToolDefinition, ...]:
    names = [definition.name for definition in definitions]
    if any(not name.strip() for name in names):
        raise ContextConfigError("Una definición de herramienta tiene el nombre vacío.")
    if len(set(names)) != len(names):
        raise ContextConfigError("Hay definiciones de herramientas con nombre duplicado.")
    return tuple(sorted(definitions, key=lambda definition: definition.name))


def _fingerprint(text: str, tools: tuple[ToolDefinition, ...]) -> str:
    try:
        serialized_tools = json.dumps(
            [[t.name, t.description, t.parameters] for t in tools],
            sort_keys=True,
            ensure_ascii=False,
        )
    except (TypeError, ValueError) as exc:
        raise ContextConfigError(
            "Los parámetros de una herramienta no se pueden serializar."
        ) from exc
    digest = hashlib.sha256()
    digest.update(text.encode("utf-8"))
    digest.update(b"\0")
    digest.update(serialized_tools.encode("utf-8"))
    return digest.hexdigest()


def build_prefix(spec: PrefixSpec, definitions: Sequence[ToolDefinition]) -> StablePrefix:
    """Build the stable prefix; equal inputs give identical output (FR-004, FR-008)."""
    tools = _sorted_tools(definitions)
    text = _render(spec)
    return StablePrefix(Message(Role.SYSTEM, text), tools, _fingerprint(text, tools))
