"""
Test Suite: P20 Unified Cognitive Snapshot Integration

Group D - Governance Tests:
    - Snapshot exists under BLOCKED/HOLD regimes
    - Snapshot does not unblock anything

Group E - Regression Tests:
    - Phase 19 values appear unchanged
    - No mutation of upstream reports

This test file validates the integration functions for Phase 20.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass, field
from typing import List, Optional, Any

from symbolu.mechanical.pipeline.p20_snapshot import (
    maybe_run_p20,
    run_p20,
    is_p20_disabled,
    has_p20_snapshot,
    get_p20_snapshot,
    get_p20_version,
    get_p20_resolver,
    P20_VERSION,
    UnifiedCognitiveSnapshot,
)


# =============================================================================
# Mock Context Classes
# =============================================================================


@dataclass
class MockCoherenceState:
    """Mock coherence state for testing."""
    coherence_score_v3: Optional[float] = None
    coherence_v3_quality: Optional[float] = None
    temporal_entropy_diff: Optional[float] = None
    temporal_entropy_volatility: Optional[float] = None
    drift_fusion_index: Optional[float] = None
    drift_risk_band: Optional[str] = None
    drift_pattern_tags: List[str] = field(default_factory=list)
    semantic_integrity_score: Optional[float] = None
    current_symbolic_harmonization_index: Optional[float] = None
    domain_history: List[str] = field(default_factory=list)


@dataclass
class MockP17Report:
    """Mock P17 integrity report."""
    integrity_score: float = 0.85


@dataclass
class MockP18Report:
    """Mock P18 temporal entropy report."""
    entropy_now: float = 0.5


@dataclass
class MockP19Report:
    """Mock P19 drift fusion report."""
    drift_fusion_index: float = 0.35
    drift_risk_band: str = "low"
    drift_pattern_tags: tuple = ()


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    coherence_state: Optional[MockCoherenceState] = None
    p17: Optional[MockP17Report] = None
    p18: Optional[MockP18Report] = None
    p19: Optional[MockP19Report] = None
    phase_minus_one: Optional[Any] = None
    phase_zero: Optional[Any] = None
    allowed_actions: Optional[Any] = None
    po4_proposal: Optional[Any] = None
    po5_execution_eligibility: Optional[Any] = None
    p6_regime: Optional[Any] = None
    p7_discourse_envelope: Optional[Any] = None
    semantic_frame: Optional[Any] = None
    lexical_frame: Optional[Any] = None
    p10_acoustic: Optional[Any] = None
    p11_prosodic_evidence: Optional[Any] = None
    p12_consistency: Optional[Any] = None
    p13_safety_envelope: Optional[Any] = None
    p14_surface: Optional[Any] = None
    interaction_directive: Optional[Any] = None
    p16_guard_result: Optional[Any] = None
    mlcr: Optional[Any] = None
    fusion: Optional[Any] = None
    phase_20_snapshot: Optional[UnifiedCognitiveSnapshot] = None
    _p20_disabled: bool = False


class TestMaybeRunP20:
    """Test maybe_run_p20 integration function."""

    def test_returns_context(self):
        """Test that maybe_run_p20 returns the context."""
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        result = maybe_run_p20(ctx)
        assert result is ctx

    def test_attaches_snapshot_to_context(self):
        """Test that snapshot is attached to context."""
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        maybe_run_p20(ctx)
        assert ctx.phase_20_snapshot is not None
        assert isinstance(ctx.phase_20_snapshot, UnifiedCognitiveSnapshot)

    def test_skips_when_disabled(self):
        """Test that P20 skips when disabled."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(),
            _p20_disabled=True,
        )
        maybe_run_p20(ctx)
        assert ctx.phase_20_snapshot is None

    def test_skips_when_no_upstream_data(self):
        """Test that P20 skips when no upstream data exists."""
        ctx = MockPipelineContext()
        maybe_run_p20(ctx)
        assert ctx.phase_20_snapshot is None

    def test_runs_with_coherence_state_only(self):
        """Test that P20 runs with just coherence_state."""
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        maybe_run_p20(ctx)
        assert ctx.phase_20_snapshot is not None

    def test_runs_with_p17_only(self):
        """Test that P20 runs with just P17."""
        ctx = MockPipelineContext(p17=MockP17Report())
        maybe_run_p20(ctx)
        assert ctx.phase_20_snapshot is not None

    def test_runs_with_p18_only(self):
        """Test that P20 runs with just P18."""
        ctx = MockPipelineContext(p18=MockP18Report())
        maybe_run_p20(ctx)
        assert ctx.phase_20_snapshot is not None

    def test_runs_with_p19_only(self):
        """Test that P20 runs with just P19."""
        ctx = MockPipelineContext(p19=MockP19Report())
        maybe_run_p20(ctx)
        assert ctx.phase_20_snapshot is not None

    def test_runs_with_mlcr_only(self):
        """Test that P20 runs with just MLCR."""
        ctx = MockPipelineContext(mlcr=Mock())
        maybe_run_p20(ctx)
        assert ctx.phase_20_snapshot is not None


