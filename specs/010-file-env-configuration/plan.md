# Implementation Plan: HU-00-04 — Configuración por archivo y variables de entorno

**Branch**: `010-file-env-configuration` (directorio de la spec; el trabajo se hace en la rama `gustavo`) | **Date**: 2026-10-20 | **Spec**: [specs/010-file-env-configuration/spec.md](spec.md)

**Input**: Feature specification from `/specs/010-file-env-configuration/spec.md`

**Directrices del usuario**: `config.py` en `src/harness_agent/` (fuera de `core/`); `tomllib` de la biblioteca estándar y ninguna dependencia nueva; objetos de configuración inmutables y tipados, con un campo reservado por cada valor que otras historias declaran necesitar (el modelo, los tres límites de HU-01-06, la raíz del área autorizada y la ruta de la base de datos); errores de dominio en frases completas en español, sin valores ni trazas; secretos con `repr` oculto; comprobación automática de AC-02 sobre los archivos versionados (con salto justificado si no hay repositorio git) y procedimiento manual documentado para el historial; **no modificar los puertos de `core/interfaces/`**.

---

## Summary

Implementar la carga de configuración como un único módulo `src/harness_agent/config.py`, fuera del núcleo, con una función `load_config(...)` que localiza el archivo (`config.toml` en el directorio de trabajo, o el indicado por parámetro o por `HARNESS_CONFIG`), lo lee con `tomllib`, rechaza lo que no entiende (campos desconocidos, campos que parecen claves, valores fuera de rango) y devuelve un `HarnessConfig` inmutable y tipado. Los valores no secretos salen solo del archivo; la clave del proveedor del modelo configurado sale solo de una variable de entorno y viaja en un `Secret` cuyo `repr` está oculto. Cada fallo es un error de dominio con una frase completa en español que nombra el campo o la variable, sin valores recibidos ni trazas. El repositorio gana dos plantillas sin secretos (`.env.example`, `config.example.toml`), las entradas de `.gitignore` y dos pruebas de arquitectura: una que recorre los archivos versionados buscando claves (AC-02) y otra que garantiza que el núcleo no lee archivos ni entorno. El historial se comprueba con un procedimiento manual documentado. El núcleo recibe valores ya cargados; no se toca ningún puerto.

---

## Technical Context

**Language/Version**: Python 3.12, única versión soportada (PD-07): `pyproject.toml` fija `requires-python >=3.12,<3.13`, `mypy` usa 3.12, `ruff` apunta a `py312` y la CI prueba solo 3.12.

**Primary Dependencies**: solo biblioteca estándar en `config.py` (`tomllib`, `os`, `re`, `dataclasses`, `pathlib`, `collections.abc`, `typing`). Sin dependencias nuevas de ejecución ni de desarrollo; se reutilizan `pytest`, `pytest-cov`, `mypy` y `ruff`, ya fijadas en `requirements-dev.txt`. Las pruebas de AC-02 usan además el ejecutable `git`, que ya existe en los runners de la CI.

**Storage**: N/A. Se lee un archivo TOML y variables de entorno; no se escribe nada. La ruta de la base de datos de sesiones es solo un valor reservado (HU-03-01 la usará).

**Testing**: `pytest` con `tmp_path` y un `environ` inyectado como diccionario, de modo que casi ninguna prueba toca el entorno real. Hay **dos pruebas de la ruta de producción `environ=None`** (que usa `os.environ`): la de `HARNESS_CONFIG` en T006 y la de la clave en T013, ambas con `monkeypatch.setenv` y `monkeypatch.delenv`; el directorio de trabajo se cambia con `monkeypatch.chdir`. Pruebas unitarias de carga, validación y secretos; pruebas de arquitectura de AC-02 y de «el núcleo no lee configuración»; prueba de plantillas. Sin red ni proveedor real. La segunda frase de FR-022 (rutas con la forma de otro sistema) la cubre la matriz de CI de Windows y Linux (T027).

**Target Platform**: Windows y Linux (matriz de CI: `ubuntu-latest` y `windows-latest`, Python 3.12).

**Project Type**: Biblioteca modular. `config.py` pertenece a la capa exterior (carga de entorno), no al núcleo.

**Performance Goals**: carga y validación de una configuración completa en menos de 100 ms de media (SC-007); es una lectura de archivo pequeño y un recorrido lineal.

