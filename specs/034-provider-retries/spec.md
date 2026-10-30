# Feature Specification: HU-07-04 — Reintentos con espera exponencial

**Feature Branch**: `claude/hu-07-04-retries-4df828` (el directorio de la spec es `034-provider-retries`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-30

**Status**: Draft

**Proyecto**: HARNESS v2.5 | **Sprint**: 3 (ficha; el orden por sprints ya no rige: el cierre del proyecto se adelantó al 6 de noviembre de 2026 y se trabaja por carriles de archivos) | **PHU**: 1 | **Prioridad**: Media | **Responsable**: A — Núcleo | **Requisitos**: RF-7.5, RNF-6 | **Depende de**: HU-07-02 (adaptador LiteLLM, integrado en `main`)

**Input**: User description: "HU-07-04. Ante un error temporal del proveedor (límite de tasa, tiempo agotado, servicio no disponible) el sistema reintenta con esperas crecientes antes de rendirse y registra cada intento. Motivación real: con Gemini ocurrieron 503 «high demand», timeouts y límites de 5 a 15 peticiones por minuto; sin reintentos una tarea real se cae al primer error pasajero. Sin tocar el bucle, los puertos ni el catálogo de eventos."

## Clarifications

### Session 2026-10-30

Sesión lateral sin interlocutor: las cinco ambigüedades se resolvieron con las decisiones de diseño que fijó el encargo del usuario; ninguna contradice un criterio de aceptación.

- Q: ¿Se reintenta también la cuota o el crédito agotado? → A: **No.** Solo el límite de tasa (subtipo `RateLimited` de `QuotaExceeded`, definido en el adaptador porque `core/interfaces/` está protegido); el crédito agotado se propaga en el acto (FR-002, FR-003).
- Q: ¿Dónde vive la lógica de reintentos? → A: En una **envoltura** de `Provider` en `adapters/providers/`, cableada en `compose()`; el bucle, los puertos y el catálogo de eventos no cambian (FR-013, FR-014).
- Q: ¿Cómo se registra cada intento sin añadir eventos? → A: Un observador inyectable recibe un registro sin datos; `compose()` lo publica como `provider_error` con motivo `retry` en la sesión **activa** (se mantiene al día al cambiar de sesión con `/reanudar`) (FR-009, FR-010). La CLI no lo reconoce aún (hallazgo para C).
- Q: ¿Qué pasa si la pista de espera del proveedor supera el tope? → A: No se reintenta y se propaga el error: esperar más que `max_delay` rompe la cota de la persona (FR-006).
- Q: ¿Aleatoriedad (jitter) en la espera? → A: **No**, determinista (FR-004); si hiciera falta más adelante es un cambio aditivo.

## Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04d-historias-conexiones.md` (HU-07-04). No se reescriben ni se amplían (Principio V); los escenarios de abajo los desarrollan sin sustituirlos.

- **Como:** usuario operador
- **Quiero:** que ante un error temporal el sistema reintente antes de rendirse
- **Para:** no perder la sesión por un fallo pasajero
- **Descripción:** Ante un error temporal, el sistema reintenta con esperas crecientes antes de rendirse. Es una mejora opcional: la conmutación por fallo (HU-07-05) funciona sin ella.

**Flujo general**: (1) el proveedor devuelve un error de límite de tasa; (2) el sistema espera y reintenta con esperas crecientes; (3) cada intento se registra.

**Reglas de negocio**: (1) solo se reintentan errores temporales; (2) el número de reintentos es limitado; (3) si está implementada, HU-07-05 conmuta cuando los reintentos se agotan; si no, conmuta en el primer error elegible.

- **AC-01 — Reintentos con espera exponencial.** Dado un error de límite de tasa, cuando ocurre, entonces el sistema reintenta con esperas crecientes y registra cada intento.

### Hallazgo verificado: el límite de tasa y la cuota agotada comparten tipo

Hoy el adaptador de LiteLLM traduce `RateLimitError`, `PaymentRequiredError` y `BudgetExceededError` al mismo tipo canónico `QuotaExceeded` (HU-07-02, provisional hasta esta historia). Un límite de tasa es temporal; un crédito agotado no. Reintentar el segundo gastaría tiempo sin remedio. La historia debe poder distinguirlos **sin cambiar** `core/interfaces/` (protegido): se añade en el adaptador un subtipo propio de `QuotaExceeded` para el límite de tasa. Sigue siendo un `QuotaExceeded` para quien ya lo capture (compatible con HU-07-05 y el bucle).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un fallo pasajero no tumba la tarea (Priority: P1)

La persona trabaja con un modelo real. El proveedor responde un 503 o un límite de tasa y, segundos después, vuelve a funcionar. La tarea continúa sin intervención.

**Why this priority**: Es el criterio AC-01 y la razón de la historia.

**Independent Test**: Un proveedor doble falla N veces con un error temporal y luego responde; la envoltura devuelve la respuesta, con las esperas crecientes registradas por una espera inyectada (sin esperar de verdad).

**Acceptance Scenarios**:

1. **Given** un proveedor que falla con límite de tasa dos veces y luego responde, **When** el bucle pide una respuesta, **Then** la recibe sin error y las esperas fueron crecientes (base, 2×base).
2. **Given** un proveedor que falla con tiempo agotado o servicio no disponible una vez y luego responde, **When** se pide la respuesta, **Then** se reintenta igual.
3. **Given** cada reintento, **When** ocurre, **Then** se registra el intento (número, tipo de fallo y espera) sin datos de la petición ni del proveedor.

---

### User Story 2 - Lo permanente falla enseguida y lo temporal se rinde a tiempo (Priority: P1)

**Why this priority**: Las reglas 1 y 2 de la ficha: solo lo temporal, y de forma limitada.

**Independent Test**: Errores no temporales se propagan en la primera llamada; un error temporal permanente se propaga tras agotar los intentos como el mismo tipo de error.

**Acceptance Scenarios**:

1. **Given** un error de clave inválida, petición mal formada, cuota o crédito agotado o cualquier `ProviderError` no temporal, **When** ocurre, **Then** se propaga en el acto, sin espera y sin reintento.
2. **Given** un error temporal que no se corrige, **When** se agotan los intentos configurados, **Then** se propaga el **último** error tal cual (mismo tipo), de modo que HU-07-05 pueda conmutar después.
3. **Given** una pista de espera del proveedor mayor que el tope de espera, **When** ocurre, **Then** no se reintenta y se propaga el error (esperar más que el tope rompe la cota de la persona).

---

### User Story 3 - Se configura y se puede apagar (Priority: P2)

**Why this priority**: Los planes gratuitos (5–15 peticiones por minuto) necesitan ajustar los tiempos; una persona puede preferir no reintentar.

**Independent Test**: Una sección `[retries]` opcional del archivo de configuración fija el número de intentos y las esperas; con 1 intento no hay reintentos; valores inválidos detienen el arranque con un mensaje claro.

**Acceptance Scenarios**:

1. **Given** una configuración sin `[retries]`, **When** arranca, **Then** se aplican valores por defecto sensatos.
2. **Given** `max_attempts = 1`, **When** hay un fallo temporal, **Then** no se reintenta.
3. **Given** un valor no numérico, negativo o incoherente (`base_delay` mayor que `max_delay`), **When** se carga la configuración, **Then** se informa del campo y no arranca.

### Edge Cases

- **Cancelación** (Ctrl-C, D-01): `asyncio.CancelledError` nunca se captura ni se reintenta, tampoco durante la espera.
- **Pista de espera** del proveedor («reintente en N s»): si existe y es válida se respeta como mínimo de la espera; si es ilegible, negativa o no numérica, se ignora y manda el crecimiento exponencial.
- **Respuesta vacía o ilegible** del proveedor: es un `ProviderError` genérico del adaptador, no temporal: no se reintenta.
- **Datos**: ningún registro de reintento contiene el texto del error original, la clave, los mensajes ni los argumentos; se usa el valor centinela `VALOR-DE-PRUEBA-123` para comprobarlo.
- **Observador que falla**: un fallo al registrar un intento no debe ocultar ni cambiar el error del proveedor ni impedir el reintento.
- **Límites de sesión**: la espera cuenta en el tiempo de la tarea (HU-01-06); un límite agotado detiene la tarea como siempre. Esta historia no lo cambia.
- **Cambio de sesión** (`/reanudar`): el registro del intento debe ir a la sesión activa, no a la de arranque.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST reintentar una llamada al proveedor cuando falla con un error temporal: tiempo agotado (`ProviderTimeout`), servicio no disponible (`ProviderUnavailable`) o límite de tasa.
- **FR-002**: El límite de tasa MUST distinguirse de la cuota agotada con un subtipo propio de `QuotaExceeded` definido en el adaptador (`RateLimited`); el adaptador de LiteLLM MUST traducir `RateLimitError` a él y el resto de errores de cuota (`PaymentRequiredError`, `BudgetExceededError`) MUST seguir siendo `QuotaExceeded` sin reintento.
- **FR-003**: Todo error que no sea temporal (cualquier otro `ProviderError`) MUST propagarse en el acto, sin espera.
- **FR-004**: La espera antes del reintento *n* (1, 2, …) MUST ser `base_delay × 2^(n−1)` con tope `max_delay`, sin aleatoriedad.
- **FR-005**: El número total de intentos MUST ser `max_attempts` (incluye el primero); con 1 no hay reintentos.
- **FR-006**: Si el error trae una pista de espera válida (segundos, número finito ≥ 0), la espera MUST ser el mayor entre la exponencial y la pista; si la pista supera `max_delay`, MUST no reintentarse y propagarse el error.
- **FR-007**: Agotados los intentos, el sistema MUST propagar el último error original sin envolverlo (mismo tipo), para HU-07-05.
- **FR-008**: `asyncio.CancelledError` MUST propagarse sin captura, también durante la espera.
- **FR-009**: Cada reintento MUST registrarse como un evento existente del catálogo (`provider_error`, motivo `retry`) con solo: número de intento, máximo de intentos, tipo de fallo (nombre de clase canónico), espera en segundos. Sin texto del error, mensajes, claves ni argumentos. No se añaden eventos ni cambia `core/events.py`.
- **FR-010**: Un fallo del observador MUST NOT alterar el resultado de la llamada.
- **FR-011**: La espera MUST ser inyectable (`sleep` por constructor); ninguna prueba espera de verdad.
- **FR-012**: La configuración MUST admitir una sección opcional `[retries]` con `max_attempts`, `base_delay` y `max_delay` (segundos), valores por defecto sensatos, rechazo de campos desconocidos, tipos erróneos, valores fuera de rango (`max_attempts` entre 1 y 10; `base_delay` > 0; `max_delay` entre `base_delay` y 600 s) y mensajes sin reproducir el valor.
- **FR-013**: El envoltorio MUST cumplir el puerto `Provider` y envolver a cualquier otro `Provider`; `compose()` lo cablea sobre el proveedor construido (real o inyectado).
- **FR-014**: El bucle, los puertos de `core/interfaces/` y el catálogo de eventos MUST NOT cambiar.

### Key Entities

- **Política de reintentos**: número de intentos, espera base y tope (configuración inmutable).
- **Intento de reintento**: número, máximo, tipo de fallo y espera; nunca datos de la petición.
- **`RateLimited`**: subtipo de `QuotaExceeded` con una pista de espera opcional.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una secuencia de 2 fallos temporales seguidos de una respuesta correcta se completa sin error de cara a la persona, con 3 llamadas y 2 esperas crecientes.
- **SC-002**: El 100 % de los errores no temporales se propagan con una sola llamada y cero esperas.
- **SC-003**: Con `max_attempts = N`, un fallo temporal permanente produce exactamente N llamadas y N−1 esperas y propaga el mismo tipo de error.
- **SC-004**: Ningún registro de reintento contiene el valor centinela de prueba incluido en el error, la clave o los mensajes.
- **SC-005**: Cero esperas reales en las pruebas del módulo; cobertura del módulo nuevo: 100 % de líneas y ramas.

## Assumptions

- La espera es determinista (sin aleatoriedad): el uso es de una sola persona y proceso, no hay estampida de clientes, y el determinismo hace comprobables los tiempos.
- Valores por defecto: `max_attempts = 5`, `base_delay = 2` s, `max_delay = 30` s (esperas 2, 4, 8, 16 s). Con 5 peticiones por minuto no bastan por sí solos: ahí manda la pista del proveedor o el ajuste de la persona.
- LiteLLM puede exponer una pista como atributo del error; si no existe, solo manda la exponencial. Leer cabeceras HTTP concretas queda fuera.
- Los límites por minuto de planes gratuitos se tratan como temporales (límite de tasa); un crédito agotado no.
- HU-07-05 (conmutación) y HU-07-03 (segundo proveedor) quedan fuera de alcance.
- Hallazgo para la CLI (área C, no se toca): `cli/render.py` no conoce el motivo `retry` y mostrará una línea genérica de error por cada reintento; añadir una línea propia es una mejora posterior.
