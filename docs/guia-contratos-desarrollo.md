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

`SqliteSessionStore` (en `harness_agent.adapters.storage`) crea el esquema (tablas `sessions` y `events`, versión 1) al abrirse y crea sesiones. Desde HU-03-02 hereda de `SessionStore` (ver más abajo). El puerto no tiene `create_session`, así que esa operación es del adaptador (hallazgo para A, B y C en `PROGRESO.md`).

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

#### Persistir eventos (HU-03-02):

`SqliteSessionStore` implementa `save_event` y `load_session`. Cada evento se guarda en su propia transacción durable (`BEGIN IMMEDIATE`, `PRAGMA synchronous = FULL`): un evento confirmado sobrevive a un cierre abrupto del proceso y una escritura cortada no deja la base corrupta.

```python
from harness_agent.adapters.storage import SqliteSessionStore, attach_event_recorder

with SqliteSessionStore(config.paths.sessions_db) as store:
    session = store.create_session(goal="Arreglar el ticket 42")   # la sesión debe existir antes del primer evento
    attach_event_recorder(bus, store)                                # los 17 tipos de evento se guardan al emitirse
    ...
    events = store.load_session(session.id)                          # en el orden en que se guardaron
```

- **Orden**: `load_session` devuelve los eventos por su orden de guardado (`seq` consecutivo por sesión), no por fecha. Una sesión desconocida o sin eventos devuelve `[]`.
- **Sesión previa obligatoria**: guardar un evento de una sesión inexistente lanza `SessionNotFound` (a diferencia de `InMemorySessionStore`, que la crea al vuelo). Un identificador de evento repetido lanza `DuplicateEvent`.
- **Contenido JSON**: el `payload` se guarda como JSON. Los tipos no representables (objetos, `bytes`, `NaN`, referencias circulares) lanzan `EventSerializationError` sin tocar la base; las tuplas vuelven como listas.
- **Errores del bus**: `attach_event_recorder` usa solo los puertos `EventBus` y `SessionStore`. Si el almacén falla, el emisor recibe `EventDeliveryError` con la causa original.
- **Secretos**: el contenido se guarda sin redactar hasta HU-10-02 (riesgo abierto PD-10 en `PROGRESO.md`).

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
                "path": {"type": "string", "description": "Ruta relativa del archivo"}
            },
            "required": ["path"]
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
from harness_agent.core import ApprovalAction, RiskLevel, ToolCall

@pytest.mark.asyncio
async def test_politica_con_dobles():
    tool = DummyTool(name="shell", risk=RiskLevel.HIGH)
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

#### Herramienta `shell` (HU-01-04):

`ShellTool` (`adapters/tools/shell.py`) ejecuta un comando a través del puerto `Shell` y es de riesgo **alto** sin argumento `path`, así que `DefaultPermissionPolicy` siempre pregunta: sin aprobador (HU-05-03) el bucle la deniega y no se lanza ningún proceso.

| Aspecto | Valor |
|---|---|
| Argumentos | `command` (1 a 8 000 caracteres), `timeout_seconds` (1 a 600, por defecto 120) |
| Carpeta de partida | Raíz del área de trabajo; cada llamada es independiente |
| Intérprete | `select_shell(platform.system(), cwd=...)`: PowerShell en Windows, bash en lo demás (`BashShell`, `PowerShellShell`) |
| Resultado | `Código de salida: 0` + salida; o `[codigo_de_salida=N]`, `[tiempo_agotado]`, `[interprete_no_disponible]`, `[sin_area]`, `[error_de_shell]` |
| Salida | Estándar y de errores juntas, a lo sumo 20 000 caracteres; si se recorta, cabeza + `[salida recortada: se omitieron N caracteres]` + cola. Encima, el registro de herramientas recorta con la misma marca todo resultado que pase de `limits.max_tool_output_chars` (24 000 por defecto, HU-02-02) |
| Tiempo agotado | Se termina el comando **y sus procesos hijos** (SIGTERM y luego SIGKILL al grupo en POSIX; `taskkill /T /F` en Windows) |
| Entorno | El del harness sin las variables de claves de los proveedores (`PROVIDER_KEY_VARIABLES`) |

