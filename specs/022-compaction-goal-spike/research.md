# Investigación (Fase 0): SPK-03

## Qué fija ya la documentación

| Fuente | Dato | Consecuencia para el spike |
|---|---|---|
| `docs/02-arquitectura.md` §4 (capas de contexto) | El contexto esencial vive en SQLite `contexto_esencial`: «no se toca ni se resume» | El diseño B materializa esa fila |
| `docs/02-arquitectura.md` §4 | Orden de la ventana: prefijo fijo (instrucciones, herramientas, contexto esencial) → memoria → resumen → eventos recientes completos | El bloque va en el prefijo, antes del resumen |
| `docs/02-arquitectura.md` §4 (tablas) | `contexto_esencial(id, sesion_id, clave, valor, origen, actualizado)` con claves objetivo, instrucciones, reglas, ticket, criterios_ref, decisiones; `eventos.compactado_por`; `resumenes(evento_desde, evento_hasta, texto)` | Se modelan esas claves; `decisiones` queda fuera (HU-02-06.2) |
| `core/interfaces/context.py` | `ContextManager.assemble(session_id, model_id)` y `compact(session_id) -> CompactResult(session_id, events_compacted, summary)`; ambos síncronos | La llamada de resumen es asíncrona (`Provider.complete`): hallazgo a registrar, `compact` síncrono necesita un puente (D-01) |
| `core/events.py` | `CONTEXT_COMPACTED` existe; su payload no está fijado | La decisión propone qué debe llevar, sin tocar el catálogo |
| HU-02-06.1 | El bloque se inyecta en cada ensamblado y no forma parte de lo resumido; los criterios van por referencia | Diseño B |
| HU-02-03 | Mensajes recientes íntegros; el historial original no se borra; umbral por modelo | Se prueban corte seguro y no mutación |
| HU-03-04 | Reanudar usa el historial completo, no el resumen | El bloque debe poder reconstruirse sin el resumen |

## Qué puede y qué no puede demostrar un spike sin modelo real

- **Puede**: que un diseño con bloque fijo conserva los elementos *por construcción* aunque el resumen sea malo; qué entra a la llamada de resumen; que un resumen recursivo con pérdida degrada el objetivo en dos pasadas; que el corte debe respetar los pares llamada/resultado; tamaños relativos.
- **No puede**: que un modelo real resuma bien, qué tan fielmente conserva decisiones, ni que el agente responda correctamente el objetivo (AC-03 de HU-02-06.1). Eso queda como corrida humana pendiente.

## Alternativas descartadas

- **Solo mejorar el prompt de resumen**: depende del comportamiento del modelo, no es verificable offline y viola «lo esencial nunca se resume» (HU-02-06.1, regla 1).
- **Guardar el objetivo como primer evento «anclado»**: mezcla datos protegidos con el historial; la compactación tendría que saltarse eventos y complicaría `compactado_por`.
