"""Tests for the command parser of the shell policy (HU-05-02 / T002, T003).

``parse_command`` splits a command of bash or PowerShell into parts, by the separators of its
dialect and respecting quotes, and marks whatever it does not understand. It is pure: it never
runs anything and never raises on text (only on wrong types).
"""

from __future__ import annotations

import pytest

from harness_agent.core import CommandPart, Dialect, ParsedCommand, parse_command

BASH, PS = Dialect.BASH, Dialect.POWERSHELL
SENTINEL = "VALOR-DE-PRUEBA-123"


def programs(text: str, dialect: Dialect = BASH) -> list[str]:
    return [part.program for part in parse_command(text, dialect).parts]


def understood(text: str, dialect: Dialect = BASH) -> bool:
    return parse_command(text, dialect).understood


def single(text: str, dialect: Dialect = BASH) -> CommandPart:
    parsed = parse_command(text, dialect)
    (part,) = parsed.parts
    return part


# --- T002: separators, quotes, parts ---------------------------------------------------------

BASH_SEPARATORS = [
    ("a && b", ["a", "b"]),
    ("a || b", ["a", "b"]),
    ("a ; b", ["a", "b"]),
    ("a;b", ["a", "b"]),
    ("a | b", ["a", "b"]),
    ("a|b", ["a", "b"]),
    ("a |& b", ["a", "b"]),
    ("a & b", ["a", "b"]),
    ("a\nb", ["a", "b"]),
    ("a\r\nb", ["a", "b"]),
    ("a && b || c ; d | e & f\ng", ["a", "b", "c", "d", "e", "f", "g"]),
    ("a ;", ["a"]),
    ("a\n", ["a"]),
    ("a &", ["a"]),
    ("  a   x  ", ["a"]),
]
PS_SEPARATORS = [
    ("a ; b", ["a", "b"]),
    ("a | b", ["a", "b"]),
    ("a && b", ["a", "b"]),
    ("a || b", ["a", "b"]),
    ("a\nb", ["a", "b"]),
    ("Get-ChildItem; Format-Volume -DriveLetter D", ["get-childitem", "format-volume"]),
    ("a ;", ["a"]),
]


@pytest.mark.parametrize(("text", "expected"), BASH_SEPARATORS)
def test_bash_separators(text: str, expected: list[str]) -> None:
    parsed = parse_command(text, BASH)

    assert [part.program for part in parsed.parts] == expected
    assert parsed.understood is True


@pytest.mark.parametrize(("text", "expected"), PS_SEPARATORS)
def test_powershell_separators(text: str, expected: list[str]) -> None:
    parsed = parse_command(text, PS)

    assert [part.program for part in parsed.parts] == expected
    assert parsed.understood is True


QUOTED_SEPARATORS = [
    (BASH, "echo 'a && b; c | d'", ["echo"], ("a && b; c | d",)),
    (BASH, 'echo "a && b; c | d"', ["echo"], ("a && b; c | d",)),
    (BASH, 'echo "di \\"hola\\" ya"', ["echo"], ('di "hola" ya',)),
    (BASH, "echo a\\;b", ["echo"], ("a;b",)),
    (BASH, "echo 'a'\"b\"c", ["echo"], ("abc",)),
    (BASH, "echo ''", ["echo"], ("",)),
    (PS, "echo 'a; b | c'", ["echo"], ("a; b | c",)),
    (PS, "echo 'it''s'", ["echo"], ("it's",)),
    (PS, 'echo "a `" b"', ["echo"], ('a " b',)),
    (PS, 'echo "a "" b"', ["echo"], ('a " b',)),
    (PS, "echo C:\\Users\\x", ["echo"], ("C:\\Users\\x",)),
]


@pytest.mark.parametrize(("dialect", "text", "parts", "arguments"), QUOTED_SEPARATORS)
def test_a_separator_inside_quotes_does_not_split(
    dialect: Dialect, text: str, parts: list[str], arguments: tuple[str, ...]
) -> None:
    parsed = parse_command(text, dialect)

    assert [part.program for part in parsed.parts] == parts
    assert parsed.parts[0].arguments == arguments
    assert parsed.understood is True


