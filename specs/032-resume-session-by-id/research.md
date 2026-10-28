# Research: HU-03-04 — Reanudar una sesión por identificador

Todas las decisiones salen de leer el código real (2026-10-27, rama `gustavo` alineada con `main` tras HU-02-06.1). No quedan `NEEDS CLARIFICATION`. **Ninguna decisión obliga a tocar** `core/loop.py`, `core/interfaces/`, el catálogo de eventos, `core/redaction.py`, `core/verification/` ni la lógica de `ContextCompactor`, `split_history` y del renovador del bloque esencial; el cambio mínimo de `cli/app.py` (área C) y el cableado de `bootstrap.py` van a visto bueno de C (H3). Los hallazgos que **corrigen o precisan la spec** están al final (R20) y ya se aplicaron a `spec.md` con un script.

## R1 — Verificación del hallazgo: los eventos no bastan (confirmado)

Leído `core/loop.py` (solo lectura) y el registrador:

| Mensaje en memoria | Cuándo se añade al historial y qué evento sigue | Qué lleva el evento |
|---|---|---|
| `USER` (petición) | se añade y **después** se publica `user_message` | `{content}` |
| `ASSISTANT` con texto | se añade y **después** `assistant_message` (solo si hay texto) | `{content, tool_call_count, final}` |
| `ASSISTANT` solo con llamadas, o vacío | se añade; **no hay evento** | — |
| `TOOL` (por cada llamada) | el resultado se añade y **después** `tool_finished` | `{call_id, name, is_error, category}` |
| (antes de ejecutar) | `tool_requested`, `permission_decided`, `approval_requested/resolved` | solo `call_id`, `name`, riesgo, decisión; **sin argumentos** |

Confirmado: no se puede reconstruir (a) las llamadas con argumentos, (b) el contenido de los resultados, (c) `is_external`, (d) `usage`, (e) los mensajes sin evento, (f) el mensaje de rechazo con su texto. Además el estado de la sesión **nunca cambia** (ningún `UPDATE sessions`): toda sesión queda «activa». El evento de interrupción sí existe.

**Decisión**: Q1 = B (ya tomada): tabla propia de mensajes alimentada desde la composición. Este plan solo la hace concreta.

## R2 — Relación de cada mensaje con su evento: el identificador del evento, no el orden

**Problema**: el compactador empareja mensajes y eventos **por orden y tipo** (`_pair_events`). Si la tabla de mensajes se emparejara igual con una cuenta de ordinales, un corte entre el guardado de un mensaje y el de su evento desplazaría todos los emparejamientos siguientes.

**Decisión**: cada fila lleva `evento_id` = identificador del evento que la disparó (`Event.id`, que existe **antes** de que el registrador lo guarde). Se rellena solo para los mensajes que tienen evento propio (petición, respuesta con texto, resultado de herramienta); queda `NULL` para la respuesta solo con llamadas y la vacía. La lectura une `mensajes.evento_id = events.id`:

- fila con evento guardado → su `seq` y si está cubierto (`events.compacted_by IS NOT NULL`);
- fila con `evento_id` cuyo evento nunca se guardó (corte justo entre ambos guardados) → como «sin evento»: cola aceptable;
- evento de tipo mensaje (`user_message`, `assistant_message`, `tool_finished`) **sin fila** que lo apunte → falta detalle: sesión anterior a la historia o inconsistente.

**Alternativas**: emparejar por ordinal (frágil ante cortes, descartada); guardar el `seq` en la fila (no se conoce al guardar el mensaje: el mensaje se guarda **antes** que el evento, R4); un `UPDATE` posterior de la fila (dos escrituras, ventana de inconsistencia).

## R3 — Qué mensajes cubre un resumen (relación con los rangos de eventos)

Qué hace la compactación viva (`core/context/compactor.py`, `cut.py`): la vista pasa a `[prefijo, petición inicial, resumen, mensajes desde el corte]`; los eventos cubiertos reciben `compacted_by = <id del resumen>` en el almacén de compactación; el corte nunca separa una llamada de sus resultados; un resumen nuevo **sustituye** al anterior en la vista (resume el anterior más lo nuevo).

**Regla de cobertura de la tabla de mensajes** (pura, en el reconstructor):

