# Tareas: HU-11-08.1 — Archivo de progreso del ticket con puntos de control

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · Pruebas primero (verlas fallar por la razón esperada); cada tarea cierra con ruff/mypy/pytest. `--basetemp` corto (`/c/tmp/pt37`).
**Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`; tampoco `adapters/mcp/` ni `config_mcp.py` (otra sesión).
**Mapeo a plan de sprints**: tarea de B del carril de continuidad del ticket (1 PHU de la ficha).

- [x] T001 [US1] `core/progress/snapshot.py` + `render.py` (+ `__init__`): instantánea, formato fijo, `progress_file_name`, saneo a una línea. Prueba: `tests/unit/core/progress/test_render.py` (formato exacto, estados, nombre seguro, centinela, credenciales de URL).
- [x] T002 [US1][US2] `core/progress/recorder.py`: `ProgressRecorder` (turnos, final, última respuesta, fallos → aviso, cancelación propagada). Prueba: `tests/unit/core/progress/test_recorder.py`.
- [x] T003 [US2][US3] `adapters/storage/progress_file.py` (+ API de `adapters/storage/__init__.py`): escritura atómica, lectura, sin temporales. Prueba: `tests/unit/adapters/storage/test_progress_file.py` (fallo entre temporal y renombrado conserva lo anterior; enlace simbólico; nombre inválido; subproceso terminado de golpe).
- [x] T004 [US1][US2] `bootstrap.py`: `Composition.progress`, creación en `compose` (tarea + área) y llamadas en `run_session`. Prueba: `tests/integration/test_progress_session.py` (turno, `/salir`, sin tarea no escribe, un fallo de escritura no tumba, Ctrl-C no escribe el final).
- [x] T005 Guarda `tests/architecture/test_progress_boundaries.py` (a partir de `verificar-fronteras-hexagonales/assets/test_module_boundaries.py`); ajustar `test_bootstrap_boundaries.py` si hace falta.
- [x] T006 Verificación: `ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest`, `pytest tests/architecture`; diff de archivos protegidos vacío; lista de `capas-y-reglas.md`.
- [x] T007 Documentación: `docs/PROGRESO.md`, `CLAUDE.md` (tabla y convención), skills `estructura-carpetas-harness` y `verificar-fronteras-hexagonales` en `.claude/skills/` y `.agents/skills/`.

## Tareas humanas (Claude no las marca)

- [ ] H01 Revisión cruzada (A o C).
- [ ] H02 CI remota en Ubuntu y Windows.
- [ ] H03 El PO confirma el contenido de «Hecho» (sin commits).

## Dependencias

T001 → T002 → T003 (paralela a T002) → T004 → T005 → T006 → T007.
