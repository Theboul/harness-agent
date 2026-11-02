# Tareas: HU-06-06 — Varios modelos por alias y modo de planificación

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · `--basetemp` corto (`/c/tmp/pt49`).
**Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`.
**Mapeo a plan de sprints**: historia propuesta; sin tarea `SpN-xx`.

- [x] T001 `tests/unit/core/permissions/test_mode_switch.py` + `core/permissions/mode_switch.py` (`ReadOnlySwitch`, `SwitchablePolicy`) + exports. Prueba primero.
- [x] T002 `tests/unit/adapters/providers/test_model_switch.py` + `adapters/providers/model_switch.py` (`ModelSwitch` y errores).
- [x] T003 `tests/unit/test_config_models.py` + `config.py` (`[models]`, `ModelAlias`) + `config.example.toml`.
- [x] T004 pruebas de `cli/session_commands.py` + texto de `/model` con alias y modo.
- [x] T005 `tests/unit/test_bootstrap_models.py` + `bootstrap.py` (`compose`, `/model`, `/plan`, `/implementar`, modelo activo en compactador, renovador y `/nueva`).
- [x] T006 `tests/integration/test_model_switching_agent_loop.py` con `AgentLoop` real (AC-01, AC-03).
- [x] T007 Guarda `tests/architecture/test_model_switch_boundaries.py` y verificación de fronteras; diff de protegidos vacío.
- [x] T008 README (sección corta), `CLAUDE.md` (fila), `docs/04c` (ficha), `docs/PROGRESO.md`, `.specify/feature.json`.
- [x] T009 Cuatro puertas de calidad y cobertura 100 % de lo nuevo (`ruff` y `mypy` en 0; `pytest` 8689 pasadas, 48 omitidas; cobertura total 99 %).

## Análisis de consistencia (speckit-analyze)

FR-001/002→T003; FR-003→T002; FR-004→T001; FR-005→T004/T005; FR-006→T007. AC-01/AC-03→T006; AC-02→T002/T005; AC-04→T005; AC-05→T003/T005. Sin contradicciones.

## Tareas humanas (Claude no las marca)

- [ ] H01 Revisión cruzada (A o B).
- [ ] H02 CI remota en Ubuntu y Windows.
- [ ] H03 Ratificación del PO (ID HU-06-06 y AC-01 a AC-05) y de A/B/C del cambio mínimo en `cli/session_commands.py`.
- [ ] H04 Prueba manual con claves reales de Gemini y Groq (el historial viaja entre proveedores).
