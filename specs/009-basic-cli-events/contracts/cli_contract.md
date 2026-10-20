# Contrato: CLI básica con eventos en tiempo real (HU-06-01)

**Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md) · **Modelo**: [../data-model.md](../data-model.md)

Este contrato describe la API pública de `harness_agent.cli` y los textos exactos que muestra. **No se escribe código aquí.** `<nombre>` es el nombre de la herramienta de la carga, saneado y acotado a 64 caracteres (`(sin nombre)` si falta); `{texto}` es siempre texto saneado.

## 1. API pública (`harness_agent.cli`)

```text
render_event(event: Event) -> str | None
attach_renderer(bus: EventBus, output: TextIO | None = None) -> None
async run_cli(bus: EventBus, run_turn: Callable[[str], Awaitable[object]], *,
              input_stream: TextIO | None = None, output: TextIO | None = None) -> int
```

- `output` y `input_stream` valen `sys.stdout` y `sys.stdin` por defecto (se resuelven en la llamada, no al importar).
- `attach_renderer` suscribe un manejador por cada tipo de `SHOWN_TYPES`; el bus no tiene desuscripción, así que llamarla dos veces con el mismo bus duplica la salida.
- `run_cli` llama a `attach_renderer` al empezar y devuelve el **código de salida**: `0` (`EXIT_OK`) si termina limpio (`/salir` o fin de la entrada) y `1` (`EXIT_FAILURE`) si la función de turno lanza una `Exception` ordinaria (§3.4). La firma de retorno cambió de `None` a `int` por la decisión D9.
- La CLI solo importa biblioteca estándar y nombres de `harness_agent.core.__all__`.

## 2. Líneas de salida por evento

| Evento | Condición | Línea |
|---|---|---|
| `TOOL_REQUESTED` | siempre | `... ejecutando: <nombre>` |
| `TOOL_FINISHED` | `is_error` es `False` | `v <nombre>: correcto` |
| `TOOL_FINISHED` | `is_error` es `True`, categoría `permission_denied` o `approval_required_unavailable` | `x <nombre>: no se ejecutó.` |
| `TOOL_FINISHED` | `is_error` es `True`, categoría conocida (§3.1) | `x Error: <causa> Sugerencia: <sugerencia>` |
| `TOOL_FINISHED` | `is_error` es `True`, categoría desconocida, o `is_error` ausente o no booleano | `x Error: Ocurrió un error de categoría desconocida en la herramienta '<nombre>'. Sugerencia: Revisa el registro de eventos.` |
| `ASSISTANT_MESSAGE` | `content` con texto | cada línea del texto, precedida de `> ` |
| `PERMISSION_DECIDED` | `decision` = `allow` | nada |
| `PERMISSION_DECIDED` | `deny`, `ask` o desconocida | `x Permiso: <causa> Sugerencia: <sugerencia>` (§3.2) |
| `PROVIDER_ERROR` | siempre | `x Error: <causa> Sugerencia: <sugerencia>` (§3.3) |
| `LIMIT_REACHED` | siempre | `x Límite: Se alcanzó un límite de la sesión. Sugerencia: Revisa los límites en la configuración y empieza una tarea nueva.` |
| cualquier otro tipo | — | nada (`render_event` devuelve `None`) |

Cada línea termina con un salto de línea al escribirse. Los mensajes del asistente vacíos o solo con espacios no escriben nada. Ningún formato incluye argumentos de la herramienta, la carga cruda ni la categoría desconocida.

## 3. Causas y sugerencias (tabla de categorías)

### 3.1 Errores de herramienta (`TOOL_FINISHED`)

| Categoría | Causa | Sugerencia |
|---|---|---|
| `unknown_tool` | La herramienta '<nombre>' no está registrada. | Revisa el nombre de la herramienta o regístrala antes de volver a intentarlo. |
| `invalid_arguments` | Los argumentos de la herramienta '<nombre>' no son válidos. | Corrige los argumentos según el esquema de la herramienta y vuelve a intentarlo. |
| `tool_exception` | La herramienta '<nombre>' falló al ejecutarse. | Vuelve a intentarlo y, si se repite, revisa el registro de eventos. |
| `invalid_tool_result` | La herramienta '<nombre>' devolvió un resultado no válido. | Revisa la implementación de la herramienta y el registro de eventos. |
| `tool_error` | La herramienta '<nombre>' terminó con un error. | Revisa los datos de la llamada y vuelve a intentarlo; el detalle está en el historial de la sesión. |
| otra | Ocurrió un error de categoría desconocida en la herramienta '<nombre>'. | Revisa el registro de eventos. |

### 3.2 Decisiones de permiso (`PERMISSION_DECIDED`)

| Caso | Causa | Sugerencia |
|---|---|---|
| `deny` sin `reason` | La herramienta '<nombre>' fue denegada por la política de permisos. | Si debe permitirse, ajusta la política de permisos; mientras esté denegada el agente no la ejecutará. |
| `deny` con `reason` = `policy_error` | No se pudo evaluar la política de permisos para '<nombre>'; se denegó por seguridad. | Revisa la política de permisos configurada. |
| `ask` | La herramienta '<nombre>' requiere aprobación, que no está disponible en esta sesión; se resolvió como denegada. | Pide una acción que no requiera aprobación o espera a que esté disponible la aprobación interactiva. |
| otra decisión | Se recibió una decisión de permiso desconocida para '<nombre>'. | Revisa el registro de eventos. |

### 3.3 Error del proveedor (`PROVIDER_ERROR`)