class TestRunP20Direct:
    """Test run_p20 direct execution."""

    def test_returns_snapshot_directly(self):
        """Test that run_p20 returns snapshot without modifying context."""
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        snapshot = run_p20(ctx)
        assert isinstance(snapshot, UnifiedCognitiveSnapshot)

    def test_does_not_attach_to_context(self):
        """Test that run_p20 doesn't attach snapshot to context."""
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        run_p20(ctx)
        # phase_20_snapshot should still be None since run_p20 doesn't attach
        assert ctx.phase_20_snapshot is None


class TestHelperFunctions:
    """Test helper functions."""

    def test_is_p20_disabled_false(self):
        """Test is_p20_disabled returns False by default."""
        ctx = MockPipelineContext()
        assert is_p20_disabled(ctx) is False

    def test_is_p20_disabled_true(self):
        """Test is_p20_disabled returns True when disabled."""
        ctx = MockPipelineContext(_p20_disabled=True)
        assert is_p20_disabled(ctx) is True

    def test_has_p20_snapshot_false(self):
        """Test has_p20_snapshot returns False when no snapshot."""
        ctx = MockPipelineContext()
        assert has_p20_snapshot(ctx) is False

    def test_has_p20_snapshot_true(self):
        """Test has_p20_snapshot returns True when snapshot exists."""
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        maybe_run_p20(ctx)
        assert has_p20_snapshot(ctx) is True

    def test_get_p20_snapshot_none(self):
        """Test get_p20_snapshot returns None when no snapshot."""
        ctx = MockPipelineContext()
        assert get_p20_snapshot(ctx) is None

    def test_get_p20_snapshot_returns_snapshot(self):
        """Test get_p20_snapshot returns the snapshot."""
        ctx = MockPipelineContext(coherence_state=MockCoherenceState())
        maybe_run_p20(ctx)
        snapshot = get_p20_snapshot(ctx)
        assert snapshot is not None
        assert isinstance(snapshot, UnifiedCognitiveSnapshot)

    def test_get_p20_version(self):
        """Test get_p20_version returns the version."""
        version = get_p20_version()
        assert version == P20_VERSION

    def test_get_p20_resolver_singleton(self):
        """Test get_p20_resolver returns singleton."""
        resolver1 = get_p20_resolver()
        resolver2 = get_p20_resolver()
        assert resolver1 is resolver2


