# Tareas: HU-08-01 — Conexión a un servidor MCP por stdio

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Tareas del plan**: Sp4-28 (4 h ajustadas) y Sp4-29 (1,5 h)  
Cada tarea: 15–40 min, prueba primero (verla fallar por la razón esperada), después lo mínimo, después los cuatro comandos de calidad. Rutas según `estructura-carpetas-harness` (fila «código con `mcp`/procesos → `adapters/<subpaquete>/`»). Pruebas en la carpeta equivalente de `tests/`. Comando de pruebas con `--basetemp` corto (p. ej. `C:\tmp\pt34`).

**Etiquetas**: US1 = escenarios 1, 3 y 5 de la spec (conectar, cerrar limpio, entorno aislado); US2 = escenario 2 (un servidor que falla no impide arrancar). El escenario 4 (sin servidores) lo cubre T011.

**Archivos protegidos (no tocar)**: `src/harness_agent/core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/`, `docs/archivo/`. Tampoco se modifica `tests/spikes/mcp_demo_server.py`.

## Fase 1 — Dependencia

- [x] T001 [US1] Extra `mcp = ["mcp==2.3.0"]` en `pyproject.toml` (el pin de `requirements-dev.txt` ya existe); ampliar `tests/unit/test_dependency_pins.py` (el extra existe, es un pin exacto y coincide con `requirements-dev.txt`). Rojo primero: la prueba falla porque el extra no existe.

## Fase 2 — Adaptador (US1: conectar y cerrar limpio; US2: fallar sin impedir el arranque)

- [x] T002 [P] [US2] `adapters/mcp/errors.py` y `settings.py` (`McpError`, `McpConnectError(code, server)`, `McpDependencyError`, `McpServerSettings` con valores por defecto 15/60/10 s) y `tests/unit/adapters/mcp/test_errors_settings.py`: textos fijos en español por código, el mensaje no contiene el centinela de entorno/args.
- [x] T003 [P] [US1] `adapters/mcp/environment.py` (`server_environment(environ, names)`: solo lo nombrado y presente; copia; en Windows compara sin distinguir mayúsculas) y `tests/unit/adapters/mcp/test_environment.py` (las claves de API del padre no pasan; lo nombrado sí; `names` vacío → `{}`).
- [x] T004 [P] [US2] `adapters/mcp/sdk.py` (`load_sdk()` con `importlib`; `McpDependencyError` si falta) y `adapters/mcp/translate.py` (`leaf_exceptions`, `classify`, `connect_error`) con `tests/unit/adapters/mcp/test_sdk_translate.py`: grupos anidados, `FileNotFoundError`, `Connection closed`, `timed out`, desconocido; ninguno reproduce `str(error)`.
- [x] T005 [US1] `adapters/mcp/client.py` — `connect()`/`close()` con tarea dueña, usando un SDK doble inyectado (`sdk_loader`) en `tests/unit/adapters/mcp/test_client_lifecycle.py`: listo tras negociar; idempotencia; el contexto se abre y se cierra en la misma tarea (el doble lo registra); `close()` desde otra tarea; `connect()` cancelado cancela la tarea dueña; fallo de arranque → `McpConnectError`; tope de cierre.
- [x] T006 [US1] `client.py` — `call_tool`/`list_tools`/propiedades: resultados y errores fijos (`[mcp_error]`, `[mcp_timeout]`, `[mcp_server_down]`, `[mcp_not_connected]`), cancelación propagada; `tests/unit/adapters/mcp/test_client_calls.py`; el centinela `VALOR-DE-PRUEBA-123` no aparece en ningún resultado de error.
- [x] T007 [US2] `adapters/mcp/connections.py` (`connect_all`, `close_all`) y `__init__.py` con la API pública; `tests/unit/adapters/mcp/test_connections.py`: un servidor que falla avisa y el siguiente se conecta; la cancelación cierra lo abierto; `close_all` cierra aunque uno falle.

## Fase 3 — Integración con el servidor real por stdio

