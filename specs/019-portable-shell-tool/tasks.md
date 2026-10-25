# Implementation Tasks: HU-01-04 — Herramienta de shell portable con tiempo límite

**Feature**: `specs/019-portable-shell-tool/spec.md`  
**Plan**: `specs/019-portable-shell-tool/plan.md`  
**Responsable**: C — Control y conexiones  
**Sprint**: Sprint 2 | **PHU**: 3  
**Tareas de referencia**: Sp2-01, Sp2-02, Sp2-03, Sp2-04, Sp2-05  

---

## Cómo leer este documento

**Pruebas primero, dentro de cada tarea.** Cada tarea agrupa las pruebas y la implementación de una pieza: se escriben las pruebas, se ejecutan y se confirma que fallan **por la razón esperada** (`ImportError` del símbolo nuevo o una aserción concreta), se implementa lo mínimo y se vuelve a ejecutar hasta que pasen. El rojo se anota en una línea en el registro de `PROGRESO.md`.

**Ritmo**: 16 tareas de trabajo (T002 a T017) de 40 min como máximo, una de inicio (T001), una de cierre (T018) y tres humanas (T019 a T021). Ninguna pasa de 40 min (la Constitución permite 40; el límite absoluto es 60).

**Reglas que valen para todas las tareas:**
- **Archivos protegidos**: no modificar nada bajo `src/harness_agent/core/` (en particular `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/permissions/` y `core/tools/`), ni `src/harness_agent/config.py`, ni `src/harness_agent/cli/`, ni `tests/doubles/`, ni `docs/archivo/`, ni ninguna prueba existente salvo la desviación que se anote si `compose`/`run_session` fijaban un historial vacío o la lista exacta de herramientas. Los únicos archivos existentes que se tocan son `src/harness_agent/bootstrap.py`, `src/harness_agent/adapters/system/__init__.py`, `src/harness_agent/adapters/tools/__init__.py`, `src/harness_agent/adapters/tools/_limits.py`, `tests/architecture/test_adapters_boundaries.py` (solo se añade una autoprueba), `docs/guia-contratos-desarrollo.md`, `docs/PROGRESO.md` y `arbol.md` de las dos copias de la skill.
- `adapters/system/` y `adapters/tools/` solo importan biblioteca estándar y `harness_agent.core` (`from harness_agent.core import ...`, nunca submódulos) y su propio paquete; **`tools/` no importa `system/`**; no importan `config`, `cli`, `observability`, `bootstrap` ni otro adaptador; no leen `os.environ` ni imprimen. Python 3.12. Sin dependencias nuevas.
- Todo el código y las pruebas deben pasar `mypy --strict` y `ruff` (línea de 100 columnas). Nombres de código en inglés; mensajes al usuario y documentación en español.
- Los tipos, las reglas y los límites siguen [contracts/shell_tool_contract.md](contracts/shell_tool_contract.md) y [data-model.md](data-model.md); las decisiones, [research.md](research.md) (R1 a R12) y [plan.md](plan.md) (D1 a D17).
- **Aislamiento**: toda prueba que ejecuta comandos usa `tmp_path` como carpeta de trabajo; ninguna toca el repositorio, el directorio personal ni la red; ninguna deja procesos vivos (cada prueba real limpia en `finally`). Los comandos reales usan `echo`, `exit N`, `sleep` y `sys.executable`. Las pruebas exclusivas de una plataforma llevan `skipif(sys.platform …, reason=…)` con motivo y tienen su equivalente en la otra. Valor centinela: `VALOR-DE-PRUEBA-123`.
- **Sin literales detectables**: ninguna prueba contiene texto que `tests/architecture/test_no_secrets_in_repo.py` detecte como clave (las pruebas del entorno filtrado usan nombres de variable y valores sintéticos que la guarda no marca; se comprueba en T003).
- **Commits** (estilo del proyecto): en español, sin coautor ni pie de sesión, formato `tipo(ámbito): descripción (HU-01-04)` con `feat`, `test` o `docs`; la rama es `feat/hu-01-04-shell-tool`. Cada tarea o grupo de tareas cierra con al menos un commit; sin push, merge ni PR sin confirmación humana.
- **Al cerrar cada tarea que toca código o pruebas**, ejecutar `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`; los cuatro con código 0, y registrar el resultado en `docs/PROGRESO.md` dentro de los 5 min de la tarea.

