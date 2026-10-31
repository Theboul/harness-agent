# Modelo de datos: HU-11-05

Todo en memoria; no hay esquema SQLite nuevo. Tipos inmutables (`@dataclass(frozen=True)`).

| Tipo | Campos |
|---|---|
| `FileChange` | `path`, `status` (`nuevo`/`modificado`/`eliminado`/`otro`), `added`, `removed` (`None` si es binario) |
| `ChangeSet` | `files`, `patch`, `truncated`; `total_added`, `total_removed` |
| `CriterionView` | `index`, `description`, `state` (`cumplido`, `pendiente`, `pendiente_humano`, `confirmado_humano`) |
| `ReviewView` | `ticket`, `changes`, `criteria`, `objective_met`, `objective_total`, `blockers` |
| `ReviewDecision` | `choice`, `criterion`, `reason` |

`ReviewView.can_approve` ⇔ `blockers` vacío. Bloqueos: criterio semántico sin confirmar, diff truncado.
