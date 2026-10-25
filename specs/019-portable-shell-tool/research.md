# Research: HU-01-04 — Herramienta de shell portable con tiempo límite

Fecha: 2026-10-24. No quedan `NEEDS CLARIFICATION`. Lo marcado **(sonda)** se midió en este equipo (Windows 10, Windows PowerShell 5.1, Python 3.14 solo para la sonda; el proyecto usa 3.12); lo marcado **(por verificar en CI)** solo se puede confirmar en `ubuntu-latest`.

## R1. Cómo invocar PowerShell sin perder texto, acentos ni código de salida

- **Decisión**: `powershell.exe -NoLogo -NoProfile -NonInteractive -Command <guion>` (o `pwsh` si está en el `PATH`), con un guion de tres partes: preludio (`$ProgressPreference='SilentlyContinue'`, `[Console]::OutputEncoding` y `$OutputEncoding` en UTF-8), el comando del modelo y un epílogo que sale con `$LASTEXITCODE` si es distinto de cero, o con 1 si el último paso falló (`$?` falso).
- **Sonda (Windows PowerShell 5.1)**: `-EncodedCommand` con stderr redirigido emite `#< CLIXML <Objs …>` ante cualquier error, y `-OutputFormat Text` / `-InputFormat None` no lo evitan; `-Command` entrega el texto del error legible. Con `-Command`: `echo 'áéñ ü 中'` vuelve intacto (UTF-8), `exit 3` → 3, `cmd /c exit 5` → 5, un ejecutable nativo con `sys.exit(7)` → 7 y `Get-Item inexistente` → 1.
- **Rationale**: es la forma más simple que cumple FR-009 y los tres criterios de arriba sin archivos temporales.
- **Alternativas**: `-EncodedCommand` (descartado por el XML); `-File` con un `.ps1` temporal (más estado en disco y política de ejecución); `-Command -` leyendo de la entrada (mezcla el guion con la entrada del comando, que debe estar cerrada).
- **Limitación aceptada**: ante un error de PowerShell, el mensaje cita el guion (incluye el preludio). No contiene secretos (el guion es nuestro más el comando que el modelo escribió) y solo ocurre en errores.

## R2. Cómo invocar bash

- **Decisión**: `bash --noprofile --norc -c <command>` con el ejecutable encontrado en el `PATH`. Sin modo interactivo ni perfiles (FR-009).
- **Rationale**: reproducible; no depende de `~/.bashrc`. `-c` entrega el código de salida del último comando.
- **Alternativas**: `sh -c` (no es bash: AC-02 pide bash); `bash -lc` (carga perfiles y cambia el `PATH`).
- **Nota Windows**: en Windows `shutil.which("bash")` puede devolver Git Bash o el `bash.exe` de WSL; **no** se usa en Windows (la elección es PowerShell). Las pruebas reales de bash se omiten en Windows con motivo.

## R3. Terminar el árbol de procesos

- **POSIX**: `Popen(start_new_session=True)` crea un grupo propio; `os.killpg(pgid, SIGTERM)` → espera `grace_seconds` → `os.killpg(pgid, SIGKILL)`. Tras una salida normal también se envía `SIGKILL` al grupo para no dejar procesos en segundo plano (p. ej. `sleep 100 &`), pues mantienen abierta la tubería de salida. **(por verificar en CI)**; D-01 midió `SIGTERM` ignorado → `-9` en WSL2.
- **Windows**: `creationflags=CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW`; paso amable: `send_signal(CTRL_BREAK_EVENT)`; paso forzado: `taskkill /PID <pid> /T /F` (el binario `taskkill.exe` viene con Windows). `Popen.kill()` solo mata el proceso directo, por eso no basta.
- **Límite**: `taskkill /T` recorre la relación padre-hijo viva; un proceso cuyo padre ya murió (huérfano) escapa. Los Job Objects (`ctypes`) lo cierran del todo; se deja como mejora posterior porque exige código específico de Windows sin forma de cubrirlo en Linux y el riesgo está aceptado mientras el shell tenga aprobación obligatoria.
- **Alternativas**: `psutil` (dependencia nueva; Principio III); Job Objects ahora (mayor coste y riesgo, sin mejora visible en esta historia).

## R4. Leer la salida sin bloquear y acotar la memoria

- **Decisión**: un hilo lector llama a `read1(65536)` sobre la tubería, decodifica con un decodificador incremental UTF-8 (`errors="replace"`) y alimenta un `OutputCollector` que cuenta los caracteres totales y retiene solo la cabeza y la cola. El hilo llamador espera `proc.wait(timeout)`; al terminar (o al terminar el árbol) espera al lector unos segundos y, si el lector no cierra, deja de esperarlo (hilo demonio).
- **Rationale**: evita el bloqueo clásico de `communicate` con salida enorme y mantiene la memoria en unos `2 × max_output_chars` caracteres (SC-002). El decodificador incremental no corta un carácter multibyte entre lecturas.
- **Alternativas**: `communicate(timeout)` (acumula toda la salida); redirigir a un archivo temporal (E/S extra y limpieza); `asyncio.create_subprocess_exec` (el puerto es síncrono y no cambia).

## R5. Salida combinada y orden

- `stderr=STDOUT` entrega una sola corriente en orden de llegada del sistema operativo (sin intercalado exacto garantizado). Se documenta en la spec (caso límite).

