# Research: HU-11-02 — Git mediante el shell con reglas por subcomando

Historia de 1 PHU. Las decisiones salen del código real de `origin/main` (61024bf, con HU-05-02 integrada), de la spec con sus Clarifications y de las restricciones del revisor. No hubo investigación externa salvo la sintaxis de opciones de git, que se resume aquí.

## R1. Un módulo puro: `core/permissions/git_rules.py`

- **Decision**: un único módulo nuevo, sin estado (salvo los atributos que fija `__init__`), solo con la biblioteca estándar y el núcleo. Contiene:
  - la **tabla de subcomandos** como dato inmutable;
  - `classify_git(part)`, que da una `GitClass` (`READ`, `ASK`, `DENY`) para una `CommandPart` cuyo programa es `git`;
  - `GitPolicy`, la política;
  - `git_instructions()`, el texto del prefijo (FR-010).

  Se apoya en `parse_command` de HU-05-02, que ya normaliza el programa (ruta, `.exe`), quita envoltorios y separa encadenados, y devuelve `arguments` en orden y sin comillas.
- **Rationale**: es la restricción 1. Las piezas de HU-05-02 (`command_*.py`) no cambian: `GitPolicy` solo las **consume**.
- **Alternatives considered**: añadir reglas de subcomando a la lista de denegados de HU-05-02, descartado porque esas reglas solo deniegan; no saben permitir lecturas ni forzar «preguntar».

## R2. Orden de las políticas y semántica de `GitPolicy` (restricción 2)

- **Decision**: la cadena queda `ProtectedPolicy(CommandPolicy(GitPolicy(ExactCallPolicy(DefaultPermissionPolicy))))`. `GitPolicy.evaluate(call)`:
  1. Si la llamada no es de la herramienta inyectada (`tool`), delega sin cambios.
  2. Analiza el texto del argumento (`argument`) con `parse_command(text, dialect)` y recorre las partes de todos los niveles (también las de `executable`: `bash -c`, `$( )`…).
  3. Si alguna parte git es **DENY** → `DENY`. Una variante destructiva en cualquier nivel deniega.
  4. Si no hay ninguna parte git → delega sin cambios.
  5. Si alguna parte git es **ASK** (escritura, desconocida, con `-c` o una opción global desconocida, con una asignación `GIT_*`, una lectura con efectos o con redirección) → `ASK` **sin consultar a `inner`**. Así la declaración de la tarea (`ExactCallPolicy`) nunca sube un push o un merge.
  6. Si todas las partes git son **READ**:
     - todas las partes del comando son lecturas git, el comando se entendió, no hay `executable` ni redirecciones → `ALLOW`;
     - si no (mezcla con partes que no son git) → delega a `inner`.
  7. Excepción al analizar o clasificar → `ASK`; excepción o valor raro de `inner` → `DENY`.

  `CommandPolicy`, que va fuera, ya deniega la lista base y baja a `ASK` cualquier `ALLOW` de un comando no entendido. `ProtectedPolicy` deniega antes que nadie.
- **Rationale**: se cumplen AC-01, AC-02 y V-17. El «permitir» de esta historia solo existe cuando todo son lecturas de la tabla; el resto, o se endurece o se delega.
- **Alternatives considered**: poner `GitPolicy` fuera de `CommandPolicy`, descartado porque la lista base y lo no entendido deben prevalecer (HU-05-02); ponerla dentro de `ExactCallPolicy`, descartado porque la declaración de la tarea podría subir un push.

## R3. Análisis de los argumentos de git (restricción 4)

- **Decision**:
  1. **Opciones globales**, sobre `part.arguments` en orden, mientras empiecen por `-`:
     - con valor (separado o con `=`), conocidas y sin efectos: `-C <ruta>`, `--git-dir`, `--work-tree`;
     - sin valor, conocidas: `--no-pager`, `-P`, `-p`, `--paginate`, `--bare`, `--no-replace-objects`, `--literal-pathspecs`, `--glob-pathspecs`, `--noglob-pathspecs`, `--icase-pathspecs`, `--no-optional-locks`;
     - **arriesgadas** (dejan la parte como mínimo en `ASK`): `-c <k=v>`, `--config-env`, `--exec-path`, `--namespace` y cualquier opción global desconocida.

     La siguiente palabra es el subcomando. Sin subcomando (`git`, `git --version`) → `ASK`.
  2. **Opciones del subcomando**, hasta `--`: `--larga[=v]` se guarda por nombre; `-abc` se separa en `-a`, `-b`, `-c` (b). Tras `--` todo son rutas, y se anota que `--` apareció.
  3. **Prefijos de opciones largas** (a): una opción dada `--x` coincide con una opción de la tabla `--xyz` si `"--xyz".startswith("--x")` y tiene al menos un carácter tras `--`. Si es prefijo de una opción **denegada** se deniega, aunque también lo sea de otra (prefijo ambiguo = denegar). Los prefijos de las opciones con efectos de lectura (`--output`, `--ext-diff`, `--textconv`, `--no-index`) pasan a `ASK`; por eso `--text` o `--no` también preguntan (conservador).
  4. **Refspecs de push**: un argumento posicional que empieza por `+` o `:` → `DENY`.
