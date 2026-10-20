# Investigación (Fase 0): HU-00-04 — Configuración por archivo y variables de entorno

Cada decisión sigue el formato Decision / Rationale / Alternatives considered. No quedan marcadores `NEEDS CLARIFICATION`: los tres del spec se resolvieron en la sesión de clarificación del 2026-10-20 (R-04, R-05 y R-06 los concretan).

## R-01 — Dónde vive la carga y quién conoce qué

- **Decision**: un único módulo `src/harness_agent/config.py`, fuera de `core/`, con la función pública `load_config`, los tipos inmutables, el tipo `Secret` y los errores de dominio. No se crea `bootstrap.py`. El núcleo no importa `harness_agent.config` ni lee archivos o entorno: recibirá los valores por inyección cuando la raíz de composición (otra historia) llame a `load_config` y los reparta. Una prueba de arquitectura lo verifica (R-14).
- **Rationale**: el árbol acordado asigna «lectura de configuración» a `config.py` en la raíz del paquete, y los Principios III y IV piden un núcleo sin dependencias del entorno. Crear la raíz de composición sin bucle ni adaptadores sería código de una historia posterior (Principio VI), igual que en HU-01-02 (R-11).
- **Alternatives considered**: poner los tipos de configuración en `core/` (rechazada: obligaría al núcleo a conocer el formato de la configuración y a que A y B coordinen un puerto nuevo sin necesidad); un puerto `ConfigProvider` (rechazada: el núcleo no necesita pedir configuración, solo recibirla); un paquete `config/` con varios módulos (rechazada: el árbol acordado fija un solo archivo y el código es corto).

## R-02 — Formato y lector

- **Decision**: TOML leído con `tomllib` de la biblioteca estándar (Python 3.12), sin dependencias nuevas. El archivo se lee como bytes y se decodifica con `utf-8-sig` (acepta una marca de orden de bytes) antes de `tomllib.loads`; los saltos de línea CRLF no son un problema para `tomllib`.
- **Rationale**: el árbol acordado ya fija `config.example.toml`; `tomllib` evita dependencias; TOML admite comentarios (las plantillas explican cada campo), tipos nativos (enteros, cadenas) y es igual en Windows y Linux.
- **Alternatives considered**: YAML (rechazada: exige una dependencia y su sintaxis permite ambigüedades de tipos); JSON (rechazada: no admite comentarios, esenciales en una plantilla); INI con `configparser` (rechazada: todo son cadenas y habría que convertir tipos a mano); solo variables de entorno (rechazada: la historia pide un archivo para modelo, límites y rutas).

## R-03 — Esquema, nombres y valores por defecto

- **Decision**: seis valores reservados, un campo tipado por cada uno, con estas claves TOML:

  | Clave TOML | Tipo | Valor por defecto | Lo consumirá |
  |---|---|---|---|
  | `model` | cadena `<proveedor>/<modelo>` | ninguno (obligatorio) | HU-07-02, HU-07-03 |
  | `limits.max_turns` | entero > 0 | 30 | HU-01-06 |
  | `limits.max_seconds` | entero > 0 | 600 | HU-01-06 |
  | `limits.max_tokens` | entero > 0 | 200000 | HU-01-06 |
  | `paths.workspace_root` | cadena no vacía | ninguno (`None`: sin área autorizada) | HU-01-03 |
  | `paths.sessions_db` | cadena no vacía | `.harness/sessions.db` | HU-03-01 |

  Sin `model` el arranque se detiene; sin `workspace_root` queda `None`, que los consumidores deben tratar como ausencia de autorización (falla cerrada). El consumo se mide en tokens (regla de negocio 1 de HU-01-06); el costo en dinero no se reserva.
