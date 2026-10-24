# Índice de la documentación

> Contexto del proyecto **harness-agent**, dividido en archivos enlazados. Empezar aquí.

> **Plan vigente: contexto v2.5.** Cuatro sprints con cierre máximo el 14/11/2026. El reparto ampliado del Sprint 4 está por ratificar en el Planning; mientras tanto es plan base provisional. Ver [01-vision-y-decisiones.md](01-vision-y-decisiones.md) y [06-historial-planificacion.md](06-historial-planificacion.md).

## Orden de lectura

| Archivo | Para qué | Contiene (original) |
|---|---|---|
| [01-vision-y-decisiones.md](01-vision-y-decisiones.md) | Qué es, equipo, alcance y decisiones V-01 a V-17 | §1, §2, §5 |
| [02-arquitectura.md](02-arquitectura.md) | Diagramas, contratos, eventos y modelo de datos | §3, §4 |
| [03-plan-sprints.md](03-plan-sprints.md) | Pruebas, riesgos, épicas, sprints y tareas | §6 a §9 |
| [04a-historias-fundacion.md](04a-historias-fundacion.md) | E0 Fundaciones, E1 Bucle | §10 |
| [04b-historias-estado.md](04b-historias-estado.md) | E2 Contexto, E3 Sesiones, E4 Memoria | §10 |
| [04c-historias-control.md](04c-historias-control.md) | E5 Permisos, E6 Interacción | §10 |
| [04d-historias-conexiones.md](04d-historias-conexiones.md) | E7 Proveedores, E8 MCP, E9 Subagentes, E10 Trazas, EI Innovación | §10 |
| [04e-historias-coding-harness.md](04e-historias-coding-harness.md) | E11 Coding Harness: del ticket al Pull Request | §10 |
| [05-trazabilidad.md](05-trazabilidad.md) | Requisito → historia y cómo empezar | §11, §12 |
| [06-historial-planificacion.md](06-historial-planificacion.md) | Auditoría, decisiones PD-01 a PD-06, capacidad y consolidación v2.5 | §13 |
| [PROGRESO.md](PROGRESO.md) | **Qué se hizo y dónde está** | nuevo |
| [guia-contratos-desarrollo.md](guia-contratos-desarrollo.md) | Guía de uso de los contratos del núcleo para A, B y C | nuevo |
| [decisiones/](decisiones/) | Decisiones técnicas: D-01 (asyncio y cancelación), D-02 (metadatos en la conversión) y la revisión conjunta | nuevo |
| [../CLAUDE.md](../CLAUDE.md) | Contexto base para cada sesión que implementa una historia | nuevo |
| [../specs/](../specs/) | Artefactos Spec Kit de cada historia trabajada (`specs/NNN-slug/`) | nuevo |

## Dónde está cada ID

| ID | Archivo |
|---|---|
| `V-01` a `V-17` (decisiones) | [01-vision-y-decisiones.md](01-vision-y-decisiones.md) |
| `R-1` a `R-22` (riesgos) | [03-plan-sprints.md](03-plan-sprints.md) |
| `Sp1-xx` a `Sp4-xx` (tareas) | [03-plan-sprints.md](03-plan-sprints.md) |
| `A-01` a `A-14` (auditoría), `PD-01` a `PD-06` (decisiones de planificación) | [06-historial-planificacion.md](06-historial-planificacion.md) |
| `RF-*`, `RNF-*` (requisitos) | [05-trazabilidad.md](05-trazabilidad.md) |
| `HU-00-xx` (incl. `.1` y `.2`), `HU-01-xx`, `SPK-02` | [04a-historias-fundacion.md](04a-historias-fundacion.md) |
| `HU-02-xx` (incl. `HU-02-06.1` y `.2`), `HU-03-xx`, `HU-04-xx`, `SPK-03` | [04b-historias-estado.md](04b-historias-estado.md) |
| `HU-05-xx`, `HU-06-xx` | [04c-historias-control.md](04c-historias-control.md) |
| `HU-07-xx` a `HU-10-xx`, `HU-IN-xx`, `SPK-01`, `SPK-04` | [04d-historias-conexiones.md](04d-historias-conexiones.md) |
| `HU-11-xx` (Coding Harness; `HU-11-04.x` y `HU-11-08.x`) | [04e-historias-coding-harness.md](04e-historias-coding-harness.md) |
| Estado, commits y evidencia de cualquiera | [PROGRESO.md](PROGRESO.md) |

## Convenciones

- Cada historia tiene un ancla con su ID en minúsculas: `04c-historias-control.md#hu-05-03`. Las historias divididas llevan sufijo: `04e-historias-coding-harness.md#hu-11-04.1`.
- Los IDs en texto enlazan a su historia; el estado no se repite fuera de `PROGRESO.md`.
- La numeración de secciones (§1 a §13) conserva la del documento original.
- Los documentos originales del análisis se conservan solo como histórico en `archivo/`: [v1](archivo/CONTEXTO_HARNESS_v1.md), [v2](archivo/CONTEXTO_HARNESS_v2.md) y [v2.5](archivo/CONTEXTO_HARNESS_v2.5.md) (vigente). No se editan. Los cambios van a `01` a `06` y `PROGRESO.md`.
- Las skills del proyecto están en `.claude/skills/`: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness`, `verificar-fronteras-hexagonales`.

---

[Índice](00-indice.md) · [01-vision-y-decisiones.md →](01-vision-y-decisiones.md)
