# Implementation Plan: HU-03-01 — Esquema SQLite y creación de sesión

**Branch**: `feat/hu-03-01-sqlite-session-schema` (directorio de la spec: `014-sqlite-session-schema`) | **Date**: 2026-10-23 | **Spec**: [specs/014-sqlite-session-schema/spec.md](spec.md)

**Input**: Feature specification from `/specs/014-sqlite-session-schema/spec.md`

---

## Summary

Un paquete nuevo de adaptadores, `adapters/storage/`, sin tocar `core/` ni ningún puerto:

1. `_schema.py`: DDL de las tablas `sessions` y `events`, número de versión (`PRAGMA user_version`) y la función que crea o valida el esquema al abrir.
2. `sqlite_session_store.py`: `SqliteSessionStore(path, *, clock, id_factory)` con `create_session`, `get_session`, `list_sessions`, `close` y gestor de contexto, y el tipo inmutable `StoredSession`.
3. `errors.py`: `SessionStoreError` y dos subclases (`SchemaVersionError`, `ParentSessionNotFound`); los fallos de `sqlite3` se traducen a ellas sin datos de entrada.

`SqliteSessionStore` **no** hereda todavía de `SessionStore` (decisión de la clarificación): `save_event`/`load_session` son de HU-03-02. La guarda `ast` de `adapters/` añade `storage` a `GUARDED`.

---

## Technical Context

**Language/Version**: Python 3.12 (PD-07).

**Primary Dependencies**: solo biblioteca estándar (`sqlite3`, `uuid`, `datetime`, `pathlib`, `dataclasses`, `collections.abc`, `types`). Sin dependencias nuevas.

**Storage**: SQLite por archivo (`.harness/sessions.db` por defecto, `HarnessConfig.paths.sessions_db`) o `:memory:` en pruebas.

**Testing**: `pytest`; archivos en `tmp_path`; reloj e ids inyectados; sin red ni claves.

**Target Platform**: Windows y Linux (CI en ambos).

**Project Type**: Biblioteca modular; adaptador de la capa exterior.

**Performance Goals**: crear una sesión < 100 ms (SC-003).

**Constraints**:
1. `core/` (incluido `core/interfaces/storage.py` y `core/events.py`) y `tests/doubles/` sin modificar.
2. `adapters/storage/` importa solo biblioteca estándar, `harness_agent.core` (API pública) y su propio paquete; no importa `config`, `cli`, `observability`, `bootstrap` ni otro adaptador; no lee entorno ni configuración; no usa la terminal.
3. Consultas siempre con parámetros enlazados; claves foráneas activas (`PRAGMA foreign_keys = ON`).
4. `mypy --strict`, `ruff` a 100 columnas; identificadores en inglés; mensajes de error en español sin reproducir datos.
5. Falla cerrada: versión de esquema desconocida → error, sin modificar la base.
6. Sin `save_event`/`load_session`, sin modo WAL ni durabilidad (HU-03-02), sin tablas de otras historias (Principio VI).

**Scale/Scope**: 4 módulos de código, 3 archivos de prueba unitaria y 1 ampliación de la guarda; unas 250 líneas de código.

---

## Constitution Check

