# Implementation Plan: HU-06-05 — Consola legible y comandos útiles de sesión

**Branch**: `claude/cli-console-ux-ea1667` (directorio de la spec: `033-console-ux-commands`) | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/033-console-ux-commands/spec.md` (Clarifications 2026-10-30: `/compactar` compacta igualmente, `/sesiones` 10 más recientes, actividad compacta, AC-01..AC-09 confirmados por el usuario; propuestos ante el PO)

## Summary

Se rediseña la presentación de la terminal y se añaden cuatro comandos, **sin tocar el núcleo**:

1. **Bloque de aprobación** (`ConsoleApprover`): un bloque ASCII con título, frase de la acción, valor principal (`command`/`path`) destacado, argumentos restantes acotados, riesgo, efecto y las tres opciones; valores escapados y acotados; claves ocultas; lectura `1/2/3` intacta.
2. **Vista de actividad**: un renderizador con estado mínimo (acotado) que añade la duración de cada herramienta (marcas de tiempo de `tool_requested`/`tool_finished` con el mismo `call_id`, descontando la espera de aprobación) y las líneas de `approval_resolved` y `context_compacted`.
3. **Comandos** `/sesiones`, `/nueva`, `/compactar`, `/model` registrados por el mecanismo existente. Un cambio mínimo en `run_cli`: un comando puede devolver el texto o un *awaitable* (la compactación es `async`). `/ayuda` se alinea y lista todo.
4. **Estilo**: `cli/style.py` decide el color (terminal + sin `NO_COLOR` + soporte en Windows); sin color el texto es idéntico.

El único trabajo fuera de `cli/` es el cableado en `bootstrap.py`: filtrar sesiones de subagente (vía `SqliteSessionStore.get_session`), crear la sesión de `/nueva`, un compactador de «umbral mínimo» para `/compactar` (misma clase, ajustes derivados) y la vista del modelo y límites. **No cambian** `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, el esquema SQLite ni la lógica del compactador.

## Technical Context

**Language/Version**: Python 3.12; solo biblioteca estándar en `cli/`.

**Primary Dependencies**: ninguna nueva.

**Storage**: SQLite sin cambios de esquema (`/nueva` usa `create_session`; `/sesiones` usa `list_sessions` y `get_session`).

**Testing**: pytest, `io.StringIO`, un flujo falso con `isatty()`, `FakeProvider`, bases temporales en `tmp_path`; sin red ni claves; centinela `VALOR-DE-PRUEBA-123`.

**Target Platform**: Windows y Linux (CI de ambos); consola clásica de Windows sin ANSI debe verse igual de legible.

**Project Type**: biblioteca/CLI de terminal con arquitectura hexagonal.

**Performance Goals**: ninguno relevante; formatear un bloque o una lista es O(n) en el tamaño acotado.

**Constraints**: cli/ solo stdlib + API pública de `harness_agent.core`; no inventar campos de eventos; todo texto externo saneado y acotado; decoración solo ASCII.

**Scale/Scope**: 4 módulos nuevos en `cli/` (`style`, `approval_view`, `activity`, `session_commands`), cambios en `app.py`, `approval.py`, `render.py`, `__init__.py`, cableado en `bootstrap.py`; ~12 tareas de ≤ 40 min.

## Constitution Check

| Principio / regla | Cómo se cumple |
|---|---|
| I. Una historia por especificación | Una spec (033) |
| II. Microtareas de 15 a 40 min | `tasks.md` (ninguna > 40 min) |
| III. Código modular, tipado | Módulos pequeños con dataclasses `frozen`; `mypy` estricto |
| IV. Pruebas, calidad y CI | TDD con rojo observado; cuatro puertas; CI Windows y Linux (tarea humana) |
| V. Criterios inmutables | AC-01..AC-09 son **propuestos** y confirmados por el usuario; el PO los ratifica (H1). Los de HU-06-04 AC-01 y HU-02-04 AC-01 no se alteran |
| VI. Disciplina de sprints | Historia propuesta, adelantada por el cierre del 6/11; no se implementa nada de HU-09-x, MCP ni skills |
| VII. Consulta documental quirúrgica | Se leyeron las fichas HU-06-04 y HU-02-04, `cli/`, `bootstrap.py`, el compactador |
| VIII. Registro en `PROGRESO.md` | Fila nueva `HU-06-05` y registro por tarea |
| IX. DoD estricta | `En revisión`, nunca `Hecha` |
| X. `docs/archivo/` inmutable | No se toca |
| Falla cerrada | El aprobador no cambia su lógica; los comandos nunca lanzan: devuelven una línea fija |
| V-13 (secretos) | Claves por nombre ocultas como hoy; la clave de `/model` nunca se lee |

**Resultado del gate**: pasa. Desviaciones: ninguna del núcleo. Hallazgos (no se actúa): (a) un parámetro `force` en `ContextCompactor` sería más limpio que bajar el umbral con ajustes (A7, para B); (b) el detalle del error de herramienta sigue sin viajar en el evento.

### Recorrido de los *Decision Gates* (`arquitectura-hexagonal-clean`)

| Pregunta | Respuesta |
|---|---|
| ¿Es regla o comportamiento nuevo? | No: es presentación → `cli/` (sin reglas de negocio nuevas) |
| ¿Necesita algo de fuera? | No hay puerto nuevo: usa `Approver`, `EventBus` y `SessionStore` existentes; el almacén concreto solo lo toca `bootstrap.py` |
| ¿Quién lo implementa? | `cli/` formatea; `bootstrap.py` obtiene datos del almacén y del compactador |
| ¿Cómo se conecta? | Por constructor/parámetros en `run_session` y `compose`; `ConsoleApprover` ya se cablea en `main()` |
| ¿Cómo se prueba? | Unitarias de `cli/` con `StringIO`; integración con `run_session` + `FakeProvider` + SQLite temporal; guarda `ast` nueva |
| ¿Es asíncrono? | Solo `/compactar` (la compactación ya es `async`); `run_cli` espera el resultado |

