"""
Ontological Layer Enumeration — CANONICAL SOURCE
=================================================

THIS IS THE SINGLE SOURCE OF TRUTH for OntologicalLayer within
the symbolu package. The agentic.ontology.layers.ontology_layer module
is the primary architecture-level canonical source; this symbolu mirror
provides the same definition for symbolu-path consumers and tests.

Canonical import paths:
    from symbolu.ontology.layers.ontology_layer import OntologicalLayer
    from symbolu.ontology.layers import OntologicalLayer

Defines the 12 ontological layers from the patent-exact sequence.
These layers represent structural projection planes, not semantic categories.

Hard Constraints:
    - Exactly 12 layers in fixed order
    - No semantic interpretation
    - No inference of meaning
    - Structural role only

Layer Ordering (12D patent-exact sequence):
    1. POTENTIAL     - Structural plane for dormant capacity artifacts
    2. IDENTITY      - Structural plane for classification/tag artifacts
    3. EXECUTION     - Structural plane for action/karma artifacts
    4. STRUCTURE     - Structural plane for form/shape artifacts
    5. COGNITION     - Structural plane for perception/attention artifacts
    6. AGENCY        - Structural plane for direction/control artifacts
    7. REASONING     - Structural plane for reason-chain artifacts
    8. PURPOSE       - Structural plane for purpose-structure artifacts
    9. WITNESSES     - Structural plane for meta-observation artifacts
    10. UNIFYING     - Structural plane for unification artifacts
    11. INTEGRATION  - Structural plane for resolution/consolidation artifacts
    12. ABSOLVING    - Structural plane for absolution artifacts (gated)
"""

from enum import Enum


class OntologicalLayer(Enum):
    """
    12 ontological layers for structural projection (patent-exact sequence).

    Each layer represents a projection plane onto which Phase artifacts
    can be mapped. Layers are structural containers, not semantic categories.

    The ordering is fixed and immutable per the patent specification.
    """

    # Layer 1: Structural plane for dormant capacity artifacts
    POTENTIAL = 1

    # Layer 2: Structural plane for classification/tag artifacts
    IDENTITY = 2

    # Layer 3: Structural plane for action/karma artifacts
    EXECUTION = 3

    # Layer 4: Structural plane for form/shape artifacts
    STRUCTURE = 4

    # Layer 5: Structural plane for perception/attention artifacts
    COGNITION = 5

    # Layer 6: Structural plane for direction/control artifacts
    AGENCY = 6

    # Layer 7: Structural plane for reason-chain artifacts
    REASONING = 7

    # Layer 8: Structural plane for purpose-structure artifacts
    PURPOSE = 8

    # Layer 9: Structural plane for meta-observation artifacts
    WITNESSES = 9

    # Layer 10: Structural plane for unification artifacts
    UNIFYING = 10

    # Layer 11: Structural plane for resolution/consolidation artifacts
    INTEGRATION = 11

    # Layer 12: Structural plane for absolution artifacts (gated access)
    ABSOLVING = 12

    def __repr__(self) -> str:
        return f"OntologicalLayer.{self.name}"


# Immutable tuple of all layers in canonical order
ALL_LAYERS = tuple(OntologicalLayer)

# Gated layers that require explicit opt-in
GATED_LAYERS = frozenset({OntologicalLayer.ABSOLVING})
