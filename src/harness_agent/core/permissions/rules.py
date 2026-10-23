"""The rules that the configuration gives to the permission policy (HU-05-01).

Only two lists exist: tools that are always denied and tools that are always asked. There is no
field to allow anything: the rules can only make the policy stricter. The lists are immutable,
validated when the object is built (fail closed) and the error messages never reproduce the
invalid value.
"""

from __future__ import annotations

from dataclasses import dataclass


def _normalize(field: str, value: object) -> tuple[str, ...]:
    """The names of ``field`` without duplicates (first order kept); reject what is not valid."""
    if not isinstance(value, tuple | list):
        raise TypeError(
            f"La lista '{field}' debe ser una secuencia de textos, no '{type(value).__name__}'."
        )
    names: dict[str, None] = {}
    for index, name in enumerate(value):
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"La lista '{field}' tiene un elemento no válido en la posición {index}: "
                "debe ser un texto no vacío."
            )
        names.setdefault(name, None)
    return tuple(names)


@dataclass(frozen=True, slots=True)
class PermissionRules:
    """Names of tools that are always denied (``deny``) or always asked (``ask``).

    A name in both lists is denied (deny prevails over ask). The names are compared as they are,
    distinguishing upper and lower case.
    """

    deny: tuple[str, ...] = ()
    ask: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "deny", _normalize("deny", self.deny))
        object.__setattr__(self, "ask", _normalize("ask", self.ask))
