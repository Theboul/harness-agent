# Quickstart: validar HU-02-01

Desde la raíz del worktree, con el entorno virtual activo.

```powershell
pytest tests/unit/core/context tests/integration/test_context_assembler_loop.py --cov=harness_agent.core.context --cov-report=term-missing
pytest tests/architecture
ruff format --check . ; ruff check . ; mypy src tests ; pytest
```

Resultados esperados:

- 100 % de líneas y ramas en `harness_agent/core/context/`.
- Prefijo idéntico en 20 turnos simulados (SC-001) y tras cambiar las herramientas a mitad de sesión.
- Tras `record_usage`, la estimación del mismo contenido coincide con el consumo informado (SC-002).
- `git diff --exit-code $(git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/loop.py tests/doubles docs/archivo` sin salida.

Detalles: [contracts/context_assembler.md](contracts/context_assembler.md) · [data-model.md](data-model.md).
