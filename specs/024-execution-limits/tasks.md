# Tasks: HU-01-06 — Límites de turnos, tiempo y consumo por sesión

**Input**: `specs/024-execution-limits/` (spec, plan, research, data-model, contracts, quickstart)

**Mapeo a `docs/03-plan-sprints.md`**: Sp2-06 (comprobar antes de cada llamada, 2 h) → T003–T008, T010; Sp2-07 (emitir el evento, 1 h) → T009; Sp2-08 (pruebas por tipo de límite, 2 h) → T003–T008, T011. Cada tarea es de 15–40 min con prueba primero: se escribe la prueba, se ve fallar **por la razón esperada**, se implementa lo mínimo y pasan las cuatro puertas.

**Archivos protegidos que esta historia SÍ toca (autorizados por la propia historia, cambio mínimo y aditivo)**: `src/harness_agent/core/loop.py` (T007–T009), `src/harness_agent/cli/render.py` (T012, desviación: AC-01 «explica el motivo»). **No se toca**: `core/interfaces/`, `core/events.py`, `config.py`, `tests/doubles/`, `docs/archivo/`. Se actualizan tres pruebas de Sprint 1 que prohibían los eventos de límite (T009, T011).

## Fase 1: Núcleo puro (US1, US2, US3 — lógica)

- [x] T001 [P] Escribir `tests/unit/core/test_limits.py` (validación de `SessionLimits`: no entero, `bool`, ≤ 0, mensaje en español sin el valor) y ver fallar por `ImportError`; crear `src/harness_agent/core/limits.py` con `LimitKind`, `InvalidLimitsError`, `SessionLimits`, `LimitReached`. Fila: «Regla de negocio → `core/limits.py`».
- [x] T002 [P] Guarda `tests/architecture/test_limits_boundaries.py` desde `verificar-fronteras-hexagonales/assets/test_module_boundaries.py`: `core/limits.py` solo stdlib (`time`, `collections.abc`, `dataclasses`, `enum`) y `harness_agent.core.entities`, sin E/S, config ni terminal, con autoprueba sobre fragmentos sintéticos.
- [x] T003 [US1] En `tests/unit/core/test_limits.py` añadir pruebas de `LimitTracker` para turnos (`start_turn`, `>=`, `used`/`maximum`) y verlas fallar; implementar `LimitTracker.start_turn/reached` para `TURNS` en `core/limits.py`.
- [x] T004 [US2] Pruebas de consumo: `add_usage` suma `total_tokens`; `None`, negativo y no entero cuentan 0; `reached` con `TOKENS` en `>=`; verlas fallar e implementar `add_usage` y la rama `TOKENS`.
- [x] T005 [US3] Pruebas de tiempo con reloj falso: `begin_task`/`end_task` acumulan, la pausa entre tareas no cuenta, la tarea en curso sí, `end_task` idempotente, `TIME` en `>=`; implementar la rama `TIME`. Orden fijo turnos → tiempo → consumo cuando varios se cumplen; un límite cumplido sigue cumplido.
- [x] T006 Exportar `SessionLimits`, `LimitKind`, `LimitReached`, `LimitTracker`, `InvalidLimitsError` en `src/harness_agent/core/__init__.py` (`__all__`), actualizando `tests/integration/test_core_public_api.py`; cobertura 100 % de `core/limits.py`.

**Checkpoint**: `pytest tests/unit/core/test_limits.py tests/architecture -q` en verde.

## Fase 2: Bucle (US1, US2, US3 — integración; archivo protegido, cambio mínimo)

