# Implementation Plan: HU-05-01 — Política denegar, preguntar, permitir que falla cerrada

**Branch**: `007-permission-policy` (directorio de la spec; el trabajo se hace en la rama `gustavo`) | **Date**: 2026-10-21 | **Spec**: [specs/007-permission-policy/spec.md](spec.md)

**Input**: Feature specification from `/specs/007-permission-policy/spec.md` (clarificada el 2026-10-21: Q1 opción B, Q2 opción A, Q3 opción A).

**Directrices del usuario**: el puerto `PermissionPolicy` y `core/loop.py` no se modifican; `core/permissions/` solo con biblioteca estándar; `config.py` se amplía solo con la sección `[permissions]` (`deny` y `ask`, vacías por defecto, sin poder crear reglas de permitir); tipado estricto y cobertura del 100 % en los módulos nuevos; sin investigación externa ni diseño de más: es una política pura y pequeña.

---

## Summary

Añadir el paquete `src/harness_agent/core/permissions/` con dos módulos: `rules.py` (`PermissionRules`, las listas `deny` y `ask` inmutables y validadas) y `policy.py` (`DefaultPermissionPolicy`, que implementa el puerto existente). La política es una función pura de la llamada: valida su forma, aplica las listas (denegar y luego preguntar), consulta el riesgo de la herramienta en el registro y, solo para herramientas de riesgo medio (escritura) o de riesgo bajo con `path` (lectura), pregunta al componente de área si la ruta real queda dentro; ahí está el **único** punto donde se devuelve «permitir». Todo lo demás pregunta o deniega, y cualquier excepción se convierte en «denegar». `config.py` añade la tabla `[permissions]` con las listas y las entrega como `PermissionRules` dentro de `HarnessConfig`. No se toca el puerto, el bucle, el bus, la CLI ni los dobles; la resolución provisional de «preguntar» sigue siendo del bucle y se verifica con la política real.

---

## Technical Context

**Language/Version**: Python 3.12, única versión soportada (PD-07).

**Primary Dependencies**: solo biblioteca estándar en `core/permissions/` (`dataclasses`, `typing`) y los puertos de `harness_agent.core`. `config.py` importa `PermissionRules` del núcleo (la dirección `config.py → core` está permitida; el núcleo no importa `config.py`). Sin dependencias nuevas.

**Storage**: N/A. La política no guarda estado entre llamadas: sus únicos datos son los colaboradores y las reglas inyectados.

**Testing**: `pytest` con `RecordingTool`-like de riesgo configurable, `InMemoryToolRegistry`, `DummyAuthorizedArea` (con `tmp_path`), `ScriptedProvider` y el bucle real (`make_rig`); sin red ni entorno real.

**Target Platform**: Windows y Linux (matriz de CI).

**Project Type**: Biblioteca modular; la política concreta es del núcleo (área de permisos de C).

**Performance Goals**: evaluar una llamada en menos de 1 ms de media (SC-009): una búsqueda en conjunto, una consulta al registro y, como mucho, una llamada al componente de área.

**Constraints**:
1. `core/interfaces/*`, `core/events.py`, `core/loop.py`, el bus, la CLI y `tests/doubles/*` quedan sin modificar; `docs/archivo/` también.
2. `core/permissions/` solo importa biblioteca estándar y `harness_agent.core`; no lee archivos ni entorno ni importa `config.py`.
3. `mypy --strict` sobre `src` y `tests`; `ruff` con línea de 100 columnas; cobertura del 100 % en `rules.py`, `policy.py` y el código nuevo de `config.py`.
4. Todo camino del código que devuelve «permitir» pasa por `AuthorizedArea.contains` con la ruta de `path` (D3); no existe ningún «permitir» sin esa condición; ninguna regla se puede crear desde la configuración.
5. `evaluate` nunca lanza una `Exception` ni devuelve algo distinto de las tres decisiones.

