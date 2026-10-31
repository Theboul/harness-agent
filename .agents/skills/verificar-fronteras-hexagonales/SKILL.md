---
name: verificar-fronteras-hexagonales
description: "Trigger: core/, fronteras, arquitectura hexagonal, puerto, adaptador, imports del núcleo, tests/architecture. Verifica que src/harness_agent/core/ no dependa de adapters, cli, config, observability ni SDKs externos."
license: Apache-2.0
metadata:
  author: "harness-team"
  version: "1.1"
---

## Activation Contract

Cargar al:
- Añadir o modificar cualquier archivo en `src/harness_agent/core/`, `cli/` o `adapters/`.
- Añadir una dependencia en `pyproject.toml` o `requirements-dev.txt`.
- Tocar el pipeline de integración continua (`.github/workflows/ci.yml`).
- Mover archivos entre `core/`, `adapters/`, `cli/` y `config.py`.
- Generar `tasks.md` (debe haber una tarea de verificación de fronteras) y antes de cerrar una historia.
- Oír «solo necesito importar esto un momento en el núcleo».

## Hard Rules

- Las dependencias apuntan hacia el núcleo.
- `core/` importa solo biblioteca estándar y `harness_agent.core`. NO importa `harness_agent.adapters`, `harness_agent.cli`, `harness_agent.config`, `harness_agent.observability`, `harness_agent.bootstrap`, ni `litellm`, `openai`, `anthropic`, `google`, `mcp`, `sqlite3`, `tomllib`, `typer`, `click`, `rich` ni ningún paquete de terceros.
- `core/` NO lee configuración, entorno ni archivos (`os.environ`, `os.getenv`, `open`, `read_text`) y NO usa la terminal (`print`, `input`, `sys.stdout`); emite eventos por el bus.
- `cli/` importa solo biblioteca estándar, su propio paquete y nombres de `harness_agent.core.__all__` (`from harness_agent.core import X`), nunca un submódulo del núcleo, `adapters`, `config` ni `bootstrap`.
- `harness_agent.adapters` NO importa `harness_agent.cli`.
- Los tipos de dominio (mensajes, eventos, resultados de herramienta) son propios, nunca clases de un SDK. Los eventos solo se definen en `core/events.py`.
- NO añadir excepciones ni listas blancas a las guardas para que una violación pase.
- Las guardas se escriben con `ast` en `tests/architecture/` y corren en la CI (Ubuntu y Windows) con el resto de `pytest`. `import-linter` no está adoptado: añadirlo es un cambio de dependencias y de CI que requiere acuerdo del equipo.

## Guardas existentes (`tests/architecture/`)

