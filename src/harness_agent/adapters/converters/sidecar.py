"""Conversion envelope and metadata sidecar (design D-02, HU-07-01).

Provider wire formats cannot carry local canonical attributes (``Message.is_external``,
``ToolResult.is_error`` with OpenAI, ``Message.usage``, a TOOL ``Message.content`` that differs from
``ToolResult.content``). A ``ConversionEnvelope`` keeps the wire payload and those local attributes
together so that ``restore_messages(envelope)`` is the only restoration path; nothing is ever
written into a provider payload.

Honest limits (D-02 section 4.1):

* The SHA-256 digests prove CONTENT integrity, not which conversion produced a payload. Two
  conversions whose messages differ only in local metadata produce identical payloads and digests.
* Choosing the wrong envelope cannot be detected. ``conversion_id`` is a local trace identifier,
  not a security token.
* There is no protection against code that manipulates objects in the same process.
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from harness_agent.adapters.converters.base import ConversionError
from harness_agent.core.entities import Message, Role, TokenUsage

WireKind = Literal["system", "system_block", "message", "message_block"]


def canonical_json(value: Any) -> str:
    """Serialize ``value`` as strict, canonical JSON (sorted keys, compact, no NaN/Infinity)."""
    try:
        return json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise ConversionError(f"Value is not strict JSON and cannot be snapshotted: {exc}") from exc


def content_digest(text: str) -> str:
    """Return the SHA-256 hex digest of ``text`` (UTF-8)."""
    try:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except UnicodeEncodeError as exc:
        raise ConversionError(f"Text is not valid Unicode and cannot be digested: {exc}") from exc


def wire_digest(elements: list[Any]) -> str:
    """Digest of the canonical JSON of the wire elements an entry refers to."""
    return content_digest(canonical_json(elements))


@dataclass(frozen=True)
class WireRef:
    """Reference to an element of the external payload."""

    kind: WireKind
    message_index: int | None = None
    block_index: int | None = None


@dataclass(frozen=True)
class MessageMeta:
    """Local metadata of ONE canonical message (scalars, enums and tuples only).

    ``omitted`` marks a canonical SYSTEM message with empty content that the provider payload
    cannot represent (Anthropic): it has no ``refs`` but its existence and position are kept.
    """

    index: int
    role: Role
    refs: tuple[WireRef, ...]
    wire_digest: str
    is_external: bool
    tool_call_id: str | None = None
    tool_is_error: bool | None = None
    tool_message_content: str | None = None
    usage: TokenUsage | None = None
    omitted: bool = False


_BUILD_KEY = object()


class ConversionEnvelope:
    """Immutable pairing of a provider payload (JSON snapshot) with per-message metadata.

    Created only by ``to_provider_envelope``; the constructor is not public API.
    """

    __slots__ = (
        "_snapshot",
        "conversion_id",
        "entries",
        "partial_window",
        "payload_digest",
        "provider",
    )

    provider: str
    conversion_id: str
    partial_window: bool
    payload_digest: str
    entries: tuple[MessageMeta, ...]
    _snapshot: str

    def __init__(
        self,
        key: object,
        provider: str,
        payload: dict[str, Any],
        entries: tuple[MessageMeta, ...],
        partial_window: bool,
    ) -> None:
        if key is not _BUILD_KEY:
            raise TypeError("ConversionEnvelope is created by to_provider_envelope() only")
        snapshot = canonical_json(payload)
        if json.loads(snapshot) != payload:
            raise ConversionError(
                "Payload is not representable as strict JSON without silent coercion "
                "(non-string keys or tuples)."
            )
        object.__setattr__(self, "_snapshot", snapshot)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "conversion_id", uuid.uuid4().hex)
        object.__setattr__(self, "partial_window", partial_window)
        object.__setattr__(self, "payload_digest", content_digest(snapshot))
        object.__setattr__(self, "entries", tuple(entries))

    @classmethod
    def _create(
        cls,
        *,
        provider: str,
        payload: dict[str, Any],
        entries: tuple[MessageMeta, ...],
        partial_window: bool = False,
    ) -> ConversionEnvelope:
        return cls(_BUILD_KEY, provider, payload, entries, partial_window)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"ConversionEnvelope is immutable; cannot set {name!r}")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"ConversionEnvelope is immutable; cannot delete {name!r}")

    @property
    def payload(self) -> dict[str, Any]:
        """A NEW deep copy of the payload on every access."""
        result: dict[str, Any] = json.loads(self._snapshot)
        return copy.deepcopy(result)

    def matches(self, payload: dict[str, Any]) -> bool:
        """True when ``payload`` has exactly the content of this envelope's payload.

        Proves content integrity only; it does not identify which conversion produced it.
        """
        try:
            return content_digest(canonical_json(payload)) == self.payload_digest
        except ConversionError:
            return False

    def __repr__(self) -> str:
        return (
            f"ConversionEnvelope(provider={self.provider!r}, conversion_id={self.conversion_id!r}, "
            f"entries={len(self.entries)}, partial_window={self.partial_window})"
        )


# --- Helpers shared by the provider converters --------------------------------------------------


def meta_for_message(
    index: int,
    message: Message,
    refs: tuple[WireRef, ...],
    elements: list[Any],
    *,
    omitted: bool = False,
) -> MessageMeta:
    """Build the metadata of one canonical message (local attributes + digest of its wire part)."""
    tool_call_id: str | None = None
    tool_is_error: bool | None = None
    tool_message_content: str | None = None
    if message.role == Role.TOOL and message.tool_result is not None:
        tool_call_id = message.tool_result.call_id
        tool_is_error = message.tool_result.is_error
        if message.content != message.tool_result.content:
            tool_message_content = message.content
    return MessageMeta(
        index=index,
        role=message.role,
        refs=refs,
        wire_digest=wire_digest(elements),
        is_external=message.is_external,
        tool_call_id=tool_call_id,
        tool_is_error=tool_is_error,
        tool_message_content=tool_message_content,
        usage=message.usage,
        omitted=omitted,
    )


def _ref_key(ref: WireRef) -> tuple[int, int, int]:
    block = -1 if ref.block_index is None else ref.block_index
    message = -1 if ref.message_index is None else ref.message_index
    if ref.kind == "system":
        return (0, 0, 0)
    if ref.kind == "system_block":
        return (0, block, 0)
    if ref.kind == "message":
        return (1, message, 0)
    return (1, message, block + 1)


def resolve_ref(payload: dict[str, Any], ref: WireRef) -> Any:
    """Return the payload element a reference points to or fail closed."""
    where = f"reference {ref}"
    if ref.kind in ("system", "system_block"):
        if "system" not in payload:
            raise ConversionError(f"{where} points to a missing 'system' parameter")
        system = payload["system"]
        if ref.kind == "system":
            if not isinstance(system, str):
                raise ConversionError(f"{where} expects 'system' to be a string")
            return system
        if not isinstance(system, list) or ref.block_index is None:
            raise ConversionError(f"{where} expects 'system' to be a list of blocks")
        return _at(system, ref.block_index, where)
    messages = payload.get("messages")
    if not isinstance(messages, list) or ref.message_index is None:
        raise ConversionError(f"{where} points to a missing 'messages' list")
    element = _at(messages, ref.message_index, where)
    if ref.kind == "message":
        return element
    content = element.get("content") if isinstance(element, dict) else None
    if not isinstance(content, list) or ref.block_index is None:
        raise ConversionError(f"{where} expects message content to be a list of blocks")
    return _at(content, ref.block_index, where)


def _at(items: list[Any], index: int, where: str) -> Any:
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(items):
        raise ConversionError(f"{where} is out of range")
    return items[index]


def _expected_elements(payload: dict[str, Any], used_blocks: set[int]) -> set[tuple[str, int, int]]:
    expected: set[tuple[str, int, int]] = set()
    system = payload.get("system")
    if isinstance(system, str):
        expected.add(("system", 0, 0))
    elif isinstance(system, list):
        expected.update(("system_block", 0, i) for i in range(len(system)))
    messages = payload.get("messages")
    if not isinstance(messages, list):
        raise ConversionError("Payload has no 'messages' list")
    for i, element in enumerate(messages):
        if i in used_blocks:
            content = element.get("content") if isinstance(element, dict) else None
            if not isinstance(content, list):
                raise ConversionError(
                    f"messages[{i}] is referenced by blocks but has no block list"
                )
            expected.update(("message_block", i, b) for b in range(len(content)))
        else:
            expected.add(("message", i, 0))
    return expected


def verify_structure(envelope: ConversionEnvelope, provider: str) -> dict[str, Any]:
    """Verify entry continuity, reference resolution, order, coverage and digests.

    Returns a fresh payload copy. Role/field compatibility is checked by each provider while
    rebuilding messages. Any failure raises ``ConversionError``.
    """
    if envelope.provider != provider:
        raise ConversionError(
            f"Envelope was created for provider {envelope.provider!r}, not {provider!r}"
        )
    payload = envelope.payload
    if content_digest(canonical_json(payload)) != envelope.payload_digest:
        raise ConversionError("Envelope payload digest does not match its snapshot")

    last_key: tuple[int, int, int] | None = None
    covered: dict[tuple[str, int, int], int] = {}
    used_blocks: set[int] = set()
    for position, entry in enumerate(envelope.entries):
        if entry.index != position:
            raise ConversionError(
                f"Envelope entry {position} has index {entry.index}; entries must be contiguous"
            )
        if entry.omitted:
            if entry.refs or entry.role != Role.SYSTEM:
                raise ConversionError(
                    f"Envelope entry {position}: only SYSTEM entries without references "
                    "can be omitted"
                )
        elif not entry.refs:
            raise ConversionError(f"Envelope entry {position} has no payload references")
        elements: list[Any] = []
        for ref in entry.refs:
            key = _ref_key(ref)
            if last_key is not None and key <= last_key:
                raise ConversionError(
                    f"Envelope entry {position}: references are out of order or repeated ({ref})"
                )
            last_key = key
            elements.append(resolve_ref(payload, ref))
            if ref.kind == "message_block" and ref.message_index is not None:
                used_blocks.add(ref.message_index)
            slot = (ref.kind, ref.message_index or 0, ref.block_index or 0)
            if ref.kind in ("system", "system_block"):
                slot = (ref.kind, 0, ref.block_index or 0)
            covered[slot] = covered.get(slot, 0) + 1
        if wire_digest(elements) != entry.wire_digest:
            raise ConversionError(
                f"Envelope entry {position}: payload content does not match its digest"
            )

    if any(count != 1 for count in covered.values()):
        raise ConversionError("Envelope references overlap: an element is covered more than once")
    expected = _expected_elements(payload, used_blocks)
    if set(covered) != expected:
        missing = sorted(expected - set(covered))
        extra = sorted(set(covered) - expected)
        raise ConversionError(
            f"Envelope does not cover the payload exactly (uncovered: {missing}, unknown: {extra})"
        )
    return payload
