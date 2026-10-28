# Contrato: el comando `/reanudar <id>`, el cambio de sesión y el primer turno

## El comando

| Aspecto | Regla |
|---|---|
| Nombre y ayuda | `/reanudar <identificador>`; aparece en `/ayuda` («Reanuda una sesión guardada por su identificador.») |
| Dónde se registra | `run_session`, mediante el parámetro nuevo `argument_commands` de `run_cli`, en toda composición; con tarea (o sin guardado de mensajes) responde «Reanudar no está disponible en esta sesión.» y no cambia nada |
| Qué recibe | el texto de la línea después del comando, sin espacios exteriores (puede ser vacío) |
| Qué devuelve | **una línea**: la de estado (éxito) o un mensaje fijo de error. Nunca lanza: un error de dominio se convierte en su mensaje fijo, y un fallo inesperado de lectura en «No se pudo leer la sesión; la sesión actual sigue sin cambios.» |
| Sincronía | síncrono: leer y reconstruir no llaman al modelo |
| Qué escribe | **nada** (FR-015) |

## Cambio mínimo de `cli/app.py` (área C, visto bueno H3)

- `run_cli(..., commands=None, argument_commands=None)`; tipo `Mapping[str, tuple[str, Callable[[str], str]]]`.
- En el bucle de entrada, antes de `commands`: si `argument_commands` contiene el primer token, escribir `argument_commands[token][1](resto.strip())` con `_write_line`.
- `_help_text` lista también estos comandos (tras los de `commands`, antes de la línea final).
- Sin `argument_commands` todo es idéntico (`HELP_TEXT` y mensajes intactos). Ningún otro cambio en `cli/`; no se exporta nada nuevo en `__all__`.

## Cambio de sesión (en `run_session`)

Estado local: `active = {session_id, compactor, closures}` (inicialmente la sesión y el compactador de la composición, sin cierres) y la lista `history` (la misma lista que ven el guardado y las peticiones).

Al reanudar con éxito (`resumed = resume_session(...)`):

1. `history[:] = resumed.history` (en sitio).
2. `active.session_id = <id pedido>`; `active.compactor = composition.compactor_for(<id pedido>)`.
3. `capture.bind(<id>, history, resumed.next_position, resumed.saved_count)`.
4. `active.closures = resumed.closed_calls`.
5. Devolver `resumed.notice`.

Si algo falla antes del paso 1, **nada de lo anterior cambia** (la sesión actual sigue intacta). La sesión abandonada queda tal cual en el almacén y **nada la vuelve a escribir** (R24: compactador reemplazado, guardado reenlazado e indiferente a otros identificadores, cierres con `active.session_id`). Los contadores de límites del bucle no se tocan.

Reanudar la sesión que ya es la activa da `AlreadyCurrentSession` («Esa ya es la sesión actual.»): no se lee ni se escribe nada. Tras `/reanudar X`, un segundo `/reanudar X` da ese error; reanudar `Y` y luego `X` sí funciona (R21, R23).

El comando pasa a `resume_session` el identificador activo (`current_session_id`) y los de `capture.incomplete_sessions` (`known_incomplete`, R22).

## Primer turno tras reanudar (cierre de llamadas, R10)

En `run_turn(task)` de `run_session`, **antes** de renovar el bloque (no hay, sesión sin tarea), de compactar y de llamar al bucle:

1. Por cada `(call_id, name)` de `active.closures`, en orden: publicar `Event.create(active.session_id, TOOL_FINISHED, {"call_id", "name", "is_error": True, "category": "tool_interrupted"})`. El guardado de mensajes recoge el resultado sintético pendiente (con su `evento_id`) y el registrador guarda el evento.
2. Cada cierre se retira de `active.closures` **solo después de publicarse** (si uno falla, los no publicados siguen pendientes, R21).
3. `await compactor.before_turn(history)` con el compactador activo.
4. `loop.run_turn(session_id=active.session_id, task=task, history=history)`.
5. En un `finally`: `capture.flush()`.

Si la publicación del paso 1 falla, es un fallo de entrega normal (la línea con el tipo y código 1).

## Eventos y orden de la sesión reanudada

- Los eventos nuevos llevan el identificador de la **sesión reanudada** y reciben el siguiente `seq` (`MAX(seq) + 1`, lo hace `save_event`); los anteriores no se tocan.
- El comando no publica ningún evento. Los únicos eventos que el primer turno añade por la reanudación son los `tool_finished` de cierre (tipo existente) y, si el contexto supera el umbral, el `context_compacted` de la compactación normal.

## Límites, modelo y CLI

- Los contadores del bucle **continúan** (misma ejecución): reanudar no los reinicia. Una ejecución nueva empieza en cero (no se persisten).
- El umbral y la compactación usan el modelo configurado; si difiere del guardado se añade el aviso a la línea.
- La terminal no repinta la conversación: solo la línea de estado y el cursor.
