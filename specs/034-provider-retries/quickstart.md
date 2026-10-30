# Quickstart: validar HU-07-04

Prerequisitos: entorno virtual del repo activo (`pip install -r requirements-dev.txt; pip install -e . --no-deps`).

```powershell
pytest tests/unit/adapters/providers tests/unit/test_config_retries.py tests/unit/test_bootstrap_retries.py tests/integration/test_retry_flow.py --basetemp=C:\tmp\ptr
pytest tests/architecture --basetemp=C:\tmp\ptr
```

Resultados esperados:

- 2 fallos temporales + 1 respuesta ⇒ 3 llamadas, esperas `2, 4` (SC-001); sin esperas reales.
- Error no temporal ⇒ 1 llamada, 0 esperas (SC-002). Agotado ⇒ N llamadas, N−1 esperas, mismo tipo (SC-003).
- Eventos `provider_error` con `reason: "retry"` en el bus y en la base de eventos, sin el centinela `VALOR-DE-PRUEBA-123` (SC-004).
- Configuración: sin `[retries]` ⇒ 5 / 2 s / 30 s; `max_attempts = 1` ⇒ sin reintentos; valores inválidos ⇒ arranque detenido con el campo nombrado.

Prueba manual opcional con un modelo real (no automatizada, requiere clave): `[retries]` en `config.toml` y provocar un 503 o un límite de tasa; se ven líneas de aviso por cada reintento.
