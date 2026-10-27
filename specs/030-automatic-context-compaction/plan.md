# Implementation Plan: HU-02-03 — Compactación automática por umbral

**Branch**: `gustavo` (directorio de la spec: `030-automatic-context-compaction`) | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/030-automatic-context-compaction/spec.md`

## Summary

Al empezar cada petición de la persona, la composición estima el contexto y, si supera el umbral del modelo, **resume lo antiguo con una llamada aparte** y entrega al bucle un contexto reducido, sin borrar nada del historial guardado.

- `core/context/` (puro): `ContextSettings` y el umbral por modelo, el corte seguro y la partición del historial, el prompt y la transcripción del resumen, el resumen enmarcado como contenido externo y el orquestador `ContextCompactor` con colaboradores inyectados (proveedor sin herramientas, protocolo del almacén, eventos, avisos).
- `adapters/storage/`: esquema SQLite **v3 aditivo** (tabla `resumenes`), `SqliteCompactionArchive` (una transacción para guardar el resumen, marcar los eventos y registrar `context_compacted`) y un parámetro opcional `skip` del registrador de eventos para que ese evento se guarde **una sola vez**.
- `config.py`: sección opcional `[context]`.
- `bootstrap.py`: solo cablea, como hizo HU-11-04.1 con el verificador.

No cambian `core/loop.py`, `core/interfaces/`, el catálogo de eventos ni `core/redaction.py`.

## Technical Context

**Language/Version**: Python 3.12; solo biblioteca estándar en `core/`.

**Primary Dependencies**: ninguna nueva. Reutiliza el estimador de HU-02-01 (`estimate_messages`, `estimate_tool_definition`), el puerto `Provider`, `core/redaction.py` (lineal), `SqliteSessionStore` y su conexión compartida, y el patrón de composición de HU-11-04.1.

**Storage**: SQLite: esquema 3 (tabla `resumenes`; `events.compacted_by` ya existe). Migración aditiva desde los esquemas 1 y 2.

**Testing**: pytest (`asyncio_mode = "auto"`), `FakeProvider`, bases reales en `tmp_path` (también creadas con el esquema 1 y 2), pruebas al azar con semilla 20261031, una sesión larga simulada propia en `tests/` (sin importar `tests/spikes/` desde `src/`).

**Target Platform**: Windows y Linux (CI de ambos).

**Project Type**: biblioteca/CLI hexagonal.

**Performance Goals**: sin llamada ni escritura por debajo del umbral; estimación lineal en el tamaño del historial; la transcripción corta cada mensaje (2000 caracteres) y cada resultado de herramienta (500).

**Constraints**:
- sin cambios en `core/loop.py`, `core/interfaces/`, el catálogo de eventos ni `core/redaction.py`;
- `core/` no importa `adapters/` ni `cli/`;
- la compactación **nunca** borra ni modifica un evento; una sola transacción; idempotente;
- falla cerrada y nada parcial; ni resumen ni historial en eventos o errores;
- el ensamblador **no** está cableado: se estima con las funciones puras (R1).

**Scale/Scope**: unos 6 módulos nuevos en `core/context/`, 1 adaptador, un paso de esquema, un parámetro del registrador, una sección de configuración y ajustes pequeños en `bootstrap.py`; unos 14 archivos de pruebas y 1 guarda.

## Constitution Check

*GATE: pasa antes de la Fase 0 y se revisa tras la Fase 1.*

| Principio / regla | Cumplimiento |
|---|---|
| I. Una historia, una spec | Solo HU-02-03 (Sp2-14 a Sp2-17). Pasa |
| II. Microtareas de 15–40 min | 9 tareas de implementación de ≤ 40 min más inicio y cierre. Pasa |
| III. Código modular, tipado, Python 3.12 | Módulos pequeños y puros, `dataclass(frozen=True)`, `mypy` del repo. Pasa |
| IV. Pruebas y CI multiplataforma | Sin red ni claves; bases en `tmp_path`. Pasa |
| V. Criterios inmutables | AC-01, AC-02, flujo y reglas copiados tal cual (comprobado). Pasa |
| VI. Disciplina de sprints | Fuera: HU-02-06.1/.2, HU-03-04, HU-02-04, HU-07-05, PD-06, gancho en el bucle, corrida real. Pasa |
| VII. Consulta quirúrgica | Ancla `#hu-02-03`, SPK-03 y el código citado. Pasa |
| VIII. PROGRESO.md | Fila de inicio y cierre (`En revisión`) con observaciones |
| IX. DoD estricta | Tareas humanas H1–H8 |
| X. `docs/archivo/` | No se toca. Pasa |
| V-03, V-04, V-10, V-17 | El historial original se conserva (V-03); lo esencial no se resume (V-04, cabeza protegida); el umbral es por modelo y se recalcula (V-10); el resumen es contenido externo (V-17). Pasa |