class TestGovernanceUnderBlockedRegimes:
    """Group D - Governance Tests: Snapshot exists under BLOCKED/HOLD regimes."""

    def test_snapshot_exists_under_blocked_regime(self):
        """Test that snapshot is created even when regime is BLOCKED."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_score_v3=0.75),
            p6_regime=Mock(regime=Mock(value="BLOCKED")),
        )
        maybe_run_p20(ctx)
        assert ctx.phase_20_snapshot is not None

    def test_snapshot_exists_under_hold_regime(self):
        """Test that snapshot is created even when regime is HOLD."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_score_v3=0.75),
            p6_regime=Mock(regime=Mock(value="HOLD")),
        )
        maybe_run_p20(ctx)
        assert ctx.phase_20_snapshot is not None

    def test_snapshot_does_not_unblock(self):
        """Test that snapshot creation does not affect blocking status."""
        regime_mock = Mock(regime=Mock(value="BLOCKED"))
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(),
            p6_regime=regime_mock,
        )
        maybe_run_p20(ctx)
        # Regime should still be BLOCKED
        assert ctx.p6_regime.regime.value == "BLOCKED"

    def test_snapshot_preserves_blocked_reason(self):
        """Test that snapshot creation preserves blocked reason."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(),
            p6_regime=Mock(
                regime=Mock(value="BLOCKED"),
                reason="Safety concern detected",
            ),
        )
        maybe_run_p20(ctx)
        assert ctx.p6_regime.reason == "Safety concern detected"


class TestPhase19Regression:
    """Group E - Regression Tests: Phase 19 values appear unchanged."""

    def test_p19_values_unchanged_after_snapshot(self):
        """Test that P19 values are unchanged after snapshot creation."""
        p19 = MockP19Report(
            drift_fusion_index=0.45,
            drift_risk_band="moderate",
            drift_pattern_tags=("semantic_drift", "cognitive_drift"),
        )
        ctx = MockPipelineContext(p19=p19)
        maybe_run_p20(ctx)

        # P19 values should be unchanged
        assert ctx.p19.drift_fusion_index == 0.45
        assert ctx.p19.drift_risk_band == "moderate"
        assert ctx.p19.drift_pattern_tags == ("semantic_drift", "cognitive_drift")

    def test_snapshot_contains_p19_values(self):
        """Test that snapshot contains P19 values verbatim."""
        p19 = MockP19Report(
            drift_fusion_index=0.45,
            drift_risk_band="moderate",
            drift_pattern_tags=("semantic_drift",),
        )
        ctx = MockPipelineContext(p19=p19)
        maybe_run_p20(ctx)

        assert ctx.phase_20_snapshot.drift_fusion_index == 0.45
        assert ctx.phase_20_snapshot.drift_risk_band == "moderate"
        assert "semantic_drift" in ctx.phase_20_snapshot.drift_pattern_tags

    def test_p17_values_unchanged_after_snapshot(self):
        """Test that P17 values are unchanged after snapshot creation."""
        p17 = MockP17Report(integrity_score=0.88)
        ctx = MockPipelineContext(p17=p17)
        maybe_run_p20(ctx)
        assert ctx.p17.integrity_score == 0.88

    def test_p18_values_unchanged_after_snapshot(self):
        """Test that P18 values are unchanged after snapshot creation."""
        p18 = MockP18Report(entropy_now=0.55)
        ctx = MockPipelineContext(p18=p18)
        maybe_run_p20(ctx)
        assert ctx.p18.entropy_now == 0.55

    def test_coherence_state_unchanged_after_snapshot(self):
        """Test that coherence_state is unchanged after snapshot creation."""
        coherence_state = MockCoherenceState(
            coherence_score_v3=0.85,
            temporal_entropy_diff=0.45,
            drift_fusion_index=0.35,
        )
        ctx = MockPipelineContext(coherence_state=coherence_state)
        maybe_run_p20(ctx)

        assert ctx.coherence_state.coherence_score_v3 == 0.85
        assert ctx.coherence_state.temporal_entropy_diff == 0.45
        assert ctx.coherence_state.drift_fusion_index == 0.35


class TestNoMutationOfUpstreamReports:
    """Test that upstream reports are not mutated."""

    def test_p17_report_immutable(self):
        """Test that P17 report is not mutated."""
        p17 = MockP17Report(integrity_score=0.88)
        original_score = p17.integrity_score
        ctx = MockPipelineContext(p17=p17)
        maybe_run_p20(ctx)
        assert p17.integrity_score == original_score

    def test_p18_report_immutable(self):
        """Test that P18 report is not mutated."""
        p18 = MockP18Report(entropy_now=0.55)
        original_entropy = p18.entropy_now
        ctx = MockPipelineContext(p18=p18)
        maybe_run_p20(ctx)
        assert p18.entropy_now == original_entropy

    def test_p19_report_immutable(self):
        """Test that P19 report is not mutated."""
        p19 = MockP19Report(
            drift_fusion_index=0.45,
            drift_risk_band="moderate",
        )
        original_index = p19.drift_fusion_index
        original_band = p19.drift_risk_band
        ctx = MockPipelineContext(p19=p19)
        maybe_run_p20(ctx)
        assert p19.drift_fusion_index == original_index
        assert p19.drift_risk_band == original_band

    def test_coherence_state_immutable(self):
        """Test that coherence_state is not mutated."""
        coherence_state = MockCoherenceState(
            coherence_score_v3=0.85,
            domain_history=["therapy", "finance"],
        )
        original_score = coherence_state.coherence_score_v3
        original_domains = coherence_state.domain_history.copy()
        ctx = MockPipelineContext(coherence_state=coherence_state)
        maybe_run_p20(ctx)
        assert coherence_state.coherence_score_v3 == original_score
        assert coherence_state.domain_history == original_domains


class TestPhaseCompletionFlagsAccuracy:
    """Test that phase completion flags are accurate."""

    def test_all_phases_flagged_when_present(self):
        """Test that all phases are flagged as complete when present."""
        ctx = MockPipelineContext(
            phase_minus_one=Mock(),
            phase_zero=Mock(),
            allowed_actions=Mock(),
            po4_proposal=Mock(),
            po5_execution_eligibility=Mock(),
            p6_regime=Mock(),
            p7_discourse_envelope=Mock(),
            semantic_frame=Mock(),
            lexical_frame=Mock(),
            p10_acoustic=Mock(),
            p11_prosodic_evidence=Mock(),
            p12_consistency=Mock(),
            p13_safety_envelope=Mock(),
            p14_surface=Mock(),
            interaction_directive=Mock(),
            p16_guard_result=Mock(),
            p17=MockP17Report(),
            p18=MockP18Report(),
            p19=MockP19Report(),
        )
        maybe_run_p20(ctx)

        flags = ctx.phase_20_snapshot.phase_completion_flags
        assert flags["phase_minus_one"] is True
        assert flags["phase_zero"] is True
        assert flags["phase_one"] is True
        assert flags["po4"] is True
        assert flags["po5"] is True
        assert flags["p6"] is True
        assert flags["p7"] is True
        assert flags["p8"] is True
        assert flags["p9"] is True
        assert flags["p10"] is True
        assert flags["p11"] is True
        assert flags["p12"] is True
        assert flags["p13"] is True
        assert flags["p14"] is True
        assert flags["p15"] is True
        assert flags["p16"] is True
        assert flags["p17"] is True
        assert flags["p18"] is True
        assert flags["p19"] is True

    def test_partial_phases_flagged_correctly(self):
        """Test that only present phases are flagged as complete."""
        ctx = MockPipelineContext(
            phase_minus_one=Mock(),
            phase_zero=Mock(),
            p17=MockP17Report(),
        )
        maybe_run_p20(ctx)

        flags = ctx.phase_20_snapshot.phase_completion_flags
        assert flags["phase_minus_one"] is True
        assert flags["phase_zero"] is True
        assert flags["phase_one"] is False
        assert flags["p17"] is True
        assert flags["p18"] is False
