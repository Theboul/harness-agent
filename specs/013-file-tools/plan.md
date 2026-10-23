# Implementation Plan: HU-01-03 — Herramientas de archivos: leer, escribir, listar y buscar

**Branch**: `feat/hu-01-03-file-tools` (directorio de la spec: `013-file-tools`) | **Date**: 2026-10-23 | **Spec**: [specs/013-file-tools/spec.md](spec.md)

**Input**: Feature specification from `/specs/013-file-tools/spec.md`

**Directrices del responsable**: cuatro herramientas nativas (`leer_archivo`, `escribir_archivo`, `listar_archivos`, `buscar_texto`), `editar_archivo` fuera; nombres de herramienta en español, clases e identificadores en inglés; herramientas en `adapters/tools/` y área real en `adapters/system/`; el puerto `AuthorizedArea`, el puerto `Tool`, el bucle y la política no se modifican; commits sin coautor y con el estilo del proyecto.

---

## Summary

Dos paquetes nuevos de adaptadores, sin tocar `core/`:

1. `adapters/system/workspace_area.py`: `WorkspaceArea(AuthorizedArea)`, el área real. Su raíz es la ruta real de una carpeta existente; `contains(path)` resuelve (relativa a la raíz, `..`, enlaces simbólicos), compara la ruta real y falla cerrado. Una clasificación de rutas de Windows, pura e inyectable, rechaza UNC, dispositivos, otra unidad, flujos alternos, nombres reservados y segmentos con punto o espacio final.
2. `adapters/tools/`: `ReadFileTool`, `WriteFileTool`, `ListFilesTool` y `SearchTextTool` (puerto `Tool`), con el argumento `path` de la convención de HU-05-01, el riesgo declarado y una función privada que calcula la ruta real y vuelve a comprobar la contención justo antes de actuar. Sin área, todas devuelven un error claro.

La verificación es el grueso del trabajo: pruebas unitarias, un contrato compartido con `DummyAuthorizedArea`, pruebas de escape (incluidas las de Windows, sintéticas y reales), integración con el bucle real, `DefaultPermissionPolicy` y un área real, y la guarda de arquitectura de `adapters/` que las skills reservan a esta historia.

---

## Technical Context

**Language/Version**: Python 3.12, única versión soportada (PD-07).

**Primary Dependencies**: solo biblioteca estándar (`os`, `pathlib`, `ntpath`/`PureWindowsPath`, `collections.abc`, `typing`, `dataclasses`). Sin dependencias nuevas de ejecución ni de desarrollo.

**Storage**: disco local, solo dentro del área. Ninguna base de datos.

**Testing**: `pytest` + `pytest-asyncio` (`asyncio_mode=auto`); `tmp_path` para todo el disco; `AgentLoop`, `ScriptedProvider`, `RecordingEventBus`, `InMemoryToolRegistry` y `DefaultPermissionPolicy` en integración; `DummyAuthorizedArea` en el contrato; marcas `skipif` por plataforma para los enlaces simbólicos y las pruebas reales de Windows.

**Target Platform**: Windows y Linux (matriz de CI: `ubuntu-latest` y `windows-latest`).

**Project Type**: Biblioteca modular; los adaptadores son la capa exterior, el núcleo no se entera de ellos.

**Performance Goals**: operaciones de archivo locales de tamaño acotado; la búsqueda y el listado se recortan por límites fijos, no por tiempo.

**Constraints**:
1. `core/`, `config.py`, `core/loop.py`, los puertos (`core/interfaces/`), `core/permissions/`, `core/tools/` y todo `tests/doubles/` quedan sin modificar.
2. `adapters/system/` y `adapters/tools/` importan solo biblioteca estándar y `harness_agent.core` (API pública); no importan `config`, `cli`, `observability`, `bootstrap` ni otro adaptador.
3. Las herramientas no leen configuración ni entorno ni la terminal; reciben el área por constructor.
4. `mypy --strict` sobre `src` y `tests`; `ruff` a 100 columnas; nombres de código en inglés, mensajes al usuario en español.
5. Falla cerrada: ante cualquier duda sobre una ruta, está fuera.
6. Ninguna prueba toca el repositorio ni el directorio personal: solo `tmp_path`.
7. Sin `editar_archivo`, sin sesiones, sin shell, sin aprobación interactiva (Principio VI).

