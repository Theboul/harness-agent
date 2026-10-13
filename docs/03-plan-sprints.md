# Plan, riesgos, épicas y sprints

> [← 02-arquitectura.md](02-arquitectura.md) · [Índice](00-indice.md) · [04a-historias-fundacion.md →](04a-historias-fundacion.md)  
> Secciones 6, 7, 8 y 9 del contexto original.  
> Ver también: [01-vision-y-decisiones.md](01-vision-y-decisiones.md) · [04a-historias-fundacion.md](04a-historias-fundacion.md) · [PROGRESO.md](PROGRESO.md)

## 6. Estrategia de pruebas y riesgos

| Tipo | Qué cubre | Cómo | Quién |
|---|---|---|---|
| Unitarias | Registro, validación, política de permisos, estimación de tokens, recorte. | pytest, sin red | Cada integrante |
| Integración con proveedor simulado | Bucle completo, aprobación, rechazo, compactación, reanudación. | FakeProvider con guion | Dueño del módulo |
| Fallos | Cierre forzado, proveedor caído, herramienta con excepción, MCP caído. | Inyección de fallos | A ([HU-00-05](04a-historias-fundacion.md#hu-00-05)) |
| Contrato | Cada Provider real cumple la interfaz. | Pocas llamadas reales marcadas aparte | B |
| Aceptación | Guion de demostración de 10 a 15 minutos. | Manual con persona ajena | Todo el equipo |

Casi todo se prueba con el proveedor simulado (`FakeProvider`). Las llamadas reales se reservan para pruebas de contrato y la demostración.

Riesgos nuevos (se suman a R-1 a R-10 de la captura):

| Id | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| R-11 | Fallo del modelo de concurrencia (asyncio) que obligue a reescribir. | Media | Alto | [SPK-02](04a-historias-fundacion.md#spk-02) en el Sprint 1 antes de construir sobre él. |
| R-12 | El equipo usa Windows y Linux y el shell o las rutas fallan en uno. | Alta | Medio | Intérprete por plataforma e integración continua en Windows y Linux. |
| R-13 | Estimaciones demasiado optimistas por falta de datos reales. | Alta | Medio | Recalibrar capacidad tras el Sprint 1; Should como colchón. |
| R-14 | Cuota de API agotada durante pruebas. | Media | Medio | FakeProvider para casi todas las pruebas; límite de consumo. |
| R-15 | Dependencias entre A, B y C bloquean en el Sprint 2. | Media | Alto | Contratos acordados en [HU-00-01](04a-historias-fundacion.md#hu-00-01) y dobles de prueba. |

## 7. Épicas

| Id | Nombre | Descripción | Hist. | PHU |
|---|---|---|---|---|
| E0 | Fundaciones y calidad | Repositorio, interfaces acordadas, integración continua, proveedor simulado, pruebas y documentación. Hace posible el trabajo en paralelo. | 7 | 16 |
| E1 | Bucle y herramientas | Bucle razonar-actuar-observar, registro de herramientas con esquema JSON, herramientas base, bus de eventos y límites. | 9 | 21 |
| E2 | Gestión de contexto | Estimación de tokens, prefijo estable, recorte de salidas y compactación automática sin perder el objetivo. | 8 | 16 |
| E3 | Sesiones | Persistencia de cada evento en SQLite, listado y reanudación de sesiones, resistencia a cortes abruptos. | 6 | 12 |
| E4 | Memoria | Memoria persistente separada del historial, herramienta de memoria, memoria estructurada y protección de secretos. | 5 | 11 |
| E5 | Permisos y human-in-the-loop | Política denegar, preguntar, permitir que falla cerrada; aprobación con detalle; rechazo con motivo; auditoría. | 8 | 15 |
| E6 | Interacción con el usuario | CLI con eventos en tiempo real, herramienta para preguntar con opciones, comandos de control e interrupción. | 4 | 8 |
| E7 | Proveedores de modelo | Interfaz Provider sobre LiteLLM, dos proveedores, reintentos y conmutación por fallo. | 7 | 14 |
| E8 | Integración MCP | Cliente MCP por stdio, descubrimiento y traducción de herramientas, mismos permisos que las nativas, aislamiento de fallos. | 7 | 13 |
| E9 | Subagentes (reto) | Delegación en sesiones hijas con contexto aislado, herramientas restringidas y resultado estructurado. | 7 | 17 |
| E10 | Trazabilidad | Trazas estructuradas, auditoría y redacción de secretos en los registros. | 3 | 6 |
| EI | Innovación | Interfaz web, sandbox, comparación con LangGraph y panel de costos. Solo si el mínimo está cerrado. | 4 | 21 |

## 8. Plan de sprints

### Sprint 1 — Tarea de tres pasos de principio a fin

- **Scrum Master:** A — Núcleo
- **Hito:** El agente lee y escribe archivos en varios turnos con un modelo real, la sesión queda guardada y la política de permisos clasifica cada acción.
- **Demostración:** Demostración de una tarea de tres pasos con un modelo real y con el proveedor simulado.

| Id | Historia | Prioridad | PHU | Responsable |
|---|---|---|---|---|
| [HU-00-01](04a-historias-fundacion.md#hu-00-01) | Esqueleto del repositorio e interfaces acordadas | Alta | 3 | A — Núcleo |
| [HU-00-02](04a-historias-fundacion.md#hu-00-02) | Integración continua con pruebas, tipado y formato | Alta | 2 | C — Control y conexiones |
| [HU-00-03](04a-historias-fundacion.md#hu-00-03) | Proveedor simulado para pruebas | Alta | 2 | B — Estado |
| [HU-00-04](04a-historias-fundacion.md#hu-00-04) | Configuración por archivo y variables de entorno | Alta | 1 | B — Estado |
| [HU-01-01](04a-historias-fundacion.md#hu-01-01) | Bucle agéntico básico | Alta | 5 | A — Núcleo |
| [HU-01-02](04a-historias-fundacion.md#hu-01-02) | Registro de herramientas con esquema y validación | Alta | 3 | C — Control y conexiones |
| [HU-01-03](04a-historias-fundacion.md#hu-01-03) | Herramientas de archivos: leer, escribir, listar y buscar | Alta | 3 | C — Control y conexiones |
| [HU-01-05](04a-historias-fundacion.md#hu-01-05) | Bus de eventos desacoplado de la interfaz | Alta | 2 | B — Estado |
| [HU-03-01](04b-historias-estado.md#hu-03-01) | Esquema SQLite y creación de sesión | Alta | 2 | B — Estado |
| [HU-03-02](04b-historias-estado.md#hu-03-02) | Persistir cada evento al ocurrir y tolerar cortes abruptos | Alta | 3 | B — Estado |
| [HU-05-01](04c-historias-control.md#hu-05-01) | Política denegar, preguntar, permitir que falla cerrada | Alta | 3 | C — Control y conexiones |
| [HU-06-01](04c-historias-control.md#hu-06-01) | CLI básica con eventos en tiempo real | Alta | 2 | C — Control y conexiones |
| [HU-07-01](04d-historias-conexiones.md#hu-07-01) | Interfaz Provider y formato interno de mensajes | Alta | 3 | A — Núcleo |
| [HU-07-02](04d-historias-conexiones.md#hu-07-02) | Adaptador LiteLLM para el primer proveedor | Alta | 2 | B — Estado |
| [SPK-01](04d-historias-conexiones.md#spk-01) | Spike: traducir herramientas entre OpenAI y Anthropic con LiteLLM | Alta | 1 | B — Estado |
| [SPK-02](04a-historias-fundacion.md#spk-02) | Spike: modelo asíncrono y cancelación de herramientas | Alta | 1 | A — Núcleo |

PHU obligatorios: A 12 · B 13 · C 13 (capacidad 13 por persona).

### Sprint 2 — Aprobar y reanudar

- **Scrum Master:** B — Estado
- **Hito:** Una acción de shell se detiene para aprobación, un rechazo con motivo hace replantear al agente, una sesión se reanuda tras cierre y el agente delega en un subagente básico.
- **Demostración:** Demostración de aprobación, rechazo, reanudación, compactación y delegación.

| Id | Historia | Prioridad | PHU | Responsable |
|---|---|---|---|---|
| [HU-01-04](04a-historias-fundacion.md#hu-01-04) | Herramienta de shell con tiempo límite | Alta | 2 | C — Control y conexiones |
| [HU-01-06](04a-historias-fundacion.md#hu-01-06) | Límites de turnos, tiempo y costo por sesión | Alta | 2 | A — Núcleo |
| [HU-02-01](04b-historias-estado.md#hu-02-01) | Estimación de tokens y prefijo estable | Alta | 2 | B — Estado |
| [HU-02-02](04b-historias-estado.md#hu-02-02) | Recorte de salidas largas de herramientas | Alta | 1 | C — Control y conexiones |
| [HU-02-03](04b-historias-estado.md#hu-02-03) | Compactación automática por umbral | Alta | 5 | B — Estado |
| [HU-03-03](04b-historias-estado.md#hu-03-03) | Listar sesiones | Alta | 1 | B — Estado |
| [HU-03-04](04b-historias-estado.md#hu-03-04) | Reanudar una sesión por identificador | Alta | 3 | B — Estado |
| [HU-05-02](04c-historias-control.md#hu-05-02) | Lista de denegados que ninguna configuración puede vaciar | Alta | 1 | C — Control y conexiones |
| [HU-05-03](04c-historias-control.md#hu-05-03) | Aprobación con detalle: una vez, toda la sesión o rechazar | Alta | 3 | C — Control y conexiones |
| [HU-05-04](04c-historias-control.md#hu-05-04) | Rechazo con motivo que vuelve al modelo | Alta | 1 | C — Control y conexiones |
| [HU-05-05](04c-historias-control.md#hu-05-05) | Registro de auditoría de decisiones | Alta | 2 | C — Control y conexiones |
| [HU-06-02](04c-historias-control.md#hu-06-02) | Herramienta para preguntar al usuario con opciones | Alta | 2 | C — Control y conexiones |
| [HU-06-04](04c-historias-control.md#hu-06-04) | Comandos de control de la sesión | Alta | 2 | B — Estado |
| [HU-07-03](04d-historias-conexiones.md#hu-07-03) | Segundo proveedor y selección por configuración | Alta | 2 | A — Núcleo |
| [SPK-04](04d-historias-conexiones.md#spk-04) | Spike: cliente MCP por stdio y servidor de demostración | Alta | 1 | C — Control y conexiones |
| [HU-09-01](04d-historias-conexiones.md#hu-09-01) | Delegar en un subagente con contexto limpio | Alta | 5 | A — Núcleo |
| [HU-09-02](04d-historias-conexiones.md#hu-09-02) | Instrucciones propias y herramientas restringidas por subagente | Alta | 2 | A — Núcleo |
| [HU-09-03](04d-historias-conexiones.md#hu-09-03) | Resultado estructurado en lugar de la transcripción | Alta | 2 | A — Núcleo |
| [SPK-03](04b-historias-estado.md#spk-03) | Spike: compactación sin perder el objetivo | Alta | 1 | B — Estado |

PHU obligatorios: A 13 · B 14 · C 13 (capacidad 13 por persona). B queda 1 por encima; si no cabe, partir [HU-06-04](04c-historias-control.md#hu-06-04).

### Sprint 3 — Subagente, MCP y cierre

- **Scrum Master:** C — Control y conexiones
- **Hito:** Una herramienta MCP corre bajo permisos, el sistema conmuta de proveedor al fallar uno, la memoria sobrevive entre sesiones y el repositorio queda documentado y probado.
- **Demostración:** Demostración completa siguiendo el guion de 10 a 15 minutos.

| Id | Historia | Prioridad | PHU | Responsable |
|---|---|---|---|---|
| [HU-00-05](04a-historias-fundacion.md#hu-00-05) | Pruebas de integración y de fallos | Alta | 3 | A — Núcleo |
| [HU-00-06](04a-historias-fundacion.md#hu-00-06) | README, guion de demostración y documento de arquitectura | Alta | 3 | B — Estado |
| [HU-00-07](04a-historias-fundacion.md#hu-00-07) | Cobertura mínima y prueba de instalación | Alta | 2 | C — Control y conexiones |
| [HU-01-07](04a-historias-fundacion.md#hu-01-07) | Varias llamadas a herramientas en un mismo turno | Media | 2 | A — Núcleo |
| [HU-01-08](04a-historias-fundacion.md#hu-01-08) | Detección de llamadas repetidas | Media | 1 | A — Núcleo |
| [HU-02-04](04b-historias-estado.md#hu-02-04) | Comando para compactar manualmente | Media | 1 | B — Estado |
| [HU-02-06](04b-historias-estado.md#hu-02-06) | Conservar objetivo, instrucciones y decisiones tras compactar | Alta | 2 | B — Estado |
| [HU-03-05](04b-historias-estado.md#hu-03-05) | Consumo de tokens y costo estimado por sesión | Media | 2 | B — Estado |
| [HU-04-01](04b-historias-estado.md#hu-04-01) | Almacén de memoria separado del historial | Alta | 2 | B — Estado |
| [HU-04-02](04b-historias-estado.md#hu-04-02) | Herramienta de memoria y carga al inicio | Alta | 3 | B — Estado |
| [HU-04-03](04b-historias-estado.md#hu-04-03) | Memoria estructurada de la sesión | Media | 3 | B — Estado |
| [HU-04-04](04b-historias-estado.md#hu-04-04) | Inspeccionar y editar la memoria | Media | 1 | C — Control y conexiones |
| [HU-04-05](04b-historias-estado.md#hu-04-05) | No almacenar secretos en memoria | Alta | 2 | C — Control y conexiones |
| [HU-05-06](04c-historias-control.md#hu-05-06) | Reglas de permisos por archivo | Media | 2 | C — Control y conexiones |
| [HU-05-07](04c-historias-control.md#hu-05-07) | Modo de solo lectura | Media | 1 | C — Control y conexiones |
| [HU-05-08](04c-historias-control.md#hu-05-08) | Contenido externo tratado como datos | Alta | 2 | C — Control y conexiones |
| [HU-06-03](04c-historias-control.md#hu-06-03) | Interrumpir la ejecución sin perder la sesión | Media | 2 | A — Núcleo |
| [HU-07-04](04d-historias-conexiones.md#hu-07-04) | Reintentos con espera exponencial | Alta | 1 | A — Núcleo |
| [HU-07-05](04d-historias-conexiones.md#hu-07-05) | Conmutación por fallo con umbral por modelo | Alta | 3 | A — Núcleo |
| [HU-08-01](04d-historias-conexiones.md#hu-08-01) | Conexión a un servidor MCP por stdio | Alta | 2 | C — Control y conexiones |
| [HU-08-02](04d-historias-conexiones.md#hu-08-02) | Descubrir herramientas MCP y traducirlas al formato interno | Alta | 2 | C — Control y conexiones |
| [HU-08-03](04d-historias-conexiones.md#hu-08-03) | Invocar herramientas MCP bajo la misma política de permisos | Alta | 2 | C — Control y conexiones |
| [HU-08-04](04d-historias-conexiones.md#hu-08-04) | Aislar los fallos de un servidor MCP | Alta | 1 | C — Control y conexiones |
| [HU-09-04](04d-historias-conexiones.md#hu-09-04) | Un solo nivel de anidamiento y límites por subagente | Alta | 2 | A — Núcleo |
| [HU-09-05](04d-historias-conexiones.md#hu-09-05) | Propagación explícita de errores del subagente | Alta | 1 | A — Núcleo |
| [HU-09-06](04d-historias-conexiones.md#hu-09-06) | Dos tipos de subagente: explorador y verificador | Media | 2 | A — Núcleo |
| [HU-10-01](04d-historias-conexiones.md#hu-10-01) | Trazas estructuradas de cada llamada | Alta | 2 | B — Estado |
| [HU-10-02](04d-historias-conexiones.md#hu-10-02) | Redacción de secretos en registros | Alta | 1 | B — Estado |

PHU obligatorios: A 10 · B 13 · C 13 (capacidad 13 por persona).

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

Estimación en horas: reparto inicial de los PHU (1 PHU ≈ 2,5 h) entre las tareas; el equipo la ajusta en el Planning. `(opc.)` = historia de prioridad Media, solo si el mínimo está cerrado.

### Sprint 1

| Id | HU | Tarea | Horas | Resp. |
|---|---|---|---|---|
| Sp1-01 | [HU-00-01](04a-historias-fundacion.md#hu-00-01) | Crear la estructura de paquetes: núcleo, adaptadores, interfaz CLI y pruebas | 2,5 | A |
| Sp1-02 | [HU-00-01](04a-historias-fundacion.md#hu-00-01) | Escribir las firmas de Provider, Tool, ToolRegistry, PermissionPolicy, SessionStore, MemoryStore, ContextManager, McpClient y SubagentRunner | 2,5 | A |
| Sp1-03 | [HU-00-01](04a-historias-fundacion.md#hu-00-01) | Reunión de 1 hora para acordar el formato interno de mensajes y eventos | 2,5 | A |
| Sp1-04 | [HU-00-02](04a-historias-fundacion.md#hu-00-02) | Configurar el pipeline en el repositorio | 1,5 | C |
| Sp1-05 | [HU-00-02](04a-historias-fundacion.md#hu-00-02) | Añadir pytest con informe de cobertura, verificador de tipos y formateador | 1,5 | C |
| Sp1-06 | [HU-00-02](04a-historias-fundacion.md#hu-00-02) | Fijar versiones de dependencias en el archivo de requisitos | 1,5 | C |
| Sp1-07 | [HU-00-03](04a-historias-fundacion.md#hu-00-03) | Implementar FakeProvider que lee un guion | 2,5 | B |
| Sp1-08 | [HU-00-03](04a-historias-fundacion.md#hu-00-03) | Añadir modo de fallo configurable (cuota, tiempo agotado, indisponible) | 2,5 | B |
| Sp1-09 | [HU-00-04](04a-historias-fundacion.md#hu-00-04) | Definir el esquema de configuración y sus valores por defecto | 1 | B |
| Sp1-10 | [HU-00-04](04a-historias-fundacion.md#hu-00-04) | Cargar claves solo desde variables de entorno | 1 | B |
| Sp1-11 | [HU-00-04](04a-historias-fundacion.md#hu-00-04) | Añadir .gitignore y plantilla de ejemplo sin secretos | 1 | B |
| Sp1-12 | [HU-01-01](04a-historias-fundacion.md#hu-01-01) | Implementar un turno: llamar al proveedor, procesar la respuesta, ejecutar herramientas, devolver resultados | 4 | A |
| Sp1-13 | [HU-01-01](04a-historias-fundacion.md#hu-01-01) | Condición de parada y emisión de eventos | 4 | A |
| Sp1-14 | [HU-01-01](04a-historias-fundacion.md#hu-01-01) | Pruebas con el proveedor simulado | 4 | A |
| Sp1-15 | [HU-01-02](04a-historias-fundacion.md#hu-01-02) | Definir la clase base Tool con esquema | 2,5 | C |
| Sp1-16 | [HU-01-02](04a-historias-fundacion.md#hu-01-02) | Implementar el registro y la validación con el esquema | 2,5 | C |
| Sp1-17 | [HU-01-02](04a-historias-fundacion.md#hu-01-02) | Pruebas con argumentos mal formados | 2,5 | C |
| Sp1-18 | [HU-01-03](04a-historias-fundacion.md#hu-01-03) | Implementar leer, escribir, listar y buscar | 2,5 | C |
| Sp1-19 | [HU-01-03](04a-historias-fundacion.md#hu-01-03) | Declarar para cada una su nivel de riesgo | 2,5 | C |
| Sp1-20 | [HU-01-03](04a-historias-fundacion.md#hu-01-03) | Pruebas unitarias de cada herramienta | 2,5 | C |
| Sp1-21 | [HU-01-05](04a-historias-fundacion.md#hu-01-05) | Definir los tipos de evento | 1,5 | B |
| Sp1-22 | [HU-01-05](04a-historias-fundacion.md#hu-01-05) | Implementar el emisor y la suscripción | 1,5 | B |
| Sp1-23 | [HU-01-05](04a-historias-fundacion.md#hu-01-05) | Prueba con un suscriptor de registro | 1,5 | B |
| Sp1-24 | [HU-03-01](04b-historias-estado.md#hu-03-01) | Diseñar las tablas de sesiones y eventos | 1,5 | B |
| Sp1-25 | [HU-03-01](04b-historias-estado.md#hu-03-01) | Implementar SessionStore con SQLite | 1,5 | B |
| Sp1-26 | [HU-03-01](04b-historias-estado.md#hu-03-01) | Pruebas de creación | 1,5 | B |
| Sp1-27 | [HU-03-02](04b-historias-estado.md#hu-03-02) | Suscribir el almacén al bus de eventos | 2,5 | B |
| Sp1-28 | [HU-03-02](04b-historias-estado.md#hu-03-02) | Escribir en transacciones por evento | 2,5 | B |
| Sp1-29 | [HU-03-02](04b-historias-estado.md#hu-03-02) | Prueba de interrupción forzada | 2,5 | B |
| Sp1-30 | [HU-05-01](04c-historias-control.md#hu-05-01) | Implementar PermissionPolicy con orden denegar, preguntar, permitir | 2,5 | C |
| Sp1-31 | [HU-05-01](04c-historias-control.md#hu-05-01) | Clasificar las herramientas por riesgo | 2,5 | C |
| Sp1-32 | [HU-05-01](04c-historias-control.md#hu-05-01) | Pruebas de reglas en conflicto y de lo no previsto | 2,5 | C |
| Sp1-33 | [HU-06-01](04c-historias-control.md#hu-06-01) | Suscribir la CLI al bus de eventos | 1,5 | C |
| Sp1-34 | [HU-06-01](04c-historias-control.md#hu-06-01) | Formato de mensajes y errores | 1,5 | C |
| Sp1-35 | [HU-06-01](04c-historias-control.md#hu-06-01) | Entrada de comandos | 1,5 | C |
| Sp1-36 | [HU-07-01](04d-historias-conexiones.md#hu-07-01) | Definir mensajes, bloques de herramienta y consumo | 2,5 | A |
| Sp1-37 | [HU-07-01](04d-historias-conexiones.md#hu-07-01) | Definir la interfaz chat(mensajes, herramientas) | 2,5 | A |
| Sp1-38 | [HU-07-01](04d-historias-conexiones.md#hu-07-01) | Pruebas de ida y vuelta | 2,5 | A |
| Sp1-39 | [HU-07-02](04d-historias-conexiones.md#hu-07-02) | Implementar el adaptador sobre LiteLLM | 1,5 | B |
| Sp1-40 | [HU-07-02](04d-historias-conexiones.md#hu-07-02) | Traducir llamadas y resultados de herramienta | 1,5 | B |
| Sp1-41 | [HU-07-02](04d-historias-conexiones.md#hu-07-02) | Prueba manual con una tarea de tres pasos | 1,5 | B |
| Sp1-42 | [SPK-01](04d-historias-conexiones.md#spk-01) | Probar una herramienta de ejemplo en los dos proveedores | 1 | B |
| Sp1-43 | [SPK-01](04d-historias-conexiones.md#spk-01) | Anotar las diferencias que afectan al formato interno | 1 | B |
| Sp1-44 | [SPK-02](04a-historias-fundacion.md#spk-02) | Prototipo de bucle con asyncio y cancelación | 1 | A |
| Sp1-45 | [SPK-02](04a-historias-fundacion.md#spk-02) | Decisión escrita sobre síncrono o asíncrono y sus consecuencias para MCP y subagentes | 1 | A |

### Sprint 2

| Id | HU | Tarea | Horas | Resp. |
|---|---|---|---|---|
| Sp2-01 | [HU-01-04](04a-historias-fundacion.md#hu-01-04) | Ejecutar subprocesos con tiempo máximo | 1,5 | C |
| Sp2-02 | [HU-01-04](04a-historias-fundacion.md#hu-01-04) | Seleccionar intérprete según plataforma | 1,5 | C |
| Sp2-03 | [HU-01-04](04a-historias-fundacion.md#hu-01-04) | Acotar y marcar la salida larga | 1,5 | C |
| Sp2-04 | [HU-01-06](04a-historias-fundacion.md#hu-01-06) | Comprobar los límites antes de cada llamada al modelo | 1,5 | A |
| Sp2-05 | [HU-01-06](04a-historias-fundacion.md#hu-01-06) | Emitir el evento de límite alcanzado | 1,5 | A |
| Sp2-06 | [HU-01-06](04a-historias-fundacion.md#hu-01-06) | Pruebas por cada tipo de límite | 1,5 | A |
| Sp2-07 | [HU-02-01](04b-historias-estado.md#hu-02-01) | Estimar con una heurística y corregir con el consumo reportado | 1,5 | B |
| Sp2-08 | [HU-02-01](04b-historias-estado.md#hu-02-01) | Ensamblar prefijo estable primero y contenido variable después | 1,5 | B |
| Sp2-09 | [HU-02-01](04b-historias-estado.md#hu-02-01) | Pruebas de estabilidad del prefijo | 1,5 | B |
| Sp2-10 | [HU-02-02](04b-historias-estado.md#hu-02-02) | Aplicar el recorte en el registro de herramientas | 1 | C |
| Sp2-11 | [HU-02-02](04b-historias-estado.md#hu-02-02) | Prueba con salida de gran tamaño | 1 | C |
| Sp2-12 | [HU-02-03](04b-historias-estado.md#hu-02-03) | Disparar la compactación por umbral configurable por modelo | 3 | B |
| Sp2-13 | [HU-02-03](04b-historias-estado.md#hu-02-03) | Resumir lo antiguo con una llamada aparte | 3 | B |
| Sp2-14 | [HU-02-03](04b-historias-estado.md#hu-02-03) | Reconstruir el contexto: resumen más mensajes recientes | 3 | B |
| Sp2-15 | [HU-02-03](04b-historias-estado.md#hu-02-03) | Marcar los eventos compactados sin borrarlos | 3 | B |
| Sp2-16 | [HU-03-03](04b-historias-estado.md#hu-03-03) | Consulta de listado | 1 | B |
| Sp2-17 | [HU-03-03](04b-historias-estado.md#hu-03-03) | Comando de la CLI | 1 | B |
| Sp2-18 | [HU-03-04](04b-historias-estado.md#hu-03-04) | Reconstruir el contexto desde los eventos | 2,5 | B |
| Sp2-19 | [HU-03-04](04b-historias-estado.md#hu-03-04) | Aplicar compactación si hace falta | 2,5 | B |
| Sp2-20 | [HU-03-04](04b-historias-estado.md#hu-03-04) | Comando de reanudar | 2,5 | B |
| Sp2-21 | [HU-05-02](04c-historias-control.md#hu-05-02) | Definir la lista base por plataforma | 1 | C |
| Sp2-22 | [HU-05-02](04c-historias-control.md#hu-05-02) | Aplicar la prioridad de denegación sobre cualquier aprobación | 1 | C |
| Sp2-23 | [HU-05-03](04c-historias-control.md#hu-05-03) | Evento de aprobación pedida con espera de respuesta | 2,5 | C |
| Sp2-24 | [HU-05-03](04c-historias-control.md#hu-05-03) | Presentación en la CLI | 2,5 | C |
| Sp2-25 | [HU-05-03](04c-historias-control.md#hu-05-03) | Alcance de la aprobación por herramienta y patrón | 2,5 | C |
| Sp2-26 | [HU-05-04](04c-historias-control.md#hu-05-04) | Devolver el rechazo como resultado | 1 | C |
| Sp2-27 | [HU-05-04](04c-historias-control.md#hu-05-04) | Prueba de replanteo con proveedor simulado | 1 | C |
| Sp2-28 | [HU-05-05](04c-historias-control.md#hu-05-05) | Tabla de auditoría | 2,5 | C |
| Sp2-29 | [HU-05-05](04c-historias-control.md#hu-05-05) | Registrar cada decisión de la política | 2,5 | C |
| Sp2-30 | [HU-06-02](04c-historias-control.md#hu-06-02) | Definir la herramienta y su esquema | 1,5 | C |
| Sp2-31 | [HU-06-02](04c-historias-control.md#hu-06-02) | Presentar opciones en la CLI | 1,5 | C |
| Sp2-32 | [HU-06-02](04c-historias-control.md#hu-06-02) | Devolver la respuesta como resultado | 1,5 | C |
| Sp2-33 | [HU-06-04](04c-historias-control.md#hu-06-04) | Analizador de comandos con prefijo | 2,5 | B |
| Sp2-34 | [HU-06-04](04c-historias-control.md#hu-06-04) | Conectar cada comando con su módulo | 2,5 | B |
| Sp2-35 | [HU-07-03](04d-historias-conexiones.md#hu-07-03) | Configurar el segundo proveedor | 1,5 | A |
| Sp2-36 | [HU-07-03](04d-historias-conexiones.md#hu-07-03) | Verificar las diferencias en llamadas a herramienta | 1,5 | A |
| Sp2-37 | [HU-07-03](04d-historias-conexiones.md#hu-07-03) | Pruebas con ambos | 1,5 | A |
| Sp2-38 | [SPK-04](04d-historias-conexiones.md#spk-04) | Probar el SDK de MCP con un servidor local | 1 | C |
| Sp2-39 | [SPK-04](04d-historias-conexiones.md#spk-04) | Elegir el servidor de la demostración | 1 | C |
| Sp2-40 | [SPK-04](04d-historias-conexiones.md#spk-04) | Anotar el resultado y ajustar las estimaciones de HU-08 | 1 | C |
| Sp2-41 | [HU-09-01](04d-historias-conexiones.md#hu-09-01) | Herramienta delegar con objetivo, contexto mínimo y formato de salida esperado | 4 | A |
| Sp2-42 | [HU-09-01](04d-historias-conexiones.md#hu-09-01) | Sesión hija con su propio historial | 4 | A |
| Sp2-43 | [HU-09-01](04d-historias-conexiones.md#hu-09-01) | Ejecutar el bucle del subagente y devolver el control | 4 | A |
| Sp2-44 | [HU-09-02](04d-historias-conexiones.md#hu-09-02) | Perfil de subagente: instrucciones y lista de herramientas permitidas | 2,5 | A |
| Sp2-45 | [HU-09-02](04d-historias-conexiones.md#hu-09-02) | Registro filtrado por perfil | 2,5 | A |
| Sp2-46 | [HU-09-03](04d-historias-conexiones.md#hu-09-03) | Definir el esquema del resultado | 1,5 | A |
| Sp2-47 | [HU-09-03](04d-historias-conexiones.md#hu-09-03) | Validar el resultado antes de devolverlo | 1,5 | A |
| Sp2-48 | [HU-09-03](04d-historias-conexiones.md#hu-09-03) | Prueba con respuesta simulada | 1,5 | A |
| Sp2-49 | [SPK-03](04b-historias-estado.md#spk-03) | Preparar una sesión larga de prueba | 1 | B |
| Sp2-50 | [SPK-03](04b-historias-estado.md#spk-03) | Probar el resumen con el modelo | 1 | B |
| Sp2-51 | [SPK-03](04b-historias-estado.md#spk-03) | Anotar el diseño del bloque fijo de objetivo | 1 | B |

### Sprint 3

| Id | HU | Tarea | Horas | Resp. |
|---|---|---|---|---|
| Sp3-01 | [HU-00-05](04a-historias-fundacion.md#hu-00-05) | Prueba de interrupción forzada con reanudación | 2 | A |
| Sp3-02 | [HU-00-05](04a-historias-fundacion.md#hu-00-05) | Prueba de proveedor caído con conmutación | 2 | A |
| Sp3-03 | [HU-00-05](04a-historias-fundacion.md#hu-00-05) | Prueba de herramienta que lanza excepción | 2 | A |
| Sp3-04 | [HU-00-05](04a-historias-fundacion.md#hu-00-05) | Medir el tiempo propio del harness por turno | 2 | A |
| Sp3-05 | [HU-00-06](04a-historias-fundacion.md#hu-00-06) | Redactar README con instalación, configuración y primeros pasos | 2,5 | B |
| Sp3-06 | [HU-00-06](04a-historias-fundacion.md#hu-00-06) | Escribir el guion de demostración de 10 a 15 minutos | 2,5 | B |
| Sp3-07 | [HU-00-06](04a-historias-fundacion.md#hu-00-06) | Documentar la arquitectura con los diagramas del análisis | 2,5 | B |
| Sp3-08 | [HU-00-07](04a-historias-fundacion.md#hu-00-07) | Revisar la cobertura y cubrir los módulos que falten | 1,5 | C |
| Sp3-09 | [HU-00-07](04a-historias-fundacion.md#hu-00-07) | Coordinar la prueba de instalación con una persona externa | 1,5 | C |
| Sp3-10 | [HU-00-07](04a-historias-fundacion.md#hu-00-07) | Corregir lo detectado | 1,5 | C |
| Sp3-11 | [HU-01-07](04a-historias-fundacion.md#hu-01-07) (opc.) | Ejecutar las llamadas y asociar cada resultado a su identificador | 2,5 | A |
| Sp3-12 | [HU-01-07](04a-historias-fundacion.md#hu-01-07) (opc.) | Prueba con respuesta simulada de varias llamadas | 2,5 | A |
| Sp3-13 | [HU-01-08](04a-historias-fundacion.md#hu-01-08) (opc.) | Contar repeticiones por herramienta y argumentos | 1 | A |
| Sp3-14 | [HU-01-08](04a-historias-fundacion.md#hu-01-08) (opc.) | Prueba de interrupción | 1 | A |
| Sp3-15 | [HU-02-04](04b-historias-estado.md#hu-02-04) (opc.) | Añadir el comando a la CLI | 1 | B |
| Sp3-16 | [HU-02-04](04b-historias-estado.md#hu-02-04) (opc.) | Reutilizar la compactación existente | 1 | B |
| Sp3-17 | [HU-02-06](04b-historias-estado.md#hu-02-06) | Guardar el objetivo y las decisiones en un bloque fuera del historial compactable | 1,5 | B |
| Sp3-18 | [HU-02-06](04b-historias-estado.md#hu-02-06) | Incluir una sección de decisiones en el resumen | 1,5 | B |
| Sp3-19 | [HU-02-06](04b-historias-estado.md#hu-02-06) | Prueba de tres compactaciones seguidas | 1,5 | B |
| Sp3-20 | [HU-03-05](04b-historias-estado.md#hu-03-05) (opc.) | Acumular el consumo por llamada | 2,5 | B |
| Sp3-21 | [HU-03-05](04b-historias-estado.md#hu-03-05) (opc.) | Mostrar el resumen en el listado | 2,5 | B |
| Sp3-22 | [HU-04-01](04b-historias-estado.md#hu-04-01) | Tabla de memorias en la misma base | 2,5 | B |
| Sp3-23 | [HU-04-01](04b-historias-estado.md#hu-04-01) | Implementar MemoryStore | 2,5 | B |
| Sp3-24 | [HU-04-02](04b-historias-estado.md#hu-04-02) | Herramienta de escritura en memoria | 2,5 | B |
| Sp3-25 | [HU-04-02](04b-historias-estado.md#hu-04-02) | Carga al iniciar con presupuesto de tokens | 2,5 | B |
| Sp3-26 | [HU-04-02](04b-historias-estado.md#hu-04-02) | Pruebas de recuperación entre sesiones | 2,5 | B |
| Sp3-27 | [HU-04-03](04b-historias-estado.md#hu-04-03) (opc.) | Definir el registro de decisiones, acciones y fallos | 2,5 | B |
| Sp3-28 | [HU-04-03](04b-historias-estado.md#hu-04-03) (opc.) | Alimentarlo desde el bucle | 2,5 | B |
| Sp3-29 | [HU-04-03](04b-historias-estado.md#hu-04-03) (opc.) | Incluirlo en el contexto reconstruido | 2,5 | B |
| Sp3-30 | [HU-04-04](04b-historias-estado.md#hu-04-04) (opc.) | Comando para listar y editar memoria | 2,5 | C |
| Sp3-31 | [HU-04-05](04b-historias-estado.md#hu-04-05) | Detector de patrones comunes de claves y de variables de entorno cargadas | 2,5 | C |
| Sp3-32 | [HU-04-05](04b-historias-estado.md#hu-04-05) | Prueba con claves de ejemplo | 2,5 | C |
| Sp3-33 | [HU-05-06](04c-historias-control.md#hu-05-06) (opc.) | Cargar reglas desde archivo | 2,5 | C |
| Sp3-34 | [HU-05-06](04c-historias-control.md#hu-05-06) (opc.) | Validar el formato de las reglas | 2,5 | C |
| Sp3-35 | [HU-05-07](04c-historias-control.md#hu-05-07) (opc.) | Perfil de política de solo lectura | 2,5 | C |
| Sp3-36 | [HU-05-08](04c-historias-control.md#hu-05-08) | Marcar el contenido externo en el contexto | 2,5 | C |
| Sp3-37 | [HU-05-08](04c-historias-control.md#hu-05-08) | Pruebas de inyección con archivo y con servidor simulado | 2,5 | C |
| Sp3-38 | [HU-06-03](04c-historias-control.md#hu-06-03) (opc.) | Cancelación cooperativa del turno | 2,5 | A |
| Sp3-39 | [HU-06-03](04c-historias-control.md#hu-06-03) (opc.) | Terminar el proceso de la herramienta en curso | 2,5 | A |
| Sp3-40 | [HU-07-04](04d-historias-conexiones.md#hu-07-04) | Implementar la política de reintentos | 1 | A |
| Sp3-41 | [HU-07-04](04d-historias-conexiones.md#hu-07-04) | Prueba con el proveedor simulado | 1 | A |
| Sp3-42 | [HU-07-05](04d-historias-conexiones.md#hu-07-05) | Orden de proveedores y detección de errores de cuota | 2,5 | A |
| Sp3-43 | [HU-07-05](04d-historias-conexiones.md#hu-07-05) | Repetir el turno en curso con el respaldo | 2,5 | A |
| Sp3-44 | [HU-07-05](04d-historias-conexiones.md#hu-07-05) | Umbral de compactación por modelo | 2,5 | A |
| Sp3-45 | [HU-08-01](04d-historias-conexiones.md#hu-08-01) | Iniciar el proceso del servidor y negociar | 2,5 | C |
| Sp3-46 | [HU-08-01](04d-historias-conexiones.md#hu-08-01) | Cerrar el proceso al terminar la sesión | 2,5 | C |
| Sp3-47 | [HU-08-02](04d-historias-conexiones.md#hu-08-02) | Traducir el esquema MCP al formato interno | 2,5 | C |
| Sp3-48 | [HU-08-02](04d-historias-conexiones.md#hu-08-02) | Registrar las herramientas | 2,5 | C |
| Sp3-49 | [HU-08-03](04d-historias-conexiones.md#hu-08-03) | Enrutar la invocación por la política | 1,5 | C |
| Sp3-50 | [HU-08-03](04d-historias-conexiones.md#hu-08-03) | Devolver el resultado al bucle | 1,5 | C |
| Sp3-51 | [HU-08-03](04d-historias-conexiones.md#hu-08-03) | Prueba con el servidor de la demostración | 1,5 | C |
| Sp3-52 | [HU-08-04](04d-historias-conexiones.md#hu-08-04) | Capturar fallos del servidor | 1 | C |
| Sp3-53 | [HU-08-04](04d-historias-conexiones.md#hu-08-04) | Deshabilitar solo sus herramientas | 1 | C |
| Sp3-54 | [HU-09-04](04d-historias-conexiones.md#hu-09-04) | Quitar la herramienta de delegación a los subagentes | 2,5 | A |
| Sp3-55 | [HU-09-04](04d-historias-conexiones.md#hu-09-04) | Aplicar los límites del bucle a la sesión hija | 2,5 | A |
| Sp3-56 | [HU-09-05](04d-historias-conexiones.md#hu-09-05) | Resultado de error en el esquema | 1 | A |
| Sp3-57 | [HU-09-05](04d-historias-conexiones.md#hu-09-05) | Prueba de fallo del subagente | 1 | A |
| Sp3-58 | [HU-09-06](04d-historias-conexiones.md#hu-09-06) (opc.) | Definir los dos perfiles | 2,5 | A |
| Sp3-59 | [HU-09-06](04d-historias-conexiones.md#hu-09-06) (opc.) | Pruebas por perfil | 2,5 | A |
| Sp3-60 | [HU-10-01](04d-historias-conexiones.md#hu-10-01) | Suscribir un registrador de trazas al bus de eventos | 1,5 | B |
| Sp3-61 | [HU-10-01](04d-historias-conexiones.md#hu-10-01) | Escribir en formato estructurado consultable | 1,5 | B |
| Sp3-62 | [HU-10-01](04d-historias-conexiones.md#hu-10-01) | Comando o consulta para ver una traza | 1,5 | B |
| Sp3-63 | [HU-10-02](04d-historias-conexiones.md#hu-10-02) | Filtro de redacción en el registrador | 1 | B |
| Sp3-64 | [HU-10-02](04d-historias-conexiones.md#hu-10-02) | Prueba con claves de ejemplo | 1 | B |

---

[← 02-arquitectura.md](02-arquitectura.md) · [Índice](00-indice.md) · [04a-historias-fundacion.md →](04a-historias-fundacion.md)
