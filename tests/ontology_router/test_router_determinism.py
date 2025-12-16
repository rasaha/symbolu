"""
Tests for Router Determinism
============================

Verifies that the router produces identical output for identical input.
This is a core invariant: same input → identical output (100 runs).
"""

import pytest

from symbolu.ontology.contracts.projection_contract import (
    ProjectionRequest,
    ProjectionRequestOptions,
)
from symbolu.ontology.layers.ontology_layer import OntologicalLayer
from symbolu.ontology.router.layer_router import (
    OntologicalLayerRouter,
    route_projection,
)


class TestRouterDeterminism:
    """Tests that the router is fully deterministic."""

    @pytest.fixture
    def router(self) -> OntologicalLayerRouter:
        """Create a router instance."""
        return OntologicalLayerRouter()

    @pytest.fixture
    def sample_request(self) -> ProjectionRequest:
        """Create a sample projection request."""
        return ProjectionRequest(
            phase_id="3",
            artifact_ref={"key": "value", "count": 42},
        )

    def test_same_output_100_runs(
        self,
        router: OntologicalLayerRouter,
        sample_request: ProjectionRequest,
    ) -> None:
        """Same input produces identical output over 100 runs."""
        first_response = router.project(sample_request)

        for i in range(100):
            response = router.project(sample_request)
            assert response.layers == first_response.layers
            assert response.artifacts == first_response.artifacts
            assert response.ledger_spans == first_response.ledger_spans
            assert response.eligible == first_response.eligible

    def test_layer_ordering_deterministic(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Layer ordering is consistent across runs."""
        request = ProjectionRequest(phase_id="6", artifact_ref=None)

        for _ in range(50):
            response = router.project(request)
            # Layers should be in ascending order by value
            values = [layer.value for layer in response.layers]
            assert values == sorted(values)

    def test_ledger_spans_deterministic(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Ledger span IDs are deterministic."""
        request = ProjectionRequest(
            phase_id="5",
            artifact_ref=("tuple", "artifact"),
            options=ProjectionRequestOptions(include_ledger_spans=True),
        )

        first_response = router.project(request)
        assert len(first_response.ledger_spans) > 0

        for _ in range(50):
            response = router.project(request)
            assert response.ledger_spans == first_response.ledger_spans

    def test_different_phases_different_output(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Different phase IDs produce different layer sets."""
        request_3 = ProjectionRequest(phase_id="3", artifact_ref=None)
        request_5 = ProjectionRequest(phase_id="5", artifact_ref=None)

        response_3 = router.project(request_3)
        response_5 = router.project(request_5)

        assert response_3.layers != response_5.layers

    def test_route_projection_function_deterministic(self) -> None:
        """The route_projection convenience function is deterministic."""
        request = ProjectionRequest(
            phase_id="7",
            artifact_ref={"data": [1, 2, 3]},
        )

        first_response = route_projection(request)

        for _ in range(50):
            response = route_projection(request)
            assert response.layers == first_response.layers
            assert response.ledger_spans == first_response.ledger_spans


class TestHashStability:
    """Tests that outputs are hash-stable."""

    def test_ledger_span_hash_format(self) -> None:
        """Ledger spans are 64-character hex hashes."""
        request = ProjectionRequest(
            phase_id="4",
            artifact_ref={"stable": True},
            options=ProjectionRequestOptions(include_ledger_spans=True),
        )

        response = route_projection(request)

        for span_id in response.ledger_spans:
            assert len(span_id) == 64
            assert all(c in "0123456789abcdef" for c in span_id)

    def test_artifact_order_affects_hash(self) -> None:
        """Different artifact order produces different ledger spans."""
        options = ProjectionRequestOptions(include_ledger_spans=True)

        request_a = ProjectionRequest(
            phase_id="3",
            artifact_ref=("a", "b", "c"),
            options=options,
        )
        request_b = ProjectionRequest(
            phase_id="3",
            artifact_ref=("c", "b", "a"),
            options=options,
        )

        response_a = route_projection(request_a)
        response_b = route_projection(request_b)

        # Same layers, different spans
        assert response_a.layers == response_b.layers
        assert response_a.ledger_spans != response_b.ledger_spans


class TestNoRandomness:
    """Tests that no randomness is introduced."""

    def test_no_variation_across_instances(self) -> None:
        """Different router instances produce identical output."""
        request = ProjectionRequest(
            phase_id="8",
            artifact_ref={"test": "data"},
        )

        responses = []
        for _ in range(10):
            router = OntologicalLayerRouter()
            responses.append(router.project(request))

        first = responses[0]
        for response in responses[1:]:
            assert response.layers == first.layers
            assert response.ledger_spans == first.ledger_spans
