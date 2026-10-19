# Guía de validación (Phase 1): HU-01-01 — Bucle agéntico básico

**Fecha**: 2026-10-18 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Contrato**: [contracts/agent-loop-contract.md](contracts/agent-loop-contract.md)

Guía para comprobar de punta a punta que el bucle funciona **una vez implementado**. Hoy (fase de plan) no existe código: estos comandos fallarán hasta completar las tareas. No requiere red, cuentas ni credenciales.

## Requisitos previos

- Python 3.12.x (única versión soportada, PD-07). Entorno del repositorio: `.venv`.
- Dependencias de desarrollo ya declaradas en `pyproject.toml` (`pytest`, `pytest-asyncio` con `asyncio_mode = "auto"`, `pytest-cov`, `mypy`, `ruff`). No se añade ninguna.
- Dobles de prueba de esta historia en `tests/doubles/` (`ScriptedProvider`, `InMemoryToolRegistry`, `ScriptedPolicy`, `FailingEventBus`, herramientas dobles).

## Comandos de verificación

```text
# Pruebas de la historia
.venv/Scripts/python.exe -m pytest tests/core tests/contracts/test_loop_canonical_oracle.py tests/architecture/test_loop_boundaries.py

# Suite completa (no debe romper nada existente)
.venv/Scripts/python.exe -m pytest

# Calidad
.venv/Scripts/python.exe -m mypy src tests
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
```

En Linux/WSL2 se usa `.venv/bin/python` en lugar de `.venv/Scripts/python.exe`. La CI remota (Windows y Linux, Python 3.12) debe confirmar lo mismo; sin esa corrida la Definition of Done sigue incompleta.

## Escenarios de validación

Cada escenario se expresa con los dobles de prueba; los detalles de los pasos están en la spec.

### E-01 — AC-01: guion de tres pasos

1. `ScriptedProvider` con cuatro respuestas: tres piden una herramienta distinta (A, B, C) y la cuarta es texto sin llamadas.
2. Registro con A, B y C (`RecordingTool` que anotan el orden); política `ALLOW` para las tres; `RecordingEventBus`.
3. `await run_bounded(loop.run_turn(session_id="s1", task="…", history=[]))`.
4. **Esperado**: orden de ejecución `A, B, C`; `status == COMPLETED`; `final_response` igual al texto de la cuarta respuesta; el proveedor se consultó exactamente 4 veces; el historial es canónicamente válido; repetido 20 veces da el mismo resultado (SC-001).

### E-02 — AC-02: una herramienta falla y el bucle continúa

1. Proveedor: pide la herramienta `F` (devuelve `ToolResult(is_error=True)`), luego responde con texto.
2. **Esperado**: la segunda consulta recibe un mensaje `TOOL` con `is_error=True`, el contenido del error y el `id` de la llamada original; `status == COMPLETED`. Variantes: excepción en `run`, herramienta desconocida, argumentos inválidos (SC-003).

### E-03 — Nada se ejecuta sin validación y autorización

1. Registro doble que rechaza argumentos; política `ScriptedPolicy` con `ALLOW`, `DENY` y `ASK` según la herramienta; ausencia de política configurada ⇒ `DENY`.
2. **Esperado**: el contador de ejecuciones = número de llamadas válidas con `ALLOW` (SC-002); `ASK` produce `[approval_required_unavailable]` y no se publican eventos `APPROVAL_*`; una política que lanza una excepción se trata como `DENY`.
3. **R-07**: con un registro doble que normaliza los argumentos, la política doble registra la llamada recibida (mismo `id` y `name`, argumentos efectivos) y la herramienta doble registra exactamente esos argumentos; mutar los argumentos originales o lo recibido por la política después de autorizar no cambia lo ejecutado.

### E-04 — Varias llamadas en una respuesta

1. Una respuesta con tres llamadas, la segunda falla.
2. **Esperado**: las tres se procesan en orden; tres mensajes `TOOL` en ese orden, cada uno con su `call_id`; la segunda con `is_error=True`.

### E-05 — Eventos y silencio

1. Ejecución completa con `RecordingEventBus` y `capsys`.
2. **Esperado**: la secuencia de `EventType` coincide con la tabla del contrato (§5); salida estándar y de error vacías (SC-004, SC-006). Prueba AST: `loop.py` sin `print`, `input`, `sys.stdout`/`sys.stderr` ni importaciones de `adapters`, `cli` o SDKs (SC-007).

### E-06 — Fallos de `EventBus.emit` (Q4)

1. `FailingEventBus` configurado para lanzar en `TOOL_REQUESTED`, luego en `PERMISSION_DECIDED`, luego en `TOOL_FINISHED`.
2. **Esperado**: la excepción se propaga siempre; en los dos primeros casos la herramienta **no** se ejecuta; en el tercero la herramienta se ejecutó una sola vez, su `TOOL` ya está en el historial del llamador y no hay reintento ni más llamadas.

### E-07 — Proveedor y cancelación

1. Proveedor que lanza en la segunda consulta ⇒ `PROVIDER_FAILED`, un `PROVIDER_ERROR`, sin reintento. Respuesta con ids repetidos ⇒ `INVALID_PROVIDER_RESPONSE`, nada ejecutado, respuesta no añadida.
2. `BlockingTool` y un proveedor que espera; `task.cancel()` en cada caso.
3. **Esperado**: `CancelledError` llega al llamador; un solo `INTERRUPTED`; ninguna consulta ni herramienta posterior; el historial parcial del llamador no tiene duplicados ni resultados inventados; reutilizarlo en un nuevo turno lanza `InvalidHistoryError`.
4. **R-08**: con un bus doble que falla al recibir `INTERRUPTED`, la cancelación original llega al llamador (no un error del bus) con el diagnóstico del fallo del bus adjunto como nota (`__notes__`, sin exigir `__context__`); un bus que falla fuera de una cancelación propaga su propio error (Q4).

### E-08 — Varios turnos y oráculo canónico

1. Dos turnos seguidos con el mismo `history`.
2. **Esperado**: el segundo turno parte del historial del primero sin modificarlo; cada copia entregada al proveedor supera `validate_canonical_messages` y `validate_tool_correlation` y se convierte con los dos convertidores (OpenAI y Anthropic) sin `ConversionError` (SC-005); la comprobación mínima del núcleo coincide con el validador del adaptador en el corpus compartido.

### E-09 — Dependencias ausentes

1. Construir `AgentLoop` quitando cada colaborador (4 casos).
2. **Esperado**: `MissingDependencyError` que nombra al ausente; 0 consultas; 0 ejecuciones (SC-008).

## Criterio de «listo para revisión»

Todos los escenarios en verde en Windows y en WSL2/Linux, `mypy`/`ruff` limpios, suite completa sin regresiones y duración de las pruebas de la historia por debajo de 5 s (SC-010). Los cierres formales de HU-00-01, HU-07-01, D-01 y D-02 siguen siendo ajenos a esta guía.
