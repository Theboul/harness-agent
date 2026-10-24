# Investigación: HU-07-02 — Adaptador LiteLLM

**Fecha**: 2026-10-24 · **Entorno**: Windows 11, Python 3.12, venv en ruta corta `C:\tmp\h17`, `litellm[mcp]==1.106.2` instalado de cero junto con `requirements-dev.txt`. Alcance mínimo: solo lo que el usuario pidió confirmar (puntos 1 a 5).

## 1. Excepciones reales de LiteLLM 1.106.2 y tabla de FR-010

Comprobado con `inspect` sobre `litellm.exceptions` (cadena de herencia real):

| Excepción | Hereda de | Nota |
|---|---|---|
| `Timeout` | `APITimeoutError` → `APIConnectionError` → `APIError` | **Es subclase de `APIConnectionError`**: hay que decidirla antes |
| `APIConnectionError` | `APIError` | red caída, servidor local apagado |
| `RateLimitError` | `APIStatusError` → `APIError` | 429 |
| `PaymentRequiredError` | `BadRequestError` | 402, crédito agotado; **sin regla propia caería en el genérico** |
| `BudgetExceededError` | `Exception` (no es `APIError`) | presupuesto del proxy de LiteLLM |
| `ServiceUnavailableError` | `APIStatusError` | 503 |
| `BadGatewayError` | `APIStatusError` | 502 (no estaba en la tabla de la spec) |
| `InternalServerError` | `APIStatusError` | 500 |
| `AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, `UnprocessableEntityError` | `APIStatusError` | 401, 403, 404, 422 |
| `BadRequestError` | `APIStatusError` | 400; subclases: `ContextWindowExceededError`, `ContentPolicyViolationError`, `UnsupportedParamsError`, `LiteLLMUnknownProvider`, `ImageFetchError`, `PaymentRequiredError` |

**Decisión.** La correspondencia se resuelve recorriendo el MRO de la excepción, de la clase más derivada a la más general, y usando la primera cuyo **nombre** esté en la tabla. Así `Timeout` gana a `APIConnectionError` sin lógica de orden manual, las subclases nuevas heredan el mapeo del padre y no hace falta importar `litellm` para traducir (las pruebas unitarias usan clases falsas con el mismo nombre).

| Nombre en el MRO | Tipo canónico | Mensaje (español, sin datos de la petición) |
|---|---|---|
| `Timeout`, `APITimeoutError` | `ProviderTimeout` | «El proveedor no respondió a tiempo (`<tipo>`).» |
| `RateLimitError` | `QuotaExceeded` (**provisional**, HU-07-04) | «El proveedor rechazó la llamada por límite de tasa (`<tipo>`); espere antes de reintentar.» |
| `PaymentRequiredError`, `BudgetExceededError` | `QuotaExceeded` | «La cuota o el crédito del proveedor está agotado (`<tipo>`).» |
| `ServiceUnavailableError`, `BadGatewayError`, `InternalServerError`, `APIConnectionError` | `ProviderUnavailable` | «El proveedor no está disponible (`<tipo>`).» |
| `ImportError` (instalación incompleta de LiteLLM, hallazgo de SPK-01) | `ProviderError` | mensaje de instalación con el comando y el aviso de ruta corta (research §4) |
| cualquier otra | `ProviderError` | «El proveedor devolvió un error (`<tipo>`).» |

Cambios respecto a la tabla propuesta en la spec (FR-010 decía «los nombres se confirman en el plan»): se **añaden** `PaymentRequiredError` → `QuotaExceeded` (de lo contrario un 402 llegaría como genérico por ser un `BadRequestError`), `BadGatewayError` → `ProviderUnavailable`, `APITimeoutError` → `ProviderTimeout` y `ImportError`. El resto coincide. `<tipo>` es `type(exc).__name__`; el mensaje original del proveedor nunca se copia.

Una prueba de deriva (`importorskip("litellm")`) comprueba que cada nombre de la tabla existe en `litellm.exceptions` y que la cadena de herencia asumida sigue siendo cierta con la versión fijada.

## 2. Ollama: servidor por defecto

En el código de 1.106.2 el valor por defecto está escrito: `api_base or get_secret("OLLAMA_API_BASE") or "http://localhost:11434"` (`litellm/main.py`, `litellm_core_utils/get_llm_provider_logic.py`, `llms/ollama/common_utils.py`). La documentación solo mostraba ejemplos con `api_base`, pero el código confirma el valor.

**Decisión.** El adaptador **no pasa `api_base`**: usa el servidor local por defecto de LiteLLM. Sin servidor en marcha, la llamada falla con `APIConnectionError` → `ProviderUnavailable` con mensaje claro (no hay silencio ni valor inventado). Un punto de enlace distinto queda fuera de alcance; LiteLLM mismo lee `OLLAMA_API_BASE` si el usuario la define, y el adaptador no toca el entorno. Los modelos locales sin soporte de herramientas pueden responder sin pedirlas; no es un fallo del adaptador.

## 3. Mecanismo para argumentos inválidos (FR-008, SC-009)

Restricciones: no cambiar `Provider` ni `core/loop.py`; `ToolCall.arguments` es un `dict`; el historial vuelve al modelo en el turno siguiente por los convertidores (que exigen `dict` serializable); `from_openai_response` lanza `ConversionError` ante JSON inválido y rompería el turno.

Hechos del código existente: el bucle valida cada llamada con `registry.validate_args` y, si falla, devuelve `[invalid_arguments] …` al modelo sin ejecutar nada. El validador rechaza todo campo no declarado **salvo** que el esquema diga `additionalProperties: true` (`schema_validator._validate_object`); las cuatro herramientas actuales declaran `False`.

Alternativas descartadas:

- *Dejar propagar `ConversionError`*: rompe el turno (viola FR-008).
- *Argumentos `{}`*: una herramienta sin campos obligatorios se ejecutaría con argumentos inventados (falla abierta).
- *Argumentos como cadena (no `dict`)*: el bucle los rechazaría, pero el siguiente `to_openai_messages` lanzaría `ConversionError` y rompería el turno siguiente.
- *Renombrar la llamada*: daría `[unknown_tool]`, la etiqueta equivocada.
- *Cambiar el bucle o el puerto*: prohibido.

**Decisión.** Antes de `from_openai_response`, el adaptador revisa cada `function.arguments` de la respuesta. Si la cadena no es JSON o no es un objeto, la sustituye por el objeto `{"arguments_not_valid_json": "<texto recortado a 200 caracteres>"}`. El campo no está declarado en ningún esquema, así que el validador del bucle lo rechaza («campo no declarado en el esquema», con el nombre del campo, que ya le dice al modelo qué pasó), el modelo recibe `[invalid_arguments]` y puede corregirse, y el historial sigue siendo serializable. Una cadena en blanco sigue siendo `{}` (comportamiento de los convertidores).

**Caso límite que falla cerrado.** Si el esquema de la herramienta (la lista `tools` que recibe `complete`) declara `additionalProperties: true`, el campo marcador no sería rechazado y la herramienta correría con argumentos que el modelo no emitió. En ese caso el adaptador no lo intenta: lanza `ProviderError` con un mensaje claro y se descarta la respuesta (el turno termina como fallo del proveedor, ninguna herramienta corre). Se anota como hallazgo para A: si algún día se declara una herramienta con campos libres, el bucle debería ofrecer una marca de «argumentos ilegibles» de primera clase.

La prueba exigida por el revisor corre contra el bucle real (`AgentLoop` + registro real + herramientas reales de archivos) y comprueba: la herramienta no se ejecutó, el modelo recibió un resultado con `[invalid_arguments]`, el turno siguiente se construyó sin error y terminó con la respuesta final.

## 4. Instalación en Windows con ruta corta y fricción de la ruta larga

- Instalación completa de `litellm[mcp]==1.106.2` en `C:\tmp\h17` (ruta de `site-packages` de 28 caracteres): sin archivos omitidos, `import litellm` y `acompletion` funcionan. Versiones resueltas: `openai 2.54.0`, `pydantic 2.14.1`, `httpx 0.28.1`, `mcp 2.3.0` (las transitivas **no** están fijadas; solo `litellm`).
- La ruta relativa más larga dentro del paquete mide 126 caracteres (un `.pyc` de `litellm\llms\vertex_ai\…\transformation.cpython-312.pyc`). Con el límite clásico de 260 caracteres, la ruta de `site-packages` debería quedar **por debajo de unos 130 caracteres**. Es el mismo origen del fallo silencioso de SPK-01 (omite archivos sin avisar) y del límite que ya afecta a `test_list_files`.
- Los entornos de CI no se acercan al límite (`hostedtoolcache` en Windows mide unos 60 caracteres; Linux no tiene este límite). El riesgo es de los equipos de desarrollo con rutas de OneDrive largas: se documenta en `quickstart.md` y en el mensaje de error del adaptador («si está en Windows, cree el entorno en una ruta corta, por ejemplo `C:\tmp\venv`»).
- `LongPathsEnabled` en el registro no se verificó; no se asume.
- Con `LITELLM_LOCAL_MODEL_COST_MAP=True` el import no intenta descargar la tabla de precios. Las pruebas la fijan; en producción la fija el usuario o la futura raíz de composición **antes** del primer import (el adaptador no toca el entorno).
- `litellm` publica `py.typed`, pero el adaptador lo importa con `importlib.import_module("litellm")`, así que mypy no lo analiza y `mypy src tests` no depende de que esté instalado.

## 5. Extra opcional en la CI de Ubuntu y Windows

- La CI instala `pip install -r requirements-dev.txt` y `pip install -e . --no-deps`. El extra no se instala vía `pyproject.toml` en CI; por eso `litellm[mcp]==1.106.2` va **también** en `requirements-dev.txt`. Una prueba (`tests/unit/test_dependency_pins.py`) exige que ambas versiones coincidan y que `dependencies` siga vacío.
- `.github/workflows/ci.yml` **no cambia**: ya corre en `ubuntu-latest` y `windows-latest`, Python 3.12, con `cache: pip`.
- Resolución comprobada en Windows: `pip install -r requirements-dev.txt` encima de `litellm[mcp]==1.106.2` terminó con `pip check` → «No broken requirements found» (pytest 8.3.4, pytest-asyncio 0.25.3, mypy 1.14.1 y ruff 0.9.6 intactos).
- **No verificado**: la CI de Ubuntu (no hay ejecución local) ni una corrida completa de las cuatro puertas con `litellm` instalado. Quedan como tareas: ejecutarlas en el venv corto durante la implementación y la CI remota como tarea humana.
- Las pruebas que importan `litellm` usan `pytest.importorskip` y fijan `LITELLM_LOCAL_MODEL_COST_MAP` **antes** del import (como el spike); las unitarias del adaptador inyectan una función de llamada falsa y no necesitan `litellm`. La suite sigue pasando sin `litellm` (esas pruebas se omiten, y la cobertura de los módulos nuevos no depende de ellas).
- Coste esperado: instalación de unos 380 MB (SPK-01) en cada trabajo de CI, mitigada por la caché de `pip`.

## 6. Decisiones menores (sin investigación adicional)

- **Llamada asíncrona**: `litellm.acompletion`, cancelable con `asyncio` (D-01). `CancelledError` y `KeyboardInterrupt` no son `Exception` y atraviesan el `except Exception` del adaptador sin traducirse.
- **Sin reintentos propios ni ocultos**: se envía `num_retries=0` (en 1.106.2 ese valor fija también `max_retries` del cliente interno). La política de reintentos es de HU-07-04.
- **Herramientas vacías**: si `tools` es `None` o vacío, no se envía el campo `tools`.
- **Respuesta vacía**: sin texto y sin llamadas (o sin `choices`) → `ProviderError`.
- **Lectura de la respuesta**: el objeto de LiteLLM se pasa a diccionario (`model_dump()` si lo tiene, o el propio `dict` en los dobles) solo para leerlo con `from_openai_response`; nunca se reenvía.
- **Causa encadenada**: se usa `raise … from exc` (FR-011). `str()`, `repr()` y `args` del error canónico no contienen texto del proveedor; el bucle y los eventos solo ven nuestro mensaje. El objeto original queda en `__cause__` solo para depurar: un traceback impreso podría mostrar el mensaje original (LiteLLM suele enmascarar las claves). La CLI imprime únicamente el tipo. Además, todo texto que el adaptador construye se depura: el valor de la clave se reemplaza por `<secreto oculto>` antes de armar el error o el marcador. Es el compromiso entre FR-011 (encadenar) y FR-015 (no filtrar); se anota en `PROGRESO.md`.
- **Modelo falso**: `fake/...` está en `PROVIDER_KEY_VARIABLES` pero el adaptador no lo trata de forma especial; LiteLLM lo rechazaría como proveedor desconocido (`ProviderError`). La raíz de composición elegirá `FakeProvider` para `fake/...`.
