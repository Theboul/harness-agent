# Implementation Plan: HU-07-02 — Adaptador LiteLLM para el primer proveedor

**Branch**: `017-litellm-provider-adapter` (carpeta de la spec; el trabajo sigue en la rama `gustavo`) | **Date**: 2026-10-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/017-litellm-provider-adapter/spec.md`

## Summary

Un único adaptador, `adapters/providers/litellm_provider.py`, implementa el puerto `Provider` para cualquier modelo `<proveedor>/<modelo>` de LiteLLM, sin ramas ni nombres de proveedor en el código. Construye cada petición desde el formato canónico con los convertidores de HU-07-01 (formato común de LiteLLM), fija siempre el tope de tokens de salida desde el campo nuevo `limits.max_output_tokens` (4096), marca los errores de herramienta en el contenido, trata los ids como opacos, convierte los argumentos ilegibles en una llamada que el bucle real rechaza con `[invalid_arguments]` (sin tocar el puerto ni `core/loop.py`) y traduce los fallos de LiteLLM a la jerarquía `ProviderError` con una tabla por MRO. `litellm[mcp]==1.106.2` es un extra opcional con import perezoso. La única tabla con nombres de proveedor es `PROVIDER_KEY_VARIABLES`, que gana `gemini`, `groq`, `openrouter` y `ollama`. Decisiones y verificaciones contra la versión fijada: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12 (`>=3.12,<3.13`), tipado estricto (`mypy --strict`)

**Primary Dependencies**: biblioteca estándar y `harness_agent.core` + `harness_agent.adapters.converters`; **opcional**: `litellm[mcp]==1.106.2` (extra `litellm` de `pyproject.toml`, fijada también en `requirements-dev.txt`), cargada con `importlib` solo dentro de `adapters/providers/`

**Storage**: N/A

**Testing**: `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`); función de llamada inyectable + guardia de red; `importorskip("litellm")` solo en las pruebas con LiteLLM real y transporte sustituido; cobertura del módulo nuevo 100 % de líneas y ramas

**Target Platform**: Windows y Linux (CI en `ubuntu-latest` y `windows-latest`, Python 3.12)

**Project Type**: biblioteca/CLI con arquitectura hexagonal (un adaptador nuevo)

**Performance Goals**: N/A (la latencia es del proveedor externo, V-07); `import litellm` ≈ 3,8 s, pagado una vez al construir el adaptador

**Constraints**: sin red ni claves en las pruebas automáticas; no cambiar `core/interfaces/`, `core/events.py`, `core/loop.py` ni `tests/doubles/`; clave solo por entorno dentro de `Secret`; el adaptador no lee entorno ni archivos; ruta de `site-packages` de Windows de menos de ~130 caracteres para instalar LiteLLM

**Scale/Scope**: 1 módulo nuevo (~250 líneas), 2 ampliaciones aditivas de `config.py`, 3 plantillas/archivos de dependencias, ~9 archivos de prueba nuevos. 2 PHU; presupuesto del plan de sprints: Sp1-43 (3,5 h), Sp1-44 (2,5 h), Sp1-45 (1 h)

## Constitution Check

*GATE: pasa antes de la Fase 0 y se revisó de nuevo tras el diseño. Sin violaciones; las decisiones de interpretación se listan en «Complexity Tracking».*

| Principio / regla | Cumplimiento |
|---|---|
| I — una historia por spec | HU-07-02 sola; `specs/017-…` |
| II — microtareas de 15–40 min | ver «Descomposición prevista» (9 tareas, ninguna > 40 min) |
| III — Python 3.12, modular, tipado | un módulo, funciones pequeñas, `mypy --strict`, `importlib` evita depender de tipos de `litellm` |
| IV — pruebas, calidad y CI en dos SO | cuatro puertas + `pytest tests/architecture`; `ci.yml` no cambia; `litellm` entra por `requirements-dev.txt` |
| V — criterios inmutables | AC-01 copiado tal cual en la spec |
| VI — disciplina de sprints | HU-07-02 es del Sprint 1 (activo); nada de sprints futuros: sin `bootstrap.py`, streaming, `tool_choice`, reintentos, conmutación |
| VII — consulta quirúrgica | solo la ficha, SPK-01 y los archivos nombrados |
| VIII — `PROGRESO.md` | tarea de cierre: fila a `En revisión`, archivos, evidencia, observaciones y hallazgos (una fila por línea, CRLF, sin tocar *Resumen*) |
| IX — DoD y verificación humana | tareas humanas finales sin marcar: acuerdo de dependencia, Sp1-45, revisión cruzada, CI remota |
| X — `docs/archivo/` | no se toca |
| V-02 / falla cerrada | todo lo no previsto es `ProviderError`; argumentos ilegibles nunca ejecutan una herramienta; herramienta con campos libres → `ProviderError` |
| V-13 / secretos | clave solo en `Secret`; nunca en repr, mensajes ni eventos; prueba con centinela |
| V-14 / `FakeProvider` | contrato compartido con `FakeProvider` |
| D-01 (asyncio) | `acompletion` cancelable; `CancelledError`/`KeyboardInterrupt` se propagan |
| Skill `arquitectura-hexagonal-clean` | recorrido de *Decision Gates* y lista de comprobación abajo |
| Skill `estructura-carpetas-harness` | ruta de cada archivo con su fila abajo |
| Skill `verificar-fronteras-hexagonales` | guarda nueva `test_providers_boundaries.py` y tarea de verificación |

### Decision Gates (`arquitectura-hexagonal-clean`)

| Pregunta | Resultado |
|---|---|
| ¿Es regla o comportamiento nuevo del núcleo? | No. Es traducción de formatos y errores: adaptador. Las reglas de validación de argumentos, permisos y límites siguen en el bucle |
| ¿Necesita algo de fuera? | Sí, el modelo por red: puerto existente `Provider` (`core/interfaces/provider.py`), sin cambios |
| ¿Quién lo implementa? | `adapters/providers/litellm_provider.py` (única pieza que conoce LiteLLM) |
| ¿Cómo se conecta? | Por constructor; la conexión real es de `bootstrap.py` (no existe): el plan anota qué cablear (quickstart §6) y las pruebas de integración lo hacen a mano |
| ¿Cómo se prueba? | Contrato compartido con `FakeProvider` (`tests/contracts/`), integración con el `AgentLoop` real, unitarias con función de llamada falsa y una prueba con LiteLLM real y transporte sustituido |
| ¿Es asíncrono? | `complete` sí (D-01) |

### Lista de comprobación (`capas-y-reglas.md`)

| # | Pregunta | Respuesta |
|---|---|---|
| 1 | ¿La regla de negocio está en `core/` y no en un adaptador? | **Sí.** El adaptador no decide permisos, límites ni validación de argumentos |
| 2 | ¿Todo lo externo pasa por un puerto con tipos del dominio? | **Sí.** `Provider`; la función de llamada recibe y devuelve datos simples |
| 3 | ¿Puertos, entidades y eventos siguen sin cambios? | **Sí.** Se comprueba con el `git diff --exit-code` de CLAUDE.md |
| 4 | ¿Errores externos traducidos sin reproducir valores? | **Sí**, con una nota: la causa original queda en `__cause__` (FR-011); `str`/`repr`/`args` y los eventos solo llevan texto propio |
| 5 | ¿Dependencias inyectadas y conectadas solo en `bootstrap.py`? | **Sí (parcial):** `model`, tope, clave y función de llamada por constructor; `bootstrap.py` aún no existe, el plan anota el cableado |
| 6 | ¿El núcleo se probó con dobles, sin red, disco ni claves? | **Sí.** El bucle real corre con el adaptador y una función de llamada falsa |
| 7 | ¿El adaptador real tiene prueba de contrato en `tests/contracts/`? | **Sí:** `test_litellm_provider_contract.py` |
| 8 | ¿Pasa `pytest tests/architecture` y la guarda nueva en Windows y Linux? | **Por verificar** en la implementación (tarea de fronteras) y en la CI remota |
| 9 | ¿El núcleo emite eventos en lugar de imprimir? | **No aplica:** el adaptador no emite eventos ni imprime; el bucle publica `PROVIDER_ERROR` |
| 10 | ¿Lo público está exportado en `core/__init__.py`? | **No aplica:** no se añade nada a `core/`; el adaptador importa de `harness_agent.core` |
| 11 | ¿Se respetan las decisiones de diseño? | **Sí:** falla cerrada y secretos ocultos; compactación no aplica |
| 12 | ¿Otro integrante revisó el cambio? | **No todavía:** tarea humana final (revisión cruzada) |

## Project Structure

### Documentation (this feature)

```text
specs/017-litellm-provider-adapter/
├── spec.md
├── plan.md                                      # este archivo
├── research.md                                  # verificaciones contra litellm 1.106.2
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
├── contracts/
│   ├── litellm_provider_contract.md
│   └── config_additions_contract.md
└── tasks.md                                     # /speckit-tasks (no lo crea este comando)
```

### Source Code (rutas y fila de `estructura-carpetas-harness` que las justifica)

| Archivo | Cambio | Fila de la tabla |
|---|---|---|
| `src/harness_agent/adapters/providers/__init__.py` | nuevo; solo docstring, sin exportaciones | «Código con `litellm`… → `adapters/<subpaquete>/`» (receta *Nuevo proveedor de modelo*) |
| `src/harness_agent/adapters/providers/litellm_provider.py` | nuevo: `LiteLLMProvider`, `ProviderDependencyError`, tabla de errores | misma fila; conversiones con `adapters/converters/` |
| `src/harness_agent/config.py` | `PROVIDER_KEY_VARIABLES` (+4) y `Limits.max_output_tokens` | «Lectura de configuración → `config.py`» |
| `.env.example`, `config.example.toml` | proveedores nuevos; `max_output_tokens` comentado | secretos solo en plantillas sin valores |
| `pyproject.toml` | extra opcional `litellm = ["litellm[mcp]==1.106.2"]`; `dependencies` sigue vacío | cambio de dependencias (acuerdo previo A, B y C) |
| `requirements-dev.txt` | `litellm[mcp]==1.106.2` | idem; es lo que instala la CI |
| `tests/unit/adapters/providers/` (`__init__.py`, `conftest.py`, `test_request.py`, `test_response.py`, `test_errors.py`, `test_loading.py`) | nuevo | «`tests/unit/<ruta del módulo>`» |
| `tests/contracts/test_litellm_provider_contract.py` | nuevo | «contrato que se corre contra el doble y la implementación real» |
| `tests/integration/test_litellm_provider_agent_loop.py` | nuevo: `AgentLoop` real + adaptador + herramientas reales | «`tests/integration/`» |
| `tests/integration/test_litellm_real_transport.py` | nuevo: LiteLLM real con transporte sustituido (`importorskip`) | «`tests/integration/`» |
| `tests/integration/test_litellm_real_model_manual.py` | nuevo: Sp1-45, se omite sin `HARNESS_REAL_MODEL` y clave | «`tests/integration/`» |
| `tests/architecture/test_providers_boundaries.py` | nuevo: guarda de `adapters/providers/` y del import de `litellm` | «`tests/architecture/`» |
| `tests/unit/test_config_providers.py`, `tests/unit/test_config_max_output_tokens.py` | nuevos (los existentes no cambian) | «`tests/unit/`» |
| `tests/unit/test_dependency_pins.py` | nuevo: versión del extra = versión de `requirements-dev.txt`; `dependencies` vacío | «`tests/unit/`» |
| `CLAUDE.md` (fila nueva en «Qué existe hoy»), `.claude/skills/` y `.agents/skills/` (guardas y `arbol.md`: `providers/` ya existe) | documentación al cerrar | las skills describen el código real; se actualizan las dos copias |

Sin archivos nuevos en `core/`; sin cambios en `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/` ni `.github/workflows/ci.yml`.

**Por qué una guarda propia y no `GUARDED`** (`test_adapters_boundaries.py`): `GUARDED` solo permite biblioteca estándar, la API pública del núcleo y el propio paquete. `providers/` necesita además `adapters.converters` (permitido por la skill) y la carga perezosa de `litellm`. Reutiliza `imported_modules`, `find_config_reads` y `terminal_uses`; `test_no_adapter_imports_the_terminal_layer` ya recorre todos los adaptadores, incluido el nuevo.

**Structure Decision**: un solo módulo en `adapters/providers/`. La única pieza que sabe de nombres de proveedor es la tabla de `config.py`. `core/` no cambia.

## Diseño (resumen; detalle en `data-model.md` y `contracts/`)

1. **Construcción**: `LiteLLMProvider(model, *, max_output_tokens, api_key=None, completion=None)`. Valida `model` y el tope (`ValueError` en español, sin el valor). Si `completion` es `None`, carga `litellm.acompletion` con `importlib`; un `ImportError` se convierte en `ProviderDependencyError` con `pip install -e ".[litellm]"` y el aviso de ruta corta.
2. **`complete`**: prepara el historial (marca de `is_error`), convierte con `to_openai_messages` y `to_openai_tools`, llama a la función con `model`, `messages`, `tools` (si hay), `max_tokens`, `num_retries=0` y `api_key` (si hay), y traduce la respuesta.
3. **Traducción de la respuesta**: se lee el objeto de LiteLLM como diccionario, se reparan los argumentos ilegibles con el campo marcador y se delega en `from_openai_response`. Los dobles de prueba devuelven diccionarios directamente.
4. **Errores**: `except Exception` → `_translate(exc)` por MRO; `ConversionError` → `ProviderError`; `CancelledError` y `KeyboardInterrupt` pasan. Mensajes fijos en español con el nombre de la clase, nunca con el texto original.
5. **Argumentos ilegibles**: mecanismo y alternativas descartadas en `research.md` §3; prueba contra el bucle real.

## Hallazgos y notas para `PROGRESO.md` al cerrar (tarea de cierre)

1. Ampliación **aditiva** del esquema de HU-00-04 con `limits.max_output_tokens` (aviso a B y al PO) y 4 proveedores nuevos en `PROVIDER_KEY_VARIABLES` (visto bueno del PO sobre la lista).
2. `RateLimitError` → `QuotaExceeded` es **provisional**; HU-07-04 decide el tipo propio con A y B. También se añadieron `PaymentRequiredError` → `QuotaExceeded` y `BadGatewayError` → `ProviderUnavailable`.
3. Para A: una herramienta con `additionalProperties: true` no puede recibir la marca de argumentos ilegibles; el adaptador falla cerrado. Si aparece una, el bucle debería ofrecer una marca de primera clase.
4. La causa original queda encadenada (`__cause__`); un traceback impreso podría mostrarla.
5. Dependencia opcional `litellm[mcp]==1.106.2` y el acuerdo previo de A, B y C; dependencias transitivas sin fijar (`openai`, `pydantic`, `mcp`…); fricción de la ruta larga en Windows (≈130 caracteres).
6. `LITELLM_LOCAL_MODEL_COST_MAP=True` debe fijarlo el usuario o `bootstrap.py` antes del primer import; el adaptador no toca el entorno.
7. Sp1-45 (resultado humano) y que `max_output_tokens = 4096` fue aceptado por el modelo elegido.
8. Cuando exista `bootstrap.py`: cablear `LiteLLMProvider(config.model, max_output_tokens=config.limits.max_output_tokens, api_key=config.api_key)` (y `FakeProvider` para `fake/...`).

## Descomposición prevista (la fija `/speckit-tasks`; regla RITMO: 8–10 tareas de ≤ 40 min, pruebas e implementación agrupadas por módulo)

1. Inicio (humana): acuerdo de A, B y C para añadir la dependencia; línea base de las cuatro puertas.
2. `config.py`: proveedores nuevos, `max_output_tokens`, plantillas y pruebas nuevas (Sp1-43).
3. Dependencia opcional: `pyproject.toml`, `requirements-dev.txt`, prueba de coincidencia de versiones, venv corto con LiteLLM (Sp1-43).
4. Adaptador, lado petición y carga perezosa + pruebas (Sp1-43).
5. Adaptador, lado respuesta y argumentos ilegibles + pruebas (Sp1-44).
6. Adaptador, tabla de errores y secretos + pruebas (Sp1-44).
7. Contrato con `FakeProvider` + integración con el bucle real (Sp1-44).
8. Guarda de fronteras + prueba con LiteLLM real y transporte sustituido (verificación de fronteras).
9. Prueba manual Sp1-45 (archivo omitido sin clave) + documentación de cierre (CLAUDE.md, skills, `PROGRESO.md`) + puertas finales.
10. Fin (humanas, sin marcar): ejecución real de Sp1-45, revisión cruzada, CI remota en Ubuntu y Windows.

**Archivos protegidos** (verificar antes de cerrar): `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `cli/`, `tests/doubles/`, `docs/archivo/`.

