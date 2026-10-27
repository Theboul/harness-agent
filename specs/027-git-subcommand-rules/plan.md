# Implementation Plan: HU-11-02 — Git mediante el shell con reglas de permisos por subcomando

**Branch**: `gustavo` (directorio de la spec: `027-git-subcommand-rules`) | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/027-git-subcommand-rules/spec.md`

## Summary

Un módulo puro nuevo, `core/permissions/git_rules.py`, clasifica cada parte git de un comando del shell en lectura, preguntar o denegar con una tabla inmutable de subcomandos. Lo hace apoyado en `parse_command` de HU-05-02, que ya normaliza `git`/`git.exe`, quita envoltorios y separa encadenados. Su política `GitPolicy` va entre `CommandPolicy` y `ExactCallPolicy`:

- deniega cualquier variante destructiva, en cualquier nivel;
- devuelve «preguntar» para escrituras, desconocidos y lecturas con efectos **sin consultar** a la política de dentro, así que la declaración de la tarea nunca sube un push o un merge;
- solo devuelve «permitir» cuando todo el comando son lecturas de la tabla y se entendió;
- en cualquier otro caso delega.

Además:

- `bootstrap.py` protege `.git` del área como dato (zona protegida de HU-11-01) y añade al prefijo las instrucciones de git;
- una única función pura `core/redaction.py::hide_url_credentials` oculta credenciales de URLs en la salida del shell (`ShellTool`);
- Sp2-45 se prueba con git real en un repositorio temporal aislado.

## Technical Context

**Language/Version**: Python 3.12; solo biblioteca estándar en `core/`.

**Primary Dependencies**: ninguna nueva. git solo es necesario para la prueba de Sp2-45, que se omite si no está.

**Storage**: N/A.

**Testing**:

- pytest con tablas de los ejemplos normativos;
- propiedades con entradas al azar y semilla fija;
- `ScriptedPolicy`;
- `compose()` con un shell doble que registra las llamadas;
- git real solo en `test_git_real_repository.py`.

Cobertura del 100 % en los módulos nuevos y en las líneas nuevas de los tocados.

**Target Platform**: Windows (PowerShell) y Linux (bash), CI de ambos.

**Project Type**: biblioteca/CLI hexagonal.

**Performance Goals**: clasificación O(número de argumentos); propiedades al azar en menos de unos segundos.

**Constraints**:

- sin cambios en `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/permissions/{policy,protected,exact_calls,approvals,rules,command_parser,command_rules,command_policy}.py`, `adapters/system/protected_paths.py`, `config.py`, `cli/` ni `tests/doubles/`;
- `core/` no importa `adapters/`;
- mensajes en español sin el valor recibido;
- falla cerrada.

**Scale/Scope**:

- 2 módulos nuevos de `core/` (`permissions/git_rules.py`, `redaction.py`);
- cambios pequeños en `core/permissions/__init__.py`, `core/__init__.py`, `adapters/tools/shell.py` (aplicar el ocultado) y `bootstrap.py`;
- unos 7 archivos de pruebas y 2 guardas `ast`.

## Constitution Check

*GATE: pasa antes de la Fase 0 y se revisa tras la Fase 1.*

| Principio / regla | Cumplimiento |
|---|---|
| I. Una historia, una spec | Solo HU-11-02 (Sp2-43 a Sp2-45). Pasa |
| II. Microtareas de 15–40 min | 7 tareas de implementación más el inicio, el cierre y las humanas (RITMO, 1 PHU). Pasa |
| III. Código modular, tipado, Python 3.12 | Módulos pequeños y puros, `mypy` del repo. Pasa |
| IV. Pruebas y CI multiplataforma | Clasificación sin plataforma; shell doble; git real con omisión limpia. Pasa |
| V. Criterios inmutables | AC-01, AC-02, el flujo y las reglas tal cual (comprobado). Pasa |
| VI. Disciplina de sprints | Fuera: flujos de PR, HU-10-02 completa, generalizar aprobaciones. Pasa |
| VII. Consulta quirúrgica | Ancla `#hu-11-02`, V-17, specs 025/026 y código consumido. Pasa |
| VIII. PROGRESO.md | Fila de inicio y cierre (`En revisión`), observaciones (incluida la nota para HU-10-02) |
| IX. DoD estricta | Tareas humanas H1–H5 |
| X. `docs/archivo/` | No se toca. Pasa |
| V-02, V-17 | Denegar gana; push y merge preguntan siempre (salvo el supuesto Q3 de reutilizar una aprobación de sesión idéntica, pendiente del PO). Pasa |

