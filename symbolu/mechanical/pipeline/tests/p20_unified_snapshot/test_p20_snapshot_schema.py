"""
Test Suite: P20 Unified Cognitive Snapshot Schema

Group A - Structural Tests:
    - Snapshot immutability
    - Field presence
    - Correct propagation of None values

This test file validates the schema and data structures for Phase 20.
"""

import pytest
from datetime import datetime, timezone
from dataclasses import FrozenInstanceError

from symbolu.mechanical.pipeline.p20_snapshot.p20_unified_snapshot_schema import (
    P20_VERSION,
    UnifiedCognitiveSnapshot,
    create_snapshot,
)


class TestSnapshotImmutability:
    """Verify that UnifiedCognitiveSnapshot is truly immutable."""

    def test_frozen_dataclass(self):
        """Test that snapshot is a frozen dataclass."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert hasattr(snapshot, "__dataclass_fields__")

    def test_cannot_modify_timestamp(self):
        """Test that timestamp cannot be modified after creation."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        with pytest.raises(FrozenInstanceError):
            snapshot.timestamp = datetime.now(timezone.utc)

    def test_cannot_modify_run_id(self):
        """Test that run_id cannot be modified after creation."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        with pytest.raises(FrozenInstanceError):
            snapshot.run_id = "new-id"

    def test_cannot_modify_coherence_v3(self):
        """Test that coherence_v3 cannot be modified after creation."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
            coherence_v3=0.85,
        )
        with pytest.raises(FrozenInstanceError):
            snapshot.coherence_v3 = 0.50

    def test_cannot_modify_drift_fusion_index(self):
        """Test that drift_fusion_index cannot be modified after creation."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
            drift_fusion_index=0.35,
        )
        with pytest.raises(FrozenInstanceError):
            snapshot.drift_fusion_index = 0.75

    def test_cannot_modify_drift_risk_band(self):
        """Test that drift_risk_band cannot be modified after creation."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
            drift_risk_band="low",
        )
        with pytest.raises(FrozenInstanceError):
            snapshot.drift_risk_band = "high"

    def test_cannot_modify_drift_pattern_tags(self):
        """Test that drift_pattern_tags cannot be modified after creation."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
            drift_pattern_tags=("semantic_drift",),
        )
        with pytest.raises(FrozenInstanceError):
            snapshot.drift_pattern_tags = ("new_tag",)

    def test_drift_pattern_tags_is_tuple(self):
        """Test that drift_pattern_tags is stored as an immutable tuple."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
            drift_pattern_tags=["semantic_drift", "cognitive_drift"],
        )
        assert isinstance(snapshot.drift_pattern_tags, tuple)
        assert snapshot.drift_pattern_tags == ("semantic_drift", "cognitive_drift")

    def test_active_domains_is_tuple(self):
        """Test that active_domains is stored as an immutable tuple."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
            active_domains=["therapy", "finance"],
        )
        assert isinstance(snapshot.active_domains, tuple)
        assert snapshot.active_domains == ("therapy", "finance")


class TestFieldPresence:
    """Verify all required fields are present in the snapshot."""

    def test_has_timestamp(self):
        """Test that snapshot has timestamp field."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert hasattr(snapshot, "timestamp")
        assert snapshot.timestamp is not None

    def test_has_run_id(self):
        """Test that snapshot has run_id field."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert hasattr(snapshot, "run_id")
        assert snapshot.run_id == "test-123"

    def test_has_coherence_fields(self):
        """Test that snapshot has coherence fields."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert hasattr(snapshot, "coherence_v3")
        assert hasattr(snapshot, "coherence_quality")

    def test_has_entropy_fields(self):
        """Test that snapshot has entropy fields."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert hasattr(snapshot, "temporal_entropy_diff")
        assert hasattr(snapshot, "temporal_entropy_volatility")

    def test_has_drift_fields(self):
        """Test that snapshot has drift fields."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert hasattr(snapshot, "drift_fusion_index")
        assert hasattr(snapshot, "drift_risk_band")
        assert hasattr(snapshot, "drift_pattern_tags")

    def test_has_integrity_harmony_fields(self):
        """Test that snapshot has integrity and harmony fields."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert hasattr(snapshot, "semantic_integrity")
        assert hasattr(snapshot, "symbolic_harmony")

    def test_has_domain_activation_fields(self):
        """Test that snapshot has domain and activation fields."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert hasattr(snapshot, "active_domains")
        assert hasattr(snapshot, "phase_completion_flags")


