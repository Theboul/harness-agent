# Contract: Async Tool Cancellation Protocol (SPK-02)

**Feature**: `specs/003-async-cancellation-spike/spec.md`  
**Date**: 2026-10-17 (alineado con el prototipo tras la auditoría)  
**Status**: Experimental Contract (Spike) — no es un contrato de producción ni modifica los contratos de HU-00-01  

---

## 1. Definición del Protocolo de Cancelación

El protocolo describe lo que implementa el prototipo de `tests/spikes/test_async_cancellation_spike.py`. Las firmas son las reales del prototipo.

```python
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Protocol


class OperationStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    FAILED = "failed"


@dataclass(frozen=True)
class OperationResult:
    status: OperationStatus
    return_code: int | None
    duration_ms: float
    output: str
    error_message: str | None = None


class ProcessLike(Protocol):
    """Subconjunto de asyncio.subprocess.Process que usa el algoritmo de cancelación."""

    @property
    def pid(self) -> int: ...
    @property
    def returncode(self) -> int | None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    async def wait(self) -> int: ...


class CancellableOperation(Protocol):
    """Operación o subproceso cancelable."""

    async def execute(self) -> tuple[int | None, str]:
        """Inicia la operación y espera su término. Devuelve (código de salida, salida)."""
        ...

    async def cancel(self, grace_period_s: float | None = None) -> None:
        """Parada en dos fases: terminate -> gracia acotada -> kill -> wait."""
        ...

    def is_alive(self) -> bool:
        """Indica si el proceso subyacente sigue activo."""
        ...
```

`SpikeLoop.run_operation(op, timeout=None, reraise_cancel=False) -> OperationResult` traduce el desenlace a un estado:

| Desenlace | Estado | Código de salida |
|---|---|---|
| Código 0 | `COMPLETED` | 0 |
| Código distinto de 0 | `FAILED` | el del proceso |
| `TimeoutError` | `TIMEOUT` | el observado tras la limpieza (Windows: 1) |
| `CancelledError` | `CANCELLED` | el observado tras la limpieza (Windows: 1) |

---

## 2. Comportamiento ante Excepciones y Ciclo de Parada

1. **La limpieza es independiente de quien cancela.** Se ejecuta como tarea propia y el llamador la espera dentro de un bucle de `asyncio.shield` que absorbe las cancelaciones adicionales y reanuda la espera hasta que la tarea termina (`complete_cleanup`). `shield` solo no basta: devuelve el control al llamador en cuanto llega la segunda cancelación (control V17), y esperar `op.cancel()` directamente se interrumpe antes de `kill` (control V16).
2. **Post-condición**: tras `complete_cleanup(op)`, `op.proc.returncode` no es `None` y `op.is_alive()` es `False`.
3. **`CancelledError`**:
   - `reraise_cancel=False` (por defecto, **solo experimento**): se absorbe y se devuelve `CANCELLED`. La tarea parece terminar con normalidad y queda `Task.cancelling() == 1` (V21).
   - `reraise_cancel=True`: la limpieza termina y se vuelve a lanzar `CancelledError`; la tarea queda cancelada (V20). **Producción debe usar esta semántica.**
4. **Fuera de alcance**: Ctrl+C, persistencia del evento de interrupción y reanudación de sesión (HU-06-03); árboles de procesos (HU-01-04); limpieza que no termina ni tras `kill` (no cubierta).
