# Contrato: mensajes fijos de HU-03-04

Todos son texto fijo en español: **nunca** incluyen el identificador escrito, texto del historial, de la tarea, nombres de herramientas ni el texto de una excepción. Cada error de dominio tiene su tipo en `core/context/errors.py` (subclases de una raíz común `ResumeError`, salvo el del guardado). El orden de las comprobaciones está en `rebuild_rules.md`.

| Tipo | Cuándo | Mensaje |
|---|---|---|
| `InvalidSessionId` (vacío) | `/reanudar` sin identificador | `Uso: /reanudar <identificador de la sesión>.` |
| `InvalidSessionId` | más de 128 caracteres, caracteres fuera de `[A-Za-z0-9._-]` o de control | `El identificador de sesión no es válido.` |
| `AlreadyCurrentSession` | el identificador es el de la sesión activa | `Esa ya es la sesión actual.` |
| `UnknownSession` | identificador válido sin sesión | `No existe una sesión con ese identificador.` |
| `TaskSessionNotResumable` | la sesión tiene criterios o contexto esencial | `Las sesiones de tarea no se pueden reanudar todavía.` |
| `SessionDetailMissing` | hay eventos de mensaje sin su fila (sesión anterior a la historia o guardado fallido) | `Esa sesión se guardó sin el detalle de sus mensajes y no se puede reanudar.` |
| `ConversationInconsistent` | filas incoherentes (ver `rebuild_rules.md`) | `Los mensajes guardados de la sesión no son coherentes y no se puede reanudar.` |
| (lectura) | `SessionStoreError` al leer | `No se pudo leer la sesión; la sesión actual sigue sin cambios.` |
| (no disponible) | la composición tiene tarea o no tiene guardado | `Reanudar no está disponible en esta sesión.` |
| `ConversationSaveError` | falla el guardado de un mensaje (por el avisador, y como excepción) | `No se pudo guardar un mensaje de la conversación; la sesión no podrá reanudarse.` |

## Garantías

- El comando devuelve siempre una línea y la sesión actual **sigue operativa y sin cambios** ante cualquiera de los siete primeros mensajes y el de lectura.
- `ConversationSaveError` no se captura en el bucle: sale como `EventDeliveryError` (R4/R7); el aviso fijo ya se escribió por el avisador.
- Las pruebas usan un centinela en el identificador, en el texto del historial, en los argumentos y en los resultados, y comprueban que no aparece en ningún mensaje de esta tabla, en eventos, en avisos ni en la terminal.
- Una prueba compara estos textos con el contrato (cualquier cambio es un cambio de contrato).
