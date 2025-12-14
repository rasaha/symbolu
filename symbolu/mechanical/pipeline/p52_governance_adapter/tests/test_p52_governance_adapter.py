"""
P52 Governance Adapter Test Suite

This test suite validates the P52 Governance Adapter Interface phase.

Testing rule (STRICT):
    One test per invariant.
    No invariant -> no test.

Required Tests:
    - INV-P52-1: GovernanceResponse never instantiated
    - INV-P52-2: Upstream data unchanged
    - INV-P52-3: No gating side effects
    - INV-P52-4: Absence of response does not error
    - INV-P52-5: Removal equivalence test
    - Structural: GovernanceRequest contains only allowed fields

Total tests: 6

Each test explicitly states which invariant it proves.

CRITICAL: All tests are DETERMINISTIC with ZERO false positives.
"""

import inspect
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import pytest


# ============================================================================
# IMPORTS
# ============================================================================

from symbolu.mechanical.pipeline.p52_governance_adapter import (
    # Version
    P52_VERSION,
    # Constants
    VALID_GOVERNANCE_DECISIONS,
    VALID_READINESS_LEVELS,
    GOVERNANCE_REQUEST_FIELDS,
    GOVERNANCE_RESPONSE_FIELDS,
    # Dataclasses
    GovernanceRequest,
    GovernanceResponse,
    # Core assembly
    assemble_governance_request,
    run_p52_directly,
    # Integration
    maybe_run_p52,
    # Helpers
    is_p52_disabled,
    has_p52_request,
    get_p52_request,
)


# ============================================================================
# MOCK HELPERS
# ============================================================================


@dataclass
class MockP20Snapshot:
    """Mock P20 unified cognitive snapshot."""
    run_id: str = "test_run_123"
    coherence_v3: Optional[float] = 0.85
    drift_fusion_index: Optional[float] = 0.3
    temporal_entropy_diff: Optional[float] = 0.1

    def phase_count(self) -> int:
        return 20


@dataclass
class MockP21DeliveryMode:
    """Mock P21 delivery mode decision."""
    delivery_mode: str = "TEXT_AND_VOICE"
    delivery_allowed: bool = True


@dataclass
class MockP51Envelope:
    """Mock P51 governance readiness envelope."""
    ready: bool = True
    readiness_level: str = "READY"
    blocking_factors: Tuple[str, ...] = ()
    advisory_notes: Tuple[str, ...] = ()
    supporting_evidence: Dict[str, Any] = None
    observer_only: bool = True

    def __post_init__(self):
        if self.supporting_evidence is None:
            self.supporting_evidence = {}


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    p51_governance_readiness: Optional[MockP51Envelope] = None
    phase_20_snapshot: Optional[MockP20Snapshot] = None
    p21_delivery_mode: Optional[MockP21DeliveryMode] = None
    p52_governance_request: Optional[GovernanceRequest] = None
    _p52_disabled: bool = False


def make_complete_context() -> MockPipelineContext:
    """Create a context with all required phases present."""
    return MockPipelineContext(
        p51_governance_readiness=MockP51Envelope(),
        phase_20_snapshot=MockP20Snapshot(),
        p21_delivery_mode=MockP21DeliveryMode(),
    )


def make_not_ready_context() -> MockPipelineContext:
    """Create a context with NOT_READY status."""
    return MockPipelineContext(
        p51_governance_readiness=MockP51Envelope(
            ready=False,
            readiness_level="NOT_READY",
            blocking_factors=("MISSING_MANDATORY_PHASE:p7_discourse_envelope",),
        ),
        phase_20_snapshot=MockP20Snapshot(),
        p21_delivery_mode=MockP21DeliveryMode(),
    )


def make_context_without_p51() -> MockPipelineContext:
    """Create a context without P51 envelope."""
    return MockPipelineContext(
        p51_governance_readiness=None,
        phase_20_snapshot=MockP20Snapshot(),
        p21_delivery_mode=MockP21DeliveryMode(),
    )


# ============================================================================
# INV-P52-1: NO GOVERNANCE EXECUTION
# ============================================================================


