"""Provider adapter over LiteLLM, for any ``<provider>/<model>`` it supports (HU-07-02).

One adapter serves every provider: the provider and the model come only from the configured
model name (``<provider>/<model>``, the LiteLLM form) and this module holds no provider name and
no branch per provider. The only table that knows provider names is ``PROVIDER_KEY_VARIABLES``
in ``config.py``.

LiteLLM is an optional dependency and is loaded lazily, with ``importlib``, only here and only
when the adapter is built without an injected completion function. Requests are built from the
canonical messages with the converters of HU-07-01 (LiteLLM takes the common wire format); the
response object of LiteLLM is read, never sent back.
"""

from __future__ import annotations

import copy
import dataclasses
import importlib
import json
import logging
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from types import MappingProxyType
from typing import Any, Protocol

from harness_agent.adapters.converters import (
    ConversionError,
    from_openai_response,
    to_openai_messages,
    to_openai_tools,
)
from harness_agent.adapters.providers.errors import RateLimited
from harness_agent.core import (
    Message,
    Provider,
    ProviderError,
    ProviderResponse,
    ProviderTimeout,
    ProviderUnavailable,
    QuotaExceeded,
    ToolDefinition,
)

CompletionFn = Callable[..., Awaitable[Any]]

# The canonical way to say "this tool result is an error" is a ``[tag]`` in the content: the
# ``is_error`` flag does not travel through LiteLLM (SPK-01, difference 8).
_ERROR_TAG = "[tool_error]"
_TAG_AT_START = re.compile(r"\s*\[[a-z_]+\]")

# Unreadable tool arguments (invalid JSON, or JSON that is not an object) must not break the turn
# (FR-008). The call keeps its id and name and carries this one field, which no tool declares: the
# validator of the loop rejects it as ``[invalid_arguments]`` and the model can correct itself.
_UNREADABLE_ARGUMENTS = "arguments_not_valid_json"
_PREVIEW_CHARS = 200

_HIDDEN_KEY = "<oculta>"
_KEY_MARKER = "<secreto oculto>"
_BAD_MODEL = "El modelo debe tener la forma <proveedor>/<modelo>."
_BAD_CAP = "max_output_tokens debe ser un entero mayor que 0."
_BAD_HISTORY = "El historial no se puede enviar al modelo: no tiene una forma representable."
_BAD_RESPONSE = "La respuesta del modelo no tiene el formato esperado."
_EMPTY_RESPONSE = "El modelo respondió sin texto y sin llamadas a herramientas."
_MISSING_LIBRARY = (
    "Falta la dependencia opcional 'litellm', necesaria para conectar con un modelo real. "
    'Instálela con: pip install -e ".[litellm]". En Windows cree el entorno virtual en una '
    "ruta corta (por ejemplo C:\\tmp\\venv): con rutas largas la instalación puede quedar "
    "incompleta sin avisar."
)


# Failure of the library -> (canonical type, message). The texts are written here: the original
# message of the provider is never copied. ``{kind}`` is the name of the class that was raised.
_TIMEOUT = "El proveedor no respondió a tiempo ({kind})."
_RATE_LIMIT = (
    "El proveedor rechazó la llamada por límite de tasa ({kind}); espere antes de reintentar."
)
_QUOTA = "La cuota o el crédito del proveedor está agotado ({kind})."
_UNAVAILABLE = "El proveedor no está disponible ({kind})."
_GENERIC = "El proveedor devolvió un error ({kind})."

# Matched by class name along the MRO of the exception, from the most derived class to the most
# general one, so that ``Timeout`` (a subclass of ``APIConnectionError`` in LiteLLM) wins over its
# parent and a new subclass inherits the mapping of its parent. Names were checked against the
# pinned version (research.md, section 1). ``RateLimitError`` -> ``RateLimited`` (HU-07-04), a
# subtype of ``QuotaExceeded`` that passes by itself, unlike an exhausted credit.
# ``ImportError`` is a broken installation, found at call time.
ERROR_TABLE: Mapping[str, tuple[type[ProviderError], str]] = MappingProxyType(
    {
        "Timeout": (ProviderTimeout, _TIMEOUT),
        "APITimeoutError": (ProviderTimeout, _TIMEOUT),
        "RateLimitError": (RateLimited, _RATE_LIMIT),
        "PaymentRequiredError": (QuotaExceeded, _QUOTA),
        "BudgetExceededError": (QuotaExceeded, _QUOTA),
        "ServiceUnavailableError": (ProviderUnavailable, _UNAVAILABLE),
        "BadGatewayError": (ProviderUnavailable, _UNAVAILABLE),
        "InternalServerError": (ProviderUnavailable, _UNAVAILABLE),
        "APIConnectionError": (ProviderUnavailable, _UNAVAILABLE),
        "ImportError": (ProviderError, _MISSING_LIBRARY),
    }
)
_ANY_OTHER_FAILURE = (ProviderError, _GENERIC)


