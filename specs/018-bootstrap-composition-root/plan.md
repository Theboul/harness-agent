# Implementation Plan: Raíz de composición y punto de entrada ejecutable (propuesta HU-00-08)

**Branch**: `018-bootstrap-composition-root` (carpeta de la spec; el trabajo sigue en la rama `feat/bootstrap-composition-root`) | **Date**: 2026-10-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/018-bootstrap-composition-root/spec.md`

## Summary

Un único módulo, `src/harness_agent/bootstrap.py`, une las piezas que ya existen (configuración, `LiteLLMProvider`, las cuatro herramientas de archivos con `WorkspaceArea`, `DefaultPermissionPolicy`, `InMemoryEventBus`, `SqliteSessionStore` con `attach_event_recorder`, `AgentLoop` y `run_cli`) y expone `main() -> int`. Un `__main__.py` de tres líneas permite `python -m harness_agent` y `pyproject.toml` declara el comando `harness`. La composición se separa en una función síncrona `compose(config, ...)` (construye y falla cerrada, probable con dobles) y una función `run_session(composition, ...)` (corre la CLI). No cambia ningún puerto, evento, bucle, política, almacén, herramienta ni la CLI (FR-011): si algo no encaja, es un hallazgo.

## Technical Context

**Language/Version**: Python 3.12 (`>=3.12,<3.13`), tipado estricto (`mypy --strict`)

**Primary Dependencies**: biblioteca estándar, `harness_agent.core`, `harness_agent.config`, `harness_agent.cli` y la API pública de `harness_agent.adapters.storage`, `.system` y `.tools`; dos imports de submódulo, **autorizados de forma explícita** porque no tienen otra vía pública: `harness_agent.core.loop` (`AgentLoop` no está en `core.__all__`) y `harness_agent.adapters.providers.litellm_provider` (`providers/__init__.py` solo tiene docstring por regla de `test_providers_boundaries.py`); **sin dependencias nuevas** (`litellm` sigue siendo el extra opcional de HU-07-02)

**Storage**: la base SQLite de HU-03-01/02 (ruta de `paths.sessions_db`); esta historia no cambia el esquema

**Testing**: `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`); `FakeProvider` inyectado, flujos de texto en memoria, base en memoria o en `tmp_path`, reloj e identificadores fijos, guardia de red; cobertura del módulo nuevo 100 % de líneas y ramas

**Target Platform**: Windows y Linux (CI en `ubuntu-latest` y `windows-latest`, Python 3.12)

**Project Type**: biblioteca/CLI con arquitectura hexagonal (raíz de composición)

**Performance Goals**: arranque hasta el prompt < 2 s con el proveedor ya cargado o simulado (SC-006); la carga de `litellm` (≈ 4 s, HU-07-02) se paga una sola vez al construir el proveedor real

**Constraints**: no cambiar `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `cli/` ni `tests/doubles/`; la clave llega solo de `Secret` y nunca se imprime; `bootstrap.py` no lee `os.environ` por su cuenta (lo recibe); ningún mensaje de arranque reproduce valores recibidos

**Scale/Scope**: 2 módulos nuevos (`bootstrap.py` ≈ 200 líneas, `__main__.py` 3 líneas), 1 cambio de `pyproject.toml` (`[project.scripts]`), 1 guarda de arquitectura, ≈ 5 archivos de prueba; 3 h de presupuesto (decisión del PO, Sprint 1, área C). **La estimación de `tasks.md` es 340 min (≈ 5,7 h, 1,9 veces el presupuesto)**: el PO acepta el exceso o recorta alcance al implementar (aviso de capacidad en `PROGRESO.md`)

## Constitution Check

*GATE: pasa antes de la Fase 0 y se revisó de nuevo tras el diseño. Sin violaciones; las decisiones de interpretación se listan en «Complexity Tracking».*

