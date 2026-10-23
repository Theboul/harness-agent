# Implementation Tasks: HU-00-03 — Proveedor simulado para pruebas

**Feature**: `specs/012-fake-provider/spec.md`  
**Plan**: `specs/012-fake-provider/plan.md`  
**Responsable**: B — Estado  
**Sprint**: Sprint 1 | **PHU**: 2  
**Tareas de referencia**: Sp1-07, Sp1-08  

---

## Cómo leer este documento

**Pruebas primero, dentro de cada tarea.** Cada tarea agrupa las pruebas y la implementación de una pieza: se escriben las pruebas, se ejecutan y se confirma que fallan **por la razón esperada** (`ImportError` del símbolo nuevo o aserción concreta), se implementa lo mínimo y se vuelve a ejecutar hasta que pasen. El rojo esperado de cada tarea está en su *Verificación*.

**Ritmo**: 9 tareas de trabajo (T002 a T010) de 40 min como máximo, una de inicio (T001), una de cierre (T011) y dos humanas (T012, T013). Ninguna pasa de 40 min (la Constitución permite 40; el límite absoluto es 60).

**Reglas que valen para todas las tareas:**
- **Archivos protegidos**: no modificar `src/harness_agent/core/loop.py`, `tests/doubles/scripted_provider.py`, `tests/doubles/dummy_provider.py`, ninguna prueba existente ni `docs/archivo/`. Los únicos archivos existentes que se tocan son `src/harness_agent/core/interfaces/provider.py`, `src/harness_agent/core/interfaces/__init__.py`, `src/harness_agent/core/__init__.py` (solo reexportar), `tests/doubles/__init__.py` (solo exportar `FakeProvider`), `docs/guia-contratos-desarrollo.md` y `docs/PROGRESO.md`.
- `core/` solo con biblioteca estándar; no importa `tests/`, `cli/` ni `adapters/`. Python 3.12. Sin dependencias nuevas.
- Todo el código y las pruebas deben pasar `mypy --strict` y `ruff` (línea de 100 columnas). Nombres en inglés; textos de usuario y documentación en español.
- Los tipos, las reglas y las transiciones siguen [contracts/fake_provider_contract.md](contracts/fake_provider_contract.md) y [data-model.md](data-model.md); las decisiones, [research.md](research.md) (R-01 a R-08) y [plan.md](plan.md) (D1 a D10).
- **Aislamiento**: ninguna prueba usa red, proveedor real, reloj ni el entorno. Las pruebas de integración usan `AgentLoop`, `RecordingEventBus`, `InMemoryToolRegistry`, `ScriptedPolicy` y `RecordingTool` de `tests/doubles`, construidos como en `tests/core/support.py` (`make_rig`), pero con `FakeProvider`.
- **Sin literales detectables**: ninguna prueba contiene texto que `tests/architecture/test_no_secrets_in_repo.py` detecte como clave; usar `VALOR-DE-PRUEBA-123` como centinela.
- **Al cerrar cada tarea que toca código o pruebas**, ejecutar `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`; los cuatro con código 0, y registrar el resultado en `docs/PROGRESO.md` dentro de los 5 min de la tarea.

**Correspondencia con las tareas del plan de sprint:**

| Tarea F5 | Descripción en `docs/03-plan-sprints.md` | Presupuesto | Microtareas |
|---|---|---|---|
| **Sp1-07** | Implementar FakeProvider que lee un guion | 180 min (3 h) | T002, T003, T004, T005 |
| **Sp1-08** | Añadir modo de fallo configurable (cuota, tiempo agotado, indisponible) | 90 min (1,5 h) | T006, T007 |
| Transversal | Guion agotado y mal formado, fronteras, guía, estado, cierre, revisión y CI remota (Principios VIII y IX) | — | T001, T008, T009, T010, T011, T012, T013 |

**Nota sobre la estimación**: la suma de las tareas de trabajo supera los 270 min presupuestados en Sp1-07 y Sp1-08 (véase el final); se avisa a B en `PROGRESO.md` (T001).

---

## Phase 1: Setup (estado)

**Propósito**: Marcar la historia `En curso`.