- **Rationale**: es el análisis mínimo para las reglas (a)–(d). Git distingue mayúsculas, así que la comparación es exacta, también en PowerShell (`arguments` conserva el texto original).

## R4. La tabla de subcomandos (dato; revisión del PO)

| Subcomando | READ (solo) | DENY | Lo demás |
|---|---|---|---|
| `status`, `diff`, `log`, `show`, `blame`, `shortlog`, `describe`, `rev-parse`, `ls-files` | siempre, salvo opciones con efectos o redirección | — | `ASK` |
| `grep` | sin `-O`/`--open-files-in-pager` | — | `ASK` |
| `branch` | sin posicionales y con opciones de listar (`-a -r -l -v --list --all --remotes --verbose --merged --no-merged --contains --no-contains --show-current --sort --format --color --no-color --column --no-column --points-at`), o con `-l`/`--list` y patrones | `-D`; `-d`/`--delete` junto a `-f`/`--force` | `ASK` (crear, `-m`, `-d`…) |
| `tag` | sin posicionales y con opciones de listar (`-l --list -n --sort --format --contains --no-contains --points-at --merged --no-merged --column --color`), o con `-l` y patrones | — | `ASK` |
| `stash` | `stash list` | `stash drop`, `stash clear` | `ASK` |
| `reset` | — | `--hard`, `--merge`, `--keep` | `ASK` |
| `clean` | — | siempre (incluido `-n`) | — |
| `push` | — | `-f`, `--force`, `--force-with-lease`, `--force-if-includes`, `-d`/`--delete`, `--mirror`, refspec `+…` o `:…` | `ASK` |
| `checkout` | — | `-f`/`--force`, `--` presente, posicional `.` | `ASK` |
| `restore` | — | sin `-S`/`--staged`, o con `-W`/`--worktree` | `ASK` (`--staged` solo) |
| `switch` | — | `--discard-changes`, `-f`/`--force` | `ASK` |
| `reflog` | — | `reflog expire` | `ASK` |
| `gc` | — | `--prune=now` (o `--prune now`) | `ASK` |
| `filter-branch` | — | siempre | — |
| `update-ref` | — | `-d` | `ASK` |
| cualquier otro (`commit`, `merge`, `add`, `rebase`, `cherry-pick`, `revert`, `fetch`, `pull`, `init`, `clone`, `rm`, `mv`, `config`, `remote`…, alias, desconocido) | — | — | `ASK` |

Opciones con efectos que sacan una lectura a `ASK`: `--output`, `--ext-diff`, `--textconv`, `--no-index` (y sus prefijos), y `-O`/`--open-files-in-pager` en `grep`. Una redirección (`redirect_targets` no vacío) también.

## R5. Asignaciones `GIT_*` (Q1)

