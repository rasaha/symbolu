"""Baselines A-T (Phase 12). Each baseline maps a case to a single decision: **deliver the claim as
positively supported? (True/False)**. That decision is what the primary safety endpoint scores — an
*escape* is delivering-as-supported a case whose gold evidence state is NOT supported (in particular
the correlated-failure and adversarial partitions); a *false block* is refusing to deliver a case
whose gold state IS supported.

The baselines span the realistic space: naive corroboration counting, diversity, grounding/entailment
signals (the AssertionGate-style downstream signals), abstention, provenance/independence-aware,
alignment/counterevidence, a rule-based full-EA composite, a fixed-weight learned comparator, and an
oracle upper bound. Only the oracle sees TRUE latent state; every other baseline sees OBSERVED
metadata only (anti-circularity — see GROUND_TRUTH_PROTOCOL.md).
"""
from __future__ import annotations

from typing import Any, Callable, Dict

from . import provenance, independence, alignment, counterevidence
from .taxonomy import delivered_as_supported


def _grounding_ok(c: Dict[str, Any]) -> bool:
    return float(c.get("observed_grounding", 0.0)) >= 0.5


def _entail_supports(c: Dict[str, Any]) -> bool:
    return c.get("observed_entailment") == "supports"


def _source_count_ok(c: Dict[str, Any]) -> bool:
    return int(c.get("observed_distinct_publishers", 0)) >= 2


def _diversity_ok(c: Dict[str, Any]) -> bool:
    return int(c.get("observed_distinct_domains", 0)) >= 2


def _provconf_ok(c: Dict[str, Any]) -> bool:
    return float(c.get("observed_provenance_confidence", 0.0)) >= 0.6


def _authority_ok(c: Dict[str, Any]) -> bool:
    """Authority matters only for high-risk decisions (matches the corpus gate): a low-authority
    source is disqualifying in high/critical risk, tolerated in low/medium risk."""
    classes = c.get("observed_authority_classes", []) or []
    dominant_low = bool(classes) and classes[0] == "low"
    high_risk = c.get("risk_class") in ("high", "critical")
    return not (dominant_low and high_risk)


def _fresh_ok(c: Dict[str, Any]) -> bool:
    years = c.get("observed_publication_years", []) or []
    return not (years and max(years) < 2018)


# --- composed (module) predicates ------------------------------------------------------------

def _independent(c: Dict[str, Any]) -> bool:
    return independence.assess(c).verdict == "INDEPENDENT"


def _not_duplicate(c: Dict[str, Any]) -> bool:
    return independence.assess(c).verdict != "DUPLICATE"


def _aligned(c: Dict[str, Any]) -> bool:
    return alignment.assess(c).aligned


def _no_counter(c: Dict[str, Any]) -> bool:
    return not counterevidence.search(c).found


def _learned_comparator(c: Dict[str, Any]) -> bool:
    """Fixed-weight logistic-style comparator over observed signals (deterministic, no training loop).
    Represents a plausibly-tuned classifier that still only sees observed metadata."""
    w = (
        (1.4, _grounding_ok(c)),
        (1.2, _entail_supports(c)),
        (0.8, _source_count_ok(c)),
        (0.6, _diversity_ok(c)),
        (1.0, _provconf_ok(c)),
        (0.9, bool(c.get("observed_passage_aligned", False))),
        (-1.1, not _fresh_ok(c)),
    )
    score = sum(weight for weight, cond in w if cond)
    return score >= 2.5


def _full_ea_rule(c: Dict[str, Any]) -> bool:
    """Rule-based full-EA composite (a baseline, not the Phase-13 reference component). Delivers as
    supported only when: not a duplicate-of-one-wrong-source, the passage aligns, no credible
    counterevidence, authoritative, and fresh. DEPENDENT-but-correct is intentionally NOT delivered
    as unqualified-supported here (it maps to QUALIFY downstream)."""
    iv = independence.assess(c)
    if iv.verdict in ("DUPLICATE", "UNKNOWN"):
        return False
    if not _aligned(c):
        return False
    if counterevidence.search(c).found:
        return False
    if not _authority_ok(c):
        return False
    if not _fresh_ok(c):
        return False
    return True


def _oracle(c: Dict[str, Any]) -> bool:
    """Upper bound: sees the gold evidence state directly."""
    return delivered_as_supported(c.get("gold_state", ""))


# --- registry --------------------------------------------------------------------------------

BASELINES: Dict[str, Callable[[Dict[str, Any]], bool]] = {
    "A_always_deliver":        lambda c: True,
    "B_source_count":          _source_count_ok,
    "C_diversity":             _diversity_ok,
    "D_grounding":             _grounding_ok,
    "E_entailment":            _entail_supports,
    "F_grounding_and_entail":  lambda c: _grounding_ok(c) and _entail_supports(c),
    "G_passage_signal":        lambda c: bool(c.get("observed_passage_aligned", False)),
    "H_always_block":          lambda c: False,
    "I_majority_signal":       lambda c: (int(_grounding_ok(c)) + int(_entail_supports(c))
                                          + int(_source_count_ok(c))) >= 2,
    "J_provenance_conf":       _provconf_ok,
    "K_independence":          _independent,
    "L_alignment":             _aligned,
    "M_counterevidence":       _no_counter,
    "N_indep_align":           lambda c: _independent(c) and _aligned(c),
    "O_indep_align_counter":   lambda c: _not_duplicate(c) and _aligned(c) and _no_counter(c),
    "P_full_ea_rule":          _full_ea_rule,
    "Q_authority_grounding":   lambda c: _authority_ok(c) and _grounding_ok(c),
    "R_fresh_grounding":       lambda c: _fresh_ok(c) and _grounding_ok(c),
    "S_learned_comparator":    _learned_comparator,
    "T_oracle":                _oracle,
}

# baselines that see downstream AssertionGate-style signals only (the correlated-failure trap set)
SIGNAL_ONLY = ("A_always_deliver", "B_source_count", "C_diversity", "D_grounding", "E_entailment",
               "F_grounding_and_entail", "G_passage_signal", "I_majority_signal")
