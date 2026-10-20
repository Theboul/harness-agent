# Research: HU-01-02 — Registro de herramientas con esquema y validación

**Fecha**: 2026-10-18 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

El Technical Context no tiene marcadores `NEEDS CLARIFICATION`: las directrices del usuario fijan el lenguaje, la dependencia (solo biblioteca estándar), la forma del registro, el validador y las pruebas. Este documento recoge las decisiones de diseño que quedaban abiertas, cada una con su justificación y las alternativas descartadas.

---

## R-01 — Dónde vive el registro concreto

- **Decision**: `InMemoryToolRegistry` y el validador de esquema van en `src/harness_agent/core/tools/`. No son un adaptador. El puerto sigue en `core/interfaces/tool.py` sin cambios.
- **Rationale**: la skill `estructura-carpetas-harness` da un criterio de desempate: "si cambiaría al cambiar de proveedor, base de datos o interfaz, es adaptador". Un catálogo en memoria con validación pura no cambia con ninguno de los tres, no toca red ni disco y es una regla de negocio (el árbol acordado ya prevé `core/tools/` para "Tool, ToolRegistry, validación de esquema"). La skill `arquitectura-hexagonal-clean` pide un puerto solo para lo externo, y aquí no hay nada externo.
- **Alternatives considered**:
  - *`adapters/tools/registry.py`*: rechazada. Los adaptadores contienen implementaciones de lo externo; ubicar aquí una regla de negocio es un antipatrón de la skill, y el bucle del núcleo acabaría dependiendo de un adaptador.
  - *Poner la implementación en `core/interfaces/tool.py`*: rechazada por la instrucción explícita de no modificar los puertos.

## R-02 — Validador de esquema propio, subconjunto mínimo de JSON Schema

- **Decision**: escribir un validador propio en `core/tools/schema_validator.py` con dos funciones puras: `check_schema(schema)` (valida la definición al registrar) y `validate_arguments(schema, args)` (valida cada llamada).
- **Rationale**: lo exigen la directriz del usuario y el Principio III (núcleo sin librerías externas). Además, los mensajes tienen un destinatario particular, el modelo, y una librería genérica no cumpliría FR-008 (texto en español, sin reproducir valores recibidos, con rutas de campo uniformes) sin una capa de traducción que acabaría pesando más que el propio validador.
- **Alternatives considered**:
  - *`jsonschema` dentro de `core/`*: rechazada, es una dependencia de terceros en el núcleo.
  - *`jsonschema` en un adaptador detrás de un puerto nuevo*: rechazada, exigiría un puerto nuevo (prohibido tocar los puertos) y los errores de la librería incluyen los valores recibidos.
  - *Validar solo tipos y campos requeridos*: rechazada, el spec pide enumeraciones, límites y estructuras anidadas.

## R-03 — Qué subconjunto se soporta y qué hace el resto

- **Decision**: soportar estas palabras clave de validación: `type`, `properties`, `required`, `additionalProperties`, `enum`, `minimum`, `maximum`, `minLength`, `maxLength`, `items`, `minItems`, `maxItems`. Aceptar como anotaciones inertes: `description`, `title`, `default`, `examples`, `$comment`, `$schema`. **Cualquier otra palabra clave** (`$ref`, `$defs`, `anyOf`, `oneOf`, `allOf`, `not`, `pattern`, `format`, `const`, `if`…) se **rechaza al registrar** con un mensaje que la nombra y dice dónde está.
- **Rationale**: ignorar en silencio una restricción (por ejemplo `pattern`) deja al autor de la herramienta creyendo que algo se valida cuando no es así. Es lo contrario de la falla cerrada que exige la constitución. Rechazar también cubre el caso del spec de esquemas con referencias externas, y evita cualquier acceso a red o disco al validar (FR-012).
- **Alternatives considered**:
  - *Ignorar palabras clave desconocidas (comportamiento por defecto de JSON Schema)*: rechazada por la razón anterior.
  - *Soportar `$ref` interno, `anyOf` y `pattern` ya*: rechazada por alcance; el spec habla de "tipos básicos, campos requeridos, valores enumerados, límites y estructuras anidadas". Se deja como ampliación (una entrada nueva en la tabla de manejadores) cuando HU-08-03 la necesite.

## R-04 — Forma del esquema raíz y uniones de tipo

- **Decision**: el esquema raíz debe ser un objeto con `type: "object"`. `type` puede ser un nombre (`"string"`) o una lista de nombres sin repetir (`["string", "null"]`). Los nombres válidos son `string`, `integer`, `number`, `boolean`, `array`, `object` y `null`.
- **Rationale**: los argumentos de una llamada son siempre un objeto (Assumptions del spec) y los proveedores de modelos exigen un objeto en la raíz. Las uniones con `null` son la forma habitual de declarar un argumento opcional anulable, por lo que soportarlas cuesta poco y evita rechazar esquemas razonables.
- **Alternatives considered**: permitir cualquier raíz (rechazada: el fallo aparecería al enviar el turno al proveedor, que es exactamente lo que la aclaración 2 quiso evitar con los nombres); no soportar listas de tipos (rechazada: obligaría a escribir esquemas poco naturales).

