# Tareas: SPK-01 — Spike: traducir herramientas entre OpenAI y Anthropic con LiteLLM

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Responsable**: B — Estado  
**Presupuesto**: Sp1-46 (90 min) + Sp1-47 (60 min) = 150 min; estimado 135 min.

**Archivos protegidos** (no se tocan): `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `cli/`, `tests/doubles/`, `docs/archivo/`.

- [x] **T001** Exploración con `litellm` real en un venv de ruta corta: capturar la petición y la respuesta de cada proveedor (Sp1-46, 30 min)
  - **Verificación**: scripts descartables fuera del repositorio; se confirma que se puede inyectar el transporte sin red.
- [x] **T002** [US1] Pruebas de caracterización de la ida y vuelta de una herramienta (Sp1-46, 45 min)
  - **Archivos**: `tests/spikes/test_litellm_tool_translation_spike.py`
  - **Verificación**: 11 pruebas pasan con `litellm` y se omiten sin él; el guardia de red falla ante una conexión real; `ruff` y `mypy` en 0.
- [x] **T003** [US2] Documento de hallazgos con lo comprobado, lo no comprobado y las consecuencias para el formato interno (Sp1-47, 45 min)
  - **Archivos**: `docs/decisiones/SPK-01-traduccion-herramientas-litellm.md`
- [x] **T004** Registro en `docs/PROGRESO.md` (`En curso`) y verificación final: cuatro puertas de calidad, `pytest tests/architecture`, archivos protegidos (15 min)
  - **Archivos**: `docs/PROGRESO.md`, `.specify/feature.json`

## Tareas humanas (no las marca Claude)

- [ ] **T005** Corrida con claves reales de pocos tokens para cerrar AC-01 (depende de D-IA)
- [ ] **T006** Revisión cruzada por A o C
- [ ] **T007** CI remota en `ubuntu-latest` y `windows-latest` (la prueba debe omitirse sin `litellm`)
