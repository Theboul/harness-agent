# Research: HU-11-04.1 — Verificación automática de criterios objetivos

Cada decisión sigue el formato Decisión / Razón / Alternativas. No quedan marcadores sin resolver: las tres preguntas de la spec están resueltas en *Clarifications*.

## R1 — Por dónde se ejecuta el comando: la herramienta del registro, no el puerto `Shell`

**Decisión**: el verificador ejecuta cada comando por el **mismo camino que el agente**: `registry.validate_args("shell", …)` y `registry.get("shell").run(…)`. Un adaptador nuevo y pequeño, `adapters/tools/shell_outcome.py`, convierte el `ToolResult` de la herramienta en un `CommandOutcome` del núcleo (`ran`, `exit_code`, `timed_out`, `output`, `cause`) y se inyecta como `CommandRunner`.

**Razón**: heredar sin duplicar lo que ya hace `ShellTool` y el registro: área de trabajo obligatoria (`[sin_area]`), tiempo acotado y terminación del árbol de procesos, ocultado de credenciales de URL (HU-11-02), recorte general de salida (HU-02-02) y gancho de cancelación. La etiqueta del resultado es estable (`Código de salida: 0`, `[codigo_de_salida=N]`, `[tiempo_agotado]`, `[sin_area]`, `[argumentos_invalidos]`, `[interprete_no_disponible]`, `[error_de_shell]`); una prueba del adaptador ejecuta la herramienta real con un `Shell` doble y fija cada etiqueta, así que un cambio de texto en la herramienta rompe esa prueba y no la verificación en silencio.

**Alternativas**: (a) llamar a `Shell.execute` directamente: da un `ShellResult` estructurado, pero obliga a repetir el ocultado de credenciales, la comprobación del área, el recorte y la cancelación en un segundo sitio (más superficie para filtrar datos). (b) Añadir al puerto un método con resultado estructurado: toca `core/interfaces/`; descartado (restricción 1).

## R2 — Forma de la llamada y evaluación de permisos

**Decisión**: para cada criterio objetivo el verificador construye un `ToolCall(id="verificacion-<n>", name="shell", arguments={"command": <comando>})`, **añadiendo** `"timeout_seconds": <t>` solo cuando el comando es **idéntico** (sin espacios exteriores) a uno declarado en `## Comandos` de la tarea (entonces `t` es el tiempo declarado, ≤ 600). Esa llamada se pasa **tal cual** a `policy.evaluate(...)` (la cadena `ProtectedPolicy(CommandPolicy(GitPolicy(ExactCallPolicy(DefaultPermissionPolicy))))` de `compose()`), a la puerta de aprobación y al runner. El nombre de la herramienta y los nombres de los argumentos se reciben por constructor desde `bootstrap.py` (`shell_tool.name`, `COMMAND_ARGUMENT`, `TIMEOUT_ARGUMENT`), como hace `CommandPolicy`.

**Razón**: es la misma forma que usa el agente, de modo que `ExactCallPolicy`, `CommandPolicy`, `GitPolicy` y `ProtectedPolicy` deciden exactamente igual. Un comando declarado hereda permiso (la política ya lo permite si el tiempo no lo supera) y tiempo; uno que no lo es no lleva tiempo, la política cuenta los 120 s del shell y, como el resto de comandos de riesgo alto, normalmente resuelve «preguntar».

**Resolución**: `DENY` → no se ejecuta ni se pregunta (estado `no_ejecutado`, causa `denegado`); `ASK` → R3; `ALLOW` → se ejecuta; excepción o valor inesperado → `DENY` (falla cerrada).

**Alternativas**: pasar siempre `timeout_seconds` (cambiaría lo que la política ve para comandos no declarados y haría que un comando permitido por `ExactCallPolicy` dependiera de un número); evaluar con otro nombre de herramienta (las reglas del shell no se aplicarían).

## R3 — «Preguntar»: la misma puerta de HU-05-03, pero propia del verificador

