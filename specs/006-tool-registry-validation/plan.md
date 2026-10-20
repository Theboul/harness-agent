# Implementation Plan: HU-01-02 — Registro de herramientas con esquema y validación

**Branch**: `006-tool-registry-validation` | **Date**: 2026-10-18 | **Spec**: [specs/006-tool-registry-validation/spec.md](spec.md)

**Input**: Feature specification from `/specs/006-tool-registry-validation/spec.md`

**Directrices del usuario**: Python 3.12, solo biblioteca estándar en `core/`; `ToolRegistry` concreto en memoria que implemente el contrato de `core/interfaces/tool.py`; validador de esquema mínimo propio; pruebas con pytest y `DummyTool`; respetar las skills `arquitectura-hexagonal-clean` y `estructura-carpetas-harness`; **no modificar los puertos**.

---

## Summary

Implementar el registro de herramientas como una clase concreta en memoria (`InMemoryToolRegistry`) que cumple el contrato `ToolRegistry` ya acordado en HU-00-01, junto con un validador propio de un subconjunto mínimo de JSON Schema, todo en Python puro dentro de `core/tools/`. El registro valida la definición de cada herramienta al registrarla (nombre, descripción, nivel de riesgo y esquema), rechaza duplicados y, en cada llamada, valida los argumentos antes de que nada se ejecute; ante un incumplimiento lanza un error de dominio cuyo texto, redactado en español y sin reproducir valores, nombra cada campo inválido y está listo para devolverse al modelo (AC-01). Como el bucle solo conoce el puerto `ToolRegistry` y la interfaz `Tool`, incorporar una herramienta nueva consiste únicamente en registrarla (AC-02). Los puertos de `core/interfaces/` no se tocan: las excepciones nuevas heredan de `ValueError`, que es lo que el contrato ya declara.

---

## Technical Context

**Language/Version**: Python 3.12, única versión soportada (PD-07): `pyproject.toml` fija `requires-python >=3.12,<3.13`, `mypy` usa 3.12, `ruff` apunta a `py312` y la CI (`.github/workflows/ci.yml`) prueba solo 3.12.

**Primary Dependencies**: solo biblioteca estándar en `core/tools/` (`copy`, `dataclasses`, `json`, `math`, `re`, `typing`). Sin dependencias nuevas de ejecución ni de desarrollo; se reutilizan `pytest`, `pytest-asyncio`, `pytest-cov`, `mypy` y `ruff`, ya fijadas en `requirements-dev.txt`.

**Storage**: N/A. El catálogo vive en memoria durante la sesión; persistirlo está fuera de alcance.

**Testing**: `pytest` con `DummyTool` (ampliado de forma retrocompatible con un parámetro `schema` opcional). Pruebas unitarias, de contrato, de integración con un consumidor mínimo que imita al bucle, y de arquitectura (solo biblioteca estándar en `core/tools/`). Sin red ni proveedor real.

**Target Platform**: Windows y Linux (matriz de CI: `ubuntu-latest` y `windows-latest`, Python 3.12).

**Project Type**: Biblioteca modular (núcleo de una arquitectura hexagonal).

**Performance Goals**: validación de una llamada con un esquema de hasta 20 campos en menos de 10 ms de media (SC-005). El algoritmo es lineal en el tamaño de los argumentos y del esquema.

**Constraints**:
1. `core/interfaces/*` queda sin modificar (verificable con `git diff`).
2. Cero importaciones fuera de la biblioteca estándar y de `harness_agent` en `core/tools/` (Principio III, RNF-12/13).
3. `mypy --strict` sobre `src` y `tests`; `ruff` con línea de 100 columnas.
4. Sin herramientas concretas, shell, bucle ni `bootstrap.py` (Principio VI; el spec acota el alcance).
5. Falla cerrada: lo que el validador no entiende (palabras clave no soportadas, esquema raíz que no es objeto) se rechaza al registrar, no se ignora.

