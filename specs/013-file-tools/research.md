# Research: HU-01-03 — Herramientas de archivos

Las decisiones de alcance las tomó el responsable el 2026-10-23 (véase *Clarifications* en la spec). Aquí se resuelven los detalles técnicos.

## R-01 — Dónde se decide la contención

- **Decision**: la decide `AuthorizedArea.contains` sobre la ruta real; la herramienta calcula la ruta real con `os.path.realpath` y vuelve a preguntar al área antes de actuar.
- **Rationale**: la política (HU-05-01) ya llama a `contains(path)` con el `path` sin modificar; el puerto no cambia. Si la herramienta usara su propia lógica de contención, habría dos autoridades que podrían discrepar.
- **Alternatives considered**: añadir `resolve()` al puerto (descartado: cambia un contrato de HU-00-01, exige el acuerdo de A, B y C); que la herramienta compare por texto (descartado: viola la regla de negocio 2).

## R-02 — Resolver rutas que no existen

- **Decision**: `os.path.realpath(candidate)` sin `strict`, para poder crear archivos nuevos; la parte que existe se resuelve (enlaces incluidos) y el resto se normaliza.
- **Rationale**: una escritura crea un archivo que aún no existe; `strict=True` lo impediría. Un enlace en un tramo existente sí se sigue, que es lo que importa para el escape.
- **Alternatives considered**: `Path.resolve(strict=True)` (descartado por lo anterior).

## R-03 — Comparar contención

- **Decision**: `os.path.commonpath([root, real]) == root`, tras `os.path.normcase` en ambos; `ValueError` (otra unidad en Windows, mezcla de absoluta y relativa) cuenta como fuera.
- **Rationale**: evita el error clásico de `startswith` (`/area` frente a `/area-otra`); `commonpath` lanza `ValueError` entre unidades distintas, que se trata como «fuera».
- **Alternatives considered**: `Path.is_relative_to` (válido, pero no normaliza mayúsculas de Windows por sí solo); `startswith` (descartado: inseguro).

## R-04 — Casos de Windows

- **Decision**: `windows_path_problem(raw)` con `PureWindowsPath`: rechaza prefijos UNC y de dispositivo (`\\`, `//`, `\\?\`, `\\.\`), unidad distinta de la del área (la decide la comparación), `:` fuera de la unidad (flujo alterno), nombres reservados (CON, PRN, AUX, NUL, COM1–9, LPT1–9, con o sin extensión) y segmentos que acaban en punto o espacio.
- **Rationale**: son los casos que nombra AC-03 más los que Windows trata como atajos al mismo destino. Al ser una función pura se prueba en Linux.
- **Alternatives considered**: apoyarse solo en `realpath` de Windows (descartado: no reconoce los flujos alternos ni los nombres de dispositivo como fuera del área).

## R-05 — Enlaces simbólicos en las pruebas

- **Decision**: crearlos con `os.symlink` en `tmp_path`; si el sistema no lo permite (Windows sin privilegios), la prueba se omite con `pytest.skip`. Los enlaces de carpeta usan `target_is_directory=True`.
- **Rationale**: `CLAUDE.md` ya espera 1 omisión de enlace simbólico en Windows.

## R-06 — Lectura de texto

- **Decision**: leer como máximo `MAX_READ_BYTES + 1` bytes; si hay más, error de tamaño; NUL en el contenido o decodificación UTF-8 estricta que falla → error («no parece texto» / «no es UTF-8»).
- **Rationale**: evita cargar archivos enormes y devolver basura al modelo; el contenido leído se marca como externo en el bucle.

## R-07 — Escritura

- **Decision**: codificar a UTF-8, rechazar si supera `MAX_WRITE_BYTES`, comprobar contención, crear carpetas padre y `Path.write_bytes`. Los errores del sistema (`OSError`) se traducen a un mensaje en español.
- **Rationale**: simple y suficiente; la escritura atómica con archivo temporal es una mejora posterior.

## R-08 — Búsqueda

- **Decision**: texto literal, sensible a mayúsculas; recorrido ordenado con `os.scandir`; no seguir enlaces de carpeta; cada archivo se comprueba con `area.contains(real)`; se omiten binarios y archivos mayores que el límite; formato `ruta/relativa:línea: texto`.
- **Rationale**: determinista y acotado; un regex añade riesgo de ReDoS que la historia no pide.

## R-09 — Errores como resultados

- **Decision**: toda ruta de error devuelve `ToolResult(is_error=True)`; ninguna lanza. Un `try` externo captura `Exception` y devuelve un error genérico para lo imprevisto (el bucle lo habría convertido, pero así el mensaje es nuestro y sin traza).
- **Rationale**: regla de negocio 4 y FR-010.

## R-10 — Pruebas de integración

- **Decision**: componer en la prueba el área, las herramientas, `InMemoryToolRegistry`, `DefaultPermissionPolicy(area=..., allow_reads_in_area=<ambos>)`, `RecordingEventBus` y `AgentLoop` con `ScriptedProvider`.
- **Rationale**: es el único sitio de composición hasta que exista `bootstrap.py`. Se comprueba el evento `permission_decided` (AC-02) y que el archivo no se crea fuera.

## R-11 — Qué no se prueba aquí

- La causa específica del rechazo de la política (HU-05-03), la carpeta de la sesión (HU-03-01), el shell y `editar_archivo`.
