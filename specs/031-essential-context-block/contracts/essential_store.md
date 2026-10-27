# Contrato: el almacén del contexto esencial y el lector de criterios

## Protocolos (`harness_agent.core`, definidos en `core/context/renewer.py`)

```python
class EssentialSource(Protocol):
    def items(self, session_id: str) -> Sequence[EssentialItem]: ...

class CriteriaReader(Protocol):
    def load_criteria(self, session_id: str) -> Sequence[TaskCriteriaItem]: ...
```

`core/interfaces/` **no cambia**: `SessionStore`, `TaskCriteria` y `ContextManager` siguen igual. `CriteriaReader` es un protocolo estructural de **solo lectura** (una sola operación de `TaskCriteria`); `SqliteTaskStore` lo cumple sin modificarse. La escritura (`save_items`) es del adaptador y solo la usa la composición al crear la sesión: el núcleo no escribe.

## Garantías del adaptador (`SqliteEssentialStore`)

1. **`save_items`** ocurre en **una transacción** (`BEGIN IMMEDIATE` … `COMMIT`) sobre `store.connection()`; nunca abre otra conexión. Inserta todas las filas o ninguna (cualquier error → `ROLLBACK` y `SessionStoreError` con mensaje fijo).
2. **Escritura única**: guardar de nuevo los elementos de una sesión que ya los tiene falla (clave primaria) sin cambiar nada. El adaptador **no** ofrece actualizar ni borrar.
3. **`items`** devuelve las filas de la sesión ordenadas por (clave, orden). Una sesión sin filas devuelve una lista vacía (una sesión sin tarea no tiene bloque).
4. **No toca** `events`, `resumenes`, `criterios` ni `criterios_sello`.
5. Un error del motor se convierte en `SessionStoreError` con un texto fijo; nunca lleva un valor.
6. Los valores ya vienen **limpios y con las credenciales de URL ocultas** (lo hace `make_items`, en el núcleo); el adaptador guarda lo que recibe y no contiene reglas de negocio.

## Lector de criterios y falla cerrada

- El renovador llama a `load_criteria` con la **referencia guardada** (`criterios_ref`), no con el identificador que tenga a mano.
- `SqliteTaskStore.load_criteria` verifica cada fila y el sello; ante cualquier indicio de alteración publica `criteria_tampered` (solo el motivo) **y lanza**. El renovador no publica nada: captura la excepción y lanza `EssentialContextUnavailable` con mensaje fijo, sin texto de la excepción.
- Una lista vacía de criterios con `criterios_ref` presente es válida (el bloque no lleva sección de criterios).

## Ejemplo normativo (E1): la composición guarda y el renovador lee

Sesión `s1` de la tarea del ejemplo de `data-model.md`:

1. `compose(…, task=…)` valida (antes de abrir nada), abre el almacén, crea la sesión con `start_task` y llama a `save_items("s1", items)` con 7 filas (4 del bloque y 3 instrucciones).
2. `items("s1")` devuelve las 7 filas ordenadas: `criterios_ref`, `instrucciones` 1, 2 y 3, `objetivo`, `reglas`, `ticket`.
3. Segundo `save_items("s1", …)` → `SessionStoreError`; las 7 filas siguen idénticas.
4. `render_block(items, criterios)` usa las 4 filas del bloque y **no** las 3 de instrucciones.
5. `instruction_messages(items)` devuelve 3 mensajes `SYSTEM` cuyo contenido es igual, uno a uno, al de `Composition.history_prefix`.

## Ejemplo normativo (E2): rollback

Un fallo inyectado (disparador SQL) en cualquiera de las inserciones deja `contexto_esencial` sin filas nuevas y la conexión fuera de transacción.

## Ejemplo normativo (E3): sin tarea

`items("s9")` de una sesión creada sin tarea → lista vacía. Una sesión sin tarea **no tiene renovador** (la composición no lo construye), así que nadie lee esa lista y no hay bloque. Si, en cambio, una sesión **con tarea** (con renovador) encuentra la lista vacía o sin `objetivo`, `criterios_ref` o alguna `instrucciones`, el renovador **falla cerrado** con `EssentialContextUnavailable(missing=True)` y el mensaje `Faltan elementos del contexto esencial de la tarea; la petición no se envía.`: nunca se trata como sesión sin tarea.
