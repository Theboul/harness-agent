# Contrato: `GitPolicy`, `classify_git`, `git_instructions` y `hide_url_credentials`

## API pública (`harness_agent.core`)

```python
class GitClass(str, Enum): READ = "lectura"; ASK = "preguntar"; DENY = "denegar"

def classify_git(part: CommandPart, *, risky_environment: bool = False) -> GitClass: ...
def git_instructions() -> str: ...

class GitPolicy(PermissionPolicy):
    def __init__(self, inner: PermissionPolicy, *, dialect: Dialect, tool: str,
                 argument: str, deny_names: Sequence[str] = (),
                 ask_names: Sequence[str] = ()) -> None: ...
    def evaluate(self, call: ToolCall) -> PermissionDecision: ...

HIDDEN_SECRET = "<secreto oculto>"
def hide_url_credentials(text: str) -> str: ...
```

## Garantías

1. **Solo un camino a `ALLOW`**: todas las partes del comando son lecturas git de la tabla, el comando se entendió y no hay `executable` ni redirecciones. Lo vigila la guarda `tests/architecture/test_git_rules_boundaries.py`: `PermissionDecision.ALLOW` aparece una sola vez, dentro de `if self._only_reads(...) is True:`.
2. **Push y merge nunca se permiten solos**: toda parte git de clase `ASK` devuelve `ASK` sin consultar a `inner` (ni a `ExactCallPolicy`).
2a. **Las listas de herramientas mandan** (HU-05-01; ajuste de la implementación, T006). Las listas `deny` y `ask` de la configuración llegan por constructor (`deny_names`, `ask_names`) y se aplican sin consultar a `inner`. Con la herramienta en `deny`, toda llamada con partes git se deniega; con ella en `ask`, ninguna se permite sola. Sin esto, la garantía 2 habría aflojado la lista `deny` (FR-007).
3. **Denegar gana**: una parte git destructiva en cualquier nivel (encadenada, en `$( )`, en `bash -c`) deniega el comando entero.
4. **Falla cerrada**: una excepción al analizar da `ASK`; una excepción o valor raro de `inner`, o una llamada mal formada, dan `DENY`. Todo `except` del módulo devuelve `ASK` o `DENY`.
5. **Sin E/S ni estado**: los módulos solo usan la biblioteca estándar y el núcleo (sin `os`, `subprocess`, `shlex`, `adapters`, `config`); ningún método salvo `__init__` asigna atributos de `self`. No nombran `"shell"`, `"command"` ni `"timeout_seconds"`, porque la herramienta llega por constructor.
6. **Sin filtrar datos**: ni el comando ni las credenciales aparecen en excepciones ni en decisiones. `hide_url_credentials` se aplica a la salida del shell.

## Cableado en `bootstrap.compose()`

```text
policy = ProtectedPolicy(
    CommandPolicy(
        GitPolicy(
            ExactCallPolicy(DefaultPermissionPolicy(registry, area, config.permissions),
                            allowed, ask_names=config.permissions.ask),
            dialect=deny_list.dialect, tool=shell_tool.name, argument=COMMAND_ARGUMENT,
            deny_names=config.permissions.deny, ask_names=config.permissions.ask),
        deny_list, tool=shell_tool.name, argument=COMMAND_ARGUMENT),
    protected, markers)          # protected incluye workspace/.git cuando hay área
history_prefix = (environment_notice, git_instructions() si hay área, commands_notice si hay comandos)
```

## Ejemplos normativos (también son pruebas; `inner` = `ASK` salvo que se indique)

| Comando (bash; los mismos en PowerShell con `git`/`git.exe`) | Resultado |
|---|---|
| `git status` · `git diff --stat` · `git log --oneline -5` · `/usr/bin/git status` · `git -C sub status` · `git --no-pager log` · `git --git-dir=.git --work-tree=. status` | `ALLOW` |
| `git show HEAD` · `git blame a.py` · `git branch` · `git branch -a` · `git tag -l` · `git stash list` · `git status && git diff` | `ALLOW` |
| `git status && ls` · `git log \| head` | `inner` (aquí `ASK`) |
| `git commit -m "x"` · `git push origin main` · `git merge rama` · `git add .` · `git switch -c nueva` · `git checkout -b nueva` · `git branch nueva` · `git rebase main` · `git st` · `git frobnicate` | `ASK` (también con `inner` = `ALLOW`) |
| `git -c alias.x=push x` · `git -c core.pager=less log` · `git --exec-path=/x status` · `GIT_EXTERNAL_DIFF=x git diff` · `git diff --output=x` · `git log --ext-diff` · `git diff --no-index a b` · `git log > x` · `git grep -O foo` | `ASK` |
| `git reset --hard` · `git reset --ha` · `git clean -n` · `git clean -fd` · `git push --force` · `git push --forc` · `git push -fu origin main` · `git push origin +main` · `git push origin :rama` · `git push --mirror` | `DENY` |
| `git checkout -- a.py` · `git checkout .` · `git checkout -f` · `git restore a.py` · `git switch --discard-changes main` · `git branch -D x` · `git branch -Df x` · `git stash drop` · `git reflog expire --all` · `git gc --prune=now` · `git filter-branch` · `git update-ref -d HEAD` · `git status && git reset --hard` · `bash -c "git push --force"` | `DENY` |
| `git restore --staged a.py` · `git reset HEAD~1` · `git branch -d x` · `git cherry-pick x` · `git revert x` | `ASK` |

| Texto | `hide_url_credentials` |
|---|---|
| `https://usuario:secreto@servidor/r.git` | `https://<secreto oculto>@servidor/r.git` |
| `https://tokenDePrueba@servidor/r.git` | `https://<secreto oculto>@servidor/r.git` |
| `https://servidor/r.git` | sin cambios |
| `On branch main` | sin cambios |
