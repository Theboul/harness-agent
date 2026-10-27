# Tasks: HU-05-02 — Lista de denegados y análisis de comandos compuestos

**Input**: `specs/026-shell-deny-compound/` (spec.md con Clarifications, plan.md, research.md R1–R13, data-model.md, contracts/, quickstart.md)
**Rama**: `gustavo` (sin commit, push ni cambio de rama por parte de Claude)
**Responsable**: C — Control y conexiones | **PHU**: 2 | **Sprint**: 2
**Tareas de referencia**: Sp2-24, Sp2-25, Sp2-26, Sp2-27, Sp2-28

## Cómo leer este documento

- **Regla RITMO**: 2 PHU → 10 tareas de Claude de ≤ 40 min; de ellas, 9 de implementación agrupadas por módulo (T002–T010) y la de fronteras y documentación (T011). Aparte van solo el inicio (T001), el cierre (T012) y las humanas (H1–H4). Como la historia tiene menos de 3 PHU, no hay `/speckit-analyze`.
- **TDD dentro de cada tarea**:
  1. escribir las pruebas;
  2. ejecutarlas y ver el **rojo por la razón esperada** (anotarla en la evidencia);
  3. implementar lo mínimo;
  4. pasar `ruff format --check .`, `ruff check .`, `mypy src tests` y las pruebas del módulo con cobertura.
