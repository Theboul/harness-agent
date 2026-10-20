# Data Model: HU-01-02 — Registro de herramientas con esquema y validación

**Fecha**: 2026-10-18 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md) | **Decisiones**: [research.md](research.md)

Los tipos del puerto (`Tool`, `ToolRegistry`, `RiskLevel`) y las entidades canónicas (`ToolCall`, `ToolResult`) **ya existen** desde HU-00-01 y no se modifican. Aquí se describe solo lo que añade esta historia. Los nombres están en inglés (decisión del 2026-10-17 para métodos y atributos); los textos para el modelo, en español.

---

## Entidades existentes que esta historia usa (sin cambios)

| Tipo | Ubicación | Uso en esta historia |
|---|---|---|
| `Tool` | `core/interfaces/tool.py` | Lo que se registra: expone `name`, `description`, `schema`, `risk` y `run(args)`. |
| `ToolRegistry` | `core/interfaces/tool.py` | Puerto que implementa `InMemoryToolRegistry`: `register`, `get`, `list`, `validate_args`. |
| `RiskLevel` | `core/interfaces/tool.py` | Enumeración `LOW`, `MEDIUM`, `HIGH` que toda herramienta debe declarar. |
| `ToolCall`, `ToolResult` | `core/entities.py` | Los usa el consumidor de prueba que imita al bucle; el registro no los toca. |
| `ToolDefinition` | `core/interfaces/provider.py` | Lo que el consumidor presenta al modelo (`name`, `description`, `parameters`); se arma a partir de `Tool`. |

---

## Entidades nuevas

### `Violation` (`core/tools/errors.py`)

Un incumplimiento concreto del esquema. Inmutable (`@dataclass(frozen=True)`).

| Campo | Tipo | Descripción |
|---|---|---|
| `path` | `str` | Ruta del campo desde la raíz de los argumentos. Cadena vacía = la raíz (los argumentos en conjunto). Los campos anidados se separan con punto (`opciones.tiempo_maximo`) y los elementos de listas llevan índice (`archivos[2].ruta`). |
| `message` | `str` | Motivo en español: frase completa que termina en punto (lo garantiza el validador; el texto del error lo imprime tal cual y no añade nada), sin los valores recibidos (por ejemplo, `se esperaba un entero.`). |

### `ToolRegistryError(ValueError)` (`core/tools/errors.py`)

Base común. Heredar de `ValueError` es lo que permite cumplir el contrato del puerto sin modificarlo.

| Subclase | Se lanza cuando | Atributos |
|---|---|---|
| `InvalidToolDefinitionError` | `register` detecta nombre, descripción, riesgo o esquema inválidos | `tool_name: str`, `problems: tuple[str, ...]` (todos los problemas encontrados, ya redactados) |
| `DuplicateToolError` | `register` recibe un nombre ya registrado | `tool_name: str` |
| `UnknownToolError` | `validate_args` recibe el nombre de una herramienta no registrada | `tool_name: str` |
| `ToolValidationError` | `validate_args` detecta que los argumentos incumplen el esquema | `tool_name: str`, `violations: tuple[Violation, ...]` (todas) |

`str(error)` produce el texto final para el modelo (formato en [contracts/tool_registry_contract.md](contracts/tool_registry_contract.md)).

### `InMemoryToolRegistry` (`core/tools/registry.py`)

Implementa `ToolRegistry`. Sin argumentos de constructor.

| Elemento | Tipo | Descripción |
|---|---|---|
| `_entries` | `dict[str, _Entry]` | Catálogo por nombre. El orden de inserción define el orden de `list()`. |
| `_Entry` (interna, congelada) | `tool: Tool`, `schema: dict[str, Any]` | La herramienta y una **copia profunda** de su esquema tomada al registrar. |

Estados y transiciones: el catálogo solo crece (`register` añade; no hay eliminación ni reemplazo). Un registro rechazado no cambia el estado.

### Funciones de `core/tools/schema_validator.py`

| Función | Firma | Descripción |
|---|---|---|
| `check_schema` | `(schema: object) -> list[str]` | Devuelve los problemas de un esquema de definición (lista vacía si es correcto). Cada problema indica el lugar dentro del esquema (por ejemplo `properties.limite.minimum`). |
| `validate_arguments` | `(schema: dict[str, Any], args: object) -> list[Violation]` | Devuelve todas las violaciones de los argumentos respecto de un esquema ya comprobado (lista vacía si cumplen). No modifica `args`. |

### Constantes (`core/tools/errors.py` y `core/tools/schema_validator.py`)

`MAX_NAME_LENGTH`, `MAX_RENDERED_VIOLATIONS` y `MAX_PATH_DISPLAY` viven en `errors.py`, porque las usan los textos de error y así `schema_validator.py` y `registry.py` pueden importarlas sin ciclos. `MAX_SCHEMA_DEPTH` vive en `schema_validator.py`.

