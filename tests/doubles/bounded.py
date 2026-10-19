"""Test helper: run_bounded, a time-boxed await that fails on script exhaustion (T002)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from tests.doubles.scripted_provider import ScriptedProvider

T = TypeVar("T")


async def run_bounded(
    awaitable: Awaitable[T],
    *,
    provider: ScriptedProvider | None = None,
    timeout: float = 5.0,
) -> T:
    """Await ``awaitable`` within ``timeout`` seconds (detects endless loops, FR-028).

    If a ``provider`` is given and its script was exhausted during the run, the test
    fails explicitly even if the code under test swallowed the error.
    """
    async with asyncio.timeout(timeout):
        result = await awaitable
    if provider is not None and provider.exhausted:
        raise AssertionError("ScriptedProvider script was exhausted: the loop asked for more.")
    return result
