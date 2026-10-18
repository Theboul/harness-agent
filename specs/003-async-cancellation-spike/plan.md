# Implementation Plan: SPK-02 — Spike: modelo asíncrono y cancelación de herramientas

**Branch**: `003-async-cancellation-spike` | **Date**: 2026-10-17 | **Spec**: [specs/003-async-cancellation-spike/spec.md](spec.md)  
**Responsable**: A — Núcleo | **Sprint**: Sprint 1 | **Estimación**: 1 PHU (~3 horas F5)  
**Input**: Feature specification from `specs/003-async-cancellation-spike/spec.md`  

---

## Summary

Diseñar y ejecutar un experimento controlado y reproducible para evaluar si HARNESS debe adoptar `asyncio` como modelo de concurrencia central y cómo debe implementarse la cancelación limpia de herramientas de larga duración. Se creará un prototipo de bucle aislado en `tests/spikes/test_async_cancellation_spike.py` que invocará subprocesos Python controlados con `sys.executable` y `asyncio.create_subprocess_exec`, comprobando la captura de `asyncio.CancelledError`, el retorno inmediato de control en $< 500\text{ ms}$, la ausencia de procesos huérfanos y la viabilidad de continuar con turnos posteriores. Como resultado del experimento se generará el informe formal de decisión técnica (Sp1-49) evaluando los impactos en `Provider`, `Tool`, `Approver`, `EventBus`, `MCP` y `SubagentRunner`.

---

## Technical Context

**Language/Version**: Python 3.12.x, única versión soportada (PD-07 aprobada por el Product Owner el 2026-10-17; antes había un conflicto 3.11+ frente a 3.12+, ver D-01 §7). Las pruebas solo se han ejecutado en 3.12.10.  
**Primary Dependencies**: Biblioteca estándar (`asyncio`, `sys`, `os`, `signal`, `dataclasses`). Sin dependencias externas adicionales.  
**Storage**: N/A (experimento en memoria y subprocesos de sistema operativo).  
**Testing**: `pytest==8.3.4` y `pytest-asyncio==0.25.3` (fijados en `requirements-dev.txt`).  
**Target Platform**: Windows (`win32` con `ProactorEventLoop`): ejecutado. Linux: ejecutado en WSL2 Ubuntu 26.04.1 local con señales POSIX reales (no es un runner de GitHub Actions); `ubuntu-latest` en la CI: pendiente.  
**Project Type**: Prototipo experimental y suite de pruebas automatizadas en `tests/spikes/`.  
**Performance Goals**: Cancelación confirmada y retorno de control en $< 500\text{ ms}$ (medido en Windows: 1.0 a 2.4 ms, n=10); 100% de subprocesos directos terminados sin PIDs vivos (Windows).  
**Constraints**: Aislamiento estricto (no contamina `src/harness_agent/core/`); sin llamadas de red ni modelos externos; sin comandos de shell arbitrarios (`shell=False`); duración estimada total de ~3 horas dividida en microtareas de menos de 60 minutos.  
**Scale/Scope**: 2 módulos de pruebas aislados en `tests/spikes/`: cancelación (22 escenarios V1-V22) y alternativas de concurrencia (4 experimentos), más 1 documento de decisión técnica pendiente de aprobación.  

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Estado | Justificación / Cumplimiento |
|---|---|---|
| **Principio I (1 historia por spec)** | **PASS** | Exclusivamente enfocado en SPK-02 (Sp1-48 y Sp1-49). |
| **Principio II (Microtareas < 60 min)** | **PASS** | T001-T005 de 25 a 35 min (155 min) y T006-T014 de la fase de corrección, cada una por debajo de 60 min. |
| **Principio III (Hexagonal y Python 3.12.x)** | **PASS (arquitectura y versión, PD-07)** | Prototipo aislado en `tests/spikes/`; no introduce acoplamiento en `core/` ni SDKs propietarios. El conflicto 3.11+ frente a 3.12+ quedó resuelto por PD-07 (D-01 §7). |
| **Principio IV (Pruebas y CI multiplataforma)** | **PARCIAL** | Pytest, Mypy y Ruff pasan en Windows local (35 pasan, 5 omitidas) y en WSL2 Ubuntu local (40 pasan). La ejecución en un runner de GitHub Actions depende de subir los cambios y no está confirmada. |
| **Principio V (Inmutabilidad de criterios)** | **PASS** | Criterio AC-01 conservado íntegramente. |
| **Principio VI (Disciplina de sprints)** | **PASS** | Pertenece al Sprint 1 activo; no adelanta código de Sprint 2 a 4. |
| **Principio VII (Consulta quirúrgica)** | **PASS** | Basado en los contratos de HU-00-01, la decisión V-01 y la pregunta abierta sobre asyncio de `docs/01` (V-14 es el FakeProvider y no se usa). |
| **Principio VIII (Registro en PROGRESO.md)** | **PASS** | Incluye tarea final de sincronización de progreso y evidencias. |
| **Principio IX (DoD estricta y supervisión)** | **PENDIENTE** | D-01 queda como «pendiente de aprobación» hasta la revisión humana de A, B y C. |
| **Principio X (Inmutabilidad histórica)** | **PASS** | No modifica archivos de `docs/archivo/`. |

