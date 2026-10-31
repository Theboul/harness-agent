# Implementation Plan: HU-07-04 — Reintentos con espera exponencial

**Branch**: `claude/hu-07-04-retries-4df828` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/034-provider-retries/spec.md`

## Summary

Una **envoltura** del puerto `Provider` (`RetryingProvider`, en `adapters/providers/`) reintenta las llamadas que fallan con un error temporal (`ProviderTimeout`, `ProviderUnavailable` y el nuevo `RateLimited`, subtipo de `QuotaExceeded` que el adaptador de LiteLLM produce para `RateLimitError`), con espera exponencial determinista, tope, pista de espera opcional del proveedor y número de intentos acotado. Agotados los intentos, propaga el último error tal cual (HU-07-05 podrá conmutar). Cada reintento se comunica a un observador inyectable sin datos; `compose()` lo publica como `provider_error` (motivo `retry`) en la sesión activa. Nueva sección opcional `[retries]` en `config.py`. No cambian el bucle, los puertos ni el catálogo de eventos.

## Technical Context

**Language/Version**: Python 3.12 (solo biblioteca estándar en el módulo nuevo)

**Primary Dependencies**: ninguna nueva (`asyncio`, `math`, `dataclasses`); LiteLLM solo lo toca el adaptador existente

**Storage**: N/A (los eventos que publica `compose()` los guarda el registrador existente)

**Testing**: pytest (`asyncio_mode = "auto"`), `FakeProvider` (protegido, sin modificar), espera y observador inyectados; centinela `VALOR-DE-PRUEBA-123`

**Target Platform**: Windows y Linux (CI)

**Project Type**: CLI (harness de agente)

**Performance Goals**: N/A; ninguna prueba espera de verdad

**Constraints**: no tocar `core/loop.py`, `core/events.py`, `core/interfaces/`, `tests/doubles/`; cambios en `config.py` y `bootstrap.py` mínimos y aditivos (otras sesiones los editan en paralelo)

**Scale/Scope**: 1 módulo nuevo (~150 líneas), 1 error nuevo, cambios aditivos en config, bootstrap y el adaptador LiteLLM

## Constitution Check

*GATE: pasa antes de la investigación y se revisa tras el diseño.*

- Principio V (AC inmutables): AC-01 copiado sin cambios. **Sí**.
- Principio VI (sprint): la ficha dice Sprint 3; el orden por sprints ya no rige por decisión del usuario (cierre adelantado al 2026-11-06, trabajo por carriles de archivos). Se anota en `PROGRESO.md`. **Sí, con la decisión documentada**.
- Principio VII (contexto mínimo): se leyó la ficha, la de HU-07-02 y el código del adaptador. **Sí**.
- V-xx de seguridad y secretos: el registro de intento no lleva texto de error, claves ni argumentos (FR-009; prueba con centinela). **Sí**.
- Falla cerrada: lo no clasificado como temporal no se reintenta; un fallo del observador no cambia el resultado. **Sí**.
- Archivos protegidos: ninguno se modifica (verificación `git diff` al cerrar). **Sí**.

**Hard Rules de las skills del proyecto**

*arquitectura-hexagonal-clean — Decision Gates*

| Pregunta | Resultado |
|---|---|
| ¿Regla de negocio nueva en `core/`? | No: es política de resiliencia del adaptador; no cambia ninguna regla del dominio. Va en `adapters/providers/` |
| ¿Necesita algo de fuera? | Solo espera (`asyncio.sleep`): se inyecta por constructor; ningún puerto nuevo |
| ¿Quién lo implementa? | `RetryingProvider(Provider)` en `adapters/providers/retrying_provider.py` |
| ¿Cómo se conecta? | Por constructor, en `compose()` de `bootstrap.py` |
| ¿Cómo se prueba? | `FakeProvider` + `sleep` y observador de prueba, sin red ni claves; guarda `ast` nueva |
| ¿Es asíncrono? | `Provider.complete` lo es (D-01); la espera es `await sleep(...)` y `CancelledError` se propaga |

**Lista de comprobación de `capas-y-reglas.md` (respondida)**

- ¿Regla de negocio en `core/` y no en un adaptador? **No** — justificado: política de transporte del proveedor, no del dominio; `core/` sigue sin conocer los reintentos.
- ¿Todo lo externo pasa por un puerto con tipos del dominio? **Sí**: la envoltura es un `Provider` que envuelve a otro `Provider`; la espera es una función inyectada.
- ¿Puertos, entidades y eventos sin cambios? **Sí**.
- ¿Errores externos traducidos a errores de dominio sin reproducir valores? **Sí**: `RateLimitError` → `RateLimited` con texto propio; el registro de intento solo lleva el nombre de la clase canónica.
- ¿Dependencias por constructor, cableadas solo en `bootstrap.py`? **Sí**.
- ¿Núcleo probado con dobles? **Sí** (no hay cambio de núcleo; la envoltura se prueba con `FakeProvider`).
- ¿Prueba de contrato en `tests/contracts/`? **Sí**: la envoltura cumple el contrato `Provider` existente (se comprueba en la tarea correspondiente si el contrato es parametrizable; si no, prueba unitaria del mismo comportamiento y se anota).
- ¿`pytest tests/architecture` y la guarda nueva? **Sí** (`test_retry_boundaries.py`).
- ¿El núcleo emite eventos en lugar de imprimir? **Sí**: nada imprime; el evento sale por el bus desde `bootstrap.py`.
- ¿Lo público de `core/` exportado en `core/__init__.py`? **N/A**: nada nuevo en `core/`; el consumidor (`bootstrap.py`) importa del subpaquete del adaptador, como ya hace con `litellm_provider`.
- ¿Decisiones de diseño respetadas (falla cerrada, secretos)? **Sí**.
- ¿Otro integrante revisó? **Pendiente (tarea humana)**.

*estructura-carpetas-harness — ruta de cada archivo nuevo*

| Archivo | Fila de la tabla |
|---|---|
| `adapters/providers/errors.py` (`RateLimited`) | «Error de dominio»… pero **no** puede ir a `core/` (contrato protegido) → queda como tipo del adaptador, junto al código que lo lanza |
| `adapters/providers/retrying_provider.py` | «Código con red, … → `adapters/<subpaquete>/`» (envuelve a un proveedor) |
| `tests/unit/adapters/providers/test_retrying_*.py`, `test_rate_limited.py` | Espejo de `src/` en `tests/unit/` |
| `tests/architecture/test_retry_boundaries.py` | Guarda `ast` del módulo nuevo (receta de módulo nuevo) |
| `tests/integration/test_retry_flow.py` | Bucle real + envoltura (integración) |
| `config.py` (sección `[retries]`), `bootstrap.py` | «Lectura de configuración» / «Unir piezas» |

*verificar-fronteras-hexagonales*: el módulo nuevo importa solo biblioteca estándar y `harness_agent.core`; lo vigila `test_providers_boundaries.py` (existente) más la guarda nueva; se ejecuta `pytest tests/architecture` al cerrar.

## Project Structure

### Documentation (this feature)

```text
specs/034-provider-retries/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/retrying_provider.md
├── checklists/requirements.md
└── tasks.md   # /speckit-tasks
```

### Source Code (repository root)

```text
src/harness_agent/
├── adapters/providers/
│   ├── errors.py               # nuevo: RateLimited(QuotaExceeded)
│   ├── retrying_provider.py    # nuevo: RetryPolicy, RetryAttempt, RetryingProvider
│   └── litellm_provider.py     # cambio mínimo: RateLimitError -> RateLimited(+pista)
├── config.py                   # aditivo: Retries, [retries], HarnessConfig.retries
└── bootstrap.py                # aditivo: envolver proveedor, observador -> bus, cursor de sesión

tests/
├── unit/adapters/providers/    # test_rate_limited.py, test_retrying_*.py
├── unit/test_config_retries.py
├── unit/test_bootstrap_retries.py
├── architecture/test_retry_boundaries.py
└── integration/test_retry_flow.py
```

**Structure Decision**: envoltura en el subpaquete del proveedor; `core/` intacto.

## Complexity Tracking

| Desvío | Por qué | Alternativa rechazada |
|---|---|---|
| `RateLimited` vive en `adapters/` y no en `core/interfaces/provider.py` | El puerto es contrato protegido (acuerdo de A, B y C) | Añadirlo al puerto: queda como propuesta en `PROGRESO.md` para cuando se acuerde |
| Cursor de sesión mutable en `bootstrap.py` | El observador debe publicar en la sesión activa tras `/reanudar` | Fijar la sesión de arranque: los eventos irían a la sesión equivocada |