class TestOptionsAndPositionals:
    def test_bash_short_options_are_expanded(self) -> None:
        part = single("rm -rf /", BASH)

        assert part.options == frozenset({"-r", "-f"})
        assert part.positionals == ("/",)

    def test_bash_separate_short_options(self) -> None:
        assert single("rm -r -f x").options == frozenset({"-r", "-f"})

    def test_bash_long_options_keep_their_name_without_value(self) -> None:
        part = single("rm --recursive --force --interactive=never x")

        assert part.options == frozenset({"--recursive", "--force", "--interactive"})

    def test_bash_double_dash_ends_the_options(self) -> None:
        part = single("rm -f -- -r x")

        assert part.options == frozenset({"-f"})
        assert part.positionals == ("-r", "x")

    def test_bash_is_case_sensitive(self) -> None:
        part = single("RM -R X")

        assert part.program == "RM"
        assert part.options == frozenset({"-R"})

    def test_a_lone_dash_is_positional(self) -> None:
        assert single("cat -").positionals == ("-",)

    def test_powershell_parameters_are_lower_case_and_without_value(self) -> None:
        part = single("Remove-Item -Recurse -Force:$true C:\\", PS)

        assert part.program == "remove-item"
        assert "-recurse" in part.options

    def test_powershell_parameter_with_a_colon_value(self) -> None:
        part = single("Remove-Item -Recurse:1 x", PS)

        assert part.options == frozenset({"-recurse"})
        assert part.positionals == ("x",)

    def test_the_arguments_keep_the_order_and_the_quotes_are_removed(self) -> None:
        part = single('git commit -m "fix: shutdown limpio" --amend')

        assert part.program == "git"
        assert part.arguments == ("commit", "-m", "fix: shutdown limpio", "--amend")
        assert part.positionals == ("commit", "fix: shutdown limpio")


NOT_UNDERSTOOD_BASH = [
    "echo 'abc",
    'echo "abc',
    "echo abc\\",
    "echo a \\\n b",
    "a ;; b",
    "| b",
    "a &&",
    "a && && b",
    "; a",
    "echo hola # comentario",
    "# solo comentario",
    "(cd x && ls)",
    "{ ls; }",
    "echo }",
    "cat << EOF",
    "cat <<< texto",
    "echo $X",
    "echo ${X}",
    "echo $1",
    "echo $?",
    "rm -rf $HOME",
    "$CMD -x",
    "echo ~usuario",
    "! ls",
    "",
    "   ",
    "\n",
]
NOT_UNDERSTOOD_PS = [
    "echo 'abc",
    'echo "abc',
    "echo abc `",
    "a ;; b",
    "| b",
    "echo hola # comentario",
    "<# bloque #> dir",
    "{ dir }",
    "(dir)",
    "echo $x",
    "echo $env:PATH",
    "echo ${x}",
    'echo "hola $nombre"',
    "dir < entrada.txt",
    "@(1, 2)",
    "& notepad",
    "dir --% /s",
    "",
]


@pytest.mark.parametrize("text", NOT_UNDERSTOOD_BASH)
def test_bash_constructions_that_are_not_understood(text: str) -> None:
    assert understood(text, BASH) is False


@pytest.mark.parametrize("text", NOT_UNDERSTOOD_PS)
def test_powershell_constructions_that_are_not_understood(text: str) -> None:
    assert understood(text, PS) is False


@pytest.mark.parametrize(
    ("dialect", "text"),
    [
        (BASH, "ls ~"),
        (BASH, "ls ~/proyecto"),
        (BASH, "echo a=b x=$"),
        (BASH, "ls *.py ?.txt [ab].md"),
        (BASH, "echo 'precio: $5'"),
        (BASH, "echo a#b c#"),
        (PS, "Get-ChildItem ~"),
        (PS, "echo 'cuesta $5'"),
        (PS, "echo a#b"),
    ],
)
def test_constructions_that_are_understood(dialect: Dialect, text: str) -> None:
    assert understood(text, dialect) is True


