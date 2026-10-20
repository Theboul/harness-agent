# Research: HU-01-05 — Bus de eventos desacoplado de la interfaz

**Fecha**: 2026-10-20 · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

No quedó ningún punto por aclarar tras la especificación. Cada decisión recoge qué se eligió, por qué y qué alternativas se descartaron.

## R-01 — Ubicación: `core/`, módulo plano `in_memory_event_bus.py`

- **Decisión**: `src/harness_agent/core/in_memory_event_bus.py`, exportado desde `harness_agent.core`.
- **Razón**: la skill `estructura-carpetas-harness` manda a `adapters/` lo que «cambiaría al cambiar de proveedor, base de datos o interfaz»; un bus en memoria, solo con biblioteca estándar, no cambia con ninguno. Precedente directo: `InMemoryToolRegistry` en `core/tools/`. Además `core/` ya exige solo biblioteca estándar, que es lo que el módulo usa.
- **Alternativas**: `adapters/event_bus/` (descartada: obligaría a que el bucle o la raíz de composición dependan de una capa externa para algo sin dependencias externas; el bucle de A ya recibe el bus por inyección); un subpaquete `core/bus/` (descartada: una sola pieza no lo justifica).

## R-02 — Almacenamiento: diccionario de tuplas inmutables por tipo

- **Decisión**: `dict[EventType, tuple[EventHandler, ...]]`; `subscribe` reemplaza la tupla por otra con el manejador añadido; `emit` lee la tupla una vez al empezar.
- **Razón**: la «copia de la lista de manejadores al empezar cada emisión» (decisión 4) sale gratis: la tupla leída no cambia aunque otro manejador suscriba durante la entrega. Coste O(n) al suscribir (raro) y O(1) al emitir (frecuente).
- **Alternativas**: lista viva (descartada: es lo que hace el doble y recibe el evento en curso un manejador suscrito durante la entrega); copiar la lista en cada `emit` (equivalente pero más caro).

## R-03 — Aislamiento de fallos con propagación

- **Decisión**: cada manejador se llama dentro de `try`; una `Exception` se acumula y la entrega continúa; al terminar, si hay fallos, se lanza `EventDeliveryError(mensaje, fallos)` con los fallos en el orden de entrega.
- **Razón**: Q4 del bucle de A: las excepciones de `emit` se propagan (si falla «herramienta solicitada» la herramienta no se ejecuta). Parar en el primer error dejaría a otros suscriptores sin el evento (HU-03-02 perdería eventos por culpa de una interfaz); tragar errores rompería Q4.
- **Alternativas**: registrar y seguir (descartada: se traga el error); detenerse en el primero (descartada: pierde entregas); lanzar el primer error y adjuntar el resto como notas (descartada: no es un contenedor de errores y `except*` no funciona).

## R-04 — `EventDeliveryError` como subclase de `ExceptionGroup[Exception]`

- **Decisión**: `class EventDeliveryError(ExceptionGroup[Exception])` con `derive` sobreescrito (`return EventDeliveryError(self.message, excs)`), mensaje en español sin la carga del evento.
- **Razón**: `ExceptionGroup` ya es el contenedor estándar (3.11+); permite `except*` y `.exceptions`. Al derivar de `Exception` (no de `BaseExceptionGroup` genérico) el bucle y HU-03-02 la capturan con `except Exception`. Sin `derive`, `split` y `subgroup` devolverían un `ExceptionGroup` simple y perderían el tipo.
- **Alternativas**: excepción propia con una lista (descartada: reinventa el contenedor); `BaseExceptionGroup` (descartada: no es `Exception`).

## R-05 — Excepciones no ordinarias: propagación inmediata con nota

- **Decisión**: `except BaseException` tras `except Exception`: si hubo fallos ordinarios previos, se anotan con `add_note` («N fallos previos: TipoA, TipoB; el evento X no llegó a los manejadores restantes», sin contenido del evento) y se relanza la misma excepción, sin envolverla.
- **Razón**: la decisión del responsable fija que la cancelación o la interrupción no se agrupan; una nota evita perder los fallos previos en silencio y copia la técnica del bucle (R-08 de HU-01-01). **Asumido, a confirmar** (plan, D3).
- **Alternativas**: descartar los fallos previos (más simple, pero se pierden); lanzar un `BaseExceptionGroup` mixto (contradice «sin agrupar» y convierte la cancelación en un grupo).

## R-06 — Mensajes sin la carga del evento

- **Decisión**: el mensaje del error agrupado dice solo el tipo de evento y el número de fallos («Fallaron 2 manejadores al entregar el evento 'tool_finished'.» / «Falló 1 manejador …»); los `TypeError` nombran el tipo recibido (`str`, `int`), no su valor.
- **Razón**: la carga de un evento puede contener resultados de herramientas o mensajes con datos sensibles; los mensajes de error acaban en registros y pantallas.
- **Alternativas**: incluir el identificador del evento (descartada por ahora: el identificador no es sensible, pero la causa raíz ya viaja en las excepciones agrupadas; se puede añadir sin cambiar el contrato).

