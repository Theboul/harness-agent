# Implementation Plan: HU-05-04 — Rechazo con motivo que vuelve al modelo

**Branch**: `gustavo` (directorio de la spec: `028-approval-rejection-reason`) | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/028-approval-rejection-reason/spec.md`

## Summary

Dos funciones puras nuevas en `core/permissions/approvals.py` (la puerta de aprobación de HU-05-03) hacen todo el trabajo:

- `clean_reason` sanea el motivo del rechazo: una sola línea, sin caracteres de control ni de formato, credenciales de URLs ocultas con `core/redaction.py`, comillas neutralizadas y 200 caracteres como máximo.
- `rejection_message` compone el texto del rechazo: la marca estable `[approval_rejected]` primero, la advertencia fija y el motivo entre comillas simples, con un tope de 500 caracteres. Sin motivo válido devuelve el texto actual, byte a byte.

`ApprovalGate` usa `clean_reason` para `ApprovalOutcome.reason`. El bucle cambia en un solo punto: `_ask_approval` llama a `rejection_message(call.name, outcome.reason)` en lugar de escribir el texto fijo. `cli/approval.py` pide el motivo tras elegir «rechazar». Puertos, catálogo de eventos y firma pública del bucle no cambian, y el motivo no entra en ningún evento. Sp2-33 se demuestra con un proveedor simulado, con un aprobador de prueba y con `ConsoleApprover` real sobre flujos de texto.

## Technical Context

**Language/Version**: Python 3.12; solo biblioteca estándar en `core/` (`unicodedata`, sin dependencias nuevas).

**Primary Dependencies**: ninguna nueva. Reutiliza `core/redaction.py` (HU-11-02).

**Storage**: N/A. Afirmación exacta sobre dónde puede quedar el motivo en `research.md` R6: no hay tabla de mensajes en SQLite; vive en el historial en memoria y viaja al proveedor del modelo en cada petición posterior.

**Testing**: pytest (`asyncio_mode = "auto"`), `FakeProvider`, `DummyApprover`/`ScriptedApprover`/`RecordingTool`/`RecordingEventBus` de `tests/doubles/` (sin dobles nuevos), `ConsoleApprover` sobre `io.StringIO`, `compose()` para la convivencia. Prueba adversarial por tabla y con entradas al azar (semilla fija, solo stdlib). Cobertura del 100 % en `approvals.py` y en las líneas nuevas de `loop.py` y `cli/approval.py`. Sin red ni claves.

**Target Platform**: Windows y Linux (CI de ambos); nada depende de la plataforma.

**Project Type**: biblioteca/CLI hexagonal.

**Performance Goals**: coste constante por motivo (lectura acotada a 1 000 caracteres), aunque el motivo mida 1 MB.

**Constraints**:
- sin cambios en `core/interfaces/`, `core/events.py` ni en la firma pública del bucle;
- en `core/loop.py` solo `_ask_approval`, su `import` y su docstring;
- `core/` no importa `cli/` ni `adapters/`;
- falla cerrada;
- el motivo no entra en eventos ni en mensajes de error.

**Scale/Scope**: 2 funciones nuevas y 1 modificación pequeña en `approvals.py`; 1 llamada en el bucle; 1 lectura en la terminal; unos 5 archivos de pruebas y 1 guarda `ast`.

## Constitution Check

*GATE: pasa antes de la Fase 0 y se revisa tras la Fase 1.*

| Principio / regla | Cumplimiento |
|---|---|
| I. Una historia, una spec | Solo HU-05-04 (Sp2-32 y Sp2-33). Pasa |
| II. Microtareas de 15–40 min | 7 tareas (RITMO, 1 PHU). Pasa |
| III. Código modular, tipado, Python 3.12 | Funciones pequeñas y puras, `mypy` del repo. Pasa |
| IV. Pruebas y CI multiplataforma | Sin dependencias de plataforma. Pasa |
| V. Criterios inmutables | AC-01, flujo y regla copiados tal cual (comprobado). Pasa |
| VI. Disciplina de sprints | Fuera: PD-06, lectura asíncrona, cambios de política, recordar rechazos. Pasa |
| VII. Consulta quirúrgica | Ancla `#hu-05-04`, specs 019/027 y el código citado. Pasa |
| VIII. PROGRESO.md | Fila de inicio y cierre (`En revisión`) con observaciones |
| IX. DoD estricta | Tareas humanas H1–H5 |
| X. `docs/archivo/` | No se toca. Pasa |
| V-02, V-17 | Una aprobación nunca anula una denegación (las guardas existentes siguen en verde); el motivo no abre un camino nuevo hacia el modelo sin sanear. Pasa |

