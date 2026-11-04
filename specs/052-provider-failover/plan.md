# Plan: HU-07-05 — Conmutación por fallo con umbral por modelo

**Spec**: [spec.md](spec.md) · Skills: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness`, `verificar-fronteras-hexagonales`.
**Contexto técnico**: Python 3.12, sin dependencias nuevas; núcleo solo biblioteca estándar; pruebas con `FakeProvider`, el bucle real y archivos SQLite reales en `tmp_path`.

## Decision Gates (arquitectura-hexagonal-clean)

| Gate | Resultado |
|---|---|
| ¿Regla de negocio nueva en `core/`? | **Sí, mínima**: `core/failover.py` — qué errores conmutan (`ELIGIBLE_ERRORS`, `is_failover_eligible`) y qué lleva probado un turno (`FailoverTurn`). Pura, sin E/S. |
| ¿Puerto nuevo? | **No.** `Provider` no cambia; la jerarquía `ProviderError` no cambia. `FailoverProvider` es una envoltura del puerto `Provider` en el adaptador, como `RetryingProvider` y `ModelSwitch`. |
| ¿Adaptador? | `adapters/providers/failover_provider.py` (`FailoverProvider`, `Switched`, `Switchable`) y `FailoverExhausted` en `adapters/providers/errors.py`. Usa el `ModelSwitch` por un `Protocol` mínimo (`alias`, `model`, `select`). |
| ¿Dónde se conecta? | Solo `bootstrap.py`, y solo con `[failover] models` no vacío (D-10, FR-012): envuelve al `RetryingProvider(ModelSwitch)`, publica `PROVIDER_SWITCHED` y la línea de pantalla, y `run_session` llama a `begin_turn()` antes de cada petición. |
| ¿Evento? | `PROVIDER_SWITCHED` ya existe en `core/events.py`: no hace falta tocar el catálogo (no hay caso A/B/C). |
| ¿Cómo se prueba? | Núcleo con tablas; envoltura con un proveedor interno falso y un `Switchable` falso; integración con `compose()` + `FakeProvider` + bucle real + `run_session`. |

## Estructura (estructura-carpetas-harness)

| Archivo | Fila de la tabla que lo justifica |
|---|---|
| `src/harness_agent/core/failover.py` | Regla de negocio → módulo de `core/`; se exporta en `core/__init__.py` |
| `src/harness_agent/adapters/providers/failover_provider.py` | Código de proveedores → `adapters/providers/` |
| `src/harness_agent/adapters/providers/errors.py` (cambio) | Error de dominio del adaptador → `errors.py` del paquete |
| `src/harness_agent/config.py` (cambio) | Lectura de configuración → `config.py`: `[failover] models`, `HarnessConfig.failover` |
| `config.example.toml` (cambio) | Sección `[failover]` comentada |
| `src/harness_agent/bootstrap.py` (cambio) | Unir piezas → `bootstrap.py`: envoltorio, observador, avisos de arranque, `begin_turn` |
| `src/harness_agent/core/__init__.py` (cambio) | Exportar lo público del núcleo |
| `tests/unit/core/test_failover.py` | Equivalente en `tests/` |
| `tests/unit/adapters/providers/test_failover_provider.py`, `test_failover_classification.py` | Equivalentes en `tests/` |
| `tests/unit/test_config_failover.py`, `tests/unit/test_bootstrap_failover.py` | Equivalentes en `tests/` |
| `tests/integration/test_failover_agent_loop.py` | Integración con el bucle real |
| `tests/architecture/test_failover_boundaries.py` | Guarda `ast` (plantilla de `verificar-fronteras-hexagonales`) |

## Diseño

1. **`is_failover_eligible(error)`**: `isinstance(error, (QuotaExceeded, ProviderTimeout, ProviderUnavailable))`; todo lo demás (el `ProviderError` genérico, `FailoverExhausted`, cualquier excepción) es no elegible.
2. **`FailoverTurn(chain)`**: `begin()` vacía los probados; `mark(key)`; `next_untried()` devuelve el primero de `chain` en orden que no se marcó, o `None`.
3. **`FailoverProvider.complete`**: si el turno no ha empezado, marca el alias activo (`switch.alias or DEFAULT_ALIAS`); llama al interno; ante un error no elegible o `CancelledError`, lo deja pasar; ante uno elegible llama a `_advance`: recorre `next_untried()`, marca, intenta `switch.select(key)` (un `ModelSwitchError` salta al siguiente con una línea fija) y, si cambió, avisa al observador y **repite la llamada**; sin candidatos lanza `FailoverExhausted`.
4. **`bootstrap.compose`**: crea el envoltorio después del `RetryingProvider` y del `WarningSink` (hay que subir la creación del sink), con los alias de respaldo utilizables (los que tienen clave); los que no, dan un aviso fijo en `notices`. El observador publica `PROVIDER_SWITCHED {from_model, to_model, reason}` en `SessionCursor.value` y escribe la línea por el `WarningSink`. `Composition.failover` guarda el envoltorio para que `run_session.turn` llame a `begin_turn()` antes de la compactación y del bucle. El compactador y el renovador siguen leyendo `switch.model` (AC-04 sin cambios).
5. **Config**: `[failover] models = [...]`; `_check_failover` valida contra los alias ya leídos de `[models]`.

## Dry run: pruebas existentes que cambian

Se aplicaron los cambios provisionales **reales** (`core/failover.py`, `adapters/providers/failover_provider.py`, `errors.py`, `config.py`, `core/__init__.py` y el cableado de `bootstrap.py` con el envoltorio, el evento, `begin_turn` y el campo `Composition.failover`), con la función apagada por defecto, se corrió la suite completa (`pytest --no-cov`: 8 956 pasadas, **1 fallida**, 48 omitidas) y se revirtió todo (árbol limpio). Al estar apagada por defecto, ninguna prueba de comportamiento se mueve (no se aplicó la opción «activa por defecto»: no hay alias por defecto que activar); no fallaron `test_core_public_api.py`, las pruebas de `config`, las de compactación ni el esquema SQLite (no cambia, sigue v5).

Pruebas existentes que cambian, **autorizadas por el usuario, pendientes de ratificar** (ejecutada antes sin tocar para ver el rojo previsto):

| # | Prueba existente | Por qué cambia | Ajuste |
|---|---|---|---|
| 1 | `tests/architecture/test_bootstrap_boundaries.py::test_bootstrap_imports_only_what_its_rule_allows` | `bootstrap.py` importa el submódulo `harness_agent.adapters.providers.failover_provider` (como ya hace con `model_switch`, `retrying_provider` y `litellm_provider`; `providers/__init__.py` no tiene API pública por regla) | Añadir ese submódulo a la lista de permitidos y a la frase de la regla |

Si al implementar falla cualquier otra prueba existente, se detiene el trabajo y se avisa.

## Constitution Check

| Principio / regla | Resultado |
|---|---|
| Núcleo solo stdlib y `harness_agent.core`, sin E/S ni terminal; todo sale por el bus | Cumple: `core/failover.py` es puro; el evento y la línea los saca `bootstrap.py`. |
| V-02 falla cerrada | Cumple: error desconocido = no elegible; lista agotada = error; sin `begin_turn` no hay bucle; función apagada por defecto. |
| V-13 redacción de secretos / sin secretos | Cumple: avisos, evento y `FailoverExhausted` llevan solo nombres de modelo, de variable y de clase de error. |
| V-14 `FakeProvider` | Cumple: sin red ni claves. |
| Contratos protegidos (`core/interfaces/`, `core/events.py`, `core/loop.py`, `core/context/compactor.py`, `core/redaction.py`, `core/verification/`, `tests/doubles/`) | Intactos. |
| Reintentos de HU-07-04 y límites de HU-01-06 | Sin cambios: la conmutación va por fuera de los reintentos y no suma llamadas al contador del bucle (una llamada repetida es una llamada del bucle). |

**Lista de comprobación de `capas-y-reglas.md`**

| Pregunta | Sí/No |
|---|---|
| ¿La regla de negocio está en `core/` y no en un adaptador? | Sí |
| ¿Todo lo externo pasa por un puerto con tipos del dominio? | Sí (`Provider`; el `Protocol` `Switchable` es del propio módulo y lo cumple `ModelSwitch`) |
| ¿Puertos, entidades y eventos sin cambios? | Sí |
| ¿Los errores externos se traducen a errores de dominio sin reproducir valores? | Sí (`FailoverExhausted` con texto fijo) |
| ¿Dependencias por constructor y conexión solo en `bootstrap.py`? | Sí |
| ¿El núcleo se probó con dobles, sin red, disco ni claves? | Sí |
| ¿El adaptador real tiene prueba de contrato en `tests/contracts/`? | No: `FailoverProvider` es una envoltura como `RetryingProvider` y `ModelSwitch`, que se prueban con unitarias e integración, no con contrato. |
| ¿Pasa `pytest tests/architecture` y la guarda nueva en Windows y Linux? | Sí en Windows local; Linux en la CI remota (H02) |
| ¿El núcleo emite eventos en lugar de imprimir? | Sí |
| ¿Lo público está exportado en `core/__init__.py`? | Sí |
| ¿Se respetan las decisiones de diseño (falla cerrada, historial intacto, secretos redactados)? | Sí |
| ¿Otro integrante revisó el cambio? | No todavía (H01) |

## Guarda de fronteras

`tests/architecture/test_failover_boundaries.py`: `core/failover.py` solo stdlib y núcleo, sin E/S ni entorno ni terminal, sin importar `adapters`, `cli`, `config` ni `core.loop`; ningún `except` de `failover_provider.py` captura `BaseException` ni `CancelledError`; `FailoverProvider` solo publica por el observador (no importa el bus ni `Event`); el módulo de la envoltura no nombra proveedores ni claves. Cada regla con su prueba de mutación. `failover_provider.py` también queda cubierto por `test_providers_boundaries.py` y `bootstrap.py` por `test_bootstrap_boundaries.py`.

## Archivos protegidos (no tocar)

`core/interfaces/`, `core/events.py`, `core/loop.py`, `core/context/compactor.py`, `core/redaction.py`, `core/verification/`, `core/in_memory_event_bus.py`, `tests/doubles/`, `docs/archivo/`. No se toca `cli/`.

## Mapeo a tareas del plan de sprints

HU-07-05 no tiene tareas `Sp3-xx` propias conocidas en este plan (la ficha depende de HU-07-03); se cuenta como una sola historia: T002 a T004 (reglas y envoltura), T005 (configuración), T006 (cableado), T007 y T008 (integración).

## Hallazgos esperados

1. AC-04 se cumple en la siguiente evaluación de la compactación, no a mitad de turno: un gancho a mitad de turno exigiría cambiar `core/loop.py` (de A) (D-12).
2. HU-07-03 sigue pendiente: la lista usa los alias de HU-06-06; si HU-07-03 define otra forma de segundo proveedor, hay que reconciliarlas.
3. El peor caso de una llamada es (modelos de la lista) × (`[retries] max_attempts`) intentos (D-15).
4. El cambio es persistente hasta `/model predeterminado` (D-06); el PO puede preferir volver al modelo configurado en cada turno.
5. La pantalla recibe la línea por el `WarningSink` (no por `cli/render.py`) para no tocar `cli/`; si C prefiere que el renderizador la formatee, basta suscribirse a `PROVIDER_SWITCHED`.
