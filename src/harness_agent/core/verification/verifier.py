"""The verifier: runs the verification command of every objective criterion and marks passes.

Each time the agent proposes to finish (HU-11-04.1) a round starts: for every criterion of the task,
in order, ``CriteriaVerifier`` runs the command that the task defined, under the same permission
policy as a shell call of the agent, and it is the **only** place in the code that calls
``TaskCriteria.mark_passes``. What the model says never counts as evidence.

Rules that hold for each criterion:

* A criterion without a command is never run or marked: it waits for a person.
* The command that runs is the one stored in SQLite (the source of truth), and only when it is
  exactly the one of the task definition; if not, it is tampering: nothing runs and nothing is
  marked. Criteria are paired with the stored rows by position.
* The call handed to the policy has the shape of the agent's (same tool name and arguments), so
  every wrapper of the chain decides the same way. ``DENY`` never runs and never reaches the
  approver; ``ASK`` goes to the approval gate and, without one, does not run; an error or an
  unexpected answer of the policy is ``DENY`` (fail closed).
* The command and its output are never published: the event carries the description, the status,
  the exit code and the name of the program (see ``contracts/criterion_verified_event.md``).

Cancellation is never caught. Only the standard library and ``harness_agent.core`` are used here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from harness_agent.core.entities import ToolCall
from harness_agent.core.events import EventType
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy
from harness_agent.core.interfaces.system import TaskCriteria, TaskCriteriaItem
from harness_agent.core.interfaces.tool import Tool
from harness_agent.core.permissions.approvals import ApprovalGate
from harness_agent.core.tasks.condition import condition_met, parse_condition
from harness_agent.core.tasks.definition import CriterionDefinition, TaskDefinition
from harness_agent.core.verification.feedback import (
    MAX_DESCRIPTION_EVENT,
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
    VerificationReport,
)

Emit = Callable[[EventType, dict[str, Any]], None]
_CORRECTABLE_WITH_OUTPUT = (
    CriterionStatus.NOT_MET,
    CriterionStatus.REGRESSION,
    CriterionStatus.TIMED_OUT,
)
_WITH_PROGRAM = (
    CriterionStatus.MET,
    CriterionStatus.NOT_MET,
    CriterionStatus.REGRESSION,
    CriterionStatus.TIMED_OUT,
)


class CriteriaVerifier:
    """Runs the verification commands of a task and marks the criteria that are met.

    Args:
        store: Where the criteria live (the source of truth of the commands and of passes).
        task: The task definition the session was started with (it holds the expected
            conditions).
        policy: The permission policy of the session, the same one the agent loop uses.
        tool: The shell tool, only to describe the request to the approver (description, risk).
        run: Runs the call of the shell tool and says what happened.
        emit: Publishes an event for the session.
        gate: Asks the person when the policy asks; ``None`` means nothing that is asked runs.
        tool_name: Name of the shell tool, as the policy knows it.
        command_argument: Name of its argument with the command text.
        timeout_argument: Name of its argument with the time limit.
        declared_timeouts: Time limit of each command declared in the task (by its text); a
            criterion whose command is identical to one of them runs with that limit.
    """

    def __init__(
        self,
        store: TaskCriteria,
        task: TaskDefinition,
        policy: PermissionPolicy,
        tool: Tool,
        run: CommandRunner,
        emit: Emit,
        *,
        gate: ApprovalGate | None = None,
        tool_name: str,
        command_argument: str,
        timeout_argument: str,
        declared_timeouts: Mapping[str, int] | None = None,
    ) -> None:
        self._store = store
        self._task = task
        self._policy = policy
        self._tool = tool
        self._run = run
        self._emit = emit
        self._gate = gate
        self._tool_name = tool_name
        self._command_argument = command_argument
        self._timeout_argument = timeout_argument
        self._declared = dict(declared_timeouts or {})

    async def verify(self, session_id: str) -> VerificationReport:
        """Verify every criterion of the task once and publish one event per criterion."""
        definitions = self._task.criteria
        total = len(definitions)
        items = self._load(session_id)
        count_differs = items is not None and len(items) != total
        if count_differs:
            self._emit(EventType.CRITERIA_TAMPERED, {"motivo": "criterios_no_coinciden"})
        results: list[CriterionResult] = []
        for index, definition in enumerate(definitions, start=1):
            item = None if items is None or count_differs else items[index - 1]
            result = await self._criterion(index, definition, item)
            self._emit(EventType.CRITERION_VERIFIED, self._payload(result, total))
            results.append(result)
        return VerificationReport(tuple(results))

    def _load(self, session_id: str) -> list[TaskCriteriaItem] | None:
        try:
            return list(self._store.load_criteria(session_id))
        except Exception:
            # The store found signs of tampering (and published its own event) or failed:
            # nothing from it can be trusted.
            return None

    async def _criterion(
        self,
        index: int,
        definition: CriterionDefinition,
        item: TaskCriteriaItem | None,
    ) -> CriterionResult:
        description = definition.description
        command = definition.command
        if item is None:
            # Nothing to compare with: the store is not readable or has other criteria.
            status = CriterionStatus.PENDING_HUMAN if command is None else CriterionStatus.TAMPERED
            return self._result(index, description, status)
        if item.command != command:
            self._emit(EventType.CRITERIA_TAMPERED, {"motivo": "comando_no_coincide"})
            return self._result(index, description, CriterionStatus.TAMPERED)
        if command is None:
            return self._result(index, description, CriterionStatus.PENDING_HUMAN)
        condition = parse_condition(definition.expectation)
        if condition is None:
            return self._not_run(index, description, NotRunCause.UNSUPPORTED_CONDITION)
        call = self._call(index, command)
        cause = await self._permission(call)
        if cause is not None:
            return self._not_run(index, description, cause)
        outcome = await self._execute(call)
        if (
            outcome is None
            or not outcome.ran
            or (outcome.exit_code is None and not outcome.timed_out)
        ):
            return self._not_run(index, description, NotRunCause.ERROR)
        program = program_name(command)
        if outcome.timed_out:
            return self._result(
                index,
                description,
                CriterionStatus.TIMED_OUT,
                program=program,
                output=outcome.output,
                timeout_seconds=outcome.timeout_seconds,
            )
        code = outcome.exit_code
        assert code is not None
        if condition_met(condition, code):
            if not item.passes and not self._mark(item, code, outcome.output):
                return self._not_run(index, description, NotRunCause.ERROR)
            return self._result(
                index, description, CriterionStatus.MET, exit_code=code, program=program
            )
        status = CriterionStatus.REGRESSION if item.passes else CriterionStatus.NOT_MET
        return self._result(
            index,
            description,
            status,
            exit_code=code,
            program=program,
            output=outcome.output,
        )

    def _call(self, index: int, command: str) -> ToolCall:
        arguments: dict[str, Any] = {self._command_argument: command}
        declared = self._declared.get(command.strip())
        if declared is not None:
            arguments[self._timeout_argument] = declared
        return ToolCall(id=f"verificacion-{index}", name=self._tool_name, arguments=arguments)

    async def _permission(self, call: ToolCall) -> NotRunCause | None:
        """``None`` when the call may run; otherwise why it does not."""
        try:
            decision: object = self._policy.evaluate(call)
        except Exception:
            decision = None
        if decision is PermissionDecision.ALLOW:
            self._emit(EventType.PERMISSION_DECIDED, _decided(call, "allow", "allow", None))
            return None
        if decision is PermissionDecision.DENY:
            self._emit(EventType.PERMISSION_DECIDED, _decided(call, "deny", "deny", None))
            return NotRunCause.DENIED
        if decision is PermissionDecision.ASK:
            gate = self._gate
            resolved = "ask" if gate is not None else "deny"
            self._emit(EventType.PERMISSION_DECIDED, _decided(call, "ask", resolved, None))
            if gate is None:
                return NotRunCause.NO_APPROVER
            return await self._ask(gate, call)
        self._emit(EventType.PERMISSION_DECIDED, _decided(call, "deny", "deny", "policy_error"))
        return NotRunCause.DENIED

    async def _ask(self, gate: ApprovalGate, call: ToolCall) -> NotRunCause | None:
        outcome = await gate.resolve(
            call,
            self._tool,
            lambda risk: self._emit(
                EventType.APPROVAL_REQUESTED,
                {"call_id": call.id, "name": call.name, "risk": risk},
            ),
        )
        action = None if outcome.action is None else outcome.action.value
        self._emit(
            EventType.APPROVAL_RESOLVED,
            {
                "call_id": call.id,
                "name": call.name,
                "action": action,
                "approved": outcome.approved,
                "source": outcome.source,
            },
        )
        return None if outcome.approved else NotRunCause.NOT_APPROVED

    async def _execute(self, call: ToolCall) -> CommandOutcome | None:
        try:
            outcome = await self._run(call)
        except Exception:
            return None
        return outcome if isinstance(outcome, CommandOutcome) else None

    def _mark(self, item: TaskCriteriaItem, exit_code: int, output: str) -> bool:
        """The only call to ``mark_passes`` in the code base; ``False`` if the store failed."""
        try:
            self._store.mark_passes(item.id, evidence_text(exit_code, output))
        except Exception:
            return False
        return True

    @staticmethod
    def _result(
        index: int,
        description: str,
        status: CriterionStatus,
        *,
        exit_code: int | None = None,
        program: str | None = None,
        output: str = "",
        cause: NotRunCause | None = None,
        timeout_seconds: float | None = None,
    ) -> CriterionResult:
        return CriterionResult(
            index=index,
            description=description,
            status=status,
            exit_code=exit_code,
            program=program,
            output=output if status in _CORRECTABLE_WITH_OUTPUT else "",
            cause=cause,
            timeout_seconds=timeout_seconds,
        )

    def _not_run(self, index: int, description: str, cause: NotRunCause) -> CriterionResult:
        return self._result(index, description, CriterionStatus.NOT_RUN, cause=cause)

    @staticmethod
    def _payload(result: CriterionResult, total: int) -> dict[str, Any]:
        shows_program = result.status in _WITH_PROGRAM
        return {
            "criterion": result.index,
            "total": total,
            "description": one_line(result.description, MAX_DESCRIPTION_EVENT),
            "status": result.status.value,
            "met": result.status is CriterionStatus.MET,
            "exit_code": result.exit_code,
            "program": result.program if shows_program else None,
        }


def _decided(call: ToolCall, decision: str, resolved_as: str, reason: str | None) -> dict[str, Any]:
    return {
        "call_id": call.id,
        "name": call.name,
        "decision": decision,
        "resolved_as": resolved_as,
        "reason": reason,
    }
