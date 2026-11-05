# Plan: HU-00-06

**Spec**: [spec.md](spec.md)

## Enfoque

Documentación guiada por el código. Orden de trabajo: (1) fijar el inventario con un script y la guarda de pruebas **primero** (en rojo, porque faltan el guion y el documento de arquitectura y porque el README conserva frases obsoletas); (2) reescribir el README; (3) escribir el guion; (4) dibujar la arquitectura comprobando cada nombre con `grep`; (5) ensayo limpio fuera del repo siguiendo el README al pie de la letra; (6) mutaciones de control sobre la guarda; (7) punteros, `PROGRESO.md` y cierre. No se toca `src/`. Si algo obligara a hacerlo, se detiene y se pregunta.

## Project Structure (estructura-carpetas-harness)

| Archivo | Fila de la tabla que lo justifica | Prueba / verificación |
|---|---|---|
| `README.md` (reestructurado) | Documentación de entrada del repo (no es código; sin carpeta nueva) | `tests/unit/test_docs_match_cli.py` (G1 a G4, G6) |
| `docs/guion-demostracion.md` (nuevo) | `docs/` es la carpeta de documentación del proyecto (`docs/00-indice.md` la lista) | G1 a G6 |
| `docs/arquitectura-implementada.md` (nuevo) | Ídem; archivo nuevo para no desfasar las referencias a `docs/02-arquitectura.md` (D-01) | G4 y G6; diagramas revisados con `grep` (T008, T009) |
| `docs/02-arquitectura.md` | Solo una línea de puntero al archivo nuevo | G6 (el enlace existe) |
| `docs/00-indice.md` | Una fila para el archivo nuevo y otra para el guion | — |
| `CLAUDE.md` | «Fuentes de verdad»: tres filas/frases nuevas (D-11) | — |
| `.env.example` | Plantilla en la raíz; solo el comentario del encabezado, si la edición está permitida (D-12) | `tests/architecture/test_no_secrets_in_repo.py` |
| `tests/unit/test_docs_match_cli.py` (nuevo) | Prueba de documentación de un solo archivo, como `tests/unit/test_litellm_quickstart_docs.py` | autopruebas + mutaciones de control |
| `docs/PROGRESO.md` | Estado de la historia (Principio VIII) | — |
| `specs/056-readme-demo-architecture/` | Artefactos Spec Kit de la historia | — |

No se crea ninguna carpeta nueva. Las skills no cambian (la estructura de carpetas no cambia).

## Constitution Check / Decision Gates (arquitectura-hexagonal-clean)

La historia no escribe código de producción, así que los *Decision Gates* no crean puertos ni adaptadores; se recorren igual:

| Pregunta | Resultado |
|---|---|
| ¿Es regla o comportamiento nuevo? | No: es documentación y una prueba |
| ¿Necesita algo de fuera? | No hay puerto nuevo; la prueba usa la API pública ya existente (`compose`, `run_session`, `parse_arguments`) |
| ¿Quién lo implementa? | La prueba vive en `tests/`; nada en `core/`, `adapters/` ni `cli/` |
| ¿Cómo se conecta? | No se conecta: no toca `bootstrap.py` |
| ¿Cómo se prueba? | La prueba de documentación es la guarda; se comprueba con mutaciones |

**Lista de comprobación de `capas-y-reglas.md` (sí/no):** ¿`core/` importa algo nuevo? **No** (sin cambios). ¿Se cambia un puerto, `entities.py` o `events.py`? **No**. ¿Algo imprime o lee de la terminal fuera de `cli/`? **No**. ¿Hay secretos en el repo? **No**: marcadores `<TU_CLAVE>` y nombres de variables. ¿Se añade una dependencia? **No**. ¿Se toca `bootstrap.py`? **No**. Ningún «no» necesita justificación fuera de «la historia no cambia código».

## Verificación de fronteras (verificar-fronteras-hexagonales)

La historia no toca `core/`, `cli/`, `adapters/`, `pyproject.toml` ni la CI, así que **no hay guarda de arquitectura nueva** (no se crea módulo en `core/`). Aun así T013 corre `pytest tests/architecture` completo (tras `git add -N .`) y comprueba que `tests/architecture/test_no_secrets_in_repo.py` pasa con los archivos nuevos. La prueba de documentación importa solo la API pública que ya usan otras pruebas de `tests/unit/`.

## Diseño de la guarda (`tests/unit/test_docs_match_cli.py`)

Documentos leídos: `README.md`, `docs/guion-demostracion.md`, `docs/arquitectura-implementada.md`. Sin red, sin proveedor real, sin claves.

**Extracción** (funciones puras, con autopruebas sobre texto sintético):

