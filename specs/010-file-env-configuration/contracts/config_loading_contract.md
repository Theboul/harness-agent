# Contrato: carga de configuración, errores, plantillas y comprobaciones (HU-00-04)

**Plan**: [../plan.md](../plan.md) | **Modelo de datos**: [../data-model.md](../data-model.md) | **Puertos**: sin cambios (`src/harness_agent/core/interfaces/`)

Este documento fija el comportamiento observable de `load_config`, de los tipos que devuelve y de los errores, además de lo que deben cumplir las plantillas y las comprobaciones del repositorio. Sirve de referencia para las pruebas (`tests/unit/test_config_*.py`, `tests/architecture/`) y para quien consuma la configuración (la raíz de composición, la CLI y las historias HU-01-03, HU-01-06, HU-03-01, HU-07-02 y HU-07-03).

---

## 1. API pública (`harness_agent.config`)

| Símbolo | Tipo | Notas |
|---|---|---|
| `load_config` | función | Único punto de entrada; ver sección 2 |
| `HarnessConfig`, `Limits`, `Paths` | dataclasses congeladas | Ver [data-model.md](../data-model.md) |
| `Secret` | clase | Envoltorio de la clave; `repr` oculto |
| `ConfigError` | excepción (hereda de `Exception`) | Base de todas las siguientes |
| `ConfigFileNotFoundError`, `ConfigFileUnreadableError`, `ConfigSyntaxError`, `SecretInConfigFileError`, `InvalidConfigError`, `MissingKeyError` | excepciones | Atributos en el modelo de datos |
| `ConfigProblem` | dataclass congelada | `field`, `message` |
| `PROVIDER_KEY_VARIABLES` | constante (`Mapping[str, str \| None]`) | Tabla proveedor → variable de entorno de la clave (`None` si no requiere); la lee la prueba de plantillas para comprobar que `.env.example` está sincronizada |

`harness_agent.core` **no** reexporta nada de este módulo ni lo importa (FR-011).

---

## 2. `load_config`

```text
load_config(path: str | os.PathLike[str] | None = None, *, environ: Mapping[str, str] | None = None) -> HarnessConfig
```

| Aspecto | Comportamiento |
|---|---|
| `path` | Ubicación explícita del archivo. Si se indica, **gana** sobre `HARNESS_CONFIG`. Una ruta relativa se interpreta respecto al directorio de trabajo actual |
| `environ` | Mapa de variables de entorno que se consulta; por defecto `os.environ`. Las pruebas pasan un diccionario |
| Éxito | Devuelve un `HarnessConfig` inmutable. Cada campo tiene su valor del archivo o, si no se indicó, su valor por defecto; `api_key` solo si el proveedor del modelo requiere clave |
| Errores | Todos hijos de `ConfigError`; ver sección 5 |
| Garantías | Sin efectos secundarios (no escribe, no cambia el directorio de trabajo, no modifica `environ`); determinista (mismos archivo y entorno, mismos textos de error y valores equivalentes: dos cargas devuelven configuraciones que se comparan campo a campo; si hay clave, `Secret` compara por identidad, así que las dos configuraciones no son `==` pero su `reveal()` coincide); sin red; nunca devuelve una configuración parcial |
| Momento | Se llama una vez al arrancar; no hay recarga |

### Localización del archivo (orden de prioridad)

1. El parámetro `path`, si no es `None`.
2. La variable `HARNESS_CONFIG` en `environ`, si está definida y no está vacía ni es solo espacios.
3. `config.toml` en el directorio de trabajo actual.

Las variables de entorno **no** se usan para ningún otro valor no secreto: `MODEL`, `HARNESS_MODEL` o cualquier otra se ignoran.

### Orden de las comprobaciones

localización → existencia → lectura y UTF-8 → sintaxis TOML → campos desconocidos con nombre de clave o secreto → esquema (todos los problemas juntos) → resolución de rutas → clave del entorno.

---

## 3. Esquema del archivo (TOML)

| Clave | Tipo | Obligatoria | Por defecto |
|---|---|---|---|
| `model` | cadena `<proveedor>/<modelo>` | sí | — |
| `limits.max_turns` | entero > 0 | no | 30 |
| `limits.max_seconds` | entero > 0 | no | 600 |
| `limits.max_tokens` | entero > 0 | no | 200000 |
| `paths.workspace_root` | cadena no vacía | no | sin área autorizada (`None`) |
| `paths.sessions_db` | cadena no vacía | no | `.harness/sessions.db` |

