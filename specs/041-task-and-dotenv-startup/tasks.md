# Tareas: HU-00-08.1 — Tarea desde el comando y `.env` (propuesta)

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · Pruebas primero; `--basetemp` corto (`/c/tmp/pt41`).
**Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`.
**Mapeo a plan de sprints**: extensión de HU-00-08 (arranque); sin tarea `SpN-xx` propia (historia propuesta), presupuesto estimado 60 min.

- [x] T001 [US2] Pruebas `tests/unit/adapters/system/test_dotenv.py` y adaptador `adapters/system/dotenv.py` (+ API de `adapters/system/__init__.py`).
- [x] T002 [US1] Pruebas `tests/unit/test_bootstrap_arguments.py` y `bootstrap.py`: `parse_arguments`, `entry`, `main(argv=, gh_runner=, changes=)`, `.env` y tarea; `__main__.py` y `pyproject.toml`.
- [x] T003 [US1][US2] Integración `tests/integration/test_main_with_task.py` (extremo a extremo con `FakeProvider`: tarea → criterios → revisión del diff).
- [x] T004 Guarda `tests/architecture/test_dotenv_boundaries.py` y ajuste de `test_bootstrap_boundaries.py` (`adapters.tasks` en la API pública).
- [ ] T005 `.env.example` con ejemplos vacíos. **Pendiente: los permisos de la sesión impiden editar `.env.example`.**
- [x] T006 Verificación de fronteras (`verificar-fronteras-hexagonales`): `pytest tests/architecture`; diff de protegidos vacío; lista de `capas-y-reglas.md`.
- [x] T007 Cuatro puertas de calidad: ruff format, ruff check y mypy en 0; `pytest` 8186 pasadas con 3 fallos solo en la ejecución completa (pruebas de árboles de procesos de `adapters/system`, que pasan solas; ver PROGRESO).
- [x] T008 Documentación: `docs/PROGRESO.md` (fila propuesta, En revisión), `CLAUDE.md` (tabla y convención), `.specify/feature.json`.

## Tareas humanas (Claude no las marca)

- [ ] H01 Revisión cruzada (A o B).
- [ ] H02 CI remota en Ubuntu y Windows.
- [ ] H03 El PO aprueba la historia propuesta y los nombres de las opciones.
- [ ] H04 Reinstalar el paquete editable (`pip install -e . --no-deps`) para que `harness` use `entry`.

## Dependencias

T001 → T002 → T003; T004 tras T001–T002; T005 libre; T006 → T007 → T008.