**Hard Rules de las skills del proyecto**

- **`arquitectura-hexagonal-clean`**: las reglas de git y el ocultado son puros y viven en `core/`. Sin E/S nueva, no hacen falta puertos ni adaptadores nuevos: `GitPolicy` implementa `PermissionPolicy`. La raíz de composición conecta y aporta los datos (`.git` protegida, dialecto, nombres de la herramienta). Puertos, entidades y eventos sin cambios.
- **`estructura-carpetas-harness`**: rutas en la tabla de abajo. **Desviación justificada** (research R6): la redacción de secretos tiene sitio planeado en `observability/`, pero `adapters/tools/` y `bootstrap.py` no pueden importarla sin abrir guardas, así que va en `core/redaction.py`; HU-10-02 la absorberá.
- **`verificar-fronteras-hexagonales`**: guardas nuevas.
  - `test_git_rules_boundaries.py`: stdlib y núcleo, sin `os`, `subprocess`, `shlex`, `adapters`, `config`; un único `ALLOW` dentro de `if self._only_reads(...) is True:`; todo `except` devuelve `ASK` o `DENY`; sin nombres del shell; sin estado.
  - `test_redaction_boundaries.py`: stdlib (`re`) y nada más, sin E/S.

  Las dos llevan autoprueba y mutación.

### Recorrido de los *Decision Gates* (`arquitectura-hexagonal-clean`)

| Pregunta | Respuesta |
|---|---|
| ¿Regla o comportamiento nuevo? | Sí: clasificación y política de git (`core/permissions/git_rules.py`) y ocultado de credenciales (`core/redaction.py`), exportados en `core/__init__.py` |
| ¿Necesita algo de fuera? | No: el texto llega en la `ToolCall`; el dialecto y los nombres de la herramienta, por constructor |
| ¿Quién lo implementa? | `ShellTool` aplica el ocultado a su salida; `ProtectedPaths` recibe `.git` como dato |
| ¿Cómo se conecta? | `compose()`: `GitPolicy` entre `CommandPolicy` y `ExactCallPolicy`; `.git` en las carpetas protegidas; `git_instructions()` en `history_prefix` |
| ¿Cómo se prueba? | Núcleo con `ScriptedPolicy` y textos; composición con un shell doble; git real solo para lecturas en Sp2-45 |
| ¿Es asíncrono? | No |

### Lista de comprobación de `capas-y-reglas.md` (respuesta de diseño; se revisa de nuevo al cerrar)

| Punto | Resp. | Justificación |
|---|---|---|
| ¿Regla de negocio en `core/`? | Sí | `git_rules.py`, `redaction.py` |
| ¿Lo externo pasa por puertos? | Sí | Nada externo nuevo; git real solo en una prueba |
| ¿Puertos, entidades y eventos sin cambios? | Sí | Ninguno cambia |
| ¿Errores sin reproducir valores? | Sí | La política no lanza; `classify_git` lanza mensajes fijos |
| ¿Inyección y conexión solo en `bootstrap.py`? | Sí | `GitPolicy(inner, dialect=, tool=, argument=)` solo en `compose()` |
| ¿Núcleo probado con dobles? | Sí | Pruebas puras y shell doble |
| ¿Prueba de contrato del adaptador? | No aplica | No hay adaptador nuevo; `ShellTool` gana el ocultado, cubierto por su prueba |
| ¿`pytest tests/architecture` con las guardas nuevas? | Sí (diseño) | Dos guardas nuevas |
| ¿Eventos en lugar de imprimir? | Sí | Ningún evento nuevo |
| ¿Lo público exportado en `core/__init__.py`? | Sí | `GitClass`, `GitPolicy`, `classify_git`, `git_instructions`, `HIDDEN_SECRET`, `hide_url_credentials` |
| ¿Falla cerrada y secretos? | Sí | Un único camino a `ALLOW`; excepción → `ASK`/`DENY`; credenciales ocultas |
| ¿Otro integrante revisó? | No (pendiente) | H1 |

**Resultado del gate**: pasa. Desviaciones en *Complexity Tracking*.

## Project Structure

### Documentation (this feature)

