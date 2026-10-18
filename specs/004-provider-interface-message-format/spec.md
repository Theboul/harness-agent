# Feature Specification: HU-07-01 — Interfaz Provider y formato interno de mensajes

**Feature Branch**: `004-provider-interface-message-format`  
**Created**: 2026-10-18  
**Status**: En revisión (2026-10-18): AC-02 verificado; AC-01 verificado técnicamente en local para el dominio de entradas válidas mediante `to_*_envelope` + `restore_messages` (D1, D2, D8 y D9 resueltos con el diseño D-02), **pendiente de la aprobación técnica individual de A, B y C y de la revisión por otra área**; defectos D3–D7 y D10 corregidos con pruebas de regresión; dominio válido de `system` aclarado por decisión del Product Owner (D6). La historia NO está terminada  
**Responsable**: A — Núcleo  
**Sprint**: Sprint 1 | **Estimación**: 3 PHU (~9-12 horas F5)  
**Input**: Especificar una interfaz Provider independiente de los proveedores comerciales y un formato interno único para mensajes, llamadas a herramientas, resultados y consumo de tokens, conforme a RF-7.1, RF-7.2, RNF-12 y las decisiones de diseño del proyecto HARNESS v2.5.

---

## Clarifications

### Session 2026-10-18

- **Q: ¿Cuáles son los contratos reales y qué entidades se conservan para HU-07-01?** → **A:** Se reutilizan estrictamente y sin mutaciones ni versiones paralelas las entidades canónicas de [`src/harness_agent/core/entities.py`](../../src/harness_agent/core/entities.py) (`Role`, `ToolCall`, `ToolResult`, `TokenUsage`, `Message`) y [`src/harness_agent/core/interfaces/provider.py`](../../src/harness_agent/core/interfaces/provider.py) (`ToolDefinition`, `ProviderResponse`, `Provider` con `async def complete`). No se crea `Provider.chat` ni variantes de `Message`.
- **Q: ¿Cuál es el estado de SPK-01 y cómo afecta a esta especificación?** → **A:** `SPK-01` está en estado `Pendiente` en `docs/PROGRESO.md` (asignada al Desarrollador B — Estado en Sprint 1). HU-07-01 no asume completitud previa de SPK-01; en su lugar, fija formalmente el formato canónico y las reglas abstractas de traducción bidireccional contra los esquemas estándar de la industria (OpenAI tool calling y Anthropic tool use), sirviendo de especificación base para que SPK-01 y HU-07-02 implementen y validen sus adaptadores.
- **Q: ¿Cuál es el estado de HU-00-01 y D-01 de SPK-02?** → **A:** `HU-00-01` está implementada en código (T001-T015), con 9 pruebas unitarias aprobadas al 100% (conteo a la fecha de la sesión de clarificación; hoy la suite completa supera las 200 pruebas) y aprobada por el Product Owner (2026-10-17); el hito de ratificación colegiada Sp1-03 (A, B, C) continúa en curso. `SPK-02` concluyó con 7 pruebas aprobadas y la decisión técnica formal `D-01` ratificó que `Provider.complete` es definitivamente un método asíncrono (`async def`). *(Estado a la fecha de la sesión de clarificación; corrección del 2026-10-18: SPK-02 sigue «En revisión», su suite creció a más de 30 pruebas y D-01 está PENDIENTE DE APROBACIÓN, por lo que la firma asíncrona de `Provider.complete` es la acordada en HU-00-01 y no está ratificada todavía.)*
- **Q: ¿Cuál es el alcance exacto de la conversión sin pérdida para AC-01?** → **A:** Preservación integral e invertible (*round-trip*) del 100% de los datos: roles (`Role`), texto (`content`), identificadores únicos de llamadas (`ToolCall.id`), nombres de herramientas (`ToolCall.name`), argumentos como diccionarios estructurados (`ToolCall.arguments`), resultados vinculados por `call_id` (`ToolResult.call_id`), texto de respuesta (`ToolResult.content`), bandera de error (`ToolResult.is_error`), consumo de tokens (`TokenUsage`) y la marca de seguridad de origen no confiable (`is_external`).
- **Q: ¿Cómo se verificará la intercambiabilidad del proveedor (AC-02) sin construir el bucle de producción HU-01-01?** → **A:** Mediante un arnés/consumidor de prueba desacoplado en la suite de pruebas (`tests/`) que simule un turno de ejecución agéntico invocando únicamente `await provider.complete(messages, tools)`. Se verificará empíricamente que sustituir la instancia del proveedor (`FakeProvider` vs doble de prueba alternativo) no requiere cambiar ninguna línea de dicho consumidor.
- **Q: ¿Cómo se gestionan las diferencias de capacidades entre proveedores y la prevención de pérdidas silenciosas?** → **A:** Mediante la regla arquitectónica de falla cerrada (*fail-closed*): si un mensaje, herramienta o argumento contiene datos no representables en el esquema destino (por ejemplo, esquemas no serializables en JSON Schema o argumentos corruptos), el adaptador debe emitir una excepción explícita (`ValueError` o error de validación) y registrar el evento, quedando estrictamente prohibido omitir, descartar o truncar datos de forma silenciosa.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conversión bidireccional sin pérdida entre formato canónico y esquemas de proveedores (Priority: P1)

