# Implementation Plan: HU-00-02 — Integración continua con pruebas, tipado y formato

> Actualizado por PD-07 (2026-10-17, Product Owner): Python 3.12.x es la única versión soportada; la matriz vigente de CI es `ubuntu-latest` y `windows-latest` con Python 3.12 (2 jobs). Los textos sobre Python 3.11 y la matriz de 4 jobs describen el diseño original y quedan como historial; los criterios de aceptación no cambian.

**Branch**: `002-ci-testing-formatting` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-ci-testing-formatting/spec.md`

## Summary

Implement a minimal, reproducible, and secure Continuous Integration (CI) pipeline using GitHub Actions that enforces quality gates across both Linux (`ubuntu-latest`) and Windows (`windows-latest`) on Python 3.12 (the only supported version, PD-07). The pipeline executes automated tests (`pytest` + `pytest-asyncio`), code coverage reporting (`pytest-cov`), strict static type checking (`mypy --strict`), and non-modifying code formatting & linting (`ruff format --check` and `ruff check`). Deterministic builds are guaranteed through pinned dependency specifications in `requirements-dev.txt`, while preserving `pyproject.toml` abstract dependencies.

## Technical Context

**Language/Version**: Python 3.12.x only (PD-07, 2026-10-17; originally 3.11 baseline plus 3.12).

**Primary Dependencies**:
- Core: None (`dependencies = []` in `pyproject.toml`).
- Development & CI Tools: `pytest==8.3.4`, `pytest-asyncio==0.25.3`, `pytest-cov==6.0.0`, `mypy==1.14.1`, `ruff==0.9.6` pinned in `requirements-dev.txt`.

**Storage**: N/A for this infrastructure and quality feature.

**Testing**: `pytest` running with `pytest-asyncio` and `pytest-cov`, executing in-memory doubles and unit tests without external network access.

**Target Platform**: GitHub Actions hosted runners (`ubuntu-latest` and `windows-latest`).

**Project Type**: Autonomous agent harness library and CLI application with Hexagonal Architecture.

**Performance Goals**: Complete pipeline execution in under 5 minutes per runner matrix job.

**Constraints**:
- Read-only code inspection: `ruff format --check` and `ruff check` must never modify files in CI.
- Multiplatform parity: Tests and static analysis must pass identically on Windows and Linux (AC-02).
- Security: Minimum permissions (`permissions: contents: read`), zero secrets in workflow files.
- Rigorous evidence separation: Local validation (Evidence A), GitHub Actions matrix run (Evidence B), and remote branch protection rules (Evidence C).
- Microtask scope: All subsequent implementation tasks sized at 15–40 minutes (maximum 60 minutes).

**Scale/Scope**: 2 PHU, Sprint 1, HU-00-02 (Foundation & Quality Epic E0).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle / Gate | Compliance Analysis | Status |
|---|---|---|
| **Principio I: Una HU por especificación** | Aborda exclusivamente HU-00-02 (Integración continua con pruebas, tipado y formato). | **PASS** |
| **Principio II: Microtareas acotadas (<60 min)** | Tareas diseñadas para completarse en 15–40 minutos cada una (Sp1-04, Sp1-05, Sp1-06). | **PASS** |
| **Principio III: Python 3.12.x, modular y desacoplado** | Python 3.12.x como única versión (PD-07; antes 3.11 baseline y 3.12 dev); cero dependencias de producción en el núcleo. | **PASS** |
| **Principio IV: Pruebas, calidad y CI multiplataforma** | Pipeline obligatorio en Windows y Linux con `pytest`, `mypy` estricto y `ruff`. | **PASS** |
| **Principio V: Inmutabilidad de AC y prioridades** | AC-01 y AC-02 se preservan literalmente; prioridad Alta no alterada. | **PASS** |
| **Principio VI: Disciplina de sprints** | Alcance restringido al Sprint 1 (Fundaciones); sin adelantar historias futuras. | **PASS** |
| **Principio VII: Consulta documental quirúrgica** | Basado exclusivamente en fuentes vigentes (`00-indice`, `01`, `03`, `04a`, `05`, `PROGRESO.md`). | **PASS** |
| **Principio VIII: Registro en docs/PROGRESO.md** | Progreso y evidencias A, B y C se registrarán en `docs/PROGRESO.md`. | **PASS** |
| **Principio IX: DoD estricta y verificación humana** | Evidencia A comprobada localmente; evidencia B verificada en remoto; evidencia C sujeta a gobernanza humana. | **PASS** |
| **Principio X: Inmutabilidad de docs/archivo/** | Ningún archivo histórico en `docs/archivo/` es modificado. | **PASS** |

## Project Structure

### Documentation (this feature)

```text
specs/002-ci-testing-formatting/
├── spec.md              # Feature specification
├── plan.md              # Master technical implementation plan
├── research.md          # Phase 0: Technical decisions & trade-offs
├── data-model.md        # Phase 1: CI subsystem data model & state machine
├── quickstart.md        # Phase 1: Local reproduction, negative tests & evidence guide
├── contracts/           # Phase 1: Interface contracts & schemas
│   └── ci-workflow-contract.md
├── checklists/          # Quality validation checklists
│   └── requirements.md
└── tasks.md             # Phase 2: Actionable microtasks (< 60 min each, via /speckit-tasks)
```

### Source Code & Configuration (repository root)

```text
.github/
└── workflows/
    └── ci.yml           # Declarative GitHub Actions matrix workflow (Linux & Windows)

