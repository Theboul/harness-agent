# Implementation Plan: HU-06-01 — CLI básica con eventos en tiempo real

**Branch**: `009-basic-cli-events` (directorio de la spec; el trabajo se hace en la rama `gustavo`) | **Date**: 2026-10-20 | **Spec**: [specs/009-basic-cli-events/spec.md](spec.md)

**Input**: Feature specification from `/specs/009-basic-cli-events/spec.md`

**Directrices del usuario**: la CLI vive en `src/harness_agent/cli/` (`render.py` convierte eventos en líneas de texto y `app.py` es el ciclo de entrada); solo biblioteca estándar, sin colores ni ANSI; salida y entrada inyectables (por defecto `sys.stdout` y `sys.stdin`); la CLI se suscribe al puerto del bus y recibe por inyección el bus y una función asíncrona de turno; muestra herramienta solicitada y terminada, mensaje del asistente, denegación o pregunta de permiso, error del proveedor y límite alcanzado, sin inventar campos; errores con causa y acción sugerida desde una tabla de categorías; entrada mínima (`/ayuda`, `/salir`); los fallos de escritura se propagan al bus; los caracteres de control se eliminan; pruebas con flujos en memoria y el bucle real; prueba de arquitectura de fronteras.

---

## Summary

Añadir dos módulos en `src/harness_agent/cli/`: `render.py`, con funciones puras que convierten un `Event` en texto (saneado, acotado y con la tabla de categorías de error), y `app.py`, con `attach_renderer(bus, output)` (suscribe un manejador por cada tipo mostrado que escribe la línea en el flujo de salida) y `run_cli(bus, run_turn, input_stream, output)` (el ciclo de entrada: tarea, `/ayuda`, `/salir`, comando desconocido, línea vacía y fin de entrada; devuelve el código de salida: 0 si termina limpio y 1 si el turno falla). `cli/__init__.py` expone la API pública. La CLI solo importa la biblioteca estándar y la API pública de `harness_agent.core`. No se toca ningún archivo del núcleo, del bus ni de los dobles; la verificación es un render con eventos construidos a mano, una integración con el bucle real de A y el bus real con flujos en memoria, y una prueba de arquitectura de fronteras entre `core/` y `cli/`.

---

## Technical Context

**Language/Version**: Python 3.12, única versión soportada (PD-07).

**Primary Dependencies**: solo biblioteca estándar (`collections.abc`, `typing`, `unicodedata`, `sys`, `asyncio` solo para los tipos). Sin dependencias nuevas de ejecución ni de desarrollo.

**Storage**: N/A. La CLI no guarda nada; el historial y las sesiones son HU-03-xx.

**Testing**: `pytest` con `io.StringIO` como entrada y salida, `InMemoryEventBus`, `make_rig` de `tests/core/support.py`, `ScriptedProvider`, `RecordingTool` y `ScriptedPolicy`. Sin red, sin consola real, sin proveedor real.

**Target Platform**: Windows y Linux (matriz de CI).

**Project Type**: Biblioteca modular; `cli/` es la capa exterior (terminal), nunca el núcleo.

**Performance Goals**: mostrar un evento en menos de 1 ms de media (SC-008); es una transformación de texto y una escritura.

**Constraints**:
1. `core/interfaces/*`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `tests/doubles/*` y `docs/archivo/` quedan sin modificar.
2. `core/` no importa `cli/`; `cli/` solo importa biblioteca estándar y la API pública de `harness_agent.core` (nombres de `harness_agent.core.__all__`), sin adaptadores, observabilidad ni raíz de composición.
3. `mypy --strict` sobre `src` y `tests`; `ruff` con línea de 100 columnas.
4. La CLI lee solo los campos que el bucle publica hoy (spec, Assumptions); no ensancha la carga ni la inventa.
5. Los textos del modelo o de herramientas se tratan como datos: sin caracteres de control y acotados donde la spec lo pide.
6. Sin construir proveedor, registro ni bucle; sin leer configuración; sin aprobación interactiva ni Ctrl+C (Principio VI).

