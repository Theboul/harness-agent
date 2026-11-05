# Guion de demostración (10 a 15 minutos)

> [← README](../README.md) · [Arquitectura implementada](arquitectura-implementada.md) · [Progreso](PROGRESO.md)

Recorrido del flujo **ticket → agente → modificación → pruebas → verificación de criterios → revisión y aprobación del diff → commit → Pull Request**, con los controles que lo hacen seguro: permisos con aprobación y rechazo con motivo, lista de denegados, solo lectura, compactación, reanudación, auditoría y trazas.

**Honestidad primero.** Todo lo que se muestra está implementado y **en revisión** según [`PROGRESO.md`](PROGRESO.md); ninguna historia está cerrada del todo mientras HU-00-01 no se ratifique. Lo que no existe se dice al final, en «Lo que NO se demuestra», y no se afirma en ningún paso. Las salidas de este guion se capturaron ejecutando el sistema real con un **modelo simulado** (el modelo es el único doble; el shell, git, los permisos, la revisión del diff y las tablas son los reales). Con un modelo real el texto del agente cambia; las pantallas del arnés no. Lo que **no pudo verificar el agente** (Pull Request real, modelo remoto, `gh`) lleva el marcador `<SALIDA_ESPERADA: verificar>`.

## Antes de empezar (no cuenta en los 10–15 minutos)

1. Instala y comprueba el arnés como dice el [README](../README.md) (`harness` sin configuración debe fallar con «No se pudo iniciar: …»).
2. Crea el repositorio de demostración con el **Anexo A** (una carpeta nueva, `demo-ticket`, con un `git init`, un archivo de tarea y un `config.toml`). Para el modelo: `ollama/qwen2.5-coder:7b` funciona pero responde despacio y se equivoca a veces (en un ensayo intentó hacer `git commit` y `git push` él mismo: justo lo que el paso 4 enseña a rechazar); un modelo remoto con clave en el entorno (`GEMINI_API_KEY`, etc.) es más rápido y cabe mejor en el tiempo.
3. Abre **dos terminales** con el entorno activado: una en `demo-ticket` para los pasos 1 a 6 y 8, y otra en una carpeta vacía con su propio `config.toml` (sin tarea) para el paso 7.
4. Ensaya **una vez completo** antes de presentar: así queda una sesión de respaldo en `demo-ticket/.harness/sessions.db` (el paso 8 la usa) y sabes cuánto tarda tu modelo. Después restaura el repositorio: `git reset --hard` y `git clean -fd` dentro de `demo-ticket`.
5. Ten a mano el **Anexo C** (la salida de respaldo) por si el modelo o la red fallan.

Los tiempos de abajo suponen respuestas del modelo de menos de 10 segundos; el ensayo con cronómetro con un modelo real es una tarea humana pendiente (no lo midió el agente).

## Pasos

### Paso 1 — Arranque con el ticket (1 min)

- Tiempo: 1 min
- Comando: `harness --tarea tarea.md`, y dentro `/ayuda` y `/model`.
- Salida esperada: el indicador `tarea> `; `/ayuda` lista los 12 comandos (con `/criterios`, que solo existe con tarea) y `/model` muestra el modelo, la ventana de contexto, el umbral de compactación y los límites de la sesión (`Límites de la sesión: 30 turnos, 600 s, 200.000 tokens`). Qué decir: «el ticket es un archivo; los criterios con comando los verifica el arnés, no el modelo».
- Plan B: si el comando no arranca, enseña el mensaje (`No se pudo iniciar: …`, salida 2) y que no hay traza; luego muestra la salida de respaldo del Anexo C y sigue desde el paso 2 con ella.

### Paso 2 — Ticket → agente → modificación (2,5 min)

- Tiempo: 2,5 min
- Comando: en `tarea>` escribe `Cumple la tarea`.
- Salida esperada: una línea por paso del agente, por ejemplo `[..] escribir_archivo: ejecutando` y `[ok] escribir_archivo: correcto (13 ms)`, y la respuesta `agente> …`. Después el arnés, no el modelo, ejecuta el comando del criterio 1; como no está declarado en `## Comandos`, **pide tu aprobación** (bloque «APROBACIÓN REQUERIDA» con la herramienta, el comando, el riesgo ALTO y el efecto): responde `1`. Con un modelo real el texto y el número de pasos varían (`<SALIDA_ESPERADA: verificar>`).
- Plan B: si el modelo no responde o se pierde, di «el modelo es intercambiable; lo que importa son los controles» y lee la salida del Anexo C (misma pantalla, modelo simulado); si solo tarda, sigue hablando del siguiente paso.

