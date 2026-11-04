# Especificación: HU-09-01, HU-09-03 y HU-09-04 — Subagentes mínimos (el «reto del proyecto»)

**Rama**: `gustavo` · **Responsables de las fichas**: B — Estado (HU-09-01), A — Núcleo (HU-09-03 y HU-09-04) · **Implementa**: Claude por encargo de la persona usuaria, carril cruzado (pendiente de ratificar por A, B y C)
**Depende de**: HU-01-01 (`AgentLoop`), HU-03-01 (almacén de sesiones), HU-01-05 (bus), HU-01-06 (límites), HU-05-07 (solo lectura), HU-10-02 (redacción de secretos)
**Fuera de alcance**: HU-09-02 (perfiles e instrucciones propias por subagente), HU-09-05 (propagación explícita de errores más allá de lo que trae el resultado), HU-09-06 (verificador y explorador), HU-09-07 (subagentes en paralelo).

## Resumen

El agente principal (el *orquestador*) recibe una herramienta `delegar`. Con ella entrega una subtarea a un *subagente* que corre en una **sesión hija** con el contexto vacío (solo la tarea recibida), con su propio bucle, sus propios límites y las mismas reglas de permisos que el orquestador. Cuando termina, el orquestador no recibe la transcripción, sino un **resultado estructurado y breve** (`resultado`, `hallazgos_clave`, `fuentes`, `error`) validado contra un esquema. Un subagente no puede delegar. Si agota sus turnos, devuelve un resultado **parcial**. Las aprobaciones que el subagente necesita suben a la persona indicando quién las pide.

La delegación está **apagada por defecto** y se activa con `[subagents] enabled = true` en `config.toml` (D-19): sin eso no existe la herramienta ni el ejecutor, y ninguna sesión cambia.

No se cambia ningún puerto de `core/interfaces/` (se **implementa** `SubagentRunner` tal como está), ni `core/loop.py` (cada subagente usa un `AgentLoop` propio), ni el catálogo de eventos (se usan `SUBAGENT_STARTED` y `SUBAGENT_FINISHED`, que ya existen), ni `core/redaction.py`, ni `core/verification/`.

## Historias y criterios de aceptación (literales de `docs/04d-historias-conexiones.md`)

### HU-09-01 — Delegar en un subagente con contexto limpio

**Reglas de negocio**

1. El subagente solo recibe lo que el orquestador le pasa.
2. La sesión hija se guarda con el identificador de su padre.

**Criterios de aceptación**

- **AC-01 — Sesión hija con contexto vacío.** Dado una subtarea, cuando el orquestador delega, entonces se crea una sesión hija con contexto vacío que solo contiene la tarea recibida.
- **AC-02 — Sin historial del orquestador.** Dado el subagente en ejecución, cuando se revisa su contexto, entonces no contiene el historial del orquestador.

### HU-09-03 — Resultado estructurado en lugar de la transcripción

**Reglas de negocio**

1. La transcripción del subagente no entra al contexto del orquestador.
2. Las aprobaciones del subagente suben al usuario indicando quién las pide.

**Criterios de aceptación**

- **AC-01 — Resultado estructurado sin transcripción.** Dado un subagente que terminó, cuando devuelve su resultado, entonces el orquestador recibe resultado, hallazgos clave y fuentes, y no la transcripción.

### HU-09-04 — Un solo nivel de anidamiento y límites por subagente

**Reglas de negocio**

1. Solo se permite un nivel de anidamiento.
2. Los límites del subagente son independientes de los del orquestador.

**Criterios de aceptación**

- **AC-01 — Anidamiento rechazado.** Dado un subagente que intenta lanzar otro, cuando invoca la delegación, entonces se rechaza.
- **AC-02 — Resultado parcial por límite.** Dado un límite de turnos del subagente, cuando se alcanza, entonces termina y devuelve un resultado parcial.

En el resto del documento se citan como **HU-09-01 AC-01**, **HU-09-01 AC-02**, **HU-09-03 AC-01**, **HU-09-04 AC-01** y **HU-09-04 AC-02**.

