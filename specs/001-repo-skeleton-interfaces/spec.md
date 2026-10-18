# Feature Specification: Esqueleto del Repositorio e Interfaces Acordadas (HU-00-01)

**Feature Branch**: `001-repo-skeleton-interfaces`

**Created**: 2026-10-17

**Status**: En revisión (T001 a T015 implementadas; pendiente la aprobación de contratos Sp1-03)

**Proyecto**: HARNESS v2.5 | **Sprint**: 1 | **Responsable**: A — Núcleo | **Tareas de referencia**: Sp1-01, Sp1-02, Sp1-03

**Input**: User description: "Especificar un repositorio modular y contratos de componentes que permitan a los tres desarrolladores (A: Núcleo, B: Estado, C: Control y conexiones) trabajar en paralelo mediante interfaces abstractas y dobles de prueba, garantizando que el núcleo no dependa directamente de ningún proveedor de IA y respetando la constitución de HARNESS v2.5."

## Clarifications

### Session 2026-10-17
- **Q**: ¿Cómo deben tiparse provisionalmente las firmas de los contratos del núcleo (`Provider`, `Tool`, `Approver`) en HU-00-01 mientras se espera el veredicto de concurrencia de SPK-02?
- **A**: Opción A — Adoptar firmas asíncronas provisionales (`async def`) para `Provider.complete`, `Tool.run` y `Approver.request`. Mantener síncronos (`def`) los contratos de almacenamiento y operaciones locales (`SessionStore`, `MemoryStore`, `AuthorizedArea`, `TaskCriteria`).
  *Condiciones acordadas*:
  1. Decisión provisional hasta completar la investigación de `SPK-02` (modelo asíncrono y cancelación).
  2. No implementar todavía lógica de concurrencia avanzada ni ejecución paralela en `HU-00-01`.
  3. Utilizar `async def` también en los dobles de prueba de los contratos asíncronos (`tests/doubles/`).
  4. Evitar operaciones bloqueantes dentro del bucle asíncrono; utilizar adaptadores cuando sea necesario.
  5. Registrar esta decisión en el plan técnico sin considerar `SPK-02` como completado.
  6. Mantener pendiente la aprobación formal de contratos por los tres integrantes (`Sp1-03`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Desarrollo concurrente desacoplado mediante contratos y dobles de prueba (Priority: P1)

Como integrante del equipo de desarrollo (A: Núcleo, B: Estado, C: Control y conexiones), quiero contar con las definiciones de interfaz abstracta y tipos canónicos en el repositorio desde el primer día, para poder implementar y probar mi módulo de forma autónoma usando dobles de prueba sin bloquearme por el avance de los demás componentes.

**Why this priority**: Es la base fundacional de todo el proyecto (Sprint 1, E0 Fundaciones). Sin interfaces abstractas estables, los tres desarrolladores tendrían dependencias cruzadas continuas y no podrían trabajar en paralelo.

**Independent Test**: Puede probarse creando implementaciones simuladas (mocks / dummies en memoria) de cada contrato (`Provider`, `Tool`, `SessionStore`, etc.) y verificando que interactúan limpiamente respetando sus firmas de métodos y tipos de retorno, sin tocar infraestructura real.

**Acceptance Scenarios**:

1. **Given** el repositorio clonado con la estructura base de paquetes, **When** un desarrollador implementa un componente que consume `Provider` o `SessionStore`, **Then** puede instanciar un doble de prueba que satisfaga la interfaz abstracta (usando `async def` para contratos asíncronos) y ejecutar pruebas unitarias completas sin requerir bases de datos ni servicios externos (**AC-01**).
2. **Given** los contratos acordados, **When** se ejecutan las pruebas de conformidad de tipos estáticos, **Then** las firmas de métodos garantizan compatibilidad total entre las llamadas del emisor y las respuestas del receptor.

---

### User Story 2 - Pureza del núcleo y aislamiento de proveedores externos (Priority: P1)

Como arquitecto de software y responsable de calidad, quiero asegurar que ningún módulo del núcleo (`core/`) dependa o importe SDKs propietarios ni librerías de proveedores de IA, para mantener el núcleo agnóstico, reutilizable y protegido frente a cambios en APIs externas.

**Why this priority**: Constituye la regla de oro arquitectónica (V-14, RNF-12) y el Principio III de la Constitución de HARNESS. Un acoplamiento temprano al SDK de un proveedor comprometería la portabilidad y la capacidad de conmutación por fallo.

**Independent Test**: Se valida mediante una prueba automatizada de análisis estático / inspección de AST que escanee todas las importaciones dentro de `src/harness_agent/core/`, asegurando 0 referencias a librerías propietarias (`litellm`, `openai`, `anthropic`, `google-genai`).

**Acceptance Scenarios**:

1. **Given** cualquier archivo dentro de `src/harness_agent/core/`, **When** se ejecuta la prueba de auditoría de importaciones, **Then** solo se detectan importaciones de la biblioteca estándar de Python o de submódulos internos de contratos y tipos (**AC-02**).
2. **Given** la necesidad de cambiar de proveedor LLM o de adaptador de base de datos, **When** se reemplaza la implementación del adaptador en `adapters/`, **Then** el código del núcleo permanece 100 % inalterado.

---

### User Story 3 - Comunicación interna estándar mediante mensajes tipados y bus de eventos (Priority: P2)

Como desarrollador que integra la interfaz de usuario, el bucle agéntico o el almacén de eventos, quiero un modelo de datos unificado para mensajes y eventos del sistema, para que todos los subsistemas hablen el mismo lenguaje canónico sin conversiones ad-hoc ni ambigüedades.

**Why this priority**: Evita la proliferación de estructuras heterogéneas de datos y garantiza que el registro de eventos, la compactación y la auditoría operen sobre un esquema común y predecible.

**Independent Test**: Se prueba instanciando mensajes de cada rol (`sistema`, `usuario`, `asistente`, `herramienta`) con sus metadatos (origen externo, uso de tokens) y emitiendo/suscribiendo cada uno de los 17 tipos de eventos en el `EventBus` para confirmar que se transmiten intactos.

**Acceptance Scenarios**:

1. **Given** una respuesta de modelo con llamadas a herramientas y consumo de tokens, **When** se transforma al formato canónico `Message`, **Then** conserva identificadores únicos de llamada, nombre de herramienta, argumentos serializados y marcas de origen externo sin pérdida de información.
2. **Given** un evento de ciclo de vida publicado en el `EventBus`, **When** los suscriptores registrados reciben el evento, **Then** la carga útil respeta estrictamente el tipo de evento correspondiente (`approval_requested`, `tool_finished`, etc.).

---

### Edge Cases

- ¿Qué sucede si una implementación concreta de un contrato omite uno de los métodos definidos o altera su firma? El sistema DEBE fallar en tiempo de verificación estática de tipos (`mypy`/`pyright`) y en tiempo de instanciación si se utilizan clases base abstractas (`abc.ABC`).
- ¿Qué ocurre si un mensaje externo contiene caracteres malformados o datos no conformes con el esquema? El modelo canónico DEBE validar los campos requeridos y aislar el contenido marcándolo obligatoriamente como dato externo (`es_externo=True`).
- ¿Cómo se maneja un suscriptor del bus de eventos que genera una excepción durante la emisión? El `EventBus` debe garantizar que un fallo en un suscriptor de registro o interfaz no impida la notificación a los demás suscriptores críticos (como el almacenamiento transaccional de eventos).

## Scope & Boundaries *(mandatory)*

### Dentro del Alcance (In Scope)

1. **Estructura de paquetes base**: Crear el árbol de paquetes modular en `src/harness_agent/core/`, `src/harness_agent/adapters/`, `src/harness_agent/cli/` y `tests/` con sus respectivos `__init__.py` y exportaciones raíz.
2. **Contratos abstractos del núcleo (14 interfaces)**:
   - `Provider`: Firma asíncrona provisional `async def complete(messages: list[Message], tools: list[ToolDefinition]) -> ProviderResponse`.
   - `Tool`: Firma asíncrona provisional `async def run(args: dict[str, Any]) -> ToolResult`, con atributos `name`, `description`, `schema`, `risk`.
   - `ToolRegistry`: Firmas de `register`, `get`, `list`, `validate_args`.
   - `PermissionPolicy`: Firma síncrona `evaluate(call: ToolCall) -> PermissionDecision` (falla cerrada: deny > ask > allow).
   - `Approver`: Firma asíncrona `async def request(call: ToolCall, details: dict) -> ApprovalResult` (V-01).
   - `SessionStore`: Firmas síncronas de `save_event(event)`, `load_session(session_id)`, `list_sessions()`.
   - `MemoryStore`: Firmas síncronas de `save(key, content)`, `search(token_budget)`, `delete(key)`.
   - `ContextManager`: Firmas síncronas de `assemble(session_id, model_id)`, `compact(session_id)`.
   - `McpClient`: Firmas asíncronas provisionales de `connect()`, `list_tools()`, `call_tool(name, arguments)`.
   - `SubagentRunner`: Firma asíncrona provisional `async def execute(profile, objective, context, output_schema) -> SubagentResult`.
   - `Shell`: Firma síncrona `execute(command, timeout_seconds) -> ShellResult`.
   - `TaskCriteria`: Firmas síncronas de `load_criteria`, `get_pending`, `mark_passes`, `export_readonly_copy`.
   - `AuthorizedArea`: Firma síncrona `contains(path) -> bool` sobre ruta real normalizada y propiedad `root`.
   - `EventBus`: Firmas de `emit(event)` y `subscribe(event_type, handler)`.
3. **Modelos canónicos de datos de mensajes y eventos**: Tipado de roles (`sistema`, `usuario`, `asistente`, `herramienta`), bloques de contenido, llamadas a herramientas, resultados de herramientas, desglose de tokens y catálogo de 17 eventos de bus.
4. **Dobles de prueba canónicos y validación estática**: Implementación de mocks en memoria (`DummyTool`, `FakeProvider`, `InMemorySessionStore`) con firmas asíncronas para contratos asíncronos (`async def`) y suite de pruebas que certifique conformidad de contratos y 0 importaciones de proveedores externos en `core/`.
5. **Aprobación conjunta de contratos (Sp1-03)**: Revisión formal y participación humana obligatoria para acordar las firmas y esquemas antes de iniciar implementaciones dependientes.

### Fuera del Alcance (Out of Scope)

- **No implementar lógica agéntica real**: El bucle `run()` o ejecución multi-turno corresponde a `HU-01-01`.
- **No implementar concurrencia avanzada ni ejecución paralela**: La validación de paralelismo y cancelación controlada depende de `SPK-02`.
- **No implementar herramientas reales**: Las herramientas de archivos (`HU-01-03`) y el shell (`HU-01-04`) se construirán en sus respectivas historias.
- **No implementar persistencia real en SQLite**: Las tablas SQLite y consultas reales corresponden a `HU-03-01` y `HU-03-02`.
- **No implementar cliente MCP real ni subagentes**: Corresponden a E8 (`HU-08-01`..`04`) y E9 (`HU-09-01`..`06`).
- **No seleccionar proveedores definitivos ni configurar claves/costos reales**: `D-IA` permanece abierta; las pruebas usarán exclusivamente `FakeProvider` y dobles de prueba sin dependencias de red.
- **No cerrar el modelo de concurrencia**: La adopción definitiva de `asyncio` depende de la investigación en `SPK-02`.
- **No modificar criterios de aceptación ni prioridades**: Los criterios originales de `HU-00-01` (AC-01 y AC-02) son inalterables (Principio V).

## Dependencies & Traceability *(mandatory)*

### Dependencias de HU-00-01
- **Depende de**: Ninguna historia previa (es la historia fundacional del proyecto).

### Historias que dependen de HU-00-01
- `HU-00-02` (Integración continua): Requiere la estructura de paquetes y configuración de pruebas.
- `HU-00-03` (Proveedor simulado): Implementa la interfaz `Provider`.
- `HU-01-01` (Bucle agéntico básico): Consume `Provider`, `ToolRegistry`, `EventBus` y `PermissionPolicy`.
- `HU-01-02` (Registro de herramientas): Implementa `Tool` y `ToolRegistry`.
- `HU-01-03` (Herramientas de archivos): Implementa `Tool` y consume `AuthorizedArea`.
- `HU-05-01` (Política de permisos): Implementa `PermissionPolicy` y consume `AuthorizedArea` y `Approver`.
- `HU-07-01` (Interfaz Provider): Extiende y formaliza el formato interno de mensajes para adaptadores.

### Trazabilidad con Requisitos
- **RNF-12**: Arquitectura desacoplada de proveedores (garantizada por la interfaz abstracta `Provider` y la ausencia de SDKs en `core/`).
- **RNF-13**: Modularidad y extensibilidad (garantizada por los contratos de `Tool`, `ToolRegistry` y adaptadores desacoplados).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El repositorio DEBE proveer la estructura modular de paquetes en `src/harness_agent/core/` (interfaces, modelos, lógica agéntica), `src/harness_agent/adapters/` (implementaciones concretas externas), `src/harness_agent/cli/` (interfaz de terminal) y `tests/` (pruebas unitarias, contratos y dobles).
- **FR-002**: El sistema DEBE definir el contrato abstracto `Provider` con la operación asíncrona provisional `async def complete(messages: list[Message], tools: list[ToolDefinition]) -> ProviderResponse`, reportando texto, llamadas a herramientas y uso real de tokens.
- **FR-003**: El sistema DEBE definir el contrato abstracto `Tool` con la operación asíncrona provisional `async def run(args: dict[str, Any]) -> ToolResult` y atributos requeridos (`name`, `description`, `schema`, `risk`), junto con `ToolRegistry` (registro, obtención, listado y validación de argumentos contra esquema).
- **FR-004**: El sistema DEBE definir el contrato abstracto `PermissionPolicy` con la operación síncrona `evaluate(call: ToolCall) -> PermissionDecision`, implementando semántica de falla cerrada con los estados `denegar`, `preguntar` y `permitir`.
- **FR-005**: El sistema DEBE definir el contrato abstracto `Approver` con la operación asíncrona `async def request(call: ToolCall, details: dict) -> ApprovalResult` para resolver aprobaciones humanas (aprobar una vez, aprobar para la sesión, rechazar con motivo) conforme a V-01.
- **FR-006**: El sistema DEBE definir los contratos de persistencia síncronos `SessionStore` (guardar evento transaccional, cargar sesión, listar sesiones) y `MemoryStore` (guardar memoria, consultar dentro de presupuesto de tokens, borrar).
- **FR-007**: El sistema DEBE definir el contrato síncrono `ContextManager` con operaciones para ensamblar la ventana de contexto respetando el prefijo estable y disparar la compactación automática por umbral.
- **FR-008**: El sistema DEBE definir el contrato `McpClient` con operaciones asíncronas provisionales para conectar con servidores de herramientas externas, descubrir herramientas disponibles y traducirlas a la interfaz estándar `Tool`.
- **FR-009**: El sistema DEBE definir el contrato `SubagentRunner` con la operación asíncrona provisional `async def execute(profile: str, objective: str, context: list[Message], output_schema: dict) -> SubagentResult`, garantizando aislamiento de ventana y retorno estructurado.
- **FR-010**: El sistema DEBE definir los contratos de soporte operativo síncronos: `Shell` (ejecución acotada con código de salida y tiempo límite), `TaskCriteria` (gestión de criterios en SQLite y verificación) y `AuthorizedArea` (contención sobre ruta real normalizada).
- **FR-011**: El sistema DEBE definir el contrato `EventBus` con operaciones para emitir eventos fuertemente tipados y suscribir manejadores por tipo de evento.
- **FR-012**: El sistema DEBE definir los modelos inmutables o fuertemente tipados para el formato interno de mensajes: roles (`sistema`, `usuario`, `asistente`, `herramienta`), bloques de contenido, llamadas a herramientas, resultados de herramientas, desglose de uso de tokens y bandera de origen externo.
- **FR-013**: El sistema DEBE definir el catálogo formal de eventos del bus: `user_message`, `assistant_message`, `tool_requested`, `tool_finished`, `approval_requested`, `approval_resolved`, `context_compacted`, `permission_decided`, `criteria_tampered`, `limit_reached`, `provider_error`, `provider_switched`, `subagent_started`, `subagent_finished`, `interrupted`, `session_started` y `criterion_verified`.

### Key Entities

- **Message**: Representa una entrada o salida en el historial conversacional. Contiene rol, bloques de texto, lista de llamadas a herramientas solicitadas, identificador de llamada respondida, desglose de tokens y marca de procedencia de datos externos.
- **ToolCall / ToolResult**: Estructuras que encapsulan la invocación de una acción externa y su respuesta (código de salida / contenido y estado de éxito o error).
- **Event**: Estructura de evento del bus que incluye tipo de evento, identificador de sesión, marca temporal y carga útil fuertemente tipada.
- **PermissionDecision**: Resultado de la evaluación de seguridad indicando si una acción se ejecuta directamente, se bloquea con motivo o requiere escalado a aprobación humana.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de las 14 interfaces abstractas especificadas en la arquitectura v2.5 cuentan con firmas tipadas completas e independientes en el código base, respetando la asincronía provisional acordada.
- **SC-002**: 0 dependencias o importaciones directas de SDKs propietarios de proveedores (`litellm`, `openai`, `anthropic`, `google-genai`) dentro de los módulos de `src/harness_agent/core/` (**AC-02**).
- **SC-003**: Se provee una suite de pruebas de conformidad con dobles de prueba (`FakeProvider`, `DummyTool`, `InMemorySessionStore`, `RecordingEventBus`) que valida el 100 % de los contratos sin requerir red externa ni servicios reales, empleando `async def` para contratos asíncronos (**AC-01**).
- **SC-004**: El tiempo total de ejecución de la suite de pruebas de contratos y verificación de tipos es inferior a 5 segundos en entornos locales (Windows y Linux).
- **SC-005**: La especificación se encuentra descompuesta en 16 microtareas atómicas (T001 a T016) de 15 a 35 minutos cada una, dentro del límite de 15 a 40 minutos del Principio II.

## Plan de Microtareas de Implementación

El desglose vigente está en [tasks.md](tasks.md): 16 microtareas (T001 a T016) de 15 a 35 minutos cada una, dentro del límite del Principio II de la Constitución (15 a 40 minutos). T016 es el punto de control humano (Sp1-03).

## Assumptions

- El lenguaje de implementación exclusivo es Python 3.12+ utilizando `typing` moderno y `abc.ABC`.
- No se requiere configuración de claves de API ni aprovisionamiento de bases de datos para completar y verificar `HU-00-01`.
- Los adaptadores concretos (LiteLLM, SQLite, Shell, MCP) se desarrollarán en historias posteriores basándose exclusivamente en estos contratos.
- `SPK-02` (investigación de concurrencia y cancelación) y `Sp1-03` (aprobación formal del equipo) permanecen formalmente pendientes.
