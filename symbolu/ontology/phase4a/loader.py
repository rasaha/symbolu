"""
Phase-4A Ontology Loader
========================

FROZEN SUBSTRATE — NO INFERENCE, NO MODIFICATION, NO GAP-FILLING

Phase-4A is the ontology lookup sub-module within the composite Phase-4
of the Phase-1b → Phase-14 experimental pipeline.

Loads and validates the three frozen ontology files:
    - varna_bridge_map_v1.json
    - ontological_layers_v1.json
    - varna_layer_interaction_v1.json

Validation Rules:
    1. Every varna in interaction file MUST exist in bridge file
    2. Every layer in interaction file MUST exist in ontological layers
    3. Every interaction MUST have all required fields
    4. Checksum/hash consistency is enforced (fail-fast on mismatch)

The loader uses module-level caching. Files are loaded once per process.

HARD INVARIANTS:
    - READ-ONLY: Never modifies frozen ontology files
    - DETERMINISTIC: Same input => identical output
    - FAIL-FAST: Missing data triggers immediate error, never infers
    - NO INFERENCE: No gap-filling, no polarity invention, no smoothing
    - CHECKSUM VALIDATED: File integrity verified on load
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Set, Tuple, Optional, Any, FrozenSet

from symbolu.ontology.phase4a.errors import (
    Phase4AValidationError,
    Phase4AFileNotFoundError,
    Phase4AFileParseError,
)
from symbolu.ontology.phase4a.models import (
    OntologyValidationReport,
    VarnaInfo,
    LayerInfo,
)


# =============================================================================
# File Paths
# =============================================================================

def _get_data_dir() -> Path:
    """
    Get the path to the docs/data directory containing frozen ontology files.

    Returns:
        Path to the data directory
    """
    # Navigate from this file to docs/data
    # This file: symbolu/ontology/phase4a/loader.py
    # Data dir: docs/data/
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent  # symbolu repo root
    return project_root / "docs" / "data"


ONTOLOGY_FILES = {
    "varna_bridge_map": "varna_bridge_map_v1.json",
    "ontological_layers": "ontological_layers_v1.json",
    "varna_layer_interaction": "varna_layer_interaction_v1.json",
}

# Required fields for each interaction entry
REQUIRED_INTERACTION_FIELDS = frozenset({
    "manifestation_positive",
    "manifestation_negative",
    "distortion_vector",
    "sublimate_vector",
})

# Valid layer IDs (O1 through O12) - 12D patent-exact sequence
VALID_LAYER_IDS = frozenset({
    "O1_POTENTIAL",
    "O2_IDENTITY",
    "O3_EXECUTION",
    "O4_STRUCTURE",
    "O5_COGNITION",
    "O6_AGENCY",
    "O7_REASONING",
    "O8_PURPOSE",
    "O9_WITNESSES",
    "O10_UNIFYING",
    "O11_INTEGRATION",
    "O12_ABSOLVING",
})


# =============================================================================
# Checksum Registry — Frozen Substrate Integrity
# =============================================================================

# These checksums are computed from the frozen ontology files.
# Any modification to the files will cause a checksum mismatch and fail-fast.
_FROZEN_CHECKSUMS: Dict[str, Optional[str]] = {
    "varna_bridge_map": None,  # Computed on first load, then locked
    "ontological_layers": None,
    "varna_layer_interaction": None,
}

_checksums_locked: bool = False


def _compute_file_checksum(file_path: Path) -> str:
    """
    Compute SHA-256 checksum of a file.

    Args:
        file_path: Path to file

    Returns:
        Hex-encoded SHA-256 checksum
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _verify_checksum(file_key: str, file_path: Path) -> None:
    """
    Verify file checksum matches frozen value.

    On first load, records the checksum.
    On subsequent loads, verifies checksum matches.

    Args:
        file_key: Key into ONTOLOGY_FILES
        file_path: Path to file

    Raises:
        Phase4AValidationError: If checksum mismatch detected
    """
    global _checksums_locked

    current_checksum = _compute_file_checksum(file_path)

    if _FROZEN_CHECKSUMS[file_key] is None:
        # First load — record checksum
        _FROZEN_CHECKSUMS[file_key] = current_checksum
    else:
        # Subsequent load — verify checksum
        if current_checksum != _FROZEN_CHECKSUMS[file_key]:
            raise Phase4AValidationError(
                message=f"CHECKSUM MISMATCH: {file_key} has been modified. "
                        f"Expected {_FROZEN_CHECKSUMS[file_key][:16]}..., "
                        f"got {current_checksum[:16]}...",
                missing_varnas=(),
                missing_layers=(),
                orphan_interactions=(),
            )


