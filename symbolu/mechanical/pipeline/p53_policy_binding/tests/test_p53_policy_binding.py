"""
P53 Policy Binding Test Suite

This test suite validates the P53 External Policy Binding Layer phase.

Testing rule (STRICT):
    One test per invariant.
    No invariant -> no test.

Required Tests:
    - INV-P53-1: Cognition outputs unchanged
    - INV-P53-2: GovernanceResponse preserved verbatim
    - INV-P53-3: Missing governance produces bound=False
    - INV-P53-4: Invalid governance structure raises error
    - INV-P53-5: Removing P53 yields identical pre-P53 outputs
    - Structural: authority_id treated as opaque (no parsing)

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
    GovernanceResponse,
    GovernanceRequest,
)

from symbolu.mechanical.pipeline.p53_policy_binding import (
    # Version
    P53_VERSION,
    # Constants
    VALID_GOVERNANCE_DECISIONS,
    GOVERNANCE_BINDING_FIELDS,
    # Dataclasses
    GovernanceBindingEnvelope,
    # Factory functions
    create_unbound_envelope,
    # Exceptions
    GovernanceResponseValidationError,
    # Core binding
    bind_governance_response,
    run_p53_directly,
    # Integration
    maybe_run_p53,
    # Helpers
    is_p53_disabled,
    has_p53_binding,
    get_p53_binding,
    is_governance_bound,
    get_governance_decision,
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
class MockP52Request:
    """Mock P52 governance request."""
    snapshot_id: str = "test_run_123"
    readiness_level: str = "READY"
    blocking_factors: Tuple[str, ...] = ()
    advisory_notes: Tuple[str, ...] = ()
    cognitive_summary: Dict[str, Any] = None
    trace_hash: str = "abc123"

    def __post_init__(self):
        if self.cognitive_summary is None:
            self.cognitive_summary = {}


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    # Upstream cognitive phases
    phase_20_snapshot: Optional[MockP20Snapshot] = None
    p21_delivery_mode: Optional[MockP21DeliveryMode] = None
    p51_governance_readiness: Optional[MockP51Envelope] = None
    p52_governance_request: Optional[MockP52Request] = None

    # P53 inputs (external governance)
    p53_governance_response: Optional[GovernanceResponse] = None
    p53_authority_id: Optional[str] = None

    # P53 output
    p53_policy_binding: Optional[GovernanceBindingEnvelope] = None

    # Control flags
    _p53_disabled: bool = False


def make_complete_context() -> MockPipelineContext:
    """Create a context with all required phases present (no governance response)."""
    return MockPipelineContext(
        phase_20_snapshot=MockP20Snapshot(),
        p21_delivery_mode=MockP21DeliveryMode(),
        p51_governance_readiness=MockP51Envelope(),
        p52_governance_request=MockP52Request(),
    )


def make_context_with_governance_response(
    decision: str = "ALLOW",
    rationale_codes: Tuple[str, ...] = ("CODE_001", "CODE_002"),
    audit_reference: Optional[str] = "audit_ref_123",
    authority_id: Optional[str] = "authority_abc",
) -> MockPipelineContext:
    """Create a context with an external governance response."""
    ctx = make_complete_context()
    ctx.p53_governance_response = GovernanceResponse(
        decision=decision,
        rationale_codes=rationale_codes,
        audit_reference=audit_reference,
    )
    ctx.p53_authority_id = authority_id
    return ctx


def make_context_without_governance_response() -> MockPipelineContext:
    """Create a context without any governance response."""
    return make_complete_context()


# ============================================================================
# INV-P53-1: NO COGNITION MODIFICATION
# ============================================================================


class TestINV_P53_1_NoCognitionModification:
    """
    INV-P53-1: P53 MUST NOT modify cognition, regime, discourse, or delivery.

    This test proves INV-P53-1.
    """

    def test_cognition_outputs_unchanged(self):
        """
        This test proves INV-P53-1.

        P53 must not modify any upstream cognitive outputs when binding
        governance. All cognitive phase outputs must remain identical.
        """
        ctx = make_context_with_governance_response()

        # Capture original cognitive values
        original_p20_run_id = ctx.phase_20_snapshot.run_id
        original_p20_coherence = ctx.phase_20_snapshot.coherence_v3
        original_p20_drift = ctx.phase_20_snapshot.drift_fusion_index
        original_p21_mode = ctx.p21_delivery_mode.delivery_mode
        original_p21_allowed = ctx.p21_delivery_mode.delivery_allowed
        original_p51_ready = ctx.p51_governance_readiness.ready
        original_p51_level = ctx.p51_governance_readiness.readiness_level
        original_p52_snapshot_id = ctx.p52_governance_request.snapshot_id
        original_p52_trace = ctx.p52_governance_request.trace_hash

        # Run P53
        envelope = maybe_run_p53(ctx)

        # Verify P53 ran successfully
        assert envelope is not None
        assert envelope.bound is True

        # Verify all cognitive values unchanged
        assert ctx.phase_20_snapshot.run_id == original_p20_run_id
        assert ctx.phase_20_snapshot.coherence_v3 == original_p20_coherence
        assert ctx.phase_20_snapshot.drift_fusion_index == original_p20_drift
        assert ctx.p21_delivery_mode.delivery_mode == original_p21_mode
        assert ctx.p21_delivery_mode.delivery_allowed == original_p21_allowed
        assert ctx.p51_governance_readiness.ready == original_p51_ready
        assert ctx.p51_governance_readiness.readiness_level == original_p51_level
        assert ctx.p52_governance_request.snapshot_id == original_p52_snapshot_id
        assert ctx.p52_governance_request.trace_hash == original_p52_trace

        # Verify P53 only writes to p53_policy_binding, nothing else
        # (The functional test above proves cognitive values unchanged)
        # Additional verification: P53 binding envelope is the only new field
        assert hasattr(ctx, "p53_policy_binding")
        assert ctx.p53_policy_binding is envelope


# ============================================================================
# INV-P53-2: VERBATIM PRESERVATION
# ============================================================================


class TestINV_P53_2_VerbatimPreservation:
    """
    INV-P53-2: P53 MUST NOT reinterpret governance decisions.

    This test proves INV-P53-2.
    """

    def test_governance_response_preserved_verbatim(self):
        """
        This test proves INV-P53-2.

        The governance response must be stored verbatim in the binding
        envelope. No interpretation, transformation, or modification.
        """
        # Create response with specific values
        original_decision = "DENY"
        original_rationale = ("REASON_A", "REASON_B", "REASON_C")
        original_audit_ref = "audit_xyz_789"
        original_authority = "external_authority_456"

        ctx = make_context_with_governance_response(
            decision=original_decision,
            rationale_codes=original_rationale,
            audit_reference=original_audit_ref,
            authority_id=original_authority,
        )

        # Run P53
        envelope = maybe_run_p53(ctx)

        # Verify binding occurred
        assert envelope is not None
        assert envelope.bound is True

        # Verify verbatim preservation
        assert envelope.decision == original_decision
        assert envelope.rationale_codes == original_rationale
        assert envelope.audit_reference == original_audit_ref
        assert envelope.authority_id == original_authority

        # Test with DEFER decision
        ctx_defer = make_context_with_governance_response(
            decision="DEFER",
            rationale_codes=("DEFER_REASON",),
            audit_reference=None,
            authority_id="auth_defer",
        )
        envelope_defer = maybe_run_p53(ctx_defer)

        assert envelope_defer.decision == "DEFER"
        assert envelope_defer.rationale_codes == ("DEFER_REASON",)
        assert envelope_defer.audit_reference is None
        assert envelope_defer.authority_id == "auth_defer"


# ============================================================================
# INV-P53-3: NO FALLBACK LOGIC
# ============================================================================


class TestINV_P53_3_NoFallbackLogic:
    """
    INV-P53-3: P53 MUST NOT introduce fallback logic if governance is absent.

    This test proves INV-P53-3.
    """

    def test_missing_governance_produces_unbound(self):
        """
        This test proves INV-P53-3.

        When no governance response exists, P53 must produce an unbound
        envelope with no defaults. It must not introduce any fallback
        behavior or assume any governance decision.
        """
        ctx = make_context_without_governance_response()

        # Verify no governance response present
        assert ctx.p53_governance_response is None

        # Run P53
        envelope = maybe_run_p53(ctx)

        # Verify unbound envelope created
        assert envelope is not None
        assert envelope.bound is False

        # Verify no fallback values
        assert envelope.decision is None
        assert envelope.rationale_codes == ()
        assert envelope.audit_reference is None
        assert envelope.authority_id is None

        # Verify module does not contain fallback logic
        import symbolu.mechanical.pipeline.p53_policy_binding.p53_binder as binder_module
        binder_source = inspect.getsource(binder_module)

        # No default decisions or fallback logic
        assert 'default_decision' not in binder_source.lower()
        assert 'fallback' not in binder_source.lower()


# ============================================================================
# INV-P53-4: NO AUTHORITY ASSUMPTIONS
# ============================================================================


class TestINV_P53_4_NoAuthorityAssumptions:
    """
    INV-P53-4: P53 MUST NOT assume authority correctness.

    This test proves INV-P53-4.
    """

    def test_invalid_governance_structure_raises_error(self):
        """
        This test proves INV-P53-4.

        P53 validates structure only. If the structure is invalid,
        it raises an error rather than assuming what the authority
        intended. P53 does not validate authority correctness - it
        validates structural compliance only.
        """
        # Test with invalid decision value
        class InvalidResponse:
            decision = "INVALID_DECISION"
            rationale_codes = ()
            audit_reference = None

        with pytest.raises(GovernanceResponseValidationError):
            bind_governance_response(InvalidResponse())

        # Test with missing required field
        class MissingDecision:
            rationale_codes = ()
            audit_reference = None

        with pytest.raises(GovernanceResponseValidationError):
            bind_governance_response(MissingDecision())

        # Test with non-iterable rationale_codes
        class NonIterableRationale:
            decision = "ALLOW"
            rationale_codes = 12345  # Not iterable
            audit_reference = None

        with pytest.raises(GovernanceResponseValidationError):
            bind_governance_response(NonIterableRationale())

        # Test with missing audit_reference field
        class MissingAuditRef:
            decision = "ALLOW"
            rationale_codes = ()
            # audit_reference missing

        with pytest.raises(GovernanceResponseValidationError):
            bind_governance_response(MissingAuditRef())


# ============================================================================
# INV-P53-5: REMOVAL EQUIVALENCE
# ============================================================================


class TestINV_P53_5_RemovalEquivalence:
    """
    INV-P53-5: P53 MUST remain removable without changing cognitive outputs.

    This test proves INV-P53-5.
    """

    def test_removal_yields_identical_cognitive_outputs(self):
        """
        This test proves INV-P53-5.

        Removing P53 should not change any cognitive outputs.
        The system should be identical with or without P53.
        """
        # Create two identical contexts
        ctx_with_p53 = make_context_with_governance_response()
        ctx_without_p53 = make_context_with_governance_response()

        # Run P53 on one context only
        envelope = maybe_run_p53(ctx_with_p53)
        assert envelope is not None
        assert envelope.bound is True

        # Don't run P53 on the other

        # All cognitive outputs must be identical
        assert (
            ctx_with_p53.phase_20_snapshot.run_id ==
            ctx_without_p53.phase_20_snapshot.run_id
        )
        assert (
            ctx_with_p53.phase_20_snapshot.coherence_v3 ==
            ctx_without_p53.phase_20_snapshot.coherence_v3
        )
        assert (
            ctx_with_p53.phase_20_snapshot.drift_fusion_index ==
            ctx_without_p53.phase_20_snapshot.drift_fusion_index
        )
        assert (
            ctx_with_p53.p21_delivery_mode.delivery_mode ==
            ctx_without_p53.p21_delivery_mode.delivery_mode
        )
        assert (
            ctx_with_p53.p21_delivery_mode.delivery_allowed ==
            ctx_without_p53.p21_delivery_mode.delivery_allowed
        )
        assert (
            ctx_with_p53.p51_governance_readiness.ready ==
            ctx_without_p53.p51_governance_readiness.ready
        )
        assert (
            ctx_with_p53.p51_governance_readiness.readiness_level ==
            ctx_without_p53.p51_governance_readiness.readiness_level
        )
        assert (
            ctx_with_p53.p52_governance_request.snapshot_id ==
            ctx_without_p53.p52_governance_request.snapshot_id
        )

        # Only difference: p53_policy_binding field
        assert ctx_with_p53.p53_policy_binding is not None
        assert ctx_without_p53.p53_policy_binding is None


# ============================================================================
# STRUCTURAL: AUTHORITY_ID OPAQUE
# ============================================================================


class TestStructuralAuthorityIdOpaque:
    """
    Structural test: authority_id treated as opaque (no parsing).
    """

    def test_authority_id_treated_as_opaque(self):
        """
        authority_id must be treated as an opaque string.
        No parsing, no validation, no interpretation.
        """
        # Test with various opaque authority_id values
        opaque_ids = [
            "simple_id",
            "uuid:12345678-1234-1234-1234-123456789abc",
            "urn:authority:external:gov:123",
            "https://authority.example.com/id/456",
            "base64:SGVsbG8gV29ybGQ=",
            "",  # Empty string is valid
            "   spaces   ",  # Whitespace is preserved
            "special!@#$%^&*()chars",
            "unicode: émojis 🔒",
            "a" * 1000,  # Long string
        ]

        for opaque_id in opaque_ids:
            ctx = make_complete_context()
            ctx.p53_governance_response = GovernanceResponse(
                decision="ALLOW",
                rationale_codes=(),
                audit_reference=None,
            )
            ctx.p53_authority_id = opaque_id

            envelope = maybe_run_p53(ctx)

            # authority_id should be stored verbatim
            assert envelope.authority_id == opaque_id

        # Test with None authority_id
        ctx_none = make_complete_context()
        ctx_none.p53_governance_response = GovernanceResponse(
            decision="ALLOW",
            rationale_codes=(),
            audit_reference=None,
        )
        ctx_none.p53_authority_id = None

        envelope_none = maybe_run_p53(ctx_none)
        assert envelope_none.authority_id is None

        # Verify module does not parse authority_id
        import symbolu.mechanical.pipeline.p53_policy_binding.p53_binder as binder_module
        import symbolu.mechanical.pipeline.p53_policy_binding.p53_schema as schema_module

        binder_source = inspect.getsource(binder_module)
        schema_source = inspect.getsource(schema_module)

        # No parsing of authority_id
        for source in [binder_source, schema_source]:
            # No URL parsing
            assert "urlparse" not in source.lower()
            # No UUID parsing
            assert "uuid" not in source.lower()
            # No regex parsing of authority
            assert "authority_id.split" not in source
            assert "authority_id.parse" not in source