**Constraints**:
1. `core/interfaces/*` queda sin modificar (verificable con `git diff`).
2. `core/` no lee archivos ni variables de entorno ni importa `harness_agent.config` (FR-011; prueba de arquitectura nueva).
3. `mypy --strict` sobre `src` y `tests`; `ruff` con línea de 100 columnas.
4. Sin lógica de HU-01-03, HU-01-06, HU-03-01 ni de los adaptadores de proveedor: solo campos reservados (Principio VI, ver desviación D2).
5. Falla cerrada: archivo ausente, ilegible, roto, con campos desconocidos o con campos de clave detiene el arranque (FR-006, FR-008, FR-014).
6. Los secretos no aparecen en mensajes de error, `repr`, texto de objetos ni archivos versionados (RNF-16).

**Scale/Scope**: 1 módulo de código fuente (`config.py`), 2 plantillas, 1 cambio de `.gitignore`, 1 archivo de contrato, 1 ayudante de pruebas y 7 módulos de prueba nuevos (5 unitarios y 2 de arquitectura).

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / Restricción | Requisito | Pre-diseño | Post-diseño | Evidencia |
|---|---|---|---|---|
| **I** | Una historia por especificación | PASS | PASS | Solo HU-00-04. No se incluyen HU-01-03, HU-01-06, HU-03-01, HU-07-02 ni HU-10-02. |
| **II** | Microtareas de 15–40 min (máx. 60) | PASS | PASS | Módulo pequeño y separable (secreto, errores, localización, lectura, validación, claves, plantillas, comprobaciones); `/speckit-tasks` lo dividirá en tareas de 30 min como máximo. |
| **III** | Python 3.12+, tipado, hexagonal, `core/` sin libs externas | PASS | PASS | `config.py` solo usa biblioteca estándar y vive fuera de `core/`; el núcleo recibe valores por inyección y una prueba lo verifica (R-14). Ver R-01. |
| **IV** | Pruebas automatizadas, calidad y CI en Windows y Linux | PASS | PASS | Pruebas sin red con `tmp_path` y `environ` inyectado; `ruff`, `mypy --strict` y `pytest` en la matriz existente (R-15). |
| **V** | Criterios de aceptación inmutables | PASS | PASS | AC-01 y AC-02 copiados tal cual en el spec y verificados con las pruebas de la trazabilidad. |
| **VI** | Sin código de sprints futuros | PASS | PASS con nota | Sprint 1. Se reservan campos tipados para HU-01-06 (Sprint 2) sin ninguna lógica; ver desviación D2. No se crea `bootstrap.py` ni adaptadores. |
| **VII** | Consulta documental quirúrgica | PASS | PASS | Se leyeron solo la ficha HU-00-04 y las que consumen sus valores (HU-01-03, HU-01-06, HU-03-01, HU-07-02), la trazabilidad, la skill de carpetas y la constitución. |
| **VIII** | Registro en `docs/PROGRESO.md` | PASS | PASS | Registro por tarea, `En curso` al empezar y `En revisión` al terminar (lo concretan las tareas). |
| **IX** | Definition of Done y revisión humana | PASS | PASS | Revisión cruzada por A (otra área distinta de quien implementa) y CI en ambos sistemas como tareas humanas finales; DoD (5), ausencia de secretos, la cubren R-12 y R-13. |
| **X** | `docs/archivo/` inmutable | PASS | PASS | No se toca. |
| **Falla cerrada** | Lo ambiguo se deniega | PASS | PASS | Archivo inexistente, campo desconocido, campo de clave y raíz de área sin configurar se tratan como error o como «sin autorización» (R-03, R-07). |
| **Hexagonal** | `core/` no importa `adapters/`, `cli/`, SDK; puertos intactos | PASS | PASS | Ningún puerto cambia; `config.py` no importa `core`. |

**Resultado del gate**: sin violaciones; se anotan 7 desviaciones (D1 a D7), un aviso de capacidad y puntos de revisión más abajo, ninguno bloqueante.

---

## Project Structure

### Documentation (this feature)

```text
specs/010-file-env-configuration/
├── spec.md                          # Especificación (3 aclaraciones aplicadas)
├── plan.md                          # Este archivo
├── research.md                      # Fase 0: decisiones y alternativas (R-01 a R-17)
├── data-model.md                    # Fase 1: tipos, errores y reglas de validación
├── quickstart.md                    # Fase 1: guía de validación ejecutable
├── contracts/
│   └── config_loading_contract.md   # Fase 1: función de carga, errores, plantillas y comprobaciones
├── checklists/
│   └── requirements.md              # Checklist de calidad del spec
└── tasks.md                         # Fase 2 (/speckit-tasks; NO lo crea este comando)
```

