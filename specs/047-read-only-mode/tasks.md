# Tareas: HU-05-07 — Modo de solo lectura

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · `--basetemp` corto (`/c/tmp/pt47`).
**Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`, pruebas de integración de MCP.
**Mapeo a plan de sprints**: Sp3-33 (HU-05-07, opc.), 1,5 pt.

- [x] T001 `tests/unit/core/permissions/test_git_read_only.py` + `core/permissions/git_reads.py` (`only_git_reads`) + export. Prueba primero.
- [x] T002 `tests/unit/core/permissions/test_read_only.py` + `core/permissions/read_only.py` (`ReadOnlyPolicy`) + exports.
- [x] T003 `tests/unit/test_config_read_only.py` + `config.py` (`read_only`) + `config.example.toml`.
- [x] T004 `tests/unit/test_bootstrap_read_only.py (clase TestArguments)` + `bootstrap.py` `--solo-lectura`.
- [x] T005 `tests/unit/test_bootstrap_read_only.py` + `bootstrap.py` (`compose(read_only=)`, cadena, aviso) + `cli/session_commands.py` (`/model`).
- [x] T006 `tests/integration/test_read_only_agent_loop.py` con `AgentLoop` real (AC-01).
- [x] T007 Guarda `tests/architecture/test_read_only_boundaries.py` y verificación de fronteras (`pytest tests/architecture`); diff de protegidos vacío.
- [x] T008 Cuatro puertas de calidad y cobertura 100 % del módulo nuevo (`ruff`, `mypy` en 0; `pytest` 8583 pasadas, 48 omitidas; `read_only.py` y `git_reads.py` 100 %).
- [x] T009 Documentación: `docs/PROGRESO.md`, `CLAUDE.md` (fila), `.specify/feature.json`.

## Análisis de consistencia (speckit-analyze)

Cada FR tiene tarea (FR-001/002/003→T002, FR-004→T001, FR-005→T003/T005, FR-006→T004, FR-007→T005, FR-008→T007); AC-01 → T006. Sin contradicciones entre spec, plan y tareas.

## Tareas humanas (Claude no las marca)

- [ ] H01 Revisión cruzada (A o B).
- [ ] H02 CI remota en Ubuntu y Windows.
- [ ] H03 A y B ratifican `ReadOnlyPolicy` (regla nueva de permisos) y el cambio mínimo en `cli/session_commands.py`.
- [ ] H04 El PO decide si el modo debe permitir una tabla de lecturas del shell (`ls`, `cat`…).

## Dependencias

T001 → T002 → T005 → T006; T003 → T005; T004 → T005; T007 → T008 → T009.
