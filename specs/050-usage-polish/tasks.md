# Tareas: HU-06-07 — Pulido de uso del arnés

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · `--basetemp` corto (`/c/tmp/pt50`).
**Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`.
**Mapeo a plan de sprints**: historia propuesta; sin tarea `SpN-xx`. Cada tarea: prueba primero, vista fallar por la razón esperada.

- [x] T001 `tests/unit/adapters/providers/test_litellm_debug.py` + parámetro `debug` en `litellm_provider.py` + sumidero y `HARNESS_DEBUG_PROVIDER` en `bootstrap.py` (FR-001, AC-01, AC-05).
- [x] T002 `tests/unit/test_bootstrap_git.py` (ajuste) + `_provisional_prefix(…, task)` (FR-003, AC-03).
- [x] T003 `tests/unit/test_bootstrap_mode_notice.py` + `PLANNING_NOTICE`, `IMPLEMENTING_NOTICE` y `WorkMode.take_notice()/forget()` en `bootstrap.py` (`turn()`, `/nueva`, `/reanudar`) (FR-002, AC-02).
- [x] T004 Guarda `tests/architecture/test_usage_polish_boundaries.py` y verificación de fronteras; diff de protegidos vacío.
- [x] T005 (separable, última) `tests/unit/test_bootstrap_plan_offer.py` + `Composition.ask` + oferta en `run_session` + texto en `cli/session_commands.py` (FR-004, AC-04).
- [x] T006 `docs/04c` (ficha propuesta), `README.md`, `CLAUDE.md`, `docs/PROGRESO.md` (fila, registro, observaciones y solicitud a A), `.specify/feature.json`.
- [x] T007 Cuatro puertas de calidad en exit 0 (8738 pasadas, 48 omitidas, cobertura 99 %; módulos tocados al 100 %).

## Análisis de consistencia (speckit-analyze)

FR-001→T001; FR-002→T003; FR-003→T002; FR-004→T005; FR-005→T004. AC-01/AC-05→T001; AC-02→T003; AC-03→T002; AC-04→T005. Sin contradicciones. Desviación declarada: el aviso va antepuesto a la petición (un mensaje `USER`), no como mensaje suelto (spec, clarificaciones).

## Tareas humanas (Claude no las marca)

- [ ] H01 Revisión cruzada (A o B).
- [ ] H02 CI remota en Ubuntu y Windows.
- [ ] H03 Ratificación del PO (ID HU-06-07 y AC-01 a AC-05) y de A/B/C del cambio mínimo en `cli/session_commands.py`; la oferta se ratifica junto con HU-06-06.
- [ ] H04 Prueba manual con Groq `gpt-oss-120b` y `HARNESS_DEBUG_PROVIDER=1` para ver el 400 real.
