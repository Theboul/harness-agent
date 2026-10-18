# Specification Quality Checklist: HU-07-01 — Interfaz Provider y formato interno de mensajes

**Purpose**: Validar la completitud, claridad, consistencia y verificabilidad de los requisitos de la especificación técnica (`spec.md`) y el plan de implementación (`plan.md`) para la historia HU-07-01 antes de la generación de tareas y codificación.  
**Created**: 2026-10-18  
**Feature**: [`specs/004-provider-interface-message-format/spec.md`](../spec.md) | [`specs/004-provider-interface-message-format/plan.md`](../plan.md)  

**Review Ownership**: Este artefacto pertenece al revisor técnico y al equipo de desarrollo (A, B y C). Cada ítem representa un "unit test" sobre la redacción y cobertura de los requisitos.  
**Marker Semantics**: Un marcador `[x]` indica exclusivamente que el revisor ha comprobado que el criterio de calidad de requisitos está satisfecho documentalmente. No significa que el código haya sido implementado ni que las pruebas de software hayan sido ejecutadas.  

---

## 1. Criterios de Aceptación Centrales e Intercambiabilidad (AC-01 y AC-02)

- [ ] CHK001 ¿Está definido AC-01 (conversión bidireccional sin pérdida) con criterios unívocos de igualdad campo por campo para roles, texto, llamadas, resultados, métricas y seguridad? [Clarity, Spec §User Story 1, §AC-01]
- [ ] CHK002 ¿Especifica el plan un arnés/consumidor de prueba desacoplado que permita demostrar AC-02 (sustitución polimórfica de `Provider` con 0 líneas de código modificadas) sin implementar prematuramente el bucle agéntico de producción de HU-01-01? [Coverage, Plan §Estrategia de Pruebas, Spec §AC-02]

## 2. Representación Canónica y Correlación de Herramientas

- [ ] CHK003 ¿Están definidos con precisión matemática y sin ambigüedades los cuatro roles canónicos (`system`, `user`, `assistant`, `tool`) y sus reglas de mapeo para los dialectos de OpenAI y Anthropic? [Completeness, Spec §FR-001, Contracts §2-3]
- [ ] CHK004 ¿Se exige la preservación estricta e inmutable del identificador único `ToolCall.id` a través de los procesos de serialización y deserialización? [Clarity, Spec §FR-003, Data-Model §1.2]
- [ ] CHK005 ¿Está formalmente establecida la correlación unívoca entre `ToolCall.id` y `ToolResult.call_id`, cubriendo tanto llamadas individuales como múltiples llamadas paralelas en un mismo turno? [Consistency, Spec §FR-004, Edge Cases, Data-Model §1.3]
- [ ] CHK006 ¿Se especifican requisitos claros para la validación de argumentos estructurados (`dict[str, Any]`), contemplando el parseo seguro de cadenas JSON y el manejo de esquemas vacíos? [Clarity, Edge Cases, Research §3.2]
- [ ] CHK007 ¿Está documentada la representación explícita de errores de ejecución de herramientas (`is_error=True`) para garantizar que el modelo reciba la indicación de fallo sin provocar caídas del arnés? [Coverage, Spec §FR-004, Data-Model §1.3]

## 3. Métricas de Consumo y Frontera de Seguridad

- [ ] CHK008 ¿Están completamente especificadas las reglas de mapeo de métricas de tokens en `TokenUsage` (`input_tokens`, `output_tokens`, `total_tokens`), traduciendo unívocamente `prompt_tokens`/`completion_tokens`? [Completeness, Spec §FR-005, Data-Model §1.4]
- [ ] CHK009 ¿Se distingue explícitamente el metadato de seguridad local `is_external` (destinado a mitigar inyecciones de prompt) respecto de los datos que viajan en el protocolo de red, evitando rechazos de la API por campos no reconocidos? [Security, Clarity, Research §3.1, Spec §User Story 3]

## 4. Manejo de Errores, Falla Cerrada y Capacidades No Representables

- [ ] CHK010 ¿Se prescribe una política estricta de falla cerrada (*fail-closed* via `ValueError` o excepción de dominio), prohibiendo descartes, truncamientos o mutaciones silenciosas cuando un esquema o dato no pueda ser representado por el proveedor de destino? [Coverage, Exception Flow, Spec §FR-011, Research §4]
- [ ] CHK011 ¿Se definen los casos límite de mensajes sin contenido textual pero con llamadas a herramientas y respuestas con bloques de uso omitidos o nulos? [Edge Cases, Spec §Edge Cases]

## 5. Arquitectura Hexagonal, Gobernanza y Dependencias

- [ ] CHK012 ¿Garantiza el plan que `src/harness_agent/core/` no contiene ninguna importación de SDKs externos (`openai`, `anthropic`, `litellm`) ni de los adaptadores de conversión, ubicando la lógica de conversión en `adapters/converters/`? [Consistency, Constitution III, RNF-12, Plan §Project Structure]
- [ ] CHK013 ¿Exige la especificación la reutilización directa y sin mutaciones de las entidades acordadas en HU-00-01 (`Role`, `Message`, `ToolCall`, `ToolResult`, `TokenUsage`, `ToolDefinition`, `ProviderResponse`, `Provider`), prohibiendo versiones paralelas redundantes? [Consistency, Spec §Clarificaciones, Data-Model §1]
- [ ] CHK014 ¿Se documenta con honestidad técnica que SPK-01 permanece en estado `Pendiente` (a cargo del Desarrollador B), estableciendo el contrato canónico abstracto sin simular resultados empíricos inexistentes de LiteLLM? [Traceability, Research §1.1, Plan §Summary]
- [ ] CHK015 ¿Se encuentra la firma de `Provider.complete` estrictamente definida como corrutina asíncrona (`async def`), en total conformidad con la decisión D-01 de SPK-02 (propuesta, pendiente de aprobación)? [Traceability, Spec §FR-007, D-01]
- [ ] CHK016 ¿Están todos los requisitos, tipados y restricciones de entorno limitados exclusivamente a Python 3.12.x conforme a la decisión PD-07 y el Principio III de la Constitución? [Clarity, Constitution III, Spec §Technical Context]

---

## Notes

- Esta checklist constituye la puerta de calidad documental previa a `/speckit-tasks`.
- Los ítems permanecen desmarcados (`[ ]`) hasta que el revisor o desarrollador evalúe que los artefactos satisfacen cada condición sin ambigüedades.
- `/speckit-implement` utilizará esta checklist como referencia de control de calidad.
- No se han detectado contradicciones técnicas ni escenarios imposibles de verificar entre `spec.md`, `plan.md`, `research.md` y los contratos vigentes.
