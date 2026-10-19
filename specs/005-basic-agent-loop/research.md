# Research (Phase 0): HU-01-01 — Bucle agéntico básico

**Fecha**: 2026-10-18 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Este documento resuelve las incógnitas técnicas del plan. No quedan marcadores `NEEDS CLARIFICATION`. Cada decisión se apoya en un contrato o documento real (con `archivo:línea`) y registra alternativas descartadas. Las decisiones D-PLAN-xx se resumen en `plan.md`.

## Inventario de contratos reales verificados

| Contrato | Firma real | Ubicación |
|---|---|---|
| `Provider.complete` | `async def complete(self, messages: list[Message], tools: list[ToolDefinition] \| None = None) -> ProviderResponse` | `src/harness_agent/core/interfaces/provider.py:54` |
| `ProviderResponse` | `content: str = ""`, `tool_calls: list[ToolCall]` (lista mutable), `usage: TokenUsage \| None` | `provider.py:32-43` |
| `ToolDefinition` | `name`, `description`, `parameters: dict[str, Any]` | `provider.py:17-29` |
| `Tool` | propiedades `name`, `description`, `schema`, `risk`; `async def run(self, args: dict[str, Any]) -> ToolResult` | `core/interfaces/tool.py:29-70` (`run` en :60) |
| `ToolRegistry` | `register`, `get(name) -> Tool \| None`, `list() -> list[Tool]`, `validate_args(name, args) -> dict[str, Any]` (lanza `ValueError`) | `tool.py:72-94` (`get` :81, `list` :86, `validate_args` :91) |
| `PermissionPolicy.evaluate` | **síncrona**: `def evaluate(self, call: ToolCall) -> PermissionDecision` (solo el enum, sin motivo) | `core/interfaces/security.py:56-74` (`evaluate` :64) |
| `PermissionDecision` | `DENY`, `ASK`, `ALLOW` | `security.py:17-27` |
| `Approver.request` | `async`; no se cablea en esta historia | `security.py:76-84` |
| `EventBus.emit` | **síncrona**: `def emit(self, event: Event) -> None` | `core/interfaces/event_bus.py:17-28` (`emit` :21) |
| `Event` / `Event.create` | `Event(id, session_id, type, timestamp, payload)`; `Event.create(session_id, type, payload=None, ...)` | `core/events.py:61-101` (`create` :86) |
| `EventType` | 17 miembros en inglés | `core/events.py:18-57` |
| `Message` | `role`, `content`, `tool_calls: tuple[ToolCall, ...]`, `tool_result`, `usage`, `is_external` | `core/entities.py:79-97` |
| `ToolCall` / `ToolResult` / `TokenUsage` | ver archivo | `entities.py:31`, `:46`, `:61` |
| Reglas canónicas (oráculo de pruebas) | `validate_canonical_messages`, `validate_tool_correlation` | `src/harness_agent/adapters/converters/_validation.py:129`, `:167` |
| Prueba de fronteras existente | solo prohíbe SDKs de proveedores, no restringe a la biblioteca estándar | `tests/architecture/test_core_boundaries.py:15-80` |

### Divergencias entre la solicitud del plan y los contratos reales