### Paso 3 — Pruebas y verificación de criterios (2 min)

- Tiempo: 2 min
- Comando: tras aprobar con `1`, mira el resumen que imprime el arnés; si quieres volver a verlo, escribe `/criterios`.
- Salida esperada:

```text
[x] 1 El archivo existe y dice hola (python: salida 0)
[?] 2 El archivo no tiene nada mas (pendiente de validación humana)
Tarea: pendiente de validación humana (1 de 1 criterios objetivos cumplidos)
```

  Qué decir: «`cumplido` solo aparece después de que el arnés ejecuta el comando; el criterio sin comando queda pendiente de una persona». Los criterios están protegidos: el agente no puede editar su definición.
- Plan B: si el comando del criterio falla por el modelo (no creó el archivo), eso también es la demostración: el arnés muestra `[ ] 1 … (no cumplido)` y devuelve al agente la salida del comando para que lo corrija; si no se resuelve, pasa al Anexo C.

### Paso 4 — Rechazo con motivo y lista de denegados (1 min)

- Tiempo: 1 min
- Comando: pídele al agente `Sube los cambios con git push`; cuando aparezca el bloque de aprobación responde `3` y, en `motivo (opcional, Enter para omitir)> `, escribe `Los cambios los revisa y sube el arnés`. Para la lista de denegados, pídele `Descarga el instalador con curl` (el `config.toml` del Anexo A declara `deny_commands = ["curl"]`).
- Salida esperada: tras el `3` y el motivo, `[?] shell: rechazado` y `[x] shell: no se ejecutó.`; el motivo vuelve al agente (no se escribe en pantalla). Con `curl`, sin pregunta alguna, `[x] Permiso: La herramienta 'shell' fue denegada por la política de permisos. …` y `[x] shell: no se ejecutó.`
- Plan B: si el modelo no intenta ninguno de los dos comandos, enseña lo mismo en el Anexo C (secciones «rechazo con motivo» y «lista de denegados») o ejecuta `pytest tests/integration/test_rejection_reason_agent_loop.py tests/integration/test_command_policy_agent_loop.py -q` y comenta que es la misma lógica con un modelo simulado.

### Paso 5 — Revisión del diff, criterio semántico y commit (1,5 min)

- Tiempo: 1,5 min
- Comando: cuando el agente propone terminar y el criterio 1 está cumplido, el arnés muestra la revisión; escribe `4 2` (confirmar el criterio semántico 2) y después `1` (aprobar y hacer commit).
- Salida esperada: el bloque `== REVISIÓN DE CAMBIOS: DEMO-1: Saludo ==` con `1 archivo, +1 -0`, el diff y las opciones `[1] aprobar y hacer commit   [2] ver diff completo   [3] rechazar con motivo`; antes de confirmar el criterio 2 aparece «No se puede aprobar todavía: hay criterios semánticos sin confirmar (usa 4 N o 5 N).»; después de `1`, `Commit hecho: <hash>`. Qué decir: «el commit lo hace el arnés, nunca el modelo, y solo con tu aprobación».
- Plan B: si no llegas a la revisión, usa la salida del Anexo C (es esta pantalla) o ejecuta `pytest tests/integration/test_review_session.py -q`.

### Paso 6 — Pull Request (1,5 min)

- Tiempo: 1,5 min
- Comando: tras el commit, el arnés ofrece subir la rama y crear el Pull Request; cada acción pide su confirmación (`1` sí, `2` no).
- Salida esperada: con `gh` instalado y con sesión, un remoto `origin` y la rama de trabajo: dos preguntas (subir y crear, esta última con título y descripción) y el enlace del PR (`<SALIDA_ESPERADA: verificar>`; **no verificado por el agente**). Sin `gh` (verificado): `` `gh` (la CLI de GitHub) no está instalado o no se puede ejecutar: no se subió nada. La rama quedó commiteada. `` y el texto del Pull Request listo para copiar, con el objetivo, el commit, los archivos y cada criterio con una línea de evidencia, más `Para subir la rama a mano: git push -u origin <rama>`.
- Plan B: si no hay red, remoto ni `gh`, enseña justamente el texto listo para copiar (es la salida de respaldo del arnés) y di que nada sale del equipo sin confirmación; la lógica se ejecuta con `pytest tests/integration/test_pull_request_session.py -q`.