- **Cualquier otra clave se rechaza** (nunca se ignora en silencio), incluidas las tablas desconocidas. Un campo de permisos, de proveedor o de claves no existe todavía en el esquema.
- Proveedores admitidos hoy: `anthropic`, `fake` y `openai` (tabla provisional, D6 del plan).
- Las rutas relativas, y el valor por defecto de `sessions_db`, se resuelven respecto al **directorio del archivo de configuración**, con normalización léxica; no se expande `~`, no se siguen enlaces y no se comprueba que existan. Una ruta con la forma de otro sistema (por ejemplo, `C:\x` en Linux) no se interpreta como absoluta ni se convierte: se trata como lo haría el sistema donde se ejecuta (FR-022).
- Codificación: UTF-8, con o sin marca de orden de bytes; saltos de línea LF o CRLF.
- Un booleano no es un entero; un decimal no es un entero.

---

## 4. Claves (solo del entorno)

| Situación | Resultado |
|---|---|
| El proveedor del modelo no requiere clave (`fake`) | `api_key` y `key_variable` son `None`; no se lee ninguna variable |
| El proveedor requiere clave y su variable está definida y no vacía | `api_key` es un `Secret` con el valor tal cual; `key_variable` es el nombre de la variable |
| La variable no existe, está vacía o tiene solo espacios | `MissingKeyError` |
| El archivo tiene un campo que **el esquema no conoce** y cuyo nombre es de clave o de secreto | `SecretInConfigFileError`, **antes** de informar los demás problemas de esquema. Un campo declarado en el esquema (como `limits.max_tokens`) **nunca** se rechaza por su nombre |

`Secret`: `repr`, `str` y `format` devuelven siempre `<secreto oculto>`; el valor solo sale con `reveal()`; `__copy__` y `__deepcopy__` devuelven el mismo objeto (la configuración es inmutable), de modo que `copy.copy`, `copy.deepcopy` y `dataclasses.asdict` funcionan y la clave no aparece en `repr`, `str`, `asdict` ni `deepcopy`; solo se bloquea `pickle` (`TypeError`). Como `HarnessConfig` es un dataclass, su `repr` usa el de `Secret`, de modo que la clave no aparece al imprimir la configuración.

Entre los nombres de campo que el esquema **no** conoce, se considera de clave o de secreto el que, en minúsculas y sin `_` ni `-`, contiene `key`, `secret`, `token`, `password`, `passwd` o `credential`. Esta heurística solo elige el mensaje (`SecretInConfigFileError` en lugar de «campo desconocido»); **nunca** se aplica a un campo del esquema: `limits.max_tokens` contiene «token» y es válido, y `config.example.toml` carga sin error.

---

## 5. Formato de los textos de error (destinatario: la persona usuaria)

Idioma: español. Cada mensaje es una o varias frases completas con punto final. **Nunca** se reproducen valores recibidos, trazas de pila, mensajes del analizador TOML ni el valor de ninguna clave. Los nombres de campo y de variable se muestran tal cual; los de campo se recortan a 64 caracteres con `…`. Las rutas se muestran absolutas.

**`ConfigFileNotFoundError`** (según el origen de la ubicación):

```text
No se encontró el archivo de configuración 'C:\proyectos\harness\config.toml'. Cree 'config.toml' a partir de 'config.example.toml' o indique otra ubicación con la variable de entorno HARNESS_CONFIG o con el parámetro de la función de carga.
```
```text
No se encontró el archivo de configuración 'D:\otra\mi.toml', indicado por la variable de entorno HARNESS_CONFIG. Compruebe la ruta.
```
```text
No se encontró el archivo de configuración 'D:\otra\mi.toml', indicado como parámetro de la función de carga. Compruebe la ruta.
```

**`ConfigFileUnreadableError`**: `No se pudo leer el archivo de configuración '<ruta>': <motivo>.` con un motivo de este conjunto fijo: `la ruta es un directorio`, `no hay permiso de lectura`, `no está codificado en UTF-8`, `el sistema devolvió un error de lectura`.

**`ConfigSyntaxError`**:

```text
El archivo de configuración '<ruta>' no es TOML válido (línea 7). Corrija la sintaxis y vuelva a arrancar.
```
Sin la línea cuando no se puede determinar: `El archivo de configuración '<ruta>' no es TOML válido. Corrija la sintaxis y vuelva a arrancar.`

**`SecretInConfigFileError`**:

```text
El campo 'api_key' del archivo de configuración '<ruta>' parece una clave o un secreto, o es un nombre mal escrito de otro campo. Las claves se definen solo en variables de entorno (vea .env.example); si es un campo legítimo, revise su nombre; si es una clave, elimine el campo del archivo.
```
Con varios campos: `Los campos 'api_key', 'limits.token' del archivo de configuración '<ruta>' parecen claves o secretos, o son nombres mal escritos de otros campos. Las claves se definen solo en variables de entorno (vea .env.example); si son campos legítimos, revise sus nombres; si son claves, elimine esos campos del archivo.`

