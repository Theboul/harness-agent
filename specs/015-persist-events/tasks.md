# Implementation Tasks: HU-03-02 — Persistir cada evento al ocurrir y tolerar cortes abruptos

**Feature**: `specs/015-persist-events/spec.md`  
**Plan**: `specs/015-persist-events/plan.md`  
**Responsable**: B — Estado  
**Sprint**: Sprint 1 | **PHU**: 3  
**Tareas de referencia**: Sp1-29, Sp1-30, Sp1-31  

---

## Cómo leer este documento

**Pruebas primero, dentro de cada tarea.** Cada tarea agrupa las pruebas y la implementación de una pieza: se escriben las pruebas, se ejecutan y se confirma que fallan **por la razón esperada** (`ImportError` del símbolo nuevo o aserción de comportamiento, no un error de sintaxis), se implementa lo mínimo y se pasan los cuatro comandos de calidad.

**Ritmo**: 9 tareas de trabajo (T002 a T010) de 40 min como máximo, una de inicio (T001), una de verificación final (T011) y dos humanas (T012, T013). Ninguna pasa de 40 min (la Constitución permite 40; el límite absoluto es 60).

**Reglas que valen para todas las tareas:**
- **Archivos protegidos**: no modificar nada bajo `src/harness_agent/core/` (en particular `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`), ni `src/harness_agent/config.py`, ni `tests/doubles/`, ni `docs/archivo/`, ni ninguna prueba existente (salvo ampliar `test_errors.py` y `test_public_api.py` de HU-03-01). Los únicos archivos existentes que se tocan son `docs/guia-contratos-desarrollo.md`, `docs/PROGRESO.md` y `references/arbol.md` de las dos copias de la skill `estructura-carpetas-harness`.
- `adapters/storage/` solo importa biblioteca estándar, `harness_agent.core` (`from harness_agent.core import ...`, nunca submódulos) y su propio paquete.
- Todo el código y las pruebas deben pasar `mypy --strict` y `ruff` (línea de 100 columnas). Nombres de código en inglés; mensajes de error y documentación en español.
- Tipos, errores y garantías siguen [contracts/session_store_events_contract.md](contracts/session_store_events_contract.md) y [data-model.md](data-model.md); las decisiones, [research.md](research.md) y [plan.md](plan.md) (D1 a D9).
- **Aislamiento**: toda prueba que toca disco usa `tmp_path`; las de corte usan procesos hijos con `sys.executable`; ninguna toca el repositorio ni el directorio personal ni la red.
- **Sin literales detectables**: ninguna prueba contiene texto que `tests/architecture/test_no_secrets_in_repo.py` detecte como clave; usar el centinela `VALOR-DE-PRUEBA-123` para comprobar que los mensajes de error no reproducen datos.
- **Commits** (estilo del proyecto): en español, sin coautor ni pie de sesión, formato `tipo(ámbito): descripción (HU-03-02)`.
- **Al cerrar cada tarea que toca código o pruebas**, ejecutar `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`; los cuatro con código 0 (salvo el test de ruta larga de Windows ya conocido), y registrar el resultado.

**Correspondencia con las tareas del plan de sprint** (columna *Tarea F5*):

| Tarea F5 | Descripción en `docs/03-plan-sprints.md` | Presupuesto (min) | Microtareas (min) |
|---|---|---|---|
| **Sp1-29** | Suscribir el almacén al bus de eventos | 90 | T008 (35), T009 (30) = 65 |
| **Sp1-30** | Escribir en transacciones por evento | 150 | T002 (15), T003 (40), T004 (35), T005 (30) = 120 |
| **Sp1-31** | Prueba de interrupción forzada | 150 | T006 (40), T007 (35) = 75 |
| Transversal | Estado, contrato, documentación, cierre, verificación, revisión y CI remota (Principios VIII y IX) | — | T001 (20), T010 (35), T011 (30), T012, T013 = 85 |

**Total de las microtareas de trabajo**: 345 min frente a los 390 min presupuestados para Sp1-29 a Sp1-31: dentro del presupuesto.

---

## Phase 1: Setup (estado)

- [x] **T001** Marcar HU-03-02 como `En curso` en `docs/PROGRESO.md` (transversal)
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: Ninguna
  - **Criterios relacionados**: Principio VIII
  - **Tarea F5**: Transversal
  - **Estimación**: 20 min
  - **Verificación**: La fila de `HU-03-02` pasa de `Pendiente` a `En curso` con responsable `B — Estado`; se abre el bloque **Observaciones de HU-03-02** con el alcance (herencia del puerto, `attach_event_recorder` incluido, sin `bootstrap.py`), la dependencia apilada de HU-03-01 y PD-10 como riesgo abierto.

---

## Phase 2: Foundational — errores y herencia del puerto (Sp1-30)

