# Especificación: HU-07-05 — Conmutación por fallo con umbral por modelo

**Rama**: `gustavo` · **Responsable de la ficha**: A — Núcleo · **Implementa**: Claude por encargo de la persona usuaria (pendiente de ratificar por A, B y C)
**Depende de**: HU-07-04 (reintentos), HU-06-06 (alias de modelos y `ModelSwitch`), HU-02-03 (compactación por modelo). La ficha depende de HU-07-03 (segundo proveedor por configuración), que **no está hecha ni se implementa aquí**: la lista ordenada de respaldo usa los alias de HU-06-06 (D-01).

## Resumen

Si el modelo activo falla por un motivo ajeno a la petición (cuota agotada, límite de tasa, tiempo agotado, servicio no disponible, error de conexión) y ya se agotaron sus reintentos, el arnés pasa al siguiente modelo de una lista ordenada de respaldo, repite la llamada que falló y lo dice a la persona y al registro de la sesión. Los errores que sí dependen de la petición (clave inválida, petición mal formada, política de contenido) y cualquier error desconocido no conmutan: la persona recibe el error. Cada modelo se prueba como máximo una vez por turno y nunca hay bucle ni vuelta automática al primero. Tras el cambio, la compactación usa la ventana (y el umbral) del nuevo modelo.

La función está **apagada por defecto** (`[failover] models` vacío o ausente): sin lista de respaldo nada cambia.

No se cambia ningún puerto de `core/interfaces/`, ni la jerarquía de errores de proveedor, ni `core/loop.py`, ni el catálogo de eventos (el evento `PROVIDER_SWITCHED` ya existe), ni `core/context/compactor.py`, ni `core/redaction.py`, ni `core/verification/`.

## Historia y criterios de aceptación (literales de `docs/04d-historias-conexiones.md`)

### HU-07-05 — Conmutación por fallo con umbral por modelo

**Reglas de negocio**

1. Errores elegibles: cuota agotada, límite de tasa, tiempo agotado, servicio no disponible y error de conexión.
2. Errores no elegibles: clave inválida, petición mal formada y rechazo por política de contenido.
3. Cada proveedor se prueba como máximo una vez por turno; no hay vuelta automática al primero dentro del mismo turno.
4. El cambio es automático y queda visible para el usuario.

**Criterios de aceptación**

- **AC-01 — Conmutación ante error elegible.** Dado un error elegible (cuota agotada, límite de tasa, tiempo agotado, servicio no disponible o error de conexión) en el proveedor activo, cuando ocurre, entonces el sistema cambia al de respaldo, repite el turno y lo registra como evento de sesión y en pantalla.
- **AC-02 — Error no elegible sin conmutación.** Dado un error no elegible (clave inválida, petición mal formada o rechazo por política de contenido), cuando ocurre, entonces no hay conmutación y el usuario recibe el error.
- **AC-03 — Todos los proveedores fallan sin bucle.** Dado que el proveedor de respaldo también falla con un error elegible en el mismo turno, cuando se agota la lista de proveedores, entonces el turno termina con un error claro tras probar cada proveedor una sola vez, sin bucle y sin volver automáticamente al primero dentro del turno.
- **AC-04 — Umbral propio del nuevo modelo.** Dado el cambio de modelo, cuando se evalúa la compactación, entonces se usa el umbral propio de la ventana del nuevo modelo.

En el resto del documento se citan como **AC-01** a **AC-04**.

## Decisiones (dudas pequeñas resueltas con el criterio más seguro; pendientes de ratificar)

No hizo falta parar por un caso A/B/C: el evento de la regla 5 ya existe en el catálogo (`PROVIDER_SWITCHED`, «Fallback provider switched after primary failure», sin uso hasta hoy) y la jerarquía de errores alcanza.

