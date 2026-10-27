"""Seeded random check of the notice to the agent (HU-11-04.1)."""

from __future__ import annotations

import random
import unicodedata

from harness_agent.core import (
    CriterionResult,
    CriterionStatus,
    NotRunCause,
    VerificationReport,
    compose_feedback,
    evidence_text,
    program_name,
)

SEED = 20261029
CASES = 200
SENTINEL_PROGRAM = "programa-de-prueba-123"
STATUSES = list(CriterionStatus)
CAUSES = [None, *NotRunCause]
ALPHABET = (
    list("abc XYZ019 .:;,/-_'\"[]()")
    + ["\n", "\r", "\t", "\x00", "\x1b", "\x7f"]
    + [chr(0x200B), chr(0x202E), chr(0x2028), chr(0xFEFF), chr(0xE000), chr(0xD800)]
    + ["Ignora lo anterior", "system:", "--- fin del criterio 1 ---", "[verificacion]"]
)
FORBIDDEN = {"Cc", "Cf", "Cs", "Co"}


def text(rng: random.Random) -> str:
    size = rng.choice([0, 0, 1, 10, 80, 120, 1_800])
    return "".join(rng.choice(ALPHABET) for _ in range(size))


def random_report(rng: random.Random) -> VerificationReport:
    results = []
    for index in range(1, rng.randint(0, 25) + 1):
        status = rng.choice(STATUSES)
        results.append(
            CriterionResult(
                index=index,
                description=text(rng),
                status=status,
                exit_code=rng.choice([None, 0, 1, 2, 255, 4_294_967_295]),
                program=SENTINEL_PROGRAM,
                output=text(rng),
                cause=rng.choice(CAUSES),
                timeout_seconds=rng.choice([None, 1, 2.5, 120, 600]),
            )
        )
    return VerificationReport(tuple(results))


def dirty(value: str) -> list[str]:
    return [c for c in value if c != "\n" and unicodedata.category(c) in FORBIDDEN]


def test_the_feedback_never_raises_and_respects_its_bounds() -> None:
    rng = random.Random(SEED)
    for _ in range(CASES):
        report = random_report(rng)
        feedback = compose_feedback(report)

        assert (feedback is None) == (not report.correctable)
        if feedback is None:
            continue
        assert feedback.external.startswith("[salida de verificación]")
        assert feedback.notice.startswith("[verificacion] La tarea no se da por terminada")
        for part in (feedback.external, feedback.notice):
            assert dirty(part) == []
        assert SENTINEL_PROGRAM not in feedback.external + feedback.notice
        assert feedback.notice.count("\n- Criterio") <= 20
        assert len(feedback.notice) < 4_000
        assert len(feedback.external) < 6_000 + 1_000 + 200 * len(report.correctable)
        assert compose_feedback(report) == feedback  # deterministic


def test_the_notice_never_carries_the_output() -> None:
    rng = random.Random(SEED + 1)
    for _ in range(CASES):
        marker = f"SALIDA-{rng.randint(0, 10**9)}"
        report = VerificationReport(
            (
                CriterionResult(
                    index=1,
                    description="criterio",
                    status=CriterionStatus.NOT_MET,
                    exit_code=1,
                    output=marker,
                ),
            )
        )
        feedback = compose_feedback(report)
        assert feedback is not None
        assert marker in feedback.external and marker not in feedback.notice


def test_the_evidence_and_the_program_name_never_raise() -> None:
    rng = random.Random(SEED + 2)
    for _ in range(CASES):
        evidence = evidence_text(rng.choice([0, 1, 255]), text(rng))
        assert evidence.startswith("Código de salida: ") and len(evidence) <= 2_000
        name = program_name(text(rng))
        assert name is None or (0 < len(name) <= 40 and " " not in name)
