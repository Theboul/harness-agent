# Especificación: SPK-01 — Spike: traducir herramientas entre OpenAI y Anthropic con LiteLLM

**Rama**: `feat/spk-01-litellm-tool-spike` · **Responsable**: B — Estado · **Sprint**: 1 · **PHU**: 1  
**Requisitos**: RF-7.1, RF-7.3 · **Depende de**: ninguna · **Ficha**: [SPK-01](../../docs/04d-historias-conexiones.md#spk-01)  
**Numeración**: `016` (014 y 015 están reservadas por las ramas de HU-03-01 y HU-03-02 aún sin integrar)

## Clarificaciones

### Sesión 2026-10-24

- Q: ¿Cómo se hace el spike sin claves de API disponibles? → A: sin red; `litellm` real, transporte sustituido, respuestas nativas simuladas. AC-01 queda **parcial** y SPK-01 en `En curso` hasta una corrida real (decisión del usuario).

## Historia

Como equipo de desarrollo queremos probar una misma herramienta en OpenAI y en Anthropic con LiteLLM y documentar qué difiere, para diseñar el formato interno (HU-07-01) y el adaptador (HU-07-02) sabiendo qué esperar.

## Escenarios

1. **Misma herramienta, dos proveedores.** Dado un esquema de herramienta, cuando LiteLLM lo envía a cada proveedor, entonces la petición de cada uno usa su formato nativo y se obtienen llamadas equivalentes (nombre y argumentos).
2. **Ida y vuelta de un resultado.** Dado un resultado de herramienta (también uno con error) y llamadas paralelas, cuando se devuelven al modelo, entonces se documenta cómo viaja cada uno.
3. **Diferencias documentadas.** Las diferencias de identificadores y de resultados quedan escritas con su consecuencia para el formato interno.

## Requisitos funcionales

- **FR-001**: Las pruebas MUST usar `litellm` real y capturar la petición que construye para cada proveedor.
- **FR-002**: Ninguna prueba MUST abrir conexiones de red; un guardia MUST hacerlas fallar.
- **FR-003**: Las pruebas MUST omitirse si `litellm` no está instalado, y MUST NOT añadirse `litellm` a `requirements-dev.txt`, `pyproject.toml` ni la CI (cambio de dependencias que exige acuerdo de A, B y C).
- **FR-004**: Se MUST documentar en `docs/decisiones/` cada diferencia observada, con la consecuencia para el formato interno, y declarar lo que **no** se comprobó.
- **FR-005**: MUST NOT haber claves en el repositorio ni en las pruebas (solo valores falsos obvios).
- **FR-006**: No se modifica código de `src/`, puertos, `core/events.py`, `tests/doubles/` ni `docs/archivo/`.
- **FR-007**: Los cuatro comandos de calidad y `pytest tests/architecture` MUST pasar; `docs/PROGRESO.md` MUST reflejar la historia (`En curso`, nunca `Hecha`).

## Criterios de éxito

- **SC-001**: Las 11 pruebas del spike pasan con `litellm` instalado y se omiten sin él.
- **SC-002**: El documento de hallazgos separa lo comprobado de lo no comprobado y deja explícito el pendiente de la corrida real.

## Fuera de alcance

Llamadas reales, *streaming*, `tool_choice`, Gemini, el adaptador de HU-07-02 y cambios a los convertidores de HU-07-01.

## Supuestos

- Las respuestas nativas simuladas siguen el formato documentado de cada API; no son capturas.
- La corrida real depende de D-IA (proveedores y presupuesto), aún abierta.
