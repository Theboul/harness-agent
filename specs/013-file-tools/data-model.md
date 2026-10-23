# Data Model: HU-01-03 — Herramientas de archivos

No hay persistencia propia. Todo vive en el disco del área y en memoria durante una llamada.

## `WorkspaceArea` (`adapters/system/workspace_area.py`)

| Elemento | Tipo | Descripción |
|---|---|---|
| `WorkspaceArea(root, *, windows=None)` | constructor | `root`: carpeta existente (`str` o `Path`); `windows`: fuerza o desactiva la clasificación de Windows (por defecto `os.name == "nt"`) |
| `root` | `Path` | Ruta real y absoluta de la carpeta autorizada |
| `contains(path)` | `bool` | `True` solo si la ruta real de `path` queda dentro de `root` |

Reglas de construcción: `root` debe existir y ser carpeta; se guarda su ruta real. Si no, `ValueError` con mensaje en español.

Reglas de `contains(path)` (en orden; la primera que falla devuelve `False`; nunca lanza):
1. `path` es `str` o `Path`, no vacío y sin carácter nulo.
2. Con `windows` verdadero, `windows_path_problem(texto)` no devuelve un problema.
3. Si no es absoluta, se une a `root`.
4. Se calcula la ruta real (`realpath` no estricta) y se normalizan las mayúsculas del sistema (`normcase`).
5. `commonpath([root, real]) == root` (la raíz cuenta como dentro).
6. Cualquier excepción → `False`.

## `windows_path_problem(raw) -> str | None`

Función pura. Devuelve la causa (texto corto en español) o `None`:

| Causa | Ejemplo |
|---|---|
| Ruta UNC o de dispositivo | `\\servidor\recurso`, `//servidor/x`, `\\?\C:\x`, `\\.\COM1` |
| Flujo alterno de datos | `notas.txt:flujo`, `C:\area\a.txt:zone` |
| Nombre de dispositivo reservado | `CON`, `nul.txt`, `COM3`, `LPT1.log` |
| Segmento con punto o espacio final | `carpeta.`, `archivo.txt ` |

La unidad distinta de la del área no se decide aquí sino en el paso 5 (`commonpath` lanza `ValueError` entre unidades).

## Límites (`adapters/tools/_limits.py`)

| Constante | Valor | Se usa en |
|---|---|---|
| `MAX_READ_BYTES` | 262 144 | `leer_archivo`; cada archivo de `buscar_texto` |
| `MAX_WRITE_BYTES` | 1 048 576 | `escribir_archivo` |
| `MAX_LIST_ENTRIES` | 200 | `listar_archivos` |
| `MAX_MATCHES` | 50 | `buscar_texto` |
| `MAX_LINE_CHARS` | 200 | `buscar_texto` (línea de cada coincidencia) |
| `MAX_QUERY_CHARS` | 200 | `buscar_texto` (esquema: `maxLength`) |
| `MAX_RESULT_CHARS` | 20 000 | listados y búsquedas |

## Herramientas (`adapters/tools/`)

| Clase | `name` | Riesgo | Argumentos | Devuelve |
|---|---|---|---|---|
| `ReadFileTool` | `leer_archivo` | bajo | `path` | texto del archivo |
| `WriteFileTool` | `escribir_archivo` | medio | `path`, `content` | confirmación con bytes escritos |
| `ListFilesTool` | `listar_archivos` | bajo | `path` | entradas, una por línea (`archivo`/`carpeta`) |
| `SearchTextTool` | `buscar_texto` | bajo | `path`, `query` | coincidencias `ruta:línea: texto` |

Todas: constructor `Tool(area: AuthorizedArea | None)`; `additionalProperties: false`; `path` con `minLength: 1`.

### Resultado de error

`ToolResult(call_id="", content="[<categoría>] <causa>. <sugerencia>", is_error=True)`.

| Categoría | Cuándo |
|---|---|
| `[sin_area]` | no hay área configurada |
| `[fuera_del_area]` | la ruta real queda fuera, o no se pudo resolver |
| `[no_existe]` | la ruta no existe |
| `[no_es_archivo]` / `[no_es_carpeta]` | tipo equivocado |
| `[demasiado_grande]` | supera un límite de tamaño |
| `[no_es_texto]` | binario o no UTF-8 |
| `[error_de_archivo]` | error del sistema (permisos, disco) |

El mensaje repite el `path` recibido acotado a 100 caracteres y nunca la ruta real de fuera del área.

## Transiciones por llamada

```
ejecutar(args):
  sin área                         -> error [sin_area]
  not area.contains(path)          -> error [fuera_del_area]   # texto de la ruta: en Windows rechaza UNC,
                                                               # dispositivos y flujos sin tocar el disco
  real = realpath(root / path)     (sin excepciones; solo tras el paso anterior)
  not area.contains(real)          -> error [fuera_del_area]   # antes de leer o escribir
  comprobaciones propias de cada herramienta (tipo, tamaño, texto)
  acción sobre el disco            -> resultado, o error [error_de_archivo]
```
