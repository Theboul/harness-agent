# Quickstart: validar HU-05-02

## Requisitos

- Entorno como en la CI: `pip install -r requirements-dev.txt; pip install -e . --no-deps`.
- Sin red ni claves: el proveedor es `FakeProvider` y las pruebas del shell real usan el intérprete de la plataforma (PowerShell en Windows, bash en Linux).

## 1. Analizador y reglas (núcleo puro)

```powershell
pytest tests/unit/core/permissions/test_command_parser.py tests/unit/core/permissions/test_command_rules.py -q
```

Esperado:

- se cumplen los separadores, comillas, sustituciones, redirecciones y construcciones no entendidas de [research.md](research.md) R3 y R4, en bash y en PowerShell;
- las reglas de coincidencia de R2, R6 y R7 dan los resultados de la tabla de [contracts/command_policy_contract.md](contracts/command_policy_contract.md);
- `core/permissions/command_parser.py` y `core/permissions/command_rules.py` al 100 % de líneas y ramas.

## 2. Política y guarda

```powershell
pytest tests/unit/core/permissions/test_command_policy.py tests/architecture -q
```

Esperado:

- ≥ 40 encadenados con un denegado por dialecto → `DENY` (SC-001);
- ≥ 25 no entendidos por dialecto → nunca `ALLOW`, también con `inner` = `ALLOW` (SC-002);
- ≥ 20 comandos habituales más los falsos positivos → nunca `DENY` (SC-004);
- la guarda nueva `test_command_policy_boundaries.py` pasa.

## 3. Lista base y configuración

```powershell
pytest tests/unit/adapters/system/test_denied_commands.py tests/unit/adapters/system/test_denied_commands_compile.py tests/unit/test_config_deny_commands.py -q
```

Esperado:

- todas las entradas de la base compilan con su dialecto (la bomba de procesos, como `LITERAL`);
- `deny_commands = []` deja la base intacta;
- `allow_commands` o `replace` detienen el arranque como campos desconocidos;
- un valor no válido da un mensaje sin el valor;
- las pruebas existentes de `test_denied_commands.py` siguen pasando.

## 4. Composición, AC-02 y convivencia con HU-11-03

```powershell
pytest tests/unit/test_bootstrap_deny_commands.py tests/integration/test_command_policy_agent_loop.py -q
```

Esperado:

- **cadena real**: zona protegida, lista `deny` y lista `ask` prevalecen;
- **HU-11-03**: un comando de la tarea entendido y no denegado se permite; uno declarado que no se entiende se pregunta; uno declarado que contiene un denegado se deniega;
- **AC-02** con `ApprovalGate` real y una aprobación de sesión previa: el denegado sigue denegado, el aprobador no recibe la pregunta y ningún proceso escribe el marcador;
- **sin filtrar datos**: los eventos y el historial no llevan el centinela;
- **arranque**: un `deny_commands` que no se entiende detiene el arranque con el mensaje del contrato.

## 5. Cierre

```powershell
ruff format --check .; ruff check .; mypy src tests; pytest --cov=harness_agent --cov-report=term-missing
git diff --exit-code (git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/loop.py src/harness_agent/core/permissions/policy.py src/harness_agent/core/permissions/protected.py src/harness_agent/core/permissions/exact_calls.py src/harness_agent/core/permissions/approvals.py src/harness_agent/core/permissions/rules.py tests/doubles docs/archivo
```

Esperado:

- las cuatro puertas en exit 0;
- el 100 % en los módulos nuevos y en las líneas nuevas de `config.py`, `bootstrap.py` y `denied_commands.py`;
- un diff vacío en los archivos protegidos.