requirements-dev.txt     # Pinned exact versions for test, lint, format and type checking

pyproject.toml           # Packaging metadata, pytest and mypy configurations

src/
└── harness_agent/       # Existing decoupled package (pure core)

tests/
├── architecture/        # AST boundary verification tests
├── contracts/           # Contract conformity tests
└── doubles/             # In-memory test doubles
```

**Structure Decision**: Standard GitHub Actions workflow file under `.github/workflows/ci.yml`, paired with a dedicated `requirements-dev.txt` for pinned tool resolution and existing `pyproject.toml` tool configuration.

## Complexity Tracking

*No constitutional violations or unjustified complexity detected.*

| Aspect | Decision | Trade-off / Rationale |
|---|---|---|
| Dependency Pinning | `requirements-dev.txt` | Avoids heavy lockfile managers for Sprint 1 while ensuring 100% deterministic CI installation. |
| Formatting & Linting | `ruff` (unified) | Replaces separate black, flake8, and isort setups with a single, fast binary. |
| Multiplatform Matrix | `ubuntu-latest` + `windows-latest` | Satisfies AC-02 directly with standard GitHub Actions runners. |

## Implementation Roadmap (Tasks Preview)

The work will be decomposed into small, dependency-ordered microtasks (< 60 min each):
1. **T001 (Sp1-06)**: Generate `requirements-dev.txt` with pinned versions (`pytest`, `pytest-asyncio`, `pytest-cov`, `mypy`, `ruff`) and update `pyproject.toml` compatibility baseline (`>=3.12,<3.13` after PD-07; originally `>=3.11`).
2. **T002 (Sp1-05)**: Configure `ruff` in `pyproject.toml` (target Python 3.12 after PD-07, originally 3.11; line length, format and lint rules) and add coverage settings for `pytest-cov`.
3. **T003 (Sp1-04)**: Create declarative GitHub Actions workflow `.github/workflows/ci.yml` with matrix (`ubuntu-latest`, `windows-latest`, Python 3.12 after PD-07, originally 3.11/3.12) and least privilege permissions.
4. **T004 (AC-01/Evidence A)**: Execute local verification suite (Ruff format, Ruff check, Mypy strict, Pytest with coverage) and execute negative failure tests (simulated test failure, typing error, formatting violation).
5. **T005 (AC-02/Evidence B & C)**: Validate remote GitHub Actions execution on Windows and Linux, document branch protection configuration requirements, and synchronize `docs/PROGRESO.md`.
