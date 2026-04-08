"""
Phase-4A: Ontology Lookup (Sub-module of Phase-4)
=================================================

Phase-4A is the ontology lookup component within the composite Phase-4 of the
Phase-1b → Phase-14 experimental pipeline.

Phase-4 Composite Structure:
    - Phase-4A: Ontology Lookup (frozen varna × layer interaction resolution) [THIS MODULE]
    - Phase-4B: Transform Engine (Phase-4.0, non-textual transformation)
    - Phase-4C: PO4 Planner Governance (proposal validation)

Phase-4A Responsibilities:
    - Load and trust the three frozen ontology files
    - Perform deterministic (varna, layer) → interaction lookup
    - Fail fast if data is missing (never infer)

Hard Invariants:
    - READ-ONLY: Never modifies frozen ontology files
    - DETERMINISTIC: Same (varna, layer) input => identical output
    - FAIL-FAST: Missing data triggers immediate error, never infers
    - NO INFERENCE: No gap-filling, no polarity invention, no smoothing

Frozen Ontology Files:
    - varna_bridge_map_v1.json
    - ontological_layers_v1.json
    - varna_layer_interaction_v1.json

Usage:
    from agentic.ontology.phase4a import lookup_interaction, validate_ontology

    # Validate on startup
    validate_ontology()  # Raises Phase4AValidationError if inconsistent

    # Lookup (varna, layer) -> interaction
    result = lookup_interaction("ka", "O3_EXECUTION")
    # Returns: VarnaLayerInteraction with manifestation_positive, manifestation_negative,
    #          distortion_vector, sublimate_vector
"""

from agentic.ontology.phase4a.errors import (
    Phase4AError,
    Phase4AValidationError,
    Phase4AVarnaMissingError,
    Phase4ALayerMissingError,
    Phase4AInteractionMissingError,
    Phase4AFieldMissingError,
)

from agentic.ontology.phase4a.models import (
    VarnaLayerInteraction,
    OntologyValidationReport,
)

from agentic.ontology.phase4a.loader import (
    load_ontology_files,
    validate_ontology,
    get_all_varnas,
    get_all_layers,
)

from agentic.ontology.phase4a.lookup import (
    lookup_interaction,
    lookup_interaction_raw,
)

__all__ = [
    # Errors
    "Phase4AError",
    "Phase4AValidationError",
    "Phase4AVarnaMissingError",
    "Phase4ALayerMissingError",
    "Phase4AInteractionMissingError",
    "Phase4AFieldMissingError",
    # Models
    "VarnaLayerInteraction",
    "OntologyValidationReport",
    # Loader
    "load_ontology_files",
    "validate_ontology",
    "get_all_varnas",
    "get_all_layers",
    # Lookup
    "lookup_interaction",
    "lookup_interaction_raw",
]
