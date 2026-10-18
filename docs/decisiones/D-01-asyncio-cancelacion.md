# Decisión Técnica D-01: Propuesta de adopción de Asyncio y protocolo de cancelación de herramientas (SPK-02)

**Fecha**: 2026-10-17 (revisada tras la auditoría técnica del mismo día)  
**Estado**: **PENDIENTE DE APROBACIÓN** (propuesta técnica del Integrante A; no ratificada). Validación técnica local completa (Windows y WSL2 Ubuntu): **lista para la revisión de A, B y C**, sin consentimiento registrado (ver §8)  
**Autor**: Integrante A — Núcleo (plan del Sprint 1, Sp1-48 y Sp1-49)  
**Trazabilidad**: [SPK-02](../../specs/003-async-cancellation-spike/spec.md) · AC-01 · decisión V-01 · pregunta abierta «¿Se confirma asyncio como modelo de concurrencia?» en [docs/01](../01-vision-y-decisiones.md) (tabla «Preguntas abiertas»). V-14 es la decisión del FakeProvider y no tiene relación con este documento.  
**Código y pruebas**: [tests/spikes/test_async_cancellation_spike.py](../../tests/spikes/test_async_cancellation_spike.py) · [tests/spikes/test_concurrency_alternatives_spike.py](../../tests/spikes/test_concurrency_alternatives_spike.py) · [tests/spikes/test_linux_sigterm_spike.py](../../tests/spikes/test_linux_sigterm_spike.py)  

---

## 1. Contexto del problema

Las interfaces de HU-00-01 que cruzan una frontera lenta se declararon `async def` de forma provisional. Las firmas reales en el código son:

| Contrato | Firma real |
|---|---|
| `Provider` | `async def complete(self, messages, tools) -> ProviderResponse` |
| `Tool` | `async def run(self, args) -> ToolResult` |
| `Approver` | `async def request(self, call, details) -> ApprovalResult` |

La pregunta abierta de `docs/01` («¿Se confirma asyncio como modelo de concurrencia?», cierre previsto a fin del Sprint 1) depende de este spike. Los contratos de HU-00-01 siguen sin ratificar: la aprobación humana de T016 / Sp1-03 está pendiente, así que esta decisión no puede ratificarlos por sí sola.

---

## 2. Evidencia experimental y su alcance real

Resultados reales de dos entornos **locales**. Ninguno es un runner de GitHub Actions: nada se ha subido a GitHub y la CI no ha ejecutado esta feature.

| Entorno | Intérprete | Suite completa | Mypy estricto | Ruff |
|---|---|---|---|---|
| Windows 10 local (`.venv` del proyecto) | CPython 3.12.10 | **35 pasan y 5 se omiten** en 8.84 s (las 5 omitidas son las pruebas exclusivas de Linux) | Sin errores (30 archivos) | `format --check` y `check` limpios |
| **WSL2 Ubuntu 26.04.1 LTS local**, kernel 6.18.54.1-microsoft-standard-WSL2 (no es `ubuntu-latest`) | CPython 3.12.15 (`uv python install`, standalone, en espacio de usuario), `.venv` nuevo en `~/harness-agent` | **40 pasan, 0 omitidas** en 10.48 s (exit 0) | Sin errores (30 archivos) | `format --check` y `check` limpios |

En WSL2 el código se copió al sistema de archivos de Linux (sin `.venv`, `.git` ni cachés) con los cambios locales sin publicar, y las dependencias fijadas de `requirements-dev.txt` se instalaron con `uv pip` (ese entorno no trae `pip`), más `uv pip install -e . --no-deps`. Las 31 pruebas de `tests/spikes` pasaron además en 5 ejecuciones consecutivas (31 pasan cada vez, entre 7.93 y 8.04 s). Tras las corridas, `ps` no mostró procesos del experimento (`time.sleep`, `SIG_IGN`, `multiprocessing`).

