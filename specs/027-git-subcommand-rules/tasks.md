# Tasks: HU-11-02 — Git mediante el shell con reglas de permisos por subcomando

**Input**: `specs/027-git-subcommand-rules/` (spec.md con Clarifications, plan.md, research.md R1–R10, data-model.md, contracts/git_policy_contract.md, quickstart.md)
**Rama**: `gustavo` (sin commit, push ni cambio de rama por parte de Claude)
**Responsable**: B — Estado | **PHU**: 1 | **Sprint**: 2
**Tareas de referencia**: Sp2-43, Sp2-44, Sp2-45

## Cómo leer este documento

- **Regla RITMO**: 1 PHU → 8 tareas de implementación de ≤ 40 min (T002–T009), agrupadas por módulo. Aparte van solo el inicio (T001), el cierre (T010) y las humanas (H1–H5). Como la historia tiene menos de 3 PHU, no hay `/speckit-analyze`.
- **TDD dentro de cada tarea**:
  1. escribir las pruebas;
  2. ejecutarlas y ver el **rojo por la razón esperada** (anotarlo en la evidencia);
  3. implementar lo mínimo;
  4. pasar `ruff format --check .`, `ruff check .`, `mypy src tests` y las pruebas del módulo con cobertura.
- **Formato**: `- [ ] Tnnn [P?] [USn?] descripción con ruta`.
  - US1: lecturas permitidas.
  - US2: escritura que pregunta y destructivos que se deniegan.
  - US3: ninguna otra regla suelta un push o un merge, más `.git` y credenciales.
  - US4: instrucciones de git en el prefijo.
- **Ajuste al plan (revisor)**: la tabla de subcomandos va en su propio módulo de **datos**, `core/permissions/git_table.py`, separado del clasificador y la política (`core/permissions/git_rules.py`), para que el PO la revise sin leer código.
- **Seguridad de las pruebas**:
  - ningún comando que la política pregunte o deniegue se ejecuta jamás; se prueba contra la política o con un shell doble que registra;
  - git real solo en T008, con un ayudante que solo acepta `init`, `add`, `commit`, `status`, `diff` y `log`;
  - no se escriben asignaciones con forma de clave ni URLs con credenciales reales: se usan constantes y ejemplos obviamente falsos (`usuario-de-prueba`, `secreto-de-prueba`) construidos por partes si hace falta.