**Correspondencia con las tareas del plan de sprint** (columna *Tarea F5*):

| Tarea F5 | Descripción en `docs/03-plan-sprints.md` | Presupuesto | Microtareas (min) |
|---|---|---|---|
| **Sp2-01** | Ejecutar subprocesos con tiempo máximo | 120 | T004 (35), T005 (40), T006 (40) = 115 |
| **Sp2-02** | Interfaz Shell con una implementación para bash y otra para PowerShell | 180 | T007 (30), T008 (40), T009 (35), T012 (40) = 145 |
| **Sp2-03** | Informar al modelo el sistema operativo y el intérprete en el prefijo | 60 | T010 (20), T014 (parte del cableado, 40) = 60 |
| **Sp2-04** | Acotar y marcar la salida larga | 90 | T002 (35), T011 (30) = 65 |
| **Sp2-05** | Pruebas del shell en integración continua con Windows y Linux | 180 | T015 (35), T016 (25), T018 (35), T019 a T021 (humanas) = 95 |
| Transversal | Estado, entorno del hijo, lista de denegados, documentación (Principios VIII y IX) | — | T001 (20), T003 (25), T013 (20), T017 (30) = 95 |

**Total de las microtareas de trabajo**: 575 min frente a los 630 min presupuestados para Sp2-01 a Sp2-05 (T014 se cuenta una vez, en Sp2-03): dentro del presupuesto.

---

## Phase 1: Setup (estado)

**Propósito**: Marcar la historia `En curso`.

- [ ] **T001** Marcar HU-01-04 como `En curso` en `docs/PROGRESO.md` (transversal)
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: Ninguna
  - **Criterios relacionados**: Principio VIII
  - **Tarea F5**: Transversal
  - **Estimación**: 20 min (10 min impl + 5 min check + 5 min registro)
  - **Verificación**: La fila de `HU-01-04` de la tabla de Sprint 2 pasa de `Pendiente` a `En curso` (responsable `C — Control y conexiones`); se añade el bloque **Observaciones de HU-01-04** con la spec 019, las dos decisiones del responsable (lista de denegados solo como dato; entorno sin claves de proveedor), el riesgo alto con aprobación obligatoria, la limitación del puerto `Shell` (síncrono, sin carpeta, entorno ni cancelación) como hallazgo para A, y la nota de que PowerShell usa `-Command` por el XML de `-EncodedCommand`.

---

## Phase 2: Foundational — Piezas del motor de subprocesos (Sp2-01, Sp2-04)

**Propósito**: Las piezas puras o casi puras que comparten las dos implementaciones. Bloquean todas las historias.

- [ ] **T002** Constantes, error de arranque y `OutputCollector` con sus pruebas (FR-006, FR-013, FR-014)
  - **Archivos**: `src/harness_agent/adapters/system/shell_limits.py`, `src/harness_agent/adapters/system/shell_errors.py`, `src/harness_agent/adapters/system/shell_output.py`, `tests/unit/adapters/system/test_shell_output.py`
  - **Dependencias**: T001
  - **Criterios relacionados**: FR-006, FR-013, FR-014, SC-002, contrato §1 (aviso), data-model (OutputCollector), research R4 y R11, plan D5
  - **Tarea F5**: Sp2-04
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero: salida corta llega completa y sin aviso; exactamente en el máximo sin aviso; un carácter más recorta; el resultado nunca supera `max_output_chars`; conserva cabeza y cola; el aviso dice el número exacto de caracteres omitidos; bytes UTF-8 partidos entre lecturas se reconstruyen; bytes inválidos se sustituyen sin lanzar; un millón de caracteres en trozos mantiene la memoria retenida acotada (`len(head)+len(tail)`); parámetros inválidos (`max` ≤ reserva) → `ValueError`. `ShellStartError` es subclase de `OSError`.

