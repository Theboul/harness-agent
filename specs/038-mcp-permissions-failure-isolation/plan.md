# Plan: HU-08-03 + HU-08-04

**Spec**: [spec.md](spec.md)

## Decision Gates (`arquitectura-hexagonal-clean`)

| Pregunta | Respuesta |
|---|---|
| ¿Regla nueva en `core/`? | Sí, mínima y genérica: `AskCeilingPolicy` (política que solo endurece), en `core/permissions/ask_ceiling.py`, exportada en `core/permissions/__init__.py` y `core/__init__.py`. No conoce MCP. |
| ¿Puerto nuevo? | No. `McpClient`, `PermissionPolicy`, `Tool` no cambian. |
| ¿Quién implementa lo de MCP? | `adapters/mcp/` (`tool.py`, `client.py`, `registration.py`, `connections.py`). |
| ¿Conexión? | `bootstrap.py`: un conjunto `mcp_tool_names`, una envoltura de la política y un argumento en la llamada a `register_mcp_tools`. Nada reordenado. |
| ¿Prueba? | Unit (techo; cliente perdido/tope duro; `McpTool`; `connect_all`/registro), integración con `AgentLoop` real y con el servidor de demostración, guardas `ast`. |
| ¿Async? | Sin cambios de firma en puertos; `call_tool`/`run` ya son `async`. |

## Project Structure (`estructura-carpetas-harness`)

| Archivo | Fila que lo justifica |
|---|---|
| `core/permissions/ask_ceiling.py` | «Regla de negocio (permisos) → subpaquete de `core/`» |
| `core/permissions/__init__.py`, `core/__init__.py` (+exportación) | «Todo lo público de `core/` se exporta» |
| `adapters/mcp/{tool,client,registration,connections}.py` (edición) | «Código con `mcp`/procesos → `adapters/mcp/`» |
| `bootstrap.py` (cableado mínimo) | «Unir piezas → `bootstrap.py`» |
| `tests/unit/core/permissions/test_ask_ceiling.py` | equivalente de `tests/` |
| `tests/unit/adapters/mcp/test_isolation.py` | ídem |
| `tests/integration/test_mcp_permissions_agent_loop.py`, `test_mcp_failure_isolation.py` | integración con el bucle real / servidor real |
| `tests/architecture/test_ask_ceiling_boundaries.py`, `test_mcp_boundaries.py` (+reglas) | guardas de frontera |

## Constitution Check / lista de `capas-y-reglas.md`

| Punto | ¿Cumple? |
|---|---|
| `core/` solo stdlib y núcleo; sin E/S, entorno ni terminal | Sí |
| Puertos, `entities`, `events`, `loop` intactos | Sí |
| Errores del SDK traducidos en el adaptador; el núcleo no conoce `mcp` | Sí |
| Dependencias por constructor; cableado solo en `bootstrap.py` | Sí |
| Falla cerrada (techo, `perdido`, textos fijos) | Sí |
| Un adaptador no importa otro | Sí |
| Texto del servidor no llega a errores/avisos/eventos | Sí |
| Archivos protegidos sin tocar | Sí |
| Módulo nuevo de `core/` trae su guarda en `tests/architecture/` | Sí |

## Diseño

- `AskCeilingPolicy.evaluate`: `decision = inner.evaluate(call)`; si no es `PermissionDecision` → `DENY`; si `decision is ALLOW and call.name in names` → `ASK`; si no, `decision`. `except Exception` → `DENY`. El módulo no devuelve `PermissionDecision.ALLOW`.
- Cliente: nuevo estado `_LOST`. `call_tool`: `_LOST` → `[mcp_server_down]`; `CONNECTED` con sesión → `wait_for(session.call_tool(...), call_timeout_s + 5)`; si la clasificación es `SERVER_DOWN` → `_LOST`. En `_own`, una excepción tras negociar → `_LOST`. `close()` desde `_LOST` sigue el camino normal.
- `McpTool.run`: `try/except Exception → ToolResult("", "[mcp_error] …", True)`.
- `connect_all`/`register_mcp_tools`: `except Exception` con aviso fijo; el nombre sale de `getattr(client, "name", None)` si es seguro.
