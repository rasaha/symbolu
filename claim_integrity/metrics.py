"""Drift + preservation metrics (Phase 11). Aligns a method's produced claims to gold claims and
computes per-dimension preservation, material semantic-drift rate, atomicity error, invented/omitted
claim rates - each reported separately (never one collapsed score). Deterministic.
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import equivalence


def _align(gold_claims: List[Dict[str, Any]], produced: List[str]) -> List[tuple]:
    """Greedy align each gold claim to its best-overlap produced claim (or None)."""
    used = set()
    pairs = []
    for g in gold_claims:
        best, best_score = None, 0.0
        gt = equivalence._content_tokens(g["text"])
        for i, p in enumerate(produced):
            if i in used:
                continue
            pt = equivalence._content_tokens(p)
            score = len(gt & pt) / len(gt) if gt else 0.0
            if score > best_score:
                best, best_score = i, score
        if best is not None and best_score >= 0.3:
            used.add(best)
            pairs.append((g, produced[best]))
        else:
            pairs.append((g, None))
    omitted = sum(1 for g, p in pairs if p is None)
    invented = len(produced) - len(used)
    return pairs, omitted, invented


def score_method(examples: List[Dict[str, Any]], method) -> Dict[str, Any]:
    dim_totals: Dict[str, int] = {}
    dim_ok: Dict[str, int] = {}
    n_claims = 0
    material_drift = 0
    omitted_total = invented_total = 0
    count_err = 0
    over_split = under_split = 0

    for e in examples:
        produced = method(e)
        pairs, omitted, invented = _align(e["gold_claims"], produced)
        omitted_total += omitted
        invented_total += invented
        diff = len(produced) - e["expected_claim_count"]
        count_err += abs(diff)
        if diff > 0:
            over_split += 1
        elif diff < 0:
            under_split += 1
        for g, p in pairs:
            n_claims += 1
            if p is None:
                material_drift += 1     # omitted claim = maximal drift
                continue
            pres = equivalence.preservation(g, p)
            if not pres["material_preserved"]:
                material_drift += 1
            for d, ok in pres["per_dimension"].items():
                dim_totals[d] = dim_totals.get(d, 0) + 1
                dim_ok[d] = dim_ok.get(d, 0) + int(ok)

    return {
        "n_gold_claims": n_claims,
        "material_drift_rate": round(material_drift / n_claims, 4),
        "omitted_claim_rate": round(omitted_total / n_claims, 4),
        "invented_claim_rate": round(invented_total / max(1, n_claims), 4),
        "mean_count_error": round(count_err / len(examples), 4),
        "over_split_examples": over_split,
        "under_split_examples": under_split,
        "per_dimension_preservation": {
            d: round(dim_ok[d] / dim_totals[d], 4) for d in sorted(dim_totals)},
    }
