"""DelegateTool: hands a subtask to a subagent (HU-09-01, ``delegar``).

The subagent works in a child session with an empty context: it knows only the goal, the minimum
context and the output format that the orchestrator passes. What comes back is the brief structured
result (``resultado``, ``hallazgos_clave``, ``fuentes``, ``error``, ``parcial``), never the
conversation of the subagent. The tool does no work itself: it receives by constructor the
``SubagentRunner`` of the core, and the composition root connects it.

It fails closed: a goal that is not usable, a runner that fails or answers something that is not a
result is a tagged error that never copies what the runner said. A cancellation goes up.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from harness_agent.adapters.tools._paths import error_result
from harness_agent.core import (
    DELEGATE_TOOL_NAME,
    RESULT_SCHEMA,
    Message,
    RiskLevel,
    Role,
    SubagentResult,
    SubagentRunner,
    Tool,
    ToolResult,
)

PROFILE = "general"
MAX_GOAL_CHARS = 4_000
MAX_CONTEXT_CHARS = 8_000
MAX_FORMAT_CHARS = 1_000

_FAILED = (
    "No se pudo completar la delegación. Haz la tarea tú mismo o vuelve a intentarlo con otro "
    "objetivo."
)


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


class DelegateTool(Tool):
    """Delegate a subtask to a subagent in a child session; returns its brief result."""

    def __init__(self, runner: SubagentRunner) -> None:
        self._runner = runner

    @property
    def name(self) -> str:
        return DELEGATE_TOOL_NAME

    @property
    def description(self) -> str:
        return (
            "Delega una subtarea en un subagente que trabaja en una sesión aparte con el contexto "
            "vacío: solo conoce lo que le pases en el objetivo, el contexto mínimo y el formato "
            "de salida. Devuelve un resultado breve (resultado, hallazgos_clave, fuentes, error y "
            "parcial), no la conversación del subagente. Úsala para tareas pesadas que "
            "llenarían tu contexto. Un subagente no puede delegar."
        )

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "objetivo": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_GOAL_CHARS,
                    "description": "Lo que el subagente debe lograr.",
                },
                "contexto_minimo": {
                    "type": "string",
                    "maxLength": MAX_CONTEXT_CHARS,
                    "description": "Solo los datos que necesita; no conoce tu conversación.",
                },
                "formato_salida": {
                    "type": "string",
                    "maxLength": MAX_FORMAT_CHARS,
                    "description": "Cómo quieres el resultado (por ejemplo, tres viñetas).",
                },
            },
            "required": ["objetivo"],
            "additionalProperties": False,
        }

    @property
    def risk(self) -> RiskLevel:
        # Low: the tool itself changes nothing (what the subagent does goes through the chain).
        # A medium risk without a ``path`` would be denied by the default policy.
        return RiskLevel.LOW

    async def run(self, args: dict[str, Any]) -> ToolResult:
        goal = _text(args.get("objetivo"))
        if not goal:
            return error_result("objetivo_invalido", "El objetivo de la delegación está vacío.")
        output_format = _text(args.get("formato_salida"))
        if output_format:
            goal = f"{goal}\n\nFormato de salida solicitado: {output_format}"
        shared = _text(args.get("contexto_minimo"))
        context = [Message(Role.USER, shared)] if shared else []
        try:
            result = await self._runner.execute(
                PROFILE, goal, context, copy.deepcopy(RESULT_SCHEMA)
            )
            if not isinstance(result, SubagentResult):
                return error_result("subagente_fallo", _FAILED)
            content = json.dumps(result.output, ensure_ascii=False)
        except Exception:
            return error_result("subagente_fallo", _FAILED)
        return ToolResult(call_id="", content=content, is_error=result.is_error)