| Archivo | Qué comprueba |
|---|---|
| `test_core_boundaries.py` | Todo `core/`: ningún SDK de LLM (lista `FORBIDDEN_PACKAGES`) |
| `test_cli_boundaries.py` | `core/` no importa `cli`; `cli/` solo stdlib y API pública del núcleo |
| `test_console_ux_boundaries.py` | Color y entorno (HU-06-05): solo `cli/style.py` tiene el carácter de escape ANSI y lee `os.environ`/`os.getenv`; `bootstrap.py` no llama a `print` |
| `test_core_reads_no_config.py` | Todo `core/`: no lee `config`, `tomllib`, entorno ni archivos (`find_config_reads`) |
| `test_core_no_terminal.py` | Todo `core/`: no imprime ni usa la terminal (`terminal_uses`); el bus en memoria no define eventos |
| `test_loop_boundaries.py` | `core/loop.py`: solo stdlib y núcleo (`forbidden_imports`), sin consola, `LIMIT_REACHED` solo desde `_stop_at_limit` (HU-01-06) y solo los parámetros de límite `limits` y `clock`, sin ciclos |
| `test_core_tools_stdlib_only.py` | `core/tools/`: lista blanca stdlib + núcleo |
| `test_output_limit_boundaries.py` | `core/tools/output_limit.py` (HU-02-02): solo stdlib y la API del núcleo (`entities`, `interfaces.tool`), sin E/S (ni `os`), sin config ni terminal, sin importar adaptadores |
| `test_permissions_boundaries.py` | `core/permissions/`: lista blanca, sin E/S, todo «permitir» protegido por `AuthorizedArea.contains` |
| `test_tasks_boundaries.py` | `core/tasks/` (HU-11-01): lista blanca stdlib + núcleo, sin E/S (ni `pathlib`, `subprocess`, `sqlite3`), sin entorno ni terminal |
| `test_approvals_boundaries.py` | `core/permissions/approvals.py` (HU-05-03): stdlib y núcleo, sin E/S, sin capturar la cancelación, nunca nombra `PermissionDecision`; en `core/loop.py` la puerta solo se alcanza desde `_ask_approval`, que solo se llama con un veredicto «pendiente», marcado únicamente en la rama `ASK` de `_decide` (una aprobación no anula una denegación) |
| `test_rejection_reason_boundaries.py` | Motivo del rechazo (HU-05-04): en `core/loop.py` `outcome.reason` y `rejection_message` solo se usan en `_ask_approval` y no en su rama de aprobación fallida; `clean_reason` y `rejection_message` son funciones síncronas de `approvals.py` que ocultan credenciales en el núcleo; `cli/approval.py` solo escribe texto fijo mientras lee el motivo (nunca lo reimprime) |
| `test_verification_boundaries.py` | Verificación de criterios (HU-11-04.1): `core/verification/` y `core/tasks/condition.py` solo stdlib y núcleo, sin E/S, sin entorno ni terminal y sin importar el bucle; `runner.py` sin contadores ni números (no hay tope propio de rondas: lo ponen los límites de sesión); **único escritor de passes**: en todo `src/` la única llamada a `mark_passes` está en `core/verification/verifier.py` y ningún módulo de herramientas lo nombra; el verificador nunca captura la cancelación y solo concede un permiso comparando con `is` |
| `test_limits_boundaries.py` | `core/limits.py` (HU-01-06): solo stdlib y `core.entities`, sin E/S, sin entorno ni terminal, sin tocar eventos (los publica el bucle) |
| `test_context_boundaries.py` | `core/context/` (HU-02-01): solo stdlib y núcleo, sin E/S (ni stdlib que la haga), sin entorno ni terminal, sin tokenizador de terceros |
| `test_compaction_boundaries.py` | Compactación automática (HU-02-03): `core/context/compactor.py` nunca captura `BaseException`, un `except` desnudo ni `CancelledError`; la única llamada a `complete` del paquete va sin herramientas; entre `commit_compaction` y el reemplazo de la vista no hay `await`; `cut.py` no tiene `raise`; nada de `core/context/` importa el bucle, `adapters`, `cli`, `core.permissions`, `core.tasks`, `core.verification` ni `TaskCriteria`; `adapters/storage/compaction_archive.py` no abre conexión propia (usa `.connection()`), no importa el bucle y no define el puerto `SessionStore`. Cada regla lleva su prueba de mutación |
| `test_essential_boundaries.py` | Contexto esencial (HU-02-06.1): `core/context/essential.py` y `renewer.py` solo stdlib y núcleo, sin E/S, entorno ni terminal, sin importar el bucle, `adapters`, `cli`, `core.permissions`, `core.tasks`, `core.verification` ni `TaskCriteria`; el renovador nunca captura `BaseException` ni `CancelledError` y los dos módulos no tienen `async def` ni `await`; `adapters/storage/essential_store.py` no abre conexión propia (usa `.connection()`), no importa el bucle y no define `SessionStore`; **solo la composición renueva**: en todo `src/` el nombre `EssentialRenewer` y las llamadas `.renew(` solo están en `bootstrap.py` (y en las exportaciones y la propia definición). Cada regla lleva su prueba de mutación |
| `test_conversation_boundaries.py` | Conversación reanudable (HU-03-04): `core/context/conversation.py` y `resume.py` solo stdlib y núcleo, sin E/S, entorno ni terminal, sin importar el bucle, `adapters`, `cli`, `core.permissions`, `core.tasks`, `core.verification` ni `TaskCriteria`, sin `async` ni captura de `BaseException`/`CancelledError`; `adapters/storage/message_store.py` no abre conexión propia (usa `.connection()`), no importa el bucle y no define `SessionStore`; **solo la composición** nombra `ConversationCapture` y `resume_session` (en todo `src/`); en `bootstrap.py` la captura se suscribe **antes** de `attach_event_recorder` y dentro de `run_session` y `_resume_command` ninguna función interna lee `composition.session_id`; la firma de `run_cli` solo ganó `argument_commands`. Cada regla lleva su prueba de mutación |
| `test_protected_policy_boundaries.py` | `core/permissions/protected.py` (HU-11-01): sin E/S, nunca nombra `ALLOW` y todo `except` devuelve `DENY` (solo puede endurecer) |
| `test_exact_calls_boundaries.py` | `core/permissions/exact_calls.py` (HU-11-03): stdlib y núcleo, sin E/S ni entorno ni terminal; su único `ALLOW` va dentro de `if self._matches(call) is True` y después de `if <decisión> is not PermissionDecision.ASK: return <decisión>` (solo convierte un «preguntar» en «permitir»); no nombra el shell (`"shell"`, `"command"`, `"timeout_seconds"`) y no guarda estado |
| `test_ask_ceiling_boundaries.py` | `core/permissions/ask_ceiling.py` (HU-08-03): stdlib y núcleo, sin E/S ni entorno ni terminal, sin nombres de herramientas, sin estado; `PermissionDecision.ALLOW` solo aparece como operando de una comparación (nunca se devuelve ni se asigna: solo endurece) y todo `except` devuelve `DENY` |
| `test_command_policy_boundaries.py` | `core/permissions/command_parser.py`, `command_rules.py` y `command_policy.py` (HU-05-02): stdlib y núcleo, sin E/S ni `os`, `shlex`, `subprocess`, `sys`, sin entorno ni terminal; `command_policy.py` solo compara con `ALLOW` (nunca lo devuelve ni lo asigna) y todo `except` devuelve `DENY` o «no entendido» (`False`); reglas y política no nombran `"shell"`, `"command"` ni `"timeout_seconds"` (el analizador sí reconoce la palabra `command` de bash y PowerShell) y no guardan estado |
| `test_git_rules_boundaries.py` | `core/permissions/git_table.py`, `git_rules.py` y `core/redaction.py` (HU-11-02): stdlib y núcleo, sin E/S ni `os`, `shlex`, `subprocess`, `sys`, sin entorno ni terminal, sin nombres del shell y sin estado; `git_table.py` es solo datos (ni funciones, ni clases, ni bucles, ni condiciones); en `git_rules.py` `PermissionDecision.ALLOW` aparece una sola vez, dentro de `if self._only_reads(…) is True:`, y todo `except` devuelve `ASK` o `DENY` |
| `test_adapters_boundaries.py` | `adapters/`: ninguno importa `cli`; `adapters/system/`, `adapters/tools/`, `adapters/storage/` y `adapters/tasks/` solo stdlib, API pública del núcleo y su paquete, sin config ni terminal ni otro adaptador (HU-01-03, HU-03-01); `core/` no importa `sqlite3` (HU-03-01) |
| `test_providers_boundaries.py` | `adapters/providers/` (HU-07-02): ningún SDK importado en `src/` (`litellm` solo con `importlib` dentro de una función de `providers/`, nunca a nivel de módulo), imports permitidos (stdlib, API pública del núcleo y de `adapters.converters`, su paquete), sin entorno ni archivos ni terminal, sin nombres de proveedor en literales (se leen de `PROVIDER_KEY_VARIABLES`) y `__init__.py` solo con docstring |
| `test_bootstrap_boundaries.py` | `bootstrap.py` (HU-00-08): solo stdlib y la API pública (`__all__`) de `core`, `config`, `cli`, `adapters.storage/system/tools`, más los submódulos autorizados `core.loop`, `adapters.providers.litellm_provider` y `adapters.providers.retrying_provider`; sin `os.environ` ni `print`/`input`; `__main__.py` solo importa `bootstrap`; solo `__main__` importa `bootstrap` y nadie importa `__main__`; `bootstrap` es el único módulo que une las cuatro capas |
| `test_mcp_boundaries.py` | `adapters/mcp/` (HU-08-01): `mcp` solo con `importlib` dentro de una función de `sdk.py` y nunca como import estático en ningún archivo de `src/` (tampoco en `core/`), imports permitidos (stdlib, API pública del núcleo, su paquete), sin entorno ni configuración ni terminal, el único archivo que abre un archivo es `stderr_log.py` y solo con modo `"w"`, ningún manejador traga `CancelledError` (todo manejador termina en `raise`) ni captura `BaseException`, y solo `bootstrap.py` construye el cliente. Cada regla lleva su prueba de mutación (HU-08-02) `adapters/mcp/tool.py` solo nombra `RiskLevel.HIGH` (una herramienta remota nunca baja su riesgo) y solo `bootstrap.py` llama a `register_mcp_tools`. (HU-08-04) Ningún manejador de `Exception` de `connections.py`, `registration.py` ni `tool.py` liga la excepción (no puede repetir su texto) y solo `client.py` nombra el estado `_LOST`. |
| `test_progress_boundaries.py` | `core/progress/` (HU-11-08.1): solo stdlib y API pública, sin E/S (ni `pathlib`/`tempfile`), sin entorno ni terminal, no importa el bucle; el grabador captura `Exception`, nunca `BaseException`/`CancelledError`; solo `bootstrap.py` (y su propio paquete de almacenamiento) nombra `ProgressFile`; el texto del progreso no lee `evidence` ni `expectation` y `command` solo para distinguir un criterio semántico |
| `test_retry_boundaries.py` | `adapters/providers/retrying_provider.py` y `errors.py` (HU-07-04): solo stdlib, API pública del núcleo y su paquete; no conocen eventos (`Event`, `EventType`, `EventBus`: el evento lo publica `bootstrap.py`); sin `time` ni `threading` (la espera es un awaitable inyectado); ningún `except` puede tragarse la cancelación (solo `TRANSIENT_ERRORS` y `Exception`, sin `except` desnudo ni `BaseException`). Cada detector lleva su autoprueba |
| `test_no_secrets_in_repo.py` | Ningún archivo versionado con nombre o contenido de clave |

