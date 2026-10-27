"""Tests for the deny rules compiled from command text and the deny list (HU-05-02 / T004).

An entry of the list is written as the real command and compiled with the same parser as the
commands of the agent. The kind of rule follows from its words: one word (program), program with
a complete target (target), program with an argument ending in ``=`` (prefix), program with words
(subcommand), ``> destination`` (redirection) or, only for the base list, a text the parser does
not understand (literal).
"""

from __future__ import annotations

import dataclasses

import pytest

from harness_agent.core import (
    CommandPart,
    CompiledRule,
    DenyList,
    Dialect,
    RuleError,
    RuleKind,
    compile_rule,
    parse_command,
)

BASH, PS = Dialect.BASH, Dialect.POWERSHELL
SENTINEL = "VALOR-DE-PRUEBA-123"
PS_ALIASES = {"rm": "remove-item", "ri": "remove-item", "del": "remove-item"}
BASH_SYNONYMS = {
    "rm": {"--recursive": "-r", "--force": "-f", "-R": "-r"},
    "chmod": {"--recursive": "-R"},
}
FORK_BOMB = ":(){ :|:& };:"


def rule(pattern: str, dialect: Dialect = BASH, *, literal: bool = False) -> CompiledRule:
    aliases = PS_ALIASES if dialect is PS else {}
    synonyms = BASH_SYNONYMS if dialect is BASH else {}
    return compile_rule(
        pattern,
        "motivo",
        dialect,
        aliases=aliases,
        synonyms=synonyms,
        allow_literal=literal,
    )


def part(text: str, dialect: Dialect = BASH) -> CommandPart:
    aliases = PS_ALIASES if dialect is PS else {}
    synonyms = BASH_SYNONYMS if dialect is BASH else {}
    (found,) = parse_command(text, dialect, aliases=aliases, synonyms=synonyms).parts
    return found


# --- compiling ----------------------------------------------------------------------------------

KINDS = [
    (BASH, "shutdown", RuleKind.PROGRAM),
    (BASH, "mkfs", RuleKind.PROGRAM),
    (PS, "Format-Volume", RuleKind.PROGRAM),
    (BASH, "rm -rf /", RuleKind.TARGET),
    (BASH, "rm -rf ~", RuleKind.TARGET),
    (BASH, "chmod -R 777 /", RuleKind.TARGET),
    (BASH, "chown -R root /", RuleKind.TARGET),
    (PS, "Remove-Item -Recurse -Force C:\\", RuleKind.TARGET),
    (BASH, "dd if=", RuleKind.PREFIX),
    (PS, "reg delete", RuleKind.SUBCOMMAND),
    (BASH, "init 0", RuleKind.SUBCOMMAND),
    (BASH, "terraform destroy", RuleKind.SUBCOMMAND),
    (PS, "vssadmin delete shadows", RuleKind.SUBCOMMAND),
    (BASH, "shutdown -h", RuleKind.SUBCOMMAND),
    (BASH, "> /dev/sd", RuleKind.REDIRECT),
    (BASH, ">/dev/nvme", RuleKind.REDIRECT),
]


@pytest.mark.parametrize(("dialect", "pattern", "kind"), KINDS)
def test_the_kind_follows_from_the_words(dialect: Dialect, pattern: str, kind: RuleKind) -> None:
    compiled = rule(pattern, dialect)

    assert compiled.kind is kind
    assert compiled.reason == "motivo"
    assert compiled.dialect is dialect


def test_the_fork_bomb_is_a_literal_only_when_allowed() -> None:
    compiled = rule(FORK_BOMB, literal=True)

    assert compiled.kind is RuleKind.LITERAL
    with pytest.raises(RuleError):
        rule(FORK_BOMB)


@pytest.mark.parametrize(
    ("pattern", "literal"),
    [
        ("", False),
        ("   ", True),
        (f"echo $({SENTINEL})", False),
        (f"a {SENTINEL} && b", False),
        (f"a {SENTINEL} && b", True),
        (f"echo {SENTINEL} > x", False),
        (">", False),
        (f"> {SENTINEL} x", False),
    ],
)
def test_invalid_patterns_are_rejected_without_repeating_them(pattern: str, literal: bool) -> None:
    with pytest.raises(RuleError) as caught:
        rule(pattern, literal=literal)

    assert SENTINEL not in str(caught.value)


@pytest.mark.parametrize(
    "arguments",
    [(3, "motivo", BASH), ("ls", 3, BASH), ("ls", "  ", BASH), ("ls", "motivo", "bash")],
)
def test_wrong_types_are_rejected(arguments: tuple[object, object, object]) -> None:
    with pytest.raises((TypeError, RuleError)):
        compile_rule(*arguments)  # type: ignore[arg-type]


