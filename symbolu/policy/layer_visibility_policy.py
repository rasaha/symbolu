"""
Layer Visibility Policy (Exposure Gate) v1
==========================================

Deterministic policy system for controlling ontological layer visibility.

Hard Constraints:
    - Structural only — no semantics, no inference, no generation
    - Deterministic — same input → byte-for-byte identical output
    - Fail-closed — any ambiguity → deny
    - Read-only — MUST NOT mutate artifacts, projections, or ledger entries
    - No forbidden imports (random, uuid, datetime, time, ML/NLP/LLM)
    - Frozen dataclasses only
    - Hash-stable outputs

Invariants:
    - Unknown role → deny all
    - Empty allowed set → deny all
    - ABSOLVING never allowed unless explicitly listed in policy AND requested
    - requested_layers must be subset of policy-allowed layers
"""

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import FrozenSet, Mapping, Optional, Tuple

from symbolu.ontology.layers.ontology_layer import GATED_LAYERS, OntologicalLayer
from symbolu.ontology.contracts.projection_contract import ProjectionResponse


# =============================================================================
# Invariants Declaration
# =============================================================================

LAYER_VISIBILITY_INVARIANTS: Mapping[str, bool] = {
    "DETERMINISTIC": True,
    "FAIL_CLOSED": True,
    "READ_ONLY": True,
    "NO_GENERATION": True,
    "NO_SEMANTICS": True,
    "HASH_STABLE": True,
    "STRUCTURAL_ONLY": True,
}


# =============================================================================
# Enums
# =============================================================================

class RoleId(Enum):
    """Role identifiers for layer visibility control."""
    END_USER = "end_user"
    DEVELOPER = "developer"
    AUDITOR = "auditor"
    SYSTEM = "system"


class ExposureDecision(Enum):
    """Exposure decision outcomes."""
    ALLOWED = "allowed"
    DENIED = "denied"


# =============================================================================
# Policy Object (Pure Data)
# =============================================================================

@dataclass(frozen=True)
class LayerVisibilityPolicy:
    """
    Pure data object mapping roles to allowed ontological layers.

    Rules:
        - Unknown role → deny all
        - Empty allowed set → deny all
        - ABSOLVING never allowed unless explicitly listed

    Attributes:
        role_allowed_layers: Immutable mapping of RoleId to frozenset of allowed layers.
    """
    role_allowed_layers: Tuple[Tuple[RoleId, FrozenSet[OntologicalLayer]], ...]

    def get_allowed_layers(self, role_id: RoleId) -> FrozenSet[OntologicalLayer]:
        """
        Get allowed layers for a role.

        Args:
            role_id: The role to look up.

        Returns:
            Frozenset of allowed layers, or empty frozenset if role unknown.
        """
        for role, layers in self.role_allowed_layers:
            if role == role_id:
                return layers
        # Unknown role -> deny all (fail-closed)
        return frozenset()

    def is_layer_allowed(self, role_id: RoleId, layer: OntologicalLayer) -> bool:
        """
        Check if a specific layer is allowed for a role.

        Args:
            role_id: The role to check.
            layer: The layer to check.

        Returns:
            True if layer is allowed, False otherwise.
        """
        allowed = self.get_allowed_layers(role_id)
        return layer in allowed


# =============================================================================
# Default Policy (Fail-Closed)
# =============================================================================

# Standard non-gated layers available to most roles
_STANDARD_LAYERS: FrozenSet[OntologicalLayer] = frozenset({
    OntologicalLayer.ACTING,
    OntologicalLayer.TAGGING,
    OntologicalLayer.FORMING,
    OntologicalLayer.THINKING,
    OntologicalLayer.DIRECTING,
    OntologicalLayer.REASONING,
    OntologicalLayer.PURPOSING,
    OntologicalLayer.META_OBSERVING,
    OntologicalLayer.UNIFYING,
})

# ABSOLVING is gated - only AUDITOR and SYSTEM have access
_AUDITOR_LAYERS: FrozenSet[OntologicalLayer] = _STANDARD_LAYERS | frozenset({
    OntologicalLayer.ABSOLVING,
})

DEFAULT_POLICY = LayerVisibilityPolicy(
    role_allowed_layers=(
        (RoleId.END_USER, _STANDARD_LAYERS),
        (RoleId.DEVELOPER, _STANDARD_LAYERS),
        (RoleId.AUDITOR, _AUDITOR_LAYERS),
        (RoleId.SYSTEM, _AUDITOR_LAYERS),
    )
)


# =============================================================================
# Contracts (Frozen)
# =============================================================================

