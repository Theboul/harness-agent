# Implementation Tasks: SPK-02 — Spike: modelo asíncrono y cancelación de herramientas

**Feature**: `specs/003-async-cancellation-spike/spec.md`  
**Plan**: `specs/003-async-cancellation-spike/plan.md`  
**Responsable**: A — Núcleo  
**Sprint**: Sprint 1 | **PHU**: 1 (Estimación base: ~3 horas F5)  
**Estado**: T001-T005 implementadas (fase inicial); T006-T014 = fase de corrección y convergencia tras la auditoría del 2026-10-17. D-01 sigue **pendiente de aprobación**.  

---

## Phase 1: Setup del Spike y Prototipo Base (Sp1-48)

**Propósito**: Crear el arnés experimental aislado para ejecutar operaciones de larga duración mediante subprocesos Python controlados sin tocar código de producción.

- [x] **T001** [P] Crear el módulo de pruebas de spike y el mecanismo mínimo para iniciar una operación prolongada controlada (Sp1-48)
  - **Archivos**: `tests/spikes/__init__.py`, `tests/spikes/test_async_cancellation_spike.py`
  - **Dependencias**: Ninguna
  - **Criterios relacionados**: FR-001, FR-002, SC-004, Sp1-48
  - **Tarea F5**: Sp1-48
  - **Estimación**: 30 min (15 min impl + 10 min check + 5 min registro)
  - **Verificación**: `pytest tests/spikes/test_async_cancellation_spike.py -k test_spawn_and_normal_completion` ejecuta un subproceso con `sys.executable` y `asyncio.create_subprocess_exec` sin `shell=True`, finaliza exitosamente con código 0 y captura stdout sin bloquear el bucle.

---

## Phase 2: Cancelación Controlada y Suite de Validación (AC-01 / US1 / Sp1-48)

**Propósito**: Implementar la cancelación en dos fases, verificar la muerte del proceso a nivel de sistema operativo y demostrar que el bucle recupera el control.

- [x] **T002** [US1] Implementar el protocolo de cancelación asíncrona y terminación forzada en dos fases con recuperación inmediata de control (AC-01 / Sp1-48)
  - **Archivos**: `tests/spikes/test_async_cancellation_spike.py`
  - **Dependencias**: T001
  - **Criterios relacionados**: AC-01, FR-003, FR-004, FR-006, SC-001, Sp1-48
  - **Tarea F5**: Sp1-48
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: `pytest tests/spikes/test_async_cancellation_spike.py -k test_active_cancellation` lanza un proceso de 5 s, solicita cancelación a los ≈120 ms, captura `asyncio.CancelledError`, ejecuta `proc.terminate()` con fallback a `proc.kill()` y devuelve el control al bucle en $< 500\text{ ms}$.

- [x] **T003** [US1] Implementar la suite completa de validación de los 7 escenarios del spike (AC-01 / Sp1-48)
  - **Archivos**: `tests/spikes/test_async_cancellation_spike.py`
  - **Dependencias**: T002
  - **Criterios relacionados**: AC-01, FR-005, FR-008, SC-001, SC-002, Sp1-48
  - **Tarea F5**: Sp1-48
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: `pytest -v tests/spikes/test_async_cancellation_spike.py` ejecuta y aprueba los 7 escenarios: V1 (Happy path), V2 (Cancelación activa), V3 (Verificación de PID muerto en el SO), V4 (Retorno de control), V5 (Ejecución posterior exitosa), V6 (Timeout controlado) y V7 (Limpieza: PIDs directos sin vida tras 3 cancelaciones; ejecutado solo en Windows).

---

## Phase 3: Análisis de Impacto y Evaluación Arquitectónica (Sp1-49 / US2)

**Propósito**: Evaluar los efectos de la adopción de `asyncio` y las restricciones de cancelación sobre los contratos de interfaces y subsistemas de HARNESS.

