"""SearchTextTool: literal text search inside the area (HU-01-03, ``buscar_texto``)."""

from __future__ import annotations

import os
import unicodedata
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from harness_agent.adapters.tools._limits import (
    MAX_LINE_CHARS,
    MAX_MATCHES,
    MAX_QUERY_CHARS,
    MAX_READ_BYTES,
)
from harness_agent.adapters.tools._paths import (
    bounded_path,
    bounded_text,
    error_result,
    resolve_in_area,
)
from harness_agent.core import AuthorizedArea, RiskLevel, Tool, ToolResult

_UNSEARCHABLE_REASONS = {
    "demasiado_grande": f"supera el máximo de {MAX_READ_BYTES} bytes",
    "no_es_texto": "no es texto UTF-8",
    "error_de_archivo": "no se pudo leer (permisos o error del sistema)",
}


def _entries(directory: str) -> list[os.DirEntry[str]]:
    """The entries of a folder in a stable order; a folder that cannot be read has none."""
    try:
        with os.scandir(directory) as scanner:
            return sorted(scanner, key=lambda e: (e.name.casefold(), e.name))
    except OSError:
        return []


def _files_under(directory: str) -> Iterator[str]:
    """Every file below ``directory`` in a stable order, without following folder links."""
    stack = [iter(_entries(directory))]
    while stack:
        entry = next(stack[-1], None)
        if entry is None:
            stack.pop()
            continue
        try:
            if entry.is_symlink() and entry.is_dir():
                continue
            if entry.is_dir(follow_symlinks=False):
                stack.append(iter(_entries(entry.path)))
            elif entry.is_file():
                yield entry.path
        except OSError:
            continue


def _load_text(path: Path | str) -> tuple[str | None, str | None]:
    """The UTF-8 text of a file, or ``(None, category)`` when it cannot be searched."""
    try:
        with Path(path).open("rb") as handle:
            data = handle.read(MAX_READ_BYTES + 1)
    except Exception:
        return None, "error_de_archivo"
    if len(data) > MAX_READ_BYTES:
        return None, "demasiado_grande"
    if b"\x00" in data:
        return None, "no_es_texto"
    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, "no_es_texto"


def _shown_line(line: str) -> str:
    """A matching line that is safe to show: no control characters and bounded."""
    clean = "".join(" " if unicodedata.category(char) == "Cc" else char for char in line)
    if len(clean) <= MAX_LINE_CHARS:
        return clean
    return clean[: MAX_LINE_CHARS - 3] + "..."


class SearchTextTool(Tool):
    """Find a literal, case-sensitive text in a file or, recursively, in a folder."""

    def __init__(self, area: AuthorizedArea | None) -> None:
        self._area = area

    @property
    def name(self) -> str:
        return "buscar_texto"

    @property
    def description(self) -> str:
        return (
            "Busca un texto literal (sensible a mayúsculas) en un archivo o, de forma "
            "recursiva, en una carpeta del área de trabajo. Devuelve archivo, línea y texto "
            "de cada coincidencia. Usa 'path' para el lugar y 'query' para el texto."
        )

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Archivo o carpeta donde buscar.",
                },
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": MAX_QUERY_CHARS,
                    "description": "Texto literal a buscar.",
                },
            },
            "required": ["path", "query"],
            "additionalProperties": False,
        }

    @property
    def risk(self) -> RiskLevel:
        return RiskLevel.LOW

    async def run(self, args: dict[str, Any]) -> ToolResult:
        raw = args.get("path")
        query = args.get("query")
        if not isinstance(query, str) or not 1 <= len(query) <= MAX_QUERY_CHARS:
            return error_result(
                "consulta_invalida",
                f"La consulta debe ser un texto de 1 a {MAX_QUERY_CHARS} caracteres.",
            )
        resolved = resolve_in_area(self._area, raw)
        if isinstance(resolved, ToolResult):
            return resolved
        assert self._area is not None  # resolve_in_area rejects a missing area
        shown = bounded_path(raw)
        try:
            if not resolved.exists():
                return error_result(
                    "no_existe",
                    f"La ruta '{shown}' no existe. Usa 'listar_archivos' para ver los archivos.",
                )
            if resolved.is_file():
                return self._search_file(resolved, query, shown)
            lines, more = self._search_folder(resolved, query)
        except Exception:
            return error_result(
                "error_de_archivo",
                f"No se pudo buscar en '{shown}' (permisos o error del sistema). "
                "Revisa los permisos.",
            )
        return self._answer(lines, more, query, shown)

    def _search_file(self, real: Path, query: str, shown: str) -> ToolResult:
        text, problem = _load_text(real)
        if text is None:
            category = problem or "error_de_archivo"
            reason = _UNSEARCHABLE_REASONS[category]
            return error_result(category, f"No se puede buscar en '{shown}': {reason}.")
        lines, more = self._matches(real, text, query, [])
        return self._answer(lines, more, query, shown)

    def _search_folder(self, directory: Path, query: str) -> tuple[list[str], bool]:
        area = self._area
        assert area is not None
        lines: list[str] = []
        for file_path in _files_under(str(directory)):
            if area.contains(Path(os.path.realpath(file_path))) is not True:
                continue
            text, _ = _load_text(file_path)
            if text is None:
                continue
            lines, more = self._matches(Path(file_path), text, query, lines)
            if more:
                return lines, True
        return lines, False

    def _matches(
        self, file_path: Path, text: str, query: str, lines: list[str]
    ) -> tuple[list[str], bool]:
        """Add the matching lines of one file; ``True`` means the limit was exceeded."""
        assert self._area is not None
        relative = Path(os.path.relpath(file_path, self._area.root)).as_posix()
        for number, line in enumerate(text.split("\n"), start=1):
            if query not in line:
                continue
            if len(lines) >= MAX_MATCHES:
                return lines, True
            lines.append(f"{relative}:{number}: {_shown_line(line.rstrip(chr(13)))}")
        return lines, False

    @staticmethod
    def _answer(lines: list[str], more: bool, query: str, shown: str) -> ToolResult:
        if not lines:
            return ToolResult(
                call_id="",
                content=f"No hay coincidencias para '{bounded_path(query)}' en '{shown}'.",
            )
        if more:
            lines = [
                *lines,
                f"... se alcanzó el máximo de {MAX_MATCHES} coincidencias; afina la consulta.",
            ]
        return ToolResult(call_id="", content=bounded_text("\n".join(lines)))
