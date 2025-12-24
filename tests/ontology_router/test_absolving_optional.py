"""
Tests for ABSOLVING Layer Optionality
=====================================

Verifies that ABSOLVING is never applied unless explicitly requested.
ABSOLVING is a gated layer that requires opt-in.
"""

import pytest

from symbolu.ontology.contracts.projection_contract import (
    ProjectionRequest,
    ProjectionRequestOptions,
)
from symbolu.ontology.layers.ontology_layer import (
    GATED_LAYERS,
    OntologicalLayer,
)
from symbolu.ontology.router.layer_router import (
    OntologicalLayerRouter,
    route_projection,
)
from symbolu.ontology.router.phase_layer_map import (
    PHASE_TO_LAYERS,
    get_layers_for_phase,
)


class TestAbsolvingGated:
    """Tests that ABSOLVING is properly gated."""

    def test_absolving_is_gated_layer(self) -> None:
        """ABSOLVING is in the GATED_LAYERS set."""
        assert OntologicalLayer.ABSOLVING in GATED_LAYERS

    def test_phase_9_includes_absolving_in_mapping(self) -> None:
        """Phase 9 includes ABSOLVING in the raw mapping."""
        layers = PHASE_TO_LAYERS["9"]
        assert OntologicalLayer.ABSOLVING in layers

    def test_get_layers_excludes_absolving_by_default(self) -> None:
        """get_layers_for_phase excludes ABSOLVING by default."""
        layers = get_layers_for_phase("9")
        assert OntologicalLayer.ABSOLVING not in layers

    def test_get_layers_includes_absolving_when_requested(self) -> None:
        """get_layers_for_phase includes ABSOLVING when include_gated=True."""
        layers = get_layers_for_phase("9", include_gated=True)
        assert OntologicalLayer.ABSOLVING in layers


class TestRouterAbsolvingBehavior:
    """Tests router behavior with ABSOLVING layer."""

    @pytest.fixture
    def router(self) -> OntologicalLayerRouter:
        """Create a router instance."""
        return OntologicalLayerRouter()

    def test_router_excludes_absolving_by_default(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Router excludes ABSOLVING by default for Phase 9."""
        request = ProjectionRequest(
            phase_id="9",
            artifact_ref=None,
            options=ProjectionRequestOptions(include_gated_layers=False),
        )

        response = router.project(request)

        assert response.eligible is True
        assert OntologicalLayer.ABSOLVING not in response.layers

    def test_router_includes_absolving_when_requested(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Router includes ABSOLVING when include_gated_layers=True."""
        request = ProjectionRequest(
            phase_id="9",
            artifact_ref=None,
            options=ProjectionRequestOptions(include_gated_layers=True),
        )

        response = router.project(request)

        assert response.eligible is True
        assert OntologicalLayer.ABSOLVING in response.layers

    def test_default_options_exclude_absolving(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Default ProjectionRequestOptions exclude gated layers."""
        request = ProjectionRequest(
            phase_id="9",
            artifact_ref=None,
            # Using default options
        )

        response = router.project(request)

        assert OntologicalLayer.ABSOLVING not in response.layers


class TestAbsolvingNeverUnexpected:
    """Tests that ABSOLVING never appears unexpectedly."""

    def test_absolving_not_in_other_phases_default(self) -> None:
        """ABSOLVING does not appear for phases other than 9."""
        other_phases = ["1b", "2", "3", "4", "5", "6", "7", "8"]

        for phase_id in other_phases:
            request = ProjectionRequest(
                phase_id=phase_id,
                artifact_ref=None,
            )
            response = route_projection(request)
            assert OntologicalLayer.ABSOLVING not in response.layers

    def test_absolving_not_in_other_phases_with_gated(self) -> None:
        """ABSOLVING does not appear for phases other than 9, even with gated=True."""
        other_phases = ["1b", "2", "3", "4", "5", "6", "7", "8"]

        for phase_id in other_phases:
            request = ProjectionRequest(
                phase_id=phase_id,
                artifact_ref=None,
                options=ProjectionRequestOptions(include_gated_layers=True),
            )
            response = route_projection(request)
            assert OntologicalLayer.ABSOLVING not in response.layers

    def test_100_runs_never_includes_absolving_by_default(self) -> None:
        """Over 100 runs, ABSOLVING never appears when not requested."""
        request = ProjectionRequest(
            phase_id="9",
            artifact_ref={"data": "test"},
            options=ProjectionRequestOptions(include_gated_layers=False),
        )

        for _ in range(100):
            response = route_projection(request)
            assert OntologicalLayer.ABSOLVING not in response.layers

    def test_100_runs_always_includes_absolving_when_requested(self) -> None:
        """Over 100 runs, ABSOLVING always appears when requested."""
        request = ProjectionRequest(
            phase_id="9",
            artifact_ref={"data": "test"},
            options=ProjectionRequestOptions(include_gated_layers=True),
        )

        for _ in range(100):
            response = route_projection(request)
            assert OntologicalLayer.ABSOLVING in response.layers


class TestLedgerSpansWithAbsolving:
    """Tests ledger span generation with/without ABSOLVING."""

    def test_fewer_spans_without_absolving(self) -> None:
        """Without ABSOLVING, fewer ledger spans are generated."""
        options_without = ProjectionRequestOptions(
            include_gated_layers=False,
            include_ledger_spans=True,
        )
        options_with = ProjectionRequestOptions(
            include_gated_layers=True,
            include_ledger_spans=True,
        )

        request_without = ProjectionRequest(
            phase_id="9",
            artifact_ref={"test": "data"},
            options=options_without,
        )
        request_with = ProjectionRequest(
            phase_id="9",
            artifact_ref={"test": "data"},
            options=options_with,
        )

        response_without = route_projection(request_without)
        response_with = route_projection(request_with)

        # With ABSOLVING, there should be one more span
        assert len(response_with.ledger_spans) == len(response_without.ledger_spans) + 1
