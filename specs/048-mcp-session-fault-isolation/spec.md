# Especificación: HU-00-05.2 — Prueba de aislamiento de fallos de un servidor MCP

**Rama**: `claude/hu-00-05-2-mcp-isolation-956f76` · **Responsable**: A — Núcleo · **Sprint**: 4 · **PHU**: 1  
**Requisitos**: RNF-8 · **Depende de**: [HU-08-04](../038-mcp-permissions-failure-isolation/spec.md), HU-00-05.1 · **Ficha**: [HU-00-05.2](../../docs/04a-historias-fundacion.md#hu-00-05.2)  
**Numeración**: `048` (047 la usa otra historia en paralelo)

## Naturaleza de la historia

HU-08-04 ya implementó el aislamiento y sus pruebas por componentes (`tests/integration/test_mcp_failure_isolation.py`: cliente y bucle, sin `run_session`). Esta historia es **solo evidencia automatizada de sesión**: la sesión real (`compose` + `run_session` con el bucle, la política y la consola) sobrevive a un servidor MCP real que falla. **No cambia `src/`.** Si la prueba descubriera un defecto real, se detiene y se anota como hallazgo en `PROGRESO.md`.

## Clarificaciones

### Sesión 2026-10-31

- Q: ¿Se duplica `test_mcp_failure_isolation.py`? → A: no. Aquel archivo prueba el cliente y el bucle; este prueba **la sesión completa** (`run_session`, varias peticiones, estado de procesos al cerrar) y los dos escenarios de la ficha (arranque y mitad de sesión). Archivo nuevo: `tests/integration/test_mcp_session_fault_tolerance.py`.
- Q: ¿Servidor real? → A: sí (regla 1 de la ficha): procesos hijo de Python con `sys.executable`, el servidor de demostración (`tests/spikes/mcp_demo_server.py`, sin modificar) y el de sondeo (`tests/integration/mcp_env_probe_server.py`) como segundo servidor sano. Sin red ni claves.
- Q: ¿Cómo se observa la caída «a mitad de sesión»? → A: la herramienta `crash` del servidor de demostración termina su proceso durante un turno; una petición posterior de la misma sesión invoca de nuevo esa herramienta.
- Q: ¿Colisión de nombres entre servidores? → A: ambos servidores exponen `pid`; hasta HU-08-05 (prefijos) gana el primero y el segundo recibe un aviso. La prueba usa `env_names` del segundo servidor y el archivo de pid (`PROBE_PID_FILE`).
- Q: ¿Esperas? → A: nunca `sleep` fijo; sondeo con tope (`wait_until`). El «al instante» se mide con el reloj monótono alrededor de la llamada con un tope holgado (< 2 s, el tope de espera por llamada es de 10 s o más).
- Q: ¿Windows? → A: sin marca de omisión; los procesos hijo y `os._exit` funcionan en Windows (HU-08-04 ya los usa). Si la CI mostrara inestabilidad se añadirá una marca documentada.

## Escenarios

1. **AC-01 — Servidor inexistente o caído al arrancar.** Con un servidor inexistente y otro sano, la sesión arranca con un único aviso fijo, las herramientas del sano y las nativas funcionan.
2. **AC-02 — Caída a mitad de sesión.** En la petición 1 el modelo invoca `crash`; en la petición 2 invoca otra vez una herramienta de ese servidor y recibe `[mcp_server_down]` de inmediato; el segundo servidor y una herramienta nativa siguen respondiendo; la sesión termina con código 0.
3. **Servidor colgado.** Una llamada que no vuelve vence como `[mcp_timeout]` y el resto de la sesión sigue.
4. **Sin huérfanos.** Al terminar la sesión no queda ningún proceso de servidor (caído, colgado o sano).

## Requisitos funcionales

- **FR-001**: La prueba MUST ejecutarse con `run_session` y servidores reales de Python.
- **FR-002**: MUST comprobar `[mcp_server_down]` en la segunda llamada, sin esperar el tiempo máximo de la llamada.
- **FR-003**: MUST comprobar `[mcp_timeout]` con un servidor colgado y que otro servidor y las nativas responden después.
- **FR-004**: MUST comprobar con sondeo con tope que los pids de todos los servidores desaparecen al cerrar la sesión.
- **FR-005**: MUST NOT cambiar `src/`, `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `tests/spikes/mcp_demo_server.py` ni `docs/archivo/`.
- **FR-006**: MUST NOT usar red, claves ni proveedor real; el proveedor es `FakeProvider`.

## Criterios de éxito

- **SC-001**: Las pruebas pasan en verde con las cuatro puertas y `pytest tests/architecture`.
- **SC-002**: Cada criterio de la ficha (AC-01, AC-02) tiene al menos una prueba nombrada con su ID.
