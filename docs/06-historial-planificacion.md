# Historial de planificación, decisiones y capacidad (versión 2.5)

> [← 05-trazabilidad.md](05-trazabilidad.md) · [Índice](00-indice.md) · [PROGRESO.md →](PROGRESO.md)  
> Sección 13 del contexto original: auditoría, decisiones PD-01 a PD-06, capacidad y consolidación de la versión 2.5. Las tablas de las versiones 2.3 y 2.4 son históricas; prevalecen 13.8 y 13.12.  
> Ver también: [01-vision-y-decisiones.md](01-vision-y-decisiones.md) · [03-plan-sprints.md](03-plan-sprints.md) · [05-trazabilidad.md](05-trazabilidad.md) · [PROGRESO.md](PROGRESO.md)

## 13. Registro de cambios (historial 2.2–2.3 y escenario 2.4)

Esta sección es el registro de cambios del documento. La versión 2.3 corrige las inconsistencias que dejó la reestructuración de la versión 2.2 sin rediseñar el proyecto: conserva los tres sprints (agente funcional, primera versión vertical del Coding Harness y flujo completo hasta el Pull Request), los requisitos y los formatos F3, F4 y F5. Cada corrección está aplicada en las historias, las tareas y las secciones relacionadas; aquí solo se resume. Los hallazgos se distinguen en tres tipos: problema comprobado en el documento, riesgo técnico inferido y recomendación de mejora.

### 13.1 Tabla de auditoría de la versión 2.3

