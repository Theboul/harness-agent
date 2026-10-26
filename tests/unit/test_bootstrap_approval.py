"""Composition root: the approver reaches the loop and `main` wires the terminal one (HU-05-03)."""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.bootstrap import Composition, main
from harness_agent.core import (
    ApprovalAction,
    PermissionRules,
    Provider,
    ProviderResponse,
    Role,
    ToolCall,
)
from tests.doubles import DummyApprover, FakeProvider
from tests.unit.bootstrap_support import build, make_config, one_turn

CONTENT = "contenido-del-archivo"


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def reading_provider() -> FakeProvider:
    return FakeProvider(
        [
            ProviderResponse(
                tool_calls=[ToolCall(id="c1", name="leer_archivo", arguments={"path": "a.txt"})]
            ),
            ProviderResponse(content="listo"),
        ]
    )


def tool_answer(provider: FakeProvider) -> str:
    return next(m.content for m in provider.received[1] if m.role is Role.TOOL)


class TestCompose:
    async def test_the_approver_reaches_the_loop(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        (tmp_path / "a.txt").write_text(CONTENT, encoding="utf-8")
        provider = reading_provider()
        approver = DummyApprover(ApprovalAction.APPROVE_ONCE)
        config = make_config(
            tmp_path, workspace=tmp_path, permissions=PermissionRules(ask=("leer_archivo",))
        )
        composition = build(opened, config, provider, approver=approver)

        await one_turn(composition)

        assert len(approver.recorded_requests) == 1
        assert CONTENT in tool_answer(provider)

    async def test_a_rejection_does_not_run_the_tool(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        (tmp_path / "a.txt").write_text(CONTENT, encoding="utf-8")
        provider = reading_provider()
        config = make_config(
            tmp_path, workspace=tmp_path, permissions=PermissionRules(ask=("leer_archivo",))
        )
        composition = build(opened, config, provider, approver=DummyApprover(ApprovalAction.REJECT))

        await one_turn(composition)

        assert tool_answer(provider).startswith("[approval_rejected]")

    async def test_without_an_approver_the_action_is_still_denied(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider = reading_provider()
        config = make_config(
            tmp_path, workspace=tmp_path, permissions=PermissionRules(ask=("leer_archivo",))
        )
        composition = build(opened, config, provider)

        await one_turn(composition)

        assert tool_answer(provider).startswith("[approval_required_unavailable]")


def write_toml(tmp_path: Path) -> Path:
    lines = [
        'model = "openai/modelo-de-prueba"',
        "",
        "[paths]",
        f'sessions_db = "{(tmp_path / "datos" / "sesiones.db").as_posix()}"',
        f'workspace_root = "{tmp_path.as_posix()}"',
        "",
        "[permissions]",
        'ask = ["leer_archivo"]',
    ]
    target = tmp_path / "config.toml"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return target


class TestMain:
    def run(self, tmp_path: Path, typed: str, provider: Provider) -> tuple[int, str]:
        (tmp_path / "a.txt").write_text(CONTENT, encoding="utf-8")
        output = io.StringIO()
        code = main(
            environ={"OPENAI_API_KEY": "VALOR-DE-PRUEBA-123"},
            config_path=write_toml(tmp_path),
            input_stream=io.StringIO(typed),
            output=output,
            error=io.StringIO(),
            provider_factory=lambda _config: provider,
        )
        return code, output.getvalue()

    def test_the_terminal_shows_the_detail_and_the_choice_runs_the_tool(
        self, tmp_path: Path
    ) -> None:
        provider = reading_provider()

        code, text = self.run(tmp_path, "lee a.txt\n1\n/salir\n", provider)

        assert code == 0
        assert "El agente quiere ejecutar: leer_archivo" in text
        assert "path: a.txt" in text
        assert CONTENT in tool_answer(provider)

    def test_rejecting_in_the_terminal_does_not_run_the_tool(self, tmp_path: Path) -> None:
        provider = reading_provider()

        code, _text = self.run(tmp_path, "lee a.txt\n3\n/salir\n", provider)

        assert code == 0
        assert tool_answer(provider).startswith("[approval_rejected]")

    def test_the_end_of_the_input_while_asking_rejects(self, tmp_path: Path) -> None:
        provider = reading_provider()

        code, _text = self.run(tmp_path, "lee a.txt\n", provider)

        assert code == 0
        assert tool_answer(provider).startswith("[approval_rejected]")
