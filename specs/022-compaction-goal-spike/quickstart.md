# Quickstart: SPK-03

```bash
.venv/Scripts/python.exe -m pytest tests/spikes/test_compaction_goal_spike.py --no-cov -v
```

Salida esperada: todas las pruebas pasan sin red ni claves (el spike no usa `litellm`).

Las cuatro puertas de calidad y las fronteras, antes de cerrar:

```bash
ruff format --check . && ruff check . && mypy src tests && pytest && pytest tests/architecture
```

La corrida con un modelo real (tarea humana) queda descrita en `docs/decisiones/SPK-03-compactacion-bloque-fijo.md` §6.