**Scale/Scope**: 2 paquetes nuevos (`adapters/system`, `adapters/tools`), 6 módulos de código (`workspace_area.py`, `_paths.py`, `read_file.py`, `write_file.py`, `list_files.py`, `search_text.py`) más los `__init__.py`; 8 módulos de prueba nuevos; 1 sección de guía; actualización de `arbol.md` en las dos copias de la skill.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / Restricción | Requisito | Pre-diseño | Post-diseño | Evidencia |
|---|---|---|---|---|
| I. Una historia por especificación | Solo HU-01-03 | Pasa | Pasa | Spec y plan solo de HU-01-03 |
| II. Microtareas de 15 a 40 min | Ninguna tarea pasa de 40 min (límite absoluto 60) | Pasa | Pasa | `tasks.md` |
| III. Núcleo modular, tipado, sin dependencias externas | `core/` intacto; adaptadores solo con biblioteca estándar y `harness_agent.core` | Pasa | Pasa | D1, D2; guarda de `adapters/` |
| IV. Pruebas, calidad y CI multiplataforma | Pruebas primero; ruff, mypy, pytest en Windows y Linux | Pasa | Pasa | Cada tarea escribe las pruebas antes del código; casos de Windows sintéticos y reales |
| V. Inmutabilidad de criterios | AC-01 a AC-04, reglas y prototipo copiados tal cual | Pasa | Pasa | Spec, sección «Criterios de aceptación…» |
| VI. Disciplina de sprints | Nada de sprints futuros | Pasa | Pasa | Sin `editar_archivo`, sesiones, shell ni aprobación; `bootstrap.py` no se crea |
| VII. Consulta documental quirúrgica | Solo las fuentes necesarias | Pasa | Pasa | HU-01-03, Sp1-18 a Sp1-22, convención `path`, puertos `Tool` y `AuthorizedArea`, política, bucle |
| VIII. Registro en `docs/PROGRESO.md` | `En curso` y `En revisión` con registro | Pasa | Pasa | Primera y última tarea de trabajo |
| IX. Definition of Done estricta | Revisión cruzada y CI en ambos sistemas | Pasa | Pasa | Tareas humanas finales |
| X. Inmutabilidad de `docs/archivo/` | No se toca | Pasa | Pasa | `git diff` de cierre |
| Skill `arquitectura-hexagonal-clean` (Hard Rules) | Dependencias hacia el núcleo; todo lo externo (disco) por un puerto; los adaptadores no contienen reglas de negocio ni importan de otro adaptador; errores externos traducidos; inyección por constructor; falla cerrada | Pasa | Pasa | `WorkspaceArea` y las herramientas implementan los puertos `AuthorizedArea` y `Tool` sin cambiarlos; reciben el área por constructor; la política sigue en `core/permissions/`; ante la duda, fuera del área (sección «Verificación contra las skills») |
| Skill `estructura-carpetas-harness` (Hard Rules) | Cada archivo en la carpeta de su fila (herramienta nativa → `adapters/tools/`, disco → `adapters/system/`); `__init__.py` con la API pública; pruebas en la carpeta equivalente; receta «Nueva herramienta nativa» | Pasa | Pasa | Tabla «Ruta elegida» del plan; `__all__` de los dos paquetes comprobado en `test_public_api.py`; `arbol.md` actualizado en las dos copias |
| Skill `verificar-fronteras-hexagonales` (Hard Rules) | Guardas `ast` en `tests/architecture/`; `adapters/` no importa `cli`; ninguna excepción para que una violación pase | Pasa | Pasa | `tests/architecture/test_adapters_boundaries.py` (T014) con autopruebas y prueba de mutación; `pytest tests/architecture` en verde |
| V-02 Prioridad de denegación / falla cerrada | Ante la duda, fuera del área | Pasa | Pasa | FR-003, D4 |
| V-17 / A-01, A-02 | Sin escapes por «..», enlaces, UNC | Pasa | Pasa | FR-002, FR-004, batería de escape |

No hay violaciones; la sección de complejidad no aplica. Discrepancias de la documentación que **no** impiden implementar y se registran: `editar_archivo` asignada a HU-01-03 en `docs/02-arquitectura.md` (queda fuera por decisión del responsable); el «conjunto mínimo» de la constitución sin `listar` ni `buscar` (D-ARCH del PO lo cubre); la pregunta abierta de `docs/01` ya resuelta por D-ARCH.

