"""Routing arms A-G. A-E are simpler baselines; F/G call the policy interpreter.

Every arm returns a decision record with at least: arm, task_id, selected,
abstained. Arms that filter also populate 'eliminated'. This lets the metrics
layer treat all arms uniformly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import policy as pol

FIXED_DEFAULT_MODEL = "m_medium_general"

STATIC_RULES = {
    "extraction": "m_medium_general",
    "classification": "m_small_local",
    "summarization": "m_medium_general",
    "coding": "m_coding_spec",
    "structured_output_generation": "m_coding_spec",
    "long_context_analysis": "m_long_multi",
    "reasoning": "m_strong_reason",
    "multilingual": "m_long_multi",
    "privacy_sensitive": "m_small_local",
    "tool_requiring": "m_medium_general",
    "latency_sensitive": "m_small_local",
    "cost_sensitive": "m_small_local",
}


def _base_record(arm: str, task: Dict[str, Any], regime: str) -> Dict[str, Any]:
    return {"arm": arm, "task_id": task["task_id"], "task_class": task["task_class"],
            "regime": regime, "selected": None, "abstained": False, "abstain_reason": None,
            "eligible": [], "eliminated": [], "scored": [], "fallback_chain": [],
            "preflight_cost": 0.0, "preflight_latency_ms": 0.0}


def _eligible(models: Dict[str, Any], task: Dict[str, Any], cs: Dict[str, Any]):
    elig, elim = [], []
    for mid, model in models.items():
        ok, reason, constraint, prov = pol.hard_filter(model, task, cs)
        if ok:
            elig.append(mid)
        else:
            elim.append({"model": mid, "reason": reason, "constraint": constraint, "provenance": prov})
    return elig, elim


def arm_A_fixed(task, registry, ent_policy, telemetry, policy, regime, advisory=None):
    """A. Always the fixed default model. No constraint filtering (naive)."""
    r = _base_record("A", task, regime)
    r["selected"] = FIXED_DEFAULT_MODEL
    return r


def arm_B_strongest(task, registry, ent_policy, telemetry, policy, regime, advisory=None):
    """B. Always the globally strongest candidate, ignoring cost/latency AND constraints."""
    r = _base_record("B", task, regime)
    models = registry["models"]
    strongest = max(models, key=lambda m: models[m]["declared"]["declared_overall"]["value"])
    r["selected"] = strongest
    return r


def arm_C_cheapest_eligible(task, registry, ent_policy, telemetry, policy, regime, advisory=None):
    """C. Hard constraints, then lowest-cost eligible."""
    r = _base_record("C", task, regime)
    cs = pol.resolve_constraints(task, ent_policy)
    elig, elim = _eligible(registry["models"], task, cs)
    r["eligible"], r["eliminated"] = elig, elim
    if not elig:
        r["abstained"] = True
        r["abstain_reason"] = "empty eligible set"
        return r
    ranked = sorted(elig, key=lambda m: (pol.estimate_cost(registry["models"][m], task), m))
    r["selected"] = ranked[0]
    r["fallback_chain"] = ranked[1:]
    return r


def arm_D_static_rules(task, registry, ent_policy, telemetry, policy, regime, advisory=None):
    """D. Deterministic task-class -> model rules, constraint-aware."""
    r = _base_record("D", task, regime)
    cs = pol.resolve_constraints(task, ent_policy)
    elig, elim = _eligible(registry["models"], task, cs)
    r["eligible"], r["eliminated"] = elig, elim
    if not elig:
        r["abstained"] = True
        r["abstain_reason"] = "empty eligible set"
        return r
    preferred = STATIC_RULES.get(task["task_class"], FIXED_DEFAULT_MODEL)
    if preferred in elig:
        r["selected"] = preferred
    elif FIXED_DEFAULT_MODEL in elig:
        r["selected"] = FIXED_DEFAULT_MODEL
    else:
        r["selected"] = sorted(elig)[0]
    r["fallback_chain"] = [m for m in elig if m != r["selected"]]
    return r


def arm_E_benchmark_only(task, registry, ent_policy, telemetry, policy, regime, advisory=None):
    """E. Hard constraints, then highest benchmark-measured quality (ignore cost/latency/telemetry)."""
    r = _base_record("E", task, regime)
    cs = pol.resolve_constraints(task, ent_policy)
    models = registry["models"]
    elig, elim = _eligible(models, task, cs)
    r["eligible"], r["eliminated"] = elig, elim
    if not elig:
        r["abstained"] = True
        r["abstain_reason"] = "empty eligible set"
        return r

    def bench_q(mid):
        measured = models[mid]["measured"]["capability_scores"]
        req = task["required_caps"]
        covered = {c: measured[c]["value"] for c in req if c in measured}
        if not covered:
            # no benchmark coverage -> fall back to declared overall (optimistic)
            return models[mid]["declared"]["declared_overall"]["value"] - 0.001
        from common import weighted_caps
        return weighted_caps(covered, {c: req[c] for c in covered})

    ranked = sorted(elig, key=lambda m: (-bench_q(m), m))
    r["selected"] = ranked[0]
    r["fallback_chain"] = ranked[1:]
    return r


def arm_F_policy(task, registry, ent_policy, telemetry, policy, regime, advisory=None):
    """F. Policy engine WITHOUT self-assessment."""
    return pol.route(task, registry, ent_policy, telemetry, policy, regime, advisory_by_model=None)


def arm_G_policy_selfassess(task, registry, ent_policy, telemetry, policy, regime, advisory=None):
    """G. Policy engine WITH bounded self-assessment (advisory supplied by harness)."""
    rec = pol.route(task, registry, ent_policy, telemetry, policy, regime, advisory_by_model=advisory)
    return rec


ARMS = {
    "A": arm_A_fixed,
    "B": arm_B_strongest,
    "C": arm_C_cheapest_eligible,
    "D": arm_D_static_rules,
    "E": arm_E_benchmark_only,
    "F": arm_F_policy,
    "G": arm_G_policy_selfassess,
}

ARM_LABELS = {
    "A": "Fixed default", "B": "Strongest (unconstrained)", "C": "Cheapest-eligible",
    "D": "Static rules", "E": "Benchmark-only", "F": "Policy (no self-assessment)",
    "G": "Policy + bounded self-assessment",
}
