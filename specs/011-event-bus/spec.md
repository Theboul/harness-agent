# Feature Specification: HU-01-05 — Bus de eventos desacoplado de la interfaz

**Feature Branch**: `011-event-bus` (el trabajo se hace en la rama `gustavo`; el nombre del directorio de la spec no dicta la rama)

**Created**: 2026-10-20

**Status**: Draft

**Proyecto**: HARNESS v2.5 | **Sprint**: 1 | **Responsable**: B — Estado (la implementa Gustavo en nombre de B) | **Tareas de referencia**: Sp1-23 (ya cumplida por HU-00-01), Sp1-24, Sp1-25 | **Requisitos**: RF-1.8 | **Depende de**: HU-00-01

**Input**: User description: "HU-01-05 — Bus de eventos desacoplado de la interfaz. Como equipo de desarrollo quiero que el núcleo emita eventos tipados y no imprima nada, para añadir una interfaz web sin tocar el núcleo. El alcance es una implementación real del bus en memoria (Sp1-24), la prueba con un suscriptor de registro (Sp1-25) y la comprobación de AC-02."

## Clarifications

### Session 2026-10-20

Decisiones ya tomadas por el responsable antes de redactar; no quedó ningún marcador de aclaración pendiente y no se hicieron preguntas.

- Q: ¿Dónde vive el bus real y qué dependencias admite? → A: En `core/`, en un módulo nuevo, solo con biblioteca estándar; no modifica el puerto ni `core/events.py` (FR-001; la ubicación se justifica en Assumptions).
- Q: ¿Cómo se entrega un evento? → A: De forma síncrona, en el orden de suscripción, por tipo exacto; cada manejador recibe el evento inmutable; un tipo sin suscriptores no es un error (FR-002, FR-003).
- Q: ¿Qué pasa si un manejador falla? → A: El bus sigue entregando al resto y al terminar lanza un error agrupado propio en español con todos los errores; las excepciones no ordinarias se propagan de inmediato y sin agrupar; los errores nunca se tragan (FR-010, FR-011).
- Q: ¿Qué ocurre con los manejadores durante una entrega? → A: La lista se copia al empezar cada emisión; la entrega anidada es inmediata y síncrona, sin cola, y queda documentada (FR-005, FR-006).
- Q: ¿Se admiten suscripciones repetidas y qué se valida? → A: El mismo manejador puede suscribirse varias veces (una entrega por suscripción); suscribir y emitir validan de forma estricta con error de tipo en español; no hay desuscripción (FR-004, FR-008, FR-009).
- Q: ¿Cómo se prueba el bus? → A: Un único contrato de pruebas contra el doble y el bus real, indicando qué cláusulas son propias del real; AC-01 con el bucle real de A y un proveedor guionizado; Sp1-25 con el módulo de registro estándar solo en pruebas; AC-02 reutilizando y ampliando las pruebas de arquitectura (FR-015 a FR-018).
- Q: ¿Qué se hace con los fallos ordinarios ya ocurridos cuando un manejador lanza una excepción no ordinaria? → A: **Asumido al redactar, a confirmar por el responsable**: la excepción se propaga sin agrupar, como se decidió, y los fallos ya ocurridos se anotan en ella (tipo y número, sin contenido) para que no se pierdan en silencio (FR-011).

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación y reglas de negocio de la historia (inmutables)

Copiados tal cual de `docs/04a-historias-fundacion.md` (HU-01-05). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

**Reglas de negocio**

1. El núcleo no contiene impresión ni dependencias de la terminal.
2. Los eventos están definidos y tipados en un solo lugar.

**Criterios de aceptación**

- **AC-01 — Eventos emitidos en un turno completo.** Dado un turno completo, cuando corre, entonces el núcleo emite eventos de mensaje, herramienta solicitada, herramienta terminada, aprobación pedida y error.
- **AC-02 — Núcleo sin dependencias de la terminal.** Dado el núcleo, cuando se revisa su código, entonces no contiene llamadas de impresión ni dependencias de la terminal.

### Lo que ya existe y no se toca