```text
specs/027-git-subcommand-rules/
├── spec.md · plan.md · research.md (R1–R10) · data-model.md · quickstart.md
├── contracts/git_policy_contract.md     # API, garantías, cableado y ejemplos normativos
├── checklists/requirements.md
└── tasks.md                             # /speckit-tasks
```

### Source Code y fila de `estructura-carpetas-harness` que justifica cada ruta

| Ruta | Nuevo/Mod. | Fila |
|---|---|---|
| `src/harness_agent/core/permissions/git_rules.py` | Nuevo | Regla de negocio (permisos) → `core/permissions/` |
| `src/harness_agent/core/redaction.py` | Nuevo | Regla pura del núcleo alcanzable por adaptadores (desviación R6 de «redacción → `observability/`») |
| `src/harness_agent/core/permissions/__init__.py`, `src/harness_agent/core/__init__.py` | Mod. (exportaciones) | Lo público se exporta en `core/__init__.py` |
| `src/harness_agent/adapters/tools/shell.py` | Mod. (aplicar `hide_url_credentials` a la salida) | Herramienta nativa → `adapters/tools/` |
| `src/harness_agent/bootstrap.py` | Mod. (`GitPolicy` en la cadena, `.git` protegida, instrucciones en el prefijo) | Unir piezas → `bootstrap.py` |
| `tests/unit/core/permissions/test_git_rules.py`, `test_git_policy.py`, `test_git_properties.py` | Nuevos | `tests/unit/core/permissions/` |
| `tests/unit/core/test_redaction.py` | Nuevo | `tests/unit/core/` |
| `tests/unit/adapters/tools/test_shell_redaction.py` | Nuevo | `tests/unit/adapters/tools/` |
| `tests/architecture/test_git_rules_boundaries.py`, `test_redaction_boundaries.py` | Nuevos | Guardas `ast` de las fronteras nuevas |
| `tests/unit/test_bootstrap_git.py` | Nuevo | Junto a los `test_bootstrap_*.py` |
| `tests/integration/test_git_policy_agent_loop.py` | Nuevo | `tests/integration/` (shell doble) |
| `tests/integration/test_git_real_repository.py` | Nuevo | `tests/integration/` (git real, Sp2-45) |

Pruebas existentes que pueden necesitar ajustar **solo** una lista o un conteo esperado (se declaran al cerrar):

- `tests/unit/test_bootstrap_task_commands.py`, que hoy asume que `history_prefix` tiene 1 o 2 mensajes y que con área ganará el de git;
- pruebas de `history_prefix` en `test_bootstrap_*.py` (por ejemplo «solo el aviso de entorno»).

Si el número de mensajes cambia, se ajusta solo esa aserción y se anota.