| Solicitud | Realidad | Tratamiento |
|---|---|---|
| Ninguna firma de la solicitud difiere de las reales (`evaluate` sí es síncrona, `emit` sí es síncrona, `Provider.complete`/`Tool.run` son `async`). | `Event` exige `session_id` (`events.py:61`); la solicitud no lo menciona. | El llamador entrega un `session_id` opaco en cada turno (spec A-04). |
| La skill `estructura-carpetas-harness` menciona `core/ports.py`, `core/messages.py` y `core/tools/`. | El repositorio usa `core/interfaces/` y `core/entities.py`. El árbol acordado (`references/arbol.md`) sí fija `core/loop.py` como bucle de A. | El bucle va en `src/harness_agent/core/loop.py`. La constitución (Restricciones, Área A) lo llama «`core/agent`»; prevalece el árbol acordado; sin cambio constitucional. |
| `tests/` debería reflejar `src/` (skill). | No existe `tests/core/`. | Se crea `tests/core/` con `__init__.py` (como `tests/contracts/` y `tests/doubles/`). |
| «Pruebas con timeout». | `pyproject.toml` no incluye `pytest-timeout` (solo `pytest`, `pytest-asyncio`, `pytest-cov`, `mypy`, `ruff`). | Se usa `asyncio.timeout` (Python 3.12) en un ayudante de pruebas; no se añade ninguna dependencia nueva. |
| `ProviderResponse.tool_calls` es `list`. | `Message.tool_calls` es `tuple`; `Message.__post_init__` convierte listas (`entities.py:99-104`). | El bucle construye el mensaje del asistente con `tuple(response.tool_calls)`. |
| El script de configuración informó `BRANCH=005-basic-agent-loop`. | La rama git real es `feat/hu-07-01-provider-message-format`. | No se cambia de rama; el nombre de rama de la spec es solo informativo. |

## Decisiones

### R-01 — Forma de la API (D-PLAN-01, D-PLAN-02)

- **Decisión**: una única clase `AgentLoop` en `src/harness_agent/core/loop.py`, con los cuatro colaboradores inyectados en el constructor (`Provider`, `ToolRegistry`, `PermissionPolicy`, `EventBus`) y un método `async def run_turn(self, *, session_id: str, task: str, history: list[Message]) -> TurnResult`. Sin estado por turno en `self`.
- **Justificación**: es la API mínima que cubre FR-001…FR-007; la clase evita pasar cuatro colaboradores en cada llamada y permite reutilizar la instancia entre turnos y sesiones. `session_id` va por llamada porque una instancia puede servir a varias sesiones y `Event` lo exige.
- **Alternativas**: (a) función libre `run_turn(provider, registry, ...)`: pasa seis argumentos por llamada y no ofrece un sitio natural para validar colaboradores una sola vez; (b) clase con estado de sesión (`Session`): anticipa HU-03-xx y ContextManager (fuera de alcance); (c) máquina de estados explícita (como sugiere el comentario de `arbol.md`: «máquina de estados»): sobreingeniería para un único estado repetible; HU-01-06/HU-06-03 pueden introducirla si la necesitan.

### R-02 — Propiedad del historial (D-PLAN-03)

- **Decisión**: el historial es **propiedad del llamador**. `run_turn` recibe una `list[Message]` mutable y **solo le añade mensajes al final, en el sitio** (nunca modifica, reordena ni elimina los existentes). El resultado trae además una instantánea inmutable (`tuple[Message, ...]`). A cada consulta al proveedor se le entrega una **copia** (`list(history)`), de modo que el proveedor no puede alterar el historial (FR-002).
- **Justificación**: es la única forma de que el historial parcial sobreviva a una excepción o a una cancelación sin inventar un objeto de resultado (FR-026): el llamador conserva la referencia. Cumple FR-020 (solo añadido) y el modelo «el consumidor conserva el historial y lo reutiliza» (FR-007) sin persistencia.
- **Alternativas**: (a) copiar y devolver solo en el resultado: se pierde el historial parcial ante `CancelledError` o fallo de `emit`; (b) adjuntar el historial parcial a la excepción: `CancelledError` no debe envolverse (D-01 §6) y mutarla con atributos es frágil; (c) un objeto `TurnState` que el llamador crea y consulta: nueva abstracción sin necesidad demostrable frente a pasar una lista.
- **Consecuencias documentadas** (ver `contracts/agent-loop-contract.md` §Historial): tras una cancelación o un fallo de `emit` el historial puede terminar en un mensaje del asistente con llamadas sin resultado; **no es reenviable** y el siguiente `run_turn` lo rechaza con `InvalidHistoryError` (R-04). El llamador no debe invocar dos `run_turn` concurrentes con la misma lista.

### R-03 — Resultado vs. excepción (D-PLAN-04)

