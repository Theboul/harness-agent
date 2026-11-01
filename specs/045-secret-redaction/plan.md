# Plan: HU-10-02 — Redacción de secretos en registros

**Spec**: [spec.md](spec.md) · Pruebas con `--basetemp` corto (`/c/tmp/pt45`).

## Constitution Check (skills del proyecto)

- **arquitectura-hexagonal-clean — Decision Gates**: ¿regla en `core/`? Sí: qué es un secreto (`core/secret_redaction.py`, función pura, stdlib). ¿Puerto nuevo? No: el redactor es un `Callable[[str], str]` inyectado en los colaboradores existentes (`core/interfaces/` no cambia). ¿Adaptador? Solo se amplían `attach_event_recorder` y `SqliteCompactionArchive` con un parámetro opcional. ¿Conexión? `compose()` construye el redactor (única raíz). ¿Prueba? Unitarias, de almacén, de integración con `/reanudar` y guarda `ast`.
- **Lista de comprobación de `capas-y-reglas.md`**: `core/` solo importa stdlib y `core.redaction`: sí. No lee archivos ni entorno (el entorno llega como `Mapping` por constructor): sí. Dependencias por constructor: sí. Sin `print`/`input`: sí. Eventos: los existentes: sí. Puertos y `core/loop.py` intactos: sí. Prueba de integración en `tests/integration/`: sí.
- **estructura-carpetas-harness**: `src/harness_agent/core/secret_redaction.py` — fila «regla de dominio pura», exportada en `core/__init__.py`. Pruebas: `tests/unit/core/test_secret_redaction.py`, `tests/unit/adapters/storage/test_secret_redaction_storage.py`, `tests/integration/test_secret_redaction_resume.py`, `tests/architecture/test_secret_redaction_boundaries.py`.
- **verificar-fronteras-hexagonales**: se toca `core/` y `adapters/`: `pytest tests/architecture` más guarda `ast` nueva (stdlib, sin E/S ni entorno, sin async).

## Diseño

`redact_secrets(text, *, known=())`: (1) `hide_url_credentials`; (2) valores conocidos (≥ 8 caracteres, más largos primero, `str.replace`); (3) una expresión regular de prefijos y JWT, y `Bearer`/`Basic` con comprobación en la función de reemplazo; (4) pares `nombre=valor` **sin retroceso**: se recorre cada `=`/`:` y se mira hacia atrás un máximo de 64 caracteres (coste lineal). Todo sustituye por `HIDDEN_SECRET`, que no coincide con ningún patrón (idempotencia).

`SecretRedactor(known)`: invocable `str -> str` y `value(obj)` recursivo (cadenas, listas, tuplas, mapas); `from_environment(environ, extra=())` toma los valores de variables cuyo nombre parece de clave (misma lista de marcadores que `config.py`, duplicada porque `core/` no importa `config`).

Cableado mínimo: `clean_message(..., redact=)`, `ConversationCapture(..., redact=)`, `attach_event_recorder(..., redact=)` (copia del evento con `payload` redactado antes de `save_event`), `SqliteCompactionArchive(..., redact=)` (resumen) y pocas líneas en `compose()`.

## Riesgos

- Heurística: falsos negativos y positivos documentados en la spec.
- El orden de suscripción de HU-03-04 (mensaje antes que evento) no cambia.
- `hide_url_credentials` queda dentro de la nueva redacción; su API no cambia.
