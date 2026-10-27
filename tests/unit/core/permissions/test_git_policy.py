"""Tests for ``GitPolicy`` (HU-11-02 / T004).

The wrapped policy is a ``ScriptedPolicy``. ``GitPolicy`` denies destructive git calls in any
part, asks for writes and unknown subcommands **without asking the wrapped policy** (so a task
declaration can never let a push or a merge run), allows only when the whole command is git reads
and was understood, and otherwise delegates. Every normative example of
``specs/027-git-subcommand-rules/contracts/git_policy_contract.md`` is here, in bash and in
PowerShell. Nothing runs.
"""

from __future__ import annotations

from typing import Any

import pytest

import harness_agent.core as core
from harness_agent.core import (
    Dialect,
    GitPolicy,
    PermissionDecision,
    PermissionPolicy,
    ToolCall,
    git_instructions,
)
from tests.doubles import ScriptedPolicy

ALLOW, ASK, DENY = PermissionDecision.ALLOW, PermissionDecision.ASK, PermissionDecision.DENY
BASH, PS = Dialect.BASH, Dialect.POWERSHELL
BOTH = [BASH, PS]
TOOL, ARGUMENT = "ejecutar", "texto"
SENTINEL = "VALOR-DE-PRUEBA-123"


def policy(dialect: Dialect, inner: object = ASK) -> tuple[GitPolicy, ScriptedPolicy]:
    scripted = ScriptedPolicy({TOOL: inner, "otra": inner})
    return GitPolicy(scripted, dialect=dialect, tool=TOOL, argument=ARGUMENT), scripted


def decide(dialect: Dialect, command: object, inner: object = ASK) -> PermissionDecision:
    built, _ = policy(dialect, inner)
    return built.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: command}))


# --- the normative examples of the contract ------------------------------------------------------

ALLOWED = [
    "git status",
    "git diff --stat",
    "git log --oneline -5",
    "git -C sub status",
    "git --no-pager log",
    "git --git-dir=.git --work-tree=. status",
    "git show HEAD",
    "git blame a.py",
    "git branch",
    "git branch -a",
    "git tag -l",
    "git stash list",
    "git status && git diff",
]
DELEGATED = ["git status && ls", "git log | head"]
ASKED_EVEN_IF_INNER_ALLOWS = [
    'git commit -m "x"',
    "git push origin main",
    "git merge rama",
    "git add .",
    "git switch -c nueva",
    "git checkout -b nueva",
    "git branch nueva",
    "git rebase main",
    "git st",
    "git frobnicate",
    "git -c alias.x=push x",
    "git -c core.pager=less log",
    "git --exec-path=/x status",
    "git diff --output=x",
    "git log --ext-diff",
    "git diff --no-index a b",
    "git log > x",
    "git grep -O foo",
    "git restore --staged a.py",
    "git reset HEAD~1",
    "git branch -d x",
    "git cherry-pick x",
    "git revert x",
]
DENIED = [
    "git reset --hard",
    "git reset --ha",
    "git clean -n",
    "git clean -fd",
    "git push --force",
    "git push --forc",
    "git push -fu origin main",
    "git push origin +main",
    "git push origin :rama",
    "git push --mirror",
    "git checkout -- a.py",
    "git checkout .",
    "git checkout -f",
    "git restore a.py",
    "git switch --discard-changes main",
    "git branch -D x",
    "git branch -Df x",
    "git stash drop",
    "git reflog expire --all",
    "git gc --prune=now",
    "git filter-branch",
    "git update-ref -d HEAD",
    "git status && git reset --hard",
]


@pytest.mark.parametrize("dialect", BOTH)
@pytest.mark.parametrize("command", ALLOWED)
def test_reads_are_allowed(dialect: Dialect, command: str) -> None:
    assert decide(dialect, command) is ALLOW


@pytest.mark.parametrize("command", ["/usr/bin/git status", "sudo git log"])
def test_bash_reads_with_a_path_or_a_wrapper_are_allowed(command: str) -> None:
    assert decide(BASH, command) is ALLOW


@pytest.mark.parametrize("command", ["git.exe status", "C:\\Git\\cmd\\git.exe log"])
def test_powershell_reads_with_git_exe_are_allowed(command: str) -> None:
    assert decide(PS, command) is ALLOW


@pytest.mark.parametrize("dialect", BOTH)
@pytest.mark.parametrize("command", DELEGATED)
@pytest.mark.parametrize("inner", [ASK, DENY, ALLOW])
def test_reads_mixed_with_other_programs_delegate(
    dialect: Dialect, command: str, inner: PermissionDecision
) -> None:
    assert decide(dialect, command, inner) is inner


