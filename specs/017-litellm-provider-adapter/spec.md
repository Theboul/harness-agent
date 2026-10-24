# Feature Specification: HU-07-02 — Adaptador LiteLLM para el primer proveedor

**Feature Branch**: `017-litellm-provider-adapter` (carpeta de la spec; el trabajo sigue en la rama `gustavo`)

**Created**: 2026-10-24

**Status**: Draft

**Proyecto**: HARNESS v2.5 | **Sprint**: 1 | **PHU**: 2 | **Responsable de la historia**: B — Estado (la implementa C por reasignación del equipo) | **Tareas de referencia**: Sp1-43, Sp1-44, Sp1-45 | **Requisitos**: RF-7.3, RF-7.6 | **Depende de**: HU-07-01 (formato canónico y convertidores; `En revisión`), HU-00-04 (configuración; `En revisión`), SPK-01 (hallazgos en `docs/decisiones/SPK-01-traduccion-herramientas-litellm.md`)

**Input**: User description: "HU-07-02 — Adaptador LiteLLM para el primer proveedor. Un único adaptador que implementa el puerto `Provider` y es independiente del proveedor: el proveedor y el modelo salen de `config.model` con la forma `<proveedor>/<modelo>`; solo la tabla `PROVIDER_KEY_VARIABLES` de `config.py` conoce nombres de proveedores y se amplía de forma aditiva con proveedores de nivel gratuito o locales. Aplica los hallazgos de SPK-01 (`max_tokens` fijado, peticiones construidas desde el formato canónico, error de herramienta codificado en el contenido, id de llamada opaco, argumentos JSON inválidos como `[invalid_arguments]`, errores a la jerarquía `ProviderError`). Pruebas sin red ni claves; la prueba real es manual y humana."

## Clarifications

### Session 2026-10-24

Decisiones ya tomadas por el responsable antes de redactar (no son preguntas abiertas):

- Un único archivo de adaptador, `adapters/providers/litellm_provider.py`. No hay una clase ni una rama por proveedor, y el código del adaptador no contiene ningún nombre de proveedor.
- El proveedor y el modelo salen **solo** de `config.model` (`<proveedor>/<modelo>`, el formato de LiteLLM). La única tabla con nombres de proveedor es `PROVIDER_KEY_VARIABLES` de `config.py`.
- Un proveedor que no está en esa tabla sigue fallando cerrado con el error de configuración que ya existe.
- LiteLLM solo se importa dentro de `adapters/providers/`. `core/` no lo conoce.
- La prueba real contra un modelo (Sp1-45, «tarea de tres pasos») es humana, manual, se omite sin clave y no entra en la CI.
- Fuera de alcance: `bootstrap.py`, *streaming*, `tool_choice`, reintentos (HU-07-04), conmutación entre proveedores (HU-07-05) y cambio de modelo a mitad de sesión.

Respuestas del revisor (2026-10-24) a las tres preguntas abiertas de la primera redacción, más el riesgo de argumentos inválidos:

- Q: ¿La dependencia `litellm[mcp]` es opcional o de ejecución? → A: **Opcional.** Extra del proyecto en `pyproject.toml`, import perezoso solo dentro de `adapters/providers/` y error claro, con el comando de instalación, si falta. La versión exacta también va en `requirements-dev.txt` para que la CI (Ubuntu y Windows) la instale. El acuerdo de A, B y C sigue siendo una tarea humana previa a implementarla (FR-017).
- Q: ¿De dónde sale el tope de tokens de salida de una llamada? → A: De un **campo nuevo y aditivo `limits.max_output_tokens`** (entero mayor que 0, valor por defecto 4096). `limits.max_tokens` sigue siendo el presupuesto de toda la ejecución y **no** se usa como tope de una llamada. El adaptador envía siempre `max_output_tokens` a LiteLLM; el valor por defecto debe servir con proveedores de tope bajo (niveles gratuitos). Es una ampliación aditiva del esquema de HU-00-04 (FR-009 y FR-014a).
- Q: ¿Adónde va `RateLimitError`? → A: A `QuotaExceeded`, de forma **provisional**, con un mensaje que nombra la causa real (límite de tasa) para que el usuario distinga cuota de tasa. Separarlo en un tipo propio queda para HU-07-04 (FR-010 y FR-012).
- Riesgo de `ConversionError` ante argumentos JSON inválidos: el adaptador lo maneja **sin tocar** el puerto `Provider` ni `core/loop.py`, el turno no se rompe y el modelo recibe un error recuperable con la etiqueta `[invalid_arguments]`. El mecanismo se decide en el plan, con una prueba contra el bucle real (FR-008).

