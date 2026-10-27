# Research: HU-11-03 — Pruebas y lint mediante el shell

Historia de 1 PHU: solo se resuelven las decisiones de diseño que la spec deja abiertas, a partir del código real de `main` (38b8f1d). No hubo investigación externa.

## R1. Sintaxis de la sección `## Comandos`

- **Decision**: elementos de lista en la columna 0, `- pruebas: <comando>` y `- lint: <comando>`. Debajo de cada uno puede ir una sublínea con sangría, `- tiempo: <segundos>` (o `tiempo: <segundos>`). Cada tipo aparece una vez como máximo y la sección debe tener al menos un comando. El nombre de la sección se compara igual que las demás (sin distinguir mayúsculas ni espacios sobrantes). El tiempo es un entero de 1 a 600; si falta, vale 300. El texto del comando se guarda sin los espacios exteriores, sin caracteres de control (ya los rechaza `parse_task`) y con un máximo de `MAX_FIELD_CHARS` (2 000, menor que `MAX_COMMAND_CHARS` = 8 000 del shell). Cualquier otra línea no vacía de la sección, una clave repetida, un tiempo no válido o una sección vacía → `TaskFormatError("comando_no_valido")`, con mensaje fijo.
- **Rationale**: es la misma forma que ya usan los criterios (`comando:`/`espera:` con sangría), así que el analizador reutiliza el patrón de `_CriteriaReader` y el operador no aprende otra sintaxis. Poner el tiempo en una sublínea evita confundirlo con el texto del comando (por ejemplo, `pytest --timeout 300`).
- **Alternatives considered**: tiempo en la misma línea (`pruebas: pytest (tiempo: 300)`), descartado porque el sufijo podría ser parte de un comando real; claves `tiempo_pruebas:`/`tiempo_lint:`, descartadas por duplicar claves.

## R2. Dónde vive la lógica de «comando permitido» sin que `core/` conozca el shell

- **Decision**: `core/permissions/exact_calls.py` define:
  - `AllowedCall(tool, argument, value, limit_argument, limit, default_limit)`, inmutable;
  - `ExactCallPolicy(inner, allowed, *, ask_names=())`, que implementa `PermissionPolicy`.

  Ninguno de los dos nombra el shell. `bootstrap.py` construye una `AllowedCall` por comando de la tarea con `tool=ShellTool(...).name`, `argument=COMMAND_ARGUMENT`, `limit_argument=TIMEOUT_ARGUMENT` y `default_limit=DEFAULT_SHELL_TIMEOUT_SECONDS`, todos ellos públicos en `adapters.tools`.
- **Rationale**: la regla (permitir solo lo exacto y con tope) es de negocio y va en `core/`. El conocimiento de la herramienta concreta (nombre y esquema) es del adaptador, y unir ambos es tarea de la raíz de composición. Así `core/` no depende del esquema de `ShellTool`, que puede cambiar, y la guarda puede exigir que el módulo no nombre `"shell"`.
- **Alternatives considered**: (a) añadir la regla a `DefaultPermissionPolicy` (`policy.py`), descartado porque rompe la invariante de HU-05-01 «todo ALLOW pasa por `AuthorizedArea.contains`», vigilada por `unguarded_allows`; (b) ponerla en `ProtectedPolicy`, descartado porque esa política solo puede endurecer (su guarda prohíbe `ALLOW`); (c) un adaptador que decida, descartado porque un adaptador no contiene reglas de negocio; (d) `ProtectedPolicy` ya nombra `"shell"` en `core/`, pero no se repite ese acoplamiento.

## R3. Orden de la cadena y prioridad deny > ask > allow

- **Decision**: `ProtectedPolicy(ExactCallPolicy(DefaultPermissionPolicy(registry, area, rules), allowed, ask_names=rules.ask), protected, markers)`. `ExactCallPolicy.evaluate`:
  1. pregunta a la política envuelta;
  2. `DENY` o `ALLOW` se devuelven tal cual;
  3. `ASK`: si la herramienta está en `ask_names` → `ASK`; si la llamada coincide con alguna `AllowedCall` → `ALLOW`; si no → `ASK`;
  4. cualquier otro valor o excepción → `DENY`.
- **Rationale**: `ProtectedPolicy` va fuera y deniega antes que nadie (zona protegida, HU-11-01). La lista `deny` de la configuración ya hace que la política por defecto devuelva `DENY`, que se respeta. La lista `ask` hace que devuelva `ASK`, que no se puede distinguir del `ASK` por riesgo alto, de ahí `ask_names`. Cuando HU-05-02 añada su lista de denegados (en la política por defecto o en otra envoltura exterior), su `DENY` prevalecerá sin cambiar este módulo.
- **Alternatives considered**: poner `ExactCallPolicy` fuera de `ProtectedPolicy`, descartado porque un comando declarado que nombre la base de datos se permitiría.

