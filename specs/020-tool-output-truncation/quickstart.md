# Quickstart: validar HU-02-02

Desde la raíz del repositorio, con el entorno virtual activo y `pip install -r requirements-dev.txt; pip install -e . --no-deps`.

## 1. Pruebas de la historia

```powershell
pytest tests/unit/core/tools/test_output_limit.py tests/unit/core/tools/test_registry_output_limit.py tests/unit/test_config_max_tool_output_chars.py tests/unit/test_bootstrap_tool_output_limit.py tests/integration/test_tool_output_truncation.py tests/architecture/test_output_limit_boundaries.py
```

Esperado: todas pasan, sin omitidas por plataforma; `core/tools/output_limit.py` al 100 % de líneas y ramas (`--cov-report=term-missing`).

## 2. Comportamiento a mano

```python
from harness_agent.core import truncate_output
out = truncate_output("a" * 10 + "z" * 100_000, 1_000)
assert len(out) <= 1_000 and out.startswith("aaaa") and out.endswith("zzzz")
assert "[salida recortada: se omitieron" in out
```

## 3. Configurar el máximo

En `config.toml`:

```toml
[limits]
max_tool_output_chars = 12000   # entero >= 256; por defecto 24000
```

Un valor menor que 256, un texto o un booleano se rechaza al cargar con un mensaje en español.

## 4. Cierre

Los cuatro comandos de calidad y `pytest tests/architecture` en exit 0 (ver `CLAUDE.md`).