---

## Decisiones de diseño

| ID | Decisión | Motivo |
|---|---|---|
| D1 | El área real vive en `adapters/system/workspace_area.py`; las herramientas, en `adapters/tools/`. Ninguna importa a la otra: las herramientas dependen solo del puerto `AuthorizedArea`. | Tocan disco, así que son adaptadores; la skill de estructura confirma `adapters/system/` y `adapters/tools/`. Un adaptador no importa de otro. |
| D2 | No se modifica el puerto `AuthorizedArea`. Las herramientas calculan la ruta real con `os.path.realpath` (en `adapters/tools/_paths.py`) y la pasan a `area.contains(real)`. El área es la única autoridad sobre qué está dentro; la herramienta solo resuelve y pregunta, y pregunta **dos veces**: primero con el texto de la ruta (en Windows así se rechazan UNC y dispositivos sin que `realpath` toque la red) y luego con la ruta real. | Evita un cambio de contrato (acuerdo de A, B y C). Si ambas resoluciones difirieran, la herramienta rechaza (seguro). |
| D3 | `WorkspaceArea.contains` resuelve con `os.path.realpath(candidate)` (no estricta: la ruta puede no existir, para poder crear archivos) y compara con `os.path.commonpath` tras `os.path.normcase`. La raíz cuenta como dentro. | La política llama a `contains` con el `path` de la llamada sin modificar, relativo o absoluto. La ruta real decide (regla de negocio 2). |
| D4 | `contains` captura `Exception` y devuelve `False`; tipos no válidos, NUL y rutas vacías devuelven `False`. | Falla cerrada (FR-003). |
| D5 | La clasificación de Windows es una función pura `windows_path_problem(raw: str) -> str \| None` con `PureWindowsPath`; `WorkspaceArea(root, *, windows: bool \| None = None)` la aplica cuando `windows` es verdadero (por defecto `os.name == "nt"`). | Probar los casos de Windows en Linux (FR-005) y que la CI de Windows pruebe el disco real. |
| D6 | Las herramientas devuelven `ToolResult(call_id="", content=..., is_error=...)`; el bucle fuerza el id de la llamada. Los errores empiezan por una etiqueta de categoría entre corchetes y dan causa y sugerencia en español. | El bucle ya sustituye el id; el estilo de los mensajes del bucle usa la etiqueta (`[tool_exception]`). |
| D7 | Límites fijos como constantes públicas de `adapters/tools/_limits`: lectura y búsqueda por archivo 262 144 bytes, escritura 1 048 576 bytes, listado 200 entradas, búsqueda 50 coincidencias, línea 200 caracteres, consulta 200 caracteres, resultado 20 000 caracteres. | Respuestas acotadas (SC-005); configurables más adelante. |
| D8 | `escribir_archivo` crea las carpetas intermedias (`mkdir(parents=True)`) solo después de comprobar la contención de la ruta real del destino; escribe con `Path.write_bytes`. | `docs/02` dice «crear o reemplazar»; la contención de la ruta final garantiza que las carpetas nuevas quedan dentro. |
| D9 | `buscar_texto` recorre en orden alfabético, no sigue enlaces de carpeta y comprueba cada archivo con `area.contains(real)` antes de abrirlo. | Un enlace dentro del área no debe filtrar contenido de fuera. |
| D10 | Las pruebas de integración componen el sistema (área desde `tmp_path`, registro, política, bucle) y usan `ScriptedProvider`; migrarán a `FakeProvider` cuando el PR #10 se integre. | `FakeProvider` aún no está en `main`; `bootstrap.py` no existe. |
| D11 | Se añade `tests/architecture/test_adapters_boundaries.py` con autopruebas, reutilizando `forbidden_imports`, `find_config_reads` y `terminal_uses`. | La skill de fronteras reserva esta guarda a la primera historia con adaptadores fuera de `converters/`. |
| D12 | Nombres de clase: `WorkspaceArea`, `ReadFileTool`, `WriteFileTool`, `ListFilesTool`, `SearchTextTool`; nombres de herramienta: `leer_archivo`, `escribir_archivo`, `listar_archivos`, `buscar_texto`. | Decisión del responsable. |

