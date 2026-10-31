# Data Model — HU-06-05

No hay esquema nuevo ni tabla nueva. Los tipos son de presentación (`cli/`), inmutables.

| Tipo | Módulo | Campos | Reglas |
|---|---|---|---|
| `Style` | `cli/style.py` | `enabled: bool` | `paint(text, *names)` → texto con ANSI si `enabled`, igual si no; nombres: `bold`, `dim`, `red`, `green`, `yellow`, `cyan`; un nombre desconocido se ignora |
| `ActivityRenderer` | `cli/activity.py` | `style`, `max_pending=256`, estado `{call_id: PendingCall}` | por instancia; sin argumentos ni contenido en el estado; tope con descarte del más antiguo |
| `PendingCall` | `cli/activity.py` | `requested_at: datetime`, `ask_at: datetime \| None`, `waited: timedelta` | interno |
| `SessionRow` | `cli/session_commands.py` | `id`, `created_at`, `status`, `model: str \| None`, `goal: str \| None`, `current: bool` | `goal`, `model` y `status` se sanean y acotan al formatear |
| `ModelView` | `cli/session_commands.py` | `model`, `window_tokens`, `threshold_tokens`, `max_turns`, `max_seconds`, `max_tokens`, `max_output_tokens` | enteros ≥ 0; sin secretos |

## Constantes de presentación

| Constante | Valor | Dónde |
|---|---|---|
| `MAX_PRIMARY_CHARS` | 400 | `approval_view.py` (valor principal) |
| `MAX_VALUE_CHARS` | 200 | `approval_view.py` (resto de argumentos) |
| `MAX_ARGUMENTS_SHOWN` | 20 | igual que hoy |
| `RULE_WIDTH` | 60 | `approval_view.py` |
| `MAX_SESSIONS_SHOWN` | 10 | `session_commands.py` |
| `MAX_GOAL_CHARS` | 60 | `session_commands.py` |
| `MAX_PENDING_CALLS` | 256 | `activity.py` |

## Transiciones de estado de la sesión activa (`bootstrap._Active`)

`/nueva`: `session_id ← nueva`, `compactor ← factory(nueva)`, `closures ← []`, `history ← prefijo`. `/reanudar` y `/compactar` no cambian su semántica.
