# Historias: Coding Harness, del ticket al Pull Request (E11)

> [← 04d-historias-conexiones.md](04d-historias-conexiones.md) · [Índice](00-indice.md) · [05-trazabilidad.md →](05-trazabilidad.md)  
> Sección 10 del contexto original, continuación: épica E11, el flujo con el que se demuestra el proyecto.  
> Ver también: [02-arquitectura.md](02-arquitectura.md) · [03-plan-sprints.md](03-plan-sprints.md) · [PROGRESO.md](PROGRESO.md)
>
> El estado de cada historia vive solo en [PROGRESO.md](PROGRESO.md); aquí no se repite.

### E11. Coding Harness: del ticket al Pull Request

<a id="hu-11-01"></a>
#### HU-11-01 — Tarea con criterios de aceptación protegidos en SQLite

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 2 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-11.1 · **Depende de:** [HU-03-01](04b-historias-estado.md#hu-03-01), [HU-01-01](04a-historias-fundacion.md#hu-01-01), [HU-05-01](04c-historias-control.md#hu-05-01)

- **Como:** usuario operador
- **Quiero:** definir una tarea (ticket) con objetivo, contexto, reglas y criterios de aceptación en un archivo o desde un issue de GitHub, y que el harness niegue cambios a los criterios mediante herramientas controladas y registre cualquier anomalía
- **Para:** darle al agente una orden verificable y que no pueda modificar sus propias pruebas de aceptación
- **Descripción:** El usuario define una tarea con objetivo, contexto, reglas y criterios de aceptación en un archivo o en un issue de GitHub. El agente la recibe como una sesión nueva. Los criterios se guardan en la tabla criterios de SQLite y se exporta una copia JSON informativa. La política del harness deniega las modificaciones por herramientas autorizadas, pero SQLite no impide por sí solo el acceso de procesos shell que compartan la misma identidad del sistema operativo; la protección fuerte exige aislamiento o separación de privilegios. Cada criterio es objetivo (comando de verificación y condición esperada) o semántico (necesita validación humana).

**Flujo general**

1. El usuario escribe el archivo de tarea (o indica un issue de GitHub).
2. El sistema lo lee y valida que tenga objetivo y criterios.
3. Guarda los criterios en SQLite, todos con passes en falso, y exporta una copia JSON de solo lectura.
4. Crea una sesión nueva para la tarea.
5. Inyecta el objetivo, las reglas y los criterios en el prefijo estable.

**Reglas de negocio**

1. Una sesión corresponde a una tarea.
2. Una tarea sin criterios de aceptación se rechaza.
3. El objetivo y los criterios viven fuera del historial compactable.
4. La verificación lee siempre desde SQLite; la copia JSON es informativa y se restaura ante cambios. Debe fallar cerrada ante cualquier indicio de alteración de la fuente protegida.
5. Un criterio objetivo declara su comando de verificación y su condición; uno sin comando es semántico.
6. Limitación: la protección por reglas del shell depende de interpretar comandos; el aislamiento verificable es [HU-IN-02](04d-historias-conexiones.md#hu-in-02) (ver riesgo R-21).

**Prototipo**

```
TAREA-14  (copia de solo lectura de la tabla criterios)
[ {"id": 1, "tipo": "objetivo",
    "descripcion": "El email es obligatorio",
    "verificacion": {"comando": "pytest tests/test_email.py",
                     "espera": "codigo_salida == 0"},
    "passes": false},
  {"id": 2, "tipo": "semantico",
    "descripcion": "El mensaje de error es claro",
    "passes": false} ]
La fuente de verdad es SQLite. Solo el harness cambia "passes".
```

**Criterios de aceptación**

- **AC-01 — Sesión y criterios creados desde la tarea.** Dado un archivo de tarea con objetivo, reglas y criterios, cuando se inicia la tarea, entonces se crea una sesión nueva y los criterios (descripción, tipo objetivo o semántico, comando de verificación, condición esperada y passes en falso) se guardan en la tabla criterios de SQLite, con una copia JSON de solo lectura.
- **AC-02 — Tarea sin criterios rechazada.** Dado un archivo de tarea sin criterios de aceptación, cuando se inicia, entonces el sistema lo rechaza e indica qué falta.
- **AC-03 — Criterios protegidos y copia restaurada.** Dado un intento de escritura sobre los criterios mediante las herramientas controladas del harness, cuando la política lo evalúa, entonces lo deniega y registra; si la copia JSON cambia, el harness ignora esa copia, la restaura desde SQLite y registra la anomalía. Esto NO demuestra aislamiento ante un shell arbitrario con los mismos privilegios que el harness: tal garantía queda condicionada a PD-06 y exige una prueba independiente de acceso denegado.

<a id="hu-11-02"></a>
#### HU-11-02 — Git mediante el shell con reglas de permisos por subcomando

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 2 · **Desarrollador:** B — Estado  
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

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 2 · **Desarrollador:** C — Control y conexiones  
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

<a id="hu-11-04.1"></a>
#### HU-11-04.1 — Verificación automática de criterios objetivos: solo el harness marca passes

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 2 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-11.4 · **Depende de:** [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-11-03](04e-historias-coding-harness.md#hu-11-03), [HU-01-04](04a-historias-fundacion.md#hu-01-04)

- **Como:** usuario operador
- **Quiero:** que el harness ejecute el comando de verificación de cada criterio objetivo y marque passes solo cuando se cumple la condición esperada
- **Para:** no aceptar un resultado solo porque la IA dice que ya está
- **Descripción:** Cuando el agente propone terminar, el harness ejecuta por su cuenta el comando de verificación de cada criterio objetivo y marca passes solo si se cumple la condición esperada. Los criterios semánticos quedan pendientes de validación humana. Es la primera versión de la verificación: no usa subagentes.

**Flujo general**

1. El agente propone terminar la tarea.
2. El harness ejecuta el comando de verificación de cada criterio objetivo bajo la política de permisos.
3. Si el resultado cumple la condición, pone passes en verdadero; si no, lo deja en falso y devuelve al agente la salida recortada.
4. Los criterios semánticos quedan pendientes de validación humana.
5. La CLI muestra el estado de cada criterio.

**Reglas de negocio**

1. Solo el harness cambia passes; lo que el agente afirma no cuenta como evidencia.
2. Un criterio sin comando de verificación nunca se marca automáticamente.
3. Los comandos de verificación los define la tarea, no el agente.

**Prototipo**

```
TAREA-14 — estado de los criterios
  [x] 1 El email es obligatorio            (pytest: salida 0)
  [ ] 2 La contraseña tiene 8 caracteres   (pytest: salida 1)
  [?] 3 El mensaje de error es claro       pendiente de validación humana
```

**Criterios de aceptación**

- **AC-01 — Verificación por comandos del harness.** Dado un ticket con criterios objetivos, cada uno con un comando de verificación y una condición esperada, cuando el agente propone terminarlo, entonces el harness ejecuta cada comando y marca passes solo en los que cumplen la condición.
- **AC-02 — Criterio semántico pendiente de validación humana.** Dado un criterio sin comando de verificación (semántico), cuando se intenta cerrar la tarea, entonces queda pendiente de validación humana y nunca se marca por una afirmación del modelo.
- **AC-03 — Fallo de verificación informado al agente.** Dado un comando de verificación que falla, cuando termina, entonces passes sigue en falso y el agente recibe el código de salida y la salida recortada.
- **AC-04 — Estado visible de cada criterio.** Dado el estado de la tarea, cuando el usuario lo consulta, entonces ve cada criterio como cumplido, no cumplido o pendiente de validación humana.

<a id="hu-11-04.2"></a>
#### HU-11-04.2 — Verificación independiente con el subagente verificador

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-11.4, RF-9.8 · **Depende de:** [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1), [HU-09-06](04d-historias-conexiones.md#hu-09-06)

- **Como:** usuario operador
- **Quiero:** que un subagente verificador revise los criterios semánticos y aporte evidencia, sin poder marcarlos como cumplidos
- **Para:** tener una segunda opinión independiente antes de decidir
- **Descripción:** Un subagente verificador, con contexto limpio y sin permiso de edición, revisa los criterios semánticos y devuelve un informe con evidencia. El informe no cambia passes: el criterio queda pendiente de confirmación humana. Amplía el mecanismo de [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1).

**Flujo general**

1. El agente propone terminar y hay criterios semánticos.
2. El harness lanza al subagente verificador con esos criterios.
3. El verificador devuelve, por criterio, si se cumple y la evidencia.
4. El harness registra el informe y deja el criterio pendiente de confirmación humana.

**Reglas de negocio**

1. El verificador no puede editar archivos ni marcar passes.
2. El informe del verificador es una recomendación, no una aceptación.

**Criterios de aceptación**

- **AC-01 — Informe del verificador registrado sin cambiar passes.** Dado un criterio semántico, cuando el agente propone terminar, entonces el harness lanza al verificador y registra su informe (cumple o no cumple, con evidencia) sin cambiar passes.
- **AC-02 — Criterio pendiente de confirmación humana.** Dado el informe del verificador, cuando se registra, entonces el criterio queda como «verificado por subagente, pendiente de confirmación humana».

<a id="hu-11-05"></a>
#### HU-11-05 — Resumen de cambios y aprobación humana del diff

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-11.5 · **Depende de:** [HU-11-02](04e-historias-coding-harness.md#hu-11-02), [HU-05-03](04c-historias-control.md#hu-05-03), [HU-11-04.1](04e-historias-coding-harness.md#hu-11-04.1)

- **Como:** usuario operador
- **Quiero:** ver un resumen de los cambios y el diff, y aprobar antes del commit o del Pull Request
- **Para:** controlar lo que sale de mi repositorio
- **Descripción:** Antes de hacer commit o Pull Request, el usuario ve un resumen de los cambios y el diff, confirma o rechaza los criterios que esperan validación humana y decide si aprueba, con la posibilidad de rechazar indicando el motivo.

**Flujo general**

1. La tarea cumple sus criterios objetivos y el agente pide commit.
2. El sistema genera un resumen y muestra el diff.
3. El usuario confirma o rechaza cada criterio pendiente.
4. El usuario aprueba o rechaza con motivo.
5. Si aprueba, se hace el commit; si rechaza, el motivo vuelve al agente.

**Reglas de negocio**

1. Nada sale del repositorio sin aprobación.
2. El resumen se genera a partir del diff real, no de lo que el agente dice haber hecho.
3. Solo la confirmación humana cambia passes en un criterio semántico.

**Prototipo**

```
Cambios de TAREA-14 (2 archivos, +18 -3)
  auth.py        validación de email y contraseña
  test_auth.py   2 pruebas nuevas
Pruebas: 24/24 correctas
Criterio 3 (semántico) — informe del verificador: cumple
[1] aprobar y hacer commit  [2] ver diff  [3] rechazar con motivo  [4] confirmar criterio 3
```

**Criterios de aceptación**

- **AC-01 — Diff y resumen antes de decidir.** Dado una tarea terminada, cuando pide commit, entonces la terminal muestra el resumen y el diff y espera mi decisión.
- **AC-02 — Rechazo con motivo.** Dado un rechazo con motivo, cuando lo registro, entonces no se hace commit y el motivo vuelve al agente.
- **AC-03 — Confirmación humana de criterios pendientes.** Dado criterios pendientes de confirmación humana, cuando se muestra el resumen, entonces confirmo o rechazo cada uno y solo mi confirmación cambia passes.

<a id="hu-11-06"></a>
#### HU-11-06 — Pull Request tras la aprobación

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
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

<a id="hu-11-08.1"></a>
#### HU-11-08.1 — Archivo de progreso del ticket con puntos de control

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 3 · **Desarrollador:** B — Estado  
**Requisitos:** RF-11.8 · **Depende de:** [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-03-01](04b-historias-estado.md#hu-03-01), [HU-01-01](04a-historias-fundacion.md#hu-01-01)

- **Como:** usuario operador
- **Quiero:** que el progreso del ticket se anote en un archivo del repositorio al terminar con normalidad y en puntos de control durante el trabajo
- **Para:** no perder el hilo entre sesiones, ni siquiera si el proceso se termina de golpe
- **Descripción:** El harness escribe un archivo de progreso en el repositorio del ticket con lo hecho, lo pendiente y el estado de cada criterio: al terminar con normalidad y como punto de control al final de cada turno. Si el proceso se termina de golpe, el último punto de control completo se conserva. La cancelación controlada de una herramienta no forma parte de esta historia ([HU-06-03](04c-historias-control.md#hu-06-03)).

**Flujo general**

1. El agente termina un turno.
2. El harness recoge lo hecho, lo pendiente y el estado de cada criterio.
3. Escribe el archivo de progreso de forma atómica (archivo temporal y renombrado).
4. Si el proceso se termina de golpe, el archivo conserva el último punto de control completo.
5. Al reanudar la sesión por su identificador, el progreso está disponible.

**Reglas de negocio**

1. El archivo de progreso vive en el repositorio del ticket; SQLite sigue siendo la fuente del historial completo.
2. El archivo se crea con un formato fijo si no existe.
3. Tres situaciones distintas: terminar con normalidad (esta historia), terminar el proceso (último punto de control, esta historia) y cancelar una herramienta ([HU-06-03](04c-historias-control.md#hu-06-03)).

**Prototipo**

```
progreso-TAREA-14.md  (punto de control tras el turno 6)
- Hecho: validación de email (commit a1b2c3).
- Pendiente: longitud mínima de contraseña.
- Criterios: 1 pasa, 2 no, 3 pendiente de validación humana.
- Nota: auth.py usa un helper nuevo en utils.py.
```

**Criterios de aceptación**

- **AC-01 — Progreso al terminar con normalidad.** Dado el final normal de una sesión de trabajo, cuando el agente termina, entonces el archivo de progreso queda actualizado con lo hecho, lo pendiente y el estado de cada criterio; si no existe, se crea con el formato definido.
- **AC-02 — Punto de control atómico por turno.** Dado el trabajo en curso, cuando termina cada turno del agente, entonces se escribe un punto de control completo mediante escritura atómica (archivo temporal y renombrado); la función se valida en el Sprint 3.
- **AC-03 — Recuperación tras terminar el proceso.** Dado que el proceso se terminó de golpe, cuando el usuario reanuda la sesión por su identificador, entonces el archivo de progreso conserva el último punto de control completo y no queda un archivo a medias.

<a id="hu-11-08.2"></a>
#### HU-11-08.2 — Rutina de arranque al reanudar un ticket

**Prioridad:** Alta · **PHU:** 1 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-11.8 · **Depende de:** [HU-11-08.1](04e-historias-coding-harness.md#hu-11-08.1), [HU-03-04](04b-historias-estado.md#hu-03-04), [HU-11-02](04e-historias-coding-harness.md#hu-11-02)

- **Como:** usuario operador
- **Quiero:** que cada sesión de un ticket empiece leyendo el progreso anterior y comprobando que el proyecto funciona
- **Para:** retomar un ticket sin perder el hilo ni construir sobre código roto
- **Descripción:** Al reanudar un ticket, la sesión arranca con una rutina fija: leer el archivo de progreso, el log reciente de git y comprobar que el proyecto funciona antes de tocar nada. Así un contexto nuevo retoma el trabajo sin adivinar ni construir sobre algo roto.

**Flujo general**

1. El usuario reanuda un ticket.
2. El harness entrega al agente el archivo de progreso y el log reciente de git.
3. Ejecuta la prueba básica del proyecto (comando de la tarea).
4. Si falla, indica reparar eso antes de avanzar; si pasa, el agente elige el criterio pendiente.

**Reglas de negocio**

1. No se avanza con criterios nuevos mientras la prueba básica falle.
2. Se pide al agente avanzar de a un criterio por vez (instrucción del prompt, no regla dura).

**Criterios de aceptación**

- **AC-01 — Arranque con progreso, log y prueba básica.** Dado un ticket con progreso previo, cuando se reanuda, entonces antes de pedir trabajo nuevo el harness entrega al agente el archivo de progreso, el log reciente de git y el resultado de la prueba básica del proyecto.
- **AC-02 — Reparar antes de avanzar.** Dado que la prueba básica falla al arrancar, cuando el agente recibe el estado, entonces se le indica reparar eso antes de avanzar con un criterio nuevo.

---

[← 04d-historias-conexiones.md](04d-historias-conexiones.md) · [Índice](00-indice.md) · [05-trazabilidad.md →](05-trazabilidad.md)
