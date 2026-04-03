"""
P36 - Identity Resonance Memory Pipeline Integration

This module integrates Phase 36 (Identity Resonance Memory) into the pipeline.
It provides functions to update CoherenceState with P36 memory state.

P36 is an observation-only memory phase that:
- Remembers stability and drift patterns
- Smooths short-term noise
- Preserves historical identity context

P36 does NOT:
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
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agentic.core.predictive.identity_memory import (
    IdentityResonanceMemoryState,
    compute_identity_resonance_memory,
    DEFAULT_MEMORY_DEPTH,
)


def update_identity_resonance_memory(
    coherence_state: Any,
    memory_depth: int = DEFAULT_MEMORY_DEPTH,
) -> Any:
    """
    Update CoherenceState with Phase 36 Identity Resonance Memory.

    This function:
    1. Extracts required inputs from coherence_state (P26, P33, P34, P35)
    2. Computes the identity resonance memory state
    3. Updates coherence_state with the new memory snapshot
    4. Appends to history (append-only)

    INVARIANTS:
        - INV-P36-1: Memory never alters present cognition
        - INV-P36-2: Memory is append-only
        - INV-P36-3: No authority escalation
        - INV-P36-4: Deterministic math only
        - INV-P36-5: Acoustic signals forbidden

    Args:
        coherence_state: CoherenceState object with P26/P33/P34/P35 data
        memory_depth: Maximum number of snapshots for computation

    Returns:
        Updated CoherenceState (same object, mutated in-place for compatibility)
    """
    # Extract inputs from coherence state (with safe defaults)

    # P26 UCF Score
    ucf_score = getattr(coherence_state, 'current_coi', None)
    if ucf_score is None:
        # Try alternative UCF field from snapshot
        ucf_snapshot = getattr(coherence_state, 'unified_consciousness_snapshot', None)
        if ucf_snapshot is not None:
            ucf_score = getattr(ucf_snapshot, 'ucf_score', None)

    # P34 Identity Harmonics Score
    identity_harmonics_score = getattr(coherence_state, 'current_identity_harmonics_index', None)
    if identity_harmonics_score is None:
        # Try CIH as fallback
        identity_harmonics_score = getattr(coherence_state, 'current_cih', None)

    # P33 Schema Stability
    schema_stability = getattr(coherence_state, 'persona_schema_stability', None)

    # P35 Predicted Drift Score
    predicted_drift_score = getattr(coherence_state, 'current_drift_magnitude_prediction', None)
    drift_risk_band = getattr(coherence_state, 'current_drift_likelihood_band', None)

    # Get prior memory states from history
    prior_states: Optional[List[IdentityResonanceMemoryState]] = getattr(
        coherence_state, 'identity_resonance_memory_history', None
    )

    # Compute identity resonance memory state
    memory_state = compute_identity_resonance_memory(
        ucf_score=ucf_score,
        identity_harmonics_score=identity_harmonics_score,
        schema_stability=schema_stability,
        predicted_drift_score=predicted_drift_score,
        drift_risk_band=drift_risk_band,
        prior_states=prior_states,
        memory_depth=memory_depth,
    )

    # Update coherence state with new memory snapshot
    coherence_state.identity_resonance_memory_snapshot = memory_state

    # Update current metric shortcuts
    coherence_state.current_ims = memory_state.identity_resonance_index
    coherence_state.current_iep = memory_state.persistence_score
    coherence_state.current_ida = 1.0 - memory_state.volatility_index  # Anchoring is inverse of volatility
    coherence_state.current_irm_memory_band = memory_state.identity_stability_band

    # Build diagnostic tags
    tags: List[str] = []
    if memory_state.is_stable():
        tags.append("IDENTITY_MEMORY_STABLE")
    elif memory_state.is_fragile():
        tags.append("IDENTITY_MEMORY_FRAGILE")
    else:
        tags.append("IDENTITY_MEMORY_SOFT")

    if memory_state.persistence_score >= 0.85:
        tags.append("HIGH_PERSISTENCE")
    elif memory_state.persistence_score < 0.50:
        tags.append("LOW_PERSISTENCE")

    if memory_state.volatility_index >= 0.35:
        tags.append("HIGH_VOLATILITY")
    elif memory_state.volatility_index < 0.10:
        tags.append("LOW_VOLATILITY")

    coherence_state.current_irm_tags = sorted(tags)

    # Append to history (append-only - INV-P36-2)
    if coherence_state.identity_resonance_memory_history is None:
        coherence_state.identity_resonance_memory_history = []
    coherence_state.identity_resonance_memory_history.append(memory_state)

    # Update metric histories (append-only)
    if coherence_state.ims_history is None:
        coherence_state.ims_history = []
    coherence_state.ims_history.append(memory_state.identity_resonance_index)

    if coherence_state.iep_history is None:
        coherence_state.iep_history = []
    coherence_state.iep_history.append(memory_state.persistence_score)

    if coherence_state.ida_history is None:
        coherence_state.ida_history = []
    coherence_state.ida_history.append(1.0 - memory_state.volatility_index)

    if coherence_state.irm_memory_band_history is None:
        coherence_state.irm_memory_band_history = []
    coherence_state.irm_memory_band_history.append(memory_state.identity_stability_band)

    return coherence_state


def extract_p36_from_coherence_state(
    coherence_state: Any,
) -> Optional[Dict[str, Any]]:
    """
    Extract Phase 36 data from CoherenceState for API/observability.

    This function provides a read-only view of P36 data from coherence state.
    It does NOT modify any state.

    Args:
        coherence_state: CoherenceState object

    Returns:
        Dictionary with P36 data, or None if no P36 data available
    """
    snapshot = getattr(coherence_state, 'identity_resonance_memory_snapshot', None)

    if snapshot is None:
        return None

    return {
        "identity_resonance_index": getattr(snapshot, 'identity_resonance_index', None),
        "identity_stability_band": getattr(snapshot, 'identity_stability_band', None),
        "persistence_score": getattr(snapshot, 'persistence_score', None),
        "volatility_index": getattr(snapshot, 'volatility_index', None),
        "memory_depth": getattr(snapshot, 'memory_depth', None),
        "memory_timestamp": (
            snapshot.memory_timestamp.isoformat()
            if hasattr(snapshot, 'memory_timestamp') and snapshot.memory_timestamp
            else None
        ),
        "shortcuts": {
            "ims": getattr(coherence_state, 'current_ims', None),
            "iep": getattr(coherence_state, 'current_iep', None),
            "ida": getattr(coherence_state, 'current_ida', None),
            "memory_band": getattr(coherence_state, 'current_irm_memory_band', None),
        },
        "tags": getattr(coherence_state, 'current_irm_tags', []),
        "inputs": {
            "ucf_score": getattr(snapshot, 'ucf_score', None),
            "identity_harmonics_score": getattr(snapshot, 'identity_harmonics_score', None),
            "schema_stability": getattr(snapshot, 'schema_stability', None),
            "predicted_drift_score": getattr(snapshot, 'predicted_drift_score', None),
            "drift_risk_band": getattr(snapshot, 'drift_risk_band', None),
        },
        "observer_only": True,
        "architectural_phase": "P36",
    }


def compute_p36_standalone(
    ucf_score: Optional[float] = None,
    identity_harmonics_score: Optional[float] = None,
    schema_stability: Optional[float] = None,
    predicted_drift_score: Optional[float] = None,
    drift_risk_band: Optional[str] = None,
    prior_states: Optional[List[IdentityResonanceMemoryState]] = None,
    memory_depth: int = DEFAULT_MEMORY_DEPTH,
) -> IdentityResonanceMemoryState:
    """
    Compute P36 Identity Resonance Memory state without CoherenceState.

    This is a convenience function for standalone computation or testing.

    Args:
        ucf_score: P26 UCF score [0.0, 1.0]
        identity_harmonics_score: P34 identity harmonics score [0.0, 1.0]
        schema_stability: P33 schema stability [0.0, 1.0]
        predicted_drift_score: P35 predicted drift score [0.0, 1.0]
        drift_risk_band: P35 drift risk band
        prior_states: List of prior IdentityResonanceMemoryState snapshots
        memory_depth: Maximum number of snapshots for computation

    Returns:
        IdentityResonanceMemoryState - immutable snapshot
    """
    return compute_identity_resonance_memory(
        ucf_score=ucf_score,
        identity_harmonics_score=identity_harmonics_score,
        schema_stability=schema_stability,
        predicted_drift_score=predicted_drift_score,
        drift_risk_band=drift_risk_band,
        prior_states=prior_states,
        memory_depth=memory_depth,
    )


# Public exports
__all__ = [
    "update_identity_resonance_memory",
    "extract_p36_from_coherence_state",
    "compute_p36_standalone",
]
