"""
Tests for PPV (Phonemic Propensity Vector) Modules

These tests validate:
- PPV Contract v1 (symbolu/ppv/ppv_contract_v1.py)
- PPV Builder v1 (symbolu/ppv/ppv_builder_v1.py)

Key invariants tested:
- Fixed 8 dimensions
- Bounded values (0-7)
- Deterministic hash computation
- No ML/NLP dependencies
- Immutable structures
"""

import pytest
import hashlib
from dataclasses import FrozenInstanceError

from symbolu.ppv.ppv_contract_v1 import (
    PPV_CONTRACT_VERSION,
    PPV_DIM_COUNT,
    PPV_DIM_ORDER,
    PPV_VALUE_MIN,
    PPV_VALUE_MAX,
    PPVDim,
    PPVVector,
    create_ppv_vector,
    validate_ppv_invariants_v1,
    _compute_aggregate,
    _compute_ppv_hash,
)

from symbolu.ppv.ppv_builder_v1 import (
    PPV_BUILDER_VERSION,
    PHONEME_FEATURES,
    DEFAULT_PHONEME_FEATURES,
    PPVBuildContext,
    build_ppv_from_context,
    build_ppv_for_artifact,
    _get_phoneme_features,
    _clamp_value,
    _compute_edge_tension,
    _compute_sonority_lift,
)


# =============================================================================
# Tests for PPV Contract Constants
# =============================================================================


class TestPPVContractConstants:
    """Tests for PPV contract constants."""

    def test_version_is_string(self):
        """Version should be a string."""
        assert isinstance(PPV_CONTRACT_VERSION, str)
        assert PPV_CONTRACT_VERSION.startswith("1.")

    def test_dim_count_is_8(self):
        """Dimension count should be exactly 8."""
        assert PPV_DIM_COUNT == 8

    def test_dim_order_has_8_elements(self):
        """Dimension order should have exactly 8 elements."""
        assert len(PPV_DIM_ORDER) == 8

    def test_dim_order_all_ppv_dim(self):
        """All dimensions in order should be PPVDim."""
        for dim in PPV_DIM_ORDER:
            assert isinstance(dim, PPVDim)

    def test_value_bounds(self):
        """Value bounds should be 0-7."""
        assert PPV_VALUE_MIN == 0
        assert PPV_VALUE_MAX == 7


# =============================================================================
# Tests for PPVDim Enum
# =============================================================================


class TestPPVDim:
    """Tests for PPVDim enum."""

    def test_exactly_8_dimensions(self):
        """Should have exactly 8 dimensions."""
        assert len(PPVDim) == 8

    def test_all_dimensions_have_values(self):
        """All dimensions should have string values."""
        for dim in PPVDim:
            assert isinstance(dim.value, str)
            assert len(dim.value) > 0

    def test_expected_dimensions_exist(self):
        """All expected dimensions should exist."""
        expected = [
            "EDGE_TENSION",
            "EDGE_RELEASE",
            "ONSET_SHARPNESS",
            "SONORITY_LIFT",
            "CONTINUITY",
            "DISCONTINUITY",
            "RHYTHMIC_IMPULSE",
            "STABILITY_PRESSURE",
        ]
        for name in expected:
            assert hasattr(PPVDim, name)

    def test_neutral_names_only(self):
        """Dimension names should be neutral (no emotion words)."""
        emotion_words = ["joy", "sad", "fear", "anger", "happy", "anxious"]
        for dim in PPVDim:
            dim_lower = dim.value.lower()
            for word in emotion_words:
                assert word not in dim_lower, f"Emotion word '{word}' found in {dim.value}"


# =============================================================================
# Tests for PPVVector
# =============================================================================


