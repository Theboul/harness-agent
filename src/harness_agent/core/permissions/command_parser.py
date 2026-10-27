"""Parser of shell commands for the permission policy (HU-05-02).

``parse_command`` splits the text of a bash or PowerShell command into parts, by the separators of
its dialect and respecting quotes, and marks whatever it does not understand. It never runs or
looks up anything (no aliases, functions or variables of the machine) and never raises on text:
anything it cannot follow is reported as ``understood=False``, and it keeps scanning so that the
rest of the command can still be checked against the deny list.

Text that the command runs (substitutions, the text given to another interpreter with ``-c``,
``-Command`` or ``/c``) is analyzed as a command of its own and returned in ``executable``; a
command that runs text is never ``understood``. It is a hand-written scanner, character by
character: ``shlex`` only knows POSIX quoting and does not report substitutions.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum


class Dialect(str, Enum):
    """The command language; the value is ``interpreter_name`` of the shell."""

    BASH = "bash"
    POWERSHELL = "powershell"


@dataclass(frozen=True)
class CommandPart:
    """One simple command of a compound one.

    Attributes:
        program: The program without wrappers (``sudo``, ``env``…), folder or extension; lower
            case and with the alias resolved in PowerShell and in ``cmd``.
        arguments: The words after the program, without quotes, in order.
        options: The options, normalized (short options of bash expanded one by one and
            translated with the synonyms of the program).
        positionals: The arguments that are not options.
        redirect_targets: Where the output or input of the part is redirected.
    """

    program: str
    arguments: tuple[str, ...] = ()
    options: frozenset[str] = frozenset()
    positionals: tuple[str, ...] = ()
    redirect_targets: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedCommand:
    """The result of the analysis.

    Attributes:
        parts: The parts of the command at this level.
        executable: Texts this command runs that could be analyzed (substitutions, the text of
            another interpreter), each with its own analysis.
        understood: ``False`` if anything here or in an executable text was not understood, or
            if the command runs text (a substitution, another interpreter).
    """

    parts: tuple[CommandPart, ...]
    executable: tuple[ParsedCommand, ...] = ()
    understood: bool = True


_BASH, _POWERSHELL, _CMD = "bash", "powershell", "cmd"
_MAX_DEPTH = 8
_EXTENSIONS = (".exe", ".cmd", ".bat", ".com", ".ps1")
_POSIX_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
_POWERSHELLS = frozenset({"pwsh", "powershell"})
_NOT_ANALYZABLE = frozenset(
    {
        "eval",
        "source",
        ".",
        "xargs",
        "invoke-expression",
        "iex",
        "start-process",
        "saps",
        "start",
        "invoke-command",
        "icm",
        "start-job",
        "sajb",
    }
)
_GROUPING = frozenset("(){}")
_EXPANSION_START = frozenset("{?@*#!$-_") | frozenset("0123456789")
_CONTINUATION_SEPARATORS = frozenset({"&&", "||", "|", "|&"})
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_PATH_SEPARATORS = re.compile(r"[\\/]")
_END_OF_WORD = ("", " ", "\t", "\n", "\r")


@dataclass
class _Word:
    text: str
    quoted: bool


@dataclass
class _Segment:
    words: list[_Word] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)


_Inner = Callable[[str, str], "ParsedCommand"]


class _Scanner:
    """One pass over the text of one command, in one mode (``bash``, ``powershell``, ``cmd``)."""

    def __init__(self, text: str, mode: str, inner: _Inner) -> None:
        self._text = text
        self._mode = mode
        self._inner = inner
        self._pos = 0
        self.understood = True
        self.executable: list[ParsedCommand] = []
        self._chars: list[str] = []
        self._in_word = False
        self._quoted = False
        self._segment = _Segment()
        self._expect_target = False
        self.segments: list[_Segment] = []
        self._pending: str | None = None

    # --- driving -----------------------------------------------------------------------------

    def run(self) -> list[_Segment]:
        steps = {_BASH: self._bash_step, _POWERSHELL: self._powershell_step, _CMD: self._cmd_step}
        step = steps[self._mode]
        while self._pos < len(self._text):
            step(self._text[self._pos])
        self._end_word()
        self._push_segment()
        if self._pending is not None or not self.segments:
            self.understood = False
        return self.segments

    def _peek(self, offset: int = 1) -> str:
        index = self._pos + offset
        return self._text[index] if index < len(self._text) else ""

    def _append(self, text: str) -> None:
        self._chars.append(text)
        self._in_word = True

    def _end_word(self) -> None:
        if self._in_word:
            text = "".join(self._chars)
            if self._expect_target:
                self._segment.targets.append(text)
                self._expect_target = False
            else:
                self._segment.words.append(_Word(text, self._quoted))
        self._chars, self._in_word, self._quoted = [], False, False

    def _push_segment(self) -> bool:
        """Close the current part if it has anything; say whether it had."""
        if self._expect_target:
            self.understood = False  # a redirection without a target
            self._expect_target = False
        segment = self._segment
        if not segment.words and not segment.targets:
            return False
        self.segments.append(segment)
        self._segment = _Segment()
        self._pending = None
        return True

    def _separator(self, separator: str) -> None:
        """End the current part; a part may only be empty before a new line (a blank line)."""
        self._end_word()
        if self._push_segment():
            self._pending = separator if separator in _CONTINUATION_SEPARATORS else None
        elif separator != "\n":
            self.understood = False
        self._pos += len(separator)

    def _not_understood_boundary(self) -> None:
        """A grouping character: not understood, and a boundary so the inside is still seen."""
        self.understood = False
        self._end_word()
        self._push_segment()
        self._pos += 1

    def _skip_comment(self) -> None:
        self.understood = False
        end = self._text.find("\n", self._pos)
        self._pos = len(self._text) if end < 0 else end

    def _start_target(self) -> None:
        if self._expect_target:
            self.understood = False  # two redirections in a row
        self._expect_target = True

    def _drop_descriptor(self, allowed: str) -> None:
        """A word made only of ``allowed`` characters right before ``>`` is a file descriptor."""
        if self._in_word and not self._quoted and all(c in allowed for c in self._chars):
            self._chars, self._in_word = [], False
        else:
            self._end_word()

    def run_inner(self, text: str, mode: str) -> None:
        """Analyze ``text`` as a command that runs; the outer command is never understood."""
        self.understood = False
        self.executable.append(self._inner(text, mode))

    def _run_text(self, start: int, end: int, mode: str) -> None:
        self.run_inner(self._text[start:end], mode)

    def _substitution(self, mode: str) -> None:
        """``$(`` / ``@(`` / ``<(`` / ``>(`` at ``_pos``: analyze the inside, keep the raw text."""
        open_index = self._pos + 1
        close_index = _closing_parenthesis(self._text, open_index, mode)
        if close_index < 0:
            self.understood = False
            self._append(self._text[self._pos :])
            self._pos = len(self._text)
            return
        self._run_text(open_index + 1, close_index, mode)
        self._append(self._text[self._pos : close_index + 1])
        self._pos = close_index + 1

    # --- bash --------------------------------------------------------------------------------

    def _bash_step(self, char: str) -> None:
        if char in " \t\r":
            self._end_word()
            self._pos += 1
        elif char == "\n":
            self._separator("\n")
        elif char == ";":
            self._separator(";")
        elif char == "&" and self._peek() == ">":
            self._end_word()
            self._pos += 3 if self._peek(2) == ">" else 2
            self._start_target()
        elif char == "&":
            self._separator("&&" if self._peek() == "&" else "&")
        elif char == "|":
            following = self._peek()
            self._separator("|" + following if following and following in "|&" else "|")
        elif char in "<>":
            self._bash_redirection(char)
        elif char == "'":
            self._single_quotes()
        elif char == '"':
            self._bash_double_quotes()
        elif char == "\\":
            self._escape()
        elif char == "$":
            self._dollar(_BASH)
        elif char == "`":
            self._backticks()
        elif char == "#" and not self._in_word:
            self._skip_comment()
        elif char in _GROUPING:
            self._not_understood_boundary()
        elif char == "!" and not self._in_word and self._peek() in _END_OF_WORD:
            self.understood = False
            self._pos += 1
        elif char == "~" and not self._in_word and self._peek() not in (*_END_OF_WORD, "/"):
            self.understood = False
            self._append(char)
            self._pos += 1
        else:
            self._append(char)
            self._pos += 1

    def _bash_redirection(self, char: str) -> None:
        following = self._peek()
        if following == "(":
            self._end_word()
            self._substitution(_BASH)  # process substitution: runs text
            self._end_word()
            return
        self._drop_descriptor("0123456789")
        if char == "<" and following == "<":
            self.understood = False  # here-document or here-string
            self._pos += 3 if self._peek(2) == "<" else 2
            return
        if following == "&":
            target = self._peek(2)
            if target == "-" or target.isdigit():
                self._pos += 3
                while self._pos < len(self._text) and self._text[self._pos].isdigit():
                    self._pos += 1
                return
            self._pos += 2
        elif (char == ">" and following in (">", "|")) or (char == "<" and following == ">"):
            self._pos += 2
        else:
            self._pos += 1
        self._start_target()

    def _single_quotes(self) -> None:
        end = self._text.find("'", self._pos + 1)
        if end < 0:
            self.understood = False
            self._append(self._text[self._pos + 1 :])
            self._pos = len(self._text)
            return
        self._quoted = True
        self._append(self._text[self._pos + 1 : end])
        self._pos = end + 1

    def _bash_double_quotes(self) -> None:
        self._quoted = True
        self._in_word = True
        self._pos += 1
        while self._pos < len(self._text):
            char = self._text[self._pos]
            if char == '"':
                self._pos += 1
                return
            if char == "\\" and self._peek() in ('"', "\\", "$", "`", "\n"):
                if self._peek() == "\n":
                    self.understood = False
                self._append(self._peek())
                self._pos += 2
            elif char == "$":
                self._dollar(_BASH)
            elif char == "`":
                self._backticks()
            else:
                self._append(char)
                self._pos += 1
        self.understood = False

    def _escape(self) -> None:
        following = self._peek()
        if following in ("", "\n", "\r"):
            self.understood = False  # a line continuation or a lone escape at the end
            self._pos += 2
            return
        self._append(following)
        self._pos += 2

    def _backticks(self) -> None:
        index = self._pos + 1
        while index < len(self._text) and self._text[index] != "`":
            index += 2 if self._text[index] == "\\" else 1
        if index >= len(self._text):
            self.understood = False
            self._append(self._text[self._pos :])
            self._pos = len(self._text)
            return
        self._run_text(self._pos + 1, index, _BASH)
        self._append(self._text[self._pos : index + 1])
        self._pos = index + 1

    # --- PowerShell --------------------------------------------------------------------------

    def _powershell_step(self, char: str) -> None:
        if char in " \t\r":
            self._end_word()
            self._pos += 1
        elif char == "\n":
            self._separator("\n")
        elif char == ";":
            self._separator(";")
        elif char == "|":
            self._separator("||" if self._peek() == "|" else "|")
        elif char == "&" and self._peek() == "&":
            self._separator("&&")
        elif char == "&":
            self.understood = False  # the call operator runs whatever follows
            self._end_word()
            self._pos += 1
        elif char == ">":
            self._powershell_redirection()
        elif char == "<":
            self.understood = False  # reserved in PowerShell
            self._end_word()
            self._pos += 1
        elif char == "'":
            self._powershell_single_quotes()
        elif char == '"':
            self._powershell_double_quotes()
        elif char == "`":
            self._escape()
        elif char == "$":
            self._dollar(_POWERSHELL)
        elif char == "#" and not self._in_word:
            self._skip_comment()
        elif char == "@" and not self._in_word and self._peek() == "(":
            self._substitution(_POWERSHELL)
        elif char == "@" and not self._in_word and self._peek() in ("{", "'", '"'):
            self.understood = False
            self._pos += 1
        elif char in _GROUPING:
            self._not_understood_boundary()
        else:
            self._append(char)
            self._pos += 1

    def _powershell_redirection(self) -> None:
        self._drop_descriptor("0123456789*")
        self._pos += 2 if self._peek() == ">" else 1
        if self._text[self._pos : self._pos + 1] == "&" and self._peek().isdigit():
            self._pos += 2
            return
        self._start_target()

    def _powershell_single_quotes(self) -> None:
        self._quoted = True
        self._in_word = True
        self._pos += 1
        while self._pos < len(self._text):
            char = self._text[self._pos]
            if char == "'" and self._peek() == "'":
                self._append("'")
                self._pos += 2
            elif char == "'":
                self._pos += 1
                return
            else:
                self._append(char)
                self._pos += 1
        self.understood = False

    def _powershell_double_quotes(self) -> None:
        self._quoted = True
        self._in_word = True
        self._pos += 1
        while self._pos < len(self._text):
            char = self._text[self._pos]
            if char == '"' and self._peek() == '"':
                self._append('"')
                self._pos += 2
            elif char == '"':
                self._pos += 1
                return
            elif char == "`" and self._peek():
                self._append(self._peek())
                self._pos += 2
            elif char == "$":
                self._dollar(_POWERSHELL)
            else:
                self._append(char)
                self._pos += 1
        self.understood = False

    # --- cmd (only inside ``cmd /c``) --------------------------------------------------------

    def _cmd_step(self, char: str) -> None:
        if char in " \t\r":
            self._end_word()
            self._pos += 1
        elif char == "\n":
            self._separator("\n")
        elif char == "&":
            self._separator("&&" if self._peek() == "&" else "&")
        elif char == "|":
            self._separator("||" if self._peek() == "|" else "|")
        elif char == '"':
            end = self._text.find('"', self._pos + 1)
            if end < 0:
                self.understood = False
                end = len(self._text)
            self._quoted = True
            self._append(self._text[self._pos + 1 : end])
            self._pos = end + 1
        elif char in "()":
            self._not_understood_boundary()
        elif char in "<>":
            self.understood = False
            self._end_word()
            self._pos += 1
        else:
            if char in "^%!":
                self.understood = False  # escapes and variables of cmd
            self._append(char)
            self._pos += 1

    # --- shared ------------------------------------------------------------------------------

    def _dollar(self, mode: str) -> None:
        """``$(`` is a substitution; ``$`` followed by a name is an expansion (not understood)."""
        following = self._peek()
        if following == "(" and not (mode == _BASH and self._peek(2) == "("):
            self._substitution(mode)
            return
        if following == "(" or following in _EXPANSION_START or following.isalpha():
            self.understood = False
        self._append("$")
        self._pos += 1


def _closing_parenthesis(text: str, open_index: int, mode: str) -> int:
    """The index of the ``)`` that closes ``text[open_index]``, or -1; quotes are respected."""
    depth = 0
    index = open_index
    escape = "`" if mode == _POWERSHELL else "\\"
    while index < len(text):
        char = text[index]
        if char == escape:
            index += 2
            continue
        if char == "'":
            end = text.find("'", index + 1)
            if end < 0:
                return -1
            index = end + 1
            continue
        if char == '"':
            index += 1
            while index < len(text) and text[index] != '"':
                index += 2 if text[index] == escape else 1
            if index >= len(text):
                return -1
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def _skip_options(words: list[_Word], index: int, with_value: frozenset[str]) -> int:
    while index < len(words):
        text = words[index].text
        if text == "--":
            return index + 1
        if len(text) < 2 or not text.startswith("-"):
            return index
        index += 2 if text in with_value else 1
    return index


_SUDO_VALUES = frozenset({"-u", "-g", "-p", "-C", "-D", "-T", "-r", "-t", "-U", "-h"})


class _PartBuilder:
    """Turns the words of a segment into a ``CommandPart`` and finds the text it runs."""

    def __init__(
        self,
        mode: str,
        aliases: Mapping[str, str],
        synonyms: Mapping[str, Mapping[str, str]],
        scanner: _Scanner,
    ) -> None:
        self._mode = mode
        self._aliases = aliases
        self._synonyms = synonyms
        self._scanner = scanner

    def build(self, segment: _Segment) -> CommandPart:
        words = segment.words
        index = self._unwrap(words) if self._mode == _BASH else 0
        if index >= len(words):
            program = self._program(words[-1].text) if words else ""
            return CommandPart(program=program, redirect_targets=tuple(segment.targets))
        program = self._program(words[index].text)
        rest = words[index + 1 :]
        if self._mode == _CMD:
            rest = [_Word(word.text.lower(), word.quoted) for word in rest]
        options, positionals = self._classify(program, rest)
        self._executes(program, rest)
        return CommandPart(
            program=program,
            arguments=tuple(word.text for word in rest),
            options=frozenset(options),
            positionals=tuple(positionals),
            redirect_targets=tuple(segment.targets),
        )

    def _unwrap(self, words: list[_Word]) -> int:
        """Skip assignments and wrappers (``sudo``, ``env``…); the index of the real program."""
        index = 0
        while (
            index < len(words) and not words[index].quoted and _ASSIGNMENT.match(words[index].text)
        ):
            index += 1
        while index < len(words):
            name = _PATH_SEPARATORS.split(words[index].text)[-1]
            following = words[index + 1].text if index + 1 < len(words) else ""
            if name == "sudo":
                start = _skip_options(words, index + 1, _SUDO_VALUES)
            elif name == "env":
                start = self._skip_env(words, index + 1)
            elif name in ("nohup", "builtin"):
                start = index + 1
            elif name == "time":
                start = _skip_options(words, index + 1, frozenset())
            elif name == "command" and not following.startswith(("-v", "-V")):
                start = _skip_options(words, index + 1, frozenset())
            elif name == "exec":
                start = _skip_options(words, index + 1, frozenset({"-a"}))
            elif name == "nice":
                start = _skip_options(words, index + 1, frozenset({"-n"}))
            elif name == "timeout":
                start = _skip_options(words, index + 1, frozenset({"-s", "-k"})) + 1
            else:
                return index
            if start >= len(words):
                return index  # nothing after the wrapper: the wrapper is the program
            index = start
        return index

    def _skip_env(self, words: list[_Word], index: int) -> int:
        while index < len(words):
            text = words[index].text
            if text in ("-u", "--unset"):
                index += 2
            elif text in ("-S", "--split-string") or text.startswith("--split-string="):
                self._scanner.understood = False  # runs a text that is not analyzed
                index += 1
            elif text.startswith("-") or _ASSIGNMENT.match(text):
                index += 1
            else:
                return index
        return index

    def _program(self, raw: str) -> str:
        name = _PATH_SEPARATORS.split(raw)[-1]
        lowered = name.lower()
        for extension in _EXTENSIONS:
            if lowered.endswith(extension) and len(name) > len(extension):
                name = name[: -len(extension)]
                break
        if self._mode != _BASH:
            name = name.lower()
        return self._aliases.get(name, name)

    def _classify(self, program: str, words: list[_Word]) -> tuple[set[str], list[str]]:
        options: set[str] = set()
        positionals: list[str] = []
        synonyms = self._synonyms.get(program, {})
        only_positionals = False
        for word in words:
            text = word.text
            if self._mode == _POWERSHELL:
                if not word.quoted and len(text) > 1 and text.startswith("-"):
                    options.add(text.split(":", 1)[0].lower())
                else:
                    positionals.append(text)
            elif self._mode == _CMD:
                if not word.quoted and len(text) > 1 and text.startswith("/"):
                    options.add(text)
                else:
                    positionals.append(text)
            elif only_positionals or len(text) < 2 or not text.startswith("-"):
                positionals.append(text)
            elif text == "--":
                only_positionals = True
            elif text.startswith("--"):
                name = text.split("=", 1)[0]
                options.add(synonyms.get(name, name))
            else:
                for letter in text[1:]:
                    option = "-" + letter
                    options.add(synonyms.get(option, option))
        return options, positionals

    def _executes(self, program: str, words: list[_Word]) -> None:
        """Mark and analyze what runs text: other interpreters, ``eval``, ``iex``…"""
        name = program.lower()
        scanner = self._scanner
        if name in _NOT_ANALYZABLE:
            scanner.understood = False
        elif name in _POSIX_SHELLS or name == "su":
            scanner.understood = False
            text = _posix_command_text(name, words)
            if text is not None:
                scanner.run_inner(text, _BASH)
        elif name in _POWERSHELLS:
            scanner.understood = False
            text = _powershell_command_text(words)
            if text is not None:
                scanner.run_inner(text, _POWERSHELL)
        elif name == "cmd":
            scanner.understood = False
            switches = [i for i, w in enumerate(words) if w.text.lower() in ("/c", "/k")]
            if switches and switches[0] + 1 < len(words):
                text = " ".join(word.text for word in words[switches[0] + 1 :])
                scanner.run_inner(text, _CMD)


def _posix_command_text(name: str, words: list[_Word]) -> str | None:
    """The text given with ``-c`` to a POSIX shell (or to ``su``), if any."""
    for index, word in enumerate(words):
        text = word.text
        following = words[index + 1].text if index + 1 < len(words) else None
        if name == "su":
            if text in ("-c", "--command"):
                return following
            if text.startswith("--command="):
                return text.split("=", 1)[1]
        elif len(text) > 1 and text.startswith("-") and not text.startswith("--"):
            if "c" in text[1:]:
                return following
        elif not text.startswith("-"):
            return None  # a script: no text to analyze
    return None


def _powershell_command_text(words: list[_Word]) -> str | None:
    """The text given with ``-Command`` (or as positional words) to PowerShell, if analyzable."""
    for index, word in enumerate(words):
        text = word.text.lower()
        if not word.quoted and len(text) > 1 and text[0] in "-/":
            name = text[1:].split(":", 1)[0]
            if "encodedcommand".startswith(name) or name == "ec":
                return None
            if "command".startswith(name):
                rest = " ".join(w.text for w in words[index + 1 :])
                return rest or None
            if "file".startswith(name):
                return None
        else:
            return " ".join(w.text for w in words[index:])
    return None


def _parse(
    text: str,
    mode: str,
    aliases: Mapping[str, str],
    synonyms: Mapping[str, Mapping[str, str]],
    depth: int,
) -> ParsedCommand:
    if depth > _MAX_DEPTH:
        return ParsedCommand(parts=(), understood=False)

    def inner(inner_text: str, inner_mode: str) -> ParsedCommand:
        return _parse(inner_text, inner_mode, aliases, synonyms, depth + 1)

    scanner = _Scanner(text, mode, inner)
    segments = scanner.run()
    builder = _PartBuilder(mode, aliases, synonyms, scanner)
    parts = tuple(builder.build(segment) for segment in segments)
    for segment in segments:
        if mode == _POWERSHELL and any(w.text == "--%" and not w.quoted for w in segment.words):
            scanner.understood = False
    understood = scanner.understood and all(item.understood for item in scanner.executable)
    return ParsedCommand(parts=parts, executable=tuple(scanner.executable), understood=understood)


def parse_command(
    text: str,
    dialect: Dialect,
    *,
    aliases: Mapping[str, str] | None = None,
    synonyms: Mapping[str, Mapping[str, str]] | None = None,
) -> ParsedCommand:
    """Split ``text`` into parts and say whether everything was understood.

    Args:
        text: The command, as the shell would receive it.
        dialect: The language of the command.
        aliases: Program aliases, lower case (PowerShell: ``ri`` -> ``remove-item``).
        synonyms: Per program, options and the one they stand for (bash: ``--force`` -> ``-f``).

    Raises:
        TypeError: ``text`` is not a text or ``dialect`` is not a ``Dialect``.
    """
    if not isinstance(text, str):
        raise TypeError("El comando debe ser un texto.")
    if not isinstance(dialect, Dialect):
        raise TypeError("El dialecto debe ser un Dialect.")
    mode = _BASH if dialect is Dialect.BASH else _POWERSHELL
    return _parse(text, mode, dict(aliases or {}), dict(synonyms or {}), 0)
