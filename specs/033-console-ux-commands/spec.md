# Feature Specification: HU-06-05 — Consola legible y comandos útiles de sesión

**Feature Branch**: `claude/cli-console-ux-ea1667` (el directorio de la spec es `033-console-ux-commands`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-30

**Status**: Clarificada (2026-10-30); historia **propuesta**: no existe ficha en `docs/04x`, ver «Registro de la historia propuesta»; lista para `/speckit-plan`

**Proyecto**: HARNESS v2.5 | **Sprint**: 3 (adelantado por el cierre del 6/11/2026) | **Responsable**: C — Control y conexiones | **Requisitos**: RF-6.x (presentación) y RF-6.6 (comandos de sesión) | **Depende de**: HU-06-01 (CLI básica, en revisión), HU-05-03/04 (aprobación y motivo de rechazo), HU-01-06 (límites), HU-02-03 (compactación), HU-03-04 (reanudar, en revisión)

**Input**: User description: "Mejorar la consola tras la prueba manual con Gemini: los mensajes con los que el arnés pregunta si autoriza ejecutar un comando son difíciles de leer; la consola debe parecerse a la de Claude Code (mostrar con claridad lo que el agente va haciendo mientras se escribe una tarea) y tener más comandos útiles: /sesiones, /nueva, /compactar y /model (solo mostrar). Color solo con stdlib, respetando NO_COLOR y sin romper la consola clásica de Windows."

## Registro de la historia propuesta

- **ID propuesto: `HU-06-05`**, familia HU-06 (existen HU-06-01 a HU-06-04 en `docs/00-indice.md`). No hay ficha en `docs/04c`: el PO decide si la formaliza o la renombra, como se hizo con HU-00-08.
- Los **criterios de aceptación AC-01 a AC-09 de esta spec son propuestos**: son inmutables sin permiso del PO (Principio V), así que la historia **no puede pasar a `Hecha`** sin su visto bueno.
- Reutiliza, sin ampliarlos, los criterios de **HU-06-04 AC-01** (comandos de sesión: listar, nueva, reanudar, salir) y **HU-02-04 AC-01** (compactación manual). No los sustituye: la ficha de HU-06-04 (Sprint 4, área B) y la de HU-02-04 (Sprint 3, área B) siguen pendientes; esta historia entrega la parte de consola que el alcance pide.
- Esta historia **cambia la presentación** que HU-06-01 dejó en revisión (líneas `... ejecutando:`, `v x: correcto`, `x Error: ...`); sus pruebas se actualizan, no se borran.

## Clarifications

### Session 2026-10-30

Respuestas del usuario (preguntadas de una en una); ninguna contradice criterios de otra historia.

- Q: ¿Qué hace `/compactar` si el historial está por debajo del umbral? → A: **Compacta igualmente** (resume todo salvo los mensajes recientes protegidos, mínimo configurado); si no hay nada que resumir, lo dice (A1, FR-012, HU-02-04 AC-01).
- Q: ¿Cuántas sesiones lista `/sesiones`? → A: **Las 10 más recientes**, sin argumentos ni paginación, con línea «y N más» (A2, FR-010).
- Q: ¿Qué nivel de detalle tiene la vista de actividad? → A: **Compacto**: una línea al pedir y otra con resultado y duración; aprobaciones resueltas, compactación, límites y errores; sin decisiones `allow` automáticas (A3, FR-007).
- Q: ¿Se confirman AC-01 a AC-09 tal como están redactados? → A: **Confirmados por el usuario**; siguen siendo **propuestos** hasta el visto bueno del PO (H1).

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación propuestos (confirmados por el usuario el 2026-10-30; pendientes del visto bueno del PO)

- **AC-01 — Pregunta de aprobación legible.** Dado que el agente pide ejecutar una herramienta que requiere aprobación, cuando la consola me pregunta, entonces veo un bloque con: una frase que dice qué quiere hacer el agente, el comando, archivo o ruta destacado en su propia línea, el nivel de riesgo, el efecto esperado y las tres opciones; cada dato en su línea, siempre en el mismo orden.
- **AC-02 — El bloque no se rompe ni filtra.** Dado un comando o argumento largo, con saltos de línea, caracteres de control o un valor con aspecto de clave, cuando se muestra el bloque, entonces el formato no se rompe (se acota y se escapa), el valor con aspecto de clave aparece oculto, y se conserva lo ya garantizado por HU-05-03: `1`/`2`/`3` eligen, fin de entrada o tres respuestas no válidas rechazan, el texto inválido no se repite.
- **AC-03 — Vista de actividad.** Dado que escribo una tarea, cuando el agente trabaja, entonces la consola muestra una línea clara por paso con lo que hace ahora (herramienta pedida o en ejecución, resultado con su duración cuando se puede derivar, aprobación resuelta, límite alcanzado, contexto compactado, error del proveedor), usando solo los datos que los eventos ya traen.
- **AC-04 — `/sesiones`.** Dado que escribo `/sesiones`, entonces veo las sesiones principales guardadas (sin las de subagente), la más reciente primero, con identificador completo, fecha, estado y modelo, la actual marcada, y un máximo de líneas con el aviso de cuántas más hay.
- **AC-05 — `/nueva`.** Dado que escribo `/nueva`, entonces empieza una sesión limpia (historial inicial sin conversación previa, otro identificador, mensajes siguientes guardados en ella) y se me informa de su identificador; la sesión anterior queda guardada y reanudable.
- **AC-06 — `/compactar`.** Dado una sesión activa, cuando escribo `/compactar`, entonces se compacta con el mismo mecanismo que la compactación automática aunque no se haya alcanzado el umbral, y se informa cuántos tokens (estimados) se liberaron; si no hay nada que resumir lo digo claramente.
- **AC-07 — `/model`.** Dado que escribo `/model`, entonces veo el modelo configurado y los límites de la ejecución; no cambia nada y nunca muestra la clave.
- **AC-08 — `/ayuda` completa.** Dado que escribo `/ayuda`, entonces lista todos los comandos disponibles (`/ayuda`, `/salir`, `/sesiones`, `/nueva`, `/reanudar`, `/compactar`, `/model` y, con tarea, `/criterios`), cada uno con su descripción.
- **AC-09 — Color opcional y texto plano equivalente.** Dado que la salida no es una terminal, o `NO_COLOR` está definida, o es una consola de Windows sin soporte ANSI, cuando se muestra cualquier cosa de esta historia, entonces no hay ningún código ANSI y el texto es igual de legible; con soporte, el color solo resalta (nunca es la única señal).

### Reglas de negocio (propuestas)

1. La CLI solo presenta: no decide permisos, no ejecuta herramientas, no valida. Las reglas de aprobación y el bucle no cambian.
2. La CLI no inventa campos: usa solo lo que traen los eventos (que por diseño no llevan argumentos ni contenido) y lo que el `Approver` recibe en `details`.
3. Todo texto que viene del modelo, de una herramienta o de la persona se sanea y se acota antes de mostrarse.
4. Los comandos nuevos se resuelven en la CLI y en la composición; no cambian puertos, eventos ni contratos.
5. `/model` solo muestra; cambiar de modelo en caliente está fuera de alcance.

### User Story 1 - Entender de un vistazo qué se me pide autorizar (Priority: P1)

Hoy la pregunta es una lista de líneas poco jerarquizada («[!] El agente quiere ejecutar: shell / command: … / efecto: … (riesgo: …)») donde lo importante (el comando) se pierde entre los argumentos. Quiero un bloque con una frase, el comando destacado, el riesgo, el efecto y las opciones.

**Why this priority**: es el feedback directo de la prueba manual y la decisión más delicada que toma la persona; falla cerrada si no se entiende lo que se aprueba.

**Independent Test**: con un `ConsoleApprover` sobre `io.StringIO`, pedir la aprobación de una llamada `shell` con un comando largo y comprobar las líneas del bloque; responder `1`, `2`, `3`.

**Acceptance Scenarios**:

1. **Given** una petición de `shell` con `command`, **When** se pregunta, **Then** el bloque abre con una frase que menciona la acción («ejecutar un comando»), muestra el comando en una línea propia destacada, luego riesgo, efecto y las opciones `[1] [2] [3]`.
2. **Given** una petición con `path` (escritura de archivo), **When** se pregunta, **Then** la frase habla de la ruta y la ruta va destacada; los demás argumentos van debajo, en una sección aparte y acotada.
3. **Given** una herramienta sin `command` ni `path`, **When** se pregunta, **Then** la frase nombra la herramienta y los argumentos se muestran como lista acotada.
4. **Given** el usuario responde `3`, **When** se pide el motivo, **Then** el comportamiento de HU-05-04 no cambia.

---

### User Story 2 - Un bloque que no se rompe con entradas hostiles (Priority: P1)

El modelo controla el texto del comando. Un comando de 5 000 caracteres, con saltos de línea o secuencias de escape no debe desordenar la pantalla ni suplantar líneas del bloque.

**Why this priority**: seguridad de presentación (el bloque es lo que la persona lee para autorizar).

**Independent Test**: pedir aprobación con un comando que contiene `\n`, `\x1b[2J`, controles bidireccionales y 5 000 caracteres; verificar que cada línea impresa pertenece al bloque y que el valor con aspecto de clave aparece como `***`.

**Acceptance Scenarios**:

1. **Given** un comando con saltos de línea, **When** se muestra, **Then** los saltos aparecen escapados (visibles) y el comando ocupa un número acotado de líneas.
2. **Given** un comando de más de N caracteres, **When** se muestra, **Then** se acota con `...` y se indica que se omitió el resto.
3. **Given** un argumento llamado `api_key`, **When** se muestra, **Then** su valor es `***`.
4. **Given** el centinela `VALOR-DE-PRUEBA-123` en un argumento secreto, **When** se muestra, **Then** no aparece en la salida.

---

### User Story 3 - Ver qué está haciendo el agente ahora (Priority: P1)

Quiero una vista parecida a la de Claude Code: una línea por paso, en orden, que me diga qué herramienta se pidió, que está ejecutándose, cómo terminó y cuánto tardó.

**Why this priority**: es la mitad del pedido (confianza en lo que hace el agente) y no requiere cambiar el núcleo.

**Independent Test**: publicar en un bus la secuencia `tool_requested` → `tool_finished` con marcas de tiempo conocidas y comprobar las líneas y la duración.

**Acceptance Scenarios**:

1. **Given** `tool_requested` de `shell`, **When** se publica, **Then** aparece una línea «ejecutando» con el nombre.
2. **Given** el `tool_finished` correspondiente (mismo `call_id`) 1,2 s después, **When** se publica, **Then** aparece una línea de resultado con la duración «1,2 s».
3. **Given** una herramienta que esperó una aprobación, **When** termina, **Then** la duración no cuenta el tiempo de espera de la persona.
4. **Given** un `tool_finished` sin `tool_requested` previo (p. ej. cierre sintético por un corte), **When** se publica, **Then** la línea de resultado sale sin duración y sin error.
5. **Given** `context_compacted`, **When** se publica, **Then** una línea dice que se compactó el contexto y cuántos eventos cubrió.
6. **Given** un `limit_reached` o `provider_error`, **When** se publican, **Then** conservan su explicación y sugerencia actuales.

---

### User Story 4 - Gobernar las sesiones desde la terminal (Priority: P2)

Quiero `/sesiones` para ver qué hay guardado, `/nueva` para empezar limpio, `/compactar` para resumir cuando yo quiera y `/model` para saber con qué modelo y límites trabajo.

**Why this priority**: completa el pedido; reutiliza criterios de HU-06-04 y HU-02-04.

**Independent Test**: con un almacén SQLite temporal y un proveedor falso, ejecutar cada comando por `run_session` y comprobar la salida y el efecto en el almacén.

**Acceptance Scenarios**:

1. **Given** cinco sesiones guardadas (una de subagente), **When** `/sesiones`, **Then** salen cuatro, la más reciente primero, la actual marcada.
2. **Given** más de 10 sesiones, **When** `/sesiones`, **Then** salen 10 y una línea «y N más».
3. **Given** una conversación en curso, **When** `/nueva`, **Then** la siguiente tarea no ve la conversación anterior y se guarda en la sesión nueva; `/reanudar <anterior>` la recupera.
4. **Given** una sesión con tarea (criterios), **When** `/nueva`, **Then** se rechaza con un mensaje claro (igual que `/reanudar`).
5. **Given** un historial por debajo del umbral, **When** `/compactar`, **Then** se compacta igualmente y se informa «~A → ~B tokens»; con historial demasiado corto se informa que no hay nada que compactar.
6. **Given** un fallo del proveedor durante `/compactar`, **When** ocurre, **Then** el historial queda intacto y se informa del fallo sin trazas.
7. **Given** `/model`, **Then** salen modelo, ventana/umbral de contexto y los límites; sin clave.

---

### User Story 5 - Color que ayuda y nunca estorba (Priority: P3)

En una terminal con soporte, quiero resaltar el riesgo, los éxitos y los errores; en una tubería, un archivo o `NO_COLOR`, nada de códigos raros.

**Why this priority**: mejora de legibilidad; el texto plano ya es completo, así que es la última rebanada.

**Independent Test**: renderizar con `StringIO` (no es terminal) y con un flujo simulado `isatty() == True`, con y sin `NO_COLOR`.

**Acceptance Scenarios**:

1. **Given** un `StringIO`, **When** se muestra cualquier salida, **Then** no contiene `\x1b`.
2. **Given** un flujo terminal, `NO_COLOR` definida, **Then** no contiene `\x1b`.
3. **Given** un flujo terminal en Windows sin indicios de soporte ANSI, **Then** no contiene `\x1b`.
4. **Given** un flujo terminal con soporte, **Then** el riesgo alto, los errores y los éxitos llevan color y el texto sin códigos es idéntico al texto plano.

---

### Edge Cases

- Comando vacío o `command` que no es texto: se muestra `(vacío)`/su `repr` acotado; nunca falla.
- `details` sin `risk`/`effect`: textos neutros («desconocido», «(sin descripción)»), como hoy.
- Más de 20 argumentos: se acota con «y N más».
- Un `call_id` repetido o muchas llamadas pendientes: el estado de duraciones tiene tope y nunca crece sin límite; una llamada sin cierre no rompe las siguientes.
- Marcas de tiempo que van hacia atrás: la duración no se muestra (nunca negativa).
- `/sesiones` con el almacén vacío o con fallo de lectura: mensaje fijo, sin trazas.
- `/compactar` o `/nueva` con tarea activa: ver Story 4.4; `/compactar` funciona también con tarea.
- `/model` con `max_*` sin límite: se indica «sin límite».
- Salida con codificación que no soporta los caracteres decorativos: la decoración es ASCII; el texto no codificable se reemplaza como hoy.
- Terminal estrecha: las líneas del bloque no dependen del ancho de la terminal (acotadas por caracteres, no por columnas).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El bloque de aprobación MUST mostrar, en este orden y una cosa por línea: título del bloque, frase de la acción, valor principal destacado (`command` o `path` si existe), argumentos restantes, riesgo, efecto y opciones.
- **FR-002**: La frase de la acción MUST derivarse solo de `details` (`tool`, `arguments`) y de constantes de la CLI; sin `command`/`path` nombra la herramienta.
- **FR-003**: Los valores de argumentos cuyo nombre sugiera una clave (`key`, `secret`, `token`, `password`, `passwd`, `credential`, `auth`) MUST mostrarse como `***`, incluido el valor principal.
- **FR-004**: Todo valor mostrado MUST sanearse (controles y bidireccionales fuera), escaparse (saltos de línea como `\n` visibles) y acotarse; el valor principal admite hasta un tope mayor que el de los demás.
- **FR-005**: La lectura de la respuesta MUST seguir igual: `1`/`2`/`3`, `/salir` rechaza, fin de entrada rechaza, `max_attempts` respuestas no válidas rechazan, el texto inválido no se repite, el motivo tras `3` se pide igual (HU-05-03/04).
- **FR-006**: El riesgo MUST escribirse con palabra (bajo/medio/alto/desconocido) y, con color, resaltarse; la palabra siempre está.
- **FR-007**: La vista de actividad MUST mostrar una línea por `tool_requested`, `tool_finished`, `permission_decided` (no `allow`), `approval_resolved`, `context_compacted`, `provider_error`, `limit_reached` y el texto del asistente, con las explicaciones y sugerencias de error actuales.
- **FR-008**: La duración de una herramienta MUST derivarse de las marcas de tiempo de `tool_requested` y `tool_finished` con el mismo `call_id`, restando la espera entre `approval_requested` y `approval_resolved` de esa llamada; si no es derivable, la línea sale sin duración.
- **FR-009**: El estado para duraciones MUST ser acotado en tamaño y por renderizador (no global) y no conservar argumentos ni contenido.
- **FR-010**: `/sesiones` MUST listar solo sesiones sin padre (no subagente), de la más reciente a la más antigua, máximo 10, con identificador completo, fecha UTC legible, estado, modelo, marca de actual y, si existe, el objetivo saneado y acotado; sin cambiar el puerto `SessionStore` ni sus contratos.
- **FR-011**: `/nueva` MUST crear una sesión en el almacén, reiniciar el historial al prefijo inicial, enlazar el guardado de mensajes y el compactador a la nueva sesión, dejar intacta la anterior e informar el identificador; con tarea activa MUST rechazarse con mensaje claro.
- **FR-012**: `/compactar` MUST usar el mismo compactador y archivo que la compactación automática, con el umbral de disparo bajado solo para esa llamada, informar tokens estimados antes y después, y no dejar nada parcial si falla.
- **FR-013**: `/model` MUST mostrar el modelo, el tamaño de ventana y el umbral de compactación y los límites (`max_turns`, `max_seconds`, `max_tokens`, `max_output_tokens`) y MUST NOT mostrar secretos ni cambiar estado.
- **FR-014**: `/ayuda` MUST listar todos los comandos registrados con su descripción, en un orden estable.
- **FR-015**: El color MUST activarse solo si el flujo es una terminal, `NO_COLOR` no está definida (o vacía) y, en Windows, hay indicios de soporte ANSI; en cualquier otro caso el texto no contiene códigos ANSI. El entorno y el flujo son inyectables.
- **FR-016**: El texto plano MUST ser autosuficiente: ninguna información se transmite solo por color.
- **FR-017**: Ningún dato de argumentos o contenido MUST entrar en eventos ni en la vista de actividad (la CLI no inventa campos; si un dato falta en el evento, se deja como hallazgo).
- **FR-018**: Los cambios MUST limitarse a `src/harness_agent/cli/` y al cableado de `bootstrap.py`; `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/` y `docs/archivo/` no se tocan.
- **FR-019**: `cli/` MUST usar solo la biblioteca estándar y la API pública de `harness_agent.core`.
- **FR-020**: Los mensajes al usuario MUST estar en español; identificadores, docstrings y comentarios en inglés.

### Key Entities

- **Bloque de aprobación**: representación en texto de una solicitud (acción, valor principal, argumentos, riesgo, efecto, opciones).
- **Línea de actividad**: una línea de salida por evento mostrado; puede llevar duración.
- **Estilo de salida**: decisión (por flujo y entorno) de usar o no color.
- **Resumen de sesión**: fila de `/sesiones` (id, fecha, estado, modelo, objetivo, marca de actual).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En una prueba con un comando de 5 000 caracteres y 40 saltos de línea, el bloque ocupa como máximo 20 líneas y todas pertenecen al formato.
- **SC-002**: En 100 % de las salidas sobre un flujo que no es terminal o con `NO_COLOR`, hay cero códigos ANSI.
- **SC-003**: Una persona identifica el comando que se le pide autorizar, el riesgo y las opciones leyendo solo el bloque, sin desplazarse (≤ 20 líneas).
- **SC-004**: Cada herramienta ejecutada produce exactamente una línea de inicio y una de resultado, en ese orden.
- **SC-005**: `/sesiones`, `/nueva`, `/compactar` y `/model` responden en una sola salida sin trazas ante cualquier fallo del almacén o del proveedor.
- **SC-006**: Las cinco puertas de calidad y la suite de arquitectura terminan en 0 y el centinela `VALOR-DE-PRUEBA-123` no aparece en ninguna salida de las pruebas de secretos.

## Assumptions

- **A1 (confirmado)**: `/compactar` compacta siempre que haya algo que resumir, conservando los mensajes recientes que el compactador ya protege (mínimo configurado); no es un «vaciar contexto».
- **A2 (confirmado)**: `/sesiones` muestra las 10 más recientes; no admite argumentos ni paginación.
- **A3 (confirmado)**: nivel de detalle de la actividad «compacto»: una línea por paso; no se muestran las decisiones `allow` automáticas.
- **A4**: la decoración es solo ASCII (consolas clásicas de Windows con páginas de códigos antiguas).
- **A5**: `/nueva` no reinicia los contadores de límites (viven en el bucle, que es del núcleo y no se toca), igual que `/reanudar` (HU-03-04); se documenta como observación.
- **A6**: el tiempo mostrado es de reloj de pared entre eventos (marcas de tiempo del evento), no del proceso.
- **A7**: la compactación manual se obtiene construyendo el compactador existente con un umbral de disparo mínimo solo para ese comando; un parámetro explícito de «forzar» en el núcleo sería más limpio y queda como hallazgo para B.
- **A8**: `/model` solo muestra; cambiar de modelo en caliente, el panel de subagentes, `/mcp` y el comando de skills están fuera de alcance (observaciones en `PROGRESO.md`).
- **A9**: el detalle del error de una herramienta sigue sin viajar en el evento (hallazgo previo de HU-06-01); esta historia no lo cambia.

## Preguntas abiertas

Ninguna. A1–A3 y AC-01 a AC-09 quedaron confirmados por el usuario en `/speckit-clarify`; el visto bueno del PO sigue pendiente (H1).

## Dependencias y tareas humanas

- **H1**: el PO confirma o renombra HU-06-05 y ratifica AC-01 a AC-09.
- **H2**: revisión cruzada por una persona de otra área (A o B), en especial el cableado de `bootstrap.py` y la compactación forzada (A7).
- **H3**: CI remota en Windows y Linux.
- **H4**: ratificación técnica de HU-00-01 (bloquea `Hecha` para cualquier historia).
