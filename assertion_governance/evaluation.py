"""Metrics (Phase 7) + evaluation (Phase 9). Computes disposition agreement, the safety-critical
unsupported-assertion escape rate, qualification precision/recall, false-qualification, false-
rejection, escalation precision/recall, evidence preservation, and high/low-risk splits for every
method. Includes a deterministic paired (McNemar-style) comparison of AGE vs the strongest
baselines. No generic accuracy optimization. Deterministic; no live calls.
"""
from __future__ import annotations

import json
from typing import Callable, Dict, List

from assertion_governance.baselines import tune
from assertion_governance.dataset import Item, split
from assertion_governance.engine import govern_item
from assertion_governance.taxonomy import Disposition as Dsp, to_primary

D = Dsp
# "should NOT be delivered as written" gold set (delivering as ALLOW is an escape)
_NOT_DELIVERABLE = {D.REJECT.value, D.QUALIFY.value, D.NOT_SUPPORTED.value,
                    D.ESCALATE.value, D.INDETERMINATE.value}


def _prim(x: str) -> str:
    return to_primary(D(x)).value


def metrics(pred: Callable[[Item], str], items: List[Item]) -> Dict[str, float]:
    n = len(items)
    agree = sum(1 for it in items if _prim(pred(it)) == _prim(it.gold_disposition))
    # unsupported escape: gold says not-deliverable-as-written but method says ALLOW
    esc_denom = sum(1 for it in items if it.gold_disposition in _NOT_DELIVERABLE)
    escape = sum(1 for it in items if it.gold_disposition in _NOT_DELIVERABLE and _prim(pred(it)) == "ALLOW")
    # qualification
    q_gold = [it for it in items if it.gold_disposition == D.QUALIFY.value]
    q_pred = [it for it in items if _prim(pred(it)) == "QUALIFY"]
    q_tp = sum(1 for it in q_gold if _prim(pred(it)) == "QUALIFY")
    # false qualification: gold ALLOW but predicted QUALIFY
    allow_gold = [it for it in items if it.gold_disposition == D.ALLOW.value]
    false_qual = sum(1 for it in allow_gold if _prim(pred(it)) == "QUALIFY")
    false_rej = sum(1 for it in allow_gold if _prim(pred(it)) == "REJECT")
    # escalation
    e_gold = [it for it in items if it.gold_disposition == D.ESCALATE.value]
    e_pred = [it for it in items if _prim(pred(it)) == "ESCALATE"]
    e_tp = sum(1 for it in e_gold if _prim(pred(it)) == "ESCALATE")
    hi = [it for it in items if it.risk_class in ("high", "critical")]
    lo = [it for it in items if it.risk_class not in ("high", "critical")]
    return {
        "agreement": round(agree / n, 4),
        "unsupported_escape_rate": round(escape / max(1, esc_denom), 4),
        "qualification_recall": round(q_tp / max(1, len(q_gold)), 4),
        "qualification_precision": round(q_tp / max(1, len(q_pred)), 4),
        "false_qualification_rate": round(false_qual / max(1, len(allow_gold)), 4),
        "false_rejection_rate": round(false_rej / max(1, len(allow_gold)), 4),
        "escalation_recall": round(e_tp / max(1, len(e_gold)), 4),
        "escalation_precision": round(e_tp / max(1, len(e_pred)), 4),
        "agreement_high_risk": round(sum(1 for it in hi if _prim(pred(it)) == _prim(it.gold_disposition)) / max(1, len(hi)), 4),
        "agreement_low_risk": round(sum(1 for it in lo if _prim(pred(it)) == _prim(it.gold_disposition)) / max(1, len(lo)), 4),
    }


def mcnemar(a: Callable, b: Callable, items: List[Item]) -> Dict[str, float]:
    """Paired discordance: items where a correct & b wrong (a_only) vs b correct & a wrong (b_only)."""
    a_only = b_only = 0
    for it in items:
        ac = _prim(a(it)) == _prim(it.gold_disposition)
        bc = _prim(b(it)) == _prim(it.gold_disposition)
        if ac and not bc:
            a_only += 1
        elif bc and not ac:
            b_only += 1
    disc = a_only + b_only
    # McNemar chi-square (no continuity corr for small n reported alongside counts)
    chi = ((abs(a_only - b_only)) ** 2) / disc if disc else 0.0
    return {"a_only": a_only, "b_only": b_only, "discordant": disc, "chi_square": round(chi, 3)}


def run(all_split: str = "eval") -> Dict:
    items = split(all_split)
    methods = dict(tune())
    methods["AGE"] = lambda it: govern_item(it).disposition
    per = {name: metrics(fn, items) for name, fn in methods.items()}
    # adversarial-to-AGE subset: does AGE over-escalate on well-supported high-risk claims?
    adv = [it for it in items if it.adversarial_to_age]
    adv_age_correct = sum(1 for it in adv if _prim(govern_item(it).disposition) == _prim(it.gold_disposition))
    comparisons = {
        "AGE_vs_G": mcnemar(methods["AGE"], methods["G_ground_entail"], items),
        "AGE_vs_G_risk": mcnemar(methods["AGE"], methods["G_risk"], items),
        "AGE_vs_D": mcnemar(methods["AGE"], methods["D_entailment"], items),
    }
    return {"split": all_split, "n": len(items), "metrics": per, "comparisons": comparisons,
            "adversarial_to_age": {"n": len(adv), "age_correct": adv_age_correct,
                                   "age_error_rate": round(1 - adv_age_correct / max(1, len(adv)), 4)}}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
