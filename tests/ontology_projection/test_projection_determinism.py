"""
Projection Determinism Tests
============================

Verify that projections are fully deterministic:
    - Same snapshot + request => identical response
    - projection_id is consistent
    - repr(response) is byte-identical
"""

import pytest

from symbolu.ontology.projection import (
    FrozenSnapshot,
    InputRef,
    InputRefKind,
    OntologicalLayer,
    ProjectionProfile,
    OutputMode,
    Strictness,
    ProjectionOptions,
    ProjectionRequest,
    run_projection,
    attest_determinism,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_snapshot():
    """Create a sample frozen snapshot for testing."""
    return FrozenSnapshot(
        snapshot_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        payload={"key": "value", "count": 42, "items": [1, 2, 3]},
        content_hash="deadbeefcafebabe1234567890abcdef"
    )


@pytest.fixture
def sample_input_ref():
    """Create a sample input reference."""
    return InputRef(
        kind=InputRefKind.GENERIC,
        object_id="f1e2d3c4b5a69788796a5b4c3d2e1f00"
    )


@pytest.fixture
def sample_options():
    """Create sample projection options."""
    return ProjectionOptions(
        include_ledger=True,
        max_artifacts=100,
        output_mode=OutputMode.NON_TEXTUAL,
        strictness=Strictness.STRICT
    )


# =============================================================================
# THINKING Layer Determinism
# =============================================================================

class TestThinkingLayerDeterminism:
    """Test THINKING layer projection determinism."""

    def test_thinking_determinism_100_runs(self, sample_snapshot, sample_input_ref, sample_options):
        """Run THINKING projection 100 times, assert identical outputs."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.COGNITION,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        responses = []
        for _ in range(100):
            response = run_projection(sample_snapshot, request)
            responses.append(response)

        # All projection_ids should be identical
        first_id = responses[0].projection_id
        for i, r in enumerate(responses[1:], start=1):
            assert r.projection_id == first_id, f"Run {i}: projection_id mismatch"

        # All repr should be identical
        first_repr = repr(responses[0])
        for i, r in enumerate(responses[1:], start=1):
            assert repr(r) == first_repr, f"Run {i}: repr mismatch"

    def test_thinking_attest_determinism(self, sample_snapshot, sample_input_ref, sample_options):
        """Use attest_determinism helper for THINKING layer."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.COGNITION,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        ok, attestation_hash, run_hashes = attest_determinism(sample_snapshot, request, runs=50)

        assert ok, "Determinism attestation failed"
        assert len(attestation_hash) == 32, "Attestation hash should be 32 chars"
        assert len(run_hashes) == 50, "Should have 50 run hashes"
        assert all(h == attestation_hash for h in run_hashes), "All run hashes should match"


# =============================================================================
# META_OBSERVING Layer Determinism
# =============================================================================

class TestMetaObservingLayerDeterminism:
    """Test META_OBSERVING layer projection determinism."""

    def test_meta_observing_determinism_100_runs(self, sample_snapshot, sample_input_ref, sample_options):
        """Run META_OBSERVING projection 100 times, assert identical outputs."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.WITNESSES,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.AUDIT,
            options=sample_options
        )

        responses = []
        for _ in range(100):
            response = run_projection(sample_snapshot, request)
            responses.append(response)

        # All projection_ids should be identical
        first_id = responses[0].projection_id
        for i, r in enumerate(responses[1:], start=1):
            assert r.projection_id == first_id, f"Run {i}: projection_id mismatch"

        # All repr should be identical
        first_repr = repr(responses[0])
        for i, r in enumerate(responses[1:], start=1):
            assert repr(r) == first_repr, f"Run {i}: repr mismatch"

    def test_meta_observing_attest_determinism(self, sample_snapshot, sample_input_ref, sample_options):
        """Use attest_determinism helper for META_OBSERVING layer."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.WITNESSES,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.AUDIT,
            options=sample_options
        )

        ok, attestation_hash, run_hashes = attest_determinism(sample_snapshot, request, runs=50)

        assert ok, "Determinism attestation failed"
        assert all(h == attestation_hash for h in run_hashes), "All run hashes should match"


# =============================================================================
# UNIFYING Layer Determinism
# =============================================================================

