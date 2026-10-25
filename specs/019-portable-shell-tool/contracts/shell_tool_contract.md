# Contrato: herramienta `shell` y texto de entorno (HU-01-04)

Contrato de lo que ven el modelo, la política y la raíz de composición. No cambia ningún puerto.

## 1. Herramienta `shell` (lo que ve el modelo)

| Aspecto | Valor |
|---|---|
| Nombre | `shell` |
| Riesgo | `RiskLevel.HIGH` (la política pregunta siempre; sin aprobador se deniega) |
| Argumentos | `command` (texto, 1–8 000 caracteres, obligatorio); `timeout_seconds` (número, 1–600, opcional, por defecto 120) |
| Otros campos | Rechazados (`additionalProperties: false`) |
| Argumento `path` | No existe; la convención de rutas de HU-05-01 no aplica |
| Carpeta de partida | Raíz del área de trabajo; cada llamada es independiente (no se conservan carpeta ni variables) |
| Entrada estándar | Cerrada |
| Entorno | El del harness sin `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY` |

### Resultado (`ToolResult.content`)

| Situación | `is_error` | Contenido |
|---|---|---|
| Código de salida 0 | falso | `Código de salida: 0` + salto + salida (o `(sin salida)`) |
| Código de salida N ≠ 0 | verdadero | `[codigo_de_salida=N] El comando terminó con error.` + salto + salida |
| Tiempo agotado | verdadero | `[tiempo_agotado] El comando superó los T s y se terminó (junto con sus procesos hijos).` + salto + salida parcial |
| Intérprete no disponible o no arranca | verdadero | `[interprete_no_disponible] No se pudo iniciar el intérprete (bash\|powershell). Revisa que esté instalado.` |
| Sin área de trabajo | verdadero | `[sin_area] No hay un área de trabajo configurada, así que no se puede ejecutar el comando. Configura 'workspace_root' en config.toml.` |
| Otra excepción | verdadero | `[error_de_shell] El comando no se pudo ejecutar.` (sin texto de la excepción) |

La salida es la salida estándar y la de errores combinadas, en UTF-8 con sustitución, de **a lo sumo 20 000 caracteres**. Si el total superó ese máximo, la salida es `cabeza + "\n[salida recortada: se omitieron N caracteres]\n" + cola`.

Nunca contiene trazas, rutas del ejecutable ni el comando repetido.

## 2. Texto de entorno (prefijo)

`environment_notice(system_name, interpreter)` devuelve, para `("Windows", "powershell")` y `("Linux", "bash")`, un texto con esta forma (fijo, en español, sin datos de la máquina):

```
Entorno de ejecución: sistema operativo {Windows|Linux}; la herramienta 'shell' usa {PowerShell|bash}.
Escribe los comandos con la sintaxis de {PowerShell|bash}. Cada llamada a 'shell' es independiente:
no se conservan la carpeta actual ni las variables entre llamadas. Un comando que supere el tiempo
máximo se termina y se informa.
```

Reglas: mismo par de entradas → mismo texto, byte a byte; no menciona usuario, rutas ni variables de entorno.

`bootstrap.py` lo coloca como `Message(role=Role.SYSTEM, content=<texto>)`, primer elemento de `Composition.history_prefix` y de `history` en `run_session`.

## 3. Elección del intérprete

| Entrada (`system_name`) | `interpreter_name` | Implementación |
|---|---|---|
| `Windows` | `powershell` | `PowerShellShell` |
| `Linux` | `bash` | `BashShell` |
| cualquier otro | `bash` | `BashShell` (sin garantía) |

## 4. `Shell.execute` (contrato del puerto, sin cambios)

| Entrada | Resultado |
|---|---|
| `timeout_seconds` ≤ 0 o no numérico | `ValueError` (la herramienta nunca lo permite) |
| Intérprete ausente / fallo al arrancar | `ShellStartError` (subclase de `OSError`) |
| Termina a tiempo | `ShellResult(exit_code=<código>, output=<salida acotada>, timed_out=False)` |
| Agota el tiempo | `ShellResult(exit_code=<código tras terminar>, output=<salida parcial acotada>, timed_out=True)`; el árbol de procesos termina |

## 4b. Cancelación

Si la llamada a `ShellTool.run` se cancela mientras el comando corre, la herramienta invoca una vez el gancho `on_cancel` (en la composición real, `SubprocessShell.terminate_running`) y relanza `CancelledError`. El gancho termina el árbol de procesos; el hilo del shell vuelve pronto.

## 5. Lista de comandos denegados (dato)

`denied_commands_for("bash" | "powershell") -> tuple[DeniedCommand, ...]`. Datos de solo lectura; ni el shell ni la herramienta los aplican. Los consume HU-05-02.

## 6. Garantías de seguridad

- Riesgo alto sin `path`: `DefaultPermissionPolicy` pregunta; el bucle resuelve «pregunta» como denegado sin aprobador (`[approval_required_unavailable]`); ningún proceso se lanza.
- La herramienta no aplica ni sustituye a la política; el área solo fija la carpeta de partida.
- Las claves de proveedor del harness no están en el entorno del hijo.