El puerto del bus (`core/interfaces/event_bus.py`), los 17 tipos de evento y el evento inmutable (`core/events.py`), el doble de pruebas `RecordingEventBus` (`tests/doubles/`) y el bucle del agente de A (`core/loop.py`) **no se modifican**. La tarea Sp1-23 («definir los tipos de evento») ya la cumplió HU-00-01 y se registra como tal; esta historia no vuelve a definir ningún tipo.

### User Story 1 - Los eventos de un turno llegan a quien se suscriba, sin tocar el núcleo (Priority: P1) [AC-01]

Como equipo de desarrollo, quiero un bus real en memoria que entregue cada evento del núcleo a los suscriptores de su tipo, para que la terminal (o una interfaz web futura) se conecte como suscriptor sin modificar el núcleo.

**Why this priority**: Es el propósito de la historia (RF-1.8) y el criterio AC-01. Hasta hoy solo existe un doble de pruebas; sin un bus real el núcleo no tiene a quién emitir y ninguna interfaz ni el almacén de sesiones (HU-03-02) pueden suscribirse.

**Independent Test**: Se conecta el bucle real de A al bus real, con un proveedor guionizado y herramientas de prueba; un suscriptor por tipo de evento recoge lo que llega durante un turno completo y se comprueba que están los tipos que el bucle emite hoy, en el orden en que se emitieron.

**Acceptance Scenarios**:

1. **Given** un bus con un suscriptor para el tipo de mensaje del asistente, **When** el núcleo emite ese evento, **Then** el suscriptor recibe exactamente ese evento (el mismo objeto inmutable) una vez.
2. **Given** varios suscriptores del mismo tipo, **When** se emite un evento de ese tipo, **Then** reciben el evento de forma síncrona y en el orden en que se suscribieron; los suscriptores de otros tipos no reciben nada (la coincidencia es por tipo exacto).
3. **Given** un evento de un tipo sin ningún suscriptor, **When** se emite, **Then** no ocurre ningún error.
4. **Given** el bucle real con proveedor guionizado y herramientas de prueba, **When** corre un turno completo, **Then** el bus entrega los eventos de mensaje (del usuario y del asistente), herramienta solicitada, herramienta terminada y error del proveedor que el bucle emite hoy, sin que el núcleo imprima ni conozca al suscriptor; los 17 tipos del catálogo son entregables por el bus.
5. **Given** que el bucle de A todavía no emite «aprobación pedida» (llega con HU-05-03, Sprint 2), **When** se evalúa AC-01, **Then** se registra como una observación y no como un incumplimiento de esta historia: el bus ya entrega ese tipo cuando alguien lo emite.
6. **Given** un suscriptor que, mientras recibe un evento, emite otro evento, **When** corre la entrega, **Then** el evento anidado se entrega de inmediato y de forma síncrona (sin cola) a sus suscriptores antes de que termine la entrega del primero; este comportamiento queda documentado.
7. **Given** un suscriptor que, mientras recibe un evento, suscribe otro manejador, **When** corre la entrega, **Then** el nuevo manejador solo recibe los eventos posteriores, nunca el que se está entregando.

---

### User Story 2 - Un suscriptor que falla no oculta nada ni deja a los demás sin evento (Priority: P1)

Como equipo de desarrollo, quiero que un suscriptor que lanza un error no impida que el resto reciba el evento y que el error llegue al emisor, para que un fallo del almacén de sesiones (HU-03-02) o de una interfaz no pase desapercibido.

**Why this priority**: El bucle de A asume que las excepciones de la emisión se propagan (Q4: si falla la publicación de «herramienta solicitada», la herramienta no se ejecuta). Un bus que se tragara errores rompería esa garantía y haría perder eventos sin aviso; uno que se detuviera en el primer error dejaría a los demás suscriptores sin el evento.

**Independent Test**: Con tres suscriptores del mismo tipo, el segundo lanza un error: se comprueba que los tres se invocaron una vez, que la emisión termina lanzando un error agrupado en español con la excepción original y que ninguna excepción se perdió.

**Acceptance Scenarios**:

