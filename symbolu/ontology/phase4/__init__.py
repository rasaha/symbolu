"""
Phase-4: Ontology Execution Layer
=================================

Deterministic lookup engine for varna × layer interactions.

Hard Invariants:
    - READ-ONLY: Never modifies frozen ontology files
    - DETERMINISTIC: Same (varna, layer) input => identical output
    - FAIL-FAST: Missing data triggers immediate error, never infers
    - NO INFERENCE: No gap-filling, no polarity invention, no smoothing

This is the first execution checkpoint of ontology correctness.

Usage:
    from symbolu.ontology.phase4 import lookup_interaction, validate_ontology

    # Validate on startup
    validate_ontology()  # Raises Phase4ValidationError if inconsistent

    # Lookup (varna, layer) -> interaction
    result = lookup_interaction("ka", "O1_ACTING")
    # Returns: VarnaLayerInteraction with manifestation_positive, manifestation_negative,
    #          distortion_vector, sublimate_vector
"""

from symbolu.ontology.phase4.errors import (
    Phase4Error,
    Phase4ValidationError,
    Phase4VarnaMissingError,
    Phase4LayerMissingError,
    Phase4InteractionMissingError,
    Phase4FieldMissingError,
)

from symbolu.ontology.phase4.models import (
    VarnaLayerInteraction,
    OntologyValidationReport,
)

from symbolu.ontology.phase4.loader import (
    load_ontology_files,
    validate_ontology,
    get_all_varnas,
    get_all_layers,
)

from symbolu.ontology.phase4.lookup import (
    lookup_interaction,
    lookup_interaction_raw,
)

__all__ = [
    # Errors
    "Phase4Error",
    "Phase4ValidationError",
    "Phase4VarnaMissingError",
    "Phase4LayerMissingError",
    "Phase4InteractionMissingError",
    "Phase4FieldMissingError",
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
