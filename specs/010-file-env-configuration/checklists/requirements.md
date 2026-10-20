# Specification Quality Checklist: HU-00-04 — Configuración por archivo y variables de entorno

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

- Validación realizada en 1 iteración y reevaluada tras `/speckit-clarify` (sesión 2026-10-20): los 3 `[NEEDS CLARIFICATION]` se resolvieron con las respuestas de la persona responsable y quedaron registrados en la sección Clarifications del spec: **FR-004** (los valores no secretos los define solo el archivo; las variables de entorno solo aportan claves, salvo `HARNESS_CONFIG`), **FR-005** (`config.toml` en el directorio de trabajo actual; otra ubicación por parámetro explícito de la función de carga o por `HARNESS_CONFIG`, y el parámetro gana; `config.toml` y `.env` al `.gitignore`, solo se versionan las plantillas) y **FR-006** (archivo inexistente, ilegible o con sintaxis rota: se detiene el arranque, sin valores por defecto).
- Tras la clarificación se añadieron 3 escenarios a la historia 1 (ubicación del archivo, archivo inexistente o roto, variables de entorno que no sobrescriben valores no secretos) y se concretaron FR-018 y FR-019 con los nombres de las plantillas y de los archivos ignorados. AC-01, AC-02 y las dos reglas de negocio no se tocaron.
- Los ítems «sin detalles de implementación» y «para no técnicos» se evalúan con el mismo criterio que `specs/006-tool-registry-validation`: el público es el equipo de desarrollo y la persona operadora. El formato TOML se nombra porque lo fija el árbol acordado (`config.example.toml`) y es visible para quien edita el archivo; `config.py`, `core/` y «biblioteca estándar» aparecen solo en Assumptions como restricciones de arquitectura.
- Los criterios de aceptación AC-01 y AC-02 y las dos reglas de negocio están copiados literalmente de `docs/04a-historias-fundacion.md` (inmutables, Principio V).
- Diferencia con la documentación (gana el documento donde fija algo, y se indica): el árbol acordado describe `config.example.toml` con «reglas de permisos»; esta spec las deja fuera (HU-05-xx) y, por falla cerrada, hoy un campo de permisos se rechaza como desconocido. El formato TOML, `config.py` fuera de `core/`, `.env.example` y `config.example.toml` sí coinciden con el árbol acordado.
- Supuestos que hubo que asumir (ver Assumptions): el modelo no tiene valor por defecto; la raíz del área autorizada sin configurar significa «sin autorización» (falla cerrada); los campos desconocidos del archivo se rechazan; las rutas relativas se resuelven respecto al directorio del archivo; el archivo se lee una sola vez (sin recarga en caliente); los errores no reproducen valores recibidos; el nombre de la variable de clave lo aporta cada modelo conocido; umbral de 100 ms para la carga (SC-007).
- Punto a confirmar (no bloqueante): el texto de RF-7.6, RNF-16 y RNF-21 no está en la documentación activa; el spec los interpreta a partir de la trazabilidad (ver Assumptions). Conviene confirmarlo con el Product Owner antes de cerrar la historia.
- Todos los ítems pasan; el spec está listo para `/speckit-plan`.