**Hard Rules de las skills del proyecto**

- **`arquitectura-hexagonal-clean`**: la regla (componer y sanear el texto del rechazo) es pura y vive en `core/permissions/`. No hay E/S nueva, así que no hace falta puerto ni adaptador: `ApprovalResult.reason` ya existe en el puerto `Approver`. La terminal (`cli/`) solo implementa el puerto existente. Eventos sin cambios. Sin `print`, `os.environ` ni `config` en `core/`.
- **`estructura-carpetas-harness`**: rutas en la tabla de abajo; ninguna carpeta nueva.
- **`verificar-fronteras-hexagonales`**: `approvals.py` ya está guardado por `test_approvals_boundaries.py`. Se añade `tests/architecture/test_rejection_reason_boundaries.py` para lo nuevo: las funciones son totales (sin `raise` ni E/S), `rejection_message` solo se llama desde `_ask_approval` y fuera de la rama `action is None`, `outcome.reason` no se menciona en ninguna otra función del bucle ni en ninguna carga de evento, y `cli/approval.py` no escribe el motivo. Lleva autoprueba y mutación.

### Recorrido de los *Decision Gates* (`arquitectura-hexagonal-clean`)

| Pregunta | Respuesta |
|---|---|
| ¿Regla o comportamiento nuevo? | Sí: sanear y componer el rechazo, en `core/permissions/approvals.py`, exportado en `core/__init__.py` |
| ¿Necesita algo de fuera? | No: el motivo llega en `ApprovalResult.reason` (puerto existente) |
| ¿Quién lo implementa? | `ConsoleApprover` lo lee de la terminal |
| ¿Cómo se conecta? | `AgentLoop._ask_approval` llama a la función; `bootstrap.py` no cambia |
| ¿Cómo se prueba? | Funciones con tablas y semilla fija; bucle con `DummyApprover`; terminal con flujos de texto; replanteo con `FakeProvider` |
| ¿Es asíncrono? | No las funciones; `Approver.request` sigue siendo asíncrono |

### Lista de comprobación de `capas-y-reglas.md` (respuesta de diseño; se revisa de nuevo al cerrar)

| Punto | Resp. | Justificación |
|---|---|---|
| ¿Regla de negocio en `core/` y no en un adaptador? | Sí | `core/permissions/approvals.py` |
| ¿Todo lo externo pasa por un puerto con tipos del dominio? | Sí | `Approver`/`ApprovalResult` existentes |
| ¿Puertos, entidades y eventos sin cambios? | Sí | Ninguno cambia |
| ¿Errores sin reproducir valores? | Sí | Las funciones no lanzan; ningún mensaje de error lleva el motivo |
| ¿Inyección y conexión solo en `bootstrap.py`? | Sí | No hay colaborador nuevo |
| ¿Núcleo probado con dobles, sin red, disco ni claves? | Sí | Dobles de `tests/doubles/`; el archivo SQLite solo en una prueba de persistencia con `tmp_path` |
| ¿Prueba de contrato del adaptador? | No aplica | No hay adaptador nuevo; `ConsoleApprover` ya tiene sus pruebas |
| ¿`pytest tests/architecture` con la guarda nueva? | Sí (diseño) | `test_rejection_reason_boundaries.py` |
| ¿Eventos en lugar de imprimir? | Sí | Ningún evento nuevo; prueba de que ninguno lleva el motivo |
| ¿Lo público exportado en `core/__init__.py`? | Sí | `clean_reason`, `rejection_message`, `MAX_REASON_CHARS`, `MAX_REJECTION_CHARS`, `REJECTED_MARK` |
| ¿Falla cerrada y secretos? | Sí | Un rechazo nunca ejecuta; el motivo se limpia y las credenciales se ocultan |
| ¿Otro integrante revisó el cambio? | No (pendiente) | H3 |

