---
name: verificar-fronteras-hexagonales
description: "Trigger: core/, import-linter, fronteras, arquitectura hexagonal, puerto, adaptador, imports del núcleo. Verifica que src/harness_agent/core/ no dependa de adapters, cli, observability ni SDKs externos."
license: Apache-2.0
metadata:
  author: "harness-team"
  version: "1.0"
---

## Activation Contract

Cargar al:
- Añadir o modificar cualquier archivo en `src/harness_agent/core/`.
- Añadir una dependencia en `pyproject.toml`.
- Tocar el pipeline de integración continua.
- Mover archivos entre `core/`, `adapters/` y `cli/`.
- Oír «solo necesito importar esto un momento en el núcleo».

## Hard Rules

- Las dependencias apuntan hacia el núcleo.
- `core/` NO importa `harness_agent.adapters`, `harness_agent.cli`, `harness_agent.observability`, `harness_agent.bootstrap`.
- `core/` NO importa `litellm`, `openai`, `anthropic`, `google`, `mcp`, `sqlite3`, `typer`, `click`, `rich`.
- `harness_agent.adapters` NO importa `harness_agent.cli`.
- `core/` NO llama `print` ni `input`; emite eventos por el bus.
- Los tipos de dominio (mensajes, eventos, resultados de herramienta) son propios, nunca clases de un SDK.
- NO añadir excepciones ni listas blancas a los contratos.

## Decision Gates

| Situación | Acción |
|---|---|
| El núcleo necesita una capacidad externa | Definir un puerto en `core/ports.py`; implementarlo en `adapters/`; conectarlo en `bootstrap.py` |
| El núcleo necesita mostrar algo | Emitir un evento; la CLI lo imprime |
| Falla `lint-imports` | Leer la cadena de imports; corregir la dirección de la dependencia |
| Falla solo el test `ast` | Probable stdlib prohibida (`sqlite3`) o `print`/`input`; mover a `adapters/` |

## Execution Steps

1. Comprobar que `pyproject.toml` contiene los contratos de `assets/importlinter.toml`; si faltan, añadirlos y `import-linter` a las dependencias de desarrollo.
2. Comprobar que existe `tests/architecture/test_fronteras.py`; si falta, copiar `assets/test_fronteras.py`.
3. Comprobar que el CI corre `lint-imports` antes de `pytest` en Ubuntu y Windows (`assets/ci.yml`).
4. Ejecutar `lint-imports` y `pytest tests/architecture`.
5. Si algo falla, aplicar la fila correspondiente de Decision Gates y repetir el paso 4.

## Output Contract

Devolver:
- Resultado de `lint-imports` y de `pytest tests/architecture` (pasa/falla, con la cadena de imports si falla).
- Archivos de `core/` que violan una regla y el puerto o evento propuesto.
- Confirmación de que el CI cubre ambos sistemas operativos.

## References

- `assets/importlinter.toml` — contratos de import-linter.
- `assets/test_fronteras.py` — test de respaldo con `ast`.
- `assets/ci.yml` — job de integración continua.
- `docs/CONTEXTO_HARNESS.md` — contratos entre módulos (sección 4).
