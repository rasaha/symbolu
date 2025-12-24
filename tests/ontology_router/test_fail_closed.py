"""
Tests for Fail-Closed Behavior
==============================

Verifies that the router fails closed on invalid input.
Invalid phase IDs and malformed requests must result in eligible=False.
"""

import pytest

from symbolu.ontology.contracts.projection_contract import (
    ProjectionReasonCode,
    ProjectionRequest,
    ProjectionRequestOptions,
)
from symbolu.ontology.router.layer_router import (
    OntologicalLayerRouter,
    route_projection,
)


class TestFailClosed:
    """Tests that the router fails closed on invalid input."""

    @pytest.fixture
    def router(self) -> OntologicalLayerRouter:
        """Create a router instance."""
        return OntologicalLayerRouter()

    def test_invalid_phase_id_fails(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Invalid phase ID results in eligible=False."""
        request = ProjectionRequest(
            phase_id="invalid",
            artifact_ref=None,
        )

        response = router.project(request)

        assert response.eligible is False
        assert response.layers == ()
        assert response.artifacts == ()
        assert response.ledger_spans == ()

    def test_empty_phase_id_fails_at_construction(self) -> None:
        """Empty phase ID fails at request construction."""
        with pytest.raises(ValueError) as exc_info:
            ProjectionRequest(phase_id="", artifact_ref=None)
        assert "empty" in str(exc_info.value).lower()

    def test_non_string_phase_id_fails(self) -> None:
        """Non-string phase ID fails at request construction."""
        with pytest.raises(TypeError) as exc_info:
            ProjectionRequest(phase_id=123, artifact_ref=None)  # type: ignore
        assert "string" in str(exc_info.value).lower()

    def test_unknown_phase_number_fails(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Unknown phase numbers (0, 10, 100) fail."""
        for phase_id in ["0", "10", "100", "1a", "1c"]:
            request = ProjectionRequest(
                phase_id=phase_id,
                artifact_ref=None,
            )
            response = router.project(request)
            assert response.eligible is False

    def test_invalid_request_type_fails(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Non-ProjectionRequest input fails."""
        response = router.project({"phase_id": "3"})  # type: ignore

        assert response.eligible is False
        assert "request_type_valid" in response.invariants_report
        assert response.invariants_report["request_type_valid"] is False

    def test_failed_response_has_reason_code(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Failed responses include reason code in invariants report."""
        request = ProjectionRequest(
            phase_id="unknown",
            artifact_ref=None,
        )

        response = router.project(request)

        assert response.eligible is False
        assert ProjectionReasonCode.INVALID_PHASE_ID in response.invariants_report

    def test_no_fallback_behavior(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Router does not provide fallback on invalid input."""
        request = ProjectionRequest(
            phase_id="nonexistent",
            artifact_ref={"data": "should not be processed"},
        )

        response = router.project(request)

        # No fallback - strictly fails
        assert response.eligible is False
        assert response.layers == ()
        assert response.artifacts == ()


class TestInvariantsReport:
    """Tests for the invariants report."""

    def test_success_has_passed_invariants(self) -> None:
        """Successful projections have passed invariants."""
        request = ProjectionRequest(
            phase_id="3",
            artifact_ref=None,
        )

        response = route_projection(request)

        assert response.eligible is True
        assert ProjectionReasonCode.PASSED in response.invariants_report
        assert response.invariants_report[ProjectionReasonCode.PASSED] is True

    def test_success_invariants_all_true(self) -> None:
        """Successful projections have all invariants True."""
        request = ProjectionRequest(
            phase_id="5",
            artifact_ref={"test": "data"},
        )

        response = route_projection(request)

        for key, value in response.invariants_report.items():
            assert value is True, f"Invariant {key} should be True"

    def test_failure_has_false_invariant(self) -> None:
        """Failed projections have at least one False invariant."""
        request = ProjectionRequest(
            phase_id="invalid",
            artifact_ref=None,
        )

        response = route_projection(request)

        assert response.eligible is False
        has_false = any(
            value is False for value in response.invariants_report.values()
        )
        assert has_false, "Failed response should have at least one False invariant"


class TestNoFreeformStrings:
    """Tests that outputs contain no free-form strings."""

    def test_layers_are_enums(self) -> None:
        """All layers in response are OntologicalLayer enums."""
        from symbolu.ontology.layers.ontology_layer import OntologicalLayer

        request = ProjectionRequest(
            phase_id="6",
            artifact_ref=None,
        )

        response = route_projection(request)

        for layer in response.layers:
            assert isinstance(layer, OntologicalLayer)

    def test_ledger_spans_are_hex_hashes(self) -> None:
        """All ledger spans are 64-character hex hashes."""
        request = ProjectionRequest(
            phase_id="7",
            artifact_ref={"data": "test"},
            options=ProjectionRequestOptions(include_ledger_spans=True),
        )

        response = route_projection(request)

        for span_id in response.ledger_spans:
            assert isinstance(span_id, str)
            assert len(span_id) == 64
            assert all(c in "0123456789abcdef" for c in span_id)

    def test_invariant_keys_are_known_codes(self) -> None:
        """Invariant report keys are from known code sets."""
        request = ProjectionRequest(
            phase_id="3",
            artifact_ref=None,
        )

        response = route_projection(request)

        known_keys = {
            ProjectionReasonCode.PASSED,
            ProjectionReasonCode.INVALID_PHASE_ID,
            ProjectionReasonCode.VALIDATION_FAILED,
            "phase_id_valid",
            "layers_resolved",
            "artifacts_immutable",
            "deterministic",
            "request_type_valid",
            "phase_id_lookup",
        }

        for key in response.invariants_report.keys():
            assert key in known_keys, f"Unknown invariant key: {key}"
