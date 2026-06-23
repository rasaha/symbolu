"""kosha_conformance.py — DETERMINISTIC depth-conformance scorer for the Kosha K2 quality eval.
Pre-reg: docs/KOSHA_K2_QUALITY_EVAL_PREREG.md.

Given an answer + an INTENDED Kosha depth level, returns 1.0/0.0 for whether the answer's *structure*
matches that depth, via transparent rule-based checks. This is NOT an LLM judge and NOT a quality/
preference score — it measures only "did the answer take the intended depth shape." Honest caveat:
depth-conformance ≠ "better answer for the user" (that is a future K3 human/independent-judge eval).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict

_CSR = Path(__file__).resolve().parent.parent / "cg_wrapper_ablation"
if str(_CSR) not in sys.path:
    sys.path.insert(0, str(_CSR))
from csr_match_filter.kosha import KoshaLevel   # noqa: E402

# transparent marker lexicons (lowercased substring checks)
_STEP_RE = re.compile(r"(^|\n)\s*(\d+[.)]|[-*•])\s", re.M)           # numbered/bulleted list
_STEP_WORDS = ("first,", "first ", "firstly", "then ", "next,", "next ", "step ", "to begin",
               "start by", "begin by", "follow these")
_EMPATHY = ("understand", "i hear", "it's normal", "it is normal", "that's understandable",
            "concern", "don't worry", "do not worry", "reassur", "makes sense", "you might feel",
            "it can feel", "it's okay", "it is okay", "you're not alone", "take a breath")
_COMPARISON = ("compare", "however", "on the other hand", "whereas", "tradeoff", "trade-off",
               "pros", "cons", "advantage", "disadvantage", "alternatively", "versus", " vs ",
               "better suited", "depends on", "in contrast", "weigh")
_SYNTHESIS = ("overall", "in essence", "fundamentally", "underlying", "principle", "bigger picture",
              "ultimately", "in summary", "connects", "at its core", "the key idea", "taken together",
              "unifying", "broadly")

_ANNAMAYA_MAX_WORDS = 70        # surface answers should be concise
_TERSE_MIN_WORDS = 8            # below this = terse (guardrail metric)


def _has(a: str, needles) -> bool:
    return any(n in a for n in needles)


def has_steps(answer: str) -> bool:
    a = " " + answer.lower() + " "
    return bool(_STEP_RE.search(answer)) or _has(a, _STEP_WORDS)


def has_empathy(answer: str) -> bool:
    return _has(answer.lower(), _EMPATHY)


def has_comparison(answer: str) -> bool:
    return _has(" " + answer.lower() + " ", _COMPARISON)


def has_synthesis(answer: str) -> bool:
    return _has(answer.lower(), _SYNTHESIS)


def score_depth_conformance(answer: str, level) -> float:
    """1.0 if the answer structurally matches `level`, else 0.0. Deterministic. `level` is a KoshaLevel
    or its string value (the INTENDED depth, not the selector's prediction — avoids circularity)."""
    lvl = level if isinstance(level, KoshaLevel) else KoshaLevel(str(level).lower())
    answer = answer or ""
    wc = len(answer.split())
    if lvl is KoshaLevel.ANNAMAYA:
        return 1.0 if (_TERSE_MIN_WORDS <= wc <= _ANNAMAYA_MAX_WORDS) else 0.0
    if lvl is KoshaLevel.PRANAMAYA:
        return 1.0 if has_steps(answer) else 0.0
    if lvl is KoshaLevel.MANOMAYA:
        return 1.0 if has_empathy(answer) else 0.0
    if lvl is KoshaLevel.VIJNANAMAYA:
        return 1.0 if has_comparison(answer) else 0.0
    if lvl is KoshaLevel.ANANDAMAYA:
        return 1.0 if has_synthesis(answer) else 0.0
    return 0.0


def terse_rate_flag(answer: str) -> float:
    """1.0 if the answer is too terse (guardrail metric; over-shortening is a Kosha risk)."""
    return 1.0 if len((answer or "").split()) < _TERSE_MIN_WORDS else 0.0


def over_framing_flag(answer: str) -> float:
    """1.0 if the answer talks ABOUT frames/domains instead of answering (mechanical-artifact guard)."""
    a = (answer or "").lower()
    return 1.0 if _has(a, ("primary frame", "primary domain", "semantic frame", "rejected domain",
                           "secondary domain", "depth/readiness")) else 0.0


def conformance_features(answer: str, intended_level) -> Dict[str, float]:
    return {"depth_conformance": score_depth_conformance(answer, intended_level),
            "terse": terse_rate_flag(answer), "over_framing": over_framing_flag(answer),
            "word_count": float(len((answer or "").split()))}
