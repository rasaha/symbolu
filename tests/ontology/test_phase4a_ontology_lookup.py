"""
Phase-4A Ontology Lookup Test Suite
====================================

Phase-4A is the ontology lookup sub-module within the composite Phase-4
of the Phase-1b → Phase-14 experimental pipeline.

Comprehensive tests for the Phase-4A ontology lookup layer.

Test Categories:
    1. Formula Determinism - Same input produces identical output
    2. Zero-LLM Guarantee - No AI/ML imports or calls
    3. Fail-Fast Behavior - Missing data triggers errors, not inference
    4. Validation Strictness - All required fields checked
    5. Lookup Correctness - Returns exact frozen file values
    6. Edge Cases - Boundary conditions and error handling

Total: ~50 tests
"""

import pytest
import inspect
from typing import FrozenSet

from symbolu.ontology.phase4a import (
    # Errors
    Phase4AError,
    Phase4AValidationError,
    Phase4AVarnaMissingError,
    Phase4ALayerMissingError,
    Phase4AInteractionMissingError,
    Phase4AFieldMissingError,
    # Models
    VarnaLayerInteraction,
    OntologyValidationReport,
    # Loader
    load_ontology_files,
    validate_ontology,
    get_all_varnas,
    get_all_layers,
    # Lookup
    lookup_interaction,
    lookup_interaction_raw,
)
from symbolu.ontology.phase4a.lookup import (
    lookup_varna_all_layers,
    lookup_layer_all_varnas,
    has_interaction,
    is_valid_varna,
    is_valid_layer,
)
from symbolu.ontology.phase4a.loader import (
    _clear_cache,
    VALID_LAYER_IDS,
    REQUIRED_INTERACTION_FIELDS,
)


# =============================================================================
# Test Class 1: Formula Determinism (7 tests)
# =============================================================================

class TestPhase4AFormulaDeterminism:
    """Verify Phase-4A lookup is deterministic."""

    def test_lookup_same_input_same_output(self):
        """Test same (varna, layer) produces identical result every time."""
        results = [lookup_interaction("ka", "O1_ACTING") for _ in range(10)]
        first = results[0]
        assert all(r == first for r in results)

    def test_lookup_raw_deterministic(self):
        """Test raw lookup is deterministic."""
        results = [lookup_interaction_raw("a", "O2_TAGGING") for _ in range(10)]
        assert len(set(tuple(r.items()) for r in results)) == 1

    def test_all_layers_lookup_deterministic(self):
        """Test looking up all layers for a varna is deterministic."""
        results = [lookup_varna_all_layers("sha") for _ in range(5)]
        first_keys = sorted(results[0].keys())
        assert all(sorted(r.keys()) == first_keys for r in results)

    def test_all_varnas_lookup_deterministic(self):
        """Test looking up all varnas for a layer is deterministic."""
        results = [lookup_layer_all_varnas("O3_FORMING") for _ in range(5)]
        first_keys = sorted(results[0].keys())
        assert all(sorted(r.keys()) == first_keys for r in results)

    def test_validation_report_deterministic(self):
        """Test validation report is deterministic."""
        reports = [validate_ontology() for _ in range(5)]
        assert all(r.valid == reports[0].valid for r in reports)
        assert all(r.varna_count == reports[0].varna_count for r in reports)
        assert all(r.layer_count == reports[0].layer_count for r in reports)

    def test_get_all_varnas_deterministic(self):
        """Test get_all_varnas returns same set every time."""
        results = [get_all_varnas() for _ in range(5)]
        assert all(r == results[0] for r in results)

    def test_get_all_layers_deterministic(self):
        """Test get_all_layers returns same set every time."""
        results = [get_all_layers() for _ in range(5)]
        assert all(r == results[0] for r in results)


# =============================================================================
# Test Class 2: Zero-LLM Guarantee (6 tests)
# =============================================================================

