"""Properties of the git rules checked with random inputs (HU-11-02 / T004).

Only the standard library: ``random.Random`` with a fixed seed, so every run sees the same inputs
and a failure can be reproduced. Nothing runs: commands are only analyzed.

1. ``classify_git`` and ``GitPolicy.evaluate`` never raise, whatever the git arguments (odd
   options, unterminated quotes, control characters, long texts).
2. A command that holds a destructive git call in a part that runs (chained with a random
   separator, inside ``$( … )``, ``bash -c '…'`` or ``pwsh -Command "…"``, with random global
   options in front) is never allowed, even when the wrapped policy allows; and it is denied.
   A meta-test checks that this property catches a policy that ignores the text that runs.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from harness_agent.core import (
    CommandPart,
    Dialect,
    GitPolicy,
    PermissionDecision,
    ToolCall,
    classify_git,
    parse_command,
)
from tests.doubles import ScriptedPolicy
from tests.unit.core.permissions.test_git_policy import DENIED

SEED = 20261027
CASES = 2_000
ALLOW, DENY = PermissionDecision.ALLOW, PermissionDecision.DENY
BASH, PS = Dialect.BASH, Dialect.POWERSHELL
TOOL, ARGUMENT = "ejecutar", "texto"

PIECES = (
    ["status", "diff", "log", "push", "reset", "clean", "checkout", "branch", "stash", "gc"]
    + ["--force", "--forc", "-f", "-fd", "--hard", "--", ".", "+main", ":rama", "-C", "-c"]
    + ["--no-pager", "--git-dir=", "--output=x", "-O", "drop", "list", "-D", "--prune=now"]
    + ["'", '"', "`", "$(", ")", ";", "&&", "|", ">", "\n", "\x00", "\x1b", "ñ", "😀", "="]
    + ["GIT_X=1", "a", "x" * 50]
)
SINGLE_DESTRUCTIVE = [command for command in DENIED if "&&" not in command]
GLOBALS = ["", "-C sub ", "--no-pager ", "-c a.b=c ", "--git-dir=.git ", "-P "]


def random_commands(generator: random.Random) -> Iterator[str]:
    for index in range(CASES):
        size = generator.randint(5_000, 12_000) if index % 250 == 0 else generator.randint(0, 12)
        words = (generator.choice(PIECES) for _ in range(size))
        yield "git " + " ".join(words)


def git_parts(command: str, dialect: Dialect) -> list[CommandPart]:
    parsed = parse_command(command, dialect)
    pending = [parsed]
    found: list[CommandPart] = []
    while pending:
        current = pending.pop()
        found.extend(p for p in current.parts if p.program == "git")
        pending.extend(current.executable)
    return found


@pytest.mark.parametrize("dialect", [BASH, PS])
def test_the_rules_and_the_policy_never_raise(dialect: Dialect) -> None:
    generator = random.Random(SEED + (0 if dialect is BASH else 1))
    policy = GitPolicy(ScriptedPolicy({TOOL: ALLOW}), dialect=dialect, tool=TOOL, argument=ARGUMENT)
    for command in random_commands(generator):
        for part in git_parts(command, dialect):
            classify_git(part, risky_environment=generator.random() < 0.5)
        decision = policy.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: command}))
        assert isinstance(decision, PermissionDecision)


# --- property 2 -----------------------------------------------------------------------------------

USUAL = ["git status", "ls", "git log --oneline", "python -m pytest", "git diff"]
BASH_SEPARATORS = (" && ", " || ", " ; ", " | ", " & ", "\n")
PS_SEPARATORS = (" ; ", " | ", " && ", " || ", "\n")


def with_globals(generator: random.Random, command: str) -> str:
    return command.replace("git ", "git " + generator.choice(GLOBALS), 1)


def hidden_bash(generator: random.Random) -> str:
    text = with_globals(generator, generator.choice(SINGLE_DESTRUCTIVE))
    quoted_used = False
    for _ in range(generator.randint(1, 3)):
        choice = generator.randrange(3)
        if choice == 0:
            separator = generator.choice(BASH_SEPARATORS)
            other = generator.choice(USUAL)
            text = (
                f"{other}{separator}{text}"
                if generator.random() < 0.5
                else f"{text}{separator}{other}"
            )
        elif choice == 1 and not quoted_used:
            quoted_used = True
            text = f"bash -c '{text}'"
        else:
            text = f"echo $({text})"
    return text


def hidden_powershell(generator: random.Random) -> str:
    text = with_globals(generator, generator.choice(SINGLE_DESTRUCTIVE))
    quoted_used = False
    for _ in range(generator.randint(1, 3)):
        choice = generator.randrange(3)
        if choice == 0:
            separator = generator.choice(PS_SEPARATORS)
            other = generator.choice(USUAL)
            text = (
                f"{other}{separator}{text}"
                if generator.random() < 0.5
                else f"{text}{separator}{other}"
            )
        elif choice == 1 and not quoted_used:
            quoted_used = True
            text = f"pwsh -Command '{text}'"
        else:
            text = f"echo $({text})"
    return text


def decisions(
    policy: GitPolicy, generator: random.Random, hide: Callable[[random.Random], str]
) -> Iterator[tuple[str, PermissionDecision]]:
    for _ in range(CASES):
        command = hide(generator)
        yield command, policy.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: command}))


BY_DIALECT = [(BASH, hidden_bash), (PS, hidden_powershell)]


@pytest.mark.parametrize(("dialect", "hide"), BY_DIALECT)
def test_a_hidden_destructive_git_call_is_always_denied(
    dialect: Dialect, hide: Callable[[random.Random], str]
) -> None:
    generator = random.Random(SEED + 10 + (0 if dialect is BASH else 1))
    policy = GitPolicy(ScriptedPolicy({TOOL: ALLOW}), dialect=dialect, tool=TOOL, argument=ARGUMENT)
    for command, decision in decisions(policy, generator, hide):
        assert decision is not ALLOW, command
        assert decision is DENY, command


class _TopLevelOnly(GitPolicy):
    """A mutant that ignores the text that runs: only the top-level parts are looked at."""

    def _all_parts(self, parsed: Any) -> list[Any]:
        return [(part, True) for part in parsed.parts]


@pytest.mark.parametrize(("dialect", "hide"), BY_DIALECT)
def test_the_property_catches_a_policy_that_ignores_the_text_that_runs(
    dialect: Dialect, hide: Callable[[random.Random], str]
) -> None:
    generator = random.Random(SEED + 10 + (0 if dialect is BASH else 1))
    mutant = _TopLevelOnly(
        ScriptedPolicy({TOOL: ALLOW}), dialect=dialect, tool=TOOL, argument=ARGUMENT
    )

    escaped = [c for c, d in decisions(mutant, generator, hide) if d is not DENY]

    assert escaped, "the property did not tell the mutant apart"
