# Feature Specification: Aprobación con detalle: una vez, toda la sesión o rechazar (HU-05-03)

**Feature Branch**: `019-approval-with-detail` (carpeta de la spec; el trabajo sigue en la rama `feat/hu-05-03-approval-with-detail`)

**Created**: 2026-10-25

**Status**: Draft

**Proyecto**: HARNESS v2.5 | **Sprint**: 2 | **Historia**: [HU-05-03](../../docs/04c-historias-control.md#hu-05-03) | **Responsable**: C — Control y conexiones | **Prioridad**: Alta | **Requisitos**: RF-5.4, RF-5.5, RNF-9 | **Depende de**: [HU-05-01](../../docs/04c-historias-control.md#hu-05-01), [HU-01-05](../../docs/04a-historias-fundacion.md#hu-01-05) | **Tareas del plan**: Sp2-29, Sp2-30, Sp2-31 | **Desbloquea**: [HU-05-04](../../docs/04c-historias-control.md#hu-05-04) (A, rechazo con motivo que vuelve al modelo)

**Input**: User description: "Cuando la política resuelve «preguntar», el bucle emite la solicitud de aprobación y espera la respuesta del usuario; la terminal muestra herramienta, argumentos y efecto esperado y ofrece aprobar una vez, aprobar para la sesión o rechazar; la aprobación de sesión se limita a una herramienta y un patrón de argumentos; la resolución queda como evento; todo lo no resuelto se deniega; una aprobación nunca anula una denegación."

## Clarifications

### Session 2026-10-25

Decisiones tomadas por el responsable antes de redactar (no son preguntas abiertas):

- **El bucle cambia.** Hoy el bucle resuelve «preguntar» como denegado con `[approval_required_unavailable]` (provisional de Sprint 1, AC-05 de HU-05-01, que esta historia retira). Para esperar al usuario hay que tocar `core/loop.py` (archivo protegido, dueño A). El usuario, que hace toda la Ola 1 y actúa como A, **autorizó el cambio mínimo** el 2026-10-25. Sin aprobador configurado el bucle conserva el comportamiento actual (falla cerrada).
- **No cambian** los puertos de `core/interfaces/` (ya existe `Approver.request(call, details) -> ApprovalResult` con `APPROVE_ONCE`, `APPROVE_SESSION`, `REJECT` y motivo opcional) **ni el catálogo de 17 eventos** (`APPROVAL_REQUESTED` y `APPROVAL_RESOLVED` ya existen).
- Una aprobación **solo** actúa sobre una decisión «preguntar». Una denegación de la política (zona protegida de HU-11-01, lo que evaluará HU-05-02) se decide antes y nunca llega a preguntar: ninguna aprobación, ni de una vez ni de sesión, la anula.
- Fuera de alcance: **HU-05-04** (el rechazo con motivo que vuelve al modelo como resultado de herramienta; esta historia deja el camino abierto pero el motivo escrito por el usuario no se pide ni se devuelve aquí), HU-05-02 (análisis de comandos encadenados), HU-01-06 (límites), registro de auditoría (HU-05-05, Sprint 3) y cualquier cambio de la política.

Respuestas del responsable (2026-10-25):

- Q1: ¿Qué cubre el patrón de argumentos de una aprobación de sesión? → A: **Argumentos exactos** (recomendación aceptada). La misma herramienta con argumentos distintos vuelve a pedir; generalizar (misma ruta, programa y subcomando de shell) queda para después de HU-05-02, que es quien interpreta comandos.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver qué se pide y decidir (Priority: P1)

Cuando el agente quiere hacer algo que la política no permite sin preguntar, la terminal se detiene y muestra qué herramienta, con qué argumentos y qué efecto tendría. El usuario elige **aprobar una vez**, **aprobar para la sesión** o **rechazar**. El agente solo continúa cuando el usuario decide.

**Why this priority**: es el corazón de la historia (AC-01) y lo que convierte el «preguntar» provisional en una decisión humana informada.

**Independent Test**: con un proveedor guionizado que pide una herramienta cuya decisión es «preguntar» y un aprobador de prueba que responde cada opción, comprobar que la herramienta se ejecuta tras aprobar y no se ejecuta tras rechazar, y que la terminal muestra herramienta, argumentos y efecto antes de pedir la opción.

**Acceptance Scenarios**:

1. **Given** una acción que requiere aprobación, **When** se pide, **Then** el usuario ve el nombre de la herramienta, sus argumentos y el efecto esperado antes de elegir.
2. **Given** esa petición, **When** el usuario elige aprobar una vez, **Then** la herramienta se ejecuta con exactamente los argumentos mostrados y la siguiente petición igual vuelve a preguntar.
3. **Given** esa petición, **When** el usuario elige rechazar, **Then** la herramienta no se ejecuta y el modelo recibe un resultado de error que lo explica.
4. **Given** que el bucle espera la respuesta, **When** el usuario tarda, **Then** el turno queda en espera sin ejecutar nada y sin límite propio de esta historia.

---

### User Story 2 - Aprobar para la sesión con alcance limitado (Priority: P1)

El usuario puede aprobar una acción «para la sesión» y no volver a ver la pregunta por acciones **equivalentes**: la misma herramienta con argumentos dentro del patrón aprobado. Si la misma herramienta se repite con argumentos fuera del patrón, vuelve a preguntar (AC-02).

**Why this priority**: sin alcance acotado, «para la sesión» sería un permiso general; es una regla de seguridad (regla de negocio 1 y 2).

**Independent Test**: aprobar para la sesión una llamada, repetir la misma (no pregunta), repetir la herramienta con otros argumentos (pregunta), y repetir con otra herramienta (pregunta).

**Acceptance Scenarios**:

1. **Given** una aprobación de sesión para una herramienta y un patrón, **When** llega una llamada de esa herramienta dentro del patrón, **Then** se ejecuta sin preguntar y la decisión queda registrada como evento.
2. **Given** esa aprobación, **When** llega la misma herramienta con argumentos fuera del patrón, **Then** se vuelve a pedir.
3. **Given** esa aprobación, **When** llega otra herramienta, **Then** se vuelve a pedir.
4. **Given** una aprobación de sesión, **When** la política deniega (zona protegida, denegación por regla) una llamada que el patrón cubriría, **Then** sigue denegada: la aprobación nunca anula una denegación.
5. **Given** que termina la sesión, **When** empieza otra, **Then** las aprobaciones de la sesión anterior no se conservan.

---

### User Story 3 - Fallar cerrado ante lo no resuelto (Priority: P1)

Si no hay respuesta (se acabó la entrada, la terminal falla, el aprobador lanza una excepción, devuelve algo inválido o el turno se cancela) la acción se **deniega**. Nunca se ejecuta por defecto.

**Why this priority**: principio de falla cerrada (constitución); una aprobación mal resuelta que ejecuta sería un fallo de seguridad.

**Independent Test**: aprobadores de prueba que lanzan excepción, devuelven un valor no válido o nunca responden (cancelación), y entrada de terminal agotada o ilegible; en todos los casos la herramienta no se ejecuta.

**Acceptance Scenarios**:

1. **Given** que el aprobador lanza una excepción ordinaria, **When** el bucle espera, **Then** la acción se deniega y el turno continúa con el error al modelo.
2. **Given** que el aprobador devuelve algo que no es un resultado de aprobación válido, **When** el bucle lo recibe, **Then** se deniega.
3. **Given** que la entrada de la terminal se agota o la respuesta no es una opción válida, **When** se espera la decisión, **Then** se deniega (una opción no válida se vuelve a pedir un número acotado de veces antes de denegar).
4. **Given** una cancelación del turno durante la espera, **When** se propaga, **Then** nada se ejecuta y la cancelación no se convierte en aprobación.
5. **Given** que no hay aprobador configurado, **When** la política dice «preguntar», **Then** se mantiene el comportamiento actual (denegado con `[approval_required_unavailable]`).

---

### User Story 4 - La decisión queda como evento (Priority: P2)

Cada solicitud y cada resolución quedan registradas como eventos (`APPROVAL_REQUESTED` y `APPROVAL_RESOLVED`) para que otras partes (registro de sesión, y luego la auditoría de HU-05-05) las lean sin depender de la terminal.

**Why this priority**: cierra el flujo general («el sistema registra la decisión y continúa») y lo que HU-01-05 dejó pendiente.

**Independent Test**: suscribirse al bus y comprobar, en un turno con aprobación, el orden de eventos y que el contenido no incluye valores de argumentos ni contenido de archivos.

**Acceptance Scenarios**:

1. **Given** una acción que se pregunta, **When** el bucle la procesa, **Then** emite `APPROVAL_REQUESTED` antes de esperar y `APPROVAL_RESOLVED` con la decisión después, y ambos antes de ejecutar nada.
2. **Given** una aprobación de sesión que cubre una llamada, **When** se ejecuta sin preguntar, **Then** `APPROVAL_RESOLVED` indica que la decisión vino de la aprobación de sesión.
3. **Given** que un suscriptor del bus falla al recibir el evento, **When** `emit` lanza, **Then** la herramienta no se ejecuta (igual que `PERMISSION_DECIDED`, Q4 de HU-01-05).

---

### Edge Cases

- Dos llamadas «preguntar» en el mismo turno: se piden de una en una, en orden; no se agrupan ni se aprueban juntas.
- Argumentos muy largos o con caracteres de control en la presentación: se muestran acotados y saneados, sin ejecutar nada.
- Argumentos con secretos (`api_key` y similares): la presentación no reproduce valores con aspecto de clave; los eventos nunca llevan valores de argumentos.
- Una herramienta sin descripción de efecto conocida: se muestra su descripción y su nivel de riesgo; nunca un efecto inventado.
- El usuario escribe `/salir` mientras se le pide una decisión: se rechaza la acción y termina la sesión por el camino normal (o se trata como entrada no válida; ver Asumpciones).
- Un patrón de sesión que quedaría vacío o demasiado amplio: no se crea (ver FR-009).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Cuando la política resuelve «preguntar» y hay un aprobador configurado, el bucle MUST emitir `APPROVAL_REQUESTED` y esperar su respuesta antes de ejecutar nada.
- **FR-002**: La petición MUST mostrar al usuario la herramienta, sus argumentos validados y el efecto esperado (descripción de la herramienta y su nivel de riesgo), acotados y saneados (AC-01).
- **FR-003**: El usuario MUST poder elegir aprobar una vez, aprobar para la sesión o rechazar.
- **FR-004**: «Aprobar una vez» MUST ejecutar la llamada con exactamente los argumentos mostrados y no dejar rastro para llamadas posteriores.
- **FR-005**: «Aprobar para la sesión» MUST limitarse a **una herramienta y sus argumentos exactos** (regla 1; Q1); una llamada de esa herramienta con argumentos distintos MUST volver a pedir (regla 2, AC-02). Los permisos de sesión viven solo en memoria y terminan con la sesión.
- **FR-006**: La resolución MUST emitirse como `APPROVAL_RESOLVED` con la decisión y su origen (usuario, aprobación de sesión, falla cerrada), también cuando una aprobación de sesión evita preguntar.
- **FR-007**: Falla cerrada: sin respuesta, excepción ordinaria, resultado inválido, entrada agotada o cancelación MUST resultar en que la acción no se ejecute; una cancelación se propaga, nunca se convierte en aprobación.
- **FR-008**: Una aprobación MUST NOT anular una denegación: solo se consulta cuando la política devolvió «preguntar», y las aprobaciones de sesión no se consultan para llamadas denegadas por la política (zona protegida de HU-11-01, lo que evalúe HU-05-02).
- **FR-009**: Nunca se crea una aprobación de sesión que equivalga a permitir la herramienta entera: con argumentos exactos, una llamada sin argumentos equivale solo a otra sin argumentos.
- **FR-010**: Un rechazo MUST dejar el camino abierto a HU-05-04: el resultado de aprobación puede llevar un motivo (`ApprovalResult.reason`) y el bucle lo trata como dato opcional que otra historia podrá devolver al modelo; esta historia solo devuelve al modelo un resultado de error genérico y acotado.
- **FR-011**: Sin aprobador configurado el bucle MUST conservar el comportamiento previo (denegado con `[approval_required_unavailable]`).
- **FR-012**: Las cargas de `APPROVAL_REQUESTED` y `APPROVAL_RESOLVED` MUST NOT incluir valores de argumentos ni contenido de archivos.
- **FR-013**: La presentación y la lectura de la decisión viven en la CLI y se cablean en la raíz de composición; el núcleo no imprime ni lee entrada.
- **FR-014**: El texto de la CLI está en español y no reproduce el valor recibido en mensajes de error de validación.

### Key Entities

- **Solicitud de aprobación**: la llamada pendiente (herramienta y argumentos validados) más el detalle que se muestra (efecto, riesgo).
- **Resultado de aprobación**: ya definido por el puerto: acción (una vez, sesión, rechazar) y motivo opcional.
- **Aprobación de sesión**: pareja (herramienta, patrón de argumentos) guardada en memoria durante la sesión; sirve solo para decisiones «preguntar».
- **Patrón de argumentos**: la regla que decide si una llamada posterior está cubierta por una aprobación de sesión. Decidido (Q1, 2026-10-25): **argumentos exactos** — la misma herramienta con argumentos iguales (comparación estructural de los argumentos validados).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de las pruebas, toda acción que la política pregunta se detiene hasta que el aprobador decide, y ninguna se ejecuta sin una respuesta de aprobar (AC-01).
- **SC-002**: En el 100 % de las pruebas, una llamada fuera del patrón aprobado para la sesión vuelve a pedir, y una llamada denegada por la política sigue denegada aunque exista una aprobación de sesión que la cubriría (AC-02, FR-008).
- **SC-003**: Los cinco fallos de falla cerrada (sin respuesta, excepción, resultado inválido, entrada agotada, cancelación) terminan sin ejecutar la herramienta en el 100 % de las pruebas.
- **SC-004**: Las dos nuevas apariciones de eventos (`APPROVAL_REQUESTED` y `APPROVAL_RESOLVED`) llegan a los suscriptores en orden, antes de la ejecución, y ninguna carga contiene el valor de un argumento (centinela `VALOR-DE-PRUEBA-123`).
- **SC-005**: Las cuatro puertas de calidad y `pytest tests/architecture` terminan en exit 0; el módulo nuevo de `core/` tiene cobertura del 100 % de líneas y ramas.

## Assumptions

- El «efecto esperado» se toma de la descripción y el nivel de riesgo que declara la herramienta; no se inventa texto por herramienta (el prototipo de la ficha muestra un efecto redactado, pero ninguna herramienta lo declara hoy y los puertos no cambian).
- La opción «rechazar con motivo» del prototipo se presenta como **rechazar**; pedir y devolver el motivo escrito es HU-05-04.
- Las aprobaciones de sesión viven en memoria y se pierden al terminar la sesión; no se persisten (la persistencia/auditoría es HU-05-05).
- Una opción no válida en la terminal se vuelve a pedir hasta tres veces y luego se deniega.
- La espera del usuario no tiene tiempo límite propio; los límites de tiempo son HU-01-06.
- `/salir` o fin de entrada durante una petición se trata como entrada agotada: se deniega la acción.
- Un único aprobador por sesión; los subagentes (HU-09-01) y su indicación de quién pide quedan para su historia.
