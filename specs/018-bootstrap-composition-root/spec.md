# Feature Specification: Raíz de composición y punto de entrada ejecutable (historia propuesta)

**Feature Branch**: `018-bootstrap-composition-root` (carpeta de la spec; el trabajo sigue en la rama `feat/bootstrap-composition-root`)

**Created**: 2026-10-24

**Status**: Draft

**Proyecto**: HARNESS v2.5 | **Sprint**: 1 (decisión del PO, 2026-10-24) | **Historia**: **propuesta, sin ficha en `docs/04x`**; el ID provisional es `HU-00-08` y el PO lo formaliza o lo renombra | **Responsable**: C — Control y conexiones (decisión del PO, cierra PD-08) | **Requisitos**: sin RF propio (la historia es transversal); relacionada con RF-1.1 (HU-01-01) y RF-6.1 (HU-06-02) | **Depende de**: [HU-01-01](../../docs/04a-historias-fundacion.md#hu-01-01), [HU-01-03](../../docs/04a-historias-fundacion.md#hu-01-03), [HU-00-04](../../docs/04a-historias-fundacion.md#hu-00-04), [HU-03-01](../../docs/04b-historias-estado.md#hu-03-01), [HU-03-02](../../docs/04b-historias-estado.md#hu-03-02), [HU-05-01](../../docs/04c-historias-control.md#hu-05-01), [HU-06-01](../../docs/04c-historias-control.md#hu-06-01), [HU-07-02](../../docs/04d-historias-conexiones.md#hu-07-02)

**Input**: User description: "Raíz de composición `bootstrap.py` y punto de entrada ejecutable del harness: conecta el proveedor LiteLLM real, las herramientas de archivos con el área de trabajo, la política de permisos, el almacén SQLite con el registrador de eventos, el bus de eventos y la CLI, y expone un comando ejecutable. Historia propuesta, sin ficha en los documentos; el PO debe formalizarla."

## Clarifications

### Session 2026-10-24

Decisiones tomadas por el responsable antes de redactar (no son preguntas abiertas):

- La historia **no existe en los documentos**. Esta spec la propone para cerrar PD-08 (`docs/PROGRESO.md`: «ninguna historia es dueña de la raíz de composición ni del punto de entrada»). **No inventa criterios de aceptación oficiales**: los de abajo son propuestos y quedan marcados así hasta que el PO los ratifique (Principio V).
- La composición **solo conecta**: no añade reglas de negocio, no cambia puertos, eventos, bucle, política, almacén, herramientas ni CLI. Si para conectarlos hace falta cambiar alguno, es un hallazgo para A, B y C, no un cambio de esta historia.
- Sin área de trabajo configurada no se concede ninguna: ninguna herramienta de archivos puede ejecutarse: la política sin área trata cualquier uso como «preguntar» y, sin aprobación interactiva, lo deniega con motivo (la herramienta misma devolvería `[sin_area]` si llegara a ejecutarse; regla de HU-01-03). **No** se usa el directorio actual como área por omisión.
- Las acciones que hoy piden aprobación se siguen denegando con motivo hasta que llegue HU-05-03; esta historia no construye aprobación interactiva.
- Fuera de alcance: límites de turnos/tiempo/costo (HU-01-06), reanudar una sesión (HU-03-04), shell (HU-01-04), contexto y compactación, MCP, subagentes, el flujo de ticket del Coding Harness, redacción de secretos en eventos (HU-10-02) y empaquetado/instalador.

Respuestas del PO (2026-10-24):

- Q: ¿En qué sprint y a cuál área se asigna esta historia? → A: **Sprint 1, área C — Control y conexiones.** Cierra el hito del Sprint 1 (modelo real y sesión guardada en SQLite) y PD-08. Suma unas 3 h a un sprint ya sobrecargado (R-22); el PO asume esa carga.

- Q: ¿Qué pasa con Ctrl-C en mitad de un turno: termina el programa o solo se cancela el turno? → A: **Termina el programa** (recomendación aceptada): cierra la base, no muestra traza y sale con un código distinto de cero; lo ya guardado se conserva. Cancelar solo el turno y seguir en la sesión queda fuera de alcance (cancelación controlada, Sprint posterior).

No quedan preguntas abiertas en la spec.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación propuestos (pendientes de ratificación del PO)

Los criterios inmutables de las historias existentes no se tocan. Estos son nuevos y solo describen el comportamiento de la conexión.

- **AC-P1 — Una tarea de extremo a extremo.** Dado un archivo de configuración válido, una clave en el entorno y un área de trabajo configurada, cuando el usuario ejecuta el comando y escribe una tarea, entonces el modelo responde, las herramientas de archivos actúan solo dentro del área y la terminal muestra los eventos en tiempo real.
- **AC-P2 — Persistencia.** Dado ese mismo uso, cuando la sesión termina por cualquier vía, entonces todos los eventos emitidos están guardados en la base de datos de sesiones bajo un único identificador de sesión.
- **AC-P3 — Fallar cerrado al arrancar.** Dado cualquier problema de arranque (configuración inválida, falta la clave, falta la dependencia del proveedor, base de datos inutilizable), entonces el comando termina con un código distinto de cero y un mensaje de una línea en español, sin traza, sin secretos y sin haber pedido ninguna tarea.

### User Story 1 - Ejecutar una tarea real desde la terminal (Priority: P1)

Quien usa el harness abre una terminal, ejecuta un único comando y le da una instrucción al agente. El agente razona con el modelo configurado, lee y escribe archivos dentro del área de trabajo autorizada y el usuario ve cada paso a medida que ocurre. Es lo que hoy solo existe cableado a mano dentro de las pruebas.

**Why this priority**: es la única manera de que el producto exista fuera de las pruebas; sin esto ninguna otra historia se puede demostrar ni probar con un modelo real.

**Independent Test**: con un proveedor simulado inyectado, ejecutar la composición con una entrada de dos líneas («crea `notas.txt` con un saludo», «/salir») y comprobar que el archivo existe dentro del área, que la terminal mostró los eventos y que el código de salida es 0.

**Acceptance Scenarios**:

1. **Given** una configuración válida con área de trabajo, **When** el usuario escribe una tarea que pide crear un archivo dentro del área, **Then** el archivo se crea, la terminal muestra la solicitud y el resultado de la herramienta y la respuesta final del modelo.
2. **Given** la misma sesión, **When** el usuario escribe una segunda tarea que se refiere a la primera, **Then** el agente conserva la conversación anterior (el historial continúa entre líneas de la misma sesión).
3. **Given** que el modelo intenta escribir fuera del área, **When** se ejecuta la herramienta, **Then** se deniega con el motivo ya definido y el archivo no se crea.
4. **Given** una acción que pide aprobación, **When** el bucle la evalúa, **Then** se deniega con motivo y el modelo lo recibe, tal como hoy.
5. **Given** que el usuario escribe `/salir` o termina la entrada, **When** la sesión cierra, **Then** el código de salida es 0 y se muestra el texto de cierre ya definido.

---

### User Story 2 - La sesión queda guardada (Priority: P1)

Cada ejecución crea una sesión en la base de datos configurada y guarda cada evento en el momento en que ocurre, de modo que un corte abrupto no pierde lo ya confirmado.

**Why this priority**: el hito del Sprint 1 exige «la sesión queda guardada en SQLite»; además es la base de reanudar (HU-03-04) y de los criterios del ticket (HU-11-01).

**Independent Test**: ejecutar una sesión con proveedor simulado, abrir la base de datos después y comparar los eventos guardados con los que vio la terminal.

**Acceptance Scenarios**:

1. **Given** una ejecución normal, **When** termina, **Then** la base contiene una sesión con el modelo configurado y todos los eventos emitidos, en orden y con el mismo identificador de sesión.
2. **Given** que el proceso se interrumpe con Ctrl-C a mitad de un turno, **When** se inspecciona la base, **Then** el programa terminó con el código de interrupción, los eventos anteriores a la interrupción están guardados y el comando no muestra traza.
3. **Given** que la ruta de la base no existe, **When** arranca, **Then** se crea (incluidas sus carpetas) sin pedir nada al usuario.

---

### User Story 3 - Errores de arranque claros (Priority: P2)

Si algo impide arrancar, el usuario lo sabe en una línea, en español, con la causa y qué hacer, y el harness no deja nada a medias ni muestra secretos.

**Why this priority**: es el comportamiento de «fallar cerrado» aplicado al arranque; mejora la experiencia, pero el flujo feliz es lo que desbloquea al equipo.

**Independent Test**: provocar cada fallo de arranque con entradas controladas y comprobar mensaje, código de salida y ausencia de la clave en la salida.

**Acceptance Scenarios**:

1. **Given** una configuración con un campo inválido o una clave escrita en el archivo, **When** se ejecuta el comando, **Then** se muestra el error de configuración ya definido por HU-00-04 (una línea, sin el valor) y el código de salida es distinto de cero.
2. **Given** que falta la clave del proveedor elegido, **When** se ejecuta, **Then** el mensaje nombra la variable de entorno que falta, nunca su valor.
3. **Given** que la dependencia opcional del proveedor no está instalada, **When** se ejecuta, **Then** el mensaje indica el comando de instalación y no hay traza.
4. **Given** que no hay `paths.workspace_root`, **When** se ejecuta, **Then** el harness arranca, avisa una vez de que las herramientas de archivos están desactivadas por falta de área y cualquier intento de usar una herramienta de archivos se deniega con motivo (el modelo recibe `[approval_required_unavailable]`, comprobado en la implementación).
5. **Given** una base de datos con un esquema desconocido o ilegible, **When** se ejecuta, **Then** termina con un mensaje claro y sin modificarla.

---

### User Story 4 - La conexión es verificable sin red (Priority: P2)

Quien desarrolla puede ejecutar la misma composición en pruebas con un proveedor simulado, entrada y salida en memoria, base en memoria y reloj fijo, sin red ni claves.

**Why this priority**: sin esto la conexión se vuelve a duplicar a mano en cada prueba de integración y puede divergir de la real.

**Independent Test**: una prueba de integración construye la composición con dobles y comprueba la historia 1 y la 2 completas sin tocar red.

**Acceptance Scenarios**:

1. **Given** dependencias inyectadas, **When** se compone y se ejecuta una sesión, **Then** el resultado es idéntico en 20 ejecuciones seguidas.
2. **Given** la prueba de arquitectura, **When** se ejecuta, **Then** confirma que solo la raíz de composición importa a la vez núcleo, adaptadores, CLI y configuración, y que el núcleo no la importa.

### Edge Cases

- La entrada se cierra antes de la primera tarea: sale con 0 sin crear eventos de turno (la sesión sí se crea y se cierra).
- `Ctrl-C` durante la espera de una tarea o durante un turno: el programa termina (no se cancela solo el turno), con la base cerrada, sin traza y con el código de interrupción.
- El modelo falla con un error de proveedor (cuota, tiempo, servicio): se muestra con el mecanismo ya existente y la sesión sigue; no cierra el programa.
- Dos ejecuciones simultáneas sobre la misma base: la segunda no corrompe la primera (el almacén ya lo gestiona); si no puede abrir, falla cerrada con mensaje.
- El área de trabajo apunta a una carpeta que no existe: el área falla cerrada, cualquier uso de una herramienta de archivos se deniega con motivo y se avisa al arrancar.
- Una variable `HARNESS_CONFIG` apunta a un archivo inexistente: se muestra el error de HU-00-04 tal cual.
- El modelo configurado es `fake/…` (el valor de `config.example.toml`): el arranque lo rechaza con el mensaje «El proveedor 'fake' solo existe para pruebas…» y código 2, en vez de fallar en el primer turno.
- El terminal no puede codificar los caracteres de una respuesta: ya lo resuelve la CLI; la composición no lo reimplementa.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El harness MUST ofrecer un único comando ejecutable que inicie una sesión interactiva en la terminal; no hay otra forma soportada de arrancar el producto.
- **FR-002**: Al arrancar, el harness MUST cargar la configuración con las reglas existentes (archivo y entorno) y MUST mostrar cualquier error de configuración con el texto ya definido, sin traza ni valores secretos.
- **FR-003**: El harness MUST construir, a partir de esa configuración, todas las piezas del bucle: proveedor del modelo, registro con las cuatro herramientas de archivos, área de trabajo, política de permisos con las reglas de configuración, bus de eventos, almacén de sesiones y la CLI.
- **FR-004**: El harness MUST conectar el registrador de eventos al bus **antes** de que ocurra el primer evento de la sesión, de modo que ninguno se pierda.
- **FR-005**: El harness MUST crear una sesión nueva en el almacén al arrancar y usar su identificador en todos los turnos y eventos de la ejecución.
- **FR-006**: El harness MUST mantener el historial de la conversación entre las líneas de una misma sesión.
- **FR-007**: Sin área de trabajo utilizable, el harness MUST arrancar con las herramientas de archivos desactivadas (fallan cerradas) y MUST avisar al usuario una vez; MUST NOT usar el directorio actual ni ningún otro como área por omisión.
- **FR-008**: Si falta la clave, la dependencia opcional del proveedor o la base de datos no se puede abrir, el harness MUST terminar con código distinto de cero y un mensaje de una línea en español, antes de pedir ninguna tarea.
- **FR-009**: Al terminar por `/salir`, fin de entrada o interrupción de teclado, el harness MUST cerrar el almacén y MUST NOT mostrar traza. Una interrupción de teclado MUST terminar el programa entero (no solo el turno en curso). Los códigos de salida MUST distinguir: terminación normal (0), error durante un turno (el que ya define la CLI), fallo de arranque y interrupción de teclado (130, la convención de las terminales), todos distintos entre sí.
- **FR-010**: El harness MUST NOT escribir en ninguna salida (pantalla, eventos, errores, base de datos) el valor de ninguna clave.
- **FR-011**: La composición MUST NOT cambiar puertos, entidades, catálogo de eventos, bucle, política, almacén, herramientas ni CLI; solo los usa por su API pública.
- **FR-012**: Todo lo que toca el exterior (ruta de configuración, entorno, flujos de entrada y salida, proveedor, reloj, generador de identificadores) MUST poder inyectarse para probar la composición sin red, claves ni consola.
- **FR-013**: Las acciones que piden aprobación MUST seguir denegándose con motivo hasta que exista la aprobación interactiva; la composición MUST NOT conceder permisos por su cuenta.
- **FR-015**: Con el proveedor real por omisión, un modelo cuyo proveedor solo existe para pruebas (`fake/…`) MUST rechazarse al arrancar, antes de abrir la base, con un mensaje de una línea; con un proveedor inyectado se acepta (convergencia T016).
- **FR-014**: La raíz de composición MUST ser el único módulo que conoce a la vez el núcleo, los adaptadores, la CLI y la configuración; el núcleo MUST NOT importarla (guarda de arquitectura).

### Key Entities *(include if feature involves data)*

- **Composición**: el conjunto de piezas ya conectadas (proveedor, registro, política, bus, almacén, bucle) para una ejecución; se construye una vez por ejecución y no se comparte.
- **Sesión de ejecución**: la sesión guardada en el almacén que identifica todos los eventos de una ejecución del comando; ya definida por HU-03-01.
- **Configuración efectiva**: el resultado de combinar archivo y entorno (modelo, límites, rutas, permisos, clave); ya definida por HU-00-04.

### Lo que ya existe y lo que cambia

- **Existe y no se toca**: `core/` completo (puertos, bucle, eventos, política, registro, bus), `config.py`, `cli/`, `adapters/storage/`, `adapters/tools/`, `adapters/system/`, `adapters/providers/`, `adapters/converters/`.
- **Se añade**: la raíz de composición (`src/harness_agent/bootstrap.py`), el punto de entrada del paquete (`__main__.py` y un comando instalable declarado en `pyproject.toml`), sus pruebas (unitarias, de integración con proveedor simulado, de arquitectura) y la actualización de `CLAUDE.md`, la skill de carpetas y `PROGRESO.md`.
- **Hallazgos previos que esta historia recoge**: PD-08 (dueño del arranque), la conexión manual de `make_rig` y la nota de CLAUDE.md «`bootstrap.py` aún no existe».

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona nueva en el equipo, con la configuración y la clave listas, ejecuta una tarea de extremo a extremo con **un solo comando** y sin escribir código.
- **SC-002**: En el 100 % de las ejecuciones normales, el número de eventos guardados en la base es igual al de eventos que vio la terminal.
- **SC-003**: Cada uno de los fallos de arranque listados en la Historia 3 produce exactamente **una línea** de mensaje en español, un código de salida distinto de cero y **cero** apariciones del valor de la clave en la salida.
- **SC-004**: Con proveedor simulado, 20 ejecuciones consecutivas de la misma sesión producen la misma salida y los mismos eventos guardados; **cero** conexiones de red.
- **SC-005**: **Cero** archivos creados fuera del área de trabajo en todas las pruebas de la composición, incluidos los intentos de escape.
- **SC-006**: El arranque (hasta mostrar el prompt) tarda menos de 2 segundos en el equipo de referencia **sin contar la carga de la biblioteca del proveedor**, que HU-07-02 midió en unos 4 segundos y se paga una sola vez antes del prompt (corregido en `/speckit-plan`; la redacción original no lo distinguía).
- **SC-007**: Las cuatro puertas de calidad y `pytest tests/architecture` siguen en verde en Windows y Linux, con la cobertura del módulo nuevo en 100 % de líneas y ramas.

## Assumptions

- El comando se invoca como `python -m harness_agent` y, una vez instalado el paquete, como `harness`; ambos hacen lo mismo.
- La clave llega solo por variable de entorno (regla vigente); el comando no la pide por pantalla ni la guarda.
- El modelo se toma de `config.model` (`<proveedor>/<modelo>`) y el tope de salida de `limits.max_output_tokens`, tal como ya lo definen HU-00-04 y HU-07-02.
- Los límites de turnos, tiempo y costo de `config.limits` se ignoran hasta HU-01-06; la composición no los inventa.
- La base de datos por omisión es la de `paths.sessions_db` (`.harness/sessions.db`, ignorada por git); la protección de esa base frente a las herramientas es PD-09 y no se resuelve aquí.
- La redacción de secretos antes de persistir (PD-10) no existe aún; esta historia no la añade ni la oculta.
- La prueba real contra un modelo con clave es manual y se omite sin clave, como la de HU-07-02; no entra en la CI.
- Un solo usuario y una sola sesión por ejecución; no hay modo no interactivo ni opciones de línea de comandos más allá de las que ya admite la configuración.
- La capacidad de C en el Sprint 1 ya está excedida (R-22); el PO asume esa carga y el exceso se anota como aviso de capacidad en `PROGRESO.md` al implementar.