| Tipo de evidencia | Qué cubre | Estado |
|---|---|---|
| **Ejecutado en Windows con procesos reales** | V1-V7 (ejecución normal, cancelación activa, PID muerto, retorno de control, turno posterior, timeout, 3 cancelaciones seguidas); V8-V9 (cancelar antes de iniciar y durante el arranque); V10 (cancelación tardía sobre proceso ya terminado); V19 (cuatro desenlaces, ningún PID vivo); V20-V21 (semántica de `CancelledError`); V22 (conteo de handles estable); 4 experimentos de alternativas | Verificado |
| **Ejecutado con dobles controlados** (`FakeProcess`) | V11 (tarea ya terminada), V12-V14 (escalamiento a `kill`, hijo cooperativo, `ProcessLookupError`), V15-V17 (segunda cancelación durante la limpieza y controles negativos), V18 (bucle activo durante la limpieza) | Verifica el algoritmo, no el sistema operativo |
| **Ejecutado en WSL2 Ubuntu local con procesos reales** (kernel Linux real; no es un runner de GitHub Actions) | V1-V22 y los 4 experimentos de alternativas (V11-V18 siguen usando dobles, también aquí); además, 5 pruebas reales exclusivas de Linux (`test_linux_sigterm_spike.py`): el hijo ignora `SIGTERM`, la limpieza escala a `SIGKILL` (código de salida -9), segunda y tercera cancelación durante el período de gracia, timeout con hijo que ignora `SIGTERM`, y 5 ciclos sin PID del experimento vivo ni zombi | Verificado localmente |
| **Pendiente de verificación** | Ejecución en un runner `ubuntu-latest` de GitHub Actions (nada está subido); árboles de procesos; revisión humana | Sin evidencia |

Mediciones de la cancelación (Windows, procesos reales):
- Cancelación activa (`SpikeLoop.run_operation`, n=10): el control volvió en **1.0 / 1.4 / 2.4 ms** (mín / mediana / máx); el límite de AC-01 es 500 ms. Estado `CANCELLED`, código de salida 1.
- Timeout de 250 ms (n=5): la operación completa tardó 251 a 267 ms, estado `TIMEOUT`, código de salida 1.
- Los tests miden con un retardo de ≈120 ms antes de cancelar (V2) y 250 ms de timeout (V6).

Mediciones de la cancelación (WSL2 Ubuntu local, procesos reales, sondeo de diagnóstico fuera del repositorio):
- Cancelación activa de un hijo cooperativo (`time.sleep`, n=10): el control volvió en **0.7 / 1.0 / 1.4 ms** (mín / mediana / máx); código de salida **-15** (`SIGTERM`) en las 10 cancelaciones y ningún PID vivo.

Evidencia del escalamiento `SIGTERM` → `SIGKILL` (WSL2 Ubuntu local; período de gracia de 150 ms salvo indicación; salida de `pytest -s` de una corrida):

| Escenario (prueba) | Resultado observado |
|---|---|
| Control: el hijo ignora `SIGTERM` (`test_linux_child_really_ignores_sigterm`) | Tras `terminate()` el proceso seguía vivo a los 0.5 s; con `kill()` terminó con código **-9** y su PID desapareció del SO |
| Cancelación con hijo que ignora `SIGTERM` (`test_linux_sigterm_ignored_escalates_to_sigkill`) | Código de salida **-9**; el control volvió a los **151.6 ms** (gracia de 150 ms más el `kill`); PID ausente (`ProcessLookupError`, sin entrada en `/proc`) |
| Tres cancelaciones seguidas durante una gracia de 300 ms (`test_linux_second_cancel_during_grace_period_still_kills`) | 2 solicitudes extra absorbidas, código **-9**, el control volvió a los **303.0 ms**; PID ausente |
| Timeout de 0.4 s con hijo que ignora `SIGTERM` (`test_linux_timeout_with_sigterm_ignored_escalates`) | Estado `TIMEOUT`, código **-9**, total **553.4 ms**; PID ausente |
| 5 ciclos seguidos (`test_linux_sequential_cycles_leave_no_experiment_process`) | Códigos de salida `[-9, -9, -9, -9, -9]`; control de vuelta en 151.5 / 152.2 / 151.2 / 152.2 / 152.0 ms; ninguno de los 5 PIDs vivo, zombi ni listado como hijo del proceso de pruebas |

El hijo escribe un archivo de preparación solo después de instalar `SIG_IGN`, y la prueba lo espera con un plazo máximo: así `SIGTERM` nunca se envía antes de que pueda ser ignorado. Con un hijo que ignora `SIGTERM` el control no vuelve antes de agotarse la gracia (es el coste del período de gracia, no un retraso del bucle); el límite de 500 ms de AC-01 se cumple con margen (≈152 ms).