### Lista de comprobación de `capas-y-reglas.md` (respuesta de diseño; se revisa al cerrar)

| # | Pregunta | Respuesta |
|---|---|---|
| 1 | ¿La regla de negocio está en `core/` y no en un adaptador? | Sí: no hay reglas nuevas; las existentes (aprobación, compactación) no cambian |
| 2 | ¿Todo lo externo pasa por un puerto con tipos del dominio? | Sí: la terminal es `cli/`; el almacén lo usa solo `bootstrap.py` |
| 3 | ¿Puertos, entidades y eventos sin cambios? | Sí |
| 4 | ¿Errores externos traducidos, sin reproducir valores? | Sí: los comandos devuelven mensajes fijos ante cualquier excepción |
| 5 | ¿Dependencias por constructor y conectadas en `bootstrap.py`? | Sí; el entorno y la plataforma del estilo se inyectan en `detect_style` |
| 6 | ¿Núcleo probado con dobles, sin red/disco/claves? | N/A (no se toca); `cli/` con `StringIO` |
| 7 | ¿Adaptador real con prueba de contrato? | N/A: no hay adaptador nuevo |
| 8 | ¿`pytest tests/architecture` en verde? | Se comprueba en cada fase y al cerrar |
| 9 | ¿El núcleo emite eventos en lugar de imprimir? | Sí, sin cambios |
| 10 | ¿Lo público exportado en `core/__init__.py`? | N/A para `core/`; `cli/__init__.py` exporta la API nueva; `cli/` importa solo de `harness_agent.core` |
| 11 | ¿Decisiones de diseño respetadas (falla cerrada, historial intacto, secretos)? | Sí: rechazo por defecto, compactación no destructiva (mismo archivo), claves ocultas |
| 12 | ¿Otro integrante revisó? | Pendiente (tarea humana) |

## Project Structure

### Documentation (this feature)

```text
specs/033-console-ux-commands/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/console_contract.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code (repository root) — ruta de cada archivo y fila de `estructura-carpetas-harness` que la justifica

| Archivo | Fila de la tabla | Notas |
|---|---|---|
| `src/harness_agent/cli/style.py` (nuevo) | «Imprime o lee de la terminal → `cli/`» | `Style`, `detect_style` |
| `src/harness_agent/cli/approval_view.py` (nuevo) | idem | formato puro del bloque |
| `src/harness_agent/cli/activity.py` (nuevo) | idem | `ActivityRenderer`; `attach_renderer` se mueve aquí y `app.py` lo reexporta |
| `src/harness_agent/cli/session_commands.py` (nuevo) | idem | formato de `/sesiones`, `/nueva`, `/compactar`, `/model` |
| `src/harness_agent/cli/app.py` (cambia) | idem | comandos *awaitable*, ayuda alineada, `style` |
| `src/harness_agent/cli/approval.py` (cambia) | idem | usa `approval_view`; lectura sin cambios |
| `src/harness_agent/cli/render.py` (cambia) | idem | nuevos formatos de línea, `approval_resolved`, `context_compacted` |
| `src/harness_agent/cli/__init__.py` (cambia) | «`__init__.py` expone la API» | exporta `Style`, `detect_style`, `ActivityRenderer` |
| `src/harness_agent/bootstrap.py` (cambia) | «Unir piezas → `bootstrap.py`» | cableado de los 4 comandos |
| `tests/unit/cli/test_style.py`, `test_approval_view.py`, `test_activity.py`, `test_session_commands.py`, `test_app_async_commands.py` (nuevos) | «`tests/` refleja `src/`» | |
| `tests/unit/cli/test_approval*.py`, `test_render_*.py`, `test_app_*.py` (se actualizan) | idem | nuevos formatos |
| `tests/integration/test_console_commands.py` (nuevo) | idem | `run_session` real |
| `tests/architecture/test_console_ux_boundaries.py` (nuevo) | «guarda `ast` por frontera» | ANSI solo en `style.py`; `cli/` sin `os.environ` fuera de `style.py` |

**Structure Decision**: solo `cli/` y `bootstrap.py`. No se crea ninguna carpeta. `tests/doubles/` no se toca (se usan dobles existentes y objetos locales en la prueba).

## Fases de diseño

**Fase 0** → [research.md](research.md): decisiones (R1 estilo, R2 bloque, R3 duración, R4 comandos *awaitable*, R5 filtro de subagentes, R6 `/nueva`, R7 `/compactar` forzado, R8 `/model`).
**Fase 1** → [data-model.md](data-model.md), [contracts/console_contract.md](contracts/console_contract.md) (formatos exactos de cada salida), [quickstart.md](quickstart.md).

## Complexity Tracking

| Desviación | Por qué | Alternativa descartada |
|---|---|---|
| `/compactar` baja el umbral con ajustes derivados en `bootstrap.py` | `ContextCompactor.before_turn` solo compacta sobre el umbral y el núcleo no se toca | Añadir `force` al compactador (cambio de B, fuera de alcance; hallazgo A7) |
| El aviso «sigue por encima del umbral» del compactador se silencia en el compactador manual | Con umbral mínimo siempre se cumpliría y sería ruido falso | Dejarlo (confunde) |
| Estimación de duración incluye la latencia de bus, no solo la herramienta | Solo hay marcas de tiempo de eventos | Cronometrar en el núcleo (cambio protegido) |
