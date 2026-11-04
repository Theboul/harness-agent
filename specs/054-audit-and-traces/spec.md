# Especificación: HU-05-05 y HU-10-01 — Registro de auditoría de decisiones y trazas estructuradas de cada llamada

**Rama**: `gustavo` · **Responsable de las fichas**: B — Estado · **Implementa**: Claude por encargo de la persona usuaria (pendiente de ratificar por B, A y C)
**Depende de**: HU-05-03 (aprobación), HU-01-05 (bus de eventos), HU-03-01 (almacén SQLite), HU-10-02 (redacción de secretos), HU-05-01 (política), HU-09-01 (subagentes), HU-07-04 y HU-07-05 (reintentos y conmutación), HU-11-04.1 y HU-11-08.2 (verificación y arranque: otras fuentes de decisiones). **Fuera de alcance**: exportar a archivos, rotación o purga, métricas de coste, paneles (otras historias).

## Resumen

Hoy el sistema decide permisos y llama al modelo y a las herramientas sin dejar un registro que un evaluador pueda consultar. Esta especificación añade dos registros, ambos en la misma base SQLite y consultables desde la sesión:

- **Auditoría (HU-05-05).** Cada decisión de permiso (permitida, denegada, aprobada o rechazada por la persona) queda con **herramienta, argumentos, decisión y hora**, también las de herramientas MCP, de la verificación de criterios, de la rutina de arranque y de subagentes (con quién pide). Los argumentos se redactan **antes** de escribirse.
- **Trazas (HU-10-01).** Cada llamada al modelo y a una herramienta deja una traza estructurada con **tipo, duración, tokens y resultado**; nunca guarda el contenido de mensajes ni de resultados.

Los eventos que el bucle publica **no llevan los argumentos** (decisión vigente: sus cargas no incluyen argumentos ni contenido), así que la auditoría no puede ser una simple vista sobre `events`. Se completa **sin tocar** ningún puerto, el bucle, el catálogo de eventos, `core/redaction.py` ni `core/verification/`: una envoltura de la política recuerda los argumentos ya redactados de cada llamada y un suscriptor del bus escribe el registro cuando llega `permission_decided` (D-01). Las trazas se miden con envoltorios del proveedor y del registro de herramientas, colocados en `bootstrap.py` (D-08).

La auditoría no se puede apagar. Las trazas están **encendidas por defecto** y se apagan con `[traces] enabled = false` (D-14). El esquema pasa a la versión 7 con dos tablas nuevas.

## Historias y criterios de aceptación (literales de `docs/04c-historias-control.md` y `docs/04d-historias-conexiones.md`)

### HU-05-05 — Registro de auditoría de decisiones

**Flujo general**

1. Ocurre una aprobación, rechazo o denegación automática.
2. El sistema escribe un registro con herramienta, argumentos, decisión y hora.
3. El evaluador consulta el registro.

**Reglas de negocio**

1. Los argumentos se redactan para no exponer secretos.

**Criterios de aceptación**

- **AC-01 — Decisión registrada en auditoría.** Dado una decisión de aprobación, rechazo o denegación automática, cuando ocurre, entonces queda registrada con herramienta, argumentos, decisión y hora.
- **AC-02 — Auditoría mínima con argumentos redactados.** Dado un registro de aprobación, rechazo o denegación que contenga una clave con patrón conocido o el valor de una variable de entorno sensible, cuando se persiste el registro en el Sprint 3, entonces el dato queda sustituido por una marca antes de escribirse. Este control mínimo no reemplaza HU-10-01 ni HU-10-02 (trazas de modelo y herramientas, Sprint 4).

### HU-10-01 — Trazas estructuradas de cada llamada

**Flujo general**

1. Ocurre una llamada.
2. El sistema registra tipo, duración, tokens y resultado.
3. El evaluador consulta la traza de la sesión.

**Reglas de negocio**

1. El formato de traza es estructurado y consultable.
2. La traza redacta secretos.

**Criterios de aceptación**

- **AC-01 — Traza de cada llamada.** Dado una sesión terminada, cuando consulto la traza, entonces veo cada llamada con su duración, tokens y resultado en formato estructurado.

En el resto del documento se citan como **HU-05-05 AC-01**, **HU-05-05 AC-02** y **HU-10-01 AC-01**.

