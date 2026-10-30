# Investigación (Fase 0): SPK-04

## Qué fija ya el repositorio

| Fuente | Dato | Consecuencia para el spike |
|---|---|---|
| `docs/04d-historias-conexiones.md#spk-04` | AC-01: servidor de referencia sin credenciales, se negocian capacidades y se lista ≥ 1 herramienta | FR-001 / SC-001 |
| `core/interfaces/connections.py` | `McpClient`: `connect()`, `list_tools() -> list[Tool]`, `call_tool(name, arguments) -> ToolResult`; sin `close()` ni tiempo de espera | Hallazgo de ciclo de vida (D6) |
| `core/interfaces/tool.py` | `Tool` exige `name`, `description`, `schema`, `risk`, `run` | Un `RiskLevel` no viene de MCP: la política de HU-08-03 debe asignarlo (falla cerrada = al menos `ask`) |
| `core/tools/schema_validator.py` | `check_schema` y `validate_arguments` propios, stdlib | D5: validar los esquemas listados |
| `requirements-dev.txt` | `mcp==2.3.0` fijado como dependencia de `litellm[mcp]` | No se añade dependencia; `importorskip` |
| `docs/PROGRESO.md` (HU-01-02) | Los esquemas MCP con objetos libres deben declarar `additionalProperties: true`; `check_schema` no revisa valores cíclicos | Se prueba con un esquema libre |
| `docs/decisiones/D-01-asyncio-cancelacion.md` | Cancelación cooperativa con asyncio | Escenario de cancelación (FR-005) |
| `docs/03-plan-sprints.md` Sp4-26/27/28/29 | HU-00-05.2 y HU-08-01 estiman «servidor inexistente», «caída a mitad de sesión», «iniciar y negociar», «cerrar el proceso» | El spike mide exactamente esos cuatro casos |

## Qué se comprobó en una exploración previa (2026-10-25, Windows 10, Python 3.12.10)

- `mcp 2.3.0` es la rama 2.x: `FastMCP` pasó a `MCPServer` (`mcp.server.mcpserver`), existe `mcp.Client` además de `ClientSession`; `mcp.server.fastmcp` lanza `ModuleNotFoundError` con aviso de migración.
- Servidor propio por `sys.executable`: `initialize` en ~1,4 s en frío; protocolo `2025-11-25`; capacidades `tools`, `prompts`, `resources` declaradas.
- `call_tool` de una herramienta que lanza o con argumentos inválidos **no** lanza excepción en el cliente: devuelve `is_error=True` con texto; el texto de argumentos inválidos incluye el valor recibido (`input_value='x'`) y un enlace externo → no debe pasar tal cual al modelo.
- El traceback del servidor sale por stderr del proceso hijo.
- `npx -y @modelcontextprotocol/server-everything` falló por red (`npm error network`) y `uvx mcp-server-time` falló al instalar `pywin32` en Windows (archivo en uso) y se resolvió contra Python 3.14: los servidores de terceros dependen de red y de Node/uv en el primer arranque. Cuando no arrancan, el cliente ve un `ExceptionGroup`.

## Qué puede y qué no puede demostrar este spike

- **Puede**: AC-01 con un servidor propio; el contrato observado del SDK; los modos de fallo y su limpieza de procesos; la compatibilidad de esquemas con el validador del núcleo.
- **No puede**: la fiabilidad de servidores de terceros bajo carga, otros SO distintos de los de la CI, versiones de SDK distintas de la fijada, ni transportes HTTP/SSE.
