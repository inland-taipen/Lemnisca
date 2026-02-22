"""
Post-generation quality checks.

Three flags are produced:

  no_context       — zero chunks were retrieved; the answer is ungrounded.
  refusal          — the model explicitly declined to answer.
  pricing_conflict — three or more distinct dollar figures appear in one
                     pricing-related answer, suggesting the model merged
                     inconsistent source documents.
"""

import re


# Flag identifiers


NO_CONTEXT       = "no_context"
REFUSAL          = "refusal"
PRICING_CONFLICT = "pricing_conflict"


# Refusal detection


_REFUSAL_RX = [
    r"i (don'?t|do not) (have|know|see|find)",
    r"not (mentioned|found|available|provided|specified|covered)",
    r"(cannot|can'?t) (find|answer|help|provide|access)",
    r"no information",
    r"(not|isn'?t) in (the|my|our) (document|doc|knowledge|context|data)",
    r"i'?m (unable|not able) to",
    r"this (information|detail) is not",
    r"(sorry|apologize).*?(don'?t|cannot|can'?t)",
    r"outside (my|the) (scope|knowledge|context)",
    r"i (lack|have no) (information|access|data)",
]


# Pricing conflict detection


_DOLLAR_RE = re.compile(r"\$\s*[\d,]+(?:\.\d{1,2})?")
_PRICING_WORDS = frozenset(
    "price pricing plan cost subscription fee monthly annually".split()
)

def _distinct_amounts(text: str) -> int:
    raw_matches = _DOLLAR_RE.findall(text)
    values: set[float] = set()
    for m in raw_matches:
        cleaned = m.replace("$", "").replace(",", "").strip()
        try:
            values.add(float(cleaned))
        except ValueError:
            pass
    return len(values)


# Public interface


def run_quality_checks(answer: str, chunk_count: int, query: str = "") -> list[str]:
    flags: list[str] = []
    low = answer.lower()

    if chunk_count == 0:
        flags.append(NO_CONTEXT)

    if any(re.search(rx, low) for rx in _REFUSAL_RX):
        flags.append(REFUSAL)

    mentions_pricing = (
        any(w in low for w in _PRICING_WORDS)
        or any(w in query.lower() for w in _PRICING_WORDS)
    )
    if mentions_pricing and _distinct_amounts(answer) >= 3:
        flags.append(PRICING_CONFLICT)

    return flags


def describe_flags(flags: list[str]) -> str:
    if not flags:
        return ""
    labels = {
        NO_CONTEXT:       "answered without retrieved context",
        REFUSAL:          "model could not find a clear answer",
        PRICING_CONFLICT: "multiple price figures detected — may conflict",
    }
    detail = "; ".join(labels.get(f, f) for f in flags)
    return f"Low confidence — please verify with support. ({detail})"
