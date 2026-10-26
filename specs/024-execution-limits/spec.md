# Feature Specification: HU-01-06 — Límites de turnos, tiempo y consumo por sesión

**Feature Branch**: `claude/hu-01-06-limits-8aa045` (el directorio de la spec es `024-execution-limits`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-25

**Status**: Borrador (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 2 | **Responsable**: A — Núcleo | **Requisitos**: RF-1.6 | **Depende de**: HU-01-01 (bucle básico, integrada)

**Input**: User description: "HU-01-06 — Límites de turnos, tiempo y consumo por sesión (docs/04a-historias-fundacion.md#hu-01-06). Antes de cada llamada al modelo el bucle comprueba los límites configurados; si alguno se alcanza, se detiene, publica `LIMIT_REACHED` y explica el motivo al usuario. El consumo se mide en tokens; el costo en dinero es solo informativo. Fuera de alcance: cambios en `core/events.py` y `core/interfaces/`, varias llamadas por turno (HU-01-07), detección de llamadas repetidas (HU-01-08), compactación (HU-02-xx), reanudar sesiones (HU-03-04)."

## Clarifications

### Session 2026-10-25

Sesión no interactiva (la sesión se ejecuta sin el usuario delante): se resuelven por defecto las ambigüedades que la ficha deja abiertas, eligiendo la opción que falla cerrada, y se marcan **pendientes de ratificación del PO y de A**. Ninguna cambia un criterio de aceptación.

- Q: ¿Qué es un «turno» para el límite de turnos? → A: Una llamada al modelo (una vuelta del bucle). Alternativa descartada: una tarea del usuario (`run_turn`), porque no frena un bucle sin salida dentro de una sola tarea, que es el riesgo que nombra la historia.
- Q: ¿Los contadores son por tarea o por sesión? → A: Por sesión (el título lo dice): viven en el `AgentLoop`, que la raíz de composición crea una vez por sesión, y se acumulan entre tareas. Agotado un límite, las tareas siguientes se detienen igual (falla cerrada) hasta abrir otra sesión o subir el límite.
- Q: ¿El tiempo incluye la espera del usuario entre tareas? → A: No. Cuenta solo el tiempo dentro de las tareas (reloj monótono inyectado); un reloj de pared desde el arranque agotaría la sesión mientras el usuario piensa.
- Q: ¿Alcanzar es igual o mayor? → A: «Se alcanza» con `>=`: con `max_turns=N` se hacen N llamadas y la N+1 no. Con consumo, `used >= max_tokens` impide la siguiente llamada.
- Q: ¿Cómo explica el motivo el sistema? → A: El evento `LIMIT_REACHED` lleva `{limit, used, maximum}` (solo enteros y la clave del límite; ya existe en el catálogo, no se cambia `core/events.py`) y la CLI lo traduce a una línea en español. Esto exige un cambio **mínimo y aditivo** en `cli/render.py` (archivo protegido para historias que no son de CLI; aquí lo exige el AC-01 «explica el motivo»), declarado como desviación.
- Q: ¿Cómo se informa de la parada al código que llama al bucle? → A: Nuevo estado `TurnStatus.LIMIT_REACHED` (aditivo) y `TurnResult.error` con una descripción corta en inglés (sin el valor de ningún dato del usuario).

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04a-historias-fundacion.md` (HU-01-06). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

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

### Vocabulario (decisiones por defecto, ver *Clarifications*)

- **Turno (a efectos del límite)**: una vuelta del bucle, es decir, **una llamada al modelo**. No es una tarea del usuario (`run_turn`): una tarea con herramientas gasta varios turnos. Es lo que protege de un bucle sin salida.
- **Sesión**: la vida de un `AgentLoop`. La raíz de composición crea un bucle por sesión, así que los contadores viven en el bucle y se acumulan entre las tareas de la misma sesión.
- **Consumo**: suma de `TokenUsage.total_tokens` de las respuestas del proveedor de la sesión. `limits.max_tokens` es el presupuesto de **toda la ejecución**; nunca es el tope de una llamada (ese es `limits.max_output_tokens`, HU-07-02).
- **Tiempo**: tiempo transcurrido **dentro** de las tareas de la sesión (suma de lo que dura cada `run_turn`), medido con un reloj monótono inyectado. La espera del usuario entre una tarea y otra no cuenta.

### User Story 1 - Un bucle sin salida se detiene por turnos (Priority: P1)

Como usuario operador, quiero fijar un máximo de turnos de modelo por sesión, para que un agente que no deja de pedir herramientas no gaste mi cuota.

**Why this priority**: AC-01; es el límite que corta el caso peligroso (bucle infinito) aunque los otros dos no estén configurados con precisión.

**Independent Test**: Con un proveedor guionado que siempre pide una herramienta y `max_turns=3`, el bucle llama al modelo exactamente 3 veces, publica un `LIMIT_REACHED` que identifica el límite de turnos y devuelve un resultado `LIMIT_REACHED`; no hay una cuarta llamada.

**Acceptance Scenarios**:

1. **Given** `max_turns=N`, **When** el bucle ya hizo N llamadas al modelo y va a hacer otra, **Then** no llama, publica `LIMIT_REACHED` con `limit="turns"` y devuelve `TurnStatus.LIMIT_REACHED`.
2. **Given** `max_turns=N` y un proveedor que responde sin herramientas en la llamada k < N, **When** corre la tarea, **Then** termina `COMPLETED` y no se publica `LIMIT_REACHED`.
3. **Given** el límite ya alcanzado en una tarea anterior de la misma sesión, **When** el usuario envía otra tarea, **Then** el bucle sigue sin llamar al modelo (falla cerrada) y vuelve a explicar el motivo.

---

### User Story 2 - El consumo de tokens corta antes de la siguiente llamada (Priority: P1)

Como usuario operador, quiero un presupuesto de tokens para toda la sesión, para no gastar más cuota de la que decidí.

**Why this priority**: AC-02 y regla 1/2 de la historia.

**Independent Test**: Con respuestas que informan `TokenUsage` y `max_tokens=100`, tras una respuesta que lleva el acumulado a 100 o más el bucle no hace la llamada siguiente y publica `LIMIT_REACHED` con `limit="tokens"`.

**Acceptance Scenarios**:

1. **Given** `max_tokens=M` y un acumulado ≥ M, **When** el bucle va a llamar, **Then** no llama, publica `LIMIT_REACHED` con `limit="tokens"` y el historial conserva la respuesta que superó el presupuesto (ya recibida; no se descarta).
2. **Given** una respuesta sin `usage` (`None`), **When** se acumula, **Then** cuenta 0 (no hay dato) y el bucle no falla.
3. **Given** un acumulado < M, **When** el bucle va a llamar, **Then** llama (el límite se comprueba *antes*, no después; una sola llamada puede rebasar M y eso se acepta y se documenta).

---

### User Story 3 - El tiempo máximo de ejecución (Priority: P2)

Como usuario operador, quiero un máximo de segundos por sesión, para que un agente lento o colgado en un bucle no me ocupe la terminal indefinidamente.

**Independent Test**: Con un reloj inyectado que avanza, tras superar `max_seconds` el bucle no hace la llamada siguiente y publica `LIMIT_REACHED` con `limit="time"`.

**Acceptance Scenarios**:

1. **Given** `max_seconds=S` y un tiempo de ejecución ≥ S, **When** el bucle va a llamar, **Then** no llama y publica `LIMIT_REACHED` con `limit="time"`.
2. **Given** dos tareas separadas por una pausa del usuario, **When** se mide el tiempo, **Then** la pausa no se cuenta.
3. **Given** una llamada al modelo o a una herramienta en curso, **When** se cumple el tiempo, **Then** no se interrumpe (la comprobación es previa a la llamada); la cancelación sigue siendo cosa de HU-01-02/D-01.

---

### User Story 4 - El usuario entiende por qué se detuvo (Priority: P1)

Como usuario operador, quiero leer en la terminal qué límite se alcanzó y cuál era su valor, para saber qué ajustar y recuperar el control.

**Independent Test**: Publicar un `LIMIT_REACHED` con `limit="turns"`, `maximum=3` en la CLI muestra una línea en español con el motivo («turnos», 3) y la sugerencia de ajustar `[limits]` en la configuración; nunca muestra el payload crudo.

**Acceptance Scenarios**:

1. **Given** `LIMIT_REACHED` con cada uno de los tres límites, **When** la CLI lo muestra, **Then** nombra el límite y su máximo y devuelve el control (el indicador de entrada vuelve).
2. **Given** una carga desconocida o incompleta, **When** se muestra, **Then** usa el texto genérico actual (no inventa campos).

---

### User Story 5 - Los límites se configuran y se conectan (Priority: P1)

Como usuario operador, quiero fijar los límites en `[limits]` de `config.toml` (`max_turns`, `max_seconds`, `max_tokens`) y que el arranque real los aplique.

**Independent Test**: `compose(config)` con `max_turns=2` entrega un bucle que se detiene a la segunda llamada; con los valores por defecto (30, 600, 200000) están activos.

**Acceptance Scenarios**:

1. **Given** `config.limits`, **When** `compose()` arma el bucle, **Then** mapea `config.Limits` al `core.Limits` del núcleo (el núcleo no importa `config`).
2. **Given** un límite no positivo o no entero entregado directamente al núcleo, **When** se construye, **Then** falla cerrado con un error en español sin reproducir el valor (la configuración ya los rechaza antes).

### Edge Cases

- Varios límites cumplidos a la vez: se informa **uno** (orden fijo: turnos, tiempo, consumo) para que el evento y el mensaje sean deterministas.
- La tarea del usuario se añade al historial y se publica `USER_MESSAGE` antes de la comprobación (la tarea queda registrada aunque no se pueda atender); en la parada no se añade ningún mensaje del asistente.
- Una respuesta ya recibida cuyo `usage` supera el presupuesto se conserva en el historial; si pedía herramientas, **se ejecutan** (ya fueron autorizadas por la política) y el límite se aplica en la siguiente vuelta, antes de la siguiente llamada. El historial queda estructuralmente válido (sin llamadas sin resultado).
- `usage` con valores negativos o no numéricos del proveedor: se tratan como 0 (falla cerrada hacia «no se sabe»; no se infla ni se resta el consumo).
- Fallo del bus al publicar `LIMIT_REACHED`: se propaga como cualquier otro `emit` (Q4 de HU-01-01).
- Cancelación durante la espera de la llamada: igual que hoy (`INTERRUPTED`); el contador de tiempo suma lo transcurrido aun si la tarea se cancela.
- Un `AgentLoop` construido sin límites (código antiguo y pruebas existentes) no aplica ninguno; la raíz de composición **siempre** los entrega (falla cerrada en el arranque real).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El núcleo MUST definir los límites de una sesión (`core/limits.py`): turnos, segundos y tokens, enteros positivos, inmutables, validados al construirse con un error en español que no reproduce el valor.
- **FR-002**: `AgentLoop` MUST aceptar los límites por constructor (opcional; sin ellos no aplica ninguno) y un reloj inyectable.
- **FR-003**: Antes de **cada** llamada al modelo el bucle MUST comprobar, en este orden, turnos, tiempo y consumo; si alguno se cumple (`>=`), MUST NOT llamar al proveedor.
- **FR-004**: Al detenerse el bucle MUST publicar exactamente un `LIMIT_REACHED` con carga `{"limit": "turns"|"time"|"tokens", "used": n, "maximum": m}` (solo enteros y el nombre del límite; sin contenido ni argumentos) y devolver `TurnResult` con estado `LIMIT_REACHED`, `final_response=None`, el historial y una descripción corta en `error`.
- **FR-005**: El contador de turnos MUST contar las llamadas al modelo hechas por la sesión; el de consumo MUST sumar `usage.total_tokens` de las respuestas (sin `usage` o inválido = 0); el de tiempo MUST sumar la duración de las tareas con un reloj monótono.
- **FR-006**: Los contadores MUST vivir en el bucle (una sesión) y acumularse entre tareas; una tarea posterior a la parada MUST volver a detenerse sin llamar.
- **FR-007**: La CLI MUST mostrar `LIMIT_REACHED` con el límite alcanzado y su máximo en español, sin volcar la carga cruda, y devolver el control al usuario; con carga no reconocida usa el texto genérico actual.
- **FR-008**: `bootstrap.compose()` MUST mapear `config.Limits` (`max_turns`, `max_seconds`, `max_tokens`) a los límites del núcleo y entregarlos al bucle. `max_output_tokens` y `max_tool_output_chars` no son parte de estos límites y no se usan como tales.
- **FR-009**: El costo en dinero MUST NOT ser un límite (solo informativo): esta historia no lo implementa.
- **FR-010**: Esta historia MUST NOT cambiar `core/events.py` ni `core/interfaces/`; el cambio en `core/loop.py` MUST ser mínimo y aislado (un estado nuevo en `TurnStatus`, un parámetro de constructor y una comprobación al inicio de la vuelta).

### Key Entities

- **`Limits`** (`core/limits.py`): máximos de la sesión (`max_turns`, `max_seconds`, `max_tokens`).
- **`LimitKind`** (`core/limits.py`): `turns`, `time`, `tokens`.
- **`LimitTracker`** (`core/limits.py`): cuenta turnos, consumo y tiempo, y responde cuál límite se cumple (`reached() -> LimitReached | None`); lógica pura, sin E/S.
- **`TurnStatus.LIMIT_REACHED`** (`core/loop.py`): nuevo estado terminal de una tarea.

## Success Criteria *(mandatory)*

- **SC-001**: Un bucle que siempre pide herramientas se detiene tras exactamente N llamadas al modelo con `max_turns=N` (0 llamadas extra), en el 100 % de las pruebas.
- **SC-002**: Con un presupuesto de tokens, ninguna llamada al modelo se inicia cuando el consumo acumulado ya alcanzó el presupuesto.
- **SC-003**: Ante cualquiera de los tres límites, el usuario ve en una línea qué límite fue y cuál era su valor, y puede escribir otra tarea.
- **SC-004**: El arranque real (`compose`) aplica los valores de `[limits]`; con los valores por defecto el agente nunca excede 30 llamadas al modelo por sesión.
- **SC-005**: Cobertura de líneas y ramas del módulo nuevo `core/limits.py` del 100 %; las cuatro puertas de calidad y `pytest tests/architecture` en exit 0.

## Assumptions

- Turno = llamada al modelo; sesión = vida del `AgentLoop`; tiempo = suma de lo que duran las tareas (ver *Vocabulario*). **Supuestos pendientes de confirmar con el PO** (la ficha no los define).
- Los valores por defecto (30, 600, 200000) ya existen en `config.Limits` (HU-00-04) y no cambian.
- Un límite alcanzado no se puede «continuar»: el usuario inicia otra sesión (reanudar es HU-03-04) o sube el límite en la configuración.
- La comprobación no interrumpe una llamada en curso: el consumo y el tiempo pueden rebasar el máximo en una llamada.

## Dependencies

- HU-01-01 (bucle) — integrada. HU-05-03 (aprobación) ya está en `main`: la parte de `core/loop.py` que toca (`_ask_approval`, `_decide`) no se modifica aquí.
- Coordinar con A (dueño de `core/loop.py`) y con B (dueño de `config.py`: sin cambios) antes de ratificar.
