"""Phase 20 - Human-review study (deterministic dual-rubric SIMULATION).

No real reviewers are available, so this is a DETERMINISTIC dual-rubric simulation, labelled honestly as
such. Two simulated reviewers (the independent ground-truth annotators A and B) assess each item's
obligation, source authority, external-evidence need, and allow-safety; agreement and override metrics
are reported. This is a proxy for a real review study, NOT a substitute for one.

Deterministic, read-only. Writes eval_results/review_study.json.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from evidence_obligation import ground_truth as gt, classifier, dataset, schema as s

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")

SIMULATED = True   # honest flag: these are simulated reviewers, not humans
_LOW_BURDEN = {s.NO_FACTUAL_EVIDENCE_GATE, s.CONTEXTUAL_SUPPORT_SUFFICIENT,
               s.IMPLEMENTATION_EVIDENCE_SUFFICIENT, s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT}


def _reviewers(item) -> Dict[str, str]:
    fam, obl_a = gt.annotator_A(item["text"], item.get("source_role_hint", "unknown_source"))
    _, obl_b = gt.annotator_B(item["text"])
    return {"reviewer_1": obl_a, "reviewer_2": obl_b}


def compute() -> Dict[str, Any]:
    items = dataset.load_partition("HELD_OUT_NATURAL")
    n = len(items)
    r_agree = obl_vs_component = comp_allow_safe_agree = high_risk_agree = 0
    overrides = 0
    override_stricter = override_looser = 0
    high_risk_n = 0

    from evidence_obligation import ground_truth as _gt  # burden ranking

    for it in items:
        rv = _reviewers(it)
        comp = classifier.classify(it).evidence_obligation_type
        gold = it["gold_obligation"]

        if rv["reviewer_1"] == rv["reviewer_2"]:
            r_agree += 1
        # component matches at least one reviewer
        if comp in (rv["reviewer_1"], rv["reviewer_2"], gold):
            obl_vs_component += 1
        # allow-safety agreement: reviewers (via gold) and component agree on whether a clean allow is safe
        comp_low = comp in _LOW_BURDEN
        gold_low = gold in _LOW_BURDEN
        if comp_low == gold_low:
            comp_allow_safe_agree += 1
        # high-risk agreement
        if it.get("risk_tier") in ("high", "critical"):
            high_risk_n += 1
            if not comp_low and not gold_low:
                high_risk_agree += 1
        # override: a reviewer would change the component's decision toward a different burden
        if comp != gold:
            overrides += 1
            if _gt._RANK.get(gold, 0) > _gt._RANK.get(comp, 0):
                override_stricter += 1
            else:
                override_looser += 1

    return {
        "simulated": SIMULATED,
        "method": "deterministic dual-rubric simulation (annotators A and B as two reviewers)",
        "n": n,
        "reviewer_agreement": round(r_agree / n, 4),
        "component_matches_a_reviewer_or_gold": round(obl_vs_component / n, 4),
        "clean_allow_safety_agreement": round(comp_allow_safe_agree / n, 4),
        "high_risk_agreement": round(high_risk_agree / high_risk_n, 4) if high_risk_n else None,
        "override_rate": round(overrides / n, 4),
        "override_direction": {"toward_stricter": override_stricter, "toward_looser": override_looser},
        "simulated_review_time_units_per_item": 5,   # fixed symbolic units (not wall-clock)
        "caveat": "SIMULATED reviewers. Low reviewer agreement (H0-14 risk) reflects the two rubrics' "
                  "different axes; a real review study is required before external-pilot readiness.",
    }


def freeze() -> Dict[str, Any]:
    import hashlib
    m = compute()
    m["review_sha256"] = hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "review_study.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"SIMULATED review study (n={m['n']})")
    print(f"  reviewer agreement:            {m['reviewer_agreement']}")
    print(f"  component matches reviewer/gold:{m['component_matches_a_reviewer_or_gold']}")
    print(f"  clean-allow safety agreement:  {m['clean_allow_safety_agreement']}")
    print(f"  high-risk agreement:           {m['high_risk_agreement']}")
    print(f"  override rate:                 {m['override_rate']} {m['override_direction']}")
