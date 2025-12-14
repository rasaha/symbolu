"""
P55 Execution Authorization Boundary Test Suite

This test suite validates the P55 Execution Authorization Boundary phase.

Testing rule (STRICT):
    One test per invariant.
    No invariant -> no test.

Required Tests:
    - INV-P55-1: Default deny test
    - INV-P55-2: Cognition cannot authorize
    - INV-P55-3: Observer data ignored
    - INV-P55-4: Missing governance → deny
    - INV-P55-5: Determinism test
    - INV-P55-6: Remove P55 → no cognition change
    - Integration: Authorized execution path requires valid P53 + P54

Total tests: 7

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

from symbolu.mechanical.pipeline.p53_policy_binding import (
    GovernanceBindingEnvelope,
)

from symbolu.mechanical.pipeline.p54_audit_trace import (
    ComplianceAuditRecord,
)

from symbolu.mechanical.pipeline.p55_execution_boundary import (
    # Version
    P55_VERSION,
    # Denial reason codes
    DENIAL_NO_GOVERNANCE,
    DENIAL_GOVERNANCE_NOT_BOUND,
    DENIAL_GOVERNANCE_DECISION_NOT_ALLOW,
    DENIAL_BLOCKING_READINESS_FLAGS,
    DENIAL_NO_AUDIT_RECORD,
    DENIAL_NO_EXECUTION_PROPOSAL,
    DENIAL_EXECUTION_NOT_IN_ALLOWLIST,
    VALID_DENIAL_REASON_CODES,
    # Constants
    EXECUTION_AUTHORIZATION_DECISION_FIELDS,
    ALLOWED_ACTION_TYPES,
    # Dataclasses
    ExecutionProposalEnvelope,
    ExecutionAuthorizationDecision,
    # Factory functions
    create_denial_decision,
    create_authorization_decision,
    # Core function
    authorize_execution,
    run_p55_directly,
    # Integration
    maybe_run_p55,
    is_p55_disabled,
    has_p55_authorization,
    get_p55_authorization,
    is_execution_authorized,
)


# ============================================================================
# MOCK HELPERS
# ============================================================================


@dataclass
class MockP6Regime:
    """Mock P6 regime gate output (authoritative cognition phase)."""
    regime: str = "SPEECH"
    confidence: float = 0.95


@dataclass
class MockP7Discourse:
    """Mock P7 discourse envelope (authoritative cognition phase)."""
    discourse_type: str = "STATEMENT"
    pragmatic_force: float = 0.8


@dataclass
class MockP9Lexical:
    """Mock P9 lexical output (authoritative cognition phase)."""
    normalized_text: str = "hello world"
    token_count: int = 2


@dataclass
class MockP20Snapshot:
    """Mock P20 unified cognitive snapshot."""
    run_id: str = "test_run_123"
    coherence_v3: Optional[float] = 0.85
    drift_fusion_index: Optional[float] = 0.3
    temporal_entropy_diff: Optional[float] = 0.1


@dataclass
class MockP21DeliveryMode:
    """Mock P21 delivery mode decision."""
    delivery_mode: str = "TEXT_AND_VOICE"
    delivery_allowed: bool = True


@dataclass
class MockP30Observer:
    """Mock P30+ observer phase output (should be ignored by P55)."""
    observer_metric: float = 0.42
    observer_flag: bool = True
    observer_data: str = "observer_sensitive_data"


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
class MockP54AuditRecord:
    """Mock P54 compliance audit record."""
    execution_id: str = "exec_12345"
    timestamp_utc: str = "2024-01-15T12:00:00Z"
    governance_present: bool = True
    authority_id: Optional[str] = "authority_abc"
    governance_decision: Optional[str] = "ALLOW"
    rationale_codes: Tuple[str, ...] = ()
    affected_phases: Tuple[str, ...] = ()
    blocked_actions: Tuple[str, ...] = ()
    determinism_hash: str = "abc123def456"


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    # Authoritative cognitive phases (P55 MUST NOT read these)
    p6_regime: Optional[MockP6Regime] = None
    p7_discourse_envelope: Optional[MockP7Discourse] = None
    p9_lexical: Optional[MockP9Lexical] = None
    p21_delivery_mode: Optional[MockP21DeliveryMode] = None

    # Snapshot
    phase_20_snapshot: Optional[MockP20Snapshot] = None

    # Observer phases (P55 MUST NOT read these)
    p30_observer: Optional[MockP30Observer] = None
    p35_observer: Optional[MockP30Observer] = None
    p40_observer: Optional[MockP30Observer] = None

    # Governance phases (P55 MAY read these)
    p51_governance_readiness: Optional[MockP51Envelope] = None
    p53_policy_binding: Optional[GovernanceBindingEnvelope] = None
    p54_audit_record: Optional[MockP54AuditRecord] = None

    # Execution proposal (P55 MAY read this)
    p55_execution_proposal: Optional[ExecutionProposalEnvelope] = None

    # P55 output
    p55_execution_authorization: Optional[ExecutionAuthorizationDecision] = None

    # Control flags
    _p55_disabled: bool = False


def make_complete_context() -> MockPipelineContext:
    """Create a context with all required phases present."""
    return MockPipelineContext(
        # Cognitive phases
        p6_regime=MockP6Regime(),
        p7_discourse_envelope=MockP7Discourse(),
        p9_lexical=MockP9Lexical(),
        p21_delivery_mode=MockP21DeliveryMode(),
        phase_20_snapshot=MockP20Snapshot(),
        # Observer phases
        p30_observer=MockP30Observer(),
        p35_observer=MockP30Observer(),
        p40_observer=MockP30Observer(),
        # Governance phases (but no governance bound yet)
        p51_governance_readiness=MockP51Envelope(),
        p54_audit_record=MockP54AuditRecord(),
    )


def make_authorized_context(
    decision: str = "ALLOW",
    rationale_codes: Tuple[str, ...] = ("CODE_001", "CODE_002"),
    audit_reference: Optional[str] = "audit_ref_123",
    authority_id: Optional[str] = "authority_abc",
    action_type: str = "DELIVERY_TEXT",
) -> MockPipelineContext:
    """Create a context that should result in authorization."""
    ctx = make_complete_context()
    ctx.p53_policy_binding = GovernanceBindingEnvelope(
        bound=True,
        decision=decision,
        rationale_codes=rationale_codes,
        audit_reference=audit_reference,
        authority_id=authority_id,
    )
    ctx.p55_execution_proposal = ExecutionProposalEnvelope(
        action_id="action_001",
        action_type=action_type,
        target_scope=("delivery",),
    )
    return ctx


def make_unauthorized_context() -> MockPipelineContext:
    """Create a context that should result in denial (no governance)."""
    ctx = make_complete_context()
    # No p53_policy_binding - governance absent
    ctx.p55_execution_proposal = ExecutionProposalEnvelope(
        action_id="action_001",
        action_type="DELIVERY_TEXT",
        target_scope=("delivery",),
    )
    return ctx


# ============================================================================
# INV-P55-1: DEFAULT DENY
# ============================================================================


class TestINV_P55_1_DefaultDeny:
    """
    INV-P55-1: Execution is DENIED by default unless explicitly authorized.

    This test proves INV-P55-1.
    """

    def test_default_deny_when_no_inputs(self):
        """
        This test proves INV-P55-1.

        When no governance, no readiness, no audit record, and no proposal
        are present, execution MUST be denied by default.
        """
        # Empty context with nothing
        ctx = MockPipelineContext()

        # Run P55
        decision = maybe_run_p55(ctx)

        # MUST be denied
        assert decision is not None
        assert decision.authorized is False
        assert decision.denial_reason_code is not None
        assert decision.denial_reason_code in VALID_DENIAL_REASON_CODES

    def test_default_deny_with_audit_but_no_governance(self):
        """
        This test proves INV-P55-1.

        Even with audit record present, if governance is missing,
        execution MUST be denied by default.
        """
        ctx = MockPipelineContext(
            p54_audit_record=MockP54AuditRecord(),
            p55_execution_proposal=ExecutionProposalEnvelope(
                action_id="action_001",
                action_type="DELIVERY_TEXT",
                target_scope=("delivery",),
            ),
        )

        decision = maybe_run_p55(ctx)

        assert decision.authorized is False
        assert decision.denial_reason_code == DENIAL_NO_GOVERNANCE

    def test_default_deny_factory_function(self):
        """
        This test proves INV-P55-1.

        The create_denial_decision factory function must produce
        a properly formed denial decision.
        """
        decision = create_denial_decision(
            denial_reason_code=DENIAL_NO_GOVERNANCE,
            audit_record_id="exec_123",
        )

        assert decision.authorized is False
        assert decision.authority_id is None
        assert decision.denial_reason_code == DENIAL_NO_GOVERNANCE
        assert decision.audit_record_id == "exec_123"


# ============================================================================
# INV-P55-2: COGNITION CANNOT AUTHORIZE
# ============================================================================


class TestINV_P55_2_CognitionCannotAuthorize:
    """
    INV-P55-2: No cognition phase can override P55.

    This test proves INV-P55-2.
    """

    def test_cognition_phases_do_not_influence_authorization(self):
        """
        This test proves INV-P55-2.

        P55 must NOT read or be influenced by cognition phases (P1-P21).
        Authorization decision must be based ONLY on governance provenance.
        """
        # Create context with cognition phases but no governance
        ctx = MockPipelineContext(
            # All cognition phases present
            p6_regime=MockP6Regime(regime="SPEECH", confidence=1.0),
            p7_discourse_envelope=MockP7Discourse(discourse_type="COMMAND"),
            p9_lexical=MockP9Lexical(normalized_text="authorize this"),
            p21_delivery_mode=MockP21DeliveryMode(delivery_allowed=True),
            phase_20_snapshot=MockP20Snapshot(),
            # Audit record present
            p54_audit_record=MockP54AuditRecord(),
            # Proposal present
            p55_execution_proposal=ExecutionProposalEnvelope(
                action_id="action_001",
                action_type="DELIVERY_TEXT",
                target_scope=("delivery",),
            ),
            # BUT no governance
            p53_policy_binding=None,
        )

        decision = maybe_run_p55(ctx)

        # MUST be denied because no governance
        assert decision.authorized is False
        assert decision.denial_reason_code == DENIAL_NO_GOVERNANCE

    def test_p55_authorizer_does_not_import_cognition_modules(self):
        """
        This test proves INV-P55-2.

        The P55 authorizer module must NOT import any cognition modules.
        """
        import symbolu.mechanical.pipeline.p55_execution_boundary.p55_authorizer as authorizer_module

        # Get the source code
        source = inspect.getsource(authorizer_module)

        # Must NOT import cognition phases
        cognition_imports = [
            "from symbolu.mechanical.pipeline.p1_",
            "from symbolu.mechanical.pipeline.p2_",
            "from symbolu.mechanical.pipeline.p3_",
            "from symbolu.mechanical.pipeline.p4_",
            "from symbolu.mechanical.pipeline.p5_",
            "from symbolu.mechanical.pipeline.p6_",
            "from symbolu.mechanical.pipeline.p7_",
            "from symbolu.mechanical.pipeline.p8_",
            "from symbolu.mechanical.pipeline.p9_",
            "from symbolu.mechanical.pipeline.p10_",
            "from symbolu.mechanical.pipeline.p11_",
            "from symbolu.mechanical.pipeline.p12_",
            "from symbolu.mechanical.pipeline.p13_",
            "from symbolu.mechanical.pipeline.p14_",
            "from symbolu.mechanical.pipeline.p15_",
            "from symbolu.mechanical.pipeline.p16_",
            "from symbolu.mechanical.pipeline.p17_",
            "from symbolu.mechanical.pipeline.p18_",
            "from symbolu.mechanical.pipeline.p19_",
            "from symbolu.mechanical.pipeline.p20_",
            "from symbolu.mechanical.pipeline.p21_",
        ]

        for import_pattern in cognition_imports:
            assert import_pattern not in source, (
                f"P55 authorizer must not import cognition module: {import_pattern}"
            )


# ============================================================================
# INV-P55-3: OBSERVER DATA IGNORED
# ============================================================================


class TestINV_P55_3_ObserverDataIgnored:
    """
    INV-P55-3: No observer phase can influence P55.

    This test proves INV-P55-3.
    """

    def test_observer_phases_do_not_influence_authorization(self):
        """
        This test proves INV-P55-3.

        P55 must NOT read or be influenced by observer phases (P22-P49).
        """
        # Create two contexts: one with observers, one without
        ctx_with_observers = make_authorized_context()
        ctx_with_observers.p30_observer = MockP30Observer(observer_metric=0.99)
        ctx_with_observers.p35_observer = MockP30Observer(observer_flag=True)
        ctx_with_observers.p40_observer = MockP30Observer(observer_data="critical")

        ctx_without_observers = make_authorized_context()
        ctx_without_observers.p30_observer = None
        ctx_without_observers.p35_observer = None
        ctx_without_observers.p40_observer = None

        # Run P55 on both
        decision_with = maybe_run_p55(ctx_with_observers)
        decision_without = maybe_run_p55(ctx_without_observers)

        # Both must produce the same authorization decision
        assert decision_with.authorized == decision_without.authorized
        assert decision_with.denial_reason_code == decision_without.denial_reason_code

    def test_p55_does_not_access_observer_attributes(self):
        """
        This test proves INV-P55-3.

        P55 integration must not extract observer phase data from context.
        """
        import symbolu.mechanical.pipeline.p55_execution_boundary.p55_integration as integration_module

        source = inspect.getsource(integration_module)

        # Must NOT access observer phases (P22-P49)
        observer_patterns = [
            "p22_", "p23_", "p24_", "p25_", "p26_", "p27_", "p28_", "p29_",
            "p30_", "p31_", "p32_", "p33_", "p34_", "p35_", "p36_", "p37_",
            "p38_", "p39_", "p40_", "p41_", "p42_", "p43_", "p44_", "p45_",
            "p46_", "p47_", "p48_", "p49_",
        ]

        for pattern in observer_patterns:
            # Check for getattr calls to observer phases
            assert f'"{pattern}' not in source and f"'{pattern}" not in source, (
                f"P55 integration must not access observer phase: {pattern}"
            )


# ============================================================================
# INV-P55-4: AUTHORIZATION REQUIRES GOVERNANCE PROVENANCE
# ============================================================================


class TestINV_P55_4_AuthorizationRequiresGovernanceProvenance:
    """
    INV-P55-4: Authorization requires governance provenance.

    This test proves INV-P55-4.
    """

    def test_missing_governance_binding_denies(self):
        """
        This test proves INV-P55-4.

        Without GovernanceBindingEnvelope (P53), execution MUST be denied.
        """
        ctx = MockPipelineContext(
            p51_governance_readiness=MockP51Envelope(),
            p54_audit_record=MockP54AuditRecord(),
            p55_execution_proposal=ExecutionProposalEnvelope(
                action_id="action_001",
                action_type="DELIVERY_TEXT",
                target_scope=("delivery",),
            ),
            # Missing: p53_policy_binding
        )

        decision = maybe_run_p55(ctx)

        assert decision.authorized is False
        assert decision.denial_reason_code == DENIAL_NO_GOVERNANCE

    def test_unbound_governance_denies(self):
        """
        This test proves INV-P55-4.

        With bound=False governance, execution MUST be denied.
        """
        ctx = MockPipelineContext(
            p51_governance_readiness=MockP51Envelope(),
            p54_audit_record=MockP54AuditRecord(),
            p53_policy_binding=GovernanceBindingEnvelope(
                bound=False,
                decision=None,
                rationale_codes=(),
                audit_reference=None,
                authority_id=None,
            ),
            p55_execution_proposal=ExecutionProposalEnvelope(
                action_id="action_001",
                action_type="DELIVERY_TEXT",
                target_scope=("delivery",),
            ),
        )

        decision = maybe_run_p55(ctx)

        assert decision.authorized is False
        assert decision.denial_reason_code == DENIAL_GOVERNANCE_NOT_BOUND

    def test_deny_decision_denies(self):
        """
        This test proves INV-P55-4.

        With decision="DENY" governance, execution MUST be denied.
        """
        ctx = MockPipelineContext(
            p51_governance_readiness=MockP51Envelope(),
            p54_audit_record=MockP54AuditRecord(),
            p53_policy_binding=GovernanceBindingEnvelope(
                bound=True,
                decision="DENY",
                rationale_codes=("POLICY_VIOLATION",),
                audit_reference=None,
                authority_id="authority_abc",
            ),
            p55_execution_proposal=ExecutionProposalEnvelope(
                action_id="action_001",
                action_type="DELIVERY_TEXT",
                target_scope=("delivery",),
            ),
        )

        decision = maybe_run_p55(ctx)

        assert decision.authorized is False
        assert decision.denial_reason_code == DENIAL_GOVERNANCE_DECISION_NOT_ALLOW

    def test_defer_decision_denies(self):
        """
        This test proves INV-P55-4.

        With decision="DEFER" governance, execution MUST be denied.
        Only explicit "ALLOW" authorizes.
        """
        ctx = MockPipelineContext(
            p51_governance_readiness=MockP51Envelope(),
            p54_audit_record=MockP54AuditRecord(),
            p53_policy_binding=GovernanceBindingEnvelope(
                bound=True,
                decision="DEFER",
                rationale_codes=("NEEDS_REVIEW",),
                audit_reference=None,
                authority_id="authority_abc",
            ),
            p55_execution_proposal=ExecutionProposalEnvelope(
                action_id="action_001",
                action_type="DELIVERY_TEXT",
                target_scope=("delivery",),
            ),
        )

        decision = maybe_run_p55(ctx)

        assert decision.authorized is False
        assert decision.denial_reason_code == DENIAL_GOVERNANCE_DECISION_NOT_ALLOW


# ============================================================================
# INV-P55-5: DETERMINISM
# ============================================================================


class TestINV_P55_5_Determinism:
    """
    INV-P55-5: P55 must be deterministic and replayable.

    This test proves INV-P55-5.
    """

    def test_identical_inputs_produce_identical_outputs(self):
        """
        This test proves INV-P55-5.

        Given identical inputs, P55 must produce identical outputs.
        """
        # Create identical contexts
        ctx1 = make_authorized_context(
            decision="ALLOW",
            authority_id="auth_123",
            action_type="DELIVERY_TEXT",
        )
        ctx2 = make_authorized_context(
            decision="ALLOW",
            authority_id="auth_123",
            action_type="DELIVERY_TEXT",
        )

        # Run P55 multiple times
        decisions = []
        for _ in range(10):
            decision1 = run_p55_directly(
                governance_binding=ctx1.p53_policy_binding,
                governance_readiness=ctx1.p51_governance_readiness,
                audit_record=ctx1.p54_audit_record,
                execution_proposal=ctx1.p55_execution_proposal,
            )
            decision2 = run_p55_directly(
                governance_binding=ctx2.p53_policy_binding,
                governance_readiness=ctx2.p51_governance_readiness,
                audit_record=ctx2.p54_audit_record,
                execution_proposal=ctx2.p55_execution_proposal,
            )
            decisions.append((decision1, decision2))

        # All decisions must be identical
        for d1, d2 in decisions:
            assert d1.authorized == d2.authorized
            assert d1.authority_id == d2.authority_id
            assert d1.denial_reason_code == d2.denial_reason_code

    def test_p55_has_no_random_or_time_dependencies(self):
        """
        This test proves INV-P55-5.

        P55 authorizer must not use random or time-based logic.
        """
        import symbolu.mechanical.pipeline.p55_execution_boundary.p55_authorizer as authorizer_module

        source = inspect.getsource(authorizer_module)

        # Must NOT use random
        assert "import random" not in source
        assert "from random" not in source
        assert "random." not in source

        # Must NOT use time
        assert "import time" not in source
        assert "from time" not in source
        assert "time." not in source

        # Must NOT use datetime (for current time)
        assert "datetime.now" not in source
        assert "datetime.utcnow" not in source


# ============================================================================
# INV-P55-6: REMOVAL EQUIVALENCE
# ============================================================================


class TestINV_P55_6_RemovalEquivalence:
    """
    INV-P55-6: P55 must be removable without altering cognition.

    This test proves INV-P55-6.
    """

    def test_pipeline_cognition_unchanged_with_p55_disabled(self):
        """
        This test proves INV-P55-6.

        Disabling P55 must not change any cognitive phase outputs.
        All upstream phases (P1-P54) must be identical.
        """
        # Create two identical contexts
        ctx_with_p55 = make_authorized_context()
        ctx_without_p55 = make_authorized_context()

        # Disable P55 on one context
        ctx_without_p55._p55_disabled = True

        # Capture original cognitive state
        original_p6 = ctx_with_p55.p6_regime.regime
        original_p7 = ctx_with_p55.p7_discourse_envelope.discourse_type
        original_p9 = ctx_with_p55.p9_lexical.normalized_text
        original_p21 = ctx_with_p55.p21_delivery_mode.delivery_mode
        original_p51 = ctx_with_p55.p51_governance_readiness.ready
        original_p53 = ctx_with_p55.p53_policy_binding.bound
        original_p54 = ctx_with_p55.p54_audit_record.execution_id

        # Run P55 on enabled context
        decision = maybe_run_p55(ctx_with_p55)
        assert decision is not None

        # Run P55 on disabled context
        no_decision = maybe_run_p55(ctx_without_p55)
        assert no_decision is None

        # Verify ALL cognitive outputs unchanged
        assert ctx_with_p55.p6_regime.regime == original_p6
        assert ctx_without_p55.p6_regime.regime == original_p6

        assert ctx_with_p55.p7_discourse_envelope.discourse_type == original_p7
        assert ctx_without_p55.p7_discourse_envelope.discourse_type == original_p7

        assert ctx_with_p55.p9_lexical.normalized_text == original_p9
        assert ctx_without_p55.p9_lexical.normalized_text == original_p9

        assert ctx_with_p55.p21_delivery_mode.delivery_mode == original_p21
        assert ctx_without_p55.p21_delivery_mode.delivery_mode == original_p21

        # Governance phases unchanged
        assert ctx_with_p55.p51_governance_readiness.ready == original_p51
        assert ctx_without_p55.p51_governance_readiness.ready == original_p51

        assert ctx_with_p55.p53_policy_binding.bound == original_p53
        assert ctx_without_p55.p53_policy_binding.bound == original_p53

        assert ctx_with_p55.p54_audit_record.execution_id == original_p54
        assert ctx_without_p55.p54_audit_record.execution_id == original_p54

        # Only difference: p55_execution_authorization field
        assert ctx_with_p55.p55_execution_authorization is not None
        assert ctx_without_p55.p55_execution_authorization is None


# ============================================================================
# INTEGRATION TEST: AUTHORIZED EXECUTION PATH
# ============================================================================


class TestIntegration_AuthorizedExecutionPath:
    """
    Integration test: Authorized execution path requires valid P53 + P54.

    This test proves the full authorization flow.
    """

    def test_full_authorization_flow_with_valid_p53_p54(self):
        """
        This test proves the full authorization flow.

        Authorization requires:
            1. Valid P53 GovernanceBindingEnvelope with bound=True, decision="ALLOW"
            2. Valid P54 ComplianceAuditRecord
            3. Valid P51 GovernanceReadinessEnvelope with no blocking factors
            4. Valid ExecutionProposalEnvelope with action in allow-list
        """
        # Create fully authorized context
        ctx = make_authorized_context(
            decision="ALLOW",
            rationale_codes=("POLICY_COMPLIANT",),
            audit_reference="audit_ref_full",
            authority_id="authority_full_auth",
            action_type="DELIVERY_TEXT",
        )

        # Verify P53 is valid
        assert ctx.p53_policy_binding is not None
        assert ctx.p53_policy_binding.bound is True
        assert ctx.p53_policy_binding.decision == "ALLOW"

        # Verify P54 is valid
        assert ctx.p54_audit_record is not None
        assert ctx.p54_audit_record.execution_id is not None

        # Verify P51 is valid (no blocking factors)
        assert ctx.p51_governance_readiness is not None
        assert len(ctx.p51_governance_readiness.blocking_factors) == 0

        # Verify proposal is valid
        assert ctx.p55_execution_proposal is not None
        assert ctx.p55_execution_proposal.action_type in ALLOWED_ACTION_TYPES

        # Run P55
        decision = maybe_run_p55(ctx)

        # MUST be authorized
        assert decision is not None
        assert decision.authorized is True
        assert decision.authority_id == "authority_full_auth"
        assert decision.denial_reason_code is None
        assert decision.audit_record_id is not None

        # Verify attached to context
        assert ctx.p55_execution_authorization is decision
        assert is_execution_authorized(ctx) is True

    def test_authorization_denied_when_action_not_in_allowlist(self):
        """
        Even with valid P53 + P54, if action is not in allow-list, deny.
        """
        ctx = make_authorized_context(
            decision="ALLOW",
            authority_id="authority_xyz",
            action_type="FORBIDDEN_ACTION",  # Not in ALLOWED_ACTION_TYPES
        )

        decision = maybe_run_p55(ctx)

        assert decision.authorized is False
        assert decision.denial_reason_code == DENIAL_EXECUTION_NOT_IN_ALLOWLIST

    def test_authorization_denied_when_blocking_factors_exist(self):
        """
        Even with valid P53 + P54, if P51 has blocking factors, deny.
        """
        ctx = make_authorized_context(
            decision="ALLOW",
            authority_id="authority_xyz",
            action_type="DELIVERY_TEXT",
        )
        ctx.p51_governance_readiness = MockP51Envelope(
            ready=False,
            readiness_level="NOT_READY",
            blocking_factors=("MISSING_PHASE", "DRIFT_TOO_HIGH"),
        )

        decision = maybe_run_p55(ctx)

        assert decision.authorized is False
        assert decision.denial_reason_code == DENIAL_BLOCKING_READINESS_FLAGS

    def test_authorization_denied_when_audit_record_missing(self):
        """
        Even with valid P53, if P54 audit record is missing, deny.
        """
        ctx = make_authorized_context(
            decision="ALLOW",
            authority_id="authority_xyz",
            action_type="DELIVERY_TEXT",
        )
        ctx.p54_audit_record = None

        decision = maybe_run_p55(ctx)

        assert decision.authorized is False
        assert decision.denial_reason_code == DENIAL_NO_AUDIT_RECORD
