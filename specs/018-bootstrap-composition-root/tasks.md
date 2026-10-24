# Implementation Tasks: Raíz de composición y punto de entrada ejecutable (propuesta HU-00-08)

**Feature**: `specs/018-bootstrap-composition-root/spec.md`  
**Plan**: `specs/018-bootstrap-composition-root/plan.md`  
**Responsable de la historia**: C — Control y conexiones (decisión del PO, cierra PD-08)  
**Sprint**: Sprint 1 | **PHU**: sin asignar (historia propuesta; el PO la formaliza)  
**Tareas de referencia**: ninguna en `docs/03-plan-sprints.md` (la historia no tiene ficha); se propone el prefijo provisional `Sp1-P` en `PROGRESO.md`

---

## Cómo leer este documento

**Pruebas primero, dentro de cada tarea.** Cada tarea agrupa las pruebas y la implementación de una pieza: se escriben las pruebas, se ejecutan y se confirma que fallan **por la razón esperada** (indicada en cada tarea), se implementa lo mínimo y se pasan los cuatro comandos de calidad. No hay tareas de «solo pruebas».

**Ritmo**: 7 tareas de trabajo con código (T003 a T009), todas de 40 min como máximo; aparte, solo estas: inicio (T001), documentación de cierre (T010), verificación final (T011) y las humanas (T002, T012 a T015).

