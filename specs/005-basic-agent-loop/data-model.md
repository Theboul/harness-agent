# Modelo de datos (Phase 1): HU-01-01 — Bucle agéntico básico

**Fecha**: 2026-10-18 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Principio rector: **no se crean contratos paralelos** (FR-033). Todo el modelo de dominio ya existe en `core/`; esta historia solo añade el mínimo imprescindible para devolver el resultado de un turno y nombrar dos errores de precondición.

## 1. Entidades reutilizadas sin cambios

| Entidad | Uso en el bucle | Ubicación |
|---|---|---|
| `Role` | `USER`, `ASSISTANT`, `TOOL`; `SYSTEM` solo como prefijo recibido | `core/entities.py:15` |
| `Message(role, content, tool_calls, tool_result, usage, is_external)` | Unidad del historial. Mensaje de usuario, del asistente (con `tool_calls` y `usage`) y `TOOL` (con `tool_result`) | `core/entities.py:79` |
| `ToolCall(id, name, arguments)` | Solicitud del modelo, tal como la emite; no se modifica | `core/entities.py:31` |
| `ToolResult(call_id, content, is_error)` | Resultado entregado al modelo; `call_id` siempre es el de la llamada | `core/entities.py:46` |
| `TokenUsage` | Se conserva en el mensaje del asistente (`Message.usage`) | `core/entities.py:61` |
| `ProviderResponse`, `ToolDefinition`, `Provider` | Contrato de consulta | `core/interfaces/provider.py:17,32,46` |
| `Tool`, `ToolRegistry`, `RiskLevel` | Catálogo, validación y ejecución | `core/interfaces/tool.py:16,29,72` |
| `PermissionPolicy`, `PermissionDecision` | Decisión por llamada | `core/interfaces/security.py:56,17` |
| `Event`, `EventType`, `EventBus` | Salida de hechos | `core/events.py:61,18`, `core/interfaces/event_bus.py:17` |

`Approver`, `ApprovalResult`, `ContextManager`, `SessionStore` y el resto de interfaces **no se usan** (Q3; A-08).

## 2. Tipos nuevos (mínimos, en `src/harness_agent/core/loop.py`)

| Tipo | Forma | Por qué es necesario | Alternativa descartada |
|---|---|---|---|
| `TurnStatus` | `Enum` (`str`, como `Role`/`EventType`): `COMPLETED`, `PROVIDER_FAILED`, `INVALID_PROVIDER_RESPONSE` | FR-005/FR-006 exigen distinguir finalización normal de cada terminación por fallo. Tres valores cubren exactamente los resultados que no son excepción. | Reutilizar `EventType`: mezcla hechos del bus con resultados de negocio |
| `TurnResult` | `@dataclass(frozen=True)`: `status: TurnStatus`, `final_response: str \| None`, `history: tuple[Message, ...]`, `error: str \| None` | FR-006 pide devolver el resultado y el historial; es inmutable, igual que el resto de entidades. `final_response` solo está presente con `COMPLETED` (puede ser `""`, respuesta vacía válida); `error` solo con fallos. | Devolver una tupla o un dict: sin tipado; añadir `iterations`/`usage` agregados: no los exige ningún requisito (`ScriptedProvider.recorded_calls` ya permite contar consultas en pruebas) |
| `MissingDependencyError` | `class MissingDependencyError(ValueError)`; el mensaje nombra al colaborador (`provider`, `registry`, `policy`, `bus`) | FR-025/SC-008: error explícito que nombra al ausente, distinguible de otros `ValueError` en pruebas | `TypeError` genérico: no se puede afirmar con precisión que sea una dependencia ausente |
| `InvalidHistoryError` | `class InvalidHistoryError(ValueError)`; el mensaje cita la regla violada y la posición | R-04: precondición del llamador; no es un resultado de negocio del turno | Reutilizar `ConversionError` (vive en `adapters/`; prohibido importar) |

Tipos **privados** del módulo (no públicos, no contratos): un `_CallOutcome` (`result: ToolResult`, `category: str`, `is_external: bool`) que transporta el resultado normalizado de una llamada entre la tubería y el añadido al historial, y funciones auxiliares (`_check_history`, `_tool_definitions`, `_reject`, `_payload_*`). Si `loop.py` supera ~350 líneas se divide en un paquete `core/loop/` sin cambiar la API (decisión de las tareas, no de este plan).

**No se crea**: `AgentConfig`, `LoopLimits`, `Session`, `TurnState`, interfaces nuevas ni excepciones por categoría de herramienta.

## 3. Invariantes del historial (propiedad del llamador; el bucle solo añade)