---

## Verificación contra las skills del proyecto

Skills cargadas: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness` y `verificar-fronteras-hexagonales` (exigidas por `CLAUDE.md`).

### Decision Gates (`arquitectura-hexagonal-clean`)

| Pregunta | Resultado |
|---|---|
| ¿Es regla o comportamiento nuevo? | No hay regla de negocio nueva: la regla de «permitir solo dentro del área» ya vive en `core/permissions/` (HU-05-01). Aquí se implementan un puerto existente (`AuthorizedArea`) y cuatro herramientas. |
| ¿Necesita algo de fuera? | Sí, disco. Usa los puertos existentes `Tool` y `AuthorizedArea`; no se propone ningún puerto nuevo. |
| ¿Quién lo implementa? | Adaptadores: `adapters/system/` (área real) y `adapters/tools/` (herramientas), porque tocan disco. |
| ¿Cómo se conecta? | Por constructor (el área, o `None`); `bootstrap.py` no existe: la prueba de integración compone y el plan anota qué deberá conectar. |
| ¿Cómo se prueba? | Unitarias con `tmp_path`, contrato `DummyAuthorizedArea` / `WorkspaceArea`, integración con el bucle, la política y el registro reales, y guarda `ast`. |
| ¿Es asíncrono? | `Tool.run` es `async`; `AuthorizedArea.contains` es síncrono, como declara el puerto. |

### Ruta elegida (`estructura-carpetas-harness`)

| Archivo nuevo | Fila de la tabla | Prueba equivalente |
|---|---|---|
| `adapters/system/workspace_area.py` | «Código con … disco» → `adapters/<subpaquete>/` | `tests/unit/adapters/system/`, `tests/contracts/test_authorized_area_contract.py` |
| `adapters/tools/read_file.py`, `write_file.py`, `list_files.py`, `search_text.py`, `_paths.py`, `_limits.py` | «Herramienta nativa» → `adapters/tools/` (receta «Nueva herramienta nativa») | `tests/unit/adapters/tools/`, `tests/integration/test_file_tools_agent_loop.py` |
| `tests/architecture/test_adapters_boundaries.py` | Guarda de la frontera de `adapters/` (hueco conocido) | — |

### Lista de comprobación (`capas-y-reglas.md`)

- [x] ¿La regla de negocio está en `core/` y no en un adaptador? Sí: la política decide permisos en `core/permissions/`; los adaptadores no contienen reglas de permisos, solo comprueban la contención con el puerto.
- [x] ¿Todo lo externo pasa por un puerto con tipos del dominio? Sí: `Tool`, `ToolResult` y `AuthorizedArea`; el disco lo toca el adaptador.
- [x] ¿Los puertos, entidades y eventos siguen sin cambios? Sí: ninguno se modifica (`git diff` de `core/` vacío).
- [x] ¿Los errores externos se traducen a errores de dominio, sin reproducir valores recibidos? Sí: toda excepción del sistema se convierte en un `ToolResult` con etiqueta y sin la excepción ni la ruta real.
- [x] ¿Las dependencias se inyectan por constructor y se conectan solo en `bootstrap.py` (o en la prueba)? Sí: el área llega por constructor; la composición está en la prueba de integración.
- [x] ¿El núcleo se probó con dobles, sin red, disco ni claves? Sí; los adaptadores se prueban sobre `tmp_path`, sin red ni claves.
- [x] ¿El adaptador real tiene prueba de contrato en `tests/contracts/`? Sí: `test_authorized_area_contract.py`.
- [x] ¿Pasa `pytest tests/architecture` (y la guarda nueva) en Windows y Linux? Sí: 209 pruebas en Linux; la CI de `windows-latest` se comprueba en T018.
- [x] ¿El núcleo emite eventos en lugar de imprimir? Sin cambios en el núcleo; los adaptadores no imprimen (lo vigila la guarda).
- [x] ¿Lo público está exportado y los consumidores importan de `harness_agent.core`? Sí: `__all__` de los dos paquetes y solo `from harness_agent.core import ...`.
- [x] ¿Se respetan las decisiones de diseño (falla cerrada, historial intacto, secretos)? Sí: cualquier duda sobre una ruta es «fuera»; sin secretos en el repositorio.
- [ ] ¿Otro integrante revisó el cambio? **No todavía** (T017).

### Fronteras (`verificar-fronteras-hexagonales`)

`pytest tests/architecture` → 209 pasadas; guarda nueva `tests/architecture/test_adapters_boundaries.py` (T014) para `adapters/` (no importa `cli`) y para `system/` y `tools/`. Sin archivos que violen una regla.

---

## Project Structure

### Documentation (this feature)

```text
specs/013-file-tools/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── file_tools_contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
src/harness_agent/adapters/
├── system/                         # NUEVO
│   ├── __init__.py                 # API pública: WorkspaceArea, windows_path_problem
│   └── workspace_area.py
└── tools/                          # NUEVO
    ├── __init__.py                 # API pública: las cuatro herramientas y los límites
    ├── _limits.py                  # constantes
    ├── _paths.py                   # ruta real, error de herramienta, mensajes
    ├── read_file.py                # ReadFileTool
    ├── write_file.py               # WriteFileTool
    ├── list_files.py               # ListFilesTool
    └── search_text.py              # SearchTextTool