1. La **petición inicial** es la fila de posición 1; nunca está cubierta (si lo está: inconsistente).
2. Una fila **con evento guardado** está cubierta si y solo si su evento tiene `compacted_by`.
3. Una fila **sin evento** (respuesta solo con llamadas, respuesta vacía, o con evento que nunca se guardó) **toma la cobertura de la siguiente fila con evento**; si no hay siguiente, no está cubierta.
4. Las filas cubiertas forman un bloque contiguo justo tras la petición inicial; si no (o hay filas cubiertas sin resumen, o un resumen sin filas cubiertas): inconsistente, falla cerrada.
5. El **resumen vigente** es la fila de `resumenes` con mayor `evento_hasta` (desempate: la última insertada). La vista es `[prefijo, petición inicial, frame_summary(texto), filas NO cubiertas…]`; sin resumen, `[prefijo, todas las filas…]`.

**Por qué la regla 3 es exacta casi siempre**: una respuesta solo con llamadas va siempre seguida de sus resultados (cada llamada se contesta antes de cualquier otro mensaje) y el corte retrocede para no separarla; por tanto cae en el mismo lado que su primer resultado. **Única divergencia conocida**: una **respuesta vacía** (sin texto ni llamadas, que el bucle admite) situada **exactamente justo antes del corte** estaba resumida en memoria, y la regla 3 la deja después del resumen (porque toma la cobertura del siguiente mensaje, que está en el lado reciente). Sin efecto: ese mensaje no tiene evento, así que no cuenta en el emparejamiento del compactador, y no lleva información. Se declara como excepción en la spec (R20) y se prueba.

**Alternativas**: (a) marcar la cobertura por identidad cuando el bus publica `context_compacted` leyendo la vista ya reemplazada (exacta, pero añade una segunda fuente de verdad que puede quedar a medias si falla el aviso o el proceso se corta entre el `COMMIT` y la publicación; además obliga a escribir en la tabla de mensajes desde un suscriptor más); (b) ampliar `commit_compaction` para marcar las filas (necesita el índice del corte, que el protocolo no entrega; cambiaría el protocolo de HU-02-03); (c) no guardar las respuestas vacías (cambia la igualdad con memoria en todos los casos). Se descartan por coste/riesgo frente a una divergencia sin consecuencias.

## R4 — Orden de suscripción y entrega del bus (verificado)

`InMemoryEventBus.emit` (leído completo): llama a los manejadores del **tipo exacto del evento**, **en el orden en que se suscribieron**, de forma síncrona; si uno lanza una excepción ordinaria, **los demás siguen recibiendo el evento** y al final `emit` lanza `EventDeliveryError` con todas las excepciones; `CancelledError`/`KeyboardInterrupt` se propagan de inmediato (con nota de los fallos previos). El bucle no captura lo que sale de `emit` (Q4 del bucle): llega a `run_turn`, a `run_session` y a `run_cli`, que escribe una línea con el nombre del tipo (`turn_failure_line`) y termina con código 1.

Quién suscribe y cuándo (`bootstrap.compose`): `attach_event_recorder(bus, store, (CONTEXT_COMPACTED,))` se llama dentro de `compose`, **antes** de crear el bucle, el compactador y la sesión interactiva; el renderizador de la CLI (`attach_renderer`) y el tablero de criterios se suscriben dentro de `run_cli`/`run_session`, **después**.

**Decisión**: el guardado de mensajes se suscribe en `compose` **justo antes** de `attach_event_recorder`, para los cuatro tipos que dispara (`user_message`, `assistant_message`, `tool_requested`, `tool_finished`). Resultado: para cada evento el orden de entrega es **guardar mensaje → guardar evento → CLI**. FR-034: un corte entre ambos deja un mensaje sin evento (cola aceptable), nunca un evento sin mensaje. Se prueba con dos dobles que registran el orden de llamada.

**Si el guardado del mensaje falla**: el registrador y la CLI **siguen recibiendo el evento** (el bus no corta) y después `emit` lanza `EventDeliveryError`. Ver R7.

**El guardado es inerte hasta que se enlaza**: muchas pruebas existentes llaman a `composition.loop.run_turn(history=[])` directamente; los eventos llegan al guardado antes de que `run_session` le entregue el historial. Hasta `bind(history, …)` el guardado **ignora** los eventos (no hay historial que leer). Una prueba de arranque comprueba que `run_session` lo enlaza.

