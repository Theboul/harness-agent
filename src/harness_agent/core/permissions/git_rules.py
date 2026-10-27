"""Rules for git through the shell: classify each git call and decide (HU-11-02).

``classify_git`` reads one git part of a command (as ``parse_command`` of HU-05-02 returns it)
and gives its class with the data of ``git_table``: a **read** (allowed without asking if the
whole command is reads), **ask** (writes, unknown subcommands, aliases, risky global options,
reads with effects) or **deny** (destructive variants). Git compares options exactly, so the
comparison is case-sensitive in every dialect. A prefix of a long option counts as the option; a
prefix of a destructive one denies even if it could also be the prefix of another option.

``GitPolicy`` sits between ``CommandPolicy`` (HU-05-02) and ``ExactCallPolicy`` (HU-11-03):

* a destructive git call in any part of the command (also inside ``$( )`` or ``bash -c``)
  denies the whole command;
* any git call that is asked returns ``ASK`` without asking the wrapped policy, so a task
  declaration can never let a push or a merge run by itself;
* the ``deny`` and ``ask`` lists of tools of the configuration (HU-05-01) come by constructor and
  are applied here too, without asking the wrapped policy: with the tool in ``deny`` every git
  call is denied, with it in ``ask`` none is allowed by itself;
* it allows only when every part of the command is a git read and the command was understood
  (no text that runs, no redirection, no ``GIT_*`` assignment);
* anything else is decided by the wrapped policy.

It fails closed: an exception while classifying asks, and an exception or an odd value of the
wrapped policy denies. Nothing here runs git, reads its configuration or looks up aliases.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy
from harness_agent.core.permissions import git_table
from harness_agent.core.permissions.command_parser import (
    CommandPart,
    Dialect,
    ParsedCommand,
    parse_command,
)

_GIT = "git"


class GitClass(str, Enum):
    """The class of one git call; ``DENY`` > ``ASK`` > ``READ``."""

    READ = "lectura"
    ASK = "preguntar"
    DENY = "denegar"


@dataclass
class _Arguments:
    """The arguments of a subcommand, split into options and positionals."""

    long: list[str] = field(default_factory=list)
    long_values: dict[str, str] = field(default_factory=dict)
    short: set[str] = field(default_factory=set)
    positionals: list[str] = field(default_factory=list)
    double_dash: bool = False


def _split(words: tuple[str, ...]) -> _Arguments:
    found = _Arguments()
    for index, word in enumerate(words):
        if word == "--":
            found.double_dash = True
            found.positionals.extend(words[index + 1 :])
            break
        if word.startswith("--") and len(word) > 2:
            name, _, value = word.partition("=")
            found.long.append(name)
            if value:
                found.long_values[name] = value
        elif word.startswith("-") and len(word) > 1:
            found.short.update(word[1:])
        else:
            found.positionals.append(word)
    return found


def _is_prefix_of_any(given: str, options: frozenset[str]) -> bool:
    """Whether the long option ``given`` is one of ``options`` or a prefix of one."""
    return len(given) > 2 and any(option.startswith(given) for option in options)


def _has(arguments: _Arguments, short: frozenset[str], long: frozenset[str]) -> bool:
    return bool(arguments.short & short) or any(
        _is_prefix_of_any(given, long) for given in arguments.long
    )


def _global_options(words: tuple[str, ...]) -> tuple[int, bool]:
    """The index of the subcommand and whether a risky global option came before it."""
    index, risky = 0, False
    while index < len(words) and words[index].startswith("-"):
        word = words[index]
        name = word.split("=", 1)[0]
        if name in git_table.KNOWN_GLOBAL_WITH_VALUE:
            index += 1 if "=" in word else 2
        elif word in git_table.KNOWN_GLOBAL_FLAGS:
            index += 1
        else:
            risky = True
            index += 2 if word == "-c" else 1
    return index, risky


def _destructive(subcommand: str, arguments: _Arguments) -> bool:
    if subcommand in git_table.ALWAYS_DESTRUCTIVE:
        return True
    if _has(
        arguments,
        git_table.DESTRUCTIVE_SHORT.get(subcommand, frozenset()),
        git_table.DESTRUCTIVE_LONG.get(subcommand, frozenset()),
    ):
        return True
    first = arguments.positionals[0] if arguments.positionals else ""
    if subcommand == "push":
        return any(p.startswith(git_table.PUSH_DESTRUCTIVE_REFSPECS) for p in arguments.positionals)
    if subcommand == "checkout":
        return arguments.double_dash or bool(
            set(arguments.positionals) & git_table.CHECKOUT_DESTRUCTIVE_PATHS
        )
    if subcommand == "restore":
        staged = _has(arguments, *git_table.RESTORE_STAGED)
        return not staged or _has(arguments, *git_table.RESTORE_WORKTREE)
    if subcommand == "branch":
        short_delete, long_delete, short_force, long_force = git_table.BRANCH_FORCE_DELETE
        return _has(arguments, short_delete, long_delete) and _has(
            arguments, short_force, long_force
        )
    if subcommand == "stash":
        return first in git_table.STASH_DESTRUCTIVE_ACTIONS
    if subcommand == "reflog":
        return first in git_table.REFLOG_DESTRUCTIVE_ACTIONS
    if subcommand == "gc":
        return _gc_prunes_now(arguments)
    return False


def _gc_prunes_now(arguments: _Arguments) -> bool:
    """``gc --prune=now`` or ``gc --prune now``."""
    if "--prune" not in arguments.long:
        return False
    value = arguments.long_values.get("--prune")
    if value is None:
        value = arguments.positionals[0] if arguments.positionals else ""
    return value in git_table.GC_DESTRUCTIVE_PRUNE


def _read(subcommand: str, arguments: _Arguments) -> bool:
    """Whether the subcommand, with these arguments, only reads (before effects are checked)."""
    if subcommand in git_table.READ_SUBCOMMANDS:
        return True
    if subcommand == "stash":
        return bool(arguments.positionals) and (
            arguments.positionals[0] in git_table.STASH_READ_ACTIONS
        )
    if subcommand in git_table.LISTING_SHORT:
        short = git_table.LISTING_SHORT[subcommand]
        long = git_table.LISTING_LONG[subcommand]
        if not arguments.short <= short or not all(given in long for given in arguments.long):
            return False
        patterns = bool(arguments.short & git_table.LIST_PATTERN_SHORT) or any(
            given in git_table.LIST_PATTERN_LONG for given in arguments.long
        )
        return not arguments.positionals or patterns
    return False


def _has_effects(subcommand: str, arguments: _Arguments, part: CommandPart) -> bool:
    if part.redirect_targets:
        return True
    if any(_is_prefix_of_any(given, git_table.READ_EFFECT_LONG) for given in arguments.long):
        return True
    return subcommand == "grep" and _has(
        arguments, git_table.GREP_EFFECT_SHORT, git_table.GREP_EFFECT_LONG
    )


def classify_git(part: CommandPart, *, risky_environment: bool = False) -> GitClass:
    """The class of one git call.

    Args:
        part: A part whose program is git, as ``parse_command`` returns it.
        risky_environment: The command assigns a ``GIT_*`` variable: a read is asked.

    Raises:
        ValueError: The part is not a git call.
    """
    if part.program != _GIT:
        raise ValueError("La parte no es una llamada a git.")
    words = part.arguments
    index, risky = _global_options(words)
    if index >= len(words):
        return GitClass.ASK
    subcommand = words[index]
    arguments = _split(words[index + 1 :])
    if _destructive(subcommand, arguments):
        return GitClass.DENY
    if risky or risky_environment or not _read(subcommand, arguments):
        return GitClass.ASK
    if _has_effects(subcommand, arguments, part):
        return GitClass.ASK
    return GitClass.READ


# --- the policy ---------------------------------------------------------------------------------

_GIT_ASSIGNMENT = re.compile(r"(?:^|[\s;&|(`])GIT_[A-Za-z0-9_]*=")
_INSTRUCTIONS = (
    "Uso de git en esta tarea: trabaja en una rama propia de la tarea (por ejemplo, créala con "
    "git switch -c <nombre>) y haz commits pequeños con mensajes descriptivos que digan qué "
    "cambia y por qué. git status, git diff, git log y otras consultas se ejecutan sin preguntar; "
    "commit, push, merge, add y crear ramas piden aprobación; reset --hard, clean, push --force y "
    "otras operaciones destructivas se deniegan."
)


def git_instructions() -> str:
    """The instructions about git that the model receives at the start (HU-11-02, Sp2-44)."""
    return _INSTRUCTIONS


class _Verdict(str, Enum):
    DENY = "denegar"
    ASK = "preguntar"
    DELEGATE = "delegar"
    READS = "lecturas"


def _is_name(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _names(value: object, what: str) -> frozenset[str]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TypeError(f"{what} deben ser una secuencia de nombres.")
    if not all(_is_name(name) for name in value):
        raise TypeError(f"{what} deben ser una secuencia de nombres.")
    return frozenset(value)


class GitPolicy(PermissionPolicy):
    """Deny destructive git calls, ask writes, allow only pure reads; delegate the rest.

    Args:
        inner: The policy that decides the calls this one does not decide.
        dialect: The dialect of the shell (bash or PowerShell).
        tool: Name of the tool whose argument is a command.
        argument: Name of the argument that holds the command.
        deny_names: Tools that are always denied (the ``deny`` list of the configuration).
        ask_names: Tools that are always asked (the ``ask`` list of the configuration).
    """

    def __init__(
        self,
        inner: PermissionPolicy,
        *,
        dialect: Dialect,
        tool: str,
        argument: str,
        deny_names: Sequence[str] = (),
        ask_names: Sequence[str] = (),
    ) -> None:
        if not isinstance(inner, PermissionPolicy):
            raise TypeError(
                f"La política envuelta debe ser un PermissionPolicy, no '{type(inner).__name__}'."
            )
        if not isinstance(dialect, Dialect):
            raise TypeError("El dialecto debe ser un Dialect.")
        if not _is_name(tool) or not _is_name(argument):
            raise TypeError("La herramienta y su argumento deben ser nombres.")
        self._inner = inner
        self._dialect = dialect
        self._tool = tool
        self._argument = argument
        self._deny_names = _names(deny_names, "Las herramientas denegadas")
        self._ask_names = _names(ask_names, "Las herramientas que se preguntan")

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        """Decide the git parts of a shell command; anything else is left to ``inner``."""
        try:
            if (
                not isinstance(call, ToolCall)
                or not isinstance(call.name, str)
                or not isinstance(call.arguments, dict)
            ):
                return PermissionDecision.DENY
            if call.name != self._tool:
                return self._inner_decision(call)
            try:
                verdict = self._verdict(call.arguments.get(self._argument))
            except Exception:
                return PermissionDecision.ASK
            if verdict is not _Verdict.DELEGATE:
                if verdict is _Verdict.DENY or call.name in self._deny_names:
                    return PermissionDecision.DENY
                if verdict is _Verdict.ASK or call.name in self._ask_names:
                    return PermissionDecision.ASK
            if self._only_reads(verdict) is True:
                return PermissionDecision.ALLOW
            return self._inner_decision(call)
        except Exception:
            return PermissionDecision.DENY

    def _inner_decision(self, call: ToolCall) -> PermissionDecision:
        decision: object = self._inner.evaluate(call)
        if not isinstance(decision, PermissionDecision):
            return PermissionDecision.DENY
        return decision

    @staticmethod
    def _only_reads(verdict: _Verdict) -> bool:
        return verdict is _Verdict.READS

    def _verdict(self, command: object) -> _Verdict:
        if not isinstance(command, str):
            return _Verdict.DELEGATE
        parsed = parse_command(command, self._dialect)
        risky = _GIT_ASSIGNMENT.search(command) is not None
        classes: list[GitClass] = []
        other_programs = False
        for part, top in self._all_parts(parsed):
            if part.program == _GIT:
                classes.append(classify_git(part, risky_environment=risky))
            elif top:
                other_programs = True
        if not classes:
            return _Verdict.DELEGATE
        if GitClass.DENY in classes:
            return _Verdict.DENY
        if GitClass.ASK in classes:
            return _Verdict.ASK
        if other_programs or not parsed.understood or parsed.executable:
            return _Verdict.DELEGATE
        return _Verdict.READS

    def _all_parts(self, parsed: ParsedCommand) -> list[tuple[CommandPart, bool]]:
        """Every part of the command, at the top level (``True``) or in text that runs."""
        found = [(part, True) for part in parsed.parts]
        pending = list(parsed.executable)
        while pending:
            inner = pending.pop()
            found.extend((part, False) for part in inner.parts)
            pending.extend(inner.executable)
        return found
