# Implementation Tasks: HU-00-02 — Integración continua con pruebas, tipado y formato

**Feature**: `specs/002-ci-testing-formatting/spec.md`  
**Plan**: `specs/002-ci-testing-formatting/plan.md`  
**Responsable**: A — Núcleo  
**Sprint**: Sprint 1 | **PHU**: 2  

---

## Phase 1: Setup & Dependencias Reproducibles (Sp1-06)

**Propósito**: Establecer el manifiesto determinista de versiones fijadas para herramientas de desarrollo y CI, garantizando instalaciones idénticas y reproducibles en Linux y Windows.

- [x] **T001** [P] Crear manifiesto de dependencias fijadas en `requirements-dev.txt` con versiones exactas para herramientas de calidad y CI (Sp1-06)
  - **Archivos**: `requirements-dev.txt`
  - **Dependencias**: Ninguna
  - **Criterios relacionados**: FR-006, SC-004, Sp1-06, Principio IV
  - **Tarea F5**: Sp1-06
  - **Estimación**: 25 min (15 min impl + 5 min check + 5 min registro)
  - **Verificación**: `requirements-dev.txt` define exactamente `pytest==8.3.4`, `pytest-asyncio==0.25.3`, `pytest-cov==6.0.0`, `mypy==1.14.1` y `ruff==0.9.6`; `pip install -r requirements-dev.txt` instala las herramientas sin errores en el entorno virtual.

- [x] **T002** [P] Configurar `pyproject.toml` para línea base de compatibilidad Python 3.11+, configuración de Ruff e informe de cobertura de Pytest (Sp1-05)
  - **Archivos**: `pyproject.toml`
  - **Dependencias**: Ninguna
  - **Criterios relacionados**: FR-004, FR-005, SC-005, Sp1-05, Principio III
  - **Tarea F5**: Sp1-05
  - **Estimación**: 30 min (20 min impl + 5 min check + 5 min registro)
  - **Verificación**: `pyproject.toml` define `requires-python = ">=3.11"`, bloque `[tool.ruff]` con inspección de formato (line-length 100, target-version py311) y linter básico, y opciones de cobertura para `pytest-cov` sobre `src/harness_agent/`.

---

## Phase 2: Workflow de CI & Matriz Multiplataforma (Sp1-04 / AC-02)

**Propósito**: Crear la automatización declarativa de GitHub Actions con matriz paralela para Linux y Windows.

- [x] **T003** [US2] Crear workflow declarativo de GitHub Actions en `.github/workflows/ci.yml` con matriz Linux/Windows y Python 3.11/3.12 (Sp1-04 / AC-02)
  - **Archivos**: `.github/workflows/ci.yml`
  - **Dependencias**: T001, T002
  - **Criterios relacionados**: AC-02, FR-001, FR-007, FR-008, SC-001, Sp1-04, Principio IV
  - **Tarea F5**: Sp1-04
  - **Estimación**: 35 min (20 min impl + 10 min check + 5 min registro)
  - **Verificación**: Archivo `.github/workflows/ci.yml` con sintaxis YAML válida; disparadores en `pull_request` y `push` hacia `main`; permisos restringidos a `permissions: contents: read`; matriz configurada con `os: [ubuntu-latest, windows-latest]` y `python-version: ["3.11", "3.12"]`; pasos ordenados: checkout, setup-python, install (con `requirements-dev.txt`), ruff format check, ruff check, mypy strict y pytest con cobertura.

---

## Phase 3: Validación Local de Puertas de Calidad y Pruebas Negativas (AC-01 / Evidencia A)

**Propósito**: Demostrar y comprobar empíricamente que las herramientas de calidad pasan sobre el código limpio y que el pipeline falla de forma determinista ante cualquier defecto introducido.

- [x] **T004** [US1] Ejecutar y validar localmente la suite de calidad (Ruff, Mypy estricto, Pytest con cobertura) sobre el repositorio limpio (AC-01 / Evidencia A)
  - **Archivos**: `pyproject.toml`, `requirements-dev.txt`
  - **Dependencias**: T001, T002, T003
  - **Criterios relacionados**: AC-01, FR-002, FR-003, FR-004, FR-005, SC-003, Sp1-05
  - **Tarea F5**: Sp1-05
  - **Estimación**: 25 min (15 min impl + 5 min check + 5 min registro)
  - **Verificación**: Ejecutar secuencialmente `ruff format --check .`, `ruff check .`, `mypy src tests` y `pytest --cov=harness_agent --cov-report=term-missing`; los 4 comandos devuelven código de salida 0 y las 9 pruebas existentes pasan al 100 %.

