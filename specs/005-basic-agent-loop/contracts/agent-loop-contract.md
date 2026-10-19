# Contrato del bucle agéntico (Phase 1): HU-01-01

**Fecha**: 2026-10-18 | **Spec**: [../spec.md](../spec.md) | **Plan**: [../plan.md](../plan.md) | **Modelo**: [../data-model.md](../data-model.md)

Este contrato describe la **API pública** que HU-01-01 añade al núcleo. No modifica ningún contrato compartido de HU-00-01/HU-07-01; los consume tal como están (firmas verificadas en [../research.md](../research.md)). Las firmas se muestran solo como contrato; la implementación es de la fase de tareas.

## 1. API

Módulo: `harness_agent.core.loop` (`src/harness_agent/core/loop.py`). Solo biblioteca estándar y `harness_agent.core.*`.

```python
class TurnStatus(str, Enum):
    COMPLETED = "completed"
    PROVIDER_FAILED = "provider_failed"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"

@dataclass(frozen=True)
class TurnResult:
    status: TurnStatus
    final_response: str | None      # presente (puede ser "") solo con COMPLETED
    history: tuple[Message, ...]    # instantánea inmutable del historial al terminar
    error: str | None               # presente solo con fallos

class MissingDependencyError(ValueError): ...
class InvalidHistoryError(ValueError): ...

class AgentLoop:
    def __init__(
        self,
        provider: Provider,
        registry: ToolRegistry,
        policy: PermissionPolicy,
        bus: EventBus,
    ) -> None: ...

    async def run_turn(
        self,
        *,
        session_id: str,
        task: str,
        history: list[Message],
    ) -> TurnResult: ...
```

### Entradas

| Parámetro | Semántica |
|---|---|
| `provider`, `registry`, `policy`, `bus` | Obligatorios. Cualquiera `None` ⇒ `MissingDependencyError` que nombra al ausente (`provider`, `registry`, `policy`, `bus`), lanzada en el constructor, antes de cualquier consulta o ejecución (FR-025). No existe valor por defecto; en particular no hay política que permita. |
| `session_id` | Identificador opaco para `Event.session_id` (spec A-04). El bucle no lo crea ni lo valida. |
| `task` | Texto de la tarea; se añade como `Message(USER, task)`. El bucle no la valida (A-04; tarea vacía permitida). |
| `history` | Contexto inicial **y** destino de los mensajes nuevos (§4). Lista vacía en una sesión nueva; el historial de turnos anteriores en uno posterior. |

### Salida

`TurnResult` solo con `COMPLETED`, `PROVIDER_FAILED` o `INVALID_PROVIDER_RESPONSE`. Todo lo demás es excepción (§3).

## 2. Garantías de orden y secuencia

1. Un turno ejecuta, en este orden: precondiciones → añadir `USER` → `USER_MESSAGE` → bucle de consultas.
2. Cada consulta pasa a `Provider.complete` una **copia** del historial y la lista de `ToolDefinition` recalculada desde `registry.list()` (`ToolDefinition(name=t.name, description=t.description, parameters=t.schema)`).
3. Con llamadas en la respuesta: se añade el `ASSISTANT` (texto + `tuple(tool_calls)` + `usage`) y luego **cada llamada se procesa completa y en secuencia** en el orden recibido; su `TOOL` se añade en cuanto termina, antes de procesar la siguiente. Solo tras la última se consulta de nuevo (FR-003, FR-015).
4. La presencia de `tool_calls` prevalece sobre el texto (FR-004): texto + llamadas no es respuesta final.
5. Sin llamadas: se añade el `ASSISTANT` final y el turno termina con `COMPLETED`, sin consulta adicional.
6. **No hay límite de iteraciones, ni parámetro de turnos, ni `LIMIT_REACHED`** (FR-028; decisión del PO). Un guion que nunca termina solo se detecta en pruebas (guiones finitos y `asyncio.timeout`). La ejecución desatendida con proveedores reales **no se considera segura** hasta contar con los límites de HU-01-06 o controles externos equivalentes.

### Tubería por llamada

