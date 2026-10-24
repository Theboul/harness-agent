# Feature Specification: HU-03-02 — Persistir cada evento al ocurrir y tolerar cortes abruptos

**Feature Branch**: `015-persist-events`

**Created**: 2026-10-23

**Status**: Draft

**Proyecto**: HARNESS v2.5 | **Sprint**: 1 | **Responsable**: B — Estado | **Tareas de referencia**: Sp1-29 (suscribir el almacén al bus), Sp1-30 (transacciones por evento), Sp1-31 (prueba de interrupción forzada) | **Requisitos**: RF-3.2, RF-3.5 | **Depende de**: HU-03-01 (esquema y creación de sesión; en revisión, PR pendiente), HU-01-05 (bus de eventos)

**Input**: User description: "HU-03-02 — Persistir cada evento al ocurrir y tolerar cortes abruptos (docs/04b-historias-estado.md#hu-03-02)."

## Clarifications

### Session 2026-10-23

Sin preguntas de producto abiertas; las ambigüedades son de diseño y se resuelven con los contratos existentes. Quedan como supuestos por confirmar con B.

- Q: ¿Qué hace `save_event` si la sesión del evento no existe? → A: Falla cerrada con un error de dominio (`SessionNotFound`); no crea la sesión por su cuenta. A diferencia del doble en memoria, que la crea al vuelo, el almacén real exige `create_session` antes (HU-03-01).
- Q: ¿`SqliteSessionStore` hereda ya de `SessionStore`? → A: Sí. Con `save_event` y `load_session` implementa los tres métodos del puerto; el puerto no cambia.
- Q: ¿Cómo se ordena la sesión al cargar? → A: Por un número de orden (`seq`) por sesión, asignado al guardar (1, 2, 3…) dentro de la misma transacción; no por la marca de tiempo, que puede repetirse.
- Q: ¿Qué pasa con un evento cuyo id ya existe? → A: Se rechaza con error de dominio y no se guarda; un evento confirmado nunca se sobrescribe (regla 1).
- Q: ¿Cómo se guarda el contenido (`payload`)? → A: Como JSON. Lo que no sea JSON (objetos arbitrarios) se rechaza con error de dominio antes de tocar la base. Al leer, las tuplas vuelven como listas (limitación documentada).
- Q: ¿Qué durabilidad se exige? → A: Cada evento se confirma (commit) con sincronización completa antes de que `save_event` devuelva; un cierre abrupto posterior no lo pierde. Se mantiene el diario de reversión por defecto de SQLite (sin WAL).
- Q: ¿Se redactan secretos antes de guardar (V-13, PD-10)? → A: No en esta historia; la redacción llega con HU-10-02 (Sprint 4). Se deja explícito en `PROGRESO.md` como riesgo abierto hasta que el PO decida.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04b-historias-estado.md` (HU-03-02). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

**Flujo general**

1. Ocurre un evento.
2. El SessionStore lo escribe en la base de datos de inmediato.
3. Si el proceso se interrumpe, el evento sigue en la base al reiniciar.

**Reglas de negocio**

1. Un evento confirmado nunca se pierde.
2. Una escritura cortada no deja la base corrupta.

**Criterios de aceptación**

- **AC-01 — Evento sobrevive a un cierre abrupto.** Dado un evento confirmado, cuando el proceso se interrumpe de golpe, entonces el evento sigue en la base al reiniciar.
- **AC-02 — Base sin corrupción.** Dado una escritura en curso, cuando se corta, entonces la base no queda corrupta.

### Lo que ya existe y lo que cambia

- **Existe y no se toca**: el puerto `SessionStore`, `Event`, `core/events.py`, el bus, el bucle de A, la CLI y los dobles de `tests/doubles/`. Las tablas `sessions` y `events` y `SqliteSessionStore` (HU-03-01) ya existen; el esquema no cambia (sigue en la versión 1).
- **Cambia, de forma aditiva**: `SqliteSessionStore` pasa a subclase de `SessionStore` y gana `save_event` y `load_session`, más dos errores de dominio nuevos (`SessionNotFound`, `EventSerializationError`).
- **Se añade**: `attach_event_recorder(bus, store)` (Sp1-29), que suscribe un `SessionStore` a los 17 tipos de evento del bus. No se conecta al bucle ni a la CLI aquí (no existe `bootstrap.py`; Principio VI): la raíz de composición deberá llamarla y crear la sesión antes del primer evento.

### User Story 1 - Guardar cada evento en el momento en que ocurre (Priority: P1) [Flujo 1–2]

Como usuario operador, quiero que cada evento de una sesión se escriba de inmediato y se pueda volver a leer en orden, para tener el historial completo.

**Why this priority**: Es el flujo central y la base de reanudar (HU-03-03 a HU-03-05) y de la compactación.

**Independent Test**: Se crea una sesión, se guardan tres eventos de tipos distintos con contenido y se cargan: salen los mismos tres, en el orden en que se guardaron, con id, tipo, marca de tiempo y contenido idénticos.

**Acceptance Scenarios**:

1. **Given** una sesión creada, **When** se guardan eventos uno tras otro, **Then** `load_session` los devuelve en ese orden con los mismos id, tipo, fecha (UTC) y contenido.
2. **Given** eventos de dos sesiones intercaladas, **When** se carga cada sesión, **Then** solo contiene sus propios eventos, cada una numerada desde 1.
3. **Given** una sesión sin eventos o un identificador que no existe, **When** se carga, **Then** devuelve una lista vacía.
4. **Given** un evento de una sesión que no existe, **When** se guarda, **Then** se rechaza con `SessionNotFound` y no se guarda nada.
5. **Given** un evento cuyo id ya está guardado, **When** se intenta guardar de nuevo, **Then** se rechaza y el original queda intacto.
6. **Given** un contenido que no se puede convertir a JSON, **When** se guarda, **Then** se rechaza con `EventSerializationError` sin tocar la base y sin reproducir el contenido en el mensaje.
7. **Given** el almacén y el doble `InMemorySessionStore`, **When** se corre la misma prueba de contrato, **Then** ambos se comportan igual en lo común (orden, aislamiento por sesión, vacío).

---

### User Story 2 - Un evento confirmado sobrevive a un cierre abrupto (Priority: P1) [AC-01, Regla 1]

Como usuario operador, quiero que si el programa se cierra de golpe no se pierda ningún evento ya confirmado, para poder retomar el trabajo.

**Why this priority**: Es el criterio AC-01 y la regla de negocio 1.

**Independent Test**: Un proceso hijo crea una sesión, guarda un evento y termina de inmediato sin cerrar nada (`os._exit`); el proceso padre abre la base y encuentra el evento.

**Acceptance Scenarios**:

1. **Given** un evento cuyo `save_event` ya devolvió, **When** el proceso termina sin cerrar el almacén, **Then** al reabrir la base el evento está.
2. **Given** varios eventos guardados, **When** el proceso termina de golpe, **Then** están todos, en orden.
3. **Given** `save_event` devuelto, **When** se lee con otra conexión sin cerrar la primera, **Then** el evento ya es visible (confirmado, no pendiente).

---

### User Story 3 - Una escritura cortada no deja la base corrupta (Priority: P1) [AC-02, Regla 2]

Como usuario operador, quiero que si el proceso se corta a mitad de una escritura la base siga siendo válida y sin eventos a medias, para no perder todo el historial.

**Why this priority**: Es el criterio AC-02 y la regla de negocio 2.

**Independent Test**: Un proceso hijo abre una transacción de escritura del evento, la deja sin confirmar y termina con `os._exit`; el padre reabre la base, `PRAGMA integrity_check` da `ok`, el evento a medias no aparece y los anteriores siguen.

**Acceptance Scenarios**:

1. **Given** una escritura sin confirmar, **When** el proceso se corta, **Then** al reabrir la base pasa la comprobación de integridad y no contiene el evento a medias.
2. **Given** un fallo del motor durante `save_event`, **When** ocurre, **Then** se revierte, se lanza `SessionStoreError` y el siguiente `save_event` funciona con el orden correcto (sin huecos en `seq`).
3. **Given** los eventos confirmados antes del corte, **When** se reabre, **Then** siguen todos.

---

### User Story 4 - Suscribir el almacén al bus de eventos (Priority: P2) [Flujo 1–2, Sp1-29]

Como usuario operador, quiero que cada evento que el bus publica se guarde sin que el bucle conozca la base de datos, para que el historial se escriba solo.

**Why this priority**: Es la tarea Sp1-29 y el punto donde «ocurre un evento» se convierte en «se escribe de inmediato»; es P2 porque el criterio de aceptación se cumple ya con `save_event`.

**Independent Test**: Se crea un bus en memoria, un almacén real y se llama a `attach_event_recorder`; se emiten eventos de varios tipos y se comprueba que `load_session` los devuelve en orden.

**Acceptance Scenarios**:

1. **Given** el almacén suscrito al bus, **When** se emite un evento de cualquiera de los 17 tipos, **Then** queda guardado antes de que `emit` devuelva.
2. **Given** un fallo al guardar (sesión inexistente, base bloqueada), **When** el bus entrega el evento, **Then** el fallo llega al emisor como `EventDeliveryError` del bus (no se silencia) y el evento no se da por guardado.
3. **Given** el bucle real de A con `ScriptedProvider`, **When** corre un turno con el almacén suscrito, **Then** los eventos del turno quedan en la sesión en el orden en que se emitieron.
4. **Given** `attach_event_recorder`, **When** se revisa su código, **Then** solo depende de los puertos `EventBus` y `SessionStore` del núcleo.

---

### Edge Cases

- **Orden con fechas iguales**: el orden lo da `seq`, no la fecha.
- **Dos almacenes sobre el mismo archivo**: cada guardado toma el bloqueo de escritura al empezar para que `seq` no se repita; si otro proceso tiene la base bloqueada más allá del tiempo de espera, `save_event` falla con `SessionStoreError` y no guarda.
- **Contenido grande o con Unicode**: se guarda y lee sin cambios (UTF-8).
- **Tuplas en el contenido**: vuelven como listas (JSON); se documenta.
- **Contenido con claves no cadena**: JSON las convierte a cadena; claves no serializables se rechazan.
- **Almacén cerrado**: `save_event` y `load_session` lanzan `SessionStoreError`.
- **Tipo de evento**: se guarda su valor canónico y al leer se reconstruye `EventType`; un valor desconocido en la base se trata como base dañada (`SessionStoreError`).
- **Evento sin zona horaria**: `Event` ya lo normaliza a UTC.
- **Secretos en el contenido**: se guardan tal cual (PD-10 abierta; HU-10-02 los redactará).

## Requirements *(mandatory)*

### Functional Requirements

**Guardar y cargar (flujo, regla 1)**

- **FR-001**: `SqliteSessionStore` MUST ser subclase de `SessionStore` e implementar `save_event(event)` y `load_session(session_id)` sin cambiar el puerto.
- **FR-002**: `save_event` MUST guardar el evento en una sola transacción: asignar `seq` (siguiente número de la sesión, empezando en 1), insertar y confirmar antes de devolver.
- **FR-003**: Al devolver `save_event`, el evento MUST estar confirmado con sincronización completa a disco (visible desde otra conexión y presente tras un cierre abrupto).
- **FR-004**: `load_session` MUST devolver los eventos de la sesión ordenados por `seq`, reconstruyendo `Event` con id, `session_id`, `EventType`, marca de tiempo UTC y contenido; una sesión sin eventos o desconocida devuelve `[]`.
- **FR-005**: `save_event` de una sesión inexistente MUST lanzar `SessionNotFound` sin guardar nada.
- **FR-006**: Un id de evento repetido MUST rechazarse con error de dominio y dejar el original intacto.
- **FR-007**: El contenido MUST guardarse como JSON; si no es serializable, MUST lanzarse `EventSerializationError` antes de abrir la transacción; el mensaje no reproduce el contenido.
- **FR-008**: Los eventos de una sesión MUST NOT mezclarse con los de otra y `seq` MUST ser único y sin huecos por sesión, también tras un guardado fallido.

**Cortes abruptos (AC-01, AC-02, regla 2)**

- **FR-009**: Una escritura sin confirmar MUST NOT dejar rastro tras un corte: al reabrir, la base pasa `PRAGMA integrity_check` y no contiene el evento a medias.
- **FR-010**: Un fallo del motor durante el guardado MUST revertir la transacción, lanzar `SessionStoreError` (mensaje fijo, sin datos ni rutas) y dejar el almacén utilizable.
- **FR-011**: El guardado MUST tomar el bloqueo de escritura al empezar la transacción para que dos escritores no asignen el mismo `seq`.

**Calidad y alcance**

- **FR-018**: `attach_event_recorder(bus, store)` MUST suscribir `store.save_event` a cada valor de `EventType` y depender solo de los puertos `EventBus` y `SessionStore`; los fallos del almacén MUST propagarse por el mecanismo del bus, nunca silenciarse.
- **FR-012**: MUST NOT modificarse el puerto `SessionStore`, `core/events.py`, `tests/doubles/` ni el bucle; `core/` sigue sin importar `sqlite3`.
- **FR-013**: Las pruebas de cierre abrupto MUST usar procesos hijos reales y funcionar en Windows y Linux, sin red.
- **FR-014**: MUST existir una prueba de contrato compartida entre `InMemorySessionStore` y `SqliteSessionStore` para lo común del puerto.
- **FR-015**: Las consultas MUST usar parámetros enlazados; los errores del motor se traducen sin reproducir datos.
- **FR-016**: `ruff format --check`, `ruff check`, `mypy src tests` y `pytest` MUST pasar y la cobertura del código nuevo MUST ser del 100 % (líneas y ramas).
- **FR-017**: Al cerrar, `docs/PROGRESO.md` MUST reflejar la historia (estado «En revisión», archivos y evidencia, riesgo PD-10 explícito) según el Principio VIII.

### Key Entities

- **Evento guardado**: un `Event` con su orden (`seq`) dentro de la sesión; la fila combina id, sesión, orden, tipo, contenido JSON y fecha.
- **Orden de sesión (`seq`)**: número consecutivo por sesión que define el orden de lectura.
- **SessionNotFound / EventSerializationError**: errores de dominio del adaptador para la sesión inexistente y el contenido no serializable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de 20 repeticiones de la prueba de cierre abrupto, el evento confirmado está al reabrir la base (en Windows y Linux).
- **SC-002**: En el 100 % de 20 repeticiones del corte a mitad de escritura, la base pasa la comprobación de integridad y no contiene el evento a medias; los anteriores siguen.
- **SC-003**: 1 000 eventos guardados y cargados mantienen el orden y los valores sin pérdida ni duplicados (100 %).
- **SC-004**: Un guardado toma menos de 100 ms de mediana en la prueba de 100 eventos sobre un archivo temporal.
- **SC-005**: El 100 % de los intentos inválidos (sesión inexistente, id repetido, contenido no serializable, almacén cerrado) se rechazan sin modificar la base.
- **SC-006**: 0 pruebas existentes modificadas o en rojo por esta historia; el código nuevo al 100 % de cobertura; `ruff`, `mypy` y `pytest` en 0.

## Assumptions

- **HU-03-01 no está integrada en `main` todavía**; esta historia parte de su rama (apilada) y su PR debe integrarse después.
- **HU-00-01 sigue pendiente de aprobación técnica.** No se cambia ningún puerto.
- **Sesión previa obligatoria**: la raíz de composición deberá llamar a `create_session` antes del primer evento; hoy `run_cli` usa identificadores de sesión sin crear (hallazgo para B y C).
- **Conexión real**: `attach_event_recorder` existe y se prueba con el bucle real, pero quien lo invoca en la aplicación será la raíz de composición (aún inexistente).
- **Redacción de secretos (PD-10)**: sin decidir; se guarda el contenido tal cual y se deja el riesgo explícito.
- **Sin WAL**: durabilidad con el diario por defecto y sincronización completa; migrar a WAL sería una decisión posterior con medición.
- **Estimación**: según `docs/03-plan-sprints.md`, 3 PHU; la verificación con procesos hijos puede exceder el presupuesto y se avisará a B.
- **Nombres en inglés** para clases y métodos (decisión del 2026-10-17); textos de usuario y documentación en español.
