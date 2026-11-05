## Equipo 👥

- **Integrante 1:** CORRALES FERREL BRAD ALEXANDER
- **Integrante 2:** SANDOVAL SANCHEZ GUSTAVO ANTONIO
- **Integrante 3:** SANTOS CASTRO ROBERTO ANJEL

## Materia 🎓

- **Materia:** TOPIC.AVANZ.DE PROGRAMAC.(ALGORIT.GENE.)
- **Grupo:** SA

## Resumen y estado 📋

**harness-agent** es un harness de agente en terminal: la aplicación que rodea a un modelo de lenguaje y lo conecta con el mundo mediante un bucle razonar–actuar–observar, herramientas, permisos, contexto, memoria y sesiones. El núcleo es reutilizable y está desacoplado de la interfaz. Su enfoque es el **Coding Harness**: un ticket llega al agente, que modifica un repositorio, ejecuta pruebas, verifica criterios de aceptación y, con tu aprobación del diff, hace el commit y prepara el Pull Request.

**Estado** (según [`docs/PROGRESO.md`](docs/PROGRESO.md), única fuente de estado): ninguna historia está cerrada del todo, porque la ratificación técnica de los contratos (HU-00-01) sigue pendiente. Lo que ves aquí como **implementado, en revisión** está en `main` y tiene pruebas automáticas, pero espera la revisión cruzada, la CI remota o una decisión del Product Owner. Lo diferido no se ofrece como funcionando.

| Categoría | Qué incluye |
|---|---|
| Implementado y probado (en revisión) | Arranque y configuración (HU-00-04, HU-00-08, HU-00-08.1, HU-00-07); bucle y herramientas de archivos (HU-01-01, HU-01-02, HU-01-03); sesiones SQLite, eventos que sobreviven a un corte y reanudar (HU-03-01, HU-03-02, HU-03-04); compactación automática y contexto esencial (HU-02-03, HU-02-06.1); permisos, aprobación y rechazo con motivo, solo lectura y auditoría (HU-05-01 a HU-05-05, HU-05-07); consola (HU-06-01, HU-06-02); reintentos, trazas y redacción de secretos (HU-07-04, HU-10-01, HU-10-02); tarea con criterios protegidos y progreso del ticket (HU-11-01, HU-11-08.1); pruebas de fallos del núcleo (HU-00-05.1, HU-00-05.2) |
| Implementado, en revisión, con reservas | Adaptador LiteLLM (HU-07-02, sin prueba del equipo con un modelo real); shell y comandos de la tarea (HU-01-04, HU-11-03, sin entorno aislado); reglas de git (HU-11-02); verificación de criterios (HU-11-04.1); revisión del diff, commit y Pull Request (HU-11-05, HU-11-06); rutina de arranque (HU-11-08.2); cambio de modelo y modo `/plan` (HU-06-05, HU-06-06, HU-06-07); comandos de sesión (HU-02-04, HU-06-04); MCP por stdio (HU-08-01 a HU-08-04); opcionales apagados por defecto: subagentes (HU-09-01, HU-09-03, HU-09-04), conmutación por fallo (HU-07-05) y memoria (HU-04-01, HU-04-02); datos externos no confiables (HU-05-08, solo AC-02) |
| Diferido (Pendiente en `PROGRESO.md`) | HU-01-07, HU-01-08, HU-02-06.2, HU-03-05, HU-05-06, HU-06-03, HU-07-03, HU-09-02, HU-09-05, HU-09-06, HU-11-04.2, HU-11-07, HU-03-03, HU-04-03, HU-04-04, HU-04-05, HU-02-05, HU-02-07, HU-03-06, HU-07-06, HU-08-05, HU-08-06, HU-09-07, HU-10-03, HU-IN-01 a HU-IN-04: no existen todavía |

La demostración paso a paso está en [`docs/guion-demostracion.md`](docs/guion-demostracion.md) y lo que **no** demuestra, al final de ese archivo.

## Requisitos e instalación