| Principio / regla | Cumplimiento |
|---|---|
| I — una historia por spec | una sola historia propuesta (`HU-00-08` provisional); `specs/018-…` |
| II — microtareas de 15–40 min | `tasks.md`: 15 tareas (7 con código), ninguna > 40 min |
| III — Python 3.12, modular, tipado | funciones pequeñas con dependencias por parámetro, `mypy --strict`, docstrings en inglés |
| IV — pruebas, calidad y CI en dos SO | cuatro puertas + `pytest tests/architecture`; `ci.yml` no cambia |
| V — criterios inmutables | no se toca ningún criterio existente; AC-P1 a AC-P3 son nuevos y quedan marcados «propuestos» hasta que el PO los ratifique |
| VI — disciplina de sprints | asignada por el PO al Sprint 1 (área C); no entra nada de sprints futuros: sin límites, reanudar, shell, contexto ni cancelación de turno |
| VII — consulta quirúrgica | solo las fichas de las dependencias, `PROGRESO.md` (PD-08) y los archivos nombrados |
| VIII — `PROGRESO.md` | tarea de cierre: fila nueva en la tabla del Sprint 1 (`En revisión`), PD-08 resuelta, observaciones, registro por tarea |
| IX — DoD y verificación humana | tareas humanas finales sin marcar: ratificación de los AC por el PO, revisión cruzada, CI remota, prueba manual con modelo real |
| X — `docs/archivo/` | no se toca |
| V-01 / el núcleo no imprime | los mensajes de arranque los escribe `bootstrap.py` (capa de composición), no `core/` |
| V-02 / falla cerrada | sin área no hay herramientas de archivos; cualquier excepción no prevista al arrancar termina con código 2 sin detalle |
| V-11 / Ctrl+C | el bucle ya publica `INTERRUPTED` al cancelarse; la composición solo termina el programa con 130 (cancelar solo el turno queda fuera, ver Complexity Tracking) |
| V-13 / secretos | la clave vive en `Secret`; ningún mensaje de arranque incluye valores; prueba con centinela |
| V-14 / `FakeProvider` | la composición acepta un proveedor inyectado; las pruebas usan `FakeProvider` |
| D-01 (asyncio) | una sola llamada a `asyncio.run`; `CancelledError`/`KeyboardInterrupt` no se tragan |
| Skill `arquitectura-hexagonal-clean` | recorrido de *Decision Gates* y lista de comprobación abajo |
| Skill `estructura-carpetas-harness` | ruta de cada archivo con su fila abajo |
| Skill `verificar-fronteras-hexagonales` | guarda nueva `test_bootstrap_boundaries.py` y tarea de verificación |

### Decision Gates (`arquitectura-hexagonal-clean`)

| Pregunta | Resultado |
|---|---|
| ¿Es regla o comportamiento nuevo del núcleo? | No. Es solo conexión: ninguna regla nueva. Las reglas (permisos, validación, límites) siguen en `core/` |
| ¿Necesita algo de fuera? | Todo lo externo ya tiene puerto y adaptador (`Provider`, `SessionStore`, `AuthorizedArea`, `Tool`); la terminal y la configuración ya tienen su capa (`cli/`, `config.py`). Ningún puerto nuevo |
| ¿Quién lo implementa? | `bootstrap.py` es la raíz de composición, la única excepción prevista a «no conocer adaptadores» |
| ¿Cómo se conecta? | Por constructor, desde `compose()`; todo lo que toca el exterior entra por parámetro (proveedor, reloj, identificadores, flujos, entorno) |
| ¿Cómo se prueba? | `compose` y `main` con dobles y `FakeProvider`; integración con el `AgentLoop` real; guarda `ast` de la frontera nueva |
| ¿Es asíncrono? | `run_session` sí (llama a `run_cli`); `compose` es síncrona |

### Lista de comprobación (`capas-y-reglas.md`)

