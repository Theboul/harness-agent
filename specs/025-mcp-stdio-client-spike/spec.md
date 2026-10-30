# Especificación: SPK-04 — Spike: cliente MCP por stdio y servidor de demostración

**Rama**: `claude/spk-04-spike-9e2cfc` · **Responsable**: C — Control y conexiones · **Sprint**: 2 · **PHU**: 1  
**Requisitos**: RF-8.1 · **Depende de**: ninguna · **Ficha**: [SPK-04](../../docs/04d-historias-conexiones.md#spk-04)  
**Tareas del plan**: Sp2-54, Sp2-55, Sp2-56  
**Numeración**: `025` (la `024` está reservada por la rama de HU-01-06 aún sin integrar)

## Clarificaciones

### Sesión 2026-10-25

- Q: ¿Qué servidor sirve de referencia en las pruebas automáticas? → A: uno propio, local, escrito con el propio SDK y lanzado con el intérprete de Python de la prueba; las pruebas no usan red, claves ni `npx`/`uvx`. Los servidores de terceros se sondean a mano y solo se documentan.
- Q: ¿El spike añade el SDK a las dependencias? → A: no. `mcp==2.3.0` ya está fijado en `requirements-dev.txt` (llega con `litellm[mcp]`); las pruebas usan `pytest.importorskip("mcp")` y no tocan `pyproject.toml`, ni la CI ni `src/`.
- Q: ¿El spike traduce herramientas MCP al puerto `Tool`? → A: no (eso es HU-08-02). Solo comprueba qué datos entrega el SDK y si el validador de esquemas del núcleo los acepta, para estimar.

## Historia

Como equipo de desarrollo queremos probar, durante medio día, un cliente MCP por stdio contra un servidor local sin credenciales y elegir el servidor de la demostración, para estimar con seguridad las historias de MCP (HU-08-01 a HU-08-05 y HU-00-05.2).

## Escenarios

1. **Servidor de referencia conectado (AC-01).** Dado un servidor local sin credenciales, cuando el cliente de prueba lo inicia por stdio, entonces se negocian capacidades (versión de protocolo, nombre del servidor, capacidad de herramientas) y se lista al menos una herramienta con su nombre, descripción y esquema de entrada.
2. **Invocación y resultados.** Dado el servidor conectado, cuando se invoca una herramienta con argumentos válidos, inválidos, de una herramienta inexistente o que falla, entonces queda documentado cómo llega el resultado y el error (¿excepción o resultado con marca de error?) y qué texto llega al modelo.
3. **Fallos del servidor.** Dado un servidor que no arranca, que muere a mitad de una llamada o que no responde, entonces queda documentado qué excepción ve el cliente, en cuánto tiempo y si queda algún proceso huérfano.
4. **Cancelación.** Dado una llamada en curso, cuando la tarea del cliente se cancela, entonces el cliente termina y el proceso del servidor se cierra (compatible con D-01).
5. **Compatibilidad con el núcleo.** Dado el esquema de entrada que anuncia un servidor, cuando se pasa por el validador de esquemas del núcleo, entonces queda claro qué esquemas acepta y cuáles no.
6. **Elección y estimación.** El servidor de demostración elegido y las estimaciones ajustadas de HU-08 quedan escritos en `docs/decisiones/`.

## Requisitos funcionales

- **FR-001**: El spike MUST iniciar un servidor MCP por stdio desde un cliente de prueba, negociar capacidades y listar al menos una herramienta, sin red ni credenciales (AC-01).
- **FR-002**: El servidor de demostración MUST ser local, determinista y sin credenciales; vive en `tests/spikes/` y se lanza con `sys.executable`.
- **FR-003**: Las pruebas MUST documentar con aserciones el contrato observado del SDK: forma del resultado de una herramienta, `is_error`, error por herramienta inexistente y por argumentos inválidos, y si el texto de error reproduce valores recibidos.
- **FR-004**: Las pruebas MUST cubrir fallo de arranque, caída del servidor durante una llamada y tiempo de espera agotado, y comprobar que no queda un proceso hijo vivo.
- **FR-005**: Las pruebas MUST cubrir la cancelación de una llamada en curso.
- **FR-006**: Las pruebas MUST pasar cada esquema de herramienta anunciado por `check_schema` del núcleo y registrar los que no acepte.
- **FR-007**: Ninguna prueba MUST abrir red, usar claves ni un proveedor real. Los servidores de terceros (`npx`, `uvx`) no se lanzan en pruebas.
- **FR-008**: La decisión MUST separar lo comprobado en pruebas, lo medido a mano una sola vez y lo no comprobado; MUST comparar al menos tres candidatos de servidor de demostración y recomendar uno con sus condiciones.
- **FR-009**: Si el spike concluye que hace falta cambiar un puerto de `core/interfaces/`, el catálogo de `core/events.py`, `pyproject.toml` o la CI, MUST quedar como hallazgo para A, B y C, sin tocarlos.
- **FR-010**: El código MUST vivir en `tests/spikes/`; nada se añade a `src/`. No se implementan HU-08-01 a HU-08-05.
- **FR-011**: Los cuatro comandos de calidad y `pytest tests/architecture` MUST pasar; `docs/PROGRESO.md` MUST reflejar la historia (`En revisión`, nunca `Hecha`).

## Criterios de éxito

- **SC-001**: La prueba de AC-01 inicia el servidor propio, negocia capacidades y lista ≥ 1 herramienta en una sola ejecución de `pytest` sin red.
- **SC-002**: El documento de decisión nombra el servidor elegido, el motivo frente a al menos dos alternativas y las estimaciones ajustadas de cada historia de HU-08 que cambien.
- **SC-003**: Cada hallazgo que afecte a otra historia (HU-08-01…05, HU-00-05.2) queda enlazado a ella con una recomendación.

## Fuera de alcance

Cliente MCP de producción, adaptador en `adapters/`, traducción al puerto `Tool`, política de permisos de herramientas MCP (HU-08-03), aislamiento definitivo de fallos (HU-08-04, HU-00-05.2), configuración de servidores en `config.py`, transportes distintos de stdio (HTTP/SSE), recursos, prompts y muestreo de MCP.

## Supuestos

- El SDK fijado es `mcp==2.3.0` (API 2.x: `MCPServer`, no `FastMCP` de 1.x). Si el equipo fija otra versión, los hallazgos de API deben revisarse.
- Las mediciones de tiempo se hicieron en Windows 10 con Python 3.12; son orientativas, no umbrales de las pruebas.
- Un servidor de terceros que necesita red en su primer arranque no puede ser el servidor de las pruebas automáticas, pero sí candidato para la demostración manual.
