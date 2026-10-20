# Implementation Plan: HU-01-05 — Bus de eventos desacoplado de la interfaz

**Branch**: `011-event-bus` (directorio de la spec; el trabajo se hace en la rama `gustavo`) | **Date**: 2026-10-20 | **Spec**: [specs/011-event-bus/spec.md](spec.md)

**Input**: Feature specification from `/specs/011-event-bus/spec.md`

**Directrices del usuario**: bus real en memoria en `core/` (biblioteca estándar, módulo nuevo que no toca el puerto ni `events.py`); entrega síncrona por tipo exacto y en orden de suscripción; aislamiento de fallos con propagación (error agrupado propio en español; las excepciones no ordinarias se propagan de inmediato); copia de la lista de manejadores al empezar cada emisión y entrega anidada inmediata; validación estricta con `TypeError` en español; un único contrato de pruebas para el doble y el bus real; AC-01 con el bucle real de A y proveedor guionizado; Sp1-25 con `logging` solo en pruebas; AC-02 ampliando las pruebas de arquitectura sin duplicarlas.

---

## Summary

Añadir un único módulo de código, `src/harness_agent/core/in_memory_event_bus.py`, con `InMemoryEventBus` (implementa el puerto `EventBus` sin modificarlo) y `EventDeliveryError` (subclase de `ExceptionGroup`). El bus guarda por tipo una tupla inmutable de manejadores, de modo que la «copia al empezar la emisión» es gratuita; entrega de forma síncrona y en orden, aísla los fallos de los manejadores y los reúne en un error agrupado al terminar, y valida estrictamente `subscribe` y `emit`. Se exporta desde `harness_agent.core`. El resto es verificación: un contrato de pruebas compartido con `RecordingEventBus` (cláusulas comunes y cláusulas propias del bus real), AC-01 con el bucle real de A (y la propagación del error agrupado, Q4), un suscriptor de registro con `logging` en pruebas (Sp1-25) y una prueba de arquitectura nueva que amplía AC-02 a todo el núcleo. No se toca el puerto, `events.py`, el bucle, los dobles ni `docs/archivo/`.

---

## Technical Context

**Language/Version**: Python 3.12, única versión soportada (PD-07). `ExceptionGroup` y `BaseException.add_note` existen desde 3.11.

**Primary Dependencies**: solo biblioteca estándar en el módulo nuevo (`collections.abc`, `typing`). Sin dependencias nuevas de ejecución ni de desarrollo. Las pruebas usan `pytest`, `caplog` y `logging`.

**Storage**: N/A. Todo vive en memoria durante la ejecución; el almacén de eventos es HU-03-02.

**Testing**: `pytest` con los dobles ya existentes (`RecordingEventBus`, `ScriptedProvider`, `ScriptedPolicy`, `make_rig` de `tests/core/support.py`). Sin red, sin entorno real, sin consola.

**Target Platform**: Windows y Linux (matriz de CI: `ubuntu-latest` y `windows-latest`, Python 3.12).

**Project Type**: Biblioteca modular; el bus es una pieza del núcleo (ver D1).

**Performance Goals**: entregar un evento a 10 suscriptores en menos de 1 ms de media (SC-007); es un recorrido de una tupla.

**Constraints**:
1. `core/interfaces/*`, `core/events.py`, `core/loop.py`, `tests/doubles/*` y `docs/archivo/` quedan sin modificar (verificable con `git diff` contra la base de integración).
2. El módulo del bus importa solo biblioteca estándar y `harness_agent.core` (puerto y catálogo), y no define tipos de evento (regla de negocio 2).
3. `mypy --strict` sobre `src` y `tests`; `ruff` con línea de 100 columnas.
4. Los mensajes de error no reproducen la carga del evento (FR-012).
5. Sin suscriptor de producción, sin desuscripción, sin cola, sin asincronía (Principio VI; ver «Fuera de alcance» en la spec).