@pytest.mark.parametrize("dialect", BOTH)
@pytest.mark.parametrize("command", ASKED_EVEN_IF_INNER_ALLOWS)
@pytest.mark.parametrize("inner", [ASK, ALLOW, DENY])
def test_writes_and_unknown_are_asked_without_the_inner_policy(
    dialect: Dialect, command: str, inner: PermissionDecision
) -> None:
    built, scripted = policy(dialect, inner)

    decision = built.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: command}))

    assert decision is ASK
    assert scripted.received == []


@pytest.mark.parametrize("dialect", BOTH)
@pytest.mark.parametrize("command", DENIED)
@pytest.mark.parametrize("inner", [ASK, ALLOW])
def test_destructive_variants_are_denied(
    dialect: Dialect, command: str, inner: PermissionDecision
) -> None:
    assert decide(dialect, command, inner) is DENY


# --- mixed chains, nested text and GIT_* ---------------------------------------------------------

MIXED = [
    (BASH, "git status && git diff", ALLOW),
    (BASH, "git status && rm x", ASK),
    (BASH, "git status && git push", ASK),
    (BASH, "git status && git reset --hard", DENY),
    (BASH, "git log | head", ASK),
    (BASH, "git status; git log\ngit diff", ALLOW),
    (BASH, 'bash -c "git push --force"', DENY),
    (BASH, "echo $(git clean -fd)", DENY),
    (BASH, 'bash -c "echo $(git clean -fd)"', DENY),
    (BASH, "echo $(echo $(git push -f))", DENY),
    (BASH, 'bash -c "git status"', ASK),
    (BASH, "echo $(git status)", ASK),
    (BASH, "GIT_EXTERNAL_DIFF=x git diff", ASK),
    (BASH, "env GIT_SSH_COMMAND=x git status", ASK),
    (BASH, "LANG=C git status", ALLOW),
    (BASH, "GIT_TRACE=1 git push --force", DENY),
    (PS, "git status; git diff", ALLOW),
    (PS, "git status; Remove-Item x", ASK),
    (PS, "git status && git push", ASK),
    (PS, "git status | git reset --hard", DENY),
    (PS, 'pwsh -Command "git push --force"', DENY),
    (PS, "echo $(git clean -fd)", DENY),
    (PS, '$env:GIT_PAGER = "x"; git log', ASK),
]


@pytest.mark.parametrize(("dialect", "command", "expected"), MIXED)
def test_mixed_and_nested_commands(
    dialect: Dialect, command: str, expected: PermissionDecision
) -> None:
    assert decide(dialect, command) is expected


def test_reads_inside_another_interpreter_are_not_allowed_here_but_delegated() -> None:
    # GitPolicy never allows them itself; CommandPolicy (outside) lowers any ALLOW of a command
    # it does not understand (``bash -c`` runs text), as the composition test checks.
    assert decide(BASH, 'bash -c "git status"', ALLOW) is ALLOW
    assert decide(BASH, 'bash -c "git status"', ASK) is ASK


# --- commands without git and other tools --------------------------------------------------------


@pytest.mark.parametrize("command", ["ls -la", "python -m pytest", "echo git push"])
@pytest.mark.parametrize("inner", [ASK, ALLOW, DENY])
def test_commands_without_git_delegate(command: str, inner: PermissionDecision) -> None:
    built, scripted = policy(BASH, inner)
    call = ToolCall(id="1", name=TOOL, arguments={ARGUMENT: command})

    assert built.evaluate(call) is inner
    assert scripted.received == [call]


def test_another_tool_delegates() -> None:
    built, scripted = policy(BASH, ALLOW)
    call = ToolCall(id="1", name="otra", arguments={ARGUMENT: "git push --force"})

    assert built.evaluate(call) is ALLOW
    assert scripted.received == [call]


@pytest.mark.parametrize("value", [None, 3, ["git", "status"]])
def test_an_argument_that_is_not_a_text_delegates(value: object) -> None:
    assert decide(BASH, value, ALLOW) is ALLOW
    assert decide(BASH, value, DENY) is DENY


# --- fail closed ----------------------------------------------------------------------------------


