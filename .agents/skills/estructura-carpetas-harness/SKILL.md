---
name: estructura-carpetas-harness
description: "Trigger: crear archivo, mover código, nuevo módulo, estructura de carpetas, dónde va, nueva herramienta, nuevo proveedor, nuevo comando CLI. Decide la carpeta correcta en src/harness_agent/ según la arquitectura hexagonal."
license: Apache-2.0
metadata:
  author: "harness-team"
  version: "1.1"
---

## Activation Contract

Cargar antes de crear un archivo nuevo, mover código o proponer un módulo en el repositorio, y en `/speckit-plan` (sección *Project Structure*) y `/speckit-tasks`.

## Hard Rules

- Ubicar todo archivo nuevo según la tabla de Decision Gates; no inventar carpetas fuera de `references/arbol.md`. Una carpeta marcada como «planeada» se crea solo con la historia que la necesita.
- `core/` solo contiene reglas y puertos; importa solo biblioteca estándar y `harness_agent.core` (ver skill `verificar-fronteras-hexagonales`).
- Los puertos viven en `core/interfaces/`, en el archivo de su dominio (tabla de `references/arbol.md`); su cambio exige acuerdo de A, B y C. Lo mismo vale para `core/entities.py` y el catálogo de eventos `core/events.py`.
- Un puerto por interfaz, como clase abstracta (`ABC`), nombrado por rol en inglés (`SessionStore`), no por tecnología.
- Todo lo público de `core/` se exporta en `core/__init__.py` (`__all__`); los consumidores (`cli/`, `adapters/`, pruebas) importan desde `harness_agent.core`, nunca de un submódulo.
- Las implementaciones se conectan en la raíz de composición `src/harness_agent/bootstrap.py`. Cada pieza nueva se cablea en `compose()` de ese archivo.
- `tests/` refleja la estructura de `src/harness_agent/` (ver «Pruebas» en `references/arbol.md`).
- Sin secretos en el repositorio: solo `.env.example` y `config.example.toml` sin valores de clave.
- `__init__.py` expone la API pública del subpaquete; el resto es interno.
- Archivos y módulos en `snake_case`; clases en `PascalCase`; identificadores y docstrings en inglés; mensajes al usuario en español.

## Decision Gates

| Lo que se escribe | Carpeta |
|---|---|
| Tipo de mensaje o resultado del dominio (`Message`, `ToolCall`, `ToolResult`…) | `core/entities.py` (contrato compartido) |
| Tipo de evento | `core/events.py` (contrato compartido: acuerdo de A, B y C) |
| Interfaz que el núcleo necesita de fuera (puerto) | `core/interfaces/<dominio>.py` (ver tabla de puertos) |
| Regla de negocio (permisos, límites, compactación, subagentes) | Subpaquete de `core/` (`core/permissions/`, `core/limits.py`, `core/context/`, `core/subagents/`) |
| Implementación en memoria de un puerto, pura y sin E/S | `core/` (como `core/in_memory_event_bus.py`, `core/tools/registry.py`) |
| Error de dominio | `errors.py` del subpaquete que lo lanza (como `core/tools/errors.py`) |
| Código con `litellm`, `sqlite3`, `mcp`, `subprocess`, red o disco | `adapters/<subpaquete>/` |
| Conversión entre el formato canónico y el de un proveedor | `adapters/converters/` |
| Herramienta nativa | `adapters/tools/` (la interfaz `Tool` vive en `core/interfaces/tool.py`) |
| Imprime o lee de la terminal | `cli/` (`app.py` entrada y comandos, `render.py` texto de cada evento, `approval_view.py` bloque de aprobación, `activity.py` líneas de actividad, `session_commands.py` texto de los comandos de sesión, `style.py` color: el único que conoce ANSI y el entorno) |
| Trazas, auditoría, redacción de secretos | `observability/` |
| Unir piezas y elegir implementaciones | `bootstrap.py` |
| Lectura de configuración (archivo y entorno) | `config.py` |
| Doble de prueba reutilizable | `tests/doubles/` (protegido: solo si la spec lo justifica) |

Duda entre `core/` y `adapters/`: si cambiaría al cambiar de proveedor, base de datos o interfaz, o si toca E/S, es adaptador.

## Execution Steps

1. Clasificar lo que se va a escribir con la tabla anterior.
2. Si es una pieza nueva (herramienta, proveedor, almacén, comando, evento, puerto), seguir la receta en `references/recetas.md`.
3. Crear el archivo y su prueba en la carpeta equivalente de `tests/`.
4. Exportar lo público en el `__init__.py` del subpaquete (y en `core/__init__.py` si es del núcleo).
5. Conectar la implementación en `bootstrap.py` si existe; si no, anotarlo en el plan.
6. Ejecutar la verificación de fronteras (`pytest tests/architecture`).

## Output Contract

Devolver:
- Ruta elegida y fila de la tabla que la justifica.
- Archivos de código y de prueba creados o movidos.
- Resultado de la verificación de fronteras.

## References

- `references/arbol.md` — árbol real (existente y planeado), tabla de puertos y reparto de áreas A/B/C.
- `references/recetas.md` — recetas para añadir piezas.
- `../verificar-fronteras-hexagonales/SKILL.md` — reglas de dependencia.
