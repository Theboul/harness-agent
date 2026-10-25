# Contrato: `harness_agent.bootstrap` y el comando

La raíz de composición es la única superficie nueva. No cambia ningún puerto ni evento.

## API pública (`harness_agent.bootstrap`)

```python
EXIT_STARTUP: int = 2
EXIT_INTERRUPTED: int = 130

ProviderFactory = Callable[[HarnessConfig], Provider]

class StartupError(Exception): ...   # decisión del usuario que impide arrancar (p. ej. modelo fake/…)

@dataclass(frozen=True)
class Composition:
    loop: AgentLoop
    bus: EventBus
    store: SqliteSessionStore
    session_id: str
    notices: tuple[str, ...]
    def close(self) -> None: ...

def compose(
    config: HarnessConfig,
    *,
    provider_factory: ProviderFactory | None = None,
    clock: Callable[[], datetime] | None = None,
    id_factory: Callable[[], str] | None = None,
) -> Composition: ...

async def run_session(
    composition: Composition,
    *,
    input_stream: TextIO | None = None,
    output: TextIO | None = None,
) -> int: ...

def main(
    *,
    environ: Mapping[str, str] | None = None,
    config_path: str | os.PathLike[str] | None = None,
    input_stream: TextIO | None = None,
    output: TextIO | None = None,
    error: TextIO | None = None,
    provider_factory: ProviderFactory | None = None,
    clock: Callable[[], datetime] | None = None,
    id_factory: Callable[[], str] | None = None,
) -> int: ...
```

Los valores `None` significan «el real»: `sys.stdin`, `sys.stdout`, `sys.stderr`, `os.environ` (vía `load_config`), reloj UTC e identificadores `uuid4` (vía el almacén), `LiteLLMProvider` para el proveedor.

## Imports permitidos de `bootstrap.py`

Solo biblioteca estándar, `harness_agent.core` (nombres de `__all__`), `harness_agent.config`, `harness_agent.cli` y la API pública de `harness_agent.adapters.storage`, `.system` y `.tools`. Dos submódulos están **autorizados de forma explícita** porque no existe vía pública: `harness_agent.core.loop` (`AgentLoop`) y `harness_agent.adapters.providers.litellm_provider` (`LiteLLMProvider`, `ProviderDependencyError`). La guarda `test_bootstrap_boundaries.py` rechaza cualquier otro submódulo.

## Comando

| Forma | Efecto |
|---|---|
| `python -m harness_agent` | `raise SystemExit(main())` |
| `harness` (tras `pip install -e .`) | `[project.scripts] harness = "harness_agent.bootstrap:main"` |

Sin argumentos ni opciones. La ruta de la configuración se elige con `HARNESS_CONFIG` (regla de HU-00-04).

## Cableado (qué se conecta con qué)

| Pieza | Entrada desde la configuración |
|---|---|
| `LiteLLMProvider` | `config.model`, `config.limits.max_output_tokens`, `config.api_key` |
| `WorkspaceArea` | `config.paths.workspace_root` (ausente o no carpeta → sin área + aviso) |
| `ReadFileTool`, `WriteFileTool`, `ListFilesTool`, `SearchTextTool` | el área (o `None`) |
| `InMemoryToolRegistry` | las 4 herramientas |
| `DefaultPermissionPolicy` | registro, área, `config.permissions` (solo `deny` y `ask`) |
| `InMemoryEventBus` | — |
| `SqliteSessionStore` | `config.paths.sessions_db`, reloj, `id_factory` |
| `attach_event_recorder` | bus, almacén |
| `AgentLoop` | proveedor, registro, política, bus |
| `run_cli` | bus, `run_turn`, flujos |

`config.limits.max_turns`, `max_seconds` y `max_tokens` no se usan hasta HU-01-06.

## Códigos de salida

| Código | Cuándo |
|---|---|
| 0 | `/salir` o fin de entrada |
| 1 | un turno falló con una excepción ordinaria (lo decide `run_cli`) |
| 2 | fallo de arranque |
| 130 | interrupción de teclado |

## Mensajes (todos en español, una línea, sin valores recibidos)

| Situación | Salida (flujo) |
|---|---|
| Error de configuración o de clave | `No se pudo iniciar: <texto del ConfigError>` (error) |
| Falta la dependencia del proveedor | `No se pudo iniciar: <texto de ProviderDependencyError>` (error) |
| Base ilegible o de otro esquema | `No se pudo iniciar: <texto de SessionStoreError>` (error) |
| Modelo `fake/…` con el proveedor por omisión | `No se pudo iniciar: El proveedor 'fake' solo existe para pruebas y no se puede usar con el comando; elija un modelo real en config.toml (por ejemplo <proveedor>/<modelo>).` (error) |
| Cualquier otra excepción al arrancar | `No se pudo iniciar: error inesperado (<Tipo>).` (error) |
| Sin `workspace_root` | `Aviso: no hay área de trabajo configurada (paths.workspace_root); las herramientas de archivos están desactivadas.` (salida, antes del prompt) |
| `workspace_root` que no es una carpeta | `Aviso: el área de trabajo configurada no es una carpeta; las herramientas de archivos están desactivadas.` (salida, antes del prompt) |
| Interrupción | sin mensaje de traza; la línea de cierre de la CLI no se garantiza |

## Garantías comprobables

- Ninguna salida (salida, error, base de datos) contiene el valor de la clave (prueba con centinela).
- Ninguna excepción llega al usuario como traza desde `main`.
- Tras `main`, el almacén está cerrado en todos los caminos.
- Los eventos guardados coinciden en número y orden con los que vio la terminal.
