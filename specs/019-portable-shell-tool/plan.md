# Implementation Plan: HU-01-04 — Herramienta de shell portable con tiempo límite

**Branch**: `feat/hu-01-04-shell-tool` (directorio de la spec: `019-portable-shell-tool`) | **Date**: 2026-10-24 | **Spec**: [specs/019-portable-shell-tool/spec.md](spec.md)

**Input**: Feature specification from `/specs/019-portable-shell-tool/spec.md`

**Directrices del responsable** (aclaraciones del 2026-10-24): la lista de comandos denegados por plataforma se publica como dato y **no** se aplica aquí (HU-05-02 la consume); el comando hereda el entorno del harness **sin** las variables de claves de los proveedores; riesgo alto y aprobación obligatoria hasta HU-05-02/HU-05-03; rama `feat/hu-01-04-shell-tool` en su propio worktree; commits sin coautor y en el estilo del proyecto.

---

## Summary

Se añaden piezas a dos paquetes de adaptadores ya existentes y una línea de composición, sin tocar `core/` ni ningún puerto:

1. `adapters/system/`: el motor de subprocesos con tiempo máximo (`SubprocessShell`, base común de `Shell`), sus dos implementaciones (`BashShell`, `PowerShellShell`), la elección según la plataforma (`select_shell`, `interpreter_for`), el control del árbol de procesos por plataforma, el entorno del hijo sin claves de proveedores, el colector de salida acotada, el texto de entorno para el modelo (`environment_notice`) y la lista por defecto de comandos denegados (dato).
2. `adapters/tools/shell.py`: `ShellTool` (`Tool`, nombre `shell`, riesgo alto). Recibe el `Shell` y el área por constructor, ejecuta el puerto síncrono en un hilo y traduce el resultado a un `ToolResult` con etiquetas.
3. `bootstrap.py`: elige el `Shell`, registra `ShellTool`, quita las claves de proveedor del entorno del hijo y antepone el mensaje de sistema con el entorno al historial de la sesión.

La verificación es el grueso del trabajo: la misma batería con procesos reales en Linux y en Windows (tiempo agotado, árbol de procesos, salida enorme, no ASCII, entorno filtrado) más pruebas con plataforma inyectada para lo que difiere.

---

## Technical Context

**Language/Version**: Python 3.12, única versión soportada (PD-07).

**Primary Dependencies**: solo biblioteca estándar (`subprocess`, `threading`, `signal`, `os`, `shutil`, `codecs`, `collections.abc`, `dataclasses`, `asyncio`). Sin dependencias nuevas de ejecución ni de desarrollo.

**Storage**: ninguno. El shell no persiste nada; la carpeta de partida es la raíz del área.

**Testing**: `pytest` + `pytest-asyncio` (`asyncio_mode=auto`); `tmp_path`; procesos reales con comandos comunes a bash y PowerShell (`echo`, `exit N`, `sleep`) y con `sys.executable`; plataforma, `which` y control de procesos inyectables para los casos de la otra plataforma; `AgentLoop`, `InMemoryToolRegistry`, `DefaultPermissionPolicy`, `ScriptedProvider` y `ScriptedPolicy` en integración.

**Target Platform**: Windows y Linux (matriz de CI: `ubuntu-latest` y `windows-latest`). macOS usa bash sin garantía ni CI.

**Project Type**: Biblioteca modular; los adaptadores son la capa exterior.

**Performance Goals**: el control vuelve en menos de `timeout + 3 s` tras un tiempo agotado (SC-001); memoria de salida acotada a unos `2 × max_output_chars` caracteres aunque el hijo escriba cientos de MB (SC-002).

