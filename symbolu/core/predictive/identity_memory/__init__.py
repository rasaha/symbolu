"""
Phase 36 - Identity Resonance Memory

P36 is an observation-only memory phase that persists identity resonance patterns
over time, independent of momentary fluctuations. It is a memory of identity
behavior, NOT a decision system.

P36 answers: "What identity resonance patterns persist over time, independent
of momentary fluctuations?"

It:
- Remembers stability and drift patterns
- Smooths short-term noise
- Preserves historical identity context

It does NOT:
- Predict futures (Phase 35 does that)
- Influence regime, discourse, semantics, or tone
- Gate insights or actions
- Modify persona behavior

INVARIANTS:
    - INV-P36-1: Memory never alters present cognition
    - INV-P36-2: Memory is append-only
    - INV-P36-3: No authority escalation
    - INV-P36-4: Deterministic math only
    - INV-P36-5: Acoustic signals forbidden

Usage:
    from symbolu.core.predictive.identity_memory import (
        IdentityResonanceMemoryState,
        compute_identity_resonance_memory,
        compute_identity_resonance_index,
        compute_persistence_score,
        compute_volatility_index,
        stability_band_from_scores,
    )

    # Compute memory state from inputs
    state = compute_identity_resonance_memory(
        ucf_score=0.75,
        identity_harmonics_score=0.80,
        schema_stability=0.70,
        predicted_drift_score=0.30,
    )

    # Access outputs
    print(state.identity_resonance_index)  # [0.0, 1.0]
    print(state.identity_stability_band)   # "stable" | "soft" | "fragile"
    print(state.persistence_score)         # [0.0, 1.0]
    print(state.volatility_index)          # [0.0, 1.0]
"""

from symbolu.core.predictive.identity_memory.memory_state import (
    # Version
    P36_VERSION,
    # Enums
    IdentityStabilityBand,
    # Constants
    W_UCF_SCORE,
    W_IDENTITY_HARMONICS,
    W_SCHEMA_STABILITY,
    W_INVERSE_DRIFT,
    PERSISTENCE_STABLE_THRESHOLD,
    PERSISTENCE_FRAGILE_THRESHOLD,
    VOLATILITY_STABLE_THRESHOLD,
    VOLATILITY_FRAGILE_THRESHOLD,
    DEFAULT_MEMORY_DEPTH,
    MAX_MEMORY_DEPTH,
    # Dataclass
    IdentityResonanceMemoryState,
    # Helpers
    create_state,
    stability_band_from_scores,
    create_empty_state,
    create_initial_state,
)

from symbolu.core.predictive.identity_memory.memory_formula import (
    # Helpers
    clamp,
    safe_get,
    # Core formulas
    compute_identity_resonance_index,
    compute_variance,
    compute_persistence_score,
    compute_volatility_index,
    compute_stability_band,
    compute_all_metrics,
)

from symbolu.core.predictive.identity_memory.memory_store import (
    compute_identity_resonance_memory,
    extract_resonance_history,
    get_latest_resonance_value,
    get_stability_trend,
    append_to_history,
    compute_with_coherence_state,
)


__all__ = [
    # Version
    "P36_VERSION",
    # Enums
    "IdentityStabilityBand",
    # Constants
    "W_UCF_SCORE",
    "W_IDENTITY_HARMONICS",
    "W_SCHEMA_STABILITY",
    "W_INVERSE_DRIFT",
    "PERSISTENCE_STABLE_THRESHOLD",
    "PERSISTENCE_FRAGILE_THRESHOLD",
    "VOLATILITY_STABLE_THRESHOLD",
    "VOLATILITY_FRAGILE_THRESHOLD",
    "DEFAULT_MEMORY_DEPTH",
    "MAX_MEMORY_DEPTH",
    # Dataclass
    "IdentityResonanceMemoryState",
    # State helpers
    "create_state",
    "stability_band_from_scores",
    "create_empty_state",
    "create_initial_state",
    # Formula helpers
    "clamp",
    "safe_get",
    # Core formulas
    "compute_identity_resonance_index",
    "compute_variance",
    "compute_persistence_score",
    "compute_volatility_index",
    "compute_stability_band",
    "compute_all_metrics",
    # Store functions
    "compute_identity_resonance_memory",
    "extract_resonance_history",
    "get_latest_resonance_value",
    "get_stability_trend",
    "append_to_history",
    "compute_with_coherence_state",
]
