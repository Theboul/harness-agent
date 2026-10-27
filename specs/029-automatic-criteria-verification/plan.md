# Implementation Plan: HU-11-04.1 — Verificación automática de criterios objetivos: solo el harness marca passes

**Branch**: `gustavo` (directorio de la spec: `029-automatic-criteria-verification`) | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/029-automatic-criteria-verification/spec.md`

## Summary

Cuando el agente propone terminar, el harness ejecuta por su cuenta el comando de **todos** los criterios objetivos de la tarea, bajo la misma política de permisos que el shell del agente, y es el **único** que marca `passes`. Piezas nuevas, todas puras y en `core/` salvo el adaptador del shell y la CLI:

- `core/tasks/condition.py`: la condición esperada (`codigo_salida == N` / `!= N`, nada más) y su evaluación. El analizador de la tarea la valida al cargar.
- `core/verification/`: `CriteriaVerifier` (orquesta: emparejar, política, aprobación, ejecución, marcar, publicar), la composición del aviso al agente y de la evidencia, el estado de los criterios y de la tarea, y `VerifyingRunner` (detecta que el agente propone terminar y abre la ronda de corrección).
- `adapters/tools/shell_outcome.py`: ejecuta por la herramienta `shell` del registro (hereda recorte, ocultado de credenciales, tiempo y cancelación) y convierte su resultado en un `CommandOutcome`.
- `cli/`: el estado de cada criterio (`criterion_verified`, con una suscripción aparte) y el comando `/criterios` (parámetro opcional de `run_cli`).
- `bootstrap.py`: solo cablea el verificador y el runner cuando hay tarea.

No cambian `core/loop.py`, los puertos, `core/events.py` (el evento `criterion_verified` ya existe), `core/redaction.py` ni la política de permisos.

## Technical Context

**Language/Version**: Python 3.12; solo biblioteca estándar en `core/`.

**Primary Dependencies**: ninguna nueva. Reutiliza `ApprovalGate` (HU-05-03), `truncate_output` (HU-02-02), `hide_url_credentials` (a través de la herramienta shell), `TaskCriteria`/`SqliteTaskStore.mark_passes` (HU-11-01), `ExactCallPolicy` y la cadena de políticas (HU-11-03/05-02/11-02).

**Storage**: SQLite sin cambios de esquema (HU-11-01 ya guarda comando, condición, `passes` y evidencia). La evidencia se escribe solo al cumplir.

**Testing**: pytest (`asyncio_mode = "auto"`), `FakeProvider`, dobles existentes de `tests/doubles/` (sin dobles nuevos), `SqliteTaskStore` en `tmp_path`, shell doble que registra (patrón de HU-11-03), `ConsoleApprover` sobre `io.StringIO`. Pruebas al azar con semilla fija 20261029. Un flujo con shell real y `python -c` triviales (se omite si no hay intérprete).

**Target Platform**: Windows y Linux (CI de ambos).

**Project Type**: biblioteca/CLI hexagonal.

**Performance Goals**: los comandos de verificación tienen el tiempo máximo del shell (120 s) o el declarado (≤ 600 s); el aviso y la evidencia están acotados.

**Constraints**:
- sin cambios en `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py` ni en la política de permisos;
- `core/` no importa `cli/` ni `adapters/`;
- único escritor de passes (guarda `ast` sobre todo `src/`);
- falla cerrada: lo denegado no se ejecuta ni se pregunta, lo preguntado sin aprobador no se ejecuta;
- ni el comando ni la salida ni credenciales en eventos, errores o evidencia.

**Scale/Scope**: unos 5 módulos nuevos en `core/` (más `condition.py`), 1 adaptador, 1 módulo de CLI y modificaciones pequeñas en el analizador de la tarea, `cli/app.py` y `bootstrap.py`; unos 14 archivos de pruebas y 1 guarda.

## Constitution Check

*GATE: pasa antes de la Fase 0 y se revisa tras la Fase 1.*

| Principio / regla | Cumplimiento |
|---|---|
| I. Una historia, una spec | Solo HU-11-04.1 (Sp2-49 a Sp2-53). Pasa |
| II. Microtareas de 15–40 min | 9 tareas, ninguna de más de 40 min. Pasa |
| III. Código modular, tipado, Python 3.12 | Módulos pequeños, `dataclass(frozen=True)`, `mypy` del repo. Pasa |
| IV. Pruebas y CI multiplataforma | Comandos de prueba triviales (`python -c`); el shell real solo en un flujo. Pasa |
| V. Criterios inmutables | AC-01 a AC-04, flujo y reglas copiados tal cual (comprobado). Pasa |
| VI. Disciplina de sprints | Fuera: PD-06, `main()` cargando tareas, confirmación humana de semánticos, revocar passes. Pasa |
| VII. Consulta quirúrgica | Ancla `#hu-11-04.1`, specs 021/025/026/027/028 y el código citado. Pasa |
| VIII. PROGRESO.md | Fila de inicio y cierre (`En revisión`) con observaciones |
| IX. DoD estricta | Tareas humanas H1–H6 |
| X. `docs/archivo/` | No se toca. Pasa |
| V-02, V-15, V-17 | Una aprobación nunca anula una denegación (la verificación consulta la cadena existente); solo el harness marca passes (V-15); la salida de los comandos es contenido externo enmarcado y marcado. Pasa |

