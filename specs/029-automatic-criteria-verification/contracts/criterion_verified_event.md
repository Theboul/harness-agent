# Contrato: el evento `criterion_verified`

El tipo ya existe en el catálogo de 17 eventos (`core/events.py`, sin uso hasta hoy); esta historia **no cambia el catálogo**, solo fija el contenido de su carga. Los campos se confirman con A, B y C (H1).

## Cuándo se publica

Una vez por **cada criterio de la tarea**, en el orden de la tarea, al final de cada verificación (incluidos los semánticos, con `pendiente_humano`). El último evento de la ronda lleva `criterion == total`. El evento se publica después de haber marcado `passes` (si procede); si la publicación falla, la excepción del bus se propaga (como en el bucle) y el criterio ya cumplido sigue cumplido.

## Carga (siete claves, en este orden)

| Clave | Tipo | Contenido |
|---|---|---|
| `criterion` | `int` | Posición del criterio, desde 1 |
| `total` | `int` | Número de criterios de la tarea |
| `description` | `str` | Descripción del criterio (texto de la tarea), en una línea, sin caracteres de control ni de formato, ≤ 120 caracteres |
| `status` | `str` | `cumplido`, `no_cumplido`, `regresion`, `no_ejecutado`, `tiempo_agotado`, `alterado` o `pendiente_humano` |
| `met` | `bool` | `true` solo con `cumplido` |
| `exit_code` | `int \| null` | Código de salida; `null` si no se ejecutó, hubo tiempo agotado o es un criterio semántico |
| `program` | `str \| null` | Nombre del programa del comando sin ruta (`pytest`); `null` si no hay comando o no es un nombre válido |

**Nunca** lleva: el comando ni sus argumentos, la salida, evidencia, credenciales, rutas o el motivo de un rechazo.

## Ejemplos normativos

```json
{"criterion": 1, "total": 3, "description": "El email es obligatorio", "status": "cumplido", "met": true, "exit_code": 0, "program": "pytest"}
{"criterion": 2, "total": 3, "description": "La contraseña tiene 8 caracteres", "status": "no_cumplido", "met": false, "exit_code": 1, "program": "pytest"}
{"criterion": 3, "total": 3, "description": "El mensaje de error es claro", "status": "pendiente_humano", "met": false, "exit_code": null, "program": null}
```

| Situación | `status` | `met` | `exit_code` |
|---|---|---|---|
| El comando cumple su condición | `cumplido` | `true` | el código |
| No cumple y no estaba cumplido | `no_cumplido` | `false` | el código |
| No cumple y ya había cumplido | `regresion` | `false` | el código |
| Política que deniega, pregunta sin aprobador o la persona rechaza | `no_ejecutado` | `false` | `null` |
| El proceso se terminó por tiempo | `tiempo_agotado` | `false` | `null` |
| Comando de SQLite distinto del de la definición, o la base alterada | `alterado` | `false` | `null` |
| Criterio sin comando | `pendiente_humano` | `false` | `null` |

## Prueba explícita de no filtración

Con valores centinela en el comando (`VALOR-DE-PRUEBA-123` en un argumento), en la salida del comando y en una credencial de URL de prueba (construida por partes), ninguna carga de `criterion_verified`, `approval_requested`, `approval_resolved`, `permission_decided` ni `criteria_tampered` de la verificación contiene el centinela del comando, de la salida ni la credencial; la descripción del criterio sí aparece (es texto de la tarea).

## Otros eventos de la verificación (formas existentes, sin cambios)

- `permission_decided`: `{call_id, name, decision, resolved_as, reason}` con `call_id = "verificacion-<n>"`, igual que el del bucle.
- `approval_requested` `{call_id, name, risk}` y `approval_resolved` `{call_id, name, action, approved, source}`.
- `criteria_tampered` `{"motivo": "comando_no_coincide" | "criterios_no_coinciden"}`; si el almacén lo detecta antes, ya publica el suyo.
