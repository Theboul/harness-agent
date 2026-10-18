# Implementation Plan: HU-07-01 — Interfaz Provider y formato interno de mensajes

**Branch**: `004-provider-interface-message-format` | **Date**: 2026-10-18 | **Spec**: [specs/004-provider-interface-message-format/spec.md](spec.md)  
**Responsable**: A — Núcleo | **Sprint**: Sprint 1 | **Estimación**: 3 PHU (~6 horas F5)  
**Input**: Feature specification from `specs/004-provider-interface-message-format/spec.md`  

---

## Summary

Diseñar e implementar la arquitectura de mensajes canónicos y los convertidores de dialecto de proveedores para garantizar que el núcleo y el bucle agéntico de HARNESS operen de manera 100% independiente de los proveedores comerciales de LLM (OpenAI, Anthropic, Gemini). Se reutilizan estrictamente las entidades existentes de `HU-00-01` (`Role`, `Message`, `ToolCall`, `ToolResult`, `TokenUsage`, `ToolDefinition`, `ProviderResponse`, `Provider`) con su firma asíncrona propuesta en `D-01` (pendiente de aprobación) (`complete`). La lógica de conversión específica de proveedores se ubica en `src/harness_agent/adapters/converters/`, garantizando conversión bidireccional sin pérdida (AC-01) con política de falla cerrada (*fail-closed*). La intercambiabilidad del proveedor (AC-02) se comprueba mediante un consumidor de prueba desacoplado en `tests/contracts/` sin construir prematuramente el bucle agéntico de producción de `HU-01-01`.

---

## Technical Context

**Language/Version**: Python 3.12.x (estándar único obligatorio conforme a PD-07 y Principio III).  
**Primary Dependencies**: Biblioteca estándar (`dataclasses`, `enum`, `typing`, `abc`, `json`). Cero SDKs de terceros en `core/` (RNF-12).  
**Storage**: N/A (estructuras de memoria y adaptadores puros).  
**Testing**: `pytest==8.3.4` y `pytest-asyncio==0.25.3` (fijados en `requirements-dev.txt`). Pruebas en memoria sin red.  
**Target Platform**: Multiplataforma (Windows y Linux en integración continua).  
**Project Type**: Núcleo hexagonal y adaptadores de conversión sin acoplamiento a I/O.  
**Performance Goals**: Latencia de conversión $< 1\text{ ms}$ por secuencia de mensajes; ejecución total de la suite de pruebas $< 1\text{ s}$.  
**Constraints**: Aislamiento estricto de `core/` (verificado con `test_core_boundaries.py`); preservación local de `is_external` sin contaminar payloads de red; política de falla cerrada ante argumentos o esquemas incompatibles; descomposición en microtareas de 15 a 40 minutos (máximo 60 min).  
**Scale/Scope**: 2 módulos de conversión de dialecto en `adapters/converters/`, 1 suite de prueba de conversión round-trip (`tests/adapters/test_converters.py`), y 1 arnés de prueba de intercambiabilidad (`tests/contracts/test_provider_interchangeability.py`).

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Estado | Justificación / Cumplimiento |
|---|---|---|
| **Principio I (1 historia por spec)** | **PASS** | Exclusivamente enfocado en HU-07-01 (RF-7.1, RF-7.2, RNF-12). |
| **Principio II (Microtareas < 60 min)** | **PASS** | Estimación base de ~6 horas F5 descompuesta en microtareas atómicas de 20 a 40 minutos. |
| **Principio III (Hexagonal y Python 3.12.x)** | **PASS** | Python 3.12.x estricto; `core/` no importa convertidores ni librerías externas; los conversores residen en `adapters/`. |
| **Principio IV (Pruebas y CI multiplataforma)** | **PASS** | Pruebas unitarias deterministas en `tests/` ejecutables en Windows y Linux sin depender de red externa. |
| **Principio V (Inmutabilidad de criterios)** | **PASS** | Criterios originales AC-01 y AC-02 respetados textualmente. |
| **Principio VI (Disciplina de sprints)** | **PASS** | Sprint 1 activo; no se implementa el bucle de HU-01-01 ni el cliente LiteLLM de HU-07-02. |
| **Principio VII (Consulta quirúrgica)** | **PASS** | Documentación de referencia limitada a `00-indice`, `02-arquitectura`, `04d-historias` y `PROGRESO.md`. |
| **Principio VIII (Registro en PROGRESO.md)** | **PASS** | Se incluye la tarea final de sincronización de progreso y evidencias. |
| **Principio IX (DoD estricta y supervisión)** | **PASS** | Cobertura de tipos con `mypy --strict`, linting con `ruff` y revisión por pares requerida. |
| **Principio X (Inmutabilidad histórica)** | **PASS** | Ningún archivo de `docs/archivo/` es modificado. |

---

## Project Structure

### Documentation (this feature)

```text
specs/004-provider-interface-message-format/
├── spec.md              # Especificación clarificada
├── plan.md              # Este plan de implementación
├── research.md          # Investigación de protocolos, estado de SPK-01 y diseño fail-closed
├── data-model.md        # Entidades de dominio y modelo de adaptadores
├── quickstart.md        # Guía de validación y ejecución reproducible
├── contracts/
│   └── provider-conversion-contract.md  # Especificación formal de los mapeos OpenAI y Anthropic
└── checklists/
    └── requirements.md  # Checklist de calidad de requisitos (100% PASS)
```

### Source Code (repository root)

