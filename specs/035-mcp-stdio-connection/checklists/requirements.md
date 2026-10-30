# Lista de calidad de la especificación: HU-08-01

**Propósito**: validar la especificación antes de planificar · **Creada**: 2026-10-30 · **Spec**: [spec.md](../spec.md)

## Contenido

- [x] Enfocada en el valor para la persona operadora (el arnés arranca aunque un servidor falle; claves protegidas)
- [x] Secciones obligatorias completas (historia, escenarios, requisitos, criterios, alcance, supuestos)
- [x] Los FR citan componentes del proyecto (puerto, `core/`, `config`) porque la historia es de integración; los criterios de éxito (SC) son observables sin conocer la implementación

## Completitud

- [x] Sin marcadores [NEEDS CLARIFICATION]: las siete decisiones las tomó el usuario (sección *Clarificaciones*)
- [x] Requisitos comprobables (cada FR tiene una prueba obvia)
- [x] Criterios de éxito medibles
- [x] Casos límite identificados (comando inexistente, salida inmediata, sin respuesta, cancelación, sin servidores, SDK ausente)
- [x] Alcance acotado (HU-08-02/03/04/05 fuera) y dependencias/supuestos anotados
- [x] AC-01 de la ficha (inmutable) cubierto por el escenario 1 y FR-001

## Preparación

- [x] Los criterios de aceptación de la ficha no se han cambiado
- [x] Puertos y eventos protegidos sin tocar (FR-013)

## Notas

- Pendiente de ratificar por el PO: nada nuevo; el servidor de demostración fuera de `tests/` sigue siendo T013 de SPK-04.
