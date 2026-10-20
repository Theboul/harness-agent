# Modelo de datos: HU-00-04 — Configuración por archivo y variables de entorno

**Plan**: [plan.md](plan.md) | **Contrato**: [contracts/config_loading_contract.md](contracts/config_loading_contract.md) | **Investigación**: [research.md](research.md)

Todos los tipos viven en `src/harness_agent/config.py` (fuera de `core/`). No se modifica ningún puerto de `core/interfaces/`.

---

## Entidades

### `HarnessConfig` (dataclass congelada, con `slots`)

Configuración completa que `load_config` entrega al resto del sistema.

| Campo | Tipo | Origen | Valor por defecto | Notas |
|---|---|---|---|---|
| `model` | `str` | archivo, clave `model` | ninguno (obligatorio) | Forma `<proveedor>/<modelo>`; el proveedor debe estar en la tabla de proveedores |
| `limits` | `Limits` | archivo, tabla `[limits]` | ver `Limits` | Siempre presente (con sus valores por defecto si la tabla falta) |
| `paths` | `Paths` | archivo, tabla `[paths]` | ver `Paths` | Siempre presente |
| `api_key` | `Secret \| None` | **solo** entorno | `None` si el proveedor no requiere clave | Nunca viene del archivo |
| `key_variable` | `str \| None` | tabla de proveedores | `None` si no requiere clave | Nombre de la variable de entorno de la clave (no es secreto) |
| `source` | `Path` | localización | — | Ruta absoluta del archivo que se leyó |

### `Limits` (dataclass congelada) — reservado para HU-01-06

| Campo | Tipo | Clave TOML | Valor por defecto | Validación |
|---|---|---|---|---|
| `max_turns` | `int` | `limits.max_turns` | 30 | entero (no booleano) mayor que 0 |
| `max_seconds` | `int` | `limits.max_seconds` | 600 | entero (no booleano) mayor que 0 |
| `max_tokens` | `int` | `limits.max_tokens` | 200000 | entero (no booleano) mayor que 0 |

### `Paths` (dataclass congelada) — reservado para HU-01-03 y HU-03-01

| Campo | Tipo | Clave TOML | Valor por defecto | Validación |
|---|---|---|---|---|
| `workspace_root` | `Path \| None` | `paths.workspace_root` | `None` (sin área autorizada) | cadena no vacía; se vuelve absoluta respecto al directorio del archivo |
| `sessions_db` | `Path` | `paths.sessions_db` | `<directorio del archivo>/.harness/sessions.db` | cadena no vacía; igual que la anterior |

### `Secret`

Envoltorio de un valor secreto (la clave de un proveedor).

| Aspecto | Comportamiento |
|---|---|
| Contenido | Una cadena, guardada en un campo con `__slots__` (sin `__dict__`) |
| `repr`, `str`, `format` | Siempre `<secreto oculto>`; nunca el valor, ni parte de él, ni su longitud |
| `reveal() -> str` | Único modo de obtener el valor; lo usa solo quien deba autenticarse |
| Igualdad y `hash` | Por identidad (no se compara por valor) |
| Copia | `__copy__` y `__deepcopy__` devuelven el mismo objeto (la configuración es inmutable): `copy.copy`, `copy.deepcopy` y `dataclasses.asdict` funcionan y siguen mostrando `<secreto oculto>`; la clave no aparece en `repr`, `str`, `asdict` ni `deepcopy` |
| Serialización | `__reduce__` lanza `TypeError`: solo se bloquea `pickle` (no se puede guardar por descuido) |

### Tabla de proveedores (constante pública `PROVIDER_KEY_VARIABLES`, provisional)

| Proveedor | Variable de entorno de la clave |
|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `fake` | ninguna (el proveedor simulado no requiere clave) |

### Errores de dominio (todos hijos de `ConfigError`)

