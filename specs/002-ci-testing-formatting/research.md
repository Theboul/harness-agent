# Technical Research & Decisions: HU-00-02 (CI Pipeline)

## Decision 1: CI Platform and Workflow Engine

- **Decision**: GitHub Actions (`.github/workflows/ci.yml`).
- **Rationale**: The project remote is hosted on GitHub (`https://github.com/Theboul/harness-agent.git`). GitHub Actions provides native integration with GitHub Pull Requests, branch protection rulesets, status checks, and hosted runners for both Linux and Windows without third-party webhooks or external infrastructure overhead.
- **Alternatives considered**:
  - *GitLab CI / Bitbucket Pipelines*: Rejected because the repository is on GitHub.
  - *Local pre-commit hooks alone*: Rejected because client-side hooks can be bypassed (`--no-verify`) and do not enforce server-side pull request gating or multiplatform execution across Windows and Linux.

## Decision 2: Multiplatform Matrix and Python Version Support

- **Decision**: Matrix strategy with `os: [ubuntu-latest, windows-latest]` and `python-version: ["3.11", "3.12"]`.
- **Rationale**:
  - Satisfies **AC-02** ("Dado el pipeline, cuando corre, entonces ejecuta en Linux y Windows").
  - Adheres to the user's requirement to establish Python 3.11 as the baseline compatibility target while preserving compatibility with Python 3.12 (the team's primary active development version).
  - Ensures path handling (POSIX vs Windows backslashes), process execution, and line ending differences (`LF` vs `CRLF`) are detected automatically on both operating systems.
- **Alternatives considered**:
  - *Single OS (Ubuntu only)*: Rejected because AC-02 explicitly demands both Linux and Windows, and team members work in Windows and Linux environments.
  - *Python 3.14 alpha/beta*: Rejected as unstable; 3.11 and 3.12 provide stable production and development environments.

## Decision 3: Pinned Dependencies and Reproducibility Strategy (Sp1-06)

- **Decision**: Dual manifest strategy:
  1. `pyproject.toml` declares permissive abstract ranges (`>=`) for package distribution metadata.
  2. `requirements-dev.txt` defines concrete, exact pinned versions (`==`) for all test, lint, format, and type-checking tools used in CI and local development.
  3. Installation command in CI: `python -m pip install --upgrade pip` followed by `pip install -r requirements-dev.txt` and `pip install -e . --no-deps`.
- **Rationale**: Ensures that every CI run on both Linux and Windows resolves identical package hashes and versions, eliminating "works on my machine" issues caused by transient upstream releases of dependencies.
- **Pinned Development Toolset**:
  - `pytest==8.3.4`
  - `pytest-asyncio==0.25.3`
  - `pytest-cov==6.0.0`
  - `mypy==1.14.1`
  - `ruff==0.9.6`
- **Alternatives considered**:
  - *`pip-tools` / `uv.lock` / `poetry.lock`*: Rejected for Sprint 1 to keep tooling minimal and avoid introducing additional package managers or heavy external lockfile workflows. A standard `requirements-dev.txt` provides 100% reproducibility across OSs with standard `pip`.
  - *Unpinned installation directly from `pyproject.toml`*: Rejected because it violates Sp1-06 and produces non-deterministic builds.

## Decision 4: Code Quality, Formatting and Coverage Tools (Sp1-05)

- **Decision**:
  - **Unit & Contract Testing**: `pytest` + `pytest-asyncio` (reusing existing setup in `pyproject.toml`).
  - **Coverage Reporting**: `pytest-cov`, invoked via `pytest --cov=harness_agent --cov-report=term-missing`.
  - **Static Type Checking**: `mypy --strict` targeting `src/` and `tests/` (reusing configuration in `pyproject.toml`).
  - **Formatting & Linting**: `ruff` executed in read-only inspection mode:
    - Format check: `ruff format --check .` (does not modify code in CI, exits with non-zero if code needs formatting).
    - Linter check: `ruff check .`
- **Rationale**: `ruff` is written in Rust, executes in milliseconds, supports both formatting and linting, and is explicitly recognized in Principle IV of the HARNESS Constitution. `pytest-cov` satisfies Sp1-05 with minimal footprint.
- **Alternatives considered**:
  - *`black` + `flake8` + `isort`*: Rejected because `ruff` replaces all three with a single unified binary that is 10-100x faster and requires no conflicting configuration files.
  - *Auto-formatting during CI*: Rejected; CI must fail and alert developers rather than silently modifying source code in the runner.

## Decision 5: CI Security, Least Privilege and Triggers

- **Decision**:
  - Permissions: Set `permissions: contents: read` at the top level of the workflow.
  - Secrets: Zero repository or environment secrets referenced in the CI workflow.
  - Triggers:
    - `pull_request: branches: [main]`
    - `push: branches: [main]`
- **Rationale**: Adheres to the principle of least privilege, preventing token exposure or unauthorized write access to repository contents.

## Decision 6: Rigorous Distinction of Verification Evidences

- **Decision**: Formally separate and document three tiers of evidence:
  - **Evidence A (Local Validation)**: Execution of all checks locally via shell commands (`ruff format --check`, `ruff check`, `mypy`, `pytest --cov`) on both clean and intentionally broken code, verifying correct exit codes.
  - **Evidence B (GitHub Actions Runner Execution)**: Successful live execution of matrix jobs on GitHub Actions (`ubuntu-latest` and `windows-latest`), confirmed with run ID and URL.
  - **Evidence C (Branch Protection Enforcement)**: Verification that GitHub branch protection rules require the CI status checks to pass before pull requests can be merged into `main`.
- **Rationale**: Prevents conflating local workflow syntax validity with actual remote runner execution or GitHub branch protection enforcement.
