# Quickstart: validar HU-02-06.1 sin red ni claves

Guía de validación; el detalle está en los contratos y en el modelo de datos. Todo corre con el proveedor simulado y bases de datos en `tmp_path`.

## Requisitos previos

```powershell
python -m venv .venv; .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt; pip install -e . --no-deps
```

## 1. Antes de tocar nada: las pruebas existentes que van a cambiar

Con el esquema 4 en su sitio, estas pruebas fallan **por la versión o por la tabla nueva** y solo ellas (lista exacta en `plan.md`). Ejecutarlas **sin tocar** y ver el rojo antes de ajustar las líneas declaradas:

```powershell
pytest tests/unit/adapters/storage/test_schema.py tests/unit/adapters/storage/test_schema_migration.py tests/unit/adapters/storage/test_schema_v3.py tests/unit/adapters/storage/test_public_api.py tests/integration/test_rejection_reason_agent_loop.py -q --no-cov
```

## 2. El texto del bloque (T002–T003)

```powershell
pytest tests/unit/core/context/test_essential_items.py tests/unit/core/context/test_essential_block.py -q --no-cov
```

Comprueba los ejemplos E1–E7 de `contracts/block_format.md` carácter a carácter, los topes (rechazo sin truncar) y que las instrucciones nunca entran en el texto.

## 3. El renovador (T004)

```powershell
pytest tests/unit/core/context/test_essential_renewer.py tests/unit/core/context/test_essential_renewer_failures.py tests/unit/core/context/test_essential_renewer_properties.py -q --no-cov
```

Sustitución in situ, idempotencia, el intento de imitar la marca desde `USER`, `TOOL` y `ASSISTANT`, la falla cerrada (fuente ilegible, elementos que faltan, no cabe) y nunca dos bloques (2 000 historiales al azar con semilla fija).

## 4. El esquema 4 y el adaptador (T005–T006)

```powershell
pytest tests/unit/adapters/storage/test_schema_v4.py tests/unit/adapters/storage/test_essential_store.py -q --no-cov
```

Migración desde bases reales de las versiones 1, 2 y 3 (comparación de filas antes y después), escritura única, rollback con disparadores SQL, sin conexión propia.

## 5. El cableado y la sesión de punta a punta (T007–T009)

```powershell
pytest tests/unit/test_bootstrap_essential.py tests/integration/test_essential_context_agent_loop.py tests/integration/test_essential_context_security.py -q --no-cov
```

Escenarios que debe cubrir la sesión simulada (proveedor que graba lo recibido, cinco valores centinela distintos):

| Escenario | Resultado esperado |
|---|---|
| Varias llamadas en una petición y dos compactaciones seguidas | El bloque está una sola vez en cada llamada, idéntico byte a byte y en la misma posición (AC-01) |
| Tras compactar | Las instrucciones siguen intactas (una sola vez cada una) y los criterios salen de su fuente (AC-02) |
| Resumen simulado que pierde el objetivo; se pregunta por él | El proveedor simulado lo responde porque el contexto lo lleva (AC-03) |
| Un criterio pasa a cumplido entre rondas | El bloque cambia en la ronda siguiente; nunca hay dos bloques |
| Tarea sin reglas ni título | Bloque sin esos encabezados |
| Bloque que no cabe / fuente alterada | La petición no se envía; mensaje fijo; sin valores en eventos ni avisos |
| El modelo intenta escribir en la base | La política lo deniega; la tabla no cambia |
| Llamada real de resumen del compactador | Su entrada no contiene el bloque ni ninguno de sus valores |
| Sesión sin tarea | Contexto idéntico al de hoy |
| Sesión **con** tarea y filas borradas | La petición no se envía; mensaje de «faltan elementos»; código 1 (nunca se trata como sesión sin tarea) |
| El guardado falla tras `start_task` | `compose` lanza, el almacén queda cerrado y no hay composición |

## 6. Fronteras y las cuatro puertas

```powershell
pytest tests/architecture
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
```

La guarda nueva (`test_essential_boundaries.py`) vigila: módulos puros sin E/S ni importaciones prohibidas, sin `BaseException`, adaptador sin conexión propia y sin importar el bucle, y que **solo la composición** renueva el bloque. Cada regla lleva su prueba de mutación.

## 7. Comprobar que lo prohibido no cambió

```bash
base=$(git merge-base HEAD origin/main)
git diff --exit-code $base -- src/harness_agent/core/loop.py src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/redaction.py src/harness_agent/core/verification src/harness_agent/core/context/cut.py src/harness_agent/core/context/compactor.py tests/doubles docs/archivo
```

## Lo que NO se puede comprobar aquí

- Que un modelo **real** use bien el bloque y responda el objetivo tras compactar (AC-03 con un modelo real): corrida de SPK-03, depende de D-IA (H5).
- Que el bloque llegue desde la línea de comandos: `main()` no carga tareas (R1); solo `compose(task=…)`.