- **Rationale**: el spec exige un campo reservado por valor y que el modelo y la raíz del área no tengan valor por defecto seguro. Los números por defecto son un punto de partida razonable (30 turnos, 10 minutos, 200 000 tokens) que ninguna historia fija; la plantilla los muestra y se pueden cambiar sin código.
- **Alternatives considered**: representar «sin límite» con `0` o `null` (rechazada: ambigua y contraria a la falla cerrada; si alguna historia lo necesita, lo añadirá de forma explícita); poner un modelo por defecto (rechazada: el spec lo prohíbe); `max_seconds` decimal (rechazada: un entero basta y evita comparar flotantes).

## R-04 — Localización del archivo

- **Decision**: `load_config(path=None, *, environ=None)`. Orden de prioridad: el parámetro `path` explícito; si es `None`, la variable `HARNESS_CONFIG` (una cadena vacía o de solo espacios cuenta como no definida); si tampoco, `config.toml` en el directorio de trabajo actual en el momento de la llamada. Una ruta relativa se interpreta respecto al directorio de trabajo actual. El error de archivo ausente indica de dónde salió la ubicación (parámetro, `HARNESS_CONFIG` o predeterminada). No hay argumento de la terminal: lo aportará la CLI y lo pasará como `path`.
- **Rationale**: es exactamente la respuesta a FR-005. Que el parámetro gane sobre la variable permite que una prueba o la CLI no dependa del entorno. `HARNESS_CONFIG` no es un secreto ni un valor de configuración, solo una ubicación.
- **Alternatives considered**: buscar el archivo en el directorio del usuario o junto al paquete (rechazada: el spec fija el directorio de trabajo; buscar en varios sitios crea precedencias ocultas); `HARNESS_CONFIG` por encima del parámetro (rechazada: lo explícito debe ganar).

## R-05 — Precedencia: solo el archivo define valores no secretos

- **Decision**: ninguna variable de entorno sobrescribe un valor no secreto. El único uso del entorno es (a) `HARNESS_CONFIG`, (b) las variables de clave de la tabla de proveedores (R-08). El `environ` se inyecta (por defecto `os.environ`) para que las pruebas no toquen el entorno real. Una variable cuyo nombre coincida con un valor no secreto (por ejemplo, una llamada `MODEL`) se ignora.
- **Rationale**: es la respuesta a FR-004. Una sola fuente por valor hace el comportamiento predecible y evita que una variable olvidada en la sesión cambie el modelo sin que nadie lo vea.
- **Alternatives considered**: el entorno gana sobre el archivo (rechazada por el responsable); prefijo `HARNESS_` para cada valor (rechazada: duplica el esquema y la validación).

## R-06 — Lectura robusta y errores de lectura

- **Decision**: la comprobación va en este orden: (1) existe (si no, `ConfigFileNotFoundError`); (2) es un archivo legible (si es un directorio, no hay permisos o falla el sistema, `ConfigFileUnreadableError` con un motivo de un conjunto fijo de frases); (3) se decodifica como UTF-8 (si no, el mismo error con el motivo «no está codificado en UTF-8»); (4) `tomllib.loads` (si falla, `ConfigSyntaxError`). El error de sintaxis nunca reproduce el mensaje de `tomllib` ni la línea del archivo, porque podrían contener una clave pegada por error: solo extrae el número de línea del mensaje con una expresión regular (`line (\d+)`) y, si no lo consigue, lo omite. Todos los errores se lanzan con `from None` para no encadenar la causa original.
- **Rationale**: FR-006 y FR-017 (sin trazas, sin valores) y el caso límite «línea con una clave pegada por error». `tomllib.TOMLDecodeError` en 3.12 no expone la línea como atributo, solo en el texto.
- **Alternatives considered**: usar `tomllib.load` sobre el archivo binario (rechazada: no acepta una marca de orden de bytes); citar el mensaje del analizador (rechazada: riesgo de filtrar contenido); no informar la línea (rechazada: pierde utilidad y es barato extraerla).

## R-07 — Validación y errores de dominio

