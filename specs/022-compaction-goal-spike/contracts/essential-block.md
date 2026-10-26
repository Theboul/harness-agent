# Contrato propuesto: bloque fijo de contexto esencial

Borrador que el spike valida y que la decisión SPK-03 formaliza para HU-02-06.1 y HU-02-03. No cambia ningún puerto.

1. **Contenido**: cinco claves — `objetivo`, `instrucciones`, `reglas`, `ticket`, `criterios_ref`. `decisiones` queda para HU-02-06.2.
2. **Posición**: un mensaje `SYSTEM` en el prefijo, antes del resumen y de los eventos recientes. Mismo texto byte a byte entre ensamblados mientras no cambien sus valores.
3. **Exclusión de la compactación**: la entrada de la llamada de resumen contiene solo eventos antiguos y el resumen previo; nunca el bloque.
4. **Criterios**: el bloque lleva la referencia; el ensamblador lee el texto de la fuente protegida en cada ensamblado. Referencia sin fuente → falla cerrada.
5. **Reconstrucción**: el bloque se rearma desde `contexto_esencial` sin el resumen (compatible con reanudar, HU-03-04).
