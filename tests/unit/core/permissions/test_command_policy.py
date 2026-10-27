"""Tests for ``CommandPolicy``, the policy that only hardens shell decisions (HU-05-02 / T005).

The wrapped policy is a ``ScriptedPolicy`` and the deny list is built here with the base entries of
HU-01-04, so the tests do not depend on the data of the adapter. Nothing runs: commands are only
analyzed. The tables include every normative example of
``specs/026-shell-deny-compound/contracts/command_policy_contract.md`` and the scenarios of the
spec, plus the batteries of SC-001 (chained denied), SC-002 (not understood) and SC-004 (usual
commands and false positives).
"""

from __future__ import annotations

from typing import Any

import pytest

import harness_agent.core as core
from harness_agent.core import (
    CommandPolicy,
    DenyList,
    Dialect,
    ParsedCommand,
    PermissionDecision,
    PermissionPolicy,
    ToolCall,
    compile_rule,
)
from tests.doubles import ScriptedPolicy

ALLOW, ASK, DENY = PermissionDecision.ALLOW, PermissionDecision.ASK, PermissionDecision.DENY
BASH, PS = Dialect.BASH, Dialect.POWERSHELL
TOOL, ARGUMENT = "ejecutar", "texto"
SENTINEL = "VALOR-DE-PRUEBA-123"

BASH_BASE = (
    "rm -rf /",
    "rm -rf ~",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",
    "shutdown",
    "reboot",
    "chmod -R 777 /",
)
PS_BASE = (
    "Remove-Item -Recurse -Force C:\\",
    "Format-Volume",
    "Clear-Disk",
    "Stop-Computer",
    "Restart-Computer",
    "Set-ExecutionPolicy",
    "reg delete",
)
PS_ALIASES = {name: "remove-item" for name in ("rm", "ri", "del", "erase", "rd", "rmdir")}
BASH_SYNONYMS = {
    "rm": {"--recursive": "-r", "--force": "-f", "-R": "-r"},
    "chmod": {"--recursive": "-R"},
}


def deny_list(dialect: Dialect) -> DenyList:
    patterns = BASH_BASE if dialect is BASH else PS_BASE
    aliases = PS_ALIASES if dialect is PS else {}
    synonyms = BASH_SYNONYMS if dialect is BASH else {}
    base = [
        compile_rule(p, "motivo", dialect, aliases=aliases, synonyms=synonyms, allow_literal=True)
        for p in patterns
    ]
    return DenyList(dialect, base, aliases=aliases, synonyms=synonyms)


def policy(dialect: Dialect, inner: object = ASK) -> tuple[CommandPolicy, ScriptedPolicy]:
    scripted = ScriptedPolicy({TOOL: inner, "otra": inner})
    return CommandPolicy(scripted, deny_list(dialect), tool=TOOL, argument=ARGUMENT), scripted


def decide(dialect: Dialect, command: object, inner: object = ASK) -> PermissionDecision:
    built, _ = policy(dialect, inner)
    return built.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: command}))


# --- the normative examples of the contract ------------------------------------------------------

NORMATIVE = [
    (BASH, "echo hola && rm -rf /", DENY, ASK),
    (BASH, "rm -fr ~/*", DENY, ASK),
    (BASH, "sudo /sbin/shutdown -h now", DENY, ASK),
    (BASH, "env X=1 reboot", DENY, ASK),
    (BASH, "dd if=/dev/zero of=a.img", DENY, ASK),
    (BASH, "echo $(shutdown now)", DENY, ASK),
    (BASH, 'bash -c "rm -rf /"', DENY, ASK),
    (BASH, "echo hola > $(reboot)", DENY, ASK),
    (BASH, "cat shutdown.log", ASK, ASK),
    (BASH, 'echo "no uses shutdown"', ASK, ASK),
    (BASH, 'git commit -m "fix: shutdown limpio"', ASK, ASK),
    (BASH, "rm -rf /tmp/build", ASK, ASK),
    (BASH, "echo $(whoami)", ASK, ALLOW),
    (BASH, 'bash -c "ls"', ASK, ALLOW),
    (BASH, "eval ls", ASK, ALLOW),
    (BASH, "rm -rf $HOME", ASK, ALLOW),
    (BASH, 'echo "abc', ASK, ALLOW),
    (PS, "dir | Stop-Computer", DENY, ASK),
    (PS, "ri -r -fo C:\\", DENY, ASK),
    (PS, "REMOVE-ITEM -Recurse -Force c:/*", DENY, ASK),
    (PS, 'pwsh -Command "Stop-Computer"', DENY, ASK),
    (PS, "Get-Content Stop-Computer.txt", ASK, ASK),
    (PS, "Remove-Item -Recurse -Force C:\\proyecto\\dist", ASK, ASK),
    (PS, 'iex "dir"', ASK, ALLOW),
    (PS, "& $x", ASK, ALLOW),
    (PS, "powershell -EncodedCommand AAAA", ASK, ALLOW),
    (PS, "{ dir }", ASK, ALLOW),
]