## R5 — Captura: qué dispara qué y cómo se siguen los mensajes por identidad

**Disparadores** (los cuatro eventos de R1): en cada uno, el guardado lee el historial en memoria y guarda lo **pendiente**:

- pendiente = los mensajes **reales** (`is_real`: ni `SYSTEM` ni `USER` externo, es decir, ni prefijo, ni bloque, ni resumen, ni salida del verificador) que están **después del último mensaje guardado**, localizado por **identidad** (`is`), no por posición ni por igualdad (dos mensajes iguales son mensajes distintos);
- `user_message` → guarda pendientes; el último (que debe ser el `USER` de la petición) lleva el `evento_id`;
- `assistant_message` → igual con el `ASSISTANT` con texto;
- `tool_requested` → guarda todos los pendientes **sin** `evento_id` (cubre la respuesta solo con llamadas, que no tiene evento);
- `tool_finished` → guarda hasta el pendiente cuyo `ToolResult.call_id` es el `call_id` del evento, y ese lleva el `evento_id`;
- al **cerrar cada turno** (en `run_session`, con `finally`) → guarda lo que quede sin `evento_id` (respuesta final vacía, o mensajes de un turno cortado por un error del proveedor).

**Compactación**: reemplaza la vista en memoria in situ (`history[:] = …`), pero el último mensaje guardado sigue en la vista (la ventana reciente nunca baja de 4 mensajes y siempre incluye el final) y la compactación ocurre antes del turno, con todo ya guardado. Si el último guardado no aparece en el historial → inconsistencia: error fijo (no se adivina).

**Mensajes que nunca se guardan**: prefijo y bloque (`SYSTEM`), resumen y salida del verificador (`USER` externos): los excluye `is_real`. Además las **composiciones con tarea no instalan el guardado** (Q3 = A: esas sesiones no se reanudan, así que no hay motivo para escribir más datos en disco).

**Posición**: contador por sesión que empieza en `última posición guardada + 1` (consulta al enlazar).

## R6 — Reconocer un rechazo sin tocar el bucle (señal fiable verificada)

Código real: todo resultado fabricado por el bucle pasa por `_rejection(call, category, content)` y su `category` viaja en `tool_finished`. Las categorías posibles son `unknown_tool`, `invalid_arguments`, `permission_denied`, `approval_required_unavailable`, `approval_failed`, **`approval_rejected`** (solo desde `_ask_approval`) y las de ejecución (`tool_exception`, `invalid_tool_result`, `tool_error`, `ok`). **Una herramienta no puede fijar la categoría** (la fija el bucle). Solo `approval_rejected` lleva el motivo de la persona (`approval_failed` nunca).

**Decisión**: al guardar el mensaje de un `tool_finished` con `category == "approval_rejected"`, el contenido se **sustituye** por `rejection_message(name, None)` (el texto estándar de HU-05-03: `[approval_rejected] Tool '<name>' was rejected by the user.`), con `name` del payload. El motivo **nunca** llega a la función de guardado. Señal única: la categoría (contrato del payload del bucle). Se guarda con una prueba de contrato: si alguien cambia la categoría, falla.

**Aviso honesto**: si el **modelo** repite el motivo en una respuesta posterior, ese texto es salida del modelo y sí se guarda; no es el motivo «filtrado» por esta historia. Se documenta.

**Alternativas**: reconocer el prefijo `[approval_rejected]` del contenido (un archivo que lo cite lo corrompería) o escuchar `approval_resolved` (más piezas, misma información). No hace falta tocar el bucle: **hay señal fiable**.

## R7 — Fallo al guardar un mensaje: no es silencioso

**Decisión (la más conservadora)**: el guardado captura cualquier fallo del almacén o de la serialización, escribe **un mensaje fijo** por el `WarningSink` de la composición y lanza `ConversationSaveError` (mensaje fijo, sin contenido ni texto de la excepción original, sin `__cause__`). Por R4, `emit` lo agrupa en `EventDeliveryError` y el turno **falla**: `run_cli` escribe la línea con el tipo y termina con código 1 (igual que un fallo del registrador de eventos). Mensaje: «No se pudo guardar un mensaje de la conversación; la sesión no podrá reanudarse.»

