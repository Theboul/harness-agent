# Feature Specification: HU-02-06.1 — Contexto esencial persistente fuera del historial compactable

**Feature Branch**: `gustavo` (el directorio de la spec es `031-essential-context-block`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-27

**Status**: Borrador (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 2 | **PHU**: 1 | **Responsable**: B — Estado | **Tareas de referencia**: Sp2-18 (2 h), Sp2-19 (1,5 h), Sp2-20 (1,5 h) | **Requisitos**: RF-2.7 | **Depende de**: HU-02-03 (compactación automática, integrada en `main`) y HU-11-01 (tarea con criterios protegidos, integrada en `main`); apoyada en HU-02-01 (prefijo y estimación) y en el diseño SPK-03 (**parcial**: sin corrida con un modelo real, D-IA abierta)

**Input**: User description: "HU-02-06.1 (spec 031). Contexto esencial persistente fuera del historial compactable: qué contiene el bloque esencial y de dónde sale cada parte; que se inyecta íntegro en cada llamada al modelo como contenido propio (no resumible, no editable por el modelo, fuera de la llamada de resumen); cómo convive con el prefijo estable y con el orden del contexto acordado en HU-02-03; qué pasa si el bloque no cabe, si cambia a mitad de tarea (criterios que pasan a cumplidos, instrucciones nuevas) y si no hay criterios; que tras compactar el bloque sigue idéntico; la relación con los mensajes de sistema que el bucle ya admite como prefijo contiguo (sin cambiar el bucle, los puertos ni el catálogo de eventos: si algo lo exigiera, plantearlo como pregunta para A, B y C); la interacción con la reanudación futura (HU-03-04) y con el presupuesto de contexto (el bloque cuenta en el umbral)."

## Clarifications

### Session 2026-10-27

Respuestas del revisor a las dos preguntas de `/speckit-specify`. Ninguna contradice un criterio de aceptación.

- Q: ¿Cada cuándo se renueva el bloque esencial? → A: **A.** Al empezar cada petición de la persona y entre las rondas de verificación de criterios, en la capa de composición. `core/loop.py`, `core/interfaces/` y el catálogo de eventos **no cambian**. **Limitación conocida**: dentro de una misma petición (una tarea larga con muchas llamadas a herramientas) el bloque no se renueva; es la misma limitación que la compactación de HU-02-03 y un único gancho futuro en el bucle resolvería las dos. Ese gancho va como aviso a A en las tareas humanas; **no se decide aquí**.
- Q: ¿Qué son las «instrucciones del sistema» del bloque y cómo conviven con el bloque? → A: **A, con una condición.** Los mensajes de sistema provisionales que la composición ya entrega (aviso de entorno, reglas de git y, si la tarea los declara, comandos de verificación) **siguen exactamente como están y son las instrucciones**. El bloque **no repite su texto** en lo que se envía al modelo: el modelo no recibe nada dos veces. El bloque guarda un **registro** de cuáles son esas instrucciones **únicamente para poder reconstruir desde el almacén** (HU-03-04); ese registro **no se inyecta**. Si hace falta contrastar el costo en tokens, se hace en el plan.
- Resuelto al registrar (opción más conservadora; **se avisa**): una **sesión sin tarea no recibe bloque**. La ficha habla de «la sesión del ticket», y crear un bloque a partir de la primera petición cambiaría el contexto de toda sesión sin tarea (y pruebas existentes que fijan sus mensajes) para duplicar un texto que HU-02-03 ya protege como petición inicial. Si el PO prefiere el bloque también en sesiones sin tarea, es una decisión suya (H4) que obliga a ajustar pruebas existentes.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04b-historias-estado.md` (HU-02-06.1). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

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

### Lo que ya existe y lo que cambia

Se nombran piezas existentes solo como contexto de lo que ya hay y con lo que hay que convivir; los requisitos describen comportamiento.

| Pieza existente | Qué aporta | Qué cambia en esta historia |
|---|---|---|
| Compactación automática (HU-02-03) | Protege la cabeza del historial (los mensajes de sistema iniciales y la petición inicial), resume solo lo antiguo con una llamada aparte y deja intactos el prefijo y los mensajes recientes; reservó el sitio del bloque esencial como un mensaje de sistema del prefijo | Se apoya en ello tal cual: un mensaje de sistema del prefijo ya queda fuera de lo resumido; esta historia **añade** ese mensaje y comprueba que sigue idéntico tras compactar |
| Bucle del agente | Admite mensajes de sistema solo como prefijo contiguo del historial y envía al modelo el historial que recibe en cada llamada | Sin cambios. El bloque es un mensaje de sistema más del prefijo contiguo; se renueva desde la capa de composición (Q1 = A) |
| Prefijo provisional de la composición (aviso de entorno, reglas de git y, si la tarea los declara, comandos de verificación) | Es hoy lo único que el modelo recibe como instrucciones del sistema; ya queda fuera de lo resumido | **Sigue exactamente como está y son las instrucciones** (Q2 = A); el bloque no repite su texto |
| Tarea con criterios protegidos (HU-11-01) | Guarda el objetivo (como meta de la sesión), las reglas y los criterios con su estado en el almacén protegido, con sello y copia de solo lectura; la lectura falla cerrada ante cualquier indicio de alteración | Se **leen** desde su fuente en cada renovación del bloque; esta historia no los copia ni los escribe |
| Hoy **ningún** texto de la tarea (objetivo, reglas, criterios) llega al modelo | El paso 5 del flujo de HU-11-01 («inyecta el objetivo, las reglas y los criterios en el prefijo estable») está sin hacer | El bloque esencial es el lugar donde el modelo los recibe por primera vez (ver supuestos) |
| Verificación automática de criterios (HU-11-04.1) | Solo el harness marca un criterio como cumplido y el aviso al agente nunca muestra el comando del criterio | El bloque refleja el estado de los criterios (pendiente o cumplido) y tampoco muestra comandos |
| Ensamblador y estimación del contexto (HU-02-01) | Estimación de tokens y prefijo estable; **sin cablear** en el bucle | No se cablea aquí; el bloque entra en la estimación cruda que usa el umbral de HU-02-03 |
| Almacén de sesiones (SQLite) y su protección | Guarda eventos, resúmenes y criterios en una base que la política de permisos ya protege frente a las herramientas del agente | Se añade, de forma aditiva, un almacén propio para el contexto esencial (esquema nuevo, de B) |
| Diseño SPK-03 (`docs/decisiones/SPK-03-compactacion-bloque-fijo.md`) | Las cinco claves del bloque, su posición, que sea idéntico entre ensamblados, que quede fuera de la llamada de resumen y que los criterios se lean de su fuente; límite de tamaño recomendado | Se aplica con **una diferencia**: SPK-03 metía las instrucciones en el bloque; aquí no se repiten (Q2 = A), se registran solo para reconstruir. Sigue **sin validar con un modelo real** |

### User Story 1 - El bloque esencial se guarda aparte y llega íntegro al modelo en cada llamada (Priority: P1)

Al crear la sesión de un ticket el sistema guarda, fuera del historial, el objetivo, las instrucciones, las reglas, el identificador del ticket y la referencia a los criterios, cada uno con su origen. En cada llamada al modelo van completos, como un contenido propio del sistema y antes del historial: el objetivo, las reglas, el identificador y los criterios dentro del bloque, y las instrucciones como los mensajes de sistema provisionales que ya existen. El modelo no recibe nada dos veces.

**Why this priority**: Es el flujo 1 y 2 y la razón de la historia. Sin esto no hay nada que proteger.

**Independent Test**: Con un proveedor simulado que graba lo que recibe, una sesión con tarea, cinco valores centinela distintos (uno por elemento) y varias llamadas al modelo: en cada llamada el contexto lleva el bloque exactamente una vez, con el objetivo, las reglas, el identificador y los criterios completos, y cada instrucción exactamente una vez (como su mensaje de sistema), todo antes de la petición inicial y del resto del historial.

**Acceptance Scenarios**:

1. **Given** una tarea con objetivo, reglas, identificador y criterios, **When** se crea su sesión, **Then** los cinco elementos (incluido el registro de las instrucciones) quedan guardados aparte del historial, cada uno con su clave y su origen.
2. **Given** una sesión con bloque, **When** el agente hace varias llamadas al modelo en una misma petición (con herramientas entre medias), **Then** cada llamada recibe el bloque completo, una sola vez, en la misma posición.
3. **Given** el bloque y el prefijo de sistema que la composición ya entrega, **When** se arma el contexto, **Then** el orden es: mensajes de sistema del prefijo (las instrucciones), bloque esencial, petición inicial, resumen (si lo hay) y mensajes recientes.
4. **Given** el bloque y los mensajes de sistema provisionales, **When** se inspecciona lo que recibe el modelo, **Then** el texto de cada instrucción aparece exactamente una vez y el registro de las instrucciones del almacén no aparece en ningún mensaje.
5. **Given** una sesión **sin** tarea, **When** llega la primera petición de la persona, **Then** no se crea ningún bloque y el contexto es el de hoy: el prefijo y la petición inicial, que la compactación ya protege.
6. **Given** un valor del bloque con un centinela, **When** se inspeccionan los eventos, los mensajes de error y los avisos, **Then** ninguno contiene el valor.
7. **Given** el contenido del bloque, **When** el modelo responde o llama herramientas, **Then** nada de lo que el modelo produce modifica el almacén del bloque (no hay herramienta ni vía que lo escriba).

---

### User Story 2 - La compactación no toca el bloque y este sigue idéntico (Priority: P1)

Cuando HU-02-03 compacta, el bloque queda fuera de lo resumido y fuera de la llamada de resumen, y el contexto reconstruido lo lleva idéntico a como estaba.

**Why this priority**: Es la regla 1 y AC-01; es la garantía que justifica el bloque.

**Independent Test**: Con una sesión larga simulada y dos compactaciones consecutivas, el texto del bloque antes y después de cada una es idéntico byte a byte, ocupa la misma posición, y ninguna de las llamadas de resumen recibió ninguno de los cinco centinelas.

**Acceptance Scenarios**:

1. **Given** una sesión con bloque y objetivo, instrucciones, reglas, identificador y criterios, **When** se compacta, **Then** esos elementos siguen en el prefijo del contexto, idénticos, y no forman parte de lo resumido (AC-01).
2. **Given** una llamada de resumen, **When** se inspecciona su entrada, **Then** no contiene el bloque, ni los mensajes de sistema del prefijo, ni el registro de las instrucciones (salvo que el historial antiguo repita algo por sí mismo, que el prompt de resumen pide no hacer).
3. **Given** dos compactaciones seguidas, **When** se compara el bloque tras cada una, **Then** es idéntico al anterior mientras no hayan cambiado sus fuentes.
4. **Given** un resumen que contiene una copia desactualizada de un criterio, **When** se reconstruye el contexto, **Then** el modelo recibe el estado vigente del criterio desde el bloque y no el del resumen.
5. **Given** un contexto compactado, **When** se compara con el de antes, **Then** el bloque cuenta en la estimación igual que antes y no se resume ni se descarta para hacer sitio.

---

### User Story 3 - Los criterios se leen desde su fuente protegida, no desde una copia (Priority: P1)

El bloque no copia los criterios: guarda su referencia y, en cada renovación, lee su texto y su estado de la fuente protegida de HU-11-01.

**Why this priority**: Es la regla 2 y AC-02. Una copia en el historial o en el resumen podría quedarse vieja o alterada.

**Independent Test**: Con una tarea de tres criterios, se marca uno como cumplido en la fuente protegida y el bloque siguiente lo muestra cumplido sin haber tocado el historial; se altera la fuente y el bloque no se envía con datos viejos.

**Acceptance Scenarios**:

1. **Given** un bloque con la referencia a los criterios, **When** se arma el contexto, **Then** el texto y el estado de cada criterio salen de la fuente protegida, no del historial ni del resumen (AC-02).
2. **Given** un criterio que pasa a cumplido (lo marca el harness), **When** llega el siguiente punto de renovación, **Then** el bloque lo muestra como cumplido y el anterior deja de estar en el contexto.
3. **Given** una fuente de criterios ilegible, ausente o con indicios de alteración, **When** se renueva el bloque, **Then** la petición no se envía al modelo con el bloque viejo: falla cerrada con un mensaje fijo, sin texto de los criterios (regla 4 de HU-11-01).
4. **Given** un criterio, **When** se muestra en el bloque, **Then** aparecen su orden, su descripción y su estado, y **no** su comando de verificación, su condición ni su evidencia.
5. **Given** una sesión sin criterios, **When** se arma el bloque, **Then** no hay sección de criterios (ni encabezado vacío) y los demás elementos siguen presentes.

---

### User Story 4 - Tras compactar, el agente sigue sabiendo el objetivo y las reglas (Priority: P2)

Después de una compactación, una pregunta sobre el objetivo original se responde correctamente porque el contexto que recibe el modelo lo lleva íntegro.

**Why this priority**: Es el flujo 4 y AC-03. P2 porque depende de lo anterior y su prueba con un modelo real queda como tarea humana.

**Independent Test**: Con un proveedor simulado que responde a partir del contexto que recibe, tras compactar dos veces se le pregunta por el objetivo y la respuesta contiene el valor centinela del objetivo; sin el bloque (resumen malo que lo pierde) la misma prueba falla.

**Acceptance Scenarios**:

1. **Given** una sesión compactada, **When** se pregunta por el objetivo original, **Then** el contexto enviado contiene el objetivo íntegro y el proveedor simulado lo responde (AC-03).
2. **Given** un resumen simulado deliberadamente pobre (que pierde el objetivo), **When** se pregunta por el objetivo, **Then** sigue respondiéndose bien gracias al bloque.
3. **Given** una sesión compactada, **When** se pregunta por las reglas de la tarea o el identificador del ticket, **Then** el contexto enviado los lleva íntegros.

---

### User Story 5 - Cambios a mitad de tarea, tamaño y presupuesto de contexto (Priority: P2)

El bloque se renueva cuando cambian sus fuentes, tiene un tamaño acotado, y su tamaño cuenta para el umbral de compactación.

**Why this priority**: Cierra los casos límite que evitan que el bloque se quede viejo, devore la ventana o se ignore en el presupuesto.

**Independent Test**: Se cambia una fuente (un criterio cumplido, un valor nuevo), se comprueba el momento exacto en que el bloque cambia y que no coexisten dos versiones; se prueba un valor demasiado grande (rechazo sin truncar); y se mide que el umbral se cruza antes por exactamente el tamaño del bloque.

**Acceptance Scenarios**:

1. **Given** un cambio en una fuente del bloque, **When** llega el siguiente punto de renovación (el comienzo de la siguiente petición o la siguiente ronda de verificación), **Then** el bloque nuevo **sustituye** al anterior: nunca hay dos bloques en el contexto ni texto viejo acumulado en el historial.
2. **Given** un cambio en una fuente durante una misma petición larga (sin ronda de verificación de por medio), **When** el agente sigue llamando al modelo, **Then** el modelo ve el bloque anterior, completo y coherente, hasta el siguiente punto de renovación (limitación conocida).
3. **Given** un valor del bloque por encima del tope por elemento, **When** se intenta guardarlo, **Then** se rechaza con un mensaje fijo, sin truncarlo en silencio y sin crear una sesión a medias.
4. **Given** un bloque cuyo tamaño estimado supera la parte del umbral que se le permite (por ejemplo, tras cambiar a un modelo de ventana más pequeña), **When** se renueva, **Then** falla cerrada con un mensaje fijo y la petición no se envía; no se trunca ni se resume.
5. **Given** el mismo historial con y sin bloque, **When** se estima el contexto, **Then** la diferencia es el tamaño estimado del bloque y la compactación de HU-02-03 se dispara cuando el total, bloque incluido, supera el umbral.
6. **Given** una sesión reanudada en el futuro (HU-03-04), **When** se reconstruye el contexto, **Then** el bloque y el prefijo de instrucciones se rearman solo desde el almacén (el registro de las instrucciones incluido) y la fuente de criterios, sin depender del resumen ni del historial.
7. **Given** una compactación, **When** termina, **Then** el bloque no ha cambiado de posición ni de contenido, y no se ha publicado ningún evento nuevo por su causa.

---

### Edge Cases

- **Sesión sin tarea**: no hay objetivo, reglas, identificador ni criterios declarados; no se crea bloque y el contexto es el de hoy (la petición inicial, que ya es objetivo y queda protegida por HU-02-03). Decisión conservadora registrada en la sección de aclaraciones; el PO puede preferir otra (H4).
- **Tarea sin reglas o sin identificador**: ese elemento queda ausente; no se inventa un valor ni se deja un encabezado vacío.
- **Tarea sin criterios**: la historia HU-11-01 las rechaza; si aun así no hubiera criterios legibles, el bloque no lleva sección de criterios (no es un error de esta historia).
- **El valor de un elemento supera su tope**: se rechaza al guardarlo, con un mensaje fijo que nombra el elemento y el tope pero no repite el valor.
- **Sesión con tarea sin elementos guardados** (el segundo guardado tras crear la sesión falló, se borraron filas de la base o la base se alteró): falla cerrada; la petición no se envía, el mensaje es fijo y la sesión termina con fallo. Nunca se trata como una sesión sin tarea. Si el guardado falla al arrancar, no queda una sesión activa y usable.
- **El bloque no cabe en la parte del umbral que se le reserva**: falla cerrada, sin truncar ni resumir (regla 1: lo esencial nunca se reescribe).
- **El bloque más el prefijo ya superan el umbral por sí solos**: no hay nada compactable que lo arregle; sigue el comportamiento de HU-02-03 (una compactación por turno, advertencia, sin bucle).
- **Cambio de una fuente a mitad de tarea** (un criterio pasa a cumplido, una regla nueva): el bloque cambia al empezar la siguiente petición o en la siguiente ronda de verificación; mientras tanto el modelo ve el anterior completo y coherente, nunca una mezcla.
- **Instrucciones nuevas a mitad de tarea**: las instrucciones son los mensajes provisionales que la composición arma una vez al empezar; esta historia no ofrece un modo de cambiarlas durante la sesión. Si una historia futura lo ofrece, su registro del almacén debe actualizarse con ellas.
- **Tarea larga con muchas llamadas a herramientas** (limitación conocida de Q1): el bloque no se renueva dentro de una misma petición; un único gancho futuro en el bucle, con el acuerdo de A, resolvería esto y la compactación a la vez.
- **Fuente de criterios con indicios de alteración o no disponible**: falla cerrada; se informa con un mensaje fijo y, si ya existe el evento de alteración de HU-11-01, ese sigue siendo quien lo publica; no se crea un evento nuevo.
- **El resumen o el historial contienen una copia vieja de un elemento** (objetivo, criterios): prevalece el bloque, que va antes y es la versión vigente; el prompt de resumen ya pide no repetirlos.
- **El modelo intenta escribir en el bloque** (pide editar la base de datos, el archivo de criterios o repite texto del bloque como si fuera suyo): la política de permisos y la protección de la base ya lo deniegan; el bloque no se lee del historial, así que repetirlo no lo cambia.
- **Contenido externo en un valor del bloque** (por ejemplo, el cuerpo de un issue de GitHub usado como tarea): se trata como definición de la tarea hecha por la persona que la inicia (HU-11-01); no se amplía ese perímetro de confianza.
- **El texto de una instrucción coincide con un valor del bloque**: no se deduplica entre elementos distintos; lo que no ocurre nunca es que **la misma instrucción** llegue dos veces al modelo (una como mensaje y otra dentro del bloque).
- **Cambio de modelo**: el tamaño permitido del bloque se recalcula con el umbral del modelo nuevo (la conmutación en sí es de HU-07-05).
- **Base de datos de una versión anterior**: recibe el almacén nuevo de forma aditiva; las sesiones antiguas sin bloque siguen funcionando sin él.
- **Sesión reanudada** (HU-03-04): fuera de alcance; esta historia solo garantiza que el bloque se puede rearmar desde su almacén.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST guardar, aparte del historial y de los eventos, cinco elementos esenciales de la sesión de una tarea, cada uno con su clave y su origen (flujo 1): **objetivo** (la meta de la sesión de la tarea), **instrucciones** (el registro de cuáles son los mensajes de sistema que la composición entrega; ver FR-021), **reglas** (las de la tarea), **identificador del ticket** (el que la tarea declare) y **referencia a los criterios** protegidos.
- **FR-002**: Los elementos MUST guardarse al crear la sesión de la tarea (flujo 1). Un elemento que la tarea no declare MUST quedar ausente, no inventado ni vacío. Una sesión sin tarea MUST NOT crear bloque ni elementos.
- **FR-003**: El sistema MUST inyectar en cada llamada al modelo, **íntegros**, el objetivo, las reglas, el identificador y los criterios, como un único contenido propio del sistema (el bloque esencial) y antes del historial (flujo 2): ni resumido, ni truncado, ni repartido. Cada llamada MUST llevar exactamente un bloque. Las instrucciones llegan al modelo como los mensajes de sistema que ya existen (FR-021), no dentro del bloque.
- **FR-004**: El orden del contexto MUST ser: mensajes de sistema del prefijo (las instrucciones), bloque esencial, petición inicial protegida, resumen (si lo hay) y mensajes recientes. El bloque MUST ocupar siempre la misma posición: justo después del último mensaje de sistema del prefijo.
- **FR-005**: La compactación MUST NOT resumir, reescribir, mover ni descartar el bloque (regla 1, AC-01); tras compactar, el bloque MUST ser idéntico, byte a byte, al de antes mientras no cambien sus fuentes (flujo 3).
- **FR-006**: La entrada de la llamada de resumen MUST NOT contener el bloque ni el registro de las instrucciones, ni ninguno de los valores del almacén.
- **FR-007**: El modelo MUST NOT poder escribir, borrar ni reemplazar el bloque: ninguna herramienta ni vía del agente escribe el almacén de lo esencial, que queda protegido como el resto de la base de la sesión. Repetir texto del bloque en una respuesta MUST NOT alterarlo.
- **FR-008**: Los criterios MUST NOT copiarse al bloque (regla 2): el bloque guarda su referencia y, en cada renovación, el texto y el estado de cada criterio MUST leerse de su fuente protegida (AC-02), nunca del historial ni del resumen.
- **FR-009**: De cada criterio el bloque MUST mostrar su orden, su descripción y su estado (pendiente o cumplido) y MUST NOT mostrar su comando de verificación, su condición esperada ni su evidencia.
- **FR-010**: Si la fuente de criterios no se puede leer o muestra indicios de alteración, la renovación MUST fallar cerrada: la petición MUST NOT enviarse al modelo con un bloque viejo ni con criterios tomados del historial, y MUST informarse con un mensaje fijo sin texto de los criterios. Lo mismo MUST ocurrir en una sesión **con tarea** a la que le falten los elementos guardados (el guardado falló, se borraron filas o la base se alteró): MUST NOT tratarse como una sesión sin tarea ni enviarse la petición sin contexto esencial.
- **FR-011**: Una sesión sin criterios MUST producir un bloque sin sección de criterios y sin encabezados vacíos; los demás elementos MUST seguir presentes. Un bloque sin ningún elemento MUST NOT enviarse.
- **FR-012**: El bloque MUST renovarse leyendo de nuevo sus fuentes **al empezar cada petición de la persona y entre las rondas de verificación de criterios**, en la capa de composición, **sustituyendo** al anterior: nunca coexisten dos bloques ni queda texto viejo acumulado en el historial. Dentro de una misma petición el bloque MUST NOT renovarse (limitación conocida: el bucle no ofrece un punto intermedio y no se cambia).
- **FR-013**: Cada elemento MUST tener un tope de tamaño, y el bloque completo MUST tener un tope como parte del umbral del modelo en uso (valores por defecto en los supuestos). Un valor que exceda su tope MUST rechazarse al guardarlo, y un bloque que exceda su parte del umbral MUST fallar cerrado al renovarse; en ambos casos con un mensaje fijo que **nombra el elemento y el tope** (en caracteres o en tokens) pero no su contenido, y sin truncar ni resumir.
- **FR-014**: El tamaño del bloque MUST contarse en la estimación de contexto que HU-02-03 compara con el umbral, sin cambiar esa comparación.
- **FR-015**: El bloque y el prefijo de instrucciones MUST poder rearmarse solo desde su almacén (registro de las instrucciones incluido) y la fuente de criterios, sin el resumen ni el historial (base para HU-03-04).
- **FR-016**: Ninguno de los valores del bloque MUST aparecer en un evento, un mensaje de error ni un aviso de esta historia; los mensajes MUST ser fijos. El catálogo de eventos MUST NOT cambiar y esta historia MUST NOT añadir eventos.
- **FR-017**: El bloque MUST ser un mensaje de sistema dentro del prefijo contiguo que el bucle ya admite; el bucle, los puertos y el catálogo de eventos MUST NOT cambiar (Q1 = A). Si el plan descubriera que cumplir la historia exige cambiarlos, MUST detenerse y plantearse a A, B y C, no decidirse.
- **FR-018**: El almacén de lo esencial MUST añadirse de forma aditiva al esquema existente y MUST migrar sin pérdida las bases de datos de versiones anteriores.
- **FR-019**: Todo lo que dependa de un modelo MUST poder probarse con el proveedor simulado, sin red; la respuesta correcta sobre el objetivo tras compactar (AC-03) MUST comprobarse como «el contexto enviado lo lleva íntegro y un proveedor simulado lo responde».
- **FR-020**: Las pruebas existentes de las historias de las que depende MUST pasar sin cambios, salvo los ajustes declarados y autorizados.
- **FR-021**: Los mensajes de sistema provisionales que la composición entrega hoy (aviso de entorno, reglas de git y, si la tarea los declara, comandos de verificación) MUST seguir exactamente como están y MUST ser las instrucciones del sistema. El texto de una instrucción MUST NOT repetirse en el bloque ni en ningún otro mensaje que reciba el modelo. El registro de las instrucciones del almacén MUST usarse solo para reconstruir (FR-015) y MUST NOT inyectarse.
- **FR-022**: La lista de mensajes provisionales que la composición expone (el prefijo con el que arranca cada sesión) MUST NOT cambiar; el bloque se añade al historial de la sesión, no a ese prefijo.

### Key Entities

- **Contexto esencial**: el conjunto de cinco elementos de la sesión de una tarea (objetivo, instrucciones, reglas, identificador del ticket y referencia a los criterios) que se guarda aparte. La ficha lo llama `contexto_esencial`.
- **Bloque esencial**: el mensaje de sistema que se inyecta en cada llamada con cuatro de esos elementos (objetivo, reglas, identificador y criterios). Las instrucciones no van en él: llegan como los mensajes de sistema provisionales que ya existen.
- **Registro de las instrucciones**: el elemento «instrucciones» del almacén; dice cuáles son los mensajes de sistema de la sesión, solo para reconstruir; nunca se inyecta.
- **Elemento esencial**: una clave, su valor y su origen (de dónde salió); inmutable para el modelo.
- **Referencia a los criterios**: el vínculo con la fuente protegida; el bloque muestra lo que esa fuente dice en cada renovación.
- **Punto de renovación**: el momento en que el bloque se vuelve a leer de sus fuentes y sustituye al anterior: el comienzo de cada petición y cada ronda de verificación.
- **Tope del bloque**: el tamaño máximo de cada elemento del bloque y de todo el bloque como parte del umbral.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de las llamadas al modelo de una sesión con bloque, el contexto enviado lleva el bloque exactamente una vez, completo y en la posición acordada, y el texto de cada instrucción exactamente una vez (0 repeticiones).
- **SC-002**: En una sesión larga simulada con al menos dos compactaciones, el bloque y los mensajes de sistema del prefijo son idénticos byte a byte antes y después de cada una en el 100 % de los casos, y los cinco valores centinela (cuatro en el bloque y las instrucciones en su mensaje) siguen presentes.
- **SC-003**: En el 100 % de las llamadas de resumen, la entrada no contiene el bloque ni ninguno de los valores del almacén.
- **SC-004**: Tras marcar un criterio como cumplido en su fuente, el bloque siguiente lo muestra cumplido en el 100 % de los casos, y el contexto nunca contiene a la vez el estado nuevo y el viejo.
- **SC-005**: Con una fuente de criterios alterada o ilegible, 0 peticiones llegan al modelo con criterios viejos o tomados del historial, y el 100 % de los casos produce el mensaje fijo. Con una sesión **con tarea** a la que le faltan sus elementos guardados, 0 peticiones llegan al modelo y el 100 % de los casos produce el mensaje fijo de elementos que faltan (nunca se trata como sesión sin tarea).
- **SC-006**: En el 100 % de los intentos con un valor por encima de su tope o con un bloque por encima de su parte del umbral, la operación se rechaza con un mensaje fijo que nombra el elemento y el tope sin su contenido, y 0 valores se truncan.
- **SC-007**: Con centinelas en los cinco elementos y en el historial, 0 eventos, 0 mensajes de error y 0 avisos de esta historia los contienen.
- **SC-008**: La diferencia entre la estimación de contexto con y sin bloque es el tamaño estimado del bloque, y el disparo de la compactación cambia exactamente cuando ese tamaño cruza el umbral.
- **SC-009**: Tras dos compactaciones con un resumen simulado que pierde el objetivo, el proveedor simulado responde correctamente el objetivo, las reglas y el identificador en el 100 % de las preguntas.
- **SC-010**: Una tarea sin reglas ni identificador produce un bloque coherente (0 encabezados vacíos, 0 elementos inventados) y una sesión sin tarea no recibe bloque, en el 100 % de los casos; el contexto de una sesión sin tarea es idéntico al de hoy.
- **SC-011**: Una base de datos con el esquema anterior se abre sin perder ninguna fila y las pruebas existentes de las dependencias pasan sin cambios, salvo los ajustes declarados.

## Assumptions

- **«Cada llamada al modelo»** del flujo 2 se cumple porque el bloque viaja dentro del historial que el bucle envía en cada llamada. Lo que depende de un punto de renovación es **cuándo cambia** su contenido (Q1), no si está presente.
- **Lo que se renueva y cuándo (Q1 = A)**: al empezar cada petición de la persona y entre las rondas de verificación de criterios (HU-11-04.1), en la capa de composición. Dentro de una misma petición el bucle no ofrece un punto intermedio y no se cambia; un único gancho futuro en el bucle (acuerdo de A) resolvería esto y la compactación a la vez. Se avisa a A (H1), sin decidirlo aquí.
- **Las instrucciones** son hoy el aviso de entorno, las reglas de git y los comandos de verificación de la tarea (el prefijo provisional de la composición); la historia HU-02-05 que cita SPK-03 como origen es, en el plan de sprints, otra cosa (compactación pedida por el modelo), así que el origen de las instrucciones se fija aquí (Q2 = A). Su registro en el almacén guarda lo que se envió, para que una reconstrucción dé el mismo prefijo; el plan decide su forma exacta.
- **El objetivo** es la meta de la sesión de la tarea; se guarda una sola vez al crear la sesión. Una sesión sin tarea no tiene bloque: su objetivo es la petición inicial, que ya queda protegida (decisión conservadora; ver aclaraciones y H4).
- **El identificador del ticket** es el que la tarea declare (su título o referencia de issue); cuál de los campos existentes lo aporta se decide en el plan. Sin identificador, el elemento queda ausente.
- **Fuera del bloque**: el contexto o antecedentes libres de la tarea (no están entre los cinco elementos de la ficha) y las decisiones acumuladas (HU-02-06.2). Se mantiene así (coherente con los topes y con la ficha); qué más debería entrar lo decide el PO (H4).
- **La tarea solo llega a una sesión por `compose(task=…)`**: el arranque por línea de comandos aún no carga tareas (igual que HU-11-04.1); esta historia no lo cambia.
- **Topes por defecto (a revisar por el PO)**: cada elemento **del bloque** (objetivo, reglas, identificador y criterios) hasta 8 000 caracteres y el bloque completo hasta el 20 % del umbral del modelo en uso. Un valor o un bloque que los excede se rechaza, nunca se trunca. Los topes no se aplican a los mensajes de sistema provisionales ni a su registro: los genera el harness, no la persona ni el modelo, y no forman parte del bloque; el plan comprueba si conviene sumarlos al 20 %.
- **Los criterios se muestran con su orden, su descripción y su estado**, sin comando, condición ni evidencia, coherente con que el aviso de HU-11-04.1 nunca muestra el comando.
- **El almacén de lo esencial** vive en la misma base que la sesión, ya protegida frente a las herramientas del agente, y se amplía con un esquema nuevo aditivo (cambio de esquema: de B, tarea humana).
- **Sin eventos nuevos**: el catálogo no cambia y la renovación del bloque no publica nada; lo que ya existe (alteración de criterios, fallo del proveedor) sigue donde estaba.
- **Para el plan (no son requisitos)**:
  - **Esquema 4 aditivo** del almacén de sesiones: tabla propia para el contexto esencial (sesión, clave, valor, origen), migración desde los esquemas 1, 2 y 3 probada con bases reales, y los ajustes previsibles de pruebas existentes que fijan la versión 3 (las de HU-02-03 y la prueba del esquema 3) y el conjunto exacto de tablas; se declaran y se autorizan antes de tocarlas.
  - **Convivencia bloque y resumen en el orden del contexto**: el bloque es un mensaje de sistema colocado justo tras los provisionales y antes de la petición inicial, de modo que cae dentro de la cabeza protegida que la compactación ya reconoce (los mensajes de sistema iniciales) sin cambiar su lógica; el resumen sigue siendo un mensaje de usuario externo tras la petición inicial. Hay que dar al bloque una marca fija para localizarlo y sustituirlo, comprobar que ni el estimador ni el reconocimiento del resumen lo confunden, y que no tiene evento propio (los mensajes de sistema no lo tienen).
  - **Dónde se renueva**: en la composición, antes de cada petición y **antes** de la compactación (para que la estimación del umbral incluya el bloque vigente), y en el cierre del turno de cada ronda de verificación, no dentro del código del verificador (protegido). El bloque se inserta al final del prefijo; la lista de mensajes provisionales que expone la composición no cambia (FR-022).
  - **Lectura de criterios**: por el puerto de solo lectura de criterios, inyectado; el núcleo no importa adaptadores. Decidir cómo se informa la falla cerrada en la terminal y si la alteración sigue publicando solo el evento que ya existe.
  - **Costo en tokens**: contrastar en el plan el bloque de cuatro elementos frente a repetir las instrucciones (que no se hace) y medir el tamaño del bloque con una tarea típica frente al 20 % del umbral por defecto (25 600 tokens).
  - **Identificador del ticket**: decidir qué campo de la tarea lo aporta (el título y, en un issue, su número).
  - **Topes**: constantes del núcleo o campos de la sección `[context]` de la configuración (de B).
  - **Guardas**: la guarda de que ningún módulo del núcleo importa el bucle y la del paquete de contexto ya existen; añadir las del adaptador (sin conexión propia, patrón de HU-02-03) y la de que el bloque se renueva solo desde la composición.
  - **Pruebas existentes que fijan el prefijo**: el prefijo provisional queda como está (FR-022), por lo que las pruebas que lo comprueban no cambian; revisar las de sesiones con tarea que cuenten mensajes enviados.
- **La estimación del umbral es la cruda de HU-02-03**; cuando el ensamblador se integre en el bucle, el bloque debería pasar a su prefijo y a la estimación calibrada (observación para A y B).
- **No se valida con un modelo real**: la calidad con que un modelo real usa el bloque (AC-03) y el prompt de resumen quedan para la corrida de SPK-03 (D-IA).
- **Fuera de alcance**: las decisiones acumuladas (HU-02-06.2), reanudar una sesión (HU-03-04), la memoria estructurada (HU-04-03), el comando de compactar a mano (HU-02-04), la compactación pedida por el modelo (HU-02-05), cambios de política de permisos, PD-06, y la integración del ensamblador en el bucle.
- **Archivos de otra área**: la historia es de B (almacén de lo esencial y su esquema, contexto); el cableado en la composición es de C (visto bueno); el bucle, los puertos y el catálogo de eventos no cambian.

## Preguntas abiertas

Ninguna. Q1 y Q2 quedaron resueltas (ver aclaraciones). Queda como decisión del PO, no como pregunta bloqueante, si las sesiones sin tarea deberían recibir también un bloque (H4).

## Dependencias y tareas humanas

- **H1**: **aviso a A** (sin decidirlo aquí): dentro de una misma petición ni el bloque esencial ni la compactación de HU-02-03 se renuevan; un único gancho en `core/loop.py` antes de cada llamada al modelo resolvería ambas. Cualquier cambio del bucle, de los puertos o del catálogo de eventos necesita el acuerdo de A, B y C; con Q1 = A no hace falta.
- **H2**: visto bueno de B al esquema nuevo de `adapters/storage/` (almacén de lo esencial, migración aditiva) y a lo que toque de `config.py` si se parametrizan los topes; visto bueno de C al cableado en la composición.
- **H3**: revisión cruzada por A o C (la historia es de B).
- **H4**: el **PO decide qué entra al bloque**: los elementos y su origen (las instrucciones son los mensajes provisionales de hoy y no se repiten, Q2), si el contexto libre de la tarea debe entrar, que los criterios se muestren sin comando, los topes por defecto (8 000 caracteres por elemento, 20 % del umbral) y si las sesiones **sin tarea** deberían recibir también un bloque con la primera petición como objetivo (hoy no; cambiarlo obliga a ajustar pruebas existentes).
- **H5**: corrida de SPK-03 con un modelo real cuando D-IA lo permita: comprobar AC-03 («¿cuál era el objetivo original?») y la calidad del resumen con el bloque presente (no bloquea esta historia).
- **H6**: CI remota en `ubuntu-latest` y `windows-latest`, con push y PR confirmados por una persona.
- **H7**: avisos. **A** (HU-11-01): el paso 5 de su flujo (inyectar objetivo, reglas y criterios en el prefijo) estaba sin hacer y lo cubre esta historia; **A y B** (HU-02-01): el ensamblador sigue sin cablear y el bloque debería formar parte de su prefijo cuando se integre; **A** (HU-03-04): el bloque se rearma desde su almacén; **B** (HU-02-06.2): las decisiones acumuladas se añadirán al mismo almacén.
