"""The audit of decisions (HU-05-05): arguments, the policy tap, the recorder and the table.

The core part is pure: a fake log, fake events and the redactor of the run are enough. Anything that
looks like a key is built in parts so that this file holds no literal the secrets detector flags.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from harness_agent.core import (
    AUDIT_TABLE_ROWS,
    NO_DATA,
    ArgumentsTap,
    AuditEntry,
    AuditRecorder,
    AuditRow,
    Event,
    EventType,
    PermissionDecision,
    PermissionPolicy,
    SecretRedactor,
    ToolCall,
    format_audit,
    origin_of,
    prepare_arguments,
    requester_label,
    resolution_of,
)

NOW = datetime(2026, 11, 4, 10, 30, 15, tzinfo=timezone.utc)
SENTINEL = "VALOR-DE-PRUEBA-123"
PREFIXED_KEY = "s" + "k-" + "a" * 24
KNOWN_VALUE = "valor-del-entorno-" + "z" * 6
HIDDEN = SecretRedactor().value(PREFIXED_KEY)  # the mark the redactor writes


def redactor() -> SecretRedactor:
    return SecretRedactor(known=[KNOWN_VALUE])


# --- prepare_arguments ------------------------------------------------------------------------


def test_the_arguments_become_one_json_text_with_sorted_keys() -> None:
    text = prepare_arguments({"b": 1, "a": "x"}, redactor().value)

    assert text == '{"a": "x", "b": 1}'


def test_a_key_with_a_known_prefix_and_a_known_value_are_hidden_before_anything_else() -> None:
    text = prepare_arguments({"content": f"a {PREFIXED_KEY} b {KNOWN_VALUE}"}, redactor().value)

    assert PREFIXED_KEY not in text and KNOWN_VALUE not in text
    assert HIDDEN in text


def test_credentials_of_a_url_are_hidden() -> None:
    url = "https://" + "user" + ":" + "pass1234" + "@host.example/path"

    text = prepare_arguments({"url": url}, redactor().value)

    assert "pass1234" not in text


def test_every_text_is_shortened_after_the_redaction_with_a_mark() -> None:
    text = prepare_arguments({"content": "a" * 500}, redactor().value)

    value = json.loads(text)["content"]
    assert value == "a" * 200 + "[+300]"


def test_a_secret_that_the_cut_would_split_is_hidden_first() -> None:
    padded = "a" * 189 + " " + PREFIXED_KEY  # the cut at 200 characters falls inside the key

    text = prepare_arguments({"content": padded}, redactor().value)

    assert "sk-" not in text and "aaaaaaaaaa" in text


def test_the_whole_text_is_shortened_to_the_total_cap() -> None:
    arguments = {f"k{index}": "v" * 150 for index in range(40)}

    text = prepare_arguments(arguments, redactor().value)

    assert len(text) == 2000 and text.endswith("[recortado]")


def test_nested_structures_and_non_texts_are_kept_and_shortened_inside() -> None:
    arguments = {"items": [1, True, None, {"deep": "d" * 300}], "pair": (1, 2)}

    parsed = json.loads(prepare_arguments(arguments, redactor().value))

    assert parsed["items"][:3] == [1, True, None]
    assert parsed["items"][3]["deep"].endswith("[+100]")
    assert parsed["pair"] == [1, 2]


def test_the_keys_are_shortened_too() -> None:
    parsed = json.loads(prepare_arguments({"k" * 300: 1}, redactor().value))

    assert list(parsed) == ["k" * 200 + "[+100]"]


def test_hidden_and_direction_characters_are_escaped_so_that_they_are_visible() -> None:
    text = prepare_arguments({"a": "x" + chr(0x202E) + chr(0x200B) + "y"}, redactor().value)

    assert chr(0x202E) not in text and chr(0x200B) not in text
    assert "\\u202e" in text and "\\u200b" in text


class Unreadable:
    pass


def test_an_object_that_json_cannot_write_is_no_data_and_never_raises() -> None:
    assert prepare_arguments({"a": Unreadable()}, redactor().value) == NO_DATA


def test_a_cycle_or_a_failing_redactor_is_no_data() -> None:
    cycle: dict[str, Any] = {}
    cycle["self"] = cycle

    def broken(value: Any) -> Any:
        raise RuntimeError(SENTINEL)

    assert prepare_arguments(cycle, redactor().value) == NO_DATA
    assert prepare_arguments({"a": 1}, broken) == NO_DATA


def test_mixed_key_types_that_cannot_be_sorted_are_no_data() -> None:
    assert prepare_arguments({1: "a", "b": 2}, redactor().value) == NO_DATA


# --- resolution and origin --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("decision", "resolved_as", "expected"),
    [
        ("allow", "allow", "permitida"),
        ("deny", "deny", "denegada"),
        ("ask", "deny", "denegada"),
        ("ask", "ask", "pendiente"),
        ("otra", "allow", NO_DATA),
        (NO_DATA, NO_DATA, NO_DATA),
    ],
)
def test_the_resolution_of_a_decision(decision: str, resolved_as: str, expected: str) -> None:
    assert resolution_of(decision, resolved_as) == expected


@pytest.mark.parametrize(
    ("call_id", "expected"),
    [
        ("verificacion-1", "verificacion"),
        ("arranque-git", "arranque"),
        ("arranque-prueba", "arranque"),
        ("call_1", "agente"),
        ("", "agente"),
    ],
)
def test_the_origin_comes_from_the_prefix_of_the_call_id(call_id: str, expected: str) -> None:
    assert origin_of(call_id) == expected


# --- the policy tap ---------------------------------------------------------------------------


class FixedPolicy(PermissionPolicy):
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.seen: list[ToolCall] = []

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        self.seen.append(call)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        decision: PermissionDecision = self.outcome
        return decision


def call_of(identifier: str = "c1", **arguments: Any) -> ToolCall:
    return ToolCall(identifier, "escribir_archivo", dict(arguments))


@pytest.mark.parametrize("decision", list(PermissionDecision))
def test_the_tap_returns_exactly_what_the_inner_policy_decided(
    decision: PermissionDecision,
) -> None:
    inner = FixedPolicy(decision)
    tap = ArgumentsTap(inner, redactor().value)

    assert tap.evaluate(call_of(path="a")) is decision
    assert len(inner.seen) == 1


def test_an_exception_of_the_inner_policy_still_rises_and_the_arguments_are_kept() -> None:
    tap = ArgumentsTap(FixedPolicy(RuntimeError(SENTINEL)), redactor().value)

    with pytest.raises(RuntimeError):
        tap.evaluate(call_of(path="a"))

    assert tap.take("c1") == '{"path": "a"}'


def test_the_tap_hands_the_arguments_once_and_unknown_calls_have_no_data() -> None:
    tap = ArgumentsTap(FixedPolicy(PermissionDecision.ALLOW), redactor().value)
    tap.evaluate(call_of(path="a"))

    assert tap.take("c1") == '{"path": "a"}'
    assert tap.take("c1") == NO_DATA
    assert tap.take("never") == NO_DATA


def test_the_tap_stores_the_redacted_arguments_never_the_original() -> None:
    tap = ArgumentsTap(FixedPolicy(PermissionDecision.ASK), redactor().value)
    tap.evaluate(call_of(content=PREFIXED_KEY))

    assert PREFIXED_KEY not in tap.take("c1")


def test_a_failing_redactor_leaves_no_data_and_does_not_change_the_decision() -> None:
    def broken(value: Any) -> Any:
        raise RuntimeError(SENTINEL)

    tap = ArgumentsTap(FixedPolicy(PermissionDecision.DENY), broken)

    assert tap.evaluate(call_of(path="a")) is PermissionDecision.DENY
    assert tap.take("c1") == NO_DATA


def test_the_pending_arguments_are_bounded_and_the_oldest_go_first() -> None:
    tap = ArgumentsTap(FixedPolicy(PermissionDecision.ALLOW), redactor().value)
    for index in range(300):
        tap.evaluate(call_of(f"c{index}", n=index))

    assert tap.take("c0") == NO_DATA
    assert tap.take("c43") == NO_DATA
    assert tap.take("c44") == '{"n": 44}'
    assert tap.take("c299") == '{"n": 299}'


def test_the_same_call_id_again_replaces_the_arguments() -> None:
    tap = ArgumentsTap(FixedPolicy(PermissionDecision.ALLOW), redactor().value)
    tap.evaluate(call_of("verificacion-1", command="uno"))
    tap.evaluate(call_of("verificacion-1", command="dos"))

    assert tap.take("verificacion-1") == '{"command": "dos"}'


# --- the recorder -----------------------------------------------------------------------------


class MemoryAuditLog:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []
        self.resolutions: list[tuple[Any, ...]] = []
        self.fail = False

    def record_decision(self, entry: AuditEntry) -> None:
        if self.fail:
            raise RuntimeError(SENTINEL)
        self.entries.append(entry)

    def record_resolution(
        self,
        session_id: str,
        call_id: str,
        resolution: str,
        action: str | None,
        source: str | None,
        resolved_at: datetime,
    ) -> None:
        if self.fail:
            raise RuntimeError(SENTINEL)
        self.resolutions.append((session_id, call_id, resolution, action, source, resolved_at))

    def rows(self, session_id: str, limit: int) -> list[AuditRow]:
        return []

    def count(self, session_id: str) -> int:
        return 0


def event(kind: EventType, payload: dict[str, Any], session: str = "s1") -> Event:
    return Event("e1", session, kind, NOW, payload)


def decided(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "call_id": "c1",
        "name": "escribir_archivo",
        "decision": "ask",
        "resolved_as": "ask",
        "reason": None,
    }
    return {**payload, **overrides}


def recorder() -> tuple[AuditRecorder, ArgumentsTap, MemoryAuditLog]:
    tap = ArgumentsTap(FixedPolicy(PermissionDecision.ASK), redactor().value)
    log = MemoryAuditLog()
    return AuditRecorder(log, tap, redactor().value), tap, log


def test_a_decision_event_writes_the_row_with_the_arguments_of_the_tap() -> None:
    audit, tap, log = recorder()
    tap.evaluate(call_of(path="a.txt"))

    audit.on_decided(event(EventType.PERMISSION_DECIDED, decided()))

    assert log.entries == [
        AuditEntry(
            session_id="s1",
            call_id="c1",
            tool="escribir_archivo",
            arguments='{"path": "a.txt"}',
            decision="ask",
            resolution="pendiente",
            reason=None,
            origin="agente",
            decided_at=NOW,
        )
    ]


@pytest.mark.parametrize(
    ("overrides", "resolution", "reason"),
    [
        ({"decision": "allow", "resolved_as": "allow"}, "permitida", None),
        ({"decision": "deny", "resolved_as": "deny"}, "denegada", None),
        ({"decision": "ask", "resolved_as": "deny"}, "denegada", None),
        (
            {"decision": "deny", "resolved_as": "deny", "reason": "policy_error"},
            "denegada",
            "policy_error",
        ),
    ],
)
def test_the_resolution_and_the_reason_of_each_decision(
    overrides: dict[str, Any], resolution: str, reason: str | None
) -> None:
    audit, _, log = recorder()

    audit.on_decided(event(EventType.PERMISSION_DECIDED, decided(**overrides)))

    assert (log.entries[0].resolution, log.entries[0].reason) == (resolution, reason)


@pytest.mark.parametrize(
    ("call_id", "origin"),
    [("verificacion-2", "verificacion"), ("arranque-git", "arranque"), ("toolu_1", "agente")],
)
def test_the_origin_of_the_row_comes_from_the_call_id(call_id: str, origin: str) -> None:
    audit, _, log = recorder()

    audit.on_decided(event(EventType.PERMISSION_DECIDED, decided(call_id=call_id)))

    assert log.entries[0].origin == origin


def test_the_session_of_the_event_is_the_session_of_the_row_also_for_a_child() -> None:
    audit, _, log = recorder()

    audit.on_decided(event(EventType.PERMISSION_DECIDED, decided(), session="hija"))

    assert log.entries[0].session_id == "hija"


@pytest.mark.parametrize(
    "payload",
    [{}, {"call_id": 7, "name": None, "decision": ["x"], "resolved_as": {}, "reason": 3}],
)
def test_an_incomplete_or_odd_payload_is_recorded_as_no_data_and_does_not_fail(
    payload: dict[str, Any],
) -> None:
    audit, _, log = recorder()

    audit.on_decided(event(EventType.PERMISSION_DECIDED, payload))

    entry = log.entries[0]
    assert (entry.call_id, entry.tool, entry.decision) == (NO_DATA, NO_DATA, NO_DATA)
    assert (entry.arguments, entry.resolution, entry.reason) == (NO_DATA, NO_DATA, None)


def test_the_name_and_the_call_id_are_redacted_and_bounded() -> None:
    audit, _, log = recorder()

    audit.on_decided(
        event(
            EventType.PERMISSION_DECIDED,
            decided(name=PREFIXED_KEY + "n" * 400, call_id=KNOWN_VALUE),
        )
    )

    entry = log.entries[0]
    assert PREFIXED_KEY not in entry.tool and KNOWN_VALUE not in entry.call_id
    assert len(entry.tool) <= 200


def test_an_approval_completes_the_row_as_approved_rejected_or_failed() -> None:
    audit, _, log = recorder()
    base = {"call_id": "c1", "name": "x", "source": "user"}

    audit.on_resolved(
        event(EventType.APPROVAL_RESOLVED, {**base, "action": "approve_once", "approved": True})
    )
    audit.on_resolved(
        event(EventType.APPROVAL_RESOLVED, {**base, "action": "reject", "approved": False})
    )
    audit.on_resolved(
        event(
            EventType.APPROVAL_RESOLVED,
            {**base, "action": None, "approved": False, "source": "approver_error"},
        )
    )

    assert [(row[2], row[3], row[4]) for row in log.resolutions] == [
        ("aprobada", "approve_once", "user"),
        ("rechazada", "reject", "user"),
        ("fallida", None, "approver_error"),
    ]
    assert log.resolutions[0][:2] == ("s1", "c1") and log.resolutions[0][5] == NOW


def test_an_approval_with_an_odd_payload_is_never_taken_as_approved() -> None:
    audit, _, log = recorder()

    audit.on_resolved(event(EventType.APPROVAL_RESOLVED, {"approved": "yes", "action": 3}))
    audit.on_resolved(event(EventType.APPROVAL_RESOLVED, {"approved": "yes", "action": "reject"}))

    assert log.resolutions[0][1:5] == (NO_DATA, "fallida", None, None)
    assert log.resolutions[1][2] == "rechazada"


def test_a_failure_of_the_log_is_not_swallowed() -> None:
    audit, _, log = recorder()
    log.fail = True

    with pytest.raises(RuntimeError):
        audit.on_decided(event(EventType.PERMISSION_DECIDED, decided()))
    with pytest.raises(RuntimeError):
        audit.on_resolved(event(EventType.APPROVAL_RESOLVED, {"call_id": "c1"}))


# --- the table --------------------------------------------------------------------------------


def row(**overrides: Any) -> AuditRow:
    values: dict[str, Any] = {
        "session_id": "s1",
        "parent_id": None,
        "call_id": "c1",
        "tool": "escribir_archivo",
        "arguments": '{"path": "a.txt"}',
        "decision": "ask",
        "resolution": "aprobada",
        "reason": None,
        "action": "approve_once",
        "source": "user",
        "origin": "agente",
        "decided_at": NOW,
        "resolved_at": NOW,
    }
    return AuditRow(**{**values, **overrides})


def test_the_table_has_a_header_one_line_per_row_and_the_time_in_utc() -> None:
    text = format_audit([row()], total=1, session_id="s1")

    lines = text.splitlines()
    assert lines[0] == "Auditoría de la sesión s1 (1 registro)."
    assert "hora" in lines[1] and "herramienta" in lines[1] and "resolución" in lines[1]
    assert "10:30:15" in lines[2] and "escribir_archivo" in lines[2] and "aprobada" in lines[2]
    assert '{"path": "a.txt"}' in lines[2]
    assert len(lines) == 3


def test_without_rows_it_says_so_in_one_fixed_line() -> None:
    text = format_audit([], total=0, session_id="s1")

    assert text == "Sin registros de auditoría para esa sesión."


def test_more_rows_than_the_table_holds_says_how_many_are_shown() -> None:
    rows = [row(call_id=f"c{index}") for index in range(AUDIT_TABLE_ROWS)]

    text = format_audit(rows, total=45, session_id="s1")

    assert text.splitlines()[0] == (
        f"Auditoría de la sesión s1 ({AUDIT_TABLE_ROWS} de 45 registros; últimos mostrados)."
    )


def test_who_asks_is_the_agent_the_verification_the_startup_or_a_subagent() -> None:
    rows = [
        row(call_id="a"),
        row(call_id="verificacion-1", origin="verificacion"),
        row(call_id="arranque-git", origin="arranque"),
        row(call_id="b", session_id="hija-0123456789", parent_id="s1"),
    ]

    lines = format_audit(rows, total=4, session_id="s1").splitlines()[2:]

    assert "agente" in lines[0]
    assert "verificación" in lines[1]
    assert "arranque" in lines[2]
    assert requester_label("hija-0123456789") in lines[3]


def test_the_arguments_are_shortened_to_fifty_characters_in_the_table() -> None:
    text = format_audit(
        [row(arguments='{"content": "' + "a" * 200 + '"}')], total=1, session_id="s1"
    )

    assert "a" * 60 not in text and "..." in text.splitlines()[2]


def test_hidden_characters_in_a_stored_field_never_reach_the_screen() -> None:
    hostile = row(tool="x" + chr(0x202E) + "y", arguments="a\nb\tc")

    text = format_audit([hostile], total=1, session_id="s1")

    assert chr(0x202E) not in text
    assert len(text.splitlines()) == 3


def test_the_resolution_is_shown_as_stored_even_when_it_is_no_data() -> None:
    text = format_audit([row(resolution=NO_DATA)], total=1, session_id="s1")

    assert NO_DATA in text.splitlines()[2]
