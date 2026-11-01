# Plan: HU-00-07 — Cobertura mínima y prueba de instalación

## Resumen técnico

Solo CI, configuración de pytest y pruebas. Sin código de producción.

## Constitution Check y skills

**arquitectura-hexagonal-clean** — Decision Gates: ¿regla en `core/`? no. ¿Puerto? no. ¿Adaptador? no. ¿Conexión en `bootstrap.py`? no. ¿Prueba? sí (`tests/install`, `tests/unit`). Lista de `capas-y-reglas.md`: núcleo sin cambios — sí; sin imports nuevos en `core/`, `cli/` ni `adapters/` — sí; puertos y eventos intactos — sí; dependencias nuevas — no (el CI solo usa `coverage`, ya instalado con `pytest-cov`).

**estructura-carpetas-harness** — rutas nuevas:

| Archivo | Fila que lo justifica |
|---|---|
| `tests/install/test_clean_install.py` | pruebas que levantan procesos y un entorno reales y no encajan en `unit/` ni `integration/` (carpeta nueva anotada en `references/arbol.md` de `.claude` y `.agents`) |
| `tests/unit/test_ci_quality_gates.py` | espejo de `tests/unit/test_dependency_pins.py` (lee `ci.yml` y `pyproject.toml`) |
| `specs/046-coverage-install-check/` | artefactos Spec Kit |

**verificar-fronteras-hexagonales** — la historia toca `pyproject.toml` y `ci.yml`: sin dependencias nuevas; `pytest tests/architecture` en verde; la CI sigue en Ubuntu y Windows, Python 3.12.

## Diseño

- `pyproject.toml`: `addopts` añade `-m 'not install'` y se registra la marca `install`.
- `ci.yml`: `--cov-fail-under=95` en el paso de pytest; paso `coverage report … --fail-under=60` sobre `core/`; paso `pytest -m install --no-cov tests/install`.
- `tests/install/test_clean_install.py`: fixture de módulo que crea el venv (una vez), instala con `--no-deps` y cuatro pruebas sobre el entorno instalado con un entorno de procesos mínimo (sin claves ni `HARNESS_CONFIG`, carpeta de trabajo vacía).
- `test_ci_quality_gates.py` fija que el umbral aparece una vez, es ≥ 60, que el paso de instalación existe y que la marca está excluida por defecto.