- [x] **T005** [US1] Validar el fallo y bloqueo ante una prueba fallida mediante caso de prueba negativo simulado (AC-01)
  - **Archivos**: `tests/contracts/test_contracts.py` (modificación temporal para prueba negativa)
  - **Dependencias**: T004
  - **Criterios relacionados**: AC-01, FR-002, FR-008, SC-002
  - **Tarea F5**: Sp1-05
  - **Estimación**: 25 min (15 min impl + 5 min check + 5 min registro)
  - **Verificación**: Agregar temporalmente una prueba con aserción falsa (`assert False`); ejecutar `pytest` y confirmar que retorna `exit code 1` (fallo explícito); restaurar de inmediato el archivo limpio.

- [x] **T006** [US1] Validar el fallo y bloqueo ante un error de tipos estáticos mediante caso de prueba negativo simulado (AC-01)
  - **Archivos**: `src/harness_agent/core/entities.py` (modificación temporal para prueba negativa)
  - **Dependencias**: T004
  - **Criterios relacionados**: AC-01, FR-003, FR-008, SC-002
  - **Tarea F5**: Sp1-05
  - **Estimación**: 25 min (15 min impl + 5 min check + 5 min registro)
  - **Verificación**: Agregar temporalmente una incompatibilidad de tipos explícita (e.g. `x: int = "texto"`); ejecutar `mypy src tests` y confirmar que retorna `exit code 1` (fallo de tipado); restaurar de inmediato el archivo limpio.

- [x] **T007** [US1] Validar el fallo y bloqueo ante una violación de formateo de código mediante caso de prueba negativo simulado (AC-01)
  - **Archivos**: `src/harness_agent/core/events.py` (modificación temporal para prueba negativa)
  - **Dependencias**: T004
  - **Criterios relacionados**: AC-01, FR-004, FR-008, SC-002
  - **Tarea F5**: Sp1-05
  - **Estimación**: 20 min (10 min impl + 5 min check + 5 min registro)
  - **Verificación**: Introducir espaciado no estándar en un archivo existente; ejecutar `ruff format --check .` y confirmar que retorna `exit code 1` señalando que el archivo requiere reformateo sin haberlo modificado en disco; restaurar de inmediato el archivo limpio.

---

## Phase 4: Verificación Remota, Gobernanza y Registro (Evidencias B y C)

**Propósito**: Separar rigurosamente la validación automatizada de las acciones que requieren credenciales o acceso administrativo al repositorio remoto de GitHub.

- [ ] **T008** [US2] Documentar y verificar la ejecución real del workflow en GitHub Actions para Linux y Windows (AC-02 / Evidencia B)
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: T003, T004, T005, T006, T007
  - **Criterios relacionados**: AC-02, SC-001, SC-003, Sp1-04
  - **Tarea F5**: Sp1-04
  - **Estimación**: 30 min (15 min impl/inspección + 10 min check + 5 min registro)
  - **Verificación**: Confirmar la ejecución remota de los trabajos de la matriz (`ubuntu-latest` y `windows-latest`) en GitHub Actions reportando enlace/ID de ejecución, o documentar explícitamente en `docs/PROGRESO.md` que la ejecución remota queda lista y pendiente de confirmación tras el push a origin.

- [ ] **T009** [US1] Documentar el procedimiento de configuración de Branch Protection Rules en GitHub para el bloqueo efectivo de merge (AC-01 / Evidencia C)
  - **Archivos**: `docs/PROGRESO.md`, `specs/002-ci-testing-formatting/quickstart.md`
  - **Dependencias**: T008
  - **Criterios relacionados**: AC-01, FR-009, SC-006, Principio IX
  - **Tarea F5**: Sp1-04
  - **Estimación**: 25 min (15 min impl + 5 min check + 5 min registro)
  - **Verificación**: Registrar en `quickstart.md` y `docs/PROGRESO.md` los checks obligatorios que el administrador del repositorio debe configurar en GitHub (`Settings -> Branches -> Require status checks to pass before merging`), asegurando la distinción entre el fallo técnico del workflow y la política administrativa de bloqueo de merge.

