# Contrato: el protocolo del almacén de compactación y su adaptador

## Protocolo (`harness_agent.core`, definido en `core/context/store.py`)

```python
@dataclass(frozen=True)
class MessageEvent:
    seq: int
    kind: str        # "user" | "assistant" | "tool"
    covered: bool    # compacted_by no es NULL

@dataclass(frozen=True)
class CompactionCommit:
    session_id: str
    protected_seq: int   # evento de la petición inicial: nunca se marca
    through_seq: int     # seq del último evento de mensaje de la región antigua (INCLUSIVO)
    summary: str         # ya limpio y con las credenciales ocultas
    summary_id: str
    event_id: str

@dataclass(frozen=True)
class CompactionReceipt:
    summary_id: str
    desde: int
    hasta: int
    eventos: int
    event: Event         # context_compacted ya guardado

class CompactionStore(Protocol):
    def message_events(self, session_id: str) -> list[MessageEvent]: ...
    def commit_compaction(self, commit: CompactionCommit) -> CompactionReceipt | None: ...
```

`core/interfaces/` **no cambia**; `SessionStore` y `ContextManager` tampoco. El protocolo es un colaborador interno de `core/context/`.

## Garantías del adaptador (`SqliteCompactionArchive`)

1. **`message_events`** devuelve, en orden de `seq`, solo los eventos de tipo `user_message` (`user`), `assistant_message` (`assistant`) y `tool_finished` (`tool`) de la sesión, con `covered` según `compacted_by`. Un mensaje del asistente **sin contenido** (solo llamadas a herramientas) no tiene evento `assistant_message` (el bucle lo publica solo si hay contenido): el compactador lo tiene en cuenta al enlazar mensajes y eventos (ejemplo E5).
2. **`commit_compaction`** ocurre en **una transacción** (`BEGIN IMMEDIATE` … `COMMIT`): (a) selecciona las filas a marcar: `session_id` igual, `seq > protected_seq`, `seq <= through_seq`, `compacted_by IS NULL` y `type != 'context_compacted'`; (b) si no hay ninguna, no escribe **nada** y devuelve `None` (idempotente); (c) inserta la fila de `resumenes` con `evento_desde = min(seq)` y `evento_hasta = max(seq)`; (d) actualiza **solo** `compacted_by` de esas filas con `summary_id`; (e) inserta el evento `context_compacted` (`id = event_id`, `seq = MAX(seq) + 1`) con la carga `{"desde": …, "hasta": …, "eventos": …}`; (f) `COMMIT`. Cualquier error → `ROLLBACK` y nada queda.
3. **No borra ni modifica** el `content`, el `type`, el `seq`, el `created_at` ni el `id` de ningún evento (AC-02). `load_session` devuelve los mismos eventos de antes más el de resumen.
4. **Un solo registro del evento**: el adaptador escribe la fila; el registrador del bus **no** la escribe porque `compose()` lo adjunta con `skip=(EventType.CONTEXT_COMPACTED,)`. Si se olvidara, la clave primaria `events.id` haría fallar el segundo intento con `DuplicateEvent`: nunca hay dos filas.
5. Un error del motor se convierte en `SessionStoreError` con mensaje fijo; nunca lleva el texto del resumen ni del historial.

## Ejemplo normativo (E1)

Eventos de la sesión (la columna *msg* indica el evento de mensaje y su tipo):

| seq | tipo | msg |
|---|---|---|
| 1 | `user_message` | `user` (petición inicial, protegida) |
| 2 | `assistant_message` | `assistant` (pide una herramienta) |
| 3 | `tool_requested` | — |
| 4 | `permission_decided` | — |
| 5 | `tool_finished` | `tool` |
| 6 | `assistant_message` | `assistant` |
| 7 | `user_message` | `user` |
| 8 | `assistant_message` | `assistant` |
| 9 | `user_message` | `user` |
| 10 | `assistant_message` | `assistant` |

`message_events` → 8 elementos: seq 1, 2, 5, 6, 7, 8, 9 y 10, todos `covered = False`. Con la ventana reciente de los cuatro últimos mensajes (seq 7 a 10), el compactador pide `commit_compaction(CompactionCommit(session_id=…, protected_seq=1, through_seq=6, …))`:

- filas marcadas: seq 2, 3, 4, 5 y 6 (cinco, incluidos los eventos que no son mensajes);
- fila de `resumenes`: `evento_desde = 2`, `evento_hasta = 6`;
- evento nuevo: seq 11, tipo `context_compacted`, contenido `{"desde": 2, "hasta": 6, "eventos": 5}`;
- recibo: `desde = 2`, `hasta = 6`, `eventos = 5`;
- seq 1 y 7 a 10 siguen con `compacted_by = NULL`; ninguna fila cambió de contenido.

## Ejemplo normativo (E2) — idempotencia

Repetir el mismo `commit_compaction` (mismos `protected_seq` y `through_seq`) devuelve `None` y no escribe nada: `resumenes` tiene una fila y `events` tiene 11.

## Ejemplo normativo (E3) — segunda compactación

Con más eventos (seq 11 es el `context_compacted`; llegan los seq 12 a 19 y la ventana reciente empieza en el 17): `through_seq = 16` (el último evento de mensaje de la región antigua); se marcan los seq 7 a 10 y 12 a 16 que aún no estaban cubiertos, **sin** el seq 11 (`context_compacted`) y sin el 1; `evento_desde = 7`, `evento_hasta = 16`. Los rangos de las dos compactaciones no se solapan.

## Ejemplo normativo (E4) — rollback

Un fallo inyectado en cualquiera de los tres pasos (`INSERT` del resumen, `UPDATE` de las marcas, `INSERT` del evento) deja la base **idéntica** a la de antes: `resumenes` sin filas nuevas, ningún `compacted_by` cambiado y ningún `context_compacted` nuevo.

## Ejemplo normativo (E5) — un mensaje del asistente sin contenido no tiene evento

Historial real: `USER`, `ASSISTANT` con contenido vacío y una llamada, `TOOL`, `ASSISTANT("Listo")`. Eventos de la sesión: 1 `user_message`, 2 `tool_requested`, 3 `permission_decided`, 4 `tool_finished`, 5 `assistant_message`.

- Eventos esperados por los mensajes reales: `user`, (ninguno para el asistente vacío), `tool`, `assistant`.
- `message_events`: seq 1 (`user`), 4 (`tool`) y 5 (`assistant`): **coinciden** uno a uno; no hay fallo de correspondencia.
- Si la región antigua termina en el `TOOL` (seq 4) y la ventana reciente empieza en el `ASSISTANT("Listo")`, `through_seq = 4`: se marcan los seq 2, 3 y 4 (con `protected_seq = 1`); el seq 5 no se marca.
- Si la ventana reciente empezara en el asistente vacío (porque el corte seguro lo exige), los `tool_requested` y `permission_decided` de esa llamada (seq 2 y 3) quedan **sin marcar**, porque están después del último evento de mensaje de la región antigua.
