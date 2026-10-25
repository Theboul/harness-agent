# Implementation Plan: HU-02-02 — Recorte de salidas largas de herramientas

**Branch**: `feat/hu-02-02-tool-output-truncation` | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/020-tool-output-truncation/spec.md`

## Summary

El registro de herramientas (`core/tools/registry.py`) sirve, cuando se le da un máximo, cada herramienta envuelta en un decorador (`TruncatingTool`) que recorta el `content` del `ToolResult` que `run` devuelve: conserva principio y final y deja en medio la marca `[salida recortada: se omitieron N caracteres]` (la misma de HU-01-04). El bucle ya obtiene la herramienta con `registry.get` y llama a `run`, así que no cambian los puertos ni `core/loop.py`. El máximo es un parámetro opcional del registro; `config.toml` lo expone como `[limits] max_tool_output_chars` (24 000 por defecto) y `bootstrap.py` lo entrega siempre. Los acotados propios de HU-01-03 y HU-01-04 se conservan; el máximo general deja margen para la cabecera del shell y evita un segundo recorte.

## Technical Context

**Language/Version**: Python 3.12 (solo biblioteca estándar en `core/`).

**Primary Dependencies**: ninguna nueva.

**Storage**: N/A.

**Testing**: pytest (`asyncio_mode = "auto"`), dobles de `tests/doubles/`, `make_rig` de `tests/core/support.py`, cobertura 100 % del módulo nuevo.

**Target Platform**: Windows y Linux (CI de ambos); sin pruebas dependientes de plataforma.

**Project Type**: Biblioteca/CLI hexagonal (`core/` + `adapters/` + `cli/`).

**Performance Goals**: el recorte es O(n) sobre un texto que la herramienta ya produjo; una copia por resultado recortado y ninguna si cabe.

**Constraints**: puertos de `core/interfaces/`, `core/events.py` y `core/loop.py` sin cambios; mensajes de validación en español sin reproducir el valor recibido; el recorte nunca supera el máximo.

**Scale/Scope**: 1 módulo nuevo de `core/tools/`, 1 cambio en el registro, 1 campo aditivo en `config.py`, 1 línea en `bootstrap.py`, 6 archivos de pruebas.

## Constitution Check

*GATE: pasa antes de Fase 0 y se revisa tras la Fase 1.*

| Principio / regla | Cumplimiento |
|---|---|
| I. Una historia, una spec | Solo HU-02-02 (Sp2-12, Sp2-13). Pasa |
| II. Microtareas de 15–40 min | `tasks.md` las divide así. Pasa |
| III. Código modular, tipado, Python 3.12 | Módulo pequeño, `mypy` del repo. Pasa |
| IV. Pruebas y CI multiplataforma | Pruebas sin red ni plataforma; 100 % del módulo. Pasa |
| V. Criterios inmutables | AC-01, flujo y reglas copiados tal cual. Pasa |
| VI. Disciplina de sprints | Sin HU-02-01/02-03/11-03/01-06. El campo de `config.py` es aditivo y se declara. Pasa |
| VII. Consulta quirúrgica | Solo ancla `#hu-02-02` y fichas de dependencia. Pasa |
| VIII. PROGRESO.md | Se actualiza al cerrar (fila a `En revisión`). Tarea de cierre |
| IX. DoD estricta | Revisión cruzada, CI remota y ratificación quedan como tareas humanas |
| X. `docs/archivo/` | No se toca. Pasa |
| V-01…V-17 (falla cerrada, eventos, sin secretos) | El recorte no oculta errores: `is_error` y `call_id` intactos; ningún contenido va a eventos. Pasa |

**Hard Rules de las skills del proyecto**

- `arquitectura-hexagonal-clean`: la regla (recortar) es pura y vive en `core/`; no hay E/S, así que no hace falta puerto nuevo ni adaptador; el decorador implementa el puerto `Tool` existente. Las dependencias llegan por constructor y se cablean en `bootstrap.py`. Eventos: ninguno nuevo (el catálogo de 17 no cambia). Sin `print`, `os.environ` ni `config` en `core/`.
- `estructura-carpetas-harness`: ver tabla de rutas abajo.
- `verificar-fronteras-hexagonales`: `core/tools/output_limit.py` entra en las guardas existentes de `core/` (stdlib + `harness_agent.core`); se comprueba además `test_core_tools_stdlib_only.py` y se añade una guarda `ast` específica del módulo (sin `config`, sin `os`, sin E/S).

### Lista de comprobación de `capas-y-reglas.md` (respuesta de diseño; se revisa de nuevo al cerrar)

