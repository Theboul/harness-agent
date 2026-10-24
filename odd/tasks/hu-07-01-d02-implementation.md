# ODD: HU-07-01 D-02 implementation (Conversion Envelope + Metadata Sidecar)

- Feature: hu-07-01-d02-implementation
- Engram mirror topic: `odd/hu-07-01-d02-implementation/tasks`
- Route: delegated direct (single writer); executed inline by the worker fork
- TDD: ON (source: explicit user directive), runner: `.venv/Scripts/python.exe -m pytest`
- Authorization: implementation granted by the Product Owner (collective team consensus communicated 2026-10-18). Not individual approval of D-02 by A, B, C. Not story closure.

## Objective
Resolve D1 (`is_external`), D2 (`ToolResult.is_error` with OpenAI), D8 (`Message.usage`), D9 (TOOL content) via `to_*_envelope` / `restore_messages` in `src/harness_agent/adapters/converters/`, without touching `core/`.

## Constraints
No changes to `Message`, `ToolResult`, `Provider`, `ProviderResponse`, `core/`, constitution, AC wording, HU-07-02. No provider SDK/litellm, no network, no commits/push/PR, no `/speckit.converge`. SPK-01 stays Pendiente (needs real providers). T018 annotated, not ticked. T016/D-01 pending.

## Tasks
- [x] T019 envelope types, strict JSON snapshot, digests, matches (tests/adapters/test_envelope_types.py, RED observed first)
- [x] T020 OpenAI envelope + restore (D1, D2, D8, D9, correlation, partial_window)
- [x] T021 Anthropic envelope + restore (WireRef coverage, empty SYSTEM omitted + sidecar)
- [x] T022 security + concurrency tests, 28 D-02 scenarios (test_envelope_security.py, test_envelope_roundtrip.py)
- [x] T023 pending D1/D2 tests converted to preservation tests; AC-01 sweep; docs
- [x] T024 DeprecationWarning on from_openai_messages / from_anthropic_payload (RED observed first)
- [x] DOCS D-02 v4, spec, plan, data-model, contract, tasks.md, PROGRESO.md
- [x] VALIDATION Windows + WSL2; SPK-01 status check (stays Pendiente, no simulation)

## Progress / evidence
- Baseline: 253 passed, 5 skipped. Final Windows (3.12.10): 385 passed, 5 skipped; mypy 47 files clean; ruff check/format clean.
- WSL2 Ubuntu (3.12.15): 390 passed; mypy/ruff clean.
- `git status`: no change under `src/harness_agent/core/`, `tests/contracts/`, `pyproject.toml`, `requirements-dev.txt`.
- Probe `probe_envelope.py`: D1/D2/D8/D9 + empty SYSTEM lossless for both providers; no local field leaks into payloads.
- Route evidence: inline execution (worker fork), no delegation.

## Next step
Human review: individual technical approvals of D-02 by A, B, C (T018), T016, D-01, SPK-01 by B. No commits made.
