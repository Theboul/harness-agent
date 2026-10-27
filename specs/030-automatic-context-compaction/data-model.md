# Data Model: HU-02-03

No cambia ningún puerto ni entidad compartida. Los tipos nuevos son `@dataclass(frozen=True)` o protocolos y viven en `core/context/` (solo biblioteca estándar y `harness_agent.core`), salvo el adaptador, que vive en `adapters/storage/`.

## Esquema SQLite nuevo (versión 3, aditivo)

`SCHEMA_VERSION` pasa de 2 a 3. El paso `_V3` de `adapters/storage/_schema.py` es **solo** esto; `events`, `criterios` y `criterios_sello` no se tocan:

```sql
CREATE TABLE resumenes (
    id            TEXT PRIMARY KEY,
    sesion_id     TEXT NOT NULL REFERENCES sessions(id),
    evento_desde  INTEGER NOT NULL CHECK (evento_desde >= 1),
    evento_hasta  INTEGER NOT NULL CHECK (evento_hasta >= evento_desde),
    texto         TEXT NOT NULL CHECK (length(trim(texto)) > 0),
    creado        TEXT NOT NULL
);
CREATE INDEX idx_resumenes_sesion ON resumenes (sesion_id, evento_hasta);
```

| Columna | Significado |
|---|---|
| `id` | Identificador del resumen (de la fábrica de identificadores inyectada); es el valor que llevan en `events.compacted_by` los eventos que cubre |
| `sesion_id` | Sesión a la que pertenece |
| `evento_desde`, `evento_hasta` | Menor y mayor `seq` de los eventos marcados (el rango cubierto) |
| `texto` | El resumen **ya limpio** y con las credenciales de URLs ocultas; nunca el prompt ni la transcripción |
| `creado` | Marca de tiempo UTC en ISO 8601 |

`events.compacted_by` (`TEXT`, ya existente desde la versión 1): `NULL` = no cubierto; si no, el `id` del resumen que lo cubre. **Marcar es lo único que se escribe en `events`**: `content`, `type`, `seq`, `created_at` e `id` no cambian nunca.

**Migración**: de 1 → 3 y de 2 → 3 en una transacción (`_script`); aditiva: no se pierde ni se reescribe ninguna fila. La versión 3 solo la abre esta versión o una posterior (una versión anterior la rechaza como «esquema desconocido», como ya hace con una versión mayor).

**Orden de las tablas respecto del registro de eventos**: el evento `context_compacted` se escribe en `events` con `seq = MAX(seq) + 1` de la sesión dentro de la misma transacción.

## `core/context/settings.py`

| Tipo / función | Forma |
|---|---|
| `ContextSettings` | `window_tokens: int = 32_000`; `windows: tuple[tuple[str, int], ...] = ()`; `threshold_percent: int = 80`; `recent_percent: int = 30`; `min_recent_messages: int = 4`; `summary_tokens: int = 2_000`. `__post_init__` valida los rangos de `contracts/context_settings.md` y lanza `ContextConfigError` (mensaje en español, **sin repetir el valor**) |
| `ContextSettings.window_for(model: str) -> int` | La ventana del modelo en `windows`, o `window_tokens` |
| `threshold_tokens(settings, model) -> int` | `window_for(model) * threshold_percent // 100` |
| `recent_budget_tokens(settings, model) -> int` | `threshold_tokens(settings, model) * recent_percent // 100` |
| `summary_cap_tokens(settings) -> int` | `2 * summary_tokens` (tope del resumen estimado) |

## `core/context/cut.py` (puro)

| Tipo / función | Forma |
|---|---|
| `HistoryParts` | `head_end: int` (índice del primer mensaje que ya no es cabeza protegida), `summary_index: int \| None` (posición del resumen anterior, siempre `head_end`), `region_start: int` |
| `split_history(history) -> HistoryParts \| None` | `None` si todavía no hay petición inicial (un `USER` no externo tras los `SYSTEM` iniciales) |
| `is_real(message) -> bool` | `False` para `SYSTEM` y para `USER` con `is_external` (el resumen y el mensaje de salida del verificador); `True` para el resto |
| `rebuild_history(history, region_start, cut, summary: Message) -> list[Message]` | El contexto resultante: `history[:region_start]` sin el resumen anterior, el resumen nuevo y `history[cut:]` (mismos objetos); puro |
| `choose_cut(history, region_start, budget_tokens, min_messages) -> int \| None` | El corte del contexto (índice del primer mensaje reciente) según R3; `None` si no queda nada por resumir. Puro y total |

## `core/context/summary.py` (puro)

