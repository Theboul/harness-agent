# Historias: Coding Harness, del ticket al Pull Request (E11)

> [← 04d-historias-conexiones.md](04d-historias-conexiones.md) · [Índice](00-indice.md) · [05-trazabilidad.md →](05-trazabilidad.md)  
> Sección 10 del contexto original, continuación: épica E11, el flujo con el que se demuestra el proyecto.  
> Ver también: [02-arquitectura.md](02-arquitectura.md) · [03-plan-sprints.md](03-plan-sprints.md) · [PROGRESO.md](PROGRESO.md)
>
> El estado de cada historia vive solo en [PROGRESO.md](PROGRESO.md); aquí no se repite.

### E11. Coding Harness: del ticket al Pull Request

<a id="hu-11-01"></a>
#### HU-11-01 — Tarea con criterios de aceptación en una lista estructurada y protegida

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-11.1 · **Depende de:** [HU-03-01](04b-historias-estado.md#hu-03-01), [HU-01-01](04a-historias-fundacion.md#hu-01-01)

- **Como:** usuario operador
- **Quiero:** definir una tarea (ticket) con objetivo, contexto, reglas y criterios de aceptación en un archivo o desde un issue de GitHub, y que los criterios se guarden en una lista estructurada que el agente no puede editar
- **Para:** darle al agente una orden verificable y que no pueda modificar sus propias pruebas
- **Descripción:** El usuario define una tarea con objetivo, contexto, reglas y criterios de aceptación en un archivo o en un issue de GitHub. El agente la recibe como una sesión nueva y los criterios se guardan en una lista JSON (descripción, pasos de verificación y passes) que el agente no puede editar.

**Flujo general**

1. El usuario escribe el archivo de tarea (o indica un issue de GitHub).
2. El sistema lo lee y valida que tenga objetivo y criterios.
3. Genera la lista JSON de criterios, todos con passes en falso.
4. Crea una sesión nueva para la tarea.
5. Inyecta el objetivo, las reglas y los criterios en el prefijo estable.

**Reglas de negocio**

1. Una sesión corresponde a una tarea.
2. Una tarea sin criterios de aceptación se rechaza.
3. El objetivo y los criterios viven fuera del historial compactable.
4. El archivo de criterios es de solo lectura para el agente; el harness es el único que cambia passes. Se usa JSON y no texto libre porque es más difícil de alterar por error.

**Prototipo**

```
TAREA-14  (criterios.json)
[ {"id": 1, "descripcion": "El email es obligatorio",
    "pasos": ["enviar formulario sin email", "ver error"],
    "passes": false},
  {"id": 2, "descripcion": "Las pruebas pasan",
    "pasos": ["ejecutar pytest"], "passes": false} ]
Solo el harness cambia "passes".
```

**Criterios de aceptación**

- **AC-01 — Sesión y lista de criterios creadas desde la tarea.** Dado un archivo de tarea con objetivo, reglas y criterios, cuando se inicia la tarea, entonces se crea una sesión nueva con ese contenido en el contexto estable y una lista JSON de criterios con descripción, pasos de verificación y passes en falso.
- **AC-02 — Tarea sin criterios rechazada.** Dado un archivo de tarea sin criterios de aceptación, cuando se inicia, entonces el sistema lo rechaza e indica qué falta.
- **AC-03 — Lista de criterios protegida.** Dado que el agente intenta editar la lista de criterios con las herramientas de archivos o con el shell, cuando la política lo evalúa, entonces lo deniega; solo el harness puede cambiar el campo passes.

<a id="hu-11-02"></a>
#### HU-11-02 — Git mediante el shell con reglas de permisos por subcomando

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-11.2 · **Depende de:** [HU-01-04](04a-historias-fundacion.md#hu-01-04), [HU-05-02](04c-historias-control.md#hu-05-02)

- **Como:** agente principal
- **Quiero:** consultar el estado y el diff, crear una rama y hacer commit usando git por el shell, con reglas de permisos por subcomando
- **Para:** entregar los cambios de una tarea sin una herramienta especial y bajo el mismo control
- **Descripción:** El agente consulta el estado y el diff, crea una rama y hace commit usando git por el shell. No hay una herramienta Git propia: lo que cambia es la regla de permisos de cada subcomando.

**Flujo general**

1. El agente pide git status, git diff o git log por el shell.
2. La política los permite y la salida larga se recorta.
3. Para commit, push o merge, la política pide aprobación.
4. Los comandos destructivos se deniegan.

**Reglas de negocio**

1. Estado, diff y log son de bajo riesgo; commit, push y merge piden aprobación; reset --hard, clean y push --force se deniegan.
2. El prefijo pide una rama por tarea y commits descriptivos.

**Criterios de aceptación**

- **AC-01 — Lectura de Git permitida.** Dado git status, git diff o git log, cuando el agente los pide por el shell, entonces se permiten sin preguntar y la salida larga se recorta.
- **AC-02 — Escritura de Git sujeta a aprobación o denegada.** Dado git commit, git push o git merge, cuando se evalúan, entonces la política pide aprobación; dado git reset --hard, git clean o git push --force, entonces se deniegan.

<a id="hu-11-03"></a>
#### HU-11-03 — Pruebas y lint mediante el shell con salida recortada

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-11.3 · **Depende de:** [HU-01-04](04a-historias-fundacion.md#hu-01-04), [HU-02-02](04b-historias-estado.md#hu-02-02), [HU-11-01](04e-historias-coding-harness.md#hu-11-01)

- **Como:** agente principal
- **Quiero:** ejecutar las pruebas y el lint con los comandos configurados en la tarea y recibir el código de salida y la salida recortada
- **Para:** saber si mis cambios funcionan y corregir los errores
- **Descripción:** El agente ejecuta las pruebas y el lint con los comandos configurados en la tarea y recibe el código de salida y la salida recortada. Es un comando del shell con permiso explícito, no una herramienta nueva.

**Flujo general**

1. El agente ejecuta el comando de pruebas configurado.
2. La política permite ese comando exacto con tiempo máximo.
3. El sistema devuelve el código de salida y los mensajes de fallo.
4. Si la salida es larga, se recorta con marca de omisión.

**Reglas de negocio**

1. Los comandos de pruebas y de lint se definen en la tarea o en la configuración del proyecto.
2. Solo se permiten automáticamente esos comandos exactos; el tiempo máximo es obligatorio.

**Criterios de aceptación**

- **AC-01 — Fallo de pruebas informado al agente.** Dado un proyecto con una prueba fallida, cuando el agente corre el comando de pruebas configurado, entonces recibe un código de salida distinto de cero y los mensajes de fallo.
- **AC-02 — Salida larga recortada.** Dado una salida muy larga de pruebas, cuando vuelve al contexto, entonces se recorta con marca de omisión.

<a id="hu-11-04"></a>
#### HU-11-04 — Verificación de criterios: solo el harness marca passes

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-11.4 · **Depende de:** [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-11-03](04e-historias-coding-harness.md#hu-11-03), [HU-09-06](04d-historias-conexiones.md#hu-09-06)

- **Como:** usuario operador
- **Quiero:** que la tarea solo se dé por terminada cuando el harness haya verificado cada criterio y marcado passes con evidencia
- **Para:** no aceptar código solo porque la IA dice que ya está
- **Descripción:** El sistema no da la tarea por terminada hasta que el harness verifica cada criterio. El agente no puede marcar su propio trabajo: passes solo cambia con la evidencia de las pruebas o del subagente verificador.

**Flujo general**

1. El agente propone terminar la tarea.
2. El harness ejecuta las pruebas y lanza el verificador con la lista de criterios.
3. Por cada criterio con evidencia, el harness pone passes en verdadero.
4. Si falta algún criterio, la tarea sigue abierta y el agente recibe qué falta.
5. El usuario ve el estado de cada criterio.

**Reglas de negocio**

1. Solo el harness cambia passes.
2. Una tarea solo se cierra si todos los criterios tienen evidencia.
3. Lo que el agente afirma no cuenta como evidencia.

**Criterios de aceptación**

- **AC-01 — Verificación antes de cerrar.** Dado una tarea con tres criterios, cuando el agente propone terminarla, entonces el harness ejecuta la verificación y marca como cumplidos solo los criterios con evidencia.
- **AC-02 — Tarea abierta si falta evidencia.** Dado un criterio sin evidencia, cuando se intenta cerrar la tarea, entonces queda abierta, passes sigue en falso y el agente recibe qué falta.
- **AC-03 — El agente no marca su propio trabajo.** Dado que el agente afirma que un criterio pasa, cuando no hay evidencia del verificador o de las pruebas, entonces passes no cambia.

<a id="hu-11-05"></a>
#### HU-11-05 — Resumen de cambios y aprobación humana del diff

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-11.5 · **Depende de:** [HU-11-02](04e-historias-coding-harness.md#hu-11-02), [HU-05-03](04c-historias-control.md#hu-05-03)

- **Como:** usuario operador
- **Quiero:** ver un resumen de los cambios y el diff, y aprobar antes del commit o del Pull Request
- **Para:** controlar lo que sale de mi repositorio
- **Descripción:** Antes de hacer commit o Pull Request, el usuario ve un resumen de los cambios y el diff y decide si aprueba, con la posibilidad de rechazar indicando el motivo.

**Flujo general**

1. La tarea cumple sus criterios y el agente pide commit.
2. El sistema genera un resumen y muestra el diff.
3. El usuario aprueba o rechaza con motivo.
4. Si aprueba, se hace el commit; si rechaza, el motivo vuelve al agente.

**Reglas de negocio**

1. Nada sale del repositorio sin aprobación.
2. El resumen se genera a partir del diff real, no de lo que el agente dice haber hecho.

**Prototipo**

```
Cambios de TAREA-14 (2 archivos, +18 -3)
  auth.py        validación de email y contraseña
  test_auth.py   2 pruebas nuevas
Pruebas: 24/24 correctas
[1] aprobar y hacer commit  [2] ver diff completo  [3] rechazar con motivo
```

**Criterios de aceptación**

- **AC-01 — Diff y resumen antes de decidir.** Dado una tarea terminada, cuando pide commit, entonces la terminal muestra el resumen y el diff y espera mi decisión.
- **AC-02 — Rechazo con motivo.** Dado un rechazo con motivo, cuando lo registro, entonces no se hace commit y el motivo vuelve al agente.

<a id="hu-11-06"></a>
#### HU-11-06 — Pull Request tras la aprobación

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-11.6 · **Depende de:** [HU-11-05](04e-historias-coding-harness.md#hu-11-05)

- **Como:** usuario operador
- **Quiero:** que el agente cree el Pull Request con la descripción de los cambios cuando yo apruebe
- **Para:** cerrar el flujo del ticket hasta la revisión
- **Descripción:** Tras la aprobación del usuario, el agente hace push de la rama y crea el Pull Request con la descripción de los cambios y los criterios verificados.

**Flujo general**

1. El usuario aprueba el commit.
2. El agente solicita push y creación del Pull Request.
3. La política pide aprobación para ambas acciones.
4. El sistema usa la CLI de GitHub y devuelve el enlace del Pull Request.

**Reglas de negocio**

1. Push y Pull Request son acciones sensibles y siempre piden aprobación.
2. La descripción incluye el resumen y la lista de criterios con su evidencia.

**Criterios de aceptación**

- **AC-01 — Pull Request creado tras aprobar.** Dado un commit aprobado, cuando se confirma, entonces se hace push de la rama y se crea el Pull Request con el resumen y los criterios verificados.
- **AC-02 — Push y Pull Request sujetos a aprobación.** Dado que push y creación del Pull Request son acciones sensibles, cuando se solicitan, entonces siempre piden aprobación.

<a id="hu-11-07"></a>
#### HU-11-07 — Una sesión por ticket con un worktree propio

**Prioridad:** Media · **PHU:** 3 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-11.7 · **Depende de:** [HU-11-02](04e-historias-coding-harness.md#hu-11-02)

- **Como:** usuario operador
- **Quiero:** trabajar varios tickets en paralelo, cada uno con su sesión y su worktree de Git
- **Para:** aislar las tareas entre sí
- **Descripción:** El usuario trabaja varios tickets en paralelo: cada sesión usa su propio worktree de Git para que los cambios no se mezclen.

**Flujo general**

1. El usuario inicia una segunda tarea mientras otra está abierta.
2. El sistema crea un worktree para la sesión nueva.
3. Cada agente trabaja solo en su worktree.
4. Al terminar, el worktree se elimina.

**Reglas de negocio**

1. Una sesión, una tarea, un worktree.
2. El agente no puede salir de la carpeta de su worktree.

**Criterios de aceptación**

- **AC-01 — Aislamiento entre tareas.** Dado dos tickets abiertos, cuando el agente trabaja en cada uno, entonces cada sesión usa su propio worktree y los cambios no se mezclan.

<a id="hu-11-08"></a>
#### HU-11-08 — Rutina de arranque de sesión y archivo de progreso del ticket

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-11.8 · **Depende de:** [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-03-04](04b-historias-estado.md#hu-03-04), [HU-11-02](04e-historias-coding-harness.md#hu-11-02)

- **Como:** usuario operador
- **Quiero:** que cada sesión de un ticket empiece leyendo el progreso anterior y comprobando que el proyecto funciona, y termine dejando el progreso anotado
- **Para:** retomar un ticket sin perder el hilo ni construir sobre código roto
- **Descripción:** Cada sesión de un ticket arranca con una rutina fija: leer el archivo de progreso, el log reciente de git y comprobar que el proyecto funciona antes de tocar nada. Al terminar o ser interrumpida, la sesión deja el progreso anotado. Así un contexto nuevo retoma el trabajo sin adivinar ni construir sobre algo roto.

**Flujo general**

1. El usuario reanuda un ticket.
2. El harness entrega al agente el archivo de progreso y el log reciente de git.
3. Ejecuta la prueba básica del proyecto (comando de la tarea).
4. Si falla, indica reparar eso antes de avanzar; si pasa, el agente elige el criterio pendiente.
5. Al terminar o interrumpirse, el harness actualiza el archivo de progreso.

**Reglas de negocio**

1. El archivo de progreso vive en el repositorio del ticket; SQLite sigue siendo la fuente del historial completo.
2. Se pide al agente avanzar de a un criterio por vez (instrucción del prompt, no regla dura).
3. No se avanza con criterios nuevos mientras la prueba básica falle.

**Prototipo**

```
progreso-TAREA-14.md
- Hecho: validación de email (commit a1b2c3).
- Pendiente: longitud mínima de contraseña.
- Criterios: 1 pasa, 2 no, 3 no.
- Nota: auth.py usa un helper nuevo en utils.py.
```

**Criterios de aceptación**

- **AC-01 — Arranque con progreso, log y prueba básica.** Dado un ticket con progreso previo, cuando se reanuda, entonces antes de pedir trabajo nuevo el harness entrega al agente el archivo de progreso, el log reciente de git y el resultado de la prueba básica del proyecto.
- **AC-02 — Reparar antes de avanzar.** Dado que la prueba básica falla al arrancar, cuando el agente recibe el estado, entonces se le indica reparar eso antes de avanzar con un criterio nuevo.
- **AC-03 — Progreso actualizado al cerrar.** Dado el final de una sesión de trabajo, cuando el agente termina o se interrumpe, entonces el archivo de progreso queda actualizado con lo hecho, lo pendiente y los criterios que pasan.

---

[← 04d-historias-conexiones.md](04d-historias-conexiones.md) · [Índice](00-indice.md) · [05-trazabilidad.md →](05-trazabilidad.md)
