"""Build the versioned data artifacts for the experiment.

Emits four JSON files into ./data:

  ground_truth_v1.json  -- TRUE latent model behavior. Visible ONLY to the
                           simulator/oracle. Never read by a routing arm.
  registry_v1.json      -- Policy-visible capability registry. Contains
                           provider-DECLARED facts and MEASURED benchmark
                           scores (a noisy, partially-covered view of ground
                           truth). Every value carries provenance.
  corpus_v1.json        -- Task corpus with explicit constraints + ground truth
                           references (business priority, thresholds, etc.).
  policy_v1.json        -- Declarative policy: scoring weights, evidence-fusion
                           confidences, precedence, thresholds.

ALL SYNTHETIC ASSUMPTIONS ARE EXPLICIT and documented inline. The generative
model is deliberately NOT rigged in favor of the policy engine:
  * cost and latency are accurate, verifiable facts for every arm (the policy
    gets no private advantage there);
  * the uncertain quantity is task quality, which every arm must estimate from
    whatever evidence it is allowed to use;
  * declared capability tiers are OPTIMISTICALLY biased (as real spec sheets
    are), so a policy that leans on declared evidence is penalised, not helped;
  * benchmark coverage has GAPS, so no arm has complete measured evidence.
"""

from __future__ import annotations

import os

from common import (
    CAPS,
    DATA_DIR,
    GROUND_TRUTH_VERSION,
    REGISTRY_VERSION,
    clamp,
    det_signed,
    det_unit,
    save_json,
    weighted_caps,
)

# ---------------------------------------------------------------------------
# GROUND TRUTH -- true latent capability per model (0..1), plus verifiable
# operational facts. These facts (deployment, provider, price, latency,
# modalities, tools, structured-output, TRUE effective context) are treated as
# accurate and knowable by any arm; the *quality* caps are hidden.
# ---------------------------------------------------------------------------
GROUND_TRUTH_MODELS = {
    "m_small_local": {
        "label": "small local model",
        "caps": dict(reasoning=0.35, coding=0.30, extraction=0.55, summarization=0.50,
                     classification=0.72, long_context=0.25, multilingual=0.30,
                     structured_output=0.55, tool_use=0.28),
        "provider": "internal", "deployment": "on_prem", "privacy_tier": "high",
        "trains_on_data": False, "price_per_ktok": 0.02, "base_latency_ms": 250,
        "true_effective_context_k": 8, "modalities_in": ["text"],
        "tool_calling": False, "structured_strict": False,
    },
    "m_medium_general": {
        "label": "medium general model",
        "caps": dict(reasoning=0.60, coding=0.55, extraction=0.68, summarization=0.70,
                     classification=0.76, long_context=0.55, multilingual=0.60,
                     structured_output=0.72, tool_use=0.72),
        "provider": "vendor_alpha", "deployment": "approved_cloud", "privacy_tier": "medium",
        "trains_on_data": False, "price_per_ktok": 0.15, "base_latency_ms": 600,
        "true_effective_context_k": 32, "modalities_in": ["text"],
        "tool_calling": True, "structured_strict": True,
    },
    "m_strong_reason": {
        "label": "strong reasoning model",
        "caps": dict(reasoning=0.90, coding=0.70, extraction=0.75, summarization=0.80,
                     classification=0.80, long_context=0.75, multilingual=0.72,
                     structured_output=0.78, tool_use=0.80),
        "provider": "vendor_beta", "deployment": "approved_cloud", "privacy_tier": "medium",
        "trains_on_data": False, "price_per_ktok": 0.90, "base_latency_ms": 1400,
        "true_effective_context_k": 128, "modalities_in": ["text"],
        "tool_calling": True, "structured_strict": True,
    },
    "m_coding_spec": {
        "label": "coding specialist model",
        "caps": dict(reasoning=0.72, coding=0.93, extraction=0.70, summarization=0.65,
                     classification=0.72, long_context=0.60, multilingual=0.55,
                     structured_output=0.86, tool_use=0.83),
        "provider": "vendor_gamma", "deployment": "approved_cloud", "privacy_tier": "medium",
        "trains_on_data": False, "price_per_ktok": 0.35, "base_latency_ms": 800,
        "true_effective_context_k": 64, "modalities_in": ["text"],
        "tool_calling": True, "structured_strict": True,
    },
    "m_long_multi": {
        "label": "long-context / multimodal model",
        "caps": dict(reasoning=0.70, coding=0.60, extraction=0.80, summarization=0.82,
                     classification=0.74, long_context=0.92, multilingual=0.78,
                     structured_output=0.72, tool_use=0.68),
        "provider": "vendor_delta", "deployment": "approved_cloud", "privacy_tier": "medium",
        "trains_on_data": False, "price_per_ktok": 0.80, "base_latency_ms": 1500,
        "true_effective_context_k": 400, "modalities_in": ["text", "image"],
        "tool_calling": True, "structured_strict": True,
    },
    "m_external_frontier": {
        "label": "external frontier model (non-approved provider)",
        "caps": dict(reasoning=0.93, coding=0.88, extraction=0.85, summarization=0.86,
                     classification=0.84, long_context=0.85, multilingual=0.88,
                     structured_output=0.88, tool_use=0.90),
        "provider": "vendor_omega", "deployment": "external_api", "privacy_tier": "low",
        "trains_on_data": True, "price_per_ktok": 1.30, "base_latency_ms": 1100,
        "true_effective_context_k": 150, "modalities_in": ["text", "image"],
        "tool_calling": True, "structured_strict": True,
    },
}

