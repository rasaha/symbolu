"""Join predictions + observations at analysis time and compute Phase-9 shadow endpoints.

Prediction and observation are read from separate append-only logs and joined by
(request_id, model_id). Critical (compliance) false-eligibility is reported separately.
"""
from __future__ import annotations

from typing import Dict, List

from execution_gate_shadow.outcomes import (CRITICAL_OUTCOMES, EXECUTABLE_OUTCOMES, ObservedOutcome)

_SELECTABLE = {"ELIGIBLE", "CONDITIONALLY_ELIGIBLE"}


def compute(predictions: List[dict], observations: List[dict]) -> Dict:
    obs = {(o["request_id"], o["model_id"]): o for o in observations}
    tp = fp = fn = tn = 0
    fe_critical = fe_operational = fi = 0
    indeterminate = 0
    attempted = 0
    joined = 0
    for p in predictions:
        state = p["predicted_state"]
        if state == "INDETERMINATE":
            indeterminate += 1
        o = obs.get((p["request_id"], p["model_id"]))
        if o is None:
            continue
        joined += 1
        outcome = ObservedOutcome(o["outcome"])
        if outcome == ObservedOutcome.NOT_ATTEMPTED:
            # unverified: excluded from confusion (never presumed)
            continue
        attempted += 1
        truly_ok = outcome in EXECUTABLE_OUTCOMES
        selectable = state in _SELECTABLE
        if selectable and truly_ok:
            tp += 1
        elif selectable and not truly_ok:
            fp += 1
            if outcome in CRITICAL_OUTCOMES:
                fe_critical += 1
            else:
                fe_operational += 1
        elif (not selectable) and truly_ok:
            fn += 1; fi += 1
        else:
            tn += 1
    denom = tp + fp + fn + tn
    prec = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    return {
        "predictions": len(predictions), "observations": len(observations),
        "joined": joined, "attempted": attempted, "indeterminate": indeterminate,
        "indeterminate_rate": round(indeterminate / len(predictions), 4) if predictions else None,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "false_eligible_rate": round(fp / attempted, 4) if attempted else None,
        "false_eligible_critical": fe_critical,
        "false_eligible_operational": fe_operational,
        "false_ineligible": fi,
        "false_ineligible_rate": round(fi / attempted, 4) if attempted else None,
        "eligibility_precision": round(prec, 4) if prec is not None else None,
        "eligibility_recall": round(rec, 4) if rec is not None else None,
    }
