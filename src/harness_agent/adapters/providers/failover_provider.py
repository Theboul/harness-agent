"""Switch to another model when the active one fails for a reason outside the request (HU-07-05).

``FailoverProvider`` is a ``Provider`` that wraps the retrying provider, which wraps the
``ModelSwitch``. A failure reaches it only after the retries of the active model are spent. If the
core rule (``is_failover_eligible``) says the failure is one a change of model can fix, it moves
the switch to the next model of the list that the turn has not tried, **repeats the same call**
with the same messages and tools, and tells an observer. Anything else is raised untouched: a bad
key, a malformed request, a refusal by content policy, an unknown error and a cancellation never
switch (fail closed). When no model is left it raises ``FailoverExhausted`` with a fixed text.

The list is the default model first, then the aliases in the order of the configuration. A model
counts as tried when the wrapper tries to move to it, whether the move worked or not; the one that
is active when the turn makes its first call counts too. ``begin_turn`` starts a new turn, so each
request of the person can try them all again but never loops inside one.

It holds no provider name, no key and no event: the composition root gives it the switch and the
observer, and publishes the event itself. The text of a provider failure is never copied.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from harness_agent.adapters.providers.errors import FailoverExhausted
from harness_agent.adapters.providers.model_switch import DEFAULT_ALIAS, ModelSwitchError
from harness_agent.core import (
    FailoverTurn,
    Message,
    Provider,
    ProviderResponse,
    ToolDefinition,
    is_failover_eligible,
)


class Switchable(Protocol):
    """What the failover needs of the switch (``ModelSwitch`` has all of it)."""

    @property
    def alias(self) -> str | None:
        """The alias in use, or ``None`` for the configured model."""
        ...

    @property
    def model(self) -> str:
        """The ``<provider>/<model>`` in use."""
        ...

    def select(self, name: str) -> str:
        """Make ``name`` the active model and return its ``<provider>/<model>``."""
        ...


@dataclass(frozen=True)
class Switched:
    """What an observer learns about a switch: the two models and the class of the error.

    Never the text of the error nor of the request.
    """

    from_model: str
    to_model: str
    error_type: str


Observer = Callable[[Switched], None]
Warn = Callable[[str], None]


def _skipped_line(alias: str) -> str:
    return f"Modelo de respaldo «{alias}» no disponible; se prueba el siguiente de la lista."


class FailoverProvider(Provider):
    """A ``Provider`` that moves to the next untried model after an eligible failure.

    Args:
        inner: The provider that makes the calls (the retrying one, over the switch).
        switch: The model switch that ``inner`` follows; the wrapper moves it.
        aliases: The aliases to fall back to, in order; the default model always goes first.
        observer: Told about every switch; a failure of the observer is ignored.
        warn: Receives one fixed line for every model that could not be built.
    """

    def __init__(
        self,
        inner: Provider,
        switch: Switchable,
        aliases: Sequence[str],
        *,
        observer: Observer | None = None,
        warn: Warn | None = None,
    ) -> None:
        self._inner = inner
        self._switch = switch
        self._observer = observer
        self._warn = warn
        self._turn = FailoverTurn((DEFAULT_ALIAS, *aliases))
        self._started = False

    @property
    def inner(self) -> Provider:
        """The wrapped provider."""
        return self._inner

    @property
    def tried(self) -> frozenset[str]:
        """The models (aliases, or the default word) tried in the turn that is running."""
        return self._turn.tried

    def begin_turn(self) -> None:
        """A new request of the person starts: nothing has been tried."""
        self._turn.begin()
        self._started = False

    def _notify(self, change: Switched) -> None:
        if self._observer is None:
            return
        try:
            self._observer(change)
        except Exception:
            # The record is a courtesy: it must never change the outcome of the call.
            return

    def _advance(self, error_type: str) -> bool:
        """Move to the first untried model that can be built; ``False`` if none is left."""
        while True:
            key = self._turn.next_untried()
            if key is None:
                return False
            self._turn.mark(key)
            before = self._switch.model
            try:
                after = self._switch.select(key)
            except ModelSwitchError:
                if self._warn is not None:
                    self._warn(_skipped_line(key))
                continue
            self._notify(Switched(before, after, error_type))
            return True

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderResponse:
        """Call the wrapped provider; on an eligible failure, repeat with the next model."""
        if not self._started:
            self._turn.mark(self._switch.alias or DEFAULT_ALIAS)
            self._started = True
        while True:
            try:
                return await self._inner.complete(messages, tools)
            except Exception as error:
                if not is_failover_eligible(error):
                    raise
                error_type = type(error).__name__
            # Outside the handler: the exhausted error must not carry the failure as its context.
            if not self._advance(error_type):
                raise FailoverExhausted()