**`InvalidConfigError`** (todos los problemas juntos; orden: obligatorios ausentes, campos presentes en el orden del esquema, desconocidos en el orden del archivo):

```text
Configuración inválida en '<ruta>':
- model: falta el campo obligatorio.
- limits.max_turns: debe ser un entero mayor que 0.
- paths.sessions_db: debe ser un texto no vacío.
- limites: campo desconocido en el esquema.
```
Motivos posibles: `falta el campo obligatorio.`, `debe ser un texto con la forma <proveedor>/<modelo>.`, `el proveedor no es uno de los admitidos (anthropic, fake, openai).`, `debe ser un entero mayor que 0.`, `debe ser un texto no vacío.`, `debe ser una tabla.`, `campo desconocido en el esquema.`

**`MissingKeyError`**:

```text
Falta la variable de entorno ANTHROPIC_API_KEY (o está vacía), que el proveedor 'anthropic' necesita para autenticarse. Defínala en el entorno (vea .env.example); su valor no se muestra.
```

Límite declarado (V-13): el nombre de un campo desconocido se muestra tal cual porque el mensaje debe nombrarlo; una clave pegada por error *como nombre de campo* (no como valor) quedaría en el mensaje. Es un riesgo residual aceptado y mínimo.

---

## 6. Plantillas y `.gitignore`

| Archivo | Versionado | Contenido |
|---|---|---|
| `config.example.toml` | sí | Todos los campos del esquema con sus valores por defecto, un modelo de ejemplo del proveedor simulado (`fake/test`) y un comentario por campo. Cargado con `load_config` da exactamente los valores por defecto del esquema |
| `.env.example` | sí | Las variables de clave de la tabla de proveedores (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`), **vacías**, con comentarios y cómo cargarlas en PowerShell y en bash. Nombra todas las variables de la tabla y solo esas |
| `config.toml` | **no** (ignorado) | Archivo real de la persona usuaria |
| `.env` | **no** (ignorado) | Variables reales; el sistema no lo lee (D4): la persona usuaria lo carga en su entorno |

El `.gitignore` ignora `config.toml` y `.env` y no ignora las dos plantillas (también ignora `.harness/`, FR-019). Ninguna plantilla contiene un patrón de clave.

---

## 7. Comprobaciones del repositorio (`tests/architecture/`)

| Comprobación | Falla si… |
|---|---|
| `test_no_secrets_in_repo.py` (AC-02) | un archivo versionado (`git ls-files`) tiene nombre de secreto (`.env` y `.env.*` salvo `.env.example`, `config.toml`, `*.pem`, `*.key`, `id_rsa`, `id_ed25519`, `*.p12`, `*.pfx`), o su contenido coincide con un patrón de clave. Incluye una autoprueba del detector con ejemplos sintéticos. Se salta con motivo explícito si no hay repositorio o `git`, salvo que `CI` esté definida |
| `test_core_reads_no_config.py` (FR-011) | un archivo de `core/` importa `tomllib` o `harness_agent.config`, usa `os.environ`/`os.getenv`, o llama a `open` o a `.read_text`/`.read_bytes` |

El historial de cambios se comprueba con el procedimiento manual de [../quickstart.md](../quickstart.md) §4 (la CI trabaja con una copia superficial).

---

## 8. Uso previsto por el consumidor

1. La raíz de composición (o la CLI) llama una sola vez a `load_config(...)` al arrancar; si lanza `ConfigError`, muestra `str(error)` y termina sin continuar.
2. Reparte a cada pieza solo lo que necesita: `config.limits` al bucle (HU-01-06), `config.paths.workspace_root` al área autorizada (HU-01-03), `config.paths.sessions_db` al almacén de sesiones (HU-03-01), `config.model` y `config.api_key` al adaptador del proveedor (HU-07-02).
3. Un `workspace_root` `None` significa **sin área autorizada**: las escrituras se deniegan (falla cerrada); el consumidor nunca lo sustituye por el directorio actual.
4. Quien necesite la clave llama a `config.api_key.reveal()` en el último momento y no la guarda, ni la registra ni la incluye en eventos o mensajes.
5. El núcleo nunca llama a `load_config` ni lee archivos o entorno.

---

## 9. Fuera de este contrato

Lógica de las historias consumidoras; ampliación de proveedores y de la tabla de variables (HU-07-02, HU-07-03); reglas de permisos en el archivo (HU-05-xx); argumento de la terminal para indicar la ubicación (HU-06-01); recarga en caliente; lectura de `.env`; redacción de secretos en trazas y auditoría (HU-10-02) y detector de patrones de claves (HU-04-05); reescritura del historial de cambios.