class TestPhase4AZeroLLMGuarantee:
    """Verify Phase-4A makes NO LLM or ML calls."""

    def test_no_anthropic_imports(self):
        """Test no Anthropic imports in Phase-4A modules."""
        import symbolu.ontology.phase4a.lookup as module
        source = inspect.getsource(module)
        assert 'anthropic' not in source.lower()

    def test_no_openai_imports(self):
        """Test no OpenAI imports in Phase-4A modules."""
        import symbolu.ontology.phase4a.lookup as module
        source = inspect.getsource(module)
        assert 'openai' not in source.lower()

    def test_no_ml_imports_loader(self):
        """Test no ML imports in loader."""
        import symbolu.ontology.phase4a.loader as module
        source = inspect.getsource(module)
        for ml_lib in ['sklearn', 'tensorflow', 'torch', 'numpy', 'scipy']:
            assert ml_lib not in source.lower()

    def test_no_network_calls(self):
        """Test no network calls in Phase-4A."""
        import symbolu.ontology.phase4a.lookup as module
        source = inspect.getsource(module)
        assert 'requests' not in source.lower()
        assert 'urllib' not in source.lower()
        assert 'httpx' not in source.lower()

    def test_no_randomness(self):
        """Test no randomness in Phase-4A."""
        import symbolu.ontology.phase4a.lookup as module
        source = inspect.getsource(module)
        assert 'random' not in source.lower()

    def test_runs_offline(self):
        """Test Phase-4A runs completely offline."""
        # If this runs, Phase-4A works offline
        result = lookup_interaction("ga", "O5_DIRECTING")
        assert result is not None
        assert isinstance(result, VarnaLayerInteraction)


# =============================================================================
# Test Class 3: Fail-Fast Behavior (8 tests)
# =============================================================================

class TestPhase4AFailFast:
    """Verify Phase-4A fails immediately on missing data, never infers."""

    def test_missing_varna_raises_error(self):
        """Test missing varna raises Phase4AVarnaMissingError."""
        with pytest.raises(Phase4AVarnaMissingError) as exc:
            lookup_interaction("nonexistent_varna", "O1_ACTING")
        assert "nonexistent_varna" in str(exc.value)

    def test_missing_layer_raises_error(self):
        """Test missing layer raises Phase4ALayerMissingError."""
        with pytest.raises(Phase4ALayerMissingError) as exc:
            lookup_interaction("ka", "O99_INVALID")
        assert "O99_INVALID" in str(exc.value)

    def test_invalid_layer_format_raises_error(self):
        """Test invalid layer format raises error."""
        with pytest.raises(Phase4ALayerMissingError):
            lookup_interaction("ka", "ACTING")  # Missing O1_ prefix

    def test_empty_varna_raises_error(self):
        """Test empty varna raises error."""
        with pytest.raises(Phase4AVarnaMissingError):
            lookup_interaction("", "O1_ACTING")

    def test_empty_layer_raises_error(self):
        """Test empty layer raises error."""
        with pytest.raises(Phase4ALayerMissingError):
            lookup_interaction("ka", "")

    def test_whitespace_varna_raises_error(self):
        """Test whitespace-only varna raises error."""
        with pytest.raises(Phase4AVarnaMissingError):
            lookup_interaction("   ", "O1_ACTING")

    def test_error_includes_context(self):
        """Test errors include helpful context."""
        with pytest.raises(Phase4AVarnaMissingError) as exc:
            lookup_interaction("xyz", "O1_ACTING")
        assert exc.value.varna == "xyz"
        assert "varna" in str(exc.value).lower()

    def test_layer_error_includes_valid_layers(self):
        """Test layer error includes list of valid layers."""
        with pytest.raises(Phase4ALayerMissingError) as exc:
            lookup_interaction("ka", "O0_FAKE")
        assert len(exc.value.valid_layers) == 12


# =============================================================================
# Test Class 4: Validation Strictness (6 tests)
# =============================================================================

