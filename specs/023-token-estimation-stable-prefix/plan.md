# Implementation Plan: HU-02-01 — Estimación de tokens y prefijo estable

**Branch**: `feat/hu-02-01-token-estimation-stable-prefix` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)

## Summary

Un subpaquete nuevo del núcleo, `core/context/`, con tres piezas puras y síncronas: un **estimador** (heurística `ceil(caracteres/4)` con factor de calibración por sesión), la descripción del **prefijo estable** (un mensaje `SYSTEM` con instrucciones, reglas, sistema operativo e intérprete, más las definiciones de herramientas ordenadas por nombre, con huella SHA-256) y un **ensamblador** por sesión que congela el prefijo en el primer ensamblado, le añade el historial y estima el total. `record_usage` corrige la calibración con el consumo de entrada que informa el proveedor. Sin cambios en puertos, eventos, bucle ni CLI; el puerto `ContextManager` lo compondrán HU-02-03 y HU-02-06.1.

## Technical Context

**Language/Version**: Python 3.12.x, solo biblioteca estándar (`hashlib`, `json`, `math`, `dataclasses`).
**Storage**: ninguno (estado en memoria por sesión; la persistencia del factor no se pide).
**Testing**: pytest (`asyncio_mode=auto`), sin red, claves ni consola.
**Target Platform**: Windows y Linux (CI de ambos).
**Constraints**: `core/` solo stdlib y `harness_agent.core`; sin E/S, entorno ni terminal; mensajes de error fijos en español; 100 % líneas y ramas; rutas ≤ 260 caracteres en Windows.
**Scale/Scope**: sesiones de miles de mensajes; estimación lineal en el tamaño del historial.

## Constitution Check

| Principio / regla | Cumple | Nota |
|---|---|---|
| I–IV (núcleo puro, puertos, falla cerrada, pruebas primero) | Sí | Todo en `core/context/`; entradas inyectadas; duplicados y entradas vacías se rechazan |
| V (AC inmutables) | Sí | AC-01 y AC-02 copiados sin tocar |
| VI (sprint activo) | Sí | Sp2-09 a Sp2-11; compactación, bloque esencial y archivo de instrucciones quedan fuera |
| VII (contexto mínimo) | Sí | |
| VIII (PROGRESO) | Sí | Se actualiza al cerrar |
| X (`docs/archivo/`) | Sí | Intacto |
| Puertos y 17 eventos sin cambio | Sí | `ContextManager` no se implementa ni se cambia (ver hallazgos) |
| Hard Rules de las tres skills | Sí | Ver abajo |

### Recorrido de los Decision Gates (`arquitectura-hexagonal-clean`)

| Pregunta | Resultado |
|---|---|
| ¿Regla nueva? | Sí: estimación, calibración y prefijo estable → `core/context/` |
| ¿Necesita algo de fuera? | No. Instrucciones, reglas, SO e intérprete y las definiciones llegan por constructor (valores y un `Callable`); sin puerto nuevo |
| ¿Quién lo implementa? | Nadie fuera del núcleo: es lógica pura |
| ¿Cómo se conecta? | Constructor; el cableado en `bootstrap.py` espera a que `AgentLoop` lo acepte (cambio de A). Hoy no se cablea (sería código muerto) |
| ¿Cómo se prueba? | Unitarias sin dobles (valores y funciones de prueba) y una prueba de integración con `ScriptedProvider` que devuelve `usage` |
| ¿Asíncrono? | No |

### Lista de comprobación de `capas-y-reglas.md` (respuesta de diseño; se revisa de nuevo al cerrar)

- Regla en `core/`: **sí**.
- Todo lo externo por un puerto: **sí** (no hay nada externo; SO e intérprete se inyectan).
- Puertos, entidades y eventos sin cambio: **sí**.
- Errores externos traducidos sin reproducir valores: **sí** (`ContextConfigError` con mensajes fijos).
- Dependencias por constructor, conexión en `bootstrap.py`: **parcial** → no se cablea aún; se anota como hallazgo para A (el bucle es protegido).
- Núcleo probado con dobles, sin red ni disco: **sí**.
- Prueba de contrato del adaptador: **no aplica** (no hay adaptador).
- `pytest tests/architecture` más guarda nueva: **sí** (`test_context_boundaries.py`).
- Núcleo emite eventos en lugar de imprimir: **sí** (no imprime; no emite eventos nuevos).
- Lo público exportado en `core/__init__.py`: **sí**.
- Falla cerrada, historial intacto, secretos: **sí** (el ensamblador copia, no muta).
- Revisión por otra área: **no todavía** (tarea humana).

