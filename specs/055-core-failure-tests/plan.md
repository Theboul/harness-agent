# Plan: HU-00-05.1

**Spec**: [spec.md](spec.md)

## Enfoque

Solo pruebas, tres archivos de prueba y un ayudante de proceso hijo en `tests/integration/`. Ningún archivo de `src/`. Se parte del inventario de la spec y solo se cubren sus huecos:

1. **AC-01**: el padre lanza un hijo (`sys.executable` + `core_kill_child.py`) que arma `compose()` con un `FakeProvider`/proveedor propio y corre `run_session`; el hijo anuncia por stdout los eventos confirmados (conexión `sqlite3` aparte) y el padre lo mata con `Popen.kill()`. Un segundo hijo abre la misma base, ejecuta `/reanudar <id>` y una petición más. El padre solo lee la base con `sqlite3` y los textos que imprime el hijo.
2. **AC-02**: `compose()` con un proveedor por modelo (`FakeProvider`), `retry_sleep` sin espera y SQLite real; una herramienta registrada en `composition.registry`.
3. **AC-03**: `compose()` completo y `composition.loop.run_turn` 200 veces; un envoltorio del proveedor mide el tiempo dentro de `complete()`.

## Project Structure (estructura-carpetas-harness)

| Archivo | Fila de la tabla | Motivo |
|---|---|---|
| `tests/integration/test_core_abrupt_kill_resume.py` | `tests/integration/` — piezas reales cableadas | Proceso real matado y reanudado (AC-01) |
| `tests/integration/core_kill_child.py` | `tests/integration/` — ayudante de proceso hijo, igual que `mcp_env_probe_server.py` | Programa del hijo: modos `block-provider`, `block-tool`, `busy`, `resume` |
| `tests/integration/test_core_failure_modes.py` | `tests/integration/` | Proveedor caído a mitad de turno, herramienta con excepción y `BaseException` con la composición real (AC-02) |
| `tests/integration/test_harness_own_time.py` | `tests/integration/` | Medición del tiempo propio por turno (AC-03) |

Sin archivos nuevos en `src/`. Receta de `recetas.md`: ninguna (no es herramienta, proveedor, almacén, comando ni evento). Los dobles se reutilizan de `tests/doubles/` (`FakeProvider`, `RecordingTool`/`BlockingTool` si encajan); **no** se añade ni se modifica ningún doble (protegido). Lo que falte (un proveedor que se bloquea o mide el tiempo, una herramienta que lanza) se define dentro del archivo de prueba.

## Constitution Check / Decision Gates (arquitectura-hexagonal-clean)

Regla en `core/`: no. Puerto nuevo: no. Adaptador nuevo: no. Conexión nueva en `bootstrap.py`: no. Prueba: sí, en la carpeta equivalente. Lista de `capas-y-reglas.md`: **no aplica a código nuevo** (no hay código de producción); se revisa contra el existente y se responde en el cierre:

| Pregunta | Respuesta |
|---|---|
| `core/` solo importa estándar y `core` | Sí (sin cambios) |
| Las pruebas importan `core` por su API pública (`from harness_agent.core import …`) | Sí; solo `core.loop` (`TurnStatus`) y `adapters.storage`/`adapters.providers.*` como en pruebas vecinas |
| `Composition` sigue siendo la única raíz | Sí; las pruebas usan `compose()` |
| Falla cerrada | Sí; F-01/F-02 se anotan, no se cambian |
| Archivos protegidos intactos | Sí; se verifica con `git diff` (T010) |
| Nada de red, claves ni proveedor real | Sí; `FakeProvider` y proveedores locales |

## Verificación de fronteras (verificar-fronteras-hexagonales)

La historia no toca `core/`, `cli/`, `adapters/`, `pyproject.toml` ni la CI. Se corre `pytest tests/architecture` (tras `git add -N .`, por la guarda de secretos) y se deja el resultado en `PROGRESO.md`. Sin guarda `ast` nueva (no hay módulo de producción). Confirmación: `ci.yml` sigue en Ubuntu y Windows y no se modifica.

## Diseño de las pruebas

### `core_kill_child.py` (ayudante, tipado para `mypy`)

`python core_kill_child.py <modo> <db> <workspace> [<id-de-sesión>]`. Construye `HarnessConfig` con `make_config`-equivalente mínimo (`Paths(workspace_root, sessions_db)`, `Limits(max_turns=5000, max_output_tokens=777)`), `compose(config, provider_factory=…, system_name="Linux")` y registra la herramienta `eco` (riesgo bajo, `path`).

