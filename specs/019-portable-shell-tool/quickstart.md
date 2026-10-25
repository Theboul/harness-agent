# Quickstart: HU-01-04 — Herramienta de shell portable

## Prerrequisitos

```bash
# Python 3.12 con requirements-dev.txt (igual que la CI)
git switch feat/hu-01-04-shell-tool
```

## 1. Los cuatro pasos de CI

```bash
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
```

Esperado: los cuatro terminan con código 0; los módulos nuevos de `adapters/system` y `adapters/tools` al 100 % de líneas y ramas (salvo lo exclusivo de plataforma, cubierto por las pruebas con plataforma inyectada y las marcadas).

## 2. Pruebas de la historia

```bash
pytest tests/unit/adapters/system tests/unit/adapters/tools/test_shell_tool.py \
       tests/contracts/test_shell_contract.py tests/integration/test_shell_agent_loop.py \
       tests/unit/test_bootstrap_shell.py tests/architecture/test_adapters_boundaries.py -q --no-cov
```

## 3. Recorrido manual (AC-01 a AC-04)

1. **AC-01**: `pytest tests/unit/adapters/system/test_subprocess_shell.py -k timeout -q --no-cov`: un `sleep` más largo que el plazo vuelve marcado como tiempo agotado, el proceso hijo también termina.
2. **AC-02**: `-k selection`: `Windows` → PowerShell, `Linux` → bash; las pruebas reales ejecutan un comando que imprime el intérprete.
3. **AC-03**: `pytest tests/unit/test_bootstrap_shell.py -q --no-cov`: el historial inicial empieza con el mensaje de sistema del entorno.
4. **AC-04**: la misma suite corre en `ubuntu-latest` y `windows-latest`; en local se confirma con `pytest -rs` que las únicas omisiones son las marcadas por plataforma, con motivo.
5. **Aprobación obligatoria**: en `tests/integration/test_shell_agent_loop.py`, con la política real, la llamada se pregunta, se deniega sin aprobador y no lanza ningún proceso.

## 4. Archivos protegidos

```bash
base=$(git merge-base HEAD origin/main)
git diff --exit-code "$base" -- docs/archivo src/harness_agent/core src/harness_agent/config.py src/harness_agent/cli tests/doubles
```

Esperado: código 0 (la historia no los toca; solo cambia `bootstrap.py` entre los archivos de composición).

## 5. Detalle que queda para humanos

- Revisión cruzada por A o B; HU-00-01 sigue pendiente de aprobación técnica.
- CI en Linux y Windows (nada está subido).
- Confirmación del PO de la lista de comandos denegados por defecto y de los supuestos «por confirmar» de la spec (carpeta de partida, formato del resultado, recorte).