- [ ] T007 [US1] `tests/core/test_loop_limits.py` con `make_rig`: con `max_turns=3` y un proveedor que siempre pide herramienta hay exactamente 3 llamadas y el resultado es `TurnStatus.LIMIT_REACHED` (historial con la tarea y sin mensaje de asistente extra); sin `limits` el comportamiento es el de hoy; el límite agotado sigue deteniendo la tarea siguiente. Ver fallar y en `core/loop.py` añadir `TurnStatus.LIMIT_REACHED`, parámetros `limits`/`clock` (solo palabra clave), el tracker, `begin_task/end_task` en `run_turn` (`finally`) y la consulta al inicio de la vuelta (`_stop_at_limit`), contando `start_turn()` antes de llamar y `add_usage` tras validar la respuesta.
- [ ] T008 [US2] [US3] Pruebas del bucle por consumo (se detiene antes de la siguiente llamada, la respuesta que rebasó se conserva y sus herramientas se ejecutan) y por tiempo (reloj falso que avanza dentro del proveedor; la pausa entre tareas no cuenta); ajustar solo lo que haga falta.
- [ ] T009 [US1] Evento: pruebas en `tests/core/test_loop_limits.py` de que se publica **un** `LIMIT_REACHED` con `{limit, used, maximum}` (sin contenido ni argumentos), que un bus que falla propaga el error, y de que no se publica sin límite alcanzado. Implementar la publicación en `_stop_at_limit`. Actualizar `tests/core/test_loop_events.py` (ya no se prohíbe `LIMIT_REACHED`) y `tests/architecture/test_loop_boundaries.py` (el bucle publica `LIMIT_REACHED` solo en `_stop_at_limit`; los únicos parámetros de límite son `limits` y `clock`).

**Checkpoint**: `pytest tests/core tests/architecture -q` en verde.

## Fase 3: CLI y composición (US4, US5)

- [ ] T010 [US5] `tests/unit/test_bootstrap_limits.py`: `compose(config)` con `max_turns=2` entrega un bucle que se detiene a la segunda llamada (con `FakeProvider`), los valores por defecto están activos y `max_output_tokens` no se usa como límite. Mapear `config.limits` → `SessionLimits` en `src/harness_agent/bootstrap.py`.
- [ ] T011 [US1] [US2] [US3] `tests/integration/test_limits_agent_loop.py`: recorrido con `AgentLoop` real, herramientas reales de prueba y `RecordingEventBus` para los tres límites, más la continuidad (otra tarea tras la parada).
- [ ] T012 [US4] `tests/unit/cli/test_render_limits.py` (una línea por límite con su máximo en español; carga desconocida o incompleta → texto genérico; nunca la carga cruda) y ver fallar; modificar `LIMIT_REACHED` en `src/harness_agent/cli/render.py`.

## Fase 4: Cierre

- [ ] T013 Verificación de fronteras: `pytest tests/architecture`; ningún archivo viola una regla; comprobar `git diff --exit-code <base> -- src/harness_agent/core/interfaces src/harness_agent/core/events.py tests/doubles docs/archivo`.
- [ ] T014 Las cuatro puertas: `ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest --cov=harness_agent --cov-report=term-missing` en exit 0.
- [ ] T015 Actualizar `docs/PROGRESO.md` (fila HU-01-06 → `En revisión`, *Archivos*, *Evidencia*, registro de cambios por tarea, observaciones: reconciliar con A, B y PO) y las skills si el código difiere (`arbol.md`, tabla de guardas en `verificar-fronteras-hexagonales`, en `.claude/` y `.agents/`); `CLAUDE.md` (fila de `core/limits.py`).
- [ ] T016 Commits convencionales en español con el ID, por unidad de trabajo.

## Tareas humanas (Claude NO las marca)

- [ ] H01 Revisión cruzada por alguien de otra área (B o C) del cambio en `core/loop.py`.
- [ ] H02 Ratificación de A (dueño del bucle) y del PO de los supuestos del vocabulario (turno = llamada al modelo; contadores por sesión; tiempo = suma de tareas).
- [ ] H03 CI remota en Ubuntu y Windows en verde.

## Dependencias

T001 → T003 → T004 → T005 → T006; T002 tras T001; T007 tras T006; T008, T009 tras T007; T010 tras T009; T011 tras T009; T012 independiente del bucle (puede ir tras T006); T013–T016 al final.
