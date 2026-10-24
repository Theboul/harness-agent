# Feature Specification: HU-06-01 — CLI básica con eventos en tiempo real

**Feature Branch**: `009-basic-cli-events` (el trabajo se hace en la rama `gustavo`; el nombre del directorio de la spec no dicta la rama)

**Created**: 2026-10-20

**Status**: En revisión (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 1 | **Responsable**: C — Control y conexiones | **Tareas de referencia**: Sp1-37, Sp1-38, Sp1-39 | **Requisitos**: RF-6.4, RNF-10 | **Depende de**: HU-01-05

**Input**: User description: "HU-06-01 — CLI básica con eventos en tiempo real. Como usuario operador quiero una terminal que muestre en vivo qué herramienta se está ejecutando y mensajes de error claros, para entender qué hace el agente. El alcance es el render de eventos en vivo y una entrada de comandos mínima."

## Clarifications

### Session 2026-10-20

Decisiones ya tomadas por el responsable antes de redactar; no quedó ningún marcador de aclaración pendiente y no se hicieron preguntas.

- Q: ¿Qué entra y qué queda fuera? → A: Entra el render de eventos en vivo (estado de herramienta, mensajes del asistente, errores) y una entrada de comandos mínima. Quedan fuera: construir el proveedor real y leer la configuración (raíz de composición), la aprobación interactiva (HU-05-03), la cancelación con Ctrl+C (HU-06-03), los colores, el historial de sesiones y los comandos de sesión (`/sesiones`, `/reanudar`).
- Q: ¿Dónde vive y con qué dependencias? → A: En `src/harness_agent/cli/` (`render.py` convierte eventos en líneas de texto y `app.py` es el ciclo de entrada), solo con biblioteca estándar, sin colores ni secuencias ANSI; la salida y la entrada son flujos inyectables (por defecto la salida y la entrada estándar); codificación UTF-8 segura en Windows y Linux (FR-014, FR-015, FR-020).
- Q: ¿Cuánta lógica tiene la CLI? → A: Ninguna del núcleo: se suscribe al puerto del bus y recibe por inyección una función asíncrona que ejecuta un turno y el bus; no decide permisos, no valida, no ejecuta herramientas y no construye el bucle, el proveedor ni el registro (FR-021, FR-022).
- Q: ¿Qué eventos se muestran? → A: Herramienta solicitada y terminada, mensaje del asistente, decisión de permiso cuando es denegación o pregunta, error del proveedor y límite alcanzado; el resto se ignora sin error. El contenido de cada línea sale de lo que el bucle emite hoy, sin inventar campos (FR-002 a FR-008).
- Q: ¿Cómo se muestran los errores? → A: Con causa y acción sugerida, en frases completas en español, sin trazas, sin objetos internos y sin volcar la carga cruda; las sugerencias salen de una tabla de categorías conocidas del bucle y una categoría desconocida muestra una causa genérica con la sugerencia «revisa el registro de eventos»; los datos se acotan a una longitud máxima (FR-009 a FR-011).
- Q: ¿Qué entrada admite? → A: Una línea de texto es una tarea nueva; las líneas que empiezan por «/» son comandos; solo existen `/ayuda` y `/salir`; un comando desconocido muestra un mensaje claro y no ejecuta nada; una línea vacía se ignora; el fin de la entrada termina limpio; la CLI no interpreta la tarea (FR-016 a FR-019).
- Q: ¿Qué pasa si falla la escritura en la salida? → A: No se traga en silencio: se propaga al bus, que ya la agrupa en `EventDeliveryError` (HU-01-05) (FR-013).
- Q: ¿Qué hace la CLI si la función de turno falla? → A: (D9, decidida) `run_cli` captura solo las `Exception` ordinarias que lance la función de turno (incluido `EventDeliveryError`), muestra una línea con el formato de error («x Error: el turno terminó con un fallo interno (<TipoDeError>). Sugerencia: revisa el registro de eventos.», con el tipo acotado a 64 caracteres, sin el mensaje de la excepción, sin traza ni carga), termina la sesión y devuelve un código de salida distinto de cero (falla cerrada); `CancelledError`, `KeyboardInterrupt` y cualquier `BaseException` que no sea `Exception` se propagan sin tocar; si escribir esa línea también falla, ese fallo se propaga (FR-026).
- Q: ¿Qué se hace con el texto que viene del modelo o de archivos? → A: Solo se muestra: no se ejecuta ni interpreta; los caracteres de control (salvo salto de línea y tabulación) se sustituyen o eliminan antes de imprimir (FR-012).
- Q: ¿Cómo se prueba? → A: Render con eventos construidos a mano; integración con el bucle real de A, el bus real, un proveedor guionizado y flujos en memoria, sin red; una prueba de arquitectura de que `core/` no importa `cli/` y de que `cli/` solo usa la API pública de `harness_agent.core` (FR-022, FR-024).

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y prototipo de la historia (inmutables)

Copiados tal cual de `docs/04c-historias-control.md` (HU-06-01). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

**Reglas de negocio**

1. La CLI no contiene lógica del núcleo.
2. Los errores no muestran trazas de pila crudas.

**Prototipo**

```
> Leí el archivo pagos.py
... ejecutando: buscar "def cobrar" …
x Error: la ruta 'src/pago.py' no existe. Sugerencia: usa 'listar' para ver los archivos.
```

**Criterios de aceptación**

- **AC-01 — Estado de herramienta en vivo.** Dado una tarea en curso, cuando el agente invoca una herramienta, entonces la terminal muestra su nombre y estado.
- **AC-02 — Errores claros.** Dado un error, cuando se muestra, entonces indica la causa y una acción sugerida, sin trazas de pila crudas.

### Lo que ya existe y no se toca

El puerto del bus, los 17 tipos de evento, el bus en memoria (HU-01-05), el bucle de A y los dobles de pruebas **no se modifican**. La CLI es un consumidor: se apoya en lo que el bucle emite hoy y no le pide nada nuevo.

### User Story 1 - Ver en vivo qué herramienta ejecuta el agente (Priority: P1) [AC-01]

Como usuario operador, quiero ver en la terminal, mientras el agente trabaja, el nombre de cada herramienta que invoca y su estado, y los mensajes del asistente, para entender qué está haciendo.

**Why this priority**: Es el criterio AC-01 y el propósito de la historia (RF-6.4). Sin esto la terminal es una caja negra y la persona no sabe si el agente avanza, está bloqueado o ejecutó algo inesperado.

**Independent Test**: Con el bucle real conectado al bus real y un proveedor guionizado, se corre un turno con una herramienta y se comprueba que la salida (un flujo en memoria) contiene, en orden, la línea de «ejecutando» con el nombre de la herramienta, la línea de resultado correcto y el mensaje del asistente.

**Acceptance Scenarios**:

1. **Given** una tarea en curso, **When** el agente invoca una herramienta, **Then** la terminal muestra una línea con su nombre y el estado «ejecutando», en cuanto se publica el evento de herramienta solicitada.
2. **Given** una herramienta en ejecución, **When** termina correctamente, **Then** la terminal muestra una línea con el nombre y el estado «correcto».
3. **Given** el mensaje de texto del asistente, **When** se publica, **Then** la terminal lo muestra.
4. **Given** un evento de un tipo que la CLI no muestra (por ejemplo, el mensaje del usuario o la interrupción), **When** se publica, **Then** se ignora sin error y sin salida.
5. **Given** varias herramientas en un turno, **When** se ejecutan, **Then** las líneas aparecen en el mismo orden en que se publicaron los eventos.

---

### User Story 2 - Errores claros, con causa y acción sugerida (Priority: P1) [AC-02]

Como usuario operador, quiero que cada error me diga qué falló y qué puedo hacer, sin trazas de pila ni datos internos, para poder corregirlo sin leer código.

**Why this priority**: Es el criterio AC-02 y la regla de negocio 2. Una traza cruda o un volcado de datos es ilegible para quien opera y puede exponer contenido que no debe mostrarse.

**Independent Test**: Con eventos de error construidos a mano (una herramienta con argumentos inválidos, una herramienta no registrada, una denegación de permiso, un error del proveedor, un límite alcanzado y una categoría desconocida con un valor centinela en su carga), se comprueba que cada línea contiene una causa y una sugerencia, y que no aparecen trazas, objetos internos ni el centinela.

**Acceptance Scenarios**:

1. **Given** una herramienta que termina con error de una categoría conocida del bucle, **When** se muestra, **Then** la línea indica la causa y una acción sugerida de la tabla de categorías.
2. **Given** una decisión de permiso de denegación o de pregunta, **When** se publica, **Then** la terminal muestra el motivo y una acción sugerida, una sola vez por llamada.
3. **Given** un error del proveedor, **When** se publica, **Then** la terminal muestra la causa con el mensaje acotado y una acción sugerida, sin traza.
4. **Given** un límite alcanzado, **When** se publica, **Then** la terminal muestra que se alcanzó un límite de la sesión y una acción sugerida, sin leer campos de la carga (su contenido aún no está definido).
5. **Given** una categoría de error desconocida, **When** se muestra, **Then** la línea indica una causa genérica y la sugerencia «revisa el registro de eventos», nunca la excepción ni la carga cruda.
6. **Given** un mensaje de error largo, **When** se muestra, **Then** se acota a una longitud máxima documentada.

---

### User Story 3 - Entrada de comandos mínima (Priority: P2)

Como usuario operador, quiero escribir una tarea o un comando en la terminal, para dar trabajo al agente y salir sin cerrar la ventana a la fuerza.

**Why this priority**: Sin entrada no hay forma de producir eventos; aun así es P2 porque el render (AC-01 y AC-02) se puede verificar sin entrada interactiva y porque la entrada es deliberadamente mínima en esta historia.

**Independent Test**: Con una entrada en memoria que contiene una tarea, un comando conocido, un comando desconocido, una línea vacía y el fin de la entrada, y con una función de turno de prueba que registra lo que recibe, se comprueba que la tarea llega una sola vez y sin cambios, que los comandos se atienden sin ejecutar nada del agente y que el ciclo termina limpio.

**Acceptance Scenarios**:

1. **Given** una línea de texto que no empieza por «/», **When** se introduce, **Then** se entrega tal cual, una sola vez, a la función de turno inyectada como tarea nueva; la CLI no interpreta su contenido.
2. **Given** la línea `/ayuda`, **When** se introduce, **Then** se muestra la lista de comandos disponibles y no se ejecuta ningún turno.
3. **Given** la línea `/salir`, **When** se introduce, **Then** el ciclo termina limpio.
4. **Given** un comando desconocido (por ejemplo, `/sesiones`), **When** se introduce, **Then** se muestra un mensaje claro que lo indica y sugiere `/ayuda`, y no se ejecuta nada.
5. **Given** una línea vacía o solo con espacios, **When** se introduce, **Then** se ignora.
6. **Given** el fin de la entrada, **When** se alcanza, **Then** el ciclo termina limpio sin error.

---

### User Story 4 - La CLI es solo un suscriptor, y lo que muestra es solo texto (Priority: P2)

Como equipo de desarrollo, quiero que la CLI no contenga lógica del núcleo y que trate todo lo que muestra como texto, para poder cambiarla o añadir una interfaz web sin tocar el núcleo y para que un texto malicioso no pueda controlar la terminal.

**Why this priority**: Es la regla de negocio 1 y una barrera de seguridad barata: el texto de los mensajes y de los errores viene del modelo o de archivos y puede contener secuencias de control.

**Independent Test**: Una prueba de arquitectura recorre `core/` y `cli/`; una prueba de render usa cadenas con secuencias de control y comprueba que no llegan a la salida.

**Acceptance Scenarios**:

1. **Given** el código del núcleo, **When** se revisa, **Then** ningún módulo importa `cli/`.
2. **Given** el código de `cli/`, **When** se revisa, **Then** solo usa la API pública de `harness_agent.core` y la biblioteca estándar; no importa adaptadores, observabilidad ni la raíz de composición.
3. **Given** un texto del modelo o de una herramienta con caracteres de control (escape, retroceso, retorno de carro, nulo, control de terminal), **When** se muestra, **Then** los caracteres de control, salvo salto de línea y tabulación, se sustituyen o eliminan y la terminal no interpreta nada.
4. **Given** un fallo al escribir en la salida (por ejemplo, un flujo cerrado), **When** un evento se muestra, **Then** la excepción no se oculta: se propaga al bus, que la agrupa en el error de entrega.
5. **Given** la CLI en funcionamiento, **When** se revisa lo que hace, **Then** no decide permisos, no valida argumentos y no ejecuta herramientas: solo muestra lo que el núcleo publicó.

---

### Edge Cases

- **Error de herramienta sin detalle**: el evento de herramienta terminada trae el nombre, si fue error y una categoría, pero no el texto del error de la herramienta. La causa que se muestra sale de la categoría (por ejemplo, «los argumentos no son válidos»), no del texto que devolvió la herramienta; el detalle, como la ruta que no existe del prototipo, llegaría con una ampliación de la carga que corresponde al núcleo y queda fuera de esta historia.
- **Argumentos de la herramienta**: la carga de la herramienta solicitada no incluye argumentos (decisión del bucle, FR-029 de HU-01-01); la línea de «ejecutando» muestra solo el nombre y no el texto `buscar "def cobrar" …` del prototipo.
- **Herramienta rechazada antes de ejecutarse**: el bucle publica la herramienta solicitada aunque luego la rechace (no registrada, argumentos inválidos, permiso denegado); la línea «ejecutando» va seguida de su error. Una denegación de permiso se informa una sola vez con causa y sugerencia, en la línea de la decisión; el estado final de esa llamada no repite la sugerencia.
- **Decisión de permiso «permitir»**: no se muestra (solo denegación o pregunta).
- **«Pregunta» sin aprobador**: en Sprint 1 el bucle resuelve la pregunta como denegada porque la aprobación interactiva llega con HU-05-03; la CLI lo muestra como «requiere aprobación, no disponible» sin ofrecer aprobar.
- **Límite alcanzado**: el bucle de Sprint 1 todavía no publica este evento (llega con HU-01-06); la CLI ya sabe mostrarlo pero no lee campos de su carga, porque aún no están definidos.
- **Categoría desconocida o campos ausentes en una carga**: nunca produce una excepción; se muestra la causa genérica y la sugerencia «revisa el registro de eventos».
- **Texto largo del asistente**: se muestra completo salvo los caracteres de control; los mensajes de error se acotan.
- **Caracteres no representables en la consola de Windows**: la salida no falla por una codificación que no los admita; los caracteres no representables se sustituyen.
- **Salto de línea dentro de un mensaje**: se conserva (es texto legítimo); el resto de los controles no.
- **Línea de entrada que empieza por espacios y luego «/»**: se trata como texto de tarea, no como comando (el comando empieza en la primera columna).
- **Entrada muy larga**: se entrega sin interpretar.
- **La función de turno falla** (D9): `run_cli` captura solo las `Exception` ordinarias, incluido el error de entrega que agrupa un fallo de escritura; muestra una sola línea con el tipo de la excepción (sin su mensaje, sin traza y sin carga), termina la sesión y devuelve un código de salida distinto de cero. Si escribir esa línea también falla (por ejemplo, porque la salida está cerrada), ese segundo fallo se propaga: no se traga.
- **Cancelación con Ctrl+C**: fuera de alcance (HU-06-03); no se atiende en esta historia. `CancelledError`, `KeyboardInterrupt` y cualquier `BaseException` que no sea `Exception` se propagan sin tocar (FR-026).

## Requirements *(mandatory)*

### Functional Requirements

**Render de eventos**

- **FR-001**: La CLI MUST suscribirse al puerto del bus a los tipos de evento que muestra e ignorar sin error y sin salida cualquier otro tipo.
- **FR-002**: Ante un evento de herramienta solicitada, la CLI MUST mostrar una línea con el nombre de la herramienta y el estado «ejecutando», sin argumentos (el evento no los incluye).
- **FR-003**: Ante un evento de herramienta terminada sin error, la CLI MUST mostrar una línea con el nombre y el estado «correcto».
- **FR-004**: Ante un evento de herramienta terminada con error, la CLI MUST mostrar una línea de error con la causa y una acción sugerida, tomadas de la tabla de categorías (FR-009).
- **FR-005**: Ante un mensaje del asistente, la CLI MUST mostrar su texto.
- **FR-006**: Ante una decisión de permiso de denegación o de pregunta, la CLI MUST mostrar el motivo y una acción sugerida; si la decisión es «permitir», MUST NOT mostrar nada. Una denegación se informa una sola vez por llamada.
- **FR-007**: Ante un error del proveedor, la CLI MUST mostrar la causa, el mensaje acotado y una acción sugerida.
- **FR-008**: Ante un límite alcanzado, la CLI MUST mostrar que se alcanzó un límite de la sesión con una acción sugerida, sin leer campos de la carga.
- **FR-009**: Las acciones sugeridas MUST salir de una tabla de categorías conocidas del bucle (argumentos inválidos, herramienta no registrada, denegado por permiso, requiere aprobación no disponible, excepción o resultado inválido de la herramienta, error de la herramienta, error del proveedor y límite alcanzado); una categoría desconocida MUST mostrar una causa genérica y la sugerencia «revisa el registro de eventos».
- **FR-010**: Los errores mostrados MUST NOT contener trazas de pila, nombres de objetos internos ni la carga cruda del evento; los datos que provienen del evento MUST acotarse a una longitud máxima documentada.
- **FR-011**: Los mensajes de la CLI MUST ser frases completas en español, con los nombres de herramientas y categorías tal cual.

**Seguridad y robustez de la salida**

- **FR-012**: La CLI MUST tratar todo lo que muestra como texto: no ejecuta ni interpreta nada; los caracteres de control, salvo el salto de línea y la tabulación, MUST sustituirse o eliminarse antes de imprimir.
- **FR-013**: Un fallo al escribir en la salida MUST NOT tragarse: la excepción se propaga al bus, que la agrupa en el error de entrega de HU-01-05.
- **FR-014**: La salida MUST ser texto plano, sin colores ni secuencias ANSI.
- **FR-015**: La salida MUST escribirse sin fallar por la codificación en Windows y en Linux: los caracteres que la consola no pueda representar se sustituyen.

**Entrada**

- **FR-016**: Una línea de texto que no empieza por «/» MUST entregarse sin cambios, una sola vez, a la función de turno inyectada como tarea nueva; la CLI MUST NOT interpretar su contenido.
- **FR-017**: Las líneas que empiezan por «/» en la primera columna MUST tratarse como comandos de la CLI; solo existen `/ayuda` (lista los comandos) y `/salir` (termina el ciclo limpio); un comando desconocido MUST mostrar un mensaje claro y no ejecutar nada.
- **FR-018**: Una línea vacía o solo con espacios MUST ignorarse.
- **FR-019**: El fin de la entrada MUST terminar el ciclo limpio, sin error.
- **FR-020**: La salida y la entrada MUST ser flujos inyectables (por defecto la salida y la entrada estándar).

**Arquitectura**

- **FR-021**: La CLI MUST NOT contener lógica del núcleo: no decide permisos, no valida argumentos y no ejecuta herramientas; no construye el bucle, el proveedor ni el registro.
- **FR-022**: El ciclo de entrada MUST recibir por inyección el bus y una función asíncrona que ejecuta un turno; la historia MUST NOT construir el proveedor real ni leer la configuración.
- **FR-023**: La historia MUST NOT modificar `core/interfaces/`, `core/events.py`, `core/loop.py`, el bus en memoria, `tests/doubles/` ni `docs/archivo/`, y MUST NOT añadir dependencias.
- **FR-024**: Una comprobación automática MUST verificar que `core/` no importa `cli/` y que `cli/` solo usa la API pública de `harness_agent.core` (y la biblioteca estándar), sin adaptadores.
- **FR-025**: Las pruebas MUST pasar en Windows y en Linux, sin red, sin proveedor real y sin tocar la consola real: usan flujos en memoria.

**Fallo del turno**

- **FR-026**: Si la función de turno lanza una `Exception` ordinaria (incluido el error de entrega de un fallo de escritura), `run_cli` MUST capturarla, mostrar UNA línea con el formato de error («x Error: el turno terminó con un fallo interno (<TipoDeError>). Sugerencia: revisa el registro de eventos.», con el nombre del tipo saneado y acotado a 64 caracteres, sin el mensaje de la excepción, sin traza ni carga), terminar la sesión y devolver un código de salida distinto de cero (falla cerrada). `CancelledError`, `KeyboardInterrupt` y cualquier `BaseException` que no sea `Exception` MUST propagarse sin tocar; si escribir esa línea también falla, ese fallo MUST propagarse. Una terminación limpia (`/salir` o fin de la entrada) devuelve 0.

### Key Entities *(include if feature involves data)*

- **Línea de salida**: texto en español que la CLI escribe por cada evento mostrado; no tiene estado.
- **Tabla de categorías**: relación entre una categoría conocida del bucle y su causa y su acción sugerida; una categoría desconocida cae en la entrada genérica.
- **Comando de la CLI**: línea que empieza por «/»; hoy `/ayuda` y `/salir`.
- **Tarea**: línea de texto que se entrega sin interpretar a la función de turno.
- **Evento y tipo de evento**: los de HU-01-05 (sin cambios); la CLI solo lee los campos que el bucle publica hoy.
- **Función de turno**: función asíncrona inyectada que ejecuta un turno del bucle; la CLI no sabe qué hay detrás.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En un turno con el bucle real, el 100 % de las herramientas invocadas aparece en la salida con su nombre y los estados «ejecutando» y «correcto» o error, en el orden de los eventos.
- **SC-002**: En el 100 % de los errores mostrados (todas las categorías conocidas, error del proveedor, permiso y límite) la línea contiene una causa y una acción sugerida, y en ninguna aparece una traza, un objeto interno ni la carga cruda (comprobado con un valor centinela en la carga).
- **SC-003**: El 100 % de las categorías que el bucle publica hoy tiene entrada en la tabla; una categoría desconocida nunca produce una excepción y siempre muestra la sugerencia «revisa el registro de eventos».
- **SC-004**: En el 100 % de las cadenas de prueba con caracteres de control (escape, nulo, retroceso, retorno de carro, controles de 7 y 8 bits), la salida no contiene ningún carácter de control salvo salto de línea y tabulación.
- **SC-005**: El 100 % de las líneas de entrada de prueba se clasifica correctamente (tarea, comando conocido, comando desconocido, vacía, fin de entrada); una tarea llega a la función de turno exactamente una vez y sin cambios, y un comando desconocido no ejecuta nada.
- **SC-006**: Un fallo al escribir en la salida llega a quien emitió el evento en el 100 % de los casos de prueba (nunca se silencia).
- **SC-007**: La comprobación de arquitectura encuentra cero importaciones de `cli/` en `core/` y cero importaciones de adaptadores o de módulos no públicos de `core` en `cli/`; la diferencia de los archivos protegidos respecto a la base de integración es vacía.
- **SC-008**: Mostrar un evento cuesta en promedio menos de 1 ms, de modo que el render en vivo no se note en el turno.
- **SC-009**: Las pruebas automatizadas de la historia pasan al 100 % en Windows y en Linux, sin red ni proveedor real.
- **SC-010**: En el 100 % de los fallos ordinarios de la función de turno de prueba, la salida contiene exactamente una línea de fallo con el tipo de la excepción (nunca su mensaje ni una traza), la sesión termina y el código de salida es distinto de cero; en el 100 % de los casos de `BaseException` que no es `Exception` la excepción original llega sin cambios a quien llamó a `run_cli`.

## Assumptions

- **Contratos base**: La historia usa tal cual los contratos de HU-00-01 y el bus de HU-01-05. HU-00-01 sigue `Pendiente de aprobación técnica` en `docs/PROGRESO.md` (Sp1-03); la historia no modifica ningún puerto, pero esa ratificación debe producirse antes de pasar HU-06-01 a `Hecha`.
- **Qué publica el bucle hoy**: Herramienta solicitada (`call_id`, `name`), decisión de permiso (`call_id`, `name`, `decision`, `resolved_as`, `reason`), herramienta terminada (`call_id`, `name`, `is_error`, `category`), mensaje del asistente (`content`, `tool_call_count`, `final`) y error del proveedor (`reason`, `error_type`, `message` acotado a 500 caracteres). Las categorías de herramienta terminada son `ok`, `tool_error`, `unknown_tool`, `invalid_arguments`, `permission_denied`, `approval_required_unavailable`, `tool_exception` e `invalid_tool_result`. La CLI se apoya solo en estos campos.
- **Límite alcanzado**: El bucle de Sprint 1 no lo publica todavía (HU-01-06, Sprint 2); su carga no está definida, así que la CLI muestra un texto fijo sin leer campos.
- **Diferencia con el prototipo**: El prototipo muestra los argumentos de la herramienta y la ruta concreta que no existe; la carga actual del bucle no los incluye (decisión de HU-01-01 para no filtrar contenido). La causa mostrada sale de la categoría. Si se quiere el detalle, hay que ampliar la carga del núcleo (A) en otra historia; no se resuelve aquí.
- **Prefijos de línea**: Se siguen las marcas del prototipo (`...` para «ejecutando» y `x` para error); el formato exacto de cada línea se fija en el plan y su contrato.
- **Idioma**: Los textos de la CLI van en español, el idioma de trabajo del proyecto.
- **Errores de la función de turno** (D9, decidida por el responsable): `run_cli` captura solo las `Exception` ordinarias del turno, muestra una línea con el tipo de la excepción y termina la sesión con un código de salida distinto de cero; las `BaseException` que no son `Exception` se propagan; el fallo de escribir esa línea también se propaga. La raíz de composición futura usa el código de salida como código del proceso.
- **Longitudes máximas**: El valor concreto de las longitudes máximas se fija en el plan y se documenta.
- **Entrada**: El indicador de entrada y el manejo de la lectura bloqueante se deciden en el plan; la historia solo exige que la entrada sea un flujo inyectable.
- **Presupuesto**: El plan de sprint asigna 5 h a Sp1-37, Sp1-38 y Sp1-39 (1,5 + 2 + 1,5). La estimación de las tareas se compara con ese presupuesto y se anota como aviso, sin recortar el alcance (Principio VI).
- **Texto de RF-6.4 y RNF-10**: El texto íntegro de estos requisitos no figura en la documentación activa; solo su trazabilidad a HU-06-01. La spec los interpreta a partir de la historia.
- **Fuera de alcance**: Proveedor real y configuración (raíz de composición), aprobación interactiva (HU-05-03), cancelación con Ctrl+C (HU-06-03), colores, historial y comandos de sesión (`/sesiones`, `/reanudar`), punto de entrada ejecutable, ampliación de la carga de los eventos.
- **Disciplina de proceso**: La historia se limita al Sprint 1 (Principio VI), se verifica con pruebas automatizadas sin red (Principio IV), no altera `docs/archivo/` (Principio X) y se registra en `docs/PROGRESO.md` (Principio VIII).
