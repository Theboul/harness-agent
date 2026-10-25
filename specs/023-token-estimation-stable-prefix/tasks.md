# Tasks: HU-02-01 — Estimación de tokens y prefijo estable

**Input**: `specs/023-token-estimation-stable-prefix/` (spec, plan, research, data-model, contracts, quickstart)
**Mapeo al plan de sprints**: Sp2-09 (estimar y corregir, 3 h, T004–T008 y T014–T016), Sp2-10 (ensamblar prefijo y variable, 2,5 h, T009–T013 y T017), Sp2-11 (pruebas de estabilidad, 1,5 h, T018–T019). Los tiempos son referencia.
**Pruebas primero**: cada tarea de código escribe la prueba, la ve fallar por la razón esperada, implementa lo mínimo y pasa las cuatro puertas.
**Formato**: `- [ ] Txxx [P] [USn] descripción con ruta`.

## Archivos protegidos (no se tocan)

`src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `cli/`, `tests/doubles/`, `docs/archivo/`.

## Phase 1: Setup

- [x] T001 Crear la rama/worktree desde `origin/main` y comprobar la base verde (`pytest -q`, `ruff`, `mypy`); ruta del worktree corta (≤ 260 caracteres)
- [x] T002 Crear el paquete vacío `src/harness_agent/core/context/{__init__,errors}.py` con `ContextConfigError(ValueError)` y su docstring (fila: subpaquete de `core/` + `errors.py`); prueba en `tests/unit/core/context/__init__.py`

## Phase 2: Foundational

- [x] T003 Escribir la guarda `tests/architecture/test_context_boundaries.py` a partir de `test_tasks_boundaries.py` (solo stdlib y `harness_agent.core`, sin E/S, entorno ni terminal) y verla pasar sobre el paquete vacío (`verificar-fronteras-hexagonales`)

## Phase 3: User Story 2 — Estimar (P1)

**Goal**: estimar tokens de texto, mensaje, definición y lista. **Independent test**: valores conocidos.

- [x] T004 [US2] Prueba roja en `tests/unit/core/context/test_estimator.py`: `estimate_text` (`""`→0, 1→1, 4→1, 5→2), `estimate_message` (contenido, llamadas con argumentos de claves en distinto orden dan el mismo valor, resultado de herramienta, sobrecarga fija por mensaje), `estimate_tool_definition`, `estimate_messages` (suma)
- [x] T005 [US2] Implementar las funciones de estimación en `src/harness_agent/core/context/estimator.py` (serialización JSON con `sort_keys`, `default=str`)

## Phase 4: User Story 3 — Corregir con el consumo real (P1)

**Goal**: factor de calibración por sesión. **Independent test**: observar un consumo conocido y re-estimar.

- [x] T006 [US3] Prueba roja en el mismo `test_estimator.py`: `TokenEstimator.factor` inicial 1.0; `observe` ajusta a reportado/crudo (estimación calibrada = reportado ±1); ignora reportado ≤ 0 y crudo ≤ 0; tope inferior 0,25 y superior 4,0; sesiones independientes
- [x] T007 [US3] Implementar `TokenEstimator` en `estimator.py`
- [x] T008 [US3] Revisar cobertura 100 % de `estimator.py` y `errors.py`; añadir los casos que falten

## Phase 5: User Story 1 — Prefijo estable (P1)

**Goal**: prefijo determinista, congelado por sesión. **Independent test**: ensamblar en N turnos.

- [x] T009 [P] [US1] Prueba roja en `tests/unit/core/context/test_prefix.py`: `PrefixSpec` rechaza instrucciones/SO/intérprete vacíos y reglas vacías con `ContextConfigError` (mensaje fijo sin el valor); `build_prefix` produce un mensaje `SYSTEM` con secciones en orden, herramientas ordenadas por nombre, misma huella para distinto orden de registro, huella distinta si cambia algo, rechaza nombres duplicados o vacíos y parámetros no serializables
- [x] T010 [US1] Implementar `PrefixSpec`, `StablePrefix` y `build_prefix` en `src/harness_agent/core/context/prefix.py`
- [x] T011 [US1] Prueba roja en `tests/unit/core/context/test_assembler.py`: `assemble` devuelve prefijo + copia del historial, no muta ni da alias; sesión vacía; `session_id` vacío rechazado; estimación = prefijo + definiciones + mensajes; `provider_messages()` pone el sistema primero; el prefijo se calcula una sola vez por sesión (la fuente se llama una vez); sesión nueva toma lo vigente
- [x] T012 [US1] Implementar `AssembledContext` y `ContextAssembler.assemble` en `src/harness_agent/core/context/assembler.py`
- [x] T013 [US1] Exportar la API pública en `core/context/__init__.py` y en `src/harness_agent/core/__init__.py` (`__all__`); prueba de importación desde `harness_agent.core`

## Phase 6: Corrección integrada (US3 sobre el ensamblador)

- [x] T014 [US3] Prueba roja en `test_assembler.py`: `record_usage` calibra con la última estimación cruda; la siguiente estimación del mismo contenido coincide con el consumo (±1); `usage` nulo, cero o sin ensamblado previo no cambia nada; segunda llamada tras consumir no hace nada; sesiones independientes
- [x] T015 [US3] Implementar `record_usage` en `assembler.py`
- [x] T016 [US3] Prueba de integración `tests/integration/test_context_assembler_loop.py`: ensamblador + `ScriptedProvider` que devuelve `usage`; tres turnos con historial creciente (armado a mano, sin tocar `AgentLoop`); el prefijo enviado es idéntico y la estimación converge al uso informado

## Phase 7: Estabilidad del prefijo (Sp2-11)

- [x] T017 [P] [US1] Escribir `tests/unit/core/context/test_prefix_stability.py`: 20 turnos con historial creciente → misma huella y mismo objeto de mensaje; cambio de herramientas, de orden y de fuente a mitad de sesión → prefijo igual; dos sesiones con fuentes distintas → huellas distintas; la huella no depende de reglas de otras sesiones
- [x] T018 [US1] Ejecutar las pruebas de estabilidad y registrar la salida real en la evidencia

## Phase 8: Polish y cierre

- [x] T019 Verificación de fronteras: `pytest tests/architecture` (con `test_context_boundaries.py`) y revisar los archivos protegidos con el `git diff --exit-code` de CLAUDE.md
- [x] T020 Cuatro puertas de calidad en exit 0: `ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest --cov=harness_agent --cov-report=term-missing` (100 % de `core/context/`)
- [x] T021 Actualizar `CLAUDE.md` (tabla «Qué existe hoy»), `.claude/skills/estructura-carpetas-harness/references/arbol.md` y su copia en `.agents/skills/` (`core/context/` ya no es «planeado»); `docs/guia-contratos-desarrollo.md` si describe el contexto
- [x] T022 Actualizar `docs/PROGRESO.md`: fila HU-02-01 → `En revisión`, *Archivos*, *Evidencia*, registro de cambios (Sp2-09 a Sp2-11) y bloque **Observaciones de HU-02-01** con los cuatro hallazgos del plan; actualizar `.specify/feature.json`
- [x] T023 Commits convencionales en español con el ID `HU-02-01`, sin atribución de IA, en unidades de trabajo (código con sus pruebas; documentación)

## Tareas humanas (no las marca Claude)

- [ ] T024 Revisión cruzada por A o C (diseño de `core/context/` y los hallazgos)
- [ ] T025 CI remota en verde en `ubuntu-latest` y `windows-latest`
- [ ] T026 A decide e integra el punto de `core/loop.py` (hallazgo 1) y A, B y C acuerdan el destino del puerto `ContextManager` (hallazgo 2)
- [ ] T027 Ratificación técnica de HU-00-01 (Sp1-03) pendiente, que bloquea pasar la historia a `Hecha`

## Dependencias

T001 → T002 → T003 → {T004→T005 → T006→T007→T008} y {T009→T010 → T011→T012→T013 → T014→T015 → T016} → T017→T018 → T019 → T020 → T021 → T022 → T023. T009 puede ir en paralelo con T004–T008 (otro archivo); T017 en paralelo con T016.

## Estrategia

MVP = US1 + US2 + US3 (las tres son P1 y se prueban juntas en T016). Entrega en dos commits de unidad de trabajo: (1) estimador, (2) prefijo y ensamblador, más (3) documentación.

## Evidencia (2026-10-25)

- T003/T019: `pytest tests/architecture`: 376 pasadas; `test_context_boundaries.py` con autoprueba de detectores; `git diff --exit-code` sobre `core/interfaces`, `core/events.py`, `core/loop.py`, `tests/doubles` y `docs/archivo`: sin salida.
- T008/T020: `harness_agent/core/context/` al 100 % de líneas y ramas; `ruff format --check .`, `ruff check .` y `mypy src tests`: exit 0; `pytest`: 3865 pasadas, 49 omitidas.
- T016: `tests/integration/test_context_assembler_loop.py`: prefijo idéntico en tres llamadas y estimación igual al consumo informado tras `record_usage`.
- T018: `tests/unit/core/context/test_prefix_stability.py` (20 turnos, cambio de herramientas, orden, sesiones distintas).
- `/speckit-converge`: sin trabajo pendiente de código; los pendientes son las tareas humanas T024 a T027.