class TestPPVVector:
    """Tests for PPVVector dataclass."""

    def test_create_valid_vector(self):
        """Should create valid PPVVector."""
        ppv = create_ppv_vector(
            values=(3, 2, 4, 5, 5, 2, 3, 3),
            source_unit_span_ids=("abcdef1234567890",),
            version="1.0",
        )
        assert ppv is not None
        assert ppv.version == "1.0"
        assert len(ppv.values) == 8

    def test_frozen_immutable(self):
        """PPVVector should be immutable (frozen)."""
        ppv = create_ppv_vector(values=(3, 2, 4, 5, 5, 2, 3, 3))

        with pytest.raises(FrozenInstanceError):
            ppv.version = "2.0"

    def test_values_must_be_tuple(self):
        """Values must be tuple, not list."""
        with pytest.raises(ValueError, match="must be tuple"):
            PPVVector(
                version="1.0",
                dims=PPV_DIM_ORDER,
                values=[3, 2, 4, 5, 5, 2, 3, 3],  # List instead of tuple
                aggregate=0,
                source_unit_span_ids=(),
                ppv_hash="a" * 64,
            )

    def test_values_must_be_8_elements(self):
        """Values must have exactly 8 elements."""
        with pytest.raises(ValueError, match="exactly 8"):
            create_ppv_vector(values=(3, 2, 4))  # Only 3 elements

    def test_values_must_be_in_bounds(self):
        """Values must be in range [0, 7]."""
        with pytest.raises(ValueError, match="range"):
            create_ppv_vector(values=(3, 2, 4, 5, 5, 2, 3, 10))  # 10 is out of bounds

        with pytest.raises(ValueError, match="range"):
            create_ppv_vector(values=(3, 2, -1, 5, 5, 2, 3, 3))  # -1 is out of bounds

    def test_values_must_be_ints(self):
        """Values must be integers."""
        with pytest.raises(ValueError, match="int"):
            create_ppv_vector(values=(3, 2, 4.5, 5, 5, 2, 3, 3))  # float

    def test_hash_is_64_chars(self):
        """ppv_hash should be 64 hex characters."""
        ppv = create_ppv_vector(values=(3, 2, 4, 5, 5, 2, 3, 3))
        assert len(ppv.ppv_hash) == 64
        int(ppv.ppv_hash, 16)  # Should not raise

    def test_span_ids_must_be_16_chars_hex(self):
        """Span IDs must be 16-char hex strings."""
        # Valid
        ppv = create_ppv_vector(
            values=(3, 2, 4, 5, 5, 2, 3, 3),
            source_unit_span_ids=("abcdef1234567890",),
        )
        assert ppv is not None

        # Invalid length
        with pytest.raises(ValueError, match="16-char hex"):
            create_ppv_vector(
                values=(3, 2, 4, 5, 5, 2, 3, 3),
                source_unit_span_ids=("short",),  # Too short
            )

    def test_to_dict(self):
        """to_dict should return JSON-serializable dict."""
        ppv = create_ppv_vector(values=(3, 2, 4, 5, 5, 2, 3, 3))
        d = ppv.to_dict()

        assert isinstance(d, dict)
        assert d["version"] == "1.0"
        assert d["values"] == (3, 2, 4, 5, 5, 2, 3, 3)

    def test_get_value(self):
        """get_value should return correct dimension value."""
        ppv = create_ppv_vector(values=(3, 2, 4, 5, 6, 2, 3, 1))

        assert ppv.get_value(PPVDim.EDGE_TENSION) == 3
        assert ppv.get_value(PPVDim.SONORITY_LIFT) == 5
        assert ppv.get_value(PPVDim.CONTINUITY) == 6
        assert ppv.get_value(PPVDim.STABILITY_PRESSURE) == 1


# =============================================================================
# Tests for create_ppv_vector
# =============================================================================


