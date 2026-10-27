# Data Model: HU-05-02

Todos los tipos del núcleo son `@dataclass(frozen=True)` en `core/permissions/` y solo usan la biblioteca estándar. No hay tablas nuevas ni cambios en SQLite.

## `Dialect` (`core/permissions/command_parser.py`)

`str, Enum`: `BASH = "bash"`, `POWERSHELL = "powershell"`. Coincide con `interpreter_name` del shell (HU-01-04), que lo da `bootstrap.py`.

## `CommandPart`

Una parte de un comando, tras separar por los separadores del dialecto.

| Campo | Tipo | Regla |
|---|---|---|
| `program` | `str` | Normalizado: sin envoltorios, sin carpeta ni extensión; en PowerShell, en minúsculas y con el alias resuelto. Vacío si no se pudo identificar |
| `arguments` | `tuple[str, ...]` | Tokens sin comillas, sin las redirecciones, en orden |
| `options` | `frozenset[str]` | Opciones normalizadas (cortas expandidas; largas traducidas por sinónimos; PowerShell en minúsculas) |
| `positionals` | `tuple[str, ...]` | Argumentos que no son opciones (tras `--` todo es posicional) |
| `redirect_targets` | `tuple[str, ...]` | Destinos de redirección, sin comillas |
| `quoted` | `frozenset[int]` | Índices de `arguments` que iban entre comillas (datos: no se buscan en la lista) |

## `ParsedCommand`

| Campo | Tipo | Significado |
|---|---|---|
| `parts` | `tuple[CommandPart, ...]` | Partes entendidas al nivel superior |
| `executable` | `tuple[ParsedCommand, ...]` | Textos que se ejecutan y se pudieron analizar (sustituciones, `-c`, `-Command`, `/c`), cada uno con su propio análisis |
| `understood` | `bool` | `False` si algo no se entendió aquí o en un texto ejecutable, o si hubo una sustitución u otro intérprete (R4) |

`parse_command(text: str, dialect: Dialect, *, aliases, synonyms) -> ParsedCommand` es pura: no lanza ante texto malformado (lo marca como no entendido) y solo lanza `TypeError` ante tipos indebidos.

## `RuleKind` y `CompiledRule` (`core/permissions/command_rules.py`)

`RuleKind`: `PROGRAM`, `TARGET`, `PREFIX`, `SUBCOMMAND`, `REDIRECT`, `LITERAL` (research R2).

| Campo | Tipo | Regla |
|---|---|---|
| `kind` | `RuleKind` | Se deduce del patrón |
| `program` | `str` | Normalizado como en `CommandPart` (vacío en `REDIRECT` y `LITERAL`) |
| `options` | `frozenset[str]` | Opciones requeridas (`TARGET`) |
| `words` | `tuple[str, ...]` | Subcomando requerido (`SUBCOMMAND`) o prefijo (`PREFIX`: un elemento que termina en `=`) |
| `text` | `str` | Prefijo del destino (`REDIRECT`) o fragmento sin espacios (`LITERAL`) |
| `reason` | `str` | Motivo en español; no se publica |

`compile_rule(pattern, reason, dialect, *, aliases, synonyms, allow_literal) -> CompiledRule`:

- lanza `RuleError` (sin repetir el patrón) si el patrón está vacío;
- lanza `RuleError` si el patrón no se entiende y `allow_literal` es falso (las entradas de `deny_commands`);
- lanza `RuleError` si tiene más de una parte;
- lanza `RuleError` si es un `TARGET` sin objetivo completo.

`CompiledRule.matches(part: CommandPart) -> bool`, para todos los tipos salvo `LITERAL`, y `CompiledRule.matches_text(text) -> bool` solo para `LITERAL`.

## `DenyList`

`DenyList(dialect, base: Sequence[CompiledRule], extra: Sequence[CompiledRule] = (), *, aliases: Mapping[str, str], synonyms: Mapping[str, Mapping[str, str]])`:

- inmutable: guarda tuplas y `MappingProxyType`;
- **no tiene ninguna operación para quitar entradas**;
- `base` no puede estar vacía (`ValueError`), porque una lista sin base falla cerrada;
- `rules` es `base + extra`.

`DenyList.denies(parsed: ParsedCommand, raw: str) -> bool` busca en las partes, en los textos ejecutables (recursivamente) y en los destinos de redirección. Las reglas `LITERAL` se buscan en `raw`. No busca en los argumentos entre comillas de las partes (FR-005a).

## `CommandPolicy` (`core/permissions/command_policy.py`)

`CommandPolicy(inner: PermissionPolicy, deny_list: DenyList, *, tool: str, argument: str)` implementa `PermissionPolicy`. No guarda estado entre llamadas.

| Situación | Resultado |
|---|---|
| Llamada a otra herramienta | `inner.evaluate(call)` sin cambios (con `DENY` ante una excepción o un valor raro) |
| Argumento ausente o no texto | se trata como «no entendido»: `ASK` como mínimo (o lo que diga `inner` si es `DENY`) |
| `deny_list.denies(...)` | `DENY`, sin consultar a `inner` |
| Excepción del analizador | «no entendido» |
| `inner` → `DENY` | `DENY` |
| `inner` → `ASK` | `ASK` |
| `inner` → `ALLOW` y entendido | `ALLOW` (es la decisión de `inner`, nunca creada aquí) |
| `inner` → `ALLOW` y no entendido | `ASK` |
| `inner` lanza o devuelve otro valor | `DENY` |

## Datos en `adapters/system/denied_commands.py` (ampliado)

- `DeniedCommand(pattern, reason)`: sin cambios de forma.
- `DEFAULT_DENIED_COMMANDS`: ampliado (research R12).
- Nuevos, de solo lectura: `PROGRAM_ALIASES: MappingProxyType[str, MappingProxyType[str, str]]` (por intérprete) y `OPTION_SYNONYMS: MappingProxyType[str, MappingProxyType[str, MappingProxyType[str, str]]]` (intérprete → programa → opción larga → corta), con sus funciones `program_aliases_for(interpreter)` y `option_synonyms_for(interpreter)`.

## `HarnessConfig.deny_commands` (`config.py`, aditivo)

`tuple[str, ...] = ()`. Se lee de `[permissions] deny_commands` (contrato en `contracts/deny_commands_config_contract.md`).

## Relaciones

```text
adapters/system/denied_commands.py ──(datos)──┐
config.toml [permissions] deny_commands ──────┤  bootstrap.compose()
                                               ▼
     compile_rule(...) × N  ──▶  DenyList(dialect, base, extra, aliases, synonyms)
                                               ▼
ProtectedPolicy( CommandPolicy( ExactCallPolicy( DefaultPermissionPolicy ) ), … ) ──▶ AgentLoop
```
