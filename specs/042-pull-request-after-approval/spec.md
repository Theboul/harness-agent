# Especificación: HU-11-06 — Pull Request tras la aprobación

**Historia**: [HU-11-06](../../docs/04e-historias-coding-harness.md#hu-11-06) · **Área**: C — Control y conexiones · **Prioridad**: Alta · **PHU**: 2 · **Sprint**: 3
**Depende de**: HU-11-05 (aprobación del diff y commit), HU-11-02 (política de git), HU-11-04.1 (criterios con evidencia) · **Rama**: `claude/hu-11-06-pull-request-4840b5` · **Fecha**: 2026-10-31

## Resumen

Cuando la persona aprueba el diff y el arnés hace el commit (HU-11-05), el arnés ofrece cerrar el flujo del ticket: subir la rama con `git push` y crear el Pull Request con la CLI de GitHub (`gh`). Título y descripción salen del ticket, del cambio real (resumen de archivos) y de los criterios con su evidencia. **Cada acción saliente (push y creación) pide una confirmación humana explícita y propia**; nunca ocurre sola. Si falta `gh` o algo falla, el mensaje es claro y el arnés deja la rama commiteada y el texto del PR listo para copiar.

## Alcance

- Dentro: oferta tras el commit aprobado, borrador del PR (título, descripción), confirmación de push, confirmación de creación, ejecución de `git push` y `gh pr create` por un puerto inyectable, enlace del PR en la terminal, camino sin `gh` o con fallo.
- Fuera: crear o cambiar de rama (HU-11-07 trata worktrees), elegir la rama base o el remoto, reintentos, merge del PR, notificar al agente, PR de commits que el agente haga por el shell (siguen la política de HU-11-02: preguntar), rellenar plantillas de PR del repositorio.

## Reglas (de la ficha, inmutables)

1. Push y Pull Request son acciones sensibles y siempre piden aprobación.
2. La descripción incluye el resumen y la lista de criterios con su evidencia.

## Escenarios

### US1 — Pull Request creado tras aprobar (AC-01)
1. Dado un commit aprobado y hecho por el arnés, cuando la persona confirma el push y confirma la creación, entonces se hace push de la rama, se crea el PR con el resumen y los criterios verificados y la terminal muestra su enlace.
2. La descripción lleva: objetivo, commit (id corto), archivos con estado y `+n −m`, y cada criterio con su estado y una línea de evidencia.

### US2 — Push y PR sujetos a aprobación (AC-02)
1. Antes de **cada** acción saliente se pregunta (`1` sí / `2` no) mostrando qué se hará (rama y remoto; título y descripción). No hay opción «recordar» ni aprobación previa que cubra otra acción.
2. Rechazar, fin de la entrada, `/salir` o 3 respuestas inválidas = no. Rechazar el push no pregunta por el PR; rechazar el PR deja la rama subida (si ya se subió).
3. Tras un no, la terminal muestra el texto del PR para copiarlo y dice qué quedó hecho (commit; rama subida o no).

### US3 — Sin `gh` o con fallo (resiliencia pedida por el usuario)
1. Sin `gh` en el equipo: no se pregunta ni se sube nada; mensaje en español («`gh` no está instalado»), texto del PR para copiar y la orden manual `git push -u origin <rama>`.
2. Rama no apta (la predeterminada `main`/`master` o `HEAD` desacoplada): no se ofrece nada; mensaje que lo explica y texto del PR.
3. `git push` o `gh pr create` fallan (sin remoto, sin sesión de `gh`, red, tiempo): una línea fija en español más, como mucho, una línea limpia y acotada del error; la rama sigue commiteada y el texto del PR se muestra.

## Requisitos funcionales

- **FR-001** El PR solo se ofrece tras un commit que hizo `ReviewingRunner` (aprobación humana); se engancha con un observador opcional, sin abrir otra revisión. Un fallo de commit no ofrece nada.
- **FR-002** Orden: comprobar `gh` → leer la rama → mostrar el borrador y confirmar el push → push → confirmar la creación → crear. Ninguna acción saliente sin su confirmación; ninguna confirmación cubre otra.
- **FR-003** Fallar cerrado: cualquier excepción del puerto o del confirmador equivale a «no se hizo»; `CancelledError` se propaga. El flujo nunca hace fallar la sesión ni el turno.
- **FR-004** Título: título del ticket (o el objetivo si no hay), en una línea, ≤ 100 caracteres. Descripción ≤ 20 000 caracteres, Markdown.
- **FR-005** La descripción y todo lo mostrado: sin comandos ni argumentos de criterios, sin caracteres de control, con credenciales de URL ocultas (`hide_url_credentials`); evidencia de una línea ≤ 160 caracteres; lista de archivos ≤ 50 (el resto se resume «y N más»).
- **FR-006** `git push` y `gh` se ejecutan sin shell, con lista fija de argumentos, tiempo máximo, sin preguntas interactivas (`GIT_TERMINAL_PROMPT=0`, `GH_PROMPT_DISABLED=1`) y con el entorno sin las claves de los proveedores. La rama se valida (no vacía, sin espacios ni `-` inicial) antes de usarla.
- **FR-007** El enlace devuelto se acepta solo si es `https://…` de una línea; si no, se informa «PR creado, pero no se pudo leer su enlace».
- **FR-008** Sin cambios en `core/interfaces/`, en el catálogo de eventos ni en `core/loop.py`. Sin dependencias nuevas.
- **FR-009** Solo se activa con tarea, área de trabajo, revisor y confirmador de PR inyectado (`compose(…, pull_request_prompter=…)`); `main()` inyecta `ConsolePullRequestPrompter`. Sin él todo es como en HU-11-05.

## Criterios de éxito

- **SC-001** Con puertos dobles y entrada guionada `1`,`1`: un push y un `create`, con el título y la descripción esperados; con `2`: ninguna llamada saliente.
- **SC-002** Sin `gh` o con fallo: cero errores sin capturar, mensajes en español y el texto del PR visible.
- **SC-003** Un centinela (`VALOR-DE-PRUEBA-123`) puesto en el comando de un criterio o en una URL con credenciales no aparece en el borrador ni en lo mostrado.
- **SC-004** Ninguna prueba hace push real ni usa la red. Cuatro puertas de calidad y `pytest tests/architecture` en exit 0.

## Casos límite

- Evidencia con saltos de línea o backticks: una línea, sin romper el Markdown de la lista.
- Ticket sin título: título del objetivo; objetivo vacío: «Cambios de la tarea».
- Cambios con archivos binarios: sin cifras.
- Cancelación durante push o creación: se propaga.

## Supuestos y decisiones

- **Clarificado (2026-10-31)** P1: ¿Una o dos confirmaciones? → Dos, una por acción saliente (regla 1 y flujo paso 3 de la ficha).
- P2: ¿La «política» es `ApprovalGate`? → No: son acciones del arnés (como el commit de HU-11-05), no llamadas del modelo; el confirmador propio de esta historia es siempre «preguntar» y no recuerda. El `git push`/`gh` que el agente lance por el shell sigue la política de HU-11-02 (preguntar).
- P3: Remoto `origin` y base predeterminada del repositorio (`gh` sin `--base`). Pendiente de ratificar por el PO.
- P4: Sin `gh` no se sube nada (no hay forma de crear el PR; se deja la decisión a la persona).
- P5: La evidencia se incluye acotada porque la ficha lo exige; puede contener salida de pruebas. Riesgo abierto: no hay redacción general (HU-10-02), solo credenciales de URL.
- P6: El texto del PR queda solo en la terminal (no se escribe archivo).
