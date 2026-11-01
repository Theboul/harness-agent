# Tareas: HU-06-02 — `preguntar_usuario` y arreglos de UX

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · `--basetemp` corto (`/c/tmp/pt44`).
**Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`. No tocar `core/redaction.py`, `adapters/storage/`, `pyproject.toml`, CI (otras sesiones).
**Mapeo a plan de sprints**: HU-06-02 (2 PHU) + arreglos de UX; presupuesto estimado 180 min.

- [x] T001 [US1] `tests/unit/core/permissions/test_open_tools.py` + `src/harness_agent/core/permissions/open_tools.py` (`OpenToolsPolicy`) + exports. Primero la prueba, vista fallar.
- [x] T002 [US1] `tests/unit/adapters/tools/test_ask_user.py` + `src/harness_agent/adapters/tools/ask_user.py` (`AskUserTool`, `Question`, `Answer`, `AskFn`) + export.
- [x] T003 [US1] `tests/unit/cli/test_question_view.py` + `src/harness_agent/cli/question_view.py`.
- [x] T004 [US1] `tests/unit/cli/test_question.py` + `src/harness_agent/cli/question.py` (`ConsoleQuestioner`) + export.
- [x] T005 [US1] `bootstrap.py`: `compose(…, ask=)`, registro, `OpenToolsPolicy`, `main()` inyecta la consola; `tests/integration/test_ask_user_loop.py` con `AgentLoop` real (AC-01, AC-02, fin de entrada).
- [x] T006 [US2] UX-a: silencio de LiteLLM en `litellm_provider.py` + prueba con módulo falso.
- [x] T007 [US2] UX-b: `approval_view.py` (efecto completo con ajuste de línea, traducción fija) + pruebas.
- [x] T008 [US2] UX-c: `render.py` línea de reintento + pruebas.
- [x] T009 Guarda `tests/architecture/test_ask_user_boundaries.py` y verificación de fronteras (`pytest tests/architecture`); diff de protegidos vacío.
- [x] T010 Cuatro puertas de calidad. `ruff format --check`, `ruff check`, `mypy src tests` en 0; `pytest`: 8416 pasadas, 48 omitidas.
- [x] T011 Documentación: `docs/PROGRESO.md` (HU-06-02 «En revisión», archivos, evidencia, registro, observaciones), `CLAUDE.md` (fila de la historia, si cabe), `.specify/feature.json`.

## Tareas humanas (Claude no las marca)

- [ ] H01 Revisión cruzada (A o B).
- [ ] H02 CI remota en Ubuntu y Windows.
- [ ] H03 A y B ratifican `OpenToolsPolicy` (regla nueva de permisos) y deciden si la respuesta debe viajar sin marca de dato externo.
- [ ] H04 El PO confirma que `permitir_texto_libre` valga `true` por defecto.

## Dependencias

T001 → T002 → T005; T003 → T004 → T005; T006, T007, T008 independientes; T009 → T010 → T011.
