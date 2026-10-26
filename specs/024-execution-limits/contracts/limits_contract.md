# Contrato: límites de sesión (HU-01-06)

## API pública nueva de `harness_agent.core`

```python
class LimitKind(str, Enum): TURNS; TIME; TOKENS
class InvalidLimitsError(ValueError): ...
@dataclass(frozen=True) class SessionLimits: max_turns: int; max_seconds: int; max_tokens: int
@dataclass(frozen=True) class LimitReached: kind: LimitKind; used: int; maximum: int
class LimitTracker:
    def __init__(self, limits: SessionLimits, clock: Callable[[], float] | None = None) -> None
    def begin_task(self) -> None
    def end_task(self) -> None            # idempotente
    def start_turn(self) -> None
    def add_usage(self, usage: TokenUsage | None) -> None
    def reached(self) -> LimitReached | None
```

## `AgentLoop` (cambio aditivo)

`AgentLoop(provider, registry, policy, bus, approver=None, *, limits: SessionLimits | None = None, clock=None)`.
Sin `limits` el comportamiento es el de hoy. Con `limits`: antes de cada llamada al modelo, `tracker.reached()`; si no es `None` → publica `LIMIT_REACHED` y devuelve `TurnResult(TurnStatus.LIMIT_REACHED, None, history, error)`.

## Evento `LIMIT_REACHED`

Carga: `{"limit": "turns"|"time"|"tokens", "used": int, "maximum": int}`. Se publica una vez por parada.

## CLI

`LIMIT_REACHED` → una línea `x Límite: <motivo>. Sugerencia: …` con el nombre del límite en español y su máximo; carga no reconocida → texto genérico previo.

## Composición

`compose(config)` → `SessionLimits(config.limits.max_turns, config.limits.max_seconds, config.limits.max_tokens)` al bucle. `max_output_tokens` y `max_tool_output_chars` no participan.
