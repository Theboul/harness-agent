# Data Model: HU-05-04

Todo es texto y funciones puras en `core/permissions/approvals.py`, solo con la biblioteca estándar y el núcleo. No hay tablas nuevas ni cambios en SQLite, en el puerto `Approver` ni en el catálogo de eventos.

## Constantes (`core/permissions/approvals.py`)

| Nombre | Valor | Para qué |
|---|---|---|
| `MAX_REASON_CHARS` | 200 (ya existe) | Largo máximo del motivo limpio, `...` incluido |
| `MAX_REJECTION_CHARS` | 500 | Largo máximo del mensaje de rechazo con motivo (igual que `loop.MAX_MESSAGE_CHARS`; una prueba lo comprueba) |
| `REJECTED_MARK` | `[approval_rejected]` | Marca estable al principio del mensaje |
| `MIN_REASON_CHARS` | 20 | Por debajo de este espacio libre, el mensaje se devuelve sin motivo |
| `READ_LIMIT` | 1 000 | Caracteres limpios que se leen del motivo antes de seguir (privada) |
| `QUOTE_REPLACEMENT` | `’` (U+2019) | Sustituye a `'` y `"` dentro del motivo (privada) |

## `clean_reason(reason: object) -> str | None`

Entrada cualquier valor. Salida un texto de **una sola línea**, de 1 a 200 caracteres, sin caracteres de control (`Cc`), de formato (`Cf`), sustitutos (`Cs`) ni de uso privado (`Co`), sin `'` ni `"`, con las credenciales de URLs ocultas; o `None` si no hay motivo válido (no es texto, vacío, solo espacios o caracteres eliminados).

Pasos y orden: research R4. Propiedades:
- **Total**: nunca lanza con ninguna entrada.
- **Idempotente**: `clean_reason(clean_reason(x)) == clean_reason(x)`.
- **Acotada**: lee como mucho 1 000 caracteres limpios, aunque la entrada sea enorme.

## `rejection_message(tool_name: str, reason: object) -> str`

Compone el resultado del rechazo (research R2, R5):

| Entrada | Salida |
|---|---|
| `clean_reason(reason)` es `None` | `[approval_rejected] Tool '<nombre>' was rejected by the user.` (el texto actual, byte a byte) |
| Hay motivo y cabe | primera frase + advertencia fija + `'<motivo>'` |
| Hay motivo pero el espacio libre es menor que 20 caracteres | el texto sin motivo |
| Hay motivo y no cabe entero | el motivo se acorta con `...` hasta que el mensaje mide 500 |

Propiedades: empieza siempre por `[approval_rejected]`; con motivo, mide a lo sumo 500 caracteres, está en una sola línea, no contiene caracteres de control ni de formato, contiene exactamente cuatro comillas simples (las dos del nombre de la herramienta y las dos del marco del motivo; el texto fijo no tiene apóstrofes), ninguna dentro del motivo, y termina en la comilla simple de cierre.

## `ApprovalOutcome` (sin cambio de forma)

`reason` pasa a ser el motivo **ya limpio** (`clean_reason`) o `None`. Un resultado de tipo `approval_failed` (`action is None`) siempre tiene `reason = None`.

## `ConsoleApprover` (`cli/approval.py`)

Nueva constante `REASON_PROMPT = "motivo (opcional, Enter para omitir)> "`. Transiciones:

| Lectura | Resultado |
|---|---|
| `1` | `ApprovalResult(APPROVE_ONCE)` (no pide motivo) |
| `2` | `ApprovalResult(APPROVE_SESSION)` (no pide motivo) |
| `3`, luego texto con contenido | `ApprovalResult(REJECT, reason=<texto saneado>)` |
| `3`, luego línea vacía o en blanco, fin de la entrada o `/salir` | `ApprovalResult(REJECT)` |
| fin de la entrada o `/salir` en la pregunta de opción, o 3 opciones no válidas | `ApprovalResult(REJECT)` (sin cambios) |

El motivo no se escribe nunca en la salida.

## Relaciones

```text
Approver.request ─▶ ApprovalResult(action, reason) ─▶ ApprovalGate.resolve ─▶ ApprovalOutcome(reason=clean_reason(...))
        ▲                                                                                │
ConsoleApprover (lee el motivo tras «3»)                  AgentLoop._ask_approval ─▶ rejection_message(call.name, outcome.reason)
                                                                                          │
                                       ToolResult(is_error=True, content=...) ─▶ Message(TOOL) ─▶ historial ─▶ proveedor
eventos: APPROVAL_REQUESTED / APPROVAL_RESOLVED / TOOL_FINISHED  — sin cambios, sin el motivo
```
