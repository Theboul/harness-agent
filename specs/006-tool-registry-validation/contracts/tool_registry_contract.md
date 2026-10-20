# Contrato: registro de herramientas y validación de argumentos (HU-01-02)

**Plan**: [../plan.md](../plan.md) | **Modelo de datos**: [../data-model.md](../data-model.md) | **Puerto base**: `src/harness_agent/core/interfaces/tool.py` (HU-00-01, sin cambios)

Este documento fija el comportamiento observable de `InMemoryToolRegistry` y del validador de esquema. No redefine el puerto `ToolRegistry`: lo concreta. Sirve de referencia para las pruebas de contrato (`tests/contracts/test_tool_registry_contract.py`) y para quien escriba el bucle (HU-01-01) o las herramientas (HU-01-03 en adelante).

---

## 1. API pública (`harness_agent.core.tools`)

| Símbolo | Tipo | Notas |
|---|---|---|
| `InMemoryToolRegistry` | clase (implementa `ToolRegistry`) | Sin argumentos de constructor |
| `ToolRegistryError` | excepción (hereda de `ValueError`) | Base de todas las siguientes |
| `InvalidToolDefinitionError` | excepción | Atributos: `tool_name`, `problems` |
| `DuplicateToolError` | excepción | Atributo: `tool_name` |
| `UnknownToolError` | excepción | Atributo: `tool_name` |
| `ToolValidationError` | excepción | Atributos: `tool_name`, `violations` |
| `Violation` | dataclass congelada | `path`, `message` |
| `check_schema`, `validate_arguments` | funciones | Validador sin estado; usables sin registro |

Los símbolos principales también se reexportan desde `harness_agent.core`.

---

## 2. Operaciones del registro

### `register(tool: Tool) -> None`

| Aspecto | Comportamiento |
|---|---|
| Precondición | `tool` implementa `Tool` |
| Comprobaciones | Nombre `[A-Za-z0-9_-]{1,64}`; descripción no vacía; `risk` es `RiskLevel`; esquema correcto (sección 4). Se informan **todos** los problemas juntos. Después, nombre no repetido |
| Éxito | La herramienta queda registrada al final del orden; se guarda una copia profunda de su esquema |
| Inmutabilidad | El esquema es inmutable tras registrar: la validación usa siempre la copia guardada, y una herramienta no debe cambiar su `schema` después; si lo hiciera, el cambio no afecta a la validación |
| Errores | `InvalidToolDefinitionError` (definición inválida), `DuplicateToolError` (nombre repetido). Ambos son `ValueError` |
| Garantía | **Atómico**: si lanza, el catálogo queda idéntico al anterior |

### `get(name: str) -> Tool | None`

Devuelve la herramienta registrada con ese nombre exacto o `None` si no existe. Nunca lanza por un nombre desconocido.

### `list() -> list[Tool]`

Devuelve una lista **nueva** en cada llamada, en orden de registro. Modificarla no afecta al catálogo.

### `validate_args(name: str, args: dict[str, Any]) -> dict[str, Any]`

| Aspecto | Comportamiento |
|---|---|
| Entrada | Nombre de una herramienta y los argumentos propuestos por el modelo (en tiempo de ejecución pueden no ser un `dict`; se informa como violación) |
| Éxito | Devuelve una copia superficial de `args`, sin alteraciones (sin coerción de tipos ni valores por defecto) |
| Errores | `UnknownToolError` si el nombre no está registrado; `ToolValidationError` si `args` incumple el esquema registrado. Ambos son `ValueError` |
| Garantías | No ejecuta la herramienta; no modifica `args`; sin red ni disco; determinista (mismos datos, mismo resultado y mismo texto) |

Un `name` que no es texto (llega del JSON del modelo) cuenta como una herramienta desconocida: `validate_args` lanza `UnknownToolError` y `get` devuelve `None`.

---

## 3. Formato de los textos de error (destinatario: el modelo)

Idioma: español. Nunca se reproducen los valores recibidos. Las rutas se recortan a 80 caracteres y los nombres de herramienta a 64.

**`ToolValidationError`** (se muestran como máximo 20 líneas de violación; el resto se resume):

```text
Argumentos inválidos para la herramienta 'leer_archivo':
- ruta: falta el campo requerido.
- limite: se esperaba un entero.
- modo: valor no permitido; valores permitidos: "lectura", "escritura".
- opciones.tiempo_maximo: debe ser mayor o igual que 1.
- extra: campo no declarado en el esquema.
- … y 3 violaciones más.
```

Cuando los argumentos en conjunto no son un objeto, la ruta se muestra como `(argumentos)`:

```text
Argumentos inválidos para la herramienta 'leer_archivo':
- (argumentos): los argumentos deben ser un objeto.
```

**`UnknownToolError`**: `Herramienta desconocida: 'nombre_pedido'.`

**`DuplicateToolError`**: `Ya existe una herramienta registrada con el nombre 'nombre'.`

**`InvalidToolDefinitionError`**:

```text
Definición inválida de la herramienta 'nombre':
- nombre: solo se admiten letras ASCII, dígitos, guion bajo y guion (1 a 64 caracteres).
- descripción: no puede estar vacía.
- riesgo: debe ser un RiskLevel (low, medium o high).
- esquema properties.limite: palabra clave no soportada 'pattern'.
```

