# Contract Specification: Conversión de Mensajes y Adaptación de Proveedores

**Feature**: `specs/004-provider-interface-message-format/spec.md`  
**Status**: Draft Contract  
**Date**: 2026-10-18  
**Responsable**: A — Núcleo  

---

## 1. Protocolo de Conversión de Proveedor

Todo conversor de dialecto de proveedor implementa la siguiente especificación abstracta en la capa de adaptadores (`src/harness_agent/adapters/converters/`):

```python
from typing import Any, Protocol
from harness_agent.core.entities import Message
from harness_agent.core.interfaces.provider import ProviderResponse, ToolDefinition


class ProviderMessageConverter(Protocol):
    """Protocolo contractual para adaptadores de formato de proveedores."""

    def to_provider_payload(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> dict[str, Any]:
        """Convierte mensajes y herramientas canónicas al payload esperado por la API."""
        ...

    def to_canonical_response(
        self,
        raw_response: dict[str, Any],
    ) -> ProviderResponse:
        """Convierte la respuesta cruda devuelta por la API al ProviderResponse canónico."""
        ...
```

---

## 2. Especificación de Mapeo: Dialecto OpenAI (Chat Completions v1)

### 2.1 Mapeo de Mensajes (`to_openai_messages`)
1. **Mensaje de Sistema**:
   - Canónico: `Message(role=Role.SYSTEM, content="Directivas")`
   - OpenAI: `{"role": "system", "content": "Directivas"}`
2. **Mensaje de Usuario**:
   - Canónico: `Message(role=Role.USER, content="Pregunta")`
   - OpenAI: `{"role": "user", "content": "Pregunta"}`
3. **Mensaje de Asistente con Llamadas a Herramientas**:
   - Canónico: `Message(role=Role.ASSISTANT, content="Ejecutando...", tool_calls=(ToolCall(id="call_abc", name="shell", arguments={"cmd": "ls"}),))`
   - OpenAI:
     ```json
     {
       "role": "assistant",
       "content": "Ejecutando...",
       "tool_calls": [
         {
           "id": "call_abc",
           "type": "function",
           "function": {
             "name": "shell",
             "arguments": "{\"cmd\": \"ls\"}"
           }
         }
       ]
     }
     ```
4. **Mensaje de Resultado de Herramienta**:
   - Canónico: `Message(role=Role.TOOL, tool_result=ToolResult(call_id="call_abc", content="salida.txt", is_error=False))`
   - OpenAI: `{"role": "tool", "tool_call_id": "call_abc", "content": "salida.txt"}`

### 2.2 Mapeo de Declaración de Herramientas (`to_openai_tools`)
- Canónico: `ToolDefinition(name="shell", description="Ejecuta comando", parameters={"type": "object", "properties": {"cmd": {"type": "string"}}})`
- OpenAI:
  ```json
  {
    "type": "function",
    "function": {
      "name": "shell",
      "description": "Ejecuta comando",
      "parameters": {
        "type": "object",
        "properties": {
          "cmd": { "type": "string" }
        }
      }
    }
  }
  ```

### 2.3 Mapeo de Respuesta (`from_openai_response`)
- Parsea `choices[0].message`:
  - `content`: `str` (o `""` si es `None`).
  - `tool_calls`: parsea cada llamada deserializando `function.arguments` mediante `json.loads` a `dict[str, Any]`.
- Parsea `usage`:
  - `TokenUsage(input_tokens=usage["prompt_tokens"], output_tokens=usage["completion_tokens"])`.

---

## 3. Especificación de Mapeo: Dialecto Anthropic (Messages v1)

### 3.1 Mapeo de Mensajes y Sistema (`to_anthropic_payload`)
1. **Extracción de Sistema**:
   - Mensajes con `Role.SYSTEM` no se agregan a la lista `messages`. Solo se admiten al inicio de la conversación: uno solo se asigna como cadena al parámetro superior `system`; varios se asignan como lista de bloques `{"type": "text", "text": ...}` conservando orden y límites (no se concatenan). Un `system` posterior a cualquier mensaje `user`, `assistant` o `tool` es una secuencia canónica inválida (decisión del Product Owner, 2026-10-18) y produce `ConversionError` en ambos proveedores; un `system` vacío también produce `ConversionError` en Anthropic. *(Actualizado 2026-10-18; antes se concatenaban.)*
