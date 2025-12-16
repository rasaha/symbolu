"""
Phase to Ontological Layer Mapping
==================================

Deterministic, declarative mapping from Phase IDs to ontological layers.

Hard Constraints:
    - Mapping is immutable
    - One-to-many relationship (Phase -> multiple layers)
    - No inference logic
    - No probabilistic selection
    - Purely declarative

Mapping Table:
    Phase 1b -> TAGGING, FORMING
    Phase 2  -> TAGGING, FORMING
    Phase 3  -> THINKING, REASONING, DIRECTING
    Phase 4  -> ACTING, THINKING
    Phase 5  -> FORMING, UNIFYING
    Phase 6  -> DIRECTING, META_OBSERVING, PURPOSING
    Phase 7  -> ACTING, DIRECTING, THINKING
    Phase 8  -> META_OBSERVING, DIRECTING
    Phase 9  -> UNIFYING, REASONING, ABSOLVING (ABSOLVING is gated)
"""

from typing import FrozenSet, Mapping, Tuple

from symbolu.ontology.layers.ontology_layer import (
    GATED_LAYERS,
    OntologicalLayer,
)


# =============================================================================
# Phase to Layer Mapping (IMMUTABLE)
# =============================================================================

# Type alias for clarity
LayerSet = FrozenSet[OntologicalLayer]

# The canonical phase-to-layer mapping
# Keys are phase IDs as strings, values are frozensets of layers
_PHASE_TO_LAYERS_RAW: Mapping[str, LayerSet] = {
    "1b": frozenset({
        OntologicalLayer.TAGGING,
        OntologicalLayer.FORMING,
    }),
    "2": frozenset({
        OntologicalLayer.TAGGING,
        OntologicalLayer.FORMING,
    }),
    "3": frozenset({
        OntologicalLayer.THINKING,
        OntologicalLayer.REASONING,
        OntologicalLayer.DIRECTING,
    }),
    "4": frozenset({
        OntologicalLayer.ACTING,
        OntologicalLayer.THINKING,
    }),
    "5": frozenset({
        OntologicalLayer.FORMING,
        OntologicalLayer.UNIFYING,
    }),
    "6": frozenset({
        OntologicalLayer.DIRECTING,
        OntologicalLayer.META_OBSERVING,
        OntologicalLayer.PURPOSING,
    }),
    "7": frozenset({
        OntologicalLayer.ACTING,
        OntologicalLayer.DIRECTING,
        OntologicalLayer.THINKING,
    }),
    "8": frozenset({
        OntologicalLayer.META_OBSERVING,
        OntologicalLayer.DIRECTING,
    }),
    "9": frozenset({
        OntologicalLayer.UNIFYING,
        OntologicalLayer.REASONING,
        OntologicalLayer.ABSOLVING,  # Gated - requires explicit opt-in
    }),
}

# Immutable public mapping
PHASE_TO_LAYERS: Mapping[str, LayerSet] = dict(_PHASE_TO_LAYERS_RAW)

# All valid phase IDs
VALID_PHASE_IDS: FrozenSet[str] = frozenset(PHASE_TO_LAYERS.keys())


# =============================================================================
# Lookup Functions (Deterministic)
# =============================================================================

def get_layers_for_phase(
    phase_id: str,
    *,
    include_gated: bool = False,
) -> Tuple[OntologicalLayer, ...]:
    """
    Get the ontological layers mapped to a phase.

    Args:
        phase_id: The phase identifier (e.g., "1b", "2", "9")
        include_gated: If False, gated layers (ABSOLVING) are excluded.
                       Default is False (fail-closed).

    Returns:
        Tuple of OntologicalLayer values in canonical order.

    Raises:
        KeyError: If phase_id is not in the mapping.

    Note:
        Ordering is deterministic (sorted by layer.value).
    """
    if phase_id not in PHASE_TO_LAYERS:
        raise KeyError(f"Unknown phase_id: {phase_id!r}")

    layers = PHASE_TO_LAYERS[phase_id]

    if not include_gated:
        layers = layers - GATED_LAYERS

    # Return in canonical order (sorted by enum value)
    return tuple(sorted(layers, key=lambda l: l.value))


def is_valid_phase_id(phase_id: str) -> bool:
    """
    Check if a phase ID is valid.

    Args:
        phase_id: The phase identifier to check.

    Returns:
        True if phase_id is in the mapping, False otherwise.
    """
    return phase_id in VALID_PHASE_IDS


def get_phases_for_layer(layer: OntologicalLayer) -> Tuple[str, ...]:
    """
    Get all phases that map to a given layer.

    Args:
        layer: The ontological layer to query.

    Returns:
        Tuple of phase IDs in sorted order.

    Note:
        This is an inverse lookup. Ordering is deterministic.
    """
    phases = []
    for phase_id, layers in PHASE_TO_LAYERS.items():
        if layer in layers:
            phases.append(phase_id)
    return tuple(sorted(phases))
