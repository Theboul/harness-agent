# Research: HU-02-06.1 — Contexto esencial persistente fuera del historial compactable

Todas las decisiones de abajo salen de leer el código real (2026-10-27, rama `gustavo` alineada con `main` tras HU-02-03). No quedan `NEEDS CLARIFICATION`. Ninguna decisión obliga a tocar `core/loop.py`, `core/interfaces/`, el catálogo de eventos, `core/redaction.py`, `core/verification/` ni la lógica de `split_history` y del compactador de HU-02-03 (comprobado en R3, R5 y R14).

## R1 — Cómo llega hoy una tarea a una sesión (honestidad sobre el alcance)

**Hallazgos**:
- `main()` carga la configuración, llama a `compose(config, …)` **sin tarea** y ejecuta `run_session`. No hay argumento, comando ni línea de la terminal que cargue una tarea.
- Las fuentes de tarea existen (`load_task_file`, `load_github_issue`, HU-11-01) pero **nada en `bootstrap.py` las llama**.
- Una tarea solo entra con `compose(config, task=…)` (pruebas y quien integre el paquete como biblioteca). Los comandos de la tarea (`## Comandos`, HU-11-03) viajan dentro de esa misma `TaskDefinition`.
- Ni el objetivo, ni las reglas, ni los criterios de la tarea llegan hoy al modelo en ningún mensaje: solo se guardan en SQLite (el objetivo como `goal` de la sesión) y el prefijo provisional lleva el aviso de entorno, las reglas de git y los comandos. El paso 5 del flujo de HU-11-01 («inyecta el objetivo, las reglas y los criterios en el prefijo estable») está sin hacer.

**Decisión**: el bloque esencial solo es alcanzable por composición con tarea, **igual que el verificador de HU-11-04.1 y los comandos de HU-11-03**. No se arregla aquí (fuera de alcance: cargar una tarea desde la línea de comandos es otra historia). Se anota en `PROGRESO.md` y en el aviso a A (H7). Consecuencia buena: una sesión sin tarea (la única que existe desde la línea de comandos) no cambia en nada.

**Alternativas**: añadir `--task` a `main()` (otra historia, toca la CLI y la configuración); inyectar el texto de la tarea como mensaje de usuario (cambia el contrato de la petición inicial y duplicaría el bloque).

## R2 — Qué contiene el bloque y de dónde sale cada parte (modelo de tarea real)

La tarea real (`TaskDefinition`) tiene: `title` (opcional, ≤ 2 000 caracteres), `objective`, `context` (texto libre), `rules` (texto libre, puede ser vacío), `criteria` (de 1 a 100 con su descripción ≤ 2 000 caracteres) y `commands`. El analizador acota cada sección a 20 000 caracteres y la tarea entera a 65 536.

| Elemento | Origen | Cómo se guarda | ¿Va en el bloque? |
|---|---|---|---|
| `ticket` | `task.title` (para un issue de GitHub es el **título** del issue: `load_github_issue` no conserva el número) | una línea, limpia | Sí |
| `objetivo` | `task.objective` | texto limpio, con credenciales de URL ocultas | Sí |
| `reglas` | `task.rules` (ausente si está vacío) | texto limpio, credenciales ocultas | Sí |
| `criterios_ref` | el identificador de la sesión cuyos criterios se leen (la sesión de la tarea) | solo la **referencia**; el texto y el estado se leen en cada renovación | Sí, leídos de su fuente |
| `instrucciones` | los mensajes `SYSTEM` provisionales realmente entregados | un registro por mensaje (R8) | **No** (Q2 = A) |

**Fuera del bloque** (decisión de la spec, H4): `task.context` y los comandos de la tarea (estos últimos ya llegan en el mensaje provisional de comandos).

**Identificador del ticket**: el campo es `title`. Sin título el elemento queda ausente. Limitación honesta: en un issue el número no se conserva, solo su título.

