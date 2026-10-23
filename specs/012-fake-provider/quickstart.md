# Quickstart: HU-00-03 — Proveedor simulado para pruebas

## Prerrequisitos

```bash
source .venv/bin/activate       # Python 3.12 con requirements-dev.txt
git switch 012-fake-provider
```

## 1. Los cuatro pasos de CI

```bash
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
```

Esperado: los cuatro terminan con código 0; el módulo `fake_provider.py` y los errores nuevos al 100 %.

## 2. Pruebas de la historia

```bash
pytest tests/unit/core/test_provider_errors.py \
       tests/unit/doubles/test_fake_provider.py \
       tests/contracts/test_fake_provider_contract.py \
       tests/integration/test_fake_provider_agent_loop.py \
       tests/architecture/test_provider_errors_boundaries.py -q --no-cov
```

Esperado: todas pasan, sin red.

## 3. Recorrido manual (AC-01 y AC-02)

1. Importar los errores: `python -c "from harness_agent.core import QuotaExceeded, ProviderError; print(issubclass(QuotaExceeded, ProviderError))"` → `True`.
2. Ejecutar la prueba de integración con `-k determinism`: el mismo guion de tres pasos da el mismo resultado 20 veces.
3. Ejecutar `-k quota`: el evento de error del proveedor lleva `error_type == "QuotaExceeded"`.
4. Ejecutar `-k no_network`: la fixture de red bloqueada no registra ninguna conexión.

## 4. Archivos protegidos

```bash
base=$(git merge-base HEAD origin/main)
git diff --exit-code "$base" -- docs/archivo src/harness_agent/core/loop.py \
  tests/doubles/scripted_provider.py tests/doubles/dummy_provider.py
```

Esperado: código 0 (la historia no los toca).

## 5. Detalle que queda para humanos

- Visto bueno de A a la ampliación aditiva de `provider.py`.
- CI en Windows y Linux; HU-00-01 sigue pendiente de aprobación técnica.