- **Decision**: `parse_command` quita las asignaciones iniciales (`VAR=x cmd`) y los envoltorios `env`, así que la `CommandPart` no las conserva y no se puede tocar `command_parser.py`. `GitPolicy` busca en el **texto crudo** la expresión `(^|[\s;&|(`])GIT_[A-Za-z0-9_]*=`. Si aparece, todas las partes git del comando pasan como mínimo a `ASK`.
- **Rationale**: es conservador. Un falso positivo, como `echo GIT_X=1 && git status`, pregunta, no deniega. En PowerShell, `$env:GIT_X = …` ya no se entiende (HU-05-02), así que nunca hay «permitir».
- **Alternatives considered**: ampliar `CommandPart` con las asignaciones, descartado por la restricción 1.

## R6. Ocultado de credenciales en URLs (FR-011)

- **Decision**: una sola función pura, `hide_url_credentials(text) -> str`, en un módulo nuevo `core/redaction.py`, exportada en `core/__init__.py`. Usa la expresión `([A-Za-z][A-Za-z0-9+.-]*://)[^\s/@]+@`, que sustituye por `\1<secreto oculto>@`. Cubre `usuario:secreto@` y `token@` (también `ssh://git@host`, que solo lleva un usuario: es conservador). Una URL sin `@` y un texto sin URL no cambian. La aplica `ShellTool` a la salida en sus tres ramas (éxito, error, tiempo agotado) antes de devolver el `ToolResult`. Ningún evento lleva hoy esa salida, pero si alguno la llevara usaría la misma función.
- **Rationale**: la skill de estructura pondría la redacción en `observability/`, que está planeada. Pero `adapters/tools/` solo puede importar la biblioteca estándar y la API pública del núcleo (guarda `test_adapters_boundaries.py`), y `bootstrap.py` no tiene `observability` entre sus importaciones permitidas. `core/` es el único lugar que todos pueden usar sin tocar guardas. El marcador `<secreto oculto>` es el mismo texto que usa `config.Secret` y el adaptador LiteLLM. Se define aquí sin importar `config` (`core/` no puede). **Para HU-10-02**: debe absorber esta función.
- **Alternatives considered**: `observability/redaction.py`, descartado porque exigiría abrir guardas; un decorador de herramienta en `bootstrap.py`, descartado porque añade una pieza para algo que cabe en `ShellTool`; reutilizar `_clean` de LiteLLM, imposible porque solo sustituye una clave conocida.

## R7. Protección de `.git` como dato (FR-009)

- **Decision**: `bootstrap._protection` añade `workspace / ".git"` a las carpetas protegidas cuando hay área de trabajo. No se añade como **marcador** de shell, porque `.git` aparece en comandos legítimos como `cat .gitignore`. Se usan `ProtectedPaths` y `ProtectedPolicy` sin cambios. Efecto aceptado: las herramientas de archivos tampoco pueden leer `.git`.
- **Rationale**: decisión del revisor. `ProtectedPaths` juzga la ruta real, así que también sirve si `.git` aún no existe al arrancar (se crea después con `git init`).
- **Limitación**: solo protege la carpeta `.git` de la raíz del área, no las de subcarpetas (repositorios anidados ni submódulos). Se anota.

## R8. Instrucciones de git en el prefijo (FR-010, Sp2-44)

- **Decision**: `git_instructions()` devuelve un texto fijo en español: una rama por tarea, commits con mensajes descriptivos, push y merge piden aprobación, y lecturas permitidas sin preguntar. `compose()` lo añade como mensaje `SYSTEM` a `history_prefix` **cuando hay área de trabajo**, después del aviso de entorno y antes del mensaje de comandos de la tarea (HU-11-03).
- **Rationale**: `history_prefix` es la vía provisional en uso. `ContextAssembler` (HU-02-01) aún no está en el bucle, así que se repite la observación para HU-02-01: debe conservar estos mensajes.

## R9. Sp2-45: repositorio temporal con git real

- **Decision**: `tests/integration/test_git_real_repository.py`.
  - Se omite si `shutil.which("git")` no lo encuentra.
  - Entorno aislado:
    - `GIT_CONFIG_GLOBAL` apunta a un archivo vacío de `tmp_path`, con `GIT_CONFIG_NOSYSTEM=1`;
    - `HOME` y `USERPROFILE` apuntan a `tmp_path/home`;
    - `GIT_AUTHOR_*` y `GIT_COMMITTER_*` llevan valores de prueba;
    - `GIT_TERMINAL_PROMPT=0` y `GIT_OPTIONAL_LOCKS=0` (que `status` no reescriba el índice).
  - La preparación (`init`, `add`, `commit`) se hace con `subprocess` y ese entorno.
  - Las lecturas (`status`, `diff`, `log`) pasan por `compose()` con el shell real y el mismo entorno, sin aprobador: deben ejecutarse porque la política las permite.
  - El estado se compara antes y después con:
    - el contenido de `.git/HEAD` y de los archivos bajo `.git/refs`, leídos con Python;
    - la salida de `git status --porcelain` y de `git diff --cached`;
    - la huella de los archivos del árbol de trabajo.
  - Un `git log` largo (muchos commits creados en la preparación) llega recortado con la marca.
  - **Nunca** se ejecuta un comando que se pregunte o deniegue.
- **Rationale**: es la decisión Sp2-45 del revisor, con solo `init`, `add`, `commit`, `status`, `diff` y `log`.

## R10. Lo que no cambia

No cambian `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/permissions/{policy,protected,exact_calls,approvals,rules,command_parser,command_rules,command_policy}.py`, `adapters/system/protected_paths.py`, `config.py`, `cli/` ni `tests/doubles/`. Las pruebas de HU-05-02 y HU-11-03 no cambian sus aserciones (SC-006).