- [ ] **T003** [P] `child_environment`: copia del entorno sin las claves de proveedores (FR-010c)
  - **Archivos**: `src/harness_agent/adapters/system/shell_environment.py`, `tests/unit/adapters/system/test_shell_environment.py`
  - **Dependencias**: T001
  - **Criterios relacionados**: FR-010c, data-model (funciones puras), research R7, plan D15
  - **Tarea F5**: Transversal
  - **Estimación**: 25 min (15 min impl + 5 min check + 5 min registro)
  - **Verificación**: Pruebas primero: quita exactamente los nombres indicados y deja el resto intacto; no muta la entrada; con `windows=True` compara sin distinguir mayúsculas; con `windows=False` distingue; nombres vacíos o ausentes no fallan; devuelve un `dict` nuevo. Los nombres y valores de prueba son sintéticos y la guarda de secretos sigue en verde.

- [ ] **T004** `ProcessControl`, `PosixProcessControl` y `WindowsProcessControl` con sus pruebas (FR-002, FR-003)
  - **Archivos**: `src/harness_agent/adapters/system/process_control.py`, `tests/unit/adapters/system/test_process_control.py`
  - **Dependencias**: T002
  - **Criterios relacionados**: AC-01, FR-002, FR-003, data-model (ProcessControl), research R3, plan D6
  - **Tarea F5**: Sp2-01
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero con un proceso falso (registra llamadas) para ambas clases en cualquier sistema (módulos `os`/`signal`/ejecutor de `taskkill` inyectables): POSIX → `popen_options` con `start_new_session`, `request_stop` envía `SIGTERM` al grupo, `force_stop` `SIGKILL`, tolera `ProcessLookupError`; Windows → `creationflags`, `CTRL_BREAK_EVENT`, `taskkill /PID n /T /F`, tolera el fallo del ejecutor; `default_process_control(windows)` elige la correcta. Prueba real marcada por plataforma: POSIX (grupo con un nieto que muere) y Windows (`taskkill /T` mata al nieto), cada una con su `skipif` y motivo.

- [ ] **T005** `SubprocessShell`: arranque, lectura, espera y resultado, con pruebas reales (FR-001, FR-004, FR-005)
  - **Archivos**: `src/harness_agent/adapters/system/subprocess_shell.py`, `tests/unit/adapters/system/test_subprocess_shell.py`
  - **Dependencias**: T002, T003, T004
  - **Criterios relacionados**: FR-001, FR-004, FR-005, FR-006, data-model (SubprocessShell), research R4 y R6, plan D1, D3, D4
  - **Tarea F5**: Sp2-01
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero con una subclase mínima de prueba (`_argv` que ejecuta `sys.executable -c <código>`, común a ambas plataformas): código de salida 0 y no 0; salida estándar y de errores combinadas; salida no ASCII correcta; la carpeta de partida es `cwd`; la entrada está cerrada (un hijo que lee `stdin` recibe fin de archivo); el entorno del hijo es el filtrado; tiempo ≤ 0, `nan` o no numérico → `ValueError`; ejecutable ausente (`which` devuelve `None`) y fallo del sistema al arrancar → `ShellStartError` sin ruta ni comando en el mensaje; sin `shell=True`.

---

## Phase 3: User Story 1 — Tiempo agotado y árbol de procesos [AC-01] (Priority: P1)

**Objetivo**: Un comando que excede el tiempo se termina con todo lo que lanzó y el modelo recibe un resultado de tiempo agotado.

**Prueba independiente**: un `sleep` más largo que el plazo vuelve marcado como tiempo agotado poco después del plazo, sin procesos vivos.

