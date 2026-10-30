# Guía de validación: SPK-04

## Requisitos

Entorno con `requirements-dev.txt` instalado (incluye `mcp==2.3.0`). Sin red ni claves.

## Comandos

```powershell
pytest tests/spikes/test_mcp_stdio_spike.py -v     # el spike completo
pytest tests/spikes/test_mcp_stdio_spike.py -k handshake   # solo AC-01
ruff format --check .; ruff check .; mypy src tests; pytest --cov=harness_agent
pytest tests/architecture
```

## Resultado esperado

- AC-01: el servidor de demostración se inicia, se negocian capacidades y se listan las herramientas.
- Cada modo de fallo termina sin proceso hijo vivo.
- Si `mcp` no está instalado, las pruebas se omiten (no fallan).

## Medición manual (no automatizada)

Servidores de terceros: `npx -y @modelcontextprotocol/server-everything` y `uvx mcp-server-time` con la misma sonda; los resultados de 2026-10-25 están en la decisión.