| Error | Atributos | Cuándo |
|---|---|---|
| `ConfigError` | — | Base de todos los siguientes (hereda de `Exception`) |
| `ConfigFileNotFoundError` | `path`, `origin` | El archivo no existe; `origin` es `parameter`, `HARNESS_CONFIG` o `default` |
| `ConfigFileUnreadableError` | `path`, `reason` | Es un directorio, falta permiso, error del sistema o no está en UTF-8 |
| `ConfigSyntaxError` | `path`, `line` (`int \| None`) | El contenido no es TOML válido |
| `SecretInConfigFileError` | `path`, `fields` (`tuple[str, ...]`) | El archivo tiene campos con aspecto de clave o secreto |
| `InvalidConfigError` | `path`, `problems` (`tuple[ConfigProblem, ...]`) | Valor fuera de rango, tipo incorrecto, campo desconocido u obligatorio ausente |
| `MissingKeyError` | `variable`, `provider` | El proveedor requiere clave y su variable falta o está vacía |

### `ConfigProblem` (dataclass congelada)

| Campo | Tipo | Notas |
|---|---|---|
| `field` | `str` | Ruta del campo con puntos (`limits.max_turns`); cadena vacía no se usa |
| `message` | `str` | Frase completa en español con punto final; nunca contiene el valor recibido |

---

## Relaciones

```text
load_config(path, environ)
   ├─ localiza y lee el archivo ─► diccionario TOML (descartable)
   ├─ valida ─► Limits, Paths, model
   ├─ consulta la tabla de proveedores ─► key_variable
   ├─ lee environ[key_variable] ─► Secret
   └─► HarnessConfig(model, Limits, Paths, Secret | None, key_variable, source)
        └─ se inyecta al núcleo (otra historia); el núcleo nunca llama a load_config
```

El diccionario TOML intermedio no se conserva ni se expone: solo existen los tipos inmutables.

---

## Reglas de validación y de resolución

| # | Regla | Error |
|---|---|---|
| C-1 | La ubicación sigue el orden parámetro, `HARNESS_CONFIG` (no vacía), `config.toml` en el directorio de trabajo | — |
| C-2 | El archivo debe existir | `ConfigFileNotFoundError` |
| C-3 | Debe ser un archivo legible y estar en UTF-8 (se admite marca de orden de bytes) | `ConfigFileUnreadableError` |
| C-4 | Debe ser TOML válido | `ConfigSyntaxError` |
| C-5 | Entre los nombres que el esquema **no** conoce (en cualquier nivel, incluido lo que hay dentro de una tabla desconocida), ninguno puede ser de clave o secreto (en minúsculas y sin `_` ni `-`, contiene `key`, `secret`, `token`, `password`, `passwd` o `credential`). Un campo declarado en el esquema (por ejemplo, `limits.max_tokens`) **nunca** se rechaza por su nombre | `SecretInConfigFileError` (si el nombre no es de clave, el campo desconocido es un problema de C-9). Su mensaje avisa de que también puede ser un nombre mal escrito de otro campo (por ejemplo, `limits.max_token`) y pide revisar el nombre si el campo es legítimo |
| C-6 | `model` es obligatorio, cadena, de la forma `<proveedor>/<modelo>` con ambas partes no vacías y proveedor de la tabla | `InvalidConfigError` |
| C-7 | `limits.*` son enteros mayores que 0 (un booleano no cuenta como entero) | `InvalidConfigError` |
| C-8 | `paths.*` son cadenas no vacías | `InvalidConfigError` |
| C-9 | Solo existen las claves del esquema (`model`, `limits.*`, `paths.*`); cualquier otra, o una tabla que no es tabla, se rechaza nombrando el campo | `InvalidConfigError` |
| C-10 | Todos los problemas de C-6 a C-9 se informan juntos, en orden determinista | `InvalidConfigError` |
| C-11 | Las rutas se vuelven absolutas respecto al directorio del archivo, con normalización léxica; no se comprueba su existencia ni se siguen enlaces | — |
| C-12 | Si el proveedor requiere clave, su variable debe estar definida y no vacía ni de solo espacios | `MissingKeyError` |
| C-13 | Ningún error ni `repr` contiene un valor recibido; el valor de la clave no aparece en ninguna salida | — |
| C-14 | La configuración devuelta es inmutable | `FrozenInstanceError` al asignar |

Orden de evaluación: C-1 → C-2 → C-3 → C-4 → C-5 → (C-6 a C-10) → C-11 → C-12. C-5 se evalúa sobre los nombres que el esquema no conoce (se localizan al contrastar el archivo con el esquema) y su error se lanza **antes** de informar los problemas de C-6 a C-10.
