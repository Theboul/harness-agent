"""Loading of the SDK and translation of its failures (HU-08-01 / FR-004, FR-011)."""

from __future__ import annotations

import sys
import types

import pytest

from harness_agent.adapters.mcp import McpConnectError, McpDependencyError
from harness_agent.adapters.mcp.sdk import load_sdk
from harness_agent.adapters.mcp.translate import (
    CallFailure,
    classify_call,
    connect_error,
    leaf_exceptions,
)

SENTINEL = "VALOR-DE-PRUEBA-123"


class FakeMcpError(Exception):
    """Stands for ``mcp.MCPError``: the translation only reads its text."""


class TestLeafExceptions:
    def test_a_plain_exception_is_its_own_leaf(self) -> None:
        error = OSError("x")

        assert leaf_exceptions(error) == [error]

    def test_nested_groups_are_flattened_in_order(self) -> None:
        first, second, third = ValueError("a"), KeyError("b"), OSError("c")
        group = ExceptionGroup("outer", [ExceptionGroup("inner", [first, second]), third])

        assert leaf_exceptions(group) == [first, second, third]


class TestConnectError:
    @pytest.mark.parametrize(
        ("error", "code"),
        [
            (FileNotFoundError("no-such"), "no_se_pudo_iniciar"),
            (PermissionError("denied"), "no_se_pudo_iniciar"),
            (FakeMcpError("Connection closed"), "cerro_al_arrancar"),
            (BrokenPipeError("pipe"), "cerro_al_arrancar"),
            (FakeMcpError("Request 'initialize' timed out"), "sin_respuesta"),
            (TimeoutError("late"), "sin_respuesta"),
            (RuntimeError("otra cosa"), "fallo"),
        ],
    )
    def test_each_failure_gets_its_code(self, error: Exception, code: str) -> None:
        assert connect_error("demo", error).code == code

    def test_a_group_is_classified_by_its_leaves(self) -> None:
        group = ExceptionGroup("g", [ExceptionGroup("g2", [FakeMcpError("Connection closed")])])

        assert connect_error("demo", group).code == "cerro_al_arrancar"

    def test_the_text_of_the_original_error_never_reaches_the_domain_error(self) -> None:
        error = connect_error("demo", FakeMcpError(f"Connection closed {SENTINEL}"))

        assert isinstance(error, McpConnectError)
        assert SENTINEL not in str(error)
        assert SENTINEL not in repr(error.args)


class TestCallFailure:
    @pytest.mark.parametrize(
        ("error", "kind"),
        [
            (FakeMcpError("Request 'tools/call' timed out"), CallFailure.TIMEOUT),
            (TimeoutError("late"), CallFailure.TIMEOUT),
            (FakeMcpError("Connection closed"), CallFailure.SERVER_DOWN),
            (ExceptionGroup("g", [BrokenPipeError("p")]), CallFailure.SERVER_DOWN),
            (ValueError(SENTINEL), CallFailure.ERROR),
        ],
    )
    def test_a_failure_of_a_call_gets_its_kind(self, error: Exception, kind: CallFailure) -> None:
        assert classify_call(error) is kind


class TestLoadSdk:
    def test_it_returns_the_pieces_the_adapter_uses(self) -> None:
        sdk = load_sdk()

        assert sdk.client_session.__name__ == "ClientSession"
        assert sdk.server_parameters.__name__ == "StdioServerParameters"
        assert callable(sdk.stdio_client)
        assert sdk.text_content.__name__ == "TextContent"

    def test_a_missing_library_is_a_dependency_error_that_names_the_extra(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "mcp", None)

        with pytest.raises(McpDependencyError) as raised:
            load_sdk()

        assert 'pip install ".[mcp]"' in str(raised.value)

    def test_an_incompatible_library_is_also_a_dependency_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "mcp", types.ModuleType("mcp"))

        with pytest.raises(McpDependencyError):
            load_sdk()