- **Archivos protegidos** (diff vacío al cerrar): `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `core/permissions/{policy,protected,exact_calls,approvals,rules,command_parser,command_rules,command_policy}.py`, `adapters/system/protected_paths.py`, `config.py`, `cli/`, `tests/doubles/`, `docs/archivo/`.
- **Archivos existentes que se tocan**:
  - `core/permissions/__init__.py`, `core/__init__.py`, `adapters/tools/shell.py`, `bootstrap.py`;
  - `docs/PROGRESO.md`, `CLAUDE.md` y las skills (dos copias);
  - solo el **número** de las cinco aserciones `len(…history_prefix) == N` de `tests/unit/test_bootstrap_shell.py` (líneas 166, 202 y 237) y `tests/unit/test_bootstrap_task_commands.py` (líneas 230 y 244), que se declara en PROGRESO.

## Mapeo a tareas del sprint

| Tarea | Descripción (03-plan-sprints) | Presupuesto | Tareas aquí |
|---|---|---|---|
| **Sp2-43** | Reglas de permisos por subcomando de git | 90 min | T002 (25), T003 (40), T004 (40), T005 (30) = 135 |
| **Sp2-44** | Instrucciones de uso de git en el prefijo | 60 min | T006 (35) = 35 |
| **Sp2-45** | Pruebas sobre un repositorio temporal | 90 min | T007 (40), T008 (35) = 75 |
| — | Inicio, fronteras/documentación y cierre | — | T001 (10), T009 (20), T010 (30) = 60 |

**Total de Claude: 305 min** frente a 240 min presupuestados. El presupuesto es un aviso, no un límite.

---

## Phase 1: Inicio

- [x] T001 Inicio (10 min) en `docs/PROGRESO.md` (CRLF puro, una fila por línea, sin tocar la tabla *Resumen*):
  - la fila **existente** de HU-11-02 pasa de `Pendiente` a `En curso`. Responsable B; se anota que la implementa Claude en la rama `gustavo`;
  - una línea en *Registro de cambios*;
  - un bloque nuevo **Observaciones de HU-11-02** con la spec 027 y las decisiones Q1, Q2, Q3, Sp2-45, `.git` y credenciales.

  Comprobar que `.specify/feature.json` apunta a `specs/027-git-subcommand-rules`.

  **Hecho cuando**: solo cambia esa fila y se añaden líneas; el archivo sigue en CRLF.

---

## Phase 2: Tabla de datos (US1, US2 · Sp2-43)

- [x] T002 [US1] [US2] Tabla de subcomandos como dato (25 min).

  Pruebas primero en `tests/unit/core/permissions/test_git_table.py`:
  - **contenido**: las lecturas de Q1 (`status`, `diff`, `log`, `show`, `blame`, `shortlog`, `describe`, `rev-parse`, `ls-files`, `grep`), las opciones de listar de `branch` y `tag`, las opciones de efecto (`--output`, `--ext-diff`, `--textconv`, `--no-index`, más `-O`/`--open-files-in-pager` de `grep`), las destructivas largas y cortas por subcomando de research R4, los subcomandos siempre destructivos (`clean`, `filter-branch`), las globales conocidas con valor y sin valor, y las globales arriesgadas;
  - **coherencia**: ningún subcomando o combinación denegada aparece en las listas de lectura ni en las de listar; las listas no tienen duplicados;
  - **inmutabilidad**: los valores son `frozenset`, `tuple` o `MappingProxyType` (asignar o mutar lanza `TypeError`/`AttributeError`);
  - **sin lógica**: una comprobación `ast` del propio archivo: solo docstring, `from __future__`, imports de `types` y asignaciones a nivel de módulo; ningún `def`, `class`, `lambda`, `if`, `for` ni comprensión.

  Rojo esperado: `ModuleNotFoundError` de `git_table`. Implementar `src/harness_agent/core/permissions/git_table.py` (solo datos, con un comentario por bloque para el PO).

  **Hecho cuando**: las pruebas pasan y el módulo está al 100 %.

---

## Phase 3: Clasificador y política (US1, US2, US3 · Sp2-43)

- [x] T003 [US1] [US2] `classify_git` (40 min). Depende de T002.

  Pruebas primero, por tabla, en `tests/unit/core/permissions/test_git_rules.py`, para `Dialect.BASH` y `Dialect.POWERSHELL`, sobre partes obtenidas con `parse_command`:
  - **lecturas**: todos los `READ` del contrato; ruta completa (`/usr/bin/git`, `C:\Program Files\Git\bin\git.exe`), `git.exe`, `-C sub`, `--no-pager`, `--git-dir=.git --work-tree=.`; `branch`/`tag`/`stash list` cuando listan;
  - **opciones globales**: `-c k=v`, `--config-env`, `--exec-path`, `--namespace`, una desconocida → `ASK`; sin subcomando (`git`, `git --version`) → `ASK`;
  - **lecturas con efectos**: `--output`, `--ext-diff`, `--textconv`, `--no-index` y sus prefijos (`--out`, `--ext`); `grep -O`; una redirección; `risky_environment=True` → `ASK`;
  - **escrituras**: `commit`, `push`, `merge`, `add`, `switch -c`, `checkout -b`, `branch nueva`, `tag v1`, `rebase`, `cherry-pick`, `revert`, `reset HEAD~1`, `branch -d`, `restore --staged`, `stash push`, `stash show`, un alias (`st`), uno desconocido → `ASK`;
  - **destructivas**: todas las de research R4 y del contrato:
    - prefijos de opciones largas (`--forc`, `--force-w`, `--ha`, `--for`; prefijo ambiguo de una denegada → `DENY`);
    - opciones cortas agrupadas (`clean -fd`, `clean -n`, `push -fu`, `branch -Df`, `checkout -qf`);
    - `+refspec` y `:refspec` (`origin +main`, `+HEAD:main`, `main +dev`, `origin :rama`);
    - `checkout -- a.py`, `checkout .`, `restore a.py`, `restore --worktree a.py`, `switch --discard-changes`, `reset --keep`/`--merge`, `branch -d -f x`, `stash drop`/`clear`, `push --delete`, `push --mirror`, `reflog expire`, `gc --prune=now`, `gc --prune now`, `filter-branch`, `update-ref -d`;
  - **reglas de orden**: `risky_environment` nunca baja un `DENY`; las opciones de git distinguen mayúsculas (`git STATUS` → `ASK`; `push -F`, que no existe, → `ASK`, no `DENY`);
  - **errores**: una parte que no es git → `ValueError` con mensaje fijo.

  Rojo esperado: `ImportError` de `classify_git`. Implementar `classify_git` y `GitClass` en `src/harness_agent/core/permissions/git_rules.py`, leyendo **solo** de `git_table.py`.

  **Hecho cuando**: todas las tablas pasan en los dos dialectos y `classify_git` está al 100 %.

- [x] T004 [US2] [US3] `GitPolicy`, propiedades al azar y guarda (40 min). Depende de T003.

  Pruebas primero en `tests/unit/core/permissions/test_git_policy.py`, con `ScriptedPolicy` como `inner` y en los dos dialectos:
  - **todos los ejemplos normativos** de `contracts/git_policy_contract.md` (con `inner = ASK` y, para los que deben preguntar, también con `inner = ALLOW`, que nunca debe salir);
  - **encadenados mixtos**: `git status && git diff` → `ALLOW`; `git status && rm x` → delega (aquí `ASK`; nunca `ALLOW` por la parte git); `git status && git push` → `ASK`; `git status && git reset --hard` → `DENY`; `git log | head` → delega;
  - **git dentro de otro texto**: `bash -c "git push --force"` y `echo $(git clean -fd)` → `DENY`; `bash -c "git status"` → no `ALLOW`;
  - **`GIT_*` delante**: `GIT_EXTERNAL_DIFF=x git diff` y `env GIT_SSH_COMMAND=x git status` → `ASK`;
  - **comandos sin git** → delega sin cambios (se comprueba con `ScriptedPolicy.received`);
  - **`ASK` de git sin consultar a `inner`** (`received` vacío);
  - **falla cerrada**: excepción al analizar → `ASK`; `inner` que lanza o devuelve un valor raro → `DENY`; llamada mal formada → `DENY`;
  - **otras propiedades**: sin estado entre llamadas; ninguna decisión ni error reproduce el centinela `VALOR-DE-PRUEBA-123`; otra herramienta → `inner`;
  - **constructor**: tipos validados.

  Propiedades en `tests/unit/core/permissions/test_git_properties.py`, solo con la biblioteca estándar: `random.Random(20261027)` y unas 2 000 entradas por intérprete y propiedad, en pocos segundos:
  1. `classify_git` (sobre las partes git de `parse_command`) y `GitPolicy.evaluate` **nunca lanzan**. El generador usa argumentos de git al azar, opciones raras, comillas sin cerrar, caracteres de control y textos largos.
  2. Un comando con una variante destructiva escondida (encadenada con un separador al azar, en `$( … )`, en `bash -c '…'` o `pwsh -Command "…"`, con opciones globales al azar delante) **nunca** sale `ALLOW`, ni con `inner = ALLOW`, y sale `DENY` cuando se puede analizar.

     Lleva una metaprueba: un mutante que no mira `executable` deja escapar casos.

  Guarda nueva `tests/architecture/test_git_rules_boundaries.py` para `git_table.py`, `git_rules.py` y `core/redaction.py`:
  - solo biblioteca estándar y núcleo, sin `adapters`, `config`, `cli`, `os`, `subprocess`, `shlex`, `sys`;
  - sin lectura de configuración ni terminal;
  - sin `"shell"`, `"command"` ni `"timeout_seconds"`;
  - sin estado fuera de `__init__`;
  - en `git_rules.py`, un único `PermissionDecision.ALLOW`, dentro de `if self._only_reads(…) is True:`, y todo `except` devuelve `ASK` o `DENY`;
  - en `git_table.py`, ninguna función ni clase.

  Reutiliza `forbidden_imports`, `io_stdlib_imports`, `find_config_reads`, `terminal_uses` y `stateful_methods`. Lleva autoprueba y mutación sobre una copia. Esta guarda espera `core/redaction.py`, que llega en T005: hasta entonces su parte de `redaction` se omite con un `skipif` y el motivo.

  Rojo esperado: `ImportError` de `GitPolicy`; la metaprueba confirma que la propiedad 2 tiene dientes. Implementar `GitPolicy` y `git_instructions()` en `src/harness_agent/core/permissions/git_rules.py` y exportar `GitClass`, `GitPolicy`, `classify_git` y `git_instructions` en `src/harness_agent/core/permissions/__init__.py` y `src/harness_agent/core/__init__.py`.

  **Hecho cuando**: `git_rules.py` al 100 %, las propiedades sin hallazgos (o con hallazgos corregidos **en el clasificador**, sin relajar la propiedad) y `pytest tests/architecture` en verde.

---

## Phase 4: Credenciales en URLs (US3 · Sp2-43)

- [x] T005 [P] [US3] `core/redaction.py` y su uso en `ShellTool` (30 min). Puede ir en paralelo con T003 y T004.

  Pruebas primero:
  - `tests/unit/core/test_redaction.py` comprueba los cuatro casos del contrato:
    - `esquema://usuario:secreto@host` → `esquema://<secreto oculto>@host`;
    - solo token → igual;
    - URL sin credenciales → sin cambios;
    - texto sin URL → sin cambios.

    Y además: varias URLs en una línea; esquemas `http`, `https`, `ssh` y `git+ssh`; un correo sin esquema (`a@b.c`) sin cambios; idempotencia; `TypeError` si no es texto; `HIDDEN_SECRET == "<secreto oculto>"`. Los secretos de prueba se construyen por partes (por ejemplo `"secreto" + "-de-prueba"`) para no dejar literales con forma de clave.
  - `tests/unit/adapters/tools/test_shell_redaction.py` usa un `Shell` doble cuya salida contiene una URL con credenciales en las tres ramas de `ShellTool.run` (código 0, código ≠ 0, tiempo agotado). El `ToolResult.content` no contiene ni el usuario ni el secreto y sí contiene `<secreto oculto>`.
  - Con el bucle real y `RecordingEventBus`, ningún evento publicado tras esa llamada contiene el secreto. Hoy ningún evento lleva la salida; la prueba fija que siga así o que, si la llevara, vaya oculta.

  Rojo esperado: `ImportError` de `hide_url_credentials` y, tras crear la función, el secreto aún en el `ToolResult`. Implementar `src/harness_agent/core/redaction.py` (`HIDDEN_SECRET`, `hide_url_credentials`; docstring que nombra HU-10-02 como quien debe absorberla), exportar en `src/harness_agent/core/__init__.py` y aplicarla en `src/harness_agent/adapters/tools/shell.py` a la salida, antes de construir el mensaje, en las tres ramas.

  **Hecho cuando**: `redaction.py` y `shell.py` al 100 %, y la guarda de T004 ya cubre `redaction.py` (se quita el `skipif`).

