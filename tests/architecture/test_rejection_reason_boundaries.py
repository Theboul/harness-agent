"""Architecture guards of the rejection reason (HU-05-04).

* In ``core/loop.py`` the reason (``.reason`` of the outcome) and ``rejection_message`` are used
  only in ``_ask_approval`` (the rejection branch): no event payload builder and no other function
  of the loop touches the reason, and the failed-approval branch never receives it.
* ``clean_reason`` and ``rejection_message`` are plain synchronous functions: pure, total, with the
  sanitizing step (``hide_url_credentials``) inside the core.
* In ``cli/approval.py`` the reason typed by the user is never written back: the only text that
  ``_read_reason`` writes is the fixed prompt (or an empty line).

The rules have a self-test with synthetic fragments. The generic checks of the module (imports,
I/O, cancellation, ``PermissionDecision``) are in ``test_approvals_boundaries.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core"
APPROVALS_FILE = CORE_DIR / "permissions" / "approvals.py"
LOOP_FILE = CORE_DIR / "loop.py"
CLI_APPROVAL_FILE = CORE_DIR.parent / "cli" / "approval.py"


def _owners(tree: ast.AST) -> dict[ast.AST, str]:
    owner: dict[ast.AST, str] = {}
    for function in ast.walk(tree):
        if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
            for child in ast.walk(function):
                owner.setdefault(child, function.name)
    return owner


def reason_users(source: str) -> set[str]:
    """Functions that read ``outcome.reason`` or call ``rejection_message``."""
    tree = ast.parse(source)
    owner = _owners(tree)
    users: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "reason":
            if not (isinstance(node.value, ast.Name) and node.value.id == "outcome"):
                continue  # e.g. ``verdict.reason``: the policy's reason, not the user's
            users.add(owner.get(node, "<module>"))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "rejection_message":
                users.add(owner.get(node, "<module>"))
    return users


def failed_branch_uses_reason(source: str) -> bool:
    """True when the ``outcome.action is None`` branch of ``_ask_approval`` mentions the reason."""
    tree = ast.parse(source)
    for function in ast.walk(tree):
        if not (isinstance(function, ast.AsyncFunctionDef) and function.name == "_ask_approval"):
            continue
        for node in ast.walk(function):
            if isinstance(node, ast.If) and "action" in ast.unparse(node.test):
                body = "\n".join(ast.unparse(statement) for statement in node.body)
                if "reason" in body or "rejection_message" in body:
                    return True
    return False


def function_kinds(source: str, names: set[str]) -> dict[str, type]:
    return {
        node.name: type(node)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name in names
    }


def written_by(source: str, function_name: str) -> list[str]:
    """Unparsed arguments of every ``put_line`` call inside ``function_name``."""
    tree = ast.parse(source)
    owner = _owners(tree)
    return [
        ast.unparse(arg)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "put_line"
        and owner.get(node) == function_name
        for arg in node.args[1:]
    ]


def test_only_ask_approval_uses_the_reason_in_the_loop() -> None:
    assert reason_users(LOOP_FILE.read_text(encoding="utf-8")) == {"_ask_approval"}


def test_the_failed_approval_branch_never_uses_the_reason() -> None:
    assert not failed_branch_uses_reason(LOOP_FILE.read_text(encoding="utf-8"))


def test_the_pure_functions_are_synchronous_and_exist() -> None:
    kinds = function_kinds(
        APPROVALS_FILE.read_text(encoding="utf-8"), {"clean_reason", "rejection_message"}
    )
    assert kinds == {"clean_reason": ast.FunctionDef, "rejection_message": ast.FunctionDef}


def test_the_pure_functions_never_raise_on_purpose() -> None:
    tree = ast.parse(APPROVALS_FILE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in {"clean_reason", "rejection_message"}:
            assert not [n for n in ast.walk(node) if isinstance(n, ast.Raise)], node.name


def test_the_credentials_are_hidden_inside_the_core() -> None:
    assert "hide_url_credentials" in APPROVALS_FILE.read_text(encoding="utf-8")


def test_the_terminal_writes_only_fixed_text_while_reading_the_reason() -> None:
    written = written_by(CLI_APPROVAL_FILE.read_text(encoding="utf-8"), "_read_reason")
    assert written, "the reason prompt must be written"
    assert set(written) <= {"REASON_PROMPT", "''"}


class TestSelfTest:
    def test_a_second_user_of_the_reason_is_detected(self) -> None:
        source = (
            "class L:\n"
            "    async def _ask_approval(self, outcome):\n"
            "        return rejection_message('x', outcome.reason)\n"
            "    def _payload(self, outcome):\n        return {'r': outcome.reason}\n"
            "    def _policy(self, verdict):\n        return verdict.reason\n"
        )
        assert reason_users(source) == {"_ask_approval", "_payload"}

    def test_the_reason_in_the_failed_branch_is_detected(self) -> None:
        bad = (
            "class L:\n    async def _ask_approval(self, o):\n"
            "        if o.action is None:\n            return rejection_message('x', o.reason)\n"
        )
        good = (
            "class L:\n    async def _ask_approval(self, o):\n"
            "        if o.action is None:\n            return 'failed'\n"
            "        return rejection_message('x', o.reason)\n"
        )
        assert failed_branch_uses_reason(bad)
        assert not failed_branch_uses_reason(good)

    def test_an_async_pure_function_is_detected(self) -> None:
        kinds = function_kinds("async def clean_reason(r):\n    return r\n", {"clean_reason"})
        assert kinds["clean_reason"] is ast.AsyncFunctionDef

    def test_echoing_the_reason_is_detected(self) -> None:
        source = (
            "def _read_reason(s, out):\n    put_line(out, REASON_PROMPT, end='')\n"
            "    a = s.readline()\n    put_line(out, a)\n"
        )
        assert "a" in written_by(source, "_read_reason")