**Consecuencia consistente**: como el registrador sí guardó el evento, la sesión queda con un evento de mensaje sin fila → la lectura la clasifica como «sin detalle» (FR-009) y se rechaza al reanudar con un mensaje claro. Nunca se reconstruye mal sin que nadie lo sepa.

**Alternativas**: continuar con solo un aviso (la sesión seguiría y se perdería el rastro del fallo); marcar la sesión como no reanudable en otra tabla (más piezas, más escrituras que pueden fallar). Se descartan.

**Cancelación**: el guardado no captura `BaseException`; el vaciado del cierre de turno es el único que corre durante una excepción: si él mismo falla, escribe el aviso fijo y la excepción original sigue su camino.

## R8 — Seguridad: redacción, tamaño, protección de la base

- **Redacción**: todo lo que se guarda pasa por `hide_url_credentials` (el contenido de cada mensaje, el contenido del resultado y **cada valor de texto de los argumentos**, recursivamente). No se aplica otra limpieza (no se quitan caracteres ocultos: se guarda lo que el modelo vio). **Consecuencia**: lo reconstruido difiere de la memoria solo si el original llevaba una credencial de URL (excepción declarada).
- **Tamaño**: los resultados de herramientas ya vienen recortados por el límite existente (`limits.max_tool_output_chars`, 24 000 por defecto); los argumentos y los textos de la persona y del asistente no tienen tope propio. No se añade un tope nuevo (decisión del PO, H4).
- **Secretos que no son URLs**: HU-10-02 (redacción general) no existe; un archivo leído con una clave queda en disco, igual que ya llega al proveedor del modelo. Es decisión del PO (H4) y queda como riesgo explícito. V-13 se cumple solo en parte (ver *Complexity Tracking*).
- **El modelo no puede leer ni editar la tabla**: la base ya está protegida por `ProtectedPolicy` (la carpeta de la base y, si contiene al área de trabajo, la base y `tareas/`; coincidencia literal del comando del shell). Se añade una prueba de que `leer_archivo`, `escribir_archivo`, `buscar_texto`, `listar_archivos` y el shell no pueden alcanzar la base ni la tabla nueva, y de que ninguna declaración de herramienta nombra `mensajes`.
- **Centinelas**: el texto de los mensajes y el identificador no aparecen en eventos, errores, avisos ni terminal por esta historia.

## R9 — Reconstrucción: función pura y estructura del resultado

Entrada (`StoredConversation`, leída por el adaptador): sesión, modelo guardado, si es de tarea, filas ordenadas con su cobertura, texto del resumen vigente, cuántos eventos de mensaje no tienen fila, tipo del último evento.

Pasos (`rebuild_conversation`): (1) validar la petición inicial (fila 1, `USER` no externo); (2) calcular cobertura (R3); (3) armar `[prefijo, petición, resumen?, filas no cubiertas]`; (4) cerrar llamadas sin resultado **solo en la cola** (R10); (5) validar la estructura con una función propia que **replica** la del bucle (SYSTEM solo al principio; identificadores de llamada no vacíos y únicos; cada grupo contestado por completo antes de otro mensaje; ningún resultado sin llamada). **Se replica, no se importa**: `AgentLoop._check_history` es privado y `core/context/` no puede importar el bucle (guarda existente). Una prueba compara ambas sobre un conjunto de historiales válidos e inválidos.

Cualquier incoherencia (primera fila que no es la petición, filas cubiertas sin resumen, resultado huérfano, llamada sin resultado **en medio**, rol desconocido) → `ConversationInconsistent` (mensaje fijo).

## R10 — Contradicción hallada: el cierre sintético debe PERSISTIRSE al continuar

**Hallazgo**: un resultado sintético solo en memoria (FR-019 tal como estaba) es un mensaje `TOOL` **sin evento**. El compactador de HU-02-03 exige que los mensajes reales de la vista y los eventos no cubiertos coincidan uno a uno por orden y tipo; ese `TOOL` extra rompe la coincidencia y la compactación **fallaría cerrada para siempre** en esa sesión (cada vez que el contexto superara el umbral, un `provider_error` y nada compactado), hasta desbordar la ventana. No se puede arreglar sin tocar el compactador (prohibido).