- **Decision**: jerarquía local de errores, todos hijos de `ConfigError(Exception)` (no hay puerto que obligue a `ValueError`): `ConfigFileNotFoundError`, `ConfigFileUnreadableError`, `ConfigSyntaxError`, `SecretInConfigFileError`, `InvalidConfigError` y `MissingKeyError`. Orden de comprobaciones: localización y lectura (R-06) → **campos desconocidos con nombre de clave** (se localizan los campos que el esquema no conoce, en cualquier nivel, y entre ellos los de nombre de clave o secreto) → validación de esquema → resolución de rutas → clave del entorno. Los problemas de esquema se informan **todos juntos**, en el orden del esquema (primero los obligatorios faltantes, luego los campos presentes en el orden de la tabla de R-03, luego los desconocidos en el orden del archivo), como en HU-01-02. Entre los nombres que el esquema **no** conoce, se considera de clave o secreto el que, en minúsculas y sin `_` ni `-`, contiene `key`, `secret`, `token`, `password`, `passwd` o `credential`; esa comprobación va antes que la de «campo desconocido» (solo cambia el mensaje y el tipo de error) y su error no reproduce el valor. **Un campo declarado en el esquema nunca se rechaza por su nombre**: `limits.max_tokens` contiene «token» y es válido. Como un error tipográfico de un campo legítimo (`limits.max_token`) también contiene el marcador, el mensaje de `SecretInConfigFileError` dice que el nombre parece de clave o de secreto **o es un nombre mal escrito de otro campo**, e indica que, si el campo es legítimo, debe revisarse su nombre. Cada error es una frase completa en español que nombra el campo o la variable y cómo corregirlo, sin valores recibidos (los formatos exactos están en el contrato).
- **Rationale**: FR-007, FR-008, FR-014 y FR-017. Aplicar la heurística solo a nombres desconocidos evita rechazar `limits.max_tokens`, que es un campo válido. Informar todos los problemas a la vez ahorra ciclos de editar y arrancar. Comprobar los secretos antes que el esquema evita que un secreto pegado quede escondido tras un error de tipo.
- **Alternatives considered**: informar solo el primer problema (rechazada: peor experiencia); heredar de `ValueError` (rechazada: aquí no hay un puerto que lo exija y `ConfigError` evita capturas accidentales); aplicar la heurística a todos los nombres, también a los del esquema (rechazada: rechazaría `limits.max_tokens`, un campo válido); una lista blanca de nombres seguros en lugar de marcadores (rechazada: el esquema ya es una lista blanca; los marcadores solo mejoran el mensaje).

## R-08 — Claves: tabla de proveedores y `Secret`

- **Decision**: el modelo tiene la forma `<proveedor>/<modelo>`. Una tabla interna asigna a cada proveedor la variable de entorno de su clave: `anthropic` → `ANTHROPIC_API_KEY`, `openai` → `OPENAI_API_KEY`, `fake` → ninguna (el proveedor simulado de las pruebas). Un proveedor que no esté en la tabla es un problema de esquema (`model`) que lista los proveedores admitidos. Si el proveedor requiere clave, la variable debe existir y no estar vacía ni ser solo espacios (si no, `MissingKeyError` con el nombre de la variable); si no la requiere, no se lee nada. La clave se entrega en `HarnessConfig.api_key` como un `Secret`: clase con `__slots__`, `__repr__` y `__str__` fijos (`<secreto oculto>`), `__format__` coherente, sin `__eq__` por valor, con `__copy__` y `__deepcopy__` que devuelven el mismo objeto (la configuración es inmutable, para que `copy.deepcopy` y `dataclasses.asdict` funcionen sin exponer la clave), sin serialización (`__reduce__` lanza `TypeError`: solo se bloquea `pickle`) y un único método `reveal()` para quien deba autenticarse. El valor no se recorta: se entrega tal cual.
- **Rationale**: FR-013 a FR-016 y RNF-16. La tabla es el único sitio que conoce nombres de variables (el spec lo asumió: «cada modelo conocido declara si requiere clave y cuál es su variable»). Ocultar el valor en `repr` y `str` cubre la representación del propio `HarnessConfig` (un `dataclass` usa el `repr` de sus campos).
- **Alternatives considered**: que el archivo indique el nombre de la variable (rechazada: añade un campo con «key» en el nombre que choca con la detección de R-07 y abre la puerta a leer cualquier variable); una cadena simple para la clave (rechazada: se filtraría en cualquier `repr`); cifrar el valor en memoria (rechazada: sin valor real de seguridad y complejidad innecesaria).

