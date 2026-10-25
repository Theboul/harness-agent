# Contrato: política de protección (`ProtectedPolicy`)

`evaluate(call)` → `PermissionDecision`:

1. Si `call` no es válida o ocurre cualquier excepción → `DENY`.
2. Si `call.arguments["path"]` es texto y `area.contains(path)` es `True` → `DENY` (cualquier herramienta, lectura o escritura).
3. Si `call.name == "shell"` y `call.arguments["command"]` es texto que, en minúsculas y con `\` convertido en `/`, contiene algún marcador → `DENY`.
4. En otro caso → `inner.evaluate(call)` sin cambios.

Marcadores que entrega `bootstrap.py`: nombre del archivo de la base de datos, nombre de la copia (`criterios.json`) y, si la carpeta del harness se protege entera, su nombre (`.harness`).

**Limitación declarada (regla 6, HU-05-02, HU-IN-02)**: no se interpretan comandos compuestos, variables de entorno, comodines, codificaciones ni enlaces creados por el propio comando. Esta política **no** demuestra aislamiento ante un shell con los mismos privilegios (AC-03, PD-06).