# Declared context OVERSTATES true effective context (spec-sheet optimism).
DECLARED_CONTEXT_INFLATION = {
    "m_small_local": 1.0, "m_medium_general": 1.0, "m_strong_reason": 1.56,   # 128k true -> 200k declared
    "m_coding_spec": 1.0, "m_long_multi": 1.25, "m_external_frontier": 1.0,
}

# Synthetic evidence-noise assumptions (documented; tune-here only).
DECLARED_OPTIMISM = 0.12    # declared capability tier reads high vs truth
DECLARED_CONFIDENCE = 0.30
BENCH_NOISE = 0.08          # stddev-like magnitude of benchmark measurement error
BENCH_CONFIDENCE = 0.60
BENCH_GAP_RATE = 0.28       # fraction of (model, cap) benchmark cells that are MISSING


def build_ground_truth() -> dict:
    return {"version": GROUND_TRUTH_VERSION, "caps": CAPS, "models": GROUND_TRUTH_MODELS,
            "notes": "TRUE latent behavior; simulator/oracle only; never seen by a routing arm."}


def build_registry() -> dict:
    """Derive the policy-visible registry from ground truth + fixed evidence noise."""
    models = {}
    for mid, gt in GROUND_TRUTH_MODELS.items():
        overall = sum(gt["caps"].values()) / len(gt["caps"])
        # DECLARED capability tier: coarse, optimistic bucket.
        declared_overall = clamp(overall + DECLARED_OPTIMISM)
        declared_tier = "high" if declared_overall >= 0.8 else "medium" if declared_overall >= 0.6 else "low"
        # MEASURED benchmark per cap, with noise and coverage gaps.
        measured = {}
        for cap in CAPS:
            if det_unit("bench_gap", mid, cap) < BENCH_GAP_RATE:
                continue  # coverage gap: this cell was never benchmarked
            val = clamp(gt["caps"][cap] + det_signed("bench", mid, cap) * BENCH_NOISE)
            measured[cap] = {"value": round(val, 4), "provenance": "benchmark-measured",
                             "confidence": BENCH_CONFIDENCE, "method": "held-out synthetic eval",
                             "as_of": "2026-05"}
        declared_ctx = int(round(gt["true_effective_context_k"] * DECLARED_CONTEXT_INFLATION[mid]))
        models[mid] = {
            "id": mid, "label": gt["label"],
            # ---- provider-DECLARED, verifiable facts (accurate) ----
            "declared": {
                "provider": {"value": gt["provider"], "provenance": "provider-declared"},
                "deployment": {"value": gt["deployment"], "provenance": "provider-declared"},
                "privacy_tier": {"value": gt["privacy_tier"], "provenance": "provider-declared"},
                "trains_on_data": {"value": gt["trains_on_data"], "provenance": "provider-declared"},
                "price_per_ktok": {"value": gt["price_per_ktok"], "provenance": "provider-declared"},
                "base_latency_ms": {"value": gt["base_latency_ms"], "provenance": "provider-declared"},
                "declared_context_k": {"value": declared_ctx, "provenance": "provider-declared",
                                       "caveat": "advertised; may exceed effective"},
                "modalities_in": {"value": gt["modalities_in"], "provenance": "provider-declared"},
                "tool_calling": {"value": gt["tool_calling"], "provenance": "provider-declared"},
                "structured_strict": {"value": gt["structured_strict"], "provenance": "provider-declared"},
                "capability_tier": {"value": declared_tier, "provenance": "provider-declared",
                                    "confidence": DECLARED_CONFIDENCE,
                                    "caveat": "optimistic; marketing-biased"},
                "declared_overall": {"value": round(declared_overall, 4),
                                     "provenance": "provider-declared", "confidence": DECLARED_CONFIDENCE},
            },
            # ---- MEASURED benchmark evidence (noisy, gapped) ----
            "measured": {"capability_scores": measured},
        }
    return {"version": REGISTRY_VERSION, "caps": CAPS, "models": models,
            "synthetic_assumptions": {
                "declared_optimism": DECLARED_OPTIMISM,
                "benchmark_noise": BENCH_NOISE,
                "benchmark_confidence": BENCH_CONFIDENCE,
                "benchmark_gap_rate": BENCH_GAP_RATE,
                "declared_context_inflation": DECLARED_CONTEXT_INFLATION,
                "note": "cost/latency/deployment/provider/modality are accurate facts; "
                        "quality is the uncertain quantity every arm must estimate."}}


