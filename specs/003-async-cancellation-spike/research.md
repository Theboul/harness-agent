# Technical Research: SPK-02 — Modelo Asíncrono y Cancelación de Herramientas

**Feature**: `specs/003-async-cancellation-spike/spec.md`  
**Date**: 2026-10-17  
**Author**: Integrante A — Núcleo  
**Status**: Actualizado tras la auditoría técnica del 2026-10-17 · Decisión D-01 pendiente de aprobación  

---

## 1. Contexto y Objetivos del Experimento

El objetivo de este spike es responder de forma empírica y fundada a la pregunta abierta «¿Se confirma asyncio como modelo de concurrencia?» (`docs/01-vision-y-decisiones.md`, tabla «Preguntas abiertas»), mediante la tarea **Sp1-49** (V-14 es la decisión del FakeProvider y no está relacionada):
1. ¿Debe el núcleo de HARNESS adoptar formalmente `asyncio` como modelo de concurrencia para operaciones de E/S?
2. ¿Cómo debe implementarse la cancelación limpia de herramientas de larga duración (como comandos de subproceso) garantizando que el bucle de ejecución recupere el control inmediato y no queden procesos huérfanos?

---

## 2. Hipótesis Experimentales

- **H1 (Recuperación de control del bucle)**: `asyncio.create_task` combinado con `asyncio.wait_for` o `task.cancel()` permite que el bucle capture `asyncio.CancelledError` o `TimeoutError` en < 500 ms y retome la ejecución secuencial de inmediato.
- **H2 (Terminación de subprocesos aislados)**: Iniciar un subproceso mediante `asyncio.create_subprocess_exec(sys.executable, ...)` y aplicar un protocolo de parada (`proc.terminate()` $\rightarrow$ tiempo de gracia 150 ms $\rightarrow$ `proc.kill()` $\rightarrow$ `await proc.wait()`) garantiza que el subproceso directo finaliza con código de salida no nulo. **Resultado**: confirmada en Windows (código 1); Linux pendiente de la CI.
- **H3 (Límites de terminación de árboles de procesos)**: La cancelación de un proceso directo mediante `proc.terminate()` o `proc.kill()` **NO** garantiza automáticamente la destrucción de procesos nietos o árboles de procesos creados por scripts complejos, salvo que se utilicen *Process Groups* (`setpgid` en POSIX) o *Job Objects* en Windows. Esta limitación debe documentarse explícitamente para las historias de Shell de Sprint 2 (HU-01-04).
- **H4 (Asincronía selectiva vs. concurrencia universal)**: Declarar contratos `async` para operaciones con E/S de red o interacción humana (`Provider.complete`, `Tool.run`, `Approver.request`, `McpClient`, `SubagentRunner.execute`) mientras los componentes puramente locales (`SessionStore` con SQLite) se mantienen síncronos, ofrece la mayor simplicidad, evita la sobrecarga de locking y previene condiciones de carrera.

---

## 3. Comparación verificable de alternativas (US2 / FR-007)

Alternativas evaluadas: **A** corrutinas `asyncio` con `create_subprocess_exec`; **B** hilos (`threading`, `asyncio.to_thread`), en dos variantes: B1 trabajo Python bloqueante dentro del hilo y B2 un hilo dueño de un `Popen`; **C** procesos (`multiprocessing`, método `spawn`).

Los experimentos viven en `tests/spikes/test_concurrency_alternatives_spike.py` (4 pruebas) y miden solo las propiedades comparadas. Números reales de 5 ejecuciones (mínimo / mediana / máximo): la tabla siguiente es de **Windows 10, CPython 3.12.10**, y las mediciones equivalentes de **WSL2 Ubuntu local** están justo después; no son benchmarks de rendimiento. Para reproducirlos: `python -m tests.spikes.test_concurrency_alternatives_spike`.

| Propiedad | A. asyncio + subproceso | B1. Hilo con trabajo Python | B2. Hilo dueño de `Popen` | C. `multiprocessing` (spawn) |
|---|---|---|---|---|
| Espera no bloqueante | Sí: ticks de 10 ms en 150 ms = 9 / 9 / 10 | Sí (el bucle sigue libre) | Sí: ticks = 15 / 15 / 15 en el hilo llamador | Sí: ticks = 14 / 14 / 15 |
| Regreso del control tras cancelar | 1.6 / 1.7 / 3.3 ms hasta que el proceso salió | 158 / 165 / 166 ms (el `await` se rinde al vencer el timeout de 150 ms) | 1.3 / 1.3 / 1.6 ms | 2.1 / 2.1 / 2.5 ms |
| La operación realmente se detiene | Sí | **No**: el hilo siguió corriendo; terminó solo 835 / 843 / 844 ms después de la cancelación | Sí, si se tiene el `Popen` y se llama a `terminate()` desde otro hilo | Sí, `terminate()` |
| Código de salida observado | 1 (`TerminateProcess` en Windows) | n/a | 1 | -15 (normalizado por `multiprocessing`) |
| PID vivo después | No | n/a | No | No |
| Limpieza de recursos | Tarea de limpieza propia; el conteo de handles del proceso se mantuvo estable en 5 ciclos (V22) | El hilo debe terminar por sí mismo; el `join` no es forzable | Hay que hacer `join` del hilo y gestionar manualmente las tuberías | `join()` y `close()` manuales |
| Integración con E/S asíncrona (red, stdio, MCP) | Nativa: misma primitiva (`await`) para todo | Requiere puentes (`to_thread`, `run_in_executor`) | Requiere puentes | Requiere IPC (colas, tuberías) |
| Windows y Linux | Windows y WSL2 Ubuntu local ejecutados; `terminate` en Windows ya es `TerminateProcess` y en Linux es `SIGTERM` | Igual en ambos (limitación del lenguaje) | Windows y WSL2 ejecutados | Windows y WSL2 ejecutados con el método `spawn` explícito (el valor por defecto de Linux, `fork`, no se probó) |
| Complejidad | Moderada: disciplina de no bloquear el bucle y de proteger la limpieza (V15-V17) | Alta: sin cancelación cooperativa no hay forma limpia de parar | Alta: coordinación de hilos, tuberías y señales a mano | Alta para herramientas pequeñas; adecuada para aislamiento fuerte |

