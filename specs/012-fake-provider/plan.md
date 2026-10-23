# Implementation Plan: HU-00-03 — Proveedor simulado para pruebas

**Branch**: `012-fake-provider` | **Date**: 2026-10-23 | **Spec**: [specs/012-fake-provider/spec.md](spec.md)

**Input**: Feature specification from `/specs/012-fake-provider/spec.md`

**Directrices del responsable**: los errores simulados usan la jerarquía canónica `ProviderError` (`QuotaExceeded`, `ProviderTimeout`, `ProviderUnavailable`) definida en `core/interfaces/provider.py` y exportada desde `harness_agent.core`; `FakeProvider` vive en `tests/doubles/fake_provider.py`; convive con `ScriptedProvider` y `DummyProvider` sin migrar las pruebas existentes.

---

## Summary

Dos piezas pequeñas y desacopladas:

1. **Ampliación aditiva del puerto** (`core/interfaces/provider.py`): cuatro clases de excepción (`ProviderError` y sus tres subclases), reexportadas por `core/interfaces/__init__.py` y `harness_agent.core`. Solo biblioteca estándar; no cambia la firma de `Provider.complete`.
2. **`FakeProvider`** (`tests/doubles/fake_provider.py`): subclase de `Provider` que reproduce un guion ordenado de pasos (cada paso, una `ProviderResponse` o un `ProviderError`), valida el guion al construirse, trabaja con copias, lanza el fallo del paso sin esperar, registra lo recibido y falla de forma explícita (`ScriptExhausted`, ya existente) cuando el guion se agota.

El resto es verificación: pruebas unitarias, de contrato y de integración con el bucle real, una prueba de arquitectura, la guía de dobles y el registro en `PROGRESO.md`.

---

## Technical Context

**Language/Version**: Python 3.12, única versión soportada (PD-07).

**Primary Dependencies**: solo biblioteca estándar (`copy`, `collections.abc`, `typing`). Sin dependencias nuevas de ejecución ni de desarrollo.

**Storage**: N/A.

**Testing**: `pytest` + `pytest-asyncio` (`asyncio_mode=auto`); bucle real `AgentLoop`, `InMemoryEventBus` o `RecordingEventBus`, `InMemoryToolRegistry`, `ScriptedPolicy` y `RecordingTool` de `tests/doubles`. Red bloqueada con un parche de `socket` en una fixture.

**Target Platform**: Windows y Linux (matriz de CI).

**Project Type**: Biblioteca modular; el doble vive en `tests/`, el puerto en `core/`.

**Performance Goals**: un fallo simulado devuelve en menos de 10 ms (SC-004); la llamada normal es una copia en memoria.

**Constraints**:
1. `core/` sigue sin dependencias de terceros ni importaciones de `tests/`, `cli/` o `adapters/`.
2. La firma de `Provider.complete` y las entidades de `entities.py` no cambian.
3. No se modifica ningún archivo de `tests/` existente salvo `tests/doubles/__init__.py` (una importación y un nombre en `__all__`). Ni `scripted_provider.py`, ni `dummy_provider.py`, ni `core/loop.py` (SC-005).
4. `mypy --strict` sobre `src` y `tests`; `ruff` a 100 columnas; nombres en inglés.
5. Sin sleeps, sin reloj, sin aleatoriedad, sin variables de entorno, sin red en el doble.
6. No se toca `docs/archivo/` (Principio X).

**Scale/Scope**: 1 módulo de producción modificado (`provider.py`) y 2 de reexportación (`interfaces/__init__.py`, `core/__init__.py`); 1 módulo de doble nuevo; 5 módulos de prueba nuevos (errores, doble, contrato, integración y arquitectura); 1 sección de guía.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / Restricción | Requisito | Pre-diseño | Post-diseño | Evidencia |
|---|---|---|---|---|
| I. Una historia por especificación | Solo HU-00-03 | Pasa | Pasa | Spec y plan solo de HU-00-03 |
| II. Microtareas de 15 a 40 min | Ninguna tarea pasa de 40 min (límite absoluto 60) | Pasa | Pasa | `tasks.md`: 9 tareas de trabajo (≤ 40 min) más inicio, cierre y las dos humanas |
| III. Núcleo modular, tipado, sin dependencias externas | `core/` solo con biblioteca estándar | Pasa | Pasa | D1: cuatro excepciones sin imports nuevos; prueba de arquitectura |
| IV. Pruebas, calidad y CI multiplataforma | Pruebas primero; ruff, mypy, pytest en Windows y Linux | Pasa | Pasa | Cada tarea escribe las pruebas antes del código |
| V. Inmutabilidad de criterios | AC-01, AC-02, reglas y flujo copiados tal cual | Pasa | Pasa | Spec, sección «Criterios de aceptación…» |
| VI. Disciplina de sprints | Nada de sprints futuros | Pasa | Pasa | Sin adaptador LiteLLM, sin clasificación de elegibles, sin reintentos, sin archivo de guion |
| VII. Consulta documental quirúrgica | Solo las fuentes necesarias | Pasa | Pasa | HU-00-03, Sp1-07/08, HU-07-05 (solo la lista de errores), `provider.py`, `loop.py` |
| VIII. Registro en `docs/PROGRESO.md` | `En curso` y `En revisión` con registro | Pasa | Pasa | Primera y última tarea |
| IX. Definition of Done estricta | Revisión cruzada y CI | Pasa | Pasa | Tareas humanas: visto bueno de A al puerto y CI en ambos sistemas; HU-00-01 pendiente |
| X. Inmutabilidad de `docs/archivo/` | No se toca | Pasa | Pasa | `git diff` de cierre |

