# Contrato: recorte general de salidas de herramientas (HU-02-02)

API pública nueva de `harness_agent.core` (no hay puertos ni eventos nuevos).

```python
DEFAULT_MAX_OUTPUT_CHARS: int   # 24_000
MIN_MAX_OUTPUT_CHARS: int       # 256
def omission_notice(omitted: int) -> str: ...
def truncate_output(text: str, max_chars: int) -> str: ...
def check_max_output_chars(value: object) -> int: ...      # ValueError (español, sin el valor)
class TruncatingTool(Tool):
    def __init__(self, inner: Tool, max_chars: int) -> None: ...

class InMemoryToolRegistry(ToolRegistry):
    def __init__(self, *, max_output_chars: int | None = None) -> None: ...
```

## Garantías

1. `truncate_output(t, m)` devuelve `t` (misma instancia) si `len(t) <= m`.
2. Si `len(t) > m`: `len(resultado) <= m`; empieza con `t[:h]`, termina con `t[-k:]` (`h`, `k` > 0) y contiene exactamente una vez `omission_notice(len(t) - h - k)`.
3. El conteo es en caracteres de Python; no se parte ningún carácter.
4. `TruncatingTool.run` no altera `call_id` ni `is_error`, no captura excepciones ni cancelación y no modifica `args`.
5. Con `max_output_chars=None`, `registry.get(n)` devuelve la instancia registrada. Con máximo, devuelve un `Tool` con los mismos `name`, `description`, `schema` y `risk`.
6. `bootstrap.compose()` crea el registro con `config.limits.max_tool_output_chars`.

## Convivencia con otros acotados

| Origen | Límite del cuerpo | Cabecera | Pasa por el registro con el máximo por defecto |
|---|---|---|---|
| `ShellTool` | 20 000 (`MAX_OUTPUT_CHARS`, marca propia) | `[codigo_de_salida=N] …` / `[tiempo_agotado] …` / `Código de salida: 0` | Intacta (≤ 24 000) |
| `listar_archivos`, `buscar_texto` | 20 000 (`MAX_RESULT_CHARS`) | etiquetas cortas | Intactas |
| `leer_archivo` | sin recorte propio hasta 262 144 bytes | — | Recortada con marca si supera 24 000 |
