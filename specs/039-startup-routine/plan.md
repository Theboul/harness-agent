# Plan: HU-11-08.2 — Rutina de arranque

**Spec**: [spec.md](spec.md) · Skills aplicadas: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness`, `verificar-fronteras-hexagonales`.

## Estructura (ruta y fila de la tabla que la justifica)

| Archivo | Fila | Contenido |
|---|---|---|
| `core/startup/briefing.py` | Regla de negocio → subpaquete de `core/` | Puro: `CheckResult`, `StartupFacts`, `build_briefing`, saneo y marco |
| `core/startup/gated.py` | Regla de negocio | `GatedCommandRunner`: política → aprobación → ejecución (misma lógica que el verificador, con eventos existentes) |
| `core/startup/routine.py` | Regla de negocio | `StartupRoutine(...).run() -> Briefing \| None`; `ProgressReader` (Protocol local; `ProgressFile` ya lo cumple) |
| `core/startup/__init__.py`, `core/__init__.py` | exportación pública | |
| `bootstrap.py` | Unir piezas | `Composition.startup`, `_startup_routine(...)`, y `run_session` antepone el texto a la primera petición |
| `tests/unit/core/startup/`, `tests/integration/test_startup_routine.py`, `tests/architecture/test_startup_boundaries.py` | espejo de `src/` | |

No hay puerto nuevo (`core/interfaces/` intacto) ni evento nuevo. Los comandos se ejecutan con el `CommandRunner` de `core/verification` (`make_command_runner`, ya existente en `adapters/tools`). El nombre del archivo sale de `progress_file_name` (API pública).

## Decision Gates

Regla en `core/`: sí. Puerto: no hace falta (la E/S es `ProgressFile.read` y `CommandRunner`, ya existentes e inyectados). Adaptador: ninguno nuevo. Conexión: `bootstrap.py`. Prueba: unitarias con dobles sin red; integración con `compose`/`run_session` reales.

## Lista de comprobación (`capas-y-reglas.md`)

`core/` solo stdlib+núcleo: sí · sin E/S, entorno ni terminal: sí · dependencias por constructor: sí · tipos `frozen`: sí · falla cerrada: sí · cancelación no capturada: sí · eventos solo del catálogo: sí · no toca `core/interfaces/`, `events.py`, `loop.py`: sí · guarda `ast` nueva: sí · adaptador con reglas de negocio: no aplica · «no» sin justificar: ninguno.

## Constitution Check

Principios V (AC inmutables), VI (Sprint 3), VII, VIII cumplidos; sin secretos; textos al usuario en español.

## Riesgos

El contenido del progreso es no confiable (la nota la escribe el agente): va delimitado y saneado. La prueba básica ejecuta código editable por el agente (R-21, PD-06).