# ---------------------------------------------------------------------------
# ENTERPRISE POLICY (governance plane): what is allowed by default.
# ---------------------------------------------------------------------------
DEFAULT_APPROVED_PROVIDERS = ["internal", "vendor_alpha", "vendor_beta", "vendor_gamma", "vendor_delta"]
# NOTE: vendor_omega (external frontier) is NOT approved by default -> a naive
# "always strongest" arm will select it and violate policy.


# ---------------------------------------------------------------------------
# TASK CORPUS
# ---------------------------------------------------------------------------
# Each task class maps to the capability weighting that defines quality for it.
CLASS_CAP_WEIGHTS = {
    "extraction": {"extraction": 1.0, "structured_output": 0.4},
    "classification": {"classification": 1.0},
    "summarization": {"summarization": 1.0, "reasoning": 0.3},
    "coding": {"coding": 1.0, "reasoning": 0.3},
    "structured_output_generation": {"structured_output": 1.0, "extraction": 0.3},
    "long_context_analysis": {"long_context": 1.0, "reasoning": 0.5},
    "reasoning": {"reasoning": 1.0},
    "multilingual": {"multilingual": 1.0, "summarization": 0.3},
    "privacy_sensitive": {"extraction": 0.7, "summarization": 0.6},
    "tool_requiring": {"tool_use": 1.0, "reasoning": 0.4},
    "latency_sensitive": {"classification": 0.7, "extraction": 0.6},
    "cost_sensitive": {"summarization": 0.7, "classification": 0.5},
}

# Business-priority profiles -> utility weights (quality, cost, latency).
PRIORITY_PROFILES = {
    "quality_first": (1.0, 0.15, 0.10),
    "balanced": (1.0, 0.45, 0.35),
    "cost_first": (0.7, 1.0, 0.25),
    "latency_first": (0.8, 0.25, 1.0),
}


def _base_task(tid, tclass, tokens_k, priority, threshold, constraints, note=""):
    return {
        "task_id": tid, "task_class": tclass,
        "required_caps": CLASS_CAP_WEIGHTS[tclass],
        "input_tokens_k": tokens_k,
        "business_priority": priority,
        "utility_weights": dict(zip(("quality", "cost", "latency"), PRIORITY_PROFILES[priority])),
        "acceptable_quality_threshold": threshold,
        "hard_constraints": constraints,
        "note": note,
    }


