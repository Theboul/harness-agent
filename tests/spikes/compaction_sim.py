"""Test-only support of the SPK-03 spike (compaction without losing the goal).

Nothing here is production code and none of it may move into ``src/``: it models, with plain
stdlib code and the public core API, a long session, two ways of assembling the context, two
summarizers and a survival check. The real pieces belong to HU-02-01, HU-02-03 and HU-02-06.1.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from harness_agent.core import Message, Provider, Role, ToolCall, ToolResult

# --- Scenario ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Seed:
    """A fact planted in the session. The sentinel is a unique string used to find it later."""

    key: str
    sentinel: str
    text: str


ESSENTIAL_KEYS = ("objetivo", "instrucciones", "reglas", "ticket", "criterios")
DECISION_KEYS = ("decision_1", "decision_2", "decision_3")

SEEDS: tuple[Seed, ...] = (
    Seed(
        "objetivo",
        "OBJ-7F3A",
        "Objetivo: migrar el módulo de pagos a la API v2 sin cambiar su firma pública (OBJ-7F3A).",
    ),
    Seed(
        "instrucciones",
        "INS-2B91",
        "Instrucciones: responde en español y nunca ejecutes comandos destructivos (INS-2B91).",
    ),
    Seed(
        "reglas",
        "REG-5C40",
        "Reglas de la tarea: cada cambio lleva su prueba antes del código (REG-5C40).",
    ),
    Seed("ticket", "TCK-4821", "Ticket: TCK-4821."),
    Seed(
        "criterios",
        "CRI-9D12",
        "Criterio protegido: todas las pruebas de pagos pasan en Linux y Windows (CRI-9D12).",
    ),
    Seed(
        "decision_1",
        "DEC-11A1",
        "DECISIÓN DEC-11A1: se mantiene el cliente HTTP actual y solo se cambia la ruta.",
    ),
    Seed(
        "decision_2",
        "DEC-22B2",
        "DECISIÓN DEC-22B2: los reintentos son exponenciales con tope de tres intentos.",
    ),
    Seed(
        "decision_3",
        "DEC-33C3",
        "DECISIÓN DEC-33C3: el modo antiguo se conserva detrás de una bandera hasta el cierre.",
    ),
)

_DECISION_TURNS = {5: "decision_1", 12: "decision_2", 18: "decision_3"}
_TURNS = 20


def sentinel_of(key: str) -> str:
    """Return the sentinel planted for ``key``."""
    for seed in SEEDS:
        if seed.key == key:
            return seed.sentinel
    raise KeyError(key)


def text_of(key: str) -> str:
    """Return the planted text for ``key``."""
    for seed in SEEDS:
        if seed.key == key:
            return seed.text
    raise KeyError(key)


def _tool_output(turn: int) -> str:
    return "\n".join(
        f"salida {turn:02d} línea {line:03d}: comprobación del módulo sin novedades"
        for line in range(1, 17)
    )


def build_long_session(turns: int = _TURNS) -> tuple[Message, ...]:
    """Build the deterministic long session: the first message plants the essential facts.

    Each turn is four messages (user, assistant with a tool call, tool result, assistant text).
    Three turns carry a decision. The filler never repeats a sentinel.
    """
    opening = " ".join(text_of(key) for key in ESSENTIAL_KEYS)
    messages: list[Message] = [Message(Role.USER, opening)]
    for turn in range(1, turns + 1):
        call = ToolCall(id=f"call-{turn:03d}", name="leer_archivo", arguments={"path": f"p{turn}"})
        reply = f"Turno {turn}: revisé el archivo y todo sigue en orden."
        decision_key = _DECISION_TURNS.get(turn)
        if decision_key is not None:
            reply = f"{reply} {text_of(decision_key)}"
        messages += [
            Message(Role.USER, f"Turno {turn}: revisa el archivo p{turn} y dime qué ves."),
            Message(Role.ASSISTANT, "", tool_calls=(call,)),
            Message(Role.TOOL, tool_result=ToolResult(call.id, _tool_output(turn))),
            Message(Role.ASSISTANT, reply),
        ]
    return tuple(messages)


def estimate_tokens(messages: Sequence[Message]) -> int:
    """Rough size in tokens (``ceil(chars / 4)``). Local to the spike: this is not HU-02-01."""
    chars = 0
    for message in messages:
        chars += len(message.content)
        if message.tool_result is not None:
            chars += len(message.tool_result.content)
        for call in message.tool_calls:
            chars += len(call.name) + len(str(call.arguments))
    return math.ceil(chars / 4)


# --- Assembly: two designs --------------------------------------------------------------------

SYSTEM_PROMPT = "Eres un agente de programación. Usa las herramientas cuando haga falta."
SUMMARY_HEADER = "Resumen de la conversación anterior:"
BLOCK_HEADER = "[contexto esencial]"


class CriteriaUnavailable(Exception):
    """The protected criteria source has nothing for the reference (fail closed)."""


class CriteriaSource(Protocol):
    """Read-only access to the protected criteria (HU-11-01)."""

    def read(self, ref: str) -> str: ...


class InMemoryCriteria:
    """Read-only stand-in for the protected criteria source (HU-11-01)."""

    def __init__(self, criteria: dict[str, str]) -> None:
        self._criteria = dict(criteria)

    def read(self, ref: str) -> str:
        try:
            return self._criteria[ref]
        except KeyError:
            raise CriteriaUnavailable("No hay criterios para la referencia dada.") from None


@dataclass(frozen=True)
class EssentialBlock:
    """The five keys of HU-02-06.1. Criteria are a reference, never a copy."""

    goal: str
    instructions: str
    rules: str
    ticket_id: str
    criteria_ref: str

    def render(self, criteria: CriteriaSource) -> Message:
        """Render the pinned system message; the criteria text is read from its source."""
        lines = [
            BLOCK_HEADER,
            self.goal,
            self.instructions,
            self.rules,
            f"Ticket: {self.ticket_id}",
            f"Criterios ({self.criteria_ref}): {criteria.read(self.criteria_ref)}",
        ]
        return Message(Role.SYSTEM, "\n".join(lines))


def block_from_seeds() -> EssentialBlock:
    """The block a ticket session would store, built from the planted seeds."""
    return EssentialBlock(
        goal=text_of("objetivo"),
        instructions=text_of("instrucciones"),
        rules=text_of("reglas"),
        ticket_id=sentinel_of("ticket"),
        criteria_ref=f"criteria:{sentinel_of('ticket')}",
    )


@dataclass(frozen=True)
class CompactionState:
    """One row of ``resumenes``: the summary and how many history events it covers."""

    summary: str = ""
    covered_until: int = 0


def _summary_messages(state: CompactionState) -> list[Message]:
    if not state.summary:
        return []
    return [Message(Role.SYSTEM, f"{SUMMARY_HEADER}\n{state.summary}")]


def assemble_summary_only(history: Sequence[Message], state: CompactionState) -> list[Message]:
    """Design A: everything the user said lives in the history, so it can be summarized."""
    return [
        Message(Role.SYSTEM, SYSTEM_PROMPT),
        *_summary_messages(state),
        *history[state.covered_until :],
    ]


def assemble_pinned_block(
    history: Sequence[Message],
    state: CompactionState,
    block: EssentialBlock,
    criteria: CriteriaSource,
) -> list[Message]:
    """Design B: the pinned block sits in the stable prefix, outside what gets summarized."""
    return [
        Message(Role.SYSTEM, SYSTEM_PROMPT),
        block.render(criteria),
        *_summary_messages(state),
        *history[state.covered_until :],
    ]


def safe_cut(history: Sequence[Message], desired: int) -> int:
    """Largest cut <= ``desired`` that keeps a tool call and its results on the same side."""
    cut = min(max(desired, 0), len(history))
    while 0 < cut < len(history) and history[cut].role is Role.TOOL:
        cut -= 1
    return cut


# --- Summarizers and compaction ---------------------------------------------------------------

SUMMARY_PROMPT = (
    "Resume la conversación para que otro agente pueda continuar. Conserva las decisiones "
    "tomadas y su motivo, el estado del trabajo y lo pendiente. No repitas el contexto "
    "esencial ni los criterios: viven aparte y se inyectan en cada llamada."
)


class Summarizer(Protocol):
    """Turns the not-yet-summarized events plus the previous summary into a new summary."""

    async def summarize(self, old: Sequence[Message], previous: str) -> str: ...


def render_transcript(messages: Sequence[Message]) -> str:
    """Plain-text transcript of messages, one line per message."""
    lines: list[str] = []
    for message in messages:
        if message.tool_calls:
            names = ", ".join(call.name for call in message.tool_calls)
            lines.append(f"{message.role.value}: [llama a {names}]")
        elif message.tool_result is not None:
            lines.append(f"{message.role.value}: {message.tool_result.content}")
        else:
            lines.append(f"{message.role.value}: {message.content}")
    return "\n".join(lines)


class LossySummarizer:
    """Deterministic stress model of a recursive summary with a fixed size budget.

    Each message becomes one line (a tool output keeps only its first line, as real summaries
    do). Newest lines are kept first; the previous summary, being the oldest content, gets the
    room that is left and keeps its tail. It is NOT a prediction of a real model: it models the
    pattern in which the oldest facts are the first ones squeezed out, pass after pass.
    """

    def __init__(self, budget_chars: int = 3_000) -> None:
        self._budget = budget_chars

    @staticmethod
    def _lines(old: Sequence[Message]) -> list[str]:
        lines: list[str] = []
        for message in old:
            if message.tool_result is not None:
                first, *rest = message.tool_result.content.splitlines() or [""]
                lines.append(f"tool: {first} [+{len(rest)} líneas]")
            else:
                lines.append(render_transcript([message]))
        return lines

    async def summarize(self, old: Sequence[Message], previous: str) -> str:
        kept: list[str] = []
        used = 0
        for line in reversed(self._lines(old)):
            if used + len(line) + 1 > self._budget:
                break
            kept.append(line)
            used += len(line) + 1
        kept.reverse()
        room = max(self._budget - used - 1, 0)
        head = previous[-room:] if room else ""
        return "\n".join(part for part in (head, *kept) if part)


class ProviderSummarizer:
    """Summarizes with a separate ``Provider.complete`` call (no tools, no essential block)."""

    def __init__(self, provider: Provider, prompt: str = SUMMARY_PROMPT) -> None:
        self._provider = provider
        self._prompt = prompt

    async def summarize(self, old: Sequence[Message], previous: str) -> str:
        body = render_transcript(old)
        if previous:
            body = f"Resumen anterior:\n{previous}\n\nConversación nueva:\n{body}"
        request = [Message(Role.SYSTEM, self._prompt), Message(Role.USER, body)]
        response = await self._provider.complete(request)
        return response.content


async def compact(
    history: Sequence[Message],
    state: CompactionState,
    summarizer: Summarizer,
    *,
    keep_recent: int,
) -> CompactionState:
    """Summarize what is old and not yet covered; the history itself is never modified."""
    cut = safe_cut(history, len(history) - keep_recent)
    if cut <= state.covered_until:
        return state
    summary = await summarizer.summarize(history[state.covered_until : cut], state.summary)
    return CompactionState(summary=summary, covered_until=cut)


# --- Evaluation -------------------------------------------------------------------------------


def locate(context: Sequence[Message], sentinel: str) -> str:
    """Where a sentinel is found: ``bloque``, ``resumen``, ``reciente`` or ``ausente``."""
    for message in context:
        if sentinel in message.content or (
            message.tool_result is not None and sentinel in message.tool_result.content
        ):
            if message.content.startswith(BLOCK_HEADER):
                return "bloque"
            if message.content.startswith(SUMMARY_HEADER):
                return "resumen"
            if message.role is not Role.SYSTEM:
                return "reciente"
    return "ausente"


def survival(context: Sequence[Message], keys: Sequence[str]) -> dict[str, bool]:
    """Which planted facts are still present anywhere in the assembled context."""
    return {key: locate(context, sentinel_of(key)) != "ausente" for key in keys}
