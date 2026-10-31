# Contrato: `RetryingProvider`

```text
RetryingProvider(inner: Provider, policy: RetryPolicy, *,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 observer: Callable[[RetryAttempt], None] | None = None) -> Provider
async complete(messages, tools=None) -> ProviderResponse
```

1. Cumple el puerto `Provider`; pasa `messages` y `tools` tal cual a `inner` en cada intento.
2. Devuelve la primera respuesta correcta de `inner`.
3. Reintenta solo `ProviderTimeout`, `ProviderUnavailable` y `RateLimited`. Todo otro `ProviderError` se propaga en el acto, sin espera.
4. Máximo `policy.max_attempts` llamadas a `inner`; agotadas, propaga el **último** error (misma instancia, sin envolver).
5. Espera antes del reintento *n*: `min(base·2^(n−1), max_delay)`; con `retry_after` válido ≥ eso; `retry_after > max_delay` ⇒ propaga sin reintentar.
6. `observer` recibe un `RetryAttempt` antes de cada espera; si lanza, se ignora (`Exception`; `CancelledError` no).
7. `asyncio.CancelledError` y cualquier excepción que no sea `ProviderError` se propagan sin captura ni reintento (D-01), también durante la espera.
8. Ningún texto del error original, de los mensajes ni de las herramientas entra en `RetryAttempt`.

**Adaptador LiteLLM**: `RateLimitError` ⇒ `RateLimited` (mensaje propio de HU-07-02; `retry_after` leído del atributo del mismo nombre si es válido). `PaymentRequiredError`, `BudgetExceededError` siguen siendo `QuotaExceeded`.

**Configuración**: `[retries]` `max_attempts`, `base_delay`, `max_delay` (ver `data-model.md`).