Como desarrollador del núcleo de HARNESS, necesito un formato canónico de mensajes y herramientas fuertemente tipado que pueda traducirse a los esquemas de entrada de distintos proveedores LLM (como OpenAI y Anthropic) y reconstruirse a partir de sus respuestas sin perder roles, llamadas a herramientas, resultados, argumentos ni metadatos de seguridad, para garantizar que la conversación interna del agente no dependa del dialecto de ninguna API comercial.

**Why this priority**: Es el criterio de aceptación central AC-01 de HU-07-01 y el fundamento del desacoplamiento arquitectónico (Principio III y RNF-12). Sin una representación interna completa e invertible, cualquier cambio de modelo o proveedor provocaría corrupción de contexto o pérdida de argumentos estructurados.

**Independent Test**: Se puede verificar de forma aislada e independiente convirtiendo una secuencia de mensajes canónicos representativa (mensaje de sistema, mensaje de usuario con marca de contenido externo, mensaje del asistente con múltiples llamadas a herramientas y mensaje de herramienta con resultado de éxito o fallo) al formato de carga de un proveedor y reconstruyendo el objeto canónico equivalente, comprobando igualdad exacta campo por campo.

**Acceptance Scenarios**:

1. **Given** una secuencia de mensajes canónicos con roles (`system`, `user`, `assistant`, `tool`), contenido de texto y marca de origen externo (`is_external`), **When** se transforma a la estructura esperada por un proveedor y se reconstruye al formato canónico, **Then** la reconstrucción conserva idénticos roles, contenidos textuales y banderas sin pérdida de información (AC-01).
2. **Given** un mensaje de asistente con múltiples llamadas a herramientas (`tool_calls`), cada una con su identificador único (`id`), nombre de función (`name`) y argumentos estructurados (`arguments`), **When** se convierte a la carga del proveedor y se deserializa la respuesta devuelta, **Then** todos los identificadores y diccionarios de argumentos coinciden exactamente con los emitidos originalmente.
3. **Given** un mensaje de rol herramienta (`tool`) que transporta el resultado de una ejecución (`ToolResult`), **When** se traduce al esquema del proveedor y se reinterpreta, **Then** se conservan intactos el `call_id`, la salida textual (`content`) y la indicación de fallo o error de ejecución (`is_error`).
4. **Given** una respuesta de proveedor con desglose de consumo de tokens, **When** se normaliza en el objeto canónico `TokenUsage`, **Then** los tokens de entrada (`input_tokens`) y de salida (`output_tokens`) quedan asignados con precisión y el total reportado coincide con la suma aritmética (`total_tokens`).

---