class TestFailClosed:
    def test_an_exception_while_classifying_is_ask(self) -> None:
        class Exploding(GitPolicy):
            def _all_parts(self, parsed: Any) -> list[Any]:
                raise RuntimeError(SENTINEL)

        built = Exploding(ScriptedPolicy({TOOL: ALLOW}), dialect=BASH, tool=TOOL, argument=ARGUMENT)

        decision = built.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: "git status"}))

        assert decision is ASK

    @pytest.mark.parametrize("raw", ["allow", None, 1])
    def test_a_value_that_is_not_a_decision_is_deny(self, raw: object) -> None:
        assert decide(BASH, "ls", raw) is DENY

    def test_an_exception_of_the_inner_policy_is_deny(self) -> None:
        assert decide(BASH, "ls", RuntimeError(SENTINEL)) is DENY

    @pytest.mark.parametrize(
        "call",
        [
            "not a call",
            ToolCall(id="1", name=3, arguments={}),  # type: ignore[arg-type]
            ToolCall(id="1", name=TOOL, arguments="git status"),  # type: ignore[arg-type]
        ],
    )
    def test_a_malformed_call_is_deny(self, call: Any) -> None:
        assert policy(BASH, ALLOW)[0].evaluate(call) is DENY

    def test_it_keeps_no_state_between_calls(self) -> None:
        built, _ = policy(BASH, ASK)

        def run(command: str) -> PermissionDecision:
            return built.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: command}))

        assert run("git status") is ALLOW
        assert run("git push --force") is DENY
        assert run("git status") is ALLOW
        assert run("git push") is ASK
        assert run("git status") is ALLOW

    def test_nothing_reproduces_the_command(self) -> None:
        built, _ = policy(BASH)
        command = f"git push --force https://servidor/{SENTINEL}.git"

        decision = built.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: command}))

        assert decision is DENY
        assert SENTINEL not in repr(decision)


class TestTheConstructor:
    def test_the_inner_policy_must_be_a_policy(self) -> None:
        with pytest.raises(TypeError):
            GitPolicy(object(), dialect=BASH, tool=TOOL, argument=ARGUMENT)  # type: ignore[arg-type]

    def test_the_dialect_must_be_a_dialect(self) -> None:
        with pytest.raises(TypeError):
            GitPolicy(ScriptedPolicy(), dialect="bash", tool=TOOL, argument=ARGUMENT)  # type: ignore[arg-type]

    @pytest.mark.parametrize(("tool", "argument"), [("", ARGUMENT), (TOOL, " "), (3, ARGUMENT)])
    def test_the_names_must_be_texts(self, tool: object, argument: object) -> None:
        with pytest.raises(TypeError):
            GitPolicy(ScriptedPolicy(), dialect=BASH, tool=tool, argument=argument)  # type: ignore[arg-type]

    def test_it_is_a_permission_policy_exported_by_the_core(self) -> None:
        assert isinstance(policy(BASH)[0], PermissionPolicy)
        for name in ("GitPolicy", "GitClass", "classify_git", "git_instructions"):
            assert name in core.__all__, name


def test_the_git_instructions_for_the_model() -> None:
    text = git_instructions()

    assert "rama" in text and "tarea" in text
    assert "commit" in text and "descriptivos" in text
    assert "push" in text and "merge" in text and "aprobación" in text
    assert "git status" in text


# --- the deny and ask lists of tools (HU-05-01), applied without asking the inner policy --------


def with_lists(deny: tuple[str, ...] = (), ask: tuple[str, ...] = ()) -> GitPolicy:
    return GitPolicy(
        ScriptedPolicy({TOOL: ALLOW}),
        dialect=BASH,
        tool=TOOL,
        argument=ARGUMENT,
        deny_names=deny,
        ask_names=ask,
    )


@pytest.mark.parametrize("command", ["git status", "git push origin main", "git reset --hard"])
def test_the_tool_in_the_deny_list_denies_every_git_call(command: str) -> None:
    built = with_lists(deny=(TOOL,))

    assert built.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: command})) is DENY


@pytest.mark.parametrize(
    ("command", "expected"),
    [("git status", ASK), ("git push origin main", ASK), ("git reset --hard", DENY)],
)
def test_the_tool_in_the_ask_list_is_never_allowed(
    command: str, expected: PermissionDecision
) -> None:
    built = with_lists(ask=(TOOL,))

    assert built.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: command})) is expected


def test_the_lists_of_other_tools_change_nothing() -> None:
    built = with_lists(deny=("otra",), ask=("otra",))

    assert built.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: "git status"})) is ALLOW


def test_without_git_the_lists_are_left_to_the_inner_policy() -> None:
    built = with_lists(deny=(TOOL,))

    assert built.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: "ls"})) is ALLOW


@pytest.mark.parametrize("names", [None, "shell", [3], [""]])
def test_the_lists_must_be_sequences_of_names(names: object) -> None:
    with pytest.raises(TypeError):
        GitPolicy(ScriptedPolicy(), dialect=BASH, tool=TOOL, argument=ARGUMENT, deny_names=names)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        GitPolicy(ScriptedPolicy(), dialect=BASH, tool=TOOL, argument=ARGUMENT, ask_names=names)  # type: ignore[arg-type]