### Source Code (repository root)

Archivos nuevos (N) y modificados (M). **No se modifica ningún archivo de `src/harness_agent/core/interfaces/`.**

```text
.env.example                           # N: plantilla de variables de entorno, sin secretos
config.example.toml                    # N: plantilla de configuración, sin secretos
.gitignore                             # M: ignora .env, config.toml y .harness/ (FR-019, D3 aceptada)

src/harness_agent/
├── config.py                          # N: load_config, HarnessConfig, Limits, Paths, Secret, errores (stdlib)
└── core/                              # SIN CAMBIOS (no lee configuración)
    └── interfaces/                    # SIN CAMBIOS (puertos de HU-00-01)

tests/
├── unit/
│   ├── config_support.py              # N: ayudantes compartidos de las pruebas de configuración (sin pruebas)
│   ├── test_config_secret.py          # N: Secret y errores (textos, sin valores)
│   ├── test_config_location.py        # N: parámetro > HARNESS_CONFIG > config.toml; archivo ausente/ilegible/roto
│   ├── test_config_schema.py          # N: tipos, rangos, campos desconocidos, rutas, inmutabilidad (AC-01)
│   ├── test_config_keys.py            # N: claves solo del entorno, campos de clave en el archivo, centinela
│   └── test_config_templates.py       # N: las plantillas cargan, están sincronizadas y no llevan secretos
└── architecture/
    ├── test_no_secrets_in_repo.py     # N: AC-02 sobre `git ls-files` (+ autoprueba del detector)
    └── test_core_reads_no_config.py   # N: el núcleo no lee archivos ni entorno ni importa config
```

**Structure Decision**: Se sigue el árbol de la skill `estructura-carpetas-harness`: «Lectura de configuración» va en `config.py` en la raíz del paquete, fuera de `core/`, y las plantillas `.env.example` y `config.example.toml` en la raíz del repositorio. Las pruebas reflejan `src/harness_agent/` bajo `tests/unit/`; las dos comprobaciones del repositorio van en `tests/architecture/`, donde ya viven las demás barreras (`test_core_boundaries.py`, `test_core_tools_stdlib_only.py`, `test_loop_boundaries.py`). Los errores de dominio se mantienen locales en `config.py` (no hay `core/errors.py` compartido y esta capa no es el núcleo). No se crea `bootstrap.py`: lo creará la historia del bucle o de la CLI, que llamará a `load_config` y repartirá los valores (R-01).

---

## Trazabilidad de requisitos y criterios de aceptación

| Requisito | Componentes | Verificación |
|---|---|---|
| **AC-01** (otro modelo, sin tocar el código) | `load_config`, `HarnessConfig.model` | `test_config_schema.py`: dos archivos con modelos distintos devuelven cada uno el suyo |
| **AC-02** (sin claves en el repositorio) | `.gitignore`, plantillas, comprobación de archivos versionados, procedimiento manual | `tests/architecture/test_no_secrets_in_repo.py`; historial: [quickstart.md](quickstart.md) §4 |
| **Regla 1** (claves nunca en archivos ni repositorio) | rechazo de campos de clave, lectura solo del entorno | `test_config_keys.py`, `test_no_secrets_in_repo.py` |
| **Regla 2** (plantilla sin secretos y `.gitignore`) | `.env.example`, `config.example.toml`, `.gitignore` | `test_config_templates.py`, `test_no_secrets_in_repo.py` |
| **RF-7.6** (clave del proveedor desde el entorno) | tabla proveedor→variable, `Secret`, `MissingKeyError` | `test_config_keys.py` |
| **RNF-16** (secretos fuera de archivos, mensajes y registros) | `Secret`, textos de error sin valores | `test_config_secret.py`, `test_config_keys.py` (centinela) |
| **RNF-21** (cambiar por configuración, núcleo desacoplado) | `load_config`, valores inyectados | `test_config_schema.py`, `test_core_reads_no_config.py` |
| **FR-001 a FR-012** | `config.py` (localización, lectura, esquema, validación, rutas, núcleo sin lectura, inmutabilidad) | `test_config_location.py`, `test_config_schema.py`, `test_core_reads_no_config.py` |
| **FR-013 a FR-017** | claves, `Secret`, errores | `test_config_keys.py`, `test_config_secret.py` |
| **FR-018 a FR-021** | plantillas, `.gitignore`, comprobación y procedimiento | `test_config_templates.py`, `test_no_secrets_in_repo.py`, quickstart §4 |
| **FR-022 y FR-023** | UTF-8/CRLF/BOM, rutas relativas, `tmp_path` y `environ` inyectado | `test_config_location.py`, `test_config_schema.py`; matriz de CI |
| **SC-007** (latencia) | recorrido lineal | prueba de humo con margen amplio en `test_config_schema.py` |

