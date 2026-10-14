"""
Extract live governance signals from a running agent conversation.

These feed into SERAPH's distillation defense vector in real time —
one extraction per tool proposal, before govern() is called.
"""

from __future__ import annotations

import math
import re
from typing import Any

_INJECTION = re.compile(
    r"ignore (previous|prior|all) instructions"
    r"|pretend (you have no|you are|to be)"
    r"|you are now\b"
    r"|act as (if|though|a)\b"
    r"|jailbreak|(?<!\w)DAN(?!\w)"
    r"|without (restrictions|guidelines|ethics)"
    r"|override (your|the) (instructions|rules|training)"
    r"|forget (your|the) (training|instructions|rules)"
    r"|as an? (AI|assistant|model) (with no|without)",
    re.IGNORECASE,
)


def _text_from_message(msg: dict[str, Any]) -> str:
    content = msg.get("content", "")
    if isinstance(content, list):
        return " ".join(
            (b.get("text", "") if isinstance(b, dict) else getattr(b, "text", ""))
            for b in content
            if (isinstance(b, dict) and b.get("type") == "text")
            or (hasattr(b, "type") and getattr(b, "type") == "text")
        )
    return str(content)


def semantic_load_variance(messages: list[dict[str, Any]]) -> float:
    """Normalized std-dev of assistant message lengths. Low = stable, high = erratic."""
    lengths = [
        len(_text_from_message(m))
        for m in messages
        if m.get("role") == "assistant"
    ]
    if len(lengths) < 2:
        return 0.05
    mean = sum(lengths) / len(lengths)
    std = math.sqrt(sum((l - mean) ** 2 for l in lengths) / len(lengths))
    return min(1.0, std / 600.0)


def topic_coherence(tool_call_history: list[str]) -> float:
    """Consistency of tool usage. 1.0 = focused, 0.0 = chaotic."""
    recent = tool_call_history[-8:]
    if len(recent) < 2:
        return 0.9
    ratio = len(set(recent)) / len(recent)
    return max(0.05, 1.0 - ratio * 0.85)


def symbolic_pressure(messages: list[dict[str, Any]]) -> float:
    """Injection / manipulation pressure score from recent user messages."""
    for m in reversed(messages[-5:]):
        if m.get("role") != "user":
            continue
        if _INJECTION.search(_text_from_message(m)):
            return 0.92
    return 0.0


def operator_adaptation(
    tool_call_history: list[str],
    allowed_names: set[str],
) -> float:
    """Fraction of calls within the approved tool set."""
    if not tool_call_history:
        return 1.0
    return sum(1 for t in tool_call_history if t in allowed_names) / len(tool_call_history)


def extract(
    messages: list[dict[str, Any]],
    tool_call_history: list[str],
    allowed_names: set[str],
) -> dict[str, float]:
    """Return a complete DistillationDefenseVector kwargs dict."""
    return {
        "semantic_load_variance": semantic_load_variance(messages),
        "timing_variance": 0.08,
        "operator_adaptation": operator_adaptation(tool_call_history, allowed_names),
        "topic_coherence": topic_coherence(tool_call_history),
        "recursion_depth": 0.0,
        "symbolic_pressure": symbolic_pressure(messages),
    }