- [x] **T001** Marcar HU-00-03 como `En curso` en `docs/PROGRESO.md` (transversal)
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: Ninguna
  - **Criterios relacionados**: Principio VIII
  - **Tarea F5**: Transversal
  - **Estimación**: 20 min (10 min impl + 5 min check + 5 min registro)
  - **Verificación**: La fila de `HU-00-03` de la tabla de Sprint 1 pasa de `Pendiente` a `En curso` con responsable `B — Estado`; Commit/PR vacío; se añade el bloque **Observaciones de HU-00-03** con el aviso de capacidad, la ampliación aditiva del puerto (pendiente del visto bueno de A) y la nota de HU-00-01 `Pendiente de aprobación técnica`; ninguna otra fila ni la tabla *Resumen* cambian (`git diff -U0 docs/PROGRESO.md`).

---

## Phase 2: Foundational — Jerarquía de errores canónica (Sp1-07, bloquea US1 a US3)

**Propósito**: Los tipos de error que el doble lanza y el adaptador real reutilizará.

- [x] **T002** Añadir `ProviderError`, `QuotaExceeded`, `ProviderTimeout` y `ProviderUnavailable` al puerto y reexportarlos, con sus pruebas (FR-001 a FR-005)
  - **Archivos**: `tests/unit/core/test_provider_errors.py`, `src/harness_agent/core/interfaces/provider.py`, `src/harness_agent/core/interfaces/__init__.py`, `src/harness_agent/core/__init__.py`
  - **Dependencias**: T001
  - **Criterios relacionados**: AC-02, regla de negocio 2, FR-001, FR-002, FR-003, FR-004, FR-005, SC-006, contrato §1, data-model (Producción), research R-01
  - **Tarea F5**: Sp1-07
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero: los tres tipos son subclases de `ProviderError` y esta de `Exception`; se importan de `harness_agent.core` y de `harness_agent.core.interfaces`; están en `core.__all__` sin repetirse; conservan el mensaje; la firma de `Provider.complete` no cambió (`inspect.signature`); `provider.py` no importa nada nuevo fuera de la biblioteca estándar. Rojo esperado: `ImportError: cannot import name 'ProviderError'`. Cierre: los cuatro comandos en 0; los módulos tocados al 100 %; `test_contracts.py` y `test_core_public_api.py` sin cambios y en verde.

---

## Phase 3: User Story 1 — Reproducir un guion de respuestas sin red (P1) [AC-01]

**Objetivo**: Un guion de respuestas de texto y de llamadas a herramientas que el bucle consume de forma determinista y sin red.

**Prueba independiente**: Un guion de tres pasos corre dos veces con el bucle real; historial, eventos y estado son idénticos y no se abre ningún socket.

- [x] **T003** [US1] Implementar `FakeProvider` (reproducción de respuestas, registro y copias) y exportarlo, con sus pruebas (FR-006 a FR-014)
  - **Archivos**: `tests/unit/doubles/__init__.py`, `tests/unit/doubles/test_fake_provider.py`, `tests/doubles/fake_provider.py`, `tests/doubles/__init__.py`
  - **Dependencias**: T002
  - **Criterios relacionados**: AC-01, regla de negocio 1, FR-006, FR-007, FR-008, FR-009, FR-010, FR-011 (ids), FR-012, FR-014, FR-017, contrato §2, data-model (Prueba), research R-03, R-04 y R-07, plan D2 a D6
  - **Tarea F5**: Sp1-07
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero: la llamada i devuelve el paso i; el orden se mantiene en 3 llamadas; devuelve una copia (mutar la respuesta no cambia la siguiente instancia del mismo guion); el guion original mutado después de construir no afecta; `received` y `received_tools` guardan copias; `call_count` cuenta; un paso sin `usage` devuelve `usage is None` y uno con `usage` lo devuelve sin cambios; ids de llamada vacíos o repetidos se rechazan al construir con `ValueError` que nombra el id; dos instancias del mismo guion son independientes; `isinstance(provider, Provider)` y la misma firma de `complete`. En esta tarea el guion solo acepta `ProviderResponse`. Rojo esperado: `ImportError: cannot import name 'FakeProvider'`. Cierre: los cuatro comandos en 0; `fake_provider.py` al 100 %; `git diff` de `tests/doubles/` solo muestra el archivo nuevo y `__init__.py`.