---

## Desviaciones y puntos a revisar por el equipo

**Desviaciones respecto de la documentación y la constitución** (ninguna bloqueante):

- **D1 — `config.example.toml` sin «reglas de permisos»**: el árbol acordado lo describe con «modelo, límites, rutas, reglas de permisos». Aquí contiene solo modelo, límites y rutas, por la decisión del responsable y porque las reglas de permisos son de HU-05-xx. Por falla cerrada, un campo de permisos se rechaza hoy como desconocido; cuando llegue esa historia ampliará el esquema.
- **D2 — Campos reservados para HU-01-06 (Sprint 2)**: el Principio VI prohíbe código de sprints futuros. Aquí solo se reserva un campo tipado con su valor por defecto y su validación de tipo y rango, sin ninguna lógica del bucle; se justifica porque Sp1-09 pide «definir el esquema de configuración y sus valores por defecto» y porque el responsable lo decidió así (decisión 2). Lo mismo para HU-01-03 y HU-03-01 (Sprint 1).
- **D3 — `.harness/` en `.gitignore` (aceptada por el responsable)**: la ruta por defecto de la base de datos es `.harness/sessions.db` y puede contener conversaciones con datos sensibles. Se ignora `.harness/` junto con `.env` y `config.toml`; el spec lo recoge en FR-019 y las pruebas de AC-02 lo comprueban.
- **D4 — El sistema no lee `.env`**: «las claves se leen solo de variables de entorno» se cumple literalmente; `.env` es solo la plantilla local que la persona usuaria carga en su entorno (la plantilla indica cómo, en PowerShell y en bash). Leer `.env` exigiría una dependencia o código propio y ampliaría el origen de las claves.
- **D5 — Tipos de configuración propios en `config.py`**: el núcleo no puede importar `config.py`, así que cuando HU-01-06 defina sus límites en `core/limits.py` (área A) habrá que mapear los tipos en la raíz de composición o hacer que `config.py` los importe (`config.py` sí puede importar `core`). Es una decisión a coordinar con A; no afecta a esta historia.
- **D6 — Tabla de proveedores provisional**: la variable de entorno de la clave depende del proveedor del modelo (`anthropic/…`, `openai/…`, `fake/…`). La tabla inicial es mínima y la ampliarán HU-07-02 y HU-07-03; un proveedor que no esté en la tabla se rechaza como desconocido.
- **D7 — La comprobación de AC-02 necesita `git`**: se salta con un motivo explícito si no hay repositorio o no hay `git`, salvo cuando la variable `CI` está definida, donde falla (R-12).

**Puntos a confirmar** (no bloqueantes):

1. **Nombres de variables de clave** (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) y **formato del modelo** `<proveedor>/<modelo>`: son los de LiteLLM, que usará HU-07-02; conviene confirmarlos con B antes de implementar.
2. **Valores por defecto de los límites** (30 turnos, 600 s, 200 000 tokens): no los fija ningún documento; son un punto de partida editable en la plantilla.
3. **Lectura de RF-7.6, RNF-16 y RNF-21** (R-16): su texto no figura en la documentación activa.

**Aviso de capacidad**: la estimación de las microtareas (680 min, 11,3 h, tras dividir tres tareas para respetar los 30 min) supera los 180 min (3 h) presupuestados en `docs/03-plan-sprints.md` para Sp1-09, Sp1-10 y Sp1-11, unas 3,8 veces. Por decisión del responsable **no se recorta el alcance**; la discrepancia se declara aquí y en `tasks.md`, y la tarea de `docs/PROGRESO.md` la anota como aviso a B. Sprint 1 ya supera la disponibilidad media (R-20 del plan de sprint).
