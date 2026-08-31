"""Frozen numeric-gate evaluation (non-compensation). Torch-free. Thresholds come only from config."""
from __future__ import annotations

from .config import NUMERIC_GATES


# mapping: gate key -> (metric key, comparison) ; ">=" pass if metric>=threshold, "<=" pass if <=
_GATE_METRIC = {
    "structured_output_validity": ("structured_output_validity", ">="),
    "entity_selection": ("entity_selection", ">="),
    "relation_path_exact_ordered": ("relation_path_exact_ordered", ">="),
    "latest_event": ("latest_event", ">="),
    "policy_condition": ("policy_condition", ">="),
    "evidence_precision": ("evidence_precision", ">="),
    "evidence_recall": ("evidence_recall", ">="),
    "abstention_R10_R11": ("abstention_accuracy", ">="),
    "false_abstention_on_answerable_max": ("false_abstention_on_answerable", "<="),
    "hallucinated_entity_max": ("hallucinated_entity", "<="),
    "hallucinated_relation_max": ("hallucinated_relation", "<="),
    "hallucinated_evidence_max": ("hallucinated_evidence", "<="),
    "R9_full_chain_correct": ("r9_full_chain_correct", ">="),
}


def evaluate_gates(metrics: dict, per_split_answer_acc: dict | None = None,
                   latest_event_baseline: float | None = None) -> dict:
    """Return {'gates': {name: {pass,threshold,value}}, 'all_pass': bool}. Thresholds never mutated.

    `latest_event_baseline` (global-most-recent accuracy) enables the frozen effect gate
    latest_event - baseline >= latest_event_effect_over_global_most_recent (0.20).
    """
    results = {}
    for gate, (mkey, cmp) in _GATE_METRIC.items():
        thr = NUMERIC_GATES[gate]
        val = metrics.get(mkey)
        if val is None:
            results[gate] = {"pass": None, "threshold": thr, "value": None}
            continue
        ok = val >= thr if cmp == ">=" else val <= thr
        results[gate] = {"pass": bool(ok), "threshold": thr, "value": val}
    # per-split answer-accuracy gates (R1..R4, R7, R9 composite, R12 relative)
    psa = per_split_answer_acc or {}
    for gate, mkey in (("R1_direct_attribute", "R1"), ("R2_path_given_1hop", "R2"),
                       ("R3_path_given_multihop", "R3"), ("R4_path_discovery_multihop", "R4"),
                       ("R7_path_discovery_temporal", "R7"), ("R9_composite_final_answer", "R9")):
        thr = NUMERIC_GATES[gate]
        val = psa.get(mkey)
        results[gate] = ({"pass": bool(val >= thr), "threshold": thr, "value": val}
                         if val is not None else {"pass": None, "threshold": thr, "value": None})
    # R12 relative to R9
    if "R12" in psa and "R9" in psa:
        thr = NUMERIC_GATES["R12_confusable_min_relative_to_R9"]
        results["R12_confusable_relative"] = {"pass": bool(psa["R12"] - psa["R9"] >= thr),
                                              "threshold": thr, "value": psa["R12"] - psa["R9"]}
    # latest-event effect over the global-most-recent baseline (F3)
    le = metrics.get("latest_event")
    if latest_event_baseline is not None and le is not None:
        thr = NUMERIC_GATES["latest_event_effect_over_global_most_recent"]
        effect = le - latest_event_baseline
        results["latest_event_effect_over_global_most_recent"] = {
            "pass": bool(effect >= thr), "threshold": thr, "value": effect,
            "baseline": latest_event_baseline}
    decided = [v["pass"] for v in results.values() if v["pass"] is not None]
    return {"gates": results, "all_pass": bool(decided) and all(decided),
            "non_compensation": "every critical gate must pass; strong R1/R2 cannot offset any failure"}
