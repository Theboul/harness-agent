"""Integration (proposed HU-00-08.1): ``main`` starts a ticket from the command line.

The whole path from ``main(argv=["--tarea", …])``: task file, ``.env`` key, criteria verified by the
real shell chain, review of the diff with simulated input and the commit through a ``ChangeSource``
double (real git has its own test). The provider is a ``FakeProvider``; no network or console.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

from harness_agent.adapters.storage import SqliteSessionStore
from harness_agent.bootstrap import main
from harness_agent.core import ChangeSet, ChangeStatus, FileChange, ProviderResponse
from tests.doubles import FakeProvider
from tests.unit.test_bootstrap_main import write_toml

SENTINEL = "VALOR-DE-PRUEBA-123"
TASK_TEXT = (
    "# TAREA-41\n"
    "## Objetivo\nValidar la clave\n"
    "## Criterios de aceptación\n"
    "- La clave mide 8\n"
    "  - comando: python --version\n"
    "  - espera: codigo_salida == 0\n"
    "## Comandos\n"
    "- pruebas: python --version\n"
)


class Source:
    def __init__(self) -> None:
        self.commits: list[str] = []

    async def snapshot(self) -> ChangeSet:
        return ChangeSet((FileChange("auth.py", ChangeStatus.NEW, 5, 0),), "+def validar(): ...\n")

    async def commit(self, message: str) -> str:
        self.commits.append(message)
        return "abc1234"


def test_a_ticket_session_runs_from_the_command_to_the_approved_commit(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(f"OPENAI_API_KEY={SENTINEL}\n", encoding="utf-8")
    task = tmp_path / "tarea.md"
    task.write_text(TASK_TEXT, encoding="utf-8", newline="")
    provider = FakeProvider([ProviderResponse(content="hecho")])
    source = Source()
    output, error = io.StringIO(), io.StringIO()

    code = main(
        argv=["--tarea", str(task)],
        environ={k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"},
        config_path=write_toml(tmp_path, workspace=tmp_path),
        input_stream=io.StringIO("haz la tarea\n1\n/salir\n"),
        output=output,
        error=error,
        provider_factory=lambda _config: provider,
        changes=source,
    )

    shown = output.getvalue()
    assert code == 0 and error.getvalue() == ""
    assert "La clave mide 8" in shown  # the criterion was verified and shown
    assert "REVISIÓN DE CAMBIOS: TAREA-41" in shown and "+def validar" in shown
    assert source.commits == ["TAREA-41: Validar la clave"]
    assert SENTINEL not in shown
    with SqliteSessionStore(tmp_path / "datos" / "sesiones.db") as store:
        assert len(store.list_sessions()) == 1