@dataclass(frozen=True)
class ExposureRequest:
    """
    Request for layer exposure evaluation.

    Attributes:
        artifact_id: Identifier of the artifact being accessed.
        span_id: Identifier of the ledger span.
        role_id: Role making the request.
        requested_layers: Specific layers being requested.
                          If None, use policy-allowed ∩ projected.
    """
    artifact_id: str
    span_id: str
    role_id: RoleId
    requested_layers: Optional[Tuple[OntologicalLayer, ...]] = None

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        if not isinstance(self.artifact_id, str):
            raise TypeError("artifact_id must be a string")
        if len(self.artifact_id) == 0:
            raise ValueError("artifact_id must be non-empty")
        if not isinstance(self.span_id, str):
            raise TypeError("span_id must be a string")
        if len(self.span_id) == 0:
            raise ValueError("span_id must be non-empty")
        if not isinstance(self.role_id, RoleId):
            raise TypeError("role_id must be a RoleId enum value")
        if self.requested_layers is not None:
            if not isinstance(self.requested_layers, tuple):
                raise TypeError("requested_layers must be a tuple or None")
            for layer in self.requested_layers:
                if not isinstance(layer, OntologicalLayer):
                    raise TypeError("requested_layers must contain OntologicalLayer values")


@dataclass(frozen=True)
class ExposureResponse:
    """
    Response from layer exposure evaluation.

    Attributes:
        allowed_layers: Layers that were allowed (subset of requested).
        denied_layers: Layers that were denied.
        effective_layers: Layers actually exposed (allowed ∩ projected).
        decision_hash: SHA-256 hash (truncated to 16 chars) of the decision.
    """
    allowed_layers: Tuple[OntologicalLayer, ...]
    denied_layers: Tuple[OntologicalLayer, ...]
    effective_layers: Tuple[OntologicalLayer, ...]
    decision_hash: str

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        if not isinstance(self.allowed_layers, tuple):
            raise TypeError("allowed_layers must be a tuple")
        if not isinstance(self.denied_layers, tuple):
            raise TypeError("denied_layers must be a tuple")
        if not isinstance(self.effective_layers, tuple):
            raise TypeError("effective_layers must be a tuple")
        if not isinstance(self.decision_hash, str):
            raise TypeError("decision_hash must be a string")
        if len(self.decision_hash) != 16:
            raise ValueError("decision_hash must be 16 characters")


# =============================================================================
# Hash Computation
# =============================================================================

def compute_decision_hash(
    artifact_id: str,
    span_id: str,
    role_id: RoleId,
    effective_layers: Tuple[OntologicalLayer, ...],
) -> str:
    """
    Compute deterministic hash for exposure decision.

    Hash formula:
        SHA-256(artifact_id | span_id | role_id | sorted(effective_layers))
        Truncated to 16 hex characters.

    Args:
        artifact_id: Artifact identifier.
        span_id: Span identifier.
        role_id: Role making the request.
        effective_layers: Effective layers in the decision.

    Returns:
        16-character hex string.
    """
    # Sort layers by value for deterministic ordering
    sorted_layers = tuple(sorted(effective_layers, key=lambda x: x.value))
    layer_names = ",".join(layer.name for layer in sorted_layers)

    # Build canonical input string
    canonical_input = f"{artifact_id}|{span_id}|{role_id.value}|{layer_names}"

    # Compute SHA-256 and truncate to 16 chars
    hash_bytes = sha256(canonical_input.encode("utf-8")).hexdigest()
    return hash_bytes[:16]


# =============================================================================
# ExposureGate
# =============================================================================

