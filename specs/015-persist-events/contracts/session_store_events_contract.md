# Contrato: eventos en `SqliteSessionStore` (HU-03-02)

```python
class SqliteSessionStore(SessionStore):
    def save_event(self, event: Event) -> None: ...
    def load_session(self, session_id: str) -> list[Event]: ...
    # + lo de HU-03-01: create_session, get_session, list_sessions, close

def attach_event_recorder(bus: EventBus, store: SessionStore) -> None: ...
```

## Garantías de `save_event`

- Al devolver, el evento está confirmado con sincronización completa (sobrevive a un cierre abrupto).
- Se asigna `seq` consecutivo por sesión dentro de una transacción con bloqueo de escritura.
- Sesión inexistente → `SessionNotFound`; id repetido → `DuplicateEvent`; contenido no serializable → `EventSerializationError` (sin abrir transacción). En los tres casos no se guarda nada.
- Fallo del motor → rollback y `SessionStoreError` (mensaje fijo); el almacén sigue usable y `seq` no tiene huecos.
- Almacén cerrado → `SessionStoreError`.

## Garantías de `load_session`

- Orden por `seq`; solo eventos de esa sesión; sesión desconocida o sin eventos → `[]`.
- Base dañada (tipo desconocido, JSON inválido) → `SessionStoreError`.

## `attach_event_recorder`

- Suscribe `store.save_event` a cada `EventType`.
- No captura excepciones: los fallos llegan al emisor como `EventDeliveryError` del bus.
- Depende solo de los puertos `EventBus` y `SessionStore`.

## Errores

`SessionStoreError` ← `SchemaVersionError`, `ParentSessionNotFound`, `SessionNotFound`, `DuplicateEvent`, `EventSerializationError`.
