# Guía de Consumo de Contratos y Uso de Dobles de Prueba

> Documento de referencia para los desarrolladores **A** (Núcleo), **B** (Estado y Conexiones) y **C** (Control e Interacción) para trabajar en paralelo a partir de `HU-00-01`.

---

## 1. Importación Unificada desde el Núcleo

Todos los contratos, modelos canónicos y eventos deben importarse directamente desde `harness_agent.core`. Nunca se deben importar submódulos internos directamente.

```python
from harness_agent.core import (
    # Entidades de mensajería
    Role,
    Message,
    ToolCall,
    ToolResult,
    TokenUsage,
    # Catálogo de eventos
    EventType,
    Event,
    # Contratos abstractos
    Provider,
    ProviderResponse,
    ProviderError,        # fallos de proveedor: base de los tres siguientes
    QuotaExceeded,
    ProviderTimeout,
    ProviderUnavailable,
    Tool,
    ToolRegistry,
    RiskLevel,
    PermissionPolicy,
    Approver,
    SessionStore,
    MemoryStore,
    ContextManager,
    Shell,
    AuthorizedArea,
    TaskCriteria,
    EventBus,
)
```

---

## 2. Guía para el Desarrollador B (Estado y Persistencia)

### Historias inmediatas: HU-00-03 (FakeProvider), HU-00-04 (Config), HU-03-01 (SQLite)

#### Implementar un adaptador de almacenamiento real (`SessionStore`):
```python
from harness_agent.core import SessionStore, SessionSummary, Event

class SqliteSessionStore(SessionStore):
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def save_event(self, event: Event) -> None:
        # Guardar atómicamente el evento en la tabla 'eventos'
        ...

    def load_session(self, session_id: str) -> list[Event]:
        # Cargar eventos ordenados cronológicamente
        ...

    def list_sessions(self) -> list[SessionSummary]:
        ...
```

#### Sesiones en SQLite (HU-03-01):

`SqliteSessionStore` (en `harness_agent.adapters.storage`) crea el esquema (tablas `sessions` y `events`, versión 1) al abrirse y crea sesiones. **Todavía no hereda de `SessionStore`**: `save_event` y `load_session` llegan con HU-03-02. El puerto tampoco tiene `create_session`, así que esa operación es del adaptador (hallazgo para A, B y C en `PROGRESO.md`).

```python
from harness_agent.adapters.storage import SqliteSessionStore

with SqliteSessionStore(config.paths.sessions_db) as store:   # el directorio se crea si falta
    parent = store.create_session(model="fake/test", goal="Arreglar el ticket 42")
    child = store.create_session(parent_id=parent.id)         # sesión de subagente
    assert child.parent_id == parent.id and child.status == "active"
    store.list_sessions()                                      # list[SessionSummary], más antigua primero
```

- El reloj y el generador de identificadores se pueden inyectar (`clock=`, `id_factory=`) para pruebas deterministas; por defecto UTC y `uuid4`.
- Errores: `SessionStoreError` (base), `SchemaVersionError` (versión de esquema desconocida; la base no se modifica) y `ParentSessionNotFound`. Los mensajes no reproducen datos de entrada ni rutas.
- La raíz de composición (`bootstrap.py`, aún inexistente) deberá construirlo con `config.paths.sessions_db`.

#### Usar dobles en pruebas de B sin levantar SQLite ni proveedores reales:
```python
from tests.doubles import InMemorySessionStore, InMemoryMemoryStore, DummyProvider
from harness_agent.core import Event, EventType

session_store = InMemorySessionStore()
memory_store = InMemoryMemoryStore()
provider = DummyProvider()

# Guardar evento en memoria
event = Event.create(session_id="sesion-test", type=EventType.USER_MESSAGE, payload={"text": "test"})
session_store.save_event(event)
assert len(session_store.load_session("sesion-test")) == 1
```

#### Qué doble de proveedor usar (HU-00-03):