**Decisión (la más conservadora)**: la reconstrucción sigue siendo lectura pura y entrega los resultados sintéticos en la vista. **En la primera petición después de reanudar**, antes de compactar y de llamar al bucle, la composición publica por cada llamada cerrada un evento **`tool_finished`** (tipo existente) con `{call_id, name, is_error: true, category: "tool_interrupted"}`. El guardado de mensajes lo recoge como a cualquier resultado (queda en la tabla con su `evento_id`) y el registrador guarda el evento. Resultado: la historia guardada queda coherente y la compactación posterior funciona; reanudar de nuevo ya no encuentra llamadas sin resultado.

- **No se pierde la propiedad «reanudar no escribe»**: el comando no escribe nada; las escrituras ocurren al **continuar** (si la persona sale sin escribir, nada cambia). Solo se **añade**: no se modifica ni se borra nada.
- **Coherente con V-11**: «devuelve el resultado correspondiente al modelo en el siguiente turno».
- **Efecto visible**: la CLI pinta los `tool_finished`; para la categoría nueva mostrará la línea genérica de error desconocido (mejorar su texto es del área C, aviso H8).
- **Texto fijo del resultado** (contrato): `[tool_interrupted] La ejecución se interrumpió antes de obtener el resultado; verifique el estado antes de repetirla.` con el mismo identificador de llamada y `is_error = true`, `is_external = false`.
- Si la publicación falla, es un fallo de entrega normal (el turno falla con código 1).

**Alternativas**: (a) no persistir y aceptar la compactación rota (rechazada: degradación silenciosa); (b) tocar `_pair_events` para tolerar mensajes sin evento (prohibido); (c) escribir el cierre en el comando (rechazada: el comando dejaría de ser de solo lectura y saldría escritura aunque la persona no continúe).

## R11 — Detección de sesión de tarea, anterior a la historia y vacía

Consultas del adaptador (existencia, sin leer valores, sin verificar sellos ni publicar eventos):

- **Tarea**: existe alguna fila en `criterios` o en `contexto_esencial` de esa sesión (también la fila huérfana de HU-02-06.1, que sí tiene criterios) → `TaskSessionNotResumable`.
- **Anterior a la historia / sin detalle**: `eventos de mensaje sin fila que los apunte > 0` → `SessionDetailMissing` (sesiones anteriores, o un guardado que falló, R7).
- **Vacía**: ningún evento de mensaje y ninguna fila → se reanuda como nueva, con aviso (FR-021).
- **Inexistente / inválido**: antes de consultar nada, el texto se valida (R13); si pasa y no hay sesión → `UnknownSession`.
- **Esquema desconocido**: `SqliteSessionStore` ya rechaza una base de una versión que no conoce al abrir (`SchemaVersionError`), antes de poder reanudar nada; no hay un caso propio.

## R12 — Cambiar de sesión sin tocar la lógica de HU-02-03 y HU-02-06.1

Qué está atado a la sesión al componer (leído): el compactador (`session_id` y el cierre `emit` de su `provider_error`) y, solo con tarea, el renovador del bloque y el ejecutor de rondas. El bucle recibe el identificador en **cada** `run_turn`; el almacén de compactación lo recibe en cada llamada; el registrador va por `event.session_id`.

**Opciones**: (A) componer de nuevo sobre el mismo almacén (duplicaría proveedor, política, herramientas, aprobador, **el registrador de eventos** —cada evento se guardaría dos veces— y los contadores de límites; el bus no permite darse de baja); (B) un titular mutable de sesión en `run_session` más una fábrica del compactador.

**Decisión**: B. `compose()` entrega, además, una **fábrica** `compactor_for(session_id)` que reutiliza `_compactor(...)` tal como está (sin cambiar su firma ni su lógica), y el guardado enlazable. `run_session` mantiene un titular `{session_id, compactor, cierres pendientes}` y `/reanudar` lo reemplaza **en sitio** junto con el contenido de la lista del historial (`history[:] = …`, la misma lista que ven el guardado y la sesión). La sesión que se abandona **queda tal cual**. Los contadores de límites (en el bucle) **no se reinician** (misma ejecución). Las composiciones con tarea no registran el comando.