tests/
├── unit/adapters/__init__.py
├── unit/adapters/system/
│   └── test_workspace_area.py      # área real, incluidas las pruebas sintéticas de Windows
├── unit/adapters/tools/
│   ├── test_paths.py
│   ├── test_read_file.py
│   ├── test_list_files.py
│   ├── test_search_text.py
│   ├── test_write_file.py
│   ├── test_no_area.py             # sin área configurada
│   ├── test_registration_and_risk.py   # registro real, riesgos y decisión de la política
│   └── test_escape_attempts.py     # batería de escape contra las cuatro herramientas
├── contracts/
│   └── test_authorized_area_contract.py   # mismo contrato contra el doble y el área real
├── integration/
│   └── test_file_tools_agent_loop.py      # AC-01 a AC-04 con bucle, política, registro y área reales
└── architecture/
    └── test_adapters_boundaries.py

docs/
├── guia-contratos-desarrollo.md    # + sección de las herramientas de archivos
└── PROGRESO.md                     # fila de HU-01-03 y registro de cambios
.claude/skills/estructura-carpetas-harness/references/arbol.md   # system/ y tools/ pasan de planeado a existente
.agents/skills/estructura-carpetas-harness/references/arbol.md   # misma copia
```

**Structure Decision**: Single project. Se crean `adapters/system/` y `adapters/tools/` (ya previstos por el árbol de la skill); no se crea ninguna otra carpeta. `bootstrap.py` sigue sin existir: la composición se hace en la prueba de integración y queda anotada.

**Qué deberá conectar `bootstrap.py` cuando exista**: construir `WorkspaceArea(config.paths.workspace_root)` si `workspace_root` no es `None` (si es `None`, pasar `area=None`), crear las cuatro herramientas con esa área, registrarlas en el `ToolRegistry` y pasar la misma área a `DefaultPermissionPolicy(area=...)`.

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Un escape por una ruta que la política y la herramienta resuelven distinto | La herramienta vuelve a comprobar con `area.contains(real)`; ante discrepancia rechaza. Batería de escape sobre la política y sobre las herramientas. |
| Comportamiento distinto en Windows que no se puede probar en Linux | Clasificación pura e inyectable con pruebas sintéticas + pruebas reales marcadas que corren en `windows-latest`; se revisa la CI antes de pasar a «Hecha». |
| Los enlaces simbólicos en Windows exigen privilegios | Las pruebas de enlaces se marcan y se omiten si no se pueden crear (1 omisión esperada en Windows, como indica `CLAUDE.md`). |
| Carrera entre comprobar y usar | Se vuelve a resolver y comprobar justo antes de actuar; la ventana restante se documenta (spec, casos límite). |
| Mensajes que revelan rutas externas | Los mensajes repiten el `path` recibido (acotado), nunca la ruta real de fuera del área (FR-010, US3-7). |
| El motivo específico no llega al modelo por la política | Aceptado en el Sprint 1 (HU-05-01, Q3 = A); queda como observación para HU-05-03. |
| La estimación de C se queda corta | Aviso de capacidad en `PROGRESO.md` si se supera el presupuesto (hoy: unos 545 min frente a 780). |
