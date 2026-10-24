# Implementation Tasks: HU-03-01 — Esquema SQLite y creación de sesión

**Feature**: `specs/014-sqlite-session-schema/spec.md`  
**Plan**: `specs/014-sqlite-session-schema/plan.md`  
**Responsable**: B — Estado  
**Sprint**: Sprint 1 | **PHU**: 2  
**Tareas de referencia**: Sp1-26, Sp1-27, Sp1-28  

---

## Cómo leer este documento

**Pruebas primero, dentro de cada tarea.** Cada tarea agrupa las pruebas y la implementación de una pieza: se escriben las pruebas, se ejecutan y se confirma que fallan **por la razón esperada** (`ImportError` del símbolo nuevo o aserción de comportamiento, no un error de sintaxis), se implementa lo mínimo y se pasan los cuatro comandos de calidad.

**Ritmo**: 10 tareas de trabajo (T002 a T011) de 40 min como máximo, una de inicio (T001), una de verificación final (T012) y dos humanas (T013, T014). Ninguna pasa de 40 min (la Constitución permite 40; el límite absoluto es 60).

**Reglas que valen para todas las tareas:**
- **Archivos protegidos**: no modificar nada bajo `src/harness_agent/core/` (en particular `core/interfaces/` y `core/events.py`), ni `src/harness_agent/config.py`, ni `tests/doubles/`, ni `docs/archivo/`, ni ninguna prueba existente (salvo ampliar `GUARDED` en `tests/architecture/test_adapters_boundaries.py`, T009). Los únicos archivos existentes que se tocan son `docs/guia-contratos-desarrollo.md`, `docs/PROGRESO.md` y `references/arbol.md` de las dos copias de la skill `estructura-carpetas-harness`.
- `adapters/storage/` solo importa biblioteca estándar, `harness_agent.core` (`from harness_agent.core import ...`, nunca submódulos) y su propio paquete; no importa `config`, `cli`, `observability`, `bootstrap` ni otro adaptador; no lee entorno ni configuración ni usa la terminal.
- Todo el código y las pruebas deben pasar `mypy --strict` y `ruff` (línea de 100 columnas). Nombres de código en inglés; mensajes de error y documentación en español.
- Tipos, errores y garantías siguen [contracts/sqlite_session_store_contract.md](contracts/sqlite_session_store_contract.md) y [data-model.md](data-model.md); las decisiones, [research.md](research.md) y [plan.md](plan.md) (D1 a D10).
- **Aislamiento**: toda prueba que toca disco usa `tmp_path`; ninguna toca el repositorio ni el directorio personal ni la red.
- **Sin literales detectables**: ninguna prueba contiene texto que `tests/architecture/test_no_secrets_in_repo.py` detecte como clave; usar el centinela `VALOR-DE-PRUEBA-123` para comprobar que los mensajes de error no reproducen datos.
- **Commits** (estilo del proyecto): en español, sin coautor ni pie de sesión, formato `tipo(ámbito): descripción (HU-03-01)`; por ejemplo `feat(storage): esquema SQLite y creación de sesión (HU-03-01)`.
- **Al cerrar cada tarea que toca código o pruebas**, ejecutar `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`; los cuatro con código 0, y registrar el resultado.

**Correspondencia con las tareas del plan de sprint** (columna *Tarea F5*):

| Tarea F5 | Descripción en `docs/03-plan-sprints.md` | Presupuesto | Microtareas (min) |
|---|---|---|---|
| **Sp1-26** | Diseñar las tablas de sesiones y eventos | 90 | T002 (15), T003 (40) = 55 |
| **Sp1-27** | Implementar SessionStore con SQLite | 180 | T004 (35), T005 (40), T006 (30), T007 (30) = 135 |
| **Sp1-28** | Pruebas de creación | 90 | T008 (30) |
| Transversal | Estado, fronteras, documentación, cierre, verificación, revisión y CI remota (Principios VIII y IX) | — | T001 (20), T009 (30), T010 (30), T011 (35), T012 (25), T013, T014 = 140 |

**Total de las microtareas de trabajo**: 360 min frente a los 360 min presupuestados para Sp1-26 a Sp1-28; el margen es nulo: se avisará a B si la guarda o la documentación se desbordan.

