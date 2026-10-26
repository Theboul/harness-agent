"""Stability of the prefix between turns of a session (HU-02-01 AC-01, Sp2-11)."""

from __future__ import annotations

from harness_agent.core import ContextAssembler, Message, PrefixSpec, Role, ToolDefinition

TURNS = 20


def spec(rules: tuple[str, ...] = ("Ask first.",)) -> PrefixSpec:
    return PrefixSpec("Be precise.", rules, "Windows 11", "PowerShell")


class MutableSource:
    def __init__(self, names: list[str]) -> None:
        self.names = names

    def __call__(self) -> list[ToolDefinition]:
        return [ToolDefinition(n, f"Tool {n}.", {"type": "object"}) for n in self.names]


def test_the_prefix_is_identical_in_every_turn_of_a_growing_session() -> None:
    assembler = ContextAssembler(spec(), MutableSource(["b", "a"]))
    history: list[Message] = []
    contexts = []
    for turn in range(TURNS):
        history.append(Message(Role.USER, f"turn {turn}"))
        contexts.append(assembler.assemble("s1", history))
        history.append(Message(Role.ASSISTANT, f"answer {turn}"))
    first = contexts[0].provider_messages()[0]
    assert {c.prefix.fingerprint for c in contexts} == {contexts[0].prefix.fingerprint}
    assert all(c.provider_messages()[0] == first for c in contexts)
    assert all(c.provider_messages()[0].content == first.content for c in contexts)
    assert all(c.tools == contexts[0].tools for c in contexts)
    assert [len(c.history) for c in contexts] == [2 * t + 1 for t in range(TURNS)]


def test_the_prefix_does_not_change_when_tools_change_mid_session() -> None:
    source = MutableSource(["a", "b"])
    assembler = ContextAssembler(spec(), source)
    before = assembler.assemble("s1", [])
    source.names = ["c", "b", "a", "d"]
    after = assembler.assemble("s1", [Message(Role.USER, "hi")])
    assert after.prefix == before.prefix
    assert [t.name for t in after.tools] == ["a", "b"]


def test_registration_order_does_not_change_the_prefix() -> None:
    forward = ContextAssembler(spec(), MutableSource(["a", "b", "c"])).assemble("s1", [])
    backward = ContextAssembler(spec(), MutableSource(["c", "b", "a"])).assemble("s1", [])
    assert forward.prefix.fingerprint == backward.prefix.fingerprint


def test_sessions_with_different_sources_get_different_prefixes() -> None:
    source = MutableSource(["a"])
    assembler = ContextAssembler(spec(), source)
    first = assembler.assemble("s1", [])
    source.names = ["a", "b"]
    second = assembler.assemble("s2", [])
    assert first.prefix.fingerprint != second.prefix.fingerprint
    assert assembler.assemble("s1", []).prefix.fingerprint == first.prefix.fingerprint


def test_history_never_leaks_into_the_prefix() -> None:
    assembler = ContextAssembler(spec(), MutableSource(["a"]))
    empty = assembler.assemble("s1", [])
    full = assembler.assemble("s1", [Message(Role.USER, "x" * 10_000)])
    assert full.prefix is empty.prefix
    assert "x" * 100 not in full.prefix.system_message.content