class TestTypes:
    def test_wrong_types_raise_type_error(self) -> None:
        with pytest.raises(TypeError):
            parse_command(3, BASH)  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            parse_command("ls", "bash")  # type: ignore[arg-type]

    def test_the_result_is_immutable(self) -> None:
        parsed = parse_command("ls", BASH)

        assert isinstance(parsed, ParsedCommand)
        with pytest.raises(AttributeError):
            parsed.understood = False  # type: ignore[misc]

    def test_errors_never_repeat_the_text(self) -> None:
        with pytest.raises(TypeError) as caught:
            parse_command(3, SENTINEL)  # type: ignore[arg-type]

        assert SENTINEL not in str(caught.value)

    def test_the_dialect_values(self) -> None:
        assert Dialect.BASH.value == "bash"
        assert Dialect.POWERSHELL.value == "powershell"


# --- T003: substitutions, other interpreters, wrappers, redirections, program -------------------


def executable_programs(text: str, dialect: Dialect = BASH) -> list[list[str]]:
    """The programs of each executable text found in ``text`` (first level only)."""
    parsed = parse_command(text, dialect)
    return [[part.program for part in inner.parts] for inner in parsed.executable]


def all_programs(parsed: ParsedCommand) -> list[str]:
    found = [part.program for part in parsed.parts]
    for inner in parsed.executable:
        found.extend(all_programs(inner))
    return found


SUBSTITUTIONS = [
    (BASH, "echo $(whoami)", [["whoami"]]),
    (BASH, "echo $(echo $(shutdown now))", [["echo"]]),
    (BASH, 'echo "hoy es $(date)"', [["date"]]),
    (BASH, "echo `date`", [["date"]]),
    (BASH, 'echo "`reboot`"', [["reboot"]]),
    (BASH, "echo $(a; b | c)", [["a", "b", "c"]]),
    (BASH, "echo $(echo ')'; reboot)", [["echo", "reboot"]]),
    (BASH, "cat <(ls)", [["ls"]]),
    (BASH, "tee >(reboot)", [["reboot"]]),
    (PS, "echo $(Get-Date)", [["get-date"]]),
    (PS, 'echo "hoy $(Stop-Computer)"', [["stop-computer"]]),
    (PS, "echo @(Stop-Computer)", [["stop-computer"]]),
]


@pytest.mark.parametrize(("dialect", "text", "expected"), SUBSTITUTIONS)
def test_substitutions_are_analyzed_and_never_understood(
    dialect: Dialect, text: str, expected: list[list[str]]
) -> None:
    parsed = parse_command(text, dialect)

    assert executable_programs(text, dialect) == expected
    assert parsed.understood is False


def test_nested_substitutions_are_analyzed_recursively() -> None:
    parsed = parse_command("echo $(echo $(shutdown now))", BASH)

    assert "shutdown" in all_programs(parsed)


@pytest.mark.parametrize(
    ("dialect", "text"),
    [
        (BASH, "echo $(ls"),
        (BASH, "echo `ls"),
        (BASH, "echo $((1 + 2))"),
        (PS, "echo $(Get-Date"),
    ],
)
def test_an_unterminated_substitution_is_not_understood(dialect: Dialect, text: str) -> None:
    assert understood(text, dialect) is False


def test_too_deep_nesting_is_not_understood_and_does_not_recurse_forever() -> None:
    text = "echo " + "$(echo " * 12 + "x" + ")" * 12

    parsed = parse_command(text, BASH)

    assert parsed.understood is False


