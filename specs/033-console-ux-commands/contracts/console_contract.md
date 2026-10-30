# Contrato de la consola — HU-06-05

Formatos exactos (texto plano; con color solo se envuelven fragmentos con ANSI y el texto sin códigos es idéntico). `<…>` = valor saneado y acotado.

## 1. Bloque de aprobación

```
============================================================
 APROBACIÓN REQUERIDA
------------------------------------------------------------
 El agente quiere ejecutar un comando:
     <comando en una línea, \n escapados, ≤ 400 caracteres>
 Herramienta: <nombre>
 Argumentos:                       (solo si hay más de los destacados)
   <nombre>: <valor ≤ 200>         (máx. 20, luego "... (y N más)")
 Riesgo:      BAJO | MEDIO | ALTO | DESCONOCIDO
 Efecto:      <efecto ≤ 200 | (sin descripción)>
------------------------------------------------------------
 [1] aprobar una vez   [2] aprobar para la sesión   [3] rechazar
opción> 
```

Frases: `command` → «El agente quiere ejecutar un comando:»; `path` → «El agente quiere usar la ruta indicada con '<tool>':»; otro → «El agente quiere usar la herramienta '<tool>'.». Sin `command`/`path` no hay línea destacada. Lectura: igual que HU-05-03/04 (`1`/`2`/`3`, `/salir`, fin de entrada, `max_attempts`, `Opción no válida: escribe 1, 2 o 3.`, `motivo (opcional, Enter para omitir)> `).

## 2. Líneas de actividad

| Evento | Línea |
|---|---|
| `assistant_message` | `agente> <línea 1>` y continuación con 8 espacios |
| `tool_requested` | `  [..] <tool>: ejecutando` |
| `tool_finished` ok | `  [ok] <tool>: correcto (<duración>)` / sin duración si no se deriva |
| `tool_finished` error | `  [x] <tool>: no se ejecutó.` (denegada/rechazada) o `  [x] Error: <causa> Sugerencia: <acción>` |
| `permission_decided` deny/ask-sin-aprobador | `  [x] Permiso: <causa> Sugerencia: <acción>` (sin cambios de texto) |
| `approval_resolved` | `  [?] <tool>: aprobado una vez` / `aprobado para la sesión` / `rechazado` |
| `context_compacted` | `  [~] Contexto compactado: <N> eventos resumidos.` |
| `provider_error` | `[x] Error: …` (texto actual) |
| `limit_reached` | `[x] Límite: …` (texto actual) |

Duración: `<1 s` → `N ms`; `< 60 s` → `1,2 s`; si no `2 min 5 s`. `permission_decided` con `allow` y `ask` con espera de aprobador no producen línea (supuesto A3).

## 3. Comandos

| Comando | Descripción en `/ayuda` | Salida |
|---|---|---|
| `/ayuda` | Muestra esta ayuda. | lista de todos los comandos (formato actual `  /nombre  descripción`, sin cambios) |
| `/salir` | Termina la sesión. | `Sesión terminada.` |
| `/sesiones` | Lista las sesiones guardadas. | cabecera, hasta 10 filas `* <id>  <fecha> UTC  <estado>  <modelo>  <objetivo>` (`*` = actual) y `... y N más` |
| `/nueva` | Empieza una sesión nueva. | `Sesión nueva: <id>. La anterior sigue guardada; reanúdala con /reanudar <id>.` |
| `/reanudar <id>` | Reanuda una sesión guardada por su identificador. | (HU-03-04, sin cambios) |
| `/compactar` | Compacta el contexto ahora. | `Contexto compactado: ~A → ~B tokens (historial original conservado).` o `No se compactó: no hay mensajes antiguos que resumir (o el resumen falló).` |
| `/model` | Muestra el modelo y los límites. | líneas `Modelo`, `Ventana de contexto`, `Compactación desde`, `Límites` |
| `/criterios` | (con tarea; sin cambios) | |

Mensajes fijos de error: `No se pudo leer la lista de sesiones.`, `No se pudo crear la sesión nueva; la sesión actual sigue sin cambios.`, `Nueva sesión no está disponible en esta ejecución.`, `Compactar no está disponible en esta ejecución.`.

## 4. Estilo

`detect_style(stream, environ, platform)`: apagado si `isatty()` falso, `NO_COLOR` no vacía, `TERM=dumb`, o `win32` sin `WT_SESSION`/`ANSICON`/`ConEmuANSI=ON`/`TERM_PROGRAM`. Colores: riesgo alto rojo, medio amarillo, bajo verde; `[ok]` verde, `[x]` rojo, `[..]` cian, `[?]` amarillo, `[~]` cian; título del bloque en negrita.
