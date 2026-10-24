# Data Model: HU-03-02

El esquema no cambia (versión 1 de HU-03-01). Se documenta cómo se llena la tabla `events`.

## Tabla `events`

| Columna | Origen |
|---|---|
| `id` | `Event.id` (clave primaria; un id repetido se rechaza) |
| `session_id` | `Event.session_id` (debe existir en `sessions`) |
| `seq` | Siguiente número de la sesión (1, 2, 3…), asignado en la transacción de `save_event` |
| `type` | `Event.type.value` |
| `content` | `json.dumps(Event.payload)` |
| `created_at` | `Event.timestamp` en UTC, ISO-8601 con zona |
| `compacted_by` | `NULL` (lo usa la compactación futura) |

## Lectura

`load_session(session_id)` → `list[Event]` ordenada por `seq`. Se reconstruye `Event(id, session_id, EventType(type), timestamp, payload)`.

Limitación documentada: las tuplas del contenido vuelven como listas y las claves no cadena como cadenas (comportamiento de JSON).

## Errores de dominio

`SessionNotFound`, `DuplicateEvent`, `EventSerializationError` (subclases de `SessionStoreError`).