**Scale/Scope**: 1 módulo de código fuente, 1 línea de exportación en `core/__init__.py`, 1 contrato documentado, y 5 módulos de prueba nuevos (2 unitarios/contrato, 2 de integración, 1 de arquitectura).

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / Restricción | Requisito | Pre-diseño | Post-diseño | Evidencia |
|---|---|---|---|---|
| I. Una historia por especificación | Solo HU-01-05 | Pasa | Pasa | Spec y plan solo de HU-01-05; Sp1-23 ya cumplida por HU-00-01, sin trabajo nuevo |
| II. Microtareas de 15 a 40 min | Ninguna tarea pasa de 40 min (límite absoluto 60) | Pasa | Pasa | `tasks.md`: 5 tareas de trabajo (≤ 40 min) más inicio, cierre y las dos humanas |
| III. Núcleo modular, tipado, sin dependencias externas | `core/` solo con biblioteca estándar; módulos pequeños; mypy estricto | Pasa | Pasa | D1; el módulo solo importa `collections.abc`, `typing` y `harness_agent.core`; prueba de arquitectura (T006) |
| IV. Pruebas, calidad y CI multiplataforma | Pruebas primero; ruff, mypy, pytest en Windows y Linux | Pasa | Pasa | Cada tarea escribe las pruebas antes del código; los cuatro comandos al cerrar cada tarea de código; matriz de CI (T009) |
| V. Inmutabilidad de criterios | AC-01, AC-02 y reglas copiados tal cual | Pasa | Pasa | Spec, sección «Criterios de aceptación…» |
| VI. Disciplina de sprints | Nada de sprints futuros | Pasa | Pasa | Sin suscriptor de producción, desuscripción ni «aprobación pedida»; esta última se registra como observación (HU-05-03) |
| VII. Consulta documental quirúrgica | Solo las fuentes necesarias | Pasa | Pasa | HU-01-05, arquitectura §3.7, Sp1-23 a Sp1-25, V-01, código del bucle y del puerto |
| VIII. Registro en `docs/PROGRESO.md` | `En curso` al empezar y `En revisión` al terminar, con registro | Pasa | Pasa | T001 y T007; cada tarea anota su registro dentro de sus 5 min |
| IX. Definition of Done estricta | Revisión cruzada por otra área y CI | Pasa | Pasa | T008 (revisión por A) y T009 (CI); HU-00-01 sigue pendiente de aprobación técnica |
| X. Inmutabilidad de `docs/archivo/` | No se toca | Pasa | Pasa | Verificación con `git diff` en T007 |
| Hexagonal (skill `arquitectura-hexagonal-clean`) | El núcleo no importa adaptadores ni terminal; puertos por rol | Pasa | Pasa | D1; el bus implementa el puerto existente y no añade ninguno |
| V-01 (el bus solo emite) | Sin respuesta ni valor de retorno en la entrega | Pasa | Pasa | `emit` devuelve `None`; la aprobación va por `Approver` (HU-05-03) |

**Resultado**: sin violaciones; no hace falta tabla de complejidad.

---

## Project Structure

### Documentation (this feature)

```text
specs/011-event-bus/
├── spec.md
├── plan.md                              # este archivo
├── research.md                          # decisiones R-01 a R-11
├── data-model.md                        # bus, suscripción, error de entrega
├── quickstart.md                        # cómo verificar la historia
├── contracts/
│   └── event_bus_contract.md            # contrato de la implementación y cláusulas por implementación
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/harness_agent/core/
├── in_memory_event_bus.py               # NUEVO: InMemoryEventBus y EventDeliveryError
└── __init__.py                          # M: exporta InMemoryEventBus y EventDeliveryError

tests/
├── contracts/test_event_bus_contract.py                 # NUEVO: contrato único (doble y bus real)
├── unit/core/test_in_memory_event_bus.py                # NUEVO: validación, entrega y fallos del bus real
├── integration/test_event_bus_agent_loop.py             # NUEVO: AC-01 con el bucle real y Q4
├── integration/test_event_bus_logging_subscriber.py     # NUEVO: Sp1-25, suscriptor de registro (caplog)
└── architecture/test_core_no_terminal.py                # NUEVO: AC-02 sobre todo core/
docs/PROGRESO.md                                         # M: En curso / En revisión y registro
```

**Structure Decision**: el bus vive en `core/` como módulo plano, sin subpaquete, porque es una sola pieza; `core/tools/` existe porque el registro tiene tres módulos. No se crea ninguna carpeta nueva y no se modifican `core/interfaces/`, `core/events.py`, `core/loop.py` ni `tests/doubles/`.

---

## Decisiones de diseño y desviaciones

