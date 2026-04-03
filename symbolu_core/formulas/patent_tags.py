"""
Patent Formula Tags - Phase 6 Metadata Layer
=============================================

This module provides metadata tags for all patent formulas (implemented and patent-only).
Tags enable tracking of formula implementation status, lineage, and integration phases.

This is a metadata-only layer with ZERO behavioral impact.
No logic should depend on these tags.

Version: 1.0 (Phase 6)
Date: 2025-12-10
"""

# Patent Formula Tags
# -------------------
# Tag format: "phase{N}_{category}" for implemented formulas, "patent_only" for unimplemented

PATENT_FORMULA_TAGS = {
    # Phase 1: Temporal Resonance Formulas
    "smi": "phase1_temporal",
    "delta_smi": "phase1_temporal",

    # Phase 1: Temporal Geometry Formulas
    "bhava_gap": "phase1_temporal",
    "tension_corridor": "phase1_temporal",

    # Phase 3: Derived Metrics
    "resonance_index": "phase3_derived",
    "tension_index": "phase3_derived",
    "arc_alignment_index": "phase3_derived",

    # Patent-only formulas (not yet implemented)
    "guna_kosha_vrtti": "patent_only",
    "hope_greed_harmonic": "patent_only",
    "cognitive_arc_equation": "patent_only",
}


def get_formula_tag(name: str) -> str:
    """
    Get the tag for a formula by name.

    Args:
        name: Formula name (e.g., "smi", "resonance_index", "cognitive_arc_equation")

    Returns:
        Tag string (e.g., "phase1_temporal", "phase3_derived", "patent_only")
        Returns "unknown" if formula name not found in PATENT_FORMULA_TAGS

    Examples:
        >>> get_formula_tag("smi")
        'phase1_temporal'

        >>> get_formula_tag("resonance_index")
        'phase3_derived'

        >>> get_formula_tag("cognitive_arc_equation")
        'patent_only'

        >>> get_formula_tag("nonexistent_formula")
        'unknown'
    """
    return PATENT_FORMULA_TAGS.get(name, "unknown")