### User Story 2 - Intercambiabilidad del proveedor en el bucle agéntico sin alterar el código invocador (Priority: P1)

Como arquitecto de software y desarrollador del bucle agéntico, necesito que el bucle interactúe exclusivamente con la abstracción `Provider` a través de su método asíncrono canónico `complete(messages, tools)`, para que el proveedor LLM pueda ser sustituido (por ejemplo, entre un proveedor simulado `FakeProvider`, un adaptador LiteLLM o un cliente especializado) mediante inyección de dependencias sin modificar una sola línea de código del bucle.

**Why this priority**: Cumple directamente con el criterio de aceptación AC-02. Protege el principio de inversión de dependencias y la pureza hexagonal del núcleo (`core/`), permitiendo probar todo el sistema sin costo de red ni claves comerciales.

**Independent Test**: Puede probarse de forma independiente implementando un arnés de prueba que ejecute una rutina de bucle simple contra dos implementaciones distintas de `Provider` (un proveedor simulado predecible y un doble de prueba con latencia simulada), verificando que la invocación `await provider.complete(messages, tools)` devuelve un `ProviderResponse` estándar sin que el consumidor conozca la implementación concreta.

**Acceptance Scenarios**:

1. **Given** un bucle o rutina de control que utiliza la interfaz `Provider`, **When** se reemplaza la instancia del proveedor por otra implementación compatible con el contrato, **Then** el bucle continúa ejecutándose normalmente y procesando turnos sin requerir modificaciones en ninguna línea de su código fuente (AC-02).
2. **Given** una invocación a `provider.complete(messages, tools)`, **When** el proveedor procesa la solicitud, **Then** la respuesta devuelta es siempre una instancia de `ProviderResponse` que contiene texto plano (`content`), lista de llamadas a herramientas (`tool_calls`) y métricas de consumo (`usage: TokenUsage | None`).
3. **Given** un conjunto de herramientas disponibles declaradas como `ToolDefinition` (nombre, descripción y esquema JSON de parámetros), **When** se envían al proveedor en `complete(messages, tools)`, **Then** el proveedor recibe las definiciones en formato agnóstico y el bucle no realiza adaptaciones específicas para el proveedor.

---

### User Story 3 - Integridad de seguridad y trazabilidad de contenido no confiable (Priority: P2)

Como responsable de seguridad del agente, necesito que el formato canónico `Message` preserve de manera explícita e inmutable la bandera `is_external` que señala el contenido proveniente de fuentes no confiables (archivos locales, herramientas, respuestas de subagentes o servidores MCP), para que los componentes de contexto y de auditoría puedan distinguir las instrucciones del usuario legítimo de datos potencialmente portadores de inyecciones de prompt.

**Why this priority**: Respalda las decisiones arquitectónicas V-13 y RF-7.1, preparando las defensas en profundidad del sistema antes de exponerlo a herramientas del sistema de archivos (`HU-01-03`) y del shell (`HU-01-04`).

**Independent Test**: Se verifica creando mensajes que contienen datos leídos de archivos o salidas de comandos con `is_external=True`, transformándolos y serializándolos, comprobando que la marca no se borra, no se altera en las conversiones internas y permanece accesible para los evaluadores de políticas.

**Acceptance Scenarios**:

1. **Given** un mensaje que encapsula contenido proveniente de una fuente externa o herramienta, **When** se construye la entidad `Message` con `is_external=True`, **Then** la entidad mantiene inmutable su bandera y previene que el contenido sea categorizado erróneamente como instrucción de usuario confiable.
2. **Given** una serialización interna o conversión de contexto, **When** se transmiten los mensajes, **Then** la información de origen (`is_external`) no se descarta ni se confunde con el rol conversacional.

---

### Edge Cases