**Constraints**:
1. `core/`, los puertos (`core/interfaces/`, incluido `Shell`/`ShellResult`), `core/events.py`, `core/loop.py`, `core/permissions/`, `core/tools/`, `cli/`, `config.py` y `tests/doubles/` quedan sin modificar.
2. `adapters/system/` y `adapters/tools/` importan solo biblioteca estándar, `harness_agent.core` (API pública) y su propio paquete (guarda `test_adapters_boundaries.py`); **`tools/` no importa `system/`**: se hablan por el puerto `Shell`. No leen `os.environ` ni configuración: el entorno, los nombres a quitar y la carpeta llegan por constructor.
3. No se aplica ninguna lista de denegación (decisión del responsable).
4. `mypy --strict` sobre `src` y `tests`; `ruff` a 100 columnas; identificadores en inglés, mensajes en español.
5. Falla cerrada: intérprete ausente, área ausente o error al arrancar → resultado de error etiquetado; nunca ejecución por otra vía.
6. Ninguna prueba usa red ni el repositorio como carpeta de trabajo de un comando, y ninguna deja procesos vivos.
7. Sin análisis de comandos (HU-05-02), sin aprobación interactiva (HU-05-03), sin límites del bucle (HU-01-06), sin recorte general (HU-02-02), sin ensamblador de contexto (HU-02-01), sin cambios de `config.py` (Principio VI).

**Scale/Scope**: 11 módulos de código nuevos en `adapters/system/` (`shell_limits.py`, `shell_errors.py`, `shell_output.py`, `shell_environment.py`, `process_control.py`, `subprocess_shell.py`, `bash_shell.py`, `powershell_shell.py`, `shell_selection.py`, `denied_commands.py`, `environment_notice.py`) y 1 en `adapters/tools/` (`shell.py`) más 2 constantes en `_limits.py`; cambios en `bootstrap.py`; unos 14 módulos de prueba nuevos; 1 sección de la guía; actualización de `PROGRESO.md` y de `arbol.md`.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / Restricción | Requisito | Pre-diseño | Post-diseño | Evidencia |
|---|---|---|---|---|
| I. Una historia por especificación | Solo HU-01-04 | Pasa | Pasa | Spec y plan solo de HU-01-04 |
| II. Microtareas de 15 a 40 min | Ninguna tarea pasa de 40 min (límite absoluto 60) | Pasa | Pasa | `tasks.md` |
| III. Núcleo modular, tipado, sin dependencias externas | `core/` intacto; adaptadores solo con biblioteca estándar y `harness_agent.core` | Pasa | Pasa | D1, D2; guarda de `adapters/` |
| IV. Pruebas, calidad y CI multiplataforma | Pruebas primero; ruff, mypy, pytest en Windows y Linux; el shell se prueba en ambos | Pasa | Pasa | D9, D10; Sp2-05 |
| V. Inmutabilidad de criterios | AC-01 a AC-04, reglas y flujo copiados tal cual | Pasa | Pasa | Spec |
| VI. Disciplina de sprints | Nada de otras historias del Sprint 2 ni futuras | Pasa | Pasa | Sin HU-05-02/03, 01-06, 02-01/02, `config.py` |
| VII. Consulta documental quirúrgica | Solo las fuentes necesarias | Pasa | Pasa | HU-01-04, Sp2-01 a Sp2-05, `Shell`, D-01, HU-01-03 como modelo |
| VIII. Registro en `docs/PROGRESO.md` | `En curso` y `En revisión` con registro | Pasa | Pasa | Primera y última tarea de trabajo |
| IX. Definition of Done estricta | Revisión cruzada y CI en ambos sistemas | Pasa | Pasa | Tareas humanas finales |
| X. Inmutabilidad de `docs/archivo/` | No se toca | Pasa | Pasa | `git diff` de cierre |
| Skill `arquitectura-hexagonal-clean` (Hard Rules) | Dependencias hacia el núcleo; lo externo (procesos) por un puerto (`Shell`); sin reglas de negocio en el adaptador; errores externos traducidos; inyección por constructor; falla cerrada | Pasa | Pasa | D1–D6, D12; lista de abajo |
| Skill `estructura-carpetas-harness` (Hard Rules) | Cada archivo en su fila: código con `subprocess` → `adapters/system/`; herramienta nativa → `adapters/tools/`; cableado en `bootstrap.py`; prueba en la carpeta equivalente | Pasa | Pasa | Tabla «Ruta elegida» |
| Skill `verificar-fronteras-hexagonales` (Hard Rules) | Guardas `ast`; sin excepciones para que una violación pase | Pasa | Pasa | La guarda de `adapters/` ya cubre `system/` y `tools/`; se añade autoprueba de que `subprocess` está permitido solo ahí |
| V-02 Falla cerrada | Sin intérprete/área → error; sin aprobación → denegado | Pasa | Pasa | FR-010, FR-017, riesgo alto |
| V-08 Shell portable | Dos implementaciones, prefijo y CI en ambos sistemas | Pasa | Pasa | FR-007, FR-011, FR-023 |
| V-17 Permisos sobre texto libre | Fuera de alcance aquí: HU-05-02 | Pasa | Pasa | Riesgo alto → pregunta siempre |

