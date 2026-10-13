# Visión, alcance y decisiones de diseño

> [← 00-indice.md](00-indice.md) · [Índice](00-indice.md) · [02-arquitectura.md →](02-arquitectura.md)  
> Secciones 1, 2 y 5 del contexto original.  
> Ver también: [02-arquitectura.md](02-arquitectura.md) · [03-plan-sprints.md](03-plan-sprints.md) · [04a-historias-fundacion.md](04a-historias-fundacion.md)

## 1. Qué es y cómo se trabaja

Un **harness** es la aplicación que rodea a un modelo de lenguaje (el «cerebro») y lo conecta con el mundo: bucle de razonar–actuar–observar, herramientas, permisos, contexto, memoria, sesiones. Este proyecto construye uno propio, en terminal, con un núcleo reutilizable y desacoplado de la interfaz.

| Tema | Decisión |
|---|---|
| Equipo | 3 personas: A = Núcleo, B = Estado, C = Control y conexiones |
| Plazo | 3 sprints de 1 semana |
| Disponibilidad | 15 a 28 h por semana en días hábiles más sábados y domingos completos (27 a 44 h por sprint). Capacidad usada: 13 PHU por persona y sprint (≈ 32 h); se recalibra tras el Sprint 1 |
| Product Owner | Brad (tiene la rúbrica) |
| Scrum Master | Rota: Sprint 1 = A, Sprint 2 = B, Sprint 3 = C |
| Sistemas operativos | Windows y Linux (Arch). Integración continua en ambos |
| Lenguaje | Python 3.12+. TypeScript solo si se hace la interfaz web |
| Interfaz | Terminal (CLI). El núcleo emite eventos por un bus y nunca imprime, para añadir web (FastAPI/WebSocket) sin tocarlo |
| Proveedores | LiteLLM detrás de una interfaz propia `Provider`. Al menos dos de Claude, OpenAI y Gemini (por decidir; presupuesto de API por definir) |
| Persistencia | SQLite (sesiones, eventos, memoria, auditoría, trazas) |
| Herramientas externas | Cliente MCP (SDK de Python), stdio primero. Servidor de demostración local y sin credenciales (se elige en [SPK-04](04d-historias-conexiones.md#spk-04)) |
| Reto | Subagentes con contexto aislado (obligatorio) |
| Estimación | Puntos de historia (PHU) con Fibonacci; planning poker en el Sprint 1 |

Reglas del equipo: cada área tiene un dueño, pero todo cambio lo revisa otra persona. Definition of Done:
- El código está integrado y la integración continua pasa.
- Tiene pruebas y cumple los criterios de aceptación.
- Pasa el verificador de tipos y el formateador.
- No introduce secretos en el código ni en los registros.
- Otro integrante la revisó.
- Se mostró en la demostración del sprint.

## 2. Alcance

- **Obligatorio (prioridad Alta):** bucle con herramientas, contexto con compactación, sesiones reanudables, memoria, permisos con aprobación humana, CLI, dos proveedores con conmutación por fallo, MCP, subagentes, trazas.
- **Si hay capacidad (Media):** varias llamadas por turno, detección de repeticiones, compactación manual, costos, memoria editable, modo solo lectura, reglas por archivo, subagentes explorador/verificador.
- **Innovación (después del mínimo):** interfaz web, ejecución en entorno aislado, comparación con LangGraph, panel de costos.


## 5. Decisiones de diseño que no se negocian

Salen de revisar los requisitos. Cada una tiene historias asociadas.

| Id | Hallazgo y decisión | Historias |
|---|---|---|
| V-01 | **La aprobación necesita comunicación en dos sentidos.** El bus de eventos solo emite. Para pedir aprobación el núcleo debe esperar una respuesta de la interfaz. El núcleo espera una decisión asíncrona (interfaz Approver). Se confirma con [SPK-02](04a-historias-fundacion.md#spk-02). | [HU-01-05](04a-historias-fundacion.md#hu-01-05), [HU-05-03](04c-historias-control.md#hu-05-03), [SPK-02](04a-historias-fundacion.md#spk-02) |
| V-02 | **«Aprobar para la sesión» podía saltarse una denegación.** La captura no decía qué pasa si existe una regla de denegar. Denegar siempre gana. La aprobación de sesión se limita a una herramienta y un patrón de argumentos. | [HU-05-02](04c-historias-control.md#hu-05-02), [HU-05-03](04c-historias-control.md#hu-05-03) |
| V-03 | **Compactar no debe borrar historial.** RF-2 y RF-3 chocaban: reanudar exige el historial completo. La compactación añade un evento de resumen y marca los eventos cubiertos; el original permanece en SQLite. | [HU-02-03](04b-historias-estado.md#hu-02-03), [HU-03-02](04b-historias-estado.md#hu-03-02) |
| V-04 | **El objetivo y las decisiones no pueden vivir en el historial compactable.** Un resumen mal hecho podía perder la tarea original. El objetivo y las decisiones del usuario se guardan aparte y se inyectan siempre en el prefijo del contexto. | [HU-02-06](04b-historias-estado.md#hu-02-06) |
| V-05 | **«Relevancia» de la memoria no estaba definida.** Sin embeddings no hay medida de similitud. Relevancia = recencia dentro de un presupuesto de tokens. Embeddings pasan a innovación. | [HU-04-02](04b-historias-estado.md#hu-04-02) |
| V-06 | **El contrato del subagente era vago.** No se sabía qué recibe ni qué devuelve. Entrada: objetivo, contexto mínimo y formato de salida. Salida: resultado, hallazgos clave, fuentes y error. Las aprobaciones suben al usuario. | [HU-09-01](04d-historias-conexiones.md#hu-09-01), [HU-09-02](04d-historias-conexiones.md#hu-09-02), [HU-09-03](04d-historias-conexiones.md#hu-09-03) |
| V-07 | **RNF-5 medía algo que no controlamos.** La latencia del modelo no depende del harness. Se mide el tiempo propio del harness por turno con proveedor simulado. | [HU-00-05](04a-historias-fundacion.md#hu-00-05) |
| V-08 | **Windows y macOS cambian el shell y la lista de comandos peligrosos.** El equipo usa Windows y Linux (Arch). Intérprete y lista de denegación para Windows y Linux; la integración continua corre en ambos. | [HU-01-04](04a-historias-fundacion.md#hu-01-04), [HU-00-02](04a-historias-fundacion.md#hu-00-02) |
| V-09 | **El conteo exacto de tokens no existe para todos los modelos.** Cada proveedor cuenta distinto. Estimación heurística corregida con el uso real que informa la API en cada respuesta. | [HU-02-01](04b-historias-estado.md#hu-02-01) |
| V-10 | **El umbral de compactación depende del modelo.** Al conmutar de proveedor cambia la ventana disponible. El umbral se calcula por modelo y se recalcula al conmutar. | [HU-02-03](04b-historias-estado.md#hu-02-03), [HU-07-05](04d-historias-conexiones.md#hu-07-05) |
| V-11 | **Cancelar una herramienta en curso no estaba definido.** Interrumpir con Ctrl+C podía dejar el estado a medias. La herramienta se cancela, se registra como interrumpida y el modelo recibe ese resultado en el siguiente turno. | [HU-06-03](04c-historias-control.md#hu-06-03) |
| V-12 | **Faltaba un archivo de instrucciones del proyecto.** Es práctica común en harnesses actuales. Se añade RF-2.9 (Could): cargar un archivo de instrucciones al prefijo. | [HU-02-07](04b-historias-estado.md#hu-02-07) |
| V-13 | **La detección de secretos no puede ser total.** No existe garantía absoluta. Se declara el alcance: patrones conocidos más los valores de las variables de entorno cargadas. | [HU-04-05](04b-historias-estado.md#hu-04-05), [HU-10-02](04d-historias-conexiones.md#hu-10-02) |
| V-14 | **Hace falta un proveedor simulado.** Sin él las pruebas dependen de la red y de la cuota. Se crea FakeProvider en el Sprint 1 como base de todas las pruebas. | [HU-00-03](04a-historias-fundacion.md#hu-00-03) |

Cambios a la captura de requisitos:

| Requisito | Cambio |
|---|---|
| RF-2.9 (nuevo, Could) | Cargar un archivo de instrucciones del proyecto en el prefijo del contexto. |
| RF-2.4 (precisado) | La compactación conserva el historial original y no puede eliminar el objetivo ni las decisiones del usuario. |
| RF-4.3 (precisado) | Relevancia de la memoria = recencia dentro de un presupuesto de tokens. |
| RF-5.4 (precisado) | Aprobar para la sesión nunca anula una regla de denegar y se limita a herramienta y patrón. |
| RF-9 (precisado) | Se define el contrato de entrada y salida del subagente y la subida de aprobaciones al usuario. |
| RNF-5 (reformulado) | Se mide el tiempo propio del harness por turno, no la latencia del modelo. |

Decisiones tomadas:

| Pregunta | Respuesta |
|---|---|
| ¿El límite de costo en dinero o en tokens? | En tokens. El costo en moneda es solo informativo. |
| ¿Dónde vive la memoria? | En SQLite, con el comando /memoria para consultarla y borrarla. |
| ¿Qué sistema operativo usa cada integrante? | Windows y Linux (Arch Linux). La integración continua y el shell cubren ambos. |
| ¿Quién es el Product Owner? | Brad. |
| ¿Cuántas horas tiene cada persona? | 15 a 28 horas por semana en los 5 días hábiles, más los sábados y domingos completos. Equivale a unas 27 a 44 horas por sprint, según cuánto se trabaje el fin de semana. |
| ¿Qué servidor MCP usamos en la demostración? | Se elige en [SPK-04](04d-historias-conexiones.md#spk-04): servidor local por stdio, sin credenciales. |

Preguntas abiertas:

| Pregunta | Por qué importa | Cuándo se cierra |
|---|---|---|
| ¿Qué dos modelos entre Claude, OpenAI y Gemini, y con qué presupuesto de API? | Define el proveedor principal y el de respaldo ([HU-07-02](04d-historias-conexiones.md#hu-07-02), [HU-07-03](04d-historias-conexiones.md#hu-07-03), [SPK-01](04d-historias-conexiones.md#spk-01)). | Antes de [SPK-01](04d-historias-conexiones.md#spk-01) |
| ¿Se confirma asyncio como modelo de concurrencia? | Depende del resultado de [SPK-02](04a-historias-fundacion.md#spk-02). | Fin del Sprint 1 |

---

[← 00-indice.md](00-indice.md) · [Índice](00-indice.md) · [02-arquitectura.md →](02-arquitectura.md)