def test_a_rule_is_immutable() -> None:
    compiled = rule("shutdown")

    with pytest.raises(dataclasses.FrozenInstanceError):
        compiled.program = "otro"  # type: ignore[misc]


# --- matching -----------------------------------------------------------------------------------

MATCHES = [
    # program: only in the position of the program
    ("shutdown", BASH, "shutdown now", True),
    ("shutdown", BASH, "shutdown", True),
    ("shutdown", BASH, "cat shutdown.log", False),
    ("shutdown", BASH, "grep reboot shutdown", False),
    ("shutdown", BASH, "which shutdown", False),
    ("mkfs", BASH, "mkfs.ext4 /dev/sda1", True),
    ("mkfs", BASH, "mkfsx", False),
    ("Stop-Computer", PS, "stop-computer -force", True),
    ("Stop-Computer", PS, "STOP-COMPUTER", True),
    ("Stop-Computer", PS, "Get-Content Stop-Computer.txt", False),
    ("shutdown", BASH, "SHUTDOWN now", False),
    # target: complete targets only, options in any order or combination
    ("rm -rf /", BASH, "rm -rf /", True),
    ("rm -rf /", BASH, "rm -fr /", True),
    ("rm -rf /", BASH, "rm -r -f /", True),
    ("rm -rf /", BASH, "rm -f -r /", True),
    ("rm -rf /", BASH, "rm --recursive --force /", True),
    ("rm -rf /", BASH, "rm -R -f /", True),
    ("rm -rf /", BASH, "rm -rfv /", True),
    ("rm -rf /", BASH, "rm -rf /*", True),
    ("rm -rf /", BASH, "rm -rf //", True),
    ("rm -rf /", BASH, "rm -rf /.", True),
    ("rm -rf /", BASH, 'rm -rf "/"', True),
    ("rm -rf /", BASH, "rm -rf x /", True),
    ("rm -rf /", BASH, "rm -rf ~", True),
    ("rm -rf /", BASH, "rm -rf ~/*", True),
    ("rm -rf /", BASH, "rm -rf /tmp/build", False),
    ("rm -rf /", BASH, "rm -rf ~/proyecto/dist", False),
    ("rm -rf /", BASH, "rm -rf .", False),
    ("rm -rf /", BASH, "rm -rf *", False),
    ("rm -rf /", BASH, "rm -r /", False),
    ("rm -rf /", BASH, "rm /", False),
    ("rm -rf /", BASH, "ls -rf /", False),
    ("rm -rf /", BASH, "RM -rf /", False),
    ("chmod -R 777 /", BASH, "chmod -R 777 /", True),
    ("chmod -R 777 /", BASH, "chmod --recursive 777 /*", True),
    ("chmod -R 777 /", BASH, "chmod -R 777 ./dist", False),
    ("chmod -R 777 /", BASH, "chmod -R 755 /", False),
    ("chmod -R 777 /", BASH, "chmod -r 777 /", False),
    ("Remove-Item -Recurse -Force C:\\", PS, "Remove-Item -Recurse -Force C:\\", True),
    ("Remove-Item -Recurse -Force C:\\", PS, "remove-item -force -recurse c:/", True),
    ("Remove-Item -Recurse -Force C:\\", PS, "ri -r -fo C:\\", True),
    ("Remove-Item -Recurse -Force C:\\", PS, "rm -Rec -Fo D:\\*", True),
    ("Remove-Item -Recurse -Force C:\\", PS, "del -recurse -force C:", True),
    ("Remove-Item -Recurse -Force C:\\", PS, "Remove-Item -Recurse -Force ~", True),
    ("Remove-Item -Recurse -Force C:\\", PS, "Remove-Item -Recurse -Force \\", True),
    ("Remove-Item -Recurse -Force C:\\", PS, "Remove-Item -Recurse -Force C:\\proyecto", False),
    ("Remove-Item -Recurse -Force C:\\", PS, "Remove-Item -Recurse C:\\", False),
    ("Remove-Item -Recurse -Force C:\\", PS, "Remove-Item -Recurse -Force", False),
    # prefix
    ("dd if=", BASH, "dd if=/dev/zero of=a.img", True),
    ("dd if=", BASH, "dd of=a.img if=x", True),
    ("dd if=", BASH, "dd of=a.img", False),
    ("dd if=", BASH, "cat if=x", False),
    # subcommand
    ("reg delete", PS, "reg delete HKLM\\x /f", True),
    ("reg delete", PS, "REG DELETE x", True),
    ("reg delete", PS, "reg query x", False),
    ("init 0", BASH, "init 0", True),
    ("init 0", BASH, "init 3", False),
    ("vssadmin delete shadows", PS, "vssadmin delete shadows /all", True),
    ("vssadmin delete shadows", PS, "vssadmin list shadows", False),
    ("shutdown -h", BASH, "shutdown -h now", True),
    ("shutdown -h", BASH, "shutdown -r now", False),
]