def build_corpus() -> dict:
    tasks = []
    # 12 task classes; several deterministic variants each.
    matrix = [
        # (class, [(tokens_k, priority, threshold, extra_constraints, note), ...])
        ("extraction", [(6, "balanced", 0.62, {}, ""), (20, "cost_first", 0.60, {"max_cost": 0.5}, ""),
                        (40, "balanced", 0.68, {}, "")]),
        ("classification", [(2, "latency_first", 0.65, {"max_latency_ms": 500}, ""),
                            (4, "cost_first", 0.62, {"max_cost": 0.05}, ""),
                            (8, "balanced", 0.66, {}, "")]),
        ("summarization", [(10, "balanced", 0.66, {}, ""), (30, "quality_first", 0.72, {}, ""),
                           (18, "cost_first", 0.62, {"max_cost": 0.6}, "")]),
        ("coding", [(8, "quality_first", 0.75, {"require_tools": True}, ""),
                    (16, "balanced", 0.72, {"require_tools": True}, ""),
                    (30, "quality_first", 0.78, {"require_tools": True}, "")]),
        ("structured_output_generation", [(6, "balanced", 0.68, {"require_structured_strict": True}, ""),
                                          (12, "quality_first", 0.72, {"require_structured_strict": True}, "")]),
        ("long_context_analysis", [(90, "quality_first", 0.70, {}, "needs large ctx"),
                                   (160, "balanced", 0.70, {}, "context trap vs declared"),
                                   (350, "quality_first", 0.72, {}, "very large ctx")]),
        ("reasoning", [(6, "quality_first", 0.78, {}, ""), (12, "balanced", 0.74, {}, ""),
                       (10, "quality_first", 0.80, {}, "high bar")]),
        ("multilingual", [(8, "balanced", 0.66, {}, ""), (14, "quality_first", 0.72, {}, "")]),
        ("privacy_sensitive", [(10, "balanced", 0.60, {"privacy": "high", "require_on_prem": True}, "PHI on-prem"),
                               (6, "quality_first", 0.62, {"privacy": "high", "require_on_prem": True}, "confidential")]),
        ("tool_requiring", [(8, "balanced", 0.66, {"require_tools": True}, ""),
                            (14, "quality_first", 0.72, {"require_tools": True}, "")]),
        ("latency_sensitive", [(4, "latency_first", 0.64, {"max_latency_ms": 450}, "tight SLA"),
                               (6, "latency_first", 0.66, {"max_latency_ms": 700}, "")]),
        ("cost_sensitive", [(12, "cost_first", 0.62, {"max_cost": 0.08}, "hard cap"),
                            (20, "cost_first", 0.60, {"max_cost": 0.15}, "")]),
        # multimodal
        ("extraction", [(12, "balanced", 0.66, {"require_modality": "image"}, "multimodal doc")]),
    ]
    idx = 0
    for tclass, variants in matrix:
        for (tokens_k, priority, threshold, extra, note) in variants:
            idx += 1
            tid = f"t{idx:03d}_{tclass}"
            tasks.append(_base_task(tid, tclass, tokens_k, priority, threshold, extra, note))

    # ---- Explicit ADVERSARIAL / AMBIGUOUS cases ----
    adversarial = [
        # Strongest model (external frontier) is best on quality but PROHIBITED provider.
        _base_task("t900_reasoning_trap", "reasoning", 8, "quality_first", 0.80,
                   {}, "frontier is best but not on allow-list; policy must reject it"),
        # Context trap: 160k exceeds strong_reason TRUE effective (128k) though declared 200k.
        _base_task("t901_ctx_trap", "long_context_analysis", 160, "quality_first", 0.70,
                   {"max_context_k": 160}, "declared 200k but true effective 128k -> trap"),
        # Cheapest eligible cannot meet the quality bar (small_local too weak);
        # no cost ceiling, so all approved models are eligible and cheapest-eligible
        # routing (arm C) will pick the weak cheap model and miss the quality bar.
        _base_task("t902_cheap_fails_quality", "reasoning", 5, "balanced", 0.78,
                   {}, "cheapest-eligible picks a too-weak model; policy should not"),
        # No eligible model: on-prem required AND image modality (only on_prem model is text-only).
        _base_task("t903_zero_eligible", "extraction", 6, "balanced", 0.62,
                   {"require_on_prem": True, "require_modality": "image"},
                   "on-prem + image => empty eligible set; must abstain"),
        # Ambiguous: two eligible models near-Pareto-tied on balanced priority.
        _base_task("t904_ambiguous", "summarization", 16, "balanced", 0.66,
                   {}, "multiple near-optimal picks"),
        # Latency + quality tension: tight SLA excludes the strong slow models.
        _base_task("t905_latency_quality", "reasoning", 6, "latency_first", 0.70,
                   {"max_latency_ms": 700}, "strong models too slow for SLA"),
    ]
    tasks.extend(adversarial)

    return {"version": "corpus_v1", "n_tasks": len(tasks),
            "enterprise_policy": {"approved_providers": DEFAULT_APPROVED_PROVIDERS},
            "priority_profiles": PRIORITY_PROFILES,
            "tasks": tasks,
            "synthetic_assumptions": {
                "note": "quality of a (model,task) is the weighted average of the model's TRUE caps "
                        "over the task's required_caps, with context-rot penalties; cost/latency are "
                        "deterministic functions of price/base-latency and task size."}}