- [x] **T004** [P] [US1] Prueba de contrato: `FakeProvider` es intercambiable con los otros dobles (FR-019)
  - **Archivos**: `tests/contracts/test_fake_provider_contract.py`
  - **Dependencias**: T003
  - **Criterios relacionados**: AC-01, regla de negocio 1, FR-019, SC-005
  - **Tarea F5**: Sp1-07
  - **Estimación**: 25 min (15 min impl + 5 min check + 5 min registro)
  - **Verificación**: Con el mismo consumidor mínimo de `tests/contracts/test_provider_interchangeability.py` (se importa o se replica en el módulo nuevo, sin editar el existente), `DummyProvider`, `ScriptedProvider` y `FakeProvider` son intercambiables sin cambiar el consumidor; `FakeProvider` cumple `isinstance(…, Provider)` y devuelve `ProviderResponse`. Sin código nuevo: no hay rojo previo porque valida T003 (se demuestra con una mutación temporal: cambiar el tipo devuelto hace fallar la prueba). Cierre: los cuatro comandos en 0.

- [x] **T005** [US1] Integración AC-01: determinismo y «sin red» con el bucle real (FR-009, FR-010, FR-018)
  - **Archivos**: `tests/integration/test_fake_provider_agent_loop.py`
  - **Dependencias**: T003
  - **Criterios relacionados**: AC-01, FR-009, FR-010, FR-018, SC-001, SC-002, research R-04 y R-05, plan D8 y D9
  - **Tarea F5**: Sp1-07
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Sin código de producción nuevo. Una fixture parchea `socket.create_connection` y `socket.getaddrinfo` para fallar la prueba si se llaman, y `socket.socket.connect` para fallar ante cualquier destino que no sea loopback ni `AF_UNIX` (en Windows el bucle de asyncio conecta a loopback en `socketpair()`); se aplica a todo el módulo (`autouse`). Un guion de tres pasos (dos llamadas a `RecordingTool` y una respuesta final) corre con `AgentLoop` 20 veces; en cada una, el historial y la lista `(tipo, carga)` de eventos son idénticos a la primera (se excluyen `id` y `timestamp`, D9); el proveedor recibió en cada llamada los mensajes acumulados esperados; la herramienta se ejecutó dos veces con los argumentos del guion. Nombres de prueba con `determinism` y `no_network` para el recorrido del quickstart §3. No hay rojo previo porque valida T003; una autoprueba de la fixture comprueba que un `connect` a una dirección no local falla y que uno a loopback pasa. Cierre: los cuatro comandos en 0.

---

## Phase 4: User Story 2 — Simular fallos con los tipos canónicos (P1) [AC-02]

**Objetivo**: El guion puede forzar `QuotaExceeded`, `ProviderTimeout` y `ProviderUnavailable` en cualquier posición, y el bucle recibe el mismo tipo que daría un proveedor real.

**Prueba independiente**: Con el bucle real y un guion cuyo primer paso es `QuotaExceeded`, el turno termina como fallo de proveedor y el evento lleva `error_type == "QuotaExceeded"`.

- [x] **T006** [US2] Admitir pasos de fallo (`ProviderError`) en el guion de `FakeProvider`, con sus pruebas (FR-007, FR-015, FR-016)
  - **Archivos**: `tests/unit/doubles/test_fake_provider.py`, `tests/doubles/fake_provider.py`
  - **Dependencias**: T003
  - **Criterios relacionados**: AC-02, regla de negocio 2, FR-007, FR-008, FR-015, FR-016, SC-003, SC-004, contrato §2, research R-06, plan D4 y D7
  - **Tarea F5**: Sp1-08
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero (clase nueva en el módulo existente de T003): cada uno de los tres tipos se lanza como el tipo exacto y es instancia de `ProviderError`; un fallo en primera, tercera y última posición deja pasar las respuestas anteriores; el mensaje se conserva; el fallo se lanza una copia (dos instancias del mismo guion lanzan objetos distintos); la llamada tarda menos de 10 ms (`time.perf_counter`) y no usa `sleep` (se parchea `asyncio.sleep` y `time.sleep` para fallar si se llaman); `call_count` avanza también en los fallos; un guion que mezcla éxitos y fallos se repite igual en una instancia nueva. Rojo esperado: `ValueError` por paso de tipo no admitido en T003. Cierre: los cuatro comandos en 0; `fake_provider.py` al 100 %.

