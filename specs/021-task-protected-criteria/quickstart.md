# Quickstart: validar HU-11-01

Prerrequisitos: `.venv` con Python 3.12 y `pip install -r requirements-dev.txt; pip install -e . --no-deps`.

1. **Calidad**: `ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest --cov=harness_agent --cov-report=term-missing` → exit 0; `pytest tests/architecture` → exit 0.
2. **AC-01 y AC-02** (pruebas de integración): `pytest tests/integration/test_task_start.py` — tarea válida → sesión, filas con `passes` falso, copia de solo lectura; sin criterios → rechazo sin rastro.
3. **AC-03**: `pytest tests/integration/test_task_protection_agent_loop.py` — con el bucle y la política reales, las cinco herramientas sobre `.harness/` se deniegan; alterar o borrar la copia → restauración y evento `criteria_tampered`.
4. **Migración**: `pytest tests/unit/adapters/storage/test_schema_migration.py` — base v1 con datos pasa a v2 sin perderlos.
5. **Manual (opcional)**: crear `tarea.md` según [contracts/task_format.md](contracts/task_format.md), llamar `compose(config, task=parse_task(texto))` desde un script y abrir `.harness/tareas/<sesión>/criterios.json`; modificarlo y llamar `verify_export`.
6. **Archivos protegidos**: `git diff --exit-code $(git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/loop.py src/harness_agent/cli tests/doubles docs/archivo` → exit 0.
