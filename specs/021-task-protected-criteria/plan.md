# Implementation Plan: HU-11-01 — Tarea con criterios de aceptación protegidos en SQLite

**Branch**: `feat/hu-11-01-task-protected-criteria` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)

## Summary

Una tarea (Markdown, de archivo o de un issue de `gh`) se valida con una función pura del núcleo y se inicia en **una sola transacción** de SQLite: sesión nueva con el objetivo, filas en `criterios` (todas `passes` falso), un sello de integridad y la copia JSON de solo lectura. Un decorador de `PermissionPolicy` niega a las herramientas (y al shell, por coincidencia literal) tocar la base y las copias. Una verificación compara la huella de la copia con lo que SQLite produciría, la restaura y publica `criteria_tampered`. El esquema pasa a la versión 2 con migración. Sin cambios en puertos, eventos, bucle ni CLI.

## Technical Context

**Language/Version**: Python 3.12.x, sin dependencias de ejecución nuevas (`sqlite3`, `hashlib`, `json`, `subprocess` solo en `adapters/`).
**Storage**: SQLite (`adapters/storage/`), esquema v1 → v2 (migración en `_schema.py`).
**Testing**: pytest (`asyncio_mode=auto`), sin red, sin `gh` real, sin consola; `tmp_path` para bases y copias.
**Target Platform**: Windows y Linux (CI de ambos).
**Constraints**: `core/` solo stdlib y `harness_agent.core`; fallar cerrado; mensajes fijos en español sin reproducir valores; 100 % líneas y ramas de los módulos nuevos; ruta Windows ≤ 260.
**Scale/Scope**: tareas de hasta 64 KiB y 100 criterios.

## Constitution Check

| Principio / regla | Cumple | Nota |
|---|---|---|
| I–IV (núcleo puro, puertos, falla cerrada, pruebas primero) | Sí | Analizador y decorador en `core/`; E/S en adaptadores; el decorador deniega ante cualquier error |
| V (AC inmutables) | Sí | AC-01 a AC-03 copiados sin tocar |
| VI (sprint activo) | Sí | Todo es Sprint 2; HU-11-03, HU-11-04.1, HU-02-06.1, HU-05-02 quedan fuera |
| VII (contexto mínimo) | Sí | Solo se leyeron las secciones necesarias |
| VIII (PROGRESO) | Sí | Se actualiza al cerrar |
| X (no tocar `docs/archivo/`) | Sí | |
| Puertos y 17 eventos sin cambio | Sí | `TaskCriteria` se implementa tal cual; `criteria_tampered` ya existe. **Hallazgos** para A, B y C: el puerto no expone tipo, condición ni creación; `SessionStore` no tiene `create_session` |
| Hard Rules de las tres skills | Sí | Ver lista y tabla de rutas |

### Recorrido de los Decision Gates (`arquitectura-hexagonal-clean`)

| Pregunta | Resultado |
|---|---|
| ¿Regla nueva? | Formato/validación de la tarea y política de protección → `core/tasks/` y `core/permissions/protected.py` |
| ¿Necesita algo de fuera? | Disco y SQLite → adaptadores; para la protección se reutiliza el puerto `AuthorizedArea` (sin puerto nuevo); para el registro, el puerto `EventBus` |
| ¿Quién lo implementa? | `adapters/storage/` (criterios), `adapters/system/` (rutas protegidas), `adapters/tasks/` (archivo y `gh`) |
| ¿Cómo se conecta? | Constructores; `bootstrap.compose(..., task=...)` |
| ¿Cómo se prueba? | Núcleo con dobles (`ScriptedPolicy`, `RecordingEventBus`, `DummyAuthorizedArea`); adaptadores reales con SQLite y disco temporales; prueba de contrato de `TaskCriteria` |
| ¿Asíncrono? | No: todo es síncrono (como el puerto) |

### Lista de comprobación de `capas-y-reglas.md` (respuesta de diseño; se revisa de nuevo al cerrar)

- La regla está en `core/` y no en un adaptador: **sí** (analizador, decorador).
- Todo lo externo pasa por un puerto con tipos del dominio: **sí** (`TaskCriteria`, `AuthorizedArea`, `EventBus`, `PermissionPolicy`); `gh` y archivos solo en adaptadores, inyectables.
- Puertos, entidades y eventos sin cambio: **sí**.
- Errores externos traducidos sin reproducir valores: **sí** (`TaskSourceError`, `CriteriaIntegrityError`, `SessionStoreError`).
- Dependencias por constructor y conexión solo en `bootstrap.py`: **sí**.
- Núcleo probado con dobles, sin red ni disco: **sí**.
- Adaptador real con prueba de contrato en `tests/contracts/`: **sí** (`test_task_criteria_contract.py`).
- `pytest tests/architecture` más guardas nuevas: **sí** (`test_tasks_boundaries.py`, `test_protected_policy_boundaries.py`, ampliación de `test_adapters_boundaries.py`).
- Núcleo emite eventos en lugar de imprimir: **sí** (`criteria_tampered` desde el adaptador por el bus inyectado; el núcleo no imprime).
- Lo público exportado en `core/__init__.py`: **sí**.
- Falla cerrada, secretos: **sí** (PD-10 sigue abierta).
- Revisión por otra área: **no todavía** (tarea humana).

