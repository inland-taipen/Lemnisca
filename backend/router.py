"""
Deterministic query classifier — eight ordered rules, first match wins.

Simple  → llama-3.1-8b-instant   (greetings, short look-ups, single-fact)
Complex → llama-3.3-70b-versatile (reasoning, comparison, complaints, multi-step)
"""

import json
import logging
import re
from pathlib import Path
from typing import Literal, TypedDict


# Logging


_LOG_DIR = Path(__file__).resolve().parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_logger = logging.getLogger("query_router")
_logger.setLevel(logging.INFO)
_fh = logging.FileHandler(_LOG_DIR / "routing.log")
_fh.setFormatter(logging.Formatter("%(message)s"))
_logger.addHandler(_fh)


# Types & constants


Tier  = Literal["simple", "complex"]
Model = Literal["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]

_FAST:  Model = "llama-3.1-8b-instant"
_HEAVY: Model = "llama-3.3-70b-versatile"

class Decision(TypedDict):
    query: str
    classification: Tier
    model_used: Model
    rule_triggered: str
    tokens_input: int
    tokens_output: int
    latency_ms: float


# Pattern banks


_GREETINGS = frozenset(
    "hi hello hey greetings howdy sup yo thanks bye goodbye cheers".split()
) | {"good morning", "good afternoon", "good evening", "thank you"}

_FACT_PATTERNS = [
    r"\bwhat (is|are)\b", r"\bwho is\b", r"\bwhen (is|was|did)\b",
    r"\bwhat version\b",  r"\bwhat does\b", r"\bname (the|a|an)\b",
    r"\blist (the|all|any)\b", r"\bhow (many|much)\b", r"\bwhere (is|are|can)\b",
]

_REASONING_PATTERNS = [
    r"\bwhy\b", r"\bhow does\b", r"\bhow do\b", r"\bhow (to|can i)\b",
    r"\bexplain\b", r"\bdescribe\b",
    r"\bcompare\b", r"\bcomparison\b", r"\bdifference between\b",
    r"\bversus\b", r"\bvs\.?\b",
    r"\bpros and cons\b", r"\badvantages\b", r"\bdisadvantages\b",
    r"\brecommend\b", r"\bsuggestion\b", r"\bbest practice\b",
    r"\btroubleshoot\b", r"\bdebug\b", r"\bfixing\b",
    r"\bintegrat\b", r"\bmigrat\b",
    r"\bsetup\b", r"\bconfigur\b",
    r"\bstep.by.step\b", r"\bwalkthrough\b",
    r"\bscenario\b", r"\buse[- ]case\b",
]

_COMPLAINT_PATTERNS = [
    r"\bnot working\b", r"\bbroken\b", r"\bfailed\b", r"\bfailure\b",
    r"\bissue\b", r"\bproblem\b", r"\berror\b", r"\bbug\b",
    r"\bcan'?t\b", r"\bcannot\b", r"\bdoesn'?t work\b", r"\bwon'?t\b",
    r"\bstuck\b", r"\bkeep(s)? (getting|showing|failing)\b",
    r"\bnot (able|loading|responding)\b",
]

_COND_OPENERS = [r"\bif\b", r"\bwhen\b", r"\bunless\b"]
_COND_ACTIONS = [r"\bthen\b", r"\bshould\b", r"\bwill\b", r"\bdo\b", r"\bcan\b"]


# Helpers


def _wc(text: str) -> int:
    return len(text.split())

def _qm(text: str) -> int:
    return text.count("?")

def _has(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, re.I) for p in patterns)

def _is_greeting(text: str) -> bool:
    stripped = text.lower().strip().rstrip("!. ")
    if stripped in _GREETINGS:
        return True
    first = stripped.split()[0] if stripped.split() else ""
    return first in _GREETINGS and _wc(stripped) <= 5


# Classifier — eight rules, deterministic


def _classify(q: str) -> tuple[Tier, str]:
    words, qmarks = _wc(q), _qm(q)

    if _is_greeting(q):                                      return "simple",  "R1_greeting"
    if words <= 5 and qmarks <= 1:                           return "simple",  "R2_short"
    if words < 15 and qmarks <= 1 and _has(_FACT_PATTERNS, q) and not _has(_COMPLAINT_PATTERNS, q):
                                                             return "simple",  "R3_fact_lookup"
    if words >= 25:                                          return "complex", "R4_long"
    if qmarks >= 2:                                          return "complex", "R5_multi_question"
    if _has(_REASONING_PATTERNS, q):                         return "complex", "R6_reasoning"
    if _has(_COMPLAINT_PATTERNS, q):                         return "complex", "R7_complaint"
    if _has(_COND_OPENERS, q) and _has(_COND_ACTIONS, q):   return "complex", "R8_conditional"

    return "simple", "R_default"


# Public interface


def classify_and_route(query: str) -> Decision:
    tier, rule = _classify(query.strip())
    return Decision(
        query=query,
        classification=tier,
        model_used=_FAST if tier == "simple" else _HEAVY,
        rule_triggered=rule,
        tokens_input=0,
        tokens_output=0,
        latency_ms=0.0,
    )

def persist_decision(d: Decision) -> None:
    entry = json.dumps({k: d[k] for k in d})  # type: ignore[literal-required]
    _logger.info(entry)
    print(f"[router] {entry}")
