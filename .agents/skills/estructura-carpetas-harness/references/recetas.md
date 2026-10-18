# Recetas para añadir piezas

## Nueva herramienta nativa

1. `adapters/tools/<nombre>.py`: clase que implementa `Tool` (nombre, descripción, esquema JSON, nivel de riesgo, `run`).
2. Registrarla en `bootstrap.py`.
3. Declarar su riesgo para que la política de permisos la clasifique.
4. `tests/unit/test_tool_<nombre>.py` con argumentos válidos, inválidos y error.
5. No tocar `core/loop.py`.

## Nuevo proveedor de modelo

1. `adapters/providers/<nombre>_provider.py` implementa `Provider`; convierte del formato interno al del proveedor y de vuelta.
2. Registrarlo por configuración en `bootstrap.py`.
3. Prueba de contrato en `tests/contract/` y misma suite de resultados de herramienta.

## Nuevo almacén (por ejemplo otra base de datos)

1. `adapters/storage/` implementa `SessionStore` o `MemoryStore`.
2. Debe pasar los mismos tests de comportamiento que el almacén SQLite.

## Nuevo comando de la terminal

1. Función en `cli/app.py` que llama a la API del núcleo; nunca contiene lógica del núcleo.
2. Mostrar resultados con eventos o con `cli/render.py`.

## Nuevo tipo de evento

1. Añadirlo en `core/events.py` con campos tipados.
2. Suscribir a `cli/render.py` y, si corresponde, a `observability/`.

# Antes de dar por bueno un cambio

- ¿El archivo nuevo está en la carpeta que dice la tabla?
- ¿Algún archivo de `core/` importa de `adapters/`, `cli/` o un SDK? (skill `verificar-fronteras-hexagonales`)
- ¿Las implementaciones se conectan solo en `bootstrap.py`?
- ¿Hay test en la carpeta equivalente de `tests/`?