- [ ] **T006** [US1] Tiempo agotado, terminación en dos pasos y árbol de procesos con procesos reales (FR-002, FR-003, SC-001)
  - **Archivos**: `tests/unit/adapters/system/test_subprocess_shell.py`, `src/harness_agent/adapters/system/subprocess_shell.py`
  - **Dependencias**: T005
  - **Criterios relacionados**: AC-01, US1-1 a US1-6, FR-002, FR-003, SC-001, research R3
  - **Tarea F5**: Sp2-01
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero (comunes a las dos plataformas, con `sys.executable`): un hijo que duerme más que el plazo → `timed_out=True`, control de vuelta en menos de plazo + 3 s; un hijo que lanza un nieto vivo → el nieto también muere (se comprueba su PID); salida parcial escrita antes del cuelgue llega acotada; un comando que termina antes del plazo no espera el plazo completo; un comando que termina justo antes de agotarse no se marca como agotado; un proceso en segundo plano que sobrevive al comando se limpia. Marcada POSIX (con motivo): un hijo que ignora `SIGTERM` escala a `SIGKILL` (código -9). Marcada Windows (con motivo): terminación por `CTRL_BREAK` + `taskkill /T`. Gracia inyectable (0,2 s) en las pruebas. Ningún PID del experimento sigue vivo al terminar la prueba.

---

## Phase 4: User Story 2 — PowerShell en Windows y bash en Linux [AC-02] (Priority: P1)

**Objetivo**: Dos implementaciones de `Shell` y una elección según la plataforma.

**Prueba independiente**: con el sistema inyectado, la elección devuelve la implementación correcta; en cada sistema real, un comando imprime el intérprete que lo ejecuta.