**Scale/Scope**: 1 clase concreta, 2 funciones públicas de validación, 6 tipos de error o de datos, 4 módulos de código fuente y 8 módulos de prueba nuevos.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / Restricción | Requisito | Pre-diseño | Post-diseño | Evidencia |
|---|---|---|---|---|
| **I** | Una historia por especificación | PASS | PASS | Solo HU-01-02. El spec y el plan no incluyen HU-01-03, HU-01-04 ni HU-05-xx. |
| **II** | Microtareas de 15–40 min (máx. 60) | PASS | PASS | Los módulos son pequeños y separables (errores, validador de definición, validador de argumentos, registro, pruebas); `/speckit-tasks` los dividirá. |
| **III** | Python 3.12+, tipado, hexagonal, `core/` sin libs externas | PASS | PASS | `core/tools/` solo importa biblioteca estándar y `harness_agent.core`; tipado estricto; sin SDK ni UI. Ver R-01 y R-02 en [research.md](research.md). |
| **IV** | Pruebas automatizadas, calidad y CI en Windows y Linux | PASS | PASS | Pruebas sin red con `DummyTool`; `ruff`, `mypy --strict` y `pytest` en la matriz existente. |
| **V** | Criterios de aceptación inmutables | PASS | PASS | AC-01 y AC-02 se verifican tal como están redactados (ver Trazabilidad). |
| **VI** | Sin código de sprints futuros | PASS | PASS | Sprint 1. No se crea bucle, política de permisos, herramientas reales, MCP ni `bootstrap.py`. |
| **VII** | Consulta documental quirúrgica | PASS | PASS | Se leyeron solo la ficha HU-01-02, el contrato `ToolRegistry`, la constitución y las skills pedidas. |
| **VIII** | Registro en `docs/PROGRESO.md` | PASS | PASS | Registro por tarea (regla «Registro» de `tasks.md`), `En curso` en T001, consolidación de la fila en T021 y confirmación de la CI en T023. |
| **IX** | Definition of Done y revisión humana | PASS | PASS | Revisión cruzada por A o B antes de marcar la historia como `Hecha`; CI en ambos sistemas. |
| **X** | `docs/archivo/` inmutable | PASS | PASS | No se toca. |
| **Falla cerrada** | Lo ambiguo se deniega | PASS | PASS | Campos no declarados rechazados (aclaración 1 del spec); palabras clave no soportadas rechazadas al registrar (R-03). |
| **Hexagonal** | `core/` no importa `adapters/`, `cli/`, SDK; puertos intactos | PASS | PASS | El registro no necesita nada externo, por lo que es regla de negocio del núcleo y no un adaptador (R-01). |

**Resultado del gate**: sin violaciones; no se requiere sección de justificación de complejidad.

---

## Project Structure

### Documentation (this feature)

```text
specs/006-tool-registry-validation/
├── spec.md                          # Especificación (con 2 aclaraciones)
├── plan.md                          # Este archivo
├── research.md                      # Fase 0: decisiones y alternativas
├── data-model.md                    # Fase 1: tipos, errores y reglas de validación
├── quickstart.md                    # Fase 1: guía de validación ejecutable
├── contracts/
│   └── tool_registry_contract.md    # Fase 1: comportamiento observable y subconjunto de esquema
├── checklists/
│   └── requirements.md              # Checklist de calidad del spec
└── tasks.md                         # Fase 2 (/speckit-tasks; NO lo crea este comando)
```

### Source Code (repository root)

Archivos nuevos (N) y modificados (M). **No se modifica ningún archivo de `src/harness_agent/core/interfaces/`.**

```text
src/harness_agent/
└── core/
    ├── __init__.py                    # M: reexporta la API pública de core/tools
    ├── interfaces/                    # SIN CAMBIOS (puertos de HU-00-01)
    │   └── tool.py                    #    Tool, ToolRegistry, RiskLevel
    └── tools/                         # N: carpeta prevista en el árbol acordado
        ├── __init__.py                # N: API pública del subpaquete
        ├── errors.py                  # N: Violation y jerarquía de errores de dominio
        ├── schema_validator.py        # N: check_schema() y validate_arguments() (stdlib)
        └── registry.py                # N: InMemoryToolRegistry (implementa ToolRegistry)

tests/
├── doubles/
│   └── dummy_tool.py                  # M: parámetro opcional `schema` (retrocompatible)
├── unit/                              # N: refleja src/harness_agent/
│   ├── __init__.py
│   ├── test_dummy_tool_schema.py      # N: parámetro `schema` de DummyTool (T001)
│   └── core/
│       ├── __init__.py
│       └── tools/
│           ├── __init__.py
│           ├── test_errors.py             # N: jerarquía de errores y formato de los mensajes
│           ├── test_schema_check.py       # N: definición de esquemas válidos e inválidos
│           ├── test_schema_validator.py   # N: cada tipo de violación de argumentos
│           └── test_registry.py           # N: registrar, consultar, listar, validar (HU-01-02 US1/US2)
├── integration/                       # N
│   ├── __init__.py
│   └── test_tool_registry_consumer.py # N: consumidor mínimo que imita al bucle (AC-01, AC-02)
├── contracts/
│   └── test_tool_registry_contract.py # N: el registro concreto cumple el contrato ToolRegistry
└── architecture/
    └── test_core_tools_stdlib_only.py # N: core/tools/ importa solo stdlib y harness_agent
```

