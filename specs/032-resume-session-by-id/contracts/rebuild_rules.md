# Contrato: reconstrucción del contexto al reanudar (`resume_session` y `rebuild_conversation`)

Funciones puras de `core/context/resume.py` (solo biblioteca estándar y núcleo). `resume_session(source, text, *, prefix, current_model, current_session_id, known_incomplete=frozenset())` valida el identificador, aplica los rechazos que no necesitan leer, pide la sesión a una `ResumeSource`, aplica el resto y llama a `rebuild_conversation(prefix, stored, current_model)`.

## Orden del resultado (igual al de HU-02-03)

```
[ prefijo (SYSTEM…), petición inicial, resumen vigente (si lo hay), filas NO cubiertas… , cierres sintéticos (si los hay) ]
```

- Sin resumen vigente: `[ prefijo, todas las filas…, cierres sintéticos ]`.
- El resumen es `frame_summary(texto)` de HU-02-03 (`USER` externo con el encabezado fijo); es **el mismo mensaje** que tenía la vista viva.
- Los mensajes de las filas se rehacen con los mismos tipos del núcleo (`Message`, `ToolCall`, `ToolResult`, `TokenUsage`): rol, contenido, llamadas con argumentos, resultado, `is_external`, `usage`.

## Algoritmo

1. **Identificador** (`check_session_id`): vacío → `InvalidSessionId` (uso); más de 128 caracteres o fuera de `[A-Za-z0-9._-]` → `InvalidSessionId`. No se consulta nada antes.
1b. Es `current_session_id` → `AlreadyCurrentSession` (sin leer ni escribir). Está en `known_incomplete` (su guardado falló en esta ejecución) → `SessionDetailMissing`, sin leer.
2. `source.load_conversation(id)`: `None` → `UnknownSession`.
3. `stored.is_task` → `TaskSessionNotResumable`.
4. `stored.events_without_row > 0` → `SessionDetailMissing`.
5. Sin filas y sin resumen → sesión **vacía**: historial = prefijo, `empty = True`.
6. Primera fila: `USER`, no externo, no cubierta (si no → `ConversationInconsistent`).
7. **Cobertura** (R3): con evento → `covered`; sin evento → la de la siguiente fila con evento; si no hay siguiente, no cubierta. Las cubiertas deben ser una racha contigua justo tras la fila 1; deben existir si y solo si hay resumen (si no → `ConversationInconsistent`).
8. Armar el historial (orden de arriba).
9. **Cierre de llamadas** (solo la cola): para cada `ASSISTANT` con llamadas cuya lista de resultados no está completa y que está **al final** del historial (o seguido solo de sus resultados), añadir al final, en el orden de las llamadas, un `TOOL` sintético por cada llamada sin resultado (texto fijo, `is_error`, no externo). Una llamada sin resultado **en medio** (seguida de un mensaje que no es su resultado) → `ConversationInconsistent`.
10. **Estructura** (`check_structure`, réplica de la validación del bucle): `SYSTEM` solo al principio, identificadores de llamada no vacíos y únicos, cada grupo contestado antes de cualquier otro mensaje, ningún resultado sin llamada → si falla, `ConversationInconsistent`.
11. `cut_off = hay cierres o stored.last_event_type == "interrupted"`; `model_changed = stored.model not in (None, current_model)`.
12. `next_position = última posición + 1` (no hace falta consultar: viene de las filas); `saved_count = número de mensajes sin los sintéticos`.

Ninguna rama devuelve un historial a medias: o se reconstruye entero o se lanza un error de dominio de mensaje fijo.

## Texto fijo del cierre sintético

`[tool_interrupted] La ejecución se interrumpió antes de obtener el resultado; verifique el estado antes de repetirla.`

Mismo `call_id` que la llamada, `is_error = True`, `is_external = False`. Es el contenido del mensaje y de su `ToolResult`.

## Línea de estado (`Resumed.notice`, una sola línea)

| Caso | Texto |
|---|---|
| Normal | `Sesión reanudada: {n} mensajes.` |
| Con resumen vigente | `Sesión reanudada: {n} mensajes en el contexto (con resumen).` |
| Vacía | `Sesión reanudada: no tenía mensajes; se empieza de nuevo.` |
| Corte | se añade ` Terminó de forma abrupta; se cerraron {k} llamadas sin resultado.` o ` Se había interrumpido.` |
| Modelo distinto | se añade ` El modelo configurado difiere del de la sesión.` |

`n` = mensajes del historial sin contar el prefijo. Nada del contenido, del identificador ni de los nombres de herramientas.

## Ejemplos normativos (calculados a mano)

Sea `P` el único mensaje de prefijo (`SYSTEM`). Filas: `U` petición, `A` asistente, `T` resultado. «ev» = tiene evento. `⟦S⟧` = `frame_summary(S)`.

