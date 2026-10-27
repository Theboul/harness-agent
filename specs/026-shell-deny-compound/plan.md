# Implementation Plan: HU-05-02 — Lista de denegados y análisis de comandos compuestos

**Branch**: `gustavo` (directorio de la spec: `026-shell-deny-compound`) | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/026-shell-deny-compound/spec.md`

## Summary

Un analizador de comandos propio, manual por caracteres y sin `shlex`, con dos dialectos (bash y PowerShell), separa el comando del shell en partes. Reconoce comillas, sustituciones, redirecciones y otros intérpretes, y marca lo que no entiende. Las entradas de la lista de denegados (la base de HU-01-04, ampliada en `adapters/system/denied_commands.py`, más `[permissions] deny_commands`) se **compilan con ese mismo analizador** a reglas de seis tipos: programa, objetivo, prefijo, subcomando, redirección y literal.

Una política nueva, `CommandPolicy`, en `core/permissions/`:

- **deniega** sin consultar a la política envuelta si algún texto ejecutable contiene un comando de la lista;
- convierte en **preguntar** cualquier «permitir» de un comando que no entiende;
- deja pasar las demás decisiones.

`bootstrap.py` monta `ProtectedPolicy(CommandPolicy(ExactCallPolicy(DefaultPermissionPolicy)))`. Así se cumple denegar > preguntar > permitir, y `ExactCallPolicy` (HU-11-03) solo puede subir a «permitir» lo que esta regla entiende y no deniega. AC-02 se cumple por estructura: el aprobador solo se consulta ante «preguntar». Lo demuestra una prueba de integración con `ApprovalGate` real.

## Technical Context

**Language/Version**: Python 3.12; solo biblioteca estándar en `core/` (sin `shlex`, research R3).

**Primary Dependencies**: ninguna nueva.

**Storage**: N/A.

**Testing**:

- pytest (`asyncio_mode = "auto"`);
- dobles de `tests/doubles/` (`ScriptedPolicy`, `FakeProvider`, `DummyApprover` o un aprobador de prueba local);
- `compose()` para la integración;
- shell real solo donde se comprueba que no se ejecuta nada.

Cobertura del 100 % en los módulos nuevos y en las líneas nuevas de los tocados. Sin red ni claves.

**Target Platform**: Windows y Linux (CI de ambos). El analizador es puro, así que sus pruebas no dependen de la plataforma; las de integración usan el intérprete nativo.

**Project Type**: Biblioteca/CLI hexagonal (`core/` + `adapters/` + `cli/` + `bootstrap.py`).

**Performance Goals**: análisis O(n) en la longitud del comando, que es como mucho de 8 000 caracteres; la recursión de las sustituciones está acotada a una profundidad de 8 (más es «no entendido»).

**Constraints**:

- sin cambios en `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/permissions/{policy,protected,exact_calls,approvals,rules}.py`, `cli/` ni `tests/doubles/`;
- `core/` no importa `adapters/`;
- mensajes en español sin reproducir el valor recibido;
- falla cerrada.

**Scale/Scope**:

- 3 módulos nuevos en `core/permissions/`;
- ampliación de `adapters/system/denied_commands.py` (datos y dos tablas);
- 1 campo aditivo en `config.py` y en `config.example.toml`;
- cableado en `bootstrap.py`;
- unos 8 archivos de pruebas y 1 guarda `ast`.

## Constitution Check

*GATE: pasa antes de la Fase 0 y se revisa tras la Fase 1.*

| Principio / regla | Cumplimiento |
|---|---|
| I. Una historia, una spec | Solo HU-05-02 (Sp2-24 a Sp2-28). Pasa |
| II. Microtareas de 15–40 min | 8 tareas de implementación (RITMO, 2 PHU) más el inicio, el cierre y las humanas. Pasa |
| III. Código modular, tipado, Python 3.12 | Tres módulos pequeños y puros, `frozen`, `mypy` del repo. Pasa |
| IV. Pruebas y CI multiplataforma | Analizador sin plataforma; integración en bash (CI Linux) y PowerShell. Pasa |
| V. Criterios inmutables | AC-01 a AC-04, el flujo y las reglas copiados tal cual (comprobado línea a línea). Pasa |
| VI. Disciplina de sprints | Quedan fuera las reglas de git (HU-11-02), el motivo en la CLI, generalizar aprobaciones y PD-06. Pasa |
| VII. Consulta quirúrgica | Ancla `#hu-05-02`, V-02, V-17, código consumido y specs 007/025. Pasa |
| VIII. PROGRESO.md | Fila a `En curso` al iniciar y a `En revisión` al cerrar, con observaciones. Tareas de inicio y cierre |
| IX. DoD estricta | Visto bueno de B, revisión cruzada (A o B), revisión del PO de la lista y CI remota: tareas humanas |
| X. `docs/archivo/` | No se toca. Pasa |
| V-02, V-17 | La denegación se decide antes que cualquier aprobación o permiso; las partes se evalúan por separado y lo no entendido se pregunta. Pasa |

