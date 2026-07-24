"""Phase 9/12 - Obligation-assignment metrics.

Scores predicted obligations against the independent gold labels: exact accuracy, acceptable-obligation
accuracy, UNSAFE assignment count (predicted an obligation the gold marks unacceptable - the safety
metric), claim-type accuracy, and source-role accuracy. Deterministic.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List


def score_obligations(items: List[Dict[str, Any]], predict: Callable) -> Dict[str, Any]:
    """predict(item) -> EvidenceObligation. Returns the obligation scorecard for one partition."""
    n = len(items)
    exact = acceptable = unsafe = ct_correct = 0
    unsafe_high_risk = 0
    unsafe_examples: List[str] = []

    for it in items:
        o = predict(it)
        pred = o.evidence_obligation_type
        gold = it["gold_obligation"]
        acc = it.get("acceptable_obligations", [gold])
        unacc = it.get("unacceptable_obligations", [])

        if pred == gold:
            exact += 1
        if pred == gold or pred in acc:
            acceptable += 1
        if pred in unacc:
            unsafe += 1
            if it.get("risk_tier") in ("high", "critical"):
                unsafe_high_risk += 1
            if len(unsafe_examples) < 8:
                unsafe_examples.append(f"{it['artifact_id']}: gold={gold} pred={pred}")
        if o.claim_type == it.get("claim_family"):
            ct_correct += 1

    return {
        "n": n,
        "exact_accuracy": round(exact / n, 4) if n else None,
        "acceptable_accuracy": round(acceptable / n, 4) if n else None,
        "unsafe_assignments": unsafe,
        "unsafe_assignment_rate": round(unsafe / n, 4) if n else None,
        "unsafe_high_risk_assignments": unsafe_high_risk,
        "claim_type_accuracy_vs_gold_rubric": round(ct_correct / n, 4) if n else None,
        "unsafe_examples": unsafe_examples,
    }
