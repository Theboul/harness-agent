## Equipo 👥

- **Integrante 1:** CORRALES FERREL BRAD ALEXANDER
- **Integrante 2:** SANDOVAL SANCHEZ GUSTAVO ANTONIO
- **Integrante 3:** SANTOS CASTRO ROBERTO ANJEL

## Materia 🎓

- **Materia:** TOPIC.AVANZ.DE PROGRAMAC.(ALGORIT.GENE.)
- **Grupo:** SA

## Resumen 📋

**harness-agent** es un harness de agente en terminal: la aplicación que rodea a un modelo de lenguaje y lo conecta con el mundo mediante un bucle razonar–actuar–observar, herramientas, permisos, contexto, memoria y sesiones. El núcleo es reutilizable y está desacoplado de la interfaz.

> **Estado:** en desarrollo (Sprint 1). Ya existen el núcleo (`core/`), la configuración, la CLI básica, los conversores y las herramientas de archivos; aún no hay adaptador de proveedor real, SQLite, raíz de composición ni punto de entrada ejecutable. El estado de cada historia está en [`docs/PROGRESO.md`](docs/PROGRESO.md) y el contexto completo en [`docs/00-indice.md`](docs/00-indice.md).

## Decisiones principales

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

## Capacidades obligatorias

- Bucle del agente con herramientas.
- Contexto con compactación que conserva el historial original.
- Sesiones reanudables.
- Memoria persistente separada del historial.
- Permisos con aprobación humana; la política falla cerrada.
- CLI con eventos en tiempo real.
- Dos proveedores con conmutación por fallo.
- Cliente MCP.
- Subagentes.
- Trazas y auditoría con redacción de secretos.
- Flujo de tarea con criterios de aceptación, herramientas Git, pruebas y lint, verificación de criterios, aprobación del diff y Pull Request (E11).

## Arquitectura

Hexagonal con Clean Architecture: las dependencias apuntan hacia el núcleo.

```
cli ──┐
      ├──▶ core ◀── adapters
bootstrap ──▶ (ambos)
```

| Carpeta | Responsabilidad |
|---|---|
| `src/harness_agent/core/` | Reglas y puertos. Sin imports externos |
| `src/harness_agent/adapters/` | Implementaciones: proveedores, almacenamiento, MCP, herramientas nativas |
| `src/harness_agent/observability/` | Trazas, auditoría, redacción de secretos |
| `src/harness_agent/cli/` | Terminal; se suscribe al bus de eventos |
| `src/harness_agent/bootstrap.py` | Raíz de composición: único lugar que une núcleo y adaptadores |
| `tests/` | `adapters`, `architecture`, `contracts`, `core`, `doubles`, `integration`, `spikes`, `unit` |

La frontera se verifica con tests basados en `ast` en `tests/architecture/` (no se usa `import-linter`); corren en la integración continua junto al resto de la suite.

## Skills del proyecto

Guías para el agente de código, en `.claude/skills/`:

| Skill | Cuándo se usa |
|---|---|
| `arquitectura-hexagonal-clean` | Implementar o revisar una historia con puertos y adaptadores |
| `estructura-carpetas-harness` | Decidir dónde va cada archivo nuevo |
| `verificar-fronteras-hexagonales` | Comprobar que `core/` no dependa de nada externo |

## Equipo y plan

- **Equipo:** A = Núcleo, B = Estado, C = Control y conexiones. Product Owner: Brad.
- **Plazo:** 4 sprints de 1 semana, con cierre máximo el 14/11/2026 (19–23/10, 26–30/10, 02–06/11 y 09–13/11). La cuarta semana está aprobada por el Product Owner; el reparto ampliado del Sprint 4 está por ratificar en el Planning.
- **Definition of Done:** integrado con CI en verde, con pruebas, tipos y formato correctos, sin secretos, revisado por otra persona y mostrado en la demostración.

