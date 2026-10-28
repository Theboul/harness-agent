# Contrato: protocolos del registro de mensajes

Dos protocolos pequeños que pertenecen a `core/context/` (los puertos de `core/interfaces/` **no cambian**: mismo patrón que `CompactionStore` de HU-02-03 y las fuentes de solo lectura de HU-02-06.1). Los implementa `SqliteMessageStore` (`adapters/storage/message_store.py`) y un doble en memoria de las pruebas; **la misma prueba de contrato** (`tests/contracts/test_message_log_contract.py`) corre contra ambos.

## `MessageLog` (escritura)

```python
class MessageLog(Protocol):
    def append(self, session_id: str, records: Sequence[MessageRecord]) -> None: ...
    def last_position(self, session_id: str) -> int: ...
```

| Regla | Detalle |
|---|---|
| Atómico | todo el lote o nada; una excepción deja la tabla como estaba |
| Idempotente | una fila con la **misma posición e idéntica** (rol, contenido, llamadas, resultado, externo, uso, `evento_id`) ya guardada se ignora; la misma posición con valores distintos falla |
| Sin huecos impuestos | no exige posiciones consecutivas (un lote fallido no deja huecos, pero el almacén no lo vigila) |
| `last_position` | la mayor posición de la sesión, o 0 si no hay filas |
| Errores | `SessionStoreError` con mensaje fijo, sin contenido, sin datos, sin `__cause__`; cualquier fallo de serialización también (los argumentos deben ser JSON) |
| Sesión inexistente | falla (clave foránea) con el mismo error fijo |
| Sin conexión propia | usa `store.connection()` de `SqliteSessionStore` |

El lote recibe registros **ya limpios** (credenciales ocultas, rechazo sin motivo): el almacén no redacta ni decide qué es un rechazo.

## `ResumeSource` (lectura)

```python
class ResumeSource(Protocol):
    def load_conversation(self, session_id: str) -> StoredConversation | None: ...
```

Devuelve `None` si la sesión no existe. Si existe, devuelve:

| Campo | Cómo se calcula |
|---|---|
| `model` | `sessions.model` |
| `is_task` | existe una fila de la sesión en `criterios` o en `contexto_esencial` (solo existencia: no lee valores, no verifica sellos, no publica eventos) |
| `messages` | todas las filas de `mensajes` por `posicion`, cada una con `covered`: `None` si `evento_id` es `NULL` o su evento no está guardado; `True` si `events.compacted_by` no es `NULL`; `False` si lo es |
| `summary` | `resumenes.texto` de la fila de mayor `evento_hasta` de la sesión (desempate: la última insertada), o `None` |
| `events_without_row` | número de eventos de la sesión de tipo `user_message`, `assistant_message` o `tool_finished` que **ningún** `mensajes.evento_id` apunta |
| `last_event_type` | el tipo del evento de mayor `seq`, descartando `context_compacted` (o `None` si no hay) |

Reglas: una sola lectura consistente (una transacción de lectura); solo lectura; los errores del motor → `SessionStoreError` fijo; un valor dañado en una columna (JSON ilegible, rol desconocido) → `SessionStoreError` («Un mensaje guardado está dañado y no se puede leer.»). Nada del contenido en ningún mensaje de error.

## Prueba de contrato (lo que fijan ambos)

1. `append` + `load_conversation` devuelven los mismos mensajes (todos los campos).
2. Un lote repetido idéntico no cambia nada; uno que difiere falla y no deja nada.
3. Un lote con una fila inválida (JSON no serializable) no guarda ninguna.
4. `last_position` crece con el lote y vale 0 al principio.
5. La cobertura sale de las marcas de los eventos (el doble en memoria simula las marcas).
6. Una sesión inexistente → `None`.