**Hard Rules de las skills del proyecto**

- **`arquitectura-hexagonal-clean`**: la regla (verificar, componer el aviso, decidir el estado) es pura y vive en `core/verification/`. Lo externo entra por colaboradores inyectados que ya existen: `TaskCriteria` (puerto), `PermissionPolicy` (puerto), `ApprovalGate` sobre el puerto `Approver`, y la herramienta `shell` por el registro; el único código nuevo que interpreta texto de un adaptador (`ShellTool`) está en un adaptador. No se crea ni se cambia ningún puerto. Todo se conecta solo en `bootstrap.py`.
- **`estructura-carpetas-harness`**: rutas en la tabla de abajo; un subpaquete nuevo de `core/` (regla de negocio) y archivos nuevos en `adapters/tools/` y `cli/`.
- **`verificar-fronteras-hexagonales`**: se añade `tests/architecture/test_verification_boundaries.py` (módulo nuevo de `core/`), con el único escritor de passes sobre todo `src/`, y se vigila que `adapters/tools/shell_outcome.py` y `cli/criteria.py` entren en las guardas existentes.

### Recorrido de los *Decision Gates* (`arquitectura-hexagonal-clean`)

| Pregunta | Respuesta |
|---|---|
| ¿Regla o comportamiento nuevo? | Sí: verificar criterios y decidir el estado de la tarea, en `core/verification/` (la condición, en `core/tasks/`); exportado en `core/__init__.py` |
| ¿Necesita algo de fuera? | Sí, y ya existe: almacén de criterios, política, aprobación, herramienta shell, bus. Ningún puerto nuevo |
| ¿Quién lo implementa? | `SqliteTaskStore` (ya existe), la herramienta `shell` (ya existe) y un adaptador pequeño que traduce su resultado |
| ¿Cómo se conecta? | Inyección en constructor; `bootstrap.py` monta el verificador y el runner solo con tarea |
| ¿Cómo se prueba? | Núcleo con dobles y almacén en `tmp_path`; adaptador con la herramienta real y un `Shell` doble (fija las etiquetas); integración con `compose()` |
| ¿Es asíncrono? | `verify` y el runner sí (esperan al aprobador y a la herramienta); la condición, el aviso y el estado no |

### Lista de comprobación de `capas-y-reglas.md` (respuesta de diseño; se revisa de nuevo al cerrar)

