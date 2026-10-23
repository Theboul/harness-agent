"""ReadFileTool: reads a text file inside the authorized area (HU-01-03, ``leer_archivo``)."""

from __future__ import annotations

from typing import Any

from harness_agent.adapters.tools._limits import MAX_READ_BYTES
from harness_agent.adapters.tools._paths import bounded_path, error_result, resolve_in_area
from harness_agent.core import AuthorizedArea, RiskLevel, Tool, ToolResult


class ReadFileTool(Tool):
    """Read the UTF-8 text of a file; every failure is a result, never an exception."""

    def __init__(self, area: AuthorizedArea | None) -> None:
        self._area = area

    @property
    def name(self) -> str:
        return "leer_archivo"

    @property
    def description(self) -> str:
        return (
            "Lee el texto (UTF-8) de un archivo del área de trabajo. "
            "Usa 'path' con una ruta relativa al área o absoluta dentro de ella."
        )

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Ruta del archivo a leer.",
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
                    f"La ruta '{shown}' no existe. Usa 'listar_archivos' para ver los archivos.",
                )
            if not resolved.is_file():
                return error_result(
                    "no_es_archivo",
                    f"La ruta '{shown}' no es un archivo. "
                    "Usa 'listar_archivos' para ver el contenido de una carpeta.",
                )
            with resolved.open("rb") as handle:
                data = handle.read(MAX_READ_BYTES + 1)
        except Exception:
            return error_result(
                "error_de_archivo",
                f"No se pudo leer '{shown}' (permisos o error del sistema). "
                "Revisa los permisos del archivo.",
            )
        if len(data) > MAX_READ_BYTES:
            return error_result(
                "demasiado_grande",
                f"El archivo '{shown}' supera el máximo de {MAX_READ_BYTES} bytes. "
                "Usa 'buscar_texto' para localizar lo que necesitas.",
            )
        if b"\x00" in data:
            return error_result("no_es_texto", f"El archivo '{shown}' no parece texto (binario).")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return error_result("no_es_texto", f"El archivo '{shown}' no es UTF-8.")
        return ToolResult(call_id="", content=text)
