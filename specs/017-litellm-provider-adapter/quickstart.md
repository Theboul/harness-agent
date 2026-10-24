# Guía de validación: HU-07-02 — Adaptador LiteLLM

Guía para comprobar la historia de punta a punta. Detalle de contratos en `contracts/`; reglas en `spec.md`.

## 1. Entorno en Windows (ruta corta)

LiteLLM trae archivos con rutas muy largas (la más larga dentro del paquete mide 126 caracteres). Con el límite clásico de 260 caracteres de Windows, la ruta de `site-packages` debe medir **menos de unos 130 caracteres**; si no, la instalación queda **incompleta sin avisar** (faltan archivos como `litellm/llms/custom_httpx`). Una ruta de OneDrive larga suele pasarse: cree el entorno fuera, en una ruta corta.

```powershell
python -m venv C:\tmp\h17
C:\tmp\h17\Scripts\python.exe -m pip install -r requirements-dev.txt
C:\tmp\h17\Scripts\python.exe -m pip install -e . --no-deps
C:\tmp\h17\Scripts\python.exe -m pip check          # No broken requirements found
# Medir la ruta de site-packages (debe dar menos de ~130):
C:\tmp\h17\Scripts\python.exe -c "import sysconfig; print(len(sysconfig.get_paths()['purelib']))"
```

`requirements-dev.txt` ya incluye `litellm[mcp]==1.106.2` y las dependencias que pip resolvió para él, todas fijadas. Fuera de la CI, el extra del proyecto se instala con `pip install -e ".[litellm]"`. En Ubuntu no hay límite de ruta; el resto es igual.

## 2. Variables de entorno de LiteLLM

**`LITELLM_LOCAL_MODEL_COST_MAP`**: sin ella, LiteLLM intenta descargar su tabla de precios al importarse. Fíjela en `True` **antes** del primer import (las pruebas ya lo hacen; el adaptador no toca el entorno):

```powershell
$env:LITELLM_LOCAL_MODEL_COST_MAP = "True"          # PowerShell
```
```bash
export LITELLM_LOCAL_MODEL_COST_MAP=True            # bash
```

**Tokenizador (`cl100k_base`)**: en la versión fijada, LiteLLM pide ese codificador de `tiktoken` en cada llamada y su archivo **no viene en el paquete**. La primera llamada real lo descarga de la red (unos 1,6 MB) a una carpeta de LiteLLM; sin red falla. Para trabajar sin conexión, deje el archivo en una carpeta propia y apúntela con `CUSTOM_TIKTOKEN_CACHE_DIR`. Las pruebas automáticas no lo necesitan: `tests/litellm_offline.py` sustituye el codificador en memoria.

## 3. Proveedores de ejemplo

El proveedor y el modelo salen solo de `model = "<proveedor>/<modelo>"` en `config.toml`; el adaptador es el mismo para todos. La variable de la clave se define **solo en el entorno** (nunca en archivos del repositorio). Consulte la documentación de cada proveedor para elegir el modelo y conocer los límites de su nivel gratuito; esta guía no fija nombres de modelo.

| Proveedor | `model` | Variable de entorno | Nota |
|---|---|---|---|
| anthropic | `anthropic/<modelo>` | `ANTHROPIC_API_KEY` | |
| openai | `openai/<modelo>` | `OPENAI_API_KEY` | |
| gemini | `gemini/<modelo>` | `GEMINI_API_KEY` | |
| groq | `groq/<modelo>` | `GROQ_API_KEY` | |
| openrouter | `openrouter/<modelo>` | `OPENROUTER_API_KEY` | el modelo lleva su propio prefijo, p. ej. `openrouter/<casa>/<modelo>` |
| ollama | `ollama/<modelo>` | sin clave | servidor local en `http://localhost:11434` (el valor por defecto de LiteLLM); debe estar en marcha |

Un proveedor que no está en la tabla de `config.py` (`PROVIDER_KEY_VARIABLES`) falla al cargar la configuración con la lista de los admitidos.

