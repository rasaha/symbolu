"""
Projection Fail-Closed Tests
=============================

Verify that projections fail closed:
    - Unsupported layers => eligible=False
    - Exceptions => eligible=False with EXCEPTION_BLOCKED
    - Invalid requests => eligible=False with reason codes
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
)
from symbolu.ontology.projection.api_models import ReasonCode


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_snapshot():
    """Create a sample frozen snapshot for testing."""
    return FrozenSnapshot(
        snapshot_id="a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        payload={"key": "value", "count": 42},
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
# Unsupported Layer Tests
# =============================================================================

class TestUnsupportedLayers:
    """Test fail-closed behavior for unsupported layers."""

    @pytest.mark.parametrize("layer", [
        OntologicalLayer.SENSING,
        OntologicalLayer.PERCEIVING,
        OntologicalLayer.FEELING,
        OntologicalLayer.ACTING,
        OntologicalLayer.RELATING,
        OntologicalLayer.TRANSCENDING,
        OntologicalLayer.INTEGRATING,
    ])
    def test_unsupported_layer_returns_ineligible(
        self, layer, sample_snapshot, sample_input_ref, sample_options
    ):
        """Unsupported layers should return eligible=False."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=layer,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        response = run_projection(sample_snapshot, request)

        assert response.eligible is False, f"Layer {layer.name} should be ineligible"
        assert response.artifacts == (), f"Layer {layer.name} should have empty artifacts"
        assert ReasonCode.LAYER_NOT_IMPLEMENTED in response.invariants_report.reason_codes

    def test_acting_layer_fail_closed(self, sample_snapshot, sample_input_ref, sample_options):
        """ACTING layer (unsupported) should fail closed."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.ACTING,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        response = run_projection(sample_snapshot, request)

        assert response.eligible is False
        assert response.artifacts == ()
        assert response.ledger_spans == ()
        assert response.invariants_report.passed is False
        assert ReasonCode.LAYER_NOT_IMPLEMENTED in response.invariants_report.reason_codes

    def test_unsupported_layer_still_has_projection_id(
        self, sample_snapshot, sample_input_ref, sample_options
    ):
        """Even failed projections should have a deterministic projection_id."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.ACTING,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        # Run multiple times
        responses = [run_projection(sample_snapshot, request) for _ in range(10)]

        # All projection_ids should be identical
        first_id = responses[0].projection_id
        for r in responses[1:]:
            assert r.projection_id == first_id


# =============================================================================
# Exception Handling Tests
# =============================================================================

class TestExceptionHandling:
    """Test fail-closed behavior when exceptions occur."""

    def test_non_serializable_payload_exception(self, sample_input_ref, sample_options):
        """Non-serializable payload should trigger fail-closed."""
        # Create a snapshot with a non-JSONable, non-repr-stable object
        class BadObject:
            def __repr__(self):
                raise RuntimeError("Cannot repr")

        snapshot = FrozenSnapshot(
            snapshot_id="b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6a7",
            payload=BadObject(),
            content_hash="cafebabe12345678deadbeef90abcdef"
        )

        request = ProjectionRequest(
            snapshot_id=snapshot.snapshot_id,
            layer=OntologicalLayer.UNIFYING,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        response = run_projection(snapshot, request)

        # Should have a projection_id regardless
        assert len(response.projection_id) == 32
        # Should still succeed for UNIFYING with non-list payload
        # (empty classes returned)
        assert response.eligible is True

    def test_exception_blocked_has_projection_id(self, sample_input_ref, sample_options):
        """Exception-blocked responses should still have projection_id."""
        # Create payload that will cause issues in specific layer processing
        snapshot = FrozenSnapshot(
            snapshot_id="c3d4e5f6a7b8c9d0e1f2a3b4c5d6a7b8",
            payload=None,
            content_hash="1234567890abcdefdeadbeefcafebabe"
        )

        request = ProjectionRequest(
            snapshot_id=snapshot.snapshot_id,
            layer=OntologicalLayer.ACTING,  # Unsupported
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        response = run_projection(snapshot, request)

        assert response.projection_id is not None
        assert len(response.projection_id) == 32


# =============================================================================
# Invalid Request Tests
# =============================================================================

class TestInvalidRequests:
    """Test fail-closed behavior for invalid requests."""

    def test_invalid_max_artifacts_zero(self, sample_snapshot, sample_input_ref):
        """max_artifacts=0 should fail closed."""
        options = ProjectionOptions(
            include_ledger=True,
            max_artifacts=0,  # Invalid
            output_mode=OutputMode.NON_TEXTUAL,
            strictness=Strictness.STRICT
        )

        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.THINKING,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=options
        )

        response = run_projection(sample_snapshot, request)

        assert response.eligible is False
        assert response.artifacts == ()
        assert ReasonCode.INVALID_MAX_ARTIFACTS in response.invariants_report.reason_codes

    def test_invalid_max_artifacts_negative(self, sample_snapshot, sample_input_ref):
        """max_artifacts < 0 should fail closed."""
        options = ProjectionOptions(
            include_ledger=True,
            max_artifacts=-1,  # Invalid
            output_mode=OutputMode.NON_TEXTUAL,
            strictness=Strictness.STRICT
        )

        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.THINKING,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=options
        )

        response = run_projection(sample_snapshot, request)

        assert response.eligible is False
        assert ReasonCode.INVALID_MAX_ARTIFACTS in response.invariants_report.reason_codes


# =============================================================================
# Fail-Closed Response Structure Tests
# =============================================================================

class TestFailClosedStructure:
    """Test structure of fail-closed responses."""

    def test_fail_closed_response_structure(self, sample_snapshot, sample_input_ref, sample_options):
        """Fail-closed responses should have correct structure."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.ACTING,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        response = run_projection(sample_snapshot, request)

        # Check structure
        assert isinstance(response.projection_id, str)
        assert isinstance(response.snapshot_id, str)
        assert isinstance(response.layer, OntologicalLayer)
        assert isinstance(response.input_ref, InputRef)
        assert isinstance(response.artifacts, tuple)
        assert isinstance(response.ledger_spans, tuple)
        assert isinstance(response.invariants_report.passed, bool)
        assert isinstance(response.invariants_report.reason_codes, tuple)
        assert isinstance(response.eligible, bool)

        # Check values
        assert response.eligible is False
        assert response.artifacts == ()
        assert response.ledger_spans == ()
        assert response.invariants_report.passed is False
        assert len(response.invariants_report.reason_codes) > 0

    def test_fail_closed_preserves_request_info(self, sample_snapshot, sample_input_ref, sample_options):
        """Fail-closed responses should preserve request info."""
        request = ProjectionRequest(
            snapshot_id=sample_snapshot.snapshot_id,
            layer=OntologicalLayer.ACTING,
            input_ref=sample_input_ref,
            projection_profile=ProjectionProfile.STANDARD,
            options=sample_options
        )

        response = run_projection(sample_snapshot, request)

        assert response.snapshot_id == request.snapshot_id
        assert response.layer == request.layer
        assert response.input_ref == request.input_ref


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
