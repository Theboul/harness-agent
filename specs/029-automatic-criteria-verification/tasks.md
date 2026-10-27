# Tasks: HU-11-04.1 — Verificación automática de criterios objetivos: solo el harness marca passes

**Input**: `specs/029-automatic-criteria-verification/` (spec.md con Clarifications, plan.md, research.md R1–R15, data-model.md, contracts/ ×4, quickstart.md)
**Rama**: `gustavo` (sin commit, push ni cambio de rama por parte de Claude)
**Responsable**: A — Núcleo | **PHU**: 2 | **Sprint**: 2
**Tareas de referencia**: Sp2-49, Sp2-50, Sp2-51, Sp2-52, Sp2-53

## Cómo leer este documento

- **Regla RITMO**: 2 PHU → 7 tareas de implementación de ≤ 40 min (T002–T008 agrupan módulo y pruebas), más el inicio (T001), el cierre (T009) y las humanas (H1–H6). Como la historia tiene menos de 3 PHU, no hay `/speckit-analyze`. El presupuesto del sprint es un aviso, no un límite.
- **TDD dentro de cada tarea**:
  1. escribir las pruebas;
  2. ejecutarlas y ver el **rojo por la razón esperada** (anotarlo en la evidencia);
  3. implementar lo mínimo;
  4. pasar `ruff format --check .`, `ruff check .`, `mypy src tests` y las pruebas del módulo con cobertura (100 % de líneas y ramas del módulo nuevo).
- **Formato**: `- [ ] Tnnn [USn] descripción con ruta`.
  - US1: el harness comprueba los criterios objetivos (AC-01).
  - US2: un criterio sin comando nunca se marca solo (AC-02).
  - US3: el fallo llega al agente con código y salida recortada (AC-03).
  - US4: la persona ve el estado de cada criterio (AC-04).
  - US5: la verificación no afloja ninguna regla de permisos.
  - US6: el resultado de cada ronda es claro en cada caso.
