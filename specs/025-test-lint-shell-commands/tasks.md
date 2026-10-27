# Tasks: HU-11-03 — Pruebas y lint mediante el shell con salida recortada

**Input**: `specs/025-test-lint-shell-commands/` (spec.md, plan.md, research.md, data-model.md, contracts/, quickstart.md)
**Rama**: `gustavo` (sin commit, push ni cambio de rama por parte de Claude)
**Responsable**: C — Control y conexiones | **PHU**: 1 | **Sprint**: 2
**Tareas de referencia**: Sp2-46, Sp2-47, Sp2-48

## Cómo leer este documento

- **Regla RITMO**: 1 PHU → 5 tareas de implementación de ≤ 40 min, agrupadas por módulo. Aparte van solo el inicio, el cierre y las tareas humanas. Como la historia tiene menos de 3 PHU, no hay `/speckit-analyze`.
- **TDD dentro de cada tarea**: primero se escribe la prueba, luego se ejecuta y se comprueba que falla **por la razón esperada** (anotarla), después se implementa lo mínimo y por último se pasan `ruff format --check .`, `ruff check .`, `mypy src tests` y las pruebas del módulo.
- **Formato**: `- [ ] Tnnn [P?] [USn?] descripción con ruta`. `[P]` = paralelizable (archivos distintos, sin dependencia pendiente).
- **Archivos protegidos** (diff vacío al cerrar): `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `core/permissions/policy.py`, `core/permissions/protected.py`, `src/harness_agent/cli/`, `src/harness_agent/config.py`, `tests/doubles/`, `docs/archivo/` y **`tests/unit/core/tasks/test_task_parser.py`** (la ampliación del analizador es aditiva).
- **Archivos existentes que se tocan**: `core/tasks/{definition,parser,errors,__init__}.py` (aditivo, código de A), `core/permissions/__init__.py`, `core/__init__.py`, `adapters/tools/{shell,__init__}.py` (dos constantes), `bootstrap.py`, `docs/PROGRESO.md`, `CLAUDE.md` y `arbol.md` de las dos copias de la skill. Si `tests/integration/test_core_public_api.py` fija la lista exacta de nombres públicos, se ajusta solo la lista esperada y se anota.
- **Rutas**: cada archivo nuevo sigue la tabla *Project Structure* de `plan.md` (fila de `estructura-carpetas-harness`).

## Mapeo a tareas del sprint

| Tarea | Descripción (03-plan-sprints) | Presupuesto | Tareas aquí |
|---|---|---|---|
| **Sp2-46** | Leer los comandos de pruebas y de lint de la configuración de la tarea | 90 min | T002 (40), T004 (30) = 70 |
| **Sp2-47** | Permitir en la política esos comandos exactos con tiempo máximo | 60 min | T003 (40) = 40 |
| **Sp2-48** | Prueba con un proyecto de ejemplo | 90 min | T005 (40) = 40 |
| — | Inicio, fronteras/documentación y cierre | — | T001 (10), T006 (20), T007 (30) = 60 |

Total: 210 min de Claude frente a 240 min presupuestados. El presupuesto es un aviso: no se recorta alcance para cumplirlo.

---

## Phase 1: Inicio

- [x] T001 Inicio (10 min) en `docs/PROGRESO.md`:
  - la fila de HU-11-03 pasa de `Pendiente` a `En curso` (editar solo esa fila, una fila por línea, CRLF puro, sin tocar la tabla *Resumen*);
  - una línea en *Registro de cambios*;
  - un bloque nuevo **Observaciones de HU-11-03** con la spec 025, las decisiones Q1–Q3 de `/speckit-clarify` y la nota «ampliación del formato de la tarea pendiente del visto bueno de A».

  Comprobar que `.specify/feature.json` apunta a `specs/025-test-lint-shell-commands`.

---

## Phase 2: Formato de la tarea — módulo `core/tasks/` (US1, US2 · Sp2-46)

**Objetivo**: la tarea declara `pruebas:`/`lint:` con un `tiempo:` opcional, y una tarea sin la sección no cambia.
**Prueba independiente**: `pytest tests/unit/core/tasks -q` pasa y `git diff` de `test_task_parser.py` está vacío.

- [x] T002 [US1] Comandos en la tarea, TDD (40 min). Pruebas primero en `tests/unit/core/tasks/test_task_commands.py`:
  - `TaskCommand` valida el texto (vacío, en blanco, más de 2 000 caracteres) y el tiempo (`bool`, 0, 601, por defecto 300), con mensajes fijos que no reproducen el centinela `VALOR-DE-PRUEBA-123`;
  - `TaskDefinition` sin `commands` es igual a la de HU-11-01 y rechaza dos comandos del mismo tipo;
  - `parse_task` lee `## Comandos` con `- pruebas:`, `- lint:` y la sublínea `- tiempo:`, con el nombre de sección sin distinguir mayúsculas, el orden del archivo y los espacios exteriores recortados;
  - `parse_task` rechaza con `comando_no_valido` todos los casos de `contracts/task_commands_format.md` §4, y con `seccion_repetida` una sección repetida;
  - una tarea sin la sección da `commands == ()`;
  - `commands_notice(())` es `None` y con comandos devuelve el texto con cada comando entre comillas invertidas y su tiempo;
  - el mensaje de `seccion_desconocida` nombra «Comandos».

  Rojo esperado: `ImportError` de `TaskCommand`/`commands_notice`. Después implementar:
  - `src/harness_agent/core/tasks/commands.py` (nuevo): `CommandKind`, `TaskCommand`, `DEFAULT_COMMAND_TIMEOUT_SECONDS = 300`, `MAX_COMMAND_TIMEOUT_SECONDS = 600` y `commands_notice`;
  - `src/harness_agent/core/tasks/definition.py`: campo `commands: tuple[TaskCommand, ...] = ()`, el último, y la regla de uno por tipo;
  - `src/harness_agent/core/tasks/parser.py`: alias `comandos` en `_SECTION_BY_NAME` y un lector de comandos con la forma de `_CriteriaReader`;
  - `src/harness_agent/core/tasks/errors.py`: código `comando_no_valido` y mensaje actualizado de `seccion_desconocida`;
  - exportar en `src/harness_agent/core/tasks/__init__.py` y `src/harness_agent/core/__init__.py`.

  Al terminar: `tests/unit/core/tasks` con el 100 % de líneas y ramas de `core/tasks/`, y `pytest tests/architecture/test_tasks_boundaries.py` en verde.

