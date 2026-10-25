"""Protection of the harness folder against the tools of the agent (HU-11-01).

``ProtectedPolicy`` wraps another ``PermissionPolicy`` and decides first:

* a call whose ``path`` is inside the protected area is denied, whatever the tool and whether it
  reads or writes (the real path is judged by the ``AuthorizedArea`` it receives);
* a ``shell`` call whose ``command`` names one of the protected markers (file or folder names,
  compared in lower case and with ``\\`` read as ``/``) is denied;
* any other call is left to the wrapped policy, unchanged.

It fails closed: a malformed call, an area that does not answer with a bool, or any exception is a
denial; it never allows by itself (it never returns ``ALLOW`` on its own).

Known limitation (business rule 6 of HU-11-01, risk R-21): commands are not interpreted. A compound
command, a variable, a wildcard or an encoded name that does not contain a marker literally is not
detected; that analysis is HU-05-02 and verifiable isolation is HU-IN-02 (PD-06). This policy does
not prove isolation from a shell that runs with the privileges of the harness.
"""

from __future__ import annotations

from collections.abc import Sequence

from harness_agent.core.entities import ToolCall
from harness_agent.core.interfaces.security import PermissionDecision, PermissionPolicy
from harness_agent.core.interfaces.system import AuthorizedArea

_SHELL_TOOL = "shell"


def _normalize_markers(markers: Sequence[str]) -> tuple[str, ...]:
    if isinstance(markers, str) or not isinstance(markers, Sequence):
        raise TypeError("Los marcadores deben ser una secuencia de textos.")
    normalized: list[str] = []
    for index, marker in enumerate(markers):
        if not isinstance(marker, str):
            raise TypeError(f"El marcador en la posición {index} debe ser un texto.")
        text = marker.replace("\\", "/").lower().strip()
        if not text:
            raise ValueError(f"El marcador en la posición {index} no puede estar vacío.")
        normalized.append(text)
    return tuple(normalized)


class ProtectedPolicy(PermissionPolicy):
    """Deny access to the protected area and to shell commands that name it; delegate the rest.

    Args:
        inner: The policy that decides every call that does not touch the protected area.
        area: The protected area (files and folders); ``contains`` answers for a ``path``.
        shell_markers: Names whose literal presence in a shell command denies it.
    """

    def __init__(
        self,
        inner: PermissionPolicy,
        area: AuthorizedArea,
        shell_markers: Sequence[str] = (),
    ) -> None:
        if not isinstance(inner, PermissionPolicy):
            raise TypeError(
                f"La política envuelta debe ser un PermissionPolicy, no '{type(inner).__name__}'."
            )
        if not isinstance(area, AuthorizedArea):
            raise TypeError(
                f"El área protegida debe ser un AuthorizedArea, no '{type(area).__name__}'."
            )
        self._inner = inner
        self._area = area
        self._markers = _normalize_markers(shell_markers)

    def evaluate(self, call: ToolCall) -> PermissionDecision:
        """Deny what touches the protected area; otherwise the wrapped policy decides."""
        try:
            if self._touches_protected(call):
                return PermissionDecision.DENY
            return self._inner.evaluate(call)
        except Exception:
            return PermissionDecision.DENY

    def _touches_protected(self, call: ToolCall) -> bool:
        if (
            not isinstance(call, ToolCall)
            or not isinstance(call.name, str)
            or not call.name
            or not isinstance(call.arguments, dict)
        ):
            return True
        path = call.arguments.get("path")
        if isinstance(path, str):
            inside = self._area.contains(path)
            if inside is True:
                return True
            if inside is not False:
                return True  # an area that cannot answer is a denial
        if call.name == _SHELL_TOOL:
            command = call.arguments.get("command")
            if isinstance(command, str):
                text = command.replace("\\", "/").lower()
                return any(marker in text for marker in self._markers)
        return False