**Resultado del gate**: pasa. Desviaciones en *Complexity Tracking*.

**Revisión contra el código (T006)**: las respuestas se mantienen. Las funciones nuevas no tienen `raise` (guarda y prueba al azar), `core/__init__.py` exporta los cinco nombres, ningún evento ni puerto cambió y `bootstrap.py` no se tocó. Único «No»: la revisión cruzada (H3), pendiente de otra persona.

## Project Structure

### Documentation (this feature)

```text
specs/028-approval-rejection-reason/
├── spec.md · plan.md · research.md (R1–R11) · data-model.md · quickstart.md
├── contracts/rejection_message_contract.md   # API, garantías y ejemplos normativos del texto exacto
├── checklists/requirements.md
└── tasks.md                                  # /speckit-tasks
```

### Source Code y fila de `estructura-carpetas-harness` que justifica cada ruta

| Ruta | Nuevo/Mod. | Fila |
|---|---|---|
| `src/harness_agent/core/permissions/approvals.py` | Mod. (`clean_reason`, `rejection_message`, constantes; la puerta usa `clean_reason`) | Regla de negocio (permisos) → `core/permissions/` |
| `src/harness_agent/core/permissions/__init__.py`, `src/harness_agent/core/__init__.py` | Mod. (exportaciones) | Lo público se exporta en `core/__init__.py` |
| `src/harness_agent/core/loop.py` | Mod. **mínima**: `_ask_approval`, su `import` y su docstring | Archivo protegido de A; acuerdo en H1 |
| `src/harness_agent/cli/approval.py` | Mod. (`REASON_PROMPT` y la lectura tras `3`) | Terminal → `cli/` (de C; visto bueno en H2) |
| `tests/unit/core/permissions/test_rejection_message.py` | Nuevo | `tests/unit/core/permissions/` (tablas y ejemplos normativos) |
| `tests/unit/core/permissions/test_rejection_properties.py` | Nuevo | Ídem (semilla fija) |
| `tests/unit/core/permissions/test_approvals.py` | Mod. (casos nuevos de `clean_reason` en la puerta; sin tocar los existentes) | Ídem |
| `tests/core/test_loop_rejection_reason.py` | Nuevo | `tests/core/` (bucle) |
| `tests/core/test_loop_approval.py` | Mod. **una aserción** (research R9) | Ídem |
| `tests/unit/cli/test_approval_reason.py` | Nuevo | `tests/unit/cli/` |
| `tests/integration/test_rejection_reason_agent_loop.py` | Nuevo | `tests/integration/` (Sp2-33, convivencia, persistencia) |
| `tests/architecture/test_rejection_reason_boundaries.py` | Nuevo | Guarda `ast` de lo nuevo |

**Archivos protegidos** (diff vacío al cerrar): `core/interfaces/`, `core/events.py`, `core/in_memory_event_bus.py`, `core/permissions/{policy,protected,exact_calls,rules,command_parser,command_rules,command_policy,git_rules,git_table}.py`, `core/redaction.py`, `config.py`, `bootstrap.py`, `tests/doubles/`, `docs/archivo/`. En `core/loop.py` solo cambia lo indicado (se revisa a mano).

### Decisiones clave (detalle en `research.md`)