`<tipo>` es `error_type` saneado y acotado a 64 caracteres (`Error` si falta); `<mensaje>` es `message` saneado, en una sola línea (los espacios y saltos de línea se reducen a un espacio) y acotado a 200 caracteres, con un punto final si no termina en `.`, `!` o `?`.

| `reason` | Causa | Sugerencia |
|---|---|---|
| `provider_exception` | El proveedor del modelo falló (<tipo>): <mensaje> | Comprueba la conexión y la clave del proveedor y vuelve a intentarlo. |
| `provider_exception` sin mensaje (ausente, vacío o que no es texto) | El proveedor del modelo falló (<tipo>). | Comprueba la conexión y la clave del proveedor y vuelve a intentarlo. |
| `invalid_response` | El proveedor del modelo devolvió una respuesta no válida (<tipo>). | Vuelve a intentarlo y, si se repite, revisa el registro de eventos. |
| otra o ausente | El proveedor del modelo falló (<tipo>). | Revisa el registro de eventos. |

### 3.4 Fallo del turno (`run_cli`)

`x Error: el turno terminó con un fallo interno (<TipoDeError>). Sugerencia: revisa el registro de eventos.` donde `<TipoDeError>` es el nombre de la clase de la excepción (`type(error).__name__`), saneado y acotado a 64 caracteres. La línea **no** incluye el mensaje de la excepción, ni la traza, ni la carga de ningún evento. Se escribe una sola vez y la sesión termina con código `1`.

## 4. Saneado y acotado

- `sanitize` elimina todo carácter de categoría Unicode `Cc` salvo `\n` y `\t` (escape, nulo, retroceso, retorno de carro, suprimir y los controles de 8 bits) y los controles bidireccionales U+202A a U+202E y U+2066 a U+2069. Se aplica a **todo** texto que viene de una carga o de la entrada del usuario antes de mostrarse.
- `bounded(texto, límite)` recorta a `límite` caracteres con `...` al final; se aplica después del saneado.
- La salida no contiene colores ni secuencias ANSI. Antes de escribir, el texto se adapta a la codificación declarada del flujo con sustitución (`errors="replace"`) sin modificar el flujo.

## 5. Entrada

- Indicador de entrada: `tarea> ` (se escribe y se vacía el búfer antes de cada lectura).
- Clasificación (data-model §4): fin de entrada (`readline()` devuelve `""`), vacía, comando y tarea. Un comando es una línea con `/` en la primera columna; se reconoce por su primera palabra, sin distinguir argumentos.
- `/ayuda` escribe:
  ```text
  Comandos disponibles:
    /ayuda  Muestra esta ayuda.
    /salir  Termina la sesión.
  Cualquier otra línea se envía al agente como una tarea nueva.
  ```
- `/salir` escribe `Sesión terminada.` y termina el ciclo; el fin de la entrada escribe un salto de línea y termina el ciclo.
- Comando desconocido: `Comando desconocido: '<comando>'. Escribe /ayuda para ver los comandos disponibles.` (`<comando>` es la primera palabra, saneada y acotada a 40 caracteres); no se ejecuta nada.
- Una tarea se entrega a `await run_turn(texto)` sin el salto de línea final, sin otro cambio y una sola vez; la CLI no la interpreta ni la valida ni limita su longitud.

## 6. Errores y propagación

| Situación | Resultado |
|---|---|
| Falla `write` o `flush` de la salida dentro de un manejador | La excepción sube al bus, que la agrupa en `EventDeliveryError`; la CLI no la captura |
| Falla `write` o `flush` fuera de un manejador (indicador, ayuda) | La excepción sube a quien llamó a `run_cli` |
| `run_turn` lanza una `Exception` (incluido `EventDeliveryError`) | `run_cli` escribe la línea de §3.4, termina la sesión y devuelve `1` |
| `run_turn` lanza una `BaseException` que no es `Exception` (`CancelledError`, `KeyboardInterrupt`, `SystemExit`…) | Sube sin tocar a quien llamó a `run_cli` |
| Falla la escritura de la línea de §3.4 | Esa excepción sube a quien llamó a `run_cli` (no se traga; la original queda como contexto) |
| Carga con campos ausentes o de tipo inesperado | Nunca lanza; usa valores neutros (data-model §3) |

## 7. Comprobaciones de arquitectura asociadas

| Prueba | Falla si… |
|---|---|
| `tests/architecture/test_cli_boundaries.py` | un módulo de `core/` importa `harness_agent.cli` (absoluta o relativa); un módulo de `cli/` importa algo que no sea biblioteca estándar, `harness_agent.cli.*` o `harness_agent.core` (solo con nombres de `harness_agent.core.__all__`); o `cli/` importa `adapters`, `observability`, `bootstrap` o `config` |
| `tests/architecture/test_core_no_terminal.py` (HU-01-05, existente) | el núcleo imprime o usa la terminal; sigue valiendo sin cambios |

## 8. Uso previsto por el consumidor

1. La raíz de composición construye el bus, el bucle y el proveedor, define `run_turn` (que llama a `AgentLoop.run_turn` con la sesión y el historial) y termina con `sys.exit(asyncio.run(run_cli(bus, run_turn)))`: el código de salida de `run_cli` (0 limpio, 1 si el turno falló) es el del proceso.
2. Quien necesite solo el render (por ejemplo, una prueba) llama a `attach_renderer(bus, output)`.
3. La CLI nunca decide: todo lo que muestra es lo que el núcleo publicó.
