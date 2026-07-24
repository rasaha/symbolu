"""Decomposition validation / audit (Phases 9,16). Given a corpus example and a method's produced
claims, aligns them to gold and assigns each gold claim a ClaimIntegrity DISPOSITION by composing the
per-dimension checkers. This is what lets ANY method (baseline or the component) be audited for the
specific drift it introduced - and what the component uses for self-check. Deterministic.
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import (metrics, negation, modality, uncertainty, qualifiers, scope, numerics, attribution)
from .taxonomy import Disposition


import re
_DANGLING = re.compile(r"^\s*(it|they|this|that|these|those|he|she)\b", re.I)


def _claim_disposition(gold_claim: Dict[str, Any], produced_text, risk_class: str) -> str:
    if produced_text is None:
        return Disposition.OMITTED_CLAIM.value
    gt = gold_claim["text"]
    # dangling pronoun subject: the claim cannot be evaluated / retrieves evidence for an ambiguous
    # entity -> reference error (only when gold has a concrete noun subject, i.e. it should have resolved)
    if _DANGLING.match(produced_text) and not _DANGLING.match(gt):
        return Disposition.REFERENCE_ERROR.value
    # order: meaning inversions first (most severe), then scope/attribution/numeric, then qualifier
    if not negation.preserved(gt, produced_text):
        return Disposition.NEGATION_ERROR.value
    if not uncertainty.preserved(gt, produced_text):
        return Disposition.NEGATION_ERROR.value    # incl. no-evidence -> false
    if modality.possibility_to_certainty(gt, produced_text) or not modality.preserved(gt, produced_text):
        return Disposition.SCOPE_ERROR.value
    if attribution.flattened_to_direct(gt, produced_text):
        return Disposition.ATTRIBUTION_ERROR.value
    num = numerics.check(gt, produced_text)
    if not num["preserved"]:
        return Disposition.NUMERIC_ERROR.value
    sc = scope.preserved(gold_claim, produced_text)
    if not sc["all_ok"]:
        return Disposition.SCOPE_ERROR.value
    if qualifiers.material_loss(gt, produced_text, risk_class):
        return Disposition.QUALIFIER_LOSS.value
    return Disposition.VALID.value


def audit(example: Dict[str, Any], produced: List[str]) -> Dict[str, Any]:
    pairs, omitted, invented = metrics._align(example["gold_claims"], produced)
    risk = example.get("risk_class", "low")
    per_claim = []
    for g, p in pairs:
        disp = _claim_disposition(g, p, risk)
        per_claim.append({"gold": g["text"], "produced": p, "disposition": disp,
                          "fragile_dimension": g["fragile_dimension"],
                          "downstream_consequence": g["downstream_consequence"]})
    if invented > 0:
        per_claim.append({"gold": None, "produced": "(extra)", "disposition":
                          Disposition.INVENTED_CLAIM.value, "fragile_dimension": "",
                          "downstream_consequence": "unsafe_allow"})
    drift = [c for c in per_claim if c["disposition"] not in
             (Disposition.VALID.value, Disposition.VALID_WITH_ALTERNATIVES.value)]
    return {
        "example_id": example["example_id"],
        "example_disposition": (Disposition.VALID.value if not drift
                                else drift[0]["disposition"]),
        "per_claim": per_claim,
        "n_drift_claims": len(drift),
        "invented": invented,
        "omitted": omitted,
    }