| Paso | Operación | Si falla |
|---|---|---|
| 1 | `bus.emit(TOOL_REQUESTED)` | Se propaga (Q4): la herramienta de esta llamada y las siguientes no se ejecutan |
| 2 | `registry.get(name)` | `None` o excepción ⇒ `unknown_tool` |
| 3 | `registry.validate_args(name, call.arguments)`; el retorno (un `dict`) se copia en profundidad: son los **argumentos efectivos** (R-07) | Cualquier `Exception` o retorno que no sea `dict` ⇒ `invalid_arguments` (falla cerrada); la política no se consulta |
| 4 | `policy.evaluate(eval_call)` con `eval_call = ToolCall(id=call.id, name=call.name, arguments=<copia profunda de los argumentos efectivos>)` (R-07; la `ToolCall` original no se pasa a la política) | Excepción o valor que no sea `PermissionDecision` ⇒ tratado como `DENY` |
| 5 | `bus.emit(PERMISSION_DECIDED)` | Se propaga (Q4): la herramienta **no** se ejecuta |
| 6 | Solo si la decisión es exactamente `ALLOW`: `await tool.run(authorized_args)` con **exactamente** los argumentos autorizados (copia propia, distinta de la que recibió la política; ningún cambio posterior en `call.arguments` ni en lo que recibió la política altera la ejecución) | `Exception` ⇒ `tool_exception`; retorno inválido ⇒ `invalid_tool_result`; `CancelledError` ⇒ se propaga (§3) |
| 7 | Normalizar resultado y añadir `Message(TOOL)` al historial | — |
| 8 | `bus.emit(TOOL_FINISHED)` | Se propaga (Q4); la herramienta ya se ejecutó y su resultado ya está en el historial; sin rollback ni repetición |

`DENY`, `ASK` y cualquier otro valor ⇒ `permission_denied` / `approval_required_unavailable`; ninguna ruta ejecuta la herramienta (FR-009). `Approver` no se usa; no se publican `APPROVAL_REQUESTED` ni `APPROVAL_RESOLVED` (Q3).

## 3. Matriz de tratamiento de errores

| Situación | Origen | Efecto en la herramienta | Resultado del turno | Evento | ¿Reintento? |
|---|---|---|---|---|---|
| Herramienta desconocida | modelo | no se ejecuta | continúa; `ToolResult` de error `[unknown_tool]` | `TOOL_REQUESTED`, `TOOL_FINISHED(category=unknown_tool)` | no |
| Argumentos inválidos / excepción de `validate_args` | modelo / registro | no se ejecuta; política no consultada | continúa; `[invalid_arguments]` con el motivo | `TOOL_REQUESTED`, `TOOL_FINISHED(invalid_arguments)` | no |
| `DENY` | política | no se ejecuta | continúa; `[permission_denied]` | `…`, `PERMISSION_DECIDED(deny)`, `TOOL_FINISHED(permission_denied)` | no |
| `ASK` (Sprint 1) | política (C) | no se ejecuta | continúa; `[approval_required_unavailable]` | `PERMISSION_DECIDED(ask, resolved_as=deny)`, `TOOL_FINISHED(...)` | no |
| Excepción / valor inválido de `evaluate` | política | no se ejecuta | continúa; `[permission_denied]` (falla cerrada) | `PERMISSION_DECIDED(deny, reason=policy_error)` | no |
| `Tool.run` devuelve `is_error=True` | herramienta | ejecutada | continúa; contenido íntegro del `ToolResult`, `call_id` forzado | `TOOL_FINISHED(tool_error)` | no |
| `Tool.run` lanza `Exception` | herramienta | ejecutada (efecto parcial posible) | continúa; `[tool_exception]` con nombre de clase y mensaje, sin traza | `TOOL_FINISHED(tool_exception)` | no |
| `Tool.run` devuelve algo que no es `ToolResult` con `content: str` | herramienta | ejecutada | continúa; `[tool_exception] …returned an invalid result` | `TOOL_FINISHED(invalid_tool_result)` | no |
| `Provider.complete` lanza `Exception` | proveedor | — | `TurnResult(PROVIDER_FAILED, error=…)`; historial hasta ese punto | `PROVIDER_ERROR(reason=provider_exception)` | **no** (sin reintento ni fallback) |
| Respuesta inválida (ids vacíos/repetidos, tipo incorrecto) | proveedor | ninguna llamada se ejecuta | `TurnResult(INVALID_PROVIDER_RESPONSE)`; la respuesta no se añade | `PROVIDER_ERROR(reason=invalid_response)` | no |
| `bus.emit(...)` lanza | bus (HU-01-05) | según §2 (nunca se ejecuta lo que aún no se había ejecutado) | **se propaga la excepción**; no se devuelve `TurnResult` | — | no |
| `bus.emit(PROVIDER_ERROR)` lanza al tratar un fallo | bus | — | se propaga la excepción del bus (encadenada a la del proveedor) | — | no |
| Suscriptor del bus falla (aislado por el bus) | HU-01-05 | — | el bucle no se entera | — | — |
| Cancelación durante `complete` o `run` | asyncio | la herramienta gestiona su limpieza | `CancelledError` se propaga | `INTERRUPTED` **una vez**, con `phase` | no |
| `bus.emit(INTERRUPTED)` lanza durante la cancelación (R-08) | bus | — | La `CancelledError` **original** se propaga (no un error del bus): se intenta publicar una vez, se adjunta una nota con el tipo y el mensaje del fallo del bus (`add_note`; no se exige ni se garantiza `__context__`); sin más herramientas ni reintentos ni `ToolResult` | — | no |
| Colaborador ausente | integrador | — | `MissingDependencyError` (constructor) | ninguno | no |
| Historial inicial inválido | llamador | — | `InvalidHistoryError`, sin añadir ni publicar nada | ninguno | no |

