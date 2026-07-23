"""Routing-time Model Selection Policy for the pilot.

Enforces the routing-time INFORMATION BOUNDARY: the policy operates on a
sanitized task view that excludes ground truth (`_oracle`) and any execution
output. It may use registry facts, a telemetry snapshot (prior dev outcomes),
task classification, input size, enterprise policy, and -- for arm G -- bounded
task-shape advisory.

Two policy modes (mandated ablation):
  F1: quality is a SOFT utility term (no gate)   -- the prior, weaker design.
  F2: minimum acceptable quality is an ELIGIBILITY GATE, per the corrected order:
      1 enterprise/governance hard constraints
      2 verified technical eligibility
      3 minimum-quality gate
      4 minimum-reliability gate (schema tasks)
      5 rank remaining by utility
      6 fallback order
G: F2 + bounded cold-start self-assessment folded into the quality estimate.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import advisory as adv
from common import POLICY_VERSION, clamp

ALLOWED_TASK_VIEW_FIELDS = {
    "task_id", "task_class", "input_tokens_k", "business_priority", "hard_constraints",
    "min_acceptable_quality", "required_schema", "label_set", "candidate_clause_ids", "question",
}

PRIORITY_WEIGHTS = {
    "quality_first": (1.0, 0.15, 0.10),
    "balanced": (1.0, 0.50, 0.40),
    "cost_first": (0.7, 1.00, 0.30),
    "latency_first": (0.8, 0.30, 1.00),
}

FUSION = {"observed_base": 1.4, "advisory_base": 0.6, "prior_base": 0.10,
          "telemetry_conf_k": 8, "advisory_conf": 0.40, "prior_value": 0.5,
          "gate_confidence_floor": 0.30, "min_reliability": 0.80}


class InformationBoundaryError(ValueError):
    pass


def routing_view(task: Dict[str, Any]) -> Dict[str, Any]:
    """Strip everything the policy is not allowed to see at routing time."""
    return {k: v for k, v in task.items() if k in ALLOWED_TASK_VIEW_FIELDS}


def _assert_boundary(view: Dict[str, Any]) -> None:
    if "_oracle" in view or "output" in view or "score" in view:
        raise InformationBoundaryError("routing view leaked post-execution / ground-truth data")


def estimate_cost(model: Dict[str, Any], view: Dict[str, Any]) -> float:
    pf = model["provider_facts"]
    price = pf["pricing_per_mtok"]["value"]
    ktok_in = view["input_tokens_k"]
    ktok_out = max(0.05, ktok_in * 0.15)  # assume modest output
    return (price["in"] * ktok_in + price["out"] * ktok_out) / 1000.0


def estimate_latency_ms(model: Dict[str, Any], view: Dict[str, Any]) -> float:
    pf = model["provider_facts"]
    return pf["base_latency_ms"]["value"] * (1.0 + view["input_tokens_k"] / 8.0)


def hard_and_technical_filter(mid, model, view, ent_policy):
    """Steps 1-2: enterprise/governance + verified technical eligibility."""
    pf = model["provider_facts"]
    hc = view.get("hard_constraints", {})
    # 1 enterprise/governance
    if pf["provider"]["value"] not in ent_policy["approved_providers"]:
        return False, "provider not approved", "approved_providers", "enterprise-hard-policy"
    if hc.get("require_on_prem") and pf["deployment_mode"]["value"] != "on-prem":
        return False, "deployment not on-prem", "residency", "enterprise-hard-policy"
    if hc.get("approved_deployment") and pf["deployment_mode"]["value"] not in hc["approved_deployment"]:
        return False, "deployment mode not approved", "deployment", "enterprise-hard-policy"
    # 2 verified technical eligibility
    ctx = pf["context_limit_tokens"]["value"]
    if view["input_tokens_k"] * 1000 > ctx:
        return False, f"input exceeds context limit {ctx}", "context", "verified-provider-fact"
    if hc.get("require_structured_strict") and pf["structured_output_support"]["value"] != "json-schema-strict":
        return False, "strict structured output unsupported", "structured_output", "verified-provider-fact"
    if hc.get("require_tools") and not pf["tool_support"]["value"]:
        return False, "tool calling unsupported", "tools", "verified-provider-fact"
    if hc.get("max_cost") is not None and estimate_cost(model, view) > hc["max_cost"]:
        return False, "expected cost exceeds hard ceiling", "max_cost", "enterprise-hard-policy"
    if hc.get("max_latency_ms") is not None and estimate_latency_ms(model, view) > hc["max_latency_ms"]:
        return False, "expected latency exceeds hard SLA", "max_latency", "enterprise-hard-policy"
    return True, None, None, None


def predict_quality(mid, view, telemetry, advisory) -> Dict[str, Any]:
    """Fuse observed telemetry + (optional) advisory + weak prior. Returns
    predicted quality, a confidence, predicted reliability, and evidence list.

    `advisory` is None (F1/F2) or a validated task-shape dict (G)."""
    tc = view["task_class"]
    ev: List[Dict[str, Any]] = []
    tel = telemetry.get(mid, {}).get(tc)
    weight_sum = 0.0
    val_sum = 0.0
    determinate_conf = 0.0
    reliability = None
    if tel and tel["n"] > 0:
        conf = tel["n"] / (tel["n"] + FUSION["telemetry_conf_k"])
        w = FUSION["observed_base"] * conf
        val_sum += tel["quality_mean"] * w
        weight_sum += w
        determinate_conf += conf
        reliability = tel.get("schema_valid_rate")
        ev.append({"source": "runtime-observed", "provenance": "runtime-observed",
                   "value": round(tel["quality_mean"], 4), "confidence": round(conf, 4),
                   "n": tel["n"]})
    if advisory is not None:
        adj = adv.difficulty_to_quality_prior(advisory.get("anticipated_reasoning_difficulty", "medium"))
        base = tel["quality_mean"] if (tel and tel["n"] > 0) else FUSION["prior_value"]
        aval = clamp(base + adj)
        w = FUSION["advisory_base"] * FUSION["advisory_conf"]
        val_sum += aval * w
        weight_sum += w
        determinate_conf += FUSION["advisory_conf"] * 0.5
        ev.append({"source": "model-advisory", "provenance": "model-advisory",
                   "value": round(aval, 4), "confidence": FUSION["advisory_conf"],
                   "advisory_fields": advisory})
    # weak neutral prior so a value always exists
    w = FUSION["prior_base"]
    val_sum += FUSION["prior_value"] * w
    weight_sum += w
    predicted = val_sum / weight_sum if weight_sum else FUSION["prior_value"]
    return {"predicted_quality": round(predicted, 4), "confidence": round(determinate_conf, 4),
            "predicted_reliability": reliability, "evidence": ev}


def route(task: Dict[str, Any], registry: Dict[str, Any], telemetry: Dict[str, Any],
          regime: str, mode: str, advisory_map: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """mode in {'F1','F2','G'}. advisory_map (G only): {model_id: task-shape dict}.
    Returns a full decision record."""
    view = routing_view(task)
    _assert_boundary(view)
    ent = registry["enterprise_policy"]
    models = registry["models"]
    use_advisory = (mode == "G")
    if use_advisory:
        advisory_map = advisory_map or {}
        for a in advisory_map.values():
            adv.validate(a)  # enforce task-shape-only field restriction
    min_q = view.get("min_acceptable_quality", 0.0)

    rec = {"task_id": view["task_id"], "task_class": view["task_class"], "mode": mode,
           "regime": regime, "policy_version": POLICY_VERSION, "registry_version": registry["version"],
           "telemetry_version": telemetry.get("_version", "none"),
           "eligible": [], "eliminated": [], "gate": [], "scored": [],
           "selected": None, "fallback_chain": [], "abstained": False, "abstain_reason": None,
           "self_assessment_used": use_advisory, "preflight_cost": 0.0, "preflight_latency_ms": 0.0,
           "uncertainty": None}

    # Steps 1-2
    survivors = []
    for mid, model in models.items():
        ok, reason, constraint, prov = hard_and_technical_filter(mid, model, view, ent)
        if ok:
            survivors.append(mid)
        else:
            rec["eliminated"].append({"model": mid, "reason": reason, "constraint": constraint,
                                      "provenance": prov, "stage": "hard/technical"})

    # quality prediction for survivors
    preds = {mid: predict_quality(mid, view, telemetry,
                                  (advisory_map.get(mid) if use_advisory else None))
             for mid in survivors}

    # Steps 3-4: quality + reliability gate (F2 / G only; F1 skips the gate)
    gated = []
    for mid in survivors:
        p = preds[mid]
        gate_entry = {"model": mid, "predicted_quality": p["predicted_quality"],
                      "min_required": min_q, "confidence": p["confidence"]}
        if mode == "F1":
            gate_entry["result"] = "no-gate (soft quality)"
            gated.append(mid)
        else:
            # Lenient on thin evidence (F2 AND G): never hard-eliminate on a
            # low-confidence quality estimate -- that would cause over-abstention.
            indeterminate = p["confidence"] < FUSION["gate_confidence_floor"]
            if indeterminate:
                gate_entry["result"] = "indeterminate-pass (low evidence)"
                gated.append(mid)
            elif p["predicted_quality"] >= min_q:
                gate_entry["result"] = "pass"
                gated.append(mid)
            else:
                gate_entry["result"] = "fail-min-quality"
                rec["eliminated"].append({"model": mid, "reason": f"predicted quality "
                                          f"{p['predicted_quality']} < min {min_q}",
                                          "constraint": "min_quality", "provenance": "gate", "stage": "quality-gate"})
            # reliability gate for strict-schema tasks
            if mid in gated and view.get("hard_constraints", {}).get("require_structured_strict"):
                rel = p["predicted_reliability"]
                if rel is not None and rel < FUSION["min_reliability"]:
                    gated.remove(mid)
                    gate_entry["result"] = "fail-min-reliability"
                    rec["eliminated"].append({"model": mid, "reason": f"predicted reliability {rel} < "
                                              f"{FUSION['min_reliability']}", "constraint": "min_reliability",
                                              "provenance": "gate", "stage": "reliability-gate"})
        rec["gate"].append(gate_entry)

    rec["eligible"] = gated

    # preflight tax for G (charged per candidate assessed = survivors before gate)
    if use_advisory:
        rec["preflight_latency_ms"] = adv.PREFLIGHT_LATENCY_MS
        rec["_preflight_candidates"] = len(survivors)

    if not gated:
        rec["abstained"] = True
        rec["abstain_reason"] = ("no model passes hard/technical + minimum-quality gate"
                                 if survivors else "no model satisfies hard/technical constraints")
        return rec

    # Step 5: rank by utility
    wq, wc, wl = PRIORITY_WEIGHTS[view.get("business_priority", "balanced")]
    cost_ref = max(estimate_cost(models[m], view) for m in gated) or 1.0
    lat_ref = max(estimate_latency_ms(models[m], view) for m in gated) or 1.0
    scored = []
    for mid in gated:
        p = preds[mid]
        c = estimate_cost(models[mid], view) / cost_ref
        l = estimate_latency_ms(models[mid], view) / lat_ref
        utility = wq * p["predicted_quality"] - wc * c - wl * l
        scored.append({"model": mid, "utility": round(utility, 4),
                       "predicted_quality": p["predicted_quality"], "confidence": p["confidence"],
                       "est_cost": round(estimate_cost(models[mid], view), 6),
                       "est_latency_ms": round(estimate_latency_ms(models[mid], view), 1),
                       "components": {"quality": round(wq * p["predicted_quality"], 4),
                                      "cost_penalty": round(-wc * c, 4),
                                      "latency_penalty": round(-wl * l, 4)},
                       "evidence": p["evidence"]})
    scored.sort(key=lambda s: (-s["utility"], s["model"]))
    rec["scored"] = scored
    rec["selected"] = scored[0]["model"]
    rec["fallback_chain"] = [s["model"] for s in scored[1:]]
    rec["uncertainty"] = scored[0]["confidence"]
    return rec
