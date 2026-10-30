# Tasks: HU-07-04 — Reintentos con espera exponencial

**Input**: `specs/034-provider-retries/` (spec, plan, research, data-model, contracts)

**Mapeo a tareas del plan de sprints**: Sp3-40 «Implementar la política de reintentos» (1,5 h) y Sp3-41 «Prueba con el proveedor simulado» (1 h). El presupuesto es una advertencia, no un límite; el orden por sprints ya no rige (cierre adelantado al 2026-11-06).

**Convención**: pruebas primero; cada prueba se ve fallar **por la razón esperada** antes de implementar. Tareas de 15–40 min. Comandos de calidad al cerrar cada fase útil: `ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest --basetemp=C:\tmp\ptXX`.

**Archivos protegidos (no se tocan)**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `cli/`, `tests/doubles/`, `docs/archivo/`.

## Phase 1: Setup

- [x] T001 Ejecutar la línea base (`pytest`, `pytest tests/architecture`) y anotar cuántas pruebas pasan; revisar qué pruebas de `tests/unit/test_config_*.py` y `tests/unit/test_bootstrap_*.py` enumeran las tablas o los campos de `HarnessConfig`/`Composition` y pueden cambiar con el campo nuevo (corrida en seco)

## Phase 2: Foundational

- [x] T002 [P] Prueba y tipo `RateLimited(QuotaExceeded)` con `retry_after` validado (finito ≥ 0, no `bool`, otro ⇒ `None`) y mensaje que no reproduce datos, en `tests/unit/adapters/providers/test_rate_limited.py` y `src/harness_agent/adapters/providers/errors.py`
- [x] T003 [P] Pruebas y tipos `RetryPolicy` (validación 1–10, > 0, `max_delay ≥ base_delay`, mensajes en español sin el valor) y `RetryAttempt` en `tests/unit/adapters/providers/test_retry_policy.py` y `src/harness_agent/adapters/providers/retrying_provider.py`

## Phase 3: User Story 1 — Un fallo pasajero no tumba la tarea (P1) 🎯 MVP

**Prueba independiente**: `FakeProvider` falla con límite de tasa / tiempo agotado / no disponible y luego responde; la envoltura devuelve la respuesta con esperas crecientes y registro de cada intento.

- [x] T004 [US1] Pruebas rojas de la envoltura: éxito directo sin espera; 2 fallos temporales ⇒ 3 llamadas y esperas 2, 4 (con `sleep` registrador); cada uno de los tres tipos temporales; el tope `max_delay`; mensajes y herramientas llegan iguales a cada intento, en `tests/unit/adapters/providers/test_retrying_success.py`
- [x] T005 [US1] Implementar `RetryingProvider.complete` (bucle de intentos, espera exponencial con tope, `sleep` inyectable) hasta poner en verde T004, en `src/harness_agent/adapters/providers/retrying_provider.py`
- [x] T006 [US1] Prueba roja e implementación del observador: recibe un `RetryAttempt` por reintento con número, máximo, tipo de fallo y espera; el centinela `VALOR-DE-PRUEBA-123` del mensaje del error no aparece en el registro; un observador que lanza no cambia el resultado, en `tests/unit/adapters/providers/test_retrying_observer.py` y `retrying_provider.py`
- [x] T007 [US1] Prueba roja y cambio mínimo del adaptador: `RateLimitError` ⇒ `RateLimited` (con `retry_after` del atributo del error si es válido) y `PaymentRequiredError`/`BudgetExceededError` siguen siendo `QuotaExceeded` simple; actualizar la prueba de `ERROR_TABLE` existente, en `tests/unit/adapters/providers/test_errors.py` y `src/harness_agent/adapters/providers/litellm_provider.py`

## Phase 4: User Story 2 — Lo permanente falla enseguida, lo temporal se rinde a tiempo (P1)

**Prueba independiente**: errores no temporales ⇒ 1 llamada y 0 esperas; temporal permanente ⇒ N llamadas y el mismo error.

- [x] T008 [US2] Pruebas rojas: `QuotaExceeded` simple, `ProviderError` genérico y una excepción ajena se propagan al instante; agotado ⇒ `max_attempts` llamadas, `max_attempts − 1` esperas y la misma instancia de error; `max_attempts = 1` no reintenta; pista válida mayor que la exponencial la sustituye; pista > `max_delay` ⇒ propaga sin reintentar; pista inválida se ignora, en `tests/unit/adapters/providers/test_retrying_failures.py`
- [x] T009 [US2] Pruebas rojas de cancelación: `CancelledError` del proveedor y durante el `sleep` se propaga sin reintento (D-01) y sin llamar al observador más; implementar lo que falte en `retrying_provider.py`