- **Mensaje con contenido vacío pero con llamadas a herramientas**: Ocurre habitualmente cuando el modelo decide invocar herramientas sin emitir texto previo para el usuario. El sistema debe aceptar `content=""` o cadenas vacías siempre que `tool_calls` contenga al menos un `ToolCall`.
- **Múltiples llamadas a herramientas en un solo turno (Parallel Tool Calling)**: El modelo puede emitir varias llamadas a herramientas simultáneas. `Message.tool_calls` debe aceptar una tupla con $N \ge 1$ llamadas distintas, conservando el orden original y sus IDs independientes.
- **Herramienta que devuelve error de ejecución**: Si un comando o herramienta falla, el resultado se reporta en `ToolResult(is_error=True)`. La conversión debe preservar la bandera `is_error` de forma inequívoca para que el modelo interprete el fallo sin que el arnés lance excepciones no controladas.
- **Argumentos de herramienta como diccionario vacío o cadena JSON no parseada**: Si un proveedor entrega argumentos vacíos (`{}`) o argumentos mal formados, la capa adaptadora debe validar o rechazar antes de construir `ToolCall`, garantizando que `ToolCall.arguments` sea siempre un diccionario tipado (`dict[str, Any]`).
- **Proveedor que no reporta tokens o reporta valores nulos**: Si la API del proveedor omite el bloque de uso (`usage`), `ProviderResponse.usage` debe admitir `None`, o inicializar `TokenUsage(input_tokens=0, output_tokens=0)` de forma segura sin fallar.
- **Incompatibilidad de nombres o esquemas de roles**: Proveedores como Anthropic utilizan `user` y `assistant` pero manejan `system` a nivel de parámetro superior de llamada. El formato canónico retiene `Role.SYSTEM` en la lista secuencial de mensajes, dejando la responsabilidad de extracción o agrupamiento al adaptador específico sin alterar la lista canónica original. Los mensajes `system` solo son válidos como prefijo contiguo al inicio de la secuencia (decisión del Product Owner del 2026-10-18, ver la aclaración de AC-01 más abajo); uno posterior a un mensaje `user`, `assistant` o `tool` es una entrada inválida y se rechaza.
- **Detección de datos no representables (Fail-closed)**: Si un esquema de herramienta o payload contiene tipos no serializables o roles no soportados por el proveedor de destino, la conversión debe fallar con una excepción explícita (`ValueError`), impidiendo cualquier descarte o truncamiento silencioso de información.

---

## Requirements *(mandatory)*

### Clarificaciones Operacionales y Estado de Dependencias

1. **Reutilización estricta de entidades de `HU-00-01`**:
   - Se conservan e inspeccionan las entidades existentes en [`src/harness_agent/core/entities.py`](../../src/harness_agent/core/entities.py) e [`src/harness_agent/core/interfaces/provider.py`](../../src/harness_agent/core/interfaces/provider.py):
     - `Role`: Enum (`SYSTEM = "system"`, `USER = "user"`, `ASSISTANT = "assistant"`, `TOOL = "tool"`).
     - `ToolCall`: Dataclass inmutable (`id: str`, `name: str`, `arguments: dict[str, Any]`).
     - `ToolResult`: Dataclass inmutable (`call_id: str`, `content: str`, `is_error: bool = False`).
     - `TokenUsage`: Dataclass inmutable (`input_tokens: int = 0`, `output_tokens: int = 0`, propiedad `total_tokens`).
     - `Message`: Dataclass inmutable (`role: Role`, `content: str = ""`, `tool_calls: tuple[ToolCall, ...]`, `tool_result: ToolResult | None`, `usage: TokenUsage | None`, `is_external: bool = False`).
     - `ToolDefinition`: Dataclass inmutable (`name: str`, `description: str`, `parameters: dict[str, Any]`).
     - `ProviderResponse`: Dataclass inmutable (`content: str = ""`, `tool_calls: list[ToolCall]`, `usage: TokenUsage | None`).
     - `Provider`: Clase base abstracta (`ABC`).
   - **Regla de oro**: NO crear nuevas versiones ni clases paralelas (como `MessageV2` o `CustomMessage`) si las entidades existentes satisfacen completamente los requisitos funcionales.

