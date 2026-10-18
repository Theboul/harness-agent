# Plan, riesgos, épicas y sprints

> [← 02-arquitectura.md](02-arquitectura.md) · [Índice](00-indice.md) · [04a-historias-fundacion.md →](04a-historias-fundacion.md)  
> Secciones 6, 7, 8 y 9 del contexto original (cuatro sprints).  
> Ver también: [01-vision-y-decisiones.md](01-vision-y-decisiones.md) · [04a-historias-fundacion.md](04a-historias-fundacion.md) · [06-historial-planificacion.md](06-historial-planificacion.md) · [PROGRESO.md](PROGRESO.md)

## 6. Estrategia de pruebas y riesgos

| Tipo | Qué cubre | Cómo | Quién |
|---|---|---|---|
| Unitarias | Registro, validación, política de permisos, estimación de tokens, recorte. | pytest, sin red | Cada integrante |
| Integración con proveedor simulado | Bucle completo, aprobación, rechazo, compactación, reanudación. | FakeProvider con guion | Dueño del módulo |
| Fallos | Cierre forzado, proveedor caído, herramienta con excepción, MCP caído. | Inyección de fallos | A ([HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1); MCP en [HU-00-05.2](04a-historias-fundacion.md#hu-00-05.2)) |
| Contrato | Cada Provider real cumple la interfaz. | Pocas llamadas reales marcadas aparte | B |
| Aceptación | Guion de demostración de 10 a 15 minutos. | Manual con persona ajena | Todo el equipo |

Casi todo se prueba con el proveedor simulado (`FakeProvider`). Las llamadas reales se reservan para pruebas de contrato y la demostración.

Riesgos nuevos (se suman a R-1 a R-10 de la captura):

| Id | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| R-11 | Fallo del modelo de concurrencia (asyncio) que obligue a reescribir. | Media | Alto | [SPK-02](04a-historias-fundacion.md#spk-02) en el Sprint 1 antes de construir sobre él. |
| R-12 | El equipo usa Windows y Linux y el shell o las rutas fallan en uno. | Alta | Medio | Intérprete por plataforma e integración continua en Windows y Linux. |
| R-13 | Estimaciones demasiado optimistas por falta de datos reales: la velocidad de 39 PHU por sprint es una hipótesis. | Alta | Alto | Recalibrar puntos y horas tras Sprint 1. La cuarta semana está aprobada según v3, pero su capacidad no está demostrada; las historias Media solo entran si se completa lo obligatorio. |
| R-14 | Cuota de API agotada durante pruebas. | Media | Medio | FakeProvider para casi todas las pruebas; límite de consumo. |
| R-15 | Dependencias entre A, B y C bloquean en el Sprint 2. | Media | Alto | Contratos acordados en [HU-00-01](04a-historias-fundacion.md#hu-00-01) y dobles de prueba. |
| R-16 | Con el shell como herramienta general, un comando mal clasificado borra o publica algo. | Media | Alto | Lista de denegados inalterable, evaluación por partes, falla cerrada y aprobación siempre para push y merge ([HU-05-02](04c-historias-control.md#hu-05-02), [HU-11-02](04e-historias-coding-harness.md#hu-11-02)). El worktree por ticket ([HU-11-07](04e-historias-coding-harness.md#hu-11-07), hoy Should) sube de prioridad si el riesgo se materializa en las pruebas. |
| R-17 | El verificador y el agente comparten modelo y pueden coincidir en el error. | Media | Medio | El harness ejecuta las pruebas por su cuenta y no se apoya solo en el informe del verificador; los criterios llevan pasos concretos. |
| R-18 | PowerShell y bash difieren en comillas, rutas y comandos disponibles. | Alta | Medio | El prefijo informa el sistema y el intérprete; las pruebas del shell corren en integración continua en Windows y Linux ([HU-01-04](04a-historias-fundacion.md#hu-01-04)). |
| R-19 | La ruta crítica del Sprint 2 es corta: shell, política de comandos, pruebas y verificación deben encadenarse en una semana. | Alta | Alto | Se trabaja primero la ruta crítica ([HU-01-04](04a-historias-fundacion.md#hu-01-04), [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-05-02](04c-historias-control.md#hu-05-02), [HU-11-03](04e-historias-coding-harness.md#hu-11-03), [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1)); el shell sale con aprobación obligatoria hasta que llegue [HU-05-02](04c-historias-control.md#hu-05-02); el flujo se prueba pronto con un guion del FakeProvider y un ticket de ejemplo preparado. |
| R-20 | Aunque la cuarta semana fue aprobada en v3, el reparto de Sprint 4 creció de 8 PHU de MCP a 19 PHU Alta y requiere ratificación. Sprint 1 supera la disponibilidad media. | Alta | Alto | Ratificar las 11 PHU diferidas adicionales, responsables y margen; confirmar la fecha 14/11 en Planning. Sin capacidad, renegociar obligaciones con el PO sin degradarlas unilateralmente. |
| R-21 | Si shell y harness comparten permisos de sistema operativo, el agente podría modificar SQLite (la fuente de verdad) o los comandos/pruebas de aceptación; un JSON marcado como solo lectura no constituye aislamiento. | Media | Alto | La política deniega accesos identificables y el harness ignora la copia JSON. Esta mitigación es lógica, NO garantiza integridad frente al shell arbitrario. PD-06 exige separación de privilegios/sandbox operativo y pruebas que muestren acceso denegado; sin ello se declara riesgo residual. |
| R-22 | Carga actual v2.5 Alta: Sprint 1 = 104,5 h; Sprint 2 = 101 h; Sprint 3 = 94,5 h; Sprint 4 = 45,5 h. El equipo dispone de 96 h netas en escenario medio; no existe una reserva consistente del 20 %. | Alta | Alto | Recalibrar tras Sprint 1, verificar las horas reales por persona y proteger pruebas/integración. La cuarta semana aprobada no garantiza velocidad ni aprueba por sí sola el reparto ampliado. |

## 7. Épicas

| Id | Nombre | Descripción | Hist. | PHU |
|---|---|---|---|---|
| E0 | Fundaciones y calidad | Repositorio, interfaces acordadas, integración continua, proveedor simulado, pruebas y documentación. Hace posible el trabajo en paralelo. | 8 | 16 |
| E1 | Bucle y herramientas | Bucle razonar-actuar-observar, registro de herramientas con esquema JSON, herramientas base, bus de eventos y límites. | 9 | 23 |
| E2 | Gestión de contexto | Estimación de tokens, prefijo estable, recorte de salidas y compactación automática sin perder el objetivo. | 9 | 16 |
| E3 | Sesiones | Persistencia de cada evento en SQLite, listado y reanudación de sesiones, resistencia a cortes abruptos. | 6 | 12 |
| E4 | Memoria | Memoria persistente separada del historial, herramienta de memoria, memoria estructurada y protección de secretos. | 5 | 11 |
| E5 | Permisos y human-in-the-loop | Política denegar, preguntar, permitir que falla cerrada; aprobación con detalle; rechazo con motivo; auditoría. | 8 | 16 |
| E6 | Interacción con el usuario | CLI con eventos en tiempo real, herramienta para preguntar con opciones, comandos de control e interrupción. | 4 | 8 |
| E7 | Proveedores de modelo | Interfaz Provider sobre LiteLLM, dos proveedores, reintentos y conmutación por fallo. | 7 | 14 |
| E8 | Integración MCP | Cliente MCP por stdio, descubrimiento y traducción de herramientas, mismos permisos que las nativas, aislamiento de fallos. | 7 | 13 |
| E9 | Subagentes (reto) | Delegación en sesiones hijas con contexto aislado, herramientas restringidas y resultado estructurado. | 7 | 17 |
| E10 | Trazabilidad | Trazas estructuradas, auditoría y redacción de secretos en los registros. | 3 | 6 |
| E11 | Coding Harness: del ticket al Pull Request | Tarea con criterios verificables protegidos en SQLite (copia JSON de solo lectura), Git y pruebas por el shell, verificación de criterios por el harness, aprobación del diff, Pull Request y relevo entre sesiones con archivo de progreso. Es el flujo con el que se demuestra el proyecto. | 10 | 16 |
| EI | Innovación | Interfaz web, sandbox, comparación con LangGraph y panel de costos. Solo si el mínimo está cerrado. | 4 | 21 |

## 8. Plan de sprints

### Sprint 1 — Agente ejecutable en terminal: recibe una tarea, usa herramientas de archivos y deja todo guardado

- **Fechas:** 19 de octubre de 2026 al 23 de octubre de 2026
- **Estado:** Compromiso
- **Scrum Master:** A — Núcleo
- **Hito:** El agente recibe una instrucción en la terminal, la resuelve en varios turnos con herramientas de archivos y un modelo real, y la sesión queda guardada en SQLite. Las escrituras solo se permiten dentro de un área de trabajo autorizada y verificada; cualquier otra acción que pida aprobación se deniega con motivo, porque la interfaz de aprobación llega en el Sprint 2. Limitación asumida: no hay aprobación interactiva ni shell todavía.
- **Demostración:** Ejecutar una tarea de varios pasos dentro del área de trabajo autorizada, mostrar sus eventos y la sesión guardada, e intentar una escritura fuera del área para ver cómo se deniega.

**Criterios de demostración (con las historias que los respaldan):**

- Con el proveedor simulado, una tarea guionizada de tres pasos (leer, escribir y releer un archivo) dentro del área de trabajo autorizada termina igual en cada ejecución, también en la integración continua. (Respaldo: [HU-00-03](04a-historias-fundacion.md#hu-00-03), [HU-01-01](04a-historias-fundacion.md#hu-01-01), [HU-01-03](04a-historias-fundacion.md#hu-01-03), [HU-05-01](04c-historias-control.md#hu-05-01), [HU-00-02](04a-historias-fundacion.md#hu-00-02))
- Con un modelo real, el agente completa la misma tarea desde la CLI y muestra los eventos en tiempo real. (Respaldo: [HU-07-01](04d-historias-conexiones.md#hu-07-01), [HU-07-02](04d-historias-conexiones.md#hu-07-02), [HU-06-01](04c-historias-control.md#hu-06-01), [HU-01-05](04a-historias-fundacion.md#hu-01-05), [HU-00-04](04a-historias-fundacion.md#hu-00-04))
- Tras la ejecución existe una sesión en SQLite con todos sus eventos; si se mata el proceso a mitad, los eventos ya ocurridos siguen guardados. (Respaldo: [HU-03-01](04b-historias-estado.md#hu-03-01), [HU-03-02](04b-historias-estado.md#hu-03-02))
- Una escritura fuera del área (con «..», ruta absoluta o enlace simbólico) se rechaza antes de escribir, el modelo recibe el motivo y la decisión queda como evento. (Respaldo: [HU-01-03](04a-historias-fundacion.md#hu-01-03), [HU-05-01](04c-historias-control.md#hu-05-01), [HU-03-02](04b-historias-estado.md#hu-03-02))
- Una acción que resulta en «preguntar» se deniega con motivo, porque la aprobación interactiva llega en el Sprint 2; no hay ninguna regla que permita escribir en cualquier ruta. (Respaldo: [HU-05-01](04c-historias-control.md#hu-05-01))
- La integración continua pasa en Linux y en Windows. (Respaldo: [HU-00-02](04a-historias-fundacion.md#hu-00-02))

| Id | Historia | Prioridad | PHU | Responsable |
|---|---|---|---|---|
| [HU-00-01](04a-historias-fundacion.md#hu-00-01) | Esqueleto del repositorio e interfaces acordadas | Alta | 3 | A — Núcleo |
| [HU-00-02](04a-historias-fundacion.md#hu-00-02) | Integración continua con pruebas, tipado y formato | Alta | 2 | A — Núcleo |
| [HU-00-03](04a-historias-fundacion.md#hu-00-03) | Proveedor simulado para pruebas | Alta | 2 | B — Estado |
| [HU-00-04](04a-historias-fundacion.md#hu-00-04) | Configuración por archivo y variables de entorno | Alta | 1 | B — Estado |
| [HU-01-01](04a-historias-fundacion.md#hu-01-01) | Bucle agéntico básico | Alta | 5 | A — Núcleo |
| [HU-01-02](04a-historias-fundacion.md#hu-01-02) | Registro de herramientas con esquema y validación | Alta | 3 | C — Control y conexiones |
| [HU-01-03](04a-historias-fundacion.md#hu-01-03) | Herramientas de archivos: leer, escribir, listar y buscar | Alta | 4 | C — Control y conexiones |
| [HU-01-05](04a-historias-fundacion.md#hu-01-05) | Bus de eventos desacoplado de la interfaz | Alta | 2 | B — Estado |
| [HU-03-01](04b-historias-estado.md#hu-03-01) | Esquema SQLite y creación de sesión | Alta | 2 | B — Estado |
| [HU-03-02](04b-historias-estado.md#hu-03-02) | Persistir cada evento al ocurrir y tolerar cortes abruptos | Alta | 3 | B — Estado |
| [HU-05-01](04c-historias-control.md#hu-05-01) | Política denegar, preguntar, permitir que falla cerrada | Alta | 3 | C — Control y conexiones |
| [HU-06-01](04c-historias-control.md#hu-06-01) | CLI básica con eventos en tiempo real | Alta | 2 | C — Control y conexiones |
| [HU-07-01](04d-historias-conexiones.md#hu-07-01) | Interfaz Provider y formato interno de mensajes | Alta | 3 | A — Núcleo |
| [HU-07-02](04d-historias-conexiones.md#hu-07-02) | Adaptador LiteLLM para el primer proveedor | Alta | 2 | B — Estado |
| [SPK-01](04d-historias-conexiones.md#spk-01) | Spike: traducir herramientas entre OpenAI y Anthropic con LiteLLM | Alta | 1 | B — Estado |
| [SPK-02](04a-historias-fundacion.md#spk-02) | Spike: modelo asíncrono y cancelación de herramientas | Alta | 1 | A — Núcleo |

PHU Alta: 39 (velocidad hipotética del equipo: 39). Horas de tareas Alta: A 33,5 · B 34,5 · C 36,5; total 104,5 h (disponible neto por persona: 23,5 a 40,5 h; media del equipo 96 h).

### Sprint 2 — Primer flujo vertical del Coding Harness: del ticket a la verificación automática de criterios

- **Fechas:** 26 de octubre de 2026 al 30 de octubre de 2026
- **Estado:** PLAN BASE para Planning S2 (26–30/10, estimaciones preliminares)
- **Scrum Master:** B — Estado
- **Hito:** el agente recibe un ticket, modifica un repositorio de prueba, ejecuta pruebas y verifica criterios objetivos. Se mantienen permisos, aprobación/rechazo y la persistencia de eventos. [SPK-04](04d-historias-conexiones.md#spk-04) investiga la integración MCP de forma anticipada, pero no convierte MCP en condición de demostración del Sprint 2. Subagentes y archivo de progreso del ticket permanecen en Sprint 3.
- **Demostración:** crear un ticket de prueba, permitir al agente modificar el proyecto, ejecutar pruebas y mostrar criterios objetivos cumplidos/no cumplidos y semánticos pendientes. Validar un intento bloqueado de alterar los criterios por herramientas controladas; no afirmar aislamiento del shell arbitrario.

**Criterios de demostración (con las historias que los respaldan):**

- Dado un ticket de ejemplo con tres criterios (dos con comando de verificación y uno semántico), el agente modifica el proyecto de prueba, git status y git diff muestran el cambio, y la CLI presenta cada criterio como cumplido, no cumplido o pendiente de validación humana. (Respaldo: [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1), [HU-11-03](04e-historias-coding-harness.md#hu-11-03), [HU-11-02](04e-historias-coding-harness.md#hu-11-02), [HU-01-04](04a-historias-fundacion.md#hu-01-04))
- «Cumplido» solo aparece después de que el harness ejecuta el comando de verificación; un intento del agente de modificar los criterios (por las herramientas de archivos o por el shell) se bloquea y queda en los eventos. (Respaldo: [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1), [HU-05-01](04c-historias-control.md#hu-05-01), [HU-03-02](04b-historias-estado.md#hu-03-02))
- Un comando encadenado con una parte denegada se rechaza; uno no permitido pide aprobación al usuario y un rechazo con motivo vuelve al modelo. (Respaldo: [HU-05-02](04c-historias-control.md#hu-05-02), [HU-05-03](04c-historias-control.md#hu-05-03), [HU-05-04](04c-historias-control.md#hu-05-04), [HU-01-04](04a-historias-fundacion.md#hu-01-04))
- Las pruebas del proyecto de ejemplo se ejecutan con tiempo máximo, código de salida visible y salida recortada. (Respaldo: [HU-11-03](04e-historias-coding-harness.md#hu-11-03), [HU-01-04](04a-historias-fundacion.md#hu-01-04), [HU-02-02](04b-historias-estado.md#hu-02-02))
- La sesión conserva sus eventos confirmados tras terminar el proceso y puede reanudarse por su identificador. No se promete todavía archivo de progreso del ticket ni cancelación controlada. (Respaldo: [HU-03-02](04b-historias-estado.md#hu-03-02), [HU-03-04](04b-historias-estado.md#hu-03-04))
- Una sesión larga se compacta y el agente sigue conociendo el objetivo, las instrucciones, las reglas de la tarea, el identificador del ticket y los criterios, que no forman parte de lo resumido. (Respaldo: [HU-02-03](04b-historias-estado.md#hu-02-03), [HU-02-06.1](04b-historias-estado.md#hu-02-06.1), [HU-02-01](04b-historias-estado.md#hu-02-01), [HU-11-01](04e-historias-coding-harness.md#hu-11-01))

| Id | Historia | Prioridad | PHU | Responsable |
|---|---|---|---|---|
| [HU-01-04](04a-historias-fundacion.md#hu-01-04) | Herramienta de shell portable con tiempo límite | Alta | 3 | C — Control y conexiones |
| [HU-01-06](04a-historias-fundacion.md#hu-01-06) | Límites de turnos, tiempo y costo por sesión | Alta | 2 | A — Núcleo |
| [HU-02-01](04b-historias-estado.md#hu-02-01) | Estimación de tokens y prefijo estable | Alta | 2 | B — Estado |
| [HU-02-02](04b-historias-estado.md#hu-02-02) | Recorte de salidas largas de herramientas | Alta | 1 | C — Control y conexiones |
| [HU-02-03](04b-historias-estado.md#hu-02-03) | Compactación automática por umbral | Alta | 5 | B — Estado |
| [HU-02-06.1](04b-historias-estado.md#hu-02-06.1) | Contexto esencial persistente fuera del historial compactable | Alta | 1 | B — Estado |
| [HU-03-04](04b-historias-estado.md#hu-03-04) | Reanudar una sesión por identificador | Alta | 3 | A — Núcleo |
| [HU-05-02](04c-historias-control.md#hu-05-02) | Lista de denegados y análisis de comandos compuestos | Alta | 2 | C — Control y conexiones |
| [HU-05-03](04c-historias-control.md#hu-05-03) | Aprobación con detalle: una vez, toda la sesión o rechazar | Alta | 3 | C — Control y conexiones |
| [HU-05-04](04c-historias-control.md#hu-05-04) | Rechazo con motivo que vuelve al modelo | Alta | 1 | A — Núcleo |
| [SPK-04](04d-historias-conexiones.md#spk-04) | Spike: cliente MCP por stdio y servidor de demostración | Alta | 1 | C — Control y conexiones |
| [SPK-03](04b-historias-estado.md#spk-03) | Spike: compactación sin perder el objetivo | Alta | 1 | B — Estado |
| [HU-11-01](04e-historias-coding-harness.md#hu-11-01) | Tarea con criterios de aceptación protegidos en SQLite | Alta | 2 | A — Núcleo |
| [HU-11-02](04e-historias-coding-harness.md#hu-11-02) | Git mediante el shell con reglas de permisos por subcomando | Alta | 1 | B — Estado |
| [HU-11-03](04e-historias-coding-harness.md#hu-11-03) | Pruebas y lint mediante el shell con salida recortada | Alta | 1 | C — Control y conexiones |
| [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1) | Verificación automática de criterios objetivos: solo el harness marca passes | Alta | 2 | A — Núcleo |

PHU Alta: 31 (velocidad hipotética del equipo: 39). Horas de tareas Alta: A 31,5 · B 32,5 · C 37; total 101 h (disponible neto por persona: 23,5 a 40,5 h; media del equipo 96 h).

### Sprint 3 — Coding Harness completo: del ticket al Pull Request, con integración y calidad

- **Fechas:** 2 de noviembre de 2026 al 6 de noviembre de 2026
- **Estado:** PLAN BASE para Planning S3 (02–06/11)
- **Scrum Master:** C — Control y conexiones
- **Hito:** construir la delegación en subagentes y completar ticket → verificación independiente → aprobación del diff → commit → Pull Request. Incorporar puntos de control, reanudación del ticket, decisiones persistentes y conmutación de proveedor. El registro mínimo de auditoría queda redactado antes de persistir; las trazas exhaustivas de modelos/herramientas y memoria transversal se entregan en Sprint 4.
- **Demostración:** Recorrer el flujo completo en 10 a 15 minutos: ticket → agente → modificación → pruebas → verificación de criterios → revisión y aprobación del diff → commit → Pull Request.

**Criterios de demostración (con las historias que los respaldan):**

- Sobre un repositorio de demostración, el flujo completo termina con un Pull Request creado y su enlace visible. (Respaldo: [HU-11-06](04e-historias-coding-harness.md#hu-11-06), [HU-11-05](04e-historias-coding-harness.md#hu-11-05), [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1), [HU-11-02](04e-historias-coding-harness.md#hu-11-02))
- Un criterio semántico recibe el informe del subagente verificador y queda pendiente hasta que el usuario lo confirma; el subagente no puede editar archivos. (Respaldo: [HU-11-04.2](04e-historias-coding-harness.md#hu-11-04.2), [HU-09-06](04d-historias-conexiones.md#hu-09-06), [HU-09-02](04d-historias-conexiones.md#hu-09-02), [HU-09-03](04d-historias-conexiones.md#hu-09-03), [HU-09-01](04d-historias-conexiones.md#hu-09-01), [HU-11-05](04e-historias-coding-harness.md#hu-11-05))
- Un ticket terminado normalmente o interrumpido por cierre del proceso conserva el último punto de control completo; al reanudar, se leen el progreso, el log de git y la prueba básica. (Respaldo: [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1), [HU-11-08.2](04e-historias-coding-harness.md#hu-11-08.2), [HU-03-04](04b-historias-estado.md#hu-03-04), [HU-11-02](04e-historias-coding-harness.md#hu-11-02))
- Push y creación del Pull Request siempre piden aprobación; sin ella no sale nada del repositorio, y cada decisión queda en el registro de auditoría. (Respaldo: [HU-05-01](04c-historias-control.md#hu-05-01), [HU-05-03](04c-historias-control.md#hu-05-03), [HU-11-06](04e-historias-coding-harness.md#hu-11-06), [HU-05-05](04c-historias-control.md#hu-05-05))
- Un error elegible del proveedor principal causa conmutación sin bucle; se conserva un evento mínimo en la sesión y se informa en pantalla. Las trazas estructuradas completas y la memoria entre sesiones se implementan en Sprint 4. (Respaldo: [HU-07-03](04d-historias-conexiones.md#hu-07-03), [HU-07-05](04d-historias-conexiones.md#hu-07-05), [HU-03-02](04b-historias-estado.md#hu-03-02))
- Tras tres compactaciones seguidas el agente respeta el rechazo con motivo que el usuario dio antes y conoce el objetivo original. (Respaldo: [HU-02-06.2](04b-historias-estado.md#hu-02-06.2), [HU-02-06.1](04b-historias-estado.md#hu-02-06.1), [HU-05-04](04c-historias-control.md#hu-05-04))
- Las pruebas de fallos del núcleo pasan en CI y el registro mínimo de decisiones redacta argumentos sensibles antes de persistir; no se confunde con las trazas exhaustivas pospuestas. (Respaldo: [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1), [HU-05-05](04c-historias-control.md#hu-05-05))

| Id | Historia | Prioridad | PHU | Responsable |
|---|---|---|---|---|
| [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1) | Pruebas de integración y de fallos del núcleo | Alta | 2 | A — Núcleo |
| [HU-00-06](04a-historias-fundacion.md#hu-00-06) | README, guion de demostración y documento de arquitectura | Alta | 3 | B — Estado |
| [HU-00-07](04a-historias-fundacion.md#hu-00-07) | Cobertura mínima y prueba de instalación | Media | 2 | C — Control y conexiones |
| [HU-01-07](04a-historias-fundacion.md#hu-01-07) | Varias llamadas a herramientas en un mismo turno | Media | 2 | A — Núcleo |
| [HU-01-08](04a-historias-fundacion.md#hu-01-08) | Detección de llamadas repetidas | Media | 1 | A — Núcleo |
| [HU-02-04](04b-historias-estado.md#hu-02-04) | Comando para compactar manualmente | Media | 1 | B — Estado |
| [HU-02-06.2](04b-historias-estado.md#hu-02-06.2) | Decisiones acumuladas y continuidad tras varias compactaciones | Alta | 1 | B — Estado |
| [HU-03-05](04b-historias-estado.md#hu-03-05) | Consumo de tokens y costo estimado por sesión | Media | 2 | B — Estado |
| [HU-05-05](04c-historias-control.md#hu-05-05) | Registro de auditoría de decisiones | Alta | 2 | B — Estado |
| [HU-05-06](04c-historias-control.md#hu-05-06) | Reglas de permisos por archivo | Media | 2 | C — Control y conexiones |
| [HU-05-07](04c-historias-control.md#hu-05-07) | Modo de solo lectura | Media | 1 | C — Control y conexiones |
| [HU-06-03](04c-historias-control.md#hu-06-03) | Interrumpir la ejecución sin perder la sesión | Media | 2 | A — Núcleo |
| [HU-07-03](04d-historias-conexiones.md#hu-07-03) | Segundo proveedor y selección por configuración | Alta | 2 | A — Núcleo |
| [HU-07-04](04d-historias-conexiones.md#hu-07-04) | Reintentos con espera exponencial | Media | 1 | A — Núcleo |
| [HU-07-05](04d-historias-conexiones.md#hu-07-05) | Conmutación por fallo con umbral por modelo | Alta | 3 | A — Núcleo |
| [HU-09-01](04d-historias-conexiones.md#hu-09-01) | Delegar en un subagente con contexto limpio | Alta | 5 | B — Estado |
| [HU-09-02](04d-historias-conexiones.md#hu-09-02) | Instrucciones propias y herramientas restringidas por subagente | Alta | 2 | C — Control y conexiones |
| [HU-09-03](04d-historias-conexiones.md#hu-09-03) | Resultado estructurado en lugar de la transcripción | Alta | 2 | A — Núcleo |
| [HU-09-04](04d-historias-conexiones.md#hu-09-04) | Un solo nivel de anidamiento y límites por subagente | Alta | 2 | A — Núcleo |
| [HU-09-05](04d-historias-conexiones.md#hu-09-05) | Propagación explícita de errores del subagente | Media | 1 | A — Núcleo |
| [HU-09-06](04d-historias-conexiones.md#hu-09-06) | Subagente verificador y subagente explorador | Alta | 2 | C — Control y conexiones |
| [HU-11-04.2](04e-historias-coding-harness.md#hu-11-04.2) | Verificación independiente con el subagente verificador | Alta | 1 | C — Control y conexiones |
| [HU-11-05](04e-historias-coding-harness.md#hu-11-05) | Resumen de cambios y aprobación humana del diff | Alta | 2 | C — Control y conexiones |
| [HU-11-06](04e-historias-coding-harness.md#hu-11-06) | Pull Request tras la aprobación | Alta | 2 | C — Control y conexiones |
| [HU-11-07](04e-historias-coding-harness.md#hu-11-07) | Una sesión por ticket con un worktree propio | Media | 3 | C — Control y conexiones |
| [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) | Archivo de progreso del ticket con puntos de control | Alta | 1 | B — Estado |
| [HU-11-08.2](04e-historias-coding-harness.md#hu-11-08.2) | Rutina de arranque al reanudar un ticket | Alta | 1 | C — Control y conexiones |

PHU Alta: 33 (velocidad hipotética del equipo: 39). Horas de tareas Alta: A 30 · B 33 · C 31,5; total 94,5 h (disponible neto por persona: 23,5 a 40,5 h; media del equipo 96 h). Media (18 PHU, 34,5 h) solo si el mínimo está cerrado.

### Sprint 4 — MCP, memoria, trazabilidad y funciones complementarias

- **Fechas:** 9 de noviembre de 2026 al 13 de noviembre de 2026
- **Estado:** CUARTA SEMANA APROBADA según PD-01 del documento v3 (17/10/2026), con cierre máximo 14/11/2026
- **Scrum Master:** A — Núcleo (provisional, confirmar en Planning)
- **Hito:** Hito mínimo formalmente aprobado: integración MCP completa y prueba de fallos (8 PHU). Este plan consolidado asigna además otras 11 PHU Alta a Sprint 4 (memoria, trazas, listado y preguntas), heredadas del alcance original; su redistribución dentro de la cuarta semana requiere ratificación de PO y equipo en el Planning. No hay 31 PHU garantizados de holgura: la capacidad hipotética no es velocidad real.
- **Demostración:** MCP por stdio con aprobación y fallos aislados; memoria entre sesiones, listado, preguntas y trazas completas con redacción, si se ratifica el reparto adicional. Las funciones del Sprint 3 conservan su propia demostración independiente.

**Criterios de demostración (con las historias que los respaldan):**

- El agente conecta un servidor MCP por stdio, descubre y usa herramientas con los mismos contratos que las nativas. La prueba preliminar [SPK-04](04d-historias-conexiones.md#spk-04) ya se ejecutó en Sprint 2. (Respaldo: [SPK-04](04d-historias-conexiones.md#spk-04), [HU-08-01](04d-historias-conexiones.md#hu-08-01), [HU-08-02](04d-historias-conexiones.md#hu-08-02))
- Cada herramienta MCP queda bajo los controles de permisos y su denegación no rompe la sesión; un servidor caído afecta solo a sus propias herramientas. (Respaldo: [HU-08-03](04d-historias-conexiones.md#hu-08-03), [HU-08-04](04d-historias-conexiones.md#hu-08-04), [HU-00-05.2](04a-historias-fundacion.md#hu-00-05.2))
- La memoria persiste entre sesiones; las trazas redactan secretos y se pueden consultar; se pueden listar sesiones y preguntar con opciones. (Respaldo: [HU-04-01](04b-historias-estado.md#hu-04-01), [HU-04-02](04b-historias-estado.md#hu-04-02), [HU-10-01](04d-historias-conexiones.md#hu-10-01), [HU-10-02](04d-historias-conexiones.md#hu-10-02), [HU-03-03](04b-historias-estado.md#hu-03-03), [HU-06-02](04c-historias-control.md#hu-06-02))

| Id | Historia | Prioridad | PHU | Responsable | Reparto |
|---|---|---|---|---|---|
| [HU-00-05.2](04a-historias-fundacion.md#hu-00-05.2) | Prueba de aislamiento de fallos de un servidor MCP | Alta | 1 | A — Núcleo | Aprobado (MCP) |
| [HU-03-03](04b-historias-estado.md#hu-03-03) | Listar sesiones | Alta | 1 | B — Estado | Por ratificar |
| [HU-04-01](04b-historias-estado.md#hu-04-01) | Almacén de memoria separado del historial | Alta | 2 | B — Estado | Por ratificar |
| [HU-04-02](04b-historias-estado.md#hu-04-02) | Herramienta de memoria y carga al inicio | Alta | 3 | B — Estado | Por ratificar |
| [HU-04-03](04b-historias-estado.md#hu-04-03) | Memoria estructurada de la sesión | Media | 3 | B — Estado | Por ratificar |
| [HU-04-04](04b-historias-estado.md#hu-04-04) | Inspeccionar y editar la memoria | Media | 1 | C — Control y conexiones | Por ratificar |
| [HU-04-05](04b-historias-estado.md#hu-04-05) | No almacenar secretos en memoria | Media | 2 | C — Control y conexiones | Por ratificar |
| [HU-05-08](04c-historias-control.md#hu-05-08) | Contenido externo tratado como datos | Media | 2 | C — Control y conexiones | Por ratificar |
| [HU-06-02](04c-historias-control.md#hu-06-02) | Herramienta para preguntar al usuario con opciones | Alta | 2 | C — Control y conexiones | Por ratificar |
| [HU-06-04](04c-historias-control.md#hu-06-04) | Comandos de control de la sesión | Media | 2 | B — Estado | Por ratificar |
| [HU-08-01](04d-historias-conexiones.md#hu-08-01) | Conexión a un servidor MCP por stdio | Alta | 2 | C — Control y conexiones | Aprobado (MCP) |
| [HU-08-02](04d-historias-conexiones.md#hu-08-02) | Descubrir herramientas MCP y traducirlas al formato interno | Alta | 2 | C — Control y conexiones | Aprobado (MCP) |
| [HU-08-03](04d-historias-conexiones.md#hu-08-03) | Invocar herramientas MCP bajo la misma política de permisos | Alta | 2 | C — Control y conexiones | Aprobado (MCP) |
| [HU-08-04](04d-historias-conexiones.md#hu-08-04) | Aislar los fallos de un servidor MCP | Alta | 1 | C — Control y conexiones | Aprobado (MCP) |
| [HU-10-01](04d-historias-conexiones.md#hu-10-01) | Trazas estructuradas de cada llamada | Alta | 2 | B — Estado | Por ratificar |
| [HU-10-02](04d-historias-conexiones.md#hu-10-02) | Redacción de secretos en registros | Alta | 1 | B — Estado | Por ratificar |

PHU Alta: 19 (velocidad hipotética del equipo: 39). Horas de tareas Alta: A 4,5 · B 20 · C 21; total 45,5 h (disponible neto por persona: 23,5 a 40,5 h; media del equipo 96 h). Media (10 PHU, 15,5 h) solo si el mínimo está cerrado. Reparto ampliado por ratificar: 11 PHU Alta ([HU-03-03](04b-historias-estado.md#hu-03-03), [HU-04-01](04b-historias-estado.md#hu-04-01), [HU-04-02](04b-historias-estado.md#hu-04-02), [HU-06-02](04c-historias-control.md#hu-06-02), [HU-10-01](04d-historias-conexiones.md#hu-10-01), [HU-10-02](04d-historias-conexiones.md#hu-10-02)) y 10 PHU Media.

### Sin sprint (backlog)

| Id | Historia | Prioridad | PHU |
|---|---|---|---|
| [HU-02-05](04b-historias-estado.md#hu-02-05) | Compactación solicitada por el propio modelo | Baja | 2 |
| [HU-02-07](04b-historias-estado.md#hu-02-07) | Archivo de instrucciones del proyecto | Baja | 2 |
| [HU-03-06](04b-historias-estado.md#hu-03-06) | Exportar una sesión a formato legible | Baja | 1 |
| [HU-07-06](04d-historias-conexiones.md#hu-07-06) | Respuesta en streaming | Baja | 2 |
| [HU-08-05](04d-historias-conexiones.md#hu-08-05) | Varios servidores por archivo y prefijos para evitar colisiones | Media | 3 |
| [HU-08-06](04d-historias-conexiones.md#hu-08-06) | Transporte HTTP además de stdio | Baja | 2 |
| [HU-09-07](04d-historias-conexiones.md#hu-09-07) | Subagentes en paralelo con agregación de resultados | Baja | 3 |
| [HU-10-03](04d-historias-conexiones.md#hu-10-03) | Convenciones de OpenTelemetry para IA generativa | Baja | 3 |
| [HU-IN-01](04d-historias-conexiones.md#hu-in-01) | Interfaz web sobre el mismo núcleo | Baja | 8 |
| [HU-IN-02](04d-historias-conexiones.md#hu-in-02) | Ejecución de comandos en entorno aislado | Baja | 5 |
| [HU-IN-03](04d-historias-conexiones.md#hu-in-03) | Comparación del orquestador propio con LangGraph | Baja | 5 |
| [HU-IN-04](04d-historias-conexiones.md#hu-in-04) | Panel de costos y consumo por sesión | Baja | 3 |

## 9. Sprint Backlogs (tareas)

Estimación en horas por tarea, hecha tarea por tarea y no derivada de los PHU; el equipo la ajusta en el Planning. `(opc.)` = historia de prioridad Media, solo si el mínimo está cerrado. La semana del Sprint 4 fue aprobada por el Product Owner (PD-01); su reparto ampliado está por ratificar. Los códigos Sp#-nn son los de F5 del Word v2.5.

### Sprint 1

| Id | HU | Tarea | Horas | Resp. |
|---|---|---|---|---|
| Sp1-01 | [HU-00-01](04a-historias-fundacion.md#hu-00-01) | Crear la estructura de paquetes: núcleo, adaptadores, interfaz CLI y pruebas | 2 | A |
| Sp1-02 | [HU-00-01](04a-historias-fundacion.md#hu-00-01) | Escribir las firmas de Provider, Tool, ToolRegistry, PermissionPolicy, SessionStore, MemoryStore, ContextManager, McpClient y SubagentRunner | 2,5 | A |
| Sp1-03 | [HU-00-01](04a-historias-fundacion.md#hu-00-01) | Reunión de 1 hora para acordar el formato interno de mensajes y eventos | 1 | A |
| Sp1-04 | [HU-00-02](04a-historias-fundacion.md#hu-00-02) | Configurar el pipeline en el repositorio | 2,5 | A |
| Sp1-05 | [HU-00-02](04a-historias-fundacion.md#hu-00-02) | Añadir pytest con informe de cobertura, verificador de tipos y formateador | 2 | A |
| Sp1-06 | [HU-00-02](04a-historias-fundacion.md#hu-00-02) | Fijar versiones de dependencias en el archivo de requisitos | 1 | A |
| Sp1-07 | [HU-00-03](04a-historias-fundacion.md#hu-00-03) | Implementar FakeProvider que lee un guion | 3 | B |
| Sp1-08 | [HU-00-03](04a-historias-fundacion.md#hu-00-03) | Añadir modo de fallo configurable (cuota, tiempo agotado, indisponible) | 1,5 | B |
| Sp1-09 | [HU-00-04](04a-historias-fundacion.md#hu-00-04) | Definir el esquema de configuración y sus valores por defecto | 1,5 | B |
| Sp1-10 | [HU-00-04](04a-historias-fundacion.md#hu-00-04) | Cargar claves solo desde variables de entorno | 1 | B |
| Sp1-11 | [HU-00-04](04a-historias-fundacion.md#hu-00-04) | Añadir .gitignore y plantilla de ejemplo sin secretos | 0,5 | B |
| Sp1-12 | [HU-01-01](04a-historias-fundacion.md#hu-01-01) | Implementar un turno: llamar al proveedor, procesar la respuesta, ejecutar herramientas, devolver resultados | 7 | A |
| Sp1-13 | [HU-01-01](04a-historias-fundacion.md#hu-01-01) | Condición de parada y emisión de eventos | 2,5 | A |
| Sp1-14 | [HU-01-01](04a-historias-fundacion.md#hu-01-01) | Pruebas con el proveedor simulado | 4 | A |
| Sp1-15 | [HU-01-02](04a-historias-fundacion.md#hu-01-02) | Definir la clase base Tool con esquema | 3 | C |
| Sp1-16 | [HU-01-02](04a-historias-fundacion.md#hu-01-02) | Implementar el registro y la validación con el esquema | 2,5 | C |
| Sp1-17 | [HU-01-02](04a-historias-fundacion.md#hu-01-02) | Pruebas con argumentos mal formados | 2 | C |
| Sp1-18 | [HU-01-03](04a-historias-fundacion.md#hu-01-03) | Implementar leer, listar y buscar con error claro de ruta inexistente | 2,5 | C |
| Sp1-19 | [HU-01-03](04a-historias-fundacion.md#hu-01-03) | Componente AuthorizedArea: configuración del área y comprobación de contención sobre la ruta real | 2,5 | C |
| Sp1-20 | [HU-01-03](04a-historias-fundacion.md#hu-01-03) | Implementar escribir usando AuthorizedArea (normalización, enlaces simbólicos, unidades y rutas UNC) | 3,5 | C |
| Sp1-21 | [HU-01-03](04a-historias-fundacion.md#hu-01-03) | Declarar para cada herramienta su nivel de riesgo | 1 | C |
| Sp1-22 | [HU-01-03](04a-historias-fundacion.md#hu-01-03) | Pruebas de escape: «..», ruta absoluta, enlace simbólico y casos de Windows | 3,5 | C |
| Sp1-23 | [HU-01-05](04a-historias-fundacion.md#hu-01-05) | Definir los tipos de evento | 1 | B |
| Sp1-24 | [HU-01-05](04a-historias-fundacion.md#hu-01-05) | Implementar el emisor y la suscripción | 2,5 | B |
| Sp1-25 | [HU-01-05](04a-historias-fundacion.md#hu-01-05) | Prueba con un suscriptor de registro | 1,5 | B |
| Sp1-26 | [HU-03-01](04b-historias-estado.md#hu-03-01) | Diseñar las tablas de sesiones y eventos | 1,5 | B |
| Sp1-27 | [HU-03-01](04b-historias-estado.md#hu-03-01) | Implementar SessionStore con SQLite | 3 | B |
| Sp1-28 | [HU-03-01](04b-historias-estado.md#hu-03-01) | Pruebas de creación | 1,5 | B |
| Sp1-29 | [HU-03-02](04b-historias-estado.md#hu-03-02) | Suscribir el almacén al bus de eventos | 1,5 | B |
| Sp1-30 | [HU-03-02](04b-historias-estado.md#hu-03-02) | Escribir en transacciones por evento | 2,5 | B |
| Sp1-31 | [HU-03-02](04b-historias-estado.md#hu-03-02) | Prueba de interrupción forzada | 2,5 | B |
| Sp1-32 | [HU-05-01](04c-historias-control.md#hu-05-01) | Implementar PermissionPolicy con orden denegar, preguntar, permitir | 3,5 | C |
| Sp1-33 | [HU-05-01](04c-historias-control.md#hu-05-01) | Clasificar las herramientas por riesgo | 1 | C |
| Sp1-34 | [HU-05-01](04c-historias-control.md#hu-05-01) | Regla explícita «escribir solo dentro del área autorizada» usando AuthorizedArea | 2 | C |
| Sp1-35 | [HU-05-01](04c-historias-control.md#hu-05-01) | Resolución provisional de «preguntar» como denegación con motivo y registro de la decisión | 1,5 | C |
| Sp1-36 | [HU-05-01](04c-historias-control.md#hu-05-01) | Pruebas de reglas en conflicto, de lo no previsto y de rutas fuera del área | 3 | C |
| Sp1-37 | [HU-06-01](04c-historias-control.md#hu-06-01) | Suscribir la CLI al bus de eventos | 1,5 | C |
| Sp1-38 | [HU-06-01](04c-historias-control.md#hu-06-01) | Formato de mensajes y errores | 2 | C |
| Sp1-39 | [HU-06-01](04c-historias-control.md#hu-06-01) | Entrada de comandos | 1,5 | C |
| Sp1-40 | [HU-07-01](04d-historias-conexiones.md#hu-07-01) | Definir mensajes, bloques de herramienta y consumo | 2,5 | A |
| Sp1-41 | [HU-07-01](04d-historias-conexiones.md#hu-07-01) | Definir la interfaz chat(mensajes, herramientas) | 2 | A |
| Sp1-42 | [HU-07-01](04d-historias-conexiones.md#hu-07-01) | Pruebas de ida y vuelta | 1,5 | A |
| Sp1-43 | [HU-07-02](04d-historias-conexiones.md#hu-07-02) | Implementar el adaptador sobre LiteLLM | 3,5 | B |
| Sp1-44 | [HU-07-02](04d-historias-conexiones.md#hu-07-02) | Traducir llamadas y resultados de herramienta | 2,5 | B |
| Sp1-45 | [HU-07-02](04d-historias-conexiones.md#hu-07-02) | Prueba manual con una tarea de tres pasos | 1 | B |
| Sp1-46 | [SPK-01](04d-historias-conexiones.md#spk-01) | Probar una herramienta de ejemplo en los dos proveedores | 1,5 | B |
| Sp1-47 | [SPK-01](04d-historias-conexiones.md#spk-01) | Anotar las diferencias que afectan al formato interno | 1 | B |
| Sp1-48 | [SPK-02](04a-historias-fundacion.md#spk-02) | Prototipo de bucle con asyncio y cancelación | 2 | A |
| Sp1-49 | [SPK-02](04a-historias-fundacion.md#spk-02) | Decisión escrita sobre síncrono o asíncrono y sus consecuencias para MCP y subagentes | 1 | A |

### Sprint 2

| Id | HU | Tarea | Horas | Resp. |
|---|---|---|---|---|
| Sp2-01 | [HU-01-04](04a-historias-fundacion.md#hu-01-04) | Ejecutar subprocesos con tiempo máximo | 2 | C |
| Sp2-02 | [HU-01-04](04a-historias-fundacion.md#hu-01-04) | Interfaz Shell con una implementación para bash y otra para PowerShell | 3 | C |
| Sp2-03 | [HU-01-04](04a-historias-fundacion.md#hu-01-04) | Informar al modelo el sistema operativo y el intérprete en el prefijo | 1 | C |
| Sp2-04 | [HU-01-04](04a-historias-fundacion.md#hu-01-04) | Acotar y marcar la salida larga | 1,5 | C |
| Sp2-05 | [HU-01-04](04a-historias-fundacion.md#hu-01-04) | Pruebas del shell en integración continua con Windows y Linux | 3 | C |
| Sp2-06 | [HU-01-06](04a-historias-fundacion.md#hu-01-06) | Comprobar los límites antes de cada llamada al modelo | 2 | A |
| Sp2-07 | [HU-01-06](04a-historias-fundacion.md#hu-01-06) | Emitir el evento de límite alcanzado | 1 | A |
| Sp2-08 | [HU-01-06](04a-historias-fundacion.md#hu-01-06) | Pruebas por cada tipo de límite | 2 | A |
| Sp2-09 | [HU-02-01](04b-historias-estado.md#hu-02-01) | Estimar con una heurística y corregir con el consumo reportado | 3 | B |
| Sp2-10 | [HU-02-01](04b-historias-estado.md#hu-02-01) | Ensamblar prefijo estable primero y contenido variable después | 2,5 | B |
| Sp2-11 | [HU-02-01](04b-historias-estado.md#hu-02-01) | Pruebas de estabilidad del prefijo | 1,5 | B |
| Sp2-12 | [HU-02-02](04b-historias-estado.md#hu-02-02) | Aplicar el recorte en el registro de herramientas | 1 | C |
| Sp2-13 | [HU-02-02](04b-historias-estado.md#hu-02-02) | Prueba con salida de gran tamaño | 1,5 | C |
| Sp2-14 | [HU-02-03](04b-historias-estado.md#hu-02-03) | Disparar la compactación por umbral configurable por modelo | 3 | B |
| Sp2-15 | [HU-02-03](04b-historias-estado.md#hu-02-03) | Resumir lo antiguo con una llamada aparte | 4 | B |
| Sp2-16 | [HU-02-03](04b-historias-estado.md#hu-02-03) | Reconstruir el contexto: resumen más mensajes recientes | 3 | B |
| Sp2-17 | [HU-02-03](04b-historias-estado.md#hu-02-03) | Marcar los eventos compactados sin borrarlos | 2 | B |
| Sp2-18 | [HU-02-06.1](04b-historias-estado.md#hu-02-06.1) | Tabla contexto_esencial (clave, valor, origen) fuera de los eventos, con el objetivo, las instrucciones, las reglas y el ticket | 2 | B |
| Sp2-19 | [HU-02-06.1](04b-historias-estado.md#hu-02-06.1) | Inyectar el bloque en el prefijo en cada ensamblado y excluirlo de lo resumible | 1,5 | B |
| Sp2-20 | [HU-02-06.1](04b-historias-estado.md#hu-02-06.1) | Prueba de una compactación con el proveedor simulado | 1,5 | B |
| Sp2-21 | [HU-03-04](04b-historias-estado.md#hu-03-04) | Reconstruir el contexto desde los eventos | 3 | A |
| Sp2-22 | [HU-03-04](04b-historias-estado.md#hu-03-04) | Aplicar compactación si hace falta | 2 | A |
| Sp2-23 | [HU-03-04](04b-historias-estado.md#hu-03-04) | Comando de reanudar | 2 | A |
| Sp2-24 | [HU-05-02](04c-historias-control.md#hu-05-02) | Definir la lista base por plataforma | 1,5 | C |
| Sp2-25 | [HU-05-02](04c-historias-control.md#hu-05-02) | Aplicar la prioridad de denegación sobre cualquier aprobación | 1 | C |
| Sp2-26 | [HU-05-02](04c-historias-control.md#hu-05-02) | Separar comandos encadenados y evaluar cada parte | 3 | C |
| Sp2-27 | [HU-05-02](04c-historias-control.md#hu-05-02) | Preguntar ante lo que el analizador no entiende | 1 | C |
| Sp2-28 | [HU-05-02](04c-historias-control.md#hu-05-02) | Pruebas con encadenamientos de ejemplo | 2 | C |
| Sp2-29 | [HU-05-03](04c-historias-control.md#hu-05-03) | Evento de aprobación pedida con espera de respuesta | 2 | C |
| Sp2-30 | [HU-05-03](04c-historias-control.md#hu-05-03) | Presentación en la CLI | 3 | C |
| Sp2-31 | [HU-05-03](04c-historias-control.md#hu-05-03) | Alcance de la aprobación por herramienta y patrón | 2,5 | C |
| Sp2-32 | [HU-05-04](04c-historias-control.md#hu-05-04) | Devolver el rechazo como resultado | 1 | A |
| Sp2-33 | [HU-05-04](04c-historias-control.md#hu-05-04) | Prueba de replanteo con proveedor simulado | 1,5 | A |
| Sp2-34 | [SPK-03](04b-historias-estado.md#spk-03) | Preparar una sesión larga de prueba | 2 | B |
| Sp2-35 | [SPK-03](04b-historias-estado.md#spk-03) | Probar el resumen con el modelo | 1,5 | B |
| Sp2-36 | [SPK-03](04b-historias-estado.md#spk-03) | Anotar el diseño del bloque fijo de objetivo | 1 | B |
| Sp2-37 | [HU-11-01](04e-historias-coding-harness.md#hu-11-01) | Definir el formato de la tarea y su validación | 1 | A |
| Sp2-38 | [HU-11-01](04e-historias-coding-harness.md#hu-11-01) | Guardar los criterios en la tabla criterios de SQLite (fuente de verdad) y exportar una copia JSON de solo lectura | 2 | A |
| Sp2-39 | [HU-11-01](04e-historias-coding-harness.md#hu-11-01) | Proteger el directorio del harness (base de datos y exportación) con reglas de denegación en archivos y shell | 1,5 | A |
| Sp2-40 | [HU-11-01](04e-historias-coding-harness.md#hu-11-01) | Detectar cambios en la exportación mediante una huella, restaurarla y registrar el intento | 1,5 | A |
| Sp2-41 | [HU-11-01](04e-historias-coding-harness.md#hu-11-01) | Leer la tarea desde archivo y desde un issue con la CLI de GitHub | 1,5 | A |
| Sp2-42 | [HU-11-01](04e-historias-coding-harness.md#hu-11-01) | Crear la sesión con la tarea como objetivo | 1 | A |
| Sp2-43 | [HU-11-02](04e-historias-coding-harness.md#hu-11-02) | Reglas de permisos por subcomando de git | 1,5 | B |
| Sp2-44 | [HU-11-02](04e-historias-coding-harness.md#hu-11-02) | Instrucciones de uso de git en el prefijo (una rama por tarea, commits descriptivos) | 1 | B |
| Sp2-45 | [HU-11-02](04e-historias-coding-harness.md#hu-11-02) | Pruebas sobre un repositorio temporal | 1,5 | B |
| Sp2-46 | [HU-11-03](04e-historias-coding-harness.md#hu-11-03) | Leer los comandos de pruebas y de lint de la configuración de la tarea | 1,5 | C |
| Sp2-47 | [HU-11-03](04e-historias-coding-harness.md#hu-11-03) | Permitir en la política esos comandos exactos con tiempo máximo | 1 | C |
| Sp2-48 | [HU-11-03](04e-historias-coding-harness.md#hu-11-03) | Prueba con un proyecto de ejemplo | 1,5 | C |
| Sp2-49 | [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1) | Definir el campo de verificación del criterio (comando y condición esperada) | 1 | A |
| Sp2-50 | [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1) | Ejecutar los comandos de verificación desde el harness bajo la política de permisos | 2,5 | A |
| Sp2-51 | [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1) | Actualizar passes solo desde el harness y dejar pendientes los criterios sin verificación automática | 1,5 | A |
| Sp2-52 | [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1) | Mostrar en la CLI el estado de cada criterio | 1,5 | A |
| Sp2-53 | [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1) | Preparar el proyecto de prueba y el ticket de ejemplo con tres criterios | 2 | A |
| Sp2-54 | [SPK-04](04d-historias-conexiones.md#spk-04) | Probar el SDK de MCP con un servidor local | 2 | C |
| Sp2-55 | [SPK-04](04d-historias-conexiones.md#spk-04) | Elegir el servidor de la demostración | 1 | C |
| Sp2-56 | [SPK-04](04d-historias-conexiones.md#spk-04) | Anotar el resultado y ajustar las estimaciones de HU-08 | 1 | C |

### Sprint 3

| Id | HU | Tarea | Horas | Resp. |
|---|---|---|---|---|
| Sp3-01 | [HU-09-01](04d-historias-conexiones.md#hu-09-01) | Herramienta delegar con objetivo, contexto mínimo y formato de salida esperado | 4 | B |
| Sp3-02 | [HU-09-01](04d-historias-conexiones.md#hu-09-01) | Sesión hija con su propio historial | 4 | B |
| Sp3-03 | [HU-09-01](04d-historias-conexiones.md#hu-09-01) | Ejecutar el bucle del subagente y devolver el control | 5 | B |
| Sp3-04 | [HU-09-02](04d-historias-conexiones.md#hu-09-02) | Perfil de subagente: instrucciones y lista de herramientas permitidas | 2 | C |
| Sp3-05 | [HU-09-02](04d-historias-conexiones.md#hu-09-02) | Registro filtrado por perfil | 2 | C |
| Sp3-06 | [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) | Definir el formato del archivo de progreso del ticket | 1 | B |
| Sp3-07 | [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) | Escribir el progreso al terminar y un punto de control atómico al final de cada turno | 2 | B |
| Sp3-08 | [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) | Prueba con el proveedor simulado: final normal y proceso terminado a mitad del trabajo | 1,5 | B |
| Sp3-09 | [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1) | Prueba de interrupción forzada con reanudación | 2,5 | A |
| Sp3-10 | [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1) | Prueba de proveedor caído con conmutación y de herramienta que lanza excepción | 3 | A |
| Sp3-11 | [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1) | Medir el tiempo propio del harness por turno | 1,5 | A |
| Sp3-12 | [HU-00-06](04a-historias-fundacion.md#hu-00-06) | Redactar README con instalación, configuración y primeros pasos | 2,5 | B |
| Sp3-13 | [HU-00-06](04a-historias-fundacion.md#hu-00-06) | Escribir el guion de demostración de 10 a 15 minutos | 1,5 | B |
| Sp3-14 | [HU-00-06](04a-historias-fundacion.md#hu-00-06) | Documentar la arquitectura con los diagramas del análisis | 3 | B |
| Sp3-15 | [HU-00-07](04a-historias-fundacion.md#hu-00-07) (opc.) | Revisar la cobertura y cubrir los módulos que falten | 2 | C |
| Sp3-16 | [HU-00-07](04a-historias-fundacion.md#hu-00-07) (opc.) | Coordinar la prueba de instalación con una persona externa | 1 | C |
| Sp3-17 | [HU-00-07](04a-historias-fundacion.md#hu-00-07) (opc.) | Corregir lo detectado | 2 | C |
| Sp3-18 | [HU-01-07](04a-historias-fundacion.md#hu-01-07) (opc.) | Ejecutar las llamadas y asociar cada resultado a su identificador | 2 | A |
| Sp3-19 | [HU-01-07](04a-historias-fundacion.md#hu-01-07) (opc.) | Prueba con respuesta simulada de varias llamadas | 1,5 | A |
| Sp3-20 | [HU-01-08](04a-historias-fundacion.md#hu-01-08) (opc.) | Contar repeticiones por herramienta y argumentos | 1,5 | A |
| Sp3-21 | [HU-01-08](04a-historias-fundacion.md#hu-01-08) (opc.) | Prueba de interrupción | 1 | A |
| Sp3-22 | [HU-02-04](04b-historias-estado.md#hu-02-04) (opc.) | Añadir el comando a la CLI | 0,5 | B |
| Sp3-23 | [HU-02-04](04b-historias-estado.md#hu-02-04) (opc.) | Reutilizar la compactación existente | 1 | B |
| Sp3-24 | [HU-02-06.2](04b-historias-estado.md#hu-02-06.2) | Acumular cada decisión del usuario en contexto_esencial al producirse | 1,5 | B |
| Sp3-25 | [HU-02-06.2](04b-historias-estado.md#hu-02-06.2) | Incluir una sección de decisiones en el resumen | 1,5 | B |
| Sp3-26 | [HU-02-06.2](04b-historias-estado.md#hu-02-06.2) | Prueba de tres compactaciones seguidas | 2 | B |
| Sp3-27 | [HU-03-05](04b-historias-estado.md#hu-03-05) (opc.) | Acumular el consumo por llamada | 1,5 | B |
| Sp3-28 | [HU-03-05](04b-historias-estado.md#hu-03-05) (opc.) | Mostrar el resumen en el listado | 1 | B |
| Sp3-29 | [HU-05-05](04c-historias-control.md#hu-05-05) | Tabla de auditoría | 1,5 | B |
| Sp3-30 | [HU-05-05](04c-historias-control.md#hu-05-05) | Registrar decisiones y validar la redacción de argumentos sensibles antes de persistir (AC-01/02) | 2 | B |
| Sp3-31 | [HU-05-06](04c-historias-control.md#hu-05-06) (opc.) | Cargar reglas desde archivo | 1,5 | C |
| Sp3-32 | [HU-05-06](04c-historias-control.md#hu-05-06) (opc.) | Validar el formato de las reglas | 1,5 | C |
| Sp3-33 | [HU-05-07](04c-historias-control.md#hu-05-07) (opc.) | Perfil de política de solo lectura | 1,5 | C |
| Sp3-34 | [HU-06-03](04c-historias-control.md#hu-06-03) (opc.) | Cancelación cooperativa del turno | 2 | A |
| Sp3-35 | [HU-06-03](04c-historias-control.md#hu-06-03) (opc.) | Terminar el proceso de la herramienta en curso | 1,5 | A |
| Sp3-36 | [HU-06-03](04c-historias-control.md#hu-06-03) (opc.) | Escribir el punto de control del progreso al cancelar | 1 | A |
| Sp3-37 | [HU-07-03](04d-historias-conexiones.md#hu-07-03) | Configurar el segundo proveedor | 1,5 | A |
| Sp3-38 | [HU-07-03](04d-historias-conexiones.md#hu-07-03) | Verificar las diferencias en llamadas a herramienta | 1,5 | A |
| Sp3-39 | [HU-07-03](04d-historias-conexiones.md#hu-07-03) | Pruebas con ambos | 2 | A |
| Sp3-40 | [HU-07-04](04d-historias-conexiones.md#hu-07-04) (opc.) | Implementar la política de reintentos | 1,5 | A |
| Sp3-41 | [HU-07-04](04d-historias-conexiones.md#hu-07-04) (opc.) | Prueba con el proveedor simulado | 1 | A |
| Sp3-42 | [HU-07-05](04d-historias-conexiones.md#hu-07-05) | Clasificar los errores del proveedor en elegibles y no elegibles | 2 | A |
| Sp3-43 | [HU-07-05](04d-historias-conexiones.md#hu-07-05) | Lista ordenada de proveedores y registro de los ya probados en el turno | 2 | A |
| Sp3-44 | [HU-07-05](04d-historias-conexiones.md#hu-07-05) | Repetir turno con respaldo y persistir un evento mínimo de conmutación (sin trazas exhaustivas) | 2,5 | A |
| Sp3-45 | [HU-07-05](04d-historias-conexiones.md#hu-07-05) | Umbral de compactación por modelo | 1,5 | A |
| Sp3-46 | [HU-07-05](04d-historias-conexiones.md#hu-07-05) | Pruebas: error no elegible, ambos proveedores caídos y conmutación correcta | 3 | A |
| Sp3-47 | [HU-09-03](04d-historias-conexiones.md#hu-09-03) | Definir el esquema del resultado | 1 | A |
| Sp3-48 | [HU-09-03](04d-historias-conexiones.md#hu-09-03) | Validar el resultado antes de devolverlo | 1,5 | A |
| Sp3-49 | [HU-09-03](04d-historias-conexiones.md#hu-09-03) | Prueba con respuesta simulada | 1,5 | A |
| Sp3-50 | [HU-09-04](04d-historias-conexiones.md#hu-09-04) | Quitar la herramienta de delegación a los subagentes | 1 | A |
| Sp3-51 | [HU-09-04](04d-historias-conexiones.md#hu-09-04) | Aplicar los límites del bucle a la sesión hija | 2 | A |
| Sp3-52 | [HU-09-05](04d-historias-conexiones.md#hu-09-05) (opc.) | Resultado de error en el esquema | 1 | A |
| Sp3-53 | [HU-09-05](04d-historias-conexiones.md#hu-09-05) (opc.) | Prueba de fallo del subagente | 1 | A |
| Sp3-54 | [HU-09-06](04d-historias-conexiones.md#hu-09-06) | Definir los dos perfiles | 2 | C |
| Sp3-55 | [HU-09-06](04d-historias-conexiones.md#hu-09-06) | Formato del informe del verificador por criterio | 1,5 | C |
| Sp3-56 | [HU-09-06](04d-historias-conexiones.md#hu-09-06) | Pruebas por perfil | 2 | C |
| Sp3-57 | [HU-11-04.2](04e-historias-coding-harness.md#hu-11-04.2) | Ampliar el flujo de cierre para lanzar al verificador con los criterios pendientes | 2 | C |
| Sp3-58 | [HU-11-04.2](04e-historias-coding-harness.md#hu-11-04.2) | Registrar el informe del verificador como evidencia del criterio | 1,5 | C |
| Sp3-59 | [HU-11-04.2](04e-historias-coding-harness.md#hu-11-04.2) | Estado «pendiente de confirmación humana» | 1 | C |
| Sp3-60 | [HU-11-05](04e-historias-coding-harness.md#hu-11-05) | Generar el resumen de cambios a partir del diff | 2 | C |
| Sp3-61 | [HU-11-05](04e-historias-coding-harness.md#hu-11-05) | Mostrar el diff en la terminal | 1,5 | C |
| Sp3-62 | [HU-11-05](04e-historias-coding-harness.md#hu-11-05) | Conectar la decisión con la política de permisos | 2 | C |
| Sp3-63 | [HU-11-05](04e-historias-coding-harness.md#hu-11-05) | Confirmar o rechazar los criterios pendientes | 2 | C |
| Sp3-64 | [HU-11-06](04e-historias-coding-harness.md#hu-11-06) | Herramienta de push y de creación de Pull Request con la CLI de GitHub | 2,5 | C |
| Sp3-65 | [HU-11-06](04e-historias-coding-harness.md#hu-11-06) | Descripción generada con resumen y criterios | 1,5 | C |
| Sp3-66 | [HU-11-06](04e-historias-coding-harness.md#hu-11-06) | Prueba con un repositorio de demostración | 2 | C |
| Sp3-67 | [HU-11-07](04e-historias-coding-harness.md#hu-11-07) (opc.) | Crear y eliminar worktrees por tarea | 2 | C |
| Sp3-68 | [HU-11-07](04e-historias-coding-harness.md#hu-11-07) (opc.) | Asociar la sesión con su worktree | 1,5 | C |
| Sp3-69 | [HU-11-07](04e-historias-coding-harness.md#hu-11-07) (opc.) | Prueba con dos tareas en paralelo | 2,5 | C |
| Sp3-70 | [HU-11-08.2](04e-historias-coding-harness.md#hu-11-08.2) | Paso de arranque: leer progreso, log de git y prueba básica | 2 | C |
| Sp3-71 | [HU-11-08.2](04e-historias-coding-harness.md#hu-11-08.2) | Prueba de reanudar un ticket a medias con el proveedor simulado | 2 | C |

### Sprint 4

| Id | HU | Tarea | Horas | Resp. |
|---|---|---|---|---|
| Sp4-01 | [HU-03-03](04b-historias-estado.md#hu-03-03) | Consulta de listado | 1 | B |
| Sp4-02 | [HU-03-03](04b-historias-estado.md#hu-03-03) | Comando de la CLI | 1 | B |
| Sp4-03 | [HU-04-01](04b-historias-estado.md#hu-04-01) | Tabla de memorias en la misma base | 1,5 | B |
| Sp4-04 | [HU-04-01](04b-historias-estado.md#hu-04-01) | Implementar MemoryStore | 2 | B |
| Sp4-05 | [HU-04-02](04b-historias-estado.md#hu-04-02) | Herramienta de escritura en memoria | 2 | B |
| Sp4-06 | [HU-04-02](04b-historias-estado.md#hu-04-02) | Carga al iniciar con presupuesto de tokens | 3 | B |
| Sp4-07 | [HU-04-02](04b-historias-estado.md#hu-04-02) | Pruebas de recuperación entre sesiones | 2,5 | B |
| Sp4-08 | [HU-04-03](04b-historias-estado.md#hu-04-03) (opc.) | Definir el registro de decisiones, acciones y fallos | 1,5 | B |
| Sp4-09 | [HU-04-03](04b-historias-estado.md#hu-04-03) (opc.) | Alimentarlo desde el bucle | 2 | B |
| Sp4-10 | [HU-04-03](04b-historias-estado.md#hu-04-03) (opc.) | Incluirlo en el contexto reconstruido | 1,5 | B |
| Sp4-11 | [HU-04-04](04b-historias-estado.md#hu-04-04) (opc.) | Comando para listar y editar memoria | 1,5 | C |
| Sp4-12 | [HU-04-05](04b-historias-estado.md#hu-04-05) (opc.) | Detector de patrones comunes de claves y de variables de entorno cargadas | 1,5 | C |
| Sp4-13 | [HU-04-05](04b-historias-estado.md#hu-04-05) (opc.) | Prueba con claves de ejemplo | 1 | C |
| Sp4-14 | [HU-05-08](04c-historias-control.md#hu-05-08) (opc.) | Marcar el contenido externo en el contexto | 1,5 | C |
| Sp4-15 | [HU-05-08](04c-historias-control.md#hu-05-08) (opc.) | Pruebas de inyección con archivo y con servidor simulado | 2 | C |
| Sp4-16 | [HU-06-02](04c-historias-control.md#hu-06-02) | Definir la herramienta y su esquema | 1,5 | C |
| Sp4-17 | [HU-06-02](04c-historias-control.md#hu-06-02) | Presentar opciones en la CLI | 2 | C |
| Sp4-18 | [HU-06-02](04c-historias-control.md#hu-06-02) | Devolver la respuesta como resultado | 1,5 | C |
| Sp4-19 | [HU-06-04](04c-historias-control.md#hu-06-04) (opc.) | Analizador de comandos con prefijo | 1,5 | B |
| Sp4-20 | [HU-06-04](04c-historias-control.md#hu-06-04) (opc.) | Conectar cada comando con su módulo | 1,5 | B |
| Sp4-21 | [HU-10-01](04d-historias-conexiones.md#hu-10-01) | Suscribir un registrador de trazas al bus de eventos | 1,5 | B |
| Sp4-22 | [HU-10-01](04d-historias-conexiones.md#hu-10-01) | Escribir en formato estructurado consultable | 2 | B |
| Sp4-23 | [HU-10-01](04d-historias-conexiones.md#hu-10-01) | Comando o consulta para ver una traza | 1,5 | B |
| Sp4-24 | [HU-10-02](04d-historias-conexiones.md#hu-10-02) | Filtro de redacción en el registrador | 1 | B |
| Sp4-25 | [HU-10-02](04d-historias-conexiones.md#hu-10-02) | Prueba con claves de ejemplo | 1 | B |
| Sp4-26 | [HU-00-05.2](04a-historias-fundacion.md#hu-00-05.2) | Prueba de servidor MCP inexistente al arrancar la sesión | 2 | A |
| Sp4-27 | [HU-00-05.2](04a-historias-fundacion.md#hu-00-05.2) | Prueba de caída del servidor de demostración a mitad de sesión | 2,5 | A |
| Sp4-28 | [HU-08-01](04d-historias-conexiones.md#hu-08-01) | Iniciar el proceso del servidor y negociar | 3 | C |
| Sp4-29 | [HU-08-01](04d-historias-conexiones.md#hu-08-01) | Cerrar el proceso al terminar la sesión | 1,5 | C |
| Sp4-30 | [HU-08-02](04d-historias-conexiones.md#hu-08-02) | Traducir el esquema MCP al formato interno | 2 | C |
| Sp4-31 | [HU-08-02](04d-historias-conexiones.md#hu-08-02) | Registrar las herramientas | 1,5 | C |
| Sp4-32 | [HU-08-03](04d-historias-conexiones.md#hu-08-03) | Enrutar la invocación por la política | 2 | C |
| Sp4-33 | [HU-08-03](04d-historias-conexiones.md#hu-08-03) | Devolver el resultado al bucle | 1,5 | C |
| Sp4-34 | [HU-08-03](04d-historias-conexiones.md#hu-08-03) | Prueba con el servidor de la demostración | 2 | C |
| Sp4-35 | [HU-08-04](04d-historias-conexiones.md#hu-08-04) | Capturar fallos del servidor | 1,5 | C |
| Sp4-36 | [HU-08-04](04d-historias-conexiones.md#hu-08-04) | Deshabilitar solo sus herramientas | 1 | C |

---

[← 02-arquitectura.md](02-arquitectura.md) · [Índice](00-indice.md) · [04a-historias-fundacion.md →](04a-historias-fundacion.md)
