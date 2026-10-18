# Feature Specification: SPK-02 — Spike: modelo asíncrono y cancelación de herramientas

**Feature Branch**: `003-async-cancellation-spike`  
**Created**: 2026-10-17  
**Status**: Clarified · Implementación en revisión (T001-T016, ver `tasks.md`) · Decisión D-01 pendiente de aprobación (validación técnica local completa; lista para revisión de A, B y C)  
**Responsable**: A — Núcleo  
**Sprint**: Sprint 1 | **Estimación**: 1 PHU (~3 horas F5)  
**Input**: SPK-02 — Spike: modelo asíncrono y cancelación de herramientas. Investigación técnica experimental para decidir sobre el modelo de ejecución asíncrono de HARNESS y el mecanismo de cancelación de herramientas en curso.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cancelación controlada de operación prolongada y retorno al bucle (Priority: P1)

Como equipo de desarrollo de HARNESS, necesitamos un prototipo experimental mínimo donde una operación de larga duración pueda ser cancelada limpiamente en pleno vuelo, para comprobar empíricamente que el proceso subyacente termina y que el bucle de ejecución recupera el control sin bloqueos ni procesos huérfanos.

**Why this priority**: Es el criterio de aceptación central (AC-01) del spike. Sin evidencia empírica de cancelación y recuperación del control, no es seguro construir el bucle agéntico de producción (HU-01-01) ni las herramientas con tiempo límite (HU-01-04).

**Independent Test**: Puede probarse de forma aislada ejecutando un script de prueba reproducible que lanza una tarea/subproceso de prueba que simula un trabajo de 5 segundos, dispara una cancelación tras un breve retardo (≈120 ms en las pruebas), y verifica que la tarea finaliza de inmediato, que el proceso se destruye y que el bucle continúa activo.

**Acceptance Scenarios**:

1. **Given** un prototipo experimental con bucle asíncrono y una operación prolongada en ejecución controlada, **When** se solicita la cancelación voluntaria de la operación antes de su finalización natural, **Then** la corrutina invocadora captura `asyncio.CancelledError` en menos de 500 ms, el subproceso o tarea subyacente finaliza, el estado se registra como cancelado y el bucle recupera el control operativo inmediatamente sin bloquearse.
2. **Given** una operación prolongada con tiempo límite configurado, **When** el tiempo de ejecución excede dicho límite, **Then** el mecanismo de tiempo agotado cancela la tarea, el bucle recibe `TimeoutError`, el resultado se registra como `timeout` y los recursos del sistema quedan completamente liberados tanto en Linux como en Windows.
3. **Given** la cancelación confirmada de una herramienta o subproceso, **When** se inspecciona la tabla de procesos del sistema operativo, **Then** el PID asociado ya no existe en el sistema operativo y no quedan procesos huérfanos ni zombies.

---

### User Story 2 - Decisión técnica fundada sobre el modelo de concurrencia y sus impactos (Priority: P2)

Como arquitecto y desarrolladores del proyecto, necesitamos un documento formal de decisión técnica basado en la evidencia experimental del prototipo, para ratificar o rectificar de manera informada la adopción de `asyncio` y evaluar sus consecuencias directas sobre MCP, subagentes y aprobación humana.

**Why this priority**: Cierra la pregunta abierta «¿Se confirma asyncio como modelo de concurrencia?» (`docs/01-vision-y-decisiones.md`, tabla «Preguntas abiertas») mediante la tarea Sp1-49 de la planificación de HARNESS v2.5. (V-14 es la decisión del FakeProvider y no está relacionada.) Proporciona los fundamentos técnicos necesarios para desbloquear con certeza HU-01-01, HU-07-01 y las historias de conexión asíncrona de los Sprints 1 a 4.

**Independent Test**: Verificable mediante la revisión del informe técnico de decisión que analiza los pros, contras, alternativas evaluadas (hilos vs corrutinas vs procesos), comportamiento multiplataforma comprobado y consecuencias específicas para los módulos futuros.

**Acceptance Scenarios**:

1. **Given** los resultados empíricos del prototipo de cancelación, **When** se documenta la decisión técnica Sp1-49, **Then** se detalla la viabilidad de `asyncio`, el manejo de `asyncio.CancelledError`, la interacción con subprocesos (`asyncio.create_subprocess_exec`) y el impacto sobre la interfaz `Approver` y clientes MCP.
2. **Given** los contratos asíncronos provisionales de HU-00-01 (`Provider.complete`, `Tool.run`, `Approver.request`), **When** se valida la decisión del spike, **Then** se emite una **propuesta** de dictamen sobre las firmas (`Provider.complete(messages, tools) -> ProviderResponse`, `Tool.run(args) -> ToolResult`, `Approver.request(call, details) -> ApprovalResult`). La ratificación definitiva requiere la aprobación humana de A, B y C y queda registrada en D-01 como pendiente.

