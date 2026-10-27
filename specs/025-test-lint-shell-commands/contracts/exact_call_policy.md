# Contrato: `ExactCallPolicy` y su cableado

## API pública (`harness_agent.core`)

```python
@dataclass(frozen=True)
class AllowedCall:
    tool: str
    argument: str
    value: str            # guardado sin espacios exteriores
    limit_argument: str
    limit: int | float
    default_limit: int | float
    def matches(self, call: ToolCall) -> bool: ...

class ExactCallPolicy(PermissionPolicy):
    def __init__(self, inner: PermissionPolicy, allowed: Sequence[AllowedCall],
                 *, ask_names: Sequence[str] = ()) -> None: ...
    def evaluate(self, call: ToolCall) -> PermissionDecision: ...
```

## Garantías

1. **Solo endurece o permite lo exacto**: el resultado es `ALLOW` únicamente si `inner` devolvió `ALLOW`, o si devolvió `ASK`, la herramienta no está en `ask_names` y alguna `AllowedCall.matches(call)` es `True`.
2. **Coincidencia** (todas las condiciones):
   - `call.name == tool`;
   - `set(call.arguments) ⊆ {argument, limit_argument}`;
   - `call.arguments[argument].strip() == value`;
   - el tiempo efectivo (`call.arguments.get(limit_argument, default_limit)`) es numérico no booleano, finito, > 0 y ≤ `limit`.
3. **Falla cerrada**: una excepción de `inner`, un valor que no es `PermissionDecision` o un error al comparar → `DENY`. Una `ToolCall` mal formada no coincide.
4. **Sin estado**: no guarda nada entre llamadas y solo recibe la llamada.
5. **No conoce el shell**: el módulo no contiene los literales `"shell"`, `"command"` ni `"timeout_seconds"` (lo vigila `tests/architecture/test_exact_calls_boundaries.py`).

## Cableado en `bootstrap.compose()`

```text
allowed = tuple(
    AllowedCall(tool=shell_tool.name, argument=COMMAND_ARGUMENT, value=c.command,
                limit_argument=TIMEOUT_ARGUMENT, limit=c.timeout_seconds,
                default_limit=DEFAULT_SHELL_TIMEOUT_SECONDS)
    for c in (task.commands if task else ()))
policy = ProtectedPolicy(
    ExactCallPolicy(DefaultPermissionPolicy(registry, area, config.permissions),
                    allowed, ask_names=config.permissions.ask),
    protected, markers)
history_prefix = (environment_notice, *([Message(SYSTEM, commands_notice(...))] if commands else []))
```

Sin tarea o sin comandos, `allowed == ()` y la decisión es idéntica a la de antes de esta historia (SC-004). `COMMAND_ARGUMENT = "command"` y `TIMEOUT_ARGUMENT = "timeout_seconds"` se definen en `adapters/tools/shell.py`, se usan en su esquema y se exportan en `adapters.tools`.

## Cargas de eventos

Sin eventos nuevos. `PERMISSION_DECIDED` sigue sin llevar argumentos: el comando no aparece en ningún evento ni en ningún mensaje de error.
