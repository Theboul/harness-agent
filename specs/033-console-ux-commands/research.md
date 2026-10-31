# Research — HU-06-05

Todas las decisiones se tomaron leyendo el código actual (`cli/`, `bootstrap.py`, `core/context/compactor.py`, `adapters/storage/sqlite_session_store.py`).

## R1 — Decisión de color

- **Decision**: `detect_style(stream, environ=None, platform=None) -> Style`. Color solo si: `stream.isatty()` es verdadero, `NO_COLOR` no está definida con valor no vacío, `TERM != "dumb"`, y en `win32` hay alguno de `WT_SESSION`, `ANSICON`, `ConEmuANSI=ON`, `TERM_PROGRAM`. Entorno y plataforma inyectables. `Style.paint(text, *names)` devuelve el texto tal cual si el estilo está apagado.
- **Rationale**: la consola clásica de Windows (cmd/PowerShell antiguos) no interpreta ANSI y mostraría `←[31m`; conservador = apagado salvo indicios. `NO_COLOR` es la convención de no-color.org.
- **Alternatives**: activar el modo VT con `ctypes`/`os.system("")` (efectos secundarios globales y difícil de probar); `colorama` (dependencia, prohibida).

## R2 — Forma del bloque de aprobación

- **Decision**: bloque ASCII de ancho fijo (reglas de 60 caracteres), una cosa por línea, orden fijo: título, frase, valor principal, «Herramienta», «Argumentos» (si hay más), «Riesgo», «Efecto», opciones. Valor principal = `command` si existe y es texto; si no, `path`; si no, ninguno. Frase por clave: `command` → «ejecutar un comando», `path` → «usar la ruta indicada con la herramienta X», otra → «usar la herramienta X». Saltos de línea del valor escritos como `\n`; tope 400 caracteres para el principal y 200 para el resto. Claves ocultas por nombre, igual que hoy.
- **Rationale**: el feedback fue que la jerarquía se perdía; el ancho fijo y el acotado por caracteres no dependen de la terminal. ASCII evita `?` por codificación.
- **Alternatives**: cajas Unicode (se degradan en cp437/cp1252); ajustar al ancho de la terminal (dependiente del entorno, difícil de probar).

## R3 — Duración de herramienta

- **Decision**: `ActivityRenderer` guarda `{call_id: (t_requested, approval_wait)}` con tope de 256 entradas (se descarta la más antigua). Al llegar `approval_requested` guarda `t_ask`; al llegar `approval_resolved` suma `t_resolved − t_ask` a la espera; en `tool_finished` la duración es `t_finished − t_requested − espera`, solo si ≥ 0. Formato: `< 1 s` → «N ms»; < 60 s → «1,2 s»; si no «2 min 5 s».
- **Rationale**: `Event.timestamp` ya viaja (UTC, inyectable por el reloj de la composición); no se inventa ningún campo. Restar la espera evita atribuir a la herramienta el tiempo que tardó la persona en leer.
- **Alternatives**: reloj propio del renderizador (rompe el determinismo de las pruebas y mide otra cosa); medir en el bucle (protegido).

## R4 — Comandos asíncronos

- **Decision**: el tipo de los comandos pasa a `Callable[..., str | Awaitable[str]]`; `run_cli` hace `await` si el resultado es *awaitable* (`inspect.isawaitable`). Los comandos existentes no cambian.
- **Rationale**: `/compactar` llama al proveedor (async); ejecutar `asyncio.run` dentro de un bucle activo falla. Cambio mínimo y compatible.
- **Alternatives**: comando síncrono con bucle propio (falla dentro de `asyncio.run`); hilo auxiliar (complejidad innecesaria).

## R5 — Sesiones de subagente

- **Decision**: en `bootstrap.py`, `store.list_sessions()` (puerto) y, por cada resumen, `store.get_session(id).parent_id is None` (el almacén concreto lo expone); se ordena de la más reciente a la más antigua y la CLI toma 10.
- **Rationale**: el puerto no trae `parent_id` y no se cambia; `get_session` es una consulta por clave, barata para decenas de sesiones.
- **Alternatives**: SQL directo en `bootstrap.py` (acopla a la tabla); ampliar `SessionSummary` (contrato).

## R6 — `/nueva`

- **Decision**: `store.create_session(model=composition.model)` → historial = copia del prefijo → `capture.bind(nueva, history, last_position+1, len(history))` → `active.session_id`, `active.compactor = factory(nueva)`, `active.closures.clear()`. Con tarea (`composition.runner is not None`) o sin captura/almacén/fábrica: mensaje fijo «no disponible».
- **Rationale**: es exactamente la mitad de `/reanudar` sin leer; reutiliza sus piezas. Los límites viven en el bucle (núcleo) y no se reinician (A5, igual que `/reanudar`).
- **Alternatives**: reiniciar el proceso (pierde el estado de la ejecución); reiniciar límites (cambio en `core/loop.py`).

## R7 — `/compactar` forzado

- **Decision**: segunda fábrica `manual_compactor_for(session)` que reutiliza `_compactor` con `dataclasses.replace(config.context, window_tokens=1000, windows=(), threshold_percent=10)` (umbral 100 tokens: siempre superado, porque las declaraciones de herramientas solas lo exceden) y `warn` silenciado. Se conservan `recent_percent`, `min_recent_messages` y `summary_tokens` del usuario. El resultado `CompactionResult` aporta `estimated_before/after`.
- **Rationale**: misma clase y mismo archivo (`SqliteCompactionArchive`) que la automática (HU-02-04 regla 1); el núcleo no se toca. Con el umbral mínimo, los recientes protegidos son los `min_recent_messages` (4 por defecto).
- **Alternatives**: añadir `force` al compactador (mejor diseño, requiere a B; hallazgo); copiar la lógica (duplica reglas).
- **Limitación**: `None` significa «nada que resumir» **o** «falló»; el fallo ya publicó un `provider_error` fijo que la vista de actividad muestra, y el comando responde con un mensaje que cubre ambos casos.

## R8 — `/model`

- **Decision**: `Composition.model_view: ModelView` (modelo, ventana, umbral, `max_turns`, `max_seconds`, `max_tokens`, `max_output_tokens`) construido en `compose()` desde `config`; `format_model` lo imprime. Nunca se lee `config.api_key`.
- **Rationale**: solo muestra; los datos ya están en la configuración validada.
- **Alternatives**: leer la configuración dentro de la CLI (la CLI no importa `config`).

## R9 — Qué cambia en las pruebas existentes

- Formatos de línea (`... ejecutando:`, `v x: correcto`, `x Error:`, `> texto`) cambian: se actualizan las pruebas de `tests/unit/cli/test_render_*.py`, `test_app_output.py` y las de integración que comparan texto de la CLI. Se ejecutan antes para fijar la lista exacta (tarea T001).
- `SHOWN_TYPES` gana `APPROVAL_RESOLVED` y `CONTEXT_COMPACTED`.
- `HELP_TEXT` cambia de forma (alineado); sus pruebas se actualizan.
