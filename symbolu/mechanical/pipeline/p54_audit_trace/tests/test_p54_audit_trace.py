"""
P54 Audit & Compliance Trace Engine Test Suite

This test suite validates the P54 Audit & Compliance Trace Engine phase.

Testing rule (STRICT):
    One test per invariant.
    No invariant -> no test.

Required Tests:
    - INV-P54-1: No upstream influence test
    - INV-P54-2: Identical inputs → identical audit record
    - INV-P54-3: authority_id surfaced verbatim
    - INV-P54-4: No inferred explanation fields
    - INV-P54-5: Pipeline identical with P54 disabled
    - Determinism: Hash unchanged across runs

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
    GovernanceBindingEnvelope,
)

from symbolu.mechanical.pipeline.p54_audit_trace import (
    # Version
    P54_VERSION,
    # Constants
    COMPLIANCE_AUDIT_RECORD_FIELDS,
    AUTHORITATIVE_PHASES,
    # Dataclasses
    ComplianceAuditRecord,
    # Hash computation
    compute_determinism_hash,
    # Collection functions
    collect_authoritative_outputs,
    extract_governance_info,
    # Core creation
    create_audit_record,
    run_p54_directly,
    # Integration
    maybe_run_p54,
    # Helpers
    is_p54_disabled,
    has_p54_audit_record,
    get_p54_audit_record,
    get_determinism_hash,
)


# ============================================================================
# MOCK HELPERS
# ============================================================================


@dataclass
class MockP6Regime:
    """Mock P6 regime gate output."""
    regime: str = "SPEECH"
    confidence: float = 0.95


@dataclass
class MockP7Discourse:
    """Mock P7 discourse envelope."""
    discourse_type: str = "STATEMENT"
    pragmatic_force: float = 0.8


@dataclass
class MockP9Lexical:
    """Mock P9 lexical output."""
    normalized_text: str = "hello world"
    token_count: int = 2


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
    # Execution identity
    execution_id: str = "exec_12345"
    timestamp_utc: str = "2024-01-15T12:00:00Z"

    # Authoritative cognitive phases
    p6_regime: Optional[MockP6Regime] = None
    p7_discourse_envelope: Optional[MockP7Discourse] = None
    p9_lexical: Optional[MockP9Lexical] = None
    p21_delivery_mode: Optional[MockP21DeliveryMode] = None

    # Upstream phases
    phase_20_snapshot: Optional[MockP20Snapshot] = None
    p51_governance_readiness: Optional[MockP51Envelope] = None
    p52_governance_request: Optional[MockP52Request] = None

    # P53 binding
    p53_policy_binding: Optional[GovernanceBindingEnvelope] = None

    # P54 output
    p54_audit_record: Optional[ComplianceAuditRecord] = None

    # Control flags
    _p54_disabled: bool = False


def make_complete_context() -> MockPipelineContext:
    """Create a context with all required phases present (no governance)."""
    return MockPipelineContext(
        p6_regime=MockP6Regime(),
        p7_discourse_envelope=MockP7Discourse(),
        p9_lexical=MockP9Lexical(),
        p21_delivery_mode=MockP21DeliveryMode(),
        phase_20_snapshot=MockP20Snapshot(),
        p51_governance_readiness=MockP51Envelope(),
        p52_governance_request=MockP52Request(),
    )


def make_context_with_governance(
    decision: str = "ALLOW",
    rationale_codes: Tuple[str, ...] = ("CODE_001", "CODE_002"),
    audit_reference: Optional[str] = "audit_ref_123",
    authority_id: Optional[str] = "authority_abc",
) -> MockPipelineContext:
    """Create a context with governance bound."""
    ctx = make_complete_context()
    ctx.p53_policy_binding = GovernanceBindingEnvelope(
        bound=True,
        decision=decision,
        rationale_codes=rationale_codes,
        audit_reference=audit_reference,
        authority_id=authority_id,
    )
    return ctx


def make_context_without_governance() -> MockPipelineContext:
    """Create a context without governance (unbound)."""
    ctx = make_complete_context()
    # No p53_policy_binding - governance absent
    return ctx


# ============================================================================
# INV-P54-1: NO UPSTREAM INFLUENCE
# ============================================================================


class TestINV_P54_1_NoUpstreamInfluence:
    """
    INV-P54-1: P54 MUST NOT influence execution, governance, or cognition.

    This test proves INV-P54-1.
    """

    def test_no_upstream_influence(self):
        """
        This test proves INV-P54-1.

        P54 must not modify any upstream phase outputs when creating
        audit records. All cognitive and governance phase outputs must
        remain identical before and after P54 runs.
        """
        ctx = make_context_with_governance()

        # Capture original values
        original_p6_regime = ctx.p6_regime.regime
        original_p6_confidence = ctx.p6_regime.confidence
        original_p7_discourse = ctx.p7_discourse_envelope.discourse_type
        original_p9_text = ctx.p9_lexical.normalized_text
        original_p21_mode = ctx.p21_delivery_mode.delivery_mode
        original_p20_run_id = ctx.phase_20_snapshot.run_id
        original_p20_coherence = ctx.phase_20_snapshot.coherence_v3
        original_p51_ready = ctx.p51_governance_readiness.ready
        original_p52_snapshot_id = ctx.p52_governance_request.snapshot_id
        original_p53_bound = ctx.p53_policy_binding.bound
        original_p53_decision = ctx.p53_policy_binding.decision
        original_p53_authority = ctx.p53_policy_binding.authority_id

        # Run P54
        record = maybe_run_p54(ctx)

        # Verify P54 ran successfully
        assert record is not None
        assert isinstance(record, ComplianceAuditRecord)

        # Verify ALL upstream values unchanged
        assert ctx.p6_regime.regime == original_p6_regime
        assert ctx.p6_regime.confidence == original_p6_confidence
        assert ctx.p7_discourse_envelope.discourse_type == original_p7_discourse
        assert ctx.p9_lexical.normalized_text == original_p9_text
        assert ctx.p21_delivery_mode.delivery_mode == original_p21_mode
        assert ctx.phase_20_snapshot.run_id == original_p20_run_id
        assert ctx.phase_20_snapshot.coherence_v3 == original_p20_coherence
        assert ctx.p51_governance_readiness.ready == original_p51_ready
        assert ctx.p52_governance_request.snapshot_id == original_p52_snapshot_id
        assert ctx.p53_policy_binding.bound == original_p53_bound
        assert ctx.p53_policy_binding.decision == original_p53_decision
        assert ctx.p53_policy_binding.authority_id == original_p53_authority

        # Verify P54 only writes to p54_audit_record
        assert hasattr(ctx, "p54_audit_record")
        assert ctx.p54_audit_record is record


# ============================================================================
# INV-P54-2: REPRODUCIBLE AUDIT RECORDS
# ============================================================================


class TestINV_P54_2_ReproducibleAuditRecords:
    """
    INV-P54-2: Audit records MUST be reproducible for identical inputs.

    This test proves INV-P54-2.
    """

    def test_identical_inputs_produce_identical_record(self):
        """
        This test proves INV-P54-2.

        Given identical pipeline inputs (same execution ID, timestamp,
        and phase outputs), the audit record must be bitwise identical,
        including the determinism hash.
        """
        # Create two identical contexts
        ctx1 = make_context_with_governance(
            decision="DENY",
            rationale_codes=("REASON_A", "REASON_B"),
            audit_reference="audit_xyz",
            authority_id="auth_123",
        )
        ctx2 = make_context_with_governance(
            decision="DENY",
            rationale_codes=("REASON_A", "REASON_B"),
            audit_reference="audit_xyz",
            authority_id="auth_123",
        )

        # Use identical execution IDs and timestamps
        execution_id = "exec_identical_test"
        timestamp_utc = "2024-01-15T12:00:00Z"

        # Create audit records
        record1 = create_audit_record(execution_id, timestamp_utc, ctx1)
        record2 = create_audit_record(execution_id, timestamp_utc, ctx2)

        # Verify all fields are identical
        assert record1.execution_id == record2.execution_id
        assert record1.timestamp_utc == record2.timestamp_utc
        assert record1.governance_present == record2.governance_present
        assert record1.authority_id == record2.authority_id
        assert record1.governance_decision == record2.governance_decision
        assert record1.rationale_codes == record2.rationale_codes
        assert record1.affected_phases == record2.affected_phases
        assert record1.blocked_actions == record2.blocked_actions

        # CRITICAL: Determinism hash must be identical
        assert record1.determinism_hash == record2.determinism_hash

        # Verify dict representations are identical
        assert record1.to_dict() == record2.to_dict()


# ============================================================================
# INV-P54-3: AUTHORITY PROVENANCE EXPLICIT
# ============================================================================


class TestINV_P54_3_AuthorityProvenanceExplicit:
    """
    INV-P54-3: Audit records MUST expose authority provenance explicitly.

    This test proves INV-P54-3.
    """

    def test_authority_id_surfaced_verbatim(self):
        """
        This test proves INV-P54-3.

        The authority_id from P53 must be surfaced verbatim in the
        audit record without interpretation or modification.
        """
        # Test various authority IDs
        test_authority_ids = [
            "simple_authority",
            "urn:authority:external:gov:123",
            "https://authority.example.com/id/456",
            "uuid:12345678-1234-1234-1234-123456789abc",
            "",  # Empty string
            "   spaces   ",  # Whitespace preserved
            "special!@#$%^&*()chars",
            "unicode_authority_",
        ]

        for authority_id in test_authority_ids:
            ctx = make_context_with_governance(
                decision="ALLOW",
                rationale_codes=(),
                audit_reference=None,
                authority_id=authority_id,
            )

            record = create_audit_record("exec_123", "2024-01-15T12:00:00Z", ctx)

            # authority_id must be surfaced verbatim
            assert record.authority_id == authority_id
            assert record.governance_present is True

        # Test with None authority_id
        ctx_none = make_context_with_governance(
            decision="ALLOW",
            rationale_codes=(),
            audit_reference=None,
            authority_id=None,
        )

        record_none = create_audit_record("exec_123", "2024-01-15T12:00:00Z", ctx_none)
        assert record_none.authority_id is None
        assert record_none.governance_present is True

        # Test with no governance at all
        ctx_no_gov = make_context_without_governance()
        record_no_gov = create_audit_record(
            "exec_123", "2024-01-15T12:00:00Z", ctx_no_gov
        )
        assert record_no_gov.authority_id is None
        assert record_no_gov.governance_present is False


# ============================================================================
# INV-P54-4: NO INFERRED EXPLANATIONS
# ============================================================================


class TestINV_P54_4_NoInferredExplanations:
    """
    INV-P54-4: Audit records MUST NOT contain inferred explanations.

    This test proves INV-P54-4.
    """

    def test_no_inferred_explanation_fields(self):
        """
        This test proves INV-P54-4.

        The audit record must contain only factual data from upstream
        phases. It must not contain any fields that explain, interpret,
        or infer meaning from the governance decision.
        """
        ctx = make_context_with_governance(
            decision="DENY",
            rationale_codes=("CODE_X", "CODE_Y"),
            audit_reference="ref_123",
            authority_id="auth_abc",
        )

        record = create_audit_record("exec_123", "2024-01-15T12:00:00Z", ctx)

        # Check that record only has allowed fields
        record_dict = record.to_dict()
        allowed_fields = COMPLIANCE_AUDIT_RECORD_FIELDS

        for field_name in record_dict.keys():
            assert field_name in allowed_fields, (
                f"Unexpected field '{field_name}' in audit record"
            )

        # Verify no explanation fields exist
        forbidden_field_patterns = [
            "explanation",
            "reason",
            "why",
            "because",
            "interpretation",
            "meaning",
            "intent",
            "inferred",
            "derived",
            "computed_reason",
            "human_readable",
        ]

        for pattern in forbidden_field_patterns:
            for field_name in record_dict.keys():
                assert pattern not in field_name.lower(), (
                    f"Field '{field_name}' appears to be an explanation field"
                )

        # Verify module source does not contain explanation logic
        import symbolu.mechanical.pipeline.p54_audit_trace.p54_collector as collector_module
        collector_source = inspect.getsource(collector_module)

        # No explanation generation
        assert "explain" not in collector_source.lower() or "explanation" not in collector_source.lower()
        assert "infer_" not in collector_source.lower()
        assert "derive_" not in collector_source.lower()


# ============================================================================
# INV-P54-5: REMOVAL EQUIVALENCE
# ============================================================================


class TestINV_P54_5_RemovalEquivalence:
    """
    INV-P54-5: Removing P54 MUST NOT change system behavior.

    This test proves INV-P54-5.
    """

    def test_pipeline_identical_with_p54_disabled(self):
        """
        This test proves INV-P54-5.

        The pipeline must behave identically with P54 enabled or disabled.
        All cognitive and governance outputs must be the same.
        """
        # Create two identical contexts
        ctx_with_p54 = make_context_with_governance()
        ctx_without_p54 = make_context_with_governance()

        # Disable P54 on one context
        ctx_without_p54._p54_disabled = True

        # Run P54 on enabled context
        record = maybe_run_p54(ctx_with_p54)
        assert record is not None

        # Run P54 on disabled context
        no_record = maybe_run_p54(ctx_without_p54)
        assert no_record is None

        # All upstream outputs must be identical
        assert (
            ctx_with_p54.p6_regime.regime ==
            ctx_without_p54.p6_regime.regime
        )
        assert (
            ctx_with_p54.p7_discourse_envelope.discourse_type ==
            ctx_without_p54.p7_discourse_envelope.discourse_type
        )
        assert (
            ctx_with_p54.p9_lexical.normalized_text ==
            ctx_without_p54.p9_lexical.normalized_text
        )
        assert (
            ctx_with_p54.p21_delivery_mode.delivery_mode ==
            ctx_without_p54.p21_delivery_mode.delivery_mode
        )
        assert (
            ctx_with_p54.phase_20_snapshot.run_id ==
            ctx_without_p54.phase_20_snapshot.run_id
        )
        assert (
            ctx_with_p54.p51_governance_readiness.ready ==
            ctx_without_p54.p51_governance_readiness.ready
        )
        assert (
            ctx_with_p54.p52_governance_request.snapshot_id ==
            ctx_without_p54.p52_governance_request.snapshot_id
        )
        assert (
            ctx_with_p54.p53_policy_binding.bound ==
            ctx_without_p54.p53_policy_binding.bound
        )
        assert (
            ctx_with_p54.p53_policy_binding.decision ==
            ctx_without_p54.p53_policy_binding.decision
        )

        # Only difference: p54_audit_record field
        assert ctx_with_p54.p54_audit_record is not None
        assert ctx_without_p54.p54_audit_record is None


# ============================================================================
# DETERMINISM TEST: HASH UNCHANGED ACROSS RUNS
# ============================================================================


class TestDeterminismHashUnchangedAcrossRuns:
    """
    Determinism test: Hash unchanged across runs.

    This test proves that the determinism hash is stable and reproducible.
    """

    def test_hash_unchanged_across_multiple_runs(self):
        """
        The determinism hash must be identical when computed multiple times
        for the same input data, proving INV-P54-2 for hash specifically.
        """
        # Fixed input data
        ctx = make_context_with_governance(
            decision="DEFER",
            rationale_codes=("A", "B", "C"),
            audit_reference="ref_determinism_test",
            authority_id="auth_determinism_test",
        )

        execution_id = "exec_determinism"
        timestamp_utc = "2024-06-15T18:30:00Z"

        # Compute hash multiple times
        hashes = []
        for _ in range(10):
            record = create_audit_record(execution_id, timestamp_utc, ctx)
            hashes.append(record.determinism_hash)

        # All hashes must be identical
        assert len(set(hashes)) == 1, "Hash changed across runs"

        # Verify hash is non-empty and valid hex
        assert len(hashes[0]) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in hashes[0])

        # Verify hash changes when inputs change
        ctx_different = make_context_with_governance(
            decision="ALLOW",  # Different decision
            rationale_codes=("A", "B", "C"),
            audit_reference="ref_determinism_test",
            authority_id="auth_determinism_test",
        )

        record_different = create_audit_record(
            execution_id, timestamp_utc, ctx_different
        )

        # Hash must be different for different inputs
        assert record_different.determinism_hash != hashes[0]

        # Test that timestamp is NOT included in hash
        # (Same inputs with different timestamps should produce same hash)
        record_diff_timestamp = create_audit_record(
            execution_id,
            "2025-12-25T00:00:00Z",  # Different timestamp
            ctx,  # Same context
        )

        # Hash should be same because timestamp is not in hash
        assert record_diff_timestamp.determinism_hash == hashes[0]