- [ ] **T007** [P] [US2] `BashShell` (FR-007, FR-009, FR-010)
  - **Archivos**: `src/harness_agent/adapters/system/bash_shell.py`, `tests/unit/adapters/system/test_bash_shell.py`
  - **Dependencias**: T005
  - **Criterios relacionados**: AC-02, US2-2, US2-4, FR-007, FR-009, FR-010, research R2, plan D7
  - **Tarea F5**: Sp2-02
  - **Estimación**: 30 min (15 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero: `interpreter_name == "bash"`; el argv es `[<bash>, "--noprofile", "--norc", "-c", <command>]` con `which` inyectado (corre en cualquier sistema); sin `bash` → `ShellStartError` («intérprete no disponible»), sin caer en otro; marcadas Linux (con motivo): `echo $0`/`echo $BASH_VERSION` confirma bash, `exit 3`, `echo hola`, perfiles no cargados (variable exportada en un archivo de perfil temporal no aparece), comando con comillas y `&&`.

- [ ] **T008** [P] [US2] `PowerShellShell` (FR-007, FR-009, FR-010)
  - **Archivos**: `src/harness_agent/adapters/system/powershell_shell.py`, `tests/unit/adapters/system/test_powershell_shell.py`
  - **Dependencias**: T005
  - **Criterios relacionados**: AC-02, US2-1, US2-4, US2-6, FR-007, FR-009, FR-010, research R1, plan D7
  - **Tarea F5**: Sp2-02
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero: `interpreter_name == "powershell"`; con `which` inyectado prefiere `pwsh` y si no usa `powershell`; el argv contiene `-NoLogo -NoProfile -NonInteractive -Command` y el guion con preludio UTF-8, el comando intacto en su propia línea y el epílogo del código de salida (corre en cualquier sistema); sin ninguno de los dos → `ShellStartError`. Marcadas Windows (con motivo): `echo hola`, `exit 3`, un ejecutable nativo con código 7, un cmdlet que falla → 1 y texto legible (sin `#< CLIXML`), `echo 'áéñ ü'` correcto, un comando con comillas simples y dobles, comando terminado en comentario `# …`.

- [ ] **T009** [US2] `select_shell`, `interpreter_for` y contrato común del puerto (FR-007, FR-008, FR-022)
  - **Archivos**: `src/harness_agent/adapters/system/shell_selection.py`, `src/harness_agent/adapters/system/__init__.py`, `tests/unit/adapters/system/test_shell_selection.py`, `tests/contracts/test_shell_contract.py`
  - **Dependencias**: T007, T008
  - **Criterios relacionados**: AC-02, AC-04, US2-1 a US2-3, US2-5, FR-007, FR-008, FR-022, contrato §3, plan D8, D9
  - **Tarea F5**: Sp2-02
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero: `Windows` → `PowerShellShell`/`powershell`, `Linux` → `BashShell`/`bash`, otro sistema → bash; `interpreter_for` coincide con `interpreter_name`; el `cwd`, el entorno y los nombres a quitar llegan a la implementación. Contrato `tests/contracts/test_shell_contract.py`: la **misma batería** corre contra la implementación nativa del sistema (`select_shell(platform.system())`, real) y contra ambas implementaciones con una función `which` y un proceso falsos; verifica la forma de `ShellResult` (entero, texto, booleano), el código de salida, la salida combinada, el tiempo agotado y el error de arranque. Sin omisiones en la parte nativa.

---

## Phase 5: User Story 3 — El modelo conoce su entorno [AC-03] (Priority: P1)

**Objetivo**: Un texto estable con el sistema operativo y el intérprete llega al modelo desde el arranque.

**Prueba independiente**: el historial inicial empieza con un mensaje de sistema que nombra el sistema y el intérprete (completada con T014).

- [ ] **T010** [P] [US3] `environment_notice` (FR-011)
  - **Archivos**: `src/harness_agent/adapters/system/environment_notice.py`, `src/harness_agent/adapters/system/__init__.py`, `tests/unit/adapters/system/test_environment_notice.py`
  - **Dependencias**: T001
  - **Criterios relacionados**: AC-03, US3-2, US3-3, FR-011, contrato §2, research R8, plan D13
  - **Tarea F5**: Sp2-03
  - **Estimación**: 20 min (10 min impl + 5 min check + 5 min registro)
  - **Verificación**: Pruebas primero: el texto de `("Windows","powershell")` y de `("Linux","bash")` nombra el sistema y el intérprete; dos llamadas devuelven el mismo texto (igualdad exacta); dos pares distintos dan textos distintos; no contiene `\r`, ni la ruta de trabajo, ni el nombre de usuario, ni variables de entorno (con centinelas); un intérprete desconocido no lanza y se nombra tal cual.

---

## Phase 6: User Story 4 — Salida larga acotada y marcada (Priority: P2)

**Objetivo**: La salida enorme llega al modelo recortada, con aviso y sin agotar la memoria.

**Prueba independiente**: un comando que imprime mucho más que el máximo devuelve a lo sumo el máximo, con cabeza, cola y aviso; uno corto, sin aviso.

- [ ] **T011** [US4] Salida enorme y no UTF-8 con procesos reales (FR-006, FR-013, FR-014, SC-002)
  - **Archivos**: `tests/unit/adapters/system/test_subprocess_shell.py`
  - **Dependencias**: T006
  - **Criterios relacionados**: US4-1 a US4-5, FR-006, FR-013, FR-014, SC-002
  - **Tarea F5**: Sp2-04
  - **Estimación**: 30 min (15 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero (con `sys.executable`, comunes a las dos plataformas): un hijo que escribe 100 MB termina, el texto no supera el máximo, empieza con el principio y acaba con el final reconocibles y el aviso dice el total omitido; la memoria retenida del colector queda acotada (`tracemalloc` o recuento de longitudes); un hijo que escribe bytes inválidos devuelve texto con caracteres de sustitución, sin excepción; el aviso también aparece con tiempo agotado y con código distinto de 0; salida corta sin aviso. Si el volumen de 100 MB hace lenta la prueba (más de 10 s), se reduce el tamaño y se anota (el colector ya se probó por separado en T002).

---

## Phase 7: User Story 5 — Herramienta `shell`, riesgo alto y aprobación obligatoria (Priority: P2)

**Objetivo**: El modelo ve una herramienta `shell` de riesgo alto que la política existente controla y que traduce todo a un `ToolResult`.

**Prueba independiente**: con el bucle y la política reales y sin aprobador, la llamada se pregunta, se deniega y no lanza ningún proceso.

- [ ] **T012** [US5] `ShellTool` y sus límites (FR-015 a FR-019)
  - **Archivos**: `src/harness_agent/adapters/tools/shell.py`, `src/harness_agent/adapters/tools/_limits.py`, `src/harness_agent/adapters/tools/__init__.py`, `tests/unit/adapters/tools/test_shell_tool.py`
  - **Dependencias**: T005
  - **Criterios relacionados**: AC-01, US5-1, US5-2, US5-4, US5-5, FR-015 a FR-019, SC-004, contrato §1, plan D2, D11, D12, D16
  - **Tarea F5**: Sp2-02
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero con un `Shell` de prueba (clase local en la prueba, no en `tests/doubles/`) que devuelve resultados guionizados: nombre `shell`, riesgo `HIGH`, esquema que pasa `check_schema` (registro real) y rechaza campos extra, `command` vacío o no textual, `timeout_seconds` fuera de rango; éxito → `Código de salida: 0`; código ≠ 0 → `[codigo_de_salida=N]` y `is_error`; tiempo agotado → `[tiempo_agotado]` con el plazo aplicado y la salida parcial; salida vacía → `(sin salida)`; `ShellStartError`/`OSError` → `[interprete_no_disponible]` con el nombre del intérprete; otra excepción → `[error_de_shell]` sin el texto de la excepción (centinela `VALOR-DE-PRUEBA-123` no aparece); sin área → `[sin_area]` y el `Shell` no se llama; `timeout_seconds` por defecto 120 y acotado a 600; el `Shell` se ejecuta fuera del hilo del bucle (`asyncio.to_thread`); el resultado no repite el comando.

- [ ] **T013** [P] [US5] Lista de comandos denegados por plataforma como dato (FR-010b)
  - **Archivos**: `src/harness_agent/adapters/system/denied_commands.py`, `src/harness_agent/adapters/system/__init__.py`, `tests/unit/adapters/system/test_denied_commands.py`
  - **Dependencias**: T001
  - **Criterios relacionados**: regla de negocio 3, FR-010b, research R9, plan D14
  - **Tarea F5**: Transversal
  - **Estimación**: 20 min (10 min impl + 5 min check + 5 min registro)
  - **Verificación**: Pruebas primero: `denied_commands_for("bash")` y `("powershell")` devuelven tuplas no vacías de `DeniedCommand` con `pattern` y `reason` no vacíos; son distintas entre sí; un intérprete desconocido devuelve `()`; `DEFAULT_DENIED_COMMANDS` es de solo lectura (no admite asignación); una prueba de arquitectura ligera confirma que `subprocess_shell.py`, `bash_shell.py`, `powershell_shell.py` y `shell.py` **no** importan este módulo (nada lo aplica aquí).

- [ ] **T014** [US5] Cableado en `bootstrap.py`: elección del `Shell`, `ShellTool`, entorno sin claves y prefijo (FR-012, AC-03)
  - **Archivos**: `src/harness_agent/bootstrap.py`, `tests/unit/test_bootstrap_shell.py`
  - **Dependencias**: T009, T010, T012
  - **Criterios relacionados**: AC-03, US3-1, US3-4, US5-5, FR-010c, FR-012, plan D13, D15 y «Qué cambia en bootstrap.py»
  - **Tarea F5**: Sp2-03
  - **Estimación**: 40 min (25 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero con `compose` y un `provider_factory` de prueba: la herramienta `shell` queda registrada (con y sin área; sin área devuelve `[sin_area]`); el `Shell` se construye con `cwd == area.root`, el entorno inyectado y los nombres de `PROVIDER_KEY_VARIABLES` (sin `None`) como nombres a quitar; `Composition.history_prefix` tiene un único mensaje de sistema con el texto de `environment_notice` del sistema inyectado; `run_session` empieza `history` con ese prefijo y el prefijo no cambia entre turnos; `main` pasa su `environ` a `compose`. `bootstrap.py` sigue importando solo lo permitido (`test_bootstrap_boundaries.py` en verde). Si una prueba existente fijaba la lista exacta de herramientas o el historial vacío, se ajusta solo su aserción y se anota la desviación en `PROGRESO.md`.

- [ ] **T015** [US5] Integración con el bucle real y la política real: denegación sin proceso y ejecución de extremo a extremo (AC-01 a AC-03, FR-024)
  - **Archivos**: `tests/integration/test_shell_agent_loop.py`
  - **Dependencias**: T014
  - **Criterios relacionados**: AC-01, AC-02, AC-03, US5-3, FR-024, SC-003
  - **Tarea F5**: Sp2-05
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: Pruebas primero con `AgentLoop`, `InMemoryToolRegistry`, `DefaultPermissionPolicy`, `ScriptedProvider` (o `FakeProvider`) y el `Shell` nativo real sobre `tmp_path`: (a) con la política real y sin aprobador, la llamada a `shell` se pregunta, se resuelve como denegada y **ningún proceso** se lanza (se comprueba con un archivo marcador que el comando habría creado); (b) con una política de prueba (`ScriptedPolicy`) que permite `shell`, un `echo` vuelve al modelo con su salida y el código 0, y un comando que se cuelga vuelve con `[tiempo_agotado]` (plazo corto); (c) el historial con el mensaje de sistema inicial es válido para el bucle (prefijo contiguo). Comandos válidos en bash y PowerShell (`echo`, `exit`, `sleep`) para que la misma prueba corra en las dos plataformas.

---

## Phase 8: Fronteras y cierre de calidad (Sp2-05)

- [ ] **T016** Verificación de fronteras hexagonales (skill `verificar-fronteras-hexagonales`)
  - **Archivos**: `tests/architecture/test_adapters_boundaries.py`
  - **Dependencias**: T014
  - **Criterios relacionados**: FR-020, FR-021, Principio III, skill `verificar-fronteras-hexagonales`
  - **Tarea F5**: Sp2-05
  - **Estimación**: 25 min (10 min impl + 10 min check + 5 min registro)
  - **Verificación**: `pytest tests/architecture` en verde con los módulos nuevos; autoprueba nueva: `adapters/tools/shell.py` no importa `harness_agent.adapters.system` (el detector marca un fuente sintético que sí lo hace); `system/` puede usar `subprocess`, `threading`, `signal`, `codecs` (stdlib) sin romper la guarda; ningún módulo nuevo lee `os.environ`/`getenv` ni imprime. Se anota en el registro la lista de archivos que violarían una regla (esperado: ninguno).

- [ ] **T017** [P] Documentación: guía de contratos y árbol de las skills (FR-027)
  - **Archivos**: `docs/guia-contratos-desarrollo.md`, `.claude/skills/estructura-carpetas-harness/references/arbol.md`, `.agents/skills/estructura-carpetas-harness/references/arbol.md`
  - **Dependencias**: T014
  - **Criterios relacionados**: FR-027, CLAUDE.md («Si encuentras una diferencia entre una skill y el código…»)
  - **Tarea F5**: Transversal
  - **Estimación**: 30 min (20 min impl + 5 min check + 5 min registro)
  - **Verificación**: La guía gana una sección «Herramienta `shell`» (nombre, riesgo, argumentos, etiquetas, entorno filtrado, prefijo, lista de denegados como dato y qué le toca a HU-05-02/HU-05-03); las dos copias de `arbol.md` pasan las piezas del shell de «planeadas» a «existentes» y quedan idénticas entre sí; `CLAUDE.md` se actualiza en la fila de `bootstrap.py`/qué existe solo si el equipo lo acepta (si no, se anota como observación).

---

## Phase 9: Cierre

- [ ] **T018** Cierre de la historia: calidad, cobertura, archivos protegidos y `PROGRESO.md` (Principio VIII, Sp2-05)
  - **Archivos**: `docs/PROGRESO.md`, `specs/019-portable-shell-tool/tasks.md`
  - **Dependencias**: T001 a T017
  - **Criterios relacionados**: Principios IV, VIII y IX, FR-026, FR-027, SC-005 a SC-007
  - **Tarea F5**: Sp2-05
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: Los cuatro comandos de calidad en 0 y `pytest tests/architecture`; cobertura al 100 % de líneas y ramas en los módulos nuevos salvo ramas exclusivas de plataforma (se enumeran); `pytest -rs` muestra solo las omisiones marcadas con motivo y su equivalente; el comando de archivos protegidos (`git diff --exit-code $base -- src/harness_agent/core/interfaces src/harness_agent/core/events.py tests/doubles docs/archivo`) da 0; `PROGRESO.md`: fila de HU-01-04 → `En revisión` (nunca `Hecha`), *Archivos*, *Evidencia* con comandos y resultados reales, una línea por tarea en *Registro de cambios*, observaciones para A (puerto síncrono, cancelación), B (prefijo provisional, `config.py`), HU-05-02 (lista de denegados), HU-05-03, HU-02-02 y HU-11-03; las tareas humanas quedan sin marcar. `.specify/feature.json` apunta a `specs/019-portable-shell-tool`.

---

## Phase 10: Tareas humanas (Claude no las marca)

- [ ] **T019** *(humana)* Revisión cruzada por un integrante de otra área (A o B)
  - **Archivos**: —
  - **Dependencias**: T018
  - **Criterios relacionados**: Principio IX
  - **Estimación**: según la persona revisora
  - **Verificación**: Revisa el diff, el *Output Contract* de las tres skills, la lista de comprobación sí/no y las limitaciones del puerto `Shell` (síncrono, sin carpeta/entorno/cancelación) para decidir si se amplía con acuerdo de A, B y C.

- [ ] **T020** *(humana)* Ejecución de la CI en Linux y Windows y relleno de Commit/PR
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: T019
  - **Criterios relacionados**: AC-04, Principio IX
  - **Estimación**: según la CI
  - **Verificación**: La matriz de CI (`ubuntu-latest`, `windows-latest`) pasa con las pruebas de procesos reales de ambas plataformas (incluidas las marcadas); la fila de HU-01-04 recibe Commit/PR y, solo entonces, puede pasar a `Hecha`. Nada está subido hasta que el usuario lo decida.

- [ ] **T021** *(humana)* Confirmación del PO de los supuestos «por confirmar»
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: T018
  - **Criterios relacionados**: spec (*Clarifications*)
  - **Estimación**: según el PO
  - **Verificación**: El PO confirma o corrige: la lista inicial de comandos denegados de cada plataforma, la carpeta de partida (raíz del área), el formato del resultado, el recorte (cabeza + cola) y el nombre `shell`; se registra la respuesta.

---

## Dependencias y orden de ejecución

```
T001 → T002 ──┬──→ T004 ─┐
        │     └──→ T005 ←┤ (T003 también)
        ├──→ T003 [P] ───┘
        ├──→ T010 [P] ─────────────────────────┐
        └──→ T013 [P]                           │
T005 → T006 → T011                              │
T005 → T007 [P], T008 [P] → T009 ───────────────┤
T005 → T012 ────────────────────────────────────┤
T009 + T010 + T012 → T014 → T015, T016, T017 [P]│
T001..T017 → T018 → T019 → T020 ;  T018 → T021
```

- **US1** (T006) es P1 y depende de T005; **US2** (T007, T008, T009) es P1; **US3** (T010 + T014) es P1; **US4** (T011) y **US5** (T012 a T015) son P2.
- **MVP**: T001 a T009 y T012 a T015 cubren AC-01, AC-02 y AC-03; T016 y T018 con la CI humana cubren AC-04.
- Paralelo: T003, T010 y T013 no comparten archivos con otras tareas; T007 y T008 son independientes entre sí.

## Estimación frente al presupuesto

| Concepto | Minutos |
|---|---|
| Sp2-01 a Sp2-05 presupuestados | 630 |
| Tareas F5 (T002, T004 a T012, T014 a T016, T018) | 480 |
| Transversales (T001, T003, T013, T017) | 95 |
| **Total de tareas de trabajo** | **575** |

Dentro del presupuesto por 55 min; las tres tareas humanas (T019 a T021) no se cuentan.
