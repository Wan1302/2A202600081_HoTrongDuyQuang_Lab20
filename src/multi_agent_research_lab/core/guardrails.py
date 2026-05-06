"""Input guardrails for research queries."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InputGuardrailResult:
    """Decision returned by the input guardrail."""

    allowed: bool
    reason: str


_GREETING_PATTERNS = (
    r"^\s*(hi|hello|hey|xin chào|chào|cảm ơn|thanks|thank you)\s*[.!?]*\s*$",
    r"^\s*(test|ping)\s*$",
)

_BLOCKED_PATTERNS = (
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"reveal\s+(the\s+)?(system\s+)?prompt",
    r"(show|print|leak|reveal).*(api[_\s-]?key|secret|token|password)",
    r"bypass\s+(guardrails|safety|policy)",
)

_RESEARCH_KEYWORDS = {
    "analyze",
    "analysis",
    "benchmark",
    "compare",
    "evaluate",
    "explain",
    "guardrail",
    "guardrails",
    "investigate",
    "overview",
    "research",
    "review",
    "summarize",
    "summary",
    "state-of-the-art",
    "sota",
    "why",
    "phân tích",
    "so sánh",
    "nghiên cứu",
    "tóm tắt",
    "giải thích",
    "đánh giá",
}


def validate_research_query(query: str) -> InputGuardrailResult:
    """Decide whether a query is worth running through the research workflow."""

    normalized = " ".join(query.strip().split())
    lowered = normalized.lower()
    if len(normalized) < 8:
        return InputGuardrailResult(False, "Query is too short to run a research workflow.")

    for pattern in _GREETING_PATTERNS:
        if re.search(pattern, lowered):
            return InputGuardrailResult(
                False,
                "Query is a greeting/test message, not a research task.",
            )

    for pattern in _BLOCKED_PATTERNS:
        if re.search(pattern, lowered):
            return InputGuardrailResult(
                False,
                "Query appears to request secrets, prompt leakage, or bypass behavior.",
            )

    word_count = len(normalized.split())
    has_research_keyword = any(keyword in lowered for keyword in _RESEARCH_KEYWORDS)
    if word_count < 4 and not has_research_keyword:
        return InputGuardrailResult(
            False,
            "Query is too underspecified for meaningful research.",
        )

    if word_count < 7 and not has_research_keyword and len(normalized) < 40:
        return InputGuardrailResult(
            False,
            "Query does not look like a research, comparison, analysis, or summary task.",
        )

    return InputGuardrailResult(True, "Query is suitable for research.")