## R-05 — Semántica de tipos, sin coerción

- **Decision**:
  - `boolean` no cuenta como `integer` ni `number` (en Python `bool` es subclase de `int`; hay que excluirlo explícitamente).
  - `integer` acepta un `int` o un `float` de valor entero (`3.0`), siguiendo JSON Schema; rechaza `"3"`, `true` y `3.5`.
  - `number` acepta `int` y `float` finitos. `NaN` e infinitos se rechazan como inválidos para `integer` y `number`, porque `json.loads` los acepta y cualquier comparación con `NaN` es falsa, lo que dejaría pasar `minimum` y `maximum`.
  - Los argumentos se entregan tal cual: ningún tipo se convierte (FR-011).
  - En `enum`, la igualdad distingue booleanos de números (`true` no es igual a `1`).
- **Rationale**: son los errores clásicos de un validador manual en Python y cada uno abre una vía a argumentos que el esquema debía excluir. Cada caso tendrá su prueba.
- **Alternatives considered**: coerción de `"42"` a entero (rechazada: contradice FR-011 y oculta errores del modelo); rechazar `3.0` en `integer` (rechazada: se aparta de JSON Schema sin ganancia real).

## R-06 — Campos no declarados

- **Decision**: si el esquema no incluye `additionalProperties`, equivale a `false`: todo campo no declarado es una violación. Solo `additionalProperties: true` explícito los permite. Un `additionalProperties` con valor de esquema (no booleano) no está soportado y se rechaza al registrar (R-03).
- **Rationale**: es la respuesta A de la aclaración 1 del spec (falla cerrada, mantiene FR-011). Se aplica en todos los niveles de anidamiento. Un valor que es un objeto se valida como objeto aunque su subesquema no declare `type`: se rechazan los campos no declarados salvo `additionalProperties: true`, y quien necesite un objeto libre debe escribir `{"type": "object", "additionalProperties": true}`.
- **Alternatives considered**: las opciones B (aceptar) y C (descartar el campo) de la aclaración, ya descartadas por el usuario.

## R-07 — Errores de dominio y formato del mensaje para el modelo

- **Decision**: jerarquía local en `core/tools/errors.py`, todas heredando de `ValueError` a través de una base `ToolRegistryError`:
  `InvalidToolDefinitionError`, `DuplicateToolError`, `UnknownToolError` y `ToolValidationError` (esta última lleva una tupla de `Violation(path, message)`). El mensaje (`str(error)`) está en español, nombra cada campo con su ruta (`opciones.tiempo_maximo`, `archivos[2].ruta`), da el motivo y la expectativa (tipo, valores permitidos, límites), y **no incluye los valores recibidos**. Se muestran como máximo 20 violaciones; si hay más se añade "y N más" (el error conserva todas). Las rutas y los nombres de herramienta citados se recortan a 80 y 64 caracteres.
- **Rationale**:
  - Heredar de `ValueError` cumple lo que el puerto ya declara ("Raises ValueError") sin modificarlo; el bucle puede capturar `ToolRegistryError` para obtener el texto o las violaciones estructuradas.
  - Dejar los errores en `core/tools/` evita crear el `core/errors.py` compartido del árbol, que aún no existe y es del área A; pasar a ese archivo más adelante es un movimiento mecánico.
  - No reproducir valores evita filtrar secretos al contexto y a las trazas (V-13).
  - El tope y los recortes protegen la ventana de contexto frente a entradas patológicas (una lista de miles de elementos inválidos o un nombre de campo enorme).
- **Alternatives considered**: devolver un objeto resultado en lugar de lanzar (rechazada: el puerto `validate_args` ya está definido para lanzar); un único `ValueError` con texto (rechazada: el bucle no podría distinguir los casos ni leer las violaciones); sin tope (ver "Puntos a revisar" del plan).

## R-08 — Qué se valida al registrar y cómo se protege el catálogo

- **Decision**: `register` lee una sola vez `name`, `description`, `risk` y `schema` de la herramienta y comprueba, acumulando **todos** los problemas antes de lanzar: nombre con el formato `[A-Za-z0-9_-]{1,64}` (con `fullmatch`, porque `$` acepta un salto de línea final), descripción no vacía tras recortar espacios, `risk` instancia de `RiskLevel`, y esquema correcto según `check_schema` (incluido que cada campo de `required` esté en `properties`, y una profundidad máxima de 32 niveles que también corta esquemas circulares). Después comprueba la colisión de nombre. Solo si todo pasa, guarda una entrada con una **copia profunda** del esquema. La validación de argumentos usa esa copia.
- **Rationale**: acumular los problemas permite corregir una definición en una sola pasada; la copia impide que una herramienta debilite su esquema después de registrada; no modificar nada antes de terminar las comprobaciones garantiza que un registro rechazado deje el catálogo idéntico (SC-004).
- **Alternatives considered**: leer las propiedades de la herramienta en cada llamada (rechazada: el esquema podría cambiar tras el registro); detenerse en el primer problema (rechazada: peor experiencia de desarrollo).