---

## Phase 3: Regla de permitir exacta — módulo `core/permissions/exact_calls.py` (US2 · Sp2-47)

**Objetivo**: solo la llamada exacta, con un tiempo ≤ al declarado, pasa de «preguntar» a «permitir»; deny > ask > allow.
**Prueba independiente**: `pytest tests/unit/core/permissions/test_exact_calls.py tests/architecture -q`.

- [x] T003 [P] [US2] `AllowedCall` y `ExactCallPolicy` con su guarda, TDD (40 min). Puede ir en paralelo con T002.

  Pruebas primero en `tests/unit/core/permissions/test_exact_calls.py`, con `ScriptedPolicy` de `tests/doubles/` como política envuelta y `ToolCall` sintéticas con nombres de herramienta y argumentos inventados (no `shell`):
  - **validación del constructor** de `AllowedCall`: texto vacío, `limit`/`default_limit` `bool`, ≤ 0 o no finitos, y `limit_argument == argument`;
  - **tabla de transiciones** de `data-model.md`: `DENY` y `ALLOW` pasan tal cual; `ASK` con la herramienta en `ask_names` se queda en `ASK`; `ASK` con coincidencia pasa a `ALLOW`; un valor raro o una excepción de `inner` da `DENY`;
  - **batería de ≥ 15 variaciones** que no deben coincidir (SC-002): `&& x`, `; x`, `| x`, `\n x`, un argumento extra, otro nombre de herramienta, mayúsculas, comillas añadidas, espacios internos dobles, tiempo mayor, tiempo `True`, `nan`/`inf`, 0 y negativo, argumento no `str`, `arguments` que no es `dict`;
  - **casos que sí coinciden**: espacios exteriores y llamada sin tiempo con `default_limit ≤ limit`;
  - **sin tiempo pero no coincide**: llamada sin tiempo con `default_limit > limit`;
  - la política no guarda estado;
  - el texto del comando no aparece en ningún mensaje de error.

  Guarda nueva en `tests/architecture/test_exact_calls_boundaries.py`, con autoprueba sobre fragmentos sintéticos y prueba de mutación sobre una copia en `tmp_path`, como `test_permissions_boundaries.py`:
  - el único `PermissionDecision.ALLOW` nuevo está dentro de `if <decisión> is PermissionDecision.ASK` y de `if self._matches(call) is True` (más el paso de un `ALLOW` de `inner`);
  - el módulo no contiene los literales `"shell"`, `"command"` ni `"timeout_seconds"`;
  - ningún método salvo `__init__` asigna `self.*`;
  - se reutilizan `forbidden_imports`, `find_config_reads` y `terminal_uses`.

  Rojo esperado: `ImportError`. Implementar `src/harness_agent/core/permissions/exact_calls.py` y exportar en `src/harness_agent/core/permissions/__init__.py` y `src/harness_agent/core/__init__.py`. Al terminar: 100 % de líneas y ramas del módulo y `pytest tests/architecture` en verde.

