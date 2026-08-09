"""Structure-blind baselines + length-shortcut control. Torch-free.

Implements the preregistered structure-blind controls and the Amendment-002 audit watch item: a pure
input-length shortcut must not silently count as reasoning success. This module adds NO new scientific
gate (unauthorized); it instruments and exposes statistics for the frozen shortcut machinery
(structure_blind_margin = 0.10).
"""
from __future__ import annotations

from .config import NUMERIC_GATES
from .schema_ext import ReasoningContext
from .serializer import input_token_count


def length_shortcut_control(contexts: list[ReasoningContext]) -> dict:
    """Detect whether input token length separates answerable from abstain episodes.

    Returns length ranges per class and a `length_preserving` flag (True iff the two length ranges
    overlap, so a length-only classifier cannot cleanly separate them). A length shortcut is possible iff
    length_preserving is False.
    """
    ans = [input_token_count(c) for c in contexts
           if c.authoritative_output.status != "INSUFFICIENT_EVIDENCE"]
    absent = [input_token_count(c) for c in contexts
              if c.authoritative_output.status == "INSUFFICIENT_EVIDENCE"]
    if not ans or not absent:
        return {"applicable": False, "length_preserving": True}
    overlap = max(min(ans), min(absent)) <= min(max(ans), max(absent))
    # accuracy of a length-only median-threshold classifier predicting abstain for short inputs
    thr = sorted([input_token_count(c) for c in contexts])[len(contexts) // 2]
    correct = 0
    for c in contexts:
        pred_abstain = input_token_count(c) < thr
        gold_abstain = c.authoritative_output.status == "INSUFFICIENT_EVIDENCE"
        correct += int(pred_abstain == gold_abstain)
    return {
        "applicable": True,
        "answerable_len_range": [min(ans), max(ans)],
        "absent_len_range": [min(absent), max(absent)],
        "length_preserving": bool(overlap),
        "length_only_status_accuracy": correct / len(contexts),
    }


def structure_blind_predictions(kind: str, contexts: list[ReasoningContext]) -> list[tuple]:
    """Produce (context, predicted_text) for a blind baseline that ignores relational structure.

    kind: 'majority_status' | 'query_only' | 'always_abstain'. These are degenerate predictors whose
    accuracy is the structure-blind floor the model must beat by >= structure_blind_margin.
    """
    out = []
    for c in contexts:
        if kind == "always_abstain":
            text = '{"answer":null,"reasoning_path":[],"evidence_ids":[],"status":"INSUFFICIENT_EVIDENCE"}'
        else:  # majority_status / query_only: emit a schema-valid but uninformed SUPPORTED guess
            text = '{"answer":"NO_ACTION","reasoning_path":[],"evidence_ids":[],"status":"SUPPORTED"}'
        out.append((c, text))
    return out


def blind_baseline_within_margin(model_metric: float, blind_metric: float,
                                 margin: float = NUMERIC_GATES["structure_blind_margin"]) -> bool:
    """True => SHORTCUT_OR_LEAKAGE risk: a blind baseline is within `margin` of the model."""
    return (model_metric - blind_metric) < margin