- [x] T008 [US1] `tests/integration/test_mcp_stdio_connection.py` con `tests/spikes/mcp_demo_server.py`: conecta y negocia (AC-01), `call_tool("add")`, `close()` y el proceso (`pid` por la herramienta `pid`) desaparece (sondeo con tope, `process_alive` del spike); cancelar `connect()`; cancelar la tarea que llama. Sin `sleep` fijo.
- [x] T009 [US1][US2] `tests/integration/mcp_env_probe_server.py` (servidor mínimo: herramienta que devuelve los nombres del entorno) + pruebas: la clave de API del padre no llega, lo nombrado sí (SC-004); stderr no llega al terminal y va al archivo de registro; comando inexistente, salida inmediata (`python -c "raise SystemExit(1)"`) y sin respuesta (`python -c "import time; time.sleep(60)"` con `startup_timeout_s` corto) → `McpConnectError` en tiempo acotado y sin proceso vivo; `crash` mientras se llama → `[mcp_server_down]`.

## Fase 4 — Configuración y composición

- [x] T010 [US1][US2] `config.py` — `McpServerConfig`, `HarnessConfig.mcp_servers`, sección `[mcp_servers.<nombre>]` (campos conocidos, validación, rechazo de campos con aspecto de clave; cambios aditivos y mínimos) y `tests/unit/test_config_mcp.py`: sin sección = comportamiento actual; válido; campo desconocido; tipo erróneo; tiempo fuera de rango; nombre de variable inválido; un nombre de campo con aspecto de clave → `SecretInConfigFileError`; los mensajes no reproducen el valor.
- [x] T011 [US1][US2] `bootstrap.py` — `compose()` crea los clientes (sin conectar; `Composition.mcp_clients`, `log_path` junto a la base de sesiones) y `run_session` conecta antes del primer aviso/`run_cli` y cierra en `finally`, con el aviso por el flujo de la sesión; `tests/integration/test_bootstrap_mcp.py`: sin servidores no importa `mcp` (SC-005); con servidor roto el arnés arranca, aviso exacto en español sin el centinela (SC-003); con el servidor de demostración conecta y cierra al terminar; Ctrl-C/cancelación cierra.

## Fase 5 — Fronteras y cierre

- [x] T012 `tests/architecture/test_mcp_boundaries.py` (a partir de `verificar-fronteras-hexagonales/assets/test_module_boundaries.py`): `adapters/mcp/` solo stdlib + API pública del núcleo + su paquete; `mcp` solo con `importlib` dentro de una función de `sdk.py`; sin `config`, `cli`, otro adaptador, entorno (`os.environ`), terminal; no captura `CancelledError` salvo para reenviarlo; `core/` no importa `mcp`; `bootstrap.py` es el único que nombra `McpStdioClient`; autopruebas con fragmentos sintéticos; ajustar `test_bootstrap_boundaries.py` (permitir `adapters.mcp`).
- [x] T013 Verificación de fronteras y calidad (`verificar-fronteras-hexagonales`): `ruff format --check .`, `ruff check .`, `mypy src tests`, `pytest`, `pytest tests/architecture`; diff de archivos protegidos vacío; lista de comprobación de `capas-y-reglas.md` contra el código.
- [x] T014 Documentación: `docs/PROGRESO.md` (fila a `En revisión`, Archivos, Evidencia, registro de cambios, observación de HU-08-01 con la decisión del usuario sobre carriles y el 6-nov, pendientes para A, B y C), `CLAUDE.md` (tabla «Qué existe hoy» y convenciones), skills `estructura-carpetas-harness` (árbol: `adapters/mcp/` ya no «planeado») y `verificar-fronteras-hexagonales` (guarda nueva) en `.claude/skills/` y `.agents/skills/`; `config.example.toml` con la sección comentada si existe.

## Tareas humanas (Claude no las marca)

- [ ] H01 Revisión cruzada (A o B).
- [ ] H02 CI remota en Ubuntu y Windows (el comportamiento de procesos hijo no se ha probado en Linux).
- [ ] H03 Acuerdo de A, B y C: `close()` queda en la clase concreta y no en el puerto (alternativa a de H1); estructura `[mcp_servers.*]` de la configuración (B).
- [ ] H04 Visto bueno del PO al servidor de demostración fuera de `tests/` (T013 de SPK-04; lo retoma HU-08-03).

## Dependencias

T001 → T002..T004 (paralelas) → T005 → T006 → T007 → T008 → T009; T010 es independiente de T005–T009 (puede ir en paralelo) y T011 necesita T007 y T010; T012 tras T011; T013 y T014 al final.