1. **Given** un suscriptor que lanza una excepción ordinaria, **When** se emite el evento, **Then** el bus sigue entregando el evento a los suscriptores restantes y, al terminar, lanza un error agrupado propio con un mensaje en español que contiene todas las excepciones recibidas, en el orden de entrega.
2. **Given** varios suscriptores que fallan, **When** se emite el evento, **Then** el error agrupado contiene una excepción por cada uno y todos los suscriptores sanos recibieron el evento.
3. **Given** un suscriptor que lanza una excepción que no es ordinaria (cancelación o interrupción de teclado), **When** se emite el evento, **Then** se propaga de inmediato y sin agrupar, y los suscriptores que faltan no reciben el evento.
4. **Given** que ningún suscriptor falla, **When** se emite el evento, **Then** la emisión termina sin error.
5. **Given** un fallo ya ocurrido en un evento, **When** se emite el siguiente, **Then** el bus sigue funcionando con normalidad (un error no deja el bus en un estado roto).
6. **Given** el bucle real conectado al bus con un suscriptor que falla, **When** corre un turno, **Then** el error agrupado llega hasta quien llamó al turno sin que el bucle lo modifique ni lo oculte (Q4).

---

### User Story 3 - El núcleo no imprime ni depende de la terminal (Priority: P2) [AC-02]

Como equipo de desarrollo, quiero una comprobación automática de que ninguna pieza del núcleo imprime ni usa la terminal, para poder añadir una interfaz web sin tocar el núcleo.

**Why this priority**: Es el criterio AC-02 y la regla de negocio 1. Es una barrera barata que protege el desacoplamiento de forma permanente, pero no bloquea el funcionamiento del bus.

**Independent Test**: La comprobación recorre todo el código del núcleo; su detector se prueba con fragmentos sintéticos (cada construcción prohibida se detecta, el código limpio no) y con una copia del núcleo a la que se añade una llamada de impresión.

**Acceptance Scenarios**:

1. **Given** el código del núcleo, **When** se revisa, **Then** ningún módulo llama a la impresión ni a la lectura de la terminal, ni usa la salida o la entrada estándar de la terminal, ni importa bibliotecas de terminal.
2. **Given** un fragmento con una llamada de impresión, una lectura de la terminal, un uso de la salida estándar o la importación de una biblioteca de terminal, **When** lo analiza el detector, **Then** lo señala; con código limpio, no.
3. **Given** que ya existen comprobaciones de arquitectura sobre el núcleo (proveedores externos, solo biblioteca estándar, el bucle sin consola), **When** se añade esta, **Then** no duplica lo que ya cubren: reutiliza su detector y amplía su alcance a todos los módulos del núcleo.
4. **Given** que los tipos de evento se definen solo en `core/events.py`, **When** se revisa el nuevo módulo del bus, **Then** no define ningún tipo de evento propio (regla de negocio 2).

---

### User Story 4 - Una segunda interfaz se suscribe con un suscriptor de registro, y un solo contrato vale para ambos buses (Priority: P2)

Como equipo de desarrollo, quiero probar el bus con un suscriptor de registro y ejecutar el mismo contrato de pruebas contra el doble y contra el bus real, para demostrar que una interfaz nueva solo necesita suscribirse y que el doble sigue siendo fiel.

**Why this priority**: Es la tarea Sp1-25 y el flujo 4 de la historia («una interfaz futura se suscribe sin tocar el núcleo»). El contrato único evita que el doble de pruebas y la implementación real se separen sin que nadie lo note.

**Independent Test**: Un suscriptor de registro (en pruebas) se suscribe a todos los tipos y escribe una línea por evento con el módulo de registro estándar; se corre un turno y se comprueba lo registrado. El mismo contrato se parametriza con las dos implementaciones del bus.

**Acceptance Scenarios**:

1. **Given** un suscriptor que escribe en el registro estándar y está suscrito a los tipos de un turno, **When** corre un turno, **Then** el registro contiene una entrada por evento, con su tipo, y el núcleo no sabe que existe.
2. **Given** el contrato de pruebas del bus, **When** se ejecuta contra el doble y contra el bus real, **Then** ambos cumplen las cláusulas comunes (entrega en orden, por tipo exacto, tipo sin suscriptores, mismo manejador varias veces, 17 tipos, entrega anidada); el contrato indica qué cláusulas aplican solo al bus real (aislamiento de fallos, copia de manejadores, validación estricta).
3. **Given** que no existe un suscriptor de producción, **When** se revisa el código fuente de la historia, **Then** el suscriptor de registro vive solo en las pruebas.

