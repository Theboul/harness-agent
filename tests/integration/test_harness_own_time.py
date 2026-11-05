"""AC-03 of HU-00-05.1: the own time of the harness per turn is small and is recorded.

``compose()`` builds the real system (loop, policy chain, registry with its wrappers, bus, message
capture, audit, traces) over a SQLite file in ``tmp_path`` (real COMMITs with ``fsync``). The model
is a ``FakeProvider`` of zero latency whose ``complete`` is timed with ``time.perf_counter``; that
time is the model's and is taken off the turn, so what is left is the time of the harness (rule 2
of the story). The test fails only on a big regression: the threshold is about twelve times the
median measured on the development machine (see ``specs/055-core-failure-tests/spec.md``, D-10).

The result is recorded in three places and never in the repository: ``record_property`` (JUnit),
one line printed to the real output (the CI log) and, if the variable ``HARNESS_TIMING_REPORT``
names a path, a JSON file there.
"""

from __future__ import annotations

import asyncio
import gc
import json
import math
import os
import statistics
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from harness_agent.bootstrap import Composition, compose
from harness_agent.config import Limits
from harness_agent.core import (
    Message,
    Provider,
    ProviderResponse,
    RiskLevel,
    Tool,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from harness_agent.core.loop import TurnStatus
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import make_config

TURNS = 200
WARMUP = 10
THRESHOLD_MS = 250.0  # median own time per turn; about 12 times the local median (~20 ms)
MODEL_LATENCY_LIMIT_MS = 5.0  # a model of "zero latency" spends far less than this per call
REPORT_VARIABLE = "HARNESS_TIMING_REPORT"
SLOW_MODEL_SECONDS = 0.05


class Echo(Tool):
    """An instant tool inside the work area (low risk: the policy lets it through)."""

    @property
    def name(self) -> str:
        return "eco"

    @property
    def description(self) -> str:
        return "Answers ok."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        }

    @property
    def risk(self) -> RiskLevel:
        return RiskLevel.LOW

    async def run(self, args: dict[str, Any]) -> ToolResult:
        return ToolResult("", "ok", False)


class TimedModel(Provider):
    """A scripted model that counts the time spent inside ``complete`` (the model's latency)."""

    def __init__(self, turns: int, delay: float) -> None:
        script: list[ProviderResponse] = []
        for number in range(turns):
            call = ToolCall(f"c{number}", "eco", {"path": "."})
            script += [ProviderResponse(content="", tool_calls=[call])]
            script += [ProviderResponse(content=f"listo {number}")]
        self._inner = FakeProvider(script)
        self._delay = delay
        self.spent = 0.0
        self.calls = 0

    async def complete(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None
    ) -> ProviderResponse:
        started = time.perf_counter()
        try:
            if self._delay:
                await asyncio.sleep(self._delay)
            return await self._inner.complete(messages, tools)
        finally:
            self.spent += time.perf_counter() - started
            self.calls += 1


@dataclass(frozen=True)
class Measurement:
    own_ms: list[float]  # per measured turn: turn time minus the model's time
    total_ms: list[float]  # per measured turn: the whole turn
    model_ms_per_call: float
    composition: Composition


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


async def measure(
    tmp_path: Path, opened: list[Composition], turns: int, warmup: int, delay: float = 0.0
) -> Measurement:
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    model = TimedModel(turns + warmup, delay)
    config = replace(
        make_config(tmp_path, workspace=workspace),
        limits=Limits(max_turns=100_000, max_output_tokens=777),
    )
    composition = compose(config, provider_factory=lambda _config: model, system_name="Linux")
    opened.append(composition)
    composition.registry.register(Echo())
    own: list[float] = []
    total: list[float] = []
    gc.collect()
    for number in range(turns + warmup):
        history = list(composition.history_prefix)  # a new history: its size does not grow the cost
        spent_before = model.spent
        started = time.perf_counter()
        result = await composition.loop.run_turn(
            session_id=composition.session_id, task=f"tarea {number}", history=history
        )
        elapsed = time.perf_counter() - started
        assert result.status is TurnStatus.COMPLETED
        if number >= warmup:
            own.append((elapsed - (model.spent - spent_before)) * 1000)
            total.append(elapsed * 1000)
    return Measurement(own, total, model.spent * 1000 / model.calls, composition)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def count(composition: Composition, sql: str) -> int:
    return int(composition.store.connection().execute(sql).fetchone()[0])


def test_ac03_the_own_time_of_the_harness_per_turn_is_below_the_threshold_and_is_recorded(
    tmp_path: Path,
    opened: list[Composition],
    record_property: Callable[[str, object], None],
    capsys: pytest.CaptureFixture[str],
) -> None:
    measured = asyncio.run(measure(tmp_path, opened, TURNS, WARMUP))

    # the measured path is the real system: every call left its trace and its audit row
    turns = TURNS + WARMUP
    composition = measured.composition
    assert count(composition, "SELECT COUNT(*) FROM trazas WHERE tipo = 'modelo'") == 2 * turns
    assert count(composition, "SELECT COUNT(*) FROM trazas WHERE tipo = 'herramienta'") == turns
    assert count(composition, "SELECT COUNT(*) FROM auditoria") == turns
    assert count(composition, "SELECT COUNT(*) FROM events WHERE type = 'tool_finished'") == turns
    # and the model was a model of zero latency, so what is measured is the harness
    assert measured.model_ms_per_call < MODEL_LATENCY_LIMIT_MS

    median = statistics.median(measured.own_ms)
    p95, worst = percentile(measured.own_ms, 0.95), max(measured.own_ms)
    report = {
        "story": "HU-00-05.1",
        "turns": TURNS,
        "model_calls_per_turn": 2,
        "median_ms": round(median, 2),
        "p95_ms": round(p95, 2),
        "max_ms": round(worst, 2),
        "model_ms_per_call": round(measured.model_ms_per_call, 3),
        "threshold_ms": THRESHOLD_MS,
    }
    for key, value in report.items():
        record_property(f"own_time_{key}", value)
    line = (
        f"[HU-00-05.1] own time of the harness per turn ({TURNS} turns): "
        f"median={median:.2f} ms p95={p95:.2f} ms max={worst:.2f} ms "
        f"(model {measured.model_ms_per_call:.3f} ms per call, threshold {THRESHOLD_MS:.0f} ms)"
    )
    with capsys.disabled():
        print("\n" + line)
    target = os.environ.get(REPORT_VARIABLE)
    (Path(target) if target else tmp_path / "timing.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    assert median <= THRESHOLD_MS, line


def test_ac03_the_measurement_subtracts_the_latency_of_the_model(
    tmp_path: Path, opened: list[Composition]
) -> None:
    turns = 5
    measured = asyncio.run(measure(tmp_path, opened, turns, 1, delay=SLOW_MODEL_SECONDS))

    model_ms = SLOW_MODEL_SECONDS * 1000
    assert measured.model_ms_per_call >= model_ms  # the model really was slow
    assert min(measured.total_ms) >= 2 * model_ms  # so every whole turn took at least two calls
    assert max(measured.own_ms) < THRESHOLD_MS  # but that latency is not the harness's time
    assert statistics.median(measured.own_ms) < statistics.median(measured.total_ms) - model_ms
