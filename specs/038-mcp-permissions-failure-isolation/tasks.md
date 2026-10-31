# Tareas: HU-08-03 + HU-08-04

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Tareas del plan**: Sp4-32 a Sp4-34 (HU-08-03), Sp4-35 y Sp4-36 (HU-08-04)  
Pruebas primero (rojo observado por la razón esperada). `--basetemp /c/tmp/ptNN`. **Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`.

- [x] T001 `core/permissions/ask_ceiling.py` + exportación; `tests/unit/core/permissions/test_ask_ceiling.py` (ALLOW→ASK solo para nombres del conjunto, DENY/ASK intactos, conjunto vivo, falla cerrada).
- [x] T002 `adapters/mcp/tool.py`: `run` aislado y descripción limpia; `tests/unit/adapters/mcp/test_isolation.py::TestMcpTool`.
- [x] T003 `adapters/mcp/client.py`: estado `perdido`, tope duro; `TestClientLoss`.
- [x] T004 `connections.py` y `registration.py`: excepciones inesperadas aisladas, `names`; `TestConnectionsIsolation`.
- [x] T005 Cableado mínimo en `bootstrap.py` (`Composition.mcp_tool_names`, envoltura, argumento).
- [x] T006 `tests/integration/test_mcp_permissions_agent_loop.py` (SC-001, SC-003, cadena completa con `compose`).
- [x] T007 `tests/integration/test_mcp_failure_isolation.py` con el servidor de demostración (SC-002).
- [x] T008 Guardas: `test_ask_ceiling_boundaries.py` y reglas nuevas en `test_mcp_boundaries.py`.
- [x] T009 Verificación de fronteras y calidad (`verificar-fronteras-hexagonales`): cuatro puertas + `pytest tests/architecture`, diff de protegidos vacío.
- [x] T010 Documentación: `PROGRESO.md` (HU-08-03 y HU-08-04 En revisión), `CLAUDE.md`, skills (copias `.claude/` y `.agents/`).

> Nota de proceso: las pruebas de `test_mcp_permissions_agent_loop.py` (T006) caracterizan un
> comportamiento que la cadena ya tenía (`HIGH` → preguntar, `is_external` del bucle), así que
> pasaron en verde a la primera; el rojo previo se observó en T001–T004 (módulo inexistente o
> parámetro `call_grace_s`/`names` no aceptado). El camino `_own` → `perdido` tras negociar
> (`client.py`, una rama) no tiene prueba unitaria directa: lo alcanza el servidor real solo si
> la tarea dueña falla antes de que una llamada detecte la caída.

## Tareas humanas (Claude no las marca)

- [ ] H1 Revisión cruzada por alguien de otra área (A o B).
- [ ] H2 CI remota en Windows y Linux.
- [ ] H3 PO/A confirman la decisión «sin reconexión ni baja de herramientas» y el techo de `ASK`.