**E1 — sin compactar.** Filas: 1 `U "hola"` ev · 2 `A "ok"` ev · 3 `U "lee a"` ev · 4 `A ""` con llamada `c1` (sin evento) · 5 `T c1 "texto de a"` ev · 6 `A "fin"` ev. Sin resumen. Resultado: `[P, 1, 2, 3, 4, 5, 6]` → 7 mensajes, `n = 6`, `saved_count = 7`, sin cierres. Igual a la memoria.

**E2 — una compactación que cubrió las filas 2 y 3** (el corte quedó en la fila 4: llamada y resultado juntos en el lado reciente). Marcas: eventos de 2 y 3 cubiertos. Cobertura: 1 no (cabeza) · 2 sí · 3 sí · 4 sin evento → toma la de la 5 → no · 5 no · 6 no. Resumen vigente `S1`. Resultado: `[P, 1, ⟦S1⟧, 4, 5, 6]` → 6 mensajes, `n = 5`. Igual a la vista viva.

**E3 — dos compactaciones.** A E2 se añaden 7 `U "otra"` ev y 8 `A "listo"` ev; la segunda compactación cubrió 4 y 5 (resumió `S1` más ellas). Marcas: 2 y 3 → resumen 1; 5 → resumen 2. Cobertura: 4 sin evento toma la de la 5 → sí. Resumen vigente: el de mayor `evento_hasta` → `S2`. Resultado: `[P, 1, ⟦S2⟧, 6, 7, 8]` → 6 mensajes. La vista viva solo tenía un resumen; la reconstrucción también.

**E4 — corte entre la petición de una herramienta y su resultado.** Filas: 1 `U "haz"` ev · 2 `A ""` con llamadas `c1` y `c2` (sin evento) · 3 `T c1 "ok"` ev. Resultado: `[P, 1, 2, 3, T(c2, texto fijo, error)]` → 5 mensajes, `saved_count = 4`, `closed_calls = (("c2", <nombre>),)`, `cut_off`. Si el corte llega antes de cualquier resultado: `[P, 1, 2, T(c1), T(c2)]`, `saved_count = 3`, dos cierres en el orden de las llamadas.

**E5 — petición sin respuesta.** Filas: 1 `U "a"` ev · 2 `A "b"` ev · 3 `U "c"` ev. Resultado: `[P, 1, 2, 3]`. No hay cierres. La petición siguiente se añade a continuación (dos `USER` seguidos son válidos).

**E6 — rechazo con motivo.** En memoria: `T` con `[approval_rejected] Tool 'shell' was rejected by the user. Reason given by the person… '<motivo>'`. Guardado y reconstruido: `[approval_rejected] Tool 'shell' was rejected by the user.` (excepción declarada).

**E7 — respuesta vacía en el corte (divergencia conocida).** Filas: 1 `U` ev · 2 `A "x"` ev · 3 `U "y"` ev · 4 `A ""` sin evento y sin llamadas · 5 `U "z"` ev · 6 `A "w"` ev. La compactación resumió 2 a 4 (corte en el 5). Cobertura: 2 y 3 cubiertas; 4 toma la de la 5 → no. Reconstruido: `[P, 1, ⟦S⟧, 4, 5, 6]`; la memoria era `[P, 1, ⟦S⟧, 5, 6]`. Sin efecto sobre el emparejamiento (la fila 4 no tiene evento).

**E8 — incoherencias** (todas `ConversationInconsistent`): primera fila `ASSISTANT`; fila cubierta sin resumen; resumen sin filas cubiertas; fila 1 cubierta; `T c9` sin llamada `c9`; `A` con llamadas seguido de una `U` sin que `c1` tenga resultado; identificadores de llamada repetidos.

**E9 — errores de entrada**: `""` → uso; el identificador de la sesión activa → «Esa ya es la sesión actual.»; un identificador de `known_incomplete` → «sin detalle»; `"../x"`, un identificador de 129 caracteres, uno con salto de línea → «no es válido»; `"no-existe"` válido → «No existe…»; sesión con criterios → «sesiones de tarea»; sesión con eventos de mensaje y sin filas → «sin detalle»; sesión sin eventos de mensaje ni filas → vacía (E10).

**E10 — sesión vacía.** Sin filas ni resumen: historial = `[P]`, `empty`, línea «no tenía mensajes».

## Propiedades que prueba el azar (semilla 20261101)

Para historiales válidos generados (peticiones, respuestas con y sin texto, grupos de llamadas, errores, contenido externo, compactaciones simuladas):

1. Guardar con `ConversationCapture` y reconstruir devuelve la vista viva (salvo las excepciones declaradas).
2. Un resultado de herramienta nunca queda huérfano ni una llamada sin resultado en el historial entregado.
3. La reconstrucción es determinista (dos veces, igual) y pasa `check_structure`.
4. Cortar en cualquier punto del guardado produce un historial reconstruible o un error de dominio fijo, nunca otra cosa.