class TestINV_P52_1_NoGovernanceExecution:
    """
    INV-P52-1: P52 MUST NOT execute or simulate governance.

    This test proves INV-P52-1.
    """

    def test_governance_response_never_instantiated(self):
        """
        This test proves INV-P52-1.

        GovernanceResponse is defined as a contract only. P52 must never
        instantiate it. We verify that running P52 does not create any
        GovernanceResponse objects.
        """
        ctx = make_complete_context()

        # Run P52
        request = maybe_run_p52(ctx)

        # Verify GovernanceRequest was created
        assert request is not None
        assert isinstance(request, GovernanceRequest)

        # Verify no GovernanceResponse was created on context
        assert not hasattr(ctx, "p52_governance_response")

        # Verify the module code does not instantiate GovernanceResponse
        import symbolu.mechanical.pipeline.p52_governance_adapter.p52_assembler as assembler_module
        import symbolu.mechanical.pipeline.p52_governance_adapter.p52_integration as integration_module

        assembler_source = inspect.getsource(assembler_module)
        integration_source = inspect.getsource(integration_module)

        # GovernanceResponse should never be instantiated in these modules
        assert "GovernanceResponse(" not in assembler_source
        assert "GovernanceResponse(" not in integration_source


# ============================================================================
# INV-P52-2: UPSTREAM IMMUTABILITY
# ============================================================================


class TestINV_P52_2_UpstreamImmutability:
    """
    INV-P52-2: P52 MUST NOT modify or reinterpret upstream data.

    This test proves INV-P52-2.
    """

    def test_upstream_data_unchanged(self):
        """
        This test proves INV-P52-2.

        P52 must not modify any upstream phase outputs when assembling
        the governance request.
        """
        ctx = make_complete_context()

        # Capture original values
        original_p51_readiness = ctx.p51_governance_readiness.readiness_level
        original_p51_ready = ctx.p51_governance_readiness.ready
        original_p20_run_id = ctx.phase_20_snapshot.run_id
        original_p20_coherence = ctx.phase_20_snapshot.coherence_v3
        original_p21_mode = ctx.p21_delivery_mode.delivery_mode
        original_p21_allowed = ctx.p21_delivery_mode.delivery_allowed

        # Run P52
        maybe_run_p52(ctx)

        # Verify all upstream values unchanged
        assert ctx.p51_governance_readiness.readiness_level == original_p51_readiness
        assert ctx.p51_governance_readiness.ready == original_p51_ready
        assert ctx.phase_20_snapshot.run_id == original_p20_run_id
        assert ctx.phase_20_snapshot.coherence_v3 == original_p20_coherence
        assert ctx.p21_delivery_mode.delivery_mode == original_p21_mode
        assert ctx.p21_delivery_mode.delivery_allowed == original_p21_allowed


# ============================================================================
# INV-P52-3: NO GATING
# ============================================================================


class TestINV_P52_3_NoGating:
    """
    INV-P52-3: P52 MUST NOT introduce branching or gating.

    This test proves INV-P52-3.
    """

    def test_no_gating_side_effects(self):
        """
        This test proves INV-P52-3.

        P52 cannot gate or block any output. The pipeline should behave
        identically with or without P52 running. P52 always produces a
        request if P51 is present, regardless of readiness level.
        """
        # Test with READY status
        ctx_ready = make_complete_context()
        request_ready = maybe_run_p52(ctx_ready)

        assert request_ready is not None
        assert request_ready.readiness_level == "READY"

        # Test with NOT_READY status - still produces request, no blocking
        ctx_not_ready = make_not_ready_context()
        request_not_ready = maybe_run_p52(ctx_not_ready)

        assert request_not_ready is not None
        assert request_not_ready.readiness_level == "NOT_READY"

        # Both cases produce requests - no gating based on readiness
        # P52 is purely observational


# ============================================================================
# INV-P52-4: NO RESPONSE REQUIREMENT
# ============================================================================


