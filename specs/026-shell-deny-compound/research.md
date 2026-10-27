# Research: HU-05-02 — Lista de denegados y análisis de comandos compuestos

Historia de 2 PHU. Las decisiones salen del código real de `origin/main` (e60d101, que ya incluye HU-11-03) y de las restricciones del revisor. No hubo investigación externa salvo la sintaxis de bash y PowerShell, que se resume aquí.

## R1. Dónde vive cada pieza (restricciones 1, 2 y 8)

- **Decision**:
  - El analizador de comandos y la política nueva van en `core/permissions/`, en tres módulos puros, solo con la biblioteca estándar:
    - `command_parser.py`: separa y entiende un comando según su dialecto;
    - `command_rules.py`: reglas de denegación compiladas desde texto y lista en uso;
    - `command_policy.py`: `CommandPolicy`, que envuelve a otra política.
  - La **lista base** sigue en `adapters/system/denied_commands.py`. Allí se amplía con las entradas nuevas y con dos tablas de datos por intérprete: los alias de programa (PowerShell) y los sinónimos de opción (bash, por ejemplo `--recursive` = `-r` para `rm`).
  - `core/` no importa `adapters/`. `bootstrap.py` lee la lista del intérprete elegido y las entradas de `[permissions] deny_commands`, las compila con la API pública del núcleo y las inyecta a la política junto con el nombre del dialecto (`bash` o `powershell`) y los nombres de la herramienta y de su argumento.
- **Rationale**: la regla (qué se deniega y cómo se analiza) es de negocio y va en `core/`. Qué comandos son peligrosos en cada plataforma es un dato propio de cada sistema, y ya vivía en `adapters/system/` desde HU-01-04: se amplía sin duplicarlo. La política recibe todo por constructor, igual que `ExactCallPolicy` (HU-11-03), así que no conoce la herramienta `shell` por nombre.
- **Alternatives considered**: mover la lista a `core/`, descartado por la restricción 2 y porque rompería las pruebas de HU-01-04; hacer que el núcleo importe la lista, descartado porque `core/` no importa `adapters/`.

## R2. Formato de una regla: el propio texto del comando