**Topes frente al analizador**: el analizador admite secciones de hasta 20 000 caracteres; el tope de esta historia es **8 000 por elemento**, más estricto. Una tarea válida para HU-11-01 con un objetivo de 9 000 caracteres **no arranca** con bloque (rechazo explícito, sin truncar; regla 1 y FR-013). Es la consecuencia directa de la spec y se señala al PO (H4).

## R3 — Dónde entra el bloque y por qué la compactación no cambia

**Hechos del código**:
- `AgentLoop._check_history` admite `SYSTEM` solo como prefijo contiguo del historial; no admite `SYSTEM` más tarde.
- `split_history` (HU-02-03) toma como **cabeza protegida** todos los `SYSTEM` iniciales contiguos más el primer `USER` no externo.
- `is_real` es falso para `SYSTEM`, así que ni la correspondencia mensajes↔eventos ni el recuento de eventos los ven; `rebuild_history` conserva `history[:region_start]` tal cual.
- `estimate_messages` suma todos los mensajes del historial, bloque incluido.

**Decisión**: el bloque es **un mensaje `SYSTEM` colocado justo después del último `SYSTEM` del prefijo contiguo y antes del primer `USER`**. Queda dentro de la cabeza protegida **sin cambiar una línea** de `split_history`, `choose_cut`, `rebuild_history` ni del compactador: no se resume, no entra a la llamada de resumen (esta toma `history[region_start:cut]`) y cuenta en el umbral (FR-014). Se añade al historial **de la sesión** que arma `run_session` y **no** a `Composition.history_prefix`, cuya lista y longitud fijan pruebas existentes (FR-022).

**Alternativas**: meterlo en `history_prefix` (cambia la lista de provisionales y las pruebas que la fijan); un mensaje `USER` externo (no sería del sistema y la compactación lo resumiría); integrar el ensamblador (R14).

## R4 — La marca y por qué un texto externo no puede suplantarlo

**Decisión**: el bloque empieza con la línea fija `[contexto esencial de la tarea]`. Un mensaje **es** el bloque si y solo si (1) su rol es `SYSTEM`, (2) está dentro del **prefijo `SYSTEM` contiguo del principio** del historial y (3) su contenido es exactamente la marca o empieza por la marca seguida de un salto de línea. Nunca se busca en `USER`, `ASSISTANT` ni `TOOL`, ni fuera del prefijo contiguo.

**Razón**: el bucle impide un `SYSTEM` después de un mensaje que no lo sea, y los roles `ASSISTANT`, `TOOL` y `USER` los producen el proveedor, las herramientas y la persona; un texto externo (una salida de herramienta, un archivo, un resumen) que imite la marca queda en un rol que la búsqueda no mira, así que **no puede ser sustituido ni sustituir** al bloque. La prueba del intento (T004) mete la marca en mensajes de los cuatro roles y comprueba que el renovador solo toca el `SYSTEM` del prefijo.

**Duplicados**: si por error hubiera más de un `SYSTEM` con la marca en el prefijo, el renovador deja el primero (sustituido) y borra los demás; nunca quedan dos.

**Alternativas**: identificar el bloque por posición (frágil si cambian los provisionales); por identidad de objeto (se pierde con la copia profunda y no sirve al reanudar); por un campo nuevo en `Message` (cambia `core/entities.py`, contrato compartido).

## R5 — Cuándo se renueva y por qué no hace falta tocar el verificador

**Hechos**: `VerifyingRunner.run(task, history)` llama a una función `run_turn(text, history)` que **construye la composición** (`_verifying_runner` en `bootstrap.py`) y la llama una vez por ronda. `run_session` ejecuta la compactación antes de entregar la petición al ejecutor.

**Decisión** (Q1 = A):
1. `run_session.run_turn(task)`: **renovar → compactar → ejecutar**. Se renueva primero para que la estimación del umbral vea el bloque vigente.
2. La función `run_turn` que `_verifying_runner` entrega al `VerifyingRunner` renueva **antes de cada llamada al bucle**, es decir, antes de cada ronda de verificación. `VerifyingRunner` y `core/verification/` **no se tocan**.
3. Dentro de una misma ronda el bucle hace sus llamadas al modelo sin que la composición intervenga: **limitación conocida**, igual que la compactación de HU-02-03; un único gancho futuro en el bucle (acuerdo de A) resolvería ambas (H1).