- [x] **T007** [US2] Integración AC-02: el bucle recibe el tipo de error canónico (FR-018, SC-003)
  - **Archivos**: `tests/integration/test_fake_provider_agent_loop.py`
  - **Dependencias**: T005, T006
  - **Criterios relacionados**: AC-02, regla de negocio 2, FR-018, SC-003, SC-004, contrato §3, research R-02
  - **Tarea F5**: Sp1-08
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: Sin código de producción nuevo; clase nueva en el módulo de T005 (con la misma fixture de red bloqueada). Parametrizada por los tres tipos: con el fallo en el primer paso, `run_turn` devuelve `TurnStatus.PROVIDER_FAILED`, se publica un `PROVIDER_ERROR` con `reason == "provider_exception"` y `error_type` igual al nombre del tipo, y el tipo es el mismo objeto que `harness_agent.core` exporta. Un fallo en la tercera llamada deja el historial de las dos primeras. Un fallo con un mensaje largo se acota por el bucle sin romper la prueba. Los nombres de las pruebas incluyen `quota`, `timeout` y `unavailable` para el recorrido del quickstart §3. El turno entero tarda menos de 10 ms de forma holgada (SC-004 se comprueba con una cota generosa de 500 ms para no ser frágil en CI, y la cota estricta de 10 ms queda en T006). No hay rojo previo porque valida T002 y T006. Cierre: los cuatro comandos en 0.

---

## Phase 5: User Story 3 — Guion agotado y mal formado fallan de forma explícita (P2)

**Objetivo**: Un guion corto o inválido produce un error claro, nunca una respuesta inventada.

**Prueba independiente**: N+1 llamadas lanzan `ScriptExhausted` y marcan `exhausted`; los guiones inválidos se rechazan al construir.

