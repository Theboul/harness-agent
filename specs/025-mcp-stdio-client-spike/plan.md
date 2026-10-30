# Plan de implementación: SPK-04 — Cliente MCP por stdio y servidor de demostración

**Spec**: [spec.md](spec.md) · **Rama**: `claude/spk-04-spike-9e2cfc` · **Fecha**: 2026-10-25

## Resumen técnico

Pruebas de caracterización en `tests/spikes/` contra el SDK `mcp==2.3.0` (ya fijado en `requirements-dev.txt`). Dos módulos de apoyo, ambos de prueba: (1) `mcp_demo_server.py`, un servidor MCP local escrito con el propio SDK (`MCPServer`), sin credenciales ni red, con herramientas deterministas para cada caso (suma, eco, fallo, lenta, caída, esquema sin tipos); y (2) `mcp_probe.py`, un cliente delgado que lanza ese servidor por stdio con `sys.executable`, negocia capacidades, lista y llama herramientas, y mide. Las pruebas fijan el contrato observado (qué devuelve el SDK, qué excepciones ve el cliente, si queda algún proceso vivo) y los hallazgos van a `docs/decisiones/SPK-04-cliente-mcp-stdio.md`, que además compara candidatos de servidor de demostración y reajusta las estimaciones de HU-08.

## Technical Context

**Language/Version**: Python 3.12.x · **Primary Dependencies**: ninguna nueva; `mcp==2.3.0` ya fijado (extra opcional `litellm`), cargado con `pytest.importorskip("mcp")` · **Storage**: N/A · **Testing**: pytest, `asyncio_mode = "auto"` · **Target Platform**: Windows y Linux (CI) · **Project Type**: spike de pruebas · **Constraints**: sin red, sin claves, sin `npx`/`uvx` en pruebas, sin cambios en `src/`, `pyproject.toml`, CI, puertos ni eventos · **Scale/Scope**: un servidor, ~7 herramientas, ~25 pruebas

## Decisiones de diseño del spike

- **D1 — Servidor propio para las pruebas.** Reproducible, sin red y cruzable entre Windows y Linux; los de terceros (`server-everything` por `npx`, `mcp-server-time` por `uvx`) se sondean a mano una vez y se documentan.
- **D2 — Cliente de apoyo = API de bajo nivel (`ClientSession` + `stdio_client`).** Es la que usará el adaptador de HU-08-01; se prueba también `mcp.Client` (API 2.x) solo para anotar la diferencia.
- **D3 — Fallos observados, no corregidos.** El spike documenta qué excepción llega (p. ej. `ExceptionGroup` al no arrancar) y cuánto tarda; el diseño de aislamiento es de HU-08-04 / HU-00-05.2.
- **D4 — Procesos huérfanos.** El servidor de demostración informa su PID por una herramienta; la prueba comprueba, tras salir del contexto, que ese PID ya no existe (`os.kill(pid, 0)` en POSIX; consulta de proceso en Windows sin dependencias nuevas).
- **D5 — Compatibilidad de esquemas por `check_schema`.** Se pasa cada `input_schema` listado por el validador del núcleo (HU-01-02) y se anota qué rechaza (p. ej. esquemas sin `type` o con `title`/`$defs`).
- **D6 — Ciclo de vida y D-01.** Se prueba que abrir y cerrar la conexión en tareas distintas falla (alcances de `anyio`) para dimensionar `McpClient.connect()` sin `close()`; es hallazgo para A, B y C, no un cambio.
- **D7 — Tiempos solo informativos.** Las pruebas usan márgenes holgados; las mediciones van a la decisión como cifras de una máquina concreta.

## Project Structure (skill `estructura-carpetas-harness`)

| Archivo | Fila de la tabla | Justificación |
|---|---|---|
| `tests/spikes/mcp_demo_server.py` | Prueba (apoyo del spike) | Precedente `tests/spikes/compaction_sim.py`; es un servidor ejecutable de prueba, no un doble reutilizable (`tests/doubles/` está protegido) |
| `tests/spikes/mcp_probe.py` | Prueba (apoyo del spike) | Mismo precedente; el adaptador real irá en `adapters/mcp/` con HU-08-01 y no se crea aquí |
| `tests/spikes/test_mcp_stdio_spike.py` | Prueba | Precedente: `tests/spikes/` (SPK-01…03) |
| `docs/decisiones/SPK-04-cliente-mcp-stdio.md` | Documentación | Precedente: `docs/decisiones/SPK-01-…`, `SPK-03-…` |
| `specs/025-mcp-stdio-client-spike/` | Artefactos de la historia | Convención `specs/NNN-slug/` |

`adapters/mcp/` está «planeada» y se crea con HU-08-01; no se crea código en `src/`. No es una pieza nueva de producción: no hay receta.

## Constitution Check y skills

Lista de `arquitectura-hexagonal-clean` (`capas-y-reglas.md`):

| Punto | Sí/No | Justificación |
|---|---|---|
| `core/` sin imports de `adapters/`, `cli/`, `config`, SDKs | Sí | `core/` no se toca |
| Todo lo externo por un puerto | Sí | El SDK vive solo en `tests/spikes/`; el puerto `McpClient` ya existe y se evalúa sin cambiarlo |
| Puertos nuevos o modificados | No | Si `McpClient` necesita `close()` o un tiempo de espera, queda como hallazgo (FR-009) |
| Eventos nuevos | No | El catálogo no se toca |
| Tipos de dominio inmutables | Sí | Los resultados del apoyo son `dataclass(frozen=True)` |
| Dependencias por constructor, reloj e ids inyectados | Sí | La sonda recibe el comando y los tiempos por parámetro |
| Falla cerrada | Sí | Un servidor que no responde se corta por tiempo; no se reintenta |
| Pruebas sin red, claves ni consola | Sí | Servidor local por `sys.executable`; `importorskip` si falta el SDK |

- `verificar-fronteras-hexagonales`: no cambia `core/`, `cli/`, `adapters/`, `pyproject.toml` ni la CI; no hay módulo nuevo en `core/`, así que no hay guarda nueva. Se ejecuta `pytest tests/architecture`.
- Principio VI: no se implementan HU-08-01…05 ni HU-00-05.2. Principio VII: solo se leyeron SPK-04, HU-08-01 y la lista de historias de HU-08 / HU-00-05.2 del plan de sprints.
- Principio II: tareas de 15–40 min (ver `tasks.md`).

## Fases

- **Fase 0** — [research.md](research.md): datos del SDK y del repositorio que condicionan el diseño.
- **Fase 1** — [data-model.md](data-model.md), [contracts/probe-api.md](contracts/probe-api.md), [quickstart.md](quickstart.md).
