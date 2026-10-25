# Implementation Plan: Aprobación con detalle (HU-05-03)

**Branch**: `feat/hu-05-03-approval-with-detail` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)

## Summary

Cuando la política resuelve «preguntar», el bucle ya no deniega: delega en una **puerta de aprobación** del núcleo (`core/permissions/approvals.py`) que emite `APPROVAL_REQUESTED`, espera al `Approver` (puerto existente), aplica falla cerrada y recuerda las aprobaciones de sesión (herramienta + argumentos exactos); el bucle emite `APPROVAL_RESOLVED` y ejecuta o rechaza. La CLI aporta un `ConsoleApprover` que muestra herramienta, argumentos y efecto y lee la opción; `bootstrap.py` lo cablea. Sin aprobador el comportamiento de Sprint 1 no cambia. Puertos y catálogo de eventos **no cambian**; `core/loop.py` cambia lo mínimo (autorizado por el usuario como A, 2026-10-25).

## Technical Context

- **Language/Version**: Python 3.12, sin dependencias de ejecución nuevas.
- **Testing**: pytest (`asyncio_mode = "auto"`), `ScriptedProvider`/`FakeProvider`, `RecordingEventBus`, `DummyApprover` de `tests/doubles/` (sin dobles nuevos), `make_rig` de `tests/core/support.py`.
- **Constraints**: `core/` solo stdlib + `harness_agent.core`; sin `print`/`input`; falla cerrada; cobertura 100 % del módulo nuevo.
- **Scale/Scope**: una sesión, un aprobador, aprobaciones de sesión en memoria.
- **NEEDS CLARIFICATION**: ninguna (Q1 resuelta: argumentos exactos).

## Constitution Check

| Principio / regla | Cumplimiento |
|---|---|
| I — una historia por spec | solo HU-05-03; `specs/019-approval-with-detail` |
| II — microtareas 15–40 min | `tasks.md` con tareas acotadas, pruebas primero |
| III — Python 3.12 tipado, modular | `mypy --strict`, funciones pequeñas, docstrings en inglés |
| IV — pruebas, calidad, CI en dos SO | cuatro puertas + `pytest tests/architecture`; `ci.yml` no cambia; sin pruebas dependientes de POSIX |
| V — criterios inmutables | AC-01 y AC-02 de la ficha sin cambios |
| VI — disciplina de sprints | Sprint 2, área C; nada de HU-05-04/05-02/01-06 |
| VII — consulta quirúrgica | solo fichas de HU-05-03/04, plan Sp2-29..31 y archivos citados |
| VIII — `PROGRESO.md` | tarea de cierre: fila a `En revisión`, registro, observaciones |
| IX — DoD y verificación humana | tareas humanas finales sin marcar |
| X — `docs/archivo/` | no se toca |
| V-01 / el núcleo no imprime | `ApprovalGate` solo emite eventos; la lectura/escritura está en `cli/` |
| V-02 / falla cerrada | sin aprobador, excepción, resultado inválido, entrada agotada → denegar; cancelación se propaga |
| V-13 / secretos | las cargas de eventos no llevan valores de argumentos; la CLI redacta argumentos con nombre de clave |
| D-01 (asyncio) | `Approver.request` es `async`; `CancelledError` no se traga |
| Puertos / eventos | `Approver`, `ApprovalResult`, `ApprovalAction`, `APPROVAL_*` ya existen: **sin cambios** |
| Archivo protegido `core/loop.py` | cambio mínimo autorizado por el usuario (A) el 2026-10-25; ver Complexity Tracking |
| Skills del proyecto | recorridos abajo |

### Decision Gates (`arquitectura-hexagonal-clean`)

| Pregunta | Resultado |
|---|---|
| ¿Regla nueva? | Sí: esperar la decisión, falla cerrada y alcance de sesión → `core/permissions/approvals.py`, exportado en `core/__init__.py` |
| ¿Necesita algo de fuera? | Sí: preguntar al humano → puerto `Approver` existente (sin cambios) |
| ¿Quién lo implementa? | `ConsoleApprover` en `cli/approval.py` (terminal) |
| ¿Cómo se conecta? | Constructor de `AgentLoop(…, approver=None)` y `compose(…, approver=…)`; `main()` crea el `ConsoleApprover` con los flujos reales |
| ¿Cómo se prueba? | Núcleo con `DummyApprover` y `RecordingEventBus`; CLI con `StringIO`; integración con el bucle real |
| ¿Asíncrono? | `Approver.request` sí; `ApprovalGate.resolve` es corutina; el resto síncrono |

### Lista de comprobación (`capas-y-reglas.md`)

- [x] ¿La regla de negocio está en `core/`? Sí (`approvals.py`).
- [x] ¿Todo lo externo pasa por un puerto? Sí (`Approver`).
- [x] ¿Puertos, entidades y eventos sin cambios? Sí. `core/loop.py` cambia (no es un puerto) con autorización de A.
- [x] ¿Errores externos traducidos sin reproducir valores? Sí: el aprobador que falla se resuelve como `approver_error` sin reproducir el mensaje.
- [x] ¿Inyección por constructor y cableado solo en `bootstrap.py`? Sí.
- [x] ¿Núcleo probado con dobles, sin red ni disco? Sí.
- [ ] ¿Adaptador real con prueba de contrato en `tests/contracts/`? **No**: `ConsoleApprover` es CLI, no adaptador de `adapters/`; se prueba en `tests/unit/cli/` e integración. Se reutiliza el doble `DummyApprover` sin contrato nuevo (no hay segundo implementador hasta MCP/subagentes).
- [x] ¿`pytest tests/architecture` + guarda nueva? Sí: `test_approvals_boundaries.py`; se actualiza `test_loop_boundaries.py` (el bucle ya puede emitir eventos de aprobación, no los de límite).
- [x] ¿El núcleo emite eventos en lugar de imprimir? Sí.
- [x] ¿Lo público está exportado? Sí (`ApprovalGate`, `ApprovalOutcome`).
- [x] ¿Falla cerrada? Sí.
- [ ] ¿Otro integrante revisó el cambio? Pendiente (tarea humana).

