# Implementation Plan: HU-03-02 — Persistir cada evento al ocurrir y tolerar cortes abruptos

**Branch**: `feat/hu-03-02-persist-events` (directorio de la spec: `015-persist-events`) | **Date**: 2026-10-23 | **Spec**: [specs/015-persist-events/spec.md](spec.md)

**Input**: Feature specification from `/specs/015-persist-events/spec.md`

---

## Summary

Se completa el adaptador de HU-03-01 sin tocar `core/` ni ningún puerto:

1. `SqliteSessionStore` pasa a subclase de `SessionStore` y gana `save_event` (una transacción: bloqueo de escritura, comprobación de sesión e id, `seq`, inserción, commit con sincronización completa) y `load_session` (orden por `seq`, reconstruye `Event`).
2. `errors.py` gana tres errores de dominio: `SessionNotFound`, `DuplicateEvent` y `EventSerializationError`.
3. `event_recorder.py`: `attach_event_recorder(bus, store)` suscribe `store.save_event` a los 17 `EventType` del bus (Sp1-29).
4. Pruebas: unitarias, de contrato compartido con `InMemorySessionStore`, de integración con el bucle real y de interrupción forzada con procesos hijos (`os._exit`) para AC-01 y AC-02 (Sp1-31).

---

## Technical Context

**Language/Version**: Python 3.12 (PD-07).

**Primary Dependencies**: solo biblioteca estándar (`sqlite3`, `json`, `datetime`, `collections.abc`). Sin dependencias nuevas.

**Storage**: el mismo archivo SQLite de HU-03-01; el esquema (versión 1) no cambia.

**Testing**: `pytest`; archivos en `tmp_path`; procesos hijos con `subprocess` y `sys.executable`; sin red.

**Target Platform**: Windows y Linux (CI en ambos).

**Project Type**: Biblioteca modular; adaptador de la capa exterior.

**Performance Goals**: mediana de `save_event` < 100 ms (SC-004).

**Constraints**:
1. `core/` (incluido `core/interfaces/storage.py`, `core/events.py`, `core/in_memory_event_bus.py`), `tests/doubles/` y el bucle sin modificar.
2. `adapters/storage/` importa solo biblioteca estándar, `harness_agent.core` (API pública) y su paquete; sin `config`, `cli`, `observability`, `bootstrap` ni otro adaptador.
3. Consultas con parámetros enlazados; mensajes de error fijos, sin datos ni rutas.
4. `mypy --strict`, `ruff` a 100 columnas; identificadores en inglés; mensajes en español.
5. Falla cerrada: sesión inexistente, id repetido o contenido no serializable se rechazan sin escribir.
6. Sin WAL, sin redacción de secretos (PD-10), sin reanudar ni listar (HU-03-03 a 03-05), sin `bootstrap.py` (Principio VI).

**Scale/Scope**: 1 módulo nuevo, 2 modificados, 4 archivos de prueba nuevos y 1 ampliado; unas 200 líneas de código.

---

## Constitution Check

| Principio / Restricción | Requisito | Pre-diseño | Post-diseño | Evidencia |
|---|---|---|---|---|
| I. Una historia por especificación | Solo HU-03-02 | Pasa | Pasa | Spec y plan solo de HU-03-02 |
| II. Microtareas de 15 a 40 min | Ninguna pasa de 40 min | Pasa | Pasa | `tasks.md` |
| III. Núcleo modular, tipado, sin dependencias externas | `core/` intacto | Pasa | Pasa | D1, D2 |
| IV. Pruebas, calidad y CI multiplataforma | Pruebas primero; procesos hijos portables | Pasa | Pasa | D6; `sys.executable`, `os._exit` |
| V. Inmutabilidad de criterios | AC-01, AC-02, reglas y flujo copiados tal cual | Pasa | Pasa | Spec |
| VI. Disciplina de sprints | Nada de sprints futuros | Pasa | Pasa | Sin reanudar, listar, redactar ni `bootstrap.py` |
| VII. Consulta documental quirúrgica | Solo fuentes necesarias | Pasa | Pasa | HU-03-02, `docs/02` §4, puertos `SessionStore` y `EventBus` |
| VIII. Registro en `docs/PROGRESO.md` | `En curso` y `En revisión` | Pasa | Pasa | Primera y última tarea |
| IX. Definition of Done estricta | Revisión cruzada y CI remota humanas | Pasa | Pasa | Tareas humanas finales |
| X. Inmutabilidad de `docs/archivo/` | No se toca | Pasa | Pasa | `git diff` de cierre |
| Skill `arquitectura-hexagonal-clean` | Dependencias al núcleo; SQLite solo en el adaptador; el recorder depende de puertos | Pasa | Pasa | D1 a D8 |
| Skill `estructura-carpetas-harness` | `adapters/storage/`; pruebas en `tests/unit`, `tests/contracts`, `tests/integration` | Pasa | Pasa | Tabla de rutas |
| Skill `verificar-fronteras-hexagonales` | `storage` ya está en `GUARDED`; el módulo nuevo entra solo | Pasa | Pasa | Tarea de fronteras |
| V-03 transaccionalidad por evento | Cada evento en su transacción confirmada | Pasa | Pasa | FR-002, FR-003 |
| V-13 redactar antes de persistir | Sin redactor hasta HU-10-02 | **Riesgo abierto** | **Riesgo abierto** | PD-10 explícita en `PROGRESO.md`; no se resuelve aquí |

