# Feature Specification: HU-01-04 — Herramienta de shell portable con tiempo límite

**Feature Branch**: `feat/hu-01-04-shell-tool` (el directorio de la spec es `019-portable-shell-tool`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-24

**Status**: Borrador (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 2 | **Responsable**: C — Control y conexiones | **Tareas de referencia**: Sp2-01, Sp2-02, Sp2-03, Sp2-04, Sp2-05 | **Requisitos**: RF-1.2, RNF-20 | **Depende de**: HU-01-02 (registro de herramientas, integrada) y HU-05-01 (política de permisos, integrada)

**Input**: User description: "HU-01-04 — Herramienta de shell portable con tiempo límite (docs/04a-historias-fundacion.md#hu-01-04). Alcance: subprocesos con tiempo máximo, interfaz Shell con implementación para bash y otra para PowerShell, prefijo con sistema operativo e intérprete, salida acotada y marcada, pruebas en Linux y Windows. Fuera de alcance: HU-05-02 (análisis de comandos compuestos), HU-05-03 (aprobación interactiva), HU-01-06 (límites del bucle) y HU-02-02 (recorte general de salidas)."

## Clarifications

### Session 2026-10-24

Decisiones por defecto del análisis previo. Las marcadas **(por confirmar)** no tienen respuesta explícita todavía; se aplican mientras tanto, se confirman en `/speckit-clarify` y se registran en `PROGRESO.md`.

- Q: ¿Cómo se llama la herramienta que ve el modelo? → A: `shell` (coincide con `docs/02-arquitectura.md`, la constitución y la guía). La clase se llama `ShellTool`; los identificadores van en inglés.
- Q: ¿Dónde viven las piezas? → A: Las implementaciones de `Shell` (bash y PowerShell) y la elección según la plataforma en `src/harness_agent/adapters/system/`; la herramienta en `src/harness_agent/adapters/tools/` (propuesta de `PROGRESO.md`, observación «Menores» de 2026-10-23). El puerto `Shell`, `ShellResult` y el puerto `Tool` no cambian.
- Q: ¿Qué riesgo declara? → A: **alto** (`RiskLevel.HIGH`: «código arbitrario o ejecución en el sistema»). La política vigente (HU-05-01) pregunta ante cualquier herramienta de riesgo alto y, sin aprobador, el bucle lo resuelve como denegado: el shell **sale con aprobación obligatoria** hasta que lleguen HU-05-02 y HU-05-03 (riesgo R-19 del plan). Esta historia no toca la política.
- Q: ¿Qué argumentos tiene? → A: `command` (texto no vacío, con longitud máxima) y `timeout_seconds` (número opcional, mayor que 0, acotado por un máximo fijo). No hay argumento `path`: la convención de rutas de HU-05-01 no aplica y la política decide solo por el riesgo.
- Q: ¿Desde qué carpeta se ejecuta? → A: **(por confirmar)** Desde la raíz del área de trabajo (`AuthorizedArea.root`). Sin área configurada el shell no actúa y devuelve un error claro, igual que las herramientas de archivos. El área solo fija la carpeta de partida: no confina lo que el comando haga (un comando puede salir de ella; por eso la aprobación es obligatoria).
- Q: ¿Cómo informa el resultado? → A: **(por confirmar)** Un único texto con el código de salida y la salida combinada (salida estándar y de errores). Código 0 es éxito; código distinto de 0, tiempo agotado, intérprete no disponible y falta de área llevan `is_error=True` y una etiqueta (`[codigo_de_salida=N]`, `[tiempo_agotado]`, `[interprete_no_disponible]`, `[sin_area]`), como las etiquetas de las herramientas de archivos.
- Q: ¿Qué hace la salida larga? → A: **(por confirmar)** Se conserva el principio y el final dentro de un máximo fijo de caracteres y se marca con un aviso explícito de cuántos caracteres se omitieron. El máximo se alinea con el de las herramientas de archivos (20 000, observación «Menores» de PROGRESO) hasta que HU-02-02 defina el recorte general.
- Q: ¿Qué pasa con los procesos hijos de un comando? → A: Al agotarse el tiempo se termina el **árbol** de procesos, no solo el proceso directo (requisito heredado de D-01 / `revision-conjunta-abc.md`: grupos de procesos en POSIX y su equivalente en Windows).
- Q: ¿Qué es «el prefijo» mientras no exista el ensamblador de contexto (HU-02-01)? → A: **(por confirmar)** Un mensaje de sistema con el sistema operativo y el intérprete, construido por una función pura y conectado en `bootstrap.py` como primer mensaje del historial. Cuando HU-02-01 ensamble el prefijo estable, tomará ese texto sin cambiarlo.
- Q: ¿La lista de comandos denegados por plataforma (regla de negocio 3) se aplica en esta historia? → A: **No se aplica; solo se publica como dato.** Esta historia entrega la lista por defecto de cada plataforma (bash y PowerShell) como constantes de solo lectura y no rechaza ningún comando por sí misma; HU-05-02 la consume en la política (decisión del responsable, 2026-10-24, opción B). Así hay un único punto de decisión sobre comandos.
- Q: ¿El comando hereda las variables de entorno del harness, incluidas las claves de API? → A: **Hereda el entorno quitando las variables de claves de los proveedores** (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`); el resto (`PATH`, `HOME`, credenciales de Git…) se conserva (decisión del responsable, 2026-10-24, opción B). Los nombres a quitar llegan por constructor desde la raíz de composición, que los toma de la configuración; el adaptador no importa `config`.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04a-historias-fundacion.md` (HU-01-04). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

**Flujo general**

1. El modelo solicita ejecutar un comando.
2. La política de permisos evalúa el comando y, si corresponde, pide aprobación.
3. El sistema lo ejecuta con tiempo máximo en el intérprete de la plataforma.
4. Si excede el tiempo, lo termina y lo informa.
5. La salida se acota y vuelve al modelo.

**Reglas de negocio**

1. El intérprete se elige según el sistema operativo (PowerShell o bash) detrás de una misma interfaz.
2. El prefijo del contexto indica al modelo el sistema operativo y el intérprete.
3. La lista de comandos denegados es propia de cada plataforma.

**Criterios de aceptación**

- **AC-01 — Tiempo máximo de ejecución.** Dado un comando que excede el tiempo máximo, cuando se ejecuta, entonces se termina y el modelo recibe un resultado de tiempo agotado.
- **AC-02 — Intérprete según plataforma.** Dado el sistema operativo del usuario, cuando se ejecuta un comando, entonces se usa PowerShell en Windows y bash en Linux.
- **AC-03 — El modelo conoce su entorno.** Dado el arranque de una sesión, cuando se arma el contexto, entonces el prefijo indica al modelo el sistema operativo y el intérprete que se usan.
- **AC-04 — Mismas pruebas en Windows y Linux.** Dado el mismo conjunto de pruebas de shell, cuando corre en integración continua, entonces pasa en Windows y en Linux.

### Lo que ya existe y lo que cambia

- **Existe y no se toca**: el puerto `Shell` y `ShellResult` (`core/interfaces/system.py`), el puerto `Tool` y el registro (HU-01-02), la política (HU-05-01), el bucle de A, el bus, la CLI, la configuración y los dobles de `tests/doubles/`.
- **Se añade**: las implementaciones `Shell` de bash y de PowerShell con la ejecución de subprocesos con tiempo máximo, la elección de la implementación según la plataforma, la herramienta `shell`, el texto del prefijo de entorno, el recorte de salida, la conexión en `bootstrap.py` (la pieza nueva del arranque la cablea la historia que la crea) y sus pruebas (unitarias, de contrato, de integración y de arquitectura) que corren en Linux y en Windows.
- **No se añade**: análisis de comandos compuestos ni lista de denegación evaluada por la política (HU-05-02), aprobación interactiva (HU-05-03), contador de límites del bucle (HU-01-06), recorte general de salidas de herramientas (HU-02-02), ensamblador de contexto (HU-02-01), cancelación de un turno aislado, entorno aislado del shell (PD-06, pendiente del PO) ni cambios en `config.py`.

### User Story 1 - Un comando que se cuelga se termina y el modelo lo sabe (Priority: P1) [AC-01]

Como usuario operador, quiero que un comando que excede el tiempo máximo se termine, junto con todo lo que haya lanzado, y que el modelo reciba un resultado de tiempo agotado, para automatizar tareas sin riesgo de que el agente se cuelgue.

**Why this priority**: Es el criterio AC-01 y la razón de ser de la historia (RNF-20). Sin él, un comando interactivo o infinito bloquea la sesión.

**Independent Test**: Con la implementación de la plataforma, se ejecuta un comando que duerme más que el tiempo máximo: vuelve poco después del plazo, marcado como tiempo agotado, y no queda ningún proceso vivo (ni el directo ni uno hijo lanzado por el comando).

**Acceptance Scenarios**:

1. **Given** un comando que dura más que el tiempo máximo, **When** se ejecuta, **Then** el control vuelve poco después del plazo con `timed_out` verdadero y el modelo recibe un resultado con la etiqueta de tiempo agotado y el tiempo aplicado.
2. **Given** un comando que lanza un proceso hijo que sigue vivo, **When** se agota el tiempo, **Then** el hijo también termina (se termina el árbol de procesos).
3. **Given** un comando que escribe salida antes de colgarse, **When** se agota el tiempo, **Then** el modelo recibe la salida producida hasta ese momento, acotada.
4. **Given** un comando que termina antes del plazo, **When** se ejecuta, **Then** devuelve su código de salida y su salida sin esperar el plazo completo.
5. **Given** un tiempo máximo pedido por el modelo mayor que el máximo permitido o no positivo, **When** se valida la llamada, **Then** se rechaza o se acota al máximo documentado, nunca se ejecuta sin límite.
6. **Given** un comando que espera entrada por la entrada estándar, **When** se ejecuta, **Then** no se queda esperando al usuario: la entrada está cerrada y el comando termina o se agota su tiempo.

---

### User Story 2 - PowerShell en Windows y bash en Linux detrás de una misma interfaz (Priority: P1) [AC-02]

Como usuario operador, quiero que el agente use el intérprete propio de mi sistema operativo, para que los comandos del modelo corran en el shell que de verdad tengo.

**Why this priority**: Es el criterio AC-02 y la regla de negocio 1 (decisión V-08). Las dos plataformas del equipo difieren en comillas, rutas y comandos (riesgo R-18).

**Independent Test**: Con la plataforma inyectada, la elección devuelve la implementación de PowerShell para Windows y la de bash para Linux; en cada sistema real, un comando que imprime el nombre del intérprete que lo ejecuta lo confirma.

**Acceptance Scenarios**:

1. **Given** Windows, **When** se elige el shell, **Then** se obtiene la implementación de PowerShell y su `interpreter_name` es `powershell`.
2. **Given** Linux, **When** se elige el shell, **Then** se obtiene la implementación de bash y su `interpreter_name` es `bash`.
3. **Given** un sistema que no es Windows ni Linux (por ejemplo macOS), **When** se elige el shell, **Then** se usa bash si está disponible (no es plataforma del equipo ni se prueba en CI).
4. **Given** que el intérprete no está instalado, **When** el agente intenta ejecutar un comando, **Then** recibe un error claro con la etiqueta de intérprete no disponible, sin excepción ni traza.
5. **Given** cualquiera de las dos implementaciones, **When** se ejecuta el mismo comando simple, **Then** devuelven el mismo `ShellResult` en la forma (código de salida entero, texto, indicador de tiempo agotado).
6. **Given** un comando con tildes, eñes u otros caracteres no ASCII en su salida, **When** se ejecuta, **Then** el modelo recibe el texto correcto, no caracteres corruptos.

---

### User Story 3 - El modelo sabe en qué sistema y con qué intérprete trabaja (Priority: P1) [AC-03]

Como usuario operador, quiero que el modelo sepa desde el arranque qué sistema operativo y qué intérprete tiene delante, para que escriba comandos con la sintaxis correcta.

**Why this priority**: Es el criterio AC-03 y la regla de negocio 2. Es la mitigación del riesgo R-18 (diferencias de comillas y comandos).

**Independent Test**: Al componer el sistema y arrancar una sesión, el historial inicial empieza con un mensaje de sistema que nombra el sistema operativo y el intérprete de la implementación elegida.

**Acceptance Scenarios**:

1. **Given** el arranque de una sesión, **When** se arma el contexto, **Then** el primer mensaje del historial es de sistema e indica el sistema operativo y el intérprete en uso.
2. **Given** la misma plataforma y el mismo intérprete, **When** se construye el texto dos veces, **Then** es idéntico byte a byte (el prefijo debe ser estable para no romper el almacenamiento en caché del proveedor).
3. **Given** que el texto no contiene datos de la máquina más allá del sistema operativo y el intérprete, **When** se construye, **Then** no revela nombre de usuario, rutas ni variables de entorno.
4. **Given** un modelo `fake/…` o cualquier proveedor, **When** arranca la sesión, **Then** el mensaje de sistema es válido como prefijo contiguo del historial para todos los conversores.

---

### User Story 4 - La salida larga se acota y se marca (Priority: P2)

Como usuario operador, quiero que la salida muy larga de un comando llegue al modelo acotada y con una marca explícita de que se recortó, para no llenar su contexto ni hacerle creer que vio todo.

**Why this priority**: Es la tarea Sp2-04 y la regla del flujo (paso 5). P2 porque la historia funciona sin ella, pero una salida sin límite agotaría el contexto y la memoria.

**Independent Test**: Un comando que imprime mucho más que el máximo devuelve un texto que no supera el máximo documentado, conserva el principio y el final y dice cuántos caracteres se omitieron; un comando de salida corta no lleva ninguna marca.

**Acceptance Scenarios**:

1. **Given** una salida mayor que el máximo, **When** vuelve al modelo, **Then** el texto no supera el máximo, conserva el principio y el final y contiene un aviso con la cantidad omitida.
2. **Given** una salida menor o igual que el máximo, **When** vuelve, **Then** llega completa y sin aviso.
3. **Given** un comando que produce cientos de megabytes de salida, **When** se ejecuta, **Then** el uso de memoria del harness queda acotado (no se acumula toda la salida) y el comando termina o se agota su tiempo.
4. **Given** bytes que no son UTF-8 válido en la salida, **When** se decodifican, **Then** se sustituyen sin lanzar excepción.
5. **Given** que el recorte ocurre, **When** el modelo lee el resultado, **Then** el aviso aparece también en el caso de tiempo agotado y de código de salida distinto de 0.

---

### User Story 5 - La herramienta declara su riesgo y la política la controla (Priority: P2)

Como equipo de desarrollo, quiero que la herramienta `shell` declare riesgo alto y se registre como las demás, para que la política existente la trate con la máxima cautela mientras llegan el análisis de comandos y la aprobación interactiva.

**Why this priority**: Es el contrato con HU-05-01 y la mitigación del riesgo R-19; el shell no debe poder ejecutar nada sin aprobación.

**Independent Test**: Se registra la herramienta en el registro real (que valida su esquema) y, con el bucle real y la política real, una llamada a `shell` se pregunta y, sin aprobador, se resuelve como denegada sin ejecutar ningún comando.

**Acceptance Scenarios**:

1. **Given** la herramienta `shell`, **When** se registra en `InMemoryToolRegistry`, **Then** pasa la validación de esquema con nombre único.
2. **Given** su riesgo, **When** se consulta, **Then** es alto.
3. **Given** el bucle real con la política real y sin aprobador, **When** el modelo pide un comando, **Then** la política pregunta, se resuelve como denegada y ningún proceso se lanza.
4. **Given** una llamada sin `command`, con `command` vacío o no textual, o con campos extra, **When** la valida el registro, **Then** se rechaza antes de llegar a la herramienta.
5. **Given** que no hay área de trabajo configurada, **When** la herramienta llegara a ejecutarse, **Then** devuelve un error claro con la etiqueta `[sin_area]` y no lanza ningún proceso.

---

### User Story 6 - Las mismas pruebas pasan en Windows y en Linux (Priority: P1) [AC-04]

Como equipo de desarrollo, quiero que el mismo conjunto de pruebas del shell corra en la integración continua de Windows y de Linux, para detectar cuanto antes lo que difiere entre plataformas.

**Why this priority**: Es el criterio AC-04 y la decisión V-08. Las diferencias de plataforma solo se ven corriendo en ambas.

**Independent Test**: La CI existente (`ubuntu-latest` y `windows-latest`) ejecuta toda la suite del shell; la parte común usa la implementación nativa de cada sistema y no hay pruebas omitidas salvo las marcadas por plataforma, con motivo escrito.

**Acceptance Scenarios**:

1. **Given** el conjunto de pruebas del shell, **When** corre en Linux y en Windows, **Then** pasa en ambos sin cambios de código entre ellos.
2. **Given** una prueba que solo tiene sentido en una plataforma (por ejemplo la señal de terminación en POSIX o la instalación de PowerShell), **When** corre en la otra, **Then** se omite con un motivo explícito y existe su equivalente para la plataforma contraria.
3. **Given** la lógica que difiere por plataforma (construcción de la línea de comandos, terminación del árbol), **When** se prueba con la plataforma inyectada, **Then** corre en ambos sistemas con dobles, sin necesitar el otro intérprete.
4. **Given** que la CI remota solo se puede confirmar subiendo la rama, **When** se cierra la historia, **Then** queda anotado como pendiente humano hasta que corra en GitHub Actions.

---

### Edge Cases

- **Comando vacío o solo espacios**: lo rechaza el esquema; la implementación también lo trata como error claro.
- **Comando muy largo o con carácter nulo**: se rechaza por longitud máxima o se devuelve un error claro; nunca llega a la línea de comandos del sistema.
- **Código de salida negativo o muy grande**: se informa tal cual como entero; en POSIX una señal produce un código negativo.
- **Salida combinada**: la salida estándar y la de errores se entregan en un solo texto en el orden de llegada, sin garantizar el intercalado exacto.
- **Procesos que ignoran la terminación amable**: se escala a terminación forzada tras un período de gracia corto; no queda proceso vivo.
- **Proceso que termina justo al agotarse el plazo**: el resultado es coherente (no se informa «tiempo agotado» con un proceso ya terminado con éxito, ni se queda un proceso vivo).
- **Comando que cambia de carpeta o de variables**: no persiste entre llamadas; cada ejecución es independiente y parte de la carpeta del área.
- **Interrupción de la sesión (Ctrl-C) o cancelación de la llamada durante un comando**: el comando en curso y su árbol de procesos se terminan al cancelarse la llamada, sin esperar al tiempo máximo, sin dejar procesos huérfanos y sin bloquear la salida del programa.
- **Resultado y eventos**: las cargas de los eventos del bucle no llevan argumentos ni salida (FR-029 de HU-01-01); esta historia no cambia eso. El contenido de la salida es dato, no instrucción.
- **Variables de claves en el entorno**: `env`, `printenv` o `Get-ChildItem Env:` no muestran las claves de los proveedores del harness (se quitaron); otras variables sensibles que el usuario tenga sí aparecen si el comando se aprueba.
- **Secretos en la salida**: la salida del comando se entrega tal cual (puede contener lo que el usuario aprobó imprimir); esta historia no redacta secretos (PD-10 sigue abierta).
- **Nombres de intérprete y rutas del ejecutable**: no aparecen rutas absolutas del sistema del usuario en los mensajes de error al modelo.

## Requirements *(mandatory)*

### Functional Requirements

**Ejecución con tiempo máximo (Sp2-01)**

- **FR-001**: Las implementaciones MUST ejecutar el comando como un subproceso con la entrada estándar cerrada, la salida estándar y de errores combinadas, sin consola interactiva, y desde la carpeta que se les inyecta por constructor.
- **FR-002**: `execute(command, timeout_seconds)` MUST terminar el subproceso y todo su árbol de procesos cuando se agota el tiempo y MUST devolver `ShellResult(timed_out=True)` con la salida recogida hasta entonces, acotada.
- **FR-003**: La terminación MUST ser en dos pasos (petición amable, período de gracia corto y terminación forzada) y MUST NOT dejar procesos vivos del comando; MUST NOT lanzar si el proceso ya terminó.
- **FR-004**: `execute` MUST NOT lanzar excepciones por fallos previsibles (comando que no arranca, intérprete ausente, salida no decodificable): MUST devolver o señalar un resultado utilizable; los tipos de error de esta historia no dependen de bibliotecas de terceros.
- **FR-005**: El tiempo máximo MUST ser siempre finito: `execute` MUST rechazar un tiempo no positivo o no numérico, y la herramienta MUST aplicar un valor por defecto cuando el modelo no lo da y un tope fijo cuando pide más.
- **FR-006**: La implementación MUST NOT acumular en memoria más salida que el máximo documentado más un margen acotado, aunque el comando produzca salida ilimitada.

**Interfaz Shell por plataforma (Sp2-02)**

- **FR-007**: MUST existir una implementación de `Shell` para bash (`interpreter_name == "bash"`) y otra para PowerShell (`interpreter_name == "powershell"`), sin cambiar el puerto, y una función que elige la implementación según la plataforma (Windows → PowerShell; Linux → bash; otro → bash).
- **FR-008**: La plataforma MUST poder inyectarse para probar la elección y la construcción de la línea de comandos en cualquier sistema.
- **FR-009**: La implementación de PowerShell MUST ejecutar el comando sin cargar perfiles del usuario ni pedir confirmaciones, y MUST fijar la codificación de la salida a UTF-8; la de bash MUST ejecutar el comando sin cargar perfiles ni modo interactivo.
- **FR-010**: Si el ejecutable del intérprete no existe, la elección o la ejecución MUST fallar cerrado con un error claro y etiquetado; MUST NOT caer en otro intérprete ni en la ejecución directa sin shell.

- **FR-010b**: MUST existir, como datos de solo lectura, la lista de comandos denegados por defecto de cada plataforma (una para bash y otra para PowerShell), consultable por el nombre del intérprete; el shell y la herramienta MUST NOT aplicarla ni rechazar comandos por ella (la evalúa HU-05-02 en la política).

- **FR-010c**: El entorno del subproceso MUST ser una copia del entorno del harness sin las variables de claves de los proveedores; la lista de nombres a quitar MUST inyectarse por constructor (con la de los proveedores admitidos como valor por defecto) y MUST aplicarse sin distinguir mayúsculas en Windows. MUST NOT quitarse nada más.

**Prefijo con sistema operativo e intérprete (Sp2-03)**

- **FR-011**: MUST existir una función pura que, dados el nombre del sistema operativo y el del intérprete, devuelve el texto en español que se entrega al modelo, estable (misma entrada, misma salida) y sin datos de la máquina.
- **FR-012**: `bootstrap.py` MUST colocar ese texto como primer mensaje de sistema del historial de la sesión, usando el nombre del intérprete de la implementación elegida; MUST NOT cambiar el bucle, los puertos ni la política.

**Salida acotada y marcada (Sp2-04)**

- **FR-013**: Una salida que supera el máximo documentado MUST recortarse conservando el principio y el final, y MUST llevar un aviso con la cantidad de caracteres omitidos; una salida dentro del máximo MUST llegar sin aviso.
- **FR-014**: El texto de la salida MUST decodificarse en UTF-8 con sustitución de los bytes inválidos, sin lanzar.

**Herramienta `shell` (Sp2-01, Sp2-02)**

- **FR-015**: MUST existir `ShellTool` que implemente el puerto `Tool`: nombre `shell`, descripción para el modelo (indica el intérprete y que cada llamada es independiente), esquema con `command` (texto, longitud mínima 1 y máxima fija) y `timeout_seconds` (número opcional mayor que 0), `additionalProperties` falso, y riesgo alto.
- **FR-016**: La herramienta MUST recibir por constructor el `Shell` y el área (o `None`); MUST NOT leer configuración, entorno ni terminal.
- **FR-017**: Sin área (`None`), la herramienta MUST devolver un error claro con la etiqueta `[sin_area]` y MUST NOT lanzar ningún proceso.
- **FR-018**: La herramienta MUST ejecutar el `Shell` fuera del bucle de eventos (el puerto es síncrono) y MUST devolver siempre un `ToolResult`; si la llamada se cancela mientras el comando corre, MUST invocar el gancho de cancelación que se le inyecta (que termina el comando en curso) y MUST dejar propagar la cancelación. Resultados: éxito con la salida y el código 0; con `is_error=True` y etiqueta para código distinto de 0, tiempo agotado, intérprete no disponible y falta de área.
- **FR-019**: El contenido devuelto al modelo MUST incluir el código de salida y la salida acotada, y MUST NOT incluir trazas, rutas absolutas del ejecutable ni el comando completo repetido.

**Calidad y fronteras (Sp2-05)**

- **FR-020**: `core/`, el bucle, los puertos, el catálogo de eventos, la política, el registro, la CLI, la configuración y los dobles existentes MUST NOT modificarse; solo se añaden archivos, el cableado en `bootstrap.py` y la documentación. Desviación aceptada al implementar (2026-10-25): `bootstrap.py` no puede leer `os.environ` (lo prohíbe su guarda), así que se añade a `config.py` la función aditiva `process_environment()` y se ajustan solo 4 aserciones de pruebas existentes que fijaban el historial vacío o la lista de herramientas.
- **FR-021**: La guarda de arquitectura de `adapters/` MUST seguir en verde: las piezas nuevas de `adapters/system/` y `adapters/tools/` usan solo biblioteca estándar y la API pública de `harness_agent.core`, sin `config`, `cli` ni terceros, y sin `print` ni `input`.
- **FR-022**: MUST existir una batería de contrato común que corre contra ambas implementaciones (la nativa del sistema en cada ejecución y la otra con dobles) y verifica el mismo `ShellResult` para los casos comunes.
- **FR-023**: MUST existir pruebas con procesos reales que corran en Linux y en Windows sin cambios (éxito, código de salida, salida combinada, no ASCII, tiempo agotado, árbol de procesos, salida enorme), y pruebas marcadas por plataforma, con motivo escrito, para lo exclusivo de una.
- **FR-024**: MUST existir pruebas de integración con el bucle real, la política real, el registro real y un `FakeProvider` o `ScriptedProvider`: el shell se pregunta y se deniega sin aprobador (ningún proceso), y, con una política de prueba que permita la herramienta, se ejecuta de extremo a extremo y el resultado vuelve al modelo.
- **FR-025**: Las pruebas MUST NOT usar red, claves ni el repositorio como carpeta de trabajo de los comandos (carpetas temporales), y MUST NOT dejar procesos vivos al terminar.
- **FR-026**: `ruff format --check`, `ruff check`, `mypy src tests` y `pytest` MUST pasar y los módulos nuevos MUST tener 100 % de cobertura de líneas y ramas salvo las ramas exclusivas de una plataforma, que se cubren con las pruebas con plataforma inyectada y las marcadas por plataforma.
- **FR-027**: Al cerrar, `docs/PROGRESO.md` MUST reflejar la historia (estado «En revisión», archivos, evidencia y observaciones para HU-05-02, HU-05-03, HU-02-01, HU-02-02, HU-11-03 y B por la ampliación futura de `config.py`) según el Principio VIII, y las skills y `arbol.md` MUST actualizarse si cambian (en `.claude/skills/` y `.agents/skills/`).

### Key Entities

- **Shell**: puerto existente; una implementación por intérprete; ejecuta un comando con tiempo máximo y devuelve un `ShellResult`.
- **ShellResult**: código de salida, salida de texto y marca de tiempo agotado (existente, sin cambios).
- **Intérprete**: bash o PowerShell; identifica a la implementación y se nombra al modelo.
- **Texto de entorno (prefijo)**: mensaje de sistema estable con el sistema operativo y el intérprete.
- **Árbol de procesos**: el proceso del comando y todo lo que lanza; se termina entero al agotarse el tiempo.
- **Salida acotada**: texto con principio y final, y un aviso de lo omitido.
- **Límites**: tiempo por defecto, tiempo máximo, máximo de caracteres de salida, longitud máxima del comando y período de gracia (constantes documentadas en el plan).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de las pruebas de tiempo agotado (al menos un comando simple, uno con proceso hijo y uno que ignora la terminación amable, en cada plataforma), el control vuelve en menos de la suma del tiempo máximo y 3 segundos, y ningún proceso del comando queda vivo.
- **SC-002**: Un comando que produce más de 100 MB de salida no hace crecer el uso de memoria del harness más allá del máximo documentado más un margen fijo, y la salida devuelta por el shell nunca supera el máximo de caracteres (el resultado de la herramienta añade solo un encabezado corto de código de salida).
- **SC-003**: Con el bucle real, la política real y sin aprobador, el 100 % de las llamadas a `shell` se resuelven como denegadas y no lanzan ningún proceso.
- **SC-004**: La herramienta devuelve un resultado estructurado, no una excepción, en el 100 % de los casos de error probados (código distinto de 0, tiempo agotado, intérprete ausente, sin área, comando que no arranca, salida no UTF-8).
- **SC-005**: El mismo conjunto de pruebas de shell pasa en Linux y en Windows con el mismo código; las únicas omisiones son las marcadas por plataforma, con motivo, y cada una tiene su equivalente en la otra.
- **SC-006**: El texto de entorno es idéntico en dos construcciones consecutivas con los mismos datos y el historial inicial lo lleva como primer mensaje de sistema en el 100 % de los arranques de prueba.
- **SC-007**: 0 pruebas existentes modificadas y 0 en rojo; la suite completa pasa; los módulos nuevos tienen 100 % de cobertura de líneas y ramas (salvo lo exclusivo de plataforma), y `ruff`, `mypy --strict` y `pytest` terminan con código 0.

## Assumptions

- **HU-00-01 sigue pendiente de aprobación técnica.** Esta historia no cambia ningún puerto, el bucle, el catálogo de eventos ni los dobles, así que puede implementarse sin esa ratificación, pero debe producirse antes de pasar a «Hecha».
- **Sin aprobador, el shell no ejecuta nada.** La política vigente pregunta ante riesgo alto y el bucle resuelve «pregunta» como denegado hasta HU-05-03. La historia se prueba de extremo a extremo con una política de prueba que permite la herramienta; el uso real interactivo llega con HU-05-02 y HU-05-03.
- **El puerto `Shell` es síncrono y no cambia.** La herramienta lo ejecuta en un hilo. Como el puerto no tiene cancelación, la implementación concreta ofrece un método propio (`terminate_running`) que la raíz de composición inyecta a la herramienta como gancho de cancelación: así la cancelación de la llamada (o Ctrl-C) termina el comando en curso. Cancelar solo un turno, sin cancelar la llamada, no existe todavía; en cualquier caso el tiempo máximo acota la vida del proceso. Cualquier ampliación del puerto (cancelación en el contrato, carpeta de trabajo, entorno) requiere el acuerdo de A, B y C y queda como hallazgo.
- **Intérpretes**: PowerShell de Windows es `powershell.exe` (siempre presente) y, si existe, se prefiere `pwsh`; bash es `bash` del `PATH`. macOS no es plataforma del equipo ni de la CI; solo se garantiza que usa bash.
- **El área solo fija la carpeta inicial**; no confina el comando. La confianza viene de la aprobación, no del área.
- **La lista de comandos denegados por plataforma** (regla de negocio 3) se publica aquí como dato (FR-010b) y su evaluación, igual que el análisis de comandos compuestos, pertenece a la política (HU-05-02). La lista inicial es conservadora y de revisión por el PO; no sustituye a la aprobación obligatoria.
- **`config.py` no se amplía** (tiempos y lista de denegados del shell se anotaron en PROGRESO como ampliación futura de B): los límites son constantes documentadas de esta historia y el constructor los admite por parámetro para las pruebas.
- **El recorte es provisional**: se alinea con los 20 000 caracteres de las herramientas de archivos hasta que HU-02-02 defina el recorte general en el registro; HU-02-02 podrá sustituirlo sin cambiar el contrato de la herramienta.
- **El prefijo es provisional**: hasta HU-02-01 (ensamblador de contexto, área B) es un mensaje de sistema colocado por la raíz de composición; HU-02-01 lo recogerá.
- **Entorno de pruebas**: las pruebas con procesos reales usan comandos que existen en ambos intérpretes (`echo`, `exit`, `sleep`) o el propio intérprete de Python (`sys.executable`) para no depender de utilidades externas.
- **Nombres en inglés** para clases, métodos y atributos; los textos de usuario, mensajes de error, el prefijo para el modelo y la documentación van en español.
- Estimación: las tareas Sp2-01 a Sp2-05 suman 10,5 h (630 min); es solo referencia, no una restricción.
