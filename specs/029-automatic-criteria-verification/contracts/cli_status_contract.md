# Contrato: el estado de cada criterio en la CLI (AC-04)

## Qué se muestra y cuándo

- **Tras cada verificación**: una línea por criterio, a medida que llegan los eventos `criterion_verified`, y, al llegar el último (`criterion == total`), una línea final con el estado de la tarea.
- **Cuando la persona lo consulta**: el comando `/criterios` escribe el último estado de cada criterio de la sesión (la CLI lo guarda en memoria a partir de los eventos; no lee el almacén ni ejecuta nada) y la línea final. Sin ninguna verificación, escribe `Todavía no se ha verificado ningún criterio.`
- `/ayuda` añade la línea `  /criterios  Muestra el estado de los criterios.` **solo** cuando `run_cli` recibe ese comando extra (la composición lo pasa con tarea); sin él, el texto de `/ayuda` es el de siempre.

El texto sale **solo** de la carga del evento (contrato del evento): se sanea y se acota como el resto de la CLI (una línea, sin caracteres de control; descripción ≤ 80 caracteres). Muestra el código de salida y, como máximo, el nombre del programa; **nunca** los argumentos del comando (la CLI no los recibe).

## Formato de una línea

`<marca> <n> <descripción> (<detalle>)`

| Estado | Marca | Detalle |
|---|---|---|
| `cumplido` | `[x]` | `<programa>: salida <N>` (sin programa: `salida <N>`) |
| `no_cumplido` | `[ ]` | `<programa>: salida <N>` |
| `regresion` | `[ ]` | `regresión; <programa>: salida <N>` |
| `tiempo_agotado` | `[ ]` | `<programa>: tiempo agotado` |
| `no_ejecutado` | `[ ]` | `no ejecutado` |
| `alterado` | `[ ]` | `criterio alterado: no se ejecutó` |
| `pendiente_humano` | `[?]` | `pendiente de validación humana` |

## Línea final

`Tarea: <estado> (<x> de <y> criterios objetivos cumplidos)` con `<estado>` ∈ {`verificada`, `pendiente de validación humana`, `no terminada`} (de `task_state`); `<y>` cuenta los criterios que no son `pendiente_humano`.

## Ejemplos normativos

El prototipo de la ficha (con los dos primeros criterios ya verificados y el tercero semántico); el prototipo alinea el texto del criterio semántico con espacios, aquí va entre paréntesis para que todas las líneas tengan la misma forma:

```text
[x] 1 El email es obligatorio (pytest: salida 0)
[ ] 2 La contraseña tiene 8 caracteres (pytest: salida 1)
[?] 3 El mensaje de error es claro (pendiente de validación humana)
Tarea: no terminada (1 de 2 criterios objetivos cumplidos)
```

Con el segundo criterio ya corregido:

```text
[x] 1 El email es obligatorio (pytest: salida 0)
[x] 2 La contraseña tiene 8 caracteres (pytest: salida 0)
[?] 3 El mensaje de error es claro (pendiente de validación humana)
Tarea: pendiente de validación humana (2 de 2 criterios objetivos cumplidos)
```

Sin criterios semánticos y con todo cumplido: `Tarea: verificada (2 de 2 criterios objetivos cumplidos)`.

| Evento recibido | Línea |
|---|---|
| `status` `regresion`, `exit_code` 2, `program` `pytest` | `[ ] 4 El correo se normaliza (regresión; pytest: salida 2)` |
| `tiempo_agotado`, `program` `pytest` | `[ ] 2 Compila (pytest: tiempo agotado)` |
| `no_ejecutado` | `[ ] 5 Compila sin avisos (no ejecutado)` |
| `alterado` | `[ ] 5 Compila sin avisos (criterio alterado: no se ejecutó)` |
| `cumplido` sin `program`, `exit_code` 0 | `[x] 1 Algo (salida 0)` |
| carga con campos que faltan o de otro tipo | el neutro: `[ ] ? (no ejecutado)`; nunca una excepción ni el volcado de la carga |
| descripción con una secuencia de escape y U+202E (escrito con `chr`) | la línea sin esos caracteres |

## Qué cambia en `cli/` (área C; visto bueno en H2)

- `cli/criteria.py` (nuevo): `criterion_line(payload)`, `CriteriaBoard` (`update(payload)`, `lines()`, `summary_line()`, `report()`) y `attach_criteria_status(bus, output)`, que se suscribe a `criterion_verified` (solo a ese tipo), actualiza el tablero, escribe la línea del criterio y, tras el último (`criterion == total`), la línea final. Devuelve el tablero.
- `cli/__init__.py`: exporta `CriteriaBoard` y `attach_criteria_status`.
- `cli/app.py`: `run_cli(..., commands=None)`; `commands` es un `Mapping[str, tuple[str, Callable[[], str]]]` (descripción, función que devuelve el texto). Un comando de la tabla escribe su texto; `/ayuda` añade su línea. Sin `commands`, nada cambia.
- **No cambian**: `cli/render.py`, `SHOWN_TYPES` (siguen siendo 6 tipos), `attach_renderer`, `HELP_TEXT`.
