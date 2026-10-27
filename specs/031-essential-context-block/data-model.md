# Data Model: HU-02-06.1

No cambia ningún puerto, entidad compartida ni evento. Los tipos nuevos son `@dataclass(frozen=True)` o protocolos y viven en `core/context/` (solo biblioteca estándar y `harness_agent.core`), salvo el adaptador, que vive en `adapters/storage/`.

## Esquema SQLite nuevo (versión 4, aditivo)

`SCHEMA_VERSION` pasa de 3 a 4. El paso `_V4` de `adapters/storage/_schema.py` es **solo** esto; `events`, `resumenes`, `criterios` y `criterios_sello` no se tocan:

```sql
CREATE TABLE contexto_esencial (
    sesion_id  TEXT NOT NULL REFERENCES sessions(id),
    clave      TEXT NOT NULL CHECK (length(trim(clave)) > 0),
    orden      INTEGER NOT NULL CHECK (orden >= 1),
    valor      TEXT NOT NULL CHECK (length(trim(valor)) > 0),
    origen     TEXT NOT NULL CHECK (length(trim(origen)) > 0),
    creado     TEXT NOT NULL,
    PRIMARY KEY (sesion_id, clave, orden)
);
```

| Columna | Significado |
|---|---|
| `sesion_id` | Sesión de la tarea a la que pertenecen los elementos |
| `clave` | `objetivo`, `reglas`, `ticket`, `criterios_ref` o `instrucciones`. Sin `CHECK` sobre el conjunto de claves a propósito: HU-02-06.2 añadirá `decisiones` sin otro cambio de esquema; el conjunto lo valida el núcleo |
| `orden` | 1 para los elementos de un solo valor; 1, 2, 3… para `instrucciones` (el orden en que se entregaron) |
| `valor` | El texto limpio (objetivo, reglas, ticket), la referencia (criterios) o el texto exacto del mensaje (instrucciones) |
| `origen` | De dónde salió: `tarea (objetivo)`, `tarea (reglas)`, `tarea (título)`, `criterios protegidos (HU-11-01)`, o `entorno`, `git`, `comandos` para las instrucciones |
| `creado` | Marca de tiempo UTC en ISO 8601 (reloj inyectado del almacén) |

**Escritura única**: los elementos se guardan **una vez**, al crear la sesión de la tarea, en una transacción (`BEGIN IMMEDIATE` … `COMMIT`). El adaptador no ofrece actualizar ni borrar; la clave primaria impide guardar dos veces la misma. Después solo se lee.

**Migración**: de 1 → 4, 2 → 4 y 3 → 4 en una transacción (`_script`); aditiva: no se pierde ni se reescribe ninguna fila. Una versión anterior rechaza una base de versión 4 como «esquema desconocido».

**Qué NO hay en la tabla**: el texto ni el estado de los criterios (se leen de su fuente en cada renovación), el bloque ya armado (se arma en cada renovación), ni ninguna salida del modelo.

### Ejemplo normativo (E1): filas de una sesión con tarea

Tarea «TAREA-14: Validar el correo», con reglas y 2 criterios, y un prefijo de tres provisionales (entorno, git y comandos):

| sesion_id | clave | orden | valor | origen |
|---|---|---|---|---|
| `s1` | `ticket` | 1 | `TAREA-14: Validar el correo` | `tarea (título)` |
| `s1` | `objetivo` | 1 | `Rechazar correos sin dominio en el formulario de alta.` | `tarea (objetivo)` |
| `s1` | `reglas` | 1 | `No tocar el esquema de la base.` + salto + `Mantener la API pública.` | `tarea (reglas)` |
| `s1` | `criterios_ref` | 1 | `s1` | `criterios protegidos (HU-11-01)` |
| `s1` | `instrucciones` | 1 | texto exacto del aviso de entorno | `entorno` |
| `s1` | `instrucciones` | 2 | texto exacto de las reglas de git | `git` |
| `s1` | `instrucciones` | 3 | texto exacto del aviso de comandos | `comandos` |

Una tarea sin título ni reglas no guarda las filas `ticket` ni `reglas`. Sin comandos de la tarea no hay fila de comandos (el prefijo tiene solo dos mensajes).

## `core/context/essential.py` (puro)

