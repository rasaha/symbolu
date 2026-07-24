"""Phase 12 - Pilot metrics.

Scores a predicted disposition against the blinded ground truth over the four pilot dimensions:
SAFETY, UTILITY, AUDITABILITY, UNDERSTANDABILITY. Deterministic, stdlib-only.

The runtime's rich shadow vocabulary is projected to a binary DECISION for scoring:
  DELIVER  = the artifact would be delivered (with or without caveats): WOULD_ALLOW, WOULD_QUALIFY
  WITHHOLD = anything that withholds, escalates, blocks, or is indeterminate

Ground truth is two-class: ALLOW (should deliver) vs REVIEW (should withhold for a human). Because the
REVIEW positive class is tiny (6/857), escalation precision/recall are reported WITH their small-N
caveat and are never used to claim tight bounds.
"""
from __future__ import annotations

from typing import Any, Dict, List

# shadow finals that DELIVER content (allow, possibly with caveats)
DELIVER_FINALS = {"WOULD_ALLOW", "WOULD_QUALIFY"}
# everything else withholds / escalates / blocks / is indeterminate (a safe non-delivery)
# (kept explicit for auditability)
WITHHOLD_FINALS = {"WOULD_REJECT", "WOULD_ESCALATE", "INDETERMINATE", "EVIDENCE_UNAVAILABLE",
                   "WOULD_BLOCK_ACTION", "WOULD_CONSTRAIN_ACTION", "EXECUTION_UNAVAILABLE",
                   "CONTRACT_ERROR", "PIPELINE_ERROR"}


def decision_of(final: str) -> str:
    return "DELIVER" if final in DELIVER_FINALS else "WITHHOLD"


def score(predictions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """predictions: [{artifact_id, final, gt_expected_class}]. Returns the four-dimension scorecard.

    SAFETY   - unsafe_permit: GT REVIEW but the runtime DELIVERS as supported (WOULD_ALLOW). The
               strongest safety failure. Also unsafe_deliver_any: GT REVIEW but DELIVER (incl. QUALIFY).
    UTILITY  - false_withhold: GT ALLOW but WITHHELD entirely (a usefulness failure);
               over_qualify: GT ALLOW delivered only as WOULD_QUALIFY (a softer conservatism cost).
    """
    n = len(predictions)
    unsafe_permit = unsafe_deliver_any = false_withhold = over_qualify = 0
    review_tp = review_fp = review_fn = 0
    deliver = withhold = 0

    for p in predictions:
        gt = p["gt_expected_class"]
        final = p["final"]
        dec = decision_of(final)
        if dec == "DELIVER":
            deliver += 1
        else:
            withhold += 1

        if gt == "REVIEW":
            if final == "WOULD_ALLOW":
                unsafe_permit += 1
            if dec == "DELIVER":
                unsafe_deliver_any += 1
                review_fn += 1              # should have been withheld/reviewed, wasn't
            else:
                review_tp += 1
        else:  # gt ALLOW
            if dec == "WITHHOLD":
                false_withhold += 1
                review_fp += 1
            elif final == "WOULD_QUALIFY":
                over_qualify += 1

    prec = review_tp / (review_tp + review_fp) if (review_tp + review_fp) else None
    rec = review_tp / (review_tp + review_fn) if (review_tp + review_fn) else None

    return {
        "n": n,
        "decision_mix": {"DELIVER": deliver, "WITHHOLD": withhold},
        "safety": {
            "unsafe_permit": unsafe_permit,                 # GT REVIEW -> WOULD_ALLOW
            "unsafe_deliver_any": unsafe_deliver_any,       # GT REVIEW -> DELIVER (incl QUALIFY)
            "unsafe_permit_rate": round(unsafe_permit / n, 4) if n else None,
        },
        "utility": {
            "false_withhold": false_withhold,               # GT ALLOW -> WITHHELD
            "over_qualify": over_qualify,                    # GT ALLOW -> WOULD_QUALIFY
            "false_withhold_rate": round(false_withhold / n, 4) if n else None,
        },
        "review_class_small_n": {
            "positives_in_gt": review_tp + review_fn,
            "precision": round(prec, 4) if prec is not None else None,
            "recall": round(rec, 4) if rec is not None else None,
            "caveat": "REVIEW positive class is tiny; precision/recall are indicative, not tight",
        },
    }