## R-09 — Inmutabilidad y tipado

- **Decision**: `HarnessConfig`, `Limits` y `Paths` son `dataclass(frozen=True, slots=True)`; las rutas son `pathlib.Path`; no hay diccionarios ni listas mutables en la configuración. Los campos opcionales usan `X | None`. Una prueba comprueba que asignar a cualquier campo lanza `FrozenInstanceError` y que no existe `__dict__`.
- **Rationale**: FR-001 y FR-012; `mypy --strict` verifica el uso correcto de los tipos en los consumidores.
- **Alternatives considered**: `NamedTuple` (rechazada: sin campos con nombre más claros ni valores por defecto cómodos en la anidación); `types.MappingProxyType` (rechazada: pierde el tipado por campo).

## R-10 — Rutas relativas

- **Decision**: una ruta relativa del archivo se resuelve respecto al directorio del archivo de configuración con normalización léxica (`os.path.normpath` sobre la ruta absoluta), sin seguir enlaces simbólicos ni expandir `~`. Una ruta absoluta se normaliza igual. No se comprueba que exista ni que esté permitida: eso lo hacen HU-01-03 (contención sobre la ruta real) y HU-03-01 (apertura de la base). El valor por defecto de `sessions_db` se resuelve igual, respecto al directorio del archivo.
- **Rationale**: FR-010 y el caso límite del spec: el resultado no debe depender del directorio desde el que se arranca ni del sistema operativo. Resolver enlaces simbólicos es justo la responsabilidad de `AuthorizedArea`.
- **Alternatives considered**: relativas al directorio de trabajo (rechazada: el mismo archivo daría resultados distintos según desde dónde se arranque); `Path.resolve()` (rechazada: sigue enlaces y consulta el sistema de archivos, lo que corresponde a HU-01-03).

## R-11 — Plantillas

- **Decision**: `config.example.toml` (raíz) contiene todos los campos con sus valores por defecto, un modelo de ejemplo del proveedor simulado (`fake/test`) y un comentario por campo; `.env.example` lista las variables de clave de la tabla de R-08 con valor vacío y comentarios, y explica cómo cargarlas en PowerShell y en bash (D4). Una prueba (`test_config_templates.py`) carga `config.example.toml` con `load_config` sin error (incluido `limits.max_tokens`, que contiene «token» y es un campo válido) y comprueba que da exactamente los valores por defecto del esquema, que `.env.example` nombra todas las variables de la tabla y solo esas, y que ninguna de las dos plantillas contiene un patrón de clave.
- **Rationale**: Sp1-11 y regla de negocio 2; que las plantillas se prueben evita que se desactualicen cuando una historia añada un campo.
- **Alternatives considered**: valores de ejemplo con forma de clave («sk-…») en `.env.example` (rechazada: confunde a los detectores y a las personas); no probar las plantillas (rechazada: se desincronizan).

## R-12 — Comprobación automática de AC-02

