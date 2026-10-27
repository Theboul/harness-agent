# Tasks: HU-05-04 — Rechazo con motivo que vuelve al modelo

**Input**: `specs/028-approval-rejection-reason/` (spec.md con Clarifications, plan.md, research.md R1–R11, data-model.md, contracts/rejection_message_contract.md, quickstart.md)
**Rama**: `gustavo` (sin commit, push ni cambio de rama por parte de Claude)
**Responsable**: A — Núcleo | **PHU**: 1 | **Sprint**: 2
**Tareas de referencia**: Sp2-32, Sp2-33

## Cómo leer este documento

- **Regla RITMO**: 1 PHU → 5 tareas de implementación de ≤ 40 min (T002–T006), agrupadas por módulo. Aparte van solo el inicio (T001), el cierre (T007) y las humanas (H1–H5). Como la historia tiene menos de 3 PHU, no hay `/speckit-analyze`.
- **TDD dentro de cada tarea**:
  1. escribir las pruebas;
  2. ejecutarlas y ver el **rojo por la razón esperada** (anotarlo en la evidencia);
  3. implementar lo mínimo;
  4. pasar `ruff format --check .`, `ruff check .`, `mypy src tests` y las pruebas del módulo con cobertura.
- **Formato**: `- [ ] Tnnn [P?] [USn?] descripción con ruta`.
  - US1: el modelo recibe el motivo y replantea.
  - US2: el motivo no sirve para inyectar instrucciones ni filtrar datos.
  - US3: lo denegado y lo protegido no cambian.
  - US4: la terminal pide el motivo.
- **Decisión R3 (aprobada)**: dentro del motivo, tanto `'` como `"` se sustituyen por `’` (U+2019); el motivo va entre comillas simples.
- **Lo que no se toca** (diff vacío al cerrar): `src/harness_agent/core/interfaces/`, `core/events.py`, `core/in_memory_event_bus.py`, `core/permissions/{policy,protected,exact_calls,rules,command_parser,command_rules,command_policy,git_rules,git_table}.py`, `core/redaction.py`, `config.py`, `bootstrap.py`, `tests/doubles/`, `docs/archivo/`. En `core/loop.py` solo cambian el `import`, el cuerpo de la rama de rechazo de `_ask_approval` y su docstring; ni la firma pública del bucle ni los eventos.
- **La única prueba existente que cambia** es `tests/core/test_loop_approval.py::TestRejectedAndFailedClosed::test_a_rejection_does_not_run_the_tool_and_tells_the_model` (la aserción `SENTINEL not in message.content`). **Si necesitas tocar cualquier otra, detente y avisa con la razón antes de hacerlo.**
- **Caracteres ocultos**: en archivos de `specs/` y `docs/` escribe `U+202E` y `U+200B` como texto, nunca el carácter. En código y pruebas construye los caracteres con `chr(0x202E)` y similares, no con secuencias `\u...` en el texto que escribe la herramienta (se convierten en el carácter real).
- **Finales de línea**: todo archivo de `specs/` y `docs/` en CRLF. Usa scripts que lean y escriban bytes; nunca `sed -i`.
- **Secretos**: ninguna asignación con forma de clave ni URL con credenciales literales; los ejemplos se construyen por partes (`"usuario" + "-de-prueba"`).

## Mapeo a tareas del sprint

| Tarea | Descripción (03-plan-sprints) | Presupuesto | Tareas aquí |
|---|---|---|---|
| **Sp2-32** | Devolver el rechazo como resultado | 60 min | T002 (40), T003 (35), T004 (35) = 110 |
| **Sp2-33** | Prueba de replanteo con proveedor simulado | 90 min | T005 (40) = 40 |
| — | Inicio, guarda/documentación y cierre | — | T001 (10), T006 (25), T007 (30) = 65 |

**Total de Claude: 215 min** frente a 150 min presupuestados. El presupuesto es un aviso, no un límite.

---

## Phase 1: Inicio