- **Decisión**: la taxonomía de salida es:

  | Situación | Salida |
  |---|---|
  | Respuesta final | `TurnResult(status=COMPLETED, final_response=...)` |
  | `Provider.complete` lanza `Exception` | `TurnResult(status=PROVIDER_FAILED, error=...)` + evento `PROVIDER_ERROR` |
  | Respuesta inválida del proveedor | `TurnResult(status=INVALID_PROVIDER_RESPONSE, error=...)` + `PROVIDER_ERROR` |
  | Colaborador ausente | `MissingDependencyError` al construir |
  | Historial inicial inválido | `InvalidHistoryError` antes de cualquier efecto |
  | `EventBus.emit` lanza | la excepción original se propaga (Q4) |
  | Cancelación | `asyncio.CancelledError` se propaga tras `INTERRUPTED` |

- **Justificación**: FR-005/FR-006/FR-023 piden un resultado explícito para los fallos del proveedor (la constitución, «Manejo de errores y aislamiento», exige que un error de proveedor no rompa la sesión); los errores de programación o configuración (dependencia ausente, historial inválido) y los fallos del bus (Q4) son excepciones porque no son resultados de negocio del turno.
- **Alternativas**: devolver todo como resultado (incluida la cancelación): contradice D-01 §6 (no absorber `CancelledError`) y Q4 (no ocultar errores de `emit`).

### R-04 — Comprobación mínima del contexto inicial (D-PLAN-05)

- **Decisión**: el núcleo implementa una comprobación estructural privada y pequeña (`_check_history`) que se ejecuta **antes de añadir nada o publicar nada**. Rechaza con `InvalidHistoryError` si: (1) hay un mensaje `SYSTEM` que no forma parte del prefijo contiguo inicial; (2) `tool_calls` aparece fuera de un mensaje `ASSISTANT` o `tool_result` fuera de un mensaje `TOOL`, o un `TOOL` no trae `tool_result`; (3) hay identificadores de llamada vacíos o repetidos o resultados duplicados; (4) alguna llamada del historial no tiene su resultado (llamadas pendientes). Las reglas 1–3 son las de `validate_canonical_messages`/`validate_tool_correlation` (`_validation.py:129`, `:167`); la regla 4 es propia del bucle (un historial con llamadas pendientes no se puede reenviar).
- **Justificación**: FR-001 delega la decisión en el plan. El núcleo no puede importar `adapters/` (FR-032, Principio III), así que reutilizar el validador existente no es posible sin mover código de HU-07-01 (prohibido: «No alterar semánticas establecidas por HU-07-01»). La duplicación se limita a ~25 líneas y **se vigila con una prueba de acuerdo** (`tests/contracts/test_loop_canonical_oracle.py`) que ejecuta ambos validadores sobre un mismo corpus de historiales y exige que coincidan en las reglas 1–3. Falla rápido y de forma determinista, y cubre el caso real de reutilizar el historial de un turno cancelado.
- **Alternativas**: (a) no comprobar y confiar en el límite del proveedor (texto actual de FR-001): el error llega tarde, como `ConversionError` dentro de un adaptador que puede no existir (p. ej. `FakeProvider` no valida) y se disfraza de fallo del proveedor; (b) mover `validate_canonical_messages` a `core/`: toca HU-07-01 y su historial de revisión; propuesta futura, no de esta historia; (c) comprobación completa duplicada: más superficie de divergencia.
- **Compatibilidad con la spec**: FR-001 se mantiene como respaldo para lo que la comprobación no detecta; la decisión queda registrada en este plan, como FR-001 pedía.

### R-05 — Orden de la tubería por llamada y eventos (D-PLAN-06)