---

### Edge Cases

- **Mismo manejador suscrito varias veces**: se entrega una vez por suscripción (no se deduplica).
- **Manejador no invocable o tipo que no es un tipo de evento al suscribir**: error de tipo en español en el momento de suscribir; no se registra nada. Una cadena que coincide con el nombre de un tipo (por ejemplo, `"user_message"`) tampoco es un tipo de evento válido: se exige el tipo del catálogo.
- **Lo que se emite no es un evento**: error de tipo en español; no se entrega nada.
- **Un manejador emite el mismo tipo que está recibiendo** (recursión): la entrega anidada es inmediata; un manejador que reemite siempre el mismo tipo sin condición de parada produce una recursión infinita que Python detiene con su error de recursión (responsabilidad del suscriptor; no se añade protección).
- **Fallo dentro de una entrega anidada**: el error agrupado del evento anidado se propaga al manejador que lo emitió; si ese manejador no lo captura, cuenta como un fallo de ese manejador en la entrega externa.
- **Excepción no ordinaria tras fallos ordinarios previos**: se propaga de inmediato y sin agrupar; para que los fallos ordinarios ya ocurridos no se pierdan en silencio, se anotan en la excepción propagada (tipo y número de fallos, sin contenido del evento).
- **Contenido del evento y de los errores**: los mensajes del error agrupado nombran el tipo de evento y el número de fallos, pero nunca reproducen la carga del evento, porque puede contener datos sensibles (resultados de herramientas, mensajes).
- **Manejadores que devuelven un valor o una corrutina**: el puerto define los manejadores como funciones síncronas sin resultado; el valor devuelto se ignora y una corrutina devuelta no se espera (fuera de alcance; la entrega asíncrona no forma parte de esta historia).
- **Sin desuscripción**: el puerto no la tiene y no se modifica; los manejadores viven mientras viva el bus.
- **Uso desde varios hilos**: el bus está pensado para el bucle de un solo hilo del agente; no promete seguridad entre hilos (queda documentado).

## Requirements *(mandatory)*

### Functional Requirements

**Entrega**

- **FR-001**: El sistema MUST ofrecer una implementación real en memoria del puerto del bus que no dependa de nada fuera de la biblioteca estándar, que viva en el núcleo en un módulo nuevo y que no modifique el puerto, el catálogo de eventos, el doble de pruebas ni el bucle.
- **FR-002**: El bus MUST entregar cada evento de forma síncrona a los manejadores suscritos a su tipo exacto, en el orden de suscripción, pasando a cada uno el mismo evento inmutable.
- **FR-003**: Emitir un evento de un tipo sin suscriptores MUST NOT ser un error.
- **FR-004**: Un mismo manejador suscrito varias veces MUST recibir el evento una vez por suscripción.
- **FR-005**: El conjunto de manejadores de un tipo MUST fijarse al empezar cada emisión: un manejador suscrito durante una entrega solo recibe los eventos posteriores.
- **FR-006**: Un manejador MUST poder emitir otro evento durante la entrega; la entrega anidada MUST ser inmediata y síncrona, sin cola, y este comportamiento MUST estar documentado.
- **FR-007**: El bus MUST poder entregar los 17 tipos del catálogo.

**Validación**

- **FR-008**: Al suscribir, el bus MUST lanzar un error de tipo con mensaje en español si el manejador no es invocable o si el tipo no es un tipo de evento del catálogo, sin registrar nada.
- **FR-009**: Al emitir, el bus MUST lanzar un error de tipo con mensaje en español si lo recibido no es un evento, sin entregar nada.

**Fallos**