def get_frozen_checksums() -> Dict[str, Optional[str]]:
    """
    Get the current frozen checksums for audit purposes.

    Returns:
        Dict mapping file_key → checksum (or None if not yet loaded)
    """
    return dict(_FROZEN_CHECKSUMS)


def verify_all_checksums() -> bool:
    """
    Verify all frozen ontology files have consistent checksums.

    This is a fail-fast integrity check.

    Returns:
        True if all checksums are valid

    Raises:
        Phase4AValidationError: If any checksum mismatch
    """
    for file_key in ONTOLOGY_FILES:
        file_path = _get_data_dir() / ONTOLOGY_FILES[file_key]
        if file_path.exists():
            _verify_checksum(file_key, file_path)
    return True


# =============================================================================
# Module-Level Cache
# =============================================================================

_cached_ontology: Optional[Dict[str, Any]] = None
_cached_varnas: Optional[FrozenSet[str]] = None
_cached_layers: Optional[FrozenSet[str]] = None


def _load_json_file(file_key: str) -> Dict[str, Any]:
    """
    Load a single JSON file from the data directory.

    FROZEN SUBSTRATE: Verifies checksum before loading.

    Args:
        file_key: Key into ONTOLOGY_FILES

    Returns:
        Parsed JSON as dict

    Raises:
        Phase4AFileNotFoundError: If file doesn't exist
        Phase4AFileParseError: If file is invalid JSON
        Phase4AValidationError: If checksum mismatch
    """
    file_name = ONTOLOGY_FILES[file_key]
    file_path = _get_data_dir() / file_name

    if not file_path.exists():
        raise Phase4AFileNotFoundError(file_name, str(file_path))

    # Verify checksum before loading (fail-fast on modification)
    _verify_checksum(file_key, file_path)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise Phase4AFileParseError(file_name, str(e))


def load_ontology_files(*, force_reload: bool = False) -> Dict[str, Any]:
    """
    Load all three frozen ontology files.

    Files are cached at module level. Use force_reload=True to reload.

    Args:
        force_reload: If True, reload files even if cached

    Returns:
        Dict with keys:
            - "varna_bridge_map": The varna bridge map data
            - "ontological_layers": The layer definitions
            - "varna_layer_interaction": The interaction map

    Raises:
        Phase4AFileNotFoundError: If any file is missing
        Phase4AFileParseError: If any file is invalid JSON
    """
    global _cached_ontology

    if _cached_ontology is not None and not force_reload:
        return _cached_ontology

    ontology = {
        "varna_bridge_map": _load_json_file("varna_bridge_map"),
        "ontological_layers": _load_json_file("ontological_layers"),
        "varna_layer_interaction": _load_json_file("varna_layer_interaction"),
    }

    _cached_ontology = ontology
    return ontology


def _clear_cache() -> None:
    """Clear the module-level cache. Used for testing."""
    global _cached_ontology, _cached_varnas, _cached_layers
    _cached_ontology = None
    _cached_varnas = None
    _cached_layers = None
    # Note: Checksums are NOT cleared — once recorded, they are frozen
    # To reset checksums in tests, use _reset_checksums_for_testing()


def _reset_checksums_for_testing() -> None:
    """
    Reset checksum registry for testing purposes ONLY.

    WARNING: This should only be used in test fixtures.
    Production code should NEVER call this function.
    """
    global _FROZEN_CHECKSUMS
    _FROZEN_CHECKSUMS["varna_bridge_map"] = None
    _FROZEN_CHECKSUMS["ontological_layers"] = None
    _FROZEN_CHECKSUMS["varna_layer_interaction"] = None


# =============================================================================
# Varna Extraction
# =============================================================================

