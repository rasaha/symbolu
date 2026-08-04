"""Decomposable, auditable candidate scoring.

Each dimension returns a *fit* score in [0, 1] where higher is better. Cost and latency
are normalized RELATIVE to the eligible set (cheapest / fastest eligible candidate scores
best), which is why scoring runs only after hard filtering. Every other dimension uses a
fixed, documented class-prior map.

All scores are ESTIMATED from declared metadata — never measured production performance.
No dimension asserts objective superiority; the weights are configured preferences.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .contracts import (
    AVAILABILITY_CLASS_ORDER,
    CandidateScore,
    ModelCandidate,
    ProviderCandidate,
    QUALITY_TIER_ORDER,
    RELIABILITY_CLASS_ORDER,
    SteeringRequest,
)
from .estimate import estimate_cost, estimate_latency_ms
from .policy import ROUND, RoutingPolicy

# --- fixed class-prior maps (documented in SCORING_AND_EXPLANATION.md) -----------------
_QUALITY_PRIOR = {t: round((i + 1) / len(QUALITY_TIER_ORDER), 4)
                  for i, t in enumerate(QUALITY_TIER_ORDER)}
_RELIABILITY_PRIOR = {t: round((i + 1) / len(RELIABILITY_CLASS_ORDER), 4)
                      for i, t in enumerate(RELIABILITY_CLASS_ORDER)}
_AVAILABILITY_PRIOR = {t: round((i + 1) / len(AVAILABILITY_CLASS_ORDER), 4)
                       for i, t in enumerate(AVAILABILITY_CLASS_ORDER)}

# Context headroom that earns a full context_fit score (4x the needed window).
_CONTEXT_TARGET_RATIO = 4.0


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _capability_fit(model: ModelCandidate, request: SteeringRequest) -> float:
    req_caps = request.requirements.required_capabilities
    if not req_caps:
        return 1.0
    present = sum(1 for c in req_caps if c in model.capabilities)
    return present / len(req_caps)  # all present were already hard-gated => 1.0 for eligible


def _policy_fit(model: ModelCandidate, provider: ProviderCandidate, request: SteeringRequest) -> float:
    """Soft policy alignment: reward candidates carrying the request's policy-domain tag."""
    domain = request.policy_domain
    tags = set(model.policy_tags) | set(provider.policy_tags)
    if domain and domain != "default" and domain in tags:
        return 1.0
    return 0.75  # neutral baseline (hard policy already enforced upstream)


def _context_fit(model: ModelCandidate, request: SteeringRequest) -> float:
    needed = max(request.requirements.min_context_window,
                 request.requirements.estimated_input_tokens)
    if needed <= 0:
        return 1.0
    headroom = model.context_limit / needed
    # 1x headroom -> 0, target-ratio headroom -> 1
    return _clamp01((headroom - 1.0) / (_CONTEXT_TARGET_RATIO - 1.0))


def _privacy_score(model: ModelCandidate, provider: ProviderCandidate) -> float:
    score = 1.0 if model.privacy_tier == "high" else 0.6
    if provider.trains_on_data:
        score *= 0.7
    return _clamp01(score)


def _relative_scores(values: List[float]) -> List[float]:
    """Map raw penalty values (cost/latency; lower is better) to fit scores in [0,1]
    relative to the eligible set: min -> 1.0, max -> 0.0. Constant sets score 1.0."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [1.0 for _ in values]
    return [1.0 - (v - lo) / (hi - lo) for v in values]


def score_eligible(
    eligible: List[Tuple[ModelCandidate, ProviderCandidate]],
    request: SteeringRequest,
    policy: RoutingPolicy,
) -> List[CandidateScore]:
    """Score every eligible ``(model, provider)`` pair. Returns scores in the same order
    as ``eligible`` (the controller sorts them)."""
    weights = policy.weights()
    input_tokens = request.requirements.estimated_input_tokens

    costs = [estimate_cost(m, input_tokens) for m, _ in eligible]
    lats = [estimate_latency_ms(m, input_tokens) for m, _ in eligible]
    cost_scores = _relative_scores(costs)
    latency_scores = _relative_scores(lats)

    results: List[CandidateScore] = []
    for idx, (model, provider) in enumerate(eligible):
        components: Dict[str, float] = {
            "capability_fit": _capability_fit(model, request),
            "policy_fit": _policy_fit(model, provider, request),
            "context_fit": _context_fit(model, request),
            "quality_score": _QUALITY_PRIOR[model.quality_tier],
            "latency_score": latency_scores[idx],
            "cost_score": cost_scores[idx],
            "privacy_score": _privacy_score(model, provider),
            "reliability_score": _RELIABILITY_PRIOR[model.reliability_class],
            "availability_score": _AVAILABILITY_PRIOR[model.availability_class],
        }
        weighted = {k: round(components[k] * weights[k], ROUND) for k in components}
        wsum = sum(weights[k] for k in components)
        total = round(sum(weighted.values()) / wsum, ROUND)
        components = {k: round(v, ROUND) for k, v in components.items()}
        results.append(CandidateScore(
            model_id=model.model_id,
            provider_id=model.provider_id,
            total=total,
            components=components,
            weighted=weighted,
        ))
    return results


def confidence_from_scores(sorted_scores: List[CandidateScore]) -> Tuple[float, str]:
    """Estimate a confidence in [0,1] from the score dispersion at the top of the ranking.

    This is a dispersion diagnostic, NOT a quality guarantee: a clear margin between the
    top candidate and the runner-up yields higher confidence; a single eligible candidate
    yields a fixed moderate confidence (no comparison was possible).
    """
    if not sorted_scores:
        return 0.0, "no eligible candidate"
    if len(sorted_scores) == 1:
        return 0.6, "single eligible candidate (no comparison possible)"
    gap = sorted_scores[0].total - sorted_scores[1].total
    conf = _clamp01(0.55 + gap * 1.5)
    return round(conf, ROUND), f"top-vs-runner-up score gap={round(gap, ROUND)}"


__all__ = ["score_eligible", "confidence_from_scores"]
