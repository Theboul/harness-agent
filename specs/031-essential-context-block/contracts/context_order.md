# Contrato: el orden del contexto con el bloque esencial (actualiza el de HU-02-03)

## Orden

```text
1. los mensajes SYSTEM provisionales (las instrucciones: entorno, git y, si la tarea los declara, comandos)  ┐
2. el bloque esencial (un mensaje SYSTEM)                                                                    │ cabeza protegida
3. la petición inicial del usuario (primer USER no externo)                                                   ┘
4. el resumen (un solo USER externo, enmarcado), si lo hay
5. los mensajes recientes, íntegros y en su orden
```

Respecto del contrato de HU-02-03 solo se **añade** el punto 2. Los puntos 1 y 3 a 5 son los mismos. El bloque no es un mensaje real (`is_real` es falso para `SYSTEM`): no tiene evento y no cuenta en la correspondencia mensajes↔eventos.

## Qué cambia y qué no en la compactación (nada de su lógica)

| Pieza de HU-02-03 | Con el bloque |
|---|---|
| `split_history` | La cabeza son los `SYSTEM` iniciales contiguos (ahora uno más: el bloque) y el primer `USER` no externo. Sin cambios |
| `choose_cut` | Mira desde el final y nunca baja de `region_start`; el bloque está antes. Sin cambios |
| `rebuild_history` | Conserva `history[:region_start]` (menos un resumen anterior): el bloque sigue ahí, mismo objeto. Sin cambios |
| Entrada de la llamada de resumen | `history[region_start:cut]` y el resumen anterior: **nunca** el bloque. Sin cambios |
| Estimación del umbral | `estimate_messages(history)` incluye el bloque. Sin cambios |

## Ejemplos normativos (calculados a mano)

Sin comandos de la tarea; ventana reciente de 4 mensajes (como en los ejemplos de HU-02-03).

**E1 — primera compactación.** `H` = `[0 SYSTEM entorno, 1 SYSTEM git, 2 SYSTEM bloque, 3 USER petición, 4 ASSISTANT llamada c1, 5 TOOL c1, 6 ASSISTANT, 7 USER, 8 ASSISTANT, 9 USER, 10 ASSISTANT]` (11 mensajes).

- `split_history`: los `SYSTEM` iniciales son 0 a 2; la petición está en 3 → `head_end = 4`, sin resumen → `region_start = 4`.
- Corte deseado: `11 − 4 = 7`; `H[7]` es `USER`, no `TOOL` → corte 7.
- Región a resumir: `H[4:7]` = 4, 5 y 6 (3 mensajes: la llamada, su resultado y la respuesta).
- Contexto resultante: `[0, 1, 2, 3, S, 7, 8, 9, 10]` (9 mensajes). El bloque (2) sigue idéntico y en la misma posición.

**E2 — segunda compactación.** `H''` = `[0 SYSTEM entorno, 1 SYSTEM git, 2 SYSTEM bloque, 3 USER petición, 4 S, 5 USER, 6 ASSISTANT, 7 USER, 8 ASSISTANT, 9 USER, 10 ASSISTANT, 11 USER, 12 ASSISTANT]` (13 mensajes).

- `head_end = 4`; en 4 hay resumen → `region_start = 5`.
- Corte deseado: `13 − 4 = 9`; `H''[9]` es `USER` → corte 9.
- Región: `H''[5:9]` más el texto de `S` como resumen anterior.
- Resultado: `[0, 1, 2, 3, S', 9, 10, 11, 12]` (9 mensajes). El bloque no cambió.

**E3 — el criterio 1 pasa a cumplido entre dos peticiones.** Antes de la petición siguiente la composición renueva: `[0, 1, 2 BLOCK(v1), 3, S, …]` → `[0, 1, 2 BLOCK(v2), 3, S, …]`. Misma longitud; la compactación (si toca) corre **después** y ya ve el bloque v2.

**E4 — presupuesto (SC-008).** Ventana 2 000 tokens y umbral del 50 % → 1 000. El historial sin el bloque estima 900 (no compacta); el bloque E1 pesa 115 → con él el total es 1 015 > 1 000 → compacta. El bloque cabe en su parte: el 20 % de 1 000 es 200 ≥ 115.

**E5 — sesión sin tarea.** `[0 SYSTEM entorno, 1 SYSTEM git, 2 USER petición, …]` sin bloque: el contexto y la compactación son **exactamente** los de HU-02-03.

**E6 — con comandos de la tarea.** `[0 entorno, 1 git, 2 comandos, 3 BLOCK, 4 USER petición, …]`: `head_end = 5`; lo demás igual.

## Lo que el modelo recibe una sola vez

El texto de cada instrucción (entorno, git, comandos) llega **solo** como su mensaje `SYSTEM` provisional, y el bloque no lo repite. El registro de instrucciones del almacén no se inyecta. Comprobación: en la petición que recibe el proveedor simulado, cada uno de esos textos aparece exactamente una vez (SC-001).
