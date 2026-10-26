# Tareas: SPK-03 — Spike: compactación sin perder el objetivo

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Responsable**: B — Estado  
**Mapeo y presupuesto**: Sp2-34 (120 min) → T001–T003 · Sp2-35 (90 min) → T004–T006 · Sp2-36 (60 min) → T007 · cierre T008–T009. Total del plan 270 min; los tiempos son referencia.

**Archivos protegidos** (no se tocan): `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `cli/`, `tests/doubles/`, `docs/archivo/`. Tampoco se añade nada a `src/`, `pyproject.toml` ni la CI.

**Orden por prueba primero**: en T001–T005 se escribe la prueba, se observa que falla por la razón esperada (módulo o función ausente, o aserción de pérdida), se implementa lo mínimo del apoyo y se pasan las puertas.

## Fase 1 — Sesión larga de prueba (Sp2-34)

- [x] **T001** [US1] Escenario sembrado en `tests/spikes/compaction_sim.py`: `Seed`, `build_long_session()` determinista (~80 mensajes: objetivo, instrucciones, reglas, ticket `TCK-4821` y referencia a criterios al inicio; tres decisiones intermedias; llamadas a herramientas con salidas largas) y `estimate_tokens` local (Sp2-34, 35 min)
  - **Archivos**: `tests/spikes/compaction_sim.py`, `tests/spikes/test_compaction_goal_spike.py` (clase `TestScenario`)
  - **Verificación**: cada centinela aparece exactamente una vez; la sesión es idéntica en dos construcciones; ningún mensaje `TOOL` queda sin su `ASSISTANT`.
- [x] **T002** [US1] Ensamblado en dos diseños y corte seguro en `compaction_sim.py`: `EssentialBlock.render`, `CriteriaSource` (doble de solo lectura), `assemble_summary_only`, `assemble_pinned_block`, `safe_cut` (Sp2-34, 40 min)
  - **Archivos**: `tests/spikes/compaction_sim.py`, `tests/spikes/test_compaction_goal_spike.py` (clase `TestAssembly`)
  - **Verificación**: el bloque es un mensaje `SYSTEM` al inicio; `criteria_ref` sin fuente falla cerrado; `safe_cut` nunca separa llamada y resultado.
- [x] **T003** [US1] Resumidores en `compaction_sim.py`: `LossySummarizer` (presupuesto de caracteres, de lo nuevo a lo viejo) y `ProviderSummarizer` sobre `FakeProvider` (Sp2-34, 35 min)
  - **Archivos**: `tests/spikes/compaction_sim.py`, `tests/spikes/test_compaction_goal_spike.py` (clase `TestSummarizers`)
  - **Verificación**: el resumidor con pérdida es determinista y respeta su presupuesto; el proveedor simulado recibe la petición de resumen y devuelve el guion.

## Fase 2 — Probar el resumen con doble compactación (Sp2-35)

- [x] **T004** [US2] Doble compactación y comparación de diseños (Sp2-35, 40 min)
  - **Archivos**: `tests/spikes/test_compaction_goal_spike.py` (clase `TestDoubleCompaction`)
  - **Verificación**: «solo resumen» + resumidor con pérdida pierde el objetivo y al menos otro elemento tras la 2.ª compactación; «bloque fijo» conserva los cinco elementos idénticos tras ambas; las decisiones se pierden en ambos diseños con el resumidor con pérdida (hallazgo para HU-02-06.2); SC-001.
- [x] **T005** [US2] Entrada y salida de la compactación (Sp2-35, 35 min)
  - **Archivos**: `tests/spikes/test_compaction_goal_spike.py` (clase `TestCompactionProperties`)
  - **Verificación**: la entrada de la llamada de resumen no contiene el bloque ni los recientes; los mensajes recientes quedan íntegros; el historial de entrada no cambia (tupla idéntica).
- [x] **T006** [US2] Estabilidad del prefijo y criterios por referencia (Sp2-35, 35 min)
  - **Archivos**: `tests/spikes/test_compaction_goal_spike.py` (clase `TestEssentialBlock`)
  - **Verificación**: el mensaje del bloque es idéntico byte a byte entre ensamblados antes y después de compactar; los criterios se leen de la fuente en cada ensamblado y un resumen con criterios desactualizados no los reemplaza; el contexto enviado a `FakeProvider` tras compactar contiene el objetivo (AC-03 de HU-02-06.1 solo hasta donde se puede probar sin modelo).

## Fase 3 — Diseño anotado (Sp2-36)

- [x] **T007** [US4] Decisión escrita `docs/decisiones/SPK-03-compactacion-bloque-fijo.md` (Sp2-36, 40 min)
  - **Archivos**: `docs/decisiones/SPK-03-compactacion-bloque-fijo.md`
  - **Contenido**: qué se hizo y qué no (comprobado / no comprobado); resultados medidos; diseño del bloque fijo (claves, origen, inyección, exclusión, criterios por referencia, reconstrucción al reanudar); reglas del corte seguro; recomendaciones separadas para HU-02-03, HU-02-06.1, HU-02-06.2 y HU-03-04; hallazgos sobre puertos y eventos (`compact` síncrono frente a `Provider.complete` asíncrono, payload de `CONTEXT_COMPACTED`) **sin tocarlos**; pendiente humano y procedimiento de la corrida con modelo real.

## Fase 4 — Cierre

- [x] **T008** Verificación (`verificar-fronteras-hexagonales`): `ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest`, `pytest tests/architecture`, `git diff --exit-code` sobre archivos protegidos y confirmar que `src/` no cambió (20 min)
  - **Archivos**: ninguno
- [x] **T009** Registro en `docs/PROGRESO.md` (SPK-03 `En curso`, nunca `Hecha`; fila, *Registro de cambios* y bloque **Observaciones de SPK-03**) y marcado de este archivo (15 min)
  - **Archivos**: `docs/PROGRESO.md`, `specs/022-compaction-goal-spike/tasks.md`, `.specify/feature.json` (ignorado por git: se edita en disco)

## Tareas humanas (no las marca Claude)

- [ ] **T010** Corrida con un modelo real de pocos tokens: resumir dos veces el historial del escenario y comprobar que el resumen conserva objetivo y decisiones, y que el agente responde el objetivo tras compactar (cierra AC-01 de SPK-03; depende de D-IA: proveedores y presupuesto)
- [ ] **T011** Revisión cruzada por A o C
- [ ] **T012** CI remota en `ubuntu-latest` y `windows-latest`
- [ ] **T013** Acuerdo de A, B y C sobre los hallazgos que tocan contratos (puente síncrono/asíncrono de `compact`, payload de `CONTEXT_COMPACTED`) antes de que HU-02-03 los use

## Dependencias y ejecución

T001 → T002 → T003 (mismo archivo de apoyo, en serie) → T004 → T005 → T006 (mismo archivo de pruebas, en serie) → T007 (necesita los números de T004–T006) → T008 → T009. MVP: T001–T006 demuestran el diseño; T007 lo deja usable por HU-02-03 y HU-02-06.1.

## Phase 5: Convergence

- [x] T014 Añadir el Protocol `CriteriaSource` en `tests/spikes/compaction_sim.py` y tipar `EssentialBlock.render` y `assemble_pinned_block` con él, como dice el modelo de datos per plan: D4 (partial)
- [x] T015 Añadir en `TestDoubleCompaction` una prueba con `ProviderSummarizer` y un guion de `FakeProvider` cuyo resumen omite el objetivo: el diseño A lo pierde y el B lo conserva, per plan: D3 (partial)

## Evidencia (2026-10-25)

- T001–T006, T014, T015: `tests/spikes/test_compaction_goal_spike.py` → 113 pruebas en verde; rojo previo observado en T001–T003 (`ModuleNotFoundError` / importaciones ausentes). T004–T006 pasaron al primer intento; tres mutaciones del apoyo (sin bloque, corte sin pares, resumidor con todo el historial) las hacen fallar.
- T007: `docs/decisiones/SPK-03-compactacion-bloque-fijo.md`.
- T008: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov` → exit 0 (3634 pasadas, 45 omitidas, 130,66 s, cobertura 98 %); `pytest tests/architecture` → 347 pasadas; sin diferencias en `src/`, `pyproject.toml`, `requirements-dev.txt`, `.github`, `tests/doubles` ni `docs/archivo`.
- T009: `docs/PROGRESO.md` (SPK-03 `En curso`).
- Lista de comprobación de `arquitectura-hexagonal-clean` revisada contra el código: sin puertos ni eventos nuevos, `core/` intacto, todo lo externo por el puerto `Provider` (con `FakeProvider`), falla cerrada en criterios sin fuente, sin red ni claves: todas «sí» salvo «puertos nuevos» y «eventos nuevos» (no).
