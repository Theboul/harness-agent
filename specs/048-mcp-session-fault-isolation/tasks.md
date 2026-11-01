# Tareas: HU-00-05.2

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Tareas del plan**: Sp4-26 (2 h), Sp4-27 (2,5 h)  
`--basetemp /c/tmp/ptNN`. **Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `tests/spikes/mcp_demo_server.py`, `docs/archivo/`, y por la sesión paralela: `core/permissions`, `bootstrap.py`, `cli/`.

- [x] T001 `tests/integration/test_mcp_session_fault_tolerance.py`: ayudantes (sesión, espía de `call_tool`, pids) y AC-01 (servidor inexistente + sano) — Sp4-26.
- [x] T002 Mismo archivo: AC-02 (caída a mitad de sesión, `[mcp_server_down]` inmediato, otro servidor y nativas siguen) — Sp4-27.
- [x] T003 Mismo archivo: servidor colgado (`[mcp_timeout]`) y ausencia de procesos huérfanos tras cerrar.
- [x] T004 Mutación de control: comprobar que cada aserción clave falla si se rompe la conducta (p. ej. cambiar el código esperado) o, si no se puede, anotarlo. Hecho: 2 de 3 pruebas fallan al cambiar los códigos esperados.
- [x] T005 Verificación de fronteras (`verificar-fronteras-hexagonales`): cuatro puertas + `pytest tests/architecture` + diff de protegidos vacío.
- [x] T006 Documentación: `PROGRESO.md` (fila HU-00-05.2 `En revisión`, registro de cambios, observaciones) y `.specify/feature.json`.

## Tareas humanas (Claude no las marca)

- [ ] H1 Revisión cruzada por alguien de otra área (B o C).
- [ ] H2 CI remota en Windows y Linux.
