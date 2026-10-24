# Data Model: HU-03-01

## Tabla `sessions`

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | TEXT | PRIMARY KEY |
| `parent_id` | TEXT | NULL; FOREIGN KEY → `sessions(id)` |
| `created_at` | TEXT | NOT NULL; ISO-8601 UTC con zona |
| `model` | TEXT | NULL |
| `goal` | TEXT | NULL |
| `status` | TEXT | NOT NULL; CHECK en (`active`, `completed`, `interrupted`) |

## Tabla `events` (solo esquema; la escribe HU-03-02)

| Columna | Tipo | Restricciones |
|---|---|---|
| `id` | TEXT | PRIMARY KEY |
| `session_id` | TEXT | NOT NULL; FOREIGN KEY → `sessions(id)` |
| `seq` | INTEGER | NOT NULL; UNIQUE con `session_id` |
| `type` | TEXT | NOT NULL |
| `content` | TEXT | NOT NULL; JSON del `payload` |
| `created_at` | TEXT | NOT NULL |
| `compacted_by` | TEXT | NULL (referencia futura a resúmenes) |

## Versión

`PRAGMA user_version = 1`.

## Tipos de Python

`StoredSession` (frozen): `id: str`, `status: str`, `created_at: datetime` (UTC), `model: str | None`, `goal: str | None`, `parent_id: str | None`.

Transición de estado: toda sesión nace `active`; los cambios de estado llegan con otras historias.