## Complexity Tracking

No hay violaciones de la constitución ni de las skills. Decisiones de interpretación que conviene que el revisor vea:

| Decisión | Por qué | Alternativa descartada |
|---|---|---|
| Causa original encadenada (`from exc`) aunque el mensaje original puede contener fragmentos de la petición | FR-011 pide encadenarla para depurar; el texto que ve el bucle, los eventos y la CLI es solo el propio y, además, depurado de la clave (`<secreto oculto>`) antes de construirlo | `from None`: pierde la causa y contradice FR-011 |
| Carga con `importlib.import_module("litellm")` en vez de `import litellm` | mypy no depende de tener LiteLLM; las pruebas unitarias no lo necesitan; el import es perezoso por construcción | `import` dentro de una función con `# type: ignore` |
| Campo marcador `arguments_not_valid_json` en lugar de un cambio en el bucle o el puerto | el bucle ya rechaza campos no declarados con `[invalid_arguments]`; no se toca ningún archivo protegido | cambiar `core/loop.py` o `ToolCall` (prohibido sin acuerdo de A, B y C) |
| Guarda propia en vez de ampliar `GUARDED` | `providers/` necesita `converters` y la carga perezosa de `litellm` | relajar `GUARDED` para todos los adaptadores |
| `litellm` en `requirements-dev.txt` además del extra | la CI instala solo `requirements-dev.txt`; una prueba obliga a que ambas versiones coincidan | cambiar `ci.yml` para instalar el extra |