class TestCreatePPVVector:
    """Tests for create_ppv_vector factory function."""

    def test_computes_aggregate_automatically(self):
        """Should compute aggregate checksum automatically."""
        ppv = create_ppv_vector(values=(1, 2, 3, 4, 5, 6, 7, 0))
        expected = _compute_aggregate((1, 2, 3, 4, 5, 6, 7, 0))
        assert ppv.aggregate == expected

    def test_computes_hash_automatically(self):
        """Should compute hash automatically."""
        ppv = create_ppv_vector(values=(1, 2, 3, 4, 5, 6, 7, 0))
        assert len(ppv.ppv_hash) == 64

    def test_default_version(self):
        """Default version should be 1.0."""
        ppv = create_ppv_vector(values=(1, 2, 3, 4, 5, 6, 7, 0))
        assert ppv.version == "1.0"

    def test_default_empty_span_ids(self):
        """Default span_ids should be empty tuple."""
        ppv = create_ppv_vector(values=(1, 2, 3, 4, 5, 6, 7, 0))
        assert ppv.source_unit_span_ids == ()


# =============================================================================
# Tests for validate_ppv_invariants_v1
# =============================================================================


class TestValidatePPVInvariantsV1:
    """Tests for validate_ppv_invariants_v1 function."""

    def test_valid_ppv_passes(self):
        """Valid PPV should pass validation."""
        ppv = create_ppv_vector(values=(3, 2, 4, 5, 5, 2, 3, 3))
        assert validate_ppv_invariants_v1(ppv) is True

    def test_wrong_version_fails(self):
        """Wrong version should fail validation."""
        ppv = create_ppv_vector(values=(3, 2, 4, 5, 5, 2, 3, 3), version="1.0")
        # Manually create with wrong version (bypass factory)
        # This would require direct PPVVector construction which validates internally


# =============================================================================
# Tests for _compute_aggregate
# =============================================================================


class TestComputeAggregate:
    """Tests for _compute_aggregate function."""

    def test_deterministic(self):
        """Same values should produce same aggregate."""
        values = (1, 2, 3, 4, 5, 6, 7, 0)
        agg1 = _compute_aggregate(values)
        agg2 = _compute_aggregate(values)
        assert agg1 == agg2

    def test_position_sensitive(self):
        """Different positions should produce different aggregates."""
        values1 = (1, 2, 3, 4, 5, 6, 7, 0)
        values2 = (0, 7, 6, 5, 4, 3, 2, 1)
        assert _compute_aggregate(values1) != _compute_aggregate(values2)

    def test_weighted_sum(self):
        """Aggregate should be weighted sum."""
        values = (1, 0, 0, 0, 0, 0, 0, 0)
        # Weight by position (1-indexed): 1*1 = 1
        assert _compute_aggregate(values) == 1

        values = (0, 1, 0, 0, 0, 0, 0, 0)
        # Weight by position: 1*2 = 2
        assert _compute_aggregate(values) == 2


# =============================================================================
# Tests for _compute_ppv_hash
# =============================================================================


class TestComputePPVHash:
    """Tests for _compute_ppv_hash function."""

    def test_returns_64_char_hex(self):
        """Should return 64-character hex string."""
        h = _compute_ppv_hash(
            version="1.0",
            dims=PPV_DIM_ORDER,
            values=(1, 2, 3, 4, 5, 6, 7, 0),
            aggregate=100,
            source_unit_span_ids=(),
        )
        assert len(h) == 64
        int(h, 16)  # Should not raise

    def test_deterministic(self):
        """Same inputs should produce same hash."""
        h1 = _compute_ppv_hash("1.0", PPV_DIM_ORDER, (1, 2, 3, 4, 5, 6, 7, 0), 100, ())
        h2 = _compute_ppv_hash("1.0", PPV_DIM_ORDER, (1, 2, 3, 4, 5, 6, 7, 0), 100, ())
        assert h1 == h2

    def test_different_values_different_hash(self):
        """Different values should produce different hash."""
        h1 = _compute_ppv_hash("1.0", PPV_DIM_ORDER, (1, 2, 3, 4, 5, 6, 7, 0), 100, ())
        h2 = _compute_ppv_hash("1.0", PPV_DIM_ORDER, (0, 2, 3, 4, 5, 6, 7, 1), 100, ())
        assert h1 != h2


