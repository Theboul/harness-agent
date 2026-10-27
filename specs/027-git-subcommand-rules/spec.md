# Feature Specification: HU-11-02 — Git mediante el shell con reglas de permisos por subcomando

**Feature Branch**: `gustavo` (el directorio de la spec es `027-git-subcommand-rules`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-27

**Status**: Borrador (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 2 | **PHU**: 1 | **Responsable**: B — Estado | **Tareas de referencia**: Sp2-43 (1,5 h), Sp2-44 (1 h), Sp2-45 (1,5 h) | **Requisitos**: RF-11.2 | **Decisión**: V-17 | **Depende de**: HU-01-04 (shell, integrada en `main`), HU-05-02 (lista de denegados y analizador de comandos, integrada en `main` en 61024bf); ambas `En revisión` en PROGRESO

**Input**: User description: "HU-11-02 — Git mediante el shell con reglas de permisos por subcomando. Reutilizar el analizador y la política de HU-05-02, `ExactCallPolicy` (HU-11-03), la zona protegida (HU-11-01), la lista base y la herramienta `shell`. push y merge siempre piden aprobación; variantes (`git -C`, `--git-dir`, `-c`, alias, ruta completa, `git.exe`, encadenados); una declaración de la tarea no puede permitir push o merge; una aprobación de sesión de commit no autoriza push; sin filtrar datos ni credenciales de URLs. Fuera: ejecutar git de verdad en las pruebas, flujos de PR/rama, puertos y `core/loop.py`."

## Clarifications

### Session 2026-10-27

Respuestas del revisor a las tres preguntas de `/speckit-specify` y decisiones sobre Sp2-45, `.git` y las credenciales. Ninguna contradice AC-01 ni AC-02.

- Q: ¿Qué lecturas de git se permiten sin preguntar? → A: **Solo** `status`, `diff`, `log`, `show`, `blame`, `shortlog`, `describe`, `rev-parse`, `ls-files`, `grep` (sin `-O`/`--open-files-in-pager`), y `branch`, `tag` y `stash list` **solo cuando listan**. Todo lo demás se pregunta, incluidos crear una rama (`switch -c`, `checkout -b`, `branch <nombre>`) y `git add`. Una lectura con `--output`, `--ext-diff`, `--textconv`, `--no-index` o una redirección pasa a preguntar. Una asignación `GIT_*` delante de git (`GIT_EXTERNAL_DIFF=…`, `GIT_SSH_COMMAND=…`) pasa a preguntar.
- Q: ¿Qué variantes destructivas se deniegan? → A:
  - **Se deniegan**: `reset --hard`; `clean` (incluido `-n`); toda forma de push forzado (`-f`, `--force`, `--force-with-lease`, `--force-if-includes` y refspecs con `+`); `checkout -f`; `checkout -- <rutas>`; `restore` sin `--staged`; `switch --discard-changes`; `reset --merge`/`--keep`; `branch -D`; `stash drop`/`clear`; `push --delete`/`:rama`/`--mirror`; `reflog expire`; `gc --prune=now`; `filter-branch`; `update-ref -d`.
  - **Se preguntan**: `rebase`, `cherry-pick`, `revert`, `reset` sin `--hard` y `branch -d`.
  - **Coincidencia**:
    - (a) un prefijo de una opción larga de git (`--forc`, `--ha`) cuenta como la opción completa y, si es prefijo de una denegada, se deniega;
    - (b) las opciones cortas agrupadas se separan (`clean -fd`, `push -fu`, `branch -Df`);
    - (c) las opciones globales conocidas (`-C`, `--git-dir`, `--work-tree`, `--no-pager`) se saltan para encontrar el subcomando, y `-c` o una opción global desconocida dejan la llamada como mínimo en «preguntar»;
    - (d) un alias del usuario o un subcomando desconocido se pregunta.
- Q: ¿Puede un push o un merge idénticos reutilizar su propia aprobación de sesión? → A: **Sí**. Solo con argumentos exactos, como en HU-05-03; una denegación nunca. No se toca `core/permissions/approvals.py`. **Supuesto pendiente de ratificar por el PO**: la lectura literal de V-17 («push y merge siempre piden aprobación») pediría aprobar siempre.
- Q: ¿Cómo se cubre Sp2-45 («pruebas sobre un repositorio temporal»)? → A: Con **git real**, con estas reglas:
  - solo dentro de una carpeta temporal de la prueba;
  - entorno aislado: `GIT_CONFIG_GLOBAL` a un archivo vacío propio, `GIT_CONFIG_NOSYSTEM=1`, `HOME` propio, usuario y correo de prueba;
  - se omite, con su motivo, si git no está instalado;
  - solo se ejecutan `init`, `add`, `commit`, `status`, `diff` y `log`.

  Sirve para comprobar que lo que la política clasifica como lectura (`status`, `diff`, `log`) no cambia el estado del repositorio (antes frente a después) y que la salida larga se recorta. **Nunca** se ejecuta un comando que la política pregunte o deniegue: esos se prueban solo contra la política y el shell doble.
- Q: ¿Cómo se protege `.git` frente a las herramientas de archivos? → A: Como **dato** desde `bootstrap.py` (carpeta protegida de HU-11-01), sin cambiar `protected.py` ni `protected_paths.py`. La zona protegida no distingue lectura de escritura, así que las herramientas de archivos tampoco pueden **leer** `.git`. Es un efecto aceptado y queda como limitación conocida: el agente obtiene esa información con `git status`, `log` y `show`, que se permiten solos.
- Q: ¿Cómo se ocultan las credenciales de las URLs? → A: Con **una única función pequeña y pura**, en un solo lugar con nombre claro. Sustituye las credenciales de una URL (`esquema://usuario:secreto@host` y `esquema://token@host`) por el marcador existente `<secreto oculto>`. Se aplica **solo** a la salida del shell que vuelve al modelo y a los eventos que lleven esa salida. No duplica el depurador del adaptador LiteLLM (que solo sustituye una clave conocida). Es la pieza que HU-10-02 debe absorber: se anota aquí y en PROGRESO, con una tarea humana para avisar a su responsable. `git remote -v` sigue sin permitirse solo.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y flujo de la historia (inmutables)

Copiados tal cual de `docs/04e-historias-coding-harness.md` (HU-11-02). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

- **Como:** agente principal
- **Quiero:** consultar el estado y el diff, crear una rama y hacer commit usando git por el shell, con reglas de permisos por subcomando
- **Para:** entregar los cambios de una tarea sin una herramienta especial y bajo el mismo control
- **Descripción:** El agente consulta el estado y el diff, crea una rama y hace commit usando git por el shell. No hay una herramienta Git propia: lo que cambia es la regla de permisos de cada subcomando.

**Flujo general**

1. El agente pide git status, git diff o git log por el shell.
2. La política los permite y la salida larga se recorta.
3. Para commit, push o merge, la política pide aprobación.
4. Los comandos destructivos se deniegan.

**Reglas de negocio**

1. Estado, diff y log son de bajo riesgo; commit, push y merge piden aprobación; reset --hard, clean y push --force se deniegan.
2. El prefijo pide una rama por tarea y commits descriptivos.

**Criterios de aceptación**

- **AC-01 — Lectura de Git permitida.** Dado git status, git diff o git log, cuando el agente los pide por el shell, entonces se permiten sin preguntar y la salida larga se recorta.
- **AC-02 — Escritura de Git sujeta a aprobación o denegada.** Dado git commit, git push o git merge, cuando se evalúan, entonces la política pide aprobación; dado git reset --hard, git clean o git push --force, entonces se deniegan.

### Lo que ya existe y lo que cambia

- **Ya existe**:
  - **HU-05-02**: un analizador de comandos de bash y PowerShell. Separa encadenados, quita envoltorios (`sudo`, `env`…), normaliza el programa (ruta y extensión, de modo que `/usr/bin/git` y `git.exe` son `git`), analiza el texto que se ejecuta y marca lo que no entiende. También una lista de denegados con reglas de **subcomando** y una política que solo endurece: deniega antes de consultar a las demás reglas y nunca deja «permitir» lo que no entiende.
  - **HU-11-03**: una regla que sube a «permitir» el texto exacto de los comandos declarados en la tarea.
  - **HU-05-03**: la aprobación «una vez» o «para la sesión», que cubre herramienta y argumentos **exactos**.
  - **HU-11-01**: la zona protegida, que deniega antes que nadie.
  - **HU-02-02**: el recorte de salidas largas.
  - Hoy cualquier `git …` es una llamada al shell de riesgo alto: se pregunta siempre (y sin aprobador se deniega), salvo que esté en la lista de denegados.
- **Falta (esta historia)**:
  1. Clasificar cada llamada a git por su subcomando y sus opciones en **permitir** (lectura), **preguntar** (escritura y lo desconocido) o **denegar** (destructivo).
  2. Que push y merge **nunca** se permitan solos, ni siquiera por una declaración de la tarea.
  3. Que las instrucciones de uso de git (una rama por tarea, commits descriptivos) lleguen al modelo.
  4. Que no se filtren el comando ni credenciales de URLs remotas.

### User Story 1 - El agente consulta el repositorio sin interrupciones (Priority: P1)

El agente pide `git status`, `git diff` o `git log`, solos o encadenados entre sí. Se ejecutan sin preguntar y la salida larga llega recortada.

**Why this priority**: Es AC-01 y el uso más frecuente del Coding Harness: revisar el estado y los cambios antes de verificar y entregar.

**Independent Test**: Con la política real y un shell doble que registra las llamadas, se evalúan los comandos de lectura y sus variantes. Todos dan «permitir», el doble los recibe y una salida larga vuelve recortada con la marca de omisión.

**Acceptance Scenarios**:

1. **Given** el agente pide `git status`, `git diff` o `git log`, **When** la política lo evalúa, **Then** lo permite sin preguntar.
2. **Given** variantes de la misma lectura: ruta completa (`/usr/bin/git`, `C:\Program Files\Git\bin\git.exe`), `git -C sub status`, `git --no-pager log`, `git --git-dir=.git --work-tree=. status`, opciones de lectura (`git diff --stat`, `git log --oneline -5`) y las demás lecturas permitidas (`git show HEAD`, `git blame a.py`, `git branch`, `git branch -a`, `git tag -l`, `git stash list`), **When** se evalúan, **Then** se permiten igual.
5. **Given** una lectura con efectos (`git diff --output=x`, `git log --ext-diff`, `git diff --no-index a b`, `git log > salida.txt`, `GIT_EXTERNAL_DIFF=x git diff`, `GIT_PAGER=x git log`), una lectura que crea (`git branch nueva`, `git tag v1`) o `git add .`, **When** se evalúa, **Then** se pregunta.
3. **Given** `git status && git diff` o `git log | head` en bash, **When** se evalúa, **Then** se permite si todas las partes se permiten; si una parte no es una lectura de git (`git status && ls`), manda la más restrictiva (preguntar).
4. **Given** una salida de `git diff` mayor que el máximo, **When** vuelve al contexto, **Then** llega recortada con `[salida recortada: se omitieron N caracteres]` (HU-01-04, HU-02-02).

---

### User Story 2 - La escritura pide aprobación y lo destructivo se deniega (Priority: P1)

El agente pide `git commit`, `git push` o `git merge`: el usuario decide. Si pide `git reset --hard`, `git clean` o `git push --force`, se deniega sin preguntar.

**Why this priority**: Es AC-02 y V-17. Push y merge siempre piden aprobación.

**Independent Test**: Con la política real, cada subcomando de escritura da «preguntar», cada destructivo da «denegar» con independencia de sus variantes y de su posición en un encadenado, y ninguno llega al shell doble sin aprobación.

**Acceptance Scenarios**:

1. **Given** `git commit -m "mensaje"`, `git push origin main` o `git merge rama`, **When** se evalúan, **Then** se pregunta.
2. **Given** `git reset --hard`, `git reset --hard HEAD~1`, `git clean -fd` o `git push --force`, **When** se evalúan, **Then** se deniegan sin preguntar.
3. **Given** variantes del push forzado (`git push -f`, `git push --force-with-lease`, `git push origin +main`, `git -C x push --force`), **When** se evalúan, **Then** se deniegan.
4. **Given** `git status && git reset --hard`, **When** se evalúa, **Then** se deniega: manda la parte más restrictiva.
5. **Given** un subcomando que no está en ninguna lista (`git frobnicate`) o un alias del usuario (`git st`), **When** se evalúa, **Then** se pregunta: lo desconocido nunca se permite.
6. **Given** prefijos de opciones largas denegadas (`git push --forc`, `git push --force-w`, `git reset --ha`, `git checkout --for`), **When** se evalúan, **Then** se deniegan como la opción completa.
7. **Given** opciones cortas agrupadas (`git clean -fd`, `git clean -n`, `git push -fu origin main`, `git branch -Df rama`, `git checkout -qf main`), **When** se evalúan, **Then** se deniegan.
8. **Given** refspecs forzados (`git push origin +main`, `git push origin +HEAD:main`, `git push origin main +dev`), **When** se evalúan, **Then** se deniegan; `git push origin main` (sin `+`) se pregunta.
9. **Given** las demás variantes destructivas (`git checkout -- a.py`, `git checkout .`, `git restore a.py`, `git switch --discard-changes main`, `git reset --keep HEAD~1`, `git stash drop`, `git push --delete origin rama`, `git push origin :rama`, `git push --mirror`, `git reflog expire --all`, `git gc --prune=now`, `git filter-branch`, `git update-ref -d HEAD`), **When** se evalúan, **Then** se deniegan; `git restore --staged a.py`, `git rebase main`, `git cherry-pick x`, `git revert x`, `git reset HEAD~1` y `git branch -d rama` se preguntan.

---

### User Story 3 - Ninguna otra regla puede soltar un push o un merge (Priority: P1)

Un push o un merge siguen preguntándose aunque la tarea los declare como comando, aunque el usuario haya aprobado otro comando de git para la sesión o aunque vayan disfrazados con opciones globales.

**Why this priority**: Es la frontera de seguridad de V-17 frente a las reglas de HU-11-03 y HU-05-03.

**Independent Test**: Con la composición real (zona protegida, lista de denegados, comandos de la tarea y aprobación de sesión), un push o un merge nunca se ejecutan sin una pregunta propia.

**Acceptance Scenarios**:

1. **Given** una tarea que declara `- pruebas: git push origin main` (HU-11-03), **When** el agente pide ese texto exacto, **Then** se pregunta: la declaración no lo convierte en «permitir».
2. **Given** que el usuario aprobó «para la sesión» `git commit -m "x"`, **When** el agente pide `git push`, **Then** se pregunta (la aprobación cubre solo esos argumentos exactos).
3. **Given** `git -c alias.x=push x`, `git -c core.sshCommand=… push` o cualquier `git -c …`, **When** se evalúa, **Then** como mínimo se pregunta: una configuración en línea puede cambiar lo que git ejecuta.
4. **Given** que el usuario aprobó «para la sesión» un `git push origin main` concreto, **When** el agente pide **el mismo** push exacto, **Then** se ejecuta sin volver a preguntar: la aprobación de sesión cubre ese push exacto (HU-05-03). Cualquier otro push, con argumentos distintos, se pregunta, y un push denegado nunca llega al aprobador. Supuesto pendiente de ratificar por el PO.
5. **Given** un área de trabajo con un repositorio, **When** el agente intenta **escribir** `.git/config` o **leer** `.git/HEAD` con las herramientas de archivos, **Then** las dos llamadas se deniegan (zona protegida). En la misma sesión, `git status` por el shell sigue permitiéndose solo.
6. **Given** que la salida del shell contiene `https://usuario:secreto@servidor/repo.git`, **When** vuelve al modelo, **Then** se ve `https://<secreto oculto>@servidor/repo.git`: no queda ni el usuario ni el secreto.
7. **Given** que la salida contiene `https://ghp_tokenDePrueba@servidor/repo.git` (solo un token), **When** vuelve al modelo, **Then** se ve `https://<secreto oculto>@servidor/repo.git`.
8. **Given** que la salida contiene `https://servidor/repo.git` (una URL sin credenciales), **When** vuelve al modelo, **Then** no cambia.
9. **Given** que la salida no contiene ninguna URL (por ejemplo `On branch main`), **When** vuelve al modelo, **Then** no cambia.

---

### User Story 4 - El modelo sabe cómo usar git en la tarea (Priority: P2)

El modelo recibe, al empezar, las instrucciones de uso de git: una rama por tarea y commits con mensajes descriptivos.

**Why this priority**: Es la regla de negocio 2 (Sp2-44). No es una barrera de seguridad, sino una guía.

**Independent Test**: El prefijo del historial contiene un mensaje de sistema con esas instrucciones.

**Acceptance Scenarios**:

1. **Given** una ejecución con área de trabajo, **When** se arma el prefijo del historial, **Then** incluye un mensaje de sistema que pide una rama por tarea y commits descriptivos, y recuerda que push y merge piden aprobación.

---

### Edge Cases

- **Opciones globales antes del subcomando**:
  - `-C <ruta>`, `--git-dir=<x>` / `--git-dir <x>`, `--work-tree=<x>`, `--no-pager`, `-P`, `--paginate`/`-p`, `--bare`, `--no-replace-objects` y `--literal-pathspecs` se saltan para encontrar el subcomando y no cambian su clase;
  - `-c <clave>=<valor>`, `--config-env`, `--exec-path`, `--namespace` y cualquier otra opción global desconocida dejan la llamada **al menos en preguntar**, porque pueden cambiar lo que git ejecuta;
  - una asignación de variable `GIT_*` delante de git (`GIT_EXTERNAL_DIFF=…`, `GIT_SSH_COMMAND=…`, `GIT_PAGER=…`) deja la llamada al menos en preguntar; otras asignaciones (`LANG=C git log`) no cambian la clase.
- **Alias de git**: el analizador no puede consultar la configuración (`git st` puede ser cualquier cosa). Un subcomando que no está en las listas se pregunta.
- **Lecturas con efectos**: una lectura deja de permitirse sola (pasa a preguntar) si lleva opciones que escriben archivos, leen fuera del repositorio o ejecutan programas: `--output`, `--ext-diff`, `--textconv`, `--no-index`, `-O`/`--open-files-in-pager` en `grep`, o una redirección (`git log > x`). `git diff --no-ext-diff` y `--no-textconv` se permiten. Un prefijo de una de esas opciones (`--out`, `--ext`) cuenta como la opción completa.
- **Listar frente a crear** en `branch`, `tag` y `stash`: se permiten solos `git branch` (sin argumentos o solo con `-a`, `-r`, `-l`/`--list`, `-v`, `-vv`, `--merged`, `--no-merged`, `--contains`, `--show-current`), `git tag` (sin argumentos o con `-l`/`--list`, `-n`) y `git stash list`. Cualquier otro argumento (un nombre nuevo, `-m`, `-d`…) los convierte en escritura (preguntar) o en destructivos (`branch -D`, `stash drop`/`clear`: denegar).
- **Configuración del repositorio que ejecuta programas**: `git status` o `git diff` pueden ejecutar comandos definidos en `.git/config` (por ejemplo `core.fsmonitor`, `core.pager`, `diff.external`, filtros). Para que permitir lecturas sea seguro, las herramientas de archivos del agente no pueden escribir dentro de la carpeta `.git` del área de trabajo; tampoco leerla (limitación conocida, FR-009). Por el shell, escribir en `.git` ya se pregunta, porque no es una lectura de git.
- **Encadenados**: cada parte se clasifica por separado y manda la más restrictiva (HU-05-02): denegar > preguntar > permitir.
- **Lo que el analizador no entiende** (`git $(echo push)`, `git log "$X"`, comillas sin cerrar): se pregunta, nunca se permite (HU-05-02, V-17).
- **PowerShell**: las mismas reglas con `git` y `git.exe`. Las opciones de git distinguen mayúsculas (`git status` y `git STATUS` no son lo mismo para git; el segundo es desconocido → preguntar).
- **Credenciales en URLs**: un comando con `https://usuario:secreto@servidor/...` (por ejemplo en `git push` o `git clone`) nunca aparece en eventos ni en mensajes de error. En la salida del shell que vuelve al modelo, las credenciales de cualquier URL (`esquema://usuario:secreto@` y `esquema://token@`) se sustituyen por `<secreto oculto>` (FR-011). Una URL sin credenciales y un texto sin URL no cambian. `git remote -v` y `git config --get remote.*.url` no se permiten solos.
- **Subcomandos destructivos además de los de la ficha**: los de la Clarificación (Q2) se deniegan; `rebase`, `cherry-pick`, `revert`, `reset` sin `--hard` y `branch -d` se preguntan.
- **Opciones de git**: un prefijo de una opción larga cuenta como la opción completa (`--forc` es `--force`, `--ha` es `--hard`); si es prefijo de una opción denegada, se deniega aunque también pudiera serlo de otra. Las opciones cortas agrupadas se separan (`-fd` = `-f -d`). `--` separa las opciones de las rutas (`git checkout -- a.py` es destructivo).
- **Lecturas permitidas más allá de status, diff y log**: las de la Clarificación (Q1); ninguna otra.
- **Subcomandos de escritura local o remota** que no destruyen (`add`, `commit`, `checkout -b`, `checkout <rama>`, `switch -c`, `switch <rama>`, `branch <nueva>`, `fetch`, `pull`, `merge`, `push`, `stash` y `stash push/pop/apply`, `tag <nuevo>`, `init`, `clone`, `rm`, `mv`, `config`, `remote`…): se preguntan.
- **Un `git` dentro de otro intérprete** (`bash -c "git push"`) ya no se entiende (HU-05-02), así que se pregunta; si contiene una variante destructiva, se deniega.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Cada parte de un comando del shell cuyo programa es git, normalizado por el analizador de HU-05-02 (ruta, extensión, envoltorios), DEBE clasificarse por su **subcomando**, encontrado tras saltar las opciones globales conocidas, y por sus opciones, en una de tres clases: **lectura** (permitir), **escritura** (preguntar) o **destructiva** (denegar).
- **FR-002**: Son de **lectura**, y solo ellas, `status`, `diff`, `log` (AC-01), `show`, `blame`, `shortlog`, `describe`, `rev-parse`, `ls-files`, `grep` (sin `-O`/`--open-files-in-pager`), y `branch`, `tag` y `stash list` cuando solo listan (Edge Cases). Una lectura deja de serlo, y pasa a preguntar, si lleva `--output`, `--ext-diff`, `--textconv`, `--no-index` (o un prefijo de ellas), una redirección o una asignación `GIT_*` delante.
- **FR-003**: Son **destructivas**, y se deniegan sin preguntar (AC-02):
  - `reset --hard`, `reset --merge` y `reset --keep`;
  - `clean`, con cualquier opción, incluido `-n`;
  - todo push forzado (`-f`, `--force`, `--force-with-lease`, `--force-if-includes`, un refspec que empieza por `+`) y `push --delete`, `push <remoto> :<rama>` y `push --mirror`;
  - `checkout -f` (`--force`) y `checkout` con `--` o con rutas que descartan cambios (`checkout -- a.py`, `checkout .`);
  - `restore` sin `--staged` (o con `--worktree`) y `switch --discard-changes` (o `-f`/`--force`);
  - `branch -D` (o `--delete --force`, `-df`), `stash drop` y `stash clear`;
  - `reflog expire`, `gc --prune=now`, `filter-branch` y `update-ref -d`.
- **FR-003a**: Coincidencia de opciones:
  - (a) un prefijo de una opción larga cuenta como la opción completa y, si es prefijo de una opción denegada, se deniega;
  - (b) las opciones cortas agrupadas se separan;
  - (c) `--` separa opciones de rutas;
  - (d) las opciones globales conocidas se saltan para encontrar el subcomando (FR-006).
- **FR-004**: `commit`, `push` y `merge` DEBEN preguntar siempre (AC-02, V-17). Ninguna otra regla puede convertirlos en «permitir»: ni la declaración de un comando de la tarea (HU-11-03), ni una lectura encadenada, ni una opción global.
- **FR-005**: Todo subcomando que no sea de lectura ni destructivo DEBE preguntar: `commit`, `push`, `merge`, `add`, crear ramas (`switch -c`, `checkout -b`, `branch <nombre>`), `rebase`, `cherry-pick`, `revert`, `reset` sin `--hard`, `branch -d`, y cualquier subcomando desconocido o alias del usuario. Lo desconocido nunca se permite.
- **FR-006**: Las opciones globales `-c`, `--config-env`, `--exec-path`, `--namespace` y cualquier opción global desconocida, así como una asignación `GIT_*` delante de git, DEBEN dejar la llamada como mínimo en «preguntar» (nunca la vuelven destructiva si no lo era, ni la sacan de destructiva si lo era). Las conocidas sin efectos (`-C`, `--git-dir`, `--work-tree`, `--no-pager`, `-P`, `-p`/`--paginate`, `--bare`, `--no-replace-objects`, `--literal-pathspecs`) no cambian la clase.
- **FR-007**: La regla de git DEBE respetar el orden de HU-05-02, denegar > preguntar > permitir. Una parte destructiva deniega el comando entero; una denegación de la lista base, de la zona protegida o de la lista `deny` de herramientas nunca se afloja; lo que el analizador no entiende se pregunta. La única subida a «permitir» que añade esta historia es la de las lecturas de git, y solo si todas las partes del comando son lecturas permitidas (o se permiten por otra regla).
- **FR-008**: Una aprobación de sesión (HU-05-03) DEBE cubrir solo la llamada con los mismos argumentos: aprobar `git commit -m "x"` no autoriza ningún `git push`. Un push o un merge idénticos a uno aprobado para la sesión pueden reutilizar esa aprobación (supuesto pendiente del PO); una llamada denegada nunca llega al aprobador. `core/permissions/approvals.py` no cambia.
- **FR-009**: Las herramientas de archivos del agente NO DEBEN poder escribir dentro de la carpeta `.git` del área de trabajo (se deniega), para que la configuración del repositorio no pueda hacer que una lectura permitida ejecute programas. Se hace como **dato** desde `bootstrap.py` (carpeta protegida de HU-11-01), sin cambiar `protected.py` ni `protected_paths.py`. **Limitación conocida y aceptada**: como la zona protegida no distingue lectura de escritura, las herramientas de archivos tampoco pueden leer `.git`. El agente usa `git status`, `log` y `show`, que se permiten solos.
- **FR-010**: El modelo DEBE recibir al empezar un mensaje de sistema con las instrucciones de uso de git (una rama por tarea, commits descriptivos, push y merge piden aprobación) cuando hay área de trabajo (regla de negocio 2, Sp2-44).
- **FR-011**: Ni los eventos ni los mensajes de error DEBEN contener el comando. La salida del shell que vuelve al modelo, y los eventos que la lleven, DEBEN ocultar las credenciales de las URLs: `esquema://usuario:secreto@host` y `esquema://token@host` pasan a `esquema://<secreto oculto>@host`, con el marcador existente. Una URL sin credenciales y un texto sin URL no cambian. Lo hace **una única función pequeña y pura**, en un solo lugar con nombre claro, que no duplica el depurador del adaptador LiteLLM y que HU-10-02 debe absorber.
- **FR-012**: La salida larga de un comando de git permitido DEBE llegar recortada con la marca de omisión (AC-01; comportamiento existente de HU-01-04 y HU-02-02).
- **FR-013**: La clasificación DEBE ser pura y determinista: no ejecuta git, no lee la configuración de git, no consulta alias ni el estado del repositorio.
- **FR-014**: Una prueba con **git real** sobre un repositorio temporal aislado (Sp2-45; reglas en la Clarificación) DEBE comprobar que `status`, `diff` y `log` no cambian el estado del repositorio y que su salida larga se recorta. Ninguna prueba ejecuta un comando que la política pregunte o deniegue.

### Key Entities

- **Clase de una llamada a git**: lectura (permitir), escritura (preguntar) o destructiva (denegar). Se obtiene del subcomando, de sus opciones y de las opciones globales.
- **Tabla de subcomandos**: para cada subcomando conocido, su clase base y las opciones que lo hacen destructivo (por ejemplo `--hard` en `reset`) o lo sacan de la lectura (por ejemplo `--output` en `diff`). Es inmutable y está pendiente de la revisión del PO.
- **Instrucciones de git**: texto fijo en español que el modelo recibe en el prefijo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En una batería de al menos 20 lecturas de git por plataforma (bash y PowerShell), con variantes de ruta, extensión, opciones globales conocidas y encadenados de lecturas, el 100 % se permite sin preguntar.
- **SC-002**: En una batería de al menos 20 variantes destructivas por plataforma (opciones en otro orden, `-f`, `+refspec`, opciones globales delante, encadenadas con lecturas), el 100 % se deniega y ninguna llega al shell.
- **SC-003**: En una batería de al menos 15 escrituras, subcomandos desconocidos, alias y llamadas con `-c` por plataforma, el 0 % se permite sin preguntar, tampoco cuando la tarea los declara como comando.
- **SC-004**: Con la composición real y una aprobación de sesión de `git commit`, el 0 % de los `git push` o `git merge` se ejecuta sin una pregunta propia.
- **SC-005**: En el 100 % de los casos con una URL con credenciales (usuario y secreto, o solo token), ni los eventos ni los mensajes de error contienen el comando, y el resultado del shell que vuelve al modelo no contiene ni el usuario ni el secreto. En el 100 % de las URLs sin credenciales y de los textos sin URL, la salida no cambia.
- **SC-006**: Sin comandos de git, el 100 % de las pruebas existentes de la política, la lista de denegados, los comandos de la tarea y la aprobación siguen pasando sin cambiar sus aserciones.
- **SC-007**: En un repositorio temporal real (Sp2-45), tras ejecutar `status`, `diff` y `log`, el estado del repositorio (HEAD, índice, árbol de trabajo y ramas) es idéntico al de antes, y una salida de `log` mayor que el máximo llega recortada con la marca de omisión.

## Assumptions

- HU-01-04 y HU-05-02 están integradas en `origin/main` (61024bf, que incluye la spec 026), pero ninguna está `Hecha`. HU-11-02 está `Pendiente` en PROGRESO y ninguna rama remota la tiene en curso.
- **Responsable B (Estado)**. Si la implementa otra área, la revisión cruzada la hace alguien de A o C (otra área distinta de B). Las tareas humanas son:
  - revisión cruzada;
  - revisión del PO de la tabla de subcomandos (lecturas permitidas y destructivas);
  - visto bueno de C a la regla en `core/permissions/` y a la protección de `.git` (piezas de C);
  - avisar al responsable de HU-10-02 de la función de ocultado de credenciales en URLs que debe absorber;
  - CI remota en Linux y Windows.

  Si el plan tocara `config.py`, haría falta además el visto bueno de B. No está previsto: las reglas de git no se configuran.
- **Sp2-45 («pruebas sobre un repositorio temporal»)**: con git real, en una carpeta temporal y un entorno aislado, ejecutando solo `init`, `add`, `commit`, `status`, `diff` y `log` (FR-014). Los comandos que se preguntan o se deniegan se prueban solo contra la política y un shell doble que registra las llamadas.
- **Limitación conocida (FR-009)**: las herramientas de archivos no pueden leer ni escribir `.git` del área de trabajo; el agente usa `git status`, `log` y `show`.
- **Para HU-10-02 (redacción de secretos)**: la función de ocultado de credenciales en URLs de esta historia es la primera genérica y HU-10-02 debe absorberla; se anota en PROGRESO.
- **Supuesto pendiente de ratificar por el PO (Q3)**: un push o un merge idénticos a uno aprobado para la sesión se ejecutan sin volver a preguntar (comportamiento de HU-05-03); la lectura literal de V-17 pediría aprobar siempre.
- No se cambian los puertos de `core/interfaces/`, el catálogo de eventos, `core/loop.py` ni `core/permissions/approvals.py` (salvo que la pregunta del escenario 4 de la US3 se resuelva con la opción B, que requeriría acuerdo). La regla de git vive en la política y se conecta en la raíz de composición, igual que `CommandPolicy` y `ExactCallPolicy`.
- La protección de `.git` frente a la escritura de las herramientas de archivos es una ampliación de la zona protegida (solo escritura). No protege frente a un shell arbitrario: eso sigue siendo PD-06 / HU-IN-02 (R-21).
- Fuera de alcance: ejecutar en las pruebas cualquier subcomando de git distinto de `init`, `add`, `commit`, `status`, `diff` y `log`, flujos de PR y de rama (crear PR, nombrar ramas), mostrar el motivo de una denegación, generalizar las aprobaciones de sesión, redactar secretos que no estén en URLs (HU-10-02, PD-10) y cualquier cambio de puertos o de `core/loop.py`.
- Presupuesto del sprint: 4 h (Sp2-43 a Sp2-45). Es un aviso, no motivo para recortar alcance.