## Decisiones (dudas pequeñas resueltas con el criterio más seguro; pendientes de ratificar)

No hizo falta parar por un caso A/B/C: nada de lo que sigue exige cambiar un puerto, `core/loop.py`, el catálogo de eventos, `core/redaction.py` ni `core/verification/`.

- **D-01 Perfil.** Sin perfiles (HU-09-02): un único perfil fijo `general`. El parámetro `profile` del puerto se recibe y se registra en el evento, y no cambia nada más.
- **D-02 Herramienta.** Se llama `delegar` y recibe `objetivo` (obligatorio), `contexto_minimo` (opcional) y `formato_salida` (opcional). Riesgo `LOW`: la herramienta en sí no cambia nada (lo que haga el subagente pasa por la cadena) y, con riesgo medio y sin `path`, la política por defecto la denegaría. Es una herramienta *abierta* (como `preguntar_usuario`, HU-06-02): la política de archivos pregunta, y `OpenToolsPolicy` convierte ese «preguntar» en «permitir» salvo que `[permissions] ask` o `deny` la nombre. Razón: lo que hace el subagente pasa por la misma cadena de políticas y aprobaciones; pedir permiso para delegar sería un segundo aviso por lo mismo.
- **D-03 Solo lectura.** `delegar` **no** es una lectura: en modo solo lectura (`--solo-lectura`, `/plan`) la política lo deniega como a cualquier herramienta que el modo no lista. Es lo más cerrado; permitirlo con el subagente también en solo lectura queda como mejora futura.
- **D-04 Contexto del hijo.** La conversación del subagente es **un solo mensaje `USER`** con la tarea: objetivo, contexto mínimo, formato de salida y las instrucciones fijas del resultado (el esquema). Sin prefijo `SYSTEM`, sin avisos de modo, sin historial. Del parámetro `context` del puerto solo se aceptan los mensajes `USER` no externos; el resto se descarta.
- **D-05 Bucle del hijo.** Cada delegación crea un `AgentLoop` nuevo (sin tocar `core/loop.py`) con el **mismo** proveedor, bus y política del orquestador, un aprobador envuelto y límites propios. Esa política es el mismo objeto: el subagente hereda `deny`, las rutas protegidas, las reglas del shell, de git y el modo de solo lectura (también si se activa después), y nunca tiene más permisos que el orquestador. Las aprobaciones «para la sesión» que la persona dé a un subagente valen solo para él.
- **D-06 Un nivel.** El registro del hijo es una **vista** del registro del orquestador que oculta `delegar`: el subagente no la ve y, si la llama, el bucle responde `[unknown_tool]` (rechazo). Las herramientas MCP que se registren después también le llegan, igual que al orquestador.
- **D-07 Sesión hija.** `sessions.parent_id` existe desde el esquema v1 y `create_session(parent_id=)` ya valida que el padre exista: **no se cambia el esquema** (sigue en v5). La sesión hija guarda el modelo, el objetivo (una línea, sin secretos, ≤ 200 caracteres) y el identificador de la sesión **activa** del orquestador. `/sesiones` ya excluye las que tienen padre y se mantiene. Sus eventos se guardan con su propio identificador (con la redacción de secretos del registrador). Sus mensajes **no** se guardan en `mensajes`: una sesión hija no se puede reanudar. El almacén no tiene operación para cambiar el estado de una sesión; la hija queda `active`, igual que las de nivel superior.
- **D-08 `SessionCursor` en `/nueva`.** Para que el padre sea siempre la sesión activa, `/nueva` mueve también el `SessionCursor` (hoy solo lo mueve `/reanudar`). Cambio mínimo en `bootstrap.py`.
- **D-09 Resultado.** El subagente termina con **un objeto JSON** (se acepta dentro de un bloque de código) con `resultado` (texto), `hallazgos_clave` (lista de textos), `fuentes` (lista de textos) y, si no pudo cumplir, `error` (texto). Se valida con el validador de esquemas propio del núcleo; un campo no declarado o de otro tipo hace el resultado inválido. Después se acota (`resultado` ≤ 4 000 caracteres; cada elemento ≤ 500; ≤ 10 elementos por lista; `error` ≤ 500) con la marca `…`. La salida siempre trae las cinco claves `resultado`, `hallazgos_clave`, `fuentes`, `error` y `parcial`.
- **D-10 Errores con códigos fijos.** Nada de lo que dice el subagente o el proveedor sobre un fallo llega al orquestador: `resultado_no_valido` (la respuesta final no es un JSON válido), `fallo_del_proveedor`, `respuesta_invalida_del_proveedor`, `fallo_del_subagente` (excepción), `limite_alcanzado:<turns|time|tokens>` (parcial) y `sin_sesion_hija` (no se pudo crear la sesión). `is_error` es verdadero en todos salvo el parcial por límite; también lo es cuando el propio subagente informa un `error`. Una cancelación nunca se captura.
- **D-11 Parcial.** Al alcanzar un límite del hijo el bucle publica `LIMIT_REACHED` (con la sesión hija) y no llama al modelo. El resultado lleva `parcial: true`, `error: limite_alcanzado:<límite>` y, como `resultado`, el último texto del asistente del hijo (acotado) o vacío. Sin hallazgos ni fuentes.
- **D-12 Límites propios.** Sección opcional `[subagents]` de `config.toml`: `enabled` (apagada), `max_turns` (10), `max_seconds` (300) y `max_tokens` (50 000). Cada delegación tiene su contador (se crea con el bucle) y **no suma** al contador del orquestador; los del orquestador siguen contando solo sus propias llamadas. Un «turno» es una llamada al modelo, como en HU-01-06; «costo» es el presupuesto de tokens.
- **D-13 Transcripción.** El orquestador solo recibe el contenido del `ToolResult` de `delegar` (el JSON del resultado). Los mensajes del hijo viven en una lista local de la delegación y se descartan; no se copian al historial del orquestador, ni a un evento, ni al resumen de la compactación.
- **D-14 Dato externo y secretos.** El bucle ya marca `is_external=True` todo resultado de herramienta. Además el ejecutor recibe el redactor general (HU-10-02) y lo aplica a **todos los textos** del resultado y al objetivo guardado en la sesión hija antes de devolverlos.
- **D-15 Aprobaciones.** El aprobador del hijo envuelve al de la terminal y añade `requested_by` («subagente `<8 primeros caracteres de la sesión hija>`») a los detalles. `cli/approval_view.py` muestra la línea `Pide:` solo si ese dato llega; sin él el bloque es idéntico. Sin aprobador, el «preguntar» del subagente se deniega como en el orquestador.
- **D-16 Eventos.** `SUBAGENT_STARTED {child_session_id, profile}` y `SUBAGENT_FINISHED {child_session_id, status, is_error, partial}` en la sesión **del orquestador**, sin texto del subagente. Son informativos: si un suscriptor falla al recibirlos, la delegación sigue. Los eventos del bucle del hijo (herramientas, permisos, aprobaciones, límite) llevan el identificador de la sesión hija.
- **D-17 Secuencia.** El bucle ejecuta las llamadas de herramientas de una en una, así que dos `delegar` en la misma respuesta corren una tras otra. El paralelo es HU-09-07.
- **D-18 Visibilidad.** La terminal muestra las líneas de actividad del subagente sin etiqueta (el renderizador no distingue sesiones); solo las aprobaciones indican quién pide. Queda como hallazgo para C.
- **D-19 Apagada por defecto.** Registrar `delegar` siempre añadía su declaración (unos 300 tokens) a cada petición de todas las sesiones y movía los umbrales de compactación calibrados a mano en **28 pruebas existentes** (el dry run con una herramienta ficticia ya movía 14; ver el plan). Además un subagente gasta llamadas al modelo que la persona no pidió y un modelo pequeño podría delegar sin necesidad. Lo más seguro: `enabled = false` por defecto; con la opción apagada no se crea la herramienta, ni el ejecutor, ni la apertura en la política, y el comportamiento y las pruebas existentes no cambian. Si el PO la quiere activa por defecto, basta cambiar el valor por defecto y recalibrar esas pruebas (H03).