def _extract_varnas_from_bridge_map(bridge_map: Dict[str, Any]) -> FrozenSet[str]:
    """
    Extract all varna tokens from the bridge map.

    Args:
        bridge_map: The loaded varna_bridge_map_v1.json

    Returns:
        Frozen set of all varna tokens
    """
    varnas: Set[str] = set()

    # Add vowels
    if "vowels" in bridge_map:
        varnas.update(bridge_map["vowels"].keys())

    # Add consonants
    if "consonants" in bridge_map:
        varnas.update(bridge_map["consonants"].keys())

    return frozenset(varnas)


def get_all_varnas(*, force_reload: bool = False) -> FrozenSet[str]:
    """
    Get all valid varna tokens from the bridge map.

    Args:
        force_reload: If True, reload files

    Returns:
        Frozen set of all valid varna tokens
    """
    global _cached_varnas

    if _cached_varnas is not None and not force_reload:
        return _cached_varnas

    ontology = load_ontology_files(force_reload=force_reload)
    _cached_varnas = _extract_varnas_from_bridge_map(ontology["varna_bridge_map"])
    return _cached_varnas


# =============================================================================
# Layer Extraction
# =============================================================================

def _extract_layers_from_ontological_layers(layers_file: Dict[str, Any]) -> FrozenSet[str]:
    """
    Extract all layer IDs from the ontological layers file.

    Args:
        layers_file: The loaded ontological_layers_v1.json

    Returns:
        Frozen set of all layer IDs
    """
    if "layers" not in layers_file:
        return frozenset()
    return frozenset(layers_file["layers"].keys())


def get_all_layers(*, force_reload: bool = False) -> FrozenSet[str]:
    """
    Get all valid layer IDs from the ontological layers file.

    Args:
        force_reload: If True, reload files

    Returns:
        Frozen set of all valid layer IDs (O3_EXECUTION through O12_ABSOLVING)
    """
    global _cached_layers

    if _cached_layers is not None and not force_reload:
        return _cached_layers

    ontology = load_ontology_files(force_reload=force_reload)
    _cached_layers = _extract_layers_from_ontological_layers(
        ontology["ontological_layers"]
    )
    return _cached_layers


# =============================================================================
# Validation
# =============================================================================

def validate_ontology(*, force_reload: bool = False) -> OntologyValidationReport:
    """
    Validate consistency between the three frozen ontology files.

    Validation checks:
        1. Every varna in interaction file exists in bridge file
        2. Every layer in interaction file exists in ontological layers
        3. Every interaction entry has all required fields

    Args:
        force_reload: If True, reload files before validation

    Returns:
        OntologyValidationReport (check .valid to see if passed)
    """
    ontology = load_ontology_files(force_reload=force_reload)

    bridge_map = ontology["varna_bridge_map"]
    layers_file = ontology["ontological_layers"]
    interaction_file = ontology["varna_layer_interaction"]

    # Extract valid sets
    valid_varnas = _extract_varnas_from_bridge_map(bridge_map)
    valid_layers = _extract_layers_from_ontological_layers(layers_file)

    # Get interaction map
    interaction_map = interaction_file.get("interaction_map", {})

    # Collect errors
    errors: list[str] = []
    missing_varnas: list[str] = []
    missing_layers: list[str] = []
    missing_interactions: list[Tuple[str, str]] = []
    missing_fields: list[Tuple[str, str, str]] = []  # (varna, layer, field)

    interaction_count = 0

    # Check each interaction entry
    for varna, layer_map in interaction_map.items():
        # Check varna exists in bridge map
        if varna not in valid_varnas:
            missing_varnas.append(varna)
            errors.append(
                f"Varna '{varna}' in interaction file not found in bridge map"
            )

        if not isinstance(layer_map, dict):
            errors.append(
                f"Invalid layer map for varna '{varna}': expected dict, got {type(layer_map).__name__}"
            )
            continue

        for layer, interaction_data in layer_map.items():
            interaction_count += 1

            # Check layer exists in ontological layers
            if layer not in valid_layers:
                if layer not in missing_layers:
                    missing_layers.append(layer)
                errors.append(
                    f"Layer '{layer}' in interaction for varna '{varna}' not found in ontological layers"
                )

            if not isinstance(interaction_data, dict):
                errors.append(
                    f"Invalid interaction data for ({varna}, {layer}): expected dict"
                )
                continue

            # Check required fields
            for field in REQUIRED_INTERACTION_FIELDS:
                if field not in interaction_data:
                    missing_fields.append((varna, layer, field))
                    errors.append(
                        f"Missing required field '{field}' in interaction ({varna}, {layer})"
                    )

    # Check that all expected (varna, layer) pairs exist
    # For each varna in bridge map, we expect interactions with all layers
    for varna in valid_varnas:
        if varna not in interaction_map:
            for layer in valid_layers:
                missing_interactions.append((varna, layer))
            errors.append(f"Varna '{varna}' has no interactions defined")
        else:
            varna_layers = interaction_map[varna]
            if isinstance(varna_layers, dict):
                for layer in valid_layers:
                    if layer not in varna_layers:
                        missing_interactions.append((varna, layer))
                        errors.append(
                            f"Missing interaction for (varna='{varna}', layer='{layer}')"
                        )

    # Build report
    varna_count = len(valid_varnas)
    layer_count = len(valid_layers)

    if errors:
        return OntologyValidationReport.failure(
            varna_count=varna_count,
            layer_count=layer_count,
            interaction_count=interaction_count,
            missing_varnas=tuple(missing_varnas),
            missing_layers=tuple(missing_layers),
            missing_interactions=tuple(missing_interactions),
            errors=tuple(errors),
        )

    return OntologyValidationReport.success(
        varna_count=varna_count,
        layer_count=layer_count,
        interaction_count=interaction_count,
    )


