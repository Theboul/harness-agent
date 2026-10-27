# Implementation Plan: HU-11-03 — Pruebas y lint mediante el shell con salida recortada

**Branch**: `gustavo` (directorio de la spec: `025-test-lint-shell-commands`) | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/025-test-lint-shell-commands/spec.md`

## Summary

La tarea gana una sección opcional `## Comandos` con `pruebas:` y `lint:` (cada uno con `tiempo:` opcional; 300 s por defecto, tope 600 s). El analizador de tareas de HU-11-01 la lee de forma **aditiva**: una tarea sin la sección se interpreta igual que hoy y sus pruebas no cambian. Una política nueva y **genérica** de `core/permissions/`, `ExactCallPolicy`, envuelve a `DefaultPermissionPolicy` y convierte un «preguntar» en «permitir» solo cuando la llamada coincide con una `AllowedCall`. Coincide si la herramienta es la misma, el argumento tiene exactamente el mismo texto (sin espacios exteriores), no hay argumentos extra y el tiempo de la llamada no supera el declarado. Si la llamada no indica tiempo, cuenta el del shell por defecto. El núcleo **no conoce el shell**: la raíz de composición (`bootstrap.py`) traduce los comandos de la tarea a `AllowedCall` con el nombre, los argumentos y el tiempo por defecto de `ShellTool`, y deja la cadena `ProtectedPolicy(ExactCallPolicy(DefaultPermissionPolicy))`, de modo que se mantiene deny > ask > allow. Además añade al prefijo del historial un mensaje de sistema con los comandos permitidos (FR-008). AC-01 y AC-02 se demuestran con un proyecto de ejemplo real (prueba fallida y salida enorme) a través de `compose()` y el bucle real, sin aprobador.

## Technical Context

**Language/Version**: Python 3.12 (solo biblioteca estándar en `core/`).

**Primary Dependencies**: ninguna nueva. El proyecto de ejemplo usa `pytest` y `ruff`, ya fijados en `requirements-dev.txt`.

**Storage**: N/A. Los comandos no se guardan en SQLite: viven en el `TaskDefinition` validado al arrancar (FR-007). Ver observación para HU-03-04 en `research.md` R7.

**Testing**: pytest (`asyncio_mode = "auto"`), `FakeProvider`, `compose()` con `provider_factory` y `environ` inyectados, shell real de la plataforma para el proyecto de ejemplo. Cobertura del 100 % en los módulos tocados: `core/tasks/*`, `core/permissions/exact_calls.py` y lo nuevo de `bootstrap.py`. Sin red ni claves.

**Target Platform**: Windows (PowerShell) y Linux (bash), en la CI de ambos. Los comandos del ejemplo (`python -m pytest …`, `python -m ruff check …`) valen en los dos intérpretes.

**Project Type**: Biblioteca/CLI hexagonal (`core/` + `adapters/` + `cli/` + `bootstrap.py`).

**Performance Goals**: la decisión es O(número de comandos declarados), con un máximo de 2 comparaciones de texto.

**Constraints**: sin cambios en los puertos de `core/interfaces/`, en `core/events.py` ni en `core/loop.py`. Lo que se cambie en `core/tasks/` es aditivo y deja intacto `tests/unit/core/tasks/test_task_parser.py`. Mensajes de error en español y sin reproducir el valor recibido. Falla cerrada.

**Scale/Scope**: 2 módulos nuevos de `core/` (`core/tasks/commands.py`, `core/permissions/exact_calls.py`), cambios aditivos en `core/tasks/{definition,parser,errors,__init__}.py`, en `core/permissions/__init__.py`, en `core/__init__.py`, en `adapters/tools/shell.py` (dos constantes) y en `bootstrap.py`. Unos 5 archivos de pruebas y 1 guarda `ast`.

## Constitution Check

*GATE: pasa antes de la Fase 0 y se revisa tras la Fase 1.*

| Principio / regla | Cumplimiento |
|---|---|
| I. Una historia, una spec | Solo HU-11-03 (Sp2-46, Sp2-47, Sp2-48). Pasa |
| II. Microtareas de 15–40 min | `tasks.md` (regla RITMO: 8–10 tareas, TDD dentro de cada una). Pasa |
| III. Código modular, tipado, Python 3.12 | Dos módulos pequeños, tipos `frozen`, `mypy` del repo. Pasa |
| IV. Pruebas y CI multiplataforma | Ejemplo real en bash y PowerShell; el resto, sin plataforma. Pasa |
| V. Criterios inmutables | AC-01, AC-02, flujo y reglas copiados tal cual en la spec. Pasa |
| VI. Disciplina de sprints | No entran HU-11-04.1 (ejecutar criterios), HU-05-02 (análisis de comandos) ni HU-11-02 (git). Pasa |
| VII. Consulta quirúrgica | Ancla `#hu-11-03`, fichas de dependencias y código consumido. Pasa |
| VIII. PROGRESO.md | Fila a `En curso` al iniciar y a `En revisión` al cerrar, con el hallazgo de `conftest.py` (R-21/PD-06). Tareas de inicio y cierre |
| IX. DoD estricta | Visto bueno de A al formato, revisión cruzada (A o B) y CI remota quedan como tareas humanas |
| X. `docs/archivo/` | No se toca. Pasa |
| V-01…V-17 (falla cerrada, eventos, sin secretos) | La regla nueva solo puede convertir «preguntar» en «permitir» con coincidencia exacta; una excepción o un valor raro de la política envuelta → denegar. Ningún evento nuevo; las cargas no llevan el comando. Pasa |

