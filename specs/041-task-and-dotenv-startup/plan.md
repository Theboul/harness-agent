# Plan de implementación: HU-00-08.1 — Tarea desde el comando y `.env` (propuesta)

**Spec**: [spec.md](spec.md) · **Rama**: `claude/wire-task-and-dotenv-a8b914` · **Fecha**: 2026-10-31

## Resumen

Dos piezas pequeñas fuera de `core/`: un adaptador `adapters/system/dotenv.py` (lector tolerante de `.env`) y el cableado en `bootstrap.py::main` (análisis manual de `--tarea`/`--issue`, carga de la tarea con `adapters/tasks`, entorno combinado). Sin dependencias nuevas.

## Constitution Check (reglas duras de las tres skills)

| Regla | Cumple | Nota |
|---|---|---|
| `core/` no cambia ni lee archivos/entorno | Sí | todo en adaptador y `bootstrap` |
| Puertos, eventos y `core/loop.py` sin cambios | Sí | |
| E/S en `adapters/` | Sí | `adapters/system/dotenv.py` lee el archivo |
| Adaptador solo stdlib + su paquete | Sí | guarda `test_dotenv_boundaries.py` |
| `bootstrap.py` sin `os.environ`/`print`/`input` | Sí | el entorno llega por `process_environment()` o parámetro; avisos por `_write_notice` |
| Falla cerrada | Sí | tarea inválida → salida 2; `.env` roto → se ignora lo no válido, nunca se interpreta |
| Sin secretos | Sí | valores del `.env` nunca en salida; `.env.example` sin valores |
| Dependencias inyectables | Sí | `gh_runner`, `environ`, `argv`, `changes` |

**Gates**: ¿regla nueva en `core/`? No. ¿Algo de fuera? Disco → adaptador. ¿Conexión? `bootstrap.py`. ¿Prueba? Unitarias del adaptador, de `main`, integración extremo a extremo con `FakeProvider`.

## Estructura

| Archivo | Fila |
|---|---|
| `adapters/system/dotenv.py` (+ API en `adapters/system/__init__.py`) | lee disco → `adapters/system/` |
| `bootstrap.py` (`StartupArguments`, `parse_arguments`, `entry`, `main(argv=, gh_runner=, changes=)`) | conexión |
| `__main__.py`, `pyproject.toml` (`harness = …:entry`) | punto de entrada |
| `tests/unit/adapters/system/test_dotenv.py`, `tests/unit/test_bootstrap_arguments.py`, `tests/integration/test_main_with_task.py`, `tests/architecture/test_dotenv_boundaries.py` | carpeta equivalente |
| `tests/architecture/test_bootstrap_boundaries.py` | `adapters.tasks` pasa a la API pública permitida |
| `.env.example` | ejemplos vacíos |

## Diseño

- `read_dotenv(path) -> DotenvResult(values, skipped, unreadable)`; `merge_environment(environ, values)` devuelve un dict nuevo con el entorno real prevaleciendo.
- `main`: (1) analiza `argv`; (2) entorno real + `.env`; (3) `load_config(environ=combinado)`; (4) carga la tarea; (5) `compose(task=…, environ=combinado)`. Cualquier `TaskSourceError`/`TaskFormatError`/`StartupError` → una línea, salida 2.
- `entry()` pasa `sys.argv[1:]`; hay que reinstalar el paquete editable para regenerar el script `harness`.

## Lista de comprobación de `capas-y-reglas.md` (al cerrar)

| Pregunta | Respuesta |
|---|---|
| ¿`core/` sin cambios y sin E/S? | Sí |
| ¿Adaptador en su capa, imports permitidos? | Sí (guarda propia) |
| ¿Conectado solo en `bootstrap.py`? | Sí |
| ¿Falla cerrada? | Sí |
| ¿Algún «no»? | No |
