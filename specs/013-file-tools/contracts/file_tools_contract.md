# Contrato: área de trabajo y herramientas de archivos

**Spec**: [../spec.md](../spec.md) (FR-001 a FR-016) · **Convención**: `specs/007-permission-policy/contracts/path_argument_convention.md` · **La cumplen**: HU-01-03 (herramientas) y HU-05-01 (política)

## 1. Área autorizada (`adapters/system`)

```python
from harness_agent.adapters.system import WorkspaceArea

area = WorkspaceArea("/ruta/al/proyecto")        # carpeta existente; si no, ValueError
area.root                                        # Path real y absoluto
area.contains("src/main.py")                     # relativa a root -> True si queda dentro
area.contains("../fuera.txt")                    # False
area.contains("/etc/hosts")                      # False
area.contains("enlace-a-tmp/x")                  # False si la ruta real sale
```

| Regla | Texto |
|---|---|
| A-1 | `contains` nunca lanza; ante lo no previsto devuelve `False`. |
| A-2 | Decide sobre la ruta real; el texto de la ruta no cuenta. |
| A-3 | La raíz cuenta como dentro. |
| A-4 | En Windows, UNC, dispositivos, otra unidad, flujos alternos, nombres reservados y segmentos con punto o espacio final devuelven `False`. |
| A-5 | `DummyAuthorizedArea` y `WorkspaceArea` coinciden en los casos léxicos y de contención básica (prueba de contrato). |

## 2. Herramientas (`adapters/tools`)

```python
from harness_agent.adapters.tools import (
    ListFilesTool, ReadFileTool, SearchTextTool, WriteFileTool,
)

tools = [ReadFileTool(area), WriteFileTool(area), ListFilesTool(area), SearchTextTool(area)]
```

| Herramienta | Argumentos | Riesgo | Notas |
|---|---|---|---|
| `leer_archivo` | `path` | bajo | UTF-8, máximo 256 KiB; error si carpeta, binario, no UTF-8, grande |
| `escribir_archivo` | `path`, `content` | medio | crea o reemplaza; crea carpetas intermedias; máximo 1 MiB |
| `listar_archivos` | `path` | bajo | no recursivo, ordenado, máximo 200 entradas |
| `buscar_texto` | `path`, `query` | bajo | literal, sensible a mayúsculas, recursivo, máximo 50 coincidencias |

| Regla | Texto |
|---|---|
| T-1 | `path` es el único argumento de ruta, texto no vacío; el esquema no admite otros campos. |
| T-2 | Antes de actuar: `area.contains(<texto de la ruta>)`, después la ruta real y `area.contains(real)`; si alguna dice que no, error `[fuera_del_area]` y no se toca el disco. |
| T-3 | Ninguna herramienta lanza: todo error es un `ToolResult` con `is_error=True`, causa y sugerencia en español. |
| T-4 | Sin área (`None`): error `[sin_area]`, sin actuar. |
| T-5 | Resultados acotados por las constantes de `adapters/tools`. |
| T-6 | Los mensajes no revelan rutas reales fuera del área. |

## 3. Cómo lo ven la política y el bucle (sin cambios en ellos)

| Llamada | Política (`DefaultPermissionPolicy`) | Resultado en el Sprint 1 |
|---|---|---|
| `escribir_archivo` con `path` dentro | permitir | se ejecuta; evento de decisión «allow» |
| `escribir_archivo` con `path` fuera o sin área | preguntar | sin aprobador: denegada, no se ejecuta |
| `leer_archivo`, `listar_archivos`, `buscar_texto` con `path` dentro | permitir (regla de lectura) | se ejecutan |
| lo mismo, fuera o sin área | preguntar | denegadas |
| sin `path` o `path` no textual | denegar | llamada mal formada |

## 4. Qué NO cambia

El puerto `Tool`, el puerto `AuthorizedArea`, el bucle, la política, el registro, la configuración y los dobles.
