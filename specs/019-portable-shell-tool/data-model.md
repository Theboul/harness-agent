# Data Model: HU-01-04 — Herramienta de shell portable con tiempo límite

Sin persistencia. Lo que hay son tipos en memoria de los adaptadores y los tipos existentes del núcleo, que no cambian.

## Tipos existentes (sin cambios)

| Tipo | Dónde | Uso aquí |
|---|---|---|
| `Shell` (ABC) | `core/interfaces/system.py` | `interpreter_name` y `execute(command, timeout_seconds) -> ShellResult` |
| `ShellResult` | idem | `exit_code: int`, `output: str`, `timed_out: bool = False` |
| `Tool`, `RiskLevel`, `ToolResult` | `core/interfaces/tool.py`, `core/entities.py` | `ShellTool`; riesgo `HIGH`; `ToolResult(call_id="", content, is_error)` |
| `AuthorizedArea` | `core/interfaces/system.py` | Fija la carpeta de partida (`root`) |
| `Message`, `Role` | `core/entities.py` | Mensaje de sistema con el entorno |

## Tipos nuevos (en `adapters/system/`)

### `SubprocessShell` (clase base de `Shell`)

| Campo (constructor) | Tipo | Regla |
|---|---|---|
| `cwd` | `Path` | Carpeta de partida; debe existir al ejecutar |
| `environ` | `Mapping[str, str]` | Entorno de partida (inyectado; por defecto vacío) |
| `removed_env` | `Collection[str]` | Nombres de variables a quitar (claves de proveedores) |
| `grace_seconds` | `float` (> 0) | Entre la petición amable y la forzada |
| `max_output_chars` | `int` (> `NOTICE_RESERVE_CHARS`) | Máximo de la salida devuelta |
| `which` | `Callable[[str], str \| None]` | Búsqueda del ejecutable (inyectable) |
| `control` | `ProcessControl` | Terminación por plataforma (inyectable) |

Estados de `execute`: `validar → arrancar → leer + esperar → (terminar árbol si agota el tiempo) → recoger`. Reglas: tiempo no positivo o no numérico → `ValueError`; ejecutable ausente o fallo al arrancar → `ShellStartError`; todo lo demás devuelve `ShellResult`.

### `BashShell` / `PowerShellShell`

Solo cambian: `interpreter_name` (`"bash"` / `"powershell"`), el ejecutable candidato (`bash`; `pwsh` o `powershell`) y `_argv(executable, command) -> list[str]`.

### `ShellStartError(OSError)`

Mensaje en español, sin rutas ni el comando: «No se encontró el intérprete (<nombre>).» o «No se pudo iniciar el intérprete (<nombre>).».

### `OutputCollector`

| Atributo | Descripción |
|---|---|
| `head` | Primeros `max//2` caracteres |
| `tail` | Últimos `max - max//2` caracteres tras la cabeza |
| `total` | Caracteres vistos |
| `feed(chunk: bytes)` | Decodifica incrementalmente (UTF-8, `replace`) y actualiza |
| `finish() -> str` | Texto final: completo si `total ≤ max`; si no, `head[:H'] + aviso + tail[-T']` con `H' + T' + len(aviso) ≤ max` |

Aviso: `\n[salida recortada: se omitieron N caracteres]\n`.

### `ProcessControl` (ABC) y sus dos implementaciones

| Miembro | `PosixProcessControl` | `WindowsProcessControl` |
|---|---|---|
| `popen_options()` | `{"start_new_session": True}` | `{"creationflags": CREATE_NEW_PROCESS_GROUP \| CREATE_NO_WINDOW}` |
| `request_stop(proc)` | `killpg(SIGTERM)` | `send_signal(CTRL_BREAK_EVENT)` |
| `force_stop(proc)` | `killpg(SIGKILL)` (tolera `ProcessLookupError`) | `taskkill /PID n /T /F` (tolera el fallo) |
| `cleanup(proc)` | `force_stop` tras salida normal | nada |

### `DeniedCommand` y `DEFAULT_DENIED_COMMANDS`

`DeniedCommand(pattern: str, reason: str)` (`frozen`). `DEFAULT_DENIED_COMMANDS: Mapping[str, tuple[DeniedCommand, ...]]` con las claves `"bash"` y `"powershell"` (`MappingProxyType`). `denied_commands_for(interpreter) -> tuple[DeniedCommand, ...]` (vacío si el intérprete no se conoce, falla abierta sobre un dato que nadie aplica aquí; HU-05-02 decidirá).

### Funciones puras

| Función | Firma |
|---|---|
| `child_environment` | `(environ: Mapping[str, str], removed: Collection[str], *, windows: bool) -> dict[str, str]` |
| `select_shell` | `(system_name: str, *, cwd: Path, environ=…, removed_env=…, which=…, …) -> Shell` |
| `interpreter_for` | `(system_name: str) -> str` (`"powershell"` si `Windows`; si no `"bash"`) |
| `environment_notice` | `(system_name: str, interpreter: str) -> str` |

## Tipo nuevo (en `adapters/tools/`)

### `ShellTool(Tool)`

| Miembro | Valor |
|---|---|
| `name` | `shell` |
| `risk` | `RiskLevel.HIGH` |
| `schema` | `{"type": "object", "properties": {"command": {"type": "string", "minLength": 1, "maxLength": 8000}, "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 600}}, "required": ["command"], "additionalProperties": false}` |
| constructor | `ShellTool(shell: Shell \| None, area: AuthorizedArea \| None)` |

Etiquetas: `[codigo_de_salida=N]`, `[tiempo_agotado]`, `[interprete_no_disponible]`, `[sin_area]`, `[error_de_shell]`.

## Cambios en `bootstrap.py`

| Cambio | Detalle |
|---|---|
| `Composition.history_prefix` | `tuple[Message, ...]` con el mensaje de sistema |
| `compose(..., environ=None)` | Entorno del hijo (por defecto `os.environ`) |
| `run_session` | `history = list(composition.history_prefix)` |
| `main` | Pasa su `environ` a `compose` |