1. **R1/R2**: funciones puras en `approvals.py`; texto exacto con marca, advertencia y motivo entre comillas simples; sin motivo, el texto actual.
2. **R3 (desviación)**: las dos restricciones del revisor sobre comillas (marco simple; dobles → simples) no se pueden cumplir a la vez de forma segura; `'` y `"` del motivo pasan a `’`.
3. **R4**: saneado en el núcleo (no se reutiliza el de la CLI, que no elimina caracteres de formato); lectura acotada a 1 000 caracteres por el coste cuadrático de `hide_url_credentials` (hallazgo).
4. **R5**: mensaje ≤ 500; si no caben 20 caracteres de motivo, texto sin motivo.
5. **R6**: afirmación exacta de persistencia; **R7**: eventos sin cambios, con prueba.
6. **R8/R9**: terminal y única prueba existente que cambia.

### Estimación de tareas (RITMO: 1 PHU → 7 de ≤ 40 min, TDD en cada una)

| # | Tarea | Min | Sprint |
|---|---|---|---|
| T001 | Inicio: PROGRESO `En curso`, observaciones de inicio | 10 | — |
| T002 | `approvals.py`: `clean_reason`, `rejection_message`, uso en la puerta; tablas, ejemplos normativos y prueba al azar | 40 | Sp2-32 |
| T003 | `core/loop.py` (`_ask_approval`) y su prueba: motivo al modelo, sin motivo idéntico, `approval_failed` igual, eventos sin motivo; la aserción que cambia | 35 | Sp2-32 |
| T004 | `cli/approval.py`: pedir el motivo; pruebas | 35 | Sp2-32 |
| T005 | Replanteo (Sp2-33) con `FakeProvider`, con `DummyApprover` y con `ConsoleApprover` real; convivencia; persistencia | 40 | Sp2-33 |
| T006 | Guarda `ast`, skills (dos copias), `CLAUDE.md`, lista de comprobación y detector de secretos | 25 | — |
| T007 | Cierre: cuatro puertas, diff de protegidos, PROGRESO `En revisión` con observaciones | 30 | — |

Total de Claude: unos 215 min, frente a 150 min presupuestados (Sp2-32 y Sp2-33). El presupuesto es un aviso, no un límite.

### Tareas humanas (Claude no las marca)

- **H1**: **ratificar el acuerdo** de A, B y C al cambio mínimo en `core/loop.py` (hoy autorizado por el usuario actuando como A).
- **H2**: **visto bueno de C** a los cambios en `core/permissions/approvals.py` y `cli/approval.py`.
- **H3**: **revisión cruzada** por B o C (la historia es de A).
- **H4**: **revisión del PO** de la advertencia fija (research R2) y de que el motivo llegue al proveedor del modelo en cada petición posterior (research R6).
- **H5**: **CI remota** en `ubuntu-latest` y `windows-latest`.
- Aviso para HU-11-02/HU-10-02 (no es una tarea de esta historia): el coste cuadrático de `hide_url_credentials` (research R4).

## Complexity Tracking

| Desviación | Por qué | Alternativa descartada |
|---|---|---|
| `'` y `"` del motivo pasan a `’`, no solo `"` → `'` | Las restricciones 1 y 2 son incompatibles con un marco de comillas simples (R3) | Marco de comillas dobles; escapar con barra invertida |
| Una aserción de `test_loop_approval.py` se invierte | Comprobaba que el motivo no llegaba al modelo, justo lo que esta historia cambia (R9) | Dejarla: la prueba fallaría |
| Saneado propio en el núcleo | `core/` no importa `cli/` y el de la CLI no elimina caracteres de formato (R4) | Copiar `render.sanitize` |
| Lectura acotada a 1 000 caracteres antes de ocultar credenciales | Coste cuadrático de `hide_url_credentials` con palabras largas (R4) | Llamarla con el motivo entero |
| Si caben menos de 20 caracteres de motivo, se devuelve el texto sin motivo | El tope de 500 manda; con un nombre de herramienta gigante no hay sitio útil (R5) | Recortar la advertencia |