| ID | Problema | Historia afectada | Tipo | Gravedad | Solución propuesta | Impacto |
|---|---|---|---|---|---|---|
| A-01 | P1. La demostración del Sprint 1 escribe un archivo, pero [HU-01-03](04a-historias-fundacion.md#hu-01-03) clasifica la escritura como acción que requiere permiso, [HU-05-01](04c-historias-control.md#hu-05-01) la manda a «preguntar» y la interfaz de aprobación ([HU-05-03](04c-historias-control.md#hu-05-03)) llega en el Sprint 2, donde «preguntar» se deniega. La demostración la bloquea su propia política. | [HU-01-03](04a-historias-fundacion.md#hu-01-03), [HU-05-01](04c-historias-control.md#hu-05-01), demo del Sprint 1 | Comprobado | Alta | Área de trabajo autorizada: la escritura se permite con una regla explícita acotada a esa área, sobre la ruta real; fuera de ella se pregunta (y en el Sprint 1 se deniega con motivo y registro). | [HU-01-03](04a-historias-fundacion.md#hu-01-03) pasa de 3 a 4 PHU. [HU-02-02](04b-historias-estado.md#hu-02-02) (1 PHU) sale del Sprint 1 para mantenerlo en 39. |
| A-02 | P1. Una comprobación de rutas por texto se evade con «..», enlaces simbólicos, unidades y rutas UNC (Windows). | [HU-01-03](04a-historias-fundacion.md#hu-01-03), [HU-05-01](04c-historias-control.md#hu-05-01) | Riesgo inferido | Media | AreaAutorizada compara siempre la ruta real y se prueba con intentos de escape en Linux y Windows. | Incluido en el aumento de [HU-01-03](04a-historias-fundacion.md#hu-01-03); sin historias nuevas. |
| A-03 | P2. La demostración del Sprint 2 promete compactar sin perder el objetivo, pero HU-02-06 está en el Sprint 3 y depende de [HU-04-03](04b-historias-estado.md#hu-04-03) (Media). | HU-02-06, [HU-02-03](04b-historias-estado.md#hu-02-03), [HU-04-03](04b-historias-estado.md#hu-04-03), demo del Sprint 2 | Comprobado | Alta | Se divide HU-02-06: .1 (Sprint 2) guarda en contexto_esencial el objetivo, las instrucciones, las reglas, el ticket y la referencia a los criterios; .2 (Sprint 3) acumula decisiones y asegura tres compactaciones. | Mismos 2 PHU repartidos 1 + 1. Sin dependencia de [HU-04-03](04b-historias-estado.md#hu-04-03). El Sprint 2 sube 1 PHU y se compensa con [HU-05-05](04c-historias-control.md#hu-05-05) al Sprint 3. |
| A-04 | P3. La demostración del Sprint 2 dice «al interrumpir» y [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) «termina o se interrumpe», pero la interrupción interactiva ([HU-06-03](04c-historias-control.md#hu-06-03)) es del Sprint 3. | [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1), [HU-06-03](04c-historias-control.md#hu-06-03), demo del Sprint 2 | Comprobado | Media | Tres situaciones distintas: terminar con normalidad, terminar el proceso y cancelar una herramienta. [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) escribe progreso al terminar y un punto de control atómico por turno; [HU-06-03](04c-historias-control.md#hu-06-03) es la cancelación controlada. | [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) gana [HU-01-01](04a-historias-fundacion.md#hu-01-01) como dependencia; [HU-06-03](04c-historias-control.md#hu-06-03) depende de [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1). Sin cambio de puntos. |
| A-05 | P4. HU-00-05 (Alta) depende de [HU-08-04](04d-historias-conexiones.md#hu-08-04) (Media) por la prueba de fallos de MCP. | HU-00-05, [HU-08-04](04d-historias-conexiones.md#hu-08-04) | Comprobado | Alta | Se divide HU-00-05: .1 (núcleo, Sprint 3) y .2 (MCP, con la integración MCP). [HU-08-04](04d-historias-conexiones.md#hu-08-04) vuelve a Alta porque RNF-8 es un requisito original. | 3 PHU repartidos 2 + 1. [HU-08-04](04d-historias-conexiones.md#hu-08-04) (1 PHU) pasa a obligatoria (+1 PHU Alta). Decisión PD-03. |
| A-06 | P4. HU-02-06 (Alta) depende de [HU-04-03](04b-historias-estado.md#hu-04-03) (Media). | HU-02-06, [HU-04-03](04b-historias-estado.md#hu-04-03) | Comprobado | Alta | Preservar lo esencial no necesita la memoria estructurada: se elimina la dependencia (ver A-03). [HU-04-03](04b-historias-estado.md#hu-04-03) solo puede enriquecer el bloque de decisiones. | [HU-04-03](04b-historias-estado.md#hu-04-03) sigue opcional; ninguna historia obligatoria depende de ella. |
| A-07 | P4. [HU-07-05](04d-historias-conexiones.md#hu-07-05) (Alta) depende de [HU-07-04](04d-historias-conexiones.md#hu-07-04) (Media), pero conmutar no necesita reintentos. | [HU-07-05](04d-historias-conexiones.md#hu-07-05), [HU-07-04](04d-historias-conexiones.md#hu-07-04) | Comprobado | Media | La conmutación actúa ante errores elegibles, prueba cada proveedor una sola vez por turno y no vuelve al primero: sin bucles. [HU-07-04](04d-historias-conexiones.md#hu-07-04) queda como mejora opcional. | Sin cambio de puntos. Criterios nuevos en [HU-07-05](04d-historias-conexiones.md#hu-07-05). |
| A-08 | P5. El Sprint 3 suma 42 PHU obligatorios frente a 39 de velocidad hipotética; los Sprints 1 y 2 están al 100 %. | Sprint 3 completo | Comprobado | Alta | Alternativa B recomendada: la integración MCP completa ([HU-08-01](04d-historias-conexiones.md#hu-08-01) a [HU-08-04](04d-historias-conexiones.md#hu-08-04) y [HU-00-05.2](04a-historias-fundacion.md#hu-00-05.2), 8 PHU) pasa a un Sprint 4 propuesto. El Sprint 3 queda en 36 PHU. | Compromiso de 114 PHU en tres sprints frente a 117. La decisión es del Product Owner (PD-01). Si la rechaza, el Sprint 3 queda en 44 PHU (5 por encima). |
| A-09 | P5. El documento convertía puntos en horas con una equivalencia fija (1 punto ≈ 2,5 h) y comparaba puntos por persona con una capacidad individual. | Secciones 5, 7 y 13 | Comprobado | Media | Las horas se estiman por tarea, de abajo hacia arriba, y solo se usan para contrastar carga con disponibilidad. Los puntos se leen como velocidad del equipo. | Cambian la sección 5 (estimación por tarea), la sección 7 y las hojas del Excel. Los puntos no se tocan. |
| A-10 | P5. Con las horas estimadas por tarea, los tres sprints superan las horas netas del escenario medio de disponibilidad (104,5, 122,5 y 98 h frente a 96 h del equipo) y el Sprint 2 supera incluso las del escenario alto (121,5 h). | Sprints 1, 2 y 3 | Riesgo inferido | Alta | Se reconoce en la evaluación de capacidad (13.6); se decide con datos tras el Sprint 1 (PD-04) y se deja lista la lista de recortes del Sprint 2. Varias historias de 1 PHU del Sprint 2 suman 4 a 5 h: se revisan en el planning poker, sin cambiar puntos aquí. | Sin cambio de alcance ni de puntos. Riesgo R-22. |
| A-11 | P5. En el Sprint 1 la persona C concentraba la mayor carga de tareas. | [HU-00-02](04a-historias-fundacion.md#hu-00-02), Sprint 1 | Comprobado | Baja | [HU-00-02](04a-historias-fundacion.md#hu-00-02) (integración continua) pasa de C a A; se equilibra por horas, no por puntos. También cambian de responsable [HU-02-02](04b-historias-estado.md#hu-02-02) y [HU-05-04](04c-historias-control.md#hu-05-04) (a C). | Responsables: ver 13.4. Se confirma con el equipo (PD-05). |
| A-12 | P6. La protección de los criterios dependía de una regla de denegación sobre un archivo JSON y de interpretar comandos del shell, que no es verificable por completo. | [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1), [HU-05-02](04c-historias-control.md#hu-05-02) | Riesgo inferido | Alta | Fuente de verdad en SQLite (tabla criterios) con copia JSON de solo lectura que se restaura si cambia; el harness verifica siempre desde SQLite. Limitación declarada (R-21) y entorno aislado ([HU-IN-02](04d-historias-conexiones.md#hu-in-02)) como mecanismo verificable. | [HU-11-01](04e-historias-coding-harness.md#hu-11-01) conserva 2 PHU; se aclara su alcance. Riesgo R-21 y decisión PD-06. |
| A-13 | P6. La demostración del Sprint 3 incluía una herramienta MCP, que sale del compromiso por A-08. | Demo del Sprint 3 | Comprobado | Media | La demostración del Sprint 3 deja de incluir MCP; la del Sprint 4 propuesto lo cubre. | Criterios de demostración reescritos con las historias que los respaldan. |
| A-14 | P6. La sección 13 de la versión 2.2, la sección 7, el pie de la figura de carga y la hoja «Carga» del Excel contenían cifras de la versión 2.2. | Secciones 7 y 13, Excel, figura | Comprobado | Media | Todos los artefactos se regeneran desde la misma fuente de datos y una auditoría automática compara F3, F4, F5, totales y dependencias. | Ver 13.9. Cero incoherencias detectadas por la auditoría tras la regeneración. |

Tipos: «Comprobado» es una incoherencia que se verifica leyendo el propio documento; «Riesgo inferido» es una consecuencia técnica que no está escrita en el documento; las recomendaciones de mejora se marcan en las decisiones pendientes (13.8).

### 13.2 Diagnóstico fundamentado

| Problema | Dónde aparece | Historias | Por qué es una inconsistencia | Impacto | ¿Requiere corrección? |
|---|---|---|---|---|---|
| P1. Permisos del Sprint 1 | Sección 5 (Sprint 1), fichas [HU-01-03](04a-historias-fundacion.md#hu-01-03) y [HU-05-01](04c-historias-control.md#hu-05-01), hito del Sprint 1. | [HU-01-03](04a-historias-fundacion.md#hu-01-03), [HU-05-01](04c-historias-control.md#hu-05-01), [HU-05-03](04c-historias-control.md#hu-05-03) | La demostración del Sprint 1 pide leer, escribir y releer. [HU-01-03](04a-historias-fundacion.md#hu-01-03) clasificaba la escritura como acción que requiere permiso y el hito decía que lo que pide aprobación se deniega hasta el Sprint 2. El criterio de demostración y la política no podían cumplirse a la vez. | Alto: la demostración inaugural quedaba bloqueada, o se desactivaba el control para que pasara. | Sí. Es un problema comprobado. |
| P2. Garantía de contexto tras compactar | Sección 5 (Sprint 2), fichas [HU-02-03](04b-historias-estado.md#hu-02-03), HU-02-06 y [HU-04-03](04b-historias-estado.md#hu-04-03). | [HU-02-03](04b-historias-estado.md#hu-02-03), HU-02-06, [HU-04-03](04b-historias-estado.md#hu-04-03), [HU-03-04](04b-historias-estado.md#hu-03-04) | La demostración del Sprint 2 promete compactar sin perder el objetivo. HU-02-06, que lo garantiza, estaba en el Sprint 3 y dependía de [HU-04-03](04b-historias-estado.md#hu-04-03) (Media). Además, ya existía parte de lo esencial: [HU-11-01](04e-historias-coding-harness.md#hu-11-01) deja el objetivo y los criterios fuera del historial. | Alto: la promesa del Sprint 2 no tenía historia que la respaldara. | Sí. Es un problema comprobado. |
| P3. Interrupción de sesiones | Sección 5 (Sprint 2), fichas [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) y [HU-06-03](04c-historias-control.md#hu-06-03). | [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1), [HU-06-03](04c-historias-control.md#hu-06-03), [HU-03-02](04b-historias-estado.md#hu-03-02) | «Interrumpir» designaba a la vez terminar el proceso y cancelar una herramienta. [HU-06-03](04c-historias-control.md#hu-06-03), que cancela, es del Sprint 3 y es Media; [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) prometía anotar progreso «al interrumpirse». | Medio: ambigüedad, y el riesgo de prometer una cancelación que el Sprint 2 no construye. | Sí. Es un problema comprobado. |
| P4. Dependencias obligatorias sobre opcionales | Sección 13.7 (versión 2.2) y fichas de las seis historias. | HU-00-05 ← [HU-08-04](04d-historias-conexiones.md#hu-08-04); HU-02-06 ← [HU-04-03](04b-historias-estado.md#hu-04-03); [HU-07-05](04d-historias-conexiones.md#hu-07-05) ← [HU-07-04](04d-historias-conexiones.md#hu-07-04) | La versión 2.2 las declaraba como pendientes. Un sprint cuyas historias de Alta dependen de una de Media no puede darse por completo si la de Media no se hace. | Alto: tres historias obligatorias podían quedar incompletas sin que el plan lo avisara. | Sí en los tres casos, con soluciones distintas: división (A), eliminar la dependencia con un mecanismo propio (B) y eliminar la dependencia con criterios de errores elegibles (C). |
| P5. Capacidad y sobrecarga | Secciones 5, 7 y 13.5 a 13.6; hoja «Carga»; figura de carga. | Sprint 3 (42 PHU), Sprints 1 y 2 (39 PHU), estimación de horas | El Sprint 3 superaba en 3 PHU la velocidad hipotética de 39; los Sprints 1 y 2 estaban exactamente al límite. Las horas se obtenían multiplicando los puntos por 2,5 y se repartían en partes iguales entre las tareas de cada historia. | Alto: el plan no era viable tal como estaba y, además, la conversión fija hacía que las horas no aportaran información. | Sí. El exceso es un problema comprobado; la conversión fija es un defecto de método. |
| P6. Coherencia global y protección de criterios | Todo el documento. | Todas; en especial [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1) y el Sprint 3 | La auditoría automática de las versiones anteriores solo comprobaba dependencias entre sprints. No comparaba las demostraciones con las historias que las respaldan ni F3, F4 y F5 entre sí. En seguridad, la protección de los criterios se apoyaba en reglas sobre comandos del shell. | Medio: riesgo de contradicciones nuevas tras cada cambio; en seguridad, una garantía menos fuerte que la prometida. | Sí. La auditoría se amplía y la protección se refuerza con una fuente de verdad que el agente no puede alcanzar con herramientas. |

### 13.3 Soluciones seleccionadas

| Problema | Alternativas | Elegida | Justificación y consecuencias |
|---|---|---|---|
| P1 | Alternativas: (a) permitir escrituras en cualquier sitio durante el Sprint 1; (b) cambiar la demostración para que solo lea; (c) área de trabajo autorizada. | (c). Se descartan (a), porque desactiva el control, y (b), porque la demostración dejaría de probar el bucle completo. | Seguridad y demostración: la regla de permitir está acotada a la ruta real dentro del área; fuera de ella se pregunta y, mientras no exista [HU-05-03](04c-historias-control.md#hu-05-03), se deniega con motivo y se registra. No hay ninguna regla global. Cuesta 1 PHU en [HU-01-03](04a-historias-fundacion.md#hu-01-03) por las pruebas de escape; se compensa moviendo [HU-02-02](04b-historias-estado.md#hu-02-02), que ninguna demostración del Sprint 1 usa. |
| P2 | Alternativas: (a) adelantar HU-02-06 completa al Sprint 2; (b) quitar la promesa del Sprint 2; (c) dividir HU-02-06. | (c). La parte esencial (1 PHU) entra en el Sprint 2; las decisiones acumuladas y las tres compactaciones quedan en el Sprint 3. | Menor impacto: (a) añadiría 2 PHU al sprint más cargado y arrastraría la dependencia de [HU-04-03](04b-historias-estado.md#hu-04-03); (b) retiraría una garantía que el flujo del ticket necesita. No se duplica trabajo: [HU-11-01](04e-historias-coding-harness.md#hu-11-01) crea la sesión y los criterios; [HU-02-06.1](04b-historias-estado.md#hu-02-06.1) solo los protege de la compactación. |
| P3 | Alternativas: (a) adelantar [HU-06-03](04c-historias-control.md#hu-06-03) al Sprint 2; (b) precisar qué hace [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1). | (b). [HU-06-03](04c-historias-control.md#hu-06-03) sigue en el Sprint 3. | El Sprint 2 solo promete lo que sus historias construyen: progreso al terminar con normalidad y, tras terminar el proceso, el último punto de control completo. La cancelación controlada es de [HU-06-03](04c-historias-control.md#hu-06-03), que además deja un punto de control al cancelar. |
| P4-A | Alternativas: (a) subir [HU-08-04](04d-historias-conexiones.md#hu-08-04) a Alta; (b) dividir HU-00-05. | Ambas, porque se complementan: se divide HU-00-05 para que las pruebas del núcleo no esperen a MCP, y [HU-08-04](04d-historias-conexiones.md#hu-08-04) sube a Alta para que la prueba de MCP (RNF-8) no se condicione a una historia opcional. | No se elimina ninguna prueba de fallos. El costo es 1 PHU de prioridad Alta más ([HU-08-04](04d-historias-conexiones.md#hu-08-04)), que viaja con la integración MCP. |
| P4-B | Alternativas: (a) subir [HU-04-03](04b-historias-estado.md#hu-04-03) a Alta; (b) eliminar la dependencia con un mecanismo propio. | (b): la tabla contexto_esencial y su inyección en el prefijo. | Mantiene las garantías originales de HU-02-06 sin memoria estructurada. La memoria estructurada puede enriquecer las decisiones, pero no se exige. |
| P4-C | Alternativas: (a) subir [HU-07-04](04d-historias-conexiones.md#hu-07-04) a Alta; (b) conmutar ante errores elegibles sin reintentos. | (b). Técnicamente válido: el cambio de proveedor es una respuesta a un error persistente, no una forma de reintentar. | Errores elegibles: cuota agotada, límite de tasa, tiempo agotado, servicio no disponible y error de conexión. Cada proveedor se prueba una vez por turno y no hay vuelta automática al primero, así que no hay bucles. Si [HU-07-04](04d-historias-conexiones.md#hu-07-04) existe, se agotan antes sus reintentos. |
| P5 | Alternativas A, B y C de la sección 13.6. | B, con una decisión con datos al cierre del Sprint 1. | Ver la evaluación de la sección 13.6. Los puntos se leen como velocidad del equipo y las horas como contraste con la disponibilidad. |
| P6 | Alternativas: (a) denegar con reglas el archivo de criterios; (b) fuente de verdad en SQLite y copia de solo lectura; (c) entorno aislado. | (b) ahora y (c) como recomendación ([HU-IN-02](04d-historias-conexiones.md#hu-in-02)). | (b) no depende de interpretar comandos: aunque el agente lograra cambiar la copia, el harness verifica siempre desde SQLite y la restaura. Sigue sin cubrir un agente que edite las pruebas que usa un criterio; eso lo mitiga la revisión del diff. Solo (c) lo hace verificable. |

### 13.4 Historias corregidas durante la versión 2.3 (historial; prevalece la redistribución 2.4 de F3–F5)

Solo aparecen las historias cuyo sprint, responsable, estimación, prioridad o dependencias cambiaron respecto de la versión 2.2. Las historias divididas usan identificadores derivados (.1 y .2) y conservan los puntos de la original. Las fichas completas están en la sección 4.

| Historia | Título | Versión 2.2 | Versión 2.3 | Depende de | Justificación |
|---|---|---|---|---|---|
| [HU-00-02](04a-historias-fundacion.md#hu-00-02) | Integración continua con pruebas, tipado y formato | Sprint 1 (2 PHU, C) | Sprint 1 (2 PHU, A) | — | Equilibrio de horas del Sprint 1: la persona C tenía la mayor carga. La integración continua acompaña al esqueleto del repositorio (A) (P5). |
| HU-00-05 | Pruebas de integración y de fallos | Sprint 3 (3 PHU, A) | Dividida en [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1) (Sprint 3) y [HU-00-05.2](04a-historias-fundacion.md#hu-00-05.2) (Sprint 4 (según v2.4, entonces propuesto)) | Ver las dos partes | Se divide: pruebas del núcleo (Sprint 3) y prueba de MCP, que viaja con la integración MCP (P4-A). |
| [HU-01-03](04a-historias-fundacion.md#hu-01-03) | Herramientas de archivos: leer, escribir, listar y buscar | Sprint 1 (3 PHU, C) | Sprint 1 (4 PHU, C) | [HU-01-02](04a-historias-fundacion.md#hu-01-02) | Suma las pruebas de escape de rutas y el componente AreaAutorizada (P1). |
| [HU-02-02](04b-historias-estado.md#hu-02-02) | Recorte de salidas largas de herramientas | Sprint 1 (1 PHU, A) | Sprint 2 (1 PHU, C) | [HU-01-02](04a-historias-fundacion.md#hu-01-02) | Sale del Sprint 1: la demostración no necesita recortes; la usan el shell y las pruebas del Sprint 2. Pasa a C, que ya tiene [HU-11-03](04e-historias-coding-harness.md#hu-11-03), su dependiente (P1, P5). |
| HU-02-06 | Conservar objetivo, instrucciones y decisiones tras compactar | Sprint 3 (2 PHU, B) | Dividida en [HU-02-06.1](04b-historias-estado.md#hu-02-06.1) (Sprint 2) y [HU-02-06.2](04b-historias-estado.md#hu-02-06.2) (Sprint 3) | Ver las dos partes | Se divide: lo esencial (Sprint 2, sin [HU-04-03](04b-historias-estado.md#hu-04-03)) y las decisiones acumuladas (Sprint 3) (P2, P4-B). |
| [HU-05-01](04c-historias-control.md#hu-05-01) | Política denegar, preguntar, permitir que falla cerrada | Sprint 1 (3 PHU, C) | Sprint 1 (3 PHU, C) | [HU-00-01](04a-historias-fundacion.md#hu-00-01), [HU-01-03](04a-historias-fundacion.md#hu-01-03), [HU-01-05](04a-historias-fundacion.md#hu-01-05) | Depende de [HU-01-03](04a-historias-fundacion.md#hu-01-03) (usa AreaAutorizada) y de [HU-01-05](04a-historias-fundacion.md#hu-01-05) (registra la decisión como evento). Nuevos criterios 4 y 5 (P1). |
| [HU-05-04](04c-historias-control.md#hu-05-04) | Rechazo con motivo que vuelve al modelo | Sprint 2 (1 PHU, B) | Sprint 2 (1 PHU, C) | [HU-05-03](04c-historias-control.md#hu-05-03) | Vuelve a C, responsable natural de permisos. Ya no se usa para equilibrar el Sprint 2 (P5). |
| [HU-05-05](04c-historias-control.md#hu-05-05) | Registro de auditoría de decisiones | Sprint 2 (2 PHU, C) | Sprint 3 (2 PHU, C) | [HU-05-03](04c-historias-control.md#hu-05-03) | Sale del Sprint 2. La demostración del Sprint 2 se apoya en los eventos; la auditoría se necesita en el Sprint 3 (P5). |
| [HU-06-03](04c-historias-control.md#hu-06-03) | Interrumpir la ejecución sin perder la sesión | Sprint 3 (2 PHU, A) | Sprint 3 (2 PHU, A) | [SPK-02](04a-historias-fundacion.md#spk-02), [HU-01-01](04a-historias-fundacion.md#hu-01-01), [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) | Depende de [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) para dejar un punto de control al cancelar. Sigue siendo Media (P3). |
| [HU-07-05](04d-historias-conexiones.md#hu-07-05) | Conmutación por fallo con umbral por modelo | Sprint 3 (3 PHU, A) | Sprint 3 (3 PHU, A) | [HU-07-03](04d-historias-conexiones.md#hu-07-03) | Ya no depende de [HU-07-04](04d-historias-conexiones.md#hu-07-04): conmuta ante errores elegibles y sin bucles (P4-C). |
| [HU-08-01](04d-historias-conexiones.md#hu-08-01) | Conexión a un servidor MCP por stdio | Sprint 3 (2 PHU, C) | Sprint 4 (según v2.4, entonces propuesto) (2 PHU, C) | [SPK-04](04d-historias-conexiones.md#spk-04) | Pasa a la propuesta de Sprint 4 (P5). |
| [HU-08-02](04d-historias-conexiones.md#hu-08-02) | Descubrir herramientas MCP y traducirlas al formato interno | Sprint 3 (2 PHU, C) | Sprint 4 (según v2.4, entonces propuesto) (2 PHU, C) | [HU-08-01](04d-historias-conexiones.md#hu-08-01), [HU-01-02](04a-historias-fundacion.md#hu-01-02) | Pasa a la propuesta de Sprint 4 (P5). |
| [HU-08-03](04d-historias-conexiones.md#hu-08-03) | Invocar herramientas MCP bajo la misma política de permisos | Sprint 3 (2 PHU, C) | Sprint 4 (según v2.4, entonces propuesto) (2 PHU, C) | [HU-08-02](04d-historias-conexiones.md#hu-08-02), [HU-05-01](04c-historias-control.md#hu-05-01) | Pasa a la propuesta de Sprint 4 (P5). |
| [HU-08-04](04d-historias-conexiones.md#hu-08-04) | Aislar los fallos de un servidor MCP | Sprint 3 (1 PHU, C) | Sprint 4 (según v2.4, entonces propuesto) (1 PHU, C, prioridad Alta) | [HU-08-01](04d-historias-conexiones.md#hu-08-01) | Sube a Alta (RNF-8) y pasa a la propuesta de Sprint 4 (P4-A, P5). |
| [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) | Archivo de progreso del ticket con puntos de control | Sprint 2 (1 PHU, B) | Sprint 2 (1 PHU, B) | [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-03-01](04b-historias-estado.md#hu-03-01), [HU-01-01](04a-historias-fundacion.md#hu-01-01) | Se acota a progreso al terminar y puntos de control. Depende también de [HU-01-01](04a-historias-fundacion.md#hu-01-01) (el punto de control cierra cada turno) (P3). |
| [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1) | Pruebas de integración y de fallos del núcleo | — (historia nueva) | Sprint 3 (2 PHU, A) | [HU-03-02](04b-historias-estado.md#hu-03-02), [HU-07-05](04d-historias-conexiones.md#hu-07-05) | Ya no depende de [HU-08-04](04d-historias-conexiones.md#hu-08-04). Cubre RNF-1, 5, 6 y 7. |
| [HU-00-05.2](04a-historias-fundacion.md#hu-00-05.2) | Prueba de aislamiento de fallos de un servidor MCP | — (historia nueva) | Sprint 4 (según v2.4, entonces propuesto) (1 PHU, A) | [HU-08-04](04d-historias-conexiones.md#hu-08-04), [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1) | Cubre RNF-8. Depende de [HU-08-04](04d-historias-conexiones.md#hu-08-04), que ahora es Alta. |
| [HU-02-06.1](04b-historias-estado.md#hu-02-06.1) | Contexto esencial persistente fuera del historial compactable | — (historia nueva) | Sprint 2 (1 PHU, B) | [HU-02-03](04b-historias-estado.md#hu-02-03), [HU-11-01](04e-historias-coding-harness.md#hu-11-01) | Depende de la compactación ([HU-02-03](04b-historias-estado.md#hu-02-03)) y de la tarea con criterios ([HU-11-01](04e-historias-coding-harness.md#hu-11-01)). |
| [HU-02-06.2](04b-historias-estado.md#hu-02-06.2) | Decisiones acumuladas y continuidad tras varias compactaciones | — (historia nueva) | Sprint 3 (1 PHU, B) | [HU-02-06.1](04b-historias-estado.md#hu-02-06.1), [HU-05-04](04c-historias-control.md#hu-05-04) | Depende de [HU-02-06.1](04b-historias-estado.md#hu-02-06.1) y de [HU-05-04](04c-historias-control.md#hu-05-04) (el rechazo con motivo es la decisión que más importa conservar). |

Historias cuyo contenido cambió sin cambiar su planificación:

[HU-11-01](04e-historias-coding-harness.md#hu-11-01): Criterios en la tabla criterios de SQLite con una copia JSON de solo lectura que se restaura si cambia (P6). Mismos 2 PHU: sustituye el archivo JSON como fuente por una tabla y añade la detección por huella.

[HU-07-04](04d-historias-conexiones.md#hu-07-04): Se declara como mejora opcional: si existe, la conmutación espera a que se agoten sus reintentos (P4-C).

[HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1): Sin cambios de planificación; los criterios se leen de SQLite (P6).

Criterios de aceptación de las historias corregidas (texto completo):

[HU-01-03](04a-historias-fundacion.md#hu-01-03) — Herramientas de archivos: leer, escribir, listar y buscar (4 PHU, Sprint 1, Alta). Depende de: [HU-01-02](04a-historias-fundacion.md#hu-01-02).

AC-01  Dado una ruta existente dentro del área de trabajo, cuando el agente la lee, entonces recibe su contenido; si no existe, recibe un error claro.

AC-02  Dado una escritura cuya ruta real queda dentro del área de trabajo autorizada, cuando la política la evalúa, entonces se permite y la decisión queda registrada; dado una escritura fuera del área, entonces es una acción que requiere permiso.

AC-03  Dado una ruta con «..», una ruta absoluta, un enlace simbólico o, en Windows, otra unidad, una ruta UNC o un flujo alterno, cuando se resuelve, entonces se calcula la ruta real y, si el destino queda fuera del área, se rechaza antes de escribir y el modelo recibe el motivo.

AC-04  Dado que no hay un área de trabajo configurada, cuando el agente intenta escribir, entonces toda escritura requiere permiso: no existe un área por defecto fuera de la carpeta de la sesión.

[HU-05-01](04c-historias-control.md#hu-05-01) — Política denegar, preguntar, permitir que falla cerrada (3 PHU, Sprint 1, Alta). Depende de: [HU-00-01](04a-historias-fundacion.md#hu-00-01), [HU-01-03](04a-historias-fundacion.md#hu-01-03), [HU-01-05](04a-historias-fundacion.md#hu-01-05).

AC-01  Dado una llamada que no coincide con ninguna regla, cuando se evalúa, entonces requiere aprobación manual.

AC-02  Dado reglas que se contradicen, cuando se evalúan, entonces prevalece el orden denegar, preguntar, permitir.

AC-03  Dado instrucciones en el contenido de un archivo, cuando el modelo las sigue, entonces la política las evalúa igual que cualquier otra llamada.

AC-04  Dado una escritura cuya ruta real queda dentro del área de trabajo autorizada, cuando se evalúa, entonces una regla explícita acotada a esa área la permite; dado cualquier otra ubicación, entonces se pregunta. No existe ninguna regla que permita escribir en cualquier ruta.

AC-05  Dado el Sprint 1, sin la interfaz de aprobación ([HU-05-03](04c-historias-control.md#hu-05-03)), cuando una acción resulta en «preguntar», entonces se deniega provisionalmente, el modelo recibe el motivo y la decisión queda registrada como evento; esta resolución provisional se retira cuando [HU-05-03](04c-historias-control.md#hu-05-03) existe.

[HU-02-06.1](04b-historias-estado.md#hu-02-06.1) — Contexto esencial persistente fuera del historial compactable (1 PHU, Sprint 2, Alta). Depende de: [HU-02-03](04b-historias-estado.md#hu-02-03), [HU-11-01](04e-historias-coding-harness.md#hu-11-01).

AC-01  Dado una sesión con objetivo, instrucciones, reglas, identificador de ticket y criterios, cuando se compacta, entonces esos elementos siguen en el prefijo del contexto, idénticos, y no forman parte de lo resumido.

AC-02  Dado una compactación, cuando se reconstruye el contexto, entonces las instrucciones de sistema están intactas y los criterios se leen desde su fuente protegida, no desde el resumen.

AC-03  Dado una sesión compactada, cuando se pregunta por el objetivo original, entonces el agente lo responde correctamente.

[HU-02-06.2](04b-historias-estado.md#hu-02-06.2) — Decisiones acumuladas y continuidad tras varias compactaciones (1 PHU, Sprint 3, Alta). Depende de: [HU-02-06.1](04b-historias-estado.md#hu-02-06.1), [HU-05-04](04c-historias-control.md#hu-05-04).

AC-01  Dado una sesión con decisiones del usuario, entre ellas un rechazo con motivo, cuando se compacta tres veces seguidas, entonces las decisiones siguen en el bloque esencial sin resumirse y el agente responde correctamente el objetivo original.

AC-02  Dado el resumen de una compactación, cuando se genera, entonces incluye una sección con las decisiones del tramo resumido.

[HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1) — Pruebas de integración y de fallos del núcleo (2 PHU, Sprint 3, Alta). Depende de: [HU-03-02](04b-historias-estado.md#hu-03-02), [HU-07-05](04d-historias-conexiones.md#hu-07-05).

AC-01  Dado un cierre forzado del proceso a mitad de sesión, cuando se reanuda, entonces no se pierde ningún evento confirmado.

AC-02  Dado un proveedor principal caído con un error elegible, cuando corre el turno, entonces el sistema conmuta al de respaldo y el turno termina; dado una herramienta que lanza una excepción, entonces el modelo recibe un error y el bucle continúa.

AC-03  Dado un turno con proveedor simulado y herramientas instantáneas, cuando se mide, entonces el tiempo propio del harness es pequeño y queda registrado.

[HU-00-05.2](04a-historias-fundacion.md#hu-00-05.2) — Prueba de aislamiento de fallos de un servidor MCP (1 PHU, Sprint 4 (aprobado en calendario; distribución de v2.5 pendiente de ratificación), Alta). Depende de: [HU-08-04](04d-historias-conexiones.md#hu-08-04), [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1).

AC-01  Dado un servidor MCP inexistente o caído, cuando arranca la sesión, entonces solo sus herramientas quedan deshabilitadas y el resto funciona.

AC-02  Dado un servidor que se cae a mitad de sesión, cuando el modelo invoca su herramienta, entonces recibe un error y las demás herramientas siguen funcionando.

[HU-07-05](04d-historias-conexiones.md#hu-07-05) — Conmutación por fallo con umbral por modelo (3 PHU, Sprint 3, Alta). Depende de: [HU-07-03](04d-historias-conexiones.md#hu-07-03).

AC-01  Dado un error elegible (cuota agotada, límite de tasa, tiempo agotado, servicio no disponible o error de conexión) en el proveedor activo, cuando ocurre, entonces el sistema cambia al de respaldo, repite el turno y lo registra en la traza y en pantalla.

AC-02  Dado un error no elegible (clave inválida, petición mal formada o rechazo por política de contenido), cuando ocurre, entonces no hay conmutación y el usuario recibe el error.

AC-03  Dado que el proveedor de respaldo también falla con un error elegible en el mismo turno, cuando se agota la lista de proveedores, entonces el turno termina con un error claro tras probar cada proveedor una sola vez, sin bucle y sin volver automáticamente al primero dentro del turno.

AC-04  Dado el cambio de modelo, cuando se evalúa la compactación, entonces se usa el umbral propio de la ventana del nuevo modelo.

[HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) — Archivo de progreso del ticket con puntos de control (1 PHU, Sprint 2, Alta). Depende de: [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-03-01](04b-historias-estado.md#hu-03-01), [HU-01-01](04a-historias-fundacion.md#hu-01-01).

AC-01  Dado el final normal de una sesión de trabajo, cuando el agente termina, entonces el archivo de progreso queda actualizado con lo hecho, lo pendiente y el estado de cada criterio; si no existe, se crea con el formato definido.

AC-02  Dado el trabajo en curso, cuando termina cada turno del agente, entonces se escribe un punto de control del archivo de progreso mediante escritura atómica (archivo temporal y renombrado).

AC-03  Dado que el proceso se terminó de golpe, cuando el usuario reanuda la sesión por su identificador, entonces el archivo de progreso conserva el último punto de control completo y no queda un archivo a medias.

[HU-06-03](04c-historias-control.md#hu-06-03) — Interrumpir la ejecución sin perder la sesión (2 PHU, Sprint 3, Media). Depende de: [SPK-02](04a-historias-fundacion.md#spk-02), [HU-01-01](04a-historias-fundacion.md#hu-01-01), [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1).

AC-01  Dado un comando en ejecución, cuando interrumpo, entonces se cancela esa herramienta, el modelo recibe un resultado de cancelado y la sesión sigue disponible.

AC-02  Dado una cancelación, cuando termina, entonces los eventos hasta ese punto están guardados y el archivo de progreso del ticket se actualiza con un punto de control.

[HU-11-01](04e-historias-coding-harness.md#hu-11-01) — Tarea con criterios de aceptación protegidos en SQLite (2 PHU, Sprint 2, Alta). Depende de: [HU-03-01](04b-historias-estado.md#hu-03-01), [HU-01-01](04a-historias-fundacion.md#hu-01-01), [HU-05-01](04c-historias-control.md#hu-05-01).

AC-01  Dado un archivo de tarea con objetivo, reglas y criterios, cuando se inicia la tarea, entonces se crea una sesión nueva y los criterios (descripción, tipo objetivo o semántico, comando de verificación, condición esperada y passes en falso) se guardan en la tabla criterios de SQLite, con una copia JSON de solo lectura.

AC-02  Dado un archivo de tarea sin criterios de aceptación, cuando se inicia, entonces el sistema lo rechaza e indica qué falta.

AC-03  Dado que el agente intenta modificar los criterios, su copia exportada o la base de datos con las herramientas de archivos o con el shell, cuando la política lo evalúa, entonces lo deniega; dado que la copia exportada cambió por cualquier vía, cuando el harness verifica, entonces ignora la copia, usa los criterios de SQLite, restaura la exportación y registra el intento.

### 13.5 Sprint Backlogs: versión consolidada 2.5 y trazabilidad de demostraciones

Los F5 operativos están en la sección 5. Las matrices siguientes vinculan demostraciones con historias Alta disponibles en cada sprint. El calendario de cuatro semanas está aprobado según la v3; la asignación de las 11 PHU adicionales de S4 exige ratificación en Planning.

### Sprint 1 — Agente ejecutable en terminal: recibe una tarea, usa herramientas de archivos y deja todo guardado

Sprint 1: 16 elementos Alta, 39 PHU y 104,5 h estimadas; disponibilidad media insuficiente (96 h).

| Criterio de demostración | Historias que lo respaldan |
|---|---|
| Con el proveedor simulado, una tarea guionizada de tres pasos (leer, escribir y releer un archivo) dentro del área de trabajo autorizada termina igual en cada ejecución, también en la integración continua. | [HU-00-03](04a-historias-fundacion.md#hu-00-03), [HU-01-01](04a-historias-fundacion.md#hu-01-01), [HU-01-03](04a-historias-fundacion.md#hu-01-03), [HU-05-01](04c-historias-control.md#hu-05-01), [HU-00-02](04a-historias-fundacion.md#hu-00-02) |
| Con un modelo real, el agente completa la misma tarea desde la CLI y muestra los eventos en tiempo real. | [HU-07-01](04d-historias-conexiones.md#hu-07-01), [HU-07-02](04d-historias-conexiones.md#hu-07-02), [HU-06-01](04c-historias-control.md#hu-06-01), [HU-01-05](04a-historias-fundacion.md#hu-01-05), [HU-00-04](04a-historias-fundacion.md#hu-00-04) |
| Tras la ejecución existe una sesión en SQLite con todos sus eventos; si se mata el proceso a mitad, los eventos ya ocurridos siguen guardados. | [HU-03-01](04b-historias-estado.md#hu-03-01), [HU-03-02](04b-historias-estado.md#hu-03-02) |
| Una escritura fuera del área (con «..», ruta absoluta o enlace simbólico) se rechaza antes de escribir, el modelo recibe el motivo y la decisión queda como evento. | [HU-01-03](04a-historias-fundacion.md#hu-01-03), [HU-05-01](04c-historias-control.md#hu-05-01), [HU-03-02](04b-historias-estado.md#hu-03-02) |
| Una acción que resulta en «preguntar» se deniega con motivo, porque la aprobación interactiva llega en el Sprint 2; no hay ninguna regla que permita escribir en cualquier ruta. | [HU-05-01](04c-historias-control.md#hu-05-01) |
| La integración continua pasa en Linux y en Windows. | [HU-00-02](04a-historias-fundacion.md#hu-00-02) |

### Sprint 2 — Primer flujo vertical del Coding Harness: del ticket a la verificación automática de criterios

Sprint 2: 16 elementos Alta, 31 PHU y 101 h estimadas; incluye el spike MCP [SPK-04](04d-historias-conexiones.md#spk-04), sin prometer integración MCP en esta demo. Subagentes y progreso del ticket permanecen en S3.

| Criterio de demostración | Historias que lo respaldan |
|---|---|
| Dado un ticket de ejemplo con tres criterios (dos con comando de verificación y uno semántico), el agente modifica el proyecto de prueba, git status y git diff muestran el cambio, y la CLI presenta cada criterio como cumplido, no cumplido o pendiente de validación humana. | [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1), [HU-11-03](04e-historias-coding-harness.md#hu-11-03), [HU-11-02](04e-historias-coding-harness.md#hu-11-02), [HU-01-04](04a-historias-fundacion.md#hu-01-04) |
| «Cumplido» solo aparece después de que el harness ejecuta el comando de verificación; un intento del agente de modificar los criterios (por las herramientas de archivos o por el shell) se bloquea y queda en los eventos. | [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1), [HU-05-01](04c-historias-control.md#hu-05-01), [HU-03-02](04b-historias-estado.md#hu-03-02) |
| Un comando encadenado con una parte denegada se rechaza; uno no permitido pide aprobación al usuario y un rechazo con motivo vuelve al modelo. | [HU-05-02](04c-historias-control.md#hu-05-02), [HU-05-03](04c-historias-control.md#hu-05-03), [HU-05-04](04c-historias-control.md#hu-05-04), [HU-01-04](04a-historias-fundacion.md#hu-01-04) |
| Las pruebas del proyecto de ejemplo se ejecutan con tiempo máximo, código de salida visible y salida recortada. | [HU-11-03](04e-historias-coding-harness.md#hu-11-03), [HU-01-04](04a-historias-fundacion.md#hu-01-04), [HU-02-02](04b-historias-estado.md#hu-02-02) |
| Tras cerrar abruptamente el proceso se conservan los eventos confirmados de la sesión; al reanudar por identificador se reconstruye el historial. | [HU-03-02](04b-historias-estado.md#hu-03-02), [HU-03-04](04b-historias-estado.md#hu-03-04) |
| Una sesión larga se compacta y el agente sigue conociendo el objetivo, las instrucciones, las reglas de la tarea, el identificador del ticket y los criterios, que no forman parte de lo resumido. | [HU-02-03](04b-historias-estado.md#hu-02-03), [HU-02-06.1](04b-historias-estado.md#hu-02-06.1), [HU-02-01](04b-historias-estado.md#hu-02-01), [HU-11-01](04e-historias-coding-harness.md#hu-11-01) |

### Sprint 3 — Coding Harness completo: del ticket al Pull Request, con integración y calidad

Sprint 3: 16 elementos Alta, 33 PHU y 94,5 h estimadas. Demuestra ticket→PR con auditoría mínima redactada y verificación independiente. El avance depende de completar subagentes.

| Criterio de demostración | Historias que lo respaldan |
|---|---|
| Sobre un repositorio de demostración, el flujo completo termina con un Pull Request creado y su enlace visible. | [HU-11-06](04e-historias-coding-harness.md#hu-11-06), [HU-11-05](04e-historias-coding-harness.md#hu-11-05), [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1), [HU-11-02](04e-historias-coding-harness.md#hu-11-02) |
| Un criterio semántico recibe el informe del subagente verificador y queda pendiente hasta que el usuario lo confirma; el subagente no puede editar archivos. | [HU-11-04.2](04e-historias-coding-harness.md#hu-11-04.2), [HU-09-06](04d-historias-conexiones.md#hu-09-06), [HU-09-02](04d-historias-conexiones.md#hu-09-02), [HU-09-03](04d-historias-conexiones.md#hu-09-03), [HU-09-01](04d-historias-conexiones.md#hu-09-01), [HU-11-05](04e-historias-coding-harness.md#hu-11-05) |
| Un ticket interrumpido se reanuda: antes de pedir trabajo nuevo, el harness entrega el progreso, el log de git y el resultado de la prueba básica. | [HU-11-08.2](04e-historias-coding-harness.md#hu-11-08.2), [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1), [HU-03-04](04b-historias-estado.md#hu-03-04), [HU-11-02](04e-historias-coding-harness.md#hu-11-02) |
| Las pruebas de fallos del núcleo pasan; cada aprobación y rechazo deja auditoría mínima con argumentos sensibles redactados (sin trazas completas). | [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1), [HU-05-05](04c-historias-control.md#hu-05-05) |
| El proveedor activo conmuta al de respaldo ante error elegible y nunca entra en bucle. | [HU-07-03](04d-historias-conexiones.md#hu-07-03), [HU-07-05](04d-historias-conexiones.md#hu-07-05) |
| Tras tres compactaciones seguidas el agente respeta el rechazo con motivo que el usuario dio antes y conoce el objetivo original. | [HU-02-06.2](04b-historias-estado.md#hu-02-06.2), [HU-02-06.1](04b-historias-estado.md#hu-02-06.1), [HU-05-04](04c-historias-control.md#hu-05-04) |
| Las pruebas de fallos del núcleo pasan; cada aprobación y rechazo deja auditoría mínima con argumentos sensibles redactados (sin trazas completas). | [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1), [HU-05-05](04c-historias-control.md#hu-05-05) |

### Sprint 4 — MCP, memoria, trazabilidad y funciones complementarias

Semana aprobada en PD-01 de v3; 11 elementos Alta, 19 PHU, 45,5 h estimadas. El PO aprobó 8 PHU de MCP; el reparto adicional de 11 PHU debe ratificarse en Planning. La meta incluye MCP, memoria, trazas completas y capacidades diferidas.

| Criterio de demostración | Historias que lo respaldan |
|---|---|
| El agente se conecta a un servidor MCP por stdio, descubre sus herramientas y las usa con el mismo formato que las nativas. | [HU-08-01](04d-historias-conexiones.md#hu-08-01), [HU-08-02](04d-historias-conexiones.md#hu-08-02), [SPK-04](04d-historias-conexiones.md#spk-04) |
| Una herramienta MCP pasa por la misma política de permisos que las nativas: pide aprobación y un rechazo con motivo vuelve al modelo. | [HU-08-03](04d-historias-conexiones.md#hu-08-03), [HU-05-01](04c-historias-control.md#hu-05-01), [HU-05-03](04c-historias-control.md#hu-05-03), [SPK-04](04d-historias-conexiones.md#spk-04) |
| Si el servidor se cae, el modelo recibe un error y las demás herramientas siguen funcionando; la prueba automática lo comprueba. | [HU-08-04](04d-historias-conexiones.md#hu-08-04), [HU-00-05.2](04a-historias-fundacion.md#hu-00-05.2) |
| La memoria persistente se recupera en una nueva sesión, se listan sesiones, se pregunta con opciones y cada traza sensible se redacta antes de registrarse (solo si PD-01 se aprueba). | [HU-04-01](04b-historias-estado.md#hu-04-01), [HU-04-02](04b-historias-estado.md#hu-04-02), [HU-03-03](04b-historias-estado.md#hu-03-03), [HU-06-02](04c-historias-control.md#hu-06-02), [HU-10-01](04d-historias-conexiones.md#hu-10-01), [HU-10-02](04d-historias-conexiones.md#hu-10-02) |

### 13.6 Capacidad y viabilidad — versión 2.5

La velocidad hipotética 39 PHU/sprint no es garantía de entrega. Cargas Alta reales por F5: 104,5 / 101 / 94,5 / 45,5 h en S1–S4. Disponibilidad neta media: 96 h y alta: 121,5 h por sprint. S1 y S2 superan el escenario medio en 8,5 y 5 h respectivamente; todas las semanas caben en el escenario alto sin asegurar el margen recomendado del 20 %. Las PHU siguen siendo relativas; la estimación de horas es por tarea.

| Criterio | A. Mantener tres sprints | B. Cuarta semana aprobada; reparto v2.5 sujeto a ratificación | C. Ajustar el alcance con el PO |
|---|---|---|---|
| Dependencias | En tres sprints MCP competiría con el cierre del Pull Request; no se ha validado una secuencia viable. | Cuarta semana aprobada: el verificador y ticket→PR se entregan en S3; MCP, memoria y auxiliares en S4. Debe ratificarse el reparto adicional de 11 PHU. | Exige renegociación explícita de entregables y dependencias, no solo etiquetas de prioridad. |
| Riesgo técnico | Muy alto, especialmente en Sprint 3. | Sigue alto en la ruta crítica de subagentes en Sprint 3; menor en Sprint 2. | Variable; depende de qué requisitos académicos se modifiquen. |
| Valor entregado | No se puede garantizar la funcionalidad obligatoria completa en tres semanas. | Ticket→verificación en S2 ([SPK-04](04d-historias-conexiones.md#spk-04) investiga MCP); ticket→PR y auditoría mínima redactada en S3; MCP y funciones transversales diferidas en S4. | Dependerá del acuerdo explícito con el Product Owner. |
| Capacidad estimada | No viable conforme a las horas actuales; requiere recortar requisitos o extender calendario. | PHU Alta S1 39, S2 31, S3 33, S4 19; horas 104,5 / 101 / 94,5 / 45,5. Semana aprobada, horas/persona y alcance repartido aún por validar. | Debe recalcularse después de una renegociación verdadera; prohibido reducir puntos artificialmente. |
| Disponibilidad del equipo | Insuficiente con escenario medio y sin reserva. | S1 y S2 siguen tensos incluso con cuarta semana; se exige validar horas reales disponibles. | La capacidad del equipo no cambia por redefinir prioridades. |
| Requisitos académicos | Solo si todos los requisitos obligatorios caben antes de la entrega real; no demostrado. | Cierre planificado 13/11, antes del límite de 14/11. La disponibilidad real y la ratificación de las 11 PHU trasladadas siguen abiertas. | Las renuncias requieren aprobación del PO y cumplimiento de rúbrica. |
| Veredicto | No aprobar como compromiso en el estado actual. | Plan base recomendado para Planning. Semana S4 aprobada en v3; distribución de sus 19 PHU Alta y horas/persona todavía por ratificar. | Alternativa si se rechaza PD-01: hay que diseñar un nuevo compromiso sin dependencias incoherentes. |

Decisión incorporada desde v3: se aprobó una cuarta semana con cierre máximo 14/11/2026, no una velocidad ni una holgura garantizada. Para mantener el flujo vertical del S2, subagentes y progreso se implementan en S3; se adelanta únicamente [SPK-04](04d-historias-conexiones.md#spk-04) (4 h) al S2. MCP completo permanece en S4 junto con otras funcionalidades cuya reubicación aún debe ratificar el equipo. Ante una caída de disponibilidad o necesidad de reducir alcance, no degradar [HU-07-05](04d-historias-conexiones.md#hu-07-05) mientras [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1) dependa de ella; remitir al PO una alternativa validada.

Ruta crítica de implementación (suma de horas de las historias de la cadena, sin contar esperas):

| Sprint | Cadena | Horas | Cómo se protege |
|---|---|---|---|
| Sprint 1 | [HU-01-02](04a-historias-fundacion.md#hu-01-02) → [HU-01-03](04a-historias-fundacion.md#hu-01-03) → [HU-05-01](04c-historias-control.md#hu-05-01) (todo en C) | 31,5 | La política usa AreaAutorizada. Para no esperar, se acuerda su contrato en [HU-00-01](04a-historias-fundacion.md#hu-00-01) y [HU-05-01](04c-historias-control.md#hu-05-01) avanza con un doble hasta que [HU-01-03](04a-historias-fundacion.md#hu-01-03) la entregue. |
| Sprint 2 | [HU-01-04](04a-historias-fundacion.md#hu-01-04) → [HU-05-02](04c-historias-control.md#hu-05-02) / [HU-11-03](04e-historias-coding-harness.md#hu-11-03) → [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1) | 23 h de implementación cruzada (sin esperas) | La demo exige ticket, permisos, pruebas y verificación; [SPK-04](04d-historias-conexiones.md#spk-04) corre en paralelo sin prometer integración MCP. |
| Sprint 3 | [HU-09-01](04d-historias-conexiones.md#hu-09-01) → [HU-09-02](04d-historias-conexiones.md#hu-09-02)/03 → [HU-09-06](04d-historias-conexiones.md#hu-09-06) → [HU-11-04.2](04e-historias-coding-harness.md#hu-11-04.2) → [HU-11-05](04e-historias-coding-harness.md#hu-11-05) → [HU-11-06](04e-historias-coding-harness.md#hu-11-06) | Ruta crítica elevada; estimación por tareas del equipo | Contratos de delegación acordados al final de S2; comenzar [HU-09-01](04d-historias-conexiones.md#hu-09-01) al iniciar S3 y probar verticalmente desde el segundo día. |
| Sprint 4 | [SPK-04](04d-historias-conexiones.md#spk-04) (ejecutado en S2) → [HU-08-01](04d-historias-conexiones.md#hu-08-01) → [HU-08-02](04d-historias-conexiones.md#hu-08-02) → [HU-08-03](04d-historias-conexiones.md#hu-08-03); [HU-08-04](04d-historias-conexiones.md#hu-08-04) → [HU-00-05.2](04a-historias-fundacion.md#hu-00-05.2) | 45,5 h Alta del Sprint 4; spike ya no suma aquí | Semana aprobada PD-01; memoria, trazas y auxiliares en paralelo. Ratificar 11 PHU extra del reparto en Planning. |

Orden Sprint 2 (26–30/10): días 1–2, ticket y shell con política restrictiva; días 2–3, análisis de comandos, pruebas y contexto; días 3–4, verificación objetiva y permisos; en paralelo, [SPK-04](04d-historias-conexiones.md#spk-04) (4 h de C) investiga MCP y documenta contratos sin integrarlo; día 4, ensayo vertical; día 5, Review y retrospectiva. El spike no es requisito de la demo funcional del S2.

| Cuándo | Qué | Quién |
|---|---|---|
| Días 1–2 | [HU-11-01](04e-historias-coding-harness.md#hu-11-01) (ticket y criterios), [HU-01-04](04a-historias-fundacion.md#hu-01-04) (shell) y pruebas de integración tempranas. | A, C |
| Días 2–3 | [HU-05-02](04c-historias-control.md#hu-05-02) (comandos y permisos), [HU-11-03](04e-historias-coding-harness.md#hu-11-03) (pruebas), [HU-02-03](04b-historias-estado.md#hu-02-03) y [HU-02-06.1](04b-historias-estado.md#hu-02-06.1) (contexto). | C, B |
| Días 3–4 | [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1) (verificación), [HU-11-02](04e-historias-coding-harness.md#hu-11-02) (Git de lectura) y [HU-05-03](04c-historias-control.md#hu-05-03)/04 (aprobación y rechazo). [SPK-04](04d-historias-conexiones.md#spk-04) (4 h de C) investiga servidor MCP en paralelo, sin entrar a demo S2. | A, B, C |
| Día 4 | Demostración de ticket → cambios → pruebas → criterios, primero con FakeProvider y después con modelo real. | Todos |
| Día 5 | Review, retrospectiva y recalibración; confirmar responsables y secuencia de Sprint 3/4. | Todos |

Contingencia: las historias esenciales [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-11-03](04e-historias-coding-harness.md#hu-11-03), [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1), [HU-01-04](04a-historias-fundacion.md#hu-01-04) y [HU-05-02](04c-historias-control.md#hu-05-02) no se recortan silenciosamente. Ante menos horas de las previstas, el equipo recalcula el Sprint Backlog, pone en evidencia el Sprint Goal y solicita decisión al PO; no traslada tareas obligatorias a sprints futuros dando por cumplidos sus criterios originales.

### 13.7 Validación de trazabilidad

Los requisitos permanecen trazados a sus historias. RF-8.1 a RF-8.5 y RNF-8, RF-4.1 a RF-4.3, RF-10.1/10.2/10.4 y las funciones auxiliares diferidas tienen fecha objetivo S4. La investigación [SPK-04](04d-historias-conexiones.md#spk-04) se ejecuta en S2, sin declarar ya cumplida la integración. El registro mínimo seguro del Sprint 3 ([HU-05-05](04c-historias-control.md#hu-05-05) y [HU-07-05](04d-historias-conexiones.md#hu-07-05)) no sustituye las trazas completas de S4. Las pruebas de inyección MCP de [HU-05-08](04c-historias-control.md#hu-05-08) (Media) requieren MCP disponible.

| Revisión pedida | Cómo se comprueba | Resultado |
|---|---|---|
| Historias duplicadas o faltantes | El script cuenta los identificadores y los compara con F3, F4 y F5. | Sin hallazgos: 87 historias. |
| Identificadores incorrectos | Formato de cada identificador y búsqueda de historias citadas que no existen. | Sin hallazgos. Los identificadores HU-02-06, HU-00-05, HU-11-04 y HU-11-08 solo aparecen como historias divididas. |
| Sprint asignado en F3, F4 y F5 | Se lee el Word generado y se compara historia por historia. | Sin hallazgos. |
| Dependencias hacia sprints posteriores | Orden de sprint de cada dependencia; el compromiso no puede depender de la propuesta. | Sin hallazgos. |
| Obligatorias que dependen de opcionales | Prioridad de cada dependencia de cada historia de Alta. | Sin hallazgos (tres encontradas en la versión 2.2, resueltas). |
| Estimaciones entre secciones | Puntos de F3, F4 y totales de los sprints contra los datos. | Sin hallazgos. |
| Criterios de aceptación sin tareas | Cada ficha tiene criterios, títulos y tareas; las horas de F5 tienen una tarea cada una. | Pendiente de análisis semántico por historia y prueba real. La comprobación de identificadores no prueba cobertura de AC. |
| Tareas sin historia | Cada tarea de F5 lleva el identificador de una historia existente de su sprint. | Sin hallazgos: 212 tareas. |
| Demostraciones que prometen funcionalidad inexistente | Cada criterio de demostración lista sus historias; se comprueba que ellas y todo lo que necesitan estén en el sprint o antes y sean obligatorias. | Sin hallazgos. |
| Totales declarados contra reales | Portada, tabla de épicas y secciones 7 y 13 contra los datos. | Recalculado para v2.5 en sección 7. El resto del cuadro corresponde a la auditoría histórica de v2.3. |

### 13.8 Registro de decisiones (v3 incorporadas; tareas de ratificación pendientes)

PD-01: la cuarta semana fue aprobada por el PO el 17/10/2026 según registro de la v3, con cierre máximo el 14/11. La v3 aprobó 8 PHU de MCP en S4; esta consolidación mueve 11 PHU obligatorias adicionales allí y requiere ratificar ese reparto (no reaprobación de toda la semana). PD-03 está confirmada, PD-04 es obligatoria tras S1, PD-05 es provisional para el equipo y PD-06 sigue pendiente. PD-02 NO se aplica ni degrada requisitos sin resolver dependencias.

| Id | Decisión | Quién decide | Impacto | Estado / próximo control |
|---|---|---|---|---|
| PD-01 | Cuarta semana de desarrollo aprobada (17/10/2026, según v3); S4 integra MCP (8 PHU Alta). V2.5 redistribuye 11 PHU Alta adicionales a S4, sin alterar los 122 PHU totales del producto. | Product Owner | La APROBACIÓN de calendario y MCP consta en v3. La ampliación del reparto de S4 a 19 PHU Alta es una propuesta de replanificación que necesita ratificación de PO y equipo, no se da por autorizada automáticamente. El cierre máximo indicado es 14/11/2026. | SEMANA APROBADA; reparto adicional por ratificar en Planning. |
| PD-02 | Si se rechaza PD-01, renegociar alcance/plazo con matriz de dependencias y requisitos. No bajar automáticamente [HU-07-05](04d-historias-conexiones.md#hu-07-05) (Alta) a Media mientras [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1) (Alta) depende de ella. | Product Owner | Las candidatas anteriores [HU-07-05](04d-historias-conexiones.md#hu-07-05) y [HU-04-02](04b-historias-estado.md#hu-04-02) NO constituyen un plan alterno válido por sí solas: arrastran pruebas o cobertura de requisitos. Se debe elaborar y aprobar otro escenario verificable. | NO APLICADA. Solo se reabre si falla la capacidad tras Sprint 1. |
| PD-03 | Confirmar que [HU-08-04](04d-historias-conexiones.md#hu-08-04) vuelve a prioridad Alta (RF-8.5 vuelve a Must). | Product Owner | Confirmado en v3: [HU-08-04](04d-historias-conexiones.md#hu-08-04) Alta (RF-8.5 Must); [HU-00-05.2](04a-historias-fundacion.md#hu-00-05.2) prueba MCP en S4. | CONFIRMADA. |
| PD-04 | Recalibrar la velocidad con los puntos realmente terminados en el Sprint 1. | Product Owner y equipo | Recalibrar tras Sprint 1. Estimaciones v2.5: S1 104,5; S2 101; S3 94,5; S4 45,5 h. No usar 39 PHU como velocidad demostrada. | OBLIGATORIA al cerrar Sprint 1 (23/10/2026). |
| PD-05 | Confirmar reasignaciones del escenario v2.4: [HU-03-04](04b-historias-estado.md#hu-03-04) B→A, [HU-11-02](04e-historias-coding-harness.md#hu-11-02) C→B, [HU-05-04](04c-historias-control.md#hu-05-04) C→A, [HU-09-01](04d-historias-conexiones.md#hu-09-01) A→B, [HU-09-02](04d-historias-conexiones.md#hu-09-02) A→C, [HU-11-06](04e-historias-coding-harness.md#hu-11-06) A→C y [HU-05-05](04c-historias-control.md#hu-05-05) C→B. Permanecen cambios previos [HU-00-02](04a-historias-fundacion.md#hu-00-02) C→A y [HU-02-02](04b-historias-estado.md#hu-02-02) A→C. | Equipo | V3 aceptó provisionalmente tres reasignaciones; v2.4 introdujo otras para equilibrar horas. La distribución completa v2.5 requiere confirmación de A, B y C. S2 A31,5/B32,5/C37 h; S3 A30/B33/C31,5 h. | PROVISIONAL; confirmar en Planning S1. |
| PD-06 | Incluir [HU-IN-02](04d-historias-conexiones.md#hu-in-02) (entorno aislado, 5 PHU) si se quiere un aislamiento verificable de los criterios y del shell. | Product Owner | Sin separación efectiva de privilegios o aislamiento, SQLite y JSON de solo lectura son controles lógicos, NO garantía de inmutabilidad frente a shell arbitrario. [HU-IN-02](04d-historias-conexiones.md#hu-in-02) sigue fuera del compromiso hasta decisión del PO. | PENDIENTE (riesgo R-21 aceptado hasta decisión de PO). |

### 13.9 Resultado de consolidación y riesgos residuales

| Sprint | Alta comprometida 1–3 | Alta asignada en S4 (ratificar reparto) | Media opcional |
|---|---|---|---|
| Sprint 1 | 39 | — | 0 |
| Sprint 2 | 31 | — | 0 |
| Sprint 3 | 33 | — | 18 |
| Sprint 4 | — | 19 | 10 |
| Total | 103 | 19 | 28 |

Corregido en v2.5 respecto a v2.4:

Se incorpora la aprobación de la cuarta semana y el plazo máximo de v3, sin trasladar automáticamente la aprobación de su reparto de solo 8 PHU MCP al reparto ampliado de 19 PHU del Sprint 4 actual.

[SPK-04](04d-historias-conexiones.md#spk-04) adelanta sus 4 h desde S4 a S2: este último pasa de 97 a 101 h y de 30 a 31 PHU Alta. S4 pasa de 49,5 a 45,5 h y de 20 a 19 PHU. Ninguna estimación individual se altera.

Los registros mínimos del S3 se hacen explícitamente redactados dentro de [HU-05-05](04c-historias-control.md#hu-05-05), y la conmutación de [HU-07-05](04d-historias-conexiones.md#hu-07-05) se guarda como evento de sesión; las trazas completas siguen en [HU-10-01](04d-historias-conexiones.md#hu-10-01)/02 en S4. F3, F4, F5, tareas y fechas de sprint se mantienen sincronizadas.

Las demostraciones no atribuyen funcionalidades de S4 a S2 o S3. El aislamiento fuerte de la base SQLite frente a shell arbitrario no está demostrado y requiere decisión PD-06. La documentación tiene 212 tareas; cada criterio nuevo tiene una tarea responsable en F5.

PD-01 de v3 cierra la duda sobre disponibilidad de una cuarta semana, pero PD-05 y la validación de la redistribución ampliada en Sprint 4 siguen abiertos. PD-02 requiere un plan alternativo íntegro y verificable, no un descenso aislado de prioridades.

La auditoría estructural comprueba unicidad de las 212 tareas, concordancia F3/F4/F5, precedencias y demos; no sustituye la revisión por desarrolladores de cobertura de AC, calidad real del código ni capacidad observada tras el Sprint 1.

Riesgos residuales y controles:

El Sprint 1 excede la disponibilidad media por 8,5 h; Sprint 2 la supera por 5 h y C tiene 37 h. Aunque ambos están por debajo del escenario alto, el equipo debe confirmar la disponibilidad y margen de integración antes de comprometer fechas.

La aprobación de la cuarta semana no certifica disponibilidad personal ni valida por sí sola el reparto adicional del Sprint 4. Formalizar en Planning que las 11 PHU diferidas se incluyen y qué integrante asumirá cada historia.

El shell con permisos del mismo sistema operativo puede acceder a SQLite fuera de las herramientas controladas; el aislamiento real se evalúa por PD-06 (R-21).

Las horas son preliminares y omiten el riesgo de integración; el equipo debe confirmar distribución y límites antes de comenzar.

El mayor riesgo técnico de Sprint 3 es la cadena de subagentes hasta Pull Request, comprimida en una semana. Conviene validar los contratos de delegación al final del Sprint 2 sin declarar implementada la historia.

### 13.10 Historial de versiones 2.2 y 2.3

La versión 2.2 reestructuró los Sprint Backlogs en cortes verticales: el Sprint 2 pasó a entregar un primer flujo del Coding Harness (ticket → agente → pruebas → verificación) en lugar de módulos técnicos, y HU-11-04 y HU-11-08 se dividieron en .1 y .2. Problemas que atendía:

| Problema | Evidencia en el plan 2.1 | Consecuencia |
|---|---|---|
| El flujo diferenciador llegaba al final | Los 12 puntos obligatorios de E11 estaban en el Sprint 3, junto con el resto de la integración. | El primer recorrido ticket → verificación ocurría en la última semana, sin margen para corregir. |
| Una dependencia empujaba toda la verificación al Sprint 3 | HU-11-04 dependía de [HU-09-06](04d-historias-conexiones.md#hu-09-06) (subagente verificador, Sprint 3), aunque comprobar criterios objetivos solo necesita ejecutar comandos. | La parte más sencilla de la verificación quedaba atada a la más compleja. Se divide en [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1) (comandos, Sprint 2) y [HU-11-04.2](04e-historias-coding-harness.md#hu-11-04.2) (verificador, Sprint 3). |
| Los incrementos de los Sprints 1 y 2 eran técnicos, no de producto | El Sprint 2 de la versión 2.1 cerraba aprobación, compactación, reanudación y delegación básica, pero ningún recorrido del Coding Harness. | Podían terminarse todos los módulos sin saber si el flujo del producto funciona. |
| Capacidad sin margen | El alcance obligatorio sumaba 119 puntos frente a 117 de capacidad inicial en tres sprints (39 por sprint), sin tiempo para integración ni contingencias. | Reordenar no crea capacidad: el plan nuevo suma 120 puntos obligatorios y lo señala en la sección de capacidad. |

### 13.11 Historial de la propuesta v2.4 (superada por v2.5)

REGISTRO HISTÓRICO: cuando se elaboró la v2.4, la cuarta semana aún no figuraba aprobada. La versión v3 incorporada en v2.5 registró la aprobación el 17/10/2026 y el cierre máximo el 14/11/2026. Prevalece la distribución operativa v2.5 en F3–F5 sobre las cifras y condiciones históricas aquí explicadas.

En v2.4 se retiraron de Sprint 2 los subagentes, la continuidad por progreso y el spike MCP para proteger el corte vertical. En v2.5 se devuelve solo [SPK-04](04d-historias-conexiones.md#spk-04) a S2 como investigación anticipada; subagentes y continuidad siguen en S3.

La propuesta v2.4 trasladó memoria, trazabilidad completa, listado y preguntas a Sprint 4; v2.5 conserva esa redistribución para reducir la carga previa al Pull Request. La prioridad Alta permanece; la aprobación del PO de v3 abarcaba la semana y MCP, por lo que la asignación del resto debe ratificarse.

Balance histórico v2.4 (NO vigente): S1 39 PHU/104,5 h; S2 30 PHU/97 h; S3 33 PHU/94,5 h; S4 20 PHU/49,5 h. Balance vigente v2.5: S1 39/104,5; S2 31/101; S3 33/94,5; S4 19/45,5. Total 122 PHU Alta en ambos.

Las decisiones sobre fechas y compromisos se encuentran en la sección 13.8 actualizada. Cualquier recorte de alcance exige acuerdo formal del PO y respeto de pruebas y dependencias. Las historias Media solo se atienden después del mínimo obligatorio.

Seguridad: SQLite es fuente de verdad lógica, no una barrera de aislamiento frente a cualquier comando ejecutado con el mismo usuario del sistema operativo. R-21 sigue abierto. Para demostrar que los criterios no son editables por shell arbitrario, se necesita separar identidades/permisos del proceso verificador o ejecutar las herramientas del agente en un sandbox operativo verificable; no basta con un JSON de solo lectura.

Validación en Planning S1/S2: comprobar disponibilidad real, ratificar 11 PHU trasladadas al Sprint 4 y responsables, ejecutar [SPK-04](04d-historias-conexiones.md#spk-04) (26–30/10), comprobar permisos y acceso a SQLite, ensayar el flujo ticket→tests→criterios con FakeProvider y cotejar AC con tareas y pruebas.

Sincronización: esta entrega actualiza exclusivamente el Word. Los Excel/Markdown anteriores (v3) NO quedan sincronizados automáticamente: deben regenerarse desde el mismo inventario y auditarlos antes de su publicación.

### 13.12 Consolidación v2.5 — decisiones operativas (prevalece sobre las tablas históricas 2.3/2.4)

Origen de decisiones: documento «analisis_scrum_harness_f_v3.docx», sección 13.8, registra PD-01 aprobada el 17/10/2026 con límite 14/11/2026; PD-03 confirmada; PD-04 obligatoria; PD-05 provisional; PD-06 pendiente. La estructura y redistribución por capacidad proceden del Word v2.4. No se incorporan los excesos del Sprint 2 de v3.

Calendario de trabajo propuesto: S1 19–23/10, S2 26–30/10, S3 02–06/11, S4 09–13/11. El último día hábil se deja para integración, revisión y demo antes del cierre máximo registrado de 14/11/2026. Estas fechas distribuyen la semana autorizada; el Planning ratifica sus compromisos por persona.

Cambio funcional: [SPK-04](04d-historias-conexiones.md#spk-04) regresa a Sprint 2 como investigación de 4 h/1 PHU (responsable C) y sirve para reducir incertidumbre de MCP antes de Sprint 4. No se adelantan [HU-08-01](04d-historias-conexiones.md#hu-08-01) a [HU-08-04](04d-historias-conexiones.md#hu-08-04), ni se promete MCP en Sprint 2. La demostración de Sprint 2 sigue siendo ticket→modificaciones→tests→verificación.

Seguridad por fases: [HU-05-05](04c-historias-control.md#hu-05-05) en S3 garantiza el registro mínimo de decisiones con argumentos redactados antes de guardar; [HU-07-05](04d-historias-conexiones.md#hu-07-05) registra conmutación como evento de sesión. [HU-10-01](04d-historias-conexiones.md#hu-10-01) y [HU-10-02](04d-historias-conexiones.md#hu-10-02) en S4 implementan trazas exhaustivas de modelo y herramientas con redacción general. Ni los registros mínimos ni SQLite por sí solos prueban aislamiento del shell frente a acceso arbitrario con la misma identidad del sistema operativo; PD-06 continúa abierto.

Capacidad real planificada por F5 (solo Alta): S1 39 PHU/104,5 h (A 33,5; B 34,5; C 36,5); S2 31 PHU/101 h (A 31,5; B 32,5; C 37); S3 33 PHU/94,5 h (A 30; B 33; C 31,5); S4 19 PHU/45,5 h (A 4,5; B 20; C 21). Total 122 PHU y 345,5 h. Historias Media: 28 PHU no comprometidas, con prioridad sin modificar.

Pendiente de validación: la aprobación de la cuarta semana con 8 PHU MCP no implica aprobar automáticamente la asignación ampliada de 19 PHU Alta al Sprint 4. El PO y el equipo deben ratificar 11 PHU reubicadas y la distribución de responsables, sin reducir requisitos ni suponer 31 PHU de holgura. Recalibrar la velocidad observada y las horas tras Sprint 1 es obligatorio.

Control documental: este Word es la fuente actual de decisiones y estimaciones de v2.5. Las hojas Excel y el .md heredados de v3 NO se consideran sincronizados con el reparto de v2.5 hasta regeneración y auditoría por identificador de historia, prioridad, sprint, dependencias, F5, horas y criterios de demostración.

### 13.13 Observaciones de la revisión del .md frente al Word v2.5

- [HU-11-01](04e-historias-coding-harness.md#hu-11-01): el resumen F3 del Word conserva el texto anterior («que los criterios se guarden donde el agente no pueda cambiarlos»), mientras que la ficha F4 dice que el harness niega cambios mediante herramientas controladas y registra anomalías. Este .md usa la ficha F4, que es la más reciente y la coherente con R-21 y PD-06.
- Demostración del Sprint 2, criterio 2: dice que un intento de modificar los criterios se bloquea «por las herramientas de archivos o por el shell», pero R-21, PD-06 y el texto de la demostración dicen que no se afirma aislamiento frente a un shell arbitrario. Leerlo como bloqueo por herramientas controladas y comandos identificables.
- La portada habla de 12 PHU añadidas por v2.4 al Sprint 4; el resto del documento habla de 11. La diferencia es [SPK-04](04d-historias-conexiones.md#spk-04) (1 PHU), que v2.5 devolvió al Sprint 2. Vale 11.
- 13.7, fila «Dependencias hacia sprints posteriores»: conserva la frase de v2.3 («el compromiso no puede depender de la propuesta»). Las secciones 13.1 a 13.4 y 13.10 son históricas de v2.3 y todavía dicen «Sprint 4 propuesto»; prevalecen 13.8 y 13.12.
- 13.6, ruta crítica: en las filas de los Sprints 2 y 3 la columna «Horas» contiene texto («23 h de implementación cruzada…», «Ruta crítica elevada…») en lugar de un número.
- Sección 13.5 del Word: los criterios de demostración de los Sprints 2, 3 y 4 no coinciden palabra por palabra con los de F5. En el Sprint 3, la fila 4 de 13.5 repite la fila 7 (pruebas de fallos y auditoría mínima) y omite el criterio de que push y Pull Request siempre piden aprobación; en el Sprint 4, 13.5 tiene 4 filas frente a 3 viñetas en F5, y la cuarta dice «solo si PD-01 se aprueba» aunque PD-01 ya está aprobada. Este .md usa los criterios de F5 en la sección 8.
- Si el reparto ampliado no se ratifica: las 11 PHU Alta de las historias por ratificar (25 h de tareas) volverían al Sprint 3, que pasaría de 33 a 44 PHU Alta y de 94,5 a 119,5 h, frente a 96 h netas medias del equipo y 121,5 h del escenario alto. Si además se devuelven al Sprint 2 [HU-09-01](04d-historias-conexiones.md#hu-09-01), [HU-09-02](04d-historias-conexiones.md#hu-09-02) y [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1) (8 PHU, 21,5 h), el Sprint 2 sube a 39 PHU y a 122,5 h, por encima de las 121,5 h del escenario alto. Ninguna de las dos variantes cabe con la reserva del 20 %; por eso la ratificación o una alternativa verificable es necesaria antes del Planning del Sprint 3.

---

[← 05-trazabilidad.md](05-trazabilidad.md) · [Índice](00-indice.md) · [PROGRESO.md →](PROGRESO.md)
