# SPK-04 — Cliente MCP por stdio y servidor de demostración

**Estado**: propuesta del spike, pendiente de revisión cruzada y de acuerdo de A, B y C sobre los hallazgos de contratos (§7) · **Fecha**: 2026-10-25 · **Responsable**: C — Control y conexiones  
**Ficha**: [SPK-04](../04d-historias-conexiones.md#spk-04) · **Spec**: [`specs/025-mcp-stdio-client-spike/`](../../specs/025-mcp-stdio-client-spike/spec.md) · **Alimenta**: HU-08-01, HU-08-02, HU-08-03, HU-08-04, HU-08-05, HU-00-05.2

## 1. Resumen

- **AC-01 se cumple sin red**: un servidor local sin credenciales se inicia por stdio desde el cliente de prueba, se negocian capacidades (protocolo `2025-11-25`, capacidad `tools`) y se listan sus herramientas con nombre, descripción y esquema.
- **Servidor de la demostración recomendado**: el propio, `tests/spikes/mcp_demo_server.py` (hoy) y, cuando se necesite fuera de las pruebas, su versión estable bajo `examples/` o `demo/` que proponga HU-08-03 (§3). `@modelcontextprotocol/server-everything` queda como segunda opción para una demostración manual y no entra en pruebas automáticas.
- **El SDK fijado es `mcp==2.3.0` (rama 2.x)**: cambió la API respecto a 1.x (`FastMCP` → `MCPServer`, ruta de importación nueva, `mcp.Client` además de `ClientSession`). Quien escriba el adaptador debe apoyarse en 2.x; la documentación y los ejemplos de internet suelen ser de 1.x.
- **Tres hallazgos cambian el diseño de las historias** (detalle en §5 a §7): el ciclo de vida de la conexión exige abrir y cerrar en la misma tarea; los fallos llegan como `ExceptionGroup`; y `check_schema` del núcleo rechaza esquemas que son normales en servidores reales (`anyOf`, `$ref`/`$defs`, `format`).

## 2. Qué se comprobó y qué no

| Tipo | Contenido |
|---|---|
| **Comprobado en pruebas automáticas** (`tests/spikes/test_mcp_stdio_spike.py`, 28 pruebas, sin red ni claves) | Negociación y listado (AC-01); forma de los resultados y de los errores; fallo de arranque; caída a mitad de llamada; tiempo de espera por llamada y de la negociación; cancelación de una llamada y de la tarea dueña de la sesión; ausencia de proceso hijo vivo tras cada salida; compatibilidad de esquemas con `check_schema` |
| **Medido a mano, una sola vez** (2026-10-25, Windows 10, Python 3.12.10, `mcp 2.3.0`) | Arranque en frío del servidor propio; `server-everything` por `npx`; `mcp-server-time` por `uvx`; cierre de la conexión desde otra tarea (§5.3) |
| **No comprobado** | Linux (lo cubre la CI al fusionar: T011); macOS; transporte HTTP/SSE (HU-08-06); recursos, prompts y muestreo; servidores de terceros bajo carga; otras versiones del SDK; el comportamiento de un modelo real al usar herramientas MCP |

## 3. Servidor de la demostración (Sp2-55)

Criterios: local; sin credenciales; sin red en el primer arranque; determinista; arranque rápido; portable a Windows y Linux (la CI corre en ambos); herramientas que ejerciten permisos (HU-08-03) y fallos (HU-08-04, HU-00-05.2).

| Candidato | Local y sin credenciales | Sin red al arrancar | Determinista | Arranque medido | Veredicto |
|---|---|---|---|---|---|
| **Servidor propio** (`MCPServer`, lanzado con `sys.executable`) | Sí | Sí (usa el SDK ya instalado) | Sí; incluye `fail`, `slow`, `crash` y `pid` para HU-08-04 y HU-00-05.2 | 1,3–2,0 s (5 corridas: 1,33 / 1,67 / 1,46 / 1,44 / 1,95); cierre 0,15 s | **Recomendado** |
| `@modelcontextprotocol/server-everything` por `npx` | Sí | No: la primera vez descarga el paquete; un primer intento falló por red (`npm error network`) y el segundo funcionó | Parcial: 16 herramientas, varias con salida variable | 11,8 s en frío; 1,8 s con caché | Opción manual. Necesita Node |
| `mcp-server-time` por `uvx` | Sí | No (instala dependencias) | Depende de la hora | Falló dos veces en esta máquina: `uv` no pudo instalar `pywin32` («archivo en uso»); el cliente solo vio `Connection closed` | Descartado como servidor de pruebas; sin garantía en Windows |
| `server-filesystem` / `server-memory` (npm) | Sí | No (`npx`) | Escriben en disco | No medidos | Descartados: tocan el sistema de archivos y chocan con la política de áreas |

**Recomendación**: el servidor de la demostración es el propio. Es el único que cumple todos los criterios a la vez, se lanza con el mismo intérprete de la CI y tiene las herramientas que las historias de permisos y fallos necesitan. Para HU-08-03 se puede promover a un archivo no-prueba (p. ej. `examples/mcp_demo_server.py`) **sin** dependencias nuevas; hoy vive en `tests/spikes/` porque el spike no añade código fuera de las pruebas. Hace falta el visto bueno del PO (T013).

## 4. Contrato observado del SDK `mcp==2.3.0`

- **Lanzamiento**: `stdio_client(StdioServerParameters(command, args, env))` devuelve el par de flujos; `ClientSession(read, write, read_timeout_seconds=…)`; `initialize()` devuelve versión de protocolo, `server_info` y capacidades. `mcp.Client` (nuevo en 2.x) envuelve lo mismo; el spike usó la API baja porque es la que conviene al adaptador.
- **`list_tools()`** da nombre, descripción y `input_schema` (diccionario JSON Schema); también `output_schema` cuando la función declara tipo de retorno.
- **`call_tool(name, arguments, read_timeout_seconds=…)`** devuelve contenido de texto, `structured_content` y `is_error`. **Los errores de la herramienta no lanzan**: llegan con `is_error=True`: fallo interno de la herramienta (texto genérico, no revela el mensaje original), herramienta inexistente (nombra la herramienta) y argumentos inválidos.
- **Fuga de datos**: el texto de «argumentos inválidos» reproduce el valor recibido (`input_value=…`) y un enlace a documentación externa. Con el centinela `VALOR-DE-PRUEBA-123` se comprobó que sale en el texto. HU-08-03 no debe pasar ese texto tal cual al modelo ni a los eventos (el bucle ya valida argumentos antes de llamar: `[invalid_arguments]`).
- **Tiempos**: el arranque del servidor (importar el SDK) tarda 1,3–2,0 s en esta máquina. Un `read_timeout_seconds` de sesión de 1 s hace fallar la negociación; el de cada llamada se puede dar aparte. Valores propuestos en §6.
- **Stderr del hijo**: el traceback del servidor sale por el stderr del proceso hijo (en el spike se descarta al `os.devnull`); el adaptador debe decidir adónde va (no al terminal del usuario).
- **Dependencias del SDK**: llega con `litellm[mcp]==1.106.2`, que ya está fijado en `requirements-dev.txt` junto con sus dependencias directas; el adaptador no necesita cambiar `pyproject.toml` más que mover `mcp` a un extra propio (§7, H4).

## 5. Modos de fallo y ciclo de vida (alimenta HU-08-01, HU-08-04, HU-00-05.2)

### 5.1 Fallos observados

| Caso | Lo que ve el cliente | Tiempo | Proceso hijo |
|---|---|---|---|
| Comando inexistente | `FileNotFoundError` (excepción simple) | < 0,1 s | No se crea |
| El servidor sale al arrancar | `ExceptionGroup` (anidado) con `MCPError("Connection closed")` | < 0,1 s | Terminado |
| El servidor muere en mitad de una llamada | `ExceptionGroup` con `MCPError("Connection closed")` al salir del contexto | ~1,4 s (incluye el arranque) | Terminado |
| El servidor no contesta a la negociación | `ExceptionGroup` con `MCPError("Request 'initialize' timed out")` | el tiempo de espera + ~0,5 s | Terminado |
| Llamada que supera su tiempo de espera | `MCPError("Request 'tools/call' timed out")` **dentro** de la sesión; la sesión sigue usable | el tiempo de espera | Sigue vivo hasta salir; muere al salir |
| Cancelar una llamada en curso | `CancelledError`; la sesión sigue usable | inmediato | Sigue vivo hasta salir; muere al salir |
| Cancelar la tarea dueña de la sesión | `CancelledError`; el contexto cierra el proceso | ~2 s | Terminado |

Conclusiones: (1) el adaptador debe **aplanar** los grupos de excepciones (`leaf_exceptions` en `tests/spikes/mcp_probe.py` es un ejemplo) y traducirlos a un error de dominio; (2) un servidor caído no se distingue de uno que cierra por otra causa: `Connection closed` es el único dato; (3) el tiempo de espera de una llamada corta la espera del cliente; no se comprobó si el servidor detiene el trabajo (la herramienta `slow` es una función síncrona que corre en un hilo del servidor y no es interrumpible); (4) en ningún caso probado quedó un proceso huérfano.

### 5.2 Cancelación y D-01

La cancelación cooperativa de asyncio (D-01) funciona con el SDK: cancelar una llamada o la tarea dueña termina limpia y sin colgarse. Lo que se cancela es la espera del cliente; no se comprobó si el servidor interrumpe la herramienta (con el servidor de demostración no se puede decidir porque `slow` es síncrona).

### 5.3 Abrir y cerrar en tareas distintas — medido a mano, no automatizado

`stdio_client` y `ClientSession` usan alcances de cancelación de `anyio` que **deben salir en la misma tarea que los abrió**. Probado: entrar al contexto en una tarea y salir desde otra lanza `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in` y la operación completa tardó 98,8 s en terminar y no quedó ningún proceso del servidor vivo después. No se deja como prueba automática por ese tiempo (en el plan, D6 pedía probarlo: queda como medición manual). Consecuencia: el puerto `McpClient` actual (`connect()` sin `close()`) **no puede implementarse de forma simple** si la sesión se abre en `connect()` y se cierra en otra tarea (p. ej. al terminar la sesión del agente). Soluciones posibles, a decidir con A, B y C (H1): (a) una tarea de fondo dueña de la conexión que vive hasta una señal de cierre, con `connect()` esperando a que esté lista; (b) añadir `close()`/`aclose()` al puerto y garantizar que se llame desde la tarea dueña.

## 6. Esquemas frente al validador del núcleo (alimenta HU-08-02)

`check_schema` (HU-01-02) acepta lo que emite el servidor propio con parámetros simples y objetos libres, y **rechaza** lo siguiente (pruebas `TestSchemaCompatibility`):

| Esquema | Resultado de `check_schema` | Dónde aparece |
|---|---|---|
| Parámetro opcional `str \| None` | rechazado: `anyOf` no soportada | el propio SDK al declarar `title: str \| None = None` (herramienta `greet`) |
| `$ref` y `$defs` | rechazados | modelos anidados de Pydantic |
| `format` (p. ej. `uri`) | rechazado | varias herramientas reales |
| Raíz sin `type: "object"` o esquema vacío | rechazado: la raíz debe ser un objeto | servidores que no declaran `type` |
| `$schema`, `type` como lista, `additionalProperties: false` | aceptados | — |
| Objeto libre sin `additionalProperties: true` | acepta el esquema pero rechaza cualquier campo | conocido desde HU-01-02 |

Medición con un servidor real: de las 16 herramientas de `server-everything`, `check_schema` rechazó al menos dos por `x-mcp-header` y `format`. Con esto HU-08-02 debe decidir qué hacer con una herramienta cuyo esquema no valida; la regla de falla cerrada sugiere **omitir solo esa herramienta, con un aviso visible**, y no la conexión entera. Ampliar `check_schema` (A/C) es una decisión del equipo (H3).

## 7. Recomendaciones y estimaciones ajustadas por historia

Estimaciones del plan (`docs/03-plan-sprints.md`): HU-08-01 = Sp4-28 3 h + Sp4-29 1,5 h; HU-08-02 = Sp4-30 2 h + Sp4-31 1,5 h; HU-08-03 = Sp4-32 2 h + Sp4-33 1,5 h + Sp4-34 2 h; HU-08-04 = Sp4-35 1,5 h + Sp4-36 1 h; HU-00-05.2 = Sp4-26 2 h + Sp4-27 2,5 h.

| Historia | Recomendación | Ajuste propuesto |
|---|---|---|
| **HU-08-01** (conexión por stdio) | Adaptador en `adapters/mcp/` con la API baja del SDK 2.x. Dueño de la conexión = una tarea (§5.3). Tiempo de espera de la negociación **≥ 15 s** (el arranque mide 1,3–2 s, y 12 s en frío con `npx`), tiempo por llamada configurable. Stderr del hijo a un archivo o a `observability`, no al terminal. «Un servidor que no arranca no impide iniciar la sesión»: capturar `FileNotFoundError` **y** `ExceptionGroup`. Cerrar el proceso al terminar | Sp4-28 **3 h → 4 h** (ciclo de vida y aplanar errores); Sp4-29 se mantiene 1,5 h pero depende de H1 |
| **HU-08-02** (traducir herramientas) | `Tool` con `name`, `description`, `schema` = `input_schema`; el `RiskLevel` no viene de MCP: fijar `HIGH` o «pregunta» por defecto (falla cerrada, regla de HU-08-03). Validar con `check_schema`; omitir y avisar las herramientas rechazadas | Sp4-30 **2 h → 3 h** (esquemas con `anyOf`/`$ref`/`format`); Sp4-31 se mantiene |
| **HU-08-03** (permisos) | Pasar por `ProtectedPolicy` y la política igual que una nativa. El texto de `is_error` puede incluir los valores recibidos: **recortar y no publicar** en eventos; marcar el resultado como dato externo | Sp4-33 **1,5 h → 2 h** (limpieza del texto de error); Sp4-34 se mantiene con el servidor propio |
| **HU-08-04** (aislar fallos) | Cualquier excepción del cliente de un servidor se traduce a un `ToolResult` de error con etiqueta; tras `Connection closed` marcar el servidor como caído y deshabilitar **solo** sus herramientas. No reconectar solo | Sp4-35 se mantiene 1,5 h (los modos de fallo ya están documentados en §5.1); Sp4-36 se mantiene |
| **HU-08-05** (varios servidores, prefijos) | Prefijar al registrar. El registro solo admite `[A-Za-z0-9_-]{1,64}` (`_NAME_PATTERN` en `core/tools/registry.py`): `get-sum` de `server-everything` cabe, pero un nombre con punto se rechazaría y `prefijo + nombre` no puede pasar de 64 caracteres; hay que normalizar o omitir con aviso. Sin cambios de estimación | — |
| **HU-00-05.2** (A) | Se pueden escribir con el servidor propio: `crash()` da la caída a mitad de sesión y `ProbeServer("no-such-command")` el servidor inexistente. Reutilizar la forma de `tests/spikes/mcp_probe.py` | Sp4-26 y Sp4-27 se mantienen |

**Efecto total**: +2,5 h: HU-08-01 a HU-08-04 pasan de 16 h a 18,5 h y, con HU-00-05.2 (de A), de 20,5 h a 23 h. No cambia el reparto del Sprint 4, pero C debe saber que HU-08-01 y HU-08-02 son las de mayor incertidumbre.

## 8. Hallazgos que tocan contratos o configuración (sin tocarlos)

Todos requieren acuerdo de A, B y C (T012); el spike no modifica `core/interfaces/`, `core/events.py`, `core/loop.py`, `pyproject.toml` ni la CI.

- **H1 — `McpClient` sin cierre.** `connect()`, `list_tools()` y `call_tool()` no tienen `close()`/`aclose()` y el SDK exige cerrar en la misma tarea que abrió (§5.3). Hace falta o bien una tarea dueña de la conexión (sin cambiar el puerto) o añadir `close()` al puerto. Recomendación: **no cambiar el puerto** y encapsularlo en el adaptador con una tarea de fondo; si no es viable, cambio aditivo mínimo `async def close(self) -> None`.
- **H2 — Sin tiempo de espera en el puerto.** `call_tool` no recibe un límite. El adaptador debe aplicar uno por defecto (configurable) y traducir `MCPError("…timed out")` a un `ToolResult` de error. Recomendación: configuración en el adaptador; sin cambio de puerto.
- **H3 — Validador de esquemas.** Ampliar `check_schema`/`validate_arguments` con `anyOf` (al menos `T | null`), `$ref`/`$defs` internos y la tolerancia a `format` y `x-*`, o aceptar solo un subconjunto y omitir el resto con aviso. Es de A (núcleo de herramientas) y C.
- **H4 — Dependencia.** `mcp` llega hoy solo por `litellm[mcp]`. El adaptador de MCP necesita `mcp` aun si se usa otro proveedor: moverlo a un extra propio (`mcp = ["mcp==2.3.0"]`) es un cambio de `pyproject.toml`, `requirements-dev.txt` y CI que requiere acuerdo.
- **H5 — `config.py` (B).** Faltan la sección y los campos de servidores MCP (comando, argumentos, entorno, tiempos). Ya estaba anotado en `PROGRESO.md`; este spike propone: `command`, `args`, `env` (nombres de variables, no valores), `startup_timeout_s` (15 por defecto) y `call_timeout_s` (60 por defecto). El entorno de un servidor MCP no debe heredar claves del proceso padre salvo las nombradas.
- **H6 — Eventos.** No se necesita un evento nuevo: el fallo de un servidor se puede publicar como `TOOL_FINISHED` con resultado de error (existente); si HU-08-04 quisiera un evento propio (`mcp_server_down`) sería un cambio del catálogo de 17 eventos y requeriría acuerdo.

## 9. Pendiente humano

- **T010** Revisión cruzada (A o B).
- **T011** CI remota en Ubuntu y Windows: las pruebas dependen de `process_alive` (Windows por `ctypes`, POSIX por `os.kill`) y de que el proceso hijo muera tras salir del contexto; no se ha corrido en Linux.
- **T012** Acuerdo de A, B y C sobre H1–H6.
- **T013** Visto bueno del PO al servidor de la demostración.
- La medición manual de §3 y §5.3 se hizo en una sola máquina: conviene repetirla en la CI o en otra máquina si el equipo va a depender de las cifras.