- **Decision**: `tests/architecture/test_no_secrets_in_repo.py` obtiene los archivos versionados con `git ls-files -z` (ejecutado en la raíz del repositorio, calculada desde `__file__`), lee cada uno como UTF-8 (los que no lo son se cuentan como binarios y se omiten) y falla si (a) hay un archivo versionado con nombre de secreto (`.env` y `.env.*` salvo `.env.example`, `config.toml`, `*.pem`, `*.key`, `id_rsa`, `id_ed25519`, `*.p12`, `*.pfx`) o (b) algún contenido coincide con un patrón de clave: formas conocidas (`sk-…` de 20 o más caracteres, `AKIA…`, `AIza…`, `ghp_…`/`gho_…`, `xox…-…`, bloque `BEGIN … PRIVATE KEY`) o una asignación `clave|secret|token|password = "valor de 16 o más caracteres"`. El detector tiene su **autoprueba**: ejemplos sintéticos construidos en tiempo de ejecución por concatenación (para que el propio archivo de pruebas no contenga un patrón) deben ser detectados y el texto limpio no. Si no hay repositorio o no hay `git`, la prueba se salta con un motivo explícito, salvo que la variable de entorno `CI` esté definida, en cuyo caso falla.
  - **Las pruebas versionadas no deben contener literales detectables**: los ejemplos con forma de clave (y los archivos TOML de prueba con un campo de clave y el valor centinela) se construyen en tiempo de ejecución, por concatenación (`"api_" + "key"`), o usan valores de menos de 16 caracteres; de lo contrario la comprobación fallaría sobre el propio código de pruebas.
  - **Estado actual** (lectura previa, solo lectura): 232 archivos versionados, todos UTF-8, **0 coincidencias** y 0 archivos con nombre de secreto; el `.gitignore` aún no cubre `.env` ni `config.toml`.
  - **Límite declarado** (V-13): la detección por patrones no es total; la prueba reduce el riesgo y no lo elimina.
- **Rationale**: es la verificación automática que pidió el responsable para AC-02 y encaja con el resto de pruebas de arquitectura, que ya inspeccionan el repositorio. La CI hace `checkout` sin historial completo, por eso el historial se cubre con el procedimiento manual de R-13.
- **Alternatives considered**: escanear el árbol de trabajo en lugar de `git ls-files` (rechazada: incluiría `.env` y `config.toml` locales, que están ignorados a propósito); usar un detector externo (rechazada: dependencia nueva); no saltar nunca la prueba (rechazada: fallaría en un archivo comprimido sin `.git`, donde no tiene sentido).

## R-13 — Procedimiento manual para el historial

- **Decision**: se documenta en [quickstart.md](quickstart.md) §4.2, con órdenes que funcionan igual en bash y en PowerShell: `git log --all --oneline -G '<patrones conocidos>'`, `git log --all --oneline -i -G '<clave = valor largo>'` (sin comillas dentro del patrón, porque PowerShell 5.1 las elimina al llamar a `git`) y `git log --all --name-only --pretty=format: -- .env config.toml '*.pem' '*.key'` para los archivos de secretos que hayan existido; se registra el resultado en `docs/PROGRESO.md` y, si apareciera una clave, **se revoca y se emite otra** antes de cualquier otra acción. **Comprobado el 2026-10-20 (git 2.49.0)**: las tres órdenes detectan una clave sintética en un repositorio temporal (en bash y en PowerShell) y dan 0 resultados en este repositorio con todas sus ramas locales y remotas; reescribir el historial queda fuera de esta historia. Es el único modo de cubrir la segunda mitad de AC-02 («ni en el historial de cambios»), porque la CI trabaja con una copia superficial.
- **Rationale**: FR-021 y decisión 6 del responsable. Una clave que llegó al historial se considera comprometida aunque se borre después.
- **Alternatives considered**: automatizar el escaneo del historial en una prueba (rechazada: depende de un historial completo que la CI no clona y es lenta); un flujo de trabajo de CI aparte con `fetch-depth: 0` (rechazada: cambia la CI, que es de HU-00-02, y queda fuera de alcance; puede proponerse como mejora).

## R-14 — Prueba de que el núcleo no lee configuración

