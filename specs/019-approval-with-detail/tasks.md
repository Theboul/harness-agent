# Implementation Tasks: Aprobación con detalle (HU-05-03)

**Feature**: `specs/019-approval-with-detail/spec.md`  
**Plan**: `specs/019-approval-with-detail/plan.md`  
**Responsable de la historia**: C — Control y conexiones | **Sprint**: 2 | **PHU**: 3  
**Tareas de referencia**: Sp2-29 (evento y espera, 2 h), Sp2-30 (presentación en la CLI, 3 h), Sp2-31 (alcance por herramienta y patrón, 2,5 h). Los tiempos son referencia.

---

## Cómo leer este documento

**Pruebas primero, dentro de cada tarea**: escribir la prueba, verla fallar **por la razón esperada** (indicada), implementar lo mínimo, pasar los cuatro comandos de calidad.

**Mapeo a tareas del plan**: Sp2-29 → T002, T004, T005; Sp2-31 → T003; Sp2-30 → T006, T007; cableado → T008; integración → T009.

**Reglas para todas las tareas:**
- **Archivos protegidos**: no modificar `src/harness_agent/core/interfaces/`, `core/events.py`, `core/in_memory_event_bus.py`, `tests/doubles/`, `docs/archivo/`, `.github/workflows/ci.yml`. **Excepción acordada**: `core/loop.py` (dueño A) se toca solo en T004/T005, con el cambio mínimo autorizado por el usuario el 2026-10-25; `cli/` se toca en T006/T007 porque la historia es de CLI/control (C).
- Sin red, claves ni consola real: `DummyApprover`, `RecordingEventBus`, `ScriptedProvider`/`FakeProvider`, `StringIO`. Centinela `VALOR-DE-PRUEBA-123`; sin literales que el detector de secretos marque.
- Windows: sin señales reales, `ids=` explícitos en `parametrize` largos, rutas como `Path`.
- `rm -f .coverage*` antes de confirmar; `git add <rutas>` explícitas.
- Cobertura objetivo: 100 % de líneas y ramas de `approvals.py` y `cli/approval.py`.
- Cierre de cada tarea con código: `ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest --cov=harness_agent --cov-report=term-missing` (exit 0) y `pytest tests/architecture`.
- Entorno: el worktree no tiene `.venv`; se usa el de la copia principal con `pythonpath = ["src"]` del `pyproject.toml` (las pruebas importan el `src` del worktree).

---

## Phase 1: Setup

- [x] T001 Marcar HU-05-03 `En curso` en `docs/PROGRESO.md` (fila de Sprint 2, sin tocar la tabla *Resumen*)
  - **Archivos**: `docs/PROGRESO.md`

## Phase 2: Foundational — la puerta de aprobación del núcleo (US1)

- [x] T002 [US1] `ApprovalGate` y `ApprovalOutcome`: una vez, rechazar y falla cerrada, con `build_details`
  - **Archivos**: `src/harness_agent/core/permissions/approvals.py`, `src/harness_agent/core/permissions/__init__.py`, `src/harness_agent/core/__init__.py`, `tests/unit/core/permissions/test_approvals.py` (fila: «regla de negocio → subpaquete de `core/`»)
  - **Primero las pruebas** (rojo esperado: `ImportError` de `ApprovalGate`): approve_once aprueba y no deja rastro; reject deniega y conserva el motivo acotado; el aprobador que lanza `Exception` → `approver_error`; resultado que no es `ApprovalResult` o acción inválida → `invalid_result`; `CancelledError` se propaga; `details` lleva copia de los argumentos, descripción y riesgo; `emit_requested` se llama antes de `request`; si `emit_requested` lanza, no se pregunta.
  - **Implementar** lo mínimo; **~35 min**.

## Phase 3: User Story 2 — alcance de la sesión (P1)

- [x] T003 [US2] Aprobaciones de sesión (herramienta + argumentos exactos) en `ApprovalGate`
  - **Archivos**: `src/harness_agent/core/permissions/approvals.py`, `tests/unit/core/permissions/test_approvals.py`
  - **Pruebas** (rojo: la segunda llamada vuelve a preguntar): approve_session recuerda; los mismos argumentos con otro orden de claves coinciden; argumentos distintos vuelven a pedir; otra herramienta vuelve a pedir; argumentos no serializables → se aprueba pero no se recuerda; la coincidencia devuelve `source="session_grant"` sin llamar al aprobador; una puerta nueva no hereda aprobaciones.
  - **~30 min**.