| Principio / Restricción | Requisito | Pre-diseño | Post-diseño | Evidencia |
|---|---|---|---|---|
| I. Una historia por especificación | Solo HU-03-01 | Pasa | Pasa | Spec y plan solo de HU-03-01 |
| II. Microtareas de 15 a 40 min | Ninguna tarea pasa de 40 min | Pasa | Pasa | `tasks.md` |
| III. Núcleo modular, tipado, sin dependencias externas | `core/` intacto; adaptador con stdlib | Pasa | Pasa | D1, D2 |
| IV. Pruebas, calidad y CI multiplataforma | Pruebas primero; ruff, mypy, pytest en Windows y Linux | Pasa | Pasa | Cada tarea escribe la prueba antes; rutas con `tmp_path` |
| V. Inmutabilidad de criterios | AC-01, regla 1 y flujo copiados tal cual | Pasa | Pasa | Spec |
| VI. Disciplina de sprints | Nada de sprints futuros | Pasa | Pasa | Sin eventos persistidos, sin reanudar, sin tablas de otras historias |
| VII. Consulta documental quirúrgica | Solo fuentes necesarias | Pasa | Pasa | HU-03-01, `docs/02` §4, puerto `SessionStore`, `config.py` |
| VIII. Registro en `docs/PROGRESO.md` | `En curso` y `En revisión` | Pasa | Pasa | Primera y última tarea |
| IX. Definition of Done estricta | Revisión cruzada y CI remota quedan humanas | Pasa | Pasa | Tareas humanas finales |
| X. Inmutabilidad de `docs/archivo/` | No se toca | Pasa | Pasa | `git diff` de cierre |
| Skill `arquitectura-hexagonal-clean` | Dependencias al núcleo; sqlite solo en adaptador; sin lógica de negocio en el adaptador; errores traducidos | Pasa | Pasa | D1 a D6 |
| Skill `estructura-carpetas-harness` | `adapters/storage/` (planeado para HU-03-01); prueba en `tests/unit/adapters/storage/` | Pasa | Pasa | Tabla de rutas |
| Skill `verificar-fronteras-hexagonales` | `storage` entra en `GUARDED` de `test_adapters_boundaries.py` | Pasa | Pasa | Tarea de guarda |
| V-02 falla cerrada | Versión desconocida y padre inexistente se rechazan | Pasa | Pasa | FR-003, FR-006 |
| Datos sensibles | Mensajes sin objetivo, modelo ni rutas | Pasa | Pasa | FR-011 |

No hay violaciones. Hallazgos que **no** impiden implementar: el puerto carece de `create_session` (observación para A, B y C); PD-09 (proteger `.harness/sessions.db`) sigue abierta.

---

## Decisiones de diseño

| ID | Decisión | Motivo |
|---|---|---|
| D1 | El almacén vive en `adapters/storage/` y no hereda aún de `SessionStore`. | La receta de almacén lo sitúa ahí; heredar exigiría `save_event`/`load_session` (HU-03-02). |
| D2 | No se modifica ningún puerto; `create_session`/`get_session` son del adaptador y devuelven `StoredSession` (frozen, con `parent_id`). | Contrato protegido; `SessionSummary` no tiene padre. |
| D3 | Tablas `sessions` y `events` según `data-model.md`; fechas en ISO-8601 UTC con zona. | `docs/02` §4 con nombres en inglés (decisión 2026-10-17). |
| D4 | Versión del esquema en `PRAGMA user_version` (`SCHEMA_VERSION = 1`). Base nueva → se crea; igual → se acepta; mayor → `SchemaVersionError` sin escribir. | Falla cerrada; permite migraciones futuras. |
| D5 | Reloj (`Callable[[], datetime]`) e ids (`Callable[[], str]`) se inyectan por constructor con valores por defecto UTC y `uuid4`. Un `datetime` sin zona se interpreta como UTC. | Determinismo e inyección. |
| D6 | Los `sqlite3.Error` se traducen a `SessionStoreError` con mensaje fijo en español, sin ruta ni datos. Un padre inexistente se detecta antes de insertar con una consulta (no solo por la clave foránea) para dar `ParentSessionNotFound`. | FR-006, FR-011. |
| D7 | `path` acepta `str` o `os.PathLike` o `":memory:"`; el directorio padre se crea con `mkdir(parents=True, exist_ok=True)` salvo en `:memory:`. | `.harness/` no existe en una instalación nueva. |
| D8 | Una sola conexión por almacén; cada escritura dentro de `with conn:`; `close()` idempotente; uso tras cerrar → `SessionStoreError`. | Sencillez; la concurrencia es de HU-03-02. |
| D9 | `list_sessions` ordena por `created_at, rowid`. | Estable aunque dos sesiones compartan fecha. |
| D10 | `bootstrap.py` no existe: la raíz de composición deberá hacer `SqliteSessionStore(config.paths.sessions_db)`; se anota, no se implementa. | Principio VI. |

---

## Verificación contra las skills del proyecto