@pytest.mark.parametrize(("dialect", "command", "expected", "inner"), NORMATIVE)
def test_the_normative_examples_of_the_contract(
    dialect: Dialect, command: str, expected: PermissionDecision, inner: PermissionDecision
) -> None:
    assert decide(dialect, command, inner) is expected


# --- the scenarios of the spec ---------------------------------------------------------------

DENIED_SCENARIOS = [
    # US1, scenarios 1-3, 5-8
    (BASH, "echo hola && rm -rf /"),
    (BASH, "rm -rf / ; echo hola"),
    (BASH, "ls | shutdown now"),
    (PS, "Get-ChildItem; Format-Volume -DriveLetter D"),
    (PS, "dir | Stop-Computer"),
    (BASH, "rm -fr /"),
    (BASH, "rm -r -f /"),
    (BASH, "rm   -rf    /"),
    (BASH, "/bin/rm -rf /"),
    (BASH, "rm --recursive --force /"),
    (PS, "remove-item -FORCE -recurse C:\\"),
    (PS, "Del -Rec -Fo C:\\"),
    (BASH, "rm -rf /*"),
    (BASH, "rm -fr ~/*"),
    (BASH, "sudo /sbin/shutdown -h now"),
    (BASH, "env X=1 reboot"),
    (BASH, "dd if=/dev/zero of=archivo.img"),
    (BASH, "echo hola > $(reboot)"),
    (PS, "Remove-Item -Recurse -Force C:\\*"),
    (PS, "ri -r -fo C:\\"),
    (PS, 'pwsh -Command "Stop-Computer"'),
    (BASH, 'bash -c "rm -rf /"'),
    (BASH, "echo $(shutdown now)"),
    # US3, scenario 1b (an entry added by the configuration is covered in the bootstrap tests)
]


@pytest.mark.parametrize(("dialect", "command"), DENIED_SCENARIOS)
def test_the_denied_scenarios(dialect: Dialect, command: str) -> None:
    assert decide(dialect, command) is DENY
    assert decide(dialect, command, ALLOW) is DENY


FALSE_POSITIVES = [
    # US1, scenario 9
    (BASH, "cat shutdown.log"),
    (BASH, "grep reboot notas.txt"),
    (BASH, 'echo "no uses shutdown"'),
    (BASH, 'git commit -m "fix: shutdown limpio"'),
    (BASH, "rm -rf /tmp/build"),
    (BASH, "rm -rf ~/proyecto/dist"),
    (BASH, "chmod -R 777 ./dist"),
    (PS, "Get-Content Stop-Computer.txt"),
    (PS, "Remove-Item -Recurse -Force C:\\proyecto\\dist"),
]


@pytest.mark.parametrize(("dialect", "command"), FALSE_POSITIVES)
def test_the_false_positives_are_not_denied(dialect: Dialect, command: str) -> None:
    assert decide(dialect, command) is ASK
    assert decide(dialect, command, ALLOW) is ALLOW