**Decisión**: `bootstrap.py` entrega al verificador una `ApprovalGate(approver)` **propia** (si hay aprobador; si no, `None`) y la herramienta del shell (para la descripción y el riesgo que muestra el aprobador). Para cada «preguntar» el verificador publica `approval_requested` y `approval_resolved` con la misma forma que el bucle (`{call_id, name, risk}` y `{call_id, name, action, approved, source}`; una prueba compara las claves con las del bucle). Sin aprobador, o si la persona rechaza o la puerta falla cerrada, el comando no se ejecuta: `no_ejecutado` con causa `sin_aprobador` o `no_aprobado`. El motivo de un rechazo (HU-05-04) **no** se reenvía al agente: el aviso solo dice «no ejecutado».

**Razón**: reutiliza el prompt, la falla cerrada y la aprobación de sesión de HU-05-03 sin tocar el bucle (que guarda su puerta como atributo privado). La aprobación de sesión del verificador es independiente de la del bucle: aprobar «para la sesión» un comando de verificación no aprueba esa llamada para el agente y viceversa. Es conservador (la persona puede ser preguntada una vez más) y queda como observación.

**Alternativas**: compartir la puerta del bucle (exige exponerla: cambio en `core/loop.py`); ejecutar siempre por venir de la tarea (descartada en clarify).

## R4 — Un único escritor de passes

**Decisión**: `mark_passes` solo se invoca desde `core/verification/verifier.py`. Guarda `ast` sobre **todo** `src/`: ningún otro archivo contiene una llamada `….mark_passes(…)`; solo hay definiciones (`interfaces/system.py`, `adapters/storage/task_store.py`). Además, una prueba de integración con `compose()` recorre el registro y comprueba que ninguna herramienta registrada (nombre, esquema o descripción) lo expone ni tiene ese atributo, y que `criterios.json` y la base siguen protegidas (HU-11-01).

**Razón**: regla de negocio 1 como propiedad verificable del código, no solo de las pruebas de comportamiento.

**Alternativas**: restringirlo por convención (no se comprueba); quitar el método del puerto (cambia el puerto).

## R5 — Emparejado y alteración (Q1 = B)

**Decisión**: `CriterionDefinition` no tiene identificador (el formato de HU-11-01 solo guarda descripción, comando y condición) y el `id` de SQLite es un autoincremento global, no comparable con la definición. Por tanto el emparejado es **por posición**: `store.load_criteria(session)` devuelve los criterios en el orden de la tarea. Si el número de filas difiere del de la definición, o una fila no coincide con su pareja (tipo distinto, o comando de SQLite ≠ comando de la definición, comparados con `==` sin normalizar), el criterio es una **alteración**: no se ejecuta, passes no cambia, el aviso al agente no lo menciona con el comando y se publica `criteria_tampered` con `{"motivo": "comando_no_coincide"}` (o `"criterios_no_coinciden"`), el mismo formato que ya publica el almacén (solo el motivo). Si `load_criteria` lanza (el almacén detecta alteración y ya publica su evento), todos los criterios objetivos quedan `alterado`.

**Razón**: la fila de SQLite es la fuente de verdad, pero el agente no debe poder cambiar lo que se ejecuta: solo se ejecuta lo que **coincide exactamente** en las dos fuentes.

**Alternativas**: ejecutar el comando de la definición sin comparar (ignoraría una alteración de la base); comparar normalizando espacios (acepta diferencias que un atacante puede aprovechar).

## R6 — Dónde viven la detección de «propone terminar» y la nueva ronda

**Decisión**: un `VerifyingRunner` puro en `core/verification/runner.py`, con colaboradores inyectados: `run_turn(task, history) -> TurnResult`, el verificador y `compose_feedback`. `bootstrap.py` solo lo **cablea**: `Composition` gana el campo `runner` (opcional) y `run_session` lo usa en el cierre de `run_turn` cuando hay tarea. Sin tarea, nada cambia.