- **D1 — El bus real va en `core/`, no en `adapters/`**: la skill `estructura-carpetas-harness` pregunta si el código «cambiaría al cambiar de proveedor, base de datos o interfaz»; un bus en memoria con biblioteca estándar no cambia con ninguno, así que es núcleo. Precedente: `InMemoryToolRegistry` (HU-01-02) vive en `core/tools/`. Quien lo cree y lo conecte al bucle es la raíz de composición (`bootstrap.py`, fuera de esta historia).
- **D2 — El puerto no se modifica y no tiene desuscripción**: el contrato de HU-00-01 es `emit` y `subscribe`; ampliarlo exigiría acuerdo de A, B y C. Quien necesite desuscribirse (hoy nadie) lo planteará en su historia.
- **D3 — Una excepción no ordinaria propagada anota los fallos previos (asumido, a confirmar)**: la decisión del responsable dice «se propagan de inmediato y sin agrupar». Para cumplir también «los errores no se tragan nunca», los fallos ordinarios ocurridos antes en la misma emisión se anotan con `add_note` en la excepción propagada (tipo y número, sin contenido del evento), igual que el bucle anota el fallo del bus en la cancelación (R-08 de HU-01-01). Alternativa: descartarlos. Queda en el informe como decisión que confirmar.
- **D4 — `EventDeliveryError` hereda de `ExceptionGroup[Exception]`**: así `except*` y `.exceptions` funcionan; es subclase de `Exception`, de modo que el bucle (`except Exception`) y HU-03-02 la tratan como un fallo de emisión normal. Se sobreescribe `derive` para que `split` y `subgroup` conserven el tipo y el mensaje.
- **D5 — La suscripción durante una entrega no afecta a la emisión en curso**: se logra guardando una tupla inmutable por tipo (R-02); no hay copia en cada `emit`.
- **D6 — El doble `RecordingEventBus` no cumple todas las cláusulas**: itera su lista viva (un manejador suscrito durante la entrega recibe el mismo evento), no aísla fallos y no valida. Es un doble de pruebas y no se modifica; el contrato lo declara (cláusulas comunes frente a cláusulas del bus real).
- **D7 — Un solo hilo**: sin bloqueos; documentado en el docstring del módulo y en el contrato.
- **D8 — «Aprobación pedida» no se emite todavía**: lo hará el bucle en HU-05-03 (Sprint 2). AC-01 se verifica con lo que el bucle emite hoy (mensajes, herramienta solicitada y terminada, decisión de permiso, error del proveedor) y el bus entrega los 17 tipos; se registra como observación en `docs/PROGRESO.md`.
- **D9 — Presupuesto del plan de sprint**: Sp1-23 + Sp1-24 + Sp1-25 suman 5 h (300 min); Sp1-23 ya está cumplida, así que el presupuesto aplicable es 4 h (240 min). `tasks.md` compara la estimación (260 min) con ese presupuesto; es un aviso, no un recorte de alcance.
- **D10 — AC-02 amplía y no duplica**: `tests/architecture/test_loop_boundaries.py` ya detecta impresión y consola, pero solo sobre `core/loop.py`; `test_core_boundaries.py` solo comprueba SDK de proveedores. La prueba nueva reutiliza el detector `console_uses` y recorre todo `core/`, y añade lo que no cubre: bibliotecas de terminal, alias de `sys` y `from sys import stdout`.
- **D11 — Ratificación de HU-00-01 pendiente**: HU-00-01 sigue `Pendiente de aprobación técnica` (Sp1-03). La historia no modifica ningún puerto, pero la ratificación debe producirse antes de pasar HU-01-05 a `Hecha` (T007 y T008 lo registran).

---

## Riesgos y cómo se comprueban

| Riesgo | Mitigación |
|---|---|
| Un fallo del suscriptor se pierde y el bucle no se entera (Q4) | Cláusulas del contrato C-10 a C-12 y prueba de integración con el bucle real (T004) |
| `ExceptionGroup` pierde su tipo al hacer `split` | `derive` sobreescrito y probado en T003 |
| Un suscriptor que se suscribe durante la entrega recibe el evento en curso | Tupla inmutable por tipo; cláusula C-9 |
| El mensaje de error filtra datos del evento | Cláusula C-15 con un centinela en la carga |
| El detector de AC-02 no detecta alias de `sys` o bibliotecas de terminal | Autoprueba con fragmentos sintéticos y mutación sobre una copia de `core/` (T006) |
| El doble y el bus real se separan sin aviso | Contrato único parametrizado con ambos (T002) |
