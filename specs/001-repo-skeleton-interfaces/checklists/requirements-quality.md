# Checklist de Calidad de Requisitos: HU-00-01 (Fundaciones y Contratos)

**Purpose**: Validación de calidad, claridad, completitud y gobernanza de los requisitos de HU-00-01 antes de la descomposición en tareas de implementación.  
**Created**: 2026-10-17  
**Feature**: [spec.md](../spec.md) | **Plan**: [plan.md](../plan.md)  

**Note**: Esta checklist es un artefacto de revisión de calidad de requisitos ("Unit Tests for Requirements"). No evalúa la ejecución de código.  
**Review Ownership**: Artefacto propiedad del revisor humano / equipo de desarrollo. Marcar una casilla `[x]` únicamente cuando la revisión confirme que el criterio de calidad del requisito está completamente satisfecho.  
**Marker Semantics**: `[x]` indica que la redacción y especificidad del requisito es satisfactoria; NO indica que el código esté implementado.  

---

## 1. Criterios de Aceptación Obligatorios (AC-01 y AC-02)

- [ ] CHK001 - ¿Están los requisitos de importabilidad con dobles de prueba (AC-01) especificados con firmas y tipos concretos para que los módulos dependientes puedan instanciarlos sin dependencias externas? [Completitud, Spec §User Story 1, SC-003]
- [ ] CHK002 - ¿Está la restricción de ausencia de SDKs propietarios de proveedores en el núcleo (AC-02) formulada de manera medible y auditable automáticamente mediante análisis estático? [Medibilidad, Spec §User Story 2, SC-002]

## 2. Claridad de Contratos Provisionales (SPK-01 y SPK-02)

- [ ] CHK003 - ¿Están las firmas asíncronas (`async def`) de `Provider`, `Tool` y `Approver` claramente marcadas como provisionales y dependientes del veredicto del spike `SPK-02` sin asumir adopción definitiva? [Claridad, Spec §Clarifications, Plan §Technical Context]
- [ ] CHK004 - ¿Se especifica explícitamente que los formatos de mensajes y llamadas a herramientas quedan sujetos a los hallazgos de `SPK-01` sin congelar esquemas de proveedores propietarios? [Consistencia, Spec §Scope & Boundaries, Plan §Technical Context]

## 3. Delimitación de Alcance y Disciplina de Sprints

- [ ] CHK005 - ¿Están las exclusiones de alcance (no implementar bucle agéntico `HU-01-01`, herramientas reales `HU-01-03`, SQLite `HU-03-01`, MCP `HU-08-xx` ni shell `HU-01-04`) formalmente delimitadas para evitar fugas de sprints futuros? [Límites de Alcance, Spec §Scope & Boundaries, Plan §Constraints]
- [ ] CHK006 - ¿Se establecen las microtareas de implementación en unidades atómicas estrictamente acotadas a menos de 60 minutos conforme al Principio II de la Constitución? [Medibilidad, Spec §Plan de Microtareas, SC-005]

## 4. Gobernanza y Supervisión Humana (Sp1-03)

- [ ] CHK007 - ¿Está el hito de reunión y aprobación conjunta de contratos (`Sp1-03`) registrado como un punto de control con participación humana obligatoria antes de iniciar implementaciones dependientes? [Gobernanza, Spec §Scope & Boundaries, Plan §Constitution Check]
- [ ] CHK008 - ¿Se especifica que los dobles de prueba entregados en `HU-00-01` son stubs mínimos en memoria y no reemplazan el desarrollo de `FakeProvider` programable asignado a `HU-00-03`? [Consistencia, Spec §Scope & Boundaries, Plan §Trazabilidad]

---

## Notes

- Total de verificaciones: 8 ítems enfocados exclusivamente en la calidad de los requisitos escritos.
- Todas las casillas se inicializan en `[ ]` a la espera de la revisión del equipo.
- Ninguna verificación evalúa ejecución de código ni reemplaza pruebas unitarias de software.