Límites de la evidencia:
- **Descriptores**: V22 comprueba que el conteo de descriptores/handles del proceso de pruebas no crece tras 5 ciclos de cancelación (Windows: 162 antes y 162 después; WSL2 Ubuntu, `/proc/self/fd`: 8 antes y 8 después; ambos en mediciones de diagnóstico, y la prueba tolera un delta de hasta 2). No se verifica el cierre de cada tubería individual.
- **PIDs**: se verifican los PIDs de los procesos directos creados por las pruebas; en Linux, además, que no figuren como hijos del proceso de pruebas (zombis incluidos). No hay un barrido de todos los procesos del sistema.
- **Códigos de salida**: `TerminateProcess` en Windows produce 1 en `asyncio` y -15 en `multiprocessing`; en Linux se observaron -15 (`SIGTERM` atendido por el hijo) y -9 (`SIGKILL` tras ignorar `SIGTERM`).
- **Alcance de WSL2**: es un kernel Linux real, pero no es el runner `ubuntu-latest` de GitHub Actions; la versión de Python (3.12.15) tampoco coincide con la de Windows (3.12.10).

---

## 3. Comparación de alternativas (US2 / FR-007)

Mediciones reales (5 ejecuciones; mín / mediana / máx; solo Windows). El detalle y su lectura están en [research.md §3](../../specs/003-async-cancellation-spike/research.md).

| Propiedad | A. asyncio + subproceso | B1. Hilo con trabajo Python | B2. Hilo dueño de `Popen` | C. `multiprocessing` |
|---|---|---|---|---|
| Espera sin bloquear al llamador | Sí | Sí | Sí | Sí |
| Control tras cancelar | 1.6 / 1.7 / 3.3 ms | 158 / 165 / 166 ms (solo el `await` se rinde) | 1.3 / 1.3 / 1.6 ms | 2.1 / 2.1 / 2.5 ms |
| La operación se detiene de verdad | Sí | **No**: siguió 835 / 843 / 844 ms más | Sí, con acceso al `Popen` | Sí |
| PID vivo después | No | n/a | No | No |
| Integración con E/S asíncrona | Nativa | Puentes | Puentes | IPC |
| Complejidad | Moderada | Alta | Alta | Alta |

Conclusión de la comparación: la diferencia decisiva no es la velocidad, sino que `asyncio` ofrece una única primitiva para esperar, poner *timeout* y cancelar, tanto subprocesos como futuras llamadas de red o aprobación humana. Con hilos el trabajo Python bloqueante no se puede cancelar (B1) y un subproceso exige plomería manual (B2); con procesos de `multiprocessing` se necesita IPC para cada comunicación (C). Esta conclusión **no** prueba que `asyncio` sea mejor en rendimiento ni verifica el SDK de MCP, el streaming de proveedores o SQLite (ver §5).

---

## 4. Propuesta de decisión (pendiente de aprobación)

Se propone **adoptar `asyncio` como modelo de ejecución del núcleo** y mantener las siguientes firmas, que ya están en el código de HU-00-01:

- `Provider.complete(messages, tools) -> ProviderResponse` (asíncrona)
- `Tool.run(args) -> ToolResult` (asíncrona)
- `Approver.request(call, details) -> ApprovalResult` (asíncrona)

Esto es una propuesta técnica del autor. No modifica ningún contrato compartido. Para que sea una decisión vinculante se requieren las condiciones de §8.

---

## 5. Consecuencias propuestas por subsistema y qué es supuesto

| Subsistema | Consecuencia propuesta | Respaldo en el spike |
|---|---|---|
| Bucle agéntico (HU-01-01) | La herramienta se ejecuta bajo `asyncio.wait_for`; la limpieza del subproceso se protege como se describe en §6 | Verificado (V6, V15-V20) |
| `Provider.complete` | Permite cancelar una consulta lenta en vuelo | Supuesto: el spike no ejecuta llamadas de red ni streaming |
| `Approver.request` | El núcleo queda suspendido en `await` mientras la interfaz atiende la entrada (regla V-01) | Supuesto de diseño; el spike no implementa aprobación |
| `SessionStore` | Se mantiene síncrono en el Sprint 1 | Supuesto: no se midió el coste de SQLite |
| `EventBus` | Despacho en memoria, con suscriptores síncronos y asíncronos | Supuesto |
| MCP (HU-08-01) | El SDK oficial de Python para MCP usa `asyncio`/`anyio`, por lo que no haría falta puentear con hilos | Supuesto externo, no verificado aquí; confirmar en SPK-04 / HU-08-01 |
| Subagentes (`SubagentRunner.execute`, HU-09-01) | Tareas asíncronas cancelables sin afectar al agente principal | Supuesto; el spike solo cancela subprocesos |

---

## 6. Semántica de cancelación y robustez de la limpieza

