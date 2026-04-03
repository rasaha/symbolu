"""
Phase to Ontological Layer Mapping
==================================

Deterministic, declarative mapping from Phase IDs to ontological layers (12D).

Hard Constraints:
    - Mapping is immutable
    - One-to-many relationship (Phase -> multiple layers)
    - No inference logic
    - No probabilistic selection
    - Purely declarative

Mapping Table (12D layer names):
    Phase 1b -> IDENTITY, STRUCTURE
    Phase 2  -> IDENTITY, STRUCTURE
    Phase 3  -> COGNITION, REASONING, AGENCY
    Phase 4  -> EXECUTION, COGNITION
    Phase 5  -> STRUCTURE, UNIFYING
    Phase 6  -> AGENCY, WITNESSES, PURPOSE
    Phase 7  -> EXECUTION, AGENCY, COGNITION
    Phase 8  -> WITNESSES, AGENCY
    Phase 9  -> UNIFYING, REASONING, ABSOLVING (ABSOLVING is gated)
"""

from typing import FrozenSet, Mapping, Tuple

from agentic.ontology.layers.ontology_layer import (
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
        OntologicalLayer.IDENTITY,
        OntologicalLayer.STRUCTURE,
    }),
    "2": frozenset({
        OntologicalLayer.IDENTITY,
        OntologicalLayer.STRUCTURE,
    }),
    "3": frozenset({
        OntologicalLayer.COGNITION,
        OntologicalLayer.REASONING,
        OntologicalLayer.AGENCY,
    }),
    "4": frozenset({
        OntologicalLayer.EXECUTION,
        OntologicalLayer.COGNITION,
    }),
    "5": frozenset({
        OntologicalLayer.STRUCTURE,
        OntologicalLayer.UNIFYING,
    }),
    "6": frozenset({
        OntologicalLayer.AGENCY,
        OntologicalLayer.WITNESSES,
        OntologicalLayer.PURPOSE,
    }),
    "7": frozenset({
        OntologicalLayer.EXECUTION,
        OntologicalLayer.AGENCY,
        OntologicalLayer.COGNITION,
    }),
    "8": frozenset({
        OntologicalLayer.WITNESSES,
        OntologicalLayer.AGENCY,
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