| # | Pregunta | Respuesta |
|---|---|---|
| 1 | ¿La regla de negocio está en `core/` y no en un adaptador? | **Sí.** `bootstrap.py` no decide permisos, límites ni validación; solo elige qué implementación va en cada puerto |
| 2 | ¿Todo lo externo pasa por un puerto con tipos del dominio? | **Sí.** Se usan los puertos existentes; la composición no abre red ni disco por su cuenta (la comprobación de que la carpeta del área existe la hace `WorkspaceArea`/el almacén) |
| 3 | ¿Puertos, entidades y eventos siguen sin cambios? | **Sí.** Se comprueba con el `git diff --exit-code` de CLAUDE.md |
| 4 | ¿Errores externos traducidos sin reproducir valores? | **Sí.** Los errores de arranque se traducen a una línea propia; los no previstos se reducen a `error inesperado` con el tipo, nunca el texto |
| 5 | ¿Dependencias inyectadas y conectadas solo en `bootstrap.py`? | **Sí.** Es el cumplimiento de esta regla: cierra el «aún no existe» de las historias previas |
| 6 | ¿El núcleo se probó con dobles, sin red, disco ni claves? | **Sí.** No se toca el núcleo; la composición se prueba con `FakeProvider` |
| 7 | ¿El adaptador real tiene prueba de contrato en `tests/contracts/`? | **No aplica:** no se crea ningún adaptador ni puerto |
| 8 | ¿Pasa `pytest tests/architecture` y la guarda nueva en Windows y Linux? | **Por verificar** en la implementación (tarea de fronteras) y en la CI remota |
| 9 | ¿El núcleo emite eventos en lugar de imprimir? | **Sí, sin cambios.** Los avisos y errores de arranque son de la capa de composición, antes de que exista el bucle |
| 10 | ¿Lo público está exportado en `core/__init__.py`? | **No aplica:** no se añade nada a `core/`; `bootstrap.py` importa de `harness_agent.core` |
| 11 | ¿Se respetan las decisiones de diseño? | **Sí:** falla cerrada y secretos ocultos; historial intacto (no hay compactación aún) |
| 12 | ¿Otro integrante revisó el cambio? | **No todavía:** tarea humana final (revisión cruzada) |

## Project Structure

### Documentation (this feature)

```text
specs/018-bootstrap-composition-root/
├── spec.md
├── plan.md              # este archivo
├── research.md          # Fase 0: decisiones y alternativas
├── data-model.md        # Fase 1: Composition, orden de construcción, códigos de salida
├── quickstart.md        # Fase 1: cómo comprobar la historia a mano y con pruebas
├── contracts/
│   └── bootstrap_contract.md   # API pública, mensajes, códigos de salida, tabla de cableado
├── checklists/
│   └── requirements.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (rutas y fila de `estructura-carpetas-harness` que las justifica)

| Archivo | Fila de la tabla | Notas |
|---|---|---|
| `src/harness_agent/bootstrap.py` (nuevo) | «Unir piezas y elegir implementaciones → `bootstrap.py`» | única raíz de composición; no exporta nada a `core/` |
| `src/harness_agent/__main__.py` (nuevo) | «Unir piezas…» (entrada del paquete; delega todo en `bootstrap.main`) | 3 líneas, sin lógica |
| `pyproject.toml` (cambio) | Tocar `pyproject.toml` activa la skill de fronteras | `[project.scripts] harness = "harness_agent.bootstrap:main"`; sin dependencias nuevas |
| `tests/unit/test_bootstrap_compose.py` (nuevo) | «Pruebas» de `arbol.md`: módulos de la raíz del paquete van en `tests/unit/` (como `test_config_*`) | cableado, orden, fallos que cierran el almacén |
| `tests/unit/test_bootstrap_main.py` (nuevo) | idem | `run_session` (historial, avisos), `main()` feliz, errores de arranque, códigos de salida, interrupción, secretos |
| `tests/unit/test_entry_point.py` (nuevo) | idem | `__main__` y el comando declarado en `pyproject.toml` |
| `tests/integration/test_bootstrap_session.py` (nuevo) | «integración con el `AgentLoop` real» | historias 1, 2 y 4; 20 ejecuciones idénticas; guardia de red |
| `tests/architecture/test_bootstrap_boundaries.py` (nuevo) | guarda `ast` de la frontera nueva (skill de fronteras) | ver «Diseño» §6 |
| `CLAUDE.md`, `.claude/skills/estructura-carpetas-harness/references/arbol.md`, `.claude/skills/verificar-fronteras-hexagonales/SKILL.md` y sus copias en `.agents/skills/` | regla «las skills describen el código real» | `bootstrap.py` deja de ser «planeado»; la guarda nueva entra en la tabla |
| `docs/PROGRESO.md` | Principio VIII | fila nueva, PD-08, observaciones |

No se crea ninguna carpeta nueva, ningún puerto ni ningún adaptador. **Archivos protegidos** (verificar antes de cerrar): `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `cli/`, `tests/doubles/`, `docs/archivo/`.