**Hard Rules de las skills del proyecto**

- **`arquitectura-hexagonal-clean`**:
  - la regla (analizar y denegar) es pura y vive en `core/permissions/`;
  - no hay E/S nueva, así que no hace falta puerto ni adaptador nuevo: `CommandPolicy` implementa el puerto `PermissionPolicy`;
  - los datos de la plataforma están en `adapters/system/` y se unen en `bootstrap.py`;
  - dependencias por constructor; sin `print`, `os.environ` ni `config` en `core/`;
  - puertos, entidades y eventos sin cambios.
- **`estructura-carpetas-harness`**: rutas en la tabla de abajo; ninguna carpeta nueva.
- **`verificar-fronteras-hexagonales`**: los tres módulos entran en `test_permissions_boundaries.py` (imports, E/S y terminal de todo el paquete). Como esa guarda solo vigila el `ALLOW` de `policy.py` y no detecta E/S de la biblioteca estándar, se añade `tests/architecture/test_command_policy_boundaries.py`. Esa guarda comprueba:
  - los tres módulos no importan `adapters`, `config`, `cli`, `subprocess`, `socket`, `os`, `pathlib`, `shutil`, `shlex` ni terceros;
  - no nombran `"shell"`, `"command"` ni `"timeout_seconds"`;
  - `command_policy.py` nunca devuelve un `PermissionDecision.ALLOW` propio (solo lo compara);
  - todo `except` de `command_policy.py` termina en «no entendido» o `DENY`;
  - no hay métodos con estado.

  Lleva autoprueba y mutación.

### Recorrido de los *Decision Gates* (`arquitectura-hexagonal-clean`)

| Pregunta | Respuesta |
|---|---|
| ¿Regla o comportamiento nuevo? | Sí: analizador, reglas compiladas, lista en uso y política que endurece, en `core/permissions/`, exportados en `core/__init__.py` |
| ¿Necesita algo de fuera? | No: el texto llega en la `ToolCall`; la lista, el dialecto y los nombres de la herramienta, por constructor |
| ¿Quién lo implementa? | Nadie nuevo: los datos de la plataforma ya están en `adapters/system/denied_commands.py` y se amplían allí |
| ¿Cómo se conecta? | En `bootstrap.compose()`: dialecto de `interpreter_for(system)`, compilar base y `config.deny_commands`, `DenyList`, `CommandPolicy` entre `ProtectedPolicy` y `ExactCallPolicy` |
| ¿Cómo se prueba? | Núcleo con textos sintéticos y `ScriptedPolicy`; la unión, con `compose()`, `FakeProvider` y `ApprovalGate` real |
| ¿Es asíncrono? | No: `PermissionPolicy.evaluate` es síncrono |

### Lista de comprobación de `capas-y-reglas.md` (respuesta de diseño; se revisa de nuevo al cerrar)

