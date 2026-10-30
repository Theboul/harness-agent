# Contrato: `McpStdioClient` y configuración

## Constructor

`McpStdioClient(settings, *, environ, log_path=None, sdk_loader=load_sdk)`; `environ` es el entorno del padre (inyectado, nunca `os.environ`).

## Puerto `McpClient` (sin cambios)

| Método | Contrato |
|---|---|
| `await connect()` | Lanza la tarea dueña y espera «listo». Idempotente si ya está conectado. Fallo → `McpConnectError`/`McpDependencyError` (texto fijo), sin proceso vivo. Si quien espera se cancela, la tarea dueña se cancela y se espera; sin huérfanos. Tope: `startup_timeout_s` |
| `await list_tools()` | `[]` hasta HU-08-02 |
| `await call_tool(name, arguments)` | Nunca lanza por errores del servidor: `ToolResult(call_id="", content, is_error)`. Éxito: texto de los bloques de texto. Error: `[mcp_error]`, `[mcp_timeout]`, `[mcp_server_down]` o `[mcp_not_connected]` + frase fija; jamás el texto del servidor ni los argumentos. `CancelledError` se propaga |

## Métodos propios de la clase (no del puerto)

`await close()` (idempotente, nunca lanza salvo cancelación), `connected: bool`, `server_name: str | None`, `has_tools: bool`.

## `connect_all(clients, warn)` / `close_all(clients)`

`connect_all` conecta en orden; ante `McpError` llama `warn(str(error))` y sigue; la cancelación se propaga tras cerrar lo ya abierto. `close_all` cierra todos aunque uno falle.

## Configuración (`config.toml`)

```toml
[mcp_servers.demo]
command = "python"
args = ["servidor.py"]
env = ["PATH_EXTRA"]          # nombres de variables del entorno, nunca valores
startup_timeout_s = 15
call_timeout_s = 60
```

## Avisos al usuario (español, texto fijo)

- `no_se_pudo_iniciar`: «El servidor MCP '<nombre>' no se pudo iniciar: no se encontró o no se pudo ejecutar el comando configurado. Se continúa sin sus herramientas.»
- `cerro_al_arrancar`: «… se cerró al arrancar. …»
- `sin_respuesta`: «… no respondió a tiempo. …»
- `fallo`: «… falló al conectarse. …»
- dependencia: «… necesita la biblioteca 'mcp'. Instálela con: pip install ".[mcp]". …»
