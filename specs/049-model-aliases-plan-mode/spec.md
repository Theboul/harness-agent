# Especificación: HU-06-06 (propuesta) — Varios modelos por alias y modo de planificación

**Rama**: `claude/sweet-mccarthy-23018c` · **Responsable**: C — Control y conexiones · **Historia propuesta** (fuera de la lista original; pendiente de ratificación del PO, como HU-06-05 y HU-00-08.1)
**Depende de**: HU-06-05 (`/model`, `ModelView`), HU-07-02 (`LiteLLMProvider`), HU-07-04 (`RetryingProvider`), HU-05-07 (`ReadOnlyPolicy`) · **Ficha**: [HU-06-06](../../docs/04c-historias-control.md#hu-06-06)

## Resumen

La persona usa dos modelos en una misma sesión, p. ej. Gemini para planear y Groq para implementar, sin reiniciar ni editar la configuración a mano. `config.toml` declara alias (`[models]`), `/model <alias>` cambia el modelo en caliente, `/plan` cambia al alias `plan` y activa el modo de solo lectura de HU-05-07, y `/implementar` vuelve al alias `build` (o al predeterminado) y lo desactiva. El historial se conserva.

## Clarificaciones

### Sesión 2026-10-31

Sin preguntas al PO: las decisiones de diseño se fijan con la opción más simple.

- Q: ¿Qué es un alias? → A: un nombre en minúsculas (`[a-z][a-z0-9_-]{0,31}`) que apunta a `<proveedor>/<modelo>` de LiteLLM; el proveedor debe ser uno de los admitidos. `predeterminado` está reservado (vuelve al `model` de siempre).
- Q: ¿De dónde salen las claves? → A: solo del entorno/.env, por proveedor (`GEMINI_API_KEY`, `GROQ_API_KEY`…). `config.py` las lee al cargar y guarda cada una dentro del alias; una clave que falta **no detiene el arranque**: falla al elegir ese alias, con un aviso fijo que nombra la variable.
- Q: ¿Cómo se cambia en caliente sin tocar el bucle? → A: un proveedor conmutable (`ModelSwitch`, `adapters/providers/`) que delega en el activo; el `RetryingProvider` lo envuelve por fuera. El compactador, la ventana de contexto y las sesiones nuevas leen el modelo activo.
- Q: ¿`/plan` sin alias `plan`? → A: usa el modelo predeterminado y solo activa el solo lectura.
- Q: ¿`/plan` cuando el alias no se puede usar (clave ausente, dependencia)? → A: no cambia nada (atómico) y lo dice.
- Q: ¿`/implementar` con `--solo-lectura` o `read_only = true`? → A: el modo fijado al arrancar **no se puede apagar**; cambia el modelo y avisa de que el solo lectura sigue.
- Q: ¿`/modo`? → A: no; el estado se ve en `/model` (línea de modo) y lo confirman `/plan` e `/implementar`.

## Escenarios

1. Sin `[models]` todo es como hoy; `/model` muestra lo mismo.
2. `/model` lista alias, modelo activo y modo, sin claves.
3. `/model plan` cambia el proveedor de las llamadas siguientes; el historial sigue.
4. Alias desconocido o sin clave: línea fija, nada cambia.
5. `/plan` → modelo `plan` + solo lectura (una escritura se deniega); `/implementar` → `build` (o predeterminado) + escritura de nuevo permitida (según la política normal).
6. `/nueva`, la compactación y la ventana usan el modelo activo.
7. `/ayuda` lista los comandos nuevos.

## Requisitos funcionales

- **FR-001** `config.toml` admite `[models]` (alias → texto `<proveedor>/<modelo>`); rechaza campos con aspecto de clave, alias inválidos, valores sin la forma o con proveedor desconocido (mensajes fijos sin reproducir el valor).
- **FR-002** `ModelAlias(alias, model, api_key, key_variable)` en `HarnessConfig.models`; las claves solo del entorno.
- **FR-003** `ModelSwitch` (adapters/providers): `Provider` conmutable; `select(alias)` construye (y recuerda) el proveedor del alias con una función inyectada; errores `UnknownModelAlias`/`ModelUnavailable` con código, sin texto externo.
- **FR-004** `ReadOnlySwitch` y `SwitchablePolicy` (core/permissions): conmutan entre la política restringida y la abierta; fallan cerrado; el valor fijado al arrancar queda bloqueado.
- **FR-005** `/model [alias]`, `/plan`, `/implementar` en `bootstrap.py`; `ModelView` y `format_model` muestran alias y modo.
- **FR-006** No cambian `core/interfaces/`, `core/events.py`, `core/loop.py` ni `tests/doubles/`.

## Fuera de alcance

Subagentes; conmutación automática por fallo (HU-07-05); modelo por herramienta; límites de coste.

## Criterios de aceptación propuestos

- **AC-01** Dado `[models]` con `plan` y `build`, cuando la persona escribe `/model build`, entonces las llamadas siguientes van al modelo de `build` y el historial se conserva.
- **AC-02** Dado un alias cuyo proveedor no tiene clave en el entorno, cuando se elige, entonces se avisa con un texto fijo que nombra la variable y el modelo activo no cambia; el arranque nunca falla por eso.
- **AC-03** Cuando la persona escribe `/plan`, entonces se usa el modelo `plan` y se deniega toda escritura; con `/implementar` se vuelve a `build` (o al predeterminado) y se desactiva el solo lectura.
- **AC-04** Sin `[models]` el sistema se comporta como antes.
- **AC-05** Ninguna clave aparece en `/model`, avisos, eventos ni archivos del repositorio.

## Criterios de éxito

- **SC-001** Cuatro puertas de calidad y `pytest tests/architecture` en exit 0; 100 % de líneas y ramas de lo nuevo.
- **SC-002** Diff de archivos protegidos vacío.