No hay violaciones; la sección de complejidad no aplica. Discrepancias de la documentación que **no** impiden implementar y se registran: (1) el puerto `Shell` es síncrono y sin carpeta de trabajo ni entorno: se resuelve por constructor sin cambiarlo; (2) `docs/PROGRESO.md` propone `adapters/system/` y `adapters/tools/` como ubicación (se confirma); (3) la regla de negocio 3 (denegados por plataforma) se publica como dato, no se aplica.

---

## Decisiones de diseño

| ID | Decisión | Motivo |
|---|---|---|
| D1 | `SubprocessShell(Shell)` en `adapters/system/subprocess_shell.py` es la base común; `BashShell` y `PowerShellShell` solo aportan el nombre, el ejecutable candidato y la construcción de la línea de comandos (`_argv(command)`). | Una sola implementación del tiempo máximo, la salida y la terminación; las dos plataformas difieren solo en cómo se invoca el intérprete (V-08). |
| D2 | Las herramientas no importan `adapters/system/`: `ShellTool` depende del puerto `Shell`. Los errores de arranque se señalan con `ShellStartError(OSError)` (en `system/`); la herramienta captura `OSError` y `Exception` sin importarlos. | La guarda de `adapters/` prohíbe que `tools/` importe otro paquete de adaptadores. |
| D3 | No se modifica el puerto `Shell`. La carpeta de partida, el entorno, los nombres a quitar, la gracia y el máximo de salida llegan al constructor de cada implementación. | Los puertos solo cambian con acuerdo de A, B y C. Se anota como hallazgo. |
| D4 | Ejecución: `subprocess.Popen` con `stdin=DEVNULL`, `stdout=PIPE`, `stderr=STDOUT`, `cwd`, `env` filtrado, sin `shell=True` (se invoca el intérprete con argv explícito). Un hilo lector drena la tubería y alimenta un `OutputCollector`; el hilo llamador espera con `proc.wait(timeout)`. | Evita bloqueos de tubería llena y acota la memoria (FR-006). Sin `shell=True` no hay un segundo intérprete (cmd/sh) entre el modelo y el nuestro. |
| D5 | `OutputCollector` decodifica incrementalmente en UTF-8 con sustitución (`codecs.getincrementaldecoder`), cuenta los caracteres totales y retiene solo la cabeza (`max//2`) y la cola (`max - max//2`). El texto final, si el total supera el máximo, es `cabeza + aviso + cola` con una reserva fija para el aviso, de modo que **nunca supera `max_output_chars`**. | FR-006, FR-013, FR-014; el aviso dice cuántos caracteres se omitieron. |
| D6 | Terminación por `ProcessControl` (una estrategia por plataforma, elegida por un indicador `windows` inyectable como en `WorkspaceArea`). POSIX: `start_new_session=True`; `killpg(SIGTERM)`, gracia, `killpg(SIGKILL)`; al terminar normalmente también `killpg(SIGKILL)` para no dejar segundo plano vivo. Windows: `CREATE_NEW_PROCESS_GROUP \| CREATE_NO_WINDOW`; `CTRL_BREAK_EVENT`, gracia, `taskkill /PID n /T /F`. | D-01 / revisión conjunta: terminar el **árbol**, no solo el hijo directo. `taskkill /T` es biblioteca estándar y suficiente; el límite (huérfanos re-parentados) se documenta. |
| D7 | PowerShell: `powershell.exe` (o `pwsh` si existe) con `-NoLogo -NoProfile -NonInteractive -Command <guion>`, donde el guion = preludio (UTF-8 de salida, barra de progreso silenciada) + comando + epílogo que reenvía el último código nativo (o 1 si falló un cmdlet). Bash: `bash --noprofile --norc -c <command>`. Sonda real en Windows 10 (PowerShell 5.1): `-EncodedCommand` vuelca los errores como XML (`#< CLIXML`) por stderr redirigido y `-OutputFormat Text` no lo evita; `-Command` entrega texto plano, acentos correctos y códigos de salida fieles. | Calidad de la salida que ve el modelo y código de salida fiel (con `-Command` a secas se pierde `$LASTEXITCODE`, de ahí el epílogo). |
| D8 | `select_shell(system_name, *, cwd, ...)` devuelve `PowerShellShell` para `Windows`, `BashShell` para el resto; `interpreter_for(system_name)` devuelve solo el nombre (lo usa el prefijo aunque no haya área). El ejecutable se busca con un `which` inyectable; si no existe, `execute` lanza `ShellStartError` con el mensaje «intérprete no disponible» (sin ruta). | AC-02, FR-010; fallar cerrado, nunca caer a otro intérprete. |
| D9 | Pruebas con procesos reales (comunes): `echo`, `exit N`, `sleep` y `sys.executable` (en PowerShell se invoca con `& '…'`). La construcción de argv, el entorno y la terminación de la **otra** plataforma se prueban con `windows=True/False`, `which` y `ProcessControl` falsos. | AC-04; el mismo conjunto en ambos sistemas. |
| D10 | Las pruebas exclusivas de plataforma usan `pytest.mark.skipif(sys.platform ...)` con motivo y tienen su equivalente: POSIX → `SIGTERM` ignorado escala a `SIGKILL` (código -9); Windows → `taskkill /T` mata al nieto. La CI de `windows-latest` y `ubuntu-latest` ya existe y corre todo `tests/`: no cambia `ci.yml`. | AC-04; Sp2-05 se cumple con la suite común más las dos mitades marcadas. |
| D11 | `ShellTool` devuelve: éxito → `Código de salida: 0` + salida; código ≠ 0 → `[codigo_de_salida=N]` (error); tiempo agotado → `[tiempo_agotado]` (error) con la salida parcial; `OSError` de arranque → `[interprete_no_disponible]`; sin área → `[sin_area]`; cualquier otra `Exception` → `[error_de_shell]` sin texto de la excepción. Salida vacía → `(sin salida)`. | Convención de etiquetas de HU-01-03; mensajes sin rutas ni trazas. |
| D12 | `timeout_seconds` opcional con `minimum` > 0 y `maximum` = tope en el esquema (el registro rechaza lo no válido) y la herramienta acota por seguridad; por defecto 120 s, tope 600 s. | FR-005; el esquema es la primera barrera. |
| D13 | `environment_notice(system_name, interpreter)` en `adapters/system/environment_notice.py` devuelve un texto fijo en español; `bootstrap.py` lo coloca como primer `Message(Role.SYSTEM)` del historial (`Composition.history_prefix`). HU-02-01 lo recogerá. | AC-03 sin esperar al ensamblador de contexto; estable para el caché del proveedor; sin cambiar el bucle. |
| D14 | `DEFAULT_DENIED_COMMANDS` (`Mapping[str, tuple[DeniedCommand, ...]]` por intérprete) y `denied_commands_for(interpreter)` en `adapters/system/denied_commands.py`. Datos puros; nada del shell ni de la herramienta los lee. | Decisión del responsable (B); HU-05-02 los consume. |
| D15 | El entorno del hijo lo construye `child_environment(environ, removed, *, windows)`: copia sin las claves quitadas (insensible a mayúsculas en Windows). `bootstrap.py` pasa `os.environ` y `{v for v in PROVIDER_KEY_VARIABLES.values() if v}` de `config.py`. `compose()` gana el parámetro `environ`. | FR-010c; el adaptador no importa `config` ni lee `os.environ`. |
| D16 | La herramienta ejecuta `shell.execute` con `asyncio.to_thread`. Una cancelación a mitad de un comando no interrumpe el hilo: el tiempo máximo acota la espera (hallazgo para A: cancelar un turno aislado requeriría ampliar el puerto). | El puerto es síncrono (D-01 lo declara así para `Shell`). |
| D17 | Nombres: `ShellTool` (herramienta `shell`), `SubprocessShell`, `BashShell`, `PowerShellShell`, `ShellStartError`, `OutputCollector`, `ProcessControl`, `PosixProcessControl`, `WindowsProcessControl`. | Identificadores en inglés. |