2. **Contrato de método Provider**:
   - Se ratifica la firma asíncrona real:
     ```python
     async def complete(
         self,
         messages: list[Message],
         tools: list[ToolDefinition] | None = None,
     ) -> ProviderResponse: ...
     ```
   - **Prohibición expresa**: NO crear métodos alternativos como `Provider.chat`, `Provider.generate` o variantes síncronas.

3. **Estado transparente de dependencias**:
   - `HU-00-01`: Código implementado y verificado (T001-T015). Aprobado por el Product Owner (2026-10-17). Ratificación técnica colegiada de los desarrolladores A, B y C (Sp1-03 / T016) registrada como hito en curso.
   - `SPK-01` (*Spike: traducir herramientas entre OpenAI y Anthropic con LiteLLM*): Asignada al desarrollador B — Estado en el Sprint 1. Estado en `PROGRESO.md`: `Pendiente`. HU-07-01 establece formalmente los modelos canónicos y los requisitos de conversión abstractos sin depender de la finalización previa de SPK-01, aportando el marco contra el cual SPK-01 y HU-07-02 verificarán sus adaptadores.
   - `SPK-02` (*Spike: modelo asíncrono y cancelación*): Validado experimentalmente en Windows y WSL2 Ubuntu; sigue «En revisión». La decisión técnica D-01 propone la naturaleza asíncrona (`async def`) para `Provider.complete` y está **PENDIENTE DE APROBACIÓN** de A, B y C; esta especificación no la da por ratificada.

---

### Functional Requirements

- **FR-001**: El formato canónico DEBE utilizar exclusivamente los cuatro roles definidos en la enumeración `Role` (`SYSTEM`, `USER`, `ASSISTANT`, `TOOL`), garantizando tipado estricto e interoperabilidad con cadenas de texto (RF-7.1).
- **FR-002**: La estructura `Message` DEBE ser inmutable (`frozen=True`), normalizar automáticamente el rol si se proporciona como cadena de texto, y asegurar que la colección de llamadas a herramientas sea inmutable (tupla) (RF-7.1, Principio III).
- **FR-003**: Cada llamada a herramienta emitida por un modelo DEBE representarse mediante `ToolCall`, conteniendo obligatoriamente un identificador (`id`), el nombre de la herramienta (`name`) y un diccionario de argumentos validados (`arguments`) (RF-7.1).
- **FR-004**: Cada resultado de ejecución de herramienta DEBE representarse mediante `ToolResult`, vinculando el identificador original de la llamada (`call_id`), la salida textual procesada o recortada (`content`) y un indicador booleano de error (`is_error`) (RF-7.1, V-11).
- **FR-005**: El consumo de tokens reportado por cualquier proveedor DEBE normalizarse en la estructura `TokenUsage`, exponiendo `input_tokens` y `output_tokens` como enteros no negativos, y calculando `total_tokens` como la suma exacta de ambos (RF-7.2, V-09).
- **FR-006**: La declaración de herramientas enviada al proveedor DEBE expresarse mediante `ToolDefinition`, conteniendo el identificador de la herramienta (`name`), la descripción en lenguaje natural para el modelo (`description`) y el esquema formal de parámetros según la especificación JSON Schema (`parameters`) (RF-7.1, RF-1.2).
- **FR-007**: La interfaz `Provider` DEBE heredar de `abc.ABC` y declarar el método abstracto asíncrono `complete(messages, tools) -> ProviderResponse`, asegurando que cualquier adaptador de proveedor cumpla estrictamente este contrato (RF-7.1, D-01).
- **FR-008**: La especificación DEBE definir reglas formales de transformación bidireccional entre el formato canónico y los formatos estándar de la industria (esquema de mensajes OpenAI y esquema de mensajes Anthropic), de tal forma que la conversión de ida y vuelta (round-trip) preserve el 100% de la información sin mutaciones ni pérdidas (AC-01, RNF-12).
- **FR-009**: El bucle agéntico DEBE interactuar con los proveedores únicamente a través de las abstracciones del paquete `core` (`Provider`, `Message`, `ToolDefinition`, `ProviderResponse`), garantizando que la sustitución de un proveedor por otro no requiera modificar ninguna línea de código del bucle (AC-02, RNF-12).
- **FR-010**: El paquete del núcleo (`src/harness_agent/core/`) NUNCA DEBE importar SDKs o librerías externas de proveedores (`openai`, `anthropic`, `litellm`, `google-generativeai`, etc.), manteniendo su pureza conforme a la Arquitectura Hexagonal (RNF-12, Principio III).
- **FR-011**: Los mecanismos de conversión DEBEN aplicar una política de falla cerrada (*fail-closed*), lanzando una excepción explícita ante cualquier elemento o estructura no representable en el esquema del proveedor, prohibiendo descartes o mutaciones silenciosas de datos (AC-01, Principio IX).
- **FR-012**: La verificación de intercambiabilidad del proveedor (AC-02) DEBE ejecutarse mediante un consumidor de prueba desacoplado que opere exclusivamente contra la interfaz `Provider`, demostrando sustitución polimórfica sin implementar ni depender del bucle de producción de HU-01-01 (AC-02, Principio VI).