## Phase 4: User Story 1 y 3 — el bucle espera y falla cerrado

- [x] T004 [US1] `AgentLoop(…, approver=None)`: emite `APPROVAL_REQUESTED`/`APPROVAL_RESOLVED` y ejecuta o rechaza
  - **Archivos**: `src/harness_agent/core/loop.py` (mínimo), `tests/core/test_loop_approval.py`, `tests/architecture/test_loop_boundaries.py` (el bucle puede emitir eventos de aprobación, no los de límite), `tests/integration/test_event_bus_agent_loop.py` (invertir `test_observation_the_loop_does_not_emit_approval_requested_yet`)
  - **Pruebas** (rojo: el bucle sigue devolviendo `[approval_required_unavailable]`): con aprobador y «preguntar», orden `TOOL_REQUESTED, PERMISSION_DECIDED(ask), APPROVAL_REQUESTED, APPROVAL_RESOLVED, TOOL_FINISHED`; aprobar ejecuta con los argumentos mostrados; rechazar → `[approval_rejected]` y no ejecuta; falla del aprobador → `[approval_failed]`; sin aprobador, sin cambios; una denegación de la política no llama al aprobador aunque haya aprobación de sesión previa; cargas sin el centinela de los argumentos; dos «preguntar» se piden de una en una.
  - **~40 min**.

- [x] T005 [US3] Cancelación y fallo del bus durante la aprobación
  - **Archivos**: `src/harness_agent/core/loop.py`, `tests/core/test_loop_approval.py`
  - **Pruebas** (rojo: fase `tool_execution` en `INTERRUPTED` o herramienta ejecutada): cancelar mientras se espera publica `INTERRUPTED` con fase `approval`, no ejecuta y no resuelve como aprobado; un suscriptor que falla en `APPROVAL_REQUESTED`/`APPROVAL_RESOLVED` impide la ejecución y propaga `EventDeliveryError`.
  - **~25 min**.

## Phase 5: User Story 1 — la CLI muestra el detalle (P1)

- [x] T006 [US1] `ConsoleApprover` en la CLI
  - **Archivos**: `src/harness_agent/cli/approval.py`, `src/harness_agent/cli/__init__.py`, `tests/unit/cli/test_approval.py` (fila: «lee de la terminal → `cli/`»)
  - **Pruebas** (rojo: `ImportError`): muestra herramienta, un renglón por argumento (saneado y acotado), efecto y riesgo y las tres opciones; `1`/`2`/`3` → acciones; opción no válida se repite hasta 3 veces y luego rechaza; fin de entrada rechaza; valores de claves con aspecto de secreto salen como `***`; el texto no reproduce el valor de una entrada inválida; usa solo stdlib y la API pública de `core`.
  - **~40 min**.

- [x] T007 [US4] Render de `PERMISSION_DECIDED(ask)` pendiente y de las categorías de rechazo (`APPROVAL_RESOLVED` no se añade a `SHOWN_TYPES`: ver observaciones de PROGRESO)
  - **Archivos**: `src/harness_agent/cli/render.py`, `tests/unit/cli/test_render_approval.py`
  - **Pruebas** (rojo: se imprime el error de permiso «ask» aunque haya aprobación): `resolved_as="ask"` no imprime error; `APPROVAL_RESOLVED` imprime una línea en español por cada acción/origen; carga mal formada no rompe.
  - **~25 min**.

## Phase 6: Cableado e integración

- [x] T008 [US1] Cablear en `bootstrap.py`: `compose(approver=None)` pasa el aprobador al bucle y `main()` crea el `ConsoleApprover` con los flujos reales
  - **Archivos**: `src/harness_agent/bootstrap.py`, `tests/unit/test_bootstrap_approval.py`; ajustar `tests/architecture/test_bootstrap_boundaries.py` solo si hace falta
  - **Pruebas** (rojo: `compose()` no acepta `approver`): `compose` entrega el aprobador al bucle; `main` con `provider_factory` guionizado que pide una escritura fuera del área y entrada `1` ejecuta; con `3` no; ajustar las pruebas existentes de `main` que contaban con `[approval_required_unavailable]`.
  - **~35 min**.