- **Lo que no se toca** (diff vacío al cerrar): `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `core/redaction.py`, **todo** `core/permissions/`, `config.py`, `adapters/tools/shell.py`, `adapters/storage/`, `tests/doubles/`, `docs/archivo/`. **Si algo lo exige, detente y avisa.**
- **Pruebas existentes que cambian** (y solo estas):
  - `tests/integration/test_task_start.py:24`: la condición `salida 0` pasa a `codigo_salida == 0` (T002);
  - `tests/unit/adapters/tasks/test_task_source.py:25`: la condición `ok` pasa a `codigo_salida == 0` (T002);
  - `tests/unit/adapters/tools/test_public_api.py`: solo se añaden los nombres nuevos de `adapters.tools` a la lista esperada (T005);
  - `tests/integration/test_core_public_api.py`: **no debería cambiar** (comprueba `core.tools`, no los nombres nuevos de `core`); si falla, es un hallazgo: detente;
  - `tests/unit/core/tasks/test_task_parser.py`: **solo se añaden casos**.
  - **Cualquier otra prueba existente que falle: detente y avisa con la razón antes de ajustarla.** Hallazgo ya hecho al preparar las tareas: las pruebas de la CLI fijan `SHOWN_TYPES` (6 tipos) y el texto de `/ayuda`, por eso el diseño no los toca (research R12).
- **Caracteres ocultos**: en `specs/` y `docs/` escribe `U+202E` y `U+200B` como texto, nunca el carácter. En código y pruebas, `chr(0x202E)`, `chr(0x200B)` y `chr(27)`, nunca secuencias `\u...` en el texto que escribe la herramienta.
- **Finales de línea**: todo archivo de `specs/` y `docs/` en CRLF. Usa scripts que lean y escriban bytes; nunca `sed -i`.
- **Secretos**: ninguna asignación con forma de clave ni URL con credenciales literales; se construyen por partes (`"https://" + "usuario-de-prueba" + ":" + "secreto-de-prueba" + "@servidor.example/r.git"`).
- **Nada peligroso se ejecuta jamás en pruebas**: los comandos denegados o preguntados solo pasan por un shell doble que registra.

## Mapeo a tareas del sprint

| Tarea | Descripción (03-plan-sprints) | Presupuesto | Tareas aquí |
|---|---|---|---|
| **Sp2-49** | Definir el campo de verificación del criterio (comando y condición esperada) | 60 min | T002 (35) = 35 |
| **Sp2-50** | Ejecutar los comandos de verificación desde el harness bajo la política de permisos | 150 min | T004 (40), T005 (35) = 75 |
| **Sp2-51** | Actualizar passes solo desde el harness y dejar pendientes los criterios sin verificación automática | 90 min | T003 (40) = 40 |
| **Sp2-52** | Mostrar en la CLI el estado de cada criterio | 90 min | T006 (40) = 40 |
| **Sp2-53** | Preparar el proyecto de prueba y el ticket de ejemplo con tres criterios | 120 min | T007 (40) = 40 |
| — | Inicio, guardas/documentación y cierre | — | T001 (10), T008 (30), T009 (30) = 70 |

**Total de Claude: 300 min** frente a 510 min presupuestados. **Humanas: H1–H6** (sin minutos de Claude).

---

## Phase 1: Inicio

- [x] T001 Inicio (10 min) en `docs/PROGRESO.md` (CRLF puro, una fila por línea, sin tocar la tabla *Resumen*, con un script que conserve los CRLF; deriva el de `prog028.py` del scratchpad cambiando el prefijo de la fila por `| [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1) |` y la cabecera por `**Observaciones de HU-11-04.1**:`):
  - la fila **existente** de HU-11-04.1 pasa de `Pendiente` a `En curso` (responsable A; la implementa Claude en `gustavo`);
  - una línea en *Registro de cambios*;
  - un bloque nuevo **Observaciones de HU-11-04.1** con la spec 029, las decisiones Q1, Q2 y Q3 de clarify, la corrección «se ejecutan todos los criterios objetivos en cada propuesta» y la nota «el puerto no cambia (Q1 = B)».

  Comprobar que `.specify/feature.json` apunta a `specs/029-automatic-criteria-verification`.

  **Hecho cuando**: la fila está en `En curso`, `PROGRESO.md` sigue en CRLF puro y solo cambia una fila existente más líneas añadidas.

---

## Phase 2: Fundamentos puros

- [x] T002 [US1] Condición esperada y validación en el analizador (35 min · Sp2-49). Archivos:
  - nuevo `src/harness_agent/core/tasks/condition.py`: `MAX_EXIT_CODE`, `Condition` (`@dataclass(frozen=True)`: `operator`, `value`), `parse_condition(text: object) -> Condition | None` y `condition_met(condition, exit_code: int | None) -> bool`, según `contracts/condition_contract.md`: puras y totales, solo biblioteca estándar;
  - `src/harness_agent/core/tasks/errors.py`: clave `condicion_no_soportada` con el texto exacto del contrato;
  - `src/harness_agent/core/tasks/parser.py`: en `_CriteriaReader._close`, **después** de comprobar la pareja `comando`/`espera` y antes de crear el `CriterionDefinition`, `if parse_condition(expectation) is None: raise TaskFormatError("condicion_no_soportada")`. No se valida en `CriterionDefinition.__post_init__`;
  - exportaciones en `core/tasks/__init__.py` y `core/__init__.py` (`Condition`, `MAX_EXIT_CODE`, `parse_condition`, `condition_met`).

  Pruebas primero:
  - nuevo `tests/unit/core/tasks/test_condition.py`: **tabla exacta** de los 13 ejemplos del contrato (`parse_condition`) y de los 7 de `condition_met`; valores que no son texto (`None`, `5`, `b"x"`) → `None`; el mensaje del error no contiene el texto recibido (centinela `VALOR-DE-PRUEBA-123`);
  - nuevo `tests/unit/core/tasks/test_condition_properties.py` (semilla fija **20261029**, solo `random`): 2 000 textos construidos (operador, número, espacios, y también mutaciones: letras, signos, números enormes, saltos de línea): nunca lanza; un texto construido como válido devuelve exactamente su operador y su número; uno con un carácter ajeno devuelve `None`;
  - **solo se añaden** casos a `tests/unit/core/tasks/test_task_parser.py`: `espera: salida 0` y `espera: ok` (con `comando:`) → `TaskFormatError` con `code == "condicion_no_soportada"` y mensaje sin el texto recibido; `espera: codigo_salida != 1` se acepta; `comando:` sin `espera:` sigue siendo `criterio_incompleto`; un campo de más de 2 000 caracteres sigue siendo `texto_demasiado_largo` (la comprobación de pareja y de longitud va antes).

  **Rojo esperado**: `ImportError` de `harness_agent.core.tasks.condition` (y los casos nuevos del analizador fallan porque no se rechaza `salida 0`). Tras implementar, ejecutar `tests/integration/test_task_start.py` y `tests/unit/adapters/tasks/test_task_source.py` **sin tocarlos**: deben fallar con `condicion_no_soportada` (esa es la razón del ajuste); entonces cambiar **una cadena cada uno** a `codigo_salida == 0` y declararlo. `tests/architecture/test_tasks_boundaries.py` sigue en verde.

  **Hecho cuando**: `condition.py` al 100 % de líneas y ramas; las suites de `core/tasks`, `adapters/tasks` y `test_task_start.py` en verde; ninguna otra prueba existente cambió.

- [x] T003 [US3] [US6] Estados, aviso, evidencia y nombre del programa (40 min · Sp2-51). Archivos nuevos en `src/harness_agent/core/verification/`: `__init__.py`, `outcomes.py` (`CriterionStatus`, `NotRunCause`, `TaskState`, `CommandOutcome`, `CriterionResult`, `VerificationReport`, `task_state`, según `data-model.md`; `CommandRunner = Callable[[ToolCall], Awaitable[CommandOutcome]]`) y `feedback.py` (`Feedback`, `compose_feedback`, `evidence_text`, `program_name`, `one_line` y las constantes de límites del modelo de datos); exportaciones en `core/__init__.py`. Solo biblioteca estándar y `harness_agent.core`; reutiliza `truncate_output` (HU-02-02).

  Pruebas primero, en `tests/unit/core/verification/` (con `__init__.py` si las demás carpetas lo tienen):
  - `test_outcomes.py`: tabla de `task_state` (todos `cumplido` → `verificada`; con algún `pendiente_humano` → `pendiente_humano`; cualquier otro estado, un valor desconocido o la lista vacía → `no_terminada`); invariantes de `CommandOutcome` (`ran` falso con código o salida → `ValueError`; `timed_out` con código → `ValueError`); `VerificationReport.state` y `.correctable` (`no_cumplido`, `regresion`, `tiempo_agotado`);
  - `test_feedback.py`: **los ejemplos E1–E4 del contrato `agent_notice_contract.md` con el texto exacto** (tabla); singular y plural de la primera línea; más de 20 criterios → `- ... y N más.`; más de 6 000 caracteres de salida en total → el bloque de los criterios que no caben dice `(salida omitida por espacio)`; tabla de `evidence_text` y de `program_name` del contrato; `one_line` quita `Cc`, `Cf`, `Cs`, `Co` (se construyen con `chr(27)`, `chr(0x202E)`, `chr(0x200B)`) y corta con `...`; `compose_feedback` devuelve `None` si solo hay `alterado` o `no_ejecutado`;
  - `test_feedback_properties.py` (semilla **20261029**): 2 000 informes con estados, códigos, salidas hostiles (instrucciones, caracteres de control, 10 000 caracteres, una URL con credencial de prueba **por partes**) y descripciones con caracteres de control: `compose_feedback` nunca lanza; el aviso y el mensaje externo **nunca contienen el comando** (un centinela puesto en `CriterionResult` como comando de prueba que no debe filtrarse); el aviso no contiene salida; ambos respetan sus límites y no tienen caracteres `Cc`/`Cf`/`Cs`/`Co` salvo `\n`.
  - Añadir al final de `contracts/agent_notice_contract.md` (script que conserve CRLF) el ejemplo **E5**: salida total de más de 6 000 caracteres → `(salida omitida por espacio)`.

  **Rojo esperado**: `ImportError` de `harness_agent.core.verification`. **Hecho cuando**: `outcomes.py` y `feedback.py` al 100 %; los textos coinciden carácter a carácter con el contrato; `pytest tests/architecture` sigue en verde.

---

## Phase 3: El verificador (US1, US2, US5, US6 · Sp2-50, Sp2-51)

- [x] T004 [US1] [US2] [US5] [US6] `CriteriaVerifier` (40 min). Archivo nuevo `src/harness_agent/core/verification/verifier.py` (+ exportación) con la firma del modelo de datos: `CriteriaVerifier(store, task, policy, tool, run, emit, *, gate=None, tool_name, command_argument, timeout_argument, declared_timeouts)` y `async verify(session_id) -> VerificationReport`. Solo biblioteca estándar y `harness_agent.core`; es el **único** módulo que llama a `mark_passes`. Por cada criterio, en el orden de la tarea (research R2, R3, R5, R8, R10, R11; contrato del evento):
  1. semántico → `PENDING_HUMAN`, sin política ni ejecución;
  2. emparejar con la fila de SQLite por posición (`store.load_criteria`); si `load_criteria` lanza, o el número de filas difiere, o el comando de la fila no es **exactamente** el de la definición → `TAMPERED`, nada se ejecuta, `criteria_tampered` con `{"motivo": "comando_no_coincide"}` o `"criterios_no_coinciden"`;
  3. condición con `parse_condition`; `None` → `NOT_RUN` (`condicion_no_soportada`);
  4. llamada `ToolCall(id="verificacion-<n>", name=tool_name, arguments={command_argument: comando})`, con `timeout_argument` **solo** si `comando.strip()` está en `declared_timeouts`;
  5. `policy.evaluate(llamada)` (excepción o valor que no es un `PermissionDecision` → `DENY`): `DENY` → `NOT_RUN` (`denegado`) sin llegar al aprobador; `ASK` → sin `gate`, `NOT_RUN` (`sin_aprobador`); con `gate`, `gate.resolve(llamada, tool, emit_requested)` (publica `approval_requested` y `approval_resolved` con las claves del bucle) y si no aprueba, `NOT_RUN` (`no_aprobado`); `ALLOW` o aprobado → ejecutar con `run(llamada)`; publica también `permission_decided` (`{call_id, name, decision, resolved_as, reason}`);
  6. resultado: `ran` falso → `NOT_RUN` (`error`); `timed_out` → `TIMED_OUT`; `condition_met` → si ya tenía `passes` queda `MET` **sin** volver a marcar, si no `mark_passes(id, evidence_text(...))` y `MET` (una excepción del almacén → `NOT_RUN` (`error`)); no cumple → `REGRESSION` si ya tenía `passes`, si no `NOT_MET`;
  7. publicar `criterion_verified` (siete claves del contrato, un evento por cada criterio, en orden, también los semánticos).
  - `asyncio.CancelledError` nunca se captura.

  Pruebas primero, `tests/unit/core/verification/test_verifier.py`, con `SqliteTaskStore` en `tmp_path` (ayudantes de `tests/unit/adapters/storage/task_support.py`), un runner, una política y un `Approver` definidos **en el propio archivo** (sin dobles nuevos en `tests/doubles/`; `DummyApprover` sí se puede usar):
  - **matriz de casos de la spec** (una prueba por fila): todos cumplen → `verificada` con evidencia sin comando; todos los objetivos cumplen y hay semánticos → `pendiente_humano` y el semántico nunca se marca; uno falla → `no_cumplido`, `passes` falso; **regresión** (ronda 1 cumple, ronda 2 falla) → `regresion`, `passes` sigue en verdadero y `mark_passes` no se vuelve a llamar; comando alterado (una tarea distinta en el verificador) y base alterada (cambio por `store.connection()`) → `alterado`, runner con 0 llamadas; política que pregunta sin aprobador → `no_ejecutado`; con aprobador que rechaza → `no_aprobado`; con `APPROVE_SESSION` la segunda ronda no vuelve a preguntar; comando **denegado** → `no_ejecutado`, **0 preguntas al aprobador y 0 llamadas al runner**; tiempo agotado → `tiempo_agotado`; criterio sin comando → `pendiente_humano`;
  - todos los criterios objetivos se ejecutan en cada llamada a `verify`, también los ya cumplidos;
  - forma de la llamada: la política recibe exactamente `{command}` y, para un comando idéntico a uno declarado, `{command, timeout_seconds: <declarado>}`; el `ToolCall` que ve el runner es el mismo;
  - política que lanza o devuelve basura → `DENY`; condición no soportada construida a mano → `no_ejecutado`; `mark_passes` que lanza → `no_ejecutado`/`error` y el criterio no queda cumplido; `CancelledError` del runner se propaga;
  - eventos: exactamente siete claves en `criterion_verified`, uno por criterio y en orden; las claves de `approval_requested`/`approval_resolved`/`permission_decided` son las del bucle (se comparan con los conjuntos de claves del bucle); **no filtración**: con centinelas en un argumento del comando, en la salida y en una credencial de URL de prueba (por partes), ninguna carga publicada los contiene, mientras que la descripción del criterio sí aparece.

  **Rojo esperado**: `ImportError` de `harness_agent.core.verification.verifier`. **Hecho cuando**: `verifier.py` al 100 %; ningún comando denegado o preguntado llegó al runner de las pruebas; `core/loop.py` y `core/permissions/` sin diff.

---

## Phase 4: La ronda de corrección y el adaptador del shell (US1, US3 · Sp2-50)

- [x] T005 [US1] [US3] `VerifyingRunner` y `adapters/tools/shell_outcome.py` (35 min). Archivos:
  - nuevo `src/harness_agent/core/verification/runner.py` (+ exportación): `VerifyingRunner(run_turn, verifier, session_id)` y `async run(task, history) -> TurnResult` según research R6: ejecuta el turno; si no es `TurnStatus.COMPLETED` o no hay verificador, lo devuelve; si lo es, `verify`; con algo corregible (`report.correctable`), añade a `history` un `Message(Role.USER, feedback.external, is_external=True)` y lanza otro turno con `feedback.notice` como tarea; si nada es corregible, o el estado es `verificada` o `pendiente_humano`, termina con el último resultado. **Sin contador de rondas ni constantes numéricas de rondas**: el tope lo pone el bucle (`LIMIT_REACHED`). Solo biblioteca estándar y `harness_agent.core`; sin E/S;
  - nuevo `src/harness_agent/adapters/tools/shell_outcome.py`: `outcome_from_result(result: ToolResult) -> CommandOutcome` y `make_command_runner(registry: ToolRegistry, tool_name: str) -> CommandRunner` (valida con `registry.validate_args`, ejecuta `registry.get(tool_name).run(...)`, convierte; lo desconocido o un fallo de validación → `ran=False`); exportar ambos en `adapters/tools/__init__.py`. Importa solo biblioteca estándar, la API pública de `core` y su paquete.

  Pruebas primero:
  - `tests/unit/core/verification/test_runner.py` (turno y verificador definidos en el archivo): turno que no es `COMPLETED` → sin verificar; `verificada` y `pendiente_humano` → un solo turno; corregible → el historial recibe el mensaje externo (`Role.USER`, `is_external=True`) **antes** del aviso y el segundo turno recibe el aviso como tarea; segundo turno `LIMIT_REACHED` → termina; solo `alterado`/`no_ejecutado` → no abre otra ronda; un guion de cinco rondas corregibles seguidas de `LIMIT_REACHED` demuestra que el único tope es el del turno; la cancelación se propaga; sin verificador → paso directo;
  - `tests/unit/adapters/tools/test_shell_outcome.py`: ejecuta la **`ShellTool` real** con un `Shell` doble (patrón de `test_shell_tool.py`) y fija cada etiqueta: salida 0, salida N, tiempo agotado, sin área, argumentos inválidos, intérprete no disponible, error del shell, contenido desconocido; con `InMemoryToolRegistry`: argumentos que no validan → `ran=False`;
  - `tests/unit/adapters/tools/test_public_api.py`: añadir **solo** `make_command_runner` y `outcome_from_result` a la lista esperada.

  **Rojo esperado**: `ImportError` de `runner` y `shell_outcome`. **Hecho cuando**: ambos módulos al 100 %; `tests/architecture/test_adapters_boundaries.py` sigue en verde con `shell_outcome.py`; `adapters/tools/shell.py` sin diff.

---

## Phase 5: La terminal y el cableado (US4 · Sp2-52)

- [x] T006 [US4] Estado de los criterios en la CLI y cableado en `bootstrap.py` (40 min). Archivos:
  - nuevo `src/harness_agent/cli/criteria.py`: `criterion_line(payload)`, `CriteriaBoard` (`update`, `lines`, `summary_line`, `report`) y `attach_criteria_status(bus, output) -> CriteriaBoard` (suscripción **solo** a `criterion_verified`; escribe la línea de cada criterio y, tras el último, la línea final con `task_state`), según `contracts/cli_status_contract.md`; solo biblioteca estándar y la API pública de `core`; reutiliza `sanitize` y `bounded` de `cli/render.py`; descripción ≤ 80 caracteres;
  - `src/harness_agent/cli/app.py`: `run_cli(..., commands=None)` con `commands: Mapping[str, tuple[str, Callable[[], str]]] | None`; un comando de la tabla escribe su texto; `/ayuda` añade `  <comando>  <descripción>` **solo** si hay `commands`; `src/harness_agent/cli/__init__.py` exporta `CriteriaBoard` y `attach_criteria_status`. **No cambian** `cli/render.py`, `SHOWN_TYPES`, `attach_renderer` ni `HELP_TEXT`;
  - `src/harness_agent/bootstrap.py` (solo cableado): con tarea, construir el `CriteriaVerifier` (política de la cadena, `shell_tool`, `make_command_runner(registry, shell_tool.name)`, `ApprovalGate(approver)` o `None` sin aprobador, `emit` que fabrica el `Event` con el `session_id`, el reloj y el `id_factory` inyectados, y `declared_timeouts={c.command: c.timeout_seconds for c in commands}`) y el `VerifyingRunner`; `Composition` gana `runner: VerifyingRunner | None = None`; `run_session` usa el runner si existe, crea el tablero con `attach_criteria_status(bus, stream)` y pasa `commands={"/criterios": ("Muestra el estado de los criterios.", board.report)}`. Sin tarea nada cambia.

  Pruebas primero:
  - `tests/unit/cli/test_criteria.py`: **tabla exacta** de líneas y de líneas finales del contrato (prototipo, estados, cargas con campos que faltan o de otro tipo → línea neutra sin excepción, descripción con `chr(27)` y `chr(0x202E)` sin esos caracteres, descripción de 200 caracteres cortada, una clave `command` extra en la carga no aparece nunca);
  - `tests/unit/cli/test_app_criteria.py`: `attach_criteria_status` con `InMemoryEventBus`: tres eventos → tres líneas y la línea final solo tras el último; `/criterios` antes de verificar → `Todavía no se ha verificado ningún criterio.`; después → las líneas y la final; `run_cli` sin `commands` conserva `/ayuda` y los desconocidos (las pruebas existentes de `test_app_input.py` pasan **sin cambios**); con `commands`, `/ayuda` añade la línea;
  - `tests/unit/test_bootstrap_verification.py`: `compose(task=…)` entrega un `runner`; sin tarea es `None`; la política que ve el verificador es la de la cadena (una llamada denegada por la lista base no llega al runner); el `declared_timeouts` sale de `## Comandos`.

  **Rojo esperado**: `ImportError` de `harness_agent.cli.criteria` y `TypeError` por el parámetro `commands`. **Hecho cuando**: `criteria.py` al 100 %; todas las pruebas existentes de `cli/` y de `bootstrap` pasan sin cambios; `tests/architecture/test_cli_boundaries.py` y `test_bootstrap_boundaries.py` en verde.