No hay violaciones sin justificar; V-13 queda como riesgo declarado y decidido por el PO (PD-10), no como incumplimiento silencioso.

---

## Decisiones de diseño

| ID | Decisión | Motivo |
|---|---|---|
| D1 | `SqliteSessionStore(SessionStore)`: el puerto no cambia; `create_session`, `get_session` y `StoredSession` siguen siendo del adaptador. | Contrato protegido. |
| D2 | `save_event` serializa el contenido primero (`json.dumps(..., ensure_ascii=False, allow_nan=False)`); un `TypeError`, `ValueError` o `RecursionError` se traduce a `EventSerializationError` antes de abrir la transacción. | FR-007; sin bloqueo de la base por un error evitable. |
| D3 | Transacción: `BEGIN IMMEDIATE` → existe la sesión (si no, `SessionNotFound`) → no existe el id (si no, `DuplicateEvent`) → `seq = MAX(seq)+1` → `INSERT` → `commit`. Cualquier excepción hace `rollback`. | FR-002, FR-005, FR-006, FR-008, FR-011. |
| D4 | `PRAGMA synchronous = FULL` explícito al abrir; diario de reversión por defecto (sin WAL). | FR-003; el commit llega a disco antes de devolver. |
| D5 | `load_session` ordena por `seq` y reconstruye `Event`; un tipo de evento desconocido, un JSON inválido o un contenido que no es objeto se tratan como base dañada: `SessionStoreError`. | FR-004, falla cerrada. |
| D6 | Las pruebas de corte usan un proceso hijo (`sys.executable -c`, `PYTHONPATH=src`) que termina con `os._exit`; AC-02 envuelve la conexión del almacén en un proxy que sale justo en `commit`. | Portable en Windows y Linux; ejerce el código real. |
| D7 | `attach_event_recorder(bus: EventBus, store: SessionStore)` en `adapters/storage/event_recorder.py` suscribe `store.save_event` a cada `EventType`; no captura excepciones. | Sp1-29; los fallos viajan por `EventDeliveryError` del bus. |
| D8 | Contrato compartido en `tests/contracts/test_session_store_contract.py`, parametrizado con el doble y el almacén real, solo sobre lo común (orden, aislamiento, vacío). | Receta de almacén; el doble crea sesiones al vuelo y el real no. |
| D9 | `bootstrap.py` no existe: la raíz de composición deberá crear la sesión (`create_session`) y llamar a `attach_event_recorder(bus, store)`; se anota, no se implementa. | Principio VI. |

---

## Verificación contra las skills del proyecto