| Punto | Resp. | Justificación |
|---|---|---|
| ¿Regla de negocio en `core/` y no en un adaptador? | Sí | `core/verification/`, `core/tasks/condition.py` |
| ¿Todo lo externo pasa por un puerto con tipos del dominio? | Sí | `TaskCriteria`, `PermissionPolicy`, `Approver`, `Tool`/`ToolRegistry`, `EventBus` (vía `emit` inyectado) |
| ¿Puertos, entidades y eventos sin cambios? | Sí | Ninguno cambia; `criterion_verified` ya existía |
| ¿Errores sin reproducir valores? | Sí | Mensajes fijos; el comando y la salida no entran en ellos |
| ¿Inyección y conexión solo en `bootstrap.py`? | Sí | Se añaden dos piezas al cableado |
| ¿Núcleo probado con dobles, sin red, disco ni claves? | Sí | El almacén en `tmp_path` y el shell doble; el shell real solo en un flujo marcado |
| ¿Prueba de contrato del adaptador? | Sí | `test_shell_outcome.py` ejecuta la `ShellTool` real con un `Shell` doble |
| ¿`pytest tests/architecture` con la guarda nueva? | Sí (diseño) | `test_verification_boundaries.py` |
| ¿Eventos en lugar de imprimir? | Sí | `criterion_verified`; la CLI lo dibuja |
| ¿Lo público exportado en `core/__init__.py`? | Sí | Lista en el modelo de datos |
| ¿Falla cerrada y secretos? | Sí | Denegado/preguntado sin aprobador no se ejecuta; comando solo si coincide exactamente; sin comando ni credenciales en eventos |
| ¿Otro integrante revisó el cambio? | No (pendiente) | H3 |

**Resultado del gate**: pasa. Desviaciones en *Complexity Tracking*.

**Revisión contra el código (T008)**: las respuestas se mantienen. Dos hallazgos de la implementación: (1) `runner.py` no puede importar `core.loop` (la guarda existente `test_loop_boundaries` lo prohíbe), así que lee el estado del turno por un protocolo y no cambia ninguna prueba; (2) `CommandOutcome.exit_code` tiene valor por defecto `None`. Único «No»: la revisión cruzada (H3), pendiente de otra persona.

## Project Structure

### Documentation (this feature)

```text
specs/029-automatic-criteria-verification/
├── spec.md · plan.md · research.md (R1–R15) · data-model.md · quickstart.md
├── contracts/
│   ├── condition_contract.md          # gramática y ejemplos
│   ├── agent_notice_contract.md       # aviso, evidencia y nombre del programa (texto exacto)
│   ├── criterion_verified_event.md    # carga del evento
│   └── cli_status_contract.md         # líneas y estado en la CLI
├── checklists/requirements.md
└── tasks.md                           # /speckit-tasks
```

### Source Code y fila de `estructura-carpetas-harness` que justifica cada ruta

