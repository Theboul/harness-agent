# Feature Specification: HU-11-03 — Pruebas y lint mediante el shell con salida recortada

**Feature Branch**: `gustavo` (el directorio de la spec es `025-test-lint-shell-commands`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-26

**Status**: Borrador (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 2 | **PHU**: 1 | **Responsable**: C — Control y conexiones | **Tareas de referencia**: Sp2-46 (1,5 h), Sp2-47 (1 h), Sp2-48 (1,5 h) | **Requisitos**: RF-11.3 | **Depende de**: HU-01-04 (shell, integrada en `main`), HU-02-02 (recorte, integrada en `main`), HU-11-01 (tarea con criterios, integrada en `main`); las tres están `En revisión` en PROGRESO, ninguna `Hecha`

**Input**: User description: "HU-11-03 — Pruebas y lint mediante el shell con salida recortada (1 PHU). Es un comando del shell con permiso explícito, no una herramienta nueva. Sin cambiar puertos de core/interfaces ni core/loop.py; core/ solo stdlib; docs/archivo inmutable. La historia puede ser de otra área: tarea humana de revisión cruzada."

## Clarifications

### Session 2026-10-26

Respuestas del revisor a las tres preguntas abiertas de `/speckit-specify`.

- Q: ¿Dónde se declaran los comandos de pruebas y de lint (regla 1: «en la tarea o en la configuración del proyecto»)? → A: En el **archivo de la tarea**, con una sección opcional `## Comandos` y las líneas `pruebas:` y `lint:`. No se usa `config.toml`: la decisión de HU-00-04/HU-05-01 prohíbe reglas de permitir en la configuración. La ampliación del analizador de tareas (`core/tasks`, dueño A) es **aditiva**: una tarea sin la sección sigue siendo válida y las pruebas existentes no cambian. Tareas humanas: visto bueno de A a la ampliación y revisión cruzada por A o B.
- Q: ¿Cómo se hace obligatorio el tiempo máximo? → A: Cada comando lleva su tiempo máximo: el declarado o, si falta, 300 s, y nunca más que el tope del shell (600 s). La política permite solo si el tiempo de la llamada no supera el del comando; si la llamada no indica tiempo, cuenta el del shell por defecto (120 s).
- Q: ¿Los comandos de los criterios objetivos de HU-11-01 también se permiten automáticamente al agente? → A: No. Solo los dos comandos declarados; la ejecución de los criterios objetivos es de HU-11-04.1.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04e-historias-coding-harness.md` (HU-11-03). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

- **Como:** agente principal
- **Quiero:** ejecutar las pruebas y el lint con los comandos configurados en la tarea y recibir el código de salida y la salida recortada
- **Para:** saber si mis cambios funcionan y corregir los errores
- **Descripción:** El agente ejecuta las pruebas y el lint con los comandos configurados en la tarea y recibe el código de salida y la salida recortada. Es un comando del shell con permiso explícito, no una herramienta nueva.

**Flujo general**

1. El agente ejecuta el comando de pruebas configurado.
2. La política permite ese comando exacto con tiempo máximo.
3. El sistema devuelve el código de salida y los mensajes de fallo.
4. Si la salida es larga, se recorta con marca de omisión.

**Reglas de negocio**

1. Los comandos de pruebas y de lint se definen en la tarea o en la configuración del proyecto.
2. Solo se permiten automáticamente esos comandos exactos; el tiempo máximo es obligatorio.

**Criterios de aceptación**

- **AC-01 — Fallo de pruebas informado al agente.** Dado un proyecto con una prueba fallida, cuando el agente corre el comando de pruebas configurado, entonces recibe un código de salida distinto de cero y los mensajes de fallo.
- **AC-02 — Salida larga recortada.** Dado una salida muy larga de pruebas, cuando vuelve al contexto, entonces se recorta con marca de omisión.

### Lo que ya existe y lo que cambia

- **Ya existe (HU-01-04):** la herramienta `shell` ejecuta un comando con tiempo máximo (por defecto 120 s, tope 600 s), devuelve `[codigo_de_salida=N]` o `Código de salida: 0` con la salida estándar y de errores juntas, acotada con principio, final y aviso `[salida recortada: se omitieron N caracteres]`. Declara riesgo alto, así que hoy la política **siempre pregunta** (y sin aprobador, deniega).
- **Ya existe (HU-02-02):** el registro de herramientas recorta todo resultado por encima de `limits.max_tool_output_chars` (24 000) con la misma marca.
- **Ya existe (HU-11-01):** la tarea (objetivo, contexto, reglas, criterios) se lee, se valida y se guarda en SQLite al arrancar; `ProtectedPolicy` deniega antes que nadie los comandos que nombran la zona protegida.
- **Falta (esta historia):** (1) un lugar donde declarar el comando de pruebas y el de lint (Sp2-46); (2) una regla de la política que **permita sin preguntar** exactamente esos comandos, con tiempo máximo (Sp2-47); (3) la demostración con un proyecto de ejemplo que tiene una prueba fallida y una salida larga (Sp2-48). AC-01 y AC-02 dependen de piezas ya hechas; lo nuevo es que el comando llegue a ejecutarse sin aprobación manual.

### User Story 1 - El agente corre las pruebas configuradas y ve el fallo (Priority: P1)

Un operador inicia una tarea que declara su comando de pruebas. El agente, tras cambiar código, pide al shell ese comando exacto. La política lo permite sin preguntar, el comando corre con su tiempo máximo y el agente recibe el código de salida distinto de cero y los mensajes del fallo, con los que corrige su cambio.

**Why this priority**: Es AC-01 y el bucle de corrección del Coding Harness; sin ello la verificación (HU-11-04.1) y la demostración del Sprint 2 no se sostienen.

**Independent Test**: Con un proyecto de ejemplo que tiene una prueba fallida, una tarea que declara su comando de pruebas y un proveedor simulado que pide ese comando por el shell, el bucle real ejecuta el comando sin aprobador y el resultado que vuelve al modelo lleva un código distinto de cero y el nombre de la prueba fallida.

**Acceptance Scenarios**:

1. **Given** una tarea con comando de pruebas configurado y un proyecto con una prueba fallida, **When** el agente pide exactamente ese comando, **Then** la política lo permite sin preguntar y el agente recibe `[codigo_de_salida=N]` con N ≠ 0 y los mensajes de fallo.
2. **Given** el mismo proyecto con la prueba corregida, **When** el agente repite el comando, **Then** recibe código de salida 0.
3. **Given** una tarea con comando de lint configurado, **When** el agente pide ese comando exacto, **Then** se permite sin preguntar igual que el de pruebas.

---

### User Story 2 - Solo los comandos exactos se permiten solos (Priority: P1)

Cualquier comando que no sea idéntico a uno configurado sigue el camino normal del shell: se pregunta al usuario (o se deniega si no hay aprobador). Una variación mínima, un comando encadenado, un argumento añadido o un tiempo mayor que el configurado no se permiten automáticamente.

**Why this priority**: Es la regla de negocio 2 y la frontera de seguridad: un permiso automático demasiado amplio daría al agente un shell libre (riesgo R-19/R-21).

**Independent Test**: Con la política real y una tarea configurada, se evalúa una batería de llamadas parecidas al comando configurado (con `&&`, `;`, argumentos extra, mayúsculas distintas, otro tiempo) y ninguna obtiene «permitir».

**Acceptance Scenarios**:

1. **Given** el comando de pruebas configurado, **When** el agente pide ese comando seguido de `&& otro` o `; otro`, **Then** la política no lo permite automáticamente (pregunta).
2. **Given** el comando configurado, **When** el agente lo pide con un tiempo máximo mayor que el permitido para él, **Then** la política no lo permite automáticamente.
3. **Given** una tarea sin comandos de pruebas ni de lint, **When** el agente pide cualquier comando, **Then** la política se comporta exactamente como antes de esta historia.
4. **Given** el comando configurado y una regla de denegación que lo alcanza (la herramienta `shell` en `deny`, o el comando nombra la zona protegida), **When** se evalúa, **Then** se deniega: denegar prevalece sobre permitir.

---

### User Story 3 - La salida larga de las pruebas llega recortada (Priority: P2)

Una ejecución de pruebas produce una salida enorme. El agente recibe el principio (código de salida y primeros fallos) y el final (resumen), con la marca de cuántos caracteres se omitieron.

**Why this priority**: Es AC-02. Ya lo resuelven HU-01-04 y HU-02-02; aquí solo se demuestra con el comando configurado y el proyecto de ejemplo.

**Independent Test**: En el proyecto de ejemplo, una prueba que imprime mucho más que el máximo; el mensaje de herramienta del historial no supera el máximo, contiene la marca de omisión, el código de salida y el resumen final.

**Acceptance Scenarios**:

1. **Given** una ejecución de pruebas cuya salida excede el máximo, **When** el resultado vuelve al contexto, **Then** está recortado con la marca `[salida recortada: se omitieron N caracteres]` y conserva el código de salida.

---

### Edge Cases

- El comando configurado tarda más que su tiempo máximo: se termina con su árbol de procesos y el agente recibe `[tiempo_agotado]` (comportamiento de HU-01-04), sin que el permiso automático lo alargue.
- El agente pide el comando configurado sin indicar tiempo: cuenta el tiempo por defecto del shell (120 s); se permite si no supera el tiempo máximo del comando (el declarado o 300 s). Con un tiempo declarado menor que 120 s, la llamada sin tiempo no se permite sola: el agente debe indicar un tiempo que no lo supere.
- El tiempo declarado para un comando no es un número entero positivo o supera 600 s: la tarea se rechaza al arrancar con un mensaje en español que no reproduce el valor.
- Espacios al principio o al final del comando pedido: se ignoran; cualquier otra diferencia (espacios internos, mayúsculas, comillas) hace que no coincida.
- El texto configurado está vacío, en blanco, tiene caracteres de control o supera el máximo de longitud del shell: la tarea (o la configuración) se rechaza al arrancar con un mensaje en español que no reproduce el valor.
- El agente modifica después el archivo de la tarea en disco: no cambia nada; los comandos permitidos son los leídos al arrancar.
- El comando de pruebas ejecuta código del proyecto que el propio agente puede editar (por ejemplo, un `conftest.py`): es inherente a ejecutar pruebas y no lo cubre esta historia; queda como hallazgo abierto (ver Assumptions, R-21 y PD-06).
- La sección `## Comandos` de la tarea está vacía, repetida, tiene una línea distinta de `pruebas:`/`lint:` o repite una de ellas: la tarea se rechaza con un mensaje fijo, igual que los demás errores de formato de HU-11-01.
- Se arranca sin tarea: no hay comandos configurados y nada cambia respecto a hoy.
- La herramienta `shell` está en la lista `ask` de la configuración: pregunta prevalece sobre permitir (orden deny > ask > allow de HU-05-01).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El operador DEBE poder declarar, como máximo, un comando de pruebas y un comando de lint, ambos opcionales, en el **archivo de la tarea**, dentro de una sección opcional `## Comandos` con las líneas `pruebas:` y `lint:`, cada una con un tiempo máximo opcional en segundos. La configuración del proyecto (`config.toml`) no admite estos comandos: no puede definir reglas de permitir (HU-00-04/HU-05-01).
- **FR-001a**: La ampliación del formato de la tarea DEBE ser aditiva: una tarea sin la sección `## Comandos` sigue siendo válida y se interpreta igual que hoy, y las pruebas existentes del analizador no cambian sus aserciones.
- **FR-002**: Los comandos declarados DEBEN validarse al arrancar (texto no vacío, sin caracteres de control, dentro de la longitud máxima del shell) y, si no son válidos, el arranque falla cerrado con un mensaje en español que no reproduce el valor.
- **FR-003**: La política DEBE permitir sin preguntar una llamada a la herramienta `shell` solo si su comando, sin espacios al principio ni al final, es idéntico carácter a carácter a uno de los comandos declarados **y** su tiempo máximo efectivo no supera el permitido para ese comando (FR-004).
- **FR-004**: Cada comando declarado DEBE tener un tiempo máximo: el declarado o, si falta, 300 s; nunca más que el tope del shell (600 s). La política permite solo si el tiempo de la llamada no supera el del comando; si la llamada no indica tiempo, cuenta el del shell por defecto (120 s). Así todo comando permitido automáticamente se ejecuta con un tiempo máximo finito.
- **FR-005**: Cualquier otra llamada al shell DEBE decidirse exactamente igual que antes de esta historia (preguntar, o denegar sin aprobador).
- **FR-006**: Las denegaciones existentes DEBEN prevalecer sobre este permiso: zona protegida de HU-11-01, la lista `deny` de la configuración y, cuando exista, la lista de denegados de HU-05-02. La lista `ask` también prevalece.
- **FR-007**: Los comandos permitidos DEBEN ser los leídos al arrancar y no cambiar durante la ejecución (ni por cambios del archivo en disco ni por acciones del agente).
- **FR-008**: El agente DEBE poder saber qué comandos tiene permitidos y con qué tiempo máximo: el texto de la tarea que recibe el modelo los muestra tal cual, para que los pida exactamente.
- **FR-008a**: Los comandos de verificación de los criterios objetivos (`comando:`/`espera:` de HU-11-01) NO DEBEN permitirse automáticamente al agente por esta historia; su ejecución es del harness (HU-11-04.1).
- **FR-009**: El resultado del comando DEBE llegar al agente con el código de salida y la salida combinada, recortada con la marca de omisión si excede el máximo (comportamiento existente de HU-01-04 y HU-02-02, sin cambios).
- **FR-010**: Los eventos y mensajes de error que añade esta historia NO DEBEN incluir el comando ni la salida (convención de los eventos del bucle).
- **FR-011**: Ninguna herramienta nueva: la ejecución sigue siendo la herramienta `shell`.
- **FR-012**: Un proyecto de ejemplo con una prueba fallida y una prueba de salida larga DEBE servir para demostrar AC-01 y AC-02 con el bucle real, sin red ni claves, en Linux y en Windows.

### Key Entities

- **Comando de verificación de la ejecución** (pruebas o lint): tipo (pruebas | lint), texto exacto del comando y tiempo máximo (declarado o 300 s; entero de 1 a 600). Se declara en la sección `## Comandos` de la tarea, forma parte de la tarea validada y es inmutable durante la ejecución. No es un criterio de aceptación: los comandos de los criterios (`comando:`/`espera:` de HU-11-01) los ejecuta el harness en HU-11-04.1 y no se permiten automáticamente al agente (FR-008a).
- **Regla de permiso por comando exacto**: lista inmutable de comandos declarados que la política consulta antes de preguntar.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el proyecto de ejemplo, el 100 % de las ejecuciones del comando de pruebas configurado con una prueba fallida devuelven al agente un código distinto de cero y el nombre de la prueba fallida, sin intervención del usuario.
- **SC-002**: En una batería de al menos 15 variaciones del comando configurado (encadenamientos, argumentos extra, mayúsculas, comillas, espacios internos, tiempo mayor), 0 obtienen permiso automático.
- **SC-003**: Con una salida de pruebas al menos diez veces mayor que el máximo, el resultado que vuelve al contexto no supera el máximo y contiene la marca de omisión, el código de salida y el resumen final.
- **SC-004**: Sin comandos declarados, el 100 % de las pruebas existentes de la política y del arranque siguen pasando sin cambios en sus aserciones.
- **SC-005**: Ningún comando permitido automáticamente corre más de su tiempo máximo más el margen de terminación de HU-01-04.

## Assumptions

- HU-01-04, HU-02-02 y HU-11-01 están integradas en `main` (verificado en `origin/main` 38b8f1d el 2026-10-26: `adapters/tools/shell.py`, `core/tools/output_limit.py`, `core/tasks/`, `core/permissions/protected.py`, `adapters/storage/task_store.py`). Ninguna está `Hecha`; si su revisión cambia sus contratos, esta spec se revisa.
- HU-05-02 (lista de denegados y análisis de comandos compuestos) está **Pendiente**. La coincidencia exacta no necesita analizar comandos: un encadenamiento nunca es idéntico al comando declarado. Cuando HU-05-02 llegue, su denegación prevalece (FR-006).
- HU-05-03 (aprobación interactiva) está integrada: los comandos no declarados se preguntan al usuario.
- El comando corre en la raíz del área de trabajo (HU-01-04: sin carpeta persistente); el operador escribe el comando pensando en esa carpeta y con la sintaxis del intérprete de la plataforma (bash o PowerShell). Un comando que sirva en ambos (por ejemplo `python -m pytest`) es lo recomendado para el proyecto de ejemplo.
- Comparación exacta: distingue mayúsculas, no normaliza espacios internos ni comillas; solo se quitan espacios al principio y al final.
- No se cambian puertos (`core/interfaces/`), el catálogo de eventos ni `core/loop.py`. La regla nueva vive en la política (área C) y su conexión en la raíz de composición.
- Fuera de alcance: comandos en `config.toml`; ejecutar los comandos de los criterios y marcar `passes` (HU-11-04.1), reglas de git por subcomando (HU-11-02), análisis de comandos compuestos y lista de denegados (HU-05-02), aislamiento verificable (HU-IN-02 / PD-06), lectura de comandos desde un issue de GitHub más allá de lo que ya lea HU-11-01.
- Tareas humanas: visto bueno de A a la ampliación aditiva del analizador de tareas (`core/tasks`), revisión cruzada por A o B y CI remota en Windows y Linux. Claude no las marca como hechas.
- **Hallazgo abierto para PROGRESO (al cierre, en Observaciones de HU-11-03):** el comando de pruebas ejecuta código del proyecto que el agente puede editar (por ejemplo, `conftest.py`), así que permitirlo sin preguntar equivale a ejecutar código escrito por el agente con los privilegios del harness. No se cierra en esta historia; queda ligado a R-21 y a PD-06 (entorno aislado, HU-IN-02).
- Presupuesto del sprint: 4 h (Sp2-46/47/48). Es un aviso, no motivo para recortar alcance.