## Diseño (resumen; detalle en `data-model.md` y `contracts/`)

1. **`compose(config, *, provider_factory=None, clock=None, id_factory=None) -> Composition`**. Orden fijo (primero lo que puede fallar sin dejar rastro): proveedor → área y herramientas → política → bus → almacén → sesión → registrador → bucle. Si algo falla después de abrir el almacén, se cierra antes de propagar (nunca queda a medias). El registrador se conecta **antes** de entregar la composición, así que ningún evento se pierde (FR-004) y se persiste antes de que la CLI lo muestre.
2. **`Composition`**: contenedor inmutable (`@dataclass(frozen=True)`) con `loop`, `bus`, `store`, `session_id`, `notices` (avisos para el usuario, p. ej. «sin área») y un método `close()` que cierra el almacén.
3. **`run_session(composition, *, input_stream, output) -> int`**: crea el `history` de la sesión, define `run_turn(task)` que llama a `loop.run_turn(session_id=…, task=…, history=history)` (el historial se conserva entre líneas, FR-006), escribe los avisos y delega en `run_cli`. Devuelve su código (0 o 1).
4. **`main(*, environ=None, config_path=None, input_stream=None, output=None, error=None, provider_factory=None, clock=None, id_factory=None) -> int`**: `load_config` → `compose` → `asyncio.run(run_session(...))` → `close()`. Traduce a una línea en `error` los fallos de arranque conocidos (`ConfigError` y subclases, `ProviderDependencyError`, `SessionStoreError`) con código **2**; cualquier otra excepción de arranque se reduce a «error inesperado (Tipo)». `KeyboardInterrupt` → **130**, base cerrada, sin traza. El comando `harness` y `python -m harness_agent` llaman a `main()` sin argumentos.
5. **Proveedor por defecto**: `LiteLLMProvider(config.model, max_output_tokens=config.limits.max_output_tokens, api_key=config.api_key)`. `FakeProvider` vive en `tests/doubles/` y **no** se importa desde `src/`; un modelo `fake/…` no tiene tratamiento especial (se documenta como hallazgo).
6. **Guarda de fronteras**: (a) `config.py` no importa `bootstrap` y nada importa `__main__` (que `core/`, `cli/` y `adapters/` no importan `bootstrap` ya lo vigilan `test_core_no_terminal.py`, `test_cli_boundaries.py`, `test_adapters_boundaries.py` y `test_providers_boundaries.py`; no se duplica); (b) `bootstrap.py` solo importa stdlib, `harness_agent.core` (nombres de `__all__`), `harness_agent.config`, `harness_agent.cli` y la API pública (`__all__`) de `adapters.storage`, `.system` y `.tools`, **más exactamente dos submódulos autorizados por no tener vía pública**: `harness_agent.core.loop` y `harness_agent.adapters.providers.litellm_provider`; cualquier otro submódulo es una violación; (c) `bootstrap.py` no lee `os.environ`/`os.getenv`, no usa `print`/`input` ni `sys.stdout`; (d) `__main__.py` solo importa `bootstrap` y `sys`; (e) es el único módulo de `src/` que importa a la vez `core`, `adapters`, `cli` y `config` (FR-014). Detectores reutilizados de las guardas existentes, con autoprueba sobre fragmentos sintéticos.
7. **Interrupción**: se deja el comportamiento de `asyncio.run` (el primer Ctrl-C cancela la tarea principal y el bucle publica `INTERRUPTED`; ver `research.md` §4 para la limitación en el prompt). La composición no instala manejadores de señal.

## Hallazgos y notas para `PROGRESO.md` al cerrar (tarea de cierre)

