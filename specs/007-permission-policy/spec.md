# Feature Specification: HU-05-01 — Política denegar, preguntar, permitir que falla cerrada

**Feature Branch**: `007-permission-policy` (el trabajo se hace en la rama `gustavo`; el nombre del directorio de la spec no dicta la rama)

**Created**: 2026-10-20

**Status**: En revisión (clarificada, 2026-10-21): Q1, Q2 y Q3 resueltas; queda un supuesto pendiente de confirmación del PO (regla de lectura, FR-007)

**Proyecto**: HARNESS v2.5 | **Sprint**: 1 | **Responsable**: C — Control y conexiones | **Tareas de referencia**: Sp1-32, Sp1-33, Sp1-34, Sp1-35, Sp1-36 | **Requisitos**: RF-5.1, RF-5.2, RF-5.3 | **Depende de**: HU-00-01, HU-01-03, HU-01-05

**Input**: User description: "HU-05-01 — Política denegar, preguntar, permitir que falla cerrada. Como usuario operador quiero que cada acción del agente se clasifique en denegar, preguntar o permitir, que lo no previsto pida aprobación, y que el único permiso explícito del Sprint 1 sea escribir dentro del área de trabajo autorizada, para que nada sensible ocurra sin mi control y aun así se pueda demostrar el agente antes de tener la interfaz de aprobación."

## Clarifications

### Session 2026-10-20

Decisiones fijas del encargo antes de redactar. Las 3 preguntas abiertas que dejó la redacción (Q1, Q2 y Q3) se resolvieron en la sesión 2026-10-21 (más abajo) y ya no hay marcadores de aclaración en el texto.

- Fijo: la política usa el puerto que ya existe (`PermissionPolicy.evaluate(call)` devuelve `deny`, `ask` o `allow`) y no lo modifica; el doble `ScriptedPolicy` es la referencia de contrato. La política concreta vive fuera de los puertos, en el área de permisos del núcleo (`core/permissions/`, según el árbol acordado), solo con biblioteca estándar.
- Fijo: «falla cerrada» significa que ante duda, error, configuración ausente o regla desconocida no se permite nada; el detalle caso por caso está en la tabla de la sección «Casos de falla cerrada».
- Fijo: encaja con el bucle de A tal como está: el bucle publica `PERMISSION_DECIDED`, rechaza con `[permission_denied] …` y con `[approval_required_unavailable] …`, y los tests existentes del bucle siguen pasando sin cambios.
- Fijo: toda configuración de reglas sale de `config.py` / `config.toml` (sin secretos y sin leer `.env`); el núcleo no lee archivos ni entorno.
- Fijo: la revisión cruzada por A o B es una tarea humana.

### Session 2026-10-21

Respuestas del revisor a las tres preguntas abiertas; se aplicaron sin preguntar de nuevo y los criterios AC-01 a AC-05 y las reglas de negocio quedan intactos.

- Q: ¿Qué decisión recibe una herramienta de lectura de riesgo bajo en el Sprint 1? → A: Opción B. Se añade UNA regla explícita de permitir: una herramienta de riesgo bajo (solo lectura) cuya llamada incluye `path` y cuya ruta real queda dentro del área autorizada (`AuthorizedArea.contains`); fuera del área o sin área configurada se pregunta; nunca se permiten lecturas en cualquier ruta. Es un **supuesto pendiente de confirmación del PO**, porque amplía el texto «único permiso explícito del Sprint 1» de la historia (que no se modifica); la regla es independiente y puede quitarse sin tocar el resto (FR-007). La tarea de cierre debe dejar una observación en `docs/PROGRESO.md`.
- Q: ¿Cómo sabe la política cuál es el argumento de la ruta de una herramienta de archivos? → A: Opción A. Convención: el argumento de ruta se llama `path`. Una herramienta de riesgo medio que no trae `path` o cuyo `path` no es texto es una llamada mal formada y se deniega (falla cerrada); lo mismo una de riesgo bajo que trae `path` no textual. La convención se documenta en `contracts/path_argument_convention.md` para que HU-01-03 la cumpla y no se toca el puerto de herramienta (FR-012).
- Q: ¿De dónde sale el «motivo» que recibe el modelo? → A: Opción A. La política solo devuelve la decisión; el motivo es el texto genérico que ya redacta el bucle. No se toca `core/loop.py` ni los puertos. Queda registrado como hallazgo para A y para HU-05-03 que ese texto no distingue la causa (fuera del área, sin área, no prevista, riesgo alto) (FR-019).

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación y reglas de negocio de la historia (inmutables)

Copiados tal cual de `docs/04c-historias-control.md` (HU-05-01). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

**Reglas de negocio**

