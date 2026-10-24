# Decisión Técnica D-02: Preservación de metadatos locales en la conversión de mensajes (HU-07-01, D1 y D2)

**Fecha**: 2026-10-18 (versión 4: implementación técnica registrada, ver §0 y §13)  
**Estado**: **PROPUESTA — PENDIENTE DE APROBACIÓN TÉCNICA.** La implementación técnica se ejecutó el 2026-10-18 con la autorización colectiva comunicada por el Product Owner (ver §0); **no** hay aprobación individual de A, B ni C registrada (ver §12).  
**Decisión funcional del Product Owner (D6)**: **APROBADA POR PRODUCT OWNER** el 2026-10-18 (ver §5). Es independiente de la aprobación técnica de este documento, que **sigue pendiente de A, B y C**.  
**Autor**: Integrante A — Núcleo (propuesta para revisión técnica)  
**Trazabilidad**: [HU-07-01](../04d-historias-conexiones.md#hu-07-01) · AC-01 · T018 de [`tasks.md`](../../specs/004-provider-interface-message-format/tasks.md) · [D-01](D-01-asyncio-cancelacion.md) (sin cambios)  
**Restricciones de esta propuesta**: no modifica los criterios de aceptación; no modifica `Message`, `ToolResult`, `Provider`, `ProviderResponse` ni `Provider.complete`. Las secciones 1 a 11 conservan el texto de la propuesta (v3); lo que en ellas figura como «propuesto» o «no ejecutado» está implementado desde la v4 según la sección 0.

---

## 0. Registro de autorización e implementación (2026-10-18)

Esta sección distingue cuatro cosas que no deben confundirse.

| # | Concepto | Estado |
|---|---|---|
| A | **Autorización para implementar** | **Concedida.** El Product Owner comunicó, el 2026-10-18, un **consenso colectivo del equipo** con cinco recomendaciones (envelope, restauración solo por `restore_messages(envelope)`, política de ventanas parciales, deprecación de las funciones sin envelope y manejo del `SYSTEM` vacío). Es un consenso **comunicado por el Product Owner**; **no** son firmas individuales de A, B ni C |
| B | **Aprobación técnica formal de D-02** por A, B y C | **Pendiente.** No existe evidencia individual identificable (revisión de PR, acta o comentario de cada integrante). Las tablas de §12 siguen en «Pendiente» |
| C | **Evidencia de validación** | **Generada** (ver más abajo): suite, tipado, formato, probes y pruebas de los 28 escenarios |
| D | **Cierre de la historia** | **No realizado.** HU-07-01 sigue **En revisión**; T018 sigue sin marcar |

### Qué se implementó

Todo en `src/harness_agent/adapters/converters/`; `core/` no cambia.

| Elemento | Dónde |
|---|---|
| `WireRef`, `MessageMeta`, `ConversionEnvelope`, instantánea JSON estricta, huellas SHA-256, `matches`, verificación de estructura y cobertura | `sidecar.py` |
| `to_openai_envelope` y restauración OpenAI | `openai_converter.py` |
| `to_anthropic_envelope` y restauración Anthropic (`system`, `system_block`, `message`, `message_block`) | `anthropic_converter.py` |
| `restore_messages(envelope)` (única vía de restauración) | `restore.py` |
| Protocolo `EnvelopeConverter` (el `ProviderMessageConverter` existente no cambia) y `to_provider_envelope` en ambos conversores | `base.py`, conversores |
| Política de correlación (`validate_tool_correlation`) y verificación de JSON estricto de argumentos | `_validation.py` |
| T024: `DeprecationWarning` en `from_openai_messages` y `from_anthropic_payload` (comportamiento sin cambios) | conversores |

Las funciones `to_openai_messages`, `to_anthropic_payload`, `to_openai_tools`, `OpenAIConverter.to_provider_payload`, `AnthropicConverter.to_provider_payload`, `from_openai_response`, `from_anthropic_response` y `to_canonical_response` **no cambian de firma ni de comportamiento** (salvo el refactor interno de `to_anthropic_payload`, que produce el mismo resultado y sigue rechazando el `SYSTEM` vacío).

### Resultado por defecto

| Defecto | Resultado |
|---|---|
| D1 `is_external` | Conservado por el envelope en ambos proveedores; nunca viaja en el payload |
| D2 `is_error` (OpenAI) | Conservado por el envelope; el payload de OpenAI no contiene `is_error`; en Anthropic se compara el campo nativo con el del sidecar |
| D8 `Message.usage` | Conservado por el envelope; no se emite en el payload ni se mezcla con el `usage` de una respuesta |
| D9 `Message.content` de un `TOOL` distinto de `ToolResult.content` | Conservado (`tool_message_content`) |

### `SYSTEM` vacío (decisión del Product Owner)

Un `SYSTEM` de contenido vacío es un prefijo válido. Con **OpenAI** viaja tal cual (`{"role":"system","content":""}`). Con **Anthropic** el parámetro `system` no puede representarlo de forma segura, así que la ruta del envelope lo **omite solo del payload externo** y registra en el sidecar una entrada `omitted=True` con su rol, posición, contenido (vacío) y `is_external`; la restauración lo devuelve en su posición original. La función solo-payload `to_anthropic_payload` sigue rechazándolo con `ConversionError` porque omitirlo allí perdería datos sin registro.

Evidencia sobre lo que acepta Anthropic: la consulta de la documentación del SDK oficial (`anthropic-sdk-python`, vía Context7) muestra `system: Union[str, Iterable[TextBlockParam]]` y `TextBlock.text: str` sin restricción de longitud en el tipo; **no documenta** si el servicio acepta una cadena vacía o un bloque de texto vacío en `system`. No se hizo ninguna llamada a la API. La omisión es segura en ambos casos y es la decisión adoptada; el comportamiento del servicio **queda sin verificar**.

### Adaptaciones respecto al diseño de §4 (a revisar por A, B y C)

1. El módulo se llama `sidecar.py` (el diseño decía `envelope.py`). `MessageMeta` usa `wire_digest` (huella de los elementos externos referenciados) en lugar de `content_digest` y añade el campo `omitted`.
2. La construcción del envelope es privada (`ConversionEnvelope._create`, token interno); las funciones públicas son `to_openai_envelope`, `to_anthropic_envelope` y `to_provider_envelope` de cada conversor. Los atributos son de solo lectura.
3. `restore_messages` solo recibe el envelope, así que la huella del payload se verifica contra la instantánea inmutable (detecta errores internos); comparar una **copia externa** del payload solo es posible con `matches`. El escenario 9 («restaurar una copia alterada») se cubre con `matches` y con envelopes fabricados mediante `_create` con contenido alterado (que fallan por huella, rol o identificador).
4. Se añadió una verificación no prevista: los argumentos de `ToolCall` (y todo el payload) deben sobrevivir a un viaje por JSON sin coerción (claves enteras, tuplas); si no, `ConversionError`. Sin ella, OpenAI (que serializa los argumentos como cadena) habría vuelto con listas en lugar de tuplas.
5. Un texto que no se puede codificar en UTF-8 (sustitutos sueltos) produce `ConversionError`, no `UnicodeEncodeError`.
6. `message_block` está implementado y verificado en la restauración, aunque ningún conversor lo emite (agrupar varios resultados en un solo mensaje `user` queda como extensión futura).

### Límites que se mantienen

La huella prueba integridad de contenido, no identidad de conversión; elegir el envelope equivocado no es detectable; no hay protección frente a código malicioso del mismo proceso; `conversion_id` no es un token de seguridad. Un valor `matches` verdadero tampoco prueba procedencia.

### Escenarios de §11 y dónde se prueban

| Escenarios | Prueba |
|---|---|
| 1, 2, 3, 4, 15 | `test_envelope_roundtrip.py` (`test_d1_*`, `test_d2_*`, `test_d8_*`, `test_d9_*`) y barrido combinatorio `test_ac01_generated_sweep_is_lossless` (216 secuencias por proveedor) |
| 5, 22, 23 | `test_envelope_roundtrip.py` (ids duplicados o vacíos, dos resultados, resultado antes de su llamada, huérfano con y sin `partial_window`); `test_envelope_security.py` (huérfano fabricado) |
| 6, 17, 18 | `test_identical_content_keeps_each_conversions_own_metadata`, `test_scenario_18_*` |
| 7, 8, 9, 11, 13, 14 | `test_envelope_security.py`, `test_envelope_types.py` (`matches`) |
| 10, 25 | `test_concurrent_conversions_do_not_contaminate_each_other` (8 conversiones con cesiones de control, ambos proveedores) |
| 12 | `test_scenario_12_restore_requires_an_envelope` |
| 16 | las 253 pruebas previas siguen pasando (las dos `test_pending_d1/d2` se transformaron según T023) |
| 19, 20 | `test_scenario_19_*`, `test_scenario_20_*` |
| 21 | `test_scenario_21_*` y `test_mutating_the_original_payload_after_creation_*` |
| 24, 26 | `test_scenario_24_*`, `test_scenario_26_*` |
| 27 | `test_envelope_security.py` (`test_scenario_27_*`) y `test_canonical_validation.py` |
| 28 | `test_envelope_security.py`: fixtures literales escritas a mano (digests calculados con `hashlib`, sin usar los conversores para construirlas) |

Nota de alcance: D-02 sigue en **PROPUESTA — PENDIENTE DE APROBACIÓN TÉCNICA**. Esta implementación se ejecutó bajo la autorización colectiva comunicada por el Product Owner y puede requerir cambios si A, B o C aprueban con observaciones.

---

## 1. Problema

AC-01 de HU-07-01 dice: «Dado el formato interno, cuando se convierte a la entrada de un proveedor y de vuelta, entonces no se pierde información.» Hoy la ida y vuelta pierde atributos canónicos que los protocolos externos no representan:

- **D1**: `Message.is_external` (marca de contenido no confiable, defensa contra inyección de prompt, decisión V-13).
- **D2**: `ToolResult.is_error` con OpenAI (el mensaje `tool` de OpenAI no tiene ese campo; Anthropic sí lo tiene).
- **D8** y **D9** (hallazgos de la auditoría, mismo remedio): `Message.usage` y `Message.content` de un mensaje `TOOL` cuando difiere de `ToolResult.content`.

Escribir un atributo local en un campo inventado del protocolo queda descartado: el proveedor lo rechazaría o ignoraría, y además se filtrarían metadatos de seguridad a la red.

---

## 2. Evidencia reproducida (auditoría, 2026-10-18)

Script de sondeo con los conversores actuales (`src/harness_agent/adapters/converters/`), Python 3.12.10:

| Caso | Resultado observado |
|---|---|
| `Message(USER, "hi", is_external=True)` → OpenAI → canónico | `is_external=False` |
| Ídem con Anthropic | `is_external=False` |
| `ToolResult(is_error=True)` → OpenAI → canónico | `is_error=False` |
| Ídem con Anthropic | `is_error=True` (conservado de forma nativa) |
| `Message(ASSISTANT, "x", usage=TokenUsage(3, 4))` → cualquiera → canónico | `usage=None` |
| `Message(TOOL, "DIFFERENT", tool_result=ToolResult("c", "real"))` → cualquiera → canónico | `content="real"` |
| `Message(TOOL, "a")` seguido de `Message(USER, "u")` → Anthropic | dos mensajes `user` independientes |

Las pruebas `test_pending_d1_*` y `test_pending_d2_*` de `tests/adapters/test_converters_regressions.py` fijan hoy D1 y D2 como comportamiento conocido.

### Dónde se pierde cada atributo

| Atributo | Operación que lo pierde | Por qué |
|---|---|---|
| `is_external` | **Ida** (`to_openai_messages`, `to_anthropic_payload`): no se emite, a propósito (hay una prueba que exige que no viaje al proveedor). **Vuelta** (`from_openai_messages`, `from_anthropic_payload`): construyen `Message(...)` sin ese argumento y toma el valor por defecto `False` | El protocolo no tiene dónde guardarlo y la vuelta no tiene otra fuente |
| `is_error` (OpenAI) | **Ida** (`to_openai_messages`): el mensaje `tool` solo lleva `tool_call_id` y `content`. **Vuelta** (`from_openai_messages`): lee `raw.get("is_error", False)`, un campo que la ida nunca escribe | Mismo motivo |
| `Message.usage` (**D8**) | Ida: no se emite. Vuelta: nunca se asigna | El uso por mensaje no viaja en ningún protocolo de entrada |
| `Message.content` de un mensaje `TOOL` (**D9**) | Ida: se envía `tool_result.content` y se ignora `Message.content`. Vuelta: ambos quedan iguales | Canónicamente pueden diferir |

**Observación de seguridad sobre la vuelta actual**: `from_openai_messages` lee `is_error` de datos externos. Un payload manipulado puede fijar ese valor. Con el diseño propuesto, la restauración ignora ese campo del payload y solo acepta lo que viene de los metadatos del envelope.

### Hallazgo adicional (D10), corregido fuera de D-02 (T025)

Un `Message` canónico incoherente se convierte **sin error y descartando datos**. Se comprobó con ambos conversores: `Message(USER, "x", tool_calls=(...))`, `Message(USER, "x", tool_result=...)` y `Message(ASSISTANT, "x", tool_result=...)` producían un mensaje externo sin `tool_calls` ni resultado; `Message(TOOL, ..., tool_calls=(...))` descartaba las `tool_calls`. Era una pérdida silenciosa que contradecía la falla cerrada (FR-011). Se registró como **D10** y **se corrigió el 2026-10-18 como T025, fuera de D-02** (no usa envelope ni metadatos): un validador compartido (`validate_canonical_messages`, `adapters/converters/_validation.py`) rechaza con `ConversionError` las combinaciones incoherentes en ambos conversores y en `from_openai_messages`. Evidencia: `tests/adapters/test_canonical_validation.py` y `docs/PROGRESO.md`. No se rechaza un `TOOL` cuyo `Message.content` difiere de `ToolResult.content`: eso es D9 y queda para la solución de este documento.

---

## 3. Alternativas

### 3.1 Mecanismo de preservación

| Criterio | A. Sidecar solo | B. Envelope solo | C. Extender modelos | **B + A (recomendada)** |
|---|---|---|---|---|
| Contratos existentes (HU-00-01) | Intactos | Intactos | **Rompe contratos compartidos congelados** (requiere A, B y C) | Intactos |
| ¿Resuelve D2? | Sí | No por sí sola (no hay dónde guardar) | **No**: `ToolResult.is_error` ya existe; lo que falta es el cable | Sí |
| ¿Resuelve D1? | Sí | No por sí sola | No: `Message.is_external` ya existe | Sí |
| Complejidad | Baja | Baja | Alta (migración, pruebas de contrato, docs) | Media-baja |
| Aislamiento entre proveedores | Cada adaptador define su sidecar | Sí | El modelo mezcla preocupaciones de transporte | El envelope y sus metadatos viven en `adapters/`, no en `core/` |
| Concurrencia asíncrona | Segura si es inmutable y por conversión | Segura | Segura | Segura: sin estado global; valor inmutable por llamada |
| Efecto en HU-07-02 | Mínimo | Mínimo | El adaptador LiteLLM dependería del cambio de modelo | Mínimo: la ruta de producción puede usar solo el payload |

La opción C **no resuelve** D1 ni D2: el problema no es que el modelo carezca del atributo, sino que el protocolo externo no puede transportarlo.

### 3.2 Cómo se vincula el payload con sus metadatos

| Criterio | (1) `restore_messages(envelope)` — **recomendada** | (2) payload y sidecar como argumentos separados, con huella | (3) sidecar ligado por HMAC con clave secreta |
|---|---|---|---|
| Recombinación accidental de un payload con metadatos de otra conversión | **No es posible por la API pública**: el payload sale del mismo envelope | Posible: el llamador elige ambos argumentos; la huella solo detecta contenido distinto | Detectable solo si el payload lleva algo que lo ate al sidecar |
| Dos conversiones con contenido idéntico y `is_external` distinto | Cada envelope restaura **sus** metadatos | **Indistinguibles**: mismo payload, misma huella; intercambiar los sidecars no se detecta | **Indistinguibles** salvo que se incruste un identificador en el payload (campo inventado, prohibido) |
| Complejidad | Baja | Baja | Alta: gestión de claves sin beneficio |
| Protección frente a código del mismo proceso | Ninguna (mismo dominio de confianza) | Ninguna | Ninguna: la clave vive en el mismo proceso |
| Compatibilidad | API nueva y aditiva | Exige un parámetro nuevo en funciones existentes o funciones nuevas con dos argumentos | Ídem a (2), más custodia de clave |

**Conclusión**: se recomienda (1). Un HMAC (3) no resuelve el caso de contenido idéntico y añade una clave que protege contra un atacante que, por estar en el mismo proceso, ya podría leerla. El envelope no pretende demostrar «de qué conversión viene» un payload suelto; garantiza que **no hace falta** esa demostración, porque el payload y los metadatos nunca circulan por separado.

---

## 4. Diseño recomendado: envelope sin argumentos independientes

> Todos los nombres de esta sección son **propuestos**, salvo los marcados como existentes. Todo vive en `src/harness_agent/adapters/converters/`; `core/` no cambia.

### 4.1 Garantías reales (y límites)

1. **Recombinación**: a través de la API pública, el payload y los metadatos de una conversión no se pueden combinar con los de otra. `restore_messages(envelope)` lee ambos del mismo objeto.
2. **Llamador que elige el envelope equivocado**: la biblioteca **no puede detectarlo**. Si dos conversiones tienen contenido idéntico y metadatos distintos (por ejemplo `Message(USER, "Hola", is_external=True)` y `Message(USER, "Hola", is_external=False)`), producen el mismo payload y la misma huella SHA-256. Quien conserve los dos envelopes y pase el equivocado obtiene los mensajes de ese envelope, que son correctos *para ese envelope*. La única referencia para vincular un envelope con una solicitud concreta es su `conversion_id`, que el llamador debe registrar (por ejemplo en la traza de la solicitud) si necesita esa correspondencia.
3. **Código que modifica objetos en memoria**: sin protección. El envelope vive en el mismo proceso y dominio de confianza que quien lo usa; ningún mecanismo de este diseño defiende frente a código que manipule el heap.
4. **Huella (SHA-256)**: prueba únicamente que el *contenido* de un payload coincide con el del envelope. **No identifica una conversión.** Sirve para `envelope.matches(payload)`, que detecta que una copia del payload (por ejemplo la que pasó por una capa de reintentos o de registro) fue alterada o es de contenido distinto. Dos envelopes con el mismo contenido responden `True` ambos: no se puede distinguir cuál originó la copia.
5. **Restauración y confianza**: la restauración nunca rebaja una clasificación `is_external=True` a `False`. Los datos del payload no pueden fijar ni elevar `is_external` ni `is_error` (ver §4.5).

### 4.2 Tipos propuestos

```python
@dataclass(frozen=True)
class WireRef:
    """Referencia a un elemento del payload externo."""
    kind: Literal["system", "system_block", "message", "message_block"]
    message_index: int | None   # posición en payload["messages"] (message, message_block)
    block_index: int | None     # bloque dentro de system (lista) o de content (lista)

@dataclass(frozen=True)
class MessageMeta:
    """Metadatos locales de UN mensaje canónico; solo escalares, enums y tuplas."""
    index: int                        # posición en la lista canónica de entrada
    role: Role
    refs: tuple[WireRef, ...]         # elementos externos a los que corresponde
    content_digest: str               # sha256 del JSON canónico de los elementos referenciados
    is_external: bool
    tool_call_id: str | None          # solo mensajes TOOL
    tool_is_error: bool | None        # solo mensajes TOOL
    tool_message_content: str | None  # D9: Message.content del mensaje TOOL si difiere
    usage: TokenUsage | None          # D8: uso histórico adjunto al mensaje

class ConversionEnvelope:             # no es un dataclass con campos públicos
    provider: str                     # "openai" | "anthropic"
    conversion_id: str                # uuid4: identificador local de trazabilidad, NO es un token de seguridad
    partial_window: bool              # ver §4.7
    payload: dict[str, Any]           # propiedad de solo lectura: copia profunda nueva en cada acceso
    entries: tuple[MessageMeta, ...]  # propiedad de solo lectura
    def matches(self, payload: dict[str, Any]) -> bool: ...
```

El constructor del envelope no forma parte de la API pública: solo lo crea `to_provider_envelope`.

### 4.3 Correspondencia con el payload de Anthropic

La correspondencia **no** es «un mensaje canónico por mensaje externo». Estructura real que produce `to_anthropic_payload` (comprobada en el código):

- Los `SYSTEM` **iniciales** van al parámetro superior `system`: una cadena si hay uno solo, una lista de bloques `{"type": "text", "text": ...}` si hay varios. Un `SYSTEM` posterior a cualquier mensaje no `SYSTEM` es una secuencia canónica **inválida** (decisión del Product Owner, §5) y se rechaza con `ConversionError` antes de convertir; un `SYSTEM` de contenido vacío se sigue rechazando en Anthropic porque el parámetro no puede representarlo (pregunta abierta en §12).
- `USER` → un mensaje `user` con `content` de tipo cadena.
- `ASSISTANT` sin llamadas → mensaje `assistant` con `content` de tipo cadena; con llamadas → `content` es una lista: un bloque `text` (si hay texto) seguido de un bloque `tool_use` por llamada.
- `TOOL` → **un mensaje externo `user`** con un único bloque `tool_result`.

**Modelo de referencias.** Cada `MessageMeta` lista los `WireRef` a los que corresponde:

| `kind` | Apunta a |
|---|---|
| `system` | el parámetro `system` completo (cadena) |
| `system_block` | el bloque `block_index` de la lista `system` |
| `message` | el mensaje completo `messages[message_index]` |
| `message_block` | el bloque `block_index` de `messages[message_index].content` |

El conversor actual solo emite `system`, `system_block` y `message`. `message_block` queda previsto para el caso en que varios mensajes canónicos compartan un mensaje externo (por ejemplo, varios resultados de herramienta agrupados en un solo `user`, forma que Anthropic admite). Si se introdujera esa agrupación, la restauración ya sabría validarla.

**Compatibilidad de roles (no es igualdad literal):**

| Rol canónico | Representación externa admitida | Observaciones |
|---|---|---|
| `SYSTEM` | `system` (cadena) o `system_block` | Solo como prefijo contiguo al inicio de la secuencia (decisión D6) |
| `USER` | mensaje `user` con contenido cadena o bloques `text` | Un `user` que contenga un bloque `tool_result` **no** es un `USER` canónico: ambiguo ⇒ `ConversionError` |
| `ASSISTANT` | mensaje `assistant` con cadena, o `text` + `tool_use` | Los bloques `tool_use` deben coincidir con `ToolCall` del mensaje |
| `TOOL` | mensaje `user` cuyo contenido es un bloque `tool_result` (por `message` o `message_block`) | `tool_use_id` debe ser igual a `tool_call_id`; el rol externo `user` es válido para un `TOOL` canónico |

**Verificaciones de la restauración (cualquier fallo ⇒ `ConversionError`):**

1. Las referencias de cada entrada resuelven a elementos existentes del payload.
2. Las referencias están en orden estrictamente creciente de aparición en el payload (`system` primero, luego `messages` en orden) y las entradas conservan el orden canónico (`index` contiguo `0..n-1`).
3. Cada elemento del payload queda cubierto **exactamente una vez**: sin elementos sin cubrir, sin solapes, sin referencias repetidas.
4. El rol canónico de la entrada es compatible con el rol y los bloques del elemento referenciado, según la tabla anterior.
5. La coincidencia de contenido con `content_digest` (integridad del contenido, no identidad).
6. Los límites originales se conservan: cada bloque `system_block` produce su propio `SYSTEM`; un `message` no se parte ni se une con otro.

**Ejemplo con la estructura real:**

| Canónico | Payload de Anthropic | `refs` |
|---|---|---|
| 0 `SYSTEM "S1"` | `system[0]` = `{"type":"text","text":"S1"}` | `system_block(block=0)` |
| 1 `SYSTEM "S2"` | `system[1]` = `{"type":"text","text":"S2"}` | `system_block(block=1)` |
| 2 `USER "u"` (`is_external=True`) | `messages[0]` = `{"role":"user","content":"u"}` | `message(0)` |
| 3 `ASSISTANT "t"` con `c1` y `c2` | `messages[1]` = `{"role":"assistant","content":[text, tool_use c1, tool_use c2]}` | `message(1)` |
| 4 `TOOL` resultado de `c1` (`is_error=True`) | `messages[2]` = `{"role":"user","content":[{"type":"tool_result","tool_use_id":"c1",...}]}` | `message(2)` |
| 5 `TOOL` resultado de `c2` | `messages[3]` = `{"role":"user","content":[{"type":"tool_result","tool_use_id":"c2",...}]}` | `message(3)` |
| 6 `USER "next"` | `messages[4]` = `{"role":"user","content":"next"}` | `message(4)` |

Seis mensajes externos para siete canónicos: la cantidad no coincide, y la restauración no lo exige.

**OpenAI** es más simple: un mensaje externo por mensaje canónico. Todas las referencias son de tipo `message` y los roles son idénticos (`TOOL` ↔ rol externo `tool`).

### 4.4 Compatibilidad de API

Funciones y clases **reales** hoy (`adapters/converters/`):

| Grupo | Elemento real | Acción propuesta |
|---|---|---|
| **A. Canónico → payload** | `to_openai_messages`, `to_openai_tools`, `to_anthropic_payload`, `OpenAIConverter.to_provider_payload`, `AnthropicConverter.to_provider_payload` | **Sin cambios.** Siguen siendo la ruta de producción (HU-07-02) |
| **B. Restauración exacta** | no existe | **Implementado**: `to_openai_envelope` y `to_anthropic_envelope` (funciones de módulo; el método `to_provider_envelope(messages, tools=None, *, partial_window=False)` de cada conversor del Protocolo `EnvelopeConverter` las expone) y `restore_messages(envelope)` |
| **C. Respuestas nuevas del proveedor** | `from_openai_response`, `from_anthropic_response`, `OpenAIConverter.to_canonical_response`, `AnthropicConverter.to_canonical_response` | **Sin cambios.** Nunca reciben ni consultan un envelope |
| **Interpretación solo del payload** | `from_openai_messages`, `from_anthropic_payload` (exportadas en `__init__.py`) | **Decisión pendiente**, ver abajo |

No existe una función `from_provider_response`. Y la versión 1 de este documento proponía exigir un parámetro `sidecar` en `from_*_messages`, lo que habría roto a cualquier consumidor existente; **esa propuesta se retira**. La restauración exacta es una función nueva, no una variante de las existentes.

El Protocolo `ProviderMessageConverter` (`base.py`) hoy declara `to_provider_payload` y `to_canonical_response`. Añadirle `to_provider_envelope` obligaría a cualquier implementación externa a actualizarse. Se resolvió con un Protocolo adicional, `EnvelopeConverter` (implementado en `base.py`), dejando el existente intacto.

**Consumidores reales de `from_openai_messages` y `from_anthropic_payload`** (búsqueda en el repositorio): solo las pruebas (`tests/adapters/test_converters.py`, `tests/adapters/test_converters_regressions.py`) y las exportaciones de `__init__.py`. No hay código de producción que las use todavía (HU-07-02 no está implementada).

**Problema de seguridad de estas dos funciones**: interpretan payloads de origen desconocido y devuelven `is_external=False`, que significa «confiable». Eso es un valor por defecto abierto.

| Opción | Cambio incompatible | Migración |
|---|---|---|
| 1. Mantener sin cambios y documentar la advertencia | No | Ninguna |
| 2. Marcar como obsoletas (`DeprecationWarning`) apuntando a `restore_messages`, sin cambiar el comportamiento | No (solo avisa) | Los consumidores pasan a `restore_messages(envelope)`; las funciones se retiran en una versión posterior si A, B y C lo aprueban |
| 3. Cambiar el valor por defecto a no confiable (`is_external=True` para `USER` y `TOOL`) | **Sí**: cambia la salida y rompe las pruebas que comparan igualdad con `is_external=False` | Actualizar pruebas y documentación; avisar a B antes de que HU-07-02 las use |

**Recomendación**: opción 2 como paso inmediato (tarea propuesta T024) y evaluar la 3 como decisión aparte de A, B y C. La decisión final es suya.

### 4.5 Reglas de restauración y confianza

1. `is_external`, `is_error`, `usage` y `tool_message_content` salen **únicamente** de los metadatos del envelope, creados por `to_provider_envelope` a partir de mensajes canónicos.
2. En OpenAI, el campo `is_error` de un mensaje `tool` del payload se **ignora** (la restauración lo toma del envelope). En Anthropic, el `is_error` del bloque `tool_result` se **compara** con el del envelope; si difieren ⇒ `ConversionError`.
3. Las respuestas del proveedor (`from_*_response`) no reciben envelope y no pueden alterar la clasificación de confianza.
4. No hay restauración «sin envelope»: no existe una ruta pública que devuelva `is_external=False` por omisión en `restore_messages`.
5. `usage` por mensaje (D8) es el uso histórico adjunto a un mensaje canónico. **No** tiene relación con el `usage` de una respuesta nueva del proveedor, que `from_*_response` lee de la respuesta y nunca fusiona con los metadatos del envelope.

### 4.6 Inmutabilidad y serialización

`@dataclass(frozen=True)` **no** vuelve inmutables los diccionarios o listas anidados: solo impide reasignar atributos. Por eso:

- **Fuente de verdad**: una cadena JSON estricta del payload (`json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)`), creada al construir el envelope. Una cadena es inmutable.
- **`payload`**: propiedad que devuelve una **copia nueva** (`json.loads`) en cada acceso. Modificar la copia, o el diccionario original que se pasó, no altera lo que usa la restauración.
- **Rechazos**: `NaN`, `Infinity` y valores no serializables ⇒ `ConversionError` (los conversores ya lo hacen para los argumentos de herramientas; se extiende al payload completo). Se propone además verificar que `json.loads(snapshot)` es igual al payload original, para detectar coerciones silenciosas de `json` (claves enteras convertidas a cadenas, tuplas convertidas a listas) ⇒ `ConversionError` (a validar al implementar).
- **Orden de claves**: la copia devuelta tiene las claves ordenadas, lo que no cambia el significado de un objeto JSON.
- **`MessageMeta`**: dataclasses con escalares, enums, tuplas y `TokenUsage` (enteros inmutables).

| Alternativa | Valoración |
|---|---|
| Solo `copy.deepcopy` al construir | No da forma canónica ni comprueba JSON estricto; el dict almacenado seguiría siendo mutable si se expone |
| `MappingProxyType` | Inmutabilidad superficial: los objetos anidados siguen siendo mutables |
| **Instantánea JSON + copia por acceso (recomendada)** | Inmutable de verdad, canónica, valida JSON estricto |

**Cuándo se calculan y verifican las huellas**: `payload_digest` y los `content_digest` se calculan **una vez, al construir el envelope**. Se verifican en `restore_messages` (contra la instantánea) y en `matches(payload)` (contra la forma canónica de la copia candidata). Como la instantánea es una cadena inmutable, la verificación dentro de `restore_messages` detecta errores internos, no manipulación externa; el valor real de la huella está en `matches` y en el diagnóstico.

### 4.7 Correlación de herramientas: conversación completa y ventana parcial

La versión 1 exigía que cada resultado de herramienta encontrara su llamada en un mensaje `ASSISTANT` anterior del mismo payload. Eso es correcto para una conversación completa pero **no** para las ventanas que producirán la compactación, el recorte y la reanudación de sesión. Políticas:

| Situación | Resultado |
|---|---|
| `id` de `ToolCall` vacío o duplicado entre mensajes `ASSISTANT` | `ConversionError` (siempre) |
| Dos `ToolResult` con el mismo `call_id` | `ConversionError` (siempre) |
| `ToolResult` que aparece **antes** de su `ToolCall` | `ConversionError` (siempre) |
| `call_id` vacío | `ConversionError` (siempre) |
| `ToolResult` cuya llamada **no está en la ventana** | `ConversionError` por defecto: las API de OpenAI y Anthropic rechazan resultados huérfanos |
| ídem, con `partial_window=True` en `to_provider_envelope` | Permitido; el modo queda registrado en `envelope.partial_window`; los `call_id` siguen debiendo ser únicos y no vacíos |
| `ToolCall` sin resultado posterior | Permitido: el bucle puede estar a mitad de turno; el conversor no valida el protocolo del proveedor |

Dependencia futura con `ContextManager` (contrato en `docs/02-arquitectura.md` §4: `assemble(session_id, model_id)` y `compact(session_id)`): quien ensamble ventanas debe cortarlas en límites consistentes, sin separar un mensaje `ASSISTANT` con `tool_calls` de sus resultados. Las historias relacionadas son [HU-02-02](../04b-historias-estado.md#hu-02-02) (recorte de salidas largas), [HU-02-03](../04b-historias-estado.md#hu-02-03) (compactación automática), [HU-02-04](../04b-historias-estado.md#hu-02-04) y [HU-02-05](../04b-historias-estado.md#hu-02-05) (compactación manual y solicitada por el modelo) y [HU-03-04](../04b-historias-estado.md#hu-03-04) (reanudar una sesión). Esta propuesta no implementa compactación ni persistencia; `partial_window` es solo el punto de contacto.

### 4.8 D8 y D9: almacenamiento y restauración

| Atributo | Dónde se guarda | Cómo se restaura |
|---|---|---|
| **D8** `Message.usage` | `MessageMeta.usage` (`TokenUsage | None`, solo enteros) | `Message.usage` se restaura desde el envelope. No se emite en el payload |
| **D9** `Message.content` de un mensaje `TOOL` | `MessageMeta.tool_message_content`, solo si difiere de `tool_result.content` | Si existe, es `Message.content`; si no, se usa el contenido del resultado de la herramienta |

### 4.9 Modelo de amenaza

Dominio de confianza: **el mismo proceso**. Se consideran estas amenazas:

1. Metadatos obsoletos o aplicados a otra solicitud (cubierto por §4.1, punto 1, con la limitación del punto 2).
2. Copias del payload alteradas por capas intermedias (reintentos, conmutación entre proveedores, registros): detectables con `matches` y por las verificaciones de §4.3.
3. Datos del proveedor que intenten influir en la clasificación de confianza: cubierto por §4.5.
4. Concurrencia: las conversiones son funciones síncronas y puras, sin puntos de `await`; cada llamada devuelve un valor propio sin estado compartido.

Fuera de alcance: código malicioso dentro del proceso, compromiso de la cadena de suministro y el contenido semántico de las inyecciones de prompt (este diseño solo preserva la marca `is_external`; no la calcula).

---

## 5. Decisión del Product Owner sobre D6 y análisis de D4

### Decisión del Product Owner sobre D6 (dominio válido de mensajes `SYSTEM`)

| Campo | Valor |
|---|---|
| Fecha | 2026-10-18 |
| Decisión | **APROBADA POR PRODUCT OWNER** |
| Tema | Dominio válido de los mensajes `SYSTEM` |
| Alcance | HU-07-01 y AC-01 |
| Tipo de aprobación | Funcional. **No** es la aprobación técnica de D-02, que sigue **PENDIENTE de A, B y C** |

Reglas:

1. Los mensajes `SYSTEM` solo son válidos como **prefijo contiguo al inicio** de la conversación canónica. Se admiten cero, uno o varios `SYSTEM` consecutivos al inicio.
2. Un `SYSTEM` después de cualquier mensaje `USER`, `ASSISTANT` o `TOOL` es una secuencia canónica **inválida**.
3. El conversor debe rechazar esa entrada con `ConversionError`.
4. No se permite normalización silenciosa ni reordenamiento.
5. El `ContextManager` deberá respetar esta regla cuando se implemente (por ejemplo, los resúmenes de compactación no pueden emitirse como `SYSTEM` intercalados). No se implementa aquí.
6. El texto original de AC-01 no se modifica: la decisión aclara el **dominio de entradas válidas**.

Estado de la validación: implementada y probada el 2026-10-18 (`validate_canonical_messages`, ambos conversores y `from_openai_messages`; `tests/adapters/test_canonical_validation.py`). La opción D6-a queda **descartada** por esta decisión.

Lo que **no** resuelve: rechazar una secuencia inválida no demuestra conversión sin pérdida. AC-01 sigue sin cumplirse del todo por D1, D2, D8 y D9 (§7). Tampoco cubre el `SYSTEM` de contenido vacío: es un prefijo válido para la regla, pero Anthropic no puede representarlo y sigue rechazándose (pregunta abierta en §12).

### D4 — bloques mixtos de texto y `tool_result` en Anthropic

`from_anthropic_payload` rechaza con `ConversionError` un mensaje de usuario que mezcla `tool_result` con otros bloques. **Verificado con el conversor real**: la conversión canónica → Anthropic nunca genera ese formato (cada `TOOL` sale como un mensaje `user` propio con un único `tool_result`, y un `USER` posterior es otro mensaje `user`). Por tanto, las entradas canónicas admitidas **no caen** en este rechazo, que solo afecta a payloads de terceros. Se mantiene el rechazo explícito. Esto cumple el requisito de manejo explícito de formatos no representables (FR-011); no es un caso de pérdida de AC-01 porque el formato nunca se origina en el modelo canónico.

### D6 — `SYSTEM` intercalado: resuelto funcionalmente por el Product Owner

Antes de la decisión se compararon dos caminos:

| Opción | Descripción | Resultado |
|---|---|---|
| D6-a | Mover los `SYSTEM` intercalados al parámetro superior y registrar su posición original en los metadatos | **Descartada**: cambia lo que recibe el modelo (la instrucción rige desde el inicio y no desde ese punto) |
| **D6-b** | Rechazar explícitamente el `SYSTEM` intercalado | **Adoptada** por decisión del Product Owner (2026-10-18), como regla de dominio de entrada y no como restricción provisional |

Consecuencias:

- Un `SYSTEM` intercalado deja de ser «una secuencia canónica válida que no se puede convertir» y pasa a ser una **entrada inválida** rechazada con `ConversionError` en ambos proveedores. AC-01 conserva su texto; su dominio de entrada queda aclarado en la especificación.
- Cambio de comportamiento para OpenAI: antes preservaba un `SYSTEM` intercalado de forma nativa; ahora lo rechaza. Es consecuencia de la decisión, no una regresión.
- Rechazar no es convertir sin pérdida: la preservación de los datos de las entradas **válidas** sigue pendiente por D1, D2, D8 y D9.
- Sigue abierto, para A, B y C, el `SYSTEM` vacío (§12).
- Restricción futura para el `ContextManager` (sin implementar): no puede emitir `SYSTEM` fuera del prefijo inicial.

---|---|---|
| **D6-a** | Mover los `SYSTEM` intercalados al parámetro superior y registrar su posición original en los metadatos, para que la restauración los devuelva a su lugar | La restauración sería exacta, pero **cambia lo que recibe el modelo**: la instrucción rige desde el inicio y no desde ese punto. Es un cambio de semántica con implicaciones de seguridad |
| **D6-b** (recomendada **provisionalmente**) | Mantener el rechazo explícito | Falla cerrada; impacto mínimo; el modelo recibe exactamente lo que se envió o nada |

**Aclaración obligatoria**: rechazar una secuencia **no** es convertirla sin pérdida. Mientras exista el rechazo, **D6 permanece identificado como un incumplimiento pendiente de AC-01** para las secuencias canónicas válidas con un `SYSTEM` intercalado (o vacío) dirigidas a Anthropic. Este documento no declara AC-01 cumplido mediante una restricción de alcance que nadie ha aprobado.

Caminos de decisión para el Product Owner y para A, B y C (cualquiera requiere aprobación; ninguno se aplica aquí):

1. Aprobar D6-a, con la revisión de seguridad correspondiente.
2. Que el Product Owner decida formalmente sobre el alcance de AC-01 para estas entradas. Los criterios de aceptación son inmutables (Principio V de la constitución): cualquier cambio queda fuera de este documento y debe seguir el procedimiento formal del proyecto.
3. Establecer, como restricción de diseño aprobada, que el `ContextManager` no emita `SYSTEM` intercalados hacia ese proveedor (por ejemplo, para los resúmenes de compactación). Esto traslada el problema a otra historia y también requiere aprobación.

---

## 6. Casos que todavía no podrían convertirse sin pérdida

| Caso | Motivo | Estado con la propuesta |
|---|---|---|
| `SYSTEM` intercalado (D6) | Secuencia canónica inválida por decisión del Product Owner (2026-10-18) | Rechazado con `ConversionError`; resuelto como regla de dominio. El `SYSTEM` vacío hacia Anthropic sigue rechazado (pregunta abierta en §12) |
| Payloads de terceros con bloques mixtos (D4) | No provienen del formato canónico | Siguen rechazados; no afectan a entradas canónicas |
| Bloques no textuales (`image`, `document`) | Fuera del alcance de la historia | Siguen rechazados |
| `Message` canónico incoherente (D10) | Antes descartaba `tool_calls` o `tool_result` sin avisar | **Corregido** el 2026-10-18 (T025, fuera de D-02): `ConversionError` en ambos conversores |
| Envelope elegido por error por el llamador | La biblioteca no puede detectarlo (§4.1) | Limitación documentada; mitigación: registrar `conversion_id` |
| Restauración con envelope manipulado en memoria | Mismo dominio de confianza | Sin protección |
| Argumentos no serializables o con NaN | No son JSON | Ya rechazados |

---

## 7. Impacto en AC-01

- AC-01 sigue **parcialmente verificado**. Esta propuesta no lo cambia. La decisión del Product Owner sobre D6 (§5) aclara el dominio de entradas válidas sin cambiar la redacción del criterio, y la validación de entradas inválidas (D6 y D10) **no sustituye** la conservación de datos de las entradas válidas: D1, D2, D8 y D9 siguen pendientes.
- Si se aprobara e implementara, el round-trip a través del envelope conservaría `is_external`, `is_error`, `usage` por mensaje y el contenido de los mensajes `TOOL` en toda secuencia del dominio válido. Con D6 resuelto por el Product Owner no queda ninguna secuencia válida que el conversor rechace, salvo el `SYSTEM` de contenido vacío hacia Anthropic (pregunta abierta en §12). AC-01 se daría por cumplido solo tras la implementación, la verificación y la aprobación técnica.
- Los criterios de aceptación no se modifican.

---

## 8. Contratos y archivos afectados

| Elemento | Cambio |
|---|---|
| `core/entities.py` (`Message`, `ToolResult`) | **Sin cambios** |
| `core/interfaces/provider.py` (`Provider`, `ProviderResponse`, `Provider.complete`) | **Sin cambios** |
| `adapters/converters/sidecar.py` (implementado; el diseño lo llamaba `envelope.py`) | Nuevo: `WireRef`, `MessageMeta`, `ConversionEnvelope`, instantánea JSON y huellas |
| `adapters/converters/base.py` | Sin cambios en `ProviderMessageConverter`; Protocolo adicional propuesto `EnvelopeConverter` |
| `adapters/converters/openai_converter.py`, `anthropic_converter.py` | Nueva ruta de envelope y restauración; las funciones existentes se conservan |
| `adapters/converters/__init__.py` | Exportaciones nuevas (`to_openai_envelope`, `to_anthropic_envelope`, `restore_messages`, `ConversionEnvelope`) |
| `from_openai_messages`, `from_anthropic_payload` | Según la decisión de §4.4 (opción 2 recomendada: `DeprecationWarning`) |
| `tests/adapters/` | Pruebas nuevas; las `test_pending_d1_*` y `test_pending_d2_*` se transforman en pruebas de preservación |
| `specs/004-.../` y `docs/PROGRESO.md` | Actualización tras la implementación |

HU-07-02 (adaptador LiteLLM) usaría `to_provider_payload` o el envelope; no depende de este cambio para funcionar.

---

## 9. Riesgos

| Riesgo | Mitigación |
|---|---|
| Fallo abierto si se restaura sin metadatos (`is_external=False` = confiable) | No existe ruta de restauración sin envelope; las funciones `from_*_messages`/`from_anthropic_payload` se marcan como obsoletas (opción 2) |
| Envelope elegido por error por el llamador | No detectable; se documenta y se recomienda registrar `conversion_id` |
| Falsa sensación de seguridad con la huella | Se documenta que prueba contenido, no identidad de conversión ni defensa dentro del proceso |
| Mutación del payload original tras crear el envelope | Instantánea JSON inmutable y copia por acceso |
| Coerciones silenciosas de `json` (claves enteras, tuplas) | Verificación de igualdad de la instantánea; `ConversionError` |
| Correlación de herramientas incorrecta en ventanas parciales | Política de §4.7 y `partial_window` explícito; dependencia documentada con `ContextManager` |
| El envelope podría filtrarse a registros o a la red | No se serializa al payload; se prohíbe incluirlo en trazas de proveedor; revisión en HU-07-02 |
| Crecimiento del alcance (D4, D6, D10) | D6 resuelto por decisión del Product Owner; D10 corregido fuera de D-02; D4 sigue como rechazo explícito |
| Cambio de la forma de `ProviderMessageConverter` afecta a B | No se modifica; Protocolo adicional |

---

## 10. Plan de implementación (no ejecutado)

Microtareas de menos de 60 minutos, con pruebas en rojo primero. (Ejecutado bajo la autorización colectiva comunicada por el Product Owner; ver §0. La aprobación individual de §12 sigue pendiente.)

1. **T019** — Tipos del envelope (`WireRef`, `MessageMeta`, `ConversionEnvelope`), instantánea JSON estricta, huellas y `matches`.
2. **T020** — `to_provider_envelope` y restauración para OpenAI (D1, D2, D8, D9, política de correlación de §4.7).
3. **T021** — `to_provider_envelope` y restauración para Anthropic con `WireRef` y la verificación de cobertura (si supera los 60 minutos, dividir en referencias/cobertura y restauración).
4. **T022** — Pruebas de seguridad y concurrencia (§11).
5. **T023** — Transformar `test_pending_d1_*`/`test_pending_d2_*` en pruebas de preservación; actualizar documentos y PROGRESO.
6. **T024 (propuesta adicional)** — Marcar como obsoletas `from_openai_messages` y `from_anthropic_payload` con `DeprecationWarning` y actualizar sus pruebas, según la decisión de §4.4.
7. **T025 (D10) — EJECUTADA el 2026-10-18, fuera de D-02**: `ConversionError` para los mensajes canónicos incoherentes en ambos conversores (validador compartido `validate_canonical_messages`). Evidencia en `tests/adapters/test_canonical_validation.py` y `docs/PROGRESO.md`. La validación del dominio de `SYSTEM` (decisión D6) se ejecutó en el mismo cambio y se registra en `tasks.md` como T026. T024 sigue siendo propuesta; T019–T023 siguen sin implementar.

**Estado (v4)**: T019–T024 ejecutadas el 2026-10-18 con pruebas en rojo primero (ver §0 y `tasks.md`). T018 permanece **sin marcar** hasta que A, B y C aprueben individualmente.

---

## 11. Plan de pruebas propuesto

Las pruebas nuevas usan fixtures **escritas a mano** (diccionarios literales y ejemplos de la documentación de cada proveedor), independientes del código que verifican. No se ejecuta ni implementa ninguna todavía.

### 11.1 Escenarios originales (1–16)

| # | Entrada | Resultado esperado | Riesgo cubierto | Condición de éxito |
|---|---|---|---|---|
| 1 | `USER` con `is_external=True`, OpenAI, ida y vuelta | Se conserva; el payload no contiene el campo | D1 | `restore_messages(env)` igual al original |
| 2 | Ídem, Anthropic | Se conserva | D1 | Igualdad con el original |
| 3 | `ToolResult(is_error=True)`, OpenAI | Se conserva; el payload no contiene `is_error` | D2 | Igualdad; clave ausente en el payload |
| 4 | Varios `ToolCall` y `ToolResult`, éxito y error mezclados | Cada resultado conserva `call_id` e `is_error` | Mezcla de resultados | Igualdad por posición e id |
| 5 | `ToolCall.id` duplicados o vacíos; `ToolResult` con id sin llamada previa | `ConversionError` | Correlación ambigua | Excepción con el id en el mensaje |
| 6 | Mensajes de contenido idéntico y metadatos distintos | Cada uno recupera los suyos | Confusión por contenido | Igualdad por posición |
| 7 | Mensajes reordenados en el payload | `ConversionError` | Alteración de orden | Excepción |
| 8 | Entradas del envelope intercambiadas entre sí | `ConversionError` | Metadatos del mensaje equivocado | Excepción (contenido o rol no coincide) |
| 9 | Payload modificado (contenido, rol, id, bloques) vía `matches` y vía copia | `matches` devuelve `False`; `ConversionError` si se restaura una copia alterada | Manipulación de la copia | `False` / excepción |
| 10 | Dos conversiones asíncronas simultáneas (`asyncio.gather` con cesiones de control) | Cada una restaura solo lo suyo | Contaminación | Igualdad con cada original |
| 11 | Envelope de A usado con el payload de B (solo posible mediante `matches`) | `matches` devuelve `False` si el contenido difiere | Uso indebido entre solicitudes | `False` |
| 12 | Restaurar sin envelope | No existe ruta pública; invocar con `None` ⇒ `TypeError` o `ConversionError` | Fallo abierto | Excepción |
| 13 | Anthropic: `is_error` del payload distinto del envelope | `ConversionError` | Manipulación de `is_error` | Excepción |
| 14 | OpenAI: `is_error`/`is_external` inyectados en el payload | Ignorados; nunca elevan ni bajan la confianza | Influencia del proveedor | Valores iguales a los del envelope |
| 15 | D8 y D9 | Se conservan | Pérdida de uso y contenido | Igualdad |
| 16 | Las 206 pruebas actuales | Siguen verdes; `to_provider_payload` sin cambios | Regresión | Suite en verde |

### 11.2 Escenarios nuevos (17–28)

| # | Entrada | Resultado esperado | Riesgo cubierto | Condición de éxito |
|---|---|---|---|---|
| 17 | Dos mensajes `USER "Hola"`, uno `is_external=True` y otro `False`, en conversiones distintas | Payloads y huellas **idénticos**; cada envelope restaura su propio valor | Creer que la huella identifica la conversión | `payload_a == payload_b`, `digest_a == digest_b`, restauraciones distintas |
| 18 | Intercambio accidental de metadatos entre dos conversiones de contenido idéntico | No detectable por la biblioteca; no hay API para cruzar payload y metadatos | Límite de las garantías (§4.1) | Prueba que documenta el límite: restaurar el otro envelope devuelve los datos de **ese** envelope |
| 19 | Anthropic con `SYSTEM "A"`, `SYSTEM "B"` iniciales | `system` es lista de dos bloques; la restauración devuelve dos `SYSTEM` en orden | Fusión de mensajes `system` | Dos mensajes, orden y límites iguales |
| 20 | `TOOL` canónico seguido de `USER` en Anthropic | Dos mensajes externos `user`; `TOOL` se restaura como `TOOL` | Rol externo `user` confundido con `USER` | Roles canónicos iguales a los originales |
| 21 | Modificar el diccionario externo (el que se pasó o el devuelto por `payload`) después de crear el envelope | `restore_messages` no cambia | Mutación posterior | Resultado idéntico al previo |
| 22 | `ToolResult` cuyo `ToolCall` no está en la ventana, con y sin `partial_window` | Sin opt-in: `ConversionError`; con opt-in: se acepta y queda `partial_window=True` | Ventanas parciales | Excepción / aceptación según el modo |
| 23 | Ids duplicados; dos resultados para el mismo id; resultado antes de su llamada; referencia ambigua | `ConversionError` en todos, también con `partial_window=True` (salvo el huérfano) | Correlación ambigua | Excepción en cada caso |
| 24 | Respuesta nueva de OpenAI/Anthropic procesada con `from_*_response` | No recibe envelope; `usage` y contenido salen de la respuesta; ningún metadato local | Reutilizar metadatos de una solicitud en una respuesta | La firma no admite envelope; resultado independiente del envelope |
| 25 | Cuatro o más conversiones simultáneas con metadatos distintos | Sin contaminación | Estado compartido | Cada restauración igual a su original |
| 26 | D8 y D9 en ambos proveedores; `Message.usage` distinto del `usage` de una respuesta posterior | `Message.usage` restaurado intacto; no se mezcla con el de la respuesta | Confundir usos | Igualdad y ausencia de fusión |
| 27 | D4 (`tool_result` mezclado con texto, payload de terceros) y D6 (`SYSTEM` tras `USER`/`ASSISTANT`/`TOOL`, hacia OpenAI y Anthropic) | `ConversionError` explícito; D6 es entrada inválida por decisión del Product Owner (ya cubierto por `test_canonical_validation.py`) | Rechazo silencioso, reordenamiento o declaración falsa de cumplimiento | Excepción con la posición del mensaje; sin reordenamiento |
| 28 | Fixtures literales escritas a mano a partir de la documentación de cada proveedor, no generadas por los conversores | Se restauran correctamente; los envelopes creados por el conversor coinciden con la forma esperada | Probar el código con su propia salida | Las fixtures no importan los conversores para construirse |

---

## 12. Revisión técnica y aprobaciones necesarias

Preguntas para A, B y C:

1. ¿Se aprueba **B + A** (envelope con metadatos) descartando la extensión de modelos (C)?
2. ¿Se aprueba que la restauración sea **solo por envelope** (`restore_messages(envelope)`) y no con payload y metadatos como argumentos separados?
3. ¿Se aceptan las **garantías y límites** de §4.1 (en particular, que el envelope equivocado no es detectable y que no hay protección frente a código del mismo proceso)?
4. ¿Se acepta el **modelo `WireRef`** y sus verificaciones de cobertura para Anthropic (§4.3)?
5. **Ventanas parciales**: ¿se acepta el opt-in `partial_window` y la política de §4.7, y quién coordina con el `ContextManager`?
6. **Migración** de `from_openai_messages` y `from_anthropic_payload`: ¿opción 1, 2 (recomendada) o 3?
7. **D6** (resuelto por el Product Owner el 2026-10-18: `SYSTEM` solo como prefijo contiguo; ver §5). Queda por decidir el `SYSTEM` de **contenido vacío**: es un prefijo válido, pero Anthropic no puede representarlo y hoy se rechaza. ¿Se mantiene el rechazo, se documenta como entrada inválida o se omite con registro explícito?
8. ¿Se incluyen **D8 y D9** en el mismo cambio y se abre **T024**? (T025 / D10 ya se ejecutó fuera de D-02; ¿se confirma esa decisión?)
9. ¿Qué debe revisar B antes de que HU-07-02 y SPK-01 usen el envelope?
10. ¿Se confirman como reglas de contrato las invariantes de `validate_canonical_messages` (`tool_calls` solo en `ASSISTANT`; `tool_result` solo en `TOOL`; `TOOL` exige `tool_result`)? Derivan del modelo `Message`, pero no figuran como requisito expreso en la spec original.

| Integrante | Rol | Decisión | Fecha | Observaciones |
|---|---|---|---|---|
| A | Núcleo | _Pendiente_ | — | |
| B | Estado | _Pendiente_ | — | |
| C | Control y conexiones | _Pendiente_ | — | |

Valores permitidos: `Aprobada`, `Aprobada con cambios` (indicar cuáles) o `Rechazada`. Hasta que las tres decisiones estén registradas, T018 permanece sin marcar y HU-07-01 permanece **En revisión**.

**Consenso comunicado (2026-10-18)**: el Product Owner comunicó un consenso colectivo del equipo con cinco recomendaciones (ver §0). Se registra como **consenso comunicado por el Product Owner**, no como firma individual: las filas de arriba **no** se rellenan con él.

**Estado de dependencias al redactar**: SPK-01 está «Pendiente» en `docs/PROGRESO.md` (no hay resultados disponibles); D-01 de SPK-02 sigue pendiente de aprobación; T016 / Sp1-03 de HU-00-01 sigue pendiente.

---

## 13. Historial de revisión del documento

| Versión | Fecha | Cambios |
|---|---|---|
| v1 | 2026-10-18 | Primera propuesta: comparación de A/B/C, sidecar con huella SHA-256, restauración con payload y sidecar como argumentos, análisis de D4 y D6, plan de 16 pruebas |
| v2 | 2026-10-18 | Corrección tras revisión técnica |
| v3 | 2026-10-18 | Registro de la decisión del Product Owner sobre D6 (dominio de `SYSTEM`), ejecución de T025 (D10) fuera de D-02 y actualización de §2, §4.3, §5–§7, §9–§12. D-02 sigue **pendiente de aprobación técnica** |
| v4 | 2026-10-18 | Registro de la autorización de implementación (consenso colectivo comunicado por el Product Owner), implementación de T019–T024, resolución de D1, D2, D8 y D9, mecanismo del `SYSTEM` vacío y adaptaciones (§0). D-02 sigue **pendiente de aprobación técnica individual** |

Correcciones de la v2:

1. **Identidad del envelope**: la v1 sugería que `conversion_id` y la huella SHA-256 vinculaban un sidecar con su payload. Dos mensajes que solo difieren en `is_external` producen el mismo payload y la misma huella, así que la huella solo prueba integridad de contenido. La restauración pasa a `restore_messages(envelope)`, sin argumentos independientes, y se documentan las garantías reales y sus límites.
2. **Correspondencia Anthropic**: la v1 suponía una correspondencia directa entre la cantidad de mensajes canónicos y externos. Se sustituye por el modelo `WireRef` con compatibilidad de roles (un `TOOL` canónico se representa como `user` externo) y verificación de cobertura.
3. **Compatibilidad de API**: la v1 afirmaba conservar las funciones existentes pero proponía exigir un parámetro `sidecar` en `from_*_messages`. Se retira; se separan canónico → payload, restauración exacta y respuestas nuevas, y se usan solo nombres reales o marcados como propuestos.
4. **Inmutabilidad**: la v1 daba por inmutable un `dict` dentro de un `dataclass(frozen=True)`. Se sustituye por una instantánea JSON estricta con copia por acceso.
5. **Correlación de herramientas**: la v1 exigía siempre la llamada previa en el mismo payload. Se distingue conversación completa de ventana parcial.
6. **Redacción de D6 y AC-01**: la v1 podía leerse como que AC-01 quedaría cumplido «para secuencias convertibles». La v2 aclara que rechazar no es convertir sin pérdida y mantiene D6 como incumplimiento pendiente.
7. **Hallazgos añadidos**: D10 (mensajes canónicos incoherentes), D6 por `SYSTEM` vacío, consumidores reales de las funciones existentes y modelo de amenaza.
8. **Pruebas**: se conservan los 16 escenarios y se añaden 12, con entrada, resultado esperado, riesgo y condición de éxito.

Cambios de la v3:

1. **D6**: deja de ser un incumplimiento pendiente de AC-01 y pasa a regla de dominio de entrada aprobada por el Product Owner; D6-a se descarta.
2. **D10**: corregido con un validador compartido y pruebas de regresión (T025 ejecutada fuera de D-02).
3. **Sin cambios**: D1, D2, D8 y D9 siguen pendientes; el envelope, `restore_messages` y T018–T024 siguen sin implementar; la aprobación técnica de A, B y C sigue pendiente.