2. **Mensaje de Asistente con Herramientas**:
   - `Message(role=Role.ASSISTANT, content="Texto", tool_calls=(ToolCall(id="toolu_1", name="leer", arguments={"ruta": "a.txt"}),))`
   - Anthropic:
     ```json
     {
       "role": "assistant",
       "content": [
         { "type": "text", "text": "Texto" },
         { "type": "tool_use", "id": "toolu_1", "name": "leer", "input": { "ruta": "a.txt" } }
       ]
     }
     ```
3. **Resultado de Herramienta**:
   - En Anthropic, los resultados viajan como bloques `tool_result` dentro de un mensaje con `role: "user"`:
     ```json
     {
       "role": "user",
       "content": [
         {
           "type": "tool_result",
           "tool_use_id": "toolu_1",
           "content": "contenido de a.txt",
           "is_error": false
         }
       ]
     }
     ```

### 3.2 Mapeo de Herramientas (`to_anthropic_tools`)
- Canónico: `ToolDefinition(name="leer", description="Lee archivo", parameters={"type": "object", ...})`
- Anthropic:
  ```json
  {
    "name": "leer",
    "description": "Lee archivo",
    "input_schema": { "type": "object", "..." : "..." }
  }
  ```

---

## 4. Invariante de Conversión Sin Pérdida (Round-Trip)

Para cualquier mensaje canónico $M$ y herramienta $T$, se cumple:
$$\text{from\_provider}(\text{to\_provider}(M)) \equiv M$$
$$\text{from\_provider\_tool}(\text{to\_provider\_tool}(T)) \equiv T$$

En caso de argumentos no representables o JSON malformado devuelto por la API externa, la función lanza obligatoriamente `ConversionError` (subclase de `ValueError`) garantizando la política de falla cerrada.

> **Vía de restauración exacta (2026-10-18):** el invariante rige, para todo el dominio de entradas canónicas válidas, a través de `to_openai_envelope` / `to_anthropic_envelope` (o `to_provider_envelope` de cada conversor) y `restore_messages(envelope)`: `is_external`, `is_error`, `usage` por mensaje y el `content` de un mensaje `tool` se guardan en un sidecar local y nunca se escriben en el payload (diseño D-02, pendiente de aprobación técnica individual). Las funciones `from_openai_messages` y `from_anthropic_payload` interpretan un payload suelto, **no** pueden recuperar esos atributos y están obsoletas (`DeprecationWarning`). `from_*_response` y `to_canonical_response` no reciben envelope.
>
> **Política de correlación del envelope:** ids de `ToolCall` vacíos o duplicados, `call_id` vacío o repetido y un resultado anterior a su llamada se rechazan siempre; un resultado cuya llamada no está en la ventana se rechaza salvo `partial_window=True`. Un `SYSTEM` vacío se omite del payload de Anthropic y se conserva en el sidecar.

### Reglas de falla cerrada (actualizadas 2026-10-18)

1. Argumentos de herramientas: deben ser un objeto JSON; listas, escalares, `null` y otros tipos se rechazan. Los argumentos no serializables a JSON estricto se rechazan al enviar.
2. `ToolResult.content` y `Message.content` son `str`; una lista de bloques `text` se une con salto de línea; cualquier otro contenido se rechaza (`None` se trata como texto vacío cuando el proveedor omite el campo).
3. Anthropic (solicitud): un mensaje con `tool_result` no puede mezclarse con otros bloques; los bloques desconocidos, los roles distintos de `user`/`assistant`, los bloques incompletos y las listas vacías se rechazan.
4. Todo error por un payload externo inválido (estructura, tipos, campos obligatorios ausentes, `usage` no entero o negativo) se reporta como `ConversionError`; los errores de programación no se capturan.