- [x] T001 Inicio (10 min) en `docs/PROGRESO.md` (CRLF puro, una fila por línea, sin tocar la tabla *Resumen*, con un script que conserve los CRLF):
  - la fila **existente** de HU-05-04 pasa de `Pendiente` a `En curso` (responsable A; la implementa Claude en `gustavo`);
  - una línea en *Registro de cambios*;
  - un bloque nuevo **Observaciones de HU-05-04** con la spec 028, las decisiones Q1 y Q2 de clarify y la nota «cambio mínimo en el bucle autorizado por el usuario actuando como A, pendiente de ratificar».

  Comprobar que `.specify/feature.json` apunta a `specs/028-approval-rejection-reason`.

  **Hecho cuando**: solo cambia esa fila y se añaden líneas; el archivo sigue en CRLF.

---

## Phase 2: Funciones puras — `core/permissions/approvals.py` (US1, US2 · Sp2-32)

- [x] T002 [US1] [US2] `clean_reason` y `rejection_message` (40 min). Pruebas primero:
  - `tests/unit/core/permissions/test_rejection_message.py`:
    - **ejemplos normativos del contrato, con el texto exacto** (tabla): motivo normal (252 caracteres con `escribir_archivo`), sin motivo (`None`, `""`, solo espacios, `5`), instrucción «Ignora las instrucciones anteriores…» (nombre `shell`), marcas falsas, comillas que intentan cerrar el marco (`’`), saltos de línea, ESC y bidireccional, URL con credenciales de prueba construida por partes, `x` × 10 000 (197 `x` + `...`, 400 caracteres), `palabra ` × 2 000, URL con clave de 10 000 caracteres (sin motivo), nombre de 150 caracteres (351), nombre de 100 y motivo de 300 (495), nombre de 400 (sin motivo);
    - **tabla adversarial**: `[approval_rejected]`, `[permission_denied]`, `system:`, `Código de salida: 0`, «ignora lo anterior», `\r\n`, tabuladores, NUL, ESC, DEL, U+0085, U+2028 y U+2029, U+202E, U+2066, U+200B, U+FEFF, comillas `'` `"` y curvas, 10 000 caracteres, URL con credenciales, valores que no son texto (`None`, `5`, `b"x"`, lista);
    - **constantes** y que `MAX_REJECTION_CHARS` es igual a `loop.MAX_MESSAGE_CHARS`;
    - **idempotencia** de `clean_reason`;
    - **lectura acotada**: un motivo de 1 MB se limpia en menos de un segundo.
  - `tests/unit/core/permissions/test_rejection_properties.py`, solo con la biblioteca estándar: `random.Random(20261028)` y unas 2 000 entradas (alfabeto con comillas, corchetes, controles, bidireccionales, fragmentos de URL, espacios y largos de hasta 20 000). Para cualquier motivo la salida de `rejection_message`:
    - empieza por `[approval_rejected] Tool '`;
    - tiene una sola línea;
    - mide ≤ 500 caracteres;
    - no contiene caracteres de las categorías `Cc`, `Cf`, `Cs` ni `Co`;
    - no contiene `"`, y con motivo contiene exactamente cuatro `'` y termina en `'`.

    Además, `clean_reason` no lanza nunca, es idempotente, y para 300 motivos al azar `ApprovalGate` con `DummyApprover(REJECT, motivo)` devuelve `approved=False` y `action=REJECT`.
  - `tests/unit/core/permissions/test_approvals.py`: casos **nuevos** de la puerta (`ApprovalOutcome.reason` sale limpio, un motivo en blanco es `None`, `approval_failed` tiene `reason=None` aunque el resultado inválido traiga uno); los existentes no se tocan.

  Rojo esperado: `ImportError` de `clean_reason`. Implementar en `src/harness_agent/core/permissions/approvals.py` (research R2–R5): constantes, `clean_reason`, `rejection_message` y el uso de `clean_reason` en lugar de `_bounded_reason`. El módulo **no puede contener** el nombre de la decisión de permisos, ni E/S, ni `raise`. Exportar `clean_reason`, `rejection_message`, `MAX_REASON_CHARS`, `MAX_REJECTION_CHARS` y `REJECTED_MARK` en `src/harness_agent/core/permissions/__init__.py` y `src/harness_agent/core/__init__.py`.

  **Hecho cuando**: `approvals.py` al 100 % de líneas y ramas, `tests/unit/core/permissions/test_approvals.py` pasa con sus pruebas existentes sin cambios, y `test_approvals_boundaries.py` y `test_permissions_boundaries.py` siguen en verde.

