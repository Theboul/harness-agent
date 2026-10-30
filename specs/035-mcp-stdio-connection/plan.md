# Plan de implementación: HU-08-01 — Conexión a un servidor MCP por stdio

**Spec**: [spec.md](spec.md) · **Rama**: `claude/hu-08-01-mcp-client-cbf065` · **Fecha**: 2026-10-30

## Resumen

Un adaptador nuevo `adapters/mcp/` implementa el puerto existente `McpClient` sin cambiarlo. Una **tarea de fondo** abre `stdio_client` + `ClientSession` y los mantiene abiertos hasta una señal de cierre (el SDK exige cerrar en la misma tarea que abrió: SPK-04 §5.3). `connect()` espera a que la tarea avise «listo» o «falló». Los fallos del SDK (`ExceptionGroup`) se aplanan y se traducen a errores de dominio con texto fijo en español. `config.py` gana una sección aditiva `[mcp_servers.<nombre>]`; `bootstrap.py` construye los clientes en `compose()` (síncrono, sin conectar) y los conecta/cierra dentro de `run_session` (donde ya hay un bucle de eventos). Un servidor que falla produce un aviso por `WarningSink`; el arnés sigue.

## Contexto técnico

- **Lenguaje**: Python 3.12; mypy estricto; `ruff` línea 100. **Dependencia**: `mcp==2.3.0` (extra `mcp`), cargada con `importlib` solo dentro de `adapters/mcp/`.
- **Pruebas**: `pytest` + `asyncio_mode=auto`; servidor local `tests/spikes/mcp_demo_server.py` (sin modificar) más un servidor propio de pruebas para el entorno (`tests/integration/`).
- **Rendimiento**: arranque 1,3–2,0 s (SPK-04); tiempo de negociación 15 s, de llamada 60 s, de cierre 10 s (todos configurables o inyectables).
- **Sin NEEDS CLARIFICATION**: ver `research.md`.

## Constitution Check (reglas duras de las tres skills del proyecto)

| Regla | Cumple | Nota |
|---|---|---|
| `core/` solo stdlib y `harness_agent.core`; sin `mcp` | Sí | `core/` no se toca |
| Puertos y `core/events.py` sin cambios (acuerdo A, B, C) | Sí | `McpClient` intacto; sin evento nuevo (H6) |
| Todo lo externo (procesos, SDK, disco) en `adapters/` | Sí | `adapters/mcp/` |
| El adaptador traduce errores externos a errores de dominio | Sí | `McpConnectError`, `McpDependencyError`; resultados de llamada como `ToolResult(is_error=True)` |
| Adaptadores no importan `cli` ni otro adaptador; no leen entorno/config | Sí | el entorno llega inyectado (`environ`); `config.py` define el tipo de configuración y `bootstrap.py` lo mapea |
| Reloj, entorno y rutas inyectados | Sí | `environ`, `log_path`, `sdk_loader`, tiempos |
| Falla cerrada | Sí | sin SDK, sin servidor o con error: sin herramientas + aviso; nunca «permitir» |
| Sin secretos en el repo; config rechaza campos con aspecto de clave | Sí | `env` es lista de **nombres** |
| `bootstrap.py` es la única raíz de composición | Sí | cambios mínimos y aditivos |
| Guarda `ast` para el módulo nuevo | Sí | `tests/architecture/test_mcp_boundaries.py` (+ `GUARDED` de `test_adapters_boundaries.py` no aplica: `mcp/` tiene guarda propia, como `providers/`) |

**Lista de comprobación de `capas-y-reglas.md` (se completa al cerrar, T-final)**: puerto sin cambios (sí); adaptador en `adapters/` (sí); conexión solo en `bootstrap.py` (sí); prueba de contrato del adaptador real sin red ni claves (sí, servidor local por stdio); núcleo sin E/S (sí, intacto); «no» justificados: ninguno.

## Gates de decisión (arquitectura-hexagonal-clean)

| Pregunta | Resultado |
|---|---|
| ¿Regla nueva en `core/`? | No: es una conexión externa |
| ¿Necesita algo de fuera? | Procesos y SDK: `McpClient` ya existe |
| ¿Quién lo implementa? | `adapters/mcp/` |
| ¿Cómo se conecta? | Constructor; `compose()` crea, `run_session` conecta/cierra |
| ¿Cómo se prueba? | Contrato contra el servidor local por stdio, sin red |
| ¿Asíncrono? | Sí (`McpClient.*`, D-01) |

