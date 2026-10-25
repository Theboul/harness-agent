# Implementation Tasks: HU-07-02 — Adaptador LiteLLM para el primer proveedor

**Feature**: `specs/017-litellm-provider-adapter/spec.md`  
**Plan**: `specs/017-litellm-provider-adapter/plan.md`  
**Responsable de la historia**: B — Estado (la implementa C por reasignación del equipo)  
**Sprint**: Sprint 1 | **PHU**: 2  
**Tareas de referencia**: Sp1-43, Sp1-44, Sp1-45  

---

## Cómo leer este documento

**Pruebas primero, dentro de cada tarea.** Cada tarea agrupa las pruebas y la implementación de una pieza: se escriben las pruebas, se ejecutan y se confirma que fallan **por la razón esperada** (indicada en cada tarea), se implementa lo mínimo y se pasan los cuatro comandos de calidad. No hay tareas de «solo pruebas» ni de «solo código».

**Ritmo (regla RITMO)**: 10 tareas de trabajo (T003 a T012) de 40 min como máximo; aparte, solo estas: inicio (T001), la tarea humana de acuerdo sobre la dependencia (T002), el cierre (T013), la prueba manual Sp1-45 (T014) y la revisión cruzada con la CI remota (T015). Si una tarea de trabajo se pasa de 40 min, se corta en la costura que indica su nota; el máximo absoluto de la Constitución es 60 min. El presupuesto del plan de sprint es un aviso, no un motivo para recortar alcance.

**Reglas que valen para todas las tareas:**
- **Archivos protegidos**: no modificar `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `cli/`, `tests/doubles/`, ninguna prueba existente ni `docs/archivo/`. Tampoco `.github/workflows/ci.yml`. Los únicos archivos existentes que se tocan son `src/harness_agent/config.py` (aditivo), `.env.example`, `config.example.toml`, `pyproject.toml`, `requirements-dev.txt`, `CLAUDE.md`, las skills (ambas copias) y `docs/PROGRESO.md`. Si un doble hace falta (p. ej. una herramienta permisiva), se define **dentro del archivo de prueba** que lo usa.
- `core/` no se toca. El adaptador importa solo biblioteca estándar, `harness_agent.core`, `harness_agent.adapters.converters` y su paquete; **`litellm` solo se carga con `importlib.import_module("litellm")` dentro de una función de `adapters/providers/`**. Python 3.12, `mypy --strict`, `ruff` a 100 columnas. Identificadores y docstrings en inglés; mensajes al usuario y documentación en español.
- Contratos y decisiones: [contracts/litellm_provider_contract.md](contracts/litellm_provider_contract.md), [contracts/config_additions_contract.md](contracts/config_additions_contract.md), [data-model.md](data-model.md), [research.md](research.md) y [plan.md](plan.md).
- **Aislamiento**: ninguna prueba usa red ni claves reales. Las pruebas de `tests/unit/adapters/providers/` instalan un guardia de red (`socket.getaddrinfo` y `socket.create_connection` fallan la prueba; patrón de `tests/spikes/test_litellm_tool_translation_spike.py`) y fijan `LITELLM_LOCAL_MODEL_COST_MAP=True` **antes** de cualquier import de `litellm`.
- **Sin literales detectables**: usar `VALOR-DE-PRUEBA-123` como centinela de la clave y de los datos de entrada; no asignar valores largos a nombres tipo `secret`, `token`, `password` (`tests/architecture/test_no_secrets_in_repo.py`).
- **Al cerrar cada tarea que toca código o pruebas**: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`, los cuatro con código 0, y `pytest tests/architecture`. La cobertura de `litellm_provider.py` debe llegar al **100 % de líneas y ramas** al cerrar T006 y se reconfirma en T013.
- **Entorno en Windows**: ejecutar con el venv de ruta corta `C:\tmp\h17` (ruta de `site-packages` bajo ~130 caracteres; véase `research.md` §4). Las pruebas con `importorskip("litellm")` solo corren si `litellm` está instalado en ese venv.

**Correspondencia con las tareas del plan de sprint** (presupuesto en `docs/03-plan-sprints.md`):

| Tarea F5 | Descripción | Presupuesto | Microtareas |
|---|---|---|---|
| **Sp1-43** | Implementar el adaptador sobre LiteLLM | 210 min (3,5 h) | T004, T006, T009, T010 |
| **Sp1-44** | Traducir llamadas y resultados de herramienta | 150 min (2,5 h) | T005, T007 |
| **Sp1-45** | Prueba manual con una tarea de tres pasos | 60 min (1 h) | T011 (archivo omitido sin clave), T014 (ejecución humana) |
| Transversal | Inicio, acuerdo, configuración aditiva, fronteras, guía, documentación, cierre, revisión y CI remota | — | T001, T002, T003, T008, T011, T012, T013, T015 |

---

## Phase 1: Setup (estado y acuerdo)

**Propósito**: Marcar la historia `En curso` y obtener el acuerdo previo sobre la dependencia nueva.

- [x] T001 Marcar HU-07-02 como `En curso` en `docs/PROGRESO.md` (transversal)
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: Ninguna
  - **Criterios relacionados**: Principio VIII
  - **Tarea F5**: Transversal
  - **Estimación**: 20 min (10 min impl + 5 min check + 5 min registro)
  - **Verificación**: La fila de `HU-07-02` de la tabla de Sprint 1 pasa de `Pendiente` a `En curso` con responsable `B — Estado` (implementa C); se añade el bloque **Observaciones de HU-07-02** con: la dependencia opcional `litellm[mcp]==1.106.2` pendiente de acuerdo (T002), la ampliación aditiva del esquema de HU-00-04 (`limits.max_output_tokens`) con aviso a B y al PO, y que HU-07-01, HU-00-04 y HU-00-01 siguen sin ratificación técnica completa. Una fila por línea, CRLF puro; no se reescribe ninguna fila existente ni la tabla *Resumen*; una fila nueva en *Registro de cambios*.
  - **Evidencia**: 2026-10-24: fila de HU-07-02 → `En curso`, bloque Observaciones de HU-07-02 y fila nueva en Registro de cambios (una línea por fila, CRLF puro, tabla *Resumen* intacta). Línea base antes de tocar código: ruff format/check y mypy en 0, 2756 pasadas y 33 omitidas.

- [ ] T002 *(humana)* Acuerdo de A, B y C para añadir `litellm[mcp]==1.106.2` como dependencia opcional (antes de T009)
  - **Archivos**: `docs/PROGRESO.md` (solo para anotar el acuerdo)
  - **Dependencias**: T001
  - **Criterios relacionados**: FR-017, regla de la skill `verificar-fronteras-hexagonales` (cambiar `pyproject.toml`, `requirements-dev.txt` o la CI exige acuerdo del equipo)
  - **Tarea F5**: Transversal
  - **Estimación**: fuera del presupuesto de Claude
  - **Verificación**: Las tres personas aceptan por escrito (chat o PR) añadir el extra opcional `litellm`, fijado a `1.106.2`, a `pyproject.toml` y a `requirements-dev.txt`, sabiendo que la CI de Ubuntu y Windows instalará ~380 MB más y que las transitivas no están fijadas. Se anota la fecha y quién aceptó. **Bloquea solo a T009 y T010**; T003 a T008 no dependen de ella porque sus pruebas inyectan la función de llamada y no necesitan `litellm`. Claude no marca esta tarea.