---

## Phase 5: Composición (US3, US4 · Sp2-44)

- [x] T006 [US4] `bootstrap.py`: cadena, `.git` como dato e instrucciones en el prefijo (35 min). Depende de T004 y T005.

  Pruebas primero en `tests/unit/test_bootstrap_git.py`, con `compose()`, `FakeProvider` y la base de datos en `tmp_path`:
  - **sin área** (sin shell, nada se ejecuta), por comportamiento a través del bucle: `git status` → se ejecutaría (aquí `[sin_area]` del shell, no `[approval_required_unavailable]`); `git push` → `[approval_required_unavailable]`; `git reset --hard` → `[permission_denied]`;
  - **con área**, con un shell doble (`monkeypatch` de `bootstrap.select_shell`): `leer_archivo .git/HEAD` y `escribir_archivo .git/config` → `[permission_denied]`; `git status` → se ejecuta en el doble; `cat .gitignore` por el shell no se deniega (`.git` no es marcador);
  - **prefijo**: con área, aviso de entorno → `git_instructions()` → comandos de la tarea (si los hay); sin área, sin el mensaje de git;
  - **orden de la cadena**: un denegado de la lista base sigue denegado; la zona protegida gana; la lista `ask` con `git status` → se pregunta.

  Rojo esperado: `git status` termina en `[approval_required_unavailable]`, `.git` se puede leer y no está el mensaje. Implementar en `src/harness_agent/bootstrap.py`:
  - `GitPolicy` entre `CommandPolicy` y `ExactCallPolicy`, con `dialect=deny_list.dialect`, `tool=shell_tool.name` y `argument=COMMAND_ARGUMENT`;
  - `_protection` añade `workspace / ".git"` a las carpetas protegidas cuando hay área;
  - `history_prefix` añade `git_instructions()` cuando hay área.

  Después cambiar **solo el número** de las cinco aserciones `len(…history_prefix)` de `tests/unit/test_bootstrap_shell.py` y `tests/unit/test_bootstrap_task_commands.py`, y anotar cuáles y por qué.

  **Hecho cuando**: `tests/unit/test_bootstrap_*.py` y `tests/architecture/test_bootstrap_boundaries.py` en verde, y `bootstrap.py` al 100 %.