- [x] T009 [US2] Integración: bucle real + `DefaultPermissionPolicy` + `ProtectedPolicy` real + `ConsoleApprover`
  - **Archivos**: `tests/integration/test_approval_agent_loop.py`
  - **Pruebas**: aprobar para la sesión una escritura y repetirla (no pregunta) y repetirla con otros argumentos (pregunta); una llamada a la zona protegida sigue denegada con una aprobación de sesión que la «cubriría» (AC-02 de HU-05-02 / FR-008); un turno completo con eventos en el bus real.
  - **~35 min**.

## Phase 7: Fronteras y documentación

- [x] T010 Guarda `tests/architecture/test_approvals_boundaries.py` desde la plantilla (stdlib + `harness_agent.core`, sin E/S, sin `print`/`input`, sin `config`; el gate no importa `loop`) con autoprueba y mutación
  - **Archivos**: `tests/architecture/test_approvals_boundaries.py` (skill `verificar-fronteras-hexagonales`)
  - **~25 min**.

- [x] T011 Documentación viva: `CLAUDE.md` (tabla «Qué existe hoy» y convenciones), `.claude/skills/verificar-fronteras-hexagonales/SKILL.md` y `estructura-carpetas-harness/references/arbol.md` (ambas copias `.claude` y `.agents`), `docs/guia-contratos-desarrollo.md` (aprobación de sesión)
  - **~25 min**.

## Phase 8: Cierre

- [x] T012 Verificación final y `docs/PROGRESO.md`: cuatro comandos + `pytest tests/architecture`, `git diff --exit-code $base -- src/harness_agent/core/interfaces src/harness_agent/core/events.py tests/doubles docs/archivo` (exit 0), fila de HU-05-03 → `En revisión` (nunca `Hecha`), *Archivos*, *Evidencia*, registro por tarea y bloque **Observaciones de HU-05-03** (los hallazgos del plan)
  - **~30 min**.

## Phase 9: Tareas humanas finales (Claude **no** las marca)

- [ ] T013 Revisión cruzada por un integrante de otra área (A debe revisar el cambio de `core/loop.py`)
- [ ] T014 Ejecución de la CI en `ubuntu-latest` y `windows-latest` y relleno de Commit/PR
- [ ] T015 Confirmación del PO: patrón de sesión = argumentos exactos (Q1), «efecto esperado» = descripción de la herramienta + riesgo, rechazo sin motivo hasta HU-05-04

---

## Dependencias y orden

T001 → T002 → T003 → T004 → T005; T006 y T007 (CLI) pueden ir en paralelo con T004/T005 [P] tras T002; T008 depende de T004 y T006; T009 de T008; T010 puede ir tras T002 (se completa tras T005); T011 y T012 al final.

## Archivos protegidos (verificar antes de cerrar)

```bash
base=$(git merge-base HEAD origin/main)
git diff --exit-code $base -- src/harness_agent/core/interfaces src/harness_agent/core/events.py tests/doubles docs/archivo
```
`core/loop.py` aparecerá en el diff: es el cambio autorizado (T004, T005) y se declara en `PROGRESO.md`.

## Estrategia

MVP = T001–T005 (núcleo y bucle). Después la CLI (T006–T007), el cableado (T008–T009) y el cierre.

---

## Phase 10: Convergence

- [x] T016 Rechazar de inmediato cuando la persona escribe `/salir` durante una petición de aprobación, en lugar de contarlo como opción no válida, en `src/harness_agent/cli/approval.py` y `tests/unit/cli/test_approval.py` per Assumptions de la spec («`/salir` ... se trata como entrada agotada») (partial)
- [x] T017 Corregir en `specs/019-approval-with-detail/quickstart.md` y `plan.md` la ruta de la prueba de `main()` (`tests/unit/test_bootstrap_approval.py`, no `tests/integration/...`) per plan: Project Structure (partial)
