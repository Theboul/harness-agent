"""Tool registry and argument validation for HARNESS (HU-01-02).

Concrete in-memory implementation of the ``ToolRegistry`` port plus a minimal JSON Schema
validator. Standard library only: this package must never import adapters, the CLI or any
third-party SDK.
"""

from harness_agent.core.tools.errors import (
    DuplicateToolError,
    InvalidToolDefinitionError,
    ToolRegistryError,
    ToolValidationError,
    UnknownToolError,
    Violation,
)
from harness_agent.core.tools.registry import InMemoryToolRegistry
from harness_agent.core.tools.schema_validator import check_schema, validate_arguments

__all__ = [
    "InMemoryToolRegistry",
    "ToolRegistryError",
    "InvalidToolDefinitionError",
    "DuplicateToolError",
    "UnknownToolError",
    "ToolValidationError",
    "Violation",
    "check_schema",
    "validate_arguments",
]