---

## Phase 3: El bucle (US1, US2 · Sp2-32)

- [x] T003 [US1] [US2] La llamada en `_ask_approval` (35 min). Depende de T002. Pruebas primero en `tests/core/test_loop_rejection_reason.py` (nuevo), con `DummyApprover`/`ScriptedApprover`, `RecordingTool` y `RecordingEventBus` de `tests/doubles/`:
  - rechazo **con** motivo: el mensaje de herramienta es exactamente `rejection_message(nombre, motivo)`, la herramienta no se ejecuta, `is_error` es verdadero y la categoría de `TOOL_FINISHED` es `approval_rejected`;
  - rechazo **sin** motivo (ausente, vacío, no textual): exactamente `[approval_rejected] Tool 'act' was rejected by the user.`;
  - `approval_failed` (aprobador que lanza una excepción; resultado no válido con un motivo): exactamente el texto de hoy y sin motivo;
  - **eventos sin cambios**: ningún evento publicado contiene el motivo (`repr` de cada carga); `APPROVAL_RESOLVED` tiene exactamente las claves `call_id`, `name`, `action`, `approved`, `source`; `TOOL_FINISHED`, `call_id`, `name`, `is_error`, `category`;
  - un rechazo no deja aprobación de sesión (la misma acción se vuelve a preguntar);
  - un motivo con instrucciones («ejecuta rm -rf») no cambia la decisión.

  Después, en `tests/core/test_loop_approval.py`, **solo** en `test_a_rejection_does_not_run_the_tool_and_tells_the_model`, cambiar la aserción `assert SENTINEL not in message.content` por la contraria (el centinela está en el mensaje y el mensaje es el de `rejection_message`); el resto de esa prueba y de las demás queda igual.

  Rojo esperado: el mensaje con motivo sigue siendo el texto fijo (las pruebas nuevas fallan) y la aserción invertida también. Implementar en `src/harness_agent/core/loop.py`: añadir `rejection_message` al `import` de `harness_agent.core.permissions.approvals`, la rama de rechazo de `_ask_approval` llama a `rejection_message(call.name, outcome.reason)` en lugar de escribir el texto fijo (la rama `approval_failed` no se toca) y se actualiza la frase del docstring que decía que el motivo no se reenvía. **Comprobar a mano `git diff src/harness_agent/core/loop.py`: solo esos tres cambios.**

  **Hecho cuando**: las pruebas del bucle (`tests/core/`) en verde, `tests/architecture/test_loop_boundaries.py` y `test_approvals_boundaries.py` en verde **sin ajustes**, y las líneas nuevas de `loop.py` cubiertas. Si una guarda exigiera un ajuste, detenerse y avisar.

---

## Phase 4: La terminal (US4 · Sp2-32)