**Scale/Scope**: 2 módulos de código nuevos (`render.py`, `app.py`) y la API pública en `cli/__init__.py`; 1 contrato; 5 módulos de prueba nuevos (3 unitarios, 1 de integración y 1 de arquitectura).

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / Restricción | Requisito | Pre-diseño | Post-diseño | Evidencia |
|---|---|---|---|---|
| I. Una historia por especificación | Solo HU-06-01 | Pasa | Pasa | Spec y plan solo de HU-06-01 |
| II. Microtareas de 15 a 40 min | Ninguna tarea pasa de 40 min (límite absoluto 60) | Pasa | Pasa | `tasks.md`: 7 tareas de trabajo (≤ 40 min) más inicio, cierre y las dos humanas |
| III. Núcleo modular, tipado, sin dependencias externas | `core/` no depende de `cli/`; solo biblioteca estándar | Pasa | Pasa | D1 y D2; prueba de arquitectura (T007) |
| IV. Pruebas, calidad y CI multiplataforma | Pruebas primero; ruff, mypy, pytest en Windows y Linux | Pasa | Pasa | Cada tarea escribe las pruebas antes del código; matriz de CI (T010) |
| V. Inmutabilidad de criterios | AC-01, AC-02, reglas y prototipo copiados tal cual | Pasa | Pasa | Spec, sección «Criterios de aceptación…» |
| VI. Disciplina de sprints | Nada de sprints futuros | Pasa | Pasa | Sin proveedor real, configuración, aprobación, Ctrl+C, colores ni comandos de sesión; el límite alcanzado se muestra sin leer su carga |
| VII. Consulta documental quirúrgica | Solo las fuentes necesarias | Pasa | Pasa | HU-06-01, Sp1-37 a Sp1-39, payloads del bucle, especificaciones 010 y 011 |
| VIII. Registro en `docs/PROGRESO.md` | `En curso` y `En revisión` con registro | Pasa | Pasa | T001 y T008; cada tarea anota su registro dentro de sus 5 min |
| IX. Definition of Done estricta | Revisión cruzada por otra área y CI | Pasa | Pasa | T009 (A o B revisa) y T010 (CI); HU-00-01 sigue pendiente de aprobación técnica |
| X. Inmutabilidad de `docs/archivo/` | No se toca | Pasa | Pasa | Verificación con `git diff` en T008 |
| Hexagonal (skill `arquitectura-hexagonal-clean`) | La CLI se conecta por el puerto; no contiene reglas | Pasa | Pasa | D1; la CLI solo suscribe manejadores al `EventBus` y escribe texto |
| Estructura de carpetas (skill `estructura-carpetas-harness`) | «Imprime o lee de la terminal» → `cli/` | Pasa | Pasa | `cli/render.py` y `cli/app.py` según el árbol acordado |

**Resultado**: sin violaciones; no hace falta tabla de complejidad.

---

## Project Structure

### Documentation (this feature)

```text
specs/009-basic-cli-events/
├── spec.md
├── plan.md                              # este archivo
├── research.md                          # decisiones R-01 a R-12
├── data-model.md                        # líneas, tabla de categorías, constantes
├── quickstart.md                        # cómo verificar la historia
├── contracts/
│   └── cli_contract.md                  # formatos de línea, tabla, entrada y fronteras
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/harness_agent/cli/
├── __init__.py                          # M: API pública (render_event, attach_renderer, run_cli)
├── render.py                            # NUEVO: sanear, acotar, tabla de categorías, render_event
└── app.py                               # NUEVO: attach_renderer y run_cli

tests/
├── unit/cli/__init__.py                                 # NUEVO
├── unit/cli/test_render_text.py                         # NUEVO: saneado, acotado y tabla
├── unit/cli/test_render_events.py                       # NUEVO: una línea por tipo de evento
├── unit/cli/test_app_output.py                          # NUEVO: suscripción, salida y fallos de escritura
├── unit/cli/test_app_input.py                           # NUEVO: ciclo de entrada y comandos
├── integration/test_cli_agent_loop.py                   # NUEVO: AC-01 y AC-02 con el bucle real
└── architecture/test_cli_boundaries.py                  # NUEVO: core no importa cli; cli solo API pública
docs/PROGRESO.md                                         # M: En curso / En revisión y registro
```

**Structure Decision**: dos módulos planos, como en el árbol acordado (`render.py`, `app.py`); la lógica de texto (pura, sin flujos) va en `render.py` y todo lo que toca flujos y el bus va en `app.py`, de modo que el render se prueba sin flujos y el ciclo sin formatos. No hay `__main__`: el punto de entrada ejecutable lo traerá la raíz de composición. No se tocan `core/`, `adapters/` ni los dobles.

---

## Decisiones de diseño y desviaciones