- [x] **T002** Errores de dominio nuevos (FR-005, FR-006, FR-007)
  - **Archivos**: `tests/unit/adapters/storage/test_errors.py`, `src/harness_agent/adapters/storage/errors.py`
  - **Dependencias**: T001
  - **Criterios relacionados**: FR-005, FR-006, FR-007, contrato (Errores)
  - **Tarea F5**: Sp1-30
  - **Estimación**: 15 min
  - **Verificación**: Prueba primero: `SessionNotFound`, `DuplicateEvent` y `EventSerializationError` son subclases de `SessionStoreError` y conservan su mensaje; fallan por `ImportError` antes de implementar.

---

## Phase 3: User Story 1 — guardar y cargar eventos (Sp1-30)

**Prueba independiente**: tres eventos guardados en una sesión se cargan iguales y en orden.

- [x] **T003** [US1] `save_event` y herencia de `SessionStore` (FR-001, FR-002, FR-005 a FR-008, FR-011, FR-015)
  - **Archivos**: `tests/unit/adapters/storage/test_sqlite_event_store.py`, `src/harness_agent/adapters/storage/sqlite_session_store.py`
  - **Dependencias**: T002
  - **Criterios relacionados**: Historia 1 (escenarios 4 a 6), FR-001, FR-002, FR-005, FR-006, FR-007, FR-008, FR-011, FR-015, plan D1 a D4
  - **Tarea F5**: Sp1-30
  - **Estimación**: 40 min
  - **Verificación**: Pruebas primero (con una sesión creada por `create_session`): el almacén es instancia de `SessionStore`; guardar un evento lo inserta con `seq` 1 y el siguiente con 2, independiente por sesión; sesión inexistente lanza `SessionNotFound` y no guarda; id repetido lanza `DuplicateEvent` y el original queda; contenido no serializable (objeto, `NaN`, referencia circular) lanza `EventSerializationError` sin reproducir el contenido (centinela) y sin abrir transacción (`in_transaction` falso); un fallo del motor revierte, lanza `SessionStoreError` sin el centinela, y el siguiente guardado usa el `seq` correcto (sin huecos); almacén cerrado lanza `SessionStoreError`.

- [x] **T004** [US1] `load_session` (FR-004, FR-008)
  - **Archivos**: `tests/unit/adapters/storage/test_sqlite_event_store.py`, `src/harness_agent/adapters/storage/sqlite_session_store.py`
  - **Dependencias**: T003
  - **Criterios relacionados**: Historia 1 (escenarios 1 a 3), FR-004, FR-008, plan D5, SC-003
  - **Tarea F5**: Sp1-30
  - **Estimación**: 35 min
  - **Verificación**: Pruebas primero: tres eventos de tipos distintos vuelven iguales (id, sesión, `EventType`, fecha UTC, contenido) y en orden de guardado aunque tengan la misma fecha; dos sesiones intercaladas no se mezclan; sesión desconocida o sin eventos devuelve `[]`; Unicode y contenido grande intactos; tuplas vuelven como listas; una fila con tipo desconocido o JSON inválido (insertada a mano) lanza `SessionStoreError`; 1 000 eventos se guardan y cargan sin pérdida; almacén cerrado lanza `SessionStoreError`.

- [x] **T005** [US1] Contrato compartido con el doble en memoria (FR-014)
  - **Archivos**: `tests/contracts/test_session_store_contract.py`
  - **Dependencias**: T004
  - **Criterios relacionados**: Historia 1 (escenario 7), FR-014, plan D8
  - **Tarea F5**: Sp1-30
  - **Estimación**: 30 min
  - **Verificación**: Prueba parametrizada con `InMemorySessionStore` y `SqliteSessionStore` sobre lo común del puerto: orden de guardado, aislamiento por sesión, vacío para sesión desconocida, devuelve `Event` iguales a los guardados (con contenido compatible con JSON). No se documenta como común la creación al vuelo de sesiones.

---

## Phase 4: User Stories 2 y 3 — cierre abrupto y escritura cortada (Sp1-31)

**Prueba independiente**: un proceso hijo muere con `os._exit` y el padre reabre la base.

- [x] **T006** [US2] AC-01: el evento confirmado sobrevive a un cierre abrupto (FR-003, FR-013)
  - **Archivos**: `tests/integration/test_session_store_abrupt_close.py`, `src/harness_agent/adapters/storage/sqlite_session_store.py`
  - **Dependencias**: T004
  - **Criterios relacionados**: AC-01, regla de negocio 1, historia 2, FR-003, FR-013, plan D4, D6, SC-001
  - **Tarea F5**: Sp1-31
  - **Estimación**: 40 min
  - **Verificación**: Pruebas primero con un auxiliar que lanza `sys.executable -c` con `PYTHONPATH=src` en un proceso hijo: el hijo crea la sesión, guarda N eventos y termina con `os._exit(0)` sin cerrar; el padre reabre el archivo y encuentra todos en orden (20 repeticiones); un evento confirmado es visible desde una segunda conexión mientras la primera sigue abierta; en el código se fija `PRAGMA synchronous = FULL` al abrir (la prueba lo lee con `PRAGMA synchronous` en la conexión del almacén).