La primera ronda renueva dos veces (una en `run_session` y otra en la función de la ronda): la segunda no cambia nada (idempotente, R6) y cuesta una lectura de SQLite.

**Alternativas**: renovar solo en la función de la ronda (la compactación correría antes de renovar y su estimación no vería el bloque vigente); gancho en el bucle (cambia un archivo protegido de A).

## R6 — Renovador: idempotente, estable byte a byte y sin dos bloques

El renovador es **síncrono** (solo lee SQLite y arma texto): `renew(history) -> RenewalOutcome` (`INSERTED`, `REPLACED`, `UNCHANGED`).

Pasos: (1) leer los elementos; (2) si falta alguno de los elementos obligatorios (`objetivo`, `criterios_ref` y al menos una `instrucciones`) falla cerrado (R15); no existe un resultado «sin bloque»; (3) leer los criterios por el lector de solo lectura; (4) armar el texto con el formato fijo (`contracts/block_format.md`); (5) comprobar los topes; (6) localizar el bloque (R4) y insertar, sustituir o no hacer nada. Si el texto es **idéntico** al del mensaje existente, **no se toca la lista ni el objeto** (`UNCHANGED`): el mensaje que recibe el modelo es el mismo byte a byte antes y después de compactar y entre llamadas. El texto es una función pura de (elementos, criterios, tamaño del umbral): no hay reloj, azar ni orden de diccionario.

## R7 — Topes y costo medido en tokens

Con el estimador de HU-02-01 (`ceil(caracteres/4)` + 4 por mensaje), medido sobre el formato real (`contracts/block_format.md`):

| Caso | Caracteres | Tokens estimados | Frente a 5 120 (20 % de 25 600) |
|---|---|---|---|
| Cabecera sola (nunca se envía) | 141 | 40 | 0,8 % |
| Ejemplo E1 del contrato (ticket, objetivo, 2 reglas y 2 criterios) | 444 | 115 | 2,2 % |
| Tarea típica (objetivo ~460, reglas ~570, 6 criterios) | ~1 980 | ~500 | 9,8 % |
| Máximo por el tope por elemento (4 × 8 000) | ~32 200 | ~8 065 | **157 %**: no cabe |
| Máximo que cabe en el 20 % por defecto | 20 464 | 5 120 | 100 % |

**Lectura**: el tope por elemento solo no basta (cuatro elementos llenos pesan el 31 % del umbral); **el tope del 20 % del umbral es el que manda** y es el que protege la ventana. Con ventanas pequeñas el 20 % baja (ventana de 8 000 → 1 280 tokens; una tarea típica aún cabe, una máxima no).

**Decisión**: los topes son **constantes del núcleo** (`MAX_ELEMENT_CHARS = 8_000`, `MAX_BLOCK_SHARE_PERCENT = 20`); la spec no pide configurarlos y añadir campos a `[context]` obligaría a tocar `config.py`, su plantilla y sus pruebas. Si el PO los quiere configurables (H4), es un cambio aditivo posterior. El tope por elemento se comprueba **al guardar** (sobre el valor limpio) y el del 20 % **al guardar (con los criterios pendientes de la definición) y en cada renovación**, porque depende del modelo en uso.

**Qué se mide contra el tope del bloque**: solo el mensaje del bloque. Los provisionales (79 y 106 tokens los dos primeros) no entran en el 20 %; ya cuentan en el umbral.

## R8 — Forma exacta del registro de instrucciones

**Decisión**: una fila por mensaje provisional entregado, en el orden en que se entregaron:

| Columna | Valor |
|---|---|
| `clave` | `instrucciones` |
| `orden` | 1, 2, 3… (posición en el prefijo) |
| `valor` | el **texto exacto** del mensaje, sin limpiar (lo que se envió) |
| `origen` | una etiqueta fija: `entorno`, `git` o `comandos` |

