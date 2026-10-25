# Data Model: HU-02-02 — Recorte de salidas largas de herramientas

Sin persistencia ni entidades nuevas del dominio: `ToolResult` (`call_id`, `content`, `is_error`) no cambia.

## Constantes (`core/tools/output_limit.py`)

| Nombre | Valor | Uso |
|---|---|---|
| `DEFAULT_MAX_OUTPUT_CHARS` | 24 000 | Valor por defecto de `Limits.max_tool_output_chars` |
| `MIN_MAX_OUTPUT_CHARS` | 256 | Mínimo aceptado; deja sitio a la marca y a contenido útil |

## Funciones y clases

| Elemento | Firma | Reglas |
|---|---|---|
| `omission_notice(omitted: int) -> str` | pura | `"\n[salida recortada: se omitieron {omitted} caracteres]\n"` |
| `truncate_output(text: str, max_chars: int) -> str` | pura | `len(text) <= max_chars` → el mismo objeto; si no, `head + marca + tail`, `len <= max_chars`, `omitidos = len(text) - len(head) - len(tail)` exactos |
| `check_max_output_chars(value: object) -> int` | valida | Entero (no `bool`) `>= MIN_MAX_OUTPUT_CHARS`; si no, `ValueError` en español sin el valor |
| `TruncatingTool(inner: Tool, max_chars: int)` | `Tool` | `name`, `description`, `schema`, `risk` delegan en `inner` en cada lectura; `run(args)` espera `inner.run(args)` y recorta; no captura excepciones |

## Reglas de `TruncatingTool.run`

1. Si el resultado no es un `ToolResult` o su `content` no es `str`, se devuelve tal cual (el bucle lo rechaza como hoy).
2. Si `len(content) <= max_chars`, se devuelve el mismo objeto.
3. Si no, `dataclasses.replace(result, content=truncate_output(...))`: `call_id` e `is_error` intactos.

## Registro

`_Entry(tool, schema, served)`: `served` es `TruncatingTool(tool, max)` si el registro tiene máximo, o `tool`. `get(name)` → `entry.served`; `list()` → `[e.served …]`; `validate_args` y el orden de registro no cambian. El máximo se valida en el constructor con `check_max_output_chars` (si no es `None`).

## Configuración

`Limits.max_tool_output_chars: int = 24000`. En `config.toml`: `[limits] max_tool_output_chars = N`.
