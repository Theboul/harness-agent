---
name: arquitectura-hexagonal-clean
description: "Trigger: implementar historia, puerto, adaptador, Clean Architecture, hexagonal, inyección de dependencias, bootstrap, revisar diseño. Guía cómo implementar y revisar cada historia del harness con puertos y adaptadores."
license: Apache-2.0
metadata:
  author: "harness-team"
  version: "1.0"
---

## Activation Contract

Cargar antes de escribir código de una historia, al diseñar un puerto o adaptador, y al revisar un cambio.

## Hard Rules

- Las dependencias solo apuntan hacia el núcleo; `core/` nunca importa de `adapters/`, `cli/`, `observability/` ni de un SDK.
- Todo lo externo (red, disco, base de datos, terminal, reloj, procesos) pasa por un puerto en `core/ports.py`.
- Los puertos se nombran por rol y usan solo tipos y errores del dominio, nunca del SDK.
- Los adaptadores traducen errores externos a errores de dominio; el núcleo no captura excepciones de SDK.
- Las dependencias se reciben por constructor y se conectan solo en `bootstrap.py`.
- El reloj, los identificadores y las variables de entorno se inyectan.
- El núcleo no imprime ni lee de la terminal: emite eventos.
- Un adaptador no contiene reglas de negocio ni importa de otro adaptador.
- Nunca relajar la regla dentro de `core/`; si parece imposible, falta un puerto.

## Decision Gates

| Pregunta | Resultado |
|---|---|
| ¿Es regla o comportamiento nuevo? | Caso de uso o entidad en `core/` |
| ¿Necesita algo de fuera? | Definir puerto mínimo en `core/ports.py` |
| ¿Quién lo implementa? | Adaptador en `adapters/` (`litellm`, `sqlite3`, `mcp`, `subprocess`) |
| ¿Cómo se conecta? | Inyección en constructor, en `bootstrap.py` |
| ¿Cómo se prueba? | Núcleo con adaptador falso; adaptador real con prueba de contrato |
| ¿El núcleo es asíncrono? | Los puertos exponen `async` desde el diseño (spike de asyncio) |

Capas, antipatrones y reglas del harness: `references/capas-y-reglas.md`.

## Execution Steps

1. Recorrer el flujo de Decision Gates para la historia.
2. Escribir el puerto con tipos del dominio y documentar los errores de dominio que puede lanzar (`assets/port_provider.py`).
3. Implementar el adaptador traduciendo formatos y errores (`assets/adapter_litellm.py`).
4. Conectar en `bootstrap.py` (`assets/bootstrap.py`).
5. Probar el núcleo con un doble (`FakeProvider`, almacén en memoria) y el adaptador con prueba de contrato.
6. Revisar contra la lista de `references/capas-y-reglas.md` y ejecutar la skill `verificar-fronteras-hexagonales`.

## Output Contract

Devolver:
- Puerto, adaptador y punto de conexión creados o modificados (rutas).
- Respuesta sí/no a cada punto de la lista de comprobación; justificar cada «no».
- Resultado de `lint-imports` y del test de fronteras.

## References

- `references/capas-y-reglas.md` — capas, antipatrones, reglas específicas y lista de comprobación.
- `assets/port_provider.py`, `assets/adapter_litellm.py`, `assets/bootstrap.py` — ejemplos mínimos.
- `../estructura-carpetas-harness/SKILL.md` — dónde va cada archivo.
- `../verificar-fronteras-hexagonales/SKILL.md` — verificación automática.
