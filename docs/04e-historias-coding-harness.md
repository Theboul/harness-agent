# Historias: Coding Harness, del ticket al Pull Request (E11)

> [← 04d-historias-conexiones.md](04d-historias-conexiones.md) · [Índice](00-indice.md) · [05-trazabilidad.md →](05-trazabilidad.md)  
> Sección 10 del contexto original, continuación: épica E11, el flujo con el que se demuestra el proyecto.  
> Ver también: [02-arquitectura.md](02-arquitectura.md) · [03-plan-sprints.md](03-plan-sprints.md) · [PROGRESO.md](PROGRESO.md)
>
> El estado de cada historia vive solo en [PROGRESO.md](PROGRESO.md); aquí no se repite.

### E11. Coding Harness: del ticket al Pull Request

<a id="hu-11-01"></a>
#### HU-11-01 — Tarea con objetivo, contexto, reglas y criterios de aceptación

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-11.1 · **Depende de:** [HU-03-01](04b-historias-estado.md#hu-03-01), [HU-01-01](04a-historias-fundacion.md#hu-01-01)

- **Como:** usuario operador
- **Quiero:** definir una tarea (ticket) con objetivo, contexto, reglas y criterios de aceptación en un archivo o desde un issue de GitHub
- **Para:** darle al agente una orden verificable y no una instrucción vaga
- **Descripción:** El usuario define una tarea con objetivo, contexto, reglas y criterios de aceptación en un archivo o en un issue de GitHub, y el agente la recibe como una sesión nueva con inicio y fin claros.

**Flujo general**

1. El usuario escribe el archivo de tarea (o indica un issue de GitHub).
2. El sistema lo lee y valida que tenga objetivo y criterios.
3. Crea una sesión nueva para la tarea.
4. Inyecta el objetivo, las reglas y los criterios en el prefijo estable.

**Reglas de negocio**

1. Una sesión corresponde a una tarea.
2. Una tarea sin criterios de aceptación se rechaza.
3. El objetivo y los criterios viven fuera del historial compactable.

**Prototipo**

```
TAREA-14
Objetivo: corregir la validación del login.
Criterios:
  - El email es obligatorio.
  - La contraseña tiene al menos 8 caracteres.
  - Las pruebas pasan.
  - No se modifica la API existente.
```

**Criterios de aceptación**

- **AC-01 — Sesión creada desde la tarea.** Dado un archivo de tarea con objetivo, reglas y criterios, cuando se inicia la tarea, entonces se crea una sesión nueva con ese contenido en el contexto estable.
- **AC-02 — Tarea sin criterios rechazada.** Dado un archivo de tarea sin criterios de aceptación, cuando se inicia, entonces el sistema lo rechaza e indica qué falta.

<a id="hu-11-02"></a>
#### HU-11-02 — Herramientas Git: estado, diff, rama y commit

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-11.2 · **Depende de:** [HU-01-02](04a-historias-fundacion.md#hu-01-02), [HU-05-01](04c-historias-control.md#hu-05-01)

- **Como:** agente principal
- **Quiero:** consultar el estado y el diff, crear una rama y hacer commit
- **Para:** entregar los cambios de una tarea de forma ordenada
- **Descripción:** El agente consulta el estado y el diff de un repositorio, crea una rama y hace commit mediante herramientas Git que pasan por la política de permisos.

**Flujo general**

1. El agente pide el estado o el diff.
2. La herramienta ejecuta Git y devuelve el resultado estructurado y acotado.
3. Para crear rama o commit, la política evalúa la acción.
4. Si requiere aprobación, se pide al usuario.

**Reglas de negocio**

1. Estado y diff son de bajo riesgo; commit requiere aprobación.
2. Los resultados largos se recortan con marca de omisión.

**Criterios de aceptación**

- **AC-01 — Diff estructurado y acotado.** Dado un repositorio con cambios, cuando el agente pide el diff, entonces recibe los cambios en formato estructurado y acotado.
- **AC-02 — Commit sujeto a aprobación.** Dado una solicitud de commit, cuando se evalúa, entonces la política la clasifica como acción que requiere aprobación.

<a id="hu-11-03"></a>
#### HU-11-03 — Herramienta para ejecutar pruebas y lint

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** C — Control y conexiones  
**Requisitos:** RF-11.3 · **Depende de:** [HU-01-04](04a-historias-fundacion.md#hu-01-04), [HU-02-02](04b-historias-estado.md#hu-02-02)

- **Como:** agente principal
- **Quiero:** ejecutar las pruebas y el lint del proyecto y recibir un resultado estructurado
- **Para:** saber si mis cambios funcionan y corregir los errores
- **Descripción:** El agente ejecuta las pruebas y el lint del proyecto como herramienta y recibe un resultado estructurado que le permite corregir errores.

**Flujo general**

1. El agente invoca la herramienta de pruebas.
2. El sistema ejecuta el comando configurado con tiempo máximo.
3. Analiza la salida: pasaron, fallaron y mensajes.
4. Devuelve el resultado estructurado al agente.

**Reglas de negocio**

1. El comando de pruebas y de lint se define en la configuración del proyecto.
2. Ejecutar pruebas se permite automáticamente; el tiempo máximo es obligatorio.

**Criterios de aceptación**

- **AC-01 — Resultado estructurado de pruebas.** Dado un proyecto con una prueba fallida, cuando el agente ejecuta las pruebas, entonces recibe cuántas pasaron, cuáles fallaron y el mensaje de cada fallo.
- **AC-02 — Salida larga recortada.** Dado una salida muy larga de pruebas, cuando vuelve al contexto, entonces se recorta con marca de omisión.

<a id="hu-11-04"></a>
#### HU-11-04 — Verificación de criterios de aceptación antes de terminar

**Prioridad:** Alta · **PHU:** 2 · **Sprint:** Sprint 3 · **Desarrollador:** A — Núcleo  
**Requisitos:** RF-11.4 · **Depende de:** [HU-11-01](04e-historias-coding-harness.md#hu-11-01), [HU-11-03](04e-historias-coding-harness.md#hu-11-03)

- **Como:** usuario operador
- **Quiero:** que la tarea solo se dé por terminada si cumple cada criterio verificable
- **Para:** no aceptar código solo porque la IA lo generó
- **Descripción:** El sistema no da la tarea por terminada hasta que el agente aporta evidencia de que cada criterio de aceptación se cumple.

**Flujo general**

1. El agente propone terminar la tarea.
2. El sistema pide evidencia por cada criterio.
3. El agente reporta la evidencia (por ejemplo, el resultado de las pruebas).
4. Si falta algún criterio, la tarea sigue abierta y el agente recibe qué falta.

**Reglas de negocio**

1. Una tarea solo se cierra si todos los criterios tienen evidencia.
2. El usuario puede ver el estado de cada criterio.

**Criterios de aceptación**

- **AC-01 — Evidencia por criterio.** Dado una tarea con tres criterios, cuando el agente propone terminarla, entonces el sistema pide evidencia por cada criterio y marca cuáles cumplen.
- **AC-02 — Tarea abierta si falta evidencia.** Dado un criterio sin evidencia, cuando se intenta cerrar la tarea, entonces queda abierta y el agente recibe qué falta.

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

---

[← 04d-historias-conexiones.md](04d-historias-conexiones.md) · [Índice](00-indice.md) · [05-trazabilidad.md →](05-trazabilidad.md)
