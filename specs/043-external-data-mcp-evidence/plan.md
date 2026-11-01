# Plan: HU-05-08 (solo AC-02)

**Spec**: [spec.md](spec.md) · Pruebas con `--basetemp` corto (`/c/tmp/pt43`).

## Constitution Check (skills del proyecto)

- **arquitectura-hexagonal-clean — Decision Gates**: ¿regla nueva en `core/`? No. ¿Puerto nuevo? No. ¿Adaptador nuevo? No. ¿Conexión nueva? No (se usa `compose()` y `register_mcp_tools` tal cual). ¿Prueba? Sí, de integración con el bucle real.
- **Lista de comprobación de `capas-y-reglas.md`**: `core/` sin imports nuevos: sí. Dependencias por constructor: sí (cliente doble inyectado). Eventos: solo los existentes: sí. Cambios en puertos/eventos: no. Prueba de integración en `tests/integration/`: sí. Sin red, claves ni consola: sí; el servidor real es local y por stdio (se omite si falta `mcp`).
- **estructura-carpetas-harness**: `tests/integration/test_external_data_mcp.py` — fila «prueba de integración con el `AgentLoop` real» (`tests/integration/`). Sin archivos nuevos en `src/`.
- **verificar-fronteras-hexagonales**: no se toca `core/`, `cli/`, `adapters/`, `pyproject.toml` ni CI; se corre `pytest tests/architecture` igualmente. No hay módulo nuevo, luego no hay guarda `ast` nueva.

## Diseño de la prueba

`build(...)` de `tests/unit/bootstrap_support.py` compone la cadena real de políticas y el bucle real con `FakeProvider` guionado y `DummyApprover`. Fuentes de resultado: (a) un cliente doble (`RemoteClient`) que registra llamadas y devuelve cualquier texto o forma de error; (b) el servidor de demostración real (`echo`) por `McpStdioClient`. Se pasa `system_name="Linux"` a `compose()` para que la lista de denegados sea la de bash en cualquier anfitrión; el shell real no se ejecuta porque la composición no tiene área de trabajo y lo peligroso se deniega antes.

## Riesgos

- La marca vive en el bucle (protegido, A): si el bucle cambiara, estas pruebas lo detectan.
- Una marca de origen específica por herramienta (no solo `is_external`) queda como decisión de A.