**Structure Decision**: Se sigue el árbol de la skill `estructura-carpetas-harness`: la implementación del registro y la validación de esquema van en `core/tools/`, porque son reglas de negocio que no cambiarían al cambiar de proveedor, base de datos o interfaz (el criterio de desempate de la skill). Las dos diferencias entre el árbol de las skills y el repositorio real vienen de HU-00-01 y se respetan sin tocarlas: (1) los puertos viven en `core/interfaces/` y no en `core/ports.py`; (2) las pruebas de contrato y de arquitectura ya están en `tests/contracts/` y `tests/architecture/`. Las excepciones de dominio se mantienen locales en `core/tools/errors.py` y no en un `core/errors.py` compartido, que aún no existe y pertenece al área A (ver R-07). No se crea `bootstrap.py`: el registro no tiene dependencias que inyectar y la raíz de composición corresponde a la historia del bucle (R-11).

---

## Trazabilidad de requisitos y criterios de aceptación

| Requisito | Componentes | Verificación |
|---|---|---|
| **AC-01** (argumentos inválidos no ejecutan y el error nombra el campo) | `schema_validator.validate_arguments`, `InMemoryToolRegistry.validate_args`, `ToolValidationError` | `tests/unit/core/tools/test_schema_validator.py`, `test_registry.py` y `tests/integration/test_tool_registry_consumer.py` (la herramienta de prueba registra 0 ejecuciones) |
| **AC-02** (herramienta nueva sin tocar el bucle) | `InMemoryToolRegistry` usado solo a través del puerto `ToolRegistry` | `tests/integration/test_tool_registry_consumer.py`: el consumidor se escribe antes de registrar una herramienta que no conoce |
| **RF-1.2 / RF-1.3** (registrar con esquema y validar) | `registry.register`, `registry.get`, `registry.list`, `validate_args` | `tests/unit/core/tools/test_registry.py`, `tests/contracts/test_tool_registry_contract.py` |
| **RNF-2** (añadir herramientas sin tocar el bucle) | Contrato uniforme `Tool` + `ToolRegistry`; sin lógica por herramienta | Igual que AC-02 |
| **RNF-13** (núcleo desacoplado) | `core/tools/` solo stdlib; puertos intactos | `tests/architecture/test_core_tools_stdlib_only.py`, `tests/architecture/test_core_boundaries.py` y `git diff` sobre `core/interfaces/` |
| **FR-001 a FR-005** | `InMemoryToolRegistry.register/get/list`, `schema_validator.check_schema` | `test_registry.py`, `test_schema_check.py` |
| **FR-006 a FR-012** | `validate_arguments`, `ToolValidationError`, `UnknownToolError` | `test_schema_validator.py`, `test_registry.py` |
| **FR-013 a FR-016** | Diseño por puertos, `RiskLevel` expuesto vía `Tool.risk` | `test_tool_registry_consumer.py`, pruebas de arquitectura |
| **SC-005** (latencia) | Validador lineal | Prueba de humo con margen amplio en `test_schema_validator.py` |

---

## Puntos a revisar por el equipo

1. **Tope de violaciones en el mensaje (R-07)**: el error conserva todas las violaciones, pero el texto para el modelo muestra como máximo 20 y resume el resto ("y N más"), para no inflar el contexto con una lista enorme. El spec ya fue enmendado en consecuencia (FR-009 y SC-002 con tope de 20). Si se prefiriera sin tope, habría que revertir esa enmienda además de cambiar una constante.
2. **Tipo `integer` (R-05)**: acepta `3` y `3.0` (semántica de JSON Schema) y rechaza `"3"`, `true` y `3.5`. No hay coerción de ningún tipo (FR-011).
3. **Esquemas con `anyOf`, `oneOf`, `$ref`, `pattern`** y similares se rechazan al registrar (R-03). Las herramientas MCP (HU-08-03) probablemente los necesiten; ampliar el validador será una historia posterior, con un punto de extensión previsto.
4. **Versión de Python**: Python 3.12.x es la única versión soportada (PD-07). `pyproject.toml` (`requires-python >=3.12,<3.13`) y la CI (solo 3.12) ya coinciden con la constitución, que pide 3.12+; no hay nada que reconciliar en esta historia.
5. **`import-linter`** se menciona en la documentación y en las skills, pero no está instalado ni configurado en el repositorio. La verificación de fronteras de esta historia se apoya en los tests AST (existente y nuevo). Añadirlo implicaría cambiar las dependencias fijadas y queda fuera de alcance.