### Paso 7 — Controles de sesión: plan, compactar, sesiones y reanudar (2,5 min)

- Tiempo: 2,5 min
- Comando: en la **segunda terminal** (sin tarea): haz cuatro peticiones largas, y luego `/sesiones`, `/compactar`, `/plan`, `/nueva`, `/sesiones` y `/reanudar <id>` con el identificador de la primera sesión.
- Salida esperada: `/sesiones` lista las sesiones con la actual marcada con `*`; `/compactar` imprime `Contexto compactado: ~antes → ~después tokens (historial original conservado).`; `/plan` responde `Modo planificación: modelo …, solo lectura (se deniega toda escritura). Vuelve con /implementar.`; `/nueva` imprime `Sesión nueva: <id>. La anterior sigue guardada; reanúdala con /reanudar <id>.`; `/reanudar <id>` imprime `Sesión reanudada: N mensajes en el contexto (con resumen).`. Con una tarea activa `/nueva` y `/reanudar` no están disponibles (por eso hace falta la segunda terminal).
- Plan B: si el modelo falla, ejecuta `pytest tests/integration/test_session_control_commands.py -q`, que recorre estos mismos comandos con un modelo simulado, o lee las secciones «sesiones» del Anexo C.

### Paso 8 — Auditoría y trazas (1 min)

- Tiempo: 1 min
- Comando: `/auditoria` y `/trazas` en la sesión de los pasos 1 a 6.
- Salida esperada: una tabla de decisiones (`hora  quién  herramienta  argumentos  resolución`, con `aprobada`, `rechazada`, `denegada` o `permitida`; los argumentos van sin claves y acortados) y una tabla de llamadas con duración, tokens (o `sin dato`) y resultado. Qué decir: «la auditoría no se puede apagar: si una decisión no se puede registrar, la herramienta no se ejecuta».
- Plan B: si la sesión se perdió, ejecuta `pytest tests/integration/test_audit_agent_loop.py -q` o enseña la tabla de la sección «lista de denegados» del Anexo C.

### Paso 9 — Cierre y lo que no se demuestra (0,75 min)

- Tiempo: 0,75 min
- Comando: ninguno; escribe `/salir` y muestra la sección «Lo que NO se demuestra» de este guion.
- Salida esperada: `Sesión terminada.` y, en la carpeta, el archivo `progreso-DEMO-1.md` con el punto de control del ticket (sin comandos ni evidencias). Qué decir: lo que sigue en «Lo que NO se demuestra».
- Plan B: si no hay tiempo, lee solo los tres primeros puntos de la sección final; son los que el público más suele suponer terminados.

**Suma de los pasos obligatorios: 13,75 minutos.**

## Tramos opcionales (no suman; solo si sobra tiempo)

### Opcional 1 — Conmutación por fallo entre modelos (1,5 min)

- Tiempo: 1,5 min
- Comando: con `[models]` y `[failover]` en `config.toml` (ver el README), provoca un fallo del modelo principal (apaga el servidor del primero) y haz una petición.
- Salida esperada: una línea `Cambio de modelo por fallo: A a B (motivo).` y el turno termina con el modelo de respaldo (`<SALIDA_ESPERADA: verificar>`; **no verificado por el agente**: necesita provocar un fallo real del proveedor).
- Plan B: `pytest tests/integration/test_failover_agent_loop.py -q`.

### Opcional 2 — Memoria entre sesiones (1,5 min)

- Tiempo: 1,5 min
- Comando: con `[memory]` activada (ver el README), pide `Recuerda que prefiero respuestas breves`, aprueba la herramienta `memoria` con `1`, ejecuta `/nueva` y pregunta qué preferencia tienes guardada.
- Salida esperada: la aprobación de la herramienta `memoria` (riesgo ALTO, cada llamada pregunta) y, al abrir la sesión nueva, el aviso «Memoria: se cargaron N entradas …» (`<SALIDA_ESPERADA: verificar>`; **no verificado por el agente**).
- Plan B: `pytest tests/integration/test_persistent_memory_agent_loop.py -q`.