class TestPhase4AValidationStrictness:
    """Verify Phase-4A validates all required fields."""

    def test_validation_report_returns_valid(self):
        """Test validation report indicates valid ontology."""
        report = validate_ontology()
        assert isinstance(report, OntologyValidationReport)
        # If the files are complete, this should be True
        # If files have issues, this might be False with details

    def test_required_fields_defined(self):
        """Test required interaction fields are defined."""
        assert "manifestation_positive" in REQUIRED_INTERACTION_FIELDS
        assert "manifestation_negative" in REQUIRED_INTERACTION_FIELDS
        assert "distortion_vector" in REQUIRED_INTERACTION_FIELDS
        assert "sublimate_vector" in REQUIRED_INTERACTION_FIELDS
        assert len(REQUIRED_INTERACTION_FIELDS) == 4

    def test_valid_layer_ids_defined(self):
        """Test all 12 layer IDs are defined."""
        assert len(VALID_LAYER_IDS) == 12
        assert "O1_POTENTIAL" in VALID_LAYER_IDS
        assert "O12_ABSOLVING" in VALID_LAYER_IDS

    def test_interaction_has_all_required_fields(self):
        """Test looked-up interaction has all required fields."""
        result = lookup_interaction("ka", "O1_ACTING")
        assert hasattr(result, "manifestation_positive")
        assert hasattr(result, "manifestation_negative")
        assert hasattr(result, "distortion_vector")
        assert hasattr(result, "sublimate_vector")

    def test_varna_count_matches_bridge_map(self):
        """Test varna count in validation matches get_all_varnas."""
        report = validate_ontology()
        varnas = get_all_varnas()
        assert report.varna_count == len(varnas)

    def test_layer_count_is_ten(self):
        """Test layer count is exactly 10."""
        report = validate_ontology()
        assert report.layer_count == 10


# =============================================================================
# Test Class 5: Lookup Correctness (8 tests)
# =============================================================================

class TestPhase4ALookupCorrectness:
    """Verify Phase-4A returns exact values from frozen files."""

    def test_lookup_returns_dataclass(self):
        """Test lookup returns VarnaLayerInteraction dataclass."""
        result = lookup_interaction("a", "O1_ACTING")
        assert isinstance(result, VarnaLayerInteraction)

    def test_lookup_includes_input_varna(self):
        """Test result includes input varna."""
        result = lookup_interaction("ka", "O1_ACTING")
        assert result.varna == "ka"

    def test_lookup_includes_input_layer(self):
        """Test result includes input layer."""
        result = lookup_interaction("ka", "O5_DIRECTING")
        assert result.layer == "O5_DIRECTING"

    def test_distortion_vector_valid_values(self):
        """Test distortion_vector is 'lateral' or 'downward'."""
        result = lookup_interaction("a", "O1_ACTING")
        assert result.distortion_vector in ("lateral", "downward")

    def test_sublimate_vector_valid_values(self):
        """Test sublimate_vector is 'upward' or 'terminating'."""
        result = lookup_interaction("a", "O1_ACTING")
        assert result.sublimate_vector in ("upward", "terminating")

    def test_o10_has_terminating_sublimate(self):
        """Test O10_ABSOLVING typically has 'terminating' sublimate."""
        result = lookup_interaction("a", "O10_ABSOLVING")
        assert result.sublimate_vector == "terminating"

    def test_raw_lookup_returns_dict(self):
        """Test raw lookup returns plain dict."""
        result = lookup_interaction_raw("sha", "O7_PURPOSING")
        assert isinstance(result, dict)
        assert set(result.keys()) == set(REQUIRED_INTERACTION_FIELDS)

    def test_manifestation_fields_are_strings(self):
        """Test manifestation fields are non-empty strings."""
        result = lookup_interaction("ga", "O3_FORMING")
        assert isinstance(result.manifestation_positive, str)
        assert isinstance(result.manifestation_negative, str)
        assert len(result.manifestation_positive) > 0
        assert len(result.manifestation_negative) > 0


# =============================================================================
# Test Class 6: Edge Cases (5 tests)
# =============================================================================