## Decisiones (dudas pequeñas resueltas con el criterio más seguro; pendientes de ratificar)

No hizo falta parar por un caso A/B/C: nada de lo siguiente toca un puerto de `core/interfaces/`, `core/loop.py`, `core/events.py`, `core/redaction.py` ni `core/verification/`, y `cli/` no cambia (los comandos nuevos solo se registran en el diccionario de `bootstrap.py`).

- **D-01 Qué llevan hoy los eventos y cómo se completa (sin caso A/B/C).** `permission_decided` lleva `call_id`, `name`, `decision`, `resolved_as` y `reason`; `approval_resolved`, `call_id`, `name`, `action`, `approved` y `source`; el evento trae además sesión y hora. **Faltan los argumentos**, que HU-05-05 AC-01 exige y que ningún evento lleva a propósito. Opciones valoradas: **A** ampliar la carga (toca `core/loop.py`, el verificador y la rutina de arranque, invierte la regla de «eventos sin argumentos» y los argumentos irían a `events`); **C** vista parcial sobre `events` (incumple AC-01); **elegida, variante de B sin tocar nada protegido:** (1) una envoltura de la política, la más externa (`ArgumentsTap`), que en cada `evaluate` guarda los argumentos **ya redactados** de la llamada indexados por su `call_id` y devuelve la decisión de dentro **sin cambiarla**; (2) un suscriptor del bus (`AuditRecorder`) que, al llegar `permission_decided`, escribe la fila con esos argumentos y, al llegar `approval_resolved`, la completa. Funciona porque en el bucle, en el verificador y en la rutina de arranque la decisión se publica **justo después** de evaluarla, sin `await` entre medias (D-15). Costo asumido: la fila duplica la decisión que ya está en `events`, porque tiene que viajar con los argumentos.
- **D-02 Qué se audita.** **Toda** decisión de la política: permitida, a preguntar y denegada, no solo las tres que nombra el AC, porque sin las permitidas un evaluador no distingue «permitida» de «no registrada». Quedan fuera las llamadas rechazadas **antes** de decidir (herramienta desconocida, argumentos inválidos): no hubo decisión de permiso; siguen en `events` (`tool_finished`).
- **D-03 Un registro por decisión, completado al resolverse.** Al llegar `permission_decided` se inserta la fila con `resolucion` = `permitida` (allow), `denegada` (deny, o preguntar sin aprobador) o `pendiente` (preguntar con aprobador). Al llegar `approval_resolved` se actualiza la última fila de esa sesión y llamada: `aprobada`, `rechazada` o `fallida` (acción nula: el aprobador falló, falla cerrado), con `accion`, `fuente` y hora de resolución. Un corte durante la pregunta deja `pendiente`.
- **D-04 Argumentos redactados antes de escribir (AC-02).** Los argumentos pasan por el `SecretRedactor` de la composición (claves con prefijo, JWT, `Bearer`, pares `nombre=valor` de nombre sensible, credenciales de URL y **los valores de las variables de entorno sensibles**), después se serializan como JSON solo ASCII (los caracteres ocultos, como U+202E o U+200B, quedan escapados y visibles) y cada texto se acorta a 200 caracteres con una marca de recorte y el total a 2 000. Se redacta **antes** de acortar. Si algo falla al preparar los argumentos, se guarda la marca «sin dato»: nunca se guarda el original ni se cambia la decisión. La redacción es heurística (HU-10-02).
- **D-05 Quién pide.** La fila guarda el **origen** por el prefijo del identificador de la llamada: `verificacion-` (criterios, HU-11-04.1), `arranque-` (rutina de arranque, HU-11-08.2) y el resto `agente`. Si la sesión del evento tiene `parent_id`, la consulta lo muestra como **subagente** con las mismas 8 letras de sesión que ve la persona al aprobar (`requester_label`). Una prueba con el verificador y la rutina reales falla si esos prefijos cambian.
- **D-06 Falla cerrado en la auditoría.** Un fallo al escribir la auditoría **no se traga**: sube por el bus como el del registrador de eventos (`EventDeliveryError`) y **la herramienta no se ejecuta** (es el comportamiento de Q4 del bucle: nada se ejecuta si la decisión no se pudo publicar). Es lo contrario de las trazas (D-11) y es deliberado: una auditoría que falla en silencio no sirve para «verificar que los controles funcionan». Un evento de decisión con la carga incompleta no hace fallar: los campos que faltan quedan como «sin dato».
- **D-07 Esquema v7, dos tablas, sin clave foránea.** `auditoria` y `trazas` (columnas en el plan), aditivas, con migración v1…v6 → v7 en una transacción; una base v7 se acepta y la 8 se rechaza sin modificarla. **Sin `REFERENCES`** a `sessions` ni a `events`: el registro de auditoría es evidencia y no debe desaparecer ni impedir nada si se borra una sesión (hoy no hay borrado de sesiones; así tampoco lo bloqueará), y se consulta con `LEFT JOIN` para saber si una sesión es hija. Sin `CHECK` sobre valores (tolerancia ante cargas inesperadas, D-06).
- **D-08 Trazas: envoltorios, no suscriptor del bus.** La tarea Sp4-21 del plan habla de suscribirse al bus, pero **ningún evento lleva duración ni tokens** y no hay evento de llamada al modelo; hacerlo por el bus exigiría tocar el catálogo. Se miden con dos envoltorios que `bootstrap.py` coloca sin tocar el bucle: `TracingProvider` (implementa `Provider`) **por fuera de los reintentos y de la conmutación** y `TracingRegistry` (implementa `ToolRegistry`; sus herramientas medidas llevan el mismo nombre, esquema y riesgo). Una traza por **llamada que hace el bucle** (lo que ve la persona), con la duración total incluida la espera de reintentos y el modelo **activo al terminar** (una conmutación por fallo se ve en el nombre); los intentos intermedios ya están en los eventos `provider_error` con motivo `retry` y `provider_switched`. La llamada de resumen de la compactación también es una llamada al modelo y deja su traza.
- **D-09 Qué guarda una traza.** Solo metadatos: tipo (`modelo` o `herramienta`), nombre (el modelo activo o la herramienta), instante de inicio (UTC), duración en milisegundos (reloj monótono inyectado), tokens de entrada y de salida **de `ProviderResponse.usage`**, resultado y tamaño en caracteres del contenido de la respuesta o del resultado. **Si no hay `usage` (o la llamada falló) los tokens quedan nulos y se muestran como «sin dato»: nunca se inventa un cero.** Nunca se guardan mensajes, texto del modelo, argumentos ni contenido de resultados. Nombre y resultado pasan por el redactor aunque solo sean metadatos (regla 2 de HU-10-01).
- **D-10 Resultado.** Modelo: `ok`, el **nombre de la clase** del error del proveedor (`ProviderTimeout`, `RateLimited`, `QuotaExceeded`, `FailoverExhausted`…) o `error`; herramienta: `ok`, la etiqueta entre corchetes que abre el contenido de un resultado de error (`[fuera_del_area]` → `fuera_del_area`, solo `[a-z_]` hasta 40) o `error`; una excepción de la herramienta, el nombre de su clase; `cancelado` si la llamada se cancela (se anota en un `finally` sin capturar la cancelación, que sigue subiendo).
- **D-11 Registrar una traza nunca cambia el resultado.** Un fallo al escribirla (disco, tabla ausente) se captura (solo `Exception`), se avisa **una vez por ejecución** por el `WarningSink` con una línea fija sin texto del motor («No se pudo guardar una traza; la sesión continúa sin ella.») y la respuesta o el resultado de la llamada vuelven intactos. Medir tampoco cambia los argumentos ni el contenido.
- **D-12 Subagentes.** El bucle de un subagente usa **su** envoltorio de proveedor y de registro, atados a su sesión hija: sus trazas quedan bajo la sesión hija y las de `delegar` (con toda la delegación dentro de su duración) bajo la del orquestador. Sus decisiones se auditan con la sesión del evento, que es la hija.
- **D-13 Consulta.** Funciones de lectura en cada almacén y dos comandos de sesión: **`/auditoria [id]`** y **`/trazas [id]`** (sesión actual por defecto; el id se valida como en `/reanudar`). Imprimen una tabla corta de las **últimas 30** filas de esa sesión y de sus sesiones hijas directas, con el total. Auditoría: hora (UTC), quién, herramienta, argumentos (≤ 50 caracteres), resolución. Trazas: hora, sesión (si es hija), tipo, nombre, duración, tokens (o «sin dato») y resultado. Nunca lanzan: un fallo de lectura es una línea fija; sin filas, otra línea fija. No exportan ni escriben archivos. El formato de las tablas es una función pura de `core/` que devuelve texto, así que **`cli/` no cambia**.
- **D-14 Configuración.** `[traces] enabled` (booleano, **por defecto `true`**); un valor inválido o un campo desconocido detiene el arranque sin repetir el valor. **Dry run con cambios reales:** con las trazas encendidas por defecto se movieron **4** pruebas de comportamiento (las que comprueban que el proveedor del bucle es la envoltura de reintentos o de conmutación) y, al implementar, una quinta (la del bucle del subagente, que comprobaba que compartía el mismo objeto de proveedor y una `RegistryView`), por debajo del umbral de unas 5 que obligaría a que fueran opcionales; la auditoría **no tiene interruptor**. Con `enabled = false` no hay envoltorios y `/trazas` lo dice.
- **D-15 Dependencia de orden y protección.** `ArgumentsTap` depende de que cada `evaluate` vaya seguido de su `permission_decided` **sin `await` entre los dos** (hoy es así en el bucle, el verificador y la rutina); las pruebas de integración con los tres emisores reales fallan si eso cambia, y las entradas del mapa se acotan (256) para que una evaluación sin evento no acumule memoria. La base de datos es ruta protegida (HU-11-01) para las herramientas de archivos y el shell: el modelo no tiene vía de escritura a estas tablas (con la limitación de coincidencia literal ya documentada).
- **D-16 Sin retención.** No hay purga ni tope de filas: es un archivo local y la rotación queda para otra historia. Queda documentado como límite conocido.
- **D-17 Sprint.** HU-05-05 es de Sprint 3 y HU-10-01 de Sprint 4 (reparto de Sprint 4 «por ratificar» en `docs/PROGRESO.md`); van juntas porque comparten tabla, redactor, composición y consulta. Divergencia con el plan de sprints: Sp4-21 («suscribir al bus») se cumple con envoltorios (D-08).

