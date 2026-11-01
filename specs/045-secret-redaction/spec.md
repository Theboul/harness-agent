# Especificación: HU-10-02 — Redacción de secretos en registros

**Rama**: `claude/hu-10-02-secret-redaction-b3e2f6` · **Responsable**: B — Estado · **Sprint**: 4 (cierre adelantado al 6-nov-2026) · **PHU**: 1 · **Prioridad**: Alta  
**Requisitos**: RF-10.4, RNF-16, V-13 · **Depende de**: HU-10-01 (la traza aún no existe; esta historia cubre lo que hoy se escribe en disco) · **Ficha**: [HU-10-02](../../docs/04d-historias-conexiones.md#hu-10-02)  
**Absorbe**: `core/redaction.py::hide_url_credentials` (HU-11-02) y el riesgo abierto PD-10 / «V-13 solo en parte» de HU-03-04.

## Contexto

El flujo de tickets se probó con claves reales (Gemini, Groq) cargadas desde `.env`. Hoy una clave que aparezca en una salida de herramienta, un error o un mensaje se escribe tal cual en SQLite (`events.content`, `mensajes`, `resumenes`). Solo se ocultan las credenciales de URL.

## Aclaraciones (clarify, sin preguntas al PO: el criterio es explícito)

- Q1 ¿Qué es «registro»? → A: todo lo que el harness escribe en la base de sesiones: el `content` de cada evento, cada mensaje guardado para `/reanudar` y el texto del resumen de compactación. Los criterios y el contexto esencial vienen del ticket (texto de la persona) y no se tocan.
- Q2 ¿Cambia lo que ve el modelo? → A: **no**. Solo se redacta lo que se escribe en disco; la vista en memoria, la terminal y los eventos entregados a los suscriptores no cambian.
- Q3 ¿Dónde se aplica? → A: en los puntos de escritura ya existentes —`ConversationCapture`/`clean_message` (mensajes), `attach_event_recorder` (eventos) y `SqliteCompactionArchive` (resumen)—, nunca en cada herramienta. Puertos, catálogo de eventos y `core/loop.py` no cambian.
- Q4 ¿Qué se oculta? → A: (1) patrones de claves conocidas, (2) valores secretos **conocidos** inyectados (la clave del proveedor y el valor de las variables de entorno cuyo nombre parece de clave, incluidas las del `.env`), comparados literalmente, (3) credenciales de URL. El marcador es `HIDDEN_SECRET`.
- Q5 ¿Límite? → A: heurística, no garantía (regla de negocio 1): hay falsos negativos (una clave sin prefijo conocido, partida o codificada) y falsos positivos (un texto `nombre_con_key=valor`). Los valores conocidos de menos de 8 caracteres se ignoran para no destruir texto común.

## Escenarios

1. **AC-01.** Un registro con una clave de patrón conocido se guarda con el marcador en su lugar (mensaje de usuario, resultado de herramienta, argumentos, evento, resumen).
2. **Valor conocido.** La clave real del proveedor y los valores secretos del entorno se ocultan aunque no tengan patrón.
3. **Idempotente.** Redactar un texto ya redactado no lo cambia.
4. **Texto normal intacto.** Prosa, rutas (Windows y POSIX), código y números no cambian.
5. **`/reanudar`.** La conversación reconstruida no contiene el secreto.
6. **Rendimiento.** Un texto de varios MB se procesa en tiempo lineal (sin retroceso catastrófico).
7. **Sin alterar la sesión en curso.** El historial en memoria conserva el texto original.

## Requisitos funcionales

- **FR-001**: `core/secret_redaction.py` MUST ofrecer `redact_secrets(text, *, known=()) -> str` (función pura, solo biblioteca estándar) y `SecretRedactor` (valores conocidos + `value()` recursivo para cargas JSON).
- **FR-002**: MUST ocultar claves con prefijo conocido (`sk-`, `gsk_`, `AIza`, `ghp_`/`github_pat_`…, `xox*-`, `AKIA`/`ASIA`), JWT, `Bearer`/`Authorization`, pares `NOMBRE=valor` con nombre que contiene key/secret/token/password/credential, y credenciales de URL.
- **FR-003**: MUST ser idempotente, de coste lineal y no alterar texto sin secretos.
- **FR-004**: `clean_message`, `attach_event_recorder` y `SqliteCompactionArchive` MUST aceptar un redactor opcional; `compose()` MUST construirlo con la clave de `config.api_key` y el entorno combinado.
- **FR-005**: MUST NOT cambiar `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`.
- **FR-006**: Sin redactor inyectado el comportamiento anterior se conserva (compatibilidad de pruebas antiguas); `compose()` siempre lo inyecta.

## Fuera de alcance

Trazas estructuradas (HU-10-01), archivo de progreso y salida del PR (siguen con `hide_url_credentials`; se anota), redacción de lo que se muestra en terminal.
