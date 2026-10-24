# ODD: contract-naming-english

**Objective**: standardize contract naming in English: `AreaAutorizada` -> `AuthorizedArea` and the 17 `EventType` members/values; prepare (not perform) closure of HU-00-01, HU-00-02 and SPK-02.
**Date**: 2026-10-18 · **Route**: delegated writer (single writer) · **TDD**: off (functional checks) · **Runner**: `.venv/Scripts/python.exe -m pytest`
**Commit exception**: the user forbids commits/push/merge; no work-unit commits are made in this phase.
**Scope**: rename in src/, tests/, active docs/, specs/001-003, skills copies. Out of scope: pyproject, constitution, PD-07, docs/archivo/, new stories.

## Tasks
- [x] N01 Inspect references and persisted data using old strings
- [x] N02 Rename AreaAutorizada -> AuthorizedArea (code, exports, doubles, tests)
- [x] N03 Rename the 17 EventType members/values (code, tests)
- [x] N04 Compatibility decision (persisted data evidence)
- [x] N05 Update active docs/specs/skills
- [x] N06 Governance: record communicated decision, keep approvals pending
- [x] N07 Validation (Windows + WSL2) and leftover grep

## Evidence
- Persisted data inspected: no SQLite/JSON/JSONL event data, no serialization code, no SessionStore implementation -> no migration or legacy mapping added (decision documented in PROGRESO 2026-10-18).
- Windows (Python 3.12.10): 58 passed, 5 skipped (Linux-only); mypy 32 files clean; ruff check and format --check clean.
- WSL2 Ubuntu (Python 3.12.15): 63 passed; mypy, ruff clean; no leftover experiment processes.
- Leftover old names: constitution (needs amendment procedure), docs/06 (historical), PROGRESO/revision-conjunta history entries, one negative test asserting the old value is rejected.
- Governance: communicated collective decision recorded; T016, D-01, per-person approvals remain pending; nothing marked Completada.
- Engram mirror: saved at start (observation 11); final status not re-mirrored beyond that.
