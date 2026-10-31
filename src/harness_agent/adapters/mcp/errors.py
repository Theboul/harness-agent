"""Domain errors of the MCP adapter (HU-08-01).

Every text is a fixed sentence in Spanish for the user. None of them reproduces what the SDK or
the server said, the arguments, the environment or a path: the original exception stays in
``__cause__`` for a developer and never reaches the user, the events or the model.
"""

from __future__ import annotations

_UNAVAILABLE = (
    "El servidor MCP '{server}' no está disponible: {reason}. Se continúa sin sus herramientas."
)
_REASONS = {
    "no_se_pudo_iniciar": "no se encontró o no se pudo ejecutar el comando configurado",
    "cerro_al_arrancar": "se cerró al arrancar",
    "sin_respuesta": "no respondió a tiempo",
    "fallo": "falló al conectarse",
}


class McpError(Exception):
    """Base of the errors of the MCP adapter; its text is always safe to show to the user."""


class McpConnectError(McpError):
    """The server could not be started or negotiated.

    Attributes:
        server: Name the server has in the configuration.
        code: Stable reason: ``no_se_pudo_iniciar``, ``cerro_al_arrancar``, ``sin_respuesta`` or
            ``fallo`` (anything else is shown as ``fallo``).
    """

    def __init__(self, server: str, code: str) -> None:
        self.server = server
        self.code = code
        reason = _REASONS.get(code, _REASONS["fallo"])
        super().__init__(_UNAVAILABLE.format(server=server, reason=reason))


class McpDependencyError(McpError):
    """The optional ``mcp`` library is not installed (or is not the expected version)."""

    def __init__(self, server: str) -> None:
        self.server = server
        super().__init__(
            f"El servidor MCP '{server}' necesita la biblioteca 'mcp'. Instálela con: "
            'pip install ".[mcp]". Se continúa sin sus herramientas.'
        )


class McpListError(McpError):
    """The server is connected but its tool list could not be read (HU-08-02)."""

    def __init__(self, server: str) -> None:
        self.server = server
        super().__init__(
            f"El servidor MCP '{server}' no pudo listar sus herramientas. Se continúa sin ellas."
        )
