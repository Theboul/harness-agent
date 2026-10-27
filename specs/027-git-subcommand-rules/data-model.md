# Data Model: HU-11-02

Todo lo nuevo de `core/` es inmutable y solo usa la biblioteca estándar. No hay tablas nuevas ni cambios en SQLite.

## `GitClass` (`core/permissions/git_rules.py`)

`str, Enum`: `READ = "lectura"` (se permite si todo el comando son lecturas), `ASK = "preguntar"`, `DENY = "denegar"`. Orden de severidad: `DENY` > `ASK` > `READ`.

## `classify_git(part: CommandPart, *, risky_environment: bool = False) -> GitClass`

Función pura para una parte cuyo `program` es `git`. Pasos:

1. Opciones globales (research R3). Una arriesgada fija como mínimo `ASK`.
2. Subcomando y sus opciones (cortas separadas, largas por nombre, `--` anotado, refspecs).
3. Tabla de research R4 → `DENY`, `READ` o `ASK`.
4. Las lecturas con opciones de efecto o con `redirect_targets` pasan a `ASK`.
5. `risky_environment=True` (una asignación `GIT_*` en el comando) sube `READ` a `ASK`. Nunca baja un `DENY`.

Una parte cuyo programa no es `git` no se clasifica (`classify_git` lanza `ValueError`, y `GitPolicy` no la llama).

## Tabla de subcomandos (dato inmutable)

Estructuras `frozenset` y `MappingProxyType` a nivel de módulo:

- `READ_SUBCOMMANDS`;
- `LISTING_OPTIONS` por `branch` y `tag`;
- `READ_EFFECT_OPTIONS`;
- `DESTRUCTIVE_LONG` por subcomando (por ejemplo `push`: `--force`, `--force-with-lease`, `--force-if-includes`, `--delete`, `--mirror`);
- `DESTRUCTIVE_SHORT` por subcomando (por ejemplo `push`: `f`, `d`; `branch`: `D`);
- `KNOWN_GLOBAL_WITH_VALUE` y `KNOWN_GLOBAL_FLAGS`.

Revisable por el PO (H2). Contenido en research R4.

## `GitPolicy` (`core/permissions/git_rules.py`)

`GitPolicy(inner: PermissionPolicy, *, dialect: Dialect, tool: str, argument: str, deny_names: Sequence[str] = (), ask_names: Sequence[str] = ())` implementa `PermissionPolicy`; valida los tipos al construirse. No guarda estado entre llamadas. `deny_names` y `ask_names` son las listas `deny` y `ask` de herramientas de la configuración (ajuste de T006).

| Situación | Resultado |
|---|---|
| Otra herramienta | `inner.evaluate(call)` |
| Sin partes git (en ningún nivel) | `inner.evaluate(call)` |
| Alguna parte git `DENY` (en cualquier nivel), o la herramienta en `deny_names` | `DENY` |
| Alguna parte git `ASK`, o la herramienta en `ask_names` | `ASK`, sin consultar a `inner` |
| Todas las partes son lecturas git, comando entendido, sin `executable` ni redirecciones | `ALLOW` |
| Lecturas git mezcladas con partes que no son git | `inner.evaluate(call)` |
| Excepción al analizar o clasificar | `ASK` |
| `inner` lanza o devuelve un valor raro; llamada mal formada | `DENY` |

## `git_instructions() -> str`

Texto fijo en español para el prefijo (FR-010). Sin datos de la máquina.

## `hide_url_credentials(text: str) -> str` (`core/redaction.py`)

Función pura. Sustituye las credenciales (`usuario:secreto` o `token`) entre `esquema://` y `@` por `<secreto oculto>`. Idempotente, nunca lanza con un texto y lanza `TypeError` si no lo es. Marcador: `HIDDEN_SECRET = "<secreto oculto>"` (el mismo texto de `config.Secret`). Pieza que HU-10-02 debe absorber.

## Datos de la composición (`bootstrap.py`)

- `_protection(...)` añade `workspace / ".git"` a las carpetas protegidas cuando hay área.
- `history_prefix`: aviso de entorno → instrucciones de git (si hay área) → comandos de la tarea (si los hay).

## Relaciones

```text
ToolCall(shell, command) ─▶ ProtectedPolicy ─▶ CommandPolicy ─▶ GitPolicy ─▶ ExactCallPolicy ─▶ DefaultPermissionPolicy
                                                        │
                                   parse_command (HU-05-02) ─▶ classify_git por parte git
ShellTool.run ─▶ hide_url_credentials(salida) ─▶ ToolResult ─▶ (recorte HU-02-02) ─▶ modelo
```
