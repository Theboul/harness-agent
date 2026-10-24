"""Sp1-45: a task of three steps with a REAL model (HU-07-02 / AC-01). Manual; outside the CI.

This test spends the quota of a real provider, so it never runs by itself: it is skipped unless
``HARNESS_REAL_MODEL`` (``<provider>/<model>``) is defined **and**, if the provider needs one, the
environment variable of its key (``PROVIDER_KEY_VARIABLES``). The key is read only from the
environment, travels in a ``Secret`` and is never printed. The CI has neither variable, so the
test shows up as skipped there. How to run it: ``quickstart.md``, section 7.

The task: list the files of a temporary folder, read ``pista.txt`` and answer with the code it
holds. The real loop, the real file tools and the adapter are used; the model is the real one.
At most ``MAX_CALLS`` calls to the model are allowed, so a model that goes in circles cannot spend
more than that. The result (provider, model, tokens, whether the cap of output tokens was
accepted) is for the person to write in ``docs/PROGRESO.md``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Avoids the download of the price table of LiteLLM; the real call is still made.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

from harness_agent.adapters.providers.litellm_provider import LiteLLMProvider  # noqa: E402
from harness_agent.adapters.system import WorkspaceArea  # noqa: E402
from harness_agent.adapters.tools.list_files import ListFilesTool  # noqa: E402
from harness_agent.adapters.tools.read_file import ReadFileTool  # noqa: E402
from harness_agent.config import PROVIDER_KEY_VARIABLES, Secret  # noqa: E402
from harness_agent.core import (  # noqa: E402
    DefaultPermissionPolicy,
    InMemoryToolRegistry,
    Message,
    PermissionRules,
    Provider,
    ProviderError,
    ProviderResponse,
    Role,
    ToolDefinition,
)
from harness_agent.core.loop import AgentLoop, TurnStatus  # noqa: E402
from tests.doubles import RecordingEventBus, run_bounded  # noqa: E402

REAL_MODEL = os.environ.get("HARNESS_REAL_MODEL", "")
PROVIDER = REAL_MODEL.partition("/")[0]
KEY_VARIABLE = PROVIDER_KEY_VARIABLES.get(PROVIDER)
KEY = os.environ.get(KEY_VARIABLE, "") if KEY_VARIABLE else ""
MAX_OUTPUT_TOKENS = int(os.environ.get("HARNESS_REAL_MAX_OUTPUT_TOKENS", "4096"))
MAX_CALLS = 8
TIMEOUT_SECONDS = 180.0
CODE = "CODIGO-AZUL-42"
TASK = (
    "Tarea de tres pasos con las herramientas: 1) lista los archivos de la carpeta '.', "
    "2) lee el archivo 'pista.txt', 3) responde con el código que contiene, tal cual."
)


def skip_reason() -> str | None:
    if not REAL_MODEL:
        return "HARNESS_REAL_MODEL no está definida: prueba manual Sp1-45, fuera de la CI"
    if PROVIDER not in PROVIDER_KEY_VARIABLES:
        return "HARNESS_REAL_MODEL no tiene la forma <proveedor>/<modelo> de un proveedor admitido"
    if KEY_VARIABLE and not KEY.strip():
        return f"falta la variable de entorno {KEY_VARIABLE} con la clave del proveedor"
    return None


pytestmark = pytest.mark.skipif(skip_reason() is not None, reason=skip_reason() or "")


class CappedProvider(Provider):
    """Lets at most ``limit`` calls through: a loop that never ends cannot spend more."""

    def __init__(self, inner: Provider, limit: int) -> None:
        self._inner = inner
        self._limit = limit
        self.calls = 0

    async def complete(
        self, messages: list[Message], tools: list[ToolDefinition] | None = None
    ) -> ProviderResponse:
        if self.calls >= self._limit:
            raise ProviderError("Se alcanzó el máximo de llamadas permitidas en la prueba manual.")
        self.calls += 1
        return await self._inner.complete(messages, tools)


async def test_a_real_model_does_a_task_of_three_steps(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pytest.importorskip("litellm")
    root = tmp_path / "area"
    root.mkdir()
    (root / "pista.txt").write_text(f"El código es {CODE}\n", "utf-8", newline="")
    (root / "otro.txt").write_text("nada interesante\n", "utf-8", newline="")
    (root / "notas.txt").write_text("tampoco aquí\n", "utf-8", newline="")
    area = WorkspaceArea(root)
    registry = InMemoryToolRegistry()
    registry.register(ListFilesTool(area))
    registry.register(ReadFileTool(area))
    policy = DefaultPermissionPolicy(registry, area, PermissionRules())
    adapter = LiteLLMProvider(
        REAL_MODEL,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        api_key=Secret(KEY) if KEY_VARIABLE else None,
    )
    provider = CappedProvider(adapter, MAX_CALLS)
    bus = RecordingEventBus()
    loop = AgentLoop(provider, registry, policy, bus)

    result = await run_bounded(
        loop.run_turn(session_id="sp1-45", task=TASK, history=[]), timeout=TIMEOUT_SECONDS
    )

    tool_results = [m for m in result.history if m.role is Role.TOOL]
    usage = [m.usage for m in result.history if m.usage is not None]
    input_tokens = sum(u.input_tokens for u in usage)
    output_tokens = sum(u.output_tokens for u in usage)
    with capsys.disabled():
        print(
            f"\n[Sp1-45] modelo={REAL_MODEL} llamadas={provider.calls} "
            f"herramientas={len(tool_results)} tokens_entrada={input_tokens} "
            f"tokens_salida={output_tokens} max_output_tokens={MAX_OUTPUT_TOKENS} "
            f"estado={result.status.value} contiene_el_codigo="
            f"{CODE in (result.final_response or '')}"
        )
        print(f"[Sp1-45] respuesta final: {(result.final_response or '')[:300]!r}")

    assert result.status is TurnStatus.COMPLETED, result.error
    assert result.final_response
    assert tool_results, "el modelo no pidió ninguna herramienta"
    assert all(m.tool_result is not None and not m.tool_result.is_error for m in tool_results)
