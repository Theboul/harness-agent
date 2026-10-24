# Contratos de Interfaces del Núcleo (HU-00-01)

**Feature**: Esqueleto del Repositorio e Interfaces Acordadas (HU-00-01)  
**Date**: 2026-10-17  
**Status**: Firmas acordadas para HU-00-01 (Asincronía provisional sujeta a SPK-02; Aprobación formal sujeta a Sp1-03)

Todas las interfaces del núcleo se definen como Clases Base Abstractas (`abc.ABC`) con decoradores `@abstractmethod` y type hints estrictos en `src/harness_agent/core/`.

---

## 1. Proveedores y Modelos de Lenguaje

### `Provider` (Interfaz Abstracta)
*Aísla a LiteLLM y proveedores propietarios; el núcleo nunca importa SDKs de proveedores (RNF-12).*
- **`async def complete(self, messages: list[Message], tools: list[ToolDefinition] | None = None) -> ProviderResponse`**
  - **Entrada**:
    - `messages`: Lista ordenada de objetos `Message` que representan la ventana de contexto.
    - `tools`: Lista opcional de esquemas de herramientas declaradas en formato canónico.
  - **Salida**: `ProviderResponse` conteniendo `content: str`, `tool_calls: list[ToolCall]` y `usage: TokenUsage`.
  - **Notas**: *[PROVISIONAL - SPK-02]* Firma asíncrona provisional.
  - **Errores** *(ampliación aditiva de HU-00-03, pendiente del visto bueno de A)*: `ProviderError(Exception)` es la base de los fallos que un proveedor comunica al núcleo, con tres tipos concretos: `QuotaExceeded` (cuota agotada), `ProviderTimeout` (tiempo agotado) y `ProviderUnavailable` (servicio no disponible). Se exportan desde `harness_agent.core`. Los adaptadores reales traducen a ellos los errores de su biblioteca y el núcleo nunca ve una excepción de un SDK; la firma de `complete` no cambia.

---

## 2. Herramientas y Políticas de Ejecución

### `Tool` (Interfaz Abstracta)
*Contrato unificado para todas las herramientas (nativas de archivos, shell, MCP o subagentes).*
- **Atributos de clase o propiedades**:
  - `nombre: str`: Identificador único de la herramienta (ej. `leer_archivo`, `shell`).
  - `descripcion: str`: Descripción funcional para el modelo de lenguaje.
  - `esquema: dict[str, Any]`: Esquema JSON conforme a JSON Schema que valida los argumentos.
  - `riesgo: RiskLevel`: Nivel de riesgo (`LOW`, `MEDIUM`, `HIGH`) utilizado por la política.
- **`async def run(self, args: dict[str, Any]) -> ToolResult`**
  - **Entrada**: Argumentos validados contra `esquema`.
  - **Salida**: `ToolResult` con `call_id`, `content` textual y bandera `is_error`.
  - **Notas**: *[PROVISIONAL - SPK-02]* Firma asíncrona provisional.

### `ToolRegistry` (Interfaz Abstracta)
*Catálogo y validador de herramientas antes de la ejecución.*
- **`def register(self, tool: Tool) -> None`**: Registra una nueva herramienta. Falla si el nombre colisiona.
- **`def get(self, name: str) -> Tool | None`**: Obtiene una herramienta por su nombre unívoco.
- **`def list(self) -> list[Tool]`**: Retorna la lista de todas las herramientas registradas.
- **`def validate_args(self, name: str, args: dict[str, Any]) -> dict[str, Any]`**: Valida los argumentos recibidos contra el esquema JSON de la herramienta; genera error si es inválido.

### `PermissionPolicy` (Interfaz Abstracta)
*Evaluación de seguridad con falla cerrada (V-02, RF-5.1).*
- **`def evaluate(self, call: ToolCall) -> PermissionDecision`**
  - **Entrada**: La llamada a herramienta extraída de la respuesta del modelo.
  - **Salida**: `PermissionDecision` (`DENY`, `ASK`, `ALLOW`). Falla cerrada: si no coincide con una regla explícita, devuelve `ASK`.

### `Approver` (Interfaz Abstracta)
*Canal bidireccional asíncrono hacia la interfaz humana (V-01).*
- **`async def request(self, call: ToolCall, details: dict[str, Any]) -> ApprovalResult`**
  - **Entrada**: La llamada a herramienta y detalles de contexto/efecto para mostrar al usuario.
  - **Salida**: `ApprovalResult` con la acción decidida (`APPROVE_ONCE`, `APPROVE_SESSION`, `REJECT`) y motivo en caso de rechazo.

