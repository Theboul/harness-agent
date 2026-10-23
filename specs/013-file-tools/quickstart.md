# Quickstart: HU-01-03 — Herramientas de archivos

## Prerrequisitos

```bash
source .venv/bin/activate       # Python 3.12 con requirements-dev.txt
git switch feat/hu-01-03-file-tools
```

## 1. Los cuatro pasos de CI

```bash
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
```

Esperado: los cuatro terminan con código 0; `adapters/system` y `adapters/tools` al 100 % de líneas y ramas.

## 2. Pruebas de la historia

```bash
pytest tests/unit/adapters tests/contracts/test_authorized_area_contract.py \
       tests/integration/test_file_tools_agent_loop.py \
       tests/architecture/test_adapters_boundaries.py -q --no-cov
```

## 3. Recorrido manual (AC-01 a AC-04)

1. **AC-01**: en la integración, `-k TestRead`: lee un archivo del área y una ruta inexistente devuelve `[no_existe]`.
2. **AC-02**: `-k TestWriteInside`: la escritura dentro se ejecuta y el evento de decisión es «allow»; `-k TestWriteOutside`: se pregunta, se deniega y no se crea el archivo.
3. **AC-03**: `pytest tests/unit/adapters/tools/test_escape_attempts.py -q --no-cov`: ninguna ruta hostil escribe fuera.
4. **AC-04**: `-k TestNoArea`: sin `workspace_root` nada se ejecuta.
5. **Windows**: en la CI de `windows-latest` corren las pruebas marcadas por plataforma; en Linux, las sintéticas de `windows_path_problem`.

## 4. Archivos protegidos

```bash
base=$(git merge-base HEAD origin/main)
git diff --exit-code "$base" -- docs/archivo src/harness_agent/core src/harness_agent/config.py tests/doubles
```

Esperado: código 0 (la historia no los toca).

## 5. Detalle que queda para humanos

- Revisión cruzada por A o B; HU-00-01 sigue pendiente de aprobación técnica.
- CI en Linux y Windows.
- Confirmación del PO de la regla de lectura de HU-05-01 y de los dos puntos «por confirmar» de la spec.