Las cinco situaciones que la decisión del PO sobre Q4 exige distinguir (suscriptor aislado, fallo real de `emit`, fallo de herramienta, fallo del proveedor y cancelación) tienen tratamientos distintos y nunca se convierten unas en otras: ninguna excepción de `emit` se transforma en `ToolResult`.

### Contenido de los resultados redactados por el bucle

Texto orientado al modelo (artefacto de código; en inglés). `{reason}` y los mensajes de excepción se acotan a 500 caracteres. Los resultados de herramientas **no** se recortan (HU-02-02 es otra historia).

| Categoría | `content` | `is_error` | `is_external` |
|---|---|---|---|
| `unknown_tool` | `[unknown_tool] Tool '{name}' is not registered.` | `True` | `False` |
| `invalid_arguments` | `[invalid_arguments] Arguments for tool '{name}' were rejected: {reason}` | `True` | `False` |
| `permission_denied` | `[permission_denied] Tool '{name}' was denied by the permission policy.` (con política fallida: `…could not be evaluated and was denied (fail closed).`) | `True` | `False` |
| `approval_required_unavailable` | `[approval_required_unavailable] Tool '{name}' requires approval, which is not available in this session; the request was resolved as denied.` | `True` | `False` |
| `tool_exception` | `[tool_exception] Tool '{name}' raised {ExceptionType}: {message}` | `True` | `True` |
| `invalid_tool_result` | `[tool_exception] Tool '{name}' returned an invalid result ({type}).` | `True` | `True` |
| `tool_error` / `ok` | contenido íntegro del `ToolResult` de la herramienta | el de la herramienta | `True` |

## 4. Propiedad y semántica del historial

| Pregunta | Respuesta |
|---|---|
| ¿Quién es propietario? | El **llamador**. El bucle no conserva referencias entre turnos. |
| ¿Copia u original? | El bucle **añade en el sitio** a la lista recibida (nunca modifica, reordena ni elimina lo existente). A `Provider.complete` le entrega siempre una **copia** (FR-002). |
| ¿Qué devuelve? | `TurnResult.history`: instantánea `tuple` del estado final (útil para pruebas y para el siguiente turno). |
| ¿Qué pasa ante una excepción? | La lista del llamador conserva todo lo añadido hasta ese punto. Puede terminar en un `ASSISTANT` con llamadas sin resultado. |
| ¿Y ante una cancelación? | Igual: el llamador lee su lista (FR-026, US6-4). No se fabrican resultados «interrumpido» (V-11 → HU-06-03). |
| ¿Se puede reutilizar? | Tras `COMPLETED`, `PROVIDER_FAILED` o `INVALID_PROVIDER_RESPONSE`: sí. Tras cancelación o fallo de `emit` a mitad de llamadas: no; el siguiente `run_turn` lanza `InvalidHistoryError`. |
| ¿Concurrencia? | Dos `run_turn` simultáneos sobre la misma lista no están soportados (responsabilidad del llamador). Instancias de `AgentLoop` sin estado por turno: se pueden reutilizar entre turnos y sesiones. |
| ¿Cómo se conserva el orden? | El único modo de escritura es `append` (§2 y [../data-model.md](../data-model.md) §3). |
| ¿Dónde se valida? | `_check_history` (privada, mínima; R-04) antes de añadir nada; en pruebas, el oráculo canónico de `adapters/converters/_validation.py` (SC-005). |

