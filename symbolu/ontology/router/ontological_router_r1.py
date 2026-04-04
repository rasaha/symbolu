"""
Ontological Layer Router - R1 Relaxation
==========================================

RELAXATION R1 ONLY:
    Allow routing to be influenced by an explicit, declared projection hint
    embedded in the artifact — while enforcing strict per-phase allowlists
    and fail-closed behavior.

This router is a STRUCTURAL SWITCHBOARD. It does NOT:
    - Infer meaning
    - Infer intent
    - Infer emotion
    - Compute importance
    - Compute centrality
    - Compare magnitudes
    - Introduce scores
    - Introduce thresholds
    - Optimize routing
    - Use language terms in logic

Hard Constraints:
    - Deterministic: SAME INPUT -> IDENTICAL OUTPUT (byte-for-byte)
    - No mutation of request or artifacts
    - No probabilistic logic
    - No scoring, ranking, weighting
    - No NLP / ML / LLM imports
    - Fail-closed on ANY violation
    - ABSOLVING unreachable without opt-in
    - Hash stability across 100 runs

-------------------------------------------------------------------
R1 RELAXATION BOUNDARY MARKER - THE ONLY RELAXED CONSTRAINT IS HERE:

    declared_projection_hint may override the default projection
    IFF the hint is in PHASE_ALLOWED_HINTS[phase_id]

    This is the ONLY deviation from purely static phase->layer mapping.
-------------------------------------------------------------------
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Mapping, Optional, Tuple

from symbolu.ontology.layers.ontology_layer import OntologicalLayer  # canonical source
from symbolu.safety.gcc_runtime_guard import assert_non_expressive


# =============================================================================
# Request/Response Contracts (Frozen/Immutable)
# =============================================================================

@dataclass(frozen=True)
class ProjectionRequest:
    """
    Request for ontological layer projection (R1).

    Attributes:
        artifact_id: Opaque, hash-stable artifact identifier.
        phase_id: Phase identifier (e.g., "1b", "2", ..., "9").
        artifact_hash: Precomputed, immutable hash of the artifact.
        declared_projection_hint: Optional declared hint for R1 relaxation.

    Invariants:
        - All fields are immutable after construction
        - artifact_id and artifact_hash are opaque strings
        - No enrichment or interpretation occurs
    """
    artifact_id: str
    phase_id: str
    artifact_hash: str
    declared_projection_hint: Optional[OntologicalLayer] = None

    def __post_init__(self) -> None:
        """Validate invariants on construction (fail-closed)."""
        if not isinstance(self.artifact_id, str) or len(self.artifact_id) == 0:
            raise ProjectionBlockedError(
                "artifact_id must be a non-empty string",
                reason=BlockedReason.INVALID_ARTIFACT_ID
            )
        if not isinstance(self.phase_id, str) or len(self.phase_id) == 0:
            raise ProjectionBlockedError(
                "phase_id must be a non-empty string",
                reason=BlockedReason.INVALID_PHASE_ID
            )
        if not isinstance(self.artifact_hash, str) or len(self.artifact_hash) == 0:
            raise ProjectionBlockedError(
                "artifact_hash must be a non-empty string",
                reason=BlockedReason.INVALID_ARTIFACT_HASH
            )
        if self.declared_projection_hint is not None:
            if not isinstance(self.declared_projection_hint, OntologicalLayer):
                raise ProjectionBlockedError(
                    "declared_projection_hint must be an OntologicalLayer or None",
                    reason=BlockedReason.INVALID_HINT_TYPE
                )


@dataclass(frozen=True)
class ProjectionResponse:
    """
    Response from ontological layer projection (R1).

    Attributes:
        artifact_id: Echo of the input artifact ID.
        artifact_hash: Echo of the input artifact hash.
        phase_id: Echo of the input phase ID.
        projected_layers: Tuple of projected layers (deterministic order).
        router_version: Version string for the router (for audit).

    Invariants:
        - All outputs are hash-stable
        - Same input always produces identical output
        - No semantic inference
    """
    artifact_id: str
    artifact_hash: str
    phase_id: str
    projected_layers: Tuple[OntologicalLayer, ...]
    router_version: str


# =============================================================================
# Blocked Reason Codes (Fixed)
# =============================================================================

class BlockedReason(Enum):
    """Fixed reason codes for projection failures (fail-closed)."""
    INVALID_ARTIFACT_ID = "INVALID_ARTIFACT_ID"
    INVALID_PHASE_ID = "INVALID_PHASE_ID"
    INVALID_ARTIFACT_HASH = "INVALID_ARTIFACT_HASH"
    INVALID_HINT_TYPE = "INVALID_HINT_TYPE"
    PHASE_NOT_IN_MAPPING = "PHASE_NOT_IN_MAPPING"
    HINT_NOT_IN_ALLOWLIST = "HINT_NOT_IN_ALLOWLIST"
    ABSOLVING_NOT_PERMITTED = "ABSOLVING_NOT_PERMITTED"
    HASH_MISMATCH = "HASH_MISMATCH"


class ProjectionBlockedError(Exception):
    """
    Exception raised when projection is blocked (fail-closed).

    WHY FAIL-CLOSED:
        This router operates in a non-probabilistic, deterministic system.
        Any ambiguity, invalid input, or constraint violation MUST result
        in a complete failure rather than a partial or "best effort" result.

        Fail-closed ensures:
        - No silent corruption of the projection path
        - No unintended routing to forbidden layers
        - Full auditability of all failures
        - Replay safety (same invalid input always fails identically)
    """

    def __init__(self, message: str, *, reason: BlockedReason) -> None:
        super().__init__(message)
        self.reason = reason


# =============================================================================
# Deterministic Mapping Tables (STATIC)
# =============================================================================

# 2.1 Base Phase -> Layer Mapping (STATIC, DEFAULT)
# This is the canonical mapping from Phase IDs to default ontological layers.
# Each phase maps to exactly one default layer.
PHASE_TO_LAYER_DEFAULT: Mapping[str, Tuple[OntologicalLayer, ...]] = {
    "1b": (OntologicalLayer.EXECUTION,),
    "2": (OntologicalLayer.IDENTITY,),
    "3": (OntologicalLayer.STRUCTURE,),
    "4": (OntologicalLayer.STRUCTURE,),
    "5": (OntologicalLayer.COGNITION,),
    "6": (OntologicalLayer.AGENCY,),
    "7": (OntologicalLayer.REASONING,),
    "8": (OntologicalLayer.WITNESSES,),
    "9": (OntologicalLayer.UNIFYING,),
}

# 2.2 Phase -> Allowed Declared Hints (ALLOWLIST)
# This is the core safety mechanism for R1 relaxation.
# A declared hint is ONLY valid if it is in this allowlist for the given phase.
#
# RULES:
#   - Declared hint MUST be in the allowlist for that phase
#   - Declared hint MUST NOT introduce ABSOLVING unless explicitly permitted
#   - Declared hint MUST NOT expand the default set — only refine within allowed scope
PHASE_ALLOWED_HINTS: Mapping[str, FrozenSet[OntologicalLayer]] = {
    "1b": frozenset({OntologicalLayer.EXECUTION}),
    "2": frozenset({OntologicalLayer.IDENTITY}),
    "3": frozenset({OntologicalLayer.STRUCTURE}),
    "4": frozenset({OntologicalLayer.STRUCTURE, OntologicalLayer.COGNITION}),
    "5": frozenset({OntologicalLayer.COGNITION, OntologicalLayer.UNIFYING}),
    "6": frozenset({OntologicalLayer.AGENCY}),
    "7": frozenset({OntologicalLayer.REASONING}),
    "8": frozenset({OntologicalLayer.WITNESSES}),
    "9": frozenset({OntologicalLayer.UNIFYING}),
}

# Valid phase IDs (derived from mapping)
VALID_PHASE_IDS: FrozenSet[str] = frozenset(PHASE_TO_LAYER_DEFAULT.keys())


# =============================================================================
# Ontological Layer Router (R1)
# =============================================================================

class OntologicalLayerRouter:
    """
    Deterministic router for projecting Phase artifacts onto ontological layers.

    This is the R1 relaxation router:
        - Supports declared_projection_hint (within allowlist)
        - Enforces fail-closed behavior on ANY violation
        - ABSOLVING is gated and requires explicit opt-in

    This router:
        - Does NOT modify any Phase logic
        - Does NOT mutate artifacts
        - Does NOT infer semantics
        - Only projects through structural rules
    """

    ROUTER_VERSION = "R1.0"

    def __init__(self, *, explicit_absolving_opt_in: bool = False) -> None:
        """
        Initialize the R1 router.

        Args:
            explicit_absolving_opt_in: If True, ABSOLVING layer is reachable.
                                       Default is False (fail-closed).

        Note:
            The router is stateless except for the ABSOLVING gate flag.
        """
        self._explicit_absolving_opt_in = explicit_absolving_opt_in

    def project(self, request: ProjectionRequest) -> ProjectionResponse:
        """
        Project a Phase artifact onto its ontological layers.

        Args:
            request: The ProjectionRequest containing phase_id, artifact info,
                     and optional declared_projection_hint.

        Returns:
            ProjectionResponse with the projected layers.

        Raises:
            ProjectionBlockedError: If ANY validation fails (fail-closed).

        Routing Logic:
            1. Validate phase_id is in VALID_PHASE_IDS
            2. Resolve default projection from PHASE_TO_LAYER_DEFAULT
            3. If declared_projection_hint exists:
               - Validate hint in PHASE_ALLOWED_HINTS[phase_id]
               - Validate ABSOLVING gate
               - Replace default projection with declared hint
            4. If ANY validation fails -> raise ProjectionBlockedError
            5. Return ProjectionResponse (hash-stable)
        """
        # Step 1: Validate phase_id
        if request.phase_id not in VALID_PHASE_IDS:
            # FAIL-CLOSED: Unknown phase ID means we cannot route.
            # We do not guess or infer the correct phase.
            raise ProjectionBlockedError(
                f"phase_id '{request.phase_id}' is not in valid phase set",
                reason=BlockedReason.PHASE_NOT_IN_MAPPING
            )

        # Step 2: Resolve default projection
        default_layers = PHASE_TO_LAYER_DEFAULT[request.phase_id]

        # Step 3: Handle declared projection hint (R1 RELAXATION)
        if request.declared_projection_hint is not None:
            projected_layers = self._apply_hint(
                request.phase_id,
                request.declared_projection_hint
            )
        else:
            projected_layers = default_layers

        # Step 4: (Validations occurred in _apply_hint if hint was provided)
        # Step 5: Build response
        response = ProjectionResponse(
            artifact_id=request.artifact_id,
            artifact_hash=request.artifact_hash,
            phase_id=request.phase_id,
            projected_layers=projected_layers,
            router_version=self.ROUTER_VERSION,
        )

        # GCC C-1: Assert return value is non-expressive (fail-closed)
        assert_non_expressive(response, path="OntologicalLayerRouter.project:return")

        return response

    def _apply_hint(
        self,
        phase_id: str,
        hint: OntologicalLayer,
    ) -> Tuple[OntologicalLayer, ...]:
        """
        Apply a declared projection hint (R1 relaxation boundary).

        -------------------------------------------------------------------
        R1 RELAXATION BOUNDARY - THIS IS THE ONLY RELAXED CONSTRAINT:

        The declared_projection_hint may override the default projection
        IFF the hint is in PHASE_ALLOWED_HINTS[phase_id].

        This is the ONLY deviation from purely static phase->layer mapping.
        -------------------------------------------------------------------

        Args:
            phase_id: The phase identifier.
            hint: The declared projection hint.

        Returns:
            Tuple containing the hint as the sole projected layer.

        Raises:
            ProjectionBlockedError: If hint is not in allowlist or
                                    ABSOLVING gate is violated.
        """
        # Get allowed hints for this phase
        allowed_hints = PHASE_ALLOWED_HINTS.get(phase_id, frozenset())

        # Validate hint is in allowlist
        if hint not in allowed_hints:
            # FAIL-CLOSED: Hint is not permitted for this phase.
            # We do not fall back to default - we reject entirely.
            raise ProjectionBlockedError(
                f"declared_projection_hint '{hint.name}' is not in "
                f"allowed hints for phase '{phase_id}': {sorted(h.name for h in allowed_hints)}",
                reason=BlockedReason.HINT_NOT_IN_ALLOWLIST
            )

        # ABSOLVING Gate Check (NON-NEGOTIABLE)
        if hint == OntologicalLayer.ABSOLVING:
            if not self._explicit_absolving_opt_in:
                # FAIL-CLOSED: ABSOLVING is terminal/tombstone-adjacent.
                # It MUST NEVER be reachable without explicit opt-in.
                raise ProjectionBlockedError(
                    "ABSOLVING layer requires explicit_absolving_opt_in=True",
                    reason=BlockedReason.ABSOLVING_NOT_PERMITTED
                )
            # Additional check: ABSOLVING must also be in allowlist
            # (This is redundant given the check above, but defense-in-depth)
            if OntologicalLayer.ABSOLVING not in allowed_hints:
                raise ProjectionBlockedError(
                    f"ABSOLVING is not in allowlist for phase '{phase_id}'",
                    reason=BlockedReason.ABSOLVING_NOT_PERMITTED
                )

        # Return hint as sole projected layer
        return (hint,)


# =============================================================================
# Ledger Adapter (Deterministic)
# =============================================================================

@dataclass(frozen=True)
class LedgerSpanInput:
    """
    Input for generating a ledger span ID.

    Attributes:
        artifact_hash: The precomputed artifact hash.
        phase_id: The phase identifier.
        projected_layers: Tuple of projected layers.
    """
    artifact_hash: str
    phase_id: str
    projected_layers: Tuple[OntologicalLayer, ...]


class LedgerAdapter:
    """
    Deterministic ledger span ID generator.

    Generates span IDs using SHA-256 ONLY.
    Inputs:
        - artifact_hash
        - phase_id
        - projected_layers
    Output:
        - stable span_id (first N hex chars)

    Constraints:
        - NO timestamps
        - NO randomness
        - NO counters
    """

    # Number of hex characters to use for span ID (64 = full SHA-256)
    SPAN_ID_LENGTH = 16

    @staticmethod
    def generate_span_id(span_input: LedgerSpanInput) -> str:
        """
        Generate a deterministic span ID from input.

        Args:
            span_input: The LedgerSpanInput containing artifact_hash,
                        phase_id, and projected_layers.

        Returns:
            A hex string of length SPAN_ID_LENGTH representing the span ID.

        Note:
            - Deterministic: same input always produces same output
            - No timestamps, no randomness, no counters
            - Uses SHA-256 for hash stability
        """
        # Build canonical representation
        # Layers are sorted by enum value for deterministic ordering
        sorted_layers = sorted(span_input.projected_layers, key=lambda l: l.value)
        layer_names = ",".join(layer.name for layer in sorted_layers)

        canonical = (
            f"artifact_hash:{span_input.artifact_hash}|"
            f"phase_id:{span_input.phase_id}|"
            f"layers:{layer_names}"
        )

        # Compute SHA-256 hash
        full_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        # Return first N characters
        return full_hash[:LedgerAdapter.SPAN_ID_LENGTH]


# =============================================================================
# Module-Level Convenience Function
# =============================================================================

def route_projection(
    request: ProjectionRequest,
    *,
    explicit_absolving_opt_in: bool = False,
) -> ProjectionResponse:
    """
    Route a projection request through the R1 ontological layer router.

    This is a convenience function that creates a router instance and
    calls project().

    Args:
        request: The projection request.
        explicit_absolving_opt_in: If True, ABSOLVING layer is reachable.

    Returns:
        The projection response.

    Raises:
        ProjectionBlockedError: If ANY validation fails (fail-closed).
    """
    router = OntologicalLayerRouter(
        explicit_absolving_opt_in=explicit_absolving_opt_in
    )
    # GCC guard applied inside router.project(); no double-check needed
    return router.project(request)