**Hard Rules de las skills del proyecto**

- `arquitectura-hexagonal-clean`: las dos reglas (formato de la tarea y permiso por llamada exacta) son puras y viven en `core/`. No hay E/S nueva, así que no hace falta ni puerto ni adaptador nuevo: `ExactCallPolicy` implementa el puerto `PermissionPolicy` existente. El conocimiento del shell (nombre `shell`, argumentos `command`/`timeout_seconds`, tiempo por defecto de 120 s) queda en `adapters/tools/shell.py` y se une en `bootstrap.py`, la única raíz de composición. No hay `print`, `os.environ` ni `config` en `core/`. Puertos, entidades y eventos sin cambios.
- `estructura-carpetas-harness`: ver la tabla de rutas abajo. Ninguna carpeta nueva.
- `verificar-fronteras-hexagonales`: `core/tasks/commands.py` entra en `test_tasks_boundaries.py` (que cubre todo el paquete) y `core/permissions/exact_calls.py` en `test_permissions_boundaries.py` (imports, E/S y terminal de todo el paquete). Como `unguarded_allows` solo mira `policy.py`, se añade la guarda **nueva** `tests/architecture/test_exact_calls_boundaries.py`, que comprueba tres cosas: (a) el único `ALLOW` del módulo está dentro de una rama que exige que la política envuelta haya dicho `ASK` y que `_matches(call) is True`; (b) el módulo no nombra el shell (`"shell"`, `"command"`, `"timeout_seconds"`); (c) los métodos no guardan estado. Lleva autoprueba sobre fragmentos sintéticos.

### Recorrido de los *Decision Gates* (`arquitectura-hexagonal-clean`)

| Pregunta | Respuesta |
|---|---|
| ¿Regla o comportamiento nuevo? | Sí, dos: el formato `## Comandos` (`core/tasks/`) y el permiso por llamada exacta (`core/permissions/exact_calls.py`), ambos exportados en `core/__init__.py` |
| ¿Necesita algo de fuera? | No. La política solo ve la `ToolCall`; los comandos llegan por constructor |
| ¿Quién lo implementa? | Nadie nuevo: el shell existente (`ShellTool`) ejecuta; `ExactCallPolicy` implementa `PermissionPolicy` |
| ¿Cómo se conecta? | En `bootstrap.compose()`: `task.commands` → `AllowedCall` (con las constantes públicas de `adapters.tools`) → `ProtectedPolicy(ExactCallPolicy(DefaultPermissionPolicy(...), allowed, ask_names=config.permissions.ask), …)`, más el mensaje de comandos en `history_prefix` |
| ¿Cómo se prueba? | Núcleo con `ScriptedPolicy`/`ToolCall` sintéticas; la unión, con `compose()` y `FakeProvider`; AC-01/AC-02, con el shell real sobre un proyecto de ejemplo en `tmp_path` |
| ¿Es asíncrono? | No: `PermissionPolicy.evaluate` es síncrono |

### Lista de comprobación de `capas-y-reglas.md` (respuesta de diseño; se revisa de nuevo al cerrar)