---

## Phase 1: Setup (estado)

**Propósito**: Marcar la historia `En curso`.

- [x] **T001** Marcar HU-03-01 como `En curso` en `docs/PROGRESO.md` (transversal)
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: Ninguna
  - **Criterios relacionados**: Principio VIII
  - **Tarea F5**: Transversal
  - **Estimación**: 20 min
  - **Verificación**: La fila de `HU-03-01` pasa de `Pendiente` a `En curso` con responsable `B — Estado`; se abre el bloque **Observaciones de HU-03-01** con el hallazgo de que el puerto `SessionStore` no tiene `create_session` y el alcance respecto a HU-03-02.

---

## Phase 2: Foundational — errores y esquema (Sp1-26)

**Propósito**: Los errores de dominio del adaptador y el esquema versionado. Bloquea todas las historias de usuario.

- [x] **T002** Errores de dominio del adaptador (FR-011)
  - **Archivos**: `tests/unit/adapters/storage/__init__.py`, `tests/unit/adapters/storage/test_errors.py`, `src/harness_agent/adapters/storage/__init__.py`, `src/harness_agent/adapters/storage/errors.py`
  - **Dependencias**: T001
  - **Criterios relacionados**: FR-011, contrato (Errores), plan D6
  - **Tarea F5**: Sp1-26
  - **Estimación**: 15 min
  - **Verificación**: Prueba primero: `SchemaVersionError` y `ParentSessionNotFound` son subclases de `SessionStoreError`, que es subclase de `Exception`; cada una conserva su mensaje; fallan por `ImportError` antes de implementar. `__init__.py` del paquete existe con docstring.

- [x] **T003** [US3] Esquema versionado: DDL, `SCHEMA_VERSION` y `ensure_schema` (FR-001 a FR-004)
  - **Archivos**: `tests/unit/adapters/storage/test_schema.py`, `src/harness_agent/adapters/storage/_schema.py`
  - **Dependencias**: T002
  - **Criterios relacionados**: FR-001, FR-002, FR-003, FR-004, historia 3 (escenarios 2 a 5), data-model, research (versión de esquema), plan D3, D4
  - **Tarea F5**: Sp1-26
  - **Estimación**: 40 min
  - **Verificación**: Pruebas primero con `sqlite3.connect(":memory:")` y archivos de `tmp_path`: en una base nueva se crean `sessions` y `events` con las columnas del data-model; `user_version` queda en 1; llamar dos veces es idempotente y conserva filas; `user_version` mayor lanza `SchemaVersionError` y no modifica la base (comprobado leyendo `sqlite_master` antes y después); el `CHECK` de estado rechaza un valor fuera de catálogo; con claves foráneas activas un evento de sesión inexistente y un `seq` repetido en la misma sesión se rechazan con `sqlite3.IntegrityError`.

---

## Phase 3: User Story 3 — apertura y ciclo de vida del almacén (Sp1-27)

**Propósito**: Abrir, cerrar y traducir fallos del motor.

- [x] **T004** [US3] `SqliteSessionStore`: constructor, ruta, `close` y gestor de contexto (FR-010, FR-013, plan D5, D7, D8)
  - **Archivos**: `tests/unit/adapters/storage/test_sqlite_session_store.py`, `src/harness_agent/adapters/storage/sqlite_session_store.py`
  - **Dependencias**: T003
  - **Criterios relacionados**: FR-004, FR-010, FR-013, historia 3 (escenarios 1 y 2), Edge Cases (`:memory:`, cierre)
  - **Tarea F5**: Sp1-27
  - **Estimación**: 35 min
  - **Verificación**: Pruebas primero: abrir sobre un directorio inexistente lo crea y deja el esquema; reabrir el mismo archivo no pierde nada; `:memory:` funciona; `close()` es idempotente; el almacén sirve como gestor de contexto; el constructor acepta `str` y `Path`; una ruta que apunta a un archivo que no es SQLite lanza `SessionStoreError` con mensaje que no contiene la ruta.

---

## Phase 4: User Story 1 — crear sesión (Sp1-27)

**Propósito**: AC-01.

**Prueba independiente**: crear una sesión y leerla de vuelta con id, fecha UTC y estado `active`.