## Project Structure

### Documentation (this feature)

```text
specs/019-approval-with-detail/
├── spec.md  plan.md  research.md  data-model.md  quickstart.md  tasks.md
├── checklists/requirements.md
└── contracts/approval_flow.md
```

### Source Code (ruta y fila de `estructura-carpetas-harness`)

| Archivo | Fila que lo justifica |
|---|---|
| `src/harness_agent/core/permissions/approvals.py` (nuevo) | «Regla de negocio (permisos…) → subpaquete de `core/`» |
| `src/harness_agent/core/permissions/__init__.py`, `core/__init__.py` (exportan) | «Todo lo público de `core/` se exporta» |
| `src/harness_agent/core/loop.py` (cambio mínimo, protegido) | el bucle es quien resuelve «preguntar» |
| `src/harness_agent/cli/approval.py` (nuevo) | «Imprime o lee de la terminal → `cli/`» |
| `src/harness_agent/cli/render.py`, `cli/__init__.py` | el texto de cada evento vive en `render.py`; se exporta `ConsoleApprover` |
| `src/harness_agent/bootstrap.py` | «Unir piezas y elegir implementaciones» |
| `tests/unit/core/permissions/test_approvals.py` | espejo del módulo |
| `tests/core/test_loop_approval.py` | espejo de `core/loop.py` (los tests del bucle viven en `tests/core/`) |
| `tests/unit/cli/test_approval.py`, `tests/unit/cli/test_render_approval.py` | espejo de `cli/` |
| `tests/integration/test_approval_agent_loop.py` | bucle real + política protegida + CLI |
| `tests/architecture/test_approvals_boundaries.py` (nuevo) + `test_loop_boundaries.py`, `test_cli_boundaries.py` (ajuste) | guarda del módulo nuevo |
| `tests/integration/test_event_bus_agent_loop.py` | se invierte `test_observation_the_loop_does_not_emit_approval_requested_yet` |

## Diseño (detalle en `data-model.md` y `contracts/approval_flow.md`)

1. En `_process_call`, tras `PERMISSION_DECIDED`, si la decisión fue «preguntar» **y hay aprobador**, el bucle llama a `ApprovalGate.resolve(...)`; si no hay aprobador, la rama actual (`[approval_required_unavailable]`) queda **intacta**.
2. `ApprovalGate.resolve` emite `APPROVAL_REQUESTED` (vía una función de emisión que le pasa el bucle: el gate no conoce el bus), consulta las aprobaciones de sesión, o pide al `Approver`; devuelve un `ApprovalOutcome` inmutable.
3. El bucle emite `APPROVAL_RESOLVED` y ejecuta con los argumentos mostrados o devuelve `[approval_rejected]`/`[approval_failed]` como resultado de herramienta (error).
4. Las aprobaciones de sesión solo se consultan en la rama «preguntar»: una denegación (`ProtectedPolicy`, HU-05-02) se decide antes y nunca llega a la puerta (FR-008).
5. HU-05-04: `ApprovalOutcome.reason` conserva el motivo del `ApprovalResult` (acotado); hoy el bucle no lo envía al modelo.

## Hallazgos y notas para `PROGRESO.md` al cerrar

- Cambio mínimo en `core/loop.py` por autorización del usuario (A): parámetro opcional `approver`, rama nueva en `_process_call`, nueva fase de cancelación `approval`.
- La regla de lectura/«sin área» sigue preguntando (hallazgo de HU-05-01 y HU-00-08): con aprobación interactiva, sin área el usuario recibiría una pregunta que nunca podría aprobarse con éxito (la herramienta devuelve `[sin_area]`); conviene que la política deniegue directamente.
- Generalizar el patrón de sesión (misma ruta, programa y subcomando) queda para después de HU-05-02.
- `Approver.request` no lleva `session_id`: no se puede indicar qué subagente pide (HU-09-01).
- Prompt síncrono: `input()` bloquea el bucle de eventos mientras se espera; una cancelación (Ctrl-C) actúa al volver la lectura (limitación de la lectura de `TextIO`).

## Complexity Tracking

| Decisión | Por qué | Alternativa descartada |
|---|---|---|
| Tocar `core/loop.py` | Única forma de esperar al usuario antes de ejecutar | Wrapper de `PermissionPolicy`: la política es síncrona y no puede esperar |
| `ApprovalGate` aparte en `core/permissions/` | Mantiene el bucle delgado y la política sin estado | Lógica de sesión en `policy.py`: rompería «la política no tiene estado» (guarda existente) |
| Aprobaciones de sesión en el gate (vida = vida del bucle) | El bucle se crea una vez por sesión en `compose` | Persistirlas: HU-05-05 |
| `ConsoleApprover` lee con `readline` síncrono | Igual que `run_cli`; sin hilos | `asyncio` con executor: complejidad y cancelación ambigua |
| `compose(approver=None)` por defecto sin aprobador | Los tests existentes de `compose` no leen stdin; `main()` cablea el real | Cablear siempre uno real: bloquearía pruebas |
