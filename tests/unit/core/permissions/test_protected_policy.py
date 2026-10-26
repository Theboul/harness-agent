"""ProtectedPolicy: denial of the protected harness folder for files and shell (HU-11-01 / T007)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from harness_agent.core import PermissionDecision, ToolCall
from harness_agent.core.permissions import ProtectedPolicy
from tests.doubles.dummy_authorized_area import DummyAuthorizedArea
from tests.doubles.scripted_policy import ScriptedPolicy

SENTINEL = "VALOR-DE-PRUEBA-123"
ALL_TOOLS = ["leer_archivo", "escribir_archivo", "listar_archivos", "buscar_texto", "otra"]


@pytest.fixture
def protected_dir(tmp_path: Path) -> Path:
    folder = tmp_path / ".harness"
    folder.mkdir()
    return folder


def make(
    protected_dir: Path,
    inner_decision: Any = PermissionDecision.ALLOW,
    markers: tuple[str, ...] = (".harness", "sessions.db"),
) -> tuple[ProtectedPolicy, ScriptedPolicy]:
    names = [*ALL_TOOLS, "shell"]
    inner = ScriptedPolicy({name: inner_decision for name in names})
    return ProtectedPolicy(inner, DummyAuthorizedArea(protected_dir), markers), inner


def call(name: str, **arguments: Any) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments)


@pytest.mark.parametrize("tool", ALL_TOOLS)
@pytest.mark.parametrize(
    "path",
    [
        ".harness/sessions.db",
        ".harness/tareas/s1/criterios.json",
        ".harness",
        "sub/../.harness/sessions.db",
    ],
)
def test_any_tool_with_a_path_inside_the_protected_folder_is_denied(
    tmp_path: Path, protected_dir: Path, tool: str, path: str
) -> None:
    protected = ProtectedPolicy(
        ScriptedPolicy({tool: PermissionDecision.ALLOW}),
        _Anchored(protected_dir, tmp_path),
        (),
    )

    assert protected.evaluate(call(tool, path=path)) is PermissionDecision.DENY


class _Anchored(DummyAuthorizedArea):
    """The double resolves relative paths under its own root; anchor them to the workspace."""

    def __init__(self, root: Path, workspace: Path) -> None:
        super().__init__(root)
        self._workspace = workspace

    def contains(self, path: Path | str) -> bool:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self._workspace / candidate
        return super().contains(candidate)


def test_absolute_path_inside_is_denied_and_the_inner_policy_is_not_consulted(
    protected_dir: Path,
) -> None:
    policy, inner = make(protected_dir)

    decision = policy.evaluate(call("escribir_archivo", path=str(protected_dir / "sessions.db")))

    assert decision is PermissionDecision.DENY
    assert inner.received == []


def test_a_path_outside_the_protected_folder_follows_the_inner_policy(
    tmp_path: Path, protected_dir: Path
) -> None:
    for inner_decision in PermissionDecision:
        policy, inner = make(protected_dir, inner_decision)
        outside = str(tmp_path / "src" / "main.py")

        assert policy.evaluate(call("leer_archivo", path=outside)) is inner_decision
        assert len(inner.received) == 1


@pytest.mark.parametrize(
    "command",
    [
        "cat .harness/sessions.db",
        "type .HARNESS\\sessions.db",
        "sqlite3 SESSIONS.DB 'delete from criterios'",
        "echo x > ./.harness/tareas/s/x.json",
        "Remove-Item -Force .\\.harness\\sessions.db",
    ],
)
def test_a_shell_command_naming_the_protected_files_is_denied(
    protected_dir: Path, command: str
) -> None:
    policy, inner = make(protected_dir)

    assert policy.evaluate(call("shell", command=command)) is PermissionDecision.DENY
    assert inner.received == []


@pytest.mark.parametrize("command", ["ls -la", "pytest tests", "git status", "echo hola"])
def test_a_shell_command_that_does_not_name_them_follows_the_inner_policy(
    protected_dir: Path, command: str
) -> None:
    policy, inner = make(protected_dir, PermissionDecision.ASK)

    assert policy.evaluate(call("shell", command=command)) is PermissionDecision.ASK
    assert len(inner.received) == 1


def test_known_limitation_a_disguised_command_is_not_detected(protected_dir: Path) -> None:
    """Regla 6 of the story: no interpretation of compound commands, variables or wildcards."""
    policy, _ = make(protected_dir, PermissionDecision.ASK)

    for command in ["cat .har*/sess*", 'D=.har; cat "${D}ness/s*"', "cd . && cat $(echo c2Vz)"]:
        assert policy.evaluate(call("shell", command=command)) is PermissionDecision.ASK


def test_markers_only_apply_to_the_shell_tool_and_to_its_command(protected_dir: Path) -> None:
    policy, inner = make(protected_dir, PermissionDecision.ALLOW)

    assert policy.evaluate(call("buscar_texto", pattern=".harness")) is PermissionDecision.ALLOW
    assert policy.evaluate(call("otra", command="cat .harness/x")) is PermissionDecision.ALLOW
    assert policy.evaluate(call("shell", comando=".harness")) is PermissionDecision.ALLOW
    assert policy.evaluate(call("shell", command=42)) is PermissionDecision.ALLOW
    assert len(inner.received) == 4


def test_non_text_path_is_left_to_the_inner_policy(protected_dir: Path) -> None:
    policy, inner = make(protected_dir, PermissionDecision.DENY)

    assert policy.evaluate(call("leer_archivo", path=42)) is PermissionDecision.DENY
    assert len(inner.received) == 1


def test_malformed_calls_are_denied(protected_dir: Path) -> None:
    policy, _ = make(protected_dir)

    for bad in [
        None,
        "leer_archivo",
        ToolCall(id="c", name="", arguments={}),
        ToolCall(id="c", name="x", arguments=None),  # type: ignore[arg-type]
    ]:
        assert policy.evaluate(bad) is PermissionDecision.DENY  # type: ignore[arg-type]


def test_any_failure_while_evaluating_is_a_denial(protected_dir: Path) -> None:
    class Exploding(DummyAuthorizedArea):
        def contains(self, path: Path | str) -> bool:
            raise RuntimeError(SENTINEL)

    boom = ProtectedPolicy(
        ScriptedPolicy({"leer_archivo": PermissionDecision.ALLOW}), Exploding(protected_dir), ()
    )
    assert boom.evaluate(call("leer_archivo", path="x")) is PermissionDecision.DENY

    inner_fails = ScriptedPolicy({"leer_archivo": RuntimeError(SENTINEL)})
    policy = ProtectedPolicy(inner_fails, DummyAuthorizedArea(protected_dir), ())
    assert policy.evaluate(call("leer_archivo", path="x")) is PermissionDecision.DENY


def test_an_area_that_does_not_answer_with_a_bool_is_a_denial(
    protected_dir: Path,
) -> None:
    class Vague(DummyAuthorizedArea):
        def contains(self, path: Path | str) -> bool:
            return 1  # type: ignore[return-value]

    policy = ProtectedPolicy(
        ScriptedPolicy({"leer_archivo": PermissionDecision.ASK}), Vague(protected_dir), ()
    )
    assert policy.evaluate(call("leer_archivo", path="x")) is PermissionDecision.DENY


def test_constructor_validates_its_arguments(protected_dir: Path) -> None:
    inner = ScriptedPolicy()
    area = DummyAuthorizedArea(protected_dir)
    with pytest.raises(TypeError):
        ProtectedPolicy("no", area, ())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ProtectedPolicy(inner, "no", ())  # type: ignore[arg-type]
    for markers in [("",), ("  ",), (1,), "texto"]:
        with pytest.raises((TypeError, ValueError)) as caught:
            ProtectedPolicy(inner, area, markers)  # type: ignore[arg-type]
        assert SENTINEL not in str(caught.value)


def test_markers_are_compared_without_case_or_separator_style(protected_dir: Path) -> None:
    policy, _ = make(protected_dir, markers=(".Harness\\Tareas",))

    assert policy.evaluate(call("shell", command="dir .harness/TAREAS")) is PermissionDecision.DENY
