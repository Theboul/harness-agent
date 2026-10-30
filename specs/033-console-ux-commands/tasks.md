# Tasks: HU-06-05 — Consola legible y comandos útiles de sesión

**Input**: `specs/033-console-ux-commands/` (spec.md con Clarifications, plan.md, research.md R1–R9, data-model.md, contracts/console_contract.md, quickstart.md)
**Rama**: `claude/cli-console-ux-ea1667` (commits convencionales en español con el ID; sin push ni PR)
**Responsable**: C — Control y conexiones | **Historia propuesta** (sin ficha en `docs/04x`) | **Tareas de referencia**: ninguna `SpN-xx` (historia nueva); presupuesto propio de 15–40 min por tarea

## Cómo leer este documento

- **TDD dentro de cada tarea**: (1) escribir las pruebas; (2) ejecutarlas y ver el **rojo por la razón esperada** (anotarlo en la evidencia); (3) implementar lo mínimo; (4) `ruff format --check .`, `ruff check .`, `mypy src tests` y las pruebas del módulo con cobertura (100 % de líneas y ramas del módulo nuevo).
- **Formato**: `- [ ] Tnnn [USn] descripción con ruta (minutos)`.
  - US1: bloque de aprobación legible (FR-001 a FR-003, FR-006; AC-01).
  - US2: bloque que no se rompe ni filtra (FR-004, FR-005; AC-02).
  - US3: vista de actividad (FR-007 a FR-009, FR-017; AC-03).
  - US4: comandos `/sesiones`, `/nueva`, `/compactar`, `/model` y `/ayuda` (FR-010 a FR-014; AC-04 a AC-08).
  - US5: color opcional y texto plano (FR-015, FR-016; AC-09).
- **Archivos protegidos** (no tocar): `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`. Comprobación al cerrar (T016).
- **Cualquier cambio en `core/`** es un hallazgo: detenerse y dejarlo anotado.
- **Rutas** justificadas en `plan.md` (*Source Code*): todo en `cli/`, `bootstrap.py` y `tests/`.
- Las tareas **humanas** (H1–H4) al final **no se marcan**.

## Phase 1: Setup

- [x] T001 Registrar la historia en `docs/PROGRESO.md` (fila `HU-06-05` propuesta, área C, `En curso`; observación del visto bueno del PO) y fijar la línea base: correr `pytest tests/unit/cli tests/integration -q` y anotar la lista exacta de pruebas que cambiarán por los nuevos formatos (R9) (30 min)

## Phase 2: Foundational (bloquea las historias de usuario)

- [x] T002 [US5] `tests/unit/cli/test_style.py` y `src/harness_agent/cli/style.py`: `Style`, `detect_style(stream, environ, platform)`; flujo no terminal, `NO_COLOR`, `TERM=dumb`, Windows con y sin indicios; `paint` sin estilo devuelve el texto idéntico (30 min)
- [x] T003 [US4] `tests/unit/cli/test_app_async_commands.py` y `src/harness_agent/cli/app.py`: un comando puede devolver `str` o *awaitable* y `run_cli` lo espera; `/ayuda` sigue listando todos los comandos en orden de registro (formato sin cambios; no cambia la firma de `run_cli`); los comandos existentes y sus pruebas no cambian (30 min)

## Phase 3: US1 + US2 — Aprobación legible y a prueba de entradas hostiles (P1)

**Prueba independiente**: `ConsoleApprover` sobre `StringIO` con un `shell` de comando largo, saltos de línea, escape ANSI y `api_key` con centinela.

- [x] T004 [P] [US1] [US2] `tests/unit/cli/test_approval_view.py` y `src/harness_agent/cli/approval_view.py`: `approval_block(name, details, style) -> list[str]` con título, frase, valor principal (`command`/`path`), herramienta, argumentos, riesgo, efecto y opciones; escapado de `\n`, saneado, acotado (400/200), claves ocultas, detalle sin `risk`/`effect`/`arguments`, más de 20 argumentos (40 min)
- [x] T005 [US1] [US2] `tests/unit/cli/test_approval.py`, `test_approval_reason.py` y `src/harness_agent/cli/approval.py`: `ConsoleApprover` usa el bloque (parámetro opcional `style`); la lectura `1/2/3`, `/salir`, fin de entrada, `max_attempts` y el motivo no cambian; el centinela no aparece; actualizar las pruebas de formato (30 min)

## Phase 4: US3 — Vista de actividad (P1)

**Prueba independiente**: publicar `tool_requested` → `approval_*` → `tool_finished` con marcas de tiempo conocidas y comprobar líneas y duración.

