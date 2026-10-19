# Feature Specification: HU-01-01 — Bucle agéntico básico

**Feature Branch**: `005-basic-agent-loop`  
**Created**: 2026-10-18  
**Status**: Implementado con dobles, en revisión (2026-10-19; T001–T030 completadas, T031/T032 bloqueadas por B y C). Historial previo: Borrador (2026-10-18): especificación redactada y aclarada (sesión de `/speckit-clarify` del 2026-10-18; las cinco aclaraciones resueltas, Q4 aprobada por el PO), plan generado (`plan.md`, 2026-10-18), decisiones R-07 y R-08 incorporadas (comunicadas en la solicitud de `/speckit-tasks` del 2026-10-18), `tasks.md` generado. No hay código. La historia sigue en `Pendiente` en `docs/PROGRESO.md`  
**Responsable**: A — Núcleo  
**Sprint**: Sprint 1 | **Estimación**: 5 PHU (Sp1-12: 7 h, Sp1-13: 2,5 h, Sp1-14: 4 h)  
**Prioridad**: Alta | **Requisitos**: RF-1.1, RF-1.5 | **Depende de**: HU-00-01, HU-07-01  
**Input**: Especificar el bucle agéntico básico del proyecto HARNESS v2.5: el usuario plantea una tarea y el agente ejecuta turnos de razonar, actuar y observar hasta terminarla, usando únicamente los contratos del núcleo ya existentes y dobles de prueba para las colaboraciones de otras historias.

---

## Criterios de aceptación originales (inmutables)

