# Contrato: errores de proveedor y `FakeProvider`

## 1. Errores canónicos (`harness_agent.core`)

```python
class ProviderError(Exception): ...
class QuotaExceeded(ProviderError): ...
class ProviderTimeout(ProviderError): ...
class ProviderUnavailable(ProviderError): ...
```

- Importables con `from harness_agent.core import ProviderError, QuotaExceeded, ProviderTimeout, ProviderUnavailable`.
- `issubclass(QuotaExceeded, ProviderError)` es verdadero para los tres.
- Sin atributos propios; el mensaje es el argumento de la excepción.
- Un adaptador real DEBE lanzar estos tipos (no los de su biblioteca) hacia el núcleo.

## 2. `FakeProvider`

```python
from tests.doubles import FakeProvider
from harness_agent.core import ProviderResponse, QuotaExceeded, ToolCall

provider = FakeProvider(
    [
        ProviderResponse(tool_calls=[ToolCall(id="c1", name="echo", arguments={"x": 1})]),
        QuotaExceeded("cuota agotada"),
        ProviderResponse(content="listo"),
    ]
)
```

| Aspecto | Contrato |
|---|---|
| Herencia | `FakeProvider(Provider)`; `complete(messages, tools=None)` asíncrona, misma firma |
| Orden | La llamada i consume el paso i |
| Respuesta | Devuelve una copia profunda del paso |
| Fallo | Lanza una copia del `ProviderError` del paso, sin esperar |
| Guion agotado | Lanza `ScriptExhausted` y deja `exhausted = True` |
| Construcción | Rechaza guion vacío, pasos de otro tipo e ids de llamada vacíos o repetidos |
| Aislamiento | Copia del guion al construir; sin estado compartido entre instancias |
| Registro | `received`, `received_tools`, `call_count`, `exhausted` |
| Red / tiempo / azar | Ninguno |

## 3. Cómo lo ve el bucle (sin cambios en el bucle)

Con un paso `QuotaExceeded("…")`:

- el turno termina con `TurnStatus.PROVIDER_FAILED`;
- se publica `PROVIDER_ERROR` con `payload["error_type"] == "QuotaExceeded"` y `payload["reason"] == "provider_exception"`.

## 4. Qué doble usar

| Necesito… | Uso |
|---|---|
| Una respuesta fija, sin más | `DummyProvider` |
| Excepciones arbitrarias, bloquear una llamada, o ids repetidos a propósito | `ScriptedProvider` |
| Reproducir un guion y simular cuota, tiempo agotado o indisponibilidad con los tipos canónicos | `FakeProvider` |
