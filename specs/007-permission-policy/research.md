# Research: HU-05-01 — Política denegar, preguntar, permitir que falla cerrada

**Fecha**: 2026-10-21 · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

Sin investigación externa: es una política pura y pequeña. Cada decisión recoge qué se eligió, por qué y qué alternativas se descartaron.

## R-01 — Una política con reglas fijas y listas de configuración, no un motor de reglas

- **Decisión**: una clase con un algoritmo de siete pasos fijo (plan D5) y dos listas configurables (`deny`, `ask`).
- **Razón**: la historia pide un orden y unas pocas reglas; un motor de reglas genérico (condiciones, patrones, prioridades) es diseño de más y abre la puerta a reglas de permitir por configuración.
- **Alternativas**: tabla de reglas ordenadas (descartada: más superficie y más forma de equivocarse); patrones o globs de herramientas (descartada: HU-05-02 trae los patrones de comandos).

## R-02 — Todo «permitir» pasa por `AuthorizedArea.contains`

- **Decisión**: la política devuelve «permitir» solo desde `_inside_area`, la función que usan las dos reglas de permitir (escritura y lectura), y solo si `area.contains(path)` es exactamente `True`.
- **Razón**: la regla de negocio 5 y SC-008 piden que no exista una regla de permitir todo; con todo «permitir» detrás de la misma condición, una prueba de `ast` y una de matriz con un comprobador espía lo garantizan (no se cuenta cuántas reglas hay: se comprueba que ninguna permite sin pasar por el área).
- **Alternativas**: un `ALLOW` por regla (descartada: dos puntos que vigilar y copiar la validación).

## R-03 — El riesgo se consulta en el registro por nombre

- **Decisión**: `registry.get(name).risk`; `None` o un valor que no es `RiskLevel` se trata como no previsto.
- **Razón**: FR-015 de HU-01-02 ya expone el riesgo «para que la política de permisos lo consulte»; no hace falta tocar el puerto `Tool`.
- **Alternativas**: tabla propia de riesgos en la política (descartada: duplicaría lo que declara cada herramienta).

## R-04 — `path` por convención, no por metadato

- **Decisión**: el argumento se llama `path` (Q2, opción A) y se documenta en `contracts/path_argument_convention.md`.
- **Razón**: no cambia ningún puerto; HU-01-03 lo cumple al definir sus herramientas.
- **Alternativas**: declarar el argumento por herramienta en la configuración (descartada: más configuración y más errores posibles); ampliar `Tool` (descartada: cambia un puerto).

## R-05 — La contención la decide `AuthorizedArea`

- **Decisión**: la política llama a `area.contains(path)` y solo acepta `True` exacto; no resuelve rutas.
- **Razón**: la ruta real (enlaces simbólicos, unidades, UNC) es responsabilidad del componente de área (HU-01-03); reimplementarla duplicaría una comprobación de seguridad.
- **Alternativas**: normalizar la ruta en la política (descartada: duplica y puede diferir del componente real).

## R-06 — Falla cerrada en dos niveles

- **Decisión**: lo no evaluable con seguridad (llamada mal formada, `path` inválido, excepción) se **deniega**; lo que ninguna regla prevé se **pregunta** (AC-01). El bucle resuelve ambos como denegación en el Sprint 1.
- **Razón**: la spec (tabla «Casos de falla cerrada»): AC-01 es inmutable y dice «requiere aprobación manual».
- **Alternativas**: denegar todo lo no previsto (descartada: contradice AC-01).

## R-07 — `PermissionRules` validadas al construirse

- **Decisión**: `PermissionRules` valida que cada nombre sea un texto no vacío (`ValueError` en español) y la política valida el tipo de sus colaboradores (`TypeError`); `config.py` hace además su propia validación con mensajes por campo.
- **Razón**: falla cerrada en la construcción; la configuración da el mensaje al usuario y la validación del tipo protege a quien construya las reglas a mano.
- **Alternativas**: confiar en el tipo (descartada: un `deny` mal formado podría ignorarse sin avisar).

## R-08 — Una sola función para la regla de lectura y de escritura

- **Decisión**: ambas reglas usan `_inside_area`; solo cambia quién la llama (riesgo medio siempre, riesgo bajo con `path` y si la regla de lectura está activa).
- **Razón**: misma validación de `path`, mismo comprobador, un punto de «permitir» (R-02); la regla de lectura se apaga con `allow_reads_in_area=False` (plan D6).
- **Alternativas**: dos funciones (descartada: dos puntos de «permitir»).
