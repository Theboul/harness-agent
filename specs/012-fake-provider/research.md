# Research: HU-00-03 — Proveedor simulado para pruebas

Todas las decisiones de alcance las tomó el responsable el 2026-10-23 (véase *Clarifications* en la spec). Aquí se resuelven los detalles técnicos.

## R-01 — Qué es «el mismo tipo que un proveedor real»

- **Decision**: una jerarquía canónica en el núcleo (`ProviderError` y tres subclases). El proveedor real traducirá los errores de su biblioteca a estos tipos.
- **Rationale**: no existe hoy ninguna jerarquía; `core/` no puede importar excepciones de terceros (RNF-12); el bucle publica `type(exc).__name__`, así que el nombre del tipo es lo observable. HU-07-05 enumera cuota, límite de tasa, tiempo agotado, no disponible y conexión como elegibles; esta historia nombra solo tres.
- **Alternatives considered**: (b) definirla dentro del doble, descartada porque el adaptador real tendría que importar de `tests/`; una jerarquía completa con clasificación de elegibilidad, descartada por Principio VI (es de HU-07-05).

## R-02 — Cómo reacciona hoy el bucle a un error del proveedor

- **Decision**: no se modifica el bucle.
- **Rationale**: `loop.py` captura `Exception`, publica `PROVIDER_ERROR` con `{reason: "provider_exception", error_type: type(exc).__name__, message}` y devuelve `TurnStatus.PROVIDER_FAILED`. Con `QuotaExceeded` el `error_type` es `"QuotaExceeded"` (AC-02 verificable sin cambiar el bucle). El mensaje queda acotado por `_bounded`.

## R-03 — Qué reutilizar de `ScriptedProvider`

- **Decision**: reutilizar el tipo `ScriptExhausted` y los nombres de atributos; no heredar de la clase ni llamar a sus métodos privados.
- **Rationale**: heredar acoplaría el doble nuevo al de A (y a su opción `allow_invalid_ids`); `_check_ids` es privado. La validación de ids son ~10 líneas.
- **Alternatives considered**: heredar de `ScriptedProvider` (descartado por acoplamiento); mover la validación a un módulo común (descartado: modificaría un doble existente, SC-005).

## R-04 — Determinismo

- **Decision**: el doble no usa reloj, aleatoriedad ni entorno; las pruebas comparan `(tipo, carga)` y el historial, no `id` ni `timestamp`.
- **Rationale**: `Event.create` genera UUID y marca de tiempo, que no controla el proveedor. Se repite cada escenario 20 veces (SC-001).

## R-05 — Garantizar «sin red»

- **Decision**: una fixture parchea `socket.create_connection` y `socket.getaddrinfo` para fallar si se llaman, y `socket.socket.connect` para fallar ante cualquier destino que no sea loopback (`127.0.0.0/8`, `::1`) ni `AF_UNIX`; la suite del doble la usa.
- **Rationale**: demuestra el 0 intentos de conexión externa (SC-002) también en una máquina con red. Se permite loopback porque en Windows `socket.socketpair()` (el bucle de asyncio) conecta a loopback.
- **Alternatives considered**: `pytest-socket` (descartado: dependencia nueva).

## R-06 — Fallos sin espera

- **Decision**: lanzar la excepción en la misma llamada; no hay `await` que ceda y no se usa `sleep`. La prueba mide con `time.perf_counter` que cada caso tarda menos de 10 ms.
- **Rationale**: SC-004; un tiempo agotado «real» haría lentas las pruebas del bucle.

## R-07 — Copias y mutabilidad

- **Decision**: `copy.deepcopy` del guion al construir y del paso al devolverlo; las listas recibidas se copian al registrarlas.
- **Rationale**: `ProviderResponse` es inmutable en forma pero contiene una lista (`tool_calls`) y `ToolCall.arguments` es un diccionario; sin copia, el bucle podría mutar el guion y romper la repetibilidad.

## R-08 — Qué no se prueba aquí

- La tarea guionizada de tres pasos con herramientas de archivos (HU-01-03) y el adaptador LiteLLM (HU-07-02) quedan fuera; se prueba el mismo patrón con `RecordingTool`.
