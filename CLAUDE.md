# CLAUDE.md — harness-agent

Contexto base para cada sesión que implementa **una** historia (feature). Léelo entero; el resto de la documentación se consulta solo en la parte que toque (Principio VII de la constitución).

## Qué es

Harness de agente en terminal (Python 3.12, sin dependencias de ejecución): bucle razonar–actuar–observar, herramientas, permisos que fallan cerrados, contexto, sesiones, memoria, proveedores LLM y MCP. Enfoque final: **Coding Harness** por tickets (ticket → cambios → pruebas → verificación de criterios → aprobación humana → PR). Proyecto universitario de 3 personas, 4 sprints semanales con cierre el 14/11/2026.

- Equipo por áreas: **A — Núcleo**, **B — Estado**, **C — Control y conexiones**. Product Owner: Brad. Todo cambio lo revisa alguien de otra área.
- Idioma: documentación, specs, mensajes al usuario y commits en **español**; identificadores, docstrings y comentarios del código en **inglés** (decisión 2026-10-17/18).

## Fuentes de verdad (en este orden)

| Qué | Dónde |
|---|---|
| Reglas no negociables | `.specify/memory/constitution.md` (Principios I–X, V-01 a V-17, DoD) |
| Estado de cada historia, evidencia y decisiones abiertas | `docs/PROGRESO.md` (**única** fuente de estado) |
| Ficha de la historia (AC, reglas, dependencias, responsable) | `docs/04a`…`04e-historias-*.md`, ancla `#hu-xx-yy` (ver `docs/00-indice.md` para saber en qué archivo está cada ID) |
| Contratos, eventos, modelo de datos SQLite | `docs/02-arquitectura.md` §4 |
| Tareas del sprint (`Sp1-xx`…) y presupuesto en minutos | `docs/03-plan-sprints.md` |
| Artefactos de una historia ya trabajada | `specs/NNN-slug/` (spec, plan, research, data-model, contracts/, tasks, quickstart) |
| Decisiones técnicas | `docs/decisiones/D-01-asyncio-cancelacion.md`, `D-02-preservacion-metadatos-conversion.md` |

**Nunca** editar `docs/archivo/` (Principio X). No leer los `04x` completos: ir al ancla de la historia.

## Al abrir una sesión para una feature

1. Localiza la historia en `docs/PROGRESO.md` (sprint, responsable, estado, observaciones de historias previas que la afectan).
2. Lee su ficha en `04x` y las fichas de sus dependencias («Depende de»). Los **criterios de aceptación y la prioridad son inmutables** sin permiso del PO (Principio V).
3. Comprueba que pertenece al **sprint activo**; no implementes nada de sprints futuros (Principio VI). Si una historia necesita algo de otra futura, déjalo como observación.
4. Busca si ya existe `specs/NNN-*` para ella; si no, sigue el flujo Spec Kit de abajo.
5. Revisa las observaciones en `PROGRESO.md` que la mencionan (p. ej. HU-05-01 dejó la convención `path` para HU-01-03).

## Skills obligatorias del proyecto

**Toda especificación, plan, lista de tareas, implementación y revisión DEBE seguir las tres skills del proyecto** de `.claude/skills/`. Cárgalas con la herramienta Skill (no basta con recordarlas) en la fase que indica la tabla y respeta sus *Hard Rules*, *Decision Gates* y *Output Contract*:

| Skill | Cuándo es obligatoria | Qué debe quedar escrito |
|---|---|---|
| `arquitectura-hexagonal-clean` (+ `references/capas-y-reglas.md`) | `/speckit-plan` (diseño de puertos/adaptadores), `/speckit-implement` y toda revisión de diseño | En `plan.md`: recorrido de los *Decision Gates* (regla en `core/`, puerto, adaptador, conexión, prueba) y la **lista de comprobación** de `capas-y-reglas.md` respondida sí/no, justificando cada «no». Al cerrar: la misma lista revisada contra el código |
| `estructura-carpetas-harness` (+ `references/arbol.md`, `references/recetas.md`) | `/speckit-plan` (sección *Project Structure*), `/speckit-tasks` y antes de crear o mover cualquier archivo | Ruta de cada archivo nuevo con la fila de la tabla que la justifica; si es una pieza nueva (herramienta, proveedor, almacén, comando, evento) seguir su receta; prueba en la carpeta equivalente de `tests/` |
| `verificar-fronteras-hexagonales` | Siempre que la historia toque `core/`, `cli/`, `adapters/`, `pyproject.toml` o la CI; como tarea de verificación en `tasks.md` y antes de cerrar | Resultado de `pytest tests/architecture` (y guarda `ast` nueva para la frontera del módulo que se crea), archivos que violen una regla y el puerto/evento propuesto |

