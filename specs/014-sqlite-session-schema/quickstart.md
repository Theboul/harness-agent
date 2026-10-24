# Quickstart: HU-03-01

## Prerrequisitos

```bash
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt   # Python 3.12
```

## 1. Las cuatro puertas de CI

```bash
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
```

Esperado: exit 0 en las cuatro; `adapters/storage` al 100 % de líneas y ramas.

## 2. Pruebas de la historia y fronteras

```bash
pytest tests/unit/adapters/storage tests/architecture -q --no-cov
```

## 3. Recorrido manual (AC-01 y regla 1)

Con un script fuera del repositorio: abrir `SqliteSessionStore` sobre un archivo temporal, `create_session(goal=...)`, crear una hija con `parent_id`, cerrar, reabrir y comprobar `get_session` y `list_sessions`.

Contrato: [contracts/sqlite_session_store_contract.md](contracts/sqlite_session_store_contract.md). Tablas: [data-model.md](data-model.md).
