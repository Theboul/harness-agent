# Research: HU-06-01 — CLI básica con eventos en tiempo real

**Fecha**: 2026-10-20 · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

No quedó ningún punto por aclarar tras la especificación. Cada decisión recoge qué se eligió, por qué y qué alternativas se descartaron.

## R-01 — Dos módulos: texto puro en `render.py`, flujos en `app.py`

- **Decisión**: `render.py` contiene funciones puras (`sanitize`, `bounded`, `render_event`, la tabla de categorías y las constantes); `app.py` contiene `attach_renderer` y `run_cli`, que son los únicos que tocan flujos y el bus.
- **Razón**: el árbol acordado ya prevé `render.py` («impresión de eventos») y `app.py` («entrada y comandos»); separar lo puro permite probar los formatos con eventos construidos a mano, sin flujos ni bus.
- **Alternativas**: un solo módulo (descartada: mezcla formato y E/S); una clase `Renderer` con estado (descartada: no hay estado que guardar).

## R-02 — Los eventos que se muestran y de dónde sale cada campo

- **Decisión**: se leen solo los campos que el bucle publica hoy: `TOOL_REQUESTED` (`name`), `TOOL_FINISHED` (`name`, `is_error`, `category`), `ASSISTANT_MESSAGE` (`content`), `PERMISSION_DECIDED` (`name`, `decision`, `reason`), `PROVIDER_ERROR` (`reason`, `error_type`, `message`) y `LIMIT_REACHED` (ninguno). Un campo ausente o de tipo inesperado nunca lanza: se usa un valor neutro («(sin nombre)», cadena vacía).
- **Razón**: decisión 4; el bucle (`core/loop.py`, funciones `_*_payload`) es la fuente. El evento de herramienta terminada no incluye el texto del error de la herramienta, así que la causa sale de la categoría.
- **Alternativas**: leer también `call_id` (descartada: no aporta al usuario); mostrar el texto del resultado de la herramienta (descartada: la carga no lo trae y exigiría ampliar el núcleo).

## R-03 — Formato de línea

- **Decisión**: siguiendo el prototipo: `... ejecutando: <nombre>` (progreso), `v <nombre>: correcto` (éxito), `x Error: <causa> Sugerencia: <acción>` (error), `> <texto>` por cada línea del mensaje del asistente. La decisión de permiso usa `x Permiso: <causa> Sugerencia: <acción>`; el límite, `x Límite: …`. Todo ASCII salvo el texto en español.
- **Razón**: el prototipo fija `...` y `x`; el resto se deriva de él. Evita símbolos (marcas de verificación) que la consola de Windows no siempre representa.
- **Alternativas**: iconos Unicode (descartada: sustitución en `cp1252`); colores (fuera de alcance).

## R-04 — Tabla de categorías (causa y sugerencia)

- **Decisión**: una constante inmutable con una entrada por categoría que el bucle publica hoy: `unknown_tool`, `invalid_arguments`, `permission_denied`, `approval_required_unavailable`, `tool_exception`, `invalid_tool_result` y `tool_error`, más los motivos del proveedor (`provider_exception`, `invalid_response`), la razón `policy_error` y el límite. Cada entrada tiene una causa con `{name}` y una sugerencia. Una categoría desconocida usa la entrada genérica con la sugerencia «Revisa el registro de eventos.» y **no** reproduce la categoría.
- **Razón**: decisión 5. Un valor desconocido podría venir de una versión futura del núcleo o de un dato corrupto; no se reproduce para no mostrar contenido sin saneado.
- **Alternativas**: mostrar la categoría tal cual (descartada: puede ser cualquier texto); una función de traducción con `if` (descartada: la tabla se puede revisar y probar entera).

## R-05 — Denegación informada una sola vez

- **Decisión**: la línea de `PERMISSION_DECIDED` (denegación o pregunta) lleva causa y sugerencia; el `TOOL_FINISHED` de las categorías `permission_denied` y `approval_required_unavailable` solo escribe `x <nombre>: no se ejecutó.`. Una decisión «permitir» no escribe nada.
- **Razón**: spec (FR-006); el bucle publica ambos eventos para la misma llamada y repetir la sugerencia duplicaría el aviso.
- **Alternativas**: mostrar solo el evento final (descartada: la decisión incluye el motivo `policy_error`); mostrar ambos completos (descartada: duplicado).

## R-06 — Saneado de texto y acotado

- **Decisión**: `sanitize(text)` elimina cada carácter de categoría Unicode `Cc` (controles de 7 y 8 bits, incluidos escape, nulo, retroceso, retorno de carro y suprimir) salvo salto de línea y tabulación, y los controles bidireccionales U+202A–U+202E y U+2066–U+2069. `bounded(text, limit)` recorta a `limit` caracteres y añade `...`. Los límites: nombre de herramienta 64, tipo de error 64, mensaje del proveedor 200, comando desconocido 40. El texto del asistente no se recorta.
- **Razón**: decisión 8 y 5. El saneado va **antes** del acotado para que un límite no parta una secuencia a medias. Los textos largos de un asistente son legítimos y el usuario los necesita completos.
- **Alternativas**: sustituir por `?` (descartada: ensucia el texto; se elimina); usar `repr` (descartada: muestra escapes).

## R-07 — Codificación segura en Windows y Linux