| Constante | Valor | Uso |
|---|---|---|
| `MAX_NAME_LENGTH` | 64 | Longitud máxima del nombre de herramienta (aclaración 2 del spec). |
| `MAX_SCHEMA_DEPTH` | 32 | Profundidad máxima de anidamiento del esquema; también corta esquemas circulares. |
| `MAX_RENDERED_VIOLATIONS` | 20 | Violaciones que muestra el texto del error. |
| `MAX_PATH_DISPLAY` | 80 | Caracteres máximos de una ruta de campo en el texto. |

---

## Reglas de validación

### De la definición de una herramienta (al registrar)

| # | Regla | Requisito |
|---|---|---|
| D-1 | `name` coincide por completo con `[A-Za-z0-9_-]{1,64}` | FR-002 y aclaración 2 |
| D-2 | `description` no está vacía tras recortar espacios | FR-002 |
| D-3 | `risk` es una instancia de `RiskLevel` | FR-002, regla de negocio 2 |
| D-4 | `schema` pasa `check_schema` (ver siguiente tabla) | FR-003 |
| D-5 | El nombre no existe ya en el catálogo | FR-004 |
| D-6 | Se informan todos los problemas D-1 a D-4 juntos; D-5 se comprueba después | R-08 |

### Del esquema (`check_schema`)

| # | Regla |
|---|---|
| S-1 | El esquema es un `dict` y su `type` raíz es `"object"` |
| S-2 | Solo aparecen palabras clave soportadas o anotaciones inertes (lista en el contrato); cualquier otra se rechaza nombrándola |
| S-3 | `type` es un nombre válido o una lista no vacía de nombres válidos sin repetir |
| S-4 | `properties` es un `dict` de nombre a subesquema válido |
| S-5 | `required` es una lista de cadenas sin repetir y cada una está declarada en `properties` |
| S-6 | `additionalProperties`, si aparece, es un booleano |
| S-7 | `enum` es una lista no vacía |
| S-8 | `minimum` y `maximum` son números finitos (no booleanos) y `minimum <= maximum`; `minLength`, `maxLength`, `minItems` y `maxItems` son enteros no negativos (no booleanos) y cada mínimo es menor o igual que su máximo |
| S-9 | `items`, si aparece, es un subesquema válido (la forma de lista de esquemas no está soportada) |
| S-10 | La profundidad no supera `MAX_SCHEMA_DEPTH` |

### De los argumentos (`validate_arguments`)

| # | Regla | Mensaje (resumen) |
|---|---|---|
| A-1 | Los argumentos son un `dict` | "los argumentos deben ser un objeto." |
| A-2 | Cada campo de `required` está presente | "falta el campo requerido." |
| A-3 | Cada campo presente cumple su `type` (con R-05) | "se esperaba <tipo>." |
| A-4 | Un campo no declarado se rechaza salvo `additionalProperties: true` | "campo no declarado en el esquema." |
| A-5 | `enum`: el valor debe ser uno de los permitidos | "valor no permitido; valores permitidos: <valores>." (`<valores>`: los 10 primeros del esquema, en su orden, cada uno en JSON y recortado a 40 caracteres contando la `…`; si hay más, se cierra con `, … y N más`, con N = los no mostrados) |
| A-6 | `minimum` / `maximum` en números | "debe ser mayor o igual que N." / "debe ser menor o igual que N." |
| A-7 | `minLength` / `maxLength` en cadenas | "debe tener al menos N caracteres." / "debe tener como máximo N caracteres." (en singular para 1: "debe tener al menos 1 carácter.") |
| A-8 | `minItems` / `maxItems` en listas | "debe tener al menos N elementos." / "debe tener como máximo N elementos." (en singular para 1: "debe tener al menos 1 elemento.") |
| A-9 | Se descienden `properties` e `items` de forma recursiva | la ruta incluye el camino completo |
| A-10 | Si el tipo es incorrecto en un nivel, no se evalúan las demás restricciones de ese campo | evita violaciones duplicadas |

---

## Relaciones

```
Tool (puerto) ──registrada en──▶ InMemoryToolRegistry ──implementa──▶ ToolRegistry (puerto)
                                        │
                                        ├─ usa ─▶ check_schema        (al registrar)
                                        └─ usa ─▶ validate_arguments  (al validar una llamada)
                                                         │
                                                         └─ produce ─▶ Violation* ─▶ ToolValidationError
```

El consumidor (el bucle de HU-01-01 en el futuro) solo conoce `Tool` y `ToolRegistry`; las excepciones `ToolRegistryError` son lo único de `core/tools/` que necesita para convertir un rechazo en un `ToolResult` con `is_error=True`.
