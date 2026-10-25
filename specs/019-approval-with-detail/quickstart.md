# Quickstart: validar HU-05-03

Prerrequisitos: entorno de desarrollo (`pip install -r requirements-dev.txt; pip install -e . --no-deps`).

1. Núcleo: `pytest tests/unit/core/permissions/test_approvals.py tests/core/test_loop_approval.py` → una vez, sesión, rechazo y falla cerrada.
2. CLI: `pytest tests/unit/cli/test_approval.py tests/unit/cli/test_render_approval.py` → detalle mostrado y opciones leídas.
3. Integración: `pytest tests/integration/test_approval_agent_loop.py` → bucle real, `ProtectedPolicy` real y una aprobación de sesión que no anula la denegación.
4. Bus: `pytest tests/integration/test_event_bus_agent_loop.py` → `APPROVAL_REQUESTED` llega con aprobador (test invertido).
5. Fronteras: `pytest tests/architecture`.
6. Calidad: `ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest --cov=harness_agent --cov-report=term-missing`.
7. Manual (opcional, con `fake`/doble inyectado vía `main(provider_factory=…)`): ver los tests de `tests/integration/test_bootstrap_approval.py`.

Contratos: [approval_flow.md](contracts/approval_flow.md). Modelo: [data-model.md](data-model.md).
