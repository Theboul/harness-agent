# Data Model: HU-03-04 — Reanudar una sesión por identificador

Esquema SQLite **versión 5**, aditivo. No se toca ninguna tabla existente (`sessions`, `events`, `criterios*`, `resumenes`, `contexto_esencial`). Los tipos del núcleo son `@dataclass(frozen=True)`.

## Tabla nueva: `mensajes`

Una fila por **mensaje real** de la conversación de una sesión **sin tarea**, en el orden en que ocurrió.

```sql
CREATE TABLE mensajes (
    sesion_id        TEXT NOT NULL REFERENCES sessions(id),
    posicion         INTEGER NOT NULL CHECK (posicion >= 1),
    rol              TEXT NOT NULL CHECK (rol IN ('user', 'assistant', 'tool')),
    contenido        TEXT NOT NULL,
    llamadas         TEXT,
    resultado_id     TEXT,
    resultado_error  INTEGER CHECK (resultado_error IN (0, 1)),
    externo          INTEGER NOT NULL DEFAULT 0 CHECK (externo IN (0, 1)),
    uso              TEXT,
    evento_id        TEXT,
    creado           TEXT NOT NULL,
    PRIMARY KEY (sesion_id, posicion),
    CHECK ((rol = 'tool' AND resultado_id IS NOT NULL AND resultado_error IS NOT NULL)
        OR (rol <> 'tool' AND resultado_id IS NULL AND resultado_error IS NULL)),
    CHECK (rol = 'assistant' OR llamadas IS NULL)
);
CREATE INDEX idx_mensajes_evento ON mensajes (evento_id);
```

| Columna | Qué guarda | Notas |
|---|---|---|
| `sesion_id` | la sesión | clave foránea a `sessions`; con `PRAGMA foreign_keys = ON` (ya activo) |
| `posicion` | 1, 2, 3… por sesión | **única por sesión** (clave primaria); el guardado sigue la numeración; no hay huecos salvo un guardado fallido |
| `rol` | `user`, `assistant` o `tool` | nunca `system` |
| `contenido` | el texto del mensaje, con las credenciales de URL ocultas | puede ser `''` (respuesta solo con llamadas o vacía) |
| `llamadas` | JSON: lista `[{"id", "name", "arguments"}]` | solo en `assistant`; `NULL` si no hay llamadas; los textos de los argumentos con credenciales ocultas |
| `resultado_id` | `ToolCall.id` al que contesta | solo en `tool` |
| `resultado_error` | 0/1 (`ToolResult.is_error`) | solo en `tool` |
| `externo` | 0/1 (`Message.is_external`) | |
| `uso` | JSON `{"input_tokens", "output_tokens"}` o `NULL` | solo `assistant` (el que informó el proveedor) |
| `evento_id` | `Event.id` del evento que disparó el guardado de **este** mensaje | `NULL` en la respuesta solo con llamadas, la vacía y los cierres sin evento; **sin clave foránea** (el evento puede no haberse guardado nunca tras un corte) |
| `creado` | marca de tiempo UTC ISO | reloj inyectado |

Para un mensaje de herramienta, `contenido` es también el contenido del `ToolResult` (el bucle los hace iguales); si no lo fueran, el guardado falla con el error fijo (no se puede representar).

**Qué NO entra**: mensajes `SYSTEM` (prefijo, bloque esencial), el resumen de compactación y la salida del verificador (`USER` con `externo`), ni los resultados sintéticos hasta que se **publica** su `tool_finished` de cierre (R10).

### Qué se sustituye antes de guardar

| Caso | Qué se guarda |
|---|---|
| Resultado de una llamada rechazada por la persona (`category == "approval_rejected"` en `tool_finished`) | `rejection_message(name, None)` = `[approval_rejected] Tool '<name>' was rejected by the user.` (nunca el motivo) |
| Cualquier texto con una URL que lleve credenciales antes de la arroba | `hide_url_credentials`: la parte entre `://` y `@` pasa a `<secreto oculto>` |

