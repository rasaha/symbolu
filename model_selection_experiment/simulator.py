"""The simulated world: ground-truth eligibility, outcomes, telemetry, oracle.

Only this module (and the metrics module, via the oracle) reads ground truth.
Routing arms never import from here except through the read-only telemetry and
advisory feeds, which are deliberately noisy views of the truth.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from model_selection_experiment.common import (
    REGIME_SAMPLES,
    clamp,
    det_signed,
    load_ground_truth,
    weighted_caps,
)

# Synthetic assumptions for outcome + evidence generation (explicit).
CONTEXT_ROT_SOFT = 0.70      # above 70% of true effective context, quality decays
CONTEXT_ROT_MAX_PENALTY = 0.35
OBS_NOISE_BASE = 0.10        # telemetry per-observation noise magnitude
ADVISORY_BIAS = 0.06         # self-assessment OVERCONFIDENCE (models read high)
ADVISORY_NOISE = 0.10        # self-assessment noise magnitude
ADVISORY_PREFLIGHT_COST = 0.004   # $ charged to arm G per task (preflight tokens)
ADVISORY_PREFLIGHT_LATENCY_MS = 220  # added to arm G latency

_GT = load_ground_truth()
GT_MODELS: Dict[str, Any] = _GT["models"]
MODEL_IDS: List[str] = list(GT_MODELS.keys())


# ---------------------------------------------------------------------------
# Hard-constraint eligibility, evaluated against TRUE facts.
# (The policy re-derives eligibility from registry facts; because those facts
# are accurate, the two agree -- except where declared context overstates the
# true effective limit, which is exactly the "context trap" test.)
# ---------------------------------------------------------------------------
def true_eligibility(model_id: str, task: Dict[str, Any], approved_providers: List[str]
                     ) -> Tuple[bool, Optional[str]]:
    m = GT_MODELS[model_id]
    hc = task.get("hard_constraints", {})

    if m["provider"] not in approved_providers:
        return False, f"provider '{m['provider']}' not on approved list"
    if hc.get("privacy") == "high" and m["privacy_tier"] != "high":
        return False, "privacy tier below required (confidential/PHI)"
    if hc.get("require_on_prem") and m["deployment"] != "on_prem":
        return False, "deployment not on-prem (residency)"
    if m["trains_on_data"] and hc.get("privacy") == "high":
        return False, "provider trains on data; prohibited for confidential"
    req_mod = hc.get("require_modality")
    if req_mod and req_mod not in m["modalities_in"]:
        return False, f"required modality '{req_mod}' unsupported"
    if hc.get("require_tools") and not m["tool_calling"]:
        return False, "tool calling required but unsupported"
    if hc.get("require_structured_strict") and not m["structured_strict"]:
        return False, "strict structured output required but unsupported"
    # Context: use TRUE effective context (this is where declared may overstate).
    if task["input_tokens_k"] > m["true_effective_context_k"]:
        return False, (f"input {task['input_tokens_k']}k exceeds effective context "
                       f"{m['true_effective_context_k']}k")
    if hc.get("max_context_k") is not None and task["input_tokens_k"] > hc["max_context_k"]:
        return False, "input exceeds task max_context_k"
    # Hard cost / latency ceilings must bound the oracle's eligible set too, so a
    # policy that correctly refuses a task no model can satisfy is not charged regret.
    if hc.get("max_cost") is not None and true_cost(model_id, task) > hc["max_cost"]:
        return False, "true cost exceeds hard ceiling"
    if hc.get("max_latency_ms") is not None and true_latency_ms(model_id, task) > hc["max_latency_ms"]:
        return False, "true latency exceeds hard SLA"
    return True, None


def true_quality(model_id: str, task: Dict[str, Any]) -> float:
    m = GT_MODELS[model_id]
    q = weighted_caps(m["caps"], task["required_caps"])
    # context-rot penalty as utilisation approaches the true effective limit
    util = task["input_tokens_k"] / max(1, m["true_effective_context_k"])
    if util > CONTEXT_ROT_SOFT:
        frac = (util - CONTEXT_ROT_SOFT) / (1.0 - CONTEXT_ROT_SOFT)
        q -= CONTEXT_ROT_MAX_PENALTY * clamp(frac)
    return clamp(q)


def true_cost(model_id: str, task: Dict[str, Any]) -> float:
    # simple, accurate: price * tokens (assume output ~ 25% of input for costing)
    m = GT_MODELS[model_id]
    ktok = task["input_tokens_k"] * 1.25
    return m["price_per_ktok"] * ktok


def true_latency_ms(model_id: str, task: Dict[str, Any]) -> float:
    m = GT_MODELS[model_id]
    return m["base_latency_ms"] * (1.0 + task["input_tokens_k"] / 120.0)


# ---------------------------------------------------------------------------
# Evidence feeds handed to routing arms (noisy views of truth).
# ---------------------------------------------------------------------------
def telemetry_feed(regime: str) -> Dict[str, Dict[str, Dict[str, float]]]:
    """runtime-observed quality per (model, task_class), given a regime.

    Returns {model_id: {task_class: {"estimate":.., "confidence":.., "n":..}}}.
    Cold regime => empty (no telemetry). Estimate is truth + noise that shrinks
    with sample count; confidence = n/(n+k) computed by the policy, we expose n.
    """
    n = REGIME_SAMPLES[regime]
    feed: Dict[str, Dict[str, Dict[str, float]]] = {}
    if n == 0:
        return feed
    from model_selection_experiment.build_data import CLASS_CAP_WEIGHTS  # local import to avoid cycle at module load
    for mid in MODEL_IDS:
        feed[mid] = {}
        for tclass, weights in CLASS_CAP_WEIGHTS.items():
            tq = weighted_caps(GT_MODELS[mid]["caps"], weights)
            noise = det_signed("tel", regime, mid, tclass) * OBS_NOISE_BASE / (n ** 0.5)
            feed[mid][tclass] = {"estimate": round(clamp(tq + noise), 4), "n": n}
    return feed


def advisory_feed(model_id: str, task: Dict[str, Any], adversarial: bool = False) -> Dict[str, Any]:
    """Bounded self-assessment for arm G. ONLY self-knowledge fields.

    suitability_estimate is a biased, noisy read of the model's own true quality
    on this task. Overconfidence bias is positive (models read high). The
    'adversarial' flag inflates bias/noise to test harm.
    """
    bias = ADVISORY_BIAS * (3.0 if adversarial else 1.0)
    noise_mag = ADVISORY_NOISE * (2.0 if adversarial else 1.0)
    tq = true_quality(model_id, task)
    est = clamp(tq + bias + det_signed("adv", model_id, task["task_id"]) * noise_mag)
    # task-shape signals (advisory; not used numerically but recorded)
    needs_tools = task["required_caps"].get("tool_use", 0) > 0.5
    difficulty = "high" if tq < 0.6 else "medium" if tq < 0.78 else "low"
    return {
        "suitability_estimate": round(est, 4),
        "anticipated_tool_requirement": needs_tools,
        "anticipated_reasoning_difficulty": difficulty,
        "recommended_decomposition": "decompose" if task["input_tokens_k"] > 60 else "single-pass",
        "anticipated_execution_limitation": ("context pressure" if task["input_tokens_k"] > 100 else "none"),
        "provenance": "model-advisory",
        "confidence": 0.40,
    }


# ---------------------------------------------------------------------------
# Oracle + utility + regret (ground truth).
# ---------------------------------------------------------------------------
CONSTRAINT_VIOLATION_PENALTY = 2.0  # utility assigned to a hard-constraint-violating pick


def _norm_refs(task: Dict[str, Any], eligible: List[str]) -> Tuple[float, float]:
    """Reference max cost/latency over eligible set for normalisation (accurate facts)."""
    if not eligible:
        return 1.0, 1.0
    max_cost = max(true_cost(m, task) for m in eligible) or 1.0
    max_lat = max(true_latency_ms(m, task) for m in eligible) or 1.0
    return max_cost, max_lat


def true_utility(model_id: str, task: Dict[str, Any], eligible: List[str]) -> float:
    """Utility of actually running model_id on task, from ground truth."""
    w = task["utility_weights"]
    max_cost, max_lat = _norm_refs(task, eligible)
    q = true_quality(model_id, task)
    c = true_cost(model_id, task) / max_cost
    l = true_latency_ms(model_id, task) / max_lat
    return w["quality"] * q - w["cost"] * c - w["latency"] * l


def eligible_set(task: Dict[str, Any], approved_providers: List[str]) -> List[str]:
    return [m for m in MODEL_IDS if true_eligibility(m, task, approved_providers)[0]]


def oracle(task: Dict[str, Any], approved_providers: List[str]) -> Dict[str, Any]:
    elig = eligible_set(task, approved_providers)
    if not elig:
        return {"eligible": [], "best": None, "best_utility": 0.0, "pareto": []}
    utils = {m: true_utility(m, task, elig) for m in elig}
    best = max(utils, key=utils.get)
    # Pareto set on (quality up, cost down, latency down)
    pareto = []
    for a in elig:
        qa, ca, la = true_quality(a, task), true_cost(a, task), true_latency_ms(a, task)
        dominated = False
        for b in elig:
            if b == a:
                continue
            qb, cb, lb = true_quality(b, task), true_cost(b, task), true_latency_ms(b, task)
            if qb >= qa and cb <= ca and lb <= la and (qb > qa or cb < ca or lb < la):
                dominated = True
                break
        if not dominated:
            pareto.append(a)
    return {"eligible": elig, "best": best, "best_utility": utils[best],
            "utilities": utils, "pareto": pareto}


def regret_for_choice(task: Dict[str, Any], choice: Optional[str], approved_providers: List[str],
                      abstained: bool) -> Dict[str, Any]:
    """Regret = oracle utility - achieved utility.

    - Empty eligible set: correct action is to abstain (regret 0); a non-abstain
      pick there is impossible (no eligible model), abstain => 0.
    - A choice that violates a TRUE hard constraint gets utility = -PENALTY.
    """
    orc = oracle(task, approved_providers)
    if not orc["eligible"]:
        # empty set: abstaining is optimal; any "choice" would be a violation.
        if abstained or choice is None:
            return {"regret": 0.0, "violated": False, "oracle_best": None,
                    "achieved_utility": 0.0, "oracle_utility": 0.0, "empty_eligible": True}
        return {"regret": CONSTRAINT_VIOLATION_PENALTY, "violated": True, "oracle_best": None,
                "achieved_utility": -CONSTRAINT_VIOLATION_PENALTY, "oracle_utility": 0.0,
                "empty_eligible": True}
    if abstained or choice is None:
        # abstaining when eligible models existed forfeits the achievable utility.
        return {"regret": orc["best_utility"], "violated": False, "oracle_best": orc["best"],
                "achieved_utility": 0.0, "oracle_utility": orc["best_utility"], "empty_eligible": False}
    violated = not true_eligibility(choice, task, approved_providers)[0]
    if violated:
        achieved = -CONSTRAINT_VIOLATION_PENALTY
    else:
        achieved = true_utility(choice, task, orc["eligible"])
    return {"regret": max(0.0, orc["best_utility"] - achieved), "violated": violated,
            "oracle_best": orc["best"], "achieved_utility": achieved,
            "oracle_utility": orc["best_utility"], "empty_eligible": False}