**Archivos protegidos** (diff vacío al cerrar): `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `core/permissions/{policy,protected,exact_calls,approvals,rules,command_parser,command_rules,command_policy}.py`, `adapters/system/protected_paths.py`, `config.py`, `cli/`, `tests/doubles/`, `docs/archivo/`.

### Estimación de tareas (RITMO: 1 PHU → 7 de ≤ 40 min, TDD en cada una)

| # | Tarea | Min | Sprint |
|---|---|---|---|
| T001 | Inicio: PROGRESO (fila de HU-11-02 a `En curso`, responsable B, quién la implementa), observaciones | 10 | — |
| T002 | `classify_git` y la tabla (globales, prefijos, cortas agrupadas, `--`, refspecs, listar o crear), tablas de los ejemplos normativos | 40 | Sp2-43 |
| T003 | `GitPolicy` (orden, `ASK` sin consultar a `inner`, único `ALLOW`, `GIT_*`, falla cerrada), propiedades al azar y guarda `test_git_rules_boundaries.py` | 40 | Sp2-43 |
| T004 | `core/redaction.py` y su guarda; `ShellTool` aplica el ocultado en sus tres ramas | 30 | Sp2-43 |
| T005 | `bootstrap.py`: cadena con `GitPolicy`, `.git` como dato, `git_instructions()` en el prefijo; ajustar las aserciones de prefijo afectadas | 35 | Sp2-44 |
| T006 | Integración con shell doble: AC-01 y AC-02, `ExactCallPolicy` no sube push o merge, aprobación de sesión (commit ≠ push; push idéntico reutiliza), `.git`, lista base y `ask`, credenciales, sin filtrar datos | 40 | Sp2-43, Sp2-45 |
| T007 | Repositorio temporal con git real (Sp2-45): lecturas sin cambiar el estado y recorte de `log` | 35 | Sp2-45 |
| T008 | Fronteras y documentación (skills en las dos copias, `CLAUDE.md`, lista de comprobación, detector de secretos sobre lo nuevo) | 20 | — |
| T009 | Cierre: cuatro puertas, diff de protegidos, PROGRESO `En revisión` con observaciones (Q3 para el PO, limitación de `.git`, nota para HU-10-02) | 30 | — |

Total de Claude: unos 280 min, frente a 240 min presupuestados (Sp2-43 a Sp2-45, 4 h). El presupuesto es un aviso.

### Tareas humanas (Claude no las marca)

- **H1**: revisión cruzada por alguien de otra área (A o C; la historia es de B).
- **H2**: revisión del PO de la tabla de subcomandos (lecturas, destructivas) y del supuesto Q3 (reutilizar la aprobación de sesión de un push o merge idénticos).
- **H3**: visto bueno de C a `core/permissions/git_rules.py`, a la protección de `.git` y al cambio en `ShellTool` (piezas de C).
- **H4**: avisar al responsable de HU-10-02 de `core/redaction.py::hide_url_credentials`, que debe absorber.
- **H5**: CI remota en `ubuntu-latest` y `windows-latest` (git está en los dos runners, así que la prueba de Sp2-45 se ejecuta).

No se toca `config.py`, así que no hace falta el visto bueno de B por configuración.

### Lista de comprobación revisada contra el código (T009, 2026-10-27)

| Punto | Resp. | Evidencia |
|---|---|---|
| Regla en `core/` | Sí | `core/permissions/git_table.py` (datos), `git_rules.py` (clasificación y política), `core/redaction.py`; `bootstrap.py` solo conecta y aporta datos (`.git`, listas de herramientas) |
| Lo externo por puertos | Sí | Ningún import de E/S en `core/` (guarda `test_git_rules_boundaries.py`); git real solo en una prueba |
| Puertos, entidades y eventos sin cambios | Sí | `git diff` vacío en `core/interfaces/`, `core/entities.py`, `core/events.py`, `core/loop.py` |
| Errores sin reproducir valores | Sí | `classify_git` con mensaje fijo; la política no lanza; pruebas con centinela |
| Inyección y conexión en `bootstrap.py` | Sí | `GitPolicy(inner, dialect=, tool=, argument=, deny_names=, ask_names=)` solo en `compose()` |
| Núcleo con dobles | Sí | `ScriptedPolicy` y textos; integración con shell doble; git real con ayudante restringido |
| Prueba de contrato del adaptador | No aplica | No hay adaptador nuevo; `ShellTool` gana el ocultado, cubierto por `test_shell_redaction.py` |
| `pytest tests/architecture` | Sí | 460 pasadas (Windows), con la guarda nueva |
| Eventos en lugar de imprimir | Sí | Ningún evento nuevo; pruebas de que ningún evento lleva credenciales ni comando |
| Exportado en `core/__init__.py` | Sí | `GitClass`, `GitPolicy`, `classify_git`, `git_instructions`, `HIDDEN_SECRET`, `hide_url_credentials` |
| Falla cerrada y secretos | Sí | Un único `ALLOW`; listas `deny`/`ask` aplicadas sin consultar a `inner`; propiedades al azar sin fallos; credenciales ocultas |
| Revisión de otro integrante | No (pendiente) | H1 |

## Complexity Tracking

| Desviación | Por qué | Alternativa descartada |
|---|---|---|
| `core/redaction.py` en lugar de `observability/` | `adapters/tools/` y `bootstrap.py` no pueden importar `observability` sin abrir guardas (R6) | Abrir las guardas de adaptadores y del arranque |
| Detección de `GIT_*` sobre el texto crudo | `parse_command` descarta las asignaciones y `command_parser.py` no se puede tocar (R5) | Ampliar `CommandPart` |
| `.git` tampoco se puede leer con las herramientas de archivos | La zona protegida no distingue lectura de escritura; decisión aceptada por el revisor | Cambiar `protected.py`/`protected_paths.py` |
| Excepción al clasificar → `ASK` (no `DENY`) | Decisión del revisor (restricción 3): «pregunta, o deniega si ya halló un destructivo» | `DENY` como en las demás políticas |
| Ajuste posible de aserciones sobre el tamaño de `history_prefix` | Un mensaje de sistema más con área (FR-010) | — |
