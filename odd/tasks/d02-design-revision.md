# ODD: d02-design-revision

**Objective**: revise `docs/decisiones/D-02-preservacion-metadatos-conversion.md` (v1 -> v2) so it can be reviewed by A, B and C. Documentation only.
**Route**: delegated writer (fork). TDD: not applicable (no code). Runner for sanity checks: `.venv/Scripts/python.exe -m pytest`.
**Authorized scope**: D-02 document, one registry entry in `docs/PROGRESO.md`, this file. No `src/`, `tests/`, `core/`, specs, constitution or acceptance criteria. No commits/push/merge (user restriction).

## Checklist
- [x] T1 Read context (constitution, docs 01/02/04d, PROGRESO, specs/004, core entities/provider, converters, tests, D-01, SPK-01) and list the real public API
- [x] T2 Envelope identity (restore_messages(envelope), real guarantees, alternatives)
- [x] T3 Anthropic correspondence (WireRef model, role table, worked example)
- [x] T4 API compatibility (A canonical->payload, B exact restoration, C new responses; migration of payload-only from_*_messages)
- [x] T5 Immutability (strict-JSON snapshot, defensive copy, digest timing)
- [x] T6 Tool correlation (complete vs partial window)
- [x] T7 D4/D6 wording (D6 stays a pending non-compliance)
- [x] T8 D8/D9 storage and restoration
- [x] T9 Test plan (16 existing + 12 new, with input/expected/risk/success)
- [x] T10 Rewrite sections 4-12, add revision history and proposed T024
- [x] T11 Final consistency audit
- [x] T12 PROGRESO registry entry

## Status rules
D-02 stays PROPUESTA — PENDIENTE DE APROBACIÓN. HU-07-01 stays En revisión. T018 unchecked, T019–T023 unimplemented.

## Evidence
Audit (2026-10-18): D-02 v2 written; no file:/// or absolute links; anchors HU-02-02/03/04/05 and HU-03-04 exist; all existing function/class names found in adapters/converters; proposed names (restore_messages, to_provider_envelope, ConversionEnvelope, WireRef, MessageMeta, EnvelopeConverter) absent from src (expected); T018 unchecked; pytest sanity 206 passed, 5 skipped; git status shows no src/ or tests/ changes by this task. Engram mirror saved (topic odd/d02-design-revision/tasks); a conflict review with 3 unrelated candidates is left pending.
