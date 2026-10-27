# Quickstart: validar HU-11-03

## Requisitos

- Entorno de desarrollo instalado como en la CI: `pip install -r requirements-dev.txt; pip install -e . --no-deps`.
- Sin red ni claves: todo usa `FakeProvider` y el shell real de la plataforma (bash en Linux, PowerShell en Windows).

## 1. Formato de la tarea

```powershell
pytest tests/unit/core/tasks -q
```

Esperado: pasan las pruebas nuevas (`test_task_commands.py`) y `test_task_parser.py` sigue pasando **sin cambios** (`git diff` vacío en ese archivo).

## 2. Política de llamada exacta

```powershell
pytest tests/unit/core/permissions/test_exact_calls.py -q
pytest tests/architecture -q
```

Esperado:

- Las ≥ 15 variaciones del comando (encadenamientos, argumentos extra, mayúsculas, comillas, espacios internos, tiempo mayor) obtienen `ASK` y ninguna `ALLOW` (SC-002).
- `deny` y `ask` prevalecen.
- La guarda nueva `test_exact_calls_boundaries.py` pasa.

## 3. Cableado y demostración (AC-01, AC-02)

```powershell
pytest tests/unit/test_bootstrap_task_commands.py tests/integration/test_task_commands_agent_loop.py -q
```

Esperado:

- Con la tarea de ejemplo (sección `## Comandos` como en [contracts/task_commands_format.md](contracts/task_commands_format.md)) y **sin aprobador**, el bucle ejecuta el comando de pruebas.
- El resultado empieza con `[codigo_de_salida=N]` (N ≠ 0) y contiene el nombre de la prueba fallida (AC-01, SC-001).
- La salida enorme llega con `[salida recortada: se omitieron N caracteres]`, el código y el resumen final, sin superar el máximo (AC-02, SC-003).
- Una variación del comando se deniega (`[approval_required_unavailable]`) sin crear ningún proceso.
- Sin comandos, `history_prefix` y la política se comportan como antes (SC-004).

## 4. Cierre

```powershell
ruff format --check .; ruff check .; mypy src tests; pytest --cov=harness_agent --cov-report=term-missing
git diff --exit-code (git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/loop.py tests/doubles docs/archivo tests/unit/core/tasks/test_task_parser.py
```

Esperado: las cuatro puertas en exit 0, el 100 % de cobertura en `core/tasks/` y `core/permissions/exact_calls.py`, y un diff vacío en los archivos protegidos.