- `SpikeLoop.run_operation` distingue `COMPLETED` (código 0), `FAILED` (código distinto de 0), `CANCELLED` y `TIMEOUT` (V19).
- **Absorber `CancelledError` es solo experimental.** El prototipo lo hace por defecto: la tarea parece terminar bien y queda `Task.cancelling() == 1` (V21). Producción debe usar el modo `reraise_cancel=True`: limpiar y volver a lanzar, dejando la tarea cancelada (V20).
- **Segunda cancelación durante la limpieza.** La limpieza corre como tarea propia, esperada en un bucle de `asyncio.shield` que reanuda la espera tras cada `CancelledError`. Dos controles negativos muestran por qué hace falta: esperar `op.cancel()` sin protección se interrumpe antes de `kill` y deja vivo al hijo (V16), y un único `shield` devuelve el control al llamador mientras el hijo sigue vivo (V17). `shield` por sí solo no garantiza la limpieza completa.
- No cubierto: un hijo que no termina ni tras `kill`, y el cierre del bucle de eventos con una limpieza a medias. La cancelación definitiva (Ctrl+C, persistencia del evento de interrupción en SQLite) sigue siendo alcance de **HU-06-03**.

---

## 7. Limitaciones, riesgos y decisiones pendientes

1. **Árboles de procesos**: el protocolo mata el subproceso directo, no a sus nietos. Requisito para HU-01-04: grupos de procesos (`os.setsid` / `os.killpg` en POSIX) o Job Objects en Windows. Sin evidencia en el spike.
2. **Linux: verificado en WSL2 local, no en la CI**: el escalamiento `SIGTERM` → `SIGKILL` con un hijo real se comprobó en WSL2 Ubuntu (§2). Sigue pendiente la matriz de HU-00-02 (Linux/Windows × 3.12, tras PD-07) en un runner de GitHub Actions: requiere confirmar y subir los cambios.
3. **Versión de Python (resuelta por PD-07)**: el Product Owner aprobó el 2026-10-17 que Python 3.12.x es la única versión soportada (`requires-python = ">=3.12,<3.13"`, mypy `3.12`, ruff `py312`, CI en Windows y Linux con 3.12). Historial: la constitución, `docs/01` y el README exigían 3.12+, mientras `pyproject.toml` y la CI de HU-00-02 usaban 3.11+. Resolver PD-07 no aprueba D-01.
4. **Semántica de `Task.cancelling()` entre versiones**: ya no aplica, porque Python 3.11 dejó de estar soportado (PD-07). La semántica se verificó solo en 3.12.10.

---

## 8. Condiciones para aprobar D-01

- [x] Firmas y referencias corregidas contra el código real.
- [x] Comparación de alternativas con mediciones reales.
- [x] Casos límite cubiertos por pruebas deterministas y dobles.
- [ ] Ejecución verde en la CI en Linux y Windows con Python 3.12 (requiere confirmar y subir los cambios).
- [x] Prueba real de un hijo que ignora `SIGTERM` en Linux: ejecutada en WSL2 Ubuntu local (5 pruebas, código de salida -9). La evidencia en un runner de GitHub Actions sigue pendiente (casilla anterior).
- [x] Decisión de gobernanza sobre la versión de Python: resuelta por PD-07 (2026-10-17, Python 3.12.x única versión soportada).
- [ ] Aprobación de HU-00-01 / T016 (Sp1-03), prerrequisito para ratificar firmas.
- [ ] Revisión técnica y aprobación humana de A, B y C.

> **Contexto (2026-10-18)**: el equipo comunicó, a través del Product Owner, la decisión de cerrar las historias pendientes y de usar nomenclatura en inglés (`AuthorizedArea` y los 17 eventos). Es una decisión colectiva relayada, sin aprobaciones individuales de A, B y C documentadas, por lo que **no ratifica D-01** ni completa T016. Ver [revision-conjunta-abc.md](revision-conjunta-abc.md).

### Bloque de aprobación (sin consentimiento registrado)

| Integrante | Rol | Decisión | Fecha |
|---|---|---|---|
| A | Núcleo | _Pendiente_ | — |
| B | Estado | _Pendiente_ | — |
| C | Control y conexiones | _Pendiente_ | — |

Estado de la validación técnica: completa en entornos locales (Windows y WSL2 Ubuntu). La decisión queda lista para que A, B y C la revisen; las casillas pendientes de §8 son externas a este spike (CI en GitHub Actions y T016 / Sp1-03).

---

## 9. Alcance pendiente para HU-06-03 (Sprint 3)

Queda fuera de este spike: captura de `SIGINT` / Ctrl+C en la CLI y persistencia transaccional del evento de interrupción antes de devolver el control al operador.