- [x] **T010** Actualizar `docs/PROGRESO.md` con el estado técnico, evidencias y registro de la historia HU-00-02
  - **Archivos**: `docs/PROGRESO.md`
  - **Dependencias**: T001 a T009
  - **Criterios relacionados**: Principio VIII, Principio IX
  - **Tarea F5**: Sp1-04, Sp1-05, Sp1-06
  - **Estimación**: 20 min (10 min impl + 5 min check + 5 min registro)
  - **Verificación**: Fila de `HU-00-02` en `docs/PROGRESO.md` actualizada con estado, evidencias verificadas (Evidencia A completa, Evidencias B y C documentadas), enlaces a archivos y entrada detallada en la sección *Registro de cambios*.

---

## Dependencias & Orden de Ejecución

```mermaid
flowchart TD
  subgraph Phase 1: Setup
    T001["T001: requirements-dev.txt (Sp1-06)"]
    T002["T002: pyproject.toml ruff & cov (Sp1-05)"]
  end

  subgraph Phase 2: Workflow
    T003["T003: .github/workflows/ci.yml (Sp1-04/AC-02)"]
  end

  subgraph Phase 3: Calidad Local y Fallos Negativos (AC-01)
    T004["T004: Validación local clean pass (Evidencia A)"]
    T005["T005: Prueba negativa test fail (AC-01)"]
    T006["T006: Prueba negativa mypy fail (AC-01)"]
    T007["T007: Prueba negativa format fail (AC-01)"]
  end

  subgraph Phase 4: Remoto y Gobernanza (Evidencias B y C)
    T008["T008: Verificación ejecución remota en GitHub Actions (Evidencia B)"]
    T009["T009: Documentación branch protection rules (Evidencia C)"]
    T010["T010: Sincronización docs/PROGRESO.md"]
  end

  T001 --> T003
  T002 --> T003
  T003 --> T004
  T004 --> T005
  T004 --> T006
  T004 --> T007
  T005 --> T008
  T006 --> T008
  T007 --> T008
  T008 --> T009
  T009 --> T010
```

### Oportunidades de Paralelización:
- **T001** y **T002** son paralelizables (`[P]`) porque afectan archivos distintos sin dependencias mutuas.
- **T005**, **T006** y **T007** son verificaciones negativas independientes que pueden ejecutarse de forma secuencial o paralela tras verificar la línea base limpia en **T004**.

---

## Estrategia de Implementación

1. **Fijación de cimientos (T001–T002)**: Configurar primero las herramientas deterministas y los estándares de calidad locales.
2. **Definición del pipeline (T003)**: Escribir el workflow declarativo multi-OS con mínimos privilegios.
3. **Verificación empírica local (T004–T007)**: Ejecutar suite limpia y pruebas destructivas/negativas para certificar que el pipeline realmente falla ante errores de pruebas, tipado o formato.
4. **Verificación remota y gobernanza (T008–T010)**: Validar la ejecución remota y documentar la protección de ramas en GitHub, actualizando `docs/PROGRESO.md`.

---

## Resumen de Estimaciones

| Tarea | Descripción breve | Tiempo Impl. | Tiempo Check | Tiempo Reg. | Total |
|---|---|---|---|---|---|
| **T001** | `requirements-dev.txt` con versiones fijadas | 15 min | 5 min | 5 min | 25 min |
| **T002** | `pyproject.toml` con baseline 3.11+, ruff y cobertura | 20 min | 5 min | 5 min | 30 min |
| **T003** | Workflow `.github/workflows/ci.yml` con matriz Linux/Windows | 20 min | 10 min | 5 min | 35 min |
| **T004** | Validación local suite limpia (Ruff, Mypy, Pytest cov) | 15 min | 5 min | 5 min | 25 min |
| **T005** | Prueba negativa: fallo simulado de Pytest | 15 min | 5 min | 5 min | 25 min |
| **T006** | Prueba negativa: error simulado de Mypy | 15 min | 5 min | 5 min | 25 min |
| **T007** | Prueba negativa: violación simulada de Ruff | 10 min | 5 min | 5 min | 20 min |
| **T008** | Verificación remota GitHub Actions (Evidencia B) | 15 min | 10 min | 5 min | 30 min |
| **T009** | Documentación Branch Protection Rules (Evidencia C) | 15 min | 5 min | 5 min | 25 min |
| **T010** | Sincronización y cierre en `docs/PROGRESO.md` | 10 min | 5 min | 5 min | 20 min |
| **Total** | **10 microtareas acotadas** | **150 min** | **65 min** | **45 min** | **260 min (~4.3 h)** |
