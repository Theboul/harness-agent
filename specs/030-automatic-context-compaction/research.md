# Research: HU-02-03 — Compactación automática por umbral

Cada decisión sigue el formato Decisión / Razón / Alternativas. No quedan marcadores sin resolver: Q1, Q2 y Q3 están resueltas en *Clarifications*.

## R1 — Dónde corre la compactación y qué estima (Q1 = A; restricción 2)

**Decisión**: un `ContextCompactor` puro en `core/context/` se invoca desde la capa de composición (`bootstrap.run_session`) **antes de entregar cada petición de la persona** al bucle, igual que `VerifyingRunner` (HU-11-04.1) envuelve el turno sin tocarlo. No se invoca dentro de las rondas de corrección del verificador: «turno» es el inicio de una petición.

**Comprobación** (restricción 2): `ContextAssembler` **no está cableado** en ningún sitio (`grep` sobre `src/`: solo se define y exporta; ni `bootstrap.py` ni `core/loop.py` lo usan). Cablearlo exigiría tocar `core/loop.py`. Por eso la estimación usa las funciones **puras** del estimador: `estimate_messages(historial) + Σ estimate_tool_definition(definición)`, con las definiciones que entrega la composición (las mismas que arma el bucle). La estimación es **cruda** (sin el factor de calibración por sesión, que vive en el ensamblador); el umbral del 80 % deja holgura.

**Observación para A y HU-02-06.1**: el ensamblador (prefijo congelado, calibración, bloque esencial como segundo mensaje `SYSTEM`) sigue sin integrarse al bucle; cuando se integre, la estimación de esta historia debería pasar a `AssembledContext.estimated_tokens`. Limitación conocida de Q1: una tarea larga puede crecer por encima del umbral entre dos peticiones; el gancho en el bucle (opción B) es una mejora futura con acuerdo de A.

**Alternativas**: gancho en `core/loop.py` (descartado por Q1); cablear el ensamblador (toca el bucle).

## R2 — Qué es «lo protegido» y cómo se parte el historial

**Decisión**: el historial en memoria que se entrega al bucle se parte en cuatro zonas, en este orden: (1) **cabeza protegida**: los mensajes `SYSTEM` iniciales (hoy el aviso de entorno, las instrucciones de git y el aviso de comandos de la tarea; mañana el bloque esencial de HU-02-06.1, que será otro `SYSTEM` del prefijo) y el **primer mensaje `USER` no externo** (la petición inicial); (2) el **resumen anterior**, si lo hay (un mensaje `USER` externo con la cabecera fija); (3) la **región antigua** (todo lo que sigue hasta el corte); (4) la **ventana reciente**. Solo la región antigua y el resumen anterior se resumen; la cabeza y la ventana reciente no se tocan.

**Razón**: `core/loop.py` (`_check_history`) solo admite `SYSTEM` como prefijo contiguo, así que el resumen **no puede ser `SYSTEM`** tras la petición inicial: es un `USER` con `is_external=True` (R7). La petición inicial se protege porque, sin HU-02-06.1, es donde vive hoy el enunciado de la tarea.

## R3 — Ventana reciente y corte seguro

**Decisión**: `choose_cut` parte del final: acumula mensajes mientras su estimación sume como mucho el **30 % del umbral** (por defecto) y siempre al menos `min_recent_messages` (4); el corte deseado es `len(historial) - n`. Después **retrocede** mientras `historial[corte]` sea un resultado de herramienta (`Role.TOOL`), de modo que la llamada del asistente y todos sus resultados queden juntos del lado reciente (regla de SPK-03 §4; igual que `safe_cut` del spike). Retroceder solo alarga la ventana reciente: los recientes quedan íntegros. Si el corte no deja nada por resumir (`corte ≤ inicio de la región`), no hay compactación.

**Alternativas**: avanzar el corte (separaría llamada y resultado o resumiría una llamada sin su resultado); cortar por número fijo de mensajes (ignora el tamaño).

## R4 — Cómo se enlazan los mensajes en memoria con los eventos guardados (AC-02, flujo 3)

**Problema**: el historial en memoria no lleva identificadores de evento y la tabla `events` guarda también eventos que no son mensajes (permisos, aprobaciones, `tool_requested`…).