| Punto | Resp. | Justificación |
|---|---|---|
| ¿Regla de negocio en `core/` y no en un adaptador? | Sí | Formato en `core/tasks/`; permiso en `core/permissions/exact_calls.py`. `bootstrap.py` solo traduce y conecta |
| ¿Todo lo externo pasa por un puerto con tipos del dominio? | Sí | No hay nada externo nuevo; el shell sigue tras el puerto `Shell` y la herramienta `Tool` |
| ¿Puertos, entidades y eventos sin cambios? | Sí | `core/interfaces/`, `core/entities.py` y `core/events.py` intactos |
| ¿Errores externos traducidos sin reproducir valores? | Sí | `TaskFormatError("comando_no_valido")` con mensaje fijo; la política no lanza (fallo → `DENY`) |
| ¿Inyección por constructor y conexión solo en `bootstrap.py`? | Sí | `ExactCallPolicy(inner, allowed, *, ask_names)`; se cablea en `compose()` |
| ¿Núcleo probado con dobles, sin red, disco ni claves? | Sí | Pruebas unitarias puras; el disco y el shell solo en la integración (`tmp_path`) |
| ¿El adaptador real tiene prueba de contrato en `tests/contracts/`? | No aplica | No se crea ni cambia un adaptador; `ShellTool` ya tiene su contrato (HU-01-04). Se añaden dos constantes cubiertas por la prueba de cableado |
| ¿Pasa `pytest tests/architecture` (y la guarda nueva)? | Sí (diseño) | Guarda nueva `test_exact_calls_boundaries.py`; se ejecuta en una tarea de verificación |
| ¿El núcleo emite eventos en lugar de imprimir? | Sí | No imprime; la decisión ya la publica el bucle (`PERMISSION_DECIDED`) sin el comando |
| ¿Lo público está exportado en `core/__init__.py`? | Sí | `AllowedCall`, `ExactCallPolicy`, `CommandKind`, `TaskCommand`, `commands_notice` y las constantes de tiempo |
| ¿Se respetan falla cerrada y secretos? | Sí | Solo coincidencia exacta; deny > ask > allow; el comando no va a eventos ni a mensajes de error |
| ¿Otro integrante revisó el cambio? | No (pendiente) | Tarea humana: revisión cruzada por A o B y visto bueno de A al formato |

**Resultado del gate**: pasa, sin violaciones que justificar.

## Project Structure

### Documentation (this feature)

```text
specs/025-test-lint-shell-commands/
├── spec.md
├── plan.md              # este archivo
├── research.md          # Fase 0
├── data-model.md        # Fase 1
├── quickstart.md        # Fase 1
├── contracts/
│   ├── task_commands_format.md     # sección «## Comandos» del archivo de la tarea
│   └── exact_call_policy.md        # ExactCallPolicy / AllowedCall y cableado
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks (no lo crea este comando)
```

### Source Code (repository root) y fila de `estructura-carpetas-harness` que justifica cada ruta

| Ruta | Nuevo/Mod. | Fila de la tabla |
|---|---|---|
| `src/harness_agent/core/tasks/commands.py` | Nuevo | Regla de negocio → subpaquete de `core/` (`core/tasks/`, HU-11-01) |
| `src/harness_agent/core/tasks/definition.py` | Mod. (aditivo: `TaskDefinition.commands = ()`) | Regla de negocio → `core/tasks/` |
| `src/harness_agent/core/tasks/parser.py` | Mod. (aditivo: sección `comandos`) | Regla de negocio → `core/tasks/` |
| `src/harness_agent/core/tasks/errors.py` | Mod. (código nuevo `comando_no_valido`; el mensaje de `seccion_desconocida` nombra Comandos) | Error de dominio → `errors.py` del subpaquete |
| `src/harness_agent/core/tasks/__init__.py`, `src/harness_agent/core/__init__.py` | Mod. (exportaciones) | Lo público se exporta en `core/__init__.py` |
| `src/harness_agent/core/permissions/exact_calls.py` | Nuevo | Regla de negocio (permisos) → `core/permissions/` |
| `src/harness_agent/core/permissions/__init__.py` | Mod. (exportaciones) | Ídem |
| `src/harness_agent/adapters/tools/shell.py`, `adapters/tools/__init__.py` | Mod. (constantes `COMMAND_ARGUMENT`, `TIMEOUT_ARGUMENT`, usadas en el esquema y exportadas) | Herramienta nativa → `adapters/tools/` |
| `src/harness_agent/bootstrap.py` | Mod. (traducción de comandos a `AllowedCall`, cadena de políticas, mensaje de comandos) | Unir piezas → `bootstrap.py` |
| `tests/unit/core/tasks/test_task_commands.py` | Nuevo | Prueba en la carpeta equivalente (`tests/unit/core/tasks/`) |
| `tests/unit/core/permissions/test_exact_calls.py` | Nuevo | `tests/unit/core/permissions/` |
| `tests/architecture/test_exact_calls_boundaries.py` | Nuevo | Guarda `ast` de la frontera nueva |
| `tests/unit/test_bootstrap_task_commands.py` | Nuevo | Junto a los `test_bootstrap_*.py` existentes |
| `tests/integration/test_task_commands_agent_loop.py` | Nuevo | `tests/integration/` (bucle real + shell real) |

No cambian: `tests/unit/core/tasks/test_task_parser.py`, `core/permissions/policy.py`, `core/permissions/protected.py`, `core/loop.py`, `core/interfaces/`, `core/events.py`, `tests/doubles/`, `cli/`, `config.py`.

