# Tareas: SPK-04 — Cliente MCP por stdio y servidor de demostración

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Responsable**: C — Control y conexiones  
**Mapeo y presupuesto**: Sp2-54 «Probar el SDK de MCP con un servidor local» (120 min) → T001–T005 · Sp2-55 «Elegir el servidor de la demostración» (60 min) → T006 · Sp2-56 «Anotar el resultado y ajustar las estimaciones de HU-08» (60 min) → T007 · cierre T008–T009. Los tiempos son referencia.

**Archivos protegidos** (no se tocan): `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `cli/`, `tests/doubles/`, `docs/archivo/`. Tampoco se añade nada a `src/`, `pyproject.toml`, `requirements-dev.txt` ni la CI.

**Orden por prueba primero**: en T001–T005 se escribe la prueba, se observa que falla por la razón esperada (módulo o función ausente, o aserción del contrato), se implementa lo mínimo del apoyo y se pasan las puertas. Todas las pruebas usan `pytest.importorskip("mcp")`.

## Fase 1 — Probar el SDK con un servidor local (Sp2-54)

- [x] **T001** [US1] Servidor y sonda base + AC-01: `tests/spikes/mcp_demo_server.py` (`MCPServer` con `add`, `echo`, `fail`, `slow`, `crash`, `pid`, `free_form`) y `tests/spikes/mcp_probe.py` (`ProbeServer`, `open_session`, `handshake`, `list_tools`, `demo_server`) (Sp2-54, 40 min)
  - **Archivos**: `tests/spikes/mcp_demo_server.py`, `tests/spikes/mcp_probe.py`, `tests/spikes/test_mcp_stdio_spike.py` (clase `TestHandshake`)
  - **Verificación**: el servidor se inicia, la negociación devuelve versión de protocolo, nombre del servidor y capacidad de herramientas, y se lista ≥ 1 herramienta con nombre, descripción y esquema (AC-01 / SC-001).
- [x] **T002** [US2] Invocación y errores: `call` en `mcp_probe.py` y pruebas de resultado correcto, `is_error` por fallo de la herramienta, herramienta inexistente y argumentos inválidos (Sp2-54, 35 min)
  - **Archivos**: `tests/spikes/mcp_probe.py`, `tests/spikes/test_mcp_stdio_spike.py` (clase `TestCallResults`)
  - **Verificación**: ninguna de las cuatro llamadas lanza excepción en el cliente; el texto de argumentos inválidos se comprueba contra un centinela para registrar si reproduce el valor recibido.
- [x] **T003** [US3] Fallos del servidor: no arranca (comando inexistente), muere a mitad de llamada, no responde (tiempo de espera) y comprobación de procesos huérfanos con `process_alive` (Sp2-54, 40 min)
  - **Archivos**: `tests/spikes/mcp_probe.py`, `tests/spikes/test_mcp_stdio_spike.py` (clase `TestServerFailures`)
  - **Verificación**: se registra el tipo de excepción de cada caso, que llega en un tiempo acotado y que el PID informado por `pid()` ya no existe tras salir del contexto.
- [x] **T004** [US4] Cancelación y ciclo de vida: cancelar una llamada en curso, y abrir/cerrar la conexión desde tareas distintas (Sp2-54, 30 min)
  - **Archivos**: `tests/spikes/test_mcp_stdio_spike.py` (clase `TestCancellationAndLifecycle`)
  - **Verificación**: la cancelación termina sin colgarse y sin proceso vivo; el cierre desde otra tarea falla o no según lo observado (hallazgo para `McpClient.connect()` sin `close()`).
- [x] **T005** [US5] Compatibilidad de esquemas con `check_schema` del núcleo, incluido el objeto libre (Sp2-54, 25 min)
  - **Archivos**: `tests/spikes/test_mcp_stdio_spike.py` (clase `TestSchemaCompatibility`)
  - **Verificación**: cada esquema listado pasa por `check_schema`; la lista de problemas (si hay) queda fijada por la prueba.

## Fase 2 — Elegir el servidor de la demostración (Sp2-55)

- [x] **T006** [US6] Comparar candidatos (servidor propio, `server-everything` por `npx`, `mcp-server-time` por `uvx`, y `server-filesystem`/`server-memory` solo por referencia) con medición manual de una vez, y fijar la recomendación (Sp2-55, 40 min)
  - **Archivos**: sección «Servidor de la demostración» de `docs/decisiones/SPK-04-cliente-mcp-stdio.md`
  - **Verificación**: criterios explícitos (local, sin credenciales, sin red en el primer arranque, determinista, tiempo de arranque, portabilidad Windows/Linux) con el resultado por candidato.

## Fase 3 — Anotar el resultado (Sp2-56)

- [x] **T007** [US6] Decisión escrita completa `docs/decisiones/SPK-04-cliente-mcp-stdio.md` (Sp2-56, 40 min)
  - **Archivos**: `docs/decisiones/SPK-04-cliente-mcp-stdio.md`
  - **Contenido**: comprobado / medido a mano / no comprobado; contrato observado del SDK; modos de fallo; recomendaciones y estimaciones ajustadas por historia (HU-08-01…05, HU-00-05.2); hallazgos sobre `McpClient`, la política y la configuración **sin tocarlos**; pendientes humanos.

## Fase 4 — Cierre

- [x] **T008** Verificación (`verificar-fronteras-hexagonales`): `ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest --cov=harness_agent`, `pytest tests/architecture`, `git diff --exit-code` sobre archivos protegidos y confirmar que `src/`, `pyproject.toml`, `requirements-dev.txt` y `.github` no cambiaron (20 min)
  - **Archivos**: ninguno
- [x] **T009** Registro en `docs/PROGRESO.md` (SPK-04 `En revisión`, nunca `Hecha`; fila, *Registro de cambios* y bloque **Observaciones de SPK-04**) y marcado de este archivo (15 min)
  - **Archivos**: `docs/PROGRESO.md`, `specs/025-mcp-stdio-client-spike/tasks.md`, `.specify/feature.json` (ignorado por git: se edita en disco)

## Tareas humanas (no las marca Claude)

- [ ] **T010** Revisión cruzada por A o B
- [ ] **T011** CI remota en `ubuntu-latest` y `windows-latest` (las pruebas de procesos y PID deben pasar en ambos)
- [ ] **T012** Acuerdo de A, B y C sobre los hallazgos que tocan contratos o configuración (cierre de `McpClient`, tiempos de espera, sección `[mcp]` de `config.py`) antes de HU-08-01
- [ ] **T013** Visto bueno del PO al servidor de la demostración elegido

## Dependencias y ejecución

T001 → T002 → T003 → T004 (mismo archivo de pruebas, en serie; T002–T003 amplían `mcp_probe.py`) → T005 → T006 (necesita las cifras de T001–T005) → T007 → T008 → T009. MVP: T001 cumple AC-01; T002–T005 dimensionan HU-08; T006–T007 dejan la decisión usable.

## Phase 5: Convergence

- [x] T014 Probar con una prueba automática la API `mcp.Client` de la rama 2.x (negociar, listar y llamar) contra el servidor de demostración, per plan: D2 (partial)
- [x] T015 Actualizar `contracts/probe-api.md` con la firma real del apoyo (`call(..., timeout_s)`, `leaf_exceptions`, `Handshake` sin `elapsed_s`), per plan: Fase 1 contratos (partial)
- [x] T016 Registrar en la decisión que D6 (abrir y cerrar en tareas distintas) se midió a mano y no se automatizó por durar ~99 s, per plan: D6 (partial)

## Evidencia (2026-10-25)

- T001–T005, T014: `tests/spikes/test_mcp_stdio_spike.py` → 28 pruebas en verde (Windows 10, Python 3.12.10, `mcp 2.3.0`); rojo previo observado en T001 (`ModuleNotFoundError`), T002 (nombre `call`), T003 (importación de `leaf_exceptions`) y T005 (`KeyError` de `greet`). T004 se midió antes con un experimento; la parte de cerrar desde otra tarea quedó como medición manual (~99 s).
- T006–T007, T016: `docs/decisiones/SPK-04-cliente-mcp-stdio.md`.
- T008: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov` → exit 0 (4142 pasadas, 47 omitidas, 193,04 s, cobertura 99 %); `pytest tests/architecture` → 392 pasadas; sin diferencias en `src/`, `pyproject.toml`, `requirements-dev.txt`, `.github`, `tests/doubles` ni `docs/archivo`.
- T009: `docs/PROGRESO.md` (SPK-04 `En revisión`).
- T015: `contracts/probe-api.md` y `data-model.md` alineados con el apoyo real.
- Lista de comprobación de `arquitectura-hexagonal-clean` revisada contra el código: sin puertos ni eventos nuevos, `core/` e `src/` intactos, el SDK solo vive en `tests/spikes/`, falla cerrada (tiempos de espera acotados, sin reintentos), sin red ni claves: todas «sí» salvo «puertos nuevos» y «eventos nuevos» (no).
