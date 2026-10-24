# Specification Quality Checklist: HU-07-02 — Adaptador LiteLLM para el primer proveedor

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-24
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

- **Marcadores resueltos (2026-10-24, `/speckit-clarify`)**: FR-017 → dependencia opcional (extra, import perezoso, versión exacta también en `requirements-dev.txt`); FR-009 → campo aditivo `limits.max_output_tokens` (por defecto 4096), `limits.max_tokens` no se usa como tope por llamada (FR-014a); FR-012 → `RateLimitError` → `QuotaExceeded` provisional con mensaje que nombra el límite de tasa. Además, FR-008 exige manejar `ConversionError` de argumentos inválidos sin tocar el puerto ni `core/loop.py`, con prueba contra el bucle real (SC-009). No quedan marcadores.
- Es una historia de integración para un equipo técnico: la spec nombra rutas, tipos del puerto, la biblioteca y sus excepciones porque son el contrato acordado con el responsable y los hallazgos de SPK-01 (mismo criterio que las specs 009 y 012). Los criterios de éxito no dependen de herramientas concretas salvo donde la propia historia las exige (LiteLLM solo dentro del adaptador, regla de negocio 1).
- Los criterios de aceptación (AC-01), el flujo y la regla de negocio se copian sin cambios de `docs/04d-historias-conexiones.md` (Principio V).
- Verificado el 2026-10-24 en la documentación de LiteLLM: `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`; `ollama` sin clave (el servidor local por defecto y `api_base` se confirman en el plan).
- Riesgo cubierto por FR-008 (mecanismo a decidir en el plan): `from_openai_response` lanza `ConversionError` ante argumentos JSON inválidos; el adaptador debe interceptarlos para cumplir FR-008 sin cambiar el puerto ni el bucle (un `ToolCall` tiene `arguments: dict`).
- Pendiente de confirmación humana: acuerdo de A, B y C para la dependencia, visto bueno del PO sobre los proveedores añadidos, Sp1-45, revisión cruzada y CI remota; HU-07-01, HU-00-04 y HU-00-01 siguen sin ratificación técnica completa.
