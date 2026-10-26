# Modelo de datos (Fase 1): SPK-04

Solo tipos de prueba en `tests/spikes/mcp_probe.py`; ninguno entra en `src/`.

| Entidad | Campos | Notas |
|---|---|---|
| `ProbeServer` | `command: str`, `args: tuple[str, ...]`, `env: Mapping[str, str] \| None` | Cómo lanzar el servidor; el demo usa `sys.executable` y la ruta de `mcp_demo_server.py` |
| `Handshake` (frozen) | `protocol_version: str`, `server_name: str`, `has_tools: bool`, `capabilities: tuple[str, ...]`, `elapsed_s: float` | Resultado de negociar; `elapsed_s` es informativo |
| `ListedTool` (frozen) | `name: str`, `description: str`, `input_schema: dict[str, Any]` | Lo mínimo que HU-08-02 necesita para construir un `Tool` |
| `CallOutcome` (frozen) | `text: str`, `is_error: bool`, `structured: dict[str, Any] \| None` | Aplanado de lo que devuelve `call_tool` |
| `FailureObservation` (frozen) | `kind: str`, `exception_type: str`, `elapsed_s: float`, `child_alive: bool` | Una fila por modo de fallo (arranque, caída, tiempo agotado, cancelación) |

## Herramientas del servidor de demostración

| Herramienta | Propósito | Caso que cubre |
|---|---|---|
| `add(a: int, b: int)` | Suma determinista | Camino feliz, esquema con tipos |
| `echo(text: str)` | Devuelve el texto | Contenido de texto y centinela de filtración |
| `fail()` | Lanza `ValueError` | Resultado con `is_error` |
| `slow(seconds: float)` | Duerme | Tiempo de espera y cancelación |
| `crash()` | Termina el proceso (`os._exit`) | Caída a mitad de llamada |
| `pid()` | Devuelve el PID del servidor | Comprobar procesos huérfanos |
| `free_form(payload: dict)` | Acepta un objeto libre | Esquema sin `properties` fijas |
