# Data Model: HU-11-03

Todos los tipos son `@dataclass(frozen=True)` en `core/`. No hay tablas nuevas ni cambios en SQLite.

## `CommandKind` (`core/tasks/commands.py`)

`str, Enum`: `TESTS = "pruebas"`, `LINT = "lint"`. El valor es la clave de la línea en la tarea.

## `TaskCommand` (`core/tasks/commands.py`)

| Campo | Tipo | Regla |
|---|---|---|
| `kind` | `CommandKind` | — |
| `command` | `str` | Sin espacios exteriores (se recortan al analizar); no vacío; ≤ `MAX_FIELD_CHARS` (2 000) |
| `timeout_seconds` | `int` | `1 ≤ t ≤ MAX_COMMAND_TIMEOUT_SECONDS` (600); por defecto `DEFAULT_COMMAND_TIMEOUT_SECONDS` (300); un `bool` no vale |

`__post_init__` lanza `ValueError` con mensaje fijo en español (sin el valor) si algo no se cumple.

Constantes nuevas: `DEFAULT_COMMAND_TIMEOUT_SECONDS = 300` y `MAX_COMMAND_TIMEOUT_SECONDS = 600`. La segunda debe ser igual a `MAX_SHELL_TIMEOUT_SECONDS` de `adapters.tools`, y una prueba de cableado lo comprueba.

## `TaskDefinition` (`core/tasks/definition.py`, ampliación aditiva)

Campo nuevo, el **último** y con valor por defecto: `commands: tuple[TaskCommand, ...] = ()`. Regla añadida en `__post_init__`: como mucho un comando de cada `CommandKind`. Los cinco campos existentes y sus reglas no cambian, y una tarea sin comandos es igual a la de HU-11-01.

## `commands_notice(commands) -> str | None` (`core/tasks/commands.py`)

Función pura. Con `()` devuelve `None`. Con comandos, devuelve un texto fijo en español: cada comando en su propia línea, con el tipo, el texto exacto entre comillas invertidas y el tiempo máximo, más la regla «solo estos textos exactos se ejecutan sin preguntar; cualquier variación pide aprobación».

## `AllowedCall` (`core/permissions/exact_calls.py`)

| Campo | Tipo | Regla |
|---|---|---|
| `tool` | `str` | No vacío |
| `argument` | `str` | No vacío; nombre del argumento con el texto exacto |
| `value` | `str` | No vacío tras recortar los espacios exteriores; se guarda recortado |
| `limit_argument` | `str` | No vacío y distinto de `argument` |
| `limit` | `int \| float` | Finito, > 0 (no `bool`) |
| `default_limit` | `int \| float` | Finito, > 0 (no `bool`); es el valor que se toma si la llamada no trae `limit_argument` |

Método `matches(call: ToolCall) -> bool` (sin estado; detalle en `research.md` R4).

## `ExactCallPolicy` (`core/permissions/exact_calls.py`)

`ExactCallPolicy(inner: PermissionPolicy, allowed: Sequence[AllowedCall], *, ask_names: Sequence[str] = ())` implementa `PermissionPolicy`. Valida los tipos al construirse (`TypeError` con mensaje fijo) y guarda una tupla inmutable y un `frozenset`. Transiciones de `evaluate` (sin estado entre llamadas):

| Decisión de `inner` | Condición | Resultado |
|---|---|---|
| `DENY` | — | `DENY` |
| `ALLOW` | — | `ALLOW` |
| `ASK` | `call.name in ask_names` | `ASK` |
| `ASK` | alguna `allowed[i].matches(call) is True` | `ALLOW` |
| `ASK` | ninguna coincide | `ASK` |
| otro valor / excepción | — | `DENY` |

## Relaciones

```text
archivo de tarea ──parse_task──▶ TaskDefinition.commands (TaskCommand×≤2)
                                        │  bootstrap.compose()
                                        ▼
        AllowedCall(tool="shell"*, argument=COMMAND_ARGUMENT*, value=command,
                    limit_argument=TIMEOUT_ARGUMENT*, limit=timeout_seconds,
                    default_limit=DEFAULT_SHELL_TIMEOUT_SECONDS*)      (* desde adapters.tools)
                                        │
ProtectedPolicy( ExactCallPolicy( DefaultPermissionPolicy ), … )  ──▶ AgentLoop
commands_notice(task.commands) ──▶ Message(SYSTEM) en Composition.history_prefix
```