class TestUnifyingLayerDeterminism:
    """Test UNIFYING layer projection determinism."""

    def test_unifying_determinism_100_runs(self, sample_input_ref, sample_options):
        """Run UNIFYING projection 100 times, assert identical outputs."""
        # Use list payload for equivalence testing
        snapshot = FrozenSnapshot(
            snapshot_id="b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6a7",
            payload=[
                {"type": "a", "val": 1},
                {"type": "b", "val": 2},
                {"type": "a", "val": 1},  # Duplicate
                {"type": "c", "val": 3},
                {"type": "b", "val": 2},  # Duplicate
            ],
            content_hash="cafebabe12345678deadbeef90abcdef"
        )

        request = ProjectionRequest(
            snapshot_id=snapshot.snapshot_id,
            layer=OntologicalLayer.UNIFYING,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.MINIMAL,
            options=sample_options
        )

        responses = []
        for _ in range(100):
            response = run_projection(snapshot, request)
            responses.append(response)

        # All projection_ids should be identical
        first_id = responses[0].projection_id
        for i, r in enumerate(responses[1:], start=1):
            assert r.projection_id == first_id, f"Run {i}: projection_id mismatch"

        # All repr should be identical
        first_repr = repr(responses[0])
        for i, r in enumerate(responses[1:], start=1):
            assert repr(r) == first_repr, f"Run {i}: repr mismatch"

    def test_unifying_attest_determinism(self, sample_input_ref, sample_options):
        """Use attest_determinism helper for UNIFYING layer."""
        snapshot = FrozenSnapshot(
            snapshot_id="c3d4e5f6a7b8c9d0e1f2a3b4c5d6a7b8",
            payload=[(1, 2), (3, 4), (1, 2), (5, 6)],
            content_hash="1234567890abcdefdeadbeefcafebabe"
        )

        request = ProjectionRequest(
            snapshot_id=snapshot.snapshot_id,
            layer=OntologicalLayer.UNIFYING,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.MINIMAL,
            options=sample_options
        )

        ok, attestation_hash, run_hashes = attest_determinism(snapshot, request, runs=50)

        assert ok, "Determinism attestation failed"
        assert all(h == attestation_hash for h in run_hashes), "All run hashes should match"


# =============================================================================
# Cross-Layer Determinism
# =============================================================================

class TestCrossLayerDeterminism:
    """Test determinism across different configurations."""

    def test_different_profiles_different_ids(self, sample_snapshot, sample_input_ref, sample_options):
        """Different profiles should produce different projection_ids."""
        request_minimal = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.COGNITION,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.MINIMAL,
            options=sample_options
        )

        request_standard = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.COGNITION,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        resp_minimal = run_projection(sample_snapshot, request_minimal)
        resp_standard = run_projection(sample_snapshot, request_standard)

        # Different profiles should produce different projection_ids
        assert resp_minimal.projection_id != resp_standard.projection_id

    def test_different_layers_different_ids(self, sample_snapshot, sample_input_ref, sample_options):
        """Different layers should produce different projection_ids."""
        request_thinking = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.COGNITION,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        request_meta = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.WITNESSES,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        resp_thinking = run_projection(sample_snapshot, request_thinking)
        resp_meta = run_projection(sample_snapshot, request_meta)

        # Different layers should produce different projection_ids
        assert resp_thinking.projection_id != resp_meta.projection_id

    def test_projection_id_is_32_hex_chars(self, sample_snapshot, sample_input_ref, sample_options):
        """projection_id should always be 32 lowercase hex characters."""
        for layer in [OntologicalLayer.COGNITION, OntologicalLayer.WITNESSES, OntologicalLayer.UNIFYING]:
            request = ProjectionRequest(
                snapshot_id=sample_snapshot.snapshot_id,
                layer=layer,
                input_ref=sample_input_ref,
                projection_profile=ProjectionProfile.STANDARD,
                options=sample_options
            )

            response = run_projection(sample_snapshot, request)

            assert len(response.projection_id) == 32, f"Layer {layer}: projection_id length wrong"
            assert response.projection_id == response.projection_id.lower(), f"Layer {layer}: not lowercase"
            # Verify it's valid hex
            int(response.projection_id, 16)


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
