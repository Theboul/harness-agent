# Modelo de datos (solo de prueba): SPK-03

Ninguna de estas estructuras entra en `src/`. Todas viven en `tests/spikes/compaction_sim.py`.

| Entidad | Campos | Notas |
|---|---|---|
| `Seed` | `key`, `sentinel`, `text` | Elemento sembrado; `key` ∈ {objetivo, instrucciones, reglas, ticket, criterios_ref, decision_1..n} |
| `EssentialBlock` (`frozen`) | `goal`, `instructions`, `rules`, `ticket_id`, `criteria_ref` | Cinco claves de HU-02-06.1; `render(criteria) -> Message` (rol `SYSTEM`) |
| `CriteriaSource` (Protocol) | `read(ref) -> str` | Doble de solo lectura de la fuente protegida (HU-11-01); `KeyError` si la referencia no existe |
| `Summarizer` (Protocol, async) | `summarize(old, previous_summary) -> str` | `LossySummarizer` (estrés) y `ProviderSummarizer` (`FakeProvider`) |
| `CompactionState` | `summary`, `covered_until` | Equivale a una fila de `resumenes`; el historial no se muta |
| `Survival` | `{key: bool}` por paso | Presencia del centinela en el contexto ensamblado |

Reglas: el historial de entrada es una `tuple[Message, ...]` que nunca se modifica; el resumen previo es entrada de la compactación siguiente; el corte nunca separa un mensaje `ASSISTANT` con `tool_calls` de sus resultados `TOOL`.