- [x] **T004** [US2] Elaborar el análisis técnico de consecuencias para Provider, Tool, Approver, MCP, subagentes y almacenamiento (Sp1-49)
  - **Archivos**: `specs/003-async-cancellation-spike/research.md`, `docs/decisiones/D-01-asyncio-cancelacion.md`
  - **Dependencias**: T003
  - **Criterios relacionados**: FR-007, SC-003, Sp1-49
  - **Tarea F5**: Sp1-49
  - **Estimación**: 30 min (20 min impl + 5 min check + 5 min registro)
  - **Verificación**: Documento `docs/decisiones/D-01-asyncio-cancelacion.md` detalla con rigor las consecuencias técnicas sobre: `Provider.complete` (I/O streaming), `Tool.run` (timeout/cancelación), `Approver.request` (aprobación bidireccional no bloqueante), `EventBus` (despacho), `SessionStore` (síncrono justificado), cliente MCP y subagentes; incluye la limitación sobre árboles de procesos para HU-01-04.

---

## Phase 4: Formalización de Decisión y Sincronización de Progreso (Sp1-49)

**Propósito**: Formalizar el dictamen sobre las firmas provisionales de HU-00-01, preparar la revisión humana de los desarrolladores A, B y C, y actualizar el progreso del proyecto.

- [x] **T005** Redactar la propuesta de dictamen de firmas asíncronas, registrar la decisión técnica y sincronizar docs/PROGRESO.md (Sp1-49). *Corregida por T006, T010 y T013: el dictamen es una propuesta pendiente de aprobación, no una ratificación.*
  - **Archivos**: `docs/guia-contratos-desarrollo.md`, `docs/PROGRESO.md`
  - **Dependencias**: T004
  - **Criterios relacionados**: Principio VIII, Principio IX, SC-003, Sp1-49
  - **Tarea F5**: Sp1-49
  - **Estimación**: 25 min (15 min impl + 5 min check + 5 min registro)
  - **Verificación**: `docs/guia-contratos-desarrollo.md` actualizado con la propuesta de dictamen sobre `async def` en `Provider`, `Tool` y `Approver` (pendiente de aprobación); fila de SPK-02 en `docs/PROGRESO.md` actualizada con estado (`En revisión` / `Completada`), enlace al reporte de decisión y evidencias reales de ejecución de pruebas.

---

## Phase 5: Corrección y Convergencia tras la Auditoría (2026-10-17)

**Propósito**: Resolver los problemas de la auditoría técnica sin reconstruir el spike ni ampliar su alcance. Regla de cierre: D-01 permanece **PENDIENTE DE APROBACIÓN** y no se tocan los contratos compartidos de `core/`.

- [x] **T006** Corregir firmas de contratos y referencias a V-14 en spec, plan, research, D-01 (Correcciones 1 y 2)
  - **Archivos**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `docs/decisiones/D-01-asyncio-cancelacion.md`
  - **Estimación**: 30 min
  - **Verificación**: firmas leídas de `core/interfaces/` (`complete(messages, tools) -> ProviderResponse`, `run(args) -> ToolResult`, `request(call, details) -> ApprovalResult`); V-14 solo aparece para aclarar que es el FakeProvider.
  - **Resultado**: hecho; `grep` de `V-14` y `ApprovalDecision` en `specs/003-*` y D-01 solo devuelve aclaraciones.

- [x] **T007** Refactorizar la cancelación del spike: `ProcessLike`, `terminate_then_kill`, limpieza robusta ante segunda cancelación y modo `reraise_cancel` (Correcciones 4 y 5)
  - **Archivos**: `tests/spikes/test_async_cancellation_spike.py`
  - **Estimación**: 45 min
  - **Verificación**: las 7 pruebas originales siguen verdes sin cambios de intención.
  - **Resultado**: hecho; V1-V7 verdes.

- [x] **T008** Añadir las pruebas de casos límite V8-V22 con dobles controlados y límites de tiempo (Corrección 4, 6)
  - **Archivos**: `tests/spikes/test_async_cancellation_spike.py`
  - **Estimación**: 55 min
  - **Verificación**: `pytest tests/spikes/test_async_cancellation_spike.py` verde; repetido 5 veces sin fallos; sin procesos difíciles de terminar.
  - **Resultado**: hecho; 22 pruebas, 5.8 s en total en la última corrida.

