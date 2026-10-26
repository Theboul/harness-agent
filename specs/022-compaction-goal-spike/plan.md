# Plan de implementación: SPK-03 — Compactación sin perder el objetivo

**Spec**: [spec.md](spec.md) · **Rama**: `feat/spk-03-compaction-goal-spike` · **Fecha**: 2026-10-25

## Resumen técnico

Pruebas de caracterización en `tests/spikes/` sobre una sesión larga simulada y determinista. Un módulo de apoyo (`tests/spikes/compaction_sim.py`) modela tres cosas, todas de prueba y ninguna de producción: (1) el ensamblado de contexto en dos diseños, «solo resumen» y «bloque fijo + resumen», (2) dos resumidores, uno **con pérdida** (modelo de peor caso, sesgado a lo reciente) y otro que llama a `FakeProvider` con una respuesta guionizada (comprueba qué entra a la llamada de resumen), y (3) un evaluador de supervivencia por centinelas. Se compacta dos veces y se mide qué sobrevive. Los hallazgos van a `docs/decisiones/SPK-03-compactacion-bloque-fijo.md`.

## Technical Context

**Language/Version**: Python 3.12.x · **Primary Dependencies**: ninguna nueva (stdlib, pytest, `FakeProvider`) · **Storage**: N/A (sin SQLite; la tabla `contexto_esencial` se modela en memoria) · **Testing**: pytest, `asyncio_mode = "auto"` · **Target Platform**: Windows y Linux (CI) · **Project Type**: spike de pruebas · **Constraints**: sin red, sin claves, sin cambios en `src/`, puertos ni eventos · **Scale/Scope**: sesión de ~80 mensajes, dos compactaciones

## Decisiones de diseño del spike

- **D1 — Dos diseños comparados con el mismo historial.** «Solo resumen» (todo, también el objetivo, vive en el historial y se resume) frente a «bloque fijo» (las cinco claves de la ficha de HU-02-06.1 en un mensaje de sistema inyectado en cada ensamblado y excluido de la entrada del resumen).
- **D2 — Resumidor con pérdida = modelo de estrés, no predicción.** Conserva un presupuesto fijo de caracteres, de lo nuevo a lo viejo, tratando el resumen previo como lo más viejo. Es el patrón de degradación de un resumen recursivo; no representa a un modelo real.
- **D3 — `FakeProvider` para la llamada aparte.** `ProviderSummarizer` arma la petición de resumen (prompt + historial antiguo) y la envía a `Provider.complete`. El guion devuelve resúmenes fieles o con pérdida. Se verifica **la entrada** de la llamada (no contiene el bloque fijo ni los mensajes recientes), no la calidad del texto.
- **D4 — Criterios por referencia.** El bloque guarda `criteria_ref` y el ensamblador lee los criterios de un `CriteriaSource` de solo lectura (doble); cambiar la fuente cambia el contexto sin tocar el resumen.
- **D5 — Corte seguro.** El punto de corte entre «antiguo» y «reciente» no puede separar una llamada a herramienta de su resultado; se prueba una función de corte que retrocede hasta un límite válido.
- **D6 — Centinelas únicos.** Cada elemento esencial y cada decisión lleva una cadena única (`OBJ-…`, `TCK-4821`, `DEC-…`); la supervivencia es presencia de la cadena y, para el bloque, igualdad byte a byte del mensaje.
- **D7 — Estimación local de tokens** (`ceil(len/4)`) solo para informar tamaños en la decisión; no es HU-02-01.

## Project Structure (skill `estructura-carpetas-harness`)

| Archivo | Fila de la tabla | Justificación |
|---|---|---|
| `tests/spikes/compaction_sim.py` | Prueba (apoyo del spike) | Precedente `tests/spikes/` y `tests/litellm_offline.py`; no es un doble reutilizable, así que no va a `tests/doubles/` (protegido) |
| `tests/spikes/test_compaction_goal_spike.py` | Prueba | Precedente: `tests/spikes/` (SPK-01, SPK-02) |
| `docs/decisiones/SPK-03-compactacion-bloque-fijo.md` | Documentación | Precedente: `docs/decisiones/SPK-01-…` |
| `specs/022-compaction-goal-spike/` | Artefactos de la historia | Convención `specs/NNN-slug/` |

No se crea código en `src/` (la skill reserva `core/context/` para HU-02-03/HU-02-06.1 y `adapters/storage/` para la tabla real). No es una pieza nueva de producción: no hay receta que seguir.

## Constitution Check y skills

Lista de comprobación de `arquitectura-hexagonal-clean` (`capas-y-reglas.md`):

| Punto | Sí/No | Justificación |
|---|---|---|
| `core/` sin imports de `adapters/`, `cli/`, `config`, SDKs | Sí | `core/` no se toca |
| Todo lo externo por un puerto | Sí | El resumen usa el puerto `Provider` (con `FakeProvider`); sin E/S real |
| Puertos nuevos o modificados | No | Ninguno; si hiciera falta uno, queda como hallazgo (FR-007) |
| Eventos nuevos | No | Se usa el `CONTEXT_COMPACTED` existente; su payload se discute en la decisión sin tocar el catálogo |
| Tipos de dominio inmutables | Sí | Se usan `Message` y `dataclass(frozen=True)` en el apoyo |
| Dependencias por constructor, reloj e ids inyectados | Sí | El apoyo recibe resumidor y fuente por constructor; sin reloj ni aleatoriedad |
| Falla cerrada | Sí | Un `criteria_ref` sin fuente falla el ensamblado, no lo omite |
| Pruebas sin red, claves ni consola | Sí | `FakeProvider`; sin E/S |

- `verificar-fronteras-hexagonales`: no cambia `core/`, `cli/`, `adapters/`, `pyproject.toml` ni la CI; no hay módulo nuevo en `core/`, por tanto no hay guarda nueva. Se ejecuta `pytest tests/architecture`.
- Principio VI: no se implementa HU-02-01, HU-02-03 ni HU-02-06.1. Principio VII: solo se leyeron las fichas de SPK-03, HU-02-01, HU-02-03, HU-02-06.1 y HU-03-04.
- Principio II: tareas de 15–40 min (ver `tasks.md`).

## Fases

- **Fase 0** — [research.md](research.md): qué dicen la ficha, la arquitectura y los puertos que condicionan el diseño.
- **Fase 1** — [data-model.md](data-model.md), [contracts/essential-block.md](contracts/essential-block.md), [quickstart.md](quickstart.md).