---

## Project Structure

### Documentation (this feature)

```text
specs/003-async-cancellation-spike/
├── spec.md              # Especificación clarificada
├── plan.md              # Este plan de implementación
├── research.md          # Investigación de alternativas, hipótesis e impacto arquitectónico
├── data-model.md        # Modelo de ciclo de vida de cancelación y resultados
├── quickstart.md        # Guía de ejecución y verificación de los 7 escenarios
├── contracts/
│   └── async-cancellation-contract.md  # Protocolo abstracto de operación cancelable
└── checklists/
    └── requirements.md  # Checklist de calidad de requisitos
```

### Source Code (repository root)

```text
tests/
└── spikes/
    ├── __init__.py
    ├── test_async_cancellation_spike.py      # Prototipo, casos límite y dobles (V1-V22)
    └── test_concurrency_alternatives_spike.py  # Experimentos asyncio / hilos / procesos

docs/
├── decisiones/D-01-asyncio-cancelacion.md  # Decisión técnica (pendiente de aprobación)
└── guia-contratos-desarrollo.md            # Nota sobre la propuesta de firmas asíncronas
```

**Structure Decision**: El código del experimento se coloca deliberadamente en `tests/spikes/` para asegurar que el prototipo experimental sea 100% ejecutable y reproducible en el CI sin contaminar el paquete de producción `src/harness_agent/core/`.

---

## Estrategia de Pruebas y Validación (V1-V22)

1. **V1 (Happy Path)**: Ejecución de subproceso Python rápido (`python -c "print('ok')"`), comprobando salida y código 0.
2. **V2 (Cancelación activa)**: Subproceso Python de 5 s (`python -c "import time; time.sleep(5)"`), cancelado a los ≈120 ms con `proc.terminate()`; retorno en $< 500\text{ ms}$.
3. **V3 (Proceso terminado)**: Verificación de que `proc.returncode is not None` y que el PID ya no existe en el sistema operativo.
4. **V4 (Retorno de control)**: El bucle captura `asyncio.CancelledError` y continúa inmediatamente sin quedar en espera indefinida.
5. **V5 (Ejecución posterior)**: Inmediatamente tras cancelar la operación V2, el bucle lanza y completa una segunda operación exitosa.
6. **V6 (Timeout controlado)**: `asyncio.wait_for` con timeout de 250 ms sobre una operación de 4 s; verifica estado `TIMEOUT` y limpieza del proceso.
7. **V7 (Limpieza de recursos)**: Tres cancelaciones consecutivas; los PIDs directos no siguen vivos (ejecutado en Windows).
8. **V8-V22 (casos límite y semántica)**: cancelación antes de iniciar (V8, V9), finalización previa a la cancelación (V10, V11), escalamiento `terminate` a `kill` y no cooperativo con doble (V12-V14), segunda cancelación durante la limpieza y controles negativos (V15-V17), bucle activo durante la limpieza (V18), cuatro resultados distinguibles sin PIDs vivos (V19), re-lanzamiento de `CancelledError` y limitación del modo experimental (V20, V21) y estabilidad de handles (V22).

---

## Riesgos y Limitaciones Documentadas

1. **Limitación de árboles de procesos**: Cancelar el subproceso directo con `proc.terminate()` o `proc.kill()` garantiza la muerte del proceso inmediato, pero **no** garantiza la terminación de subprocesos nietos si el proceso invocó otros comandos. Se documenta la necesidad de *Process Groups* / *Job Objects* para la historia de Shell de Sprint 2 (HU-01-04).
2. **Plataformas**: Windows carece de señales POSIX directas como `SIGTERM`, por lo que `proc.terminate()` mapea a `TerminateProcess` y el escalamiento a `kill` no se puede reproducir con un proceso real. Se valida con un doble controlado y, en Linux, con una prueba real (T016, `tests/spikes/test_linux_sigterm_spike.py`) ejecutada en WSL2 Ubuntu local.
3. **Semántica de `CancelledError`**: el prototipo por defecto la absorbe y devuelve un resultado normal (solo experimental); el modo `reraise_cancel=True` muestra la semántica que debe usar producción. La cancelación definitiva (Ctrl+C, persistencia) es HU-06-03.

---

## Complexity Tracking

*No se introducen violaciones a la Constitución ni dependencias adicionales.*