Algoritmo: ejecuta el turno; si no es `COMPLETED` (o no hay verificador) devuelve ese resultado. Si lo es, verifica **todos** los criterios objetivos. Si hay algo que el agente puede corregir (`no_cumplido`, `regresion`, `tiempo_agotado`), añade al historial —que la persona que llama le pasa y el bucle ya muta— un mensaje de `Role.USER` con `is_external=True` con las salidas enmarcadas y lanza otro turno con el aviso del harness como tarea. Si solo quedan causas que el agente no puede arreglar (`denegado`, `sin_aprobador`, `no_aprobado`, `alterado`, condición no soportada) o nada falla, termina y devuelve el último resultado; la CLI muestra el estado.

**Razón**: `core/loop.py` no cambia (`TurnStatus.COMPLETED` es la señal) y la lógica queda probada sin la raíz de composición. Dos mensajes de `Role.USER` seguidos son válidos para `_check_history` (solo prohíbe `SYSTEM` fuera del prefijo y llamadas sin responder).

**Rondas**: no hay contador nuevo. Cada ronda de corrección es otro `run_turn`, que pasa por `_stop_at_limit`; cuando se agota un límite (turnos, tiempo o tokens) el bucle devuelve `LIMIT_REACHED` sin llamar al proveedor y el runner termina. Además, parar cuando nada es corregible evita rondas inútiles. **Observación para A**: el contador de tiempo del bucle (HU-01-06) mide lo que duran las tareas dentro del bucle; los comandos de verificación (hasta 600 s cada uno) corren fuera y **no** cuentan para `max_seconds`. Los límites de turnos y tokens sí acotan las rondas. No se cambia el contador (archivo protegido).

**Alternativas**: tocar `core/loop.py` para que el cierre llame al verificador (descartada, restricción 1); un bucle propio con contador de rondas (descartado en clarify).

## R7 — Aviso al agente y contenido externo

**Decisión**: dos mensajes, en este orden: (1) uno `Role.USER` con `is_external=True` que **enmarca** la salida recortada de cada criterio corregible, con una cabecera fija que dice que es información y no instrucciones; (2) el **aviso del harness** como tarea del turno siguiente, con número, descripción acotada, estado y código de salida, **nunca el comando**. Textos exactos en `contracts/agent_notice_contract.md`. Límites: 1 500 caracteres de salida por criterio (`truncate_output`, que deja la marca de omisión), 6 000 en total, 20 criterios listados.

**Razón**: la salida de un comando es contenido externo no confiable (puede venir de código que el agente edita): se marca (`is_external`) y se enmarca; el texto que sí es del harness se mantiene corto y fijo. Que el aviso lleve la descripción del criterio ayuda a corregir y viene de la tarea; se sanea (`una línea, sin caracteres de control o de formato, ≤ 80`).

**Alternativas**: un solo mensaje (no se puede marcar solo la parte externa); `Role.TOOL` (exige una llamada de herramienta previa sin responder, que no existe).

## R8 — Evidencia guardada

**Decisión**: al marcar un criterio, la evidencia es `Código de salida: <N>` + salto de línea + la salida acotada, todo ≤ 2 000 caracteres (`truncate_output`). La salida ya llega con credenciales ocultas y recortada por la herramienta. **No** contiene el comando. Solo se escribe cuando el criterio pasa (el almacén no tiene dónde guardar un fallo).

**Alternativas**: guardar el comando (lo piden otras vistas, pero la evidencia se exporta a `criterios.json`; el comando ya está en la fila del criterio); guardar la salida completa (la exportación crece sin límite).

## R9 — Evento `criterion_verified`