```text
src/harness_agent/
├── core/
│   ├── entities.py                      # Reutilizado: Role, Message, ToolCall, ToolResult, TokenUsage
│   └── interfaces/
│       └── provider.py                  # Reutilizado: ToolDefinition, ProviderResponse, Provider
└── adapters/
    └── converters/                      # NUEVO: Conversores específicos de dialecto de proveedor
        ├── __init__.py                  # Exporta funciones de conversión
        ├── openai_converter.py          # Conversión bidireccional OpenAI Chat Completions v1
        └── anthropic_converter.py       # Conversión bidireccional Anthropic Messages v1

tests/
├── adapters/
│   └── test_converters.py               # Suite completa de conversión bidireccional sin pérdida (AC-01)
├── contracts/
│   ├── test_contracts.py                # Existente: pruebas de dobles de contratos
│   └── test_provider_interchangeability.py # NUEVO: Arnés de prueba de intercambiabilidad de Provider (AC-02)
└── architecture/
    └── test_core_boundaries.py          # Existente: verificación de fronteras hexagonales
```

**Structure Decision**: Conforme a la skill `estructura-carpetas-harness`, la lógica de conversión específica de cada proveedor LLM reside en `adapters/converters/` porque cambiaría si la API de un tercero evoluciona, manteniendo a `core/` estrictamente puro y agnóstico.

---

## Fases y Descomposición de Microtareas (Estimación: ~6 horas F5)

El trabajo se divide en 4 fases secuenciales con un total de 7 microtareas atómicas (estimadas entre 25 y 40 minutos cada una, sin exceder jamás los 60 minutos):

### Fase 1: Módulo de Conversores y Dialecto OpenAI (AC-01)
- **T001**: Crear el paquete `adapters/converters/` e implementar la conversión canónico $\to$ OpenAI para mensajes y herramientas (`openai_converter.py`).
  - *Tiempo estimado*: 35 min (20 impl + 10 check + 5 reg).
- **T002**: Implementar la reconstrucción OpenAI $\to$ canónico (`from_openai_response`), parseo seguro de JSON de argumentos y mapeo de `TokenUsage`.
  - *Tiempo estimado*: 35 min (20 impl + 10 check + 5 reg).

### Fase 2: Dialecto Anthropic y Política de Falla Cerrada (AC-01)
- **T003**: Implementar la conversión canónico $\to$ Anthropic Messages v1 (`anthropic_converter.py`) extrayendo el prompt de sistema y traduciendo herramientas a `input_schema`.
  - *Tiempo estimado*: 35 min (20 impl + 10 check + 5 reg).
- **T004**: Implementar la reconstrucción Anthropic $\to$ canónico y la validación de falla cerrada (*fail-closed*) ante esquemas o argumentos no representables.
  - *Tiempo estimado*: 35 min (20 impl + 10 check + 5 reg).

### Fase 3: Suites de Pruebas Automatizadas de AC-01 y AC-02
- **T005**: Crear `tests/adapters/test_converters.py` cubriendo los 10 escenarios de conversión round-trip sin pérdida para OpenAI y Anthropic (AC-01).
  - *Tiempo estimado*: 40 min (25 impl + 10 check + 5 reg).
- **T006**: Crear `tests/contracts/test_provider_interchangeability.py` implementando el consumidor de prueba (`TestAgentConsumer`) y verificando el reemplazo polimórfico de proveedores (AC-02).
  - *Tiempo estimado*: 35 min (20 impl + 10 check + 5 reg).

### Fase 4: Verificación Integral de Calidad, Tipado y Cierre (RNF-12)
- **T007**: Ejecutar verificación estricta de Mypy, Ruff, cobertura de pruebas, test de fronteras hexagonales y sincronizar `docs/PROGRESO.md`.
  - *Tiempo estimado*: 30 min (15 impl + 10 check + 5 reg).

---

## Estrategia de Pruebas y Validación

1. **AC-01 (Conversión Sin Pérdida)**:
   - Prueba unitaria parametrizada ejecutando ciclos `canónico -> wire -> canónico` verificando igualdad exacta de atributos (`role`, `content`, `tool_calls`, `tool_result`, `usage`, `is_error`).
   - Prueba negativa verificando que argumentos JSON corruptos o esquemas incompatibles lanzan `ValueError` explícito sin pérdidas silenciosas.
2. **AC-02 (Intercambiabilidad del Proveedor)**:
   - Arnés de prueba `TestAgentConsumer` que invoca `await provider.complete(messages, tools)`.
   - Se ejecuta el consumidor con `FakeScriptedProvider` y con `AlternativeMockProvider`.
   - Se valida que el consumidor procesa ambos turnos exitosamente con 0 líneas de código modificadas.
3. **RNF-12 (Pureza Hexagonal)**:
   - `tests/architecture/test_core_boundaries.py` verifica que ningún archivo bajo `src/harness_agent/core/` importa de `adapters/`, `cli/` ni librerías de proveedores.

---

## Riesgos y Mitigaciones

1. **Riesgo**: `is_external` podría perderse al interactuar con APIs externas si el diseño confía en que la API lo devuelva.
   - *Mitigación*: Diseñado explícitamente en `research.md`: `is_external` es un metadato local que se preserva en la colección de mensajes del arnés; los convertidores de red solo transportan datos de protocolo y no esperan que la API externa devuelva dicho metadato. Implementado el 2026-10-18 (T019–T024) como envelope + sidecar en `adapters/converters/sidecar.py`; la restauración exacta es `restore_messages(envelope)`. Aprobación técnica individual de D-02 pendiente.
2. **Riesgo**: Incompatibilidad futura cuando el Desarrollador B ejecute `SPK-01` con LiteLLM.
   - *Mitigación*: HU-07-01 se basa en los esquemas canónicos públicos de OpenAI y Anthropic. LiteLLM utiliza exactamente estos mismos esquemas internamente, garantizando compatibilidad natural cuando se construya el adaptador `HU-07-02`.

---

## Complexity Tracking

*No se introducen violaciones a la Constitución ni dependencias externas adicionales.*
