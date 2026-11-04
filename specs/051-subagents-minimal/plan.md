# Plan: HU-09-01, HU-09-03 y HU-09-04 — Subagentes mínimos

**Spec**: [spec.md](spec.md) · Skills: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness`, `verificar-fronteras-hexagonales`.
**Contexto técnico**: Python 3.12, sin dependencias nuevas; núcleo solo biblioteca estándar; pruebas con `FakeProvider` y archivos SQLite reales en `tmp_path`.

## Decision Gates (arquitectura-hexagonal-clean)

| Gate | Resultado |
|---|---|
| ¿Regla de negocio nueva en `core/`? | **Sí**: `core/subagents/` (tarea del hijo, vista del registro sin `delegar`, validación y acotado del resultado, resultado parcial, aprobador que dice quién pide, ejecutor que une todo). Es puro: recibe por constructor la creación de la sesión hija, el bucle del hijo, el bus y el redactor. |
| ¿Puerto nuevo? | **No.** Se **implementa** `SubagentRunner` (`core/interfaces/connections.py`) tal como está; se usan `SubagentResult`, `Approver`, `ToolRegistry`, `EventBus`. Las dos costuras (`ChildSessions`, `ChildLoop`) son `Protocol`/invocables del propio módulo, como `MessageLog` o `ProgressSink`. |
| ¿Qué es externo? | La base SQLite (la crea `bootstrap.py` con `store.create_session(parent_id=)`, que ya existe) y el bucle (`AgentLoop`, lo construye `bootstrap.py`). El núcleo no importa `core/loop.py` desde `core/subagents/`: lee el resultado del turno por protocolo (`ChildTurn`). |
| ¿Adaptador? | `adapters/tools/delegar.py` — `DelegateTool(runner)`: la herramienta nativa. Solo stdlib y API pública del núcleo. |
| ¿Dónde se conecta? | Solo `bootstrap.py`, y solo si `[subagents] enabled = true` (D-19): registra `delegar`, la abre en la política, construye el ejecutor y la fábrica del bucle hijo con los límites de `[subagents]`. |
| ¿Cómo se prueba? | Núcleo con dobles de bucle y de sesiones en memoria; herramienta con un ejecutor falso; integración con `compose()` + `FakeProvider` + archivo real. |

## Estructura (estructura-carpetas-harness)

| Archivo | Fila de la tabla que lo justifica |
|---|---|
| `src/harness_agent/core/subagents/__init__.py` | Regla de negocio (subagentes) → subpaquete de `core/`; exporta la API pública |
| `src/harness_agent/core/subagents/result.py` | Regla de negocio: `RESULT_SCHEMA`, `parse_result`, `shorten_output`, `failure_output`, `partial_output` |
| `src/harness_agent/core/subagents/task.py` | Regla de negocio: `build_task` (el único mensaje del hijo) |
| `src/harness_agent/core/subagents/registry.py` | Regla de negocio: `RegistryView`, `DELEGATE_TOOL_NAME` |
| `src/harness_agent/core/subagents/approval.py` | Regla de negocio: `SubagentApprover`, `requester_label` |
| `src/harness_agent/core/subagents/runner.py` | Regla de negocio: `LoopSubagentRunner`, `ChildSessions`, `ChildTurn`, `ChildLoop` |
| `src/harness_agent/adapters/tools/delegar.py` | Herramienta nativa → `adapters/tools/` |
| `src/harness_agent/config.py` (cambio) | Lectura de configuración → `config.py`: `[subagents]`, `SubagentSettings` |
| `src/harness_agent/cli/approval_view.py` (cambio mínimo) | Imprime → `cli/`: línea `Pide:` |
| `src/harness_agent/bootstrap.py` (cambio) | Unir piezas → `bootstrap.py` |
| `src/harness_agent/core/__init__.py`, `adapters/tools/__init__.py` (cambio) | Exportar lo público |
| `config.example.toml` (cambio) | Sección `[subagents]` comentada |
| `tests/unit/core/subagents/test_{result,task,registry_view,approval,runner,runner_limits,public_api}.py` | Equivalentes en `tests/` |
| `tests/unit/adapters/tools/test_delegar.py` | Equivalente en `tests/` |
| `tests/unit/test_config_subagents.py`, `tests/unit/cli/test_approval_view_requester.py` | Equivalentes en `tests/` |
| `tests/unit/test_bootstrap_subagents.py`, `tests/integration/test_subagents_agent_loop.py` | Cableado e integración |
| `tests/architecture/test_subagents_boundaries.py` | Guarda `ast` (plantilla de `verificar-fronteras-hexagonales`) |

## Diseño

1. **`LoopSubagentRunner.execute(profile, goal, context, output_schema)`**: (1) construye la tarea (`build_task`); (2) crea la sesión hija (`ChildSessions.create(parent_id, goal)`; fallo → `sin_sesion_hija`, nada más); (3) publica `SUBAGENT_STARTED`; (4) ejecuta `ChildLoop(child_id, task, [])` (lista de historial vacía y local; solo `Exception` se convierte en `fallo_del_subagente`); (5) traduce el `ChildTurn`: `completed` → `parse_result` (válido → `shorten_output`; no → `resultado_no_valido`), `limit_reached` → `partial_output`, `provider_failed`/`invalid_provider_response` → códigos fijos; (6) oculta secretos en todos los textos; (7) publica `SUBAGENT_FINISHED`; (8) devuelve `SubagentResult`.
2. **`DelegateTool.run`**: valida (lo hace el registro antes), arma `goal` con el formato de salida, llama a `runner.execute("general", goal, [Message(USER, contexto)], RESULT_SCHEMA)` y devuelve `json.dumps(output, ensure_ascii=False)` con `is_error` del resultado. Una excepción del ejecutor (menos la cancelación) es `[subagente_fallo]`.
3. **Bucle del hijo (en `bootstrap.py`)**: `AgentLoop(provider, RegistryView(registry, {delegar}), policy, bus, approver=SubagentApprover(approver, label) o None, limits=SessionLimits(**config.subagents))`; `run_turn(session_id=hija, task=…, history=[])`.
4. **Política**: con la opción activada, `delegar` entra en `open_tools` y **no** en `read_names`; apagada, nada de esto existe. La política del hijo es la `SwitchablePolicy` final del orquestador, el mismo objeto.
5. **Padre**: `lambda: cursor.value`; `/nueva` mueve el cursor (D-08).
6. **Sesión hija**: `store.create_session(model=switch.model, goal=<objetivo oculto, una línea, ≤ 200>, parent_id=padre)`.

## Dry run: pruebas existentes que cambian

**Primer dry run (herramienta ficticia, registrada siempre).** Se aplicaron cambios provisionales (herramienta `delegar` ficticia en el registro, campo `subagents` en `HarnessConfig`, nombre nuevo en `core.__all__` y en `adapters.tools.__all__`, subpaquete `core/subagents` vacío) sobre el árbol limpio, se corrió la suite completa (`pytest --no-cov`: 8 724 pasadas, **14 fallidas**, 48 omitidas) y se revirtió todo (árbol limpio). No fallaron `test_core_public_api.py`, las pruebas de `config`, el esquema/tablas SQLite (no cambia: sigue v5) ni las de arquitectura.

**Segundo dry run (herramienta real, registrada siempre).** Al implementar T011 se corrió la suite con la declaración real de `delegar` (unos 300 tokens, mucho más que la ficticia): **28 fallidas**, todas por el mismo motivo salvo dos listas de nombres. La declaración suma tokens al estimado de cada petición y mueve los umbrales de compactación calibrados a mano: `tests/integration/test_context_compaction_agent_loop.py` (11), `test_essential_context_agent_loop.py` (2), `test_resume_agent_loop.py` (6), `test_resume_cuts.py` (1), `test_resume_security.py` (1), `tests/unit/test_bootstrap_compaction.py` (5), más `test_bootstrap_compose.py` (lista de herramientas) y `test_mcp_tool_discovery.py` (conjunto de herramientas). Eso excede lo que el usuario autorizó (la lista del primer dry run) y recalibrar 28 pruebas a mano arriesga debilitarlas.

**Decisión (D-19): la delegación se apaga por defecto** (`[subagents] enabled = false`). Con la opción apagada el registro no cambia y esas 28 pruebas pasan sin tocarlas (comprobado con la suite completa). Las pruebas nuevas activan la opción explícitamente.

Pruebas existentes que **sí** cambian, **autorizadas por el usuario, pendientes de ratificar** (ejecutada antes sin tocar para ver el rojo previsto):

| # | Prueba existente | Por qué cambia | Ajuste |
|---|---|---|---|
| 1 | `tests/unit/adapters/tools/test_public_api.py::test_tools_expose_the_tools_and_the_limits` | `adapters.tools.__all__` gana `DelegateTool` | Añadir `DelegateTool` al conjunto esperado |

Si el PO quiere la delegación activa por defecto (H03), hay que cambiar el valor por defecto y recalibrar las 27 pruebas restantes del segundo dry run. Si al implementar falla cualquier otra prueba existente, se detiene el trabajo y se avisa.

## Constitution Check

| Principio / regla | Resultado |
|---|---|
| Falla cerrada también en el alcance | Cumple: la delegación está apagada por defecto (D-19); activarla es una decisión explícita en `config.toml`. |
| Núcleo solo stdlib y `harness_agent.core`, sin E/S ni terminal; todo sale por el bus | Cumple: `core/subagents/` no importa `adapters`, `cli`, `config`, `sqlite3`, `core.loop`, y publica por `EventBus`. |
| V-02 falla cerrada | Cumple: política compartida (deny > ask > allow); no entender el resultado = error; sin aprobador se deniega; códigos fijos. |
| V-06 contrato de subagentes (entrada `{objetivo, contexto_minimo, formato_salida, perfil}`, salida `{resultado, hallazgos_clave, fuentes, error}`; sin escaladas de permisos) | Cumple: mismo objeto de política; las aprobaciones suben a la persona. |
| V-13 redacción de secretos | Cumple: el redactor general se aplica al resultado y al objetivo guardado. |
| V-14 `FakeProvider` | Cumple: sin red ni claves. |
| Contratos protegidos (`core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py`, `core/verification/`, `tests/doubles/`) | Intactos. |
| Un solo escritor de `passes` (`CriteriaVerifier`) | Intacto: el subagente no toca criterios. |
| Sin secretos en el repo | Cumple; literales de prueba partidos y centinelas. |

**Lista de comprobación de `capas-y-reglas.md`**

| Pregunta | Sí/No |
|---|---|
| ¿La regla de negocio está en `core/` y no en un adaptador? | Sí |
| ¿Todo lo externo pasa por un puerto con tipos del dominio? | Sí (`SubagentRunner`, `EventBus`, `Approver`, `ToolRegistry`; las dos costuras nuevas son del propio módulo y las conecta `bootstrap.py`) |
| ¿Puertos, entidades y eventos sin cambios? | Sí |
| ¿Los errores externos se traducen a errores de dominio sin reproducir valores? | Sí (códigos fijos) |
| ¿Dependencias por constructor y conexión solo en `bootstrap.py`? | Sí |
| ¿El núcleo se probó con dobles, sin red, disco ni claves? | Sí |
| ¿El adaptador real tiene prueba de contrato en `tests/contracts/`? | No: `DelegateTool` es una herramienta, se prueba como `AskUserTool` (unitaria y con el bucle real); no hay contrato de herramienta común que correr contra un doble. |
| ¿Pasa `pytest tests/architecture` y la guarda nueva en Windows y Linux? | Sí en Windows local; Linux queda para la CI remota (H02) |
| ¿El núcleo emite eventos en lugar de imprimir? | Sí |
| ¿Lo público está exportado en `core/__init__.py`? | Sí |
| ¿Se respetan las decisiones de diseño (falla cerrada, historial intacto, secretos redactados)? | Sí |
| ¿Otro integrante revisó el cambio? | No todavía (H01) |

## Guarda de fronteras

`tests/architecture/test_subagents_boundaries.py`: `core/subagents/` solo stdlib y núcleo (lista blanca), sin E/S ni entorno ni terminal, sin importar `core.loop`, `core.permissions`, `core.context` ni `core.verification`; ningún `except` captura `BaseException`, un `except` desnudo ni `CancelledError`; `registry.py` no define `register` que registre; en `runner.py` el `await` del bucle hijo está fuera de cualquier `try` que capture `BaseException`. Cada regla con su prueba de mutación (fragmentos sintéticos). `adapters/tools/delegar.py` ya queda cubierto por `test_adapters_boundaries.py`; `bootstrap.py` por `test_bootstrap_boundaries.py` (solo API pública).

## Archivos protegidos (no tocar)

`core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py`, `core/verification/`, `core/in_memory_event_bus.py`, `tests/doubles/`, `docs/archivo/`. Cambios mínimos autorizados fuera de lo anterior: `cli/approval_view.py` (una línea nueva solo cuando llega `requested_by`) — pendiente de ratificar por C.

## Mapeo a tareas del plan de sprints

Sp3-01, Sp3-02, Sp3-03 (HU-09-01) → T004, T005, T011, T013; Sp3-47, Sp3-48, Sp3-49 (HU-09-03) → T002, T005, T013; Sp3-50, Sp3-51 (HU-09-04) → T003, T009, T014.

## Hallazgos esperados

1. La terminal no distingue la actividad del subagente de la del orquestador (D-18): solo las aprobaciones llevan la línea `Pide:`. Mejora de C.
2. El costo del subagente no suma al presupuesto del orquestador (D-12).
3. Una sesión hija no se puede reanudar (sin mensajes guardados) y queda `active` (el almacén no cambia estados).
4. `delegar` no está disponible en modo solo lectura (D-03).
5. Apagada por defecto (D-19): activarla por defecto exige recalibrar 27 pruebas de compactación y cambia el contexto de todas las sesiones (H03).
6. Con un modelo real, la respuesta final del subagente debe ser JSON; un modelo que no lo cumple recibe `resultado_no_valido` y el orquestador decide (HU-09-05 completará la propagación).
