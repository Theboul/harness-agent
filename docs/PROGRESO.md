# Progreso

> [← 06-historial-planificacion.md](06-historial-planificacion.md) · [Índice](00-indice.md)  
> Única fuente de estado del proyecto: qué se hizo, dónde está y con qué evidencia.  
> Ver también: [03-plan-sprints.md](03-plan-sprints.md) · [06-historial-planificacion.md](06-historial-planificacion.md) · [04a](04a-historias-fundacion.md) · [04b](04b-historias-estado.md) · [04c](04c-historias-control.md) · [04d](04d-historias-conexiones.md) · [04e](04e-historias-coding-harness.md)

## Cómo mantenerlo

1. Al empezar una historia, ponerla en **En curso** y anotar quién la toma.
2. Al cerrar un cambio, completar **Commit/PR**, **Archivos** (rutas bajo `src/harness_agent/` y `tests/`) y **Evidencia** (comando de prueba y resultado).
3. Pasar a **Hecha** solo con la Definition of Done cumplida ([01-vision-y-decisiones.md](01-vision-y-decisiones.md)).
4. Toda decisión o desvío relevante va al **Registro de cambios** con enlace al ID afectado.

Estados: `Pendiente` · `En curso` · `En revisión` · `Hecha` · `Bloqueada`.

## Resumen

| Sprint | Historias | Hechas | PHU Alta | PHU totales | PHU hechos |
|---|---|---|---|---|---|
| Sprint 1 | 16 | 0 | 39 | 39 | 0 |
| Sprint 2 | 16 | 0 | 31 | 31 | 0 |
| Sprint 3 | 27 | 0 | 33 | 51 | 0 |
| Sprint 4 | 16 | 0 | 19 | 29 | 0 |
| Backlog | 12 | 0 | 0 | 39 | 0 |

Actualizar esta tabla al cerrar cada historia.

## Sprint 1

