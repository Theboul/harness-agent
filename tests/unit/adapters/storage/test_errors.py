"""Domain errors of the storage adapter (HU-03-01 / T002)."""

from __future__ import annotations

import pytest

from harness_agent.adapters.storage.errors import (
    ParentSessionNotFound,
    SchemaVersionError,
    SessionStoreError,
)


def test_session_store_error_is_an_exception() -> None:
    assert issubclass(SessionStoreError, Exception)


@pytest.mark.parametrize("error_type", [SchemaVersionError, ParentSessionNotFound])
def test_specific_errors_are_session_store_errors(error_type: type[SessionStoreError]) -> None:
    assert issubclass(error_type, SessionStoreError)


@pytest.mark.parametrize(
    "error_type", [SessionStoreError, SchemaVersionError, ParentSessionNotFound]
)
def test_errors_keep_their_message(error_type: type[SessionStoreError]) -> None:
    assert str(error_type("mensaje fijo")) == "mensaje fijo"