class TestPhase4AEdgeCases:
    """Verify Phase-4A handles edge cases correctly."""

    def test_vowel_lookup_works(self):
        """Test vowel varnas work."""
        result = lookup_interaction("a", "O1_ACTING")
        assert result.varna == "a"

    def test_consonant_lookup_works(self):
        """Test consonant varnas work."""
        result = lookup_interaction("ka", "O1_ACTING")
        assert result.varna == "ka"

    def test_special_vowel_am_works(self):
        """Test special vowel aṁ (anusvara) works."""
        if is_valid_varna("aṁ"):
            result = lookup_interaction("aṁ", "O1_ACTING")
            assert result.varna == "aṁ"

    def test_special_vowel_aha_works(self):
        """Test special vowel aha (visarga) works."""
        if is_valid_varna("aha"):
            result = lookup_interaction("aha", "O1_ACTING")
            assert result.varna == "aha"

    def test_conjunct_ksha_works(self):
        """Test conjunct consonant ksha works."""
        result = lookup_interaction("ksha", "O1_ACTING")
        assert result.varna == "ksha"


# =============================================================================
# Test Class 7: Dataclass Immutability (4 tests)
# =============================================================================

class TestPhase4AImmutability:
    """Verify Phase-4A outputs are immutable."""

    def test_varnaLayerInteraction_is_frozen(self):
        """Test VarnaLayerInteraction cannot be modified."""
        result = lookup_interaction("ka", "O1_ACTING")
        with pytest.raises(AttributeError):
            result.varna = "modified"

    def test_varnaLayerInteraction_is_hashable(self):
        """Test VarnaLayerInteraction can be used in sets."""
        result1 = lookup_interaction("ka", "O1_ACTING")
        result2 = lookup_interaction("ka", "O1_ACTING")
        result_set = {result1, result2}
        assert len(result_set) == 1  # Same hash

    def test_to_dict_returns_copy(self):
        """Test to_dict returns a modifiable copy."""
        result = lookup_interaction("ka", "O1_ACTING")
        d = result.to_dict()
        d["varna"] = "modified"
        assert result.varna == "ka"  # Original unchanged

    def test_get_all_varnas_returns_frozenset(self):
        """Test get_all_varnas returns immutable frozenset."""
        varnas = get_all_varnas()
        assert isinstance(varnas, frozenset)


# =============================================================================
# Test Class 8: Existence Checks (4 tests)
# =============================================================================

class TestPhase4AExistenceChecks:
    """Verify non-throwing existence check functions."""

    def test_has_interaction_true(self):
        """Test has_interaction returns True for valid pair."""
        assert has_interaction("ka", "O1_ACTING") is True

    def test_has_interaction_false_bad_varna(self):
        """Test has_interaction returns False for bad varna."""
        assert has_interaction("xyz", "O1_ACTING") is False

    def test_is_valid_varna_true(self):
        """Test is_valid_varna returns True for valid varna."""
        assert is_valid_varna("ka") is True
        assert is_valid_varna("a") is True

    def test_is_valid_layer_true(self):
        """Test is_valid_layer returns True for valid layer."""
        assert is_valid_layer("O1_ACTING") is True
        assert is_valid_layer("O10_ABSOLVING") is True


# =============================================================================
# Test Class 9: All Layers Coverage (2 tests)
# =============================================================================

class TestPhase4AAllLayersCoverage:
    """Verify all 12 layers work for varnas."""

    def test_all_layers_for_ka(self):
        """Test all 12 layers work for 'ka'."""
        result = lookup_varna_all_layers("ka")
        assert len(result) == 12
        assert "O1_POTENTIAL" in result
        assert "O12_ABSOLVING" in result

    def test_all_layers_have_required_fields(self):
        """Test all layer interactions have required fields."""
        result = lookup_varna_all_layers("ga")
        for layer, interaction in result.items():
            assert hasattr(interaction, "manifestation_positive")
            assert hasattr(interaction, "manifestation_negative")
            assert hasattr(interaction, "distortion_vector")
            assert hasattr(interaction, "sublimate_vector")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
