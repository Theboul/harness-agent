# Quickstart: validar HU-11-04.1

## Requisitos

- Entorno como en la CI: `pip install -r requirements-dev.txt; pip install -e . --no-deps`.
- Sin red ni claves: el proveedor es `FakeProvider`, el aprobador un doble o `ConsoleApprover` sobre flujos de texto. La matriz de casos usa un shell doble que **registra** y no ejecuta nada; un único flujo usa el shell real con comandos triviales de Python en `tmp_path` y se omite si no hay intérprete. Ningún comando denegado o preguntado se ejecuta jamás en pruebas.

## 1. La condición y el analizador de la tarea

```powershell
pytest tests/unit/core/tasks/test_condition.py tests/unit/core/tasks/test_condition_properties.py tests/unit/core/tasks/test_task_parser.py -q
```

Esperado: todos los ejemplos de [contracts/condition_contract.md](contracts/condition_contract.md); una condición distinta de `codigo_salida == N` o `!= N` hace inválida la tarea con `condicion_no_soportada` y un mensaje que no repite el texto; la prueba al azar (semilla 20261029) nunca lanza. Ajustes a pruebas existentes (research R11): `tests/integration/test_task_start.py` y `tests/unit/adapters/tasks/test_task_source.py`.

## 2. El aviso, la evidencia y el estado (puros)

```powershell
pytest tests/unit/core/verification/test_outcomes.py tests/unit/core/verification/test_feedback.py tests/unit/core/verification/test_feedback_properties.py -q
```

Esperado: ejemplos de [contracts/agent_notice_contract.md](contracts/agent_notice_contract.md) (texto exacto), `task_state` según el modelo de datos, y al azar: el aviso nunca contiene el comando ni una credencial de prueba y respeta sus límites.

## 3. El verificador

```powershell
pytest tests/unit/core/verification/test_verifier.py tests/unit/core/verification/test_runner.py tests/unit/adapters/tools/test_shell_outcome.py -q
```

Esperado, con dobles de política, almacén (`SqliteTaskStore` en `tmp_path`), aprobador y runner: la matriz de siete casos (todos cumplen, uno falla, regresión, comando alterado, política que pregunta sin aprobador, tiempo agotado, criterio sin comando); un denegado no llega al aprobador; la aprobación de la persona decide el «preguntar»; todos los criterios objetivos se ejecutan en cada propuesta; las rondas terminan cuando el bucle devuelve `LIMIT_REACHED` o nada es corregible; `mark_passes` solo se llama tras cumplir la condición. El adaptador fija las etiquetas reales de `ShellTool`.

## 4. La terminal

```powershell
pytest tests/unit/cli/test_criteria.py tests/unit/cli/test_app_criteria.py tests/unit/test_bootstrap_verification.py -q
```

Esperado: las líneas y los estados de [contracts/cli_status_contract.md](contracts/cli_status_contract.md), `/criterios` sin y con verificación, texto saneado y acotado, nunca los argumentos del comando; `compose()` monta el runner solo con tarea; las pruebas existentes de la CLI (`SHOWN_TYPES`, `/ayuda`) pasan sin cambios.

## 5. De punta a punta (Sp2-53) y no filtración

```powershell
pytest tests/integration/test_criteria_verification_agent_loop.py -q
```

Esperado:

- ticket de ejemplo con tres criterios (dos con comando y uno semántico) sobre un proyecto en `tmp_path`: el agente (proveedor falso) modifica el proyecto, propone terminar, el harness ejecuta los dos comandos, la CLI muestra `[x]`, `[ ]` y `[?]` y, tras corregir, el estado final es «pendiente de validación humana»;
- «cumplido» solo aparece después de que se ejecutó el comando;
- denegados, git destructivo y zona protegida: 0 preguntas y 0 ejecuciones; un comando que la política pregunta sin aprobador no se ejecuta;
- ningún evento, mensaje de error ni evidencia contiene el comando, la salida o la credencial de prueba; el aviso nunca contiene el comando y la salida llega como contenido externo;
- ninguna herramienta registrada expone `mark_passes`;
- un único flujo con el shell real y `python -c "…"` triviales.

## 6. Guardas y cierre

```powershell
pytest tests/architecture -q
ruff format --check .; ruff check .; mypy src tests; pytest --cov=harness_agent --cov-report=term-missing
git diff --exit-code (git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/loop.py src/harness_agent/core/in_memory_event_bus.py src/harness_agent/core/redaction.py src/harness_agent/core/permissions src/harness_agent/config.py src/harness_agent/adapters/tools/shell.py src/harness_agent/adapters/storage tests/doubles docs/archivo
```

Esperado: las cuatro puertas en exit 0, 100 % de líneas y ramas en los módulos nuevos, `core/loop.py` y los puertos sin diff, y la guarda `test_verification_boundaries.py` en verde (único escritor de passes en todo `src/`). El detector de secretos se pasa a mano sobre los archivos nuevos y modificados.
