# Feature Specification: HU-02-02 — Recorte de salidas largas de herramientas

**Feature Branch**: `feat/hu-02-02-tool-output-truncation` (el directorio de la spec es `020-tool-output-truncation`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-25

**Status**: Borrador (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 2 | **Responsable**: C — Control y conexiones | **Tareas de referencia**: Sp2-12, Sp2-13 | **Requisitos**: RF-2.5 | **Depende de**: HU-01-02 (registro de herramientas, integrada)

**Input**: User description: "HU-02-02 — Recorte de salidas largas de herramientas (docs/04b-historias-estado.md#hu-02-02). Recorte general aplicado en el registro de herramientas (core/tools/registry.py), con marca visible de cuánto se omitió, tamaño máximo configurable. Fuera de alcance: HU-02-01, HU-02-03, HU-11-03, HU-01-06, cambios en puertos de core/interfaces ni en core/loop.py. Debe convivir con los acotados propios de HU-01-03 (adapters/tools/_limits.py) y HU-01-04 (adapters/system/shell_output.py) sin duplicarlos ni contradecirlos."

## Clarifications

### Session 2026-10-25

Decisiones por defecto del análisis previo. Confirmadas en `/speckit-clarify` (una pregunta, respondida por el responsable).

- Q: ¿Dónde se aplica el recorte? → A: En el registro de herramientas (`core/tools/registry.py`, tarea Sp2-12). El registro no ejecuta herramientas: el bucle (`core/loop.py`, protegido) obtiene la herramienta con `registry.get(nombre)` y llama a `run`. Por eso el registro guarda, al registrar, la herramienta envuelta en un decorador que recorta el contenido del `ToolResult` que `run` devuelve. No cambian el puerto `Tool`, el puerto `ToolRegistry` ni el bucle. Cualquier herramienta futura (shell, MCP, subagentes) queda cubierta sin tocar su código.
- Q: ¿Qué se recorta y qué no? → A: Solo el texto `content` de un `ToolResult`. `call_id` e `is_error` pasan intactos: un error largo sigue siendo un error. Las etiquetas de error (`[codigo_de_salida=N]`, `[fuera_del_area]`…) están al inicio del texto, y el recorte conserva el principio, así que no se pierden.
- Q: ¿Cómo se recorta? → A: **Principio y final** con una marca en medio, con el mismo criterio y el mismo texto de aviso que ya usa HU-01-04 (`[salida recortada: se omitieron N caracteres]`), para que el modelo vea una sola forma de aviso. El texto resultante nunca supera el máximo (la marca cabe dentro del máximo).
- Q: ¿Qué máximo por defecto? → A: 24 000 caracteres. Las herramientas acotan su *cuerpo* a 20 000 (`MAX_RESULT_CHARS` de HU-01-03 y `MAX_OUTPUT_CHARS` de HU-01-04) y el shell le antepone una cabecera con el código de salida o la etiqueta de error (unas decenas de caracteres): con un máximo general de 20 000 esa salida ya acotada se recortaría una segunda vez y llevaría dos avisos. Con 24 000 hay margen de sobra y una salida ya acotada por su herramienta atraviesa el registro intacta. Los acotados de cada herramienta se **conservan** como defensa en origen (memoria, entradas enormes); el recorte general es la red de seguridad común. Esto resuelve la observación «Menores» de PROGRESO del 2026-10-23 (alinear ambos límites con HU-02-02).
- Q: ¿Cómo se configura el máximo? → A: **Confirmado por el responsable (2026-10-25).** Parámetro opcional de construcción del registro (`InMemoryToolRegistry(max_output_chars=...)`; sin valor, el registro no recorta y se comporta como en HU-01-02, de modo que `get` devuelve la misma instancia registrada) y campo opcional `[limits] max_tool_output_chars` en `config.toml` (por defecto 24 000), que `bootstrap.py` siempre entrega al registro: en el arranque real el recorte general está activo. El campo en `config.py` (dueño B) es aditivo y se declara como desviación, como hizo HU-01-04 con `process_environment()`.
- Q: ¿Se recorta también el texto de los errores del bucle (`[unknown_tool]`, `[invalid_arguments]`…)? → A: No. Esos mensajes ya los acota el bucle a 500 caracteres y no pasan por `Tool.run`.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04b-historias-estado.md` (HU-02-02). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

**Flujo general**

1. Una herramienta devuelve una salida larga.
2. El sistema compara su tamaño con el máximo.
3. Si lo excede, la recorta y añade una marca con la cantidad omitida.
4. El resultado recortado vuelve al contexto.

**Reglas de negocio**

1. El tamaño máximo es configurable.
2. El recorte siempre deja una marca visible.

**Criterios de aceptación**

- **AC-01 — Recorte con marca de omisión.** Dado una salida que supera el tamaño máximo, cuando vuelve al contexto, entonces se recorta e incluye una marca con la cantidad omitida.

### Lo que ya existe y lo que cambia

- **Existe y no se toca**: los puertos `Tool` y `ToolRegistry`, `ToolResult`, el bucle, la política, el bus, la CLI, `tests/doubles/` y los acotados de HU-01-03 y HU-01-04 (siguen como están).
- **Se añade**: la función pura que recorta un texto con marca, el decorador de herramienta que la aplica, su uso en `InMemoryToolRegistry`, el parámetro de máximo del registro, su conexión en `bootstrap.py` y las pruebas.

### User Story 1 - Una salida enorme no llena el contexto (Priority: P1)

Como usuario operador, quiero que la salida de cualquier herramienta que supere el máximo llegue al modelo recortada y con una marca de cuánto se omitió, para que un solo comando no llene el contexto ni le haga creer al modelo que vio todo.

**Why this priority**: Es el criterio AC-01 y la razón de la historia; HU-11-03 (pruebas y lint por shell) depende de ella.

**Independent Test**: Registrar una herramienta que devuelve un texto mucho mayor que el máximo, obtenerla del registro, ejecutarla y comprobar que el contenido no supera el máximo, empieza y termina como el original y contiene la cantidad omitida.

**Acceptance Scenarios**:

1. **Given** una herramienta registrada que devuelve una salida mayor que el máximo, **When** el bucle la obtiene del registro y la ejecuta, **Then** el contenido devuelto no supera el máximo, conserva el principio y el final de la salida original y contiene un aviso con la cantidad exacta de caracteres omitidos.
2. **Given** una salida de exactamente el máximo, **When** vuelve, **Then** llega completa y sin aviso.
3. **Given** una salida menor que el máximo, **When** vuelve, **Then** llega idéntica y sin aviso.
4. **Given** un resultado con error (`is_error=True`) cuya salida es larga, **When** vuelve, **Then** sigue marcado como error, conserva su `call_id` y su etiqueta inicial, y está recortado con aviso.
5. **Given** el bucle real con una herramienta de salida enorme, **When** completa el turno, **Then** el mensaje de herramienta que entra al historial ya está recortado y con aviso.

---

### User Story 2 - El operador fija el máximo (Priority: P2)

Como usuario operador, quiero poder cambiar el tamaño máximo, para ajustarlo al modelo y a la tarea.

**Why this priority**: Es la regla de negocio 1; P2 porque con el valor por defecto la historia ya funciona.

**Independent Test**: Construir registros con máximos distintos y comprobar que el mismo texto se recorta según cada uno; en la configuración, un valor válido llega al registro y uno inválido se rechaza al cargar.

**Acceptance Scenarios**:

1. **Given** un máximo menor o mayor que el de defecto, **When** una herramienta devuelve una salida intermedia, **Then** se recorta o no según ese máximo.
2. **Given** un máximo que no es un entero positivo o que no deja espacio para la marca, **When** se construye el registro, **Then** se rechaza con un mensaje en español que no reproduce el valor recibido.
3. **Given** un `config.toml` sin el campo, **When** se arranca, **Then** rige el máximo por defecto; **Given** el campo con un valor válido, **Then** rige ese.

---

### User Story 3 - Convive con los acotados de cada herramienta (Priority: P2)

Como mantenedor, quiero que el recorte general no duplique ni contradiga los acotados que ya hacen las herramientas de archivos y el shell, para que el modelo vea siempre una sola marca coherente.

**Why this priority**: Evita doble recorte y dos avisos distintos; P2 porque es una garantía de integración, no una capacidad nueva.

**Independent Test**: Pasar por el registro una salida que el shell ya acotó con su aviso y comprobar que llega idéntica; pasar una que supera un máximo del registro más bajo y comprobar que el resultado final no supera ese máximo y que su aviso nuevo es exacto.

**Acceptance Scenarios**:

1. **Given** el peor resultado que producen hoy las herramientas (cuerpo de 20 000 caracteres con aviso propio más su cabecera), **When** vuelve con el máximo por defecto, **Then** llega idéntico, con su aviso original y sin un segundo aviso.
2. **Given** una salida ya acotada que aún supera un máximo del registro más bajo, **When** vuelve, **Then** el resultado final no supera el máximo y lleva el aviso nuevo, cuya cantidad omitida es exacta respecto del texto que el registro recibió.

---

### Edge Cases

- **Salida vacía**: llega vacía y sin aviso.
- **Caracteres no ASCII** (tildes, eñes, emoji): el recorte cuenta y corta en caracteres de Python, nunca produce texto corrupto.
- **Cuenta de omitidos**: es la longitud original menos los caracteres conservados; el aviso la dice con exactitud.
- **Máximo mínimo**: el máximo debe poder contener la marca más algo de contenido; por debajo de ese mínimo el registro se rechaza al construirse.
- **Herramienta que lanza excepción o devuelve algo que no es `ToolResult`**: el decorador no interviene; el bucle sigue normalizando esos casos (`[tool_exception]`, `invalid_tool_result`). El decorador no oculta ni convierte excepciones y deja propagar la cancelación.
- **Resultado de tipo inesperado**: si `run` devuelve algo que no es `ToolResult` con `content` de texto, se entrega tal cual para que el bucle lo rechace como hoy.
- **Identidad de la herramienta**: `get(nombre)` devuelve un objeto con el mismo `name`, `description`, `schema` y `risk` que la herramienta registrada; el catálogo (`list()`) sigue en orden de registro y las definiciones que ve el modelo no cambian.
- **Contenido como dato**: el texto de la salida es dato, no instrucción; el recorte no lo interpreta. Los eventos del bucle siguen sin llevar salida (FR-029 de HU-01-01).
- **Secretos en la salida**: no se redactan aquí (PD-10 sigue abierta).

## Requirements *(mandatory)*

### Functional Requirements

**Recorte (Sp2-12)**

- **FR-001**: Existe una función pura que, dado un texto y un máximo, devuelve el texto sin cambios si no lo supera, y si lo supera devuelve principio + marca + final, nunca más largo que el máximo.
- **FR-002**: La marca MUST ser visible, decir la cantidad exacta de caracteres omitidos y usar el mismo texto que el aviso de HU-01-04: `[salida recortada: se omitieron N caracteres]`.
- **FR-003**: El recorte MUST conservar tanto el principio como el final del texto original, en caracteres.
- **FR-004**: El registro MUST aplicar el recorte a todo `ToolResult` que devuelva `run` de cualquier herramienta registrada, sin que la herramienta lo sepa.
- **FR-005**: El recorte MUST NOT alterar `call_id` ni `is_error`, y MUST NOT tocar un resultado que ya cabe en el máximo (misma instancia, sin copia).
- **FR-006**: Con recorte activo, `get(nombre)` MUST devolver una herramienta con el mismo `name`, `description`, `schema` y `risk` que la registrada; sin recorte, MUST devolver la misma instancia; `list()` mantiene el orden de registro; `validate_args` no cambia.
- **FR-007**: El decorador MUST NOT capturar excepciones ni cancelación de la herramienta y MUST NOT modificar los argumentos que recibe `run`.
- **FR-008**: Los puertos de `core/interfaces/`, `core/events.py` y `core/loop.py` MUST NOT cambiar.

**Configuración**

- **FR-009**: El máximo MUST ser configurable: parámetro opcional de construcción del registro (sin valor, no hay recorte general) y valor de configuración opcional `[limits] max_tool_output_chars` con valor por defecto de 24 000 caracteres, que `bootstrap.py` MUST entregar siempre al registro.
- **FR-010**: Un máximo que no sea un entero positivo (un booleano no cuenta como entero) o que no deje espacio para la marca y contenido útil MUST rechazarse al construir el registro y al cargar la configuración, con mensaje en español sin reproducir el valor.

**Convivencia**

- **FR-011**: Los acotados de `adapters/tools/_limits.py` y de `adapters/system/shell_output.py` MUST NOT eliminarse ni cambiar de comportamiento; la salida ya acotada por una herramienta (cuerpo de 20 000 más su cabecera) cabe en el máximo por defecto y atraviesa sin segundo aviso.
- **FR-012**: La documentación de las constantes `MAX_OUTPUT_CHARS` (shell) y `MAX_RESULT_CHARS` (archivos) MUST dejar de decir «hasta que HU-02-02…» y remitir al recorte general, sin cambiar sus valores.

**Calidad**

- **FR-013**: El código nuevo de `core/` MUST usar solo biblioteca estándar y `harness_agent.core`; lo nuevo y público se exporta desde `core/__init__.py`; el módulo nuevo trae su guarda en `tests/architecture/`.
- **FR-014**: Las pruebas MUST correr sin red, sin claves y sin consola, y el módulo nuevo MUST alcanzar 100 % de líneas y ramas.
- **FR-015**: Al cerrar, `docs/PROGRESO.md` MUST reflejar la historia (estado «En revisión», archivos, evidencia y observaciones para HU-11-03, HU-02-01 y B por el campo de `config.py`) según el Principio VIII.

### Key Entities

- **Salida recortada**: texto con principio, marca y final; su longitud no supera el máximo.
- **Marca de omisión**: aviso con la cantidad de caracteres omitidos.
- **Máximo de salida**: número de caracteres permitido por resultado de herramienta; por defecto 24 000 en la configuración.
- **Herramienta con recorte**: envoltura de una herramienta registrada que delega todo y recorta el resultado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Con una salida diez veces mayor que el máximo, el mensaje que entra al historial del bucle no supera el máximo y contiene la cantidad omitida exacta.
- **SC-002**: En el 100 % de los casos de prueba con salida dentro del máximo, el contenido llega idéntico y sin aviso.
- **SC-003**: El mismo conjunto de pruebas pasa en Windows y en Linux sin pruebas omitidas por plataforma.
- **SC-004**: Las pruebas existentes de HU-01-01, HU-01-02, HU-01-03 y HU-01-04 pasan sin modificar su comportamiento esperado (solo se ajustan si fijaban la identidad exacta del objeto devuelto por `get`, y se documenta).
- **SC-005**: Cobertura del módulo nuevo: 100 % de líneas y ramas.

## Assumptions

- La herramienta se obtiene del registro en cada llamada (`registry.get`), como hace el bucle hoy; no se cachean herramientas fuera del registro.
- El conteo es en caracteres de Python, no en bytes ni en tokens (la estimación de tokens es de HU-02-01).
- 24 000 caracteres es un valor razonable de partida; el PO o el equipo pueden ajustarlo con el campo de configuración.
- El recorte es síncrono y barato: hace una copia del texto, acotado por lo que la herramienta ya devolvió.
- Fuera de alcance: compactación (HU-02-03), ensamblado de contexto (HU-02-01), uso por pruebas y lint (HU-11-03), límites del bucle (HU-01-06), redacción de secretos (PD-10) y cualquier cambio en puertos o en el bucle.