- **FR-010**: Si un manejador lanza una excepción ordinaria, el bus MUST seguir entregando el evento a los manejadores restantes y, al terminar, MUST lanzar un error agrupado propio, con mensaje en español, que contenga todas las excepciones recibidas en el orden de entrega. Los errores MUST NOT tragarse nunca.
- **FR-011**: Las excepciones que no son ordinarias (cancelación, interrupción de teclado y similares) MUST propagarse de inmediato y sin agrupar; los manejadores restantes no reciben el evento y los fallos ordinarios ya ocurridos MUST anotarse en la excepción propagada, sin contenido del evento.
- **FR-012**: Los mensajes de error del bus MUST NOT reproducir la carga del evento; solo nombran el tipo de evento, el número de fallos y la causa de la validación.
- **FR-013**: Un fallo MUST NOT dejar el bus en un estado roto: la siguiente emisión funciona con normalidad y los suscriptores no cambian.
- **FR-014**: El error agrupado MUST llegar sin cambios hasta quien llamó al turno del bucle (Q4); la historia no modifica el bucle.

**Contrato y pruebas**

- **FR-015**: Un único contrato de pruebas MUST ejecutarse contra el doble `RecordingEventBus` y contra el bus real, e indicar qué cláusulas aplican a cada uno (el aislamiento de fallos, la copia de manejadores y la validación estricta son propios del bus real).
- **FR-016**: AC-01 MUST verificarse con el bucle real de A conectado al bus real y un proveedor guionizado, comprobando los tipos que el bucle emite hoy; «aprobación pedida» MUST registrarse como observación pendiente de HU-05-03 (Sprint 2), no como incumplimiento.
- **FR-017**: La prueba con un suscriptor de registro (Sp1-25) MUST usar el módulo de registro estándar y vivir solo en las pruebas; la historia MUST NOT añadir ningún suscriptor de producción.

**Arquitectura**

- **FR-018**: Una comprobación automática MUST verificar que ningún módulo del núcleo llama a la impresión o a la lectura de la terminal, usa la salida, el error o la entrada estándar, ni importa bibliotecas de terminal (AC-02), reutilizando lo que ya cubren las pruebas de arquitectura, con autoprueba del detector.
- **FR-019**: El módulo del bus MUST NOT definir tipos de evento: los tipos y el evento se importan de su única definición (regla de negocio 2).
- **FR-020**: La historia MUST NOT añadir dependencias ni modificar nada de `core/interfaces/`, de `core/events.py`, del bucle, de `tests/doubles/` ni de `docs/archivo/`.
- **FR-021**: Las pruebas de la historia MUST pasar en Windows y en Linux, sin red, sin proveedor real y sin tocar el entorno ni los archivos del usuario.

### Key Entities *(include if feature involves data)*

- **Bus de eventos en memoria**: implementación real del puerto del bus; guarda, por tipo de evento, la lista ordenada de manejadores y entrega de forma síncrona.
- **Manejador (suscripción)**: función que recibe un evento y no devuelve nada; cada llamada a suscribir crea una suscripción, aunque la función se repita.
- **Evento**: registro inmutable ya definido (identificador, sesión, tipo, instante, carga); lo entrega el bus tal cual, sin copiarlo.
- **Tipo de evento**: uno de los 17 del catálogo; define a qué suscriptores llega un evento.
- **Error de entrega**: error agrupado propio, en español, que reúne todas las excepciones ordinarias de los manejadores de una emisión.
- **Suscriptor de registro**: manejador de pruebas que escribe una línea por evento con el módulo de registro estándar.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En un turno completo con el bucle real y el bus real, el 100 % de los eventos que el bucle emite llega a un suscriptor de su tipo, una vez y en el orden de emisión, y aparecen los tipos de mensaje, herramienta solicitada, herramienta terminada y error del proveedor.
- **SC-002**: Los 17 tipos del catálogo se entregan correctamente por el bus real y por el doble (100 % de los tipos en el contrato compartido).
- **SC-003**: Con n manejadores de los que k fallan (0 ≤ k ≤ n), el 100 % de los n recibe el evento exactamente una vez y la emisión lanza un error agrupado con exactamente k excepciones (ninguno si k = 0); en el 100 % de los casos ningún error se pierde.
- **SC-004**: La comprobación de AC-02 encuentra cero usos de impresión, lectura de terminal, salida estándar y bibliotecas de terminal en todos los módulos del núcleo, y su detector señala el 100 % de las construcciones prohibidas de los fragmentos de autoprueba.
- **SC-005**: Ningún archivo protegido cambia: la diferencia respecto a la base de integración de `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/` y `docs/archivo/` es vacía.
- **SC-006**: Las pruebas automatizadas de la historia pasan al 100 % en Windows y en Linux, sin red ni proveedor real.
- **SC-007**: Entregar un evento a diez suscriptores cuesta en promedio menos de 1 ms, de modo que el bus no sea perceptible en el turno del agente.