class ProviderDependencyError(Exception):
    """The optional dependency of the adapter is not installed.

    A failure to build the adapter, not a failure of a model call: it is not a ``ProviderError``.
    """


class _Revealable(Protocol):
    """What the adapter needs from a secret: a way to read it at the moment of the call."""

    def reveal(self) -> str: ...


# The loggers of LiteLLM write their own help text ("Give Feedback / Get Help", "LiteLLM.Info:
# ...turn_on_debug()") on the terminal when a call fails. The harness reports the failure itself
# (HU-06-05), so the library is kept quiet; the errors the adapter raises are not affected.
_LITELLM_LOGGERS = ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy")


def _silence(module: Any) -> None:
    """Turn off the debug help of LiteLLM and keep its loggers from writing to the terminal."""
    module.suppress_debug_info = True
    for name in _LITELLM_LOGGERS:
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL + 1)
        logger.propagate = False


def _load_completion() -> CompletionFn:
    """Return the async completion function of LiteLLM, imported only now."""
    try:
        module = importlib.import_module("litellm")
    except ImportError as exc:
        raise ProviderDependencyError(_MISSING_LIBRARY) from exc
    _silence(module)
    completion: CompletionFn = module.acompletion
    return completion


def _with_error_tags(messages: Sequence[Message]) -> list[Message]:
    """Copy of the history where every failed tool result carries a ``[tag]`` in its content."""
    prepared: list[Message] = []
    for message in messages:
        result = message.tool_result
        if result is not None and result.is_error and _TAG_AT_START.match(result.content) is None:
            tagged = dataclasses.replace(result, content=f"{_ERROR_TAG} {result.content}")
            message = dataclasses.replace(message, tool_result=tagged)
        prepared.append(message)
    return prepared


def _free_form_tools(tools: Sequence[ToolDefinition] | None) -> set[str]:
    """Names of the tools whose schema accepts undeclared fields (the marker would get through)."""
    return {
        tool.name for tool in tools or () if tool.parameters.get("additionalProperties") is True
    }


def _readable(raw: object) -> bool:
    """True if ``raw`` is something the converters accept as the arguments of a call."""
    if isinstance(raw, dict):
        return True
    if not isinstance(raw, str):
        return False
    if not raw.strip():
        return True
    try:
        return isinstance(json.loads(raw), dict)
    except ValueError:
        return False


def _mark_unreadable_arguments(
    wire: dict[str, Any], free_form: set[str], clean: Callable[[str], str]
) -> None:
    """Replace, in place, the arguments of the calls that cannot be read by the marker field."""
    choices = wire.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return
    message = choices[0].get("message")
    calls = message.get("tool_calls") if isinstance(message, dict) else None
    if not isinstance(calls, list):
        return
    for call in calls:
        function = call.get("function") if isinstance(call, dict) else None
        if not isinstance(function, dict) or _readable(function.get("arguments", "{}")):
            continue
        name = function.get("name")
        if isinstance(name, str) and name in free_form:
            raise ProviderError(
                clean(
                    f"No se puede señalar como ilegibles los argumentos de la herramienta "
                    f"'{name}' porque su esquema admite campos adicionales; se descarta la "
                    "respuesta."
                )
            )
        raw = function["arguments"]
        text = raw if isinstance(raw, str) else str(raw)
        preview = clean(text)[:_PREVIEW_CHARS]
        function["arguments"] = json.dumps({_UNREADABLE_ARGUMENTS: preview})