| Ruta | Nuevo/Mod. | Fila |
|---|---|---|
| `src/harness_agent/core/tasks/condition.py` | Nuevo | Regla de negocio → `core/tasks/` (área A) |
| `src/harness_agent/core/tasks/parser.py`, `errors.py`, `__init__.py` | Mod. (`condicion_no_soportada`; exportaciones) | Ídem |
| `src/harness_agent/core/verification/{__init__,outcomes,feedback,verifier,runner}.py` | Nuevo | Regla de negocio → subpaquete de `core/` (área A) |
| `src/harness_agent/core/__init__.py` | Mod. (exportaciones) | Lo público se exporta en `core/__init__.py` |
| `src/harness_agent/adapters/tools/shell_outcome.py`, `__init__.py` | Nuevo / Mod. | Código que interpreta el resultado de `ShellTool` → `adapters/tools/` (área C; visto bueno en H2) |
| `src/harness_agent/cli/criteria.py` | Nuevo | Imprime → `cli/` (área C; visto bueno en H2) |
| `src/harness_agent/cli/app.py`, `cli/__init__.py` | Mod. mínima (`run_cli(..., commands=None)`; exportaciones). `render.py`, `SHOWN_TYPES` y `HELP_TEXT` **no cambian** (R12) | Ídem |
| `src/harness_agent/bootstrap.py` | Mod. mínima (cablear verificador y runner; `Composition.runner`; `run_session`) | Raíz de composición (área C; visto bueno en H2) |
| `tests/unit/core/tasks/test_condition.py`, `test_condition_properties.py` | Nuevo | `tests/unit/core/tasks/` |
| `tests/unit/core/tasks/test_task_parser.py` | Mod. (**solo se añaden casos**) | Ídem |
| `tests/integration/test_task_start.py`, `tests/unit/adapters/tasks/test_task_source.py` | Mod. **una cadena cada uno** (research R11) | Ajuste declarado |
| `tests/unit/core/verification/{test_outcomes,test_feedback,test_feedback_properties,test_verifier,test_runner}.py` | Nuevo | `tests/unit/core/verification/` |
| `tests/unit/adapters/tools/test_shell_outcome.py` | Nuevo | `tests/unit/adapters/tools/` (contrato con la herramienta real) |
| `tests/unit/adapters/tools/test_public_api.py`, `tests/integration/test_core_public_api.py` | Mod. (**solo las listas de nombres esperados**) | Ajuste declarado |
| `tests/unit/cli/test_criteria.py`, `test_app_criteria.py` | Nuevo | `tests/unit/cli/` |
| `tests/unit/test_bootstrap_verification.py` | Nuevo | `tests/unit/` (cableado) |
| `tests/integration/test_criteria_verification_agent_loop.py` | Nuevo | `tests/integration/` (Sp2-53, convivencia, no filtración) |
| `tests/architecture/test_verification_boundaries.py` | Nuevo | Guarda `ast` de lo nuevo |

