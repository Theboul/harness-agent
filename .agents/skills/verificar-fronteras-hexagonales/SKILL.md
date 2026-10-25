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
| `test_core_reads_no_config.py` | Todo `core/`: no lee `config`, `tomllib`, entorno ni archivos (`find_config_reads`) |
| `test_core_no_terminal.py` | Todo `core/`: no imprime ni usa la terminal (`terminal_uses`); el bus en memoria no define eventos |
| `test_loop_boundaries.py` | `core/loop.py`: solo stdlib y núcleo (`forbidden_imports`), sin consola, sin eventos de límite/aprobación, sin ciclos |
| `test_core_tools_stdlib_only.py` | `core/tools/`: lista blanca stdlib + núcleo |
| `test_output_limit_boundaries.py` | `core/tools/output_limit.py` (HU-02-02): solo stdlib y la API del núcleo (`entities`, `interfaces.tool`), sin E/S (ni `os`), sin config ni terminal, sin importar adaptadores |
| `test_permissions_boundaries.py` | `core/permissions/`: lista blanca, sin E/S, todo «permitir» protegido por `AuthorizedArea.contains` |
| `test_tasks_boundaries.py` | `core/tasks/` (HU-11-01): lista blanca stdlib + núcleo, sin E/S (ni `pathlib`, `subprocess`, `sqlite3`), sin entorno ni terminal |
| `test_protected_policy_boundaries.py` | `core/permissions/protected.py` (HU-11-01): sin E/S, nunca nombra `ALLOW` y todo `except` devuelve `DENY` (solo puede endurecer) |
| `test_adapters_boundaries.py` | `adapters/`: ninguno importa `cli`; `adapters/system/`, `adapters/tools/`, `adapters/storage/` y `adapters/tasks/` solo stdlib, API pública del núcleo y su paquete, sin config ni terminal ni otro adaptador (HU-01-03, HU-03-01); `core/` no importa `sqlite3` (HU-03-01) |
| `test_providers_boundaries.py` | `adapters/providers/` (HU-07-02): ningún SDK importado en `src/` (`litellm` solo con `importlib` dentro de una función de `providers/`, nunca a nivel de módulo), imports permitidos (stdlib, API pública del núcleo y de `adapters.converters`, su paquete), sin entorno ni archivos ni terminal, sin nombres de proveedor en literales (se leen de `PROVIDER_KEY_VARIABLES`) y `__init__.py` solo con docstring |
| `test_bootstrap_boundaries.py` | `bootstrap.py` (HU-00-08): solo stdlib y la API pública (`__all__`) de `core`, `config`, `cli`, `adapters.storage/system/tools`, más los submódulos autorizados `core.loop` y `adapters.providers.litellm_provider`; sin `os.environ` ni `print`/`input`; `__main__.py` solo importa `bootstrap`; solo `__main__` importa `bootstrap` y nadie importa `__main__`; `bootstrap` es el único módulo que une las cuatro capas |
| `test_no_secrets_in_repo.py` | Ningún archivo versionado con nombre o contenido de clave |

**Huecos conocidos** (los cierra la historia que los toca): no hay una lista blanca para *todo* `core/` (las importaciones de `adapters`, `observability` o `mcp` solo se detectan en los módulos que tienen guarda propia); `forbidden_imports` acepta módulos estándar que hacen E/S (`sqlite3`, `subprocess`, `socket`…) porque son de la biblioteca estándar, así que ni `loop.py`, ni `core/tools/`, ni `core/permissions/` los detectan hoy (la plantilla añade `io_stdlib_imports`). Por eso cada módulo o subpaquete nuevo de `core/` trae su guarda; `adapters/` ya tiene `test_adapters_boundaries.py` (HU-01-03), que cubre `system/`, `tools/`, `storage/` y `tasks/`, `adapters/providers/` tiene guarda propia, `test_providers_boundaries.py` (HU-07-02), porque además de la biblioteca estándar y la API del núcleo necesita `adapters.converters` y la carga perezosa de `litellm`; cada paquete nuevo de `adapters/` (`mcp/`) debe añadirse a su lista `GUARDED` o traer una guarda propia.

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
