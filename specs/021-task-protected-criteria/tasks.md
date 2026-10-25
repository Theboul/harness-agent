# Implementation Tasks: HU-11-01 — Tarea con criterios de aceptación protegidos en SQLite

**Feature**: `specs/021-task-protected-criteria/spec.md`  
**Plan**: `specs/021-task-protected-criteria/plan.md`  
**Responsable**: A — Núcleo  
**Sprint**: Sprint 2 | **PHU**: 2  
**Tareas de referencia**: Sp2-37 a Sp2-42 (presupuesto 8,5 h; los tiempos son referencia, no restricción)

---

## Cómo leer este documento

**Pruebas primero, dentro de cada tarea.** Se escriben, se ejecutan y se confirma que fallan **por la razón esperada**, se implementa lo mínimo y se repite hasta que pasen. El rojo se anota en una línea en `PROGRESO.md`.

**Reglas que valen para todas las tareas:**
- **Archivos protegidos**: no modificar `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `core/permissions/policy.py` ni `rules.py`, `cli/`, `tests/doubles/`, `docs/archivo/`. Existentes que sí se tocan: `core/__init__.py`, `core/permissions/__init__.py`, `adapters/storage/` (`_schema.py`, `errors.py`, `__init__.py`, `sqlite_session_store.py` solo con el método `connection()`), `adapters/system/__init__.py`, `bootstrap.py`, `docs/PROGRESO.md`, `docs/guia-contratos-desarrollo.md`, `CLAUDE.md`, `arbol.md` y `verificar-fronteras-hexagonales/SKILL.md` de `.claude/skills/` y `.agents/skills/`, `tests/integration/test_core_public_api.py` (solo la lista de nombres públicos) y las pruebas que fijen `SCHEMA_VERSION == 1`.
- `core/tasks/` y `core/permissions/protected.py`: solo biblioteca estándar y `harness_agent.core`; sin `os`, `sqlite3`, `subprocess`, `print`. `sqlite3`, `hashlib` para archivos, `subprocess` solo en `adapters/`.
- Código, identificadores y docstrings en inglés; mensajes al usuario y documentación en español, fijos, sin reproducir el valor recibido. Valor centinela: `VALOR-DE-PRUEBA-123`. Línea de 100 columnas. Python 3.12, sin dependencias nuevas.
- Cobertura de los módulos nuevos: 100 % de líneas y ramas. Sin red, sin `gh` real, sin consola.
- **Commits** (estilo del proyecto): español, sin coautor ni pie de atribución, `tipo(ámbito): descripción (HU-11-01)`; rama `feat/hu-11-01-task-protected-criteria`; sin push, merge ni PR sin confirmación humana.
- **Al cerrar cada tarea con código**: `ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest` con código 0 y `pytest tests/architecture`.
- **Skills**: plan hecho con `arquitectura-hexagonal-clean`, `estructura-carpetas-harness` y `verificar-fronteras-hexagonales`; T012 y T014 vuelven a pasar sus listas.
- **Windows**: `.venv` de Python 3.12 del repositorio principal con `PYTHONPATH=src` desde este worktree.

---

## Phase 1: Inicio

- [x] T001 Comprobar la línea base: rama cortada de `origin/main` (3d466eb), `pytest -q` y `pytest tests/architecture` en verde antes de tocar nada; anotar cuántas pruebas pasan.

## Phase 2: US1 — Iniciar una tarea desde un archivo (P1) · Sp2-37, Sp2-38, Sp2-42

**Independent test**: archivo válido → sesión, filas con `passes` falso y copia de solo lectura; sin criterios → rechazo sin rastro.

- [x] T002 [US1] (Sp2-37) Formato y validación: `src/harness_agent/core/tasks/{__init__,definition,parser,errors}.py` y exportar en `core/__init__.py`; pruebas en `tests/unit/core/tasks/` (contrato `contracts/task_format.md`: secciones, criterios objetivo/semántico, desparejados, repetidos, desconocidos, límites, caracteres de control, mensajes sin eco del valor).
- [ ] T003 [US1] (Sp2-38) Migración del esquema: `adapters/storage/_schema.py` a la versión 2 (`criterios`, `criterios_sello`), migración 1→2 transaccional; pruebas en `tests/unit/adapters/storage/test_schema_migration.py` (base v1 con datos, base nueva, v2 aceptada, versión desconocida rechazada, restricciones `CHECK`); ajustar las pruebas existentes que fijen la versión 1.
- [ ] T004 [US1] (Sp2-38/40) Exportación canónica: `adapters/storage/criteria_export.py` (JSON determinista, huella SHA-256, escritura de solo lectura con reemplazo atómico, quitar la marca antes de reemplazar, eliminar archivo/enlace/carpeta en la ruta exacta); pruebas en `tests/unit/adapters/storage/test_criteria_export.py`.
- [ ] T005 [US1] (Sp2-38/42) Almacén: `adapters/storage/task_store.py` (`SqliteTaskStore`: `start_task` atómico, `load_criteria`, `get_pending`, `mark_passes`, `export_readonly_copy`), errores nuevos en `errors.py`, `connection()` en `sqlite_session_store.py`, exportar en `adapters/storage/__init__.py`; pruebas en `tests/unit/adapters/storage/test_task_store.py` y contrato en `tests/contracts/test_task_criteria_contract.py` (rollback si falla la copia, sin rastro si falla la validación, ids, evidencia obligatoria).

## Phase 3: US4 — La copia JSON alterada se restaura (P1) · Sp2-40

**Independent test**: modificar/borrar/reemplazar la copia → `verify_export` la restaura y publica `criteria_tampered`.

- [ ] T006 [US4] (Sp2-40) `verify_export`, sello e integridad: ampliar `task_store.py` (huella contra lo que SQLite produciría, restauración, evento `criteria_tampered` sin contenido por el bus inyectado, `CriteriaIntegrityError` si una fila viola las reglas o el sello no coincide, `ExportError` si no se puede restaurar); pruebas en `tests/unit/adapters/storage/test_task_store_tamper.py`.

## Phase 4: US3 — Los criterios no se pueden tocar con las herramientas (P1) · Sp2-39

**Independent test**: con la política real, las cinco herramientas sobre `.harness/` se deniegan; el resto no cambia.

- [ ] T007 [US3] (Sp2-39) `src/harness_agent/core/permissions/protected.py` (`ProtectedPolicy`, contrato `contracts/protected_policy.md`), exportar en `core/permissions/__init__.py` y `core/__init__.py`; pruebas en `tests/unit/core/permissions/test_protected_policy.py` con dobles (`ScriptedPolicy`, `DummyAuthorizedArea`): ruta protegida, shell con marcador, delegación, excepción → DENY, limitación documentada con un caso no detectado.
- [ ] T008 [US3] (Sp2-39) `adapters/system/protected_paths.py` (`ProtectedPaths`: archivos con `-wal/-shm/-journal` y carpetas, ruta real, mayúsculas de Windows, `..`, enlaces, fallo cerrado) y exportar en `adapters/system/__init__.py`; pruebas en `tests/unit/adapters/system/test_protected_paths.py` con batería de rutas hostiles.

## Phase 5: US2 — Iniciar una tarea desde un issue de GitHub (P2) · Sp2-41

**Independent test**: con un `runner` simulado, el issue produce la misma tarea que un archivo; los fallos no dejan efectos.

- [ ] T009 [US2] (Sp2-41) `adapters/tasks/{__init__,task_source,errors}.py`: `read_task_file(path)` (UTF-8, tamaño acotado) y `fetch_issue_task(number, runner=...)` (número positivo, `gh issue view N --json title,body`, `shell=False`, tiempo límite, título como respaldo); pruebas en `tests/unit/adapters/tasks/` (archivo ausente/enorme/binario, `gh` ausente, salida no JSON, sin eco de la salida de `gh`, número inválido sin lanzar proceso).

## Phase 6: Cableado e integración · Sp2-42

- [ ] T010 [US1] (Sp2-42) `bootstrap.py`: envolver la política con `ProtectedPolicy` (área `ProtectedPaths` y marcadores derivados de `paths.sessions_db`), crear `SqliteTaskStore`, `compose(..., task=)` que inicia la tarea (sesión de la composición = sesión de la tarea) y `Composition` con `task_store`, `task` y `criteria_export`; pruebas en `tests/unit/test_bootstrap_task.py`; sin tarea, el comportamiento actual no cambia.
- [ ] T011 [US3] Integración AC-01 a AC-03 en `tests/integration/test_task_start.py` y `tests/integration/test_task_protection_agent_loop.py`: bucle, política y registro reales; cinco herramientas sobre `.harness/` denegadas con evento `permission_decided`; copia alterada → restaurada + `criteria_tampered`; ningún proceso lanzado por el shell denegado (archivo marcador ausente).

## Phase 7: Frontera y cierre

- [ ] T012 (Sp2 transversal) Guardas y skills: `tests/architecture/test_tasks_boundaries.py` y `test_protected_policy_boundaries.py` (desde `verificar-fronteras-hexagonales/assets/test_module_boundaries.py` con autoprueba), añadir `adapters/tasks/` a la lista `GUARDED` de `test_adapters_boundaries.py`, y ampliar `test_bootstrap_boundaries.py` si hace falta; ejecutar `pytest tests/architecture`; responder sí/no la lista de `capas-y-reglas.md` contra el código; comprobar archivos protegidos con `git diff --exit-code`.
- [ ] T013 Documentación: `docs/guia-contratos-desarrollo.md`, `CLAUDE.md` (tabla «Qué existe hoy»), `arbol.md` y `verificar-fronteras-hexagonales/SKILL.md` en `.claude/skills/` y `.agents/skills/`.
- [ ] T014 Cierre: los cuatro comandos de calidad y `pytest tests/architecture` en exit 0, cobertura 100 % de módulos nuevos; `docs/PROGRESO.md` (fila a `En revisión`, archivos, evidencia, registro por tarea, **Observaciones de HU-11-01** para HU-02-06.1, HU-11-03, HU-11-04.1, HU-05-02, HU-IN-02, PD-09, PD-10 y los hallazgos de puertos); marcar aquí solo lo hecho.

## Phase 8: Tareas humanas (Claude no las marca)

- [ ] T015 Revisión cruzada por B o C del diff completo.
- [ ] T016 Ejecución de la CI en GitHub Actions (Ubuntu y Windows) y relleno de Commit/PR en `PROGRESO.md`.
- [ ] T017 Confirmaciones: A, B y C del hallazgo sobre `TaskCriteria`/`SessionStore` y del método `connection()` añadido a `SqliteSessionStore` (B); el PO de la decisión de denegar toda la carpeta del harness (PD-09) y de la limitación del shell (R-21).

---

## Dependencias y orden

T001 → T002 (independiente de T003–T004) → T003 → T004 → T005 → T006 → T010 → T011; T007 y T008 son independientes de T003–T006 (T007 → T008 → T010); T009 es independiente (antes de T010 si se quiere probar el flujo completo). T012–T014 al final.

## Presupuesto (Sp2-37 a Sp2-42 = 8,5 h)

| Tareas | Referencia | Horas |
|---|---|---|
| T002 | Sp2-37 | 1 |
| T003–T005 | Sp2-38 | 2 |
| T007–T008 | Sp2-39 | 1,5 |
| T004, T006 | Sp2-40 | 1,5 |
| T009 | Sp2-41 | 1,5 |
| T010–T011 | Sp2-42 | 1 |