@pytest.mark.parametrize(("pattern", "dialect", "command", "expected"), MATCHES)
def test_matching(pattern: str, dialect: Dialect, command: str, expected: bool) -> None:
    assert rule(pattern, dialect).matches(part(command, dialect)) is expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("echo x > /dev/sda", True),
        ("echo x > /dev/sdb1", True),
        ("echo x >> /dev/sda", True),
        ("echo x > salida.txt", False),
        ("cat /dev/sda", False),
    ],
)
def test_redirection_rules(command: str, expected: bool) -> None:
    assert rule("> /dev/sd").matches(part(command)) is expected


def test_redirection_rules_ignore_case_in_powershell() -> None:
    assert rule("> \\\\.\\PhysicalDrive", PS).matches(part("echo x > \\\\.\\physicaldrive0", PS))


def test_a_literal_rule_matches_the_raw_text_without_spaces() -> None:
    compiled = rule(FORK_BOMB, literal=True)

    assert compiled.matches_text(":(){ :|:& };:") is True
    assert compiled.matches_text("x; :( ) { : | : & } ; :") is True
    assert compiled.matches_text("echo hola") is False
    assert compiled.matches(part("ls")) is False


def test_only_literal_rules_match_text() -> None:
    assert rule("shutdown").matches_text("shutdown") is False


# --- the deny list ------------------------------------------------------------------------------


def deny_list(*extra: str) -> DenyList:
    base = [rule("rm -rf /"), rule("shutdown"), rule("> /dev/sd"), rule(FORK_BOMB, literal=True)]
    return DenyList(BASH, base, [rule(text) for text in extra], synonyms=BASH_SYNONYMS)


DENIES = [
    ("echo hola && rm -rf /", True),
    ("rm -rf / ; echo hola", True),
    ("ls | shutdown now", True),
    ("echo hola\nshutdown", True),
    ("echo $(shutdown now)", True),
    ("echo `shutdown`", True),
    ('bash -c "rm -rf /"', True),
    ("echo hola > $(shutdown)", True),
    ("echo x > /dev/sda", True),
    (":(){ :|:& };:", True),
    ("echo hola", False),
    ("cat shutdown.log", False),
    ('echo "no uses shutdown"', False),
    ('git commit -m "fix: shutdown limpio"', False),
    ("rm -rf /tmp/build", False),
    ("echo $(whoami)", False),
    ('bash -c "ls"', False),
]


@pytest.mark.parametrize(("command", "expected"), DENIES)
def test_the_list_searches_parts_executable_text_and_redirections(
    command: str, expected: bool
) -> None:
    rules = deny_list()
    parsed = parse_command(command, BASH, synonyms=rules.synonyms)

    assert rules.denies(parsed, command) is expected


def test_extra_entries_add_to_the_base() -> None:
    rules = deny_list("terraform destroy")
    command = "ls && terraform destroy -auto-approve"

    assert rules.denies(parse_command(command, BASH), command) is True
    assert len(rules.rules) == len(rules.base) + 1
    assert rules.rules[: len(rules.base)] == rules.base


def test_an_empty_extra_keeps_the_base() -> None:
    assert deny_list().rules == deny_list().base


class TestTheListCannotBeEmptiedOrChanged:
    def test_an_empty_base_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            DenyList(BASH, [])

    @pytest.mark.parametrize(
        "base",
        [None, "shutdown", ["shutdown"], [object()]],
    )
    def test_the_base_must_be_compiled_rules(self, base: object) -> None:
        with pytest.raises((TypeError, ValueError)):
            DenyList(BASH, base)  # type: ignore[arg-type]

    def test_the_extra_must_be_compiled_rules(self) -> None:
        with pytest.raises(TypeError):
            DenyList(BASH, [rule("shutdown")], ["x"])  # type: ignore[list-item]

    def test_the_dialect_must_be_a_dialect(self) -> None:
        with pytest.raises(TypeError):
            DenyList("bash", [rule("shutdown")])  # type: ignore[arg-type]

    def test_it_has_no_way_to_remove_entries(self) -> None:
        rules = deny_list()
        public = {name for name in dir(rules) if not name.startswith("_")}

        assert public == {"base", "extra", "rules", "dialect", "aliases", "synonyms", "denies"}
        with pytest.raises(dataclasses.FrozenInstanceError):
            rules.base = ()  # type: ignore[misc]
        with pytest.raises(TypeError):
            rules.aliases["x"] = "y"  # type: ignore[index]
        with pytest.raises(TypeError):
            rules.synonyms["rm"]["-x"] = "-y"  # type: ignore[index]

    def test_a_list_given_by_the_caller_is_copied(self) -> None:
        base = [rule("shutdown")]
        rules = DenyList(BASH, base)
        base.clear()

        assert len(rules.base) == 1