## Lo que NO se demuestra

Nada de esto se ofrece como funcionando; sigue `Pendiente` en [`PROGRESO.md`](PROGRESO.md) o tiene reservas que hay que decir en voz alta.

**Criterios de demostración del Sprint 3 que se cumplen a medias**

| Criterio | Qué existe y qué no |
|---|---|
| Un criterio semántico recibe el informe del subagente verificador | **No se demuestra el informe del subagente:** HU-11-04.2, HU-09-06 y HU-09-02 están Pendiente. Sí existe que el criterio semántico queda pendiente hasta que la persona lo confirma (`4 N`, HU-11-05) |
| Tras tres compactaciones el agente respeta el rechazo con motivo | **No se afirma:** las decisiones acumuladas (HU-02-06.2) están Pendiente. Sí se conserva el objetivo, las reglas y los criterios (contexto esencial, HU-02-06.1) y existe `/compactar` |
| Segundo proveedor por configuración | HU-07-03 está Pendiente; la conmutación existe con alias de `[models]` (HU-06-06, HU-07-05) |

**Historias Pendiente del Sprint 3 y 4** (no existen todavía): HU-01-07 y HU-01-08 (varias llamadas por turno, llamadas repetidas), HU-03-05 (consumo y costo), HU-03-03 (listado con título y fecha relativa; `/sesiones` existe, la historia sigue pendiente), HU-05-06 (permisos por archivo), HU-06-03 (interrumpir sin perder la sesión), HU-09-02 y HU-09-05 (perfiles de subagente, propagación de errores), HU-11-07 (una sesión por ticket con su propio árbol de trabajo), HU-04-03, HU-04-04 y HU-04-05 (memoria estructurada, inspección y edición, negarse a guardar secretos).

**Backlog diferido** (Pendiente): HU-02-05, HU-02-07, HU-03-06, HU-07-06 (respuesta en streaming), HU-08-05, HU-08-06, HU-09-07, HU-10-03, HU-IN-01, HU-IN-02, HU-IN-03 y HU-IN-04.

**Implementado, en revisión, con reservas que se dicen en voz alta**

- El shell no está aislado (decisión PD-06 pendiente del Product Owner): las pruebas y los comandos de la tarea ejecutan código que el agente puede haber editado (HU-01-04, HU-11-03).
- La tabla de reglas de git y un supuesto están pendientes del Product Owner (HU-11-02); la verificación de criterios obliga «no avanzar mientras falle» por instrucción al modelo, no por bloqueo (HU-11-04.1, HU-11-08.2).
- Una confirmación de criterio no se invalida si el agente cambia el código después (HU-11-05); el Pull Request real necesita `gh`, red y un remoto y **no lo verificó el agente** (HU-11-06).
- El adaptador de modelos reales no tiene aún la prueba del equipo con un modelo real registrada (HU-07-02).
- Subagentes (HU-09-01, HU-09-03, HU-09-04), conmutación (HU-07-05) y memoria (HU-04-01, HU-04-02) están apagados por defecto y sin perfiles de subagente; la memoria no se inspecciona ni se edita.
- MCP: ver el Anexo B; no reconecta un servidor caído (decisión pendiente del Product Owner).
- Comandos de sesión: `/compactar` muestra la estimación «antes → después» (heurística, no el recuento del proveedor) y no distingue «nada que resumir» de «falló».
- La ratificación técnica de los contratos (HU-00-01) sigue pendiente de A, B y C: por eso ninguna historia está cerrada del todo.

## Anexo A — Crear el repositorio de demostración

Una carpeta nueva fuera del clon de `harness-agent`, con el entorno de `harness-agent` activado. Ajusta `model` a tu proveedor (para uno con clave, define antes su variable de entorno, ver el README).

```powershell
mkdir demo-ticket
cd demo-ticket
git init
git config user.name "Demo"
git config user.email "demo@example.org"
Set-Content -Encoding ascii .gitignore @(".harness/", "config.toml", ".env", "progreso-*.md")
Set-Content -Encoding ascii config.toml @('model = "ollama/qwen2.5-coder:7b"', '', '[paths]', 'workspace_root = "."', '', '[permissions]', 'deny_commands = ["curl"]')
Set-Content -Encoding ascii tarea.md @'
# DEMO-1: Saludo

## Objetivo
Crear el archivo saludo.txt con la palabra hola.

## Reglas
- No uses git: el arnes hace el commit despues de que revises el diff.

## Criterios
- El archivo existe y dice hola
  - comando: python -c "assert open('saludo.txt').read().strip() == 'hola'"
  - espera: codigo_salida == 0
- El archivo no tiene nada mas
'@
git add .gitignore tarea.md
git commit -m "inicial"
```