**Archivos protegidos** (diff vacío al cerrar): `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `core/redaction.py`, `core/permissions/` (todos), `config.py`, `adapters/tools/shell.py`, `adapters/storage/`, `tests/doubles/`, `docs/archivo/`.

**Archivos de otra área que se tocan** (área C): `cli/app.py`, `cli/__init__.py`, `cli/criteria.py` (nuevo), `bootstrap.py`, `adapters/tools/shell_outcome.py` (nuevo) y `adapters/tools/__init__.py`. La historia es de A: visto bueno de C en H2.

### Decisiones clave (detalle en `research.md`)

1. **R1**: se ejecuta por la herramienta `shell` del registro (no por el puerto `Shell`) para heredar recorte, ocultado, tiempo y cancelación.
2. **R2/R3**: misma forma de llamada que el agente; política → denegar/preguntar/permitir; «preguntar» con una `ApprovalGate` propia; sin aprobador no se ejecuta.
3. **R4**: `mark_passes` solo en `verifier.py` (guarda `ast` sobre todo `src/`).
4. **R5**: emparejado por posición y comparación exacta del comando; si no coincide, alteración.
5. **R6**: `VerifyingRunner` en `core/` (detecta `COMPLETED`, abre la ronda), cableado en `bootstrap.py`; sin contador nuevo; para si nada es corregible.
6. **R7/R8**: aviso en dos mensajes (salida externa y enmarcada + aviso del harness sin comando); evidencia con código y salida acotada.
7. **R9/R10**: carga del evento (siete claves) y estados; `task_state` único.
8. **R11**: Q3 en el analizador; 2 pruebas existentes se ajustan.
9. **R12**: CLI mínima.

### Estimación de tareas (RITMO: 2 PHU → 9 tareas de ≤ 40 min, TDD en cada una)

| # | Tarea | Min | Sprint |
|---|---|---|---|
| T001 | Inicio: PROGRESO `En curso`, observaciones de inicio | 10 | — |
| T002 | `core/tasks/condition.py` + validación en el analizador + 2 ajustes de pruebas + prueba al azar | 35 | Sp2-49 |
| T003 | `core/verification/outcomes.py` y `feedback.py`: estados, `task_state`, evidencia, aviso, nombre del programa; ejemplos normativos y prueba al azar | 40 | Sp2-51 |
| T004 | `core/verification/verifier.py`: emparejar, política, aprobación, ejecución, marcar, eventos; matriz de siete casos y convivencia | 40 | Sp2-50, Sp2-51 |
| T005 | `core/verification/runner.py` + `adapters/tools/shell_outcome.py` y exportaciones | 35 | Sp2-50 |
| T006 | CLI (`criteria.py`, `app.py`, `__init__.py`) y cableado en `bootstrap.py` | 40 | Sp2-52 |
| T007 | Integración Sp2-53: proyecto y ticket de ejemplo, matriz con `compose()`, un flujo con shell real, no filtración, único escritor en el registro | 40 | Sp2-53 |
| T008 | Guarda `ast`, skills (dos copias), `CLAUDE.md`, lista de comprobación, detector de secretos | 30 | — |
| T009 | Cierre: cuatro puertas, diff de protegidos, PROGRESO `En revisión` con observaciones | 30 | — |

Total de Claude: unos 300 min, frente a 510 min (8,5 h) presupuestados en Sp2-49 a Sp2-53. El presupuesto es un aviso, no un límite.

### Tareas humanas (Claude no las marca)

- **H1**: **acuerdo de A, B y C** sobre los campos del evento `criterion_verified` (siete claves; en especial `program` y `description`) y sobre el endurecimiento del analizador de la tarea (`condicion_no_soportada`).
- **H2**: **visto bueno de C** a los cambios en `cli/` (`criteria.py`, `app.py`, `__init__.py`), `bootstrap.py` y `adapters/tools/shell_outcome.py`.
- **H3**: **revisión cruzada** por B o C (la historia es de A).
- **H4**: **revisión del PO** de la regla ante «preguntar» (Q2), de la gramática de la condición (Q3) y de si el almacén debe permitir **revocar passes con evidencia** ante una regresión.
- **H5**: **CI remota** en `ubuntu-latest` y `windows-latest` (el flujo con shell real corre allí).
- **H6**: aviso a A para HU-01-06: el tiempo de los comandos de verificación no cuenta en `max_seconds` (research R6). No es una tarea de esta historia.

## Complexity Tracking

| Desviación | Por qué | Alternativa descartada |
|---|---|---|
| El evento lleva `description` y `program` además de índice, resultado y código | La CLI no tiene otra fuente y la restricción 10 pide mostrar el programa (R9) | CLI que lee el almacén (cambia `run_cli`); evento sin descripción (el prototipo no se puede dibujar) |
| Ejecución por la herramienta `shell` y no por el puerto `Shell` | Hereda ocultado, recorte, área, tiempo y cancelación sin duplicarlos (R1) | `Shell.execute` directo; ampliar el puerto |
| Emparejado por posición y no por identificador | La definición no tiene identificador (R5) | Añadir un identificador al formato de la tarea |
| `ApprovalGate` propia del verificador | El bucle guarda la suya como atributo privado y no se toca (R3) | Compartir la del bucle |
| Para de abrir rondas cuando nada es corregible | Evita gastar turnos en algo que el agente no puede arreglar (R6) | Rondas hasta agotar los límites |
| Dos pruebas existentes cambian una cadena y dos listas de nombres esperados | El endurecimiento de Q3 y las exportaciones nuevas (R11) | Dejar la validación fuera del analizador (contradice Q3) |
| El prototipo pone «pendiente de validación humana» entre paréntesis | Misma forma en todas las líneas (R12) | Alinear con espacios |
| El estado de los criterios se suscribe aparte y `/criterios` es un parámetro opcional de `run_cli` | Las pruebas existentes fijan `SHOWN_TYPES` (6 tipos) y el texto de `/ayuda`; así no cambia ninguna (R12) | Añadir el tipo a `SHOWN_TYPES` (rompe 3 pruebas existentes) |
