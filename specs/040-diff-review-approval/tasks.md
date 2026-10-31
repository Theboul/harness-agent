# Tareas: HU-11-05 — Resumen de cambios y aprobación humana del diff

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · Pruebas primero (verlas fallar por la razón esperada); cada tarea cierra con ruff/mypy/pytest. `--basetemp` corto (`/c/tmp/pt40`).
**Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`; tampoco `adapters/mcp/`, `config_mcp.py` ni `core/progress/`.
**Mapeo a plan de sprints**: Sp3-60 (resumen, 2 min), Sp3-61 (mostrar diff, 1,5), Sp3-62 (decisión ↔ política, 2), Sp3-63 (confirmar criterios, 2).

- [ ] T001 [US1] `core/review/changes.py` + `view.py` (+ `__init__`): tipos, vista, bloqueos. Prueba `tests/unit/core/review/test_view.py`.
- [ ] T002 [US2] `core/review/messages.py` + `decision.py`: mensaje de commit, avisos de rechazo (saneados). Prueba `test_messages.py`.
- [ ] T003 [US3] `core/verification` (`outcomes.py`, `verifier.py::confirm`, estado `confirmado_humano`) y `cli/criteria.py`. Pruebas en `tests/unit/core/verification/` y `tests/unit/cli/test_criteria.py`; la guarda del único escritor de passes sigue en verde.
- [ ] T004 [US1][US2][US3] `core/review/runner.py`: `ReviewingRunner`. Prueba `tests/unit/core/review/test_runner.py` (aprobar, rechazar, criterios, sin decisión, falla de git, sin cambios, objetivos sin cumplir).
- [ ] T005 [US1] `adapters/system/git_changes.py` (+ API de `adapters/system/__init__.py`). Pruebas `tests/unit/adapters/system/test_git_changes.py` (runner doble) e integración con git real `tests/integration/test_git_changes_real.py`.
- [ ] T006 [US1][US2][US3] `cli/review_view.py` + `cli/review.py` (+ API de `cli/__init__.py`). Pruebas `tests/unit/cli/test_review_view.py`, `test_review.py`.
- [ ] T007 `bootstrap.py`: `compose(reviewer=, changes=)`, `Composition.runner` como `TaskRunner`, `main()` inyecta la consola. Prueba `tests/integration/test_review_session.py`.
- [ ] T008 Guarda `tests/architecture/test_review_boundaries.py` (plantilla de la skill) y ajuste de `test_bootstrap_boundaries.py`/`test_adapters_boundaries.py` si hace falta.
- [ ] T009 Verificación: `ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest`, `pytest tests/architecture`; diff de protegidos vacío; lista de `capas-y-reglas.md`.
- [ ] T010 Documentación: `docs/PROGRESO.md`, `CLAUDE.md` (tabla y convención), contrato de `criterion_verified` (spec 029), skills en `.claude/skills/` y `.agents/skills/`.

## Tareas humanas (Claude no las marca)

- [ ] H01 Revisión cruzada (A o B).
- [ ] H02 CI remota en Ubuntu y Windows.
- [ ] H03 El PO ratifica: aprobar exige criterios semánticos confirmados; resumen sin descripción por archivo.
- [ ] H04 A ratifica el cambio en `core/verification` (`confirm`, `confirmado_humano`).

## Dependencias

T001 → T002 → T004; T003 → T004; T005 (paralela); T004 → T006 → T007 → T008 → T009 → T010.