Lectura de la evidencia:
- Las tres opciones pueden **esperar sin bloquear al llamador** y las que poseen un proceso lo terminan en milisegundos. La diferencia no está en la velocidad, sino en **qué se puede cancelar**: un hilo con trabajo Python (B1) no se puede detener (835 a 844 ms de trabajo residual en el experimento), mientras que una corrutina o un subproceso sí.
- Con B2 y C se logra terminar el subproceso, pero cada uno exige coordinar hilos o IPC a mano y no ofrece una primitiva de cancelación común con el resto del bucle (red, aprobación humana).
- `asyncio` es la única opción de las tres donde la espera, el *timeout* y la cancelación comparten el mismo mecanismo (`Task.cancel`, `wait_for`). Eso es lo que respalda la propuesta, no una ventaja de velocidad.
- Lo que el experimento **no** demuestra: el comportamiento del SDK de MCP, el streaming de proveedores y el rendimiento de SQLite. Son supuestos (D-01 §5).
- El tiempo de arranque (`spawn_ms`) solo mide el retorno de la llamada de creación (2.0 / 2.2 / 5.6 ms asyncio; 1.9 / 2.5 / 3.4 ms hilo con `Popen`; 1.3 / 1.3 / 7.6 ms `multiprocessing`) y no incluye el arranque del intérprete hijo, así que no sirve para comparar costes de arranque.
- Los ticks de A (9 en 150 ms en Windows) son menos que los de B2 y C (14 a 15) sin que se haya investigado la causa (posible efecto de la resolución del temporizador de Windows); en todos los casos el llamador siguió ejecutándose y no quedó bloqueado.

**Mediciones equivalentes en WSL2 Ubuntu 26.04.1 local** (CPython 3.12.15, kernel 6.18.54.1-microsoft-standard-WSL2; 5 ejecuciones, mín / mediana / máx; **no es un runner de GitHub Actions**; salida de `python -m tests.spikes.test_concurrency_alternatives_spike`):

| Propiedad | A. asyncio + subproceso | B1. Hilo con trabajo Python | B2. Hilo dueño de `Popen` | C. `multiprocessing` (spawn) |
|---|---|---|---|---|
| Control tras cancelar / salida del proceso | 0.6 / 0.9 / 2.2 ms | 150.6 / 150.7 / 150.9 ms (el `await` se rinde al vencer el timeout de 150 ms) | 0.8 / 1.2 / 1.2 ms | 0.9 / 1.1 / 1.6 ms |
| La operación realmente se detiene | Sí | **No**: el hilo siguió 849.8 / 849.9 / 854.8 ms más | Sí, con acceso al `Popen` | Sí |
| Código de salida | -15 (`SIGTERM`) | n/a | -15 | -15 |
| PID vivo después | No | n/a | No (hilo unido) | No |

La conclusión es la misma que en Windows: la diferencia está en qué se puede cancelar, no en la velocidad. En Linux los ticks mientras se espera fueron 14 (A) y 15 (B2 y C), así que la diferencia de ticks observada en Windows no se reprodujo.

### Escalamiento `SIGTERM` → `SIGKILL` en Linux (T016)

`tests/spikes/test_linux_sigterm_spike.py` usa un hijo Python real que instala `SIG_IGN` para `SIGTERM`, escribe un archivo de preparación y duerme (solo se ejecuta en Linux). Resultados reales en WSL2 Ubuntu local, con gracia de 150 ms salvo indicación:

| Prueba | Resultado |
|---|---|
| Control (`terminate()` sin `kill()`) | El proceso seguía vivo a los 0.5 s; con `kill()` terminó con código -9 |
| Cancelación con hijo que ignora `SIGTERM` | Código -9; control de vuelta a los 151.6 ms; PID ausente |
| Tres cancelaciones durante una gracia de 300 ms | 2 solicitudes extra absorbidas; código -9; control de vuelta a los 303.0 ms |
| Timeout de 0.4 s | Estado `TIMEOUT`; código -9; total 553.4 ms |
| 5 ciclos seguidos | Códigos `[-9, -9, -9, -9, -9]`; control de vuelta entre 151.2 y 152.2 ms; ningún PID vivo, zombi o listado como hijo |

