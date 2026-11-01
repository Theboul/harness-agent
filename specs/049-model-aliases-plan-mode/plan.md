# Plan: HU-06-06 — Varios modelos por alias y modo de planificación

**Spec**: [spec.md](spec.md) · Skills aplicadas: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness`, `verificar-fronteras-hexagonales`.

## Decision Gates (arquitectura-hexagonal-clean)

| Gate | Resultado |
|---|---|
| ¿Regla de negocio? | Sí, pequeña: `core/permissions/mode_switch.py` (`ReadOnlySwitch`, `SwitchablePolicy`): conmutar entre dos políticas. |
| ¿Puerto nuevo? | **No.** `Provider` y `PermissionPolicy` existentes. |
| ¿Adaptador? | `adapters/providers/model_switch.py` (`ModelSwitch`): sin E/S propia; construye proveedores con una función inyectada. |
| ¿Dónde se conecta? | Solo `bootstrap.py` (`compose`, `/model`, `/plan`, `/implementar`). |
| ¿Cómo se prueba? | Unitarias con `FakeProvider`/`ScriptedPolicy`; integración con `AgentLoop` real; LiteLLM nunca se carga. |

## Estructura (estructura-carpetas-harness)

| Archivo | Fila |
|---|---|
| `src/harness_agent/core/permissions/mode_switch.py` | Regla de permisos → `core/permissions/` |
| `src/harness_agent/adapters/providers/model_switch.py` | Código de proveedores → `adapters/providers/` |
| `src/harness_agent/cli/session_commands.py` (cambio) | Texto de comandos de sesión → `cli/` |
| `config.py`, `bootstrap.py`, `config.example.toml`, `README.md` | Lectura de configuración / composición |
| `tests/unit/core/permissions/test_mode_switch.py`, `tests/unit/adapters/providers/test_model_switch.py`, `tests/unit/test_config_models.py`, `tests/unit/test_bootstrap_models.py`, `tests/unit/cli/` (ampliado), `tests/integration/test_model_switching_agent_loop.py` | Equivalentes en `tests/` |
| `tests/architecture/test_model_switch_boundaries.py` | Guarda `ast` de los módulos nuevos |

## Diseño

- `ModelSwitch(default_model, default_provider, aliases, build)` es un `Provider`; `select(alias)` usa el proveedor en caché o lo construye con `build(alias)`; cualquier fallo de `build` se traduce a `ModelUnavailable(code)` sin copiar el texto de la excepción.
- `compose` envuelve el proveedor base en `ModelSwitch` y ese en `RetryingProvider`. `build(alias)` clona la configuración con el modelo y la clave del alias y llama a la misma fábrica de proveedores (así los dobles de las pruebas sirven).
- `_compactor`, el renovador esencial y `/nueva` leen `switch.model` en vez de `config.model`.
- Política: `SwitchablePolicy(restricted=ReadOnlyPolicy(cadena,…), open=cadena, switch)`; `ReadOnlySwitch(enabled, locked)`. `locked` = solo lectura fijado al arrancar.
- `WorkMode.planning` (estado mínimo en `bootstrap.py`) distingue «planificación» del solo lectura fijo.
- `/model` pasa a comando con argumento (los de `commands` tienen prioridad sobre `argument_commands`, por eso se mueve).

## Constitution Check

| Principio / skill | Resultado |
|---|---|
| Núcleo solo stdlib, sin E/S | Cumple. |
| Falla cerrado | Cumple (error → `DENY`; alias no usable → nada cambia). |
| Contratos protegidos intactos | Cumple. |
| Sin secretos en el repo | Cumple (claves solo del entorno; `Secret` no se imprime). |
| Lista `capas-y-reglas.md`: dependencias por constructor / una raíz de composición / sin puerto nuevo justificado / adaptador sin reglas de negocio | sí / sí / sí / sí |

## Hallazgos esperados

1. La sesión guardada conserva el modelo con el que nació; el cambio en caliente no actualiza la columna `model`.
2. El historial viaja entre proveedores distintos tal cual: la compatibilidad de llamadas a herramientas entre Gemini y Groq se prueba solo con dobles; queda la prueba manual con claves reales.
3. `cli/session_commands.py` (protegido por defecto) gana campos con valor por defecto.
