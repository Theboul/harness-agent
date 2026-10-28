# Contrato: reglas del guardado de mensajes (`ConversationCapture`)

Pieza pura de `core/context/conversation.py`. La composición le entrega el almacén (un `MessageLog`), un reloj, un avisador y la lista del historial; el bus llama a su método `on_event`. No importa el bucle, `adapters`, `cli`, `config` ni `sqlite3`.

## Suscripción y orden (verificado en R4)

| Qué | Regla |
|---|---|
| Tipos | `user_message`, `assistant_message`, `tool_requested`, `tool_finished` |
| Cuándo se suscribe | en `compose`, **justo antes** de `attach_event_recorder`; el renderizador de la CLI y el tablero de criterios se suscriben después (dentro de `run_session`/`run_cli`) |
| Orden de entrega por evento | **guardar mensaje → guardar evento → CLI** |
| Si un manejador falla | los demás siguen recibiendo el evento y `emit` lanza `EventDeliveryError` al final (comportamiento del bus, sin cambios) |
| Hasta `bind` | **inerte**: ignora todo evento (las pruebas que llaman al bucle directamente siguen igual) |
| Sesiones con tarea | no se instala |

## Qué guarda en cada evento

Sea *pendiente* la lista de mensajes **reales** (`is_real`) del historial que están **después del último guardado**, localizado por identidad (`is`). Si el último guardado no está en el historial → `ConversationSaveError`.

| Evento | Guarda | Lleva `evento_id` |
|---|---|---|
| `user_message` | todos los pendientes | el último, que debe ser `USER` no externo; si no → error |
| `assistant_message` | todos los pendientes | el último, que debe ser `ASSISTANT`; si no → error |
| `tool_requested` | todos los pendientes | ninguno |
| `tool_finished` | los pendientes **hasta el que contesta** a `call_id` del payload | ese |
| (cierre de turno) `flush()` | todos los pendientes | ninguno |

Un evento cuya `session_id` no es la enlazada se ignora. Sin pendientes, no se escribe nada (idempotente).

## Qué contiene cada registro

1. El mensaje tal cual está en el historial, con `hide_url_credentials` aplicado al contenido, al contenido del resultado y a **cada valor de texto** de los argumentos (recursivo, sin tocar las claves).
2. Si el evento es `tool_finished` con `payload["category"] == "approval_rejected"`: el contenido (del mensaje y de su resultado) es `rejection_message(payload["name"], None)`; el original, con el motivo, **nunca** llega al almacén ni a los registros.
3. `position` = siguiente número de la sesión; el contador solo avanza si el lote se guardó.

## Fallo al guardar

| Fallo | Qué ocurre |
|---|---|
| El almacén lanza cualquier `Exception` (o el mensaje no es serializable) | se escribe **una línea fija** con el avisador y se lanza `ConversationSaveError` (mensaje fijo, sin contenido ni texto de la excepción, sin causa encadenada); el estado no cambia (el último guardado y la posición siguen igual) |
| Cualquier fallo de guardado de una sesión | el fallo es **pegajoso** para esa sesión: los eventos siguientes lanzan `ConversationSaveError` sin tocar el almacén y sin repetir el aviso; el identificador se recuerda en `incomplete_sessions` (R22) |
| `BaseException` (cancelación, interrupción del teclado) | no se captura |
| El vaciado del cierre de turno falla **mientras otra excepción sale** | escribe el aviso fijo; la excepción original sigue su camino |

Línea fija: «No se pudo guardar un mensaje de la conversación; la sesión no podrá reanudarse.»

## Enlazar (`bind`)

`bind(session_id, history, next_position, saved_count)` guarda las referencias (el fallo pegajoso se mantiene si la sesión ya está en `incomplete_sessions` y no se vuelve a escribir en ella; con otra sesión se puede guardar de nuevo); el último guardado pasa a ser el último mensaje **real** de `history[:saved_count]` (o `None` si no hay). En una sesión nueva: historial = prefijo → `None`. En una reanudada: el último de los mensajes cargados; los sintéticos de cierre quedan **después**, **retenidos**: `flush()` nunca los guarda y solo los guarda su propio `tool_finished` de cierre (R10).

## Pruebas propias de la regla

- Cada tipo de evento con sus pendientes, incluida la respuesta solo con llamadas (guardada al `tool_requested`) y la vacía (guardada en el cierre).
- Rechazo: el centinela del motivo no aparece en ninguna fila, ni en la lista de registros ni en los bytes de la base (`T010c`).
- Identidad: dos mensajes iguales se guardan los dos; el mismo evento repetido no duplica.
- Compactación entre medias: el resumen y el bloque nunca se guardan; el siguiente turno guarda solo lo nuevo.
- Fallos: almacén que falla → aviso fijo, error fijo, sin contenido, estado intacto; reintento posterior guarda lo pendiente sin duplicar.
- Fallo pegajoso: tras un fallo, un evento posterior lanza el error fijo sin llamar al almacén; `incomplete_sessions` contiene la sesión; `bind` a otra sesión permite guardar de nuevo y conserva el recuerdo.
- Azar de semilla fija (20261101): se prueba junto con la reconstrucción en `test_resume_properties.py` (historiales válidos con compactaciones simuladas → todo lo real se guarda una vez y en orden).