**Decisión**: el adaptador entrega la lista ordenada de los **eventos de mensaje** de la sesión (`user_message` → `user`, `assistant_message` → `assistant`, `tool_finished` → `tool`), cada uno con su `seq` y si ya está cubierto (`compacted_by` no nulo). El compactador deriva del historial los **eventos que cada mensaje real debe haber producido**: un `USER` real siempre (`user`), un `ASSISTANT` **solo si tiene contenido** (el bucle publica `assistant_message` únicamente `if response.content`, así que un mensaje del asistente que solo pide herramientas **no tiene evento**) y un `TOOL` siempre (`tool`). «Real» es todo mensaje que no es `SYSTEM` ni `USER` externo (ni el resumen ni el mensaje de salida del verificador, que no tienen evento). Exige que esa secuencia de tipos coincida uno a uno, en orden, con los eventos de mensaje **no cubiertos**; si no coincide, **falla cerrado**: no se compacta y se informa (R9). Con esa correspondencia, `through_seq` es el `seq` del **último mensaje con evento de la región antigua** (inclusivo). El evento de la **petición inicial** (el primer evento de mensaje de la sesión) nunca se marca.

**Qué se marca**: todos los eventos de la sesión con `seq` mayor que el de la petición inicial y **menor o igual** que `through_seq`, que aún no estén cubiertos y que no sean `context_compacted`. `evento_desde` y `evento_hasta` son el mínimo y el máximo `seq` marcados; `eventos` es la cuenta. Los eventos que no son de mensaje y quedan después de `through_seq` (por ejemplo los `tool_requested` de una llamada que está en la ventana reciente) **no** se marcan. Sin filas que marcar, no se hace nada (idempotencia).

**Corrección del análisis (2026-10-27)**: una versión anterior de esta decisión suponía un evento por cada mensaje del asistente y un límite exclusivo del primer mensaje reciente; con mensajes del asistente sin contenido habría fallado cerrado en casi todas las sesiones reales. Ver el ejemplo E5 de `contracts/store_protocol.md`.

**Alternativas**: añadir un identificador de evento a `Message` (cambia `core/entities.py`, contrato compartido); marcar por tiempo (no es exacto); guardar en memoria una lista paralela (se pierde al reanudar).

## R5 — Resolver que `context_compacted` no se guarde dos veces (restricción 4)

**Problema**: `attach_event_recorder` suscribe `store.save_event` a **todos** los tipos de evento; si el adaptador escribe la fila de `context_compacted` dentro de su transacción y el compactador además publica el evento en el bus, el registrador intentaría guardarlo otra vez.

**Decisión** (la más simple que lo garantiza): el adaptador escribe la fila **dentro de la transacción única** (resumen + marcas + evento) y devuelve el `Event`; el compactador lo publica en el bus **después** del `COMMIT` para los demás suscriptores. `attach_event_recorder` gana un parámetro opcional `skip: Collection[EventType] = ()` (aditivo; sin él se comporta igual) y `compose()` lo llama con `skip=(EventType.CONTEXT_COMPACTED,)`: el registrador no guarda ese tipo porque ya lo guardó el adaptador. El parámetro es posicional o por nombre y `compose()` lo pasa **de forma posicional**: la prueba existente `tests/unit/test_bootstrap_compose.py` sustituye el registrador por `failing_recorder(*_args)`, que no acepta nombres. No cambia `SessionStore` ni el puerto del bus.

**Por qué es seguro**: la clave primaria `events.id` hace que, aunque alguien olvide el `skip`, el segundo intento **falle de forma visible** (`DuplicateEvent`) en lugar de duplicar la fila: «exactamente una fila» lo garantiza el esquema. Pruebas: una de **duplicado** (compactar con el registrador activado con y sin `skip` deja una sola fila; sin `skip` falla ruidosamente) y una de **rollback** (un fallo inyectado en el `INSERT` del evento, en el `UPDATE` de las marcas o en el del resumen no deja resumen, ni marcas, ni evento).

**Alternativas**: (a) que el registrador ignore `DuplicateEvent` (cambia su semántica para todos los eventos y esconde errores reales); (b) no publicar el evento en el bus (los demás suscriptores no lo verían); (c) guardar el evento solo por el registrador (rompe la transacción única).

## R6 — Esquema v3 aditivo (Q2 = B)

