# Quickstart: validar HU-11-02

## Requisitos

- Entorno como en la CI: `pip install -r requirements-dev.txt; pip install -e . --no-deps`.
- Sin red ni claves. Solo la prueba de Sp2-45 usa git real (se omite si no está instalado) y solo ejecuta `init`, `add`, `commit`, `status`, `diff` y `log` en una carpeta temporal aislada.

## 1. Clasificación y política (núcleo puro)

```powershell
pytest tests/unit/core/permissions/test_git_rules.py tests/unit/core/permissions/test_git_policy.py tests/unit/core/permissions/test_git_properties.py -q
```

Esperado:

- todos los ejemplos normativos de [contracts/git_policy_contract.md](contracts/git_policy_contract.md) en los dos dialectos;
- las baterías SC-001 (≥ 20 lecturas), SC-002 (≥ 20 destructivas) y SC-003 (≥ 15 escrituras, desconocidos y `-c`), también con `inner` = `ALLOW`;
- con semilla fija, ninguna excepción y ningún destructivo en una parte ejecutable sale `ALLOW`;
- `git_rules.py` al 100 %.

## 2. Ocultado de credenciales y guardas

```powershell
pytest tests/unit/core/test_redaction.py tests/unit/adapters/tools/test_shell_redaction.py tests/architecture -q
```

Esperado:

- los cuatro casos de la tabla del contrato;
- la salida de `ShellTool` en éxito, error y tiempo agotado sin credenciales;
- `test_git_rules_boundaries.py` y `test_redaction_boundaries.py` en verde.

## 3. Composición y convivencia (shell doble)

```powershell
pytest tests/unit/test_bootstrap_git.py tests/integration/test_git_policy_agent_loop.py -q
```

Esperado:

- la cadena real deniega lo destructivo, pregunta push y merge aunque la tarea los declare, y permite las lecturas;
- `ProtectedPolicy`, la lista de denegados y la lista `ask` prevalecen;
- una aprobación de sesión de `git commit` no autoriza un push (una aprobación de sesión del mismo push exacto sí se reutiliza: supuesto del PO);
- `.git` no se puede leer ni escribir con las herramientas de archivos y `git status` se permite;
- el prefijo contiene las instrucciones de git;
- ningún evento lleva el comando y ningún resultado lleva credenciales.

## 4. Repositorio temporal con git real (Sp2-45)

```powershell
pytest tests/integration/test_git_real_repository.py -q -rs
```

Esperado:

- `status`, `diff` y `log` se ejecutan sin aprobador;
- el estado del repositorio no cambia (HEAD, refs, `status --porcelain`, `diff --cached`, árbol de trabajo);
- un `log` largo llega con `[salida recortada: se omitieron`;
- si git no está instalado, se omite con su motivo.

## 5. Cierre

```powershell
ruff format --check .; ruff check .; mypy src tests; pytest --cov=harness_agent --cov-report=term-missing
git diff --exit-code (git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/loop.py src/harness_agent/core/permissions/policy.py src/harness_agent/core/permissions/protected.py src/harness_agent/core/permissions/exact_calls.py src/harness_agent/core/permissions/approvals.py src/harness_agent/core/permissions/rules.py src/harness_agent/core/permissions/command_parser.py src/harness_agent/core/permissions/command_rules.py src/harness_agent/core/permissions/command_policy.py src/harness_agent/adapters/system/protected_paths.py src/harness_agent/config.py src/harness_agent/cli tests/doubles docs/archivo
```
