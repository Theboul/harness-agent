# Especificación: SPK-03 — Spike: compactación sin perder el objetivo

**Rama**: `feat/spk-03-compaction-goal-spike` · **Responsable**: B — Estado · **Sprint**: 2 · **PHU**: 1  
**Requisitos**: RF-2.3, RF-2.4, RF-2.7 · **Depende de**: [HU-01-01](../../docs/04a-historias-fundacion.md#hu-01-01) · **Ficha**: [SPK-03](../../docs/04b-historias-estado.md#spk-03)  
**Tareas del plan**: Sp2-34, Sp2-35, Sp2-36  
**Numeración**: `022` (la `021` está reservada por la rama de HU-11-01 aún sin integrar)

## Clarificaciones

### Sesión 2026-10-25

- Q: ¿Cómo se hace el spike sin claves ni presupuesto de API (D-IA abierta)? → A: sin red, con `FakeProvider` y dobles; el resumen lo produce un resumidor simulado y determinista. La corrida con un modelo real queda como tarea humana pendiente y el spike **no** se declara cerrado sin ella (AC-01 parcial, como SPK-01).

## Historia

Como equipo de desarrollo queremos probar con una sesión larga simulada que un resumen del historial antiguo conserva el objetivo, las instrucciones, las reglas de la tarea, el identificador del ticket y los criterios, y decidir qué debe vivir fuera de lo resumible, para estimar y diseñar con seguridad la compactación (HU-02-03) y el contexto esencial persistente (HU-02-06.1), y la reanudación de sesiones (HU-03-04).

## Escenarios

1. **Sesión larga simulada.** Dado un guion reproducible de una sesión de varias decenas de mensajes, con el objetivo y las reglas dichos al principio, decisiones intermedias y salidas de herramientas, cuando se prepara, entonces el historial contiene datos esenciales sembrados (objetivo, instrucciones, reglas, ticket, criterios) que se pueden buscar.
2. **Doble compactación.** Dado ese historial, cuando se compacta dos veces (la segunda resume también el resumen anterior), entonces se evalúa qué elementos esenciales y qué decisiones sobreviven en cada paso.
3. **Resumen solo frente a bloque fijo.** Dado el mismo historial, cuando se compara el diseño «todo dentro del resumen» con el diseño «bloque fijo de contexto esencial fuera de lo resumible», entonces queda medida la pérdida de cada uno tras dos compactaciones.
4. **Diseño anotado.** El diseño del bloque fijo queda escrito en `docs/decisiones/` de forma que HU-02-03 y HU-02-06.1 lo usen sin reinterpretarlo.

## Requisitos funcionales

- **FR-001**: El spike MUST usar una sesión larga simulada, determinista y reproducible, con los elementos esenciales sembrados en posiciones conocidas (incluido un ticket con identificador y criterios por referencia).
- **FR-002**: Las pruebas MUST compactar dos veces (la segunda sobre el resumen de la primera más eventos nuevos) y MUST evaluar la supervivencia de cada elemento esencial y de las decisiones en cada paso.
- **FR-003**: Las pruebas MUST demostrar que un resumidor con pérdida deja caer elementos del historial resumido y que el diseño con bloque fijo los conserva idénticos, sin depender de que el resumen los contenga.
- **FR-004**: Ninguna prueba MUST abrir red, usar claves ni un proveedor real; el modelo se sustituye por `FakeProvider` y dobles.
- **FR-005**: La decisión escrita MUST separar lo comprobado de lo no comprobado y declarar que el resumen simulado **no** prueba el comportamiento de un modelo real.
- **FR-006**: La decisión MUST definir el bloque fijo: qué claves contiene, de dónde sale cada una, cómo se inyecta en el prefijo, qué no puede reescribir la compactación y qué debe leer de su fuente protegida (criterios por referencia).
- **FR-007**: Si el spike concluye que hace falta cambiar un puerto de `core/interfaces/` o el catálogo de `core/events.py`, MUST quedar como hallazgo en la decisión, sin tocarlos.
- **FR-008**: El código MUST vivir en `tests/spikes/` y MUST NOT añadirse nada a `src/`; no se implementan HU-02-01, HU-02-03 ni HU-02-06.1.
- **FR-009**: Los cuatro comandos de calidad y `pytest tests/architecture` MUST pasar; `docs/PROGRESO.md` MUST reflejar la historia (`En curso`, nunca `Hecha`).

## Criterios de éxito

- **SC-001**: Tras dos compactaciones, el 100 % de los elementos esenciales siguen idénticos en el contexto ensamblado con bloque fijo, y la prueba equivalente con el resumidor con pérdida muestra al menos un elemento perdido.
- **SC-002**: El documento de decisión separa lo comprobado de lo no comprobado y deja explícita la corrida con modelo real como pendiente.

## Fuera de alcance

Llamadas reales a un modelo, estimación real de tokens (HU-02-01), el `ContextManager` real, tabla `contexto_esencial` real en SQLite, decisiones acumuladas (HU-02-06.2), memoria estructurada (HU-04-03) y cualquier cambio de puertos o eventos.

## Supuestos

- Un resumidor simulado con pérdida modela el riesgo de forma conservadora, pero no es evidencia del comportamiento de un modelo real.
- Los criterios protegidos de HU-11-01 se leen desde su fuente por referencia; aquí se representan con un doble de solo lectura.
- La corrida real depende de D-IA (proveedores y presupuesto), aún abierta.