## 5. Eventos

Solo miembros existentes de `EventType`. Se construyen con `Event.create(session_id, type, payload)`. Las cargas son diccionarios pequeños, sin argumentos de herramientas ni contenido de archivos.

| # | Hecho | `EventType` | Carga (`payload`) |
|---|---|---|---|
| 1 | Se recibe la tarea (tras añadir el `USER`) | `USER_MESSAGE` | `{"content": task}` |
| 2 | La respuesta del proveedor trae texto (tras añadir el `ASSISTANT`); no se publica si el texto es `""` | `ASSISTANT_MESSAGE` | `{"content": text, "tool_call_count": n, "final": bool}` |
| 3 | Antes de procesar cada llamada | `TOOL_REQUESTED` | `{"call_id": id, "name": name}` |
| 4 | La política decidió (solo llamadas que llegan a ella) | `PERMISSION_DECIDED` | `{"call_id": id, "name": name, "decision": "allow"\|"deny"\|"ask", "resolved_as": "allow"\|"deny", "reason": None\|"policy_error"}` |
| 5 | Tras añadir el `TOOL` | `TOOL_FINISHED` | `{"call_id": id, "name": name, "is_error": bool, "category": …}` |
| 6 | Fallo del proveedor o respuesta inválida | `PROVIDER_ERROR` | `{"reason": "provider_exception"\|"invalid_response", "error_type": …, "message": … (≤500 caracteres)}` |
| 7 | Cancelación, antes de re-lanzarla | `INTERRUPTED` | `{"phase": "provider_call"\|"tool_execution", "call_id": id\|None}` |

Orden relativo garantizado por llamada: `TOOL_REQUESTED` < `PERMISSION_DECIDED` (si llega a la política) < `TOOL_FINISHED`. Por turno: `USER_MESSAGE` precede a cualquier otro evento; `ASSISTANT_MESSAGE` precede a los `TOOL_REQUESTED` de sus llamadas.

**No se publican**: `LIMIT_REACHED` (FR-028), `APPROVAL_REQUESTED`/`APPROVAL_RESOLVED` (Q3), `CONTEXT_COMPACTED`, `PROVIDER_SWITCHED`, `SESSION_STARTED`, `SUBAGENT_*`, `CRITERIA_TAMPERED`, `CRITERION_VERIFIED`.

**Fallos al publicar**: el bucle no captura nada (Q4, aprobada por el PO). Cada evento se publica en un punto tal que una excepción deja el sistema en un estado seguro (ver research R-08).

## 6. Compatibilidades y límites del contrato

- **Asincronía**: se consumen `Provider.complete` y `Tool.run` como `async def` existentes; `get`, `list`, `validate_args`, `evaluate` y `emit` son síncronas y así se invocan. D-01 sigue **pendiente de aprobación**; si cambia, este contrato se revisa.
- **Sin cambios a contratos compartidos**: no se agregan métodos a `Tool`, `ToolRegistry`, `PermissionPolicy`, `EventBus` ni `Provider`; no se crean versiones paralelas de `Message`, `ToolCall` o `ToolResult` (FR-033).
- **Silencio de la consola**: el módulo no usa `print`, `input`, `sys.stdout` ni `sys.stderr` (FR-030); una prueba AST lo verifica.
- **Fuera del contrato**: persistencia, compactación, paralelismo, límites, reintentos, shell, MCP, subagentes, CLI, streaming, truncado de salidas.
