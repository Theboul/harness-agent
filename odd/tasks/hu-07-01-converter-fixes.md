# ODD: hu-07-01-converter-fixes

**Objective**: correct audited defects 3–7 in the HU-07-01 provider converters and align documentation, without changing acceptance criteria.
**Route**: delegated writer (single writer). **TDD**: ON (source: user instruction "cada defecto debe incluir una prueba de regresión que falle antes"), runner `.venv/Scripts/python.exe -m pytest`.
**Commits**: none. Exception recorded: the user forbids commits/push/merge in this phase.
**Out of scope**: defects 1 and 2 (`is_external` lost; `is_error` lost in OpenAI), `core/` contracts, constitution, pyproject, HU-07-02.

## Checklist
- [x] T010 Regression tests written first (red evidence captured)
- [x] T011 D3 JSON-object arguments (shared helper)
- [x] T012 D4 Anthropic payload: no silent drops, unknown blocks rejected
- [x] T013 D5 ToolResult.content must be str
- [x] T014 D6 system messages preserved (Anthropic block list) / ConversionError when not representable
- [x] T015 D7 ConversionError normalization for invalid external payloads
- [x] T016 Docs: PROGRESO, spec 004 (links, status, limitations), tasks, contract, data-model
- [x] T017 Validation: HU-07-01 tests, full suite, mypy, ruff check, ruff format --check, probe before/after

## Progress / evidence
- Red (code before fixes, 130 regression tests): 99 failed, 31 passed (positive/control cases). Later +3 tests (text after tool_use, pending D1, pending D2).
- Green: tests/adapters + tests/contracts/test_provider_interchangeability.py = 148 passed (133 regression + 13 + 2).
- Full suite Windows (3.12.10): 206 passed, 5 skipped. WSL2 Ubuntu (3.12.15): 211 passed. mypy src tests: 40 files clean. ruff check / format --check: clean.
- core/ untouched; no vendor imports in core/. Probe script: D3-D7 now raise ConversionError; D1/D2 still reproduce (pending, T018 in specs/004/tasks.md).
- Design decisions: D4 mixed tool_result+text => ConversionError (canonical model cannot keep grouping); D6 Anthropic system as block list when several, ConversionError for non-leading/empty system.
- Pending for owners: docstring in core/interfaces/provider.py still says async signatures provisional pending SPK-02 (shared contract, not edited).
- Commits: none (user forbids).
