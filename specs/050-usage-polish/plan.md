# Plan: HU-06-07 — Pulido de uso del arnés

**Spec**: [spec.md](spec.md) · Skills: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness`, `verificar-fronteras-hexagonales`.

## Decision Gates (arquitectura-hexagonal-clean)

| Gate | Resultado |
|---|---|
| ¿Regla de negocio nueva en `core/`? | **No.** Es composición y presentación. |
| ¿Puerto nuevo? | **No.** Se reutiliza `AskFn` (de `adapters/tools`) y `ConsoleQuestioner`. |
| ¿Adaptador? | `adapters/providers/litellm_provider.py`: parámetro `debug` (invocable inyectado); no lee el entorno. |
| ¿Dónde se conecta? | Solo `bootstrap.py`: `HARNESS_DEBUG_PROVIDER` del entorno inyectado, prefijo de git, avisos de modo, oferta. |
| ¿Cómo se prueba? | Unitarias con `completion` falsa y E/S en memoria; integración con `run_session`. |

## Estructura (estructura-carpetas-harness)

| Archivo | Fila |
|---|---|
| `adapters/providers/litellm_provider.py` (cambio) | Código de proveedores → `adapters/providers/` |
| `bootstrap.py` (cambio) | Unir piezas → `bootstrap.py` |
| `cli/session_commands.py` (cambio: textos de la oferta; los avisos al modelo van en `bootstrap.py`) | Texto de comandos de sesión → `cli/` |
| `tests/unit/adapters/providers/test_litellm_debug.py`, `tests/unit/test_bootstrap_git.py` (ajuste), `tests/unit/test_bootstrap_mode_notice.py`, `tests/unit/test_bootstrap_plan_offer.py` | Equivalentes en `tests/` |
| `tests/architecture/test_usage_polish_boundaries.py` | Guarda `ast` |

## Diseño

1. `LiteLLMProvider(..., debug=None)`: en `complete`, si la llamada falla con una excepción no canónica, `debug(clean(str(exc))[:2000])` dentro de un `try/except Exception` que nunca altera el error canónico. `bootstrap._default_provider(config, debug=None)`; `compose` construye la fábrica por defecto con `_debug_sink(environ)` (apagado → `None`).
2. `WorkMode` (estado mínimo en `bootstrap.py`) gana `told_planning` (el modo que el modelo conoce); `take_notice()` devuelve el texto si `planning != told_planning` y marca lo dicho; `turn()` lo antepone a la tarea; `/nueva` y `/reanudar` llaman a `forget()`.
3. `_provisional_prefix(system, area, commands, task)`: git solo con `area is not None and task is not None`. `history_prefix` lo hereda `/nueva`.
4. Oferta en `run_session.run_turn` (tras el turno): si `work_mode.planning`, el solo lectura no está `locked` y hay `ask`, se pregunta con `Question(…, allow_free_text=False)`; `number == 1` → `_implement_command(...)()` y se escribe su línea. Todo lo demás (incluida una excepción de `ask`) = nada. `Composition.ask` guarda el `AskFn`.

## Constitution Check

| Principio / skill | Resultado |
|---|---|
| Núcleo solo stdlib, sin E/S; `core/` sin cambios | Cumple. |
| Falla cerrado | Cumple: oferta sin respuesta deja el solo lectura; un fallo del sumidero de depuración no cambia el error. |
| Contratos protegidos intactos | Cumple. |
| Sin secretos | Cumple: depuración con `_clean` y redactor, solo `stderr`, nunca a disco. |
| Lista `capas-y-reglas.md`: dependencias por constructor / una raíz de composición / sin puerto nuevo / adaptador sin reglas de negocio / `core/` sin E-S | sí / sí / sí / sí / sí |

## Hallazgos esperados

1. El texto del 400 puede contener la petición de la persona (opt-in y solo `stderr`).
2. Ocultar herramientas de escritura en `/plan` no se hace (ver spec).
3. Reinicio de límites en `/nueva`: solicitud a A (`LimitTracker.reset()`, `AgentLoop.reset_limits()` en `core/loop.py`).
4. La tarea de la oferta (T005) es separable: HU-06-06 la ratifica el PO.
