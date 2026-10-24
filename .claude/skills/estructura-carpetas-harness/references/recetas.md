# Recetas para añadir piezas

Cada receta asume pruebas primero: escribir la prueba, verla fallar por la razón esperada, implementar lo mínimo y pasar `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent`.

## Nueva herramienta nativa

1. `adapters/tools/<nombre>.py`: clase que implementa `Tool` de `harness_agent.core` (`name`, `description`, `schema` JSON Schema, `risk: RiskLevel`, `async run(args) -> ToolResult`).
2. Declarar el riesgo para que `DefaultPermissionPolicy` la clasifique: escribir = `MEDIUM`; leer, listar, buscar = `LOW`; varias rutas o efectos amplios = `HIGH`.
3. El argumento de ruta se llama **`path`** (convención de `specs/007-permission-policy/contracts/path_argument_convention.md`): la política solo permite cuando `AuthorizedArea.contains(path)` es `True`.
4. El esquema debe pasar `check_schema` de `core/tools/` (`InMemoryToolRegistry.register` lo valida); objetos libres declaran `additionalProperties: true`.
5. Contenido leído de fuera se marca como externo (dato, no instrucción): `Message.is_external` en `core/entities.py`.
6. Registrarla en `bootstrap.py` (`compose()`), con su prueba.
7. Pruebas: `tests/unit/adapters/tools/test_<nombre>.py` (argumentos válidos, inválidos, error) y una integración con `AgentLoop` + `DefaultPermissionPolicy` en `tests/integration/`.
8. No tocar `core/loop.py`.

## Nuevo proveedor de modelo

1. `adapters/providers/<nombre>_provider.py` implementa `Provider` (`async complete(messages, tools) -> ProviderResponse`).
2. Convertir con `adapters/converters/` (`to_openai_envelope` / `to_anthropic_envelope` y `from_openai_response` / `from_anthropic_response`); no reescribir conversiones. `from_openai_messages` y `from_anthropic_payload` están obsoletas.
3. Traducir las excepciones del SDK a errores de dominio; el núcleo nunca ve una excepción del SDK.
4. Clave solo desde `HarnessConfig.api_key` (`Secret`), nunca leída del entorno dentro del adaptador.
5. Seleccionarlo por configuración (`model = "<proveedor>/<modelo>"`) en `bootstrap.py`.
6. Prueba de contrato en `tests/contracts/` (como `test_provider_interchangeability.py`) sin red: respuestas grabadas o SDK falseado.

## Nuevo almacén (SQLite u otro)

1. `adapters/storage/` implementa `SessionStore` o `MemoryStore` (síncronos).
2. Debe pasar el mismo contrato que el doble `InMemorySessionStore` / `InMemoryMemoryStore` (`tests/contracts/`).
3. Excepciones de `sqlite3` traducidas a errores de dominio; ruta de la base desde `HarnessConfig.paths.sessions_db`.

## Nuevo puerto

1. Solo con acuerdo de A, B y C (contrato de HU-00-01); registrar la decisión en `docs/PROGRESO.md`.
2. Clase `ABC` en el archivo de dominio de `core/interfaces/` con tipos del dominio; métodos `async` si hacen E/S que pueda tardar o cancelarse (D-01).
3. Reexportar en `core/interfaces/__init__.py` y `core/__init__.py`; añadir un doble en `tests/doubles/` y su prueba de contrato.

## Nuevo comando de la terminal

1. En `cli/app.py`: las líneas que empiezan por `/` son comandos; añadir el caso y su línea en `HELP_TEXT`. Nunca lógica del núcleo.
2. El comando usa solo la API pública de `harness_agent.core` y lo que se inyecte a `run_cli`.
3. Pruebas en `tests/unit/cli/` con flujos en memoria (`io.StringIO`).

## Nuevo tipo de evento

1. Solo con acuerdo de A, B y C: `core/events.py` es el catálogo único de 17 tipos (contrato) y `tests/contracts/test_event_catalog.py` lo fija.
2. Añadir su texto en `cli/render.py` (`SHOWN_TYPES` y la tabla de categorías) sin leer campos que la carga no traiga.
3. Si corresponde, suscribirlo en `observability/`.

## Nueva regla del núcleo (permisos, límites, contexto)

1. Subpaquete o módulo en `core/`, puro (sin E/S, sin leer configuración: la recibe por constructor).
2. Exportar en `core/__init__.py`.
3. Guarda AST propia en `tests/architecture/test_<modulo>_boundaries.py` reutilizando `forbidden_imports`, `find_config_reads` y `terminal_uses` (ver skill `verificar-fronteras-hexagonales`).

# Antes de dar por bueno un cambio

- ¿El archivo nuevo está en la carpeta que dice la tabla?
- ¿Algún archivo de `core/` importa de `adapters/`, `cli/`, `config`, `observability/` o un SDK? (skill `verificar-fronteras-hexagonales`)
- ¿Lo público está exportado en el `__init__.py` y los consumidores importan de `harness_agent.core`?
- ¿Las implementaciones se conectan solo en `bootstrap.py`?
- ¿Hay prueba en la carpeta equivalente de `tests/`?
