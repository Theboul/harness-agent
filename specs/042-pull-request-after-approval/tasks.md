# Tareas: HU-11-06 — Pull Request tras la aprobación

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · Pruebas primero; `--basetemp` corto (`/c/tmp/pt42`).
**Archivos protegidos (no tocar)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`.
**Mapeo a plan de sprints**: HU-11-06 (Sprint 3, 2 pts); presupuesto estimado 150 min en 6 tareas de 15–40 min.

- [ ] T001 [US1] `core/review/approved.py` + `ReviewingRunner(after_commit=)`; pruebas `tests/unit/core/review/test_runner_after_commit.py`.
- [ ] T002 [US1] `core/pullrequest/draft.py` (`build_draft`); pruebas `tests/unit/core/pullrequest/test_draft.py` (resumen, criterios con evidencia, centinela, límites).
- [ ] T003 [US1][US2][US3] `core/pullrequest/{ports,flow}.py` + exports de `core/__init__.py`; pruebas `tests/unit/core/pullrequest/test_flow.py` (dos confirmaciones, rechazos, sin `gh`, rama no apta, fallos, cancelación).
- [ ] T004 [US1][US3] `adapters/system/github_pull_requests.py`; pruebas `tests/unit/adapters/system/test_github_pull_requests.py` (argumentos fijos, sin shell, `gh` ausente, fallos, URL).
- [ ] T005 [US2] `cli/pullrequest.py` (`ConsolePullRequestPrompter`); pruebas `tests/unit/cli/test_pullrequest.py`.
- [ ] T006 Cableado en `bootstrap.py` (`compose`, `main`); integración `tests/integration/test_pull_request_session.py` con `ReviewingRunner` real.
- [ ] T007 Guarda `tests/architecture/test_pullrequest_boundaries.py` y verificación de fronteras (`verificar-fronteras-hexagonales`): `pytest tests/architecture`; diff de protegidos vacío; lista de `capas-y-reglas.md`.
- [ ] T008 Cuatro puertas de calidad en exit 0.
- [ ] T009 Documentación: `docs/PROGRESO.md` (En revisión), `CLAUDE.md` (tabla y convención).

## Tareas humanas (Claude no las marca)

- [ ] H01 Revisión cruzada (A o B).
- [ ] H02 CI remota en Ubuntu y Windows.
- [ ] H03 El PO ratifica remoto `origin`, base predeterminada y «sin `gh` no se sube».
- [ ] H04 Prueba manual real con `gh` instalado y un repositorio de pruebas.

## Dependencias

T001 → T003; T002 → T003; T003 → T006; T004, T005 → T006; T006 → T007 → T008 → T009.