**Hard Rules de las skills del proyecto**

- **`arquitectura-hexagonal-clean`**: la regla (umbral, corte, composición, orquestación) es pura y vive en `core/context/`. Lo externo entra por colaboradores inyectados: el puerto `Provider` (existente) y un **protocolo** del almacén definido en `core/context/` (no en `core/interfaces/`, para no cambiar contratos) que implementa un adaptador. Todo se conecta solo en `bootstrap.py`. Los puertos no cambian; el reajuste de `SessionStore`/`ContextManager` (SPK-03 §6) queda para un acuerdo posterior.
- **`estructura-carpetas-harness`**: rutas en la tabla de abajo; ninguna carpeta nueva.
- **`verificar-fronteras-hexagonales`**: `core/context/` ya tiene su guarda (`test_context_boundaries.py`); se añade `test_compaction_boundaries.py` para las reglas propias.

### Recorrido de los *Decision Gates* (`arquitectura-hexagonal-clean`)

| Pregunta | Respuesta |
|---|---|
| ¿Regla o comportamiento nuevo? | Sí: decidir cuándo y qué compactar, en `core/context/`, exportado en `core/__init__.py` |
| ¿Necesita algo de fuera? | Sí: el proveedor (puerto existente) y el almacén (protocolo nuevo en `core/context/`) |
| ¿Quién lo implementa? | El proveedor real o simulado; `SqliteCompactionArchive` (adaptador nuevo de B) |
| ¿Cómo se conecta? | Inyección en constructor; `bootstrap.py` lo monta |
| ¿Cómo se prueba? | Núcleo con `FakeProvider` y un almacén de prueba; adaptador con bases reales; integración con `compose()` |
| ¿Es asíncrono? | El orquestador sí (espera al proveedor); el corte, la composición y el umbral no |

### Lista de comprobación de `capas-y-reglas.md` (respuesta de diseño; se revisa de nuevo al cerrar)

| Punto | Resp. | Justificación |
|---|---|---|
| ¿Regla de negocio en `core/` y no en un adaptador? | Sí | `core/context/` |
| ¿Todo lo externo pasa por un puerto o protocolo con tipos del dominio? | Sí | `Provider` y `CompactionStore` (protocolo interno) |
| ¿Puertos, entidades y eventos sin cambios? | Sí | Ninguno cambia; `context_compacted` ya existía |
| ¿Errores sin reproducir valores? | Sí | Mensajes fijos; `provider_error` con contenido fijo |
| ¿Inyección y conexión solo en `bootstrap.py`? | Sí | Se añaden el archivo, el compactador y el `skip` del registrador |
| ¿Núcleo probado con dobles, sin red ni claves? | Sí | `FakeProvider`; SQLite solo en pruebas del adaptador y de integración, en `tmp_path` |
| ¿Prueba de contrato del adaptador? | Sí | `test_compaction_archive.py` fija las garantías de `store_protocol.md` |
| ¿`pytest tests/architecture` con la guarda nueva? | Sí (diseño) | `test_compaction_boundaries.py` |
| ¿Eventos en lugar de imprimir? | Sí | `context_compacted` y `provider_error`; la advertencia sale por el `warn` de la composición |
| ¿Lo público exportado en `core/__init__.py`? | Sí | Lista en el modelo de datos |
| ¿Falla cerrada y secretos? | Sí | Nada parcial; resumen como externo y sin credenciales de URL; sin texto en eventos |
| ¿Otro integrante revisó el cambio? | No (pendiente) | H3 |