INTERPRETERS = [
    (BASH, 'bash -c "rm -rf /"', ["rm"]),
    (BASH, "sh -c 'ls; reboot'", ["ls", "reboot"]),
    (BASH, 'zsh -lc "ls"', ["ls"]),
    (BASH, '/bin/bash -c "ls"', ["ls"]),
    (BASH, 'su -c "reboot"', ["reboot"]),
    (BASH, 'pwsh -Command "Stop-Computer"', ["stop-computer"]),
    (PS, 'pwsh -Command "Stop-Computer"', ["stop-computer"]),
    (PS, 'powershell.exe -c "Stop-Computer"', ["stop-computer"]),
    (PS, "powershell -NoProfile -Command Stop-Computer -Force", ["stop-computer"]),
    (PS, 'powershell "Stop-Computer"', ["stop-computer"]),
    (PS, 'bash -c "reboot"', ["reboot"]),
    (PS, 'cmd /c "dir & shutdown /s"', ["dir", "shutdown"]),
    (PS, "cmd.exe /C format C:", ["format"]),
]


@pytest.mark.parametrize(("dialect", "text", "expected"), INTERPRETERS)
def test_the_text_of_another_interpreter_is_analyzed(
    dialect: Dialect, text: str, expected: list[str]
) -> None:
    parsed = parse_command(text, dialect)

    assert parsed.understood is False
    assert [part.program for inner in parsed.executable for part in inner.parts] == expected


NOT_ANALYZABLE = [
    (BASH, "eval ls"),
    (BASH, "source script.sh"),
    (BASH, ". script.sh"),
    (BASH, "find . -name x | xargs rm"),
    (BASH, "bash -c"),
    (BASH, "env -S 'ls -l'"),
    (PS, "Invoke-Expression 'dir'"),
    (PS, 'iex "dir"'),
    (PS, "Start-Process notepad"),
    (PS, "Invoke-Command -ScriptBlock x"),
    (PS, "powershell -EncodedCommand AAAA"),
    (PS, "pwsh -enc AAAA"),
    (PS, "pwsh -e AAAA"),
    (PS, ". .\\script.ps1"),
    (PS, "cmd /c echo %PATH%"),
    (PS, "cmd /c echo ^& x"),
    (PS, "cmd /c (dir)"),
    (PS, "cmd /c dir > x"),
    (PS, "cmd /c"),
]


@pytest.mark.parametrize(("dialect", "text"), NOT_ANALYZABLE)
def test_executable_text_that_cannot_be_analyzed_is_not_understood(
    dialect: Dialect, text: str
) -> None:
    assert understood(text, dialect) is False


WRAPPERS = [
    ("sudo rm -rf /", "rm", ("/",)),
    ("sudo -u root -E rm -rf /", "rm", ("/",)),
    ("sudo -- reboot", "reboot", ()),
    ("env X=1 reboot", "reboot", ()),
    ("env -i -u HOME X=1 reboot now", "reboot", ("now",)),
    ("X=1 Y=2 reboot", "reboot", ()),
    ("nohup reboot", "reboot", ()),
    ("time -p reboot", "reboot", ()),
    ("nice -n 5 reboot", "reboot", ()),
    ("nice -5 reboot", "reboot", ()),
    ("timeout -s KILL 10 reboot", "reboot", ()),
    ("command reboot", "reboot", ()),
    ("builtin echo x", "echo", ("x",)),
    ("exec -a nombre reboot", "reboot", ()),
    ("sudo nohup env X=1 /sbin/shutdown -h now", "shutdown", ("now",)),
    ("sudo", "sudo", ()),
    ("command -v shutdown", "command", ("shutdown",)),
]


@pytest.mark.parametrize(("text", "program", "positionals"), WRAPPERS)
def test_wrappers_are_removed_before_the_program(
    text: str, program: str, positionals: tuple[str, ...]
) -> None:
    part = single(text, BASH)

    assert part.program == program
    assert part.positionals == positionals