## Project Structure

### Documentation (this feature)

```text
specs/021-task-protected-criteria/
├── spec.md · plan.md · research.md · data-model.md · quickstart.md · tasks.md
├── checklists/requirements.md
└── contracts/ task_format.md · criteria_store.md · protected_policy.md
```

### Source Code y fila de `estructura-carpetas-harness` que justifica cada ruta

| Ruta (nueva salvo indicación) | Fila de la tabla | Contenido |
|---|---|---|
| `src/harness_agent/core/tasks/{__init__,definition,parser,errors}.py` | Regla de negocio en subpaquete de `core/` + error de dominio en `errors.py` | `TaskDefinition`, `CriterionDefinition`, `CriterionKind`, `parse_task`, `TaskFormatError`, límites |
| `src/harness_agent/core/permissions/protected.py` | Regla del núcleo (permisos) | `ProtectedPolicy(inner, area, shell_markers)` |
| `src/harness_agent/core/permissions/__init__.py`, `core/__init__.py` (existentes) | Exportar lo público | |
| `src/harness_agent/adapters/storage/_schema.py` (existente) | Almacén SQLite | `SCHEMA_VERSION = 2`, migración 1→2, tablas `criterios` y `criterios_sello` |
| `src/harness_agent/adapters/storage/criteria_export.py` | Código con disco/hash | JSON determinista, huella, escritura de solo lectura y restauración |
| `src/harness_agent/adapters/storage/task_store.py` | Nuevo almacén (receta) | `SqliteTaskStore(TaskCriteria)`: `start_task`, `load_criteria`, `get_pending`, `mark_passes`, `export_readonly_copy`, `verify_export` |
| `src/harness_agent/adapters/storage/errors.py`, `__init__.py`, `sqlite_session_store.py` (existentes) | | `CriteriaIntegrityError`, `CriteriaNotFound`; método `connection()` para el almacén hermano |
| `src/harness_agent/adapters/system/protected_paths.py` | Código con disco | `ProtectedPaths(AuthorizedArea)`: archivos y carpetas protegidos por ruta real |
| `src/harness_agent/adapters/tasks/{__init__,task_source,errors}.py` | Código con disco/`subprocess` (carpeta nueva para esta historia) | `read_task_file`, `fetch_issue_task` con `GhRunner` inyectable, `TaskSourceError` |
| `src/harness_agent/bootstrap.py`, `config.py` (existentes) | Raíz de composición | `compose(..., task=)`, política envuelta; `config.py` sin cambios |
| `tests/unit/core/tasks/`, `tests/unit/core/permissions/test_protected_policy.py`, `tests/unit/adapters/{storage,system,tasks}/`, `tests/unit/test_bootstrap_task.py`, `tests/contracts/test_task_criteria_contract.py`, `tests/integration/test_task_protection_agent_loop.py`, `tests/architecture/test_{tasks,protected_policy}_boundaries.py` | Espejo de `src/` | |
| `docs/guia-contratos-desarrollo.md`, `CLAUDE.md`, `arbol.md` y `verificar-fronteras-hexagonales/SKILL.md` de `.claude/skills/` y `.agents/skills/` | Documentación viva | |

### Decisiones clave (detalle en `research.md`)

1. Markdown como formato único; analizador puro.
2. Alta atómica: sesión + criterios + sello + archivo dentro de una transacción `BEGIN IMMEDIATE`; si falla el archivo, rollback; si falla el commit, se borra el archivo.
3. La huella de la copia es el SHA-256 de su contenido canónico, que es también el sello guardado en SQLite.
4. Protección por decorador, sin tocar `DefaultPermissionPolicy`; por ruta real (`AuthorizedArea`) y por coincidencia literal en `command` del shell.
5. Anomalía = evento `criteria_tampered` (sin contenido) por el bus inyectado.

## Complexity Tracking

| Desviación | Por qué | Alternativa descartada |
|---|---|---|
| Método público `connection()` en `SqliteSessionStore` (B) | El alta debe ser atómica con la sesión | Dos conexiones: no atómico |
| Carpeta nueva `adapters/tasks/` | Origen de la tarea (archivo, `gh`) no encaja en las existentes | Meterlo en `storage/` (mezcla roles) |
| Hallazgos de puertos sin ampliarlos | Regla dura | Ampliar `TaskCriteria`/`SessionStore`: requiere acuerdo de A, B y C |