NOT_UNDERSTOOD_SCENARIOS = [
    # US2, scenarios 1-3
    (BASH, "echo $(whoami)"),
    (BASH, "echo `date`"),
    (BASH, "cat <(ls)"),
    (BASH, 'bash -c "ls"'),
    (BASH, "echo 'abc"),
    (BASH, "echo a \\\nb"),
    (PS, "Invoke-Expression 'dir'"),
    (PS, 'iex "dir"'),
    (PS, "& $programa"),
    (PS, "{ dir }"),
    (PS, "echo $(Get-Date)"),
    (PS, "powershell -EncodedCommand AAAA"),
]


@pytest.mark.parametrize(("dialect", "command"), NOT_UNDERSTOOD_SCENARIOS)
def test_what_is_not_understood_is_asked_even_if_the_inner_policy_allows(
    dialect: Dialect, command: str
) -> None:
    # US2, scenario 4: a declared task command (HU-11-03) makes the inner policy say ALLOW.
    assert decide(dialect, command, ALLOW) is ASK
    assert decide(dialect, command, ASK) is ASK


# --- chained commands, one per separator --------------------------------------------------------

BASH_SEPARATORS = (" && ", " || ", " ; ", " | ", " & ", "\n")
PS_SEPARATORS = (" ; ", " | ", " && ", " || ", "\n")
BASH_DENIED = (
    "rm -rf /",
    "rm -rf ~",
    "mkfs.ext4 /dev/sda1",
    "dd if=/dev/zero of=/dev/sda",
    "shutdown now",
    "reboot",
    "chmod -R 777 /",
    "sudo reboot",
)
PS_DENIED = (
    "Remove-Item -Recurse -Force C:\\",
    "Format-Volume -DriveLetter D",
    "Clear-Disk -Number 1",
    "Stop-Computer",
    "Restart-Computer -Force",
    "Set-ExecutionPolicy Unrestricted",
    "reg delete HKLM\\x /f",
)


def chained(denied: tuple[str, ...], separators: tuple[str, ...]) -> list[str]:
    commands = []
    for command in denied:
        for separator in separators:
            commands.append(f"echo hola{separator}{command}")
            commands.append(f"{command}{separator}echo hola")
    return commands


BASH_CHAINED = chained(BASH_DENIED, BASH_SEPARATORS)
PS_CHAINED = chained(PS_DENIED, PS_SEPARATORS)


def test_the_chained_batteries_are_large_enough() -> None:
    # SC-001: at least 40 chained commands per dialect.
    assert len(BASH_CHAINED) >= 40
    assert len(PS_CHAINED) >= 40


@pytest.mark.parametrize("command", BASH_CHAINED)
def test_bash_chained_with_a_denied_part_is_denied(command: str) -> None:
    assert decide(BASH, command, ALLOW) is DENY


@pytest.mark.parametrize("command", PS_CHAINED)
def test_powershell_chained_with_a_denied_part_is_denied(command: str) -> None:
    assert decide(PS, command, ALLOW) is DENY


def test_the_denied_part_may_be_in_the_middle() -> None:
    assert decide(BASH, "ls && reboot && ls") is DENY
    assert decide(PS, "dir; Stop-Computer; dir") is DENY


# --- SC-002: not understood, never allowed ------------------------------------------------------

BASH_NOT_UNDERSTOOD = [
    "echo $(whoami)",
    "echo `date`",
    "cat <(ls)",
    "tee >(cat)",
    'bash -c "ls"',
    "sh -c 'ls'",
    "eval ls",
    "source x.sh",
    ". x.sh",
    "ls | xargs cat",
    "echo $HOME",
    "echo ${X}",
    "$CMD",
    "echo 'abc",
    'echo "abc',
    "echo a \\\nb",
    "cat << EOF",
    "cat <<< x",
    "(ls)",
    "{ ls; }",
    "ls # x",
    "a ;; b",
    "| b",
    "a &&",
    "echo $((1+2))",
    "! ls",
    "env -S 'ls'",
]
PS_NOT_UNDERSTOOD = [
    "echo $(Get-Date)",
    "@(dir)",
    "Invoke-Expression 'dir'",
    'iex "dir"',
    "Start-Process notepad",
    "Invoke-Command -ScriptBlock x",
    "powershell -EncodedCommand AAAA",
    "pwsh -enc AAAA",
    'pwsh -Command "dir"',
    "cmd /c dir",
    ". .\\x.ps1",
    "& notepad",
    "& $x",
    "{ dir }",
    "(dir)",
    "echo $env:PATH",
    "echo $x",
    'echo "hola $x"',
    "echo 'abc",
    'echo "abc',
    "dir `",
    "dir # x",
    "<# x #> dir",
    "dir < x",
    "@{a=1}",
    "dir --% /s",
    "a ;; b",
]


