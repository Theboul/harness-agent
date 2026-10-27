"""Deny rules compiled from command text, and the deny list in use (HU-05-02).

An entry of the list is written as the real command (``rm -rf /``, ``shutdown``, ``dd if=``) and
compiled with the same parser as the commands of the agent, so the base list and the entries of
the configuration share one syntax. The kind of rule follows from its words:

* one word (``shutdown``): **program**, only in the position of the program (never as an argument
  of another program); ``mkfs`` also covers ``mkfs.ext4``;
* program, options and a complete target (``rm -rf /``): **target**, only when the part has those
  options (in any order or combination) and one of its arguments is the root, ``~`` or a whole
  drive (``/``, ``/*``, ``~``, ``~/*``, ``C:\\``, ``C:\\*``…), never a path below them;
* program and one argument ending in ``=`` (``dd if=``): **prefix**;
* program and words (``reg delete``): **subcommand**, the words lead the arguments in order;
* ``> destination``: **redirection**, a redirection target starts with it;
* text the parser does not understand (the fork bomb): **literal**, only for the base list.

PowerShell is compared without case, and its parameters may be abbreviated: any prefix counts,
even an ambiguous one, because denying too much is safe and the real parameters of each cmdlet
cannot be looked up here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from harness_agent.core.permissions.command_parser import (
    CommandPart,
    Dialect,
    ParsedCommand,
    parse_command,
)

_MESSAGES = {
    "vacia": "La entrada de la lista de comandos denegados está vacía.",
    "no_se_entiende": "Una entrada de la lista de comandos denegados no se entiende.",
    "varias_partes": "Una entrada de la lista de comandos denegados tiene varios comandos.",
    "redireccion": "Una entrada de redirección de la lista de comandos denegados no es válida.",
    "motivo": "El motivo de una entrada de la lista de comandos denegados está vacío.",
}
_DRIVE = re.compile(r"[a-z]:")
_ROOT_CHARACTERS = frozenset("/*.")


class RuleError(ValueError):
    """An entry of the deny list cannot be compiled; ``code`` says why (never the entry)."""

    def __init__(self, code: str) -> None:
        super().__init__(_MESSAGES[code])
        self.code = code


class RuleKind(str, Enum):
    """How an entry matches a part of a command."""

    PROGRAM = "programa"
    TARGET = "objetivo"
    PREFIX = "prefijo"
    SUBCOMMAND = "subcomando"
    REDIRECT = "redireccion"
    LITERAL = "literal"


def is_complete_target(text: str, dialect: Dialect) -> bool:
    """Whether ``text`` is the root, the home folder or a whole drive (not a path below)."""
    target = text.strip()
    if dialect is Dialect.POWERSHELL:
        target = target.replace("\\", "/").lower()
        if _DRIVE.match(target):
            target = "/" + target[2:]
    if target.startswith("~"):
        return set(target[1:]) <= _ROOT_CHARACTERS
    return target.startswith("/") and set(target) <= _ROOT_CHARACTERS


@dataclass(frozen=True)
class CompiledRule:
    """One entry of the deny list, ready to compare with the parts of a command.

    Attributes:
        kind: How it matches.
        dialect: The dialect it was compiled for (PowerShell compares without case).
        program: The normalized program (empty for redirection and literal rules).
        options: The options a part must have (target and subcommand rules).
        words: The words of a subcommand, the other arguments of a target or the prefix.
        text: The start of the redirection target, or the literal text without spaces.
        reason: Why it is denied, in Spanish; never published.
    """

    kind: RuleKind
    dialect: Dialect
    program: str = ""
    options: frozenset[str] = frozenset()
    words: tuple[str, ...] = ()
    text: str = ""
    reason: str = ""

    def matches(self, part: CommandPart) -> bool:
        """Whether ``part`` is this denied command."""
        insensitive = self.dialect is Dialect.POWERSHELL
        if self.kind is RuleKind.LITERAL:
            return False
        if self.kind is RuleKind.REDIRECT:
            targets = (t.lower() if insensitive else t for t in part.redirect_targets)
            return any(target.startswith(self.text) for target in targets)
        program = part.program.lower() if insensitive else part.program
        if self.kind is RuleKind.PROGRAM:
            return program == self.program or program.startswith(self.program + ".")
        if program != self.program or not self._has_options(part.options):
            return False
        positionals = [p.lower() if insensitive else p for p in part.positionals]
        if self.kind is RuleKind.TARGET:
            return all(word in positionals for word in self.words) and any(
                is_complete_target(p, self.dialect) for p in part.positionals
            )
        if self.kind is RuleKind.PREFIX:
            return any(p.startswith(self.words[0]) for p in positionals)
        return tuple(positionals[: len(self.words)]) == self.words

    def matches_text(self, raw: str) -> bool:
        """Whether the raw command contains this literal rule (spaces are ignored)."""
        return self.kind is RuleKind.LITERAL and self.text in "".join(raw.split())

    def _has_options(self, options: frozenset[str]) -> bool:
        if self.dialect is not Dialect.POWERSHELL:
            return self.options <= options
        return all(
            any(len(given) > 1 and required.startswith(given) for given in options)
            for required in self.options
        )


def compile_rule(
    pattern: str,
    reason: str,
    dialect: Dialect,
    *,
    aliases: Mapping[str, str] | None = None,
    synonyms: Mapping[str, Mapping[str, str]] | None = None,
    allow_literal: bool = False,
) -> CompiledRule:
    """Compile one entry of the deny list.

    Raises:
        TypeError: A value has the wrong type.
        RuleError: The entry is empty, has several commands, is a redirection without a target,
            or is not understood and ``allow_literal`` is false (the message never repeats it).
    """
    if not isinstance(pattern, str) or not isinstance(reason, str):
        raise TypeError("La entrada y su motivo deben ser textos.")
    if not isinstance(dialect, Dialect):
        raise TypeError("El dialecto debe ser un Dialect.")
    if not reason.strip():
        raise RuleError("motivo")
    text = pattern.strip()
    if not text:
        raise RuleError("vacia")
    insensitive = dialect is Dialect.POWERSHELL
    if text.startswith(">"):
        target = text[1:].strip()
        if not target or len(target.split()) != 1:
            raise RuleError("redireccion")
        return CompiledRule(
            RuleKind.REDIRECT,
            dialect,
            text=target.lower() if insensitive else target,
            reason=reason,
        )
    parsed = parse_command(text, dialect, aliases=aliases, synonyms=synonyms)
    if not parsed.understood:
        if not allow_literal:
            raise RuleError("no_se_entiende")
        return CompiledRule(RuleKind.LITERAL, dialect, text="".join(text.split()), reason=reason)
    if len(parsed.parts) != 1 or parsed.parts[0].redirect_targets:
        raise RuleError("varias_partes")
    part = parsed.parts[0]
    if not part.arguments:
        return CompiledRule(RuleKind.PROGRAM, dialect, program=part.program, reason=reason)
    positionals = tuple(p.lower() if insensitive else p for p in part.positionals)
    complete = [p for p in part.positionals if is_complete_target(p, dialect)]
    if complete:
        words = tuple(
            p
            for p, original in zip(positionals, part.positionals, strict=True)
            if not is_complete_target(original, dialect)
        )
        kind = RuleKind.TARGET
    elif not part.options and len(positionals) == 1 and positionals[0].endswith("="):
        words, kind = positionals, RuleKind.PREFIX
    else:
        words, kind = positionals, RuleKind.SUBCOMMAND
    return CompiledRule(
        kind, dialect, program=part.program, options=part.options, words=words, reason=reason
    )


def _frozen_synonyms(
    synonyms: Mapping[str, Mapping[str, str]] | None,
) -> MappingProxyType[str, MappingProxyType[str, str]]:
    return MappingProxyType(
        {program: MappingProxyType(dict(table)) for program, table in (synonyms or {}).items()}
    )


def _rules(value: object, name: str) -> tuple[CompiledRule, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TypeError(f"Las reglas {name} deben ser una secuencia de CompiledRule.")
    if not all(isinstance(item, CompiledRule) for item in value):
        raise TypeError(f"Las reglas {name} deben ser una secuencia de CompiledRule.")
    return tuple(value)


@dataclass(frozen=True)
class DenyList:
    """The deny list in use: the base of the dialect plus what the configuration adds.

    It is immutable and has no way to remove an entry: the base cannot be emptied (V-02).

    Args:
        dialect: The dialect of the shell.
        base: The base rules of the platform; never empty.
        extra: The rules added by the configuration.
        aliases: Program aliases of the dialect, used when parsing the commands.
        synonyms: Per program, options and the one they stand for, used when parsing.
    """

    dialect: Dialect
    base: Sequence[CompiledRule]
    extra: Sequence[CompiledRule] = ()
    aliases: Mapping[str, str] = field(default_factory=dict, kw_only=True)
    synonyms: Mapping[str, Mapping[str, str]] = field(default_factory=dict, kw_only=True)

    def __post_init__(self) -> None:
        if not isinstance(self.dialect, Dialect):
            raise TypeError("El dialecto debe ser un Dialect.")
        base = _rules(self.base, "base")
        if not base:
            raise ValueError("La lista base de comandos denegados no puede estar vacía.")
        object.__setattr__(self, "base", base)
        object.__setattr__(self, "extra", _rules(self.extra, "añadidas"))
        object.__setattr__(self, "aliases", MappingProxyType(dict(self.aliases)))
        object.__setattr__(self, "synonyms", _frozen_synonyms(self.synonyms))

    @property
    def rules(self) -> tuple[CompiledRule, ...]:
        """The base followed by the added rules."""
        return tuple(self.base) + tuple(self.extra)

    def denies(self, parsed: ParsedCommand, raw: str) -> bool:
        """Whether a part, an executable text or a redirection of the command is denied."""
        rules = self.rules
        if any(rule.matches_text(raw) for rule in rules):
            return True
        return self._denies(parsed, rules)

    def _denies(self, parsed: ParsedCommand, rules: tuple[CompiledRule, ...]) -> bool:
        if any(rule.matches(part) for part in parsed.parts for rule in rules):
            return True
        return any(self._denies(inner, rules) for inner in parsed.executable)
