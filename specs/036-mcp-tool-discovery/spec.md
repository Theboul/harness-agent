# Especificación: HU-08-02 — Descubrir herramientas MCP y traducirlas al formato interno

**Rama**: `claude/hu-08-02-mcp-tools-a7dbf9` · **Responsable**: C — Control y conexiones · **Sprint**: 4 (el orden por sprints ya no rige: cierre el 6-nov-2026) · **PHU**: 2  
**Requisitos**: RF-8.2 · **Depende de**: [HU-08-01](../035-mcp-stdio-connection/spec.md), [HU-01-02](../../docs/04a-historias-fundacion.md#hu-01-02) · **Ficha**: [HU-08-02](../../docs/04d-historias-conexiones.md#hu-08-02)  
**Tareas del plan**: Sp4-30 (2 h → 3 h según SPK-04), Sp4-31 (1,5 h)  
**Numeración**: `036` (033 consola, 034 reintentos, 035 MCP stdio)

## Clarificaciones

### Sesión 2026-10-30

Resueltas con las recomendaciones de [SPK-04](../../docs/decisiones/SPK-04-cliente-mcp-stdio.md) §6–§7 y la regla de falla cerrada; ninguna toca criterios de aceptación ni puertos, así que no se pidió decisión al PO.

- Q: ¿Se amplía `check_schema` para aceptar `anyOf`, `$ref`, `format`…? → A: **no**. Es del núcleo (A). Una herramienta cuyo esquema no valida se **omite con un aviso** y el resto se registra.
- Q: ¿Qué riesgo tiene una herramienta MCP? → A: **`HIGH` siempre** (MCP no trae riesgo; falla cerrada). Con `HIGH` la política por defecto pregunta; la política específica es HU-08-03.
- Q: ¿Se prefijan los nombres? → A: **no**, se registran tal cual los da el servidor; los prefijos son HU-08-05. Un nombre inválido o repetido se omite con aviso.
- Q: ¿Cambia el puerto `McpClient`? → A: no. `list_tools() -> list[Tool]` ya existía: el cliente devuelve `Tool` internas (`McpTool`) que llaman a su `call_tool`.
- Q: ¿Qué se hace con el texto del servidor? → A: es **no fiable**: la descripción se acota a 2 000 caracteres y los avisos usan textos fijos (el nombre de la herramienta solo se cita si cumple `[A-Za-z0-9_-]{1,64}`).
- Q: ¿Cuándo se registran? → A: en `run_session`, justo después de `connect_all` y antes del primer prompt, con el `WarningSink`. El bucle consulta el registro en cada turno, así que no hace falta reconstruir nada.

## Historia

Como agente principal quiero ver las herramientas del servidor como si fueran nativas para usarlas con el mismo mecanismo.

## Escenarios

1. **Herramientas MCP en el registro (AC-01).** Dado un servidor conectado, cuando se listan sus herramientas, entonces aparecen en el registro con su nombre, descripción y esquema, y se ejecutan con `registry.get(nombre).run(...)` como cualquier otra.
2. **Una herramienta con esquema no soportado no impide las demás.** Dado un servidor con una herramienta cuyo esquema usa `anyOf`, esa se omite con un aviso en español y las demás se registran.
3. **Colisión de nombre.** Dado un nombre ya registrado, la herramienta MCP se omite con aviso; la nativa no se toca.
4. **Falla el listado o el servidor no conectó.** Un fallo al listar es un aviso y ese servidor queda sin herramientas; un servidor no conectado se salta sin segundo aviso.
5. **Sin servidores.** El arnés se comporta exactamente como hoy.

## Requisitos funcionales

- **FR-001**: `McpStdioClient.list_tools()` MUST leer las herramientas del servidor (siguiendo la paginación, con tope de 20 páginas y cortando un cursor repetido) y devolver `Tool` con nombre, descripción y esquema copiado del servidor.
- **FR-002**: El riesgo de toda herramienta MCP MUST ser `HIGH`.
- **FR-003**: Una descripción vacía MUST sustituirse por un texto fijo y una larga MUST acotarse a 2 000 caracteres.
- **FR-004**: Un fallo al listar MUST ser `McpListError` con texto fijo que no reproduce lo que dijo el servidor; la cancelación MUST propagarse.
- **FR-005**: `register_mcp_tools` MUST registrar las herramientas de los clientes conectados; ante `InvalidToolDefinitionError` o `DuplicateToolError` MUST omitir solo esa herramienta con un aviso fijo.
- **FR-006**: `core/interfaces/`, `core/events.py`, `core/loop.py` y `check_schema` MUST NOT cambiar. Solo `bootstrap.py` cablea el registro.
- **FR-007**: Sin servidores configurados, nada se conecta ni se registra.

## Fuera de alcance

HU-08-03 (permisos y marcar el resultado como dato externo), HU-08-04 (aislamiento de fallos), HU-08-05 (prefijos y varios servidores), `output_schema` y las anotaciones MCP.

## Criterios de éxito

- **SC-001**: con el servidor de demostración, las 7 herramientas con esquema válido aparecen en el registro y `add` devuelve `5` para `2+3`; `greet` (con `anyOf`) produce exactamente un aviso.
- **SC-002**: ningún aviso ni error contiene texto del servidor (centinela `VALOR-DE-PRUEBA-123`).
- **SC-003**: las cuatro puertas de calidad y `pytest tests/architecture` en exit 0; cobertura 100 % de los módulos nuevos.