- **Decisión**: por cada llamada, en este orden exacto:
  1. publicar `TOOL_REQUESTED`;
  2. `registry.get(name)`;
  3. `registry.validate_args(name, call.arguments)`;
  4. `policy.evaluate(call)`;
  5. publicar `PERMISSION_DECIDED`;
  6. si la decisión es `ALLOW`: `await tool.run(effective_args)`;
  7. normalizar el resultado y **añadir el mensaje `TOOL` al historial**;
  8. publicar `TOOL_FINISHED`.
  Los pasos 2–6 se omiten a partir del primer rechazo (desconocida o argumentos inválidos no llegan a la política ni producen `PERMISSION_DECIDED`; spec A-06).
- **Justificación**: `PERMISSION_DECIDED` se publica **antes** de ejecutar para que el registro de auditoría preceda al efecto; si publicarlo falla, la herramienta no se ejecuta (Q4, regla 4). El mensaje `TOOL` se añade **antes** de `TOOL_FINISHED` para que, si ese `emit` falla después de una operación con efectos, la observación ya esté en el historial del llamador (Q4, regla 5: sin rollback ni repetición).
- **Alternativas**: publicar `TOOL_FINISHED` antes de añadir el mensaje: si `emit` falla se pierde la observación de una acción ya realizada; publicar `PERMISSION_DECIDED` después de ejecutar: auditoría posterior al efecto, rechazado por falla cerrada.

### R-06 — Argumentos efectivos (D-PLAN-07)

- **Decisión (R-07, adoptada; comunicada en la solicitud de `/speckit-tasks` del 2026-10-18)**: se valida con `validate_args` (`tool.py:91`); su retorno debe ser un `dict` (si no, rechazo de validación, falla cerrada) y se toma una **copia profunda** como argumentos efectivos. La política evalúa una `ToolCall` con el mismo `id` y `name` y esos argumentos efectivos (otra copia profunda) y `Tool.run` recibe exactamente los argumentos autorizados (copia propia): no hay diccionarios compartidos entre autorización y ejecución y los argumentos originales solo se conservan para diagnóstico e historial. Sustituye la decisión previa (política sobre la llamada cruda).
- **Riesgo residual (R-07 en `plan.md`)**: la semántica de `validate_args` y que la política de C asuma argumentos crudos; la copia profunda neutraliza que `validate_args` devuelva el mismo objeto o lo mute. Ratificación formal del PO pendiente si quien comunicó la decisión no actúa como PO.
- **Preguntas exactas para C**: (1) ¿`validate_args` devuelve siempre un `dict` nuevo con los argumentos normalizados, sin mutar el recibido? (2) ¿La política de C razona sobre los argumentos efectivos (p. ej. rutas contra `AuthorizedArea`)? (3) ¿Qué excepciones puede lanzar además de `ValueError`?

### R-07 — Normalización del resultado de la herramienta (D-PLAN-08)

- **Decisión**:
  - El `call_id` del resultado entregado al modelo es **siempre** `call.id` (`dataclasses.replace(result, call_id=call.id)` solo si difiere; FR-016). Hallazgo ya registrado: `Tool.run(args)` no recibe el id y `DummyTool` devuelve `"call_dummy_default"` si falta (`tests/doubles/dummy_tool.py:54`).
  - `Message(role=TOOL, content=result.content, tool_result=result, is_external=...)`: `content` igual a `tool_result.content` (evita D9 de D-02; los convertidores usan `tool_result.content`).
  - Categorías de resultado (para `TOOL_FINISHED.category` y para el prefijo textual de los resultados redactados por el bucle): `ok`, `tool_error` (la herramienta devolvió `is_error=True`), `tool_exception`, `invalid_tool_result`, `unknown_tool`, `invalid_arguments`, `permission_denied`, `approval_required_unavailable`.
  - `is_external=True` para `ok`, `tool_error`, `tool_exception` e `invalid_tool_result` (el contenido nace en la ejecución); `False` para los rechazos previos a la ejecución (FR-022, A-05).
  - Si `Tool.run` devuelve algo que no es un `ToolResult` o cuyo `content` no es `str`, se trata como `invalid_tool_result` con `is_error=True` (FR-018, ampliado: sin esto un contenido no textual llegaría al convertidor y fallaría ahí como si fuera culpa del proveedor).