No hay violaciones; la sección de complejidad no aplica.

---

## Decisiones de diseño

| ID | Decisión | Motivo |
|---|---|---|
| D1 | Cuatro clases de excepción en `provider.py`, sin atributos nuevos: `ProviderError(Exception)` y `QuotaExceeded`, `ProviderTimeout`, `ProviderUnavailable` (subclases de `ProviderError`). | Mínimo que pide el flujo de la historia; el bucle ya publica `type(exc).__name__`, así que el nombre del tipo es el contrato observable (AC-02). |
| D2 | `FakeProvider(script)` recibe una secuencia de `ProviderResponse \| ProviderError`. Acepta solo esos dos tipos (un `BaseException` cualquiera se rechaza al construir). | La spec limita los fallos a los canónicos; `ScriptedProvider` sigue sirviendo para excepciones arbitrarias. |
| D3 | Se reutiliza `ScriptExhausted` de `tests/doubles/scripted_provider.py`. | Mismo comportamiento y mismo nombre que el doble de A; no se duplica el tipo. |
| D4 | Copia profunda del guion al construir y de cada paso al devolverlo. | Dos instancias del mismo guion no comparten estado (spec, casos límite) y el bucle no puede mutar el guion. |
| D5 | Validación al construir: guion no vacío, tipos válidos, ids de llamadas a herramientas no vacíos y únicos en todo el guion. El error es `ValueError` con mensaje claro. | FR-011; igual que `ScriptedProvider`, pero sin opción de saltarse la regla (YAGNI). |
| D6 | Registro: `received` y `received_tools` (copias), `call_count`, `exhausted`. Mismos nombres que `ScriptedProvider`. | Las pruebas existentes de A leen esos nombres; así las nuevas pueden compartir ayudas. |
| D7 | Sin `asyncio.sleep` ni `block_on_call`. | FR-015; el doble de bloqueo ya existe en `ScriptedProvider`. |
| D8 | La prueba de «sin red» parchea `socket.create_connection`, `socket.getaddrinfo` y `socket.socket.connect`; este último deja pasar las direcciones de loopback y `AF_UNIX` y falla ante cualquier otro destino. | Evidencia directa de SC-002 sin depender de que el entorno esté sin conexión. En Windows `socket.socketpair()` (que usa asyncio) se implementa con un `connect` a loopback, así que bloquearlo todo rompería el bucle de eventos. |
| D9 | Las pruebas de determinismo comparan `(tipo, carga)` de los eventos y el historial, no `id` ni `timestamp` (el evento los genera con UUID y reloj). | Son los únicos campos no deterministas del evento y no los controla el proveedor. |
| D10 | `FakeProvider` se exporta desde `tests/doubles/__init__.py`; la jerarquía de errores desde `harness_agent.core`. No se actualizan `test_contracts.py` ni `test_core_public_api.py` (no fijan el conjunto exacto de `__all__`). | SC-005. |

---

## Project Structure

### Documentation (this feature)

```text
specs/012-fake-provider/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── fake_provider_contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
src/harness_agent/core/
├── interfaces/
│   ├── provider.py          # + ProviderError, QuotaExceeded, ProviderTimeout, ProviderUnavailable
│   └── __init__.py          # + reexportación de los cuatro tipos
└── __init__.py              # + reexportación y __all__

tests/
├── doubles/
│   ├── fake_provider.py     # NUEVO: FakeProvider
│   └── __init__.py          # + FakeProvider en importaciones y __all__
├── unit/core/
│   └── test_provider_errors.py        # NUEVO: jerarquía, exportación, mensajes
├── unit/doubles/
│   ├── __init__.py                    # NUEVO
│   └── test_fake_provider.py          # NUEVO: guion, validación, copias, agotado, sin espera
├── contracts/
│   └── test_fake_provider_contract.py # NUEVO: cumple Provider; intercambiable
├── integration/
│   └── test_fake_provider_agent_loop.py  # NUEVO: AC-01 y AC-02 con el bucle real
└── architecture/
    └── test_provider_errors_boundaries.py # NUEVO: core sin tests/ ni terceros tras la ampliación

docs/
├── guia-contratos-desarrollo.md   # + sección «Qué doble de proveedor usar»
└── PROGRESO.md                    # fila de HU-00-03 y registro de cambios
```

**Structure Decision**: Single project. El puerto y sus errores van en `core/interfaces/` (donde ya vive `Provider`), y el doble en `tests/doubles/` junto a los demás. No se crea ningún paquete nuevo en `src/`.

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| A no aprueba la ampliación del puerto | Es aditiva y de 4 clases; se deja el visto bueno como tarea humana y no bloquea la implementación. |
| Los nombres de los tipos no coinciden con lo que HU-07-02 necesite | Los tres nombres vienen de la spec y de HU-07-05; añadir tipos después es compatible. |
| Un error canónico reutilizado entre instancias acumula trazas | D4: copia profunda al construir; cada instancia lanza sus propios objetos. |
| `ScriptExhausted` queda acoplado a otro doble | Solo se importa; si A lo mueve, el cambio es de una línea. |
| La estimación de B se queda corta | Aviso de capacidad en `PROGRESO.md`, como en las historias hermanas. |
