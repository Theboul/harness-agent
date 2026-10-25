"""Parser of the task format: Markdown text in, validated ``TaskDefinition`` out (HU-11-01).

Pure function over text: the same format serves a task file and the body of a GitHub issue. The
format is in ``specs/021-task-protected-criteria/contracts/task_format.md``. It fails closed:
anything that does not fit the format is rejected with a ``TaskFormatError`` that says what is
missing and never repeats the received text.
"""

from __future__ import annotations

import re

from harness_agent.core.tasks.definition import (
    MAX_CRITERIA,
    MAX_FIELD_CHARS,
    MAX_SECTION_CHARS,
    MAX_TASK_CHARS,
    CriterionDefinition,
    TaskDefinition,
)
from harness_agent.core.tasks.errors import TaskFormatError

_SECTION_BY_NAME = {
    "objetivo": "objetivo",
    "contexto": "contexto",
    "reglas": "reglas",
    "criterios de aceptación": "criterios",
    "criterios": "criterios",
}
_KEY_LINE = re.compile(r"^(?:[-*]\s+)?(comando|espera)\s*:\s*(.*)$", re.IGNORECASE)
_SPACES = re.compile(r"\s+")
_ALLOWED_CONTROLS = frozenset("\n\r\t")


def _has_control_characters(text: str) -> bool:
    return any((ord(ch) < 32 or ord(ch) == 127) and ch not in _ALLOWED_CONTROLS for ch in text)


def _bounded(text: str, limit: int) -> str:
    if len(text) > limit:
        raise TaskFormatError("texto_demasiado_largo")
    return text


class _CriteriaReader:
    """Collects the criteria of the criteria section, line by line."""

    def __init__(self) -> None:
        self.criteria: list[CriterionDefinition] = []
        self._description: str | None = None
        self._keys: dict[str, str] = {}

    def line(self, raw: str) -> None:
        if not raw.strip():
            return
        if raw[0] in "-*" and raw[1:2] == " ":
            self._close()
            description = raw[2:].strip()
            if not description:
                raise TaskFormatError("formato_no_valido")
            self._description = _bounded(description, MAX_FIELD_CHARS)
            return
        if raw[0] not in " \t" or self._description is None:
            raise TaskFormatError("formato_no_valido")
        match = _KEY_LINE.match(raw.strip())
        if match is None:
            raise TaskFormatError("formato_no_valido")
        key, value = match.group(1).lower(), match.group(2).strip()
        if not value or key in self._keys:
            raise TaskFormatError("criterio_incompleto")
        self._keys[key] = _bounded(value, MAX_FIELD_CHARS)

    def finish(self) -> list[CriterionDefinition]:
        self._close()
        return self.criteria

    def _close(self) -> None:
        if self._description is None:
            return
        command, expectation = self._keys.get("comando"), self._keys.get("espera")
        if (command is None) != (expectation is None):
            raise TaskFormatError("criterio_incompleto")
        if len(self.criteria) >= MAX_CRITERIA:
            raise TaskFormatError("demasiados_criterios")
        self.criteria.append(CriterionDefinition(self._description, command, expectation))
        self._description = None
        self._keys = {}


def parse_task(text: str) -> TaskDefinition:
    """Validate ``text`` and return the task it describes.

    Raises:
        TaskFormatError: The text is empty, too large, malformed or lacks an objective or
            acceptance criteria (the message says which).
    """
    if not isinstance(text, str) or not text.strip():
        raise TaskFormatError("vacia")
    if len(text) > MAX_TASK_CHARS:
        raise TaskFormatError("demasiado_grande")
    if _has_control_characters(text):
        raise TaskFormatError("contenido_no_valido")

    title: str | None = None
    seen_heading = False
    section: str | None = None
    seen: set[str] = set()
    texts: dict[str, list[str]] = {"objetivo": [], "contexto": [], "reglas": []}
    reader = _CriteriaReader()
    for raw in text.splitlines():
        if raw.startswith("## "):
            name = _SECTION_BY_NAME.get(_SPACES.sub(" ", raw[3:].strip()).casefold())
            if name is None:
                raise TaskFormatError("seccion_desconocida")
            if name in seen:
                raise TaskFormatError("seccion_repetida")
            seen.add(name)
            section = name
            seen_heading = True
        elif raw.startswith("# "):
            if seen_heading:
                raise TaskFormatError("formato_no_valido")
            heading = raw[2:].strip()
            if not heading:
                raise TaskFormatError("formato_no_valido")
            title = _bounded(heading, MAX_FIELD_CHARS)
            seen_heading = True
        elif section is None:
            if raw.strip():
                raise TaskFormatError("formato_no_valido")
        elif section == "criterios":
            reader.line(raw)
        else:
            texts[section].append(raw)

    objective = _bounded("\n".join(texts["objetivo"]).strip(), MAX_SECTION_CHARS)
    if not objective:
        raise TaskFormatError("sin_objetivo")
    criteria = reader.finish()
    if not criteria:
        raise TaskFormatError("sin_criterios")
    return TaskDefinition(
        title=title,
        objective=objective,
        context=_bounded("\n".join(texts["contexto"]).strip(), MAX_SECTION_CHARS),
        rules=_bounded("\n".join(texts["reglas"]).strip(), MAX_SECTION_CHARS),
        criteria=tuple(criteria),
    )
