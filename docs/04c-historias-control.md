# Historias: permisos e interacción (E5, E6)

> [← 04b-historias-estado.md](04b-historias-estado.md) · [Índice](00-indice.md) · [04d-historias-conexiones.md →](04d-historias-conexiones.md)  
> Sección 10 del contexto original, continuación: épicas E5 y E6.  
> Ver también: [02-arquitectura.md](02-arquitectura.md) · [03-plan-sprints.md](03-plan-sprints.md) · [PROGRESO.md](PROGRESO.md)
>
> El estado de cada historia vive solo en [PROGRESO.md](PROGRESO.md); aquí no se repite.

### E5. Permisos y human-in-the-loop

<a id="hu-05-01"></a>
#### HU-05-01 — Política denegar, preguntar, permitir que falla cerrada

**Prioridad:** Alta · **PHU:** 3 · **Sprint:** Sprint 1 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-5.1, RF-5.2, RF-5.3 · **Depende de:** [HU-00-01](04a-historias-fundacion.md#hu-00-01), [HU-01-03](04a-historias-fundacion.md#hu-01-03), [HU-01-05](04a-historias-fundacion.md#hu-01-05)

- **Como:** usuario operador
- **Quiero:** que cada acción del agente se clasifique en denegar, preguntar o permitir, que lo no previsto pida aprobación, y que el único permiso explícito del Sprint 1 sea escribir dentro del área de trabajo autorizada
- **Para:** que nada sensible ocurra sin mi control y que aun así se pueda demostrar el agente antes de tener la interfaz de aprobación
- **Descripción:** Cada acción del agente se clasifica en denegar, preguntar o permitir, y toda acción no prevista pide aprobación (falla cerrada). En el Sprint 1, sin interfaz de aprobación, «preguntar» se resuelve como denegar con motivo; el único permiso explícito es escribir dentro del área de trabajo autorizada.

**Flujo general**

1. El modelo solicita una herramienta.
2. La política evalúa la llamada en orden: denegar, preguntar, permitir.
3. Si ninguna regla coincide, pide aprobación.
4. Se ejecuta, se pide aprobación o se deniega según el resultado.
5. Mientras no exista [HU-05-03](04c-historias-control.md#hu-05-03), «preguntar» se deniega con motivo y la decisión se registra.

**Reglas de negocio**

1. Denegar siempre prevalece sobre preguntar y permitir.
2. La política se aplica en el harness, no en el prompt.
3. Las instrucciones halladas en archivos no cambian la política.
4. Borrar archivos, hacer push, merge y deploy siempre requieren aprobación.
5. El permiso de escritura está acotado al área autorizada; no hay regla de «permitir todo».

**Criterios de aceptación**

- **AC-01 — Falla cerrada ante lo no previsto.** Dado una llamada que no coincide con ninguna regla, cuando se evalúa, entonces requiere aprobación manual.
- **AC-02 — Orden de precedencia.** Dado reglas que se contradicen, cuando se evalúan, entonces prevalece el orden denegar, preguntar, permitir.
- **AC-03 — Instrucciones en archivos no alteran la política.** Dado instrucciones en el contenido de un archivo, cuando el modelo las sigue, entonces la política las evalúa igual que cualquier otra llamada.
- **AC-04 — Escritura permitida solo en el área autorizada.** Dado una escritura cuya ruta real queda dentro del área de trabajo autorizada, cuando se evalúa, entonces una regla explícita acotada a esa área la permite; dado cualquier otra ubicación, entonces se pregunta. No existe ninguna regla que permita escribir en cualquier ruta.
- **AC-05 — «Preguntar» provisional en el Sprint 1.** Dado el Sprint 1, sin la interfaz de aprobación ([HU-05-03](04c-historias-control.md#hu-05-03)), cuando una acción resulta en «preguntar», entonces se deniega provisionalmente, el modelo recibe el motivo y la decisión queda registrada como evento; esta resolución provisional se retira cuando [HU-05-03](04c-historias-control.md#hu-05-03) existe.

<a id="hu-05-02"></a>
#### HU-05-02 — Lista de denegados y análisis de comandos compuestos

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 2 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RNF-19, RF-5.2 · **Depende de:** [HU-05-01](04c-historias-control.md#hu-05-01), [HU-01-04](04a-historias-fundacion.md#hu-01-04)

- **Como:** usuario operador
- **Quiero:** una lista de comandos peligrosos denegados por defecto y que cada parte de un comando encadenado se evalúe por separado
- **Para:** que ni un error de configuración ni un comando encadenado abran un hueco de seguridad
- **Descripción:** El sistema trae una lista de comandos peligrosos denegados que ninguna configuración puede vaciar ni una aprobación de sesión anular. Como el shell es la herramienta general, un comando encadenado se separa y cada parte se evalúa por separado.

**Flujo general**

1. El sistema carga la lista base al arrancar.
2. Fusiona la configuración del usuario sin poder quitar la base.
3. Ante un comando con &&, ; o |, separa sus partes y evalúa cada una.
4. Manda la decisión más restrictiva; si no entiende el comando, pregunta.
5. Ante un comando denegado, la política lo rechaza aunque exista aprobación de sesión.

**Reglas de negocio**

1. La lista es propia de cada plataforma.
2. Una aprobación de sesión nunca anula una denegación.
3. Lo que el analizador no entiende se pregunta; nunca se permite por defecto.

**Criterios de aceptación**

- **AC-01 — Lista base inalterable.** Dado un archivo de configuración que intenta vaciar la lista, cuando arranca el sistema, entonces la lista base se mantiene.
- **AC-02 — Aprobación de sesión no anula denegación.** Dado una aprobación para toda la sesión, cuando se pide un comando denegado, entonces sigue denegado.
- **AC-03 — Comandos encadenados evaluados por partes.** Dado un comando encadenado con &&, ; o |, cuando la política lo evalúa, entonces evalúa cada parte y manda la más restrictiva.
- **AC-04 — Falla cerrada ante lo no entendido.** Dado un comando que el analizador no logra entender, cuando se evalúa, entonces se pregunta al usuario (falla cerrada).

<a id="hu-05-03"></a>
#### HU-05-03 — Aprobación con detalle: una vez, toda la sesión o rechazar

**Prioridad:** Alta · **PHU:** 3 · **Sprint:** Sprint 2 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-5.4, RF-5.5, RNF-9 · **Depende de:** [HU-05-01](04c-historias-control.md#hu-05-01), [HU-01-05](04a-historias-fundacion.md#hu-01-05)

- **Como:** usuario operador
- **Quiero:** ver qué herramienta, con qué argumentos y qué efecto tendría antes de decidir
- **Para:** aprobar con conocimiento
- **Descripción:** Antes de decidir, el usuario ve qué herramienta se invoca, con qué argumentos y qué efecto tendría, y elige aprobar una vez, para la sesión o rechazar.

**Flujo general**

1. La política requiere aprobación.
2. El sistema muestra herramienta, argumentos y efecto esperado.
3. El usuario elige una opción.
4. El sistema registra la decisión y continúa.

**Reglas de negocio**

1. La aprobación de sesión se limita a una herramienta y un patrón de argumentos.
2. Fuera del patrón, se vuelve a pedir.

**Prototipo**

```
[!] El agente quiere ejecutar: shell
  comando: pip install requests
  efecto: instala un paquete en el entorno
  [1] aprobar una vez  [2] aprobar para la sesión  [3] rechazar con motivo
```

**Criterios de aceptación**

- **AC-01 — Aprobación con detalle.** Dado una acción que requiere aprobación, cuando se pide, entonces veo herramienta, argumentos y efecto esperado y elijo aprobar una vez, aprobar para la sesión o rechazar.
- **AC-02 — Alcance limitado de la aprobación de sesión.** Dado una aprobación para la sesión, cuando se repite la misma herramienta con otros argumentos fuera del patrón, entonces vuelve a pedir.

<a id="hu-05-04"></a>
#### HU-05-04 — Rechazo con motivo que vuelve al modelo

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 2 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-5.6 · **Depende de:** [HU-05-03](04c-historias-control.md#hu-05-03)

- **Como:** usuario operador
- **Quiero:** rechazar una acción explicando por qué
- **Para:** que el agente replantee su plan en lugar de insistir
- **Descripción:** El usuario puede rechazar una acción explicando el motivo, y el agente replantea su plan en lugar de insistir.

**Flujo general**

1. El usuario rechaza una acción y escribe el motivo.
2. El comando no se ejecuta.
3. El motivo vuelve al modelo como resultado de herramienta.
4. El modelo propone otra vía.

**Reglas de negocio**

1. Un rechazo nunca ejecuta la acción.

**Criterios de aceptación**

- **AC-01 — Rechazo con motivo devuelto al modelo.** Dado un rechazo con motivo, cuando se registra, entonces el comando no se ejecuta y el motivo vuelve al modelo como resultado de herramienta.

<a id="hu-05-05"></a>
#### HU-05-05 — Registro de auditoría de decisiones

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** B — Estado  
**Requisitos:** RF-5.7, RF-10.3 · **Depende de:** [HU-05-03](04c-historias-control.md#hu-05-03)

- **Como:** evaluador del proyecto
- **Quiero:** un registro de cada acción sensible y de la decisión tomada
- **Para:** verificar que los controles funcionan
- **Descripción:** El sistema registra cada acción sensible y la decisión tomada para poder verificar que los controles funcionan.

**Flujo general**

1. Ocurre una aprobación, rechazo o denegación automática.
2. El sistema escribe un registro con herramienta, argumentos, decisión y hora.
3. El evaluador consulta el registro.

**Reglas de negocio**

1. Los argumentos se redactan para no exponer secretos.

**Criterios de aceptación**

- **AC-01 — Decisión registrada en auditoría.** Dado una decisión de aprobación, rechazo o denegación automática, cuando ocurre, entonces queda registrada con herramienta, argumentos, decisión y hora.
- **AC-02 — Auditoría mínima con argumentos redactados.** Dado un registro de aprobación, rechazo o denegación que contenga una clave con patrón conocido o el valor de una variable de entorno sensible, cuando se persiste el registro en el Sprint 3, entonces el dato queda sustituido por una marca antes de escribirse. Este control mínimo no reemplaza [HU-10-01](04d-historias-conexiones.md#hu-10-01) ni [HU-10-02](04d-historias-conexiones.md#hu-10-02) (trazas de modelo y herramientas, Sprint 4).

<a id="hu-05-06"></a>
#### HU-05-06 — Reglas de permisos por archivo

**Prioridad:** Media · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-5.8 · **Depende de:** [HU-05-01](04c-historias-control.md#hu-05-01)

- **Como:** usuario operador
- **Quiero:** definir mis reglas de permisos en un archivo
- **Para:** ajustar el control sin tocar el código
- **Descripción:** El usuario define sus reglas de permisos en un archivo para ajustar el control sin tocar el código.

**Flujo general**

1. El usuario edita el archivo de reglas.
2. Al arrancar, el sistema las carga.
3. La política las aplica.

**Reglas de negocio**

1. Las reglas del archivo no pueden anular la lista base de denegados.

**Criterios de aceptación**

- **AC-01 — Reglas aplicadas desde archivo.** Dado una regla nueva en el archivo, cuando arranca el sistema, entonces se aplica sin modificar el código.

<a id="hu-05-07"></a>
#### HU-05-07 — Modo de solo lectura

**Prioridad:** Media · **PHU:** 1 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-5.9 · **Depende de:** [HU-05-01](04c-historias-control.md#hu-05-01)

- **Como:** usuario operador
- **Quiero:** un modo que deniegue toda escritura
- **Para:** explorar un proyecto sin riesgo
- **Descripción:** El usuario activa un modo de solo lectura que deniega toda escritura, para explorar un proyecto sin riesgo.

**Flujo general**

1. El usuario activa el modo.
2. El agente intenta una escritura.
3. La política la deniega.

**Reglas de negocio**

1. El modo se aplica también a los subagentes.

**Criterios de aceptación**

- **AC-01 — Escritura denegada en solo lectura.** Dado el modo de solo lectura, cuando el agente intenta escribir o ejecutar un comando de escritura, entonces se deniega.

<a id="hu-05-08"></a>
#### HU-05-08 — Contenido externo tratado como datos

**Prioridad:** Media · **PHU:** 2 · **Sprint:** Sprint 4 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RNF-17, RNF-18 · **Depende de:** [HU-05-01](04c-historias-control.md#hu-05-01)

- **Como:** evaluador del proyecto
- **Quiero:** evidencia de que las instrucciones escondidas en archivos o servidores no se obedecen
- **Para:** confiar en las defensas frente a inyección de prompt
- **Descripción:** El sistema demuestra que las instrucciones escondidas en archivos o respuestas de servidores se tratan como datos y no alteran los permisos.

**Flujo general**

1. El agente lee un archivo con una instrucción maliciosa.
2. Cualquier acción derivada pasa por la política.
3. El resultado de un servidor MCP vuelve marcado como dato externo.

**Reglas de negocio**

1. Todo contenido externo lleva una marca de origen.
2. Un contenido externo nunca amplía permisos.

**Criterios de aceptación**

- **AC-01 — Archivo con instrucción maliciosa.** Dado un archivo con una instrucción para borrar archivos, cuando el agente lo lee, entonces cualquier acción derivada pasa por la política y pide aprobación.
- **AC-02 — Resultado MCP marcado como dato.** Dado un resultado MCP, cuando la integración MCP esté disponible en el Sprint 4 condicional, entonces vuelve marcado como dato y no altera permisos; esta parte del criterio no puede darse por completada en Sprint 3.

### E6. Interacción con el usuario

<a id="hu-06-01"></a>
#### HU-06-01 — CLI básica con eventos en tiempo real

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 1 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-6.4, RNF-10 · **Depende de:** [HU-01-05](04a-historias-fundacion.md#hu-01-05)

- **Como:** usuario operador
- **Quiero:** una terminal que muestre en vivo qué herramienta se está ejecutando y mensajes de error claros
- **Para:** entender qué hace el agente
- **Descripción:** La terminal muestra en vivo qué herramienta ejecuta el agente y presenta errores claros con una acción sugerida.

**Flujo general**

1. La CLI se suscribe al bus de eventos.
2. Cuando el agente invoca una herramienta, muestra nombre y estado.
3. Ante un error, muestra la causa y una acción sugerida.

**Reglas de negocio**

1. La CLI no contiene lógica del núcleo.
2. Los errores no muestran trazas de pila crudas.

**Prototipo**

```
> Leí el archivo pagos.py
... ejecutando: buscar "def cobrar" …
x Error: la ruta 'src/pago.py' no existe. Sugerencia: usa 'listar' para ver los archivos.
```

**Criterios de aceptación**

- **AC-01 — Estado de herramienta en vivo.** Dado una tarea en curso, cuando el agente invoca una herramienta, entonces la terminal muestra su nombre y estado.
- **AC-02 — Errores claros.** Dado un error, cuando se muestra, entonces indica la causa y una acción sugerida, sin trazas de pila crudas.

<a id="hu-06-02"></a>
#### HU-06-02 — Herramienta para preguntar al usuario con opciones

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 4 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-6.1, RF-6.2, RF-6.3 · **Depende de:** [HU-01-02](04a-historias-fundacion.md#hu-01-02), [HU-01-05](04a-historias-fundacion.md#hu-01-05)

- **Como:** agente principal
- **Quiero:** formular una pregunta con opciones predefinidas cuando la tarea es ambigua
- **Para:** no adivinar lo que el usuario quiere
- **Descripción:** El agente puede formular una pregunta con opciones predefinidas cuando la tarea es ambigua, y el usuario puede elegir o escribir libremente.

**Flujo general**

1. El agente invoca la herramienta de pregunta con las opciones.
2. La CLI muestra la pregunta.
3. El usuario elige una opción o escribe una respuesta.
4. La respuesta vuelve al bucle como resultado de herramienta.

**Reglas de negocio**

1. Siempre se acepta respuesta libre además de las opciones.

**Prototipo**

```
? ¿Dónde guardo el resultado?
  [1] informe.md  [2] resultados/  [3] otra ruta
> 2
```

**Criterios de aceptación**

- **AC-01 — Elección entre opciones.** Dado una pregunta con tres opciones, cuando el usuario elige una, entonces la respuesta vuelve al bucle como resultado de herramienta.
- **AC-02 — Respuesta libre.** Dado la misma pregunta, cuando el usuario escribe una respuesta libre, entonces también se acepta.

<a id="hu-06-03"></a>
#### HU-06-03 — Interrumpir la ejecución sin perder la sesión

**Prioridad:** Media · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-6.5 · **Depende de:** [SPK-02](04a-historias-fundacion.md#spk-02), [HU-01-01](04a-historias-fundacion.md#hu-01-01), [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1)

- **Como:** usuario operador
- **Quiero:** cancelar de forma controlada la herramienta que el agente está ejecutando
- **Para:** corregir el rumbo sin perder la sesión ni el trabajo ya registrado
- **Descripción:** El usuario cancela de forma controlada la herramienta que el agente está ejecutando, sin perder la sesión. Es distinto de cerrar el proceso (que se recupera con los eventos y el último punto de control) y de terminar con normalidad.

**Flujo general**

1. El usuario pulsa la tecla de interrupción.
2. El sistema cancela la herramienta en curso.
3. Registra la herramienta como interrumpida y escribe un punto de control del progreso.
4. El modelo recibe el resultado de cancelado en el siguiente turno.

**Reglas de negocio**

1. La sesión sigue disponible tras cancelar.
2. La semántica de cancelación se define en [SPK-02](04a-historias-fundacion.md#spk-02).
3. Terminar el proceso no es una cancelación: lo cubren [HU-03-02](04b-historias-estado.md#hu-03-02) y [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1).

**Criterios de aceptación**

- **AC-01 — Cancelación sin perder la sesión.** Dado un comando en ejecución, cuando interrumpo, entonces se cancela esa herramienta, el modelo recibe un resultado de cancelado y la sesión sigue disponible.
- **AC-02 — Eventos y progreso guardados al cancelar.** Dado una cancelación, cuando termina, entonces los eventos hasta ese punto están guardados y el archivo de progreso del ticket se actualiza con un punto de control.

<a id="hu-06-04"></a>
#### HU-06-04 — Comandos de control de la sesión

**Prioridad:** Media · **PHU:** 2 · **Sprint:** Sprint 4 · **Desarrollador:** B — Estado  
**Requisitos:** RF-6.6 · **Depende de:** [HU-03-03](04b-historias-estado.md#hu-03-03), [HU-03-04](04b-historias-estado.md#hu-03-04)

- **Como:** usuario operador
- **Quiero:** comandos para crear sesión nueva, listar, reanudar, compactar y salir
- **Para:** gobernar mis sesiones desde la terminal
- **Descripción:** El usuario gobierna sus sesiones con comandos de crear, listar, reanudar, compactar y salir.

**Flujo general**

1. El usuario escribe un comando que empieza con /.
2. La CLI lo interpreta.
3. Ejecuta la acción correspondiente sobre el núcleo.

**Reglas de negocio**

1. Los comandos se resuelven en la CLI y llaman a la API del núcleo.

**Prototipo**

```
> /nueva   /sesiones   /reanudar <id>   /compactar   /memoria   /salir
```

**Criterios de aceptación**

- **AC-01 — Comandos de control de sesión.** Dado la terminal, cuando escribo el comando de reanudar con un identificador, entonces se carga esa sesión; lo mismo para listar, nueva y salir.

<a id="hu-06-06"></a>
#### HU-06-06 — Varios modelos por alias y modo de planificación (propuesta)

**Estado de la ficha:** historia **propuesta**, pendiente de ratificación del PO (como HU-06-05 y HU-00-08.1); sus criterios son propuestos y son inmutables una vez ratificados.
**Prioridad:** Media · **PHU:** — · **Sprint:** Sprint 4 (cierre adelantado al 6-nov-2026) · **Desarrollador:** C — Control y conexiones
**Requisitos:** RF-6.6 (relacionada) · **Depende de:** [HU-06-04](04c-historias-control.md#hu-06-04), [HU-05-07](04c-historias-control.md#hu-05-07)

- **Como:** usuario operador
- **Quiero:** usar dos modelos en una misma sesión (uno para planear y otro para implementar)
- **Para:** aprovechar cada modelo sin reiniciar ni editar la configuración a mano
- **Descripción:** `config.toml` declara alias de modelos; `/model <alias>` cambia el modelo en caliente, `/plan` usa el alias `plan` con el modo de solo lectura y `/implementar` vuelve al alias `build` (o al modelo predeterminado) sin solo lectura. El historial se conserva y las claves salen solo del entorno.

**Flujo general**

1. La persona declara `[models]` en `config.toml` y las claves de cada proveedor en el entorno.
2. Escribe `/plan`: el agente explora con el modelo `plan` sin poder escribir.
3. Escribe `/implementar`: el agente cambia al modelo `build` y puede escribir según los permisos.

**Reglas de negocio**

1. Las claves no se guardan en el repositorio ni se muestran; un proveedor sin clave falla al elegirlo, no al arrancar.
2. Un modo de solo lectura fijado al arrancar (`--solo-lectura` o `read_only`) no se puede desactivar con `/implementar`.

**Criterios de aceptación (propuestos)**

- **AC-01 — Cambio de modelo en caliente.** Dado `[models]` con `plan` y `build`, cuando escribo `/model build`, entonces las llamadas siguientes van a ese modelo y el historial se conserva.
- **AC-02 — Proveedor sin clave.** Dado un alias cuyo proveedor no tiene clave en el entorno, cuando lo elijo, entonces se avisa con un texto fijo que nombra la variable y el modelo activo no cambia; el arranque nunca falla por eso.
- **AC-03 — Modo de planificación.** Cuando escribo `/plan`, entonces se usa el modelo `plan` y se deniega toda escritura; con `/implementar` se vuelve a `build` (o al predeterminado) y se desactiva el solo lectura.
- **AC-04 — Compatibilidad.** Sin `[models]` el sistema se comporta como antes.
- **AC-05 — Sin secretos.** Ninguna clave aparece en `/model`, avisos, eventos ni archivos del repositorio.

---

[← 04b-historias-estado.md](04b-historias-estado.md) · [Índice](00-indice.md) · [04d-historias-conexiones.md →](04d-historias-conexiones.md)
