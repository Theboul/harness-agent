# Quickstart: verificar HU-06-01 — CLI básica con eventos en tiempo real

**Spec**: [spec.md](spec.md) · **Contrato**: [contracts/cli_contract.md](contracts/cli_contract.md) · **Plan**: [plan.md](plan.md)

Guía de validación para quien implemente o revise la historia. No contiene código de la implementación.

## Requisitos previos

- Python 3.12 y el entorno virtual del proyecto con las versiones de `requirements-dev.txt` (en Windows, `.venv\Scripts\python.exe`).
- Árbol de trabajo en la rama `gustavo`, sin cambios en `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `tests/doubles/` ni `docs/archivo/`.

## 1. Ejecutar las pruebas de la historia

```bash
pytest tests/unit/cli
pytest tests/integration/test_cli_agent_loop.py
pytest tests/architecture/test_cli_boundaries.py
```

Resultado esperado: todas pasan; sin red, sin consola real y sin proveedor real.

## 2. Puertas de calidad (las mismas de la CI)

```bash
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
```

Resultado esperado: los cuatro terminan con código 0 y `src/harness_agent/cli/render.py` y `src/harness_agent/cli/app.py` quedan al 100 % de cobertura (toda línea sin cubrir se justifica por escrito).

## 3. Comprobar que no se tocaron los archivos protegidos

```bash
git fetch origin
base=$(git merge-base HEAD origin/main)
git diff --exit-code $base -- src/harness_agent/core/interfaces src/harness_agent/core/events.py src/harness_agent/core/loop.py src/harness_agent/core/in_memory_event_bus.py tests/doubles docs/archivo
pytest tests/architecture
```

Resultado esperado: el `git diff` termina con código 0 y sin salida; las pruebas de arquitectura pasan (incluidas `test_cli_boundaries.py` y `test_core_no_terminal.py`).

## 4. Recorrido manual opcional (demostración AC-01 y AC-02)

Con un intérprete de Python abierto en la raíz del repositorio (con `PYTHONPATH=src` si el paquete no está instalado), usando flujos en memoria (`io.StringIO`) y un bus en memoria:

1. Crear un `InMemoryEventBus`, llamar a `attach_renderer(bus, salida)` y emitir a mano un `TOOL_REQUESTED` con `{"name": "buscar"}`: la salida contiene `... ejecutando: buscar`. Emitir `TOOL_FINISHED` con `is_error` falso: `v buscar: correcto`.
2. Emitir `TOOL_FINISHED` con `is_error` verdadero y categoría `invalid_arguments`: una línea `x Error: Los argumentos de la herramienta 'buscar' no son válidos. Sugerencia: …`, sin traza.
3. Emitir un `ASSISTANT_MESSAGE` cuyo texto contiene una secuencia de escape: la salida no contiene el carácter de escape.
4. Emitir un `TOOL_FINISHED` con una categoría inventada y un valor centinela en la carga: la salida muestra la causa genérica y `Revisa el registro de eventos.`, sin el centinela.
5. Cerrar el flujo de salida y emitir un evento mostrado: `emit` lanza `EventDeliveryError` (el fallo de escritura no se oculta).
6. Con el bucle real (`make_rig` de `tests/core/support.py`) y un guion de una herramienta, llamar a `run_cli` con una entrada en memoria `tarea de prueba`, una línea vacía, `/desconocido`, `/ayuda` y `/salir`: la tarea llega una sola vez al turno, se ven las líneas de la herramienta y el mensaje del asistente, la línea vacía se ignora, el comando desconocido avisa y el ciclo termina con `Sesión terminada.`.
7. Repetir con una función de turno que lanza `RuntimeError` con un texto reconocible: `run_cli` escribe una sola línea `x Error: el turno terminó con un fallo interno (<TipoDeError>). Sugerencia: revisa el registro de eventos.` con el tipo (`RuntimeError`) y sin el texto, no pide más tareas y devuelve `1`; con `KeyboardInterrupt` en lugar de `RuntimeError`, la excepción llega sin cambios a quien llamó a `run_cli`.

## 5. Fronteras

```bash
pytest tests/architecture/test_cli_boundaries.py -v
```

Resultado esperado: pasan la comprobación de que `core/` no importa `cli/`, la de que `cli/` solo usa la API pública de `harness_agent.core`, la autoprueba del detector con fragmentos sintéticos y la prueba de mutación sobre una copia (el código real no se edita nunca).

## Criterios de «listo» para esta historia

- [ ] Las pruebas de las secciones 1 y 5 pasan y la sección 2 termina con código 0 en los cuatro comandos.
- [ ] La sección 3 no muestra diferencias en los archivos protegidos.
- [ ] `docs/PROGRESO.md` tiene la fila de HU-06-01 en `En revisión` (nunca `Hecha` antes de la revisión cruzada y la CI), el registro de cada tarea y la nota de la diferencia con el prototipo (argumentos y causa concreta no disponibles en la carga).
- [ ] Revisión cruzada por un integrante de A o B y CI en Linux y Windows pendientes de confirmación humana; HU-00-01 sigue pendiente de aprobación técnica.
