# Plan de implementación: HU-11-05 — Resumen de cambios y aprobación humana del diff

**Spec**: [spec.md](spec.md) · **Rama**: `claude/hu-11-05-diff-approval-306675` · **Fecha**: 2026-10-31

## Resumen

Núcleo puro `core/review/` (tipos del cambio, vista, mensajes, `ReviewingRunner` con el menú como máquina de estados, puertos `ChangeSource` y `ChangeReviewer` como `Protocol`, igual que `ProgressSink`). Adaptador `adapters/system/git_changes.py` (git con índice temporal y commit tras aprobar) y consola `cli/review.py` + `cli/review_view.py`. `CriteriaVerifier` gana `confirm` (misma única llamada a `mark_passes`) y un estado `confirmado_humano`. `bootstrap.py` lo cablea.

## Contexto técnico

Python 3.12, mypy estricto, ruff 100, sin dependencias nuevas. Pruebas: doble de `ChangeSource`, revisor guionado, git real solo en `tmp_path` con entorno aislado (ayudante de `test_git_real_repository.py`).

## Constitution Check (reglas duras de las tres skills)

| Regla | Cumple | Nota |
|---|---|---|
| `core/` solo stdlib y `harness_agent.core`; sin E/S, `print`, entorno | Sí | git y terminal son `Protocol` inyectados |
| `core/interfaces/`, eventos y `core/loop.py` sin cambios | Sí | `criterion_verified` solo gana un valor de `status` |
| E/S en `adapters/` (subprocess) | Sí | `adapters/system/git_changes.py` |
| Terminal en `cli/` | Sí | `cli/review.py`, `cli/review_view.py` |
| `cli/` solo stdlib + API pública de `core` | Sí | |
| Adaptador no importa `cli` ni otro adaptador | Sí | |
| Dependencias por constructor; entorno inyectado | Sí | `run`, `environ`, `root` |
| Falla cerrada | Sí | sin git, sin decisión, truncado, semánticos pendientes → no commit |
| Una sola llamada a `mark_passes` | Sí | `verifier.py::_store_pass` (confirm y verify) |
| Sin secretos | Sí | sin comandos ni evidencia en la vista; credenciales de URL ocultas |
| `bootstrap.py` única raíz, cambio mínimo | Sí | `reviewer`, `changes` en `compose`; `main()` inyecta la consola |
| Guarda `ast` del módulo nuevo | Sí | `tests/architecture/test_review_boundaries.py` |

**Gates**: ¿regla nueva en `core/`? sí (cuándo se revisa, qué se exige para aprobar). ¿Necesita algo de fuera? git y terminal → puertos de núcleo (no se tocan los de `core/interfaces/`). ¿Quién implementa? `adapters/system/` y `cli/`. ¿Conexión? `bootstrap.py`.

## Estructura (fila de `estructura-carpetas-harness`)

| Archivo | Fila |
|---|---|
| `core/review/{__init__,changes,view,messages,decision,runner}.py` | regla de dominio → subpaquete de `core/` |
| `adapters/system/git_changes.py` | `subprocess`/disco → `adapters/system/` |
| `cli/review.py`, `cli/review_view.py` | lee/imprime terminal → `cli/` (patrón `approval.py` + `approval_view.py`) |
| `core/verification/{outcomes,verifier}.py`, `cli/criteria.py` (cambios) | continuidad de HU-11-04.1 |
| `bootstrap.py` | conexión |
| `tests/unit/core/review/`, `tests/unit/adapters/system/test_git_changes.py`, `tests/unit/cli/test_review*.py`, `tests/integration/test_review_session.py`, `tests/integration/test_git_changes_real.py`, `tests/architecture/test_review_boundaries.py` | carpeta equivalente |

## Diseño

- `changes.py`: `FileChange(path, status, added, removed)`, `ChangeSet(files, patch, truncated)` (+ totales), `ChangeSource` Protocol (`async snapshot() -> ChangeSet`, `async commit(message) -> str`), `ChangeSourceError(reason)`.
- `view.py`: `CriterionView`, `ReviewView(ticket, changes, criteria, objective_met, objective_total, blockers)` con `can_approve`; `build_view`.
- `decision.py`: `Choice` (APPROVE, REJECT, CONFIRM, REJECT_CRITERION, NONE), `ReviewDecision(choice, criterion, reason)`, `ChangeReviewer` Protocol (`async choose(view)`, `inform(text)`).
- `messages.py`: `commit_message`, `rejection_notice`, `criterion_rejection_notice` (con `clean_reason`).
- `runner.py`: `TaskRunner` y `CriterionConfirmer` Protocol; `ReviewingRunner(inner, source, reviewer, criteria, confirmer, *, session_id, ticket, objective)`. `run(task, history)` corre `inner`; si `completed`, objetivos cumplidos y hay cambios → bucle de revisión.
- `GitChanges`: lectura con `GIT_INDEX_FILE` temporal (`read-tree HEAD` o `--empty`, `add -A -- . :(exclude)…`, `diff --cached --no-renames --no-ext-diff --no-textconv` en `--numstat -z`, `--name-status -z` y parche); commit con `add -A` + `commit -m` + `rev-parse --short HEAD`. `run` inyectable.

## Riesgos

El agente puede hacer `git commit` por el shell (la política pregunta): no pasa por la revisión. Los hooks de git de la persona corren al hacer el commit (`.git` está protegido del agente).

## Lista de comprobación de `capas-y-reglas.md` (revisada al cerrar)

| Pregunta | Respuesta |
|---|---|
| ¿`core/` importa solo stdlib y `harness_agent.core`? | Sí (`test_review_boundaries.py`) |
| ¿El núcleo evita E/S, entorno, configuración y terminal? | Sí; git y terminal son `Protocol` inyectados |
| ¿Puertos de `core/interfaces/`, eventos y bucle sin cambios? | Sí (diff de protegidos vacío) |
| ¿Adaptador y consola en su capa y con imports permitidos? | Sí |
| ¿Dependencias por constructor? | Sí |
| ¿Conectado solo en `bootstrap.py`? | Sí (guarda: solo `bootstrap.py` nombra `GitChanges`/`ReviewingRunner`) |
| ¿Falla cerrada? | Sí |
| ¿Prueba de contrato del adaptador real? | Sí, git real en repositorio temporal |
| ¿Algún «no»? | No hay |