| Sprint | Hito |
|---|---|
| 1 | Agente ejecutable en terminal: resuelve una tarea de varios pasos con herramientas de archivos y modelo real, escribe solo dentro de un área autorizada y deja la sesión guardada en SQLite |
| 2 | Primer flujo del Coding Harness: ticket → cambios → pruebas → verificación automática de criterios, con aprobación y rechazo, sesión reanudable y compactación que conserva el contexto esencial |
| 3 | Flujo completo hasta el Pull Request: subagente verificador, aprobación del diff, commit y PR; progreso del ticket, conmutación de proveedor y auditoría mínima con secretos redactados |
| 4 | MCP bajo permisos con fallos aislados; memoria entre sesiones, trazas completas, listado de sesiones y preguntas al usuario (este reparto está por ratificar) |

## Instalación y uso

Entorno de desarrollo (Python 3.12.x):

```bash
python -m venv .venv
pip install -e ".[dev]"   # incluye pytest, pytest-asyncio, pytest-cov, mypy y ruff

# Las cuatro puertas de calidad de la CI (todas deben dar exit 0)
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
```

### Prueba de instalación limpia (HU-00-07)

Crea un entorno virtual temporal, instala el proyecto desde este checkout con `--no-deps` y comprueba que `harness` y `python -m harness_agent` terminan con una línea «No se pudo iniciar: …» y salida 2 (sin traza) cuando no hay configuración, y que importar el paquete no carga `litellm` ni `mcp`. Necesita red una vez (pip descarga `setuptools` para construir), por eso está fuera de la ejecución normal de `pytest` (marca `install`) y la CI la corre como paso aparte en Ubuntu y Windows:

```bash
pytest -m install --no-cov tests/install
```

En Windows, si la ruta temporal del sistema es larga, define `HARNESS_INSTALL_ROOT` con una carpeta corta que exista (por ejemplo `C:\tmp`): el límite de 260 caracteres de las rutas afecta a los entornos virtuales.

### Cobertura mínima

La CI exige que la suite completa cubra al menos el umbral fijado en `.github/workflows/ci.yml` (`--cov-fail-under`, único lugar donde vive). Una ejecución parcial local (`pytest ruta -k nombre`) no lo aplica.

La configuración de ejemplo está en `config.example.toml`; copiarla a `config.toml` (ignorado por Git) y poner las claves solo en variables de entorno. `.env.example` lista las variables de entorno. El uso de la CLI se documentará cuando exista un punto de entrada ejecutable.

## Subagentes (opcional, apagados por defecto)

Con `enabled = true` el agente recibe la herramienta `delegar`: entrega una subtarea a un subagente que trabaja en una sesión hija con el contexto vacío (solo conoce lo que el agente le pasa), con su propio bucle y sus propios límites, bajo las mismas reglas de permisos. Lo que vuelve al agente es un resultado breve (`resultado`, `hallazgos_clave`, `fuentes`, `error`, `parcial`), nunca la conversación del subagente. Un subagente no puede delegar; si agota sus turnos devuelve un resultado parcial; si necesita una aprobación, la ves con la línea `Pide:` que dice qué subagente la pide. En solo lectura (`--solo-lectura`, `/plan`) no se puede delegar.

```toml
[subagents]
enabled = true
max_turns = 10      # llamadas al modelo de cada subagente
max_seconds = 300
max_tokens = 50000
```

## Varios modelos: planear con uno e implementar con otro

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

## Conmutación por fallo entre modelos (opcional, apagada por defecto)

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

## Memoria persistente (opcional, apagada por defecto)

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

## Auditoría de decisiones y trazas de las llamadas

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

## Documentación

- [`docs/00-indice.md`](docs/00-indice.md): índice de la documentación (visión, arquitectura, plan, historias y trazabilidad).
- [`docs/PROGRESO.md`](docs/PROGRESO.md): qué se hizo y dónde está.
