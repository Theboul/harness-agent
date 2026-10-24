# Plan de implementación: SPK-01

**Spec**: [spec.md](spec.md) · **Rama**: `feat/spk-01-litellm-tool-spike`

## Resumen técnico

Pruebas de caracterización en `tests/spikes/` que ejecutan `litellm.completion` real contra dos transportes simulados: `HTTPHandler.post` para Anthropic (LiteLLM usa su propio cliente `httpx`) y un `httpx.MockTransport` inyectado en el cliente `openai` para OpenAI. Un guardia de red bloquea `socket.getaddrinfo` y `socket.create_connection`. Los hallazgos van en un documento de decisiones.

## Decisiones

- **D1 — Sin `socket.connect`**: asyncio crea su tubería interna con `socketpair`, que en Windows es una conexión de bucle local; bloquear `connect` rompe el bucle de eventos. Se bloquea la resolución de nombres y `create_connection`.
- **D2 — `pytest.importorskip`**: `litellm`, `openai` y `httpx` se importan así, de modo que la CI (sin `litellm`) omite el módulo y `mypy` no necesita sus tipos.
- **D3 — `LITELLM_LOCAL_MODEL_COST_MAP=True`** antes de importar, para que LiteLLM no descargue su tabla de precios.
- **D4 — Entorno aparte**: `litellm` se instala en un venv fuera del repositorio con ruta corta (en Windows, una ruta larga dejó la instalación incompleta sin avisar).
- **D5 — Respuestas simuladas escritas a mano**: son supuestos documentados, no capturas; el documento lo declara.

## Project Structure (skill `estructura-carpetas-harness`)

| Archivo | Fila de la tabla | Justificación |
|---|---|---|
| `tests/spikes/test_litellm_tool_translation_spike.py` | Prueba | Precedente: `tests/spikes/` (SPK-02) |
| `docs/decisiones/SPK-01-traduccion-herramientas-litellm.md` | Documentación | Precedente: `docs/decisiones/D-01…` |
| `specs/016-litellm-tool-translation-spike/` | Artefactos de la historia | Convención `specs/NNN-slug/` |

No se crea código en `src/`: el spike no produce piezas de producción (la skill reserva `adapters/providers/` para HU-07-02).

## Constitution Check y skills

- `arquitectura-hexagonal-clean`: no se toca `core/` ni se crean puertos; `litellm` no entra en el núcleo. Lista de comprobación: sin puertos nuevos (sí), sin `core/` modificado (sí), dependencia de tercero fuera de `src/` (sí), inyección del transporte en lugar de red real (sí).
- `verificar-fronteras-hexagonales`: sin cambios en `core/`, `cli/`, `adapters/`, `pyproject.toml` ni CI; se ejecuta `pytest tests/architecture`.
- Principio VI: no se implementa HU-07-02. Principio VII: solo se leyó la ficha de SPK-01.