---

### Edge Cases

- **Cancelación inmediata o antes de iniciar**: Si la cancelación ocurre antes de que la herramienta o subproceso empiece a ejecutarse, el sistema debe abortar sin iniciar el proceso y reportar el estado cancelado limpiamente.
- **Finalización concurrente con la cancelación**: Si la operación termina con éxito una fracción de segundo antes de recibir la señal de cancelación, el sistema debe aceptar el resultado producido sin lanzar excepciones espurias ni corromper el estado.
- **Subproceso no cooperativo**: Si un proceso hijo no finaliza tras `proc.terminate()`, el mecanismo debe aplicar un tiempo de gracia breve (100–200 ms; 150 ms en el prototipo) y forzar la terminación con `proc.kill()` garantizando la eliminación del PID. En Windows `terminate()` ya equivale a `TerminateProcess`, por lo que este escalamiento solo se valida con un doble controlado (`FakeProcess`); la prueba real con un hijo que ignora `SIGTERM` queda pendiente para Linux.
- **Diferencias multiplataforma (Windows vs Linux)**: En Windows se debe validar el comportamiento bajo `ProactorEventLoop` (por defecto en Python 3.8+), asegurando que `terminate()` / `kill()` finalizan el subproceso sin requerir llamadas POSIX incompatibles.

---

## Requirements *(mandatory)*

### Clarificaciones Operacionales Específicas

1. **Definición de «recuperar el control del bucle»**:
   - La corrutina principal de control no queda colgada en un `await` indefinido.
   - Captura limpiamente la excepción de interrupción (`asyncio.CancelledError` o `asyncio.TimeoutError`).
   - El bucle queda en un estado limpio y disponible para iniciar el siguiente ciclo o turno sin reiniciar el proceso principal.
2. **Verificación de terminación real del proceso**:
   - Se comprueba que `proc.returncode` sea distinto de `None`.
   - Se verifica a nivel del sistema operativo que el identificador de proceso (PID) ya no existe activo (mediante `os.kill(pid, 0)` en Linux capturando `ProcessLookupError`, y comprobación de proceso en Windows).
3. **Cancelación voluntaria vs Tiempo agotado**:
   - **Cancelación voluntaria**: Invocada externamente; genera estado `cancelled` y mensaje explicativo al usuario/modelo.
   - **Tiempo agotado (timeout)**: Invocada automáticamente por umbral temporal; cancela la tarea y genera estado `timeout`.
4. **Evidencia multiplataforma**:
   - Pruebas automatizadas en `tests/spikes/`. Ejecutadas realmente: Windows local (Python 3.12.10) y WSL2 Ubuntu 26.04.1 local (Python 3.12.15, kernel Linux real; no es un runner de GitHub Actions). Pendiente: matriz de CI en Linux (`ubuntu-latest`, Python 3.12), porque nada de esta feature se ha subido todavía. Los escenarios no reproducibles en Windows (hijo que ignora `SIGTERM`) se validaron con dobles controlados y con una prueba real en WSL2 (T016); ver D-01 §2.
5. **Decisiones preestablecidas vs Decisiones dependientes del spike**:
   - **Preestablecidas**: Python 3.12.x como única versión soportada (PD-07, resuelta el 2026-10-17; ver D-01 §7), soporte Windows/Linux, `Approver` asíncrono bidireccional (V-01), persistencia SQLite síncrona en Sprint 1.
   - **Dependientes de este spike (SPK-02)**: Ratificación definitiva de `asyncio` como modelo del núcleo, patrón estándar de cancelación de herramientas y ratificación formal de las firmas provisionales de HU-00-01.

---

### Functional Requirements