| Función / constante | Forma |
|---|---|
| `SUMMARY_PROMPT_TEMPLATE`, `summary_prompt(summary_tokens) -> str` | El texto fijo de `contracts/summary_prompt.md` |
| `FRAME_HEADER` | La cabecera fija del resumen en el contexto |
| `render_transcript(messages) -> str` | La transcripción en texto plano de la región antigua (formato del contrato) |
| `build_summary_request(previous: str \| None, messages, summary_tokens) -> list[Message]` | `[SYSTEM(prompt), USER(resumen anterior + transcripción)]`; sin herramientas |
| `clean_summary(text) -> str` | Quita caracteres `Cc`, `Cf`, `Cs`, `Co` salvo `\n`, el tabulador pasa a espacio, recorta y oculta credenciales de URLs |
| `check_summary(text: object, cap_tokens: int) -> str` | Devuelve el resumen limpio o lanza `SummaryRejected` (vacío, no texto o por encima del tope) sin repetir el texto |
| `frame_summary(text) -> Message` | `Message(Role.USER, FRAME_HEADER + "\n" + text, is_external=True)` |
| `is_summary(message) -> bool` y `summary_text(message) -> str` | Reconocen el resumen en el historial y devuelven su texto sin el marco |

## `core/context/store.py` (protocolo, sin importar `adapters/`)

| Tipo | Forma |
|---|---|
| `MessageEvent` | `seq: int`; `kind: str` (`user`, `assistant` o `tool`); `covered: bool` |
| `CompactionCommit` | `session_id: str`; `protected_seq: int` (el evento de la petición inicial: nunca se marca); `through_seq: int` (seq del último evento de mensaje de la región antigua, inclusivo); `summary: str` (ya limpio); `summary_id: str`; `event_id: str` |
| `CompactionReceipt` | `summary_id: str`; `desde: int`; `hasta: int`; `eventos: int`; `event: Event` (el `context_compacted` ya guardado, listo para publicar) |
| `CompactionStore` (`Protocol`) | `message_events(session_id) -> list[MessageEvent]` y `commit_compaction(commit) -> CompactionReceipt \| None` (`None` = nada que cubrir, no se escribió nada) |

## `core/context/compactor.py`

`ContextCompactor(provider, store, settings, *, model, definitions, emit, publish, warn, new_id)`:

| Colaborador | Tipo | Quién lo da |
|---|---|---|
| `provider` | `Provider` (puerto existente; la llamada aparte, sin herramientas) | el proveedor de `compose()` |
| `store` | `CompactionStore` | `SqliteCompactionArchive` |
| `settings` | `ContextSettings` | `config.context` |
| `model` | `Callable[[], str]` | devuelve el modelo en uso (`config.model`) |
| `definitions` | `Callable[[], Sequence[ToolDefinition]]` | las declaraciones del registro (para estimar) |
| `emit` | `Callable[[EventType, dict[str, Any]], None]` | fabrica y publica un evento de la sesión (solo `provider_error`) |
| `publish` | `Callable[[Event], None]` | `bus.emit` (el evento de resumen ya guardado) |
| `warn` | `Callable[[str], None]` | escribe un aviso en la terminal |
| `new_id` | `Callable[[], str]` | identificadores del resumen y del evento |

`async before_turn(history: list[Message]) -> CompactionResult | None` (`history` se reemplaza in situ solo si la compactación termina bien). `CompactionResult`: `desde`, `hasta`, `eventos`, `estimated_before`, `estimated_after`.

## `adapters/storage/compaction_archive.py`

`SqliteCompactionArchive(store: SqliteSessionStore, *, clock=..., )` implementa `CompactionStore` sobre la conexión compartida (`SqliteSessionStore.connection()`), con las mismas reglas que `save_event` (`BEGIN IMMEDIATE`, `COMMIT`/`ROLLBACK`). Errores del motor → `SessionStoreError` (mensaje fijo).

## Configuración

`HarnessConfig.context: ContextSettings = ContextSettings()` (campo nuevo al final, con valor por defecto). `config.py` construye el valor desde la sección opcional `[context]` (contrato en `contracts/context_settings.md`).

## Estados y relaciones

```text
history (memoria) = [SYSTEM…] [USER petición inicial] [USER externo: resumen?] [región antigua] [ventana reciente]
                       └──── cabeza protegida ────┘      └ se reemplaza ┘   └── se resume ──┘   └─ íntegra ─┘

events (SQLite, intacto) ── seq 1 … n ── compacted_by = id del resumen ──▶ resumenes(id, rango, texto)
                              └── context_compacted (seq n+1, {desde, hasta, eventos}, sin texto)
```