**Decisión**: el tipo ya existe; esta historia define su carga (siete claves: `criterion`, `total`, `description`, `status`, `met`, `exit_code`, `program`). Es la **única** información que llega a la CLI, así que incluye la descripción del criterio (texto de la tarea, saneado y ≤ 120) y el **nombre del programa** (primer elemento del comando, sin ruta, con caracteres de nombre; `null` si no lo es), que pide la restricción 10. No lleva el comando, los argumentos, la salida ni credenciales. Se publica **un evento por cada criterio de la tarea y en orden** (también los semánticos: `pendiente_humano`), de modo que el último (`criterion == total`) cierra la ronda. Prueba explícita de no filtración con valores centinela en comando, argumentos y salida.

**Desviación declarada**: la restricción 8 pide «sin comando ni salida»; se añade el nombre del programa porque la 10 pide mostrarlo. Alternativa si el acuerdo de A/B/C (H1) no lo admite: quitar `program` del evento y de la línea de la CLI; no cambia nada más.

## R10 — Estado de la tarea y de cada criterio

**Decisión**: siete estados de criterio (`cumplido`, `no_cumplido`, `regresion`, `no_ejecutado`, `tiempo_agotado`, `alterado`, `pendiente_humano`) y tres de tarea: `verificada` (todos los objetivos cumplen y no hay semánticos), `pendiente_humano` (todos los objetivos cumplen y hay semánticos) y `no_terminada` (algún objetivo no cumple). La función pura `task_state(statuses)` se exporta en `core/__init__.py` y la usan el verificador y la CLI, de modo que no hay dos implementaciones. **Nunca** hay un estado «cumplida» por afirmación del modelo: el único camino a `verificada` es que cada objetivo haya cumplido en la ronda.

## R11 — Condición esperada y endurecimiento del analizador (Q3 = A)

**Decisión**: `core/tasks/condition.py` (nuevo) con `parse_condition` y `condition_met`; gramática en `contracts/condition_contract.md`. El analizador de la tarea (`core/tasks/parser.py`, `_CriteriaReader._close`) llama a `parse_condition` **después** de comprobar la pareja `comando`/`espera` y lanza el código nuevo `condicion_no_soportada` (mensaje fijo, sin repetir el texto recibido). **No** se valida en `CriterionDefinition.__post_init__`: las pruebas y el código que construyen definiciones a mano no cambian. El verificador, por su parte, trata una condición no soportada que le llegue por esa vía como `no_ejecutado` (causa `condicion_no_soportada`): defensa en profundidad, falla cerrada.

**Pruebas existentes de HU-11-01 que usan otra condición** (búsqueda en `tests/`):

| Archivo y línea | Condición | ¿Cambia? |
|---|---|---|
| `tests/integration/test_task_start.py:24` | `salida 0` (se analiza con `parse_task`) | **Sí**: pasa a `codigo_salida == 0`; ajuste declarado |
| `tests/unit/adapters/tasks/test_task_source.py:25` | `ok` (se analiza con `parse_task`) | **Sí**: pasa a `codigo_salida == 0`; ajuste declarado |
| `tests/unit/core/tasks/test_task_parser.py:156-158` | `ok`, vacío | No: se rechazan antes por `criterio_incompleto` (la comprobación de la pareja va primero) |
| `tests/unit/core/tasks/test_task_parser.py:195, 199` | `ok` y un texto largo | No: `texto_demasiado_largo` se lanza al leer la línea, antes de validar la condición |
| `tests/unit/core/tasks/test_task_commands.py:248` | `espera:` bajo `## Comandos` | No: `comando_no_valido` se lanza antes |
| `tests/unit/adapters/storage/task_support.py:30`, `test_criteria_export.py:65`, `test_task_store.py:327` y demás | `salida 0` por construcción directa de `CriterionDefinition`, o `codigo_salida == 0` | No: no pasan por el analizador |
| Resto (`test_task_commands.py:35`, `test_task_parser.py:35`, `test_task_commands_agent_loop.py:86`) | `codigo_salida == 0` | No |

Total: **2 ajustes** de pruebas existentes (una cadena cada una) y pruebas nuevas en `test_task_parser.py` (archivo existente: solo se **añaden** casos). El contrato de formato de la spec 021 dejó la gramática a esta historia (*«la define y evalúa HU-11-04.1»*); no se edita esa spec.