**Scale/Scope**: 2 módulos nuevos más `__init__.py`, una ampliación pequeña de `config.py` (tabla, validador y campo), una línea de exportación en `core/__init__.py`, 1 sección comentada en `config.example.toml`, 3 contratos y 6 módulos de prueba nuevos.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / Restricción | Requisito | Pre-diseño | Post-diseño | Evidencia |
|---|---|---|---|---|
| I. Una historia por especificación | Solo HU-05-01 | Pasa | Pasa | Spec y plan solo de HU-05-01 |
| II. Microtareas de 15 a 40 min | Entre 8 y 10 tareas, ninguna pasa de 40 min | Pasa | Pasa | Se fijan en `tasks.md` (inicio, módulos, cierre y humanas aparte) |
| III. Núcleo modular, tipado, sin dependencias externas | `core/` solo con biblioteca estándar; módulos pequeños | Pasa | Pasa | D1; prueba de fronteras (T-arquitectura) |
| IV. Pruebas, calidad y CI multiplataforma | Pruebas primero; ruff, mypy, pytest en Windows y Linux | Pasa | Pasa | Cada tarea escribe las pruebas antes del código |
| V. Inmutabilidad de criterios | AC-01 a AC-05 y reglas copiados tal cual | Pasa | Pasa | Spec; verificado contra `docs/04c-historias-control.md` |
| VI. Disciplina de sprints | Nada de sprints futuros | Pasa | Pasa | Sin lista de comandos peligrosos, aprobación, permiso de sesión ni herramientas de archivos |
| VII. Consulta documental quirúrgica | Solo las fuentes necesarias | Pasa | Pasa | HU-05-01, puertos de seguridad y de herramienta, bucle (`_decide`), `config.py` |
| VIII. Registro en `docs/PROGRESO.md` | `En curso` y `En revisión` con registro | Pasa | Pasa | Tareas de inicio y de cierre; observación del supuesto de lectura |
| IX. Definition of Done estricta | Revisión cruzada por A o B y CI | Pasa | Pasa | Tareas humanas; HU-00-01 sigue pendiente de aprobación técnica |
| X. Inmutabilidad de `docs/archivo/` | No se toca | Pasa | Pasa | `git diff` en el cierre |
| Hexagonal (skill `arquitectura-hexagonal-clean`) | La política depende de puertos (registro, área); se conecta por inyección | Pasa | Pasa | D1; la raíz de composición la crea (fuera de esta historia) |
| Estructura de carpetas (skill `estructura-carpetas-harness`) | «Regla de negocio (permisos…)» → `core/` | Pasa | Pasa | `core/permissions/` según el árbol acordado |
| Puertos acordados (A, B y C) | Cambiar un puerto exige acuerdo | Pasa | Pasa | D7: ningún puerto cambia (Q2 y Q3 se resolvieron sin tocarlos) |

**Resultado**: sin violaciones; no hace falta tabla de complejidad.

---

## Project Structure

### Documentation (this feature)

```text
specs/007-permission-policy/
├── spec.md
├── plan.md                                # este archivo
├── research.md                            # decisiones R-01 a R-08
├── data-model.md                          # PermissionRules, política y tabla de decisión
├── quickstart.md                          # cómo verificar la historia
├── contracts/
│   ├── path_argument_convention.md        # convención `path` (ya existe; la cumple HU-01-03)
│   ├── policy_contract.md                 # API, orden de evaluación y cláusulas P-1 a P-16
│   └── permissions_config_contract.md     # sección [permissions] y sus mensajes
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/harness_agent/
├── core/
│   ├── permissions/
│   │   ├── __init__.py                    # NUEVO: API pública del paquete
│   │   ├── rules.py                       # NUEVO: PermissionRules (deny, ask)
│   │   └── policy.py                      # NUEVO: DefaultPermissionPolicy
│   └── __init__.py                        # M: exporta DefaultPermissionPolicy y PermissionRules
└── config.py                              # M: tabla [permissions], validador y campo permissions
config.example.toml                        # M: sección [permissions] comentada

tests/
├── unit/core/permissions/__init__.py                        # NUEVO
├── unit/core/permissions/test_rules.py                      # NUEVO
├── unit/core/permissions/test_policy.py                     # NUEVO
├── unit/test_config_permissions.py                          # NUEVO
├── contracts/test_permission_policy_contract.py             # NUEVO
├── integration/test_permission_policy_agent_loop.py         # NUEVO
└── architecture/test_permissions_boundaries.py              # NUEVO
docs/PROGRESO.md                                             # M: En curso / En revisión y registro
```

**Structure Decision**: un paquete pequeño con dos módulos, uno por responsabilidad (datos de las reglas y decisión), sin subpaquetes. La política no conoce `config.py`; `config.py` conoce `PermissionRules`. No se tocan `core/interfaces/`, `core/events.py`, `core/loop.py`, `core/in_memory_event_bus.py`, `cli/` ni `tests/doubles/`.

---

## Decisiones de diseño y desviaciones

