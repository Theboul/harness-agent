"""The base deny list of each platform compiles and covers what HU-05-02 needs (T007).

``adapters/system/denied_commands.py`` keeps the data (HU-01-04, extended here): the entries per
interpreter, the program aliases of PowerShell and the option synonyms of bash. Every entry must
compile with the rules of the core and its own dialect; only the fork bomb is a literal rule. The
usual commands of development must not match the real base list.
"""

from __future__ import annotations

import pytest

from harness_agent.adapters.system import (
    DEFAULT_DENIED_COMMANDS,
    denied_commands_for,
    option_synonyms_for,
    program_aliases_for,
)
from harness_agent.core import DenyList, Dialect, RuleKind, compile_rule, parse_command
from tests.unit.core.permissions.test_command_policy import BASH_USUAL, PS_USUAL

FORK_BOMB = ":(){ :|:& };:"


def real_list(interpreter: str) -> DenyList:
    dialect = Dialect(interpreter)
    aliases = program_aliases_for(interpreter)
    synonyms = option_synonyms_for(interpreter)
    base = [
        compile_rule(
            entry.pattern,
            entry.reason,
            dialect,
            aliases=aliases,
            synonyms=synonyms,
            allow_literal=True,
        )
        for entry in denied_commands_for(interpreter)
    ]
    return DenyList(dialect, base, aliases=aliases, synonyms=synonyms)


@pytest.mark.parametrize("interpreter", ["bash", "powershell"])
def test_every_entry_compiles_with_its_dialect(interpreter: str) -> None:
    rules = real_list(interpreter)

    literal = [r for r in rules.base if r.kind is RuleKind.LITERAL]
    expected_literals = 1 if interpreter == "bash" else 0
    assert len(literal) == expected_literals
    assert len(rules.base) == len(denied_commands_for(interpreter))


def test_only_the_fork_bomb_is_a_literal() -> None:
    patterns = {entry.pattern for entry in denied_commands_for("bash")}

    assert FORK_BOMB in patterns
    (literal,) = [r for r in real_list("bash").base if r.kind is RuleKind.LITERAL]
    assert literal.matches_text(FORK_BOMB)


NEW_ENTRIES = {
    "bash": (
        "halt",
        "poweroff",
        "init 0",
        "init 6",
        "wipefs",
        "shred",
        "fdisk",
        "parted",
        "> /dev/sd",
        "> /dev/nvme",
        "> /dev/hd",
        "chown -R root /",
    ),
    "powershell": (
        "shutdown",
        "Remove-Item -Recurse -Force ~",
        "format",
        "Initialize-Disk",
        "Remove-Partition",
        "Disable-ComputerRestore",
        "bcdedit",
        "vssadmin delete shadows",
    ),
}


@pytest.mark.parametrize("interpreter", ["bash", "powershell"])
def test_the_new_entries_are_present_with_a_reason(interpreter: str) -> None:
    entries = {entry.pattern: entry.reason for entry in denied_commands_for(interpreter)}

    for pattern in NEW_ENTRIES[interpreter]:
        assert pattern in entries, pattern
        assert entries[pattern].strip()


def test_the_entries_of_hu_01_04_are_kept() -> None:
    bash = {entry.pattern for entry in denied_commands_for("bash")}
    powershell = {entry.pattern for entry in denied_commands_for("powershell")}

    assert {"rm -rf /", "rm -rf ~", "mkfs", "dd if=", FORK_BOMB, "shutdown", "reboot"} <= bash
    assert {"chmod -R 777 /"} <= bash
    assert {"Format-Volume", "Clear-Disk", "Stop-Computer", "Restart-Computer"} <= powershell
    assert {"Remove-Item -Recurse -Force C:\\", "Set-ExecutionPolicy", "reg delete"} <= powershell


@pytest.mark.parametrize("alias", ["rm", "ri", "del", "erase", "rd", "rmdir"])
def test_powershell_aliases_resolve_to_remove_item(alias: str) -> None:
    assert program_aliases_for("powershell")[alias] == "remove-item"


def test_bash_synonyms_of_rm_chmod_and_chown() -> None:
    synonyms = option_synonyms_for("bash")

    assert synonyms["rm"]["--recursive"] == "-r"
    assert synonyms["rm"]["--force"] == "-f"
    assert synonyms["rm"]["-R"] == "-r"
    assert synonyms["chmod"]["--recursive"] == "-R"
    assert synonyms["chown"]["--recursive"] == "-R"


class TestTheTablesAreReadOnly:
    def test_aliases(self) -> None:
        with pytest.raises(TypeError):
            program_aliases_for("powershell")["x"] = "y"  # type: ignore[index]

    def test_synonyms(self) -> None:
        with pytest.raises(TypeError):
            option_synonyms_for("bash")["rm"]["-x"] = "-y"  # type: ignore[index]
        with pytest.raises(TypeError):
            option_synonyms_for("bash")["x"] = {}  # type: ignore[index]

    def test_an_unknown_interpreter_has_empty_tables(self) -> None:
        assert dict(program_aliases_for("zsh")) == {}
        assert dict(option_synonyms_for("zsh")) == {}
        assert dict(program_aliases_for("bash")) == {}
        assert dict(option_synonyms_for("powershell")) == {}

    def test_the_default_mapping_is_still_read_only(self) -> None:
        with pytest.raises(TypeError):
            DEFAULT_DENIED_COMMANDS["powershell"] = ()  # type: ignore[index]


@pytest.mark.parametrize(
    ("interpreter", "command"),
    [("bash", command) for command in BASH_USUAL]
    + [("powershell", command) for command in PS_USUAL],
)
def test_the_usual_commands_do_not_match_the_real_base(interpreter: str, command: str) -> None:
    rules = real_list(interpreter)
    parsed = parse_command(command, rules.dialect, aliases=rules.aliases, synonyms=rules.synonyms)

    assert rules.denies(parsed, command) is False


@pytest.mark.parametrize(
    ("interpreter", "command"),
    [
        ("bash", "sudo halt"),
        ("bash", "init 0"),
        ("bash", "echo x > /dev/nvme0n1"),
        ("bash", "chown -R root /"),
        ("bash", "wipefs -a /dev/sda"),
        ("powershell", "shutdown /s /t 0"),
        ("powershell", "rm -Recurse -Force ~"),
        ("powershell", "format C:"),
        ("powershell", "vssadmin delete shadows /all"),
        ("powershell", "Initialize-Disk -Number 1"),
    ],
)
def test_the_new_entries_deny_their_commands(interpreter: str, command: str) -> None:
    rules = real_list(interpreter)
    parsed = parse_command(command, rules.dialect, aliases=rules.aliases, synonyms=rules.synonyms)

    assert rules.denies(parsed, command) is True
