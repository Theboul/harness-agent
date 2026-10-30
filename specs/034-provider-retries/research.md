# Research: HU-07-04 — Reintentos

## 1. Qué es «temporal»

- **Decisión**: `ProviderTimeout`, `ProviderUnavailable` y `RateLimited`. Todo lo demás (incluido `QuotaExceeded` sin subtipo, que cubre `PaymentRequiredError` y `BudgetExceededError`, y el `ProviderError` genérico) no se reintenta.
- **Rationale**: la ficha (regla 1) pide solo errores temporales; el crédito agotado no se arregla esperando; el error genérico incluye clave inválida, petición mal formada y respuesta ilegible, que tampoco.
- **Alternativas**: reintentar todo `QuotaExceeded` (descartada: gasta tiempo con crédito agotado); reintentar `ProviderError` genérico (descartada: no es seguro).

## 2. Distinguir límite de tasa sin tocar el puerto

- **Decisión**: `RateLimited(QuotaExceeded)` en `adapters/providers/errors.py`, con atributo `retry_after: float | None`. `ERROR_TABLE` mapea `RateLimitError` a él.
- **Rationale**: `core/interfaces/` es contrato de A, B y C. El subtipo sigue siendo `QuotaExceeded` para quien ya lo capture (el bucle solo lee `type(exc).__name__`; HU-07-05 podrá usar ambos).
- **Alternativas**: atributo en `QuotaExceeded` (cambia el puerto); mirar el texto del error (frágil y copia datos).

## 3. Pista de espera

- **Decisión**: el adaptador de LiteLLM lee, si existe, el atributo `retry_after` del error original (LiteLLM lo expone en algunas excepciones) y lo acepta solo si es `int`/`float` finito ≥ 0 (no `bool`). La envoltura la lee con `getattr(error, "retry_after", None)` bajo la misma validación. Espera = `max(exponencial, pista)`; pista > `max_delay` ⇒ no se reintenta.
- **Rationale**: respeta lo que el proveedor pide sin permitir esperas arbitrarias; no se leen cabeceras HTTP (dependen de la versión de LiteLLM).
- **Alternativas**: recortar la pista a `max_delay` (descartada: reintentar antes de lo pedido provoca otro 429 y gasta intentos).

## 4. Espera y cancelación

- **Decisión**: `sleep: Callable[[float], Awaitable[None]]` inyectado (por defecto `asyncio.sleep`). Se captura solo `ProviderError`; `CancelledError` (y cualquier otra excepción) sube sin tocar, también si llega durante la espera.
- **Rationale**: D-01. Pruebas sin espera real.

## 5. Registro de cada intento

- **Decisión**: `RetryingProvider(..., observer: Callable[[RetryAttempt], None] | None)`. `RetryAttempt(attempt, max_attempts, error_type, delay)`. `compose()` lo publica como `provider_error` con carga `{"reason": "retry", "error_type", "attempt", "max_attempts", "delay_seconds"}`. Un fallo del observador se descarta (FR-010).
- **Rationale**: `provider_error` ya existe en el catálogo de 17; ningún evento nuevo. Los eventos se guardan por sesión, por lo que se necesita la sesión **activa**: `bootstrap.py` mantiene un cursor mutable que `run_session` actualiza al reanudar.
- **Alternativas**: no publicar (incumple «registra cada intento»); evento nuevo `provider_retry` (cambia el catálogo, protegido).
- **Hallazgo**: `cli/render.py` mostrará una línea de «Error» genérica por cada reintento; mejora de C.

## 6. Configuración

- **Decisión**: `[retries]` con `max_attempts` (entero 1–10, defecto 5), `base_delay` (número > 0, defecto 2.0), `max_delay` (número ≥ `base_delay`, defecto 30.0, tope 600). Dataclass `Retries` en `config.py`; `bootstrap.py` la convierte en `RetryPolicy` del adaptador (los adaptadores no importan `config`).
- **Rationale**: ajustable para planes gratuitos; `max_attempts = 1` los apaga. Valida como `[limits]`: mensaje con el campo y qué es válido, sin repetir el valor.

## 7. Dónde se envuelve

- **Decisión**: en `compose()`, tras crear la sesión y antes del bucle y del compactador, de modo que **todas** las llamadas (turnos y resumen de compactación) se reintenten. Un `provider_factory` inyectado también se envuelve (las pruebas de integración con `FakeProvider` lo ejercitan).
- **Rationale**: la compactación llama al proveedor aparte (HU-02-03) y se beneficia igual.