- **Decisión**: antes de escribir, cada texto se codifica con la codificación declarada del flujo (`getattr(stream, "encoding", None)`) y `errors="replace"` y se decodifica de vuelta; sin codificación declarada (p. ej. `io.StringIO`) se escribe tal cual. No se reconfigura `sys.stdout`.
- **Razón**: decisión 2; reconfigurar `sys.stdout` es un efecto global que afectaría a otros; esta técnica no tiene efectos laterales y es comprobable con un flujo `cp1252`.
- **Alternativas**: `sys.stdout.reconfigure(encoding="utf-8")` (descartada: global, y no siempre existe); forzar UTF-8 con una envoltura (descartada: la consola de Windows puede no mostrarlo).

## R-08 — Los fallos de escritura se propagan

- **Decisión**: los manejadores no tienen `try`; si `write` o `flush` lanzan, la excepción sube al bus, que la agrupa en `EventDeliveryError` (HU-01-05). La CLI no la oculta ni la convierte.
- **Razón**: decisión 7 y regla de negocio de HU-01-05 («los errores no se tragan»); el bucle (Q4) ya espera que `emit` propague.
- **Alternativas**: capturar y seguir (descartada: oculta un fallo); abortar el programa (descartada: decide la raíz de composición).

## R-09 — Ciclo de entrada

- **Decisión**: `async def run_cli(bus, run_turn, *, input_stream=None, output=None)`: suscribe el render, y en cada vuelta escribe el indicador `tarea> `, lee una línea con `readline()` (bloqueante), clasifica y actúa. Fin de entrada (`""`) y `/salir` terminan; línea vacía o solo espacios se ignora; `/ayuda` escribe la lista; un comando desconocido escribe el aviso; cualquier otra línea se entrega sin cambios (sin el salto de línea final) a `await run_turn(línea)`. Un comando es una línea cuya primera columna es «/»; se reconoce por su primera palabra.
- **Razón**: decisión 6; la lectura bloqueante es suficiente mientras nada más corra en el bucle (D5). La función de turno es una corrutina porque el bucle de A es asíncrono.
- **Alternativas**: `asyncio.to_thread(readline)` (descartada por ahora: complica los flujos en memoria y no aporta hasta HU-06-03); `input()` (descartada: no inyectable); comandos con espacios iniciales (descartada: ambigua con texto).

## R-10 — No se interpreta ni se valida la tarea

- **Decisión**: la línea de tarea se pasa sin recortar espacios internos ni inspeccionar su contenido; la CLI no limita su longitud.
- **Razón**: decisión 6 y regla de negocio 1 (la validación es del núcleo).
- **Alternativas**: recortar espacios (descartada: modifica la tarea); limitar longitud (descartada: es una regla del núcleo).

## R-11 — Fronteras verificadas por prueba

- **Decisión**: `tests/architecture/test_cli_boundaries.py` comprueba con `ast` que (a) ningún módulo de `core/` importa `harness_agent.cli` (absoluta o relativa), (b) los módulos de `cli/` solo importan biblioteca estándar, `harness_agent.cli.*` (relativos) y `harness_agent.core` (exactamente ese módulo, con nombres que existan en `harness_agent.core.__all__`), y (c) no importan adaptadores, observabilidad, raíz de composición ni `config`. Autoprueba con fragmentos y mutación sobre una copia.
- **Razón**: decisión 9; reutiliza el estilo de las pruebas de arquitectura existentes (`test_loop_boundaries.py`, `test_core_no_terminal.py`). La prueba de HU-01-05 ya garantiza que `core/` no use la terminal.
- **Alternativas**: `import-linter` (descartada: no es dependencia del proyecto).

## R-12 — Pruebas con el bucle real

- **Decisión**: `tests/integration/test_cli_agent_loop.py` usa `make_rig(script, tools, bus=InMemoryEventBus())`, `attach_renderer(bus, StringIO())` y un turno con una herramienta, uno con argumentos inválidos, uno con una herramienta no registrada, uno con permiso denegado, uno con error del proveedor y uno con excepción de la herramienta; y un `run_cli` con una entrada en memoria cuya función de turno ejecuta el bucle real.
- **Razón**: decisión 9; AC-01 y AC-02 se verifican con lo que el bucle emite de verdad, no con eventos inventados.
- **Alternativas**: solo eventos a mano (descartada: no detectaría un cambio del bucle).

## R-13 — Fallo del turno: una línea, sesión terminada y código de salida (D9)

- **Decisión**: `run_cli` envuelve `await run_turn(texto)` en un `try` que captura solo `Exception`; escribe la línea del contrato §3.4 (solo el nombre del tipo, saneado y acotado a 64 caracteres), termina el ciclo y devuelve `EXIT_FAILURE` (1). Una `BaseException` que no sea `Exception` (`CancelledError`, `KeyboardInterrupt`, `SystemExit`) no se captura. Si escribir la línea falla, ese fallo sube (queda encadenado a la causa original).
- **Razón**: decidida por el responsable. Evita que una traza llegue a la terminal (regla de negocio 2 y AC-02) sin ocultar el fallo: hay una línea visible y un código de salida distinto de cero (falla cerrada). Mostrar solo el tipo evita reproducir mensajes de excepción, que pueden contener datos del evento.
- **Alternativas**: dejar subir la excepción (descartada: traza en la terminal); seguir pidiendo tareas tras el fallo (descartada: falla cerrada); mostrar el mensaje de la excepción (descartada: puede contener datos).