---

## Phase 6: Integración y repositorio real (US1, US2, US3 · Sp2-43, Sp2-45)

- [x] T007 [US3] Integración con el bucle real y un shell doble (40 min). Depende de T006.

  Pruebas en `tests/integration/test_git_policy_agent_loop.py`, con `compose()` real y `select_shell` sustituido por un doble que registra y nunca ejecuta, en `Linux` y `Windows`:
  - **AC-01**: `git status`, `git diff` y `git log` se ejecutan en el doble sin aprobador, y una salida larga del doble vuelve recortada con la marca.
  - **AC-02**: `git commit`, `git push` y `git merge` → se pregunta; `git reset --hard`, `git clean -fd` y `git push --force` → `[permission_denied]`, y el doble no los recibe.
  - **HU-11-03**: una tarea que declara `- pruebas: git push origin main`. El texto exacto → se pregunta (con aprobador, el aprobador recibe la pregunta; sin él, `[approval_required_unavailable]`).
  - **Aprobación de sesión**, con un aprobador de prueba «aprobar para la sesión» que cuenta:
    1. `git commit -m x` aprobado para la sesión;
    2. `git push` → nueva pregunta;
    3. el mismo `git push` repetido → no pregunta (supuesto Q3);
    4. `git push --force` → `[permission_denied]` y el aprobador no lo recibe.
  - **Zona protegida y listas**: `echo sesiones.db` → denegado; `[permissions] ask = ["shell"]` con `git status` → se pregunta; `deny = ["shell"]` → denegado.
  - **`.git`**: leer y escribir `.git/…` con las herramientas de archivos → denegado; `git status` permitido en la misma sesión.
  - **Credenciales**: el doble devuelve una salida con una URL con credenciales de prueba; el mensaje de herramienta del historial no las contiene; ningún evento contiene el comando ni el secreto.

  Rojo esperado: con `GitPolicy` retirada temporalmente de `bootstrap.py` (`git stash` solo de ese archivo, y restaurarlo), las lecturas terminan preguntadas y el push declarado depende solo de `ExactCallPolicy`. Anotar el número de fallos.

  **Hecho cuando**: todo en verde en Windows; el doble nunca recibe un comando denegado ni uno preguntado sin aprobación.