1. Denegar siempre prevalece sobre preguntar y permitir.
2. La política se aplica en el harness, no en el prompt.
3. Las instrucciones halladas en archivos no cambian la política.
4. Borrar archivos, hacer push, merge y deploy siempre requieren aprobación.
5. El permiso de escritura está acotado al área autorizada; no hay regla de «permitir todo».

**Criterios de aceptación**

- **AC-01 — Falla cerrada ante lo no previsto.** Dado una llamada que no coincide con ninguna regla, cuando se evalúa, entonces requiere aprobación manual.
- **AC-02 — Orden de precedencia.** Dado reglas que se contradicen, cuando se evalúan, entonces prevalece el orden denegar, preguntar, permitir.
- **AC-03 — Instrucciones en archivos no alteran la política.** Dado instrucciones en el contenido de un archivo, cuando el modelo las sigue, entonces la política las evalúa igual que cualquier otra llamada.
- **AC-04 — Escritura permitida solo en el área autorizada.** Dado una escritura cuya ruta real queda dentro del área de trabajo autorizada, cuando se evalúa, entonces una regla explícita acotada a esa área la permite; dado cualquier otra ubicación, entonces se pregunta. No existe ninguna regla que permita escribir en cualquier ruta.
- **AC-05 — «Preguntar» provisional en el Sprint 1.** Dado el Sprint 1, sin la interfaz de aprobación ([HU-05-03](04c-historias-control.md#hu-05-03)), cuando una acción resulta en «preguntar», entonces se deniega provisionalmente, el modelo recibe el motivo y la decisión queda registrada como evento; esta resolución provisional se retira cuando [HU-05-03](04c-historias-control.md#hu-05-03) existe.

### Lo que ya existe y no se toca

El puerto de la política, el catálogo de eventos, el bucle de A (que ya publica la decisión y ya resuelve «preguntar» como denegación provisional, `_decide` en `core/loop.py`), el bus y los dobles de pruebas **no se modifican**. Esta historia aporta la política concreta que el bucle recibe por inyección, la clasificación de herramientas por riesgo que esa política consulta y la tabla de reglas configurable.

### User Story 1 - Cada llamada se clasifica y lo no previsto pide aprobación (Priority: P1) [AC-01, AC-02]

Como usuario operador, quiero que cada llamada del modelo se evalúe en el orden denegar, preguntar, permitir y que lo que ninguna regla prevé pida aprobación, para que nada ocurra sin mi control y para que una regla permisiva nunca anule una restrictiva.

**Why this priority**: Es el núcleo de la historia (RF-5.1, RF-5.2) y de la regla de negocio 1. Sin la política concreta el bucle solo tiene dobles: no hay ninguna decisión real que proteja al usuario.

**Independent Test**: Se construye la política con reglas de prueba y se evalúan llamadas construidas a mano (herramienta desconocida, herramienta de riesgo alto, reglas contradictorias) comprobando la decisión de cada una.

**Acceptance Scenarios**:

1. **Given** una llamada a una herramienta que ninguna regla prevé, **When** se evalúa, **Then** la decisión es «preguntar» (requiere aprobación manual).
2. **Given** una herramienta que una regla deniega y otra permite, **When** se evalúa, **Then** la decisión es «denegar».
3. **Given** una herramienta que una regla pregunta y otra permite, **When** se evalúa, **Then** la decisión es «preguntar».
4. **Given** una herramienta clasificada como de riesgo alto (ejecución de código o red), **When** se evalúa, **Then** la decisión es «preguntar» y ninguna regla de permitir puede cambiarla.
5. **Given** una herramienta cuyo riesgo no está declarado o que no está registrada, **When** se evalúa, **Then** la decisión es «preguntar».
6. **Given** una llamada mal formada (sin nombre, o con argumentos que no son un diccionario) o un error al evaluar, **When** se evalúa, **Then** la decisión es «denegar» y la política nunca devuelve otra cosa que denegar, preguntar o permitir.
7. **Given** una herramienta de riesgo bajo (solo lectura) cuya llamada incluye `path`, **When** su ruta real queda dentro del área autorizada, **Then** una regla explícita acotada a esa área la permite (**supuesto pendiente de confirmación del PO**: amplía el texto «único permiso explícito del Sprint 1» de la historia, que no se modifica); **And** si la ruta queda fuera del área o no hay área configurada, la decisión es «preguntar»; **And** una herramienta de riesgo bajo sin `path` no tiene regla y se pregunta; **And** esta regla puede quitarse sin tocar las demás, y sin ella las lecturas se preguntan (literal de la historia).
8. **Given** una herramienta de riesgo bajo que incluye `path` con un valor que no es texto, vacío o inválido, o un comprobador del área que falla, **When** se evalúa, **Then** la decisión es «denegar» (llamada mal formada o error al evaluar).

---

### User Story 2 - La escritura solo se permite dentro del área autorizada (Priority: P1) [AC-04]

Como usuario operador, quiero que el agente solo pueda escribir dentro del área de trabajo autorizada y que cualquier otra escritura pida aprobación, para que no pueda modificar nada fuera de mi proyecto.

**Why this priority**: Es el permiso explícito de escritura de la historia (AC-04, regla de negocio 5 y HU-01-03). Un fallo aquí permite escribir en cualquier ruta del equipo.

**Independent Test**: Con un comprobador de área de prueba sobre un directorio temporal, se evalúan escrituras dentro, fuera, con «..», con ruta absoluta, con enlace simbólico y sin área configurada, y se comprueba que solo las de dentro se permiten.

**Acceptance Scenarios**:

1. **Given** una herramienta de escritura (riesgo medio) con una ruta cuya ruta real queda dentro del área autorizada, **When** se evalúa, **Then** una regla explícita acotada a esa área la permite.
2. **Given** una escritura cuya ruta real queda fuera del área (incluidas rutas con «..», rutas absolutas, enlaces simbólicos que salen del área y, en Windows, otra unidad o una ruta UNC), **When** se evalúa, **Then** la decisión es «preguntar».
3. **Given** que no hay un área de trabajo configurada, **When** el agente intenta escribir, **Then** toda escritura es «preguntar»: no existe un área por defecto.
4. **Given** una escritura sin ruta, con una ruta vacía, que no es texto o con caracteres no válidos, **When** se evalúa, **Then** la decisión es «denegar» (no se puede comprobar).
5. **Given** que el comprobador del área falla al resolver la ruta, **When** se evalúa, **Then** la decisión es «denegar».
6. **Given** cualquier configuración, **When** se revisan las reglas de permitir, **Then** no existe ninguna regla que permita escribir en cualquier ruta ni que permita todo; las únicas reglas de permitir son la de escritura acotada al área (AC-04) y la de lectura acotada al área (supuesto del escenario 7 de la historia 1).
7. **Given** una escritura dentro del área sobre una herramienta que una regla de denegar o de preguntar cubre, **When** se evalúa, **Then** prevalece denegar o preguntar sobre la regla de escritura (AC-02).
8. **Given** una herramienta de riesgo medio, **When** se evalúa una escritura, **Then** la política toma la ruta del argumento `path` (convención documentada en `contracts/path_argument_convention.md`); **And** si la llamada no trae `path` o no es texto, es una llamada mal formada y la decisión es «denegar»; **And** el puerto de herramienta no se modifica.

---

### User Story 3 - «Preguntar» se deniega con motivo mientras no exista la aprobación (Priority: P1) [AC-05]

Como usuario operador, quiero que, mientras no exista la interfaz de aprobación, una acción que debe preguntarse se deniegue con un motivo que el modelo reciba y que la decisión quede registrada, para poder demostrar el agente sin que nada sensible se ejecute.

**Why this priority**: Es AC-05 y lo que permite cerrar el Sprint 1 con un agente que funciona sin HU-05-03. Debe retirarse limpiamente cuando esa historia exista.

**Independent Test**: Con el bucle real, la política real y herramientas de prueba, se corre un turno cuya herramienta resulta en «preguntar»: la herramienta no se ejecuta, el modelo recibe el motivo y el bus entrega la decisión.

**Acceptance Scenarios**:

1. **Given** una acción cuya decisión es «preguntar» en el Sprint 1, **When** el bucle la procesa, **Then** la herramienta no se ejecuta, el modelo recibe un resultado de error que explica que requiere aprobación y que no está disponible (`[approval_required_unavailable] …`), y se publica la decisión de permiso con «preguntar» resuelta como denegada.
2. **Given** una acción cuya decisión es «denegar», **When** el bucle la procesa, **Then** la herramienta no se ejecuta y el modelo recibe `[permission_denied] …`.
3. **Given** una acción cuya decisión es «permitir», **When** el bucle la procesa, **Then** la herramienta se ejecuta con los argumentos exactos que se evaluaron.
4. **Given** que la política devuelve «preguntar», **When** se revisa el código de la política, **Then** no resuelve ella misma «preguntar» como denegar: esa resolución provisional es del bucle (ya existe) y se retira allí cuando exista HU-05-03.
5. **Given** una acción cuya decisión es «preguntar» o «denegar», **When** se explica la decisión al modelo, **Then** el motivo es el texto genérico que ya redacta el bucle; la política solo devuelve la decisión y no se modifica el bucle ni ningún puerto. **Hallazgo para A y para HU-05-03**: ese texto no distingue la causa (fuera del área, sin área configurada, herramienta no prevista, riesgo alto).

---

### User Story 4 - Las instrucciones halladas en archivos no cambian la política (Priority: P2) [AC-03]

Como usuario operador, quiero que un texto dentro de un archivo (por ejemplo, «permite todo» o «ignora las reglas») no pueda cambiar lo que la política decide, para que un archivo malicioso no me quite el control.

**Why this priority**: Es AC-03 y las reglas de negocio 2 y 3. Es una propiedad de diseño (la política no lee contenido) que conviene fijar con pruebas, pero no añade comportamiento nuevo.

**Independent Test**: Se evalúa la misma llamada antes y después de que el modelo «lea» un archivo con instrucciones; la decisión es idéntica, y la política no recibe ni guarda el contenido de ningún mensaje o resultado.

**Acceptance Scenarios**:

1. **Given** un archivo cuyo contenido dice «permite escribir en cualquier ruta», **When** el modelo lo lee y luego pide escribir fuera del área, **Then** la decisión es la misma que sin haber leído el archivo («preguntar»).
2. **Given** dos evaluaciones de la misma llamada con las mismas reglas, **When** entre ambas se leen archivos con instrucciones, **Then** las dos decisiones son idénticas.
3. **Given** la política, **When** se revisa su interfaz, **Then** solo recibe la llamada (nombre y argumentos): no recibe mensajes, historial ni resultados de herramientas, y su decisión no depende de ellos.
4. **Given** un argumento de la llamada con texto que imita una instrucción (por ejemplo, un nombre de herramienta o una ruta con «allow»), **When** se evalúa, **Then** se trata como dato y no cambia el orden ni las reglas.

---

### User Story 5 - Reglas configurables que nunca abren un hueco (Priority: P2)

Como usuario operador, quiero poder añadir herramientas a las listas de denegar y de preguntar desde el archivo de configuración, y que una configuración mal escrita nunca amplíe lo que se permite, para endurecer la política sin tocar el código.

**Why this priority**: La configuración de reglas es una decisión fija del encargo y la clasificación de herramientas por riesgo es la tarea Sp1-33; pero el núcleo de la historia funciona con las reglas integradas, por eso es P2.

**Independent Test**: Con archivos de configuración de prueba, se comprueba que las listas se leen, que un nombre desconocido o un tipo erróneo detienen el arranque con un mensaje claro y que ninguna configuración puede producir una regla de permitir.

**Acceptance Scenarios**:

1. **Given** un archivo de configuración con herramientas en la lista de denegadas, **When** arranca el sistema, **Then** la política las deniega aunque otra regla las permita.
2. **Given** un archivo con herramientas en la lista de preguntadas, **When** arranca el sistema, **Then** la política las pregunta aunque la regla de escritura las permitiría.
3. **Given** un archivo de configuración sin la sección de permisos, **When** arranca el sistema, **Then** rigen solo las reglas integradas (no se permite nada salvo la escritura dentro del área) y no se considera un error.
4. **Given** un archivo con un campo de permisos desconocido, un valor de tipo erróneo o un intento de definir una regla de permitir, **When** arranca el sistema, **Then** el arranque se detiene con un mensaje que nombra el campo (las reglas desconocidas no se ignoran ni se interpretan como permitir).
5. **Given** las herramientas registradas, **When** se clasifican, **Then** cada una declara su nivel de riesgo (bajo, medio o alto) y la política lo consulta por su nombre; una herramienta sin riesgo declarado se trata como no prevista.

---

### Edge Cases

- **Reglas que se contradicen**: prevalece denegar sobre preguntar y preguntar sobre permitir, sin importar el orden en que estén escritas.
- **Borrar archivos, hacer push, merge y deploy**: siempre requieren aprobación. En el Sprint 1 no existen herramientas de shell ni de git (llegan con HU-01-04); estas acciones quedan cubiertas por la regla de riesgo alto (preguntar) y por la regla de lo no previsto. Reconocer esas operaciones dentro de un comando de shell es HU-05-02 (Sprint 2).
- **Un permiso de sesión**: no existe en esta historia (llega con HU-05-03); ninguna regla de esta historia puede ser anulada por una aprobación.
- **Rutas con «..», absolutas, enlaces simbólicos, otra unidad, rutas UNC o flujos alternos de Windows**: la contención la decide el comprobador del área sobre la ruta real; si el comprobador falla o no puede resolver la ruta, la decisión es «denegar».
- **Herramienta de riesgo bajo o medio sin el argumento `path`**: de riesgo medio, llamada mal formada («denegar»); de riesgo bajo, no es una herramienta con ruta, no coincide con ninguna regla y se pregunta (AC-01).
- **Herramientas con varias rutas o con la ruta en otro argumento** (copiar, mover, `src`/`dst`): la convención solo cubre `path`; una herramienta así no cumple el contrato de HU-01-03 y, hasta que lo cumpla, se declara de riesgo alto (siempre se pregunta).
- **Mayúsculas y minúsculas en nombres de herramienta**: los nombres se comparan tal cual (sensibles a mayúsculas); un nombre que no coincide con ninguna herramienta registrada es una herramienta no prevista.
- **Nombre de herramienta con caracteres de control o muy largo**: no cambia la evaluación; se trata como una herramienta no prevista y el nombre no se reproduce sin acotar en ningún mensaje de la política.
- **Argumentos con valores enormes o anidados**: la política solo lee el argumento de la ruta; el resto no se interpreta.
- **La política recibe una llamada que cambia entre la evaluación y la ejecución**: el bucle ejecuta con los argumentos exactos que se evaluaron; esta historia no lo modifica.
- **Configuración con listas duplicadas o vacías**: los duplicados no cambian nada; una lista vacía es válida y significa «sin reglas adicionales».
- **HU-05-03 existe**: el bucle dejará de resolver «preguntar» como denegar y pedirá aprobación; la política no cambia.

### Casos de falla cerrada

| Situación | Decisión | Origen |
|---|---|---|
| Ninguna regla coincide (herramienta no registrada, riesgo no declarado) | Preguntar | AC-01 |
| Escritura cuya ruta real queda fuera del área | Preguntar | AC-04 |
| Escritura sin área de trabajo configurada | Preguntar | HU-01-03, AC-04 |
| Herramienta de riesgo alto | Preguntar | Regla de negocio 4 y riesgo |
| Herramienta en la lista de denegadas | Denegar | Regla de negocio 1 |
| Llamada mal formada: sin nombre, argumentos que no son un diccionario, ruta ausente, vacía o no textual en una escritura | Denegar | Falla cerrada |
| Error al evaluar: excepción del comprobador del área, clasificación no disponible | Denegar | Falla cerrada |
| Configuración con campo de permisos desconocido o de tipo erróneo | El arranque se detiene | HU-00-04 (campos desconocidos) |
| Configuración sin sección de permisos | Solo reglas integradas | Falla cerrada (no se permite nada nuevo) |
| Lectura de riesgo bajo con `path` cuya ruta real queda dentro del área | Permitir (**supuesto pendiente de confirmación del PO**; removible) | Q1, opción B |
| Lectura de riesgo bajo con `path` fuera del área o sin área configurada | Preguntar | Q1, opción B |
| Herramienta de riesgo bajo sin `path` | Preguntar (ninguna regla coincide) | AC-01 |
| Herramienta de riesgo bajo con `path` no textual, vacío o inválido; herramienta de riesgo medio sin `path` o con `path` no textual | Denegar | Q2, opción A |
| Sprint 1: «preguntar» sin aprobador | Se deniega con motivo (lo hace el bucle) | AC-05 |

La instrucción del encargo («ante duda, error, configuración ausente o regla desconocida, denegar») se aplica así: lo que no se puede evaluar con seguridad (llamada mal formada, error al evaluar) se **deniega**; lo que simplemente ningún regla prevé se **pregunta** porque lo fija AC-01 (inmutable) y, hasta que exista HU-05-03, el bucle lo resuelve igualmente como denegación; la diferencia solo se notará cuando haya aprobación interactiva.

## Requirements *(mandatory)*

### Functional Requirements

**Evaluación y precedencia**

- **FR-001**: El sistema MUST ofrecer una política concreta que implemente el puerto de política existente, evalúe cada llamada y devuelva siempre exactamente una de las tres decisiones (denegar, preguntar o permitir); no modifica el puerto.
- **FR-002**: La política MUST aplicar las reglas en el orden denegar, preguntar, permitir: si una regla de denegar coincide, la decisión es denegar; si no, y una de preguntar coincide, preguntar; si no, y una de permitir coincide, permitir; si ninguna coincide, preguntar.
- **FR-003**: Denegar MUST prevalecer sobre preguntar y permitir, y preguntar sobre permitir, independientemente del orden en que estén definidas las reglas (AC-02, regla de negocio 1).
- **FR-004**: Una llamada que ninguna regla prevé MUST resultar en «preguntar» (AC-01).
- **FR-005**: Las herramientas de riesgo alto MUST resultar siempre en «preguntar» y ninguna regla de permitir MUST poder cambiarlo; las acciones de borrar archivos, push, merge y deploy MUST requerir siempre aprobación (regla de negocio 4).
- **FR-006**: Una herramienta no registrada, sin riesgo declarado o con un riesgo desconocido MUST tratarse como no prevista («preguntar»).
- **FR-007**: **Regla de lectura (supuesto pendiente de confirmación del PO)**: una herramienta de riesgo bajo cuya llamada incluye `path` MUST resultar en «permitir» cuando la ruta real queda dentro del área autorizada (según el comprobador del área), en «preguntar» cuando queda fuera o no hay área configurada, y en «denegar» cuando `path` no es texto, está vacío o es inválido o el comprobador falla; MUST NOT permitir lecturas en cualquier ruta; una herramienta de riesgo bajo sin `path` resulta en «preguntar». La regla MUST ser independiente de las demás y poder quitarse sin tocar el resto, con lo que las lecturas pasan a «preguntar». Amplía el texto «único permiso explícito del Sprint 1» de la historia, que no se modifica.

**Escritura en el área autorizada**

- **FR-008**: Las únicas reglas de permitir MUST ser dos, ambas acotadas al área de trabajo autorizada: la de escritura (una herramienta de riesgo medio cuya ruta real queda dentro del área se permite, AC-04) y la de lectura de FR-007 (supuesto pendiente de confirmación del PO). Todo camino que devuelve «permitir» MUST pasar por `AuthorizedArea.contains` con la ruta que trae `path` y solo cuando devuelve exactamente `True`; no existe ningún «permitir» sin esa condición.
- **FR-009**: La contención MUST decidirla el comprobador del área sobre la ruta real (no sobre el texto recibido); la política MUST NOT reimplementar la resolución de rutas.
- **FR-010**: Una escritura cuya ruta queda fuera del área, o cuando no hay área configurada, MUST resultar en «preguntar». No existe un área por defecto ni ninguna regla que permita escribir en cualquier ruta o permitir todo.
- **FR-011**: Una escritura con ruta ausente, vacía, que no es texto o con caracteres no válidos, o con un comprobador que falla, MUST resultar en «denegar».
- **FR-012**: El argumento que contiene la ruta de las herramientas de archivos MUST llamarse `path` (convención documentada en `contracts/path_argument_convention.md`, que HU-01-03 debe cumplir); una herramienta de riesgo medio sin `path` o con un `path` que no es texto MUST tratarse como llamada mal formada («denegar»); el puerto de herramienta no se modifica.

**Falla cerrada**

- **FR-013**: Una llamada mal formada (sin nombre de herramienta, con argumentos que no son un diccionario) y cualquier error o excepción al evaluar MUST resultar en «denegar»; la política MUST NOT dejar escapar una excepción al bucle ni devolver un valor distinto de las tres decisiones.
- **FR-014**: La política MUST NOT tener ninguna rama que permita por defecto: toda ruta de código que no produzca una decisión explícita resulta en «preguntar» o «denegar».

**Instrucciones en archivos y aplicación en el harness**

- **FR-015**: La política MUST recibir solo la llamada (nombre y argumentos) y MUST NOT leer ni guardar mensajes, historial ni resultados de herramientas; su decisión MUST depender solo de la llamada, las reglas y el estado del área (AC-03, reglas de negocio 2 y 3).
- **FR-016**: Un texto que imita una instrucción dentro de los argumentos MUST tratarse como dato y MUST NOT cambiar las reglas ni el orden.

**Resolución provisional de «preguntar»**

- **FR-017**: La política MUST devolver «preguntar» tal cual; la resolución provisional como denegación con motivo MUST seguir siendo del bucle de A y retirarse allí cuando exista HU-05-03 (AC-05).
- **FR-018**: Con el bucle real y la política real, una acción que resulta en «preguntar» MUST no ejecutar la herramienta, devolver al modelo el resultado `[approval_required_unavailable] …` y publicar la decisión de permiso con «preguntar» resuelta como denegada; una denegación MUST devolver `[permission_denied] …` y una permisión ejecutar con los argumentos evaluados.
- **FR-019**: La política MUST devolver solo la decisión; el motivo que recibe el modelo MUST ser el texto genérico que ya redacta el bucle, sin modificar `core/loop.py` ni los puertos. Queda como hallazgo para A y HU-05-03 que ese texto no distingue la causa.

**Clasificación y configuración**

- **FR-020**: Cada herramienta MUST declarar su nivel de riesgo (bajo, medio o alto) y la política MUST consultarlo por nombre mediante el registro de herramientas; las herramientas de lectura se clasifican como de riesgo bajo, las de escritura en el área como de riesgo medio y la ejecución de código o la red como de riesgo alto.
- **FR-021**: La configuración MUST poder declarar, en una sección de permisos del archivo de configuración, una lista de herramientas denegadas y una lista de herramientas preguntadas (ambas vacías por defecto); la sección ausente MUST ser válida y dejar solo las reglas integradas.
- **FR-022**: La configuración MUST NOT poder definir reglas de permitir ni ampliar las reglas de escritura y de lectura; un campo de permisos desconocido o de tipo erróneo MUST detener el arranque con un mensaje que nombre el campo, y el núcleo MUST recibir las reglas ya cargadas como valores tipados e inmutables sin leer archivos ni entorno.
- **FR-023**: La configuración MUST NOT contener secretos ni leer `.env`; el área autorizada es la ruta de trabajo ya configurada en el archivo de configuración.

**Calidad y alcance**

- **FR-024**: La historia MUST NOT modificar `core/interfaces/`, `core/events.py`, `core/loop.py`, el bus, `tests/doubles/` ni `docs/archivo/`, MUST NOT romper las pruebas existentes del bucle y MUST NOT añadir dependencias; solo biblioteca estándar en el núcleo.
- **FR-025**: Las pruebas MUST pasar en Windows y en Linux, sin red y sin tocar el entorno real.
- **FR-026**: La historia MUST NOT implementar la lista de comandos peligrosos, el análisis de comandos encadenados (HU-05-02), la interfaz de aprobación ni el permiso de sesión (HU-05-03), ni las herramientas de archivos ni el componente real de área autorizada (HU-01-03).

### Key Entities *(include if feature involves data)*

- **Política de permisos**: componente que recibe una llamada y devuelve denegar, preguntar o permitir; es el único lugar donde se decide.
- **Decisión**: una de tres: denegar, preguntar o permitir.
- **Regla**: condición sobre una llamada con una decisión asociada; hay reglas de denegar, de preguntar y de permitir; las de permitir son solo dos, integradas y acotadas al área: la de escritura y la de lectura (esta última, supuesto pendiente de confirmación del PO).
- **Nivel de riesgo**: clasificación de cada herramienta en bajo, medio o alto, declarada por la herramienta.
- **Área de trabajo autorizada**: carpeta configurada dentro de la cual se permite escribir y, por el supuesto de FR-007, leer; su comprobación de contención es del componente de área (HU-01-03).
- **Configuración de permisos**: listas de herramientas denegadas y preguntadas, cargadas desde el archivo de configuración como valores inmutables.
- **Llamada**: nombre de herramienta y argumentos pedidos por el modelo; es lo único que evalúa la política.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de las llamadas de prueba que ninguna regla prevé (herramientas no registradas, sin riesgo declarado o de riesgo alto), la decisión es «preguntar»; en ninguna es «permitir».
- **SC-002**: En el 100 % de las combinaciones de prueba de reglas que se contradicen (todas las parejas y trías de denegar, preguntar y permitir, en cualquier orden de definición), la decisión respeta el orden denegar, preguntar, permitir.
- **SC-003**: En el 100 % de las escrituras de prueba con ruta real dentro del área la decisión es «permitir», y en el 100 % de las escrituras con ruta real fuera del área, sin área configurada, con «..», absolutas, con enlace simbólico que sale del área o (en Windows) de otra unidad o UNC es «preguntar»; ninguna escritura fuera del área se permite. Lo mismo para las lecturas de riesgo bajo con `path` (supuesto de FR-007): dentro del área «permitir», fuera o sin área «preguntar», `path` inválido «denegar», y ninguna lectura fuera del área se permite.
- **SC-004**: En el 100 % de las llamadas mal formadas y de los errores simulados al evaluar (excepción del comprobador, clasificación no disponible), la decisión es «denegar» y ninguna excepción llega al bucle.
- **SC-005**: La decisión de una llamada es idéntica antes y después de leer archivos con instrucciones (100 % de los casos de prueba), y la política no recibe ni guarda contenido de mensajes.
- **SC-006**: Con el bucle real, el 100 % de las acciones que resultan en «preguntar» no ejecuta la herramienta, entrega al modelo el motivo de la historia y publica la decisión; las pruebas existentes del bucle siguen pasando sin modificarlas.
- **SC-007**: En el 100 % de los archivos de configuración de prueba con campos de permisos desconocidos, de tipo erróneo o con un intento de definir una regla de permitir, el arranque se detiene con un mensaje que nombra el campo; ninguna configuración produce una regla de permitir adicional.
- **SC-008**: La comprobación automática no encuentra más reglas de permitir que las dos acotadas al área (escritura y lectura), ni ninguna regla que permita todo o escribir o leer en cualquier ruta; todo camino del código que devuelve «permitir» pasa por `AuthorizedArea.contains` con la ruta de `path` y no existe ningún «permitir» sin esa condición; y la diferencia de los archivos protegidos respecto a la base de integración es vacía.
- **SC-009**: Evaluar una llamada cuesta en promedio menos de 1 ms, de modo que la política no sea perceptible en el turno.
- **SC-010**: Las pruebas automatizadas de la historia pasan al 100 % en Windows y en Linux, sin red.

## Assumptions

- **Contratos base**: La historia usa tal cual los contratos de HU-00-01 (puerto `PermissionPolicy`, `RiskLevel` y `AuthorizedArea`); no modifica puertos. HU-00-01 sigue `Pendiente de aprobación técnica` en `docs/PROGRESO.md` (Sp1-03); la ratificación debe producirse antes de pasar HU-05-01 a `Hecha`.
- **Dónde vive**: La política concreta va en el área de permisos del núcleo (`core/permissions/`, C), solo con biblioteca estándar, y recibe por inyección el registro de herramientas (para consultar el riesgo), el componente de área y las reglas ya cargadas. La lectura del archivo de configuración y la construcción del objeto de reglas están fuera del núcleo (`config.py`); conectar todo es de la raíz de composición, fuera de esta historia.
- **Qué hace hoy el bucle**: Llama a la política con la llamada validada, publica la decisión de permiso (decisión, resolución, motivo `policy_error` si la política falló), rechaza la denegación con `[permission_denied] …` y la pregunta con `[approval_required_unavailable] …`, y ejecuta solo si la decisión es exactamente «permitir». La resolución provisional de «preguntar» (Sp1-35) ya existe ahí; esta historia la verifica con la política real y no la duplica.
- **Clasificación por riesgo (Sp1-33)**: El puerto de herramienta ya tiene el atributo de riesgo (bajo: lectura; medio: modificaciones dentro del área; alto: ejecución o red). La política consulta el riesgo por el nombre de la herramienta en el registro. Que cada herramienta de archivos declare su riesgo es de HU-01-03 (Sp1-21); aquí se prueba con herramientas de prueba.
- **Qué es «escritura» y «lectura»**: Una herramienta de riesgo medio es una herramienta de escritura sobre una ruta y una de riesgo bajo con `path` es una de lectura; el argumento de la ruta es `path` (convención de FR-012). Una herramienta de riesgo bajo sin `path` no es de archivos y se pregunta.
- **Regla de lectura (supuesto pendiente de confirmación del PO)**: La regla de FR-007 se añade para poder demostrar el agente leyendo archivos del área en el Sprint 1 y amplía el texto «único permiso explícito del Sprint 1» de la historia, que no se modifica. Es independiente y se puede quitar sin tocar el resto. **La tarea de cierre debe añadir una observación en `docs/PROGRESO.md`** con este supuesto y su confirmación pendiente.
- **Hallazgos para A y HU-05-03**: El texto genérico que redacta el bucle para «preguntar» («requiere aprobación, que no está disponible en esta sesión; se resolvió como denegada») no distingue la causa (fuera del área, sin área configurada, herramienta no prevista, riesgo alto); cuando exista la interfaz de aprobación convendrá que el motivo llegue al usuario y al modelo. No se resuelve aquí y no se modifica el bucle.
- **Configuración de reglas**: Se asume una sección `[permissions]` del archivo de configuración con las listas `deny` y `ask` de nombres de herramienta (vacías por defecto). Esto amplía el esquema de `config.py` (HU-00-04, que dejó las reglas de permisos para esta historia); no se admiten reglas de permitir. El área autorizada es `paths.workspace_root`, ya existente.
- **Nombres de herramienta**: Se comparan tal cual; los nombres de las listas se validan como texto no vacío.
- **Aplicación en el harness**: La política la invoca el bucle antes de ejecutar; el modelo no puede influir en ella salvo por la llamada que pide.
- **Fuera de alcance**: Lista de comandos peligrosos y análisis de comandos encadenados (HU-05-02, Sprint 2); interfaz de aprobación, permiso de sesión y retirada de la resolución provisional (HU-05-03); las herramientas de archivos y el componente real de área autorizada (HU-01-03); reconocer borrar/push/merge/deploy dentro de un comando de shell (HU-05-02 y HU-01-04); cualquier regla de permitir configurable.
- **Texto de RF-5.1, RF-5.2 y RF-5.3**: El texto íntegro de estos requisitos no figura en la documentación activa; solo su trazabilidad a HU-05-01. La spec los interpreta a partir de la historia.
- **Presupuesto**: El plan de sprint asigna 11 h a Sp1-32 a Sp1-36 (3,5 + 1 + 2 + 1,5 + 3). La estimación de las tareas se compara con ese presupuesto y se anota como aviso, sin recortar alcance (Principio VI). El encargo fija entre 8 y 10 tareas de 40 min como máximo.
- **Disciplina de proceso**: La historia se limita al Sprint 1 (Principio VI), se verifica con pruebas automatizadas sin red (Principio IV), no altera `docs/archivo/` (Principio X) y se registra en `docs/PROGRESO.md` (Principio VIII). La revisión cruzada por A o B es una tarea humana (Principio IX).
