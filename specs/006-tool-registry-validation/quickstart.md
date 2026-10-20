# Quickstart: validar HU-01-02 — Registro de herramientas con esquema y validación

**Fecha**: 2026-10-18 | **Plan**: [plan.md](plan.md) | **Contrato**: [contracts/tool_registry_contract.md](contracts/tool_registry_contract.md) | **Modelo**: [data-model.md](data-model.md)

Guía para comprobar que la historia funciona de punta a punta una vez implementada. No contiene código de implementación; el detalle por microtarea irá en `tasks.md`.

## Requisitos previos

- Python 3.12, única versión soportada (PD-07).
- Dependencias de desarrollo fijadas, desde la raíz del repositorio:

```bash
python -m pip install -r requirements-dev.txt
python -m pip install -e . --no-deps
```

No hacen falta red, claves de API ni proveedor real.

## 1. Ejecutar las pruebas de la historia

```bash
pytest tests/unit tests/integration tests/contracts tests/architecture
```

Resultado esperado: todas pasan. Cada escenario de aceptación del spec tiene una prueba:

| Escenario del spec | Archivo de prueba |
|---|---|
| US1 — registrar, duplicar, esquema mal formado, atributos inválidos, consultar y listar | `tests/unit/core/tools/test_registry.py`, `test_schema_check.py` |
| US2 — campo ausente, tipo incorrecto, valor fuera de rango o enumeración, anidados, varios campos, campo no declarado, herramienta desconocida | `tests/unit/core/tools/test_schema_validator.py`, `test_registry.py` |
| US2 / AC-01 — la herramienta no se ejecuta (0 ejecuciones) y el texto es utilizable por el modelo | `tests/integration/test_tool_registry_consumer.py` |
| US3 / AC-02 — herramienta nueva sin modificar el consumidor ni el registro | `tests/integration/test_tool_registry_consumer.py` |
| Jerarquía de errores y formato de los textos para el modelo | `tests/unit/core/tools/test_errors.py` |
| Contrato del puerto `ToolRegistry` | `tests/contracts/test_tool_registry_contract.py` |
| Solo biblioteca estándar en `core/tools/` | `tests/architecture/test_core_tools_stdlib_only.py` |
| API pública de `core/tools` y de `core`, e importación sin ciclos en un intérprete nuevo (13 casos) | `tests/integration/test_core_public_api.py` |
| Parámetro opcional `schema` de `DummyTool`, retrocompatible (7 casos) | `tests/unit/test_dummy_tool_schema.py` |

## 2. Puertas de calidad (las mismas de la CI)

```bash
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
```

Resultado esperado: sin diferencias de formato, sin avisos de `ruff`, `mypy --strict` limpio y toda la suite en verde. Debe cumplirse en Windows y en Linux (la matriz de CI lo ejecuta).

## 3. Comprobar que no se tocaron los puertos

```bash
git diff --exit-code -- src/harness_agent/core/interfaces
```

Resultado esperado: sin salida y código de salida 0. También `git status --short src/harness_agent/core/interfaces` debe estar vacío.

## 4. Comprobar las fronteras del núcleo

```bash
pytest tests/architecture
```

Resultado esperado: `test_core_boundaries.py` (ya existente) y `test_core_tools_stdlib_only.py` (nuevo) en verde. `core/tools/` no importa `adapters/`, `cli/`, `observability/` ni nada fuera de la biblioteca estándar y de `harness_agent`.

> `import-linter` se cita en las skills pero no está instalado ni configurado en este repositorio, por lo que no se ejecuta `lint-imports`; las pruebas AST cubren la regla.

## 5. Recorrido manual opcional (demostración AC-01 / AC-02)

Con un intérprete de Python abierto en la raíz del repositorio (con el paquete instalado):

1. Crear un `InMemoryToolRegistry` y registrar un `DummyTool` con un esquema que tenga un campo requerido numérico con límites.
2. Pedir `validate_args` con el campo ausente: debe lanzar `ToolValidationError` y `str(error)` debe nombrar el campo; el `DummyTool` mantiene su lista de ejecuciones vacía.
3. Pedir `validate_args` con un tipo incorrecto y con un campo no declarado: mensajes que nombran cada campo, sin los valores enviados.
4. Registrar un segundo `DummyTool` con otro nombre, esquema y riesgo, y repetir con el mismo código de consulta: funciona sin cambiar nada más (AC-02).
5. Intentar registrar un nombre repetido, un nombre con espacios y un esquema con `anyOf`: cada intento lanza un error que explica el motivo y `list()` queda igual.

## Nota para quien construya la raíz de composición

`InMemoryToolRegistry()` no recibe argumentos, así que conectarlo en `bootstrap.py` será una sola línea cuando exista (la crea la historia del bucle, no esta). Las herramientas nativas (HU-01-03 en adelante) y las de MCP se registrarán ahí, nunca dentro del bucle.

## Criterios de "listo" para esta historia

- [ ] Las pruebas de los puntos 1, 2 y 4 pasan en Windows y Linux.
- [ ] El punto 3 no muestra cambios en los puertos.
- [ ] Los escenarios AC-01 y AC-02 se demuestran con el recorrido del punto 5 o con la prueba de integración.
- [ ] `docs/PROGRESO.md` registra estado, archivos y evidencia (Principio VIII).
- [ ] Revisión cruzada de otro integrante (Principio IX).
