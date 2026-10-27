# Contrato: `CommandPolicy`, `DenyList` y el analizador de comandos

## API pública (`harness_agent.core`)

```python
class Dialect(str, Enum): BASH = "bash"; POWERSHELL = "powershell"

def parse_command(text: str, dialect: Dialect, *, aliases: Mapping[str, str] = {},
                  synonyms: Mapping[str, Mapping[str, str]] = {}) -> ParsedCommand: ...

class RuleError(ValueError): ...           # mensaje fijo, sin el patrón
def compile_rule(pattern: str, reason: str, dialect: Dialect, *, aliases=..., synonyms=...,
                 allow_literal: bool = False) -> CompiledRule: ...

class DenyList:
    def __init__(self, dialect: Dialect, base: Sequence[CompiledRule],
                 extra: Sequence[CompiledRule] = (), *, aliases=..., synonyms=...) -> None: ...
    def denies(self, parsed: ParsedCommand, raw: str) -> bool: ...

class CommandPolicy(PermissionPolicy):
    def __init__(self, inner: PermissionPolicy, deny_list: DenyList, *, tool: str,
                 argument: str) -> None: ...
    def evaluate(self, call: ToolCall) -> PermissionDecision: ...
```

## Garantías (las vigila la guarda `tests/architecture/test_command_policy_boundaries.py`)

1. **Solo endurece**: el módulo de la política nunca devuelve un `PermissionDecision.ALLOW` creado por él; solo puede devolver la decisión de `inner` o `DENY`/`ASK`. `ALLOW` aparece únicamente en una comparación con la decisión de `inner`.
2. **Deny > ask > allow**:
   - un comando denegado da `DENY` antes de consultar a `inner` (y por tanto a `ExactCallPolicy`);
   - `DENY` de `inner` se mantiene;
   - un comando no entendido nunca da `ALLOW`.
3. **Falla cerrada**:
   - excepción del analizador → «no entendido»;
   - excepción o valor raro de `inner` → `DENY`;
   - una `ToolCall` mal formada → `DENY`.
4. **Sin estado ni E/S**: en `command_rules.py` y `command_policy.py` ningún método salvo `__init__` asigna atributos de `self` (el analizador usa un objeto de escaneo que se crea en cada llamada a `parse_command` y no se comparte; ajuste de la implementación, T006). Los módulos no importan `adapters`, `config`, `cli`, `subprocess`, `socket`, `os`, `pathlib`, `shutil`, `shlex` ni ningún paquete de terceros, y no leen el entorno ni usan la terminal.
5. **No conoce la herramienta**: `command_rules.py` y `command_policy.py` no contienen los literales `"shell"`, `"command"` ni `"timeout_seconds"`, y `command_parser.py` no contiene `"shell"` ni `"timeout_seconds"`. El analizador sí reconoce la palabra `command`, que es el builtin `command` de bash y el parámetro `-Command` de PowerShell, no la herramienta (ajuste de la implementación, T006). La herramienta y su argumento llegan por constructor.
6. **Sin filtrar datos**: ni el texto del comando ni el patrón ni el motivo aparecen en una excepción, un evento ni un mensaje.
7. **Lista base inalterable**: `DenyList` no ofrece ninguna operación para quitar entradas, guarda tuplas inmutables y rechaza una base vacía.

## Cableado en `bootstrap.compose()`

```text
dialect   = Dialect(interpreter_for(system))
base      = [compile_rule(e.pattern, e.reason, dialect, ..., allow_literal=True)
             for e in denied_commands_for(dialect.value)]
extra     = [compile_rule(text, "Añadido por la configuración.", dialect, ...)
             for text in config.deny_commands]          # RuleError → StartupError (sin el texto)
deny_list = DenyList(dialect, base, extra, aliases=program_aliases_for(...),
                     synonyms=option_synonyms_for(...))
policy = ProtectedPolicy(
    CommandPolicy(
        ExactCallPolicy(DefaultPermissionPolicy(registry, area, config.permissions),
                        allowed, ask_names=config.permissions.ask),
        deny_list, tool=shell_tool.name, argument=COMMAND_ARGUMENT),
    protected, markers)
```

## Ejemplos normativos (también son pruebas)

| Dialecto | Comando | Resultado (con `inner` = `ASK`) |
|---|---|---|
| bash | `echo hola && rm -rf /` | `DENY` |
| bash | `rm -fr ~/*` · `sudo /sbin/shutdown -h now` · `env X=1 reboot` · `dd if=/dev/zero of=a.img` | `DENY` |
| bash | `echo $(shutdown now)` · `bash -c "rm -rf /"` · `echo hola > $(reboot)` | `DENY` |
| bash | `cat shutdown.log` · `echo "no uses shutdown"` · `git commit -m "fix: shutdown limpio"` · `rm -rf /tmp/build` | `ASK` |
| bash | `echo $(whoami)` · `bash -c "ls"` · `eval ls` · `rm -rf $HOME` · `echo "abc` | `ASK` (aunque `inner` diga `ALLOW`) |
| powershell | `dir \| Stop-Computer` · `ri -r -fo C:\` · `REMOVE-ITEM -Recurse -Force c:/*` · `pwsh -Command "Stop-Computer"` | `DENY` |
| powershell | `Get-Content Stop-Computer.txt` · `Remove-Item -Recurse -Force C:\proyecto\dist` | `ASK` |
| powershell | `iex "dir"` · `& $x` · `powershell -EncodedCommand AAAA` · `{ dir }` | `ASK` |