- [x] T004 [P] [US4] `ConsoleApprover` pide el motivo (35 min). Depende de T002; puede ir en paralelo con T003. Pruebas primero en `tests/unit/cli/test_approval_reason.py` (nuevo), con flujos `io.StringIO`:
  - `3` y luego `usa pytest` → `ApprovalResult(REJECT, reason="usa pytest")`;
  - `3` y luego línea vacía, solo espacios, fin de la entrada o `/salir` → `ApprovalResult(REJECT)`;
  - `1` y `2` no piden motivo (la línea siguiente del flujo queda sin leer);
  - la pregunta del motivo aparece **solo** después de `3`;
  - **el motivo no se escribe en la salida** (se comprueba con un centinela) y el fin de la entrada escribe un salto de línea como hoy;
  - un motivo con caracteres de control pegados se entrega saneado y en una línea; uno de 100 000 caracteres se entrega cortado a 1 000;
  - de punta a punta con `ApprovalGate` real: el `ApprovalOutcome.reason` sale limpio.

  Rojo esperado: el motivo devuelto es siempre `None` (la terminal no lee nada tras `3`). Implementar en `src/harness_agent/cli/approval.py`: `REASON_PROMPT = "motivo (opcional, Enter para omitir)> "` y la lectura tras elegir `3` con la misma lectura (`readline`) y el mismo flujo, con el `sanitize` y `bounded` de la propia CLI (research R8).

  **Hecho cuando**: `tests/unit/cli/test_approval.py` y los demás tests de la CLI pasan **sin cambios**, las líneas nuevas de `cli/approval.py` al 100 % y `tests/architecture/test_cli_boundaries.py` en verde. Si una prueba existente fallara, detenerse y avisar con la razón.

---

## Phase 5: Replanteo, convivencia y persistencia (US1, US2, US3 · Sp2-33)

- [x] T005 [US1] [US2] [US3] Prueba de replanteo y convivencia (40 min). Depende de T003 y T004. Pruebas en `tests/integration/test_rejection_reason_agent_loop.py` (nuevo), con `compose()` real, `FakeProvider` y un shell doble que registra las llamadas y no ejecuta nada (el mismo patrón de `tests/integration/test_command_policy_agent_loop.py`, sin dobles nuevos en `tests/doubles/`):
  - **Sp2-33 con un aprobador de prueba**: el proveedor falso pide una acción, el aprobador la rechaza con motivo, **la petición siguiente que recibe el proveedor contiene el mensaje de herramienta con la marca y el motivo**, el proveedor propone una acción distinta (que se evalúa como cualquier otra) y el doble de la herramienta rechazada recibe 0 llamadas.
  - **Lo mismo con `ConsoleApprover` real** sobre `io.StringIO` (por ejemplo `3` y `usa pytest`).
  - **Convivencia**: una aprobación nunca anula una denegación (comando de la lista base, git destructivo, zona protegida y lista `deny`): el aprobador recibe 0 preguntas y el modelo recibe `[permission_denied]` sin motivo; tras una aprobación de sesión, la misma acción se ejecuta sin preguntar; tras un rechazo con motivo, la misma acción se vuelve a preguntar; `approval_failed` no cambia y nunca lleva motivo.
  - **Eventos**: todos los eventos del bus de `compose()` se recogen y ninguno contiene el motivo; las claves de `APPROVAL_RESOLVED` son las de siempre.
  - **Persistencia (research R6)**: la sesión se guarda en un SQLite de `tmp_path`; tras un rechazo con motivo, ni el contenido de las filas de `events` ni los bytes del archivo de la base de datos contienen el motivo; el esquema no tiene tabla de mensajes (`sqlite_master` solo con `sessions`, `events`, `criterios` y `criterios_sello`); el mensaje con el motivo sí está en el historial en memoria y en la siguiente petición al proveedor.
  - **Motivos hostiles de punta a punta**: instrucciones, controles y bidireccionales, comillas que intentan cerrar el marco y URL con credenciales de prueba (por partes): lo que ve el proveedor es el texto saneado, de ≤ 500 caracteres, con la marca estable primero y una sola línea.

  Rojo esperado: se comprueba retirando temporalmente de `loop.py` la llamada nueva (`git stash` solo de ese archivo, y restaurarlo): la petición siguiente no contiene el motivo. Anotar el número de fallos.

  **Hecho cuando**: todo en verde en Windows; el doble nunca recibe la acción rechazada ni un comando denegado; ningún evento ni archivo contiene el motivo.

---

## Phase 6: Guarda, documentación y cierre

