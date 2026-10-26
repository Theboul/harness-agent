# Contrato: flujo de aprobación (HU-05-03)

## Orden de eventos por llamada «preguntar» con aprobador
`TOOL_REQUESTED` → `PERMISSION_DECIDED` (`decision="ask"`, `resolved_as="ask"`) → `APPROVAL_REQUESTED` → [espera] → `APPROVAL_RESOLVED` → (`TOOL_FINISHED`).
Si algún `emit` lanza, la herramienta no se ejecuta (Q4 de HU-01-05).

## Cargas
- `APPROVAL_REQUESTED`: `{"call_id": str, "name": str, "risk": str}`.
- `APPROVAL_RESOLVED`: `{"call_id": str, "name": str, "action": "approve_once"|"approve_session"|"reject"|None, "approved": bool, "source": "user"|"session_grant"|"approver_error"|"invalid_result"}`.
- Nunca argumentos ni contenido.

## Resultado de herramienta al modelo
- Rechazo: `[approval_rejected] Tool '<name>' was rejected by the user.` (`is_error`).
- Falla: `[approval_failed] Tool '<name>' could not be approved and was denied (fail closed).`
- Sin aprobador: sin cambios (`[approval_required_unavailable]`).

## `details` entregado al `Approver`
`{"tool": str, "arguments": dict (copia validada), "effect": str, "risk": str}`.

## Presentación de `ConsoleApprover`
```
[!] El agente quiere ejecutar: shell
  comando: pip install requests
  efecto: <descripción de la herramienta> (riesgo: alto)
  [1] aprobar una vez  [2] aprobar para la sesión  [3] rechazar
opción> 
```
Una línea por argumento; valores saneados y acotados; claves con aspecto de secreto → `***`.

## Garantías
1. Una aprobación nunca se consulta para una llamada denegada.
2. Aprobación de sesión = misma herramienta + mismos argumentos exactos.
3. `CancelledError` se propaga; nunca equivale a aprobar.
