"""
Phase-4A Ontology Lookup
========================

Phase-4A is the ontology lookup sub-module within the composite Phase-4
of the Phase-1b → Phase-14 experimental pipeline.

Deterministic lookup for (varna, layer) → interaction.

This module provides the core Phase-4A execution function:
    validate → lookup → return

Rules:
    - NO inference
    - NO gap-filling
    - NO polarity invention
    - NO smoothing language
    - If data is missing → throw, not infer
"""

from typing import Dict, Any, Optional

from agentic.ontology.phase4a.errors import (
    Phase4AVarnaMissingError,
    Phase4ALayerMissingError,
    Phase4AInteractionMissingError,
    Phase4AFieldMissingError,
)
from agentic.ontology.phase4a.models import VarnaLayerInteraction
from agentic.ontology.phase4a.loader import (
    load_ontology_files,
    get_all_varnas,
    get_all_layers,
    REQUIRED_INTERACTION_FIELDS,
)


# =============================================================================
# Raw Lookup (Dict Output)
# =============================================================================

def lookup_interaction_raw(
    varna: str,
    layer: str,
    *,
    force_reload: bool = False,
) -> Dict[str, str]:
    """
    Look up a (varna, layer) interaction, returning raw dict.

    This is the low-level lookup that returns a plain dict.
    Use lookup_interaction() for a typed dataclass output.

    Flow:
        1. Validate varna exists in bridge map → fail if not
        2. Validate layer exists in ontological layers → fail if not
        3. Lookup interaction → fail if missing
        4. Validate all required fields present → fail if missing
        5. Return raw interaction dict

    Args:
        varna: The varna token (e.g., "ka", "a", "sha")
        layer: The ontological layer (e.g., "O3_EXECUTION")
        force_reload: If True, reload ontology files

    Returns:
        Dict with keys:
            - manifestation_positive
            - manifestation_negative
            - distortion_vector
            - sublimate_vector

    Raises:
        Phase4AVarnaMissingError: If varna not in bridge map
        Phase4ALayerMissingError: If layer not in ontological layers
        Phase4AInteractionMissingError: If (varna, layer) pair has no entry
        Phase4AFieldMissingError: If any required field is missing
    """
    # Load ontology files
    ontology = load_ontology_files(force_reload=force_reload)

    # Get valid sets
    valid_varnas = get_all_varnas(force_reload=force_reload)
    valid_layers = get_all_layers(force_reload=force_reload)

    # Step 1: Validate varna exists
    if varna not in valid_varnas:
        raise Phase4AVarnaMissingError(varna)

    # Step 2: Validate layer exists
    if layer not in valid_layers:
        raise Phase4ALayerMissingError(layer, valid_layers=tuple(sorted(valid_layers)))

    # Step 3: Lookup interaction
    interaction_map = ontology["varna_layer_interaction"].get("interaction_map", {})

    if varna not in interaction_map:
        raise Phase4AInteractionMissingError(varna, layer)

    varna_interactions = interaction_map[varna]

    if not isinstance(varna_interactions, dict):
        raise Phase4AInteractionMissingError(varna, layer)

    if layer not in varna_interactions:
        raise Phase4AInteractionMissingError(varna, layer)

    interaction_data = varna_interactions[layer]

    if not isinstance(interaction_data, dict):
        raise Phase4AInteractionMissingError(varna, layer)

    # Step 4: Validate all required fields present
    for field in REQUIRED_INTERACTION_FIELDS:
        if field not in interaction_data:
            raise Phase4AFieldMissingError(varna, layer, field)

    # Step 5: Return only the required fields
    return {
        "manifestation_positive": interaction_data["manifestation_positive"],
        "manifestation_negative": interaction_data["manifestation_negative"],
        "distortion_vector": interaction_data["distortion_vector"],
        "sublimate_vector": interaction_data["sublimate_vector"],
    }


# =============================================================================
# Typed Lookup (Dataclass Output)
# =============================================================================