Sin tope (los genera el harness, no la persona ni el modelo) y **nunca se inyecta**: la función de armado del bloque ignora la clave `instrucciones`; una función aparte, `instruction_messages`, devuelve los `SYSTEM` para reconstruir. Se guarda **el texto**, no solo la etiqueta, para que una reconstrucción dé el mismo prefijo aunque el código de los avisos cambie entre versiones.

## R9 — Esquema 4, atomicidad y orden de validación

- Tabla propia `contexto_esencial` (clave, orden, valor, origen por sesión); **no** se tocan `events`, `resumenes` ni `criterios*`. Migración aditiva desde 1, 2 y 3 en una transacción (`_script`).
- `SqliteTaskStore.start_task` (HU-11-01, de A) crea la sesión, los criterios, el sello y la copia en su propia transacción y **no se modifica**. El guardado de los elementos es una **segunda** transacción justo después. Si falla, `compose` cierra el almacén y relanza; quedan en la base una sesión y unos criterios sin elementos esenciales (huérfanos inofensivos: nadie los reanuda y una nueva ejecución crea otra sesión). Es un riesgo conocido y se documenta; la alternativa (un gancho dentro de `start_task`) obligaría a tocar un archivo de A.
- Para no dejar huérfanos en el caso más probable (un valor demasiado grande), **toda la validación pura ocurre antes de abrir el almacén**: se arman los elementos, se comprueban los topes y se comprueba que el bloque con los criterios pendientes de la definición cabe en el 20 % del umbral del modelo. Para eso el prefijo provisional se construye antes de abrir el almacén (no depende de él).
- Un fallo de validación sale como `StartupError` con un mensaje fijo (`main` ya lo muestra en una línea, sin traza).

## R10 — Lectura de criterios y qué se muestra de ellos

- `core/context/` importa solo el **tipo de dato** `TaskCriteriaItem` (de `core/interfaces/`), nunca el puerto `TaskCriteria` ni `core.tasks`: la guarda de HU-02-03 prohíbe esos nombres en todo el paquete y sigue pasando **sin tocarla** (compara el nombre exacto `TaskCriteria`; `TaskCriteriaItem` es otro).
- El núcleo define un protocolo de **solo lectura** `CriteriaReader.load_criteria(session_id)`; `SqliteTaskStore` lo cumple sin cambios (es estructural) y se pasa por constructor. El núcleo no importa adaptadores.
- `load_criteria` **verifica el sello** y, si hay indicios de alteración, ya publica `criteria_tampered` (solo el motivo) y lanza `CriteriaIntegrityError`. El renovador captura cualquier `Exception` de la lectura (el núcleo no conoce el tipo del adaptador), la convierte en un error de dominio con **mensaje fijo** y no publica nada propio: no hay evento nuevo y la alteración sigue informándose donde ya se informaba.
- De cada criterio se muestran: su **posición**, su **descripción** (limpia, en una línea, credenciales ocultas) y su **estado** (`pendiente` o `cumplido`, según `passes`). **No** se leen ni se muestran `command`, `evidence` ni el tipo; el estado `pendiente` cubre también al criterio semántico que espera validación humana.

## R11 — Cómo se informa un fallo cerrado

El renovador lanza `EssentialContextError` (subclases `EssentialContextTooLarge` y `EssentialContextUnavailable`) con un mensaje fijo en español. Como `run_cli` ante cualquier excepción del turno escribe solo el **nombre del tipo** y termina con código 1, la composición, antes de dejar pasar la excepción, escribe el **mensaje fijo** por el `WarningSink` (la salida de la sesión). Resultado: la persona ve el motivo y la sesión termina con fallo; la petición **no** llega al modelo. Mensajes fijos (R16): tope (`El elemento «<elemento>» del contexto esencial supera el tope de <N> <caracteres|tokens>.`), lectura (`No se pudo leer el contexto esencial de la tarea; la petición no se envía.`) y elementos que faltan (`Faltan elementos del contexto esencial de la tarea; la petición no se envía.`). Ninguno incluye valores.

## R12 — Pruebas existentes afectadas (búsqueda completa y corrida en seco)