- `code_spans(text)`: lo que está entre acentos graves, en línea o en bloques ```` ``` ````, con el lenguaje del bloque.
- `slash_commands(text)`: tokens de la forma `^/[a-záéíóúñ]+$` que aparecen como primer token de un fragmento de código o de una línea de bloque; se ignoran las rutas (un segundo `/`) y los fragmentos que empiezan por `#`.
- `harness_flags(text)`: `--opciones` solo en líneas de código cuya primera palabra es `harness`, `python -m harness_agent` o `.\.venv\Scripts\harness` (D-06).
- `toml_sections(text)`: encabezados `[a]`, `[a.b]` de los bloques ```` ```toml ````.
- `story_lines(text)`: líneas que contienen un ID `HU-\d\d-\d\d(\.\d)?`, `HU-IN-\d\d` o `SPK-\d\d`.
- `steps(guion)`: bloques «Paso N» con sus campos `Tiempo`, `Comando`, `Salida esperada` y `Plan B`.

**Fuentes reales** (D-07):

- Comandos: `run_session` con una composición de prueba **con tarea** (como `tests/integration/test_console_commands.py`) y la entrada `/ayuda`; se parsean las líneas `  /comando  descripción`.
- Opciones: `parse_arguments([flag, valor])` no debe lanzar `StartupError` por «opción desconocida»; `--solo-lectura` se acepta sin valor.
- Secciones: `[sección]` y `# [sección]` de `config.example.toml`.
- Estados: la tabla de `docs/PROGRESO.md` (ID → estado) para G4.

**Reglas**

| Regla | Qué comprueba | Falla cuando |
|---|---|---|
| G1 | Cada comando `/` citado está en `/ayuda` | un comando inventado (p. ej. `/memoria`) |
| G2 | Cada `--opción` de una línea `harness` la acepta `parse_arguments` | una opción inventada |
| G3 | Cada `[sección]` toml citada está en `config.example.toml` | una sección inexistente |
| G4 | (a) ninguna línea con ID dice terminad/completad/hech; (b) toda línea con un ID `Pendiente` lleva marca de diferido; (c) ninguna frase obsoleta (F-01) | un ID `Pendiente` declarado terminado, o el README viejo |
| G5 | El guion tiene pasos con tiempo, comando, salida esperada y plan B; suma 10–15 min; sección «Lo que NO se demuestra» | un paso sin plan B, suma fuera de rango |
| G6 | Los enlaces relativos apuntan a archivos que existen | un enlace roto |

## Diseño del README (E1)

Orden de secciones (H2): `Resumen y estado` · `Requisitos e instalación` (Windows / Linux) · `Configuración mínima` · `Primer paso con un modelo real` (Ollama, Gemini) · `Arrancar una tarea` · `Comandos de la consola` · `Funciones opcionales` (subagentes, varios modelos, conmutación, memoria, auditoría y trazas, MCP) · `Solución de problemas` · `Pruebas` · `Documentación`. Se conservan el encabezado del equipo y la materia. Las secciones existentes de funciones opcionales se **mueven** sin cambiar su contenido salvo para corregir lo que ya no sea cierto. Cada bloque de comandos indica `PowerShell` o `bash` y la carpeta.

Los mensajes de «Solución de problemas» se **copian del código** (T005 hace `grep` en `bootstrap.py` y `config.py`): modelo `fake`, falta `config.toml`, falta la clave de un proveedor, `litellm` no instalado (`ProviderDependencyError`), `gh` ausente con `--issue`, ruta larga en Windows, `harness` no encontrado tras cambiar el punto de entrada.

## Diseño del guion (E2)

Archivo con: cabecera (qué se demuestra y cuánto dura) · **Antes de empezar** (no cuenta) · **Pasos** · **Tramos opcionales** · **Lo que NO se demuestra** · **Anexo A** (crear el repositorio de demostración, PowerShell y bash) · **Anexo B** (MCP, unos 3 min). Cada paso:

```
### Paso N — título (X min)
- Tiempo: X min
- Comando: `...`
- Salida esperada: ...
- Plan B: ...
```

Pasos previstos (los tiempos finales se fijan en T006 y T007; la suma obligatoria debe quedar entre 10 y 15 minutos):

| # | Paso | Tiempo previsto |
|---|---|---|
| 1 | Arranque con la tarea (`harness --tarea …`), `/ayuda`, `/model` | 1,0 |
| 2 | Ticket → agente → modificación, con aprobación (`1`) | 2,5 |
| 3 | Pruebas y verificación de criterios (`/criterios`: dos cumplidos, uno pendiente) | 2,0 |
| 4 | Rechazo con motivo (`3`) y lista de denegados | 1,0 |
| 5 | Revisión del diff, criterio semántico (`4 N`) y commit (`1`) | 1,5 |
| 6 | Pull Request (confirmación del push y de la creación) | 1,5 |
| 7 | Controles: `/plan` (solo lectura), `/compactar`, `/reanudar`, `/auditoria` y `/trazas` | 3,5 |
| 8 | Cierre y «Lo que NO se demuestra» | 0,75 |

Opcionales (no suman): conmutación por fallo (`[failover]`), memoria (`[memory]`). Total previsto obligatorio: 13,75 min.

## Diseño de la arquitectura implementada (E3)