1. Cierra PD-08: dueño de la raíz de composición = área C, Sprint 1, historia propuesta `HU-00-08` (ID provisional; el PO decide si la formaliza en `docs/04a`).
2. Los AC-P1 a AC-P3 son propuestos: ratificación del PO pendiente.
3. Aviso de capacidad: 3 h añadidas al Sprint 1 de C (R-22).
4. `SessionStore` y `SqliteSessionStore` no tienen forma de pasar una sesión a `completed`/`interrupted`: toda sesión queda `active`. Para B (HU-03-04 o posterior).
5. Ctrl-C en el prompt: `run_cli` lee con `readline()` bloqueante, así que el primer Ctrl-C no se atiende hasta una nueva línea o un segundo Ctrl-C. Para C (`cli/`) cuando se aborde la cancelación controlada.
6. Un modelo `fake/…` pasa la validación de configuración pero la composición real no sabe construirlo; falla en la primera llamada con `ProviderError`. Decisión pendiente: rechazarlo al arrancar o dejarlo.
7. `LITELLM_LOCAL_MODEL_COST_MAP=True` (nota de HU-07-02): la composición no toca el entorno; lo fija el usuario.
8. PD-09 (la base de sesiones queda dentro del árbol del área si `workspace_root` contiene `.harness/`) sigue abierta y se hace visible con este comando.
9. Prueba manual con un modelo real: tarea humana, omitida sin clave (como Sp1-45).

## Descomposición prevista (resumen; la versión vigente es `tasks.md`: 15 tareas, 7 con código)

1. Inicio (humana): ratificación de los AC propuestos y línea base de las cuatro puertas.
2. `compose()` + `Composition`: pruebas con dobles y construcción (cableado, orden, área ausente o inválida, cierre del almacén ante fallo) (≈ 40 min).
3. `run_session()` + historial entre líneas y avisos (≈ 30 min).
4. `main()`: errores de arranque, códigos 2 y 130, secretos con centinela (≈ 40 min).
5. `__main__.py` + `[project.scripts]` + prueba de entrada (≈ 20 min).
6. Integración con el bucle real: historias 1, 2 y 4, 20 ejecuciones idénticas, intento de escape, aprobación denegada, Ctrl-C que deja `INTERRUPTED` guardado (≈ 40 min).
7. Guarda de fronteras `test_bootstrap_boundaries.py` + verificación de fronteras (≈ 35 min).
8. Documentación de cierre: CLAUDE.md, skills (ambas copias), `PROGRESO.md` (≈ 30 min).
9. Cuatro puertas, protegidos y verificación final (≈ 20 min).
10. Fin (humanas, sin marcar): revisión cruzada, CI remota Ubuntu y Windows, prueba manual con modelo real, ratificación del PO.

## Complexity Tracking

No hay violaciones de la constitución ni de las skills. Decisiones de interpretación que conviene que el revisor vea:

| Decisión | Por qué | Alternativa descartada |
|---|---|---|
| Dos imports de submódulo autorizados (`core.loop`, `providers.litellm_provider`) | no existe otra vía pública: `AgentLoop` no está en `core.__all__` y `providers/__init__.py` solo puede tener docstring | exportar `AgentLoop` en `core/__init__.py` (cambio aditivo del núcleo que necesita el visto bueno de A) o relajar la guarda de `providers/` |
| Ctrl-C termina el programa (no solo el turno) | Lo decidió el PO en `/speckit-clarify`; V-11 completa (devolver el resultado al modelo en el turno siguiente) exige cancelar un turno y seguir, que es otra historia | Cancelar solo el turno: requiere decidir qué queda en el historial y tocar `cli/` o el bucle |
| Sin manejador de señal propio | `asyncio.run` ya cancela la tarea principal y el bucle publica `INTERRUPTED`; un manejador propio duplicaría esa lógica | Instalar `signal.signal`: cambia la semántica de la cancelación y no se puede probar igual en Windows |
| `main()` sin argumentos de línea de comandos | La spec no pide opciones; menos superficie y nada que validar | `argparse` con `--config`: fuera de alcance (la ruta ya se elige con `HARNESS_CONFIG`) |
| El proveedor se construye antes que el almacén | Un fallo del proveedor (dependencia ausente) no deja una sesión `active` huérfana en la base | Crear la sesión primero: más natural, pero deja filas huérfanas |
| `Composition` congelada con un método `close()` | Una sola cosa que cerrar hoy (el almacén); mantiene `main` simple | Un `ExitStack`: sobredimensionado para un recurso |
| La guarda (e) «único importador de las cuatro capas» | Es la forma comprobable de FR-014 | Confiar en la revisión |