**Compatibilidad hacia atrás**: añadir después «la salida contiene un texto» como forma nueva no invalida ninguna tarea escrita con las dos comparaciones.

## R12 — CLI (AC-04)

**Decisión**: archivos de `cli/` (área C, visto bueno en H2): `cli/criteria.py` (nuevo: formateo de una línea, `CriteriaBoard` con el último estado por criterio y la línea final, y `attach_criteria_status(bus, output)`, que se suscribe **aparte** a `criterion_verified` y escribe las líneas), `cli/__init__.py` (exporta lo nuevo) y `cli/app.py` (`run_cli` gana un parámetro opcional `commands` con comandos extra de una línea, p. ej. `/criterios`). `bootstrap.py` crea el tablero y pasa `commands` solo cuando hay tarea. El texto sale **solo** de la carga del evento y se sanea y acota como el resto de la CLI (`sanitize`, `bounded`). Formato exacto en `contracts/cli_status_contract.md`.

**Por qué una suscripción aparte** (hallazgo al preparar las tareas): las pruebas existentes de la CLI fijan `SHOWN_TYPES` (exactamente 6 tipos: `test_render_events.py`, `test_app_output.py`) y el texto exacto de `/ayuda` (`test_app_input.py`). Por eso `cli/render.py`, `SHOWN_TYPES`, `attach_renderer` y `HELP_TEXT` **no cambian**; `/ayuda` solo añade la línea de `/criterios` cuando se le pasa `commands` (sin él, es byte a byte el de hoy). Ninguna prueba existente de la CLI cambia.

**Desviación declarada del prototipo**: el prototipo alinea «pendiente de validación humana» con espacios; aquí va entre paréntesis para que todas las líneas tengan la misma forma. Mismos marcadores (`[x]`, `[ ]`, `[?]`) y mismas palabras.

**Alternativas**: pasar a `run_cli` una función que lea el almacén (cambia su firma); mostrar la tarea completa en cada evento (ruido).

## R13 — Proyecto de ejemplo (Sp2-53) y pruebas con comandos reales

**Decisión**: el proyecto de ejemplo y el ticket con tres criterios (dos con comando y uno semántico) viven como constantes y un constructor en `tests/integration/test_criteria_verification_agent_loop.py` (patrón de HU-11-03: archivos escritos en `tmp_path`; `tests/doubles/` no cambia). La matriz de casos de la spec usa un shell doble que **registra** y no ejecuta nada. **Un único** flujo de punta a punta usa el shell real con comandos triviales `python -c "…"` en `tmp_path` y se omite limpio si no hay intérprete. Ningún comando denegado o preguntado se ejecuta jamás: los denegados y preguntados de la batería de seguridad se prueban solo con el shell doble.

## R14 — Prueba al azar

**Decisión**: semilla fija 20261029; sobre `parse_condition`/`condition_met` y sobre `compose_feedback` con resultados aleatorios (estados, códigos, salidas hostiles y descripciones con caracteres de control). Garantías: nunca lanzan; la condición aceptada es exactamente la del contrato; el aviso nunca contiene el comando ni una credencial de prueba; el mensaje externo y el aviso respetan sus límites y no tienen caracteres de control o de formato salvo el salto de línea.

## R15 — Hallazgos para otras áreas (sin cambiarlas aquí)

- **A (HU-01-06)**: el tiempo de los comandos de verificación no cuenta para `max_seconds` (R6).
- **A/B/C**: si el PO quiere poder revocar passes con evidencia ante una regresión, `TaskCriteria` necesita un método nuevo (cambio de puerto con acuerdo).
- **C (HU-05-03)**: la aprobación de sesión del verificador y la del bucle son independientes (R3).
- **Pendiente de otras historias**: `main()` sigue sin cargar tareas (punto abierto de HU-11-03); esta historia se ejerce con `compose(task=…)`.