**Si exigiera cambiar la firma o el comportamiento de HU-02-03/HU-02-06.1 habría que detenerse**: no lo exige.

## R13 — Validación del identificador y cambio mínimo de la CLI

**Identificador**: texto de 1 a 128 caracteres, solo letras ASCII, dígitos, `-`, `_` y `.` (los identificadores reales son UUID de 36; las pruebas usan otros). Vacío → línea de uso; cualquier otra cosa → «no es válido». Nada del texto se repite.

**CLI (cambio mínimo, área C)**: `run_cli` gana un parámetro opcional `argument_commands: Mapping[str, tuple[str, Callable[[str], str]]] | None = None` (nombre → descripción y función que recibe el texto tras el comando y devuelve la línea a escribir). Sin él, nada cambia. `/ayuda` lista estos comandos como los demás. No se cambia ningún otro comando, ni `ExtraCommands`, ni el render, ni `__all__`. Aproximadamente 12 líneas.

**Alternativa descartada**: que las funciones de `commands` acepten un argumento opcional (obliga a revisar `/criterios` y a inspeccionar firmas).

## R14 — Esquema 5 y corrida en seco

Versión 5, aditivo: tabla `mensajes` (ver `data-model.md`). Migración con el mismo patrón que 2, 3 y 4. **Corrida en seco** (esquema 5 provisional con la tabla y la versión; archivo restaurado y verificado con `cmp`): **23 fallos** y 6 933 pasadas (47 omitidas). Todas son pruebas de versión del esquema, de conjuntos de tablas o de volcados; detalle en `plan.md`. A esas se suma una de la API pública cuando se exporte el adaptador nuevo.

## R15 — Pruebas existentes: qué se revisó

Búsqueda en `tests/` de `SCHEMA_VERSION`, `user_version`, `sqlite_master`, `__all__`, bytes de la base, conteos de suscriptores, `/ayuda`, `run_session`, `attach_event_recorder` y comprobaciones de carga de eventos. Resultado: 24 pruebas cambian (23 + API pública). El resto se revisó y **se espera que pase sin tocar** (tabla en `plan.md`); si alguna falla, se detiene la implementación. Nota: la prueba de HU-05-04 que busca el motivo en **todos** los bytes llama al bucle directamente (sin `run_session`), así que no ejercita el guardado; la prueba nueva de seguridad (T010c) repite esa comprobación pasando por `run_session`.

## R16 — Prefijo, modelo y entorno

El prefijo de las sesiones sin tarea es el `history_prefix` de la composición actual (aviso de entorno y reglas de git). No se guarda su texto (para sesiones sin tarea no hay registro de instrucciones), así que **no se puede saber** si el entorno cambió: no se avisa. El modelo guardado de la sesión se compara con el configurado: si difiere, la línea de estado lo dice; el umbral y la compactación usan siempre el modelo en uso.

## R17 — Rendimiento y tamaño

Una lectura (`SELECT … LEFT JOIN events`) más tres consultas de existencia, todas por clave primaria o índice; la reconstrucción es lineal. Objetivo SC-007: 5 000 mensajes en menos de 5 s (se mide en la prueba con una base real en `tmp_path`; se espera del orden de décimas de segundo). Tamaño por mensaje: el texto + las llamadas en JSON; un resultado de herramienta ≤ 24 000 caracteres por defecto. No se añade índice más allá del de `evento_id` (la tabla se lee por la clave primaria `(sesion_id, posicion)`).

## R18 — Concurrencia

Dos procesos reanudando la misma sesión a la vez no se soportan (se intercalarían). El guardado no corrompe: la clave primaria `(sesion_id, posicion)` hace que el segundo escritor falle con el error fijo de guardado (R7) en lugar de sobrescribir; `append` es idempotente solo para la **misma** fila idéntica. Se documenta como riesgo.

## R19 — Guardado idempotente (un mensaje no se guarda dos veces)

En dos niveles: (1) el guardado sigue los mensajes por identidad y un mensaje ya guardado nunca vuelve a pendiente; (2) el almacén, al recibir una fila con una posición ya existente, la **ignora si es idéntica** (mismos valores) y falla con el error fijo si difiere. Una prueba dispara el mismo evento varias veces y reintenta un lote.