---

## Phase 6: De punta a punta (Sp2-53)

- [x] T007 [US1] [US2] [US3] [US4] [US5] [US6] Integración con `compose()` y el ticket de ejemplo (40 min · Sp2-53). Archivo nuevo `tests/integration/test_criteria_verification_agent_loop.py` (patrón de `test_task_commands_agent_loop.py` y `test_command_policy_agent_loop.py`: `monkeypatch` de `bootstrap.select_shell`, `FakeProvider`, `compose(task=…)`):
  - **ticket de ejemplo** (constante `TICKET`, formato de la tarea, **tres criterios**: dos con `comando:`/`espera: codigo_salida == 0` y uno semántico) y un **proyecto de ejemplo** en `tmp_path/trabajo` construido por una función del propio archivo;
  - **matriz con el shell doble** (registra los comandos y no ejecuta nada): todos cumplen; todos los objetivos cumplen y hay semánticos (estado final «pendiente de validación humana» en la salida de la CLI); uno falla y el agente recibe en su petición siguiente (`provider.received`) el mensaje externo (`is_external`) con la salida enmarcada y el aviso sin el comando; regresión; comando alterado; política que pregunta **sin aprobador**; comando **denegado** (lista base, git destructivo, zona protegida y lista `deny`: 0 preguntas al aprobador y 0 comandos en el doble); tiempo agotado; criterio sin comando;
  - un comando de verificación idéntico a uno de `## Comandos` se ejecuta sin preguntar y con su tiempo; uno que la política pregunta y la persona aprueba (aprobador de prueba) se ejecuta una vez;
  - **todos los criterios objetivos se ejecutan en cada propuesta** (el doble cuenta dos ejecuciones del comando ya cumplido tras la segunda propuesta);
  - **no filtración**: ningún evento, evidencia (`criterios.json` y la fila de SQLite) ni mensaje de error contiene el comando, la salida ni la credencial de prueba; el aviso nunca contiene el comando;
  - **único escritor**: recorre `registry` de `compose()` y comprueba que ninguna herramienta (nombre, esquema, descripción, atributos) expone `mark_passes`;
  - **la CLI**: con `run_session`/`run_cli` sobre `io.StringIO` el estado sale con el formato del contrato y `/criterios` lo repite;
  - **un único flujo con el shell real** y comandos triviales de Python en `tmp_path` (mismo patrón de selección de intérprete y de omisión limpia que Sp2-48; se omite si no hay intérprete): el agente crea el archivo que un criterio comprueba, el criterio pasa, el otro falla hasta que se corrige;
  - **ningún comando denegado o preguntado se ejecuta jamás**: en la matriz solo el doble los recibe.

  **Rojo esperado**: sin `runner` en `compose()` (retirar temporalmente el cableado de `bootstrap.py` con `git stash` de ese archivo y restaurarlo): la mayoría de las pruebas fallan porque no se verifica nada; anota el número de fallos. **Hecho cuando**: todo en verde en Windows; el flujo real se ejecuta o se omite limpio; `git stash list` conserva solo `stash@{0}` de la spec 017.