- **Decision**: cada entrada sigue siendo `DeniedCommand(pattern, reason)`, como en HU-01-04 (sus pruebas no cambian). `pattern` se **compila** con el mismo analizador que los comandos del agente, de modo que la base y `deny_commands` usan una sola sintaxis. Según los tokens del patrón, la regla resulta de un tipo:

  | Patrón | Tipo | Coincide con una parte cuando… |
  |---|---|---|
  | una palabra (`shutdown`, `mkfs`, `Format-Volume`) | **programa** | el programa de la parte es esa palabra o empieza por `palabra.` (`mkfs.ext4`) |
  | programa + opciones + objetivo raíz (`rm -rf /`, `chmod -R 777 /`, `Remove-Item -Recurse -Force C:\`) | **objetivo** | mismo programa, contiene las opciones de la regla (en cualquier orden y combinación) y **algún** argumento posicional es un objetivo completo (R6) |
  | programa + argumento que termina en `=` (`dd if=`) | **prefijo** | mismo programa y algún argumento empieza por ese prefijo |
  | programa + palabras (`reg delete`, `terraform destroy`) | **subcomando** | mismo programa y esas palabras aparecen como primeros argumentos posicionales, en orden |
  | `> destino` (`> /dev/sd`) | **redirección** | algún destino de redirección de la parte empieza por ese texto |
  | texto que el analizador no entiende (`:(){ :\|:& };:`) | **literal** | el texto completo, sin espacios, contiene el patrón sin espacios. Solo se admite en la lista base; en `deny_commands` es error de arranque |

- **Rationale**: una sola gramática para los patrones y para los comandos evita una segunda mini-sintaxis. La configuración del usuario (`deny_commands = ["terraform destroy"]`) se escribe como el comando real. La bomba de procesos de HU-01-04 no se puede expresar como programa (su forma ya es «no entendida» y se preguntaría); se conserva como regla literal para no perder una entrada de la base.
- **Alternatives considered**: mantener la búsqueda literal de HU-01-04, descartada porque produce los falsos positivos que la clarificación prohíbe (`cat shutdown.log`, `rm -rf /tmp/build`); un formato estructurado (programa, opciones, objetivo) para `deny_commands`, descartado por ser más difícil de escribir en `config.toml`.

## R3. Analizador manual por caracteres, sin `shlex` (restricción 9)

- **Decision**: un analizador propio que recorre el texto carácter a carácter, con un estado por dialecto. Fija tres cosas:
  - **Comillas**:
    - bash: `'…'` literal, `"…"` con `\` y sustituciones dentro;
    - PowerShell: `'…'` literal (`''` es una comilla), `"…"` con `` ` `` como escape y `$( … )` dentro.
  - **Separadores**:
    - bash: `&&`, `||`, `;`, `|`, `|&`, `&` y salto de línea;
    - PowerShell: `;`, `|`, `&&`, `||` y salto de línea.
  - **Redirecciones**:
    - bash: `>`, `>>`, `<`, `2>`, `2>>`, `&>`, `>&`, `2>&1`;
    - PowerShell: `>`, `>>`, `2>`, `*>`, `3>`…, `2>&1`.

  Produce una lista de partes y una marca «entendido» por cada construcción. Se puede cumplir FR-004, FR-005, FR-005a y FR-005b con esto:
  - los separadores dentro de comillas no separan;
  - las sustituciones `$( … )` y `` ` … ` `` se extraen con su anidamiento (contando paréntesis y respetando comillas interiores) y se analizan recursivamente como texto ejecutable;
  - el texto de `-c` / `-Command` / `/c` es el siguiente token, ya sin comillas, y se analiza con el dialecto que corresponde (R5);
  - las redirecciones se separan de los argumentos y su destino se guarda aparte.
- **Rationale**: `shlex` solo conoce la sintaxis POSIX, no distingue un `;` de un `&&`, no informa de las sustituciones (las deja como texto) y con `punctuation_chars` sigue sin reconocer `$( … )`, comillas invertidas ni here-documents. Para PowerShell no sirve. Usarlo solo en bash dejaría dos implementaciones con reglas distintas y no evitaría escribir el detector de sustituciones. Un analizador único y pequeño con dos tablas de dialecto es más fácil de probar al 100 % y de auditar.
- **Alternatives considered**: `shlex` en bash más un analizador propio para PowerShell, descartado por lo anterior; expresiones regulares sobre el texto completo, descartadas porque no manejan comillas anidadas.

## R4. Qué se «entiende» y qué no (FR-007, AC-04)

- **Decision**: el analizador marca **no entendido** ante:
  - comillas sin cerrar o una barra `\` al final de línea (continuación);
  - here-documents (`<<`, `<<<`);
  - comentarios (`#` al inicio de una palabra; `<# … #>` en PowerShell);
  - grupos y subshells (`(`, `)`, `{`, `}` fuera de comillas);
  - sustitución de procesos (`<( … )`, `>( … )`);
  - una parte vacía (`a ;; b`, `| b`, `a &&` sin nada detrás);
  - una variable o expansión en cualquier token (`$X`, `${X}`, `$env:X`, `~user`), excepto `~` y `~/…` solos, que se tratan como el hogar;
  - en PowerShell, `& algo` (operador de llamada) y `.` al inicio.

  Además, siempre son **no entendidos pero analizables**:
  - las sustituciones `$( … )` y `` ` … ` ``;
  - `bash|sh|zsh -c TEXTO`;
  - `pwsh|powershell -Command TEXTO` (también `-c`);
  - `cmd /c TEXTO`.

  Su texto interior se analiza para buscar denegados, y el resultado global nunca baja de «preguntar».

  Y son **no entendidos y no analizables**:
  - `eval`, `source`, `.`, `xargs`, `exec` con argumentos de otro intérprete;
  - `-EncodedCommand` (`-e`, `-enc`), `Invoke-Expression`, `iex`, `Start-Process`, `Invoke-Command`;
  - una sustitución cuyo texto interior no se entiende.

  Cualquier excepción del analizador se convierte en «no entendido» dentro de `CommandPolicy` (restricción 4).
- **Rationale**: es la lista de Edge Cases de la spec. Basta con marcar; no hace falta interpretar.

## R5. Envoltorios y otros intérpretes

- **Decision**:
  - Antes de identificar el programa se quitan los envoltorios `sudo` (y sus opciones `-u X`, `-E`…), `env` (con `VAR=x` y `-i`), `nohup`, `time`, `nice` (`-n N`), `command`, `builtin`, `exec` sin `-c`, y las asignaciones iniciales `VAR=x` (bash).
  - El programa se normaliza quitando la carpeta (`/` o `\`) y la extensión (`.exe`, `.cmd`, `.bat`, `.com`, `.ps1`); en PowerShell, además, en minúsculas y resolviendo los alias de la tabla (R1).
  - El texto de `bash -c` se analiza con el dialecto bash. El de `pwsh -Command`, con PowerShell. El de `cmd /c` se separa solo por `&`, `&&`, `||`, `|` y su programa se compara con las listas de **los dos** dialectos (cmd no tiene lista propia), sin entender nada más.
- **Rationale**: `sudo rm -rf /` debe denegarse (escenario 6 de la US1) y `pwsh -Command "Stop-Computer"` también (escenario 7).

## R6. Objetivos «completos» y comodines (clarificación de coincidencia)

- **Decision**: un argumento es un objetivo completo si, tras quitar comillas y normalizar `\` a `/` (en PowerShell), es uno de estos:
  - bash: `/`, `/*`, `//`, `/.`, `/./`, `~`, `~/`, `~/*`;
  - PowerShell: `X:`, `X:/`, `X:\`, `X:/*`, `X:\*` (cualquier letra, sin distinguir mayúsculas), `~`, `~/`, `~\`, `~/*`, `~\*`, `/`, `\`.

  Cualquier otra ruta, como `/tmp/build`, `~/proyecto` o `C:\proyecto`, no es completa. `$HOME` es una variable y por eso no se entiende (R4).
- **Rationale**: es la regla del revisor. Normalizar `//` y `/.` evita saltarla con una ruta equivalente.

## R7. Opciones combinadas, sinónimos y parámetros abreviados

- **Decision**:
  - **bash**: una opción corta agrupada se expande (`-rf` → `-r`, `-f`); las largas se traducen con la tabla de sinónimos del intérprete (`--recursive` → `-r`, `--force` → `-f`, `--no-preserve-root` no cuenta). `--` termina las opciones. La comparación distingue mayúsculas (`-R` ≠ `-r`), salvo la tabla de sinónimos (`chmod --recursive` → `-R`).
  - **PowerShell**: un parámetro de la parte cubre el de la regla si es un **prefijo** de él sin distinguir mayúsculas (`-rec`, `-r` → `-Recurse`; `-fo`, `-f` → `-Force`). Los parámetros con dos puntos (`-Recurse:$true`) cuentan como el parámetro; con `:$false` se marcan como no entendidos.
- **Rationale**: la spec pide que cuenten las abreviaturas «si no son ambiguas». Saber si son ambiguas exige conocer todos los parámetros de cada cmdlet, que el núcleo no puede consultar (FR-013). Aceptar cualquier prefijo es más restrictivo: puede denegar algo de más, pero nunca deja pasar un comando peligroso. **Desviación anotada**: se acepta el prefijo aunque sea ambiguo, porque denegar es seguro.

## R8. Orden de la cadena y precedencia (restricciones 3 y 4)

- **Decision**: la cadena queda `ProtectedPolicy(CommandPolicy(ExactCallPolicy(DefaultPermissionPolicy)))`. `CommandPolicy.evaluate`:
  1. Si la llamada no es de la herramienta inyectada, delega tal cual en `inner`.
  2. Si el argumento no es texto, o el análisis lanza una excepción, marca «no entendido».
  3. Analiza el comando. Si alguna parte ejecutable coincide con la lista, devuelve `DENY` **sin consultar a `inner`**: se evalúa antes que `ExactCallPolicy`.
  4. Si no, `d = inner.evaluate(call)`; una excepción o un valor raro de `inner` da `DENY`.
  5. Si el comando no se entendió y `d` es `ALLOW`, devuelve `ASK`; si no, devuelve `d`.

  Así `ExactCallPolicy` solo puede subir a `ALLOW` lo que esta regla entiende y no deniega, y una denegación de `DefaultPermissionPolicy` (lista `deny`) o de `ProtectedPolicy` (zona protegida) se mantiene. Con la herramienta en la lista `ask`, `ExactCallPolicy` ya devuelve `ASK`; con un comando denegado, `CommandPolicy` devuelve `DENY` antes.
- **Rationale**: «solo puede endurecer» (FR-009) se puede vigilar con una guarda: el módulo nunca nombra `ALLOW` salvo para compararlo y convertirlo en `ASK`. `ProtectedPolicy` sigue fuera porque deniega antes que nadie (HU-11-01).
- **Alternatives considered**: meter la regla dentro de `DefaultPermissionPolicy` (`policy.py`, protegido en esta historia y con la invariante de HU-05-01); poner `CommandPolicy` dentro de `ExactCallPolicy`, descartado porque `ExactCallPolicy` subiría a `ALLOW` un comando no entendido.

## R9. Configuración `[permissions] deny_commands` (restricción 6, Q1)

- **Decision**:
  - `config.py` añade `deny_commands` a los campos admitidos de `[permissions]` y el campo `HarnessConfig.deny_commands: tuple[str, ...] = ()`, **separado** de `PermissionRules`.
  - Cada valor debe ser un texto no vacío, de hasta 500 caracteres, sin caracteres de control. Los duplicados se descartan conservando el orden. Si no se cumple → `ConfigProblem("permissions.deny_commands", …)` con un mensaje fijo.
  - La compilación con el dialecto del intérprete ocurre en `bootstrap.py`. Un patrón que no se entiende → `StartupError` con un mensaje que no repite el texto («una entrada de permissions.deny_commands no se entiende para <intérprete>»).
  - `config.example.toml` lleva `# deny_commands = []` comentado.
- **Rationale**: `PermissionRules` tiene una prueba de arquitectura que fija sus campos (`{"deny", "ask"}`) y es un tipo del núcleo. Separar el campo evita tocarla y deja `PermissionRules` solo con nombres de herramienta. `config.py` no conoce el intérprete; lo decide `bootstrap.py`.
- **Alternatives considered**: añadir `deny_commands` a `PermissionRules`, descartado porque cambia un tipo del núcleo y una prueba existente sin necesidad.

## R10. Sin filtrar datos (restricción 7)

- **Decision**: la política devuelve solo el `PermissionDecision`. `CompiledRule` guarda el motivo (`reason`), pero ningún evento ni mensaje lo usa; el bucle ya publica `PERMISSION_DECIDED` sin argumentos y el modelo recibe `[permission_denied]`. Los errores de compilación de `deny_commands` no repiten el texto. Las pruebas usan el centinela `VALOR-DE-PRUEBA-123` dentro de comandos denegados y comprueban que no aparece en los eventos ni en el historial (solo en la llamada original del asistente, que es del modelo).
- **Observación** para el PO y A: mostrar el motivo exige cambiar el puerto o el bucle; queda fuera.

## R11. AC-02 con `ApprovalGate` real (restricción 5)

- **Decision**: una prueba de integración con `compose()` y un aprobador doble que responde «aprobar para la sesión» y cuenta las preguntas:
  1. el agente pide un comando inocente (se pregunta y se aprueba para la sesión);
  2. pide el mismo comando encadenado con uno denegado;
  3. pide el denegado solo, dos veces.

  Se comprueba que (2) y (3) dan `[permission_denied]`, que el aprobador recibió una sola pregunta (la de 1), que ningún proceso escribió el marcador y que una segunda petición idéntica a (1) sigue sin preguntar, porque la aprobación de sesión sigue viva.
- **Rationale**: es el comportamiento real del bucle: `_ask_approval` solo se alcanza con «preguntar».

## R12. Ampliación de la lista base (FR-001; pendiente del PO)

- **Decision**: la lista se amplía de forma conservadora y se describe con la sintaxis de R2.
  - **bash** (además de las 8 de HU-01-04):
    - `rm -rf ~` y `chmod -R 777 /` se mantienen;
    - nuevas: `halt`, `poweroff`, `init 0`, `init 6` (subcomando), `wipefs`, `shred`, `fdisk`, `parted`, `> /dev/sd`, `> /dev/nvme`, `> /dev/hd` (redirección), `chown -R root /` (objetivo).
  - **PowerShell** (además de las 7):
    - nuevas: `shutdown` (programa, `shutdown.exe`), `Remove-Item -Recurse -Force ~` (objetivo), `format` (programa de cmd), `Initialize-Disk`, `Remove-Partition`, `Disable-ComputerRestore`, `bcdedit`, `vssadmin delete shadows` (subcomando), `rd /s /q C:\` (objetivo).
  - **Tablas de datos**:
    - alias de PowerShell: `rm`, `ri`, `del`, `erase`, `rd`, `rmdir` → `remove-item`, y `Stop-Computer`/`Restart-Computer` sin alias;
    - sinónimos de bash: `rm` (`--recursive` → `-r`, `--force` → `-f`, `-R` → `-r`), `chmod` y `chown` (`--recursive` → `-R`).
- **Rationale**: cubre los escenarios 6 y 7 de la US1 sin bloquear el trabajo normal (SC-004). El contenido definitivo es tarea humana del PO (T-humana).

## R13. Lo que no cambia y queda fuera

- Sin cambios en `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/permissions/{policy,protected,exact_calls,approvals}.py`, `cli/` ni `tests/doubles/`. `PermissionRules` tampoco cambia.
- Fuera de alcance:
  - reglas de git por subcomando (HU-11-02, que podrá añadir entradas de tipo subcomando o una regla de «preguntar»);
  - generalizar las aprobaciones de sesión;
  - mostrar el motivo;
  - analizar scripts (`python x.py` se evalúa por su texto);
  - el entorno aislado (PD-06).
