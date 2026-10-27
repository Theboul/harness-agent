"""Context window pieces: token estimation and the stable prefix (HU-02-01)."""

from __future__ import annotations

from harness_agent.core.context.assembler import AssembledContext, ContextAssembler
from harness_agent.core.context.compactor import CompactionResult, ContextCompactor
from harness_agent.core.context.cut import (
    HistoryParts,
    choose_cut,
    is_real,
    rebuild_history,
    split_history,
)
from harness_agent.core.context.errors import (
    CompactionError,
    ContextConfigError,
    SummaryRejected,
)
from harness_agent.core.context.estimator import (
    TokenEstimator,
    estimate_message,
    estimate_messages,
    estimate_text,
    estimate_tool_definition,
)
from harness_agent.core.context.prefix import PrefixSpec, StablePrefix, build_prefix
from harness_agent.core.context.settings import (
    CONTEXT_FIELD_RANGES,
    ContextSettings,
    recent_budget_tokens,
    requirement_of,
    summary_cap_tokens,
    threshold_tokens,
)
from harness_agent.core.context.store import (
    CompactionCommit,
    CompactionReceipt,
    CompactionStore,
    MessageEvent,
)
from harness_agent.core.context.summary import (
    FRAME_HEADER,
    build_summary_request,
    check_summary,
    clean_summary,
    frame_summary,
    is_summary,
    render_transcript,
    summary_prompt,
    summary_text,
)

__all__ = [
    "CONTEXT_FIELD_RANGES",
    "FRAME_HEADER",
    "AssembledContext",
    "CompactionCommit",
    "CompactionError",
    "CompactionReceipt",
    "CompactionResult",
    "CompactionStore",
    "ContextAssembler",
    "ContextCompactor",
    "ContextConfigError",
    "ContextSettings",
    "HistoryParts",
    "MessageEvent",
    "PrefixSpec",
    "StablePrefix",
    "SummaryRejected",
    "TokenEstimator",
    "build_prefix",
    "build_summary_request",
    "check_summary",
    "choose_cut",
    "clean_summary",
    "estimate_message",
    "estimate_messages",
    "estimate_text",
    "estimate_tool_definition",
    "frame_summary",
    "is_real",
    "is_summary",
    "rebuild_history",
    "recent_budget_tokens",
    "render_transcript",
    "requirement_of",
    "split_history",
    "summary_cap_tokens",
    "summary_prompt",
    "summary_text",
    "threshold_tokens",
]