## Requisitos funcionales

- **FR-001** (HU-05-05 AC-01) Cada decisión de la política (permitida, a preguntar o denegada) deja una fila de auditoría con herramienta, argumentos, decisión y hora; incluye las de herramientas MCP.
- **FR-002** (HU-05-05 AC-01) Una aprobación completa la fila con `aprobada`, un rechazo con `rechazada`, un fallo del aprobador con `fallida`; preguntar sin aprobador es `denegada`; una denegación automática es `denegada`.
- **FR-003** (HU-05-05 AC-01) Las decisiones de la verificación de criterios y de la rutina de arranque se auditan con su origen; las de un subagente, con la sesión hija y la etiqueta de quién pide.
- **FR-004** (HU-05-05 AC-02) Los argumentos se redactan (claves con patrón conocido y valores de variables de entorno sensibles quedan sustituidos por la marca) **antes** de escribirse; el archivo SQLite leído en bytes no contiene ni el valor ni el centinela.
- **FR-005** Los argumentos se acortan después de redactar (200 por texto, 2 000 en total) y se escriben solo en ASCII; si no se pueden preparar, se guarda «sin dato» sin cambiar la decisión.
- **FR-006** La envoltura de la política devuelve siempre la decisión de dentro (incluida una excepción, que sigue subiendo) y no guarda estado más allá del mapa acotado de argumentos.
- **FR-007** Un fallo al escribir la auditoría hace fallar la entrega del evento y la herramienta no se ejecuta; una carga incompleta no hace fallar (campos «sin dato»).
- **FR-008** (HU-10-01 AC-01) Cada llamada que hace el bucle al modelo y a una herramienta deja una traza con tipo, nombre, inicio, duración, tokens, resultado y tamaño; una sesión terminada se consulta completa y en orden.
- **FR-009** Los tokens salen de `ProviderResponse.usage`; sin `usage` o con un fallo quedan nulos y se muestran como «sin dato»; nunca se inventa una cifra.
- **FR-010** Una llamada con reintentos o conmutación deja **una** traza, con el modelo activo al terminar y la duración total.
- **FR-011** (HU-10-01 regla 2) La traza no contiene contenido de mensajes, respuestas, argumentos ni resultados de herramientas; el nombre y el resultado pasan por el redactor; el archivo leído en bytes no contiene los centinelas puestos en esos contenidos.
- **FR-012** Un fallo al escribir una traza no cambia el resultado de la llamada, avisa una vez por el `WarningSink` con texto fijo y la sesión sigue; la cancelación nunca se captura y deja traza `cancelado`.
- **FR-013** Un subagente deja sus trazas bajo su sesión hija y sus decisiones bajo su sesión hija; la sesión del orquestador deja la de `delegar`.
- **FR-014** `/auditoria [id]` y `/trazas [id]` muestran la tabla corta (últimas 30 de la sesión y sus hijas, con el total), validan el id, no lanzan y no escriben nada; sin filas o con las trazas apagadas dicen una línea fija; `cli/` no cambia.
- **FR-015** El esquema v7 añade `auditoria` y `trazas` sin clave foránea; migra desde bases reales v1…v6 sin perder datos, reabrir no cambia nada y una versión desconocida se rechaza sin modificar el archivo.
- **FR-016** `[traces] enabled` (por defecto `true`) se valida; un valor inválido o un campo desconocido detiene el arranque sin repetir el valor.
- **FR-017** No cambian `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/redaction.py`, `core/verification/`, `cli/` ni `tests/doubles/`.