Necesitas **Python 3.12.x** (otras versiones no se admiten), `git` y, para un modelo real, [Ollama](https://ollama.com) (local, sin clave) o la clave de un proveedor. Lo que va entre `<` y `>` en un comando lo cambias tú. Los comandos son para una máquina limpia.

### Windows (PowerShell)

```powershell
git clone https://github.com/Theboul/harness-agent.git
cd harness-agent
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[litellm]"
```

Si PowerShell no deja activar el entorno, ejecuta antes `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`. En Windows, si la ruta del entorno es larga, créalo en una ruta corta (ver «Solución de problemas»).

### Linux (bash)

```bash
git clone https://github.com/Theboul/harness-agent.git
cd harness-agent
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[litellm]"
```

El extra `litellm` instala el adaptador de modelos reales; sin él el comando arranca pero no puede hablar con ningún modelo. Otros extras: `mcp` (servidores MCP) y `dev` (pruebas y calidad); se combinan así: `pip install -e ".[litellm,mcp,dev]"`.

### Comprobar la instalación

Con el entorno activado y **sin** archivo de configuración, el comando debe fallar con un mensaje claro y salida 2 (esto confirma que está instalado):

```bash
harness
```

Salida esperada: una línea que empieza por `No se pudo iniciar: No se encontró el archivo de configuración` y termina el comando con código 2 (`echo $?` en bash, `$LASTEXITCODE` en PowerShell). Si ves `harness: command not found` o «no se reconoce», mira «Solución de problemas».

## Configuración mínima

`harness` busca `config.toml` en la **carpeta desde la que lo ejecutas** (otra ubicación: variable de entorno `HARNESS_CONFIG`). Esa carpeta es también tu área de trabajo: el agente solo escribe dentro de `workspace_root`. Crea una carpeta de trabajo que sea un repositorio de git, con un `.gitignore` que deje fuera lo del arnés:

```powershell
cd ..
mkdir mi-proyecto
cd mi-proyecto
git init
Set-Content -Encoding ascii .gitignore @(".harness/", "config.toml", ".env")
Set-Content -Encoding ascii config.toml @('model = "ollama/qwen2.5-coder:7b"', '', '[paths]', 'workspace_root = "."')
```

```bash
cd ..
mkdir mi-proyecto
cd mi-proyecto
git init
printf '.harness/\nconfig.toml\n.env\n' > .gitignore
printf 'model = "ollama/qwen2.5-coder:7b"\n\n[paths]\nworkspace_root = "."\n' > config.toml
```

Si git aún no conoce tu identidad (`git config --global user.name` no devuelve nada), configúrala en esta carpeta con `git config user.name "<TU_NOMBRE>"` y `git config user.email "<TU_CORREO>"`: el arnés hace el commit de la tarea y git lo exige. **No verificado por el agente** (en esta máquina la identidad ya estaba definida).

`model` es `<proveedor>/<modelo>` (proveedores admitidos: `anthropic`, `gemini`, `groq`, `ollama`, `openai` y `openrouter`; `fake` solo existe para las pruebas y el comando lo rechaza). Todas las opciones, comentadas, están en [`config.example.toml`](config.example.toml): cópialo si quieres verlas, pero **cambia su `model`** (trae `fake/test`).

**Las claves van solo en variables de entorno o en un archivo `.env` junto a `config.toml`**, nunca en `config.toml` ni en el repositorio. `.env` es un archivo de líneas `NOMBRE=valor` (ver [`.env.example`](.env.example)); lo que ya esté definido en el entorno manda sobre el archivo. Con una clave, por ejemplo Gemini:

```powershell
$env:GEMINI_API_KEY = "<TU_CLAVE>"
```

```bash
export GEMINI_API_KEY="<TU_CLAVE>"
```

Variables: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`. `ollama` no necesita ninguna.

## Primer paso con un modelo real

### Sin clave: Ollama (local)

1. Instala Ollama desde [ollama.com](https://ollama.com) y baja un modelo que soporte herramientas (el ejemplo usa `qwen2.5-coder:7b`; otros, como `llama3.1`, también sirven):

```bash
ollama pull qwen2.5-coder:7b
ollama list
```

2. Con `config.toml` como en la sección anterior (`model = "ollama/qwen2.5-coder:7b"`), arranca desde `mi-proyecto` con el entorno de `harness-agent` activado:

```bash
harness
```

Verás el indicador `tarea> `. Escribe una petición, por ejemplo: `Crea el archivo saludo.txt con la palabra hola`. Salida observada con `qwen2.5-coder:7b` en un entorno limpio: `[..] escribir_archivo: ejecutando` y `[ok] escribir_archivo: correcto (25 ms)`; después el modelo intentó comprobar el archivo con comandos del shell y el arnés pidió aprobación para cada uno (un bloque «APROBACIÓN REQUERIDA» con el comando; `1` lo aprueba una vez, `3` lo rechaza). El texto exacto y el número de pasos dependen del modelo, y un modelo pequeño puede dar vueltas: si no avanza, escribe `/salir`. Para terminar: `/salir`.

### Con clave: Gemini (u otro proveedor)

Define la variable del proveedor (sección anterior), cambia la línea `model` de `config.toml` a `gemini/gemini-3.5-flash-lite` (o `<proveedor>/<modelo>`) y ejecuta `harness` igual. Esta ruta **no está verificada por el agente** (necesita una clave y red): si falla, mira «Solución de problemas».

## Arrancar una tarea

Una tarea es un archivo Markdown con un objetivo y criterios de aceptación; los criterios con `comando:` y `espera:` los verifica el arnés ejecutando el comando, y los demás quedan pendientes de tu confirmación. Crea `tarea.md` en `mi-proyecto`:

```powershell
Set-Content -Encoding ascii tarea.md @'
# DEMO-1: Saludo

## Objetivo
Crear el archivo saludo.txt con la palabra hola.

## Reglas
- No uses git: el arnes hace el commit despues de que revises el diff.

## Criterios
- El archivo existe y dice hola
  - comando: python -c "assert open('saludo.txt').read().strip() == 'hola'"
  - espera: codigo_salida == 0
- El archivo no tiene nada mas
'@
```

```bash
cat > tarea.md <<'EOF'
# DEMO-1: Saludo

## Objetivo
Crear el archivo saludo.txt con la palabra hola.

## Reglas
- No uses git: el arnes hace el commit despues de que revises el diff.

## Criterios
- El archivo existe y dice hola
  - comando: python -c "assert open('saludo.txt').read().strip() == 'hola'"
  - espera: codigo_salida == 0
- El archivo no tiene nada mas
EOF
```

Haz un primer commit para que el diff que revisarás solo contenga lo que haga el agente (ambos shells):

```bash
git add .gitignore tarea.md
git commit -m "inicial"
```

Las secciones son `## Objetivo` y `## Criterios` (o `## Criterios de aceptación`), obligatorias, y `## Contexto`, `## Reglas` y `## Comandos`, opcionales (`## Comandos` declara `- pruebas: ...` y `- lint: ...` que el agente puede ejecutar sin preguntar). Un criterio sin `comando:` es semántico. Luego arranca:

```bash
harness --tarea tarea.md
```

Dentro, `/criterios` muestra el estado de cada criterio: `cumplido` solo aparece después de que el arnés ejecuta el comando. Cuando el agente propone terminar y los criterios objetivos se cumplen, ves el resumen del diff y eliges: `1` aprobar y hacer commit, `2` ver el diff completo, `3` rechazar con motivo, `4 N` / `5 N` confirmar o rechazar el criterio semántico N. Después el arnés ofrece subir la rama y crear el Pull Request (cada acción pide su propia confirmación y necesita `gh` y un remoto; **no verificado por el agente**).

Otras formas de arrancar:

```bash
harness --issue 7
harness --issue https://github.com/<DUEÑO>/<REPO>/issues/7
harness --solo-lectura
harness --solo-lectura --tarea tarea.md
```

`--issue` lee el cuerpo de un issue de GitHub con `gh` (instalado y con sesión iniciada; **no verificado por el agente**). `--solo-lectura` deniega toda escritura (también se activa con `read_only = true` en `[permissions]`). `--tarea` e `--issue` a la vez es un error.

Cuando el agente pide permiso para algo, ves un bloque con la herramienta, sus argumentos y el efecto, y eliges `1` aprobar una vez, `2` aprobar para la sesión o `3` rechazar (después puedes escribir el motivo, que vuelve al agente).

## Comandos de la consola

Los comandos empiezan por `/`; cualquier otra línea se envía al agente como una tarea.

| Comando | Qué hace |
|---|---|
| `/ayuda` | Muestra la lista de comandos. |
| `/salir` | Termina la sesión. |
| `/sesiones` | Lista las 10 sesiones más recientes (sin las de subagentes); la actual lleva `*`. |
| `/reanudar <id>` | Reanuda una sesión guardada sin tarea por su identificador. |
| `/nueva` | Empieza una sesión nueva con el historial limpio; la anterior sigue guardada. |
| `/compactar` | Compacta el contexto ahora, aunque no se haya alcanzado el umbral, y muestra el tamaño estimado antes y después. |
| `/plan` | Pasa al alias de modelo `plan` y activa el solo lectura. |
| `/implementar` | Vuelve al alias `build` y desactiva el solo lectura (salvo que se fijara al arrancar). |
| `/criterios` | Muestra el estado de los criterios; solo existe en una sesión con tarea. |
| `/model [alias]` | Muestra el modelo, los alias, la ventana y los límites; con un alias cambia de modelo. |
| `/auditoria [id]` | Muestra las decisiones de permisos de la sesión (o de la que indiques). |
| `/trazas [id]` | Muestra las llamadas al modelo y a las herramientas con su duración. |

No hay comandos para la memoria ni para los servidores MCP: la memoria es una herramienta que usa el modelo.

## Funciones opcionales

Se activan en `config.toml`; todas están apagadas por defecto salvo las trazas, y cada una tiene su sección de ejemplo en [`config.example.toml`](config.example.toml).

### Subagentes (opcional, apagados por defecto)

Con `enabled = true` el agente recibe la herramienta `delegar`: entrega una subtarea a un subagente que trabaja en una sesión hija con el contexto vacío (solo conoce lo que el agente le pasa), con su propio bucle y sus propios límites, bajo las mismas reglas de permisos. Lo que vuelve al agente es un resultado breve (`resultado`, `hallazgos_clave`, `fuentes`, `error`, `parcial`), nunca la conversación del subagente. Un subagente no puede delegar; si agota sus turnos devuelve un resultado parcial; si necesita una aprobación, la ves con la línea `Pide:` que dice qué subagente la pide. En solo lectura (`--solo-lectura`, `/plan`) no se puede delegar.

```toml
[subagents]
enabled = true
max_turns = 10      # llamadas al modelo de cada subagente
max_seconds = 300
max_tokens = 50000
```

### Varios modelos: planear con uno e implementar con otro

Además del `model` de siempre, `config.toml` admite alias de modelos (LiteLLM, `<proveedor>/<modelo>`). Las claves de cada proveedor van **solo** en el entorno o en el `.env` (`GEMINI_API_KEY`, `GROQ_API_KEY`…), nunca en el archivo.

```toml
model = "groq/openai/gpt-oss-120b"

[models]
plan = "gemini/gemini-3.5-flash-lite"
build = "groq/openai/gpt-oss-120b"
```

| Comando | Qué hace |
|---|---|
| `/model` | Lista los alias, el modelo activo y el modo; nunca muestra claves. |
| `/model <alias>` | Cambia de modelo en caliente (`predeterminado` vuelve al `model` de arriba); el historial se conserva. |
| `/plan` | Cambia al alias `plan` (o al predeterminado si no existe) y activa el solo lectura: no se puede escribir. |
| `/implementar` | Vuelve al alias `build` (o al predeterminado) y desactiva el solo lectura, salvo que se fijara con `--solo-lectura` o `read_only = true`. |

Si falta la clave de un proveedor el sistema arranca igual; avisa al elegir ese alias y no cambia nada.

Tras `/plan` o `/implementar` el modelo recibe un aviso del modo con tu siguiente petición (una vez por cambio). Al terminar un turno en `/plan` el arnés pregunta `1` pasar a implementar / `2` seguir planificando; sin respuesta o con una respuesta inválida se sigue en solo lectura, y no se pregunta si el solo lectura se fijó al arrancar.

Para diagnosticar un error del proveedor (p. ej. un 400) arranca con `HARNESS_DEBUG_PROVIDER=1`: el texto del error sale por `stderr` (sin la clave, ≤ 2 000 caracteres, nunca a disco). Ojo: puede incluir texto de tu petición, porque el proveedor suele repetirlo.

### Conmutación por fallo entre modelos (opcional, apagada por defecto)

Si el modelo en uso falla por un motivo ajeno a tu petición (cuota agotada, límite de tasa, tiempo agotado, servicio no disponible o error de conexión) y ya agotó sus reintentos, el arnés puede pasar solo al siguiente modelo de una lista de respaldo, repetir la misma llamada y avisarte. Se activa con una lista de alias de `[models]` (ver arriba), en el orden en que se prueban; el `model` de siempre va primero y no se escribe en la lista:

```toml
model = "groq/openai/gpt-oss-120b"

[models]
plan = "gemini/gemini-3.5-flash-lite"
build = "groq/openai/gpt-oss-120b"
respaldo = "ollama/llama3.1"

[failover]
models = ["plan", "respaldo"]   # hasta 8 alias; sin esta sección (o vacía) no cambia nada
```

- **Qué conmuta y qué no.** Solo los cinco fallos de arriba. Una clave inválida, una petición mal formada, un rechazo por política de contenido y cualquier error desconocido **no** conmutan: ves el error.
- **Sin bucles.** En una petición cada modelo se prueba como máximo una vez y no se vuelve atrás; si todos fallan ves un error fijo (`FailoverExhausted`) y la petición siguiente empieza la lista de nuevo.
- **Qué ves.** Una línea «Cambio de modelo por fallo: A a B (motivo).» y un evento `provider_switched` en el registro de la sesión (solo nombres de modelo y la clase del error, nunca el texto del proveedor).
- **El cambio se queda.** El modelo de respaldo pasa a ser el modelo activo (`/model` lo muestra; `/model predeterminado` vuelve al de `model`). Tras el cambio, la compactación del contexto usa la ventana y el umbral del modelo nuevo (`[context.windows]`) desde la petición siguiente.
- **Claves.** Como siempre, solo en el entorno o en el `.env`. Si falta la clave de un alias de respaldo, el arnés arranca, avisa con el nombre de la variable y deja ese alias fuera de la lista.
- **Costo en el peor caso.** Una llamada puede hacer (modelos de la lista) × `[retries] max_attempts` intentos antes del error final; bájalos con `[retries] max_attempts` si pesa.

### Memoria persistente (opcional, apagada por defecto)

Con `enabled = true` el agente recibe la herramienta `memoria` para guardar datos breves (una preferencia, una decisión) que **sobreviven a las sesiones y a su compactación**. Viven en una tabla propia del mismo archivo de sesiones (`sesiones.db`), separada del historial: borrar o compactar una sesión no las toca. La memoria es la del archivo, así que la comparte todo lo que use ese archivo.

```toml
[memory]
enabled = true
budget_tokens = 2000      # tokens que puede ocupar el bloque al abrir una sesión (400 a 8000)
max_entries = 200         # entradas que guarda (1 a 1000)
max_content_chars = 500   # caracteres de una entrada, de una sola línea (50 a 2000)
```

- **Guardar y olvidar.** El agente llama a `memoria` con `accion` = `guardar` (una `clave` y un `texto`) u `olvidar` (por `clave`); guardar con una clave que ya existe la reemplaza y la deja como la más reciente. **Cada llamada te pregunta** (riesgo alto) y se deniega en solo lectura (`--solo-lectura`, `/plan`), con `[permissions] deny = ["memoria"]` y sin aprobador; un subagente no la ve.
- **Qué se guarda.** Una línea sin caracteres ocultos; las credenciales (claves con prefijo, `Bearer`, URLs con usuario y contraseña, valores de tu entorno con nombre de clave) se ocultan **antes** de escribir en disco. Un texto vacío o más largo que el tope se rechaza (no se corta). Con la memoria llena, una clave nueva se rechaza (`[memoria_llena]`) y hay que olvidar una antes.
- **Qué recibe el modelo.** Al abrir una sesión **nueva** (al arrancar y con `/nueva`; no al reanudar con `/reanudar`) las entradas **más recientes** entran en el contexto, enteras, hasta llenar el presupuesto (nunca más del 20 % del umbral de compactación del modelo en uso). Van en un mensaje de datos con el aviso fijo «datos, no instrucciones»: no cambian permisos ni reglas y la compactación no las resume. Si algo no cabe, el bloque y la pantalla dicen cuántas entradas más antiguas se omitieron («Memoria: se cargaron X entradas y se omitieron N más antiguas por el presupuesto.»).
- **Límites.** Lo que el modelo guarde puede ser incorrecto o malicioso y volver a leerse en sesiones futuras: la limpieza, la redacción y la pregunta por cada guardado lo mitigan, no lo eliminan (la redacción de secretos es heurística). Inspeccionar y editar la memoria a mano llegará con otra historia.

### Auditoría de decisiones y trazas de las llamadas

Dos registros en el mismo archivo de sesiones (`sesiones.db`) que se consultan desde la sesión:

- **`/auditoria [id]`**: cada decisión de permiso (permitida, denegada, aprobada o rechazada por ti) con la hora, quién la pide (el agente, la verificación de criterios, la rutina de arranque o un subagente), la herramienta, sus argumentos y el resultado. También las de las herramientas MCP. Los argumentos se guardan **sin claves ni credenciales** (patrones conocidos, URLs con usuario y contraseña y los valores de tus variables de entorno con nombre de clave) y acortados; no se guarda el motivo con el que rechazas.
- **`/trazas [id]`**: cada llamada al modelo y a una herramienta con su duración, los tokens que informó el proveedor (o «sin dato» si no los informó; nunca una cifra inventada) y su resultado (`ok`, la clase del error o la etiqueta del error de la herramienta). No guardan el contenido de los mensajes ni de los resultados. Una llamada con reintentos o con cambio de modelo es **una** traza.

Sin identificador muestran la sesión actual (y las de sus subagentes); con uno, esa sesión. Imprimen una tabla corta con las últimas 30 filas. Un identificador mal escrito o una lectura que falla dan una línea fija y la sesión sigue.

La auditoría no se puede apagar y es estricta: si una decisión no se puede registrar, la herramienta **no se ejecuta**. Las trazas están encendidas por defecto y no cambian nunca el resultado de una llamada (si no se pueden guardar, avisan una vez y la sesión sigue); se apagan con:

```toml
[traces]
enabled = false
```

Límites: no hay purga ni rotación (las filas crecen con el uso), la redacción de secretos es heurística y no hay exportación a archivos.

### Servidores MCP (opcional, implementado en revisión)

Los servidores MCP por stdio aportan herramientas al agente (HU-08-01 a HU-08-04). Necesitan el extra `mcp` (`pip install -e ".[mcp]"`). Cada servidor es una tabla `[mcp_servers.<nombre>]`; el servidor no hereda tu entorno (solo las variables cuyo **nombre** pongas en `env`). Ejemplo con el servidor de demostración del repositorio (cambia la ruta por la de tu clon):

```toml
[mcp_servers.demo]
command = "python"
args = ["<RUTA_DE_HARNESS>/tests/spikes/mcp_demo_server.py"]
env = []
```

Las herramientas MCP entran con riesgo alto: **cada llamada te pide aprobación**. Si un servidor no arranca, el arnés avisa y sigue sin sus herramientas; si cae a mitad de sesión, sus herramientas responden `[mcp_server_down]` y la sesión continúa (no se reconecta: decisión pendiente del Product Owner).

## Solución de problemas

| Lo que ves | Qué hacer |
|---|---|
| `harness: command not found` o «no se reconoce» | El entorno virtual no está activado (`.\.venv\Scripts\Activate.ps1` o `source .venv/bin/activate`) o no se instaló: repite `pip install -e ".[litellm]"`. También funciona `python -m harness_agent`. |
| `--tarea` o `--issue` no hacen nada o `harness` ignora las opciones | Es un comando instalado antes de que existieran las opciones: reinstala con `pip install -e .` y vuelve a abrir la terminal. |
| `No se pudo iniciar: No se encontró el archivo de configuración …` | Ejecuta `harness` desde la carpeta que tiene `config.toml`, o define `HARNESS_CONFIG` con su ruta. |
| `No se pudo iniciar: El proveedor 'fake' solo existe para pruebas …` | Cambia `model` en `config.toml` por un modelo real (`ollama/<modelo>`, `gemini/<modelo>`…). |
| `No se pudo iniciar: Falta la variable de entorno GEMINI_API_KEY (o está vacía) …` | Define la variable del proveedor en el entorno o en `.env` junto a `config.toml` (el nombre varía con el proveedor). |
| `Falta la dependencia opcional 'litellm' …` | Instala el extra: `pip install -e ".[litellm]"`. En Windows crea el entorno en una ruta corta, por ejemplo `C:\tmp\venv`: con rutas largas la instalación puede quedar incompleta sin avisar. |
| `Aviso: no hay área de trabajo configurada (paths.workspace_root) …` | Añade `[paths]` con `workspace_root = "."` a `config.toml`; sin área, las herramientas de archivos están desactivadas. |
| `No se pudo iniciar: argumento no reconocido; uso: harness [--solo-lectura] [--tarea RUTA \| --issue NÚMERO\|URL]` | Un argumento no es válido; las opciones son solo esas tres y `--tarea` e `--issue` no van juntas. |
| `No se pudo ejecutar la CLI de GitHub (gh) …` | Con `--issue`, instala `gh` y ejecuta `gh auth login`. |
| El modelo no responde o falla la conexión (con Ollama) | Comprueba que Ollama está en marcha (`ollama list`) y que el modelo del `config.toml` está bajado. Para ver el error original del proveedor, arranca con `HARNESS_DEBUG_PROVIDER=1` (puede incluir texto de tu petición). |
| `[x] Límite: Se alcanzó el máximo de 30 turnos de la sesión. …` | El modelo dio demasiadas vueltas (con `qwen2.5-coder:7b` pasó tras 28 aprobaciones seguidas de comandos del shell sin terminar la tarea): usa un modelo más capaz, o sube `max_turns` en `[limits]` y empieza una sesión nueva. |
| PowerShell no deja activar el entorno | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y vuelve a activarlo. |

## Pruebas

Instala los extras de desarrollo y corre las cuatro puertas de calidad de la CI (todas deben dar exit 0):

```bash
pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
```

La CI exige además el umbral de cobertura fijado en `.github/workflows/ci.yml` (`--cov-fail-under`, único lugar donde vive) y el 60 % del núcleo; una ejecución parcial local (`pytest ruta -k nombre`) no lo aplica. Comprobaciones sueltas:

```bash
pytest tests/architecture
pytest tests/unit/test_docs_match_cli.py
```

La primera verifica las fronteras entre capas (`core/` no importa adaptadores ni SDKs); la segunda, que este README y los demás documentos solo nombren comandos, opciones y secciones que existen.

### Prueba de instalación limpia (HU-00-07)

Crea un entorno virtual temporal, instala el proyecto desde este checkout con `--no-deps` y comprueba que `harness` y `python -m harness_agent` terminan con una línea «No se pudo iniciar: …» y salida 2 (sin traza) cuando no hay configuración, y que importar el paquete no carga `litellm` ni `mcp`. Necesita red una vez (pip descarga `setuptools` para construir), por eso está fuera de la ejecución normal de `pytest` (marca `install`) y la CI la corre como paso aparte en Ubuntu y Windows:

```bash
pytest -m install --no-cov tests/install
```

En Windows, si la ruta temporal del sistema es larga, define `HARNESS_INSTALL_ROOT` con una carpeta corta que exista (por ejemplo `C:\tmp`): el límite de 260 caracteres de las rutas afecta a los entornos virtuales.

## Arquitectura

Hexagonal con Clean Architecture: las dependencias apuntan hacia el núcleo.

```
cli ──┐
      ├──▶ core ◀── adapters
bootstrap ──▶ (ambos)
```

| Carpeta | Responsabilidad |
|---|---|
| `src/harness_agent/core/` | Reglas y puertos (también la auditoría, las trazas y la redacción de secretos). Solo biblioteca estándar |
| `src/harness_agent/adapters/` | Implementaciones: proveedores, almacenamiento, MCP, herramientas nativas, sistema, tareas |
| `src/harness_agent/cli/` | Terminal; se suscribe al bus de eventos |
| `src/harness_agent/config.py` | Lectura de `config.toml` y del entorno |
| `src/harness_agent/bootstrap.py` | Raíz de composición: único lugar que une núcleo y adaptadores |
| `tests/` | `adapters`, `architecture`, `contracts`, `core`, `doubles`, `integration`, `spikes`, `unit`, `install` |

La frontera se verifica con tests basados en `ast` en `tests/architecture/` (no se usa `import-linter`); corren en la integración continua junto al resto de la suite. Los diagramas de lo implementado están en [`docs/arquitectura-implementada.md`](docs/arquitectura-implementada.md) y los contratos de diseño en [`docs/02-arquitectura.md`](docs/02-arquitectura.md).

## Documentación

- [`docs/00-indice.md`](docs/00-indice.md): índice de la documentación (visión, arquitectura, plan, historias y trazabilidad).
- [`docs/PROGRESO.md`](docs/PROGRESO.md): qué se hizo y dónde está.
- [`docs/guion-demostracion.md`](docs/guion-demostracion.md): guion de la demostración de 10 a 15 minutos.
- [`docs/arquitectura-implementada.md`](docs/arquitectura-implementada.md): la arquitectura tal como está construida.

## Sobre el proyecto

### Decisiones principales

| Tema | Decisión |
|---|---|
| Enfoque | Coding Harness basado en tickets: ticket → agente → cambios → pruebas → verificación → aprobación → Pull Request |
| Lenguaje | Python 3.12.x (única versión soportada, PD-07) |
| Interfaz | Terminal (CLI). El núcleo emite eventos por un bus y nunca imprime |
| Proveedores | LiteLLM detrás de una interfaz propia `Provider`; al menos dos con conmutación por fallo |
| Persistencia | SQLite (sesiones, eventos, memoria, auditoría, trazas) |
| Herramientas externas | Cliente MCP por stdio |
| Reto | Subagentes con contexto aislado |
| Sistemas operativos | Windows y Linux; integración continua en ambos |

### Skills del proyecto

Guías para el agente de código, en `.claude/skills/`:

| Skill | Cuándo se usa |
|---|---|
| `arquitectura-hexagonal-clean` | Implementar o revisar una historia con puertos y adaptadores |
| `estructura-carpetas-harness` | Decidir dónde va cada archivo nuevo |
| `verificar-fronteras-hexagonales` | Comprobar que `core/` no dependa de nada externo |

### Equipo y plan

- **Equipo:** A = Núcleo, B = Estado, C = Control y conexiones. Product Owner: Brad.
- **Plazo:** 4 sprints de 1 semana, con cierre máximo el 14/11/2026 (19–23/10, 26–30/10, 02–06/11 y 09–13/11). La cuarta semana está aprobada por el Product Owner; el reparto ampliado del Sprint 4 está por ratificar en el Planning.
- **Definition of Done:** integrado con CI en verde, con pruebas, tipos y formato correctos, sin secretos, revisado por otra persona y mostrado en la demostración.

| Sprint | Hito |
|---|---|
| 1 | Agente ejecutable en terminal: resuelve una tarea de varios pasos con herramientas de archivos y modelo real, escribe solo dentro de un área autorizada y deja la sesión guardada en SQLite |
| 2 | Primer flujo del Coding Harness: ticket → cambios → pruebas → verificación automática de criterios, con aprobación y rechazo, sesión reanudable y compactación que conserva el contexto esencial |
| 3 | Flujo completo hasta el Pull Request: subagente verificador, aprobación del diff, commit y PR; progreso del ticket, conmutación de proveedor y auditoría mínima con secretos redactados |
| 4 | MCP bajo permisos con fallos aislados; memoria entre sesiones, trazas completas, listado de sesiones y preguntas al usuario (este reparto está por ratificar) |
