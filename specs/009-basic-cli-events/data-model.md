# Data Model: HU-06-01 — CLI básica con eventos en tiempo real

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Contrato**: [contracts/cli_contract.md](contracts/cli_contract.md)

La historia no define datos de dominio: la CLI no guarda nada y consume `Event` y `EventType` (sin cambios). Este documento describe los pequeños valores internos de `cli/`.

## 1. Constantes (`cli/render.py`)

| Constante | Valor | Uso |
|---|---|---|
| `MAX_NAME_CHARS` | 64 | Nombre de herramienta y tipo de error mostrados |
| `MAX_PROVIDER_MESSAGE_CHARS` | 200 | Mensaje del proveedor mostrado |
| `MAX_COMMAND_CHARS` | 40 | Comando desconocido repetido en el aviso |
| `ELLIPSIS` | `"..."` | Marca de recorte (ASCII, como el bucle) |
| `UNKNOWN_NAME` | `"(sin nombre)"` | Nombre cuando la carga no lo trae |
| `SHOWN_TYPES` | `TOOL_REQUESTED`, `TOOL_FINISHED`, `ASSISTANT_MESSAGE`, `PERMISSION_DECIDED`, `PROVIDER_ERROR`, `LIMIT_REACHED` | Tipos a los que se suscribe la CLI |

Constantes de `cli/app.py`: `PROMPT = "tarea> "`, `EXIT_OK = 0` y `EXIT_FAILURE = 1`.

## 2. Entrada de la tabla de categorías (`ErrorGuide`)

Valor inmutable con dos textos con el marcador `{name}` opcional:

| Campo | Tipo | Descripción |
|---|---|---|
| `cause` | `str` | Frase completa en español que dice qué falló; termina en punto |
| `suggestion` | `str` | Frase completa en español con la acción sugerida; termina en punto |

La tabla `TOOL_ERROR_GUIDE` (`Mapping[str, ErrorGuide]`, inmutable) tiene una entrada por categoría de error de herramienta que el bucle publica hoy: `unknown_tool`, `invalid_arguments`, `tool_exception`, `invalid_tool_result`, `tool_error`. Las categorías `permission_denied` y `approval_required_unavailable` no tienen entrada de error en `TOOL_FINISHED` (R-05, solo «no se ejecutó»); su causa y sugerencia están en la tabla de decisiones de permiso (`PERMISSION_GUIDE`: `deny`, `policy_error`, `ask`). Hay además `PROVIDER_GUIDE` (`provider_exception`, `invalid_response`), una entrada fija para el límite y una entrada genérica para lo desconocido. Los textos exactos están en el [contrato](contracts/cli_contract.md) §3.

**Reglas**

- R-1: toda categoría que el bucle publica hoy tiene entrada o tratamiento explícito (probado contra una lista fija de categorías).
- R-2: una categoría, razón o decisión desconocida usa la entrada genérica y **nunca** se reproduce en la salida.
- R-3: `{name}` se sustituye por el nombre saneado y acotado a `MAX_NAME_CHARS`.

## 3. Funciones puras de `render.py`

| Función | Entrada | Salida |
|---|---|---|
| `sanitize(text)` | `str` | El mismo texto sin caracteres de control (salvo `\n` y `\t`) ni controles bidireccionales |
| `bounded(text, limit)` | `str`, `int` | El texto, o sus primeros `limit - 3` caracteres más `...` si lo supera |
| `render_event(event)` | `Event` | Texto de una o varias líneas (sin salto final) o `None` si el tipo no se muestra o no hay nada que mostrar |

`render_event` nunca lanza por una carga incompleta o de tipo inesperado: usa valores neutros.

## 4. Clasificación de una línea de entrada (`app.py`)

| Línea leída | Clase | Efecto |
|---|---|---|
| `""` (fin de entrada) | Fin | Termina limpio |
| solo espacios o `\n` | Vacía | Se ignora |
| empieza por `/` en la primera columna, primera palabra `/ayuda` | Comando | Escribe la ayuda |
| primera palabra `/salir` | Comando | Escribe el aviso de salida y termina limpio |
| empieza por `/`, otra palabra | Comando desconocido | Escribe el aviso; no ejecuta nada |
| cualquier otra | Tarea | `await run_turn(línea sin el salto final)` una sola vez |

## 5. Flujo del ciclo

```text
attach_renderer(bus, output)           # una vez
repeat:
  write PROMPT; flush
  line = input.readline()
  if line == "": write newline; stop            # fin de entrada
  text = line without the final line break
  if text.strip() == "": continue
  if text starts with "/": handle command (stop on /salir)
  else:
    try: await run_turn(text)
    except Exception as error:                  # D9: solo las ordinarias
      write the one-line failure (type name only); return EXIT_FAILURE
    # BaseException (cancelación, Ctrl+C...) y el fallo de escribir esa línea suben sin tocar
return EXIT_OK                                  # /salir o fin de la entrada
```

## 6. Qué NO existe (fuera de alcance)

Colores, historial, sesiones, aprobación interactiva, cancelación, punto de entrada ejecutable, lectura de configuración, construcción del bucle o del proveedor, desuscripción y ampliación de la carga de los eventos.