---

## Phase 7: Guardas, documentación y cierre

- [x] T008 Guardas de arquitectura y documentación (30 min). Archivos:
  - nuevo `tests/architecture/test_verification_boundaries.py` (a partir de `verificar-fronteras-hexagonales/assets/test_module_boundaries.py`, reutilizando `forbidden_imports`, `find_config_reads` y `terminal_uses`, con autoprueba sobre fragmentos sintéticos y una prueba de mutación sobre una copia en `tmp_path`):
    - `core/verification/` y `core/tasks/condition.py`: solo biblioteca estándar y núcleo, sin E/S (`sqlite3`, `subprocess`, `pathlib`, `os`…), sin entorno ni terminal, sin importar `adapters`, `cli`, `config` ni `bootstrap`;
    - `runner.py`: sin `adapters/` y sin constantes numéricas de rondas ni contadores (no hay contador nuevo);
    - **único escritor**: en **todo** `src/`, ninguna llamada `….mark_passes(…)` fuera de `core/verification/verifier.py` y exactamente una en él; solo hay definiciones en `interfaces/system.py` y `adapters/storage/task_store.py`; ningún archivo de `adapters/tools/` ni `core/tools/` nombra `mark_passes`;
    - `verifier.py` nunca captura `BaseException`, un `except` desnudo ni `CancelledError`, y nunca nombra `PermissionDecision.ALLOW` fuera de una comparación `is`;
    - ningún módulo de `core/verification/` importa el bucle (`core.loop`) salvo `runner.py`, que usa `TurnResult` y `TurnStatus`;
  - skills (dos copias idénticas, `.claude/skills/` y `.agents/skills/`): fila nueva en la tabla de `verificar-fronteras-hexagonales/SKILL.md`; `core/verification/`, `core/tasks/condition.py`, `adapters/tools/shell_outcome.py` y `cli/criteria.py` en `estructura-carpetas-harness/references/arbol.md`;
  - `CLAUDE.md`: fila de HU-11-04.1 en «Qué existe hoy» y nota en las convenciones (solo el verificador marca passes; la capacidad no es alcanzable desde `python -m harness_agent` hasta que `main()` cargue tareas);
  - revisar contra el código la lista de comprobación de `capas-y-reglas.md` de `plan.md` y anotar cualquier «no» (script que conserve CRLF);
  - **detector de secretos** a mano sobre **todos** los archivos nuevos y modificados (también los no versionados) con un script que use `secret_patterns_in` de `tests/architecture/test_no_secrets_in_repo.py`, y **caracteres ocultos y CRLF** en `specs/029-automatic-criteria-verification/` y `docs/`.

  **Rojo esperado de la guarda**: la prueba de mutación (una copia con un `mark_passes` fuera del verificador, o con un `except BaseException`) la hace fallar. **Hecho cuando**: `pytest tests/architecture` en verde con la guarda nueva, las copias de las skills idénticas (`cmp`), el detector sin hallazgos y sin caracteres ocultos ni saltos de línea sueltos.