Además, las skills `speckit-*` se ejecutan en el orden del flujo de abajo; ninguna fase se salta.

Las skills describen el código real (v1.1, 2026-10-23): `core/interfaces/` para los puertos, `core/entities.py`, pruebas `ast` de `tests/architecture/` en lugar de `import-linter` y carpetas marcadas como «planeadas» hasta que llegue su historia. Si encuentras una diferencia entre una skill y el código, manda el código: corrige la skill (en `.claude/skills/` y `.agents/skills/`) en el mismo cambio y anótalo en `PROGRESO.md`.

- `bootstrap.py` existe (HU-00-08, historia propuesta): es la única raíz de composición y conecta proveedor, herramientas, política, almacén, bus y CLI. Las pruebas de integración antiguas conectan a mano (`make_rig`); las nuevas pueden usar `compose()`. Cada historia que añada una pieza nueva al arranque (shell, `Approver`, límites) la cablea ahí.
- Los ejemplos de `arquitectura-hexagonal-clean/assets/` siguen los contratos reales, pero `adapter_litellm.py` y `bootstrap.py` son ilustrativos (el `bootstrap.py` real está en `src/harness_agent/`).
- Cada módulo nuevo de `core/` trae su guarda en `tests/architecture/`, a partir de `verificar-fronteras-hexagonales/assets/test_module_boundaries.py`.

## Flujo Spec Kit (una historia = una spec)

`/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-analyze` → `/speckit-implement` → `/speckit-converge`.

- En `/speckit-plan`, el *Constitution Check* incluye las *Hard Rules* de las tres skills del proyecto; una violación sin justificar detiene el plan.
- En `/speckit-tasks`, cada tarea que crea un archivo indica su ruta según `estructura-carpetas-harness`, y hay una tarea de verificación de fronteras (`verificar-fronteras-hexagonales`).
- En `/speckit-analyze` y `/speckit-converge`, se revisa además el cumplimiento de las skills (lista de comprobación de `capas-y-reglas.md`).
- Carpeta `specs/NNN-slug/` con numeración secuencial (existen 001–018, falta 008; la siguiente es 019). `.specify/feature.json` apunta a la feature activa: actualízalo al cambiar de historia.
- Tareas de **15–40 min** (máximo absoluto 60), cada una con pruebas primero: escribir la prueba, verla fallar **por la razón esperada**, implementar lo mínimo, pasar los cuatro comandos de calidad.
- Cada `tasks.md` incluye: mapeo a tareas `SpN-xx` con presupuesto, lista de **archivos protegidos**, tareas humanas finales (revisión cruzada y CI remota) que Claude **no** marca como hechas.
- `.claude/skills/` y `.agents/skills/` son copias para distintos agentes (Claude / Codex / agy); si modificas una skill propia del proyecto, actualiza ambas.

## Comandos

```powershell
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt; pip install -e . --no-deps   # igual que la CI

# Las cuatro puertas de calidad (las mismas de .github/workflows/ci.yml); todas deben dar exit 0
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing

pytest tests/architecture          # fronteras hexagonales (rápido; correr al tocar core/ o cli/)
python -m harness_agent            # o `harness` tras `pip install -e .`: sesión interactiva (necesita config.toml y la clave en el entorno)
pytest tests/unit/core/permissions/test_policy.py -k nombre   # un test concreto
```

CI: GitHub Actions en `ubuntu-latest` y `windows-latest`, solo Python 3.12, en push/PR a `main`. Omisiones esperadas en Windows local (32 con `pytest -rs`): los 5 tests de `tests/spikes/test_linux_sigterm_spike.py` (señales POSIX), unos 23 que necesitan crear enlaces simbólicos (se omiten si el sistema no concede el privilegio), 2 que necesitan `mkfifo` (tuberías POSIX) y 2 de nombres no válidos en Windows (nombre reservado y caracteres de control).

## Arquitectura (hexagonal) y reglas duras

```
cli ──▶ core ◀── adapters        config.py ──▶ core      (bootstrap.py: raíz de composición, la única que las une)
```

