"""
Ontological Layer Router
========================

Thin, deterministic router that projects Phase artifacts onto ontological layers.

This router is structural only:
    - No semantics
    - No probabilities
    - No learning
    - No generation

Hard Constraints:
    - Deterministic ordering
    - No mutation of artifacts
    - No fallback behavior
    - No inference
    - Fail-closed on invalid input
    - Read-only projection
    - Fully auditable
    - Replayable

Responsibilities:
    1. Accept a ProjectionRequest
    2. Validate phase ID
    3. Lookup allowed layers
    4. Attach attestation (no transformation)
    5. Emit ProjectionResponse
"""

from typing import Any, Tuple

from agentic.ontology.contracts.projection_contract import (
    ProjectionReasonCode,
    ProjectionRequest,
    ProjectionResponse,
    create_failed_response,
    create_success_response,
)
from agentic.ontology.layers.ontology_layer import OntologicalLayer
from agentic.ontology.ledger.ledger_adapter import (
    generate_ledger_span,
    LedgerSpanInput,
)
from agentic.ontology.router.phase_layer_map import (
    get_layers_for_phase,
    is_valid_phase_id,
)


class OntologicalLayerRouterError(Exception):
    """Exception raised for router invariant violations."""
    pass


class OntologicalLayerRouter:
    """
    Deterministic router for projecting Phase artifacts onto ontological layers.

    This router:
        - Does NOT modify any Phase logic
        - Does NOT mutate artifacts
        - Does NOT infer semantics
        - Only projects, attests, and routes through a structural lens

    Usage:
        router = OntologicalLayerRouter()
        request = ProjectionRequest(phase_id="3", artifact_ref=my_artifact)
        response = router.project(request)
    """

    def __init__(self) -> None:
        """Initialize the router. No state is stored."""
        pass

    def project(self, request: ProjectionRequest) -> ProjectionResponse:
        """
        Project a Phase artifact onto its ontological layers.

        Args:
            request: The projection request containing phase_id and artifact_ref.

        Returns:
            ProjectionResponse with the projected layers and artifacts.

        Note:
            - Deterministic: same input always produces identical output
            - Fail-closed: invalid input results in eligible=False
            - Read-only: artifacts are never modified
        """
        # Validate request type
        if not isinstance(request, ProjectionRequest):
            return create_failed_response(
                ProjectionReasonCode.VALIDATION_FAILED,
                invariants={"request_type_valid": False},
            )

        # Validate phase ID
        if not is_valid_phase_id(request.phase_id):
            return create_failed_response(
                ProjectionReasonCode.INVALID_PHASE_ID,
                invariants={"phase_id_valid": False},
            )

        # Lookup layers for this phase
        include_gated = request.options.include_gated_layers
        try:
            layers = get_layers_for_phase(
                request.phase_id,
                include_gated=include_gated,
            )
        except KeyError:
            return create_failed_response(
                ProjectionReasonCode.INVALID_PHASE_ID,
                invariants={"phase_id_lookup": False},
            )

        # Build artifacts tuple (opaque pass-through)
        # Artifacts are wrapped in a tuple for immutability
        artifacts = self._wrap_artifacts(request.artifact_ref)

        # Generate ledger spans if requested
        ledger_spans: Tuple[str, ...] = ()
        if request.options.include_ledger_spans:
            ledger_spans = self._generate_ledger_spans(
                request.phase_id,
                layers,
                artifacts,
            )

        # Build invariants report
        invariants = {
            "phase_id_valid": True,
            "layers_resolved": True,
            "artifacts_immutable": True,
            "deterministic": True,
        }

        return create_success_response(
            layers=layers,
            artifacts=artifacts,
            ledger_spans=ledger_spans,
            invariants=invariants,
        )

    def _wrap_artifacts(self, artifact_ref: Any) -> Tuple[Any, ...]:
        """
        Wrap artifact reference in an immutable tuple.

        Args:
            artifact_ref: The opaque artifact reference.

        Returns:
            Tuple containing the artifact reference.

        Note:
            Router does not inspect or modify the artifact.
        """
        if artifact_ref is None:
            return ()
        if isinstance(artifact_ref, tuple):
            return artifact_ref
        return (artifact_ref,)

    def _generate_ledger_spans(
        self,
        phase_id: str,
        layers: Tuple[OntologicalLayer, ...],
        artifacts: Tuple[Any, ...],
    ) -> Tuple[str, ...]:
        """
        Generate ledger span IDs for the projection.

        Args:
            phase_id: The phase identifier.
            layers: The projected layers.
            artifacts: The wrapped artifacts.

        Returns:
            Tuple of ledger span ID strings (hex hashes).
        """
        spans = []
        for layer in layers:
            span_input = LedgerSpanInput(
                phase_id=phase_id,
                layer=layer,
                artifact_refs=artifacts,
            )
            span_id = generate_ledger_span(span_input)
            spans.append(span_id)
        return tuple(spans)


# =============================================================================
# Module-level convenience function
# =============================================================================

def route_projection(request: ProjectionRequest) -> ProjectionResponse:
    """
    Route a projection request through the ontological layer router.

    This is a convenience function that creates a router instance and
    calls project(). The router is stateless, so this is equivalent to
    using OntologicalLayerRouter().project(request).

    Args:
        request: The projection request.

    Returns:
        The projection response.
    """
    router = OntologicalLayerRouter()
    return router.project(request)
