# Data Model: HU-11-01

## Dominio (`core/tasks/`, todo `@dataclass(frozen=True)`)

- `CriterionKind(str, Enum)`: `OBJECTIVE = "objetivo"`, `SEMANTIC = "semantico"`.
- `CriterionDefinition`: `description: str`, `command: str | None`, `expectation: str | None`; propiedad `kind` (objetivo si hay comando). Invariante: `command` y `expectation` están ambos o ninguno.
- `TaskDefinition`: `title: str | None`, `objective: str`, `context: str`, `rules: str`, `criteria: tuple[CriterionDefinition, ...]` (≥ 1).
- `TaskFormatError(ValueError)` con `code` (`vacia`, `demasiado_grande`, `sin_objetivo`, `sin_criterios`, `criterio_incompleto`, `seccion_repetida`, `seccion_desconocida`, `contenido_no_valido`, `demasiados_criterios`, `texto_demasiado_largo`, `formato_no_valido`) y mensaje fijo en español.
- Límites: `MAX_TASK_CHARS = 65_536`, `MAX_CRITERIA = 100`, `MAX_FIELD_CHARS = 2_000`.

## Esquema SQLite v2 (migración desde v1)

```sql
CREATE TABLE criterios (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    sesion_id      TEXT NOT NULL REFERENCES sessions(id),
    orden          INTEGER NOT NULL CHECK (orden >= 1),
    descripcion    TEXT NOT NULL CHECK (length(trim(descripcion)) > 0),
    tipo           TEXT NOT NULL CHECK (tipo IN ('objetivo', 'semantico')),
    comando        TEXT,
    condicion      TEXT,
    passes         INTEGER NOT NULL DEFAULT 0 CHECK (passes IN (0, 1)),
    evidencia      TEXT,
    confirmado_por TEXT,
    UNIQUE (sesion_id, orden),
    CHECK ((tipo = 'objetivo' AND comando IS NOT NULL AND condicion IS NOT NULL)
        OR (tipo = 'semantico' AND comando IS NULL AND condicion IS NULL)),
    CHECK (passes = 0 OR (evidencia IS NOT NULL AND length(trim(evidencia)) > 0))
);
CREATE TABLE criterios_sello (
    sesion_id TEXT PRIMARY KEY REFERENCES sessions(id),
    huella    TEXT NOT NULL
);
PRAGMA user_version = 2;
```

## Copia exportada (`<carpeta del harness>/tareas/<sesión>/criterios.json`)

Lista JSON ordenada por `orden`, claves ordenadas, `indent=2`, UTF-8, `\n` final:
`{"comando"?, "descripcion", "espera"?, "evidencia"?, "id", "passes", "tipo", "verificacion"?}` — el prototipo de la ficha: los objetivos llevan `verificacion: {"comando", "espera"}`; `evidencia` solo si existe. Huella = SHA-256 hexadecimal del contenido.

## Adaptador

- `StartedTask(session_id: str, export_path: Path)` (frozen).
- `SqliteTaskStore(store, *, exports_dir, bus=None, clock=None, id_factory=None)`.
- Estados de un criterio: `passes` falso → verdadero solo con `mark_passes` (evidencia obligatoria). No hay transición inversa en esta historia.
- Errores (`adapters/storage/errors.py`): `CriteriaIntegrityError`, `CriteriaNotFound`, `ExportError`; todos `SessionStoreError`, mensajes fijos.

## Fuente (`adapters/tasks/`)

- `TaskSourceError` (mensajes fijos, sin la salida de `gh` ni la ruta).
- `GhRunner = Callable[[Sequence[str]], str]`.

## Protección

- `ProtectedPolicy(inner: PermissionPolicy, area: AuthorizedArea, shell_markers: Sequence[str])`.
- `ProtectedPaths(files: Iterable[Path], directories: Iterable[Path])` implementa `AuthorizedArea`.
