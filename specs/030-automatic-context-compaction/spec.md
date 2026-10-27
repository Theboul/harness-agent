# Feature Specification: HU-02-03 — Compactación automática por umbral

**Feature Branch**: `gustavo` (el directorio de la spec es `030-automatic-context-compaction`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-27

**Status**: Borrador (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 2 | **PHU**: 5 | **Responsable**: B — Estado | **Tareas de referencia**: Sp2-14 (3 h), Sp2-15 (4 h), Sp2-16 (3 h), Sp2-17 (2 h) | **Requisitos**: RF-2.3, RF-2.4, RNF-3 | **Depende de**: HU-02-01 (estimación y prefijo estable, integrada en `main`) y SPK-03 (diseño de la compactación; **parcial**: sin corrida con un modelo real, D-IA abierta)

**Input**: User description: "HU-02-03 — Compactación automática por umbral (Sprint 2). Lo que pida la ficha, sin inventar; historia grande (5 PHU) dividida en historias de usuario independientes y priorizadas. Convivencia: el objetivo y los criterios protegidos no se pierden ni se alteran al compactar; el prefijo estable se conserva; denegar > preguntar > permitir y los eventos no se debilitan; sin filtrar datos ni credenciales en resúmenes, eventos o errores. Todo lo que dependa de un modelo real, con proveedor simulado y sin red. Fuera: lo que la ficha asigne a HU-02-06.1 y HU-03-04, PD-06 y cambios de política. Si cumplir la ficha exige tocar un puerto, `core/loop.py`, el catálogo de eventos o un archivo de otra área, plantearlo como pregunta."

## Clarifications

### Session 2026-10-27

Respuestas del revisor a las tres preguntas de `/speckit-specify` y cinco precisiones. Ninguna contradice AC-01 ni AC-02.

- Q: ¿Dónde se ejecuta la compactación «al empezar un turno»? → A: **A.** En la capa de composición, antes de entregar cada petición de la persona al bucle; `core/loop.py` no cambia. «Turno» es el inicio de una petición de la persona. **Limitación conocida**: una tarea larga con muchas llamadas a herramientas puede crecer por encima del umbral entre dos peticiones (la acotan el recorte de salidas de HU-02-02 y los límites de sesión). La opción B (un gancho mínimo en el bucle antes de cada llamada al modelo) queda como **mejora futura** con el acuerdo de A.
- Q: ¿Cómo llegan al almacén el guardado del resumen y el marcado de eventos? → A: **B.** Un colaborador pequeño en `core/context/`, definido como protocolo (sin importar `adapters/`), implementado por un adaptador nuevo en `adapters/storage/` con un esquema SQLite **aditivo**: tabla `resumenes` (`evento_desde`, `evento_hasta`, `texto`) y uso de la columna `events.compacted_by` que ya existe. Sin cambios en `core/interfaces/`. Condiciones: (a) guardar el resumen, marcar los eventos cubiertos y publicar `context_compacted` ocurren en **una única transacción atómica**; si algo falla no queda nada parcial; (b) es **idempotente**: compactar sin eventos nuevos no llama al proveedor ni escribe nada; (c) la migración es aditiva y compatible con bases existentes (v1 y v2) sin perder datos; (d) marcar eventos nunca borra ni modifica su contenido (AC-02); (e) la carga de `context_compacted` es `{desde, hasta, eventos}`, sin el texto del resumen. Los cambios de esquema de `adapters/storage/` son del área B (tarea humana).
- Q: ¿De dónde sale el tamaño de ventana de cada modelo? → A: **A.** De `config.toml`, sección opcional `[context]`: ventana por defecto, ventanas por modelo y porcentaje del umbral. Valores por defecto: ventana de **32 000 tokens** para un modelo desconocido (conservador: compactar de más pierde detalle recuperable, desbordar la ventana rompe la tarea), umbral del **80 %** de la ventana, ventana reciente de **como mucho el 30 %** del umbral y **mínimo 4 mensajes**, resumen de **unos 2 000 tokens**. Un valor inválido **detiene el arranque** con un mensaje que no repite el texto recibido. `config.example.toml` lleva la sección comentada con ejemplos de ventanas por modelo. Visto bueno de B a `config.py` y el PO revisa los valores por defecto (tareas humanas).
- Q (precisión): ¿Qué pasa si la llamada de resumen o el guardado fallan? → A: No queda nada parcial, el turno continúa con el contexto sin compactar y el fallo se informa con el evento `provider_error` existente, sin crear un evento nuevo ni filtrar texto.
- Q (precisión): ¿Cuántas compactaciones por turno y qué pasa si sigue sobre el umbral? → A: **Una** por turno. Si tras compactar el contexto sigue por encima del umbral (por ejemplo, con un prefijo enorme) no se reintenta en bucle: el turno sigue y se informa como **advertencia**; es un caso límite.
- Q (precisión): ¿Cuál es el orden del contexto resultante y qué pide el prompt de resumen? → A: Prefijo estable; petición inicial del usuario (protegida); resumen (mensaje marcado como contenido externo, enmarcado, con las credenciales ocultas con `core/redaction.py`); mensajes recientes íntegros. El prompt de resumen se envía **sin herramientas** y pide no repetir contexto esencial ni criterios.
- Q (precisión): ¿Cuenta la llamada de resumen en los límites de sesión? → A: **No** (esos contadores viven en el bucle); queda como observación para A.
- Q (precisión): ¿Cuándo se recalcula el umbral? → A: Al cambiar de modelo (V-10); la conmutación en sí es de HU-07-05.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04b-historias-estado.md` (HU-02-03). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

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

### Lo que ya existe y lo que cambia

| Pieza existente | Qué aporta | Qué cambia en esta historia |
|---|---|---|
| Estimación de tokens y prefijo estable (HU-02-01): estimador calibrado por sesión, ensamblador del contexto | La estimación del contexto del turno y la entrada del umbral | Se usa tal cual; no se duplica |
| Puerto `Provider` (`complete`) y el proveedor simulado de pruebas | La «llamada aparte» del resumen, sin herramientas, y las pruebas sin red | Sin cambios |
| Evento `context_compacted` (ya está en el catálogo de 17 eventos, sin uso ni carga definida) | El «evento de resumen» del flujo 3 | Se publica uno por compactación con la carga `{desde, hasta, eventos}` (sin texto); el tipo no cambia |
| Tabla `events` con la columna `compacted_by` (esquema de HU-03-01, sin uso) y la tabla `resumenes` prevista en `docs/02-arquitectura.md` §4 | Dónde marcar los eventos cubiertos y dónde guardar el resumen | Se usan con un esquema **aditivo** (tabla `resumenes` y la columna `compacted_by`), un adaptador nuevo en `adapters/storage/` y un colaborador definido como protocolo en `core/context/`; `core/interfaces/` no cambia |
| Diseño SPK-03 (`docs/decisiones/SPK-03-compactacion-bloque-fijo.md`) | Corte seguro, qué entra a la llamada de resumen, borrador del texto de resumen | Se aplica; sigue **sin validar con un modelo real** |
| Redacción de credenciales de URLs (`core/redaction.py`, de coste lineal) | Ocultar credenciales de URLs | Se aplica al resumen antes de guardarlo o usarlo |
| Banderas de contenido externo de los mensajes (`is_external`) | Distinguir lo que no es de confianza | El resumen deriva de contenido que puede ser externo y se marca como tal |
| Capa de composición que envuelve el turno sin tocar el bucle (precedente: el verificador de HU-11-04.1) | Un lugar donde ejecutar algo «al empezar un turno» | La compactación se ejecuta ahí, antes de entregar cada petición al bucle; `core/loop.py` no cambia |
| Límites de sesión (HU-01-06) y recorte de salidas (HU-02-02) | Acotan las sesiones y las salidas que llegan al historial | Sin cambios; la llamada de resumen no cuenta en los límites |
| Configuración (`config.toml`, HU-00-04, área B) | Dónde viven los ajustes del usuario | Sección opcional `[context]` con la ventana por defecto, las ventanas por modelo y los porcentajes |

### User Story 1 - Se compacta solo cuando el contexto supera el umbral del modelo (Priority: P1)

Al empezar un turno el sistema estima el contexto que va a enviar y lo compara con el umbral del modelo en uso. Por debajo del umbral no ocurre nada (ninguna llamada, ningún cambio); por encima se dispara la compactación.

**Why this priority**: Es el paso 1 y 2 del flujo y la regla 2 (el umbral por modelo). Sin esto no hay disparo automático.

**Independent Test**: Con un historial de tamaño conocido y dos modelos con ventanas distintas, el mismo historial dispara la compactación en uno y no en el otro; por debajo del umbral el proveedor simulado no recibe ninguna llamada.

**Acceptance Scenarios**:

1. **Given** un contexto estimado por debajo del umbral, **When** empieza un turno, **Then** no se hace ninguna llamada de resumen y el historial no cambia.
2. **Given** un contexto estimado por encima del umbral, **When** empieza un turno, **Then** se dispara la compactación antes de que el turno llame al modelo.
3. **Given** dos modelos con ventanas distintas, **When** se calcula el umbral, **Then** cada uno tiene el suyo (regla 2); si el modelo cambia, el umbral se recalcula con el del modelo nuevo.
4. **Given** una sesión recién compactada, **When** empieza el turno siguiente sin que el contexto haya vuelto a crecer por encima del umbral, **Then** no se vuelve a compactar.
5. **Given** un modelo sin ventana configurada, **When** se calcula el umbral, **Then** se usa la ventana por defecto de 32 000 tokens y el 80 % de ella.
6. **Given** una sección `[context]` con un valor inválido, **When** arranca el sistema, **Then** el arranque se detiene con un mensaje claro que no repite el texto recibido.
7. **Given** una configuración sin la sección `[context]`, **When** arranca el sistema, **Then** funcionan los valores por defecto.

---

### User Story 2 - Lo antiguo se resume con una llamada aparte y lo reciente queda íntegro (Priority: P1)

La compactación pide a un modelo, en una llamada separada del turno del agente y sin herramientas, que resuma lo antiguo. Los mensajes recientes y lo protegido no se tocan.

**Why this priority**: Es AC-01 y el propósito de la historia.

**Independent Test**: Con un proveedor simulado que graba lo que recibe y devuelve un resumen guionado, la llamada contiene solo lo antiguo (y el resumen anterior si lo hay); los mensajes recientes del contexto resultante son idénticos a los de antes, byte a byte.

**Acceptance Scenarios**:

1. **Given** un contexto sobre el umbral, **When** se compacta, **Then** el resumen sale de una llamada aparte al proveedor, sin herramientas, distinta de la llamada del turno.
2. **Given** la compactación, **When** se arma la entrada de la llamada, **Then** contiene solo los mensajes antiguos aún no resumidos y el resumen previo; nunca el prefijo de sistema, la petición inicial protegida ni los mensajes recientes.
3. **Given** los mensajes recientes, **When** termina la compactación, **Then** son idénticos a los de antes (AC-01).
4. **Given** una llamada del asistente y los resultados de sus herramientas, **When** el corte caería en medio, **Then** el corte retrocede hasta dejarlos juntos del lado reciente (el contexto nunca tiene un resultado sin su llamada).
5. **Given** una segunda compactación, **When** se resume, **Then** la entrada es el resumen anterior más lo antiguo nuevo, y el contexto lleva un único resumen (el nuevo).

---

### User Story 3 - El turno continúa con el contexto reducido y reconstruido (Priority: P1)

Tras compactar, el contexto que ve el modelo es: prefijo estable, luego el resumen, luego los mensajes recientes. El turno sigue con eso.

**Why this priority**: Es el paso 4 del flujo y lo que hace útil la compactación; sin esto el turno seguiría con el contexto largo.

**Independent Test**: Tras compactar, la primera petición que recibe el proveedor simulado del turno tiene el prefijo, un resumen y los recientes, en ese orden, y su estimación queda por debajo del umbral cuando los recientes caben.

**Acceptance Scenarios**:

1. **Given** una compactación terminada, **When** el turno llama al modelo, **Then** recibe prefijo estable, petición inicial protegida, resumen y mensajes recientes íntegros, en ese orden.
2. **Given** el contexto reconstruido, **When** se estima, **Then** es menor que antes de compactar y, si los recientes caben, queda por debajo del umbral.
3. **Given** que, tras compactar, el contexto sigue por encima del umbral (los recientes o el prefijo por sí solos lo superan), **When** el turno continúa, **Then** no se reintenta la compactación en ese turno y se informa una advertencia.
4. **Given** el prefijo de sistema del contexto, **When** se reconstruye, **Then** es idéntico al de antes de compactar (el prefijo estable se conserva).

---

### User Story 4 - El historial original sigue guardado y los eventos cubiertos quedan marcados (Priority: P1)

Compactar no borra ni modifica nada del historial guardado: se añade un evento de resumen y se marca qué eventos cubre.

**Why this priority**: Es AC-02 y la regla 1 (V-03: reanudar necesita el historial completo).

**Independent Test**: Con un almacén de sesiones en un archivo temporal, antes y después de compactar el número de eventos guardados no baja y el contenido de cada uno es idéntico; los cubiertos llevan la marca del resumen y existe un evento de resumen con el rango.

**Acceptance Scenarios**:

1. **Given** una compactación, **When** termina, **Then** todos los eventos de antes siguen guardados, con el mismo contenido (AC-02).
2. **Given** los eventos cubiertos por el resumen, **When** termina, **Then** quedan marcados con la referencia del resumen y los no cubiertos no se marcan.
3. **Given** una compactación, **When** se consulta el almacén, **Then** hay un evento de resumen con el rango cubierto y la cuenta de eventos, y el texto del resumen guardado en su registro propio.
4. **Given** una compactación que falla a medias (la llamada falla o el almacén no puede guardar), **When** termina, **Then** no queda ninguna marca, resumen ni evento de resumen parciales: el historial y el contexto quedan como estaban, el turno continúa sin compactar y se informa con el evento `provider_error` existente, sin texto.
5. **Given** que guardar el resumen, marcar los eventos y registrar el evento de resumen ocurren en una sola transacción, **When** falla cualquiera de los tres, **Then** no queda ninguno.
6. **Given** una compactación sin eventos nuevos que cubrir, **When** se intenta, **Then** no se llama al proveedor y no se escribe nada (idempotente).
7. **Given** una base de datos de sesiones existente (esquema 1 o 2), **When** se abre con esta versión, **Then** se migra sin perder datos y sus eventos y criterios siguen idénticos.
8. **Given** el evento de resumen, **When** se publica, **Then** su carga es `{desde, hasta, eventos}` y no contiene el texto del resumen.

---

### User Story 5 - Lo protegido y la seguridad no se debilitan (Priority: P2)

Compactar no puede abrir un camino nuevo: ni perder lo esencial, ni dejar entrar contenido no confiable como si fuera del sistema, ni filtrar datos.

**Why this priority**: Es la frontera de seguridad (V-04, V-17); P2 porque no añade capacidad visible pero es obligatoria para cerrar la historia.

**Independent Test**: Con centinelas en el prefijo, la petición inicial, los criterios, una salida externa y una credencial de prueba, tras compactar el prefijo y la petición inicial están intactos, los criterios en el almacén no cambian, el resumen no trae la credencial y ningún evento ni error contiene texto del historial ni del resumen.

**Acceptance Scenarios**:

1. **Given** los mensajes de sistema del prefijo y la petición inicial del usuario, **When** se compacta, **Then** no entran a la llamada de resumen, no se resumen ni se alteran.
2. **Given** los criterios protegidos de la tarea, **When** se compacta, **Then** la compactación no los lee ni los escribe (siguen solo en su fuente protegida).
3. **Given** un resumen que contiene una URL con credenciales, **When** se guarda o se usa, **Then** las credenciales están ocultas.
4. **Given** que el historial incluye contenido externo (salidas de comandos, archivos), **When** el resumen entra al contexto, **Then** va marcado como contenido externo y enmarcado, no como instrucción del sistema.
5. **Given** cualquier compactación, **When** se publican eventos o se informa un error, **Then** solo llevan el rango, la cuenta y una causa fija; nunca el texto del resumen, del historial ni de la excepción.
6. **Given** las reglas de permisos, **When** se compacta, **Then** no se añade ninguna herramienta ni se cambia ninguna decisión de permisos (denegar > preguntar > permitir sigue igual).

---

### Edge Cases

- **Contexto justo en el umbral**: se compara con «supera»; igualar no dispara.
- **Sesión sin nada antiguo que resumir** (todo es protegido o reciente): no se llama al modelo.
- **Resumen vacío, no texto o demasiado largo**: se rechaza sin cambios (el turno continúa sin compactar); un resumen que excede su tope se rechaza.
- **La llamada de resumen o el guardado fallan** (error del proveedor, tiempo agotado, base de datos): no se cambia nada; el error se informa con el evento `provider_error` existente, sin texto, y el turno continúa con el contexto sin compactar (el proveedor puede fallar por su cuenta); la cancelación se propaga.
- **Falla la publicación del evento de resumen** (un suscriptor del bus falla) **después** de guardar: no es un fallo de compactación; no se deshace ni se reintenta nada, el turno continúa con el contexto compacto y se informa con un aviso de texto fijo (R16).
- **Sigue sobre el umbral tras compactar** (los recientes o un prefijo enorme no caben): una sola compactación por turno, sin reintento en bucle; el turno sigue y se informa una advertencia.
- **Tarea larga entre dos peticiones** (limitación conocida de Q1): una tarea con muchas llamadas a herramientas puede crecer por encima del umbral sin que se compacte hasta la petición siguiente; la acotan el recorte de salidas y los límites de sesión; el gancho en el bucle es una mejora futura con el acuerdo de A.
- **Base de datos de una versión anterior**: se migra de forma aditiva; las que no tengan la tabla del resumen la reciben sin tocar lo existente.
- **Cambio de modelo entre turnos**: el umbral se recalcula (la conmutación en sí es de HU-07-05).
- **Mensajes con llamadas de herramientas sin responder** al final del historial: el corte nunca las separa de sus resultados.
- **Compactaciones consecutivas**: cada una cubre solo lo antiguo aún no cubierto; el rango no se solapa con el de la anterior.
- **Resumen con credenciales o instrucciones** (inyección): credenciales ocultas, contenido marcado como externo.
- **Sesión reanudada** (HU-03-04): fuera de alcance; la compactación solo debe dejar el historial completo y los marcadores para que la reanudación los use.
- **Costo de la llamada de resumen**: consume tokens del proveedor; no cuenta en los límites de sesión (observación para A).
- **Valor inválido en `[context]`**: el arranque se detiene antes de abrir nada, con un mensaje que no repite el texto.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Al empezar un turno el sistema MUST estimar el contexto que enviaría al modelo (prefijo, herramientas e historial) con la estimación de HU-02-01 y compararlo con el umbral del modelo en uso (flujo 1).
- **FR-002**: El umbral MUST calcularse por modelo (regla 2) como un porcentaje (80 % por defecto) de la ventana del modelo, y MUST recalcularse si el modelo cambia (V-10). La ventana sale de la configuración: un tamaño por modelo o, para un modelo desconocido, 32 000 tokens.
- **FR-003**: Si la estimación supera el umbral, el sistema MUST compactar antes de llamar al modelo; si no lo supera, MUST NOT hacer ninguna llamada ni ningún cambio (AC-01).
- **FR-004**: El resumen MUST salir de una llamada aparte al proveedor, sin herramientas y distinta de la del turno del agente (AC-01); el texto que se envía MUST pedir no repetir contexto esencial ni criterios. La llamada MUST NOT contar en los límites de sesión.
- **FR-005**: La entrada de la llamada de resumen MUST contener solo los mensajes antiguos aún no resumidos y el resumen previo, si lo hay; MUST NOT contener los mensajes de sistema del prefijo, la petición inicial protegida ni los mensajes recientes.
- **FR-006**: Los mensajes recientes MUST conservarse íntegros e idénticos (AC-01): como mucho el 30 % del umbral y como mínimo 4 mensajes. El corte entre antiguo y reciente MUST NOT separar una llamada de herramienta de sus resultados.
- **FR-007**: Tras compactar, el contexto MUST ser prefijo estable, petición inicial protegida, resumen y mensajes recientes, en ese orden, y el turno MUST continuar con él (flujo 4). El prefijo estable y la petición inicial MUST quedar idénticos.
- **FR-008**: La compactación MUST NOT borrar ni modificar ningún evento del historial guardado (regla 1, AC-02).
- **FR-009**: El sistema MUST publicar un evento de resumen por compactación con la carga `{desde, hasta, eventos}` (rango cubierto y cuenta), sin el texto del resumen, y MUST marcar los eventos cubiertos con la referencia del resumen (flujo 3). Marcar MUST NOT borrar ni modificar el contenido de ningún evento.
- **FR-010**: El texto del resumen MUST guardarse en un registro propio (tabla `resumenes`: desde, hasta y texto) ligado al rango cubierto, fuera de los eventos. El esquema MUST ser aditivo y MUST migrar sin pérdida las bases de datos existentes (esquemas 1 y 2).
- **FR-011**: Guardar el resumen, marcar los eventos cubiertos y registrar el evento de resumen MUST ocurrir en una única transacción atómica; si la llamada de resumen, su validación o el guardado fallan, MUST NOT quedar marcas, resumen, evento de resumen ni cambio de contexto parciales, el turno MUST continuar con el contexto sin compactar y el fallo MUST informarse con el evento `provider_error` existente, sin texto.
- **FR-012**: El resumen MUST validarse (texto no vacío y acotado) y MUST tener las credenciales de URLs ocultas antes de guardarse o de entrar al contexto.
- **FR-013**: El resumen MUST entrar al contexto marcado como contenido externo y enmarcado con un texto fijo que diga que es un resumen de la conversación y no una instrucción del sistema.
- **FR-014**: La compactación MUST NOT leer ni escribir los criterios protegidos de la tarea, MUST NOT añadir herramientas y MUST NOT cambiar ninguna decisión de permisos.
- **FR-015**: Los eventos y los mensajes de error de la compactación MUST NOT llevar texto del historial, del resumen ni de una excepción; solo el rango, la cuenta y una causa fija.
- **FR-016**: Una compactación consecutiva MUST resumir el resumen anterior más lo antiguo nuevo, y el contexto MUST llevar un solo resumen. La compactación MUST ser idempotente: sin eventos nuevos que cubrir MUST NOT hacerse ninguna llamada ni escribirse nada.
- **FR-017**: La compactación MUST ejecutarse como máximo una vez por turno; si tras compactar el contexto sigue por encima del umbral, MUST NOT reintentarse en bucle y MUST informarse una advertencia.
- **FR-018**: Todo lo que dependa de un modelo MUST poder probarse con el proveedor simulado, sin red.
- **FR-019**: La compactación MUST ejecutarse en la capa de composición, antes de entregar cada petición de la persona al bucle; `core/loop.py`, los puertos y el catálogo de eventos MUST NOT cambiar.
- **FR-020**: La configuración MUST admitir una sección opcional `[context]` con la ventana por defecto, las ventanas por modelo y los porcentajes del umbral y de la ventana reciente; sin ella MUST usarse los valores por defecto; un valor inválido MUST detener el arranque con un mensaje que no repite el texto recibido; el archivo de ejemplo MUST llevar la sección comentada.

### Key Entities

- **Umbral del modelo**: el número de tokens a partir del cual el contexto se compacta: el 80 % (por defecto) de la ventana del modelo.
- **Configuración de contexto**: la ventana por defecto (32 000 tokens), las ventanas por modelo, el porcentaje del umbral, el tope de la ventana reciente (30 % del umbral, mínimo 4 mensajes) y el tamaño del resumen (unos 2 000 tokens).
- **Cabeza protegida**: los mensajes de sistema del prefijo y la petición inicial del usuario; nunca entran a un resumen.
- **Ventana reciente**: los últimos mensajes que se conservan íntegros, con un corte que no separa llamadas de herramientas de sus resultados.
- **Resumen**: el texto de la llamada aparte; acotado, sin credenciales de URL, marcado como externo.
- **Marca de compactación**: la referencia que llevan los eventos cubiertos; ligada al resumen y a su rango.
- **Evento de resumen**: el evento `context_compacted` con rango y cuenta, sin texto.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de los turnos que empiezan con una estimación por encima del umbral se hace exactamente una llamada de resumen antes de la llamada del turno; en el 100 % de los que empiezan por debajo, cero.
- **SC-002**: En el 100 % de las compactaciones los mensajes recientes del contexto resultante son idénticos a los de antes, y ninguna llamada de herramienta queda separada de sus resultados.
- **SC-003**: En el 100 % de las compactaciones el número de eventos guardados no baja y el contenido de cada uno no cambia; el 100 % de los cubiertos lleva la marca y el 0 % de los no cubiertos.
- **SC-004**: En el 100 % de las llamadas de resumen, la entrada no contiene el prefijo de sistema, la petición inicial ni los mensajes recientes.
- **SC-005**: Con valores centinela (en el historial, el resumen y una excepción) y una credencial de prueba, 0 eventos, 0 mensajes de error y 0 resúmenes guardados los contienen.
- **SC-006**: En una batería de al menos 10 fallos simulados (llamada, validación, guardado, cancelación), el historial, las marcas y el contexto quedan idénticos a los de antes en el 100 %.
- **SC-007**: En una sesión simulada larga con dos compactaciones consecutivas, el contexto tras cada una queda por debajo del umbral cuando los recientes caben, y el segundo rango no solapa con el primero.
- **SC-008**: Las pruebas existentes de las historias de las que depende pasan sin cambios, salvo los ajustes declarados.
- **SC-009**: En el 100 % de las compactaciones el resumen, las marcas y el evento de resumen quedan guardados juntos o no queda ninguno, comprobado inyectando un fallo en cada uno de los tres pasos.
- **SC-010**: Una base de datos con esquema 1 y otra con esquema 2 se abren con esta versión sin perder ninguna fila, y compactar sin eventos nuevos escribe 0 filas y hace 0 llamadas.
- **SC-011**: El 100 % de los valores inválidos de `[context]` detienen el arranque con un mensaje que no contiene el texto recibido.

## Assumptions

- **«Turno»** en el flujo y en el AC es el inicio de una petición de la persona (una tarea), no cada llamada al modelo del bucle (Q1).
- **La petición inicial protegida** es el primer mensaje del usuario de la sesión (donde vive hoy el enunciado de la tarea). Se conserva junto con los mensajes de sistema porque el bloque esencial (HU-02-06.1) aún no existe; cuando exista, será un mensaje de sistema del prefijo y quedará protegido por la misma regla sin cambiar nada.
- **Valores por defecto** (Q3, a revisar por el PO): ventana de 32 000 tokens para un modelo desconocido, umbral del 80 %, ventana reciente de como mucho el 30 % del umbral y mínimo 4 mensajes, resumen de unos 2 000 tokens.
- **La llamada de resumen consume tokens del proveedor y no cuenta en los límites de sesión** (el contador de HU-01-06 vive dentro del bucle, que no cambia); observación para A.
- **El texto del resumen** (borrador `SUMMARY_PROMPT` de SPK-03) pide conservar decisiones y motivo, estado y pendientes, y no repetir contexto esencial ni criterios; **no está validado con un modelo real** (D-IA abierta). Tras tres compactaciones las decisiones se pierden: lo resuelve HU-02-06.2 (fuera de alcance).
- **Tope del resumen**: se rechaza un resumen que supere el doble del tamaño pedido (4 000 tokens estimados con el valor por defecto); se comprueba sobre el texto sin limpiar, antes de ocultar credenciales.
- **El evento de resumen y la transacción**: el evento `context_compacted` se escribe en la misma transacción que el resumen y las marcas; cómo se evita que el registrador de eventos lo guarde dos veces se resuelve en el plan, sin cambiar el catálogo.
- **Fuera de alcance**: el bloque de contexto esencial y la lectura de criterios desde su fuente (HU-02-06.1), las decisiones acumuladas (HU-02-06.2), reanudar una sesión y reconstruir desde eventos (HU-03-04), el comando de compactar a mano (HU-02-04), la conmutación de proveedor (HU-07-05), el gancho de compactación en el bucle (mejora futura de Q1), la corrida con un modelo real, PD-06 y cualquier cambio de política de permisos.
- **Archivos de otra área**: la historia es de B (esquema de `adapters/storage/`, `config.py`, `core/context/`); el cableado en `bootstrap.py` es de C (visto bueno); `core/loop.py` y `core/interfaces/` no cambian.

## Preguntas abiertas

Ninguna sobre el alcance. La opción B de Q1 (gancho en el bucle) queda como mejora futura con el acuerdo de A.

## Dependencias y tareas humanas

- **H1**: acuerdo de A, B y C sobre la carga del evento `context_compacted` (`{desde, hasta, eventos}`, sin texto), que cierra el hallazgo 3 de SPK-03; y, como mejora futura, acuerdo de A sobre el gancho de compactación en `core/loop.py` (opción B de Q1).
- **H2**: visto bueno de B al cambio de esquema de `adapters/storage/` (tabla `resumenes`, uso de `compacted_by`, migración aditiva desde los esquemas 1 y 2) y a `config.py` (sección `[context]`); visto bueno de C al cableado en `bootstrap.py`.
- **H3**: revisión cruzada por A o C (la historia es de B).
- **H4**: el PO revisa los valores por defecto (ventana de 32 000 tokens, umbral del 80 %, ventana reciente del 30 % y mínimo 4 mensajes, resumen de unos 2 000 tokens), el tratamiento del resumen como contenido externo y que la llamada de resumen no cuente en los límites de sesión.
- **H5**: corrida de SPK-03 con un modelo real cuando D-IA lo permita (calidad del resumen; no bloquea esta historia).
- **H6**: CI remota en `ubuntu-latest` y `windows-latest`.
- **H7**: aviso a A (HU-01-06): la llamada de resumen no cuenta en los límites de sesión; y (HU-03-04) que las marcas y los resúmenes guardados son la base para reconstruir el contexto al reanudar.
- **H8**: aviso a A y a B (HU-02-01, HU-02-06.1): el ensamblador sigue sin cablear y la estimación de esta historia es cruda; debería pasar a la calibrada cuando se integre.
