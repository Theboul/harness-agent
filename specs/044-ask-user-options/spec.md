# Especificación: HU-06-02 — Herramienta para preguntar al usuario con opciones (y arreglos de UX)

**Rama**: `claude/hu-06-02-ask-options-c70b31` · **Responsable**: C — Control y conexiones · **Sprint**: 4 (cierre adelantado al 6-nov-2026) · **PHU**: 2  
**Requisitos**: RF-6.1, RF-6.2, RF-6.3 · **Depende de**: [HU-01-02](../../docs/04a-historias-fundacion.md#hu-01-02), [HU-01-05](../../docs/04a-historias-fundacion.md#hu-01-05) · **Ficha**: [HU-06-02](../../docs/04c-historias-control.md#hu-06-02)  
**Reutiliza**: 033-console-ux-commands (`cli/style.py`, `approval_view.py`, vista de actividad) y el menú numerado de 040.

## Resumen

El agente dispone de la herramienta nativa `preguntar_usuario` para pedir una decisión a la persona cuando la tarea es ambigua. La consola muestra la pregunta con opciones numeradas; la persona elige un número o (si se permite) escribe una respuesta; la respuesta vuelve al bucle como resultado de herramienta. Además se corrigen tres detalles de la consola (ver «Arreglos de UX»).

## Clarificaciones

### Sesión 2026-10-31

Sin preguntas al PO: los criterios son explícitos y las decisiones de diseño se fijan aquí.

- Q: ¿La respuesta libre es siempre aceptada? → A: la regla de negocio 1 de la ficha dice que **siempre** se acepta; por eso `permitir_texto_libre` vale `true` por defecto. El modelo puede pasar `false` para una pregunta cerrada (restricción que no contradice la ficha: ofrece menos, nunca elige por la persona).
- Q: ¿Qué se devuelve al elegir? → A: la opción elegida (número y texto) o el texto libre limpio; nunca la lista completa.
- Q: ¿Pide aprobación? → A: no. Es riesgo `LOW`, preguntar no ejecuta nada. La política por defecto la deja en «preguntar» salvo que `ExactCallPolicy`/reglas la permitan; ver FR-007 (la herramienta se declara permitida por nombre en la composición).
- Q: ¿Se marca el resultado como no externo? → A: el bucle (`core/loop.py`, protegido) marca `is_external=True` en **todo** resultado de herramienta ejecutada. No se puede cambiar aquí; queda como **hallazgo para A** (la respuesta es texto de la persona pero viaja marcada como dato externo, lo que es conservador y seguro).
- Q: ¿Sin respuesta? → A: fin de entrada, `/salir` o `max_attempts` entradas inválidas = resultado de error `[sin_respuesta]`. Nunca se elige una opción por defecto.

## Escenarios

1. **Tres opciones, la persona elige 2** (AC-01): el resultado contiene la opción 2 y su texto.
2. **Texto libre** (AC-02): con texto libre permitido, escribir «otra cosa» se acepta y vuelve limpio.
3. **Texto libre no permitido**: escribir texto no es una opción válida; tras `max_attempts` intentos, `[sin_respuesta]`.
4. **Fin de entrada / `/salir`**: `[sin_respuesta]`, sin opción por defecto.
5. **Número fuera de rango (0, 4 con 3 opciones)**: inválido y se vuelve a preguntar.
6. **Argumentos inválidos** (menos de 2 opciones, más de 8, pregunta vacía, opciones repetidas o vacías): los rechaza el validador del registro con `[invalid_arguments]`; la herramienta no pregunta.
7. **Texto libre largo, con saltos de línea, comillas o credenciales de URL**: se limpia como `clean_reason` (una línea, ≤ 200 caracteres, sin control, comillas sustituidas, credenciales ocultas).
8. **La función `ask` falla (excepción)**: `[sin_respuesta]`, el bucle sigue; `CancelledError` se propaga.
9. **Datos del modelo en pantalla**: pregunta y opciones se limpian de caracteres de control; los saltos de línea se escapan; todo acotado.

## Requisitos funcionales

- **FR-001**: Existe `AskUserTool(ask)` en `adapters/tools/ask_user.py`, nombre `preguntar_usuario`, `RiskLevel.LOW`, argumentos `{pregunta: str 1..300, opciones: list[str 2..8, cada una 1..120], permitir_texto_libre?: bool}`.
- **FR-002**: `ask` es un invocable asíncrono inyectado por constructor, con tipos definidos en el propio adaptador (`Question`, `Answer`, `AskFn`). No hay puerto nuevo en `core/`.
- **FR-003**: Elegir una opción devuelve `Respuesta de la persona: opción N: «texto»`; el texto libre devuelve `Respuesta de la persona (texto libre): …` limpio con `clean_reason`.
- **FR-004**: Falla cerrado: `None` de `ask`, excepción de `ask` (no `CancelledError`) o respuesta no válida → `ToolResult(is_error=True)` con etiqueta `[sin_respuesta]`; nunca una opción por defecto.
- **FR-005**: `ConsoleQuestioner` (`cli/question.py`) muestra la pregunta (`cli/question_view.py`, puro) con opciones numeradas `[1] …`, lee número o texto libre, rechaza lo inválido sin repetir el texto, y termina sin respuesta con fin de entrada, `/salir` o `max_attempts` inválidos.
- **FR-006**: Solo `bootstrap.py` construye `ConsoleQuestioner` y la conecta a `AskUserTool`; `compose(…, ask=)` registra la herramienta solo si recibe `ask` (sin `ask`, el registro es el de antes); `main()` inyecta la consola.
- **FR-007**: La herramienta no pide aprobación: `compose()` la añade a la lista de permitidas por nombre dentro de la cadena de políticas sin tocar las reglas existentes (ver plan).
- **FR-008**: No cambian `core/interfaces/`, `core/events.py`, `core/loop.py` ni `tests/doubles/`.
- **FR-009**: Ni la pregunta ni la respuesta aparecen en eventos (la carga de `tool_requested`/`tool_finished` no lleva argumentos ni contenido).

## Arreglos de UX (acotados)

- **UX-a — Ruido de LiteLLM**: el adaptador silencia el aviso «Give Feedback / Get Help» y «LiteLLM.Info: …turn_on_debug()» al cargar LiteLLM (`suppress_debug_info = True` y logger de LiteLLM en nivel `CRITICAL`+sin propagar), sin cambiar el mapeo de errores ni los reintentos.
- **UX-b — Efecto completo y en español**: el bloque de aprobación muestra la descripción de la herramienta completa con ajuste de línea (sin «…» salvo el tope de seguridad de 1 000 caracteres), y para las herramientas nativas el texto visible es una traducción fija en español (`cli/approval_view.py`); lo que ve el modelo no cambia.
- **UX-c — Reintentos**: `provider_error` con `reason: "retry"` se muestra como `[~] Reintentando (n de N) en X s…` (`cli/render.py`), usando solo `attempt`, `max_attempts` y `delay_seconds`; si algún campo falta o no es válido, se muestra «Reintentando…» sin inventar números.

## Fuera de alcance

Subagentes, preguntas con varias secciones o selección múltiple, historial de preguntas, cambios en el evento o el bucle.

## Criterios de éxito

- **SC-001**: AC-01 y AC-02 de la ficha pasan con el bucle real y la consola con entrada simulada.
- **SC-002**: Las cuatro puertas de calidad y `pytest tests/architecture` en exit 0.
- **SC-003**: Diff de archivos protegidos vacío.