def test_the_not_understood_batteries_are_large_enough() -> None:
    assert len(BASH_NOT_UNDERSTOOD) >= 25
    assert len(PS_NOT_UNDERSTOOD) >= 25


@pytest.mark.parametrize("command", BASH_NOT_UNDERSTOOD)
def test_bash_not_understood_is_never_allowed(command: str) -> None:
    assert decide(BASH, command, ALLOW) is ASK


@pytest.mark.parametrize("command", PS_NOT_UNDERSTOOD)
def test_powershell_not_understood_is_never_allowed(command: str) -> None:
    assert decide(PS, command, ALLOW) is ASK


# --- SC-004: usual commands are never denied ----------------------------------------------------

BASH_USUAL = [
    "python -m pytest -q",
    "python -m ruff check .",
    "git status",
    "git diff",
    "git log --oneline -5",
    "ls -la",
    "cat README.md",
    "grep -rn shutdown src",
    "pip install -r requirements.txt",
    "mkdir -p build",
    "rm -rf build",
    "rm -f a.txt",
    "cp a b",
    "mv a b",
    "npm test",
    "make",
    "python -m pytest && python -m ruff check .",
    "git diff | head -20",
    "echo hola > salida.txt",
    "find . -name '*.py'",
    "chmod +x script.sh",
    "dd --help",
]
PS_USUAL = [
    "python -m pytest -q",
    "python -m ruff check .",
    "git status",
    "git diff",
    "Get-ChildItem",
    "dir",
    "Get-Content README.md",
    "Select-String -Pattern shutdown -Path src",
    "pip install -r requirements.txt",
    "New-Item -ItemType Directory build",
    "Remove-Item -Recurse -Force build",
    "Remove-Item a.txt",
    "Copy-Item a b",
    "Move-Item a b",
    "npm test",
    "python -m pytest; python -m ruff check .",
    "git diff | Select-Object -First 20",
    "echo hola > salida.txt",
    "Get-Process",
    "Test-Path x",
    "reg query HKCU\\x",
]


def test_the_usual_batteries_are_large_enough() -> None:
    assert len(BASH_USUAL) >= 20
    assert len(PS_USUAL) >= 20


@pytest.mark.parametrize("command", BASH_USUAL)
def test_bash_usual_commands_are_not_denied(command: str) -> None:
    assert decide(BASH, command) is ASK
    assert decide(BASH, command, ALLOW) is ALLOW


@pytest.mark.parametrize("command", PS_USUAL)
def test_powershell_usual_commands_are_not_denied(command: str) -> None:
    assert decide(PS, command) is ASK
    assert decide(PS, command, ALLOW) is ALLOW


# --- the transitions of the data model ----------------------------------------------------------


