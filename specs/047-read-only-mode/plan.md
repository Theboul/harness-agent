# Plan: HU-05-07 — Modo de solo lectura

**Spec**: [spec.md](spec.md) · Skills aplicadas: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness`, `verificar-fronteras-hexagonales`.

## Decision Gates (arquitectura-hexagonal-clean)

| Gate | Resultado |
|---|---|
| ¿Regla de negocio? | Sí: `core/permissions/read_only.py` (`ReadOnlyPolicy`). Clasificación de lecturas de git: `only_git_reads` en `core/permissions/git_reads.py`, que pregunta a `GitPolicy` (misma tabla; `git_rules.py` no cambia porque su guarda limita dónde aparece `ALLOW`). |
| ¿Puerto nuevo? | **No.** Usa `PermissionPolicy` existente; el clasificador es un invocable inyectado. |
| ¿Adaptador? | No hay E/S nueva. |
| ¿Dónde se conecta? | Solo `bootstrap.py` (`compose(read_only=)`, `--solo-lectura`, aviso, `ModelView`). |
| ¿Cómo se prueba? | Unitarias con `ScriptedPolicy`; integración con `AgentLoop` real y cadena real. |

## Estructura (estructura-carpetas-harness)

| Archivo | Fila |
|---|---|
| `src/harness_agent/core/permissions/read_only.py`, `git_reads.py` | Regla de permisos → `core/permissions/` |
| `tests/unit/core/permissions/test_read_only.py`, `test_git_read_only.py` | Equivalente en `tests/` |
| `tests/unit/test_bootstrap_read_only.py`, `tests/unit/test_config_read_only.py`, `tests/integration/test_read_only_agent_loop.py` | Composición, config, bucle real |
| `tests/architecture/test_read_only_boundaries.py` | Guarda `ast` del módulo nuevo |

Cambios mínimos en: `core/permissions/__init__.py`, `core/__init__.py` (export), `config.py` (`read_only`), `bootstrap.py`, `cli/session_commands.py` (`ModelView.read_only`, línea en `/model`), `config.example.toml`.

## Diseño

- `ReadOnlyPolicy` evalúa: no `ToolCall` → `DENY`; nombre en `read_tools` → decisión de `inner`; herramienta de comandos con clasificador `True` → decisión de `inner`; resto → `DENY`. Sin `ALLOW` literal (solo endurece), sin estado.
- Cadena con el modo: `ReadOnlyPolicy(ProtectedPolicy(CommandPolicy(GitPolicy(…))))`: la denegación del modo prevalece sobre cualquier permitir de dentro, y los `DENY` de dentro siguen valiendo.
- Clasificador: `lambda c: only_git_reads(c, deny_list.dialect)`.

## Constitution Check

| Principio / skill | Resultado |
|---|---|
| Núcleo solo stdlib, sin E/S ni terminal | Cumple. |
| Falla cerrada | Cumple (todo lo desconocido se deniega). |
| Contratos protegidos intactos | Cumple. |
| Lista `capas-y-reglas.md`: dependencias por constructor, una sola raíz de composición, sin puerto nuevo justificado | sí / sí / sí (la política usa el puerto existente). |

## Hallazgos esperados

1. Subagentes (HU-09-xx) deben heredar la política envolvente.
2. En este modo `ls`, `cat`, `pytest` se deniegan: falta una tabla de lecturas del shell (decisión del PO).
3. `cli/session_commands.py` (protegido por defecto) gana un campo con valor por defecto, cambio mínimo.
