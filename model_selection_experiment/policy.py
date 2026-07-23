"""The smallest defensible Model Selection Policy interpreter.

Pipeline (deterministic, pure given its inputs):
  1. task classification (provided by corpus in this experiment)
  2. constraint resolution   -> ConstraintSet from task + enterprise policy
  3. eligibility filtering    -> eliminate models failing hard constraints
  4. evidence-weighted capability matching -> predicted quality (fusion)
  5. business-priority scoring -> utility
  6. ranked fallback generation
  7. deterministic explanation record

The policy reads ONLY the registry (declared + measured), the telemetry feed
(runtime-observed), enterprise policy, and -- for arm G only -- the bounded
advisory feed. It NEVER reads ground truth.

Cost and latency are read from declared facts (accurate). Quality is estimated
by fusion. This is where evidence quality matters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from common import POLICY_VERSION, REGISTRY_VERSION, weighted_caps


class SelfAssessmentViolation(ValueError):
    """Raised when advisory input tries to supply a forbidden (non-self-knowledge) field."""


def _declared(model: Dict[str, Any], key: str) -> Any:
    return model["declared"][key]["value"]


def resolve_constraints(task: Dict[str, Any], enterprise_policy: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 2: build the concrete ConstraintSet for this request."""
    hc = dict(task.get("hard_constraints", {}))
    return {
        "approved_providers": enterprise_policy["approved_providers"],
        "privacy": hc.get("privacy"),
        "require_on_prem": hc.get("require_on_prem", False),
        "require_modality": hc.get("require_modality"),
        "require_tools": hc.get("require_tools", False),
        "require_structured_strict": hc.get("require_structured_strict", False),
        "max_cost": hc.get("max_cost"),
        "max_latency_ms": hc.get("max_latency_ms"),
        "max_context_k": hc.get("max_context_k"),
        "input_tokens_k": task["input_tokens_k"],
    }


def estimate_cost(model: Dict[str, Any], task: Dict[str, Any]) -> float:
    return _declared(model, "price_per_ktok") * task["input_tokens_k"] * 1.25


def estimate_latency_ms(model: Dict[str, Any], task: Dict[str, Any]) -> float:
    return _declared(model, "base_latency_ms") * (1.0 + task["input_tokens_k"] / 120.0)


def hard_filter(model: Dict[str, Any], task: Dict[str, Any], cs: Dict[str, Any]):
    """Stage 3: eligibility from VERIFIED facts + enterprise policy.

    Returns (eligible: bool, reason: str|None, constraint: str|None, provenance: str|None).
    Precedence: enterprise policy is checked first, then verified provider facts.
    """
    # --- enterprise-hard-policy (highest precedence) ---
    if _declared(model, "provider") not in cs["approved_providers"]:
        return False, f"provider '{_declared(model,'provider')}' not on approved list", \
            "approved_providers", "enterprise-hard-policy"
    if cs["privacy"] == "high" and _declared(model, "privacy_tier") != "high":
        return False, "privacy tier below required", "privacy", "enterprise-hard-policy"
    if cs["privacy"] == "high" and _declared(model, "trains_on_data"):
        return False, "provider trains on data; prohibited for confidential", \
            "privacy", "enterprise-hard-policy"
    if cs["require_on_prem"] and _declared(model, "deployment") != "on_prem":
        return False, "deployment not on-prem (residency)", "residency", "enterprise-hard-policy"
    # --- verified provider facts ---
    if cs["require_modality"] and cs["require_modality"] not in _declared(model, "modalities_in"):
        return False, f"required modality '{cs['require_modality']}' unsupported", \
            "modality", "verified-provider-fact"
    if cs["require_tools"] and not _declared(model, "tool_calling"):
        return False, "tool calling required but unsupported", "tools", "verified-provider-fact"
    if cs["require_structured_strict"] and not _declared(model, "structured_strict"):
        return False, "strict structured output unsupported", "structured_output", "verified-provider-fact"
    # Context: the policy uses DECLARED context (all it can see). Where declared
    # overstates true effective context, this is the point where a naive registry
    # would wrongly admit a model -- the experiment measures that as a context trap.
    if task["input_tokens_k"] > _declared(model, "declared_context_k"):
        return False, (f"input {task['input_tokens_k']}k exceeds declared context "
                       f"{_declared(model,'declared_context_k')}k"), "context", "verified-provider-fact"
    if cs["max_context_k"] is not None and task["input_tokens_k"] > cs["max_context_k"]:
        return False, "input exceeds task max_context_k", "context", "enterprise-hard-policy"
    # Hard cost / latency ceilings (verified facts vs task cap).
    if cs["max_cost"] is not None and estimate_cost(model, task) > cs["max_cost"]:
        return False, "expected cost exceeds hard ceiling", "max_cost", "enterprise-hard-policy"
    if cs["max_latency_ms"] is not None and estimate_latency_ms(model, task) > cs["max_latency_ms"]:
        return False, "expected p50 latency exceeds hard SLA", "max_latency", "enterprise-hard-policy"
    return True, None, None, None


