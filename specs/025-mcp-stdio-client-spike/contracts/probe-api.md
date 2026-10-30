# Contrato del apoyo de prueba: `tests/spikes/mcp_probe.py`

No es una API pública del proyecto; documenta la forma del apoyo para las pruebas.

```python
@asynccontextmanager
async def open_session(server: ProbeServer, *, read_timeout_s: float | None = None,
                       errlog: TextIO | None = None) -> AsyncIterator[ClientSession]: ...

async def handshake(session: ClientSession) -> Handshake: ...   # no timing field: the tests measure time themselves
async def list_tools(session: ClientSession) -> list[ListedTool]: ...
async def call(session: ClientSession, name: str, arguments: dict[str, Any], *,
               timeout_s: float | None = None) -> CallOutcome: ...   # per-call timeout
def leaf_exceptions(error: BaseException) -> list[BaseException]: ...   # flattens ExceptionGroup
def demo_server() -> ProbeServer: ...      # sys.executable + mcp_demo_server.py
def process_alive(pid: int) -> bool: ...   # sin dependencias nuevas, Windows y POSIX
```

Reglas: `errlog` captura el stderr del servidor para que no ensucie la salida de pytest; ningún valor de configuración sale en mensajes; los tiempos se pasan por parámetro.
