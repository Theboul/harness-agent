"""HU-07-02 with the real loop: the adapter, the real registry, the real policy and real tools.

``bootstrap.py`` does not exist yet, so the system is composed by hand: a ``WorkspaceArea`` over a
temporary folder, the file tools and a recording tool in the real ``InMemoryToolRegistry``, the
real ``DefaultPermissionPolicy``, a recording bus and ``LiteLLMProvider`` fed by an injected
completion function (no network, no key, no library). ``bootstrap.py`` will build the adapter
from ``config.model``, ``config.limits.max_output_tokens`` and the key of the configuration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from harness_agent.adapters.providers.litellm_provider import LiteLLMProvider
from harness_agent.adapters.system import WorkspaceArea
from harness_agent.adapters.tools.list_files import ListFilesTool
from harness_agent.adapters.tools.read_file import ReadFileTool
from harness_agent.config import Secret
from harness_agent.core import (
    DefaultPermissionPolicy,
    EventType,
    InMemoryToolRegistry,
    PermissionRules,
    Provider,
    ProviderResponse,
    Role,
    ToolCall,
)
from harness_agent.core.loop import AgentLoop, TurnResult, TurnStatus
from tests.doubles import FakeProvider, RecordingEventBus, RecordingTool, run_bounded
from tests.unit.adapters.providers.support import RecordingCompletion, reply, wire_call

SENTINEL = "VALOR-DE-PRUEBA-123"
MARKER = "arguments_not_valid_json"
PATH_TOOL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"path": {"type": "string"}},
    "required": ["path"],
    "additionalProperties": False,
}
STRICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"n": {"type": "integer"}},
    "additionalProperties": False,
}
FREE_SCHEMA: dict[str, Any] = {"type": "object", "additionalProperties": True}


class Rig:
    """The composed system, over any provider."""

    def __init__(self, tmp_path: Path, provider: Provider, *tools: RecordingTool) -> None:
        root = tmp_path / "area"
        root.mkdir()
        (root / "a.txt").write_text("contenido A\n", "utf-8", newline="")
        (root / "b.txt").write_text("contenido B\n", "utf-8", newline="")
        area = WorkspaceArea(root)
        self.registry = InMemoryToolRegistry()
        for tool in (ReadFileTool(area), ListFilesTool(area), *tools):
            self.registry.register(tool)
        policy = DefaultPermissionPolicy(self.registry, area, PermissionRules())
        self.bus = RecordingEventBus()
        self.loop = AgentLoop(provider, self.registry, policy, self.bus)

    async def go(self) -> TurnResult:
        return await run_bounded(
            self.loop.run_turn(session_id="s1", task="haz la tarea", history=[])
        )

    def events(self, kind: EventType) -> list[dict[str, Any]]:
        return [dict(e.payload) for e in self.bus.emitted_events if e.type is kind]


def adapter(*outcomes: Any, key: str | None = None) -> tuple[LiteLLMProvider, RecordingCompletion]:
    completion = RecordingCompletion(*outcomes)
    provider = LiteLLMProvider(
        "proveedor/modelo",
        max_output_tokens=4096,
        api_key=None if key is None else Secret(key),
        completion=completion,
    )
    return provider, completion


def failure(name: str, message: str) -> Exception:
    """An exception whose class has the name that LiteLLM gives it."""
    error: Exception = type(name, (Exception,), {})(message)
    return error


def texts_seen_anywhere(result: TurnResult, rig: Rig, completion: RecordingCompletion) -> str:
    """What the loop, the events and the model could see, as one text (not the auth parameter)."""
    return json.dumps(
        {
            "error": result.error,
            "final": result.final_response,
            "history": [(m.role.value, m.content) for m in result.history],
            "events": [(e.type.value, e.payload) for e in rig.bus.emitted_events],
            "requests": [call["messages"] for call in completion.calls],
        },
        default=str,
    )


class TestATaskWithTools:
    async def test_two_calls_in_one_answer_give_the_same_turn_as_the_scripted_double(
        self, tmp_path: Path
    ) -> None:
        wire = [
            reply(
                "Voy a leer.",
                [
                    wire_call("toolu_01A", "leer_archivo", {"path": "a.txt"}, index=1),
                    wire_call("toolu_01B", "leer_archivo", {"path": "b.txt"}, index=2),
                ],
            ),
            reply("Listo."),
        ]
        script = [
            ProviderResponse(
                content="Voy a leer.",
                tool_calls=[
                    ToolCall("toolu_01A", "leer_archivo", {"path": "a.txt"}),
                    ToolCall("toolu_01B", "leer_archivo", {"path": "b.txt"}),
                ],
            ),
            ProviderResponse(content="Listo."),
        ]
        real_provider, completion = adapter(*wire)

        (tmp_path / "real").mkdir()
        (tmp_path / "fake").mkdir()
        real = await Rig(tmp_path / "real", real_provider).go()
        simulated = await Rig(tmp_path / "fake", FakeProvider(script)).go()

        assert real.status is simulated.status is TurnStatus.COMPLETED
        assert real.final_response == simulated.final_response == "Listo."
        assert real.history == simulated.history
        assert len(completion.calls) == 2

    async def test_the_second_request_carries_the_results_of_the_tools(
        self, tmp_path: Path
    ) -> None:
        provider, completion = adapter(
            reply("", [wire_call("call_A", "leer_archivo", {"path": "a.txt"})]), reply("Listo.")
        )

        await Rig(tmp_path, provider).go()

        second = completion.calls[1]
        assert [m["role"] for m in second["messages"]] == ["user", "assistant", "tool"]
        assert second["messages"][2]["tool_call_id"] == "call_A"
        assert second["messages"][2]["content"] == "contenido A\n"
        assert all(call["max_tokens"] == 4096 for call in completion.calls)


class TestUnreadableArguments:
    @pytest.mark.parametrize("raw", ["{roto", "[1, 2]", "5", "null", "texto sin comillas"])
    async def test_the_turn_goes_on_and_the_model_gets_a_recoverable_error(
        self, tmp_path: Path, raw: str
    ) -> None:
        tool = RecordingTool("contador", schema=STRICT_SCHEMA)
        provider, completion = adapter(
            reply("", [wire_call("c1", "contador", raw)]), reply("Corregido.")
        )
        rig = Rig(tmp_path, provider, tool)

        result = await rig.go()

        assert result.status is TurnStatus.COMPLETED
        assert result.final_response == "Corregido."
        assert tool.executions == []
        (tool_message,) = [m for m in result.history if m.role is Role.TOOL]
        assert tool_message.content.startswith("[invalid_arguments]")
        assert MARKER in tool_message.content
        assert tool_message.tool_result is not None
        assert tool_message.tool_result.is_error is True
        # what the model sees on the next call: the tagged error, and a history that was built
        # without error (the marker call travels back as a JSON object).
        sent = completion.calls[1]["messages"]
        assert sent[-1]["role"] == "tool"
        assert sent[-1]["content"].startswith("[invalid_arguments]")
        assert json.loads(sent[1]["tool_calls"][0]["function"]["arguments"]).keys() == {MARKER}
        assert rig.events(EventType.PROVIDER_ERROR) == []

    async def test_a_valid_call_next_to_an_unreadable_one_still_runs(self, tmp_path: Path) -> None:
        tool = RecordingTool("contador", schema=STRICT_SCHEMA)
        provider, _ = adapter(
            reply(
                "",
                [
                    wire_call("c1", "leer_archivo", {"path": "a.txt"}),
                    wire_call("c2", "contador", "{roto"),
                ],
            ),
            reply("Listo."),
        )

        result = await Rig(tmp_path, provider, tool).go()

        assert result.status is TurnStatus.COMPLETED
        contents = {m.tool_result.call_id: m.content for m in result.history if m.tool_result}
        assert contents["c1"] == "contenido A\n"
        assert contents["c2"].startswith("[invalid_arguments]")
        assert tool.executions == []

    async def test_a_tool_that_accepts_free_form_fields_fails_closed(self, tmp_path: Path) -> None:
        tool = RecordingTool("libre", schema=FREE_SCHEMA)
        provider, completion = adapter(reply("", [wire_call("c1", "libre", "{roto")]))
        rig = Rig(tmp_path, provider, tool)

        result = await rig.go()

        assert result.status is TurnStatus.PROVIDER_FAILED
        assert tool.executions == []
        (payload,) = rig.events(EventType.PROVIDER_ERROR)
        assert payload["error_type"] == "ProviderError"
        assert "libre" in payload["message"]
        assert len(completion.calls) == 1


class TestAToolThatFails:
    async def test_the_next_request_carries_the_error_in_the_content(self, tmp_path: Path) -> None:
        tool = RecordingTool("falla", content="no se pudo", is_error=True, schema=PATH_TOOL_SCHEMA)
        provider, completion = adapter(
            reply("", [wire_call("c1", "falla", {"path": "a.txt"})]), reply("Listo.")
        )

        result = await Rig(tmp_path, provider, tool).go()

        assert result.status is TurnStatus.COMPLETED
        assert tool.executions == [{"path": "a.txt"}]
        (tool_message,) = [m for m in result.history if m.role is Role.TOOL]
        assert tool_message.content == "no se pudo"
        assert completion.calls[1]["messages"][-1]["content"] == "[tool_error] no se pudo"


class TestAFailureOfTheProvider:
    @pytest.mark.parametrize(
        ("name", "canonical"),
        [
            ("RateLimitError", "RateLimited"),
            ("PaymentRequiredError", "QuotaExceeded"),
            ("Timeout", "ProviderTimeout"),
            ("ServiceUnavailableError", "ProviderUnavailable"),
            ("APIConnectionError", "ProviderUnavailable"),
            ("AuthenticationError", "ProviderError"),
            ("RuntimeError", "ProviderError"),
        ],
    )
    async def test_it_ends_the_turn_with_the_canonical_type(
        self, tmp_path: Path, name: str, canonical: str
    ) -> None:
        provider, completion = adapter(failure(name, "texto del proveedor"))
        rig = Rig(tmp_path, provider)

        result = await rig.go()

        assert result.status is TurnStatus.PROVIDER_FAILED
        (payload,) = rig.events(EventType.PROVIDER_ERROR)
        assert payload["error_type"] == canonical
        assert "proveedor" in payload["message"]
        assert "texto del proveedor" not in payload["message"]
        assert result.error is not None and result.error.startswith(f"{canonical}: ")
        assert len(completion.calls) == 1


class TestTheKeyNeverReachesAnyone:
    async def test_a_failure_that_repeats_the_key_leaves_no_trace_in_the_turn(
        self, tmp_path: Path
    ) -> None:
        original = failure("AuthenticationError", f"Incorrect API key provided: {SENTINEL}")
        provider, completion = adapter(original, key=SENTINEL)
        rig = Rig(tmp_path, provider)

        result = await rig.go()

        assert result.status is TurnStatus.PROVIDER_FAILED
        assert SENTINEL not in texts_seen_anywhere(result, rig, completion)
        assert SENTINEL in str(original)

    async def test_unreadable_arguments_that_repeat_the_key_are_cleaned_for_the_model(
        self, tmp_path: Path
    ) -> None:
        tool = RecordingTool("contador", schema=STRICT_SCHEMA)
        provider, completion = adapter(
            reply("", [wire_call("c1", "contador", "{roto " + SENTINEL)]),
            reply("Listo."),
            key=SENTINEL,
        )
        rig = Rig(tmp_path, provider, tool)

        result = await rig.go()

        assert result.status is TurnStatus.COMPLETED
        second_request = json.dumps(completion.calls[1]["messages"])
        assert SENTINEL not in second_request
        assert "<secreto oculto>" in second_request
        assert SENTINEL not in json.dumps([(m.role.value, m.content) for m in result.history])
        assert SENTINEL not in json.dumps([e.payload for e in rig.bus.emitted_events], default=str)