- [x] T008 [P] [US1] Repositorio temporal con git real (Sp2-45, FR-014) (35 min). Depende de T006; puede ir en paralelo con T007.

  Pruebas en `tests/integration/test_git_real_repository.py`:
  - se omite con su motivo si `shutil.which("git")` es `None`;
  - **ayudante `run_git(repo, *args)`**: solo acepta `init`, `add`, `commit`, `status`, `diff` y `log` como primer argumento; cualquier otro (`push`, `reset`, `clean`, `checkout`, `config`, un alias…) lanza `ValueError` **sin ejecutar nada**, y una prueba lo comprueba;
  - **entorno aislado**:
    - `GIT_CONFIG_GLOBAL` apunta a un archivo vacío en `tmp_path`, con `GIT_CONFIG_NOSYSTEM=1`;
    - `HOME` y `USERPROFILE` apuntan a `tmp_path/home`;
    - `GIT_AUTHOR_*` y `GIT_COMMITTER_*` llevan valores de prueba;
    - `GIT_TERMINAL_PROMPT=0` y `GIT_OPTIONAL_LOCKS=0`;
    - `PATH` heredado;
  - **preparación** (solo con el ayudante): `init`, un archivo, `add`, `commit` y unos 300 commits pequeños para un `log` largo, más un cambio sin confirmar para `diff`;
  - **lecturas por la composición real**, con el shell nativo, el mismo entorno (`compose(environ=…)`) y sin aprobador: `git status`, `git diff` y `git log` se ejecutan (no terminan en `[approval_required_unavailable]`);
  - **el estado no cambia**: se comparan antes y después el contenido de `.git/HEAD`, los archivos bajo `.git/refs` (leídos con Python), la salida de `run_git(repo, "status", "--porcelain")` y `run_git(repo, "diff", "--cached")`, y la huella de los archivos del árbol de trabajo;
  - **recorte**: el `git log` largo llega con `[salida recortada: se omitieron` y sin superar el máximo;
  - **un comando preguntado no se ejecuta**: en la misma composición, `git commit -m x` pedido por el modelo termina en `[approval_required_unavailable]` y el número de commits no cambia.

  Rojo esperado: sin `GitPolicy` en la composición (misma técnica que T007), las lecturas terminan preguntadas y no se ejecutan.

  **Hecho cuando**: pasa en Windows con git instalado; en Linux, en la CI (H5).