## Assumptions

- **Contratos base**: La historia usa tal cual los contratos de HU-00-01: el puerto `EventBus` (con `emit` y `subscribe`), `Event` y los 17 `EventType`. No modifica ningún puerto. HU-00-01 sigue `Pendiente de aprobación técnica` en `docs/PROGRESO.md` (Sp1-03); la historia no depende de esa ratificación para implementarse, pero debe producirse antes de pasar HU-01-05 a `Hecha`.
- **Sp1-23 ya cumplida**: `core/events.py` y su prueba del catálogo (HU-00-01) ya definen los 17 tipos y el evento. Se registra en `docs/PROGRESO.md` como cumplida por HU-00-01; no hay tarea nueva.
- **Dónde vive el bus real**: En `core/`, en un módulo nuevo. Según la skill `estructura-carpetas-harness`, el criterio es si el código «cambiaría al cambiar de proveedor, base de datos o interfaz»: un bus en memoria solo con biblioteca estándar no cambia con ninguno de los tres, así que es núcleo y no adaptador (precedente: el registro de herramientas en memoria de HU-01-02 vive en `core/tools/`). Quien lo cree y lo conecte es la raíz de composición, fuera de esta historia.
- **El bus solo emite**: La decisión V-01 fija que el bus es de un solo sentido; la aprobación, que exige respuesta, va por la interfaz `Approver` (HU-05-03). Esta historia no añade respuesta ni valor de retorno a la entrega.
- **Qué emite hoy el bucle**: Mensaje del usuario, mensaje del asistente, herramienta solicitada, herramienta terminada, decisión de permiso, error del proveedor e interrupción. «Aprobación pedida» y «límite alcanzado» no se emiten todavía (HU-05-03 y HU-01-06, Sprint 2); el bucle tiene incluso una prueba de arquitectura que lo impide hoy. AC-01 se verifica con lo que existe y se registra lo pendiente (FR-016).
- **Texto de RF-1.8**: El texto íntegro del requisito no figura en la documentación activa; solo su trazabilidad a HU-01-05. La spec lo interpreta a partir de la historia (eventos tipados al bus, nada impreso por el núcleo).
- **Un solo hilo**: El bus está pensado para el bucle del agente (un solo hilo); no se añaden bloqueos ni garantías entre hilos. Los manejadores son síncronos, como define el puerto.
- **Mensajes de error**: En español, el idioma de trabajo del proyecto; los nombres de tipos de evento se conservan tal cual.
- **Rendimiento**: El umbral de 1 ms de SC-007 es un valor razonable de humo y puede ajustarse si las mediciones lo justifican.
- **Presupuesto**: El plan de sprint asigna 5 h a Sp1-23, Sp1-24 y Sp1-25 (1 + 2,5 + 1,5); como Sp1-23 ya está cumplida, quedan 4 h. La estimación de las tareas se compara con ese presupuesto y se anota como aviso, sin recortar el alcance (Principio VI).
- **Fuera de alcance**: Suscriptor de producción (la CLI y su suscriptor son HU-06-01; el almacén de eventos, HU-03-02); desuscripción; entrega asíncrona o con cola; filtros por varios tipos o comodines; prioridades; reintentos; emisión de «aprobación pedida» y «límite alcanzado»; raíz de composición.
- **Disciplina de proceso**: La historia se limita al Sprint 1 (Principio VI), se verifica con pruebas automatizadas sin red (Principio IV), no altera `docs/archivo/` (Principio X) y se registra en `docs/PROGRESO.md` (Principio VIII).