Sea `H` la lista pasada a `run_turn`. Para toda ejecución:

1. **Solo añadido** (FR-020): ningún elemento de `H` presente al entrar cambia de posición ni de valor.
2. **Orden de añadido por turno**: `USER(task)` → por cada respuesta con llamadas: `ASSISTANT(content, tool_calls, usage)` seguido de un `TOOL` por llamada en el orden de `tool_calls` (cada uno añadido en cuanto termina su llamada) → respuesta final: `ASSISTANT(content, usage)` sin `tool_calls`.
3. **Correlación** (FR-016, FR-021): cada `TOOL.tool_result.call_id` es el `id` de su llamada; no hay `id` vacíos ni repetidos en todo `H`.
4. **Igualdad de contenido** (D-02, D9): `TOOL.content == TOOL.tool_result.content`.
5. **Marca externa** (FR-022): `TOOL.is_external` es `True` si el contenido nace en la ejecución de la herramienta; `False` en rechazos previos; `USER` y `ASSISTANT` siempre `False`.
6. **Validez canónica en cada consulta** (SC-005): en cada llamada a `Provider.complete`, la copia entregada supera `validate_canonical_messages` y `validate_tool_correlation` (oráculo en pruebas).
7. **Estados terminales**:
   - `COMPLETED`: `H` termina en un `ASSISTANT` sin llamadas; es reenviable y reutilizable como contexto del turno siguiente.
   - `PROVIDER_FAILED` / `INVALID_PROVIDER_RESPONSE`: `H` termina en el último mensaje válido (la respuesta inválida **no** se añade); reutilizable (no hay llamadas pendientes, porque el fallo ocurre en una consulta, nunca entre una llamada y su resultado).
   - Cancelación o fallo de `emit` a mitad de un turno: `H` puede terminar en `ASSISTANT` con llamadas sin resultado; **no reenviable** hasta que HU-06-03 defina el resultado «interrumpido»; `run_turn` lo rechaza con `InvalidHistoryError` (regla 4 de R-04).

## 4. Transiciones del turno

```text
INICIO ──precondiciones (colaboradores en el constructor; _check_history)──► añadir USER ──► emit USER_MESSAGE
   │ (error: MissingDependencyError / InvalidHistoryError, sin efectos)
   ▼
CONSULTAR ──excepción──► PROVIDER_ERROR ──► TurnResult(PROVIDER_FAILED)
   │ ──id vacío/repetido──► PROVIDER_ERROR ──► TurnResult(INVALID_PROVIDER_RESPONSE)
   │ ──CancelledError──► INTERRUPTED ──► (re-lanza)
   ▼
RESPUESTA ──sin tool_calls──► añadir ASSISTANT; emit ASSISTANT_MESSAGE (si hay texto) ──► TurnResult(COMPLETED)
   │ ──con tool_calls──► añadir ASSISTANT; emit ASSISTANT_MESSAGE (si hay texto)
   ▼
PARA CADA LLAMADA, EN ORDEN:
   TOOL_REQUESTED → get → validate_args → evaluate → PERMISSION_DECIDED → [run] → añadir TOOL → TOOL_FINISHED
   │ (cualquier rechazo produce ToolResult de error y se continúa con la siguiente llamada)
   ▼
CONSULTAR (de nuevo)
```

Cualquier `emit` que lance: se propaga y el turno se detiene (Q4; única excepción: R-08, fallo de `emit(INTERRUPTED)` durante una cancelación).

## 5. Reglas de validación derivadas de los requisitos

| Regla | Origen | Dónde se aplica |
|---|---|---|
| Colaborador ausente (`None`) ⇒ error nombrándolo | FR-025 | Constructor de `AgentLoop` |
| Historial inicial: prefijo `SYSTEM`, invariantes de campos, correlación, sin llamadas pendientes | FR-001, R-04 | `_check_history` al inicio de `run_turn` |
| Respuesta del proveedor: ids de llamada no vacíos, únicos entre sí y respecto de `H` (regla canónica de HU-07-01, D-02 §4.7); tipo `ProviderResponse` | FR-024 | Tras cada `complete`, antes de añadir nada |
| Herramienta existente | FR-008(a), FR-010 | Tubería, paso `get` |
| Argumentos válidos y `dict` devuelto | FR-008(b), FR-011 | Tubería, paso `validate_args` |
| `PermissionDecision.ALLOW` explícito para ejecutar; cualquier otro valor o excepción ⇒ no se ejecuta | FR-009, FR-012–FR-014 | Tubería, paso `evaluate` |
| `Tool.run` devuelve `ToolResult` con `content: str` | FR-018 | Tubería, normalización |
