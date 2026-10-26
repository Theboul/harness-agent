# Data Model: HU-01-06

Sin persistencia (el estado de los contadores vive en el `AgentLoop` de la sesión). Todo en `core/limits.py`.

| Tipo | Campos | Reglas |
|---|---|---|
| `LimitKind` (`str`, Enum) | `TURNS="turns"`, `TIME="time"`, `TOKENS="tokens"` | Valores = clave de la carga del evento |
| `SessionLimits` (frozen) | `max_turns: int`, `max_seconds: int`, `max_tokens: int` | Enteros (no `bool`) > 0; si no, `InvalidLimitsError` (español, sin el valor) |
| `LimitReached` (frozen) | `kind: LimitKind`, `used: int`, `maximum: int` | Resultado de `reached()` |
| `LimitTracker` | `turns`, `tokens`, `seconds_elapsed` (propiedades de lectura) | Estado mutable privado; no es dato compartido |

## Transiciones del `LimitTracker`

`begin_task()` → (`start_turn()` → `add_usage(usage)`)* → `end_task()`. `reached()` puede consultarse en cualquier momento:
orden fijo `TURNS` (turnos hechos ≥ `max_turns`), `TIME` (acumulado + tarea en curso ≥ `max_seconds`), `TOKENS` (consumo ≥ `max_tokens`). Una vez cumplido un límite sigue cumplido (los contadores solo crecen).

## Eventos

`LIMIT_REACHED` (ya en el catálogo) con carga `{"limit": str, "used": int, "maximum": int}`. Sin cambios en `core/events.py`.
