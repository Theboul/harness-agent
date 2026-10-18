# Data Model: Entidades Canónicas y Formato Interno (HU-00-01)

**Feature**: Esqueleto del Repositorio e Interfaces Acordadas (HU-00-01)  
**Date**: 2026-10-17  
**Status**: Provisional (Pendiente de ratificación en reunión Sp1-03 y spike SPK-01)

---

## 1. Entidades de Mensajería y Bucle

### Role (Enumerado)
Representa los roles estándar del modelo conversacional:
- `SYSTEM`: Instrucciones del sistema y prefijo estable.
- `USER`: Mensajes e instrucciones proporcionadas por el usuario.
- `ASSISTANT`: Respuestas generadas por el modelo de lenguaje (texto o llamadas a herramientas).
- `TOOL`: Resultados devueltos por la ejecución de herramientas.

### ToolCall (Dataclass Inmutable)
Encapsula la solicitud de invocación de una herramienta por parte del modelo:
- `id`: `str` — Identificador unívoco de la llamada generado por el proveedor.
- `name`: `str` — Nombre de la herramienta solicitada (`shell`, `leer_archivo`, etc.).
- `arguments`: `dict[str, Any]` — Argumentos deserializados validados contra el esquema JSON.

### ToolResult (Dataclass Inmutable)
Encapsula el resultado de la ejecución de una herramienta:
- `call_id`: `str` — Identificador que referencia la `ToolCall` correspondiente.
- `content`: `str` — Salida textual formateada o recortada de la herramienta.
- `is_error`: `bool` — Indica si la ejecución terminó con fallo o excepción.

### TokenUsage (Dataclass Inmutable)
Registro de consumo de tokens informado por la API del proveedor:
- `input_tokens`: `int` — Tokens de entrada consumidos en el turno.
- `output_tokens`: `int` — Tokens de salida generados en el turno.

### Message (Dataclass Inmutable)
Unidad atómica de comunicación en la ventana de contexto y persistencia:
- `role`: `Role` — Rol del emisor del mensaje.
- `content`: `str` — Contenido textual del mensaje.
- `tool_calls`: `tuple[ToolCall, ...]` — Lista inmutable de herramientas solicitadas (vacía si no hay llamadas).
- `tool_result`: `ToolResult | None` — Resultado asociado si el rol es `TOOL`.
- `usage`: `TokenUsage | None` — Desglose de tokens asociado al mensaje si aplica.
- `is_external`: `bool` — Bandera que marca contenido proveniente de archivos, MCP o web para evitar inyección de prompt indirecta.

---

## 2. Catálogo de Eventos del Bus (EventBus)

### EventType (Enumerado Canónico - 17 Eventos)
Eventos oficiales de ciclo de vida definidos en `docs/02-arquitectura.md, sección 4 («Eventos del bus»)`:
1. `MENSAJE_USUARIO`: Nuevo mensaje recibido del usuario.
2. `MENSAJE_ASISTENTE`: Respuesta textual emitida por el modelo.
3. `HERRAMIENTA_SOLICITADA`: El modelo solicita invocar una herramienta.
4. `HERRAMIENTA_TERMINADA`: Ejecución de herramienta completada con resultado.
5. `APROBACION_PEDIDA`: La política de permisos solicita autorización humana.
6. `APROBACION_RESUELTA`: El usuario resolvió la solicitud de aprobación.
7. `CONTEXTO_COMPACTADO`: Historial compactado por superación de umbral.
8. `PERMISO_DECIDIDO`: Evaluación de política resuelta (denegar/preguntar/permitir).
9. `CRITERIOS_ALTERADOS`: Intento de modificación o detección de cambio en criterios.
10. `LIMITE_ALCANZADO`: Límite de turnos, tiempo o costo por sesión superado.
11. `ERROR_PROVEEDOR`: Error devuelto por el proveedor de modelo.
12. `PROVEEDOR_CONMUTADO`: Conmutación por fallo al proveedor de respaldo.
13. `SUBAGENTE_INICIADO`: Lanzamiento de una sesión hija de subagente.
14. `SUBAGENTE_TERMINADO`: Finalización de subagente con entrega de resultado.
15. `INTERRUMPIDO`: Ejecución cancelada limpiamente por señal de usuario (Ctrl+C).
16. `SESION_ARRANCADA`: Reanudación o inicio de sesión con rutina de arranque.
17. `CRITERIO_VERIFICADO`: Resultado de comprobación de un criterio de aceptación.

### Event (Dataclass Inmutable)
Carga útil publicada en el bus de eventos:
- `id`: `str` — Identificador único del evento (UUIDv4).
- `session_id`: `str` — Identificador de la sesión activa a la que pertenece.
- `type`: `EventType` — Tipo de evento emitido.
- `timestamp`: `datetime` — Marca de tiempo UTC en que ocurrió el evento.
- `payload`: `dict[str, Any]` — Datos estructurados específicos del evento.

---

## 3. Entidades de Soporte y Control

### RiskLevel (Enumerado)
- `LOW`: Acciones de solo lectura sin efectos secundarios.
- `MEDIUM`: Modificaciones reversibles o acotadas al área de trabajo.
- `HIGH`: Comandos de shell destructivos, eliminación o publicación externa (`push`, `merge`).

### PermissionDecision (Enumerado)
- `DENY`: Acción bloqueada directamente por política de seguridad; genera error al modelo.
- `ASK`: Acción que requiere confirmación explícita del usuario vía interfaz `Approver`.
- `ALLOW`: Acción autorizada automáticamente dentro de las reglas establecidas.

### ApprovalAction (Enumerado)
- `APPROVE_ONCE`: Autorizar exclusivamente esta llamada específica.
- `APPROVE_SESSION`: Autorizar la herramienta con este patrón durante la sesión actual.
- `REJECT`: Denegar la ejecución e informar el motivo al modelo.

### ApprovalResult (Dataclass Inmutable)
- `action`: `ApprovalAction` — Decisión seleccionada por el usuario.
- `reason`: `str | None` — Motivo descriptivo si la acción fue rechazada.

### ShellResult (Dataclass Inmutable)
- `exit_code`: `int` — Código de terminación del proceso hijo.
- `output`: `str` — Salida estándar y de error combinada o formateada.
- `timed_out`: `bool` — Indica si el proceso fue terminado por exceder el tiempo máximo.

### SubagentResult (Dataclass Inmutable)
- `result`: `str` — Síntesis principal de la tarea realizada.
- `key_findings`: `list[str]` — Lista de hallazgos relevantes recopilados.
- `sources`: `list[str]` — Archivos o recursos consultados.
- `error`: `str | None` — Mensaje de error si la sub-tarea falló.
