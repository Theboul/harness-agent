# Tareas: HU-10-02 — Redacción de secretos en registros

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · `--basetemp` corto (`/c/tmp/pt45`).
**Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`.
**Mapeo a plan de sprints**: tarea de HU-10-02 (1 PHU); presupuesto estimado 120 min.

- [x] T001 [US1] Pruebas primero `tests/unit/core/test_secret_redaction.py` (patrones, conocidos, idempotencia, texto normal, rendimiento) → vistas fallar por `ImportError` (el módulo no existía).
- [x] T002 [US1] `src/harness_agent/core/secret_redaction.py` + export en `core/__init__.py`.
- [x] T003 [US2] Pruebas `tests/unit/adapters/storage/test_secret_redaction_storage.py` (mensajes, eventos, resumen) → vistas fallar por `TypeError` (argumento `redact` desconocido); parámetros `redact` en `clean_message`, `ConversationCapture`, `attach_event_recorder`, `SqliteCompactionArchive`.
- [x] T004 [US2] Cableado mínimo en `compose()` + prueba de integración `tests/integration/test_secret_redaction_resume.py` (`/reanudar` sin secreto; historial en memoria intacto). Pasó a la primera: el cableado ya existía.
- [x] T005 Guarda `ast` `tests/architecture/test_secret_redaction_boundaries.py` y verificación de fronteras (`pytest tests/architecture`).
- [x] T006 Cuatro puertas de calidad.
- [x] T007 Documentación: `docs/PROGRESO.md`, `CLAUDE.md` (fila y nota de HU-03-04), `.specify/feature.json`.

## Analyze / converge

Sin hallazgos bloqueantes: los FR-001 a FR-006 están cubiertos por T001–T005; sin tareas nuevas que añadir. Lista de comprobación de `capas-y-reglas.md` revisada contra el código: `core/` solo importa stdlib y `core.redaction`; sin E/S, entorno ni `print`; dependencias por constructor; puertos, eventos y bucle intactos; guarda `ast` nueva.

## Tareas humanas (Claude no las marca)

- [ ] H01 Revisión cruzada (A o C).
- [ ] H02 CI remota en Ubuntu y Windows.
- [ ] H03 El PO ratifica que HU-10-02 cierra PD-10 y la parte abierta de V-13.

## Dependencias

T001 → T002 → T003 → T004 → T005 → T006 → T007.