**Decisión**: `SCHEMA_VERSION` pasa de 2 a 3; el paso `_V3` crea la tabla `resumenes` (columnas en `data-model.md`) y un índice, y **no toca** `events` (la columna `compacted_by` ya existe desde la versión 1) ni `criterios*`. La migración corre en una transacción, igual que las anteriores (`_script`): una base en el esquema 1 o 2 pasa a 3 sin perder filas. Se prueba con bases reales creadas con el esquema anterior en `tmp_path` (el SQL literal de las versiones 1 y 2, como ya hace `test_schema_migration.py`), con datos (sesiones, eventos, criterios) y comparando todas las filas antes y después.

**Pruebas existentes que cambian** (solo las que fijan la versión o el conjunto exacto de tablas): en `tests/unit/adapters/storage/test_schema_migration.py`, las aserciones `SCHEMA_VERSION == 2` (línea 84) y `user_version == 2` (líneas 90 y 124) pasan a 3, y la prueba de «versión desconocida» (línea 158, que pone `user_version = 3`) pasa a 4; en `tests/unit/adapters/storage/test_schema.py`, `SCHEMA_VERSION == 2` (línea 46) pasa a 3; y en `tests/integration/test_rejection_reason_agent_loop.py` (~línea 296) el conjunto exacto de tablas gana `"resumenes"`. Estas dos últimas **no estaban en la versión anterior del plan**; las halló el análisis. Ninguna otra.

## R7 — El resumen vuelve como contenido externo, enmarcado y limpio

**Decisión**: el texto devuelto por el proveedor se **limpia** (se quitan caracteres de control y de formato salvo el salto de línea) y se le **ocultan las credenciales de URLs** con `hide_url_credentials` (lineal tras el arreglo de `fix/redaction-linear`); **eso** es lo que se guarda en `resumenes.texto` y lo que entra al contexto. En el contexto va como `Message(Role.USER, marco + texto, is_external=True)` con la cabecera fija de `contracts/summary_prompt.md`. Se rechaza (sin cambios) si supera el tope (`2 × summary_tokens` estimados) o si queda vacío. **Orden**: primero se rechaza el texto **bruto** que supere el tope en caracteres (16 000 con el valor por defecto), de modo que la limpieza y el ocultado de credenciales nunca reciben más de ese tamaño y la historia no depende del coste de `hide_url_credentials`; después se limpia y se comprueba que no quede vacío.

**Razón**: el resumen deriva de salidas de comandos y archivos que no son de confianza; si volviera como mensaje de sistema sin marcar, una instrucción inyectada quedaría «lavada». Que no pueda ser `SYSTEM` (R2) refuerza la decisión.

## R8 — Qué entra a la llamada de resumen

**Decisión**: una llamada aparte `provider.complete(mensajes)` **sin herramientas** (`tools` ausente) con dos mensajes: uno `SYSTEM` con el prompt fijo y uno `USER` con (a) el **resumen anterior** sin su marco, si lo hay, y (b) la **transcripción** de la región antigua. La transcripción es **texto plano** (no mensajes con estructura de herramientas): cada mensaje en una línea etiquetada, los resultados de herramientas recortados a 500 caracteres y marcados como externos, las llamadas con solo el nombre de la herramienta. Nunca entran la cabeza protegida, los criterios ni la ventana reciente.

**Razón**: enviar los mensajes con sus `tool_calls` exigiría declarar las herramientas (algunos proveedores lo piden) y complicaría la conversión; el texto plano es lo que SPK-03 simuló. La región antigua cabe en la ventana porque el contexto total superó el 80 % de ella, no el 100 %.

## R9 — Fallos y advertencia

**Decisión**: cualquier `Exception` de la llamada, de la validación, de la correspondencia con los eventos o del guardado deja **todo como estaba** (el historial en memoria no se toca hasta que el guardado confirma; el adaptador hace `ROLLBACK`), el turno continúa sin compactar y se publica `provider_error` con la forma existente y contenido fijo: `{"reason": "compaction_failed", "error_type": "CompactionFailed", "message": "No se pudo compactar el contexto; el turno continúa sin compactar."}`. Nunca lleva texto de la excepción ni del historial. `asyncio.CancelledError` **nunca se captura**. La CLI ya muestra un `provider_error` de causa desconocida con su línea genérica.

**Advertencia**: si tras compactar la estimación sigue por encima del umbral, el compactador llama a un `warn(texto)` inyectado (la composición lo escribe como aviso en la terminal, igual que los avisos de arranque) con un texto fijo y sin reintentar. No se crea ningún evento nuevo.

