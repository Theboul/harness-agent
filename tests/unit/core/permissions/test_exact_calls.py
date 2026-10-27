"""Tests for the exact-call permission rule (HU-11-03 / T003).

``ExactCallPolicy`` may only turn the ``ASK`` of the policy it wraps into ``ALLOW``, and only for a
call identical to a declared ``AllowedCall`` whose time limit is not exceeded. The unit tests use
made-up tool and argument names (the rule does not know the shell); the precedence tests build
the real chain ``ProtectedPolicy(ExactCallPolicy(DefaultPermissionPolicy))`` with the tool name
``shell``, because that is the name the protected policy watches.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

import harness_agent.core as core
from harness_agent.core import (
    AllowedCall,
    DefaultPermissionPolicy,
    ExactCallPolicy,
    PermissionDecision,
    PermissionPolicy,
    PermissionRules,
    ProtectedPolicy,
    RiskLevel,
    ToolCall,
)
from tests.doubles import ScriptedPolicy
from tests.unit.core.permissions.support import AreaStub, RiskTool, make_call, make_registry

TOOL = "ejecutar"
ARG = "texto"
LIMIT_ARG = "segundos"
COMMAND = "python -m pytest -q"
SENTINEL = "VALOR-DE-PRUEBA-123"

ALLOW, ASK, DENY = PermissionDecision.ALLOW, PermissionDecision.ASK, PermissionDecision.DENY


def allowed(
    value: str = COMMAND, limit: float = 300, default_limit: float = 120, tool: str = TOOL
) -> AllowedCall:
    return AllowedCall(
        tool=tool,
        argument=ARG,
        value=value,
        limit_argument=LIMIT_ARG,
        limit=limit,
        default_limit=default_limit,
    )


def policy(
    inner: object = ASK, *rules: AllowedCall, ask_names: tuple[str, ...] = ()
) -> ExactCallPolicy:
    return ExactCallPolicy(
        ScriptedPolicy({TOOL: inner, "otra": inner}), rules or (allowed(),), ask_names=ask_names
    )


def call(**arguments: Any) -> ToolCall:
    return make_call(TOOL, **arguments)


# --- AllowedCall -------------------------------------------------------------------------------


class TestAllowedCall:
    def test_the_value_is_kept_without_outer_spaces(self) -> None:
        assert allowed(value="  pytest  ").value == "pytest"

    def test_it_is_immutable(self) -> None:
        rule = allowed()

        with pytest.raises(AttributeError):
            rule.value = "x"  # type: ignore[misc]

    @pytest.mark.parametrize(
        "changes",
        [
            {"tool": ""},
            {"tool": 3},
            {"argument": " "},
            {"value": "   "},
            {"value": None},
            {"limit_argument": ""},
            {"limit_argument": ARG},
            {"limit": 0},
            {"limit": -1},
            {"limit": True},
            {"limit": math.inf},
            {"limit": math.nan},
            {"limit": "300"},
            {"default_limit": 0},
            {"default_limit": False},
            {"default_limit": math.inf},
        ],
    )
    def test_an_invalid_rule_is_rejected_without_repeating_values(
        self, changes: dict[str, object]
    ) -> None:
        fields: dict[str, object] = {
            "tool": TOOL,
            "argument": ARG,
            "value": SENTINEL,
            "limit_argument": LIMIT_ARG,
            "limit": 300,
            "default_limit": 120,
        }
        fields.update(changes)

        with pytest.raises(ValueError) as caught:
            AllowedCall(**fields)  # type: ignore[arg-type]

        assert SENTINEL not in str(caught.value)

    def test_matches_the_exact_call_with_and_without_time_limit(self) -> None:
        rule = allowed()

        assert rule.matches(call(texto=COMMAND)) is True
        assert rule.matches(call(texto=COMMAND, segundos=300)) is True
        assert rule.matches(call(texto=f"  {COMMAND}\t", segundos=1)) is True
        assert rule.matches(call(texto=COMMAND, segundos=299.5)) is True

    def test_without_time_limit_the_default_must_fit(self) -> None:
        assert allowed(limit=60, default_limit=120).matches(call(texto=COMMAND)) is False
        assert allowed(limit=60, default_limit=120).matches(call(texto=COMMAND, segundos=60))

    @pytest.mark.parametrize(
        "bad",
        [
            "not a call",
            ToolCall(id="1", name=TOOL, arguments="texto"),  # type: ignore[arg-type]
            ToolCall(id="1", name=3, arguments={ARG: COMMAND}),  # type: ignore[arg-type]
        ],
    )
    def test_a_malformed_call_never_matches(self, bad: object) -> None:
        assert allowed().matches(bad) is False  # type: ignore[arg-type]


# --- Variations that must NOT be allowed (SC-002) ------------------------------------------------

VARIATIONS: dict[str, dict[str, Any]] = {
    "chained with &&": {ARG: f"{COMMAND} && echo {SENTINEL}"},
    "chained with ;": {ARG: f"{COMMAND}; echo {SENTINEL}"},
    "chained with ||": {ARG: f"{COMMAND} || echo {SENTINEL}"},
    "piped": {ARG: f"{COMMAND} | tee salida.txt"},
    "with a new line": {ARG: f"{COMMAND}\necho {SENTINEL}"},
    "with a substitution": {ARG: f"{COMMAND} $(echo {SENTINEL})"},
    "with a background &": {ARG: f"{COMMAND} &"},
    "with a redirection": {ARG: f"{COMMAND} > salida.txt"},
    "with a prefix": {ARG: f"sudo {COMMAND}"},
    "with an environment prefix": {ARG: f"X=1 {COMMAND}"},
    "with an extra argument": {ARG: f"{COMMAND} -x"},
    "shorter": {ARG: "python -m pytest"},
    "double inner space": {ARG: "python -m  pytest -q"},
    "tab inside": {ARG: "python -m\tpytest -q"},
    "upper case": {ARG: COMMAND.upper()},
    "one letter in upper case": {ARG: "Python -m pytest -q"},
    "quoted": {ARG: f'"{COMMAND}"'},
    "quoted argument": {ARG: 'python -m pytest "-q"'},
    "other command": {ARG: "python -m ruff check ."},
    "empty": {ARG: ""},
    "not a text": {ARG: ["python", "-m", "pytest", "-q"]},
    "missing command": {LIMIT_ARG: 10},
    "longer time": {ARG: COMMAND, LIMIT_ARG: 301},
    "much longer time": {ARG: COMMAND, LIMIT_ARG: 600},
    "time as boolean": {ARG: COMMAND, LIMIT_ARG: True},
    "time as text": {ARG: COMMAND, LIMIT_ARG: "10"},
    "time zero": {ARG: COMMAND, LIMIT_ARG: 0},
    "time negative": {ARG: COMMAND, LIMIT_ARG: -5},
    "time infinite": {ARG: COMMAND, LIMIT_ARG: math.inf},
    "time not a number": {ARG: COMMAND, LIMIT_ARG: math.nan},
    "time null": {ARG: COMMAND, LIMIT_ARG: None},
    "an extra argument": {ARG: COMMAND, "carpeta": "otra"},
}


class TestVariations:
    def test_there_are_at_least_fifteen(self) -> None:
        assert len(VARIATIONS) >= 15

    @pytest.mark.parametrize("label", sorted(VARIATIONS))
    def test_a_variation_is_still_asked(self, label: str) -> None:
        decision = policy(ASK).evaluate(call(**VARIATIONS[label]))

        assert decision is ASK, label

    def test_the_same_command_for_another_tool_is_still_asked(self) -> None:
        assert policy(ASK).evaluate(make_call("otra", texto=COMMAND)) is ASK

    def test_the_rule_of_another_tool_does_not_serve(self) -> None:
        rules = ExactCallPolicy(ScriptedPolicy({TOOL: ASK}), (allowed(tool="otra"),))

        assert rules.evaluate(call(texto=COMMAND)) is ASK


# --- The decision table --------------------------------------------------------------------------


class TestTheDecisionTable:
    def test_ask_and_an_exact_call_becomes_allow(self) -> None:
        assert policy(ASK).evaluate(call(texto=COMMAND)) is ALLOW

    def test_a_deny_of_the_inner_policy_stays_deny_even_for_the_exact_call(self) -> None:
        assert policy(DENY).evaluate(call(texto=COMMAND)) is DENY

    def test_an_allow_of_the_inner_policy_passes_through(self) -> None:
        assert policy(ALLOW).evaluate(call(texto="cualquier cosa")) is ALLOW

    def test_a_tool_in_the_ask_list_stays_ask_even_for_the_exact_call(self) -> None:
        assert policy(ASK, ask_names=(TOOL,)).evaluate(call(texto=COMMAND)) is ASK

    def test_the_ask_list_of_another_tool_does_not_change_it(self) -> None:
        assert policy(ASK, ask_names=("otra",)).evaluate(call(texto=COMMAND)) is ALLOW

    def test_any_of_the_rules_may_match(self) -> None:
        rules = policy(ASK, allowed(value="ruff check ."), allowed())

        assert rules.evaluate(call(texto=COMMAND)) is ALLOW
        assert rules.evaluate(call(texto="ruff check .")) is ALLOW

    def test_without_rules_nothing_changes(self) -> None:
        empty = ExactCallPolicy(ScriptedPolicy({TOOL: ASK}), ())

        assert empty.evaluate(call(texto=COMMAND)) is ASK

    @pytest.mark.parametrize("raw", ["allow", None, 1, "ALLOW"])
    def test_a_value_that_is_not_a_decision_is_deny(self, raw: object) -> None:
        assert policy(raw).evaluate(call(texto=COMMAND)) is DENY

    def test_an_exception_of_the_inner_policy_is_deny(self) -> None:
        assert policy(RuntimeError(SENTINEL)).evaluate(call(texto=COMMAND)) is DENY

    def test_an_exception_while_matching_is_deny(self) -> None:
        class Exploding(dict[str, Any]):
            def keys(self) -> Any:
                raise RuntimeError(SENTINEL)

        exploding = ToolCall(id="1", name=TOOL, arguments=Exploding({ARG: COMMAND}))

        assert policy(ASK).evaluate(exploding) is DENY

    def test_it_keeps_no_state_between_calls(self) -> None:
        rules = policy(ASK)

        assert rules.evaluate(call(texto=f"{COMMAND} -x")) is ASK
        assert rules.evaluate(call(texto=COMMAND)) is ALLOW
        assert rules.evaluate(call(texto=f"{COMMAND} -x")) is ASK

    def test_it_does_not_change_the_call(self) -> None:
        arguments = {ARG: f"  {COMMAND}  ", LIMIT_ARG: 10}
        evaluated = call(**arguments)

        policy(ASK).evaluate(evaluated)

        assert evaluated.arguments == arguments


class TestTheConstructor:
    def test_the_inner_policy_must_be_a_policy(self) -> None:
        with pytest.raises(TypeError):
            ExactCallPolicy(object(), ())  # type: ignore[arg-type]

    @pytest.mark.parametrize("rules", [None, "x", [object()], allowed()])
    def test_the_rules_must_be_a_sequence_of_allowed_calls(self, rules: object) -> None:
        with pytest.raises(TypeError):
            ExactCallPolicy(ScriptedPolicy(), rules)  # type: ignore[arg-type]

    @pytest.mark.parametrize("names", [None, "shell", [3], [""]])
    def test_the_ask_names_must_be_a_sequence_of_names(self, names: object) -> None:
        with pytest.raises(TypeError):
            ExactCallPolicy(ScriptedPolicy(), (), ask_names=names)  # type: ignore[arg-type]

    def test_a_list_of_rules_is_copied(self) -> None:
        rules = [allowed()]
        built = ExactCallPolicy(ScriptedPolicy({TOOL: ASK}), rules)
        rules.clear()

        assert built.evaluate(call(texto=COMMAND)) is ALLOW

    def test_it_is_a_permission_policy_exported_by_the_core(self) -> None:
        assert isinstance(policy(), PermissionPolicy)
        assert "ExactCallPolicy" in core.__all__
        assert "AllowedCall" in core.__all__


# --- Precedence in the real chain ----------------------------------------------------------------

SHELL = "shell"


def shell_rule(command: str = COMMAND) -> AllowedCall:
    return AllowedCall(
        tool=SHELL,
        argument="command",
        value=command,
        limit_argument="timeout_seconds",
        limit=300,
        default_limit=120,
    )


def chain(
    rules: PermissionRules = PermissionRules(),  # noqa: B008 (immutable)
    command: str = COMMAND,
    protected_inside: tuple[str, ...] = (),
) -> PermissionPolicy:
    registry = make_registry(RiskTool(SHELL, RiskLevel.HIGH))
    inner = DefaultPermissionPolicy(registry, AreaStub(), rules)
    exact = ExactCallPolicy(inner, (shell_rule(command),), ask_names=rules.ask)
    protected = AreaStub(protected_inside)
    return ProtectedPolicy(exact, protected, ("sessions.db", "criterios.json", ".harness"))


class TestPrecedenceInTheRealChain:
    def test_without_this_rule_the_shell_is_asked(self) -> None:
        registry = make_registry(RiskTool(SHELL, RiskLevel.HIGH))
        plain = DefaultPermissionPolicy(registry, AreaStub())

        assert plain.evaluate(make_call(SHELL, command=COMMAND)) is ASK

    def test_the_exact_command_is_allowed(self) -> None:
        assert chain().evaluate(make_call(SHELL, command=COMMAND, timeout_seconds=300)) is ALLOW

    def test_a_variation_is_asked(self) -> None:
        assert chain().evaluate(make_call(SHELL, command=f"{COMMAND} && x")) is ASK

    def test_the_protected_area_wins_over_the_exact_command(self) -> None:
        command = "python -m pytest .harness/sessions.db"

        assert chain(command=command).evaluate(make_call(SHELL, command=command)) is DENY

    def test_the_deny_list_wins_over_the_exact_command(self) -> None:
        rules = PermissionRules(deny=(SHELL,))

        assert chain(rules).evaluate(make_call(SHELL, command=COMMAND)) is DENY

    def test_the_ask_list_wins_over_the_exact_command(self) -> None:
        rules = PermissionRules(ask=(SHELL,))

        assert chain(rules).evaluate(make_call(SHELL, command=COMMAND)) is ASK

    def test_a_tool_in_both_lists_is_denied(self) -> None:
        rules = PermissionRules(deny=(SHELL,), ask=(SHELL,))

        assert chain(rules).evaluate(make_call(SHELL, command=COMMAND)) is DENY


def test_the_protected_path_check_still_runs_first() -> None:
    # A call with a ``path`` inside the protected area is denied before the exact rule is asked.
    exact = ExactCallPolicy(ScriptedPolicy({SHELL: ASK}), (shell_rule(),))
    protected = ProtectedPolicy(exact, AreaStub(["x"]), ())

    assert protected.evaluate(make_call(SHELL, command=COMMAND, path="x")) is DENY