- **Decision**: `tests/architecture/test_core_reads_no_config.py` recorre con `ast` todos los archivos de `core/` y falla si encuentra: la importación de `tomllib` o de `harness_agent.config`; el uso de `os.environ`, `os.getenv` o `os.getenvb`; la llamada a `open(...)` o a `.read_text`/`.read_bytes`. Una autoprueba comprueba el detector con fragmentos sintéticos y con una copia de `core/` en `tmp_path` a la que se añade una lectura de entorno; el código real de `core/` no se edita en ningún momento. Estado actual: el núcleo (incluidos `core/tools/` y `core/loop.py`) no contiene ninguna de esas construcciones.
- **Rationale**: FR-011 y el escenario 1 de la historia 4; es el mismo estilo de barrera que `test_core_tools_stdlib_only.py`.
- **Alternatives considered**: ampliar `test_core_boundaries.py` (rechazada: es de HU-00-01 y su lista prohíbe SDK, no lecturas); `import-linter` (no está configurado en el repositorio; ya se anotó en HU-01-02).

## R-15 — Aislamiento de pruebas y plataformas

- **Decision**: las pruebas escriben sus archivos en `tmp_path` y pasan un `environ` en forma de diccionario a `load_config`, de modo que no leen ni cambian el entorno real; solo las pruebas del valor por defecto (`os.environ`, `HARNESS_CONFIG` y el directorio de trabajo) usan `monkeypatch.setenv`, `monkeypatch.delenv` y `monkeypatch.chdir`. Los archivos de prueba se escriben en bytes para controlar la codificación (con y sin marca de orden de bytes) y los saltos de línea (LF y CRLF). Las rutas del archivo usan solo `pathlib` y las comparaciones de rutas se hacen sobre `Path`, nunca sobre cadenas con separadores.
- **Rationale**: FR-022 y FR-023. Un `environ` inyectado evita las diferencias de Windows (nombres de variable sin distinción de mayúsculas) en casi todas las pruebas.
- **Alternatives considered**: usar siempre `monkeypatch.setenv` (rechazada: depende del entorno real y es más lento de razonar); sin parámetro `environ` (rechazada: obliga a tocar el entorno global en cada prueba).

## R-16 — Lectura de RF-7.6, RNF-16 y RNF-21

- **Decision**: su texto íntegro no figura en la documentación activa (solo la trazabilidad: RF-7.6 con HU-07-02, RNF-16 con HU-10-02, RNF-21 con HU-07-03). Se mantiene la lectura del spec: RF-7.6 = la clave del proveedor sale solo del entorno; RNF-16 = los secretos no aparecen en archivos, mensajes ni registros; RNF-21 = cambiar de modelo o proveedor es un cambio de configuración, no de código.
- **Rationale**: lo mismo que se hizo para RNF-2 y RNF-13 en HU-01-02. Conviene confirmarlo con el Product Owner antes de cerrar la historia.
- **Alternatives considered**: ninguna; es una interpretación a confirmar.

## R-17 — Sincronía, ciclo de vida y extensión

- **Decision**: `load_config` es síncrona, se llama una vez al arrancar y no tiene efectos secundarios (lee un archivo y el entorno; no escribe, no cachea, no registra). La configuración no se recarga. Los puntos de extensión previstos son: añadir un proveedor a la tabla de R-08 (HU-07-02/07-03), añadir campos al esquema (HU-05-xx, HU-01-06 al adoptar sus tipos) y pasar a `load_config` el argumento de la terminal como `path` (HU-06-01).
- **Rationale**: spec, casos límite («no se recarga») y simplicidad. Cada campo nuevo exige también actualizar las dos plantillas, algo que la prueba de plantillas obliga a hacer.
- **Alternatives considered**: carga perezosa o con caché (rechazada: no hay necesidad y complica las pruebas); recarga en caliente (fuera de alcance).
