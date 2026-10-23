# Implementation Tasks: HU-01-03 — Herramientas de archivos: leer, escribir, listar y buscar

**Feature**: `specs/013-file-tools/spec.md`  
**Plan**: `specs/013-file-tools/plan.md`  
**Responsable**: C — Control y conexiones  
**Sprint**: Sprint 1 | **PHU**: 4  
**Tareas de referencia**: Sp1-18, Sp1-19, Sp1-20, Sp1-21, Sp1-22  

---

## Cómo leer este documento

**Pruebas primero, dentro de cada tarea.** Cada tarea agrupa las pruebas y la implementación de una pieza: se escriben las pruebas, se ejecutan y se confirma que fallan **por la razón esperada** (`ImportError` del símbolo nuevo o una aserción concreta), se implementa lo mínimo y se vuelve a ejecutar hasta que pasen. El rojo esperado de cada tarea está en su *Verificación*.

**Ritmo**: 14 tareas de trabajo (T002 a T015) de 40 min como máximo, una de inicio (T001), una de cierre (T016) y dos humanas (T017, T018). Ninguna pasa de 40 min (la Constitución permite 40; el límite absoluto es 60).

**Reglas que valen para todas las tareas:**
- **Archivos protegidos**: no modificar nada bajo `src/harness_agent/core/` (en particular `core/interfaces/`, `core/loop.py`, `core/permissions/` y `core/tools/`), ni `src/harness_agent/config.py`, ni `tests/doubles/`, ni `docs/archivo/`, ni ninguna prueba existente. Los únicos archivos existentes que se tocan son `docs/guia-contratos-desarrollo.md`, `docs/PROGRESO.md` y `references/arbol.md` de las dos copias de la skill `estructura-carpetas-harness`.
- `adapters/system/` y `adapters/tools/` solo importan biblioteca estándar y `harness_agent.core` (`from harness_agent.core import ...`, nunca submódulos); no importan `config`, `cli`, `observability`, `bootstrap` ni otro adaptador. Python 3.12. Sin dependencias nuevas.
- Todo el código y las pruebas deben pasar `mypy --strict` y `ruff` (línea de 100 columnas). Nombres de código en inglés; mensajes de error y documentación en español.
- Los tipos, las reglas y los límites siguen [contracts/file_tools_contract.md](contracts/file_tools_contract.md) y [data-model.md](data-model.md); las decisiones, [research.md](research.md) (R-01 a R-11) y [plan.md](plan.md) (D1 a D12).
- **Aislamiento**: toda prueba que toca disco usa `tmp_path`; ninguna toca el repositorio, el directorio personal ni la red. Las pruebas de enlaces simbólicos se omiten con `pytest.skip` si el sistema no deja crearlos; las de Windows reales llevan `skipif(os.name != "nt")`. Valor centinela: `VALOR-DE-PRUEBA-123`.
- **Sin literales detectables**: ninguna prueba contiene texto que `tests/architecture/test_no_secrets_in_repo.py` detecte como clave.
- **Commits** (estilo del proyecto): en español, sin coautor ni pie de sesión, formato `tipo(ámbito): descripción (HU-01-03)` con `feat`, `docs` o `test`; por ejemplo `feat(tools): área de trabajo real y herramientas de archivos (HU-01-03)` y `docs(spec): especificación, plan y tareas de HU-01-03`. La rama es `feat/hu-01-03-file-tools`.
- **Al cerrar cada tarea que toca código o pruebas**, ejecutar `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`; los cuatro con código 0, y registrar el resultado en `docs/PROGRESO.md` dentro de los 5 min de la tarea.

**Correspondencia con las tareas del plan de sprint** (columna *Tarea F5*):