- **FR-001**: El prototipo experimental DEBE implementar un bucle mínimo aislado que permita iniciar y monitorear tareas u operaciones sin depender del código de producción de HU-01-01.
- **FR-002**: El prototipo DEBE proporcionar una operación de prueba prolongada y controlable que simule un comando de larga duración (tanto corrutina asíncrona pura como subproceso de sistema).
- **FR-003**: El prototipo DEBE implementar un mecanismo para emitir una solicitud de cancelación asíncrona mientras la operación se encuentra en curso.
- **FR-004**: Ante la solicitud de cancelación, el sistema DEBE asegurar que la tarea o proceso termine de forma comprobable y que el control de ejecución retorne de inmediato al bucle invocador.
- **FR-005**: La cancelación DEBE verificar la liberación limpia de recursos, garantizando que no queden procesos secundarios en ejecución en segundo plano ni fugas en Linux ni en Windows.
- **FR-006**: La investigación DEBE evaluar explícitamente el mecanismo de propagación de excepciones (`asyncio.CancelledError` y `TimeoutError`) y cómo interactúa con el flujo del agente.
- **FR-007**: El spike DEBE producir un informe técnico de decisión (Sp1-49) que documente:
  1. Conclusión fundada sobre el uso de `asyncio` como modelo de concurrencia central.
  2. Protocolo recomendado para cancelación de herramientas y subprocesos.
  3. Implicancias y recomendaciones de diseño para la aprobación humana (`Approver`), integración MCP por stdio y delegación en subagentes.
  4. Propuesta de dictamen sobre la ratificación de las firmas provisionales de HU-00-01 (la ratificación definitiva exige aprobación humana).
  5. Comparación verificable de tres modelos —corrutinas `asyncio`, hilos y procesos— con experimentos mínimos y mediciones reales (`tests/spikes/test_concurrency_alternatives_spike.py`).
- **FR-008**: Toda la investigación experimental y las comprobaciones DEBEN ejecutarse localmente de forma reproducible mediante pruebas automatizadas sin depender de red externa ni de APIs de terceros.

---

### Key Entities *(include if feature involves data)*

- **PrototipoBucle**: Estructura de control mínima que simula el ciclo de vida del agente, orquesta el inicio de tareas asíncronas y maneja las interrupciones y cancelaciones.
- **OperacionProlongada**: Representación abstracta de un trabajo en ejecución (corrutina o subproceso de sistema) con ciclo de vida observable (iniciado, en progreso, completado, cancelado).
- **SeñalCancelacion**: Disparador asíncrono (evento, cancelación de tarea o timeout) que notifica a la operación en curso que debe detenerse de inmediato.
- **InformeDecisionTecnica**: Documento estructurado que formaliza los hallazgos experimentales, el análisis comparativo de alternativas y las decisiones arquitectónicas vinculantes para las siguientes historias.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El prototipo experimental demuestra de forma reproducible que una operación cancelada detiene su ejecución y devuelve el control al bucle en menos de 500 milisegundos tras emitir la señal de cancelación.
- **SC-002**: En el 100% de las ejecuciones de prueba **realizadas** (Windows local y WSL2 Ubuntu local; el runner de GitHub Actions sigue pendiente), ningún proceso hijo directo o subproceso permanece vivo tras la cancelación confirmada. Los nietos no están cubiertos (ver D-01 §7).
- **SC-003**: El informe técnico Sp1-49 (D-01) presenta una propuesta fundada sobre el modelo de concurrencia, abordando con evidencia los 4 aspectos críticos: `asyncio` (con la comparación de alternativas), cancelación de herramientas, impacto en MCP/subagentes y firmas. Queda **pendiente de aprobación**; las afirmaciones no medidas en el spike se marcan como supuestos.
- **SC-004**: La suite de pruebas experimentales y la documentación asociada se implementan y verifican en un total de tiempo neto no superior a las 3 horas de trabajo técnico (1 PHU), dividido en microtareas de menos de 60 minutos.

---

## Assumptions

- **Aislamiento del spike**: El código y las pruebas del prototipo se mantienen en módulos independientes de spike o bajo `tests/` y artefactos de especificación, sin contaminar de forma prematura el paquete de producción `src/harness_agent/core/`.
- **Compatibilidad con contratos provisionales**: Se asume que las interfaces definidas en HU-00-01 (`core/interfaces/`) se mantienen como referencia base y no se alteran durante el desarrollo de la investigación. Firmas reales verificadas en el código: `Provider.complete(messages, tools) -> ProviderResponse`, `Tool.run(args) -> ToolResult`, `Approver.request(call, details) -> ApprovalResult` (todas `async def`).
- **Entorno de ejecución**: Las pruebas experimentales se ejecutan dentro del entorno virtual del proyecto (hasta ahora solo Python 3.12.10) con las dependencias fijadas (`requirements-dev.txt`), aprovechando `pytest` y `pytest-asyncio`. La versión soportada es Python 3.12.x (PD-07, 2026-10-17); el spike no la modifica.
- **Independencia de hardware y red**: La operación prolongada simulada utiliza recursos puramente locales (p. ej. `asyncio.sleep` o subproceso de comando de sistema inocuo como `ping` / `sleep`), sin requerir acceso a internet ni permisos de superusuario.
- **Trazabilidad estricta**: El spike responde a las tareas Sp1-48 y Sp1-49 del plan del Sprint 1, cumpliendo el rol de guardián de calidad antes de construir el bucle de producción en HU-01-01.