No quedan preguntas abiertas en la spec.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04d-historias-conexiones.md` (HU-07-02). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

**Flujo general**

1. El usuario configura la clave en el entorno.
2. El adaptador llama al modelo mediante LiteLLM.
3. El modelo responde y puede solicitar herramientas.

**Reglas de negocio**

1. LiteLLM solo se usa dentro del adaptador.

**Criterios de aceptación**

- **AC-01 — Respuesta real del modelo.** Dado una clave válida en el entorno, cuando se plantea una tarea, entonces el modelo real responde y puede solicitar herramientas.

### Lo que ya existe y lo que cambia

- **Existe y no se toca**: el puerto `Provider` y la jerarquía `ProviderError` (`core/interfaces/provider.py`), el bucle (`core/loop.py`), los convertidores de HU-07-01 (`adapters/converters/`), `FakeProvider` y los demás dobles.
- **Cambia, de forma aditiva**: `PROVIDER_KEY_VARIABLES` en `config.py` gana proveedores con nivel gratuito o locales; `Limits` en `config.py` gana el campo `max_output_tokens` (ampliación aditiva del esquema de HU-00-04); `.env.example` y `config.example.toml` los listan (comentados, sin valores); `pyproject.toml` declara `litellm[mcp]` como extra opcional y `requirements-dev.txt` lo fija a una versión exacta para la CI (requiere acuerdo de A, B y C **antes** de implementarlo).
- **Se añade**: `adapters/providers/__init__.py` (solo docstring, sin exportaciones), `adapters/providers/litellm_provider.py`, sus pruebas (unitarias, de contrato, de arquitectura) y una prueba manual real omitida sin clave.

### User Story 1 - Un modelo real responde y pide herramientas (Priority: P1) [AC-01]

Como usuario operador, quiero conectar HARNESS a un modelo real definiendo su clave en el entorno y su nombre en la configuración, para que el agente ejecute tareas reales en lugar de respuestas guionizadas.

**Why this priority**: Es el criterio AC-01 y el cierre del Sprint 1 («con un modelo real, el agente completa la misma tarea desde la CLI»). Sin este adaptador el resto del bucle solo corre con dobles.

**Independent Test**: Con el transporte sustituido (sin red ni clave real), se construye el adaptador desde una configuración `<proveedor>/<modelo>`, se llama con un historial canónico y una herramienta, y se comprueba que la respuesta canónica trae el texto, las llamadas a herramienta en orden y el consumo de tokens. Después, de forma manual y con una clave real, se corre una tarea de tres pasos (Sp1-45) y se registra el resultado.

**Acceptance Scenarios**:

1. **Given** una configuración con un modelo admitido y su clave en la variable de entorno, **When** el bucle llama al adaptador con un historial y herramientas declaradas, **Then** recibe una `ProviderResponse` con el texto del modelo, las llamadas a herramienta (id, nombre y argumentos) en el orden en que el modelo las emitió y el consumo de tokens.
2. **Given** una respuesta del modelo con texto y dos llamadas a herramienta, **When** el adaptador la traduce, **Then** conserva el texto junto a las llamadas y mantiene el orden de la lista (no usa el campo `index`).
3. **Given** el resultado de una herramienta que terminó con error, **When** el bucle lo envía de vuelta al modelo en el siguiente turno, **Then** el modelo ve el error en el contenido del mensaje, con la etiqueta `[…]` que ya usa el bucle, porque `is_error` no viaja por LiteLLM.
4. **Given** una tarea de tres pasos con un modelo real y una clave válida (prueba manual Sp1-45), **When** corre el bucle, **Then** el modelo responde, pide herramientas, recibe sus resultados y llega a una respuesta final; el resultado se anota en `docs/PROGRESO.md` como evidencia humana.
5. **Given** que `litellm` no está instalado, **When** se construye el adaptador, **Then** falla con un error claro y en español que incluye el comando de instalación del extra opcional (FR-017). Construir la configuración o importar el resto del sistema sin `litellm` instalado no falla.

---

### User Story 2 - Cambiar de proveedor solo cambiando la configuración (Priority: P1)

Como usuario operador, quiero que el mismo adaptador sirva para cualquier proveedor que LiteLLM soporte, para pasar de uno a otro cambiando el prefijo del modelo y la variable de clave, sin tocar código.

**Why this priority**: Es el requisito central pedido para esta historia y prepara HU-07-03 (segundo proveedor) sin un adaptador nuevo. Además permite probar con proveedores de nivel gratuito o locales sin gastar presupuesto (decisión D-IA abierta).

**Independent Test**: Se construye el adaptador con tres modelos de proveedores distintos y se comprueba que la petición generada difiere solo en el nombre del modelo y la clave; una prueba de arquitectura comprueba que el archivo del adaptador no contiene los nombres de los proveedores admitidos.

**Acceptance Scenarios**:

1. **Given** `model = "<proveedor>/<modelo>"` de cualquier proveedor presente en `PROVIDER_KEY_VARIABLES`, **When** se carga la configuración y se construye el adaptador, **Then** el adaptador usa ese modelo tal cual, sin ramas por proveedor.
2. **Given** un proveedor sin clave (por ejemplo, uno local), **When** se carga la configuración, **Then** no se exige ninguna variable de entorno y el adaptador no envía clave.
3. **Given** un proveedor que no está en `PROVIDER_KEY_VARIABLES`, **When** se carga la configuración, **Then** falla cerrado con el error de configuración claro ya existente, que lista los proveedores admitidos.
4. **Given** el archivo del adaptador, **When** una prueba de arquitectura lo recorre, **Then** no hay literales con nombres de proveedores y `litellm` no se importa fuera de `adapters/providers/`.

---

### User Story 3 - Los fallos del proveedor llegan al bucle como errores canónicos (Priority: P1)

Como bucle del agente, quiero recibir siempre un `ProviderError` (o uno de sus tres subtipos) cuando el modelo falla, para decidir qué hacer sin conocer ninguna biblioteca externa.

**Why this priority**: Es la regla del puerto («los adaptadores traducirán a ellos») y la base de HU-07-04 (reintentos) y HU-07-05 (conmutación). Un error sin traducir rompería la frontera hexagonal y el turno.

**Independent Test**: Para cada excepción de la tabla de FR-010, el transporte sustituido la provoca y se comprueba el tipo canónico recibido; una excepción no prevista debe llegar como `ProviderError` genérico, nunca silenciada.

**Acceptance Scenarios**:

1. **Given** cada fallo de la tabla de correspondencia, **When** el transporte lo provoca, **Then** el adaptador lanza exactamente el tipo canónico que la tabla indica, encadenando la causa original.
2. **Given** un fallo no previsto (cualquier otra excepción de la biblioteca), **When** ocurre, **Then** se lanza `ProviderError` genérico; nunca se devuelve una respuesta vacía ni se traga la excepción.
3. **Given** un fallo cuyo mensaje original contiene la clave o fragmentos de la petición, **When** se traduce, **Then** el mensaje canónico no los reproduce.
4. **Given** la cancelación del turno (`CancelledError`) o `KeyboardInterrupt`, **When** ocurre durante la llamada, **Then** se propaga sin convertirse en `ProviderError` (decisión D-01).

---

### User Story 4 - La clave y los datos nunca se filtran (Priority: P2)

Como usuario operador, quiero que mi clave de API solo exista en el entorno y dentro de un `Secret`, para no exponerla en registros, mensajes de error ni representaciones.

**Why this priority**: Es un requisito de seguridad del proyecto (sin secretos en el repo, `Secret` oculto) que la primera integración real pone a prueba por primera vez.

**Independent Test**: Con una clave centinela, se provocan errores, se hace `repr`/`str`/`format` del adaptador y de la configuración, y se capturan los eventos y registros: la centinela no aparece en ninguno.

**Acceptance Scenarios**:

1. **Given** una clave centinela en el entorno, **When** se construye el adaptador y se hace `repr`, `str` o `format` de él, **Then** no aparece la clave ni parte de ella.
2. **Given** cualquier error del proveedor, **When** se traduce al tipo canónico, **Then** ni el mensaje ni la causa visible reproducen la clave.
3. **Given** una llamada exitosa, **When** se inspeccionan los eventos y la salida del adaptador, **Then** la clave no se imprime ni se registra.

---

### User Story 5 - Peticiones acotadas y reproducibles (Priority: P2)

Como equipo, quiero que cada petición se construya desde el formato canónico con un tope de tokens explícito, para evitar costos inesperados y diferencias entre proveedores.

**Why this priority**: SPK-01 mostró que LiteLLM pide 64 000 tokens a Anthropic por defecto y que reenviar sus objetos de respuesta contamina las peticiones con campos extra.

**Independent Test**: Con el transporte capturando la petición, se comprueba que el tope de tokens de salida siempre está presente con el valor de `limits.max_output_tokens` y que no aparece ningún campo propio de LiteLLM (`provider_specific_fields`).

**Acceptance Scenarios**:

1. **Given** cualquier llamada, **When** se captura la petición, **Then** el tope de tokens de salida está presente con el valor de `limits.max_output_tokens` (4096 si no se configura) y nunca con el valor de `limits.max_tokens` (ver FR-009).
2. **Given** una conversación con llamadas y resultados de herramienta de turnos anteriores, **When** se construye la petición, **Then** sale de los mensajes canónicos mediante los convertidores de HU-07-01 y no contiene campos extra de LiteLLM.
3. **Given** una llamada de herramienta con argumentos JSON inválidos, **When** el adaptador traduce la respuesta y el bucle real la procesa, **Then** el turno no se rompe: el modelo recibe un resultado de error recuperable con la etiqueta `[invalid_arguments]`, la herramienta no se ejecuta y el modelo puede corregirse en el siguiente turno.
4. **Given** identificadores de llamada de formatos distintos (`call_…`, `toolu_…`, o cualquier otro), **When** se traducen, **Then** se conservan sin validar prefijo ni longitud y vuelven iguales en el resultado.

---

### Edge Cases

- **Argumentos que no son un objeto JSON** (lista, número, `null`): se tratan igual que el JSON inválido.
- **Argumentos vacíos** (cadena vacía): equivalen a `{}`, como ya hacen los convertidores.
- **Respuesta sin texto y sin llamadas**, o sin `choices`: es un error del proveedor (`ProviderError`), no una respuesta vacía válida.
- **Modelo que devuelve el mismo id de llamada dos veces**: se deja pasar tal cual; el bucle ya valida duplicados.
- **Respuesta sin consumo de tokens**: `usage` queda en `None`; no se inventan cifras.
- **Historial no representable** (violación del formato canónico): `ConversionError` de los convertidores se traduce a `ProviderError` con mensaje en español; la petición no sale.
- **`limits.max_output_tokens` mayor que el máximo del modelo**: lo rechaza el proveedor; llega como `ProviderError` genérico (ver FR-009). El valor por defecto (4096) es válido para proveedores de tope bajo.
- **`limits.max_output_tokens` inválido** (cero, negativo, no entero o booleano): la configuración falla cerrado con el error de validación existente, sin reproducir el valor recibido.
- **Una sola llamada de la respuesta con argumentos inválidos entre varias válidas**: solo esa llamada termina en `[invalid_arguments]`; las demás se procesan con normalidad.
- **Proveedor local sin servidor en marcha**: llega como `ProviderUnavailable`.
- **Instalación incompleta de LiteLLM en Windows con ruta larga** (SPK-01): el error de import faltante se traduce al mensaje claro de FR-017, no a un `ModuleNotFoundError` crudo.

## Requirements *(mandatory)*

### Functional Requirements

**Adaptador y puerto**

- **FR-001**: El sistema MUST ofrecer un único adaptador que implemente el puerto `Provider` (`complete` asíncrono, sin cambiar la firma) y que devuelva `ProviderResponse` con texto, llamadas a herramienta y consumo de tokens.
- **FR-002**: El adaptador MUST obtener el proveedor y el modelo exclusivamente de `config.model` (`<proveedor>/<modelo>`) y MUST NOT contener ramas, tablas ni literales con nombres de proveedores.
- **FR-003**: LiteLLM MUST importarse solo dentro de `adapters/providers/`; `core/`, `cli/` y `config.py` MUST NOT importarlo. Una prueba de arquitectura MUST vigilarlo y vigilar también que el archivo del adaptador no nombre proveedores.
- **FR-004**: `adapters/providers/__init__.py` MUST contener solo un docstring, sin exportaciones.

**Traducción**

- **FR-005**: Cada petición MUST construirse desde el formato canónico con los convertidores de HU-07-01; el adaptador MUST NOT reenviar objetos de respuesta de LiteLLM ni usar `model_dump` ni `provider_specific_fields`.
- **FR-006**: El resultado de una herramienta con `is_error` verdadero MUST llegar al modelo con el error codificado en el contenido, mediante las etiquetas `[…]` que ya usa el bucle (por ejemplo `[invalid_arguments]`, `[permission_denied]`); si el contenido no trae ya una etiqueta, el adaptador MUST anteponer una genérica. El contenido canónico original MUST NOT modificarse en el historial del bucle.
- **FR-007**: El id de una llamada MUST tratarse como opaco (sin validar prefijo ni longitud) y conservarse sin cambios hasta el resultado; el campo `index` MUST ignorarse y el orden de la lista MUST respetarse.
- **FR-008**: Los argumentos de una llamada MUST decodificarse de cadena JSON a objeto. Si son inválidos, o no son un objeto, los convertidores de HU-07-01 lanzan `ConversionError`; el adaptador MUST manejarlo **sin modificar** el puerto `Provider` (`core/interfaces/provider.py`) ni `core/loop.py`, de modo que (a) el turno no se rompe, (b) la herramienta no se ejecuta y (c) el modelo recibe un error recuperable con la etiqueta `[invalid_arguments]`. El mecanismo exacto se decide en el plan y MUST demostrarse con una prueba contra el bucle real (`AgentLoop`), no solo con una prueba unitaria del adaptador.
- **FR-009**: El adaptador MUST enviar siempre en cada petición un tope de tokens de salida tomado de `limits.max_output_tokens` (entero mayor que 0, por defecto 4096), y MUST NOT dejar el valor por defecto de LiteLLM (64 000 en Anthropic, según SPK-01). `limits.max_tokens` es el presupuesto de toda la ejecución (HU-01-06) y MUST NOT usarse como tope de una llamada. El valor por defecto MUST ser válido para proveedores de tope bajo, como los de nivel gratuito.

**Errores**

- **FR-010**: Los fallos de LiteLLM MUST traducirse a la jerarquía existente (`ProviderError`, `QuotaExceeded`, `ProviderTimeout`, `ProviderUnavailable`) con una tabla explícita en el código y en las pruebas, evaluada de la más específica a la más general. Correspondencia propuesta (nombres confirmados contra la versión 1.106.2 en `research.md` §1, que añade `PaymentRequiredError` → `QuotaExceeded`, `BadGatewayError` → `ProviderUnavailable`, `APITimeoutError` → `ProviderTimeout` e `ImportError` → `ProviderError` con mensaje de instalación):

  | Fallo de LiteLLM | Tipo canónico |
  |---|---|
  | `Timeout` | `ProviderTimeout` |
  | `RateLimitError` | `QuotaExceeded` (provisional; el mensaje nombra el límite de tasa) |
  | `BudgetExceededError` | `QuotaExceeded` |
  | `ServiceUnavailableError`, `InternalServerError`, `APIConnectionError` | `ProviderUnavailable` |
  | `AuthenticationError`, `PermissionDeniedError`, `NotFoundError`, `BadRequestError`, `ContextWindowExceededError`, `ContentPolicyViolationError` y cualquier otra excepción | `ProviderError` (genérico) |

- **FR-011**: Un fallo no previsto MUST llegar como `ProviderError` genérico con la causa encadenada; nunca se devuelve una respuesta vacía ni se traga. `CancelledError` y `KeyboardInterrupt` MUST propagarse sin traducir. Una respuesta mal formada o un historial no representable (`ConversionError`) MUST llegar como `ProviderError`. El mensaje canónico MUST estar en español y MUST NOT reproducir la clave, el contenido de la petición ni el mensaje crudo del proveedor.
- **FR-012**: No se amplía la jerarquía de errores (los subtipos de límite de tasa, clave inválida o petición mal formada son de HU-07-04). `RateLimitError` MUST mapearse a `QuotaExceeded` de forma **provisional**, con un mensaje que nombre la causa real (límite de tasa) para que el usuario distinga cuota agotada de tasa excedida; un límite de tasa transitorio no es una cuota agotada, y su separación en un tipo propio se deja para HU-07-04 junto con A y B. El mapeo MUST registrarse como hallazgo en `docs/PROGRESO.md` al cerrar la historia.

**Configuración y secretos**

- **FR-013**: `PROVIDER_KEY_VARIABLES` MUST ampliarse de forma aditiva y mínima con proveedores de nivel gratuito o locales, verificados en la documentación de LiteLLM: `gemini` → `GEMINI_API_KEY`, `groq` → `GROQ_API_KEY`, `openrouter` → `OPENROUTER_API_KEY` y `ollama` → sin clave. Las entradas existentes (`anthropic`, `fake`, `openai`) MUST NO cambiar. Un proveedor ausente de la tabla MUST seguir fallando cerrado con el error ya existente.
- **FR-014**: `.env.example` y `config.example.toml` MUST listar los proveedores nuevos (comentados, sin valores), y las pruebas de plantillas de `tests/unit/test_config_templates.py` MUST seguir pasando; las pruebas de configuración MUST cubrir cada proveedor nuevo (con clave presente, ausente y, en el caso sin clave, sin variable).
- **FR-014a**: `Limits` en `config.py` MUST ganar el campo `max_output_tokens` (entero mayor que 0, un booleano no vale, por defecto 4096), con la misma validación y mensajes que los otros tres límites y sin reproducir el valor recibido. Es una ampliación **aditiva** del esquema de HU-00-04: los casos de prueba existentes no cambian (`Limits(max_turns=30, max_seconds=600, max_tokens=200000)` sigue siendo igual a los valores por defecto porque el campo nuevo tiene su propio valor por defecto), y `config.example.toml` lo muestra **comentado** con su explicación, de modo que el conjunto de campos que declara el TOML crudo no cambia. Se añaden casos de prueba nuevos para el campo; nada se reescribe.
- **FR-015**: La clave MUST llegar solo por variable de entorno, envuelta en `Secret`, y MUST NOT registrarse, imprimirse, incluirse en mensajes de error ni en `repr`, `str` o `format` del adaptador. Además, antes de construir el error canónico o cualquier otro texto (incluido el marcador de argumentos ilegibles), el adaptador MUST reemplazar el valor de la clave por un marcador (`<secreto oculto>`) en todo texto que construya; la excepción original conserva su mensaje en `__cause__`.
- **FR-016**: El adaptador MUST recibir sus dependencias por constructor (modelo, clave como `Secret` o ausente, tope de tokens de salida por llamada y el transporte o función de llamada inyectable); no lee archivos, entorno ni configuración por su cuenta (la conexión la hará la raíz de composición, fuera de alcance).

**Dependencia nueva**

- **FR-017**: `litellm[mcp]` MUST ser una dependencia **opcional**: un extra del proyecto en `pyproject.toml` (`dependencies` sigue vacío), fijado a una versión exacta (1.106.2, la del spike) y fijado también en `requirements-dev.txt` para que la CI (Ubuntu y Windows) la instale y las pruebas corran. El import MUST ser perezoso y estar solo dentro de `adapters/providers/`; si falta, construir el adaptador MUST fallar con un error claro, en español, que incluya el comando de instalación; el resto del sistema (núcleo, CLI y configuración) MUST funcionar sin ella. Su incorporación MUST contar antes con el acuerdo de A, B y C (tarea humana previa a implementar).
- **FR-018**: La CI MUST seguir pasando en Ubuntu y Windows con Python 3.12; `LITELLM_LOCAL_MODEL_COST_MAP=True` MUST fijarse en las pruebas para evitar la descarga de precios.

**Pruebas**

- **FR-019**: Las pruebas automáticas MUST NOT usar red ni claves reales: el transporte se sustituye o se inyecta, con un guardia que hace fallar la prueba si algo intenta resolver un nombre o abrir una conexión (patrón de `tests/spikes/test_litellm_tool_translation_spike.py`).
- **FR-020**: Una prueba de contrato MUST ejecutar el mismo contrato que cumple `FakeProvider` contra el adaptador con transporte sustituido, y el bucle real MUST poder correr una tarea con herramientas sobre el adaptador sin cambiar ninguna línea del bucle.
- **FR-021**: La prueba real con un modelo (Sp1-45) MUST ser manual, humana, marcada para omitirse sin clave y fuera de la CI; su resultado se registra en `docs/PROGRESO.md`.

### Key Entities

- **Adaptador de proveedor LiteLLM**: pieza que implementa `Provider` para cualquier modelo `<proveedor>/<modelo>`. Atributos conceptuales: modelo, clave opcional (`Secret`), tope de tokens de salida por llamada y transporte inyectable.
- **Configuración del modelo**: `config.model`, `config.api_key`, `config.key_variable` y `config.limits.max_output_tokens` (nuevo, aditivo); `config.limits.max_tokens` sigue siendo el presupuesto de la ejecución y no interviene en la llamada.
- **Tabla de proveedores admitidos** (`PROVIDER_KEY_VARIABLES`): relación proveedor → variable de entorno de su clave (o ninguna). Única pieza que conoce nombres de proveedores.
- **Tabla de correspondencia de errores**: relación explícita entre fallos de LiteLLM y tipos canónicos (FR-010).
- **Respuesta canónica** (`ProviderResponse`) y **llamada/resultado de herramienta** (`ToolCall`, `ToolResult`): contratos existentes que no cambian.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de las pruebas automáticas de la historia corre sin red ni claves reales; un intento de conexión hace fallar la prueba.
- **SC-002**: Cambiar de un proveedor admitido a otro requiere modificar únicamente el valor de `model` y la variable de entorno de la clave: cero líneas de código cambiadas, verificado con al menos tres proveedores distintos.
- **SC-003**: Cada fila de la tabla de errores tiene una prueba, y el 100 % de las excepciones no previstas llega como `ProviderError`; ninguna excepción de la biblioteca externa llega al bucle.
- **SC-004**: En todas las pruebas con clave centinela, la centinela aparece cero veces en mensajes de error, `repr`, eventos y registros capturados.
- **SC-005**: El 100 % de las peticiones capturadas lleva el tope de tokens de salida con el valor de `limits.max_output_tokens` (4096 por defecto, nunca el valor de `limits.max_tokens`) y ningún campo propio de LiteLLM.
- **SC-009**: Una llamada de herramienta con argumentos inválidos, procesada por el bucle real, termina en `[invalid_arguments]` en el 100 % de los casos de prueba (JSON roto, valor que no es objeto), sin excepción que escape del turno y sin ejecutar la herramienta.
- **SC-006**: Una persona completa con un modelo real la tarea de tres pasos (Sp1-45) en una sola sesión: el modelo responde, pide al menos una herramienta, recibe su resultado y llega a una respuesta final; el resultado queda anotado en `docs/PROGRESO.md`.
- **SC-007**: Las cuatro puertas de calidad (`ruff format --check`, `ruff check`, `mypy src tests`, `pytest --cov`) y `pytest tests/architecture` pasan en Ubuntu y Windows, con cobertura del módulo nuevo del 100 % de líneas y ramas.
- **SC-008**: Cero cambios en `core/interfaces/`, `core/events.py`, `core/loop.py` y `tests/doubles/` (comprobado con el `git diff --exit-code` de CLAUDE.md).

## Assumptions

- **Estado de las dependencias**: HU-07-01 (convertidores y envelope) y HU-00-04 (configuración) están `En revisión` y se reutilizan tal cual. D-02 (envelope) sigue pendiente de aprobación técnica individual; esta historia solo consume la API pública de los convertidores.
- **Proveedores nuevos**: `gemini`, `groq` y `openrouter` usan `GEMINI_API_KEY`, `GROQ_API_KEY` y `OPENROUTER_API_KEY` (confirmado en la documentación de LiteLLM el 2026-10-24). Para `ollama` la documentación solo muestra el uso con `api_base` y sin clave; se asume el servidor local por defecto de LiteLLM y se confirma en el plan. Un punto de enlace personalizado (`api_base`) queda **fuera de alcance** porque exigiría una ampliación más del esquema de configuración (esta historia solo añade `limits.max_output_tokens`); si la prueba del plan muestra que `ollama` no funciona sin él, se deja como hallazgo para HU-07-03.
- **Elección del primer proveedor** (D-IA, presupuesto de API): no se decide aquí. El adaptador sirve para cualquiera; la elección de los dos modelos finales es del PO.
- **Errores de herramienta**: el contenido de un `ToolResult` con error ya trae, por convención del bucle y de las herramientas, una etiqueta `[…]`; la etiqueta genérica de FR-006 solo cubre el caso de que falte.
- **Cancelación**: se aplica D-01 (`asyncio`); la llamada al proveedor debe ser cancelable. La forma de llamar a LiteLLM de manera asíncrona se decide en el plan.
- **Reintentos y límites de tiempo**: el adaptador no reintenta (HU-07-04) ni impone tiempos propios más allá del valor por defecto del cliente; el límite global de ejecución es de HU-01-06.
- **Raíz de composición**: no existe todavía; en las pruebas la conexión se hace a mano (`make_rig`) y el plan anota qué deberá cablear `bootstrap.py`.
- **Documentación de la historia**: al cerrar, `docs/PROGRESO.md` pasa la fila a `En revisión` (nunca `Hecha`), con una fila por línea, CRLF puro, sin reescribir filas existentes ni tocar la tabla *Resumen*.
- **Notas obligatorias de la tarea de cierre en `docs/PROGRESO.md`**: (1) ampliación aditiva del esquema de HU-00-04 con `limits.max_output_tokens`, con aviso a B y al PO; (2) hallazgo: `RateLimitError` → `QuotaExceeded` es provisional y HU-07-04 debe decidir el tipo propio junto con A y B; (3) la dependencia opcional `litellm[mcp]` y el acuerdo de A, B y C que la precedió; (4) el resultado de Sp1-45.
- **Tareas humanas finales** (Claude no las marca como hechas): acuerdo de A, B y C para añadir la dependencia (antes de implementarla), prueba real Sp1-45, revisión cruzada por otra área y CI remota en Ubuntu y Windows.
- **Ritmo**: 8–10 tareas de 40 minutos como máximo, con pruebas e implementación agrupadas por módulo; sin `/speckit-analyze` (menos de 3 PHU).