| Tarea F5 | Descripción en `docs/03-plan-sprints.md` | Presupuesto | Microtareas (min) |
|---|---|---|---|
| **Sp1-18** | Implementar leer, listar y buscar con error claro de ruta inexistente | 150 | T005 (35), T006 (35), T007 (30), T008 (40) = 140 |
| **Sp1-19** | Componente AuthorizedArea: configuración del área y comprobación de contención sobre la ruta real | 150 | T002 (40), T003 (40), T004 (25) = 105 |
| **Sp1-20** | Implementar escribir usando AuthorizedArea (normalización, enlaces simbólicos, unidades y rutas UNC) | 210 | T009 (40) |
| **Sp1-21** | Declarar para cada herramienta su nivel de riesgo | 60 | T013 (25) |
| **Sp1-22** | Pruebas de escape: «..», ruta absoluta, enlace simbólico y casos de Windows | 210 | T011 (40) |
| Transversal | Estado, integración, sin área, fronteras, documentación, cierre, revisión y CI remota (Principios VIII y IX) | — | T001 (20), T010 (40), T012 (30), T014 (35), T015 (35), T016 (35), T017, T018 = 195 |

**Total de las microtareas de trabajo**: 545 min frente a los 780 min presupuestados para Sp1-18 a Sp1-22: dentro del presupuesto.

---

## Phase 1: Setup (estado)

**Propósito**: Marcar la historia `En curso`.

- [ ] **T001** Marcar HU-01-03 como `En curso` en `docs/PROGRESO.md` (transversal)
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: Ninguna
  - **Criterios relacionados**: Principio VIII
  - **Tarea F5**: Transversal
  - **Estimación**: 20 min (10 min impl + 5 min check + 5 min registro)
  - **Verificación**: La fila de `HU-01-03` de la tabla de Sprint 1 pasa de `Pendiente` a `En curso` con responsable `C — Control y conexiones`; Commit/PR vacío; se añade el bloque **Observaciones de HU-01-03** con: la decisión de las cuatro herramientas y `editar_archivo` fuera, los nombres en español, las discrepancias halladas en la documentación (`docs/02` asigna `editar_archivo` a esta historia; la constitución habla de un «conjunto mínimo» sin `listar` ni `buscar`; `docs/01` mantiene abierta la pregunta que D-ARCH resolvió), los dos puntos **por confirmar** (motivo genérico del bucle para AC-03 y AC-04 sin carpeta de sesión), el supuesto de lectura de HU-05-01 aún sin confirmar, `FakeProvider` pendiente del PR #10 y HU-00-01 `Pendiente de aprobación técnica`; ninguna otra fila ni la tabla *Resumen* cambian (`git diff -U0 docs/PROGRESO.md`).

---

## Phase 2: Foundational — Área de trabajo real y utilidades de ruta (Sp1-18, Sp1-19)

**Propósito**: La autoridad sobre qué está dentro del área y las utilidades que comparten las cuatro herramientas. Bloquea todas las historias.

- [ ] **T002** Implementar `WorkspaceArea`: construcción, `root` y `contains` sobre la ruta real, con sus pruebas (FR-001 a FR-003)
  - **Archivos**: `tests/unit/adapters/__init__.py`, `tests/unit/adapters/system/__init__.py`, `tests/unit/adapters/system/test_workspace_area.py`, `src/harness_agent/adapters/system/__init__.py`, `src/harness_agent/adapters/system/workspace_area.py`
  - **Dependencias**: T001
  - **Criterios relacionados**: AC-03, AC-04, reglas de negocio 2 y 3, FR-001, FR-002, FR-003, contrato §1, data-model (WorkspaceArea), research R-02 y R-03, plan D1, D3, D4
  - **Tarea F5**: Sp1-19
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero con `tmp_path`: es subclase de `AuthorizedArea`; `root` es la ruta real (un enlace a la carpeta se resuelve); construir con una ruta inexistente, un archivo o un vacío falla con `ValueError` en español; `contains` es verdadero para relativa dentro, absoluta dentro, la propia raíz, subcarpetas que aún no existen y `Path`; falso para `..` que sale, absoluta fuera, hermana con el mismo prefijo (`/area` frente a `/area-otra`), enlace a archivo o carpeta que sale, `enlace/../x`, enlace roto y circular, texto vacío o solo espacios, carácter nulo, tipos no válidos (`None`, `int`, `bytes`) y cualquier excepción forzada (parche de `os.path.realpath` que lanza) sin que `contains` lance. Rojo esperado: `ModuleNotFoundError: No module named 'harness_agent.adapters.system'`. Cierre: los cuatro comandos en 0; `workspace_area.py` al 100 % de líneas y ramas.

