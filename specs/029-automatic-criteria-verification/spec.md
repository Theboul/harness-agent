# Feature Specification: HU-11-04.1 — Verificación automática de criterios objetivos: solo el harness marca passes

**Feature Branch**: `gustavo` (el directorio de la spec es `029-automatic-criteria-verification`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-27

**Status**: Borrador (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 2 | **PHU**: 2 | **Responsable**: A — Núcleo | **Tareas de referencia**: Sp2-49 (1 h), Sp2-50 (2,5 h), Sp2-51 (1,5 h), Sp2-52 (1,5 h), Sp2-53 (2 h) | **Requisitos**: RF-11.4 | **Depende de**: HU-11-01 (tarea con criterios protegidos), HU-11-03 (comandos de la tarea) y HU-01-04 (herramienta shell); las tres integradas en `main`, `En revisión` en PROGRESO

**Input**: User description: "HU-11-04.1 — Verificación automática de criterios objetivos (Sprint 2). Lo que pida la ficha, sin inventar. Convivencia con lo construido: nunca afloja una denegación (HU-05-02, HU-11-02), una declaración de la tarea no sube a «permitir» nada que esas reglas pregunten o denieguen y lo que el analizador no entiende se pregunta. Respeta los tiempos por comando de HU-11-03 y el recorte de salida; sin filtrar el comando ni credenciales en eventos o errores. Fuera: entorno aislado (PD-06), cambios de puertos o de `core/loop.py` y cualquier cambio de política que no pida la ficha. Si cumplir la ficha exige tocar un puerto, `core/loop.py`, el catálogo de eventos o un archivo de otra área, plantearlo como pregunta."

## Clarifications

### Session 2026-10-27

Respuestas del revisor a las tres preguntas de `/speckit-specify` y una corrección a una decisión de la spec. Ninguna contradice los criterios de aceptación.

- Q: ¿Cómo conoce el verificador la condición esperada de cada criterio sin cambiar el puerto `TaskCriteriaItem`? → A: **B.** La condición sale de la `TaskDefinition` que ya recibe `compose()`; el puerto no cambia. El criterio se empareja por identificador si existe y, si no, por posición. Solo se ejecuta el comando guardado en SQLite (fuente de verdad) cuando coincide **exactamente** con el de la definición; si no coincide es una **alteración**: no se ejecuta, passes no cambia y se registra el motivo sin filtrar el comando.
- Q: ¿Qué hace el harness cuando la política resuelve «preguntar» para un comando de verificación? → A: **A.** Se pregunta a la persona con el mismo aprobador de HU-05-03. Sin aprobador no se ejecuta (falla cerrada) y el criterio queda sin cumplir con el motivo «no ejecutado». Un comando denegado nunca se ejecuta ni llega al aprobador. Un comando idéntico a uno declarado en `## Comandos` hereda su permiso y su tiempo (HU-11-03). La opción C (ejecutar siempre) queda **descartada**.
- Q: ¿Qué condiciones esperadas entiende la primera versión? → A: **A.** Solo «código de salida == N» y «código de salida != N». Cualquier otra condición hace que la **tarea sea inválida al cargarla**, con un mensaje claro; no queda un criterio en silencio como no verificable. Ampliar más adelante a «la salida contiene un texto» es **compatible hacia atrás**: las tareas escritas con las dos comparaciones seguirán siendo válidas.
- Q (corrección a la spec): ¿Se vuelven a ejecutar los criterios que ya estaban cumplidos? → A: **Sí.** Cada vez que el agente propone terminar se ejecutan **todos** los criterios objetivos. Uno que ya tenía passes y ahora falla se informa al agente como **regresión** (código de salida y salida recortada) y la tarea no se da por terminada. Passes **no se revoca** porque el almacén no lo permite: limitación conocida, con pregunta abierta para el PO (H4). Las rondas de verificación quedan acotadas por los límites de sesión existentes (turnos, tiempo, tokens); no hay contador nuevo ni bucle sin tope.
- Q: ¿Cuál es el estado final del turno de verificación? → A: Si todos los objetivos cumplen y hay criterios semánticos, la tarea queda **«pendiente de validación humana»**, nunca «cumplida» por una afirmación del modelo. Solo sin criterios semánticos y con todos los objetivos cumplidos la tarea se da por verificada.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04e-historias-coding-harness.md` (HU-11-04.1). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

- **Como:** usuario operador
- **Quiero:** que el harness ejecute el comando de verificación de cada criterio objetivo y marque passes solo cuando se cumple la condición esperada
- **Para:** no aceptar un resultado solo porque la IA dice que ya está
- **Descripción:** Cuando el agente propone terminar, el harness ejecuta por su cuenta el comando de verificación de cada criterio objetivo y marca passes solo si se cumple la condición esperada. Los criterios semánticos quedan pendientes de validación humana. Es la primera versión de la verificación: no usa subagentes.

**Flujo general**

1. El agente propone terminar la tarea.
2. El harness ejecuta el comando de verificación de cada criterio objetivo bajo la política de permisos.
3. Si el resultado cumple la condición, pone passes en verdadero; si no, lo deja en falso y devuelve al agente la salida recortada.
4. Los criterios semánticos quedan pendientes de validación humana.
5. La CLI muestra el estado de cada criterio.

**Reglas de negocio**

1. Solo el harness cambia passes; lo que el agente afirma no cuenta como evidencia.
2. Un criterio sin comando de verificación nunca se marca automáticamente.
3. Los comandos de verificación los define la tarea, no el agente.

**Prototipo**

```
TAREA-14 — estado de los criterios
  [x] 1 El email es obligatorio            (pytest: salida 0)
  [ ] 2 La contraseña tiene 8 caracteres   (pytest: salida 1)
  [?] 3 El mensaje de error es claro       pendiente de validación humana
```

**Criterios de aceptación**

- **AC-01 — Verificación por comandos del harness.** Dado un ticket con criterios objetivos, cada uno con un comando de verificación y una condición esperada, cuando el agente propone terminarlo, entonces el harness ejecuta cada comando y marca passes solo en los que cumplen la condición.
- **AC-02 — Criterio semántico pendiente de validación humana.** Dado un criterio sin comando de verificación (semántico), cuando se intenta cerrar la tarea, entonces queda pendiente de validación humana y nunca se marca por una afirmación del modelo.
- **AC-03 — Fallo de verificación informado al agente.** Dado un comando de verificación que falla, cuando termina, entonces passes sigue en falso y el agente recibe el código de salida y la salida recortada.
- **AC-04 — Estado visible de cada criterio.** Dado el estado de la tarea, cuando el usuario lo consulta, entonces ve cada criterio como cumplido, no cumplido o pendiente de validación humana.

### Lo que ya existe y lo que cambia

| Pieza existente | Qué aporta | Qué cambia en esta historia |
|---|---|---|
| Criterios de la tarea (HU-11-01): cada criterio objetivo ya guarda su comando y su condición esperada (`comando:` y `espera:` en la tarea; columnas `comando` y `condicion` en SQLite); el semántico nace sin ambos | Es el «campo de verificación» de Sp2-49 | El formato no cambia, pero la tarea pasa a validar al cargarla que la condición sea una de las dos comparaciones del código de salida (Q3); el puerto no cambia (Q1) |
| `mark_passes(criterio, evidencia)` del almacén (HU-11-01): único camino para poner passes; exige evidencia no vacía y ninguna herramienta lo expone | Regla de negocio 1 | Pasa a llamarlo el verificador del harness, tras ejecutar el comando |
| Política de permisos en cadena (HU-05-01/05-02/11-02/11-03/11-01) y aprobación (HU-05-03/05-04) | Decide permitir, preguntar o denegar un comando de shell | Se consulta tal cual, sin cambiarla, para cada comando de verificación |
| Herramienta shell (HU-01-04) y recorte de salida (HU-02-02) | Ejecución con tiempo máximo, salida acotada y credenciales de URL ocultas (HU-11-02) | Se reutilizan los mismos límites y el mismo ocultado para lo que se guarda y para lo que se devuelve al agente |
| Comandos de la tarea con tiempo propio (HU-11-03) | Tiempo declarado, 300 s por defecto, tope 600 | Un comando de verificación idéntico a uno declarado hereda su tiempo |
| Evento `criterion_verified` (ya está en el catálogo de 17 eventos, sin uso hasta hoy) | Canal para publicar el resultado | Se publica uno por criterio verificado; el tipo no cambia |
| `TurnStatus.COMPLETED` del bucle | Indica que el agente dio una respuesta final sin pedir herramientas | Es la señal de «el agente propone terminar»; el bucle no cambia |
| CLI (HU-06-01) | Muestra los eventos | Muestra el estado de cada criterio (flujo 5, AC-04) |

### User Story 1 - El harness comprueba los criterios objetivos cuando el agente propone terminar (Priority: P1)

Una persona operadora arranca una tarea con criterios objetivos. Cuando el agente da una respuesta final sin pedir más herramientas, el harness ejecuta por su cuenta el comando de **cada** criterio objetivo y marca como cumplidos solo los que cumplen su condición. El agente no puede marcar nada.

**Why this priority**: Es AC-01, las reglas 1 y 3 y el propósito de la historia: no aceptar un resultado solo porque la IA dice que ya está (V-15).

**Independent Test**: Con una tarea de tres criterios (dos objetivos con comando y uno semántico), un proveedor simulado que «propone terminar» y un shell doble que registra los comandos, el harness ejecuta exactamente los dos comandos de la tarea, marca como cumplido el que sale con la condición esperada y deja el otro sin cumplir.

**Acceptance Scenarios**:

1. **Given** una tarea con criterios objetivos, **When** el agente responde sin pedir herramientas, **Then** el harness ejecuta el comando de **todos** los criterios objetivos (también los que ya estaban cumplidos), una vez por propuesta, en el orden de la tarea.
2. **Given** un comando de verificación cuya salida cumple la condición esperada, **When** termina, **Then** el criterio queda cumplido con evidencia (código de salida y salida acotada).
3. **Given** que el agente afirma en su respuesta que todo está cumplido, **When** el harness aún no ha ejecutado los comandos, **Then** ningún criterio está cumplido: la afirmación no cuenta (regla 1).
4. **Given** cualquier herramienta o comando que intente cambiar un criterio, **When** se ejecuta, **Then** no puede marcar passes: solo el verificador del harness lo hace.

---

### User Story 2 - Un criterio sin comando nunca se marca solo (Priority: P1)

El criterio semántico (sin comando) queda siempre pendiente de validación humana; ni el modelo ni el harness lo marcan.

**Why this priority**: Es AC-02 y la regla 2; evita que el sistema «cierre» un criterio que nadie ha comprobado.

**Independent Test**: Una tarea solo con criterios semánticos: al proponer terminar, el harness no ejecuta nada y todos quedan «pendiente de validación humana».

**Acceptance Scenarios**:

1. **Given** un criterio sin comando, **When** el agente propone terminar, **Then** el criterio queda pendiente de validación humana y el harness no ejecuta ningún comando por él.
2. **Given** una tarea con un criterio semántico pendiente, **When** todos los objetivos se cumplen, **Then** la tarea no se da por validada del todo: se informa de lo que espera a una persona.
3. **Given** que el modelo escribe «el criterio 3 está cumplido», **When** termina el turno, **Then** el criterio sigue pendiente (AC-02).

---

### User Story 3 - El fallo de verificación llega al agente con el código y la salida recortada (Priority: P1)

Cuando un comando de verificación no cumple la condición, falla o agota su tiempo, el criterio sigue sin cumplir y el agente recibe lo necesario para corregirse.

**Why this priority**: Es AC-03 y el paso 3 del flujo; sin esto el agente no sabría qué arreglar.

**Independent Test**: Un comando de verificación que sale con código distinto de cero y salida larga: passes sigue en falso, el agente recibe el código de salida y la salida recortada con marca de omisión, y el turno siguiente puede corregir y volver a proponer terminar.

**Acceptance Scenarios**:

1. **Given** un comando que termina con un código distinto del esperado, **When** el harness lo ejecuta, **Then** passes sigue en falso y el agente recibe el número del criterio, el código de salida y la salida recortada.
2. **Given** una salida muy larga, **When** vuelve al agente, **Then** se recorta con la marca de omisión de HU-02-02/HU-01-04 y sin credenciales de URL.
3. **Given** un comando que agota su tiempo, **When** se termina, **Then** el criterio queda sin cumplir y el agente recibe el aviso de tiempo agotado.
4. **Given** que el agente corrige y vuelve a proponer terminar, **When** el harness verifica de nuevo, **Then** se ejecutan otra vez todos los criterios objetivos y el aviso solo menciona los que fallan.

---

### User Story 4 - La persona operadora ve el estado de cada criterio (Priority: P2)

La CLI muestra cada criterio como cumplido, no cumplido o pendiente de validación humana, tras cada verificación y cuando la persona lo consulta.

**Why this priority**: Es AC-04 y el paso 5 del flujo. Es P2 porque depende de las historias anteriores para tener qué mostrar.

**Independent Test**: Con los eventos de una verificación y la CLI sobre flujos de texto, se imprime un estado con el formato del prototipo; consultar el estado en cualquier momento muestra lo mismo que el almacén.

**Acceptance Scenarios**:

1. **Given** una tarea con tres criterios (dos objetivos y uno semántico), **When** termina la verificación, **Then** la CLI muestra `[x]`, `[ ]` y `[?]` con el texto del prototipo (cumplido, no cumplido, pendiente de validación humana).
2. **Given** un criterio cumplido, **When** se muestra, **Then** aparece «cumplido» solo si el harness ejecutó antes su comando (criterio de demostración del Sprint 2).
3. **Given** que la persona consulta el estado durante la sesión, **When** lo pide, **Then** ve el estado actual sin ejecutar nada.

---

### User Story 5 - La verificación no afloja ninguna regla de permisos (Priority: P1)

Ejecutar los comandos de la tarea por su cuenta no da al harness permisos que el agente no tenga: cada comando pasa por la misma política y lo que esa política deniega o pregunta se respeta.

**Why this priority**: Es el paso 2 del flujo («bajo la política de permisos») y la frontera de seguridad: un comando de criterio escrito en una tarea no puede ser un camino para ejecutar algo denegado.

**Independent Test**: Con la composición real y un shell doble que registra, criterios cuyos comandos son denegados (lista base, git destructivo, zona protegida), preguntados (no entendido, git de escritura) y permitidos (lectura de git, comando declarado): los denegados nunca llegan al shell, los preguntados se le preguntan a la persona con el aprobador de HU-05-03 (sin aprobador no se ejecutan) y nada de lo denegado se ejecuta ni llega al aprobador por aparecer en la tarea.

**Acceptance Scenarios**:

1. **Given** un criterio cuyo comando la política deniega, **When** llega la verificación, **Then** el comando no se ejecuta, el criterio queda sin cumplir y el agente recibe un aviso con la etiqueta de la denegación (sin repetir el comando).
2. **Given** un criterio cuyo comando la política pregunta, **When** llega la verificación, **Then** se pregunta a la persona con el aprobador de HU-05-03; sin aprobador, o si rechaza, el comando no se ejecuta y el criterio queda sin cumplir con el motivo «no ejecutado». Nunca se ejecuta sin que la política lo permita o la persona lo apruebe.
3. **Given** un comando que el analizador no entiende, **When** llega la verificación, **Then** se trata como «preguntar» (falla cerrada), nunca como «permitir».
4. **Given** un criterio cuyo comando es idéntico a un comando de pruebas o de lint declarado en la tarea, **When** llega la verificación, **Then** la política ya lo permite (HU-11-03) y hereda su tiempo máximo.
5. **Given** que la tarea declara un comando, **When** ese comando está en la lista de denegados o es git destructivo, **Then** sigue denegado: declararlo en la tarea no lo permite.
6. **Given** un comando denegado, **When** llega la verificación, **Then** no llega al aprobador: el aprobador recibe 0 preguntas.

---

### User Story 6 - El resultado de cada ronda es claro en cada caso (Priority: P1)

Cada propuesta de terminar acaba en uno de los siete casos de la tabla, con el mismo tratamiento en el almacén, en lo que recibe el agente y en lo que ve la persona.

**Why this priority**: Cierra AC-01 a AC-04 con los casos que más fallan en la práctica (regresión, alteración, política sin aprobador, tiempo agotado) y fija el estado final de la tarea.

**Independent Test**: Con la composición real, un shell doble que registra los comandos y un aprobador de prueba, una prueba por cada fila de la tabla comprueba el estado de cada criterio, lo que recibe el agente y lo que muestra la CLI.

| Caso | Qué ocurre | Passes | Qué recibe el agente | Estado de la tarea |
|---|---|---|---|---|
| **Todos cumplen** (sin criterios semánticos) | Todos los comandos salen con la condición esperada | Todos en verdadero, con evidencia | Nada que corregir | Verificada |
| **Todos los objetivos cumplen y hay semánticos** | Igual que el anterior | Los objetivos en verdadero; los semánticos no se tocan | Nada que corregir | **Pendiente de validación humana**, nunca «cumplida» |
| **Uno falla** | Un comando sale con otro código | Ese criterio sigue en falso | Número del criterio, código de salida y salida recortada | No terminada |
| **Regresión** | Un criterio que ya tenía passes ahora falla | **No se revoca** (el almacén no lo permite); se informa y se muestra como regresión | Número del criterio, código y salida recortada, indicando que antes cumplía | No terminada |
| **Comando alterado** | El comando de SQLite no coincide exactamente con el de la definición | No cambia | Aviso de alteración sin el comando | No terminada; no se ejecuta nada de ese criterio |
| **Política que pregunta sin aprobador** (o la persona rechaza) | El comando no se ejecuta | No cambia | Número del criterio y motivo «no ejecutado» | No terminada |
| **Tiempo agotado** | El proceso se termina al llegar al máximo | Sigue en falso | Número del criterio, aviso de tiempo agotado y la salida recortada hasta entonces | No terminada |
| **Criterio sin comando** | No se ejecuta nada | Nunca se marca | — | Pendiente de validación humana |

**Acceptance Scenarios**:

1. **Given** cada fila de la tabla, **When** el agente propone terminar, **Then** el estado de los criterios, lo que recibe el agente y el estado final de la tarea son los de la fila.
2. **Given** una regresión, **When** se informa, **Then** el aviso menciona el código de salida y la salida recortada, y la tarea no se da por terminada aunque el resto cumpla.
3. **Given** que todos los objetivos cumplen y existe al menos un criterio semántico, **When** termina la ronda, **Then** el estado final es «pendiente de validación humana» y no «cumplida», aunque el modelo lo afirme.

---

### Edge Cases

- **Tarea sin criterios objetivos** (todos semánticos): no se ejecuta nada; el estado muestra todos pendientes de validación humana.
- **Sesión sin tarea**: la verificación no existe; el comportamiento de hoy no cambia.
- **Criterio ya cumplido**: se vuelve a ejecutar en cada propuesta de terminar; si ahora falla es una regresión que se informa (el almacén no puede revocar passes; limitación conocida, pregunta para el PO).
- **Condición esperada que no es «código de salida == N» ni «!= N»**: la tarea es inválida al cargarla, con un mensaje claro que no repite el texto recibido; no se llega a verificar.
- **Comando de verificación que no coincide con el guardado** (la definición y la fila de SQLite difieren): no se ejecuta, passes no cambia y se trata como alteración; se registra solo el motivo (el mismo canal de `criteria_tampered`), nunca el comando.
- **Criterio sin pareja** (el identificador o la posición no corresponden a ningún criterio de la definición): se trata como alteración.
- **Política que pregunta y no hay aprobador** (o el aprobador rechaza o falla): el criterio queda sin cumplir con el motivo «no ejecutado»; nada se ejecuta.
- **Salida con credenciales de URL**: se ocultan antes de guardar la evidencia, de devolverla al agente y de publicarla.
- **Salida enorme o comando que no termina**: salida recortada y tiempo máximo; el proceso se termina.
- **Cancelación** (Ctrl-C) durante la verificación: se propaga y el proceso en curso se termina; nada queda a medio marcar.
- **Límites de sesión** (HU-01-06) agotados: no hay nuevos turnos de corrección; el estado final se muestra igualmente.
- **Fallo del almacén** al marcar: el criterio no se da por cumplido y se informa sin repetir datos.
- **Dos propuestas de terminar seguidas sin cambios**: cada una ejecuta de nuevo todos los criterios objetivos; el número de rondas lo acotan los límites de sesión existentes (turnos, tiempo y tokens) y no hay un contador nuevo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Cuando el agente propone terminar (respuesta final sin pedir herramientas), el harness MUST ejecutar por su cuenta el comando de **todos** los criterios objetivos, también los que ya estén cumplidos, en el orden de la tarea (AC-01).
- **FR-002**: El harness MUST marcar un criterio como cumplido solo si el resultado del comando cumple su condición esperada; en cualquier otro caso MUST dejarlo sin cumplir (AC-01, AC-03).
- **FR-003**: Solo el verificador del harness MUST poder poner un criterio como cumplido; ni el agente, ni una afirmación del modelo, ni una herramienta de archivos o de shell cuentan como evidencia (regla 1).
- **FR-004**: Un criterio sin comando de verificación MUST NOT marcarse automáticamente nunca y MUST mostrarse como pendiente de validación humana (AC-02, regla 2).
- **FR-005**: Los comandos de verificación MUST salir de la tarea; el agente no los define ni los modifica (regla 3). La condición esperada MUST salir de la definición de la tarea que recibe la composición, emparejando cada criterio por identificador si existe y, si no, por posición. Solo MUST ejecutarse el comando guardado en el almacén, y solo cuando coincide **exactamente** con el de la definición; si no coincide, o el criterio no tiene pareja, es una alteración: no se ejecuta, passes no cambia y se registra el motivo sin el comando.
- **FR-006**: Cada comando de verificación MUST pasar por la misma cadena de política de permisos que una llamada al shell del agente, sin cambiarla: lo denegado MUST NOT ejecutarse ni llegar al aprobador; lo preguntado MUST preguntarse a la persona con el aprobador de HU-05-03 y, sin aprobador (o si rechaza o falla), MUST NOT ejecutarse y el criterio queda sin cumplir con el motivo «no ejecutado»; lo que el analizador no entiende MUST tratarse como preguntado; y declarar un comando en la tarea MUST NOT convertir en permitido nada que esas reglas denieguen o pregunten. Un comando idéntico a uno declarado en `## Comandos` hereda su permiso y su tiempo (HU-11-03).
- **FR-007**: Cuando un criterio no se cumple, el agente MUST recibir el número del criterio, el código de salida (o la causa: no ejecutado, tiempo agotado, no aprobado) y la salida recortada con la marca de omisión (AC-03).
- **FR-008**: La salida MUST respetar el recorte de salidas existente y MUST ocultar las credenciales de URL antes de guardarse como evidencia, de devolverse al agente o de publicarse.
- **FR-009**: Cada comando MUST respetar un tiempo máximo: el declarado en la tarea si es idéntico a un comando de pruebas o de lint declarado (HU-11-03); si no, el tiempo por defecto del shell; nunca más que el tope de 600 s. Al agotarse, el proceso MUST terminarse.
- **FR-010**: La evidencia guardada al marcar MUST contener el código de salida y la salida acotada, y MUST NOT contener el comando ni credenciales.
- **FR-011**: El harness MUST publicar un evento `criterion_verified` por criterio verificado con campos acotados (identificador del criterio, resultado y código de salida o causa); MUST NOT incluir el comando, la salida ni credenciales en ningún evento ni mensaje de error.
- **FR-012**: La CLI MUST mostrar el estado de cada criterio —cumplido, no cumplido o pendiente de validación humana— tras cada verificación y cuando la persona lo consulte, con el formato del prototipo (AC-04, flujo 5).
- **FR-013**: Tras un fallo, el agente MUST poder corregir y volver a proponer terminar; cada nueva verificación MUST ejecutar de nuevo todos los criterios objetivos. El número de rondas MUST quedar acotado por los límites de sesión existentes (turnos, tiempo y tokens); MUST NOT crearse un contador nuevo ni un bucle sin tope.
- **FR-014**: Si el almacén detecta alteración de los criterios, el harness MUST no marcar nada y MUST informar solo del motivo.
- **FR-016**: Un criterio que ya tenía passes y cuyo comando ahora no cumple la condición MUST informarse al agente como regresión, con el código de salida y la salida recortada; la tarea MUST NOT darse por terminada y passes MUST NOT revocarse (el almacén no lo permite).
- **FR-017**: La condición esperada MUST ser «código de salida == N» o «código de salida != N»; cualquier otra condición MUST hacer inválida la tarea al cargarla, con un mensaje claro que no repite el texto recibido. Ampliar las condiciones en el futuro MUST ser compatible hacia atrás.
- **FR-018**: Si todos los criterios objetivos cumplen y existe al menos un criterio semántico, el estado final MUST ser «pendiente de validación humana»; MUST NOT ser «cumplida» por una afirmación del modelo. Solo sin criterios semánticos la tarea se da por verificada.
- **FR-015**: La historia MUST NOT cambiar puertos, `core/loop.py`, la forma del catálogo de eventos, ni la política de permisos; MUST NOT requerir el entorno aislado (PD-06).

### Key Entities

- **Criterio verificable**: un criterio objetivo de la tarea con su comando, su condición esperada y su estado (cumplido o no, con evidencia).
- **Resultado de verificación**: lo que produce un comando: cumplido, no cumplido (código de salida y salida acotada), no ejecutado (denegado, no aprobado, alterado) o tiempo agotado.
- **Estado del criterio (vista)**: cumplido, no cumplido o pendiente de validación humana.
- **Aviso de verificación al agente**: texto del harness que resume los criterios sin cumplir; contiene el número, el código y la salida recortada, nunca el comando.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En una tarea de ejemplo con tres criterios (dos objetivos y uno semántico), el 100 % de los criterios objetivos se comprueba ejecutando su comando, y 0 criterios se marcan por una afirmación del modelo.
- **SC-002**: En el 100 % de los casos de criterio sin comando, el criterio termina «pendiente de validación humana» y el harness ejecuta 0 comandos por él.
- **SC-003**: En el 100 % de los comandos de verificación que fallan, el agente recibe el código de salida y una salida de como máximo el límite de recorte, con la marca de omisión cuando se recorta.
- **SC-004**: En una batería de al menos 15 comandos de verificación denegados, preguntados o no entendidos (lista base, git destructivo, zona protegida, comandos compuestos), 0 se ejecutan sin permiso de la política o aprobación de la persona.
- **SC-005**: 0 eventos, mensajes de error o evidencias contienen el comando de verificación o una credencial de prueba, comprobado con valores centinela.
- **SC-006**: La CLI muestra un estado por cada criterio de la tarea en el 100 % de las verificaciones, y «cumplido» aparece solo después de que el harness ejecutó su comando.
- **SC-007**: Las pruebas existentes de las historias de las que depende pasan sin cambios, salvo los ajustes declarados (los de tareas con una condición que no sea del código de salida).
- **SC-008**: Cada una de las siete situaciones de la tabla de la historia 6 (todos cumplen, uno falla, regresión, comando alterado, política que pregunta sin aprobador, tiempo agotado, criterio sin comando) tiene una prueba que comprueba passes, lo que recibe el agente y el estado final.
- **SC-009**: En el 100 % de las propuestas de terminar se ejecutan todos los criterios objetivos, y 0 rondas superan los límites de sesión existentes.

## Assumptions

- **«Cuando el agente propone terminar»** es una respuesta final del modelo sin llamadas a herramientas (turno `COMPLETED`). La detección y la nueva ronda viven fuera del bucle, en la raíz de composición; `core/loop.py` no cambia.
- **El aviso al agente** tras un fallo entra como un mensaje nuevo del harness en la conversación (el siguiente turno), con el número del criterio, el código de salida y la salida recortada. No se marca como contenido externo.
- **Condición esperada**: el formato de la tarea ya guarda el texto de la condición (ejemplo del contrato de HU-11-01: `codigo_salida == 0`). Esta historia fija su gramática (`codigo_salida == N` y `codigo_salida != N`) y la valida al cargar la tarea; es un endurecimiento del analizador de `core/tasks/` (área A, la del responsable) y las pruebas existentes de HU-11-01 que usen otra condición se ajustan y se declaran. Ampliar a «la salida contiene un texto» no invalida ninguna tarea ya escrita.
- **Regresiones**: cada propuesta ejecuta todos los criterios objetivos; si uno que ya tenía passes falla, se informa como regresión y la tarea no se da por terminada. Passes no se revoca porque el almacén (HU-11-01) no tiene esa operación: **limitación conocida**. Pregunta para el PO (H4): ¿debe el almacén permitir revocar passes con evidencia? Cambiarlo toca el puerto `TaskCriteria` y exige acuerdo de A, B y C; no se hace aquí.
- **Evidencia**: se guarda el código de salida y la salida acotada con credenciales ocultas; el comando no se guarda en la evidencia.
- **Emparejado**: el identificador de la definición, si la tarea lo tiene, y si no la posición; el almacén conserva el orden de la tarea.
- **Rondas**: las acotan los límites de sesión (HU-01-06). Cuando un límite se agota no hay nuevos turnos de corrección y el estado final se muestra igualmente.
- **Tiempo por defecto** de un comando que no coincide con uno declarado: el del shell (120 s); el declarado de HU-11-03 si coincide exactamente; tope 600 s.
- **Cómo se arranca una tarea desde la terminal** (`main()` no carga tareas; punto abierto de HU-11-03) queda **fuera**: la historia se prueba con `compose(task=…)`, como las anteriores. Se deja como observación para decidir qué historia añade la opción.
- **Confirmación humana de criterios semánticos** (`confirmado_por`) queda fuera: esta historia solo los muestra como pendientes.
- **Archivos de otras áreas**: mostrar el estado en la CLI toca `cli/` (área C) y el cableado `bootstrap.py` (área C); la ficha lo pide (flujo 5, AC-04). Se anota con visto bueno de C.
- **Evento `criterion_verified`**: el tipo existe en el catálogo; sus campos los fija esta historia y se confirman con A, B y C. Si se prefiere no publicarlo, la CLI se alimentaría de otro modo (decisión del plan).
- **Aprobador**: es el mismo de HU-05-03; la verificación no crea otro. Sin aprobador, lo que la política pregunta no se ejecuta.

## Preguntas abiertas

Ninguna sobre el alcance. Una pregunta para una persona queda en H4 (revocar passes con evidencia).

## Dependencias y tareas humanas

- **H1**: acuerdo de A, B y C sobre los campos del evento `criterion_verified` (el puerto no cambia, Q1 = B) y sobre el endurecimiento del analizador de la tarea (Q3).
- **H2**: visto bueno de C a los cambios en `cli/` y `bootstrap.py` (archivos de su área).
- **H3**: revisión cruzada por B o C (la historia es de A).
- **H4**: revisión del PO de la regla ante «preguntar» (Q2), de las condiciones soportadas (Q3) y la pregunta de si el almacén debe permitir revocar passes con evidencia (regresiones).
- **H5**: CI remota en `ubuntu-latest` y `windows-latest`.
