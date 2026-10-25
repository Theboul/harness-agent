# Data Model: HU-05-03

## Existentes (sin cambios)
`Approver.request(call, details) -> ApprovalResult`; `ApprovalAction` (`APPROVE_ONCE`, `APPROVE_SESSION`, `REJECT`); `ApprovalResult(action, reason)`; `EventType.APPROVAL_REQUESTED/RESOLVED`.

## Nuevos (`core/permissions/approvals.py`)

### `ApprovalOutcome` (`@dataclass(frozen=True)`)
| Campo | Tipo | Notas |
|---|---|---|
| `approved` | `bool` | `True` solo si ejecutar está permitido |
| `action` | `ApprovalAction \| None` | `None` cuando falló cerrado |
| `source` | `str` | `"user"`, `"session_grant"`, `"approver_error"`, `"invalid_result"` |
| `reason` | `str \| None` | motivo del usuario, acotado (para HU-05-04); no va a eventos |

### `ApprovalGate`
- `__init__(approver: Approver)`; estado: `set[tuple[str, str]]` de aprobaciones de sesión (nombre, argumentos canónicos).
- `async resolve(call: ToolCall, tool: Tool, emit_requested: Callable[[], None]) -> ApprovalOutcome`.
- `build_details(call, tool) -> dict[str, Any]`: `{"tool", "arguments" (copia), "effect" (descripción), "risk"}`.

## Reglas de transición
```
ASK ─ sin aprobador ──────────────▶ deny [approval_required_unavailable]
ASK ─ grant de sesión coincide ───▶ aprobado (session_grant)
ASK ─ approve_once ───────────────▶ aprobado (user)
ASK ─ approve_session ────────────▶ aprobado (user) + recordar (tool, args)
ASK ─ reject ─────────────────────▶ deny [approval_rejected]
ASK ─ excepción / resultado inválido ▶ deny [approval_failed]
ASK ─ CancelledError ─────────────▶ propaga
```
Mensajes al modelo (`is_error=True`, categorías `approval_rejected`, `approval_failed`), acotados a 500 caracteres.