Cancelar un hijo cooperativo (`time.sleep`, n=10, sondeo de diagnóstico) devolvió el control en 0.7 / 1.0 / 1.4 ms con código -15 en las 10 ocasiones. La suite completa pasó en WSL2 (40 pruebas, 0 omitidas) y en 5 ejecuciones consecutivas de `tests/spikes` (31 pasan cada vez). Esto es evidencia **local**; la ejecución en un runner de GitHub Actions sigue pendiente.

---

## 4. Matriz de Impacto Arquitectónico en los Contratos de HARNESS

1. **`Provider.complete(messages, tools) -> ProviderResponse` (async)**:
   - *Impacto*: Proponer mantener `async def complete(...)`. Las llamadas a LLMs implican latencia de red (1 a 15 segundos). La asincronía permite cancelar la consulta en vuelo si el usuario interrumpe o se vence el timeout del turno.
2. **`Tool.run(args) -> ToolResult` (async)**:
   - *Impacto*: Proponer mantener `async def run(...)`. Las herramientas pueden involucrar E/S de disco, subprocesos o llamadas remotas. Permitir que `run` sea asíncrono posibilita timeouts unificados con `asyncio.wait_for(tool.run(...), timeout)`.
3. **`Approver.request(call, details) -> ApprovalResult` (async)**:
   - *Impacto*: Proponer mantener `async def request(...)`. La interacción humana toma segundos o minutos. La corrutina espera la señal asíncrona de la CLI sin consumir CPU ni bloquear la persistencia de eventos.
4. **`EventBus` (híbrido síncrono/asíncrono)**:
   - *Impacto*: El despacho de eventos puede ser síncrono en memoria para observadores locales rápidos, pero debe soportar suscriptores asíncronos para streaming a la CLI o sockets web futuros.
5. **`SessionStore` (síncrono)**:
   - *Impacto*: Mantener **síncrono** en Sprint 1. Supuesto no medido en este spike: las transacciones SQLite locales en disco son del orden de milisegundos o menos; envolverlas en `aiosqlite` añade complejidad innecesaria. Si una consulta es lenta en el futuro, se puede delegar puntualmente a un executor sin alterar el contrato.
6. **`SubagentRunner` (async)**:
   - *Impacto*: Ejecución de subagentes como tareas asíncronas encapsuladas con límite estricto de anidamiento, retornando estructuras tipadas de forma no bloqueante.
7. **Subprocesos de Shell (Sprint 2 - HU-01-04)**:
   - *Impacto*: Los comandos del sistema deben invocarse mediante `asyncio.create_subprocess_exec` (evitando `shell=True` para prevenir inyección). La cancelación debe aplicar `proc.terminate()` con fallback forzado a `proc.kill()`.

---

## 5. Matices Multiplataforma (Windows vs. Linux)

- **Windows**:
  - Python 3.8+ utiliza `asyncio.ProactorEventLoop` por defecto, que soporta E/S de subprocesos y tuberías asíncronas de forma nativa mediante I/O Completion Ports (IOCP).
  - La terminación forzada en Windows llama internamente a `TerminateProcess` de la API Win32.
- **Linux**:
  - Utiliza descriptores de archivo y señales POSIX (`SIGTERM` / `SIGKILL`). Verificado en WSL2 Ubuntu local: un hijo que ignora `SIGTERM` terminó con código -9 tras la gracia (§3, T016).
- **Limitación documentada sobre subprocesos huérfanos**:
  - Cancelar el subproceso directo con `proc.terminate()` o `proc.kill()` termina el proceso padre. Sin embargo, si ese subproceso generó procesos hijos (un árbol de procesos), esos procesos hijos pueden sobrevivir como huérfanos. Para comandos de shell complejos (Sprint 2), se documenta la necesidad futura de usar grupos de procesos (`preexec_fn=os.setsid` en Linux o Job Objects en Windows).

---

## 6. Criterios de Decisión para el Spike

El experimento se considerará exitoso y recomendará la ratificación de `asyncio` si y solo si:
1. El prototipo detiene la operación y devuelve el control al bucle en $< 500\text{ ms}$.
2. Ningún subproceso directo permanece activo en el sistema tras la cancelación.
3. El bucle puede continuar inmediatamente ejecutando otra operación tras la cancelación sin estados corruptos.
4. Las pruebas automatizadas pasan al 100% en Windows (35 pasan y 5 omitidas) y en WSL2 Ubuntu local (40 pasan); la ejecución en un runner de GitHub Actions sigue pendiente.

La decisión queda como **propuesta**: el spike respalda `asyncio` para la espera y la cancelación de subprocesos, pero no verifica el SDK de MCP, el streaming de proveedores ni el rendimiento de SQLite; esas afirmaciones son supuestos (ver D-01 §5).