**Archivos protegidos** (diff vacío al cerrar): `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `cli/`, `config.py`, `tests/doubles/`, `docs/archivo/`, `tests/unit/core/tasks/test_task_parser.py`.

### Decisiones clave (detalle en `research.md`)

1. **R1.** Formato `## Comandos`: elementos `- pruebas: <comando>` / `- lint: <comando>` en la columna 0 y una sublínea opcional con sangría `- tiempo: <segundos>`, igual que `comando:`/`espera:` de los criterios.
2. **R2.** La regla de «comando permitido» vive en `core/permissions/exact_calls.py` como política **genérica** de llamada exacta: no sabe qué es un shell. `bootstrap.py` aporta el nombre de la herramienta y de sus argumentos.
3. **R3.** Orden de la cadena: `ProtectedPolicy` → `ExactCallPolicy` → `DefaultPermissionPolicy`. `ExactCallPolicy` solo actúa sobre un `ASK` de la política envuelta, y nunca si la herramienta está en `permissions.ask`.
4. **R4.** El tiempo de la llamada se compara con el del comando; sin tiempo cuenta `DEFAULT_SHELL_TIMEOUT_SECONDS` (120). Un booleano, un no finito o un ≤ 0 no coincide.
5. **R5.** FR-008: mensaje `SYSTEM` con los comandos en `Composition.history_prefix`, tras el aviso de entorno (solo si la tarea declara comandos).
6. **R6.** Proyecto de ejemplo generado en `tmp_path` por la prueba de integración (sin carpeta de *fixtures* nueva).

### Lista de comprobación revisada contra el código (T006, 2026-10-26)

| Punto | Resp. | Evidencia |
|---|---|---|
| Regla en `core/` | Sí | `core/tasks/commands.py`, `core/tasks/parser.py` (sección `comandos`), `core/permissions/exact_calls.py`; `bootstrap.py` solo traduce (`_allowed_commands`) y conecta |
| Lo externo por puertos | Sí | Ningún import nuevo de E/S; `test_tasks_boundaries.py`, `test_permissions_boundaries.py` y `test_exact_calls_boundaries.py` en verde |
| Puertos, entidades y eventos sin cambios | Sí | `git diff` vacío en `core/interfaces/`, `core/entities.py`, `core/events.py`, `core/loop.py` |
| Errores sin reproducir valores | Sí | Pruebas con `VALOR-DE-PRUEBA-123` en `test_task_commands.py`, `test_exact_calls.py` y la integración (eventos sin el comando) |
| Inyección y conexión en `bootstrap.py` | Sí | `ExactCallPolicy(inner, allowed, ask_names=…)` construida solo en `compose()` |
| Núcleo con dobles | Sí | `ScriptedPolicy`, `ToolCall` sintéticas; shell real solo en `tests/integration/test_task_commands_agent_loop.py` |
| Prueba de contrato del adaptador | No aplica | No hay adaptador nuevo; `ShellTool` solo gana dos constantes, cubiertas por `test_bootstrap_task_commands.py` y `test_public_api.py` |
| `pytest tests/architecture` | Sí | 421 pasadas (Windows); Linux en la CI (T009) |
| Eventos en lugar de imprimir | Sí | Sin `print`; ningún evento nuevo |
| Exportado en `core/__init__.py` | Sí | `AllowedCall`, `ExactCallPolicy`, `CommandKind`, `TaskCommand`, `commands_notice`, `DEFAULT_COMMAND_TIMEOUT_SECONDS`, `MAX_COMMAND_TIMEOUT_SECONDS` |
| Falla cerrada y secretos | Sí | Excepción o valor raro → `DENY`; deny > ask > allow probado con la cadena real; detector de secretos aplicado también a los archivos nuevos (sin hallazgos) |
| Revisión de otro integrante | No (pendiente) | T008 (visto bueno de A y revisión cruzada) |

## Complexity Tracking

Sin violaciones de la constitución ni de las *Hard Rules*. Desviaciones declaradas (no son violaciones):

| Desviación | Por qué | Alternativa descartada |
|---|---|---|
| Se amplía el formato de la tarea (código de A, HU-11-01) | Decisión Q1 del revisor; cambio aditivo con las pruebas existentes intactas | `config.toml` (prohíbe reglas de permitir, HU-00-04/05-01) |
| Cambia el texto del mensaje `seccion_desconocida` (ahora nombra Comandos) | El mensaje enumera las secciones admitidas; dejarlo igual sería falso. Ninguna prueba existente comprueba ese texto (solo el código) | Mantener el texto desactualizado |
| `ExactCallPolicy` añade un segundo camino a `ALLOW` sin `AuthorizedArea.contains` | Es la regla de la historia (permitir el comando exacto). Lleva guarda propia y solo puede actuar sobre un `ASK` de la política envuelta | Meterlo en `policy.py` (rompería la invariante de HU-05-01 vigilada por `unguarded_allows`) |