- [x] T006 Guarda de arquitectura y documentación (25 min). Depende de T005.
  - **Guarda nueva** `tests/architecture/test_rejection_reason_boundaries.py`, con autoprueba sobre fragmentos sintéticos y mutación sobre una copia en `tmp_path`:
    - las funciones nuevas de `approvals.py` no hacen E/S, no tienen `raise` y no importan `cli/`, `adapters/`, `config` ni el bucle;
    - `core/loop.py` llama a `rejection_message` solo desde `_ask_approval` y fuera de la rama `approval_failed`;
    - `outcome.reason` solo se menciona dentro de `_ask_approval`; ninguna función de carga de evento del bucle (`_approval_resolved_payload`, `_tool_finished_payload` y las demás) menciona `reason`;
    - `cli/approval.py` no pasa el motivo leído a `put_line`;
    - reutiliza los detectores de las guardas existentes, sin copiarlos.
  - Añadir la guarda a la tabla de `verificar-fronteras-hexagonales/SKILL.md` en `.claude/skills/` y `.agents/skills/` (copias idénticas) y las funciones nuevas a `references/arbol.md` de `estructura-carpetas-harness` (dos copias).
  - En `CLAUDE.md`: actualizar la fila de HU-05-03 («El rechazo con motivo (HU-05-04) sigue pendiente») y añadir una fila de HU-05-04.
  - Revisar contra el código la lista de comprobación de `capas-y-reglas.md` de `plan.md` y anotar cualquier «no».
  - **Detector de secretos** a mano sobre todos los archivos nuevos y modificados, también los no versionados.
  - **Caracteres ocultos y CRLF** en `specs/028-approval-rejection-reason/` y `docs/`: un script que lea los bytes y compruebe que no hay caracteres de categoría `Cf` o `Cc` (salvo `\r`, `\n` y `\t`) y que no hay saltos de línea sueltos.

  Rojo esperado de la guarda: `ModuleNotFoundError`/mutación (la copia con una llamada fuera de `_ask_approval` o con `reason` en una carga de evento la hace fallar).

  **Hecho cuando**: `pytest tests/architecture` en verde con la guarda nueva, las copias de las skills idénticas (`diff -q`), el detector sin hallazgos y sin caracteres ocultos ni saltos de línea sueltos.

- [x] T007 Cierre (30 min). Depende de T006.
  - Ejecutar las cuatro puertas: `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`, todas en exit 0. Anotar los conteos reales, el 100 % de `approvals.py` y de las líneas nuevas de `loop.py` y `cli/approval.py`. También `pytest tests/architecture`.
  - Comprobar `git diff --exit-code $(git merge-base HEAD origin/main) -- <lo que no se toca, de arriba>` → 0, y revisar a mano que el diff de `core/loop.py` solo contiene el `import`, la rama de rechazo de `_ask_approval` y su docstring.
  - Repetir el detector de secretos y la comprobación de caracteres ocultos y CRLF **después** de escribir PROGRESO.
  - En `docs/PROGRESO.md` (CRLF puro, una fila por línea, sin reescribir filas ajenas ni la tabla *Resumen*):
    - la fila de HU-05-04 pasa a **`En revisión`** (nunca `Hecha`), con *Archivos* y *Evidencia* reales;
    - una línea por tarea en *Registro de cambios*;
    - en **Observaciones de HU-05-04**:
      1. el cambio mínimo en `core/loop.py`, **autorizado por el usuario actuando como A y pendiente de ratificar** (H1);
      2. la decisión R3 de las comillas;
      3. la única prueba existente que cambió y por qué;
      4. **dónde puede quedar el motivo**: historial en memoria y proveedor del modelo en cada petición posterior, no en disco; lo que ocurriría si se persiste el historial;
      5. el **coste cuadrático de `hide_url_credentials`** para HU-11-02/HU-10-02, y por qué aquí se acota la lectura a 1 000 caracteres;
      6. `ConsoleApprover` sigue leyendo con `readline` síncrono (bloquea el bucle de eventos, como en HU-05-03) y la línea siguiente al `3` ahora es el motivo;
      7. la advertencia fija, pendiente del PO;
      8. la nota de proceso con los rojos observados;
      9. lo pendiente (H1–H5).
  - Marcar en este archivo solo T001–T007 con su evidencia (tabla al final), con un script que conserve los CRLF; H1–H5 quedan sin marcar.

  **Hecho cuando**: las cuatro puertas en verde, el diff de lo que no se toca vacío, el detector sin hallazgos, sin caracteres ocultos y PROGRESO en CRLF con la fila en `En revisión`.

