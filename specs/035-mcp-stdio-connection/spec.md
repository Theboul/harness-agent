# Especificación: HU-08-01 — Conexión a un servidor MCP por stdio

**Rama**: `claude/hu-08-01-mcp-client-cbf065` · **Responsable**: C — Control y conexiones · **Sprint**: 4 (el orden por sprints ya no rige: ver *Supuestos*) · **PHU**: 2  
**Requisitos**: RF-8.1 · **Depende de**: [SPK-04](../../docs/04d-historias-conexiones.md#spk-04) · **Ficha**: [HU-08-01](../../docs/04d-historias-conexiones.md#hu-08-01)  
**Tareas del plan**: Sp4-28 (3 h → 4 h según SPK-04), Sp4-29 (1,5 h)  
**Numeración**: `035` (la `033` la ocupa la rama de consola `claude/cli-console-ux-ea1667` y la `034` la de reintentos, HU-07-04)

## Clarificaciones

### Sesión 2026-10-30

Decisiones tomadas por el usuario a partir de las recomendaciones de [SPK-04](../../docs/decisiones/SPK-04-cliente-mcp-stdio.md); no se reabren.

- Q: ¿Se cambia el puerto `McpClient` (H1)? → A: **no**. El puerto está protegido y cambiarlo exige acuerdo de A, B y C. El adaptador encapsula el ciclo de vida del SDK con una **tarea de fondo dueña de la conexión** que vive hasta una señal de cierre; `connect()` espera a que la conexión esté lista.
- Q: ¿Cómo se tratan los fallos del SDK (llegan como `ExceptionGroup`)? → A: el adaptador los **aplana** y los traduce a un error de dominio con un mensaje fijo que no reproduce datos del servidor ni de la configuración.
- Q: ¿Los errores de una llamada son excepciones? → A: no; llegan como `ToolResult(is_error=True)`. El texto de «argumentos inválidos» del SDK reproduce el valor recibido: el adaptador **no lo pasa tal cual**. (La traducción de herramientas y de resultados completa es HU-08-02/03; aquí solo se deja la costura y se garantiza que `call_tool` nunca filtra ese texto.)
- Q: ¿Un servidor que no arranca impide iniciar el arnés? → A: no. El arnés arranca; ese servidor queda sin herramientas y se avisa en español.
- Q: ¿Adónde va el stderr del servidor hijo? → A: no al terminal de la persona (a un archivo de registro dentro de la carpeta de datos del arnés, o al dispositivo nulo si no hay dónde escribir).
- Q: ¿El servidor hijo hereda el entorno del proceso padre? → A: **no**. Recibe solo el entorno mínimo necesario para ejecutarse más las variables que la configuración nombre; las claves de API del padre nunca llegan (H5).
- Q: ¿Qué tiempos se usan? → A: configurables; valores propuestos en SPK-04: negociación 15 s, llamada 60 s.
- Q: ¿Quién emite el aviso de un servidor que no arranca? → A: la composición, por el mismo canal de avisos que ya usa `bootstrap.py` (`WarningSink`); el núcleo no imprime y no se añade ningún evento (H6).
- Q: ¿Cómo se pasa el entorno al servidor? → A: `env` de la configuración es una lista de **nombres** de variables del padre que sí se pasan (no valores: sin secretos en el archivo); un nombre con aspecto de clave de API solo se admite si se nombra expresamente allí. Se añade siempre la base mínima de cada sistema (`PATH`, `SystemRoot`, `HOME`…), igual que el entorno del shell.
- Q: ¿Qué ocurre con la sesión si el servidor cae después de conectar? → A: queda fuera (HU-08-04); aquí solo se garantiza que una llamada a un servidor caído devuelve un `ToolResult` de error y que el cierre sigue siendo limpio.

## Historia

Como usuario operador quiero conectar el agente a un servidor MCP local por stdio para usar herramientas de servicios externos.

## Escenarios

1. **Conexión por stdio (AC-01).** Dado un servidor configurado, cuando arranca la sesión, entonces el cliente lo inicia como subproceso, negocia capacidades y queda conectado.
2. **Un servidor que no arranca no impide iniciar la sesión (regla 1).** Dado un servidor cuyo comando no existe, que sale al arrancar o que no responde a la negociación, cuando arranca la sesión, entonces el arnés inicia igualmente, ese servidor queda sin herramientas y la persona ve un aviso en español.
3. **Cierre limpio.** Dado un servidor conectado, cuando termina la sesión (o se cancela), entonces la conexión se cierra, el proceso del servidor termina y no queda ningún proceso huérfano.
4. **Sin servidores configurados.** Dado que la configuración no declara servidores MCP, cuando arranca la sesión, entonces el arnés se comporta exactamente como hoy y no se carga el SDK de MCP.
5. **Entorno aislado.** Dado un servidor configurado y claves de API en el entorno del proceso padre, cuando el servidor arranca, entonces no puede ver esas claves; solo ve lo que la configuración le entrega de forma explícita.

## Requisitos funcionales

- **FR-001**: El adaptador MUST iniciar el servidor configurado como subproceso por stdio, negociar capacidades y quedar conectado, expuesto por el puerto `McpClient` sin cambiarlo (AC-01).
- **FR-002**: Una **tarea de fondo** MUST ser la dueña de la conexión (abrirla y cerrarla en la misma tarea); `connect()` MUST esperar a que la conexión esté lista o a que falle, y MUST devolver el control con un error de dominio si falla.
- **FR-003**: El cierre (señal + espera de la tarea) MUST ser limpio y MUST terminar el proceso del servidor, también cuando la tarea que llama se cancela; nunca MUST quedar un proceso huérfano.
- **FR-004**: Los fallos de arranque y de negociación (comando inexistente, salida inmediata, falta de respuesta dentro del tiempo, `ExceptionGroup` del SDK) MUST aplanarse y traducirse a un único error de dominio cuyo mensaje es fijo y no reproduce argumentos, entorno, rutas ni texto del servidor.
- **FR-005**: El arranque del arnés MUST tolerar que un servidor falle: la composición MUST seguir adelante, avisar en español con el nombre configurado del servidor y dejarlo sin herramientas.
- **FR-006**: El stderr del servidor MUST NOT escribirse en el terminal de la persona.
- **FR-007**: El entorno del subproceso MUST construirse de forma explícita: base mínima para ejecutar + variables nombradas por la configuración; MUST NOT heredar las claves de API ni el resto del entorno del padre.
- **FR-008**: La configuración MUST admitir una sección de servidores MCP (nombre, `command`, `args`, entorno explícito, `startup_timeout_s`, `call_timeout_s`); MUST rechazar campos desconocidos y campos con aspecto de clave, y MUST NOT admitir secretos en el archivo. Sin la sección, el comportamiento es el actual.
- **FR-009**: El tiempo de espera de la negociación MUST ser configurable (15 s por defecto) y el de cada llamada también (60 s por defecto).
- **FR-010**: `call_tool` MUST devolver los errores como `ToolResult` con `is_error=True` (incluidos tiempo agotado y caída del servidor) y MUST NOT incluir en su texto valores recibidos como argumentos ni texto libre del servidor.
- **FR-011**: `core/` MUST NOT importar `mcp`; el SDK se carga con `importlib` solo dentro de `adapters/mcp/`, y su ausencia produce un error claro con el comando de instalación del extra.
- **FR-012**: La dependencia `mcp` MUST declararse en un extra propio de `pyproject.toml` y MUST seguir fijada en `requirements-dev.txt` con la misma versión; `dependencies` sigue vacío.
- **FR-013**: No MUST cambiar `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/` ni `docs/archivo/`. No MUST implementarse el descubrimiento ni la traducción de herramientas (HU-08-02), los permisos (HU-08-03) ni el aislamiento de fallos entre servidores (HU-08-04).
- **FR-014**: Cada servidor MUST tener su propia conexión y su propio ciclo de vida, de modo que HU-08-04 y HU-08-05 puedan añadir aislamiento y varios servidores sin rehacer este adaptador.

## Criterios de éxito

- **SC-001**: Con el servidor de demostración local, una ejecución de `pytest` sin red ni claves inicia el servidor, negocia capacidades y deja la conexión lista en el tiempo de espera configurado.
- **SC-002**: Tras cerrar (o cancelar) la conexión, el proceso del servidor deja de existir en menos de 10 s, en Windows y Linux.
- **SC-003**: Con un servidor roto (comando inexistente, salida inmediata, sin respuesta), el arnés inicia y la persona ve exactamente un aviso en español por servidor fallido; ningún texto del aviso reproduce el centinela de datos de la configuración.
- **SC-004**: Una variable de clave de API del proceso padre no es visible para el servidor hijo (comprobado con la herramienta del servidor de demostración que informa del entorno).
- **SC-005**: Sin servidores configurados, el arnés arranca sin importar el SDK de MCP.

## Fuera de alcance

Descubrir y traducir herramientas al registro (HU-08-02), permisos y limpieza de resultados MCP (HU-08-03), aislar fallos y deshabilitar solo las herramientas de un servidor caído (HU-08-04), varios servidores con prefijos (HU-08-05), reconexión automática, transportes distintos de stdio (HU-08-06), recursos, prompts y muestreo, ampliar `check_schema`, y promover el servidor de demostración fuera de `tests/spikes/` (T013 de SPK-04, visto bueno del PO).

## Supuestos

- El SDK fijado es `mcp==2.3.0` (API 2.x). SPK-04 midió el arranque en 1,3–2,0 s en Windows; no se ha probado en Linux (lo cubre la CI al fusionar).
- **Decisión del usuario (2026-10-30):** el orden por sprints deja de regir; el cierre del proyecto se adelantó al 6 de noviembre de 2026 y se trabaja por carriles de archivos. Por eso se implementa HU-08-01 aunque figure en el Sprint 4.
- El servidor de las pruebas es `tests/spikes/mcp_demo_server.py`, sin modificarlo.
- El puerto `McpClient` solo ofrece `connect`, `list_tools` y `call_tool`. El cierre no está en el puerto: lo ofrece la clase concreta del adaptador (método propio) y la composición lo invoca al terminar. Si A, B y C prefieren `close()` en el puerto (alternativa b de H1), es un cambio aditivo posterior.
- `list_tools()` de este adaptador queda como costura: devuelve una lista vacía hasta que HU-08-02 lo implemente (el puerto exige `Tool`, y traducir es de esa historia). `call_tool` sí se implementa de forma mínima y segura (FR-010) porque el puerto lo exige y HU-08-03 lo necesitará.
