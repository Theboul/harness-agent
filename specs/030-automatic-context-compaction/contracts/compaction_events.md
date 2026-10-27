# Contrato: los eventos de la compactación

El catálogo de 17 eventos (`core/events.py`) **no cambia**. Esta historia fija la carga de `context_compacted`, hoy sin uso, y reutiliza `provider_error` con su forma existente. Los campos se confirman con A, B y C (H1).

## `context_compacted`

- **Cuándo**: una vez por compactación que cubre algo, **después** del `COMMIT` del adaptador y de reemplazar el historial en memoria. Ya está guardado en `events` (lo escribió el adaptador dentro de la transacción única; el registrador del bus no lo guarda otra vez, ver `store_protocol.md`).
- **Carga** (tres claves enteras, en este orden):

| Clave | Contenido |
|---|---|
| `desde` | Menor `seq` de los eventos marcados |
| `hasta` | Mayor `seq` de los eventos marcados |
| `eventos` | Cuántos eventos se marcaron |

**Nunca** lleva: el texto del resumen, mensajes, credenciales, rutas ni el motivo de un error. Ejemplo normativo: `{"desde": 2, "hasta": 6, "eventos": 5}`.

## `provider_error` (fallo de la compactación)

La misma forma que publica el bucle (`reason`, `error_type`, `message`), con contenido fijo:

```json
{"reason": "compaction_failed", "error_type": "CompactionFailed", "message": "No se pudo compactar el contexto; el turno continúa sin compactar."}
```

- Se publica cuando falla cualquier paso (la llamada de resumen, la validación del resumen, la correspondencia con los eventos o el guardado) por una `Exception` ordinaria. **Nunca** lleva el texto de la excepción, del resumen ni del historial. La cancelación (`asyncio.CancelledError`) no se captura y no genera este evento.
- Tras publicarlo, el turno continúa con el contexto sin compactar; no queda ninguna marca, resumen ni evento de resumen.

## Advertencia (sin evento)

Si tras compactar la estimación sigue por encima del umbral, el compactador llama a `warn` con este texto exacto (los números son estimaciones, no datos del historial) y no reintenta:

```text
Aviso: el contexto sigue por encima del umbral tras compactar (~{estimado} de {umbral} tokens); el turno continúa sin reintentar.
```

Ejemplo normativo: `Aviso: el contexto sigue por encima del umbral tras compactar (~26100 de 25600 tokens); el turno continúa sin reintentar.`

## Fallo al publicar el evento tras el `COMMIT` (R16)

No es un fallo de compactación: no se deshace ni se reintenta nada, no se publica `provider_error`, la vista compactada se mantiene y el turno continúa. Se informa por el mismo `warn`, con este texto exacto (sin el texto del resumen ni el de la excepción):

```text
Aviso: la compactación se guardó, pero no se pudo avisar a todos los suscriptores del evento; el turno continúa con el contexto compactado.
```

## Prueba explícita de no filtración

Con centinelas en el historial, en el resumen que devuelve el proveedor simulado y en el texto de una excepción inyectada, y una credencial de URL de prueba (por partes), ni el evento `context_compacted`, ni el `provider_error`, ni el aviso, ni las filas de `events` contienen esos textos; la fila de `resumenes` contiene el resumen **sin** la credencial.