- **Alternativas**: dejar pasar el `call_id` de la herramienta: rompe la correlación (D-02 §4.7); marcar `is_external=True` en los rechazos: los convertidores no dependen de la marca y el contenido es del bucle, no de un tercero.

### R-08 — Semántica de fallos de `EventBus.emit` (Q4 aprobada, D-PLAN-09)

- **Decisión (aprobada por el PO)**: el bucle no captura ni transforma ninguna excepción lanzada por `emit`; se propaga y detiene el turno. Distinciones:

  | Fallo | Origen | Tratamiento |
  |---|---|---|
  | Suscriptor aislado | dentro de `EventBus` (HU-01-05, B) | no llega al bucle; el bus lo absorbe |
  | `emit` lanza | el bus mismo | se propaga; el turno se detiene |
  | Herramienta falla | `Tool.run` | `ToolResult` de error; continúa |
  | Proveedor falla | `Provider.complete` | `TurnResult(PROVIDER_FAILED)`; sin reintento |
  | Cancelación | `asyncio.CancelledError` | `INTERRUPTED` y se propaga |

  Efectos por punto de publicación (el historial siempre conserva lo ya ocurrido):

  | `emit` que falla | Consecuencia |
  |---|---|
  | `USER_MESSAGE` | no hay consulta al proveedor; el historial ya contiene el mensaje de usuario |
  | `ASSISTANT_MESSAGE` | no se procesan sus llamadas |
  | `TOOL_REQUESTED` | la herramienta de esa llamada y las siguientes no se ejecutan |
  | `PERMISSION_DECIDED` | la herramienta no se ejecuta (la auditoría precede al efecto) |
  | `TOOL_FINISHED` | la herramienta **ya** se ejecutó: su resultado ya está en el historial; no se asume rollback ni se repite; las llamadas siguientes no se procesan |
  | `PROVIDER_ERROR` | se propaga la excepción del bus (encadenada a la del proveedor); no se devuelve `TurnResult` |
  | `INTERRUPTED` | **R-08 (adoptada)**: la cancelación prevalece; se intenta publicar una vez; si `emit` falla se adjunta una nota (`add_note`) a la `CancelledError` original con el tipo y el mensaje del fallo del bus (no se exige `__context__`: tras capturar el error del bus dentro del manejo de la cancelación, el `__context__` de la cancelación no es el error del bus) y se propaga la `CancelledError` original (sin envolverla ni convertirla) |

- **Nota (R-08)**: el último caso resuelve, por decisión adoptada en `/speckit-tasks`, la tensión entre dos reglas («no ignorar errores de `emit`» y «no absorber la cancelación»): prevalece la cancelación y se conserva el diagnóstico. Un fallo ordinario de `emit` sigue la regla de Q4. Ratificación formal del PO pendiente si quien comunicó la decisión no actúa como PO.

### R-09 — Cancelación (D-PLAN-10)

- **Decisión**: las únicas esperas (`await`) del turno son `provider.complete` y `tool.run`; `emit`, `get`, `validate_args` y `evaluate` son síncronas. Un `try` externo alrededor de todo el turno captura `asyncio.CancelledError`, publica `INTERRUPTED` **una sola vez** con `phase` (`provider_call`, `tool_execution`) y la vuelve a lanzar. Los `except Exception` de herramienta y proveedor nunca interceptan `CancelledError` (es `BaseException`, verificado en Python 3.12). No hay `asyncio.shield` ni limpieza propia: terminar procesos hijos es de la herramienta y de HU-01-04; la cancelación definitiva (Ctrl+C, resultados «interrumpido», persistencia) es de HU-06-03.
- **Justificación**: D-01 §6 (docs/decisiones/D-01-asyncio-cancelacion.md:114-117): producción debe limpiar y re-lanzar, nunca absorber. D-01 sigue **pendiente de aprobación** (spec FR-027); si cambia, esta historia se revisa.
- **Alternativas**: `asyncio.wait_for` para la herramienta: introduce un tiempo máximo (HU-01-06); devolver un `TurnResult(INTERRUPTED)`: absorbe la cancelación.

