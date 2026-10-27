# Quickstart: validar HU-05-04

## Requisitos

- Entorno como en la CI: `pip install -r requirements-dev.txt; pip install -e . --no-deps`.
- Sin red ni claves: el proveedor es `FakeProvider`, el aprobador un doble o `ConsoleApprover` sobre flujos de texto, y nunca se ejecuta una acción rechazada.

## 1. Funciones puras

```powershell
pytest tests/unit/core/permissions/test_rejection_message.py tests/unit/core/permissions/test_rejection_properties.py -q
```

Esperado:

- todos los ejemplos normativos de [contracts/rejection_message_contract.md](contracts/rejection_message_contract.md) dan el texto exacto;
- la tabla adversarial: marcas falsas, `system:`, «ignora lo anterior», saltos de línea, secuencias de control, bidireccionales, comillas que intentan cerrar el marco, 10 000 caracteres, URL con credenciales y valores que no son texto;
- con semilla fija, para cualquier motivo la salida empieza por la marca estable, tiene una sola línea, mide ≤ 500, no tiene caracteres de control y el motivo nunca contiene `'` ni `"`;
- `approvals.py` al 100 % de líneas y ramas.

## 2. La puerta y el bucle

```powershell
pytest tests/unit/core/permissions/test_approvals.py tests/core/test_loop_approval.py tests/core/test_loop_rejection_reason.py -q
```

Esperado:

- `ApprovalOutcome.reason` sale limpio; sin motivo, byte a byte el texto de HU-05-03;
- el bucle entrega el mensaje con motivo en el resultado de herramienta (`is_error=True`, categoría `approval_rejected`) y la herramienta no se ejecuta;
- `[approval_failed]` no cambia y nunca lleva motivo;
- ningún evento contiene el motivo y `APPROVAL_RESOLVED` conserva sus cinco claves;
- única prueba existente modificada: la aserción `SENTINEL not in message.content` de `test_a_rejection_does_not_run_the_tool_and_tells_the_model` (research R9).

## 3. La terminal

```powershell
pytest tests/unit/cli/test_approval.py tests/unit/cli/test_approval_reason.py -q
```

Esperado: `3` y un motivo dan un rechazo con ese motivo; `3` con línea vacía, fin de la entrada o `/salir` dan un rechazo sin motivo; `1` y `2` no piden motivo; el motivo no se escribe en la salida; las pruebas existentes de `ConsoleApprover` pasan sin cambios.

## 4. Replanteo (Sp2-33), convivencia y persistencia

```powershell
pytest tests/integration/test_rejection_reason_agent_loop.py -q
```

Esperado:

- **Sp2-33** con aprobador de prueba y con `ConsoleApprover` real sobre flujos de texto: el proveedor falso pide una acción, se rechaza con motivo, su siguiente petición contiene el mensaje de herramienta con la marca y el motivo, propone una acción distinta y el doble de la herramienta rechazada recibe 0 llamadas;
- denegados, git destructivo y zona protegida: 0 preguntas al aprobador y `[permission_denied]`;
- aprobación de sesión y rechazo repetido como describe el contrato;
- **persistencia**: tras un rechazo con motivo, ni las filas de `events` ni los bytes del archivo SQLite contienen el motivo; el mensaje está solo en el historial en memoria.

## 5. Guardas y cierre

```powershell
pytest tests/architecture -q
ruff format --check .; ruff check .; mypy src tests; pytest --cov=harness_agent --cov-report=term-missing
git diff --exit-code (git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/permissions/policy.py src/harness_agent/core/permissions/protected.py src/harness_agent/core/permissions/exact_calls.py src/harness_agent/core/permissions/command_parser.py src/harness_agent/core/permissions/command_rules.py src/harness_agent/core/permissions/command_policy.py src/harness_agent/core/permissions/git_rules.py src/harness_agent/core/permissions/git_table.py src/harness_agent/core/redaction.py src/harness_agent/config.py tests/doubles docs/archivo
```

Esperado: las cuatro puertas en exit 0, el 100 % en `approvals.py`, el diff de `core/loop.py` limitado a `_ask_approval` y su import (se revisa a mano) y el diff vacío en los archivos protegidos de la lista. El detector de secretos se pasa a mano sobre los archivos nuevos y modificados.