---

### Key Entities *(mandatory)*

- **Role**: Enumeración canónica de los participantes conversacionales (`system`, `user`, `assistant`, `tool`).
- **ToolCall**: Especificación de una invocación de herramienta requerida por el modelo, compuesta por `id` unívoco, `name` de la herramienta registrada y diccionario `arguments`.
- **ToolResult**: Resultado textual de la ejecución de una herramienta, asociado a su `call_id` correspondiente e indicando si la ejecución resultó en error (`is_error`).
- **TokenUsage**: Registro unificado del consumo de recursos de cómputo del modelo (`input_tokens`, `output_tokens` y propiedad calculada `total_tokens`).
- **Message**: Unidad atómica e inmutable de interacción en el contexto del agente, que agrupa el rol, texto, llamadas a herramientas opcionales, resultado de herramienta opcional, uso de tokens y bandera de procedencia externa (`is_external`).
- **ToolDefinition**: Contrato de presentación de una herramienta ante el modelo, conformado por nombre descriptivo, instrucciones de uso y esquema JSON de parámetros válidos.
- **ProviderResponse**: Objeto estandarizado de respuesta producido por `Provider.complete`, conteniendo el texto generado, las llamadas a herramientas solicitadas y el informe de consumo de tokens.
- **Provider**: Puerto hexagonal primario (ABC) que define el servicio asíncrono de completado conversacional que todo adaptador de proveedor debe satisfacer.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: La prueba de conversión bidireccional (round-trip) entre el formato canónico interno y las representaciones de los dos proveedores de referencia (OpenAI y Anthropic) demuestra una fidelidad del 100% (cero campos omitidos, cero tipos alterados y cero cadenas de argumentos corrompidas).
- **SC-002**: Un bucle o rutina de prueba que ejecuta turnos utilizando la interfaz abstracta `Provider` funciona indistintamente con al menos dos implementaciones distintas (un proveedor simulado y un adaptador de prueba) sin requerir modificaciones en el código de la rutina consumidora (0 líneas alteradas).
- **SC-003**: El 100% del código de entidades y de la interfaz abstracta cumple con tipado estricto en Python 3.12 (`mypy --strict` con 0 advertencias y 0 errores) y supera todas las reglas del linter (`ruff check` y `ruff format` limpios).
- **SC-004**: Cero dependencias externas importadas en `src/harness_agent/core/`: una auditoría de importaciones confirma que `core/entities.py` y `core/interfaces/provider.py` dependen exclusivamente de la biblioteca estándar de Python (`dataclasses`, `enum`, `typing`, `abc`).
- **SC-005**: La suite de pruebas de conversión y compatibilidad de interfaz se ejecuta completamente en memoria local en menos de 1 segundo sin requerir conexión a internet ni llamadas a APIs de pago.

