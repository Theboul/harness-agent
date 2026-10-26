# Hallazgos de SPK-03: compactar sin perder el objetivo (bloque fijo de contexto esencial)

**Fecha**: 2026-10-25  
**Estado**: **Parcial.** El diseño se verificó sin red con un resumidor simulado y `FakeProvider`; falta la corrida con un modelo real, que depende de D-IA. El spike **no** se da por cerrado sin ella.  
**Autor**: Integrante B — Estado (Sp2-34, Sp2-35 y Sp2-36)  
**Trazabilidad**: [SPK-03](../04b-historias-estado.md#spk-03) · AC-01 · alimenta [HU-02-03](../04b-historias-estado.md#hu-02-03), [HU-02-06.1](../04b-historias-estado.md#hu-02-06.1), HU-02-06.2 y [HU-03-04](../04b-historias-estado.md#hu-03-04)  
**Código y pruebas**: [tests/spikes/test_compaction_goal_spike.py](../../tests/spikes/test_compaction_goal_spike.py) · [tests/spikes/compaction_sim.py](../../tests/spikes/compaction_sim.py) · [specs/022-compaction-goal-spike/](../../specs/022-compaction-goal-spike/)

---

## 1. Qué se hizo y qué no

Una sesión larga simulada (81 mensajes, unos 5 500 tokens estimados) siembra en su primer mensaje el objetivo, las instrucciones, las reglas, el ticket (`TCK-4821`) y un criterio protegido, y tres decisiones más adelante. Cada dato lleva un centinela único. Se compacta dos veces (la sesión crece entre pasadas: 56 y 81 mensajes, ventana reciente de 30) y se mide qué centinelas siguen en el contexto ensamblado con dos diseños:

- **A, solo resumen**: todo vive en el historial y se resume.
- **B, bloque fijo**: las cinco claves esenciales van en un mensaje de sistema del prefijo, fuera de lo resumible.

| Comprobado | No comprobado |
|---|---|
| Con el bloque fijo, los cinco elementos esenciales quedan idénticos tras dos compactaciones, **sin depender del contenido del resumen** | Que un modelo real resuma bien: el resumen es un modelo de estrés o un guion de `FakeProvider` |
| Qué entra a la llamada de resumen (solo eventos antiguos y resumen previo; nunca el bloque ni los recientes) | Que el agente responda correctamente el objetivo tras compactar (AC-03 de HU-02-06.1) |
| El corte entre antiguo y reciente puede orfanar un resultado de herramienta si no se corrige | Fidelidad real con que un modelo conserva decisiones y su motivo |
| El historial original no se modifica; los criterios se leen de su fuente en cada ensamblado | Costo, latencia y errores de una llamada de resumen real |
| Tras una 3.ª pasada se pierden las decisiones en **ambos** diseños | Tamaño real de la ventana por modelo y el umbral (HU-02-01) |

**Límite de la evidencia.** El resumidor con pérdida (`LossySummarizer`) está diseñado para perder lo más antiguo primero. Que el diseño A pierda el objetivo en la 2.ª pasada es, en parte, consecuencia de ese diseño. Lo que la prueba demuestra de verdad es la **propiedad del diseño B**: conserva lo esencial aunque el resumen sea malo. Cuánto pierde un modelo real queda para la corrida humana.

## 2. Resultados medidos

Presupuesto del resumen simulado: 3 000 caracteres. Tokens por la heurística local `ceil(caracteres / 4)` (no es HU-02-01).

| Momento | Contexto completo | Diseño A | Diseño B |
|---|---|---|---|
| Tras la 1.ª pasada (56 mensajes, cubre 26) | 3 841 | 2 615 | 2 715 |
| Tras la 2.ª pasada (81 mensajes, cubre 50) | 5 476 | 2 921 | 3 022 |

Supervivencia tras la 2.ª pasada:

| Elemento | A: solo resumen | B: bloque fijo |
|---|---|---|
| Objetivo | **perdido** | bloque |
| Instrucciones | **perdidas** | bloque |
| Reglas | **perdidas** | bloque |
| Ticket | **perdido** | bloque |
| Criterios | resumen (por azar: estaban al final de la línea que se conservó) | bloque (leídos de su fuente) |
| Decisiones 1 a 3 | resumen / resumen / reciente | resumen / resumen / reciente |

Sensibilidad al presupuesto del resumen (diseño A, esenciales vivos de 5 tras la 1.ª y la 2.ª pasada): 2 000 → 5 y 0; 3 000 → 5 y 1; 4 000 → 5 y 5. Subir el presupuesto retrasa la pérdida, no la evita: con más pasadas llega igual. La 3.ª pasada (sesión de 161 mensajes, presupuesto 3 000) deja **cero** decisiones en A y en B.

El bloque de las cinco claves pesa unos 100 tokens (403 caracteres): su costo por llamada es despreciable.

## 3. Diseño del bloque fijo

Contrato en [specs/022-compaction-goal-spike/contracts/essential-block.md](../../specs/022-compaction-goal-spike/contracts/essential-block.md). En resumen:

| Clave (`contexto_esencial.clave`) | Origen | Se guarda como |
|---|---|---|
| `objetivo` | `goal` de la sesión (HU-11-01) o la primera petición del usuario | Texto |
| `instrucciones` | Archivo de instrucciones / sistema (HU-02-05) | Texto |
| `reglas` | Reglas de la tarea | Texto |
| `ticket` | Identificador del ticket | Texto |
| `criterios_ref` | Referencia a los criterios protegidos | **Solo la referencia**; el texto se lee de su fuente en cada ensamblado |

1. **Posición.** Un mensaje `SYSTEM` justo después del prompt de sistema y antes del resumen y de los eventos recientes. Coincide con el orden de `docs/02-arquitectura.md` §4.
2. **Estabilidad.** Mientras no cambien sus valores, el mensaje es idéntico byte a byte entre ensamblados, antes y después de compactar (probado). Eso preserva el prefijo estable de HU-02-01.
3. **Exclusión.** La entrada de la llamada de resumen se arma solo con eventos antiguos aún no cubiertos y el resumen previo. El bloque no puede reescribirse porque nunca entra.
4. **Criterios por referencia.** Referencia sin fuente → el ensamblado **falla** (falla cerrada), aunque el resumen tenga una copia. Si el resumen trae una copia desactualizada, el bloque (que va antes) lleva la versión vigente; por eso el prompt de resumen debe pedir no repetir criterios.
5. **Reconstrucción.** El bloque se rearma desde `contexto_esencial` sin tocar el resumen: sirve para reanudar (HU-03-04) y para el modo «historial completo».
6. **No incluye `decisiones`.** Quedan para HU-02-06.2 (ver §5).

## 4. Reglas de la compactación que salen del spike

- **Corte seguro.** Dado el punto de corte deseado, retroceder mientras el primer mensaje reciente sea un resultado de herramienta (`TOOL`), de modo que la llamada del asistente y todos sus resultados queden juntos del lado reciente. Sin esto, el contexto enviado tendría un resultado huérfano y los convertidores de HU-07-01 lo rechazan. Función de referencia: `safe_cut` en `compaction_sim.py`.
- **Qué se resume.** Solo `history[covered_until:cut]` más el resumen previo. El historial no se modifica (HU-02-03 AC-02) y compactar sin eventos nuevos no hace ninguna llamada.
- **Salidas largas.** Un resumen real descarta el cuerpo de las salidas de herramientas; el modelo de estrés conserva solo su primera línea. HU-02-02 ya recorta antes de que lleguen al historial.
- **Prompt de resumen (borrador, `SUMMARY_PROMPT`).** Pide conservar decisiones y motivo, estado y pendientes, y **no** repetir contexto esencial ni criterios. Sin validar con un modelo real.

## 5. Recomendaciones por historia

| Historia | Recomendación |
|---|---|
| HU-02-06.1 (B) | Implementar `contexto_esencial` con las cinco claves y el contrato de §3; inyección en cada ensamblado; el ensamblador recibe por constructor un lector de solo lectura de criterios (HU-11-01). Limitar el tamaño de cada valor y fallar si se excede (no probado aquí) para que el bloque no devore la ventana |
| HU-02-03 (B) | Compactar solo `history[covered_until:cut]` con corte seguro; llamada aparte sin herramientas; registrar `resumenes(evento_desde, evento_hasta, texto)` y `compactado_por`; no hacer nada si no hay eventos nuevos. Orquestar la compactación desde un punto asíncrono (ver §6) |
| HU-02-06.2 (B) | Es necesaria, no accesoria: tras 3 pasadas el resumen pierde todas las decisiones en ambos diseños. Registro **solo-añadir** en `contexto_esencial.decisiones`, fuera del resumen, igual que el bloque |
| HU-03-04 (A) | Reanudar: reconstruir el bloque desde `contexto_esencial` y el contexto desde los eventos; compactar si supera el umbral. Verificado que el bloque no depende del resumen |

## 6. Hallazgos sobre contratos (no se tocó ninguno; requieren acuerdo de A, B y C)

1. **`ContextManager.compact` es síncrono y la llamada de resumen es asíncrona.** `Provider.complete` es `async` (D-01) y `compact(session_id)` no puede esperarla sin un puente. Opciones: (a) hacer `compact` asíncrono (cambio de puerto); (b) dejar `ContextManager` puro y síncrono, con un paso «preparar» (qué resumir) y otro «aplicar» (guardar el resumen), y que el bucle, que ya es asíncrono, haga la llamada. (b) evita cambiar el puerto existente si se añaden métodos; (a) es más simple. Decisión de A, B y C.
2. **`CompactResult` no lleva el rango cubierto.** Tiene `events_compacted` y `summary`, pero HU-02-03 necesita `evento_desde` y `evento_hasta` para `resumenes` y `compactado_por`. Puede resolverlo la implementación guardando antes de devolver, pero conviene que el resultado lo exponga.
3. **Carga útil de `CONTEXT_COMPACTED`.** El catálogo no fija su carga. Propuesta coherente con la regla de no filtrar contenido: `{desde, hasta, eventos}` sin texto del resumen.
4. **`assemble(session_id, model_id)` necesita leer criterios.** No cambia el puerto, pero la implementación requiere un lector de solo lectura inyectado (HU-11-01). HU-02-06.1 depende de HU-11-01.

## 7. Pendiente

1. **Corrida con un modelo real** (dependiente de D-IA: proveedores y presupuesto; claves solo como variables de entorno). Procedimiento: con el proveedor real, ejecutar `ProviderSummarizer` y `compact` sobre `build_long_session()` (dos pasadas: 56 y 81 mensajes, ventana de 30), con `SUMMARY_PROMPT`; medir con `survival` y `locate` cuáles de los ocho centinelas aparecen en cada resumen; luego enviar el contexto del diseño B con la pregunta «¿cuál era el objetivo original?» y comprobar que la respuesta contiene `OBJ-7F3A`. Costo estimado: tres llamadas de unos 3 000 a 6 000 tokens de entrada.
2. Revisión cruzada por A o C.
3. Acuerdo de A, B y C sobre los hallazgos de §6 antes de implementar HU-02-03.
4. Decidir el umbral por modelo con HU-02-01 (aquí solo hay una heurística local).

## 8. Cómo reproducir

```bash
python -m pytest tests/spikes/test_compaction_goal_spike.py --no-cov
```

No necesita red, claves ni `litellm`.
