# Implementation Plan: Esqueleto del Repositorio e Interfaces Acordadas (HU-00-01)

**Branch**: `001-repo-skeleton-interfaces` | **Date**: 2026-10-17 | **Spec**: [specs/001-repo-skeleton-interfaces/spec.md](spec.md)

**Input**: Feature specification from `/specs/001-repo-skeleton-interfaces/spec.md`

---

## Summary

Establecer la estructura modular de paquetes (`src/harness_agent/` con separación entre `core/`, `adapters/`, `cli/` y `tests/`) y definir los 14 contratos de interfaces abstractas tipadas y entidades canónicas de la arquitectura HARNESS v2.5. Este diseño permite a los tres integrantes del equipo (A: Núcleo, B: Estado, C: Control y conexiones) implementar sus módulos concurrentemente utilizando dobles de prueba (AC-01) y garantiza mediante pruebas automatizadas de análisis estático (AST) que el núcleo no importa ningún SDK propietario de proveedores de IA (AC-02).

---

## Technical Context

**Language/Version**: Python 3.12.x (única versión soportada; `requires-python = ">=3.12,<3.13"` en `pyproject.toml`). Actualizado por PD-07 (2026-10-17): antes decía «3.11+ ... ejecutándose en 3.12+».

**Primary Dependencies**: Biblioteca estándar de Python (`abc`, `dataclasses`, `enum`, `typing`, `pathlib`, `ast`). Sin dependencias externas de ejecución en el núcleo (`core/`). Dependencias de desarrollo y prueba: `pytest`, `pytest-asyncio`, `mypy`.

**Storage**: Interfaces abstractas (`SessionStore`, `MemoryStore`). Implementaciones en memoria para dobles de prueba (`tests/doubles/`). La persistencia real en SQLite está expresamente fuera de alcance (diferida a `HU-03-01`).

**Testing**: `pytest` con pruebas de conformidad de contratos (`tests/contracts/`) y prueba de análisis de árbol de sintaxis abstracta (AST) para verificación de fronteras (`tests/architecture/`).

**Target Platform**: Multiplataforma: Windows (PowerShell) y Linux (Bash Arch).

**Project Type**: Biblioteca modular con interfaz de línea de comandos (CLI).

**Performance Goals**: Tiempo total de ejecución de la suite de contratos y fronteras inferior a 2 segundos en entornos locales y CI.

**Constraints**:
1. Cero importaciones de SDKs de proveedores (`litellm`, `openai`, `anthropic`, `google-genai`) en `src/harness_agent/core/` (AC-02).
2. Contratos asíncronos (`async def`) provisionales para `Provider.complete`, `Tool.run` y `Approver.request`; contratos síncronos (`def`) para almacenes y utilidades locales, sujetos a ratificación tras `SPK-02`.
3. Ningún código agéntico, herramientas reales, SQLite, MCP ni shell implementados en esta historia.
4. Descomposición estricta en microtareas verificables de menos de 60 minutos (Principio II).

**Scale/Scope**: 14 interfaces abstractas, 17 tipos de eventos, 4 entidades canónicas de mensajería, 6 microtareas atómicas.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Requisito Constitucional | Estado en este Plan | Justificación / Evidencia |
|---|---|---|---|
| **Principio I** | Una historia de usuario por especificación | **PASS** | Exclusivamente enfocado en `HU-00-01` (Fundaciones y contratos). |
| **Principio II** | Microtareas acotadas de 15–40 min (máx. 60 min) | **PASS** | 6 microtareas atómicas estimadas en 30–40 minutos cada una. |
| **Principio III** | Código Python 3.12.x modular, tipado y desacoplado | **PASS** | Arquitectura hexagonal con `src/`, Clases Base Abstractas (`abc.ABC`) y type hints estrictos. |
| **Principio IV** | Pruebas automatizadas y CI en Windows y Linux | **PASS** | Pruebas unitarias de contratos y de fronteras AST ejecutables sin red en ambos SO. |
| **Principio V** | Inmutabilidad de criterios de aceptación y prioridades | **PASS** | AC-01 y AC-02 se preservan intactos sin relajación de requisitos. |
| **Principio VI** | Disciplina de sprint (no desarrollar sprints futuros) | **PASS** | Alcance limitado al esqueleto de S1; herramientas reales, SQLite y bucle quedan fuera. |
| **Principio VII** | Consulta documental quirúrgica y contexto relevante | **PASS** | Solo se consultan documentos activos de `docs/` (`00`, `01`, `02`, `03`, `04a`, `05`, `PROGRESO.md`). |
| **Principio VIII** | Actualización obligatoria de `docs/PROGRESO.md` | **PASS** | Estado `En curso` y directrices registradas en `PROGRESO.md`. |
| **Principio IX** | Definition of Done estricta y supervisión humana | **PASS** | Punto de control humano explícito registrado para la reunión de consenso `Sp1-03`. |
| **Principio X** | Inmutabilidad histórica en `docs/archivo/` | **PASS** | `docs/archivo/` se mantiene intacto como referencia histórica inmutable. |