Skills cargadas: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness` y `verificar-fronteras-hexagonales`.

### Decision Gates (`arquitectura-hexagonal-clean`)

| Pregunta | Resultado |
|---|---|
| ¿Es regla o comportamiento nuevo? | No hay regla de negocio nueva; es persistencia. Va al adaptador. |
| ¿Necesita algo de fuera? | Sí, disco/SQLite: es el adaptador del puerto `SessionStore` (aún parcial). Sin puerto nuevo. |
| ¿Quién lo implementa? | `adapters/storage/` (usa `sqlite3`). |
| ¿Cómo se conecta? | Constructor (ruta, reloj, ids); la raíz de composición futura pasa `config.paths.sessions_db`. |
| ¿Cómo se prueba? | Unitarias con `tmp_path` y `:memory:`; guarda `ast`. Contrato con `InMemorySessionStore`: pospuesto a HU-03-02. |
| ¿Es asíncrono? | No: `SessionStore` es síncrono. |

### Ruta elegida (`estructura-carpetas-harness`)

| Archivo nuevo | Fila de la tabla | Prueba equivalente |
|---|---|---|
| `adapters/storage/__init__.py`, `errors.py`, `_schema.py`, `sqlite_session_store.py` | «Código con `sqlite3`…» → `adapters/<subpaquete>/`; error de dominio → `errors.py` del subpaquete | `tests/unit/adapters/storage/` |
| `tests/architecture/test_adapters_boundaries.py` (ampliado) | Guarda de la frontera de `adapters/` | — |

### Lista de comprobación (`capas-y-reglas.md`)

- [x] ¿La regla de negocio está en `core/`? N.A.: no hay regla nueva; el adaptador solo persiste.
- [x] ¿Todo lo externo pasa por un puerto con tipos del dominio? Parcial: el adaptador es el lado SQLite del puerto `SessionStore`; `create_session` queda fuera del puerto (hallazgo, no se cambia sin acuerdo de A, B y C).
- [x] ¿Puertos, entidades y eventos sin cambios? Sí (`git diff` de `core/` vacío).
- [x] ¿Errores externos traducidos sin reproducir valores? Sí: `SessionStoreError` (D6).
- [x] ¿Dependencias por constructor y conexión en `bootstrap.py`? Sí; `bootstrap.py` no existe y se anota (D10).
- [x] ¿El núcleo se probó con dobles? N.A.: no se toca el núcleo; el adaptador se prueba con `tmp_path` y `:memory:`.
- [ ] ¿Prueba de contrato en `tests/contracts/`? **No**: la clase aún no implementa el puerto completo; el contrato se añade en HU-03-02 (justificado).
- [x] ¿Pasa `pytest tests/architecture` y la guarda nueva? Se comprueba al cerrar (Windows y Linux por la CI).
- [x] ¿El núcleo emite eventos en lugar de imprimir? Sin cambios; el adaptador no imprime (guarda).
- [x] ¿Lo público está exportado? `adapters/storage/__init__.py`; `core/__init__.py` sin cambios; el adaptador importa de `harness_agent.core` solo `SessionSummary`.
- [x] ¿Decisiones de diseño respetadas (falla cerrada, sin secretos)? Sí.
- [ ] ¿Otro integrante revisó el cambio? **No todavía** (tarea humana).

### Fronteras (`verificar-fronteras-hexagonales`)

`pytest tests/architecture` se corre al cerrar; `storage` entra en `GUARDED`. Sin archivos que violen reglas: `core/` no importa `sqlite3`.

---

## Project Structure

### Documentation (this feature)

```text
specs/014-sqlite-session-schema/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── sqlite_session_store_contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
src/harness_agent/adapters/storage/          # NUEVO
├── __init__.py              # API pública
├── errors.py                # SessionStoreError, SchemaVersionError, ParentSessionNotFound
├── _schema.py               # DDL, SCHEMA_VERSION, ensure_schema
└── sqlite_session_store.py  # SqliteSessionStore, StoredSession

tests/
├── unit/adapters/storage/
│   ├── __init__.py
│   ├── test_errors.py
│   ├── test_schema.py
│   └── test_sqlite_session_store.py
└── architecture/test_adapters_boundaries.py   # + "storage" en GUARDED

docs/PROGRESO.md                                    # fila HU-03-01 y registro
docs/guia-contratos-desarrollo.md                   # nota de uso (almacenamiento)
.claude/skills/estructura-carpetas-harness/references/arbol.md   # storage/ pasa de planeado a existente
.agents/skills/estructura-carpetas-harness/references/arbol.md   # misma copia
```

**Structure Decision**: Single project; solo se crea `adapters/storage/`, ya prevista por el árbol. `bootstrap.py` sigue sin existir.
