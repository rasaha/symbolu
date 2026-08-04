"""Deterministic cost / latency estimation from declared metadata.

These are ESTIMATES derived from configured class priors (or caller-supplied numeric
overrides), never measured production values. They are used identically by hard cost /
latency ceilings and by soft cost / latency scoring so a candidate is judged
consistently. See ``SCORING_AND_EXPLANATION.md`` for the evidence-class discussion.
"""

from __future__ import annotations

from .contracts import ModelCandidate

# Representative $ per 1k tokens for each cost class (configured prior).
_COST_CLASS_USD_PER_KTOK = {
    "very_low": 0.05, "low": 0.25, "medium": 1.0, "high": 3.0, "very_high": 8.0,
}
# Representative base latency in ms for each latency class (configured prior).
_LATENCY_CLASS_MS = {
    "very_fast": 150.0, "fast": 400.0, "medium": 900.0, "slow": 2000.0, "very_slow": 5000.0,
}

# Assume output tokens are ~15% of input for a modest generation (deterministic).
_OUTPUT_RATIO = 0.15
_MIN_OUTPUT_KTOK = 0.05


def cost_per_ktok(model: ModelCandidate) -> float:
    if model.est_cost_per_ktok is not None:
        return float(model.est_cost_per_ktok)
    return _COST_CLASS_USD_PER_KTOK[model.cost_class]


def base_latency_ms(model: ModelCandidate) -> float:
    if model.est_latency_ms is not None:
        return float(model.est_latency_ms)
    return _LATENCY_CLASS_MS[model.latency_class]


def estimate_cost(model: ModelCandidate, input_tokens: int) -> float:
    """Estimated request cost in USD (deterministic)."""
    ktok_in = max(0.0, input_tokens) / 1000.0
    ktok_out = max(_MIN_OUTPUT_KTOK, ktok_in * _OUTPUT_RATIO)
    ppk = cost_per_ktok(model)
    return ppk * (ktok_in + ktok_out)


def estimate_latency_ms(model: ModelCandidate, input_tokens: int) -> float:
    """Estimated p50 latency in ms (deterministic): base latency grows mildly with size."""
    ktok_in = max(0.0, input_tokens) / 1000.0
    return base_latency_ms(model) * (1.0 + ktok_in / 8.0)


__all__ = ["cost_per_ktok", "base_latency_ms", "estimate_cost", "estimate_latency_ms"]
