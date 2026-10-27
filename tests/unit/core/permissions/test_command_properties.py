"""Properties of the command analysis checked with random inputs (HU-05-02 / T006).

Only the standard library: ``random.Random`` with a fixed seed, so every run sees the same
inputs (no flakiness) and a failure can be reproduced. Nothing runs: commands are only analyzed.

1. ``parse_command`` and ``CommandPolicy.evaluate`` never raise, whatever the text (control
   characters, unterminated quotes, separators, substitutions, very long texts, non-ASCII).
2. A command that holds a denied command in a part that runs (chained with a random separator,
   inside ``$( … )``, backticks, ``bash -c '…'`` or ``pwsh -Command "…"``, one to three levels
   deep) is always denied, even when the wrapped policy would allow it. A meta-test checks that
   this property catches a policy that ignores the text that runs.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator

import pytest

from harness_agent.core import (
    CommandPolicy,
    DenyList,
    Dialect,
    ParsedCommand,
    PermissionDecision,
    ToolCall,
    parse_command,
)
from tests.doubles import ScriptedPolicy
from tests.unit.core.permissions.test_command_policy import (
    BASH_DENIED,
    BASH_USUAL,
    PS_DENIED,
    PS_USUAL,
    deny_list,
)

SEED = 20261026
CASES = 2_000
ALLOW, DENY = PermissionDecision.ALLOW, PermissionDecision.DENY
BASH, PS = Dialect.BASH, Dialect.POWERSHELL
TOOL, ARGUMENT = "ejecutar", "texto"

TRICKY = (
    list("abcxyz019 -_./\\~*?=:,")
    + list("'\"`$(){}[]<>|&;#!@%^")
    + ["\n", "\r", "\t", "\x00", "\x07", "\x1b", "\x7f", "ñ", "é", "€", " ", "😀"]
    + ["&&", "||", "$(", "${", "<<", ">>", "2>&1", "`", "-c ", "bash ", "pwsh -Command "]
    + ["rm -rf /", "shutdown", "Stop-Computer", "iex ", "cmd /c ", "--% "]
)


def random_texts(generator: random.Random) -> Iterator[str]:
    for index in range(CASES):
        if index % 200 == 0:
            length = generator.randint(5_000, 20_000)
        else:
            length = generator.randint(0, 60)
        yield "".join(generator.choice(TRICKY) for _ in range(length))


@pytest.mark.parametrize("dialect", [BASH, PS])
def test_the_parser_and_the_policy_never_raise(dialect: Dialect) -> None:
    generator = random.Random(SEED + (0 if dialect is BASH else 1))
    rules = deny_list(dialect)
    policy = CommandPolicy(ScriptedPolicy({TOOL: ALLOW}), rules, tool=TOOL, argument=ARGUMENT)
    for text in random_texts(generator):
        parsed = parse_command(text, dialect, aliases=rules.aliases, synonyms=rules.synonyms)
        assert isinstance(parsed, ParsedCommand)
        decision = policy.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: text}))
        assert isinstance(decision, PermissionDecision)


# --- property 2 ---------------------------------------------------------------------------------

BASH_SEPARATORS = (" && ", " || ", " ; ", " | ", " & ", "\n")
PS_SEPARATORS = (" ; ", " | ", " && ", " || ", "\n")


def _chain(
    generator: random.Random, inner: str, separators: tuple[str, ...], usual: list[str]
) -> str:
    other = generator.choice(usual)
    separator = generator.choice(separators)
    return (
        f"{other}{separator}{inner}" if generator.random() < 0.5 else f"{inner}{separator}{other}"
    )


def hidden_bash(generator: random.Random) -> str:
    """A denied bash command hidden one to three levels deep in text that runs."""
    text = generator.choice(BASH_DENIED)
    quoted_used = backtick_used = False
    for _ in range(generator.randint(1, 3)):
        choice = generator.randrange(5)
        if choice == 0:
            text = _chain(generator, text, BASH_SEPARATORS, BASH_USUAL_PLAIN)
        elif choice == 1:
            text = f"echo $({text})"
        elif choice == 2 and not backtick_used:
            backtick_used = True
            text = f"echo `{text}`"
        elif choice == 3 and not quoted_used:
            quoted_used = True
            text = f"bash -c '{text}'"
        else:
            text = f"ls > $({text})"
    return text


def hidden_powershell(generator: random.Random) -> str:
    """A denied PowerShell command hidden one to three levels deep in text that runs."""
    text = generator.choice(PS_DENIED)
    quoted_used = False
    for _ in range(generator.randint(1, 3)):
        choice = generator.randrange(3)
        if choice == 0:
            text = _chain(generator, text, PS_SEPARATORS, PS_USUAL_PLAIN)
        elif choice == 1 and not quoted_used:
            quoted_used = True
            text = f'pwsh -Command "{text}"'
        else:
            text = f"echo $({text})"
    return text


# Usual commands without quotes, so that the generated nesting stays analyzable.
BASH_USUAL_PLAIN = [c for c in BASH_USUAL if not any(q in c for q in "'\"")]
PS_USUAL_PLAIN = [c for c in PS_USUAL if not any(q in c for q in "'\"")]


def _decisions(
    policy: CommandPolicy, generator: random.Random, hide: Callable[[random.Random], str]
) -> Iterator[tuple[str, PermissionDecision]]:
    for _ in range(CASES):
        command = hide(generator)
        yield command, policy.evaluate(ToolCall(id="1", name=TOOL, arguments={ARGUMENT: command}))


CASES_BY_DIALECT = [(BASH, hidden_bash), (PS, hidden_powershell)]


@pytest.mark.parametrize(("dialect", "hide"), CASES_BY_DIALECT)
def test_a_denied_command_in_text_that_runs_is_always_denied(
    dialect: Dialect, hide: Callable[[random.Random], str]
) -> None:
    generator = random.Random(SEED + 10 + (0 if dialect is BASH else 1))
    policy = CommandPolicy(
        ScriptedPolicy({TOOL: ALLOW}), deny_list(dialect), tool=TOOL, argument=ARGUMENT
    )
    for command, decision in _decisions(policy, generator, hide):
        assert decision is DENY, command
        assert decision is not ALLOW


class _TopLevelOnly(DenyList):
    """A mutant that ignores the text that runs: it only looks at the top-level parts."""

    def denies(self, parsed: ParsedCommand, raw: str) -> bool:
        return any(rule.matches(part) for part in parsed.parts for rule in self.rules)


@pytest.mark.parametrize(("dialect", "hide"), CASES_BY_DIALECT)
def test_the_property_catches_a_policy_that_ignores_the_text_that_runs(
    dialect: Dialect, hide: Callable[[random.Random], str]
) -> None:
    generator = random.Random(SEED + 10 + (0 if dialect is BASH else 1))
    real = deny_list(dialect)
    mutant = _TopLevelOnly(
        dialect, real.base, real.extra, aliases=real.aliases, synonyms=real.synonyms
    )
    policy = CommandPolicy(ScriptedPolicy({TOOL: ALLOW}), mutant, tool=TOOL, argument=ARGUMENT)

    escaped = [
        command for command, decision in _decisions(policy, generator, hide) if decision is not DENY
    ]

    assert escaped, "the property did not tell the mutant apart"