| Necesito… | Uso |
|---|---|
| Una respuesta fija, sin más | `DummyProvider` |
| Excepciones arbitrarias, bloquear una llamada a propósito o ids de llamada repetidos | `ScriptedProvider` |
| Reproducir un guion y simular cuota, tiempo agotado o indisponibilidad con los tipos canónicos | `FakeProvider` |

`FakeProvider` recibe una lista de pasos; la llamada *i* a `complete` consume el paso *i*. Cada paso es una `ProviderResponse` (texto y/o llamadas a herramientas) o un `ProviderError` que se lanza al instante, sin esperar. No usa red, reloj ni azar, así que el mismo guion da el mismo resultado en cada ejecución. Los errores canónicos (`ProviderError`, `QuotaExceeded`, `ProviderTimeout`, `ProviderUnavailable`) se importan de `harness_agent.core`; los adaptadores reales lanzarán esos mismos tipos.

```python
from harness_agent.core import ProviderResponse, QuotaExceeded, ToolCall
from tests.doubles import FakeProvider

provider = FakeProvider(
    [
        ProviderResponse(tool_calls=[ToolCall(id="c1", name="echo", arguments={"text": "hola"})]),
        QuotaExceeded("cuota agotada"),  # la segunda llamada falla
        ProviderResponse(content="listo"),
    ]
)
```

- El guion se valida al crear el proveedor: no puede estar vacío, cada paso debe ser una `ProviderResponse` o una instancia de `ProviderError`, y los ids de las llamadas a herramientas no pueden estar vacíos ni repetirse en todo el guion.
- Si el bucle pide más pasos de los escritos, el proveedor lanza `ScriptExhausted` y deja `provider.exhausted = True`; nunca inventa una respuesta.
- Para comprobar lo que el bucle envió, usa `provider.received`, `provider.received_tools` y `provider.call_count`.
- Con el bucle real, un `QuotaExceeded` termina el turno como `TurnStatus.PROVIDER_FAILED` y publica `PROVIDER_ERROR` con `error_type == "QuotaExceeded"`.

---

## 3. Guía para el Desarrollador C (Herramientas, Control y Permisos)

### Historias inmediatas: HU-01-02 (ToolRegistry), HU-01-03 (Herramientas de archivos), HU-05-01 (Permisos)

#### Implementar una herramienta nativa (`Tool`):
```python
from typing import Any
from harness_agent.core import Tool, ToolResult, RiskLevel

class LeerArchivoTool(Tool):
    @property
    def name(self) -> str:
        return "leer_archivo"

    @property
    def description(self) -> str:
        return "Lee el contenido de un archivo UTF-8 dentro del espacio de trabajo."

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ruta": {"type": "string", "description": "Ruta relativa del archivo"}
            },
            "required": ["ruta"]
        }

    @property
    def risk(self) -> RiskLevel:
        return RiskLevel.LOW

    async def run(self, args: dict[str, Any]) -> ToolResult:
        # Implementación asíncrona de lectura segura
        return ToolResult(call_id=args.get("call_id", ""), content="contenido...")
```

#### Usar dobles en pruebas de C para evaluar políticas y aprobación:
```python
import pytest
from tests.doubles import DummyTool, DummyApprover
from harness_agent.core import ToolCall, ApprovalAction

@pytest.mark.asyncio
async def test_politica_con_dobles():
    tool = DummyTool(name="shell", risk="high")
    approver = DummyApprover(default_action=ApprovalAction.APPROVE_ONCE)

    call = ToolCall(id="c1", name="shell", arguments={"cmd": "pytest"})
    aprobacion = await approver.request(call, {"detalle": "ejecutar pytest"})
    assert aprobacion.action == ApprovalAction.APPROVE_ONCE
```

#### Herramientas de archivos y área de trabajo (HU-01-03):

