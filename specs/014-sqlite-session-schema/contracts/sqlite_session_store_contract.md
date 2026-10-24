# Contrato: `SqliteSessionStore` (HU-03-01)

```python
class SqliteSessionStore:
    def __init__(self, path: str | os.PathLike[str], *,
                 clock: Callable[[], datetime] = ...,
                 id_factory: Callable[[], str] = ...) -> None: ...
    def create_session(self, *, model: str | None = None, goal: str | None = None,
                       parent_id: str | None = None) -> StoredSession: ...
    def get_session(self, session_id: str) -> StoredSession | None: ...
    def list_sessions(self) -> list[SessionSummary]: ...
    def close(self) -> None: ...
    def __enter__(self) -> SqliteSessionStore: ...
    def __exit__(self, *exc: object) -> None: ...
```

## Garantías

- `create_session` devuelve una sesión `active`, con id del `id_factory` y `created_at` en UTC del `clock`.
- `parent_id` inexistente → `ParentSessionNotFound`; no se crea nada.
- `get_session` de un id desconocido → `None`.
- `list_sessions` → `SessionSummary` (puerto) de la más antigua a la más reciente.
- Abrir una base con `user_version` mayor que `SCHEMA_VERSION` → `SchemaVersionError`, sin escribir.
- Cualquier `sqlite3.Error` → `SessionStoreError` (mensaje fijo, sin datos ni rutas).
- Tras `close()`, cualquier operación → `SessionStoreError`; `close()` es idempotente.
- No lee entorno ni configuración; no imprime.

## Errores

`SessionStoreError` (base) ← `SchemaVersionError`, `ParentSessionNotFound`.
