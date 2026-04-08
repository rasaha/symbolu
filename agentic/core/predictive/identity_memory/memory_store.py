"""
P36 - Identity Resonance Memory Store

Append-only storage and orchestration for identity resonance memory.
This module manages the accumulation of memory states over time.

MEMORY RULES:
    - Append new IdentityResonanceMemoryState per run
    - Never delete prior states
    - Never overwrite history
    - No decay unless explicitly formula-driven
    - No interpretation or inference

CRITICAL CONSTRAINTS:
    - Append-only: INV-P36-2
    - Deterministic: INV-P36-4
    - Read-only memory: INV-P36-1

INVARIANTS:
    - INV-P36-1: Memory never alters present cognition
    - INV-P36-2: Memory is append-only
    - INV-P36-3: No authority escalation
    - INV-P36-4: Deterministic math only
    - INV-P36-5: Acoustic signals forbidden
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from agentic.core.predictive.identity_memory.memory_state import (
    IdentityResonanceMemoryState,
    create_state,
    create_empty_state,
    stability_band_from_scores,
    DEFAULT_MEMORY_DEPTH,
    MAX_MEMORY_DEPTH,
)
from agentic.core.predictive.identity_memory.memory_formula import (
    compute_identity_resonance_index,
    compute_persistence_score,
    compute_volatility_index,
    compute_stability_band,
    compute_all_metrics,
)


def compute_identity_resonance_memory(
    ucf_score: Optional[float] = None,
    identity_harmonics_score: Optional[float] = None,
    schema_stability: Optional[float] = None,
    predicted_drift_score: Optional[float] = None,
    drift_risk_band: Optional[str] = None,
    prior_states: Optional[List[IdentityResonanceMemoryState]] = None,
    memory_depth: int = DEFAULT_MEMORY_DEPTH,
) -> IdentityResonanceMemoryState:
    """
    Compute identity resonance memory state from inputs and history.

    This is the main entry point for Phase 36 computation. It:
    1. Computes the current identity resonance index from inputs
    2. Extracts historical resonance values from prior states
    3. Computes persistence and volatility from history
    4. Determines the stability band
    5. Returns an immutable, append-only state

    MEMORY RULES:
        - If history < 2 snapshots: volatility = 0.0, persistence = 1.0
        - Never modifies prior states
        - Caps history at memory_depth (default 5, max 7)

    Args:
        ucf_score: P26 UCF score [0.0, 1.0]
        identity_harmonics_score: P34 identity harmonics score [0.0, 1.0]
        schema_stability: P33 schema stability [0.0, 1.0]
        predicted_drift_score: P35 predicted drift score [0.0, 1.0]
        drift_risk_band: P35 drift risk band
        prior_states: List of prior IdentityResonanceMemoryState snapshots
        memory_depth: Maximum number of snapshots for computation (default 5, max 7)

    Returns:
        IdentityResonanceMemoryState - immutable snapshot of memory state
    """
    # Cap memory depth
    memory_depth = min(memory_depth, MAX_MEMORY_DEPTH)

    # Extract historical resonance values from prior states
    historical_values: List[float] = []
    if prior_states:
        for state in prior_states:
            if state is not None and hasattr(state, 'identity_resonance_index'):
                historical_values.append(state.identity_resonance_index)

    # Compute all metrics
    (
        current_resonance,
        persistence,
        volatility,
        stability_band,
        updated_values,
    ) = compute_all_metrics(
        ucf_score=ucf_score,
        identity_harmonics_score=identity_harmonics_score,
        schema_stability=schema_stability,
        predicted_drift_score=predicted_drift_score,
        historical_resonance_values=historical_values,
        memory_depth=memory_depth,
    )

    # Build debug info
    debug: Dict[str, Any] = {
        "inputs_provided": {
            "ucf_score": ucf_score is not None,
            "identity_harmonics_score": identity_harmonics_score is not None,
            "schema_stability": schema_stability is not None,
            "predicted_drift_score": predicted_drift_score is not None,
        },
        "prior_states_count": len(prior_states) if prior_states else 0,
        "historical_values_used": len(historical_values),
        "memory_depth_config": memory_depth,
    }

    # Create and return immutable state
    return create_state(
        identity_resonance_index=current_resonance,
        identity_stability_band=stability_band,
        persistence_score=persistence,
        volatility_index=volatility,
        memory_depth=len(updated_values),
        memory_timestamp=datetime.utcnow(),
        ucf_score=ucf_score,
        identity_harmonics_score=identity_harmonics_score,
        schema_stability=schema_stability,
        predicted_drift_score=predicted_drift_score,
        drift_risk_band=drift_risk_band,
        historical_resonance_values=tuple(updated_values),
        debug=debug,
    )


def extract_resonance_history(
    prior_states: Optional[List[IdentityResonanceMemoryState]],
    max_depth: int = MAX_MEMORY_DEPTH,
) -> List[float]:
    """
    Extract historical resonance values from prior memory states.

    This function provides read-only access to historical resonance values
    for analysis purposes. It never modifies the prior states.

    Args:
        prior_states: List of prior IdentityResonanceMemoryState snapshots
        max_depth: Maximum number of values to return (most recent)

    Returns:
        List of historical identity_resonance_index values
    """
    if not prior_states:
        return []

    values: List[float] = []
    for state in prior_states:
        if state is not None and hasattr(state, 'identity_resonance_index'):
            values.append(state.identity_resonance_index)

    # Return most recent values up to max_depth
    if len(values) > max_depth:
        values = values[-max_depth:]

    return values


def get_latest_resonance_value(
    prior_states: Optional[List[IdentityResonanceMemoryState]],
) -> Optional[float]:
    """
    Get the most recent identity resonance value from prior states.

    Args:
        prior_states: List of prior IdentityResonanceMemoryState snapshots

    Returns:
        Most recent identity_resonance_index, or None if no history
    """
    if not prior_states:
        return None

    # Iterate in reverse to find most recent valid state
    for state in reversed(prior_states):
        if state is not None and hasattr(state, 'identity_resonance_index'):
            return state.identity_resonance_index

    return None


def get_stability_trend(
    prior_states: Optional[List[IdentityResonanceMemoryState]],
    min_states: int = 3,
) -> Optional[str]:
    """
    Analyze stability band trend from prior states.

    Returns:
        - "stabilizing" if recent bands show improvement toward stable
        - "destabilizing" if recent bands show decline toward fragile
        - "steady" if no clear trend
        - None if insufficient data

    Args:
        prior_states: List of prior IdentityResonanceMemoryState snapshots
        min_states: Minimum states required for trend analysis (default 3)

    Returns:
        Trend string or None if insufficient data
    """
    if not prior_states or len(prior_states) < min_states:
        return None

    # Get recent stability bands
    bands: List[str] = []
    for state in prior_states[-min_states:]:
        if state is not None and hasattr(state, 'identity_stability_band'):
            bands.append(state.identity_stability_band)

    if len(bands) < min_states:
        return None

    # Map bands to numeric values for trend analysis
    band_values = {"stable": 2, "soft": 1, "fragile": 0}
    numeric_bands = [band_values.get(b, 1) for b in bands]

    # Simple trend: compare first half vs second half
    mid = len(numeric_bands) // 2
    first_avg = sum(numeric_bands[:mid]) / max(mid, 1)
    second_avg = sum(numeric_bands[mid:]) / max(len(numeric_bands) - mid, 1)

    if second_avg > first_avg + 0.3:
        return "stabilizing"
    elif second_avg < first_avg - 0.3:
        return "destabilizing"
    else:
        return "steady"


def append_to_history(
    current_state: IdentityResonanceMemoryState,
    prior_history: Optional[List[IdentityResonanceMemoryState]],
    max_history: int = MAX_MEMORY_DEPTH,
) -> List[IdentityResonanceMemoryState]:
    """
    Append current state to history, maintaining max size.

    This is a pure function that creates a new list - it never
    modifies the prior_history list (append-only semantics).

    Args:
        current_state: Current IdentityResonanceMemoryState to append
        prior_history: Existing history list (not modified)
        max_history: Maximum history size (default MAX_MEMORY_DEPTH)

    Returns:
        New list with current_state appended, capped at max_history
    """
    # Create new list (never modify prior_history)
    if prior_history is None:
        new_history = []
    else:
        new_history = list(prior_history)  # Shallow copy

    # Append current state
    new_history.append(current_state)

    # Cap at max_history (keep most recent)
    if len(new_history) > max_history:
        new_history = new_history[-max_history:]

    return new_history


def compute_with_coherence_state(
    coherence_state: Any,
    memory_depth: int = DEFAULT_MEMORY_DEPTH,
) -> IdentityResonanceMemoryState:
    """
    Compute identity resonance memory from a CoherenceState object.

    This convenience function extracts the required inputs from
    CoherenceState and computes the memory state.

    Args:
        coherence_state: CoherenceState object with P26/P33/P34/P35 data
        memory_depth: Maximum number of snapshots for computation

    Returns:
        IdentityResonanceMemoryState - immutable snapshot
    """
    # Extract inputs from coherence state (with safe defaults)
    ucf_score = getattr(coherence_state, 'current_coi', None)
    if ucf_score is None:
        # Try alternative UCF field
        ucf_snapshot = getattr(coherence_state, 'unified_consciousness_snapshot', None)
        if ucf_snapshot is not None:
            ucf_score = getattr(ucf_snapshot, 'ucf_score', None)

    identity_harmonics_score = getattr(coherence_state, 'current_identity_harmonics_index', None)
    if identity_harmonics_score is None:
        identity_harmonics_score = getattr(coherence_state, 'current_cih', None)

    schema_stability = getattr(coherence_state, 'persona_schema_stability', None)

    predicted_drift_score = getattr(coherence_state, 'current_drift_magnitude_prediction', None)
    drift_risk_band = getattr(coherence_state, 'current_drift_likelihood_band', None)

    # Get prior memory states from history
    prior_states = getattr(coherence_state, 'identity_resonance_memory_history', None)

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
    "compute_identity_resonance_memory",
    "extract_resonance_history",
    "get_latest_resonance_value",
    "get_stability_trend",
    "append_to_history",
    "compute_with_coherence_state",
]
