# Investigación: HU-08-01

Sin marcadores NEEDS CLARIFICATION. Decisiones de apoyo (las siete del usuario están en `spec.md`).

| # | Decisión | Motivo | Alternativas descartadas |
|---|---|---|---|
| D1 | Tarea de fondo dueña de la conexión | `stdio_client` y `ClientSession` deben cerrarse en la misma tarea anyio (SPK-04 §5.3: 98,8 s y `RuntimeError` si no) | `close()` en el puerto (protegido); `AsyncExitStack` repartido entre tareas |
| D2 | `asyncio.Event` de parada + `asyncio.Future` de «listo» | Stdlib; la tarea dueña es una `asyncio.Task`, anyio corre sobre asyncio | Primitivas de anyio (dependencia directa) |
| D3 | Conectar/cerrar en `run_session`, construir en `compose()` | `compose()` es síncrono y se ejecuta fuera del bucle; la tarea dueña debe vivir en el bucle de la sesión | Conectar en `compose()` con `asyncio.run` (otro bucle: la tarea moriría) |
| D4 | Entorno: solo variables nombradas; base = lista segura del SDK | El SDK ya aplica `get_default_environment() \| env`; no se hereda nada más, así que las claves de API del padre no llegan (H5) | Copiar `os.environ` menos las claves (como el shell): lista negra, falla abierta |
| D5 | `env` de la config es una lista de **nombres** | Sin valores ni secretos en `config.toml`; un nombre con `key/token/…` como valor no dispara el detector porque el detector mira nombres de campo | Tabla `env = {A = "b"}`: valores en el archivo |
| D6 | Estructura `[mcp_servers.<nombre>]` | Un servidor por tabla; HU-08-05 solo añade más tablas | Lista de tablas `[[mcp_servers]]` (el recorrido de nombres de `config.py` no distingue campos por servidor) |
| D7 | Errores de llamada: texto fijo | El texto de «argumentos inválidos» reproduce el valor (SPK-04 §4) | Recortarlo (sigue filtrando) |
| D8 | Aviso por `WarningSink` | Ya es el canal de avisos de la composición (HU-02-03); sin evento nuevo (H6) | Evento `mcp_server_down` (catálogo protegido) |
| D9 | stderr a `mcp-<nombre>.log` junto a la base de sesiones | La carpeta ya está protegida contra las herramientas del agente (HU-11-01) y está en `.gitignore` | Terminal del usuario (prohibido por la decisión 5); siempre `devnull` (se pierde diagnóstico) |
| D10 | Cierre con tope de 10 s y `cancel()` de respaldo | SPK-04: cierre normal 0,15 s, cancelación ~2 s | Esperar sin tope (colgaría el arnés al salir) |
| D11 | Pruebas con un doble del SDK (unidad) y con el servidor real (integración) | Las ramas de error sin procesos son rápidas y deterministas; el contrato real se prueba una vez | Solo integración (lenta, no cubre todas las ramas) |
| D12 | Esperas por sondeo con tope, no `sleep` fijo | Fiabilidad en Windows y Linux | `time.sleep` |
