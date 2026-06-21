"""rubric.py — deterministic rubric scoring for the Phase 2 framed-answer eval.

These are RUBRIC PROXIES, not human evaluation: keyword/rule checks over the registry's domain
keywords + phoneme-overreach patterns. judge_backend = deterministic_rubric. An LLM-as-judge could be
added later behind the same `score_answer` interface. No Phase 1 scoring is modified.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from . import registry as REG

_WORD = re.compile(r"[a-z]+")
_STOP = {"a", "an", "the", "and", "or", "of", "to", "is", "are", "in", "on", "for", "by", "with",
         "it", "this", "that", "as", "be", "can", "may", "more", "than", "not", "but", "its"}

# phoneme-overreach: claiming sound/phonemes determine meaning
_OVERREACH = re.compile(
    r"phoneme|phonetic|"
    r"sound(?:s)?\s+(?:like|prove|alone|determine|mean)|"
    r"by\s+(?:its|the)\s+sound|the\s+sound\s+of\s+the\s+word|because\s+it\s+sounds",
    re.IGNORECASE)


def _toks(text: str) -> set:
    return {w for w in _WORD.findall((text or "").lower()) if w not in _STOP and len(w) > 2}


def _domain_terms(domain: str) -> set:
    kws = set(_toks(domain))
    t = REG.DOMAIN_TEMPLATES.get(domain)
    if t:
        kws |= set(t.keywords)
    return kws


def mentioned_domains(answer: str, domains: List[str]) -> set:
    """Domains whose name or registry keywords appear in the answer."""
    toks = _toks(answer)
    return {d for d in domains if toks & _domain_terms(d)}


def has_phoneme_overreach(answer: str) -> bool:
    return bool(_OVERREACH.search(answer or ""))


def _phrase_hit(answer_toks: set, phrase: str, thresh: float = 0.5) -> bool:
    p = _toks(phrase)
    return bool(p) and (len(answer_toks & p) / len(p)) >= thresh


def phrase_recall(answer: str, phrases: List[str]) -> Optional[float]:
    """must_include-style recall: fraction of phrases whose content words substantially appear."""
    if not phrases:
        return None
    toks = _toks(answer)
    return sum(_phrase_hit(toks, p, 0.6) for p in phrases) / len(phrases)


def _forbidden_hit(answer_toks: set, phrase: str) -> bool:
    """A forbidden claim counts as present only if essentially ALL its content words appear
    (conjunctive) — so 'doctor is a fruit' fires only when both 'doctor' AND 'fruit' are present."""
    p = _toks(phrase)
    if not p:
        return False
    missing = len(p - answer_toks)
    return missing == 0 if len(p) <= 3 else missing <= 1


def forbidden_rate(answer: str, phrases: List[str]) -> float:
    if not phrases:
        return 0.0
    toks = _toks(answer)
    return sum(_forbidden_hit(toks, p) for p in phrases) / len(phrases)


def score_answer(answer: str, example: Dict, terms: Optional[List[str]] = None) -> Dict:
    """Deterministic rubric metrics for one answer. All in [0,1]; rates are violation fractions."""
    answer = answer or ""
    toks = _toks(answer)
    words = answer.split()
    prim = example.get("expected_primary", [])
    sec = example.get("expected_secondary", [])
    rej = example.get("expected_rejected", [])

    men_prim = mentioned_domains(answer, prim)
    men_rej = mentioned_domains(answer, rej)
    overreach = has_phoneme_overreach(answer)
    mni = example.get("must_not_include", [])
    must_not_viol = forbidden_rate(answer, mni)
    terms = terms or example.get("dominant_terms") or []
    term_present = (not terms) or any(_toks(t) & toks for t in terms)

    primary_frame_correct = 1.0 if (men_prim and not men_rej) else 0.0
    rejected_domain_avoidance = 0.0 if men_rej else 1.0
    secondary_handling_correct = 1.0 if (men_prim and not men_rej) else 0.0
    factuality_preserved = 1.0 if (must_not_viol == 0.0 and len(words) >= 5 and term_present) else 0.0
    clarity = 1.0 if (5 <= len(words) <= 160 and term_present) else 0.0

    return {
        "primary_frame_correct": primary_frame_correct,
        "secondary_handling_correct": secondary_handling_correct,
        "rejected_domain_avoidance": rejected_domain_avoidance,
        "phoneme_overreach_rate": 1.0 if overreach else 0.0,
        "factuality_preserved": factuality_preserved,
        "must_include_recall": phrase_recall(answer, example.get("must_include", [])),
        "must_not_violation_rate": must_not_viol,
        "answer_clarity_proxy": clarity,
        "_mentioned_primary": sorted(men_prim),
        "_mentioned_rejected": sorted(men_rej),
    }