Búsqueda completa en `tests/` de `SCHEMA_VERSION`, `user_version`, `sqlite_master`, el conjunto exacto de tablas, `history_prefix`, el recorte `[2:]`, `__all__`, `received`/`runner.run`/`run_session` con tarea, el registrador y su suscripción. Además, **corrida en seco**: con el esquema 4 provisional (tabla nueva, versión 4; restaurado después con `cmp`) la suite completa dio **13 fallos y 6 741 pasadas**, todos de esquema. La lista completa y exacta está en `plan.md` («Pruebas existentes que cambian»). Regla: ejecutarlas **sin tocar** y ver que fallan por la versión o la tabla nueva; solo entonces ajustar las líneas declaradas; cualquier otra que falle detiene la implementación.

Revisadas y **sin cambio esperado** (se ejecutan sin tocar; si una falla se detiene la implementación): `history_prefix` (FR-022), el recorte `[2:]` de `test_bootstrap_main.py` (sesión sin tarea: sin bloque, FR-002), los suscriptores del registrador (no hay eventos nuevos), `core.__all__` (las pruebas comprueban inclusión y unicidad, no igualdad) y las pruebas de sesiones con tarea que pasan por el ejecutor (filtran por `is_external` o leen `[-1]`; el bloque es un `SYSTEM` más).

## R13 — Reconstrucción para HU-03-04

Dos funciones puras sin E/S: `instruction_messages(items)` (los `SYSTEM` del registro, en orden) y `render_block(items, criteria)` (el bloque). Con el almacén y la fuente de criterios basta; no se usa el resumen ni el historial. La prueba de T003/T006 demuestra que el prefijo reconstruido **es igual** al que se entregó al empezar. Reanudar de verdad es de HU-03-04.

## R14 — Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Integrar el `ContextAssembler` y que él inyecte el bloque | Obliga a cambiar `core/loop.py` (de A) y a quitar `Composition.history_prefix`; es otra historia |
| Gancho en el bucle antes de cada llamada | Cambia un archivo protegido; mejora futura única para esto y la compactación (H1) |
| Instrucciones dentro del bloque (opción B de Q2) | Rechazada por el revisor: cambia lo que ve el modelo y las pruebas del prefijo |
| Un bloque en sesiones sin tarea con la primera petición como objetivo | Cambia el contexto de toda sesión sin tarea y pruebas existentes para duplicar la petición inicial, que ya queda protegida; decisión del PO (H4) |
| Copiar los criterios a la tabla nueva | Contra la regla 2: una copia se desactualiza |
| Evento nuevo para la renovación o para el fallo | El catálogo no cambia; el fallo se informa por el aviso de la composición |
| Topes configurables en `[context]` | No los pide la spec; obligan a tocar `config.py` y su plantilla |
| Guardar los elementos dentro de `start_task` (atómico con la sesión) | Obliga a tocar el almacén de tareas de A |

## R15 — «Sin tarea» frente a «con tarea sin elementos guardados»

**Problema**: el renovador devolvía «sin bloque» cuando la fuente no tenía elementos. Eso confunde dos situaciones distintas: una sesión **sin tarea** (correcto: no hay bloque y el contexto es el de hoy) y una sesión **con tarea** cuyos elementos no están (el segundo guardado tras `start_task` falló, alguien borró filas, la base se alteró). Tratar la segunda como la primera enviaría la petición sin objetivo, reglas ni criterios, **en silencio**.

**Decisión**:
- La distinción la hace la **composición**, no el renovador: sin tarea no se construye renovador (`Composition.essential` es `None`) y los dos puntos de renovación no hacen nada. Con tarea el renovador existe siempre.
- Con renovador, los elementos obligatorios son `objetivo`, `criterios_ref` y **al menos una** `instrucciones` (toda tarea tiene objetivo y criterios, y todo prefijo tiene al menos el aviso de entorno). Si falta alguno, o la lista viene vacía, `EssentialContextUnavailable(missing=True)`: **falla cerrado**.
- `RenewalOutcome` no tiene `NONE`: solo `INSERTED`, `REPLACED` y `UNCHANGED`.
- La composición escribe el mensaje fijo por el `WarningSink` y relanza; `run_cli` sale con código 1 (R11). La petición no llega al modelo.

