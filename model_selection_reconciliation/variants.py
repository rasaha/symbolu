"""Model-selection policy variants A / B / C (reconciliation workstream).

Isolated, NON-DESTRUCTIVE: this module imports the frozen baseline
(`model_selection_experiment.policy`, `.simulator`) READ-ONLY and adds two constrained
variants alongside it. It modifies no baseline code.

  Policy A  — existing soft weighted-utility baseline (delegates to policy.route verbatim).
  Policy B  — hard quality floor Q̂ >= Q_min, then MINIMUM expected cost among sufficient.
  Policy C  — hard quality floor Q̂ >= Q_min, then LEXICOGRAPHIC: cost ↑, latency ↑,
              quality-margin (Q̂ − Q_min) ↓, model-id ↑.

The floor is applied to the PREDICTED quality Q̂ (`fuse_quality`'s `predicted_quality`) —
the only quality signal the policy sees at selection time. True quality is ground truth
and is used ONLY by the evaluator, never by the policy. No quality estimator is invented;
`fuse_quality` is the existing one. Registry has no `reliability` field, so Policy C's
tertiary key is the quality margin, not an invented reliability attribute.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from model_selection_experiment import policy as base

VARIANTS = ("A", "B", "C")


def _q_min_for(task: Dict[str, Any], q_min: Optional[float]) -> float:
    """Global override if provided, else the task-native acceptable_quality_threshold."""
    return q_min if q_min is not None else float(task["acceptable_quality_threshold"])


def _eligible_with_quality(task, registry, enterprise_policy, telemetry, policy,
                           advisory_by_model) -> List[Dict[str, Any]]:
    """Replicate the baseline's Stage 2-4 (eligibility + fuse_quality) using the SAME
    baseline functions, returning per-eligible-model {model, predicted_quality, est_cost,
    est_latency_ms}. This does not re-implement any logic; it calls base.* directly."""
    cs = base.resolve_constraints(task, enterprise_policy)
    models = registry["models"]
    out = []
    for mid, model in models.items():
        ok, _reason, _c, _p = base.hard_filter(model, task, cs)
        if not ok:
            continue
        adv = advisory_by_model.get(mid) if advisory_by_model else None
        if adv is not None:
            base._validate_advisory(adv, policy)
        fq = base.fuse_quality(model, task, telemetry, policy, adv)
        out.append({"model": mid,
                    "predicted_quality": fq["predicted_quality"],
                    "evidence": fq["evidence"],
                    "est_cost": round(base.estimate_cost(model, task), 6),
                    "est_latency_ms": round(base.estimate_latency_ms(model, task), 1)})
    return out


def _blank_record(task, registry, policy, regime, variant, q_min) -> Dict[str, Any]:
    return {"arm": f"variant_{variant}", "policy_variant": variant,
            "q_min_applied": q_min, "task_id": task["task_id"], "task_class": task["task_class"],
            "regime": regime, "policy_version": policy["version"],
            "registry_version": registry["version"], "eligible": [], "eliminated_by_quality": [],
            "scored": [], "fallback_chain": [], "selected": None, "abstained": False,
            "abstain_reason": None, "preflight_cost": 0.0, "preflight_latency_ms": 0.0}


def route_A(task, registry, enterprise_policy, telemetry, policy, regime,
            advisory_by_model=None, q_min=None) -> Dict[str, Any]:
    """Policy A: the existing baseline, unchanged. Delegates to policy.route verbatim.
    q_min is accepted for signature symmetry but IGNORED (A does not enforce a floor)."""
    rec = base.route(task, registry, enterprise_policy, telemetry, policy, regime, advisory_by_model)
    rec["policy_variant"] = "A"
    rec["q_min_applied"] = None      # A never enforces a quality floor (documented, tested)
    return rec


def _route_constrained(task, registry, enterprise_policy, telemetry, policy, regime,
                       advisory_by_model, q_min, lexicographic: bool) -> Dict[str, Any]:
    variant = "C" if lexicographic else "B"
    qmin = _q_min_for(task, q_min)
    rec = _blank_record(task, registry, policy, regime, variant, qmin)
    cand = _eligible_with_quality(task, registry, enterprise_policy, telemetry, policy,
                                  advisory_by_model)
    rec["eligible"] = [c["model"] for c in cand]
    # hard quality floor on PREDICTED quality
    sufficient = [c for c in cand if c["predicted_quality"] >= qmin]
    rec["eliminated_by_quality"] = [{"model": c["model"], "predicted_quality": c["predicted_quality"],
                                     "q_min": qmin} for c in cand if c["predicted_quality"] < qmin]
    if not sufficient:
        # existing contract behavior: abstain (fail-fast). Escalation is not a distinct
        # supported path in the baseline; abstain is the contract's terminal.
        rec["abstained"] = True
        rec["abstain_reason"] = ("no eligible model meets quality floor "
                                 f"Q_hat >= {qmin}" if cand else
                                 "no eligible model (empty hard-eligible set)")
        return rec
    if lexicographic:
        sufficient.sort(key=lambda c: (c["est_cost"], c["est_latency_ms"],
                                       -(c["predicted_quality"] - qmin), c["model"]))
    else:
        # minimum expected cost; deterministic tie-break by (latency, id) to stay reproducible
        sufficient.sort(key=lambda c: (c["est_cost"], c["est_latency_ms"], c["model"]))
    rec["scored"] = sufficient
    rec["selected"] = sufficient[0]["model"]
    rec["fallback_chain"] = [c["model"] for c in sufficient[1:]]
    return rec


def route_B(task, registry, enterprise_policy, telemetry, policy, regime,
            advisory_by_model=None, q_min=None) -> Dict[str, Any]:
    """Policy B: hard quality floor + minimum expected cost among sufficient."""
    return _route_constrained(task, registry, enterprise_policy, telemetry, policy, regime,
                              advisory_by_model, q_min, lexicographic=False)


def route_C(task, registry, enterprise_policy, telemetry, policy, regime,
            advisory_by_model=None, q_min=None) -> Dict[str, Any]:
    """Policy C: hard quality floor + lexicographic (cost, latency, quality-margin, id)."""
    return _route_constrained(task, registry, enterprise_policy, telemetry, policy, regime,
                              advisory_by_model, q_min, lexicographic=True)


_DISPATCH = {"A": route_A, "B": route_B, "C": route_C}


def route_variant(variant: str, task, registry, enterprise_policy, telemetry, policy, regime,
                  advisory_by_model=None, q_min=None) -> Dict[str, Any]:
    """Explicit configuration entry point to select a policy variant."""
    if variant not in _DISPATCH:
        raise ValueError(f"unknown policy variant {variant!r}; expected one of {VARIANTS}")
    return _DISPATCH[variant](task, registry, enterprise_policy, telemetry, policy, regime,
                              advisory_by_model, q_min)