- [x] **T005** [US1] `StoredSession` y `create_session` / `get_session` (AC-01, FR-005, FR-007, FR-012)
  - **Archivos**: `tests/unit/adapters/storage/test_sqlite_session_store.py`, `src/harness_agent/adapters/storage/sqlite_session_store.py`
  - **Dependencias**: T004
  - **Criterios relacionados**: AC-01, FR-005, FR-007, FR-012, historia 1 (escenarios 1 a 3), plan D2, D5
  - **Tarea F5**: Sp1-27
  - **Estimación**: 40 min
  - **Verificación**: Pruebas primero con reloj e `id_factory` falsos: la sesión creada tiene el id del generador, `created_at` igual al reloj en UTC, estado `active`, `model`/`goal` opcionales (`None` por defecto) y `parent_id` `None`; un reloj sin zona se toma como UTC; `StoredSession` es inmutable; `get_session` devuelve lo mismo y `None` para un id desconocido; dos sesiones con el generador real tienen ids distintos; objetivo con comillas y caracteres especiales (`'; DROP TABLE sessions; --`) se guarda y lee intacto.

- [x] **T006** [US1] `list_sessions` y persistencia al reabrir (FR-008, FR-009)
  - **Archivos**: `tests/unit/adapters/storage/test_sqlite_session_store.py`, `src/harness_agent/adapters/storage/sqlite_session_store.py`
  - **Dependencias**: T005
  - **Criterios relacionados**: AC-01, FR-008, FR-009, historia 1 (escenarios 4 y 5), plan D9, SC-001, SC-002, SC-003
  - **Tarea F5**: Sp1-27
  - **Estimación**: 30 min
  - **Verificación**: Pruebas primero: `list_sessions` devuelve `SessionSummary` (del puerto) en orden de creación, estable con fechas iguales; vacío en una base nueva; 100 sesiones seguidas con ids distintos; tras cerrar y reabrir el archivo se recuperan con los mismos valores; la creación toma menos de 100 ms por llamada en el caso de prueba.

---

## Phase 5: User Story 2 — sesión hija enlazada al padre (Sp1-27)

**Propósito**: Regla de negocio 1.

**Prueba independiente**: hija con `parent_id` válido se guarda; con uno inexistente se rechaza sin crear nada.

- [x] **T007** [US2] `parent_id` y `ParentSessionNotFound` (regla 1, FR-006)
  - **Archivos**: `tests/unit/adapters/storage/test_sqlite_session_store.py`, `src/harness_agent/adapters/storage/sqlite_session_store.py`
  - **Dependencias**: T005
  - **Criterios relacionados**: Regla de negocio 1, FR-006, historia 2 (escenarios 1 a 3), plan D6
  - **Tarea F5**: Sp1-27
  - **Estimación**: 30 min
  - **Verificación**: Pruebas primero: la hija conserva `parent_id`; la sesión sin padre tiene `None`; un padre inexistente lanza `ParentSessionNotFound` y `list_sessions` no crece; el mensaje no contiene el id recibido; una cadena de tres niveles se lee bien.

---

## Phase 6: Pruebas de creación y errores (Sp1-28)

- [x] **T008** Traducción de errores del motor, uso tras cerrar y cobertura al 100 % (FR-011, FR-016, SC-004)
  - **Archivos**: `tests/unit/adapters/storage/test_sqlite_session_store.py`, `src/harness_agent/adapters/storage/sqlite_session_store.py`
  - **Dependencias**: T006, T007
  - **Criterios relacionados**: FR-011, FR-016, SC-004, SC-006, historia 3 (escenario 6), Edge Cases
  - **Tarea F5**: Sp1-28
  - **Estimación**: 30 min
  - **Verificación**: Pruebas primero con un centinela (`VALOR-DE-PRUEBA-123`) como objetivo y modelo: cualquier operación tras `close()` lanza `SessionStoreError`; un `sqlite3.Error` simulado (conexión que falla al ejecutar) se traduce a `SessionStoreError` sin el centinela ni la ruta; una versión de esquema futura al abrir el almacén lanza `SchemaVersionError` y el archivo queda byte a byte igual; cobertura de `adapters/storage` al 100 % de líneas y ramas (`pytest --cov=harness_agent.adapters.storage --cov-branch`).