class TestTransitions:
    def test_another_tool_keeps_the_decision_of_the_inner_policy(self) -> None:
        built, scripted = policy(BASH, ALLOW)
        call = ToolCall(id="1", name="otra", arguments={ARGUMENT: "rm -rf /"})

        assert built.evaluate(call) is ALLOW
        assert scripted.received == [call]

    @pytest.mark.parametrize("inner", [ALLOW, ASK, DENY])
    def test_the_decision_of_the_inner_policy_when_understood_and_not_denied(
        self, inner: PermissionDecision
    ) -> None:
        assert decide(BASH, "ls -la", inner) is inner

    @pytest.mark.parametrize(("inner", "expected"), [(ALLOW, ASK), (ASK, ASK), (DENY, DENY)])
    def test_not_understood_lowers_only_an_allow(
        self, inner: PermissionDecision, expected: PermissionDecision
    ) -> None:
        assert decide(BASH, "echo $X", inner) is expected

    def test_a_denied_command_does_not_ask_the_inner_policy(self) -> None:
        built, scripted = policy(BASH, ALLOW)

        decision = built.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: "reboot"}))

        assert decision is DENY
        assert scripted.received == []

    @pytest.mark.parametrize("value", [None, 3, ["ls"], b"ls"])
    def test_an_argument_that_is_not_a_text_is_not_understood(self, value: object) -> None:
        assert decide(BASH, value, ALLOW) is ASK
        assert decide(BASH, value, DENY) is DENY

    def test_a_missing_argument_is_not_understood(self) -> None:
        built, _ = policy(BASH, ALLOW)

        assert built.evaluate(ToolCall(id="1", name=TOOL, arguments={})) is ASK

    @pytest.mark.parametrize("raw", ["allow", None, 1, "ALLOW"])
    def test_a_value_that_is_not_a_decision_is_deny(self, raw: object) -> None:
        assert decide(BASH, "ls", raw) is DENY

    def test_an_exception_of_the_inner_policy_is_deny(self) -> None:
        assert decide(BASH, "ls", RuntimeError(SENTINEL)) is DENY

    def test_an_exception_of_the_analysis_is_not_understood(self) -> None:
        class Exploding(DenyList):
            def denies(self, parsed: ParsedCommand, raw: str) -> bool:
                raise RuntimeError(SENTINEL)

        exploding = Exploding(BASH, deny_list(BASH).base)
        built = CommandPolicy(
            ScriptedPolicy({TOOL: ALLOW}), exploding, tool=TOOL, argument=ARGUMENT
        )

        decision = built.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: "ls"}))

        assert decision is ASK

    @pytest.mark.parametrize(
        "call",
        [
            "not a call",
            ToolCall(id="1", name=3, arguments={}),  # type: ignore[arg-type]
            ToolCall(id="1", name=TOOL, arguments="ls"),  # type: ignore[arg-type]
        ],
    )
    def test_a_malformed_call_is_deny(self, call: Any) -> None:
        built, _ = policy(BASH, ALLOW)

        assert built.evaluate(call) is DENY

    def test_it_keeps_no_state_between_calls(self) -> None:
        built, _ = policy(BASH, ALLOW)

        def run(command: str) -> PermissionDecision:
            return built.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: command}))

        assert run("ls") is ALLOW
        assert run("reboot") is DENY
        assert run("ls") is ALLOW
        assert run("echo $X") is ASK
        assert run("ls") is ALLOW

    def test_it_does_not_change_the_call(self) -> None:
        arguments = {ARGUMENT: f"echo {SENTINEL} && reboot"}
        call = ToolCall(id="1", name=TOOL, arguments=dict(arguments))

        policy(BASH)[0].evaluate(call)

        assert call.arguments == arguments


class TestTheConstructor:
    def test_the_inner_policy_must_be_a_policy(self) -> None:
        with pytest.raises(TypeError):
            CommandPolicy(object(), deny_list(BASH), tool=TOOL, argument=ARGUMENT)  # type: ignore[arg-type]

    def test_the_list_must_be_a_deny_list(self) -> None:
        with pytest.raises(TypeError):
            CommandPolicy(ScriptedPolicy(), [], tool=TOOL, argument=ARGUMENT)  # type: ignore[arg-type]

    @pytest.mark.parametrize(("tool", "argument"), [("", ARGUMENT), (TOOL, " "), (3, ARGUMENT)])
    def test_the_names_must_be_texts(self, tool: object, argument: object) -> None:
        with pytest.raises(TypeError):
            CommandPolicy(ScriptedPolicy(), deny_list(BASH), tool=tool, argument=argument)  # type: ignore[arg-type]

    def test_it_is_a_permission_policy_exported_by_the_core(self) -> None:
        assert isinstance(policy(BASH)[0], PermissionPolicy)
        assert "CommandPolicy" in core.__all__


def test_no_decision_or_error_reproduces_the_command() -> None:
    built, _ = policy(BASH)
    command = f"echo {SENTINEL} && reboot"

    decision = built.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: command}))

    assert decision is DENY
    assert SENTINEL not in repr(decision)