---

## Phase 4: Cableado e integración con el bucle real y el shell (US1, US3 · Sp2-46, Sp2-48)

**Objetivo**: con una tarea con comandos y sin aprobador, el comando exacto corre de verdad y el agente recibe el código, los fallos y la salida recortada.
**Prueba independiente**: `pytest tests/unit/test_bootstrap_task_commands.py tests/integration/test_task_commands_agent_loop.py -q`.

- [x] T004 [US1] Cableado en la raíz de composición, TDD (30 min). Depende de T002 y T003.

  Pruebas primero en `tests/unit/test_bootstrap_task_commands.py`, usando `compose()` con `provider_factory` de `FakeProvider`, `environ` inyectado y la base de datos en `tmp_path`, como en `tests/unit/test_bootstrap_task.py`:
  - con comandos, `composition.loop` permite la llamada exacta al shell sin aprobador (se evalúa la política a través del bucle o de la composición);
  - con comandos, `history_prefix` tiene un segundo mensaje `SYSTEM` igual a `commands_notice(task.commands)`;
  - sin tarea o sin comandos, `history_prefix` sigue siendo solo el aviso de entorno y la decisión no cambia (SC-004);
  - con `shell` en `[permissions] ask` se pregunta, y con `shell` en `deny` se deniega;
  - un comando declarado que nombra la base de datos se deniega (`ProtectedPolicy` va fuera);
  - `MAX_COMMAND_TIMEOUT_SECONDS == MAX_SHELL_TIMEOUT_SECONDS`, `MAX_FIELD_CHARS <= MAX_COMMAND_CHARS`, y `COMMAND_ARGUMENT`/`TIMEOUT_ARGUMENT` son claves de `ShellTool(...).schema["properties"]`.

  Rojo esperado: la llamada exacta termina en `[approval_required_unavailable]` y falta el segundo mensaje. Implementar:
  - `src/harness_agent/adapters/tools/shell.py`: constantes `COMMAND_ARGUMENT = "command"` y `TIMEOUT_ARGUMENT = "timeout_seconds"`, usadas en el esquema y en `run`, y exportadas en `src/harness_agent/adapters/tools/__init__.py`;
  - `src/harness_agent/bootstrap.py`: traducir `task.commands` a `AllowedCall`, montar `ProtectedPolicy(ExactCallPolicy(DefaultPermissionPolicy(...), allowed, ask_names=config.permissions.ask), …)` y añadir el mensaje de comandos a `history_prefix`.

  Al terminar: `pytest tests/unit/test_bootstrap_*.py tests/unit/adapters/tools tests/architecture -q` en verde y el 100 % de las líneas nuevas de `bootstrap.py`.

