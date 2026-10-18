# core/ports.py (ejemplo)
from typing import Protocol

from .messages import DefinicionHerramienta, Mensaje, RespuestaModelo


class Provider(Protocol):
    def completar(
        self, mensajes: list[Mensaje], herramientas: list[DefinicionHerramienta]
    ) -> RespuestaModelo: ...