## Project Structure

### Documentation (this feature)

```text
specs/023-token-estimation-stable-prefix/
├── spec.md · plan.md · research.md · data-model.md · quickstart.md · tasks.md
├── checklists/requirements.md
└── contracts/context_assembler.md
```

### Source Code y fila de `estructura-carpetas-harness` que justifica cada ruta

| Ruta (nueva salvo indicación) | Fila de la tabla | Contenido |
|---|---|---|
| `src/harness_agent/core/context/__init__.py` | Subpaquete de `core/` (`core/context/`) | API pública del subpaquete |
| `src/harness_agent/core/context/errors.py` | Error de dominio en `errors.py` del subpaquete | `ContextConfigError` |
| `src/harness_agent/core/context/estimator.py` | Regla de negocio | `estimate_text/message/messages/tool_definition`, `TokenEstimator` |
| `src/harness_agent/core/context/prefix.py` | Regla de negocio | `PrefixSpec`, `StablePrefix`, `build_prefix` |
| `src/harness_agent/core/context/assembler.py` | Regla de negocio | `AssembledContext`, `ContextAssembler` |
| `src/harness_agent/core/__init__.py` (existente) | Exportar lo público | |
| `tests/unit/core/context/test_{estimator,prefix,assembler}.py` | Espejo de `src/` | Pruebas unitarias |
| `tests/unit/core/context/test_prefix_stability.py` | Espejo de `src/` | Sp2-11: estabilidad del prefijo |
| `tests/integration/test_context_assembler_loop.py` | Prueba con piezas reales | Contexto ensamblado + `ScriptedProvider` + `record_usage` |
| `tests/architecture/test_context_boundaries.py` | Guarda `ast` de la frontera nueva | Solo stdlib y `core`, sin E/S, entorno ni terminal |
| `docs/PROGRESO.md`, `CLAUDE.md`, `.claude/skills/estructura-carpetas-harness/references/arbol.md` y su copia en `.agents/skills/` | Documentación viva | `core/context/` deja de ser «planeado» |

### Decisiones clave (detalle en `research.md`)

1. Heurística `ceil(caracteres/4)`; sin tokenizador de terceros.
2. Calibración por sesión como cociente reportado/crudo acotado a [0,25 ; 4,0].
3. Prefijo = un mensaje `SYSTEM` + definiciones ordenadas; congelado por sesión; huella SHA-256.
4. `ContextManager` no se implementa: lo harán HU-02-03/06.1 componiendo estas piezas.
5. Sin cambio en `loop.py`: hallazgo de integración para A.

## Complexity Tracking

| Desviación | Por qué | Alternativa descartada |
|---|---|---|
| No cablear en `bootstrap.py` | `AgentLoop` no admite el ensamblador sin cambiar `loop.py` (protegido) | Cablear sin uso: código muerto |
| No implementar `ContextManager` | `assemble(session_id, model_id)` no recibe historial y no hay almacén integrado; HU-02-03 define cómo | Implementarlo con un lector de historial inventado: cambia contrato sin acuerdo |

## Hallazgos para A, B y C (se registran en PROGRESO al cerrar)

1. **Punto de integración en `core/loop.py` (A)**: `AgentLoop` recibe un `ContextAssembler` opcional; antes de `provider.complete` usa `assembled = assembler.assemble(session_id, history)` y llama a `complete(assembled.provider_messages(), list(assembled.tools))`; tras la respuesta, `assembler.record_usage(session_id, response.usage)`. El bucle hoy construye las definiciones en cada vuelta (`_tool_definitions`): con el ensamblador, el prefijo manda.
2. **Puerto `ContextManager`**: `assemble(session_id, model_id)` no recibe el historial ni el uso; HU-02-03 debe decidir si el gestor lee de `SessionStore` o se amplía el puerto (acuerdo de A, B y C; ver SPK-03 §6).
3. **Orden con el bloque esencial (HU-02-06.1)**: el mensaje de sistema de esta historia es el primero; el bloque esencial va justo después, en otro mensaje `SYSTEM`, sin cambiar la huella del primero.
4. **Umbral por modelo (HU-02-03)**: la estimación calibrada es la entrada; el tamaño de ventana por modelo no existe aún.