## Criterios de éxito

- **SC-001** Las cuatro puertas de calidad y `pytest tests/architecture` en exit 0; 100 % de líneas y ramas en los módulos nuevos.
- **SC-002** Diff vacío de los archivos protegidos.
- **SC-003** Con SQLite real y el bucle real: una sesión con una aprobación, un rechazo con motivo, una denegación automática, una herramienta MCP simulada, una ronda de verificación y la rutina de arranque deja **todas** sus decisiones en `/auditoria` con herramienta, argumentos redactados, decisión y hora.
- **SC-004** Con una clave con patrón conocido, el valor de una variable de entorno sensible y un centinela en los argumentos, el archivo de la base (y su WAL) no contiene ninguno de los tres.
- **SC-005** Con un guion de 3 llamadas al modelo (una con `usage`, una sin él, una que falla) y 2 de herramientas, `/trazas` muestra 5 filas con duración, tokens (o «sin dato») y resultado, y ningún texto de los mensajes.
- **SC-006** Con la tabla de trazas eliminada a mitad de una sesión, el turno termina igual, con un solo aviso fijo; con la tabla de auditoría eliminada, la herramienta no se ejecuta.
- **SC-007** Con los cambios por defecto la suite existente solo cambia las 60 pruebas que lista el plan (55 de esquema y API pública y 5 de «el proveedor del bucle o del subagente es la envoltura»).

