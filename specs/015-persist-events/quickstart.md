# Quickstart: HU-03-02

## Prerrequisitos

```bash
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt   # Python 3.12
```

La rama parte de `feat/hu-03-01-sqlite-session-schema`.

## 1. Las cuatro puertas de CI

```bash
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
```

Esperado: exit 0 en las cuatro (salvo el test de ruta larga de Windows ya conocido); `adapters/storage` al 100 % de líneas y ramas.

## 2. Pruebas de la historia y fronteras

```bash
pytest tests/unit/adapters/storage tests/contracts/test_session_store_contract.py \
       tests/integration/test_session_store_abrupt_close.py \
       tests/integration/test_event_recorder_agent_loop.py tests/architecture -q --no-cov
```

## 3. Recorrido manual (AC-01 y AC-02)

Con un script fuera del repositorio: crear una sesión, guardar un evento, terminar el proceso con `os._exit(0)` y reabrir el archivo; comprobar `load_session` y `PRAGMA integrity_check`.

Contrato: [contracts/session_store_events_contract.md](contracts/session_store_events_contract.md). Datos: [data-model.md](data-model.md).
