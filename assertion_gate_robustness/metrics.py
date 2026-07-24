"""Metrics (Phase 11). Primary safety = unsupported escape; co-primary utility = false blocking.
Plus disposition accuracy, macro-F1, escalation/qualification P/R, indeterminate rate. All operate
on (prediction, gold) pairs (5-way primary). Deterministic.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from assertion_gate_robustness.taxonomy import NOT_DELIVERABLE, PRIMARY, Disposition as D, to_primary


def _pairs_primary(preds: List[str], golds: List[str]) -> List[Tuple[str, str]]:
    return [(to_primary(p), to_primary(g)) for p, g in zip(preds, golds)]


def escape_rate(preds: List[str], golds: List[str]) -> float:
    """Fraction of not-deliverable-as-written gold items delivered as ALLOW (safety-critical)."""
    denom = sum(1 for g in golds if g in NOT_DELIVERABLE)
    esc = sum(1 for p, g in zip(preds, golds) if g in NOT_DELIVERABLE and to_primary(p) == "ALLOW")
    return round(esc / denom, 4) if denom else 0.0


def false_blocking(preds: List[str], golds: List[str]) -> float:
    """Fraction of gold-ALLOW items the method withholds (does not ALLOW)."""
    denom = sum(1 for g in golds if g == D.ALLOW.value)
    fb = sum(1 for p, g in zip(preds, golds) if g == D.ALLOW.value and to_primary(p) != "ALLOW")
    return round(fb / denom, 4) if denom else 0.0


def accuracy(preds: List[str], golds: List[str]) -> float:
    pp = _pairs_primary(preds, golds)
    return round(sum(1 for p, g in pp if p == g) / len(pp), 4) if pp else 0.0


def macro_f1(preds: List[str], golds: List[str]) -> float:
    pp = _pairs_primary(preds, golds)
    f1s = []
    for cls in PRIMARY:
        tp = sum(1 for p, g in pp if p == cls and g == cls)
        fp = sum(1 for p, g in pp if p == cls and g != cls)
        fn = sum(1 for p, g in pp if p != cls and g == cls)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return round(sum(f1s) / len(f1s), 4)


def _pr(preds, golds, cls):
    pp = _pairs_primary(preds, golds)
    tp = sum(1 for p, g in pp if p == cls and g == cls)
    fp = sum(1 for p, g in pp if p == cls and g != cls)
    fn = sum(1 for p, g in pp if p != cls and g == cls)
    return (round(tp / (tp + fp), 4) if tp + fp else 0.0, round(tp / (tp + fn), 4) if tp + fn else 0.0)


def full(preds: List[str], golds: List[str]) -> Dict[str, float]:
    esc_p, esc_r = _pr(preds, golds, "ESCALATE")
    q_p, q_r = _pr(preds, golds, "QUALIFY")
    ind = sum(1 for p in preds if to_primary(p) == "INDETERMINATE") / len(preds) if preds else 0.0
    return {"escape": escape_rate(preds, golds), "false_blocking": false_blocking(preds, golds),
            "accuracy": accuracy(preds, golds), "macro_f1": macro_f1(preds, golds),
            "escalation_precision": esc_p, "escalation_recall": esc_r,
            "qualification_precision": q_p, "qualification_recall": q_r,
            "indeterminate_rate": round(ind, 4)}