| ID | Historia | Prio. | PHU | Resp. | Estado | Commit/PR | Archivos | Evidencia |
|---|---|---|---|---|---|---|---|---|
| [HU-00-01](04a-historias-fundacion.md#hu-00-01) | Esqueleto del repositorio e interfaces acordadas | Alta | 3 | A — Núcleo | Pendiente de aprobación técnica | — | pyproject.toml, src/harness_agent/, tests/, docs/guia-contratos-desarrollo.md | T001-T015 completas; pytest y mypy --strict en verde con `pip install -e ".[dev]"` en Python 3.12; AC-01 y AC-02 verificados; Aprobado por Product Owner (2026-10-17); Sp1-03 pendiente de ratificación técnica (A, B, C) |
| [HU-00-02](04a-historias-fundacion.md#hu-00-02) | Integración continua con pruebas, tipado y formato | Alta | 2 | A — Núcleo | En revisión | — | .github/workflows/ci.yml, requirements-dev.txt, pyproject.toml | T001-T007 completas (Evidencia A); Ruff format/check 0 errores; Mypy estricto 0 errores (26 archivos); Pytest 9/9 pass (0.29s), 97% cobertura en `src/harness_agent/`; 3 pruebas negativas verificadas con exit code 1 (test fallo, mypy fallo, ruff format fallo); T008 (Evidencia B: ejecución remota en GitHub Actions) y T009 (Evidencia C: Branch Protection Rules) documentadas en quickstart.md y pendientes de push/configuración remota |
| [HU-00-03](04a-historias-fundacion.md#hu-00-03) | Proveedor simulado para pruebas | Alta | 2 | B — Estado | Pendiente |  |  |  |
| [HU-00-04](04a-historias-fundacion.md#hu-00-04) | Configuración por archivo y variables de entorno | Alta | 1 | B — Estado | Pendiente |  |  |  |
| [HU-01-01](04a-historias-fundacion.md#hu-01-01) | Bucle agéntico básico | Alta | 5 | A — Núcleo | Pendiente |  |  |  |
| [HU-01-02](04a-historias-fundacion.md#hu-01-02) | Registro de herramientas con esquema y validación | Alta | 3 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-01-03](04a-historias-fundacion.md#hu-01-03) | Herramientas de archivos: leer, escribir, listar y buscar | Alta | 4 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-01-05](04a-historias-fundacion.md#hu-01-05) | Bus de eventos desacoplado de la interfaz | Alta | 2 | B — Estado | Pendiente |  |  |  |
| [SPK-02](04a-historias-fundacion.md#spk-02) | Spike: modelo asíncrono y cancelación de herramientas | Alta | 1 | A — Núcleo | Pendiente |  |  |  |
| [HU-03-01](04b-historias-estado.md#hu-03-01) | Esquema SQLite y creación de sesión | Alta | 2 | B — Estado | Pendiente |  |  |  |
| [HU-03-02](04b-historias-estado.md#hu-03-02) | Persistir cada evento al ocurrir y tolerar cortes abruptos | Alta | 3 | B — Estado | Pendiente |  |  |  |
| [HU-05-01](04c-historias-control.md#hu-05-01) | Política denegar, preguntar, permitir que falla cerrada | Alta | 3 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-06-01](04c-historias-control.md#hu-06-01) | CLI básica con eventos en tiempo real | Alta | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-07-01](04d-historias-conexiones.md#hu-07-01) | Interfaz Provider y formato interno de mensajes | Alta | 3 | A — Núcleo | Pendiente |  |  |  |
| [HU-07-02](04d-historias-conexiones.md#hu-07-02) | Adaptador LiteLLM para el primer proveedor | Alta | 2 | B — Estado | Pendiente |  |  |  |
| [SPK-01](04d-historias-conexiones.md#spk-01) | Spike: traducir herramientas entre OpenAI y Anthropic con LiteLLM | Alta | 1 | B — Estado | Pendiente |  |  |  |

### Control de Consenso y Aprobación de Contratos (Sp1-03 / T016)

> Hito de revisión humana obligatoria según el Principio IX de la Constitución. Requiere la validación formal de los tres desarrolladores antes de cambiar HU-00-01 a `Completada` e iniciar las historias dependientes.

| Rol / Integrante | Responsabilidad en Contratos | Estado de Aprobación | Fecha de Aprobación |
|---|---|---|---|
| **Product Owner** | Aprobación de negocio y criterios de aceptación (AC-01, AC-02) | `Aprobado` | 2026-10-17 |
| **Integrante A (Núcleo)** | `Provider`, `ContextManager`, `SubagentRunner`, `EventBus`, `Message`, `Event` | `Pendiente` | — |
| **Integrante B (Estado)** | `SessionStore`, `MemoryStore`, `Provider` (consumo), dobles en memoria | `Pendiente` | — |
| **Integrante C (Control)** | `Tool`, `ToolRegistry`, `PermissionPolicy`, `Approver`, `Shell`, `AreaAutorizada` | `Pendiente` | — |

**Observaciones de la revisión**:
- *2026-10-17: Aprobación expresa registrada por el Product Owner tras verificar AC-01, AC-02, 9 pruebas en verde y Mypy sin errores. HU-00-01 se mantiene en estado `Pendiente de aprobación técnica` a la espera de la ratificación de los integrantes A, B y C (Sp1-03 / T016).*

## Sprint 2

| ID | Historia | Prio. | PHU | Resp. | Estado | Commit/PR | Archivos | Evidencia |
|---|---|---|---|---|---|---|---|---|
| [HU-01-04](04a-historias-fundacion.md#hu-01-04) | Herramienta de shell portable con tiempo límite | Alta | 3 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-01-06](04a-historias-fundacion.md#hu-01-06) | Límites de turnos, tiempo y costo por sesión | Alta | 2 | A — Núcleo | Pendiente |  |  |  |
| [HU-02-01](04b-historias-estado.md#hu-02-01) | Estimación de tokens y prefijo estable | Alta | 2 | B — Estado | Pendiente |  |  |  |
| [HU-02-02](04b-historias-estado.md#hu-02-02) | Recorte de salidas largas de herramientas | Alta | 1 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-02-03](04b-historias-estado.md#hu-02-03) | Compactación automática por umbral | Alta | 5 | B — Estado | Pendiente |  |  |  |
| [HU-02-06.1](04b-historias-estado.md#hu-02-06.1) | Contexto esencial persistente fuera del historial compactable | Alta | 1 | B — Estado | Pendiente |  |  |  |
| [SPK-03](04b-historias-estado.md#spk-03) | Spike: compactación sin perder el objetivo | Alta | 1 | B — Estado | Pendiente |  |  |  |
| [HU-03-04](04b-historias-estado.md#hu-03-04) | Reanudar una sesión por identificador | Alta | 3 | A — Núcleo | Pendiente |  |  |  |
| [HU-05-02](04c-historias-control.md#hu-05-02) | Lista de denegados y análisis de comandos compuestos | Alta | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-05-03](04c-historias-control.md#hu-05-03) | Aprobación con detalle: una vez, toda la sesión o rechazar | Alta | 3 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-05-04](04c-historias-control.md#hu-05-04) | Rechazo con motivo que vuelve al modelo | Alta | 1 | A — Núcleo | Pendiente |  |  |  |
| [SPK-04](04d-historias-conexiones.md#spk-04) | Spike: cliente MCP por stdio y servidor de demostración | Alta | 1 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-11-01](04e-historias-coding-harness.md#hu-11-01) | Tarea con criterios de aceptación protegidos en SQLite | Alta | 2 | A — Núcleo | Pendiente |  |  |  |
| [HU-11-02](04e-historias-coding-harness.md#hu-11-02) | Git mediante el shell con reglas de permisos por subcomando | Alta | 1 | B — Estado | Pendiente |  |  |  |
| [HU-11-03](04e-historias-coding-harness.md#hu-11-03) | Pruebas y lint mediante el shell con salida recortada | Alta | 1 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1) | Verificación automática de criterios objetivos: solo el harness marca passes | Alta | 2 | A — Núcleo | Pendiente |  |  |  |

## Sprint 3

| ID | Historia | Prio. | PHU | Resp. | Estado | Commit/PR | Archivos | Evidencia |
|---|---|---|---|---|---|---|---|---|
| [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1) | Pruebas de integración y de fallos del núcleo | Alta | 2 | A — Núcleo | Pendiente |  |  |  |
| [HU-00-06](04a-historias-fundacion.md#hu-00-06) | README, guion de demostración y documento de arquitectura | Alta | 3 | B — Estado | Pendiente |  |  |  |
| [HU-00-07](04a-historias-fundacion.md#hu-00-07) | Cobertura mínima y prueba de instalación | Media | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-01-07](04a-historias-fundacion.md#hu-01-07) | Varias llamadas a herramientas en un mismo turno | Media | 2 | A — Núcleo | Pendiente |  |  |  |
| [HU-01-08](04a-historias-fundacion.md#hu-01-08) | Detección de llamadas repetidas | Media | 1 | A — Núcleo | Pendiente |  |  |  |
| [HU-02-04](04b-historias-estado.md#hu-02-04) | Comando para compactar manualmente | Media | 1 | B — Estado | Pendiente |  |  |  |
| [HU-02-06.2](04b-historias-estado.md#hu-02-06.2) | Decisiones acumuladas y continuidad tras varias compactaciones | Alta | 1 | B — Estado | Pendiente |  |  |  |
| [HU-03-05](04b-historias-estado.md#hu-03-05) | Consumo de tokens y costo estimado por sesión | Media | 2 | B — Estado | Pendiente |  |  |  |
| [HU-05-05](04c-historias-control.md#hu-05-05) | Registro de auditoría de decisiones | Alta | 2 | B — Estado | Pendiente |  |  |  |
| [HU-05-06](04c-historias-control.md#hu-05-06) | Reglas de permisos por archivo | Media | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-05-07](04c-historias-control.md#hu-05-07) | Modo de solo lectura | Media | 1 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-06-03](04c-historias-control.md#hu-06-03) | Interrumpir la ejecución sin perder la sesión | Media | 2 | A — Núcleo | Pendiente |  |  |  |
| [HU-07-03](04d-historias-conexiones.md#hu-07-03) | Segundo proveedor y selección por configuración | Alta | 2 | A — Núcleo | Pendiente |  |  |  |
| [HU-07-04](04d-historias-conexiones.md#hu-07-04) | Reintentos con espera exponencial | Media | 1 | A — Núcleo | Pendiente |  |  |  |
| [HU-07-05](04d-historias-conexiones.md#hu-07-05) | Conmutación por fallo con umbral por modelo | Alta | 3 | A — Núcleo | Pendiente |  |  |  |
| [HU-09-01](04d-historias-conexiones.md#hu-09-01) | Delegar en un subagente con contexto limpio | Alta | 5 | B — Estado | Pendiente |  |  |  |
| [HU-09-02](04d-historias-conexiones.md#hu-09-02) | Instrucciones propias y herramientas restringidas por subagente | Alta | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-09-03](04d-historias-conexiones.md#hu-09-03) | Resultado estructurado en lugar de la transcripción | Alta | 2 | A — Núcleo | Pendiente |  |  |  |
| [HU-09-04](04d-historias-conexiones.md#hu-09-04) | Un solo nivel de anidamiento y límites por subagente | Alta | 2 | A — Núcleo | Pendiente |  |  |  |
| [HU-09-05](04d-historias-conexiones.md#hu-09-05) | Propagación explícita de errores del subagente | Media | 1 | A — Núcleo | Pendiente |  |  |  |
| [HU-09-06](04d-historias-conexiones.md#hu-09-06) | Subagente verificador y subagente explorador | Alta | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-11-04.2](04e-historias-coding-harness.md#hu-11-04.2) | Verificación independiente con el subagente verificador | Alta | 1 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-11-05](04e-historias-coding-harness.md#hu-11-05) | Resumen de cambios y aprobación humana del diff | Alta | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-11-06](04e-historias-coding-harness.md#hu-11-06) | Pull Request tras la aprobación | Alta | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-11-07](04e-historias-coding-harness.md#hu-11-07) | Una sesión por ticket con un worktree propio | Media | 3 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) | Archivo de progreso del ticket con puntos de control | Alta | 1 | B — Estado | Pendiente |  |  |  |
| [HU-11-08.2](04e-historias-coding-harness.md#hu-11-08.2) | Rutina de arranque al reanudar un ticket | Alta | 1 | C — Control y conexiones | Pendiente |  |  |  |

## Sprint 4

| ID | Historia | Prio. | PHU | Resp. | Estado | Commit/PR | Archivos | Evidencia |
|---|---|---|---|---|---|---|---|---|
| [HU-00-05.2](04a-historias-fundacion.md#hu-00-05.2) | Prueba de aislamiento de fallos de un servidor MCP | Alta | 1 | A — Núcleo | Pendiente |  |  |  |
| [HU-03-03](04b-historias-estado.md#hu-03-03) | Listar sesiones | Alta | 1 | B — Estado | Pendiente |  |  |  |
| [HU-04-01](04b-historias-estado.md#hu-04-01) | Almacén de memoria separado del historial | Alta | 2 | B — Estado | Pendiente |  |  |  |
| [HU-04-02](04b-historias-estado.md#hu-04-02) | Herramienta de memoria y carga al inicio | Alta | 3 | B — Estado | Pendiente |  |  |  |
| [HU-04-03](04b-historias-estado.md#hu-04-03) | Memoria estructurada de la sesión | Media | 3 | B — Estado | Pendiente |  |  |  |
| [HU-04-04](04b-historias-estado.md#hu-04-04) | Inspeccionar y editar la memoria | Media | 1 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-04-05](04b-historias-estado.md#hu-04-05) | No almacenar secretos en memoria | Media | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-05-08](04c-historias-control.md#hu-05-08) | Contenido externo tratado como datos | Media | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-06-02](04c-historias-control.md#hu-06-02) | Herramienta para preguntar al usuario con opciones | Alta | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-06-04](04c-historias-control.md#hu-06-04) | Comandos de control de la sesión | Media | 2 | B — Estado | Pendiente |  |  |  |
| [HU-08-01](04d-historias-conexiones.md#hu-08-01) | Conexión a un servidor MCP por stdio | Alta | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-08-02](04d-historias-conexiones.md#hu-08-02) | Descubrir herramientas MCP y traducirlas al formato interno | Alta | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-08-03](04d-historias-conexiones.md#hu-08-03) | Invocar herramientas MCP bajo la misma política de permisos | Alta | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-08-04](04d-historias-conexiones.md#hu-08-04) | Aislar los fallos de un servidor MCP | Alta | 1 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-10-01](04d-historias-conexiones.md#hu-10-01) | Trazas estructuradas de cada llamada | Alta | 2 | B — Estado | Pendiente |  |  |  |
| [HU-10-02](04d-historias-conexiones.md#hu-10-02) | Redacción de secretos en registros | Alta | 1 | B — Estado | Pendiente |  |  |  |
Reparto de Sprint 4 por ratificar en el Planning (la semana y las 8 PHU de MCP ya están aprobadas): [HU-03-03](04b-historias-estado.md#hu-03-03), [HU-04-01](04b-historias-estado.md#hu-04-01), [HU-04-02](04b-historias-estado.md#hu-04-02), [HU-04-03](04b-historias-estado.md#hu-04-03), [HU-04-04](04b-historias-estado.md#hu-04-04), [HU-04-05](04b-historias-estado.md#hu-04-05), [HU-05-08](04c-historias-control.md#hu-05-08), [HU-06-02](04c-historias-control.md#hu-06-02), [HU-06-04](04c-historias-control.md#hu-06-04), [HU-10-01](04d-historias-conexiones.md#hu-10-01), [HU-10-02](04d-historias-conexiones.md#hu-10-02).


## Backlog (sin sprint)

| ID | Historia | Prio. | PHU | Resp. | Estado | Commit/PR | Archivos | Evidencia |
|---|---|---|---|---|---|---|---|---|
| [HU-02-05](04b-historias-estado.md#hu-02-05) | Compactación solicitada por el propio modelo | Baja | 2 | B — Estado | Pendiente |  |  |  |
| [HU-02-07](04b-historias-estado.md#hu-02-07) | Archivo de instrucciones del proyecto | Baja | 2 | B — Estado | Pendiente |  |  |  |
| [HU-03-06](04b-historias-estado.md#hu-03-06) | Exportar una sesión a formato legible | Baja | 1 | B — Estado | Pendiente |  |  |  |
| [HU-07-06](04d-historias-conexiones.md#hu-07-06) | Respuesta en streaming | Baja | 2 | A — Núcleo | Pendiente |  |  |  |
| [HU-08-05](04d-historias-conexiones.md#hu-08-05) | Varios servidores por archivo y prefijos para evitar colisiones | Media | 3 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-08-06](04d-historias-conexiones.md#hu-08-06) | Transporte HTTP además de stdio | Baja | 2 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-09-07](04d-historias-conexiones.md#hu-09-07) | Subagentes en paralelo con agregación de resultados | Baja | 3 | A — Núcleo | Pendiente |  |  |  |
| [HU-10-03](04d-historias-conexiones.md#hu-10-03) | Convenciones de OpenTelemetry para IA generativa | Baja | 3 | B — Estado | Pendiente |  |  |  |
| [HU-IN-01](04d-historias-conexiones.md#hu-in-01) | Interfaz web sobre el mismo núcleo | Baja | 8 | A — Núcleo | Pendiente |  |  |  |
| [HU-IN-02](04d-historias-conexiones.md#hu-in-02) | Ejecución de comandos en entorno aislado | Baja | 5 | C — Control y conexiones | Pendiente |  |  |  |
| [HU-IN-03](04d-historias-conexiones.md#hu-in-03) | Comparación del orquestador propio con LangGraph | Baja | 5 | A — Núcleo | Pendiente |  |  |  |
| [HU-IN-04](04d-historias-conexiones.md#hu-in-04) | Panel de costos y consumo por sesión | Baja | 3 | B — Estado | Pendiente |  |  |  |

## Registro de cambios

| Fecha | Cambio | ID afectado | Quién |
|---|---|---|---|
| 2026-10-12 | Contexto dividido en `docs/00` a `docs/05` y `PROGRESO.md`; Python 3.12+ | — | — |
| 2026-10-13 | Alineado con `docs/archivo/CONTEXTO_HARNESS_v1.md`: enfoque Coding Harness, nueva épica E11 (HU-11-01 a HU-11-07), Sprint 3 rehecho, cinco historias pasan a Media | HU-11-xx, HU-00-07, HU-05-08, HU-07-04, HU-08-04, HU-09-05 | — |
| 2026-10-13 | Original archivado en `docs/archivo/CONTEXTO_HARNESS_v1.md` (solo histórico); se elimina el puntero `docs/CONTEXTO_HARNESS.md` | — | — |
| 2026-10-15 | Alineado con la actualización del contexto: relevo entre sesiones (§3.5), conjunto mínimo de herramientas (§3.6), HU-11-08 y criterios en JSON | HU-11-xx | — |
| 2026-10-17 | Alineado con el contexto v2.5 (`docs/archivo/CONTEXTO_HARNESS_v2.5.md`): cuarto sprint, historias divididas (HU-00-05, HU-02-06, HU-11-04, HU-11-08 pasan a `.1` y `.2`), 87 historias, contexto esencial y criterios en SQLite, AreaAutorizada, nueva sección 13 en `06-historial-planificacion.md` | HU-00-05.x, HU-02-06.x, HU-11-04.x, HU-11-08.x, Sprint 4 | — |
| 2026-10-17 | Constitución ratificada v1.0.0; directrices aplicadas a decisiones abiertas (PD-01..06, IA, herramientas); inicio de especificación para HU-00-01 | HU-00-01, PD-06, D-IA, D-ARCH | A — Núcleo |
| 2026-10-17 | **T001** (Sp1-01 / HU-00-01): Creado `pyproject.toml` (PEP 518/621, sin dependencias en núcleo, suite dev); `pip install -e .` verificado exitosamente (pass); T001 marcada; siguiente: T002 | HU-00-01, Sp1-01 | A — Núcleo |
| 2026-10-17 | **T002** (Sp1-01 / HU-00-01): Creado layout modular en `src/harness_agent/` (`core`, `adapters`, `cli`); importación verificada exitosamente (pass); T002 marcada; siguiente: T003 | HU-00-01, Sp1-01 | A — Núcleo |
| 2026-10-17 | **T003** (Sp1-01 / HU-00-01): Creada estructura modular de pruebas en `tests/` (`contracts`, `doubles`, `architecture`); importación e inspección pytest verificadas (pass); T003 marcada; siguiente: T004 | HU-00-01, Sp1-01 | A — Núcleo |
| 2026-10-17 | **T004** (Sp1-02 / HU-00-01): Definidas entidades canónicas inmutables en `src/harness_agent/core/entities.py` (`Role`, `ToolCall`, `ToolResult`, `TokenUsage`, `Message`); aserciones y mypy verificados (pass); T004 marcada; siguiente: T005 | HU-00-01, Sp1-02 | A — Núcleo |
| 2026-10-17 | **T005** (Sp1-02 / HU-00-01): Definido catálogo canónico de 17 eventos de bus (`EventType`, `Event` inmutable) en `src/harness_agent/core/events.py`; validación de 17 tipos y mypy verificados (pass); T005 marcada; siguiente: T006 | HU-00-01, Sp1-02 | A — Núcleo |
| 2026-10-17 | **T006–T015 completadas** (HU-00-01): Implementadas 14 interfaces abstractas, dobles en memoria (`tests/doubles/`), suite AC-01 de conformidad (`tests/contracts/test_contracts.py`), inspección AST AC-02 (`tests/architecture/test_core_boundaries.py`) y guía técnica (`docs/guia-contratos-desarrollo.md`); pytest 9/9 pass (0.09s), mypy 26 files pass; estado pasa a `En revisión` a la espera de Sp1-03 | HU-00-01, Sp1-01, Sp1-02, Sp1-03 | A — Núcleo |
| 2026-10-17 | Revisión de HU-00-01: nombres de métodos y atributos de los contratos unificados en inglés (`Tool.name/description/schema/risk`, se elimina el alias `Approver.pedir`); `docs/02` §4 actualizado; Python 3.12 en `pyproject.toml`; spec corregida (SC-005, estado, referencia a eventos). Siguen en español los nombres de interfaz (`AreaAutorizada`) y los valores de `EventType`: pendiente decidir | HU-00-01 | A — Núcleo |
| 2026-10-17 | Aprobación expresa del Product Owner registrada para HU-00-01 (AC-01 y AC-02 cumplidos, 9 pruebas en verde y Mypy sin errores). El estado se conserva en `Pendiente de aprobación técnica` a la espera de la ratificación de los integrantes A, B y C en Sp1-03 / T016 | HU-00-01, Sp1-03 | Product Owner |
| 2026-10-17 | **T001–T007 y T010 completadas** (HU-00-02): Implementados `requirements-dev.txt` con versiones fijadas (Sp1-06), `pyproject.toml` con baseline Python 3.11+, Ruff y cobertura pytest-cov (Sp1-05), y `.github/workflows/ci.yml` con matriz Linux/Windows y Py3.11/Py3.12 (Sp1-04/AC-02). Verificada Evidencia A: suite limpia al 100% (Ruff 0 errores, Mypy 0 errores en 26 archivos, Pytest 9/9 pass con 97% cobertura) y 3 pruebas negativas con código de salida 1 (AC-01). T008 (Evidencia B) y T009 (Evidencia C) quedan documentadas en quickstart.md como pendientes de push remoto y configuración de branch protection. Estado pasa a `En revisión` (Pendiente de validación remota) | HU-00-02, Sp1-04, Sp1-05, Sp1-06 | A — Núcleo |


## Decisiones abiertas

Decisiones de planificación (detalle en [06-historial-planificacion.md](06-historial-planificacion.md), sección 13.8). Actualizar la columna Estado al resolverlas.

| ID | Decisión | Decide | Estado |
|---|---|---|---|
| PD-01 | Cuarta semana (cierre máximo 14/11/2026). Reparto ampliado del Sprint 4 (11 PHU Alta extra) | Product Owner y equipo | Semana aprobada el 17/10/2026; reparto provisional pendiente de ratificación en Planning |
| PD-02 | Plan alterno si se rechaza PD-01; no bajar HU-07-05 mientras HU-00-05.1 dependa de ella | Product Owner | No aplicada |
| PD-03 | HU-08-04 vuelve a prioridad Alta (RF-8.5 Must) | Product Owner | Confirmada |
| PD-04 | Recalibrar velocidad y horas con lo terminado en el Sprint 1 | Product Owner y equipo | Obligatoria al cerrar el Sprint 1 (23/10/2026); no modificar estimaciones antes sin evidencia |
| PD-05 | Confirmar reasignaciones de responsables de v2.4/v2.5 | Equipo | Provisional según v2.5; confirmación definitiva por el equipo en Planning del Sprint 1 |
| PD-06 | Incluir HU-IN-02 (entorno aislado) para aislar de forma verificable el shell y los criterios | Product Owner | Pendiente decisión PO; R-21 no aceptado ni shell aislado garantizado; revisar antes de S2 |
| D-IA | Selección formal de proveedores (Claude/OpenAI/Gemini) y presupuesto de API | Product Owner y equipo | Pendiente; usar FakeProvider y contratos desacoplados; no declarar SPK-01 completado sin configuración |
| D-ARCH | Herramientas de archivos en Sprint 1 (leer, escribir, listar, buscar) | Equipo | Nativas en HU-01-03 para Sprint 1; independientes del shell de Sprint 2 |

Otras preguntas abiertas: ver «Preguntas abiertas» en [01-vision-y-decisiones.md](01-vision-y-decisiones.md). Al cerrar una, anotar aquí la respuesta y la fecha.

---

[← 06-historial-planificacion.md](06-historial-planificacion.md) · [Índice](00-indice.md)
