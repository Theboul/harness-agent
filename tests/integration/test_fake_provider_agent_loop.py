"""AC-01 of HU-00-03 with the real loop: a scripted run is deterministic and uses no network.

The real ``AgentLoop`` runs against ``FakeProvider``, the recording bus and instant tools. Every
test in this module runs with the network blocked: connecting anywhere but loopback fails the test
(loopback and Unix sockets stay open because asyncio itself uses them, notably ``socketpair`` on
Windows).
"""

from __future__ import annotations

import asyncio
import socket
import time
from collections.abc import Callable
from typing import Any

import pytest

import harness_agent.core as core
from harness_agent.core import (
    Event,
    EventType,
    Message,
    PermissionDecision,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
    Role,
    ToolCall,
)
from harness_agent.core.loop import MAX_MESSAGE_CHARS, AgentLoop, TurnResult, TurnStatus
from tests.doubles import (
    FakeProvider,
    InMemoryToolRegistry,
    RecordingEventBus,
    RecordingTool,
    ScriptedPolicy,
)

SESSION = "session-1"
TASK = "haz la tarea"
LOOPBACK = ("127.0.0.1", "::1", "localhost")


class NetworkAccessError(AssertionError):
    """A test tried to reach a non-local network destination."""


def _is_local(address: object) -> bool:
    if isinstance(address, (str, bytes)):
        return True  # Unix socket path
    if isinstance(address, tuple) and address:
        host = address[0]
        return isinstance(host, str) and (host in LOOPBACK or host.startswith("127."))
    return False