**Resultado del gate**: pasa. Desviaciones en *Complexity Tracking*.

### Revisión de la lista contra el código (T010, 2026-10-27)

Los once «Sí» de diseño se confirman contra el código: la regla vive en `core/context/` (stdlib y núcleo; `test_context_boundaries.py` y `test_compaction_boundaries.py` en verde); el proveedor entra por el puerto `Provider` y el almacén por el protocolo `CompactionStore`; `core/interfaces/`, `core/entities.py`, `core/events.py` y `core/loop.py` no tienen diff; los mensajes de error y de aviso son textos fijos (el centinela no aparece en eventos, avisos ni filas de `events`); la conexión se hace solo en `bootstrap.py` (`_compactor`); las pruebas del núcleo usan `FakeProvider` y un almacén en memoria, y SQLite solo en `tmp_path`; `test_compaction_archive.py` fija las garantías de `store_protocol.md`; lo público está exportado en `core/__init__.py`; la compactación falla cerrada (nada parcial, la cancelación se propaga). **Un «No» sigue en pie**: la revisión de otro integrante (H3).

Ajustes frente al diseño, hallados al implementar (ninguno cambia un puerto, un contrato ni un criterio):

- `ContextCompactor` recibe `session_id` por constructor: el diseño no decía de dónde sacaba el almacén el identificador de sesión.
- `summary.py` nació en T003 con el marco (`frame_summary`, `is_summary`, `summary_text`) porque `split_history` necesita reconocer el resumen anterior; T004 lo completó.
- El aviso llega a la terminal por `Composition.warning_sink` (un `WarningSink` que `run_session` apunta a su salida), porque el compactador se construye antes de que exista la salida de la sesión.
- Una prueba existente más cambia por el `skip` (`test_every_event_type_emitted_on_the_bus_is_saved`): el análisis solo había previsto la firma posicional.

## Project Structure

### Documentation (this feature)

```text
specs/030-automatic-context-compaction/
├── spec.md · plan.md · research.md (R1–R18) · data-model.md · quickstart.md
├── contracts/
│   ├── store_protocol.md       # protocolo del almacén, garantías del adaptador y ejemplos con seq
│   ├── compaction_events.md    # carga de context_compacted, provider_error y advertencia
│   ├── summary_prompt.md       # la llamada, el prompt, la transcripción y el resumen enmarcado
│   ├── context_order.md        # orden del contexto, corte seguro y ventana reciente
│   └── context_settings.md     # sección [context] y umbral por modelo
├── checklists/requirements.md
└── tasks.md                    # /speckit-tasks
```

### Source Code y fila de `estructura-carpetas-harness` que justifica cada ruta

