# Research: Raíz de composición y punto de entrada ejecutable

Fase 0 de `/speckit-plan`. No quedan marcadores `NEEDS CLARIFICATION`; aquí se justifican las decisiones de diseño que la spec deja abiertas a propósito.

## 1. Forma de la composición: función síncrona + función asíncrona

- **Decisión**: `compose(config, ...)` es síncrona y devuelve una `Composition`; `run_session(composition, ...)` es `async` y llama a `run_cli`; `main()` las une con `asyncio.run`.
- **Razón**: separar construir de ejecutar permite probar todo el cableado (orden, fallos, área ausente) sin bucle de eventos, y probar la sesión con dobles sin pasar por la configuración. Todo lo que construye es síncrono (el almacén, el área, el registro); solo `run_cli` es `async`.
- **Alternativas**: una sola función `main` grande (no se puede probar por partes y duplica el cableado en cada prueba de integración, que es justo lo que esta historia elimina); una clase `Application` con ciclo de vida (sobredimensionada para un solo recurso que cerrar).

## 2. Orden de construcción

- **Decisión**: proveedor → área y herramientas → política → bus → almacén → sesión → registrador → bucle.
- **Razón**: lo que puede fallar por el entorno del usuario (dependencia opcional ausente, modelo mal formado) va **antes** de abrir la base, para no dejar una fila `active` huérfana ni un archivo creado sin necesidad. El registrador se conecta tras crear la sesión (el almacén exige que la sesión de cada evento exista, ver `event_recorder`) y antes de devolver la composición, por lo que ningún evento se emite sin estar suscrito (FR-004). Las suscripciones se hacen antes de que `run_cli` suscriba el render, así que un evento se **guarda antes de mostrarse**.
- **Alternativa**: crear la sesión primero. Descartada por las filas huérfanas.

## 3. Qué se inyecta y por qué

- **Decisión**: `provider_factory`, `clock`, `id_factory`, `environ`, `config_path` y los tres flujos de texto. El valor por omisión de cada uno es el real.
- **Razón**: es lo que FR-012 exige y lo que usan las demás piezas (`load_config(environ=…)`, `SqliteSessionStore(clock=…, id_factory=…)`, `run_cli(input_stream=…, output=…)`). `bootstrap.py` no lee `os.environ` por su cuenta: la guarda lo vigila; `main` pasa `None` y `load_config` aplica su propia regla.
- **El proveedor**: `FakeProvider` vive en `tests/doubles/` y `src/` no puede importarlo. Por eso el proveedor de prueba entra por `provider_factory`. El valor por omisión construye `LiteLLMProvider` con `config.model`, `config.limits.max_output_tokens` y `config.api_key` (el cableado que HU-07-02 dejó anotado).

## 4. Interrupción con Ctrl-C (medido, no supuesto)

- **Hecho comprobado** (sonda en Linux, Python 3.12): bajo `asyncio.run`, con la lectura de entrada bloqueada en `readline()`, el **primer** Ctrl-C no hace nada visible (el manejador de `asyncio.Runner` cancela la tarea principal, pero la lectura bloqueante no vuelve); el **segundo** lanza `KeyboardInterrupt` y el proceso sale con 130.
- **Durante un turno** (en un `await`, por ejemplo la llamada al modelo o una herramienta) el primer Ctrl-C sí cancela la tarea principal; `AgentLoop` publica `INTERRUPTED` (ya lo hace) y relanza `CancelledError`, que `asyncio.run` convierte en `KeyboardInterrupt`.
- **Decisión**: no instalar un manejador de señal propio. El comportamiento queda: en un turno, un Ctrl-C; en el prompt, dos Ctrl-C o `/salir`/fin de entrada. En todos los casos: base cerrada, sin traza, código 130.
- **Hallazgo para C** (`cli/` está protegido en esta historia): leer la entrada con `run_in_executor` o `asyncio` haría que un solo Ctrl-C bastara también en el prompt; es parte de la cancelación controlada.
- **Alternativas**: `signal.signal` propio (cambia la semántica de la cancelación, difiere entre Windows y Linux y no se puede probar igual en ambos); hilo lector de entrada (cambio en `cli/`, fuera de alcance).
- **Prueba**: la interrupción mid-turno se prueba cancelando la tarea con una herramienta bloqueante (`BlockingTool`) y comprobando el evento `INTERRUPTED` guardado; no se envían señales reales en la CI (poco fiable en Windows).

