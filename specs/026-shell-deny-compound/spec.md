# Feature Specification: HU-05-02 — Lista de denegados y análisis de comandos compuestos

**Feature Branch**: `gustavo` (el directorio de la spec es `026-shell-deny-compound`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-26

**Status**: Borrador (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 2 | **PHU**: 2 | **Responsable**: C — Control y conexiones | **Tareas de referencia**: Sp2-24 (1,5 h), Sp2-25 (1 h), Sp2-26 (3 h), Sp2-27 (1 h), Sp2-28 (2 h) | **Requisitos**: RNF-19, RF-5.2 | **Decisiones**: V-02, V-17 | **Depende de**: HU-05-01 (política, integrada en `main`), HU-01-04 (shell y lista de datos, integrada en `main`); ambas `En revisión` en PROGRESO

**Input**: User description: "HU-05-02 — Lista de denegados y análisis de comandos compuestos (2 PHU). Puntos de seguridad: lista base por plataforma que ninguna configuración vacía ni una aprobación de sesión anula (V-02); cada parte de un encadenado se evalúa y manda la más restrictiva; lo no entendido se pregunta (V-17); sustituciones, comillas, redirecciones, saltos de línea y construcciones de PowerShell; convivencia con ExactCallPolicy de HU-11-03. Extender `adapters/system/denied_commands.py` sin duplicar. Tarea humana de revisión cruzada (A o B)."

## Clarifications

### Session 2026-10-26

Respuestas del revisor a las dos preguntas abiertas de `/speckit-specify`, más una regla de coincidencia para la lista base. Ninguna contradice AC-01 a AC-04.

- Q: ¿Cómo participa la configuración del usuario en la lista de comandos denegados? → A: Con un campo opcional `[permissions] deny_commands` (lista de textos) que **solo añade** comandos a la lista base. Una lista vacía deja la base intacta. Cualquier campo para quitar, vaciar o sustituir la base (por ejemplo `allow_commands` o `replace`) es un campo desconocido y detiene el arranque, como en HU-05-01. `config.example.toml` lleva el campo comentado. Toca `config.py` (área B): tarea humana con el visto bueno de B.
- Q: ¿Qué pasa con un comando denegado escrito dentro de comillas, de una sustitución o de `bash -c "…"`? → A: Se distingue **texto que se ejecuta** de **dato**:
  - se busca en la lista, y se **deniega** si aparece, el texto que se ejecuta: sustituciones `$( … )` y comillas invertidas, el contenido de `bash -c` / `sh -c` / `pwsh -Command` / `cmd /c` cuando se puede analizar, y los destinos de redirección;
  - **no** se busca en los argumentos entre comillas de un programa normal, porque son datos: `echo "no uses shutdown"` y `git commit -m "fix: shutdown limpio"` no se deniegan;
  - el contenido ejecutable que no se puede analizar (`eval`, `xargs`, `-EncodedCommand`, variables, comillas sin cerrar) se **pregunta**;
  - un comando denegado oculto en una parte ejecutable gana sobre cualquier otra decisión (denegar > preguntar > permitir).
- Q: ¿Cuándo coincide una entrada de la lista base con una parte del comando? → A:
  - Los patrones de **una sola palabra** (`shutdown`, `reboot`, `mkfs`, `Format-Volume`, `Stop-Computer`…) coinciden **solo en la posición del programa**, tras quitar `sudo`/`env`/`VAR=x` y la ruta y la extensión; nunca como argumento de otro programa (`cat shutdown.log` pasa).
  - Los patrones **con objetivo** (`rm -rf /`, `rm -rf ~`, `chmod -R 777 /`, `Remove-Item -Recurse -Force C:\`) coinciden solo cuando el objetivo es la raíz, `~` o la unidad completa (`/`, `/*`, `~`, `~/*`, `C:\`, `C:\*`). No coinciden cuando es el inicio de una ruta: `rm -rf /tmp/build` y `rm -rf ~/proyecto/dist` no se deniegan, aunque sí se preguntan por ser de riesgo alto, como hoy.
  - `dd if=` se mantiene conservador: se deniega cualquier `dd` con un argumento `if=`.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04c-historias-control.md` (HU-05-02). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

- **Como:** usuario operador
- **Quiero:** una lista de comandos peligrosos denegados por defecto y que cada parte de un comando encadenado se evalúe por separado
- **Para:** que ni un error de configuración ni un comando encadenado abran un hueco de seguridad
- **Descripción:** El sistema trae una lista de comandos peligrosos denegados que ninguna configuración puede vaciar ni una aprobación de sesión anular. Como el shell es la herramienta general, un comando encadenado se separa y cada parte se evalúa por separado.

**Flujo general**

1. El sistema carga la lista base al arrancar.
2. Fusiona la configuración del usuario sin poder quitar la base.
3. Ante un comando con &&, ; o |, separa sus partes y evalúa cada una.
4. Manda la decisión más restrictiva; si no entiende el comando, pregunta.
5. Ante un comando denegado, la política lo rechaza aunque exista aprobación de sesión.

**Reglas de negocio**

1. La lista es propia de cada plataforma.
2. Una aprobación de sesión nunca anula una denegación.
3. Lo que el analizador no entiende se pregunta; nunca se permite por defecto.

**Criterios de aceptación**

- **AC-01 — Lista base inalterable.** Dado un archivo de configuración que intenta vaciar la lista, cuando arranca el sistema, entonces la lista base se mantiene.
- **AC-02 — Aprobación de sesión no anula denegación.** Dado una aprobación para toda la sesión, cuando se pide un comando denegado, entonces sigue denegado.
- **AC-03 — Comandos encadenados evaluados por partes.** Dado un comando encadenado con &&, ; o |, cuando la política lo evalúa, entonces evalúa cada parte y manda la más restrictiva.
- **AC-04 — Falla cerrada ante lo no entendido.** Dado un comando que el analizador no logra entender, cuando se evalúa, entonces se pregunta al usuario (falla cerrada).

### Lo que ya existe y lo que cambia

- **Ya existe (HU-01-04)**: `adapters/system/denied_commands.py` publica, **solo como dato**, una lista por intérprete (`bash`: 8 entradas; `powershell`: 7) de `DeniedCommand(pattern, reason)`, con `pattern` como fragmento literal de texto. Es de solo lectura y nada la aplica: ni el shell, ni la herramienta, ni la política. HU-01-04 dejó a esta historia decidir cómo se compara (mayúsculas, comandos compuestos) y revisar el contenido con el PO. Esta historia **parte de esa lista y la amplía**, sin crear una segunda.
- **Ya existe (HU-05-01, HU-05-03, HU-11-01, HU-11-03)**:
  - La herramienta `shell` es de riesgo alto: la política por defecto siempre pregunta.
  - Una aprobación (una vez o para la sesión, con los argumentos exactos) solo se consulta cuando la política dijo «preguntar»: una denegación nunca llega al aprobador.
  - `ProtectedPolicy` deniega antes que nadie los comandos que nombran literalmente la zona protegida.
  - `ExactCallPolicy` convierte un «preguntar» en «permitir» solo para el texto exacto de los comandos de la tarea.
  - La configuración `[permissions]` solo admite listas `deny` y `ask` de **nombres de herramienta**, nunca de permitir.
- **Falta (esta historia)**:
  1. Una regla de la política que separe el comando del shell en partes y deniegue si alguna parte es un comando de la lista. Debe hacerlo con independencia del orden de las opciones, de los espacios, de la ruta del programa y, en PowerShell, de las mayúsculas y los alias.
  2. Que pregunte, aunque otra regla quisiera permitir, cuando el comando contiene algo que el analizador no entiende.
  3. Que la configuración pueda **añadir** comandos denegados, pero no quitar los de la base.
  4. Revisar y ampliar la lista base por plataforma.

### User Story 1 - Un comando peligroso se deniega aunque vaya encadenado (Priority: P1)

El agente pide al shell un comando que, solo o encadenado con otros, contiene un comando de la lista de denegados. La política lo deniega sin preguntar. El comando no se ejecuta y el modelo recibe la denegación.

**Why this priority**: Es AC-03 y el núcleo de V-17: un comando inocente delante no puede esconder uno peligroso detrás.

**Independent Test**: Con la política real y la lista de la plataforma, se evalúa una batería de comandos encadenados con `&&`, `||`, `;`, `|`, `&` y salto de línea. Hay un comando denegado en cualquier posición; todos dan «denegar» y ningún proceso se crea.

**Acceptance Scenarios**:

1. **Given** el shell bash, **When** el agente pide `echo hola && rm -rf /`, **Then** la política deniega (la segunda parte está en la lista).
2. **Given** el shell bash, **When** el agente pide `rm -rf / ; echo hola` o `ls | shutdown now`, **Then** deniega: manda la parte más restrictiva sin importar el orden.
3. **Given** el shell PowerShell, **When** el agente pide `Get-ChildItem; Format-Volume -DriveLetter D` o `dir | Stop-Computer`, **Then** deniega.
4. **Given** un comando encadenado cuyas partes no están en la lista y que el analizador entiende, **When** se evalúa, **Then** la decisión es la misma que sin esta historia: «preguntar», o «permitir» si es el texto exacto de un comando de la tarea.
5. **Given** una variante del mismo comando peligroso (opciones en otro orden o separadas, espacios extra, ruta completa del programa, mayúsculas o alias en PowerShell), **When** se evalúa, **Then** también se deniega.
6. **Given** el shell bash, **When** el agente pide `rm -rf /*`, `rm -fr ~/*`, `sudo /sbin/shutdown -h now`, `env X=1 reboot`, `dd if=/dev/zero of=archivo.img` o `echo hola > $(reboot)`, **Then** se deniega: el objetivo es la raíz o `~`, el programa es de una sola palabra de la lista, o hay un `dd` con `if=` o un comando denegado en texto que se ejecuta.
7. **Given** el shell PowerShell, **When** el agente pide `Remove-Item -Recurse -Force C:\*`, `ri -r -fo C:\` o `pwsh -Command "Stop-Computer"`, **Then** se deniega.
8. **Given** `bash -c "rm -rf /"` o `echo $(shutdown now)`, **When** se evalúa, **Then** se deniega: el comando denegado está en texto que se ejecuta y se puede analizar.
9. **Given** falsos positivos que **no** deben denegarse: `cat shutdown.log`, `grep reboot notas.txt`, `echo "no uses shutdown"`, `git commit -m "fix: shutdown limpio"`, `rm -rf /tmp/build`, `rm -rf ~/proyecto/dist`, `chmod -R 777 ./dist` (bash) y `Get-Content Stop-Computer.txt`, `Remove-Item -Recurse -Force C:\proyecto\dist` (PowerShell), **When** se evalúan, **Then** ninguno se deniega: se preguntan como hoy (el shell es de riesgo alto), o se permiten si son el texto exacto de un comando de la tarea y el analizador los entiende.

---

### User Story 2 - Lo que el analizador no entiende se pregunta (Priority: P1)

El agente pide un comando con construcciones que el analizador no interpreta: sustituciones, comillas sin cerrar, ejecución de otro intérprete, bloques de PowerShell o variables en lugar del programa. El usuario debe decidir: nunca se permite solo, ni siquiera si el texto coincide con un comando declarado de la tarea.

**Why this priority**: Es AC-04 y la regla de negocio 3; sin ella, una construcción no prevista sería un hueco.

**Independent Test**: Con la política real se evalúa una batería de comandos no entendibles. Todos dan «preguntar» (o «denegar» si contienen un comando de la lista) y ninguno da «permitir». Se repite con esos textos declarados como comandos de la tarea (HU-11-03) y sigue sin dar «permitir».

**Acceptance Scenarios**:

1. **Given** `echo $(whoami)`, `` echo `date` ``, `cat <(ls)` o `bash -c "ls"`, **When** se evalúa, **Then** se pregunta: el texto interior se analiza y no contiene un comando de la lista, pero ejecutar texto o sustituir nunca se permite solo.
2. **Given** una comilla sin cerrar o un salto de línea con continuación (`\` al final), **When** se evalúa, **Then** se pregunta.
3. **Given** PowerShell con `Invoke-Expression`, `iex`, `& $programa`, un bloque `{ … }`, una subexpresión `$( … )` o `-EncodedCommand`, **When** se evalúa, **Then** se pregunta.
4. **Given** un comando no entendible declarado tal cual en `## Comandos` de la tarea, **When** el agente lo pide, **Then** se pregunta: la regla de HU-11-03 no puede convertirlo en «permitir».

---

### User Story 3 - La lista base no se puede quitar ni saltar (Priority: P1)

El operador configura su propia lista y aprueba acciones durante la sesión. Ni la configuración ni una aprobación para toda la sesión hacen que un comando de la lista base se ejecute.

**Why this priority**: Son AC-01, AC-02 y V-02: un error de configuración o una aprobación generosa no deben abrir un hueco.

**Independent Test**: Se arranca con una configuración que intenta vaciar la lista y con un aprobador que lo aprueba todo para la sesión. Los comandos de la base siguen denegados y el aprobador nunca recibe la pregunta.

**Acceptance Scenarios**:

1. **Given** una configuración con `[permissions] deny_commands = []`, **When** arranca el sistema, **Then** la lista base sigue completa (AC-01).
1a. **Given** una configuración con un campo para quitar, vaciar o sustituir la base (`allow_commands`, `replace`, `base = []`…), **When** arranca el sistema, **Then** el arranque se detiene por campo desconocido, con un mensaje en español que no reproduce el valor, y la base no cambia.
1b. **Given** `[permissions] deny_commands = ["terraform destroy"]`, **When** el agente pide `terraform destroy` o lo encadena con otro comando, **Then** se deniega, y los comandos de la base siguen denegados.
2. **Given** un aprobador que responde «aprobar para la sesión» a todo, **When** el agente pide dos veces un comando de la lista (solo o encadenado), **Then** se deniega las dos veces y el aprobador no recibe ninguna pregunta.
3. **Given** que el operador aprobó para la sesión un comando inocente, **When** el agente pide ese mismo comando encadenado con uno denegado, **Then** se deniega (los argumentos ya no son los aprobados y, además, una parte está en la lista).
4. **Given** la herramienta `shell` en la lista `deny` de la configuración, **When** se evalúa cualquier comando, **Then** se deniega como hoy. Si está en `ask`, se pregunta salvo que el comando esté en la lista de denegados, que gana.

---

### Edge Cases

- **Separadores reconocidos**:
  - bash: `&&`, `||`, `;`, `|`, `|&`, `&` (en segundo plano) y salto de línea;
  - PowerShell: `;`, `|`, `&&`, `||` (PowerShell 7) y salto de línea.

  Un separador dentro de comillas no separa. Partes vacías (`a ;; b`, `| b`, `a &&`) → no se entiende → preguntar; un `;` o un salto de línea al final es válido.
- **Redirecciones** (`>`, `>>`, `2>`, `2>&1`, `&>`, `<`; en PowerShell además `*>` y `3>`…): se entienden. El destino cuenta como texto que se ejecuta: se compara con la lista, y escribir en un dispositivo de disco, como `> /dev/sda`, se deniega si la lista lo incluye. Si el destino es una sustitución, su contenido se analiza (`> $(reboot)` se deniega). Un *here-document* (`<<`, `<<<`) no se entiende → preguntar.
- **Sustituciones y expansiones**:
  - `$( … )`, `` ` … ` ``, `<( … )` y `>( … )`: no se entienden;
  - una variable o expansión en la posición del programa (`$CMD`, `${X}`, `$env:X` en PowerShell): no se entiende;
  - una variable en un argumento (`rm -rf $HOME`): tampoco se entiende, porque el valor real no se conoce.

  En todos estos casos se pregunta. Si el contenido de la sustitución se puede analizar, se analiza como un comando más: si contiene un comando de la lista, se deniega (`echo $(shutdown now)`). Si no se puede analizar, se pregunta.
- **Comillas: dato frente a texto que se ejecuta**: un argumento entre comillas de un programa normal es un dato y no se busca en la lista (`echo "no uses shutdown"`, `git commit -m "fix: shutdown limpio"`). Lo que se ejecuta sí se analiza aunque vaya entre comillas: el texto de `bash -c`, `sh -c`, `pwsh -Command`, `powershell -Command`, `cmd /c` y el de una sustitución dentro de comillas dobles (`echo "$(reboot)"`).
- **Otros intérpretes y envoltorios**:
  - Se quitan antes de evaluar el programa real: `sudo`, `env VAR=x`, `nohup`, `time`, `nice`, `command`, `exec` y una asignación inicial `VAR=x` (bash). Así `sudo rm -rf /` se deniega.
  - Ejecutar otro intérprete nunca se permite solo → preguntar. Si su texto se puede analizar (`bash -c "…"`, `sh -c`, `zsh -c`, `pwsh -Command "…"`, `powershell -Command "…"`, `cmd /c …`), se analiza como un comando más y se deniega si contiene un comando de la lista. Lo que no se puede analizar se pregunta: `-EncodedCommand`, `eval`, `source`/`.`, `xargs`, `Invoke-Expression`/`iex`, `Start-Process`, el operador `&` de PowerShell y el texto que viene de una variable.
  - El texto de otro intérprete se analiza con las reglas de ese intérprete (bash para `bash -c`/`sh -c`/`zsh -c`, PowerShell para `pwsh`/`powershell -Command`). `cmd /c` se analiza solo para separar `&`, `&&`, `||` y `|` y comparar el programa; cualquier otra cosa de `cmd` se pregunta.
- **Comentarios** (`#` en bash al principio de una palabra, `#` o `<# … #>` en PowerShell): no se entienden → preguntar.
- **Grupos y subshells** (`( … )`, `{ …; }` en bash; bloques de script en PowerShell): no se entienden → preguntar.
- **Comodines** (`*`, `?`, `[…]`): se entienden como argumentos. `rm -rf /*` y `rm -rf ~/*` cuentan como objetivo «raíz» u «hogar» completos y se deniegan; `rm -rf /tmp/*` no.
- **Programa de una sola palabra como argumento**: `cat shutdown.log`, `grep reboot notas.txt`, `man mkfs` o `which shutdown` no se deniegan, porque el patrón solo coincide en la posición del programa.
- **Objetivos con ruta**: `rm -rf /tmp/build`, `rm -rf ~/proyecto/dist`, `chmod -R 777 ./dist` y `Remove-Item -Recurse -Force C:\proyecto` no coinciden con los patrones con objetivo; se preguntan como cualquier comando del shell. Las variantes del objetivo completo sí coinciden: `/`, `/*`, `//`, `/.`, `~`, `~/`, `~/*`, `$HOME` (variable → no se entiende → preguntar), `C:\`, `C:/`, `C:\*`, `C:` y la misma unidad en minúsculas en PowerShell.
- **Mayúsculas**: en PowerShell los comandos, alias y parámetros no distinguen mayúsculas; en bash sí (`RM` no es `rm`). Los parámetros abreviados de PowerShell (`-Rec`, `-Fo`) cuentan como el parámetro completo si la abreviatura no es ambigua.
- **Ruta del programa**: `/bin/rm`, `/usr/bin/rm` o `C:\Windows\System32\shutdown.exe` se comparan por el nombre del programa, sin carpeta ni extensión (`.exe`, `.cmd`, `.bat`, `.ps1`).
- **Opciones combinadas o en otro orden**: `rm -rf /`, `rm -fr /`, `rm -r -f /`, `rm --recursive --force /` y `rm -f -r /` son el mismo comando.
- **Texto vacío, solo espacios o mayor que el máximo del shell**: ya lo rechaza la validación de la herramienta; si llegara a la política → no se entiende → preguntar.
- **Herramientas que no son el shell**: esta regla no les aplica y su decisión no cambia.
- **Sistema sin lista para su intérprete**: no hay ninguno hoy, porque el shell solo puede ser bash o PowerShell. Si apareciera un intérprete sin lista, todo comando se pregunta: nunca se permite sin lista.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE tener una **lista base de comandos denegados para cada intérprete** (bash y PowerShell), fija en el código. Parte de la lista de HU-01-04, revisada y ampliada, y no se duplica. Cada entrada tiene su motivo en español.
- **FR-002**: La lista en uso DEBE ser la base del intérprete elegido al arrancar más lo que añada la configuración (FR-003). Ninguna configuración, opción ni regla puede quitar, vaciar ni sustituir una entrada de la base (AC-01).
- **FR-003**: La configuración del usuario DEBE poder, como máximo, **añadir** comandos denegados mediante el campo opcional `[permissions] deny_commands` (lista de textos no vacíos, cada uno con el formato de un comando del intérprete). Una lista vacía o ausente deja la base intacta. Cualquier campo para quitar, vaciar o sustituir la base es un campo desconocido que detiene el arranque. Un valor no válido detiene el arranque con un mensaje en español que no reproduce el valor (convención de HU-00-04). `config.example.toml` lleva el campo comentado. Una entrada añadida coincide con las mismas reglas que la base (FR-005): una sola palabra solo en la posición del programa; varias palabras, por programa y argumentos.
- **FR-004**: Ante una llamada al shell, la política DEBE separar el comando en partes por los separadores de su intérprete (Edge Cases), respetando las comillas, y evaluar cada parte por separado (AC-03).
- **FR-005**: Una parte DEBE contar como comando denegado cuando su programa (una vez quitados los envoltorios `sudo`/`env`/`VAR=x`…, la ruta y la extensión) y sus argumentos coinciden con una entrada de la lista, según su tipo:
  - **una sola palabra** (`shutdown`, `reboot`, `mkfs`, `Format-Volume`, `Stop-Computer`…): coincide solo en la posición del programa, nunca como argumento de otro;
  - **con objetivo** (`rm -rf /`, `rm -rf ~`, `chmod -R 777 /`, `Remove-Item -Recurse -Force C:\`): coincide cuando el programa y sus opciones están presentes y el objetivo es la raíz, `~` o la unidad completa (`/`, `/*`, `~`, `~/*`, `C:\`, `C:\*` y sus formas equivalentes), nunca cuando el objetivo es una ruta por debajo;
  - **con argumento de prefijo** (`dd if=`): coincide con cualquier `dd` que lleve un argumento que empiece por `if=`.

  En todos los tipos la coincidencia no depende del orden de las opciones, de cómo se combinen las opciones cortas (`-rf`, `-fr`, `-r -f`, `--recursive --force`), de los espacios ni, en PowerShell, de las mayúsculas, los alias conocidos (`rm`, `ri`, `del`, `rd` para `Remove-Item`…) o los parámetros abreviados.
- **FR-005a**: El análisis DEBE buscar comandos de la lista en **todo el texto que se ejecuta**: cada parte del comando, el contenido de las sustituciones (`$( … )`, comillas invertidas), el texto de `bash -c`/`sh -c`/`zsh -c`/`pwsh -Command`/`powershell -Command`/`cmd /c` cuando se puede analizar, y los destinos de redirección. **No** busca en los argumentos entre comillas de un programa normal, que son datos.
- **FR-005b**: Un comando denegado encontrado en cualquier texto que se ejecuta DEBE denegar el comando completo, sea cual sea la decisión de las demás partes y de la política envuelta.
- **FR-006**: La decisión del comando completo DEBE ser la más restrictiva de sus partes y de la política envuelta, en el orden **denegar > preguntar > permitir** (AC-03).
- **FR-007**: Si alguna parte o construcción no se entiende o ejecuta texto (sustitución, otro intérprete, contenido ejecutable que no se puede analizar: Edge Cases), la decisión DEBE ser como mínimo «preguntar», aunque la política envuelta o la regla de comandos exactos de HU-11-03 quisieran «permitir» (AC-04, V-17). Si el texto analizable contiene un comando de la lista, se deniega (FR-005b).
- **FR-008**: Un comando denegado DEBE denegarse antes de consultar al aprobador. Ninguna aprobación, de una vez o de sesión, previa o posterior, puede hacer que se ejecute (AC-02, V-02).
- **FR-009**: Esta regla solo puede **endurecer**: nunca convierte en «permitir» una decisión que no lo era, y si falla (excepción o dato inesperado) la decisión es «denegar».
- **FR-010**: La convivencia con las reglas existentes DEBE quedar así:
  - la zona protegida de HU-11-01 sigue denegando primero;
  - la lista `deny` de herramientas sigue denegando el shell entero;
  - la lista `ask` de herramientas sigue preguntando;
  - la regla de comandos exactos de HU-11-03 solo puede subir de «preguntar» a «permitir» un comando que esta regla deja en «preguntar» y que el analizador entiende. Una denegación de esta historia nunca llega a esa regla.
- **FR-011**: Ni los mensajes al modelo ni los eventos DEBEN incluir el texto del comando ni la entrada de la lista que coincidió. El modelo recibe la denegación genérica actual (`[permission_denied]`), porque el puerto de la política solo devuelve la decisión.
- **FR-012**: La regla DEBE aplicarse solo a la herramienta de shell; las demás herramientas conservan su decisión.
- **FR-013**: La evaluación DEBE ser pura y determinista: el mismo comando con la misma lista da siempre la misma decisión, sin ejecutar nada, sin leer archivos ni el entorno y sin consultar el sistema (por ejemplo, para resolver alias reales o el contenido de variables).

### Key Entities

- **Comando denegado** (`DeniedCommand`, existente y ampliado): programa (con sus alias y la plataforma), tipo de coincidencia (una sola palabra, con objetivo, con argumento de prefijo), opciones y objetivo que lo hacen peligroso, y motivo en español. Pertenece a la lista de un intérprete. Las entradas añadidas por la configuración son del mismo tipo.
- **Lista de denegados en uso**: la base del intérprete más las entradas de `[permissions] deny_commands`. Es inmutable durante la ejecución.
- **Parte de un comando**: el programa y sus argumentos tras separar por los separadores del intérprete y quitar envoltorios y redirecciones. Para el análisis se marca como «entendida» o «no entendida».
- **Resultado del análisis**: lista de partes, si todo se entendió y si alguna parte coincide con la lista. No guarda ni publica el texto.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En una batería de al menos 40 comandos encadenados por plataforma (bash y PowerShell) que esconden un comando de la lista en cualquier posición o con variantes equivalentes, el 100 % se deniega y ninguno se ejecuta.
- **SC-002**: En una batería de al menos 25 comandos no entendibles por plataforma, el 0 % obtiene «permitir», tampoco cuando su texto está declarado como comando de la tarea.
- **SC-003**: Con una configuración que intenta vaciar la lista y con un aprobador que lo aprueba todo para la sesión, el 100 % de los comandos de la base siguen denegados y el aprobador recibe 0 preguntas sobre ellos.
- **SC-004**: En una batería de al menos 20 comandos habituales de desarrollo por plataforma (pruebas, lint, `git status`, listar, leer, encadenados con `&&` o `|`), más los falsos positivos del escenario 9 de la US1 (palabras de la lista como argumento o dentro de comillas de datos, y rutas por debajo de la raíz o de `~`), el 0 % se deniega: siguen preguntándose, o se permiten si son el comando exacto de la tarea. La lista no bloquea el trabajo normal.
- **SC-005**: Sin cambios en la configuración ni en la tarea, el 100 % de las pruebas existentes de la política, la aprobación, la zona protegida y los comandos de la tarea siguen pasando sin cambiar sus aserciones.

## Assumptions

- HU-05-01 y HU-01-04 están integradas en `main` (verificado en `origin/main` e60d101 el 2026-10-26, que ya incluye HU-11-03), pero ninguna está `Hecha`. HU-05-03 (aprobación) y HU-11-01 (zona protegida) también están en `main`.
- La lista base inicial es conservadora y parte de la de HU-01-04. Su contenido definitivo necesita la **revisión del PO**, tarea humana que ya pedía HU-01-04.
- No se cambian los puertos de `core/interfaces/`, el catálogo de eventos ni `core/loop.py`. La regla vive en la política (área C) y se conecta en la raíz de composición, como `ProtectedPolicy` y `ExactCallPolicy`.
- El analizador no ejecuta ni consulta el sistema: no conoce los alias, funciones ni variables reales de la máquina. Por eso, ante una variable o una construcción dinámica, pregunta (FR-007, FR-013). La protección real frente a un shell arbitrario sigue siendo el entorno aislado (PD-06 / HU-IN-02, riesgo R-21).
- Las reglas de permisos por subcomando de git (`git push`, `git reset --hard`…) son de **HU-11-02**. Esta historia deja el análisis por partes listo para que HU-11-02 añada sus reglas, pero no las define.
- Generalizar la aprobación de sesión por programa y subcomando (pendiente de HU-05-03, Q1) queda **fuera**: sigue cubriendo herramienta y argumentos exactos. Se anota como observación.
- Mostrar al usuario o al modelo el **motivo** de la denegación queda fuera, porque exige cambiar el puerto o el bucle. Se anota como observación.
- La entrada de la lista con patrón literal de HU-01-04 (`pattern`) pasa a describirse por programa, tipo de coincidencia y argumentos (FR-005); `dd if=` se mantiene conservador. Las pruebas existentes de `tests/unit/adapters/system/test_denied_commands.py` se conservan; si alguna fija el formato antiguo, se ajusta solo esa aserción y se declara.
- Fuera de alcance: reglas de git (HU-11-02), aislamiento (HU-IN-02), motivo de la denegación en la CLI, generalizar aprobaciones de sesión y analizar scripts que el comando ejecute (un `python script.py` se evalúa por su texto, no por lo que hace el script).
- Tareas humanas:
  - revisión cruzada por A o B;
  - revisión del contenido de la lista base por el PO;
  - visto bueno de B a la ampliación de `config.py` (`[permissions] deny_commands`) y de `config.example.toml`;
  - CI remota en Windows y Linux.

  Claude no las marca como hechas.
- Presupuesto del sprint: 8,5 h (Sp2-24 a Sp2-28). Es un aviso, no motivo para recortar alcance.