## R4. Coincidencia y tiempo

- **Decision**: hay coincidencia si se cumplen todas estas condiciones:
  - `call.name == tool`;
  - las claves de `call.arguments` están contenidas en `{argument, limit_argument}`;
  - `arguments[argument]` es `str` y, sin los espacios exteriores, es igual (`==`) a `value`;
  - el tiempo efectivo (`arguments.get(limit_argument, default_limit)`) es `int` o `float` (no `bool`), finito, mayor que 0 y menor o igual que `limit`.

  `AllowedCall` valida al construirse que `value` no esté vacío y que `limit` y `default_limit` sean números finitos mayores que 0. No conoce el tope de 600 s, porque es genérica: ese tope lo impone `TaskCommand`.
- **Rationale**: el bucle ya valida los argumentos con el esquema antes de preguntar a la política (`core/loop.py`, `_process_call`), pero la política repite las comprobaciones para fallar cerrada si alguien la usa sin validación. La comparación exacta deja fuera cualquier encadenamiento (`&&`, `;`, `|`) sin interpretar comandos (eso es HU-05-02).
- **Alternatives considered**: normalizar espacios internos o mayúsculas, descartado porque cambiaría el comando que se ejecuta (comillas, rutas en Linux).

## R5. Cómo sabe el agente qué comandos tiene (FR-008)

- **Decision**: la función pura `commands_notice(commands) -> str | None` (en `core/tasks/commands.py`) escribe un texto fijo en español con cada comando entre comillas invertidas y su tiempo máximo, e indica que solo esos textos exactos se ejecutan sin preguntar. `compose()` añade ese texto como segundo mensaje `SYSTEM` de `history_prefix`, tras el aviso de entorno, y solo si la tarea declara comandos.
- **Rationale**: hoy el modelo no recibe el texto de la tarea: `history_prefix` solo tiene el aviso de entorno y el prefijo estable (HU-02-01) aún no está en el bucle. Esta es la vía provisional ya usada por HU-01-04. Cuando llegue HU-02-01/HU-02-06.1, el ensamblador deberá conservar este mensaje (queda como observación).
- **Alternatives considered**: meterlo en la descripción de `ShellTool`, descartado porque la herramienta no conoce la tarea y se rompería el prefijo estable.

## R6. Proyecto de ejemplo (Sp2-48)

- **Decision**: la prueba de integración crea en `tmp_path` un proyecto mínimo con estos archivos:
  - `pytest.ini` vacío, que fija el `rootdir` y aísla el ejemplo de la configuración del repo;
  - `test_ejemplo.py`, con una prueba que pasa y otra que falla con un mensaje reconocible;
  - una prueba que imprime unos 300 000 caracteres y falla (salida larga);
  - un módulo con una importación sin usar, para el lint.

  Comandos: `python -m pytest -q -p no:cacheprovider test_ejemplo.py` y `python -m ruff check --no-cache .`. El entorno inyectado en `compose(environ=…)` antepone al `PATH` la carpeta de `sys.executable`. Se usa el shell real de la plataforma: bash en Linux, PowerShell en Windows.
- **Rationale**: no hace falta una carpeta de *fixtures* versionada nueva. Los comandos valen igual en bash y PowerShell, y el ejemplo prueba de punta a punta AC-01 (código ≠ 0 y nombre de la prueba) y AC-02 (marca de omisión, código y resumen final).
- **Alternatives considered**: `sys.executable` dentro del comando, descartado porque las comillas de una ruta con espacios difieren entre bash y PowerShell.

## R7. Persistencia de los comandos

- **Decision**: no se guardan en SQLite. Valen los del `TaskDefinition` validado que recibe `compose()`.
- **Rationale**: FR-007 (se leen al arrancar) y alcance de 1 PHU. Hoy no existe reanudar (HU-03-04).
- **Observación para HU-03-04**: al reanudar una sesión de tarea, los comandos no se recuperan, así que el shell vuelve a preguntar (falla cerrada). Si se quieren conservar, habrá que guardarlos con la tarea.

## R8. Hallazgo: `main()` no carga tareas

- `bootstrap.main()` nunca pasa `task=` a `compose()` y la CLI no tiene opción para indicar un archivo de tarea: hoy solo las pruebas y `compose()` arrancan una tarea. HU-11-03 se demuestra a través de `compose(task=…)`, igual que HU-11-01. Queda como observación en PROGRESO (para A/C: ¿qué historia añade `--tarea`?). No se resuelve aquí.

## R9. Riesgo abierto (spec, Assumptions)

- Permitir el comando de pruebas sin preguntar ejecuta código del proyecto que el agente puede haber editado (`conftest.py`, la propia prueba). No se mitiga en esta historia. Va como hallazgo abierto en las Observaciones de HU-11-03, ligado a R-21 y PD-06 (HU-IN-02).
