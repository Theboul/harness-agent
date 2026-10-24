# Contrato: ampliaciones aditivas de `config.py` (HU-07-02)

Dos ampliaciones del esquema de HU-00-04. Ninguna cambia un caso de prueba existente.

## 1. `PROVIDER_KEY_VARIABLES` (FR-013)

Tabla proveedor → variable de entorno de su clave (`None`: el proveedor no necesita clave).

| Proveedor | Variable | Estado |
|---|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` | existente, sin cambios |
| `openai` | `OPENAI_API_KEY` | existente, sin cambios |
| `fake` | `None` | existente, sin cambios |
| `gemini` | `GEMINI_API_KEY` | **nuevo** (documentación de LiteLLM, 2026-10-24) |
| `groq` | `GROQ_API_KEY` | **nuevo** (documentación de LiteLLM, 2026-10-24) |
| `openrouter` | `OPENROUTER_API_KEY` | **nuevo** (documentación de LiteLLM, 2026-10-24) |
| `ollama` | `None` | **nuevo** (servidor local; ver `research.md` §2) |

Reglas que no cambian: el proveedor de `config.model` (`<proveedor>/<modelo>`) debe estar en la tabla; si no, `InvalidConfigError` con la lista de admitidos; una variable ausente, vacía o de solo espacios lanza `MissingKeyError`; los proveedores sin clave dejan `api_key` y `key_variable` en `None`.

Plantillas: `.env.example` lista las variables de los proveedores con clave (todas vacías, comentario «Clave del proveedor X»); `config.example.toml` actualiza la línea de «Proveedores admitidos». `tests/unit/test_config_templates.py` exige que `.env.example` nombre **exactamente** las variables de la tabla: el archivo debe seguir esa regla. La instrucción «comentadas, sin valores» se cumple con el patrón actual (`NOMBRE=` vacío, sin valor).

## 2. `Limits.max_output_tokens` (FR-009, FR-014a)

```toml
[limits]
# Máximo de tokens que el modelo puede generar en UNA llamada (entero mayor que 0).
# max_output_tokens = 4096
```

| Aspecto | Valor |
|---|---|
| Tipo | entero mayor que 0; un booleano no vale |
| Valor por defecto | `4096` |
| Dónde | `Limits.max_output_tokens`, `_LIMIT_FIELDS` y `_check_limits` de `config.py` |
| Error | mismo texto que los otros límites (`debe ser un entero mayor que 0.`), campo `limits.max_output_tokens`, sin el valor recibido |
| Plantilla | **comentado** en `config.example.toml`: el TOML crudo sigue declarando tres campos de `limits`, como exige `test_config_templates.py` |
| `max_tokens` | sin cambios: presupuesto de la ejecución (HU-01-06); **no** se usa como tope de una llamada |

Compatibilidad: `Limits(max_turns=30, max_seconds=600, max_tokens=200000)` sigue siendo igual a los valores por defecto porque el campo nuevo tiene su propio valor por defecto en ambos lados de la comparación.

Pruebas nuevas (archivos nuevos, sin tocar los existentes): `tests/unit/test_config_max_output_tokens.py` y `tests/unit/test_config_providers.py`.