**Reglas que valen para todas las tareas:**
- **Archivos protegidos**: no modificar `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `cli/`, `tests/doubles/`, ninguna prueba existente ni `docs/archivo/`. Tampoco `.github/workflows/ci.yml`. Los únicos archivos existentes que se tocan son `pyproject.toml` (solo `[project.scripts]`), `CLAUDE.md`, las skills (ambas copias) y `docs/PROGRESO.md`.
- `core/` no se toca. `bootstrap.py` es el único módulo que conoce a la vez núcleo, adaptadores, CLI y configuración; importa de los paquetes públicos (`harness_agent.core`, `harness_agent.adapters.providers`, `.storage`, `.system`, `.tools`, `harness_agent.cli`, `harness_agent.config`), nunca de submódulos. No lee `os.environ`, no usa `print`, `input` ni `sys.stdout` directamente: escribe en los flujos inyectados (el valor por omisión `sys.stdout`/`sys.stderr` se resuelve en `main`). Python 3.12, `mypy --strict`, `ruff` a 100 columnas. Identificadores y docstrings en inglés; mensajes al usuario en español.
- Contratos y decisiones: [contracts/bootstrap_contract.md](contracts/bootstrap_contract.md), [data-model.md](data-model.md), [research.md](research.md) y [plan.md](plan.md).
- **Aislamiento**: ninguna prueba usa red ni claves reales. Las de integración importan la fixture `blocked_network` de `tests/integration/test_fake_provider_agent_loop.py` (con `# noqa: F401`, como `test_sprint1_scripted_file_task.py`). El proveedor de prueba entra por `provider_factory` con `FakeProvider` o una clase mínima local; la base es `:memory:` o `tmp_path`.
- **Sin literales detectables**: usar `VALOR-DE-PRUEBA-123` como centinela de la clave; no asignar valores largos a nombres tipo `secret`, `token`, `password` (`tests/architecture/test_no_secrets_in_repo.py`).
- **Windows**: no usar señales reales en las pruebas; `write_text(..., newline="")`; `ids=` explícitos en `parametrize` con valores largos; las rutas se pasan como `Path`.
- **No dejar `.coverage*`** en el árbol: `rm -f .coverage*` antes de confirmar y añadir con rutas explícitas (`git add <rutas>`).
- **Al cerrar cada tarea que toca código o pruebas**: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`, los cuatro con código 0, y `pytest tests/architecture`. La cobertura de `bootstrap.py` y `__main__.py` debe llegar al **100 % de líneas y ramas** al cerrar T007.

**Correspondencia con el plan de sprint**: la historia no tiene tareas `Sp1-xx` en `docs/03-plan-sprints.md`. El PO asignó **3 h (180 min)** de presupuesto; la estimación de abajo es mayor y se avisa en «Estimación frente al presupuesto».

| Bloque | Descripción | Microtareas |
|---|---|---|
| Composición | `compose()`, `Composition`, avisos de área | T003 |
| Sesión y comando | `run_session()`, `main()` feliz, `__main__`, comando `harness` | T004, T005 |
| Integración | tarea de extremo a extremo con el bucle real, persistencia, interrupción | T006 |
| Errores de arranque | códigos 2 y 130, secretos | T007 |
| Determinismo y fronteras | 20 ejecuciones idénticas, guarda `ast` | T008, T009 |
| Transversal | estado, ratificación, documentación, cierre, revisión y CI remota | T001, T002, T010 a T015 |

---

## Phase 1: Setup (estado y ratificación)

**Propósito**: Marcar la historia `En curso` y dejar claro que los AC son propuestos.

- [ ] T001 Marcar la historia propuesta como `En curso` en `docs/PROGRESO.md` (transversal)
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: Ninguna
  - **Criterios relacionados**: Principio VIII, PD-08
  - **Estimación**: 20 min
  - **Verificación**: Fila nueva en la tabla de Sprint 1: «HU-00-08 (propuesta) — Raíz de composición y punto de entrada ejecutable», responsable `C — Control y conexiones`, estado `En curso`, PHU «—». Bloque **Observaciones de HU-00-08 (propuesta)** con: ID provisional, AC-P1 a AC-P3 pendientes de ratificación, 3 h asignadas por el PO y el aviso de capacidad. Una línea nueva en el Registro de cambios (una línea por fila, CRLF, tabla *Resumen* intacta). Línea base de las cuatro puertas antes de tocar código.
  - **Evidencia**:

- [ ] T002 *(humana)* El PO ratifica o sustituye AC-P1 a AC-P3 y decide el ID definitivo (puede hacerse al final, pero antes de pasar a `Hecha`)
  - **Archivos**: `docs/PROGRESO.md` (solo para anotar la decisión)
  - **Dependencias**: T001
  - **Criterios relacionados**: Principio V
  - **Estimación**: fuera del presupuesto de Claude
  - **Verificación**: El PO acepta o reemplaza los tres criterios y asigna un ID de historia (o decide dejarla como tarea técnica); se anota fecha y decisión. **No bloquea** T003 a T011; **bloquea** pasar de `En revisión` a `Hecha`.
  - **Evidencia**:

---

## Phase 2: Foundational — La composición (bloquea todas las historias de usuario)

**Propósito**: Construir las piezas en el orden definido y dejar la composición lista para ejecutarse.

- [ ] T003 [US1] `compose()` y `Composition` en `src/harness_agent/bootstrap.py` con `tests/unit/test_bootstrap_compose.py`
  - **Archivos** (fila de `estructura-carpetas-harness`: «Unir piezas y elegir implementaciones → `bootstrap.py`»): `src/harness_agent/bootstrap.py` (nuevo), `tests/unit/test_bootstrap_compose.py` (nuevo)
  - **Dependencias**: T001
  - **Criterios relacionados**: FR-003, FR-004, FR-005, FR-007, FR-011, FR-012, FR-013; AC-P1, AC-P2
  - **Estimación**: 40 min
  - **Pruebas primero**: con configuración construida a mano (`HarnessConfig`) y `provider_factory` con un proveedor mínimo: (1) la composición devuelve el bucle, el bus, el almacén y un `session_id` que existe en el almacén con `model=config.model`; (2) un evento emitido por el bus queda guardado (registrador conectado antes de devolver); (3) el registrador está suscrito a los 17 tipos; (4) sin `workspace_root` → `notices` con el aviso de área ausente y una herramienta de archivos devuelve `[sin_area]`; (5) `workspace_root` que no es carpeta → el otro aviso, sin reproducir la ruta; (6) con área válida → sin avisos y las 4 herramientas registradas por nombre (`leer_archivo`, `escribir_archivo`, `listar_archivos`, `buscar_texto`); (7) el proveedor se construye **antes** de abrir la base (si `provider_factory` lanza, el archivo de la base no existe); (8) si falla un paso posterior a abrir el almacén, este se cierra antes de propagar; (9) `close()` cierra el almacén y es idempotente; (10) reloj e identificadores inyectados llegan al almacén (`session_id` fijo). Deben fallar con `ModuleNotFoundError: harness_agent.bootstrap`.
  - **Implementación**: `Composition` (`@dataclass(frozen=True)`: `loop`, `bus`, `store`, `session_id`, `notices`, `close()`), `compose(config, *, provider_factory=None, clock=None, id_factory=None)` con el orden de `data-model.md`, constantes con los dos textos de aviso, `_default_provider(config)` con `LiteLLMProvider(config.model, max_output_tokens=config.limits.max_output_tokens, api_key=config.api_key)`.
  - **Verificación**: las pruebas pasan; `bootstrap.py` no importa submódulos (`harness_agent.core.loop`, etc.); cuatro puertas en 0.
  - **Evidencia**:

---

## Phase 3: User Story 1 — Ejecutar una tarea real desde la terminal (P1) [AC-P1]

**Objetivo**: Una sesión interactiva de extremo a extremo con el comando.

**Prueba independiente**: con proveedor simulado y entrada de dos líneas, el archivo se crea dentro del área, la terminal muestra los eventos y la salida es 0.

- [ ] T004 [US1] `run_session()` con historial continuo y avisos en `src/harness_agent/bootstrap.py` (+ clase `TestRunSession` en `tests/unit/test_bootstrap_main.py`)
  - **Archivos**: `src/harness_agent/bootstrap.py`, `tests/unit/test_bootstrap_main.py` (nuevo)
  - **Dependencias**: T003
  - **Criterios relacionados**: FR-006, FR-007, FR-013; Historia 1 (escenarios 2, 4 y 5)
  - **Estimación**: 30 min
  - **Pruebas primero**: con `StringIO` de entrada y salida y un proveedor que registra los mensajes que recibe: (1) los avisos de `notices` se escriben **antes** del primer prompt; (2) la segunda tarea llega al proveedor con el historial de la primera (el historial crece entre líneas); (3) `/salir` y fin de entrada devuelven 0; (4) un turno que lanza una excepción ordinaria devuelve 1 (lo decide `run_cli`); (5) una acción que pide aprobación se deniega con `[approval_required_unavailable]` en lo que recibe el modelo. Deben fallar con `AttributeError`/`ImportError` de `run_session`.
  - **Implementación**: `run_session(composition, *, input_stream=None, output=None)`: lista `history` propia de la sesión, `run_turn(task)` que llama a `composition.loop.run_turn(session_id=…, task=…, history=history)`, escritura de avisos y `return await run_cli(composition.bus, run_turn, input_stream=…, output=…)`.
  - **Verificación**: las pruebas pasan; `cli/` no se modifica (`git diff` limpio).
  - **Evidencia**:

- [ ] T005 [US1] `main()` en el camino feliz, `__main__.py` y el comando `harness` (`src/harness_agent/bootstrap.py`, `src/harness_agent/__main__.py`, `pyproject.toml`, `tests/unit/test_entry_point.py`)
  - **Archivos**: `src/harness_agent/bootstrap.py`, `src/harness_agent/__main__.py` (nuevo), `pyproject.toml` (solo `[project.scripts]`), `tests/unit/test_entry_point.py` (nuevo), ampliación de `tests/unit/test_bootstrap_main.py`
  - **Dependencias**: T004
  - **Criterios relacionados**: FR-001, FR-002, FR-009; AC-P1; Historia 1 (escenario 5)
  - **Estimación**: 40 min
  - **Pruebas primero**: (1) `main(environ=…, config_path=<archivo en tmp_path>, input_stream=…, output=…, provider_factory=…)` con configuración válida y `/salir` devuelve 0 y cierra el almacén; (2) `main` carga la configuración con el `environ` recibido (la clave de un entorno falso llega al proveedor sin tocar `os.environ`); (3) `runpy.run_module("harness_agent", run_name="__main__")` con `main` sustituido por un doble llama a `main()` sin argumentos y termina con su código; (4) `pyproject.toml` declara `harness = "harness_agent.bootstrap:main"` (se lee con `tomllib` en la prueba) y la función existe y es invocable. Deben fallar por `main` inexistente y por el script no declarado.
  - **Implementación**: `main(...)` con los valores por omisión reales (`sys.stdin`, `sys.stdout`, `sys.stderr`), `load_config(config_path, environ=environ)`, `compose`, `asyncio.run(run_session(...))`, `close()` en `finally`. `__main__.py`: `from harness_agent.bootstrap import main` / `raise SystemExit(main())` bajo `if __name__ == "__main__":` (o sin guarda, de modo que `runpy` lo ejecute). `[project.scripts]` en `pyproject.toml`.
  - **Verificación**: las pruebas pasan; `pip install -e . --no-deps` no se rompe (mismo `pyproject.toml` válido); cuatro puertas en 0.
  - **Evidencia**:

- [ ] T006 [US1] [US2] Integración con el `AgentLoop` real en `tests/integration/test_bootstrap_session.py`
  - **Archivos**: `tests/integration/test_bootstrap_session.py` (nuevo)
  - **Dependencias**: T005
  - **Criterios relacionados**: AC-P1, AC-P2; Historia 1 (escenarios 1 a 4), Historia 2 (escenarios 1 y 2); SC-002, SC-005
  - **Estimación**: 40 min
  - **Pruebas primero** (la composición real con `FakeProvider`, `blocked_network` y base en `tmp_path`; fallan mientras falte algún cableado): (1) tarea «crea `notas.txt`» → el archivo existe dentro del área, la salida contiene la solicitud y el resultado de la herramienta y el código es 0; (2) **SC-002**: los eventos guardados en la base (en orden y con un solo `session_id`) coinciden en número y tipos con los que se mostraron; (3) segunda tarea que usa lo de la primera → el historial se conserva; (4) escritura fuera del área → denegada y el archivo no existe (**SC-005**); (5) acción que pide aprobación → denegada con motivo; (6) `QuotaExceeded` a mitad de tarea → la sesión sigue y el error se muestra; (7) interrupción: la tarea de `run_session` se cancela con una llamada al proveedor en espera → el evento `INTERRUPTED` queda guardado y la base se puede cerrar; (8) sin `workspace_root` → aviso y `[sin_area]` al intentar escribir.
  - **Verificación**: pasan sin cambios en `src/`; `rm -f .coverage*` antes de confirmar.
  - **Evidencia**:

---

## Phase 4: User Story 3 — Errores de arranque claros (P2) [AC-P3]

- [ ] T007 [US3] Errores de arranque y códigos 2 y 130 en `main()` (`src/harness_agent/bootstrap.py`, `tests/unit/test_bootstrap_main.py`)
  - **Archivos**: `src/harness_agent/bootstrap.py`, `tests/unit/test_bootstrap_main.py`
  - **Dependencias**: T005
  - **Criterios relacionados**: FR-002, FR-008, FR-009, FR-010; AC-P3; SC-003, SC-007
  - **Estimación**: 40 min
  - **Pruebas primero** (cada caso verifica: código 2, **una sola línea** en el flujo de errores, prefijo «No se pudo iniciar: », ninguna traza y que el centinela no aparece en ninguna salida): (1) archivo de configuración inexistente; (2) campo inválido; (3) clave escrita en el archivo; (4) falta la variable de la clave (el mensaje nombra la variable, no su valor); (5) `provider_factory` que lanza `ProviderDependencyError` (el mensaje incluye el comando de instalación); (6) base de datos inutilizable (`sessions_db` apunta a un archivo que no es una base, o a un esquema desconocido) → mensaje del almacén y la base no se modifica; (7) excepción no prevista en `compose` → «error inesperado (Tipo).» sin el texto de la excepción (se usa un mensaje con el centinela y se comprueba que no sale); (8) `KeyboardInterrupt` lanzado por el proveedor/entrada → código 130, almacén cerrado, sin traza; (9) **FR-009**: los cuatro códigos (0, 1, 2, 130) son distintos entre sí. Deben fallar porque `main` aún deja subir las excepciones.
  - **Implementación**: `EXIT_STARTUP = 2`, `EXIT_INTERRUPTED = 130`, función `_one_line(text)`, captura de `ConfigError`, `ProviderDependencyError`, `SessionStoreError` y `Exception` genérica **solo** en la fase de arranque (no dentro de la sesión), y de `KeyboardInterrupt` alrededor de `asyncio.run`.
  - **Verificación**: las pruebas pasan; **`bootstrap.py` y `__main__.py` al 100 % de líneas y ramas** (`--cov-report=term-missing`); cuatro puertas en 0.
  - **Evidencia**:

---

## Phase 5: User Story 4 — La conexión es verificable sin red (P2)

- [ ] T008 [US4] Determinismo: 20 ejecuciones idénticas y sin red (`tests/integration/test_bootstrap_session.py`)
  - **Archivos**: `tests/integration/test_bootstrap_session.py` (ampliación)
  - **Dependencias**: T006
  - **Criterios relacionados**: FR-012; Historia 4 (escenario 1); SC-004
  - **Estimación**: 20 min
  - **Pruebas primero**: ejecutar 20 veces la misma sesión (reloj e identificadores inyectados, base `:memory:` nueva en cada una) y comparar la salida de la terminal y los eventos guardados: idénticos; el guardia de red no se dispara. Si falla, la causa es no determinismo en la composición (orden de construcción, reloj real) y se corrige en `bootstrap.py`.
  - **Verificación**: pasa 20/20; sin cambios de código si la composición ya es determinista (se anota).
  - **Evidencia**:

- [ ] T009 [P] [US4] Guarda de arquitectura `tests/architecture/test_bootstrap_boundaries.py` y verificación de fronteras
  - **Archivos** (fila: guarda `ast` de la frontera nueva, skill `verificar-fronteras-hexagonales`): `tests/architecture/test_bootstrap_boundaries.py` (nuevo)
  - **Dependencias**: T005 (necesita `bootstrap.py` y `__main__.py`)
  - **Criterios relacionados**: FR-011, FR-014; Historia 4 (escenario 2)
  - **Estimación**: 40 min
  - **Pruebas primero** (autopruebas con fragmentos sintéticos y prueba de mutación sobre copias en `tmp_path`, como `test_cli_boundaries.py`; reutilizar `forbidden_imports`/`find_config_reads`/`terminal_uses`, no copiarlos): (a) nada en `core/`, `cli/`, `adapters/` ni `config.py` importa `harness_agent.bootstrap` ni `harness_agent.__main__`; (b) `bootstrap.py` solo importa stdlib, `harness_agent.core`, `harness_agent.config`, `harness_agent.cli` y la API pública de cada paquete de `adapters` (nunca un submódulo, y los nombres existen en `__all__`); (c) `bootstrap.py` no lee `os.environ`/`os.getenv` ni usa `print`/`input`/`sys.stdout` como llamada directa; (d) `__main__.py` solo importa `bootstrap` (y `sys` si lo necesita); (e) `bootstrap.py` es el único módulo de `src/` que importa a la vez `core`, `adapters`, `cli` y `config`.
  - **Verificación**: `pytest tests/architecture` en verde con la guarda nueva; se informa qué reglas cubre, ningún archivo viola una regla y no se añadió ninguna excepción a las guardas existentes.
  - **Evidencia**:

---

## Phase 6: Documentación y cierre

- [ ] T010 Documentación de cierre: `CLAUDE.md`, skills (ambas copias) y `docs/PROGRESO.md`
  - **Archivos**: `CLAUDE.md`, `.claude/skills/estructura-carpetas-harness/references/arbol.md`, `.claude/skills/verificar-fronteras-hexagonales/SKILL.md`, sus copias idénticas en `.agents/skills/`, `docs/PROGRESO.md`
  - **Dependencias**: T007, T008, T009
  - **Criterios relacionados**: Principio VIII; regla «las skills describen el código real»; PD-08
  - **Estimación**: 40 min
  - **Verificación**: `CLAUDE.md`: fila nueva en «Qué existe hoy» (`bootstrap.py`, `__main__.py`, comando), se retira «`bootstrap.py` aún no existe» y «raíz de composición ni punto de entrada ejecutable» de «Aún no hay», el diagrama de arquitectura pierde el «aún no existe», la numeración de specs pasa a «existen 001–018, falta 008; la siguiente es 019». `arbol.md` quita «(planeado)» de `bootstrap.py` y añade `__main__.py`; la skill de fronteras añade `test_bootstrap_boundaries.py` a la tabla de guardas. Las dos copias de cada skill quedan idénticas (`diff -r` sin diferencias). `PROGRESO.md`: fila → `En revisión` con archivos y evidencia reales, PD-08 marcada como resuelta (dueño C, historia propuesta), bloque de observaciones con los 9 hallazgos del plan y una línea por tarea en el Registro de cambios; tabla *Resumen* intacta.
  - **Evidencia**:

- [ ] T011 Verificación final: puertas de calidad, archivos protegidos y lista de comprobación
  - **Archivos**: ninguno (verificación); `tasks.md` (marcas con evidencia)
  - **Dependencias**: T010
  - **Criterios relacionados**: Principios IV y IX; Output Contract de las tres skills
  - **Estimación**: 30 min
  - **Verificación**: `ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest --cov=harness_agent --cov-report=term-missing` en 0 y `pytest tests/architecture` en verde; `git diff --exit-code $(git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py tests/doubles docs/archivo` sin diferencias, y `git diff` de `core/loop.py`, `core/in_memory_event_bus.py` y `cli/` vacío; lista de comprobación de `capas-y-reglas.md` del plan revisada **contra el código** (12 respuestas sí/no); `.coverage*` borrado.
  - **Evidencia**:

---

## Phase 7: Tareas humanas finales (Claude **no** las marca)

- [ ] T012 *(humana)* Ratificación del PO de AC-P1 a AC-P3 y del ID definitivo (ver T002)
- [ ] T013 *(humana)* Revisión cruzada por una persona de A o B (diseño de la composición, mensajes, hallazgos 4, 5 y 6 del plan)
- [ ] T014 *(humana)* CI remota en `ubuntu-latest` y `windows-latest` en verde
- [ ] T015 *(humana)* Prueba manual con un modelo real (`quickstart.md` §4), incluido SC-006 (arranque < 2 s sin contar la carga de la biblioteca) y el doble Ctrl-C en el prompt

---

## Dependencias y orden de ejecución

```text
T001 ─▶ T003 ─▶ T004 ─▶ T005 ─┬─▶ T006 ─▶ T008 ─┐
                              ├─▶ T007 ──────────┼─▶ T010 ─▶ T011 ─▶ T012–T015
                              └─▶ T009 [P] ──────┘
T002 (humana) puede ocurrir en cualquier momento; bloquea solo `Hecha`
```

- **MVP**: T003 + T004 + T005 + T006 (Historia 1 y 2: una tarea real, guardada). T007 es la Historia 3; T008 y T009 la Historia 4.
- **Paralelo**: T009 es independiente de T006 a T008 (otro archivo) una vez existe `bootstrap.py`; T007 y T006 tocan archivos de prueba distintos pero ambas ampliarían `bootstrap.py` solo en T007, por eso T006 va antes.

## Estimación frente al presupuesto

| Concepto | Minutos |
|---|---|
| T001 | 20 |
| T003 a T009 (trabajo con código) | 40 + 30 + 40 + 40 + 40 + 20 + 40 = 250 |
| T010, T011 | 40 + 30 = 70 |
| **Total de Claude** | **340 min (≈ 5,7 h)** |
| Presupuesto asignado por el PO | 180 min (3 h) |

La estimación es **1,9 veces** el presupuesto (el patrón se repite en HU-00-03, HU-01-03 y HU-06-01). Para volver a 3 h habría que quitar la prueba de interrupción de T006 (20 min) y fusionar T008 con T006 (20 min), sin llegar. Se avisa a C y al PO en `PROGRESO.md` (T001) en lugar de recortar pruebas que protegen AC-P2 y AC-P3.

## Cobertura de los requisitos

| Requisito | Tarea |
|---|---|
| FR-001 comando único | T005 |
| FR-002 configuración con sus errores | T005, T007 |
| FR-003 construir todas las piezas | T003 |
| FR-004 registrador antes del primer evento | T003, T006 |
| FR-005 sesión nueva al arrancar | T003 |
| FR-006 historial continuo | T004, T006 |
| FR-007 sin área: herramientas desactivadas y aviso | T003, T004, T006 |
| FR-008 fallos de arranque en una línea | T007 |
| FR-009 cierre del almacén y códigos de salida | T005, T007 |
| FR-010 la clave no aparece en ninguna salida | T007 |
| FR-011 no cambia puertos, bucle, CLI… | T009, T011 |
| FR-012 todo inyectable | T003, T005, T008 |
| FR-013 aprobación denegada con motivo | T004, T006 |
| FR-014 único importador de las cuatro capas | T009 |
| SC-001 un solo comando | T005, T015 |
| SC-002 eventos guardados = mostrados | T006 |
| SC-003 una línea, código ≠ 0, sin clave | T007 |
| SC-004 20 ejecuciones idénticas, sin red | T008 |
| SC-005 nada fuera del área | T006 |
| SC-006 arranque < 2 s sin la biblioteca | T015 (manual) |
| SC-007 cuatro puertas, 100 % del módulo | T007, T011 |

## Archivos protegidos (verificar antes de cerrar)

`src/harness_agent/core/interfaces/`, `src/harness_agent/core/events.py`, `src/harness_agent/core/loop.py`, `src/harness_agent/core/in_memory_event_bus.py`, `src/harness_agent/cli/`, `tests/doubles/`, `docs/archivo/`, `.github/workflows/ci.yml`.