---

## Phase 7: Fronteras, documentación y cierre

- [x] **T009** Guarda de fronteras para `adapters/storage/` (FR-014, FR-015)
  - **Archivos**: `tests/architecture/test_adapters_boundaries.py`
  - **Dependencias**: T008
  - **Criterios relacionados**: FR-014, FR-015, skill `verificar-fronteras-hexagonales`
  - **Tarea F5**: Transversal
  - **Estimación**: 30 min
  - **Verificación**: `GUARDED` pasa a `("system", "tools", "storage")`; `pytest tests/architecture` pasa; una autoprueba sintética confirma que `sqlite3` es aceptado en `storage` (biblioteca estándar) pero `import harness_agent.config` o `harness_agent.adapters.tools` no; `core/` sigue sin importar `sqlite3` (guarda existente). No se añade ninguna excepción.

- [x] **T010** API pública del paquete y documentación (FR-014)
  - **Archivos**: `src/harness_agent/adapters/storage/__init__.py`, `docs/guia-contratos-desarrollo.md`, `.claude/skills/estructura-carpetas-harness/references/arbol.md`, `.agents/skills/estructura-carpetas-harness/references/arbol.md`
  - **Dependencias**: T009
  - **Criterios relacionados**: FR-014, plan (Project Structure), CLAUDE.md (skills)
  - **Tarea F5**: Transversal
  - **Estimación**: 30 min
  - **Verificación**: `__init__.py` exporta `SqliteSessionStore`, `StoredSession`, `SessionStoreError`, `SchemaVersionError`, `ParentSessionNotFound`, `SCHEMA_VERSION` en `__all__` y una prueba lo comprueba; la guía explica cómo crear una sesión y que el puerto aún no tiene `create_session`; `arbol.md` (ambas copias idénticas) marca `adapters/storage/` como existente.

- [x] **T011** Cerrar el registro en `docs/PROGRESO.md` (Principio VIII)
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: T010
  - **Criterios relacionados**: FR-017, Principio VIII
  - **Tarea F5**: Transversal
  - **Estimación**: 35 min
  - **Verificación**: Fila de HU-03-01 en `En revisión` (nunca `Hecha`) con *Archivos* y *Evidencia* (comandos y resultados reales de T012); una línea por tarea en *Registro de cambios*; el bloque **Observaciones de HU-03-01** lista: `create_session` fuera del puerto, herencia diferida a HU-03-02, PD-09 sin cerrar, ruta por defecto por confirmar con B, estados limitados, y lo que la raíz de composición deberá conectar. La tabla *Resumen* no cambia.

- [x] **T012** Verificación final: cuatro puertas, fronteras y archivos protegidos
  - **Archivos**: ninguno (solo ejecución)
  - **Dependencias**: T010
  - **Criterios relacionados**: FR-014, FR-016, SC-005, SC-006
  - **Tarea F5**: Transversal
  - **Estimación**: 25 min
  - **Verificación**: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing` con código 0; `pytest tests/architecture` verde; `git diff --exit-code $(git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py tests/doubles docs/archivo` sin diferencias; `adapters/storage` al 100 %. Resultados reales anotados en T011.

---

## Phase 8: Tareas humanas (no las marca Claude)

- [ ] **T013** Revisión cruzada por un integrante de otra área (A o C) — checklist de `capas-y-reglas.md` y hallazgo del puerto
  - **Archivos**: PR
  - **Dependencias**: T012
  - **Criterios relacionados**: Principio IX
  - **Estimación**: humana

- [ ] **T014** CI remota en `ubuntu-latest` y `windows-latest` en verde, y ratificación de HU-00-01 (Sp1-03)
  - **Archivos**: PR
  - **Dependencias**: T013
  - **Criterios relacionados**: Principio IX
  - **Estimación**: humana

---

## Dependencias y orden

T001 → T002 → T003 → T004 → T005 → (T006, T007 en paralelo lógico, archivos distintos solo en pruebas; se hacen en orden) → T008 → T009 → T010 → (T011, T012) → T013 → T014.

**MVP**: T001 a T006 entregan AC-01; T007 añade la regla de subagentes.