## Phase 5: User Story 3 — Configuración y cableado (P2)

**Prueba independiente**: `[retries]` ajusta los valores; sin sección, defectos; `compose()` envuelve el proveedor y publica el evento.

- [x] T010 [US3] Pruebas rojas de configuración: defectos 5/2/30, valores válidos, `max_attempts` fuera de 1–10, tipos erróneos (`bool`, texto), `base_delay ≤ 0`, `max_delay < base_delay`, campo desconocido en la sección, mensaje sin el valor, en `tests/unit/test_config_retries.py`
- [x] T011 [US3] Implementar en `src/harness_agent/config.py` (cambio aditivo): `Retries` (frozen), `_RETRY_FIELDS`, entrada `"retries"` de `_TABLE_FIELDS`, `_check_retries`, campo `HarnessConfig.retries = Retries()` y su paso en las dos construcciones; actualizar `config.example.toml`
- [x] T012 [US3] Pruebas rojas de composición: `compose()` envuelve el proveedor inyectado (un fallo temporal del `FakeProvider` se reintenta con una `sleep` inyectada), el evento `provider_error` `{reason: "retry", error_type, attempt, max_attempts, delay_seconds}` llega al bus y se guarda en la sesión **activa** tras `/reanudar`, sin el centinela, en `tests/unit/test_bootstrap_retries.py`
- [x] T013 [US3] Implementar en `src/harness_agent/bootstrap.py` (aditivo): envolver el proveedor tras crear la sesión y antes del bucle y del compactador, convertir `Retries` → `RetryPolicy`, observador que emite `provider_error` con el cursor de sesión, actualizar el cursor en `run_session` al reanudar; `compose(..., sleep=)` opcional solo para pruebas
- [x] T014 [US3] Prueba de integración con el bucle real: turno con `FakeProvider` [límite de tasa, no disponible, respuesta] ⇒ `TurnResult` correcto, dos eventos de reintento y ningún cambio en el resto de eventos; temporal permanente ⇒ el bucle publica su `provider_error` de siempre (`provider_exception`), en `tests/integration/test_retry_flow.py`

## Phase 6: Polish y cierre

- [x] T014b [US2] Prueba de contrato `tests/contracts/test_retrying_provider_contract.py`: la envoltura sobre `FakeProvider` cumple las mismas comprobaciones del contrato `Provider` que ya pasan el doble y el adaptador (revisar `test_fake_provider_contract.py` y `test_provider_interchangeability.py` para reutilizar su forma sin modificarlos)
- [ ] T015 [P] Guarda `ast` nueva `tests/architecture/test_retry_boundaries.py`: `retrying_provider.py` y `errors.py` solo importan biblioteca estándar y `harness_agent.core`; no usan `time.sleep` ni `threading`; no capturan `BaseException` ni `CancelledError`; con autoprueba y prueba de mutación como las guardas vecinas
- [ ] T016 Verificación de fronteras (`verificar-fronteras-hexagonales`): `pytest tests/architecture` y comprobación de archivos protegidos con `git diff --exit-code $(git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/loop.py tests/doubles docs/archivo`
- [ ] T017 Cobertura del módulo nuevo 100 % de líneas y ramas (`pytest --cov=harness_agent.adapters.providers`) y las cuatro puertas de calidad en exit 0
- [ ] T018 Documentación: `docs/PROGRESO.md` (fila a `En revisión`, Archivos, Evidencia real, registro de cambios sin líneas en blanco en la tabla, observación de HU-07-04 con la decisión del cierre adelantado, el hallazgo de `cli/render.py` y la propuesta de `RateLimited` en el puerto), `CLAUDE.md` (tabla «Qué existe hoy») y, si cambia la descripción de `adapters/providers`, las skills en `.claude/skills/` y `.agents/skills/`
- [ ] T019 **Humana — no marcar por Claude**: revisión cruzada por una persona de otra área (A debe ser revisada por B o C)
- [ ] T020 **Humana — no marcar por Claude**: CI remota en `ubuntu-latest` y `windows-latest`

## Dependencias

T001 → T002/T003 (paralelas) → T004 → T005 → T006 → T007 → T008 → T009 → T010 → T011 → T012 → T013 → T014 → T015…T018. T007 solo depende de T002 y puede hacerse tras T003. T019 y T020 al final y humanas.

## Estrategia

MVP = Fase 3 (T004–T007): la envoltura funciona y se prueba sola. Fases 4 y 5 endurecen y cablean. Una sola spec, una PR, commits por unidad de trabajo: (1) tipos + envoltura + adaptador (T002–T009), (2) configuración y cableado (T010–T014), (3) guarda y documentación (T015–T018).
