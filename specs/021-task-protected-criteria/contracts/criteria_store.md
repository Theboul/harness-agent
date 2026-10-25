# Contrato: almacén de criterios (`SqliteTaskStore`)

Implementa el puerto `TaskCriteria` (sin cambios) y añade operaciones propias.

| Operación | Comportamiento |
|---|---|
| `start_task(task, *, model=None) -> StartedTask` | Atómico: sesión (`goal` = objetivo) + criterios (`passes` falso) + sello + copia de solo lectura. Cualquier fallo no deja sesión, filas ni archivo |
| `load_criteria(session_id) -> list[TaskCriteriaItem]` | Lee de SQLite en orden; valida filas y sello; ante alteración: evento `criteria_tampered` + `CriteriaIntegrityError` |
| `get_pending(session_id)` | Los de `passes` falso, mismo orden y mismas garantías |
| `mark_passes(criteria_id, evidence)` | Evidencia no vacía; solo cambia `passes` y `evidencia`; recalcula el sello; id inválido o inexistente → `CriteriaNotFound`; no expuesta como herramienta |
| `export_readonly_copy(session_id, destination)` | Escribe el JSON canónico en `destination` (reemplazo atómico, solo lectura) |
| `verify_export(session_id) -> bool` | `True` si la copia coincide con la huella; si no, la restaura, publica `criteria_tampered` y devuelve `False`; si no puede restaurar, `ExportError` |

Evento: `Event(type=CRITERIA_TAMPERED, session_id, payload={"motivo": "copia_modificada" | "copia_ausente" | "copia_no_regular" | "base_alterada"})`. Nunca lleva contenido de los criterios ni rutas.
