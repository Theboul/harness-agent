# Data Model: HU-11-04.1

No hay tablas ni columnas nuevas: el almacén de HU-11-01 ya guarda el comando, la condición, `passes` y la evidencia. Todos los tipos nuevos son `@dataclass(frozen=True)` o `Enum` y viven en `core/` (solo biblioteca estándar); no cambia ningún puerto ni entidad compartida.

## `core/tasks/condition.py` (nuevo)

| Nombre | Forma | Notas |
|---|---|---|
| `Condition` | `@dataclass(frozen=True)`: `operator: str` (`"=="` o `"!="`), `value: int` (0 a 4 294 967 295) | La condición ya entendida |
| `parse_condition(text: object) -> Condition \| None` | Pura y total | `None` si no es exactamente una de las dos formas (contrato) |
| `condition_met(condition: Condition, exit_code: int \| None) -> bool` | Pura y total | `exit_code is None` → `False` |
| `MAX_EXIT_CODE` | `4_294_967_295` | |

Error nuevo del analizador: `TaskFormatError("condicion_no_soportada")` en `core/tasks/errors.py`.

## `core/verification/` (nuevo subpaquete)

### `outcomes.py`

| Tipo | Campos y reglas |
|---|---|
| `CriterionStatus` (`str, Enum`) | `MET="cumplido"`, `NOT_MET="no_cumplido"`, `REGRESSION="regresion"`, `NOT_RUN="no_ejecutado"`, `TIMED_OUT="tiempo_agotado"`, `TAMPERED="alterado"`, `PENDING_HUMAN="pendiente_humano"` |
| `NotRunCause` (`str, Enum`) | `DENIED="denegado"`, `NO_APPROVER="sin_aprobador"`, `NOT_APPROVED="no_aprobado"`, `UNSUPPORTED_CONDITION="condicion_no_soportada"`, `ERROR="error"` (el runner no pudo ejecutarlo: sin área, intérprete no disponible…) |
| `TaskState` (`str, Enum`) | `VERIFIED="verificada"`, `PENDING_HUMAN="pendiente_humano"`, `NOT_FINISHED="no_terminada"` |
| `CommandOutcome` | `ran: bool`; `exit_code: int \| None`; `timed_out: bool = False`; `output: str = ""`; `timeout_seconds: float \| None = None`. Invariantes: `ran` falso ⇒ sin código ni salida; `timed_out` ⇒ `exit_code is None` |
| `CriterionResult` | `index: int` (desde 1); `description: str`; `status: CriterionStatus`; `exit_code: int \| None`; `program: str \| None`; `output: str` (ya acotada y sin credenciales; vacía salvo en estados corregibles); `cause: NotRunCause \| None`; `timeout_seconds: float \| None` |
| `VerificationReport` | `results: tuple[CriterionResult, ...]` (uno por criterio, en el orden de la tarea); propiedades `state: TaskState`, `correctable: tuple[CriterionResult, ...]` (`no_cumplido`, `regresion`, `tiempo_agotado`) |
| `task_state(statuses: Iterable[str]) -> TaskState` | Pura y total. Cualquier estado distinto de `cumplido` y `pendiente_humano` (o un valor desconocido) ⇒ `NOT_FINISHED`; si no, con algún `pendiente_humano` ⇒ `PENDING_HUMAN`; si no, `VERIFIED`. Una lista vacía ⇒ `NOT_FINISHED` (falla cerrada) |

### `verifier.py`

`CriteriaVerifier(store, task, policy, tool, run, emit, *, gate=None, tool_name, command_argument, timeout_argument, declared_timeouts)`:

| Colaborador | Tipo | Quién lo da |
|---|---|---|
| `store` | `TaskCriteria` (puerto existente) | `Composition.task_store` |
| `task` | `TaskDefinition` | `compose(task=)` |
| `policy` | `PermissionPolicy` | la cadena de `compose()` |
| `tool` | `Tool` (para la descripción y el riesgo que ve el aprobador) | `registry.get("shell")` |
| `run` | `Callable[[ToolCall], Awaitable[CommandOutcome]]` | `adapters/tools/shell_outcome.py` |
| `emit` | `Callable[[EventType, dict[str, Any]], None]` | `bootstrap.py` (fabrica `Event` con el `session_id`) |
| `gate` | `ApprovalGate \| None` | `ApprovalGate(approver)` o `None` |
| `declared_timeouts` | `Mapping[str, int]` (comando declarado → segundos) | derivado de `task.commands` |

`async verify(session_id: str) -> VerificationReport`. Es el **único** lugar del código que llama a `mark_passes`.

Algoritmo por criterio (en orden): semántico → `PENDING_HUMAN`; objetivo → emparejar (R5) → condición (R11) → llamada (R2) → política → aprobación (R3) → ejecución → evaluar. Cumple y no estaba cumplido → `mark_passes(id, evidencia)` y `MET`; cumple y ya estaba cumplido → `MET` sin escribir; no cumple y estaba cumplido → `REGRESSION`; no cumple y no → `NOT_MET`; tiempo agotado → `TIMED_OUT`. Después publica `criterion_verified` (un evento por criterio, también los semánticos).

Cancelación: `asyncio.CancelledError` nunca se captura. Cualquier otra excepción del almacén al marcar convierte ese criterio en `NOT_RUN` con causa `ERROR` (no se da por cumplido) sin repetir datos.

### `feedback.py`

| Función | Resultado |
|---|---|
| `compose_feedback(report) -> Feedback \| None` | `Feedback(external: str, notice: str)`; `None` si no hay nada corregible |
| `evidence_text(exit_code: int, output: str) -> str` | `Código de salida: <N>` + salto de línea + salida, ≤ 2 000 caracteres |
| `program_name(command: str) -> str \| None` | Primer elemento del comando sin ruta si cumple `[A-Za-z0-9._+-]{1,40}`; si no, `None` |
| `one_line(text: str, limit: int) -> str` | Una línea, sin caracteres `Cc`, `Cf`, `Cs`, `Co`, con `...` si se corta |
| Constantes | `MAX_OUTPUT_PER_CRITERION=1500`, `MAX_OUTPUT_TOTAL=6000`, `MAX_LISTED=20`, `MAX_EVIDENCE_CHARS=2000`, `MAX_DESCRIPTION_NOTICE=80`, `MAX_DESCRIPTION_EVENT=120` |

### `runner.py`

`VerifyingRunner(run_turn, verifier, session_id)`, con `async run(task: str, history: list[Message]) -> TurnResult`. Sin atributos mutables de rondas (no hay contador). Detalle del algoritmo en `research.md` R6.

## `adapters/tools/shell_outcome.py` (nuevo)

| Nombre | Función |
|---|---|
| `outcome_from_result(result: ToolResult) -> CommandOutcome` | Interpreta las etiquetas de `ShellTool` (R1); lo desconocido es `ran=False` |
| `make_command_runner(registry: ToolRegistry, tool_name: str) -> CommandRunner` | Valida los argumentos con el registro, ejecuta la herramienta del registro y convierte el resultado; cualquier fallo de validación es `ran=False` |

## Evento `criterion_verified` (carga) y estado de la CLI

Ver `contracts/criterion_verified_event.md` y `contracts/cli_status_contract.md`. La CLI no guarda nada en disco: `CriteriaBoard` (en memoria) conserva el último estado de cada criterio de la sesión.

## Relaciones

```text
TaskDefinition.criteria[i]  ──(posición)──  TaskCriteriaItem (SQLite, fuente de verdad del comando)
        │                                         │
        └── condición ── parse_condition ──┐      └── mark_passes (solo el verificador)
                                           ▼
 CriteriaVerifier ── policy / gate / run ── CommandOutcome ── CriterionResult ── VerificationReport
        │                                                                              │
        ├── emit(criterion_verified)                                   compose_feedback ┘
        └── VerifyingRunner: COMPLETED → verify → (corregible) mensaje externo + aviso → otro turno
```