---

## Verificación contra las skills del proyecto

Skills cargadas: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness` y `verificar-fronteras-hexagonales` (exigidas por `CLAUDE.md`).

### Decision Gates (`arquitectura-hexagonal-clean`)

| Pregunta | Resultado |
|---|---|
| ¿Es regla o comportamiento nuevo? | No hay regla de negocio nueva en el núcleo: la decisión de permitir/preguntar/denegar sigue en `core/permissions/` (riesgo alto → pregunta). El tiempo máximo, la terminación y el recorte son comportamiento de adaptador sobre un puerto existente. |
| ¿Necesita algo de fuera? | Sí, procesos del sistema. Usa los puertos existentes `Shell` y `Tool`; no se propone ningún puerto nuevo (se anotan las limitaciones del puerto como hallazgo). |
| ¿Quién lo implementa? | Adaptadores: `adapters/system/` (`BashShell`, `PowerShellShell`; usan `subprocess`) y `adapters/tools/` (`ShellTool`). |
| ¿Cómo se conecta? | Por constructor, en `bootstrap.py` (`compose()`), único lugar que une `select_shell`, `ShellTool` y el prefijo. |
| ¿Cómo se prueba? | Unitarias con procesos reales y dobles de plataforma; contrato común contra ambas implementaciones; integración con el bucle, la política y el registro reales; guarda `ast` existente. |
| ¿Es asíncrono? | `Tool.run` es `async` (ejecuta el puerto en un hilo); `Shell.execute` es síncrono, como declara el puerto. |

### Ruta elegida (`estructura-carpetas-harness`)

| Archivo nuevo | Fila de la tabla | Prueba equivalente |
|---|---|---|
| `adapters/system/subprocess_shell.py`, `bash_shell.py`, `powershell_shell.py`, `process_control.py`, `shell_output.py`, `shell_environment.py`, `shell_selection.py`, `shell_limits.py`, `shell_errors.py` | «Código con … `subprocess` … → `adapters/<subpaquete>/`» | `tests/unit/adapters/system/test_*shell*.py`, `tests/contracts/test_shell_contract.py` |
| `adapters/system/denied_commands.py`, `environment_notice.py` | Datos y texto del adaptador del sistema (sin lógica de negocio); mismo paquete que el shell que describen | `tests/unit/adapters/system/` |
| `adapters/tools/shell.py` (+ constantes en `_limits.py`) | «Herramienta nativa» → `adapters/tools/` (receta «Nueva herramienta nativa») | `tests/unit/adapters/tools/test_shell_tool.py`, `tests/integration/test_shell_agent_loop.py` |
| `bootstrap.py` (modificado) | «Unir piezas y elegir implementaciones» → `bootstrap.py` | `tests/integration/test_bootstrap.py` (existente, ampliada) y `tests/unit/test_bootstrap_shell.py` |

### Lista de comprobación (`capas-y-reglas.md`)

- [x] ¿La regla de negocio está en `core/` y no en un adaptador? Sí: la política decide en `core/permissions/`; el adaptador no decide permisos ni aplica la lista de denegados (D14).
- [x] ¿Todo lo externo pasa por un puerto con tipos del dominio? Sí: `Shell`/`ShellResult` y `Tool`/`ToolResult`; los procesos los toca solo el adaptador.
- [x] ¿Los puertos, entidades y eventos siguen sin cambios? Sí: ninguno se modifica (`git diff` de `core/` vacío). Las limitaciones del puerto `Shell` (síncrono, sin cwd/entorno/cancelación) se anotan como hallazgo, sin cambiarlo.
- [x] ¿Los errores externos se traducen a errores de dominio, sin reproducir valores recibidos? Sí: `OSError`/`Exception` de arranque → `ToolResult` con etiqueta y sin texto de la excepción ni rutas.
- [x] ¿Las dependencias se inyectan por constructor y se conectan solo en `bootstrap.py` (o en la prueba)? Sí: `Shell` y área a la herramienta; carpeta, entorno, claves a quitar, `which` y control de procesos a la implementación; la conexión está en `compose()`.
- [x] ¿El núcleo se probó con dobles, sin red, disco ni claves? Sí: el núcleo no cambia; los adaptadores se prueban sobre `tmp_path`, sin red ni claves.
- [x] ¿El adaptador real tiene prueba de contrato en `tests/contracts/`? Sí: `test_shell_contract.py` (la forma de `ShellResult` y el contrato del puerto contra ambas implementaciones).
- [x] ¿Pasa `pytest tests/architecture` (y la guarda nueva) en Windows y Linux? Se verifica al cierre; la guarda de `adapters/` ya vigila `system/` y `tools/`.
- [x] ¿El núcleo emite eventos en lugar de imprimir? Sin cambios en el núcleo; los adaptadores no imprimen (lo vigila la guarda).
- [x] ¿Lo público está exportado y los consumidores importan de `harness_agent.core`? Sí: `__all__` de `adapters/system` y `adapters/tools`; solo `from harness_agent.core import ...`.
- [x] ¿Se respetan las decisiones de diseño (falla cerrada, historial intacto, secretos)? Sí: sin intérprete/área → error; riesgo alto → pregunta; las claves de proveedor no llegan al hijo.
- [ ] ¿Otro integrante revisó el cambio? **No todavía** (tarea humana final).

### Fronteras (`verificar-fronteras-hexagonales`)

La guarda `tests/architecture/test_adapters_boundaries.py` ya recorre `adapters/system/` y `adapters/tools/`: stdlib + `harness_agent.core` + el propio paquete, sin leer entorno ni usar la terminal. Resultado esperado al cierre: verde sin cambios de la guarda; se añade una autoprueba que fija que `ShellTool` no importa `adapters/system/`. `bootstrap.py` está vigilado por `test_bootstrap_boundaries.py` (importa solo API pública salvo las excepciones ya declaradas): el cableado nuevo importa `harness_agent.adapters.system` y `harness_agent.adapters.tools` (ya permitidos) y `harness_agent.config.PROVIDER_KEY_VARIABLES`.

---

## Project Structure

### Documentation (this feature)

```text
specs/019-portable-shell-tool/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── shell_tool_contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
src/harness_agent/
├── bootstrap.py                    # MODIFICADO: elige el Shell, registra ShellTool, prefijo en el historial
└── adapters/
    ├── system/                     # existente (WorkspaceArea)
    │   ├── __init__.py             # + API pública del shell
    │   ├── shell_limits.py         # NUEVO: gracia, máximo de salida, reserva del aviso
    │   ├── shell_errors.py         # NUEVO: ShellStartError(OSError)
    │   ├── shell_output.py         # NUEVO: OutputCollector (cabeza + cola + aviso)
    │   ├── shell_environment.py    # NUEVO: child_environment
    │   ├── process_control.py      # NUEVO: ProcessControl, Posix…, Windows…
    │   ├── subprocess_shell.py     # NUEVO: SubprocessShell(Shell)
    │   ├── bash_shell.py           # NUEVO: BashShell
    │   ├── powershell_shell.py     # NUEVO: PowerShellShell
    │   ├── shell_selection.py      # NUEVO: select_shell, interpreter_for
    │   ├── denied_commands.py      # NUEVO: DeniedCommand, DEFAULT_DENIED_COMMANDS (dato)
    │   └── environment_notice.py   # NUEVO: environment_notice
    └── tools/                      # existente (cuatro herramientas de archivos)
        ├── __init__.py             # + ShellTool y sus límites
        ├── _limits.py              # + DEFAULT/MAX timeout y longitud del comando
        └── shell.py                # NUEVO: ShellTool

