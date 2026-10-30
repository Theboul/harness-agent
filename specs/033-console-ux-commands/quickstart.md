# Quickstart — validar HU-06-05

Desde la raíz del repo con el venv activo.

## 1. Las puertas de calidad

```powershell
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing --basetemp=C:\tmp\pt
pytest tests/architecture
```

Resultado esperado: exit 0 en las cinco.

## 2. Pruebas de la historia

```powershell
pytest tests/unit/cli tests/integration/test_console_commands.py tests/architecture/test_console_ux_boundaries.py
```

## 3. Prueba a mano con el proveedor simulado

`python -m harness_agent` con `model = "fake/test"` no es válido con el proveedor real (arranque falla cerrado); la prueba manual real es con Gemini (`GEMINI_API_KEY` en el entorno, `config.toml` con `model = "gemini/…"`):

1. Escribe una tarea que use `shell`: debe verse el bloque de aprobación (AC-01), `[..] shell: ejecutando` y `[ok] shell: correcto (…)`.
2. `/ayuda` lista `/sesiones /nueva /reanudar /compactar /model` (AC-08).
3. `/model` muestra modelo y límites sin clave (AC-07). `/sesiones` (AC-04), `/nueva` (AC-05), `/compactar` (AC-06).
4. `set NO_COLOR=1` (o redirigir a un archivo): sin códigos ANSI (AC-09).
