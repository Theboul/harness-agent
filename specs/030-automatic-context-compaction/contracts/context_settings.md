# Contrato: la sección `[context]` de `config.toml` y el umbral por modelo

## La sección (opcional)

```toml
[context]
window_tokens = 32000        # ventana de un modelo desconocido
threshold_percent = 80       # el umbral es este % de la ventana
recent_percent = 30          # la ventana reciente suma como mucho este % del umbral
min_recent_messages = 4      # y nunca menos de estos mensajes
summary_tokens = 2000        # tamaño pedido al resumen (tope: el doble)

[context.windows]            # ventana de cada modelo, por su nombre completo
"openai/gpt-4o" = 128000
```

Sin la sección rigen los valores por defecto de arriba. `config.example.toml` lleva la sección **comentada** con estos ejemplos (el valor de `[context.windows]` es un ejemplo, no una promesa del tamaño real de ese modelo).

## Campos y rangos

| Campo | Por defecto | Rango válido |
|---|---|---|
| `window_tokens` | 32000 | entero de 1000 a 10000000 |
| `windows` | vacío | tabla `"<proveedor>/<modelo>" = <entero de 1000 a 10000000>` |
| `threshold_percent` | 80 | entero de 10 a 95 |
| `recent_percent` | 30 | entero de 5 a 60 |
| `min_recent_messages` | 4 | entero de 1 a 50 |
| `summary_tokens` | 2000 | entero de 100 a 8000 |

Un booleano no es un entero. Un campo desconocido de `[context]` se rechaza como en las demás secciones.

## Errores (detienen el arranque)

Cada valor inválido genera un `ConfigProblem` con el **nombre** del campo y un mensaje fijo; **nunca** repite el valor recibido:

| Campo | Mensaje |
|---|---|
| `context.window_tokens` | `debe ser un entero entre 1000 y 10000000.` |
| `context.threshold_percent` | `debe ser un entero entre 10 y 95.` |
| `context.recent_percent` | `debe ser un entero entre 5 y 60.` |
| `context.min_recent_messages` | `debe ser un entero entre 1 y 50.` |
| `context.summary_tokens` | `debe ser un entero entre 100 y 8000.` |
| `context.windows` | `debe ser una tabla de modelo y tamaño de ventana (enteros entre 1000 y 10000000).` |
| `context` (no es una tabla) | `debe ser una tabla.` |

### Ejemplo normativo (E1)

`[context]` con `threshold_percent = 99` y `summary_tokens = "VALOR-DE-PRUEBA-123"` → el arranque se detiene con los problemas `context.threshold_percent` y `context.summary_tokens` (en el orden de los campos de la tabla) y ningún mensaje contiene `99` como valor recibido ni el centinela.

## El umbral por modelo

`threshold_tokens(settings, model) = settings.window_for(model) * threshold_percent // 100` y `recent_budget_tokens(settings, model) = threshold_tokens * recent_percent // 100`.

### Ejemplos normativos (E2)

| Configuración | Modelo | Ventana | Umbral | Presupuesto reciente |
|---|---|---|---|---|
| por defecto | `fake/test` (desconocido) | 32000 | 25600 | 7680 |
| `windows = {"openai/gpt-4o" = 128000}` | `openai/gpt-4o` | 128000 | 102400 | 30720 |
| `windows = {"openai/gpt-4o" = 128000}` | `fake/test` | 32000 | 25600 | 7680 |
| `window_tokens = 10000`, `threshold_percent = 50` | cualquiera | 10000 | 5000 | 1500 |

Si el modelo en uso cambia entre dos turnos, el umbral del turno siguiente es el del modelo nuevo (V-10); la conmutación en sí es de HU-07-05.
