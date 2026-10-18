# Visión, alcance y decisiones de diseño

> [← 00-indice.md](00-indice.md) · [Índice](00-indice.md) · [02-arquitectura.md →](02-arquitectura.md)  
> Estado del plan y secciones 1, 2 y 5 del contexto original.  
> Ver también: [02-arquitectura.md](02-arquitectura.md) · [03-plan-sprints.md](03-plan-sprints.md) · [04a-historias-fundacion.md](04a-historias-fundacion.md)

> **Estado del plan (17/10/2026):** fuente de verdad = Word «HARNESS Análisis Scrum v2.5 consolidada». Cuarta semana aprobada por el Product Owner (PD-01) con cierre máximo el 14/11/2026. **Pendiente de ratificar en el Planning:** el reparto ampliado del Sprint 4 (11 PHU Alta adicionales: [HU-03-03](04b-historias-estado.md#hu-03-03), [HU-04-01](04b-historias-estado.md#hu-04-01), [HU-04-02](04b-historias-estado.md#hu-04-02), [HU-06-02](04c-historias-control.md#hu-06-02), [HU-10-01](04d-historias-conexiones.md#hu-10-01), [HU-10-02](04d-historias-conexiones.md#hu-10-02)); la aprobación solo cubre las 8 PHU de MCP. Mientras no se ratifique, trátalo como plan base provisional.

## 1. Qué es y cómo se trabaja

Un **harness** es la aplicación que rodea a un modelo de lenguaje (el «cerebro») y lo conecta con el mundo: bucle de razonar–actuar–observar, herramientas, permisos, contexto, memoria, sesiones. Este proyecto construye uno propio, en terminal, con un núcleo reutilizable y desacoplado de la interfaz.

| Tema | Decisión |
|---|---|
| Equipo | 3 personas: A = Núcleo, B = Estado, C = Control y conexiones |
| Plazo | 4 sprints semanales. Cuarta semana aprobada por el PO el 17/10/2026 (PD-01 de v3); distribución ampliada de v2.5 pendiente de ratificar en Planning. |
| Disponibilidad | 15 a 28 h por semana en días hábiles más sábados y domingos completos (27 a 44 h por sprint). Velocidad hipotética: 39 PHU por sprint para el equipo (no por persona); las horas se estiman por tarea y solo contrastan carga con disponibilidad; se recalibra tras el Sprint 1 |
| Product Owner | Brad (tiene la rúbrica) |
| Scrum Master | Rotación: S1=A, S2=B, S3=C; S4=A provisional, por ratificar por el equipo. |
| Sistemas operativos | Windows y Linux (Arch). Integración continua en ambos |
| Lenguaje | Python 3.12.x (única versión soportada, PD-07). TypeScript solo si se hace la interfaz web |
| Interfaz | Terminal (CLI). El núcleo emite eventos por un bus y nunca imprime, para añadir web (FastAPI/WebSocket) sin tocarlo |
| Proveedores | LiteLLM detrás de una interfaz propia `Provider`. Al menos dos de Claude, OpenAI y Gemini (por decidir; presupuesto de API por definir) |
| Persistencia | SQLite (sesiones, eventos, memoria, auditoría, trazas) |
| Herramientas externas | Cliente MCP (SDK de Python), stdio primero. Servidor de demostración local y sin credenciales (se elige en [SPK-04](04d-historias-conexiones.md#spk-04)) |
| Reto | Subagentes con contexto aislado (obligatorio) |
| Enfoque | Coding Harness basado en tickets (Proyecto 1 de los apuntes). Si hay tiempo, también el Proyecto 2 |
| Plazo informado | Cierre confirmado en el documento v3: a más tardar el 14 de noviembre de 2026. Ventanas de trabajo propuestas: S1 19–23/10; S2 26–30/10; S3 02–06/11; S4 09–13/11. Presentaciones intermedias cada 1–2 semanas sin fecha fija. |
| Estimación | Puntos de historia (PHU) con Fibonacci, relativos y leídos como velocidad del equipo; planning poker en el Sprint 1 |

Reglas del equipo: cada área tiene un dueño, pero todo cambio lo revisa otra persona. Definition of Done:
- El código está integrado y la integración continua pasa.
- Tiene pruebas y cumple los criterios de aceptación.
- Pasa el verificador de tipos y el formateador.
- No introduce secretos en el código ni en los registros.
- Otro integrante la revisó.
- Se mostró en la demostración del sprint.

## 2. Alcance

**Enfoque:** Coding Harness basado en tickets (Proyecto 1 de los apuntes de la cátedra) sobre un núcleo general. Si hay tiempo, se muestra también el Proyecto 2 (agente con herramientas), que el núcleo ya cubre. Flujo de la demostración: ticket → agente → análisis → cambios → pruebas → verificación de criterios → aprobación humana → Pull Request.

- **Obligatorio (prioridad Alta):** bucle con herramientas, contexto con compactación, sesiones reanudables, memoria, permisos con aprobación humana, CLI, dos proveedores con conmutación por fallo, MCP, subagentes, trazas y el flujo de tarea con criterios protegidos en SQLite, Git y pruebas por shell, subagente verificador, aprobación del diff, Pull Request y relevo entre sesiones con archivo de progreso (E11).
- **Si hay capacidad (Media):** varias llamadas por turno, detección de repeticiones, compactación manual, costos, memoria editable, modo solo lectura, reglas por archivo, subagente explorador y reglas de permisos por archivo.
- **Innovación (después del mínimo):** interfaz web, ejecución en entorno aislado, comparación con LangGraph, panel de costos.


## 5. Decisiones de diseño que no se negocian

Salen de revisar los requisitos. Cada una tiene historias asociadas.

| Id | Hallazgo y decisión | Historias |
|---|---|---|
| V-01 | **La aprobación necesita comunicación en dos sentidos.** El bus de eventos solo emite. Para pedir aprobación el núcleo debe esperar una respuesta de la interfaz. El núcleo espera una decisión asíncrona (interfaz Approver). Se confirma con [SPK-02](04a-historias-fundacion.md#spk-02). | [HU-01-05](04a-historias-fundacion.md#hu-01-05), [HU-05-03](04c-historias-control.md#hu-05-03), [SPK-02](04a-historias-fundacion.md#spk-02) |
| V-02 | **«Aprobar para la sesión» podía saltarse una denegación.** La captura no decía qué pasa si existe una regla de denegar. Denegar siempre gana. La aprobación de sesión se limita a una herramienta y un patrón de argumentos. | [HU-05-02](04c-historias-control.md#hu-05-02), [HU-05-03](04c-historias-control.md#hu-05-03) |
| V-03 | **Compactar no debe borrar historial.** RF-2 y RF-3 chocaban: reanudar exige el historial completo. La compactación añade un evento de resumen y marca los eventos cubiertos; el original permanece en SQLite. | [HU-02-03](04b-historias-estado.md#hu-02-03), [HU-03-02](04b-historias-estado.md#hu-03-02) |
| V-04 | **El objetivo y las decisiones no pueden vivir en el historial compactable.** Un resumen mal hecho podía perder la tarea original. El objetivo, las instrucciones, las reglas, el ticket y la referencia a los criterios se guardan aparte (contexto esencial, desde el Sprint 2) y se inyectan siempre en el prefijo; las decisiones del usuario se acumulan en el mismo bloque (Sprint 3). No requiere la memoria estructurada. | [HU-02-06.1](04b-historias-estado.md#hu-02-06.1), [HU-02-06.2](04b-historias-estado.md#hu-02-06.2) |
| V-05 | **«Relevancia» de la memoria no estaba definida.** Sin embeddings no hay medida de similitud. Relevancia = recencia dentro de un presupuesto de tokens. Embeddings pasan a innovación. | [HU-04-02](04b-historias-estado.md#hu-04-02) |
| V-06 | **El contrato del subagente era vago.** No se sabía qué recibe ni qué devuelve. Entrada: objetivo, contexto mínimo y formato de salida. Salida: resultado, hallazgos clave, fuentes y error. Las aprobaciones suben al usuario. | [HU-09-01](04d-historias-conexiones.md#hu-09-01), [HU-09-02](04d-historias-conexiones.md#hu-09-02), [HU-09-03](04d-historias-conexiones.md#hu-09-03) |
| V-07 | **RNF-5 medía algo que no controlamos.** La latencia del modelo no depende del harness. Se mide el tiempo propio del harness por turno con proveedor simulado. | [HU-00-05.1](04a-historias-fundacion.md#hu-00-05.1) |
| V-08 | **Windows y macOS cambian el shell y la lista de comandos peligrosos.** El equipo usa Windows y Linux (Arch). Intérprete y lista de denegación para Windows y Linux; la integración continua corre en ambos. | [HU-01-04](04a-historias-fundacion.md#hu-01-04), [HU-00-02](04a-historias-fundacion.md#hu-00-02) |
| V-09 | **El conteo exacto de tokens no existe para todos los modelos.** Cada proveedor cuenta distinto. Estimación heurística corregida con el uso real que informa la API en cada respuesta. | [HU-02-01](04b-historias-estado.md#hu-02-01) |
| V-10 | **El umbral de compactación depende del modelo.** Al conmutar de proveedor cambia la ventana disponible. El umbral se calcula por modelo y se recalcula al conmutar. | [HU-02-03](04b-historias-estado.md#hu-02-03), [HU-07-05](04d-historias-conexiones.md#hu-07-05) |
| V-11 | **Cancelar una herramienta en curso no estaba definido.** Interrumpir con Ctrl+C podía dejar el estado a medias. La herramienta se cancela, se registra como interrumpida y el modelo recibe ese resultado en el siguiente turno. | [HU-06-03](04c-historias-control.md#hu-06-03) |
| V-12 | **Faltaba un archivo de instrucciones del proyecto.** Es práctica común en harnesses actuales. Se añade RF-2.9 (Could): cargar un archivo de instrucciones al prefijo. | [HU-02-07](04b-historias-estado.md#hu-02-07) |
| V-13 | **La detección de secretos no puede ser total.** No existe garantía absoluta. Se declara el alcance: patrones conocidos más los valores de las variables de entorno cargadas. | [HU-04-05](04b-historias-estado.md#hu-04-05), [HU-10-02](04d-historias-conexiones.md#hu-10-02) |
| V-14 | **Hace falta un proveedor simulado.** Sin él las pruebas dependen de la red y de la cuota. Se crea FakeProvider en el Sprint 1 como base de todas las pruebas. | [HU-00-03](04a-historias-fundacion.md#hu-00-03) |
| V-15 | **El agente podía dar por terminada una tarea sin estarlo.** Si el propio modelo marca sus criterios como cumplidos, el cierre depende de su palabra. El artículo de Anthropic lo llama «victoria prematura». Los criterios viven en la tabla criterios de SQLite (fuente de verdad), con una copia JSON de solo lectura que el harness restaura si cambia. Solo el harness cambia «passes»: los criterios objetivos, con el resultado de su comando de verificación; los semánticos, solo con confirmación humana. El subagente verificador aporta evidencia, no decide. | [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1), [HU-11-04.2](04e-historias-coding-harness.md#hu-11-04.2), [HU-09-06](04d-historias-conexiones.md#hu-09-06), [HU-11-05](04e-historias-coding-harness.md#hu-11-05) |
| V-16 | **Una sesión nueva de un mismo ticket no sabe qué pasó antes.** Sin memoria entre ventanas de contexto, el agente adivina el estado o construye sobre código roto. Rutina de arranque fija: leer el archivo de progreso y el log de git, correr la prueba básica y reparar antes de avanzar. Al cerrar, se anota el progreso. | [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1), [HU-11-08.2](04e-historias-coding-harness.md#hu-11-08.2), [HU-03-04](04b-historias-estado.md#hu-03-04) |
| V-17 | **Con un shell general los permisos se aplican sobre texto libre.** Un comando encadenado (a && b \| c) puede esconder una acción peligrosa detrás de una permitida. Se separa el comando, se evalúa cada parte y manda la más restrictiva; lo que no se entiende se pregunta. Push y merge siempre piden aprobación. | [HU-05-02](04c-historias-control.md#hu-05-02), [HU-11-02](04e-historias-coding-harness.md#hu-11-02) |

Cambios a la captura de requisitos:

| Requisito | Cambio |
|---|---|
| RF-11 (nuevo) | Coding Harness del ticket al Pull Request: tarea con criterios protegidos en SQLite y una copia JSON de solo lectura (11.1), Git por shell con reglas de permisos (11.2), pruebas y lint por shell (11.3), verificación de criterios por el harness, primero con comandos objetivos y luego con subagente verificador (11.4), aprobación del diff (11.5), Pull Request (11.6), worktree por ticket (11.7, Should) y arranque de sesión con archivo de progreso (11.8). Viene de los apuntes de la cátedra y del artículo de Anthropic sobre agentes de larga duración. |
| Herramientas (precisado) | El conjunto mínimo es shell, leer, escribir y editar archivos, preguntar al usuario y delegar en un subagente. Git, pruebas y lint ya no son herramientas propias: son comandos del shell bajo reglas de permisos ([HU-11-02](04e-historias-coding-harness.md#hu-11-02), [HU-11-03](04e-historias-coding-harness.md#hu-11-03) bajan a 1 punto cada una). Memoria y MCP se registran igual, como complementos. |
| RF-1.2 (precisado) | El shell es portable: PowerShell en Windows y bash en Linux detrás de una misma interfaz, y el prefijo del contexto dice al modelo cuál usa ([HU-01-04](04a-historias-fundacion.md#hu-01-04) sube de 2 a 3 puntos). |
| RF-5.2 (precisado) | Los comandos encadenados se separan y se evalúa cada parte; manda la más restrictiva y lo que no se entiende se pregunta ([HU-05-02](04c-historias-control.md#hu-05-02) sube de 1 a 2 puntos). |
| RF-9.8 (re-priorizado) | El subagente verificador pasa de Should a Must: respalda el cierre de la tarea ([HU-09-06](04d-historias-conexiones.md#hu-09-06)). |
| RF-4.6, RF-6.6 (re-priorizados) | Pasan de Must a Should para hacer espacio: no guardar secretos en memoria y el conjunto de comandos de control de la sesión. Siguen vigentes la redacción de secretos en registros (RF-10.4) y los comandos propios de listar ([HU-03-03](04b-historias-estado.md#hu-03-03)) y reanudar ([HU-03-04](04b-historias-estado.md#hu-03-04)). |
| RF-7.5, RF-9.7 (re-priorizados) | Pasan de Must a Should para hacer espacio a RF-11: reintentos con espera y errores explícitos del subagente. También pasan a opcionales la prueba de inyección de prompt (RNF-17/18) y la cobertura mínima (RNF-11/14). La conmutación por fallo (RF-7.4) ya no depende de los reintentos. |
| RF-8.5 (vuelve a Must en la versión 2.3) | El aislamiento de fallos de un servidor MCP se había pasado a Should en la versión 2.1. La prueba de fallos de MCP (RNF-8) es un requisito original y no puede quedar atada a una historia opcional, así que [HU-08-04](04d-historias-conexiones.md#hu-08-04) vuelve a prioridad Alta. Está pendiente de confirmar por el Product Owner (PD-03). |
| RF-5.1 (precisado) | Borrar archivos, push, merge y deploy siempre requieren aprobación. |
| RF-2.9 (nuevo, Could) | Cargar un archivo de instrucciones del proyecto en el prefijo del contexto. |
| RF-2.4 (precisado) | La compactación conserva el historial original y no puede eliminar el objetivo ni las decisiones del usuario. |
| RF-4.3 (precisado) | Relevancia de la memoria = recencia dentro de un presupuesto de tokens. |
| RF-5.4 (precisado) | Aprobar para la sesión nunca anula una regla de denegar y se limita a herramienta y patrón. |
| RF-9 (precisado) | Se define el contrato de entrada y salida del subagente y la subida de aprobaciones al usuario. |
| RNF-5 (reformulado) | Se mide el tiempo propio del harness por turno, no la latencia del modelo. |

Decisiones tomadas:

| Pregunta | Respuesta |
|---|---|
| ¿Cuál de los tres tipos de harness de los apuntes se hace? | El Proyecto 1: Coding Harness basado en tickets, construido sobre el núcleo general. Si da tiempo, se muestra también el Proyecto 2 (agente con herramientas), que el núcleo ya cubre. |
| ¿Cuándo termina el proyecto? | Hasta noviembre, posiblemente a mediados. Habrá presentaciones cada una o dos semanas, sin fecha fija. Es solo informativo: el plan sigue en 3 sprints y lo que sobre pasa a un posible cuarto. |
| ¿El límite de costo en dinero o en tokens? | En tokens. El costo en moneda es solo informativo. |
| ¿Dónde vive la memoria? | En SQLite, con el comando /memoria para consultarla y borrarla. |
| ¿Qué sistema operativo usa cada integrante? | Windows y Linux (Arch Linux). La integración continua y el shell cubren ambos. |
| ¿Quién es el Product Owner? | Brad. |
| ¿Cuántas horas tiene cada persona? | 15 a 28 horas por semana en los 5 días hábiles, más los sábados y domingos completos. Equivale a unas 27 a 44 horas por sprint, según cuánto se trabaje el fin de semana. |
| ¿Qué herramientas tiene el agente? | Un conjunto mínimo: shell, leer, escribir y editar archivos, preguntar al usuario y delegar en un subagente. Memoria y MCP son complementos. Git, pruebas y lint van por el shell bajo reglas de permisos. |
| ¿Cómo se pasa el trabajo entre sesiones de un mismo ticket? | Con los criterios guardados en SQLite (con una copia JSON de solo lectura), un archivo de progreso en el repositorio y el log de git, más una prueba básica antes de avanzar (patrón del artículo de Anthropic). |
| ¿Cuándo se demuestra por primera vez el flujo del Coding Harness? | Al final del Sprint 2, de ticket a verificación de criterios, sin commit ni Pull Request. El Sprint 3 lo completa: verificador independiente, aprobación del diff, commit y Pull Request. |
| ¿Qué servidor MCP usamos en la demostración? | Se elige en [SPK-04](04d-historias-conexiones.md#spk-04): servidor local por stdio, sin credenciales. |

Preguntas abiertas:

| Pregunta | Por qué importa | Cuándo se cierra |
|---|---|---|
| ¿Qué dos modelos entre Claude, OpenAI y Gemini, y con qué presupuesto de API? | Define el proveedor principal y el de respaldo ([HU-07-02](04d-historias-conexiones.md#hu-07-02), [HU-07-03](04d-historias-conexiones.md#hu-07-03), [SPK-01](04d-historias-conexiones.md#spk-01)). | Antes de [SPK-01](04d-historias-conexiones.md#spk-01) |
| ¿Se confirma asyncio como modelo de concurrencia? | Depende del resultado de [SPK-02](04a-historias-fundacion.md#spk-02). | Fin del Sprint 1 |
| ¿Se dejan listar y buscar archivos como herramientas propias o se resuelven con el shell? | Afecta a [HU-01-03](04a-historias-fundacion.md#hu-01-03) (3 puntos) y a cuántas herramientas ve el modelo. | Planning del Sprint 1 |

---

[← 00-indice.md](00-indice.md) · [Índice](00-indice.md) · [02-arquitectura.md →](02-arquitectura.md)