- **D1 — La CLI solo muestra**: no decide, no valida, no ejecuta (regla de negocio 1). Todo lo que sabe del núcleo es el catálogo de eventos, el puerto del bus y las categorías que el bucle publica, que están en la tabla de `render.py`.
- **D2 — Solo la API pública de `core`**: `cli/` importa `from harness_agent.core import ...` y nada de submódulos (`harness_agent.core.loop`, `.interfaces`, …). La prueba de arquitectura lo verifica contra `harness_agent.core.__all__`. `EventBus`, `Event` y `EventType` están en esa API. El tipo de la función de turno se declara con `Callable[[str], Awaitable[object]]`, sin importar `TurnResult`.
- **D3 — Dos funciones públicas y un ciclo**: `attach_renderer(bus, output)` (Sp1-37) suscribe una vez los seis tipos mostrados y `run_cli(bus, run_turn, ...)` (Sp1-39) la llama al empezar y gestiona la entrada. El bus no tiene desuscripción: llamar dos veces a `attach_renderer` con el mismo bus duplica la salida; queda documentado.
- **D4 — La salida se adapta al flujo sin modificarlo**: en vez de reconfigurar `sys.stdout` (un efecto global), cada línea se codifica con la codificación del flujo y `errors="replace"` y se decodifica de vuelta antes de escribir; si el flujo no declara codificación (`io.StringIO`) se escribe tal cual.
- **D5 — Lectura de la entrada**: `run_cli` es una corrutina que lee con `readline()` del flujo de entrada de forma bloqueante entre turnos. Es suficiente porque nada más corre en el bucle de eventos durante la espera; la cancelación con Ctrl+C (HU-06-03) revisará esto. Alternativa descartada por ahora: `asyncio.to_thread`.
- **D6 — Una denegación se informa una sola vez**: la decisión de permiso (denegación o pregunta) muestra causa y sugerencia; el estado final de la herramienta con esas categorías muestra solo «no se ejecutó».
- **D7 — Límite alcanzado sin carga**: el texto es fijo porque el bucle de Sprint 1 aún no lo publica y su carga no está definida (HU-01-06). Cuando exista, una historia posterior ampliará la tabla.
- **D8 — Diferencia con el prototipo (se indica porque el documento gana donde fija algo)**: el prototipo muestra los argumentos de la herramienta y la ruta que no existe; la carga actual solo trae `name` y `category`. La causa sale de la categoría. Ampliar la carga corresponde al núcleo (A) y queda fuera.
- **D9 — Excepciones de la función de turno (decidida por el responsable)**: `run_cli` captura solo las `Exception` ordinarias que lance la función de turno (incluido `EventDeliveryError`), escribe UNA línea («x Error: el turno terminó con un fallo interno (<TipoDeError>). Sugerencia: revisa el registro de eventos.», tipo saneado y acotado a 64 caracteres, sin el mensaje, la traza ni la carga) y termina la sesión devolviendo un código de salida distinto de cero (falla cerrada). `CancelledError`, `KeyboardInterrupt` y cualquier `BaseException` que no sea `Exception` se propagan sin tocar. Si escribir esa línea falla, ese fallo se propaga. La firma de retorno de `run_cli` pasa de `None` a `int` (0 limpio, 1 fallo del turno).
- **D10 — Controles bidireccionales**: además de los caracteres de control, se eliminan los de dirección de texto (U+202A a U+202E y U+2066 a U+2069), que permiten simular otro texto en pantalla. Se trata como parte de «caracteres de control».
- **D11 — Presupuesto del plan de sprint**: Sp1-37 + Sp1-38 + Sp1-39 suman 5 h (300 min); `tasks.md` compara la estimación (335 min) con ese presupuesto; se pasa por 35 min (12 %) por las tareas transversales, que el plan de sprint no presupuesta (las tres tareas F5 suman 190 min); es un aviso, sin recorte de alcance.
- **D12 — Ratificación de HU-00-01 pendiente**: HU-00-01 sigue `Pendiente de aprobación técnica` (Sp1-03). La historia no modifica ningún puerto, pero la ratificación debe producirse antes de pasar HU-06-01 a `Hecha` (T008 y T009 lo registran).

---

## Riesgos y cómo se comprueban

| Riesgo | Mitigación |
|---|---|
| Un texto del modelo controla la terminal con secuencias de escape | Saneado en `render.py` y pruebas con todos los controles (T002); la salida pasa siempre por el saneado |
| Una traza o la carga cruda llegan a la pantalla | La línea se construye solo con campos conocidos y acotados; prueba con centinela en la carga de una categoría desconocida (T003) |
| Un fallo de escritura se silencia | El manejador no captura nada; prueba con flujo cerrado y el bus real (T004, SC-006) |
| La tabla no cubre una categoría del bucle | Prueba que recorre la lista de categorías del bucle y exige entrada en la tabla (T002) |
| La CLI se acopla al núcleo | Prueba de arquitectura de la API pública (T007) |
| La consola de Windows no admite un carácter | Codificación con sustitución y prueba con un flujo en `cp1252` (T004) |
| Se duplica la salida al suscribir dos veces | Documentado (D3); `run_cli` solo suscribe una vez por llamada |
| Un fallo del turno llega a la terminal como traza | `run_cli` captura la `Exception` del turno, muestra una línea con el tipo y devuelve 1 (T006, FR-026); las `BaseException` se propagan |