tests/
├── unit/adapters/system/
│   ├── test_shell_output.py
│   ├── test_shell_environment.py
│   ├── test_process_control.py
│   ├── test_subprocess_shell.py     # procesos reales, comunes a ambas plataformas
│   ├── test_bash_shell.py           # argv sintético + pruebas reales de Linux
│   ├── test_powershell_shell.py     # argv sintético + pruebas reales de Windows
│   ├── test_shell_selection.py
│   ├── test_denied_commands.py
│   └── test_environment_notice.py
├── unit/adapters/tools/
│   └── test_shell_tool.py
├── unit/test_bootstrap_shell.py     # composición: herramienta registrada, prefijo, entorno
├── contracts/
│   └── test_shell_contract.py
├── integration/
│   └── test_shell_agent_loop.py     # AC-01..AC-03 con bucle, política y registro reales
└── architecture/
    └── test_adapters_boundaries.py  # + autoprueba: ShellTool no importa adapters.system

docs/
├── guia-contratos-desarrollo.md    # + sección de la herramienta shell
└── PROGRESO.md                     # fila de HU-01-04, registro de cambios y observaciones
.claude/skills/estructura-carpetas-harness/references/arbol.md   # shell pasa de planeado a existente
.agents/skills/estructura-carpetas-harness/references/arbol.md   # misma copia
```

**Structure Decision**: Single project. No se crean carpetas nuevas: `adapters/system/` y `adapters/tools/` ya existen. `bootstrap.py` es la única raíz de composición y recibe el cableado (lo exige `CLAUDE.md`: «cada historia que añada una pieza nueva al arranque la cablea ahí»).

**Qué cambia en `bootstrap.py`**: `compose(..., environ=None)` (por defecto `os.environ`, que ya se lee en la raíz de composición); `shell = select_shell(platform.system(), cwd=area.root, environ=environ, removed_env=claves)` solo si hay área; `ShellTool(shell, area)` se registra siempre (sin área devuelve `[sin_area]`, igual que las herramientas de archivos); `Composition` gana `history_prefix: tuple[Message, ...]`; `run_session` inicia `history = list(composition.history_prefix)`; `main()` pasa su `environ` a `compose`. Las pruebas existentes de `compose` y `run_session` se ajustan solo si fijaban un historial vacío o la lista exacta de herramientas (se verifica antes; se documenta como desviación si ocurre).

---

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Un proceso nieto sobrevive a la terminación del árbol | POSIX: grupo de procesos con `SIGKILL` final; Windows: `taskkill /T /F`. Prueba real con nieto en ambas plataformas. Límite documentado: un huérfano re-parentado en Windows escapa a `/T` (mejora posterior con Job Objects). |
| Comillas, codificación o código de salida distintos en PowerShell | `-Command` con UTF-8 forzado y reenvío de `$LASTEXITCODE` (sondeado en Windows); pruebas reales en `windows-latest`; argv sintético en Linux. |
| `bash` de Windows (WSL) tomado por error | `select_shell` elige PowerShell en Windows; las pruebas reales de bash se omiten en Windows con motivo. |
| Hilo del shell sigue tras cancelar la sesión | El tiempo máximo acota la vida; hallazgo para A sobre cancelación de un solo turno. |
| Salida enorme llena la memoria o bloquea la tubería | Lectura continua en hilo con retención acotada (D4, D5); prueba de 100 MB. |
| Fuga de claves de proveedor al hijo | `child_environment` las quita; prueba con centinela y con `env`/`Get-ChildItem Env:` reales. |
| Pruebas lentas o inestables por la espera de terminación | Gracia inyectable corta en pruebas; plazos holgados (+3 s) sin dormir de más; limpieza de procesos en `finally`. |
| Pasar una prueba solo en una plataforma | Suite común sin marcas + equivalentes marcados; la CI remota se confirma al subir la rama (tarea humana). |
| La estimación de C se queda corta | Aviso de capacidad en `PROGRESO.md` si se supera el presupuesto (unos 630 min de referencia). |