**Orden de los pasos** (sin `await` entre el guardado y la actualización): llamada de resumen → validación → `commit` del adaptador → reemplazo del historial en memoria → publicación del evento. Un fallo del bus al publicar el evento **después** del `COMMIT` no es un fallo de compactación: se trata en R16.

## R10 — Umbral por modelo y configuración (Q3 = A)

**Decisión**: `core/context/settings.py` define `ContextSettings` (inmutable, con validación) y `threshold_tokens(settings, model)` = `ventana(model) × threshold_percent // 100`, donde `ventana(model)` es la del modelo en `windows` o, si no está, `window_tokens`. El modelo en uso se lee en cada turno de un `Callable[[], str]` inyectado, de modo que si cambia (HU-07-05) el umbral se recalcula (V-10). `config.py` gana la sección opcional `[context]` (campos y rangos en `contracts/context_settings.md`) con `_check_context` al estilo de `_check_limits`; un valor inválido produce un `ConfigProblem` con el **nombre** del campo (nunca el valor) y detiene el arranque. `config.example.toml` lleva la sección comentada.

**Límite conocido**: los nombres de modelo de `[context.windows]` pasan por la comprobación de «nombre con aspecto de clave» de `config.py`; un nombre de modelo que contuviera `key`, `token` o similares se rechazaría como posible secreto (no ocurre con los modelos admitidos).

**Pruebas de configuración existentes que cambian**: ninguna prevista; `HarnessConfig` gana un campo con valor por defecto (`context`) al final y `_TABLE_FIELDS` gana `context`. Si alguna prueba que fija la lista de tablas o de campos fallara, el único ajuste permitido es esa lista.

## R11 — Cómo se actualiza el historial en memoria sin romper la reanudación futura (restricción 8)

**Decisión**: el historial que `run_session` entrega al bucle es una **vista en memoria**; compactar la reemplaza **in situ** (`history[:] = nuevo`) tras confirmar el guardado. El historial **original** vive en SQLite y no se toca: los eventos siguen completos (`load_session` los devuelve todos, con las mismas filas), los cubiertos llevan `compacted_by` y el texto del resumen está en `resumenes`. HU-03-04 reconstruirá desde los eventos y, si hace falta, aplicará el último resumen guardado; por eso el resumen se guarda **ya limpio** y con su rango. No se necesita nada más ahora (no se añade un método de lectura: lo pondrá HU-03-04).

**Alternativas**: guardar la vista compactada (pierde el original); reescribir los eventos (viola la regla 1).

## R12 — Qué toca en `bootstrap.py` (área C)

**Decisión mínima**: (1) crear `SqliteCompactionArchive` sobre el almacén de sesiones; (2) construir el `ContextCompactor` con el proveedor, el archivo, la configuración `config.context`, el modelo (`config.model`), las definiciones de herramientas (el registro), un `emit` que fabrica el `Event` con el reloj y los identificadores inyectados, `bus.emit` para el evento de resumen y un `warn`; (3) `attach_event_recorder(bus, store, skip=(CONTEXT_COMPACTED,))`; (4) `Composition` gana el campo `compactor` (con valor por defecto); (5) `run_session` llama a `compactor.before_turn(history)` antes de cada petición. Sin tarea y con tarea funciona igual. Visto bueno de C (H2).

## R13 — Pruebas y sesión larga simulada (restricción 10)

**Decisión**: todo con `FakeProvider` (sin red). `tests/spikes/compaction_sim.py` es código de pruebas y **no** puede importarse desde `src/`; las pruebas de esta historia (en `tests/`) construyen su propia sesión larga con una función pequeña en el archivo de prueba (patrón `build_long_session` del spike: mensajes con centinelas únicos y llamadas de herramienta con sus resultados), sin importar el spike. Pruebas al azar con semilla fija **20261031** sobre el corte seguro (nunca deja un resultado de herramienta huérfano, respeta el mínimo de recientes, es determinista) y sobre la composición del contexto (orden y contenido). El adaptador se prueba con bases reales en `tmp_path`.

## R14 — Guardas de arquitectura

