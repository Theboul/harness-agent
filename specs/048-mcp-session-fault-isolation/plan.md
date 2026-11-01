# Plan: HU-00-05.2

**Spec**: [spec.md](spec.md)

## Enfoque

Solo pruebas. Un archivo nuevo en `tests/integration/` que cablea `compose()` (con servidores MCP reales y un `FakeProvider` guionado) y corre `run_session` con entrada de texto. Un espía sobre `client.call_tool` registra, por llamada, el nombre, el resultado y la duración (para «al instante» y para obtener el pid del servidor de demostración sin tocar el servidor).

## Project Structure (estructura-carpetas-harness)

| Archivo | Fila de la tabla | Motivo |
|---|---|---|
| `tests/integration/test_mcp_session_fault_tolerance.py` | `tests/integration/` — pruebas con piezas reales cableadas | Prueba de sesión completa con procesos hijo |

Sin archivos nuevos en `src/`. Receta: ninguna (no es herramienta, proveedor, almacén, comando ni evento).

## Constitution Check / Decision Gates (arquitectura-hexagonal-clean)

Regla en `core/`: no. Puerto nuevo: no. Adaptador nuevo: no. Conexión nueva en `bootstrap.py`: no. Prueba: sí, en la carpeta equivalente. Lista de `capas-y-reglas.md`: **no aplica a código nuevo** (no hay código de producción); se revisa contra el existente: `core/` sin importar `adapters`/SDK — sí cumple (sin cambios); `Composition` única raíz — sí; falla cerrada — sí (la prueba lo demuestra); protegidos intactos — sí (se verifica con `git diff`).

## Verificación de fronteras (verificar-fronteras-hexagonales)

La historia no toca `core/`, `cli/`, `adapters/`, `pyproject.toml` ni la CI. Se corre `pytest tests/architecture` y se deja el resultado en `PROGRESO.md`. No hay guarda `ast` nueva (no hay módulo nuevo de producción).

## Riesgos

- Procesos hijo en Windows: sondeo con tope y `close()` en `finally`; las rutas de sesión usan `--basetemp` corto.
- Duración: la prueba del servidor colgado espera el tope de 1 s (+ gracia de 5 s como máximo).