| Punto | Resp. | Justificación |
|---|---|---|
| ¿Regla de negocio en `core/` y no en un adaptador? | Sí | Analizar, compilar y decidir viven en `core/permissions/`; el adaptador solo guarda datos (patrones, alias, sinónimos) |
| ¿Todo lo externo pasa por un puerto con tipos del dominio? | Sí | No hay nada externo nuevo |
| ¿Puertos, entidades y eventos sin cambios? | Sí | Ninguno cambia |
| ¿Errores sin reproducir valores? | Sí | `RuleError` y el `ConfigProblem` nuevo con mensaje fijo; la política no lanza |
| ¿Inyección por constructor y conexión solo en `bootstrap.py`? | Sí | `CommandPolicy(inner, deny_list, tool=, argument=)` solo en `compose()` |
| ¿Núcleo probado con dobles, sin red, disco ni claves? | Sí | Pruebas puras del analizador y de la política |
| ¿El adaptador real tiene prueba de contrato en `tests/contracts/`? | No aplica | No hay adaptador nuevo; la lista de datos tiene su prueba (todas sus entradas compilan con su dialecto) |
| ¿Pasa `pytest tests/architecture` (y la guarda nueva)? | Sí (diseño) | Guarda nueva; tarea de verificación |
| ¿El núcleo emite eventos en lugar de imprimir? | Sí | No imprime; ningún evento nuevo |
| ¿Lo público está exportado en `core/__init__.py`? | Sí | `Dialect`, `parse_command`, `ParsedCommand`, `CommandPart`, `compile_rule`, `CompiledRule`, `RuleKind`, `RuleError`, `DenyList` y `CommandPolicy` |
| ¿Falla cerrada y secretos? | Sí | Denegar gana; lo no entendido nunca se permite; ni el comando ni el patrón salen en mensajes |
| ¿Otro integrante revisó el cambio? | No (pendiente) | Tarea humana: revisión cruzada (A o B) |

**Resultado del gate**: pasa, sin violaciones. Desviaciones declaradas en *Complexity Tracking*.

## Project Structure

### Documentation (this feature)

```text
specs/026-shell-deny-compound/
├── spec.md
├── plan.md                 # este archivo
├── research.md             # Fase 0 (R1–R13)
├── data-model.md           # Fase 1
├── quickstart.md           # Fase 1
├── contracts/
│   ├── command_policy_contract.md         # API, garantías, cableado y ejemplos normativos
│   └── deny_commands_config_contract.md   # [permissions] deny_commands
├── checklists/requirements.md
└── tasks.md                # /speckit-tasks
```

### Source Code (repository root) y fila de `estructura-carpetas-harness` que justifica cada ruta

| Ruta | Nuevo/Mod. | Fila de la tabla |
|---|---|---|
| `src/harness_agent/core/permissions/command_parser.py` | Nuevo | Regla de negocio (permisos) → `core/permissions/` |
| `src/harness_agent/core/permissions/command_rules.py` | Nuevo | Ídem; `RuleError` en el mismo módulo (error de dominio del subpaquete) |
| `src/harness_agent/core/permissions/command_policy.py` | Nuevo | Ídem |
| `src/harness_agent/core/permissions/__init__.py`, `src/harness_agent/core/__init__.py` | Mod. (exportaciones) | Lo público se exporta en `core/__init__.py` |
| `src/harness_agent/adapters/system/denied_commands.py` | Mod. (entradas nuevas, `PROGRAM_ALIASES`, `OPTION_SYNONYMS` y sus funciones) | Datos de la plataforma → `adapters/system/` (ya existía, HU-01-04) |
| `src/harness_agent/adapters/system/__init__.py` | Mod. (exportaciones) | API pública del subpaquete |
| `src/harness_agent/config.py` | Mod. (aditivo: `deny_commands` en `[permissions]`, `HarnessConfig.deny_commands`) | Lectura de configuración → `config.py` (dueño B) |
| `config.example.toml` | Mod. (línea comentada) | Plantilla sin secretos |
| `src/harness_agent/bootstrap.py` | Mod. (compilación, `DenyList`, `CommandPolicy` en la cadena, `StartupError`) | Unir piezas → `bootstrap.py` |
| `tests/unit/core/permissions/test_command_parser.py` | Nuevo | `tests/unit/core/permissions/` |
| `tests/unit/core/permissions/test_command_rules.py` | Nuevo | Ídem |
| `tests/unit/core/permissions/test_command_policy.py` | Nuevo | Ídem |
| `tests/architecture/test_command_policy_boundaries.py` | Nuevo | Guarda `ast` de la frontera nueva |
| `tests/unit/adapters/system/test_denied_commands_compile.py` | Nuevo | `tests/unit/adapters/system/` (la base compila con su dialecto) |
| `tests/unit/test_config_deny_commands.py` | Nuevo | Junto a los `test_config_*.py` |
| `tests/unit/test_bootstrap_deny_commands.py` | Nuevo | Junto a los `test_bootstrap_*.py` |
| `tests/integration/test_command_policy_agent_loop.py` | Nuevo | `tests/integration/` (bucle real, `ApprovalGate` real, HU-11-03) |

