"""Structure-blind baseline suite + global-most-recent + length-shortcut control. Torch-free.

Implements the preregistered structure-blind controls as deterministic predictors, the global-most-recent
temporal shortcut, the frozen margin rule (a blind baseline within `structure_blind_margin` of the model
=> SHORTCUT_OR_LEAKAGE_DETECTED), and a robust length-shortcut instrument. Adds NO new scientific gate
and never tunes on scientific results; fixtures only.
"""
from __future__ import annotations

from collections import Counter

from .config import NUMERIC_GATES
from .output import serialize_output
from .schema_ext import ReasoningContext, ReasoningOutput
from .serializer import input_token_count

MARGIN = NUMERIC_GATES["structure_blind_margin"]                       # 0.10
LATEST_EFFECT = NUMERIC_GATES["latest_event_effect_over_global_most_recent"]  # 0.20

SUITE = ("shuffled_context", "query_only", "majority_class", "most_recent_token",
         "global_most_recent", "policy_id_to_outcome")


def _out(answer, path=(), evids=(), status="SUPPORTED") -> str:
    return serialize_output(ReasoningOutput(answer, tuple(path), tuple(evids), status))


def _global_newest_event(ctx: ReasoningContext):
    if not ctx.events:
        return None
    return max(ctx.events, key=lambda e: (e.sequence, e.event_id))


def _most_recent_serialized_event(ctx: ReasoningContext):
    # "most recent token": the event that serializes last (sorted by opaque event_id) -- decorrelated
    if not ctx.events:
        return None
    return sorted(ctx.events, key=lambda e: e.event_id)[-1]


def predict(kind: str, contexts: list[ReasoningContext]) -> list[tuple[ReasoningContext, str]]:
    """Deterministic structure-blind prediction for each context (no reasoning over structure)."""
    # majority_class needs a cohort-level statistic
    maj_status = Counter(c.authoritative_output.status for c in contexts).most_common(1)[0][0] \
        if contexts else "SUPPORTED"
    out = []
    for c in contexts:
        if kind == "query_only":
            text = _out("NO_ACTION", status="SUPPORTED")                       # sees only the query
        elif kind == "shuffled_context":
            text = _out("NO_ACTION", status="SUPPORTED")                       # structure broken
        elif kind == "majority_class":
            text = _out(None if maj_status == "INSUFFICIENT_EVIDENCE" else "NO_ACTION", status=maj_status)
        elif kind == "most_recent_token":
            ev = _most_recent_serialized_event(c)
            text = _out(ev.value if ev else "NO_ACTION",
                        path=(f"Event:{ev.event_id}",) if ev else (), status="SUPPORTED")
        elif kind == "global_most_recent":
            ev = _global_newest_event(c)
            text = _out(ev.value if ev else "NO_ACTION",
                        path=(f"Event:{ev.event_id}",) if ev else (), status="SUPPORTED")
        elif kind == "policy_id_to_outcome":
            pol = sorted(c.policies, key=lambda p: p.policy_id)[0] if c.policies else None
            text = _out(pol.outcome if pol else "NO_ACTION",
                        path=(f"Policy:{pol.policy_id}",) if pol else (), status="SUPPORTED")
        else:
            raise ValueError(f"unknown baseline {kind}")
        out.append((c, text))
    return out


def baseline_accuracy(kind: str, contexts: list[ReasoningContext],
                      metric_key: str = "final_answer_accuracy") -> float:
    from .metrics import compute
    return compute(predict(kind, contexts)).get(metric_key) or 0.0


def run_suite(contexts: list[ReasoningContext], model_metric: float,
              metric_key: str = "final_answer_accuracy", margin: float = MARGIN) -> dict:
    """Compare the model's competence on `metric_key` against every structure-blind baseline.

    shortcut_detected iff any baseline lies within `margin` of the model (model - baseline < margin).
    """
    baselines = {k: baseline_accuracy(k, contexts, metric_key) for k in SUITE}
    within = {k: (model_metric - a) < margin for k, a in baselines.items()}
    return {"baselines": baselines, "within_margin": within,
            "shortcut_detected": any(within.values()), "margin": margin, "model": model_metric}


def latest_event_effect(contexts: list[ReasoningContext], model_latest_event_accuracy: float) -> dict:
    """Global-most-recent temporal baseline + the frozen effect gate.

    Requires model_latest_event >= 0.85 (absolute, checked in gates) AND
    model_latest_event - global_most_recent_baseline >= 0.20 (here).
    """
    temporal = [c for c in contexts if c.events and c.authoritative_output.reasoning_path
                and any(n.startswith("Event:") for n in c.authoritative_output.reasoning_path)]
    baseline = baseline_accuracy("global_most_recent", temporal, "latest_event") if temporal else 0.0
    effect = model_latest_event_accuracy - baseline
    return {"global_most_recent_baseline": baseline, "effect": effect,
            "required_effect": LATEST_EFFECT, "effect_pass": effect >= LATEST_EFFECT}


def length_shortcut_control(contexts: list[ReasoningContext]) -> dict:
    """Robust length-shortcut instrument (F6): lengths by status, a deterministic length-only predictor,
    its accuracy, and whether the two length distributions overlap. Exposed for the frozen shortcut
    machinery; introduces no new scientific gate."""
    ans = [input_token_count(c) for c in contexts
           if c.authoritative_output.status != "INSUFFICIENT_EVIDENCE"]
    absent = [input_token_count(c) for c in contexts
              if c.authoritative_output.status == "INSUFFICIENT_EVIDENCE"]
    if not ans or not absent:
        return {"applicable": False, "length_preserving": True}
    lengths = sorted(input_token_count(c) for c in contexts)
    thr = lengths[len(lengths) // 2]
    correct = sum(int((input_token_count(c) < thr) ==
                      (c.authoritative_output.status == "INSUFFICIENT_EVIDENCE")) for c in contexts)
    overlap = max(min(ans), min(absent)) <= min(max(ans), max(absent))
    acc = correct / len(contexts)
    # a pure length heuristic must not be a strong separator; report and flag near-perfect separation
    return {
        "applicable": True,
        "answerable_len_range": [min(ans), max(ans)],
        "absent_len_range": [min(absent), max(absent)],
        "length_preserving": bool(overlap),
        "length_only_status_accuracy": acc,
        "length_is_trivial_separator": acc >= 0.90 and not overlap,
    }
