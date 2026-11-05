# Especificación: HU-00-05.1 — Pruebas de integración y de fallos del núcleo, con medición del tiempo propio del harness

**Rama**: `gustavo` (sin PR) · **Responsable**: A — Núcleo · **Sprint**: 3 en `PROGRESO.md` (historia arrastrada; HU-00-05.2 ya la da por hecha como dependencia) · **PHU**: 2  
**Requisitos**: RNF-1, RNF-5, RNF-6, RNF-7 · **Depende de**: [HU-03-02](../../docs/04b-historias-estado.md#hu-03-02), [HU-07-05](../../docs/04d-historias-conexiones.md#hu-07-05) · **Ficha**: [HU-00-05.1](../../docs/04a-historias-fundacion.md#hu-00-05.1)  
**Tareas del plan de sprints**: Sp3-09 (2,5 h), Sp3-10 (3 h), Sp3-11 (1,5 h)  
**Modo**: rápido (solo `spec.md`, `plan.md` y `tasks.md`; sin `/speckit-clarify` ni `/speckit-analyze`; las dudas pequeñas se deciden en «Decisiones»).

## Naturaleza de la historia

**Solo pruebas. No se cambia ningún archivo de `src/`.** El núcleo ya tiene piezas de resistencia a fallos (HU-03-02 almacén durable, HU-03-04 reanudar, HU-07-04 reintentos, HU-07-05 conmutación, HU-01-01 errores de herramienta) y muchas pruebas, pero casi todas por componentes y con dobles. Esta historia no repite lo cubierto: primero **inventaría** qué cubre cada AC de verdad y añade pruebas **solo donde la cobertura real no llega**: un proceso real que muere por fuerza y se reanuda en otro, el fallo del proveedor a mitad de un turno con herramientas, la herramienta que lanza con la composición real y la medición del tiempo propio del harness. Si al implementar apareciera un defecto real en `src/`, se detiene y se anota como hallazgo (no se arregla aquí).

## Criterios de aceptación y reglas de la ficha (literales)

**Flujo general**

1. Se simula un cierre forzado a mitad de sesión y se reanuda.
2. Se simula un proveedor caído con error elegible y se verifica la conmutación.
3. Se simula una herramienta con excepción.
4. Se mide el tiempo propio del harness por turno con proveedor simulado.

**Reglas de negocio**

1. Las pruebas de fallos corren en la integración continua.
2. El tiempo del harness se mide sin contar la latencia del modelo.

**Criterios de aceptación**

- **AC-01 — Sin pérdida de eventos tras cierre forzado.** Dado un cierre forzado del proceso a mitad de sesión, cuando se reanuda, entonces no se pierde ningún evento confirmado.
- **AC-02 — Proveedor caído y herramienta defectuosa.** Dado un proveedor principal caído con un error elegible, cuando corre el turno, entonces el sistema conmuta al de respaldo y el turno termina; dado una herramienta que lanza una excepción, entonces el modelo recibe un error y el bucle continúa.
- **AC-03 — Tiempo propio del harness medido.** Dado un turno con proveedor simulado y herramientas instantáneas, cuando se mide, entonces el tiempo propio del harness es pequeño y queda registrado.

## Inventario de la cobertura existente

Leyenda: **Cubre** = lo que la prueba demuestra de verdad; **No cubre** = lo que queda fuera de ella. Las pruebas citadas se ejecutan sin tocar en la línea base (T001), cuyas cifras se anotan en `PROGRESO.md`.

| Paso / AC | Pruebas que ya existen | Cubre | No cubre (hueco) |
|---|---|---|---|
| Paso 1 · AC-01 (cierre forzado) | `tests/integration/test_session_store_abrupt_close.py` (HU-03-02: 20 repeticiones × 3 escenarios; durabilidad `PRAGMA synchronous`) | Un hijo escribe con `SqliteSessionStore` y termina con `os._exit(0)` (antes del COMMIT o tras el INSERT): los eventos confirmados siguen, el corte no deja base corrupta, `integrity_check` ok, el siguiente `seq` continúa | El proceso no es el sistema: sin `compose`, bucle ni `run_session`; sin mensajes; la salida es **voluntaria** (`os._exit`), no `kill` desde fuera (SIGKILL / `TerminateProcess`); sin reanudación |
| Paso 1 · AC-01 (reanudar) | `test_resume_agent_loop.py`, `test_resume_cuts.py`, `test_resume_errors.py`, `test_resume_security.py` (HU-03-04); unitarias de `core/context/resume` y `message_store` | Reconstrucción del historial mensaje a mensaje con el bucle y un archivo real; cierre de llamadas sin resultado (`[tool_interrupted]`); errores de `/reanudar`; seguridad | Todo ocurre en **el mismo proceso** (el «cierre» es cerrar la composición o una `CancelledError`); nunca un proceso muerto de verdad ni uno nuevo que abra la base |
| Paso 2 · AC-02 (proveedor caído) | `tests/integration/test_failover_agent_loop.py` (HU-07-05: 16 pruebas), `test_retry_flow.py` (HU-07-04), `tests/unit/adapters/providers/test_failover_provider.py`, `tests/unit/core/test_failover.py` | Con `compose()`, bucle, reintentos y SQLite real: cuota, límite de tasa, tiempo agotado y servicio no disponible conmutan, repiten la misma llamada, dejan `PROVIDER_SWITCHED` en la sesión y el aviso; error de conexión de LiteLLM; no elegibles; lista agotada; compactación; subagente | El fallo siempre llega en la **primera** llamada del turno. No se prueba el fallo **después** de que una herramienta se ejecutó (la repetición debe llevar el resultado de la herramienta y el turno debe terminar) |
| Paso 3 · AC-02 (herramienta con excepción) | `tests/core/test_loop_tool_errors.py` (11 pruebas: `ac02_…`, `[tool_exception]`, acotado, valor inválido, varias llamadas), `tests/core/test_loop_failures.py` (cancelación en proveedor y herramienta, R-08, no se traga la cancelación) | El bucle convierte la excepción en `ToolResult` de error con etiqueta y sigue; `CancelledError` se propaga y deja un solo `INTERRUPTED`; no inventa resultados | Todo con `make_rig` y dobles: nunca con la **composición real** (registro envuelto por trazas y recorte, auditoría, eventos y mensajes en SQLite). Ninguna prueba cubre una `BaseException` que no sea cancelación |
| Paso 3 · herramienta colgada | `tests/core/test_loop_limits.py`, `tests/integration/test_limits_agent_loop.py` (reloj inyectado), `tests/core/test_loop_failures.py` (cancelación mientras bloquea), `tests/integration/test_shell_agent_loop.py` (cancelar termina el comando), `test_resume_cuts.py` (la cancelación real deja una sesión reanudable) | El límite de tiempo se aplica **entre** llamadas al modelo; la cancelación externa interrumpe una herramienta que bloquea y el cierre queda registrado | El bucle **no** tiene tope por herramienta (hallazgo F-02): una herramienta que no vuelve solo la detiene una cancelación externa o su propio tope (p. ej. el del shell). No se puede probar «hasta el límite de tiempo» porque ese límite no la interrumpe |
| Paso 4 · AC-03 (tiempo propio) | `tests/integration/test_fake_provider_agent_loop.py::test_the_whole_failing_turn_is_quick_and_uses_no_network` (`< 0.5 s`, un turno de error); `test_resume_agent_loop.py` (5 000 mensajes se reconstruyen «en segundos») | Que un turno de error con `FakeProvider` es rápido y sin red | **Ninguna medición**: ni por turno completo, ni con la composición real, ni descontando la latencia del modelo, ni se registra una cifra |
| Regla 1 (la CI) | `.github/workflows/ci.yml` corre `pytest` completo en Ubuntu y Windows | Toda prueba nueva sin marca ni excepción corre sola | Las pruebas de proceso real y de tiempo deben ser estables en ambos sistemas (ver «Decisiones») |

**Conclusión del inventario.** AC-02 (proveedor) está cubierto casi por completo: se añade solo el fallo a mitad de turno. AC-02 (herramienta) está cubierto por componentes: se añade la verificación con la composición real y la caracterización de la `BaseException`. AC-01 y AC-03 tienen huecos reales y son el grueso del trabajo.

## Escenarios y pruebas nuevas

### AC-01 — Proceso real matado y reanudado en otro (`tests/integration/test_core_abrupt_kill_resume.py`, ayudante `tests/integration/core_kill_child.py`)

1. **Proveedor en vuelo.** Un proceso hijo ejecuta `compose()` + `run_session` con un proveedor guionado que, en la 3.ª petición, escribe una línea de control y se bloquea. El padre la lee, lo mata con `Popen.kill()` y comprueba que **los eventos que el hijo vio confirmados son exactamente los que hay en el archivo**, que `PRAGMA integrity_check` da `ok` y que otro proceso, con `/reanudar <id>`, reconstruye la sesión, la acepta y deja eventos nuevos con `seq` continuo.
2. **Herramienta en vuelo.** Igual, pero el bloqueo está dentro de una herramienta: la sesión queda con una llamada sin resultado; al reanudar, el cierre `[tool_interrupted]` aparece y el aviso lo dice.
3. **Proceso que sigue escribiendo.** El hijo no se bloquea; el padre lo mata en cuanto ve la línea de control (que lista los eventos ya confirmados), mientras el hijo sigue escribiendo. Los eventos confirmados son un **prefijo** de los guardados, la base no está corrupta y la sesión se reanuda (5 repeticiones).

### AC-02 — Fallos con el sistema compuesto (`tests/integration/test_core_failure_modes.py`)

4. **Proveedor caído a mitad de turno** (cuota, límite de tasa, tiempo agotado, servicio no disponible): el modelo pide una herramienta, ésta se ejecuta, la segunda llamada falla con el error elegible; conmuta, el fallback recibe el historial **con** el resultado de la herramienta, el turno termina `COMPLETED` y `PROVIDER_SWITCHED` queda en la sesión guardada.
5. **Herramienta que lanza con la composición real:** el modelo recibe `[tool_exception]` (acotado, sin traza), el bucle sigue y termina el turno; en el archivo quedan `tool_finished` con error, la fila de auditoría `permitida` y la traza con el resultado `RuntimeError` (la clase que lanzó la herramienta: la traza guarda la clase, no la etiqueta del resultado); el valor centinela de la excepción no aparece en la base.
6. **`BaseException` que no es cancelación** (clase propia, no `KeyboardInterrupt`): se **propaga** sin convertirse (caracterización del diseño actual) y no se inventa un resultado de herramienta.

### AC-03 — Tiempo propio del harness (`tests/integration/test_harness_own_time.py`)

7. **Medición.** Con `compose()` (política, registro, bus, almacén SQLite real, captura de mensajes, auditoría y trazas activos) y `FakeProvider` de latencia cero, 200 turnos (más 10 de calentamiento descartados) de dos llamadas al modelo y una herramienta instantánea. Se mide con `time.perf_counter`, se descuenta el tiempo dentro del proveedor, se reportan mediana y p95 y la prueba falla si la mediana supera el umbral (ver «Decisiones», D-10).
8. **El método excluye la latencia del modelo.** Un proveedor que espera 50 ms por llamada no cambia el tiempo propio medido (se resta) y el tiempo total sí lo refleja.

## Requisitos funcionales

- **FR-001**: Una prueba MUST matar con `Popen.kill()` un **proceso real** que ejecuta `compose()` + `run_session` sobre un SQLite de `tmp_path` y reanudar su sesión en **otro proceso** con `/reanudar` (AC-01).
- **FR-002**: Tras el corte, todo evento que el proceso observó confirmado MUST estar en el archivo (igualdad exacta con el proveedor bloqueado; prefijo cuando el proceso sigue escribiendo) y `PRAGMA integrity_check` MUST dar `ok` (AC-01).
- **FR-003**: La sincronización con el hijo MUST ser por una línea de un pipe y nunca por `sleep` fijo; toda espera MUST tener tope y el hijo MUST terminarse en `finally` (sin procesos huérfanos).
- **FR-004**: Un fallo elegible del proveedor tras la ejecución de una herramienta MUST conmutar, repetir la llamada con el resultado de la herramienta, terminar el turno y dejar `PROVIDER_SWITCHED` guardado (AC-02).
- **FR-005**: Una herramienta que lanza una excepción, con la composición real, MUST llegar al modelo como error acotado sin traza, el bucle MUST continuar y el rastro MUST quedar en eventos, auditoría y trazas sin reproducir el texto de la excepción fuera del contenido acotado del resultado (AC-02).
- **FR-006**: La cancelación MUST seguir propagándose (cubierto por pruebas existentes, que se citan, no se repiten) y una `BaseException` ajena a la cancelación MUST propagarse sin convertirse en resultado (AC-02).
- **FR-007**: El tiempo propio por turno MUST medirse con `time.perf_counter`, descontando el tiempo dentro del proveedor, verificando que la latencia simulada del modelo es despreciable, y MUST reportar mediana, p95 y máximo (AC-03, regla 2).
- **FR-008**: La prueba de tiempo MUST fallar si la mediana supera el umbral documentado y MUST registrar el resultado por `record_property`, una línea impresa y, si la variable `HARNESS_TIMING_REPORT` apunta a una ruta, un JSON; MUST NOT escribir en el repositorio (AC-03).
- **FR-009**: Todas las pruebas MUST correr en la CI actual (Ubuntu y Windows) sin dependencias nuevas, sin red, claves ni proveedor real, y sin marcador nuevo.
- **FR-010**: La historia MUST NOT cambiar `src/`, `pyproject.toml`, `.github/workflows/ci.yml`, `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py`, `core/verification/`, `tests/doubles/`, `docs/archivo/`.

## Criterios de éxito

- **SC-001**: Cada AC (AC-01, AC-02, AC-03) tiene al menos una prueba nombrada con su ID y la tabla FR/AC → tarea → prueba del plan está completa.
- **SC-002**: Matado el proceso 5 veces en el escenario ocupado, 0 eventos confirmados se pierden y 0 bases quedan corruptas.
- **SC-003**: La mediana del tiempo propio por turno es menor que el umbral documentado (250 ms; medido en local: ≈ 20 ms) y la cifra queda registrada en `PROGRESO.md`.
- **SC-004**: Cada prueba nueva falla si se rompe lo que protege: ≥ 8 mutaciones manuales en una copia temporal de `src/` detectadas, y el árbol `src/` real queda idéntico (`git diff -- src` vacío).
- **SC-005**: Las cuatro puertas de calidad y `pytest tests/architecture` en exit 0; la cobertura no baja del 99 % (no hay código de producción nuevo).

## Decisiones (modo rápido, sin clarify)

- **D-01** Sin cambios en `src/`, `pyproject.toml` ni `ci.yml`. Si algo exigiera tocar un puerto, `core/loop.py`, el catálogo de eventos, `redaction.py` o `verification/`, se detiene la implementación y se pregunta.
- **D-02** El corte es `Popen.kill()` (SIGKILL en Linux, `TerminateProcess` en Windows), no `os._exit`: así se prueba una muerte que el proceso no controla. `test_session_store_abrupt_close.py` se queda como está (cubre cortes **dentro** de una escritura, que `kill()` no puede apuntar con precisión).
- **D-03** El hijo es un **ayudante** `tests/integration/core_kill_child.py` (no empieza por `test_`, como `mcp_env_probe_server.py`), con modos `block-provider`, `block-tool`, `busy` y `resume`. Se ejecuta con `sys.executable` y `PYTHONPATH` = la carpeta `src` del paquete importado (como `test_session_store_abrupt_close.py`, así sirve también en una copia de mutación).
- **D-04** Sincronización: el hijo escribe en stdout (con `flush`) una línea `CHECKPOINT <json>` con los ids de evento **confirmados**, leídos con una conexión `sqlite3` **aparte** (solo ve lo que tiene COMMIT); el padre lee con un hilo y una cola con tope de 60 s. El resto de la salida del hijo va a `io.StringIO`, no a stdout.
- **D-05** Igualdad exacta solo cuando el hijo está bloqueado (no hay escritura en vuelo); con el hijo ocupado la garantía es de **prefijo**: lo anunciado como confirmado está, en orden, al principio de lo guardado.
- **D-06** «Reanudar en otro proceso»: segundo hijo (modo `resume`) con `compose()` nuevo que ejecuta `run_session` con `/reanudar <id>` y una petición más; el padre comprueba el texto de reanudación, que no hay huecos ni duplicados de `seq` y que la petición nueva quedó en la sesión reanudada. No se llama a `resume_session` desde el padre (se probaría la función, no el camino real).
- **D-07** AC-02 (proveedor): los cuatro errores y la composición completa **ya están** probados; se añade solo el caso a mitad de turno (parametrizado con los mismos cuatro errores). No se duplica nada de `test_failover_agent_loop.py`; se reutiliza su patrón (`World`, `make`, `run`) copiándolo en pequeño, sin importar de otra prueba para no acoplarlas.
- **D-08** Herramienta con excepción: la herramienta se registra en `composition.registry` (riesgo bajo, argumento `path` dentro del área: la política la deja pasar sin aprobación), para que la prueba use la cadena real de políticas, el registro envuelto y la auditoría.
- **D-09** `BaseException`: se prueba como **caracterización** (hoy se propaga como la cancelación, sin `INTERRUPTED` y sin resultado inventado), con una subclase local `Fatal(BaseException)`; no se usa `KeyboardInterrupt` ni `SystemExit` para no interferir con pytest. No se afirma que deba ser así: ver F-01.
- **D-10** AC-03: una medición = un `run_turn` (2 llamadas al modelo, 1 herramienta). 200 turnos tras 10 de calentamiento. Historial nuevo por turno (el prefijo) en la **misma sesión**, para que el tiempo no crezca con la copia profunda de `FakeProvider` (medido: con el historial acumulado la mediana era de ≈ 50 ms sin descontar, porque el doble copia el historial entero en cada llamada y ese tiempo es del modelo, no del harness). **Umbral: mediana ≤ 250 ms.** Medido en local (Windows 11, disco SSD, SQLite con `synchronous=FULL`, 2 corridas de 200 turnos): mediana 20,1–20,4 ms, p95 ≈ 22 ms, máximo ≤ 137 ms; tiempo dentro del proveedor 49 ms en 400 llamadas (0,12 ms por llamada). El umbral deja ≈ 12× de margen para un disco lento de CI (cada turno hace varios COMMIT con `fsync`) y sigue diciendo algo útil: el harness añade menos de un cuarto de segundo por turno frente a llamadas de modelo de segundos. El **p95 solo se reporta** (los picos de `fsync` en una CI lenta lo harían frágil). Si la CI remota (H02) mostrara una mediana cercana al umbral, se revisa con 3 corridas antes de subirlo.
- **D-11** «Latencia del modelo verificada como cero»: el envoltorio mide el tiempo dentro de `complete()`; la prueba exige que sea < 5 ms por llamada de media (≈ 40× lo medido) y resta ese tiempo del turno.
- **D-12** Registro del resultado: `record_property` (queda en el XML de JUnit si algún día se pide), una línea impresa con `capsys.disabled()` (visible en el log de la CI sin `-s`) y, si el entorno define `HARNESS_TIMING_REPORT`, un JSON en esa ruta (que una CI futura puede subir como artefacto). Sin esa variable no se escribe ningún archivo. Subir el artefacto exige cambiar `ci.yml`: **no se hace aquí** (tarea humana H04).
- **D-13** Marcador: el único que existe es `install` (no sirve). No se crea otro: las pruebas son rápidas (las de proceso real ≈ 2–4 s cada una; la de tiempo ≈ 10 s). `pyproject.toml` no cambia.
- **D-14** No se usa `pytest-timeout` (no está instalado). Las esperas del padre llevan tope propio y el hijo se mata en `finally`.
- **D-15** La historia pertenece a Sprint 3 en `PROGRESO.md`; se implementa ahora porque HU-00-05.2 y el cierre de sprints la necesitan. No adelanta nada de sprints futuros (no hay código de producción).

- **D-16** (observado al implementar) Un mensaje del asistente sin texto (solo una llamada a herramienta) no tiene evento `assistant_message`; la secuencia guardada de un turno con herramienta y conmutación es `user_message, tool_requested, permission_decided, tool_finished, provider_switched, assistant_message`. La traza de una herramienta que lanza guarda la clase de la excepción (`RuntimeError`), no `tool_exception`. Las pruebas fijan lo observado, no lo supuesto en el diseño.

## Hallazgos (propuestas para decidir; NO se arreglan aquí)

- **F-01 — Una `BaseException` ajena a la cancelación no deja `INTERRUPTED`.** `core/loop.py` solo captura `CancelledError` para publicar `INTERRUPTED`; si una herramienta lanza otra `BaseException`, se propaga sin evento de interrupción y el historial queda con una llamada sin resultado (la reanudación la cierra igualmente con `[tool_interrupted]`). Es coherente con Python (`KeyboardInterrupt`/`SystemExit` deben terminar el proceso), por eso la prueba solo lo caracteriza. **Propuesta mínima** (si A la quiere): en `_run_turn`, tratar cualquier `BaseException` como la cancelación (publicar `INTERRUPTED` y relanzar). Toca `core/loop.py` (protegido, dueño A): requiere acuerdo.
- **F-02 — No hay tope de tiempo por herramienta en el bucle.** `max_seconds` se comprueba antes de cada llamada al modelo; una herramienta que no vuelve bloquea el turno hasta una cancelación externa (el shell tiene su propio `timeout_seconds`; las herramientas MCP, `call_timeout_s`). Una herramienta nativa propia que se cuelga no tiene red. **Propuesta mínima:** `asyncio.wait_for` alrededor de `tool.run` en `_execute` con un tope `limits.max_tool_seconds` (config y bucle). Toca `core/loop.py` y `config.py`: requiere acuerdo de A y del PO; no se implementa.
- **F-03 (informativo) — La CI no conserva los resultados de tiempo.** `ci.yml` no sube artefactos ni XML; el registro queda en el log y en `PROGRESO.md`.

## Alcance excluido

Servidores MCP caídos (HU-00-05.2, ya hecha); pruebas con proveedor real o red; carga o concurrencia entre procesos sobre la misma sesión (no soportado, ver HU-03-04); corte del **sistema operativo** (pérdida de energía): `kill()` prueba la muerte del proceso, no la caché del disco; cambiar `PRAGMA synchronous`.

## Supuestos

- `kill()` de un proceso Python con SQLite en modo de diario por defecto es seguro: lo confirmado con COMMIT está en el archivo o en su diario recuperable al reabrir (la reapertura lo recupera).
- `compose()` con un proveedor inyectado y `run_session` con entrada de texto es el camino real del arnés sin red (patrón de `test_resume_agent_loop.py`).
- El tiempo de arranque de un intérprete hijo (≈ 1 s con las importaciones) cabe holgado en el tope de 60 s por escenario.
