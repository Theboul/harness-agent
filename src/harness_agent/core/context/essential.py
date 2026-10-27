"""The essential context of a task: what is stored aside and how it becomes one system message.

A session with a task keeps its ticket, objective, rules, a reference to its protected criteria and
a record of the instructions that were sent, apart from the history. The history can be compacted
(HU-02-03); these elements never are. This module holds the pure rules: the elements, their
cleaning and caps, the text of the block, how the block is recognised and whether it fits.

Nothing here reads a file, the environment or the terminal. Error messages are fixed sentences that
name an element and a cap, never a value. See ``specs/031-essential-context-block/``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from harness_agent.core.context.errors import EssentialContextError, EssentialContextTooLarge
from harness_agent.core.context.estimator import estimate_message
from harness_agent.core.context.settings import ContextSettings, threshold_tokens
from harness_agent.core.context.summary import clean_summary
from harness_agent.core.entities import Message, Role
from harness_agent.core.interfaces.system import TaskCriteriaItem

KEY_OBJECTIVE = "objetivo"
KEY_RULES = "reglas"
KEY_TICKET = "ticket"
KEY_CRITERIA_REF = "criterios_ref"
KEY_INSTRUCTIONS = "instrucciones"
KNOWN_KEYS = frozenset({KEY_OBJECTIVE, KEY_RULES, KEY_TICKET, KEY_CRITERIA_REF, KEY_INSTRUCTIONS})

MARK = "[contexto esencial de la tarea]"
MAX_ELEMENT_CHARS = 8_000
MAX_BLOCK_SHARE_PERCENT = 20

ORIGIN_TICKET = "tarea (título)"
ORIGIN_OBJECTIVE = "tarea (objetivo)"
ORIGIN_RULES = "tarea (reglas)"
ORIGIN_CRITERIA = "criterios protegidos (HU-11-01)"

INTRO = (
    "Contexto fijo de la tarea: lo guarda el harness fuera del historial y se te entrega "
    "completo en cada llamada."
)
_HEADER = f"{MARK}\n{INTRO}"
_NO_DESCRIPTION = "(sin descripción)"
_INVALID_ITEM = "Un elemento del contexto esencial no es válido."
_MISSING_BASICS = "El contexto esencial necesita un objetivo y al menos una instrucción."
_CHARACTERS = "caracteres"
_TOKENS = "tokens"
_NOTHING_TO_SHOW = "El contexto esencial no tiene nada que mostrar."


@dataclass(frozen=True)
class EssentialItem:
    """One element of the essential context: a key, its value and where it came from.

    Attributes:
        key: One of the known keys (objective, rules, ticket, criteria reference, instructions).
        order: Position among the elements of the same key, from 1.
        value: The text (clean, for the elements of the task), the reference or the exact message.
        origin: Where the value came from.
    """

    key: str
    order: int
    value: str
    origin: str

    def __post_init__(self) -> None:
        valid = (
            self.key in KNOWN_KEYS
            and isinstance(self.order, int)
            and not isinstance(self.order, bool)
            and self.order >= 1
            and isinstance(self.value, str)
            and bool(self.value.strip())
            and isinstance(self.origin, str)
            and bool(self.origin.strip())
        )
        if not valid:
            raise EssentialContextError(_INVALID_ITEM)


def _checked(element: str, value: str) -> str:
    """The cleaned ``value`` if it is within the cap; nothing is ever truncated."""
    if len(value) > MAX_ELEMENT_CHARS:
        raise EssentialContextTooLarge(element, MAX_ELEMENT_CHARS, _CHARACTERS)
    return value


def make_items(
    *,
    ticket: str | None,
    objective: str,
    rules: str | None,
    instructions: Sequence[tuple[str, str]],
) -> tuple[EssentialItem, ...]:
    """The elements of a task, cleaned, within their caps and in a fixed order.

    The ticket, the objective and the rules lose hidden characters and have the credentials of URLs
    hidden (``core/redaction.py``); the ticket becomes one line. An absent or blank ticket or rules
    leave no element. ``instructions`` are ``(origin, text)`` pairs, one per system message that was
    sent: they are stored exactly as sent and have no cap.

    Raises:
        EssentialContextTooLarge: A cleaned value is longer than ``MAX_ELEMENT_CHARS``.
        EssentialContextError: There is no objective or no instruction.
    """
    clean_objective = clean_summary(objective)
    if not clean_objective or not instructions:
        raise EssentialContextError(_MISSING_BASICS)
    clean_ticket = " ".join(clean_summary(ticket).split()) if ticket else ""
    clean_rules = clean_summary(rules) if rules else ""
    items: list[EssentialItem] = []
    if clean_ticket:
        items.append(EssentialItem(KEY_TICKET, 1, _checked("ticket", clean_ticket), ORIGIN_TICKET))
    items.append(
        EssentialItem(KEY_OBJECTIVE, 1, _checked("objetivo", clean_objective), ORIGIN_OBJECTIVE)
    )
    if clean_rules:
        items.append(EssentialItem(KEY_RULES, 1, _checked("reglas", clean_rules), ORIGIN_RULES))
    items.extend(
        EssentialItem(KEY_INSTRUCTIONS, position, text, origin)
        for position, (origin, text) in enumerate(instructions, start=1)
    )
    return tuple(items)


def criteria_reference(session_id: str) -> EssentialItem:
    """The element that refers to the protected criteria of the session (never a copy of them)."""
    return EssentialItem(KEY_CRITERIA_REF, 1, session_id, ORIGIN_CRITERIA)


def _first(items: Sequence[EssentialItem], key: str) -> EssentialItem | None:
    found = [item for item in items if item.key == key]
    return min(found, key=lambda item: item.order) if found else None


def _criteria_lines(criteria: Sequence[TaskCriteriaItem]) -> list[str]:
    """One line per criterion: its position, its state and its clean description (never more)."""
    lines: list[str] = []
    for position, criterion in enumerate(criteria, start=1):
        description = " ".join(clean_summary(criterion.description).split()) or _NO_DESCRIPTION
        state = "cumplido" if criterion.passes else "pendiente"
        lines.append(f"{position}. [{state}] {description}")
    return lines


def render_block(items: Sequence[EssentialItem], criteria: Sequence[TaskCriteriaItem]) -> str:
    """The text of the block: ticket, objective, rules and criteria, in that order.

    A pure function of its arguments: the same data give the same text, whatever the order of
    ``items``. An absent element is left out whole, with its heading; the instructions are never
    part of the block (they reach the model as their own system messages).

    Raises:
        EssentialContextError: There is nothing to show (only a header is never sent).
    """
    sections = [_HEADER]
    ticket = _first(items, KEY_TICKET)
    objective = _first(items, KEY_OBJECTIVE)
    rules = _first(items, KEY_RULES)
    if ticket is not None:
        sections.append(f"Ticket: {ticket.value}")
    if objective is not None:
        sections.append(f"Objetivo:\n{objective.value}")
    if rules is not None:
        sections.append(f"Reglas:\n{rules.value}")
    lines = _criteria_lines(criteria)
    if lines:
        sections.append("Criterios de aceptación (estado actual):\n" + "\n".join(lines))
    if len(sections) == 1:
        raise EssentialContextError(_NOTHING_TO_SHOW)
    return "\n\n".join(sections)


def _share_limit(settings: ContextSettings, model: str) -> int:
    return threshold_tokens(settings, model) * MAX_BLOCK_SHARE_PERCENT // 100


def block_fits(text: str, settings: ContextSettings, model: str) -> bool:
    """Whether the block, as a system message, is within its share of the threshold of ``model``."""
    return estimate_message(Message(Role.SYSTEM, text)) <= _share_limit(settings, model)


def check_block(
    items: Sequence[EssentialItem],
    criteria: Sequence[TaskCriteriaItem],
    settings: ContextSettings,
    model: str,
) -> str:
    """The text of the block, once its sizes are checked; nothing is ever truncated.

    Raises:
        EssentialContextTooLarge: The section of the criteria is over ``MAX_ELEMENT_CHARS`` or
            the whole block is over its share of the threshold of ``model``.
    """
    if len("\n".join(_criteria_lines(criteria))) > MAX_ELEMENT_CHARS:
        raise EssentialContextTooLarge("criterios", MAX_ELEMENT_CHARS, _CHARACTERS)
    text = render_block(items, criteria)
    if not block_fits(text, settings, model):
        raise EssentialContextTooLarge("bloque completo", _share_limit(settings, model), _TOKENS)
    return text


def check_creation(
    items: Sequence[EssentialItem],
    criteria_descriptions: Sequence[str],
    settings: ContextSettings,
    model: str,
) -> str:
    """``check_block`` with the criteria of the definition as pending, before anything is opened."""
    pending = [
        TaskCriteriaItem(str(position), description)
        for position, description in enumerate(criteria_descriptions, start=1)
    ]
    return check_block(items, pending, settings, model)


def instruction_messages(items: Sequence[EssentialItem]) -> list[Message]:
    """The system messages that the record of instructions stands for, in order.

    Only to rebuild a prefix: they are never injected into the block.
    """
    recorded = sorted(
        (item for item in items if item.key == KEY_INSTRUCTIONS), key=lambda i: i.order
    )
    return [Message(Role.SYSTEM, item.value) for item in recorded]


def block_message(text: str) -> Message:
    """The message that carries ``text`` (the block) into the context: a system message."""
    return Message(Role.SYSTEM, text)


def find_blocks(history: Sequence[Message]) -> list[int]:
    """Where the block is: only a system message of the leading system prefix can be it.

    A message is the block if it is a ``SYSTEM`` message, inside the contiguous prefix of ``SYSTEM``
    messages at the start of the history, and its text is the mark or starts with the mark and a
    line break. A text that imitates the mark in a ``USER``, ``ASSISTANT`` or ``TOOL`` message
    (a file, a web page, a summary) is never looked at, so it can neither replace the block nor be
    replaced by it.
    """
    found: list[int] = []
    for position, message in enumerate(history):
        if message.role is not Role.SYSTEM:
            break
        if message.content == MARK or message.content.startswith(MARK + "\n"):
            found.append(position)
    return found
