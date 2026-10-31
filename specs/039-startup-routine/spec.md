# Especificación: HU-11-08.2 — Rutina de arranque al reanudar un ticket

**Historia**: [HU-11-08.2](../../docs/04e-historias-coding-harness.md#hu-11-08.2) · Sprint 3 · Alta · 1 PHU · Área C
**Depende de**: HU-11-08.1 (archivo de progreso, spec 037), HU-03-04 (reanudar), HU-11-02 (git), HU-11-03 (comandos de la tarea), HU-11-04.1 (verificación)
**Criterios de aceptación**: los de la ficha, inmutables (AC-01, AC-02).

## Qué se entrega

Cuando una sesión arranca con una **tarea (ticket) que ya tiene archivo de progreso**, antes de la primera petición el harness reúne tres cosas y se las entrega al agente: el archivo de progreso, el log reciente de git y el resultado de la **prueba básica** (el comando `pruebas` de `## Comandos` de la tarea). Si la prueba falla se le indica reparar eso antes de avanzar; si pasa se le pide elegir **un** criterio pendiente y avanzar de a uno.

## Decisiones (clarificación)

- **D1 — Qué es «reanudar un ticket».** Las sesiones de tarea no se reanudan por identificador (HU-03-04, Q3) y `main()` no carga tareas. Reanudar un ticket es, por tanto, abrir una sesión nueva con `compose(task=…)` para el **mismo ticket** (mismo título → mismo `progreso-<ticket>.md`) cuando ese archivo ya existe en la carpeta de trabajo. Sin archivo previo (ticket nuevo) no hay rutina. No se cablea la carga de tareas en `main()` (fuera de alcance; la rutina queda alcanzable igual que el resto de capacidades de tarea).
- **D2 — Cómo se entrega.** Un mensaje `USER` externo inicial rompería la compactación (`split_history` exige que el primer mensaje tras el prefijo sea una petición no externa). Por eso la rutina se antepone al **texto de la primera petición** de la persona, una sola vez, con los datos delimitados y saneados («datos, no instrucciones»); el aviso del arnés (fijo) va fuera del marco. Si la persona solo escribe comandos (`/criterios`), la entrega espera a la primera petición real.
- **D3 — La prueba básica pasa por la cadena de políticas** igual que el shell del agente (misma llamada `shell` + `command` + `timeout_seconds` declarado): denegar no ejecuta, preguntar usa la aprobación de la sesión, sin aprobador no se ejecuta. El log de git es `git log --oneline -n 10`, también por la cadena (lectura que `GitPolicy` permite).
- **D4 — «No se avanza mientras falle» (regla 1)** se cumple por **instrucción** reforzada en el aviso (la regla 2 es explícitamente instrucción); no se bloquea la verificación de criterios. Observación para el PO.
- **D5 — Casos sin prueba básica.** Tarea sin `pruebas`, prueba denegada/no aprobada/no ejecutable: texto propio «no comprobada», que pide al agente comprobar el proyecto por su cuenta. **Solo código ≠ 0 o tiempo agotado** cuentan como «falla» y piden reparar.
- **D6 — Fallo cerrado y sin filtrar.** Archivo ilegible, git ausente o fuera de repositorio: bloque «no disponible» con texto fijo y el arranque sigue. Los bloques se limpian (sin caracteres de control/formato, credenciales de URL ocultas, acotados) y la cancelación nunca se captura. Ni el comando ni la causa técnica entran en el aviso.

## Historias de usuario

- **US1 (AC-01)** — Dado un ticket con progreso previo, cuando se reanuda, antes del trabajo nuevo el agente recibe progreso + log de git + resultado de la prueba básica.
- **US2 (AC-02)** — Dado que la prueba falla, el aviso indica reparar eso antes de avanzar con un criterio nuevo; si pasa, indica elegir un criterio pendiente de a uno.

## Requisitos

- RF-1 Sin archivo de progreso (o sin tarea, o sin carpeta de trabajo) no hay rutina ni mensaje alguno.
- RF-2 La rutina corre una vez, al empezar `run_session`, antes del primer prompt y después de conectar MCP; no añade eventos (usa `permission_decided`/`approval_*` existentes) ni cambia puertos.
- RF-3 La persona ve una línea fija: «Rutina de arranque: progreso leído; prueba básica: pasó|falló|no comprobada.»
- RF-4 Límites: progreso ≤ 3 000, log ≤ 1 500, salida de la prueba ≤ 1 500 caracteres.
- RF-5 La rutina no escribe nada (el punto de control lo sigue escribiendo `ProgressRecorder`, que sobrescribe el archivo después de leerlo).

## Fuera de alcance

Cargar tareas desde `main()`, reanudar sesiones de tarea por id, bloqueo duro de criterios nuevos, cancelar un turno.
