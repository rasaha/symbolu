"""
Test Suite: P20 Unified Cognitive Snapshot Resolver

Group B - Determinism Tests:
    - Same context → identical snapshot
    - No floating drift

This test file validates the resolver logic for Phase 20.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver import (
    P20UnifiedSnapshotResolver,
)
from symbolu.mechanical.pipeline.p20_snapshot.p20_unified_snapshot_schema import (
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
    entropy_prev: Optional[float] = None
    delta_entropy: Optional[float] = None


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


class TestResolverBasics:
    """Test basic resolver functionality."""

    def test_resolver_instantiation(self):
        """Test that resolver can be instantiated."""
        resolver = P20UnifiedSnapshotResolver()
        assert resolver is not None

    def test_resolver_has_version(self):
        """Test that resolver has a version property."""
        resolver = P20UnifiedSnapshotResolver()
        assert hasattr(resolver, "version")
        assert resolver.version is not None

    def test_resolve_returns_snapshot(self):
        """Test that resolve returns a UnifiedCognitiveSnapshot."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext()
        snapshot = resolver.resolve(ctx)
        assert isinstance(snapshot, UnifiedCognitiveSnapshot)

    def test_resolve_sets_timestamp(self):
        """Test that resolve sets a timestamp."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext()
        before = datetime.now(timezone.utc)
        snapshot = resolver.resolve(ctx)
        after = datetime.now(timezone.utc)
        assert before <= snapshot.timestamp <= after

    def test_resolve_generates_run_id(self):
        """Test that resolve generates a run_id."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext()
        snapshot = resolver.resolve(ctx)
        assert snapshot.run_id is not None
        assert isinstance(snapshot.run_id, str)
        assert len(snapshot.run_id) > 0


class TestDeterminism:
    """Group B - Determinism Tests: Same context → identical snapshot (except timestamp/run_id)."""

    def test_same_context_same_coherence_v3(self):
        """Test that same context produces same coherence_v3."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_score_v3=0.85)
        )
        snapshot1 = resolver.resolve(ctx)
        snapshot2 = resolver.resolve(ctx)
        assert snapshot1.coherence_v3 == snapshot2.coherence_v3

    def test_same_context_same_drift_values(self):
        """Test that same context produces same drift values."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            p19=MockP19Report(
                drift_fusion_index=0.45,
                drift_risk_band="moderate",
                drift_pattern_tags=("semantic_drift",),
            )
        )
        snapshot1 = resolver.resolve(ctx)
        snapshot2 = resolver.resolve(ctx)
        assert snapshot1.drift_fusion_index == snapshot2.drift_fusion_index
        assert snapshot1.drift_risk_band == snapshot2.drift_risk_band
        assert snapshot1.drift_pattern_tags == snapshot2.drift_pattern_tags

    def test_same_context_same_entropy_values(self):
        """Test that same context produces same entropy values."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            p18=MockP18Report(entropy_now=0.6),
            coherence_state=MockCoherenceState(
                temporal_entropy_diff=0.6,
                temporal_entropy_volatility=0.3,
            ),
        )
        snapshot1 = resolver.resolve(ctx)
        snapshot2 = resolver.resolve(ctx)
        assert snapshot1.temporal_entropy_diff == snapshot2.temporal_entropy_diff
        assert snapshot1.temporal_entropy_volatility == snapshot2.temporal_entropy_volatility

    def test_same_context_same_integrity(self):
        """Test that same context produces same semantic integrity."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            p17=MockP17Report(integrity_score=0.92)
        )
        snapshot1 = resolver.resolve(ctx)
        snapshot2 = resolver.resolve(ctx)
        assert snapshot1.semantic_integrity == snapshot2.semantic_integrity

    def test_same_context_same_phase_flags(self):
        """Test that same context produces same phase completion flags."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            phase_minus_one=Mock(),
            phase_zero=Mock(),
            p17=MockP17Report(),
        )
        snapshot1 = resolver.resolve(ctx)
        snapshot2 = resolver.resolve(ctx)
        assert snapshot1.phase_completion_flags == snapshot2.phase_completion_flags

    def test_no_floating_point_drift(self):
        """Test that floating point values don't drift between calls."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                coherence_score_v3=0.123456789,
                temporal_entropy_diff=0.987654321,
            ),
            p17=MockP17Report(integrity_score=0.111111111),
        )
        # Call multiple times
        snapshots = [resolver.resolve(ctx) for _ in range(10)]
        # All values should be identical
        for s in snapshots[1:]:
            assert s.coherence_v3 == snapshots[0].coherence_v3
            assert s.temporal_entropy_diff == snapshots[0].temporal_entropy_diff
            assert s.semantic_integrity == snapshots[0].semantic_integrity


