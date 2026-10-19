# Specification Quality Checklist: HU-01-01 — Bucle agéntico básico

**Purpose**: Validar la completitud y la calidad documental de la especificación antes de pasar a `/speckit-clarify` o `/speckit-plan`
**Created**: 2026-10-18
**Feature**: [spec.md](../spec.md)

**Review Ownership**: Lista de revisión de calidad de requisitos. `[x]` significa que el criterio se cumple en el texto de la especificación; no significa que haya implementación. Ninguna casilla refleja aprobación humana (A, B, C o Product Owner).

## Content Quality

- [x] CHK001 Sin detalles de implementación (lenguajes, frameworks, estructura de código nuevo); los contratos existentes se citan por nombre solo cuando la solicitud lo exige
- [x] CHK002 Centrada en el valor para el usuario operador y en las necesidades del equipo
- [x] CHK003 Redactada para lectores no técnicos en lo esencial (flujo, historias, criterios), con las referencias técnicas acotadas a secciones identificables
- [x] CHK004 Todas las secciones obligatorias están completas (escenarios, requisitos, criterios de éxito, supuestos)

## Requirement Completeness

- [x] CHK005 No quedan marcadores de aclaración pendientes (FR-028 resuelto por el PO en `/speckit-clarify`, Opción B; Q4 aprobada por el PO; ver «Preguntas abiertas y ratificaciones pendientes» para las coordinaciones con B y C)
- [x] CHK006 Los requisitos son comprobables y no ambiguos (FR-001 a FR-034)
- [x] CHK007 Los criterios de éxito son medibles (SC-001 a SC-010 con cifras o conteos verificables)
- [x] CHK008 Los criterios de éxito son independientes de la tecnología (las puertas de calidad se nombran de forma genérica)
- [x] CHK009 Todos los escenarios de aceptación están definidos (37 escenarios en 6 historias, positivos y negativos)
- [x] CHK010 Los casos límite están identificados (17, incluidos los pedidos: excepción de herramienta, desconocida, argumentos inválidos, DENY, ASK, error del proveedor, respuesta vacía, llamadas repetidas, muchas llamadas, resultado grande, cancelación, dependencia ausente, identificadores duplicados)
- [x] CHK011 El alcance está acotado, con lista explícita de lo que queda fuera
- [x] CHK012 Las dependencias y supuestos están identificados, con su estado real según `docs/PROGRESO.md`

## Feature Readiness

- [x] CHK013 Cada requisito funcional tiene criterios de aceptación o escenarios asociados (ver «Trazabilidad»)
- [x] CHK014 Los escenarios cubren los flujos primarios (AC-01, AC-02, permisos, historial, eventos, fallos)
- [x] CHK015 La especificación cumple los resultados medibles definidos en los criterios de éxito
- [x] CHK016 No se filtran detalles de implementación en la especificación (formas de datos nuevas, nombres de módulos, firmas nuevas)

## Documentary Quality (solicitud de esta especificación)

- [x] CHK017 AC-01 y AC-02 originales copiados literalmente de `docs/04a` y no modificados (verificado por comparación el 2026-10-18); reglas de negocio originales también literales
- [x] CHK018 Las firmas y nombres citados existen en `src/harness_agent/core/` (verificado contra el código: `Provider.complete`, `Tool.run`, `ToolRegistry.validate_args`, `PermissionPolicy.evaluate`, `EventBus.emit`, los 17 `EventType`)
- [x] CHK019 Los miembros de `EventType` usados existen; los que no se publican se listan con el motivo
- [x] CHK020 El estado de las dependencias coincide con `docs/PROGRESO.md` (HU-00-01 pendiente de aprobación técnica, HU-07-01 en revisión, HU-00-03/01-02/01-05/05-01 y SPK-01 pendientes, D-01 pendiente de aprobación) sin llamar aprobada a ninguna
- [x] CHK021 La lista de fuera de alcance incluye los ocho puntos solicitados
- [x] CHK022 Condición de parada, error de herramienta, validación de argumentos, permiso denegado, estado del historial, dependencia ausente y fallo/cancelación básicos están especificados
- [x] CHK023 Ninguna decisión pendiente se presenta como cerrada (D-01, T016/Sp1-03, T018)
- [x] CHK024 Los hallazgos entre la solicitud, la documentación y los contratos reales están registrados en «Clarifications» (flujo de 5 vs 10 pasos, validación en el registro, `ASK`, `call_id`, cita de V-13)

## Notes

- **Iteración 1**: CHK008 fallaba porque SC-010 nombraba herramientas concretas de calidad. Corregido en la iteración 2 (redacción genérica).
- **Iteración 2**: solo CHK005 permanece sin cumplir, por el marcador abierto de FR-028 (esperado y dentro del máximo de 3). Se resuelve en `/speckit-clarify` o por decisión directa; no se avanza automáticamente.
- **Iteración 3 (`/speckit-clarify`, 2026-10-18)**: FR-028 resuelto por el PO (Opción B, sin tope interno); CHK005 pasa (23/24 → 24/24). Se actualizaron los conteos de CHK006, CHK009 y CHK010 (34 escenarios, 17 casos límite). Sin regresiones. Sigue pendiente de ratificación del PO la propuesta de «Clarify Q4».
- **Iteración 4 (`/speckit-plan`, 2026-10-18)**: Q4 registrada como aprobada por el PO (Clarifications, US4-4/US4-5, FR-031, Preguntas abiertas); se añadió el escenario US4-5 (fallo de `emit` tras una operación con efectos), por lo que CHK009 pasa a 35 escenarios. Estados de los ítems sin cambios (24/24); sin regresiones.
- **Iteración 5 (`/speckit-tasks`, 2026-10-18)**: se incorporaron las decisiones R-07 (la política evalúa los argumentos efectivos validados; FR-008, US3-8) y R-08 (la cancelación prevalece sobre un fallo de `emit(INTERRUPTED)`; FR-026, US6-6); CHK009 pasa a 37 escenarios. Estados de los ítems sin cambios (24/24); sin regresiones.
- Esta lista no sustituye la revisión por otra área ni la aprobación del Product Owner (Principio IX).