- **Formato**: `- [ ] Tnnn [P?] [USn?] descripción con ruta`. `[P]` = paralelizable (archivos distintos, sin dependencia pendiente). US1 = denegar aunque vaya encadenado; US2 = preguntar ante lo no entendido; US3 = lista base inalterable y aprobación de sesión.
- **Archivos protegidos** (diff vacío al cerrar): `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `core/permissions/{policy,protected,exact_calls,approvals,rules}.py`, `src/harness_agent/cli/`, `tests/doubles/`, `docs/archivo/`, `tests/unit/adapters/system/test_denied_commands.py`, `tests/architecture/test_permissions_boundaries.py`, `tests/unit/core/permissions/test_rules.py`.
- **Archivos existentes que se tocan**: `core/permissions/__init__.py`, `core/__init__.py`, `adapters/system/{denied_commands,__init__}.py`, `config.py` (aditivo, área B), `config.example.toml`, `bootstrap.py`, `docs/PROGRESO.md`, `CLAUDE.md`, las skills (`verificar-fronteras-hexagonales/SKILL.md` y `estructura-carpetas-harness/references/arbol.md`, dos copias). Solo se cambian **listas esperadas** en:
  - `tests/unit/adapters/tools/test_public_api.py` (`SYSTEM_API`, nombres nuevos de `adapters.system`);
  - `tests/unit/test_config_schema.py`, únicamente si fija los campos de `[permissions]` (hoy no lo hace; si sigue sin hacerlo, no se toca).
- **Centinela**: `VALOR-DE-PRUEBA-123` dentro de comandos denegados, para comprobar que ni eventos, ni mensajes, ni excepciones lo reproducen.

## Mapeo a tareas del sprint

| Tarea | Descripción (03-plan-sprints) | Presupuesto | Tareas aquí |
|---|---|---|---|
| **Sp2-24** | Definir la lista base por plataforma | 90 min | T004 (40), T007 (35), T008 (35) = 110 |
| **Sp2-25** | Aplicar la prioridad de denegación sobre cualquier aprobación | 60 min | T005 (40), T009 (35) = 75 |
| **Sp2-26** | Separar comandos encadenados y evaluar cada parte | 180 min | T002 (40), T003 (40) = 80 |
| **Sp2-27** | Preguntar ante lo que el analizador no entiende | 60 min | T006 (35) = 35 |
| **Sp2-28** | Pruebas con encadenamientos de ejemplo | 120 min | T010 (40) = 40 |
| — | Inicio, fronteras/documentación y cierre | — | T001 (10), T011 (20), T012 (30) = 60 |

**Total de Claude: 400 min** frente a 510 min presupuestados (Sp2-24 a Sp2-28). El presupuesto es un aviso: no se recorta alcance para cumplirlo.

---

## Phase 1: Inicio

- [x] T001 Inicio (10 min) en `docs/PROGRESO.md` (CRLF puro, una fila por línea, sin tocar la tabla *Resumen*):
  - la fila **existente** de HU-05-02 pasa de `Pendiente` a `En curso` (solo esa fila);
  - una línea en *Registro de cambios*;
  - un bloque nuevo **Observaciones de HU-05-02** con la spec 026, las decisiones Q1 y Q2 de clarify y la regla de coincidencia.

  Comprobar que `.specify/feature.json` apunta a `specs/026-shell-deny-compound`.

  **Hecho cuando**: `git diff docs/PROGRESO.md` solo cambia esa fila y añade líneas; el archivo sigue en CRLF.

---

## Phase 2: Analizador de comandos — `core/permissions/command_parser.py` (US1, US2 · Sp2-26, Sp2-27)

**Objetivo**: separar el comando en partes por dialecto y marcar lo que no se entiende, sin lanzar nunca.
**Prueba independiente**: `pytest tests/unit/core/permissions/test_command_parser.py -q` y 100 % de `command_parser.py`.

- [x] T002 [US1] Analizador I: comillas, separadores y partes (40 min).

  Pruebas primero, **por tabla**, en `tests/unit/core/permissions/test_command_parser.py`, para `Dialect.BASH` y `Dialect.POWERSHELL`:
  - **separadores**:
    - bash: `&&`, `||`, `;`, `|`, `|&`, `&` y salto de línea;
    - PowerShell: `;`, `|`, `&&`, `||` y salto de línea;
    - un `;` o un salto de línea al final es válido;
  - **comillas**:
    - bash: `'…'` literal, `"…"` con `\"`;
    - PowerShell: `'…'` con `''`, `"…"` con `` ` ``;
    - un separador dentro de comillas no separa;
    - los índices de los argumentos entre comillas quedan en `quoted`;
  - **opciones**: `-rf` → `{-r, -f}`; `--` termina las opciones; en PowerShell, en minúsculas;
  - **no entendido** (research R4): comilla sin cerrar, `\` al final de línea, partes vacías (`a ;; b`, `| b`, `a &&`), `#` al inicio de una palabra, `<# #>`, `(`, `)`, `{`, `}` fuera de comillas, here-documents `<<`/`<<<`, variables `$X`, `${X}`, `$env:X` (pero `~` y `~/x` sí se entienden).

  Rojo esperado: `ImportError` de `Dialect`/`parse_command`. Después implementar en `src/harness_agent/core/permissions/command_parser.py`:
  - `Dialect`, `CommandPart`, `ParsedCommand` y `parse_command(text, dialect, *, aliases={}, synonyms={})`;
  - recorrido por caracteres **sin `shlex`**;
  - ante cualquier texto, devuelve `understood=False` en lugar de lanzar; solo lanza `TypeError` con tipos indebidos.

  **Hecho cuando**: todas las tablas pasan y la cobertura del módulo, hasta aquí, cubre las ramas de T002.

- [x] T003 [US1] [US2] Analizador II: sustituciones, otros intérpretes, envoltorios, redirecciones y programa (40 min). Depende de T002.

  Pruebas primero, añadidas al mismo archivo:
  - **sustituciones** `$( … )` (anidadas y dentro de `"…"`) y `` ` … ` ``: van a `executable` con su propio análisis y dejan `understood=False`;
  - `<( … )` y `>( … )`: no entendido;
  - **otros intérpretes analizables**:
    - `bash|sh|zsh -c "…"`, analizado con BASH;
    - `pwsh|powershell -Command "…"` / `-c`, con POWERSHELL;
    - `cmd /c …`, separado solo por `&`, `&&`, `||`, `|`;
  - **no analizables**: `eval`, `source`, `.`, `xargs`, `-EncodedCommand`/`-enc`/`-e`, `Invoke-Expression`, `iex`, `Start-Process`, `Invoke-Command`, `& $x`;
  - **envoltorios**: `sudo` (con `-u X`, `-E`), `env VAR=x`, `env -i`, `nohup`, `time`, `nice -n 5`, `command`, `builtin`, `exec`, `VAR=x cmd`;
  - **programa**: sin carpeta (`/sbin/shutdown`, `C:\Windows\System32\shutdown.exe`) ni extensión (`.exe`, `.cmd`, `.bat`, `.com`, `.ps1`); en PowerShell, en minúsculas y con el alias resuelto (`ri` → `remove-item`, con una tabla de prueba);
  - **redirecciones** (bash `>`, `>>`, `<`, `2>`, `2>>`, `&>`, `>&`, `2>&1`; PowerShell `>`, `>>`, `2>`, `*>`, `3>`, `2>&1`): el destino va a `redirect_targets` y no a los argumentos; un destino que es una sustitución se analiza;
  - **profundidad** de anidamiento mayor que 8: no entendido.

  Rojo esperado: las nuevas aserciones fallan (los campos `executable` y `redirect_targets` vacíos, el programa sin normalizar). Implementar en `src/harness_agent/core/permissions/command_parser.py`.

  **Hecho cuando**: `command_parser.py` al 100 % de líneas y ramas.

