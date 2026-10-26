# Implementation Plan: HU-01-06 — Límites de turnos, tiempo y consumo por sesión

**Branch**: `claude/hu-01-06-limits-8aa045` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)

**Input**: `specs/024-execution-limits/spec.md`

## Summary

Un módulo nuevo y puro, `core/limits.py`, lleva la regla: `SessionLimits` (máximos), `LimitTracker` (cuenta turnos = llamadas al modelo, tokens de `usage` y tiempo dentro de las tareas con reloj inyectado) y `LimitReached`. `AgentLoop` recibe `limits` y `clock` opcionales y, al inicio de cada vuelta, consulta al tracker: si un límite se cumple publica `LIMIT_REACHED` (`{limit, used, maximum}`) y devuelve `TurnStatus.LIMIT_REACHED` sin llamar al proveedor. La CLI traduce el evento a una línea en español. `bootstrap.compose()` mapea `config.Limits` → `SessionLimits`. No cambian `core/events.py`, `core/interfaces/` ni `config.py`.

## Technical Context

**Language/Version**: Python 3.12, solo stdlib en `core/`. **Dependencies**: ninguna nueva. **Storage**: N/A.
**Testing**: pytest (`asyncio_mode = "auto"`), `ScriptedProvider`/`FakeProvider`, `RecordingEventBus`, `make_rig`; 100 % de líneas y ramas en `core/limits.py`.
**Platform**: Windows y Linux; reloj inyectado, sin esperas reales.
**Constraints**: `core/loop.py` es protegido (dueño A): cambio mínimo y aditivo; `max_tokens` (presupuesto de la ejecución) ≠ `max_output_tokens` (tope de una llamada).
**Scope**: 1 módulo nuevo, ~35 líneas en `loop.py`, ~15 en `render.py`, ~8 en `bootstrap.py`, exportaciones en `core/__init__.py`, guardas de arquitectura.

## Constitution Check

| Principio | Cumplimiento |
|---|---|
| I. Una historia, una spec | Solo HU-01-06. Pasa |
| II. Microtareas 15–40 min | `tasks.md`. Pasa |
| III. Modular, tipado, Python 3.12 | Pasa |
| IV. Pruebas y CI multiplataforma | Sin plataforma ni red. Pasa |
| V. Criterios inmutables | AC-01 y AC-02 copiados. Pasa |
| VI. Sprints | HU-01-06 es de Sprint 2. Sin HU-01-07/08. Pasa |
| VII. Consulta quirúrgica | Solo ficha y dependencia. Pasa |
| VIII. PROGRESO.md | Tarea de cierre. Pasa |
| IX. DoD | Revisión cruzada, CI remota y ratificación: tareas humanas |
| X. `docs/archivo/` | No se toca |
| Falla cerrada, sin secretos, eventos | Límite no válido o dato ausente nunca relaja; la carga solo lleva enteros. Pasa |

**Hard Rules de las skills**: `arquitectura-hexagonal-clean` (regla en `core/`, sin puerto nuevo porque no hay E/S: el reloj es un `Callable` inyectado; evento ya existente; dependencias por constructor y cableado en `bootstrap.py`); `estructura-carpetas-harness` (tabla abajo); `verificar-fronteras-hexagonales` (guarda `ast` nueva `test_limits_boundaries.py` y revisión de `test_loop_boundaries.py`, ver Riesgos).

### Lista de comprobación de `capas-y-reglas.md` (diseño)

| Punto | Resp. | Justificación |
|---|---|---|
| ¿Regla en `core/`? | Sí | `core/limits.py` |
| ¿Lo externo pasa por un puerto? | Sí | No hay nada externo; el reloj es un callable inyectado |
| ¿Puertos, entidades y eventos sin cambios? | Sí | `LIMIT_REACHED` ya existe; `TurnStatus` es del bucle, no un contrato HU-00-01 |
| ¿Errores externos traducidos, sin valores? | Sí | `InvalidLimitsError` sin el valor |
| ¿Dependencias por constructor y cableado en `bootstrap.py`? | Sí | `AgentLoop(limits=…)` en `compose()` |
| ¿Núcleo probado con dobles? | Sí | `ScriptedProvider`, `RecordingEventBus`, reloj falso |
| ¿Prueba de contrato del adaptador? | N/A | No hay adaptador |
| ¿`pytest tests/architecture` + guarda nueva? | Sí | `test_limits_boundaries.py` |
| ¿Núcleo emite eventos, no imprime? | Sí | `LIMIT_REACHED` |
| ¿Público exportado en `core/__init__.py`? | Sí | T006 |
| ¿Decisiones de diseño (falla cerrada)? | Sí | Un límite cumplido sigue cumplido |
| ¿Revisó otro integrante? | Pendiente | Tarea humana |

## Project Structure

| Archivo | Fila de `estructura-carpetas-harness` |
|---|---|
| `src/harness_agent/core/limits.py` (nuevo) | «Regla de negocio (permisos, límites…)» → `core/limits.py` |
| `src/harness_agent/core/loop.py` (modif., protegido) | Orquestación del bucle; cambio mínimo autorizado por la historia |
| `src/harness_agent/core/__init__.py` (modif.) | Todo lo público de `core/` se exporta |
| `src/harness_agent/cli/render.py` (modif., desviación) | «Imprime o lee de la terminal» → `cli/render.py` |
| `src/harness_agent/bootstrap.py` (modif.) | Unir piezas |
| `tests/unit/core/test_limits.py`, `tests/core/test_loop_limits.py`, `tests/integration/test_limits_agent_loop.py`, `tests/unit/cli/test_render_limits.py`, `tests/unit/test_bootstrap_limits.py`, `tests/architecture/test_limits_boundaries.py` (nuevos) | Espejo de `src/` en `tests/` |
| `tests/architecture/test_loop_boundaries.py` y `tests/core/test_loop_history.py` (modif.; `test_loop_events.py` y `test_core_public_api.py` siguen válidos) | Las guardas de la Sprint 1 prohibían el evento y los parámetros de límite; se actualizan como hizo HU-05-03 |

## Riesgos y coordinación

- **Colisión con HU-05-03**: ya está en `main` (PR #26) y esta rama la integró; no se toca `_ask_approval` ni `_decide`. Los cambios nuevos en `loop.py` están en `__init__`, `run_turn`, el inicio del `while` y el tras-respuesta; ninguno reescribe un método existente.
- **Guardas de Sprint 1**: `test_loop_boundaries.py` prohíbe `LIMIT_REACHED` y parámetros con «limit/max_/turns/budget» en el bucle. Se reemplazan por: el bucle publica `LIMIT_REACHED` y solo desde un método (`_stop_at_limit`) y los únicos parámetros de límite son `limits` y `clock`.
- **Aprobación humana**: el usuario autorizó la historia, que exige tocar `loop.py`; el cambio y su alcance se enumeran en `tasks.md` y se anotan en PROGRESO.
