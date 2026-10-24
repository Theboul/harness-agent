# Contrato: `LiteLLMProvider` (HU-07-02)

Contrato que el adaptador debe cumplir, verificable sin red ni claves. Comparte con `FakeProvider` el contrato del puerto `Provider`; añade las reglas propias del adaptador.

## 1. Contrato compartido con `FakeProvider` (FR-020)

La misma prueba parametrizada (`tests/contracts/test_litellm_provider_contract.py`) corre contra `DummyProvider`, `ScriptedProvider`, `FakeProvider` y `LiteLLMProvider` (con función de llamada falsa):

- es una subclase de `Provider` con la misma firma de `complete(messages, tools=None)` y es `async`;
- un consumidor mínimo (`TestAgentConsumer.execute_turn`) funciona con cualquiera sin cambiar una línea;
- la respuesta es una `ProviderResponse` con `content`, `tool_calls` y `usage`;
- no modifica los `messages` ni las `tools` recibidos;
- falla con tipos de `ProviderError` (el mismo tipo que lanzaría `FakeProvider` para cuota, tiempo y no disponible).

## 2. Construcción

```text
LiteLLMProvider(model, *, max_output_tokens, api_key=None, completion=None)
```

- `model` sin la forma `<proveedor>/<modelo>` → `ValueError` en español, sin el valor.
- `max_output_tokens` no entero, booleano o ≤ 0 → `ValueError`.
- `completion=None` → carga `litellm.acompletion` con `importlib`; si falla el import → `ProviderDependencyError`.
- No lee archivos, entorno ni configuración.

## 3. Petición

| Regla | Prueba |
|---|---|
| `max_tokens == max_output_tokens` en el 100 % de las llamadas, con y sin herramientas | petición capturada |
| `num_retries == 0` | petición capturada |
| `tools` ausente si `tools` es `None` o `[]` | petición capturada |
| `api_key` presente solo con clave; el valor es `reveal()` | petición capturada |
| sin campos extra de LiteLLM (`provider_specific_fields`, `refusal`, …) | `messages` igual a la salida de `to_openai_messages` |
| `is_error` marcado con etiqueta (genérica `[tool_error]` si falta); el original no se modifica | historial antes y después |
| ids opacos: `call_…`, `toolu_…`, `x`, un id de 200 caracteres ida y vuelta | petición capturada |
| historial no representable (`ConversionError`) → `ProviderError`, la función de llamada no se invoca | contador de llamadas |

## 4. Respuesta

| Regla | Prueba |
|---|---|
| texto + dos llamadas → mismo orden, `index` ignorado (empieza en 1 o repetido) | respuestas con `index` raros |
| argumentos JSON objeto → `dict`; en blanco → `{}` | respuestas |
| argumentos ilegibles, lista, número, `null` → `{"arguments_not_valid_json": …}`; el texto va recortado a 200 caracteres | respuestas |
| herramienta con `additionalProperties: true` y argumentos ilegibles → `ProviderError`, ninguna herramienta corre | respuesta + bucle |
| una llamada ilegible entre varias válidas: solo esa lleva el marcador | respuestas |
| sin `usage` → `usage is None`; `usage` con `None` en un contador → 0 | respuestas |
| sin texto ni llamadas, sin `choices`, estructura inválida → `ProviderError` | respuestas |

## 5. Con el bucle real (FR-008, SC-009)

`tests/integration/test_litellm_provider_agent_loop.py` conecta `AgentLoop` + `LiteLLMProvider` (función de llamada falsa) + registro real + herramientas reales de archivos:

- tarea con dos llamadas válidas → resultado final correcto, mismo historial que con `FakeProvider`;
- una llamada con JSON inválido → la herramienta **no** se ejecuta, el modelo recibe `[invalid_arguments]`, el turno siguiente se construye y termina bien;
- un error de la herramienta → el siguiente envío al modelo lleva la etiqueta en el contenido;
- cada error de la tabla → `TurnStatus.PROVIDER_FAILED` y evento `PROVIDER_ERROR` con el tipo canónico y sin la clave centinela.

## 6. Errores y secretos

| Regla | Prueba |
|---|---|
| cada fila de la tabla (`research.md` §1) → tipo canónico exacto, causa en `__cause__` | una prueba por fila |
| excepción desconocida → `ProviderError` genérico | prueba |
| `ImportError` durante la llamada → `ProviderError` con el comando de instalación | prueba |
| `CancelledError` y `KeyboardInterrupt` se propagan sin traducir | prueba |
| clave centinela dentro del mensaje original, o en el nombre de la clase de la excepción → ausente en `str`, `repr`, `args` y atributos de texto del error canónico (reemplazada por `<secreto oculto>`); `str(__cause__)` conserva el original | prueba |
| clave centinela dentro de los argumentos ilegibles → el marcador `arguments_not_valid_json` la lleva reemplazada | prueba |
| clave centinela ausente en el evento `PROVIDER_ERROR`, en el texto del resultado del turno y en el historial que ve el modelo (bucle real) | integración |
| clave centinela ausente en `repr`/`str`/`format` del adaptador y de la configuración | prueba |

## 7. Fronteras (`tests/architecture/test_providers_boundaries.py`)

- `litellm` (y `openai`, `anthropic`, `google`) **no** aparece como `import` en ningún archivo de `src/harness_agent/`, tampoco dentro de `adapters/providers/` a nivel de módulo.
- `importlib.import_module("litellm")` aparece solo dentro de una función de `adapters/providers/`; en cualquier otra carpeta de `src/` es una violación.
- `adapters/providers/` importa solo biblioteca estándar, la API pública del núcleo (`harness_agent.core`), `harness_agent.adapters.converters` y su propio paquete; no lee configuración ni entorno, no usa la terminal, no importa otro adaptador.
- Ningún literal de texto (sin contar docstrings) de `adapters/providers/` contiene el nombre de un proveedor de `PROVIDER_KEY_VARIABLES`. Los identificadores como `to_openai_messages` no cuentan: es el nombre del formato común que usan los convertidores.
- Autopruebas sobre fragmentos sintéticos y una mutación sobre una copia del paquete real (como `test_adapters_boundaries.py`).
