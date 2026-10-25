# Implementation Tasks: HU-02-02 — Recorte de salidas largas de herramientas

**Feature**: `specs/020-tool-output-truncation/spec.md`  
**Plan**: `specs/020-tool-output-truncation/plan.md`  
**Responsable**: C — Control y conexiones  
**Sprint**: Sprint 2 | **PHU**: 1  
**Tareas de referencia**: Sp2-12, Sp2-13  

---

## Cómo leer este documento

**Pruebas primero, dentro de cada tarea.** Se escriben las pruebas, se ejecutan y se confirma que fallan **por la razón esperada** (`ImportError` del símbolo nuevo o una aserción concreta), se implementa lo mínimo y se repite hasta que pasen. El rojo se anota en una línea en el registro de `PROGRESO.md`.

**Ritmo**: 10 tareas de trabajo (T002 a T011) de 40 min como máximo, una de inicio (T001) y tres humanas (T012 a T014). Ninguna pasa de 40 min (la Constitución permite 40; el límite absoluto es 60). Los tiempos son referencia, no una restricción.

**Reglas que valen para todas las tareas:**
- **Archivos protegidos**: no modificar `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/permissions/`, `core/in_memory_event_bus.py`, `src/harness_agent/cli/`, `tests/doubles/` ni `docs/archivo/`. Los únicos archivos existentes que se tocan son: `core/tools/registry.py`, `core/tools/__init__.py`, `core/__init__.py`, `config.py` (aditivo, área de B, se declara como desviación), `config.example.toml`, `bootstrap.py`, los docstrings de `adapters/tools/_limits.py` y `adapters/system/shell_limits.py` (sin cambiar valores), `docs/PROGRESO.md`, `CLAUDE.md` y `arbol.md` de las dos copias de la skill. Ninguna prueba existente cambia su comportamiento esperado; si alguna fijaba la lista exacta de campos de `Limits`, se ajusta y se anota.
- `core/tools/output_limit.py` importa solo biblioteca estándar y `harness_agent.core`; no `config`, no `os`, no `print`. Python 3.12. Sin dependencias nuevas.
- Todo el código y las pruebas pasan `mypy` y `ruff` (línea de 100 columnas). Identificadores y docstrings en inglés; mensajes al usuario y documentación en español, sin reproducir el valor recibido. Valor centinela: `VALOR-DE-PRUEBA-123`.
- Cobertura del módulo nuevo: 100 % de líneas y ramas. Sin pruebas por plataforma.
- **Commits** (estilo del proyecto): en español, sin coautor ni pie de sesión, formato `tipo(ámbito): descripción (HU-02-02)`; rama `feat/hu-02-02-tool-output-truncation`. Cada tarea o grupo de tareas cierra con al menos un commit; sin push, merge ni PR sin confirmación humana.
- **Al cerrar cada tarea que toca código o pruebas**: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing` con código 0; se registra el resultado en `docs/PROGRESO.md` al cerrar (T011).
- **Skills**: este plan se hizo con `arquitectura-hexagonal-clean`, `estructura-carpetas-harness` y `verificar-fronteras-hexagonales`; T009 y T011 vuelven a pasar sus listas.

**Correspondencia con las tareas del plan de sprint:**

| Tarea F5 | Descripción en `docs/03-plan-sprints.md` | Presupuesto | Microtareas (min) |
|---|---|---|---|
| **Sp2-12** | Aplicar el recorte en el registro de herramientas | 60 | T002 (40), T003 (35), T004 (40), T005 (40), T006 (30) = 185 |
| **Sp2-13** | Prueba con salida de gran tamaño | 90 | T007 (30), T008 (35) = 65 |
| Transversal | Frontera, documentación, estado (Principios VIII y IX) | — | T001 (15), T009 (30), T010 (20), T011 (35) = 100 |

Sp2-12 supera su presupuesto (185 frente a 60 min) porque incluye la configuración por `config.toml` (T005, T006), que la estimación original no contemplaba; se anota como observación.

---

## Phase 1: Inicio

- [ ] **T001** Línea base y puntero de feature (15 min)
  - **Archivos**: `.specify/feature.json` (ignorado por git; apunta a `specs/020-tool-output-truncation`).
  - **Verificación**: en el worktree, los cuatro comandos de calidad y `pytest tests/architecture` en 0 **antes** de tocar nada; anotar el número de pruebas pasadas y omitidas como línea base.

## Phase 2: US1 — Una salida enorme no llena el contexto (P1)

**Goal**: AC-01. **Independent test**: una herramienta con salida enorme, servida por el registro, devuelve contenido ≤ máximo con principio, final y marca exacta.

- [ ] **T002** [US1] Función pura de recorte y validación del máximo (40 min)
  - **Archivos**: `src/harness_agent/core/tools/output_limit.py` (fila «regla/implementación pura en `core/`»); `tests/unit/core/tools/test_output_limit.py`.
  - **Pruebas**: dentro del máximo → misma instancia; exactamente el máximo → sin marca; un carácter más → marca con `1`... (cantidad exacta); texto enorme → `len ≤ max`, empieza y termina como el original; cantidad omitida = `len(original) - len(head) - len(tail)` (se comprueba extrayéndola de la marca); texto vacío; caracteres no ASCII y emoji; máximo mínimo (256) y justo por debajo (`ValueError` sin el valor recibido, probado con el centinela); `check_max_output_chars` rechaza `bool`, `float`, `str`, `None`, 0, negativos y < 256, acepta 256 y 24 000; el texto de la marca coincide con el de `adapters/system/shell_output.py` (prueba de coherencia).
  - **Implementación**: constantes `DEFAULT_MAX_OUTPUT_CHARS = 24_000`, `MIN_MAX_OUTPUT_CHARS = 256`; `omission_notice`, `truncate_output`, `check_max_output_chars`, con la reserva de la marca calculada con los dígitos de `len(text)`.

- [ ] **T003** [US1] Decorador `TruncatingTool` (35 min)
  - **Archivos**: `src/harness_agent/core/tools/output_limit.py` (misma pieza); `tests/unit/core/tools/test_output_limit.py` (clase nueva de pruebas).
  - **Pruebas**: delega `name`, `description`, `schema` y `risk` (leídos en cada acceso); `run` recibe los mismos `args` (misma instancia, sin copiar ni mutar); resultado corto → misma instancia de `ToolResult`; largo → `call_id` e `is_error` intactos y `content` recortado; error largo conserva su etiqueta inicial; resultado que no es `ToolResult` o con `content` no texto → se devuelve tal cual; excepción de la herramienta se propaga; `asyncio.CancelledError` se propaga; el máximo del constructor se valida.
  - **Implementación**: `class TruncatingTool(Tool)` con `inner` y `max_chars`.

- [ ] **T004** [US1] El registro sirve la herramienta con recorte (40 min)
  - **Archivos**: `src/harness_agent/core/tools/registry.py` (modifica); `src/harness_agent/core/tools/__init__.py` y `src/harness_agent/core/__init__.py` (exportan `TruncatingTool`, `truncate_output`, `omission_notice`, `check_max_output_chars`, `DEFAULT_MAX_OUTPUT_CHARS`, `MIN_MAX_OUTPUT_CHARS`); `tests/unit/core/tools/test_registry_output_limit.py`.
  - **Pruebas**: sin máximo, `get` y `list` devuelven las instancias registradas (misma identidad); con máximo, `get(n).run(...)` recorta y `get(n)` tiene los mismos `name/description/schema/risk`; `list()` mantiene el orden y devuelve herramientas con recorte; registrar una herramienta inválida o duplicada sigue sin dejar rastro; `validate_args` y `UnknownToolError` no cambian; el máximo inválido (`True`, 0, 255, `"x"`) hace fallar el constructor con mensaje en español sin el valor; dos registros con máximos distintos recortan distinto el mismo texto (US2.1); `test_registry.py` existente sigue pasando sin cambios.
  - **Implementación**: `__init__(self, *, max_output_chars: int | None = None)`; `_Entry` gana `served`; `get`/`list` devuelven `served`.

## Phase 3: US2 — El operador fija el máximo (P2)

**Goal**: regla de negocio 1. **Independent test**: un valor válido en `config.toml` llega al registro de `compose()`; uno inválido se rechaza al cargar.

- [ ] **T005** [US2] Campo `limits.max_tool_output_chars` en la configuración (40 min)
  - **Archivos**: `src/harness_agent/config.py` (aditivo, área de B; **desviación declarada**); `config.example.toml` (campo comentado y explicado); `tests/unit/test_config_max_tool_output_chars.py`.
  - **Pruebas**: `Limits().max_tool_output_chars == 24000`; sin el campo rige el defecto; valor válido (256, 12000) se lee; ni `True`, ni 255, ni 0, ni texto, ni decimal se aceptan (`ConfigProblem("limits.max_tool_output_chars", …)` con mensaje en español que no reproduce el valor); se acumulan con otros problemas; los otros límites no cambian; las pruebas existentes de `config` (en particular las de `_LIMIT_FIELDS` y de campos desconocidos) siguen pasando — si alguna fija la lista exacta de campos, se ajusta y se anota.
  - **Implementación**: añadir el campo a `_LIMIT_FIELDS` y a `Limits`; validación con `MIN_MAX_OUTPUT_CHARS` importado de `harness_agent.core`.

- [ ] **T006** [US2] Cableado en `bootstrap.py` (30 min)
  - **Archivos**: `src/harness_agent/bootstrap.py` (modifica); `tests/unit/test_bootstrap_tool_output_limit.py`.
  - **Pruebas**: `compose(config)` con `max_tool_output_chars=300` devuelve un registro cuyo `get("leer_archivo")`... (con herramienta de archivos real sobre `tmp_path` y un archivo mayor que 300) entrega contenido ≤ 300 con marca; con el defecto, un archivo de 30 000 caracteres llega recortado a ≤ 24 000 y uno de 1 000 llega íntegro; `test_bootstrap_boundaries.py` sigue en verde.
  - **Implementación**: `InMemoryToolRegistry(max_output_chars=config.limits.max_tool_output_chars)`.

## Phase 4: US3 — Convive con los acotados de cada herramienta (P2)

- [ ] **T007** [US3] Coherencia con el shell y las herramientas de archivos (30 min)
  - **Archivos**: `tests/integration/test_tool_output_truncation.py` (parte 1); `src/harness_agent/adapters/tools/_limits.py` y `src/harness_agent/adapters/system/shell_limits.py` (solo docstrings: quitar «hasta que HU-02-02…» y remitir al recorte general; **valores sin cambio**).
  - **Pruebas**: el peor resultado del shell (cabecera de error + cuerpo de 20 000 con su aviso, construido con `ShellTool` y un `Shell` de prueba en memoria, o con las constantes) pasa por el registro con el máximo por defecto **idéntico** y con un solo aviso; el listado y la búsqueda de 20 000 también; con un máximo más bajo (1 000) el resultado final ≤ 1 000 y su aviso nuevo es exacto respecto del texto recibido; el texto de la marca del registro y el de `OutputCollector` son el mismo.
  - **Verificación**: `git diff` de esos dos archivos muestra solo comentarios o docstrings.

- [ ] **T008** [US1] Sp2-13: salida de gran tamaño por el bucle real (35 min)
  - **Archivos**: `tests/integration/test_tool_output_truncation.py` (parte 2); usa `make_rig` de `tests/core/support.py` o `compose()` con `FakeProvider`.
  - **Pruebas**: `AgentLoop` real con una herramienta que devuelve 10 veces el máximo (SC-001): el mensaje `TOOL` que entra al historial no supera el máximo y contiene la cantidad exacta omitida; un turno con salida corta queda idéntico (SC-002); una herramienta con `is_error=True` y salida enorme sigue marcada como error; los eventos del bucle no llevan el contenido (FR-029 de HU-01-01); dos llamadas en el mismo turno se recortan por separado.

## Phase 5: Frontera y cierre

- [ ] **T009** Guarda de arquitectura y verificación de fronteras (30 min)
  - **Archivos**: `tests/architecture/test_output_limit_boundaries.py` (a partir de `.claude/skills/verificar-fronteras-hexagonales/assets/test_module_boundaries.py`, reutilizando los detectores existentes).
  - **Pruebas**: `core/tools/output_limit.py` importa solo stdlib y `harness_agent.core`; no importa `adapters`, `cli`, `config`, `bootstrap`; no usa `os`, `open`, `print`; autopruebas sobre fragmentos sintéticos; `config.py` puede importar `harness_agent.core` (comprobado por la guarda de `config`, si existe, o documentado).
  - **Verificación**: `pytest tests/architecture` en 0.

- [ ] **T010** Documentación de estructura y guía (20 min)
  - **Archivos**: `.claude/skills/estructura-carpetas-harness/references/arbol.md` y su copia en `.agents/skills/` (el archivo nuevo de `core/tools/` y la prueba de arquitectura); `CLAUDE.md` (snapshot: una fila en «Qué existe hoy» y la convención del máximo); `docs/guia-contratos-desarrollo.md` solo si menciona el recorte de salidas.
  - **Verificación**: las dos copias de `arbol.md` quedan idénticas en lo tocado.

- [ ] **T011** Cierre de la historia (35 min)
  - **Archivos**: `docs/PROGRESO.md`; este `tasks.md` (marcar solo lo hecho, con su evidencia).
  - **Verificación**: los cuatro comandos de calidad en 0 y `pytest tests/architecture`; cobertura de `core/tools/output_limit.py` al 100 % de líneas y ramas; `git diff --exit-code $(git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/loop.py tests/doubles docs/archivo` da 0; `PROGRESO.md`: fila de HU-02-02 → `En revisión` (nunca `Hecha`), *Archivos*, *Evidencia* con comandos y resultados reales, una línea por tarea en *Registro de cambios*, observaciones para B (campo de `config.py`), HU-02-01 (el recorte afecta a `leer_archivo` y a lo que el ensamblador cuente), HU-11-03 (desbloqueada), HU-01-04 (docstrings) y el PO (24 000); la tabla *Resumen* no cambia. Las tareas humanas quedan sin marcar. `.specify/feature.json` apunta a `specs/020-tool-output-truncation`.

## Phase 6: Tareas humanas (Claude no las marca)

- [ ] **T012** *(humana)* Revisión cruzada por un integrante de otra área (A o B)
  - Revisar el diff completo, en especial el campo nuevo de `config.py` (B) y la envoltura en el registro (A, dueño del bucle).
  - **Evidencia**: nombre, fecha y resultado en `PROGRESO.md`.

- [ ] **T013** *(humana)* Ejecución de la CI en Linux y Windows y relleno de Commit/PR
  - **Evidencia**: enlace al run y commit en `PROGRESO.md`.

- [ ] **T014** *(humana)* Confirmación de los supuestos
  - B: el campo aditivo `limits.max_tool_output_chars` en `config.py`. PO: el valor por defecto de 24 000 caracteres y que `leer_archivo` quede recortado por encima de él.
  - **Evidencia**: respuesta anotada en `PROGRESO.md`.

---

## Dependencias y orden

- T001 → T002 → T003 → T004 → (T005 → T006) y (T007, T008) → T009 → T010 → T011.
- **US1** (T002, T003, T004, T008) es P1; **US2** (T005, T006) y **US3** (T007) son P2.
- **MVP**: T001 a T004 y T008 cubren AC-01 con el máximo pasado al constructor; T005 y T006 dan la configuración del operador.
- Paralelo: T005 es independiente de T004 salvo por la constante `MIN_MAX_OUTPUT_CHARS` (T002); T007 y T008 comparten archivo, así que van en serie.

## Presupuesto

| Concepto | Min |
|---|---|
| Tareas F5 (T002 a T008) | 250 |
| Transversales (T001, T009 a T011) | 100 |
| **Total de trabajo** | **350** |

Frente a los 150 min presupuestados para Sp2-12 y Sp2-13 hay un exceso de 200 min, explicado por la configuración del operador (T005, T006), la guarda y la documentación; las tres tareas humanas no se cuentan.
