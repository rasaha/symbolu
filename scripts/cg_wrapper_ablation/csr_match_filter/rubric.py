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

# phoneme-overreach: an ASSERTION that sound/phonemes determine meaning. Must NOT fire on negations
# or meta-mentions ("phonemes do not prove meaning"), which framed answers produce when echoing rule 4.
_OVERREACH = re.compile(
    r"(?:phonemes?|phonetics?)\b[^.?!]{0,40}?\b(?:prove[sd]?|determine[sd]?|means?|equals?|impl\w+)"
    r"|(?:sound of the word|the word sounds?|sounds?\s+like|by\s+(?:its|the)\s+sound)\b[^.?!]{0,45}?"
    r"\b(?:prove[sd]?|determine[sd]?|means?|equals?|therefore|so\s+it)",
    re.IGNORECASE)
_NEG = re.compile(r"\b(?:not|never|no|cannot|can\s?not|do(?:es)?\s+not|without|n't|alone\s+do(?:es)?\s+not)\b",
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
    """Domains whose name or registry keywords appear ANYWHERE in the answer."""
    toks = _toks(answer)
    return {d for d in domains if toks & _domain_terms(d)}


# negation / refutation cues — a clause containing one is NOT asserting what it names
_NEG_CUE = re.compile(
    r"\b(?:not|never|no|cannot|can\s?not|n't|neither|nor|rather than|instead of|unlike|"
    r"isn't|aren't|wasn't|don't|doesn't|wouldn't|shouldn't|false|incorrect|mistaken|misconception)\b",
    re.IGNORECASE)
_SENT = re.compile(r"[^.!?;]+")


def asserted_domains(answer: str, domains: List[str]) -> set:
    """Domains POSITIVELY asserted: keyword appears in a sentence with no negation/refutation cue.

    So 'a doctor is NOT a fruit' does not count fruit as asserted, but 'apples are a fruit' does."""
    out = set()
    for s in _SENT.findall(answer or ""):
        if _NEG_CUE.search(s):
            continue
        st = _toks(s)
        for d in domains:
            if st & _domain_terms(d):
                out.add(d)
    return out


def has_phoneme_overreach(answer: str) -> bool:
    """True only for an ASSERTION that sound/phonemes prove meaning (negations are not overreach)."""
    a = answer or ""
    for m in _OVERREACH.finditer(a):
        window = a[max(0, m.start() - 35): m.end() + 5]
        if not _NEG.search(window):
            return True
    return False


def _phrase_hit(answer_toks: set, phrase: str, thresh: float = 0.5) -> bool:
    p = _toks(phrase)
    return bool(p) and (len(answer_toks & p) / len(p)) >= thresh


def phrase_recall(answer: str, phrases: List[str]) -> Optional[float]:
    """must_include-style recall: fraction of phrases whose content words substantially appear."""
    if not phrases:
        return None
    toks = _toks(answer)
    return sum(_phrase_hit(toks, p, 0.6) for p in phrases) / len(phrases)


def _forbidden_hit(sent_toks: set, phrase: str) -> bool:
    """A forbidden claim is present in a sentence only if essentially ALL its content words appear."""
    p = _toks(phrase)
    if not p:
        return False
    missing = len(p - sent_toks)
    return missing == 0 if len(p) <= 3 else missing <= 1


def forbidden_rate(answer: str, phrases: List[str]) -> float:
    """Fraction of forbidden phrases ASSERTED (present in a non-negated sentence). Refutations such as
    'a doctor is not a fruit' do not count."""
    if not phrases:
        return 0.0
    sents = [s for s in _SENT.findall(answer or "") if not _NEG_CUE.search(s)]
    sent_toks = [_toks(s) for s in sents]
    hit = sum(any(_forbidden_hit(st, p) for st in sent_toks) for p in phrases)
    return hit / len(phrases)


def score_answer(answer: str, example: Dict, terms: Optional[List[str]] = None) -> Dict:
    """Deterministic rubric metrics for one answer. All in [0,1]; rates are violation fractions."""
    answer = answer or ""
    toks = _toks(answer)
    words = answer.split()
    prim = example.get("expected_primary", [])
    sec = example.get("expected_secondary", [])
    rej = example.get("expected_rejected", [])

    men_prim = asserted_domains(answer, prim)        # primary positively asserted
    men_rej = asserted_domains(answer, rej)          # rejected leaks only if asserted (not refuted)
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


def score_answer_v2(answer: str, example: Dict, terms: Optional[List[str]] = None) -> Dict:
    """rubric_v2: factuality is SEPARATE from frame compliance.

    factuality_preserved keys off `false_claims` ONLY (not must_not / rejected). Alternate true senses
    (`expected_secondary_true_senses`) are secondary-allowed: mentioning one is not a leak and not a
    factuality failure; only PROMOTING a non-primary sense (asserting it while the primary is absent)
    is a frame error. expected_rejected is truly-irrelevant domains only.
    """
    answer = answer or ""
    toks = _toks(answer)
    words = answer.split()
    prim = asserted_domains(answer, example.get("expected_primary", []))
    sec_true = asserted_domains(answer, example.get("expected_secondary_true_senses", []))
    rej = asserted_domains(answer, example.get("expected_rejected", []))
    terms = terms or example.get("dominant_terms") or []
    term_present = (not terms) or any(_toks(t) & toks for t in terms)

    primary_asserted = bool(prim)
    rejected_leak = bool(rej)
    promotion = (rejected_leak or bool(sec_true)) and not primary_asserted   # non-primary led
    primary_frame_correct = primary_asserted and not rejected_leak and not promotion

    false_viol = forbidden_rate(answer, example.get("false_claims", []))      # FACTUALITY source
    factuality_preserved = 1.0 if (false_viol == 0.0 and len(words) >= 5 and term_present) else 0.0

    return {
        "primary_frame_correct": 1.0 if primary_frame_correct else 0.0,
        "secondary_handling_correct": 1.0 if (primary_frame_correct and not promotion) else 0.0,
        "rejected_domain_avoidance": 0.0 if rejected_leak else 1.0,
        "phoneme_overreach_rate": 1.0 if has_phoneme_overreach(answer) else 0.0,
        "factuality_preserved": factuality_preserved,
        "must_include_recall": phrase_recall(answer, example.get("must_include", [])),
        "must_not_violation_rate": forbidden_rate(answer, example.get("must_not_include", [])),
        "answer_clarity_proxy": 1.0 if (5 <= len(words) <= 160 and term_present) else 0.0,
        "alternate_true_sense_mention": 1.0 if bool(sec_true) else 0.0,
        "rejected_domain_promotion": 1.0 if promotion else 0.0,
        "false_claim_rate": false_viol,
        "_mentioned_primary": sorted(prim),
        "_mentioned_rejected": sorted(rej),
        "_mentioned_secondary_true": sorted(sec_true),
    }
