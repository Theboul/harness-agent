# Quickstart: comprobar la raíz de composición

## Prerrequisitos

```bash
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt && pip install -e . --no-deps
```

## 1. Sin red: la composición con proveedor simulado (lo que corre la CI)

```bash
pytest tests/unit/test_bootstrap_compose.py tests/unit/test_bootstrap_main.py \
       tests/unit/test_entry_point.py tests/integration/test_bootstrap_session.py -q
```

Esperado: todo en verde; 20 ejecuciones idénticas de la misma sesión; cero conexiones de red; ningún archivo fuera del área.

## 2. Fronteras

```bash
pytest tests/architecture -q
```

Esperado: pasa, incluida `test_bootstrap_boundaries.py` (nada importa `bootstrap`; `bootstrap` no lee el entorno ni imprime; es el único importador de las cuatro capas).

## 3. Cuatro puertas de calidad

```bash
ruff format --check . && ruff check . && mypy src tests && pytest --cov=harness_agent --cov-report=term-missing
```

Esperado: exit 0; `bootstrap.py` y `__main__.py` al 100 % de líneas y ramas.

## 4. A mano, con un modelo real (humana, se omite sin clave)

```bash
cp config.example.toml config.toml        # editar: model, paths.workspace_root
export ANTHROPIC_API_KEY=...              # o la variable del proveedor elegido (nunca en el archivo)
python -m harness_agent                   # o: harness
```

Escribir una tarea («crea notas.txt con un saludo») y `/salir`. Esperado: el archivo aparece dentro del área, la terminal mostró cada evento, y la base (`paths.sessions_db`) contiene una sesión con sus eventos.

Fallos de arranque que se pueden provocar: quitar la clave (mensaje con el nombre de la variable), borrar `model` (error de configuración), no instalar el extra `litellm` (mensaje con el comando de instalación), dejar vacío `workspace_root` (aviso de área).

## 5. Qué conectará `bootstrap.py` cuando lleguen las historias siguientes

HU-01-06 (límites desde `config.limits`), HU-05-03 (un `Approver` real de la CLI), HU-01-04 (la herramienta de shell), HU-03-04 (reanudar una sesión existente en lugar de crear una nueva). Ninguna se adelanta aquí.