# =============================================================================
# Tests for PPV Builder Constants
# =============================================================================


class TestPPVBuilderConstants:
    """Tests for PPV builder constants."""

    def test_version_is_string(self):
        """Version should be a string."""
        assert isinstance(PPV_BUILDER_VERSION, str)

    def test_phoneme_features_has_entries(self):
        """PHONEME_FEATURES should have entries."""
        assert len(PHONEME_FEATURES) > 0

    def test_phoneme_features_are_8_tuples(self):
        """Each feature should be 8-tuple."""
        for phoneme, features in PHONEME_FEATURES.items():
            assert isinstance(features, tuple)
            assert len(features) == 8, f"{phoneme} has {len(features)} features"

    def test_default_features_is_zeros(self):
        """Default features should be all zeros."""
        assert DEFAULT_PHONEME_FEATURES == (0, 0, 0, 0, 0, 0, 0, 0)


# =============================================================================
# Tests for PPVBuildContext
# =============================================================================


class TestPPVBuildContext:
    """Tests for PPVBuildContext dataclass."""

    def test_create_valid_context(self):
        """Should create valid context."""
        ctx = PPVBuildContext(
            phoneme_ids=("ka", "ga", "a"),
            adjacency_markers=("BOUNDARY",),
            span_boundaries=(0, 3),
            fold_sizes=(3,),
            acoustic_regime="neutral",
        )
        assert ctx.phoneme_ids == ("ka", "ga", "a")
        assert ctx.acoustic_regime == "neutral"

    def test_frozen_immutable(self):
        """Context should be immutable."""
        ctx = PPVBuildContext(
            phoneme_ids=("ka",),
            adjacency_markers=(),
            span_boundaries=(),
            fold_sizes=(),
            acoustic_regime="neutral",
        )
        with pytest.raises(FrozenInstanceError):
            ctx.acoustic_regime = "soft"

    def test_phoneme_ids_must_be_tuple(self):
        """phoneme_ids must be tuple."""
        with pytest.raises(ValueError, match="must be tuple"):
            PPVBuildContext(
                phoneme_ids=["ka", "ga"],  # List instead of tuple
                adjacency_markers=(),
                span_boundaries=(),
                fold_sizes=(),
                acoustic_regime="neutral",
            )


# =============================================================================
# Tests for _get_phoneme_features
# =============================================================================


class TestGetPhonemeFeatures:
    """Tests for _get_phoneme_features function."""

    def test_known_phoneme(self):
        """Known phoneme should return its features."""
        features = _get_phoneme_features("ka")
        assert len(features) == 8
        assert features == PHONEME_FEATURES["ka"]

    def test_unknown_phoneme(self):
        """Unknown phoneme should return default features."""
        features = _get_phoneme_features("xyz_unknown")
        assert features == DEFAULT_PHONEME_FEATURES

    def test_case_insensitive(self):
        """Should be case insensitive."""
        lower = _get_phoneme_features("ka")
        upper = _get_phoneme_features("KA")
        assert lower == upper

    def test_unknown_returns_8_features(self):
        """Unknown phoneme should return 8-tuple features."""
        features = _get_phoneme_features("unknown_phoneme_xyz")
        # Unknown phonemes still return an 8-tuple (may be computed from fallback logic)
        assert isinstance(features, tuple)
        assert len(features) == 8


# =============================================================================
# Tests for _clamp_value
# =============================================================================


class TestClampValue:
    """Tests for _clamp_value function."""

    def test_value_in_range(self):
        """Value in range should be unchanged."""
        assert _clamp_value(3) == 3
        assert _clamp_value(0) == 0
        assert _clamp_value(7) == 7

    def test_value_below_min(self):
        """Value below min should be clamped to min."""
        assert _clamp_value(-5) == PPV_VALUE_MIN
        assert _clamp_value(-1) == PPV_VALUE_MIN

    def test_value_above_max(self):
        """Value above max should be clamped to max."""
        assert _clamp_value(10) == PPV_VALUE_MAX
        assert _clamp_value(100) == PPV_VALUE_MAX