class TestNonePropagation:
    """Verify that missing values are correctly set to None."""

    def test_coherence_v3_defaults_to_none(self):
        """Test that coherence_v3 defaults to None."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.coherence_v3 is None

    def test_coherence_quality_defaults_to_none(self):
        """Test that coherence_quality defaults to None."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.coherence_quality is None

    def test_temporal_entropy_diff_defaults_to_none(self):
        """Test that temporal_entropy_diff defaults to None."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.temporal_entropy_diff is None

    def test_temporal_entropy_volatility_defaults_to_none(self):
        """Test that temporal_entropy_volatility defaults to None."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.temporal_entropy_volatility is None

    def test_drift_fusion_index_defaults_to_none(self):
        """Test that drift_fusion_index defaults to None."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.drift_fusion_index is None

    def test_drift_risk_band_defaults_to_none(self):
        """Test that drift_risk_band defaults to None."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.drift_risk_band is None

    def test_drift_pattern_tags_defaults_to_empty_tuple(self):
        """Test that drift_pattern_tags defaults to empty tuple."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.drift_pattern_tags == ()

    def test_semantic_integrity_defaults_to_none(self):
        """Test that semantic_integrity defaults to None."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.semantic_integrity is None

    def test_symbolic_harmony_defaults_to_none(self):
        """Test that symbolic_harmony defaults to None."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.symbolic_harmony is None

    def test_active_domains_defaults_to_empty_tuple(self):
        """Test that active_domains defaults to empty tuple."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.active_domains == ()

    def test_phase_completion_flags_defaults_to_empty_dict(self):
        """Test that phase_completion_flags defaults to empty dict."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.phase_completion_flags == {}


class TestToDict:
    """Test to_dict serialization."""

    def test_to_dict_returns_dict(self):
        """Test that to_dict returns a dictionary."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        result = snapshot.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_contains_all_fields(self):
        """Test that to_dict contains all expected fields."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        result = snapshot.to_dict()
        assert "timestamp" in result
        assert "run_id" in result
        assert "coherence_v3" in result
        assert "coherence_quality" in result
        assert "temporal_entropy_diff" in result
        assert "temporal_entropy_volatility" in result
        assert "drift_fusion_index" in result
        assert "drift_risk_band" in result
        assert "drift_pattern_tags" in result
        assert "semantic_integrity" in result
        assert "symbolic_harmony" in result
        assert "active_domains" in result
        assert "phase_completion_flags" in result

    def test_to_dict_timestamp_is_iso_string(self):
        """Test that timestamp is serialized as ISO format string."""
        ts = datetime.now(timezone.utc)
        snapshot = create_snapshot(
            timestamp=ts,
            run_id="test-123",
        )
        result = snapshot.to_dict()
        assert result["timestamp"] == ts.isoformat()

    def test_to_dict_tuples_become_lists(self):
        """Test that tuples are converted to lists in to_dict."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
            drift_pattern_tags=("tag1", "tag2"),
            active_domains=("domain1",),
        )
        result = snapshot.to_dict()
        assert isinstance(result["drift_pattern_tags"], list)
        assert isinstance(result["active_domains"], list)
        assert result["drift_pattern_tags"] == ["tag1", "tag2"]
        assert result["active_domains"] == ["domain1"]


class TestConvenienceMethods:
    """Test convenience methods on the snapshot."""

    def test_has_coherence_true(self):
        """Test has_coherence returns True when coherence_v3 is present."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
            coherence_v3=0.85,
        )
        assert snapshot.has_coherence() is True

    def test_has_coherence_false(self):
        """Test has_coherence returns False when coherence_v3 is None."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.has_coherence() is False

    def test_has_entropy_true(self):
        """Test has_entropy returns True when temporal_entropy_diff is present."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
            temporal_entropy_diff=0.5,
        )
        assert snapshot.has_entropy() is True

    def test_has_entropy_false(self):
        """Test has_entropy returns False when temporal_entropy_diff is None."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.has_entropy() is False

    def test_has_drift_true(self):
        """Test has_drift returns True when drift_fusion_index is present."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
            drift_fusion_index=0.35,
        )
        assert snapshot.has_drift() is True

    def test_has_drift_false(self):
        """Test has_drift returns False when drift_fusion_index is None."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.has_drift() is False

    def test_has_integrity_true(self):
        """Test has_integrity returns True when semantic_integrity is present."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
            semantic_integrity=0.9,
        )
        assert snapshot.has_integrity() is True

    def test_has_integrity_false(self):
        """Test has_integrity returns False when semantic_integrity is None."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.has_integrity() is False

    def test_has_harmony_true(self):
        """Test has_harmony returns True when symbolic_harmony is present."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
            symbolic_harmony=0.75,
        )
        assert snapshot.has_harmony() is True

    def test_has_harmony_false(self):
        """Test has_harmony returns False when symbolic_harmony is None."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.has_harmony() is False

    def test_phase_count_zero(self):
        """Test phase_count returns 0 when no phases are complete."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
        )
        assert snapshot.phase_count() == 0

    def test_phase_count_with_flags(self):
        """Test phase_count returns correct count when phases are complete."""
        snapshot = create_snapshot(
            timestamp=datetime.now(timezone.utc),
            run_id="test-123",
            phase_completion_flags={
                "phase_minus_one": True,
                "phase_zero": True,
                "phase_one": True,
                "p6": False,
                "p7": False,
            },
        )
        assert snapshot.phase_count() == 3


class TestVersioning:
    """Test version-related functionality."""

    def test_p20_version_exists(self):
        """Test that P20_VERSION is defined."""
        assert P20_VERSION is not None
        assert isinstance(P20_VERSION, str)

    def test_p20_version_format(self):
        """Test that P20_VERSION follows semver format."""
        parts = P20_VERSION.split(".")
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()


class TestTypeValidation:
    """Test type validation in __post_init__."""

    def test_timestamp_must_be_datetime(self):
        """Test that timestamp must be a datetime object."""
        with pytest.raises(TypeError):
            UnifiedCognitiveSnapshot(
                timestamp="not-a-datetime",
                run_id="test-123",
            )

    def test_run_id_must_be_string(self):
        """Test that run_id must be a string."""
        with pytest.raises(TypeError):
            UnifiedCognitiveSnapshot(
                timestamp=datetime.now(timezone.utc),
                run_id=123,
            )

    def test_phase_completion_flags_must_be_dict(self):
        """Test that phase_completion_flags must be a dict."""
        with pytest.raises(TypeError):
            UnifiedCognitiveSnapshot(
                timestamp=datetime.now(timezone.utc),
                run_id="test-123",
                phase_completion_flags=["not", "a", "dict"],
            )