Cinco diagramas Mermaid y una tabla de diferencias. Antes de dibujar, T008 y T009 comprueban con `grep` (y anotan en el propio documento, en una nota al pie) cada nombre usado. Lista de verificación mínima:

| Diagrama | Nombres a comprobar |
|---|---|
| Capas | carpetas reales de `src/harness_agent/` (`core`, `adapters` con `converters`, `mcp`, `providers`, `storage`, `system`, `tasks`, `tools`; `cli`; `config.py`; `config_mcp.py`; `bootstrap.py`), guardas de `tests/architecture/` |
| Bucle y permisos | `AgentLoop`, `ProtectedPolicy`, `CommandPolicy`, `GitPolicy`, `AskCeilingPolicy`, `ExactCallPolicy`, `DefaultPermissionPolicy`, `ReadOnlyPolicy`, `SwitchablePolicy`, `ArgumentsTap`, `ApprovalGate` (leídos del `compose()` real, no de `CLAUDE.md`) |
| Flujo de una petición | `run_session`, `_renew_or_report`, `ContextCompactor.before_turn`, `MemoryLoader.load_into`, `TracingProvider`, `FailoverProvider`, `RetryingProvider`, `ModelSwitch`, `LiteLLMProvider`, `TracingRegistry`, `InMemoryEventBus`, `attach_event_recorder`, `ConversationCapture`, `SqliteSessionStore` |
| SQLite v7 | tablas de `adapters/storage/_schema.py` (`sessions`, `events`, `criterios`, `criterios_sello`, `resumenes`, `contexto_esencial`, `mensajes`, `memorias`, `auditoria`, `trazas`) y `PRAGMA user_version` |
| Sesiones hijas | `LoopSubagentRunner`, `ChildSessions`, `RegistryView`, `SubagentApprover`, `sessions.parent_id`, `SessionCursor` |

## Tabla FR / AC → tarea → prueba

| Requisito | Tarea | Prueba o evidencia |
|---|---|---|
| FR-001 | T002 | script de inventario (salida pegada en T002) |
| FR-016, SC-004 | T003, T011 | `tests/unit/test_docs_match_cli.py` + 6 mutaciones |
| FR-002 a FR-011, AC-01 | T004, T005 | G1 a G4, G6; ensayo limpio de T010 |
| FR-012 a FR-014, AC-02 | T006, T007 | G1 a G6 sobre el guion |
| FR-015 | T008, T009 | G4 y G6; `grep` anotado |
| SC-003 | T010 | `pytest -m install` + recorrido en venv limpio |
| FR-017 | T003 a T013 | `tests/architecture/test_no_secrets_in_repo.py`; higiene por script |
| FR-018 | T001, T013 | `docs/PROGRESO.md` |
| FR-019, SC-005 | T013 | `git diff` de `src/` vacío; cuatro puertas; suite completa |
| SC-006 | H01 | persona ajena (humana) |

## Mutaciones de control (T011)

Sobre una copia temporal de los documentos (nunca sobre los originales) o con un parche reversible; la guarda debe fallar por la razón esperada y, sin la mutación, pasar:

| # | Mutación | Regla que debe fallar |
|---|---|---|
| M1 | Añadir `/memoria` al README | G1 |
| M2 | Añadir `harness --inventada` al README | G2 |
| M3 | Añadir un bloque toml con `[inventada]` | G3 |
| M4 | Escribir «HU-11-07 está terminada» | G4 |
| M5 | Quitar el plan B de un paso del guion | G5 |
| M6 | Enlace relativo a un archivo inexistente | G6 |

Estabilidad: la prueba nueva corre 10 veces seguidas sin fallos (no usa red ni esperas).

## Riesgos

| Riesgo | Mitigación |
|---|---|
| El README vuelve a desfasarse | La guarda corre en la CI de Ubuntu y Windows con el resto de `pytest` |
| El estado de las historias cambia antes de la demostración | T002 y T013 recalculan el inventario con un script; G4 lee `PROGRESO.md` en vivo |
| La demostración depende del modelo y de la red | Plan B por paso: sesión de respaldo y pruebas con proveedor simulado |
| Alguien lee el guion como promesa de historias pendientes | Sección «Lo que NO se demuestra» y G4 |
| Un falso positivo de G1 por una ruta que empieza con `/` | Regla de D-06 y autopruebas con rutas |
| El ensayo limpio no puede ejecutar una tarea (sin modelo local) | D-03: se anota y se deja a H01 |
| Capacidad de B: estimado 440 min frente a 420 presupuestados (+4,8 %) | Se avisa en `tasks.md`; la guarda y el ensayo limpio no estaban presupuestados |

## Archivos protegidos (no tocar)

Todo `src/`, `pyproject.toml`, `.github/workflows/ci.yml`, `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py`, `core/verification/`, `tests/doubles/`, `tests/spikes/mcp_demo_server.py`, `config.example.toml` (D-12) y `docs/archivo/`.