---

## 3. Estado, Persistencia y Contexto

### `SessionStore` (Interfaz Abstracta)
*Persistencia transaccional por evento en SQLite (RF-3.1, RF-3.2, V-03).*
- **`def save_event(self, event: Event) -> None`**: Guarda un evento individual de forma atómica en SQLite.
- **`def load_session(self, session_id: str) -> list[Event]`**: Carga el historial completo ordenado de eventos de una sesión.
- **`def list_sessions(self) -> list[SessionSummary]`**: Lista las sesiones registradas con su estado y marca temporal.

### `MemoryStore` (Interfaz Abstracta)
*Persistencia de memoria entre sesiones separada del historial (RF-4.1, V-05).*
- **`def save(self, key: str, content: str) -> None`**: Guarda o actualiza un registro de memoria.
- **`def search(self, token_budget: int) -> list[MemoryItem]`**: Consulta memorias relevantes priorizadas por recencia dentro del presupuesto de tokens.
- **`def delete(self, key: str) -> bool`**: Elimina una memoria por su clave unívoca.

### `ContextManager` (Interfaz Abstracta)
*Control de ventana de contexto, prefijo estable y compactación (RF-2.1, RF-2.3, V-04).*
- **`def assemble(self, session_id: str, model_id: str) -> list[Message]`**: Construye la ventana de contexto ensamblando prefijo estable (instrucciones, herramientas, contexto esencial) + memorias + resumen + eventos recientes.
- **`def compact(self, session_id: str) -> CompactResult`**: Dispara la compactación de eventos antiguos sin alterar el contexto esencial ni eliminar eventos de SQLite.

---

## 4. Entorno de Ejecución y Conexiones

### `Shell` (Interfaz Abstracta)
*Única puerta de ejecución de comandos del sistema operativo (V-08, RF-1.2).*
- **Atributos**: `interpreter_name: str` (`powershell` en Windows, `bash` en Linux).
- **`def execute(self, command: str, timeout_seconds: float) -> ShellResult`**: Ejecuta el comando en un subproceso con tiempo límite y retorna `exit_code`, `output` y bandera `timed_out`.

### `AuthorizedArea` (Interfaz Abstracta)
*Control de contención de rutas sobre ruta real para evitar escapes de directorio (V-17, A-01, A-02).*
- **Atributos**: `root: Path`: Ruta raíz real normalizada del espacio de trabajo.
- **`def contains(self, path: Path | str) -> bool`**: Resuelve la ruta real (normalizando enlaces simbólicos, `..`, unidades de disco y rutas UNC) y confirma si el destino queda estrictamente dentro de `root`.

### `TaskCriteria` (Interfaz Abstracta)
*Gestión de la tabla `criterios` en SQLite como fuente de verdad (V-15, RF-11.1).*
- **`def load_criteria(self, session_id: str) -> list[TaskCriteriaItem]`**: Lee los criterios desde SQLite.
- **`def get_pending(self, session_id: str) -> list[TaskCriteriaItem]`**: Obtiene los criterios con `passes = False`.
- **`def mark_passes(self, criteria_id: str, evidence: str) -> None`**: Actualiza el criterio a `passes = True` con evidencia verificable. Solo invocable por el harness.
- **`def export_readonly_copy(self, session_id: str, destination: Path) -> None`**: Exporta la copia JSON de solo lectura.

### `McpClient` (Interfaz Abstracta)
*Conexión y traducción de servidores de herramientas externas MCP (RF-8.1, RF-8.2).*
- **`async def connect(self) -> None`**: Establece la conexión con el servidor MCP por stdio.
- **`async def list_tools(self) -> list[Tool]`**: Descubre las herramientas remotas y las traduce a instancias del contrato `Tool`.
- **`async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult`**: Invoca la herramienta remota.

### `SubagentRunner` (Interfaz Abstracta)
*Lanzamiento de sesiones hijas aisladas (V-06, RF-9.1, RF-9.4).*
- **`async def execute(self, profile: str, goal: str, context: list[Message], output_schema: dict[str, Any]) -> SubagentResult`**: Ejecuta el subagente con ventana limpia y límites estrictos, retornando un resultado estructurado.

---

## 5. Bus de Eventos

### `EventBus` (Interfaz Abstracta)
*Único canal del núcleo hacia interfaces de usuario y observabilidad (RF-1.8).*
- **`def emit(self, event: Event) -> None`**: Publica un evento en el bus notificando a todos los manejadores suscritos.
- **`def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None`**: Registra una función manejadora para un tipo de evento específico.
