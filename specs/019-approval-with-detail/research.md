# Research: HU-05-03

Sin incógnitas abiertas. Decisiones:

## R1 — Dónde espera el bucle al usuario
- **Decisión**: el bucle llama a un `ApprovalGate` (núcleo) tras `PERMISSION_DECIDED` cuando la decisión fue «preguntar» y hay aprobador.
- **Razón**: `PermissionPolicy.evaluate` es síncrona y sin acceso al bus; solo el bucle puede esperar y emitir.
- **Alternativas**: política que bloquea (rompe asyncio); aprobador dentro de la herramienta (la herramienta no debe decidir sobre sí misma).

## R2 — Patrón de la aprobación de sesión
- **Decisión**: herramienta + argumentos validados exactos, comparados por su serialización JSON canónica (`sort_keys`). Argumentos no serializables → se aprueba una vez pero no se recuerda (fail closed).
- **Razón**: Q1; evita adelantar HU-05-02; sin riesgo de ampliar el permiso.
- **Alternativas**: misma ruta; programa+subcomando de shell (interpretar comandos es HU-05-02).

## R3 — Aprobación nunca anula denegación
- **Decisión**: el gate solo se invoca con «preguntar». `DENY` se resuelve antes; `ProtectedPolicy` devuelve `DENY` ante la zona protegida, de modo que ninguna aprobación de sesión se consulta.
- **Verificación**: prueba de integración con `ProtectedPolicy` real y una aprobación de sesión previa que «cubriría» la llamada.

## R4 — Falla cerrada
- `Exception` del aprobador → `approver_error`; resultado que no es `ApprovalResult` o acción no válida → `invalid_result`; `CancelledError` se propaga (el bucle publica `INTERRUPTED` con fase `approval`); sin aprobador → rama de Sprint 1.
- El motivo (`reason`) del usuario se guarda acotado en `ApprovalOutcome` pero no viaja al modelo ni a eventos (HU-05-04).

## R5 — Eventos
- `APPROVAL_REQUESTED`: `{call_id, name, risk}`; `APPROVAL_RESOLVED`: `{call_id, name, action, approved, source}`. Sin argumentos ni contenido (FR-012). Siempre en pareja, también para aprobaciones de sesión (`source = "session_grant"`).

## R6 — Presentación
- `ConsoleApprover` muestra herramienta, argumentos (una línea por argumento, saneados y acotados, valores de claves con aspecto de secreto redactados) y efecto (descripción + riesgo), luego `[1] aprobar una vez  [2] aprobar para la sesión  [3] rechazar`. Entrada no válida: hasta 3 intentos, luego rechazar. Fin de entrada: rechazar.
