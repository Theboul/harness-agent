# Tareas: HU-08-02 — Descubrir herramientas MCP

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Tareas del plan**: Sp4-30 (3 h), Sp4-31 (1,5 h)  
Rutas según `estructura-carpetas-harness` (ver plan). Pruebas con `--basetemp /c/tmp/pt36`. **Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`.

> Desviación de proceso: el código de T001–T004 se escribió antes que sus pruebas, de modo que no se observó el rojo previo; las pruebas se añadieron a continuación y cubren cada rama.

- [x] T001 `adapters/mcp/tool.py` (`McpTool`, `translate_tool`): nombre, descripción acotada, esquema copiado, riesgo `HIGH`; `tests/unit/adapters/mcp/test_discovery.py::TestTranslation`.
- [x] T002 `client.list_tools()` + `name`, `McpListError`, `McpSdk.page_params`; `FakeSdk` con páginas; `TestListTools`.
- [x] T003 `adapters/mcp/registration.py::register_mcp_tools`; `TestRegistration` (esquema rechazado, colisión, nombre inválido, fallo de listado, no conectado, cancelación).
- [x] T004 Cableado en `bootstrap.py` (`Composition.registry`, llamada tras `connect_all`).
- [x] T005 `tests/integration/test_mcp_tool_discovery.py` con el servidor de demostración (SC-001).
- [x] T006 Guardas: `tool.py` solo nombra `RiskLevel.HIGH`; solo `bootstrap.py` llama al registro (`test_mcp_boundaries.py`).
- [x] T007 Verificación de fronteras y calidad (`verificar-fronteras-hexagonales`): cuatro puertas + `pytest tests/architecture`, diff de protegidos vacío.
- [x] T008 Documentación: `PROGRESO.md` (En revisión), `CLAUDE.md`, skills (copias `.claude/` y `.agents/`).

## Tareas humanas (Claude no las marca)

- [ ] H1 Revisión cruzada por alguien de otra área (A o B).
- [ ] H2 CI remota en Windows y Linux.
- [ ] H3 A decide si `check_schema` se amplía (hoy se omiten las herramientas con `anyOf`/`$ref`/`format`).