| Ruta | Nuevo/Mod. | Fila |
|---|---|---|
| `src/harness_agent/core/context/settings.py`, `cut.py`, `summary.py`, `store.py`, `compactor.py` | Nuevo | Regla de negocio → subpaquete de `core/` (área B) |
| `src/harness_agent/core/context/errors.py`, `__init__.py`, `src/harness_agent/core/__init__.py` | Mod. (`SummaryRejected`, `CompactionError`; exportaciones) | Lo público se exporta en `core/__init__.py` |
| `src/harness_agent/adapters/storage/_schema.py` | Mod. (`_V3`, `SCHEMA_VERSION = 3`) | Código con `sqlite3` → `adapters/storage/` (área B) |
| `src/harness_agent/adapters/storage/compaction_archive.py` | Nuevo | Ídem |
| `src/harness_agent/adapters/storage/event_recorder.py`, `__init__.py` | Mod. (parámetro `skip`; exportación) | Ídem |
| `src/harness_agent/config.py` | Mod. (`[context]`, `HarnessConfig.context`) | Lectura de configuración → `config.py` (área B) |
| `config.example.toml` | Mod. (sección comentada) | Plantilla sin claves |
| `src/harness_agent/bootstrap.py` | Mod. mínima (cableado; `Composition.compactor`; `run_session`) | Raíz de composición (área C; visto bueno en H2) |
| `tests/unit/core/context/test_settings.py`, `test_cut.py`, `test_cut_properties.py`, `test_summary.py`, `test_compactor.py` | Nuevo | `tests/unit/core/context/` |
| `tests/unit/adapters/storage/test_schema_v3.py`, `test_compaction_archive.py`, `test_event_recorder_skip.py` | Nuevo | `tests/unit/adapters/storage/` |
| `tests/unit/adapters/storage/test_schema_migration.py` | Mod. **solo las aserciones de versión** (R6) | Ajuste declarado |
| `tests/unit/adapters/storage/test_schema.py` | Mod. **una aserción** (`SCHEMA_VERSION == 2` → 3, R6; hallada por el análisis) | Ajuste declarado |
| `tests/integration/test_rejection_reason_agent_loop.py` | Mod. **un conjunto de tablas** (gana `resumenes`, R6; hallada por el análisis) | Ajuste declarado |
| `tests/unit/adapters/storage/test_public_api.py` | Mod. (**solo el nombre nuevo**) | Ajuste declarado |
| `tests/unit/test_config_context.py` | Nuevo | `tests/unit/` (configuración) |
| `tests/unit/test_bootstrap_compaction.py` | Nuevo | `tests/unit/` (cableado) |
| `tests/integration/test_context_compaction_agent_loop.py` | Nuevo | `tests/integration/` (sesión larga, AC-01 y AC-02, fallos, no filtración) |
| `tests/architecture/test_compaction_boundaries.py` | Nuevo | Guarda `ast` de lo nuevo |

**Archivos protegidos** (diff vacío al cerrar): `core/loop.py`, `core/interfaces/`, `core/events.py`, `core/in_memory_event_bus.py`, `core/redaction.py`, `core/permissions/`, `core/tasks/`, `core/verification/`, `adapters/tools/`, `cli/`, `tests/doubles/`, `docs/archivo/`.

**Archivos de otra área que se tocan** (área C): solo `bootstrap.py`. La historia es de B y toca su propio esquema, su configuración y su paquete `core/context/`.

### Decisiones clave (detalle en `research.md`)

1. **R1**: el compactador corre en `run_session` antes de cada petición; el ensamblador no está cableado, así que se estima con las funciones puras (observación para A y HU-02-06.1).
2. **R2 y R3**: cabeza protegida (mensajes `SYSTEM` y petición inicial), resumen como `USER` externo, ventana reciente por presupuesto con mínimo y corte seguro.
3. **R4**: correspondencia mensajes ↔ eventos por orden y tipo (el asistente solo tiene evento si tiene contenido), con falla cerrada si no coinciden.
4. **R5**: un solo registro de `context_compacted`: el adaptador lo escribe en la transacción y el registrador lo omite (`skip`); la clave primaria lo hace infalible.
5. **R6**: esquema 3 aditivo; únicas pruebas existentes que cambian: las aserciones de versión de `test_schema_migration.py`.
6. **R7 y R8**: resumen limpio, sin credenciales de URL y enmarcado; llamada de texto plano sin herramientas.
7. **R9**: fallos sin nada parcial, `provider_error` fijo y advertencia por `warn`.
8. **R10**: `[context]` con rangos validados; **R11**: la vista en memoria se reemplaza, el original no se toca.

### Estimación de tareas (RITMO: 5 PHU → 9 de implementación de ≤ 40 min, TDD, más inicio y cierre)