PROGRAMS = [
    (BASH, "/sbin/shutdown -h now", "shutdown"),
    (BASH, "/usr/bin/rm -rf x", "rm"),
    (BASH, "./reboot", "reboot"),
    (BASH, "mkfs.ext4 /dev/sda1", "mkfs.ext4"),
    (BASH, "Shutdown.exe", "Shutdown"),
    (PS, "C:\\Windows\\System32\\shutdown.exe /s", "shutdown"),
    (PS, "SHUTDOWN.EXE /s", "shutdown"),
    (PS, "script.PS1", "script"),
    (PS, "x.cmd", "x"),
    (PS, "x.bat", "x"),
    (PS, "x.com", "x"),
    (PS, "ri -r -fo C:\\", "remove-item"),
    (PS, "Del C:\\x", "remove-item"),
    (PS, "Stop-Computer", "stop-computer"),
]
ALIASES = {"ri": "remove-item", "del": "remove-item", "rm": "remove-item"}


@pytest.mark.parametrize(("dialect", "text", "program"), PROGRAMS)
def test_the_program_is_normalized(dialect: Dialect, text: str, program: str) -> None:
    parsed = parse_command(text, dialect, aliases=ALIASES if dialect is PS else {})

    assert parsed.parts[0].program == program


def test_bash_synonyms_translate_long_and_short_options() -> None:
    synonyms = {"rm": {"--recursive": "-r", "--force": "-f", "-R": "-r"}}

    part = parse_command("rm --recursive --force -R x", BASH, synonyms=synonyms).parts[0]

    assert part.options == frozenset({"-r", "-f"})


def test_cmd_options_are_lower_case() -> None:
    parsed = parse_command("cmd /c rd /S /Q C:\\", PS)

    (inner,) = parsed.executable
    assert inner.parts[0].program == "rd"
    assert inner.parts[0].options == frozenset({"/s", "/q"})
    assert inner.parts[0].positionals == ("c:\\",)


REDIRECTIONS = [
    (BASH, "echo hola > salida.txt", ("salida.txt",), ("hola",)),
    (BASH, "echo hola>salida.txt", ("salida.txt",), ("hola",)),
    (BASH, "echo hola >> a.log 2> b.log", ("a.log", "b.log"), ("hola",)),
    (BASH, "ls 2>&1", (), ()),
    (BASH, "echo x &> todo.log", ("todo.log",), ("x",)),
    (BASH, "echo x &>> todo.log", ("todo.log",), ("x",)),
    (BASH, "echo x >| forzado.txt", ("forzado.txt",), ("x",)),
    (BASH, "sort < entrada.txt", ("entrada.txt",), ()),
    (BASH, "echo x > /dev/sda", ("/dev/sda",), ("x",)),
    (BASH, 'echo x > "con espacio.txt"', ("con espacio.txt",), ("x",)),
    (BASH, "echo x 1>&2", (), ("x",)),
    (BASH, "echo x >&-", (), ("x",)),
    (PS, "echo hola > salida.txt", ("salida.txt",), ("hola",)),
    (PS, "dir 2> err.txt", ("err.txt",), ()),
    (PS, "dir *> todo.txt", ("todo.txt",), ()),
    (PS, "dir 3>> x.txt", ("x.txt",), ()),
    (PS, "dir 2>&1", (), ()),
]


@pytest.mark.parametrize(("dialect", "text", "targets", "positionals"), REDIRECTIONS)
def test_redirections_go_to_their_targets(
    dialect: Dialect, text: str, targets: tuple[str, ...], positionals: tuple[str, ...]
) -> None:
    parsed = parse_command(text, dialect)

    assert parsed.parts[0].redirect_targets == targets
    assert parsed.parts[0].positionals == positionals
    assert parsed.understood is True


def test_a_redirection_to_a_substitution_is_analyzed() -> None:
    parsed = parse_command("echo hola > $(reboot)", BASH)

    assert parsed.understood is False
    assert executable_programs("echo hola > $(reboot)") == [["reboot"]]


@pytest.mark.parametrize(
    ("dialect", "text"),
    [(BASH, "echo x >"), (BASH, "echo x > ; ls"), (PS, "echo x >"), (BASH, "echo x 2>")],
)
def test_a_redirection_without_target_is_not_understood(dialect: Dialect, text: str) -> None:
    assert understood(text, dialect) is False


