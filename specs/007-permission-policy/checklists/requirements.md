# Specification Quality Checklist: HU-05-01 — Política denegar, preguntar, permitir que falla cerrada

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-20
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

- Validación en 1 iteración y reevaluada tras `/speckit-clarify` (sesión 2026-10-21): las 3 preguntas abiertas se resolvieron (Q1 opción B, Q2 opción A, Q3 opción A) y ya no quedan marcadores; el ítem «No [NEEDS CLARIFICATION] markers remain» pasa a marcado. Queda **un supuesto pendiente de confirmación del PO** (regla de lectura acotada al área, FR-007), que amplía el texto «único permiso explícito del Sprint 1» sin modificarlo y que la tarea de cierre debe registrar en `docs/PROGRESO.md`.
- Los ítems «sin detalles de implementación» y «para no técnicos» se evalúan con el mismo criterio que las specs 009, 010 y 011: el público es el equipo de desarrollo y la persona operadora, y se nombran los puertos y el bucle porque son el contrato de la historia.
- AC-01 a AC-05 y las cinco reglas de negocio están copiados literalmente de `docs/04c-historias-control.md` (inmutables, Principio V).
- Tensión que se indica porque el documento gana donde fija algo: el encargo dice «ante duda, denegar», pero AC-01 (inmutable) dice que lo no previsto **pide aprobación**. La spec lo resuelve así: lo que no se puede evaluar con seguridad (llamada mal formada, error al evaluar) se deniega; lo que ninguna regla prevé se pregunta; en el Sprint 1 ambos acaban denegados porque el bucle resuelve «preguntar» como denegación (AC-05). La tabla «Casos de falla cerrada» lo deja caso por caso.
- Hallazgo sobre el código existente: la resolución provisional de «preguntar» (Sp1-35) y el registro de la decisión ya están en el bucle de A (`_decide` y `PERMISSION_DECIDED`); la spec los trata como ya hechos y como lo que hay que verificar con la política real, no como trabajo nuevo.
- Hallazgo sobre las dependencias: HU-01-03 (herramientas de archivos y componente real de área) aún no existe; la política depende solo del puerto `AuthorizedArea` y del atributo de riesgo de las herramientas, y se prueba con dobles.
- Supuesto a confirmar (no marcado como pregunta): la sección `[permissions]` con las listas `deny` y `ask` amplía el esquema de `config.py` (HU-00-04); sin reglas de permitir configurables.
- Punto no bloqueante: el texto de RF-5.1, RF-5.2 y RF-5.3 no está en la documentación activa; solo su trazabilidad.