Cuatro herramientas nativas actúan solo dentro del área autorizada (`adapters/tools/`), y `WorkspaceArea` (`adapters/system/`) es la implementación real de `AuthorizedArea`: decide la contención sobre la **ruta real** (resuelve `..`, rutas absolutas y enlaces simbólicos; en Windows rechaza además UNC, otra unidad, flujos alternos y nombres reservados) y falla cerrado.

| Herramienta | Argumentos | Riesgo | Qué hace |
|---|---|---|---|
| `leer_archivo` | `path` | bajo | Texto UTF-8 de un archivo (máximo 256 KiB) |
| `escribir_archivo` | `path`, `content` | medio | Crea o reemplaza un archivo (máximo 1 MiB) y las carpetas que falten |
| `listar_archivos` | `path` | bajo | Entradas de una carpeta, ordenadas, sin recursión (máximo 200) |
| `buscar_texto` | `path`, `query` | bajo | Texto literal, sensible a mayúsculas, recursivo (máximo 50 coincidencias) |

`bootstrap.py` aún no existe: la composición se hace a mano (en las pruebas de integración) y debe usar **la misma área** en las herramientas y en la política.

```python
from harness_agent.adapters.system import WorkspaceArea
from harness_agent.adapters.tools import ListFilesTool, ReadFileTool, SearchTextTool, WriteFileTool
from harness_agent.core import DefaultPermissionPolicy, InMemoryToolRegistry, PermissionRules

root = config.paths.workspace_root                       # None si no está configurada
area = WorkspaceArea(root) if root is not None else None  # sin área, nada se ejecuta

registry = InMemoryToolRegistry()
for tool in (ReadFileTool(area), WriteFileTool(area), ListFilesTool(area), SearchTextTool(area)):
    registry.register(tool)
policy = DefaultPermissionPolicy(registry, area, PermissionRules())
```

- Todas llaman `path` a la ruta (convención de HU-05-01); el registro rechaza argumentos extra o mal formados.
- Antes de actuar, cada herramienta pregunta dos veces al área (con el texto de la ruta y con la ruta real); si alguna dice que no, devuelve `[fuera_del_area]` y no toca el disco.
- Ninguna lanza: todo error es un `ToolResult` con `is_error=True`, una etiqueta (`[no_existe]`, `[no_es_archivo]`, `[no_es_carpeta]`, `[demasiado_grande]`, `[no_es_texto]`, `[contenido_invalido]`, `[consulta_invalida]`, `[sin_area]`, `[fuera_del_area]`, `[error_de_archivo]`), la causa y una sugerencia en español.
- Hoy una escritura fuera del área se pregunta y, sin aprobador, el bucle la deniega con un texto genérico; la causa específica llega con HU-05-03.

---

## 4. Reglas Obligatorias de Diseño y Pureza

1. **Firmas asíncronas (propuesta SPK-02 / D-01, pendiente de aprobación)**: `Provider.complete`, `Tool.run` y `Approver.request` son corutinas (`async def`) y siguen siendo provisionales hasta que A, B y C aprueben D-01 y HU-00-01 (T016). El spike midió en Windows una cancelación con retorno de control de 1.0 a 2.4 ms (límite de AC-01: 500 ms); la evidencia en Linux está pendiente. Todas las demás interfaces (`SessionStore`, `MemoryStore`, `ContextManager`, `AuthorizedArea`) son síncronas (`def`).
2. **Pureza del Núcleo (AC-02)**: Ningún módulo bajo `src/harness_agent/core/` puede importar SDKs de proveedores (`openai`, `anthropic`, `litellm`, `google-genai`). Las implementaciones concretas residen en `src/harness_agent/adapters/`.
3. **Inmutabilidad**: `Message`, `ToolCall`, `ToolResult`, `TokenUsage` y `Event` son `@dataclass(frozen=True)`. No intentar mutar sus atributos en tiempo de ejecución.
4. **Verificación Continua**: Antes de abrir un PR, ejecutar:
   ```powershell
   pytest tests/
   mypy src/ tests/
   ```
