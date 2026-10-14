## Equipo 👥

- **Integrante 1:** CORRALES FERREL BRAD ALEXANDER
- **Integrante 2:** SANDOVAL SANCHEZ GUSTAVO ANTONIO
- **Integrante 3:** SANTOS CASTRO ROBERTO ANJEL

## Materia 🎓

- **Materia:** TOPIC.AVANZ.DE PROGRAMAC.(ALGORIT.GENE.)
- **Grupo:** SA

## Resumen 📋

**harness-agent** es un harness de agente en terminal: la aplicación que rodea a un modelo de lenguaje y lo conecta con el mundo mediante un bucle razonar–actuar–observar, herramientas, permisos, contexto, memoria y sesiones. El núcleo es reutilizable y está desacoplado de la interfaz.

> **Estado:** en inicialización. Aún no hay código en `src/`; este README describe el diseño acordado. El contexto completo está en [`docs/00-indice.md`](docs/00-indice.md).

## Decisiones principales

| Tema | Decisión |
|---|---|
| Enfoque | Coding Harness basado en tickets: ticket → agente → cambios → pruebas → verificación → aprobación → Pull Request |
| Lenguaje | Python 3.12+ |
| Interfaz | Terminal (CLI). El núcleo emite eventos por un bus y nunca imprime |
| Proveedores | LiteLLM detrás de una interfaz propia `Provider`; al menos dos con conmutación por fallo |
| Persistencia | SQLite (sesiones, eventos, memoria, auditoría, trazas) |
| Herramientas externas | Cliente MCP por stdio |
| Reto | Subagentes con contexto aislado |
| Sistemas operativos | Windows y Linux; integración continua en ambos |

## Capacidades obligatorias

- Bucle del agente con herramientas.
- Contexto con compactación que conserva el historial original.
- Sesiones reanudables.
- Memoria persistente separada del historial.
- Permisos con aprobación humana; la política falla cerrada.
- CLI con eventos en tiempo real.
- Dos proveedores con conmutación por fallo.
- Cliente MCP.
- Subagentes.
- Trazas y auditoría con redacción de secretos.
- Flujo de tarea con criterios de aceptación, herramientas Git, pruebas y lint, verificación de criterios, aprobación del diff y Pull Request (E11).

## Arquitectura

Hexagonal con Clean Architecture: las dependencias apuntan hacia el núcleo.

```
cli ──┐
      ├──▶ core ◀── adapters
bootstrap ──▶ (ambos)
```

| Carpeta | Responsabilidad |
|---|---|
| `src/harness_agent/core/` | Reglas y puertos. Sin imports externos |
| `src/harness_agent/adapters/` | Implementaciones: proveedores, almacenamiento, MCP, herramientas nativas |
| `src/harness_agent/observability/` | Trazas, auditoría, redacción de secretos |
| `src/harness_agent/cli/` | Terminal; se suscribe al bus de eventos |
| `src/harness_agent/bootstrap.py` | Raíz de composición: único lugar que une núcleo y adaptadores |
| `tests/` | `unit`, `integration`, `failures`, `contract`, `architecture` |

La frontera se verifica con `import-linter` y un test con `ast`; ambos corren en la integración continua.

## Skills del proyecto

Guías para el agente de código, en `.claude/skills/`:

| Skill | Cuándo se usa |
|---|---|
| `arquitectura-hexagonal-clean` | Implementar o revisar una historia con puertos y adaptadores |
| `estructura-carpetas-harness` | Decidir dónde va cada archivo nuevo |
| `verificar-fronteras-hexagonales` | Comprobar que `core/` no dependa de nada externo |

## Equipo y plan

- **Equipo:** A = Núcleo, B = Estado, C = Control y conexiones. Product Owner: Brad.
- **Plazo:** 3 sprints de 1 semana.
- **Definition of Done:** integrado con CI en verde, con pruebas, tipos y formato correctos, sin secretos, revisado por otra persona y mostrado en la demostración.

| Sprint | Hito |
|---|---|
| 1 | Tarea de tres pasos de principio a fin con modelo real; sesión guardada; política de permisos |
| 2 | Aprobación y rechazo, reanudación de sesión, compactación y subagente básico |
| 3 | Una tarea con criterios llega a Pull Request tras aprobar el diff; además MCP bajo permisos, conmutación de proveedor y memoria entre sesiones |

## Instalación y uso

Pendiente hasta cerrar HU-00-01 (esqueleto del repositorio) y HU-00-04 (configuración). Se documentará aquí junto con `.env.example` y `config.example.toml`.

## Documentación

- [`docs/00-indice.md`](docs/00-indice.md): índice de la documentación (visión, arquitectura, plan, historias y trazabilidad).
- [`docs/PROGRESO.md`](docs/PROGRESO.md): qué se hizo y dónde está.