**Tope de salida por llamada**: `limits.max_output_tokens` (entero mayor que 0, 4096 por defecto, comentado en `config.example.toml`). Es independiente de `limits.max_tokens` (presupuesto de toda la ejecución). Si el modelo elegido rechaza 4096, bájelo.

## 4. Pruebas sin red ni claves (siempre)

```powershell
$env:LITELLM_LOCAL_MODEL_COST_MAP = "True"
C:\tmp\h17\Scripts\python.exe -m pytest tests/unit/adapters/providers tests/contracts/test_litellm_provider_contract.py tests/integration/test_litellm_provider_agent_loop.py tests/integration/test_litellm_real_transport.py tests/architecture/test_providers_boundaries.py tests/unit/test_dependency_pins.py --no-cov
```

Esperado: todo en verde, sin ningún intento de conexión (el guardia de red falla la prueba si lo hubiera). `test_litellm_real_transport.py` usa la biblioteca real con el transporte HTTP sustituido y se omite si `litellm` no está instalado; el resto no necesita `litellm`.

## 5. Las cuatro puertas y las fronteras

```powershell
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
pytest tests/architecture
git diff --exit-code $(git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/loop.py tests/doubles docs/archivo
```

Esperado: exit 0 en todas; módulos nuevos al 100 % de líneas y ramas; el `git diff` sin cambios en archivos protegidos.

## 6. Configuración nueva

1. `config.toml` con `model = "groq/<modelo>"` y la variable `GROQ_API_KEY` definida: `load_config()` devuelve la configuración con `api_key` oculta. Sin la variable: `MissingKeyError`.
2. `model = "ollama/<modelo>"`: no se pide ninguna clave.
3. `model = "otro/x"`: error de configuración que lista los proveedores admitidos.
4. `[limits] max_output_tokens = 0` → error de validación sin el valor; sin la línea, vale 4096.

## 7. Prueba real (Sp1-45, humana, fuera de la CI)

Es manual y queda **fuera de la CI**: se omite sola si falta `HARNESS_REAL_MODEL` o la variable de clave del proveedor (`tests/integration/test_litellm_real_model_manual.py`). Solo con presupuesto de API decidido (D-IA) o con un proveedor de nivel gratuito o local.

```powershell
$env:LITELLM_LOCAL_MODEL_COST_MAP = "True"
$env:HARNESS_REAL_MODEL = "<proveedor>/<modelo>"
$env:<VARIABLE_DE_CLAVE_DEL_PROVEEDOR> = "<su clave>"      # nunca en archivos del repositorio
# opcional: $env:HARNESS_REAL_MAX_OUTPUT_TOKENS = "4096"
C:\tmp\h17\Scripts\python.exe -m pytest tests/integration/test_litellm_real_model_manual.py -s --no-cov
```

La prueba siembra una carpeta temporal con tres archivos y le pide al modelo listar los archivos, leer uno y responder con su contenido (tarea de tres pasos), con el bucle real y las herramientas reales. Limita a 8 llamadas al modelo para no gastar de más. Esperado: el modelo responde, pide al menos una herramienta, recibe su resultado y llega a una respuesta final; se imprimen los tokens consumidos y nunca la clave. Anote en `docs/PROGRESO.md` el proveedor, el modelo, los tokens y si `limits.max_output_tokens` (4096 por defecto) fue aceptado: es la evidencia humana de AC-01 (Sp1-45).

## 8. Qué conectará la raíz de composición (`bootstrap.py`, fuera de alcance)

```text
if provider == "fake": FakeProvider(...)            # fuera del adaptador
else: LiteLLMProvider(config.model,
                      max_output_tokens=config.limits.max_output_tokens,
                      api_key=config.api_key)
```

Antes del primer import de `litellm` conviene fijar `LITELLM_LOCAL_MODEL_COST_MAP=True`. Hasta que exista `bootstrap.py`, la conexión se hace a mano en las pruebas de integración.