def lookup_interaction(
    varna: str,
    layer: str,
    *,
    force_reload: bool = False,
) -> VarnaLayerInteraction:
    """
    Look up a (varna, layer) interaction, returning typed dataclass.

    This is the primary Phase-4A API. It performs:
        1. Validate varna exists → fail if not
        2. Validate layer exists → fail if not
        3. Lookup interaction → fail if missing
        4. Validate all required fields → fail if missing
        5. Return VarnaLayerInteraction dataclass

    Example:
        >>> from agentic.ontology.phase4a import lookup_interaction
        >>> result = lookup_interaction("ka", "O3_EXECUTION")
        >>> result.manifestation_positive
        'body awakens with forward-seeking hope activation'
        >>> result.distortion_vector
        'lateral'

    Args:
        varna: The varna token (e.g., "ka", "a", "sha")
        layer: The ontological layer (e.g., "O3_EXECUTION")
        force_reload: If True, reload ontology files

    Returns:
        VarnaLayerInteraction with all four required fields

    Raises:
        Phase4AVarnaMissingError: If varna not in bridge map
        Phase4ALayerMissingError: If layer not in ontological layers
        Phase4AInteractionMissingError: If (varna, layer) pair has no entry
        Phase4AFieldMissingError: If any required field is missing
    """
    raw = lookup_interaction_raw(varna, layer, force_reload=force_reload)

    return VarnaLayerInteraction(
        varna=varna,
        layer=layer,
        manifestation_positive=raw["manifestation_positive"],
        manifestation_negative=raw["manifestation_negative"],
        distortion_vector=raw["distortion_vector"],
        sublimate_vector=raw["sublimate_vector"],
    )


# =============================================================================
# Batch Lookup
# =============================================================================

def lookup_varna_all_layers(
    varna: str,
    *,
    force_reload: bool = False,
) -> Dict[str, VarnaLayerInteraction]:
    """
    Look up a varna's interactions across all 10 layers.

    Args:
        varna: The varna token
        force_reload: If True, reload files

    Returns:
        Dict mapping layer_id → VarnaLayerInteraction

    Raises:
        Phase4AVarnaMissingError: If varna not found
        Phase4AInteractionMissingError: If any layer interaction is missing
        Phase4AFieldMissingError: If any required field is missing
    """
    layers = get_all_layers(force_reload=force_reload)
    result: Dict[str, VarnaLayerInteraction] = {}

    for layer in sorted(layers):
        result[layer] = lookup_interaction(varna, layer, force_reload=False)

    return result


def lookup_layer_all_varnas(
    layer: str,
    *,
    force_reload: bool = False,
) -> Dict[str, VarnaLayerInteraction]:
    """
    Look up all varna interactions for a specific layer.

    Args:
        layer: The ontological layer (e.g., "O3_EXECUTION")
        force_reload: If True, reload files

    Returns:
        Dict mapping varna → VarnaLayerInteraction

    Raises:
        Phase4ALayerMissingError: If layer not found
        Phase4AInteractionMissingError: If any varna interaction is missing
        Phase4AFieldMissingError: If any required field is missing
    """
    varnas = get_all_varnas(force_reload=force_reload)
    result: Dict[str, VarnaLayerInteraction] = {}

    for varna in sorted(varnas):
        result[varna] = lookup_interaction(varna, layer, force_reload=False)

    return result


# =============================================================================
# Existence Checks (Non-throwing)
# =============================================================================

def has_interaction(
    varna: str,
    layer: str,
    *,
    force_reload: bool = False,
) -> bool:
    """
    Check if a (varna, layer) interaction exists without throwing.

    Args:
        varna: The varna token
        layer: The ontological layer
        force_reload: If True, reload files

    Returns:
        True if interaction exists with all required fields, False otherwise
    """
    try:
        lookup_interaction_raw(varna, layer, force_reload=force_reload)
        return True
    except Exception:
        return False


def is_valid_varna(varna: str, *, force_reload: bool = False) -> bool:
    """
    Check if a varna exists in the bridge map.

    Args:
        varna: The varna token to check
        force_reload: If True, reload files

    Returns:
        True if varna exists, False otherwise
    """
    valid_varnas = get_all_varnas(force_reload=force_reload)
    return varna in valid_varnas


def is_valid_layer(layer: str, *, force_reload: bool = False) -> bool:
    """
    Check if a layer exists in the ontological layers file.

    Args:
        layer: The layer ID to check
        force_reload: If True, reload files

    Returns:
        True if layer exists, False otherwise
    """
    valid_layers = get_all_layers(force_reload=force_reload)
    return layer in valid_layers
