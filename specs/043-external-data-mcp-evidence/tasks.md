# Tareas: HU-05-08 (solo AC-02) — Resultado MCP como dato externo

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · `--basetemp` corto (`/c/tmp/pt43`).
**Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`.
**Mapeo a plan de sprints**: tarea de evidencia de HU-05-08; presupuesto estimado 60 min.

- [x] T001 [US1] Prueba de integración `tests/integration/test_external_data_mcp.py`: marca `is_external` en éxito, `is_error` y excepción; servidor real `echo`; límite de la marca (rechazo del bucle no es externo). Vista fallar primero: la primera corrida falló por la lista de denegados dependiente del anfitrión (Windows/PowerShell) y se fijó `system_name="Linux"`.
- [x] T002 [US2] Mismo archivo: instrucción destructiva denegada, «ya aprobado» sigue preguntando, «llama sin permiso» vuelve a preguntar, eventos sin texto del servidor.
- [x] T003 Verificación de fronteras (`verificar-fronteras-hexagonales`): `pytest tests/architecture`; diff de protegidos vacío.
- [x] T004 Cuatro puertas de calidad.
- [x] T005 Documentación: `docs/PROGRESO.md` (HU-05-08 «En revisión (solo AC-02)», AC-01 pendiente, hallazgos), `.specify/feature.json`.

## Tareas humanas (Claude no las marca)

- [ ] H01 Revisión cruzada (A o B).
- [ ] H02 CI remota en Ubuntu y Windows.
- [ ] H03 A decide si hace falta una marca de origen por herramienta (más allá de `is_external`).
- [ ] H04 Implementar AC-01 (archivo con instrucción maliciosa) en otra sesión.

## Dependencias

T001 → T002 → T003 → T004 → T005.