---

## Phase 7: Fronteras, documentación y cierre

- [x] T009 Verificación de fronteras y documentación (20 min). Depende de T008.
  - `pytest tests/architecture -q`: anotar el resultado (pasadas, guarda nueva, ningún archivo viola una regla).
  - Añadir `test_git_rules_boundaries.py` a la tabla de guardas de `verificar-fronteras-hexagonales/SKILL.md` en `.claude/skills/` y `.agents/skills/` (copias idénticas).
  - Añadir `git_table.py`, `git_rules.py` y `core/redaction.py` a `estructura-carpetas-harness/references/arbol.md` (dos copias), anotando que `core/redaction.py` es provisional hasta HU-10-02 / `observability/`.
  - En `CLAUDE.md`: una fila de HU-11-02 en «Qué existe hoy» y la cadena de políticas actualizada en las convenciones.
  - Revisar contra el código la lista de comprobación de `capas-y-reglas.md` del `plan.md` y anotar cualquier «no».
  - Aplicar `secret_patterns_in` del detector de secretos a **todos** los archivos nuevos y modificados, no versionados incluidos.

  **Hecho cuando**: guardas en verde, copias de las skills idénticas (`diff -q`) y el detector sin hallazgos.

- [x] T010 Cierre (30 min). Depende de T009.
  - Ejecutar las cuatro puertas: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`, todas en exit 0. Anotar los conteos reales y el 100 % en `git_table.py`, `git_rules.py`, `redaction.py`, `shell.py` y `bootstrap.py`. También `pytest tests/architecture`.
  - Comprobar `git diff --exit-code $(git merge-base HEAD origin/main) -- <archivos protegidos de arriba>` → 0.
  - Repetir el detector de secretos sobre lo nuevo y lo modificado, PROGRESO incluido, **después** de escribirlo. No escribir en PROGRESO ni en pruebas asignaciones con forma de clave ni URLs con credenciales: describirlas con palabras.
  - En `docs/PROGRESO.md` (CRLF puro, una fila por línea, sin reescribir filas ajenas ni la tabla *Resumen*):
    - la fila de HU-11-02 pasa a **`En revisión`** (nunca `Hecha`), con *Archivos* y *Evidencia* reales;
    - una línea por tarea en *Registro de cambios*;
    - en **Observaciones de HU-11-02**:
      1. Q1, Q2 y Q3;
      2. el **supuesto de Q3 pendiente del PO**;
      3. `.git` protegida solo en la raíz del área y tampoco legible con las herramientas de archivos;
      4. **HU-10-02 debe absorber `core/redaction.py::hide_url_credentials`**;
      5. detección de `GIT_*` sobre el texto crudo;
      6. las cinco aserciones de `history_prefix` cambiadas solo en el número;
      7. la nota para HU-02-01 (conservar el mensaje de git del prefijo);
      8. la nota de proceso con los rojos observados;
      9. lo pendiente (H1–H5).
  - Marcar en este archivo solo T001–T010 con su evidencia (tabla al final); H1–H5 quedan sin marcar.

  **Hecho cuando**: las cuatro puertas en verde, el diff de protegidos vacío, el detector sin hallazgos y PROGRESO en CRLF con la fila en `En revisión`.

---

## Phase 8: Tareas humanas (Claude no las marca)

- [ ] H1 **Revisión cruzada** por alguien de otra área, A o C (la historia es de B).
- [ ] H2 El **PO revisa** la tabla de subcomandos (`core/permissions/git_table.py`: lecturas, destructivas) y el **supuesto de Q3** (reutilizar la aprobación de sesión de un push o merge idénticos).
- [ ] H3 **Visto bueno de C** a las piezas suyas que se tocan: `core/permissions/` (nuevo `git_rules.py` y `git_table.py` en el paquete de C), `adapters/tools/shell.py` (ocultado de credenciales) y la protección de `.git` en la composición.
- [ ] H4 **Avisar al responsable de HU-10-02** de que debe absorber `core/redaction.py::hide_url_credentials`.
- [ ] H5 **CI remota** en verde en `ubuntu-latest` (bash real; `test_git_real_repository.py` con git) y `windows-latest`, con push y PR confirmados por una persona.

---

## Dependencias y orden

```text
T001 ─▶ T002 ─▶ T003 ─▶ T004 ─┐
        T005 [P] ─────────────┴─▶ T006 ─┬─▶ T007 ─┐
                                        └─▶ T008 [P] ─┴─▶ T009 ─▶ T010 ─▶ (H1–H5)