**Pruebas**: elementos borrados con una tarea activa (todos, y cada obligatorio por separado) → mensaje de «faltan elementos», 0 llamadas al proveedor, código 1; sin tarea → el contexto de hoy (T004b, T007b, T009).

## R16 — Los mensajes fijos nombran el elemento y el tope

Tres textos exactos, sin contenido:

| Situación | Texto |
|---|---|
| Un elemento o el bloque supera su tope | `El elemento «<elemento>» del contexto esencial supera el tope de <N> <caracteres\|tokens>.` con `<elemento>` ∈ {`objetivo`, `reglas`, `ticket`, `criterios`, `bloque completo`}; ejemplos: `…«objetivo»… 8000 caracteres.` y `…«bloque completo»… 5120 tokens.` |
| La fuente de elementos o de criterios no se puede leer | `No se pudo leer el contexto esencial de la tarea; la petición no se envía.` |
| Con tarea, faltan elementos obligatorios | `Faltan elementos del contexto esencial de la tarea; la petición no se envía.` |

`<N>` es el tope (8 000 caracteres por elemento, o el límite en tokens del 20 % del umbral del modelo en uso): es un número de configuración, no un dato de la tarea. Los errores llevan `element`, `limit` y `unit` como atributos y nunca el valor. Una prueba con centinelas comprueba que el valor excedido no aparece en el mensaje, en `args` ni en `__cause__`.

## R17 — Qué ocurre si el segundo guardado falla tras `start_task`

`compose` ya cierra el almacén y relanza ante **cualquier** fallo de arranque posterior a abrirlo (`except BaseException: store.close(); raise`). El guardado de los elementos va dentro de ese mismo bloque, así que un fallo **lanza**, el almacén queda **cerrado** y **no se devuelve ninguna composición**: no existe una sesión activa y usable. La fila de la sesión y los criterios creados por `start_task` permanecen en la base (huérfanos inofensivos: nadie los reanuda). No se cambia a `interrupted` porque eso exigiría un método nuevo del almacén de sesiones y es lo que `compose` ya hace con los demás fallos de arranque. La prueba comprueba que `compose` lanza, que el almacén queda cerrado y que no hay composición.

## R18 — El movimiento del prefijo en `compose()`

El prefijo provisional (aviso de entorno, reglas de git y comandos de la tarea) solo depende de `system`, del área y de los comandos; no depende del almacén. Se construye **antes** de abrir el almacén para poder validar los topes sin dejar sesiones huérfanas. Es un refactor sin comportamiento nuevo: `Composition.history_prefix` queda igual. **Antes** de añadir nada, T007 ejecuta sin tocarlos `test_bootstrap_compose.py`, `test_bootstrap_shell.py`, `test_bootstrap_main.py`, `test_bootstrap_git.py`, `test_bootstrap_verification.py`, `test_bootstrap_task_commands.py` y `test_bootstrap_compaction.py`; si alguno falla por el movimiento, se detiene la implementación y se avisa.

## R19 — Orden de creación de las funciones

`check_block` y `check_creation` necesitan `render_block`; por eso nacen en T003 y no en T002. T002 tiene los elementos, la limpieza, los topes por elemento y los errores; T003 el texto y la validación de tamaño del bloque; T004 `find_blocks`, `block_message` y el renovador (que usa `check_block`); T004b sus fallos. `make_items` no recibe el identificador de sesión (no existe antes de `start_task`): `criteria_reference(session_id)` añade el elemento `criterios_ref` después.

## R20 — Las 14 pruebas existentes se ajustan en dos tareas

Las 13 de esquema y de conjunto de tablas se ajustan en T005 (la tarea del esquema 4). La 14.ª (`test_public_api.py`) depende de que el adaptador exista y se exporte, así que se ajusta en T006. En ambos casos se ejecutan antes, sin tocar, y se comprueba que fallan por la versión, la tabla o el nombre nuevo.
