# Contrato: el orden del contexto, el corte seguro y la ventana reciente

## Orden del contexto tras compactar

```text
1. los mensajes SYSTEM iniciales (prefijo estable)         ┐ cabeza protegida
2. la petición inicial del usuario (primer USER no externo) ┘
3. el resumen (un solo USER externo, enmarcado)
4. los mensajes recientes, íntegros y en su orden
```

La cabeza protegida y la ventana reciente son **idénticas** a las de antes de compactar (mismos objetos, mismo orden). Las herramientas declaradas no forman parte de los mensajes y no cambian.

## API (`harness_agent.core`)

```python
def split_history(history: Sequence[Message]) -> HistoryParts | None: ...
def is_real(message: Message) -> bool: ...
def choose_cut(history, region_start: int, budget_tokens: int, min_messages: int) -> int | None: ...
```

- `split_history`: `head_end` es el índice del primer mensaje que no es cabeza (justo después de la petición inicial); si ahí hay un resumen (`is_summary`), `summary_index = head_end` y `region_start = head_end + 1`; si no, `summary_index = None` y `region_start = head_end`. Devuelve `None` si aún no hay petición inicial.
- `is_real`: falso para `SYSTEM` y para `USER` con `is_external`.
- `choose_cut`: determinista y total (nunca lanza).

## Reglas del corte (`choose_cut`)

1. **Ventana reciente**: se acumulan mensajes desde el final mientras la estimación acumulada no supere `budget_tokens`, y siempre al menos `min_messages`; el corte deseado es `len(history) - n`.
2. **Corte seguro**: mientras `history[corte]` sea un resultado de herramienta (`Role.TOOL`), el corte retrocede un mensaje. Así, una llamada del asistente y **todos** sus resultados quedan juntos del lado reciente.
3. Si el corte resultante es menor o igual que `region_start`, no hay nada por resumir: devuelve `None`.
4. El corte nunca queda dentro de la cabeza protegida ni separa el resumen anterior de su posición.

## Ejemplos normativos (mensajes de `H`, con `min_messages = 4` y un presupuesto que no obliga a más)

`H` = `[0 SYSTEM entorno, 1 USER petición, 2 ASSISTANT llamada c1, 3 TOOL c1, 4 ASSISTANT llamadas c2 y c3, 5 TOOL c2, 6 TOOL c3, 7 ASSISTANT, 8 USER, 9 ASSISTANT, 10 USER, 11 ASSISTANT]`, `region_start = 2`.

| Caso | Corte deseado | Corte final | Región a resumir | Contexto resultante |
|---|---|---|---|---|
| E1: cuatro recientes | 8 (`H[8]` es `USER`) | 8 | 2 a 7 (6 mensajes) | `[0, 1, S, 8, 9, 10, 11]` |
| E2: el corte caería sobre un resultado | 6 (`H[6]` es `TOOL`) | 4 (retrocede 6 → 5 → 4; `H[4]` es `ASSISTANT`) | 2 y 3 (2 mensajes) | `[0, 1, S, 4, 5, 6, 7, 8, 9, 10, 11]` |
| E3: nada antiguo | `H' = [0 … 5]`, deseado 2 | 2 ≤ `region_start` | — | no se compacta (`None`) |
| E4: segunda compactación | `H'' = [0 SYSTEM, 1 USER petición, 2 S, 3 USER, 4 ASSISTANT, 5 USER, 6 ASSISTANT, 7 USER, 8 ASSISTANT, 9 USER, 10 ASSISTANT]`, `region_start = 3` (hay resumen), `len = 11`, deseado 7 | 7 (`H''[7]` es `USER`) | 3 a 6 más el texto de `S` como resumen anterior | `[0, 1, S', 7, 8, 9, 10]` |

(`S` es el resumen enmarcado; `S'` el nuevo, que reemplaza a `S`.)

## Garantías (las vigilan la tabla y la prueba al azar con semilla 20261031)

- Para cualquier historial válido, el contexto resultante **no tiene** un `TOOL` sin su llamada del asistente.
- La ventana reciente tiene al menos `min_messages` mensajes (o todos los que haya).
- Los mensajes recientes del resultado son los mismos objetos, en el mismo orden, que el sufijo del historial.
- La cabeza protegida es idéntica; hay como máximo un resumen y va justo después de la petición inicial.
- La misma entrada da siempre la misma salida.
