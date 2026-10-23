# Feature Specification: HU-00-03 — Proveedor simulado para pruebas

**Feature Branch**: `012-fake-provider`

**Created**: 2026-10-23

**Status**: Draft

**Proyecto**: HARNESS v2.5 | **Sprint**: 1 | **Responsable**: B — Estado | **Tareas de referencia**: Sp1-07, Sp1-08 | **Requisitos**: RNF-1, RNF-6 | **Depende de**: HU-00-01 (contratos; sigue «Pendiente de aprobación técnica»)

**Input**: User description: "HU-00-03 — Proveedor simulado para pruebas (docs/04a-historias-fundacion.md#hu-00-03). Decisiones del responsable: (1) los errores simulados usan una jerarquía canónica mínima ProviderError (QuotaExceeded, ProviderTimeout, ProviderUnavailable) definida en core/interfaces/provider.py y exportada desde harness_agent.core, que HU-07-02 reutilizará; (2) FakeProvider vive en tests/doubles/fake_provider.py; (3) convive con ScriptedProvider sin migrar las pruebas del bucle de A."

## Clarifications

### Session 2026-10-23

Decisiones ya tomadas por el responsable antes de redactar; no quedó ningún marcador de aclaración pendiente.

- Q: ¿Cuál es el «mismo tipo que un proveedor real» (AC-02)? → A: Una jerarquía canónica mínima de errores de proveedor, definida en el núcleo como parte del puerto `Provider` y exportada desde `harness_agent.core`: una base `ProviderError` y tres tipos concretos, `QuotaExceeded`, `ProviderTimeout` y `ProviderUnavailable`. El proveedor simulado los lanza; el adaptador real de HU-07-02 traducirá los errores de su biblioteca a estos mismos tipos. El núcleo no importa ninguna biblioteca de terceros.
- Q: ¿Dónde vive el proveedor simulado? → A: En `tests/doubles/fake_provider.py`, exportado desde `tests/doubles/__init__.py`, como el resto de dobles. No forma parte del paquete de producción.
- Q: ¿Qué pasa con `ScriptedProvider` y `DummyProvider`? → A: Conviven. No se modifican ni se migran las pruebas del bucle de A (HU-01-01); el proveedor simulado es el doble oficial de V-14 para las historias nuevas.
- Q: ¿Cómo se escribe el guion? → A: Como una lista ordenada de pasos en código de prueba. Cada paso es una respuesta (texto y/o llamadas a herramientas) o un fallo (uno de los tres tipos de error). No hay formato de archivo en esta historia.
- Q: ¿Cómo se fuerza un fallo? → A: Como un paso más del guion, en la posición que se quiera (primera, tercera llamada, etc.). No hay un «modo global» aparte; el modo de fallo configurable de Sp1-08 es esa capacidad.
- Q: ¿Qué pasa cuando el guion se acaba? → A: Se lanza un error explícito y se deja constancia de que se agotó, igual que `ScriptedProvider`; nunca se inventa una respuesta ni se repite la última.
- Q: ¿Los errores simulados esperan de verdad? → A: No. El tiempo agotado se lanza de inmediato, sin dormir ni usar el reloj.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04a-historias-fundacion.md` (HU-00-03). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

**Flujo general**

1. El desarrollador escribe un guion con respuestas de texto y llamadas a herramientas.
2. El bucle usa el proveedor simulado en lugar de uno real.
3. El resultado es el mismo en cada ejecución.
4. Opcionalmente el guion fuerza un error de cuota, tiempo agotado o indisponibilidad.

**Reglas de negocio**

1. El proveedor simulado implementa la misma interfaz Provider que los reales.
2. Los errores simulados tienen el mismo tipo que los reales.

**Criterios de aceptación**

- **AC-01 — Ejecución determinista sin red.** Dado un guion de respuestas con texto y llamadas a herramientas, cuando el bucle corre con el proveedor simulado, entonces el resultado es idéntico en cada ejecución y sin red.
- **AC-02 — Fallos simulados equivalentes a los reales.** Dado el proveedor simulado configurado para fallar con error de cuota, cuando el bucle lo llama, entonces recibe el mismo tipo de error que daría un proveedor real.

### Lo que ya existe y lo que cambia

- **Existe y no se toca**: el bucle de A, el bus de eventos, el registro de herramientas, la política de permisos, la CLI, `ScriptedProvider`, `DummyProvider` y las pruebas actuales.
- **Cambia, de forma aditiva**: el puerto `Provider` (`core/interfaces/provider.py`) gana la jerarquía de errores y `harness_agent.core` la exporta. No cambia la firma de `complete`. Es una ampliación de un contrato de HU-00-01 (área de A) y requiere su visto bueno (véase Supuestos).
- **Se añade**: `tests/doubles/fake_provider.py` y sus pruebas.

### User Story 1 - Reproducir un guion de respuestas sin red (Priority: P1) [AC-01]

Como equipo de desarrollo, quiero escribir un guion de respuestas de texto y llamadas a herramientas y que el bucle lo use en lugar de un proveedor real, para probar el bucle sin gastar cuota de API ni depender de la red.

**Why this priority**: Es el criterio AC-01, la regla de negocio 1 y la razón de V-14: casi todas las pruebas del proyecto (Sprint 1 a 3) se apoyan en esto. Sin él las pruebas dependen de la red y de la cuota (riesgo R-14).

**Independent Test**: Se construye un guion de tres pasos (una llamada a herramienta, otra llamada a herramienta y una respuesta final de texto), se corre el bucle real dos veces con el bus real y herramientas de prueba, y se comprueba que el historial, los eventos publicados y el resultado del turno son idénticos en ambas ejecuciones y que no se abrió ningún socket de red.

**Acceptance Scenarios**:

1. **Given** un guion con una respuesta de texto y una con llamadas a herramientas, **When** el bucle corre con el proveedor simulado, **Then** recibe las respuestas en el orden del guion, una por llamada.
2. **Given** el mismo guion, **When** se ejecuta dos veces en procesos de prueba distintos, **Then** el resultado (historial, eventos y estado final) es idéntico.
3. **Given** una prueba que bloquea cualquier conexión de red, **When** corre con el proveedor simulado, **Then** pasa: el proveedor no intenta abrir sockets.
4. **Given** el proveedor simulado, **When** se comprueba contra la interfaz `Provider`, **Then** es una subclase con la misma firma de `complete`, y la suite de contrato de proveedores existente lo acepta como intercambiable con el doble actual.
5. **Given** cada llamada al proveedor, **When** se consulta lo registrado, **Then** quedan guardados los mensajes y las herramientas recibidos, como copias que no cambian si el bucle sigue trabajando.
6. **Given** un guion cuyas llamadas a herramientas repiten un identificador o lo dejan vacío, **When** se construye, **Then** se rechaza al crearlo, no a mitad de una prueba.

---

### User Story 2 - Simular fallos del proveedor con los tipos canónicos (Priority: P1) [AC-02]

Como equipo de desarrollo, quiero que el guion pueda forzar un error de cuota, de tiempo agotado o de indisponibilidad y que el bucle reciba el mismo tipo de error que daría un proveedor real, para probar cómo reacciona el sistema a los fallos sin provocarlos de verdad.

**Why this priority**: Es el criterio AC-02, la regla de negocio 2 y la base de HU-07-05 (conmutación por fallo) y de las pruebas de fallo del bucle.

**Independent Test**: Se corre el bucle real con un guion cuyo primer paso es un fallo de cuota y se comprueba que el turno termina como fallo de proveedor, que el evento de error del proveedor lleva el tipo `QuotaExceeded` y que ese tipo es el mismo que `harness_agent.core` exporta como canónico para los adaptadores reales.

**Acceptance Scenarios**:

1. **Given** un guion con un fallo de cuota, **When** el bucle llama al proveedor simulado, **Then** recibe una excepción de tipo `QuotaExceeded`, subclase de `ProviderError`.
2. **Given** un guion con un fallo de tiempo agotado o de indisponibilidad, **When** el bucle lo llama, **Then** recibe `ProviderTimeout` o `ProviderUnavailable`, también subclases de `ProviderError`, y la llamada no espera tiempo real.
3. **Given** un fallo simulado en la tercera posición del guion, **When** el bucle llama tres veces, **Then** las dos primeras devuelven su respuesta y la tercera falla.
4. **Given** un fallo simulado con un mensaje, **When** el bucle lo publica en el evento de error del proveedor, **Then** el nombre del tipo es el canónico y el mensaje no contiene claves ni datos de la entrada.
5. **Given** los tres tipos concretos, **When** se importan desde `harness_agent.core`, **Then** están disponibles sin importar submódulos internos y el núcleo sigue sin dependencias de terceros.
6. **Given** un guion que mezcla respuestas y fallos, **When** se reproduce otra vez con un proveedor nuevo, **Then** la secuencia de éxitos y fallos es la misma.

---

### User Story 3 - Guion agotado y mal formado fallan de forma explícita (Priority: P2)

Como equipo de desarrollo, quiero que un guion que se queda corto o que está mal escrito falle con un error claro, para no confundir un fallo de la prueba con un fallo del bucle.

**Why this priority**: Evita falsos positivos: sin esto, una prueba podría «pasar» porque el proveedor devolvió algo inventado. Es P2 porque no es un criterio de la historia, pero protege a todas las que la usen.

**Independent Test**: Se llama al proveedor una vez más de las respuestas escritas y se comprueba que lanza el error de guion agotado y que lo deja marcado; se construyen guiones inválidos y se comprueba que se rechazan al crearlos.

**Acceptance Scenarios**:

1. **Given** un guion de N pasos, **When** se llama N+1 veces, **Then** la llamada N+1 lanza un error de guion agotado y el proveedor queda marcado como agotado.
2. **Given** un guion vacío, **When** se construye, **Then** se rechaza con un mensaje claro al crear el proveedor.
3. **Given** un paso que no es ni una respuesta ni un fallo canónico, **When** se construye, **Then** se rechaza al crear el proveedor.
4. **Given** el proveedor simulado, **When** se usa con `asyncio`, **Then** cada llamada completa sin bloquear el bucle de eventos.

---

### User Story 4 - Convive con los dobles actuales y deja huella clara (Priority: P2)

Como equipo de desarrollo, quiero que el proveedor simulado conviva con `ScriptedProvider` y `DummyProvider` y que esté documentado, para que cada integrante sepa cuál usar y no se rompa nada existente.

**Why this priority**: La guía de contratos ya remite a «FakeProvider» (sección B) y el plan lo usa desde Sprint 1; sin documentación cada integrante inventaría el suyo.

**Independent Test**: Se ejecuta la suite completa antes y después y se comprueba que no cambia ninguna prueba existente; una prueba de arquitectura comprueba que `core/` no importa `tests/`.

**Acceptance Scenarios**:

1. **Given** la suite actual, **When** se añade el proveedor simulado, **Then** todas las pruebas existentes siguen pasando sin modificarse.
2. **Given** `tests/doubles/__init__.py`, **When** se importa `FakeProvider`, **Then** está exportado junto a los demás dobles.
3. **Given** la guía `docs/guia-contratos-desarrollo.md`, **When** se consulta la sección de dobles, **Then** explica cuándo usar `DummyProvider`, `ScriptedProvider` y `FakeProvider` y cómo escribir un guion con fallos.
4. **Given** el código de `core/`, **When** se revisa, **Then** no importa nada de `tests/` ni de bibliotecas de terceros.

---

### Edge Cases

- **Mismo guion en dos instancias**: cada instancia lleva su propia cuenta; no hay estado compartido entre instancias ni entre pruebas.
- **Guion modificado después de crear el proveedor**: no afecta al proveedor; este trabaja con su propia copia.
- **Respuesta con texto y llamadas a herramientas a la vez**: se devuelve tal cual; el proveedor no la interpreta.
- **Uso (`usage`) ausente**: se devuelve `None` si el paso no lo trae; no se inventa. Si lo trae, se devuelve sin cambios.
- **Cancelación mientras espera**: el proveedor simulado no espera ni bloquea, así que no hay nada que cancelar; si el bucle cancela entre llamadas, la cuenta de llamadas no avanza más.
- **Llamadas concurrentes**: se atienden en el orden en que llegan; cada una consume un paso distinto.
- **Mensajes y herramientas recibidos con valores mutables**: lo registrado es una copia; modificarlo después no cambia lo que se guardó.
- **Error simulado con un mensaje largo o con contenido sensible**: el proveedor no recorta ni oculta nada; el bucle ya acota el mensaje al publicarlo, y la regla de no incluir claves en los guiones es responsabilidad de quien los escribe.

## Requirements *(mandatory)*

### Functional Requirements

**Jerarquía de errores canónica (AC-02, regla 2)**

- **FR-001**: El puerto `Provider` MUST definir una base `ProviderError` (subclase de `Exception`) y tres tipos concretos, `QuotaExceeded`, `ProviderTimeout` y `ProviderUnavailable`, todos subclases de `ProviderError`.
- **FR-002**: Los cuatro tipos MUST exportarse desde `harness_agent.core` y figurar en su `__all__`.
- **FR-003**: Cada tipo MUST aceptar un mensaje legible y conservarlo; no MUST incluir claves, contenido del usuario ni objetos internos por sí mismo.
- **FR-004**: La definición MUST ser aditiva: la firma de `Provider.complete` y las entidades existentes no cambian, y `core/` sigue sin importar bibliotecas de terceros.
- **FR-005**: La jerarquía MUST ser lo bastante estable para que HU-07-02 y HU-07-05 la reutilicen: ningún tipo codifica detalles de una biblioteca concreta.

**Proveedor simulado (AC-01, regla 1)**

- **FR-006**: `FakeProvider` MUST ser una subclase de `Provider` con la misma firma asíncrona de `complete`, definida en `tests/doubles/fake_provider.py` y exportada desde `tests/doubles/__init__.py`.
- **FR-007**: El guion MUST ser una secuencia ordenada de pasos; cada paso es una `ProviderResponse` o un fallo canónico (`ProviderError`).
- **FR-008**: Cada llamada a `complete` MUST consumir exactamente un paso, en orden, y devolverlo (respuesta) o lanzarlo (fallo).
- **FR-009**: El resultado MUST ser determinista: mismo guion y mismas llamadas dan los mismos resultados en cada ejecución; el proveedor no usa aleatoriedad, reloj, variables de entorno ni red.
- **FR-010**: El proveedor MUST NOT abrir conexiones de red ni leer credenciales.
- **FR-011**: Al construirse, MUST validar el guion: pasos de tipo válido, identificadores de llamadas a herramientas no vacíos y únicos en todo el guion; un guion inválido se rechaza con un error claro en ese momento.
- **FR-012**: El proveedor MUST trabajar con una copia propia del guion; cambios posteriores del original no le afectan.
- **FR-013**: Cuando el guion se agota, MUST lanzar un error explícito de guion agotado y marcar el proveedor como agotado; nunca inventa ni repite una respuesta.
- **FR-014**: MUST registrar, por cada llamada, copias de los mensajes y de las herramientas recibidos y el número de llamadas, para que las pruebas puedan comprobar lo que el bucle envió.
- **FR-015**: Los fallos simulados MUST lanzarse de inmediato; el proveedor no duerme, no espera ni usa tiempos reales.
- **FR-016**: Un fallo simulado MUST poder colocarse en cualquier posición del guion y mezclarse con respuestas.

**Convivencia y calidad**

- **FR-017**: No MUST modificarse ni migrarse `ScriptedProvider`, `DummyProvider` ni ninguna prueba existente; solo se añaden archivos (más la ampliación aditiva del puerto y de `tests/doubles/__init__.py`).
- **FR-018**: MUST existir pruebas unitarias y de integración (con el bucle real de A, el bus real y herramientas de prueba) de los escenarios de las historias 1 a 3, sin red.
- **FR-019**: MUST existir una prueba de contrato que compruebe que el proveedor simulado cumple la interfaz `Provider` y es intercambiable con los otros dobles.
- **FR-020**: Una prueba de arquitectura MUST comprobar que `core/` no importa `tests/` ni terceros tras la ampliación del puerto.
- **FR-021**: `docs/guia-contratos-desarrollo.md` MUST explicar cuándo usar cada doble de proveedor y cómo escribir un guion con fallos.
- **FR-022**: `ruff format --check`, `ruff check`, `mypy src tests` y `pytest` MUST pasar con las versiones fijadas, y la cobertura del módulo nuevo MUST ser del 100 %.
- **FR-023**: Al cerrar, `docs/PROGRESO.md` MUST reflejar la historia (estado «En revisión», archivos y evidencia) según el Principio VIII.

### Key Entities

- **ProviderError**: base de los errores de proveedor del núcleo. Lleva un mensaje legible.
- **QuotaExceeded / ProviderTimeout / ProviderUnavailable**: los tres fallos canónicos de esta historia (cuota agotada, tiempo agotado, servicio no disponible). Los adaptadores reales los lanzarán tras traducir los errores de su biblioteca.
- **Guion**: secuencia ordenada de pasos que el proveedor simulado reproduce, uno por llamada.
- **Paso**: una respuesta del proveedor (texto, llamadas a herramientas, uso opcional) o un fallo canónico.
- **Registro de llamadas**: copias de lo recibido en cada llamada, más el número de llamadas y la marca de guion agotado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dos ejecuciones del mismo guion de tres pasos con el bucle real producen el mismo historial, los mismos eventos y el mismo estado final en el 100 % de las repeticiones (probado con al menos 20 repeticiones por prueba).
- **SC-002**: La suite del proveedor simulado corre con toda conexión de red bloqueada y con 0 intentos de conexión.
- **SC-003**: Los tres fallos canónicos llegan al bucle como el tipo exacto pedido y como subclase de `ProviderError` en el 100 % de los casos de prueba, y el evento de error del proveedor lleva ese nombre de tipo.
- **SC-004**: Un fallo simulado no consume tiempo medible: la llamada devuelve en menos de 10 ms en cada caso de prueba.
- **SC-005**: 0 pruebas existentes modificadas y 0 pruebas existentes en rojo tras la historia; la suite completa sigue en verde.
- **SC-006**: El módulo nuevo y la jerarquía de errores tienen 100 % de cobertura de líneas y ramas; `ruff`, `mypy --strict` y `pytest` terminan con código 0.
- **SC-007**: Un integrante nuevo encuentra en la guía, en menos de un minuto de lectura, cuál de los tres dobles de proveedor usar y un ejemplo de guion con un fallo.

## Assumptions

- **HU-00-01 sigue pendiente de aprobación técnica.** Ampliar `core/interfaces/provider.py` de forma aditiva no la rompe, pero la ampliación de un contrato del área de A necesita el visto bueno de A antes de pasar a «Hecha»; se registra como pendiente de confirmación humana, igual que en las historias hermanas.
- La **clasificación de errores elegibles y no elegibles** (clave inválida, petición mal formada, política de contenido, límite de tasa, error de conexión) pertenece a HU-07-05 y a HU-07-02. Esta historia solo define los tres tipos que nombra su flujo; ampliar la jerarquía después es compatible.
- El **adaptador real de HU-07-02** traducirá los errores de la biblioteca a estos tipos; esta historia no lo implementa ni lo simula.
- El **guion vive en código de prueba**. No hay formato de archivo (JSON o TOML) en esta historia; si hace falta para la demostración del Sprint, se añade en una historia posterior.
- Un **guion vacío se rechaza** al construirse, porque un proveedor sin pasos solo produciría guion agotado; el caso de «sin respuestas» se prueba con un guion de un paso.
- La **tarea guionizada de tres pasos** del objetivo del Sprint 1 (leer, escribir y releer) necesita HU-01-03 y queda fuera de esta historia; aquí se prueba el mismo patrón con herramientas de prueba.
- **Nombres en inglés** para clases, métodos y atributos (decisión del 2026-10-17); los textos de usuario y la documentación van en español.
- El **bucle de A** trata cualquier `Exception` del proveedor como fallo de proveedor y publica el nombre de su tipo; esta historia no cambia ese comportamiento ni la clasificación del bucle por tipos.
- Estimación: Sp1-07 (3 h) y Sp1-08 (1,5 h) cubren el proveedor y el modo de fallo; las pruebas, la jerarquía de errores, la guía y el registro en `PROGRESO.md` exceden los 4,5 h presupuestados, y se avisará a B de la diferencia como en las historias hermanas.