- [x] T006 [US3] `tests/unit/cli/test_render_events.py`, `test_render_limits.py`, `test_render_text.py` y `src/harness_agent/cli/render.py`: nuevos formatos de línea del contrato §2, `approval_resolved`, `context_compacted`, `SHOWN_TYPES`; mantener explicaciones y sugerencias de error (30 min)
- [x] T007 [US3] `tests/unit/cli/test_activity.py` y `src/harness_agent/cli/activity.py`: `ActivityRenderer` con duración (espera de aprobación descontada, sin `tool_requested` previo, tiempo hacia atrás, tope de pendientes); `attach_renderer` pasa a usarlo y `app.py` lo reexporta (40 min)

## Phase 5: US4 — Comandos (P2)

**Prueba independiente**: `run_session` con SQLite temporal y `FakeProvider`, ejecutando cada comando.

- [x] T008 [P] [US4] `tests/unit/cli/test_session_commands.py` y `src/harness_agent/cli/session_commands.py`: `SessionRow`, `format_sessions` (orden, máx. 10, «y N más», actual marcada, objetivo saneado), `ModelView`, `format_model`, `format_compaction`, `format_new_session` (30 min)
- [x] T009 [US4] `tests/unit/test_bootstrap_console.py` y `src/harness_agent/bootstrap.py`: `Composition.model_view` y `manual_compactor_for`; `_compactor` acepta `settings`/`warn`; la configuración derivada fuerza el umbral sin cambiar `recent_percent`, `min_recent_messages`, `summary_tokens` (30 min)
- [x] T010 [US4] `tests/integration/test_console_commands.py` y `bootstrap.py`: `/sesiones` (sin subagentes, más reciente primero, actual marcada, fallo del almacén) y `/model` (sin clave) por `run_session` (30 min)
- [ ] T011 [US4] `tests/integration/test_console_commands.py` y `bootstrap.py`: `/nueva` (historial limpio, otro identificador, mensajes en la sesión nueva, la anterior reanudable, rechazo con tarea) (40 min)
- [ ] T012 [US4] `tests/integration/test_console_commands.py` y `bootstrap.py`: `/compactar` (compacta por debajo del umbral, informa tokens, historial original conservado, nada que resumir, fallo del proveedor sin estado parcial, y también con una tarea activa) (40 min)

## Phase 6: US5 — Color de extremo a extremo (P3)

- [ ] T013 [US5] `tests/integration/test_console_ux_style.py` y el cableado de `style` en `run_cli`/`ConsoleApprover`/`attach_renderer`: terminal simulada con y sin `NO_COLOR`; el texto sin códigos es idéntico al texto plano; ningún `\x1b` en `StringIO` (30 min)

## Phase 7: Polish y cierre

- [ ] T014 `tests/architecture/test_console_ux_boundaries.py` (`verificar-fronteras-hexagonales`): `\x1b` solo en `cli/style.py`; `cli/` no lee `os.environ` fuera de `style.py`; los módulos nuevos usan solo stdlib y la API pública; `bootstrap.py` sigue sin `print`; prueba de mutación de cada regla; correr `pytest tests/architecture` (30 min)
- [ ] T015 Documentación: `docs/PROGRESO.md` (fila a `En revisión`, Archivos, Evidencia real, registro de cambios por tarea sin líneas en blanco en la tabla, observaciones y fuera de alcance), `CLAUDE.md` (tabla «Qué existe hoy», siguiente número de spec) y las skills `estructura-carpetas-harness`/`arquitectura-hexagonal-clean`/`verificar-fronteras-hexagonales` en `.claude/skills/` y `.agents/skills/` si cambia la descripción de `cli/` (30 min)
- [ ] T016 Cierre: `ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest` y `pytest tests/architecture` en exit 0; comprobar los archivos protegidos con `git diff --exit-code`; lista de comprobación de `capas-y-reglas.md` revisada contra el código; marcar aquí solo lo hecho (30 min)

## Tareas humanas (Claude no las marca)

- [ ] H1 El PO confirma o renombra HU-06-05 y ratifica AC-01 a AC-09.
- [ ] H2 Revisión cruzada por una persona de otra área (A o B): `bootstrap.py` y la compactación forzada (A7).
- [ ] H3 CI remota en Windows y Linux.
- [ ] H4 Ratificación técnica de HU-00-01 (bloquea `Hecha` para cualquier historia).

## Dependencias

T001 → T002, T003 → (T004 → T005) y (T006 → T007) en paralelo → T008 → T009 → T010 → T011 → T012 → T013 → T014 → T015 → T016. T004 y T008 son independientes de lo demás (módulos puros) y pueden hacerse en cualquier orden tras T002.

## Estrategia

MVP = US1+US2 (T001–T005): ya resuelve el feedback principal. Después US3, US4 y US5 incrementalmente; cada tarea cierra con las puertas de calidad en verde.