Si `name` o `description` no son texto, sus problemas son `nombre: debe ser un texto.` y `descripción: debe ser un texto.`, respectivamente.

Cuando hay más de 20 violaciones, la última línea resume el resto (`- … y 3 violaciones más.`; en singular, `- … y 1 violación más.`).

Valores permitidos de un `enum`: el motivo muestra como máximo los 10 primeros valores del esquema, en su orden, cada uno en JSON y recortado a 40 caracteres contando la `…`. Si hay más, se cierra con `, … y N más` (N = los valores no mostrados) antes del punto final: `valor no permitido; valores permitidos: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, … y 2 más.`.

Orden de las violaciones (determinista): en cada objeto, primero los campos requeridos ausentes (en el orden de `required`), después los campos presentes y declarados (en el orden de `properties`) y por último los campos no declarados (en el orden de los argumentos). Los elementos de una lista se recorren por índice. Dentro de un mismo campo el orden es: tipo, `enum`, restricciones de su clase de valor (límites numéricos, de longitud o de número de elementos) y, al final, lo anidado.

Nombres de tipo en los mensajes: `string` → "cadena de texto", `integer` → "entero", `number` → "número", `boolean` → "booleano", `array` → "lista", `object` → "objeto", `null` → "nulo". Una unión se muestra como "uno de: entero, nulo".

Cuando el tipo esperado es uno solo, el motivo es `se esperaba <tipo>.` con estos textos: `string` → "una cadena de texto", `integer` → "un entero", `number` → "un número", `boolean` → "un booleano", `array` → "una lista", `object` → "un objeto", `null` → "nulo" (por ejemplo, `se esperaba un entero.` y `se esperaba nulo.`). Con una unión es `se esperaba uno de: entero, nulo.`.

---

## 4. Subconjunto soportado de JSON Schema

Raíz obligatoria: `{"type": "object", ...}`. El `type` de la raíz debe ser exactamente la cadena `"object"`: una lista como `["object"]` se rechaza.

| Palabra clave | Aplica a | Efecto |
|---|---|---|
| `type` | cualquier valor | Un nombre o una lista de nombres: `string`, `integer`, `number`, `boolean`, `array`, `object`, `null` |
| `properties` | objetos | Mapa de nombre de campo a subesquema |
| `required` | objetos | Lista de campos obligatorios; todos deben estar en `properties` |
| `additionalProperties` | objetos | Solo booleano. **Si falta, equivale a `false`** (campo no declarado = violación) |
| `enum` | cualquier valor | Lista no vacía de valores permitidos; `true` no equivale a `1` |
| `minimum`, `maximum` | `integer`, `number` | Límites inclusivos |
| `minLength`, `maxLength` | `string` | Longitud en caracteres |
| `items` | `array` | Subesquema único aplicado a cada elemento |
| `minItems`, `maxItems` | `array` | Número de elementos |

Anotaciones inertes aceptadas: `description`, `title`, `default`, `examples`, `$comment`, `$schema`. `default` no se aplica a los argumentos.

**Cualquier otra palabra clave se rechaza al registrar** (`InvalidToolDefinitionError`), entre ellas `$ref`, `$defs`, `anyOf`, `oneOf`, `allOf`, `not`, `pattern`, `format`, `const`, `if`, `then`, `else`. Profundidad máxima de anidamiento: 32.

Todo subesquema (el de un campo de `properties` o el de `items`) debe ser un objeto: los esquemas booleanos `true` y `false` no se admiten.

Un valor que es un objeto se valida como objeto aunque su subesquema no declare `type`: se rechazan los campos no declarados salvo `additionalProperties: true`; quien necesite un objeto libre debe escribir `{"type": "object", "additionalProperties": true}`.

Tipos: `boolean` no es `integer` ni `number`; `integer` admite `3` y `3.0` pero no `"3"` ni `3.5`; `NaN` e infinitos no son válidos para `integer` ni `number`.

---

## 5. Uso previsto por el consumidor (el bucle de HU-01-01)

1. Obtener las definiciones que se muestran al modelo a partir de `registry.list()`: nombre, descripción y esquema de cada `Tool` (en `ToolDefinition.parameters`).
2. Ante una llamada del modelo, ejecutar `registry.validate_args(call.name, call.arguments)`.
3. Si lanza `ToolRegistryError`, **no ejecutar nada** y devolver al modelo un `ToolResult` con `is_error=True` y `str(error)` como contenido. El texto ya es utilizable tal cual.
4. Si no lanza, obtener la herramienta con `registry.get(call.name)` y ejecutar `run` con los argumentos devueltos.
5. Consultar `tool.risk` solo para la política de permisos; el registro no decide ni aplica permisos.

El consumidor nunca nombra una herramienta concreta; añadir una herramienta es solo `register`.

---

## 6. Fuera de este contrato

Ejecución de herramientas y manejo de sus fallos (bucle, HU-01-01); permisos y aprobación (HU-05-xx); eliminación o reemplazo de herramientas; persistencia del catálogo; normalización de nombres externos (MCP, HU-08-03); eventos de validación fallida (dependen del bus de eventos, HU-01-05).