## 5. Códigos de salida

| Código | Significado | Origen |
|---|---|---|
| 0 | terminación normal (`/salir` o fin de entrada) | `run_cli` (`EXIT_OK`) |
| 1 | un turno falló con una excepción ordinaria | `run_cli` (`EXIT_FAILURE`) |
| 2 | fallo de arranque (configuración, clave, dependencia, base) | `bootstrap` (`EXIT_STARTUP`) |
| 130 | interrupción de teclado | `bootstrap` (`EXIT_INTERRUPTED`; 128 + SIGINT, convención de shells) |

`EXIT_OK`/`EXIT_FAILURE` no se exportan en `cli.__all__`; se usa el valor que devuelve `run_cli`, sin reimportar constantes de un submódulo.

## 6. Mensajes de arranque

- **Decisión**: prefijo fijo «No se pudo iniciar: » + el texto del error ya definido por cada pieza, aplanado a una línea (`" ".join(text.split())`). Se escribe en el flujo de errores inyectable (por omisión `sys.stderr`).
- **Errores conocidos**: `ConfigError` y subclases (HU-00-04: ya en español y sin valores), `ProviderDependencyError` (HU-07-02: incluye el comando de instalación), `SessionStoreError` y `SchemaVersionError` (HU-03-01: texto fijo sin la ruta ni el motor).
- **Errores no previstos**: «No se pudo iniciar: error inesperado (NombreDeTipo).» y código 2. **Nunca** `str(exc)`: puede contener fragmentos de entrada o de clave (fallar cerrado y SC-003).
- **Alternativas**: dejar subir la traza (viola AC-P3); capturar todo con un solo mensaje genérico (pierde la causa accionable de los errores conocidos).

## 7. Avisos de área

- **Sin `paths.workspace_root`**: aviso único «Aviso: no hay área de trabajo configurada (paths.workspace_root); las herramientas de archivos están desactivadas.» Las herramientas se registran igualmente con `area=None` (el modelo las conoce, no recibe `[unknown_tool]`), pero la política sin área trata cualquier uso como «preguntar» y, sin aprobación interactiva, lo deniega: el modelo recibe `[approval_required_unavailable]` y la herramienta no llega a ejecutarse (comprobado en T003 con las cuatro herramientas). El `[sin_area]` de las herramientas queda como segunda barrera.
- **Carpeta inexistente o no carpeta**: se detecta con `WorkspaceArea(...).root.is_dir()` y se trata igual que sin área, con un aviso distinto que no reproduce la ruta (puede ser sensible).
- **Alternativa**: abortar el arranque. Descartada: AC-04 de HU-01-03 pide que arranque y falle cerrado, y permite usar el agente solo para conversar.

## 8. Cosas que se dejan como están

- **Modelo `fake/…`**: pasa la validación de configuración (está en `PROVIDER_KEY_VARIABLES`), pero la composición real construye `LiteLLMProvider`, que no lo conoce. Se documenta como hallazgo; las pruebas usan `provider_factory`.
- **Estado de la sesión al terminar**: ni el puerto ni el almacén permiten pasar de `active` a `completed`/`interrupted`. Hallazgo para B.
- **Límites** (`config.limits.max_turns/seconds/tokens`): se ignoran hasta HU-01-06; solo `max_output_tokens` se usa (para el proveedor).
- **Redacción de secretos y protección de la base** (PD-10, PD-09): sin cambios.
