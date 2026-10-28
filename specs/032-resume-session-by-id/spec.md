# Feature Specification: HU-03-04 — Reanudar una sesión por identificador

**Feature Branch**: `gustavo` (el directorio de la spec es `032-resume-session-by-id`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-27

**Status**: Clarificada (las tres preguntas abiertas se resolvieron el 2026-10-27; la interpretación de la regla 1 queda pendiente de ratificar por el PO y por A); lista para `/speckit-plan`

**Proyecto**: HARNESS v2.5 | **Sprint**: 2 | **PHU**: 3 (ficha) | **Responsable**: A — Núcleo | **Tareas de referencia**: Sp2-21 (3 h), Sp2-22 (2 h), Sp2-23 (2 h) | **Requisitos**: RF-3.4 | **Depende de**: HU-03-02 (persistencia de eventos, en revisión), HU-02-03 (compactación automática, integrada en `main`); se apoya en HU-02-06.1 (contexto esencial, integrada en `main`)

**Input**: User description: "HU-03-04 (spec 032). Reanudar una sesión anterior por su identificador y continuar donde quedó: cargar lo guardado, reconstruir el contexto, compactar si supera el umbral y continuar. Verificar el hallazgo de que los eventos que persiste hoy el bucle no bastan para reconstruir el historial de mensajes (resuelta como Q1 = B), la tensión entre «usa el historial completo, no el resumen» y «si supera el umbral, lo compacta» (resuelta como Q2 = B) y el alcance del comando y de las sesiones de tarea (resuelta como Q3 = A). Cubrir cortes abruptos, sesión vacía, sesiones muy largas, identificadores inválidos, errores sin texto del historial, límites de sesión y qué se muestra en la CLI."

## Clarifications

### Session 2026-10-27

Respuestas del usuario (que actúa como A) a las tres preguntas abiertas de `/speckit-specify`. Ninguna contradice un criterio de aceptación.

- Q: ¿Qué se persiste para poder reconstruir el historial de mensajes? → A: **B.** Los mensajes se guardan en una tabla propia (esquema versión 5, aditivo, con migración desde bases reales de las versiones 1 a 4), alimentada por un suscriptor de la composición que lee cada mensaje justo cuando el bus publica el evento correspondiente, más un guardado al cierre del turno que cubre la respuesta final vacía. El bucle, los puertos y el catálogo de eventos **no cambian**, y las pruebas existentes que aseguran que los eventos no llevan argumentos ni el motivo del rechazo **no se tocan**. Por mensaje se guarda: rol, contenido, llamadas con sus argumentos, resultado (identificador de la llamada, contenido y si es error), si es contenido externo y el consumo de tokens.
- Q: Al reanudar una sesión ya compactada, ¿se reconstruye el historial completo o el resumen vigente más los mensajes no cubiertos? → A: **B.** Se reconstruye el contexto como lo tenía el proceso al salir: prefijo, petición inicial, resumen vigente y mensajes no cubiertos; sin resumen, el historial completo. El historial completo sigue guardado y reconstruible (nada se borra ni se reescribe). **Interpretación de la regla 1 («Reanudar usa el historial completo, no el resumen»), pendiente de ratificar por el PO y por A (el usuario actúa como A):** lo que la regla protege es no perder nada al reanudar; re-resumir todo en cada reanudación costaría una llamada extra y podría no caber en la ventana del modelo. AC-02 se cumple porque la compactación existente corre antes de cada petición, incluida la primera tras reanudar (con un cambio de modelo o de configuración incluido).
- Q: ¿Reanudar sesiones de tarea está dentro del alcance? → A: **A.** Solo se reanudan sesiones **sin tarea**. Una sesión con tarea (con bloque esencial o con criterios guardados) se rechaza con un error claro que no repite su contenido; esta historia no restaura el verificador ni los comandos de la tarea. Se documenta que el arranque por línea de comandos no carga tareas hoy.

Precisiones obligatorias de Q1 (son requisitos FR-028 a FR-034):

- Las credenciales de URL se ocultan con la redacción existente del núcleo antes de guardar; los resultados de herramientas ya vienen recortados por el límite existente.
- Un rechazo se guarda con su texto estándar **sin el motivo** (se respeta HU-05-04: el motivo no llega a disco). Al reanudar, el modelo ve un rechazo sin motivo; queda documentado.
- La tabla guarda solo mensajes reales (de la persona, del asistente y de herramienta): ni el bloque esencial, ni los mensajes provisionales, ni el resumen, ni el mensaje de salida del verificador.
- La compactación solo reemplaza la vista en memoria, así que la tabla conserva todos los mensajes y el suscriptor sigue los mensajes por identidad.
- Qué mensajes cubre un resumen se define por una relación con los rangos de eventos marcados; el plan la fija y la demuestra con una prueba.
- Guardar resultados de herramientas con posibles secretos en disco, sin redacción general (HU-10-02 no existe) y con la base ya protegida frente a las herramientas por la política, es una decisión del PO (tarea humana H4).

Precisiones generales registradas:

- **Corte abrupto**: si el historial reconstruido termina con llamadas de herramienta sin resultado, no se descartan en silencio ni se reenvían inválidas: se añade un resultado sintético marcado como error («la ejecución se interrumpió antes de obtener el resultado; verifique el estado antes de repetirla»), porque la herramienta pudo haberse ejecutado y repetirla duplicaría el efecto (FR-019).
- **Prueba central de AC-01**: el historial reconstruido es igual al historial en memoria que tenía el proceso justo antes de salir, con y sin compactación previa, comparado mensaje a mensaje (SC-001).
- **Misma sesión**: la sesión reanudada continúa en la misma sesión; los eventos nuevos se añaden con el siguiente orden, sin duplicar ni reescribir los anteriores, y el comando de reanudar no modifica nada de lo guardado (FR-015, FR-016).
- **Sesiones sin detalle guardado**: las creadas antes de esta historia dan un error claro, nunca una reconstrucción parcial; una sesión sin mensajes se reanuda como nueva; un identificador inexistente o inválido da el error de la regla 2 sin repetir el texto recibido (FR-002, FR-003, FR-009, FR-021).
- **Comando**: `/reanudar <id>` exige un cambio mínimo de la CLI (área C, para pasar argumentos al comando), sin otro cambio en esa carpeta (H3).
- **Estado guardado**: el estado de la sesión no se usa para saber cómo terminó (nunca se actualiza hoy).
- **Pruebas existentes**: el plan hace una corrida en seco con el esquema 5 provisional (como en HU-02-06.1) y declara la lista completa y exacta de pruebas que cambian (versión, conjunto de tablas, API pública), ejecutándolas antes sin tocar.
- **Una spec y una PR**: las tareas se ordenan (persistir, reconstruir, comando y CLI) y el presupuesto del sprint es una advertencia, no un límite.

Contradicciones halladas al registrar, resueltas con la opción más conservadora (**se avisa**):

- **Igualdad estricta frente al motivo del rechazo.** La prueba central exige que el historial reconstruido sea igual al de memoria, pero el motivo de un rechazo vive en memoria y no se guarda. Se resuelve así: la igualdad es exacta salvo en el resultado de un rechazo que tuvo motivo, donde lo reconstruido es el texto estándar sin motivo; la prueba lo compara con ese texto y lo declara.
- **«Reanudar no modifica nada» frente a la compactación.** Reanudar no escribe nada; la compactación de la primera petición posterior escribe como siempre (resumen, marcas y su evento). Los requisitos distinguen ambos momentos.
- **Sesión de tarea sin elementos guardados (fila huérfana de HU-02-06.1).** Con Q3 = A se rechaza como cualquier sesión de tarea: se reconoce por tener criterios guardados o elementos esenciales, aunque falten estos últimos.
- **Prefijo.** Con Q3 = A solo hay sesiones sin tarea, que no tienen registro de instrucciones: el prefijo es el que la composición actual entrega a una sesión nueva.
- **Corte entre el guardado de un mensaje y el de su evento.** Para no dejar un evento sin su mensaje (que impediría reanudar justo tras un corte), el guardado del mensaje debe ocurrir antes que el del evento; un mensaje al final sin evento es una cola aceptable. Es una nota para el plan (ver Supuestos).
- **Resultado sintético sin evento (hallado en el plan).** Un mensaje de herramienta que solo existe en memoria rompe el emparejamiento por orden y tipo que exige la compactación de HU-02-03, que fallaría cerrada para siempre en esa sesión. Se resuelve con la opción más conservadora que no toca la compactación: el cierre se publica como un resultado real en la primera petición posterior (FR-019). El comando sigue sin escribir.
- **Dos excepciones más a la igualdad con la memoria (hallazgo del plan).** Las credenciales de URL ocultas antes de guardar y una respuesta vacía justo en el corte de una compactación se reconstruyen distinto de la memoria (FR-006). Se declaran y tienen su propia prueba.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04b-historias-estado.md` (HU-03-04). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

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

### Hallazgo verificado: lo que se guarda hoy no basta para reconstruir el historial

Antes de escribir esta spec se comprobó en el código (solo lectura) y en las specs de HU-03-02, HU-02-03 y HU-02-06.1. **Es cierto: los eventos que el bucle publica y el registrador persiste no traen lo necesario para reconstruir los mensajes que el modelo vio.**

| Mensaje del historial | Qué se guarda hoy (en el evento) | Qué falta para reconstruirlo |
|---|---|---|
| Petición de la persona | Evento de mensaje de persona con el texto | Nada (nunca es contenido externo) |
| Respuesta del asistente **con texto** | Evento de mensaje del asistente con el texto, la cuenta de llamadas y si es final | Las llamadas pedidas (identificador, nombre y **argumentos**) y el consumo de tokens |
| Respuesta del asistente **solo con llamadas** (sin texto) | **Ningún evento** | El mensaje entero |
| Respuesta del asistente vacía y sin llamadas | **Ningún evento** | El mensaje entero |
| Petición de herramienta | Evento con el identificador de la llamada y el nombre | Los argumentos (una prueba existente exige que no estén) |
| Resultado de herramienta | Evento con identificador, nombre, si fue error y la categoría | El **contenido del resultado** y si es contenido externo |
| Rechazo con motivo (HU-05-04) | El evento de aprobación resuelta, sin motivo | El motivo vive solo en el resultado de la herramienta en memoria; se decidió no escribirlo en disco ni en eventos |
| Resumen de la compactación (HU-02-03) | Tabla propia de resúmenes con su texto, y marcas de cobertura en los eventos | Nada (ya se guarda aparte) |
| Bloque esencial e instrucciones de una tarea (HU-02-06.1) | Tabla propia, escritura única | Nada (ya se guarda aparte), solo para sesiones de tarea |

Consecuencias que condicionan la historia:

- Con lo guardado hoy se puede reconstruir el **texto** de las peticiones y de las respuestas con texto y el **orden** de los eventos, pero **no** las llamadas a herramientas ni sus resultados. Un historial así sería inválido para el modelo (resultados sin llamada) o estaría mutilado. Por eso la decisión Q1 = B (ver Clarifications) añade el guardado de los mensajes; sin él, el criterio AC-01 no se podría cumplir para sesiones con herramientas.
- Ninguna sesión creada **antes** de que se guarde lo que falta puede reconstruirse completa. Con la decisión Q1 = B, reanudar una sesión anterior a esta historia debe rechazarse con un error claro, no inventarse (ver FR-009).
- El estado de la sesión en el almacén **nunca cambia hoy**: toda sesión queda «activa» (no hay ningún punto que la marque «completada» o «interrumpida»). Lo que sí existe es el evento de interrupción que el bucle publica ante una cancelación. Esta historia no puede apoyarse en el estado guardado para saber cómo terminó una sesión (ver Supuestos).

### Lo que ya existe y lo que cambia

| Pieza existente | Qué aporta | Qué cambia en esta historia |
|---|---|---|
| Persistencia de eventos (HU-03-02) | Guarda cada evento al ocurrir, con orden propio por sesión y tolerancia a cortes; lee una sesión en orden | Se **lee** (el orden y las marcas de cobertura) y no se modifica. Los eventos y su forma **no cambian** (Q1 = B); el detalle de los mensajes se guarda aparte |
| Compactación (HU-02-03) | Estima el contexto antes de cada petición, resume lo antiguo con una llamada aparte, guarda el resumen y marca cada evento cubierto **una sola vez**; falla cerrado si los mensajes en memoria no coinciden con los eventos guardados | Se **reutiliza sin cambios**. Al reanudar se reconstruye la vista que el proceso tenía (resumen vigente y mensajes no cubiertos, Q2 = B) y la compactación corre, como siempre, antes de cada petición, la primera tras reanudar incluida |
| Contexto esencial (HU-02-06.1) | Guarda aparte, para sesiones de **tarea**, el objetivo, las reglas, el ticket, la referencia a los criterios y el registro de las instrucciones; falla cerrado si una sesión con tarea no tiene sus elementos | Se **consulta** solo para reconocer una sesión de tarea y **rechazarla** al reanudar (Q3 = A); no se rearma ningún bloque ni se restaura el verificador |
| Sesión interactiva (CLI y composición) | Mantiene el historial en memoria entre las líneas de la sesión; admite comandos de una línea sin argumentos (`/ayuda`, `/salir`, `/criterios`) | Un comando **con identificador** exige pasar el argumento: cambio mínimo de la CLI (de C) y de la composición; sin otro cambio en la CLI |
| Límites de sesión (HU-01-06) | Contadores en memoria de turnos, tiempo y tokens, por ejecución del programa | Sin cambios; qué pasa con ellos al reanudar está en los Supuestos |
| Bucle del agente | Valida que el historial recibido tenga mensajes de sistema solo como prefijo y que cada grupo de llamadas esté contestado; publica los eventos | **Sin cambios** (Q1 = B); solo lectura en esta historia |
| Catálogo de eventos | 17 tipos, uno de interrupción | Sin cambios (ver Supuestos) |
| Detalle de mensajes (nuevo) | No existe | Tabla propia, aditiva (esquema 5), alimentada por la composición; es de B y necesita el visto bueno de C para el cableado |

### User Story 1 - Reanudar una sesión anterior y continuar donde quedó (Priority: P1)

El operador escribe, en una sesión interactiva, el comando de reanudar con el identificador de una sesión guardada. El sistema carga lo guardado, reconstruye el historial tal como el modelo lo vio y la siguiente petición del operador se responde con ese contexto, como si la sesión no se hubiera cerrado.

**Why this priority**: es el valor de la historia (AC-01): no repetir lo que ya se le dijo al agente.

**Independent Test**: con una sesión simulada que tuvo peticiones, respuestas con texto, llamadas a herramientas con resultados y contenido externo, comparar, con y sin compactación previa, el historial reconstruido con el historial en memoria que el proceso tenía justo antes de salir, mensaje a mensaje; y reanudarla con un proveedor simulado comprobando que la primera llamada recibe ese historial más la petición nueva.

**Acceptance Scenarios**:

1. **Given** una sesión guardada de ayer con varias peticiones y herramientas, **When** la reanudo por su identificador y escribo una petición nueva, **Then** el proveedor simulado recibe el historial reconstruido (mismos mensajes, mismo orden, mismas llamadas con sus argumentos y mismos resultados) seguido de la petición nueva, con la única excepción declarada de un rechazo con motivo, que se ve sin motivo.
2. **Given** una sesión reanudada, **When** el agente responde, **Then** los eventos nuevos se guardan en **esa misma sesión** a continuación de los anteriores, sin crear una sesión nueva para la conversación.
3. **Given** una sesión guardada que contenía contenido externo (resultado de leer un archivo), **When** se reanuda, **Then** ese contenido sigue marcado como externo en el historial reconstruido.

---

### User Story 2 - Error claro cuando el identificador no existe o no es válido (Priority: P1)

Si el identificador no corresponde a ninguna sesión, el operador recibe un error claro en español y puede seguir trabajando en la sesión actual, que no se altera.

**Why this priority**: es la regla de negocio 2 y evita que un error de tecleo termine el programa o reanude otra sesión.

**Independent Test**: probar con un identificador inexistente, uno vacío, uno con caracteres raros, uno muy largo y uno de otra sesión de un archivo de otra versión del esquema; en todos, el mensaje es fijo, no reproduce lo escrito y la sesión actual sigue operativa y sin cambios.

**Acceptance Scenarios**:

1. **Given** un identificador que no existe, **When** lo uso con el comando de reanudar, **Then** veo un mensaje claro de que no existe esa sesión, sin el texto que escribí, y el historial y los eventos de la sesión actual no cambian.
2. **Given** el comando sin identificador, **When** lo ejecuto, **Then** veo una línea de uso con el formato del comando y no se reanuda nada.
3. **Given** un identificador con saltos de línea, caracteres de control o más de la longitud posible de un identificador, **When** lo uso, **Then** recibo el mismo mensaje fijo de identificador no válido y nada se consulta con ese texto sin validarlo.
4. **Given** una sesión creada con una tarea (con bloque esencial o con criterios guardados), **When** la intento reanudar, **Then** veo un mensaje claro y fijo de que las sesiones de tarea no se pueden reanudar todavía, sin su contenido, y no se reanuda ni se ejecuta nada.
5. **Given** una sesión creada antes de esta historia (con mensajes pero sin detalle guardado), **When** la intento reanudar, **Then** veo un mensaje claro y fijo de que no se puede reanudar y no se reconstruye nada a medias.

---

### User Story 3 - Compactar al reanudar si el contexto supera el umbral (Priority: P1)

Si el contexto reconstruido supera el umbral del modelo, se compacta antes de continuar, con las mismas reglas y la misma tolerancia a fallos que en una sesión viva (AC-02). No hay un camino de compactación propio de la reanudación: la compactación existente corre antes de cada petición, y la primera petición tras reanudar no es una excepción (tampoco si cambió el modelo o la configuración desde que se guardó la sesión).

**Why this priority**: es el segundo criterio de aceptación y sin él una sesión larga reanudada no cabría en la ventana del modelo.

**Independent Test**: con una sesión larga simulada cuyo contexto reconstruido supera el umbral, reanudarla con un proveedor simulado y escribir una petición: comprobar que la llamada de resumen ocurre antes de esa primera petición y solo si corresponde, que el contexto enviado no supera el umbral y que una sesión corta no hace ninguna llamada extra. Repetir con una sesión ya compactada antes y comprobar que el contexto reconstruido es resumen vigente más mensajes no cubiertos.

**Acceptance Scenarios**:

1. **Given** una sesión larga cuyo contexto reconstruido supera el umbral, **When** la reanudo y escribo una petición, **Then** se compacta antes de enviarla y el contexto enviado queda por debajo del umbral (o se avisa una vez si no es posible).
2. **Given** una sesión corta, **When** la reanudo y escribo una petición, **Then** no se hace ninguna llamada de resumen y el contexto enviado es el reconstruido más la petición.
3. **Given** una sesión ya compactada en el proceso anterior, **When** la reanudo, **Then** el contexto reconstruido es el prefijo, la petición inicial, el resumen vigente y los mensajes no cubiertos, y el historial completo sigue guardado sin cambios.
4. **Given** que la llamada de resumen falla, **When** se intenta continuar, **Then** ocurre lo mismo que en una sesión viva: un aviso de causa fija, nada parcial guardado y la persona decide si seguir.

---

### User Story 4 - Un corte abrupto no deja un historial inválido para el modelo (Priority: P2)

Si la sesión terminó a mitad de un turno (el proceso se cerró, se canceló o se cortó la luz), al reanudarla el modelo nunca recibe un historial inválido: ni una llamada a herramienta sin resultado, ni resultados sin su llamada.

**Why this priority**: los cortes son el caso normal que HU-03-02 quiso soportar; reanudar tras uno es el uso real de la historia.

**Independent Test**: simular el corte en cada punto de un turno (tras la petición, tras la respuesta con llamadas, entre dos resultados de un grupo, tras el último resultado) y comprobar que el historial reconstruido es siempre aceptado por la validación del bucle y que lo enviado al modelo nunca contiene una llamada sin resultado.

**Acceptance Scenarios**:

1. **Given** una sesión cortada tras pedirse una herramienta y antes de su resultado, **When** se reanuda, **Then** la llamada queda contestada con un resultado sintético marcado como error que dice que la ejecución se interrumpió antes de obtener el resultado y que se verifique el estado antes de repetirla (la herramienta pudo ejecutarse), y la persona recibe un aviso de que la sesión terminó de forma abrupta.
2. **Given** una sesión cortada tras la petición de la persona y antes de cualquier respuesta, **When** se reanuda, **Then** la petición se conserva y la siguiente petición se envía a continuación.
3. **Given** una sesión con un evento de interrupción, **When** se reanuda, **Then** se avisa de que la sesión se interrumpió y se continúa con el historial válido.

---

### User Story 5 - Reanudar no cambia lo guardado y no duplica eventos (Priority: P2)

Lo ya guardado de la sesión queda intacto al reanudar y cada evento nuevo se añade una sola vez, a continuación de los anteriores.

**Why this priority**: protege el registro histórico (la regla de HU-02-03 de no borrar) y evita que reanudar sea una fuente de corrupción.

**Independent Test**: reanudar y continuar varios turnos; comparar el registro de la sesión antes y después: lo anterior idéntico, lo nuevo a continuación, orden sin huecos ni repetidos.

**Acceptance Scenarios**:

1. **Given** una sesión con N eventos, **When** la reanudo y no escribo nada más, **Then** siguen exactamente los N eventos, sin ninguno nuevo.
2. **Given** una sesión reanudada con dos peticiones nuevas, **When** termino, **Then** los N eventos anteriores son idénticos y los nuevos siguen su orden sin huecos ni repetidos.
3. **Given** una sesión reanudada, **When** se vuelve a reanudar más tarde, **Then** la reconstrucción incluye lo añadido en la reanudación anterior.

---

### User Story 6 - Un aviso breve al reanudar, sin repintar la conversación (Priority: P3)

Al reanudar, la terminal muestra una sola línea de estado (qué se reanudó, cuántos mensajes, si se compactó o si había un corte) y no vuelve a escribir la conversación anterior.

**Why this priority**: la CLI debe confirmar el cambio sin inundar la pantalla; es el último eslabón del comando.

**Independent Test**: reanudar una sesión larga con una terminal simulada y comprobar el texto escrito y que no contiene mensajes del historial.

**Acceptance Scenarios**:

1. **Given** una sesión reanudada con éxito, **When** termina el comando, **Then** la salida es el aviso de estado y el siguiente cursor de entrada, sin los mensajes anteriores.
2. **Given** una sesión reanudada tras un corte, **When** termina el comando, **Then** el aviso incluye que hubo una interrupción.

---

### Edge Cases

- **Identificador inexistente, vacío, inválido, muy largo o con caracteres de control**: mensaje fijo, sin reproducir lo escrito, sin tocar la sesión actual (US2).
- **Sesión sin ningún mensaje** (solo creada): se puede reanudar y empieza como una sesión nueva, con aviso de que no tenía mensajes (Supuestos). No es un error.
- **Sesión creada antes de que se guarde lo que falta (hallazgo)**: una sesión con eventos de mensaje pero sin detalle de mensajes guardado (o con menos mensajes que los que sus eventos implican) da un error claro y fijo de que no se puede reanudar; nunca se reconstruye parcialmente. Una sesión sin ningún evento de mensaje no es este caso (ver «sin ningún mensaje»).
- **Último mensaje de la sesión es una petición sin respuesta**: se conserva; la petición nueva se envía a continuación (dos mensajes de persona seguidos son válidos para el bucle).
- **Llamada de herramienta sin resultado** (corte antes de ejecutarla, durante o antes de guardar el resultado): se contesta con el resultado sintético de FR-019 (US4); se persiste como resultado real en la primera petición posterior. Un grupo de llamadas contestado solo en parte se completa igual, solo las que faltan. Una llamada sin resultado **en medio** del historial (seguida de otro mensaje) es una incoherencia que falla cerrada.
- **Resultado sin llamada o evento fuera de orden** (base dañada o alterada): la reconstrucción falla cerrada con un error fijo; no se envía nada al modelo.
- **Evento dañado en la base**: error fijo de HU-03-02, sin datos.
- **Sesión muy larga** (miles de mensajes): la reconstrucción lee cada mensaje una vez, sin cargar más de lo necesario, y al partir del resumen vigente no depende de una llamada de resumen mayor que la ventana del modelo (Q2 = B).
- **El contexto reconstruido sigue por encima del umbral tras compactar**: se avisa una vez y no se reintenta en bucle (regla de HU-02-03).
- **El modelo o la configuración cambiaron desde que se creó la sesión**: se usa el modelo de la ejecución en curso para el umbral y la compactación existente de la primera petición lo aplica; no se cambia el modelo guardado. Se avisa si el modelo difiere del guardado.
- **Sesión que ya está en uso**: reanudar la sesión que ya es la actual da el error fijo «Esa ya es la sesión actual.» y no escribe nada; reanudarla desde dos procesos a la vez **no se soporta** (los eventos de ambos se intercalarían), no se detecta ni se intenta resolver, y se documenta (ver Supuestos y las observaciones de `PROGRESO.md`).
- **Sesión de tarea** (con bloque esencial o con criterios guardados), con o sin sus elementos completos, incluida la fila huérfana que puede dejar un fallo del segundo guardado de HU-02-06.1: se rechaza con un mensaje fijo que no repite su contenido; nunca se reanuda ni corre sin bloque (Q3 = A).
- **Fallo al leer el almacén en medio de la reconstrucción**: error fijo, la sesión actual sigue sin cambios.
- **El texto del historial o el identificador contienen centinelas o credenciales**: ningún mensaje de error, aviso ni evento los reproduce.
- **Cancelación durante la reconstrucción o la compactación**: se propaga; la sesión actual queda como estaba y nada parcial se guarda.
- **Rechazo con motivo**: lo reconstruido es el texto estándar de rechazo sin el motivo; el modelo no ve el motivo al reanudar.
- **Respuesta del asistente solo con llamadas** (sin evento propio): se guarda al publicarse la petición de su primera herramienta y se reconstruye en su sitio; si el corte llegó antes de ese guardado, el mensaje no existe y la sesión termina como "petición sin respuesta".
- **Mensaje guardado sin su evento** (corte entre ambos guardados): es una cola aceptable; **evento de mensaje sin su mensaje** es una inconsistencia que falla cerrada.
- **El suscriptor se dispara varias veces para el mismo mensaje**: se guarda una sola vez (se siguen por identidad).
- **Fallo al guardar un mensaje en una sesión viva**: se propaga como el del registrador de eventos y no se ignora en silencio.
- **Mensajes que no son de la conversación** (bloque esencial, provisionales, resumen, salida del verificador): nunca entran en la tabla.

## Requirements *(mandatory)*

### Functional Requirements

**Comando y búsqueda**

- **FR-001**: La persona MUST poder reanudar una sesión anterior escribiendo el comando de reanudar seguido del identificador de la sesión, dentro de una sesión interactiva (flujo 1). El comando MUST aparecer en la ayuda.
- **FR-002**: Si el identificador no corresponde a ninguna sesión, el sistema MUST informar con un mensaje claro y fijo en español (regla 2) y MUST dejar intactos la sesión actual, su historial y sus eventos.
- **FR-003**: Un identificador vacío, con caracteres de control, con saltos de línea o más largo que cualquier identificador posible MUST producir un mensaje fijo de uso o de identificador no válido, sin consultar el almacén con el texto sin validar.
- **FR-004**: Ningún mensaje de error, aviso o evento de esta historia MUST reproducir el identificador escrito, ni texto del historial, de la tarea o de una excepción; solo textos fijos (y, a lo sumo, cuentas).

**Reconstrucción del contexto**

- **FR-005**: El sistema MUST cargar lo guardado de la sesión (flujo 2) y reconstruir con ello el historial de mensajes (flujo 3): peticiones, respuestas del asistente con sus llamadas y argumentos, resultados con su contenido y su marca de contenido externo, en el mismo orden en que ocurrieron (AC-01). El detalle de los mensajes sale de su tabla propia (FR-028) y el orden y la cobertura de los resúmenes, de los eventos.
- **FR-006**: El historial reconstruido MUST ser igual, mensaje a mensaje, al historial en memoria que el proceso tenía justo antes de salir (con y sin compactación previa): mismo rol, texto, llamadas (identificador, nombre y argumentos), resultado (contenido y si es error), marca de contenido externo y consumo de tokens. **Excepciones declaradas (tres)**: (1) el resultado de un rechazo que tuvo motivo se reconstruye con el texto estándar sin motivo (FR-032); (2) un texto del original con credenciales de URL se reconstruye con ellas ocultas (FR-031); (3) una respuesta vacía del asistente (sin texto ni llamadas) situada justo antes del corte de una compactación se reconstruye después del resumen y no dentro de él (sin efecto en el emparejamiento ni en el modelo).
- **FR-007**: El historial reconstruido MUST cumplir las mismas condiciones estructurales que el bucle exige al historial que recibe: mensajes de sistema solo como prefijo contiguo, identificadores de llamada no vacíos y únicos, cada grupo de llamadas contestado por completo antes de cualquier otro mensaje.
- **FR-008**: Reanudar MUST NOT volver a publicar los eventos ya guardados ni crear mensajes nuevos de la persona: la reconstrucción es lectura y no pasa por el bus.
- **FR-009**: Una sesión con eventos de mensaje cuyo detalle no se guardó (creada antes de esta historia, o con un guardado que falló) o cuyo detalle tiene menos mensajes que los eventos implican MUST rechazarse con un mensaje claro y fijo de que no se puede reanudar, sin reconstruirla a medias. Esta marca MUST NOT poder saltarse: se rechaza tanto si la marca está en la base como si el guardado falló en esa misma ejecución, y tras un fallo de guardado no se guarda nada más de esa sesión. Una sesión sin ningún evento de mensaje no es este caso (FR-021).
- **FR-010**: Una reconstrucción inconsistente (resultado sin llamada, orden roto, evento dañado) MUST fallar cerrado con un error fijo y MUST NOT enviar nada al modelo.

**Prefijo y sesiones de tarea**

- **FR-011**: El prefijo de mensajes de sistema MUST ser el que la composición actual entrega a una sesión nueva (las sesiones reanudables no tienen tarea y por tanto no tienen registro de instrucciones guardado), (no se avisa de cambios de entorno: no se puede saber, ver Supuestos). El prefijo, el bloque esencial y el resumen MUST NOT guardarse en la tabla de mensajes.
- **FR-012**: Una sesión de tarea (con elementos esenciales o con criterios guardados, completos o no) MUST rechazarse al reanudar con un mensaje fijo que no repite su contenido; MUST NOT reanudarse ni continuar sin bloque, y MUST NOT restaurarse el verificador ni los comandos de la tarea (Q3 = A). El arranque por línea de comandos no carga tareas hoy.

**Umbral y compactación**

- **FR-013**: Tras reconstruir, el contexto MUST ser el que el proceso tenía al salir (Q2 = B): prefijo, petición inicial, resumen vigente (el más reciente de la sesión) y mensajes no cubiertos; sin resumen, el historial completo. El historial completo MUST seguir guardado y reconstruible. La estimación y el umbral por modelo MUST ser los de una sesión viva y, **solo si el contexto los supera**, se compacta antes de continuar (flujo 4, AC-02) mediante la compactación existente, que corre antes de cada petición, la primera tras reanudar incluida (aunque cambien el modelo o la configuración). Si no lo supera, MUST NOT hacerse ninguna llamada ni cambio.
- **FR-014**: La compactación al reanudar MUST ser la de HU-02-03 sin cambiarla: llamada aparte sin herramientas, prefijo y petición inicial protegidos, recientes íntegros, resumen enmarcado como contenido externo con credenciales ocultas, una sola vez por petición, nada parcial si falla, aviso de causa fija. Por ser la misma, la vista reconstruida MUST cumplir la correspondencia por orden y tipo entre mensajes y eventos no cubiertos que esa compactación exige (FR-033); si no la cumple, falla cerrado como en una sesión viva.
- **FR-015**: Reanudar (el comando) MUST NOT escribir, borrar ni modificar nada de lo guardado: ni eventos, ni mensajes, ni resúmenes ni marcas. Lo que escriba la compactación de la primera petición posterior (resumen, marcas de cobertura y su evento) es el comportamiento normal de HU-02-03 y MUST NOT perder ni reescribir los resúmenes anteriores ni sus marcas; tras un corte, la primera petición también añade los resultados de cierre de FR-019 (solo se añade, nunca se modifica ni se borra).

**Continuidad y registro**

- **FR-016**: Tras reanudar, el sistema MUST continuar el trabajo (flujo 5): la siguiente petición de la persona MUST responderse con el contexto reconstruido (o compactado) y los eventos nuevos MUST guardarse en la **misma sesión**, con orden continuo y sin huecos ni duplicados, tratados por el registrador igual que en una sesión viva.
- **FR-017**: Reanudar una sesión MUST NOT cambiar la sesión que se abandona: sus eventos, mensajes y resúmenes quedan tal como estaban y MUST NOT volver a escribirse (ni por el compactador, ni por el guardado de mensajes, ni por ningún otro colaborador); el cambio de sesión MUST NOT dejar suscriptores, titulares ni colaboradores atados a la sesión anterior.
- **FR-018**: Reanudar la sesión que ya es la sesión actual MUST dar un error claro y fijo («Esa ya es la sesión actual.») sin leer ni escribir nada. Reanudar la misma sesión en ejecuciones distintas, o ir a otra y volver, MUST producir el mismo historial reconstruido y 0 eventos nuevos mientras no se haga una petición.

**Cortes abruptos**

- **FR-019**: Una llamada a herramienta sin resultado guardado MUST contestarse al reconstruir con un resultado sintético marcado como error cuyo texto fijo diga que la ejecución se interrumpió antes de obtener el resultado y que se verifique el estado antes de repetirla; MUST NOT descartarse en silencio ni reenviarse sin contestar, porque la herramienta pudo haberse ejecutado y repetirla duplicaría el efecto. La regla MUST ser determinista y aplicarse igual cada vez que se reanude, y el cierre MUST publicarse **una sola vez** por llamada interrumpida (dos reanudaciones seguidas, o reanudar, pedir y reanudar de nuevo, no lo duplican; dos cortes consecutivos se cierran una vez cada uno). El comando de reanudar no escribe nada; en la **primera petición posterior** el cierre MUST publicarse como un resultado de herramienta real (evento de fin de herramienta existente, con error) para que la historia guardada quede coherente y la compactación siguiente no falle cerrada.
- **FR-020**: Ante una sesión cortada a mitad de un turno, o con un evento de interrupción, la persona MUST recibir un aviso de una línea; el modelo MUST recibir solo un historial válido (FR-007).
- **FR-021**: Una sesión sin ningún mensaje MUST poder reanudarse, con un aviso de que no tiene mensajes, y MUST comportarse como una sesión nueva con el prefijo.

**Límites y presentación**

- **FR-022**: Los límites de sesión (turnos, tiempo, tokens) MUST seguir la regla documentada en los Supuestos y MUST NOT eludirse reanudando; reanudar MUST NOT reiniciar a cero un límite ya agotado en la ejecución en curso.
- **FR-023**: Al reanudar, la terminal MUST mostrar una sola línea de estado (cuántos mensajes, si se compactó, si hubo corte) y MUST NOT volver a escribir los mensajes del historial.

**Seguridad y compatibilidad**

- **FR-024**: Todo lo que se guarde para reconstruir MUST tener las credenciales de URLs ocultas antes de guardarse (FR-031) y MUST estar en el almacén ya protegido frente a las herramientas del agente (la política de permisos que lo protege no se relaja). Ningún texto del historial MUST aparecer en eventos, errores ni avisos de esta historia.
- **FR-025**: El cambio de esquema MUST ser aditivo (versión 5): una base de datos de las versiones 1 a 4 MUST abrirse sin perder ninguna fila, las sesiones creadas antes MUST seguir listándose y leyéndose, y la migración MUST probarse con bases reales de cada versión.
- **FR-026**: Los puertos, el bucle, el catálogo de eventos y los dobles de prueba MUST NOT cambiar (Q1 = B), y las pruebas existentes que aseguran que los eventos no llevan argumentos ni el motivo del rechazo MUST NOT tocarse; `core/` MUST seguir sin importar `adapters`, `cli`, `config`, `sqlite3` ni SDKs. Solo se ajustan las pruebas que fijan la versión del esquema, el conjunto de tablas o la API pública, tras ejecutarlas sin tocar.
- **FR-027**: Todo lo que dependa de un modelo MUST poder probarse con el proveedor simulado, sin red, sin claves y sin consola; los cortes MUST poder simularse sin matar procesos salvo la prueba de cierre abrupto real que HU-03-02 ya tiene.

**Persistencia de los mensajes (Q1 = B)**

- **FR-028**: Cada mensaje real de la conversación (de la persona, del asistente y de herramienta) MUST guardarse en su propio registro y en orden, con: rol, contenido, llamadas de herramienta con sus argumentos, resultado (identificador de la llamada, contenido y si es error), si es contenido externo y el consumo de tokens. Se guarda cuando el bus publica el evento correspondiente, leyendo el mensaje del historial en ese instante, y un guardado al cierre del turno cubre la respuesta final vacía y cualquier mensaje aún sin guardar. Una respuesta solo con llamadas se guarda al publicarse la petición de su primera herramienta.
- **FR-029**: La tabla de mensajes MUST contener solo mensajes reales: nunca el bloque esencial, los mensajes provisionales del prefijo, el resumen de compactación ni el mensaje de salida del verificador.
- **FR-030**: La compactación solo reemplaza la vista en memoria; la tabla MUST conservar todos los mensajes. El guardado MUST seguir los mensajes por identidad (no por posición) y guardar cada uno una sola vez aunque se dispare varias veces.
- **FR-031**: Las credenciales de URL MUST ocultarse con la redacción existente del núcleo antes de guardar el contenido y los argumentos. Los resultados MUST guardarse tal como vienen recortados por el límite existente; no se aplica otra redacción general (HU-10-02 no existe, H4).
- **FR-032**: Un rechazo de una herramienta MUST guardarse con su texto estándar **sin el motivo**; al reanudar, el modelo ve un rechazo sin motivo (documentado, HU-05-04).
- **FR-033**: Qué mensajes cubre un resumen MUST quedar definido por una relación explícita con los rangos de eventos marcados (incluidos los mensajes sin evento propio, como la respuesta solo con llamadas); el plan la fija y la demuestra con una prueba, y la reconstrucción de la vista se apoya en ella.
- **FR-034**: El guardado de un mensaje MUST ocurrir antes que el guardado de su evento, de modo que un corte entre ambos deje un mensaje sin evento (cola aceptable) y nunca un evento sin su mensaje. Un fallo al guardar un mensaje MUST propagarse como el del registrador y no ignorarse en silencio.

### Key Entities

- **Sesión guardada**: conversación anterior identificada por un identificador, con su modelo, su meta, su fecha, su estado guardado y su orden de eventos.
- **Detalle de mensajes de la sesión**: registro propio de cada mensaje real (rol, contenido, llamadas con argumentos, resultado, marca de contenido externo, consumo de tokens), en orden, con las credenciales de URL ocultas y sin el motivo de un rechazo. No incluye el bloque esencial, los provisionales, el resumen ni la salida del verificador.
- **Historial reconstruido**: la lista de mensajes que se obtiene de leer lo guardado y que sustituye al historial en memoria al reanudar: prefijo, petición inicial, resumen vigente (si lo hay) y mensajes no cubiertos; sin resumen, el historial completo.
- **Resumen de compactación**: texto guardado aparte (HU-02-03) que cubre un rango de eventos; marca cada evento cubierto como máximo una vez.
- **Sesión de tarea**: sesión con bloque esencial o con criterios guardados (HU-02-06.1, HU-11-01); no se reanuda en esta historia.
- **Corte abrupto**: final de una sesión a mitad de un turno (llamada sin resultado, petición sin respuesta, evento de interrupción).
- **Aviso de reanudación**: la línea de estado que ve la persona.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Con sesiones simuladas que incluyen peticiones, respuestas con texto, respuestas solo con llamadas, resultados normales, de error y externos, con y sin compactación previa, en el 100 % de los casos el historial reconstruido es igual, mensaje a mensaje, al historial en memoria que el proceso tenía justo antes de salir (salvo las tres excepciones declaradas de FR-006) y la primera llamada al proveedor simulado tras reanudar lo recibe seguido de la petición nueva.
- **SC-002**: En el 100 % de los identificadores inexistentes, vacíos, con caracteres de control o excesivamente largos, el resultado es un mensaje fijo en español, 0 mensajes reproducen el texto escrito y el historial y los eventos de la sesión actual son idénticos antes y después.
- **SC-003**: Con una sesión larga simulada cuyo contexto reconstruido supera el umbral, se hace exactamente 1 llamada de resumen antes de la primera petición tras reanudar y el contexto enviado queda por debajo del umbral (o se avisa 1 vez); con una sesión que no lo supera se hacen 0 llamadas de resumen. Con una sesión ya compactada, el contexto reconstruido es resumen vigente más mensajes no cubiertos, en el 100 % de los casos.
- **SC-004**: En un corte simulado en cada uno de los puntos de un turno (como mínimo 5 puntos distintos), 0 peticiones al modelo llevan una llamada sin resultado o un resultado sin llamada, y el historial reconstruido pasa siempre la validación estructural del bucle.
- **SC-005**: Tras reanudar y continuar N turnos, los eventos anteriores son idénticos byte a byte, el orden de los nuevos continúa sin huecos ni repetidos y no hay ninguna fila borrada ni modificada salvo, si se compacta, las marcas de cobertura.
- **SC-006**: Reanudar la misma sesión en dos ejecuciones distintas, o ir a otra y volver, produce historiales reconstruidos idénticos y 0 eventos nuevos mientras no haya una petición; reanudar la sesión activa produce el error fijo y 0 escrituras; el cierre de una llamada interrumpida aparece una sola vez en el 100 % de los casos.
- **SC-007**: Una sesión de 5 000 mensajes se reconstruye y queda lista para continuar, sin contar la llamada de resumen, en menos de 5 segundos en el equipo de integración continua.
- **SC-008**: Con centinelas en el texto del historial, en los argumentos, en los resultados y en el identificador, 0 eventos, 0 mensajes de error y 0 avisos de esta historia los contienen.
- **SC-009**: En el 100 % de las sesiones de tarea (con bloque esencial o con criterios guardados, completas o huérfanas) el intento de reanudar produce el mensaje fijo sin contenido de la tarea y 0 peticiones llegan al modelo.
- **SC-010**: El aviso de reanudación ocupa una línea, no contiene ningún mensaje del historial y aparece en el 100 % de las reanudaciones; reanudar una sesión sin mensajes avisa y empieza limpia.
- **SC-011**: Una base de datos de cada versión anterior (1 a 4) se abre sin perder ninguna fila, las sesiones anteriores se listan y se leen como antes y las pruebas existentes de las dependencias pasan sin cambios, salvo el ajuste declarado de las que fijan la versión del esquema, el conjunto de tablas y la API pública.
- **SC-012**: En el 100 % de los casos, la tabla de mensajes tiene 0 mensajes del bloque esencial, de los provisionales, del resumen y del verificador, y 0 apariciones de una credencial de URL o del motivo de un rechazo, comprobado con centinelas sobre los bytes de la base.
- **SC-013**: En un corte simulado entre el guardado de un mensaje y el de su evento, la sesión sigue siendo reanudable en el 100 % de los casos; con un evento de mensaje sin su mensaje, la reanudación falla cerrada con el mensaje fijo.

## Assumptions

- **Dónde vive el comando (confirmado)**: dentro de la sesión interactiva, con el nombre `/reanudar <id>`, registrado por la composición con el mecanismo de comandos que ya tiene la CLI. Hoy ese mecanismo no pasa argumentos: añadirlo es un cambio mínimo de la CLI (de C, visto bueno) y no se cambia nada más en esa carpeta. El comando de control completo es HU-06-04 (Sprint 4).
- **Arranque con identificador**: reanudar al arrancar el programa con un argumento de línea de comandos queda **fuera de alcance**; la ficha habla de un comando.
- **La sesión actual al reanudar**: la composición crea una sesión nueva al arrancar. Al reanudar otra, la sesión actual **se abandona tal como está** (sus eventos quedan guardados; no se borra) y desde ese momento los eventos nuevos van a la sesión reanudada. Una sesión recién creada y vacía queda en el almacén; limpiarla no se hace aquí.
- **Estado «interrumpida»**: no existe un cambio de estado guardado (siempre «activa»). Esta historia **no escribe** el estado de ninguna sesión; reconoce el corte por lo que está guardado (evento de interrupción o final de turno incompleto), nunca por el estado. Si el equipo quiere que el estado cambie, es otro cambio de almacén (B).
- **Sesión sin mensajes**: se puede reanudar y se trata como una sesión nueva (más conservador que un error: la persona pidió esa sesión y existe).
- **Llamadas sin resultado**: se completan al reconstruir con el resultado sintético de FR-019, marcado como error; la herramienta pudo ejecutarse y repetirla duplicaría el efecto. Se publican como resultados reales en la primera petición posterior (tipo de evento existente, categoría de interrupción); sin eso la compactación de HU-02-03 fallaría cerrada para siempre en esa sesión.
- **Prefijo**: las sesiones reanudables no tienen tarea y por tanto no tienen registro de instrucciones guardado; se usa el prefijo que la composición actual entrega a una sesión nueva, que puede diferir del entorno original (sistema operativo, intérprete, reglas de git). No se puede saber si cambió, así que no se avisa; no se bloquea la reanudación.
- **Límites de sesión (HU-01-06)**: los contadores viven en memoria del bucle de la ejecución del programa y **no se reinician** al reanudar dentro de la misma ejecución (el límite es el presupuesto de toda la ejecución); al reanudar en una ejecución nueva empiezan en cero porque no se persisten (observación del 2026-10-25). Persistirlos queda fuera de alcance. El PO confirma (H5).
- **Una sesión a la vez**: reanudar la misma sesión desde dos procesos a la vez no se soporta ni se detecta; los eventos de ambos se intercalarían. Se documenta y se deja como riesgo.
- **Interpretación de la regla 1 (pendiente de ratificar por el PO y por A)**: «Reanudar usa el historial completo, no el resumen» se entiende como «no se pierde nada al reanudar: el historial completo sigue guardado y reconstruible, y lo que se envía al modelo es la vista que el proceso tenía (resumen vigente y mensajes no cubiertos)». Re-resumir todo en cada reanudación costaría una llamada extra por reanudación y podría no caber en la ventana del modelo.
- **Estado guardado de la sesión**: no se usa para saber cómo terminó una sesión (nunca se actualiza hoy) ni se escribe aquí.
- **Sin tipo de evento nuevo**: el catálogo de 17 eventos no cambia. El comando de reanudar no publica ningún evento; la primera petición tras un corte publica los eventos de fin de herramienta de cierre (tipo existente).
- **Modelo**: el umbral usa el modelo configurado en la ejecución actual; si difiere del de la sesión guardada se avisa; no se cambia lo guardado.
- **Sin cambios de política de permisos**: lo que reanudar lee y escribe pasa por el almacén ya protegido; no se añade ninguna herramienta ni excepción.
- **Pruebas sin red**: proveedor simulado y almacén real en una carpeta temporal; el corte abrupto real reutiliza la técnica de HU-03-02.
- **Fuera de alcance**: reanudar sesiones de tarea y restaurar el verificador, los criterios o los comandos de una tarea (Q3 = A; hoy `main()` no carga tareas); persistir los contadores de límites; cancelar un turno sin cerrar; listar sesiones (HU-03-03); resumen de consumo (HU-03-05); cargar tareas desde la línea de comandos; guardar los comandos de una tarea (observación del 2026-10-26); historias de memoria y de decisiones acumuladas (HU-02-06.2); redacción general de secretos (HU-10-02); cualquier cambio de la política de permisos, del bucle, de los puertos o del catálogo de eventos.
- **Para el plan (no son requisitos)**:
  - **Orden de los suscriptores**: el guardado de mensajes debe suscribirse **antes** que el registrador de eventos para cumplir FR-034 (un corte deja un mensaje sin evento, nunca al revés), y antes de la CLI y de los demás suscriptores que puedan fallar; comprobar el orden real en que la composición suscribe y qué ocurre con el grupo de excepciones del bus si falla un suscriptor.
  - **Qué evento dispara qué guardado**: el mensaje de la persona y el del asistente con texto tras sus eventos; el del asistente solo con llamadas al publicarse la petición de su primera herramienta; el de herramienta tras el evento de fin; y un guardado al cierre del turno para la respuesta vacía. Recordar que el evento de fin se publica después de añadir el mensaje al historial (si falla su publicación, el mensaje ya está).
  - **Seguimiento por identidad**: la compactación sustituye la vista en memoria **in situ** y el resumen y el bloque son mensajes del historial que no deben guardarse; el suscriptor recuerda el último mensaje guardado por identidad y debe ignorar los marcados como resumen o bloque. Definir cómo se detecta cada uno sin tocar el núcleo.
  - **Relación mensaje ↔ eventos** (FR-033): fijar la correspondencia entre los registros de la tabla y los rangos de eventos marcados por un resumen (la compactación empareja mensajes y eventos por orden y tipo; la respuesta solo con llamadas no tiene evento) y demostrarla con una prueba, incluyendo una sesión compactada dos veces.
  - **Colaboradores atados a la sesión**: en la composición actual el compactador, el archivo de compactación, el renovador del bloque y el ejecutor de rondas reciben el identificador de la sesión al componerse; el bucle recibe el identificador en cada petición. Decidir cómo se cambia de sesión (reconstruir esos colaboradores o componer de nuevo) y qué pasa con el contador de límites del bucle y con la sesión vacía que se abandona.
  - **Esquema 5**: tabla aditiva de mensajes (sesión, orden, rol, contenido, llamadas y resultado en una forma que conserve los argumentos, marca externa, consumo), migración desde bases reales de las versiones 1 a 4, e índice por sesión y orden; corrida en seco con el esquema 5 provisional para declarar la lista **completa y exacta** de pruebas que cambian (versión, conjuntos de tablas, API pública), ejecutadas antes sin tocar.
  - **Detección de sesión de tarea**: por elementos esenciales o por criterios guardados; la sesión huérfana de HU-02-06.1 tiene criterios y debe rechazarse.
  - **Detección de sesión anterior a la historia**: eventos de mensaje sin detalle guardado, o menos mensajes que los eventos implican.
  - **Reconstrucción de la vista**: partir del resumen vigente (el más reciente de la sesión) y de los eventos no cubiertos; resultado sintético de FR-019; estimar y dejar que la compactación existente actúe en la primera petición.
  - **Rechazo sin motivo**: guardar el texto estándar de HU-05-03 en lugar del mensaje con motivo; decidir cómo se reconoce un rechazo sin tocar el bucle.
  - **Comando con argumento**: cambio mínimo de la CLI para pasar el texto tras el comando a su función; validar la longitud y los caracteres del identificador antes de consultar.
  - **Guardas**: módulo nuevo del núcleo (si lo hay) con su guarda `ast`; el adaptador de mensajes sin conexión propia (patrón de HU-02-03 y HU-02-06.1); que solo la composición suscribe y reconstruye.
  - **Pruebas**: AC-01 con y sin compactación previa, corte en cada punto de un turno, sesión de 5 000 mensajes, bases reales v1 a v4, centinelas sobre los bytes de la base, sin red.
## Preguntas abiertas

Ninguna. Q1, Q2 y Q3 quedaron resueltas (ver Clarifications). Queda **pendiente de ratificar** por el PO y por A la interpretación de la regla 1 (Q2 = B), y como decisión del PO, no como pregunta bloqueante, guardar en disco el contenido de los resultados de herramientas sin redacción general (H4).

## Dependencias y tareas humanas

- **H1**: **acuerdo de A, B y C sobre Q1 = B y sobre la interpretación de Q2** (cómo se persisten los mensajes sin tocar el bucle ni los eventos, y que «usa el historial completo» se lee como «no se pierde nada»). El usuario actúa como A: se registra como «autorizado por el usuario, pendiente de ratificar».
- **H2**: **visto bueno de B al esquema 5** (tabla de mensajes, migración aditiva desde las versiones 1 a 4) y al modo de leer los resúmenes y las marcas al reanudar.
- **H3**: **visto bueno de C a la CLI** (cambio mínimo para pasar argumentos al comando de reanudar, sin otro cambio en esa carpeta) y **a `bootstrap.py`** (suscriptor de mensajes, cambio de sesión y registro del comando).
- **H4**: el **PO decide** si el contenido de los resultados de herramientas puede guardarse en disco, sin redacción general (HU-10-02 no existe) y con la base ya protegida frente a las herramientas por la política; y los topes de tamaño de lo guardado.
- **H5**: el **PO decide / ratifica** la interpretación de la regla 1 (Q2 = B), que solo se reanudan sesiones sin tarea (Q3 = A), que los contadores de límites no se reinician dentro de la misma ejecución y que una sesión sin mensajes se reanuda como nueva.
- **H6**: **revisión cruzada** por B o C (la historia es de A).
- **H7**: **CI remota** en `ubuntu-latest` y `windows-latest`, con push y PR confirmados por una persona.
- **H8**: **avisos**. **B** (HU-02-03): la compactación al reanudar reutiliza su protocolo sin cambios; **B** (HU-02-06.1): las sesiones de tarea se rechazan al reanudar y la fila huérfana también; **C** (HU-06-04): el comando de reanudar con argumento es el primero que lo necesita; **B** (HU-03-03): el estado guardado de las sesiones nunca cambia, lo que afecta a listar con estado; **A y B** (HU-10-02): ya se guardan resultados de herramientas en disco y la redacción general deberá cubrirlos.