| Punto | Resp. | Justificación |
|---|---|---|
| ¿Regla de negocio en `core/` y no en un adaptador? | Sí | `core/tools/output_limit.py` |
| ¿Todo lo externo pasa por un puerto? | Sí | No hay nada externo |
| ¿Puertos, entidades y eventos sin cambios? | Sí | `Tool`/`ToolRegistry`, `ToolResult`, `events.py` intactos |
| ¿Errores externos traducidos, sin reproducir valores? | Sí | `ValueError` en español sin el valor |
| ¿Dependencias por constructor y conectadas solo en `bootstrap.py`? | Sí | `InMemoryToolRegistry(max_output_chars=…)` |
| ¿Núcleo probado con dobles, sin red/disco/claves? | Sí | Herramientas de prueba en memoria |
| ¿Adaptador real con prueba de contrato? | No aplica | No hay adaptador nuevo; la integración con el shell y las herramientas reales se prueba en `tests/integration/` |
| ¿Pasan las guardas de arquitectura en Windows y Linux? | Pendiente de ejecutar | Local en el cierre; CI remota queda para el humano |
| ¿El núcleo emite eventos en lugar de imprimir? | Sí | No imprime |
| ¿Lo público está exportado en `core/__init__.py`? | Sí | `TruncatingTool`, `truncate_output`, `omission_notice`, `check_max_output_chars`, `DEFAULT_MAX_OUTPUT_CHARS`, `MIN_MAX_OUTPUT_CHARS` |
| ¿Decisiones de diseño respetadas (falla cerrada, secretos)? | Sí | Un error largo sigue siendo error; nada se registra |
| ¿Revisó otro integrante? | Pendiente (humano) | Tarea humana final |

## Project Structure

### Documentation (this feature)

```text
specs/020-tool-output-truncation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── output_limit_contract.md
├── checklists/requirements.md
└── tasks.md            # /speckit-tasks
```

### Source Code (repository root) y fila de `estructura-carpetas-harness` que justifica cada ruta

| Archivo | Fila de la tabla | Qué cambia |
|---|---|---|
| `src/harness_agent/core/tools/output_limit.py` (nuevo) | «Regla de negocio… subpaquete de `core/`» e «implementación pura sin E/S» | `truncate_output`, `omission_notice`, `check_max_output_chars`, `TruncatingTool`, constantes |
| `src/harness_agent/core/tools/registry.py` (modifica) | ídem | Parámetro `max_output_chars`; `get`/`list` sirven la herramienta envuelta |
| `src/harness_agent/core/tools/__init__.py`, `core/__init__.py` (modifica) | «Todo lo público de `core/` se exporta» | Exportaciones nuevas |
| `src/harness_agent/config.py` (modifica, aditivo, dueño B) | «Lectura de configuración» | `Limits.max_tool_output_chars` (defecto 24 000) y su validación |
| `config.example.toml` (modifica) | raíz | Campo comentado con su explicación |
| `src/harness_agent/bootstrap.py` (modifica) | «Unir piezas» | `InMemoryToolRegistry(max_output_chars=config.limits.max_tool_output_chars)` |
| `src/harness_agent/adapters/tools/_limits.py`, `adapters/system/shell_limits.py` (solo docstrings) | adaptadores | Quitar «hasta que HU-02-02…» y remitir al recorte general; **valores sin cambio** |
| `tests/unit/core/tools/test_output_limit.py` (nuevo) | espejo de `src/` | Función pura y decorador |
| `tests/unit/core/tools/test_registry_output_limit.py` (nuevo) | espejo de `src/` | Registro con y sin máximo |
| `tests/unit/test_config_max_tool_output_chars.py` (nuevo) | espejo de `src/` | Campo y validación |
| `tests/unit/test_bootstrap_tool_output_limit.py` (nuevo) | espejo de `src/` | El registro compuesto recorta |
| `tests/integration/test_tool_output_truncation.py` (nuevo) | «integration con el `AgentLoop` real» | Sp2-13: salida enorme por el bucle real y convivencia con `ShellTool`/herramientas de archivos reales |
| `tests/architecture/test_output_limit_boundaries.py` (nuevo) | guarda `ast` del módulo | Frontera del módulo nuevo |
| `.claude/skills/estructura-carpetas-harness/references/arbol.md` y copia en `.agents/skills/` (modifica) | skills | Reflejar el archivo nuevo |
| `docs/PROGRESO.md`, `CLAUDE.md` (modifica) | Principio VIII | Estado, evidencia y snapshot |

**Structure Decision**: un único módulo nuevo en `core/tools/` (junto al registro que lo usa). No hay carpeta nueva, puerto nuevo ni evento nuevo.

### Decisiones clave (detalle en `research.md`)

1. **Envolver al registrar, no tocar el bucle**: `get`/`list` sirven la herramienta envuelta; el bucle y la política no se enteran.
2. **Sin máximo = sin envoltura** (compatibilidad con HU-01-02: `get` devuelve la instancia registrada); el arranque real siempre lo pasa.
3. **Máximo por defecto 24 000** para no volver a recortar lo que las herramientas ya acotaron (cuerpo 20 000 + cabecera).
4. **Marca única compartida** con el shell: mismo texto, un solo formato para el modelo.

## Complexity Tracking

| Violación | Por qué se necesita | Alternativa más simple descartada |
|---|---|---|
| Campo nuevo en `config.py` (área de B) | La regla de negocio 1 exige un máximo configurable por el operador (confirmado en `/speckit-clarify`) | Solo parámetro de constructor: el operador no podría cambiarlo sin tocar código |
| Constructor «sin máximo» frente a 24 000 en configuración | Evitar doble recorte y no romper el uso existente del registro (`get(...) is tool`) | Defecto 20 000 siempre activo: recorta dos veces la salida del shell y obliga a reescribir pruebas de HU-01-02 |