```bash
mkdir demo-ticket
cd demo-ticket
git init
git config user.name "Demo"
git config user.email "demo@example.org"
printf '.harness/\nconfig.toml\n.env\nprogreso-*.md\n' > .gitignore
printf 'model = "ollama/qwen2.5-coder:7b"\n\n[paths]\nworkspace_root = "."\n\n[permissions]\ndeny_commands = ["curl"]\n' > config.toml
cat > tarea.md <<'EOF'
# DEMO-1: Saludo

## Objetivo
Crear el archivo saludo.txt con la palabra hola.

## Reglas
- No uses git: el arnes hace el commit despues de que revises el diff.

## Criterios
- El archivo existe y dice hola
  - comando: python -c "assert open('saludo.txt').read().strip() == 'hola'"
  - espera: codigo_salida == 0
- El archivo no tiene nada mas
EOF
git add .gitignore tarea.md
git commit -m "inicial"
```

Para el paso 6 completo hace falta un remoto: con `gh` instalado y con sesión iniciada, `gh repo create demo-ticket-<TU_USUARIO> --private --source . --remote origin --push` lo crea (**no verificado por el agente**). Sin remoto, el paso 6 enseña el texto listo para copiar.

## Anexo B — Guion corto de MCP (3 min, aparte de los 10–15)

MCP por stdio está en `main` (HU-08-01 a HU-08-04), en revisión. Necesita el extra `mcp` (`pip install -e ".[mcp]"` en el clon de `harness-agent`) y, en el `config.toml` de una carpeta de trabajo, el servidor de demostración del repositorio:

```toml
[mcp_servers.demo]
command = "python"
args = ["<RUTA_DE_HARNESS>/tests/spikes/mcp_demo_server.py"]
```

- Tiempo: 3 min.
- Qué se ve (capturado con un modelo simulado que pide `add` con 2 y 3): al arrancar, el aviso `El servidor MCP 'demo' ofrece la herramienta 'greet', pero se omitió: su nombre o su esquema no son válidos para el arnés.` (el registro solo acepta esquemas que sabe validar y omite la herramienta, no el servidor); después, la petición del agente muestra el bloque de aprobación con la herramienta `add`, sus argumentos (`a: 2`, `b: 3`) y el riesgo ALTO (**toda herramienta MCP pregunta siempre**, sin excepción); con `1`, `[ok] add: correcto (289 ms)` y la respuesta del agente.
- Plan B: `pytest tests/integration/test_mcp_permissions_agent_loop.py tests/integration/test_mcp_failure_isolation.py -q` (permisos y aislamiento de fallos con el servidor de demostración).
- Reserva: si el servidor cae, sus herramientas responden con un error y la sesión sigue, pero no se reconecta (decisión pendiente del Product Owner); la caída a mitad de sesión se prueba en `pytest tests/integration/test_mcp_session_fault_tolerance.py -q`, no se verificó a mano.

## Anexo C — Salida de respaldo (modelo simulado, resto real)

Capturada ejecutando `harness --tarea tarea.md` en el repositorio del Anexo A con un modelo guionizado que escribe `saludo.txt`; las entradas fueron `Cumple la tarea`, `1`, `4 2`, `1` y `/salir`. El hash del commit y los milisegundos cambian en cada ejecución. Si el modelo falla, léela como si fuera la pantalla.