> Principio V de la constitución: los criterios de aceptación no se modifican, relajan ni omiten sin autorización expresa del Product Owner. Se copian literalmente de [`docs/04a-historias-fundacion.md`](../../docs/04a-historias-fundacion.md#hu-01-01) (verificados contra ese documento el 2026-10-18; coinciden con el texto de la solicitud de esta especificación).

- **AC-01 — Ejecución de tres pasos en orden.** Dado un guion de tres pasos con herramientas, cuando el bucle corre, entonces ejecuta las tres herramientas en orden y termina cuando el modelo no pide más.
- **AC-02 — Error de herramienta devuelto al modelo.** Dado una herramienta que falla, cuando el bucle recibe el error, entonces lo devuelve al modelo como resultado estructurado y continúa.

**Reglas de negocio originales** (también literales):

1. Un error de herramienta no detiene el bucle: se devuelve al modelo como resultado estructurado.
2. El bucle emite eventos y no imprime directamente.

Las secciones siguientes añaden escenarios formales, casos límite y requisitos alrededor de estos criterios; ninguna los reformula.

---

## Clarifications

### Session 2026-10-18

- **Q: ¿Qué contratos reales existen y se reutilizan?** → **A:** Se reutilizan sin modificarlos: `Role`, `ToolCall(id, name, arguments)`, `ToolResult(call_id, content, is_error)`, `TokenUsage`, `Message(role, content, tool_calls, tool_result, usage, is_external)` de [`core/entities.py`](../../src/harness_agent/core/entities.py); `Provider.complete(messages, tools) -> ProviderResponse`, `ToolDefinition` y `ProviderResponse(content, tool_calls, usage)` de [`core/interfaces/provider.py`](../../src/harness_agent/core/interfaces/provider.py); `Tool` (`name`, `description`, `schema`, `risk`, `async run(args) -> ToolResult`) y `ToolRegistry` (`register`, `get`, `list`, `validate_args`) de [`core/interfaces/tool.py`](../../src/harness_agent/core/interfaces/tool.py); `PermissionPolicy.evaluate(call) -> PermissionDecision` (`DENY`/`ASK`/`ALLOW`) de [`core/interfaces/security.py`](../../src/harness_agent/core/interfaces/security.py); `EventBus.emit(event)` y `Event`/`EventType` (17 miembros en inglés) de [`core/interfaces/event_bus.py`](../../src/harness_agent/core/interfaces/event_bus.py) y [`core/events.py`](../../src/harness_agent/core/events.py). Los contratos compartidos no se modifican sin aprobación de A, B y C.
- **Q: ¿Qué flujo describen los documentos y cuál se especifica?** → **A:** `docs/04a` define un flujo general de cinco pasos (la tarea, llamada al modelo, ejecutar herramientas, repetir, mostrar la respuesta y volver a esperar). Esta especificación lo detalla en el flujo de diez pasos de la solicitud (ver «Flujo del turno»). Son complementarios, no contradictorios. «Mostrar la respuesta final y volver a esperar al usuario» (paso 5 de `docs/04a`) corresponde a la interfaz (HU-06-01): el bucle publica el hecho y devuelve el control; no imprime ni espera entrada.
- **Q: ¿Quién valida los argumentos de una herramienta?** → **A:** El contrato real lo asigna al registro: `ToolRegistry.validate_args(name, args)` valida contra el esquema de la herramienta y lanza `ValueError` si es inválido (HU-01-02 lo implementa; `Tool` no tiene método de validación). El bucle **invoca** esa validación antes de cada ejecución y convierte el rechazo en un resultado estructurado; no reimplementa el esquema. No falta ningún método en el contrato.
- **Q: ¿Qué ocurre con «preguntar» (`ASK`) en el Sprint 1?** → **A:** `docs/04c` (HU-05-01) establece que, sin interfaz de aprobación (HU-05-03, posterior), «preguntar» se resuelve como denegar con motivo y la decisión se registra. El contrato `Approver` existe, pero su cableado no es parte de esta historia. La resolución provisional de `ASK` en la política es de C (Sp1-35, HU-05-01); el bucle no la duplica, pero es la última barrera: `ASK` nunca implica ejecución, haga lo que haga la política (ver «Clarify Q5»).
- **Q: ¿Cómo se asocia el resultado de una herramienta con su llamada?** → **A:** `Tool.run(args)` recibe solo los argumentos, no el identificador de la llamada, pero `ToolResult` exige `call_id`. Por tanto el bucle es responsable de que el resultado entregado al modelo lleve el `id` de la llamada que lo originó, incluso si la herramienta informó otro valor o ninguno útil. (Hallazgo sobre el contrato: se resuelve en el bucle, sin tocar `Tool`.)
- **Q: ¿Cuál es el estado de la asincronía?** → **A:** `Provider.complete`, `Tool.run` y `Approver.request` son `async def` en el código vigente. La decisión D-01 (SPK-02) que ratifica `asyncio` está **PENDIENTE DE APROBACIÓN** de A, B y C; esta especificación se apoya en las firmas existentes y **no** da D-01 por ratificada. Si D-01 se rechazara o cambiara, esta historia se revisaría.
- **Q: ¿Qué citar para la marca `is_external`?** → **A:** El contrato de `Message.is_external` (docstring de `entities.py`) y la User Story 3 de la spec 004. Nota: la spec 004 cita V-13, pero en `docs/01` la decisión V-13 trata de la detección de secretos; no se usa como base aquí.
**Sesión de `/speckit-clarify` (cinco aclaraciones, resueltas de forma conjunta por instrucción del Product Owner):**

- **Q: Clarify Q1 (FR-028) — ¿Se incluye en HU-01-01 un tope de iteraciones o se difiere todo a HU-01-06?** → **A:** Opción B: no hay límite interno de iteraciones ni parámetro configurable de turnos en HU-01-01, y el bucle no emite `LIMIT_REACHED`; los límites son de HU-01-06 (Sprint 2). Condiciones: las pruebas usan un proveedor simulado con guiones finitos; agotar el guion produce un fallo de prueba explícito; las pruebas llevan *timeouts*; el bucle propaga la cancelación; no se implementa nada de HU-01-06; y la ejecución desatendida con proveedores reales **no se considera segura** hasta contar con los límites de HU-01-06 o con controles externos equivalentes. *(estado: Aprobada por el PO)*
- **Q: Clarify Q2 — ¿HU-01-01 procesa todas las llamadas de una misma respuesta aunque HU-01-07 sea de Sprint 3?** → **A:** Opción A: se procesan todas las llamadas de `ProviderResponse.tool_calls`, en el orden original, de forma secuencial, validando argumentos y permisos de cada una, con un `ToolResult` por llamada; se continúa tras errores o denegaciones controladas; ninguna se descarta y no hay paralelismo. HU-01-07 sigue siendo una historia independiente (solapamiento anotado en `docs/PROGRESO.md`); esta especificación solo garantiza el mínimo secuencial. *(estado: Aprobada por el PO)*
- **Q: Clarify Q3 — ¿El bucle emite `APPROVAL_REQUESTED`/`APPROVAL_RESOLVED` cuando una llamada resulta `ASK`, dado que HU-01-05 AC-01 espera un evento de aprobación en un turno completo?** → **A:** No. En el Sprint 1 el `Approver` no está cableado y emitirlos afirmaría que se consultó a alguien cuando no fue así; `ASK` se registra mediante `PERMISSION_DECIDED`. B verifica esos eventos de HU-01-05 con un doble que los produzca; la salvedad queda anotada en `docs/PROGRESO.md`. *(estado: Derivada de contratos/decisiones existentes)*
- **Q: Clarify Q4 — ¿Qué hace el bucle si `EventBus.emit` lanza una excepción?** → **A:** El bucle no captura la excepción: la propaga y detiene la ejecución (falla cerrada). Reglas aprobadas por el PO: (1) no se ignoran los errores que escapan de `EventBus.emit`; (2) no se ejecutan nuevas herramientas después de ese error; (3) no hay reintentos automáticos; (4) si el fallo ocurre antes de ejecutar una herramienta (p. ej., al publicar `TOOL_REQUESTED` o `PERMISSION_DECIDED`), esa herramienta no se ejecuta; (5) si ocurre después de una operación con efectos (p. ej., al publicar `TOOL_FINISHED`), no se asume rollback ni se repite automáticamente la operación; (6) las excepciones del bus no se capturan indiscriminadamente para convertirlas en `ToolResult`; (7) se coordina con HU-01-05 (B) el aislamiento de fallos de suscriptores. Son situaciones distintas y no equivalentes: un fallo de suscriptor aislado por `EventBus` (HU-01-05), un fallo real propagado por `EventBus.emit`, un fallo de herramienta (`ToolResult`), un fallo del proveedor (resultado explícito, sin reintento) y la cancelación de la tarea asíncrona (se propaga). *(estado: Aprobada por el PO)*
- **Q: Clarify Q5 — ¿Quién resuelve `ASK` en el Sprint 1: la política (Sp1-35, C) o el bucle?** → **A:** Doble capa. C es dueño de la política provisional de `ASK` (Sp1-35, HU-05-01) y A no la duplica; el bucle es la última barrera: toda decisión distinta de `ALLOW` (`DENY`, `ASK`, valor inesperado o excepción de `evaluate`) significa «no se ejecuta» y produce un `ToolResult` de rechazo estructurado. `PermissionPolicy.evaluate` devuelve solo el enum (sin motivo); el contenido del rechazo lo redacta el bucle a partir de la decisión. *(estado: Derivada de contratos/decisiones existentes)*
- **Q: Aclaraciones arquitectónicas comunicadas por el PO** → **A:** Una sesión puede contener varios turnos; un turno termina cuando el proveedor deja de solicitar herramientas; el consumidor puede conservar el historial en memoria y pasarlo como contexto inicial del turno siguiente; no hay persistencia ni reanudación por identificador; el núcleo emite eventos y nunca imprime; los fallos del proveedor no activan reintentos automáticos; los errores de herramienta vuelven al modelo mediante `ToolResult`. Consecuencia: esta historia ejecuta **un turno por invocación** (ver FR-001, FR-007 y A-03).
- **Q: Decisión R-07 — ¿Qué argumentos evalúa la política y cuáles ejecuta la herramienta?** → **A:** La política evalúa los argumentos efectivos validados (copia profunda del resultado de `ToolRegistry.validate_args`, en una `ToolCall` que conserva `id` y `name`) y `Tool.run` recibe exactamente los argumentos autorizados; no hay diccionarios compartidos entre autorización y ejecución; los argumentos originales sirven solo para diagnóstico. Reemplaza la redacción previa de FR-008 y el riesgo R-07 del plan. La semántica de `validate_args` se confirma con C. *(estado: Decisión adoptada, comunicada en la solicitud de `/speckit-tasks`; ratificación formal del PO pendiente si quien la comunicó no actúa como PO)*
- **Q: Decisión R-08 — ¿Qué prevalece si `EventBus.emit(INTERRUPTED)` falla durante una cancelación?** → **A:** La cancelación: el bucle intenta publicar `INTERRUPTED`; si `emit` falla adjunta el diagnóstico (tipo y mensaje del fallo) como nota `add_note` a la cancelación, propaga la `CancelledError` original, no ejecuta más herramientas, no reintenta y no la convierte en `ToolResult`. Q4 sigue vigente para los fallos ordinarios de `emit`. *(estado: Decisión adoptada, comunicada en la solicitud de `/speckit-tasks`; ratificación formal del PO pendiente si quien la comunicó no actúa como PO)*
- **Q: Correcciones documentales tras la auditoría de `/speckit-analyze` (M1–M4) — ¿Qué se ajustó?** → **A:** (M1) el diagnóstico de R-08 se adjunta solo como nota `add_note`; `__context__` no queda con el error del bus y no se exige. (M2) la evidencia de T010 y T011 sale de pruebas mínimas de T007; ninguna tarea exige evidencia de una tarea posterior. (M3) T004 deja de ser paralelizable porque reexporta en el archivo compartido `tests/doubles/__init__.py`. (M4) la unicidad de `ToolCall.id` en todo el historial proviene de la validación canónica de HU-07-01 (`validate_tool_correlation`, D-02 §4.7), no del contrato `Provider`; los guiones deben emitir ids únicos en toda la sesión y B lo confirma en T031. *(estado: corrección documental del autor; sin cambios en AC-01 ni AC-02)*

**Correcciones de contradicciones entre la especificación inicial y los contratos/documentos:**

1. **Dueño de `ASK`**: `docs/03` (Sp1-35) lo asigna a C y la especificación inicial lo asignaba al bucle → doble capa (Q5; FR-013).
2. **Motivo de rechazo**: `PermissionPolicy.evaluate(call) -> PermissionDecision` no transporta motivo → lo redacta el bucle (FR-012, FR-013).
3. **US6-4 frente a la cancelación**: la cancelación se propaga como excepción (D-01 §6 prohíbe absorberla), de modo que no hay objeto de resultado desde el cual examinar el historial → el historial parcial queda disponible para el llamador por un mecanismo que define el plan (FR-026; US6-4).
4. **Validador canónico**: `validate_canonical_messages` vive en `adapters/converters/` y FR-032 prohíbe al núcleo importar `adapters/` → el bucle garantiza la validez canónica por construcción y ese validador se usa solo en las pruebas (FR-001, FR-021, SC-005).
5. **`APPROVAL_REQUESTED`**: HU-01-05 AC-01 espera ese evento, pero el bucle no lo emite en el Sprint 1 → B lo verifica con un doble (Q3; tabla de eventos).

---

## Flujo del turno

Flujo detallado (elaboración del flujo general de `docs/04a`):

1. **Recibir la tarea**: el llamador entrega la tarea del usuario.
2. **Construir los mensajes**: se parte del contexto inicial recibido (vacío, solo un prefijo `system` o el historial de turnos anteriores que el consumidor conservó) más el mensaje de usuario con la tarea.
3. **Llamar al proveedor**: `await provider.complete(messages, tools)`, con las herramientas del `ToolRegistry` expresadas como `ToolDefinition`.
4. **Inspeccionar la `ProviderResponse`**: texto, llamadas a herramientas, uso de tokens.
5. **Validar y comprobar permisos**: para cada llamada solicitada, en el orden recibido: existencia de la herramienta, validación de argumentos y decisión de la política.
6. **Ejecutar las herramientas permitidas**: una por vez, en orden.
7. **Producir `Message(role=TOOL)`**: un mensaje por cada llamada, con su `ToolResult` (éxito, error, denegación o rechazo).
8. **Añadir al contexto**: primero el mensaje del asistente con sus llamadas y luego, al terminar cada llamada y antes de procesar la siguiente, su mensaje `TOOL`, en el orden de las llamadas.
9. **Volver a consultar al proveedor** con el historial ampliado, una vez añadidos los mensajes `TOOL` de todas las llamadas.
10. **Terminar** cuando una `ProviderResponse` no pide herramientas (respuesta final) o cuando ocurre una de las terminaciones por fallo definidas más abajo.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un guion de tres pasos se ejecuta en orden hasta terminar (Priority: P1)

Como usuario operador, planteo una tarea y quiero que el agente encadene los turnos necesarios (por ejemplo, leer, escribir y releer un archivo) sin que yo dirija cada paso, y que se detenga cuando el modelo ya no necesita más herramientas.

**Why this priority**: Es AC-01 y la razón de ser de la historia; sin ella no existe agente (RF-1.1). Es el recorrido que el criterio de demostración del Sprint 1 exige repetible.

**Independent Test**: Con un proveedor guionizado que pide tres herramientas en tres respuestas sucesivas y una cuarta respuesta sin herramientas, un registro de herramientas con tres herramientas dobles que registran su orden de ejecución, una política que permite todo y un bus que registra eventos: se comprueba el orden exacto de ejecución, la respuesta final y la ausencia de una quinta consulta al proveedor.

**Acceptance Scenarios**:

1. **Given** un guion de tres pasos con herramientas, **When** el bucle corre, **Then** ejecuta las tres herramientas en orden y termina cuando el modelo no pide más (AC-01, literal).
2. **Given** el guion anterior, **When** el bucle termina, **Then** el proveedor fue consultado exactamente cuatro veces y la respuesta final es el texto de la cuarta respuesta.
3. **Given** el guion anterior ejecutado repetidamente con el mismo proveedor guionizado, **When** se comparan las ejecuciones, **Then** el orden de ejecución, los mensajes del historial y la secuencia de eventos son idénticos en cada una.
4. **Given** una respuesta del proveedor con texto y sin llamadas a herramientas desde la primera consulta, **When** el bucle corre, **Then** termina tras una sola consulta con ese texto como respuesta final y sin ejecutar herramientas.
5. **Given** una respuesta del proveedor con varias llamadas a herramientas en un solo turno, **When** el bucle las procesa, **Then** las ejecuta una por vez en el orden solicitado y añade un mensaje `TOOL` por llamada en ese mismo orden.

---

### User Story 2 - Un error de herramienta vuelve al modelo y el bucle continúa (Priority: P1)

Como usuario operador, quiero que si una herramienta falla el agente no se caiga ni se detenga: el modelo debe enterarse del fallo como un resultado estructurado y decidir cómo seguir.

**Why this priority**: Es AC-02 y la regla de negocio 1; sin ella el primer error de un archivo inexistente aborta la tarea completa (RF-1.5).

**Independent Test**: Con un proveedor guionizado que pide una herramienta que falla y, en la respuesta siguiente, termina con texto: se comprueba que el siguiente mensaje enviado al proveedor contiene un resultado `is_error=True` con el `id` de la llamada y que el bucle terminó con normalidad.

**Acceptance Scenarios**:

1. **Given** una herramienta que falla, **When** el bucle recibe el error, **Then** lo devuelve al modelo como resultado estructurado y continúa (AC-02, literal).
2. **Given** una herramienta que devuelve `ToolResult(is_error=True)`, **When** el bucle lo procesa, **Then** el modelo recibe un mensaje `TOOL` cuyo resultado conserva `is_error=True`, el contenido del error y el `id` de la llamada original, y se realiza la siguiente consulta al proveedor.
3. **Given** una herramienta que lanza una excepción en lugar de devolver un resultado, **When** el bucle la captura, **Then** el modelo recibe un resultado con `is_error=True` que describe el fallo y el `id` de la llamada, y el bucle continúa (la excepción no escapa del bucle).
4. **Given** una llamada a una herramienta que no existe en el registro, **When** el bucle la procesa, **Then** no se ejecuta nada y el modelo recibe un resultado de error que nombra la herramienta desconocida; el bucle continúa.
5. **Given** tres llamadas en un turno donde la segunda falla, **When** el bucle las procesa, **Then** la primera y la tercera se ejecutan igualmente y el modelo recibe tres resultados en orden, el segundo con `is_error=True`.

---

### User Story 3 - Nada se ejecuta sin validación y sin decisión de permisos (Priority: P1)

Como usuario operador, quiero que ninguna acción del agente se ejecute si sus argumentos no son válidos o si la política no la autoriza, y que el modelo sepa por qué no se ejecutó.

**Why this priority**: Es la barrera de seguridad del bucle (Principios de falla cerrada; HU-05-01 y HU-01-02 dependen de que el bucle las respete). Un bucle que ejecuta primero y pregunta después invalida todo el control.

**Independent Test**: Con herramientas dobles que cuentan sus ejecuciones y una política doble que devuelve `ALLOW`, `DENY` o `ASK` según la herramienta, junto con un registro doble que rechaza argumentos: se comprueba que el contador de ejecuciones solo avanza para llamadas válidas y permitidas.

**Acceptance Scenarios**:

1. **Given** una llamada con argumentos que el registro rechaza, **When** el bucle la procesa, **Then** la herramienta no se ejecuta, la política no se consulta y el modelo recibe un resultado de error con el motivo del rechazo (el campo inválido tal como lo informe el registro).
2. **Given** una llamada válida cuya decisión de política es `DENY`, **When** el bucle la procesa, **Then** la herramienta no se ejecuta y el modelo recibe un resultado de error que indica que fue denegada, la herramienta afectada y el motivo redactado por el bucle a partir de la decisión.
3. **Given** una llamada válida cuya decisión de política es `ASK` y no existe aprobación interactiva en el Sprint 1, **When** el bucle la procesa, **Then** la herramienta no se ejecuta, no se publican eventos de aprobación y el modelo recibe un resultado de error que indica que se requería aprobación y se resolvió como denegación, con el motivo.
4. **Given** una llamada válida cuya decisión es `ALLOW`, **When** el bucle la procesa, **Then** la herramienta se ejecuta exactamente una vez.
5. **Given** una política que lanza una excepción al evaluar, **When** el bucle procesa la llamada, **Then** se trata como denegación (falla cerrada): la herramienta no se ejecuta, el modelo recibe un resultado de error y el bucle continúa.
6. **Given** cualquier decisión distinta de `ALLOW` (incluido un valor inesperado), **When** el bucle termina de procesar la llamada, **Then** no existe ningún camino en el que la herramienta se haya ejecutado.
7. **Given** un registro cuya validación lanza una excepción distinta de `ValueError`, **When** el bucle procesa la llamada, **Then** se trata como rechazo de validación (falla cerrada): la herramienta no se ejecuta y el modelo recibe un resultado de error.
8. **Given** un registro cuya validación devuelve argumentos efectivos distintos de los emitidos por el modelo (por ejemplo, normalizados), **When** el bucle evalúa la política y ejecuta la herramienta, **Then** la política recibe una llamada con el mismo `id` y `name` pero con los argumentos efectivos, la herramienta recibe exactamente esos argumentos autorizados, y ni una mutación posterior de los argumentos originales ni de lo recibido por la política altera lo que se ejecuta (R-07).

---

### User Story 4 - Cada hecho relevante es un evento y el núcleo nunca imprime (Priority: P2)

Como equipo de desarrollo, queremos que el bucle publique cada hecho relevante en el bus de eventos y no escriba nada en la consola, para que la CLI de HU-06-01 (y una interfaz web futura) se conecte como suscriptor sin tocar el bucle.

**Why this priority**: Es la regla de negocio 2 y la base de RF-1.8; no bloquea el comportamiento del bucle, pero sí su integración con la interfaz y la persistencia.

**Independent Test**: Con un bus doble que registra los eventos y la salida estándar y de error capturadas durante una ejecución completa: se comprueba la secuencia de eventos esperada y que no hubo ninguna escritura en consola.

**Acceptance Scenarios**:

1. **Given** una ejecución completa con herramientas, **When** el bucle corre, **Then** el bus recibió los eventos de la sección «Eventos publicados» en el orden de los hechos y la salida estándar y de error del proceso permanecieron vacías.
2. **Given** una llamada procesada, **When** se examinan sus eventos, **Then** aparecen en este orden relativo: solicitud de la herramienta, decisión de permiso (si la llamada llegó a la política) y fin de la herramienta.
3. **Given** el bucle sin ningún suscriptor registrado en el bus, **When** corre, **Then** su comportamiento y su resultado no cambian.
4. **Given** un bus cuyo `emit` lanza una excepción al publicar `TOOL_REQUESTED` o `PERMISSION_DECIDED`, **When** el bucle procesa una llamada, **Then** la excepción no se silencia, la herramienta de esa llamada no se ejecuta y no se ejecuta ninguna herramienta posterior (falla cerrada; decisión aprobada por el PO, ver «Clarify Q4»).
5. **Given** un bus cuyo `emit` lanza una excepción al publicar `TOOL_FINISHED` de una llamada ya ejecutada, **When** el bucle la procesa, **Then** la excepción se propaga, el resultado de esa llamada ya consta en el historial del llamador, la operación no se repite ni se asume su rollback y no se procesan más llamadas (Q4, reglas 2, 3 y 5).

---

### User Story 5 - El historial es coherente entre iteraciones y las dependencias ausentes fallan cerrado (Priority: P2)

Como desarrollador del núcleo, quiero que el historial que el bucle construye sea siempre una secuencia canónica válida y que un colaborador ausente impida arrancar, para que el mismo historial pueda enviarse a cualquier proveedor y para que una mala configuración nunca se traduzca en ejecuciones sin control.

**Why this priority**: Evita corrupción silenciosa del contexto (HU-07-01) y protege el principio de falla cerrada; es importante pero no cambia el recorrido feliz.

**Independent Test**: Tras cada ejecución de las historias anteriores se valida el historial con las reglas canónicas existentes (prefijo `system`, roles y correlación de llamadas) y se intenta construir el bucle quitando un colaborador a la vez.

**Acceptance Scenarios**:

1. **Given** cualquier ejecución que termine con normalidad, **When** se examina el historial final, **Then** es una secuencia canónica válida: `system` solo como prefijo, `tool_calls` solo en mensajes `assistant`, `tool_result` solo en mensajes `tool`, y cada resultado está después de su llamada con el mismo identificador.
2. **Given** un mensaje del asistente con varias llamadas, **When** se añaden sus resultados, **Then** cada llamada recibe exactamente un mensaje `TOOL` con su `call_id`, en el orden de las llamadas.
3. **Given** el historial de una ejecución, **When** se compara entre iteraciones, **Then** cada iteración solo añade mensajes al final; ningún mensaje previo se modifica, reordena ni elimina.
4. **Given** un contenido producido por la ejecución de una herramienta, **When** se añade al historial, **Then** el mensaje `TOOL` correspondiente lleva `is_external=True`.
5. **Given** que falta el proveedor, el registro de herramientas, la política de permisos o el bus de eventos, **When** se intenta ejecutar el bucle, **Then** falla con un error explícito que nombra el colaborador ausente antes de consultar al proveedor y antes de ejecutar nada.
6. **Given** un registro con herramientas pero sin política de permisos, **When** se intenta ejecutar, **Then** no se ejecuta ninguna herramienta (no existe un valor por defecto que permita).
7. **Given** un resultado redactado por el propio bucle (herramienta desconocida, argumentos inválidos, `DENY`, `ASK`), **When** se añade al historial, **Then** el mensaje `TOOL` correspondiente lleva `is_external=False`.
8. **Given** un historial previo de turnos anteriores entregado como contexto inicial, **When** el bucle corre un nuevo turno, **Then** el mensaje de usuario de la tarea se añade al final, los mensajes previos permanecen intactos y el turno termina cuando el proveedor deja de pedir herramientas.

---

### User Story 6 - Un fallo del proveedor o una cancelación terminan de forma explícita (Priority: P2)

Como usuario operador, quiero que si el proveedor falla o si yo interrumpo la ejecución, el bucle termine de forma explícita y deje constancia, sin reintentos silenciosos ni historial corrupto.

**Why this priority**: Cubre el manejo básico de fallos sin ampliar el alcance: los reintentos, la conmutación y la interrupción completa con Ctrl+C pertenecen a historias posteriores.

**Independent Test**: Con un proveedor doble que lanza una excepción en la segunda consulta, y con una cancelación de la tarea asíncrona durante la ejecución de una herramienta doble que espera: se comprueba el resultado, el evento y el estado del historial.

**Acceptance Scenarios**:

1. **Given** un proveedor que falla durante una consulta, **When** el bucle recibe el error, **Then** no reintenta ni cambia de proveedor, publica un evento de error del proveedor y termina con un resultado de fallo explícito que conserva el historial hasta ese punto.
2. **Given** una respuesta del proveedor con identificadores de llamada duplicados o vacíos, **When** el bucle la inspecciona, **Then** no ejecuta ninguna de sus llamadas, no añade esa respuesta al historial y termina con un resultado de fallo explícito.
3. **Given** que la ejecución se cancela mientras una herramienta corre, **When** llega la cancelación, **Then** el bucle publica el evento de interrupción exactamente una vez, no inicia nuevas consultas ni nuevas herramientas y propaga la cancelación al llamador.
4. **Given** la interrupción anterior, **When** el llamador accede al historial parcial (por el mecanismo que define el plan, ya que la cancelación se propaga como excepción y no como resultado), **Then** solo contiene hechos ocurridos (sin resultados inventados) y sigue siendo una secuencia sin mensajes duplicados ni fuera de orden; puede terminar en llamadas del asistente sin resultado y entonces no es válido para reenviarlo a un proveedor hasta que HU-06-03 defina el resultado «interrumpido».
5. **Given** que la ejecución se cancela mientras `Provider.complete` espera respuesta, **When** llega la cancelación, **Then** se aplica el mismo comportamiento: un único evento de interrupción, ninguna consulta ni herramienta posterior y propagación al llamador.
6. **Given** que la ejecución se cancela y la publicación del evento de interrupción también falla, **When** llega la cancelación, **Then** el bucle intenta publicarlo una vez, adjunta el diagnóstico del fallo de publicación como nota (`add_note`) a la cancelación, propaga la `CancelledError` original (no un error del bus), no ejecuta más herramientas, no reintenta y no genera ningún `ToolResult`; en cambio, un fallo de `emit` fuera de una cancelación se propaga como error del bus (Q4, R-08).

---

### Edge Cases

- **Herramienta que lanza una excepción**: se captura y se devuelve como resultado `is_error=True`; nunca escapa del bucle (US2-3). La cancelación asíncrona no cuenta como excepción de herramienta: se propaga (US6-3).
- **Herramienta desconocida**: resultado de error que nombra la herramienta; no se consulta política ni se ejecuta (US2-4).
- **Argumentos inválidos**: resultado de error con el motivo informado por el registro; no se consulta política (US3-1).
- **`DENY`**: no se ejecuta; resultado de error con motivo (US3-2).
- **`ASK`**: en el Sprint 1 se resuelve como denegación con motivo; nunca se ejecuta (US3-3). No se publican eventos de solicitud o resolución de aprobación porque no hay aprobación interactiva.
- **Error del proveedor**: sin reintento ni conmutación; fallo explícito y evento (US6-1).
- **Respuesta vacía del proveedor** (sin texto y sin llamadas): se trata como fin normal con respuesta final vacía; el bucle no inventa contenido ni reintenta.
- **Llamadas idénticas repetidas** (mismo nombre y argumentos, identificadores distintos): cada una se procesa y ejecuta por separado; el bucle no las deduplica. La detección de llamadas repetidas es de HU-01-08 (Sprint 3) y el límite de turnos de HU-01-06 (Sprint 2); en esta historia no hay ningún tope (FR-028), por lo que un ciclo sin fin solo se detecta en las pruebas con guiones finitos y *timeouts*.
- **Muchas llamadas en una sola respuesta**: se procesan todas, secuencialmente y en el orden recibido, sin descartar ninguna; la ejecución en paralelo está fuera de alcance y HU-01-07 conserva su alcance propio (Q2).
- **Agotamiento del guion del proveedor simulado en una prueba**: es un fallo de prueba explícito, no una terminación normal del bucle (FR-028).
- **Resultado de herramienta muy grande**: el recorte de salidas largas pertenece a HU-02-02; el bucle no recorta ni trunca.
- **Cancelación en medio de la ejecución de una herramienta o de una consulta al proveedor**: se propaga tras publicar el evento de interrupción; la limpieza de procesos hijos es de la herramienta y de HU-01-04; los resultados «interrumpido» que ve el modelo (V-11) y la captura de Ctrl+C son de HU-06-03 (US6-3, US6-4).
- **Colaborador ausente**: error explícito antes de cualquier consulta o ejecución (US5-5, US5-6).
- **Identificadores de llamada duplicados o vacíos en una respuesta**: respuesta inválida; ninguna llamada se ejecuta (US6-2).
- **Herramienta que informa un `call_id` distinto o vacío en su `ToolResult`**: el mensaje entregado al modelo lleva el `id` de la llamada original (FR-016).
- **Registro sin herramientas**: se consulta al proveedor sin herramientas disponibles; si aun así pide una, es una herramienta desconocida (US2-4).
- **Mensaje de usuario con tarea vacía**: el bucle no la rechaza ni la interpreta; la validación de entrada es del llamador (supuesto A-04).

---

## Requirements *(mandatory)*

### Functional Requirements

**Ciclo principal (RF-1.1)**

- **FR-001**: El bucle DEBE aceptar una tarea del usuario junto con un contexto inicial opcional y ejecutar un turno hasta que termine por una de las condiciones de FR-004 o FR-005. El contexto inicial es una secuencia de mensajes que el llamador entrega ya canónicamente válida (`system` solo como prefijo contiguo; en un turno posterior, además, los mensajes de turnos anteriores que el consumidor conservó en memoria). El bucle añade el mensaje de usuario con la tarea al final y garantiza la validez canónica de lo que él mismo añade; no importa el validador canónico de `adapters/` (FR-032), que se usa solo en las pruebas. Si el contexto entregado fuera inválido, la verificación en el límite del proveedor lo rechaza y el bucle lo trata como fallo del proveedor (FR-023). *(Si el plan decide añadir una comprobación estructural mínima del contexto dentro del núcleo, se registra como decisión del plan, sin importar `adapters/`.)*
- **FR-002**: En cada consulta el bucle DEBE usar únicamente `Provider.complete(messages, tools)`, pasando una **copia profunda** del historial hasta ese punto (de modo que ni el proveedor ni un doble de pruebas puedan alterar el historial del bucle, incluidos los argumentos anidados de llamadas previas; las llamadas de la respuesta del proveedor también se copian antes de registrarse) y construyendo las herramientas **antes** de consultar al proveedor, de modo que un fallo del registro se propaga como fallo estructural y no se clasifica como fallo del proveedor y las herramientas del `ToolRegistry`, recalculadas en cada consulta desde `ToolRegistry.list()` y expresadas como `ToolDefinition` (con `parameters` tomado de `Tool.schema`); no DEBE depender de ningún proveedor concreto.
- **FR-003**: Cuando una `ProviderResponse` pide herramientas, el bucle DEBE añadir un mensaje `ASSISTANT` con el texto, las llamadas (`tool_calls`) y el uso de tokens reportado, procesar cada llamada **completa y en secuencia** (publicar `TOOL_REQUESTED` justo antes de procesarla, validar, decidir, ejecutar, publicar `TOOL_FINISHED`) y añadir su mensaje `TOOL` al historial en cuanto termine, antes de procesar la siguiente; solo después de la última vuelve a consultar al proveedor. Se procesan **todas** las llamadas de la respuesta, ninguna se descarta y se continúa tras errores o denegaciones controladas.
- **FR-004**: **Condición de parada normal**: cuando una `ProviderResponse` no contiene llamadas a herramientas, el bucle DEBE añadir su texto como mensaje `ASSISTANT`, terminar el turno y entregar esa respuesta final al llamador, sin una consulta adicional. La presencia de `tool_calls` prevalece sobre el texto: una respuesta con texto y llamadas a la vez **no** es final; su texto se publica (`ASSISTANT_MESSAGE`) y se conserva en el mensaje `ASSISTANT` que lleva las llamadas.
- **FR-005**: **Terminaciones por fallo**: el bucle DEBE terminar de forma explícita en estos casos: fallo del proveedor (FR-023), respuesta inválida del proveedor (FR-024) y cancelación (FR-026). No existe terminación por tope de iteraciones (FR-028). Ninguna terminación por fallo DEBE presentarse como una finalización normal.
- **FR-006**: El bucle DEBE devolver al llamador un resultado de la ejecución que distinga, como mínimo, finalización normal (con la respuesta final) y cada terminación por fallo (con su motivo), junto con el historial resultante. La forma concreta de ese resultado se define en la fase de plan.
- **FR-007**: El bucle DEBE ejecutar un turno (una tarea, hasta que el proveedor deja de pedir herramientas) por invocación y devolver el control al llamador; no imprime la respuesta ni espera nueva entrada del usuario (eso corresponde a la interfaz, HU-06-01). Una sesión puede contener varios turnos: el consumidor conserva el historial del resultado en memoria y lo entrega como contexto inicial del turno siguiente; no hay persistencia ni reanudación por identificador.

**Validación y permisos (falla cerrada)**

- **FR-008**: Para cada llamada solicitada, en el orden recibido, el bucle DEBE aplicar esta secuencia y detenerse en el primer paso que no se supere: (a) la herramienta existe en el `ToolRegistry`; (b) los argumentos superan `ToolRegistry.validate_args`; (c) la política decide `ALLOW`; (d) se ejecuta. **Decisión R-07** *(decisión adoptada, comunicada en la solicitud de `/speckit-tasks` del 2026-10-18; ratificación formal del PO pendiente si quien la comunicó no actúa como PO)*: la política evalúa los **argumentos efectivos validados** y la herramienta ejecuta **exactamente** los argumentos autorizados. Tras `validate_args` el bucle toma una copia profunda de su resultado (argumentos efectivos), construye una `ToolCall` de evaluación que conserva `id` y `name` del original y lleva esos argumentos efectivos, evalúa la política sobre ella y, solo con `ALLOW`, ejecuta `Tool.run` con esos mismos argumentos autorizados. Los argumentos no cambian entre la autorización y la ejecución (ni la política ni la herramienta reciben diccionarios compartidos con el bucle o entre sí), y los argumentos originales emitidos por el modelo se conservan únicamente para diagnóstico y para el mensaje `ASSISTANT` del historial, nunca como sustituto de los autorizados. La semántica exacta de `validate_args` (diccionario nuevo con los argumentos normalizados, sin mutar la entrada) se confirma con C; la firma existente no se modifica.
- **FR-009**: El bucle NO DEBE ejecutar jamás una herramienta cuyos argumentos no hayan superado la validación del registro ni cuya decisión de política no haya sido `ALLOW`; no existe ningún camino alterno ni valor por defecto que ejecute sin ambas condiciones.
- **FR-010**: Una herramienta desconocida DEBE producir un resultado de error estructurado que nombra la herramienta; no se consulta la política ni se ejecuta nada.
- **FR-011**: Un rechazo de validación (el `ValueError` de `validate_args` o cualquier otra excepción que lance, por falla cerrada) DEBE producir un resultado de error estructurado que incluye el motivo informado por el registro (incluido el campo inválido cuando el registro lo indique); la herramienta no se ejecuta y la política no se consulta.
- **FR-012**: Una decisión `DENY` DEBE producir un resultado de error estructurado que indica la denegación, la herramienta afectada y el motivo; la herramienta no se ejecuta. `PermissionPolicy.evaluate` devuelve solo el `PermissionDecision`, sin motivo: el contenido del rechazo lo redacta el bucle a partir de la decisión.
- **FR-013**: En el Sprint 1 una decisión `ASK` DEBE resolverse como denegación con motivo, produciendo un resultado de error estructurado que indica que se requería aprobación y no estaba disponible; la herramienta no se ejecuta y no se publican `APPROVAL_REQUESTED` ni `APPROVAL_RESOLVED`. La política provisional de `ASK` es de C (Sp1-35, HU-05-01) y el bucle no la duplica; el bucle es la última barrera: toda decisión distinta de `ALLOW` se trata como «no se ejecuta», sin depender de lo que la política haga.
- **FR-014**: Una excepción lanzada por la política al evaluar, o un valor de retorno que no sea un `PermissionDecision`, DEBE tratarse como denegación (falla cerrada) con resultado de error estructurado; la herramienta no se ejecuta.
- **FR-015**: El bucle DEBE ejecutar las herramientas permitidas de forma secuencial, una a la vez, en el orden en que el modelo las solicitó; la ejecución en paralelo queda fuera de alcance.

**Resultados y errores de herramienta (RF-1.5)**

- **FR-016**: Todo resultado entregado al modelo DEBE ser un `ToolResult` cuyo `call_id` es el `id` de la llamada que lo originó, con independencia del `call_id` que la herramienta informe.
- **FR-017**: Un resultado `ToolResult(is_error=True)` devuelto por una herramienta DEBE entregarse al modelo conservando `is_error=True` y su contenido; el bucle continúa con la siguiente llamada y con la siguiente consulta al proveedor (AC-02, regla 1).
- **FR-018**: Una excepción lanzada por `Tool.run` (distinta de la cancelación asíncrona) DEBE capturarse y entregarse al modelo como `ToolResult(is_error=True)` con una descripción del fallo; la excepción no escapa del bucle. Si `Tool.run` devuelve algo que no es un `ToolResult`, se trata también como fallo de la herramienta (resultado de error).
- **FR-019**: Los resultados generados por el propio bucle (herramienta desconocida, argumentos inválidos, denegación, `ASK` resuelto como denegación, fallo de la herramienta) DEBEN llevar `is_error=True` y un contenido que permita al modelo entender qué ocurrió y por qué, sin exponer detalles internos del proceso. El contenido DEBE permitir identificar la categoría del fallo: herramienta desconocida, argumentos inválidos, denegada, aprobación requerida no disponible, excepción de la herramienta (nombre de la clase y mensaje, sin traza) o error informado por la herramienta.

**Historial (contrato con HU-07-01)**

- **FR-020**: El historial de una ejecución DEBE ser solo de añadido: cada iteración agrega mensajes al final y no modifica, reordena ni elimina los anteriores.
- **FR-021**: Tras añadir un mensaje `ASSISTANT` con llamadas, el bucle DEBE añadir un mensaje `TOOL` por cada llamada, en el mismo orden, cada uno con su `ToolResult` y con `Message.content` igual a `tool_result.content` (los convertidores usan `tool_result.content` y descartan `Message.content`; igualarlos evita la divergencia D9 de D-02); el historial en cada punto de consulta al proveedor DEBE ser una secuencia canónica válida según las reglas existentes (`system` solo como prefijo contiguo, `tool_calls` solo en `assistant`, `tool_result` solo en `tool`, correlación sin identificadores duplicados o vacíos).
- **FR-022**: Los mensajes `TOOL` cuyo contenido se origina en la ejecución de una herramienta (éxito, error informado por la herramienta o excepción de la herramienta) DEBEN marcarse con `is_external=True`; los mensajes `TOOL` con resultados redactados por el propio bucle antes de ejecutar (herramienta desconocida, argumentos inválidos, `DENY`, `ASK`), el mensaje de usuario y los del asistente no se marcan como externos. *(Supuesto A-05; la validación canónica y los convertidores no dependen de esta marca.)*

**Fallos y dependencias**

- **FR-023**: Si `Provider.complete` lanza una excepción (distinta de la cancelación), el bucle NO DEBE reintentar ni conmutar de proveedor; DEBE publicar un evento de error del proveedor y terminar con un resultado de fallo explícito que conserva el historial hasta ese punto.
- **FR-024**: Si una `ProviderResponse` contiene llamadas con identificadores vacíos o repetidos (entre sí dentro de la respuesta, o respecto de llamadas ya presentes en el historial), el bucle DEBE rechazarla entera: no ejecuta ninguna de sus llamadas, no la añade al historial, publica un evento de error del proveedor y termina con un resultado de fallo explícito. La unicidad de `ToolCall.id` a lo largo de todo el historial no la declara el contrato `Provider`: proviene de la validación canónica de HU-07-01 (`validate_tool_correlation`, D-02 §4.7), que ambos convertidores aplican a toda ventana que se envía al proveedor y rechaza ids vacíos o duplicados; el bucle la comprueba para no ejecutar ni añadir una respuesta que dejaría el historial inenviable. Los guiones de prueba (y el `FakeProvider` de B) deben emitir ids no vacíos y únicos en toda la sesión. El uso de `PROVIDER_ERROR` para una respuesta inválida es una convención de esta historia: el catálogo de eventos no tiene un tipo específico.
- **FR-025**: Si falta alguno de los colaboradores obligatorios (proveedor, registro de herramientas, política de permisos, bus de eventos), el bucle DEBE fallar con un error explícito que nombra al ausente, antes de consultar al proveedor o ejecutar nada; ante la ausencia de la política NO DEBE asumir `ALLOW`.
- **FR-026**: Si la ejecución se cancela (cancelación asíncrona), incluso durante `Provider.complete` o durante una herramienta, el bucle DEBE publicar el evento de interrupción una sola vez, no iniciar nuevas consultas ni herramientas, dejar el historial sin mensajes duplicados ni fuera de orden y propagar la cancelación al llamador sin absorberla (D-01 §6). **Decisión R-08** *(decisión adoptada, comunicada en la solicitud de `/speckit-tasks` del 2026-10-18; ratificación formal del PO pendiente si quien la comunicó no actúa como PO)*: la cancelación tiene prioridad sobre un fallo al publicar el evento de interrupción: el bucle intenta publicarlo; si `emit` falla, conserva el diagnóstico del fallo (nota adjunta a la cancelación con `add_note`, con el tipo y el mensaje del fallo del bus; no se exige `__context__`) y propaga la `CancelledError` original, sin ejecutar más herramientas, sin reintentar y sin convertirla en `ToolResult`. Un fallo ordinario de `emit` (fuera de una cancelación) sigue la regla de Q4: se propaga y detiene el bucle. Como la cancelación se propaga como excepción y no como resultado, el historial parcial DEBE seguir disponible para el llamador; el mecanismo de entrega se define en el plan. El bucle no fabrica resultados para llamadas no ejecutadas: si la cancelación llega tras añadir un mensaje `ASSISTANT` con llamadas y antes de sus resultados, el historial puede terminar en llamadas sin resultado y NO es válido para reenviarlo a un proveedor hasta que HU-06-03 defina el resultado «interrumpido» (V-11). FR-026 es la base del Sprint 1 y HU-06-03 puede refinarla.
- **FR-027**: Las firmas asíncronas existentes (`Provider.complete`, `Tool.run`) se consumen tal como están; la ratificación de D-01 sigue **pendiente de aprobación** y esta especificación no la presupone.
- **FR-028**: **Sin tope de iteraciones en esta historia** (decisión del PO, «Clarify Q1»): el bucle NO DEBE implementar un límite interno de iteraciones ni un parámetro configurable de turnos, y NO DEBE emitir `LIMIT_REACHED`; los límites son de HU-01-06 (Sprint 2). Las pruebas DEBEN usar un proveedor simulado con guiones finitos, el agotamiento del guion DEBE producir un fallo de prueba explícito y toda prueba DEBE llevar un *timeout* que detecte un bucle sin fin. **Advertencia de seguridad operativa**: la ausencia de límite interno no autoriza la ejecución desatendida con proveedores reales; esa ejecución no se considera segura hasta contar con los límites de HU-01-06 o con controles externos equivalentes.

**Eventos y silencio del núcleo (regla 2, RF-1.8)**

- **FR-029**: El bucle DEBE publicar cada hecho relevante exclusivamente mediante `EventBus.emit`, usando solo miembros existentes de `EventType`, según la tabla de «Eventos publicados».
- **FR-030**: El bucle NO DEBE escribir en la salida estándar ni en la de error, ni depender de la terminal, en ningún camino (éxito, error, denegación o cancelación).
- **FR-031**: El comportamiento y el resultado del bucle NO DEBEN depender de que existan suscriptores en el bus. El bucle NO DEBE capturar ni silenciar una excepción lanzada por `EventBus.emit`: se propaga (falla cerrada) y detiene la ejecución: tras un fallo de `emit` no se ejecutan más herramientas; si el fallo ocurre al publicar `TOOL_REQUESTED` o `PERMISSION_DECIDED`, la herramienta de esa llamada no se ejecuta; si ocurre después de una operación con efectos, no se asume rollback ni se repite la operación; no hay reintentos, y la excepción del bus no se convierte en un `ToolResult`. El aislamiento de fallos de los suscriptores es responsabilidad de HU-01-05 (B). *(Decisión aprobada por el PO, «Clarify Q4».)*

**Aislamiento hexagonal**

- **FR-032**: El código del bucle DEBE residir en el núcleo y depender únicamente de la biblioteca estándar y de los contratos de `core/`; NO DEBE importar SDKs de proveedores (LiteLLM, OpenAI, Anthropic, etc.) ni módulos de `adapters/` ni de `cli/`.
- **FR-033**: El bucle DEBE reutilizar los contratos existentes sin modificarlos ni crear versiones paralelas de `Message`, `ToolCall`, `ToolResult`, `Provider`, `Tool`, `ToolRegistry`, `PermissionPolicy` o `EventBus`.
- **FR-034**: Las colaboraciones de otras historias (proveedor guionizado, registro de herramientas, bus, política de permisos) DEBEN poder sustituirse por dobles de prueba; la verificación de esta historia no DEBE exigir red, cuentas comerciales ni credenciales.

### Eventos publicados

Solo se usan miembros existentes de `EventType`. El contenido detallado de cada `payload` se define en el plan; como mínimo identifica el hecho (por ejemplo, el `id` y el nombre de la llamada) sin incluir información sensible.

| Momento | `EventType` | Cuándo |
|---|---|---|
| Se recibe la tarea | `USER_MESSAGE` | Una vez por tarea, antes de la primera consulta |
| El proveedor responde con texto | `ASSISTANT_MESSAGE` | Por cada respuesta con contenido textual, incluida la final |
| Se acepta una llamada para procesarla | `TOOL_REQUESTED` | Una vez por llamada, justo antes de procesarla (no por lote), en el orden solicitado y antes de validar |
| La política decide | `PERMISSION_DECIDED` | Por cada llamada que llega a la política; registra `DENY`, `ASK` (con su resolución como denegación) o `ALLOW` |
| Termina el procesamiento de una llamada | `TOOL_FINISHED` | Por cada llamada, también si fue rechazada, denegada, desconocida o fallida; indica `is_error` |
| Falla el proveedor o su respuesta es inválida | `PROVIDER_ERROR` | Una vez por fallo |
| Cancelación | `INTERRUPTED` | Una vez, antes de propagar la cancelación |

`PROVIDER_ERROR` también cubre, por convención de esta historia, la respuesta inválida del proveedor (FR-024).

No publica este bucle: `LIMIT_REACHED` (sin tope de iteraciones; HU-01-06, FR-028), `APPROVAL_REQUESTED` y `APPROVAL_RESOLVED` (no hay aprobación interactiva en el Sprint 1; HU-05-03; B verifica esos eventos de HU-01-05 con un doble), `CONTEXT_COMPACTED` (compactación fuera de alcance), `PROVIDER_SWITCHED` (conmutación fuera de alcance), `SESSION_STARTED` (sesiones, HU-03-xx) ni los eventos de subagentes y criterios (historias posteriores).

### Key Entities *(solo contratos existentes)*

- **Message / Role**: unidad del historial; el bucle usa `USER`, `ASSISTANT` y `TOOL` (y `SYSTEM` solo como prefijo recibido).
- **ToolCall**: solicitud del modelo (`id`, `name`, `arguments`), tal como la entrega `ProviderResponse`.
- **ToolResult**: resultado de una llamada (`call_id`, `content`, `is_error`); el estructurado que el modelo recibe en éxito, error, denegación o rechazo.
- **TokenUsage**: consumo reportado por el proveedor, conservado en el mensaje del asistente.
- **ProviderResponse / ToolDefinition / Provider**: contrato de consulta al modelo.
- **Tool / ToolRegistry / RiskLevel**: herramienta registrable y su catálogo con validación de argumentos.
- **PermissionPolicy / PermissionDecision**: decisión `DENY`/`ASK`/`ALLOW` para una llamada.
- **Event / EventType / EventBus**: canal único de salida de hechos del núcleo.
- **Resultado de la ejecución** (concepto, no entidad nueva fijada en esta especificación): respuesta final o motivo de terminación más historial resultante; su forma se decide en el plan (FR-006).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de al menos 20 ejecuciones repetidas del guion de tres pasos con herramientas, las tres herramientas se ejecutan exactamente una vez cada una y en el orden del guion, y la ejecución termina con la respuesta final tras la consulta sin herramientas (AC-01).
- **SC-002**: En todos los escenarios de validación y permisos (válido y permitido, argumentos inválidos, herramienta desconocida, `DENY`, `ASK`, política que falla), el número de ejecuciones de herramientas es igual al número de llamadas válidas con decisión `ALLOW`; 0 ejecuciones sin validación y decisión previas.
- **SC-003**: El 100 % de los fallos de herramienta (resultado de error, excepción, desconocida, argumentos inválidos, denegada, `ASK`) llega al modelo como un resultado estructurado con `is_error=True` y el `id` de la llamada original, y el bucle realiza la siguiente consulta al proveedor (AC-02).
- **SC-004**: En todos los escenarios, incluidos los de error y cancelación, la salida estándar y la de error capturadas durante la ejecución del núcleo están vacías (0 caracteres).
- **SC-005**: En el 100 % de las ejecuciones y en cada punto de consulta al proveedor, el historial supera la validación canónica existente y puede convertirse con los dos convertidores de referencia (OpenAI y Anthropic) sin `ConversionError`.
- **SC-006**: En los escenarios con eventos, la secuencia observada en el bus coincide exactamente con la secuencia esperada de la tabla «Eventos publicados» en el 100 % de los casos, y ninguna ejecución publica un `EventType` fuera de esa tabla.
- **SC-007**: Una auditoría de importaciones confirma 0 importaciones de SDKs de proveedores, de `adapters/` y de `cli/` en el código del bucle, y la prueba de fronteras existente sigue pasando.
- **SC-008**: Ante la ausencia de cada colaborador obligatorio (4 casos), el 100 % termina con un error explícito que lo nombra, con 0 consultas al proveedor y 0 ejecuciones de herramientas.
- **SC-009**: Ante un fallo del proveedor, una respuesta inválida o una cancelación, el 100 % termina con un resultado o propagación explícitos, exactamente un evento del tipo correspondiente, 0 reintentos y 0 consultas o ejecuciones posteriores.
- **SC-010**: La suite de pruebas de esta historia corre completa en memoria, sin red ni credenciales y en menos de 5 segundos, con las puertas de calidad del proyecto (tipado estricto, análisis estático y formato) sin errores, en Windows y Linux con Python 3.12.

---

## Assumptions & Scope Boundaries

### Assumptions

- **A-01 — Contratos vigentes**: se usan las firmas actuales de `core/`, sin cambios. Si el equipo decide modificarlas (por ejemplo, tras la revisión de HU-00-01), esta especificación se revisa.
- **A-02 — Dependencias con dobles**: las historias de otros desarrolladores (HU-00-03 FakeProvider, HU-01-02 ToolRegistry, HU-01-05 EventBus, HU-05-01 PermissionPolicy) están `Pendiente` en `docs/PROGRESO.md`. Las pruebas de esta historia usan dobles construidos sobre los contratos existentes (en `tests/doubles/` ya hay `DummyProvider`, `DummyTool`, `DummyApprover` y `RecordingEventBus`; si no bastan, se crean dobles guionizados propios de estas pruebas). Esta historia no implementa ni se apropia de ninguna de esas historias.
- **A-03 — Un turno por invocación**: el bucle ejecuta un turno (una tarea) hasta terminar y devuelve el control; una sesión puede contener varios turnos y el consumidor conserva el historial en memoria para el siguiente (FR-007). La persistencia, la reanudación por identificador y la presentación son de otras historias.
- **A-04 — Entrada confiable del llamador**: el llamador entrega una tarea ya validada, el contexto inicial opcional y un identificador de sesión opaco para los eventos (`Event.session_id`); la creación de sesiones es de HU-03-01.
- **A-05 — `is_external`**: la salida originada en la ejecución de una herramienta (éxito, error informado, excepción) se trata como contenido externo no confiable (marca `is_external=True`), coherente con el contrato de `Message.is_external` y la User Story 3 de la spec 004. Los resultados redactados por el propio bucle antes de ejecutar (desconocida, argumentos inválidos, `DENY`, `ASK`) no lo son. La validación canónica y los convertidores no dependen de esta marca (verificado en `_validation.py`).
- **A-06 — Orden de validación**: se valida antes de consultar la política, de modo que la política solo evalúa llamadas bien formadas y una llamada rechazada por argumentos nunca genera `PERMISSION_DECIDED`.
- **A-07 — Fallos del proveedor sin tipología**: cualquier excepción distinta de la cancelación lanzada por `Provider.complete` se trata como fallo del proveedor; la tipología (cuota, tiempo agotado, indisponible) y los reintentos son de HU-07-04 y HU-00-03.
- **A-08 — Historial en memoria**: durante la ejecución el historial vive en memoria; el llamador lo recibe en el resultado. El ensamblado de contexto (`ContextManager`) y su compactación no intervienen en el Sprint 1.
- **A-09 — Estado de la asincronía**: el bucle es asíncrono por las firmas existentes y respeta la propagación de la cancelación; D-01 sigue pendiente de aprobación.
- **A-10 — Mensajes de error**: el texto de los resultados generados por el bucle se fija en el plan; esta especificación solo exige que sean estructurados, identifiquen la categoría y la causa (FR-019) y conserven el `id` de la llamada.
- **A-11 — Ejecución desatendida**: sin límites de HU-01-06 (FR-028), la ejecución desatendida con proveedores reales no se considera segura; la demostración del Sprint 1 usa proveedor simulado o ejecución supervisada.
- **A-12 — «Leer» bajo `ASK` provisional**: la demostración del Sprint 1 (`docs/03`) lee, escribe y relee un archivo; si la política provisional de C (Sp1-35) resuelve como `ASK` (y por tanto denegación) lo no previsto, la lectura podría ser denegada salvo que C la permita por su nivel de riesgo. Es un riesgo de integración a coordinar con C; no lo resuelve esta historia.

### Dependencias y estado real (según `docs/PROGRESO.md`, 2026-10-18)

| Dependencia | Tipo | Estado real | Tratamiento en esta historia |
|---|---|---|---|
| HU-00-01 — Esqueleto e interfaces | Formal (`docs/04a`) | Pendiente de aprobación técnica (T001–T015 completas; Sp1-03/T016 sin firmas individuales de A, B, C) | Se usan sus contratos tal como están; no se da por aprobada |
| HU-07-01 — Provider y formato interno | Formal (`docs/04a`) | En revisión (D-02 y T018 pendientes de aprobación técnica) | Se usan las entidades, las reglas canónicas y los convertidores como oráculo de pruebas |
| HU-00-03 — FakeProvider (B) | Cruzada | Pendiente | Doble guionizado en pruebas |
| HU-01-02 — ToolRegistry (C) | Cruzada | Pendiente | Doble que cumple `ToolRegistry` y `validate_args` |
| HU-01-05 — EventBus (B) | Cruzada | Pendiente | `RecordingEventBus` u otro doble |
| HU-05-01 — PermissionPolicy (C), incl. Sp1-35 (resolución provisional de `ASK`) | Cruzada | Pendiente | Doble que devuelve `ALLOW`/`DENY`/`ASK`; la política provisional de `ASK` es de C y el bucle solo es la última barrera |
| SPK-02 / D-01 — asincronía | Informativa | SPK-02 en revisión; D-01 pendiente de aprobación | Se respeta; no se presupone ratificada |
| SPK-01 — evidencia con proveedores reales | Informativa | Pendiente (B) | No requerida: sin red ni proveedores reales |

### Scope Boundaries

- **Dentro del alcance**:
  - El ciclo de turnos (consultar, inspeccionar, validar, autorizar, ejecutar, devolver, repetir).
  - La condición de parada, el manejo de errores de herramienta y las terminaciones por fallo.
  - Validación de argumentos (invocando al registro) y resolución de permisos (incluido `ASK` como denegación).
  - Construcción coherente del historial y publicación de eventos con los tipos existentes.
  - Pruebas con dobles (Sp1-14).
- **Fuera del alcance (explícitamente diferido)**:
  - Persistencia en SQLite (HU-03-01, HU-03-02).
  - Compactación de contexto (HU-02-03).
  - Ejecución paralela de herramientas.
  - Límites de turnos, tiempo, tokens y costo, incluido cualquier tope de iteraciones y `LIMIT_REACHED` (HU-01-06, Sprint 2; FR-028).
  - Detección de llamadas repetidas (HU-01-08) y el alcance propio de varias llamadas por turno (HU-01-07), ambas de Sprint 3.
  - Reintentos con espera y conmutación de proveedor (HU-07-04, HU-07-05).
  - Shell (HU-01-04) y MCP (HU-08-01).
  - Subagentes (HU-09-01).
  - CLI de producción (HU-06-01), la interfaz de aprobación (HU-05-03) y la captura de Ctrl+C con resultados «interrumpido» (HU-06-03).
  - Implementación de HU-00-03, HU-01-02, HU-01-05 y HU-05-01 (pertenecen a B y C).
  - Recorte de salidas largas de herramientas (HU-02-02).
  - Streaming de respuestas del proveedor.

### Preguntas abiertas y ratificaciones pendientes

No quedan marcadores de aclaración pendientes ni decisiones del PO sin resolver en esta especificación. Quedan estos puntos de coordinación y de plan, ninguno bloquea `/speckit-tasks`:

1. **Resuelto — Clarify Q4** (`emit` que lanza excepción: el bucle propaga y falla cerrado): decisión aprobada por el PO. El caso que Q4 no cubre literalmente (fallo de `emit(INTERRUPTED)` durante una cancelación) lo resuelve la decisión R-08 (prevalece la cancelación; diagnóstico conservado; ver `plan.md`).
2. **A confirmar con B**: que HU-01-05 aísle los fallos de los suscriptores del bus, y que verifique `APPROVAL_REQUESTED`/`APPROVAL_RESOLVED` con un doble (Q3).
3. **A confirmar con C**: la semántica exacta de `validate_args` (diccionario nuevo con los argumentos efectivos, sin mutar la entrada; excepciones posibles) y que la política provisional razona sobre los argumentos efectivos (R-07, FR-008); la política provisional de `ASK` (Sp1-35) y el riesgo de la lectura en la demostración (A-12).
4. **Resuelto en el plan**: el historial parcial ante cancelación se entrega porque el historial es propiedad del llamador y el bucle le añade mensajes en el sitio (FR-026; `plan.md`, D-PLAN-03); el núcleo añade una comprobación estructural mínima del contexto inicial, sin importar `adapters/` (FR-001; `plan.md`, D-PLAN-05).

---

## Trazabilidad

| Elemento | Referencia |
|---|---|
| Requisitos | RF-1.1 (ciclo del agente), RF-1.5 (errores de herramienta); RF-1.8 (eventos desacoplados, vía HU-01-05) |
| Criterios | AC-01 → US1, SC-001, FR-004, FR-015; AC-02 → US2, SC-003, FR-016–FR-019 |
| Reglas de negocio | Regla 1 → FR-017, FR-018; Regla 2 → FR-029, FR-030, SC-004 |
| Decisiones (`docs/01`) | V-01 (aprobación bidireccional; aquí `ASK` como denegación, `Approver` sin cablear), V-11 (herramienta cancelada; fuera de alcance, HU-06-03), V-14 (FakeProvider como base de pruebas) |
| Tareas (`docs/03`) | Sp1-12 (turno completo), Sp1-13 (parada y eventos), Sp1-14 (pruebas con proveedor simulado) |
| Historias vecinas | HU-01-02 (validación), HU-05-01 (política y `ASK`; Sp1-35 de C), HU-01-05 (bus), HU-00-03 (FakeProvider), HU-07-01 (formato y reglas canónicas), HU-01-06 (límites, Sprint 2; FR-028), HU-01-07 (varias llamadas por turno, Sprint 3; solapamiento anotado), HU-01-08 (llamadas repetidas, Sprint 3), HU-06-03 (interrupción) |
| Aclaraciones | «Clarify Q1» → FR-028; «Q2» → FR-003, FR-015; «Q3» → FR-013, tabla de eventos; «Q4» → FR-031; «Q5» → FR-012–FR-014 |
| Constitución | Principio I (una historia), III (hexagonal, tipado), IV (pruebas sin red), V (ACs inmutables), VI (sin código de sprints futuros), VIII (registro en PROGRESO), IX (Definition of Done) |
| Demostración Sprint 1 | Tarea guionizada de tres pasos con proveedor simulado (`docs/03`) |
