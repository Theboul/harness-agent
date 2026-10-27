"""Tests for ``classify_git``: the class of one git call (HU-11-02 / T003).

Each case is parsed with the parser of HU-05-02 in bash and in PowerShell, and the git part is
classified as a read (allowed if the whole command is reads), asked or denied. Nothing runs.
"""

from __future__ import annotations

import pytest

from harness_agent.core import CommandPart, Dialect, GitClass, classify_git, parse_command

BASH, PS = Dialect.BASH, Dialect.POWERSHELL
READ, ASK, DENY = GitClass.READ, GitClass.ASK, GitClass.DENY
SENTINEL = "VALOR-DE-PRUEBA-123"


def git_part(command: str, dialect: Dialect) -> CommandPart:
    parts = [p for p in parse_command(command, dialect).parts if p.program == "git"]
    assert len(parts) == 1, command
    return parts[0]


def classify(command: str, dialect: Dialect, *, risky: bool = False) -> GitClass:
    return classify_git(git_part(command, dialect), risky_environment=risky)


BOTH = [BASH, PS]

READS = [
    "git status",
    "git diff",
    "git diff --stat",
    "git diff --cached",
    "git diff --no-ext-diff",
    "git diff --no-textconv",
    "git log",
    "git log --oneline -5",
    "git log -p",
    "git show HEAD",
    "git blame a.py",
    "git shortlog -sn",
    "git describe --tags",
    "git rev-parse HEAD",
    "git ls-files",
    "git grep foo",
    "git -C sub status",
    "git --no-pager log",
    "git --git-dir=.git --work-tree=. status",
    "git --git-dir .git status",
    "git -P log",
    "git --paginate log",
    "git branch",
    "git branch -a",
    "git branch -r",
    "git branch -vv",
    "git branch --show-current",
    "git branch --list 'feat*'",
    "git branch -l feat",
    "git tag",
    "git tag -l",
    "git tag -n5",
    "git tag --list 'v1*'",
    "git stash list",
    "git.exe status",
]
BASH_ONLY_READS = [
    "/usr/bin/git status",
    '"C:\\Program Files\\Git\\bin\\git.exe" status',
    "sudo git status",
    "LANG=C git log",
]
PS_ONLY_READS = [
    "C:\\Git\\cmd\\git.exe status",
    "GIT status",
]


@pytest.mark.parametrize("dialect", BOTH)
@pytest.mark.parametrize("command", READS)
def test_reads(dialect: Dialect, command: str) -> None:
    assert classify(command, dialect) is READ


@pytest.mark.parametrize("command", BASH_ONLY_READS)
def test_bash_reads(command: str) -> None:
    assert classify(command, BASH) is READ


@pytest.mark.parametrize("command", PS_ONLY_READS)
def test_powershell_reads(command: str) -> None:
    assert classify(command, PS) is READ


ASKED = [
    # global options that may change what git runs, or no subcommand
    "git -c core.pager=less log",
    "git -c alias.x=push x",
    "git --config-env=a=B status",
    "git --exec-path=/x status",
    "git --exec-path status",
    "git --namespace=n status",
    "git --frobnicate status",
    "git",
    "git --version",
    "git -C",
    # reads with effects
    "git diff --output=x",
    "git diff --out x",
    "git log --ext-diff",
    "git log --ext",
    "git diff --textconv",
    "git diff --text",
    "git diff --no-index a b",
    "git diff --no",
    "git grep -O foo",
    "git grep --open-files-in-pager foo",
    "git grep --open foo",
    "git log > salida.txt",
    # writes, unknown and aliases
    "git commit -m mensaje",
    "git push origin main",
    "git push",
    "git push -u origin main",
    "git push --follow-tags",
    "git merge rama",
    "git add .",
    "git switch -c nueva",
    "git switch main",
    "git checkout -b nueva",
    "git checkout main",
    "git checkout a.py",
    "git branch nueva",
    "git branch -m vieja nueva",
    "git branch -d rama",
    "git branch --delete rama",
    "git branch --merged main",
    "git tag v1",
    "git tag -d v1",
    "git rebase main",
    "git cherry-pick abc",
    "git revert abc",
    "git reset HEAD~1",
    "git reset --soft HEAD~1",
    "git restore --staged a.py",
    "git restore -S a.py",
    "git stash",
    "git stash push",
    "git stash pop",
    "git stash show",
    "git reflog",
    "git reflog show",
    "git gc",
    "git gc --prune=2.weeks.ago",
    "git update-ref refs/heads/x HEAD",
    "git fetch",
    "git pull",
    "git init",
    "git clone https://servidor/r.git",
    "git config user.name x",
    "git remote -v",
    "git st",
    "git frobnicate",
    "git STATUS",
    "git push -F",
]


