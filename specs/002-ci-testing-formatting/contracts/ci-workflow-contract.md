# Contracts & Interface Specifications: HU-00-02 (CI Pipeline)

## 1. GitHub Actions Workflow Contract: `.github/workflows/ci.yml`

The CI workflow must adhere to the following declarative schema and step contract:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  test:
    name: quality (${{ matrix.os }}, py${{ matrix.python-version }})
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]
        python-version: ["3.11", "3.12"]

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: "pip"

      - name: Install dependencies (pinned)
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt
          pip install -e . --no-deps

      - name: Check code formatting (ruff)
        run: ruff format --check .

      - name: Lint codebase (ruff)
        run: ruff check .

      - name: Static type checking (mypy)
        run: mypy src tests

      - name: Execute test suite with coverage (pytest)
        run: pytest --cov=harness_agent --cov-report=term-missing
```

### Invariants:
1. **Runner Independence**: Every step must run natively without OS-specific shell wrappers (using standard multiplatform actions/setup-python and cross-platform python/pytest/mypy/ruff CLIs).
2. **Permissions**: Top-level `permissions` block must be strictly limited to `contents: read`.
3. **No Secrets**: No `secrets.*` tokens or environment credentials may be passed into steps.
4. **Failure Signal**: Any step failure must terminate the step with a non-zero exit code (`exit code != 0`).

---

## 2. Pinned Development Manifest Contract: `requirements-dev.txt`

The pinned dependencies file must contain exact version specifiers (`==`) for all test, lint, and formatting tools:

```text
# Pinned development dependencies for HARNESS v2.5 CI and local quality gates
# Generated for reproducible builds on Windows and Linux (Python 3.11+)

pytest==8.3.4
pytest-asyncio==0.25.3
pytest-cov==6.0.0
mypy==1.14.1
ruff==0.9.6
```

---

## 3. Local Verification Command Interface

Developers and CI runners must execute the identical sequence of quality commands to verify code:

| Quality Gate | Exact Command | Success Condition | Failure Condition |
|---|---|---|---|
| **Format Check** | `ruff format --check .` | Returncode 0 (all files formatted) | Returncode 1 (1+ files need formatting) |
| **Linter Check** | `ruff check .` | Returncode 0 (no lint errors) | Returncode 1 (lint violations found) |
| **Type Check** | `mypy src tests` | Returncode 0 (`Success: no issues found`) | Returncode 1 (type mismatches detected) |
| **Test & Coverage** | `pytest --cov=harness_agent --cov-report=term-missing` | Returncode 0 (all tests pass) | Returncode 1 (1+ tests fail or error) |