**Decisión**: `core/context/` ya tiene `test_context_boundaries.py` (stdlib y núcleo, sin E/S, sin terminal ni entorno), que cubre los módulos nuevos sin cambios. Se añade `tests/architecture/test_compaction_boundaries.py`: el compactador no captura `BaseException` ni `CancelledError`; la única llamada a `complete` del paquete va sin herramientas; los módulos puros de corte y composición no tienen `raise`; ningún módulo del paquete importa el bucle ni `adapters`; el adaptador `compaction_archive.py` no importa el bucle y no define el puerto `SessionStore`.

## R15 — Hallazgos para otras áreas (sin cambiarlas aquí)

- **A (HU-01-06)**: la llamada de resumen consume tokens del proveedor y **no cuenta** en `max_tokens` ni en los turnos (el contador vive en el bucle).
- **A y B (HU-02-01, HU-02-06.1)**: el ensamblador sigue sin integrarse; la estimación usa las funciones puras sin calibración.
- **A (HU-03-04)**: las marcas, `resumenes` y el esquema 3 son la base para reconstruir al reanudar; la reanudación debe usar el historial completo (regla de HU-03-04) y aplicar el último resumen solo si compacta.
- **B**: `SessionStore` y `ContextManager` no cambian; el reajuste de los puertos (SPK-03 §6) queda para un acuerdo posterior de A, B y C.
- **Mejora futura**: gancho en el bucle antes de cada llamada al modelo (Q1, opción B) con el acuerdo de A.

## R16 — Fallo al publicar el evento después del `COMMIT` (no es un fallo de compactación)

**Decisión**: el orden es llamada de resumen → validación → `commit` del adaptador → reemplazo de la vista en memoria → publicación del evento. Entre el `commit` y el reemplazo de la vista **no hay ningún `await`**, así que una cancelación no puede dejar el estado guardado y la vista desalineados. Si `publish(evento)` lanza una excepción ordinaria (por ejemplo `EventDeliveryError` de un suscriptor), **no** se deshace nada (ya está guardado y la vista ya está compactada), **no** se reintenta, **no** se publica `provider_error`, el turno continúa con la vista compactada y se informa por el `warn` inyectado con este texto fijo, sin el texto del resumen ni el mensaje de la excepción:

```text
Aviso: la compactación se guardó, pero no se pudo avisar a todos los suscriptores del evento; el turno continúa con el contexto compactado.
```

`asyncio.CancelledError` durante la llamada de resumen **se propaga** y no deja nada parcial (no hubo `commit` ni cambio de la vista); durante `publish` también se propaga.

**Prueba**: composición **sin `skip` a propósito** (un suscriptor que guarda `context_compacted` con `store.save_event`): el segundo guardado falla con `DuplicateEvent`, que el bus entrega como `EventDeliveryError`; resultado: exactamente una fila de `context_compacted` en `events`, la vista compactada, el `warn` emitido y el turno que sigue. Prueba unitaria equivalente con un `publish` que lanza.

**Razón**: la compactación ya terminó y es válida; tratar un suscriptor roto como un fallo de compactación haría creer que no se compactó cuando sí.

## R17 — El adaptador usa la conexión del almacén

**Decisión**: `SqliteCompactionArchive` recibe el `SqliteSessionStore` y usa `store.connection()` (patrón de `SqliteTaskStore`, HU-11-01); **nunca** abre otra conexión (no llama a `sqlite3.connect`). Así no compite por el bloqueo de escritura con `save_event`, que usa la misma conexión y el mismo `BEGIN IMMEDIATE`.

**Prueba** con un archivo real en `tmp_path`: guardar eventos con `save_event`, compactar con el adaptador y seguir guardando en la misma base sin bloqueos ni errores; una segunda conexión de solo lectura abierta por la prueba lee el resultado tras el `COMMIT`; con `sqlite3.connect` sustituido por una función que falla, las operaciones del adaptador siguen funcionando (no la llaman).

## R18 — Pruebas de `[context.windows]` con nombres reales de modelo

**Decisión**: además de los rangos de `contracts/context_settings.md`, se prueba con una clave entrecomillada con `/` y `.` (por ejemplo `"proveedor/modelo-1.5" = 128000`), que se acepta y se usa en `window_for`; los valores inválidos **por modelo** (`0`, un negativo, un booleano y un texto) producen el problema `context.windows` con el mensaje fijo y **nunca** repiten el valor ni el nombre del modelo; y se fija el límite conocido de R10 con una prueba (un nombre de modelo cuyo último fragmento parezca una clave se rechaza como posible secreto, como ya hace `config.py` con cualquier nombre).