---

## Phase 3: Reglas y lista en uso — `core/permissions/command_rules.py` (US1, US3 · Sp2-24)

- [x] T004 [US1] [US3] `compile_rule`, `CompiledRule`, `RuleKind`, `RuleError` y `DenyList` (40 min). Depende de T003.

  Pruebas primero, **por tabla**, en `tests/unit/core/permissions/test_command_rules.py`:
  - **los seis tipos de research R2**:
    - `shutdown` → PROGRAM;
    - `rm -rf /` → TARGET;
    - `dd if=` → PREFIX;
    - `reg delete` → SUBCOMMAND;
    - `> /dev/sd` → REDIRECT;
    - `:(){ :|:& };:` → LITERAL, solo con `allow_literal=True`;
  - **errores** (`RuleError` con mensaje fijo, que no contiene el patrón ni el centinela): patrón vacío; no entendido sin `allow_literal`; varias partes; TARGET sin objetivo completo;
  - **coincidencia por tipo**, que también cubre la tabla de la clarificación:
    - PROGRAM solo en la posición del programa: `shutdown now` sí; `cat shutdown.log` no; `mkfs.ext4` sí;
    - TARGET con objetivos completos (`/`, `/*`, `//`, `/.`, `~`, `~/`, `~/*`, `C:\`, `C:/`, `C:\*`, `c:`) frente a rutas (`/tmp/build`, `~/proyecto/dist`, `C:\proyecto`), con opciones en otro orden o combinadas (`-fr`, `-r -f`), sinónimos de bash (`--recursive --force`) y prefijos de PowerShell (`-rec`, `-r`, `-fo`), incluidos los ambiguos (desviación R7);
    - PREFIX: cualquier `dd` con un argumento que empiece por `if=`;
    - SUBCOMMAND: `reg delete …` sí; `reg query` no;
    - REDIRECT: `> /dev/sda1` sí; `> salida.txt` no;
    - LITERAL: el texto sin espacios lo contiene;
    - en bash se distinguen mayúsculas (`RM -rf /` no coincide con `rm`); en PowerShell no;
  - **`DenyList`**:
    - inmutable, sin ninguna operación para quitar entradas;
    - una base vacía → `ValueError`;
    - `rules == base + extra`;
    - `denies(parsed, raw)` busca en las partes, en `executable` (recursivo) y en `redirect_targets`, **no** en los argumentos con índice en `quoted` (FR-005a), y las reglas LITERAL en `raw`.

  Rojo esperado: `ImportError`. Implementar `src/harness_agent/core/permissions/command_rules.py`.

  **Hecho cuando**: 100 % de líneas y ramas del módulo.

---

## Phase 4: Política que endurece — `core/permissions/command_policy.py` (US1, US2, US3 · Sp2-25, Sp2-27)

- [x] T005 [US1] [US2] `CommandPolicy` con la tabla normativa (40 min). Depende de T004.

  Pruebas primero en `tests/unit/core/permissions/test_command_policy.py`, con `ScriptedPolicy` como `inner` y una `DenyList` construida en la prueba con los patrones de la base de HU-01-04 más los de los escenarios:
  1. **Todos los ejemplos normativos** de `contracts/command_policy_contract.md` (tabla parametrizada: dialecto, comando, resultado esperado con `inner = ASK`).
  2. **Todos los escenarios de la spec**:
     - US1, escenarios 1–9: denegados y falsos positivos, como `echo "no uses shutdown"`, `git commit -m "fix: shutdown limpio"`, `rm -rf ~/proyecto/dist`, `chmod -R 777 ./dist`, `Remove-Item -Recurse -Force C:\proyecto\dist`;
     - US2, escenarios 1–4: preguntar, incluido «declarado en la tarea» simulado con `inner = ALLOW`.
  3. **Encadenados**, uno por separador de cada dialecto, con el denegado al principio, en medio y al final.
  4. **La tabla de transiciones** de `data-model.md`:
     - otra herramienta → `inner` sin cambios;
     - argumento ausente o no texto → como mínimo `ASK`;
     - un denegado → `DENY` y `inner` **no** se consulta (`ScriptedPolicy.received` vacío);
     - `inner` `DENY`/`ASK`/`ALLOW` con entendido y no entendido;
     - `inner` lanza o devuelve un valor raro → `DENY`;
     - excepción del analizador (`DenyList` que lanza) → «no entendido».
  5. **Sin estado** entre llamadas, y ninguna excepción ni decisión reproduce el centinela.

  Rojo esperado: `ImportError`. Implementar `src/harness_agent/core/permissions/command_policy.py` y exportar todo lo público de T002–T005 en `src/harness_agent/core/permissions/__init__.py` y `src/harness_agent/core/__init__.py`.

  **Hecho cuando**: 100 % de `command_policy.py`, y las baterías SC-001 (≥ 40 encadenados con un denegado por dialecto), SC-002 (≥ 25 no entendidos por dialecto, nunca `ALLOW`) y SC-004 (≥ 20 habituales más los falsos positivos, nunca `DENY`) están contadas en la prueba.

- [x] T006 [US2] Prueba con entradas al azar y guarda de arquitectura (35 min). Depende de T005.

  **Propiedades** en `tests/unit/core/permissions/test_command_properties.py`, solo con la biblioteca estándar (`random.Random(20261026)`, sin dependencias nuevas, unas 2 000 entradas por dialecto y por propiedad, menos de 5 s):
  1. `parse_command` y `CommandPolicy.evaluate` **nunca lanzan** con ninguna entrada. El generador combina caracteres de control, comillas sin cerrar, separadores, `$(`, comillas invertidas, `{`, `#`, texto de hasta 20 000 caracteres y bytes no ASCII.
  2. Un comando que contiene una entrada de la lista en una **parte ejecutable** (generado combinando un comando inocente con un separador al azar, envuelto en `$( … )`, en comillas invertidas, en `bash -c "…"` o en `pwsh -Command "…"`, a una profundidad al azar de 1 a 3) **nunca** obtiene `ALLOW`, ni con `inner = ALLOW`. Además, el resultado es `DENY` siempre que la construcción se pueda analizar.

  **Guarda nueva** `tests/architecture/test_command_policy_boundaries.py`, con autoprueba sobre fragmentos sintéticos y mutación sobre una copia en `tmp_path`, para `command_parser.py`, `command_rules.py` y `command_policy.py`:
  - sin imports de `harness_agent.adapters`, `config`, `cli`, `bootstrap`, ni de `subprocess`, `socket`, `os`, `pathlib`, `shutil`, `shlex`, `http`, `urllib` o terceros (reutiliza `forbidden_imports` y `io_stdlib_imports`, y añade `os` y `shlex`);
  - sin lectura de configuración ni terminal (`find_config_reads`, `terminal_uses`);
  - sin los literales `"shell"`, `"command"` ni `"timeout_seconds"`;
  - en `command_policy.py`, `PermissionDecision.ALLOW` solo aparece dentro de una comparación (`is`/`is not`/`==`), nunca devuelto ni asignado;
  - sin métodos con estado (reutiliza `stateful_methods`).

  Rojo esperado:
  - la propiedad 2 se comprueba primero contra una `CommandPolicy` sin análisis de `executable` (mutación local en la prueba), y debe fallar;
  - la guarda se comprueba con su mutación.

  **Hecho cuando**: las dos propiedades y `pytest tests/architecture -q` están en verde, y `core/` sigue sin imports de terceros (`test_core_boundaries.py`).

---

## Phase 5: Datos de la plataforma, configuración y composición (US3 · Sp2-24, Sp2-25)

- [x] T007 [P] [US3] Ampliar la lista base y las dos tablas de datos (35 min). Depende de T004; puede ir en paralelo con T005 y T006.

  Pruebas primero en `tests/unit/adapters/system/test_denied_commands_compile.py`:
  - cada entrada de `denied_commands_for("bash")` y `denied_commands_for("powershell")` compila con `compile_rule` y su dialecto (con `allow_literal=True`); solo la bomba de procesos da `RuleKind.LITERAL`;
  - las entradas nuevas de research R12 están presentes y con motivo;
  - `program_aliases_for("powershell")` resuelve `rm`, `ri`, `del`, `erase`, `rd` y `rmdir` a `remove-item`;
  - `option_synonyms_for("bash")["rm"]` traduce `--recursive` y `--force`;
  - las tablas son de solo lectura (`MappingProxyType`), y un intérprete desconocido da tablas vacías;
  - ningún comando habitual de desarrollo de la batería SC-004 coincide con la base real.

  Rojo esperado: `ImportError` de `program_aliases_for`. Implementar en `src/harness_agent/adapters/system/denied_commands.py` (entradas nuevas, `PROGRAM_ALIASES`, `OPTION_SYNONYMS`, `program_aliases_for`, `option_synonyms_for`; docstring actualizado: la lista ya se aplica en HU-05-02) y exportar en `src/harness_agent/adapters/system/__init__.py`. Ajustar **solo** la lista esperada `SYSTEM_API` de `tests/unit/adapters/tools/test_public_api.py`.

  **Hecho cuando**: `tests/unit/adapters/system/test_denied_commands.py` pasa **sin cambios** y `denied_commands.py` está al 100 %.

- [x] T008 [P] [US3] `config.py`: `[permissions] deny_commands` (35 min). Puede ir en paralelo con T005–T007.

  Pruebas primero en `tests/unit/test_config_deny_commands.py`, con las reglas 1–7 de `contracts/deny_commands_config_contract.md`:
  - ausente o `[]` → `()`;
  - una lista válida, con los duplicados descartados en orden;
  - valores no válidos (`"x"`, `[1]`, `[""]`, `["  "]`, un texto de 501 caracteres, un texto con `\n`) → `ConfigProblem("permissions.deny_commands", <mensaje fijo>)` sin el centinela;
  - `allow_commands`, `replace`, `base` y `deny_commands_base` → `campo desconocido en el esquema.` y el arranque se detiene (AC-01);
  - `config.permissions` sigue siendo `PermissionRules(deny, ask)`, sin el campo nuevo;
  - `config.example.toml` contiene `# deny_commands = []` comentado bajo `[permissions]` (prueba de plantilla).

  Rojo esperado: `deny_commands` es «campo desconocido» y `HarnessConfig` no tiene el atributo. Implementar en `src/harness_agent/config.py`: `_PERMISSION_FIELDS` admite el campo, la validación separada de `PermissionRules` y `HarnessConfig.deny_commands: tuple[str, ...] = ()`. Añadir las líneas comentadas en `config.example.toml`. Si `tests/unit/test_config_schema.py` o `tests/unit/test_config_templates.py` fijan la lista de campos, ajustar **solo** esa lista.

  **Hecho cuando**: `tests/unit/test_config_*.py` en verde y las líneas nuevas de `config.py` al 100 %.

- [x] T009 [US3] Compilar e inyectar en `bootstrap.py` (35 min). Depende de T005, T007 y T008.

  Pruebas primero en `tests/unit/test_bootstrap_deny_commands.py`, con `compose()`, `FakeProvider`, `environ` inyectado y la base de datos en `tmp_path`, como `tests/unit/test_bootstrap_task_commands.py`:
  - **orden de la cadena**: la política del bucle es `ProtectedPolicy` → `CommandPolicy` → `ExactCallPolicy` → `DefaultPermissionPolicy`. Se comprueba **por comportamiento**, no inspeccionando atributos privados:
    - un comando de la base da `[permission_denied]`;
    - un comando de `deny_commands` también;
  - **elección de la lista**: `system_name` decide el dialecto (`Windows` → powershell, `Linux` → bash): `Stop-Computer` se deniega con `Windows` y `shutdown now` con `Linux`;
  - **base intacta**: con `deny_commands = []` sigue denegando lo de la base;
  - **entrada no compilable**: un `deny_commands` con `$(x)` o `a && b` → `main()` devuelve 2 con la línea `No se pudo iniciar: una entrada de permissions.deny_commands no se entiende para …` (sin el texto ni el centinela) y el almacén se cierra;
  - **herramientas no afectadas**: las herramientas de archivos siguen decidiéndose como antes.

  Rojo esperado: el comando de la base se pregunta (`[approval_required_unavailable]`) en lugar de denegarse. Implementar en `src/harness_agent/bootstrap.py`:
  - `Dialect(interpreter_for(system))`;
  - compilar la base (`allow_literal=True`) y `config.deny_commands`, convirtiendo `RuleError` en `StartupError`;
  - `DenyList` y `CommandPolicy(inner=ExactCallPolicy(...), deny_list, tool=shell_tool.name, argument=COMMAND_ARGUMENT)` dentro de `ProtectedPolicy`.

  **Hecho cuando**: `tests/unit/test_bootstrap_*.py` y `tests/architecture/test_bootstrap_boundaries.py` en verde, y `bootstrap.py` al 100 %.

---

## Phase 6: Integración con el bucle real (US1, US2, US3 · Sp2-28)

- [x] T010 [US3] Composición completa, AC-02 con `ApprovalGate` real y HU-11-03 (40 min). Depende de T009.

  Pruebas en `tests/integration/test_command_policy_agent_loop.py`, con `compose(task=…, approver=<aprobador de prueba local que responde «aprobar para la sesión» y cuenta las preguntas>)`, el shell nativo y un `FakeProvider`:
  - **AC-02 (research R11)**:
    1. un comando inocente se pregunta una vez y se aprueba para la sesión;
    2. el mismo comando encadenado con un denegado (`; echo VALOR-DE-PRUEBA-123 > marcador.txt; <denegado>`) da `[permission_denied]`;
    3. el denegado solo, pedido dos veces, da `[permission_denied]` las dos veces;
    4. el comando del paso 1 repetido no vuelve a preguntar.

    El aprobador recibió **una** pregunta y el marcador no existe.
  - **Composición**:
    - con la zona protegida (`echo sesiones.db`): `[permission_denied]`;
    - con `[permissions] deny = ["shell"]`: denegado;
    - con `ask = ["shell"]` y sin aprobador: `[approval_required_unavailable]`;
    - con `ask = ["shell"]` y un comando denegado: `[permission_denied]` (gana la lista);
    - **HU-11-03**: un comando de `## Comandos` entendido y no denegado se ejecuta sin preguntar; uno declarado no entendido (`echo $(whoami)`) se pregunta; uno declarado que contiene un denegado se deniega.
  - **Sin filtrar datos**: ni los eventos (`PERMISSION_DECIDED`, `APPROVAL_*`) ni los mensajes de herramienta contienen el centinela ni el texto del comando denegado.
  - **Encadenados de ejemplo** (Sp2-28): una tabla de al menos 10 comandos reales por plataforma con `&&`, `||`, `;`, `|` y salto de línea, con su decisión esperada observada a través del bucle.
  - Se omite con motivo si falta el intérprete de la plataforma.

  Rojo esperado: con `CommandPolicy` retirada temporalmente de `bootstrap.py` (`git stash` solo de ese archivo, y restaurarlo), los denegados terminan en el aprobador o en `[approval_required_unavailable]`. Anotar el número de fallos.

  **Hecho cuando**: en verde con PowerShell real en Windows; bash real queda para la CI (H4).

---

## Phase 7: Fronteras, documentación y cierre

- [x] T011 Verificación de fronteras y documentación (20 min). Depende de T010.
  - `pytest tests/architecture -q`: anotar el número de pasadas, las guardas nuevas y que ningún archivo viola una regla.
  - Añadir `test_command_policy_boundaries.py` a la tabla de guardas de `.claude/skills/verificar-fronteras-hexagonales/SKILL.md` y `.agents/skills/…`.
  - Añadir `command_parser.py`, `command_rules.py` y `command_policy.py` a `references/arbol.md` de las dos copias de `estructura-carpetas-harness` (copias idénticas).
  - En `CLAUDE.md`: fila «Qué existe hoy» de HU-05-02 y la convención de la cadena de políticas; quitar «shell (HU-01-04)» de «Aún no hay», si sigue.
  - Revisar contra el código la lista de comprobación de `capas-y-reglas.md` de `plan.md` y anotar cualquier «no».
  - Aplicar `secret_patterns_in` del detector de secretos también a los archivos nuevos o no versionados.

  **Hecho cuando**: guardas en verde, las copias de las skills idénticas (`diff -q`) y el detector de secretos sin hallazgos.

- [x] T012 Cierre (30 min). Depende de T011.
  - Ejecutar las cuatro puertas: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`, todas en exit 0. Anotar los conteos reales y el 100 % de los tres módulos nuevos y de `denied_commands.py`, y de las líneas nuevas de `config.py` y `bootstrap.py`. También `pytest tests/architecture`.
  - Comprobar `git diff --exit-code $(git merge-base HEAD origin/main) -- <archivos protegidos de arriba>` → 0.
  - En `docs/PROGRESO.md` (CRLF puro, una fila por línea, sin reescribir filas ajenas ni la tabla *Resumen*):
    - la fila de HU-05-02 pasa a **`En revisión`** (nunca `Hecha`), con *Archivos* y *Evidencia* reales;
    - una línea por tarea en *Registro de cambios*;
    - en **Observaciones de HU-05-02**:
      1. decisiones Q1 (`deny_commands` solo añade; visto bueno de B) y Q2 (texto que se ejecuta frente a dato);
      2. la regla de coincidencia (una palabra solo como programa; objetivo solo raíz, `~` o unidad; `dd if=` conservador);
      3. la desviación de los parámetros abreviados de PowerShell (cualquier prefijo, para el PO);
      4. la bomba de procesos como regla `LITERAL`;
      5. para HU-11-02: puede añadir reglas de subcomando de git sobre `parse_command`;
      6. el motivo de la denegación no llega ni al modelo ni a la CLI (exige cambiar el puerto o el bucle);
      7. el contenido de la lista base, pendiente del PO;
      8. la nota de proceso con los rojos observados;
      9. lo pendiente (H1–H4).
  - Marcar en este archivo solo T001–T012 con su evidencia (tabla al final); H1–H4 quedan sin marcar.

  **Hecho cuando**: las cuatro puertas en verde, el diff de protegidos vacío y PROGRESO en CRLF con la fila en `En revisión`.

---

## Phase 8: Tareas humanas (Claude no las marca)

- [ ] H1 Visto bueno de **B** a la ampliación de `config.py` (`[permissions] deny_commands`, `HarnessConfig.deny_commands`) y de `config.example.toml` (`contracts/deny_commands_config_contract.md`).
- [ ] H2 **Revisión cruzada** del cambio por alguien de A o B (la historia es de C).
- [ ] H3 **Revisión del PO** del contenido de la lista base por plataforma (research R12) y de la desviación de las abreviaturas de PowerShell (research R7).
- [ ] H4 **CI remota** en verde en `ubuntu-latest` (con bash real: `test_command_policy_agent_loop.py`) y `windows-latest`, con push y PR confirmados por una persona.

---

## Dependencias y orden

```text
T001 ─▶ T002 ─▶ T003 ─▶ T004 ─┬─▶ T005 ─▶ T006 ─┐
                              ├─▶ T007 [P] ──────┤
        T008 [P] ────────────────────────────────┼─▶ T009 ─▶ T010 ─▶ T011 ─▶ T012 ─▶ (H1–H4)
```

- T007 (datos del adaptador) solo necesita `compile_rule` (T004). T008 (`config.py`) no depende del núcleo nuevo. Ambas pueden ir en paralelo con T005 y T006.
- **US1** (denegar aunque vaya encadenado) queda probada en el núcleo al terminar T005 y de extremo a extremo en T010.
- **US2** (preguntar ante lo no entendido) queda probada en T005 y T006 (propiedades) y con HU-11-03 en T010.
- **US3** (base inalterable, aprobación de sesión) queda probada en T008 y T009 (AC-01) y en T010 (AC-02).

## Ejemplo de paralelismo

```text
Agente 1: T005 → T006   (core/permissions/command_policy.py, propiedades, guarda)
Agente 2: T007          (adapters/system/denied_commands.py + test_denied_commands_compile.py)
Agente 3: T008          (config.py + config.example.toml + test_config_deny_commands.py)
```

Los tres tocan archivos distintos. T005 y T007 exportan en `__init__.py` diferentes (`core` y `adapters.system`).

## Estrategia de implementación

1. **MVP**: T001–T005 y T009 sin `deny_commands`. El núcleo deniega la base y pregunta lo no entendido, conectado en la composición.
2. **Incremento**:
   - T006: robustez y frontera;
   - T007: base ampliada;
   - T008: configuración aditiva;
   - T010: demostración de AC-02 y de la convivencia.
3. **Cierre**: T011 y T012. Después, H1–H4 son humanas y la historia no pasa a `Hecha` hasta completarlas y ratificar HU-00-01.

## Evidencia (2026-10-26, Windows 11, Python 3.12, `.venv` con `requirements-dev.txt`)

| Tarea | Rojo observado | Verde |
|---|---|---|
| T001 | — | Fila de HU-05-02 a `En curso`, bloque de observaciones y registro en `docs/PROGRESO.md` (CRLF) |
| T002 | `ImportError` de `CommandPart` | Separadores, comillas, opciones y no entendidos de los dos dialectos (100 pruebas) |
| T003 | 88 fallos (sin `executable`, programa y envoltorios sin normalizar, sin destinos de redirección) | `test_command_parser.py`: 242 pasadas; `command_parser.py` al 100 % de líneas y ramas |
| T004 | `ImportError` de `CompiledRule` | `test_command_rules.py`: 127 pasadas (61 casos de coincidencia); `command_rules.py` al 100 % |
| T005 | `ImportError` de `CommandPolicy` | `test_command_policy.py`: 369 pasadas, con todos los ejemplos normativos y las baterías SC-001 (96 y 70), SC-002 (27 y 27) y SC-004 (22 y 21); `command_policy.py` al 100 % |
| T006 | La metaprueba muestra que la propiedad 2 detecta un mutante que ignora el texto que se ejecuta | Propiedades con semilla 20261026 (2 000 entradas por intérprete y propiedad, ~5 s): sin hallazgos del analizador. Guarda nueva: 24 pasadas |
| T007 | `ImportError` de `option_synonyms_for` | Lista base de 20 (bash) y 15 (PowerShell) entradas que compilan; `test_denied_commands.py` sin cambios; `denied_commands.py` al 100 % |
| T008 | `deny_commands` era «campo desconocido» | `test_config_deny_commands.py` en verde; `config.py` al 100 % con toda la suite |
| T009 | 13 fallos (los denegados terminaban en `[approval_required_unavailable]`; una entrada no válida no detenía el arranque) | `test_bootstrap_deny_commands.py`: 18 pasadas, sin área (sin shell); `bootstrap.py` al 100 % |
| T010 | 9 fallos con `CommandPolicy` retirada temporalmente (`git stash` solo de `bootstrap.py`, restaurado) | `test_command_policy_agent_loop.py`: 12 pasadas con un shell doble que registra (el doble nunca recibe un comando denegado) |
| T011 | El detector de secretos encontró en una prueba nueva una variable de clave asignada a un texto literal | Corregido con una constante; 35 archivos sin hallazgos; `pytest tests/architecture` 445 pasadas; skills idénticas |
| T012 | — | Cuatro puertas en exit 0: 5305 pasadas, 47 omitidas (ninguna de esta historia), total 99 %; diff de protegidos vacío; PROGRESO a `En revisión` |

Ninguna prueba ejecuta un comando de la lista: se analizan, se evalúan contra la política o pasan por un shell doble. bash real queda para la CI de Linux (H4).