def build_policy() -> dict:
    return {
        "version": "policy_v1",
        # Utility weights come from each task's business priority; these are global knobs.
        "scoring": {
            "quality_weight_source": "task.utility_weights.quality",
            "cost_weight_source": "task.utility_weights.cost",
            "latency_weight_source": "task.utility_weights.latency",
        },
        # Evidence-fusion for the UNCERTAIN quantity (quality). Confidence-weighted.
        # Base weights multiply each source's confidence. Telemetry confidence grows
        # with sample count (regime), so telemetry dominates when mature and advisory
        # becomes marginal EMERGENTLY -- it is not hard-coded to zero.
        "evidence_fusion": {
            "base_weights": {
                "provider-declared": 0.5,   # optimistic tier; low trust
                "benchmark-measured": 1.0,
                "runtime-observed": 1.4,    # real production signal; highest predictive trust
                "model-advisory": 0.7,      # bounded self-assessment (arm G only)
            },
            "declared_confidence": DECLARED_CONFIDENCE,
            "benchmark_confidence": BENCH_CONFIDENCE,
            "advisory_confidence": 0.40,
            "telemetry_confidence_k": 12,   # conf = n / (n + k)
        },
        # PRECEDENCE. NOTE (evaluated in the report): for hard CONSTRAINTS the order
        # below is authoritative. For QUALITY PREDICTION we deliberately DO NOT use a
        # single precedence -- we use confidence-weighted fusion, because a single
        # "measured > observed" precedence is wrong for prediction (real telemetry
        # should outweigh a stale benchmark). This split is a finding, not an oversight.
        "constraint_precedence": [
            "enterprise-hard-policy",
            "verified-provider-fact",
            "benchmark-measured",
            "runtime-observed",
            "model-advisory",
        ],
        "abstain": {
            "min_predicted_quality": 0.0,   # abstain handled by zero-eligible; no quality abstain in v1
            "note": "v1 abstains only when the eligible set is empty; confidence-abstain is future work.",
        },
        # Bounded self-assessment: ONLY these advisory fields may influence routing.
        "self_assessment_allowed_fields": [
            "recommended_decomposition", "anticipated_tool_requirement",
            "anticipated_reasoning_difficulty", "anticipated_execution_limitation",
            "suitability_estimate",
        ],
        "self_assessment_forbidden_fields": [
            "price", "pricing", "latency", "expected_latency", "compliance",
            "deployment", "deployment_eligibility", "context_limit",
            "hard_context_limit", "provider_availability",
        ],
    }


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    save_json(os.path.join(DATA_DIR, "ground_truth_v1.json"), build_ground_truth())
    save_json(os.path.join(DATA_DIR, "registry_v1.json"), build_registry())
    save_json(os.path.join(DATA_DIR, "corpus_v1.json"), build_corpus())
    save_json(os.path.join(DATA_DIR, "policy_v1.json"), build_policy())
    print("wrote data artifacts to", DATA_DIR)


if __name__ == "__main__":
    main()