---

## Project Structure

### Documentation (this feature)

```text
specs/001-repo-skeleton-interfaces/
├── spec.md              # Feature specification
├── plan.md              # This file (implementation plan)
├── research.md          # Phase 0 output (decisiones de arquitectura y provisionalidad)
├── data-model.md        # Phase 1 output (modelos canónicos de mensajes y eventos)
├── quickstart.md        # Phase 1 output (guía de validación rápida)
├── checklists/
│   └── requirements.md  # Checklist de calidad de requisitos
└── contracts/
    └── core_interfaces.md # Especificación formal de los 14 contratos
```

### Source Code (repository root layout)

```text
pyproject.toml
src/
└── harness_agent/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   ├── entities.py              # Role, Message, ToolCall, ToolResult, TokenUsage
    │   ├── events.py                # EventType (17 eventos canónicos), Event
    │   └── interfaces/
    │       ├── __init__.py
    │       ├── provider.py          # Provider (async def complete) [PROVISIONAL - SPK-02]
    │       ├── tool.py              # Tool (async def run) [PROVISIONAL], ToolRegistry
    │       ├── security.py          # PermissionPolicy (evaluate), Approver (async def request)
    │       ├── storage.py           # SessionStore, MemoryStore (síncronos)
    │       ├── context.py           # ContextManager (assemble, compact)
    │       ├── connections.py       # McpClient, SubagentRunner (async def) [PROVISIONAL]
    │       ├── system.py            # Shell, TaskCriteria, AuthorizedArea (síncronos)
    │       └── event_bus.py         # EventBus (emit, subscribe)
    ├── adapters/
    │   └── __init__.py              # Directorio base para adaptadores futuros (A, B, C)
    └── cli/
        └── __init__.py              # Directorio base para interfaz CLI futura
tests/
├── __init__.py
├── architecture/
│   ├── __init__.py
│   └── test_core_boundaries.py      # Inspección AST: 0 SDKs de proveedores en core/ (AC-02)
├── contracts/
│   ├── __init__.py
│   └── test_contracts.py            # Conformidad de firmas de métodos e instanciación (AC-01)
└── doubles/
    ├── __init__.py
    ├── dummy_provider.py            # Doble de prueba para Provider (async def)
    ├── dummy_tool.py                # Doble de prueba para Tool (async def)
    ├── dummy_approver.py            # Doble de prueba para Approver (async def)
    ├── in_memory_store.py           # Doble de prueba para SessionStore y MemoryStore (síncronos)
    └── recording_bus.py             # Doble de prueba para EventBus (captura eventos emitidos)
```

**Structure Decision**: Se adopta el layout estándar `src/` con empaquetado declarativo en `pyproject.toml`. Cada subsistema del núcleo se agrupa en submódulos cohesivos bajo `src/harness_agent/core/interfaces/` exportados unificadamente en `src/harness_agent/core/__init__.py`. Los dobles de prueba residen bajo `tests/doubles/` permitiendo su importación inmediata por los desarrolladores B y C en sus respectivas historias (`HU-00-03`, `HU-01-02`, `HU-05-01`).

---

## Trazabilidad de Criterios de Aceptación (AC-01 y AC-02)

| Criterio | Componentes Involucrados | Prueba de Verificación |
|---|---|---|
| **AC-01** (Contratos importables con dobles de prueba) | `src/harness_agent/core/interfaces/*`<br>`tests/doubles/*` | `tests/contracts/test_contracts.py`: instancia cada contrato con dobles de prueba, invoca corutinas (`pytest.mark.asyncio`) y métodos síncronos, y verifica compatibilidad total de tipos. |
| **AC-02** (Núcleo sin dependencias de SDKs de proveedores) | `src/harness_agent/core/**/*.py` | `tests/architecture/test_core_boundaries.py`: recorre con `ast.parse` todos los archivos en `core/` y valida que ninguna sentencia de importación contenga `litellm`, `openai`, `anthropic`, `google-genai` ni submódulos propietarios. |

---

## Complexity Tracking

> **Sin violaciones constitucionales ni desviaciones de complejidad.** El diseño se ciñe exclusivamente a Clases Base Abstractas puras de la biblioteca estándar de Python y modelos de datos sin frameworks pesados ni dependencias externas.