## R-07 — Entrega anidada inmediata y sin cola

- **Decisión**: un manejador que llama a `emit` provoca una entrega anidada completa antes de que siga el manejador siguiente; sin cola.
- **Razón**: decisión 4; es lo que ya hace el doble; mantiene el orden causal que el bucle espera (el evento solicitado se publica antes de ejecutar la herramienta) y evita estado compartido. Una cola exigiría un bucle de vaciado y cambiaría cuándo se informan los errores.
- **Alternativas**: cola FIFO (descartada: difiere errores y rompe Q4); prohibir la reentrada (descartada: HU-03-02 y las interfaces pueden reemitir).
- **Recursión sin condición de parada**: la detiene `RecursionError` de Python; responsabilidad del suscriptor.

## R-08 — Validación estricta

- **Decisión**: `subscribe` exige `isinstance(event_type, EventType)` y `callable(handler)`; `emit` exige `isinstance(event, Event)`; `TypeError` con mensaje en español; sin registrar ni entregar nada si falla. Una cadena como `"user_message"` no es un `EventType` y se rechaza.
- **Razón**: decisión 5 y 6; un error de tipo en el momento de suscribir es más fácil de depurar que un manejador que nunca recibe nada.
- **Alternativas**: aceptar cadenas y convertirlas con `EventType(...)` (descartada: la decisión pide validación estricta).

## R-09 — Un contrato de pruebas para dos implementaciones

- **Decisión**: `tests/contracts/test_event_bus_contract.py` con una fixture parametrizada con `RecordingEventBus` y `InMemoryEventBus` para las cláusulas comunes (C-1 a C-8) y una segunda clase solo con el bus real (C-9 a C-15). El contrato lista qué cláusulas aplican a cada una.
- **Razón**: decisión 7; precedente en `test_provider_interchangeability.py`. El doble no se toca, así que sus diferencias (lista viva, sin aislamiento, sin validación) se declaran en vez de corregirse.
- **Alternativas**: dos archivos duplicados (descartada: se separan).

## R-10 — AC-01 con el bucle real

- **Decisión**: `make_rig(script, tools, bus=InMemoryEventBus())` de `tests/core/support.py` con un guion de una herramienta y respuesta final, y otro con un error del proveedor; un suscriptor por tipo recoge lo emitido y se compara su orden con el que fija el guion. También un suscriptor que falla: el error agrupado llega a `run_turn` (Q4).
- **Razón**: decisión 8; reutiliza el equipo existente sin tocar el bucle. «Aprobación pedida» no se emite aún (HU-05-03): se anota como observación; el bus la entrega (contrato C-6).

## R-11 — Suscriptor de registro con `logging` solo en pruebas

- **Decisión**: un manejador de prueba escribe `logger.info` con el tipo, la sesión y el identificador del evento en el logger `harness.events`; la prueba usa `caplog.at_level` y comprueba una entrada por evento. No se registra la carga del evento.
- **Razón**: decisión 9; `caplog` no necesita configurar nada y no toca el entorno. No hay suscriptor de producción (la CLI es HU-06-01).
- **Alternativas**: un suscriptor de producción en `observability/` (descartada: Principio VI).

## R-12 — AC-02: ampliar y no duplicar

- **Decisión**: `tests/architecture/test_core_no_terminal.py` importa `console_uses` de `test_loop_boundaries.py` (impresión, lectura y `sys.stdout/stderr/stdin`) y lo aplica a todos los módulos de `core/`; añade detección de bibliotecas de terminal (`curses`, `readline`, `rich`, `typer`, `click`, `prompt_toolkit`, `colorama`, `blessed`, `urwid`, `textual`, `tty`, `termios`, `msvcrt`, `getpass`, `pty`), de alias de `sys` y de `from sys import stdout`; autoprueba con fragmentos y mutación sobre una copia de `core/`. También comprueba que el módulo del bus solo importa biblioteca estándar y `harness_agent.core` y no define tipos de evento (regla de negocio 2).
- **Línea base medida (2026-10-20)**: 17 módulos en `core/` y 0 hallazgos con este detector ampliado.
- **Alternativas**: modificar `test_loop_boundaries.py` (descartada: es de A y ya está cerrado); duplicar el detector (descartada).

## R-13 — Sin seguridad entre hilos

- **Decisión**: sin bloqueos; documentado. El bucle del agente es asíncrono pero de un solo hilo y la entrega es síncrona.
- **Alternativas**: `threading.Lock` (descartada: cuesta en el camino caliente y nadie emite desde otro hilo).
