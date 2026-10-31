# Tareas: HU-11-08.2 — Rutina de arranque al reanudar un ticket

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · Pruebas primero; `--basetemp` corto (`/c/tmp/pt39`).
**Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`; tampoco `adapters/mcp/`, `config_mcp.py`, `core/permissions/`.
**Mapeo a plan de sprints**: tarea de C (1 PHU de la ficha).

- [ ] T001 [US1][US2] `core/startup/briefing.py`: hechos, marco, saneo y aviso (pasa/falla/no comprobada). Prueba `tests/unit/core/startup/test_briefing.py`.
- [ ] T002 [US1] `core/startup/gated.py`: política → aprobación → ejecución. Prueba `test_gated.py`.
- [ ] T003 [US1][US2] `core/startup/routine.py` (+ `__init__`, export en `core/__init__.py`). Prueba `test_routine.py`.
- [ ] T004 [US1][US2] `bootstrap.py`: `Composition.startup`, `_startup_routine`, entrega en la primera petición. Prueba `tests/integration/test_startup_routine.py`.
- [ ] T005 Guarda `tests/architecture/test_startup_boundaries.py`.
- [ ] T006 Verificación: ruff format/check, mypy, pytest, `pytest tests/architecture`, diff de protegidos.
- [ ] T007 Documentación: `docs/PROGRESO.md`, `CLAUDE.md`, skills (`.claude/skills/` y `.agents/skills/`).

## Tareas humanas (Claude no las marca)

- [ ] H01 Revisión cruzada (A o B).
- [ ] H02 CI remota en Ubuntu y Windows.
- [ ] H03 El PO confirma D4 (regla 1 por instrucción) y D1 (qué es reanudar un ticket).

## Dependencias

T001 → T002 → T003 → T004 → T005 → T006 → T007.
