# Quickstart & Verification Guide: SPK-02 — Modelo Asíncrono y Cancelación

**Feature**: `specs/003-async-cancellation-spike/spec.md`  
**Date**: 2026-10-17  
**Status**: Ready (ejecutado en Windows y en WSL2 Ubuntu local; el runner de GitHub Actions sigue pendiente)  

---

## 1. Guía de Ejecución Rápida

El prototipo experimental se estructura dentro de la suite de pruebas del proyecto (`tests/spikes/test_async_cancellation_spike.py`) para permitir su ejecución directa con `pytest` y `pytest-asyncio` sin alterar el código del núcleo.

### 1.1 Ejecución de las Pruebas del Spike

También existe `tests/spikes/test_concurrency_alternatives_spike.py` (comparación asyncio / hilos / procesos). Para imprimir sus mediciones: `python -m tests.spikes.test_concurrency_alternatives_spike`.

**En Windows (PowerShell):**
```powershell
.\.venv\Scripts\pytest -v tests/spikes/test_async_cancellation_spike.py
```

**En Linux (Bash)** (ejecutado en WSL2 Ubuntu con un `.venv` propio dentro del sistema de archivos de Linux, no en `/mnt/c`):
```bash
pytest -v -s tests/spikes
```

Las pruebas de `tests/spikes/test_linux_sigterm_spike.py` solo se ejecutan en Linux (en Windows se omiten) y con `-s` imprimen las líneas `[linux-evidence]` con tiempos y códigos de salida.

---

## 2. Escenarios de Validación Cubiertos

| # | Escenario | Comportamiento Esperado | Criterio Validador |
|---|---|---|---|
| **V1** | **Ejecución normal** | Tarea rápida finaliza exitosamente; el bucle obtiene resultado `COMPLETED` con código de salida 0. | Salida completa y código 0. |
| **V2** | **Cancelación activa** | Tarea de 5 s recibe señal a los ≈120 ms; finaliza en < 500 ms con estado `CANCELLED`. | Duración $< 500\text{ ms}$, sin bloqueo. |
| **V3** | **Proceso terminado** | El subproceso asociado ya no existe en el sistema operativo tras la cancelación. | `proc.returncode is not None` y PID no activo. |
| **V4** | **Retorno del control** | El bucle captura `CancelledError` y recupera la ejecución de inmediato. | Flujo de ejecución continúa secuencialmente. |
| **V5** | **Ejecución posterior** | Inmediatamente tras la cancelación, el bucle lanza una segunda operación exitosa. | Segunda operación retorna `COMPLETED` código 0. |
| **V6** | **Timeout controlado** | Operación supera el tiempo límite fijado; el bucle la cancela automáticamente. | Retorna estado `TIMEOUT` y libera el proceso. |
| **V7** | **Limpieza de recursos** | Tras 3 cancelaciones consecutivas no quedan PIDs directos vivos. | Verificación de PID cerrado en el SO (Windows ejecutado). |
| **V8-V9** | **Cancelación antes de iniciar** | No se crea ningún proceso, o el creado queda terminado. | `task.cancelled()` / `returncode` definido. |
| **V10-V11** | **Finalización previa a la cancelación** | Una cancelación tardía no cambia el resultado ni el código de salida. | `COMPLETED`, código 0. |
| **V12-V14** | **Hijo que ignora `terminate`** | Escalamiento `terminate` a `kill` (doble controlado), sin `kill` si es cooperativo, tolerancia a `ProcessLookupError`. | Secuencia de llamadas del doble. |
| **V15-V17** | **Segunda cancelación durante la limpieza** | La limpieza termina el proceso; los controles negativos muestran por qué `shield` solo no basta. | `returncode == -9` en el doble. |
| **V18** | **Bucle activo durante la limpieza** | El bucle sigue ejecutando ticks y acepta otra operación después. | Ticks ≥ 5 y siguiente turno `COMPLETED`. |
| **V19** | **Cuatro resultados** | `COMPLETED`, `FAILED`, `CANCELLED` y `TIMEOUT` se distinguen y no queda ningún PID vivo. | Estados y códigos de salida. |
| **V20-V21** | **Semántica de `CancelledError`** | Re-lanzamiento tras la limpieza frente a absorción experimental. | `task.cancelled()` / `task.cancelling()`. |
| **L1-L5** | **`SIGTERM` ignorado (solo Linux)** | Control; escalamiento a `SIGKILL`; cancelaciones repetidas durante la gracia; timeout; 5 ciclos sin PID vivo ni zombi. | Código de salida -9 y PID ausente (`ProcessLookupError`). |
| **V22** | **Handles** | El conteo de handles/descriptores no crece tras 5 ciclos de cancelación. | Delta ≤ 2 (Windows: 162 antes y 162 después; WSL2 Ubuntu: 8 antes y 8 después, en mediciones de diagnóstico). |

---

## 3. Comprobación Manual / Diagnóstico de Procesos

Para verificar empíricamente que no quedan procesos Python huérfanos tras ejecutar las pruebas:

**En Windows (PowerShell):**
```powershell
Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $PID }
```

**En Linux (Bash):**
```bash
ps aux | grep "[p]ython" | grep -v "$$"
```
