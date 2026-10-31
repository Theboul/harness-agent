# Especificación: HU-08-03 + HU-08-04 — Herramientas MCP bajo la política de permisos y aislamiento de fallos

**Rama**: `claude/hu-08-03-04-mcp-policy-44aa38` · **Responsable**: C — Control y conexiones · **Sprint**: 4 (cierre adelantado al 6-nov-2026) · **PHU**: 2 + 1  
**Requisitos**: RF-8.3, RF-8.4, RF-8.5, RNF-8 · **Depende de**: [HU-08-01](../035-mcp-stdio-connection/spec.md), [HU-08-02](../036-mcp-tool-discovery/spec.md), HU-05-01, HU-05-03 · **Fichas**: [HU-08-03](../../docs/04d-historias-conexiones.md#hu-08-03), [HU-08-04](../../docs/04d-historias-conexiones.md#hu-08-04)  
**Alcance de HU-05-08**: solo la parte «el resultado de un servidor MCP vuelve marcado como dato externo» (AC-02). El resto (archivos con instrucciones, marca de origen general, evidencia de inyección) es otra historia.  
**Numeración**: `038` (037 archivo de progreso; 039 queda libre para HU-11-08.2)

## Clarificaciones

### Sesión 2026-10-31

Resueltas con la regla de falla cerrada y con lo ya acordado en 035/036; ninguna toca criterios de aceptación ni puertos, así que no se pidió decisión al PO.

- Q: ¿Hace falta una política específica de MCP? → A: la cadena actual ya pregunta (`HIGH` → `ASK`), pero eso depende de que ninguna regla futura convierta ese `ASK` en `ALLOW`. Se añade un **techo** genérico `AskCeilingPolicy`: para los nombres que se le indican, un `ALLOW` se degrada a `ASK`; `DENY` y `ASK` pasan intactos. El núcleo no sabe qué es MCP: `bootstrap.py` le da el conjunto de nombres de herramientas MCP registradas.
- Q: ¿Dónde va en la cadena? → A: envuelve a `ExactCallPolicy` (la única que convierte `ASK` en `ALLOW`): `ProtectedPolicy(CommandPolicy(GitPolicy(AskCeilingPolicy(ExactCallPolicy(Default)))))`. Las denegaciones de las capas externas siguen prevaleciendo.
- Q: ¿Quién marca el resultado como dato externo? → A: ya lo hace el bucle (`is_external=True` en todo resultado de herramienta ejecutada, `core/loop.py`, protegido). Esta historia **no** toca el bucle: lo demuestra con una prueba de integración con el `AgentLoop` real y comprueba el `call_id`.
- Q: ¿El texto del servidor llega al modelo? → A: el contenido de un resultado correcto sí (es su función; lo recorta el registro a `max_tool_output_chars` y viaja como dato externo). Nunca llega texto del servidor en errores, avisos ni eventos. `McpTool.run` convierte cualquier excepción inesperada en un resultado fijo `[mcp_error]` (el bucle, si no, reproduciría `str(exc)`).
- Q: ¿La descripción de una herramienta MCP es un vector de inyección? → A: sí; ya se acota a 2 000 caracteres. Se le quitan además los caracteres de control (salvo salto de línea y tabulación), de formato, sustitutos y de uso privado. No se elimina el texto: el modelo lo necesita para usar la herramienta, y las acciones que provoque pasan por la política.
- Q (HU-08-04): ¿Qué se hace con un servidor caído? → A: **decisión: sin reconexión automática y sin retirar sus herramientas del registro.** Un cliente que detecta la pérdida pasa a estado `perdido`: `connected` es falso y cada llamada devuelve de inmediato `[mcp_server_down]` sin tocar el SDK (no espera `call_timeout_s` por cada llamada). Motivos: el registro no tiene baja; relanzar procesos sin que la persona lo sepa es una acción con efectos; el modelo recibe un error claro y las demás herramientas no se ven afectadas. Reiniciar el arnés reconecta. Una reconexión controlada queda como mejora futura.
- Q: ¿Qué pasa si el servidor se cuelga? → A: la llamada tiene un tope duro: `call_timeout_s` más una gracia de 5 s alrededor de `session.call_tool`; vence como `[mcp_timeout]`. El servidor sigue «conectado» (puede estar solo lento); no se marca perdido.
- Q: ¿Y un fallo inesperado al conectar o listar? → A: `connect_all` y `register_mcp_tools` capturan `Exception` (no la cancelación) por servidor y avisan con texto fijo; un error de programación de un cliente no impide arrancar ni afecta a los demás.

## Historias

- HU-08-03: como usuario operador quiero que las herramientas remotas pasen por los mismos controles que las nativas, para que conectar un servidor no abra un hueco de seguridad.
- HU-08-04: como usuario operador quiero que la caída de un servidor solo afecte a sus herramientas, para que la sesión no se rompa.

## Escenarios

1. **Aprobación de herramienta MCP (HU-08-03 AC-01).** El modelo invoca una herramienta MCP → la política pregunta → el aprobador decide → si se aprueba se ejecuta en el servidor y el resultado vuelve al bucle como `Role.TOOL` con `is_external=True` y el `call_id` de la llamada; si se rechaza el servidor no recibe nada.
2. **Sin aprobador, falla cerrada.** Con `approver=None` la llamada se deniega con `[approval_required_unavailable]` y el servidor no recibe nada.
3. **Listas `deny` / `ask` de la configuración** se aplican por nombre a las herramientas MCP como a las nativas.
4. **Argumentos con `path` en la carpeta protegida** se deniegan (`ProtectedPolicy`) también en una herramienta MCP.
5. **Ninguna regla de «permitir» alcanza a una herramienta MCP**: aunque la política interior devolviera `ALLOW`, el techo la degrada a `ASK`.
6. **Servidor caído a mitad de sesión (HU-08-04 AC-01).** El modelo invoca su herramienta → recibe `[mcp_server_down]` (o `[mcp_timeout]` / `[mcp_error]`) → el turno sigue → las herramientas nativas y las de otro servidor siguen funcionando.
7. **Servidor caído estando inactivo:** la siguiente llamada devuelve `[mcp_server_down]` de inmediato.
8. **Servidor colgado:** la llamada vence por el tope duro y el bucle sigue.
9. **Cierre:** `close_all` cierra todos los clientes aunque uno esté perdido o falle.

## Requisitos funcionales

- **FR-001**: `AskCeilingPolicy(inner, names)` MUST devolver `ASK` cuando `inner` devuelve `ALLOW` para una llamada cuyo nombre está en `names`; MUST devolver intactos `DENY` y `ASK`, y cualquier decisión para un nombre fuera de `names`. Una decisión que no sea `PermissionDecision` o cualquier excepción MUST ser `DENY`. Nunca devuelve `ALLOW` por sí misma.
- **FR-002**: `register_mcp_tools` MUST añadir al conjunto `names` (si se pasa) el nombre de cada herramienta registrada; `compose()` MUST construir el techo con ese conjunto vivo (se llena tras `connect_all`, antes del primer prompt).
- **FR-003**: `McpTool.run` MUST devolver un `ToolResult` de error con texto fijo `[mcp_error] …` ante cualquier `Exception` del cliente (no `CancelledError`); su descripción MUST limpiarse según la clarificación.
- **FR-004**: `McpStdioClient` MUST pasar a estado `perdido` cuando detecta que el servidor se fue (llamada con `SERVER_DOWN`, o fallo de la tarea dueña tras negociar): `connected` falso, `call_tool` → `[mcp_server_down]` sin llamar al SDK, `close()` sigue siendo seguro e idempotente y no deja procesos.
- **FR-005**: `call_tool` MUST acotar `session.call_tool` con `call_timeout_s` + 5 s; vencido es `[mcp_timeout]`.
- **FR-006**: `connect_all` y `register_mcp_tools` MUST convertir una excepción inesperada de un servidor en un aviso fijo (que solo cita el nombre si cumple `[A-Za-z0-9_-]{1,64}`) y seguir con los demás; la cancelación MUST propagarse.
- **FR-007**: `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/` y `docs/archivo/` MUST NOT cambiar. Cambios en `bootstrap.py`: solo el cableado de FR-002; `config.py`: ninguno.
- **FR-008**: Sin servidores MCP, el comportamiento es el de hoy.

## Fuera de alcance

Reconexión automática, retirar herramientas del registro, prefijos y varios servidores (HU-08-05), el resto de HU-05-08, redacción general de resultados (HU-10-02), aislamiento del proceso del servidor (PD-06).

## Criterios de éxito

- **SC-001**: con el `AgentLoop` real, una herramienta MCP (doble de cliente) pide aprobación; aprobada devuelve su texto con `is_external=True` y `call_id` correcto; rechazada o sin aprobador, el cliente no recibe llamadas.
- **SC-002**: con el servidor de demostración real, `crash` devuelve un error al modelo, la sesión continúa, una herramienta nativa y otro servidor siguen respondiendo, y no queda ningún proceso huérfano.
- **SC-003**: el centinela `VALOR-DE-PRUEBA-123` enviado por el servidor en un error no aparece en resultados, eventos ni avisos.
- **SC-004**: cuatro puertas de calidad y `pytest tests/architecture` en exit 0; cobertura 100 % de los módulos nuevos.