- [ ] **T003** Clasificación de rutas de Windows (`windows_path_problem`) y su uso en `contains` (FR-004, FR-005)
  - **Archivos**: `tests/unit/adapters/system/test_workspace_area.py`, `src/harness_agent/adapters/system/workspace_area.py`, `src/harness_agent/adapters/system/__init__.py`
  - **Dependencias**: T002
  - **Criterios relacionados**: AC-03 (Windows), FR-004, FR-005, contrato §1 (A-4), data-model (windows_path_problem), research R-04, plan D5
  - **Tarea F5**: Sp1-19
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero (clases nuevas en el módulo de T002): `windows_path_problem` devuelve una causa para `\\servidor\recurso`, `//servidor/x`, `\\?\C:\x`, `\\.\COM1`, `notas.txt:flujo`, `C:\area\a.txt:zone`, `CON`, `nul.txt`, `com3`, `LPT1.log`, `carpeta.`, `archivo.txt ` y `None` para `src\main.py`, `C:\area\a.txt`, `a.b.c`, `conexion.txt` (no confundir con `CON`); `WorkspaceArea(tmp_path, windows=True).contains(...)` es falso para cada caso malo y verdadero para uno bueno relativo; con `windows=False` los nombres con `:` son válidos; la comparación normaliza mayúsculas con `normcase` (prueba con parche de `os.path.normcase` o con rutas de `ntpath` según el sistema); pruebas **reales** marcadas `skipif(os.name != "nt")`: otra unidad (`D:\x` frente a `C:\...`, si existe) y mayúsculas distintas dentro del área. Rojo esperado: `ImportError: cannot import name 'windows_path_problem'`. Cierre: los cuatro comandos en 0; `workspace_area.py` al 100 % de líneas y ramas (las ramas exclusivas de Windows quedan cubiertas por las pruebas sintéticas).

- [ ] **T004** [P] Prueba de contrato: `DummyAuthorizedArea` y `WorkspaceArea` cumplen lo mismo (FR-019)
  - **Archivos**: `tests/contracts/test_authorized_area_contract.py`
  - **Dependencias**: T002
  - **Criterios relacionados**: FR-019, SC-004, contrato §1 (A-5)
  - **Tarea F5**: Sp1-19
  - **Estimación**: 25 min (15 min impl + 5 min check + 5 min registro)
  - **Verificación**: Una batería parametrizada por implementación (`DummyAuthorizedArea(tmp_path)` y `WorkspaceArea(tmp_path)`) con los casos que ambas deben cumplir: dentro relativa y absoluta, raíz, `..` que sale, absoluta fuera, hermana con el mismo prefijo, `root` es `Path` absoluto, `isinstance(..., AuthorizedArea)`, y que `contains` devuelve exactamente `True` o `False` (la política exige `is True`). Una prueba separada documenta que solo `WorkspaceArea` rechaza el enlace que sale (el doble es léxico). Sin código nuevo: no hay rojo previo porque valida T002 (se demuestra con una mutación temporal que invierte el resultado de `contains`). Cierre: los cuatro comandos en 0.