class TestCoherenceExtraction:
    """Test coherence value extraction."""

    def test_extracts_coherence_v3_from_coherence_state(self):
        """Test extraction of coherence_v3 from coherence_state."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_score_v3=0.75)
        )
        snapshot = resolver.resolve(ctx)
        assert snapshot.coherence_v3 == 0.75

    def test_extracts_coherence_quality_from_coherence_state(self):
        """Test extraction of coherence_quality from coherence_state."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.82)
        )
        snapshot = resolver.resolve(ctx)
        assert snapshot.coherence_quality == 0.82

    def test_missing_coherence_state_returns_none(self):
        """Test that missing coherence_state results in None values."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(coherence_state=None)
        snapshot = resolver.resolve(ctx)
        assert snapshot.coherence_v3 is None
        assert snapshot.coherence_quality is None


class TestEntropyExtraction:
    """Test entropy value extraction."""

    def test_extracts_entropy_from_p18(self):
        """Test extraction of entropy from P18 report."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            p18=MockP18Report(entropy_now=0.55)
        )
        snapshot = resolver.resolve(ctx)
        assert snapshot.temporal_entropy_diff == 0.55

    def test_extracts_volatility_from_coherence_state(self):
        """Test extraction of volatility from coherence_state."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(temporal_entropy_volatility=0.25)
        )
        snapshot = resolver.resolve(ctx)
        assert snapshot.temporal_entropy_volatility == 0.25

    def test_fallback_entropy_from_coherence_state(self):
        """Test fallback to coherence_state when P18 is missing."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            p18=None,
            coherence_state=MockCoherenceState(temporal_entropy_diff=0.45)
        )
        snapshot = resolver.resolve(ctx)
        assert snapshot.temporal_entropy_diff == 0.45


class TestDriftExtraction:
    """Test drift value extraction."""

    def test_extracts_drift_from_p19(self):
        """Test extraction of drift values from P19 report."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            p19=MockP19Report(
                drift_fusion_index=0.35,
                drift_risk_band="low",
                drift_pattern_tags=("semantic_drift", "cognitive_drift"),
            )
        )
        snapshot = resolver.resolve(ctx)
        assert snapshot.drift_fusion_index == 0.35
        assert snapshot.drift_risk_band == "low"
        assert snapshot.drift_pattern_tags == ("semantic_drift", "cognitive_drift")

    def test_fallback_drift_from_coherence_state(self):
        """Test fallback to coherence_state when P19 is missing."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            p19=None,
            coherence_state=MockCoherenceState(
                drift_fusion_index=0.55,
                drift_risk_band="moderate",
                drift_pattern_tags=["entropy_shift"],
            )
        )
        snapshot = resolver.resolve(ctx)
        assert snapshot.drift_fusion_index == 0.55
        assert snapshot.drift_risk_band == "moderate"
        assert snapshot.drift_pattern_tags == ("entropy_shift",)

    def test_missing_drift_returns_none(self):
        """Test that missing drift data results in None values."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(p19=None, coherence_state=None)
        snapshot = resolver.resolve(ctx)
        assert snapshot.drift_fusion_index is None
        assert snapshot.drift_risk_band is None
        assert snapshot.drift_pattern_tags == ()


class TestIntegrityExtraction:
    """Test semantic integrity extraction."""

    def test_extracts_integrity_from_p17(self):
        """Test extraction of integrity from P17 report."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            p17=MockP17Report(integrity_score=0.88)
        )
        snapshot = resolver.resolve(ctx)
        assert snapshot.semantic_integrity == 0.88

    def test_fallback_integrity_from_coherence_state(self):
        """Test fallback to coherence_state when P17 is missing."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            p17=None,
            coherence_state=MockCoherenceState(semantic_integrity_score=0.76)
        )
        snapshot = resolver.resolve(ctx)
        assert snapshot.semantic_integrity == 0.76

    def test_missing_integrity_returns_none(self):
        """Test that missing integrity data results in None."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(p17=None, coherence_state=None)
        snapshot = resolver.resolve(ctx)
        assert snapshot.semantic_integrity is None


class TestSymbolicHarmonyExtraction:
    """Test symbolic harmony extraction."""

    def test_extracts_harmony_from_coherence_state(self):
        """Test extraction of symbolic harmony from coherence_state."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                current_symbolic_harmonization_index=0.68
            )
        )
        snapshot = resolver.resolve(ctx)
        assert snapshot.symbolic_harmony == 0.68

    def test_missing_harmony_returns_none(self):
        """Test that missing harmony data results in None."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(coherence_state=None)
        snapshot = resolver.resolve(ctx)
        assert snapshot.symbolic_harmony is None


