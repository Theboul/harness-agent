# Historias: contexto, sesiones y memoria (E2, E3, E4)

> [← 04a-historias-fundacion.md](04a-historias-fundacion.md) · [Índice](00-indice.md) · [04c-historias-control.md →](04c-historias-control.md)  
> Sección 10 del contexto original, continuación: épicas E2, E3 y E4 (incluye SPK-03).  
> Ver también: [02-arquitectura.md](02-arquitectura.md) · [03-plan-sprints.md](03-plan-sprints.md) · [PROGRESO.md](PROGRESO.md)
>
> El estado de cada historia vive solo en [PROGRESO.md](PROGRESO.md); aquí no se repite.

### E2. Gestión de contexto

<a id="hu-02-01"></a>
#### HU-02-01 — Estimación de tokens y prefijo estable

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 2 · **Desarrollador:** B — Estado  
**Requisitos:** RF-2.1, RF-2.2, RNF-4 · **Depende de:** [HU-01-01](04a-historias-fundacion.md#hu-01-01)

- **Como:** equipo de desarrollo
- **Quiero:** estimar los tokens del contexto antes de cada llamada y mantener estable el prefijo del prompt
- **Para:** decidir cuándo compactar y aprovechar la caché del proveedor
- **Descripción:** El sistema estima los tokens del contexto antes de cada llamada y mantiene estable el prefijo del prompt para decidir cuándo compactar y aprovechar la caché.

**Flujo general**

1. Antes de llamar, el ContextManager ensambla el contexto.
2. Estima los tokens con una heurística.
3. Tras la respuesta, corrige la estimación con el consumo real informado por la API.
4. Mantiene idéntico el prefijo entre turnos.

**Reglas de negocio**

1. La estimación es heurística y se corrige con el uso real.
2. El prefijo (instrucciones y definiciones de herramientas) no cambia dentro de la sesión.

**Criterios de aceptación**

- **AC-01 — Prefijo estable entre turnos.** Dado el historial, cuando se ensambla el contexto, entonces el prefijo con instrucciones y definiciones es idéntico entre turnos de la misma sesión.
- **AC-02 — Corrección con el consumo real.** Dado un turno terminado, cuando el proveedor informa su consumo real, entonces la estimación se corrige con ese valor.

<a id="hu-02-02"></a>
#### HU-02-02 — Recorte de salidas largas de herramientas

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 2 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-2.5 · **Depende de:** [HU-01-02](04a-historias-fundacion.md#hu-01-02)

- **Como:** usuario operador
- **Quiero:** que las salidas muy largas de una herramienta se recorten e indiquen que fueron truncadas
- **Para:** que un solo comando no llene el contexto
- **Descripción:** Las salidas muy largas de una herramienta se recortan y se marca cuánto se omitió, para que un solo comando no llene el contexto.

**Flujo general**

1. Una herramienta devuelve una salida larga.
2. El sistema compara su tamaño con el máximo.
3. Si lo excede, la recorta y añade una marca con la cantidad omitida.
4. El resultado recortado vuelve al contexto.

**Reglas de negocio**

1. El tamaño máximo es configurable.
2. El recorte siempre deja una marca visible.

**Criterios de aceptación**

- **AC-01 — Recorte con marca de omisión.** Dado una salida que supera el tamaño máximo, cuando vuelve al contexto, entonces se recorta e incluye una marca con la cantidad omitida.

<a id="hu-02-03"></a>
#### HU-02-03 — Compactación automática por umbral

**Prioridad:** Alta · **PHU:** 5 · **Sprint:** Sprint 2 · **Desarrollador:** B — Estado  
**Requisitos:** RF-2.3, RF-2.4, RNF-3 · **Depende de:** [HU-02-01](04b-historias-estado.md#hu-02-01), [SPK-03](04b-historias-estado.md#spk-03)

- **Como:** usuario operador
- **Quiero:** que el sistema resuma el historial antiguo al acercarse al límite de la ventana
- **Para:** poder trabajar sesiones largas sin perder el hilo
- **Descripción:** Cuando el contexto se acerca al umbral, el sistema resume el historial antiguo con una llamada aparte y conserva íntegros los mensajes recientes.

**Flujo general**

1. Al empezar un turno se estima el contexto.
2. Si supera el umbral, se resume lo antiguo con una llamada aparte.
3. Se añade un evento de resumen y se marcan los eventos cubiertos.
4. El turno continúa con el contexto reducido.

**Reglas de negocio**

1. La compactación nunca borra el historial original.
2. El umbral se calcula por modelo.

**Criterios de aceptación**

- **AC-01 — Resumen por umbral con mensajes recientes íntegros.** Dado un contexto que supera el umbral, cuando empieza un turno, entonces se resume lo antiguo con una llamada aparte y se conservan íntegros los mensajes recientes.
- **AC-02 — Historial original conservado.** Dado una compactación, cuando termina, entonces el historial original sigue guardado en la sesión y no se borra.

<a id="hu-02-04"></a>
#### HU-02-04 — Comando para compactar manualmente

**Prioridad:** Media · **PHU:** 1 · **Sprint:** Sprint 3 · **Desarrollador:** B — Estado  
**Requisitos:** RF-2.6 · **Depende de:** [HU-02-03](04b-historias-estado.md#hu-02-03)

- **Como:** usuario operador
- **Quiero:** forzar la compactación con un comando
- **Para:** controlar cuándo se resume mi sesión
- **Descripción:** El usuario puede forzar la compactación con un comando aunque no se haya llegado al umbral.

**Flujo general**

1. El usuario escribe el comando de compactar.
2. El sistema ejecuta la compactación.
3. Informa cuántos tokens se liberaron.

**Reglas de negocio**

1. Usa el mismo mecanismo que la compactación automática.

**Prototipo**

```
> /compactar
Contexto compactado: 38 400 → 9 100 tokens (historial original conservado)
```

**Criterios de aceptación**

- **AC-01 — Compactación manual.** Dado una sesión activa, cuando ejecuto el comando de compactar, entonces se compacta aunque no se haya alcanzado el umbral.

<a id="hu-02-05"></a>
#### HU-02-05 — Compactación solicitada por el propio modelo

**Prioridad:** Baja · **PHU:** 2 · **Sprint:** Backlog · **Desarrollador:** B — Estado  
**Requisitos:** RF-2.8 · **Depende de:** [HU-02-03](04b-historias-estado.md#hu-02-03)

- **Como:** agente principal
- **Quiero:** poder pedir la compactación con una herramienta
- **Para:** hacerla en el momento oportuno
- **Descripción:** El agente principal puede pedir la compactación con una herramienta antes de leer un volumen grande de información.

**Flujo general**

1. El agente decide que va a leer mucho.
2. Invoca la herramienta de compactar.
3. El sistema compacta y el agente continúa.

**Reglas de negocio**

1. Pasa por la misma política de permisos que cualquier herramienta.

**Criterios de aceptación**

- **AC-01 — Compactación pedida por el modelo.** Dado que el agente va a leer un volumen grande de información, cuando invoca la herramienta, entonces se compacta antes de continuar.

<a id="hu-02-06.1"></a>
#### HU-02-06.1 — Contexto esencial persistente fuera del historial compactable

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 2 · **Desarrollador:** B — Estado  
**Requisitos:** RF-2.7 · **Depende de:** [HU-02-03](04b-historias-estado.md#hu-02-03), [HU-11-01](04e-historias-coding-harness.md#hu-11-01)

- **Como:** usuario operador
- **Quiero:** que el objetivo, las instrucciones del sistema, las reglas de la tarea, el identificador del ticket y la referencia a los criterios protegidos se guarden aparte y que la compactación no los toque
- **Para:** que el agente no pierda lo esencial al compactar una sesión larga
- **Descripción:** El objetivo, las instrucciones del sistema, las reglas de la tarea, el identificador del ticket y la referencia a los criterios protegidos viven en una tabla aparte del historial. En cada ensamblado se inyectan en el prefijo y la compactación no los toca. Es la parte mínima de la historia original HU-02-06 que necesita el Sprint 2; no usa la memoria estructurada ([HU-04-03](04b-historias-estado.md#hu-04-03)).

**Flujo general**

1. Al crear la sesión del ticket se guardan los elementos esenciales en contexto_esencial.
2. En cada ensamblado el sistema los inyecta en el prefijo, antes del historial.
3. Al compactar solo se resume el historial; el bloque esencial queda fuera.
4. Tras compactar, el agente responde sobre el objetivo y las reglas sin pérdida.

**Reglas de negocio**

1. Lo esencial nunca se resume ni se reescribe en una compactación.
2. Los criterios no se copian: el bloque guarda su referencia y se leen de su fuente protegida.
3. Las decisiones acumuladas se añaden en [HU-02-06.2](04b-historias-estado.md#hu-02-06.2), no aquí.

**Criterios de aceptación**

- **AC-01 — Lo esencial sigue idéntico tras compactar.** Dado una sesión con objetivo, instrucciones, reglas, identificador de ticket y criterios, cuando se compacta, entonces esos elementos siguen en el prefijo del contexto, idénticos, y no forman parte de lo resumido.
- **AC-02 — Instrucciones intactas y criterios desde su fuente.** Dado una compactación, cuando se reconstruye el contexto, entonces las instrucciones de sistema están intactas y los criterios se leen desde su fuente protegida, no desde el resumen.
- **AC-03 — Objetivo recordado tras compactar.** Dado una sesión compactada, cuando se pregunta por el objetivo original, entonces el agente lo responde correctamente.

<a id="hu-02-06.2"></a>
#### HU-02-06.2 — Decisiones acumuladas y continuidad tras varias compactaciones

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 3 · **Desarrollador:** B — Estado  
**Requisitos:** RF-2.7 · **Depende de:** [HU-02-06.1](04b-historias-estado.md#hu-02-06.1), [HU-05-04](04c-historias-control.md#hu-05-04)

- **Como:** usuario operador
- **Quiero:** que las decisiones que tomo (aprobaciones, rechazos con motivo y respuestas) se acumulen en el contexto esencial y sobrevivan a varias compactaciones seguidas
- **Para:** que el agente no repita lo que ya rechacé ni empiece de cero después de varias compactaciones
- **Descripción:** Las decisiones del usuario (aprobaciones, rechazos con motivo, respuestas) se acumulan en el contexto esencial y el resumen de cada compactación incluye una sección de decisiones. Completa las garantías de la historia original HU-02-06 tras varias compactaciones.

**Flujo general**

1. El usuario toma una decisión (por ejemplo, rechaza una acción con motivo).
2. El sistema la añade al bloque de decisiones del contexto esencial.
3. Cada compactación genera además una sección de decisiones del tramo resumido.
4. Tras varias compactaciones el agente respeta lo ya decidido.

**Reglas de negocio**

1. Las decisiones nunca se resumen: se conservan literales en el bloque esencial.
2. Si la memoria estructurada ([HU-04-03](04b-historias-estado.md#hu-04-03)) está implementada, sus entradas pueden alimentar el bloque, pero no es requisito de esta historia.

**Criterios de aceptación**

- **AC-01 — Decisiones y objetivo tras tres compactaciones.** Dado una sesión con decisiones del usuario, entre ellas un rechazo con motivo, cuando se compacta tres veces seguidas, entonces las decisiones siguen en el bloque esencial sin resumirse y el agente responde correctamente el objetivo original.
- **AC-02 — Sección de decisiones en el resumen.** Dado el resumen de una compactación, cuando se genera, entonces incluye una sección con las decisiones del tramo resumido.

<a id="hu-02-07"></a>
#### HU-02-07 — Archivo de instrucciones del proyecto

**Prioridad:** Baja · **PHU:** 2 · **Sprint:** Backlog · **Desarrollador:** B — Estado  
**Requisitos:** RF-2.9 · **Depende de:** [HU-02-01](04b-historias-estado.md#hu-02-01)

- **Como:** usuario operador
- **Quiero:** que el agente cargue un archivo de instrucciones del proyecto al iniciar
- **Para:** darle convenciones y reglas propias sin repetirlas
- **Descripción:** El agente carga al iniciar un archivo de instrucciones del proyecto para recibir convenciones y reglas propias sin repetirlas.

**Flujo general**

1. Al arrancar la sesión, el sistema busca el archivo de instrucciones.
2. Si existe, lo lee.
3. Incorpora su contenido al prefijo estable.

**Reglas de negocio**

1. El contenido del archivo se trata como instrucción del usuario, no como dato externo.

**Criterios de aceptación**

- **AC-01 — Instrucciones cargadas al iniciar.** Dado un archivo de instrucciones en la carpeta de trabajo, cuando arranca la sesión, entonces su contenido entra en el prefijo estable.

<a id="spk-03"></a>
#### SPK-03 — Spike: compactación sin perder el objetivo

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 2 · **Desarrollador:** B — Estado  
**Requisitos:** RF-2.3, RF-2.4, RF-2.7 · **Depende de:** [HU-01-01](04a-historias-fundacion.md#hu-01-01)

- **Como:** equipo de desarrollo
- **Quiero:** probar durante medio día un resumen de historial con una sesión larga simulada
- **Para:** estimar con seguridad la compactación
- **Descripción:** Spike de medio día: probar un resumen de historial con una sesión larga simulada para ver si sobreviven el objetivo y las decisiones.

**Flujo general**

1. Se simula una sesión larga.
2. Se compacta dos veces.
3. Se evalúa qué se perdió.
4. Se anota qué debe vivir fuera del resumen.

**Reglas de negocio**

1. El resultado alimenta [HU-02-03](04b-historias-estado.md#hu-02-03) y HU-02-06.

**Criterios de aceptación**

- **AC-01 — Evaluación de la compactación.** Dado una sesión larga simulada, cuando se compacta dos veces, entonces se evalúa si el objetivo y las decisiones sobreviven y se anota qué debe vivir fuera del resumen.

### E3. Sesiones

<a id="hu-03-01"></a>
#### HU-03-01 — Esquema SQLite y creación de sesión

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 1 · **Desarrollador:** B — Estado  
**Requisitos:** RF-3.1 · **Depende de:** [HU-00-01](04a-historias-fundacion.md#hu-00-01)

- **Como:** usuario operador
- **Quiero:** que cada sesión nueva se cree con un identificador y una fecha
- **Para:** poder volver a ella más tarde
- **Descripción:** Cada sesión nueva se crea en SQLite con identificador, fecha y estado, para poder volver a ella.

**Flujo general**

1. El usuario inicia una sesión.
2. El sistema crea el registro con identificador único y marca de tiempo.
3. La sesión queda en estado activa.

**Reglas de negocio**

1. Una sesión de subagente guarda el identificador de su sesión padre.

**Criterios de aceptación**

- **AC-01 — Sesión creada con identificador y fecha.** Dado el inicio de una sesión, cuando se crea, entonces tiene identificador único, marca de tiempo y estado.

<a id="hu-03-02"></a>
#### HU-03-02 — Persistir cada evento al ocurrir y tolerar cortes abruptos

**Prioridad:** Alta · **PHU:** 3 · **Sprint:** Sprint 1 · **Desarrollador:** B — Estado  
**Requisitos:** RF-3.2, RF-3.5 · **Depende de:** [HU-03-01](04b-historias-estado.md#hu-03-01), [HU-01-05](04a-historias-fundacion.md#hu-01-05)

- **Como:** usuario operador
- **Quiero:** que cada mensaje y resultado se guarde en el momento en que ocurre
- **Para:** no perder trabajo si el programa se cierra de golpe
- **Descripción:** Cada mensaje y resultado se guarda en el momento en que ocurre, de modo que un cierre abrupto no pierde trabajo.

**Flujo general**

1. Ocurre un evento.
2. El SessionStore lo escribe en la base de datos de inmediato.
3. Si el proceso se interrumpe, el evento sigue en la base al reiniciar.

**Reglas de negocio**

1. Un evento confirmado nunca se pierde.
2. Una escritura cortada no deja la base corrupta.

**Criterios de aceptación**

- **AC-01 — Evento sobrevive a un cierre abrupto.** Dado un evento confirmado, cuando el proceso se interrumpe de golpe, entonces el evento sigue en la base al reiniciar.
- **AC-02 — Base sin corrupción.** Dado una escritura en curso, cuando se corta, entonces la base no queda corrupta.

<a id="hu-03-03"></a>
#### HU-03-03 — Listar sesiones

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 4 · **Desarrollador:** B — Estado  
**Requisitos:** RF-3.3 · **Depende de:** [HU-03-01](04b-historias-estado.md#hu-03-01)

- **Como:** usuario operador
- **Quiero:** ver mis sesiones con título, fecha y estado
- **Para:** elegir cuál reanudar
- **Descripción:** El usuario puede listar sus sesiones con título, fecha y estado para elegir cuál reanudar.

**Flujo general**

1. El usuario ejecuta el comando de listar.
2. El sistema consulta las sesiones guardadas.
3. Muestra título, fecha y estado, de la más reciente a la más antigua.

**Reglas de negocio**

1. Las sesiones de subagente no se listan como sesiones de primer nivel.

**Prototipo**

```
> /sesiones
id        fecha        estado     título
7f3a91    hoy 10:42    activa     Refactor del módulo de pagos
2c8d04    ayer 17:05   cerrada    Revisión de pruebas
```

**Criterios de aceptación**

- **AC-01 — Listado ordenado de sesiones.** Dado varias sesiones guardadas, cuando ejecuto el comando de listar, entonces veo título, fecha y estado de cada una, de la más reciente a la más antigua.

<a id="hu-03-04"></a>
#### HU-03-04 — Reanudar una sesión por identificador

**Prioridad:** Alta · **PHU:** 3 · **Sprint:** Sprint 2 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-3.4 · **Depende de:** [HU-03-02](04b-historias-estado.md#hu-03-02), [HU-02-03](04b-historias-estado.md#hu-02-03)

- **Como:** usuario operador
- **Quiero:** reanudar una sesión anterior y continuar donde quedé
- **Para:** no repetir lo que ya le había dicho al agente
- **Descripción:** El usuario reanuda una sesión anterior por su identificador y el agente continúa donde quedó.

**Flujo general**

1. El usuario escribe el comando de reanudar con un identificador.
2. El sistema carga los eventos guardados.
3. Reconstruye el contexto.
4. Si supera el umbral, lo compacta.
5. El agente continúa el trabajo.

**Reglas de negocio**

1. Reanudar usa el historial completo, no el resumen.
2. Si el identificador no existe, se informa con un error claro.

**Criterios de aceptación**

- **AC-01 — Contexto reconstruido al reanudar.** Dado una sesión de ayer, cuando la reanudo por su identificador, entonces el contexto se reconstruye desde lo guardado y el agente continúa el trabajo.
- **AC-02 — Compactación si supera el umbral.** Dado una sesión larga, cuando se reanuda, entonces se compacta si el contexto reconstruido supera el umbral.

<a id="hu-03-05"></a>
#### HU-03-05 — Consumo de tokens y costo estimado por sesión

**Prioridad:** Media · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** B — Estado  
**Requisitos:** RF-3.6 · **Depende de:** [HU-03-02](04b-historias-estado.md#hu-03-02)

- **Como:** usuario operador
- **Quiero:** ver cuántos tokens y qué costo estimado consumió cada sesión
- **Para:** controlar mi gasto
- **Descripción:** El usuario consulta cuántos tokens y qué costo estimado consumió cada sesión.

**Flujo general**

1. El usuario consulta el resumen de una sesión.
2. El sistema suma los tokens de entrada y salida.
3. Calcula un costo aproximado.
4. Lo muestra marcado como estimado.

**Reglas de negocio**

1. El costo se muestra como informativo; el límite se mide en tokens.

**Criterios de aceptación**

- **AC-01 — Consumo y costo estimado por sesión.** Dado una sesión terminada, cuando consulto su resumen, entonces veo los tokens de entrada y salida y un costo estimado marcado como aproximado.

<a id="hu-03-06"></a>
#### HU-03-06 — Exportar una sesión a formato legible

**Prioridad:** Baja · **PHU:** 1 · **Sprint:** Backlog · **Desarrollador:** B — Estado  
**Requisitos:** RF-3.7 · **Depende de:** [HU-03-02](04b-historias-estado.md#hu-03-02)

- **Como:** usuario operador
- **Quiero:** exportar una sesión a un archivo legible
- **Para:** revisarla o compartirla
- **Descripción:** El usuario exporta una sesión a un archivo legible para revisarla o compartirla.

**Flujo general**

1. El usuario ejecuta el comando de exportar.
2. El sistema genera un archivo con mensajes y herramientas usadas.
3. Informa la ruta del archivo.

**Reglas de negocio**

1. La exportación redacta los secretos conocidos.

**Criterios de aceptación**

- **AC-01 — Exportación legible de la sesión.** Dado una sesión, cuando la exporto, entonces obtengo un archivo con los mensajes y las herramientas usadas.

### E4. Memoria

<a id="hu-04-01"></a>
#### HU-04-01 — Almacén de memoria separado del historial

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 4 · **Desarrollador:** B — Estado  
**Requisitos:** RF-4.1 · **Depende de:** [HU-03-01](04b-historias-estado.md#hu-03-01)

- **Como:** usuario operador
- **Quiero:** que el agente tenga una memoria que sobreviva a las sesiones
- **Para:** no repetirle mis preferencias y decisiones
- **Descripción:** El agente dispone de una memoria persistente separada del historial, que sobrevive a las sesiones y a su compactación.

**Flujo general**

1. El sistema guarda la memoria en una tabla propia de SQLite.
2. El historial se compacta o se borra.
3. La memoria permanece intacta.

**Reglas de negocio**

1. La memoria no se mezcla con el historial de eventos.

**Criterios de aceptación**

- **AC-01 — Memoria independiente del historial.** Dado una memoria guardada, cuando se borra o compacta una sesión, entonces la memoria no se ve afectada.

<a id="hu-04-02"></a>
#### HU-04-02 — Herramienta de memoria y carga al inicio

**Prioridad:** Alta · **PHU:** 3 · **Sprint:** Sprint 4 · **Desarrollador:** B — Estado  
**Requisitos:** RF-4.2, RF-4.3 · **Depende de:** [HU-04-01](04b-historias-estado.md#hu-04-01), [HU-01-02](04a-historias-fundacion.md#hu-01-02)

- **Como:** usuario operador
- **Quiero:** que el agente pueda guardar datos y recuperarlos al abrir una sesión nueva
- **Para:** continuidad entre sesiones
- **Descripción:** El agente guarda datos con una herramienta y los recupera al abrir una sesión nueva, dentro de un presupuesto de tokens.

**Flujo general**

1. El agente invoca la herramienta de memoria para guardar un dato.
2. En una sesión nueva, el sistema carga la memoria.
3. Selecciona lo más reciente hasta llenar el presupuesto.
4. Informa de lo omitido.

**Reglas de negocio**

1. Relevancia = recencia dentro del presupuesto de tokens.
2. La memoria vive en SQLite.

**Criterios de aceptación**

- **AC-01 — Dato recuperado en sesión nueva.** Dado que el agente guardó un dato en una sesión, cuando abro una sesión nueva, entonces el dato aparece en el contexto inicial.
- **AC-02 — Prioridad por recencia y aviso de omisión.** Dado más memoria de la que cabe en el presupuesto, cuando se carga, entonces se prioriza lo más reciente y se informa de lo omitido.

<a id="hu-04-03"></a>
#### HU-04-03 — Memoria estructurada de la sesión

**Prioridad:** Media · **PHU:** 3 · **Sprint:** Sprint 4 · **Desarrollador:** B — Estado  
**Requisitos:** RF-4.4 · **Depende de:** [HU-04-01](04b-historias-estado.md#hu-04-01)

- **Como:** agente principal
- **Quiero:** llevar un registro de decisiones, acciones realizadas y fallos
- **Para:** retomar el trabajo tras una compactación sin releer todo
- **Descripción:** El agente lleva un registro de decisiones, acciones realizadas y fallos que sobrevive a la compactación.

**Flujo general**

1. El agente toma una decisión.
2. La registra en la memoria de la sesión.
3. Tras compactar, el registro se inyecta en el contexto.

**Reglas de negocio**

1. El registro no se resume: se conserva literal.

**Criterios de aceptación**

- **AC-01 — Decisión registrada y conservada.** Dado una decisión tomada, cuando se registra, entonces queda en la memoria de la sesión y sobrevive a la compactación.

<a id="hu-04-04"></a>
#### HU-04-04 — Inspeccionar y editar la memoria

**Prioridad:** Media · **PHU:** 1 · **Sprint:** Sprint 4 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-4.5 · **Depende de:** [HU-04-01](04b-historias-estado.md#hu-04-01)

- **Como:** usuario operador
- **Quiero:** ver y corregir lo que el agente recuerda
- **Para:** mantener el control sobre su memoria
- **Descripción:** El usuario ve y corrige lo que el agente recuerda con el comando /memoria.

**Flujo general**

1. El usuario escribe /memoria.
2. El sistema muestra las entradas.
3. El usuario edita o elimina una.
4. El agente deja de usar el valor anterior.

**Reglas de negocio**

1. Toda edición queda reflejada de inmediato en la memoria.

**Prototipo**

```
> /memoria
1. [hoy] El usuario prefiere pruebas con pytest
2. [ayer] El proyecto usa Python 3.11
```

**Criterios de aceptación**

- **AC-01 — Edición y borrado de memoria.** Dado una entrada de memoria, cuando la edito o elimino con el comando de memoria, entonces el agente deja de usar el valor anterior.

<a id="hu-04-05"></a>
#### HU-04-05 — No almacenar secretos en memoria

**Prioridad:** Media · **PHU:** 2 · **Sprint:** Sprint 4 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-4.6 · **Depende de:** [HU-04-02](04b-historias-estado.md#hu-04-02)

- **Como:** usuario operador
- **Quiero:** que el sistema no guarde claves ni secretos en la memoria
- **Para:** evitar filtraciones
- **Descripción:** El sistema rechaza guardar en memoria claves y secretos para evitar filtraciones.

**Flujo general**

1. El agente intenta guardar un texto.
2. El sistema lo contrasta con patrones de claves conocidos y con las variables de entorno cargadas.
3. Si hay coincidencia, rechaza el guardado y avisa al usuario.

**Reglas de negocio**

1. La detección cubre patrones conocidos y valores de entorno; no garantiza detección total.

**Criterios de aceptación**

- **AC-01 — Secreto rechazado en memoria.** Dado un texto que contiene una clave con patrón conocido, cuando el agente intenta guardarlo, entonces se rechaza y se avisa al usuario.

---

[← 04a-historias-fundacion.md](04a-historias-fundacion.md) · [Índice](00-indice.md) · [04c-historias-control.md →](04c-historias-control.md)
