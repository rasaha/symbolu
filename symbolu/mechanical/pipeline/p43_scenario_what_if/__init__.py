"""
Phase 43: Scenario What-If Simulator

Generates bounded hypothetical scenario variations ("what-ifs")
derived from the fused scenario field (Phase 42).

These are possibility envelopes, not forecasts.

Phase 43 answers:
    "If the current scenario field were perturbed in controlled ways,
     what alternative scenario trajectories could exist?"

It does NOT:
    - Pick a preferred future
    - Forecast likelihood
    - Influence governance, discourse, or delivery
    - Feed any upstream decision logic

INPUTS (Read-Only):
    Phase 43 MAY read:
        - ScenarioFusionField from Phase 42
        - Optional: Phase 40 Cross-Horizon Alignment
        - Optional: Phase 19 Drift Fusion Report

    Phase 43 MUST NOT read:
        - Raw text
        - Semantics, intent, discourse
        - Acoustic / vrtti / kosha data
        - Regime gate outputs (P6)
        - Any governance or eligibility phases (>=50)

INVARIANTS:
    - INV-P43-1: Simulation only (no prediction, no likelihoods)
    - INV-P43-2: Deterministic perturbations (no randomness, seeded noise only if fixed)
    - INV-P43-3: Bounded exploration (exactly four variants, no more)
    - INV-P43-4: No authority impact (results never influence regime, discourse, or action)
    - INV-P43-5: Absence-safe (no base input -> no output)

Usage:
    from symbolu.mechanical.pipeline.p43_scenario_what_if import maybe_run_p43

    # In pipeline after P42:
    maybe_run_p43(ctx)

    # Access what-if set:
    if ctx.p43_scenario_what_if is not None:
        for variant in ctx.p43_scenario_what_if.what_if_variants:
            print(f"{variant.perturbation_type} -> {variant.resulting_regime}")
"""

# Schema exports
from .p43_schema import (
    P43_VERSION,
    VALID_PERTURBATIONS,
    VALID_REGIMES,
    DOMINANT_THRESHOLD,
    NUM_VARIANTS,
    ENTROPY_SHIFT_DELTA,
    CONFIDENCE_DROP_DELTA,
    NOISE_INJECTION_DELTA,
    ScenarioVariant,
    ScenarioWhatIfSet,
    create_scenario_variant,
    create_scenario_what_if_set,
)

# Simulator exports
from .p43_simulator import (
    simulate_what_if_variants,
    resolve_regime_from_distribution,
    apply_entropy_shift,
    apply_confidence_drop,
    apply_regime_flip,
    apply_noise_injection,
)

# Integration exports
from .p43_integration import (
    maybe_run_p43,
    run_p43_directly,
    is_p43_disabled,
    has_p43_what_if_set,
    get_p43_what_if_set,
    get_base_regime,
    get_variant_count,
    get_p43_version,
)

__all__ = [
    # Version and constants
    "P43_VERSION",
    "VALID_PERTURBATIONS",
    "VALID_REGIMES",
    "DOMINANT_THRESHOLD",
    "NUM_VARIANTS",
    "ENTROPY_SHIFT_DELTA",
    "CONFIDENCE_DROP_DELTA",
    "NOISE_INJECTION_DELTA",
    # Schema
    "ScenarioVariant",
    "ScenarioWhatIfSet",
    "create_scenario_variant",
    "create_scenario_what_if_set",
    # Simulator
    "simulate_what_if_variants",
    "resolve_regime_from_distribution",
    "apply_entropy_shift",
    "apply_confidence_drop",
    "apply_regime_flip",
    "apply_noise_injection",
    # Integration
    "maybe_run_p43",
    "run_p43_directly",
    "is_p43_disabled",
    "has_p43_what_if_set",
    "get_p43_what_if_set",
    "get_base_regime",
    "get_variant_count",
    "get_p43_version",
]