---

## Phase 7: Tareas humanas (Claude no las marca)

- [ ] H1 **Ratificar el acuerdo** de A, B y C al cambio mínimo en `core/loop.py` (`_ask_approval`), hoy autorizado por el usuario actuando como A.
- [ ] H2 **Visto bueno de C** a los cambios en `core/permissions/approvals.py` y `cli/approval.py`.
- [ ] H3 **Revisión cruzada** por B o C (la historia es de A).
- [ ] H4 El **PO revisa** la advertencia fija que rodea al motivo (research R2) y que el motivo llegue al proveedor del modelo en cada petición posterior (research R6).
- [ ] H5 **CI remota** en verde en `ubuntu-latest` y `windows-latest`, con push y PR confirmados por una persona.

---

## Dependencias y orden

```text
T001 ─▶ T002 ─┬─▶ T003 ─┐
              └─▶ T004 [P] ─┴─▶ T005 ─▶ T006 ─▶ T007 ─▶ (H1–H5)
```

- T003 y T004 tocan archivos distintos (`loop.py` y `cli/approval.py`) y pueden ir en paralelo tras T002.
- **US1 y US2** (el modelo recibe el motivo; saneado y acotado) quedan probadas en T002 y T003 y de punta a punta en T005.
- **US3** (lo denegado y lo protegido no cambian) en T003 y T005.
- **US4** (la terminal pide el motivo) en T004 y T005.

## Ejemplo de paralelismo

```text
Tras T002:
Agente 1: T003   (core/loop.py y su prueba; la aserción que cambia)
Agente 2: T004   (cli/approval.py y su prueba)
```

## Estrategia de implementación

1. **MVP**: T001–T003. El bucle ya entrega el motivo saneado al modelo (probado con un aprobador de prueba).
2. **Incremento**: T004 (la terminal pide el motivo) y T005 (Sp2-33, convivencia y persistencia).
3. **Cierre**: T006 y T007. Después, H1–H5 son humanas y la historia no pasa a `Hecha` hasta completarlas y ratificar HU-00-01.

---

## Evidencia (2026-10-27, Windows 11, Python 3.12, `.venv`)

| Tarea | Rojo observado (razón esperada) | Verde |
|---|---|---|
| T001 | — | `PROGRESO.md` con la fila en `En curso`, bloque de observaciones y registro, en CRLF |
| T002 | Error de importación al recolectar: `cannot import name 'MAX_REASON_CHARS'` | 60 pruebas del módulo; `approvals.py` 100 % de líneas y ramas; mypy y ruff limpios |
| T003 | 4 fallos (3 nuevas y la aserción del centinela) | 6140 pruebas de la suite; diff de `core/loop.py` revisado a mano (import, rama de rechazo, docstring) |
| T004 | 8 fallos y 3 pasan | `cli/approval.py` 100 %; pruebas existentes de `cli/` sin cambios |
| T005 | Sin el cambio de `loop.py` (stash de ese archivo): 9 fallos y 6 pasan | 15 pruebas; `loop.py` restaurado |
| T006 | La guarda falló una vez al contar `verdict.reason`; se afinó el detector | 470 pruebas de arquitectura; skills idénticas; detector de secretos, ocultos y CRLF: 0 problemas en 27 archivos |
| T007 | — | 6176 pasadas y 47 omitidas; ruff format/check y mypy (328 archivos) en exit 0; cobertura total 99 %; diff de lo protegido vacío; fila `En revisión` |

H1–H5 quedan sin marcar: las deciden personas.