## R20 — Ajustes a `spec.md` hechos por este plan (con script, avisados)

El plan encontró tres cosas que la spec decía de otra manera. Se aplicó la opción más conservadora y se corrigió la spec:

1. **FR-006 / SC-001 — excepciones declaradas**. Además del motivo del rechazo: (a) un texto del original con **credenciales de URL** se reconstruye con ellas ocultas (se redacta antes de guardar, FR-031); (b) una **respuesta vacía** (sin texto ni llamadas) situada justo antes del corte de una compactación se reconstruye del lado reciente (R3). Las pruebas de igualdad no usan credenciales y comparan con y sin compactación; las excepciones tienen su propia prueba.
2. **FR-019 / supuesto de llamadas sin resultado — el cierre se persiste al continuar** (R10), como un `tool_finished` real; la spec decía que no se guardaba. Sin esto la compactación posterior falla cerrada para siempre.
3. **Supuesto «sin evento nuevo»**: el comando de reanudar no publica ninguno; la primera petición tras un corte publica los `tool_finished` de cierre (tipo existente). El catálogo de eventos no cambia.

Además: la spec decía que el prefijo avisaría «si se sabe que el entorno cambió»; no se puede saber (R16), así que no se avisa.

## R21 — Cierre idempotente: una sola vez por llamada interrumpida (decisión de `/speckit-tasks`)

El cierre (R10) se **deriva del estado guardado**, no de un contador: una llamada está «sin resultado» mientras no exista su fila. Por eso es idempotente por construcción:

| Caso | Qué ocurre |
|---|---|
| Reanudar dos veces sin hacer ninguna petición (por ejemplo, reanudar `A`, pasar a `B` y volver a `A`, o reanudar en otra ejecución) | El comando no escribe nada ninguna de las veces; la lista de cierres pendientes se recalcula igual cada vez |
| Reanudar, hacer la primera petición, volver a reanudar | La primera petición publica el cierre **una vez** (un `tool_finished` y una fila por llamada); la segunda reanudación ya encuentra el resultado real y no cierra nada |
| Dos cortes consecutivos en la misma sesión (corte, reanudar, petición que cierra, nuevo corte, reanudar) | Cada corte se cierra **una vez**; el primero no se vuelve a cerrar |
| La publicación del cierre falla a medias (varias llamadas, falla la segunda) | Cada cierre se **retira de la lista pendiente solo después de publicarse**; la excepción sale (código 1); al reanudar de nuevo solo falta el que no se publicó |

Prueba de contrato: contar los `tool_finished` con categoría `tool_interrupted` y las filas de `mensajes` con ese texto por `call_id`: nunca más de uno.

## R22 — La marca «sin detalle» no se puede saltar (decisión de `/speckit-tasks`)

La marca es la **ausencia de fila** de un evento de mensaje (`events_without_row > 0`, R11), más dos refuerzos:

1. **Fallo pegajoso en el guardado**: tras el primer fallo de guardado de una sesión, el guardado **no vuelve a escribir** en esa sesión (cada evento siguiente lanza `ConversationSaveError` sin tocar el almacén; el aviso fijo se escribe una sola vez). Así no puede haber un hueco en medio con filas posteriores: o queda un prefijo coherente o queda la marca.
2. **Memoria de la ejecución**: el guardado recuerda los identificadores de las sesiones cuyo guardado falló y `resume_session` los recibe (`known_incomplete`); reanudar uno de ellos da `SessionDetailMissing` **aunque la base parezca coherente** (caso en que fallaron a la vez el mensaje y el evento).

| Escenario | Resultado de `/reanudar` |
|---|---|
| El guardado falló a mitad de un turno y el registrador sí guardó el evento (marca en la base) | `SessionDetailMissing`, también desde una conexión nueva o desde otro proceso (archivo real en `tmp_path`) |
| El guardado falló en esta ejecución y la base parece coherente (también falló el evento) | `SessionDetailMissing` por la memoria de la ejecución |
| El proceso murió sin guardar nada más (corte normal) | Reanudable: la sesión es un prefijo válido |