```text
tarea>   [..] escribir_archivo: ejecutando
  [ok] escribir_archivo: correcto (13 ms)
agente> Listo: creé saludo.txt con la palabra hola.

============================================================
 APROBACIÓN REQUERIDA
------------------------------------------------------------
 El agente quiere ejecutar un comando:
     python -c "assert open('saludo.txt').read().strip() == 'hola'"
 Herramienta: shell
 Riesgo:      ALTO
 Efecto:      Ejecuta un comando en tu equipo, empezando en
              la raíz del área de trabajo. Puede cambiar
              archivos o el sistema.
------------------------------------------------------------
 [1] aprobar una vez   [2] aprobar para la sesión   [3] rechazar
opción>   [?] shell: aprobado una vez
[x] 1 El archivo existe y dice hola (python: salida 0)
[?] 2 El archivo no tiene nada mas (pendiente de validación humana)
Tarea: pendiente de validación humana (1 de 1 criterios objetivos cumplidos)

== REVISIÓN DE CAMBIOS: DEMO-1: Saludo ==
1 archivo, +1 -0
  nuevo      +1 -0      saludo.txt
Criterios objetivos: 1 de 1 cumplidos
[x] 1 El archivo existe y dice hola (cumplido)
[?] 2 El archivo no tiene nada mas (pendiente de validación humana)
-- diff --
diff --git a/saludo.txt b/saludo.txt
new file mode 100644
index 0000000..5c1b149
--- /dev/null
+++ b/saludo.txt
@@ -0,0 +1 @@
+hola
No se puede aprobar todavía: hay criterios semánticos sin confirmar (usa 4 N o 5 N).
 [1] aprobar y hacer commit   [2] ver diff completo   [3] rechazar con motivo
 [4 N] confirmar criterio N   [5 N] rechazar criterio N   (/salir: sin decidir)
opción> [x] 2 El archivo no tiene nada mas (confirmado por la persona)
Tarea: verificada (1 de 1 criterios objetivos cumplidos)

== REVISIÓN DE CAMBIOS: DEMO-1: Saludo ==
1 archivo, +1 -0
  nuevo      +1 -0      saludo.txt
Criterios objetivos: 1 de 1 cumplidos
[x] 1 El archivo existe y dice hola (cumplido)
[x] 2 El archivo no tiene nada mas (confirmado por la persona)
 [1] aprobar y hacer commit   [2] ver diff completo   [3] rechazar con motivo
 [4 N] confirmar criterio N   [5 N] rechazar criterio N   (/salir: sin decidir)
opción> Commit hecho: 31b23c8
`gh` (la CLI de GitHub) no está instalado o no se puede ejecutar: no se subió nada. La rama quedó commiteada.
Texto del Pull Request (para copiarlo):
Título: DEMO-1: Saludo
Descripción:
## Objetivo
Crear el archivo saludo.txt con la palabra hola.

## Cambios
Commit `31b23c8`: 1 archivo, +1 −0.

- `saludo.txt` (nuevo, +1 −0)

## Criterios de aceptación
- [x] El archivo existe y dice hola — verificado. Evidencia: `Código de salida: 0 (sin salida)`
- [x] El archivo no tiene nada mas — confirmado por la persona
Para subir la rama a mano: git push -u origin <rama>
tarea> Sesión terminada.
```

**Sesiones: compactar, nueva, sesiones y reanudar** (sesión sin tarea; cuatro peticiones largas):

```text
tarea> agente> Apartado 1 resumido.
tarea> agente> Apartado 2 resumido.
tarea> agente> Apartado 3 resumido.
tarea> agente> Apartado 4 resumido.
tarea> Sesiones guardadas (la más reciente primero):
* f445c0d1-749d-4fe4-9c60-0d086c5bbe6d  2026-11-05 05:37 UTC  active  openai/modelo-de-prueba  -
Para continuar una: /reanudar <id>.
tarea>   [~] Contexto compactado: 3 eventos resumidos.
Contexto compactado: ~2.142 → ~1.867 tokens (historial original conservado).
tarea> Modelo: openai/modelo-de-prueba
Ventana de contexto: 32.000 tokens
Compactación automática desde: 25.600 tokens
Límites de la sesión: 30 turnos, 600 s, 200.000 tokens
Máximo por respuesta del modelo: 4.096 tokens
tarea> Sin registros de auditoría para esa sesión.
tarea> Trazas de la sesión f445c0d1-749d-4fe4-9c60-0d086c5bbe6d (5 llamadas).
hora      sesión  tipo    nombre                   duración  tokens    resultado
05:37:32  -       modelo  openai/modelo-de-prueba  0 ms      sin dato  ok
05:37:32  -       modelo  openai/modelo-de-prueba  0 ms      sin dato  ok
05:37:32  -       modelo  openai/modelo-de-prueba  0 ms      sin dato  ok
05:37:32  -       modelo  openai/modelo-de-prueba  0 ms      sin dato  ok
05:37:32  -       modelo  openai/modelo-de-prueba  0 ms      sin dato  ok
tarea> Sesión nueva: c87cdd48-06d5-48da-8181-bfa3bbb4aaaa. La anterior sigue guardada; reanúdala con /reanudar <id>.
tarea> Sesión terminada.
```

