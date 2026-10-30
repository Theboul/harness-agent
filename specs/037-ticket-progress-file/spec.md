# Especificación: HU-11-08.1 — Archivo de progreso del ticket con puntos de control

**Historia**: [HU-11-08.1](../../docs/04e-historias-coding-harness.md#hu-11-08.1) · **Área**: B — Estado · **Prioridad**: Alta · **PHU**: 1 · **Sprint**: 3
**Depende de**: HU-11-01 (tarea con criterios), HU-03-01 (almacén de sesiones), HU-01-01 (bucle) · **Lo continúa**: HU-11-08.2 (rutina de arranque al reanudar; **fuera de esta spec**)

## Resumen

Una sesión con tarea anota su progreso en un archivo Markdown dentro del repositorio del ticket: **lo hecho, lo pendiente y el estado de cada criterio**. Se escribe como **punto de control al terminar cada turno** y una vez más **al terminar la sesión con normalidad**. La escritura es atómica (archivo temporal + renombrado): si el proceso muere, el archivo conserva el último punto de control completo. SQLite sigue siendo la fuente del historial y de los criterios; el archivo es una copia legible para el relevo entre sesiones.

## Alcance

- Dentro: formato fijo del archivo, nombre derivado del ticket, escritura atómica, punto de control por turno, escritura final, creación si no existe, lectura del archivo existente para la siguiente rutina (`ProgressFile.read`).
- Fuera: leer el progreso y el log de git al reanudar y ejecutar la prueba básica (HU-11-08.2); cancelar una herramienta (HU-06-03); reanudar sesiones de tarea (hoy rechazadas por HU-03-04); registrar commits (el arnés no los conoce).

## Reglas (de la ficha, inmutables)

1. El archivo vive en el repositorio del ticket (la carpeta de trabajo); SQLite es la fuente del historial completo.
2. Si no existe se crea con un formato fijo.
3. Tres situaciones distintas: terminar con normalidad (esta historia), terminar el proceso (último punto de control, esta historia), cancelar una herramienta (HU-06-03).

## Historias de usuario y escenarios

### US1 — Progreso al terminar con normalidad (AC-01)
1. Dada una sesión con tarea, cuando la persona sale con `/salir` (o termina la entrada), entonces el archivo queda actualizado con **Hecho** (criterios cumplidos), **Pendiente** (criterios sin cumplir, distinguiendo los que esperan validación humana) y el estado de **cada** criterio.
2. Si el archivo no existía (por ejemplo, no hubo ningún turno), se crea con el formato fijo.
3. Si ya existía de otra sesión, se reescribe completo con el estado actual.

### US2 — Punto de control atómico por turno (AC-02)
1. Dado el trabajo en curso, cuando termina cada turno, entonces se escribe un punto de control **completo** (nunca parcial) con el número de turno.
2. La escritura se hace en un archivo temporal de la misma carpeta y se renombra sobre el destino; el temporal no se queda si la escritura falla.

### US3 — Recuperación tras terminar el proceso (AC-03)
1. Dado que el proceso se terminó de golpe (también en mitad de una escritura), entonces el archivo contiene el **último punto de control completo** y nunca un archivo a medias.
2. El progreso está disponible para quien reanude: `ProgressFile.read(name)` devuelve el texto del último punto de control (o `None`).

## Requisitos funcionales

- **FR-001** Formato fijo: encabezado con el ticket, sesión, tipo (`punto de control, turno N` o `final de la sesión, N turnos`), fecha; secciones `Hecho`, `Pendiente`, `Criterios` (uno por criterio, en orden, con su estado) y `Nota`.
- **FR-002** Estados de criterio: `cumplido`, `pendiente` (objetivo sin cumplir), `pendiente de validación humana` (semántico sin cumplir).
- **FR-003** El nombre es `progreso-<ticket>.md`, con `<ticket>` el identificador de la tarea (el texto del título antes de `:`) limpio a `[A-Za-z0-9._-]`, o la sesión si no hay título. Siempre dentro de la carpeta de trabajo, nunca fuera.
- **FR-004** Todo texto de la tarea o del agente que entra en el archivo va en una línea, sin caracteres de control y acotado; las credenciales de URL se ocultan. **Nunca** se escriben comandos de criterios, argumentos de herramientas, evidencia de ejecución ni claves.
- **FR-005** Escritura atómica: temporal en la misma carpeta + `fsync` + renombrado; ante un fallo se borra el temporal y se conserva el archivo anterior.
- **FR-006** Un fallo al escribir (disco lleno, permisos, carpeta inexistente) **no tumba el turno ni la salida**: aviso fijo en español por el flujo de avisos; el último punto de control anterior se conserva. La cancelación (`CancelledError`) nunca se captura.
- **FR-007** Solo hay archivo con tarea **y** carpeta de trabajo; sin una de las dos no se escribe nada (sin error).
- **FR-008** Los criterios se leen del almacén protegido (`TaskCriteria.load_criteria`) en cada punto de control; el archivo nunca los modifica ni se usa para marcarlos.
- **FR-009** Sin cambios en los puertos de `core/interfaces/`, el catálogo de eventos ni `core/loop.py`.

## Criterios de éxito

- **SC-001** Tras un turno hay un archivo de progreso completo; tras `/salir` hay uno final.
- **SC-002** Matar la escritura a medias (fallo simulado entre el temporal y el renombrado) deja el archivo anterior intacto y sin temporales.
- **SC-003** Ninguna cadena centinela (`VALOR-DE-PRUEBA-123`) puesta en comando, evidencia o argumentos aparece en el archivo.
- **SC-004** Las cuatro puertas de calidad y `pytest tests/architecture` en exit 0.

## Casos límite

- Título con caracteres peligrosos (`../`, `:`, espacios, nombres reservados de Windows): el nombre resultante es seguro y está en la carpeta.
- Mensaje del agente muy largo o con saltos de línea: una línea, ≤ 500 caracteres.
- Archivo destino que es un enlace simbólico: el renombrado reemplaza el enlace, no escribe a través de él.
- Dos procesos sobre el mismo ticket a la vez: no se soporta (igual que HU-03-04).

## Supuestos y decisiones pendientes

- «Turno» a efectos del punto de control es una petición de la persona al arnés (puede incluir varias rondas de verificación), no una llamada al modelo.
- «Hecho» se deriva de lo que el arnés sabe con certeza: los criterios cumplidos y el número de turnos. No se inventan commits ni archivos modificados (el arnés no los registra). La nota es el último mensaje del agente, acotado. **A confirmar con el PO**: si «Hecho» debe incluir también archivos escritos (requeriría leer eventos).
- El archivo queda dentro del área de trabajo y por eso el agente podría editarlo; no es fuente de verdad (el arnés lo reescribe en el siguiente punto de control).

## Clarificaciones (sesión 2026-10-30)

- P1: ¿Dónde se engancha el punto de control sin tocar `core/loop.py`? → En `run_session` (`bootstrap.py`), tras cada petición, como ya hacen la captura y la compactación; el final, tras `run_cli`. **Decidido.**
- P2: ¿Qué pasa si falla la escritura? → Aviso fijo y el turno sigue (el archivo es copia, SQLite es la verdad). **Decidido** (FR-006).
- P3: ¿Terminar con normalidad incluye Ctrl-C? → No: Ctrl-C o proceso terminado es la situación 2 (último punto de control). Solo `/salir` o el fin de la entrada escriben el final. **Decidido.**
- P4: ¿Contenido de «Hecho» con commits? → No disponible; ver supuestos (pendiente del PO).
