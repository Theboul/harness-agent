"""ListFilesTool: lists the entries of a folder inside the area (HU-01-03, ``listar_archivos``)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harness_agent.adapters.tools._limits import MAX_LIST_ENTRIES
from harness_agent.adapters.tools._paths import (
    bounded_path,
    bounded_text,
    error_result,
    resolve_in_area,
)
from harness_agent.core import AuthorizedArea, RiskLevel, Tool, ToolResult


def _kind(entry: Path) -> str:
    """``enlace`` for a symbolic link (not followed), else ``carpeta`` or ``archivo``."""
    if entry.is_symlink():
        return "enlace"
    return "carpeta" if entry.is_dir() else "archivo"


class ListFilesTool(Tool):
    """List one folder (not recursive), ordered, cut at ``MAX_LIST_ENTRIES``."""

    def __init__(self, area: AuthorizedArea | None) -> None:
        self._area = area

    @property
    def name(self) -> str:
        return "listar_archivos"

    @property
    def description(self) -> str:
        return (
            "Lista los archivos y carpetas de una carpeta del área de trabajo, sin entrar en "
            "las subcarpetas. Usa 'path' con la carpeta; '.' es la raíz del área."
        )

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Ruta de la carpeta a listar.",
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        }

    @property
    def risk(self) -> RiskLevel:
        return RiskLevel.LOW

    async def run(self, args: dict[str, Any]) -> ToolResult:
        raw = args.get("path")
        resolved = resolve_in_area(self._area, raw)
        if isinstance(resolved, ToolResult):
            return resolved
        shown = bounded_path(raw)
        try:
            if not resolved.exists():
                return error_result(
                    "no_existe",
                    f"La ruta '{shown}' no existe. Prueba con '.' para listar la raíz del área.",
                )
            if not resolved.is_dir():
                return error_result(
                    "no_es_carpeta",
                    f"La ruta '{shown}' no es una carpeta. "
                    "Usa 'leer_archivo' para leer un archivo.",
                )
            entries = sorted(resolved.iterdir(), key=lambda e: (e.name.casefold(), e.name))
            lines = [f"[{_kind(entry)}] {bounded_path(entry.name)}" for entry in entries]
        except Exception:
            return error_result(
                "error_de_archivo",
                f"No se pudo listar '{shown}' (permisos o error del sistema). "
                "Revisa los permisos de la carpeta.",
            )
        if not lines:
            return ToolResult(call_id="", content="La carpeta está vacía.")
        extra = len(lines) - MAX_LIST_ENTRIES
        if extra > 0:
            lines = lines[:MAX_LIST_ENTRIES]
            lines.append(f"... {extra} entradas más no se muestran (máximo {MAX_LIST_ENTRIES}).")
        return ToolResult(call_id="", content=bounded_text("\n".join(lines)))