## R-09 — Comportamiento de `validate_args`

- **Decision**: una herramienta no registrada lanza `UnknownToolError` que cita el nombre pedido, sin enumerar las herramientas disponibles. Si los argumentos no son un `dict`, se informa como una violación en la raíz. Con argumentos válidos devuelve una copia superficial (`dict(args)`) y nunca los modifica. Un `name` que no es texto cuenta como una herramienta desconocida: `validate_args` lanza `UnknownToolError` y `get` devuelve `None`.
- **Rationale**: el modelo ya conoce su lista de herramientas por el prefijo del contexto, y enumerarlas aquí crecería con el número de herramientas MCP. Una copia superficial protege la entrega de mutaciones del nivel superior sin el coste de copiar contenidos grandes (el texto de un archivo, por ejemplo).
- **Alternatives considered**: devolver el mismo objeto (rechazada: expone el diccionario del llamador); copia profunda (rechazada: coste innecesario).

## R-10 — Sincronía y concurrencia

- **Decision**: la API es síncrona, como el puerto, y sin cerrojos. Se documenta que el registro se pensó para un único bucle de eventos y que las herramientas se registran al arrancar.
- **Rationale**: el puerto `ToolRegistry` es síncrono por diseño de HU-00-01 y las operaciones son de microsegundos. Un cerrojo añadiría complejidad sin un uso concurrente real hoy. Registrar herramientas con la sesión en marcha (por ejemplo, MCP) es un caso de HU-08-03, que decidirá cuándo se refresca la lista que ve el modelo.

## R-11 — Cableado y composición

- **Decision**: no se crea `bootstrap.py` en esta historia. `InMemoryToolRegistry()` no tiene argumentos de constructor, así que el cableado será una línea en la raíz de composición cuando exista. La quickstart lo documenta como nota, sin código.
- **Rationale**: la skill ordena conectar implementaciones solo en `bootstrap.py`, pero crear la raíz de composición sin bucle ni adaptadores sería código de una historia posterior (Principio VI).

## R-12 — Estrategia de pruebas

- **Decision**:
  1. `DummyTool` gana un parámetro opcional `schema` que, si se omite, devuelve el mismo esquema de hoy (retrocompatible con `tests/contracts/test_contracts.py`). Su lista `recorded_executions` sirve para comprobar "0 ejecuciones" en AC-01.
  2. Pruebas unitarias por módulo bajo `tests/unit/core/tools/`, reflejando `src/`.
  3. Un consumidor mínimo escrito dentro del test de integración (no en `src/`) imita al bucle: consulta el catálogo, valida, ejecuta y devuelve un `ToolResult`. Se escribe antes de registrar la herramienta "nueva" para demostrar AC-02.
  4. Una prueba de contrato en `tests/contracts/` ejercita el comportamiento declarado por `ToolRegistry` (colisión, ausencia con `get`, `ValueError` al validar) contra el registro concreto, de forma que cualquier registro futuro pueda reutilizarla.
  5. Una prueba AST nueva comprueba que `core/tools/` importa solo biblioteca estándar y `harness_agent`. La prueba existente de fronteras solo busca una lista de SDK prohibidos, y la directriz "solo stdlib" merece una comprobación propia.
  6. Prueba de humo de rendimiento con un margen amplio (la media de varias validaciones debe quedar por debajo de 10 ms para un esquema de 20 campos, unas cien veces por encima de lo esperable) para no ser inestable en la CI de Windows.
  7. Los tests también pasan `mypy --strict`, que la CI ejecuta sobre `src tests`.
- **Rationale**: cubre cada escenario de aceptación del spec con una prueba nombrable, sin red.
- **Alternatives considered**: usar `unittest.mock` en lugar de ampliar `DummyTool` (rechazada: la directriz es usar `DummyTool`, y la ampliación es mínima); añadir `import-linter` (rechazada: no está instalado ni configurado, y cambiar dependencias fijadas está fuera de alcance).

## R-13 — Compatibilidad de versiones de Python

- **Decision**: el código se escribe y se prueba en Python 3.12, la única versión soportada (PD-07).
- **Rationale**: `pyproject.toml` fija `requires-python >=3.12,<3.13`, `mypy` usa `python_version = "3.12"`, `ruff` apunta a `py312` y la CI ejecuta solo 3.12. Ya no hay que evitar sintaxis de 3.12 ni mantener compatibilidad con versiones anteriores.

## R-14 — Lectura de RNF-2 y RNF-13

- **Decision**: seguir la interpretación del spec (RNF-2: extensibilidad sin tocar el bucle; RNF-13: núcleo desacoplado de proveedores, interfaz e infraestructura) y trasladarla a comprobaciones verificables: AC-02 con el consumidor mínimo, la prueba AST de solo stdlib y la verificación de que `core/interfaces/` no cambia.
- **Rationale**: el texto íntegro de ambos requisitos no está en la documentación activa. Si el Product Owner los precisa de otra manera, las comprobaciones se ajustan sin cambiar el diseño.
