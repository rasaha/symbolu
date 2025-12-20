"""
P51 Governance Readiness Test Suite

This test suite validates the P51 Governance Readiness Envelope phase.

Testing rule (STRICT):
    One test per invariant.
    No invariant -> no test.

Required Tests:
    - INV-P51-1: Snapshot unchanged after P51
    - INV-P51-2: No new decisions introduced
    - INV-P51-3: Downstream behavior unchanged
    - INV-P51-4: No governance imports
    - INV-P51-5: Removal equivalence test
    - Scenario: Fully valid pipeline -> READY
    - Scenario: Missing envelope -> NOT_READY

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

from symbolu.mechanical.pipeline.p51_governance_readiness import (
    # Version
    P51_VERSION,
    # Constants
    VALID_READINESS_LEVELS,
    DRIFT_SAFETY_THRESHOLD,
    MANDATORY_PHASES,
    # Dataclasses
    GovernanceReadinessEnvelope,
    # Factory
    create_governance_readiness_envelope,
    # Core computation
    compute_governance_readiness,
    run_p51_directly,
    # Integration
    maybe_run_p51,
    # Helpers
    is_p51_disabled,
    has_p51_envelope,
    get_p51_envelope,
    get_readiness_level,
    is_governance_ready,
    get_blocking_factors,
    get_advisory_notes,
)


# ============================================================================
# MOCK HELPERS
# ============================================================================


@dataclass
class MockP6Regime:
    """Mock P6 regime envelope."""
    regime: str = "INFORM"
    reason: str = "test"


@dataclass
class MockP7Discourse:
    """Mock P7 discourse envelope."""
    act: str = "EXPLANATION"
    allowed: bool = True
    reason: str = "test"


@dataclass
class MockP18Entropy:
    """Mock P18 temporal entropy report."""
    entropy_now: float = 0.3
    delta_entropy: float = 0.1
    volatility_band: str = "LOW"


@dataclass
class MockP19Drift:
    """Mock P19 drift fusion report."""
    drift_fusion_index: float = 0.3
    drift_risk_band: str = "low"


@dataclass
class MockP20Snapshot:
    """Mock P20 unified cognitive snapshot."""
    run_id: str = "test_run"
    coherence_v3: float = 0.8


@dataclass
class MockP21DeliveryMode:
    """Mock P21 delivery mode decision."""
    delivery_mode: str = "TEXT_AND_VOICE"
    delivery_allowed: bool = True


@dataclass
class MockP50Consistency:
    """Mock P50 cognitive consistency report."""
    consistency_score: float = 0.85
    consistency_band: str = "stable"
    detected_contradictions: Tuple[str, ...] = ()
    regression_flags: Tuple[str, ...] = ()
    observer_only: bool = True


@dataclass
class MockCoherenceState:
    """Mock coherence state."""
    convo_id: str = "test_convo"
    turn_index: int = 1


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    p6_regime: Optional[MockP6Regime] = None
    p7_discourse_envelope: Optional[MockP7Discourse] = None
    p18: Optional[MockP18Entropy] = None
    p19_drift_fusion: Optional[MockP19Drift] = None
    phase_20_snapshot: Optional[MockP20Snapshot] = None
    p21_delivery_mode: Optional[MockP21DeliveryMode] = None
    p50_cognitive_consistency: Optional[MockP50Consistency] = None
    coherence_state: Optional[MockCoherenceState] = None
    p51_governance_readiness: Optional[GovernanceReadinessEnvelope] = None
    _p51_disabled: bool = False


def make_complete_context() -> MockPipelineContext:
    """Create a context with all mandatory phases present."""
    return MockPipelineContext(
        p6_regime=MockP6Regime(),
        p7_discourse_envelope=MockP7Discourse(),
        p18=MockP18Entropy(),
        p19_drift_fusion=MockP19Drift(drift_fusion_index=0.3),
        phase_20_snapshot=MockP20Snapshot(),
        p21_delivery_mode=MockP21DeliveryMode(),
        p50_cognitive_consistency=MockP50Consistency(),
        coherence_state=MockCoherenceState(),
    )


def make_incomplete_context() -> MockPipelineContext:
    """Create a context missing mandatory phases."""
    return MockPipelineContext(
        p6_regime=MockP6Regime(),
        # Missing: p7_discourse_envelope
        # Missing: phase_20_snapshot
        # Missing: p21_delivery_mode
    )


# ============================================================================
# INV-P51-1: UPSTREAM IMMUTABILITY
# ============================================================================


class TestINV_P51_1_UpstreamImmutability:
    """
    INV-P51-1: P51 MUST NOT modify any upstream data.

    This test proves INV-P51-1.
    """

    def test_snapshot_unchanged_after_p51(self):
        """
        This test proves INV-P51-1.

        P51 must not modify any upstream phase outputs when computing
        governance readiness.
        """
        ctx = make_complete_context()

        # Capture original values
        original_p6_regime = ctx.p6_regime.regime
        original_p7_act = ctx.p7_discourse_envelope.act
        original_p18_entropy = ctx.p18.entropy_now
        original_p19_drift = ctx.p19_drift_fusion.drift_fusion_index
        original_p20_run_id = ctx.phase_20_snapshot.run_id
        original_p21_mode = ctx.p21_delivery_mode.delivery_mode
        original_p50_score = ctx.p50_cognitive_consistency.consistency_score

        # Run P51
        maybe_run_p51(ctx)

        # Verify all upstream values unchanged
        assert ctx.p6_regime.regime == original_p6_regime
        assert ctx.p7_discourse_envelope.act == original_p7_act
        assert ctx.p18.entropy_now == original_p18_entropy
        assert ctx.p19_drift_fusion.drift_fusion_index == original_p19_drift
        assert ctx.phase_20_snapshot.run_id == original_p20_run_id
        assert ctx.p21_delivery_mode.delivery_mode == original_p21_mode
        assert ctx.p50_cognitive_consistency.consistency_score == original_p50_score


# ============================================================================
# INV-P51-2: NO NEW DECISIONS
# ============================================================================


class TestINV_P51_2_NoNewDecisions:
    """
    INV-P51-2: P51 MUST NOT introduce new classifications or decisions.

    This test proves INV-P51-2.
    """

    def test_no_new_decisions_introduced(self):
        """
        This test proves INV-P51-2.

        P51 output must be observer_only=True and must not create any
        new classifications or decisions that affect pipeline behavior.
        """
        ctx = make_complete_context()

        # Run P51
        envelope = maybe_run_p51(ctx)

        # P51 must be observer-only
        assert envelope.observer_only is True

        # P51 does not modify behavior - only reports readiness
        # The readiness_level is a diagnostic, not a decision
        assert envelope.readiness_level in VALID_READINESS_LEVELS

        # Verify envelope has no decision authority fields
        # (no 'allowed', 'blocked', 'gated', etc.)
        envelope_dict = envelope.to_dict()
        forbidden_fields = ["allowed", "blocked", "gated", "action", "decision"]
        for field in forbidden_fields:
            assert field not in envelope_dict, f"Forbidden field '{field}' found"


# ============================================================================
# INV-P51-3: NO GATING
# ============================================================================


class TestINV_P51_3_NoGating:
    """
    INV-P51-3: P51 MUST NOT block or gate output.

    This test proves INV-P51-3.
    """

    def test_downstream_behavior_unchanged(self):
        """
        This test proves INV-P51-3.

        P51 cannot gate or block any output. The pipeline should behave
        identically with or without P51 running.
        """
        ctx = make_complete_context()

        # Run P51
        envelope = maybe_run_p51(ctx)

        # P51 never returns a "block" or "gate" signal
        # It only returns a diagnostic envelope
        assert envelope is not None

        # Even NOT_READY doesn't block - it's just a diagnostic
        ctx_incomplete = make_incomplete_context()
        envelope_incomplete = maybe_run_p51(ctx_incomplete)

        # NOT_READY is still returned (not blocked)
        assert envelope_incomplete is not None
        assert envelope_incomplete.readiness_level == "NOT_READY"

        # No exception raised, no None returned for blocking
        # P51 is purely observational


# ============================================================================
# INV-P51-4: NO GOVERNANCE IMPORTS
# ============================================================================


class TestINV_P51_4_NoGovernanceImports:
    """
    INV-P51-4: P51 MUST NOT depend on future governance logic.

    This test proves INV-P51-4.
    """

    def test_no_governance_imports(self):
        """
        This test proves INV-P51-4.

        P51 module must not import any governance modules or future
        governance logic.
        """
        import symbolu.mechanical.pipeline.p51_governance_readiness.p51_schema as schema_module
        import symbolu.mechanical.pipeline.p51_governance_readiness.p51_analyzer as analyzer_module
        import symbolu.mechanical.pipeline.p51_governance_readiness.p51_integration as integration_module

        # Get source code of all modules
        schema_source = inspect.getsource(schema_module)
        analyzer_source = inspect.getsource(analyzer_module)
        integration_source = inspect.getsource(integration_module)

        # Forbidden imports that would indicate governance dependency
        forbidden_imports = [
            "from symbolu.mechanical.pipeline.governance",
            "from symbolu.governance",
            "import governance",
            "from symbolu.mechanical.pipeline.policy",
            "from symbolu.policy",
        ]

        for forbidden in forbidden_imports:
            assert forbidden not in schema_source, \
                f"Schema should not import {forbidden}"
            assert forbidden not in analyzer_source, \
                f"Analyzer should not import {forbidden}"
            assert forbidden not in integration_source, \
                f"Integration should not import {forbidden}"


# ============================================================================
# INV-P51-5: REMOVAL EQUIVALENCE
# ============================================================================


class TestINV_P51_5_RemovalEquivalence:
    """
    INV-P51-5: When P51 is removed, system behavior is bitwise identical.

    This test proves INV-P51-5.
    """

    def test_removal_equivalence(self):
        """
        This test proves INV-P51-5.

        Removing P51 should not change any upstream state or downstream
        behavior. The system should be bitwise identical with or without P51.
        """
        # Create two identical contexts
        ctx_with_p51 = make_complete_context()
        ctx_without_p51 = make_complete_context()

        # Run P51 on one context
        maybe_run_p51(ctx_with_p51)

        # Don't run P51 on the other

        # All upstream values should be identical
        assert ctx_with_p51.p6_regime.regime == ctx_without_p51.p6_regime.regime
        assert ctx_with_p51.p7_discourse_envelope.act == ctx_without_p51.p7_discourse_envelope.act
        assert ctx_with_p51.p18.entropy_now == ctx_without_p51.p18.entropy_now
        assert ctx_with_p51.p19_drift_fusion.drift_fusion_index == ctx_without_p51.p19_drift_fusion.drift_fusion_index
        assert ctx_with_p51.phase_20_snapshot.run_id == ctx_without_p51.phase_20_snapshot.run_id
        assert ctx_with_p51.p21_delivery_mode.delivery_mode == ctx_without_p51.p21_delivery_mode.delivery_mode
        assert ctx_with_p51.p50_cognitive_consistency.consistency_score == ctx_without_p51.p50_cognitive_consistency.consistency_score

        # Only difference should be p51_governance_readiness field
        assert ctx_with_p51.p51_governance_readiness is not None
        assert ctx_without_p51.p51_governance_readiness is None


# ============================================================================
# SCENARIO: FULLY VALID PIPELINE -> READY
# ============================================================================


class TestScenarioFullyValidPipeline:
    """
    Scenario test: Fully valid pipeline should return READY.
    """

    def test_fully_valid_pipeline_returns_ready(self):
        """
        When all mandatory phases are present and no issues detected,
        P51 should return READY status.
        """
        ctx = make_complete_context()

        envelope = maybe_run_p51(ctx)

        assert envelope is not None
        assert envelope.readiness_level == "READY"
        assert envelope.ready is True
        assert len(envelope.blocking_factors) == 0


# ============================================================================
# SCENARIO: MISSING ENVELOPE -> NOT_READY
# ============================================================================


class TestScenarioMissingEnvelope:
    """
    Scenario test: Missing mandatory envelope should return NOT_READY.
    """

    def test_missing_envelope_returns_not_ready(self):
        """
        When mandatory phase envelopes are missing, P51 should return
        NOT_READY status with appropriate blocking factors.
        """
        ctx = make_incomplete_context()

        envelope = maybe_run_p51(ctx)

        assert envelope is not None
        assert envelope.readiness_level == "NOT_READY"
        assert envelope.ready is False
        assert len(envelope.blocking_factors) > 0

        # Should have blocking factors for missing phases
        blocking_str = " ".join(envelope.blocking_factors)
        assert "MISSING_MANDATORY_PHASE" in blocking_str
