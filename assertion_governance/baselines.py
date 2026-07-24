"""Comparison baselines (Phase 5). Each maps item features to a disposition using ONE family of
signal. Tunable baselines (B/C/E) are grid-searched on the DEV split for their best shot. D and G
are "entailment/grounding" systems that read the categorical relation + grounding scalar. G_risk
augments G with a risk rule — included to test whether AGE reduces to "G plus a risk rule" (H0-8 /
anti-circularity). All deterministic; no learning beyond threshold selection on dev.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from assertion_governance.dataset import Item, split
from assertion_governance.taxonomy import Disposition, to_primary

D = Disposition
_HIGH = ("high", "critical")


# --- Baseline A: no governance --------------------------------------------
def base_A(it: Item) -> str:
    return D.ALLOW.value


# --- Baseline B: confidence threshold (tunable) ----------------------------
def make_base_B(thr: float) -> Callable[[Item], str]:
    def f(it: Item) -> str:
        return D.ALLOW.value if it.model_confidence >= thr else D.INDETERMINATE.value
    return f


# --- Baseline C: grounding threshold (tunable hi/lo) -----------------------
def make_base_C(hi: float, lo: float) -> Callable[[Item], str]:
    def f(it: Item) -> str:
        if it.evidence_support >= hi:
            return D.ALLOW.value
        if it.evidence_support <= lo:
            return D.REJECT.value
        return D.INDETERMINATE.value
    return f


# --- Baseline D: entailment (3-way NLI) ------------------------------------
def base_D(it: Item) -> str:
    return {"supports": D.ALLOW.value, "contradicts": D.REJECT.value,
            "neutral": D.INDETERMINATE.value, "missing": D.INDETERMINATE.value,
            "conflicting": D.INDETERMINATE.value}[it.evidence_relation]


# --- Baseline E: rule-based qualification (evidence-blind, tunable) --------
def make_base_E(thr: float) -> Callable[[Item], str]:
    def f(it: Item) -> str:
        # hedge whenever the claim is strongly worded, regardless of evidence
        return D.QUALIFY.value if it.claim_strength >= thr else D.ALLOW.value
    return f


# --- Baseline F: authority resolution (TAP-style) --------------------------
def base_F(it: Item) -> str:
    return {"yes": D.ALLOW.value, "conflict": D.ESCALATE.value, "no": D.INDETERMINATE.value}[
        it.authority_governed]


# --- Baseline G: grounding + entailment (risk-blind) -----------------------
def make_base_G(overclaim_margin: float) -> Callable[[Item], str]:
    def f(it: Item) -> str:
        rel = it.evidence_relation
        if rel == "contradicts":
            return D.REJECT.value
        if rel == "missing":
            return D.NOT_SUPPORTED.value
        if rel == "conflicting":
            return D.INDETERMINATE.value
        if rel == "neutral":
            return D.INDETERMINATE.value
        # supports
        if it.claim_strength - it.evidence_support <= overclaim_margin:
            return D.ALLOW.value
        return D.QUALIFY.value
    return f


# --- Baseline G_risk: G + a risk rule (== AGE's claimed extra) -------------
def make_base_G_risk(overclaim_margin: float, big_gap: float) -> Callable[[Item], str]:
    g = make_base_G(overclaim_margin)
    def f(it: Item) -> str:
        base = g(it)
        high = it.risk_class in _HIGH
        rel = it.evidence_relation
        if high and rel in ("missing", "conflicting"):
            return D.ESCALATE.value
        if high and base == D.QUALIFY.value and (it.claim_strength - it.evidence_support) >= big_gap:
            return D.ESCALATE.value
        return base
    return f


# --- tuning (dev split, best shot) -----------------------------------------

def _agreement(fn: Callable[[Item], str], items: List[Item]) -> float:
    ok = sum(1 for it in items if to_primary(D(fn(it))) == to_primary(D(it.gold_disposition)))
    return ok / len(items)


def tune() -> Dict[str, Callable[[Item], str]]:
    dev = split("dev")
    bestB = max((thr for thr in [i / 20 for i in range(0, 21)]),
                key=lambda t: _agreement(make_base_B(t), dev))
    bestC = max(((hi, lo) for hi in [i / 20 for i in range(10, 21)] for lo in [i / 20 for i in range(0, 11)]),
                key=lambda hl: _agreement(make_base_C(*hl), dev))
    bestE = max((thr for thr in [i / 20 for i in range(0, 21)]),
                key=lambda t: _agreement(make_base_E(t), dev))
    bestG = max((m for m in [i / 20 for i in range(0, 11)]),
                key=lambda m: _agreement(make_base_G(m), dev))
    bestGr = max(((m, g) for m in [i / 20 for i in range(0, 11)] for g in [i / 10 for i in range(2, 7)]),
                 key=lambda mg: _agreement(make_base_G_risk(*mg), dev))
    return {
        "A_none": base_A,
        "B_confidence": make_base_B(bestB),
        "C_grounding": make_base_C(*bestC),
        "D_entailment": base_D,
        "E_rule_qualify": make_base_E(bestE),
        "F_authority": base_F,
        "G_ground_entail": make_base_G(bestG),
        "G_risk": make_base_G_risk(*bestGr),
    }


def tuned_params() -> Dict:
    dev = split("dev")
    return {
        "B_thr": max([i / 20 for i in range(0, 21)], key=lambda t: _agreement(make_base_B(t), dev)),
        "G_margin": max([i / 20 for i in range(0, 11)], key=lambda m: _agreement(make_base_G(m), dev)),
    }