**Pruebas existentes que pueden necesitar ajustar solo su lista esperada** (se declaran al cerrar):

- `tests/unit/adapters/tools/test_public_api.py` (`SYSTEM_API`: nombres nuevos de `adapters.system`);
- `tests/unit/test_config_schema.py` (si fija los campos de `[permissions]`).

`tests/unit/adapters/system/test_denied_commands.py` no debería cambiar.

**Archivos protegidos** (diff vacío al cerrar): `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `core/permissions/{policy,protected,exact_calls,approvals,rules}.py`, `src/harness_agent/cli/`, `tests/doubles/`, `docs/archivo/`.

### Decisiones clave (detalle en `research.md`)

1. **R1**: núcleo puro en `core/permissions/`; lista base y tablas de datos en `adapters/system/denied_commands.py`; `bootstrap.py` las inyecta.
2. **R2**: los patrones se compilan con el mismo analizador a seis tipos de regla; la bomba de procesos se conserva como `LITERAL` (solo admitido en la base).
3. **R3**: analizador manual por caracteres, sin `shlex`. Se pueden cumplir FR-004, FR-005, FR-005a y FR-005b (justificación en R3).
4. **R4 y R5**: lista explícita de lo no entendido, de lo analizable y de los envoltorios.
5. **R6 y R7**: objetivos completos, opciones combinadas, sinónimos y parámetros abreviados. **Desviación**: en PowerShell se acepta cualquier prefijo, aunque sea ambiguo, porque denegar es seguro.
6. **R8**: `ProtectedPolicy(CommandPolicy(ExactCallPolicy(DefaultPermissionPolicy)))`; la denegación se decide antes de consultar a `inner`.
7. **R9**: `HarnessConfig.deny_commands`, separado de `PermissionRules`; se compila en `bootstrap.py` y un error es `StartupError`.
8. **R11**: AC-02 con `ApprovalGate` real y una aprobación de sesión previa.

### Estimación de tareas (RITMO: 2 PHU → 8 de ≤ 40 min, TDD dentro de cada una)

| # | Tarea | Min | Sprint |
|---|---|---|---|
| T001 | Inicio: PROGRESO `En curso`, observaciones de inicio | 10 | — |
| T002 | Analizador I: tokens, comillas, separadores y partes en los dos dialectos, más lo no entendido | 40 | Sp2-26, Sp2-27 |
| T003 | Analizador II: sustituciones, otros intérpretes analizables, envoltorios, redirecciones y normalización del programa | 40 | Sp2-26, Sp2-27 |
| T004 | Reglas: `compile_rule` (seis tipos), objetivos completos, opciones, sinónimos, prefijos de PowerShell y `DenyList` | 40 | Sp2-24 |
| T005 | `CommandPolicy` más la guarda `test_command_policy_boundaries.py` (baterías SC-001, SC-002 y SC-004 con `ScriptedPolicy`) | 40 | Sp2-25, Sp2-27 |
| T006 | Lista base ampliada, alias y sinónimos en `adapters/system/denied_commands.py`; prueba de que todo compila; revisión de falsos positivos | 35 | Sp2-24 |
| T007 | `config.py` `deny_commands` (contrato), `config.example.toml` y cableado en `bootstrap.py` (`StartupError`) | 40 | Sp2-24, Sp2-25 |
| T008 | Integración: cadena real (zona protegida, `deny`, `ask`, HU-11-03), AC-02 con `ApprovalGate` real, sin filtrar datos y shell nativo sin ejecutar lo denegado | 40 | Sp2-28 |
| T009 | Fronteras y documentación (skills en las dos copias, `CLAUDE.md`, lista de comprobación) | 20 | — |
| T010 | Cierre: cuatro puertas, diff de protegidos, PROGRESO `En revisión` con observaciones | 30 | — |

Las tareas de implementación (T002–T008) son 7 bloques de módulo, más la de fronteras (T009). Total de Claude: unos 335 min frente a 510 min presupuestados (Sp2-24 a Sp2-28, 8,5 h).

### Tareas humanas (Claude no las marca)

- **H1**: visto bueno de **B** a la ampliación de `config.py` (`[permissions] deny_commands`) y de `config.example.toml`.
- **H2**: **revisión cruzada** por alguien de A o B (la historia es de C).
- **H3**: **revisión del PO** del contenido de la lista base por plataforma (pendiente desde HU-01-04) y de la desviación R7 (prefijos ambiguos de PowerShell).
- **H4**: **CI remota** en `ubuntu-latest` y `windows-latest`. La integración con bash real solo se ejecuta en Linux.

### Lista de comprobación revisada contra el código (T011, 2026-10-26)

| Punto | Resp. | Evidencia |
|---|---|---|
| Regla en `core/` | Sí | `core/permissions/command_parser.py`, `command_rules.py`, `command_policy.py`; `adapters/system/denied_commands.py` solo guarda datos; `bootstrap.py` compila y conecta (`_deny_list`) |
| Lo externo por puertos | Sí | Ningún import nuevo de E/S en `core/`; `test_command_policy_boundaries.py` lo vigila (sin `os`, `shlex`, `subprocess`, `sys`) |
| Puertos, entidades y eventos sin cambios | Sí | `git diff` vacío en `core/interfaces/`, `core/entities.py`, `core/events.py`, `core/loop.py` |
| Errores sin reproducir valores | Sí | `RuleError`, `ConfigProblem("permissions.deny_commands", …)` y `StartupError` con mensaje fijo; pruebas con `VALOR-DE-PRUEBA-123` |
| Inyección y conexión en `bootstrap.py` | Sí | `CommandPolicy(inner, deny_list, tool=, argument=)` solo en `compose()` |
| Núcleo con dobles | Sí | Pruebas puras del analizador, reglas y política con `ScriptedPolicy`; integración con un shell doble que registra (ningún comando peligroso se ejecuta) |
| Prueba de contrato del adaptador | No aplica | No hay adaptador nuevo; la lista de datos tiene `test_denied_commands_compile.py` |
| `pytest tests/architecture` | Sí | 445 pasadas (Windows), con la guarda nueva |
| Eventos en lugar de imprimir | Sí | Ningún evento nuevo; `PERMISSION_DECIDED` sin argumentos |
| Exportado en `core/__init__.py` | Sí | `CommandPart`, `CommandPolicy`, `CompiledRule`, `DenyList`, `Dialect`, `ParsedCommand`, `RuleError`, `RuleKind`, `compile_rule`, `parse_command` |
| Falla cerrada y secretos | Sí | Denegar antes de consultar; lo no entendido nunca se permite; excepción → «no entendido» o `DENY`; propiedades al azar sin fallos; detector de secretos sin hallazgos en los archivos nuevos |
| Revisión de otro integrante | No (pendiente) | H2 |

## Complexity Tracking

Sin violaciones de la constitución ni de las *Hard Rules*. Desviaciones declaradas (no son violaciones):

| Desviación | Por qué | Alternativa descartada |
|---|---|---|
| `config.py` (dueño B) gana `deny_commands` | Decisión Q1 del revisor (AC-01); aditivo; H1 | Sin campo (AC-01 solo con campos desconocidos) |
| `HarnessConfig.deny_commands` separado de `PermissionRules` | `PermissionRules` es del núcleo y su guarda fija `{"deny", "ask"}` | Ampliar `PermissionRules` (cambia un tipo del núcleo y una prueba) |
| Prefijos de parámetros de PowerShell aceptados aunque sean ambiguos | El núcleo no puede consultar los parámetros reales de cada cmdlet (FR-013); denegar de más es seguro | Exigir parámetros completos (dejaría pasar `-r -fo`) |
| La bomba de procesos se conserva como regla `LITERAL` | Su forma no es un comando entendible; no se pierde una entrada de HU-01-04 | Quitarla de la base |
| Posibles ajustes de listas esperadas (`test_public_api.py`, `test_config_schema.py`) | Nombres públicos y campos nuevos | — |
