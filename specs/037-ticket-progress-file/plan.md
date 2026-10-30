# Plan de implementación: HU-11-08.1 — Archivo de progreso del ticket

**Spec**: [spec.md](spec.md) · **Rama**: `claude/hu-11-08-1-progress-file-30590f` · **Fecha**: 2026-10-30

## Resumen

Núcleo puro `core/progress/` (instantánea, formato fijo, grabador que reúne criterios + historial y llama a un destino) y un adaptador `adapters/storage/progress_file.py` (escritura atómica en la carpeta de trabajo). `bootstrap.py` crea el grabador cuando hay tarea y área, y `run_session` lo invoca tras cada petición y al final. No cambia puertos, eventos ni el bucle.

## Contexto técnico

Python 3.12, mypy estricto, ruff línea 100, sin dependencias nuevas. Pruebas con reloj y destino inyectados; la atomicidad se prueba con un fallo simulado entre el temporal y el renombrado (`replace` inyectable) y con un subproceso terminado de golpe.

## Constitution Check (reglas duras de las tres skills)

| Regla | Cumple | Nota |
|---|---|---|
| `core/` solo stdlib y `harness_agent.core`; sin E/S, sin `print`, sin entorno | Sí | `core/progress/` define un `Protocol` de destino (`ProgressSink`, como `CompactionStore`); no abre archivos |
| Puertos de `core/interfaces/`, eventos y `core/loop.py` sin cambios | Sí | se usa `TaskCriteria.load_criteria` existente; sin evento nuevo |
| E/S en `adapters/` | Sí | `adapters/storage/progress_file.py` |
| Adaptador no importa `cli`, otro adaptador ni `config`; solo stdlib y API pública de `core` | Sí | |
| Reloj y rutas por constructor | Sí | `clock`, `root` |
| Falla cerrada | Sí | nombre seguro o ninguno; fallo de escritura = aviso + último punto conservado, nunca archivo parcial |
| Sin secretos | Sí | no se escriben comandos, evidencias ni argumentos; credenciales de URL ocultas |
| `bootstrap.py` única raíz de composición, cambio mínimo | Sí | una pieza de cableado |
| Guarda `ast` del módulo nuevo | Sí | `tests/architecture/test_progress_boundaries.py` |

**Gates de decisión**: ¿regla nueva en `core/`? sí (qué se anota y cómo se formatea). ¿Necesita algo de fuera? sí, un archivo → destino inyectado. ¿Quién lo implementa? `adapters/storage/` (área B). ¿Cómo se conecta? Por constructor desde `compose()`; `run_session` lo llama.

## Estructura (fila de `estructura-carpetas-harness` que lo justifica)

| Archivo | Fila |
|---|---|
| `src/harness_agent/core/progress/{__init__,snapshot,render,recorder}.py` | regla de dominio sin E/S → `core/<paquete>/` (como `core/context/`, `core/verification/`) |
| `src/harness_agent/adapters/storage/progress_file.py` | escritura de archivos del almacén de estado → `adapters/storage/` |
| `src/harness_agent/bootstrap.py` (+ `Composition.progress`) | conexión → solo `bootstrap.py` |
| `tests/unit/core/progress/`, `tests/unit/adapters/storage/test_progress_file.py`, `tests/integration/test_progress_session.py`, `tests/architecture/test_progress_boundaries.py` | carpeta equivalente de `tests/` |

## Diseño

- `ProgressSnapshot(ticket, session_id, turn, kind, updated_at, objective, criteria, note)`; `CriterionLine(position, description, state)`; `CriterionState`; `CheckpointKind`.
- `render_progress(snapshot) -> str` y `progress_file_name(ticket, session_id) -> str`.
- `ProgressRecorder(sink, criteria, *, ticket, objective, session_id, clock, warn)`: `checkpoint(history)` (turno +1) y `finish(history)`; captura `Exception` (no `BaseException`) al leer criterios o escribir.
- `ProgressSink` (Protocol): `write(name, text)`, `read(name)`.
- `ProgressFile(root, *, replace=os.replace)`: valida el nombre, escribe `<root>/.<name>.<pid>.tmp`, `flush` + `fsync`, `replace`; borra el temporal si falla; `ProgressWriteError` con texto fijo.

## Riesgos

El agente puede editar el archivo (está en el área); se reescribe en el siguiente punto de control. HU-11-08.2 debe tratar el contenido como dato no confiable (puede llevar texto del agente).

## Lista de comprobación de `capas-y-reglas.md` (revisada contra el código al cerrar)

| Pregunta | Respuesta |
|---|---|
| ¿`core/` importa solo stdlib y `harness_agent.core`? | Sí (`test_progress_boundaries.py`) |
| ¿El núcleo evita E/S, entorno, configuración y terminal? | Sí; el destino es un `Protocol` inyectado |
| ¿Puertos de `core/interfaces/`, eventos y bucle sin cambios? | Sí (diff de protegidos vacío) |
| ¿El adaptador está en `adapters/` y solo usa stdlib y la API pública del núcleo? | Sí (`adapters/storage/progress_file.py`, guarda de `test_adapters_boundaries.py`) |
| ¿Dependencias por constructor (reloj, destino, `replace`)? | Sí |
| ¿Conectado solo en `bootstrap.py`? | Sí (guarda: ningún otro módulo nombra `ProgressFile`) |
| ¿Falla cerrada? | Sí: nombre inválido o ilegible = error; fallo de escritura = aviso y se conserva el punto anterior |
| ¿Prueba de contrato del adaptador real? | Sí, `test_progress_file.py` (incluye subproceso terminado de golpe) |
| ¿Algún «no»? | No hay |
