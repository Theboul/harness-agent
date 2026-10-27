"""Automatic verification of the objective criteria of a task (HU-11-04.1).

Only the standard library and ``harness_agent.core`` are used here. The pure pieces: the statuses
and results, the notice to the agent and the evidence.
"""

from harness_agent.core.verification.feedback import (
    MAX_DESCRIPTION_EVENT,
    MAX_DESCRIPTION_NOTICE,
    MAX_EVIDENCE_CHARS,
    MAX_LISTED,
    MAX_OUTPUT_PER_CRITERION,
    MAX_OUTPUT_TOTAL,
    Feedback,
    compose_feedback,
    evidence_text,
    one_line,
    program_name,
)
from harness_agent.core.verification.outcomes import (
    CommandOutcome,
    CommandRunner,
    CriterionResult,
    CriterionStatus,
    NotRunCause,
    TaskState,
    VerificationReport,
    task_state,
)
from harness_agent.core.verification.runner import TurnLike, Verifier, VerifyingRunner
from harness_agent.core.verification.verifier import CriteriaVerifier

__all__ = [
    "MAX_DESCRIPTION_EVENT",
    "MAX_DESCRIPTION_NOTICE",
    "MAX_EVIDENCE_CHARS",
    "MAX_LISTED",
    "MAX_OUTPUT_PER_CRITERION",
    "MAX_OUTPUT_TOTAL",
    "CommandOutcome",
    "CommandRunner",
    "CriteriaVerifier",
    "CriterionResult",
    "CriterionStatus",
    "Feedback",
    "NotRunCause",
    "TaskState",
    "TurnLike",
    "VerificationReport",
    "Verifier",
    "VerifyingRunner",
    "compose_feedback",
    "evidence_text",
    "one_line",
    "program_name",
    "task_state",
]
