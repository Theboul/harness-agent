# Feature Specification: HU-02-01 — Estimación de tokens y prefijo estable

**Feature Branch**: `feat/hu-02-01-token-estimation-stable-prefix` (el directorio de la spec es `023-token-estimation-stable-prefix`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-25

**Status**: Borrador (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 2 | **Responsable**: B — Estado | **Tareas de referencia**: Sp2-09, Sp2-10, Sp2-11 | **Requisitos**: RF-2.1, RF-2.2, RNF-4 | **Depende de**: HU-01-01 (bucle, integrada)

**Input**: User description: "HU-02-01 — Estimación de tokens y prefijo estable (docs/04b-historias-estado.md#hu-02-01). Estimar los tokens del contexto con una heurística y corregirla con el consumo que informa el proveedor; ensamblar un prefijo estable primero (instrucciones, reglas, descripción de herramientas, sistema operativo e intérprete) y el contenido variable después; pruebas de estabilidad del prefijo. Fuera de alcance: compactación (HU-02-03), bloque de contexto esencial persistente (HU-02-06.1), archivo de instrucciones del proyecto (HU-02-07), memoria, cambios a puertos de `core/interfaces/`, a `core/events.py` y a `core/loop.py`."

## Clarifications

### Session 2026-10-25

Decisiones por defecto del análisis previo. `/speckit-clarify` (2026-10-25) no halló ambigüedades críticas: ninguna cambia puertos, datos persistentes ni los AC; los valores numéricos (4 caracteres por token, factor acotado a [0,25 ; 4,0]) son ajustables sin tocar contratos.

- Q: ¿Se implementa el puerto `ContextManager` completo? → A: **No.** `ContextManager.assemble(session_id, model_id)` no recibe el historial y hoy no hay almacén de sesión integrado ni resumen ni memoria. Esta historia entrega las piezas puras del núcleo (estimador y ensamblador del prefijo) que el `ContextManager` de HU-02-03 y HU-02-06.1 compondrá. El puerto no cambia.
- Q: ¿Dónde va el prefijo, en mensajes o en las definiciones de herramientas? → A: Las definiciones de herramientas viajan por el argumento `tools` de `Provider.complete`; las instrucciones, reglas y entorno van en **un mensaje `SYSTEM`** al inicio. El prefijo estable es el par (mensaje de sistema, definiciones ordenadas por nombre) y se congela por sesión.
- Q: ¿Cómo se corrige la estimación? → A: Con un **factor de calibración por sesión** = tokens de entrada informados / estimación cruda de lo que se envió, acotado a un rango razonable. Sin informe (proveedor sin uso) no cambia.
- Q: ¿De dónde salen el sistema operativo y el intérprete? → A: Los recibe por constructor la raíz de composición (el núcleo no lee el entorno). `Shell.interpreter_name` ya existe en el puerto.
- Q: ¿Cómo entra en el bucle? → A: `core/loop.py` es protegido (dueño A). Esta historia **no lo cambia**: deja el punto de integración documentado como hallazgo.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados de `docs/04b-historias-estado.md` (HU-02-01). No se reescriben ni se amplían (Principio V).

**Flujo general**

1. Antes de llamar, el ContextManager ensambla el contexto.
2. Estima los tokens con una heurística.
3. Tras la respuesta, corrige la estimación con el consumo real informado por la API.
4. Mantiene idéntico el prefijo entre turnos.

**Reglas de negocio**

1. La estimación es heurística y se corrige con el uso real.
2. El prefijo (instrucciones y definiciones de herramientas) no cambia dentro de la sesión.

**Criterios de aceptación**

- **AC-01 — Prefijo estable entre turnos.** Dado el historial, cuando se ensambla el contexto, entonces el prefijo con instrucciones y definiciones es idéntico entre turnos de la misma sesión.
- **AC-02 — Corrección con el consumo real.** Dado un turno terminado, cuando el proveedor informa su consumo real, entonces la estimación se corrige con ese valor.

### Lo que ya existe y lo que cambia

- **Existe y no se toca**: puertos de `core/interfaces/` (incluido `ContextManager`), `core/events.py`, `core/loop.py`, `tests/doubles/`, `cli/`.
- **Se añade**: estimador de tokens con calibración, descripción del prefijo estable, ensamblador por sesión (prefijo congelado + contenido variable) y sus pruebas, todo en `core/`.

### User Story 1 - El prefijo no cambia entre turnos (Priority: P1)

Como equipo de desarrollo, quiero que las instrucciones, reglas, herramientas y datos del entorno se envíen siempre idénticos al inicio, para aprovechar la caché del proveedor.

**Why this priority**: Es AC-01 y la regla 2.

**Independent Test**: Ensamblar la misma sesión en varios turnos con historial creciente y comprobar que el mensaje de sistema y las definiciones son iguales byte a byte; cambiar la fuente de definiciones a mitad de sesión y comprobar que el prefijo no cambia; otra sesión recibe el suyo.

**Acceptance Scenarios**:

1. **Given** una sesión con historial que crece, **When** se ensambla en tres turnos, **Then** el prefijo (texto y definiciones) es idéntico y el historial va después, intacto y en orden.
2. **Given** una sesión con prefijo ya fijado, **When** cambian las herramientas disponibles o el orden en que se registraron, **Then** el prefijo de esa sesión no cambia; una sesión nueva sí toma lo vigente.
3. **Given** las mismas herramientas registradas en distinto orden, **When** se construye el prefijo, **Then** el resultado es idéntico (orden determinista por nombre).

### User Story 2 - Estimar antes de llamar (Priority: P1)

Como equipo de desarrollo, quiero una estimación de los tokens del contexto antes de cada llamada, para decidir cuándo compactar.

**Why this priority**: Es el flujo 2 de la ficha; HU-02-03 la consume.

**Independent Test**: Estimar textos conocidos y comprobar la regla de la heurística y que el total del contexto suma prefijo, definiciones y mensajes.

**Acceptance Scenarios**:

1. **Given** un contexto ensamblado, **When** se estima, **Then** el total incluye el mensaje de sistema, las definiciones de herramientas y todos los mensajes (contenido, llamadas con argumentos y resultados).
2. **Given** un contexto sin historial, **When** se estima, **Then** el resultado es el del prefijo y es mayor que cero.

### User Story 3 - Corregir con el consumo real (Priority: P1)

Como equipo de desarrollo, quiero que la estimación se acerque al consumo real tras cada respuesta del proveedor.

**Why this priority**: Es AC-02 y la regla 1.

**Independent Test**: Registrar un consumo conocido para un contexto estimado y comprobar que la siguiente estimación del mismo tamaño coincide con el consumo; sin informe, no cambia.

**Acceptance Scenarios**:

1. **Given** un turno terminado con consumo informado, **When** se registra, **Then** la estimación posterior del mismo contenido coincide con ese valor (dentro del redondeo).
2. **Given** un proveedor que no informa uso o informa cero, **When** se registra, **Then** la calibración no cambia.
3. **Given** un consumo absurdo (muy por encima o por debajo de lo estimado), **When** se registra, **Then** el factor queda acotado y la estimación sigue siendo finita y positiva.
4. **Given** dos sesiones, **When** una registra consumo, **Then** la otra no cambia.

### Edge Cases

- Sesión sin historial; mensajes con contenido vacío; llamadas con argumentos anidados; herramientas sin parámetros.
- Argumentos de llamadas con claves en distinto orden: la estimación y la huella son deterministas.
- Identificador de sesión vacío o instrucciones vacías: se rechazan con mensaje fijo en español.
- Herramientas con el mismo nombre duplicado o vacío, o con parámetros que no se pueden serializar: se rechaza (falla cerrada).
- El ensamblador no modifica el historial recibido ni devuelve alias de él.

## Requirements *(mandatory)*

### Functional Requirements

**Estimación (Sp2-09)**

- **FR-001**: Existe un estimador puro que da un número entero de tokens para un texto con la heurística `ceil(caracteres / 4)` (0 para texto vacío), y para un mensaje, una definición de herramienta y una lista de mensajes sumando contenido, nombres y argumentos serializados de forma determinista, más una sobrecarga fija de 4 tokens por mensaje (rol y delimitadores).
- **FR-002**: El estimador guarda un factor de calibración por sesión (inicial 1.0). `observe(session_id, estimated_raw, reported_input_tokens)` lo actualiza como reportado/crudo, acotado a [0,25 ; 4,0]; ignora informes nulos, cero o negativos y estimaciones crudas de cero.
- **FR-003**: La estimación calibrada es `ceil(crudo × factor)`. Una sesión sin calibración usa 1.0.

**Prefijo y ensamblado (Sp2-10)**

- **FR-004**: El prefijo estable se describe con instrucciones, reglas, sistema operativo, intérprete y definiciones de herramientas. Se renderiza en **un** mensaje `SYSTEM` con secciones en orden fijo y las definiciones ordenadas por nombre.
- **FR-005**: El ensamblador, dado `session_id` y el historial, devuelve un contexto con: mensaje de sistema, definiciones, mensajes del historial (copiados, en orden) y la estimación calibrada. El prefijo de cada sesión se calcula **una vez** (primer ensamblado) y se reutiliza.
- **FR-006**: El ensamblador lee las instrucciones, reglas, entorno y las definiciones desde fuentes inyectadas (un valor de configuración del prefijo y un proveedor de definiciones); nunca lee archivos, entorno ni configuración.
- **FR-007**: `record_usage(session_id, usage)` calibra con el consumo de entrada informado, usando la estimación cruda de lo último que se ensambló en esa sesión. Sin ensamblado previo, no hace nada.
- **FR-008**: Cada prefijo expone una huella (SHA-256 del texto y las definiciones serializadas) para comparar en pruebas y para HU-02-06.1.

**Pruebas de estabilidad (Sp2-11)**

- **FR-009**: Hay pruebas de que el prefijo es idéntico entre turnos, ante cambio de fuentes, ante distinto orden de registro, y distinto entre sesiones con distintas fuentes.

**Calidad**

- **FR-010**: `core/` usa solo biblioteca estándar y `harness_agent.core`; lo público nuevo se exporta en `core/__init__.py`; el módulo nuevo trae su guarda en `tests/architecture/`.
- **FR-011**: Sin cambios en `core/interfaces/`, `core/events.py`, `core/loop.py`, `cli/`, `tests/doubles/`, `docs/archivo/`.
- **FR-012**: Pruebas sin red, claves ni consola; 100 % de líneas y ramas del módulo nuevo; mensajes de error en español, sin reproducir valores recibidos.
- **FR-013**: Al cerrar, `docs/PROGRESO.md` refleja la historia (En revisión) y las observaciones: punto de integración en el bucle (A), puerto `ContextManager`, orden con el bloque esencial (HU-02-06.1), umbral por modelo (HU-02-03).

### Key Entities

- **Prefijo estable**: mensaje de sistema + definiciones ordenadas + huella; inmutable y fijo por sesión.
- **Contexto ensamblado**: prefijo + historial + estimación.
- **Calibración**: factor por sesión derivado del consumo informado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En una sesión de 20 turnos simulados, el prefijo es idéntico byte a byte en los 20 ensamblados.
- **SC-002**: Tras registrar un consumo informado, el error de la estimación del mismo contenido es de como máximo 1 token (redondeo).
- **SC-003**: 100 % de líneas y ramas del módulo nuevo; las cuatro puertas de calidad y `pytest tests/architecture` en verde.
- **SC-004**: Ningún archivo protegido modificado (`git diff` vacío sobre ellos).

## Assumptions

- La heurística de 4 caracteres por token es una aproximación para inglés y código; el factor de calibración la ajusta por sesión. No se usa ningún tokenizador de terceros (el núcleo es solo biblioteca estándar).
- El umbral por modelo y la decisión de compactar son de HU-02-03; aquí solo se entrega la estimación.
- Las instrucciones, reglas y los datos de entorno los aporta la raíz de composición; el archivo de instrucciones del proyecto es de HU-02-07.
- La integración con `AgentLoop` (usar el contexto ensamblado y llamar a `record_usage`) requiere cambiar `core/loop.py` y queda para A (ver PROGRESO).