- **D-01 Lista de respaldo = alias de HU-06-06.** `[failover] models = ["alias1", "alias2"]` nombra alias de `[models]`, en orden. La lista completa del turno es `[predeterminado, alias1, alias2…]` (el modelo configurado en `model` es siempre el primero). HU-07-03 sigue pendiente y no se implementa; sus alias servirían igual.
- **D-02 Clasificación sobre la jerarquía existente.** Elegibles: `QuotaExceeded` (incluye `RateLimited` y el crédito agotado), `ProviderTimeout` y `ProviderUnavailable` (el adaptador de LiteLLM ya traduce los errores de conexión, `InternalServerError` y `BadGatewayError` a este último). No elegibles: el `ProviderError` genérico (donde el adaptador deja la clave inválida, la petición mal formada y el rechazo por política de contenido), `FailoverExhausted` y **cualquier otra excepción**. Falla cerrado: lo desconocido no conmuta. No se añade ningún subtipo.
- **D-03 Qué es un «turno».** Una petición de la persona en `run_session`, con todo lo que cuelga de ella: las llamadas al modelo del bucle, las rondas de verificación, el resumen de la compactación y los subagentes (comparten el estado del turno). `run_session` llama a `begin_turn()` antes de cada petición; eso reinicia la lista de probados. Quien maneje el bucle sin `run_session` y no llame a `begin_turn()` tiene una sola lista de probados para toda la vida del envoltorio: lo más cerrado (no puede haber bucle).
- **D-04 Orden y «probado».** Tras un error elegible se elige el primero de la lista, **en su orden**, que no se haya probado en el turno. El modelo activo al hacer la primera llamada del turno cuenta como probado. Un modelo se marca como probado al intentar pasar a él, haya o no funcionado (uno con la clave ausente se salta y no se reintenta).
- **D-05 Dónde vive.** `FailoverProvider` (`adapters/providers/`) envuelve al `RetryingProvider` que envuelve a `ModelSwitch`: la conmutación ocurre **después de agotar los reintentos** del modelo, y cada modelo tiene su propio presupuesto de reintentos. «Repetir el turno» es repetir la llamada al modelo que falló con los mismos mensajes: el bucle no se entera. La regla pura (qué errores conmutan, qué se probó) está en `core/failover.py`. El cambio usa `ModelSwitch.select`, que es atómico (si no se puede construir el proveedor no cambia nada).
- **D-06 El cambio es persistente.** El modelo de respaldo queda como modelo activo (igual que tras `/model <alias>`; `/model` lo muestra y `/model predeterminado` vuelve). No hay regreso automático entre turnos: evita el ir y venir y hace observable AC-04. El siguiente turno empieza en el modelo activo y, si ese falla, puede pasar a cualquiera de la lista aún no probado en ese turno, el primero de la lista incluido.
- **D-07 Evento y pantalla.** `PROVIDER_SWITCHED {from_model, to_model, reason}` en la sesión **activa** (`SessionCursor`), donde `reason` es el nombre de la clase del error (nunca su texto). La pantalla recibe una línea fija por el `WarningSink` («Cambio de modelo por fallo: … a … (motivo)»). No se cambia `cli/render.py`. Las trazas completas siguen para HU-10-01.
- **D-08 Lista agotada.** Se lanza `FailoverExhausted` (subtipo de `ProviderError` definido en `adapters/providers/errors.py`, como `RateLimited`) con un texto fijo en español que no contiene nada del proveedor; el bucle lo muestra como un fallo de proveedor del turno y la persona puede volver a intentar en la petición siguiente (la lista de probados se reinicia).
- **D-09 Error no elegible.** Se relanza el mismo error, sin cambiar de modelo (AC-02). Reintentos y conmutación no se aplican.
- **D-10 Configuración.** `[failover] models` es una lista de textos; cada uno debe ser un alias de `[models]`, sin repetidos ni la palabra reservada `predeterminado`, y hasta 8 entradas. Un valor inválido detiene el arranque con un problema que nombra el campo y no repite el valor. Ausente o vacía = apagada.
- **D-11 Clave de respaldo ausente.** Al arrancar se omite el alias cuya variable de clave no está en el entorno, con un aviso fijo que nombra la variable y nunca su valor, y el arranque sigue. Si al conmutar el proveedor no se puede construir (`ModelUnavailable`), se salta con una línea fija, cuenta como probado y se sigue con el siguiente.
- **D-12 AC-04.** El compactador ya pregunta el modelo activo en cada evaluación (`switch.model`) y la ventana del modelo sale de `[context]`: tras el cambio, la **siguiente** evaluación (antes de cada petición) usa la ventana y el umbral del nuevo modelo. No se toca el compactador. **Limitación:** la compactación no se evalúa a mitad de turno; si el historial ya supera la ventana del nuevo modelo, este lo rechaza como petición mal formada (no elegible) y la persona ve el error; la petición siguiente compacta con el umbral nuevo. Un gancho a mitad de turno exigiría cambiar `core/loop.py` (de A): hallazgo.
- **D-13 `/model` manual.** El estado del turno guarda nombres de alias; el envoltorio lee siempre el alias activo del `ModelSwitch` y no lo cachea. Un `/model` entre dos peticiones cambia el modelo activo sin dejar rastro en la lista (se reinicia con la petición siguiente).
- **D-14 Cancelación y secretos.** `CancelledError` nunca se captura. Ni el aviso, ni el evento, ni `FailoverExhausted` llevan el texto del error del proveedor ni claves; el evento lleva nombres de modelo (`<proveedor>/<modelo>`) y el nombre de la clase del error.
- **D-15 Costo.** En el peor caso una llamada cuesta (modelos de la lista) × (`[retries] max_attempts`) intentos antes del error final; es un límite acotado y está documentado.

