"""
Tests for No Mutation Invariant
===============================

Verifies that the router does not mutate artifacts.
Artifacts are opaque and must pass through unchanged.
"""

import copy

import pytest

from symbolu.ontology.contracts.projection_contract import (
    ProjectionRequest,
    ProjectionRequestOptions,
)
from symbolu.ontology.router.layer_router import (
    OntologicalLayerRouter,
    route_projection,
)


class TestNoMutation:
    """Tests that artifacts are not mutated."""

    @pytest.fixture
    def router(self) -> OntologicalLayerRouter:
        """Create a router instance."""
        return OntologicalLayerRouter()

    def test_dict_artifact_not_mutated(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Dictionary artifacts are not mutated."""
        original = {"key": "value", "nested": {"a": 1, "b": 2}}
        original_copy = copy.deepcopy(original)

        request = ProjectionRequest(
            phase_id="3",
            artifact_ref=original,
        )

        router.project(request)

        assert original == original_copy

    def test_list_artifact_not_mutated(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """List artifacts are not mutated."""
        original = [1, 2, {"nested": [3, 4]}, [5, 6]]
        original_copy = copy.deepcopy(original)

        request = ProjectionRequest(
            phase_id="5",
            artifact_ref=original,
        )

        router.project(request)

        assert original == original_copy

    def test_tuple_artifact_not_mutated(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Tuple artifacts are not mutated."""
        original = ("a", "b", ("nested", "tuple"))
        original_copy = copy.deepcopy(original)

        request = ProjectionRequest(
            phase_id="7",
            artifact_ref=original,
        )

        router.project(request)

        assert original == original_copy

    def test_custom_object_not_mutated(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Custom objects are not mutated."""

        class CustomArtifact:
            def __init__(self, value: int) -> None:
                self.value = value
                self.data = {"internal": [1, 2, 3]}

        original = CustomArtifact(42)
        original_value = original.value
        original_data = copy.deepcopy(original.data)

        request = ProjectionRequest(
            phase_id="4",
            artifact_ref=original,
        )

        router.project(request)

        assert original.value == original_value
        assert original.data == original_data

    def test_none_artifact_handled(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """None artifact is handled without error."""
        request = ProjectionRequest(
            phase_id="6",
            artifact_ref=None,
        )

        response = router.project(request)
        assert response.eligible is True
        assert response.artifacts == ()

    def test_response_artifacts_are_immutable(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Response artifacts are returned as a tuple (immutable)."""
        request = ProjectionRequest(
            phase_id="8",
            artifact_ref={"data": "test"},
        )

        response = router.project(request)

        assert isinstance(response.artifacts, tuple)

    def test_request_options_not_mutated(
        self,
        router: OntologicalLayerRouter,
    ) -> None:
        """Request options are not mutated."""
        options = ProjectionRequestOptions(
            include_gated_layers=False,
            include_ledger_spans=True,
        )

        request = ProjectionRequest(
            phase_id="9",
            artifact_ref={"test": "data"},
            options=options,
        )

        router.project(request)

        # Options should be unchanged
        assert options.include_gated_layers is False
        assert options.include_ledger_spans is True


class TestArtifactPassthrough:
    """Tests that artifacts pass through unchanged."""

    def test_artifact_in_response(self) -> None:
        """Original artifact is accessible in response."""
        artifact = {"original": "artifact", "with": [1, 2, 3]}
        request = ProjectionRequest(
            phase_id="3",
            artifact_ref=artifact,
        )

        response = route_projection(request)

        assert len(response.artifacts) == 1
        # The artifact should be the same object or an equivalent
        assert response.artifacts[0] == artifact

    def test_tuple_artifact_unwrapped(self) -> None:
        """Tuple artifacts are passed through as-is."""
        artifact = ("a", "b", "c")
        request = ProjectionRequest(
            phase_id="5",
            artifact_ref=artifact,
        )

        response = route_projection(request)

        assert response.artifacts == artifact

    def test_complex_nested_artifact(self) -> None:
        """Complex nested artifacts pass through unchanged."""
        artifact = {
            "level1": {
                "level2": {
                    "level3": [1, 2, {"level4": "deep"}],
                },
            },
            "list": [{"a": 1}, {"b": 2}],
            "tuple": (1, 2, 3),
        }

        request = ProjectionRequest(
            phase_id="7",
            artifact_ref=artifact,
        )

        response = route_projection(request)

        assert response.artifacts[0] == artifact