| Modo | Entrada de `run_session` | Proveedor | Efecto |
|---|---|---|---|
| `block-provider` | `tarea 1`, `tarea 2`, `tarea 3`, `/salir` | cada petición: llamada con `eco` y respuesta de texto; en la **3.ª petición**, antes de responder, escribe el checkpoint y `await asyncio.Event().wait()` | El hijo queda inmóvil con la petición en vuelo |
| `block-tool` | igual | la 3.ª petición llama a `eco` y la herramienta escribe el checkpoint y se bloquea | Llamada del asistente sin resultado |
| `busy` | 5 000 líneas `tarea n` | cada petición: `eco` + texto; en la 6.ª llamada al modelo escribe el checkpoint y **sigue** | Escribe sin parar hasta que lo matan |
| `resume` | `/reanudar <id>`, `seguimos`, `/salir` | responde texto | Imprime un JSON con `integrity_check`, eventos de la sesión antes y después, la salida de la consola |

El **checkpoint** es `CHECKPOINT ` + JSON `{"session": …, "events": [[id, tipo], …]}` leído con `sqlite3.connect(db)` (conexión nueva, solo ve lo confirmado), con `print(..., flush=True)`. La consola de `run_session` va a `io.StringIO`, nunca a stdout.

### Utilidades del padre (en `test_core_abrupt_kill_resume.py`)

- `Child` (gestor de contexto): `subprocess.Popen([sys.executable, str(HELPER), …], stdout=PIPE, stderr=PIPE, text=True, env={**os.environ, "PYTHONPATH": SRC_DIR})`; un hilo lee stdout línea a línea y las pone en una `queue.Queue`; `checkpoint(timeout=60)` devuelve el JSON o falla con la salida de error si el hijo murió antes; `kill()` = `Popen.kill()` + `wait(timeout=30)`; `__exit__` mata y espera siempre (sin huérfanos).
- `reopen(db)`: lee con `sqlite3` los ids/tipos de los eventos de la sesión y `PRAGMA integrity_check`.
- `resume_in_new_process(db, workspace, session)`: lanza el modo `resume`, espera su salida (tope 90 s) y devuelve el JSON.

### Pruebas (nombres reales)

`test_core_abrupt_kill_resume.py`
- `test_ac01_a_killed_process_with_the_provider_in_flight_loses_no_event_and_resumes`
- `test_ac01_a_process_killed_in_a_tool_resumes_with_the_call_closed`
- `test_ac01_a_process_killed_while_writing_keeps_the_confirmed_events_as_a_prefix` (5 repeticiones)

`test_core_failure_modes.py`
- `test_ac02_a_failure_after_a_tool_switches_and_repeats_the_call_with_its_result` (× 4 errores: cuota, límite de tasa, tiempo agotado, servicio no disponible)
- `test_ac02_a_raising_tool_reaches_the_model_as_a_bounded_error_and_the_turn_goes_on`
- `test_ac02_a_tool_error_leaves_event_audit_and_trace_without_the_exception_text`
- `test_a_base_exception_of_a_tool_that_is_not_a_cancellation_propagates_unconverted` (caracterización, F-01)

`test_harness_own_time.py`
- `test_ac03_the_own_time_of_the_harness_per_turn_is_below_the_threshold_and_is_recorded`
- `test_ac03_the_measurement_subtracts_the_latency_of_the_model`

Total: **9 funciones de prueba nuevas = 16 casos** (3 de proceso real con el escenario ocupado ×5 = 7; 4 de fallos con el error elegible ×4 = 7; 2 de tiempo). El recuento real lo fija `pytest --collect-only` en T010.

### Detalle de la medición (AC-03)

- `compose(make_config(tmp_path, workspace=ws), provider_factory=lambda _c: timed, system_name="Linux")` con `Limits(max_turns=10_000, …)`; `composition.registry.register(Echo())` (riesgo bajo, `path`); guion de 2 × (200 + 10) pasos: `eco` y texto.
- `Timed(FakeProvider)`: `complete` mide con `time.perf_counter` y acumula en `self.spent`.
- Por turno: `history = list(composition.history_prefix)`; `t0`, `await composition.loop.run_turn(session_id=…, task=…, history=history)`, `own = (t1 − t0) − (spent_después − spent_antes)`.
- Se comprueba que el turno terminó `COMPLETED`, que la tabla `trazas` tiene `2 × turnos` filas de modelo y `auditoria` una por herramienta (la medición pasó por las envolturas reales) y que `spent / llamadas < 5 ms`.
- Estadística con `statistics.median` y el percentil 95 por orden (`sorted(own)[ceil(0,95 × n) − 1]`).
- Registro: `record_property("own_time_median_ms", …)`, `p95`, `max`, `turns`, `threshold_ms`; una línea con `capsys.disabled()`; JSON opcional en `HARNESS_TIMING_REPORT`. `gc.collect()` antes de medir.

## Tabla FR / AC → tarea → prueba

