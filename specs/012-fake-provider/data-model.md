# Data Model: HU-00-03 — Proveedor simulado para pruebas

No hay persistencia. Todo vive en memoria durante una prueba.

## Producción (`core/interfaces/provider.py`)

| Tipo | Base | Significado | Atributos |
|---|---|---|---|
| `ProviderError` | `Exception` | Base de los errores de proveedor del núcleo | mensaje (heredado) |
| `QuotaExceeded` | `ProviderError` | Cuota o crédito agotado | — |
| `ProviderTimeout` | `ProviderError` | Tiempo agotado | — |
| `ProviderUnavailable` | `ProviderError` | Servicio no disponible | — |

Reglas: sin atributos propios ni importaciones nuevas; los cuatro se reexportan desde `harness_agent.core.interfaces` y `harness_agent.core`. Los adaptadores reales los lanzarán tras traducir sus errores (HU-07-02).

## Prueba (`tests/doubles/fake_provider.py`)

### `FakeProvider(Provider)`

| Elemento | Tipo | Descripción |
|---|---|---|
| `script` (constructor) | `Sequence[ProviderResponse \| ProviderError]` | Pasos en orden; se copia en profundidad |
| `received` | `list[list[Message]]` | Copia de los mensajes recibidos en cada llamada |
| `received_tools` | `list[list[ToolDefinition] \| None]` | Copia de las herramientas de cada llamada |
| `call_count` | `int` | Llamadas hechas |
| `exhausted` | `bool` | `True` tras pedir un paso que no existe |

### Validación al construir

| Regla | Error |
|---|---|
| Guion vacío | `ValueError` |
| Paso que no es `ProviderResponse` ni `ProviderError` | `ValueError` (el mensaje incluye el índice del paso) |
| Id de llamada a herramienta vacío o repetido en todo el guion | `ValueError` |

### Transiciones por llamada

```
llamada i (0-based):
  registra copia de messages y tools; call_count += 1
  i >= len(script)        -> exhausted = True; lanza ScriptExhausted
  script[i] es ProviderError -> lanza una copia del error
  script[i] es ProviderResponse -> devuelve una copia
```

No hay estados adicionales ni reinicio: un `FakeProvider` agotado se descarta y se crea otro.
