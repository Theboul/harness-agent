# Data Model: HU-02-01

Todo en memoria, `@dataclass(frozen=True)` salvo el estimador y el ensamblador (estado por sesión).

## PrefixSpec

| Campo | Tipo | Regla |
|---|---|---|
| `instructions` | `str` | No vacío tras `strip()` |
| `rules` | `tuple[str, ...]` | Cada regla no vacía; puede ser vacía la tupla |
| `os_name` | `str` | No vacío |
| `interpreter` | `str` | No vacío |

Valores inválidos → `ContextConfigError` con mensaje fijo, sin reproducir el valor.

## StablePrefix

| Campo | Tipo | Notas |
|---|---|---|
| `system_message` | `Message` | `Role.SYSTEM`; texto = secciones en orden fijo |
| `tools` | `tuple[ToolDefinition, ...]` | Ordenadas por `name`; sin nombres duplicados ni vacíos |
| `fingerprint` | `str` | SHA-256 hexadecimal de `system_message.content` y las definiciones serializadas (JSON, claves ordenadas) |

Texto del mensaje (ilustrativo):

```text
## Instrucciones
<instructions>

## Reglas
- <regla 1>
- <regla 2>

## Entorno
Sistema operativo: <os_name>
Intérprete de comandos: <interpreter>
```

Sin reglas, la sección `## Reglas` se escribe con «(ninguna)» (la forma no cambia).

## AssembledContext

| Campo | Tipo | Notas |
|---|---|---|
| `prefix` | `StablePrefix` | El de la sesión |
| `history` | `tuple[Message, ...]` | Copia profunda del historial recibido |
| `raw_tokens` | `int` | Estimación sin calibrar |
| `estimated_tokens` | `int` | `ceil(raw × factor)` |
| `tools` (propiedad) | `tuple[ToolDefinition, ...]` | = `prefix.tools` |
| `provider_messages()` | `list[Message]` | `[system_message, *history]`, listo para `Provider.complete` |

## Calibración (por sesión, en `TokenEstimator`)

`factor: float` (inicial 1.0), `1/4 ≤ factor ≤ 4`.

## Transiciones

- `assemble(s, h)`: si no hay prefijo de `s`, construirlo y guardarlo; guardar `raw` como «última estimación cruda» de `s`.
- `record_usage(s, usage)`: si `usage` y la última cruda existen y `usage.input_tokens > 0`, `factor[s] = clamp(input / raw)`; la última cruda se consume (segunda llamada no hace nada).