- **D1 — Dónde vive y cómo se conecta**: `core/permissions/` (C), con inyección por constructor de `ToolRegistry` (para consultar el riesgo por nombre), `AuthorizedArea | None` (el área, o `None` si no hay área configurada) y `PermissionRules`. Quien la crea y la pasa al bucle es la raíz de composición, fuera de esta historia.
- **D2 — Un tipo de reglas, no dos**: `PermissionRules` se define en el núcleo y `config.py` lo importa para entregarlo en `HarnessConfig.permissions` (campo nuevo, el último, con valor por defecto vacío: ninguna construcción existente de `HarnessConfig` cambia). Así no hay que traducir entre un tipo de configuración y uno del núcleo.
- **D3 — Todo «permitir» pasa por el área**: hay dos reglas de permitir (escritura con riesgo medio y lectura con riesgo bajo, esta última supuesto pendiente del PO) y ambas comparten la función privada `_inside_area`, que devuelve `PermissionDecision.ALLOW` solo cuando `area.contains(path)` es exactamente `True`; no existe ningún otro camino que devuelva «permitir». SC-008 se comprueba con una prueba de `ast` (toda aparición de `ALLOW` está en la rama protegida por esa condición y no hay ninguna fuera) y con una matriz exhaustiva que usa un comprobador espía y exige que `contains` reciba el valor de `path` sin modificar.
- **D4 — `evaluate` nunca lanza**: un `try` externo convierte cualquier `Exception` (registro, riesgo, comprobador del área) en «denegar». Las `BaseException` no se tocan.
- **D5 — Orden de evaluación**: (0) forma de la llamada (nombre, argumentos): mal formada → denegar; (1) lista `deny` → denegar; (2) lista `ask` → preguntar; (3) riesgo por el registro: no registrada, sin riesgo o riesgo desconocido → preguntar; (4) riesgo alto → preguntar; (5) riesgo medio o riesgo bajo con `path` → regla del área (`_inside_area`); (6) riesgo bajo sin `path` → preguntar. La validez del `path` se comprueba dentro de la regla del área, es decir, **después** de las listas: una herramienta de la lista `ask` con un `path` inválido se pregunta, no se deniega (restrictivo en ambos casos y el bucle la resuelve como denegada).
- **D6 — Regla de lectura apagable (supuesto del PO)**: `DefaultPermissionPolicy(..., allow_reads_in_area=True)`; con `False`, las lecturas de riesgo bajo con `path` se preguntan (literal de la historia). Es el modo concreto de «poder quitarse sin tocar el resto»; no es configurable desde `config.toml` (la configuración no puede crear ni quitar reglas de permitir).
- **D7 — Ningún puerto cambia**: Q2 (convención `path`) y Q3 (motivo genérico del bucle) se resolvieron sin tocar el puerto de herramienta ni el de política ni `core/loop.py`. Hallazgo para A y HU-05-03: el texto del bucle no distingue la causa.
- **D8 — Plantilla**: `config.example.toml` añade `[permissions]` **comentada** (con `deny = []` y `ask = []` y su explicación): la prueba de plantillas existente exige que el TOML crudo declare solo `model`, `limits` y `paths`, y una sección activa la rompería.
- **D9 — Contrato de configuración**: la ampliación del esquema se documenta en `contracts/permissions_config_contract.md`; no se editan los documentos de la historia HU-00-04 (ya fusionada). La observación para `docs/PROGRESO.md` se anota en la tarea de cierre.
- **D10 — Aviso de capacidad, ratificación y revisión**: el plan de sprint asigna 11 h (660 min) a Sp1-32 a Sp1-36; `tasks.md` compara la estimación con ese presupuesto como aviso, sin recortar alcance. HU-00-01 sigue `Pendiente de aprobación técnica` (Sp1-03) y debe ratificarse antes de pasar HU-05-01 a `Hecha`. La revisión cruzada por A o B es una tarea humana. La regla de lectura es un supuesto pendiente de confirmación del PO y la tarea de cierre lo anota en `docs/PROGRESO.md`.

---

## Riesgos y cómo se comprueban

| Riesgo | Mitigación |
|---|---|
| Un camino devuelve «permitir» sin pasar por el área | D3: todo «permitir» pasa por `AuthorizedArea.contains`; prueba exhaustiva de la matriz con un comprobador espía y prueba de `ast` (SC-002, SC-003, SC-008) |
| Una excepción del registro o del área llega al bucle | D4; pruebas con registro y área que fallan (SC-004) |
| Un `path` engañoso (`..`, enlace simbólico, otra unidad) se acepta | La contención la decide `AuthorizedArea`, no la política (FR-009); se prueba con el doble sobre `tmp_path` y se deja la prueba de escape real a HU-01-03 |
| El contenido de un archivo cambia la decisión | La política solo recibe la llamada y no guarda estado (FR-015); prueba de idempotencia antes y después de una «lectura» (SC-005) |
| La ampliación de `config.py` rompe pruebas existentes | Campo nuevo con valor por defecto; plantilla comentada (D8); se ejecuta toda la suite de configuración |
| La política desordena el bucle | Sin cambios en el bucle; pruebas existentes del bucle sin tocar; prueba de integración con la política real (SC-006) |
| La convención `path` no la cumple HU-01-03 | Contrato `path_argument_convention.md`; HU-01-03 lo lista como requisito |
