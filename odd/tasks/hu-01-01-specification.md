# ODD: hu-01-01-specification

**Objective**: draft the specification (WHAT/WHY only) of HU-01-01 — Basic agent loop (RF-1.1, RF-1.5) under `specs/005-basic-agent-loop/`, with a documentation-quality checklist.
**Route**: delegated writer (single writer, fork). **TDD**: not applicable (documentation only).
**Commits**: none (not authorized in this phase). **Out of scope**: code, plan.md, tasks.md, clarify, any change to `core/`, original acceptance criteria wording.

## Checklist
- [x] T1 Research: constitution, docs 02/03/04a/04d/05/PROGRESO, real contracts in `core/`, converter canonical rules
- [x] T2 `specs/005-basic-agent-loop/spec.md`
- [x] T3 `specs/005-basic-agent-loop/checklists/requirements.md` validated (max 3 iterations)
- [x] T4 `.specify/feature.json` updated
- [x] T5 `docs/PROGRESO.md` registry entry (no status change of HU-01-01)

## Progress / evidence
- Numbering sequential (`init-options.json`); next free number = 005.
- spec.md: 34 FR, 10 SC, 6 user stories, 29 scenarios, 16 edge cases, 1 [NEEDS CLARIFICATION] (FR-028).
- Checklist: 23/24 items ok; CHK005 open because of the FR-028 marker. Commits: none.

## Clarify progress (2026-10-18)
- [x] C1 `/speckit-clarify` integrated into spec.md: Q1 FR-028 (PO approved, option B), Q2 multiple tool_calls (PO approved, option A), Q3 APPROVAL_* not emitted (derived), Q4 emit() exceptions propagate (derived; pending PO ratification), Q5 ASK double layer (derived).
- [x] C2 Five contradictions corrected; checklist 23/24 -> 24/24; PROGRESO row added. No code, no commits.
- Next step: `/speckit-plan` (user decides).

## Plan progress (2026-10-18)
- [x] P1 `/speckit-plan` executed by a delegated writer (route: delegated, trigger: writer + preparation): `specs/005-basic-agent-loop/plan.md`, `research.md`, `data-model.md`, `contracts/agent-loop-contract.md`, `quickstart.md`.
- [x] P2 spec.md: Q4 recorded as approved by the PO (Clarifications, US4-4/US4-5, FR-031, open questions); checklist still 24/24 (35 scenarios).
- [x] P3 `docs/PROGRESO.md` registry row added (HU-01-01 stays Pendiente). No code, no tasks.md, no commits.
- Design: single `AgentLoop` in `core/loop.py`; caller-owned history; sequential per-call pipeline; Q4 propagate emit failures.
- Open coordination: B (subscriber isolation, APPROVAL_* double), C (validate_args semantics, ASK/read demo risk).
- Next step: `/speckit-tasks` (user decides).
- [x] P4 R-07/R-08 synced into spec/plan/contract/research/quickstart; tasks.md generated (30 tasks = 810 min + 2 blocked integration tasks T031/T032). PROGRESO row added. No code, no commits.
- Next step: audit tasks.md, then /speckit-implement (user decides).
- [x] P5 Audit fixes M1-M4 applied to spec/plan/tasks/contract/research/quickstart/data-model (2026-10-19): R-08 diagnostic = add_note only (no __context__); T010/T011 evidence from T007 minimal tests; T004 no longer [P]; ToolCall.id uniqueness documented as HU-07-01 canonical rule, T031 checks B's FakeProvider ids. Branch feat/hu-01-01-basic-agent-loop created from feat/hu-07-01-provider-message-format. No code, no commits.
- Next step: user decides /speckit-implement.

## Implementation progress (2026-10-19)
- [x] I1 T001-T030 implemented via delegated writers (RED observed per story, then GREEN): `core/loop.py` (AgentLoop, 100% coverage), `tests/core/`, `tests/doubles/`, `tests/architecture/test_loop_boundaries.py`.
- [x] I2 Gate: pytest 513 passed / 5 skipped; mypy strict 66 files clean; ruff check/format clean; shared contracts and constitution untouched.
- [x] I3 tasks.md ticked T001-T030 with evidence; PROGRESO row added; HU-01-01 = "En revisión" (not Hecha). T031/T032 left unchecked (blocked by B/C).
- No commits, no push. Next step: user decides review / commit / /speckit-converge.

## Convergencia (2026-10-19)

- `/speckit-converge`: dictamen B (convergencia técnica local). Hallazgos menores T033–T035 añadidos a tasks.md (Phase 11). T031/T032 siguen bloqueadas por B y C. HU-01-01 permanece «En revisión». Sin commits.

## Correcciones de convergencia T033-T035 (2026-10-19)
- [x] C1 T033: registry/declaration failure is structural (propagates, no PROVIDER_ERROR, provider not queried); RED 4 failures -> GREEN 5 passed.
- [x] C2 T034: deep copy of the history for the provider and of the response ToolCalls; RED 3 failures -> GREEN 4 passed.
- [x] C3 T035: per-task evidence for T001-T030 (30/30); new AST guard for Q4 (T019).
- Gate: pytest 524 passed / 5 skipped; mypy strict 66 files clean; ruff clean; loop.py coverage 100%. No commits, no push. HU-01-01 stays 'En revision'; T031/T032 blocked by B/C.