## Requisitos funcionales

- **FR-001** (HU-09-01 AC-01) `delegar` crea una sesión hija cuyo contexto es exactamente un mensaje `USER` con la tarea; el proveedor recibe solo eso.
- **FR-002** (HU-09-01 AC-02) El contexto del subagente no contiene ningún mensaje del historial del orquestador.
- **FR-003** (HU-09-01 regla 2) La sesión hija se guarda con el identificador de la sesión activa del orquestador como `parent_id`, en un archivo SQLite real.
- **FR-004** (HU-09-01) `SubagentRunner` se implementa sin cambiar el puerto; el subagente ejecuta su propio `AgentLoop` y devuelve el control al orquestador.
- **FR-005** (HU-09-03 AC-01) El orquestador recibe `resultado`, `hallazgos_clave`, `fuentes` y `error` validados contra el esquema, y ni un mensaje ni una llamada de herramienta del subagente.
- **FR-006** (HU-09-03 regla 1) Ningún texto de la transcripción del subagente entra a mensajes, eventos del orquestador ni al resumen del orquestador.
- **FR-007** (HU-09-03 regla 2) Una aprobación que el subagente necesita llega a la persona con la línea de quién la pide.
- **FR-008** (HU-09-03) El resultado viaja como dato externo y con los secretos ocultos.
- **FR-009** (HU-09-04 AC-01) Un subagente que llama a `delegar` recibe un rechazo y el orquestador no se entera de un tercer nivel.
- **FR-010** (HU-09-04 AC-02) Al alcanzar `max_turns` del subagente este termina y el orquestador recibe un resultado parcial con `parcial: true`.
- **FR-011** (HU-09-04 regla 2) Los límites del subagente (turnos, tiempo, tokens) son propios, configurables y no se suman a los del orquestador.
- **FR-012** `delegar` pasa por la misma cadena de permisos: lo que la cadena deniega, se deniega (también `deny` de la configuración y el modo de solo lectura); un fallo de la cadena es denegar.
- **FR-013** El subagente hereda esa cadena y nunca tiene más permisos que el orquestador.
- **FR-014** Todo fallo se traduce a un código fijo sin texto del subagente, del proveedor ni de excepciones; la cancelación se propaga.
- **FR-015** No cambian `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py`, `core/verification/` ni `tests/doubles/`.
- **FR-016** Con la configuración por defecto la delegación no existe: el modelo no recibe `delegar`, `Composition.subagent_runner` es `None` y nada de lo ya existente cambia; `[subagents] enabled = true` la activa.

