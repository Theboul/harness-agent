# Historias: proveedores, MCP, subagentes, trazas e innovación (E7 a E10, EI)

> [← 04c-historias-control.md](04c-historias-control.md) · [Índice](00-indice.md) · [04e-historias-coding-harness.md →](04e-historias-coding-harness.md)  
> Sección 10 del contexto original, continuación: épicas E7, E8, E9, E10 y EI (incluye SPK-01 y SPK-04).  
> Ver también: [02-arquitectura.md](02-arquitectura.md) · [03-plan-sprints.md](03-plan-sprints.md) · [PROGRESO.md](PROGRESO.md)
>
> El estado de cada historia vive solo en [PROGRESO.md](PROGRESO.md); aquí no se repite.

### E7. Proveedores de modelo

<a id="hu-07-01"></a>
#### HU-07-01 — Interfaz Provider y formato interno de mensajes

**Prioridad:** Alta · **PHU:** 3 · **Sprint:** Sprint 1 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-7.1, RF-7.2, RNF-12 · **Depende de:** [HU-00-01](04a-historias-fundacion.md#hu-00-01), [SPK-01](04d-historias-conexiones.md#spk-01)

- **Como:** equipo de desarrollo
- **Quiero:** una interfaz Provider y un formato interno único de mensajes y herramientas
- **Para:** que el bucle no dependa de ningún proveedor
- **Descripción:** El núcleo define una interfaz Provider y un formato interno único de mensajes y herramientas, para no depender de ningún proveedor.

**Flujo general**

1. Se define el formato interno con roles y bloques.
2. El adaptador convierte del formato interno al del proveedor y de vuelta.
3. El bucle solo conoce el formato interno.

**Reglas de negocio**

1. La conversión no pierde información.
2. El bucle no cambia al cambiar de proveedor.

**Criterios de aceptación**

- **AC-01 — Conversión sin pérdida.** Dado el formato interno, cuando se convierte a la entrada de un proveedor y de vuelta, entonces no se pierde información.
- **AC-02 — Bucle independiente del proveedor.** Dado el bucle, cuando se cambia de proveedor, entonces no se modifica ninguna línea del bucle.

<a id="hu-07-02"></a>
#### HU-07-02 — Adaptador LiteLLM para el primer proveedor

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 1 · **Desarrollador:** B — Estado  
**Requisitos:** RF-7.3, RF-7.6 · **Depende de:** [HU-07-01](04d-historias-conexiones.md#hu-07-01), [HU-00-04](04a-historias-fundacion.md#hu-00-04)

- **Como:** usuario operador
- **Quiero:** conectar el sistema a un primer modelo real
- **Para:** ejecutar tareas reales
- **Descripción:** El sistema se conecta a un primer modelo real mediante LiteLLM para ejecutar tareas reales.

**Flujo general**

1. El usuario configura la clave en el entorno.
2. El adaptador llama al modelo mediante LiteLLM.
3. El modelo responde y puede solicitar herramientas.

**Reglas de negocio**

1. LiteLLM solo se usa dentro del adaptador.

**Criterios de aceptación**

- **AC-01 — Respuesta real del modelo.** Dado una clave válida en el entorno, cuando se plantea una tarea, entonces el modelo real responde y puede solicitar herramientas.

<a id="hu-07-03"></a>
#### HU-07-03 — Segundo proveedor y selección por configuración

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 2 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-7.3, RNF-21 · **Depende de:** [HU-07-02](04d-historias-conexiones.md#hu-07-02)

- **Como:** usuario operador
- **Quiero:** usar otro proveedor cambiando la configuración
- **Para:** no depender de uno solo
- **Descripción:** El usuario cambia de proveedor modificando la configuración, sin cambios en el bucle.

**Flujo general**

1. El usuario edita la configuración.
2. El sistema arranca con el segundo proveedor.
3. El bucle funciona igual con los mismos resultados de herramienta.

**Reglas de negocio**

1. Ambos proveedores devuelven resultados de herramienta en el mismo formato interno.

**Criterios de aceptación**

- **AC-01 — Segundo proveedor por configuración.** Dado una configuración con el segundo proveedor, cuando arranca, entonces el bucle funciona sin cambios y con los mismos resultados de herramienta.

<a id="hu-07-04"></a>
#### HU-07-04 — Reintentos con espera exponencial

**Prioridad:** Media · **PHU:** 1 · **Sprint:** Sprint 3 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-7.5, RNF-6 · **Depende de:** [HU-07-02](04d-historias-conexiones.md#hu-07-02)

- **Como:** usuario operador
- **Quiero:** que ante un error temporal el sistema reintente antes de rendirse
- **Para:** no perder la sesión por un fallo pasajero
- **Descripción:** Ante un error temporal, el sistema reintenta con esperas crecientes antes de rendirse.

**Flujo general**

1. El proveedor devuelve un error de límite de tasa.
2. El sistema espera y reintenta con esperas crecientes.
3. Cada intento se registra.

**Reglas de negocio**

1. Solo se reintentan errores temporales.
2. El número de reintentos es limitado.

**Criterios de aceptación**

- **AC-01 — Reintentos con espera exponencial.** Dado un error de límite de tasa, cuando ocurre, entonces el sistema reintenta con esperas crecientes y registra cada intento.

<a id="hu-07-05"></a>
#### HU-07-05 — Conmutación por fallo con umbral por modelo

**Prioridad:** Alta · **PHU:** 3 · **Sprint:** Sprint 3 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-7.4, RNF-6 · **Depende de:** [HU-07-03](04d-historias-conexiones.md#hu-07-03), [HU-07-04](04d-historias-conexiones.md#hu-07-04)

- **Como:** usuario operador
- **Quiero:** que si un proveedor se queda sin cuota el sistema continúe con el otro
- **Para:** no interrumpir mi trabajo
- **Descripción:** Si un proveedor agota su cuota, el sistema continúa con el de respaldo y recalcula el umbral de compactación.

**Flujo general**

1. Se agotan los reintentos con error de cuota.
2. El sistema cambia al proveedor de respaldo.
3. Repite el turno.
4. Recalcula el umbral de compactación para el nuevo modelo.
5. Registra el cambio en la traza.

**Reglas de negocio**

1. El cambio es automático y queda visible para el usuario.

**Criterios de aceptación**

- **AC-01 — Conmutación por fallo.** Dado un error de cuota tras agotar los reintentos, cuando ocurre, entonces el sistema cambia al respaldo, repite el turno y lo registra en la traza.
- **AC-02 — Umbral propio del nuevo modelo.** Dado el cambio de modelo, cuando se evalúa la compactación, entonces se usa el umbral propio de la ventana del nuevo modelo.

<a id="hu-07-06"></a>
#### HU-07-06 — Respuesta en streaming

**Prioridad:** Baja · **PHU:** 2 · **Sprint:** Backlog · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-7.7 · **Depende de:** [HU-07-02](04d-historias-conexiones.md#hu-07-02)

- **Como:** usuario operador
- **Quiero:** ver la respuesta del modelo mientras se genera
- **Para:** percibir el sistema más ágil
- **Descripción:** El usuario ve la respuesta del modelo mientras se genera.

**Flujo general**

1. El proveedor emite fragmentos.
2. El núcleo emite eventos de fragmento.
3. La CLI los muestra progresivamente.

**Reglas de negocio**

1. El streaming no cambia el resultado final guardado.

**Criterios de aceptación**

- **AC-01 — Respuesta progresiva.** Dado una respuesta larga, cuando se genera, entonces la terminal la muestra de forma progresiva.

<a id="spk-01"></a>
#### SPK-01 — Spike: traducir herramientas entre OpenAI y Anthropic con LiteLLM

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 1 · **Desarrollador:** B — Estado  
**Requisitos:** RF-7.1, RF-7.3 · **Depende de:** ninguna

- **Como:** equipo de desarrollo
- **Quiero:** probar durante medio día una misma herramienta en ambos proveedores
- **Para:** diseñar el formato interno sabiendo qué difiere
- **Descripción:** Spike de medio día: enviar una misma herramienta a OpenAI y a Anthropic con LiteLLM y documentar qué difiere, para diseñar el formato interno.

**Flujo general**

1. Se define una herramienta de prueba.
2. Se envía a ambos proveedores.
3. Se comparan las llamadas y los resultados.
4. Se documentan las diferencias.

**Reglas de negocio**

1. El resultado alimenta [HU-07-01](04d-historias-conexiones.md#hu-07-01).

**Criterios de aceptación**

- **AC-01 — Equivalencia entre proveedores documentada.** Dado un mismo esquema de herramienta, cuando se envía a ambos proveedores mediante LiteLLM, entonces se obtienen llamadas equivalentes y se documentan las diferencias de identificadores y de resultados.

### E8. Integración MCP

<a id="spk-04"></a>
#### SPK-04 — Spike: cliente MCP por stdio y servidor de demostración

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 2 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-8.1 · **Depende de:** ninguna

- **Como:** equipo de desarrollo
- **Quiero:** probar durante medio día un servidor MCP por stdio y elegir el de la demostración
- **Para:** estimar con seguridad las historias de MCP
- **Descripción:** Spike de medio día: probar un cliente MCP por stdio con un servidor local sin credenciales y elegir el servidor de la demostración.

**Flujo general**

1. Se instala el SDK de MCP.
2. Se inicia un servidor de referencia por stdio.
3. Se negocian capacidades y se lista una herramienta.
4. Se documenta el servidor elegido.

**Reglas de negocio**

1. El servidor de demostración es local y sin credenciales.

**Criterios de aceptación**

- **AC-01 — Servidor de referencia conectado.** Dado un servidor de referencia sin credenciales, cuando se inicia desde el cliente de prueba, entonces se negocian capacidades y se lista al menos una herramienta.

<a id="hu-08-01"></a>
#### HU-08-01 — Conexión a un servidor MCP por stdio

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-8.1 · **Depende de:** [SPK-04](04d-historias-conexiones.md#spk-04)

- **Como:** usuario operador
- **Quiero:** conectar el agente a un servidor MCP local
- **Para:** usar herramientas de servicios externos
- **Descripción:** El agente se conecta a un servidor MCP local por stdio para usar herramientas de servicios externos.

**Flujo general**

1. Al iniciar la sesión, el cliente lee la configuración.
2. Inicia el servidor como subproceso.
3. Negocia capacidades y queda conectado.

**Reglas de negocio**

1. Un servidor que no arranca no impide iniciar la sesión.

**Criterios de aceptación**

- **AC-01 — Conexión por stdio.** Dado un servidor configurado, cuando arranca la sesión, entonces el cliente lo inicia, negocia capacidades y queda conectado.

<a id="hu-08-02"></a>
#### HU-08-02 — Descubrir herramientas MCP y traducirlas al formato interno

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-8.2 · **Depende de:** [HU-08-01](04d-historias-conexiones.md#hu-08-01), [HU-01-02](04a-historias-fundacion.md#hu-01-02)

- **Como:** agente principal
- **Quiero:** ver las herramientas del servidor como si fueran nativas
- **Para:** usarlas con el mismo mecanismo
- **Descripción:** Las herramientas del servidor MCP aparecen en el registro como si fueran nativas.

**Flujo general**

1. El cliente lista las herramientas del servidor.
2. Traduce cada una a Tool con nombre, descripción y esquema.
3. Las registra en el ToolRegistry.

**Reglas de negocio**

1. Una herramienta MCP se usa con el mismo mecanismo que una nativa.

**Criterios de aceptación**

- **AC-01 — Herramientas MCP en el registro.** Dado un servidor conectado, cuando se listan sus herramientas, entonces aparecen en el registro con su nombre, descripción y esquema.

<a id="hu-08-03"></a>
#### HU-08-03 — Invocar herramientas MCP bajo la misma política de permisos

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-8.3, RF-8.4 · **Depende de:** [HU-08-02](04d-historias-conexiones.md#hu-08-02), [HU-05-01](04c-historias-control.md#hu-05-01)

- **Como:** usuario operador
- **Quiero:** que las herramientas remotas pasen por los mismos controles que las nativas
- **Para:** que conectar un servidor no abra un hueco de seguridad
- **Descripción:** Las herramientas MCP pasan por la misma política de permisos que las nativas, para que conectar un servidor no abra un hueco de seguridad.

**Flujo general**

1. El modelo invoca una herramienta MCP.
2. La política la evalúa.
3. Si requiere permiso, se pide aprobación.
4. Se ejecuta en el servidor y el resultado vuelve marcado como dato externo.

**Reglas de negocio**

1. Toda herramienta MCP se trata como acción que requiere permiso salvo regla en contra.

**Criterios de aceptación**

- **AC-01 — Aprobación de herramienta MCP.** Dado una herramienta MCP clasificada como que requiere permiso, cuando el modelo la invoca, entonces se pide aprobación y su resultado vuelve al bucle.

<a id="hu-08-04"></a>
#### HU-08-04 — Aislar los fallos de un servidor MCP

**Prioridad:** Media · **PHU:** 1 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-8.5, RNF-8 · **Depende de:** [HU-08-01](04d-historias-conexiones.md#hu-08-01)

- **Como:** usuario operador
- **Quiero:** que la caída de un servidor solo afecte a sus herramientas
- **Para:** que la sesión no se rompa
- **Descripción:** La caída de un servidor MCP solo afecta a sus herramientas.

**Flujo general**

1. Un servidor se cae a mitad de sesión.
2. El modelo invoca una de sus herramientas.
3. Recibe un error.
4. El resto de las herramientas sigue funcionando.

**Reglas de negocio**

1. Una falla MCP nunca termina la sesión.

**Criterios de aceptación**

- **AC-01 — Fallo aislado del servidor.** Dado un servidor que se cae a mitad de sesión, cuando el modelo invoca su herramienta, entonces recibe un error y el resto de las herramientas siguen funcionando.

<a id="hu-08-05"></a>
#### HU-08-05 — Varios servidores por archivo y prefijos para evitar colisiones

**Prioridad:** Media · **PHU:** 3 · **Sprint:** Backlog · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-8.6, RF-8.7 · **Depende de:** [HU-08-02](04d-historias-conexiones.md#hu-08-02)

- **Como:** usuario operador
- **Quiero:** configurar varios servidores en un archivo
- **Para:** usar más de un servicio a la vez
- **Descripción:** El usuario configura varios servidores en un archivo y sus herramientas llevan el prefijo del servidor para evitar colisiones.

**Flujo general**

1. El usuario lista varios servidores en la configuración.
2. El cliente los conecta.
3. Registra cada herramienta con el prefijo de su servidor.

**Reglas de negocio**

1. Dos herramientas con el mismo nombre nunca se pisan.

**Criterios de aceptación**

- **AC-01 — Prefijos por servidor.** Dado dos servidores con una herramienta del mismo nombre, cuando se registran, entonces cada una lleva el prefijo de su servidor.

<a id="hu-08-06"></a>
#### HU-08-06 — Transporte HTTP además de stdio

**Prioridad:** Baja · **PHU:** 2 · **Sprint:** Backlog · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-8.8 · **Depende de:** [HU-08-01](04d-historias-conexiones.md#hu-08-01)

- **Como:** usuario operador
- **Quiero:** conectar servidores MCP remotos por HTTP
- **Para:** usar servicios que no corren en mi máquina
- **Descripción:** El usuario conecta servidores MCP remotos por HTTP.

**Flujo general**

1. El usuario configura una URL.
2. El cliente se conecta por HTTP.
3. Lista las herramientas del servidor.

**Reglas de negocio**

1. La autenticación se define al implementarla.

**Criterios de aceptación**

- **AC-01 — Conexión por HTTP.** Dado un servidor remoto configurado por URL, cuando arranca la sesión, entonces se conecta y lista sus herramientas.

### E9. Subagentes (reto)

<a id="hu-09-01"></a>
#### HU-09-01 — Delegar en un subagente con contexto limpio

**Prioridad:** Alta · **PHU:** 5 · **Sprint:** Sprint 2 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-9.1, RF-9.2 · **Depende de:** [HU-01-01](04a-historias-fundacion.md#hu-01-01), [HU-03-01](04b-historias-estado.md#hu-03-01), [HU-01-05](04a-historias-fundacion.md#hu-01-05)

- **Como:** agente principal
- **Quiero:** lanzar un subagente mediante una herramienta de delegación
- **Para:** proteger mi ventana de contexto en tareas pesadas
- **Descripción:** El agente principal delega una subtarea en un subagente que corre en una sesión hija con contexto vacío, protegiendo su propia ventana de contexto.

**Flujo general**

1. El orquestador invoca la herramienta de delegación con objetivo, contexto mínimo y formato de salida.
2. El harness crea la sesión hija.
3. El subagente ejecuta su propio bucle.
4. Devuelve su resultado al orquestador.

**Reglas de negocio**

1. El subagente solo recibe lo que el orquestador le pasa.
2. La sesión hija se guarda con el identificador de su padre.

**Criterios de aceptación**

- **AC-01 — Sesión hija con contexto vacío.** Dado una subtarea, cuando el orquestador delega, entonces se crea una sesión hija con contexto vacío que solo contiene la tarea recibida.
- **AC-02 — Sin historial del orquestador.** Dado el subagente en ejecución, cuando se revisa su contexto, entonces no contiene el historial del orquestador.

<a id="hu-09-02"></a>
#### HU-09-02 — Instrucciones propias y herramientas restringidas por subagente

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 2 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-9.3 · **Depende de:** [HU-09-01](04d-historias-conexiones.md#hu-09-01), [HU-01-02](04a-historias-fundacion.md#hu-01-02)

- **Como:** usuario operador
- **Quiero:** que cada subagente tenga sus instrucciones y un conjunto reducido de herramientas
- **Para:** que un subagente de lectura no pueda escribir
- **Descripción:** Cada subagente tiene sus instrucciones y un conjunto reducido de herramientas, por ejemplo uno de lectura que no puede escribir.

**Flujo general**

1. El harness lee el perfil del subagente.
2. Registra solo las herramientas del perfil.
3. El subagente trabaja con ese conjunto.

**Reglas de negocio**

1. Un subagente no ve las herramientas que no están en su perfil.
2. Los subagentes nunca incluyen la herramienta de delegación.

**Criterios de aceptación**

- **AC-01 — Herramientas restringidas por perfil.** Dado un subagente de solo lectura, cuando intenta usar una herramienta de escritura, entonces no la encuentra en su registro.

<a id="hu-09-03"></a>
#### HU-09-03 — Resultado estructurado en lugar de la transcripción

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 2 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-9.4 · **Depende de:** [HU-09-01](04d-historias-conexiones.md#hu-09-01)

- **Como:** agente principal
- **Quiero:** recibir del subagente un resultado estructurado y breve
- **Para:** continuar con mi ventana intacta
- **Descripción:** El orquestador recibe del subagente un resultado estructurado y breve en lugar de la transcripción completa.

**Flujo general**

1. El subagente termina.
2. Devuelve resultado, hallazgos clave, fuentes y error.
3. El harness valida el resultado contra el esquema.
4. El orquestador continúa con su ventana intacta.

**Reglas de negocio**

1. La transcripción del subagente no entra al contexto del orquestador.
2. Las aprobaciones del subagente suben al usuario indicando quién las pide.

**Criterios de aceptación**

- **AC-01 — Resultado estructurado sin transcripción.** Dado un subagente que terminó, cuando devuelve su resultado, entonces el orquestador recibe resultado, hallazgos clave y fuentes, y no la transcripción.

<a id="hu-09-04"></a>
#### HU-09-04 — Un solo nivel de anidamiento y límites por subagente

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-9.5, RF-9.6 · **Depende de:** [HU-09-01](04d-historias-conexiones.md#hu-09-01), [HU-01-06](04a-historias-fundacion.md#hu-01-06)

- **Como:** usuario operador
- **Quiero:** limitar la profundidad de anidamiento y los turnos y costo de cada subagente
- **Para:** evitar que la delegación se descontrole
- **Descripción:** El sistema limita la profundidad de anidamiento y los turnos y el costo de cada subagente.

**Flujo general**

1. El subagente intenta delegar.
2. El harness lo rechaza.
3. Si alcanza su límite de turnos, termina con un resultado parcial.

**Reglas de negocio**

1. Solo se permite un nivel de anidamiento.
2. Los límites del subagente son independientes de los del orquestador.

**Criterios de aceptación**

- **AC-01 — Anidamiento rechazado.** Dado un subagente que intenta lanzar otro, cuando invoca la delegación, entonces se rechaza.
- **AC-02 — Resultado parcial por límite.** Dado un límite de turnos del subagente, cuando se alcanza, entonces termina y devuelve un resultado parcial.

<a id="hu-09-05"></a>
#### HU-09-05 — Propagación explícita de errores del subagente

**Prioridad:** Media · **PHU:** 1 · **Sprint:** Sprint 3 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-9.7 · **Depende de:** [HU-09-03](04d-historias-conexiones.md#hu-09-03)

- **Como:** agente principal
- **Quiero:** recibir los errores del subagente de forma explícita
- **Para:** decidir qué hacer en lugar de fallar en silencio
- **Descripción:** El orquestador recibe los errores del subagente de forma explícita para decidir qué hacer.

**Flujo general**

1. El subagente falla.
2. El harness devuelve un resultado de error con la causa.
3. El orquestador decide reintentar, cambiar de plan o avisar al usuario.

**Reglas de negocio**

1. Un fallo del subagente nunca se oculta.

**Criterios de aceptación**

- **AC-01 — Error explícito con causa.** Dado un subagente que falla, cuando termina, entonces el orquestador recibe un resultado de error con la causa.

<a id="hu-09-06"></a>
#### HU-09-06 — Dos tipos de subagente: explorador y verificador

**Prioridad:** Media · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-9.8 · **Depende de:** [HU-09-02](04d-historias-conexiones.md#hu-09-02)

- **Como:** agente principal
- **Quiero:** elegir entre un subagente explorador y uno verificador
- **Para:** delegar según la naturaleza de la tarea
- **Descripción:** El orquestador elige entre un subagente explorador (solo lectura) y uno verificador (ejecuta pruebas, no edita).

**Flujo general**

1. El orquestador elige el tipo según la tarea.
2. El harness aplica el perfil del tipo.
3. El subagente trabaja con sus herramientas.

**Reglas de negocio**

1. Cada tipo tiene instrucciones y herramientas propias.

**Criterios de aceptación**

- **AC-01 — Herramientas por tipo de subagente.** Dado el tipo explorador, cuando se lanza, entonces solo tiene herramientas de lectura; dado el verificador, entonces puede ejecutar pruebas pero no editar archivos.

<a id="hu-09-07"></a>
#### HU-09-07 — Subagentes en paralelo con agregación de resultados

**Prioridad:** Baja · **PHU:** 3 · **Sprint:** Backlog · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-9.9 · **Depende de:** [HU-09-03](04d-historias-conexiones.md#hu-09-03), [SPK-02](04a-historias-fundacion.md#spk-02)

- **Como:** agente principal
- **Quiero:** lanzar varios subagentes a la vez
- **Para:** reducir el tiempo de tareas con partes independientes
- **Descripción:** El orquestador lanza varios subagentes a la vez y recibe sus resultados agregados.

**Flujo general**

1. El orquestador delega varias subtareas independientes.
2. Los subagentes corren en paralelo.
3. El harness agrega los resultados.

**Reglas de negocio**

1. Cada subagente conserva su contexto aislado.

**Criterios de aceptación**

- **AC-01 — Ejecución concurrente y agregación.** Dado tres subtareas independientes, cuando se delegan juntas, entonces corren a la vez y sus resultados llegan agregados.

### E10. Trazabilidad

<a id="hu-10-01"></a>
#### HU-10-01 — Trazas estructuradas de cada llamada

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** B — Estado  
**Requisitos:** RF-10.1, RF-10.2 · **Depende de:** [HU-01-05](04a-historias-fundacion.md#hu-01-05)

- **Como:** evaluador del proyecto
- **Quiero:** una traza de cada llamada al modelo y a herramientas con duración, consumo y resultado
- **Para:** ver qué hizo el agente y dónde falló
- **Descripción:** Cada llamada al modelo y a herramientas deja una traza estructurada con duración, consumo y resultado.

**Flujo general**

1. Ocurre una llamada.
2. El sistema registra tipo, duración, tokens y resultado.
3. El evaluador consulta la traza de la sesión.

**Reglas de negocio**

1. El formato de traza es estructurado y consultable.
2. La traza redacta secretos.

**Criterios de aceptación**

- **AC-01 — Traza de cada llamada.** Dado una sesión terminada, cuando consulto la traza, entonces veo cada llamada con su duración, tokens y resultado en formato estructurado.

<a id="hu-10-02"></a>
#### HU-10-02 — Redacción de secretos en registros

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 3 · **Desarrollador:** B — Estado  
**Requisitos:** RF-10.4, RNF-16 · **Depende de:** [HU-10-01](04d-historias-conexiones.md#hu-10-01)

- **Como:** usuario operador
- **Quiero:** que ningún registro contenga claves ni secretos
- **Para:** poder compartir trazas sin riesgo
- **Descripción:** Ningún registro contiene claves ni secretos: se sustituyen por una marca antes de escribirse.

**Flujo general**

1. El sistema va a escribir un registro.
2. Un filtro busca patrones de claves y valores de entorno.
3. Sustituye lo encontrado por una marca.

**Reglas de negocio**

1. La redacción cubre patrones conocidos y variables de entorno cargadas; no es una garantía total.

**Criterios de aceptación**

- **AC-01 — Secretos sustituidos por marca.** Dado un registro con una clave con patrón conocido, cuando se escribe, entonces la clave aparece sustituida por una marca.

<a id="hu-10-03"></a>
#### HU-10-03 — Convenciones de OpenTelemetry para IA generativa

**Prioridad:** Baja · **PHU:** 3 · **Sprint:** Backlog · **Desarrollador:** B — Estado  
**Requisitos:** RF-10.5 · **Depende de:** [HU-10-01](04d-historias-conexiones.md#hu-10-01)

- **Como:** equipo de desarrollo
- **Quiero:** emitir trazas con las convenciones de OpenTelemetry
- **Para:** conectar el sistema a herramientas de observabilidad estándar
- **Descripción:** Las trazas usan las convenciones de OpenTelemetry para IA generativa para conectarse a herramientas de observabilidad estándar.

**Flujo general**

1. El sistema exporta una traza.
2. Usa los nombres de atributos de las convenciones.
3. Una herramienta estándar la consume.

**Reglas de negocio**

1. La exportación es opcional y se puede desactivar.

**Criterios de aceptación**

- **AC-01 — Atributos estándar de IA generativa.** Dado una traza, cuando se exporta, entonces usa los nombres de atributos de las convenciones de IA generativa.


### EI. Innovación

<a id="hu-in-01"></a>
#### HU-IN-01 — Interfaz web sobre el mismo núcleo

**Prioridad:** Baja · **PHU:** 8 · **Sprint:** Backlog · **Desarrollador:** A — Núcleo  
**Requisitos:** Nivel 2 · **Depende de:** [HU-01-05](04a-historias-fundacion.md#hu-01-05)

- **Como:** usuario operador
- **Quiero:** usar el agente desde el navegador
- **Para:** una experiencia más cómoda y mostrable
- **Descripción:** El usuario usa el agente desde el navegador sobre el mismo núcleo, con los mismos eventos y aprobaciones.

**Flujo general**

1. El navegador abre una conexión WebSocket.
2. El servidor suscribe la web al bus de eventos.
3. El usuario plantea una tarea.
4. La web muestra eventos y pide aprobaciones.

**Reglas de negocio**

1. No se modifica el núcleo: solo se añade una interfaz.

**Criterios de aceptación**

- **AC-01 — Eventos y aprobación en la web.** Dado el servidor con WebSocket, cuando se plantea una tarea desde el navegador, entonces la web muestra los mismos eventos que la terminal, incluida la aprobación de acciones.

<a id="hu-in-02"></a>
#### HU-IN-02 — Ejecución de comandos en entorno aislado

**Prioridad:** Baja · **PHU:** 5 · **Sprint:** Backlog · **Desarrollador:** C — Control y conexiones  
**Requisitos:** Nivel 2 · **Depende de:** [HU-01-04](04a-historias-fundacion.md#hu-01-04)

- **Como:** usuario operador
- **Quiero:** que los comandos corran en un contenedor o entorno aislado
- **Para:** limitar el daño de un comando erróneo
- **Descripción:** Los comandos del agente corren en un contenedor o entorno aislado para limitar el daño de un comando erróneo.

**Flujo general**

1. La herramienta de shell arranca un entorno aislado.
2. Ejecuta el comando allí.
3. Devuelve el resultado.

**Reglas de negocio**

1. Lo que ocurre en el entorno no afecta al sistema anfitrión.

**Criterios de aceptación**

- **AC-01 — Comando aislado del anfitrión.** Dado un comando que escribe fuera de la carpeta de trabajo, cuando corre en el entorno aislado, entonces no afecta al sistema anfitrión.

<a id="hu-in-03"></a>
#### HU-IN-03 — Comparación del orquestador propio con LangGraph

**Prioridad:** Baja · **PHU:** 5 · **Sprint:** Backlog · **Desarrollador:** A — Núcleo  
**Requisitos:** Nivel 2 · **Depende de:** [HU-09-03](04d-historias-conexiones.md#hu-09-03)

- **Como:** evaluador del proyecto
- **Quiero:** una comparación entre el orquestador propio y una versión sobre LangGraph
- **Para:** juzgar si el framework aporta
- **Descripción:** El equipo compara su orquestador de subagentes con una versión sobre LangGraph para juzgar qué aporta el framework.

**Flujo general**

1. Se implementa la misma tarea de delegación con ambas versiones.
2. Se compara código, comportamiento y esfuerzo.
3. Se documentan las conclusiones.

**Reglas de negocio**

1. La comparación usa la misma tarea y los mismos límites.

**Criterios de aceptación**

- **AC-01 — Comparación documentada.** Dado una misma tarea de delegación, cuando se ejecuta con ambas versiones, entonces se documentan diferencias de código, comportamiento y esfuerzo.

<a id="hu-in-04"></a>
#### HU-IN-04 — Panel de costos y consumo por sesión

**Prioridad:** Baja · **PHU:** 3 · **Sprint:** Backlog · **Desarrollador:** B — Estado  
**Requisitos:** Nivel 2 · **Depende de:** [HU-03-05](04b-historias-estado.md#hu-03-05)

- **Como:** usuario operador
- **Quiero:** ver gráficas de consumo y costo por sesión
- **Para:** entender mi gasto de un vistazo
- **Descripción:** El usuario ve gráficas de consumo y costo por sesión y por modelo.

**Flujo general**

1. El usuario abre el panel.
2. El sistema consulta los consumos guardados.
3. Muestra gráficas por sesión y modelo.

**Reglas de negocio**

1. El costo se muestra como estimación.

**Criterios de aceptación**

- **AC-01 — Panel de consumo.** Dado varias sesiones, cuando abro el panel, entonces veo el consumo por sesión y por modelo.

---

[← 04c-historias-control.md](04c-historias-control.md) · [Índice](00-indice.md) · [04e-historias-coding-harness.md →](04e-historias-coding-harness.md)
