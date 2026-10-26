# Quickstart: validar HU-01-06

```powershell
pytest tests/unit/core/test_limits.py tests/core/test_loop_limits.py tests/integration/test_limits_agent_loop.py -q
pytest tests/unit/cli/test_render_limits.py tests/unit/test_bootstrap_limits.py -q
pytest tests/architecture -q
ruff format --check .; ruff check .; mypy src tests; pytest --cov=harness_agent --cov-report=term-missing
```

Manual (con `FakeProvider` que siempre pide una herramienta y `max_turns = 3` en `[limits]`): la terminal muestra tres rondas de herramienta y después una línea «Límite: se alcanzó el máximo de turnos (3)…»; el indicador de entrada vuelve.
