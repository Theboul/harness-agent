# Quickstart & Verification Guide: HU-00-02 (CI Pipeline)

> Actualizado por PD-07 (2026-10-17, Product Owner): Python 3.12.x es la única versión soportada; la matriz vigente de CI es `ubuntu-latest` y `windows-latest` con Python 3.12 (2 jobs). Los textos sobre Python 3.11 y la matriz de 4 jobs describen el diseño original y quedan como historial; los criterios de aceptación no cambian.

This guide documents how to execute and verify the quality checks locally, test negative failure cases, and validate the three tiers of evidence (Evidence A, B, and C).

---

## 1. Local Environment Setup

### 1.1 Install Pinned Dependencies

Ensure the virtual environment is activated, then install pinned dependencies:

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements-dev.txt
.\.venv\Scripts\pip.exe install -e . --no-deps
```

**Linux (Bash):**
```bash
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
pip install -e . --no-deps
```

---

## 2. Running Local Quality Gates (Evidence A)

Run the exact check sequence used by CI:

### Step 1: Code Formatting & Linting (Ruff)
```bash
# Check code formatting (read-only)
ruff format --check .

# Run linter
ruff check .
```
- **Expected Outcome**: Exit code 0, no unformatted files, no lint violations.

### Step 2: Static Type Checking (Mypy)
```bash
mypy src tests
```
- **Expected Outcome**: Exit code 0, `Success: no issues found in 26 source files`.

### Step 3: Automated Tests & Coverage (Pytest)
```bash
pytest --cov=harness_agent --cov-report=term-missing
```
- **Expected Outcome**: Exit code 0, 9/9 tests passed, terminal coverage report emitted for `src/harness_agent/`.

---

## 3. Negative Failure Scenarios (AC-01 Verification)

To prove that the pipeline reliably blocks integration when defects are introduced:

### Scenario 1: Failing Test Simulation
1. Temporarily add an intentional failing assertion in `tests/contracts/test_contracts.py`:
   ```python
   def test_intentional_failure():
       assert False, "Simulated test failure"
   ```
2. Execute `pytest`:
   - **Expected**: Process exits with code 1 (`FAILED`).

### Scenario 2: Type Error Simulation
1. Temporarily add a type violation in any test or source file:
   ```python
   x: int = "string_mismatch"
   ```
2. Execute `mypy src tests`:
   - **Expected**: Process exits with code 1 (`Incompatible types in assignment`).

### Scenario 3: Formatting Error Simulation
1. Introduce an unformatted line (e.g. `x =    [ 1,2, 3 ]`) in a tracked file.
2. Execute `ruff format --check .`:
   - **Expected**: Process exits with code 1 (`1 file would be reformatted`).

*Note*: Revert all test modifications before committing (`git checkout -- .`).

---

## 4. Verification Evidence Protocol

### Evidence A: Local Validation
- [ ] `ruff format --check .` passes on clean code.
- [ ] `ruff check .` passes on clean code.
- [ ] `mypy src tests` passes on clean code.
- [ ] `pytest --cov=harness_agent --cov-report=term-missing` passes 9/9 tests with coverage report.
- [ ] Negative test proving non-zero exit code on failing test.
- [ ] Negative test proving non-zero exit code on type mismatch.
- [ ] Negative test proving non-zero exit code on format mismatch.

### Evidence B: GitHub Actions Runner Execution
- [ ] Workflow pushed to remote repository on branch `002-ci-testing-formatting`.
- [ ] Run triggered automatically on GitHub Actions.
- [ ] Matrix jobs run concurrently on `ubuntu-latest` and `windows-latest` on Python 3.12 (PD-07; originally 3.11 and 3.12).
- [ ] Both matrix combinations pass after PD-07 (`quality (ubuntu-latest, py3.12)`, `quality (windows-latest, py3.12)`). Historical: Run 39087285626 passed the original 4-job matrix (py3.11 and py3.12); the 2-job matrix has not run remotely yet.
- [ ] Run URL and commit SHA recorded in `docs/PROGRESO.md`.

### Evidence C: Branch Protection Rule Verification
- [ ] In GitHub repository settings (`Settings -> Branches`), branch protection rule or ruleset exists for `main`.
- [ ] "Require status checks to pass before merging" is enabled.
- [ ] Matrix check names (e.g., `quality (ubuntu-latest, py3.12)`, `quality (windows-latest, py3.12)`) are selected as required.
- [ ] Pull request with simulated failure displays merge button blocked by GitHub.
