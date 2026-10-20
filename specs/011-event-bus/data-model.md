# Data Model: HU-01-05 — Bus de eventos desacoplado de la interfaz

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Contrato**: [contracts/event_bus_contract.md](contracts/event_bus_contract.md)

La historia no define ningún dato nuevo de dominio: reutiliza `Event` y `EventType` (`core/events.py`) y el puerto `EventBus` (`core/interfaces/event_bus.py`), que no se modifican. Este documento describe solo el estado interno del bus y su error.

## 1. Entidades reutilizadas (sin cambios)

| Entidad | Dónde | Uso en esta historia |
|---|---|---|
| `EventType` | `core/events.py` | Los 17 tipos; clave de suscripción (coincidencia por tipo exacto) |
| `Event` | `core/events.py` | Registro inmutable (`id`, `session_id`, `type`, `timestamp`, `payload`); el bus lo entrega tal cual, sin copiarlo |
| `EventBus` | `core/interfaces/event_bus.py` | Puerto con `emit(event)` y `subscribe(event_type, handler)`; el bus real lo implementa |
| `EventHandler` | `core/interfaces/event_bus.py` | `Callable[[Event], None]`; manejador síncrono |

## 2. `InMemoryEventBus` (`core/in_memory_event_bus.py`)

| Atributo | Tipo | Descripción |
|---|---|---|
| `_handlers` | `dict[EventType, tuple[EventHandler, ...]]` | Suscripciones por tipo, en el orden de suscripción. Cada `subscribe` sustituye la tupla del tipo por otra con el manejador añadido; ninguna tupla se modifica una vez creada |

**Invariantes**

- I-1: para un tipo, la tupla contiene una entrada por cada llamada a `subscribe`, repetida si el manejador se repite.
- I-2: una emisión lee la tupla de su tipo una sola vez al empezar; lo que se suscriba después no afecta a esa emisión.
- I-3: el bus no guarda eventos ni errores entre emisiones; un fallo no cambia `_handlers`.
- I-4: no hay operación para quitar suscripciones.

**Operaciones** (detalle en el [contrato](contracts/event_bus_contract.md))

| Operación | Entrada | Efecto | Errores |
|---|---|---|---|
| `subscribe(event_type, handler)` | `EventType`, invocable | Añade la suscripción al final de la tupla del tipo | `TypeError` en español si el tipo no es `EventType` o el manejador no es invocable; no registra nada |
| `emit(event)` | `Event` | Entrega el evento a la tupla del tipo, en orden y de forma síncrona; devuelve `None` | `TypeError` en español si no es un `Event` (no entrega nada); `EventDeliveryError` si fallan manejadores ordinarios (tras entregar a todos); cualquier `BaseException` no ordinaria se propaga de inmediato con una nota |

## 3. `EventDeliveryError` (`core/in_memory_event_bus.py`)

Subclase de `ExceptionGroup[Exception]` (por tanto de `Exception`).

| Elemento | Descripción |
|---|---|
| `message` | Frase en español: «Fallaron N manejadores al entregar el evento '<tipo>'.» (singular: «Falló 1 manejador …»). Sin la carga del evento |
| `exceptions` | Tupla con las excepciones ordinarias de los manejadores, en el orden de entrega (la misma instancia que lanzó cada manejador, sin envolver) |
| `derive(excs)` | Devuelve un `EventDeliveryError` con el mismo mensaje, para que `split` y `subgroup` conserven el tipo |

## 4. Flujo de una emisión

```text
emit(event)
  ├─ ¿event es un Event?  ── no → TypeError (nada se entrega)
  ├─ handlers = _handlers.get(event.type, ())      # lectura única (I-2)
  ├─ errors = []
  ├─ para cada handler en handlers (en orden):
  │     ├─ handler(event)
  │     ├─ except Exception  → errors.append(exc) y seguir
  │     └─ except BaseException → añadir nota con los fallos previos (si hay) y relanzar
  └─ si errors → raise EventDeliveryError(mensaje, errors)   # tras entregar a todos
```

Una entrega anidada es una llamada a `emit` hecha por un manejador: recorre su propio flujo completo antes de que continúe el manejador siguiente de la emisión externa. Si el anidado lanza `EventDeliveryError`, el manejador que lo emitió lo recibe como cualquier otra excepción: si no la captura, cuenta como un fallo de ese manejador.

## 5. Qué NO existe (fuera de alcance)

Cola de eventos, desuscripción, prioridades, comodines o filtros por varios tipos, entrega asíncrona, reintentos, bloqueo entre hilos, persistencia de eventos (HU-03-02) y suscriptor de producción (HU-06-01).
