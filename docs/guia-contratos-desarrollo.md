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