## Casos límite

- Una llamada con herramienta desconocida o argumentos inválidos: no hay decisión, no hay fila de auditoría ni traza de herramienta (sigue en `events`).
- La persona no contesta (corte durante la pregunta): la fila queda `pendiente`.
- Dos rondas de verificación reutilizan `verificacion-1`: cada decisión es su fila y la resolución completa la última de esa sesión y llamada.
- Un argumento de 100 000 caracteres: queda acortado y redactado; el resto de la fila intacto.
- Un argumento con U+202E o U+200B: se guarda escapado y se ve escapado en la tabla.
- Una política que lanza una excepción: la decisión es `deny` con motivo `policy_error` (el bucle ya lo decide) y la auditoría la recoge.
- Respuesta del modelo sin `usage` (proveedor simulado o real que no lo informa): tokens «sin dato», no cero.
- Una llamada cancelada (Ctrl-C): traza `cancelado` y la cancelación sigue subiendo.
- Sesión hija borrada o inexistente: las filas siguen y se muestran sin etiqueta de subagente.
- `/auditoria` con un id inexistente o mal formado: una línea fija, sin repetir el texto escrito.
- `[traces] enabled = false`: sin envoltorios ni trazas; la auditoría sigue.
- Un servidor MCP cuyo nombre de herramienta es raro: ya lo valida el registro; la auditoría guarda el nombre tal cual lo conoce el registro, pasado por el redactor.
