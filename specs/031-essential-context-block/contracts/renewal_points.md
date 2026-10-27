# Contrato: los puntos de renovación del bloque

## Quién renueva

**Solo la composición** (`bootstrap.py`), con el `EssentialRenewer` que monta `compose()` cuando hay tarea. Ni el bucle, ni el verificador, ni la CLI, ni el compactador lo llaman: una guarda de arquitectura lo vigila (T010). `core/loop.py`, `core/verification/`, `core/interfaces/` y el catálogo de eventos **no cambian**.

## Cuándo

| # | Punto | Dónde está | Qué hace |
|---|---|---|---|
| 1 | Al empezar cada petición de la persona | `run_session`, al principio de la función que entrega la petición, **antes** de la compactación | `renew(history)` |
| 2 | Antes de cada ronda de verificación (incluida la primera) | La función `run_turn(text, history)` que `_verifying_runner` entrega al `VerifyingRunner`, justo antes de llamar al bucle | `renew(history)` |

No hay un tercer punto: **dentro** de una ronda el bucle hace sus llamadas al modelo sin que la composición intervenga. Esa es la **limitación conocida** de Q1 = A (igual que la compactación de HU-02-03); un único gancho futuro en el bucle, con el acuerdo de A, la resolvería para las dos (H1).

Una sesión **sin tarea** no tiene renovador: `Composition.essential` es `None` y los dos puntos no hacen nada (el contexto es el de hoy). Una sesión **con tarea** siempre lo tiene, y si le faltan elementos **falla cerrada**; nunca se confunde con la anterior.

## Orden dentro de una petición

```text
run_session.run_turn(petición)
 ├─ 1. renew(history)                       # bloque vigente (INSERTED la primera vez, luego UNCHANGED o REPLACED)
 ├─ 2. compactor.before_turn(history)       # su estimación ya incluye el bloque
 └─ 3. runner.run(petición, history)
        ├─ ronda 1: renew(history) → UNCHANGED → loop.run_turn(…)   # n llamadas al modelo, todas con el mismo bloque
        ├─ verificador: marca criterios (el almacén cambia)
        └─ ronda 2: renew(history) → REPLACED (criterio cumplido) → loop.run_turn(…)
```

Con dos rondas hay tres renovaciones; solo cambia el texto cuando una fuente cambió.

## Cuándo cambia de verdad el texto

| Cambio en la fuente | Se ve en |
|---|---|
| Un criterio pasa a cumplido (lo marca el verificador tras una ronda) | La ronda siguiente o la petición siguiente, lo que ocurra antes |
| Un criterio pasa a cumplido durante una misma ronda | **No** se ve hasta el siguiente punto (limitación conocida) |
| El modelo en uso cambia a uno de ventana más pequeña | La siguiente renovación vuelve a comprobar el tope del 20 % del umbral nuevo |
| Cambia el valor de un elemento guardado | Ninguna ruta del producto lo cambia (escritura única); si una historia futura lo permitiera, se vería en el siguiente punto |

## Fallos (siempre cerrados; la petición no llega al modelo)

| Fallo | Error de dominio | Qué ve la persona | Evento |
|---|---|---|---|
| Un elemento supera 8 000 caracteres, o el bloque supera el 20 % del umbral del modelo en uso | `EssentialContextTooLarge` | `El elemento «<elemento>» del contexto esencial supera el tope de <N> <caracteres\|tokens>.` (R16) | Ninguno |
| La fuente de elementos o de criterios no se puede leer, o el sello de los criterios no coincide | `EssentialContextUnavailable(missing=False)` | `No se pudo leer el contexto esencial de la tarea; la petición no se envía.` | El que ya existía (`criteria_tampered`, solo el motivo); ninguno nuevo |
| **Con tarea**, faltan `objetivo`, `criterios_ref` o toda `instrucciones` (el segundo guardado falló, se borraron filas) | `EssentialContextUnavailable(missing=True)` | `Faltan elementos del contexto esencial de la tarea; la petición no se envía.` | Ninguno |
| Cancelación (`CancelledError`) durante la petición | Se propaga | — | — |

La composición escribe el mensaje fijo por el `WarningSink` y **relanza** la excepción; `run_cli` la convierte en una línea con el nombre del tipo y el código de salida 1 (comportamiento existente ante un turno que falla). Los mensajes nunca incluyen valores del bloque, texto de criterios ni la excepción original.