- [x] **T009** Experimentos mínimos de alternativas asyncio / hilos / procesos (Corrección 3)
  - **Archivos**: `tests/spikes/test_concurrency_alternatives_spike.py`
  - **Estimación**: 50 min
  - **Verificación**: 4 pruebas verdes; mediciones reales con `python -m tests.spikes.test_concurrency_alternatives_spike` (5 ejecuciones).
  - **Resultado**: hecho; cifras en `research.md` §3 y D-01 §3.

- [x] **T010** Reescribir la comparación de alternativas en `research.md` y D-01 con evidencia (US2 / FR-007)
  - **Archivos**: `research.md`, `docs/decisiones/D-01-asyncio-cancelacion.md`
  - **Estimación**: 40 min
  - **Resultado**: hecho; D-01 pasa a «PENDIENTE DE APROBACIÓN» con condiciones de aprobación en §8.

- [x] **T011** Separar evidencia Windows / Linux / dobles / pendiente y limitar la afirmación de descriptores (Corrección 6)
  - **Archivos**: D-01 §2, `spec.md`, `plan.md`, `quickstart.md`, `data-model.md`
  - **Estimación**: 30 min
  - **Resultado**: hecho; V22 aporta evidencia de handles (Windows) y las demás afirmaciones se limitan a PIDs directos.

- [x] **T012** Registrar el conflicto Python 3.11+ frente a 3.12+ como decisión pendiente (Corrección 7)
  - **Archivos**: D-01 §7, `docs/PROGRESO.md` (Decisiones abiertas)
  - **Estimación**: 20 min
  - **Resultado**: hecho; en ese momento no se modificó `pyproject.toml` ni la CI. Actualizado por PD-07 (2026-10-17): el conflicto quedó resuelto con 3.12.x y los cambios de configuración los aplicó la tarea T015.

- [x] **T013** Consistencia documental (Corrección 8)
  - **Archivos**: D-01 (enlaces), `docs/PROGRESO.md` (línea sobrante), `spec.md`, `plan.md`, `quickstart.md`, `contracts/async-cancellation-contract.md`, `docs/guia-contratos-desarrollo.md`
  - **Estimación**: 30 min
  - **Resultado**: hecho; tiempos unificados (≈120 ms de retardo, gracia de 150 ms), enlaces relativos corregidos, estados alineados.

- [x] **T014** Validación final y sincronización de `tasks.md` y `docs/PROGRESO.md`
  - **Estimación**: 30 min
  - **Resultado**: ver el resumen de validación en `docs/PROGRESO.md` y en `odd/tasks/spk-02-convergence.md`.

- [x] **T015** Aplicar PD-07: Python 3.12.x única versión soportada (constitución v1.1.0, `pyproject.toml`, CI, `requirements-dev.txt`, docs y specs vigentes)
  - **Archivos**: `.specify/memory/constitution.md`, `pyproject.toml`, `.github/workflows/ci.yml`, `requirements-dev.txt`, `docs/`, `specs/001` a `specs/003`
  - **Estimación**: 45 min
  - **Resultado**: hecho; ver `odd/tasks/pd-07-python-312.md` y `docs/PROGRESO.md`. No altera criterios de aceptación ni interfaces.