class TestINV_P52_4_NoResponseRequirement:
    """
    INV-P52-4: P52 MUST NOT require GovernanceResponse to exist.

    This test proves INV-P52-4.
    """

    def test_absence_of_response_does_not_error(self):
        """
        This test proves INV-P52-4.

        P52 must function without any GovernanceResponse existing.
        It assembles a request and stores it, expecting nothing in return.
        """
        ctx = make_complete_context()

        # Run P52 - should not raise, should not expect response
        request = maybe_run_p52(ctx)

        # Request was created successfully
        assert request is not None

        # No response exists anywhere
        assert not hasattr(ctx, "p52_governance_response")

        # Request is valid and complete
        assert request.snapshot_id == "test_run_123"
        assert request.readiness_level == "READY"
        assert request.trace_hash is not None and len(request.trace_hash) > 0

        # Module does not import or require GovernanceResponse for functionality
        # (It exists only as a contract definition)


# ============================================================================
# INV-P52-5: REMOVAL EQUIVALENCE
# ============================================================================


class TestINV_P52_5_RemovalEquivalence:
    """
    INV-P52-5: When P52 is removed, system behavior is bitwise identical.

    This test proves INV-P52-5.
    """

    def test_removal_equivalence(self):
        """
        This test proves INV-P52-5.

        Removing P52 should not change any upstream state or downstream
        behavior. The system should be bitwise identical with or without P52.
        """
        # Create two identical contexts
        ctx_with_p52 = make_complete_context()
        ctx_without_p52 = make_complete_context()

        # Run P52 on one context
        maybe_run_p52(ctx_with_p52)

        # Don't run P52 on the other

        # All upstream values should be identical
        assert (
            ctx_with_p52.p51_governance_readiness.readiness_level ==
            ctx_without_p52.p51_governance_readiness.readiness_level
        )
        assert (
            ctx_with_p52.p51_governance_readiness.ready ==
            ctx_without_p52.p51_governance_readiness.ready
        )
        assert (
            ctx_with_p52.phase_20_snapshot.run_id ==
            ctx_without_p52.phase_20_snapshot.run_id
        )
        assert (
            ctx_with_p52.phase_20_snapshot.coherence_v3 ==
            ctx_without_p52.phase_20_snapshot.coherence_v3
        )
        assert (
            ctx_with_p52.p21_delivery_mode.delivery_mode ==
            ctx_without_p52.p21_delivery_mode.delivery_mode
        )
        assert (
            ctx_with_p52.p21_delivery_mode.delivery_allowed ==
            ctx_without_p52.p21_delivery_mode.delivery_allowed
        )

        # Only difference should be p52_governance_request field
        assert ctx_with_p52.p52_governance_request is not None
        assert ctx_without_p52.p52_governance_request is None


# ============================================================================
# STRUCTURAL: ALLOWED FIELDS ONLY
# ============================================================================


class TestStructuralAllowedFieldsOnly:
    """
    Structural test: GovernanceRequest contains only allowed fields.
    """

    def test_governance_request_contains_only_allowed_fields(self):
        """
        GovernanceRequest must contain only the fields specified in the
        contract definition. No extra fields should be present.
        """
        ctx = make_complete_context()
        request = maybe_run_p52(ctx)

        assert request is not None

        # Get the dict representation
        request_dict = request.to_dict()

        # Verify all fields are in allowed set
        for field_name in request_dict.keys():
            assert field_name in GOVERNANCE_REQUEST_FIELDS, \
                f"Unexpected field '{field_name}' in GovernanceRequest"

        # Verify required fields are present
        required_fields = {
            "snapshot_id",
            "readiness_level",
            "blocking_factors",
            "advisory_notes",
            "cognitive_summary",
            "trace_hash",
        }
        for field_name in required_fields:
            assert field_name in request_dict, \
                f"Required field '{field_name}' missing from GovernanceRequest"

        # Verify cognitive_summary contains only structural metadata
        cognitive_summary = request_dict["cognitive_summary"]
        assert isinstance(cognitive_summary, dict)

        # Structural fields only - no free text, no semantics, no probabilities
        allowed_summary_fields = {
            "snapshot_present",
            "has_coherence",
            "has_drift",
            "has_entropy",
            "phase_count",
            "delivery_present",
            "delivery_allowed",
        }
        for field_name in cognitive_summary.keys():
            assert field_name in allowed_summary_fields, \
                f"Unexpected field '{field_name}' in cognitive_summary"