**Huecos conocidos** (los cierra la historia que los toca): no hay una lista blanca para *todo* `core/` (las importaciones de `adapters`, `observability` o `mcp` solo se detectan en los módulos que tienen guarda propia); `forbidden_imports` acepta módulos estándar que hacen E/S (`sqlite3`, `subprocess`, `socket`…) porque son de la biblioteca estándar, así que ni `loop.py`, ni `core/tools/`, ni `core/permissions/` los detectan hoy (la plantilla añade `io_stdlib_imports`). Por eso cada módulo o subpaquete nuevo de `core/` trae su guarda; `adapters/` ya tiene `test_adapters_boundaries.py` (HU-01-03), que cubre `system/`, `tools/`, `storage/` y `tasks/`, `adapters/providers/` tiene guarda propia, `test_providers_boundaries.py` (HU-07-02), porque además de la biblioteca estándar y la API del núcleo necesita `adapters.converters` y la carga perezosa de `litellm`; `adapters/mcp/` tiene guarda propia, `test_mcp_boundaries.py` (HU-08-01), porque carga el SDK `mcp` de forma perezosa y abre un archivo de registro; cada paquete nuevo de `adapters/` debe añadirse a su lista `GUARDED` o traer una guarda propia.

## Decision Gates

| Situación | Acción |
|---|---|
| El núcleo necesita una capacidad externa | Usar o proponer un puerto en `core/interfaces/`; implementarlo en `adapters/`; conectarlo en `bootstrap.py` |
| El núcleo necesita mostrar algo | Emitir un evento; la CLI lo imprime |
| El núcleo necesita un valor de configuración | Recibirlo por constructor; lo lee `config.py` y lo pasa la raíz de composición |
| Se crea un módulo o subpaquete en `core/` | Copiar `assets/test_module_boundaries.py` a `tests/architecture/test_<modulo>_boundaries.py` y añadir sus reglas propias |
| Falla una guarda | Leer la línea reportada; corregir la dirección de la dependencia, nunca la guarda |

