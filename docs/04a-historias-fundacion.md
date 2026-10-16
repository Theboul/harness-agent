# Historias: fundaciones y bucle (E0, E1)

> [← 03-plan-sprints.md](03-plan-sprints.md) · [Índice](00-indice.md) · [04b-historias-estado.md →](04b-historias-estado.md)  
> Sección 10 del contexto original: épicas E0 y E1 (incluye SPK-02).  
> Ver también: [02-arquitectura.md](02-arquitectura.md) · [03-plan-sprints.md](03-plan-sprints.md) · [PROGRESO.md](PROGRESO.md)
>
> El estado de cada historia vive solo en [PROGRESO.md](PROGRESO.md); aquí no se repite.

## 10. Historias de usuario

Formato: plantilla F4 del material de Scrum de la cátedra. PHU = puntos de historia de usuario.

### E0. Fundaciones y calidad

<a id="hu-00-01"></a>
#### HU-00-01 — Esqueleto del repositorio e interfaces acordadas

**Prioridad:** Alta · **PHU:** 3 · **Sprint:** Sprint 1 · **Desarrollador:** A — Núcleo  
**Requisitos:** RNF-12, RNF-13 · **Depende de:** ninguna

- **Como:** equipo de desarrollo
- **Quiero:** tener el repositorio creado y las interfaces del núcleo escritas y acordadas desde el primer día
- **Para:** trabajar los tres en paralelo contra contratos y no bloqueamos entre módulos
- **Descripción:** El equipo crea el repositorio con la estructura de paquetes y escribe las interfaces del núcleo antes de implementar nada, para que A, B y C trabajen en paralelo contra contratos.

**Flujo general**

1. El equipo crea el repositorio y la estructura de paquetes.
2. Se escriben las firmas de las interfaces del núcleo.
3. Se acuerda en una reunión el formato interno de mensajes y eventos.
4. Cada integrante programa contra las interfaces usando dobles de prueba.

**Reglas de negocio**

1. Ningún módulo del núcleo importa un SDK de proveedor directamente.
2. Las interfaces acordadas solo se cambian con el visto bueno de los tres.

**Criterios de aceptación**

- **AC-01 — Programar contra interfaces con dobles.** Dado el repositorio recién clonado, cuando un integrante importa la interfaz de otro módulo, entonces puede programar contra ella usando un doble de prueba.
- **AC-02 — Núcleo sin dependencia de proveedores.** Dado cualquier módulo del núcleo, cuando se revisan sus importaciones, entonces ninguno importa un SDK de proveedor directamente.

<a id="hu-00-02"></a>
#### HU-00-02 — Integración continua con pruebas, tipado y formato

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 1 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RNF-14, RNF-15, RNF-20 · **Depende de:** ninguna

- **Como:** equipo de desarrollo
- **Quiero:** un pipeline que ejecute pruebas, verificación de tipos y formateo en cada cambio
- **Para:** detectar errores antes de integrar
- **Descripción:** El repositorio ejecuta automáticamente pruebas, verificación de tipos y formato en cada cambio, para detectar errores antes de integrar.

**Flujo general**

1. Un integrante propone un cambio.
2. El pipeline ejecuta pruebas, tipos y formato.
3. Si algo falla, el cambio no se puede fusionar.
4. Si todo pasa, otro integrante lo revisa y lo fusiona.

**Reglas de negocio**

1. El pipeline corre en Linux y en el sistema operativo de al menos un integrante.
2. Las versiones de dependencias están fijadas.

**Criterios de aceptación**

- **AC-01 — Pipeline bloquea cambios con errores.** Dado un cambio con una prueba fallida o un error de tipos, cuando se propone su integración, entonces el pipeline falla y el cambio no se puede fusionar.
- **AC-02 — Ejecución en más de un sistema operativo.** Dado el pipeline, cuando corre, entonces ejecuta en Linux y en Windows.