- [x] **T016** Validar SPK-02 en Linux (WSL2 Ubuntu local) con una prueba real de `SIGTERM` ignorado y escalamiento a `SIGKILL` (no confundir con T016 / Sp1-03 de HU-00-01)
  - **Archivos**: `tests/spikes/test_linux_sigterm_spike.py` (nuevo), `research.md`, D-01, `docs/PROGRESO.md`, `odd/tasks/spk-02-convergence.md`
  - **Estimación**: 55 min
  - **Entorno**: WSL2 Ubuntu 26.04.1 LTS local, kernel 6.18.54.1-microsoft-standard-WSL2, CPython 3.12.15 (`uv python install`), `.venv` nuevo en `~/harness-agent`, dependencias fijadas instaladas con `uv pip`. **No es un runner de GitHub Actions.**
  - **Resultado (real)**: 5 pruebas nuevas, solo Linux (`skipif`). En WSL2: spike 31 pasan; suite completa 40 pasan, 0 omitidas (10.48 s, exit 0); Mypy sin errores (30 archivos); `ruff check` y `ruff format --check` limpios; 5 ejecuciones consecutivas de `tests/spikes` con 31 pasan cada una. En Windows: 35 pasan y 5 omitidas (8.84 s); Mypy y Ruff limpios.
  - **Escalamiento**: con hijo que ignora `SIGTERM`, código de salida -9, control de vuelta a los 151.6 ms (gracia de 150 ms), PID ausente; con tres cancelaciones durante la gracia, 2 absorbidas, -9 y 303.0 ms (gracia de 300 ms); timeout de 0.4 s: `TIMEOUT`, -9, 553.4 ms; 5 ciclos: `[-9, -9, -9, -9, -9]`, ninguno de los 5 PIDs vivo, zombi o hijo listado. Un hijo cooperativo (sondeo, n=10): control de vuelta en 0.7 / 1.0 / 1.4 ms, código -15. Descriptores (V22 en Linux, sondeo): 8 antes y 8 después de 5 ciclos.
  - **Defectos hallados**: ninguno; el algoritmo de limpieza escaló a `SIGKILL` sin cambios en el código del spike.

### Evidencia real pendiente (no marcada como hecha)

- [ ] Ejecución en un runner de GitHub Actions (`ubuntu-latest`, Python 3.12): nada está subido a GitHub, así que la matriz de HU-00-02 no ha corrido.
- [x] Prueba real de un hijo que ignora `SIGTERM` en Linux: ejecutada en WSL2 Ubuntu local (T016), no en la CI.
- [x] Decisión de gobernanza sobre la versión de Python: resuelta por PD-07 (2026-10-17, Python 3.12.x única versión soportada).
- [x] Comparación de `Task.cancelling()` entre 3.11 y 3.12: no aplica tras PD-07 (3.11 ya no es soportada).
- [ ] Revisión técnica y aprobación humana de D-01 por A, B y C (depende además de T016 / Sp1-03 de HU-00-01).

---

## Dependencias & Orden de Ejecución

```mermaid
flowchart TD
  subgraph Phase 1: Setup
    T001["T001: Arnés de prueba y subproceso (Sp1-48)"]
  end

  subgraph Phase 2: Cancelación y Validación (AC-01 / US1)
    T002["T002: Protocolo de parada y captura de CancelledError (Sp1-48)"]
    T003["T003: Suite de 7 escenarios de validación (Sp1-48)"]
  end

  subgraph Phase 3: Análisis Arquitectónico (US2)
    T004["T004: Evaluación de impacto en contratos y subsistemas (Sp1-49)"]
  end

  subgraph Phase 4: Decisión y Cierre
    T005["T005: Dictamen de firmas y sincronización PROGRESO.md (Sp1-49)"]
  end

  T001 --> T002
  T002 --> T003
  T003 --> T004
  T004 --> T005
```

---

## Resumen de Estimaciones

| Tarea | Descripción breve | Tiempo Impl. | Tiempo Check | Tiempo Reg. | Total |
|---|---|---|---|---|---|
| **T001** | Arnés de prueba y subproceso controlado (`sys.executable`) | 15 min | 10 min | 5 min | 30 min |
| **T002** | Protocolo de cancelación en dos fases y retorno de control | 20 min | 10 min | 5 min | 35 min |
| **T003** | Suite de validación de los 7 escenarios (AC-01) | 20 min | 10 min | 5 min | 35 min |
| **T004** | Análisis de impacto en contratos y subsistemas (Sp1-49) | 20 min | 5 min | 5 min | 30 min |
| **T005** | Dictamen de firmas, revisión y actualización de `PROGRESO.md` | 15 min | 5 min | 5 min | 25 min |
| **Total T001-T005** | **5 microtareas atómicas** | **90 min** | **40 min** | **25 min** | **155 min (~2.6 h)** |
| **T006-T014** | **9 microtareas de corrección (cada una < 60 min)** | | | | **estimadas en 330 min (referencia, no medidas)** |