## Execution Steps

1. Identificar qué capas toca la historia (`core/`, `cli/`, `adapters/`, `config.py`).
2. Si crea un módulo nuevo en `core/`, añadir su guarda desde `assets/test_module_boundaries.py` reutilizando `forbidden_imports`, `find_config_reads` y `terminal_uses` (no copiarlos), con autoprueba sobre fragmentos sintéticos.
3. Si toca un hueco conocido (primer adaptador nuevo, etc.), añadir la guarda que lo cierra.
4. Ejecutar `pytest tests/architecture` y, antes de cerrar, la suite completa con los cuatro comandos de la CI.
5. Si algo falla, aplicar la fila correspondiente de Decision Gates y repetir el paso 4.

## Output Contract

Devolver:
- Resultado de `pytest tests/architecture` (pasa/falla, con el archivo y la línea si falla).
- Guardas nuevas añadidas y qué regla cubren.
- Archivos que violan una regla y el puerto o evento propuesto.
- Confirmación de que la CI (`.github/workflows/ci.yml`) sigue corriendo en Ubuntu y Windows.

## References

- `assets/test_module_boundaries.py` — plantilla de guarda para un módulo nuevo de `core/`.
- `tests/architecture/` — guardas existentes y sus detectores reutilizables.
- `.github/workflows/ci.yml` — job de integración continua.
- `docs/02-arquitectura.md` — contratos entre módulos (sección 4).