- [x] **T008** [US3] Guion agotado, guion vacío, pasos inválidos y no bloqueo del bucle de eventos (FR-011, FR-013)
  - **Archivos**: `tests/unit/doubles/test_fake_provider.py`, `tests/doubles/fake_provider.py`
  - **Dependencias**: T006
  - **Criterios relacionados**: FR-011, FR-013, spec US3, research R-03, plan D3 y D5
  - **Tarea F5**: Transversal
  - **Estimación**: 30 min (15 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero: la llamada N+1 lanza `ScriptExhausted` (el de `tests.doubles`) y `exhausted` pasa a `True`, y `call_count` sigue contando; las llamadas siguientes también lanzan; un guion vacío, un paso `None`, un `str`, una excepción que no sea `ProviderError`, una *clase* de error sin instanciar (`QuotaExceeded`) y un `ProviderResponse` con id de llamada vacío se rechazan al construir con `ValueError` cuyo mensaje incluye el índice del paso; `await provider.complete(...)` dentro de `asyncio.gather` con un bucle de eventos auxiliar no queda bloqueado (`run_bounded`); cancelar la tarea entre dos llamadas no avanza `call_count`. Rojo esperado: las rutas de agotado y validación aún no existen o no cubren todos los casos. Cierre: los cuatro comandos en 0; `fake_provider.py` al 100 % de líneas y ramas.

---

## Phase 6: User Story 4 — Convivencia y documentación (P2)

**Objetivo**: Nada de lo existente se rompe, el núcleo sigue puro y cada integrante sabe qué doble usar.

**Prueba independiente**: La suite existente sigue en verde sin cambios; una prueba de arquitectura confirma las fronteras; la guía explica los tres dobles.

- [x] **T009** [P] [US4] Prueba de arquitectura: `core/` no importa `tests/` ni terceros tras la ampliación del puerto (FR-020)
  - **Archivos**: `tests/architecture/test_provider_errors_boundaries.py`
  - **Dependencias**: T002
  - **Criterios relacionados**: FR-004, FR-020, spec US4, constitución Principio III
  - **Tarea F5**: Transversal
  - **Estimación**: 30 min (15 min impl + 10 min check + 5 min registro)
  - **Verificación**: Con `ast`, ningún módulo de `core/` importa `tests`, `harness_agent.cli` ni `harness_agent.adapters`; `provider.py` solo importa biblioteca estándar y módulos de `harness_agent.core`; `tests/doubles/fake_provider.py` solo importa biblioteca estándar, `harness_agent.core` (API pública o `harness_agent.core.interfaces.provider`, como los otros dobles) y `tests.doubles.scripted_provider`. Autoprueba con fragmentos que sí violan la regla. Línea base limpia, así que no hay rojo previo (la autoprueba demuestra el detector). Cierre: los cuatro comandos en 0.

- [x] **T010** [P] [US4] Documentar qué doble de proveedor usar y cómo escribir un guion con fallos (FR-021)
  - **Archivos**: `docs/guia-contratos-desarrollo.md`
  - **Dependencias**: T008
  - **Criterios relacionados**: FR-021, SC-007, contrato §2 y §4
  - **Tarea F5**: Transversal
  - **Estimación**: 25 min (15 min impl + 5 min check + 5 min registro)
  - **Verificación**: En la sección de B (donde ya figura «HU-00-03 (FakeProvider)») se añade la tabla de qué doble usar (Dummy, Scripted, Fake), un ejemplo de guion con una llamada a herramienta, un fallo de cuota y una respuesta final, y la importación de los errores desde `harness_agent.core`; el ejemplo se ejecuta tal cual en un script temporal fuera del repositorio (scratchpad) y termina con el comportamiento descrito. Sin cambios en otras secciones (`git diff -U0 docs/guia-contratos-desarrollo.md`). No cambia código, así que solo se ejecuta `ruff format --check .` y `pytest` para confirmar que nada se rompió.

---

## Phase 7: Cierre

- [x] **T011** Cierre: verificación completa y registro en `docs/PROGRESO.md` (transversal)
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: T001 a T010
  - **Criterios relacionados**: Principios VIII, IX y X, FR-017, FR-022, FR-023, SC-005, SC-006
  - **Tarea F5**: Transversal
  - **Estimación**: 35 min (15 min impl + 15 min check + 5 min registro)
  - **Verificación**: Los cuatro comandos de CI en 0; cobertura del módulo nuevo y de los errores al 100 %; recorrido manual del quickstart §3 y §4; `git diff --exit-code "$(git merge-base HEAD origin/main)" -- docs/archivo src/harness_agent/core/loop.py tests/doubles/scripted_provider.py tests/doubles/dummy_provider.py` → 0; `git diff --stat` contra `origin/main` solo lista los archivos de la lista de este plan; detector de claves de HU-00-04 sin coincidencias. La fila de HU-00-03 pasa a `En revisión` (no a `Hecha`: faltan T012 y T013), con rutas y evidencia; la tabla *Resumen* no cambia hasta `Hecha`; se añade una línea al registro de cambios por tarea.

- [ ] **T012** *(humana)* Visto bueno de A a la ampliación del puerto y revisión cruzada por A o C
  - **Archivos**: —
  - **Dependencias**: T011
  - **Criterios relacionados**: Principio IX, spec Supuestos
  - **Estimación**: según la persona revisora
  - **Verificación**: A confirma por escrito que acepta `ProviderError`, `QuotaExceeded`, `ProviderTimeout` y `ProviderUnavailable` en `core/interfaces/provider.py`; un integrante de otra área revisa el PR. HU-00-01 sigue `Pendiente de aprobación técnica` y debe ratificarse antes de pasar a `Hecha`.

- [x] **T013** *(humana)* Ejecución de la CI en Linux y Windows y relleno de Commit/PR
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: T012
  - **Criterios relacionados**: Principio IX
  - **Estimación**: según la CI
  - **Verificación**: la matriz de CI pasa en ambos sistemas; la fila de HU-00-03 recibe Commit/PR y, solo entonces, puede pasar a `Hecha`.

---

## Dependencias y orden de ejecución

```
T001 → T002 → T003 → T004 [P]
                 ├──→ T005 ─┐
                 └──→ T006 ─┴→ T007
                      └──→ T008 → T010 [P]
T002 → T009 [P]
T001..T010 → T011 → T012 → T013
```

- **US1** (T003 a T005) y **US2** (T006, T007) son P1 y comparten el módulo `fake_provider.py`, así que van en serie; T004 y T009 no tocan archivos de otras tareas y pueden ir en paralelo.
- **MVP**: T001, T002, T003 y T005 cubren AC-01; añadir T006 y T007 cubre AC-02.

## Estimación frente al presupuesto

| Concepto | Minutos |
|---|---|
| Sp1-07 + Sp1-08 presupuestados | 270 |
| T002 a T008 (código y pruebas) | 240 |
| T009, T010 (fronteras y guía) | 55 |
| T001, T011 (estado y cierre) | 55 |
| **Total de tareas de trabajo** | **350** |

Exceso aproximado de 80 min (1,3 veces) sobre lo presupuestado, sin contar las dos tareas humanas; se avisa a B en T001.