Skills cargadas: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness` y `verificar-fronteras-hexagonales`.

### Decision Gates (`arquitectura-hexagonal-clean`)

| Pregunta | Resultado |
|---|---|
| ¿Es regla o comportamiento nuevo? | No hay regla de negocio nueva; es persistencia y una suscripción. Adaptador. |
| ¿Necesita algo de fuera? | Sí, disco: el puerto `SessionStore` ya existe; sin puerto nuevo. |
| ¿Quién lo implementa? | `adapters/storage/` (SQLite) y su `event_recorder.py` (depende de los puertos). |
| ¿Cómo se conecta? | Constructor y `attach_event_recorder(bus, store)`; la raíz de composición futura lo invoca. |
| ¿Cómo se prueba? | Unitarias, contrato compartido con el doble, integración con el bucle real y procesos hijos. |
| ¿Es asíncrono? | No: `SessionStore` y `EventBus` son síncronos. |

### Ruta elegida (`estructura-carpetas-harness`)

| Archivo nuevo o modificado | Fila de la tabla | Prueba equivalente |
|---|---|---|
| `adapters/storage/sqlite_session_store.py` (modificado), `errors.py` (modificado) | «Código con `sqlite3`» → `adapters/<subpaquete>/`; errores en `errors.py` | `tests/unit/adapters/storage/` |
| `adapters/storage/event_recorder.py` (nuevo) | Adaptador que une puertos | `tests/unit/adapters/storage/test_event_recorder.py`, `tests/integration/` |
| `tests/contracts/test_session_store_contract.py` (nuevo) | Contrato que corre contra el doble y el real | — |
| `tests/integration/test_session_store_abrupt_close.py` (nuevo) | Interrupción forzada (AC-01, AC-02) | — |

### Lista de comprobación (`capas-y-reglas.md`)

- [x] ¿La regla de negocio está en `core/`? N.A.: no hay regla nueva.
- [x] ¿Todo lo externo pasa por un puerto con tipos del dominio? Sí: el adaptador implementa `SessionStore` por completo y usa `Event`/`EventType`.
- [x] ¿Puertos, entidades y eventos sin cambios? Sí (`git diff` de `core/` vacío).
- [x] ¿Errores externos traducidos sin reproducir valores? Sí: `SessionStoreError` y subclases con mensajes fijos.
- [x] ¿Dependencias por constructor y conexión en `bootstrap.py`? Sí; `bootstrap.py` no existe y se anota (D9).
- [x] ¿El núcleo se probó con dobles? N.A.; el adaptador se prueba con archivos de `tmp_path` y el bucle real.
- [x] ¿El adaptador real tiene prueba de contrato en `tests/contracts/`? Sí, D8.
- [x] ¿Pasa `pytest tests/architecture` (y la guarda de `storage`)? Se comprueba al cerrar; la CI en Windows y Linux es tarea humana.
- [x] ¿El núcleo emite eventos en lugar de imprimir? Sin cambios; el adaptador no imprime.
- [x] ¿Lo público está exportado? `adapters/storage/__init__.py`; `core/__init__.py` sin cambios.
- [x] ¿Decisiones de diseño respetadas (falla cerrada, secretos)? Falla cerrada sí; secretos: PD-10 abierta y declarada.
- [ ] ¿Otro integrante revisó el cambio? **No todavía** (tarea humana).

### Fronteras (`verificar-fronteras-hexagonales`)

`pytest tests/architecture` al cerrar; `event_recorder.py` solo importa `harness_agent.core` y su paquete. Sin archivos que violen reglas.

---

## Project Structure

### Documentation (this feature)

```text
specs/015-persist-events/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── session_store_events_contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
src/harness_agent/adapters/storage/
├── __init__.py              # + SessionNotFound, DuplicateEvent, EventSerializationError, attach_event_recorder
├── errors.py                # + los tres errores nuevos
├── sqlite_session_store.py  # + herencia de SessionStore, save_event, load_session
└── event_recorder.py        # NUEVO: attach_event_recorder

tests/
├── unit/adapters/storage/
│   ├── test_errors.py                  # ampliado
│   ├── test_sqlite_event_store.py      # NUEVO: save_event / load_session
│   ├── test_event_recorder.py          # NUEVO
│   └── test_public_api.py              # ampliado
├── contracts/test_session_store_contract.py          # NUEVO
└── integration/
    ├── test_session_store_abrupt_close.py            # NUEVO: AC-01 y AC-02 con procesos hijos
    └── test_event_recorder_agent_loop.py             # NUEVO: bucle real + almacén real

docs/PROGRESO.md                                    # fila HU-03-02 y registro
docs/guia-contratos-desarrollo.md                   # sección de sesiones: eventos
.claude/skills/estructura-carpetas-harness/references/arbol.md   # + save_event/load_session
.agents/skills/estructura-carpetas-harness/references/arbol.md   # misma copia
```

**Structure Decision**: Single project; no se crea ninguna carpeta nueva. `bootstrap.py` sigue sin existir.