### R-10 — Cargas útiles de los eventos (D-PLAN-11)

- **Decisión**: cargas mínimas y sin información sensible (ver `contracts/agent-loop-contract.md` §Eventos). En particular, `TOOL_REQUESTED` lleva `call_id` y `name` pero **no los argumentos** (pueden contener contenido de archivos o secretos; la redacción obligatoria de V-13 corresponde a `observability/` y aún no existe). La CLI (HU-06-01) puede pedir ampliar la carga más adelante; sería un cambio aditivo.
- **Justificación**: spec «Eventos publicados»: «sin incluir información sensible».
- **Riesgo**: los mensajes de excepción de proveedor/herramienta (`error`, `message`) sí viajan en `PROVIDER_ERROR` y en los resultados; se acotan a 500 caracteres. La redacción de secretos es de HU-00-04/observabilidad y no se implementa aquí.

### R-11 — Estrategia de pruebas y dobles (D-PLAN-12)

- **Decisión**: dobles de prueba nuevos en `tests/doubles/` (no son las historias de B ni de C; se documentan como dobles): `ScriptedProvider` (guion finito; al agotarse lanza `ScriptExhausted` y marca `exhausted=True`), `InMemoryToolRegistry` (validación mínima por `required` del esquema), `ScriptedPolicy` (mapa nombre→decisión; **sin valor por defecto que permita**: lo no mapeado devuelve `DENY`), `FailingEventBus` (subclase de `RecordingEventBus` que lanza en tipos de evento configurados) y herramientas dobles (`RecordingTool`, `FailingTool`, `RaisingTool`, `BlockingTool`). Reutilizan `DummyTool`/`RecordingEventBus` cuando bastan. Un ayudante `run_bounded(coro, seconds=...)` aplica `asyncio.timeout` y comprueba `exhausted`.
- **Agotamiento del guion**: como el bucle trata cualquier excepción del proveedor como `PROVIDER_FAILED`, el fallo de prueba explícito se garantiza con el indicador `exhausted` que el ayudante comprueba y con una aserción sobre `status`.
- **Oráculo**: `validate_canonical_messages` y los dos convertidores (`openai_converter`, `anthropic_converter`) se usan **solo en pruebas** (SC-005).

### R-12 — Superficie pública (D-PLAN-13)

- **Decisión**: `AgentLoop`, `TurnResult`, `TurnStatus`, `MissingDependencyError` e `InvalidHistoryError` se importan desde `harness_agent.core.loop`. **No** se exportan desde `core/__init__.py` en esta historia.
- **Justificación**: `core/__init__.py` y `core/interfaces/__init__.py` son la superficie de HU-00-01 aún pendiente de aprobación técnica (T016); no se toca. Si el equipo quiere el reexport, es un cambio aditivo posterior.

### R-13 — Alineación de esfuerzo y descomposición

- **Decisión**: las 13,5 h de `docs/03` (Sp1-12 = 7 h; Sp1-13 = 2,5 h; Sp1-14 = 4 h; verificadas en `docs/03-plan-sprints.md:253-255`) se reparten en «costuras» de 15–55 minutos (tabla en `plan.md`) para que `/speckit-tasks` obtenga microtareas por debajo de 60 minutos (Principio II).
- **Nota**: Sp1-12 abarca el turno completo (proveedor, respuesta, herramientas, resultados) y Sp1-13 la condición de parada y los eventos; la separación es documental, el código es un único módulo.

## Dependencias y buenas prácticas consultadas

- `asyncio` 3.12: `asyncio.timeout`, `Task.cancel()`; `CancelledError` hereda de `BaseException` desde 3.8 (verificación en pruebas: `tests/core/test_loop_failures.py`).
- No se consulta documentación externa: el plan no introduce librerías de terceros ni dependencias nuevas.
