# Feature Specification: HU-03-01 — Esquema SQLite y creación de sesión

**Feature Branch**: `014-sqlite-session-schema`

**Created**: 2026-10-23

**Status**: Draft

**Proyecto**: HARNESS v2.5 | **Sprint**: 1 | **Responsable**: B — Estado | **Tareas de referencia**: Sp1-26, Sp1-27, Sp1-28 | **Requisitos**: RF-3.1 | **Depende de**: HU-00-01 (contratos; sigue «Pendiente de aprobación técnica»)

**Input**: User description: "HU-03-01 — Esquema SQLite y creación de sesión (docs/04b-historias-estado.md#hu-03-01)."

## Clarifications

### Session 2026-10-23

Sin preguntas de producto abiertas: las ambigüedades halladas son de diseño y se resuelven con los contratos existentes; quedan como supuestos por confirmar con B.

- Q: ¿`create_session` va en el puerto `SessionStore` o en el adaptador? → A: En el adaptador; el puerto es contrato protegido (A, B y C) y se deja como observación.
- Q: ¿`SqliteSessionStore` hereda ya de `SessionStore`? → A: No; heredará en HU-03-02, cuando exista `save_event`/`load_session`. Evita métodos que fallen a propósito.
- Q: ¿Qué devuelve `create_session`/`get_session`, si `SessionSummary` no trae el padre? → A: Un tipo propio del adaptador, `StoredSession` (id, status, created_at, model, goal, parent_id), inmutable. `list_sessions` devuelve `SessionSummary`. `get_session` de un id desconocido devuelve `None`.
- Q: ¿Formato del identificador y de la fecha? → A: UUID v4 en texto (generador inyectable) y fecha UTC en ISO-8601 con zona.
- Q: ¿Se puede elegir el estado al crear? → A: No; toda sesión nace `active`.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04b-historias-estado.md` (HU-03-01). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

**Flujo general**

1. El usuario inicia una sesión.
2. El sistema crea el registro con identificador único y marca de tiempo.
3. La sesión queda en estado activa.

**Reglas de negocio**

1. Una sesión de subagente guarda el identificador de su sesión padre.

**Criterios de aceptación**

- **AC-01 — Sesión creada con identificador y fecha.** Dado el inicio de una sesión, cuando se crea, entonces tiene identificador único, marca de tiempo y estado.

### Lo que ya existe y lo que cambia

- **Existe y no se toca**: el puerto `SessionStore`, `SessionSummary` (`core/interfaces/storage.py`), `Event`, el bus, el bucle de A, la CLI y el doble `InMemorySessionStore`. `config.py` ya expone `paths.sessions_db` (por defecto `.harness/sessions.db`).
- **Se añade**: el adaptador `SqliteSessionStore` en `adapters/storage/` con el esquema de las tablas de sesiones y eventos y la creación de sesiones, y sus pruebas.
- **Hallazgo (no se resuelve aquí)**: el puerto `SessionStore` no tiene operación para *crear* una sesión (solo `save_event`, `load_session`, `list_sessions`). Cambiar un puerto exige acuerdo de A, B y C; esta historia no lo toca y ofrece `create_session` como operación propia del adaptador. Queda como observación para A, B y C.

### User Story 1 - Crear una sesión con identificador, fecha y estado (Priority: P1) [AC-01]

Como usuario operador, quiero que cada sesión nueva se cree con un identificador único, una marca de tiempo y el estado «activa», para poder volver a ella más tarde.

**Why this priority**: Es el criterio AC-01 y el flujo general; HU-03-02 a HU-03-06, la memoria y los subagentes cuelgan de que exista la sesión.

**Independent Test**: Se abre el almacén sobre una base nueva, se crea una sesión, y se lee de vuelta: tiene identificador no vacío, fecha en UTC igual a la del reloj inyectado y estado `active`; crear una segunda produce otro identificador.

**Acceptance Scenarios**:

1. **Given** una base de datos recién creada, **When** se crea una sesión, **Then** queda guardada con identificador único, marca de tiempo UTC y estado `active`.
2. **Given** dos sesiones creadas una tras otra, **When** se comparan, **Then** sus identificadores son distintos.
3. **Given** una sesión creada con modelo y objetivo opcionales, **When** se lee, **Then** los conserva; sin ellos quedan vacíos (`None`).
4. **Given** una sesión creada, **When** se cierra y se vuelve a abrir el archivo de la base, **Then** la sesión sigue ahí con los mismos datos.
5. **Given** la sesión creada, **When** se consulta con `list_sessions`, **Then** aparece como `SessionSummary` con los mismos valores.

---

### User Story 2 - Sesión de subagente enlazada a su padre (Priority: P1) [Regla 1]

Como orquestador, quiero que la sesión de un subagente guarde el identificador de su sesión padre, para reconstruir la jerarquía de ejecución.

**Why this priority**: Regla de negocio 1 de la historia; HU-09-01 la usa.

**Independent Test**: Se crea una sesión padre y una hija indicando el padre; al leerlas, la hija conserva el identificador del padre y la padre no tiene ninguno. Indicar un padre inexistente se rechaza.

**Acceptance Scenarios**:

1. **Given** una sesión existente, **When** se crea otra indicando su identificador como padre, **Then** la hija guarda ese identificador.
2. **Given** un identificador de padre que no existe, **When** se intenta crear la hija, **Then** se rechaza con un error de dominio claro y no se crea nada.
3. **Given** una sesión sin padre, **When** se lee, **Then** su padre es vacío.

---

### User Story 3 - Esquema versionado, idempotente y que falla cerrado (Priority: P2)

Como equipo, quiero que abrir la base cree el esquema si falta, sea inocuo si ya existe y se niegue a usar una base de una versión desconocida, para no corromper datos ni sobrescribirlos.

**Why this priority**: Sp1-26 pide diseñar las tablas de sesiones y eventos; HU-03-02 escribirá sobre la tabla de eventos y las demás historias del Sprint 2 migrarán el esquema.

**Independent Test**: Se abre dos veces el mismo archivo y los datos persisten; se abre una base con una versión de esquema más nueva y se obtiene un error de dominio sin modificarla; se intenta insertar un evento con sesión inexistente o duplicar el orden de un evento y la base lo rechaza.

**Acceptance Scenarios**:

1. **Given** una ruta cuyo directorio no existe, **When** se abre el almacén, **Then** se crea el directorio y la base con el esquema.
2. **Given** una base ya creada con datos, **When** se vuelve a abrir, **Then** el esquema no se recrea ni se pierde ningún dato.
3. **Given** una base marcada con una versión de esquema mayor que la conocida, **When** se abre, **Then** falla con un error de dominio y no la modifica.
4. **Given** el esquema, **When** se inspecciona, **Then** existen las tablas de sesiones y de eventos con los campos de `docs/02-arquitectura.md` §4, con nombres en inglés.
5. **Given** la tabla de eventos, **When** se inserta un evento de una sesión inexistente o con un orden repetido en la misma sesión, **Then** la base lo rechaza.
6. **Given** un archivo que no es una base SQLite válida o un fallo del motor, **When** se abre o se crea una sesión, **Then** el error del motor se traduce a un error de dominio sin reproducir datos de entrada ni rutas completas en el mensaje.

---

### Edge Cases

- **Identificadores y reloj inyectados**: el almacén recibe un reloj y un generador de identificadores por constructor para que las pruebas sean deterministas.
- **Marca de tiempo sin zona**: si el reloj devuelve una fecha sin zona se interpreta como UTC, y una con zona se convierte a UTC; nunca se guarda una hora local.
- **Estado inválido**: solo `active`, `completed` e `interrupted` (los de `SessionSummary`); la base rechaza cualquier otro.
- **Texto largo o con caracteres especiales en objetivo/modelo**: se guarda y se lee sin cambios (parámetros enlazados, nunca concatenados).
- **Ruta `:memory:`**: válida para pruebas.
- **Cierre**: el almacén ofrece un cierre explícito y es utilizable como gestor de contexto; usarlo cerrado falla con error de dominio.
- **Misma ruta abierta dos veces a la vez**: el motor lo permite; la concurrencia de escritores y la durabilidad ante cortes pertenecen a HU-03-02.

## Requirements *(mandatory)*

### Functional Requirements

**Esquema (Sp1-26)**

- **FR-001**: El adaptador MUST crear, si no existen, la tabla de sesiones (`id`, `parent_id`, `created_at`, `model`, `goal`, `status`) y la de eventos (`id`, `session_id`, `seq`, `type`, `content`, `created_at`, `compacted_by`), según `docs/02-arquitectura.md` §4 con nombres en inglés.
- **FR-002**: El esquema MUST imponer integridad: identificador único, estados permitidos, padre y sesión de evento como claves foráneas activas y orden de evento único por sesión.
- **FR-003**: El esquema MUST llevar un número de versión; abrir una base de versión mayor a la conocida MUST fallar sin modificarla (falla cerrada).
- **FR-004**: Abrir una base existente MUST ser idempotente y no perder datos.

**Creación de sesión (AC-01, regla 1)**

- **FR-005**: `create_session(model=None, goal=None, parent_id=None)` MUST crear una sesión con identificador único, marca de tiempo UTC del reloj inyectado y estado `active`, y devolver un `StoredSession` (tipo del adaptador con id, status, created_at, model, goal y parent_id).
- **FR-006**: Un `parent_id` indicado MUST existir; si no, se rechaza con un error de dominio y no se crea la sesión.
- **FR-007**: El adaptador MUST permitir leer el identificador del padre de una sesión (`get_session(session_id)` → `StoredSession | None`), sin alterar `SessionSummary` del puerto.
- **FR-008**: `list_sessions()` MUST devolver las sesiones creadas como `SessionSummary`, de la más antigua a la más reciente.
- **FR-009**: Las sesiones MUST persistir al cerrar y reabrir el archivo.

**Conexión y errores**

- **FR-010**: El almacén MUST recibir la ruta de la base, el reloj y el generador de identificadores por constructor; MUST NOT leer configuración ni entorno por sí mismo (la ruta viene de `HarnessConfig.paths.sessions_db` en la raíz de composición).
- **FR-011**: Los errores del motor (`sqlite3.Error`) MUST traducirse a un error de dominio propio del adaptador; sus mensajes MUST NOT reproducir objetivo, modelo ni datos de entrada.
- **FR-012**: Todas las consultas MUST usar parámetros enlazados.
- **FR-013**: El almacén MUST poder cerrarse de forma explícita y usarse como gestor de contexto.

**Calidad y alcance**

- **FR-014**: MUST NOT modificarse el puerto `SessionStore`, `core/events.py`, `tests/doubles/` ni el bucle; `core/` sigue sin importar `sqlite3`.
- **FR-015**: El adaptador MUST importar solo biblioteca estándar y la API pública de `harness_agent.core`, y existir una guarda `ast` en `tests/architecture/` que lo compruebe.
- **FR-016**: `ruff format --check`, `ruff check`, `mypy src tests` y `pytest` MUST pasar y la cobertura del módulo nuevo MUST ser del 100 % (líneas y ramas).
- **FR-017**: Al cerrar, `docs/PROGRESO.md` MUST reflejar la historia (estado «En revisión», archivos y evidencia) según el Principio VIII.

### Key Entities

- **Sesión**: unidad de trabajo del agente. Identificador, fecha de creación (UTC), estado, modelo y objetivo opcionales, y sesión padre opcional (subagentes).
- **Evento (fila)**: registro ordenado de lo ocurrido en una sesión; en esta historia solo se define su tabla; su escritura y lectura son de HU-03-02.
- **Versión de esquema**: número que permite migrar el esquema en historias futuras y negarse a abrir uno desconocido.
- **Error de almacenamiento**: error de dominio propio del adaptador que envuelve los fallos del motor sin datos sensibles.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Crear 100 sesiones seguidas produce 100 identificadores distintos, cada una con fecha y estado `active` (100 %).
- **SC-002**: Tras cerrar y reabrir el archivo, el 100 % de las sesiones creadas se recuperan con los mismos valores.
- **SC-003**: La creación de una sesión toma menos de 100 ms en cada caso de prueba sobre un archivo temporal.
- **SC-004**: El 100 % de los intentos inválidos (padre inexistente, estado fuera de catálogo, versión desconocida, orden de evento repetido) se rechazan sin modificar la base.
- **SC-005**: 0 pruebas existentes modificadas y 0 en rojo; `core/` sin importar `sqlite3`.
- **SC-006**: El módulo nuevo tiene 100 % de cobertura de líneas y ramas; `ruff`, `mypy` y `pytest` terminan con código 0.

## Assumptions

- **HU-00-01 sigue pendiente de aprobación técnica.** Esta historia no cambia ningún puerto, pero depende de él.
- **El puerto no tiene `create_session`.** Se ofrece en el adaptador; si A, B y C deciden ampliar el puerto, se moverá allí (observación en `PROGRESO.md`).
- **Alcance respecto a HU-03-02**: aquí solo se define la tabla de eventos. `save_event` y `load_session` (y por tanto que `SqliteSessionStore` herede formalmente de `SessionStore`) llegan con HU-03-02; mientras tanto la clase no se declara subclase del puerto, para no entregar métodos que fallen a propósito. `list_sessions` sí se ofrece porque es lectura simple de lo creado aquí y lo reutilizan HU-03-03.
- **Tablas restantes** (`resumenes`, `contexto_esencial`, `criterios`, `memorias`, `auditoria`, `trazas`) pertenecen a sus historias (HU-02-xx, HU-04-01, HU-11-01…); no se crean ahora.
- **Estados** limitados a `active`, `completed`, `interrupted` (docstring de `SessionSummary`); ampliar el catálogo requiere migrar el esquema.
- **Ruta por defecto** `.harness/sessions.db` (D3 de HU-00-04, por confirmar con B).
- **Protección de la base ante las herramientas de archivos** es la decisión abierta PD-09; no se aborda aquí.
- **Nombres en inglés** para clases, tablas y columnas (decisión del 2026-10-17); textos de usuario y documentación en español.
- **Durabilidad** (modo de diario, sincronización, cortes abruptos) pertenece a HU-03-02; aquí se usa la configuración por defecto del motor.
- **Estimación**: Sp1-26 (1,5 h), Sp1-27 (3 h), Sp1-28 (1,5 h) = 6 h; las guardas, el registro de PROGRESO y la documentación pueden excederlas, y se avisará a B.