@pytest.mark.parametrize("dialect", BOTH)
@pytest.mark.parametrize("command", ASKED)
def test_asked(dialect: Dialect, command: str) -> None:
    assert classify(command, dialect) is ASK


DENIED = [
    "git reset --hard",
    "git reset --hard HEAD~1",
    "git reset --ha",
    "git reset --merge",
    "git reset --keep HEAD~1",
    "git clean -fd",
    "git clean -n",
    "git clean",
    "git push --force",
    "git push --forc",
    "git push --f",
    "git push -f",
    "git push -fu origin main",
    "git push --force-with-lease",
    "git push --force-w",
    "git push --force-with-lease=main:abc",
    "git push --force-if-includes",
    "git push origin +main",
    "git push origin +HEAD:main",
    "git push origin main +dev",
    "git push origin :rama",
    "git push --delete origin rama",
    "git push -d origin rama",
    "git push --mirror",
    "git -C x push --force",
    "git --no-pager push -f",
    "git -c a.b=c push --force",
    "git checkout -f",
    "git checkout --force main",
    "git checkout --for main",
    "git checkout -qf main",
    "git checkout -- a.py",
    "git checkout main -- a.py",
    "git checkout .",
    "git restore a.py",
    "git restore .",
    "git restore --worktree a.py",
    "git restore --staged --worktree a.py",
    "git restore -SW a.py",
    "git switch --discard-changes main",
    "git switch -f main",
    "git switch --force main",
    "git branch -D rama",
    "git branch -Df rama",
    "git branch -d -f rama",
    "git branch --delete --force rama",
    "git branch -df rama",
    "git stash drop",
    "git stash clear",
    "git reflog expire --all",
    "git gc --prune=now",
    "git gc --prune now",
    "git filter-branch",
    "git update-ref -d HEAD",
]


@pytest.mark.parametrize("dialect", BOTH)
@pytest.mark.parametrize("command", DENIED)
def test_denied(dialect: Dialect, command: str) -> None:
    assert classify(command, dialect) is DENY


class TestRiskyEnvironment:
    @pytest.mark.parametrize("command", ["git status", "git log", "git branch"])
    def test_it_turns_a_read_into_ask(self, command: str) -> None:
        assert classify(command, BASH, risky=True) is ASK

    def test_it_never_lowers_a_denial(self) -> None:
        assert classify("git push --force", BASH, risky=True) is DENY

    def test_it_keeps_an_ask(self) -> None:
        assert classify("git commit -m x", BASH, risky=True) is ASK


class TestRedirections:
    def test_a_read_with_a_redirection_is_asked(self) -> None:
        assert classify("git log > x", BASH) is ASK
        assert classify("git log > x", PS) is ASK

    def test_a_denial_with_a_redirection_is_still_denied(self) -> None:
        assert classify("git clean -fd > x", BASH) is DENY


class TestErrors:
    def test_a_part_that_is_not_git_is_rejected(self) -> None:
        (part,) = parse_command(f"ls {SENTINEL}", BASH).parts

        with pytest.raises(ValueError) as caught:
            classify_git(part)

        assert SENTINEL not in str(caught.value)

    def test_the_classes_are_named_in_spanish(self) -> None:
        assert (READ.value, ASK.value, DENY.value) == ("lectura", "preguntar", "denegar")
