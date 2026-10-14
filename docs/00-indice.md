# Índice de la documentación

> Contexto del proyecto **harness-agent**, dividido en archivos enlazados. Empezar aquí.

## Orden de lectura

| Archivo | Para qué | Contiene (original) |
|---|---|---|
| [01-vision-y-decisiones.md](01-vision-y-decisiones.md) | Qué es, equipo, alcance y decisiones V-01 a V-14 | §1, §2, §5 |
| [02-arquitectura.md](02-arquitectura.md) | Diagramas, contratos, eventos y modelo de datos | §3, §4 |
| [03-plan-sprints.md](03-plan-sprints.md) | Pruebas, riesgos, épicas, sprints y tareas | §6 a §9 |
| [04a-historias-fundacion.md](04a-historias-fundacion.md) | E0 Fundaciones, E1 Bucle | §10 |
| [04b-historias-estado.md](04b-historias-estado.md) | E2 Contexto, E3 Sesiones, E4 Memoria | §10 |
| [04c-historias-control.md](04c-historias-control.md) | E5 Permisos, E6 Interacción | §10 |
| [04d-historias-conexiones.md](04d-historias-conexiones.md) | E7 Proveedores, E8 MCP, E9 Subagentes, E10 Trazas, EI Innovación | §10 |
| [04e-historias-coding-harness.md](04e-historias-coding-harness.md) | E11 Coding Harness: del ticket al Pull Request | §10 |
| [05-trazabilidad.md](05-trazabilidad.md) | Requisito → historia y cómo empezar | §11, §12 |
| [PROGRESO.md](PROGRESO.md) | **Qué se hizo y dónde está** | nuevo |

## Dónde está cada ID

| ID | Archivo |
|---|---|
| `V-01` a `V-14` (decisiones) | [01-vision-y-decisiones.md](01-vision-y-decisiones.md) |
| `R-1` a `R-15` (riesgos) | [03-plan-sprints.md](03-plan-sprints.md) |
| `Sp1-xx`, `Sp2-xx`, `Sp3-xx` (tareas) | [03-plan-sprints.md](03-plan-sprints.md) |
| `RF-*`, `RNF-*` (requisitos) | [05-trazabilidad.md](05-trazabilidad.md) |
| `HU-00-xx`, `HU-01-xx`, `SPK-02` | [04a-historias-fundacion.md](04a-historias-fundacion.md) |
| `HU-02-xx`, `HU-03-xx`, `HU-04-xx`, `SPK-03` | [04b-historias-estado.md](04b-historias-estado.md) |
| `HU-05-xx`, `HU-06-xx` | [04c-historias-control.md](04c-historias-control.md) |
| `HU-07-xx` a `HU-10-xx`, `HU-IN-xx`, `SPK-01`, `SPK-04` | [04d-historias-conexiones.md](04d-historias-conexiones.md) |
| `HU-11-xx` (Coding Harness) | [04e-historias-coding-harness.md](04e-historias-coding-harness.md) |
| Estado, commits y evidencia de cualquiera | [PROGRESO.md](PROGRESO.md) |

## Convenciones

- Cada historia tiene un ancla con su ID en minúsculas: `04c-historias-control.md#hu-05-03`.
- Los IDs en texto enlazan a su historia; el estado no se repite fuera de `PROGRESO.md`.
- La numeración de secciones (§1 a §12) conserva la del documento original.
- El documento original del análisis se conserva solo como histórico en [archivo/CONTEXTO_HARNESS_v1.md](archivo/CONTEXTO_HARNESS_v1.md); no se edita. Los cambios van a `01` a `05` y `PROGRESO.md`.
- Las skills del proyecto están en `.claude/skills/`: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness`, `verificar-fronteras-hexagonales`.

---

[Índice](00-indice.md) · [01-vision-y-decisiones.md →](01-vision-y-decisiones.md)
