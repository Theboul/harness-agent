# Data Model: HU-07-04

Sin tablas ni esquema nuevos. Tipos nuevos (todos `@dataclass(frozen=True)` salvo el error):

| Tipo | Módulo | Campos / validación |
|---|---|---|
| `RateLimited(QuotaExceeded)` | `adapters/providers/errors.py` | `retry_after: float \| None` (solo número finito ≥ 0; otro valor ⇒ `None`) |
| `RetryPolicy` | `adapters/providers/retrying_provider.py` | `max_attempts: int` (1–10), `base_delay: float` (> 0), `max_delay: float` (≥ `base_delay`); `ValueError` en español sin reproducir el valor |
| `RetryAttempt` | idem | `attempt: int` (1 = primer reintento), `max_attempts: int`, `error_type: str` (nombre de clase canónico), `delay: float` |
| `Retries` | `config.py` | los mismos tres campos con defectos 5 / 2.0 / 30.0; `HarnessConfig.retries: Retries = Retries()` |

**Espera** del reintento *n*: `d = min(base × 2^(n−1), max_delay)`; con pista `h` válida: si `h > max_delay` ⇒ no se reintenta; si no, `max(d, h)`.

**Evento**: `provider_error` con `{reason: "retry", error_type, attempt, max_attempts, delay_seconds}`. Sin texto de error ni datos de la petición.

**Transiciones por llamada**: intento 1 → éxito (devuelve) | error no temporal (propaga) | error temporal → (¿quedan intentos y pista ≤ tope?) sí: notifica, espera, siguiente intento | no: propaga el último error.