# --- T003: the remaining branches ---------------------------------------------------------------

MORE_NOT_UNDERSTOOD = [
    (BASH, "echo x > > y"),
    (BASH, 'echo "a\\\nb"'),
    (BASH, "echo $(echo 'abc)"),
    (BASH, 'echo $(echo "abc)'),
    (BASH, "bash -c"),
    (PS, "@{a=1}"),
    (PS, "echo $(echo 'abc)"),
    (PS, "cmd /c 'echo \"abc'"),
    (PS, "cmd /c 'a > b'"),
    (PS, "cmd /c '(dir)'"),
]


@pytest.mark.parametrize(("dialect", "text"), MORE_NOT_UNDERSTOOD)
def test_more_constructions_that_are_not_understood(dialect: Dialect, text: str) -> None:
    assert understood(text, dialect) is False


def test_a_duplicated_descriptor_with_several_digits_has_no_target() -> None:
    part = single("echo x 2>&12", BASH)

    assert part.redirect_targets == ()
    assert part.positionals == ("x",)


def test_a_redirection_of_both_streams_to_a_file() -> None:
    assert single("echo x >&salida.txt", BASH).redirect_targets == ("salida.txt",)


def test_escapes_inside_a_substitution_are_skipped() -> None:
    parsed = parse_command("echo $(echo \\) ; reboot)", BASH)

    assert [p.program for inner in parsed.executable for p in inner.parts] == ["echo", "reboot"]


def test_double_quotes_inside_a_substitution_are_respected() -> None:
    parsed = parse_command('echo $(echo ")" ; reboot)', BASH)

    assert [p.program for inner in parsed.executable for p in inner.parts] == ["echo", "reboot"]


@pytest.mark.parametrize(
    ("dialect", "text", "expected"),
    [
        (PS, "cmd /c 'echo \"a b\" & ver'", ["echo", "ver"]),
        (PS, "cmd /c 'a | b || c && d'", ["a", "b", "c", "d"]),
        (BASH, 'cmd /c "a\nb"', ["a", "b"]),
    ],
)
def test_the_separators_and_quotes_of_cmd(dialect: Dialect, text: str, expected: list[str]) -> None:
    parsed = parse_command(text, dialect)

    assert [p.program for inner in parsed.executable for p in inner.parts] == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("su --command=reboot", ["reboot"]),
        ("su -l -c reboot", ["reboot"]),
        ("su --command reboot", ["reboot"]),
        ("bash -x -c 'reboot'", ["reboot"]),
        ("bash --norc -c 'reboot'", ["reboot"]),
        ("bash script.sh", []),
        ("bash -x", []),
        ("su", []),
    ],
)
def test_the_text_of_a_posix_shell(text: str, expected: list[str]) -> None:
    parsed = parse_command(text, BASH)

    assert parsed.understood is False
    assert [p.program for inner in parsed.executable for p in inner.parts] == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("pwsh -File script.ps1", []),
        ("pwsh -NoProfile", []),
        ("pwsh", []),
        ("pwsh -Command", []),
        ("pwsh /c Stop-Computer", ["stop-computer"]),
        ("pwsh -ec AAAA", []),
    ],
)
def test_the_text_of_powershell(text: str, expected: list[str]) -> None:
    parsed = parse_command(text, PS)

    assert parsed.understood is False
    assert [p.program for inner in parsed.executable for p in inner.parts] == expected


@pytest.mark.parametrize(
    ("text", "program"),
    [("sudo -u", "sudo"), ("env X=1", "env"), ("env -u", "env"), ("timeout 10", "timeout")],
)
def test_a_wrapper_without_a_program(text: str, program: str) -> None:
    assert single(text, BASH).program == program


def test_a_part_with_only_a_redirection_has_no_program() -> None:
    part = single("> vaciar.txt", BASH)

    assert part.program == ""
    assert part.redirect_targets == ("vaciar.txt",)


def test_a_lone_assignment_is_not_a_program_call() -> None:
    assert single("X=1", BASH).program == "X=1"