@pytest.fixture(autouse=True)
def blocked_network(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Fail the test on any non-local connection attempt; return the attempts seen."""
    attempts: list[str] = []
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guard_connect(self: socket.socket, address: Any) -> None:
        if not _is_local(address):
            attempts.append(f"connect {address!r}")
            raise NetworkAccessError(f"network access attempted: {address!r}")
        real_connect(self, address)

    def guard_connect_ex(self: socket.socket, address: Any) -> int:
        if not _is_local(address):
            attempts.append(f"connect_ex {address!r}")
            raise NetworkAccessError(f"network access attempted: {address!r}")
        return real_connect_ex(self, address)

    def guard_create_connection(address: Any, *args: Any, **kwargs: Any) -> socket.socket:
        if not _is_local(address):
            attempts.append(f"create_connection {address!r}")
            raise NetworkAccessError(f"network access attempted: {address!r}")
        return real_create_connection(address, *args, **kwargs)

    def guard_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        if not _is_local((host,)):
            attempts.append(f"getaddrinfo {host!r}")
            raise NetworkAccessError(f"name resolution attempted: {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    real_create_connection = socket.create_connection
    real_getaddrinfo = socket.getaddrinfo
    monkeypatch.setattr(socket.socket, "connect", guard_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guard_connect_ex)
    monkeypatch.setattr(socket, "create_connection", guard_create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", guard_getaddrinfo)
    return attempts


def _script() -> list[ProviderResponse | ProviderError]:
    return [
        ProviderResponse(tool_calls=[ToolCall(id="c1", name="echo", arguments={"text": "uno"})]),
        ProviderResponse(tool_calls=[ToolCall(id="c2", name="echo", arguments={"text": "dos"})]),
        ProviderResponse(content="listo"),
    ]


class Run:
    """One turn of the real loop over a FakeProvider, plus the doubles for assertions."""

    def __init__(self, provider: FakeProvider) -> None:
        self.provider = provider
        self.tool = RecordingTool(name="echo", content="eco")
        self.bus = RecordingEventBus()
        self.history: list[Message] = []
        registry = InMemoryToolRegistry([self.tool])
        policy = ScriptedPolicy({"echo": PermissionDecision.ALLOW})
        self.loop = AgentLoop(provider, registry, policy, self.bus)

    async def go(self) -> TurnResult:
        async with asyncio.timeout(5.0):
            return await self.loop.run_turn(session_id=SESSION, task=TASK, history=self.history)

    @property
    def events(self) -> list[Event]:
        return self.bus.emitted_events

    def signature(self, result: TurnResult) -> tuple[Any, ...]:
        """Everything a run decides; event ids and timestamps are excluded (random and clock)."""
        return (
            result.status,
            result.final_response,
            result.history,
            [(e.type, e.payload) for e in self.events],
            self.tool.executions,
            self.provider.received,
            self.provider.call_count,
        )


async def _run(script: list[ProviderResponse | ProviderError]) -> tuple[Run, TurnResult]:
    run = Run(FakeProvider(script))
    return run, await run.go()


class TestScriptedRun:
    async def test_the_loop_gets_the_steps_in_order_and_ends_with_the_final_text(self) -> None:
        run, result = await _run(_script())

        assert result.status is TurnStatus.COMPLETED
        assert result.final_response == "listo"
        assert run.provider.call_count == 3
        assert run.provider.exhausted is False
        assert run.tool.executions == [{"text": "uno"}, {"text": "dos"}]

    async def test_each_call_receives_the_history_built_so_far(self) -> None:
        run, _ = await _run(_script())

        assert run.provider.received[0] == [Message(role=Role.USER, content=TASK)]
        assert [len(m) for m in run.provider.received] == [1, 3, 5]

    async def test_the_events_follow_the_script(self) -> None:
        run, _ = await _run(_script())

        types = [e.type for e in run.events]
        assert types.count(EventType.TOOL_REQUESTED) == 2
        assert types.count(EventType.TOOL_FINISHED) == 2
        assert types[-1] is EventType.ASSISTANT_MESSAGE
        assert EventType.PROVIDER_ERROR not in types


class TestDeterminism:
    async def test_twenty_runs_of_the_same_script_are_identical(self) -> None:
        first_run, first_result = await _run(_script())
        expected = first_run.signature(first_result)

        for _ in range(19):
            run, result = await _run(_script())
            assert run.signature(result) == expected

    async def test_a_second_provider_built_from_the_same_list_behaves_the_same(self) -> None:
        script = _script()
        first_run, first_result = await _run(script)
        second_run, second_result = await _run(script)

        assert first_run.signature(first_result) == second_run.signature(second_result)


class TestNoNetwork:
    async def test_a_scripted_run_makes_no_network_attempt(
        self, blocked_network: list[str]
    ) -> None:
        for _ in range(5):
            await _run(_script())

        assert blocked_network == []


FAILURES = (
    pytest.param(QuotaExceeded, id="quota"),
    pytest.param(ProviderTimeout, id="timeout"),
    pytest.param(ProviderUnavailable, id="unavailable"),
)


class TestSimulatedFailures:
    """AC-02: the loop receives the same error type a real provider would raise."""

    @pytest.mark.parametrize("error_type", FAILURES)
    async def test_the_turn_ends_as_a_provider_failure_with_the_canonical_type(
        self, error_type: type[ProviderError]
    ) -> None:
        run, result = await _run([error_type("fallo simulado")])

        assert result.status is TurnStatus.PROVIDER_FAILED
        errors = [e for e in run.events if e.type is EventType.PROVIDER_ERROR]
        assert len(errors) == 1
        assert errors[0].payload["reason"] == "provider_exception"
        assert errors[0].payload["error_type"] == error_type.__name__
        assert errors[0].payload["message"] == "fallo simulado"
        assert getattr(core, error_type.__name__) is error_type
        assert issubclass(error_type, ProviderError)

    async def test_a_failure_in_the_third_call_keeps_the_work_of_the_first_two(self) -> None:
        script: list[ProviderResponse | ProviderError] = [*_script()[:2], QuotaExceeded("cuota")]
        run = Run(FakeProvider(script))

        result = await run.go()

        assert result.status is TurnStatus.PROVIDER_FAILED
        assert run.provider.call_count == 3
        assert run.tool.executions == [{"text": "uno"}, {"text": "dos"}]
        assert len(result.history) == 5

    async def test_a_long_failure_message_is_bounded_by_the_loop(self) -> None:
        run, _ = await _run([QuotaExceeded("x" * 5000)])

        (error,) = [e for e in run.events if e.type is EventType.PROVIDER_ERROR]
        assert len(error.payload["message"]) <= MAX_MESSAGE_CHARS

    async def test_a_failing_run_is_as_repeatable_as_a_normal_one(self) -> None:
        first_run, first_result = await _run([QuotaExceeded("cuota")])
        expected = first_run.signature(first_result)

        for _ in range(19):
            run, result = await _run([QuotaExceeded("cuota")])
            assert run.signature(result) == expected

    async def test_the_whole_failing_turn_is_quick_and_uses_no_network(
        self, blocked_network: list[str]
    ) -> None:
        started = time.perf_counter()
        await _run([ProviderTimeout("t")])

        assert time.perf_counter() - started < 0.5
        assert blocked_network == []


class TestNetworkGuard:
    """The fixture itself: external destinations fail, local ones keep working."""

    @pytest.mark.parametrize(
        "action",
        [
            lambda: socket.socket().connect(("203.0.113.1", 80)),
            lambda: socket.socket().connect_ex(("203.0.113.1", 80)),
            lambda: socket.create_connection(("example.invalid", 80)),
            lambda: socket.getaddrinfo("example.invalid", 80),
        ],
        ids=["connect", "connect_ex", "create_connection", "getaddrinfo"],
    )
    def test_external_destinations_fail_and_are_recorded(
        self, action: Callable[[], object], blocked_network: list[str]
    ) -> None:
        with pytest.raises(NetworkAccessError):
            action()

        assert len(blocked_network) == 1

    def test_loopback_and_socketpair_stay_open(self, blocked_network: list[str]) -> None:
        left, right = socket.socketpair()
        with left, right:
            left.sendall(b"x")
            assert right.recv(1) == b"x"

        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            with socket.create_connection(server.getsockname()) as client:
                accepted, _ = server.accept()
                with accepted:
                    client.sendall(b"y")
                    assert accepted.recv(1) == b"y"

        assert blocked_network == []
