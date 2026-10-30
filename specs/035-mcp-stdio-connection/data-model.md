# Modelo de datos: HU-08-01

Sin persistencia (no cambia el esquema SQLite).

## `McpServerConfig` (en `config.py`, validado al cargar)

| Campo | Tipo | Regla |
|---|---|---|
| `name` | `str` | clave de la tabla `[mcp_servers.<name>]`; `[A-Za-z0-9_-]{1,32}` |
| `command` | `str` | obligatorio, no vacío, una línea, ≤ 500 caracteres |
| `args` | `tuple[str, ...]` | lista de textos, sin caracteres de control; por defecto `()` |
| `env` | `tuple[str, ...]` | **nombres** de variables del proceso padre que se pasan al hijo; cada uno `[A-Za-z_][A-Za-z0-9_]*`; por defecto `()` |
| `startup_timeout_s` | `float` | > 0 y ≤ 300; por defecto 15 |
| `call_timeout_s` | `float` | > 0 y ≤ 3600; por defecto 60 |

`HarnessConfig.mcp_servers: tuple[McpServerConfig, ...] = ()`. Campos desconocidos → `[mcp_servers.x] campo desconocido`; campo con aspecto de clave → `SecretInConfigFileError` (regla existente).

## `McpServerSettings` (en `adapters/mcp/settings.py`, frozen)

`name`, `command`, `args`, `env_names`, `startup_timeout_s`, `call_timeout_s`, `close_timeout_s = 10.0`. Lo construye `bootstrap.py` desde `McpServerConfig` (el adaptador no importa `config`).

## Estados de `McpStdioClient`

`created → connecting → connected → closing → closed`; `connecting → failed`; `connected → lost` (el servidor muere; HU-08-04 decidirá qué hacer). `connect()` en `connected` es idempotente; en `failed`/`closed` se rechaza con `McpConnectError`. `close()` es idempotente desde cualquier estado.

## Errores

- `McpError(Exception)`: base.
- `McpConnectError(McpError)`: `code` ∈ {`no_se_pudo_iniciar`, `cerro_al_arrancar`, `sin_respuesta`, `fallo`}; `server`; mensaje fijo en español por código.
- `McpDependencyError(McpError)`: el SDK no está instalado; el mensaje nombra `pip install ".[mcp]"`.