- [ ] **T005** Implementar `_limits.py` y `_paths.py` (ruta real, errores de herramienta, acotado) con sus pruebas (FR-009, FR-010, FR-015)
  - **Archivos**: `tests/unit/adapters/tools/__init__.py`, `tests/unit/adapters/tools/test_paths.py`, `src/harness_agent/adapters/tools/__init__.py`, `src/harness_agent/adapters/tools/_limits.py`, `src/harness_agent/adapters/tools/_paths.py`
  - **Dependencias**: T002
  - **Criterios relacionados**: AC-01 (error claro), reglas de negocio 2 y 4, FR-009, FR-010, FR-015, data-model (Límites y Resultado de error), research R-01 y R-09, plan D2, D6, D7
  - **Tarea F5**: Sp1-18
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero: las constantes tienen los valores de `data-model.md`; `error_result(category, message)` devuelve un `ToolResult` con `is_error=True`, `call_id=""` y el texto `[categoría] mensaje`; `bounded_path(path)` acota a 100 caracteres y elimina caracteres de control; `resolve_in_area(area, raw_path)` pregunta primero a `area.contains(raw_path)` (si es falso, error `[fuera_del_area]` sin llamar a `os.path.realpath`: parche que falla si se llama), calcula después la ruta real y vuelve a preguntar con `area.contains(real)`; devuelve la ruta real cuando ambas aceptan y un error `[fuera_del_area]` cuando no, y `[sin_area]` cuando `area` es `None`, sin lanzar nunca (ni con NUL ni con tipos raros); el mensaje de `[fuera_del_area]` no contiene la ruta real (centinela en un directorio externo); `bounded_text(text, limit)` recorta con aviso. Rojo esperado: `ModuleNotFoundError: No module named 'harness_agent.adapters.tools'`. Cierre: los cuatro comandos en 0; `_limits.py` y `_paths.py` al 100 %.

---

## Phase 3: User Story 1 — Leer, listar y buscar dentro del área (P1) [AC-01]

**Objetivo**: Las tres herramientas de lectura devuelven contenido o un error claro, sin excepciones.

**Prueba independiente**: Con un área real sobre una carpeta temporal, cada herramienta devuelve su resultado y una ruta inexistente devuelve `[no_existe]`.

- [ ] **T006** [US1] Implementar `ReadFileTool` (`leer_archivo`) con sus pruebas (FR-006, FR-007, FR-008, FR-011)
  - **Archivos**: `tests/unit/adapters/tools/test_read_file.py`, `src/harness_agent/adapters/tools/read_file.py`
  - **Dependencias**: T005
  - **Criterios relacionados**: AC-01, regla de negocio 4, FR-006, FR-007, FR-008, FR-010, FR-011, contrato §2, research R-06
  - **Tarea F5**: Sp1-18
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero: `name == "leer_archivo"`, riesgo bajo, `schema` con `path` (texto, `minLength` 1) y `additionalProperties` falso, es subclase de `Tool`; lee un archivo UTF-8 por ruta relativa y absoluta (incluidos acentos y saltos de línea); un archivo vacío devuelve texto vacío sin error; `[no_existe]` para una ruta inexistente con la sugerencia de usar `listar_archivos`; `[no_es_archivo]` para una carpeta; `[demasiado_grande]` a `MAX_READ_BYTES + 1`; `[no_es_texto]` con un NUL; `[no_es_texto]` con bytes no UTF-8; `[error_de_archivo]` si `open` lanza `PermissionError` (parche); nunca lanza; solo lee `MAX_READ_BYTES + 1` bytes (parche que cuenta lo leído). Rojo esperado: `ModuleNotFoundError: No module named 'harness_agent.adapters.tools.read_file'`. Cierre: los cuatro comandos en 0; `read_file.py` al 100 %.