### Relación con los eventos

- `mensajes.evento_id` → `events.id` (sin clave foránea). Con evento guardado: `events.seq` y `events.compacted_by` dan la posición y si un resumen lo cubre.
- Los eventos de tipo mensaje son `user_message`, `assistant_message` y `tool_finished`: **cada uno debe tener una fila** que lo apunte; si alguno no la tiene → «sin detalle» (FR-009).
- Regla de cobertura (pura, `contracts/rebuild_rules.md`): fila con evento → cubierta si `compacted_by` no es `NULL`; fila sin evento → la cobertura de la **siguiente** fila con evento (si no hay, no cubierta).

### Migración

`_STEPS[5] = _V5`; una base nueva ejecuta 1→5; una base de la versión *v* (1 a 4) ejecuta solo `_V5…`. Una sola transacción por apertura; `PRAGMA user_version = 5`. Una base con versión mayor se rechaza sin modificarla (comportamiento actual).

## Tipos del núcleo (`core/context/`)

| Tipo | Campos | Para qué |
|---|---|---|
| `MessageRecord` | `position: int`, `message: Message`, `event_id: str \| None` | un mensaje ya limpio (credenciales y rechazo) listo para guardar |
| `StoredMessage` | `record: MessageRecord`, `covered: bool \| None` | una fila leída; `covered` es `True`/`False` si su evento está guardado, `None` si no tiene evento |
| `StoredConversation` | `session_id`, `model: str \| None`, `is_task: bool`, `messages: tuple[StoredMessage, ...]`, `summary: str \| None`, `events_without_row: int`, `last_event_type: str \| None` | todo lo que la reconstrucción necesita, sin SQL |
| `Resumed` | `history: tuple[Message, ...]`, `saved_count: int`, `closed_calls: tuple[tuple[str, str], ...]`, `message_count: int`, `has_summary: bool`, `empty: bool`, `cut_off: bool`, `model_changed: bool`, `next_position: int`, `notice: str` | el resultado de reanudar |
| `MessageLog` (protocolo) | `append(session_id, records)`, `last_position(session_id)` | donde el guardado escribe |
| `ResumeSource` (protocolo) | `load_conversation(session_id) -> StoredConversation \| None` | de donde la reconstrucción lee |

`Resumed.history` incluye el prefijo. `saved_count` es el número de mensajes iniciales que ya están guardados; el resto son los **resultados sintéticos** (pendientes de publicarse como `tool_finished`, R10). `closed_calls` = pares `(call_id, nombre)` de esos sintéticos, en orden.

## Estado del guardado (`ConversationCapture`)

| Estado | Valores | Transiciones |
|---|---|---|
| sesión y lista del historial | ninguna → enlazadas | `bind(session_id, history, next_position, saved_count)` (en `run_session` y en `/reanudar`); antes de enlazar ignora los eventos |
| último mensaje guardado | `None` o un mensaje (identidad) | tras cada lote guardado con éxito pasa al último del lote; si el lote falla no cambia |
| posición siguiente | entero ≥ 1 | crece con cada fila guardada |
| fallo de la sesión enlazada | no / sí (pegajoso) | pasa a «sí» en el primer fallo de guardado; `bind` a otra sesión lo limpia |
| `incomplete_sessions` | conjunto de identificadores | crece con cada sesión cuyo guardado falló en esta ejecución; nunca se vacía |

## Validaciones y reglas

- Una fila `tool` exige `resultado_id` y `resultado_error`; una `user`/`assistant` no los lleva; solo `assistant` lleva `llamadas`.
- `append` es **atómico** (un lote en una transacción) e **idempotente** (una fila idéntica con la misma posición se ignora; distinta → error fijo).
- La lectura une `mensajes` con `events` y `resumenes`; no verifica sellos ni publica eventos.
- Ninguna consulta construye SQL con texto recibido (parámetros enlazados).
- Los errores del motor se traducen a `SessionStoreError` con mensaje fijo, sin datos.