---

## Phase 2: Foundational — Configuración aditiva (bloquea el uso real del adaptador)

**Propósito**: Los proveedores nuevos y el tope de tokens de salida, sin cambiar ningún caso de prueba existente.

- [x] T003 [US2] Ampliar `PROVIDER_KEY_VARIABLES` y añadir `limits.max_output_tokens`, con plantillas y pruebas nuevas (FR-009, FR-013, FR-014, FR-014a)
  - **Archivos**: `tests/unit/test_config_providers.py`, `tests/unit/test_config_max_output_tokens.py`, `src/harness_agent/config.py`, `.env.example`, `config.example.toml`
  - **Dependencias**: T001
  - **Criterios relacionados**: AC-01, FR-009, FR-013, FR-014, FR-014a, SC-002, `contracts/config_additions_contract.md`
  - **Tarea F5**: Transversal (ampliación aditiva de HU-00-04)
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero. *Proveedores*: la tabla contiene exactamente `anthropic`, `fake`, `openai` (sin cambios) y `gemini`→`GEMINI_API_KEY`, `groq`→`GROQ_API_KEY`, `openrouter`→`OPENROUTER_API_KEY`, `ollama`→`None`; para cada proveedor con clave: variable ausente/vacía/solo espacios → `MissingKeyError`, presente → `api_key` es un `Secret` (su `repr` no muestra el centinela) y `key_variable` correcto; `ollama` carga sin ninguna variable y deja `api_key` y `key_variable` en `None`; `otro/x` falla con la lista de admitidos que incluye los nuevos. *Tope*: sin la línea vale 4096; `[limits] max_output_tokens = 8000` se carga; `0`, `-1`, `"10"`, `1.5` y `true` fallan con `InvalidConfigError` en el campo `limits.max_output_tokens`, mensaje `debe ser un entero mayor que 0.` y sin el valor recibido; `limits.max_tokens` conserva su valor por defecto y no se mezcla con el nuevo; un campo desconocido en `[limits]` sigue rechazado; `Limits()` por defecto sigue igual a `Limits(max_turns=30, max_seconds=600, max_tokens=200000)`. *Plantillas*: `config.example.toml` carga con `load_config` y da 4096, su TOML crudo sigue declarando tres campos en `limits` (la línea `# max_output_tokens = 4096` va **comentada** con su explicación), la línea de proveedores admitidos nombra los siete (`anthropic`, `fake`, `gemini`, `groq`, `ollama`, `openai`, `openrouter`); `.env.example` nombra exactamente las cinco variables con clave (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`), todas vacías. Rojo esperado: `KeyError`/`MissingKeyError` no lanzado para los proveedores nuevos, `AttributeError: max_output_tokens` y la prueba **existente** `tests/unit/test_config_templates.py` en rojo hasta actualizar `.env.example` (confirma el vínculo tabla↔plantilla; no se edita esa prueba). Se implementa el campo en `Limits`, `_LIMIT_FIELDS` y la tabla; los cuatro comandos de calidad en 0 con **todas las pruebas de configuración existentes sin cambios**.
  - **Evidencia**: 2026-10-24: rojo por la razón esperada (34 fallos: proveedor no admitido y falta el campo); verde tras implementar. Cuatro puertas en 0, 2805 pasadas y 33 omitidas, config.py al 100 %. Desviación: la prueba existente `test_an_unknown_provider_lists_the_admitted_ones` de tests/unit/test_config_schema.py ya no puede esperar la lista antigua de proveedores (anthropic, fake, openai); se actualizó solo el texto esperado de su aserción, sin cambiar el caso.

---

## Phase 3: User Stories 1 y 5 — El adaptador: petición y respuesta (P1/P2) [AC-01]

**Objetivo**: Un adaptador que construye peticiones acotadas desde el formato canónico y traduce las respuestas del modelo, incluidos los argumentos ilegibles.

**Prueba independiente**: Con una función de llamada falsa, el adaptador devuelve la `ProviderResponse` esperada y la petición capturada lleva `max_tokens`, `num_retries=0` y solo campos del formato canónico.

- [x] T004 [US5] Crear el paquete y el adaptador: construcción, carga perezosa de `litellm`, `repr` seguro y construcción de la petición (FR-001 a FR-005, FR-007, FR-009, FR-015, FR-016, FR-017, FR-019)
  - **Archivos**: `tests/unit/adapters/providers/__init__.py`, `tests/unit/adapters/providers/conftest.py`, `tests/unit/adapters/providers/test_request.py`, `tests/unit/adapters/providers/test_loading.py`, `src/harness_agent/adapters/providers/__init__.py` (solo docstring, sin exportaciones), `src/harness_agent/adapters/providers/litellm_provider.py`
  - **Dependencias**: T001 (no necesita T002 ni `litellm` instalado)
  - **Criterios relacionados**: AC-01, FR-001 a FR-005, FR-007, FR-009, FR-015 a FR-017, FR-019, US5 escenarios 1, 2 y 4, `contracts/litellm_provider_contract.md` §2 y §3, data-model (Petición)
  - **Tarea F5**: Sp1-43
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero. `conftest.py`: guardia de red autouse y `LITELLM_LOCAL_MODEL_COST_MAP=True`. *Construcción*: `model` sin la forma `<proveedor>/<modelo>` (`""`, `"a"`, `"a/"`, `"/b"`, no texto) → `ValueError` en español **sin** reproducir el valor (centinela ausente); `max_output_tokens` `0`, `-1`, `True`, `"4096"`, `1.5` → `ValueError`; `repr`/`str`/`format` muestran modelo y tope y `<oculta>` en lugar de la clave (centinela ausente, tampoco su longitud). *Carga perezosa*: con `completion` inyectada nunca se importa `litellm` (se comprueba con `sys.modules["litellm"] = None`); sin `completion` se usa `acompletion` de un módulo falso puesto en `sys.modules`; con `sys.modules["litellm"] = None` se lanza `ProviderDependencyError` cuyo texto contiene `pip install -e ".[litellm]"` y el aviso de ruta corta en Windows. *Petición* (método que construye los argumentos de la llamada, probado directamente porque `complete` llega en T005): claves exactas `model`, `messages`, `max_tokens`, `num_retries` (+`tools` y `api_key` solo si corresponden); `max_tokens == max_output_tokens` con y sin herramientas; `num_retries == 0`; `tools` ausente si `tools` es `None` o `[]` y igual a `to_openai_tools` si hay; `api_key` presente solo con clave y igual a `reveal()`; `messages` igual a `to_openai_messages` del historial preparado y sin campos extra de LiteLLM; un resultado de herramienta con `is_error` y contenido sin etiqueta se envía como `[tool_error] <contenido>`, con etiqueta (`[invalid_arguments] …`) queda igual, con `is_error` falso no se toca, y el historial original no cambia; ids opacos (`"x"`, `toolu_01A`, `call_A`, uno de 200 caracteres) viajan iguales en la llamada del asistente y en el mensaje de herramienta; un historial no representable (`SYSTEM` tras `USER`) → `ProviderError` en español sin el contenido. Rojo esperado: `ModuleNotFoundError: harness_agent.adapters.providers`. Implementar el módulo con `ProviderDependencyError`, la clase `LiteLLMProvider` (sin `complete` aún: la clase abstracta se completa en T005) y el cargador con `importlib`. **Si pasa de 40 min**, cortar en la costura «carga perezosa» (a T005).
  - **Evidencia**: 2026-10-24: rojo por la razón esperada (`ModuleNotFoundError: harness_agent.adapters.providers.litellm_provider`); verde con 58 pruebas nuevas. Cuatro puertas en 0 (2863 pasadas, 33 omitidas), `pytest tests/architecture` → 228. Cobertura de litellm_provider.py 99 % (queda la línea del marcador de `complete`, que sustituye T005). Desviación: `complete` existe como marcador `NotImplementedError` porque la clase abstracta no se podía construir sin él; el rojo de T005 será ese error. `litellm` no está instalado en el .venv.

- [x] T005 [US1] Implementar `complete`: traducción de la respuesta y argumentos ilegibles (FR-001, FR-005, FR-007, FR-008, FR-011, FR-019)
  - **Archivos**: `tests/unit/adapters/providers/test_response.py`, `src/harness_agent/adapters/providers/litellm_provider.py`
  - **Dependencias**: T004
  - **Criterios relacionados**: AC-01, FR-001, FR-005, FR-007, FR-008, FR-011, US1 escenarios 1 y 2, US5 escenarios 3 y 4, edge cases (argumentos no objeto, vacíos, respuesta sin texto ni llamadas, sin `usage`, id duplicado), SC-009, `contracts/litellm_provider_contract.md` §4, `research.md` §3
  - **Tarea F5**: Sp1-44
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero, con una función de llamada falsa que registra los argumentos y devuelve diccionarios (y un objeto con `model_dump()`). *Camino feliz*: solo texto; texto + dos llamadas en el orden de la lista aunque `index` venga como 1, 1, `None` o ausente; `content` `None` → `""`; ids opacos intactos; `usage` → `TokenUsage`, sin `usage` → `None`, contador `None` → 0; `complete` llama a la función exactamente una vez con la petición de T004 y no modifica `messages` ni `tools`. *Argumentos*: JSON objeto → `dict`; cadena en blanco → `{}`; JSON roto, lista, número, `"null"` y valor que no es cadena → `{"arguments_not_valid_json": <texto recortado a 200 caracteres>}` (un texto de 500 caracteres llega recortado); una llamada ilegible entre dos válidas → solo esa lleva el marcador; herramienta cuyo esquema declara `additionalProperties: True` y argumentos ilegibles → `ProviderError` que nombra la herramienta y no reproduce el texto recibido, y con argumentos válidos esa misma herramienta pasa sin problema. *Respuestas inválidas*: sin `choices`, `choices` vacío, sin texto y sin llamadas, estructura que los convertidores rechazan (`ConversionError`) → `ProviderError` con mensaje fijo en español (centinela ausente). Rojo esperado: `TypeError: Can't instantiate abstract class LiteLLMProvider` (falta `complete`). Implementar `complete` sin lógica por proveedor y delegar en `from_openai_response`. La clase ya es concreta, así que las pruebas de T004 siguen pasando.
  - **Evidencia**: 2026-10-24: rojo por la razón esperada (61 fallos con `NotImplementedError` del marcador de T004); verde con 62 pruebas nuevas en test_response.py. Cuatro puertas en 0 (2925 pasadas, 33 omitidas), `pytest tests/architecture` → 228, litellm_provider.py al 100 % de líneas y ramas. Desviación: el rojo fue `NotImplementedError` y no `TypeError` de clase abstracta (ver T004). Añadido: una llamada sin el campo `arguments` equivale a argumentos vacíos (como hacen los convertidores).

---

## Phase 4: User Stories 3 y 4 — Errores y clave (P1/P2)

**Objetivo**: Cada fallo de LiteLLM llega como un tipo canónico, y la clave no deja rastro en ningún texto que construya el adaptador.

**Prueba independiente**: Una excepción de LiteLLM cuyo mensaje repite la clave centinela produce un error canónico sin rastro de ella, con la causa original conservada.

- [x] T006 [US3] [US4] Tabla de errores por MRO y depuración de la clave (FR-010, FR-011, FR-012, FR-015)
  - **Archivos**: `tests/unit/adapters/providers/test_errors.py`, `tests/unit/adapters/providers/test_key_scrubbing.py`, `src/harness_agent/adapters/providers/litellm_provider.py`
  - **Dependencias**: T005
  - **Criterios relacionados**: US3 escenarios 1 a 4, US4 escenarios 1 a 3, FR-010, FR-011, FR-012, FR-015, SC-003, SC-004, `research.md` §1 y §6, `contracts/litellm_provider_contract.md` §6
  - **Tarea F5**: Sp1-43
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero, con clases de excepción falsas que reproducen la herencia real (`Timeout` ← `APITimeoutError` ← `APIConnectionError` ← `APIError`; `PaymentRequiredError` ← `BadRequestError`; etc.). *Tabla* (una prueba por fila, parametrizada): `Timeout` y `APITimeoutError` → `ProviderTimeout`; `RateLimitError` → `QuotaExceeded` con mensaje que contiene «límite de tasa»; `PaymentRequiredError` y `BudgetExceededError` → `QuotaExceeded` con mensaje de cuota o crédito (distinto del de tasa); `ServiceUnavailableError`, `BadGatewayError`, `InternalServerError` y `APIConnectionError` → `ProviderUnavailable`; `AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, `BadRequestError`, `ContextWindowExceededError`, `ContentPolicyViolationError` y una excepción desconocida → `ProviderError` genérico (tipo exacto `ProviderError`). *MRO*: `Timeout` gana a `APIConnectionError`; una subclase no listada de `RateLimitError` hereda `QuotaExceeded`; `PaymentRequiredError` no cae en el genérico por ser un `BadRequestError`; `ImportError` y `ModuleNotFoundError` durante la llamada → `ProviderError` con `pip install -e ".[litellm]"`. `__cause__` es la excepción original; `CancelledError` y `KeyboardInterrupt` lanzados por la función de llamada se propagan sin traducir; la función se invoca una sola vez (sin reintentos). *Depuración de la clave*: con `Secret` de centinela, una excepción cuyo mensaje es «Incorrect API key provided: <centinela>» y otra cuyo **nombre de clase** contiene el centinela producen un error canónico en el que el centinela no aparece en `str`, `repr`, `args` ni en ningún atributo de texto, y se reemplaza por `<secreto oculto>` donde habría ido; `str(error.__cause__)` **sí** conserva el original; el marcador de argumentos ilegibles de T005 con la clave dentro del texto recibido llega con `<secreto oculto>`; el `repr` del adaptador sigue sin la clave. Rojo esperado: `AssertionError` (sin traducción, la excepción de LiteLLM atraviesa `complete`) y centinela presente en el marcador. Implementar la tabla como constante inmutable por nombre de clase, el recorrido por el MRO, los mensajes fijos en español y la función que sustituye el valor de la clave por el marcador **antes** de construir el error canónico y el marcador. **Cobertura de `litellm_provider.py` al 100 % de líneas y ramas al cerrar esta tarea.**
  - **Evidencia**: 2026-10-24: rojo por la razón esperada (`ImportError: ERROR_TABLE` y 7 fallos de depuración de la clave: la excepción atravesaba `complete` y el centinela aparecía en el marcador); verde con 41 pruebas nuevas (test_errors.py y test_key_scrubbing.py). Cuatro puertas en 0 (2966 pasadas, 33 omitidas), `pytest tests/architecture` → 228. litellm_provider.py al 100 % de líneas y ramas (147 sentencias, 36 ramas). La tabla `ERROR_TABLE` es pública y de solo lectura; el mapeo es por nombre de clase a lo largo del MRO. Añadido: un `ProviderError` que lanza la función de llamada pasa sin traducir.

---

## Phase 5: Integración con el bucle real (P1) [AC-01]

**Objetivo**: Demostrar contra el `AgentLoop` real que el adaptador cumple el contrato del puerto y que los casos límite no rompen el turno.

**Prueba independiente**: El bucle real corre una tarea con herramientas sobre el adaptador (función de llamada falsa) con el mismo resultado que con `FakeProvider`.

- [x] T007 [US1] Prueba de contrato compartida con `FakeProvider` e integración con `AgentLoop` (FR-008, FR-020, SC-009)
  - **Archivos**: `tests/contracts/test_litellm_provider_contract.py`, `tests/integration/test_litellm_provider_agent_loop.py`
  - **Dependencias**: T006
  - **Criterios relacionados**: AC-01, FR-008, FR-020, US1 escenario 3, US3 escenario 1, US4 escenario 3, SC-001, SC-004, SC-009, `contracts/litellm_provider_contract.md` §1 y §5
  - **Tarea F5**: Sp1-44
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero (esta tarea es solo de pruebas sobre código ya hecho: el rojo esperado se obtiene escribiendo cada aserción contra una expectativa deliberadamente errónea y corrigiéndola, y se anota en el registro). *Contrato*: la misma consigna que `tests/contracts/test_fake_provider_contract.py` parametrizada con `DummyProvider`, `ScriptedProvider`, `FakeProvider` y `LiteLLMProvider` (función de llamada falsa): es `Provider`, `TestAgentConsumer.execute_turn` devuelve una `ProviderResponse` equivalente, no se modifican `messages` ni `tools`, y cambiar de proveedor no exige tocar el consumidor. *Integración* con `AgentLoop`, `InMemoryToolRegistry` real, `DefaultPermissionPolicy`, `RecordingEventBus` y las herramientas reales de archivos sobre un área temporal: (1) tarea con dos llamadas válidas en una respuesta y respuesta final → mismo historial y mismo estado que con `FakeProvider` con el guion equivalente; (2) argumentos JSON inválidos → la herramienta **no** se ejecuta, el siguiente envío al modelo trae un resultado que empieza por `[invalid_arguments]`, el turno **continúa** y termina con la respuesta final (la segunda petición capturada se construyó sin error); (3) herramienta de prueba permisiva (definida en el propio archivo, esquema con `additionalProperties: True`) con argumentos inválidos → `TurnStatus.PROVIDER_FAILED`, la herramienta no se ejecuta y se publica `PROVIDER_ERROR`; (4) herramienta que falla → la petición siguiente lleva su etiqueta `[…]` en el contenido; (5) cada tipo canónico de la tabla → `PROVIDER_FAILED` y evento `PROVIDER_ERROR` con el tipo esperado; (6) una excepción de LiteLLM cuyo mensaje repite la clave centinela: el centinela **no aparece** en el evento `PROVIDER_ERROR`, en el texto del resultado del turno ni en el historial que ve el modelo, y `__cause__` conserva el original. Todo sin red (guardia activo). Si pasa de 40 min, cortar entre contrato e integración.
  - **Evidencia**: 2026-10-24: contrato (tests/contracts/test_litellm_provider_contract.py, 11 pruebas) e integración con el AgentLoop real (tests/integration/test_litellm_provider_agent_loop.py, 19 pruebas: dos llamadas = mismo historial que FakeProvider; JSON ilegible → [invalid_arguments], herramienta sin ejecutar y el turno continúa; herramienta con campos libres → PROVIDER_FAILED; etiqueta [tool_error]; cada tipo canónico → evento PROVIDER_ERROR; clave centinela ausente en eventos, resultado, historial y peticiones al modelo). No se partió la tarea. Rojo: al ser pruebas sobre código ya hecho, todo salió en verde salvo una aserción mía (prefijo del mensaje de cuota); para demostrar que fallan se hicieron dos mutaciones temporales del adaptador (quitar `tools` de la petición y cambiar la etiqueta genérica) y cada una hizo fallar una prueba; el módulo se restauró (cmp idéntico). Cuatro puertas en 0 (2996 pasadas, 33 omitidas), `pytest tests/architecture` → 228, adaptador al 100 %.

---

## Phase 6: User Story 2 — Independencia del proveedor y fronteras (P1)

**Objetivo**: Que la regla «LiteLLM solo en el adaptador» y «ningún nombre de proveedor en el código» queden vigiladas por la CI.

**Prueba independiente**: La guarda pasa sobre el código real y falla ante cada mutación que viole una regla.

- [x] T008 [US2] Guarda de arquitectura propia para `adapters/providers/` (FR-002, FR-003, FR-004)
  - **Archivos**: `tests/architecture/test_providers_boundaries.py`
  - **Dependencias**: T006
  - **Criterios relacionados**: US2 escenario 4, FR-002, FR-003, FR-004, SC-002, regla de negocio 1, skill `verificar-fronteras-hexagonales`
  - **Tarea F5**: Transversal (verificación de fronteras)
  - **Estimación**: 30 min (15 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero, reutilizando `imported_modules`, `find_config_reads` y `terminal_uses` (no copiarlos). Reglas sobre el código real: (a) ningún archivo de `src/harness_agent/` tiene `import litellm`/`from litellm …` (ni `openai`, `anthropic`, `google`) como instrucción de importación, **tampoco** dentro de `adapters/providers/` a nivel de módulo; (b) `import_module("litellm")` aparece solo dentro de una función de `adapters/providers/` y en ninguna otra carpeta; (c) `adapters/providers/` importa solo biblioteca estándar, `harness_agent.core`, `harness_agent.adapters.converters` y su paquete; no importa `config`, `cli`, `observability`, `bootstrap` ni otro adaptador; no lee entorno ni archivos; no usa la terminal; (d) ningún literal de texto de `adapters/providers/` (docstrings excluidos) contiene como palabra el nombre de un proveedor de `PROVIDER_KEY_VARIABLES` (se leen de la tabla en la prueba; identificadores como `to_openai_messages` no cuentan); (e) `adapters/providers/__init__.py` contiene solo un docstring; (f) `tests/architecture/test_adapters_boundaries.py::test_no_adapter_imports_the_terminal_layer` sigue cubriendo el paquete. Autopruebas con fragmentos sintéticos (cada forma prohibida se detecta; cada forma permitida pasa) y mutaciones sobre una **copia** del paquete real: añadir `import litellm` arriba, un `import_module("litellm")` a nivel de módulo, un literal `"groq"` y `from harness_agent.config import load_config` → cada una falla; el original no cambia. Rojo esperado: `NameError`/`ImportError` de los detectores aún no escritos; luego verde sobre el código real. Resultado de `pytest tests/architecture` registrado en el cierre.
  - **Evidencia**: 2026-10-24: guarda propia tests/architecture/test_providers_boundaries.py (71 pruebas): ningún SDK importado en src/ (tampoco a nivel de módulo en providers), `import_module('litellm')` solo dentro de una función de adapters/providers/, imports permitidos (stdlib, API pública del núcleo, API pública de converters y el propio paquete), sin entorno/archivos/terminal, sin nombres de proveedor en literales (docstrings aparte; se leen de PROVIDER_KEY_VARIABLES) y `__init__.py` solo con docstring; autopruebas de cada detector y 15 mutaciones sobre copias del paquete. Rojo: los detectores se probaron con mutaciones (cada línea prohibida añadida a una copia hace fallar la regla); el código real pasa. Cuatro puertas en 0 (3067 pasadas, 33 omitidas), `pytest tests/architecture` → 299 (antes 228), litellm_provider.py y config.py al 100 %.

---

## Phase 7: Dependencia opcional y LiteLLM real con transporte sustituido (P1/P2)

**Objetivo**: Añadir `litellm[mcp]==1.106.2` como extra opcional (con el acuerdo ya obtenido) y comprobar contra la versión fijada.

- [x] T009 Añadir el extra opcional `litellm` a `pyproject.toml` y a `requirements-dev.txt`, con prueba de coincidencia de versión (FR-017, FR-018)
  - **Archivos**: `tests/unit/test_dependency_pins.py`, `pyproject.toml`, `requirements-dev.txt`
  - **Dependencias**: **T002 (acuerdo humano obligatorio)** y T008
  - **Criterios relacionados**: FR-017, FR-018, SC-007, `research.md` §4 y §5
  - **Tarea F5**: Sp1-43
  - **Estimación**: 30 min (15 min impl + 10 min check + 5 min registro)
  - **Verificación**: **No empezar sin T002 marcada por la persona responsable.** Pruebas primero (`tomllib`, sin red): `[project].dependencies` sigue siendo `[]`; existe `[project.optional-dependencies].litellm` con exactamente un requisito `litellm[mcp]==<versión>`; esa versión es exacta (`==`, sin rangos); `requirements-dev.txt` contiene **una sola** línea de `litellm` con el mismo requisito y la misma versión; el nombre del extra coincide con el comando de instalación que imprime `ProviderDependencyError` (`.[litellm]`). Rojo esperado: `KeyError: 'litellm'` y prueba de requirements sin línea. Implementar las dos líneas (con el comentario de por qué el pin va en ambos sitios) sin tocar `.github/workflows/ci.yml`. Luego, en el venv corto `C:\tmp\h17`: `pip install -r requirements-dev.txt`, `pip install -e . --no-deps`, `pip check` («No broken requirements found»), y los cuatro comandos de calidad **con `litellm` instalado**; anotar versiones resueltas. Comprobar que la suite también pasa **sin** `litellm` (otro venv sin el paquete, con las pruebas `importorskip` omitidas). La CI de Ubuntu queda para T015.
  - **Evidencia**: 2026-10-24: **se hizo sin T002 marcada, por instrucción expresa de la persona responsable** (acuerdo de A, B y C y visto bueno del PO pendientes; el PR no debe fusionarse sin esa aprobación). Rojo por la razón esperada (4 fallos: `KeyError`/extra `litellm` inexistente y sin línea en requirements). Verde con tests/unit/test_dependency_pins.py (11 pruebas). `pyproject.toml`: extra `litellm = ["litellm[mcp]==1.106.2"]`, `dependencies` sigue vacío; `requirements-dev.txt`: `litellm[mcp]==1.106.2` más 21 dependencias fijadas (las directas de litellm y del extra mcp tal como las resolvió pip: aiohttp, boto3, click, fastuuid, filelock, httpx, httpx2, huggingface-hub, importlib-metadata, jinja2, jsonschema, mcp, openai, packaging, pydantic, pydantic-settings, python-dotenv, pyyaml, tiktoken, tokenizers, typing-extensions); las transitivas más profundas siguen sin fijar. `ci.yml` sin cambios. Entorno limpio en C:\tmp\h17 reconstruido desde requirements-dev.txt: `pip check` → «No broken requirements found»; con litellm instalado, las cuatro puertas en 0 (3089 pasadas, 32 omitidas; ahora corren las 11 del spike SPK-01), `pytest tests/architecture` → 299; sin litellm (.venv) 3078 pasadas y 33 omitidas. **Hallazgo que habría roto la CI**: LiteLLM 1.106.2 pide el codificador cl100k_base de tiktoken en cada llamada y su archivo NO viene en el paquete (solo p50k y o200k); la primera vez lo descarga de la red, y el spike SPK-01 (que antes se omitía) fallaba con el guardia de red. Solución sin tocar el spike: tests/litellm_offline.py (sustituye el codificador en memoria) y tests/spikes/conftest.py (fixture autouse); los 11 tests del spike pasan sin red. Ubuntu sin verificar (no hay WSL).

- [x] T010 [US3] Pruebas con LiteLLM real y transporte sustituido: deriva de nombres y petición/respuesta reales (FR-010, FR-017, FR-019)
  - **Archivos**: `tests/integration/test_litellm_real_transport.py`
  - **Dependencias**: T009
  - **Criterios relacionados**: FR-009, FR-010, FR-019, US3 escenario 1, SC-003, SC-005, `research.md` §1 y §2, SPK-01 §2 (diferencias 1, 4, 5, 8, 9, 10 y 11)
  - **Tarea F5**: Sp1-43
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: `LITELLM_LOCAL_MODEL_COST_MAP=True` se fija antes de `pytest.importorskip("litellm")`; guardia de red activo. Pruebas primero: *Deriva* — cada nombre de la tabla de errores existe en `litellm.exceptions` de la versión fijada; `Timeout` es subclase de `APIConnectionError`; `PaymentRequiredError` es subclase de `BadRequestError`; `BudgetExceededError` existe; la versión instalada es la del pin (falla con mensaje claro si difiere). *Petición real* — con `litellm.acompletion` real y el transporte HTTP asíncrono sustituido (parchear `post` de `AsyncHTTPHandler`, o, si no funciona, inyectar `client=` con `httpx.MockTransport` mediante `functools.partial` en `completion`, como hizo el spike), un modelo `anthropic/<modelo>` envía `max_tokens == 4096` (no 64 000), la herramienta traducida, ningún `provider_specific_fields`, y una respuesta nativa con dos `tool_use` llega como dos `ToolCall` con ids `toolu_…` en orden; un modelo `openai/<modelo>` no envía campos extra. *Errores reales* — una respuesta HTTP 429 → `QuotaExceeded` («límite de tasa»); 402 → `QuotaExceeded`; 503 y 502 → `ProviderUnavailable`; 401 → `ProviderError` genérico; un `httpx.ConnectError` (como un servidor `ollama/<modelo>` apagado) → `ProviderUnavailable`; ninguna de ellas con la clave centinela en `str`/`repr`. Rojo esperado: `ImportError` de un símbolo de la tabla de errores aún no exportado para la prueba, o la aserción de `max_tokens` frente a un valor deliberadamente erróneo; sin `litellm` instalado el módulo entero se omite.
  - **Evidencia**: 2026-10-24: tests/integration/test_litellm_real_transport.py (28 pruebas, se omite sin litellm) con la biblioteca real 1.106.2 y el transporte sustituido en `httpx.AsyncClient.send` (no en `AsyncHTTPHandler.post`: así LiteLLM aplica su propio mapeo real de errores) más guardia de red. Cubre: versión instalada = pin; cada nombre de la tabla existe en litellm.exceptions; herencia por nombre del MRO (Timeout ← APITimeoutError ← APIConnectionError; PaymentRequiredError ← BadRequestError); petición Anthropic con `max_tokens` 4096 (no 64 000), herramienta nativa, sin `provider_specific_fields`; dos llamadas `toolu_…` en orden con su uso; el siguiente envío lleva los resultados y `[tool_error] no se pudo`; los prefijos openai/ y openrouter/ solo cambian el destino; ollama sin clave va a localhost:11434 (por defecto de LiteLLM) y sin servidor da ProviderUnavailable; estados 429/402/503/502/500/401/400/404 → tipo canónico real; ReadTimeout → ProviderTimeout; el mensaje del proveedor con la clave no deja rastro. Mutaciones temporales (`max_tokens` fijo y quitar BadGatewayError de la tabla) hicieron fallar 4 y 1 pruebas; módulo restaurado (cmp idéntico). Cuatro puertas en 0 con litellm (3117 pasadas, 32 omitidas, 1 aviso de LiteLLM «LoggingWorker… Event loop is closed» al cerrar el bucle de eventos: ruido de su hilo de registro, no falla) y sin litellm en el .venv (3070 pasadas, 42 omitidas). Hallazgo: tiktoken/cl100k_base se descarga en la primera llamada real (ver T009).

---

## Phase 8: Guía y documentación

**Propósito**: Dejar documentado cómo probar con un modelo real y que las skills y CLAUDE.md describan el código real.

- [x] T011 [P] Archivo de la prueba manual Sp1-45 (omitido sin clave) y guía `quickstart.md` completa (FR-021, requisito 6)
  - **Archivos**: `tests/unit/test_litellm_quickstart_docs.py`, `tests/integration/test_litellm_real_model_manual.py`, `specs/017-litellm-provider-adapter/quickstart.md`
  - **Dependencias**: T010
  - **Criterios relacionados**: AC-01, FR-021, SC-006, `quickstart.md`
  - **Tarea F5**: Sp1-45 (preparación; la ejecución es T014)
  - **Estimación**: 30 min (15 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero. *Guía*: una prueba lee `quickstart.md` y exige que mencione `LITELLM_LOCAL_MODEL_COST_MAP`, la ruta corta de Windows con el límite de ~130 caracteres de `site-packages` y cómo medirlo, los seis proveedores de ejemplo (`anthropic`, `openai`, `gemini`, `groq`, `openrouter`, `ollama`) con su variable de entorno (o «sin clave» para `ollama`) tomada de `PROVIDER_KEY_VARIABLES`, `limits.max_output_tokens`, `HARNESS_REAL_MODEL` y que la prueba real es manual y fuera de la CI. Rojo esperado: la guía aún no cita los seis proveedores ni la forma de medir la ruta. *Prueba manual*: `test_litellm_real_model_manual.py` se omite (`pytest.mark.skipif`) salvo que existan `HARNESS_REAL_MODEL=<proveedor>/<modelo>` **y** la variable de clave de ese proveedor según `PROVIDER_KEY_VARIABLES` (o ninguna si el proveedor no la usa); con ellas, ejecuta la tarea de tres pasos del plan (listar archivos de un área temporal sembrada, leer uno, responder con su contenido) con el bucle real, herramientas reales de archivos y `LiteLLMProvider`, aserta que hubo al menos una llamada a herramienta ejecutada y una respuesta final, imprime tokens consumidos (nunca la clave) y no escribe fuera del área temporal. El archivo importa sin `litellm` instalado. Actualizar `quickstart.md` (proveedores con modelo como `<modelo>` y recordatorio de consultar la documentación del proveedor para el modelo y su nivel gratuito; sin inventar nombres de modelo). Comprobar que sin variables la prueba aparece como `skipped` y no cuenta como fallo en la CI.
  - **Evidencia**: 2026-10-24: rojo por la razón esperada (8 fallos: la guía no citaba los seis proveedores con su variable, la forma de medir la ruta ni el tokenizador); verde con tests/unit/test_litellm_quickstart_docs.py (12 pruebas, la lista de proveedores sale de PROVIDER_KEY_VARIABLES) tras reescribir quickstart.md (COST_MAP, ruta corta de site-packages bajo ~130 caracteres y cómo medirla con sysconfig, tabla con anthropic/openai/gemini/groq/openrouter/ollama y su variable o «sin clave», `limits.max_output_tokens`, prueba real fuera de la CI, descarga de cl100k_base y CUSTOM_TIKTOKEN_CACHE_DIR). tests/integration/test_litellm_real_model_manual.py (Sp1-45): se omite sin HARNESS_REAL_MODEL y sin la variable de clave del proveedor (comprobado: `1 skipped`), importa sin litellm, limita a 8 llamadas y no imprime la clave; su lógica se verificó con un ensayo en seco con transporte guionizado (3 llamadas, 2 herramientas, estado completed). Cuatro puertas en 0 con litellm (3129 pasadas, 33 omitidas) y sin litellm (3082 pasadas, 43 omitidas); `pytest tests/architecture` → 299.

- [x] T012 [P] Actualizar `CLAUDE.md` y las skills (ambas copias) con el adaptador y su guarda (documentación del código real)
  - **Archivos**: `CLAUDE.md`, `.claude/skills/verificar-fronteras-hexagonales/SKILL.md`, `.agents/skills/verificar-fronteras-hexagonales/SKILL.md`, `.claude/skills/estructura-carpetas-harness/references/arbol.md`, `.agents/skills/estructura-carpetas-harness/references/arbol.md`, `.claude/skills/arquitectura-hexagonal-clean/references/capas-y-reglas.md`, `.agents/skills/arquitectura-hexagonal-clean/references/capas-y-reglas.md`
  - **Dependencias**: T010
  - **Criterios relacionados**: CLAUDE.md («si encuentras una diferencia entre una skill y el código, manda el código»), Principio VIII
  - **Tarea F5**: Transversal
  - **Estimación**: 25 min (15 min impl + 5 min check + 5 min registro)
  - **Verificación**: `CLAUDE.md`: fila nueva en «Qué existe hoy» para `adapters/providers/litellm_provider.py` y las ampliaciones de `config.py`; quitar «adaptador LiteLLM» de «Aún no hay»; convenciones nuevas (el tope por llamada es `limits.max_output_tokens`, `litellm` solo con `importlib` en `adapters/providers/`, `LITELLM_LOCAL_MODEL_COST_MAP`, entorno corto en Windows); número de la siguiente spec. Skills: la guarda `test_providers_boundaries.py` en la tabla de guardas y `providers/` como existente (ya no «planeada») en `arbol.md` y `capas-y-reglas.md`; **cada archivo cambia igual en `.claude/` y `.agents/`** (`diff` de cada par sin diferencias). Sin pruebas nuevas; verificación: los cuatro comandos de calidad siguen en 0.
  - **Evidencia**: 2026-10-24: CLAUDE.md (fila nueva de adapters/providers/litellm_provider.py, fila de tests/spikes, dos convenciones nuevas —tope por llamada y LiteLLM—, «Aún no hay» sin el adaptador y la siguiente spec es la 018) y, en las dos copias (.claude/ y .agents/), la guarda test_providers_boundaries.py en verificar-fronteras-hexagonales/SKILL.md (con la explicación de por qué no entra en GUARDED), providers/ ya existente y tests/litellm_offline.py + spikes/conftest.py en arbol.md, y capas-y-reglas.md corregida (converters, providers, storage, tools y system existen; mcp planeado). `cmp` de cada par de skills → idénticos; sin LF sueltos. Cuatro puertas en 0 tras corregir un hallazgo propio: la primera pasada falló en `tests/architecture/test_no_secrets_in_repo.py` porque `CLAUDE.md` contenía `api_key=config.api_key` (el detector lo lee como asignación de clave); se reescribió la frase sin esa forma. Resultado final en el .venv sin litellm: 3090 pasadas, 35 omitidas, `pytest tests/architecture` → 299.

---

## Phase 9: Cierre y tareas humanas

- [x] T013 Cierre: verificación completa, fronteras, archivos protegidos y registro en `docs/PROGRESO.md` (transversal)
  - **Archivos**: `docs/PROGRESO.md`, `specs/017-litellm-provider-adapter/tasks.md`, `specs/017-litellm-provider-adapter/spec.md`, `specs/017-litellm-provider-adapter/checklists/requirements.md`
  - **Dependencias**: T003 a T012
  - **Criterios relacionados**: Principios VIII y IX, SC-001 a SC-009
  - **Tarea F5**: Transversal
  - **Estimación**: 40 min (20 min impl + 15 min check + 5 min registro)
  - **Verificación**: En el venv corto con `litellm` instalado: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing` en 0; `pytest tests/architecture` en 0 y `litellm_provider.py` al 100 % de líneas y ramas (SC-007); `git diff --exit-code $(git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/loop.py tests/doubles docs/archivo` sin salida (SC-008); la suite también pasa sin `litellm`. **Normalizar a CRLF cualquier LF suelto** de `spec.md` y `checklists/requirements.md` (el aviso era la línea 33 de la spec; comprobar con un recuento de líneas sin `\r` en todos los archivos de `specs/017-litellm-provider-adapter/`, que debe dar 0). `docs/PROGRESO.md` (una fila por línea, CRLF puro, sin reescribir filas existentes ni tocar la tabla *Resumen*): fila de HU-07-02 → **`En revisión`** (nunca `Hecha`) con columnas *Archivos* y *Evidencia* (comandos y resultados reales); una fila de *Registro de cambios* por tarea T003 a T012; bloque **Observaciones de HU-07-02** con los hallazgos del plan: (1) ampliación aditiva del esquema de HU-00-04 con `limits.max_output_tokens` y 4 proveedores nuevos (aviso a B y al PO, visto bueno del PO sobre la lista); (2) `RateLimitError` → `QuotaExceeded` **provisional**, más `PaymentRequiredError`, `BadGatewayError` y `APITimeoutError` añadidos a la tabla; HU-07-04 decide el tipo propio con A y B; (3) para A: una herramienta con `additionalProperties: true` no admite el marcador de argumentos ilegibles y el adaptador falla cerrado; (4) la causa original queda encadenada y el adaptador depura la clave de todo texto que construye; (5) dependencia opcional, acuerdo previo (T002), transitivas sin fijar y ruta corta en Windows (~130 caracteres); (6) `LITELLM_LOCAL_MODEL_COST_MAP=True` lo fija el usuario o `bootstrap.py` antes del primer import; (7) qué cablear en `bootstrap.py`; (8) pendientes humanos (T014, T015) y que HU-00-01, HU-07-01 y HU-00-04 siguen sin ratificación técnica completa. Marcar en este `tasks.md` solo las tareas realmente hechas, con su evidencia; dejar T002, T014 y T015 sin marcar. Rama `gustavo`; sin commit ni push (los hace la persona).
  - **Evidencia**: 2026-10-24: con `litellm` en C:\tmp\h17 (ruta corta; reconstruido desde requirements-dev.txt, `pip check` limpio): `ruff format --check .`, `ruff check .` y `mypy src tests` en 0 (189 archivos), `pytest --cov` → 3129 pasadas y 33 omitidas (1 aviso de LiteLLM al cerrar el bucle), `pytest tests/architecture` → 299; sin `litellm` (.venv): mismas puertas en 0, 3090 pasadas y 35 omitidas. Cobertura: litellm_provider.py 147 sentencias y 36 ramas al 100 %, providers/__init__.py 100 %, config.py 267 sentencias y 70 ramas al 100 %. `git diff --exit-code` de core/interfaces, core/events.py, core/loop.py, tests/doubles y docs/archivo contra el merge-base de origin/main: sin diferencias. LF sueltos en specs/017-*, PROGRESO.md y CLAUDE.md: 0. PROGRESO.md: fila de HU-07-02 en `En revisión` (no `Hecha`), 10 filas de registro (T003–T012) + la de T013, 8 observaciones nuevas; solo se reemplazó la celda de la fila de HU-07-02 y mi propia observación de T001; tabla *Resumen* intacta. T002, T014 y T015 sin marcar.

- [ ] T014 *(humana)* Prueba manual Sp1-45: tarea de tres pasos con el proveedor que elija el usuario
  - **Archivos**: `docs/PROGRESO.md` (solo para anotar el resultado)
  - **Dependencias**: T011 y T013 (puede ejecutarse en cuanto T011 esté lista)
  - **Criterios relacionados**: AC-01, SC-006, FR-021, decisión D-IA (proveedor y presupuesto)
  - **Tarea F5**: Sp1-45
  - **Estimación**: 60 min (presupuesto del plan de sprint)
  - **Verificación**: La persona elige proveedor y modelo (idealmente con nivel gratuito o local), define su clave **solo** como variable de entorno y ejecuta la orden de `quickstart.md` §5. Esperado: el modelo responde, pide herramientas, recibe sus resultados y llega a una respuesta final. Se anota en `docs/PROGRESO.md` el proveedor, el modelo, los tokens consumidos y si `limits.max_output_tokens = 4096` fue aceptado; si el modelo lo rechaza, se anota como hallazgo. Fuera de la CI y sin clave se omite. Claude no marca esta tarea.

- [ ] T015 *(humana)* Revisión cruzada (A o B) y confirmación de la CI remota en Ubuntu y Windows
  - **Evidencia disponible (2026-10-25)**: CI en verde en Linux y Windows en `main` c12c4cb (workflow CI, run n.º 47, `quality (ubuntu-latest, py3.12)` y `quality (windows-latest, py3.12)`), https://github.com/Theboul/harness-agent/actions/runs/40149368199; solo cubre la parte de CI. La revisión cruzada sigue pendiente de una persona (no se marca).
  - **Archivos**: `docs/PROGRESO.md` (columna Commit/PR)
  - **Dependencias**: T013
  - **Criterios relacionados**: Principio IX, regla «todo cambio lo revisa alguien de otra área», FR-018, SC-007
  - **Tarea F5**: Transversal
  - **Estimación**: fuera del presupuesto de Claude
  - **Verificación**: Una persona de A o B revisa el diff con la lista de comprobación de `capas-y-reglas.md` y la guarda nueva; confirma que la CI de GitHub Actions pasa en `ubuntu-latest` y `windows-latest` con `litellm` instalado desde `requirements-dev.txt` (las pruebas con `importorskip` corren y no se omiten) y se rellena la columna Commit/PR. La historia **no** pasa a `Hecha` hasta esta tarea, la ratificación técnica de HU-00-01 y la aprobación de D-02. Claude no marca esta tarea.

---

## Dependencias y orden de ejecución

```text
T001 ──► T002 (humana) ─────────────────────────────┐
  │                                                  ▼
  ├──► T003 (config) ───────────────────────────────►(uso real; no bloquea T004–T008)
  └──► T004 ──► T005 ──► T006 ──► T007
                          │
                          └──► T008 ──► T009 ──► T010 ──► T011 [P]
                                          ▲               └──► T012 [P]
                                      (exige T002)
T003..T012 ──► T013 (cierre) ──► T015 (humana)
T011 ──► T014 (humana, Sp1-45)
```

- **T003 a T008 no necesitan `litellm` ni el acuerdo**: se pueden hacer mientras se espera T002.
- **T009 y T010 exigen T002.** Sin acuerdo, no se toca `pyproject.toml` ni `requirements-dev.txt`.
- **Paralelizables**: T011 y T012 (archivos distintos, dependen ambas de T010).
- T004 → T005 → T006 son secuenciales (el mismo módulo); T007 y T008 dependen de T006.

## Estimación frente al presupuesto

| Tarea | Min |
|---|---|
| T003 | 40 |
| T004 | 40 |
| T005 | 40 |
| T006 | 40 |
| T007 | 40 |
| T008 | 30 |
| T009 | 30 |
| T010 | 35 |
| T011 | 30 |
| T012 | 25 |
| **Trabajo de código y pruebas (T003–T012)** | **350** |
| Inicio y cierre (T001, T013) | 60 |

Presupuesto de Sp1-43 + Sp1-44 en `docs/03-plan-sprints.md`: 210 + 150 = 360 min; con Sp1-45 (60 min, humana), 420 min. Las microtareas imputadas a Sp1-43 (T004, T006, T009, T010) suman 145 min y las de Sp1-44 (T005, T007) 80 min, por debajo del presupuesto; el resto (T003, T008, T011, T012 y el inicio/cierre) es trabajo transversal que el plan de sprint no presupuesta (configuración aditiva, guarda, guía, documentación y registro). El total de Claude, 410 min, supera en unos 50 min los 360 min de Sp1-43 y Sp1-44 por ese trabajo transversal; se avisa a B en `PROGRESO.md` (T001) y no se recorta alcance.

## Cobertura de los requisitos pedidos

| # | Requisito | Tarea con prueba |
|---|---|---|
| 1 | Depuración de la clave (excepción cuyo mensaje repite la clave: sin rastro en `str`, `repr`, evento `PROVIDER_ERROR` ni texto al modelo; `__cause__` conserva el original) | T006 (unitaria), T007 (evento, resultado del turno e historial) |
| 2 | Tabla por MRO con `PaymentRequiredError`, `BadGatewayError`, `APITimeoutError`, `ImportError` y prueba de deriva | T006 (tabla), T010 (deriva y errores reales) |
| 3 | Argumentos ilegibles: marcador contra el `AgentLoop` real y `ProviderError` con esquema permisivo | T005 (unitaria), T007 (bucle real) |
| 4 | Coincidencia de versión entre `pyproject.toml` y `requirements-dev.txt` | T009 |
| 5 | Guarda propia de `adapters/providers/` (`litellm` solo ahí, import perezoso) | T008 |
| 6 | `quickstart.md` documenta `LITELLM_LOCAL_MODEL_COST_MAP`, ruta corta (~130 caracteres) y los seis proveedores | T011 |

## Archivos protegidos (verificar antes de cerrar)

`src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `cli/`, `tests/doubles/`, `docs/archivo/`, `.github/workflows/ci.yml` y todas las pruebas existentes.