---

## Limitaciones conocidas y defectos pendientes

> Sección añadida el 2026-10-18 tras la auditoría de la implementación. No modifica los criterios de aceptación ni los requisitos funcionales.

### Aclaración formal del dominio válido de AC-01 (decisión D6, 2026-10-18)

**Estado: APROBADA POR PRODUCT OWNER** (decisión funcional; la aprobación técnica de [D-02](../../docs/decisiones/D-02-preservacion-metadatos-conversion.md) por A, B y C sigue pendiente).

El texto de AC-01 **no se modifica** y se conserva literalmente:

> AC-01 — Conversión sin pérdida: Dado el formato interno, cuando se convierte a la entrada de un proveedor y de vuelta, entonces no se pierde información.

Aclaración del **dominio de entradas válidas** sobre el que AC-01 se evalúa:

1. «El formato interno» se refiere a una secuencia canónica **válida**.
2. En una secuencia canónica válida, los mensajes `system` solo aparecen como **prefijo contiguo al inicio**: se admiten cero, uno o varios `system` iniciales.
3. Un `system` después de un mensaje `user`, `assistant` o `tool` es una entrada **inválida**, no una entrada válida que deba convertirse sin pérdida. Se rechaza con `ConversionError`; no se normaliza ni se reordena en silencio.
4. Rechazar una entrada inválida **no demuestra** conversión sin pérdida; esa demostración corresponde a las entradas válidas y se obtiene con la ruta del envelope (D1, D2, D8 y D9 resueltos el 2026-10-18; ver más abajo).

Coherencia con otros requisitos: FR-011 (falla cerrada) se cumple con más fuerza, porque la entrada inválida falla de forma explícita; FR-008 y la User Story 3 siguen exigiendo preservar `is_external` e `is_error` para entradas válidas (D1, D2); la edge case de incompatibilidad de roles (Anthropic) queda alineada con esta regla.

**Impacto futuro (no implementado aquí):** el `ContextManager` deberá respetar la regla: no puede emitir `system` fuera del prefijo inicial (por ejemplo, los resúmenes de compactación no pueden insertarse como `system` intercalados). Cuando se implemente, deberá añadirse una prueba de contrato.

Trazabilidad: [D-02 §5](../../docs/decisiones/D-02-preservacion-metadatos-conversion.md), tarea T026 de [`tasks.md`](tasks.md), `tests/adapters/test_canonical_validation.py`.

### Defectos D1, D2, D8 y D9: resueltos con el envelope (pendiente de aprobación técnica)

- **D1 — `is_external`.** Ni OpenAI ni Anthropic tienen un campo de red para `Message.is_external`. Con `to_openai_envelope` / `to_anthropic_envelope` y `restore_messages(envelope)` se conserva en un sidecar local y nunca viaja en el payload.
- **D2 — `is_error` con OpenAI.** Se conserva en el sidecar; en Anthropic se compara el campo nativo con el del sidecar.
- **D8 — `Message.usage`** y **D9 — `Message.content` de un `TOOL` distinto de `ToolResult.content`** se conservan en el sidecar.
- **Alcance:** la restauración exacta es solo por envelope. `from_openai_messages` y `from_anthropic_payload` interpretan un payload suelto, siguen sin poder recuperar estos atributos y están **obsoletas** (`DeprecationWarning`, T024).
- **Estado:** implementado y probado en local (D-02 §0). La aprobación técnica individual de A, B y C sigue pendiente; hasta entonces T018 permanece sin marcar y la historia en revisión. Los criterios de aceptación no se modificaron.

### Reglas de falla cerrada vigentes (defectos D3–D7 corregidos)

