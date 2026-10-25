# Feature Specification: HU-11-01 — Tarea con criterios de aceptación protegidos en SQLite

**Feature Branch**: `feat/hu-11-01-task-protected-criteria` (el directorio de la spec es `021-task-protected-criteria`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-25

**Status**: Borrador (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 2 | **Responsable**: A — Núcleo | **Tareas de referencia**: Sp2-37 a Sp2-42 | **Requisitos**: RF-11.1 | **Depende de**: HU-03-01 (esquema SQLite, integrada), HU-01-01 (bucle, integrada), HU-05-01 (política de permisos, integrada); además HU-01-04 (shell, integrada) para la parte del shell

**Input**: User description: "HU-11-01 — Tarea con criterios de aceptación protegidos en SQLite (docs/04e-historias-coding-harness.md#hu-11-01). Formato de la tarea y su validación; criterios en la tabla `criterios` de SQLite como fuente de verdad con una copia JSON de solo lectura; protección del directorio del harness (base de datos y exportación) con reglas de denegación en archivos y, dentro de lo que la política actual permite, en el shell; huella de la exportación, restauración y registro del intento; lectura de la tarea desde un archivo y desde un issue con la CLI de GitHub; sesión nueva con la tarea como objetivo. Fuera de alcance: HU-05-02 (análisis de comandos compuestos), HU-11-03, HU-11-04.1, HU-02-06.1, cambios a puertos de `core/interfaces/` y a `core/events.py`."

## Clarifications

### Session 2026-10-25

Decisiones por defecto del análisis previo; las que dependen del responsable se confirman en `/speckit-clarify`.

- Q: ¿Qué formato tiene la tarea? → A: **Markdown** con secciones fijas (`# Título`, `## Objetivo`, `## Contexto`, `## Reglas`, `## Criterios de aceptación`). Es el mismo formato en el archivo y en el cuerpo de un issue de GitHub, así que un solo analizador sirve a las dos fuentes. El analizador es una función pura del núcleo (solo texto).
- Q: ¿Cómo se escribe un criterio? → A: Un elemento de lista; el texto es la descripción. Un criterio objetivo lleva debajo `comando:` y `espera:`; uno sin `comando:` es semántico (regla 5). `espera:` sin `comando:` y `comando:` sin `espera:` se rechazan. La gramática de la condición la define y evalúa HU-11-04.1; aquí solo se exige texto no vacío.
- Q: ¿Dónde se guardan reglas y contexto? → A: En esta historia, la sesión guarda como objetivo (`sessions.goal`) el objetivo de la tarea. Inyectar objetivo, reglas y criterios en el prefijo estable es de HU-02-06.1 / HU-02-01 (tabla `contexto_esencial`), que dependen de esta. La tarea analizada (con reglas y contexto) se devuelve al llamador para que esas historias la usen.
- Q: ¿Qué puerto implementa el almacén? → A: `TaskCriteria` (sin cambios). El puerto no tiene operación para crear criterios ni expone tipo ni condición; el adaptador de SQLite ofrece esas operaciones adicionales propias (como `create_session` en `SqliteSessionStore`) y el tipo se deriva de si hay comando. Ampliar el puerto queda como hallazgo para A, B y C.
- Q: ¿Cómo se registra una anomalía? → A: Con el evento ya existente `criteria_tampered` del catálogo, publicado en el bus (que ya persiste el registrador). No se añaden eventos.
- Q: ¿Las herramientas del agente deben tener también prohibido LEER el directorio `.harness/`, o solo escribir? → A: **Denegar todo** (confirmado por el usuario, 2026-10-25): cualquier llamada cuyo `path` caiga dentro, o cuyo comando de shell lo nombre, se deniega, sea de lectura o de escritura. Cierra PD-09 en su variante estricta para las herramientas controladas.
- Q: ¿La CLI de GitHub? → A: `gh issue view <n> --json title,body` detrás de una función inyectable; las pruebas no usan red ni `gh`. Si `gh` no está instalado o falla, error claro en español y nada se crea.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados de `docs/04e-historias-coding-harness.md` (HU-11-01). No se reescriben ni se amplían (Principio V de la constitución).

**Flujo general**

1. El usuario escribe el archivo de tarea (o indica un issue de GitHub).
2. El sistema lo lee y valida que tenga objetivo y criterios.
3. Guarda los criterios en SQLite, todos con passes en falso, y exporta una copia JSON de solo lectura.
4. Crea una sesión nueva para la tarea.
5. Inyecta el objetivo, las reglas y los criterios en el prefijo estable (esto último es de HU-02-06.1; aquí queda disponible la tarea analizada).

**Reglas de negocio**

1. Una sesión corresponde a una tarea.
2. Una tarea sin criterios de aceptación se rechaza.
3. El objetivo y los criterios viven fuera del historial compactable.
4. La verificación lee siempre desde SQLite; la copia JSON es informativa y se restaura ante cambios. Debe fallar cerrada ante cualquier indicio de alteración de la fuente protegida.
5. Un criterio objetivo declara su comando de verificación y su condición; uno sin comando es semántico.
6. Limitación: la protección por reglas del shell depende de interpretar comandos; el aislamiento verificable es HU-IN-02 (riesgo R-21).

**Criterios de aceptación**

- **AC-01 — Sesión y criterios creados desde la tarea.** Dado un archivo de tarea con objetivo, reglas y criterios, cuando se inicia la tarea, entonces se crea una sesión nueva y los criterios (descripción, tipo objetivo o semántico, comando de verificación, condición esperada y passes en falso) se guardan en la tabla criterios de SQLite, con una copia JSON de solo lectura.
- **AC-02 — Tarea sin criterios rechazada.** Dado un archivo de tarea sin criterios de aceptación, cuando se inicia, entonces el sistema lo rechaza e indica qué falta.
- **AC-03 — Criterios protegidos y copia restaurada.** Dado un intento de escritura sobre los criterios mediante las herramientas controladas del harness, cuando la política lo evalúa, entonces lo deniega y registra; si la copia JSON cambia, el harness ignora esa copia, la restaura desde SQLite y registra la anomalía. Esto NO demuestra aislamiento ante un shell arbitrario con los mismos privilegios que el harness: tal garantía queda condicionada a PD-06 y exige una prueba independiente de acceso denegado.

### Lo que ya existe y lo que cambia

- **Existe y no se toca**: puertos de `core/interfaces/`, `core/events.py`, `core/loop.py`, bus, CLI, `tests/doubles/`, herramientas y shell de HU-01-03/HU-01-04.
- **Se añade**: formato y validación de la tarea (núcleo), almacén de criterios y migración 2 del esquema (adaptador de SQLite), exportación con huella y restauración, decorador de política que protege el directorio del harness (núcleo), lectura desde archivo y desde `gh`, función que inicia la tarea y su cableado mínimo en `bootstrap.py`.

### User Story 1 - Iniciar una tarea desde un archivo (Priority: P1)

Como usuario operador, quiero iniciar una tarea desde un archivo con objetivo, reglas y criterios, para que el agente reciba una orden verificable en una sesión nueva.

**Why this priority**: Es AC-01 y AC-02; todo lo demás del Coding Harness depende de ello.

**Independent Test**: Escribir un archivo de tarea válido, iniciarla con una base temporal y comprobar la sesión, las filas de `criterios` con passes en falso y el JSON de solo lectura; repetir con un archivo sin criterios y comprobar el rechazo con el motivo y que no se creó nada.

**Acceptance Scenarios**:

1. **Given** una tarea válida con un criterio objetivo y uno semántico, **When** se inicia, **Then** hay una sesión nueva `active` cuyo objetivo es el de la tarea, dos filas en `criterios` (tipo, comando, condición, passes falso, orden) y un JSON de solo lectura con el mismo contenido.
2. **Given** una tarea sin criterios, **When** se inicia, **Then** se rechaza con un mensaje que dice qué falta y no se crea sesión, filas ni JSON.
3. **Given** una tarea sin objetivo, con un criterio con `comando:` sin `espera:` (o al revés), vacía o demasiado grande, **When** se inicia, **Then** se rechaza con el motivo y sin efectos.
4. **Given** una tarea ya iniciada, **When** se inicia otra, **Then** cada una tiene su propia sesión y sus propios criterios (una sesión, una tarea).

---

### User Story 2 - Iniciar una tarea desde un issue de GitHub (Priority: P2)

Como usuario operador, quiero indicar un issue de GitHub, para no copiar el ticket a mano.

**Why this priority**: Parte de la descripción de la historia; el archivo ya cubre AC-01/AC-02.

**Independent Test**: Con una función inyectada que simula `gh`, iniciar `issue 14` y comprobar que el resultado es igual al de un archivo con el mismo contenido; con la función fallando, comprobar el error y la ausencia de efectos.

**Acceptance Scenarios**:

1. **Given** un issue cuyo cuerpo tiene el formato de tarea, **When** se inicia desde el issue, **Then** el resultado es el de US1 y el título del issue se usa si el cuerpo no trae `# Título`.
2. **Given** `gh` ausente, sin sesión iniciada, issue inexistente o salida que no es JSON, **When** se inicia, **Then** error en español sin reproducir la salida de `gh` y sin efectos.
3. **Given** un número de issue no válido, **Then** se rechaza antes de lanzar ningún proceso.

---

### User Story 3 - Los criterios no se pueden tocar con las herramientas (Priority: P1)

Como usuario operador, quiero que el agente no pueda modificar sus propios criterios con las herramientas del harness, para que no pueda darse por aprobado.

**Why this priority**: Es AC-03, razón de ser de la historia.

**Independent Test**: Con la política real y el decorador de protección, evaluar llamadas de escritura, lectura, listado, búsqueda y shell sobre `.harness/` y comprobar `deny`; evaluar las mismas sobre otras rutas y comprobar que la decisión no cambia.

**Acceptance Scenarios**:

1. **Given** una llamada con `path` dentro del directorio del harness (base de datos o exportación; rutas relativas, absolutas, con `..`, mayúsculas o enlaces), **When** la política la evalúa, **Then** se deniega, para cualquier herramienta, sin llegar a pedir aprobación.
2. **Given** una llamada a `shell` cuyo comando nombra el directorio o los archivos protegidos (sin distinguir mayúsculas ni separadores), **When** se evalúa, **Then** se deniega.
3. **Given** cualquier otra llamada, **When** se evalúa, **Then** la decisión es la de la política subyacente, sin cambios.
4. **Given** un fallo al evaluar la protección, **Then** se deniega (falla cerrada).
5. **Given** un comando compuesto, con variables, comodines u ofuscado que no nombra literalmente lo protegido, **Then** no se detecta: es la limitación documentada (HU-05-02 y HU-IN-02; AC-03 no afirma aislamiento).

---

### User Story 4 - La copia JSON alterada se restaura (Priority: P1)

Como usuario operador, quiero que un cambio en la copia JSON se detecte, se descarte y se registre, para que la fuente de verdad siga siendo SQLite.

**Why this priority**: Es la segunda mitad de AC-03.

**Independent Test**: Exportar, alterar o borrar el archivo, verificar y comprobar que se detecta por la huella, se restaura desde SQLite y se publica un evento `criteria_tampered` sin datos del contenido.

**Acceptance Scenarios**:

1. **Given** una copia intacta, **When** se verifica, **Then** no pasa nada y no hay eventos.
2. **Given** una copia modificada, borrada, reemplazada por un directorio o con otro contenido, **When** se verifica, **Then** se restaura desde SQLite, vuelve a ser de solo lectura y se publica `criteria_tampered`.
3. **Given** que la propia base muestra indicios de alteración (filas que incumplen las reglas del esquema, `passes` verdadero sin evidencia, sello que no coincide con las filas), **When** se leen los criterios, **Then** se falla cerrado con un error y se publica `criteria_tampered`; nunca se devuelven datos dudosos.
4. **Given** que el archivo no se puede restaurar (permisos, disco), **Then** se falla cerrado con error claro; no se da la copia por buena.

---

### User Story 5 - La base existente sigue funcionando (Priority: P2)

Como mantenedor, quiero que una base de sesiones creada con el esquema 1 se actualice sin perder datos.

**Why this priority**: Regla del encargo: ampliar el esquema sin romper bases existentes.

**Independent Test**: Crear una base con el DDL de la versión 1, abrirla con esta versión y comprobar la versión 2 y los datos.

**Acceptance Scenarios**:

1. **Given** una base en versión 1 con sesiones y eventos, **When** se abre con esta versión, **Then** pasa a versión 2 con la tabla `criterios` y los datos previos intactos.
2. **Given** una base de versión mayor desconocida, **Then** se rechaza como hoy.

---

### Edge Cases

- **Archivo ilegible, inexistente, con codificación inválida o enorme** (límite de tamaño): error en español sin ruta ni contenido.
- **Duplicados**: descripciones iguales son criterios distintos; el orden de aparición se conserva.
- **Texto de criterio muy largo o con caracteres de control**: se rechaza con motivo.
- **Secciones repetidas o desconocidas**: se rechazan (falla cerrada); el orden de las secciones no importa.
- **Escritura parcial**: la sesión, las filas y el sello se crean en una sola transacción; si falla la exportación, no queda tarea a medias utilizable (se informa y se limpia lo creado).
- **`mark_passes`**: solo el adaptador lo ofrece; exige evidencia no vacía; id inexistente es error; nunca cambia otros campos.
- **Directorio del harness**: se deriva de la ubicación de la base de sesiones; si no se puede determinar, no se inicia ninguna tarea (no se inicia nada sin protección).
- **Windows**: nombres sin distinguir mayúsculas, separadores `\` y `/`, ruta de 260 caracteres.
- **Secretos**: ni mensajes de error ni eventos reproducen el contenido de la tarea (valor centinela en pruebas). La redacción de secretos sigue siendo PD-10.

## Requirements *(mandatory)*

### Functional Requirements

**Formato y validación (Sp2-37)**

- **FR-001**: Existe una función pura que convierte el texto Markdown de una tarea en una tarea validada (título, objetivo, contexto, reglas, criterios) o rechaza con un error que dice qué falta o qué está mal.
- **FR-002**: Se rechaza: texto vacío o mayor que el máximo; sin `## Objetivo` con texto; sin criterios (AC-02); `comando:`/`espera:` desparejados; secciones repetidas o desconocidas; más criterios que el máximo; textos con caracteres de control.
- **FR-003**: Un criterio con comando es objetivo; sin comando, semántico. Todos nacen con `passes` falso.
- **FR-004**: Los mensajes de error son fijos en español y no reproducen el texto de la tarea.

**Almacén (Sp2-38)**

- **FR-005**: El esquema pasa a la versión 2 con la tabla `criterios` (id, sesion_id, orden, descripcion, tipo, comando, condicion, passes, evidencia, confirmado_por) y restricciones; la migración 1→2 conserva los datos y una base ya en 2 se acepta.
- **FR-006**: Un adaptador implementa `TaskCriteria` (`load_criteria`, `get_pending`, `mark_passes`, `export_readonly_copy`) y añade `store_task` (crear criterios de una sesión, atómico). Lee siempre desde SQLite.
- **FR-007**: `mark_passes` exige evidencia no vacía y solo cambia `passes` y `evidencia`. Ninguna herramienta lo expone.
- **FR-008**: La exportación escribe JSON determinista (formato del prototipo de la ficha), de solo lectura, sin tocar nada fuera de su ruta.
- **FR-009**: Los criterios se leen con validación; cualquier fila inválida o un sello de integridad que no coincide produce un error de integridad (falla cerrada) y el evento de anomalía.

**Protección (Sp2-39)**

- **FR-010**: Un decorador de `PermissionPolicy` deniega cualquier llamada con `path` dentro del directorio protegido (contención real vía `AuthorizedArea`) y cualquier llamada a `shell` cuyo `command` nombre el directorio o archivos protegidos, antes de consultar la política subyacente; lo demás se delega sin cambios. Falla cerrada. Sin cambio de `DefaultPermissionPolicy`.
- **FR-011**: La limitación del shell (comandos compuestos, variables, ofuscación) queda documentada en el código, en la spec y en `PROGRESO.md`.

**Huella y restauración (Sp2-40)**

- **FR-012**: La huella (SHA-256) del archivo exportado se compara con la de lo que SQLite produciría; si difiere, falta o no es un archivo regular, se restaura desde SQLite, se vuelve a dejar de solo lectura y se publica `criteria_tampered` (sin contenido). La verificación ocurre al iniciar la tarea y queda disponible para que HU-11-04.1 la invoque.

**Origen de la tarea (Sp2-41)**

- **FR-013**: La tarea se lee de un archivo (UTF-8, tamaño acotado) o de un issue con `gh issue view N --json title,body`, mediante una función inyectable; un número no válido se rechaza sin lanzar procesos; el título del issue completa el de la tarea si falta.

**Sesión (Sp2-42)**

- **FR-014**: Una función de arranque de tarea valida, crea la sesión con el objetivo, guarda los criterios y exporta, de forma que o queda todo o no queda nada; devuelve el identificador de sesión, la tarea analizada y la ruta de la exportación.
- **FR-015**: `bootstrap.py` cablea el almacén de criterios y el decorador de protección (con el directorio del harness derivado de `paths.sessions_db`) y expone lo necesario para iniciar una tarea. No se añade un comando de CLI nuevo ni se cambia `cli/`.

**Calidad**

- **FR-016**: `core/` usa solo biblioteca estándar y `harness_agent.core`; SQLite solo en `adapters/storage/`; lo público nuevo se exporta; cada módulo nuevo trae su guarda en `tests/architecture/`.
- **FR-017**: Sin cambios en `core/interfaces/`, `core/events.py`, `core/loop.py`, `cli/`, `tests/doubles/`, `docs/archivo/`.
- **FR-018**: Pruebas sin red, sin claves, sin `gh` real y sin consola; 100 % de líneas y ramas de los módulos nuevos.
- **FR-019**: Al cerrar, `docs/PROGRESO.md` refleja la historia (En revisión, archivos, evidencia, observaciones para HU-02-06.1, HU-11-03, HU-11-04.1, HU-05-02, HU-IN-02, PD-09/PD-10 y los hallazgos de puertos).

### Key Entities

- **Tarea**: título, objetivo, contexto, reglas y lista ordenada de criterios; vive como texto y como sesión.
- **Criterio**: descripción, tipo (objetivo/semántico), comando y condición opcionales, `passes`, evidencia.
- **Copia de solo lectura**: JSON informativo de los criterios de una sesión; su huella decide si se restaura.
- **Directorio protegido**: carpeta del harness (base de datos y copias) que las herramientas no pueden tocar.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una tarea válida produce una sesión, tantas filas como criterios (todas con passes falso) y su copia JSON, en una sola operación; una inválida no deja rastro (0 filas, 0 sesiones, 0 archivos).
- **SC-002**: El 100 % de las llamadas de las cinco herramientas con ruta dentro del directorio protegido se deniega, incluida una batería de rutas hostiles (relativas, `..`, mayúsculas, enlaces, rutas de Windows).
- **SC-003**: Toda alteración de la copia (modificar, borrar, reemplazar) se detecta y repara en la verificación siguiente, con un evento `criteria_tampered` por intento.
- **SC-004**: Una base creada con el esquema 1 se abre con esta versión sin perder ningún dato.
- **SC-005**: Las pruebas pasan en Windows y Linux sin omisiones propias de la historia; los cuatro comandos de calidad y `pytest tests/architecture` en exit 0; cobertura 100 % de los módulos nuevos.

## Assumptions

- Un solo proceso del harness escribe la base a la vez.
- El directorio protegido es la carpeta que contiene `paths.sessions_db` (por defecto `.harness/`); la copia JSON se guarda en ella, en `tareas/<sesión>/criterios.json`. Excepción: si esa carpeta contiene al área de trabajo (por ejemplo la base en la raíz del área), proteger la carpeta entera dejaría el harness inutilizable, así que solo se protegen la base (con sus archivos auxiliares `-wal`, `-shm`, `-journal`) y `tareas/`.
- El sello de integridad no es criptográfico ni impide a un proceso con los mismos privilegios reescribir base y sello a la vez; solo detecta alteraciones accidentales o ingenuas. El aislamiento real es PD-06 / HU-IN-02.
- PD-09 se cierra parcialmente aquí por decisión de implementación (denegar `.harness/` entero a las herramientas controladas); el PO puede ajustar.
- `gh` ya está autenticado por el usuario cuando se usa un issue; el harness no gestiona credenciales.
- Fuera de alcance: análisis de comandos compuestos (HU-05-02), inyección en el prefijo (HU-02-06.1), verificación de criterios (HU-11-04.1), pruebas y lint (HU-11-03), comando de CLI para iniciar tareas, aprobación humana (HU-05-03).