- [ ] **T007** [P] [US1] Implementar `ListFilesTool` (`listar_archivos`) con sus pruebas (FR-013)
  - **Archivos**: `tests/unit/adapters/tools/test_list_files.py`, `src/harness_agent/adapters/tools/list_files.py`
  - **Dependencias**: T005
  - **Criterios relacionados**: AC-01, FR-006, FR-007, FR-008, FR-010, FR-013, contrato §2
  - **Tarea F5**: Sp1-18
  - **Estimación**: 30 min (15 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero: `name == "listar_archivos"`, riesgo bajo, esquema con `path`; lista una carpeta con archivos, subcarpetas y un enlace, ordenada, con `archivo` o `carpeta` por entrada; `.` lista la raíz; una carpeta vacía devuelve un aviso claro, no un error; más de `MAX_LIST_ENTRIES` se recorta y lo dice; el resultado no pasa de `MAX_RESULT_CHARS`; `[no_existe]` y `[no_es_carpeta]` (un archivo); nombres con acentos y espacios; nunca lanza. Rojo esperado: `ModuleNotFoundError: No module named 'harness_agent.adapters.tools.list_files'`. Cierre: los cuatro comandos en 0; `list_files.py` al 100 %.

- [ ] **T008** [US1] Implementar `SearchTextTool` (`buscar_texto`) con sus pruebas (FR-014)
  - **Archivos**: `tests/unit/adapters/tools/test_search_text.py`, `src/harness_agent/adapters/tools/search_text.py`
  - **Dependencias**: T005, T006
  - **Criterios relacionados**: AC-01, AC-03 (no filtrar por enlaces), FR-006, FR-007, FR-008, FR-010, FR-014, contrato §2, research R-08, plan D9
  - **Tarea F5**: Sp1-18
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero: `name == "buscar_texto"`, riesgo bajo, esquema con `path` y `query` (`minLength` 1, `maxLength` `MAX_QUERY_CHARS`); encuentra el texto literal en un archivo y recursivamente en una carpeta, con `ruta/relativa:línea: texto` y orden alfabético estable; sensible a mayúsculas; una consulta con caracteres de regex (`.*`, `(`) se trata como texto literal; sin coincidencias devuelve un aviso, no un error; recorta a `MAX_MATCHES` y lo dice; acota cada línea a `MAX_LINE_CHARS`; omite binarios, no UTF-8 y archivos mayores que `MAX_READ_BYTES`; **no sigue** un enlace de carpeta que sale del área ni lee un enlace de archivo que sale (el contenido externo con el centinela no aparece); `[no_existe]` para una ruta inexistente; nunca lanza. Rojo esperado: `ModuleNotFoundError: No module named 'harness_agent.adapters.tools.search_text'`. Cierre: los cuatro comandos en 0; `search_text.py` al 100 %.

---

## Phase 4: User Story 2 — Escribir solo dentro del área autorizada (P1) [AC-02]

**Objetivo**: `escribir_archivo` crea o reemplaza archivos dentro del área, y la decisión de la política queda registrada.

**Prueba independiente**: Con el bucle real, una escritura dentro se ejecuta y publica «allow»; fuera, se deniega y no se crea nada.

- [ ] **T009** [US2] Implementar `WriteFileTool` (`escribir_archivo`) con sus pruebas (FR-008, FR-012)
  - **Archivos**: `tests/unit/adapters/tools/test_write_file.py`, `src/harness_agent/adapters/tools/write_file.py`
  - **Dependencias**: T005
  - **Criterios relacionados**: AC-02, AC-03 (rechazo antes de escribir), reglas de negocio 1 y 3, FR-006, FR-007, FR-008, FR-009, FR-010, FR-012, contrato §2 (T-2), research R-07, plan D8
  - **Tarea F5**: Sp1-20
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero: `name == "escribir_archivo"`, riesgo **medio**, esquema con `path` y `content` (texto) y `additionalProperties` falso; crea un archivo nuevo, reemplaza uno existente (el contenido anterior desaparece), escribe UTF-8 con acentos y saltos de línea, crea carpetas intermedias que faltan, devuelve la cantidad de bytes; `[fuera_del_area]` sin tocar el disco para `..`, absoluta fuera y enlace que sale (el archivo externo queda idéntico y no se crea ninguna carpeta intermedia); `[no_es_archivo]` si el destino es una carpeta; `[demasiado_grande]` para `MAX_WRITE_BYTES + 1` sin tocar el disco; `[error_de_archivo]` si `write_bytes` lanza `OSError`; contenido vacío crea un archivo vacío; nunca lanza. Rojo esperado: `ModuleNotFoundError: No module named 'harness_agent.adapters.tools.write_file'`. Cierre: los cuatro comandos en 0; `write_file.py` al 100 %.

- [ ] **T010** [US2] Integración AC-01 y AC-02 con el bucle real, la política real y el área real (FR-020)
  - **Archivos**: `tests/integration/test_file_tools_agent_loop.py`
  - **Dependencias**: T006, T007, T008, T009
  - **Criterios relacionados**: AC-01, AC-02, FR-020, SC-003, contrato §3, research R-10, plan D10
  - **Tarea F5**: Transversal
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Sin código de producción nuevo. Una función de composición crea `WorkspaceArea(tmp_path / "area")`, las cuatro herramientas, `InMemoryToolRegistry`, `DefaultPermissionPolicy(area=...)`, `RecordingEventBus`, `AgentLoop` y `ScriptedProvider`. Casos (nombres con `read`, `write_inside`, `write_outside`): leer un archivo del área devuelve su contenido en el historial y el mensaje queda marcado como externo; leer una ruta inexistente devuelve `[no_existe]`; listar y buscar funcionan; escribir dentro se ejecuta, crea el archivo y publica un `PERMISSION_DECIDED` con decisión «allow»; escribir fuera (ruta absoluta y `..`) publica la pregunta, se resuelve como denegada y no crea el archivo; un guion de tres pasos (leer, escribir y releer) termina igual en cada ejecución; con `allow_reads_in_area=False` las lecturas se preguntan y se deniegan sin ejecutar. Cierre: los cuatro comandos en 0.

---

## Phase 5: User Story 3 — Los intentos de escapar del área se rechazan antes de escribir (P1) [AC-03]

**Objetivo**: Ninguna ruta hostil escribe ni lee fuera del área.

**Prueba independiente**: Una batería de al menos 15 rutas hostiles contra las cuatro herramientas y contra el área.

- [ ] **T011** [US3] Batería de escape contra las cuatro herramientas y el área (FR-021, SC-001)
  - **Archivos**: `tests/unit/adapters/tools/test_escape_attempts.py`
  - **Dependencias**: T003, T006, T007, T008, T009
  - **Criterios relacionados**: AC-03, reglas de negocio 2 y 3, SC-001, spec US3, research R-05
  - **Tarea F5**: Sp1-22
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Sin código de producción nuevo (si una prueba encuentra un escape, se corrige en T002 a T009 antes de cerrar). Una carpeta `fuera/` con un archivo centinela junto al área `area/`. Casos parametrizados sobre `escribir_archivo` y comprobados con `contains`: `..`, `../fuera/x`, `a/../../fuera/x`, absoluta fuera, ruta con barra final, enlace a archivo externo, enlace a carpeta externa (escribir a través de él), `enlace/../x`, enlace roto hacia fuera, enlace circular, NUL, vacío, solo espacios; y los mismos tramos con `leer_archivo`, `listar_archivos` y `buscar_texto`. En cada caso: `is_error=True`, categoría `[fuera_del_area]`, el archivo centinela intacto (contenido y fecha), no se crea nada fuera, y el mensaje no contiene la ruta de `fuera/` ni el centinela. Casos de Windows sintéticos con `WorkspaceArea(..., windows=True)` (UNC, `\\?\`, flujo alterno, reservados, punto final) y reales con `skipif(os.name != "nt")`. Los de enlaces se omiten si el sistema no permite crearlos. Cierre: los cuatro comandos en 0.

---

## Phase 6: User Story 4 — Sin área configurada, nada se ejecuta (P2) [AC-04]

**Objetivo**: Sin `workspace_root` no existe un área por defecto.

**Prueba independiente**: Con `area=None`, cada herramienta devuelve `[sin_area]` y, con el bucle real, la política pregunta y se deniega.

- [ ] **T012** [US4] Sin área: herramientas con `area=None` e integración AC-04 (FR-015)
  - **Archivos**: `tests/unit/adapters/tools/test_no_area.py`, `tests/integration/test_file_tools_agent_loop.py`
  - **Dependencias**: T010
  - **Criterios relacionados**: AC-04, regla de negocio 3, FR-015, spec US4
  - **Tarea F5**: Transversal
  - **Estimación**: 30 min (15 min impl + 10 min check + 5 min registro)
  - **Verificación**: Sin código de producción nuevo. Unitaria: las cuatro herramientas con `area=None` devuelven `[sin_area]` con la sugerencia de configurar `workspace_root`, sin tocar el disco (parche que falla si se llama a `open` o `os.scandir`). Integración (nombres con `no_area`): con `DefaultPermissionPolicy(area=None)` y el bucle real, `escribir_archivo`, `leer_archivo`, `listar_archivos` y `buscar_texto` se preguntan, se resuelven como denegadas y no se ejecutan ni se crea ningún archivo; un `HarnessConfig` con `workspace_root` ausente produce `area=None` en la composición; con `workspace_root` presente produce una `WorkspaceArea` cuya raíz es la ruta real. Cierre: los cuatro comandos en 0.

---

## Phase 7: User Story 5 — Riesgo y ruta declarados (P2)

**Objetivo**: La política puede clasificar las cuatro herramientas por su riesgo y su `path`.

**Prueba independiente**: Las cuatro se registran en el registro real y la política real decide como indica el contrato.

- [ ] **T013** [US5] Registro real y clasificación por la política (Sp1-21)
  - **Archivos**: `tests/unit/adapters/tools/test_registration_and_risk.py`
  - **Dependencias**: T009, T006, T007, T008
  - **Criterios relacionados**: FR-006, FR-007, FR-008, spec US5, convención `path`
  - **Tarea F5**: Sp1-21
  - **Estimación**: 25 min (15 min impl + 5 min check + 5 min registro)
  - **Verificación**: Sin código de producción nuevo. Las cuatro se registran en `InMemoryToolRegistry` (valida el esquema) con nombres únicos y sin colisión; el registro rechaza argumentos extra y `path` vacío o no textual; riesgos: `escribir_archivo` medio, las otras tres bajo; con `DefaultPermissionPolicy(area=WorkspaceArea(tmp_path))`, las llamadas sin `path` o con `path` no textual se deniegan, con `path` dentro se permiten y fuera se preguntan; una herramienta de las cuatro cuyo riesgo se cambiara a otro valor haría fallar la prueba (mutación documentada). Cierre: los cuatro comandos en 0.

---

## Phase 8: Fronteras, documentación y cierre

- [ ] **T014** [P] Guarda de arquitectura de `adapters/` con autopruebas (FR-018, plan D11)
  - **Archivos**: `tests/architecture/test_adapters_boundaries.py`
  - **Dependencias**: T008, T009
  - **Criterios relacionados**: FR-016, FR-018, skill `verificar-fronteras-hexagonales` (hueco «nada comprueba que `adapters/` no importe `cli/`»)
  - **Tarea F5**: Transversal
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: Con `ast`, reutilizando `forbidden_imports`, `find_config_reads` y `terminal_uses` de las guardas existentes (no copiarlos): ningún módulo de `adapters/` importa `harness_agent.cli`; `adapters/system/` y `adapters/tools/` solo importan biblioteca estándar y `harness_agent.core` (nunca submódulos del núcleo, `config`, `observability`, `bootstrap`, otro adaptador ni terceros); no leen configuración ni entorno ni la terminal (`print`, `input`, `sys.stdout`); línea base con al menos 8 módulos revisados y 0 hallazgos. Autoprueba con fragmentos que violan y que respetan cada regla, y prueba de mutación sobre una copia en `tmp_path`. Línea base limpia, así que no hay rojo previo. Cierre: los cuatro comandos en 0; `pytest tests/architecture` en verde.

- [ ] **T015** [P] API pública, guía y árbol de carpetas de las skills (FR-023)
  - **Archivos**: `src/harness_agent/adapters/tools/__init__.py`, `src/harness_agent/adapters/system/__init__.py`, `docs/guia-contratos-desarrollo.md`, `.claude/skills/estructura-carpetas-harness/references/arbol.md`, `.agents/skills/estructura-carpetas-harness/references/arbol.md`
  - **Dependencias**: T009, T012
  - **Criterios relacionados**: FR-023, Principio VIII, `CLAUDE.md` (actualizar las dos copias de la skill)
  - **Tarea F5**: Transversal
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: `__all__` de cada `__init__.py` exporta lo público (`WorkspaceArea`, `windows_path_problem`; las cuatro herramientas y las constantes de límite) y una prueba mínima (en un módulo de prueba existente de la historia) comprueba que importan sin ciclos y que no exponen helpers privados; en la guía, sección para C con la composición (área desde `workspace_root`, herramientas, registro y política), la tabla de herramientas, los límites y los errores; el ejemplo se ejecuta tal cual en un script del scratchpad fuera del repositorio; en `arbol.md` (las dos copias idénticas salvo lo que ya difería) `adapters/system/` y `adapters/tools/` pasan de «planeado/propuesta» a existentes, y la guarda de `adapters/` figura en la lista. Solo cambian esas líneas (`git diff -U0`). Cierre: `ruff`, `mypy` y la suite en verde.

- [ ] **T016** Cierre: verificación completa y registro en `docs/PROGRESO.md` (transversal)
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: T001 a T015
  - **Criterios relacionados**: Principios VIII, IX y X, FR-017, FR-022, FR-023, SC-006, SC-007
  - **Tarea F5**: Transversal
  - **Estimación**: 35 min (15 min impl + 15 min check + 5 min registro)
  - **Verificación**: Los cuatro comandos de CI en 0; cobertura de los módulos nuevos al 100 % de líneas y ramas (`--cov=harness_agent.adapters`); recorrido manual del quickstart §3 y §4; `git diff --exit-code "$(git merge-base HEAD origin/main)" -- docs/archivo src/harness_agent/core src/harness_agent/config.py tests/doubles` → 0; `git diff --stat` contra `origin/main` solo lista los archivos de este plan; detector de claves de HU-00-04 sin coincidencias. La fila de HU-01-03 pasa a `En revisión` (no a `Hecha`: faltan T017 y T018), con rutas y evidencia; la tabla *Resumen* no cambia hasta `Hecha`; una línea en el registro de cambios por tarea.

- [ ] **T017** *(humana)* Revisión cruzada por A o B y confirmación del PO
  - **Archivos**: —
  - **Dependencias**: T016
  - **Criterios relacionados**: Principio IX, spec (por confirmar)
  - **Estimación**: según la persona revisora
  - **Verificación**: Un integrante de otra área revisa el PR; el PO confirma la regla de lectura de HU-05-01 y los dos puntos «por confirmar» (motivo genérico del bucle para AC-03 y AC-04 sin carpeta de sesión); se ratifica que `editar_archivo` queda fuera y que D-ARCH resuelve la pregunta de `docs/01`. HU-00-01 sigue `Pendiente de aprobación técnica` y debe ratificarse antes de pasar a `Hecha`.

- [ ] **T018** *(humana)* Ejecución de la CI en Linux y Windows y relleno de Commit/PR
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: T017
  - **Criterios relacionados**: Principio IX
  - **Estimación**: según la CI
  - **Verificación**: la matriz de CI pasa en ambos sistemas, incluidas las pruebas marcadas por plataforma de Windows; la fila de HU-01-03 recibe Commit/PR y, solo entonces, puede pasar a `Hecha`.

---

## Dependencias y orden de ejecución

```
T001 → T002 → T003 ──────────────────────┐
         ├──→ T004 [P]                    │
         └──→ T005 → T006 ─→ T008 ─┐      │
                  ├──→ T007 [P] ────┤      │
                  └──→ T009 ────────┴→ T010 → T012
T003 + T006..T009 → T011              T006..T009 → T013
T008 + T009 → T014 [P]      T009 + T012 → T015 [P]
T001..T015 → T016 → T017 → T018
```

- **US1** (T006 a T008) y **US2** (T009) son P1 y dependen de T005; T007 y T014/T015/T004 no tocan archivos de otras tareas y pueden ir en paralelo.
- **MVP**: T001 a T006, T009 y T010 cubren AC-01 y AC-02; T011 cubre AC-03 y T012 cubre AC-04.

## Estimación frente al presupuesto

| Concepto | Minutos |
|---|---|
| Sp1-18 a Sp1-22 presupuestados | 780 |
| Tareas F5 (T002 a T009, T011, T013) | 350 |
| Transversales (T001, T010, T012, T014, T015, T016) | 195 |
| **Total de tareas de trabajo** | **545** |

Dentro del presupuesto por 235 min; las dos tareas humanas (T017, T018) no se cuentan.