## Estructura del proyecto (estructura-carpetas-harness)

Fila de la tabla: «Código con `litellm`, `sqlite3`, `mcp`, `subprocess`… → `adapters/<subpaquete>/`». Receta de «conexión/cliente»: paquete con `__init__` que exporta la API pública, módulos internos y prueba en la carpeta equivalente de `tests/`.

```text
src/harness_agent/adapters/mcp/
├── __init__.py          # API pública: McpStdioClient, McpServerSettings, errores, connect_all, close_all
├── errors.py            # McpError, McpConnectError, McpDependencyError (mensajes fijos en español)
├── settings.py          # McpServerSettings (frozen), valores por defecto de tiempos
├── environment.py       # server_environment(environ, names) -> dict (solo lo nombrado)
├── sdk.py               # load_sdk(): importlib de mcp; McpSdk (NamedTuple de lo que se usa)
├── translate.py         # leaf_exceptions, classify -> código; texto fijo por código
├── stderr_log.py        # open_stderr_log: único módulo que abre un archivo (solo escritura)
├── client.py            # McpStdioClient(McpClient): tarea dueña, connect/close/call_tool/list_tools
└── connections.py       # connect_all / close_all: tolera fallos y avisa por una función
src/harness_agent/config.py          # + HarnessConfig.mcp_servers y los ganchos mínimos de [mcp_servers.*]
src/harness_agent/config_mcp.py      # McpServerConfig y check_mcp_servers (validación pura; config.py la invoca; separado para minimizar conflictos con otras historias que tocan config.py)
src/harness_agent/bootstrap.py       # + construir clientes en compose(); conectar/cerrar en run_session
pyproject.toml, requirements-dev.txt # + extra `mcp = ["mcp==2.3.0"]` (el pin de requirements ya existe)
tests/unit/adapters/mcp/             # settings, environment, translate, sdk, client (SDK doble), connections
tests/integration/test_mcp_stdio_connection.py  # servidor real por stdio; cierre; cancelación; entorno; fallos
tests/integration/mcp_env_probe_server.py       # servidor mínimo que informa de los nombres de entorno
tests/unit/test_config_mcp.py                   # sección [mcp_servers]
tests/architecture/test_mcp_boundaries.py       # guarda ast del paquete nuevo
tests/unit/test_dependency_pins.py              # + extra mcp
```

## Diseño (resumen; detalle en `data-model.md` y `contracts/`)

1. **Tarea dueña** (`McpStdioClient._own`): `async with stdio_client(params, errlog=file) as (r, w): async with ClientSession(r, w, read_timeout_seconds=startup) as s: await s.initialize(); publicar listo; await stop.wait()`. Toda la apertura y el cierre ocurren en esa tarea. `close()` fija `stop` y espera la tarea (con tope; si no, `cancel()` + espera). `connect()` cancelado → cancela y espera a la tarea (sin huérfanos).
2. **Errores**: `translate.leaf_exceptions` aplana; `classify` → `no_se_pudo_iniciar` (`OSError`), `cerro_al_arrancar` (`Connection closed`), `sin_respuesta` (`TimeoutError` o `timed out`), `sdk_incompatible`/`fallo` (resto). El mensaje de dominio nunca incluye `str(error)`.
3. **Entorno**: el SDK ya mezcla `get_default_environment()` (lista segura: `PATH`, `HOME`, `SYSTEMROOT`…) con el `env` que se le da; el adaptador entrega **solo** las variables nombradas por la configuración que existan en el entorno inyectado. Se comprueba con un servidor real.
4. **stderr**: archivo `mcp-<nombre>.log` junto a la base de sesiones (carpeta protegida del arnés) o `os.devnull` si no se puede abrir; se cierra en la tarea dueña.
5. **`call_tool`**: `session.call_tool(name, arguments, read_timeout_seconds=call_timeout)`; texto de los bloques de texto si `is_error` es falso; si `is_error` o excepción, texto fijo (`[mcp_error]`, `[mcp_timeout]`, `[mcp_server_down]`, `[mcp_not_connected]`); la cancelación se propaga.
6. **Costuras**: `list_tools()` devuelve `[]` (HU-08-02); cada cliente es independiente (HU-08-04/05); `connect_all` recibe la lista y la función de aviso.

## Seguimiento de complejidad

Sin violaciones. La asimetría `close()` (método de la clase concreta, no del puerto) se documenta como alternativa (a) de H1.
