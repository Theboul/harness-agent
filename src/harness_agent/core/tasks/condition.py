"""The expected condition of a verification criterion (HU-11-04.1).

The first version understands only two forms, written exactly as in the task file::

    codigo_salida == N
    codigo_salida != N

``N`` is a whole number from 0 to ``MAX_EXIT_CODE``. Anything else is not a condition, and the
task parser rejects it when the task is loaded. Both functions are pure and total: no input makes
them raise. Adding more forms later (for example, that the output contains a text) does not
invalidate a condition written with these two.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_EXIT_CODE = 4_294_967_295
_OPERATORS = ("==", "!=")
_FORM = re.compile(r"codigo_salida[ \t]*(==|!=)[ \t]*([0-9]{1,10})")


@dataclass(frozen=True)
class Condition:
    """A condition already understood.

    Attributes:
        operator: ``==`` or ``!=``.
        value: The exit code the condition compares with.
    """

    operator: str
    value: int


def parse_condition(text: object) -> Condition | None:
    """The condition written in ``text``, or ``None`` if it is not exactly one of the two forms."""
    if not isinstance(text, str):
        return None
    match = _FORM.fullmatch(text.strip())
    if match is None:
        return None
    value = int(match.group(2))
    if value > MAX_EXIT_CODE:
        return None
    return Condition(match.group(1), value)


def condition_met(condition: Condition, exit_code: int | None) -> bool:
    """Whether ``exit_code`` meets ``condition``; no exit code (nothing ran, timeout) never does."""
    if not isinstance(condition, Condition) or condition.operator not in _OPERATORS:
        return False
    value = condition.value
    if isinstance(value, bool) or not isinstance(value, int):
        return False
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        return False
    return exit_code == value if condition.operator == "==" else exit_code != value