def _as_wire(raw: object) -> dict[str, Any]:
    """The response in the common wire shape, as a fresh dictionary that is only read."""
    dump = getattr(raw, "model_dump", None)
    wire = dump() if callable(dump) else copy.deepcopy(raw)
    if not isinstance(wire, dict):
        raise ProviderError(_BAD_RESPONSE)
    return wire


class LiteLLMProvider(Provider):
    """``Provider`` over LiteLLM; the dependencies come by constructor and nothing is read.

    Args:
        model: ``<provider>/<model>``, passed to LiteLLM as it is.
        max_output_tokens: Cap of the tokens the model may generate in one call; always sent.
        api_key: The key of the provider (a ``Secret``), or ``None`` if the provider needs none.
        completion: The async function that makes the call. By default, ``litellm.acompletion``
            loaded lazily; tests inject a fake one so that no library, network or key is needed.
    """

    def __init__(
        self,
        model: str,
        *,
        max_output_tokens: int,
        api_key: _Revealable | None = None,
        completion: CompletionFn | None = None,
    ) -> None:
        name, slash, tail = model.partition("/") if isinstance(model, str) else ("", "", "")
        if not (slash and name.strip() and tail.strip()):
            raise ValueError(_BAD_MODEL)
        if (
            isinstance(max_output_tokens, bool)
            or not isinstance(max_output_tokens, int)
            or max_output_tokens < 1
        ):
            raise ValueError(_BAD_CAP)
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._api_key = api_key
        self._completion = completion if completion is not None else _load_completion()

    @property
    def model(self) -> str:
        """The configured ``<provider>/<model>``."""
        return self._model

    @property
    def completion(self) -> CompletionFn:
        """The function that makes the call to the model."""
        return self._completion

    def __repr__(self) -> str:
        key = None if self._api_key is None else _HIDDEN_KEY
        return (
            f"LiteLLMProvider(model={self._model!r}, "
            f"max_output_tokens={self._max_output_tokens}, api_key={key})"
        )

    def _clean(self, text: str) -> str:
        """``text`` with the value of the key, if it appears, replaced by a marker."""
        key = None if self._api_key is None else self._api_key.reveal()
        return text.replace(key, _KEY_MARKER) if key else text

    def _canonical_error(self, error: Exception) -> ProviderError:
        """The canonical error for a failure of the library; its cause stays on the caller."""
        name = type(error).__name__
        for kind in type(error).__mro__:
            if kind.__name__ in ERROR_TABLE:
                canonical, template = ERROR_TABLE[kind.__name__]
                break
        else:
            canonical, template = _ANY_OTHER_FAILURE
        message = self._clean(template.format(kind=name))
        if issubclass(canonical, RateLimited):
            return canonical(message, retry_after=getattr(error, "retry_after", None))
        return canonical(message)

    def build_request(
        self, messages: Sequence[Message], tools: Sequence[ToolDefinition] | None
    ) -> dict[str, Any]:
        """Keyword arguments of the call: only canonical data, never a LiteLLM response object."""
        try:
            wire_messages = to_openai_messages(_with_error_tags(messages))
            wire_tools = to_openai_tools(None if tools is None else list(tools))
        except ConversionError as exc:
            raise ProviderError(_BAD_HISTORY) from exc
        request: dict[str, Any] = {
            "model": self._model,
            "messages": wire_messages,
            "max_tokens": self._max_output_tokens,
            "num_retries": 0,
        }
        if wire_tools:
            request["tools"] = wire_tools
        if self._api_key is not None:
            request["api_key"] = self._api_key.reveal()
        return request

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderResponse:
        """Call the model once and translate its answer to the canonical response."""
        request = self.build_request(messages, tools)
        try:
            raw = await self._completion(**request)
        except ProviderError:
            raise
        except Exception as exc:
            raise self._canonical_error(exc) from exc
        wire = _as_wire(raw)
        _mark_unreadable_arguments(wire, _free_form_tools(tools), self._clean)
        try:
            response = from_openai_response(wire)
        except ConversionError as exc:
            raise ProviderError(_BAD_RESPONSE) from exc
        if not response.content and not response.tool_calls:
            raise ProviderError(_EMPTY_RESPONSE)
        return response
