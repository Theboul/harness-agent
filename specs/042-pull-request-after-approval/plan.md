# Plan de implementación: HU-11-06 — Pull Request tras la aprobación

**Spec**: [spec.md](spec.md) · **Rama**: `claude/hu-11-06-pull-request-4840b5` · **Fecha**: 2026-10-31

## Resumen

Un paquete nuevo `core/pullrequest/` (borrador del PR, puertos `PullRequestHost` y `PullRequestPrompter`, flujo `PullRequestFlow`) que se engancha a `ReviewingRunner` mediante un observador opcional `CommitObserver` (único cambio en `core/review/`). Un adaptador `adapters/system/github_pull_requests.py` ejecuta `git push` y `gh pr create` (sin shell, `run`/`which` inyectables). Un confirmador de terminal `cli/pullrequest.py`. Cableado mínimo en `bootstrap.py`. Sin cambios en `core/interfaces/`, eventos ni `core/loop.py`.

## Constitution Check (reglas duras de las tres skills)

| Regla | Cumple | Nota |
|---|---|---|
| `core/` solo stdlib + `harness_agent.core`, sin E/S, sin `print`/`input` | Sí | git, `gh` y terminal por `Protocol` |
| Puertos de `core/interfaces/` y eventos sin cambios | Sí | puertos nuevos son `Protocol` del paquete (como `ChangeSource`) |
| Dataclasses `frozen=True` | Sí | `PullRequestDraft`, `ApprovedChange` |
| Falla cerrada | Sí | excepción/entrada vacía = no; sin `gh` = no se sube |
| Sin secretos | Sí | `hide_url_credentials`, sin comandos; entorno sin claves de proveedores |
| Dependencias por constructor | Sí | `run`, `which`, `environ`, host, confirmador |
| Cableado solo en `bootstrap.py` | Sí | guarda `ast` nombra `GitHubPullRequests`/`PullRequestFlow` |
| `adapters/` no importa `cli/`; solo stdlib + API pública de `core` | Sí | guarda `test_pullrequest_boundaries.py` |

**Gates**: ¿regla nueva? Sí, del flujo → `core/pullrequest/`. ¿Algo de fuera? git/`gh` → adaptador; terminal → `cli/`. ¿Conexión? `bootstrap.py`. ¿Prueba? Unitarias por capa + integración con `ReviewingRunner` real y dobles + guarda `ast`.

## Estructura

| Archivo | Fila de `estructura-carpetas-harness` |
|---|---|
| `core/pullrequest/{__init__,draft,ports,flow}.py` | regla de negocio sin E/S → `core/<paquete>/` |
| `core/review/approved.py` (+ export) | tipos del dominio de la revisión |
| `core/review/runner.py` (cambio mínimo: `after_commit`) | |
| `adapters/system/github_pull_requests.py` (+ API en `__init__`) | ejecuta procesos → `adapters/system/` |
| `cli/pullrequest.py` (+ export en `cli/__init__`) | terminal → `cli/` |
| `bootstrap.py` (`compose(pull_request_prompter=, pull_request_host=)`, `main(...)`) | conexión |
| `tests/unit/core/pullrequest/`, `tests/unit/core/review/test_runner_after_commit.py`, `tests/unit/adapters/system/test_github_pull_requests.py`, `tests/unit/cli/test_pullrequest.py`, `tests/integration/test_pull_request_session.py`, `tests/architecture/test_pullrequest_boundaries.py` | carpeta equivalente |

## Diseño

- `ApprovedChange(ticket, objective, commit_id, changes, criteria)`; `CommitObserver.on_committed(approved)`. `ReviewingRunner._commit` devuelve el id y, si lo hay, avisa al observador.
- `build_draft(approved, branch) -> PullRequestDraft(title, body, branch)` puro y total.
- `PullRequestHost`: `async available()`, `async current_branch()`, `async push(branch)`, `async create(draft) -> url`; todos pueden lanzar `PublishError(message)` (texto fijo).
- `PullRequestPrompter`: `confirm_push(branch)`, `confirm_create(draft)`, `show(lines)`. Devuelven `bool`; el de la CLI es 1/2 con EOF/3 inválidos = no.
- `PullRequestFlow.on_committed`: ver FR-002. Todas las ramas negativas acaban en `_leave_text(draft, done)` (texto listo para copiar).
- Adaptador: `shutil.which("gh")`; rama con `git symbolic-ref --short -q HEAD`; push `git push -u origin <rama>`; `gh pr create --title T --body B --head <rama>`; URL = última línea de stdout si es `https://`.

## Lista de comprobación de `capas-y-reglas.md` (al cerrar)

| Pregunta | Respuesta |
|---|---|
| ¿Regla de negocio en `core/` sin E/S? | Sí |
| ¿Puerto nuevo sin tocar `core/interfaces/`? | Sí (`Protocol` del paquete) |
| ¿Adaptador en su capa, imports permitidos? | Sí (guarda) |
| ¿Conectado solo en `bootstrap.py`? | Sí |
| ¿Falla cerrada, sin secretos? | Sí |
| ¿Prueba en la carpeta equivalente? | Sí |
| ¿Algún «no»? | No |