def _validate_advisory(advisory: Dict[str, Any], policy: Dict[str, Any]) -> None:
    forbidden = set(policy["self_assessment_forbidden_fields"])
    for k in advisory:
        if k in forbidden:
            raise SelfAssessmentViolation(f"advisory supplied forbidden field '{k}'")


def fuse_quality(model: Dict[str, Any], task: Dict[str, Any], telemetry: Dict[str, Any],
                 policy: Dict[str, Any], advisory: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Stage 4: confidence-weighted fusion of quality evidence.

    Sources: provider-declared (optimistic tier), benchmark-measured (noisy,
    gapped), runtime-observed (regime-dependent), model-advisory (arm G only).
    Returns predicted quality + the evidence list (for the explanation record).
    """
    ef = policy["evidence_fusion"]
    bw = ef["base_weights"]
    tclass = task["task_class"]
    mid = model["id"]
    evidence: List[Dict[str, Any]] = []

    # provider-declared overall tier (low-confidence, optimistic)
    dov = model["declared"]["declared_overall"]
    evidence.append({"source": "provider-declared", "provenance": "provider-declared",
                     "value": dov["value"], "confidence": ef["declared_confidence"],
                     "weight": bw["provider-declared"] * ef["declared_confidence"]})

    # benchmark-measured: weighted average of measured caps over required caps
    measured = model["measured"]["capability_scores"]
    req = task["required_caps"]
    covered = {c: measured[c]["value"] for c in req if c in measured}
    if covered:
        # average over the required caps we DO have measurements for
        w = {c: req[c] for c in covered}
        bval = weighted_caps(covered, w)
        evidence.append({"source": "benchmark-measured", "provenance": "benchmark-measured",
                         "value": round(bval, 4), "confidence": ef["benchmark_confidence"],
                         "weight": bw["benchmark-measured"] * ef["benchmark_confidence"],
                         "coverage": f"{len(covered)}/{len(req)} required caps"})

    # runtime-observed telemetry for this (model, task_class)
    tel = telemetry.get(mid, {}).get(tclass)
    if tel:
        n = tel["n"]
        conf = n / (n + ef["telemetry_confidence_k"])
        evidence.append({"source": "runtime-observed", "provenance": "runtime-observed",
                         "value": tel["estimate"], "confidence": round(conf, 4),
                         "weight": bw["runtime-observed"] * conf, "n": n})

    # model-advisory (arm G only)
    if advisory is not None and "suitability_estimate" in advisory:
        conf = policy["evidence_fusion"]["advisory_confidence"]
        evidence.append({"source": "model-advisory", "provenance": "model-advisory",
                         "value": advisory["suitability_estimate"], "confidence": conf,
                         "weight": bw["model-advisory"] * conf})

    total_w = sum(e["weight"] for e in evidence) or 1.0
    predicted = sum(e["value"] * e["weight"] for e in evidence) / total_w
    return {"predicted_quality": round(predicted, 4), "evidence": evidence}


def score(model: Dict[str, Any], task: Dict[str, Any], predicted_q: float,
          cost_ref: float, lat_ref: float) -> Dict[str, Any]:
    """Stage 5: business-priority utility from predicted quality + accurate cost/latency."""
    w = task["utility_weights"]
    c = estimate_cost(model, task) / (cost_ref or 1.0)
    l = estimate_latency_ms(model, task) / (lat_ref or 1.0)
    utility = w["quality"] * predicted_q - w["cost"] * c - w["latency"] * l
    return {"utility": round(utility, 4),
            "components": {"quality": round(w["quality"] * predicted_q, 4),
                           "cost_penalty": round(-w["cost"] * c, 4),
                           "latency_penalty": round(-w["latency"] * l, 4)},
            "est_cost": round(estimate_cost(model, task), 4),
            "est_latency_ms": round(estimate_latency_ms(model, task), 1)}


def route(task: Dict[str, Any], registry: Dict[str, Any], enterprise_policy: Dict[str, Any],
          telemetry: Dict[str, Any], policy: Dict[str, Any], regime: str,
          advisory_by_model: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Full policy route. advisory_by_model set => arm G; None => arm F.

    Returns a complete, deterministic decision record.
    """
    cs = resolve_constraints(task, enterprise_policy)
    models = registry["models"]

    eliminated: List[Dict[str, Any]] = []
    eligible_ids: List[str] = []
    for mid, model in models.items():
        ok, reason, constraint, prov = hard_filter(model, task, cs)
        if ok:
            eligible_ids.append(mid)
        else:
            eliminated.append({"model": mid, "reason": reason, "constraint": constraint,
                               "provenance": prov})

    arm = "G" if advisory_by_model is not None else "F"
    record: Dict[str, Any] = {
        "arm": arm, "task_id": task["task_id"], "task_class": task["task_class"],
        "regime": regime, "policy_version": policy["version"],
        "registry_version": registry["version"], "eligible": eligible_ids,
        "eliminated": eliminated, "scored": [], "fallback_chain": [],
        "selected": None, "abstained": False, "abstain_reason": None,
        "preflight_cost": 0.0, "preflight_latency_ms": 0.0, "advisory_used": None,
    }

    # Stage 3b: eligibility gate
    if not eligible_ids:
        record["abstained"] = True
        record["abstain_reason"] = "no model satisfies all hard constraints (empty eligible set)"
        return record

    # normalisation refs over eligible set (accurate facts)
    cost_ref = max(estimate_cost(models[m], task) for m in eligible_ids) or 1.0
    lat_ref = max(estimate_latency_ms(models[m], task) for m in eligible_ids) or 1.0

    scored: List[Dict[str, Any]] = []
    for mid in eligible_ids:
        model = models[mid]
        adv = None
        if advisory_by_model is not None:
            adv = advisory_by_model.get(mid)
            if adv is not None:
                _validate_advisory(adv, policy)  # enforce field restrictions
        fq = fuse_quality(model, task, telemetry, policy, adv)
        sc = score(model, task, fq["predicted_quality"], cost_ref, lat_ref)
        scored.append({"model": mid, "predicted_quality": fq["predicted_quality"],
                       "utility": sc["utility"], "components": sc["components"],
                       "est_cost": sc["est_cost"], "est_latency_ms": sc["est_latency_ms"],
                       "evidence": fq["evidence"]})

    # Stage 6: rank + fallback (deterministic tie-break by model id)
    scored.sort(key=lambda s: (-s["utility"], s["model"]))
    record["scored"] = scored
    record["selected"] = scored[0]["model"]
    record["fallback_chain"] = [s["model"] for s in scored[1:]]

    if advisory_by_model is not None:
        record["advisory_used"] = {mid: advisory_by_model[mid] for mid in eligible_ids
                                   if mid in advisory_by_model}
        record["preflight_cost"] = round(len(eligible_ids) * 0.0, 6)  # set by harness feed
    return record