- [x] T005 [US1] [US3] Proyecto de ejemplo con el bucle y el shell reales (Sp2-48), TDD (40 min). Depende de T004. Prueba en `tests/integration/test_task_commands_agent_loop.py`.

  Un *fixture* crea en `tmp_path` el proyecto de `research.md` R6: `pytest.ini` vacío, `test_ejemplo.py` con una prueba que pasa, una que falla con un mensaje reconocible y otra que imprime unos 300 000 caracteres y falla, y `modulo.py` con una importación sin usar. Se escribe una tarea con `## Comandos`:
  - `- pruebas: python -m pytest -q -p no:cacheprovider test_ejemplo.py` con `- tiempo: 300`;
  - `- lint: python -m ruff check --no-cache .`

  La composición se hace con `compose(config con workspace_root=tmp_path, task=parse_task(...), environ con PATH que empieza por la carpeta de sys.executable, approver=None)` y un `FakeProvider` que pide el shell. Casos:
  - **AC-01 / SC-001**: el resultado del comando de pruebas empieza por `[codigo_de_salida=` con un valor ≠ 0, `is_error` es verdadero y contiene el nombre de la prueba fallida;
  - **AC-02 / SC-003**: el mensaje de herramienta del historial no supera `max_tool_output_chars` y contiene `[salida recortada: se omitieron`, el código y el resumen final de pytest;
  - **lint**: el comando corre sin preguntar y devuelve un código ≠ 0 con la regla de importación sin usar;
  - **corrección**: tras arreglar la prueba en disco (con una tarea sin la prueba larga), el mismo comando da `Código de salida: 0`;
  - **variación**: el comando con `&& echo VALOR-DE-PRUEBA-123` termina en `[approval_required_unavailable]`, ningún proceso escribe el marcador y ningún evento lleva el comando.

  Rojo esperado: si T004 se desactiva temporalmente (o con `task.commands` vacío) todo termina en `[approval_required_unavailable]`; anotar cómo se observó. Debe pasar en Windows (PowerShell) y Linux (bash); si un caso depende de la plataforma, marcarlo con su `skipif` y explicarlo.

---

## Phase 5: Fronteras, documentación y cierre

- [x] T006 Verificación de fronteras y documentación (20 min). Depende de T005.
  - Ejecutar `pytest tests/architecture -q` y anotar el resultado (pasadas, guardas nuevas, ningún archivo que viole una regla) siguiendo `verificar-fronteras-hexagonales`.
  - Añadir `test_exact_calls_boundaries.py` a la tabla de guardas de la skill, en `.claude/skills/verificar-fronteras-hexagonales/SKILL.md` y en `.agents/skills/` (copias idénticas).
  - Añadir `core/tasks/commands.py` y `core/permissions/exact_calls.py` a `references/arbol.md` de las dos copias de `estructura-carpetas-harness`.
  - Añadir HU-11-03 a la tabla «Qué existe hoy» y la convención «comandos de la tarea» en `CLAUDE.md`.
  - Revisar contra el código la lista de comprobación de `capas-y-reglas.md` del `plan.md` y anotar cualquier «no».

