# ODD: spk-02-convergence

**Objective**: Correct and converge SPK-02 (async model and tool cancellation spike) after the technical audit, without rebuilding the spike or widening its scope.
**Spec**: `specs/003-async-cancellation-spike/spec.md` · **Decision doc**: `docs/decisiones/D-01-asyncio-cancelacion.md`
**Route**: delegated writer (single writer), inline reads · **TDD**: off (source: not configured; ordinary functional checks) · **Runner**: `.venv/Scripts/python.exe -m pytest` (Python 3.12.10, Windows)
**Delivery exception**: the user forbade commits, push, merge and PRs for this phase, so no work-unit commits are made. Evidence below is test output, not commit ids.
**Mirror**: Engram topic `odd/spk-02-convergence/tasks` (status below).

## Scope
In: spec/plan/research/data-model/quickstart/contract/tasks docs of 003, D-01, PROGRESO, `tests/spikes/`.
Out: `src/harness_agent/core/` contracts, `pyproject.toml`, `docs/archivo/`, other stories, HU-06-03.

## Checklist
- [x] **T006** Fix contract signatures (Provider/Tool/Approver) and V-14 references in spec, plan, research, D-01
- [x] **T007** Refactor spike cancellation: ProcessLike protocol, two-phase algorithm, cleanup robust to a second cancel, optional re-raise mode
- [x] **T008** Add edge-case tests (cancel before start, finish before cancel, terminate ignored, escalation, cancel during cleanup, no live PIDs, loop liveness, FAILED state)
- [x] **T009** Add alternatives experiments (asyncio vs threads vs processes) and record real measurements
- [x] **T010** Rewrite comparison in research.md and D-01 with measured evidence (US2 / FR-007)
- [x] **T011** Platform and resource evidence section (Windows real / Linux pending / doubles) and limit the descriptor claim
- [x] **T012** Python 3.11+ vs 3.12+ conflict recorded as pending governance decision
- [x] **T013** Documentation consistency (link, blank line, timings, statuses, stale references)
- [x] **T014** Final validation and sync of tasks.md / PROGRESO.md
- [x] **T016** Linux validation in WSL2 Ubuntu (local, not a GitHub Actions runner): real SIGTERM-ignoring child test, SIGKILL escalation, repeated cancels, leftover-process check, docs updated (spec 003 T016, not HU-00-01 T016)

## Acceptance
AC-01 still evidenced; US2/FR-007 covered by a verifiable comparison; D-01 stays PENDIENTE DE APROBACIÓN; SPK-02 stays "En revisión".

## Progress / evidence
- T006-T014 completed. Route: inline reads + single delegated writer (this fork); no work-unit commits (user forbade commits for this phase).
- Final validation (Windows 10, Python 3.12.10): full pytest 35 passed; mypy strict src+tests no issues (29 files); ruff format --check and ruff check clean; each of the 26 spike tests passes individually; spike suite repeated 5x without failures.
- AC-01: cancel -> control back in 1.0/1.4/2.4 ms (min/median/max, n=10), PID gone, exit code 1.
- US2/FR-007: comparison measured (5 runs) and recorded in research.md section 3 and D-01 section 3.
- Pending (not done): GitHub Actions run (nothing pushed), human approval of D-01 by A/B/C (depends on HU-00-01 T016).
- D-01: PENDIENTE DE APROBACION. SPK-02: En revision.
- Engram mirror: created at start; final update pending/see below.

- Update (2026-10-17): PD-07 approved by the Product Owner (Python 3.12.x only); the governance item is closed and Python 3.11 is no longer pending. See `odd/tasks/pd-07-python-312.md`.

- Update (2026-10-17, T016): Linux validated in WSL2 Ubuntu 26.04.1 (local, CPython 3.12.15, kernel 6.18.54.1-microsoft-standard-WSL2; NOT a GitHub Actions runner). New `tests/spikes/test_linux_sigterm_spike.py` (5 Linux-only tests). WSL2: spike 31 passed (5 consecutive runs), full suite 40 passed in 10.48 s (exit 0), mypy no issues (30 files), ruff check/format clean. Windows: 35 passed, 5 skipped in 8.84 s, mypy and ruff clean. SIGTERM-ignoring child: returncode -9, control back at 151.6 ms (150 ms grace), 3 cancels during a 300 ms grace -> 2 absorbed, -9, 303.0 ms; timeout 0.4 s -> TIMEOUT, -9, 553.4 ms; 5 cycles -> [-9]*5, no live/zombie PIDs. Cooperative child (probe, n=10): 0.7/1.0/1.4 ms, returncode -15. fd count 8 -> 8 over 5 cycles. No spike defects found. D-01 stays PENDIENTE DE APROBACIÓN, technically ready for A/B/C review (approval block unchecked). SPK-02: En revisión. No commits.
