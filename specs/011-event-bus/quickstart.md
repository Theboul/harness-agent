# Quickstart: verificar HU-01-05 — Bus de eventos desacoplado de la interfaz

**Spec**: [spec.md](spec.md) · **Contrato**: [contracts/event_bus_contract.md](contracts/event_bus_contract.md) · **Plan**: [plan.md](plan.md)

Guía de validación para quien implemente o revise la historia. No contiene código de la implementación.

## Requisitos previos

- Python 3.12 y el entorno virtual del proyecto con las versiones de `requirements-dev.txt` (en Windows, el intérprete de `.venv\Scripts\python.exe`).
- Árbol de trabajo en la rama `gustavo`, sin cambios en `core/interfaces/`, `core/events.py`, `core/loop.py`, `tests/doubles/` ni `docs/archivo/`.

## 1. Ejecutar las pruebas de la historia

```bash
pytest tests/contracts/test_event_bus_contract.py tests/unit/core/test_in_memory_event_bus.py
pytest tests/integration/test_event_bus_agent_loop.py tests/integration/test_event_bus_logging_subscriber.py
pytest tests/architecture/test_core_no_terminal.py
```

Resultado esperado: todas pasan; sin red, sin entorno real y sin salida por consola del núcleo.

## 2. Puertas de calidad (las mismas de la CI)

```bash
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
```

Resultado esperado: los cuatro terminan con código 0 y `src/harness_agent/core/in_memory_event_bus.py` queda al 100 % de cobertura (toda línea sin cubrir se justifica por escrito).

## 3. Comprobar que no se tocaron los archivos protegidos

```bash
git fetch origin
base=$(git merge-base HEAD origin/main)
git diff --exit-code $base -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/loop.py tests/doubles docs/archivo
pytest tests/architecture
```

Resultado esperado: el `git diff` termina con código 0 y sin salida; las pruebas de arquitectura pasan (incluida `test_core_no_terminal.py`).

## 4. Recorrido manual opcional (demostración AC-01 y fallos)

Con un intérprete de Python abierto en la raíz del repositorio (con `PYTHONPATH=src` si el paquete no está instalado):

1. Crear un `InMemoryEventBus` y suscribir dos manejadores al tipo `USER_MESSAGE` que añadan su nombre a una lista; emitir un `Event` de ese tipo: la lista tiene los dos nombres en el orden de suscripción. Emitir un evento de otro tipo: no cambia.
2. Suscribir un tercer manejador que lance `ValueError` entre otros dos sanos y emitir: los dos sanos se ejecutan, `emit` lanza `EventDeliveryError` con el mensaje «Falló 1 manejador al entregar el evento 'user_message'.» y `error.exceptions` contiene el `ValueError` original.
3. Suscribir un manejador que lance `KeyboardInterrupt`: la emisión lo propaga de inmediato y sin agrupar; los manejadores siguientes no se ejecutan.
4. Llamar a `bus.subscribe("user_message", print)`: lanza `TypeError` en español (una cadena no es un `EventType`); `bus.emit({"type": "x"})`: lanza `TypeError`.
5. Conectar el bus al bucle real con `make_rig` (de `tests/core/support.py`) y un guion de una herramienta: un suscriptor por tipo recoge, en orden, mensaje del usuario, herramienta solicitada, decisión de permiso, herramienta terminada y mensaje del asistente; con un guion que lanza un error del proveedor aparece `PROVIDER_ERROR`. «Aprobación pedida» no aparece: el bucle la emitirá con HU-05-03 (Sprint 2).
6. Añadir un suscriptor de registro (`logging`) a todos los tipos y repetir el turno: una línea por evento y el núcleo no imprime nada.

## 5. AC-02 sobre el código

```bash
pytest tests/architecture/test_core_no_terminal.py -v
```

Resultado esperado: pasan la comprobación sobre los 17 módulos de `core/`, la autoprueba del detector con fragmentos sintéticos y la prueba de mutación sobre una copia de `core/` en un directorio temporal (el código real no se edita nunca).

## Criterios de «listo» para esta historia

- [ ] Las pruebas de las secciones 1 y 5 pasan y la sección 2 termina con código 0 en los cuatro comandos.
- [ ] La sección 3 no muestra diferencias en los archivos protegidos.
- [ ] El contrato único se ejecuta contra el doble y contra el bus real; las cláusulas propias del bus real solo contra este.
- [ ] `docs/PROGRESO.md` tiene la fila de HU-01-05 en `En revisión` (nunca `Hecha` antes de la revisión cruzada y la CI), el registro de cada tarea y la observación de que «aprobación pedida» llega con HU-05-03.
- [ ] Revisión cruzada por un integrante de A y CI en Linux y Windows pendientes de confirmación humana; HU-00-01 sigue pendiente de aprobación técnica.
