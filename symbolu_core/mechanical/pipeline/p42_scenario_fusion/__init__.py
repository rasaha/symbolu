"""
Phase 42: Scenario Fusion Engine

Fuses multiple scenario regime observations from Phase 41 into a unified
scenario field for later phases (43-47) to simulate or analyze.

This phase answers:
    "Across time, layers, and scenario inputs — what scenario field is emerging?"

It does NOT:
    - Pick a winner
    - Predict outcomes
    - Trigger simulations
    - Influence discourse, tone, or action

ARCHITECTURAL POSITION:
    - Phase 41 → local scenario snapshots
    - Phase 42 → global scenario field

INPUTS (Read-Only):
    Phase 42 MAY read:
        - One or more ScenarioRegimeMap objects from Phase 41
        - Phase 19 Drift Fusion Report (read-only, optional)
        - Phase 40 Cross-Horizon Alignment (read-only, optional)

    Phase 42 MUST NOT read:
        - Raw text
        - Semantics, intent, discourse
        - Acoustic / vrtti / kosha data
        - Governance / eligibility phases (>=50)

INVARIANTS:
    - INV-P42-1: Observer-only (no downstream authority impact)
    - INV-P42-2: Deterministic aggregation (no randomness, no learned weights)
    - INV-P42-3: No regime creation (cannot invent new regimes)
    - INV-P42-4: Monotonic ambiguity (more disagreement → higher entropy)
    - INV-P42-5: Absence-safe (empty input produces no output)

Usage:
    from symbolu_core.mechanical.pipeline.p42_scenario_fusion import (
        maybe_run_p42,
        run_p42_directly,
        fuse_scenario_regimes,
        ScenarioFusionField,
    )

    # Pipeline integration
    fusion_field = maybe_run_p42(ctx)

    # Direct usage (testing)
    fusion_field = fuse_scenario_regimes([scenario_map1, scenario_map2])
"""

# Schema
from .p42_schema import (
    P42_VERSION,
    DOMINANT_THRESHOLD,
    NUM_REGIMES,
    VALID_REGIMES,
    ScenarioRegime,
    ScenarioFusionField,
    create_scenario_fusion_field,
)

# Fusion logic
from .p42_fusion import (
    clamp,
    build_regime_distribution,
    select_dominant_regime,
    compute_fusion_confidence,
    compute_regime_entropy,
    fuse_scenario_regimes,
)

# Integration
from .p42_integration import (
    maybe_run_p42,
    run_p42_directly,
    is_p42_disabled,
    has_p42_fusion_field,
    get_p42_fusion_field,
    get_dominant_regime,
    get_fusion_confidence,
    get_regime_entropy,
    get_regime_distribution,
    is_dominant_stable,
    is_dominant_divergent,
    is_ambiguous,
    get_p42_version,
)


__all__ = [
    # Version
    "P42_VERSION",
    # Constants
    "DOMINANT_THRESHOLD",
    "NUM_REGIMES",
    "VALID_REGIMES",
    # Types
    "ScenarioRegime",
    # Schema
    "ScenarioFusionField",
    "create_scenario_fusion_field",
    # Fusion logic
    "clamp",
    "build_regime_distribution",
    "select_dominant_regime",
    "compute_fusion_confidence",
    "compute_regime_entropy",
    "fuse_scenario_regimes",
    # Integration
    "maybe_run_p42",
    "run_p42_directly",
    # Helpers
    "is_p42_disabled",
    "has_p42_fusion_field",
    "get_p42_fusion_field",
    "get_dominant_regime",
    "get_fusion_confidence",
    "get_regime_entropy",
    "get_regime_distribution",
    "is_dominant_stable",
    "is_dominant_divergent",
    "is_ambiguous",
    "get_p42_version",
]