## Criterios de éxito

- **SC-001** Las cuatro puertas de calidad y `pytest tests/architecture` en exit 0; 100 % de líneas y ramas en los módulos nuevos.
- **SC-002** Diff vacío de los archivos protegidos.
- **SC-003** Un valor centinela puesto en el historial del orquestador aparece **0** veces en las peticiones del subagente al proveedor, y otro puesto en la conversación del subagente aparece **0** veces en las peticiones posteriores del orquestador.
- **SC-004** Ninguna clave aparece en el resultado de `delegar` ni en lo que se guarda en disco (la sesión hija y sus eventos); los eventos en memoria no se redactan, como ya ocurre con los del orquestador.
- **SC-005** Con la configuración por defecto la suite existente no cambia: de ella solo se ajusta el conjunto de nombres públicos de `adapters.tools` (una prueba).

## Casos límite

- El subagente responde texto que no es JSON, un JSON con claves de más o de otro tipo → `resultado_no_valido`, sin copiar lo recibido.
- El subagente llama a una herramienta que la política deniega o que necesita aprobación sin aprobador → recibe el mismo rechazo que recibiría el orquestador.
- La sesión padre no existe o la base falla al crear la hija → `sin_sesion_hija`, no se llama al proveedor.
- Cancelación (Ctrl-C) durante el subagente → se propaga; el bucle del hijo publica `interrupted` en su sesión.
- Dos delegaciones seguidas → cada una crea su sesión y su contador.
- `delegar` con `objetivo` vacío o argumentos de más → el bucle responde `[invalid_arguments]` antes de crear nada.
