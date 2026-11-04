"""The task a subagent receives (HU-09-01): its whole conversation is this one message.

The subagent starts with an empty context. What it knows is what the orchestrator hands over: the
goal, the minimum context and how to answer. The context messages are accepted only if the person's
role wrote them and they are not external data; anything else (history of the orchestrator, results
of tools, system text) is dropped, so a caller cannot leak the conversation by mistake.
"""

from __future__ import annotations

import json
from typing import Any

from harness_agent.core.entities import Message, Role

MAX_GOAL_CHARS = 6_000
MAX_CONTEXT_CHARS = 12_000
_ELLIPSIS = "…"

_INTRO = (
    "Eres un subagente. Tu conversación empieza aquí: solo conoces lo que sigue y no puedes "
    "delegar en otros subagentes."
)
_ANSWER = (
    "Cuando termines, responde SOLO con un objeto JSON, sin texto antes ni después, que cumpla "
    "este esquema:"
)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + _ELLIPSIS


def build_task(goal: str, context: list[Message], output_schema: dict[str, Any]) -> str:
    """The text of the single message that opens the conversation of a subagent.

    Args:
        goal: What the subagent must achieve (and, if given, how to present it).
        context: Messages the orchestrator chose to share; only unexternal ``USER`` ones count.
        output_schema: The JSON Schema the final answer must comply with.
    """
    parts = [_INTRO, "## Objetivo", _clip(goal.strip(), MAX_GOAL_CHARS)]
    shared = [
        message.content.strip()
        for message in context
        if message.role is Role.USER and not message.is_external and message.content.strip()
    ]
    if shared:
        parts += ["## Contexto", _clip("\n\n".join(shared), MAX_CONTEXT_CHARS)]
    parts += ["## Cómo responder", _ANSWER, json.dumps(output_schema, ensure_ascii=False)]
    return "\n\n".join(parts)