Y, en una ejecución posterior con la misma base de datos:

```text
tarea> Sesiones guardadas (la más reciente primero):
* 4773a4fd-c898-40e1-ac44-29c74f8e207f  2026-11-05 05:37 UTC  active  openai/modelo-de-prueba  -
  c87cdd48-06d5-48da-8181-bfa3bbb4aaaa  2026-11-05 05:37 UTC  active  openai/modelo-de-prueba  -
  f445c0d1-749d-4fe4-9c60-0d086c5bbe6d  2026-11-05 05:37 UTC  active  openai/modelo-de-prueba  -
Para continuar una: /reanudar <id>.
tarea> Sesión reanudada: 6 mensajes en el contexto (con resumen).
tarea> agente> Apartado 5 resumido.
tarea> Sesión terminada.
```

**Rechazo con motivo** (se pidió `git push origin main`, se respondió `3` y se escribió un motivo):

```text
tarea>   [..] shell: ejecutando

============================================================
 APROBACIÓN REQUERIDA
------------------------------------------------------------
 El agente quiere ejecutar un comando:
     git push origin main
 Herramienta: shell
 Riesgo:      ALTO
 Efecto:      Ejecuta un comando en tu equipo, empezando en
              la raíz del área de trabajo. Puede cambiar
              archivos o el sistema.
------------------------------------------------------------
 [1] aprobar una vez   [2] aprobar para la sesión   [3] rechazar
opción> motivo (opcional, Enter para omitir)>   [?] shell: rechazado
  [x] shell: no se ejecutó.
agente> De acuerdo, no subo nada.
tarea> Sesión terminada.
```

**Solo lectura** (`harness --solo-lectura`, se pidió escribir un archivo):

```text
Modo de solo lectura activo: se deniegan las escrituras, los comandos que no sean lecturas de git y las herramientas desconocidas.
tarea>   [..] escribir_archivo: ejecutando
  [x] Permiso: La herramienta 'escribir_archivo' fue denegada por la política de permisos. Sugerencia: Si debe permitirse, ajusta la política de permisos; mientras esté denegada el agente no la ejecutará.
  [x] escribir_archivo: no se ejecutó.
agente> No puedo escribir en solo lectura.
tarea> Sesión terminada.
```

**Lista de denegados y auditoría** (con `deny_commands = ["curl"]` en `[permissions]`; se pidió `curl …` y después `git status`):

```text
tarea>   [..] shell: ejecutando
  [x] Permiso: La herramienta 'shell' fue denegada por la política de permisos. Sugerencia: Si debe permitirse, ajusta la política de permisos; mientras esté denegada el agente no la ejecutará.
  [x] shell: no se ejecutó.
agente> No puedo descargar.
tarea>   [..] shell: ejecutando
  [ok] shell: correcto (269 ms)
agente> Sin cambios.
tarea> Auditoría de la sesión fcde56b6-6fee-4c2a-a38a-782c1e88f95e (2 registros).
hora      quién   herramienta  argumentos                                          resolución
05:40:58  agente  shell        {"command": "curl https://example.org/descarga....  denegada
05:40:58  agente  shell        {"command": "git status"}                           permitida
tarea> Sesión terminada.
```

**Herramienta MCP** (servidor de demostración; extracto):

```text
El servidor MCP 'demo' ofrece la herramienta 'greet', pero se omitió: su nombre o su esquema no son válidos para el arnés.
tarea>   [..] add: ejecutando

============================================================
 APROBACIÓN REQUERIDA
------------------------------------------------------------
 El agente quiere usar la herramienta 'add'.
 Herramienta: add
 Argumentos:
   a: 2
   b: 3
 Riesgo:      ALTO
 Efecto:      Add two integers.
------------------------------------------------------------
 [1] aprobar una vez   [2] aprobar para la sesión   [3] rechazar
opción>   [?] add: aprobado una vez
  [ok] add: correcto (92 ms)
agente> La suma es 5.
```
