# Plan: HU-08-02 — Descubrir herramientas MCP

**Spec**: [spec.md](spec.md)

## Decision Gates (`arquitectura-hexagonal-clean`)

| Pregunta | Respuesta |
|---|---|
| ¿Regla nueva en `core/`? | No. Traducir MCP a `Tool` es del adaptador. |
| ¿Puerto nuevo? | No: `McpClient.list_tools() -> list[Tool]` ya existe. |
| ¿Quién implementa? | `adapters/mcp/` (`tool.py`, `registration.py`, `client.list_tools`). |
| ¿Conexión? | Solo `bootstrap.py` (`Composition.registry`, llamada tras `connect_all`). |
| ¿Prueba? | Unit con `FakeSdk` ampliado; integración con el servidor de demostración; guarda `ast`. |
| ¿Async? | `list_tools` y `register_mcp_tools` son `async`. |

## Project Structure (`estructura-carpetas-harness`)

| Archivo | Fila que lo justifica |
|---|---|
| `adapters/mcp/tool.py` — `McpTool`, `translate_tool` | «Código con `mcp`/procesos → `adapters/<subpaquete>/`» |
| `adapters/mcp/registration.py` — `register_mcp_tools` | ídem |
| `adapters/mcp/errors.py` (+`McpListError`), `sdk.py` (+`page_params`), `client.py` (+`list_tools`, `name`) | ídem |
| `bootstrap.py` (+`Composition.registry`, llamada) | «Unir piezas → `bootstrap.py`» |
| `tests/unit/adapters/mcp/test_discovery.py`, `fake_sdk.py` | equivalente de `tests/` |
| `tests/integration/test_mcp_tool_discovery.py` | integración con el servidor real |
| `tests/architecture/test_mcp_boundaries.py` (+reglas) | guarda de la frontera |

## Constitution Check / lista de `capas-y-reglas.md`

| Punto | ¿Cumple? |
|---|---|
| `core/` sin cambios ni importaciones nuevas | Sí |
| Puertos, `entities`, `events` intactos | Sí |
| Errores del SDK traducidos a errores de dominio (`McpListError`) | Sí |
| Dependencias por constructor; cableado solo en `bootstrap.py` | Sí |
| Sin `print`/entorno en el adaptador | Sí |
| Falla cerrada (`HIGH`, omitir lo no válido) | Sí |
| Un adaptador no importa otro | Sí |
| Archivos protegidos sin tocar | Sí |

## Diseño

- `list_tools` usa `session.list_tools(params=PaginatedRequestParams(cursor=…))` (SDK 2.x: `input_schema`, `next_cursor`); `McpSdk.page_params` lleva la clase para no importar `mcp` fuera de `sdk.py`. Cada página va con `wait_for(call_timeout_s)`.
- `McpTool.run` reenvía a `client.call_tool(nombre_remoto, args)`; el bucle fija el `call_id`.
- `register_mcp_tools` captura `ToolRegistryError` (API pública del núcleo) y avisa con texto fijo.