- Los argumentos de herramientas deben ser un objeto JSON; listas, escalares, `null` y otros tipos producen `ConversionError`.
- Un mensaje de usuario de Anthropic que mezcla `tool_result` con otros bloques se rechaza (el modelo canónico no puede conservar esa agrupación sin metadatos de correlación locales). Los bloques desconocidos (`image`, `document`, etc.) se rechazan nombrando su tipo; no se implementa soporte multimodal.
- `ToolResult.content` es siempre `str`: una lista de bloques `text` se une con saltos de línea (representación textual aprobada); cualquier otra estructura se rechaza.
- Varios mensajes `system` iniciales se envían a Anthropic como lista de bloques de texto, conservando orden y límites. Un mensaje `system` después de cualquier mensaje `user`, `assistant` o `tool` es una **secuencia canónica inválida** (decisión del Product Owner, 2026-10-18) y produce `ConversionError` en ambos proveedores, sin normalización ni reordenamiento silenciosos. Un `system` de contenido vacío no puede representarse en el parámetro superior de Anthropic: la función solo-payload lo rechaza con `ConversionError`; la ruta del envelope lo omite del payload externo y conserva su existencia, contenido y posición en el sidecar (decisión del Product Owner; D-02 §0).
- Un mensaje canónico incoherente (D10) se rechaza con `ConversionError` que identifica rol, campo, motivo y posición: `tool_calls` solo es válido en mensajes `assistant`, `tool_result` solo en mensajes `tool`, y un mensaje `tool` exige un `tool_result` no nulo. Un mensaje `tool` cuyo `content` difiere del `content` de su `tool_result` **no** se rechaza: se conserva con el envelope (D9, resuelto).
- Los bloques de texto adyacentes de un mismo mensaje se unen con salto de línea (los límites entre ellos se normalizan); en un mensaje de asistente el texto debe preceder a los `tool_use`.
- Los errores por payloads externos inválidos se reportan siempre como `ConversionError` (subclase de `ValueError`).

---

## Assumptions & Scope Boundaries

### Assumptions

- **Reutilización directa de HU-00-01**: Las estructuras base implementadas durante HU-00-01 son sólidas, satisfacen la especificación de diseño arquitectónico y no requieren ser reconstruidas desde cero.
- **Entorno de ejecución**: El proyecto opera exclusivamente en Python 3.12.x conforme a la decisión PD-07 y el Principio III de la Constitución.
- **Independencia de proveedores reales**: La verificación de esta especificación se realiza mediante dobles de prueba y pruebas de mapeo sintáctico/semántico en memoria, sin exigir cuentas comerciales ni credenciales de API activas.
- **Rol de SPK-01**: SPK-01 validará empíricamente la compatibilidad práctica de herramientas con LiteLLM cuando el Desarrollador B la ejecute. La presente especificación establece el estándar canónico inmutable al que dicha investigación y el adaptador HU-07-02 deberán ajustarse.

### Scope Boundaries

- **Dentro del alcance**:
  - Ratificación y blindaje de las entidades canónicas del modelo de mensajes (`entities.py`).
  - Especificación de la interfaz abstracta `Provider` con método `complete(messages, tools)` (`interfaces/provider.py`).
  - Reglas y pruebas de conversión bidireccional sin pérdida (formato canónico $\leftrightarrow$ formato de proveedores de referencia).
  - Demostración de intercambiabilidad de implementaciones en el consumidor mediante inyección de dependencias.
- **Fuera del alcance (explícitamente diferido)**:
  - Implementación del adaptador funcional LiteLLM (asignado a `HU-07-02` en Sprint 1 para Desarrollador B — Estado).
  - Conexiones de red a APIs reales de OpenAI, Anthropic o Gemini.
  - Implementación del bucle agéntico de producción (asignado a `HU-01-01` en Sprint 1 para Desarrollador A — Núcleo).
  - Lógica de reintentos con espera exponencial (`HU-07-04`) y conmutación automática por fallo (`HU-07-05`).
  - Streaming de tokens en tiempo real (`HU-07-06`, diferido al Backlog).
  - Persistencia en base de datos SQLite (`HU-03-01`), integración MCP (`HU-08-01`) y subagentes (`HU-09-01`).
