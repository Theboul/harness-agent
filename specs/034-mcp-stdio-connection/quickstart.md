# Guía de validación: HU-08-01

Prerrequisitos: venv del repo con `mcp==2.3.0` (`pip install -r requirements-dev.txt; pip install -e . --no-deps`).

```powershell
pytest tests/unit/adapters/mcp tests/unit/test_config_mcp.py -q
pytest tests/integration/test_mcp_stdio_connection.py -q     # servidor local por stdio, sin red
pytest tests/architecture -q
```

Resultados esperados: todo en verde; tras cada prueba de integración el proceso del servidor ya no existe (la prueba lo sondea con tope).

Prueba manual (opcional): añadir a `config.toml`

```toml
[mcp_servers.demo]
command = "python"
args = ["tests/spikes/mcp_demo_server.py"]
```

`harness` arranca; con un `command` inexistente arranca igualmente y muestra un aviso en español. Ver `contracts/mcp_client_contract.md` y `data-model.md`.