- [x] T009 Cierre (30 min). Depende de T008.
  - Ejecutar las cuatro puertas: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`, todas en exit 0. Anotar los conteos reales, el 100 % de líneas y ramas de `condition.py`, `outcomes.py`, `feedback.py`, `verifier.py`, `runner.py`, `shell_outcome.py` y `criteria.py`, y `pytest tests/architecture`.
  - Comprobar `git diff --exit-code $(git merge-base HEAD origin/main) -- <lo que no se toca, de arriba>` → 0, y revisar a mano que las únicas pruebas existentes modificadas son las de la lista de arriba.
  - Repetir el detector de secretos y la comprobación de caracteres ocultos y CRLF **después** de escribir PROGRESO.
  - En `docs/PROGRESO.md` (CRLF puro, **una fila** de HU-11-04.1 que pasa a **`En revisión`**, nunca `Hecha`; sin reescribir filas ajenas ni la tabla *Resumen*) con *Archivos* y *Evidencia* reales, una línea por tarea en *Registro de cambios* y, en **Observaciones de HU-11-04.1**:
    1. las decisiones **Q1** (puerto sin cambios, emparejado por posición), **Q2** (preguntar con el aprobador de HU-05-03) y **Q3** (solo `==` y `!=` del código de salida; tareas con otra condición se rechazan al cargar; los dos ajustes de pruebas existentes);
    2. la **regresión sin revocar** (el almacén no tiene esa operación) y la **pregunta al PO** sobre si debe permitir revocar passes con evidencia (cambio de puerto con acuerdo);
    3. el **tiempo de verificación fuera de `max_seconds`** (hallazgo para A, HU-01-06);
    4. la **aprobación de sesión independiente** del verificador respecto de la del bucle;
    5. el campo **`program`** (y `description`) del evento `criterion_verified`, a confirmar con A, B y C;
    6. que **`main()` aún no carga tareas**: esta capacidad no es alcanzable desde `python -m harness_agent` hasta cablearlo (punto abierto de HU-11-03);
    7. la **nota de proceso** con los rojos observados y los hallazgos del plan (`SHOWN_TYPES` y `/ayuda` fijados por pruebas existentes);
    8. lo **pendiente** (H1–H6).
  - Marcar en este archivo solo T001–T009 con su evidencia (tabla al final), con un script que conserve los CRLF; H1–H6 quedan sin marcar.

  **Hecho cuando**: las cuatro puertas en verde, el diff de lo que no se toca vacío, el detector sin hallazgos, sin caracteres ocultos y PROGRESO en CRLF con una sola fila nueva en `En revisión`.

---

## Phase 8: Tareas humanas (Claude no las marca)

- [ ] H1 **Acuerdo de A, B y C** sobre los campos del evento `criterion_verified` (siete claves, en especial `program` y `description`) y sobre el endurecimiento del analizador de la tarea (`condicion_no_soportada`).
- [ ] H2 **Visto bueno de C** a `cli/` (`criteria.py`, `app.py`, `__init__.py`), `bootstrap.py` y `adapters/tools/shell_outcome.py`.
- [ ] H3 **Revisión cruzada** por B o C (la historia es de A).
- [ ] H4 El **PO revisa** la regla ante «preguntar» (Q2), la gramática de la condición (Q3) y si el almacén debe permitir **revocar passes con evidencia** ante una regresión.
- [ ] H5 **CI remota** en verde en `ubuntu-latest` y `windows-latest` (el flujo con shell real corre allí), con push y PR confirmados por una persona.
- [ ] H6 **Aviso a A (HU-01-06)**: el tiempo de los comandos de verificación no cuenta en `max_seconds`.

---

## Dependencias y orden

```text
T001 ─▶ T002 ─▶ T003 ─▶ T004 ─▶ T005 ─▶ T006 ─▶ T007 ─▶ T008 ─▶ T009 ─▶ (H1–H6)
```

- Es una cadena porque cada tarea añade exportaciones a `core/__init__.py` y la siguiente usa lo anterior; T002 y T003 podrían ir en paralelo si las exportaciones se juntan, pero no compensa.
- **US1 y US5** (comprueba y respeta los permisos): T004, T005 y T007. **US2** (sin comando): T004 y T007. **US3** (fallo informado): T003, T005 y T007. **US4** (estado en la CLI): T006 y T007. **US6** (resultado por caso): T003, T004 y T007.

## Estrategia de implementación

1. **MVP**: T001–T004. El verificador ya ejecuta, marca y publica (probado con dobles).
2. **Incremento**: T005 (ronda de corrección y adaptador), T006 (CLI y cableado) y T007 (de punta a punta).
3. **Cierre**: T008 y T009. Después, H1–H6 son humanas y la historia no pasa a `Hecha` hasta completarlas y ratificar HU-00-01.

---

## Evidencia (2026-10-27, Windows 11, Python 3.12, `.venv`)

| Tarea | Rojo observado (razón esperada) | Verde |
|---|---|---|
| T001 | — | `PROGRESO.md` con la fila en `En curso`, bloque de observaciones y registro, en CRLF |
| T002 | `ImportError` de `core.tasks.condition` (2 archivos) y 5 casos nuevos del analizador en rojo; tras implementar, 9 pruebas existentes en rojo: las 8 de los dos ajustes previstos y `test_key_lines_accept_dash_prefix_and_any_case` (aprobada por el usuario) | Tres pruebas existentes ajustadas por Q3; `condition.py` y `parser.py` al 100 %; suite completa en verde |
| T003 | `ImportError` de `CriterionResult` y demás nombres | 59 pruebas; `outcomes.py` y `feedback.py` al 100 %; E5 añadido al contrato |
| T004 | `ImportError` de `CriteriaVerifier` | 29 pruebas; `verifier.py` al 100 %; matriz de casos, forma de llamada y no filtración |
| T005 | `ImportError` de `VerifyingRunner` y `make_command_runner`; la guarda existente del bucle obligó a leer el turno por protocolo | `runner.py` y `shell_outcome.py` al 100 %; dos nombres nuevos en `test_public_api.py` de `adapters.tools` |
| T006 | `ImportError` de `cli.criteria` y `AttributeError` de `Composition.runner` | `criteria.py`, `app.py` y `bootstrap.py` al 100 %; las pruebas existentes de la CLI y de `bootstrap` sin cambios |
| T007 | Sin el cableado de `bootstrap.py` (stash de ese archivo): 18 fallos y 1 pasa | 19 pruebas; el flujo con el shell real se ejecutó; `bootstrap.py` restaurado |
| T008 | Un segundo escritor de passes en un archivo temporal hace fallar `test_only_the_verifier_marks_passes_in_all_of_src` | 19 pruebas de la guarda; skills idénticas; detector de secretos, ocultos y CRLF: 0 problemas (un U+202E literal sustituido por `chr(0x202E)`) |
| T009 | — | 6422 pasadas y 47 omitidas; `ruff format --check`, `ruff check` y `mypy src tests` (350 archivos) en exit 0; 489 pruebas de arquitectura; cobertura total 99 % y 100 % en los módulos nuevos; diff de lo protegido vacío; fila `En revisión` |

H1–H6 quedan sin marcar: las deciden personas.