```python
import platform

from harness_agent.adapters.system import environment_notice, select_shell
from harness_agent.adapters.tools import ShellTool
from harness_agent.config import PROVIDER_KEY_VARIABLES, process_environment
from harness_agent.core import Message, Role

shell = select_shell(
    platform.system(),
    cwd=area.root,
    environ=process_environment(),
    removed_env={name for name in PROVIDER_KEY_VARIABLES.values() if name},
)
registry.register(ShellTool(shell, area, on_cancel=shell.terminate_running))
prefix = Message(role=Role.SYSTEM, content=environment_notice(platform.system(), shell.interpreter_name))
```

- `bootstrap.py` hace este cableado: `Composition.history_prefix` lleva el mensaje de sistema con el sistema operativo y el intérprete, y `run_session` abre cada conversación con él.
- `on_cancel` termina el árbol de procesos si se cancela la llamada (Ctrl-C); el puerto `Shell` es síncrono y no tiene cancelación propia (hallazgo para A).
- `denied_commands_for("bash" | "powershell")` publica la lista por defecto de comandos peligrosos **solo como dato**: ni el shell ni la herramienta la aplican. La consume HU-05-02 (análisis de comandos compuestos); la aprobación interactiva es de HU-05-03.
- `process_environment()` (`config.py`) es la única lectura del entorno del proceso para el shell: ni `bootstrap.py` ni los adaptadores leen `os.environ`.

### HU-11-01: tarea con criterios protegidos

```python
from harness_agent.adapters.tasks import load_github_issue, load_task_file
from harness_agent.bootstrap import compose

task = load_task_file("tarea.md")                      # o load_github_issue(14)
composition = compose(config, task=task)               # la sesión de la tarea es la de la ejecución
composition.task_store.get_pending(composition.session_id)
composition.task_store.mark_passes(criteria_id, "salida de pytest: 0 fallos")  # exige evidencia
composition.task_store.verify_export(composition.session_id)  # restaura la copia si la tocaron
```

- Los criterios viven en SQLite (`criterios`); `tareas/<sesión>/criterios.json` es solo una copia de solo lectura con huella. Si cambia, `verify_export` la restaura y emite `criteria_tampered` con el motivo (sin contenido ni rutas).
- `ProtectedPolicy` solo puede endurecer: deniega lo que toque la carpeta del harness y delega el resto. Para `shell` es coincidencia literal con el nombre de la base, de la copia o de la carpeta; no analiza comandos compuestos (HU-05-02) ni sustituye al entorno aislado (PD-06).
- Una historia que añada una herramienta con `path` queda protegida sin cambios; una con varias rutas debe declararlas todas en `path` o aportar su propia comprobación.

---

## 4. Reglas Obligatorias de Diseño y Pureza

1. **Firmas asíncronas (propuesta SPK-02 / D-01, pendiente de aprobación)**: `Provider.complete`, `Tool.run` y `Approver.request` son corutinas (`async def`) y siguen siendo provisionales hasta que A, B y C aprueben D-01 y HU-00-01 (T016). El spike midió en Windows una cancelación con retorno de control de 1.0 a 2.4 ms (límite de AC-01: 500 ms); la evidencia en Linux existe en WSL2 Ubuntu local (0.7 a 1.4 ms; escalamiento `SIGTERM` → `SIGKILL` con un hijo real, véase `docs/decisiones/D-01-asyncio-cancelacion.md` y SPK-02 en `docs/PROGRESO.md`), pero no es un runner de GitHub Actions: aún no hay una ejecución registrada en la CI de `ubuntu-latest` para el spike. Todas las demás interfaces (`SessionStore`, `MemoryStore`, `ContextManager`, `AuthorizedArea`) son síncronas (`def`).
2. **Pureza del Núcleo (AC-02)**: Ningún módulo bajo `src/harness_agent/core/` puede importar SDKs de proveedores (`openai`, `anthropic`, `litellm`, `google-genai`). Las implementaciones concretas residen en `src/harness_agent/adapters/`.
3. **Inmutabilidad**: `Message`, `ToolCall`, `ToolResult`, `TokenUsage` y `Event` son `@dataclass(frozen=True)`. No intentar mutar sus atributos en tiempo de ejecución.
4. **Verificación Continua**: Antes de abrir un PR, ejecutar:
   ```powershell
   ruff format --check .
   ruff check .
   mypy src tests
   pytest
   ```
