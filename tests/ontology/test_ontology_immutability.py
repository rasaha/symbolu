"""
Ontology Immutability Tests
===========================

Test-level guards to detect runtime mutation of ontology data.

Per ONTOLOGY_FREEZE_CONTRACT.md Section 3.4:
    - Ontology data structures MUST be immutable after load
    - Any attempt to mutate loaded ontology MUST raise TypeError
    - Caching is permitted; mutation is forbidden

Canonical Rule:
    "Never let a higher layer compensate for uncertainty in a lower layer."

These tests verify:
    1. Loaded ontology objects are immutable (FrozenSet, tuple, etc.)
    2. Any mutation attempt raises TypeError
    3. Reloading ontology returns identical data
    4. Checksum verification catches file modifications
"""

import copy
import hashlib
import json
import pytest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

from symbolu.ontology.phase4a.loader import (
    load_ontology_files,
    get_all_varnas,
    get_all_layers,
    _clear_cache,
    _reset_checksums_for_testing,
    _get_data_dir,
)
from symbolu.ontology.phase4a.ontology_checksums import (
    FROZEN_CHECKSUMS,
    OntologyIntegrityError,
    verify_ontology_checksum,
    verify_all_ontology_checksums,
    get_expected_checksum,
    get_all_checksums,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def reset_cache():
    """Reset ontology cache before each test."""
    _clear_cache()
    _reset_checksums_for_testing()
    yield
    _clear_cache()
    _reset_checksums_for_testing()


@pytest.fixture
def data_dir() -> Path:
    """Get path to ontology data directory."""
    return _get_data_dir()


@pytest.fixture
def ontology_data() -> Dict[str, Any]:
    """Load ontology data for testing."""
    return load_ontology_files(force_reload=True)


# =============================================================================
# Test: Loaded Data Types Are Immutable
# =============================================================================

class TestLoadedDataImmutability:
    """Verify that loaded ontology data uses immutable types where possible."""

    def test_varnas_returns_frozenset(self):
        """get_all_varnas must return FrozenSet."""
        varnas = get_all_varnas()
        assert isinstance(varnas, frozenset), (
            f"get_all_varnas must return frozenset, got {type(varnas).__name__}"
        )

    def test_layers_returns_frozenset(self):
        """get_all_layers must return FrozenSet."""
        layers = get_all_layers()
        assert isinstance(layers, frozenset), (
            f"get_all_layers must return frozenset, got {type(layers).__name__}"
        )

    def test_frozenset_mutation_raises_typeerror(self):
        """Attempting to mutate FrozenSet must raise TypeError."""
        varnas = get_all_varnas()

        with pytest.raises((TypeError, AttributeError)):
            varnas.add("fake_varna")

        with pytest.raises((TypeError, AttributeError)):
            varnas.remove("a")

        with pytest.raises((TypeError, AttributeError)):
            varnas.discard("a")

    def test_layers_frozenset_mutation_raises_typeerror(self):
        """Attempting to mutate layers FrozenSet must raise TypeError."""
        layers = get_all_layers()

        with pytest.raises((TypeError, AttributeError)):
            layers.add("O99_FAKE")

        with pytest.raises((TypeError, AttributeError)):
            layers.remove("O1_ACTING")


# =============================================================================
# Test: Reload Returns Identical Data
# =============================================================================

class TestReloadConsistency:
    """Verify that reloading ontology returns identical data."""

    def test_reload_varnas_identical(self):
        """Reloading varnas must return identical set."""
        varnas1 = get_all_varnas(force_reload=True)
        _clear_cache()
        varnas2 = get_all_varnas(force_reload=True)

        assert varnas1 == varnas2, "Reloaded varnas must be identical"

    def test_reload_layers_identical(self):
        """Reloading layers must return identical set."""
        layers1 = get_all_layers(force_reload=True)
        _clear_cache()
        layers2 = get_all_layers(force_reload=True)

        assert layers1 == layers2, "Reloaded layers must be identical"

    def test_reload_ontology_files_identical(self):
        """Reloading full ontology must return identical data."""
        data1 = load_ontology_files(force_reload=True)
        _clear_cache()
        data2 = load_ontology_files(force_reload=True)

        # Compare JSON serializations for deep equality
        json1 = json.dumps(data1, sort_keys=True)
        json2 = json.dumps(data2, sort_keys=True)

        assert json1 == json2, "Reloaded ontology data must be identical"


# =============================================================================
# Test: Checksum Verification
# =============================================================================

class TestChecksumVerification:
    """Verify checksum enforcement catches file modifications."""

    def test_frozen_checksums_not_empty(self):
        """Frozen checksum registry must not be empty."""
        assert len(FROZEN_CHECKSUMS) == 3, (
            f"Expected 3 frozen checksums, got {len(FROZEN_CHECKSUMS)}"
        )

    def test_all_ontology_files_have_checksums(self):
        """All three ontology files must have checksums."""
        expected_files = {
            "varna_bridge_map_v1.json",
            "ontological_layers_v1.json",
            "varna_layer_interaction_v1.json",
        }
        actual_files = set(FROZEN_CHECKSUMS.keys())

        assert expected_files == actual_files, (
            f"Checksum registry mismatch. "
            f"Missing: {expected_files - actual_files}. "
            f"Extra: {actual_files - expected_files}"
        )

    def test_checksums_are_valid_sha256(self):
        """All checksums must be valid 64-character hex strings."""
        for file_name, checksum in FROZEN_CHECKSUMS.items():
            assert len(checksum) == 64, (
                f"{file_name} checksum length is {len(checksum)}, expected 64"
            )
            assert all(c in "0123456789abcdef" for c in checksum), (
                f"{file_name} checksum contains invalid hex characters"
            )

    def test_verify_existing_files_passes(self, data_dir: Path):
        """Verifying existing ontology files must pass."""
        verified = verify_all_ontology_checksums(data_dir)
        assert len(verified) == 3, "All three files should verify"

    def test_checksum_mismatch_raises_integrity_error(self, data_dir: Path):
        """Checksum mismatch must raise OntologyIntegrityError."""
        # Temporarily corrupt the expected checksum
        original = FROZEN_CHECKSUMS["varna_bridge_map_v1.json"]
        FROZEN_CHECKSUMS["varna_bridge_map_v1.json"] = "0" * 64

        try:
            with pytest.raises(OntologyIntegrityError) as exc_info:
                verify_ontology_checksum(
                    "varna_bridge_map_v1.json",
                    data_dir / "varna_bridge_map_v1.json"
                )

            assert "INTEGRITY VIOLATION" in str(exc_info.value)
            assert "varna_bridge_map_v1.json" in str(exc_info.value)
        finally:
            # Restore original checksum
            FROZEN_CHECKSUMS["varna_bridge_map_v1.json"] = original

    def test_unknown_file_raises_keyerror(self, data_dir: Path):
        """Verifying unknown file must raise KeyError."""
        with pytest.raises(KeyError) as exc_info:
            verify_ontology_checksum(
                "nonexistent_v1.json",
                data_dir / "nonexistent_v1.json"
            )

        assert "not found in frozen checksum registry" in str(exc_info.value)

    def test_get_expected_checksum_returns_correct_value(self):
        """get_expected_checksum must return correct checksum."""
        checksum = get_expected_checksum("varna_bridge_map")
        assert checksum == FROZEN_CHECKSUMS["varna_bridge_map_v1.json"]

    def test_get_all_checksums_returns_copy(self):
        """get_all_checksums must return a copy, not the original."""
        checksums = get_all_checksums()
        checksums["fake_file.json"] = "fake_checksum"

        # Original should not be modified
        assert "fake_file.json" not in FROZEN_CHECKSUMS


# =============================================================================
# Test: Deep Copy Cannot Modify Original
# =============================================================================

class TestDeepCopyIsolation:
    """Verify that copies of ontology data do not affect originals."""

    def test_modifying_copy_does_not_affect_cache(self, ontology_data: Dict[str, Any]):
        """Modifying a deep copy must not affect cached data."""
        # Make a deep copy
        data_copy = copy.deepcopy(ontology_data)

        # Modify the copy
        data_copy["varna_bridge_map"]["vowels"]["a"]["bridge_meaning"] = "MODIFIED"

        # Reload and verify original is unchanged
        original = load_ontology_files(force_reload=False)

        assert original["varna_bridge_map"]["vowels"]["a"]["bridge_meaning"] != "MODIFIED"
        assert original["varna_bridge_map"]["vowels"]["a"]["bridge_meaning"] == "birth_of_cognition"


# =============================================================================
# Test: Required Varnas and Layers Present
# =============================================================================

class TestRequiredContent:
    """Verify required ontology content is present."""

    def test_vowels_present(self, ontology_data: Dict[str, Any]):
        """All expected vowels must be present in bridge map."""
        expected_vowels = {"a", "ā", "i", "ī", "u", "ū", "e", "ai", "o", "au", "aṁ", "aha"}
        actual_vowels = set(ontology_data["varna_bridge_map"]["vowels"].keys())

        assert expected_vowels == actual_vowels, (
            f"Vowel mismatch. "
            f"Missing: {expected_vowels - actual_vowels}. "
            f"Extra: {actual_vowels - expected_vowels}"
        )

    def test_all_twelve_layers_present(self, ontology_data: Dict[str, Any]):
        """All 12 ontological layers must be present."""
        expected_layers = {
            "O1_POTENTIAL", "O2_IDENTITY", "O3_EXECUTION", "O4_STRUCTURE",
            "O5_COGNITION", "O6_AGENCY", "O7_REASONING", "O8_PURPOSE",
            "O9_WITNESSES", "O10_UNIFYING", "O11_INTEGRATION", "O12_ABSOLVING"
        }
        actual_layers = set(ontology_data["ontological_layers"]["layers"].keys())

        assert expected_layers == actual_layers, (
            f"Layer mismatch. "
            f"Missing: {expected_layers - actual_layers}. "
            f"Extra: {actual_layers - expected_layers}"
        )

    def test_interaction_map_has_entries(self, ontology_data: Dict[str, Any]):
        """Interaction map must have entries for varnas."""
        interaction_map = ontology_data["varna_layer_interaction"]["interaction_map"]

        assert len(interaction_map) > 0, "Interaction map must not be empty"

        # Verify each entry has all 12 layers
        for varna, layers in interaction_map.items():
            assert len(layers) == 12, (
                f"Varna '{varna}' has {len(layers)} layers, expected 12"
            )


# =============================================================================
# Test: No Inference/Smoothing/Gap-Filling
# =============================================================================

class TestNoInference:
    """Verify ontology loader does not infer or smooth data."""

    def test_missing_varna_not_invented(self, ontology_data: Dict[str, Any]):
        """Missing varna must not be auto-created."""
        vowels = ontology_data["varna_bridge_map"]["vowels"]
        consonants = ontology_data["varna_bridge_map"]["consonants"]

        # These should NOT exist (they're not in Sanskrit varna mala)
        fake_varnas = ["zz", "xx", "qq", "invented_varna"]

        for fake in fake_varnas:
            assert fake not in vowels, f"Fake varna '{fake}' found in vowels"
            assert fake not in consonants, f"Fake varna '{fake}' found in consonants"

    def test_interaction_fields_not_defaulted(self, ontology_data: Dict[str, Any]):
        """Interaction fields must have explicit values, not defaults."""
        interaction_map = ontology_data["varna_layer_interaction"]["interaction_map"]

        required_fields = {
            "manifestation_positive",
            "manifestation_negative",
            "distortion_vector",
            "sublimate_vector",
        }

        for varna, layers in interaction_map.items():
            for layer, data in layers.items():
                for field in required_fields:
                    assert field in data, (
                        f"Missing required field '{field}' in ({varna}, {layer})"
                    )
                    value = data[field]
                    assert value is not None, (
                        f"Field '{field}' is None in ({varna}, {layer})"
                    )
                    assert value != "", (
                        f"Field '{field}' is empty string in ({varna}, {layer})"
                    )
                    assert value != "default", (
                        f"Field '{field}' has default value in ({varna}, {layer})"
                    )


# =============================================================================
# Test: Ontology Integrity Error Properties
# =============================================================================

class TestOntologyIntegrityError:
    """Verify OntologyIntegrityError has correct properties."""

    def test_integrity_error_has_file_name(self):
        """OntologyIntegrityError must expose file_name."""
        error = OntologyIntegrityError(
            file_name="test.json",
            expected_checksum="a" * 64,
            actual_checksum="b" * 64,
        )

        assert error.file_name == "test.json"

    def test_integrity_error_has_checksums(self):
        """OntologyIntegrityError must expose checksums."""
        expected = "a" * 64
        actual = "b" * 64

        error = OntologyIntegrityError(
            file_name="test.json",
            expected_checksum=expected,
            actual_checksum=actual,
        )

        assert error.expected_checksum == expected
        assert error.actual_checksum == actual

    def test_integrity_error_message_contains_key_info(self):
        """OntologyIntegrityError message must contain key information."""
        error = OntologyIntegrityError(
            file_name="test.json",
            expected_checksum="a" * 64,
            actual_checksum="b" * 64,
        )

        message = str(error)

        assert "INTEGRITY VIOLATION" in message
        assert "test.json" in message
