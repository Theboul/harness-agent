# Feature Specification: HU-00-04 — Configuración por archivo y variables de entorno

**Feature Branch**: `010-file-env-configuration` (el trabajo se hace en la rama `gustavo`; el nombre del directorio de la spec no dicta la rama)

**Created**: 2026-10-20

**Status**: En revisión (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 1 | **Responsable**: B — Estado (la implementa Gustavo en nombre de B) | **Tareas de referencia**: Sp1-09, Sp1-10, Sp1-11 | **Requisitos**: RF-7.6, RNF-16, RNF-21 | **Depende de**: HU-00-01

**Input**: User description: "HU-00-04 — Configuración por archivo y variables de entorno. Como usuario operador quiero configurar modelo, límites y rutas en un archivo y las claves en variables de entorno, para cambiar de modelo o de límite sin tocar el código ni exponer claves. El sistema se configura con un archivo (modelo, límites, rutas) y las claves se leen solo de variables de entorno."

## Clarifications

### Session 2026-10-20

- Q: Para un mismo valor no secreto (por ejemplo, el modelo), ¿qué prevalece, el archivo o una variable de entorno? → A: Los valores no secretos los define solo el archivo de configuración; las variables de entorno se usan únicamente para claves, sin sobrescribir ningún valor no secreto (la única excepción es `HARNESS_CONFIG`, que solo indica la ubicación del archivo).
- Q: ¿Cuál es la ubicación por defecto del archivo de configuración y cómo se indica otra? → A: Por defecto, `config.toml` en el directorio de trabajo actual. Otra ubicación se indica con un parámetro explícito de la función de carga o con la variable de entorno `HARNESS_CONFIG`; el parámetro explícito gana. El argumento de la terminal queda fuera (lo aportará la CLI). `config.toml` y `.env` van al `.gitignore`; solo se versionan las plantillas `config.example.toml` y `.env.example`.
- Q: Si el archivo de configuración no existe, ¿el sistema aborta o arranca con valores por defecto? → A: Se detiene el arranque con un error claro (falla cerrada); no se arranca con valores por defecto. Un archivo ilegible o con sintaxis rota también detiene el arranque.
- Q: ¿Se ignora también el directorio local de datos por defecto en el control de versiones? → A: Sí; el responsable aceptó la ampliación D3 del plan y pasa a ser parte de FR-019 (la ruta por defecto de la base de datos de sesiones vive ahí y puede contener conversaciones sensibles; su nombre concreto lo fija el plan).
- Q: ¿Qué significa «mismo comportamiento en Windows y Linux» para las rutas? → A: Para el mismo archivo, rutas válidas para el sistema donde se ejecuta; una ruta con la forma de otro sistema no se reinterpreta (FR-022).

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación y reglas de negocio de la historia (inmutables)

Copiados tal cual de `docs/04a-historias-fundacion.md` (HU-00-04). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

**Reglas de negocio**

1. Las claves nunca se escriben en archivos ni en el repositorio.
2. Existe una plantilla de ejemplo sin secretos y un .gitignore adecuado.

**Criterios de aceptación**

- **AC-01 — Cambio de modelo sin tocar el código.** Dado un archivo de configuración con otro modelo, cuando arranca el sistema, entonces usa ese modelo sin cambios de código.
- **AC-02 — Sin claves en el repositorio.** Dado el repositorio completo, cuando se busca un secreto, entonces ninguna clave aparece en archivos ni en el historial de cambios.

### User Story 1 - Cambiar de modelo y de límites editando un archivo (Priority: P1) [AC-01]

Como usuario operador, quiero indicar en un archivo de configuración el modelo, los límites y las rutas que usa el sistema, para cambiar de modelo o de límite editando ese archivo, sin tocar el código.

**Why this priority**: Es el criterio de aceptación AC-01 y el propósito de la historia. Sin una configuración cargada de forma uniforme, cada historia posterior (herramientas de archivos, sesiones, límites del bucle, proveedores) tendría que leer sus propios valores.

**Independent Test**: Puede probarse con archivos de configuración de prueba en un directorio temporal: se arranca la carga con un archivo que indica un modelo, se repite con otro modelo y se comprueba que la configuración resultante refleja cada vez el modelo del archivo, sin modificar ningún código. No requiere proveedor real, red ni las historias que consumirán los demás valores.

**Acceptance Scenarios**:

1. **Given** un archivo de configuración que indica el modelo A, **When** arranca el sistema, **Then** la configuración entrega el modelo A al resto del sistema; **And** al cambiar el archivo para indicar el modelo B y volver a arrancar, entrega el modelo B sin ningún cambio de código.
2. **Given** un archivo que cambia uno o más límites por sesión (turnos, tiempo o consumo) o una ruta, **When** arranca el sistema, **Then** la configuración entrega los valores indicados y, para cualquier campo que el archivo no mencione, su valor por defecto documentado.
3. **Given** un archivo con un valor de tipo incorrecto o fuera de rango (por ejemplo, un límite de turnos negativo o escrito como texto), **When** arranca el sistema, **Then** el arranque se detiene con un mensaje que nombra el campo y lo que se esperaba, sin trazas de pila.
4. **Given** un archivo con un campo que el esquema de configuración no conoce (por ejemplo, un error tipográfico en el nombre de un límite), **When** arranca el sistema, **Then** el arranque se detiene con un mensaje que nombra el campo desconocido; nunca se ignora en silencio.
5. **Given** un archivo de configuración válido, **When** el sistema entrega la configuración al resto del sistema, **Then** la recibe como un conjunto de valores ya tipados que no se pueden modificar durante la ejecución.
6. **Given** un archivo `config.toml` en el directorio de trabajo actual y ninguna otra indicación, **When** arranca el sistema, **Then** lee ese archivo; **And** si se indica otra ubicación con la variable `HARNESS_CONFIG`, lee esa; **And** si además se indica con un parámetro explícito de la función de carga, prevalece el parámetro.
7. **Given** que el archivo no existe, es ilegible o tiene la sintaxis rota, **When** arranca el sistema, **Then** el arranque se detiene con un error claro en español que nombra el archivo (y la línea cuando sea posible, sin reproducir su contenido) y no se arranca con valores por defecto.
8. **Given** una variable de entorno con el mismo nombre que un valor no secreto del archivo (por ejemplo, el modelo), **When** arranca el sistema, **Then** la configuración entrega el valor del archivo; las variables de entorno no sobrescriben valores no secretos.

---

### User Story 2 - Claves solo desde variables de entorno, con error claro si faltan (Priority: P1)

Como usuario operador, quiero que las claves de los proveedores se lean únicamente de variables de entorno y que, si falta una, el sistema me diga cuál sin mostrar su valor, para usar modelos reales sin escribir ni exponer claves.

**Why this priority**: Es el flujo general 4 de la historia y la regla de negocio 1 (RF-7.6, RNF-16). Una clave expuesta en un archivo, en un mensaje de error o en un registro es un daño difícil de revertir; por eso comparte prioridad con la carga básica.

**Independent Test**: Puede probarse con un entorno simulado (variables definidas y retiradas por la propia prueba, sin tocar el entorno real) y una clave de prueba con un valor centinela reconocible: se comprueba que la clave se obtiene del entorno, que su ausencia produce un error que nombra la variable y que el centinela no aparece en ningún mensaje, texto de objeto ni salida.

**Acceptance Scenarios**:

1. **Given** un modelo que requiere clave y la variable de entorno correspondiente definida, **When** arranca el sistema, **Then** la configuración dispone de la clave, tomada solo del entorno.
2. **Given** un modelo que requiere clave y la variable de entorno ausente (o definida pero vacía), **When** arranca el sistema, **Then** el arranque se detiene con un mensaje que nombra la variable que falta y explica cómo definirla; **And** el mensaje no incluye el valor de ninguna clave ni parte de él.
3. **Given** un archivo de configuración que contiene un campo de clave o de secreto, **When** arranca el sistema, **Then** el archivo se rechaza con un mensaje que nombra el campo y explica que las claves van solo en variables de entorno; **And** el mensaje no reproduce el valor del campo.
4. **Given** una configuración cargada con una clave, **When** se muestra el objeto de configuración (texto, representación para depuración o mensaje de error), **Then** la clave no aparece en ninguna de esas salidas.
5. **Given** un modelo que no requiere clave (por ejemplo, el proveedor simulado de las pruebas), **When** arranca el sistema sin ninguna variable de clave, **Then** el arranque no exige ninguna.

---

### User Story 3 - Ninguna clave en el repositorio: plantillas y .gitignore (Priority: P2) [AC-02]

Como usuario operador y como equipo, quiero una plantilla de ejemplo sin secretos y un .gitignore que excluya los archivos con claves reales, y una comprobación que lo verifique, para que ninguna clave llegue nunca a un archivo versionado ni al historial.

**Why this priority**: Es el criterio de aceptación AC-02 y la regla de negocio 2. Se apoya en las historias 1 y 2 (hay que saber qué archivos y variables existen), por eso es P2, pero es la barrera que impide que un descuido humano exponga una clave.

**Independent Test**: Puede probarse sobre la lista de archivos versionados del repositorio: una comprobación automática busca patrones de claves conocidos y archivos de secretos versionados, y falla si encuentra alguno; las plantillas se comprueban abriéndolas y verificando que no contienen secretos. El historial se comprueba con un procedimiento manual documentado.

**Acceptance Scenarios**:

1. **Given** el repositorio, **When** se revisan sus archivos de plantilla, **Then** existe una plantilla de variables de entorno y una plantilla de archivo de configuración, ambas sin ningún valor secreto, que listan todas las variables y campos que el sistema entiende.
2. **Given** un archivo real de variables de entorno o de configuración local creado por la persona usuaria a partir de las plantillas, **When** consulta el control de versiones, **Then** esos archivos y el directorio local de datos por defecto aparecen como ignorados y no pueden añadirse por descuido; **And** las plantillas, en cambio, sí se versionan.
3. **Given** el conjunto de archivos versionados, **When** se ejecuta la comprobación automática de secretos, **Then** no encuentra ninguna clave ni ningún archivo de secretos versionado; **And** la comprobación falla (en una prueba con un archivo de prueba que contiene un patrón de clave) cuando encuentra uno.
4. **Given** el historial de cambios del repositorio, **When** se sigue el procedimiento manual documentado, **Then** se puede confirmar que ninguna clave aparece en commits anteriores, y el procedimiento indica qué hacer (revocar y reemplazar la clave) si apareciera alguna.

---

### User Story 4 - Entregar al resto del sistema una configuración tipada y con campos reservados (Priority: P2)

Como equipo de desarrollo, quiero que el núcleo reciba la configuración ya cargada, tipada e inmutable, con un campo reservado para cada valor que otras historias ya declaran necesitar, para que esas historias consuman su valor sin leer archivos ni variables de entorno y sin que esta historia implemente su lógica.

**Why this priority**: Es la regla arquitectónica que hace útil a las historias 1 a 3 (el núcleo no depende del entorno, RNF-21) y evita que HU-01-03, HU-03-01 y HU-01-06 inventen cada una su propia lectura de configuración. No añade comportamiento visible a la persona usuaria, por eso es P2.

**Independent Test**: Puede probarse comprobando que el código del núcleo no contiene lecturas de archivos ni de variables de entorno (prueba de arquitectura) y que la configuración expone un campo tipado por cada valor reservado, con su valor por defecto cuando corresponde, usando solo valores de prueba.

**Acceptance Scenarios**:

1. **Given** el código del núcleo, **When** se revisa automáticamente, **Then** no lee archivos de configuración ni variables de entorno; solo recibe valores de configuración ya cargados.
2. **Given** la configuración cargada, **When** un consumidor consulta el modelo, los límites por sesión (turnos, tiempo y consumo en tokens) o las rutas (raíz del área de trabajo autorizada y base de datos de sesiones), **Then** obtiene cada valor con su tipo propio y no como texto sin interpretar.
3. **Given** un valor reservado que el archivo no indica, **When** se consulta, **Then** se obtiene su valor por defecto documentado o, si el campo no tiene valor por defecto seguro (modelo, raíz del área autorizada), el estado definido de «no configurado», nunca un valor inventado.

---

### Edge Cases

- **Archivo vacío**: es un archivo válido en sí mismo; los campos con valor por defecto lo toman y los que no lo tienen (el modelo) se informan como faltantes con un mensaje claro.
- **Archivo con la sintaxis rota**: el arranque se detiene con un mensaje claro en español que indica el archivo y, cuando sea posible, la línea; el mensaje no reproduce el contenido de la línea, porque podría contener una clave pegada por error.
- **Archivo que no existe** (en la ubicación por defecto o en la indicada por parámetro o por `HARNESS_CONFIG`): se detiene el arranque con un error claro que nombra la ubicación buscada; no se arranca con valores por defecto. Si el parámetro explícito y `HARNESS_CONFIG` indican ubicaciones distintas, se usa la del parámetro.
- **Variable de entorno con un valor no secreto** (por ejemplo, una variable con el nombre del modelo): se ignora; los valores no secretos solo se leen del archivo.
- **Variable de clave definida pero vacía o solo con espacios**: se trata como ausente.
- **Secreto pegado por error en un campo que no es de clave** (por ejemplo, en el modelo): ninguna comprobación puede detectarlo con certeza (V-13: la detección de secretos no es total). La comprobación automática de archivos versionados y la guía de la plantilla reducen el riesgo, pero no lo eliminan.
- **Nombres de variables y mayúsculas**: los nombres se usan tal como figuran en la plantilla; en Windows el sistema operativo no distingue mayúsculas en los nombres de variables y en Linux sí, y el comportamiento observable para la persona usuaria debe ser el mismo con los nombres de la plantilla.
- **Archivo codificado con marca de orden de bytes o con saltos de línea de Windows**: se lee igual que un archivo de Linux.
- **Rutas relativas en el archivo**: se interpretan respecto al directorio del archivo de configuración, no respecto al directorio desde el que se arranca, para que el resultado sea el mismo en cualquier sistema y desde cualquier directorio. Que una ruta apunte a un lugar existente o permitido no lo comprueba esta historia.
- **Cambios del archivo con el sistema en marcha**: no se recargan; la configuración se lee una vez al arrancar. Para aplicar un cambio hay que reiniciar.
- **Clave ya subida al repositorio en el pasado**: el procedimiento manual indica revocarla y reemplazarla; reescribir el historial queda fuera de esta historia.

## Requirements *(mandatory)*

### Functional Requirements

**Carga y esquema (RF-7.6, RNF-21; Sp1-09)**

- **FR-001**: El sistema MUST cargar la configuración una sola vez al arrancar, a partir de un archivo de texto en formato TOML y de variables de entorno, y MUST entregarla como un único conjunto de valores tipados e inmutables.
- **FR-002**: El esquema de configuración MUST definir, como mínimo, estos campos: el modelo a usar; los límites por sesión (máximo de turnos, tiempo máximo y consumo máximo en tokens); la raíz del área de trabajo autorizada; y la ruta de la base de datos de sesiones. Cada campo reservado MUST tener un tipo propio. Esta historia MUST NOT implementar la lógica de las historias que los consumen (herramientas de archivos, sesiones, límites del bucle).
- **FR-003**: Cada campo MUST tener un valor por defecto documentado, salvo el modelo y la raíz del área de trabajo autorizada, que no tienen un valor por defecto seguro: si el modelo no se indica, el sistema MUST informarlo como faltante y no arrancar; si la raíz del área autorizada no se indica, MUST quedar como «no configurada», que los consumidores MUST tratar como ausencia de autorización (falla cerrada).
- **FR-004**: Los valores que no son secretos (modelo, límites y rutas) MUST definirse solo en el archivo de configuración. Las variables de entorno MUST usarse únicamente para las claves y para indicar la ubicación del archivo (`HARNESS_CONFIG`, FR-005); ninguna variable de entorno sobrescribe un valor no secreto.
- **FR-005**: El archivo de configuración por defecto MUST ser `config.toml` en el directorio de trabajo actual. Otra ubicación MUST poder indicarse con un parámetro explícito de la función de carga o con la variable de entorno `HARNESS_CONFIG`; el parámetro explícito MUST prevalecer sobre la variable. Indicar la ubicación con un argumento de la terminal queda fuera de esta historia (lo aportará la CLI).
- **FR-006**: Si el archivo de configuración no existe, el sistema MUST detener el arranque con un error claro que nombre la ubicación buscada y cómo indicar otra (falla cerrada); MUST NOT arrancar con valores por defecto. Un archivo ilegible o con sintaxis rota MUST detener el arranque con un error claro igualmente; nunca se arranca con valores parciales.
- **FR-007**: El sistema MUST validar al arrancar el tipo y el rango de cada valor (por ejemplo, límites enteros positivos, rutas no vacías) y MUST detener el arranque con un error que nombre el campo y lo esperado, sin reproducir el valor recibido.
- **FR-008**: El sistema MUST rechazar los campos del archivo que el esquema no conoce, nombrando el campo; nunca los ignora en silencio.
- **FR-009**: Cambiar el modelo o un límite MUST requerir únicamente editar el archivo sin ningún cambio de código (AC-01).
- **FR-010**: Las rutas relativas del archivo MUST interpretarse respecto al directorio del archivo de configuración, con el mismo resultado en Windows y en Linux.

**Separación del núcleo (RNF-21)**

- **FR-011**: El núcleo MUST recibir la configuración ya cargada y MUST NOT leer archivos ni variables de entorno; la lectura vive fuera del núcleo.
- **FR-012**: La configuración entregada MUST ser inmutable: ningún consumidor puede modificarla durante la ejecución, y la carga no tiene efectos secundarios fuera de leer el archivo y el entorno.

**Claves y secretos (RF-7.6, RNF-16; Sp1-10)**

- **FR-013**: Las claves de los proveedores MUST leerse únicamente de variables de entorno; nunca de un archivo de configuración ni de otra fuente.
- **FR-014**: Si el archivo contiene un campo de clave o de secreto, el sistema MUST rechazarlo al cargar con un error que nombre el campo y explique que las claves van en variables de entorno, sin mostrar el valor; como el nombre podría ser un error tipográfico de otro campo, el mensaje indica también que, si el campo es legítimo, debe revisarse su nombre. La comprobación se aplica solo a los campos que el esquema no conoce: un campo declarado en el esquema (por ejemplo, `limits.max_tokens`) nunca se rechaza por su nombre.
- **FR-015**: Cuando el modelo configurado requiera una clave y su variable de entorno falte o esté vacía, el sistema MUST detener el arranque con un error que nombre la variable y MUST NOT mostrar su valor ni parte de él. Cuando el modelo no requiera clave, no se exige ninguna.
- **FR-016**: Los objetos de configuración MUST NOT exponer ningún secreto en su texto, en su representación para depuración ni en los mensajes de error; el valor de una clave solo se entrega a quien lo necesita para autenticarse, en un contenedor que oculta su contenido al mostrarse.
- **FR-017**: Los mensajes de error de configuración MUST ser frases completas en español que indiquen qué falla y cómo corregirlo, sin trazas de pila y sin reproducir los valores recibidos.

**Repositorio sin secretos (Reglas 1 y 2, AC-02; Sp1-11)**

- **FR-018**: El repositorio MUST incluir una plantilla de variables de entorno (`.env.example`) y una plantilla de archivo de configuración (`config.example.toml`), ambas sin secretos, que listen todas las variables y campos que el sistema entiende, con sus valores por defecto y una breve explicación de cada uno.
- **FR-019**: El control de versiones MUST ignorar el archivo real de configuración (`config.toml`), el archivo real de variables de entorno (`.env`) y el directorio local de datos que use la ruta por defecto de la base de datos de sesiones (donde se guardan conversaciones que pueden ser sensibles) y MUST NOT ignorar las plantillas (`config.example.toml` y `.env.example`), que son lo único que se versiona.
- **FR-020**: MUST existir una comprobación automática sobre los archivos versionados que falle si encuentra un archivo de secretos versionado o un patrón de clave conocido, y que se ejecute junto con las demás pruebas.
- **FR-021**: MUST existir un procedimiento manual documentado para comprobar que ninguna clave aparece en el historial de cambios y para actuar si apareciera una (revocar y reemplazar).

**Plataformas y pruebas**

- **FR-022**: La carga y la validación MUST comportarse igual en Windows y en Linux para el mismo archivo (codificación UTF-8, saltos de línea y rutas válidas para el sistema donde se ejecuta). Una ruta con la forma de otro sistema (por ejemplo, `C:\x` en Linux) no se interpreta como absoluta ni se convierte: se trata como lo haría el sistema donde se ejecuta. Esta segunda frase no tiene prueba propia: la cubre la matriz de CI de Windows y Linux (T027).
- **FR-023**: Las pruebas de la historia MUST poder ejecutarse sin red, sin proveedor real y sin leer ni modificar el entorno real ni archivos reales de la persona usuaria (directorios temporales y variables simuladas).

### Key Entities *(include if feature involves data)*

- **Configuración**: Conjunto inmutable de valores tipados que el sistema entrega al arrancar al resto del sistema: modelo, límites por sesión, rutas y, aparte, las claves. Es lo único que el núcleo conoce de su entorno.
- **Archivo de configuración**: Archivo de texto editable por la persona usuaria con los valores no secretos (modelo, límites, rutas). Nunca contiene claves.
- **Clave (secreto)**: Valor que autentica al sistema ante un proveedor. Solo existe en una variable de entorno; se entrega envuelta en un contenedor que oculta su contenido al mostrarse.
- **Variable de entorno de clave**: Variable del entorno de la persona usuaria cuyo nombre figura en la plantilla y que contiene la clave del proveedor del modelo configurado.
- **Plantilla de ejemplo**: Par de archivos versionados (variables de entorno y configuración) con todos los campos y valores ficticios, sin secretos.
- **Error de configuración**: Resultado de una carga fallida: frase en español que nombra el campo o la variable afectados y cómo corregirlos, sin valores recibidos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de los casos de prueba, cambiar únicamente el modelo en el archivo cambia el modelo que entrega la configuración, con cero líneas de código modificadas (AC-01).
- **SC-002**: En el 100 % de los casos de clave ausente o vacía, el mensaje nombra la variable que falta, y en el 100 % de las salidas observadas (mensajes de error, texto y representación de los objetos de configuración) el valor de una clave de prueba con valor centinela aparece cero veces, ni completo ni en parte.
- **SC-003**: La comprobación automática sobre los archivos versionados encuentra cero claves y cero archivos de secretos (AC-02) y falla en el 100 % de los casos de prueba que introducen uno; el procedimiento manual sobre el historial queda documentado y su resultado registrado.
- **SC-004**: El 100 % de los archivos de prueba con un valor inválido, un campo desconocido, un campo de clave o sintaxis rota, así como la ausencia del archivo, detienen el arranque con un mensaje que nombra el campo (o el archivo), sin trazas de pila y sin reproducir el valor recibido.
- **SC-005**: El 100 % de los valores reservados (modelo, tres límites y dos rutas) tiene su campo tipado, su valor por defecto o su estado «no configurado» definido y su entrada en las dos plantillas.
- **SC-006**: Las pruebas automatizadas de la historia pasan al 100 % tanto en Windows como en Linux, sin red, sin proveedor real y sin tocar el entorno real.
- **SC-007**: La carga y validación de una configuración completa añade en promedio menos de 100 ms al arranque, de modo que no sea perceptible.

## Assumptions

- **Contratos base**: La historia usa tal cual los contratos de HU-00-01; no modifica los puertos de `core/interfaces/`. El núcleo no necesita ningún puerto nuevo, porque recibe valores y no los pide.
- **Dónde vive la lectura**: Según el árbol acordado (skill `estructura-carpetas-harness`), la lectura de archivo y entorno va en `config.py`, fuera de `core/`. El cableado con el resto del sistema (`bootstrap.py`) no existe todavía y lo creará otra historia; esta historia solo entrega la configuración.
- **Formato**: El árbol acordado ya fija una plantilla `config.example.toml`, por lo que el archivo es TOML; se lee con la biblioteca estándar y sin dependencias nuevas (Python 3.12, constitución). Las plantillas se llaman `config.example.toml` y `.env.example`, como en el árbol acordado.
- **Diferencia con la documentación**: El árbol acordado describe `config.example.toml` como «modelo, límites, rutas, reglas de permisos». Aquí el archivo no incluye reglas de permisos: pertenecen a otras historias del área C (HU-05-xx) y se añadirán al esquema cuando llegue su turno. Por la regla de falla cerrada, un campo de permisos hoy se rechaza como desconocido.
- **Valores reservados**: Solo se reserva un campo por cada valor que otras historias ya declaran necesitar: la raíz del área autorizada (HU-01-03), la ruta de la base de datos de sesiones (HU-03-01) y los límites de turnos, tiempo y consumo en tokens (HU-01-06). La selección de proveedor por configuración (HU-07-03) y el resto de valores quedan fuera; el modelo es un identificador de texto.
- **Valores por defecto**: Los valores numéricos concretos de los límites y la ruta por defecto de la base de datos son decisiones de la planificación técnica y se documentan en la plantilla. Se asume que el modelo no tiene valor por defecto (decisión explícita de seguridad y de claridad).
- **Qué modelos requieren clave**: Se asume que cada modelo conocido declara si requiere clave y cuál es su variable de entorno (por ejemplo, el proveedor simulado no requiere ninguna). El adaptador real (HU-07-02) aportará los nombres concretos; esta historia define el mecanismo y el error.
- **El archivo `.env`**: El sistema **no lee** el archivo `.env`: las claves se leen únicamente del entorno del proceso. `.env` (y su plantilla `.env.example`) es solo una ayuda de la persona usuaria para guardar sus claves localmente y cargarlas en su entorno antes de arrancar (la plantilla explica cómo, en PowerShell y en bash). Leer `.env` ampliaría el origen de las claves y exigiría código o una dependencia más.
- **Detección de secretos**: La comprobación automática busca patrones de claves conocidos y archivos de secretos; no es una garantía total (V-13). La redacción de secretos en trazas y auditoría pertenece a HU-10-02 y el detector de patrones a HU-04-05; esta historia solo garantiza que sus propios objetos y mensajes no exponen secretos.
- **Fuera de alcance**: Lógica de las historias consumidoras; selección de proveedor por configuración; reglas de permisos en el archivo; recarga de la configuración en caliente; escritura o generación del archivo por el sistema; reescritura del historial de cambios; interfaz de terminal (HU-06-01): el argumento de la terminal para indicar la ubicación del archivo lo aportará la CLI.
- **Mensajes de error**: En español, el idioma de trabajo del proyecto, conservando tal cual los nombres de campos y variables.
- **Rendimiento**: El umbral de 100 ms de SC-007 es un valor por defecto razonable para el arranque y puede ajustarse si las mediciones lo justifican.
- **Requisitos RF-7.6, RNF-16 y RNF-21**: El texto íntegro de estos requisitos no figura en la documentación activa; solo su trazabilidad (RF-7.6 se comparte con HU-07-02, RNF-16 con HU-10-02 y RNF-21 con HU-07-03). Se interpretan respectivamente como claves de proveedor solo desde el entorno (FR-013 a FR-015), secretos que no aparecen en archivos, mensajes ni registros (FR-014 a FR-021) y comportamiento cambiable por configuración sin tocar el código ni el núcleo (FR-009 y FR-011). Conviene confirmar esta lectura con el Product Owner antes de cerrar la historia.
- **Disciplina de proceso**: La historia se limita al Sprint 1 (Principio VI), se verifica con pruebas automatizadas sin red usando directorios temporales y variables simuladas (Principio IV), no altera sus criterios de aceptación AC-01 y AC-02 (Principio V) y no toca `docs/archivo/` (Principio X).
