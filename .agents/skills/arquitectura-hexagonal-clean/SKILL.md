---
name: arquitectura-hexagonal-clean
description: "Trigger: implementar historia, puerto, adaptador, Clean Architecture, hexagonal, inyección de dependencias, bootstrap, revisar diseño. Guía cómo implementar y revisar cada historia del harness con puertos y adaptadores."
license: Apache-2.0
metadata:
  author: "harness-team"
  version: "1.1"
---

## Activation Contract

Cargar antes de escribir código de una historia, al diseñar un puerto o adaptador (`/speckit-plan`), en `/speckit-implement` y al revisar un cambio (`/speckit-analyze`, `/speckit-converge`).

## Hard Rules

- Las dependencias solo apuntan hacia el núcleo; `core/` nunca importa de `adapters/`, `cli/`, `config`, `observability/`, `bootstrap` ni de un SDK. Solo biblioteca estándar y `harness_agent.core`.
- Todo lo externo (red, disco, base de datos, terminal, reloj, procesos, entorno) pasa por un puerto de `core/interfaces/`.
- Los puertos son clases abstractas (`ABC`), se nombran por rol en inglés y usan solo tipos y errores del dominio (`core/entities.py`, `core/events.py`), nunca del SDK.
- Los puertos, `core/entities.py` y `core/events.py` son contratos de HU-00-01: cambiarlos exige acuerdo de A, B y C.
- Los adaptadores traducen errores externos a errores de dominio; el núcleo no captura excepciones de SDK.
- Las dependencias se reciben por constructor y se conectan solo en `bootstrap.py` (mientras no exista, en las pruebas de integración).
- El reloj, los identificadores, la configuración y las variables de entorno se inyectan; `core/` no lee `config.toml` ni `os.environ`.
- El núcleo no imprime ni lee de la terminal: emite eventos por `EventBus`.
- Los tipos del dominio son `@dataclass(frozen=True)`; el núcleo no muta lo que recibe (copia antes de pasarlo a un colaborador).
- Falla cerrada: ante lo no previsto se pregunta o se deniega, nunca se permite.
- Un adaptador no contiene reglas de negocio ni importa de otro adaptador (salvo `adapters/converters/`, que es la utilidad compartida de los proveedores).
- Nunca relajar la regla dentro de `core/`; si parece imposible, falta un puerto.

## Decision Gates

| Pregunta | Resultado |
|---|---|
| ¿Es regla o comportamiento nuevo? | Módulo o subpaquete en `core/`, exportado en `core/__init__.py` |
| ¿Necesita algo de fuera? | Usar un puerto existente de `core/interfaces/`; si no hay, proponer uno mínimo (acuerdo A, B y C) |
| ¿Quién lo implementa? | Adaptador en `adapters/` (`litellm`, `sqlite3`, `mcp`, `subprocess`, disco) |
| ¿Cómo se conecta? | Inyección en constructor, en `bootstrap.py` |
| ¿Cómo se prueba? | Núcleo con dobles de `tests/doubles/` (`ScriptedProvider`, `ScriptedPolicy`, `RecordingEventBus`…); adaptador real con prueba de contrato en `tests/contracts/` |
| ¿Es asíncrono? | `Provider.complete`, `Tool.run`, `Approver.request`, `McpClient.*` y `SubagentRunner.execute` son `async` (D-01); los demás puertos son síncronos |

Capas, antipatrones y reglas del harness: `references/capas-y-reglas.md`.

## Execution Steps

1. Recorrer el flujo de Decision Gates para la historia.
2. Si hace falta un puerto, escribirlo con tipos del dominio y documentar los errores de dominio que puede lanzar (`assets/port_provider.py` muestra el formato real).
3. Implementar el adaptador traduciendo formatos y errores (`assets/adapter_litellm.py`).
4. Conectar en `bootstrap.py` (`assets/bootstrap.py`) o, si aún no existe, en la prueba de integración.
5. Probar el núcleo con dobles y el adaptador con prueba de contrato, sin red ni claves.
6. Revisar contra la lista de `references/capas-y-reglas.md` y ejecutar la skill `verificar-fronteras-hexagonales`.

## Output Contract

Devolver:
- Puerto, adaptador y punto de conexión creados o modificados (rutas).
- Respuesta sí/no a cada punto de la lista de comprobación; justificar cada «no».
- Resultado de `pytest tests/architecture` (y de la guarda nueva, si la historia crea un módulo).

## References

- `references/capas-y-reglas.md` — capas, antipatrones, reglas específicas y lista de comprobación.
- `assets/port_provider.py`, `assets/adapter_litellm.py`, `assets/bootstrap.py` — ejemplos con los contratos reales.
- `../estructura-carpetas-harness/SKILL.md` — dónde va cada archivo.
- `../verificar-fronteras-hexagonales/SKILL.md` — verificación automática.
- `docs/02-arquitectura.md` §4 — contratos entre módulos.