class TestActiveDomainExtraction:
    """Test active domain extraction."""

    def test_extracts_domains_from_coherence_state(self):
        """Test extraction of domains from coherence_state domain_history."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                domain_history=["therapy", "finance", "trading"]
            )
        )
        snapshot = resolver.resolve(ctx)
        assert "therapy" in snapshot.active_domains
        assert "finance" in snapshot.active_domains
        assert "trading" in snapshot.active_domains

    def test_domains_are_unique(self):
        """Test that duplicate domains are not included."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                domain_history=["therapy", "therapy", "finance", "finance"]
            )
        )
        snapshot = resolver.resolve(ctx)
        # Should have unique domains only
        assert len([d for d in snapshot.active_domains if d == "therapy"]) == 1
        assert len([d for d in snapshot.active_domains if d == "finance"]) == 1

    def test_missing_domains_returns_empty(self):
        """Test that missing domain data results in empty tuple."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(coherence_state=None)
        snapshot = resolver.resolve(ctx)
        assert snapshot.active_domains == ()


class TestPhaseCompletionFlags:
    """Test phase completion flag generation."""

    def test_phase_minus_one_flag(self):
        """Test phase_minus_one completion flag."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(phase_minus_one=Mock())
        snapshot = resolver.resolve(ctx)
        assert snapshot.phase_completion_flags.get("phase_minus_one") is True

    def test_phase_zero_flag(self):
        """Test phase_zero completion flag."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(phase_zero=Mock())
        snapshot = resolver.resolve(ctx)
        assert snapshot.phase_completion_flags.get("phase_zero") is True

    def test_p17_flag(self):
        """Test P17 completion flag."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(p17=MockP17Report())
        snapshot = resolver.resolve(ctx)
        assert snapshot.phase_completion_flags.get("p17") is True

    def test_p18_flag(self):
        """Test P18 completion flag."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(p18=MockP18Report())
        snapshot = resolver.resolve(ctx)
        assert snapshot.phase_completion_flags.get("p18") is True

    def test_p19_flag(self):
        """Test P19 completion flag."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext(p19=MockP19Report())
        snapshot = resolver.resolve(ctx)
        assert snapshot.phase_completion_flags.get("p19") is True

    def test_missing_phase_is_false(self):
        """Test that missing phases have False flags."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext()
        snapshot = resolver.resolve(ctx)
        assert snapshot.phase_completion_flags.get("phase_minus_one") is False
        assert snapshot.phase_completion_flags.get("phase_zero") is False
        assert snapshot.phase_completion_flags.get("p17") is False
        assert snapshot.phase_completion_flags.get("p18") is False

    def test_all_phases_tracked(self):
        """Test that all phases are tracked in completion flags."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext()
        snapshot = resolver.resolve(ctx)
        expected_phases = [
            "phase_minus_one", "phase_zero", "phase_one",
            "po4", "po5", "p6", "p7", "p8", "p9",
            "p10", "p11", "p12", "p13", "p14", "p15",
            "p16", "p17", "p18", "p19",
        ]
        for phase in expected_phases:
            assert phase in snapshot.phase_completion_flags


class TestRunIdGeneration:
    """Test run_id generation logic."""

    def test_uses_existing_run_id(self):
        """Test that existing run_id from context is used."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext()
        ctx.run_id = "existing-run-id-123"
        snapshot = resolver.resolve(ctx)
        assert snapshot.run_id == "existing-run-id-123"

    def test_generates_uuid_when_no_run_id(self):
        """Test that UUID is generated when no run_id exists."""
        resolver = P20UnifiedSnapshotResolver()
        ctx = MockPipelineContext()
        snapshot = resolver.resolve(ctx)
        # Should be a valid UUID format (36 chars with hyphens)
        assert len(snapshot.run_id) == 36
        assert snapshot.run_id.count("-") == 4


class TestReadOnlyBehavior:
    """Test that resolver doesn't modify context."""

    def test_does_not_modify_coherence_state(self):
        """Test that resolver doesn't modify coherence_state."""
        resolver = P20UnifiedSnapshotResolver()
        coherence_state = MockCoherenceState(coherence_score_v3=0.75)
        ctx = MockPipelineContext(coherence_state=coherence_state)
        resolver.resolve(ctx)
        assert ctx.coherence_state.coherence_score_v3 == 0.75

    def test_does_not_modify_p17(self):
        """Test that resolver doesn't modify P17 report."""
        resolver = P20UnifiedSnapshotResolver()
        p17 = MockP17Report(integrity_score=0.88)
        ctx = MockPipelineContext(p17=p17)
        resolver.resolve(ctx)
        assert ctx.p17.integrity_score == 0.88

    def test_does_not_modify_p18(self):
        """Test that resolver doesn't modify P18 report."""
        resolver = P20UnifiedSnapshotResolver()
        p18 = MockP18Report(entropy_now=0.5)
        ctx = MockPipelineContext(p18=p18)
        resolver.resolve(ctx)
        assert ctx.p18.entropy_now == 0.5

    def test_does_not_modify_p19(self):
        """Test that resolver doesn't modify P19 report."""
        resolver = P20UnifiedSnapshotResolver()
        p19 = MockP19Report(drift_fusion_index=0.35)
        ctx = MockPipelineContext(p19=p19)
        resolver.resolve(ctx)
        assert ctx.p19.drift_fusion_index == 0.35
