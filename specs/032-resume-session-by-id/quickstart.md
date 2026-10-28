# Quickstart: validar HU-03-04 (Reanudar una sesión por identificador)

Guía de validación; el detalle de cada comprobación está en `contracts/` y en `data-model.md`. Todo corre sin red, sin claves y sin proveedor real (`FakeProvider` y dobles).

## Prerrequisitos

```powershell
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt; pip install -e . --no-deps
```

## 1. Las cuatro puertas de calidad (todas en exit 0)

```powershell
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
```

Esperado al cerrar: sin fallos, 47 omitidas (las de siempre en Windows) y 100 % de líneas y ramas en los módulos nuevos (`conversation.py`, `resume.py`, `message_store.py`) y en el código nuevo de `bootstrap.py` y `cli/app.py`.

## 2. Fronteras hexagonales

```powershell
pytest tests/architecture
```

Esperado: todo en verde, incluida `test_conversation_boundaries.py` (módulos puros, adaptador sin conexión propia ni bucle, **solo la composición suscribe el guardado y reanuda**, con pruebas de mutación).

## 3. Pruebas por escenario

| Qué se valida | Comando | Esperado |
|---|---|---|
| Guardado y reconstrucción puros (ejemplos E1–E10, azar de semilla 20261101) | `pytest tests/unit/core/context -k "conversation or resume"` | verde |
| Esquema 5 y migración desde bases reales v1–v4 | `pytest tests/unit/adapters/storage/test_schema_v5.py` | cada tabla anterior idéntica fila a fila; `mensajes` vacía |
| Almacén de mensajes y contrato | `pytest tests/unit/adapters/storage/test_message_store.py tests/contracts/test_message_log_contract.py` | atómico, idempotente, cobertura de resúmenes |
| Comando con argumento de la CLI | `pytest tests/unit/cli/test_app_argument_commands.py` | el argumento llega; sin él, todo igual |
| Cableado: orden mensaje → evento → CLI, fallo del guardado, `/reanudar` | `pytest tests/unit/test_bootstrap_capture.py tests/unit/test_bootstrap_resume.py` | verde |
| **AC-01 y AC-02 de punta a punta** | `pytest tests/integration/test_resume_agent_loop.py` | el historial reconstruido es igual al de memoria (con y sin compactación); la primera petición tras reanudar compacta si supera el umbral; misma sesión, `seq` continuo, 0 eventos duplicados |
| Cortes y cierre idempotente | `pytest tests/integration/test_resume_cuts.py` | historial válido en cada punto del turno; el cierre se escribe una sola vez por llamada; dos cortes, cada uno una vez |
| Errores y marca «sin detalle» | `pytest tests/integration/test_resume_errors.py` | errores fijos para inexistente, inválido, sesión activa, tarea, sin detalle (también tras un almacén que falla, desde una base reabierta y desde otro proceso) e incoherente |
| Seguridad | `pytest tests/integration/test_resume_security.py` | 0 apariciones de centinelas en eventos, errores, avisos y terminal; motivo del rechazo y credenciales de URL en 0 bytes de la base; el modelo no lee ni edita la tabla |

## 4. Comprobaciones manuales de lo que no cubre un modelo real

La calidad con que un modelo real continúa una sesión reanudada no se valida aquí (D-IA: sin proveedor real). Con un modelo real y su clave en el entorno (cuando el equipo lo decida): ejecutar `harness`, escribir una tarea, salir con `/salir`, volver a abrir `harness` y escribir `/reanudar <id>` con el identificador de la sesión anterior (se obtiene de la base). Esperado: una línea de estado y el agente continúa sin repintar la conversación.

## 5. Archivos protegidos y limpieza

```bash
git diff --exit-code -- src/harness_agent/core/interfaces src/harness_agent/core/events.py \
    src/harness_agent/core/loop.py src/harness_agent/core/redaction.py src/harness_agent/core/verification \
    src/harness_agent/core/context/compactor.py src/harness_agent/core/context/cut.py \
    src/harness_agent/core/context/essential.py src/harness_agent/core/context/renewer.py \
    tests/doubles docs/archivo
git status --short
```

Esperado: `git diff` en exit 0 (vacío). `git status` solo lista los archivos de las tablas de `plan.md` (más `specs/032-…`).

## 6. Pruebas existentes ajustadas

Las 24 pruebas de `plan.md` («Pruebas existentes que cambian») se ejecutan **antes, sin tocar**, para ver el rojo previsto, y se ajustan después. Cualquier otra prueba existente que falle detiene la implementación.
