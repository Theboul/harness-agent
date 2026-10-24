# Feature Specification: HU-01-02 — Registro de herramientas con esquema y validación

**Feature Branch**: `006-tool-registry-validation`

**Created**: 2026-10-17

**Status**: En revisión (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 1 | **Responsable**: C — Control y conexiones | **Tareas de referencia**: Sp1-15, Sp1-16, Sp1-17 | **Requisitos**: RF-1.2, RF-1.3, RNF-2, RNF-13 | **Depende de**: HU-00-01

**Input**: User description: "HU-01-02 — Registro de herramientas con esquema y validación. Como equipo de desarrollo quiero registrar una herramienta con nombre, descripción, esquema JSON y nivel de riesgo, y validar los argumentos antes de ejecutarla, para añadir herramientas sin tocar el bucle. Si los argumentos no cumplen el esquema, no se ejecuta y el modelo recibe un error que indica el campo inválido (AC-01). Una herramienta nueva funciona sin modificar el bucle (AC-02). Alcance: solo el registro y la validación; sin herramientas concretas ni shell. Requisitos: RF-1.2, RF-1.3, RNF-2, RNF-13."

## Clarifications

### Session 2026-10-18

- Q: Cuando una llamada incluye un campo que el esquema no declara y el esquema no dice nada sobre campos adicionales, ¿se rechaza, se acepta tal cual o se descarta el campo extra? → A: Se rechaza la llamada (falla cerrada) y el error nombra el campo no declarado; solo se aceptan campos adicionales si el esquema los permite de forma explícita.
- Q: ¿Qué caracteres y qué longitud máxima debe permitir el nombre de una herramienta al registrarla? → A: Solo letras ASCII, dígitos, guion bajo y guion, con una longitud de 1 a 64 caracteres.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registrar una herramienta con su definición completa (Priority: P1)

Como equipo de desarrollo, quiero registrar una herramienta declarando su nombre, su descripción, el esquema JSON de sus argumentos y su nivel de riesgo, y poder consultarla después por nombre o listar todo el catálogo, para que el resto del sistema conozca qué herramientas existen y cómo se usan sin conocer ninguna en particular.

**Why this priority**: Es la base de la historia. Sin un catálogo con definiciones completas no hay nada que validar, ni se le puede presentar al modelo qué herramientas tiene, ni la política de permisos puede conocer el riesgo de cada una (regla de negocio 2: toda herramienta declara su nivel de riesgo).

**Independent Test**: Puede probarse registrando herramientas de prueba (dobles) con definiciones válidas e inválidas, y comprobando que las válidas quedan consultables con sus cuatro atributos intactos y que las inválidas o duplicadas se rechazan sin alterar el catálogo. No requiere bucle, proveedor ni herramientas reales.

**Acceptance Scenarios**:

1. **Given** un registro vacío, **When** se registra una herramienta con nombre, descripción, esquema JSON válido y nivel de riesgo, **Then** la herramienta queda disponible por su nombre y aparece en el listado del catálogo con sus cuatro atributos tal como se declararon.
2. **Given** un registro que ya contiene una herramienta con cierto nombre, **When** se intenta registrar otra con el mismo nombre, **Then** el registro se rechaza con un error de colisión de nombre y la herramienta original permanece sin cambios.
3. **Given** una herramienta cuyo esquema JSON está mal formado, **When** se intenta registrar, **Then** el registro se rechaza en ese momento con un error que indica el defecto del esquema, de modo que el modelo nunca llega a ver una herramienta con un esquema inservible.
4. **Given** una herramienta con nombre vacío o fuera del formato permitido, descripción vacía o un nivel de riesgo ausente o no reconocido, **When** se intenta registrar, **Then** el registro se rechaza indicando cuál de los atributos es inválido y el catálogo no cambia.
5. **Given** varias herramientas registradas, **When** un consumidor consulta una por nombre inexistente, **Then** obtiene una ausencia explícita (no una herramienta inventada ni un fallo no controlado); y **When** lista el catálogo, **Then** recibe todas las registradas en un orden estable (el de registro).

---

### User Story 2 - Validar argumentos antes de ejecutar y devolver al modelo un error accionable (Priority: P1) [AC-01]

Como equipo de desarrollo, quiero que los argumentos de cada llamada del modelo se validen contra el esquema de la herramienta antes de ejecutarla, y que cuando no cumplan, la herramienta no se ejecute y el modelo reciba un error que indique el campo inválido, para que el modelo pueda corregir la llamada y reintentar sin que una herramienta actúe con datos mal formados.

**Why this priority**: Es el criterio de aceptación AC-01 y la barrera de seguridad de la historia: ejecutar una herramienta (escribir un archivo, lanzar un comando) con argumentos incorrectos puede causar daño o resultados erróneos. También es lo que permite al modelo autocorregirse en lugar de quedar bloqueado.

**Independent Test**: Puede probarse con una herramienta de prueba que cuenta sus ejecuciones: se le envían llamadas con campo requerido ausente, tipo incorrecto, valor fuera de rango o de enumeración, campos anidados inválidos, campos que el esquema no declara y argumentos que ni siquiera son un objeto; en todos los casos el contador de ejecuciones permanece en cero y el mensaje nombra el campo inválido. Un consumidor mínimo de prueba que imita al bucle verifica que ese mensaje es utilizable tal cual como resultado de error para el modelo.

**Acceptance Scenarios**:

1. **Given** una herramienta registrada con un campo requerido, **When** el modelo la invoca omitiendo ese campo, **Then** la herramienta no se ejecuta y el error nombra el campo faltante.
2. **Given** una herramienta registrada con un campo de tipo numérico, **When** el modelo envía texto en ese campo, **Then** la herramienta no se ejecuta y el error nombra el campo y el tipo esperado.
3. **Given** un campo restringido a una lista de valores permitidos o a un rango, **When** el modelo envía un valor fuera de lo permitido, **Then** la herramienta no se ejecuta y el error nombra el campo y la restricción incumplida.
4. **Given** un esquema con objetos anidados, **When** un campo anidado es inválido, **Then** el error identifica el campo con su ruta completa (por ejemplo, `opciones.tiempo_maximo`).
5. **Given** una llamada con varios campos inválidos a la vez, **When** se valida, **Then** el error enumera los campos inválidos (hasta 20) en una sola respuesta, de modo que el modelo pueda corregirlos en un único reintento.
6. **Given** una herramienta cuyo esquema no declara cierto campo ni permite campos adicionales de forma explícita, **When** el modelo envía ese campo, **Then** la herramienta no se ejecuta y el error nombra el campo no declarado; y **Given** un esquema que sí permite campos adicionales de forma explícita, **When** el modelo los envía, **Then** la llamada se aprueba.
7. **Given** una llamada con argumentos que cumplen el esquema, **When** se valida, **Then** la validación aprueba la llamada, entrega los argumentos sin alteraciones y la herramienta puede ejecutarse.
8. **Given** una llamada a un nombre de herramienta que no está registrado, **When** se valida, **Then** no se ejecuta nada y el error indica que la herramienta es desconocida, citando el nombre solicitado.

---

### User Story 3 - Incorporar una herramienta nueva sin modificar el bucle (Priority: P2) [AC-02]

Como equipo de desarrollo, quiero que una herramienta nueva, una vez registrada, funcione cuando el modelo la invoca sin tocar el código del bucle agéntico, para que cada herramienta futura (archivos, shell, memoria, MCP) se añada únicamente registrándola.

**Why this priority**: Es el criterio de aceptación AC-02 y el propósito declarado de la historia ("añadir herramientas sin tocar el bucle", RNF-2). Se apoya en las historias 1 y 2, por eso su prioridad es P2, pero es lo que justifica todo el diseño del registro.

**Independent Test**: Puede probarse escribiendo un consumidor genérico mínimo (que imita al bucle: consulta el catálogo, valida, ejecuta y devuelve el resultado) y luego registrando una herramienta de prueba que ese consumidor no conocía cuando se escribió; la herramienta funciona sin cambiar una sola línea del consumidor ni del registro.

**Acceptance Scenarios**:

1. **Given** un consumidor genérico del registro ya escrito, **When** se registra una herramienta nueva con un esquema y un riesgo distintos a los de cualquier otra y el modelo la invoca, **Then** la llamada se valida, se ejecuta y su resultado vuelve al modelo sin modificar el consumidor ni el registro.
2. **Given** dos herramientas con distinto nivel de riesgo, **When** la política de permisos consulta el catálogo, **Then** obtiene el nivel de riesgo declarado de cada una sin necesidad de conocer la herramienta concreta.
3. **Given** el catálogo con varias herramientas, **When** el consumidor genérico prepara lo que se le presenta al modelo, **Then** dispone del nombre, la descripción y el esquema de cada herramienta registrada, sin código específico por herramienta.

---

### Edge Cases

- **Herramienta sin argumentos**: un esquema que no declara campos es válido; una llamada con argumentos vacíos pasa y una llamada con cualquier campo se rechaza como campo no declarado, salvo que el esquema permita campos adicionales de forma explícita.
- **Argumentos que no son un objeto** (ausentes, nulos, una lista o un texto): se rechazan como inválidos con un error comprensible, no con un fallo interno.
- **Valores nulos en campos requeridos**: se tratan como incumplimiento del esquema, con el campo identificado.
- **Esquema con referencias externas** (a otros archivos o a una dirección remota): la validación debe poder hacerse sin red ni acceso a otros recursos, por lo que un esquema que dependa de ellos se rechaza al registrarse.
- **Valores sensibles en argumentos** (por ejemplo, claves o tokens enviados por error): el error describe el campo y la expectativa, pero no reproduce los valores recibidos, para no filtrarlos al contexto del modelo ni a las trazas.
- **Muchas violaciones a la vez** (por ejemplo, una lista larga con elementos inválidos): el error conserva todas las violaciones, pero el texto para el modelo enumera las primeras 20 y resume el resto con el número de omitidas.
- **Reintentos repetidos con el mismo error**: la validación es determinista; la misma llamada inválida produce siempre el mismo error. El control de reintentos y de límites de turnos pertenece al bucle (HU-01-01), no al registro.
- **Fallo durante la ejecución de una herramienta ya validada**: queda fuera de esta historia; el manejo de fallos de ejecución corresponde al bucle y a cada herramienta.
- **Nombre con espacios, acentos, puntos u otros caracteres fuera del formato permitido, o de más de 64 caracteres**: se rechaza al registrar, porque el proveedor de modelos podría rechazarlo después y el fallo sería mucho más difícil de diagnosticar. Las herramientas que vengan de fuentes con otras convenciones de nombres (por ejemplo, MCP) deben normalizar su nombre antes de registrarse.

## Requirements *(mandatory)*

### Functional Requirements

**Registro (RF-1.2, RF-1.3)**

- **FR-001**: El sistema MUST permitir registrar una herramienta declarando cuatro atributos obligatorios: nombre único, descripción, esquema JSON de sus argumentos y nivel de riesgo.
- **FR-002**: El sistema MUST rechazar el registro de una herramienta cuyo nombre sea vacío, supere los 64 caracteres o contenga caracteres distintos de letras ASCII, dígitos, guion bajo y guion, cuya descripción sea vacía, o cuyo nivel de riesgo falte o no sea uno de los reconocidos, indicando cuál atributo es inválido y sin modificar el catálogo.
- **FR-003**: El sistema MUST rechazar, en el momento del registro, un esquema que no sea un esquema JSON bien formado, que dependa de recursos externos para validarse, que no describa los argumentos como un objeto en su raíz, que declare como requerido un campo que no figura entre sus propiedades, que supere los 32 niveles de anidamiento o que use palabras clave del estándar que el sistema no soporta (por ejemplo, `anyOf`, `oneOf`, `$ref` o `pattern`), indicando el defecto encontrado. Lo que el sistema no sabe validar se rechaza al registrar y nunca se ignora en silencio.
- **FR-004**: El sistema MUST rechazar el registro de una herramienta cuyo nombre ya exista, conservando intacta la herramienta registrada previamente. La unicidad distingue mayúsculas y minúsculas (`Shell` y `shell` son nombres distintos).
- **FR-005**: El sistema MUST permitir consultar una herramienta por nombre (devolviendo una ausencia explícita si no existe) y listar todas las herramientas registradas en orden estable de registro, exponiendo en ambos casos los cuatro atributos declarados.

**Validación de argumentos (RF-1.3, AC-01)**

- **FR-006**: El sistema MUST validar los argumentos de toda llamada contra el esquema de la herramienta nombrada antes de que esa herramienta se ejecute.
- **FR-007**: Cuando los argumentos no cumplan el esquema, incluido el caso de campos que el esquema no declara (a menos que permita campos adicionales de forma explícita), el sistema MUST impedir la ejecución de la herramienta (cero efectos sobre archivos, procesos u otros recursos) y MUST producir un error que indique cada campo inválido (con el tope de FR-009), usando la ruta completa para campos anidados, junto con el motivo del incumplimiento.
- **FR-008**: El error de validación MUST estar redactado como texto claro (según el formato definido en `contracts/tool_registry_contract.md`, §3), apto para devolverse al modelo como resultado de error sin transformaciones, con información suficiente para corregir la llamada; MUST NOT incluir trazas internas ni reproducir los valores recibidos.
- **FR-009**: El sistema MUST detectar todas las violaciones en una sola validación, no solo la primera, y el error MUST conservarlas todas. El texto para el modelo MUST enumerar hasta 20 violaciones, en orden determinista (el definido en `contracts/tool_registry_contract.md`, §3), y resumir el resto indicando cuántas se omiten, para no inflar el contexto con entradas patológicas.
- **FR-010**: Cuando una llamada nombre una herramienta no registrada, el sistema MUST responder con un error de herramienta desconocida que cite el nombre solicitado, sin ejecutar nada.
- **FR-011**: Cuando los argumentos cumplan el esquema, el sistema MUST aprobar la llamada y entregar los argumentos sin alteraciones.
- **FR-012**: La validación MUST ser determinista, no tener efectos secundarios, no requerir red ni proveedor de modelo, y no modificar los argumentos recibidos.

**Extensibilidad y desacoplamiento (AC-02, RNF-2, RNF-13)**

- **FR-013**: Incorporar una herramienta nueva MUST requerir únicamente registrarla; el bucle agéntico y el propio registro MUST NOT necesitar modificaciones por cada herramienta añadida.
- **FR-014**: El consumidor del registro MUST poder obtener, para cualquier herramienta registrada y mediante la misma interfaz uniforme, su nombre, descripción, esquema, nivel de riesgo y la forma de ejecutarla, sin conocer su implementación concreta.
- **FR-015**: El registro MUST exponer el nivel de riesgo declarado de cada herramienta para que la política de permisos lo consulte, sin decidir ni aplicar permisos por sí mismo.
- **FR-016**: El registro y la validación MUST poder usarse y probarse de forma automatizada sin proveedor de modelos real, sin red y sin interfaz de usuario, y MUST respetar la regla de que el núcleo no depende de SDK de proveedores ni de interfaz.

### Key Entities *(include if feature involves data)*

- **Herramienta**: Capacidad que el modelo puede invocar. Atributos: nombre único, descripción para el modelo, esquema de argumentos, nivel de riesgo y la forma de ejecutarse con argumentos ya validados. Es el contrato definido en HU-00-01.
- **Esquema de argumentos**: Descripción en JSON de los campos que acepta una herramienta (tipos, campos requeridos, valores permitidos, límites, estructuras anidadas). Es lo que se usa para validar y, a la vez, lo que se presenta al modelo.
- **Nivel de riesgo**: Clasificación declarada por cada herramienta (bajo, medio o alto, según el contrato base) que consume la política de permisos para decidir si permite, pregunta o deniega.
- **Registro de herramientas (catálogo)**: Colección de herramientas disponibles, con nombre único, que se puede consultar, listar y usar para validar llamadas. Es el único punto por el que el bucle conoce las herramientas.
- **Llamada a herramienta**: Petición del modelo, formada por el nombre de una herramienta y un conjunto de argumentos, que debe validarse antes de ejecutarse.
- **Error de validación**: Resultado de una validación fallida: lista de violaciones, cada una con el campo (ruta completa) y el motivo, redactada en texto para el modelo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de las llamadas con argumentos que violan el esquema en el conjunto de casos de prueba (campo requerido ausente, tipo incorrecto, valor fuera de enumeración o de rango, campo anidado inválido, campo no declarado en el esquema, argumentos que no son un objeto) se rechazan antes de ejecutar la herramienta, con cero ejecuciones registradas.
- **SC-002**: En el 100 % de los rechazos por validación, el mensaje identifica cada campo inválido con su ruta y el motivo, incluidos los casos con dos o más campos inválidos a la vez; si hay más de 20, el mensaje enumera 20 e indica cuántas se omiten.
- **SC-003**: Una herramienta nueva, con esquema y riesgo distintos a los existentes, funciona de extremo a extremo (consulta, validación, ejecución y resultado) con cero líneas modificadas en el bucle y en el registro.
- **SC-004**: El 100 % de los intentos de registro con atributos faltantes, esquema mal formado o nombre duplicado se rechazan con un motivo claro, y el catálogo queda idéntico a como estaba antes del intento.
- **SC-005**: La validación de una llamada añade en promedio menos de 10 ms de latencia propia para esquemas de hasta 20 campos, de modo que no sea perceptible dentro de un turno del agente.
- **SC-006**: Las pruebas automatizadas de la historia (incluidos los casos de argumentos mal formados) pasan al 100 % tanto en Windows como en Linux, sin red ni proveedor de modelos real.

## Assumptions

- **Contratos base**: La interfaz de herramienta, el registro y los niveles de riesgo ya existen desde HU-00-01. Esta historia los implementa y usa tal como están; cualquier cambio a esas interfaces requiere el visto bueno de los tres integrantes (regla de negocio 2 de HU-00-01).
- **Qué hace y qué no hace el registro**: El registro cataloga y valida; no ejecuta la herramienta ni convierte el error en un mensaje del modelo. Esa orquestación es del bucle agéntico (HU-01-01, aún pendiente). Para verificar AC-01 y AC-02 en esta historia se usa un consumidor mínimo de prueba que imita al bucle, hasta que la integración real exista.
- **Fuera de alcance**: Herramientas concretas (archivos en HU-01-03, shell en HU-01-04, preguntar al usuario, delegación a subagentes); evaluación de permisos y aprobación humana (HU-05-xx); herramientas de memoria y MCP (se registrarán después por el mismo mecanismo); eliminar o reemplazar herramientas ya registradas; persistir el catálogo entre sesiones; manejo de fallos durante la ejecución de la herramienta.
- **Esquemas admitidos**: Se admite solo el subconjunto de JSON Schema definido en FR-003: argumentos como objeto con tipos básicos, campos requeridos, valores enumerados, límites numéricos y de longitud, y objetos o listas anidados. Los mecanismos que exigirían acceso externo se rechazan al registrar (ver Edge Cases). La versión concreta del estándar se decide en la planificación técnica.
- **Formato de nombres**: Un nombre válido usa solo letras ASCII, dígitos, guion bajo y guion, con 1 a 64 caracteres (por ejemplo `leer_archivo`), que es el formato que aceptan los proveedores de modelos habituales. La normalización de nombres que vengan de fuentes externas (MCP, HU-08-03) corresponde a esas historias.
- **Mensajes de error**: Se redactan en español, el idioma de trabajo del proyecto, conservando los nombres de campo tal cual aparecen en el esquema.
- **Rendimiento**: El umbral de 10 ms de SC-005 es un valor por defecto razonable para medir la latencia propia del harness (decisión V-07), y puede ajustarse si las mediciones lo justifican.
- **Requisitos RNF-2 y RNF-13**: El texto íntegro de estos requisitos no figura en la documentación activa del repositorio; solo su trazabilidad (RNF-2 se asigna únicamente a esta historia y RNF-13 se comparte con HU-00-01). Se interpretan, respectivamente, como extensibilidad sin tocar el bucle (FR-013 y FR-014) y desacoplamiento del núcleo respecto de proveedores, interfaz e infraestructura (FR-016). Conviene confirmar esta lectura con el Product Owner antes de cerrar la historia.
- **Disciplina de proceso**: La historia se limita al Sprint 1 (constitución, Principio VI), se verifica con pruebas automatizadas sin red usando dobles de prueba (Principio IV) y no altera sus criterios de aceptación AC-01 y AC-02 (Principio V).