| # | Tarea | Min | Sprint |
|---|---|---|---|
| T001 | Inicio: PROGRESO `En curso`, observaciones de inicio | 10 | — |
| T002 | `ContextSettings`, umbral por modelo y `[context]` en `config.py` y `config.example.toml` | 40 | Sp2-14 |
| T003 | `cut.py`: partición del historial, ventana reciente y corte seguro, con tablas y prueba al azar | 40 | Sp2-16 |
| T004 | `summary.py`: prompt, transcripción, limpieza, marco y reconocimiento del resumen | 30 | Sp2-15 |
| T005 | Esquema v3 y su migración desde 1 y 2 (bases reales) y los dos ajustes de pruebas | 30 | Sp2-17 |
| T006 | `SqliteCompactionArchive` (transacción única, idempotencia, rollback) y `skip` del registrador | 40 | Sp2-17 |
| T007 | `store.py` y `compactor.py`: el orquestador con colaboradores falsos (umbral, fallos, una vez por turno, advertencia) | 40 | Sp2-14, Sp2-15 |
| T008 | Cableado en `bootstrap.py` y `run_session` | 35 | Sp2-16 |
| T009 | Integración: sesión larga con `FakeProvider` y SQLite real (AC-01, AC-02, fallos, no filtración) | 40 | Sp2-16 |
| T010 | Guarda `ast`, skills (dos copias), `CLAUDE.md`, lista de comprobación y detector de secretos | 30 | — |
| T011 | Cierre: cuatro puertas, diff de protegidos, PROGRESO `En revisión` con observaciones | 30 | — |

Total de Claude: unos 365 min, frente a 720 min (12 h) presupuestados en Sp2-14 a Sp2-17. El presupuesto es un aviso, no un límite. Con 5 PHU se usa `/speckit-analyze` entre las tareas y la implementación.

### Tareas humanas (Claude no las marca)

- **H1**: **acuerdo de A, B y C** sobre la carga del evento `context_compacted` (`{desde, hasta, eventos}`) y, como mejora futura, sobre el gancho de compactación en `core/loop.py` antes de cada llamada al modelo (A).
- **H2**: **visto bueno de B** al esquema 3 y a `config.py`; **visto bueno de C** a `bootstrap.py`.
- **H3**: **revisión cruzada** por A o C (la historia es de B).
- **H4**: el **PO revisa** los valores por defecto (32 000, 80 %, 30 % con mínimo 4, unos 2 000 tokens), el tratamiento del resumen como contenido externo y que la llamada de resumen no cuente en los límites.
- **H5**: corrida de SPK-03 con un **modelo real** cuando D-IA lo permita (calidad del resumen; no bloquea).
- **H6**: **CI remota** en `ubuntu-latest` y `windows-latest`.
- **H7**: aviso a **A (HU-01-06)**: la llamada de resumen no cuenta en los límites; y a **A (HU-03-04)**: las marcas, `resumenes` y el esquema 3 son la base para reconstruir al reanudar.
- **H8**: aviso a **A y a B (HU-02-01, HU-02-06.1)**: el ensamblador sigue sin cablear; la estimación de esta historia es cruda y debería pasar a la calibrada cuando se integre.

## Complexity Tracking

| Desviación | Por qué | Alternativa descartada |
|---|---|---|
| Protocolo del almacén en `core/context/` en vez de ampliar `SessionStore`/`ContextManager` | Q2 = B: no cambiar `core/interfaces/` (R5, R6) | Ampliar los puertos con acuerdo de A, B y C |
| Parámetro `skip` en `attach_event_recorder` | Evita guardar dos veces `context_compacted` sin cambiar `SessionStore` (R5) | Que el registrador ignore `DuplicateEvent`; no publicar el evento |
| Resumen como `USER` externo y no como `SYSTEM` | `core/loop.py` solo admite `SYSTEM` como prefijo y el resumen no es de confianza (R2, R7) | `SYSTEM` tras la petición inicial (rechazado por el bucle) |
| Estimación cruda sin calibrar | El ensamblador no está cableado y cablearlo toca el bucle (R1) | Cablear el ensamblador |
| Correspondencia mensajes ↔ eventos por orden y tipo (el asistente sin contenido no tiene evento) | `Message` no lleva identificador de evento y `core/entities.py` no cambia (R4) | Añadir un identificador al mensaje |
| `test_schema_migration.py` cambia 4 aserciones de versión; `test_schema.py`, 1; y un conjunto de tablas de `test_rejection_reason_agent_loop.py` | La versión del esquema pasa de 2 a 3 (R6) | Dejar el esquema en 2 con `CREATE TABLE IF NOT EXISTS` (rompe la regla de migraciones por versión) |