- [x] **T007** [US3] AC-02: una escritura cortada no deja la base corrupta (FR-009, FR-010)
  - **Archivos**: `tests/integration/test_session_store_abrupt_close.py`
  - **Dependencias**: T006
  - **Criterios relacionados**: AC-02, regla de negocio 2, historia 3, FR-009, FR-010, plan D6, SC-002
  - **Tarea F5**: Sp1-31
  - **Estimación**: 35 min
  - **Verificación**: Pruebas primero: el hijo guarda dos eventos, sustituye la conexión del almacén por un proxy que llama a `os._exit` en `commit` y ejecuta `save_event` del tercero; el padre reabre: `PRAGMA integrity_check` devuelve `ok`, están solo los dos primeros, y un guardado nuevo recibe `seq` 3 (20 repeticiones). Otro caso: corte tras `BEGIN IMMEDIATE` y el `INSERT` sin commit.

---

## Phase 5: User Story 4 — suscripción al bus (Sp1-29)

- [ ] **T008** [US4] `attach_event_recorder` (FR-018)
  - **Archivos**: `tests/unit/adapters/storage/test_event_recorder.py`, `src/harness_agent/adapters/storage/event_recorder.py`
  - **Dependencias**: T004
  - **Criterios relacionados**: Historia 4 (escenarios 1, 2 y 4), FR-018, plan D7
  - **Tarea F5**: Sp1-29
  - **Estimación**: 35 min
  - **Verificación**: Pruebas primero con `InMemoryEventBus` real y un almacén real: se emite un evento de cada uno de los 17 `EventType` y todos quedan guardados en orden antes de que `emit` devuelva; un fallo del almacén (sesión inexistente) llega al emisor como `EventDeliveryError` con la causa `SessionNotFound`; con un `SessionStore` falso (doble propio de la prueba) se comprueba que el recorder solo usa el puerto.

- [ ] **T009** [US4] Integración con el bucle real (FR-018)
  - **Archivos**: `tests/integration/test_event_recorder_agent_loop.py`
  - **Dependencias**: T008
  - **Criterios relacionados**: Historia 4 (escenario 3), FR-018
  - **Tarea F5**: Sp1-29
  - **Estimación**: 30 min
  - **Verificación**: Con `make_rig` o composición manual de `AgentLoop` + `ScriptedProvider` + bus real + almacén real suscrito y sesión creada: un turno con una llamada a herramienta deja en la sesión los eventos del turno en el orden de emisión; tras cerrar y reabrir el archivo siguen ahí.

---

## Phase 6: Fronteras, documentación y cierre

- [ ] **T010** API pública, fronteras y documentación (FR-012, FR-017)
  - **Archivos**: `src/harness_agent/adapters/storage/__init__.py`, `tests/unit/adapters/storage/test_public_api.py`, `docs/guia-contratos-desarrollo.md`, `.claude/skills/estructura-carpetas-harness/references/arbol.md`, `.agents/skills/estructura-carpetas-harness/references/arbol.md`
  - **Dependencias**: T009
  - **Criterios relacionados**: FR-012, plan (Project Structure)
  - **Tarea F5**: Transversal
  - **Estimación**: 35 min
  - **Verificación**: `__all__` incluye los tres errores nuevos y `attach_event_recorder` (prueba ampliada); `pytest tests/architecture` pasa sin cambiar las guardas (el módulo nuevo entra en `storage`); la guía documenta `save_event`, `load_session`, el orden por `seq`, la sesión previa obligatoria y la limitación de JSON; `arbol.md` (ambas copias idénticas) actualizado.

- [ ] **T011** Verificación final y cierre del registro en `docs/PROGRESO.md` (FR-016, FR-017)
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: T010
  - **Criterios relacionados**: FR-012, FR-016, FR-017, Principio VIII, SC-005, SC-006
  - **Tarea F5**: Transversal
  - **Estimación**: 30 min
  - **Verificación**: Los cuatro comandos de calidad, `pytest tests/architecture` y la comprobación de archivos protegidos con resultados reales; fila de HU-03-02 en `En revisión` (nunca `Hecha`) con archivos y evidencia; una línea por tarea en *Registro de cambios*; **Observaciones de HU-03-02** con: dependencia apilada de HU-03-01, sesión previa obligatoria y puente pendiente en la raíz de composición, PD-10 sin cerrar, sin WAL, limitación de JSON.

---

## Phase 7: Tareas humanas (no las marca Claude)

- [ ] **T012** Revisión cruzada por un integrante de otra área (A o C), tras integrar HU-03-01
  - **Archivos**: PR
  - **Dependencias**: T011
  - **Criterios relacionados**: Principio IX
  - **Estimación**: humana

- [ ] **T013** CI remota en `ubuntu-latest` y `windows-latest` en verde (incluidas las pruebas de procesos hijos), y ratificación de HU-00-01 (Sp1-03)
  - **Archivos**: PR
  - **Dependencias**: T012
  - **Criterios relacionados**: Principio IX
  - **Estimación**: humana

---

## Dependencias y orden

T001 → T002 → T003 → T004 → (T005, T006, T008 independientes entre sí; se hacen en orden) → T007 → T009 → T010 → T011 → T012 → T013.

**MVP**: T001 a T007 entregan AC-01 y AC-02; T008 y T009 añaden la suscripción al bus.