| Tipo / función | Forma |
|---|---|
| `KEY_OBJECTIVE`, `KEY_RULES`, `KEY_TICKET`, `KEY_CRITERIA_REF`, `KEY_INSTRUCTIONS` | Las cinco claves (constantes de texto) |
| `MARK` | `[contexto esencial de la tarea]` |
| `MAX_ELEMENT_CHARS` | 8 000 |
| `MAX_BLOCK_SHARE_PERCENT` | 20 |
| `EssentialItem` | `@dataclass(frozen=True)`: `key: str`, `order: int`, `value: str`, `origin: str`; valida clave conocida, `order ≥ 1` y valor y origen no vacíos |
| `make_items(*, ticket, objective, rules, instructions) -> tuple[EssentialItem, ...]` | Limpia (caracteres ocultos fuera, credenciales de URL ocultas con `core/redaction.py`), comprueba `MAX_ELEMENT_CHARS` sobre el valor **limpio** (`EssentialContextTooLarge` si lo excede; nunca trunca), omite lo ausente y añade un `EssentialItem` por instrucción (`instructions: Sequence[tuple[str, str]]` = origen y texto, sin limpiar ni tope). Exige objetivo y al menos una instrucción. No recibe el identificador de sesión (no existe antes de `start_task`) |
| `criteria_reference(session_id) -> EssentialItem` | El elemento `criterios_ref` (orden 1; el identificador de la sesión como valor) que la composición añade tras `start_task` |
| `render_block(items, criteria) -> str` | El texto del bloque (`contracts/block_format.md`); ignora la clave `instrucciones`; `criteria: Sequence[TaskCriteriaItem]` |
| `block_fits(text, settings, model) -> bool` | `estimate_message(SYSTEM, text) ≤ threshold_tokens × 20 // 100` |
| `check_block(items, criteria, settings, model) -> str` | Arma el texto y lo valida: la sección de criterios ≤ 8 000 caracteres (`EssentialContextTooLarge("criterios", 8000, "caracteres")`) y el mensaje ≤ el tope del 20 % (`EssentialContextTooLarge("bloque completo", <límite>, "tokens")`); devuelve el texto. Lo usan `check_creation` y el renovador |
| `check_creation(items, criteria_descriptions, settings, model) -> str` | Arma los criterios **pendientes** de las descripciones de la definición y llama a `check_block`; se usa antes de abrir el almacén |
| `find_blocks(history) -> list[int]` | Posiciones de los mensajes bloque dentro del prefijo `SYSTEM` contiguo (`contracts/block_marker.md`) |
| `block_message(text) -> Message` | `Message(Role.SYSTEM, text)` |
| `instruction_messages(items) -> list[Message]` | Los `SYSTEM` del registro, en orden de `orden` (para reconstruir; nunca se inyecta) |
| `EssentialContextError` (`ValueError`), `EssentialContextTooLarge(element, limit, unit)`, `EssentialContextUnavailable(missing)` | Errores de dominio con los tres mensajes fijos de R16; llevan `element`, `limit`, `unit` o `missing` como atributos y nunca un valor |

## `core/context/renewer.py` (puro, con colaboradores inyectados)

| Tipo | Forma |
|---|---|
| `EssentialSource` (`Protocol`) | `items(session_id: str) -> Sequence[EssentialItem]` (solo lectura) |
| `CriteriaReader` (`Protocol`) | `load_criteria(session_id: str) -> Sequence[TaskCriteriaItem]` (solo lectura; `SqliteTaskStore` lo cumple sin cambios) |
| `RenewalOutcome` (`Enum`) | `INSERTED`, `REPLACED`, `UNCHANGED` (no hay «sin bloque»: R15) |
| `EssentialRenewer(source, criteria, settings, *, session_id, model)` | `renew(history: list[Message]) -> RenewalOutcome`: síncrono; sustituye **in situ**; solo existe en sesiones con tarea. Falla cerrada con `EssentialContextUnavailable(missing=True)` si faltan `objetivo`, `criterios_ref` o toda `instrucciones`, con `EssentialContextUnavailable(missing=False)` ante cualquier `Exception` de la fuente o del lector (sin su texto) y con `EssentialContextTooLarge`; nunca captura `BaseException` |

## `adapters/storage/essential_store.py`

`SqliteEssentialStore(store: SqliteSessionStore, *, clock=…)` cumple `EssentialSource` sobre la conexión compartida (`SqliteSessionStore.connection()`), con las mismas reglas que `save_event` (`BEGIN IMMEDIATE`, `COMMIT`/`ROLLBACK`). Métodos: `save_items(session_id, items)` (una vez) e `items(session_id)` (ordenados por clave y orden). Errores del motor → `SessionStoreError` con mensaje fijo, sin valores.

## Estados y relaciones

```text
historial de la sesión (memoria) =
   [SYSTEM provisionales…] [SYSTEM bloque esencial] [USER petición inicial] [USER externo: resumen?] [región antigua] [ventana reciente]
   └───────────── cabeza protegida (HU-02-03) ──────────────┘

contexto_esencial (SQLite, escritura única) ── objetivo, reglas, ticket, criterios_ref ──▶ bloque (se arma en cada renovación)
                                              └─ instrucciones (registro, nunca se inyecta) ──▶ solo reconstruir
criterios (SQLite protegido, HU-11-01) ── texto y estado, por el lector de solo lectura ──▶ bloque
```
