"""
Phase4a Varna-Layer Lookup Adapter (O3)
========================================

Bridges the ontological phase4a varna-layer interaction lookup into the
framework signal path as a governance-safe adapter.

This adapter exposes:

1. ``resolve_varna_lookup`` — Look up the structural interaction between
   a varna archetype and an ontological layer (deterministic, cached).

2. ``resolve_varna_exists`` — Check whether a (varna, layer) pair exists
   in the canonical substrate (fast, boolean).

Both follow the established signal adapter pattern:
    - Frozen Resolution dataclass (immutable, serializable)
    - Pure resolve function (fail-closed)
    - ``available`` / ``source_detail`` provenance fields

Canonical source consumed:
    agentic.ontology.phase4a.lookup — lookup_interaction, has_interaction

Design constraints:
    - No mutation of inputs
    - Deterministic: same input => identical output
    - Serializable outputs (to_dict on resolution type)
    - Fail-closed: errors produce available=False resolutions, never raise
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


# =========================================================================
# Resolution Contract
# =========================================================================

@dataclass(frozen=True)
class VarnaLookupResolution:
    """
    Governance-safe view of a varna-layer interaction lookup.

    Attributes:
        available: Whether the lookup succeeded.
        varna: The varna archetype queried.
        layer: The ontological layer queried.
        exists: Whether the (varna, layer) pair exists in the substrate.
        manifestation_positive: Positive manifestation text.
        manifestation_negative: Negative manifestation text.
        distortion_vector: Distortion vector description.
        sublimate_vector: Sublimation vector description.
        source_detail: Provenance string.
    """
    available: bool
    varna: str = ""
    layer: str = ""
    exists: bool = False
    manifestation_positive: str = ""
    manifestation_negative: str = ""
    distortion_vector: str = ""
    sublimate_vector: str = ""
    source_detail: str = "phase4a_varna_layer_lookup"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "varna": self.varna,
            "layer": self.layer,
            "exists": self.exists,
            "manifestation_positive": self.manifestation_positive,
            "manifestation_negative": self.manifestation_negative,
            "distortion_vector": self.distortion_vector,
            "sublimate_vector": self.sublimate_vector,
            "source_detail": self.source_detail,
        }


# =========================================================================
# Unavailable Sentinel
# =========================================================================

_LOOKUP_UNAVAILABLE = VarnaLookupResolution(
    available=False,
    source_detail="phase4a_varna_layer_lookup:unavailable",
)


# =========================================================================
# Resolve Functions
# =========================================================================

def resolve_varna_lookup(
    varna: str,
    layer: str,
) -> VarnaLookupResolution:
    """
    Look up the structural interaction between a varna and layer.

    Uses the canonical ``agentic.ontology.phase4a.lookup.lookup_interaction``
    to retrieve the frozen interaction record from the deterministic
    JSON substrate.

    This is fail-closed: any error returns an unavailable resolution
    rather than raising.

    Args:
        varna: Varna archetype name (e.g., "Brahmana", "Kshatriya").
        layer: Ontological layer name (e.g., "POTENTIAL", "IDENTITY").

    Returns:
        VarnaLookupResolution with interaction details.
        available=False if the lookup fails or inputs are invalid.

    Example:
        >>> res = resolve_varna_lookup("Kshatriya", "IDENTITY")
        >>> res.available
        True
        >>> res.manifestation_positive
        'Warrior identity...'
    """
    try:
        from agentic.ontology.phase4a.lookup import (
            has_interaction,
            lookup_interaction,
        )

        exists = has_interaction(varna, layer)

        if not exists:
            return VarnaLookupResolution(
                available=True,
                varna=str(varna),
                layer=str(layer),
                exists=False,
            )

        interaction = lookup_interaction(varna, layer)

        return VarnaLookupResolution(
            available=True,
            varna=interaction.varna,
            layer=interaction.layer,
            exists=True,
            manifestation_positive=interaction.manifestation_positive,
            manifestation_negative=interaction.manifestation_negative,
            distortion_vector=interaction.distortion_vector,
            sublimate_vector=interaction.sublimate_vector,
        )

    except Exception:
        return _LOOKUP_UNAVAILABLE


def resolve_varna_exists(varna: str, layer: str) -> bool:
    """
    Check whether a (varna, layer) pair exists in the substrate.

    Convenience wrapper that returns a plain boolean. Fail-closed:
    returns False on any error.

    Args:
        varna: Varna archetype name.
        layer: Ontological layer name.

    Returns:
        True if the pair exists, False otherwise (including on error).
    """
    try:
        from agentic.ontology.phase4a.lookup import has_interaction
        return has_interaction(varna, layer)
    except Exception:
        return False