## R6. Entrada estándar y consola

- `stdin=DEVNULL`: un comando que lee la entrada recibe fin de archivo y no cuelga la sesión (US1-6). En Windows, `CREATE_NO_WINDOW` evita abrir ventanas. Sin `shell=True`: el intérprete se invoca con una lista de argumentos.

## R7. Entorno del hijo

- **Decisión (responsable, 2026-10-24)**: copia del entorno sin las claves de los proveedores. `config.PROVIDER_KEY_VARIABLES` ya tiene la lista; `bootstrap.py` pasa `{valor for valor in … if valor}` y el entorno; el adaptador no lee `os.environ` ni importa `config` (la guarda lo prohíbe). En Windows el nombre se compara sin distinguir mayúsculas.
- **Límite documentado**: solo se quitan las claves conocidas del harness; no hay lista general de secretos (PD-10 abierta).

## R8. Dónde vive el texto del entorno (prefijo)

- **Decisión**: función pura en `adapters/system/environment_notice.py`; la raíz de composición lo inserta como primer mensaje de sistema. Un texto fijo por (sistema, intérprete) es estable byte a byte (importa para el caché de prefijo del proveedor).
- **Alternativa descartada**: ponerlo en `core/` (obligaría a exportarlo y a coordinar con B/HU-02-01 sin necesidad). HU-02-01 (área B) podrá moverlo al ensamblador del contexto.
- **Texto** (ver `contracts/shell_tool_contract.md`): sistema operativo, intérprete, que cada llamada a `shell` es independiente (no se conservan carpeta ni variables) y que la herramienta termina el comando al agotar el tiempo.

## R9. Lista de comandos denegados por plataforma (dato)

- **Decisión (responsable)**: solo dato, sin aplicarla. Forma: `DeniedCommand(pattern, reason)` por intérprete; el patrón es un fragmento literal de texto, la comparación (mayúsculas, separación de comandos compuestos) es de HU-05-02. Contenido inicial conservador: bash (`rm -rf /`, `rm -rf ~`, `mkfs`, `dd if=`, fork bomb, `shutdown`, `reboot`, `chmod -R 777 /`) y PowerShell (`Remove-Item … -Recurse -Force` sobre la raíz de una unidad, `Format-Volume`, `Clear-Disk`, `Stop-Computer`, `Restart-Computer`, `Set-ExecutionPolicy`, `reg delete`). Revisión del PO pendiente; no sustituye a la aprobación.

## R10. Qué pasa con `Tool.run` async y el puerto síncrono

- `asyncio.to_thread(shell.execute, command, timeout)`. Mientras corre el comando el bucle de eventos sigue libre (el bus puede entregar eventos). Cancelar el turno no interrumpe el hilo; el tiempo máximo acota la espera. Es una limitación del puerto sin cancelación: se anota como hallazgo para A (D-01 dice que `Shell` es síncrono).
- Alternativa descartada: añadir `cancel()` al puerto (requiere acuerdo de A, B y C).

## R11. Límites iniciales

| Constante | Valor | Dónde | Motivo |
|---|---|---|---|
| `DEFAULT_TIMEOUT_SECONDS` | 120 | `adapters/tools/_limits.py` | Suficiente para pruebas y Git; el modelo puede pedir más hasta el tope |
| `MAX_TIMEOUT_SECONDS` | 600 | `adapters/tools/_limits.py` | Tope que garantiza que la sesión no se bloquea indefinidamente |
| `MAX_COMMAND_CHARS` | 8 000 | `adapters/tools/_limits.py` | Muy por debajo del límite de la línea de comandos de Windows (32 767) |
| `MAX_OUTPUT_CHARS` | 20 000 | `adapters/system/shell_limits.py` | Igual que `MAX_RESULT_CHARS` de las herramientas de archivos (alinear con HU-02-02) |
| `NOTICE_RESERVE_CHARS` | 160 | `adapters/system/shell_limits.py` | Espacio fijo para el aviso de recorte, de modo que el total no supere el máximo |
| `GRACE_SECONDS` | 2.0 | `adapters/system/shell_limits.py` | Tiempo entre la petición amable y la forzada |
| `READER_JOIN_SECONDS` | 2.0 | `adapters/system/shell_limits.py` | Espera máxima al hilo lector tras terminar el árbol |

Duplicar `max` de timeout entre paquetes no hay: el tope de tiempo es solo de la herramienta; el máximo de salida es solo del adaptador.

## R12. Hallazgos para otras áreas (no se cambian aquí)

1. **A (puertos)**: `Shell.execute` es síncrono, sin carpeta de trabajo, entorno ni cancelación; se resolvió por constructor. Si se quiere cancelar un comando a mitad de turno, hay que ampliar el puerto con acuerdo de A, B y C.
2. **B (HU-02-01, `config.py`)**: el prefijo provisional lo coloca `bootstrap.py`; los límites del shell y los nombres de claves a quitar podrían ir a `config.py` (ya anotado en PROGRESO).
3. **C / HU-05-02**: consume `DEFAULT_DENIED_COMMANDS`; el shell es riesgo alto sin `path`, así que hoy la política siempre pregunta.
4. **HU-02-02**: el recorte propio de `shell` (cabeza + cola + aviso) puede quedar redundante con el recorte general del registro.