| FR / AC | Tarea | Prueba |
|---|---|---|
| FR-001, FR-002, FR-003 · AC-01 (proveedor en vuelo) | T002 | `test_ac01_a_killed_process_with_the_provider_in_flight_…` |
| FR-001, FR-002 · AC-01 (herramienta en vuelo) | T003 | `test_ac01_a_process_killed_in_a_tool_…` |
| FR-002, FR-003 · AC-01 (sigue escribiendo) | T004 | `test_ac01_a_process_killed_while_writing_…` (×5) |
| FR-004 · AC-02 (proveedor a mitad de turno) | T005 | `test_ac02_a_failure_after_a_tool_…` (×4) |
| FR-005 · AC-02 (herramienta con excepción) | T006 | `test_ac02_a_raising_tool_…`, `test_ac02_a_tool_error_leaves_…` |
| FR-006 · AC-02 (cancelación / BaseException) | T006 (+ existentes citados en la spec) | `test_a_base_exception_of_a_tool_…`; cancelación: `tests/core/test_loop_failures.py`, `test_resume_cuts.py` |
| FR-007, FR-008 · AC-03, regla 2 | T007 | `test_ac03_the_own_time_…`, `test_ac03_the_measurement_subtracts_…` |
| FR-009 (CI sin dependencias) | T010 | cuatro puertas; `ci.yml` y `pyproject.toml` sin diff |
| FR-010 (protegidos) | T010 | `git diff` vacío |
| SC-004 (detección) | T008, T009 | mutaciones M1–M9 |
| SC-003 (cifra registrada) | T007, T011 | línea impresa y `PROGRESO.md` |

## Mutaciones de control (T008, T009)

Se hacen sobre una **copia temporal** de `src/` (en el directorio de trabajo temporal de la sesión, fuera del repo), ejecutando las pruebas con `-o pythonpath=<copia>` y comprobando antes que `harness_agent.__file__` apunta a la copia. Cada mutante se revierte; al final `git diff -- src` del repo real debe estar vacío.

| Id | Mutante (en la copia) | Prueba que debe fallar |
|---|---|---|
| M1 | `SqliteSessionStore.save_event`: confirma (COMMIT) cada 3 eventos en lugar de cada uno | AC-01 proveedor en vuelo |
| M2 | `bootstrap.py`: suscribir la captura de mensajes **después** del registrador de eventos | AC-01 sigue escribiendo (la reanudación falla **si** el corte cae entre evento y mensaje: depende del azar; si sobrevive se documenta, lo vigila `test_conversation_boundaries`) |
| M3 | `resume.py`: no cerrar las llamadas sin resultado | AC-01 herramienta en vuelo |
| M4 | `core/failover.py`: quitar `ProviderTimeout` de `ELIGIBLE_ERRORS` | AC-02 proveedor a mitad de turno (caso tiempo agotado) |
| M5 | `FailoverProvider`: repetir la llamada con los mensajes sin el resultado de la herramienta | AC-02 proveedor a mitad de turno |
| M6 | `core/loop.py::_execute`: `except Exception` relanza | AC-02 herramienta con excepción |
| M7 | `core/loop.py::_execute`: `except BaseException` convierte en resultado | caracterización `BaseException` |
| M8 | `core/loop.py::_emit` (o `TracingRegistry`): `time.sleep(0.6)` por turno | AC-03 umbral |
| M9 | En la **prueba** (copia): el proveedor espera 10 ms por llamada sin restarlo | AC-03 «la latencia del modelo es cero» |

Estabilidad: el escenario ocupado se repite 5 veces por defecto y, una sola vez en T009, 20 veces seguidas; la medición, 5 corridas seguidas.

## Riesgos

- **Procesos hijo en Windows**: lectura de stdout con hilo y cola (no `readline` bloqueante en el hilo principal), `kill()` y `wait(timeout)` en `finally`, `PYTHONPATH` explícito; sin `os.setsid` ni señales POSIX.
- **Escenario ocupado no determinista**: la garantía que se afirma es de prefijo y de integridad, no de un número de eventos; si el corte cayera entre el mensaje y el evento, la reanudación debe seguir funcionando (la captura va antes del registrador). Si no lo hiciera, **es un hallazgo real**: se detiene y se anota.
- **Duración**: 3 escenarios de proceso ≈ 2–4 s cada uno (×5 el ocupado) y la medición ≈ 10 s en total.
- **Umbral de tiempo en una CI lenta**: ver D-10; mediana con ≈ 12× de margen y p95 solo informativo.
- **Disco compartido (OneDrive)**: las pruebas usan `tmp_path` del sistema; no escriben en el repositorio.

## Archivos protegidos (no tocar)

`src/` entero (historia solo de pruebas), `pyproject.toml`, `.github/workflows/ci.yml`, `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py`, `core/verification/`, `tests/doubles/`, `tests/spikes/mcp_demo_server.py`, `docs/archivo/`.
