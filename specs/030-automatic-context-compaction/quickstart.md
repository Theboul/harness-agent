# Quickstart: validar HU-02-03

## Requisitos

- Entorno como en la CI: `pip install -r requirements-dev.txt; pip install -e . --no-deps`.
- Sin red ni claves: el proveedor es `FakeProvider`. Las bases de datos son archivos en `tmp_path` (algunas creadas con el esquema 1 y 2 para probar la migración).

## 1. Umbral por modelo y configuración

```powershell
pytest tests/unit/core/context/test_settings.py tests/unit/test_config_context.py -q
```

Esperado: la tabla de [contracts/context_settings.md](contracts/context_settings.md) (32000 → 25600 y 7680, 128000 → 102400 y 30720…); sin la sección rigen los valores por defecto; cada valor inválido detiene el arranque con el nombre del campo y sin repetir el valor; `config.example.toml` carga con la sección comentada.

## 2. Corte seguro, ventana reciente y orden del contexto

```powershell
pytest tests/unit/core/context/test_cut.py tests/unit/core/context/test_cut_properties.py -q
```

Esperado: los casos E1 a E4 de [contracts/context_order.md](contracts/context_order.md); con semilla fija, nunca queda un resultado de herramienta huérfano, se respeta el mínimo de recientes, los recientes son los mismos objetos y el resultado es determinista.

## 3. El resumen (prompt, transcripción, limpieza y marco)

```powershell
pytest tests/unit/core/context/test_summary.py -q
```

Esperado: el prompt y la transcripción exactos de [contracts/summary_prompt.md](contracts/summary_prompt.md); el resumen sale limpio y sin credenciales de URL; un resumen vacío o demasiado largo se rechaza sin repetir el texto; el marco lo hace `USER` externo.

## 4. El almacén: esquema 3 y transacción única

```powershell
pytest tests/unit/adapters/storage/test_schema_v3.py tests/unit/adapters/storage/test_schema_migration.py tests/unit/adapters/storage/test_compaction_archive.py tests/unit/adapters/storage/test_event_recorder_skip.py -q
```

Esperado:

- una base en el esquema 1 y otra en el 2 se migran al 3 sin perder ninguna fila (comparación de todas las tablas antes y después);
- los ejemplos E1 a E4 de [contracts/store_protocol.md](contracts/store_protocol.md): rango, marcas, evento `{desde, hasta, eventos}`, idempotencia y rollback con fallos inyectados en cada paso;
- **marcar no altera el contenido**: las filas de `events` antes y después son iguales salvo `compacted_by`, y `load_session` devuelve todo;
- **un solo registro del evento**: con `skip` hay una fila; sin él, el segundo intento falla con `DuplicateEvent`.

## 5. El orquestador

```powershell
pytest tests/unit/core/context/test_compactor.py -q
```

Esperado, con un almacén y un proveedor de prueba: por debajo del umbral, 0 llamadas; por encima, una llamada **sin herramientas** cuya entrada no contiene la cabeza protegida ni los recientes; una compactación por turno; sin eventos nuevos, 0 llamadas y 0 escrituras; fallo de la llamada, de la validación, de la correspondencia o del guardado → historial intacto y `provider_error` fijo; cancelación propagada; advertencia si sigue sobre el umbral.

## 6. Cableado y sesión larga

```powershell
pytest tests/unit/test_bootstrap_compaction.py tests/integration/test_context_compaction_agent_loop.py -q
```

Esperado:

- **AC-01**: una sesión larga con `FakeProvider` supera el umbral, la petición siguiente dispara una llamada de resumen y el bucle recibe prefijo, petición inicial, resumen externo y recientes idénticos;
- **AC-02**: los eventos guardados no bajan, no cambian y los cubiertos están marcados; hay una fila en `resumenes` y un `context_compacted` con la carga sin texto;
- un segundo umbral produce una segunda compactación con el resumen anterior como entrada y un solo resumen en el contexto;
- fallos simulados: nada parcial y el turno sigue;
- **no filtración**: con centinelas y una credencial de prueba, ningún evento, error ni advertencia los contiene y `resumenes.texto` no lleva la credencial.

## 7. Guardas y cierre

```powershell
pytest tests/architecture -q
ruff format --check .; ruff check .; mypy src tests; pytest --cov=harness_agent --cov-report=term-missing
git diff --exit-code (git merge-base HEAD origin/main) -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/loop.py src/harness_agent/core/in_memory_event_bus.py src/harness_agent/core/redaction.py src/harness_agent/core/permissions src/harness_agent/core/tasks src/harness_agent/core/verification src/harness_agent/adapters/tools src/harness_agent/cli tests/doubles docs/archivo
```

Esperado: las cuatro puertas en exit 0, el 100 % de líneas y ramas en los módulos nuevos, el diff de lo protegido vacío y la guarda `test_compaction_boundaries.py` en verde. El detector de secretos se pasa a mano sobre los archivos nuevos y modificados.
