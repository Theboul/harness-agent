"""A provider that can change the model it talks to while the session runs (HU-06-06).

``ModelSwitch`` is a ``Provider`` that delegates every call to the active provider: the one of the
configured model at first, then the one of an alias the person chose with ``/model``. The retries
wrap it from the outside, so they follow the change. It holds no provider name and no key: the
composition root gives it the function that builds the provider of an alias, so a missing key or a
missing dependency surfaces when the alias is chosen, not when the system starts.

A failure of that function is translated to ``ModelUnavailable`` with a code; its text is never
copied (it could hold a secret). Selecting never leaves a half change: the active provider changes
only after the new one was built.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from harness_agent.core import Message, Provider, ProviderResponse, ToolDefinition

DEFAULT_ALIAS = "predeterminado"


class ModelSwitchError(Exception):
    """Base of the errors of ``ModelSwitch.select``."""


class UnknownModelAlias(ModelSwitchError):
    """The name is neither an alias nor the word of the default model."""


class ModelUnavailable(ModelSwitchError):
    """The provider of an alias could not be built.

    Attributes:
        code: ``missing_key`` (the key of its provider is not in the environment) or ``failed``.
        variable: Name of the environment variable that is missing, for ``missing_key``.
    """

    def __init__(self, code: str, variable: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.variable = variable


class ModelSwitch(Provider):
    """Delegate to the active provider; ``select`` changes it.

    Args:
        default_model: The configured ``<provider>/<model>``.
        default_provider: The provider of that model.
        aliases: Alias -> ``<provider>/<model>``, in the order they are listed.
        build: Builds the provider of an alias; may raise ``ModelUnavailable``, any other failure
            is reported as ``failed``.
    """

    def __init__(
        self,
        default_model: str,
        default_provider: Provider,
        aliases: Mapping[str, str],
        build: Callable[[str], Provider],
    ) -> None:
        self._default_model = default_model
        self._default = default_provider
        self._aliases = dict(aliases)
        self._build = build
        self._built: dict[str, Provider] = {}
        self._active: Provider = default_provider
        self._model = default_model
        self._alias: str | None = None

    @property
    def model(self) -> str:
        """The ``<provider>/<model>`` in use."""
        return self._model

    @property
    def alias(self) -> str | None:
        """The alias in use, or ``None`` for the configured model."""
        return self._alias

    @property
    def aliases(self) -> tuple[tuple[str, str], ...]:
        """The aliases and their models, in order."""
        return tuple(self._aliases.items())

    def has(self, alias: str) -> bool:
        """Whether ``alias`` is a configured alias (the default word is not one)."""
        return alias in self._aliases

    def select(self, name: str) -> str:
        """Make ``name`` (an alias or the default word) the active model and return its model.

        Raises:
            UnknownModelAlias: ``name`` is not known.
            ModelUnavailable: The provider of the alias could not be built; nothing changed.
        """
        key = name.strip().lower()
        if key == DEFAULT_ALIAS:
            self._active, self._model, self._alias = self._default, self._default_model, None
            return self._model
        if key not in self._aliases:
            raise UnknownModelAlias(key)
        provider = self._built.get(key)
        if provider is None:
            try:
                provider = self._build(key)
            except ModelUnavailable:
                raise
            except Exception:
                raise ModelUnavailable("failed") from None
            self._built[key] = provider
        self._active, self._model, self._alias = provider, self._aliases[key], key
        return self._model

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderResponse:
        """One call to the active provider."""
        return await self._active.complete(messages, tools)
