"""The table of git subcommands is data only (HU-11-02 / T002).

``core/permissions/git_table.py`` holds what the Product Owner reviews: which subcommands are
reads, which options make one destructive and which global options are known. It has no logic
(checked with ``ast``), its values are immutable, and a denied subcommand or option never appears
among the reads or the listing options.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import MappingProxyType

import pytest

from harness_agent.core.permissions import git_table

MODULE = Path(git_table.__file__)


class TestTheContent:
    def test_the_reads_of_q1(self) -> None:
        assert git_table.READ_SUBCOMMANDS == frozenset(
            {
                "status",
                "diff",
                "log",
                "show",
                "blame",
                "shortlog",
                "describe",
                "rev-parse",
                "ls-files",
                "grep",
            }
        )

    def test_listing_subcommands_and_their_options(self) -> None:
        assert set(git_table.LISTING_SHORT) == {"branch", "tag"}
        assert set(git_table.LISTING_LONG) == {"branch", "tag"}
        assert {"a", "r", "l", "v"} <= git_table.LISTING_SHORT["branch"]
        assert {"--all", "--remotes", "--list", "--verbose", "--show-current"} <= (
            git_table.LISTING_LONG["branch"]
        )
        assert {"l", "n"} <= git_table.LISTING_SHORT["tag"]
        assert "--list" in git_table.LISTING_LONG["tag"]
        assert git_table.LIST_PATTERN_SHORT == frozenset({"l"})
        assert git_table.LIST_PATTERN_LONG == frozenset({"--list"})

    def test_the_options_with_effects(self) -> None:
        assert git_table.READ_EFFECT_LONG == frozenset(
            {"--output", "--ext-diff", "--textconv", "--no-index"}
        )
        assert git_table.GREP_EFFECT_SHORT == frozenset({"O"})
        assert git_table.GREP_EFFECT_LONG == frozenset({"--open-files-in-pager"})

    def test_the_destructive_options_of_q2(self) -> None:
        long = git_table.DESTRUCTIVE_LONG
        short = git_table.DESTRUCTIVE_SHORT
        assert long["reset"] == frozenset({"--hard", "--merge", "--keep"})
        assert long["push"] == frozenset(
            {"--force", "--force-with-lease", "--force-if-includes", "--delete", "--mirror"}
        )
        assert long["checkout"] == frozenset({"--force"})
        assert long["switch"] == frozenset({"--discard-changes", "--force"})
        assert short["push"] == frozenset({"f", "d"})
        assert short["checkout"] == frozenset({"f"})
        assert short["switch"] == frozenset({"f"})
        assert short["branch"] == frozenset({"D"})
        assert short["update-ref"] == frozenset({"d"})
        assert git_table.ALWAYS_DESTRUCTIVE == frozenset({"clean", "filter-branch"})
        assert git_table.PUSH_DESTRUCTIVE_REFSPECS == ("+", ":")
        assert git_table.CHECKOUT_DESTRUCTIVE_PATHS == frozenset({"."})

    def test_the_destructive_actions_of_subcommands(self) -> None:
        assert git_table.STASH_READ_ACTIONS == frozenset({"list"})
        assert git_table.STASH_DESTRUCTIVE_ACTIONS == frozenset({"drop", "clear"})
        assert git_table.REFLOG_DESTRUCTIVE_ACTIONS == frozenset({"expire"})
        assert git_table.GC_DESTRUCTIVE_PRUNE == frozenset({"now"})
        assert git_table.BRANCH_FORCE_DELETE == (
            frozenset({"d"}),
            frozenset({"--delete"}),
            frozenset({"f"}),
            frozenset({"--force"}),
        )
        assert git_table.RESTORE_STAGED == (frozenset({"S"}), frozenset({"--staged"}))
        assert git_table.RESTORE_WORKTREE == (frozenset({"W"}), frozenset({"--worktree"}))

    def test_the_global_options(self) -> None:
        assert git_table.KNOWN_GLOBAL_WITH_VALUE == frozenset({"-C", "--git-dir", "--work-tree"})
        assert {"--no-pager", "-P", "-p", "--paginate", "--bare"} <= (git_table.KNOWN_GLOBAL_FLAGS)
        assert "-c" not in git_table.KNOWN_GLOBAL_FLAGS
        assert "-c" not in git_table.KNOWN_GLOBAL_WITH_VALUE


class TestCoherence:
    def test_a_destructive_subcommand_is_never_a_read_or_a_listing(self) -> None:
        destructive = (
            git_table.ALWAYS_DESTRUCTIVE
            | set(git_table.DESTRUCTIVE_LONG)
            | set(git_table.DESTRUCTIVE_SHORT)
            | {"stash", "reflog", "gc", "restore", "update-ref"}
        )

        assert not destructive & git_table.READ_SUBCOMMANDS

    def test_a_destructive_option_is_never_a_listing_option(self) -> None:
        for subcommand in git_table.LISTING_LONG:
            assert (
                not git_table.DESTRUCTIVE_LONG.get(subcommand, frozenset())
                & (git_table.LISTING_LONG[subcommand])
            )
            assert (
                not git_table.DESTRUCTIVE_SHORT.get(subcommand, frozenset())
                & (git_table.LISTING_SHORT[subcommand])
            )
        deleting = git_table.BRANCH_FORCE_DELETE
        assert not (deleting[0] | deleting[2]) & git_table.LISTING_SHORT["branch"]
        assert not (deleting[1] | deleting[3]) & git_table.LISTING_LONG["branch"]

    def test_the_stash_reads_and_the_destructive_actions_differ(self) -> None:
        assert not git_table.STASH_READ_ACTIONS & git_table.STASH_DESTRUCTIVE_ACTIONS

    def test_no_effect_option_is_a_listing_option(self) -> None:
        for options in git_table.LISTING_LONG.values():
            assert not git_table.READ_EFFECT_LONG & options


IMMUTABLE = (frozenset, tuple, MappingProxyType, str)


class TestImmutability:
    @pytest.mark.parametrize(
        "name", [n for n in dir(git_table) if n.isupper() and not n.startswith("_")]
    )
    def test_every_value_is_immutable(self, name: str) -> None:
        value = getattr(git_table, name)

        assert isinstance(value, IMMUTABLE), name
        if isinstance(value, MappingProxyType):
            for inner in value.values():
                assert isinstance(inner, IMMUTABLE), name

    def test_a_mapping_cannot_be_changed(self) -> None:
        with pytest.raises(TypeError):
            git_table.DESTRUCTIVE_LONG["push"] = frozenset()  # type: ignore[index]
        with pytest.raises(AttributeError):
            git_table.READ_SUBCOMMANDS.add("push")  # type: ignore[attr-defined]


def logic_in(source: str) -> list[str]:
    """Anything in the module that is not a docstring, an import or a plain assignment."""
    tree = ast.parse(source)
    found: list[str] = []
    for node in tree.body:
        allowed = isinstance(node, ast.Import | ast.ImportFrom | ast.Assign | ast.AnnAssign) or (
            isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        )
        if not allowed:
            found.append(f"{type(node).__name__} at line {node.lineno}")
    for inner in ast.walk(tree):
        if isinstance(
            inner,
            ast.FunctionDef
            | ast.AsyncFunctionDef
            | ast.ClassDef
            | ast.Lambda
            | ast.If
            | ast.For
            | ast.While
            | ast.ListComp
            | ast.SetComp
            | ast.DictComp
            | ast.GeneratorExp,
        ):
            found.append(f"{type(inner).__name__} at line {getattr(inner, 'lineno', 0)}")
    return found


class TestNoLogic:
    def test_the_table_has_only_data(self) -> None:
        assert logic_in(MODULE.read_text(encoding="utf-8")) == []

    @pytest.mark.parametrize(
        "fragment",
        [
            "def f():\n    return 1\n",
            "class C:\n    pass\n",
            "X = lambda: 1\n",
            "if True:\n    X = 1\n",
            "X = frozenset(x for x in 'ab')\n",
            "X = {k: 1 for k in 'ab'}\n",
            "for x in 'ab':\n    pass\n",
        ],
    )
    def test_the_detector_finds_logic(self, fragment: str) -> None:
        assert logic_in(fragment)

    def test_the_detector_accepts_plain_data(self) -> None:
        source = '"""Doc."""\nfrom types import MappingProxyType\nX = frozenset({"a"})\n'

        assert logic_in(source) == []