**Límite honesto**: si fallan a la vez el mensaje y el evento y **nada se guarda después**, y el proceso muere, otra ejecución no puede distinguirlo de un corte normal (la base es un prefijo coherente); la persona recibió el aviso fijo y el código 1. No se añade una marca persistente (otra escritura que también puede fallar).

## R23 — Reanudar la sesión ya activa: error claro; dos procesos, no soportado (decisión de `/speckit-tasks`)

- `resume_session` recibe `current_session_id`. Orden de las comprobaciones: identificador vacío o inválido → es la sesión actual → fallo recordado (`known_incomplete`) → existe → es de tarea → falta detalle → reconstruir.
- Reanudar el identificador de la sesión activa da `AlreadyCurrentSession`: `Esa ya es la sesión actual.` Sin leer la base y **sin escribir nada**. Tras `/reanudar X` con éxito, un segundo `/reanudar X` da este error.
- Esto sustituye a «reanudar la sesión activa vuelve a leerla» de `resume_command.md` y modifica FR-018: la idempotencia se observa entre ejecuciones y en el ir y volver (R21).
- **Dos procesos usando a la vez la misma sesión: no soportado.** No se detecta ni se intenta resolver: sus eventos y mensajes se intercalarían (la clave primaria de `mensajes` hace fallar al segundo escritor con el error fijo de guardado, que es una protección parcial, no una garantía). Se documenta como supuesto de la spec y como observación en `PROGRESO.md`.

## R24 — El cambio de sesión no deja nada atado a la anterior (decisión de `/speckit-tasks`)

Inventario de lo que conoce un identificador de sesión (leído en `bootstrap.py`):

| Pieza | Cómo se desata |
|---|---|
| Compactador (y su cierre `emit` del `provider_error`) | Se **reemplaza** por `compactor_for(<nuevo>)`; el viejo no queda referenciado (solo se invoca desde `run_turn`) |
| Almacén de compactación | Recibe el identificador en cada llamada; no guarda estado |
| Guardado de mensajes | Se **reenlaza** (`bind`): lee `self._session_id` al llegar cada evento y **ignora** los eventos de otra sesión |
| Renovador del bloque y ejecutor de rondas | Solo existen con tarea; `/reanudar` no se registra en esas composiciones |
| Registrador de eventos | Va por `event.session_id`; no guarda estado de sesión |
| Cierres pendientes | Usan `active.session_id` |
| Bucle | Recibe el identificador en cada `run_turn`; `run_session` lo toma de `active.session_id` |

Pruebas: (a) tras `/reanudar` y una petición con compactación y cierre, el volcado de las tablas `events`, `mensajes` y `resumenes` de la sesión abandonada es **idéntico** al de antes; (b) un evento publicado a mano con el identificador de la sesión abandonada no crea ninguna fila de `mensajes`; (c) una guarda `ast`: dentro de `run_session` ninguna función interna usa `composition.session_id` (solo el titular `active`), salvo para crearlo.

## R25 — Límite del cambio en `cli/` (decisión de `/speckit-tasks`)

Los cambios en `src/harness_agent/cli/` se limitan al parámetro opcional `argument_commands` de `run_cli` y su uso para la ayuda y para despachar `/reanudar`. Comprobación: la tarea de la CLI termina con `git diff --stat -- src/harness_agent/cli` (solo `app.py`) y una revisión del diff (solo el parámetro, el alias de tipo, la rama de despacho y la línea de ayuda); una prueba comprueba que los parámetros de `run_cli` son exactamente los anteriores más `argument_commands`. **Cualquier otro cambio en `cli/` es un hallazgo: detenerse y avisar.** El texto de la línea genérica de error para `tool_interrupted` **no** se cambia aquí (aviso a C).

## R26 — Ajustes que estas decisiones hicieron a los documentos (por script)

`spec.md` (FR-009, FR-017, FR-018, FR-019, SC-006 y el caso límite de la sesión en uso), `contracts/error_messages.md` (fila nueva), `contracts/rebuild_rules.md` (firma, orden de comprobaciones y E9), `contracts/resume_command.md` (sesión activa, cierres uno a uno, desatado), `contracts/capture_rules.md` (fallo pegajoso y memoria de la ejecución), `data-model.md` (estado del guardado) y `plan.md` (19 tareas, tabla FR/AC/SC, estimación, archivos de prueba).
