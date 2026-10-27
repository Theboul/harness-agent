# Specification Quality Checklist: HU-05-02 — Lista de denegados y análisis de comandos compuestos

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-26
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

- Los 2 marcadores [NEEDS CLARIFICATION] se resolvieron en `/speckit-clarify` (2026-10-26): (1) `[permissions] deny_commands` solo añade, con visto bueno de B; (2) se deniega lo que se ejecuta (sustituciones, `bash -c` y similares analizables, destinos de redirección) y no los datos entre comillas. Se añadió la regla de coincidencia de la lista base (una palabra solo como programa; objetivo solo raíz, `~` o unidad completa; `dd if=` conservador) con escenarios de falsos positivos.
- Se nombran piezas existentes (herramienta `shell`, `[permissions]`, `ExactCallPolicy`, `[permission_denied]`) solo como contexto de lo que ya existe y con lo que hay que convivir; los requisitos describen comportamiento.
- Criterios de aceptación, flujo y reglas de negocio copiados textualmente de `docs/04c-historias-control.md#hu-05-02` (inmutables, Principio V).
- Dependencias HU-05-01 y HU-01-04 verificadas en `origin/main` (e60d101). Ya existía la lista de datos de HU-01-04 (`adapters/system/denied_commands.py`), que esta historia amplía sin duplicar.
- Historia del área C: revisión cruzada humana por A o B, revisión del PO de la lista base y visto bueno de B si se amplía `config.py` (no las marca Claude).
