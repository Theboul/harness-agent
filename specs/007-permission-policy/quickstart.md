# Quickstart: verificar HU-05-01 — Política denegar, preguntar, permitir que falla cerrada

**Spec**: [spec.md](spec.md) · **Contratos**: [contracts/policy_contract.md](contracts/policy_contract.md), [contracts/permissions_config_contract.md](contracts/permissions_config_contract.md) · **Plan**: [plan.md](plan.md)

Guía de validación para quien implemente o revise la historia. No contiene código de la implementación.

## Requisitos previos

- Python 3.12 y el entorno virtual del proyecto con las versiones de `requirements-dev.txt` (en Windows, `.venv\Scripts\python.exe`).
- Árbol de trabajo en la rama `gustavo`, sin cambios en `core/interfaces/`, `core/loop.py`, `core/events.py`, el bus, `cli/`, `tests/doubles/` ni `docs/archivo/`.

## 1. Ejecutar las pruebas de la historia

```bash
pytest tests/unit/core/permissions tests/unit/test_config_permissions.py
pytest tests/contracts/test_permission_policy_contract.py
pytest tests/integration/test_permission_policy_agent_loop.py
pytest tests/architecture/test_permissions_boundaries.py
```

Resultado esperado: todas pasan; sin red, sin entorno real.

## 2. Puertas de calidad (las mismas de la CI)

```bash
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
```

Resultado esperado: los cuatro terminan con código 0; `core/permissions/rules.py`, `core/permissions/policy.py` y `config.py` quedan al 100 % (toda línea sin cubrir se justifica por escrito); las pruebas existentes del bucle (`tests/core`) siguen pasando sin modificarlas.

## 3. Comprobar que no se tocaron los archivos protegidos

```bash
git fetch origin
base=$(git merge-base HEAD origin/main)
git diff --exit-code $base -- src/harness_agent/core/interfaces src/harness_agent/core/loop.py src/harness_agent/core/events.py src/harness_agent/core/in_memory_event_bus.py src/harness_agent/cli tests/doubles docs/archivo
pytest tests/architecture
```

Resultado esperado: el `git diff` termina con código 0 y sin salida; las pruebas de arquitectura pasan (incluida `test_permissions_boundaries.py`).

## 4. Recorrido manual opcional

Con un intérprete de Python abierto en la raíz del repositorio (con `PYTHONPATH=src`), un registro con tres herramientas de prueba (`leer`, riesgo bajo; `escribir`, riesgo medio; `ejecutar`, riesgo alto), un área sobre un directorio temporal y las reglas por defecto:

1. `escribir` con `path` dentro del área → permitir; con `path` fuera del área (`..`, absoluta) → preguntar; sin `path` → denegar.
2. `leer` con `path` dentro del área → permitir; fuera → preguntar; sin `path` → preguntar; con `allow_reads_in_area=False` → preguntar.
3. `ejecutar` (riesgo alto) → preguntar siempre; una herramienta no registrada → preguntar.
4. Reglas `deny=("escribir",)`: `escribir` dentro del área → denegar. Reglas `ask=("leer",)`: `leer` dentro del área → preguntar.
5. Una `AuthorizedArea` cuyo `contains` lanza una excepción → denegar; sin área (`area=None`) → toda escritura y lectura → preguntar.
6. Con el bucle real (`make_rig` de `tests/core/support.py`) y la política real: una acción que resulta en «preguntar» no ejecuta la herramienta, el modelo recibe `[approval_required_unavailable] …` y el bus publica `PERMISSION_DECIDED`.
7. Un `config.toml` con `[permissions] deny = ["x"]` se carga; con `allow = ["x"]` o `deny = [""]`, `load_config` lanza `InvalidConfigError` nombrando el campo.

## Criterios de «listo» para esta historia

- [ ] Las pruebas de la sección 1 pasan y la sección 2 termina con código 0 en los cuatro comandos.
- [ ] La sección 3 no muestra diferencias en los archivos protegidos.
- [ ] El contrato único se ejecuta contra `ScriptedPolicy` y contra la política real; la matriz exhaustiva confirma que solo se permite cuando se cumplen todas las condiciones.
- [ ] `docs/PROGRESO.md` tiene la fila de HU-05-01 en `En revisión` (nunca `Hecha` antes de la revisión cruzada y la CI), el registro de cada tarea y la observación del supuesto de lectura pendiente de confirmación del PO.
- [ ] Revisión cruzada por A o B y CI en Linux y Windows pendientes de confirmación humana; HU-00-01 sigue pendiente de aprobación técnica.
