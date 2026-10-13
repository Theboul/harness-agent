---
name: estructura-carpetas-harness
description: "Trigger: crear archivo, mover código, nuevo módulo, estructura de carpetas, dónde va, nueva herramienta, nuevo proveedor, nuevo comando CLI. Decide la carpeta correcta en src/harness_agent/ según la arquitectura hexagonal."
license: Apache-2.0
metadata:
  author: "harness-team"
  version: "1.0"
---

## Activation Contract

Cargar antes de crear un archivo nuevo, mover código o proponer un módulo en el repositorio.

## Hard Rules

- Ubicar todo archivo nuevo según la tabla de Decision Gates; no inventar carpetas fuera de `references/arbol.md`.
- `core/` solo contiene reglas y puertos; sin imports externos (ver skill `verificar-fronteras-hexagonales`).
- Las implementaciones se conectan únicamente en `bootstrap.py`.
- Los puertos viven en `core/ports.py`; su cambio exige acuerdo de A, B y C.
- Un puerto por interfaz, nombrado por rol (`SessionStore`), no por tecnología.
- `tests/` refleja la estructura de `src/harness_agent/`.
- Sin secretos en el repositorio: solo `.env.example`.
- `__init__.py` expone la API pública del subpaquete; el resto es interno.
- Archivos y módulos en `snake_case`; clases en `PascalCase`.

## Decision Gates

| Lo que se escribe | Carpeta |
|---|---|
| Tipo de mensaje, evento o resultado | `core/messages.py`, `core/events.py` |
| Interfaz que el núcleo necesita de fuera | `core/ports.py` |
| Regla de negocio (permisos, límites, compactación) | `core/` |
| Código con `litellm`, `sqlite3`, `mcp`, `subprocess` o disco | `adapters/` |
| Herramienta nativa | `adapters/tools/` (la interfaz `Tool` vive en `core/tools/`) |
| Imprime o lee de la terminal | `cli/` |
| Trazas, auditoría, redacción de secretos | `observability/` |
| Unir piezas y elegir implementaciones | `bootstrap.py` |
| Lectura de configuración | `config.py` |

Duda entre `core/` y `adapters/`: si cambiaría al cambiar de proveedor, base de datos o interfaz, es adaptador.

## Execution Steps

1. Clasificar lo que se va a escribir con la tabla anterior.
2. Si es una pieza nueva (herramienta, proveedor, almacén, comando, evento), seguir la receta en `references/recetas.md`.
3. Crear el archivo y su test en la carpeta equivalente de `tests/`.
4. Conectar la implementación en `bootstrap.py` si corresponde.
5. Ejecutar la verificación de fronteras.

## Output Contract

Devolver:
- Ruta elegida y fila de la tabla que la justifica.
- Archivos de código y de prueba creados o movidos.
- Resultado de la verificación de fronteras.

## References

- `references/arbol.md` — árbol acordado y reparto de áreas A/B/C.
- `references/recetas.md` — recetas para añadir piezas.
- `../verificar-fronteras-hexagonales/SKILL.md` — reglas de dependencia.
