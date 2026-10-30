"""Translation of the failures of the SDK to domain errors (HU-08-01 / FR-004).

The SDK wraps transport failures in (nested) exception groups. They are flattened here and
classified by type and by the fixed phrases the SDK uses (SPK-04, section 5.1). The text of the
original exception is read to classify it and is never copied into what this module returns.
"""

from __future__ import annotations

from enum import Enum

from harness_agent.adapters.mcp.errors import McpConnectError

_CLOSED = "connection closed"
_TIMED_OUT = "timed out"


class CallFailure(Enum):
    """Why a tool call did not produce a result."""

    TIMEOUT = "timeout"
    SERVER_DOWN = "server_down"
    ERROR = "error"


def leaf_exceptions(error: BaseException) -> list[BaseException]:
    """Flatten nested exception groups into their leaves, in order."""
    if isinstance(error, BaseExceptionGroup):
        return [leaf for inner in error.exceptions for leaf in leaf_exceptions(inner)]
    return [error]


def _timed_out(leaf: BaseException) -> bool:
    return isinstance(leaf, TimeoutError) or _TIMED_OUT in str(leaf).lower()


def _closed(leaf: BaseException) -> bool:
    return isinstance(leaf, ConnectionError) or _CLOSED in str(leaf).lower()


def connect_error(server: str, error: BaseException) -> McpConnectError:
    """The domain error for a failure while starting or negotiating with ``server``."""
    leaves = leaf_exceptions(error)
    if any(_timed_out(leaf) for leaf in leaves):
        code = "sin_respuesta"
    elif any(_closed(leaf) for leaf in leaves):
        code = "cerro_al_arrancar"
    elif any(isinstance(leaf, OSError) for leaf in leaves):
        code = "no_se_pudo_iniciar"
    else:
        code = "fallo"
    return McpConnectError(server, code)


def classify_call(error: BaseException) -> CallFailure:
    """What went wrong in a tool call that raised."""
    leaves = leaf_exceptions(error)
    if any(_timed_out(leaf) for leaf in leaves):
        return CallFailure.TIMEOUT
    if any(_closed(leaf) for leaf in leaves):
        return CallFailure.SERVER_DOWN
    return CallFailure.ERROR
