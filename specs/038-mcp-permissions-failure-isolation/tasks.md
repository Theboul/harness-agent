# Tareas: HU-08-03 + HU-08-04

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Tareas del plan**: Sp4-32 (HU-08-03), Sp4-34 (HU-08-04)  
Pruebas primero (rojo observado por la razón esperada). `--basetemp /c/tmp/ptNN`. **Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`.

- [ ] T001 `core/permissions/ask_ceiling.py` + exportación; `tests/unit/core/permissions/test_ask_ceiling.py` (ALLOW→ASK solo para nombres del conjunto, DENY/ASK intactos, conjunto vivo, falla cerrada).
- [ ] T002 `adapters/mcp/tool.py`: `run` aislado y descripción limpia; `tests/unit/adapters/mcp/test_isolation.py::TestMcpTool`.
- [ ] T003 `adapters/mcp/client.py`: estado `perdido`, tope duro; `TestClientLoss`.
- [ ] T004 `connections.py` y `registration.py`: excepciones inesperadas aisladas, `names`; `TestConnectionsIsolation`.
- [ ] T005 Cableado mínimo en `bootstrap.py` (`Composition.mcp_tool_names`, envoltura, argumento).
- [ ] T006 `tests/integration/test_mcp_permissions_agent_loop.py` (SC-001, SC-003, cadena completa con `compose`).
- [ ] T007 `tests/integration/test_mcp_failure_isolation.py` con el servidor de demostración (SC-002).
- [ ] T008 Guardas: `test_ask_ceiling_boundaries.py` y reglas nuevas en `test_mcp_boundaries.py`.
- [ ] T009 Verificación de fronteras y calidad (`verificar-fronteras-hexagonales`): cuatro puertas + `pytest tests/architecture`, diff de protegidos vacío.
- [ ] T010 Documentación: `PROGRESO.md` (HU-08-03 y HU-08-04 En revisión), `CLAUDE.md`, skills (copias `.claude/` y `.agents/`).

## Tareas humanas (Claude no las marca)

- [ ] H1 Revisión cruzada por alguien de otra área (A o B).
- [ ] H2 CI remota en Windows y Linux.
- [ ] H3 PO/A confirman la decisión «sin reconexión ni baja de herramientas» y el techo de `ASK`.
