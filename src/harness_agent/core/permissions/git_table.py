"""Table of git subcommands for the shell policy (HU-11-02): data only, reviewed by the PO.

The rules that read this table live in ``git_rules.py``. Here there is no logic, only immutable
data: which subcommands are reads that may run without asking, which options make a subcommand
destructive (denied), and which global options of git are known. Anything that is not listed as a
read or as destructive is asked.
"""

from __future__ import annotations

from types import MappingProxyType

# --- Reads: allowed without asking (Q1) -----------------------------------------------------------

# Subcommands that only read the repository.
READ_SUBCOMMANDS = frozenset(
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

# ``branch`` and ``tag`` are reads only when they list: no positional argument (unless a list
# pattern is given with ``-l``/``--list``) and only these options. Any other use creates, renames
# or deletes, and is asked (or denied, see below).
LISTING_SHORT = MappingProxyType(
    {
        "branch": frozenset({"a", "r", "l", "v"}),
        "tag": frozenset({"l", "n", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}),
    }
)
LISTING_LONG = MappingProxyType(
    {
        "branch": frozenset(
            {
                "--all",
                "--remotes",
                "--list",
                "--verbose",
                "--merged",
                "--no-merged",
                "--contains",
                "--no-contains",
                "--show-current",
                "--sort",
                "--format",
                "--color",
                "--no-color",
                "--column",
                "--no-column",
                "--points-at",
            }
        ),
        "tag": frozenset(
            {
                "--list",
                "--sort",
                "--format",
                "--contains",
                "--no-contains",
                "--points-at",
                "--merged",
                "--no-merged",
                "--column",
                "--no-column",
                "--color",
            }
        ),
    }
)
# With one of these, the positional arguments of ``branch``/``tag`` are list patterns.
LIST_PATTERN_SHORT = frozenset({"l"})
LIST_PATTERN_LONG = frozenset({"--list"})

# ``stash`` is a read only for ``stash list``.
STASH_READ_ACTIONS = frozenset({"list"})

# Options that make a read write files, read outside the repository or run programs: the read is
# then asked. A prefix of one of them counts as the option (``--out`` is ``--output``).
READ_EFFECT_LONG = frozenset({"--output", "--ext-diff", "--textconv", "--no-index"})
GREP_EFFECT_SHORT = frozenset({"O"})
GREP_EFFECT_LONG = frozenset({"--open-files-in-pager"})

# --- Destructive: denied (AC-02, Q2) --------------------------------------------------------------

# Always destructive, whatever the options (``clean -n`` included).
ALWAYS_DESTRUCTIVE = frozenset({"clean", "filter-branch"})

# Long options that make a subcommand destructive. A prefix of one of them counts as the option,
# even if it could also be the prefix of another one (``--forc`` is ``--force``).
DESTRUCTIVE_LONG = MappingProxyType(
    {
        "reset": frozenset({"--hard", "--merge", "--keep"}),
        "push": frozenset(
            {"--force", "--force-with-lease", "--force-if-includes", "--delete", "--mirror"}
        ),
        "checkout": frozenset({"--force"}),
        "switch": frozenset({"--discard-changes", "--force"}),
    }
)

# Short options that make a subcommand destructive (grouped short options are split first).
DESTRUCTIVE_SHORT = MappingProxyType(
    {
        "push": frozenset({"f", "d"}),
        "checkout": frozenset({"f"}),
        "switch": frozenset({"f"}),
        "branch": frozenset({"D"}),
        "update-ref": frozenset({"d"}),
    }
)

# ``push`` arguments that force or delete a remote branch: ``+main``, ``+HEAD:main``, ``:rama``.
PUSH_DESTRUCTIVE_REFSPECS = ("+", ":")

# ``checkout`` that throws away changes: with ``--`` and paths, or with ``.``.
CHECKOUT_DESTRUCTIVE_PATHS = frozenset({"."})

# ``branch`` deleting with force: (short delete, long delete, short force, long force).
BRANCH_FORCE_DELETE = (
    frozenset({"d"}),
    frozenset({"--delete"}),
    frozenset({"f"}),
    frozenset({"--force"}),
)

# ``restore`` is destructive unless it only touches the index (``--staged`` without
# ``--worktree``): (short, long) of each.
RESTORE_STAGED = (frozenset({"S"}), frozenset({"--staged"}))
RESTORE_WORKTREE = (frozenset({"W"}), frozenset({"--worktree"}))

# ``stash drop``/``stash clear``, ``reflog expire`` and ``gc --prune=now``.
STASH_DESTRUCTIVE_ACTIONS = frozenset({"drop", "clear"})
REFLOG_DESTRUCTIVE_ACTIONS = frozenset({"expire"})
GC_DESTRUCTIVE_PRUNE = frozenset({"now"})

# --- Global options (before the subcommand) -----------------------------------------------------

# Known and without effects: they are skipped to find the subcommand.
KNOWN_GLOBAL_WITH_VALUE = frozenset({"-C", "--git-dir", "--work-tree"})
KNOWN_GLOBAL_FLAGS = frozenset(
    {
        "--no-pager",
        "-P",
        "-p",
        "--paginate",
        "--bare",
        "--no-replace-objects",
        "--literal-pathspecs",
        "--glob-pathspecs",
        "--noglob-pathspecs",
        "--icase-pathspecs",
        "--no-optional-locks",
    }
)
# Any other global option (``-c``, ``--config-env``, ``--exec-path``, ``--namespace``…) may change
# what git runs: the call is asked at least.