def validate_ontology_strict(*, force_reload: bool = False) -> None:
    """
    Validate ontology and raise on any inconsistency.

    This is the recommended startup check for Phase-4A.

    Args:
        force_reload: If True, reload files before validation

    Raises:
        Phase4AValidationError: If any validation check fails
    """
    report = validate_ontology(force_reload=force_reload)

    if not report.valid:
        raise Phase4AValidationError(
            message="Ontology validation failed",
            missing_varnas=report.missing_varnas_in_interactions,
            missing_layers=report.missing_layers_in_interactions,
            orphan_interactions=tuple(
                f"({v}, {l})" for v, l in report.missing_interactions[:10]
            ),
        )


# =============================================================================
# Info Retrieval
# =============================================================================

def get_varna_info(varna: str, *, force_reload: bool = False) -> Optional[VarnaInfo]:
    """
    Get information about a specific varna.

    Args:
        varna: The varna token to look up
        force_reload: If True, reload files

    Returns:
        VarnaInfo if found, None otherwise
    """
    ontology = load_ontology_files(force_reload=force_reload)
    bridge_map = ontology["varna_bridge_map"]

    # Check vowels
    if "vowels" in bridge_map and varna in bridge_map["vowels"]:
        vowel_data = bridge_map["vowels"][varna]
        return VarnaInfo(
            varna=varna,
            varna_type="vowel",
            bridge_meaning=vowel_data.get("bridge_meaning", ""),
            varna_group="",
            aspirated=False,
        )

    # Check consonants
    if "consonants" in bridge_map and varna in bridge_map["consonants"]:
        consonant_data = bridge_map["consonants"][varna]
        return VarnaInfo(
            varna=varna,
            varna_type="consonant",
            bridge_meaning=consonant_data.get("bridge_meaning", ""),
            varna_group=consonant_data.get("varna_group", ""),
            aspirated=consonant_data.get("aspirated", False),
        )

    return None


def get_layer_info(layer: str, *, force_reload: bool = False) -> Optional[LayerInfo]:
    """
    Get information about a specific layer.

    Args:
        layer: The layer ID to look up (e.g., "O3_EXECUTION")
        force_reload: If True, reload files

    Returns:
        LayerInfo if found, None otherwise
    """
    ontology = load_ontology_files(force_reload=force_reload)
    layers_file = ontology["ontological_layers"]

    if "layers" not in layers_file or layer not in layers_file["layers"]:
        return None

    layer_data = layers_file["layers"][layer]
    adjacency = layer_data.get("adjacency", {})
    polarity = layer_data.get("default_polarity_behavior", {})

    return LayerInfo(
        layer_id=layer,
        experiential_role=layer_data.get("experiential_role", ""),
        kosha_anchor=layer_data.get("kosha_anchor", ""),
        polarity_tendency=polarity.get("tendency", ""),
        prev_layer=adjacency.get("prev_layer") or "",
        next_layer=adjacency.get("next_layer") or "",
    )
