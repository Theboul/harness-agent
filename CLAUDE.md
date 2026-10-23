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

- `bootstrap.py` aún no existe: la conexión se hace a mano en las pruebas de integración (`make_rig`) y el plan anota qué deberá conectar la raíz de composición.
- Los ejemplos de `arquitectura-hexagonal-clean/assets/` siguen los contratos reales, pero `adapter_litellm.py` y `bootstrap.py` son ilustrativos (usan piezas que aún no existen).
- Cada módulo nuevo de `core/` trae su guarda en `tests/architecture/`, a partir de `verificar-fronteras-hexagonales/assets/test_module_boundaries.py`.

## Flujo Spec Kit (una historia = una spec)

`/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-analyze` → `/speckit-implement` → `/speckit-converge`.

- En `/speckit-plan`, el *Constitution Check* incluye las *Hard Rules* de las tres skills del proyecto; una violación sin justificar detiene el plan.
- En `/speckit-tasks`, cada tarea que crea un archivo indica su ruta según `estructura-carpetas-harness`, y hay una tarea de verificación de fronteras (`verificar-fronteras-hexagonales`).
- En `/speckit-analyze` y `/speckit-converge`, se revisa además el cumplimiento de las skills (lista de comprobación de `capas-y-reglas.md`).
- Carpeta `specs/NNN-slug/` con numeración secuencial (existen 001–013, falta 008; la siguiente es 014). `.specify/feature.json` apunta a la feature activa: actualízalo al cambiar de historia.
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
pytest tests/unit/core/permissions/test_policy.py -k nombre   # un test concreto
```

CI: GitHub Actions en `ubuntu-latest` y `windows-latest`, solo Python 3.12, en push/PR a `main`. Omisiones esperadas en Windows: los 5 tests de `tests/spikes/test_linux_sigterm_spike.py` y 1 de enlace simbólico.

## Arquitectura (hexagonal) y reglas duras

```
cli ──▶ core ◀── adapters        config.py ──▶ core      (bootstrap.py: raíz de composición, aún no existe)
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

## Qué existe hoy (snapshot 2026-10-22; el estado real está en PROGRESO.md)

| Módulo | Historia | Notas clave |
|---|---|---|
| `core/entities.py`, `core/events.py`, `core/interfaces/` | HU-00-01 (A) | Contratos. HU-00-01 sigue **pendiente de ratificación técnica** de A, B y C (Sp1-03), lo que bloquea pasar cualquier historia a `Hecha` |
| `core/loop.py` — `AgentLoop(provider, registry, policy, bus).run_turn(session_id=, task=, history=) -> TurnResult` | HU-01-01 (A) | Resuelve `ask` como `deny` con `[approval_required_unavailable]` hasta HU-05-03. No emite aún `APPROVAL_REQUESTED` ni `LIMIT_REACHED`. Errores al modelo con prefijos `[unknown_tool]`, `[invalid_arguments]`, `[permission_denied]`, truncados a 500 caracteres |
| `core/tools/` — `InMemoryToolRegistry`, `check_schema`, `validate_arguments` | HU-01-02 (C) | Validador JSON Schema propio (stdlib). Ojo: `tests/doubles/in_memory_registry.py` es **otro** `InMemoryToolRegistry` (doble sin validación) |
| `core/in_memory_event_bus.py` — `InMemoryEventBus`, `EventDeliveryError` | HU-01-05 (B) | Un suscriptor que falla hace fallar `emit` (grupo de excepciones); `CancelledError`/`KeyboardInterrupt` se propagan sin agrupar |
| `core/permissions/` — `DefaultPermissionPolicy(registry, area=None, rules=PermissionRules(), *, allow_reads_in_area=True)` | HU-05-01 (C) | Orden deny > ask > allow. Solo dos «permitir»: escritura (riesgo medio) y lectura (riesgo bajo) **con `path` dentro de `AuthorizedArea`**. La regla de lectura es supuesto pendiente del PO |
| `config.py` — `load_config()`, `HarnessConfig`, `Secret` | HU-00-04 (B) | TOML (`config.toml` o `HARNESS_CONFIG`) + env. Rechaza campos desconocidos y campos con aspecto de clave. `[permissions]` solo admite `deny` y `ask` (nunca `allow`) |
| `cli/` — `run_cli(bus, run_turn, ...) -> int`, `attach_renderer`, `render_event` | HU-06-01 (C) | Solo stdlib + API pública de `core`. Comandos `/ayuda`, `/salir`. Ante excepción del turno: una línea con el tipo, exit 1 |
| `adapters/system/` — `WorkspaceArea` (área real); `adapters/tools/` — `leer_archivo`, `escribir_archivo`, `listar_archivos`, `buscar_texto` | HU-01-03 (C) | `WorkspaceArea(root, *, windows=None)` decide la contención sobre la ruta real y falla cerrado (reglas de Windows en `windows_path_problem`); las herramientas reciben el área (o `None`) por constructor, usan `path` y devuelven errores como `ToolResult` con etiqueta (`[fuera_del_area]`, `[sin_area]`…). Sin área, nada se ejecuta |
| `core/interfaces/provider.py` — `ProviderError`, `QuotaExceeded`, `ProviderTimeout`, `ProviderUnavailable`; `tests/doubles/fake_provider.py` — `FakeProvider(script)` | HU-00-03 (B) | Los errores canónicos son la única jerarquía que lanzan los proveedores hacia el núcleo (los adaptadores reales traducirán a ellos; HU-07-04/05 la ampliarán). `FakeProvider` reproduce un guion de `ProviderResponse` y `ProviderError` (uno por llamada, copias, sin red, reloj ni espera), valida el guion al construirse y lanza `ScriptExhausted` al agotarse. Es el doble oficial de proveedor; `ScriptedProvider` y `DummyProvider` siguen disponibles |
| `adapters/converters/` — OpenAI/Anthropic ↔ formato canónico, `ConversionEnvelope` + sidecar | HU-07-01 (A) | D-02. `from_openai_messages`/`from_anthropic_payload` están obsoletas: usar `to_*_envelope` + `restore_messages` |
| `tests/spikes/` | SPK-02 (A) | Base de D-01 (asyncio + cancelación) |

Aún **no** hay: adaptador LiteLLM (HU-07-02/SPK-01), SQLite (HU-03-01/02), shell (HU-01-04), aprobación interactiva (HU-05-03), límites (HU-01-06), raíz de composición ni punto de entrada ejecutable.

### Convenciones ya acordadas que las próximas historias deben respetar

- Herramientas de archivos (HU-01-03): el argumento de ruta se llama **`path`** y cada herramienta declara su `RiskLevel` (escribir = MEDIUM; leer, listar, buscar = LOW). Herramientas con varias rutas → HIGH. Ver `specs/007-permission-policy/contracts/path_argument_convention.md`.
- Cuando HU-05-03 emita `APPROVAL_REQUESTED`, invertir `test_observation_the_loop_does_not_emit_approval_requested_yet`.
- Cuando HU-01-06 defina `core/limits.py`, mapear `config.Limits` en la raíz de composición (o que `config.py` importe del núcleo; coordinar con A).
- La carga de los eventos del bucle no incluye argumentos ni contenido (para no filtrar datos); la CLI no inventa campos que el evento no trae.

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
