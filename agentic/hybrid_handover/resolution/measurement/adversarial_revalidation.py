#!/usr/bin/env python3
"""
Re-run every adversarial resolver through the REPAIRED metrics and confirm no
trivial strategy receives a misleadingly high capability score.

A capability metric is "gamed" if a cheat reaches >= 0.90 on it. The abstention
DECISION metrics are handled separately: an always-abstain resolver may have high
recall but must have low precision AND zero coverage (that is the point).
"""

from __future__ import annotations

from agentic.hybrid_handover.evaluation.corpus import all_cases

from ..audit.adversarial import ADVERSARIAL, ADVERSARIAL_ORDER
from .abstention import abstention_metrics
from .stage_metrics import discovery_classification, governance_modeG, packet_modeP

CAPABILITY_METRICS = [
    "discovery_recall", "discovery_precision", "classification_accuracy",
    "governance_accuracy_modeG", "packet_realization_accuracy_modeP",
]


def revalidate():
    cases = all_cases()
    rows = {}
    for name in ADVERSARIAL_ORDER:
        r = ADVERSARIAL[name]()
        m = {}
        m.update(discovery_classification(r, cases))
        m.update({k: v for k, v in governance_modeG(r, cases).items() if not k.startswith("_")})
        m.update({k: v for k, v in packet_modeP(r, cases).items() if not k.startswith("_")})
        ab = abstention_metrics(r, cases)
        m.update({k: v for k, v in ab.items() if not k.startswith("_")})
        rows[name] = m

    # gaming check on capability metrics
    gamed = {}
    for metric in CAPABILITY_METRICS:
        for name in ADVERSARIAL_ORDER:
            v = rows[name].get(metric)
            if v is not None and v >= 0.90:
                gamed.setdefault(metric, []).append(name)
    # always-abstain must be poor overall despite high recall
    aa = rows["always_abstain"]
    always_abstain_ok = (aa.get("answer_coverage") == 0.0) and (aa.get("selective_accuracy") == 0.0) \
        and (aa.get("abstention_precision") or 0) < 0.5
    return {"per_resolver": rows, "gamed_capability_metrics": gamed,
            "always_abstain_scores_poorly": always_abstain_ok}