class ExposureGate:
    """
    Deterministic gate for evaluating layer exposure requests.

    Rules:
        - Works ONLY on projected layers (never expands them)
        - requested_layers must be subset of policy-allowed layers
        - If requested_layers is None → use policy-allowed ∩ projected
        - ABSOLVING requires:
            1. Explicit request
            2. Present in policy allowlist
        - Any violation → deny everything

    This class is stateless and read-only.
    """

    def __init__(self, policy: Optional[LayerVisibilityPolicy] = None) -> None:
        """
        Initialize ExposureGate with a policy.

        Args:
            policy: The layer visibility policy. Defaults to DEFAULT_POLICY.
        """
        self._policy = policy if policy is not None else DEFAULT_POLICY

    @property
    def policy(self) -> LayerVisibilityPolicy:
        """Return the policy (read-only access)."""
        return self._policy

    def evaluate(
        self,
        projection_response: ProjectionResponse,
        exposure_request: ExposureRequest,
    ) -> ExposureResponse:
        """
        Evaluate an exposure request against projected layers and policy.

        Args:
            projection_response: Response from ontological projection.
            exposure_request: Request for layer exposure.

        Returns:
            ExposureResponse with allowed, denied, effective layers and hash.

        Rules Applied:
            1. Get policy-allowed layers for role
            2. Get projected layers from projection_response
            3. Determine requested layers (explicit or implicit)
            4. Validate ABSOLVING constraints
            5. Compute effective = requested ∩ allowed ∩ projected
            6. Any violation → deny all
        """
        role_id = exposure_request.role_id
        artifact_id = exposure_request.artifact_id
        span_id = exposure_request.span_id

        # Step 1: Get policy-allowed layers for this role
        policy_allowed = self._policy.get_allowed_layers(role_id)

        # Fail-closed: unknown role or empty policy means deny all
        if len(policy_allowed) == 0:
            return self._create_deny_all_response(artifact_id, span_id, role_id)

        # Step 2: Get projected layers from projection response
        projected_layers = frozenset(projection_response.layers)

        # Step 3: Determine requested layers
        if exposure_request.requested_layers is None:
            # Implicit: use policy-allowed ∩ projected (excluding gated unless in policy)
            requested = policy_allowed & projected_layers
            # ABSOLVING must NOT be implicitly included even if in policy
            # It requires EXPLICIT request
            requested = requested - GATED_LAYERS
        else:
            requested = frozenset(exposure_request.requested_layers)

        # Step 4: Validate ABSOLVING constraints
        # ABSOLVING requires:
        #   1. Explicit request (checked above - implicit requests exclude it)
        #   2. Present in policy allowlist
        requested_gated = requested & GATED_LAYERS
        if len(requested_gated) > 0:
            # Check if gated layers are in policy allowlist
            gated_not_allowed = requested_gated - policy_allowed
            if len(gated_not_allowed) > 0:
                # Gated layer requested but not in policy → deny ALL
                return self._create_deny_all_response(artifact_id, span_id, role_id)

        # Step 5: Validate requested is subset of policy-allowed
        requested_outside_policy = requested - policy_allowed
        if len(requested_outside_policy) > 0:
            # Requested layer outside policy → deny ALL (fail-closed)
            return self._create_deny_all_response(artifact_id, span_id, role_id)

        # Step 6: Compute effective = requested ∩ projected
        # (already subset of policy_allowed due to Step 5)
        effective = requested & projected_layers

        # Compute allowed = requested ∩ policy_allowed (all requested are allowed at this point)
        allowed = requested

        # Denied = requested - effective (layers that were requested but not in projection)
        denied = requested - effective

        # Sort for deterministic output
        allowed_tuple = tuple(sorted(allowed, key=lambda x: x.value))
        denied_tuple = tuple(sorted(denied, key=lambda x: x.value))
        effective_tuple = tuple(sorted(effective, key=lambda x: x.value))

        # Compute decision hash
        decision_hash = compute_decision_hash(
            artifact_id=artifact_id,
            span_id=span_id,
            role_id=role_id,
            effective_layers=effective_tuple,
        )

        return ExposureResponse(
            allowed_layers=allowed_tuple,
            denied_layers=denied_tuple,
            effective_layers=effective_tuple,
            decision_hash=decision_hash,
        )

    def _create_deny_all_response(
        self,
        artifact_id: str,
        span_id: str,
        role_id: RoleId,
    ) -> ExposureResponse:
        """
        Create a deny-all response (fail-closed).

        Args:
            artifact_id: Artifact identifier.
            span_id: Span identifier.
            role_id: Role making the request.

        Returns:
            ExposureResponse with all fields empty and hash computed.
        """
        decision_hash = compute_decision_hash(
            artifact_id=artifact_id,
            span_id=span_id,
            role_id=role_id,
            effective_layers=(),
        )

        return ExposureResponse(
            allowed_layers=(),
            denied_layers=(),
            effective_layers=(),
            decision_hash=decision_hash,
        )


# =============================================================================
# Factory Functions
# =============================================================================

def create_exposure_gate(
    policy: Optional[LayerVisibilityPolicy] = None,
) -> ExposureGate:
    """
    Create an ExposureGate instance.

    Args:
        policy: Optional custom policy. Defaults to DEFAULT_POLICY.

    Returns:
        ExposureGate instance.
    """
    return ExposureGate(policy=policy)


def create_exposure_request(
    artifact_id: str,
    span_id: str,
    role_id: RoleId,
    requested_layers: Optional[Tuple[OntologicalLayer, ...]] = None,
) -> ExposureRequest:
    """
    Create an ExposureRequest instance.

    Args:
        artifact_id: Artifact identifier.
        span_id: Span identifier.
        role_id: Role making the request.
        requested_layers: Optional specific layers to request.

    Returns:
        ExposureRequest instance.
    """
    return ExposureRequest(
        artifact_id=artifact_id,
        span_id=span_id,
        role_id=role_id,
        requested_layers=requested_layers,
    )