- `core/` importa **solo biblioteca estándar** y `harness_agent.core`. Nunca `adapters`, `cli`, `config`, `observability`, SDKs (`openai`, `anthropic`, `litellm`, `mcp`…) ni `sqlite3`. No lee archivos, entorno ni configuración; no usa `print`/`input`: **todo sale por el `EventBus`**.
- Consumidores (cli, adapters, tests) importan desde `harness_agent.core`, no de submódulos. Lo nuevo y público de `core/` se exporta en `core/__init__.py` (`__all__`).
- `Message`, `ToolCall`, `ToolResult`, `TokenUsage`, `Event` y demás tipos del dominio son `@dataclass(frozen=True)`.
- Puertos async: `Provider.complete`, `Tool.run`, `Approver.request`, `McpClient.*`, `SubagentRunner.execute`. El resto son síncronos.
- **Los puertos de `core/interfaces/` y el catálogo de 17 eventos (`core/events.py`) solo cambian con acuerdo de A, B y C.** Si una historia parece exigirlo, detente y déjalo como hallazgo.
- Dependencias por constructor (inyección); reloj, ids y entorno también se inyectan.
- Falla cerrada siempre: lo no previsto se pregunta o se deniega, nunca se permite.
- Sin secretos en el repo: claves solo en variables de entorno (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`); `config.toml`, `.env` y `.harness/` están ignorados. `tests/architecture/test_no_secrets_in_repo.py` lo vigila.
- Las fronteras se verifican con tests `ast` en `tests/architecture/` (no hay `import-linter`). Huecos conocidos (detalle en la skill `verificar-fronteras-hexagonales`): no hay lista blanca para todo `core/`, `forbidden_imports` deja pasar módulos estándar de E/S (`sqlite3`, `subprocess`) (`adapters/` ya está vigilado por `test_adapters_boundaries.py`: no importa `cli/` y `system/` y `tools/` solo usan stdlib y la API pública del núcleo).
- Árbol completo, existente y planeado, con la tabla de puertos por archivo: `.claude/skills/estructura-carpetas-harness/references/arbol.md`.

## Qué existe hoy (snapshot 2026-10-24; el estado real está en PROGRESO.md)

| Módulo | Historia | Notas clave |
|---|---|---|
| `core/entities.py`, `core/events.py`, `core/interfaces/` | HU-00-01 (A) | Contratos. HU-00-01 sigue **pendiente de ratificación técnica** de A, B y C (Sp1-03), lo que bloquea pasar cualquier historia a `Hecha` |
| `core/loop.py` — `AgentLoop(provider, registry, policy, bus, approver=None).run_turn(session_id=, task=, history=) -> TurnResult` | HU-01-01 (A) | Sin `approver`, resuelve `ask` como `deny` con `[approval_required_unavailable]`; con `approver`, espera la decisión y emite `APPROVAL_REQUESTED`/`APPROVAL_RESOLVED` (HU-05-03). No emite aún `LIMIT_REACHED`. Errores al modelo con prefijos `[unknown_tool]`, `[invalid_arguments]`, `[permission_denied]`, truncados a 500 caracteres |
| `core/permissions/approvals.py` — `ApprovalGate(approver).resolve(call, tool, emit_requested) -> ApprovalOutcome`; `cli/approval.py` — `ConsoleApprover(input_stream=None, output=None, *, max_attempts=3)` | HU-05-03 (C) | La puerta emite la solicitud por callback, recuerda las aprobaciones de sesión en memoria (herramienta + argumentos exactos) y falla cerrada (excepción → `approver_error`, resultado inválido → `invalid_result`; `CancelledError` se propaga). La CLI muestra herramienta, argumentos (valores con aspecto de clave ocultos) y efecto, y lee `1`/`2`/`3`; fin de entrada o 3 opciones inválidas = rechazar. Eventos: `APPROVAL_REQUESTED {call_id,name,risk}`, `APPROVAL_RESOLVED {call_id,name,action,approved,source}` sin argumentos. El rechazo con motivo lo añade HU-05-04 (fila siguiente) |
| `core/permissions/approvals.py` — `clean_reason(reason) -> str \| None`, `rejection_message(tool_name, reason) -> str`, `MAX_REASON_CHARS`, `MAX_REJECTION_CHARS`, `REJECTED_MARK`; `cli/approval.py` — `REASON_PROMPT` | HU-05-04 (A) | El motivo que la persona escribe tras elegir `3` vuelve al modelo en el resultado de herramienta del rechazo: `[approval_rejected] Tool '<nombre>' was rejected by the user.` (marca estable primero) más una advertencia fija y el motivo entre comillas simples. `clean_reason` lo deja en una línea, sin caracteres de control, formato, sustitutos ni de uso privado, con credenciales de URL ocultas (`hide_url_credentials`), `'` y `"` sustituidos por `’` y ≤ 200 caracteres (lee como mucho 1 000); el mensaje mide ≤ 500 y, sin motivo válido, es byte a byte el de HU-05-03. Cambio mínimo en `core/loop.py` (`_ask_approval`, rama de rechazo; autorizado por el usuario actuando como A, pendiente de ratificar). `approval_failed` nunca lleva motivo. El motivo no entra en eventos ni en mensajes de error ni se escribe en la terminal; vive solo en el historial en memoria (SQLite guarda `sessions`, `events` y criterios, no mensajes) y viaja al proveedor del modelo en las peticiones siguientes. Guarda: `tests/architecture/test_rejection_reason_boundaries.py` |
| `core/tools/` — `InMemoryToolRegistry`, `check_schema`, `validate_arguments` | HU-01-02 (C) | Validador JSON Schema propio (stdlib). Ojo: `tests/doubles/in_memory_registry.py` es **otro** `InMemoryToolRegistry` (doble sin validación) |
| `core/tools/output_limit.py` — `truncate_output`, `TruncatingTool`, `InMemoryToolRegistry(max_output_chars=…)`, `limits.max_tool_output_chars` | HU-02-02 (C) | Recorte general: con máximo, el registro sirve cada herramienta envuelta y recorta el `content` del `ToolResult` (principio + marca `[salida recortada: se omitieron N caracteres]` + final; `call_id` e `is_error` intactos). Sin máximo (`None`) `get` devuelve la instancia registrada. `compose()` siempre lo pasa (24 000 por defecto): deja margen sobre el cuerpo de 20 000 de las herramientas para no recortar dos veces. No cambia puertos ni el bucle |
| `core/in_memory_event_bus.py` — `InMemoryEventBus`, `EventDeliveryError` | HU-01-05 (B) | Un suscriptor que falla hace fallar `emit` (grupo de excepciones); `CancelledError`/`KeyboardInterrupt` se propagan sin agrupar |
| `core/permissions/` — `DefaultPermissionPolicy(registry, area=None, rules=PermissionRules(), *, allow_reads_in_area=True)` | HU-05-01 (C) | Orden deny > ask > allow. Solo dos «permitir»: escritura (riesgo medio) y lectura (riesgo bajo) **con `path` dentro de `AuthorizedArea`**. La regla de lectura es supuesto pendiente del PO |
| `config.py` — `load_config()`, `HarnessConfig`, `Secret` | HU-00-04 (B) | TOML (`config.toml` o `HARNESS_CONFIG`) + env. Rechaza campos desconocidos y campos con aspecto de clave. `[permissions]` solo admite `deny` y `ask` (nunca `allow`) |
| `cli/` — `run_cli(bus, run_turn, ...) -> int`, `attach_renderer`, `render_event` | HU-06-01 (C) | Solo stdlib + API pública de `core`. Comandos `/ayuda`, `/salir`. Ante excepción del turno: una línea con el tipo, exit 1 |
| `adapters/system/` — `WorkspaceArea` (área real); `adapters/tools/` — `leer_archivo`, `escribir_archivo`, `listar_archivos`, `buscar_texto` | HU-01-03 (C) | `WorkspaceArea(root, *, windows=None)` decide la contención sobre la ruta real y falla cerrado (reglas de Windows en `windows_path_problem`); las herramientas reciben el área (o `None`) por constructor, usan `path` y devuelven errores como `ToolResult` con etiqueta (`[fuera_del_area]`, `[sin_area]`…). Sin área, nada se ejecuta |
| `core/interfaces/provider.py` — `ProviderError`, `QuotaExceeded`, `ProviderTimeout`, `ProviderUnavailable`; `tests/doubles/fake_provider.py` — `FakeProvider(script)` | HU-00-03 (B) | Los errores canónicos son la única jerarquía que lanzan los proveedores hacia el núcleo (los adaptadores reales traducirán a ellos; HU-07-04/05 la ampliarán). `FakeProvider` reproduce un guion de `ProviderResponse` y `ProviderError` (uno por llamada, copias, sin red, reloj ni espera), valida el guion al construirse y lanza `ScriptExhausted` al agotarse. Es el doble oficial de proveedor; `ScriptedProvider` y `DummyProvider` siguen disponibles |
| `adapters/converters/` — OpenAI/Anthropic ↔ formato canónico, `ConversionEnvelope` + sidecar | HU-07-01 (A) | D-02. `from_openai_messages`/`from_anthropic_payload` están obsoletas: usar `to_*_envelope` + `restore_messages` |
| `adapters/providers/litellm_provider.py` — `LiteLLMProvider(model, *, max_output_tokens, api_key=None, completion=None)`, `ERROR_TABLE`, `ProviderDependencyError` | HU-07-02 (B; la implementa C) | Un solo adaptador para cualquier `<proveedor>/<modelo>` de LiteLLM, sin ramas ni nombres de proveedor en el código. `litellm[mcp]` es dependencia **opcional** (extra `litellm` de `pyproject.toml`, fijada con sus directas en `requirements-dev.txt`) y se carga con `importlib` solo aquí. El tope por llamada es `limits.max_output_tokens` (4096); `is_error` viaja como etiqueta `[tool_error]` en el contenido; los argumentos ilegibles llegan como `{"arguments_not_valid_json": …}` y el bucle los rechaza con `[invalid_arguments]`; los fallos se traducen a `ProviderError` por nombre de clase a lo largo del MRO (`RateLimitError` → `QuotaExceeded`, provisional hasta HU-07-04); la clave se depura de todo texto que el adaptador construye. `config.py` ganó `gemini`, `groq`, `openrouter`, `ollama` y `Limits.max_output_tokens`. Guarda: `tests/architecture/test_providers_boundaries.py` |
| `bootstrap.py` — `compose(config, *, provider_factory=None, clock=None, id_factory=None) -> Composition`, `run_session(...)`, `main(...) -> int`; `__main__.py`; comando `harness` | HU-00-08 (propuesta; C) | Única raíz de composición: proveedor (LiteLLM o el inyectado) → área y 4 herramientas → política → bus → almacén SQLite → sesión → registrador → bucle → `run_cli`. Solo conecta, no añade reglas. Fallos de arranque (también un modelo `fake/…` con el proveedor real): una línea «No se pudo iniciar: …» y salida 2; Ctrl-C termina con 130; la salida 0/1 la decide la CLI. Sin área de trabajo, aviso y las herramientas de archivos quedan denegadas por la política. Importa solo la API pública salvo `core.loop` y `adapters.providers.litellm_provider` (sin vía pública); lo vigila `test_bootstrap_boundaries.py` |
| `core/tasks/`, `core/permissions/protected.py`, `adapters/storage/{task_store,criteria_export}.py`, `adapters/system/protected_paths.py`, `adapters/tasks/`; `compose(..., task=)` | HU-11-01 (A) | Tarea con criterios protegidos. `parse_task(texto)` valida el formato (Markdown con `## Objetivo`, `## Criterios de aceptación`…) y falla con `TaskFormatError(code)`. El esquema SQLite pasa a **v2** (`criterios`, `criterios_sello`; migra v1 sin perder datos). `SqliteTaskStore` (implementa `TaskCriteria`) inicia la tarea de forma atómica (sesión + criterios + sello + copia `tareas/<sesión>/criterios.json` de solo lectura), `mark_passes` exige evidencia y `verify_export` restaura la copia alterada y emite `criteria_tampered` (solo el motivo). `ProtectedPolicy` envuelve la política: deniega herramientas con `path` en lo protegido (`ProtectedPaths`: la carpeta de la base de datos, o solo la base y `tareas/` si contiene al área de trabajo) y `shell` cuyo comando nombra la base, `criterios.json` o la carpeta; **limitación**: es una coincidencia literal, no analiza comandos compuestos (HU-05-02) ni sustituye al entorno aislado (PD-06 / HU-IN-02); el sello no lleva clave. `load_task_file` y `load_github_issue` (`gh` inyectable) leen la tarea. Añadió `SqliteSessionStore.connection()` y `EXPORT_FILE_NAME` a la API |
| `core/tasks/commands.py` — `TaskCommand`, `CommandKind`, `commands_notice`; `core/permissions/exact_calls.py` — `AllowedCall`, `ExactCallPolicy(inner, allowed, *, ask_names=())`; `adapters/tools` — `COMMAND_ARGUMENT`, `TIMEOUT_ARGUMENT` | HU-11-03 (C) | La tarea admite una sección opcional `## Comandos` (`- pruebas: …`, `- lint: …`, cada uno con `- tiempo: N` opcional, 300 s por defecto, tope 600); sin ella la tarea es la de HU-11-01. `ExactCallPolicy` es genérica (no conoce el shell): solo convierte el `ASK` de la política envuelta en `ALLOW` cuando la llamada es idéntica a una `AllowedCall` (misma herramienta, solo sus argumentos, mismo texto salvo espacios exteriores, tiempo ≤ el declarado; sin tiempo cuenta el del shell, 120 s); `DENY` y la lista `ask` prevalecen y un fallo es `DENY`. `compose()` monta `ProtectedPolicy(ExactCallPolicy(DefaultPermissionPolicy))` y añade a `history_prefix` un mensaje `SYSTEM` con los comandos. Los comandos de los criterios no se permiten solos (HU-11-04.1). Guarda: `test_exact_calls_boundaries.py`. **Riesgo abierto**: las pruebas ejecutan código editable por el agente (R-21, PD-06) |
| `core/permissions/command_parser.py` — `parse_command`, `Dialect`, `ParsedCommand`, `CommandPart`; `command_rules.py` — `compile_rule`, `CompiledRule`, `RuleKind`, `RuleError`, `DenyList`; `command_policy.py` — `CommandPolicy(inner, deny_list, *, tool, argument)`; `adapters/system/denied_commands.py` (lista base, `program_aliases_for`, `option_synonyms_for`); `HarnessConfig.deny_commands` | HU-05-02 (C) | Analizador propio por caracteres (bash y PowerShell, sin `shlex`): separa por `&&`, `||`, `;`, `|`, `&` y saltos de línea respetando comillas, quita envoltorios (`sudo`, `env`…), analiza el texto que se ejecuta (`$( )`, comillas invertidas, `bash -c`, `pwsh -Command`, `cmd /c`, destinos de redirección) y marca lo que no entiende (variables, `eval`, `iex`, grupos, comillas sin cerrar…). Cada entrada de la lista se escribe como el comando real y se compila a una regla (programa solo en posición de programa; objetivo solo raíz, `~` o unidad completa; `dd if=`; subcomando; redirección; literal solo en la base). `CommandPolicy` deniega antes de preguntar a la política envuelta y nunca deja «permitir» lo no entendido; `compose()` monta `ProtectedPolicy(CommandPolicy(ExactCallPolicy(DefaultPermissionPolicy)))`. `[permissions] deny_commands` solo añade (separado de `PermissionRules`); una entrada que no se entiende detiene el arranque. Guarda: `test_command_policy_boundaries.py` |
| `core/permissions/git_table.py` (datos), `core/permissions/git_rules.py` — `classify_git`, `GitClass`, `GitPolicy(inner, *, dialect, tool, argument, deny_names=(), ask_names=())`, `git_instructions`; `core/redaction.py` — `hide_url_credentials`, `HIDDEN_SECRET` | HU-11-02 (B; la implementa Claude) | Cada parte git de un comando del shell se clasifica con la tabla (revisable por el PO): **lectura** (`status`, `diff`, `log`, `show`, `blame`, `shortlog`, `describe`, `rev-parse`, `ls-files`, `grep` sin `-O`, y `branch`/`tag`/`stash list` cuando listan) se permite sola solo si **todo** el comando son lecturas y se entendió; **escritura**, desconocidos, alias, `-c`/globales desconocidas, `GIT_*` delante o lecturas con efectos (`--output`, `--ext-diff`, `--textconv`, `--no-index`, redirección) → preguntar **sin consultar a la política de dentro** (una declaración de la tarea nunca suelta un push o merge); **destructivas** (`reset --hard/--merge/--keep`, `clean`, todo push forzado o `--delete`/`:rama`/`--mirror`, `checkout -f/--/.`, `restore` sin `--staged`, `switch --discard-changes`, `branch -D`, `stash drop/clear`, `reflog expire`, `gc --prune=now`, `filter-branch`, `update-ref -d`) → denegar en cualquier nivel. Prefijos de opciones largas y cortas agrupadas cuentan. Las listas `deny`/`ask` de herramientas llegan por constructor. `compose()` protege `.git` del área como dato (tampoco legible con las herramientas de archivos), añade `git_instructions()` al prefijo con área y `ShellTool` oculta credenciales de URLs en su salida. Guarda: `test_git_rules_boundaries.py` |
| `core/limits.py` — `SessionLimits`, `LimitTracker`, `LimitReached`, `LimitKind`; `AgentLoop(…, limits=, clock=)`; `TurnStatus.LIMIT_REACHED` | HU-01-06 (A) | Antes de cada llamada al modelo el bucle (`_stop_at_limit`) consulta al contador: turnos (llamadas al modelo), tiempo (suma de lo que duran las tareas, reloj inyectado) y tokens (`usage.total_tokens` acumulado; es el presupuesto de toda la ejecución, no el tope de una llamada). Si se cumple (`>=`) publica `LIMIT_REACHED` `{limit, used, maximum}`, no llama al proveedor y devuelve `TurnStatus.LIMIT_REACHED`; el límite agotado sigue deteniendo las tareas siguientes de la sesión. Sin `limits` el bucle no aplica ninguno; `compose()` siempre los entrega. La CLI explica el límite y su máximo. Supuestos pendientes del PO (turno, sesión, tiempo) |
| `tests/spikes/` | SPK-01 (B), SPK-02 (A) | Base de D-01 (asyncio + cancelación) y hallazgos de LiteLLM (`docs/decisiones/SPK-01-…`); `tests/spikes/conftest.py` mantiene offline el spike de LiteLLM |
| `core/context/` — `estimate_text`/`estimate_message(s)`/`estimate_tool_definition`, `TokenEstimator`, `PrefixSpec`, `StablePrefix`, `build_prefix`, `ContextAssembler`, `AssembledContext` | HU-02-01 (B) | Estimación y prefijo estable, sin tocar el puerto `ContextManager`. Heurística `ceil(caracteres/4)` + 4 tokens por mensaje; `TokenEstimator` guarda un factor por sesión (consumo de entrada informado / estimación cruda, acotado a [0,25 ; 4,0]). `build_prefix(PrefixSpec(instrucciones, reglas, SO, intérprete), definiciones)` da un mensaje `SYSTEM` con secciones fijas + herramientas ordenadas por nombre + huella SHA-256. `ContextAssembler(spec, definitions, estimator=None)`: `assemble(session_id, history)` congela el prefijo en el primer ensamblado y devuelve `AssembledContext` (`provider_messages()`, `tools`, `estimated_tokens`); `record_usage(session_id, usage)` calibra. **Aún no está en el bucle**: integrarlo exige cambiar `core/loop.py` (A) y quitar `Composition.history_prefix` de `bootstrap.py` (ver PROGRESO). El bloque esencial (HU-02-06.1) irá como segundo mensaje `SYSTEM` |

Aún **no** hay: reanudar una sesión (HU-03-04) ni cancelar solo un turno.

### Convenciones ya acordadas que las próximas historias deben respetar

- Herramientas de archivos (HU-01-03): el argumento de ruta se llama **`path`** y cada herramienta declara su `RiskLevel` (escribir = MEDIUM; leer, listar, buscar = LOW). Herramientas con varias rutas → HIGH. Ver `specs/007-permission-policy/contracts/path_argument_convention.md`.
- Aprobación (HU-05-03): el bucle solo consulta la puerta (`ApprovalGate`, `core/permissions/approvals.py`) cuando la política dijo «preguntar»; una denegación nunca llega al aprobador. La aprobación de sesión cubre herramienta + argumentos **exactos**; generalizarla (misma ruta, programa y subcomando) espera a HU-05-02. HU-05-04 (en revisión) devuelve el motivo saneado al modelo con `rejection_message` y `ConsoleApprover` lo pide tras la opción `3` (lee la línea siguiente de la entrada). `main()` pasa `ConsoleApprover(input_stream, output)` a `compose(approver=...)`; `compose()` sin `approver` conserva la denegación de Sprint 1.
- Límites de sesión (HU-01-06): `core/limits.py` define `SessionLimits`; `compose()` mapea `config.Limits` (`max_turns`, `max_seconds`, `max_tokens`) y el núcleo no importa `config`. Un «turno» a efectos del límite es una llamada al modelo; los contadores viven en el `AgentLoop` (una sesión).
- Tope de tokens de **una** llamada al modelo: `limits.max_output_tokens`; `limits.max_tokens` es el presupuesto de toda la ejecución y nunca se usa como tope de una llamada (HU-07-02).
- LiteLLM (HU-07-02): `litellm` solo se carga con `importlib.import_module("litellm")` dentro de una función de `adapters/providers/`; pruebas con la función de llamada inyectable o con `tests/litellm_offline.py` (LiteLLM descarga el codificador `cl100k_base` en la primera llamada real); fijar `LITELLM_LOCAL_MODEL_COST_MAP=True` antes del primer import; en Windows, entorno virtual con `site-packages` bajo ~130 caracteres. Cuando exista `bootstrap.py`: construir `LiteLLMProvider` con `config.model`, `config.limits.max_output_tokens` y `config.api_key` (parámetro `api_key`).
- La carga de los eventos del bucle no incluye argumentos ni contenido (para no filtrar datos); la CLI no inventa campos que el evento no trae.
- Comandos de la tarea (HU-11-03): el shell solo se ejecuta sin preguntar para el texto **exacto** de `## Comandos` y con un tiempo que no supere el declarado; cualquier otra regla de permitir del shell (HU-05-02) debe envolver o preceder a `ExactCallPolicy` para que su denegación prevalezca. `main()` aún no carga tareas: se arrancan con `compose(task=…)`.
- Lista de denegados del shell (HU-05-02): denegar > preguntar > permitir. Toda regla nueva del shell que pueda **permitir** va dentro de `CommandPolicy` (envuelta por ella), nunca fuera; las reglas de git de HU-11-02 pueden añadir entradas de tipo subcomando o una política envuelta. Los comandos peligrosos solo se prueban analizándolos o con un shell doble que registra las llamadas: ninguna prueba los ejecuta.
- Cadena de políticas (HU-11-02): `ProtectedPolicy(CommandPolicy(GitPolicy(ExactCallPolicy(DefaultPermissionPolicy))))`. Una regla nueva que deba prevalecer sobre los comandos de la tarea va fuera de `ExactCallPolicy`; si necesita las listas `deny`/`ask` de herramientas, las recibe por constructor en lugar de consultar a la política de dentro. Git real en pruebas solo con un ayudante restringido en `tmp_path` y entorno aislado (ver `tests/integration/test_git_real_repository.py`).

## Pruebas

- Sin red, sin claves, sin proveedor real, sin consola: dobles de `tests/doubles/` (`ScriptedProvider`, `ScriptedPolicy`, `RecordingEventBus`, `FailingEventBus`, `DummyTool`, `RecordingTool`, `FailingTool`, `RaisingTool`, `BlockingTool`, `DummyApprover`, `DummyAuthorizedArea`, `InMemorySessionStore`…) y `make_rig` de `tests/core/support.py` para cablear el bucle.
- `tests/doubles/` está protegido por defecto: añade dobles nuevos solo si la spec lo justifica.
- Ubicación: `tests/unit/<ruta del módulo>/`, `tests/contracts/` (un contrato que se corre contra el doble y la implementación real), `tests/integration/` (con el `AgentLoop` real), `tests/architecture/` (guardas `ast` de la frontera nueva).
- Usa un valor centinela (`VALOR-DE-PRUEBA-123`) para comprobar que los mensajes de error y eventos no reproducen datos de entrada.
- No escribas literales que el detector de secretos marque (asignaciones a nombres tipo `secret`, `token`, `password` con valores largos).
- `asyncio_mode = "auto"`; cobertura objetivo del módulo nuevo: 100 % de líneas y ramas.
- Mensajes de error de validación: en español, sin reproducir el valor recibido.

## Archivos protegidos por defecto

Salvo que la historia lo exija y esté acordado: `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py` (dueño A), `core/in_memory_event_bus.py`, `cli/` (si la historia no es de CLI), `tests/doubles/`, `docs/archivo/`. Antes de cerrar, verifica:

```bash
base=$(git merge-base HEAD origin/main)
git diff --exit-code $base -- src/harness_agent/core/interfaces src/harness_agent/core/events.py tests/doubles docs/archivo
```

## Cerrar la historia

1. Los cuatro comandos de calidad en exit 0, y `pytest tests/architecture`. Entrega el *Output Contract* de las tres skills del proyecto (rutas y fila que las justifica, lista de comprobación sí/no, resultado de fronteras).
2. Actualizar `docs/PROGRESO.md` (Principio VIII): fila de la historia → **`En revisión`** (nunca `Hecha`: requiere revisión cruzada humana, CI en Windows y Linux y ratificación de HU-00-01), columnas *Archivos* y *Evidencia* (comandos y resultados reales), una línea por tarea en *Registro de cambios* y, si hay hallazgos para otras áreas, un bloque **Observaciones de HU-xx-yy**. La tabla *Resumen* solo cambia cuando algo pasa a `Hecha`.
3. Marcar en `tasks.md` solo las tareas realmente hechas, con su evidencia; dejar las humanas sin marcar.
4. Commit en español, estilo convencional con el ID: `feat(<área>): <descripción> (HU-xx-yy)`; `docs(...)`, `test(...)`, `ci(...)`, `chore(...)` según corresponda. Rama de trabajo `gustavo`; PR hacia `main`. Push, merge y aprobación de diff siempre con confirmación humana.
5. Reporta honestamente lo pendiente (revisión cruzada, CI remota, supuestos sin confirmar por el PO).

## Decisiones abiertas que conviene tener presentes

- HU-00-01 (contratos), D-01 (async) y D-02 (envelope) pendientes de aprobación técnica individual de A, B y C.
- D-IA: proveedores reales y presupuesto de API sin decidir → usar `fake/test` y dobles.
- PD-06: entorno aislado para el shell, pendiente del PO.
- Reparto del Sprint 4 por ratificar.
Detalle en `docs/PROGRESO.md` § Decisiones abiertas.
