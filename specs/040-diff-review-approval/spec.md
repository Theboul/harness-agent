# Especificación: HU-11-05 — Resumen de cambios y aprobación humana del diff

**Historia**: [HU-11-05](../../docs/04e-historias-coding-harness.md#hu-11-05) · **Área**: C — Control y conexiones · **Prioridad**: Alta · **PHU**: 2 · **Sprint**: 3
**Depende de**: HU-11-02 (política de git), HU-05-03 (aprobación), HU-11-04.1 (verificación de criterios) · **Lo continúa**: HU-11-06 (Pull Request; **fuera de esta spec**)

## Resumen

Cuando el agente propone terminar una tarea y todos sus criterios objetivos están cumplidos, el arnés lee el cambio **real** del repositorio (no lo que el agente dice haber hecho), muestra un resumen (archivos tocados, líneas añadidas y quitadas) y el diff, deja a la persona confirmar o rechazar cada criterio semántico pendiente y le pide la decisión: aprobar (el arnés hace el commit), ver el diff completo o rechazar con motivo (no hay commit y el motivo vuelve al agente). Sin aprobación no se hace commit.

## Alcance

- Dentro: lectura del cambio con git (puerto inyectable), resumen y diff en la terminal, menú de decisión, confirmación/rechazo de criterios semánticos (única vía, tras la verificación, por la que un criterio semántico pasa a cumplido), commit tras aprobar, motivo de rechazo de vuelta al agente.
- Fuera: Pull Request y push (HU-11-06); informe del subagente verificador (HU-11-04.2, aún no existe: la línea «informe del verificador» del prototipo no se muestra); resumen redactado por el modelo; cancelar un turno; cargar tareas desde `main()` (hoy solo `compose(task=…)`).

## Reglas (de la ficha, inmutables)

1. Nada sale del repositorio sin aprobación.
2. El resumen se genera a partir del diff real, no de lo que el agente dice haber hecho.
3. Solo la confirmación humana cambia passes en un criterio semántico.

## Escenarios

### US1 — Diff y resumen antes de decidir (AC-01)
1. Dada una tarea con todos los criterios objetivos cumplidos y cambios en el área de trabajo, cuando el agente propone terminar, entonces la terminal muestra el resumen (título, archivos con estado y `+n −m`, totales), el diff y el menú, y espera.
2. El resumen se calcula con `git diff` (no con texto del agente). Los archivos nuevos (sin seguimiento) cuentan.
3. Sin cambios, o con algún criterio objetivo sin cumplir, no se abre la revisión.

### US2 — Rechazo con motivo (AC-02)
1. Dado que la persona elige rechazar, escribe un motivo (opcional) y lo registra, entonces no se hace commit y el motivo, saneado como el de HU-05-04, llega al agente como un mensaje del usuario en un turno nuevo; el agente puede corregir y volver a proponer terminar (se vuelve a verificar y a revisar).
2. Fin de la entrada o `/salir` en el menú = sin decisión: no hay commit, no vuelve nada al agente y la sesión sigue.

### US3 — Confirmación humana de criterios pendientes (AC-03)
1. Dados criterios semánticos pendientes, cuando se muestra el resumen, entonces la persona confirma (`4 N`) o rechaza (`5 N`, con motivo opcional) cada uno. Solo la confirmación marca el criterio como cumplido (con evidencia «confirmado por la persona»); rechazar equivale a rechazar el diff con ese motivo.
2. Aprobar con criterios semánticos sin confirmar no está permitido (falla cerrada): el menú lo explica y no hace commit.

## Requisitos funcionales

- **FR-001** El cambio se lee por un puerto de núcleo (`ChangeSource`) sin cambiar `core/interfaces/`; el adaptador usa solo git de **lectura** para mostrar (índice temporal propio: el índice real no se toca) y `git add` + `git commit` únicamente tras la aprobación.
- **FR-002** El resumen cuenta archivos, líneas añadidas y quitadas (binarios sin cifras) y el estado de cada archivo (nuevo, modificado, eliminado).
- **FR-003** El archivo de progreso del ticket (`progreso-*.md`) no entra en el resumen ni en el commit.
- **FR-004** Todo texto del diff que se muestra pasa por la limpieza de terminal (sin caracteres de control ni secuencias de escape) y se ocultan credenciales de URL; el commit usa el contenido real, no el mostrado.
- **FR-005** Un diff mayor que el tope (400 000 caracteres) no se puede aprobar (el resumen sí se muestra): falla cerrada.
- **FR-006** Aprobar exige: criterios objetivos cumplidos, ningún semántico pendiente, diff revisable y cambios no vacíos. El núcleo lo comprueba aunque el revisor devuelva «aprobar».
- **FR-007** El commit lleva un mensaje derivado del título y el objetivo de la tarea, en una línea. Un fallo de git (identidad, hooks, índice) se informa con una línea acotada y limpia y no hay reintento.
- **FR-008** La confirmación pasa por `CriteriaVerifier.confirm`, que comprueba que el criterio es semántico y coincide con la definición, y es el mismo sitio donde se llama a `mark_passes` (sigue habiendo **una** llamada en `src/`). Publica `criterion_verified` con `status: confirmado_humano`.
- **FR-009** Una verificación posterior no deshace una confirmación: el criterio semántico con `passes` se informa `confirmado_humano`, no `pendiente_humano`, y cuenta como satisfecho en `task_state`.
- **FR-010** Sin cambios en `core/interfaces/`, el catálogo de eventos ni `core/loop.py`. El bucle de rechazo no tiene contador propio: lo acotan los límites de sesión.
- **FR-011** Solo se activa con tarea, área de trabajo y revisor inyectado (`compose(task=…, reviewer=…)`); `main()` inyecta `ConsoleReviewer`.

## Criterios de éxito

- **SC-001** Con un doble de git y un revisor guionado: aprobar hace exactamente un commit; rechazar no hace ninguno y el motivo llega al agente.
- **SC-002** Con git real en un repositorio temporal: el resumen coincide con los cambios, el índice real no cambia al leer y el commit contiene los archivos (nuevos incluidos) y no el archivo de progreso.
- **SC-003** Ningún centinela (`VALOR-DE-PRUEBA-123`) puesto en comando de criterio o evidencia aparece en la vista; credenciales de URL del diff ocultas.
- **SC-004** Las cuatro puertas de calidad y `pytest tests/architecture` en exit 0.

## Casos límite

- No es un repositorio git, o git no está: la revisión informa «no se pudo leer el cambio» y no hay commit (falla cerrada); la sesión sigue.
- Repositorio sin commits (HEAD sin nacer): el diff se calcula contra el árbol vacío.
- Archivo con ruta rara (espacios, acentos, saltos de línea): se lee con `-z`.
- Nombre de archivo con secuencias de escape: limpio al mostrar.
- Criterio rechazado y diff sin cambios: igual se devuelve al agente.

## Supuestos y decisiones

- **Clarificado (2026-10-31)** P1: ¿Quién «pide commit»? → Proponer terminar con criterios objetivos cumplidos (turno `COMPLETED`); el commit lo hace el arnés tras aprobar. El `git commit` que el agente lance por el shell sigue la política de HU-11-02 (preguntar) y **no** pasa por esta revisión (hallazgo para A/C: denegarlo mientras haya revisión).
- P2: ¿Dónde se engancha sin tocar el bucle? → Un `ReviewingRunner` envuelve al `VerifyingRunner`; se cablea solo en `bootstrap.py`.
- P3: ¿Dónde se muestra «Pruebas: 24/24»? → El arnés no interpreta salida de pruebas; se muestran los criterios objetivos (`n de m cumplidos`).
- P4: ¿Descripción por archivo («validación de email»)? → No: sería texto del modelo (regla 2). Se muestran estado y cifras.
- P5: ¿Aprobar con semánticos pendientes? → No (FR-006). Pendiente de ratificar por el PO.
- P6: Una confirmación no se invalida si el agente cambia el código después (el almacén no puede revocar passes). Hallazgo.
- Opciones del menú: `1` aprobar y commit, `2` ver diff completo, `3` rechazar con motivo, `4 N` confirmar criterio N, `5 N` rechazar criterio N.