## Requisitos funcionales

- **FR-001** (AC-01) Con la lista de respaldo activa y un error elegible del modelo activo tras agotar sus reintentos, la llamada se repite con el siguiente modelo no probado en el turno; el cambio queda como `PROVIDER_SWITCHED` en la sesión activa y como una línea en pantalla.
- **FR-002** (AC-01) Cada uno de los cinco errores elegibles (cuota agotada, límite de tasa, tiempo agotado, servicio no disponible, error de conexión) conmuta.
- **FR-003** (AC-02) Un error no elegible (clave inválida, petición mal formada, política de contenido) y cualquier error desconocido se relanzan sin conmutar ni probar otro modelo.
- **FR-004** (AC-03) Cada modelo se prueba como máximo una vez por turno; no hay vuelta automática a uno ya probado en el turno.
- **FR-005** (AC-03) Si se agota la lista, el turno termina con un error claro y fijo, tras probar cada modelo una sola vez.
- **FR-006** El estado de «probados» se reinicia al empezar cada petición (`begin_turn`) y comprende los subagentes, las rondas de verificación y el resumen de la compactación de esa petición.
- **FR-007** (AC-04) Tras el cambio, la evaluación de compactación usa la ventana y el umbral del modelo nuevo.
- **FR-008** `[failover] models` (apagada por defecto) valida alias existentes, sin repetidos; un valor inválido detiene el arranque sin repetir el valor.
- **FR-009** Un modelo de respaldo con la clave ausente se omite con un aviso fijo (sin la clave) y no rompe el arranque ni la conmutación.
- **FR-010** Un `/model` manual no rompe el estado del turno ni la conmutación siguiente.
- **FR-011** Ningún secreto ni texto del proveedor llega a mensajes, eventos ni avisos de la conmutación.
- **FR-012** Con la configuración por defecto nada cambia: no hay envoltorio, ni evento, ni aviso.
- **FR-013** No cambian `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/context/compactor.py`, `core/redaction.py`, `core/verification/` ni `tests/doubles/`.

## Criterios de éxito

- **SC-001** Las cuatro puertas de calidad y `pytest tests/architecture` en exit 0; 100 % de líneas y ramas en los módulos nuevos.
- **SC-002** Diff vacío de los archivos protegidos.
- **SC-003** Con la lista de respaldo de N modelos y todos fallando con error elegible, el proveedor recibe exactamente N llamadas (una por modelo, con `[retries] max_attempts = 1`) en la petición, y ni el aviso, ni el evento, ni el error final contienen el texto del proveedor o un valor centinela.
- **SC-004** Con la configuración por defecto la suite existente no cambia (salvo lo que liste el plan).

## Casos límite

- La lista de respaldo tiene un solo modelo y falla: se prueba el predeterminado, luego ese, y se agota.
- El modelo activo al empezar es un alias que no está en la lista (`/plan`): se marca probado y la lista se recorre en su orden.
- Un alias de respaldo cuyo proveedor no se puede construir: se salta y cuenta como probado.
- Dos peticiones seguidas con fallo: la segunda tiene lista de probados nueva.
- Cancelación (Ctrl-C) durante la espera de un reintento o de la llamada: se propaga, sin conmutar.
- Error elegible en la llamada de resumen de la compactación: conmuta como cualquier otra llamada del turno.
