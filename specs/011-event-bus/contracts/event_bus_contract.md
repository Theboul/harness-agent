# Contrato: bus de eventos en memoria (HU-01-05)

**Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md) · **Modelo**: [../data-model.md](../data-model.md)

Este contrato describe `InMemoryEventBus` y `EventDeliveryError` (`harness_agent.core.in_memory_event_bus`, reexportados por `harness_agent.core`) y las cláusulas que verifica el contrato de pruebas único. **No se escribe código aquí**: las firmas son las del puerto existente. El puerto, el catálogo y el doble no se modifican.

## 1. Superficie pública

```text
class InMemoryEventBus(EventBus):
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None
    def emit(self, event: Event) -> None

class EventDeliveryError(ExceptionGroup[Exception])      # sin atributos propios
```

Sin constructor con parámetros: un bus nuevo no tiene suscriptores. Sin desuscripción. Los manejadores son funciones síncronas `Callable[[Event], None]`; un valor devuelto se ignora y una corrutina devuelta no se espera.

## 2. Semántica de la entrega

1. **Síncrona y en orden**: `emit` entrega a cada manejador del tipo del evento, en el orden de suscripción, antes de volver.
2. **Tipo exacto**: solo reciben el evento los manejadores suscritos a `event.type`.
3. **El mismo objeto**: cada manejador recibe el `Event` emitido, sin copiarlo.
4. **Sin suscriptores**: no es un error; `emit` devuelve `None`.
5. **Repeticiones**: suscribir el mismo manejador N veces al mismo tipo da N entregas.
6. **Copia al empezar**: los manejadores suscritos durante una entrega solo reciben eventos posteriores.
7. **Entrega anidada**: un manejador que emite otro evento provoca su entrega completa, inmediata y síncrona (sin cola), antes de que se llame al siguiente manejador de la emisión externa.
8. **Un solo hilo**: el bus no es seguro entre hilos.

## 3. Fallos

| Situación | Resultado |
|---|---|
| Un manejador lanza una `Exception` | La entrega sigue con los demás; al terminar, `emit` lanza `EventDeliveryError` con todas las excepciones en el orden de entrega (las instancias originales) |
| Ningún manejador falla | `emit` termina sin error |
| Un manejador lanza una `BaseException` que no es `Exception` (cancelación, interrupción de teclado) | Se propaga **de inmediato y sin agrupar**; los manejadores restantes no reciben el evento; si hubo fallos ordinarios antes, se anotan en la excepción con `add_note` (tipos y número, sin contenido del evento) |
| Un manejador anidado provoca `EventDeliveryError` | El manejador que emitió lo recibe como una excepción más |
| Tras un fallo | El bus sigue funcionando; las suscripciones no cambian |

**Mensajes** (en español, sin la carga del evento):

- `EventDeliveryError`: «Fallaron N manejadores al entregar el evento '<tipo>'.»; con N = 1: «Falló 1 manejador al entregar el evento '<tipo>'.».
- Nota de una excepción no ordinaria con fallos previos: «Antes fallaron N manejadores (<Tipo1>, <Tipo2>) al entregar el evento '<tipo>'; los manejadores restantes no lo recibieron.»; con N = 1: «Antes falló 1 manejador (<Tipo1>) al entregar el evento '<tipo>'; los manejadores restantes no lo recibieron.»

## 4. Validación

| Llamada | Condición | Resultado |
|---|---|---|
| `subscribe` | `event_type` no es una instancia de `EventType` (incluida una cadena con el valor de un tipo) | `TypeError`: «El tipo de evento debe ser un EventType del catálogo, no '<tipo recibido>'.» |
| `subscribe` | `handler` no es invocable | `TypeError`: «El manejador debe ser invocable, no '<tipo recibido>'.» |
| `emit` | lo recibido no es un `Event` | `TypeError`: «Solo se pueden emitir objetos Event, no '<tipo recibido>'.» |

El tipo del evento se comprueba antes que el manejador. Una llamada inválida no registra ni entrega nada. Los mensajes nombran el tipo de lo recibido (`str`, `int`), nunca su valor.

## 5. Cláusulas del contrato de pruebas y a quién aplican

El archivo `tests/contracts/test_event_bus_contract.py` ejecuta las cláusulas comunes contra `RecordingEventBus` y contra `InMemoryEventBus`, y las propias del bus real solo contra este.

| Cláusula | Descripción | Doble (`RecordingEventBus`) | Bus real |
|---|---|:---:|:---:|
| C-1 | El suscriptor del tipo recibe el mismo evento, una vez | Sí | Sí |
| C-2 | Varios suscriptores reciben en orden de suscripción | Sí | Sí |
| C-3 | Solo reciben los suscriptores del tipo exacto | Sí | Sí |
| C-4 | Un tipo sin suscriptores no es un error y `emit` devuelve `None` | Sí | Sí |
| C-5 | El mismo manejador suscrito N veces recibe N entregas | Sí | Sí |
| C-6 | Los 17 tipos del catálogo se entregan | Sí | Sí |
| C-7 | La entrega anidada es inmediata y completa antes del siguiente manejador | Sí | Sí |
| C-8 | Los manejadores de un tipo no reciben eventos de otros tipos emitidos en una entrega anidada | Sí | Sí |
| C-9 | Un manejador suscrito durante una entrega solo recibe eventos posteriores | No (itera su lista viva) | Sí |
| C-10 | Un manejador que falla no impide la entrega a los demás y `emit` lanza `EventDeliveryError` con todos los errores en orden | No (el primer error corta la entrega) | Sí |
| C-11 | Una `BaseException` no ordinaria se propaga de inmediato, sin agrupar, con la nota de los fallos previos | No | Sí |
| C-12 | Tras un fallo, el bus sigue entregando con normalidad | No | Sí |
| C-13 | `subscribe` rechaza tipo no `EventType` y manejador no invocable con `TypeError` en español | No (no valida) | Sí |
| C-14 | `emit` rechaza lo que no es `Event` con `TypeError` en español sin entregar nada | No | Sí |
| C-15 | Ningún mensaje de error reproduce la carga del evento (centinela) | No | Sí |

Una cláusula marcada «No» para el doble no es un defecto del doble: es una propiedad propia de la implementación real, y el doble no se modifica (Principio de no tocar `tests/doubles/`).

## 6. Comprobaciones de arquitectura asociadas

| Prueba | Falla si… |
|---|---|
| `tests/architecture/test_core_no_terminal.py` (AC-02) | un módulo de `core/` llama a `print` o `input`, usa `sys.stdout`/`stderr`/`stdin` (también con alias o `from sys import …`) o importa una biblioteca de terminal; o `in_memory_event_bus.py` importa algo que no sea biblioteca estándar o `harness_agent.core`, o define un tipo de evento |
| `tests/architecture/test_core_boundaries.py` y `test_loop_boundaries.py` (existentes) | se importan SDK de proveedores o, en el bucle, consola; siguen valiendo sin cambios |

## 7. Uso previsto por el consumidor

1. La raíz de composición crea un `InMemoryEventBus` y se lo pasa al bucle (`AgentLoop(provider, registry, policy, bus)`) y a los suscriptores.
2. Cada interfaz o servicio (la CLI de HU-06-01, el almacén de HU-03-02) llama a `subscribe` por cada tipo que le interesa.
3. Quien llama a `run_turn` recibe, sin cambios, cualquier `EventDeliveryError` de un suscriptor que falle (Q4); un suscriptor que no deba afectar al turno debe capturar sus propios errores.
4. El núcleo nunca imprime: toda salida es un evento.