- [x] T007 Cierre (30 min). Depende de T006.
  - Ejecutar las cuatro puertas: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`, todas con exit 0. Anotar los conteos reales de pasadas y omitidas, y el 100 % en `core/tasks/` y `core/permissions/exact_calls.py`.
  - Comprobar `git diff --exit-code $(git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/loop.py tests/doubles docs/archivo tests/unit/core/tasks/test_task_parser.py`.
  - En `docs/PROGRESO.md` (CRLF puro, una fila por línea, sin reescribir filas ajenas ni la tabla *Resumen*):
    - la fila de HU-11-03 pasa a **`En revisión`** (nunca `Hecha`), con *Archivos* y *Evidencia* reales;
    - una línea por tarea en *Registro de cambios*;
    - en **Observaciones de HU-11-03**:
      1. **riesgo abierto**: el comando de pruebas ejecuta código editable por el agente (`conftest.py`), ligado a R-21 y PD-06/HU-IN-02;
      2. `main()` no carga tareas (no hay opción de CLI) y hay que decidir qué historia la añade;
      3. para HU-03-04: los comandos no se guardan en SQLite;
      4. para HU-02-01/HU-02-06.1: conservar el mensaje de comandos de `history_prefix`;
      5. para HU-05-02: su denegación debe prevalecer sobre `ExactCallPolicy`;
      6. cambio aditivo en `core/tasks/` (de A) pendiente de visto bueno.
  - Marcar en este archivo solo T001–T007 con su evidencia; T008 y T009 quedan sin marcar.

---

## Phase 6: Tareas humanas (Claude no las marca)

- [ ] T008 Visto bueno de **A** a la ampliación aditiva del formato de la tarea (`core/tasks/`, `contracts/task_commands_format.md`) y **revisión cruzada** del cambio por alguien de A o B (la historia es de C).
- [ ] T009 CI remota en verde en `ubuntu-latest` y `windows-latest` (sobre todo `test_task_commands_agent_loop.py` con bash y PowerShell reales), con push y PR confirmados por una persona.

---

## Dependencias y orden

```text
T001 ─▶ T002 ─┐
        T003 ─┴─▶ T004 ─▶ T005 ─▶ T006 ─▶ T007 ─▶ (T008, T009 humanas)
```

- T002 y T003 son independientes (`[P]`): archivos distintos de `core/`. Ambas exportan en `core/__init__.py`, así que si se hacen a la vez hay que unir esa línea a mano.
- **US2** (solo lo exacto se permite solo) queda probada al terminar T003, sin depender del resto.
- **US1** (pruebas configuradas que informan del fallo) necesita T002, T003, T004 y T005.
- **US3** (salida larga recortada) se demuestra en T005; el recorte ya existe (HU-01-04/HU-02-02).

## Ejemplo de paralelismo

```text
Agente 1: T002  (tests/unit/core/tasks/test_task_commands.py + core/tasks/*)
Agente 2: T003  (tests/unit/core/permissions/test_exact_calls.py + core/permissions/exact_calls.py + guarda)
```

## Estrategia de implementación

1. **MVP**: T001 → T002 → T003 → T004. Con eso el comando exacto de la tarea ya se permite solo, y puede comprobarse a mano con `compose()`.
2. **Incremento**: T005 demuestra AC-01 y AC-02 con un proyecto real en las dos plataformas.
3. **Cierre**: T006 y T007. Después, T008 y T009 son humanas y la historia no pasa a `Hecha` hasta completarlas y ratificar HU-00-01.

## Evidencia (2026-10-26, Windows 11, Python 3.12, `.venv` con `requirements-dev.txt`)

| Tarea | Rojo observado | Verde |
|---|---|---|
| T001 | — | Fila de HU-11-03 a `En curso`, bloque de observaciones y registro en `docs/PROGRESO.md` (CRLF) |
| T002 | `ImportError` de `DEFAULT_COMMAND_TIMEOUT_SECONDS` | `tests/unit/core/tasks`: 121 pasadas; `core/tasks/*` al 100 % de líneas y ramas; `test_task_parser.py` sin cambios |
| T003 | `ImportError` de `AllowedCall` | `test_exact_calls.py`: 92 pasadas (32 variaciones que no pasan, precedencia de zona protegida, `deny` y `ask` con la cadena real); `exact_calls.py` al 100 %; guarda nueva en verde |
| T004 | 4 fallos: la llamada exacta acababa en `[approval_required_unavailable]` y faltaba el mensaje de comandos | `test_bootstrap_task_commands.py`: 18 pasadas; `bootstrap.py` y `adapters/tools/shell.py` al 100 % |
| T005 | 5 fallos con el cableado de `bootstrap.py` retirado temporalmente (`git stash`, restaurado) | `test_task_commands_agent_loop.py`: 9 pasadas con PowerShell real (AC-01, AC-02, lint, corrección, variaciones, eventos) |
| T006 | — | `pytest tests/architecture`: 421 pasadas; skills (dos copias idénticas) y `CLAUDE.md` al día; detector de secretos sin hallazgos en los archivos nuevos |
| T007 | — | `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing` en exit 0: 4415 pasadas, 47 omitidas (ninguna de esta historia), total 99 %; `git diff --exit-code` de lo protegido en 0; PROGRESO a `En revisión` |

Pendiente: bash real (Linux) solo en la CI (T009), porque esta máquina no tiene WSL.