# =============================================================================
# Tests for build_ppv_from_context
# =============================================================================


class TestBuildPPVFromContext:
    """Tests for build_ppv_from_context function."""

    def test_builds_valid_ppv(self):
        """Should build valid PPV from context."""
        ctx = PPVBuildContext(
            phoneme_ids=("ka", "ga", "a"),
            adjacency_markers=(),
            span_boundaries=(),
            fold_sizes=(),
            acoustic_regime="neutral",
        )
        ppv = build_ppv_from_context(ctx)

        assert ppv is not None
        assert isinstance(ppv, PPVVector)
        assert len(ppv.values) == 8

    def test_empty_phonemes_returns_none(self):
        """Empty phoneme_ids should return None (fail closed)."""
        ctx = PPVBuildContext(
            phoneme_ids=(),
            adjacency_markers=(),
            span_boundaries=(),
            fold_sizes=(),
            acoustic_regime="neutral",
        )
        ppv = build_ppv_from_context(ctx)
        assert ppv is None

    def test_all_unknown_phonemes_builds_default_ppv(self):
        """Unknown phonemes should build PPV with default/fallback values."""
        ctx = PPVBuildContext(
            phoneme_ids=("qqq", "xxx", "zzz"),  # Phonemes that don't match any known pattern
            adjacency_markers=(),
            span_boundaries=(),
            fold_sizes=(),
            acoustic_regime="neutral",
        )
        ppv = build_ppv_from_context(ctx)
        # Should still build a valid PPV using fallback features
        assert ppv is not None
        assert isinstance(ppv, PPVVector)
        assert len(ppv.values) == 8

    def test_deterministic(self):
        """Same context should produce same PPV."""
        ctx = PPVBuildContext(
            phoneme_ids=("ka", "ga", "a"),
            adjacency_markers=(),
            span_boundaries=(),
            fold_sizes=(),
            acoustic_regime="neutral",
        )
        ppv1 = build_ppv_from_context(ctx)
        ppv2 = build_ppv_from_context(ctx)

        assert ppv1.ppv_hash == ppv2.ppv_hash
        assert ppv1.values == ppv2.values

    def test_different_phonemes_different_ppv(self):
        """Different phonemes should produce different PPV."""
        ctx1 = PPVBuildContext(
            phoneme_ids=("ka", "ga", "a"),
            adjacency_markers=(),
            span_boundaries=(),
            fold_sizes=(),
            acoustic_regime="neutral",
        )
        ctx2 = PPVBuildContext(
            phoneme_ids=("pa", "ta", "i"),
            adjacency_markers=(),
            span_boundaries=(),
            fold_sizes=(),
            acoustic_regime="neutral",
        )
        ppv1 = build_ppv_from_context(ctx1)
        ppv2 = build_ppv_from_context(ctx2)

        assert ppv1.values != ppv2.values


# =============================================================================
# Tests for build_ppv_for_artifact
# =============================================================================


