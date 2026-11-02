# Especificación: HU-06-07 (propuesta) — Pulido de uso del arnés

**Rama**: `claude/ola5-pulido-uso-ad21dd` · **Responsable**: C — Control y conexiones · **Historia propuesta** (pendiente de ratificación del PO, como HU-06-05 y HU-06-06)
**Depende de**: HU-06-06 (`/plan`, `/implementar`), HU-07-02 (`LiteLLMProvider`), HU-11-02 (`git_instructions`), HU-06-02 (`ConsoleQuestioner`)

## Resumen

Cuatro problemas detectados al usar el arnés instalado en una carpeta de prueba:

1. Un 400 de Groq (`gpt-oss-120b`) tras `preguntar_usuario` no se puede diagnosticar: el texto del proveedor se descarta a propósito.
2. En `/plan` el modelo no sabe que está en solo lectura: reintenta `escribir_archivo` y `shell` unas diez veces y cada intento gasta un turno del límite.
3. Las instrucciones de git («trabaja en una rama propia…») se envían en toda sesión con área, y el modelo propone ramas y commits para pedidos triviales.
4. Pasar de planear a implementar obliga a escribir `/implementar`.

## Clarificaciones

### Sesión 2026-11-02 (sin preguntas al PO; opción más simple)

- Q: ¿Cómo se activa la depuración del proveedor? → A: variable de entorno `HARNESS_DEBUG_PROVIDER` (`1`, `true`, `si`, `yes`, `on`, sin distinguir mayúsculas). La lee `bootstrap.py` del entorno combinado (con el `.env`); el adaptador recibe un invocable `debug` y no lee el entorno.
- Q: ¿Dónde sale el detalle? → A: `sys.stderr`, una línea `[depuración del proveedor] <texto>`, depurada con `_clean` (clave) y el redactor general, ≤ 2 000 caracteres. Nunca a disco. Puede contener texto de la persona (el proveedor suele repetir la petición): por eso es opt-in.
- Q: ¿«Un mensaje de rol USER» o texto antepuesto a la petición? → A: el aviso de modo viaja **antepuesto a la siguiente petición** de la persona (un solo mensaje `USER`), como la rutina de arranque (HU-11-08.2). Un `USER` suelto dejaría dos mensajes `USER` seguidos (algunos proveedores los rechazan) y podría volverse la «petición inicial» protegida de la compactación. Entra una vez por cambio de modo; si el modelo ya conoce ese modo no se repite; si se cambia y se vuelve antes de una petición, no se envía nada.
- Q: ¿Ocultar las herramientas de escritura del registro en `/plan`? → A: **no** en esta historia. El registro lo comparten el verificador, MCP y `/nueva`; ocultar y restaurar exige un envoltorio con estado y riesgo de dejar herramientas ocultas. La política ya las deniega. Queda como observación.
- Q: ¿`/nueva` en modo plan? → A: reinicia lo que el modelo sabe del modo; si sigue en plan, la siguiente petición vuelve a avisar.
- Q: ¿Solo lectura fijado al arrancar? → A: no se ofrece implementar.
- Q: ¿La oferta la hace el modelo? → A: no; la hace el arnés al cerrar el turno. Sin respuesta, fin de entrada, `/salir`, entrada inválida o excepción = seguir en solo lectura.
- Fuera de alcance: reinicio de los límites en `/nueva` (el contador vive en `core/loop.py`, protegido, de A). Solicitud a A en `PROGRESO.md`.

## Requisitos funcionales

- **FR-001** Con `HARNESS_DEBUG_PROVIDER` activo, un fallo de la llamada al modelo escribe en `stderr` el detalle limpio y acotado; apagado (por defecto) no se escribe nada, y el mensaje canónico del error no cambia nunca.
- **FR-002** `/plan` deja pendiente un aviso de planificación (solo lectura; sin herramientas de escritura ni shell salvo lecturas) e `/implementar` el contrario; se antepone a la siguiente petición una sola vez y no se repite si el modo no cambió.
- **FR-003** `git_instructions()` solo entra al prefijo con área **y** tarea.
- **FR-004** Al cerrar un turno en modo planificación (no fijado al arrancar) el arnés ofrece `[1] pasar a implementar [2] seguir planificando`; `1` hace lo mismo que `/implementar`.
- **FR-005** No cambian `core/interfaces/`, `core/events.py`, `core/loop.py` ni `tests/doubles/`.

## Criterios de aceptación propuestos

- **AC-01** Con `HARNESS_DEBUG_PROVIDER=1`, cuando el proveedor falla con un 400, `stderr` muestra el texto sin la clave y ≤ 2 000 caracteres; sin la variable no aparece nada.
- **AC-02** Tras `/plan`, el mensaje `USER` de la siguiente petición empieza por el aviso de solo lectura, una sola vez; tras `/implementar` llega el aviso contrario.
- **AC-03** Una sesión sin tarea y con área no lleva instrucciones de git en el prefijo; con tarea sí.
- **AC-04** Con un turno terminado en `/plan`, la respuesta `1` aplica `/implementar`; cualquier otra mantiene el solo lectura; con `--solo-lectura` no se pregunta.
- **AC-05** Ninguna clave aparece en la salida de depuración, avisos ni archivos.

## Criterios de éxito

- **SC-001** Cuatro puertas de calidad y `pytest tests/architecture` en exit 0; 100 % de líneas y ramas de lo nuevo.
- **SC-002** Diff de archivos protegidos vacío.
