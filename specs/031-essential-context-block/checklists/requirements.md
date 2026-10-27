# Specification Quality Checklist: HU-02-06.1 — Contexto esencial persistente fuera del historial compactable

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-27
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- `/speckit-clarify` (2026-10-27) resolvió los dos marcadores: Q1 = A (el bloque se renueva al empezar cada petición y entre las rondas de verificación, en la composición; el bucle, los puertos y el catálogo de eventos no cambian; limitación conocida y aviso a A sobre un único gancho futuro) y Q2 = A con la condición de que el bloque no repita el texto de las instrucciones (los mensajes provisionales de hoy son las instrucciones; el registro del almacén solo sirve para reconstruir y no se inyecta).
- Contradicción hallada al registrar y resuelta con la opción más conservadora: una sesión **sin tarea no recibe bloque** (la ficha habla de la sesión del ticket; el bloque con la primera petición cambiaría el contexto de toda sesión sin tarea y pruebas existentes). Queda como decisión del PO (H4).
- La historia tiene **1 PHU** en la ficha; se desarrolla en cinco historias de usuario: el bloque llega íntegro en cada llamada (P1), la compactación no lo toca (P1), los criterios se leen de su fuente (P1), el objetivo se recuerda tras compactar (P2) y cambios, tamaño y presupuesto (P2).
- Flujo, reglas de negocio y criterios de aceptación copiados por script de `docs/04b-historias-estado.md#hu-02-06-1` (inmutables, Principio V).
- Los requisitos describen comportamiento; no hay nombres de archivos de código en ellos. Las notas para el plan (esquema 4 aditivo, convivencia bloque y resumen, dónde se renueva, costo en tokens) están en los supuestos y no son requisitos.
- Hallazgo de alcance: hoy ningún texto de la tarea (objetivo, reglas, criterios) llega al modelo (el paso 5 del flujo de HU-11-01 está sin hacer); el bloque es donde lo recibe por primera vez (H7).
- Puertos, bucle y catálogo de eventos: sin cambios; si el plan descubriera que hacen falta, se detiene y se plantea a A, B y C.