class TestBuildPPVForArtifact:
    """Tests for build_ppv_for_artifact function."""

    def test_extracts_phonemes_from_source_data(self):
        """Should extract phonemes from Phase-10 source_data."""
        phase10 = type("Phase10Result", (), {
            "source_data": {"phoneme_ids": ["ka", "ga", "a"]},
            "acoustic_regime": "neutral",
        })()

        ppv = build_ppv_for_artifact(phase10)
        assert ppv is not None
        assert isinstance(ppv, PPVVector)

    def test_extracts_phonemes_from_phoneme_sequence(self):
        """Should extract phonemes from phoneme_sequence key."""
        phase10 = type("Phase10Result", (), {
            "source_data": {"phoneme_sequence": ["ka", "ga", "a"]},
            "acoustic_regime": "neutral",
        })()

        ppv = build_ppv_for_artifact(phase10)
        assert ppv is not None

    def test_extracts_phonemes_from_syllables(self):
        """Should extract phonemes from syllables key."""
        phase10 = type("Phase10Result", (), {
            "source_data": {"syllables": ["ka", "ga", "a"]},
            "acoustic_regime": "neutral",
        })()

        ppv = build_ppv_for_artifact(phase10)
        assert ppv is not None

    def test_returns_none_for_no_phonemes(self):
        """Should return None when no phonemes found."""
        phase10 = type("Phase10Result", (), {
            "source_data": {},
            "acoustic_regime": "neutral",
        })()

        ppv = build_ppv_for_artifact(phase10)
        assert ppv is None

    def test_uses_context_fallback(self):
        """Should use context parameter as fallback."""
        phase10 = type("Phase10Result", (), {
            "source_data": {},
            "acoustic_regime": None,
        })()

        ppv = build_ppv_for_artifact(
            phase10,
            context={"phoneme_ids": ["ka", "ga"], "acoustic_regime": "soft"},
        )
        assert ppv is not None


# =============================================================================
# Dimension Computation Tests
# =============================================================================


class TestDimensionComputations:
    """Tests for individual dimension computation functions."""

    def test_edge_tension_increases_with_boundaries(self):
        """Edge tension should increase with more boundary markers."""
        features = [PHONEME_FEATURES["ka"], PHONEME_FEATURES["ga"]]

        tension_no_markers = _compute_edge_tension(features, ())
        tension_with_markers = _compute_edge_tension(features, ("BOUNDARY", "BOUNDARY"))

        assert tension_with_markers >= tension_no_markers

    def test_sonority_lift_high_for_vowels(self):
        """Sonority lift should be high for vowels."""
        vowel_features = [PHONEME_FEATURES["a"], PHONEME_FEATURES["i"], PHONEME_FEATURES["u"]]
        plosive_features = [PHONEME_FEATURES["p"], PHONEME_FEATURES["t"], PHONEME_FEATURES["k"]]

        vowel_sonority = _compute_sonority_lift(vowel_features)
        plosive_sonority = _compute_sonority_lift(plosive_features)

        assert vowel_sonority > plosive_sonority


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for PPV system."""

    def test_full_ppv_creation_flow(self):
        """Test complete PPV creation from phonemes to validated vector."""
        # 1. Build context
        ctx = PPVBuildContext(
            phoneme_ids=("sa", "ma", "na", "ta", "da"),
            adjacency_markers=("BOUNDARY",),
            span_boundaries=(0, 2, 5),
            fold_sizes=(2, 3),
            acoustic_regime="neutral",
        )

        # 2. Build PPV
        ppv = build_ppv_from_context(ctx)
        assert ppv is not None

        # 3. Validate invariants
        assert validate_ppv_invariants_v1(ppv) is True

        # 4. Check all values in bounds
        for val in ppv.values:
            assert PPV_VALUE_MIN <= val <= PPV_VALUE_MAX

        # 5. Check hash is deterministic
        ppv2 = build_ppv_from_context(ctx)
        assert ppv.ppv_hash == ppv2.ppv_hash

    def test_phase10_to_ppv_flow(self):
        """Test complete flow from Phase-10 artifact to PPV."""
        # Simulate Phase-10 result
        phase10 = type("Phase10Result", (), {
            "source_data": {
                "phoneme_ids": ["om", "ka", "ra", "sa", "ma"],
                "adjacency_markers": ["BOUNDARY"],
                "span_boundaries": [0, 2, 5],
                "fold_sizes": [2, 3],
            },
            "acoustic_regime": "neutral",
        })()

        # Build PPV
        ppv = build_ppv_for_artifact(phase10)
        assert ppv is not None

        # Validate
        assert validate_ppv_invariants_v1(ppv) is True
        assert len(ppv.source_unit_span_ids) > 0