<a id="hu-00-03"></a>
#### HU-00-03 — Proveedor simulado para pruebas

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 1 · **Desarrollador:** B — Estado  
**Requisitos:** RNF-1, RNF-6 · **Depende de:** [HU-00-01](04a-historias-fundacion.md#hu-00-01)

- **Como:** equipo de desarrollo
- **Quiero:** reproducir respuestas del modelo con un proveedor simulado
- **Para:** probar el bucle sin gastar cuota de API ni depender de la red
- **Descripción:** El equipo dispone de un proveedor simulado que reproduce un guion de respuestas, de modo que casi todas las pruebas corren sin red ni cuota.

**Flujo general**

1. El desarrollador escribe un guion con respuestas de texto y llamadas a herramientas.
2. El bucle usa el proveedor simulado en lugar de uno real.
3. El resultado es el mismo en cada ejecución.
4. Opcionalmente el guion fuerza un error de cuota, tiempo agotado o indisponibilidad.

**Reglas de negocio**

1. El proveedor simulado implementa la misma interfaz Provider que los reales.
2. Los errores simulados tienen el mismo tipo que los reales.

**Criterios de aceptación**

- **AC-01 — Ejecución determinista sin red.** Dado un guion de respuestas con texto y llamadas a herramientas, cuando el bucle corre con el proveedor simulado, entonces el resultado es idéntico en cada ejecución y sin red.
- **AC-02 — Fallos simulados equivalentes a los reales.** Dado el proveedor simulado configurado para fallar con error de cuota, cuando el bucle lo llama, entonces recibe el mismo tipo de error que daría un proveedor real.

<a id="hu-00-04"></a>
#### HU-00-04 — Configuración por archivo y variables de entorno

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 1 · **Desarrollador:** B — Estado  
**Requisitos:** RF-7.6, RNF-16, RNF-21 · **Depende de:** [HU-00-01](04a-historias-fundacion.md#hu-00-01)

- **Como:** usuario operador
- **Quiero:** configurar modelo, límites y rutas en un archivo y las claves en variables de entorno
- **Para:** cambiar de modelo o de límite sin tocar el código ni exponer claves
- **Descripción:** El sistema se configura con un archivo (modelo, límites, rutas) y las claves se leen solo de variables de entorno.

**Flujo general**

1. El usuario edita el archivo de configuración.
2. Al arrancar, el sistema lee el archivo y las variables de entorno.
3. El sistema usa el modelo y los límites indicados.
4. Si falta una clave, informa cuál falta sin mostrar su valor.

**Reglas de negocio**

1. Las claves nunca se escriben en archivos ni en el repositorio.
2. Existe una plantilla de ejemplo sin secretos y un .gitignore adecuado.

**Criterios de aceptación**

- **AC-01 — Cambio de modelo sin tocar el código.** Dado un archivo de configuración con otro modelo, cuando arranca el sistema, entonces usa ese modelo sin cambios de código.
- **AC-02 — Sin claves en el repositorio.** Dado el repositorio completo, cuando se busca un secreto, entonces ninguna clave aparece en archivos ni en el historial de cambios.

<a id="hu-00-05"></a>
#### HU-00-05 — Pruebas de integración y de fallos

**Prioridad:** Alta · **PHU:** 3 · **Sprint:** Sprint 3 · **Desarrollador:** A — Núcleo  
**Requisitos:** RNF-1, RNF-5, RNF-6, RNF-7, RNF-8 · **Depende de:** [HU-03-02](04b-historias-estado.md#hu-03-02), [HU-07-05](04d-historias-conexiones.md#hu-07-05), [HU-08-04](04d-historias-conexiones.md#hu-08-04)

- **Como:** evaluador del proyecto
- **Quiero:** evidencia automatizada de que el sistema resiste fallos
- **Para:** confiar en su fiabilidad y en el rendimiento propio del harness
- **Descripción:** El equipo cuenta con pruebas automatizadas que demuestran que el sistema resiste cierres abruptos, proveedores caídos y herramientas defectuosas, y que mide el tiempo propio del harness.

**Flujo general**

1. Se simula un cierre forzado a mitad de sesión y se reanuda.
2. Se simula un proveedor caído y se verifica la conmutación.
3. Se simula un servidor MCP caído y una herramienta con excepción.
4. Se mide el tiempo propio del harness por turno con proveedor simulado.

**Reglas de negocio**

1. Las pruebas de fallos corren en la integración continua.
2. El tiempo del harness se mide sin contar la latencia del modelo.

**Criterios de aceptación**

- **AC-01 — Sin pérdida de eventos tras cierre forzado.** Dado un cierre forzado del proceso a mitad de sesión, cuando se reanuda, entonces no se pierde ningún evento confirmado.
- **AC-02 — Fallo MCP aislado.** Dado un servidor MCP inexistente o caído, cuando arranca la sesión, entonces solo sus herramientas quedan deshabilitadas y el resto funciona.
- **AC-03 — Tiempo propio del harness medido.** Dado un turno con proveedor simulado y herramientas instantáneas, cuando se mide, entonces el tiempo propio del harness es pequeño y queda registrado.

<a id="hu-00-06"></a>
#### HU-00-06 — README, guion de demostración y documento de arquitectura

**Prioridad:** Alta · **PHU:** 3 · **Sprint:** Sprint 3 · **Desarrollador:** B — Estado  
**Requisitos:** RNF-11 · **Depende de:** [HU-00-04](04a-historias-fundacion.md#hu-00-04)

- **Como:** persona ajena al equipo
- **Quiero:** instalar y ejecutar el sistema siguiendo solo el README
- **Para:** evaluar el proyecto sin pasos ocultos
- **Descripción:** Una persona ajena al equipo puede instalar y ejecutar el sistema solo con el README y recorrer la demostración de 10 a 15 minutos.

**Flujo general**

1. El equipo redacta el README con instalación, configuración y primeros pasos.
2. Se escribe el guion de demostración.
3. Se documenta la arquitectura con los diagramas del análisis.
4. Una persona ajena sigue el README en una máquina limpia.

**Reglas de negocio**

1. El README no asume pasos que no estén escritos.
2. El guion recorre todos los criterios de aceptación obligatorios.

**Criterios de aceptación**

- **AC-01 — Instalación solo con el README.** Dado una máquina limpia, cuando una persona ajena sigue el README, entonces instala y ejecuta una tarea sin ayuda del equipo.
- **AC-02 — Guion de demostración completo.** Dado el guion de demostración, cuando se sigue, entonces recorre todos los criterios de aceptación en 10 a 15 minutos.

<a id="hu-00-07"></a>
#### HU-00-07 — Cobertura mínima y prueba de instalación

**Prioridad:** Media · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RNF-11, RNF-14 · **Depende de:** [HU-00-02](04a-historias-fundacion.md#hu-00-02), [HU-00-06](04a-historias-fundacion.md#hu-00-06)

- **Como:** equipo de desarrollo
- **Quiero:** verificar la cobertura del núcleo y la instalación por una persona ajena
- **Para:** cumplir los umbrales de calidad acordados
- **Descripción:** El equipo verifica la cobertura de pruebas del núcleo y la instalación por una persona ajena antes de la entrega.

**Flujo general**

1. Se genera el informe de cobertura.
2. Se cubren los módulos del núcleo que falten.
3. Una persona externa instala siguiendo el README y anota problemas.
4. El equipo corrige lo detectado.

**Reglas de negocio**

1. La cobertura mínima del paquete del núcleo es del 60 %.
2. Los problemas de instalación se corrigen antes de la entrega.

**Criterios de aceptación**

- **AC-01 — Cobertura mínima del núcleo.** Dado el informe de cobertura, cuando se revisa el paquete del núcleo, entonces alcanza al menos el 60 %.
- **AC-02 — Prueba de instalación externa.** Dado una persona ajena al equipo, cuando instala siguiendo el README, entonces registra los problemas y se corrigen antes de la entrega.

### E1. Bucle y herramientas

<a id="hu-01-01"></a>
#### HU-01-01 — Bucle agéntico básico

**Prioridad:** Alta · **PHU:** 5 · **Sprint:** Sprint 1 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-1.1, RF-1.5 · **Depende de:** [HU-00-01](04a-historias-fundacion.md#hu-00-01), [HU-07-01](04d-historias-conexiones.md#hu-07-01)

- **Como:** usuario operador
- **Quiero:** plantear una tarea y que el agente ejecute turnos hasta terminarla
- **Para:** no tener que dirigir cada paso
- **Descripción:** El usuario plantea una tarea y el agente ejecuta turnos de razonar, actuar y observar hasta terminarla, sin que el usuario dirija cada paso.

**Flujo general**

1. El usuario escribe una tarea.
2. El agente llama al modelo con el contexto.
3. Si el modelo pide una herramienta, el agente la ejecuta y devuelve el resultado.
4. El agente repite hasta que el modelo no pide más herramientas.
5. El agente muestra la respuesta final y vuelve a esperar al usuario.

**Reglas de negocio**

1. Un error de herramienta no detiene el bucle: se devuelve al modelo como resultado estructurado.
2. El bucle emite eventos y no imprime directamente.

**Criterios de aceptación**

- **AC-01 — Ejecución de tres pasos en orden.** Dado un guion de tres pasos con herramientas, cuando el bucle corre, entonces ejecuta las tres herramientas en orden y termina cuando el modelo no pide más.
- **AC-02 — Error de herramienta devuelto al modelo.** Dado una herramienta que falla, cuando el bucle recibe el error, entonces lo devuelve al modelo como resultado estructurado y continúa.

<a id="hu-01-02"></a>
#### HU-01-02 — Registro de herramientas con esquema y validación

**Prioridad:** Alta · **PHU:** 3 · **Sprint:** Sprint 1 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-1.2, RF-1.3, RNF-2, RNF-13 · **Depende de:** [HU-00-01](04a-historias-fundacion.md#hu-00-01)

- **Como:** equipo de desarrollo
- **Quiero:** registrar una herramienta con nombre, descripción y esquema JSON, y validar sus argumentos antes de ejecutarla
- **Para:** añadir herramientas sin tocar el bucle
- **Descripción:** Cada herramienta se registra con nombre, descripción y esquema JSON, y sus argumentos se validan antes de ejecutarla.

**Flujo general**

1. El desarrollador define una herramienta con su esquema.
2. La herramienta se registra en el ToolRegistry.
3. El modelo la invoca con argumentos.
4. El registro valida los argumentos contra el esquema.
5. Si son válidos se ejecuta; si no, el modelo recibe el campo inválido.

**Reglas de negocio**

1. Una herramienta nueva no requiere cambios en el bucle.
2. Toda herramienta declara su nivel de riesgo.

**Criterios de aceptación**

- **AC-01 — Validación de argumentos.** Dado una llamada con argumentos que no cumplen el esquema, cuando se valida, entonces no se ejecuta y el modelo recibe un error que indica el campo inválido.
- **AC-02 — Herramienta nueva sin tocar el bucle.** Dado una herramienta nueva registrada, cuando el modelo la invoca, entonces funciona sin modificar el bucle.

<a id="hu-01-03"></a>
#### HU-01-03 — Herramientas de archivos: leer, escribir, listar y buscar

**Prioridad:** Alta · **PHU:** 3 · **Sprint:** Sprint 1 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-1.2 · **Depende de:** [HU-01-02](04a-historias-fundacion.md#hu-01-02)

- **Como:** usuario operador
- **Quiero:** que el agente pueda leer, escribir, listar y buscar texto en archivos
- **Para:** trabajar sobre mis proyectos
- **Descripción:** El agente puede leer, escribir, listar y buscar texto en archivos del proyecto del usuario.

**Flujo general**

1. El modelo solicita una herramienta de archivos.
2. La política de permisos evalúa la llamada.
3. La herramienta opera sobre la ruta indicada.
4. El resultado o un error claro vuelve al modelo.

**Reglas de negocio**

1. Las lecturas se clasifican como bajo riesgo y las escrituras como acción que requiere permiso.
2. Una ruta inexistente devuelve un error claro, no una excepción.

**Criterios de aceptación**

- **AC-01 — Lectura y error de ruta inexistente.** Dado una ruta existente, cuando el agente la lee, entonces recibe su contenido; si no existe, recibe un error claro.
- **AC-02 — Escritura sujeta a permiso.** Dado una escritura, cuando se ejecuta, entonces queda clasificada como acción que requiere permiso según la política.

<a id="hu-01-04"></a>
#### HU-01-04 — Herramienta de shell portable con tiempo límite

**Prioridad:** Alta · **PHU:** 3 · **Sprint:** Sprint 2 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-1.2, RNF-20 · **Depende de:** [HU-01-02](04a-historias-fundacion.md#hu-01-02), [HU-05-01](04c-historias-control.md#hu-05-01)

- **Como:** usuario operador
- **Quiero:** que el agente pueda ejecutar comandos con tiempo límite y salida acotada, en PowerShell en Windows y en bash en Linux
- **Para:** automatizar tareas en cualquiera de los dos sistemas sin riesgo de que se cuelgue
- **Descripción:** El agente puede ejecutar comandos de shell con un tiempo máximo y salida acotada. En Windows usa PowerShell y en Linux usa bash, y el modelo sabe cuál de los dos tiene delante. El shell es la herramienta general: Git, pruebas y lint se hacen con él, bajo reglas de permisos.

**Flujo general**

1. El modelo solicita ejecutar un comando.
2. La política de permisos evalúa el comando y, si corresponde, pide aprobación.
3. El sistema lo ejecuta con tiempo máximo en el intérprete de la plataforma.
4. Si excede el tiempo, lo termina y lo informa.
5. La salida se acota y vuelve al modelo.

**Reglas de negocio**

1. El intérprete se elige según el sistema operativo (PowerShell o bash) detrás de una misma interfaz.
2. El prefijo del contexto indica al modelo el sistema operativo y el intérprete.
3. La lista de comandos denegados es propia de cada plataforma.

**Criterios de aceptación**

- **AC-01 — Tiempo máximo de ejecución.** Dado un comando que excede el tiempo máximo, cuando se ejecuta, entonces se termina y el modelo recibe un resultado de tiempo agotado.
- **AC-02 — Intérprete según plataforma.** Dado el sistema operativo del usuario, cuando se ejecuta un comando, entonces se usa PowerShell en Windows y bash en Linux.
- **AC-03 — El modelo conoce su entorno.** Dado el arranque de una sesión, cuando se arma el contexto, entonces el prefijo indica al modelo el sistema operativo y el intérprete que se usan.
- **AC-04 — Mismas pruebas en Windows y Linux.** Dado el mismo conjunto de pruebas de shell, cuando corre en integración continua, entonces pasa en Windows y en Linux.

<a id="hu-01-05"></a>
#### HU-01-05 — Bus de eventos desacoplado de la interfaz

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 1 · **Desarrollador:** B — Estado  
**Requisitos:** RF-1.8 · **Depende de:** [HU-00-01](04a-historias-fundacion.md#hu-00-01)

- **Como:** equipo de desarrollo
- **Quiero:** que el núcleo emita eventos tipados y no imprima nada
- **Para:** añadir una interfaz web sin tocar el núcleo
- **Descripción:** El núcleo emite eventos tipados a un bus y nunca imprime, de modo que cualquier interfaz (terminal o web) se conecta como suscriptor.

**Flujo general**

1. El núcleo produce un evento por cada hecho relevante.
2. El bus entrega el evento a los suscriptores.
3. La interfaz CLI se suscribe y los muestra.
4. Una interfaz futura se suscribe sin tocar el núcleo.

**Reglas de negocio**

1. El núcleo no contiene impresión ni dependencias de la terminal.
2. Los eventos están definidos y tipados en un solo lugar.

**Criterios de aceptación**

- **AC-01 — Eventos emitidos en un turno completo.** Dado un turno completo, cuando corre, entonces el núcleo emite eventos de mensaje, herramienta solicitada, herramienta terminada, aprobación pedida y error.
- **AC-02 — Núcleo sin dependencias de la terminal.** Dado el núcleo, cuando se revisa su código, entonces no contiene llamadas de impresión ni dependencias de la terminal.

<a id="hu-01-06"></a>
#### HU-01-06 — Límites de turnos, tiempo y costo por sesión

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 2 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-1.6 · **Depende de:** [HU-01-01](04a-historias-fundacion.md#hu-01-01)

- **Como:** usuario operador
- **Quiero:** fijar límites de turnos, tiempo y consumo por sesión
- **Para:** evitar bucles que gasten mi cuota
- **Descripción:** El usuario fija límites de turnos, tiempo y consumo por sesión para que un bucle sin salida no gaste su cuota.

**Flujo general**

1. El usuario configura los límites.
2. Antes de cada llamada al modelo el bucle comprueba los límites.
3. Si alguno se alcanza, el bucle se detiene y emite un evento.
4. El sistema explica el motivo y devuelve el control al usuario.

**Reglas de negocio**

1. El límite de consumo se mide en tokens; el costo en dinero es solo informativo.
2. La comprobación ocurre antes de llamar, no después.

**Criterios de aceptación**

- **AC-01 — Límite de turnos.** Dado un límite de N turnos, cuando el bucle lo alcanza, entonces se detiene, emite un evento y explica el motivo.
- **AC-02 — Límite de consumo.** Dado un límite de consumo, cuando se supera, entonces el sistema se detiene antes de la siguiente llamada al modelo.

<a id="hu-01-07"></a>
#### HU-01-07 — Varias llamadas a herramientas en un mismo turno

**Prioridad:** Media · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-1.4 · **Depende de:** [HU-01-01](04a-historias-fundacion.md#hu-01-01)

- **Como:** usuario operador
- **Quiero:** que el agente ejecute varias llamadas pedidas en un mismo turno
- **Para:** terminar tareas con menos turnos
- **Descripción:** Cuando el modelo pide varias herramientas en un mismo turno, el agente las ejecuta y asocia cada resultado a su llamada.

**Flujo general**

1. El modelo responde con varias llamadas.
2. El sistema evalúa permisos de cada una.
3. Ejecuta las llamadas.
4. Devuelve cada resultado con su identificador.

**Reglas de negocio**

1. Cada resultado se asocia al identificador de su llamada.
2. Cada llamada pasa por la política por separado.

**Criterios de aceptación**

- **AC-01 — Resultados asociados a su llamada.** Dado un turno con tres llamadas independientes, cuando se ejecutan, entonces los tres resultados vuelven al modelo asociados a su llamada.

<a id="hu-01-08"></a>
#### HU-01-08 — Detección de llamadas repetidas

**Prioridad:** Media · **PHU:** 1 · **Sprint:** Sprint 3 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-1.7 · **Depende de:** [HU-01-01](04a-historias-fundacion.md#hu-01-01)

- **Como:** usuario operador
- **Quiero:** que el sistema detecte al agente repitiendo la misma llamada con los mismos argumentos
- **Para:** no gastar cuota en un bucle sin salida
- **Descripción:** El sistema detecta cuando el agente repite la misma llamada con los mismos argumentos y lo interrumpe.

**Flujo general**

1. El bucle registra las llamadas recientes.
2. Si una se repite más veces que el umbral, se detecta.
3. El bucle la interrumpe y avisa al modelo y al usuario.

**Reglas de negocio**

1. El umbral de repeticiones es configurable.
2. El aviso incluye la llamada repetida.

**Criterios de aceptación**

- **AC-01 — Repetición detectada e interrumpida.** Dado la misma llamada repetida más veces que el umbral, cuando se detecta, entonces el bucle la interrumpe y avisa al modelo y al usuario.

<a id="spk-02"></a>
#### SPK-02 — Spike: modelo asíncrono y cancelación de herramientas

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 1 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-6.5, RF-9.9 · **Depende de:** ninguna

- **Como:** equipo de desarrollo
- **Quiero:** decidir durante medio día si el núcleo es asíncrono y cómo se cancela una herramienta en curso
- **Para:** diseñar el bucle sin rehacerlo después
- **Descripción:** Spike de medio día: decidir si el núcleo es asíncrono y cómo se cancela una herramienta en curso.

**Flujo general**

1. Se prototipa el bucle con asyncio.
2. Se lanza un comando largo.
3. Se cancela y se observa el comportamiento.
4. Se documenta la decisión.

**Reglas de negocio**

1. La decisión condiciona [HU-01-05](04a-historias-fundacion.md#hu-01-05), [HU-05-03](04c-historias-control.md#hu-05-03) y [HU-06-03](04c-historias-control.md#hu-06-03).

**Criterios de aceptación**

- **AC-01 — Cancelación de comando largo en prototipo.** Dado un comando largo en ejecución, cuando se cancela en el prototipo, entonces el proceso termina y el control vuelve al bucle.

---

[← 03-plan-sprints.md](03-plan-sprints.md) · [Índice](00-indice.md) · [04b-historias-estado.md →](04b-historias-estado.md)
