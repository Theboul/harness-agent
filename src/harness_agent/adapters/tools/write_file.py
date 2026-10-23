"""WriteFileTool: creates or replaces a file inside the area (HU-01-03, ``escribir_archivo``)."""

from __future__ import annotations

from typing import Any

from harness_agent.adapters.tools._limits import MAX_WRITE_BYTES
from harness_agent.adapters.tools._paths import (
    bounded_path,
    error_result,
    outside_area,
    resolve_in_area,
)
from harness_agent.core import AuthorizedArea, RiskLevel, Tool, ToolResult


class WriteFileTool(Tool):
    """Write UTF-8 text. Nothing is written unless the real path is inside the area."""

    def __init__(self, area: AuthorizedArea | None) -> None:
        self._area = area

    @property
    def name(self) -> str:
        return "escribir_archivo"

    @property
    def description(self) -> str:
        return (
            "Crea o reemplaza un archivo de texto (UTF-8) dentro del área de trabajo. Crea las "
            "carpetas que falten. Usa 'path' para la ruta y 'content' para el contenido completo."
        )

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Ruta del archivo a crear o reemplazar.",
                },
                "content": {"type": "string", "description": "Contenido completo del archivo."},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        }

    @property
    def risk(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    async def run(self, args: dict[str, Any]) -> ToolResult:
        raw = args.get("path")
        resolved = resolve_in_area(self._area, raw)
        if isinstance(resolved, ToolResult):
            return resolved
        shown = bounded_path(raw)
        data = self._encode(args.get("content"))
        if isinstance(data, ToolResult):
            return data
        try:
            existed = resolved.exists()
            if existed and not resolved.is_file():
                return error_result(
                    "no_es_archivo",
                    f"La ruta '{shown}' no es un archivo, así que no se puede escribir en ella.",
                )
            resolved.parent.mkdir(parents=True, exist_ok=True)
            # The area is asked again right before writing: the disk may have changed meanwhile.
            if resolve_in_area(self._area, raw) != resolved:
                return outside_area(raw)
            resolved.write_bytes(data)
        except Exception:
            return error_result(
                "error_de_archivo",
                f"No se pudo escribir '{shown}' (permisos, disco o una ruta que no es carpeta). "
                "Revisa la ruta y los permisos.",
            )
        action = "reemplazado" if existed else "creado"
        return ToolResult(call_id="", content=f"Archivo {action}: '{shown}' ({len(data)} bytes).")

    @staticmethod
    def _encode(content: object) -> bytes | ToolResult:
        """The content as UTF-8 bytes, or the error to return when it cannot be written."""
        if not isinstance(content, str):
            return error_result("contenido_invalido", "El contenido debe ser un texto.")
        try:
            data = content.encode("utf-8")
        except UnicodeEncodeError:
            return error_result(
                "contenido_invalido", "El contenido no se puede codificar en UTF-8."
            )
        if len(data) > MAX_WRITE_BYTES:
            return error_result(
                "demasiado_grande",
                f"El contenido ({len(data)} bytes) supera el máximo de {MAX_WRITE_BYTES} bytes. "
                "Divídelo en varios archivos.",
            )
        return data
