"""
Ontology Checksum Enforcement
=============================

FROZEN SUBSTRATE — MANDATORY INTEGRITY VERIFICATION

This module provides hardcoded SHA-256 checksums for all frozen ontology files.
Checksum verification is MANDATORY on ontology load. Mismatch raises
OntologyIntegrityError with NO FALLBACK, NO WARNING, NO REPAIR.

Per ONTOLOGY_FREEZE_CONTRACT.md:
    - Ontology is deterministic substrate, not configuration
    - Missing data MUST throw
    - No inference, smoothing, defaults, or gap-filling

Canonical Rule:
    "Never let a higher layer compensate for uncertainty in a lower layer."

Freeze Commit: 00956fdac16001dc7bd4d56725ae946a9969598b
"""

import hashlib
from pathlib import Path
from typing import Dict

from symbolu.ontology.phase4a.errors import Phase4AError


class OntologyIntegrityError(Phase4AError):
    """
    Raised when ontology file checksum verification fails.

    This error is FATAL and indicates:
        1. Ontology file was modified outside governance process
        2. File corruption occurred
        3. Checksum registry is out of sync

    There is NO recovery. The system MUST NOT proceed with mismatched ontology.
    """

    def __init__(
        self,
        file_name: str,
        expected_checksum: str,
        actual_checksum: str,
    ):
        super().__init__(
            f"ONTOLOGY INTEGRITY VIOLATION: {file_name} checksum mismatch",
            context={
                "file_name": file_name,
                "expected": expected_checksum[:16] + "...",
                "actual": actual_checksum[:16] + "...",
            }
        )
        self.file_name = file_name
        self.expected_checksum = expected_checksum
        self.actual_checksum = actual_checksum


# =============================================================================
# FROZEN CHECKSUM REGISTRY
# =============================================================================
#
# These checksums are computed from the frozen ontology files at freeze commit.
# ANY modification to the files will cause verification to fail.
#
# To update checksums (ONLY for authorized patches per ONTOLOGY_FREEZE_CONTRACT.md):
#   1. Ensure patch follows Section 4 (Controlled Patch Rules)
#   2. Run: sha256sum docs/data/<file>.json
#   3. Update the corresponding checksum below
#   4. Update docs/ontology/CHANGELOG.md
#   5. Submit PR for @ontology-core review
#

FROZEN_CHECKSUMS: Dict[str, str] = {
    # ABSOLUTELY FROZEN — NO EDITS PERMITTED
    "varna_bridge_map_v1.json": "e0605c15556afca845b233d5a0340870782c6a800b98b94c3b53d0270be13568",
    "ontological_layers_v1.json": "625f7373d64389b4f4d1e8c249f51aaf18007b48ab2a2b55b8fd67327edb54ac",

    # CONTROLLED — distortion_vector ONLY
    "varna_layer_interaction_v1.json": "772a672623fcca483a95038c11ef88fa4eb859c24d92f70c60fbdadefef68dd9",
}

# File keys for lookup
ONTOLOGY_FILE_KEYS = {
    "varna_bridge_map": "varna_bridge_map_v1.json",
    "ontological_layers": "ontological_layers_v1.json",
    "varna_layer_interaction": "varna_layer_interaction_v1.json",
}


def _compute_sha256(file_path: Path) -> str:
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


def verify_ontology_checksum(file_name: str, file_path: Path) -> None:
    """
    Verify a single ontology file checksum against frozen registry.

    This function is MANDATORY before loading any ontology file.
    Mismatch is FATAL — raises OntologyIntegrityError with no fallback.

    Args:
        file_name: Name of the ontology file (e.g., "varna_bridge_map_v1.json")
        file_path: Full path to the file

    Raises:
        OntologyIntegrityError: If checksum mismatch detected
        KeyError: If file_name not in frozen registry
        FileNotFoundError: If file does not exist
    """
    if file_name not in FROZEN_CHECKSUMS:
        raise KeyError(
            f"File '{file_name}' not found in frozen checksum registry. "
            f"Valid files: {list(FROZEN_CHECKSUMS.keys())}"
        )

    if not file_path.exists():
        raise FileNotFoundError(f"Ontology file not found: {file_path}")

    expected = FROZEN_CHECKSUMS[file_name]
    actual = _compute_sha256(file_path)

    if actual != expected:
        raise OntologyIntegrityError(
            file_name=file_name,
            expected_checksum=expected,
            actual_checksum=actual,
        )


def verify_all_ontology_checksums(data_dir: Path) -> Dict[str, str]:
    """
    Verify checksums for all frozen ontology files.

    This function should be called on application startup to ensure
    ontology integrity before any processing begins.

    Args:
        data_dir: Path to docs/data directory containing ontology files

    Returns:
        Dict mapping file_name to verified checksum

    Raises:
        OntologyIntegrityError: If ANY checksum mismatch detected
        FileNotFoundError: If ANY ontology file is missing
    """
    verified: Dict[str, str] = {}

    for file_name, expected_checksum in FROZEN_CHECKSUMS.items():
        file_path = data_dir / file_name
        verify_ontology_checksum(file_name, file_path)
        verified[file_name] = expected_checksum

    return verified


def get_expected_checksum(file_key: str) -> str:
    """
    Get the expected checksum for an ontology file by key.

    Args:
        file_key: Key from ONTOLOGY_FILE_KEYS (e.g., "varna_bridge_map")

    Returns:
        Expected SHA-256 checksum

    Raises:
        KeyError: If file_key not recognized
    """
    if file_key not in ONTOLOGY_FILE_KEYS:
        raise KeyError(
            f"Unknown file key '{file_key}'. "
            f"Valid keys: {list(ONTOLOGY_FILE_KEYS.keys())}"
        )

    file_name = ONTOLOGY_FILE_KEYS[file_key]
    return FROZEN_CHECKSUMS[file_name]


def get_all_checksums() -> Dict[str, str]:
    """
    Get all frozen checksums for audit purposes.

    Returns:
        Copy of the frozen checksum registry
    """
    return dict(FROZEN_CHECKSUMS)
