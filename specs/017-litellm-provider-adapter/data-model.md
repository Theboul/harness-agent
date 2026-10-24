# Modelo de datos: HU-07-02 — Adaptador LiteLLM

No hay almacenamiento ni entidades nuevas del dominio: `Message`, `ToolCall`, `ToolResult`, `TokenUsage`, `ProviderResponse`, `ToolDefinition` y la jerarquía `ProviderError` **no cambian**. Lo nuevo son tres piezas del adaptador y dos ampliaciones de configuración.

## `LiteLLMProvider` (`adapters/providers/litellm_provider.py`)

Implementa `Provider`. Estado inmutable tras construirse.

| Atributo | Tipo | Origen | Regla |
|---|---|---|---|
| `model` | `str` | `HarnessConfig.model` | forma `<proveedor>/<modelo>`, ambos no vacíos; si no, `ValueError` en español (sin reproducir el valor). Se pasa tal cual a LiteLLM |
| `max_output_tokens` | `int` | `HarnessConfig.limits.max_output_tokens` | entero > 0, no booleano; se envía **siempre** como `max_tokens` |
| `api_key` | objeto con `reveal() -> str`, o `None` | `HarnessConfig.api_key` (`Secret`) | `None` si el proveedor no necesita clave; solo se revela al armar la llamada |
| `completion` | `Callable[..., Awaitable[Any]]` | inyectable; por defecto `litellm.acompletion` cargado al construir | si falta `litellm`, `ProviderDependencyError` con el comando de instalación |

`repr`: `LiteLLMProvider(model='…', max_output_tokens=…, api_key=<oculta>)`; nunca la clave, ni su longitud.

**Depuración de la clave**: toda cadena que el adaptador construye (mensajes de error, nombre de la clase de la excepción, texto recortado del marcador de argumentos ilegibles) pasa por una función que reemplaza el valor de la clave por `<secreto oculto>` **antes** de armar el error o el marcador. La excepción original no se modifica y queda en `__cause__`.

## Petición (qué se envía a la función de llamada)

| Campo | Valor |
|---|---|
| `model` | `self.model` |
| `messages` | `to_openai_messages(prepared)`; `prepared` = historial canónico con los resultados de herramienta con `is_error` marcados en el contenido (ver abajo). El original no se modifica |
| `tools` | `to_openai_tools(tools)`; el campo se omite si `tools` es `None` o vacío |
| `max_tokens` | `self.max_output_tokens` |
| `num_retries` | `0` |
| `api_key` | `self.api_key.reveal()`, solo si hay clave |

No se envía `tool_choice`, `stream`, `api_base` ni nada de las respuestas anteriores de LiteLLM.

**Marca de error de herramienta.** Para cada mensaje `TOOL` cuyo `tool_result.is_error` es verdadero: si el contenido, sin espacios iniciales, ya empieza por una etiqueta `[nombre]` con la forma `[a-z_]+` se deja igual; si no, se antepone `[tool_error] `. `is_error` falso no se toca. Los ids se copian sin validar prefijo ni longitud.

## Respuesta (qué se devuelve)

| Entrada (forma OpenAI de LiteLLM) | Salida (`ProviderResponse`) |
|---|---|
| `choices[0].message.content` (`None` → `""`) | `content` |
| `choices[0].message.tool_calls[i]` en el orden de la lista | `tool_calls[i]` = `ToolCall(id, name, arguments)`; `index` ignorado; id opaco |
| `function.arguments` JSON objeto o cadena en blanco | `arguments` (en blanco → `{}`) |
| `function.arguments` ilegible o que no es un objeto | `{"arguments_not_valid_json": <texto recortado a 200 caracteres>}` (ver `research.md` §3) |
| `usage.prompt_tokens` / `completion_tokens` | `TokenUsage(input_tokens, output_tokens)`; sin `usage` → `None` |

Sin texto y sin llamadas, sin `choices`, estructura inválida (`ConversionError`) → `ProviderError`.

## Tabla de correspondencia de errores

Definida en `research.md` §1 (se implementa como constante inmutable en el módulo y se recorre por el MRO de la excepción). Tipos de salida: `ProviderTimeout`, `QuotaExceeded`, `ProviderUnavailable`, `ProviderError`.

## `ProviderDependencyError` (mismo módulo)

`Exception` propia del adaptador, no es un `ProviderError`: es un fallo de construcción, no de llamada. Texto en español con el comando `pip install -e ".[litellm]"` y el aviso de ruta corta en Windows. No es contrato del núcleo.

## Ampliaciones de `config.py`

Detalle en `contracts/config_additions_contract.md`: `PROVIDER_KEY_VARIABLES` (+`gemini`, `groq`, `openrouter`, `ollama`) y `Limits.max_output_tokens = 4096`.

## Transiciones de estado

Ninguna. El adaptador no guarda estado entre llamadas: cada `complete` es independiente.