```

- T005 (`redaction.py` y `shell.py`) no depende de las reglas de git y puede ir en paralelo con T003 y T004.
- T007 y T008 tocan archivos de prueba distintos y pueden ir en paralelo tras T006.
- **US1** (lecturas permitidas) queda probada en T003 y T004 (núcleo), T007 (shell doble) y T008 (git real).
- **US2** (escritura y destructivos) en T003, T004 y T007.
- **US3** (nada suelta push o merge, `.git` y credenciales) en T004, T005, T006 y T007.
- **US4** (instrucciones en el prefijo) en T006.

## Ejemplo de paralelismo

```text
Agente 1: T002 → T003 → T004   (git_table.py, git_rules.py, propiedades, guarda)
Agente 2: T005                 (core/redaction.py + adapters/tools/shell.py)
Tras T006:
Agente 1: T007                 (integración con shell doble)
Agente 2: T008                 (git real en tmp_path)
```

## Estrategia de implementación

1. **MVP**: T001–T004 y T006. Las reglas de git en la cadena: lecturas permitidas, escrituras preguntadas y destructivos denegados.
2. **Incremento**: T005 (credenciales), T007 (convivencia completa) y T008 (Sp2-45 con git real).
3. **Cierre**: T009 y T010. Después, H1–H5 son humanas y la historia no pasa a `Hecha` hasta completarlas y ratificar HU-00-01.

## Evidencia (2026-10-27, Windows 11, Python 3.12, git 2.49, `.venv` con `requirements-dev.txt`)

| Tarea | Rojo observado | Verde |
|---|---|---|
| T001 | — | Fila de HU-11-02 a `En curso`, bloque de observaciones y registro en `docs/PROGRESO.md` (CRLF) |
| T002 | `ImportError` de `git_table` | `test_git_table.py`: 42 pasadas; `git_table.py` al 100 %, solo datos (comprobado con `ast`) |
| T003 | `ImportError` de `GitClass` | `test_git_rules.py`: 327 pasadas en bash y PowerShell; `classify_git` al 100 % |
| T004 | `ImportError` de `GitPolicy`; la metaprueba confirma que la propiedad detecta un mutante que ignora el texto que se ejecuta | `test_git_policy.py` con todos los ejemplos normativos; `test_git_properties.py` (semilla 20261027, 2 000 por intérprete y propiedad, ~7 s, sin hallazgos); guarda nueva en verde; `git_rules.py` al 100 % |
| T005 | `ImportError` de `HIDDEN_SECRET`; después, 4 fallos con el secreto en el `ToolResult` | `test_redaction.py` y `test_shell_redaction.py` (25 pasadas); `redaction.py` y `shell.py` al 100 %; la guarda cubre `redaction.py` |
| T006 | 5 fallos de composición (lecturas preguntadas, `.git` legible, sin mensaje) y 8 de las listas de herramientas | `test_bootstrap_git.py` (11) y suite completa en verde; `bootstrap.py` al 100 %. **Ajuste de diseño**: `GitPolicy` recibe `deny_names`/`ask_names` para no aflojar la lista `deny`. Ajustes solo numéricos declarados en las pruebas de prefijo |
| T007 | 15 de 18 fallos con `GitPolicy` retirada temporalmente (`git stash` solo de `bootstrap.py`, restaurado) | `test_git_policy_agent_loop.py`: 18 pasadas con shell doble; el doble nunca recibe un denegado ni un preguntado sin aprobación. Ajuste declarado en la tabla de encadenados de HU-05-02 |
| T008 | 2 fallos de lectura con la misma técnica | `test_git_real_repository.py`: 10 pasadas con git y PowerShell reales en `tmp_path`, entorno aislado y ayudante restringido; el estado no cambia; `log` recortado |
| T009 | — | `pytest tests/architecture` 460 pasadas; skills (copias idénticas) y `CLAUDE.md`; detector de secretos sin hallazgos en 37 archivos |
| T010 | — | Cuatro puertas en exit 0: 6097 pasadas, 47 omitidas (ninguna de esta historia); 792 pruebas nuevas; total 99 %; diff de protegidos vacío; PROGRESO a `En revisión` |

Ningún comando que la política pregunte o deniegue se ejecuta en las pruebas. bash y git reales en Linux quedan para la CI (H5).
