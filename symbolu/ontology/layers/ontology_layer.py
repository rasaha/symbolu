"""
Ontological Layer Enumeration
=============================

Defines the 10 ontological layers from the non-provisional patent.
These layers represent structural projection planes, not semantic categories.

Hard Constraints:
    - Exactly 10 layers in fixed order
    - No semantic interpretation
    - No inference of meaning
    - Structural role only

Layer Ordering:
    1. ACTING      - Structural plane for action artifacts
    2. TAGGING     - Structural plane for tag/label artifacts
    3. FORMING     - Structural plane for form/shape artifacts
    4. THINKING    - Structural plane for thought-structure artifacts
    5. DIRECTING   - Structural plane for direction/flow artifacts
    6. REASONING   - Structural plane for reason-chain artifacts
    7. PURPOSING   - Structural plane for purpose-structure artifacts
    8. META_OBSERVING - Structural plane for meta-observation artifacts
    9. UNIFYING    - Structural plane for unification artifacts
    10. ABSOLVING  - Structural plane for absolution artifacts (gated)
"""

from enum import Enum


class OntologicalLayer(Enum):
    """
    10 ontological layers for structural projection.

    Each layer represents a projection plane onto which Phase artifacts
    can be mapped. Layers are structural containers, not semantic categories.

    The ordering is fixed and immutable per the patent specification.
    """

    # Layer 1: Structural plane for action artifacts
    ACTING = 1

    # Layer 2: Structural plane for tag/label artifacts
    TAGGING = 2

    # Layer 3: Structural plane for form/shape artifacts
    FORMING = 3

    # Layer 4: Structural plane for thought-structure artifacts
    THINKING = 4

    # Layer 5: Structural plane for direction/flow artifacts
    DIRECTING = 5

    # Layer 6: Structural plane for reason-chain artifacts
    REASONING = 6

    # Layer 7: Structural plane for purpose-structure artifacts
    PURPOSING = 7

    # Layer 8: Structural plane for meta-observation artifacts
    META_OBSERVING = 8

    # Layer 9: Structural plane for unification artifacts
    UNIFYING = 9

    # Layer 10: Structural plane for absolution artifacts (gated access)
    ABSOLVING = 10

    def __repr__(self) -> str:
        return f"OntologicalLayer.{self.name}"


# Immutable tuple of all layers in canonical order
ALL_LAYERS = tuple(OntologicalLayer)

# Gated layers that require explicit opt-in
GATED_LAYERS = frozenset({OntologicalLayer.ABSOLVING})
