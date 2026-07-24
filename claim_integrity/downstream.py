"""Downstream-impact adapter (Phase 18) + error propagation (Phase 19). READ-ONLY: maps a method's
decomposition to downstream governance outcomes WITHOUT modifying EvidenceAssurance or AssertionGate.

Model (grounded in the corpus's per-claim downstream_consequence):
 - A gold claim with consequence 'unsafe_allow' is one whose fragile dimension, if preserved, makes the
   thin gate WITHHOLD (QUALIFY/REJECT/ESCALATE) - because the faithful claim is hedged/negated/
   conditional/attributed/'no evidence'/etc. If decomposition DROPS that dimension, the altered claim
   is delivered-as-supported (ALLOW) -> UNSAFE DELIVERY.
 - A REFERENCE_ERROR (dangling pronoun) does not drop a dimension but ALTERS THE EVIDENCE QUERY (the
   subject is ambiguous), so evidence is retrieved for the wrong/undetermined entity -> reported
   separately as evidence_query_altered (a downstream harm, not counted as a definite unsafe allow).
 - An OMITTED claim is never governed -> the unsupported claim passes ungoverned -> UNSAFE.
 - Drift on a 'conservative_block' claim -> FALSE REJECTION.
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import validation
from .taxonomy import Disposition

_DROP_DRIFT = {Disposition.NEGATION_ERROR.value, Disposition.SCOPE_ERROR.value,
               Disposition.NUMERIC_ERROR.value, Disposition.ATTRIBUTION_ERROR.value,
               Disposition.QUALIFIER_LOSS.value, Disposition.INVENTED_CLAIM.value}


def outcomes(example: Dict[str, Any], produced: List[str]) -> Dict[str, int]:
    aud = validation.audit(example, produced)
    o = {"unsafe_delivery": 0, "false_rejection": 0, "evidence_query_altered": 0,
         "ungoverned_claim": 0, "correct_withhold": 0, "correct_allow": 0}
    for c in aud["per_claim"]:
        disp = c["disposition"]
        conseq = c["downstream_consequence"]
        if disp in (Disposition.VALID.value, Disposition.VALID_WITH_ALTERNATIVES.value):
            o["correct_withhold" if conseq == "unsafe_allow" else "correct_allow"] += 1
        elif disp == Disposition.OMITTED_CLAIM.value:
            o["ungoverned_claim"] += 1
            if conseq == "unsafe_allow":
                o["unsafe_delivery"] += 1
        elif disp == Disposition.REFERENCE_ERROR.value:
            o["evidence_query_altered"] += 1
        elif disp in _DROP_DRIFT:
            if conseq == "unsafe_allow":
                o["unsafe_delivery"] += 1
            else:
                o["false_rejection"] += 1
    return o


def score_method(examples: List[Dict[str, Any]], method) -> Dict[str, Any]:
    agg = {"unsafe_delivery": 0, "false_rejection": 0, "evidence_query_altered": 0,
           "ungoverned_claim": 0, "correct_withhold": 0, "correct_allow": 0}
    n_claims = 0
    for e in examples:
        produced = method(e)
        o = outcomes(e, produced)
        for k in agg:
            agg[k] += o[k]
        n_claims += len(e["gold_claims"])
    return {
        "n_gold_claims": n_claims,
        "unsafe_delivery": agg["unsafe_delivery"],
        "unsafe_delivery_rate": round(agg["unsafe_delivery"] / n_claims, 4),
        "false_rejection": agg["false_rejection"],
        "false_rejection_rate": round(agg["false_rejection"] / n_claims, 4),
        "evidence_query_altered": agg["evidence_query_altered"],
        "evidence_query_altered_rate": round(agg["evidence_query_altered"] / n_claims, 4),
        "ungoverned_claim": agg["ungoverned_claim"],
    }


# ---- Phase 19: error propagation --------------------------------------------------------------
# controlled single-dimension corruptions applied to the ORACLE decomposition, to isolate how each
# error type propagates to downstream outcome.
import re

def _corrupt(text: str, kind: str) -> str:
    if kind == "qualifier_deletion":
        return re.sub(r"\b(generally|typically|often|likely)\b", "", text, flags=re.I).replace("  ", " ")
    if kind == "negation_inversion":
        return re.sub(r"\b(does not|do not|not|no)\b", "", text, flags=re.I).replace("  ", " ")
    if kind == "temporal_deletion":
        return re.sub(r"\bas of \d{4},?\s*", "", text, flags=re.I)
    if kind == "population_broadening":
        return re.sub(r"\bin [a-z ]+?(patients|investors|firms|households|families|users|clients|contractors|operators|technicians|servers|hosts|teams)[a-z ]*", "", text, flags=re.I)
    if kind == "jurisdiction_deletion":
        return re.sub(r"\bin (the )?(eu|us|uk|california|this jurisdiction|the state|the company),?\s*", "", text, flags=re.I)
    if kind == "numeric_mutation":
        return re.sub(r"\d+", "99", text)
    if kind == "causal_inflation":
        return text.replace("associated with", "causes")
    if kind == "attribution_deletion":
        return re.sub(r"\baccording to [^,]+,\s*", "", text, flags=re.I)
    if kind == "modality_deletion":
        return re.sub(r"\b(may|might|can)\b", "", text, flags=re.I).replace("  ", " ")
    if kind == "exception_deletion":
        return re.sub(r",?\s*(except|unless)[^.]*", "", text, flags=re.I)
    return text


PERTURBATIONS = ["qualifier_deletion", "negation_inversion", "temporal_deletion",
                 "population_broadening", "jurisdiction_deletion", "numeric_mutation",
                 "causal_inflation", "attribution_deletion", "modality_deletion", "exception_deletion"]


def propagation_matrix(examples: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply each perturbation to the gold decomposition; report the downstream outcome distribution
    and whether the downstream layers (EA/gate, via the disposition adapter) CATCH it."""
    rows = {}
    for kind in PERTURBATIONS:
        def method(e, k=kind):
            return [_corrupt(g["text"], k) for g in e["gold_claims"]]
        s = score_method(examples, method)
        rows[kind] = {"unsafe_delivery_rate": s["unsafe_delivery_rate"],
                      "false_rejection_rate": s["false_rejection_rate"],
                      "evidence_query_altered_rate": s["evidence_query_altered_rate"]}
    return rows
