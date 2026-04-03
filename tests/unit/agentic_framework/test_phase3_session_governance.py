"""
Phase 3: Session Enrichment → Governance Integration — Tests
=============================================================

Tests verifying:
1. Session enrichment adapter resolves identity, motivation, temporal signals
2. Identity instability produces bounded confidence penalty
3. Motivation risk types produce bounded confidence penalty
4. Temporal tension produces bounded confidence penalty
5. Total penalty is bounded at -0.15
6. Missing signals contribute zero penalty (fail-closed)
7. Reason codes are generated for instability patterns
8. ConfidenceSignals extended with session fields
9. Aggregator applies session_enrichment_adjustment correctly
10. ApprovalContext carries session enrichment fields
11. Stricter-only invariant: penalties never increase confidence
"""

import pytest
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from agentic.agentic_framework.signal_adapters.session_enrichment_adapter import (
    resolve_session_enrichment,
    SessionEnrichmentResolution,
    _resolve_identity,
    _resolve_motivation,
    _resolve_temporal,
    _compute_identity_penalty,
    _compute_motivation_penalty,
    _compute_temporal_penalty,
    _MAX_IDENTITY_PENALTY,
    _MAX_MOTIVATION_PENALTY,
    _MAX_TEMPORAL_PENALTY,
    _IDENTITY_INSTABILITY_TYPES,
    _MOTIVATION_RISK_TYPES,
    _TEMPORAL_TENSION_STATES,
)
from agentic.agentic_framework.confidence_gate import (
    ConfidenceSignals,
    ConfidenceAggregator,
    AggregationWeights,
)


# =========================================================================
# Fake types for testing
# =========================================================================

@dataclass
class FakeIdentitySignature:
    signature_type: str = "self_anchoring"
    confidence: float = 0.8
    drivers: List[str] = None
    markers: List[str] = None

    def __post_init__(self):
        if self.drivers is None:
            self.drivers = []
        if self.markers is None:
            self.markers = []


@dataclass
class FakeResonanceState:
    identity_stability_band: str = "stable"
    volatility_index: float = 0.1


@dataclass
class FakeMotivationProfile:
    motivation_type: str = "hope_driven"
    confidence: float = 0.85
    drivers: List[str] = None
    markers: List[str] = None

    def __post_init__(self):
        if self.drivers is None:
            self.drivers = []
        if self.markers is None:
            self.markers = []


@dataclass
class FakeCoherenceState:
    tension_index: Optional[float] = 0.3


# =========================================================================
# IDENTITY RESOLUTION TESTS
# =========================================================================


class TestIdentityResolution:
    """Test identity signal extraction."""

    def test_stable_identity(self):
        sig = FakeIdentitySignature(signature_type="self_anchoring", confidence=0.9)
        result = _resolve_identity(sig, None)
        assert result["identity_type"] == "self_anchoring"
        assert result["identity_confidence"] == 0.9
        assert result["identity_unstable"] is False

    def test_fragmentation_identity(self):
        sig = FakeIdentitySignature(signature_type="self_fragmentation", confidence=0.7)
        result = _resolve_identity(sig, None)
        assert result["identity_unstable"] is True

    def test_dissonance_identity(self):
        sig = FakeIdentitySignature(signature_type="self_dissonance", confidence=0.6)
        result = _resolve_identity(sig, None)
        assert result["identity_unstable"] is True

    def test_low_confidence_instability_not_flagged(self):
        """Identity instability type with confidence < 0.5 should not flag."""
        sig = FakeIdentitySignature(signature_type="self_fragmentation", confidence=0.3)
        result = _resolve_identity(sig, None)
        assert result["identity_unstable"] is False

    def test_fragile_band_reinforces_instability(self):
        sig = FakeIdentitySignature(signature_type="neutral_identity", confidence=0.5)
        resonance = FakeResonanceState(identity_stability_band="fragile")
        result = _resolve_identity(sig, resonance)
        assert result["identity_unstable"] is True
        assert result["identity_stability_band"] == "fragile"

    def test_no_identity_data(self):
        result = _resolve_identity(None, None)
        assert result["identity_type"] is None
        assert result["identity_unstable"] is False

    def test_malformed_identity(self):
        result = _resolve_identity(object(), None)
        assert result["identity_type"] is None
        assert result["identity_unstable"] is False


class TestIdentityPenalty:
    def test_penalty_is_negative(self):
        fields = {"identity_confidence": 0.8}
        penalty = _compute_identity_penalty(fields)
        assert penalty < 0

    def test_penalty_bounded(self):
        fields = {"identity_confidence": 1.0}
        penalty = _compute_identity_penalty(fields)
        assert abs(penalty) <= _MAX_IDENTITY_PENALTY

    def test_penalty_scales_with_confidence(self):
        low = _compute_identity_penalty({"identity_confidence": 0.3})
        high = _compute_identity_penalty({"identity_confidence": 0.9})
        assert abs(high) > abs(low)


# =========================================================================
# MOTIVATION RESOLUTION TESTS
# =========================================================================


class TestMotivationResolution:
    def test_hope_driven_not_risky(self):
        profile = FakeMotivationProfile(motivation_type="hope_driven", confidence=0.9)
        result = _resolve_motivation(profile)
        assert result["motivation_risk_relevant"] is False

    def test_fear_driven_is_risky(self):
        profile = FakeMotivationProfile(motivation_type="fear_driven", confidence=0.7)
        result = _resolve_motivation(profile)
        assert result["motivation_risk_relevant"] is True

    def test_overcorrection_is_risky(self):
        profile = FakeMotivationProfile(motivation_type="overcorrection", confidence=0.6)
        result = _resolve_motivation(profile)
        assert result["motivation_risk_relevant"] is True

    def test_avoidance_is_risky(self):
        profile = FakeMotivationProfile(motivation_type="avoidance_driven", confidence=0.65)
        result = _resolve_motivation(profile)
        assert result["motivation_risk_relevant"] is True

    def test_low_confidence_risk_not_flagged(self):
        profile = FakeMotivationProfile(motivation_type="fear_driven", confidence=0.3)
        result = _resolve_motivation(profile)
        assert result["motivation_risk_relevant"] is False

    def test_no_motivation_data(self):
        result = _resolve_motivation(None)
        assert result["motivation_type"] is None
        assert result["motivation_risk_relevant"] is False


class TestMotivationPenalty:
    def test_penalty_bounded(self):
        fields = {"motivation_confidence": 1.0}
        penalty = _compute_motivation_penalty(fields)
        assert abs(penalty) <= _MAX_MOTIVATION_PENALTY


# =========================================================================
# TEMPORAL RESOLUTION TESTS
# =========================================================================


class TestTemporalResolution:
    def test_stable_state(self):
        summary = {"state": "STABLE", "trajectory": {"trend": "stable"}}
        result = _resolve_temporal(summary, None)
        assert result["temporal_state"] == "STABLE"
        assert result["temporal_tense"] is False
        assert result["temporal_trend"] == "stable"

    def test_tense_state(self):
        summary = {"state": "TENSE", "trajectory": {"trend": "rising"}}
        result = _resolve_temporal(summary, None)
        assert result["temporal_tense"] is True

    def test_volatile_state(self):
        summary = {"state": "VOLATILE", "trajectory": {"trend": "falling"}}
        result = _resolve_temporal(summary, None)
        assert result["temporal_tense"] is True

    def test_high_tension_index_from_coherence_state(self):
        coh = FakeCoherenceState(tension_index=0.8)
        result = _resolve_temporal(None, coh)
        assert result["temporal_tense"] is True
        assert result["temporal_tension_index"] == 0.8
        assert result["temporal_state"] == "HIGH_TENSION_INDEX"

    def test_low_tension_index(self):
        coh = FakeCoherenceState(tension_index=0.3)
        result = _resolve_temporal(None, coh)
        assert result["temporal_tense"] is False
        assert result["temporal_tension_index"] == 0.3

    def test_no_temporal_data(self):
        result = _resolve_temporal(None, None)
        assert result["temporal_state"] is None
        assert result["temporal_tense"] is False


class TestTemporalPenalty:
    def test_penalty_with_high_tension(self):
        fields = {"temporal_tension_index": 0.9}
        penalty = _compute_temporal_penalty(fields)
        assert penalty < 0
        assert abs(penalty) <= _MAX_TEMPORAL_PENALTY

    def test_penalty_without_tension_index(self):
        fields = {"temporal_tension_index": None}
        penalty = _compute_temporal_penalty(fields)
        assert penalty < 0  # flat penalty for tense state
        assert abs(penalty) <= _MAX_TEMPORAL_PENALTY


# =========================================================================
# FULL RESOLUTION TESTS
# =========================================================================


class TestResolveSessionEnrichment:
    """Test the main resolve_session_enrichment() function."""

    def test_all_signals_stable(self):
        res = resolve_session_enrichment(
            identity_signature=FakeIdentitySignature("self_anchoring", 0.9),
            motivation_profile=FakeMotivationProfile("hope_driven", 0.85),
            temporal_summary={"state": "STABLE", "trajectory": {"trend": "stable"}},
        )
        assert res.confidence_adjustment == 0.0
        assert len(res.reason_codes) == 0
        assert "identity" in res.source_detail
        assert "motivation" in res.source_detail
        assert "temporal" in res.source_detail

    def test_all_signals_unstable(self):
        res = resolve_session_enrichment(
            identity_signature=FakeIdentitySignature("self_fragmentation", 0.9),
            identity_resonance_state=FakeResonanceState("fragile", 0.5),
            motivation_profile=FakeMotivationProfile("fear_driven", 0.8),
            temporal_summary={"state": "TENSE", "trajectory": {"trend": "rising"}},
            coherence_state=FakeCoherenceState(tension_index=0.8),
        )
        # All three penalties should fire
        assert res.confidence_adjustment < 0
        # Total bounded at -(0.05 + 0.05 + 0.05) = -0.15
        assert res.confidence_adjustment >= -0.15
        assert res.identity_unstable is True
        assert res.motivation_risk_relevant is True
        assert res.temporal_tense is True
        # Should have at least 3 reason codes (identity, fragile, motivation, temporal)
        assert len(res.reason_codes) >= 3
        # Check specific codes
        assert any("SESSION_IDENTITY:self_fragmentation" in rc for rc in res.reason_codes)
        assert any("SESSION_MOTIVATION:fear_driven" in rc for rc in res.reason_codes)
        assert any("SESSION_TEMPORAL:TENSE" in rc for rc in res.reason_codes)

    def test_no_signals(self):
        res = resolve_session_enrichment()
        assert res.confidence_adjustment == 0.0
        assert res.identity_type is None
        assert res.motivation_type is None
        assert res.temporal_state is None
        assert len(res.reason_codes) == 0

    def test_total_penalty_bounded(self):
        """Maximum total penalty must be exactly -0.15."""
        res = resolve_session_enrichment(
            identity_signature=FakeIdentitySignature("self_fragmentation", 1.0),
            motivation_profile=FakeMotivationProfile("fear_driven", 1.0),
            temporal_summary={"state": "TENSE"},
            coherence_state=FakeCoherenceState(tension_index=1.0),
        )
        assert res.confidence_adjustment >= -0.15
        assert res.confidence_adjustment <= 0.0

    def test_to_dict_serializable(self):
        res = resolve_session_enrichment(
            identity_signature=FakeIdentitySignature("self_dissonance", 0.7),
        )
        d = res.to_dict()
        assert isinstance(d, dict)
        assert d["identity_type"] == "self_dissonance"
        assert d["identity_unstable"] is True
        assert isinstance(d["reason_codes"], list)


# =========================================================================
# CONFIDENCE SIGNALS EXTENSION TESTS
# =========================================================================


class TestConfidenceSignalsSessionFields:
    """Test that ConfidenceSignals has the new session fields."""

    def test_default_session_fields(self):
        signals = ConfidenceSignals()
        assert signals.identity_stability == 0.5
        assert signals.motivation_stability == 0.5
        assert signals.temporal_stability == 0.5
        assert signals.session_enrichment_adjustment == 0.0

    def test_session_fields_in_to_dict(self):
        signals = ConfidenceSignals(identity_stability=0.3, session_enrichment_adjustment=-0.05)
        d = signals.to_dict()
        assert d["identity_stability"] == 0.3
        assert d["session_enrichment_adjustment"] == -0.05


class TestAggregatorWithSessionPenalty:
    """Test that the aggregator applies session_enrichment_adjustment."""

    def test_zero_adjustment_no_effect(self):
        signals = ConfidenceSignals(
            quality_score=0.8, coherence_score=0.8,
            trajectory_confidence=0.8, action_reversibility=0.8,
        )
        agg = ConfidenceAggregator()
        result = agg.aggregate(signals)
        baseline = result.overall

        # Now with zero adjustment — should be identical
        signals2 = ConfidenceSignals(
            quality_score=0.8, coherence_score=0.8,
            trajectory_confidence=0.8, action_reversibility=0.8,
            session_enrichment_adjustment=0.0,
        )
        result2 = agg.aggregate(signals2)
        assert abs(result2.overall - baseline) < 1e-9

    def test_negative_adjustment_lowers_confidence(self):
        signals = ConfidenceSignals(
            quality_score=0.8, coherence_score=0.8,
            trajectory_confidence=0.8, action_reversibility=0.8,
            session_enrichment_adjustment=-0.10,
        )
        agg = ConfidenceAggregator()
        result = agg.aggregate(signals)

        # Same without penalty
        signals_base = ConfidenceSignals(
            quality_score=0.8, coherence_score=0.8,
            trajectory_confidence=0.8, action_reversibility=0.8,
        )
        result_base = agg.aggregate(signals_base)

        assert result.overall < result_base.overall
        # Difference should be exactly the adjustment amount
        assert abs((result_base.overall - result.overall) - 0.10) < 1e-9

    def test_adjustment_never_raises_confidence(self):
        """Stricter-only: adjustment is always <=0, never positive."""
        signals = ConfidenceSignals(
            quality_score=0.5, coherence_score=0.5,
            session_enrichment_adjustment=-0.15,
        )
        agg = ConfidenceAggregator()
        result = agg.aggregate(signals)
        assert result.overall >= 0.0  # clamped, not negative

    def test_signals_used_includes_adjustment(self):
        signals = ConfidenceSignals(session_enrichment_adjustment=-0.05)
        agg = ConfidenceAggregator()
        result = agg.aggregate(signals)
        assert "session_enrichment_adjustment" in result.signals_used

    def test_signals_used_excludes_zero_adjustment(self):
        signals = ConfidenceSignals(session_enrichment_adjustment=0.0)
        agg = ConfidenceAggregator()
        result = agg.aggregate(signals)
        assert "session_enrichment_adjustment" not in result.signals_used


# =========================================================================
# APPROVAL CONTEXT TESTS
# =========================================================================


class TestApprovalContextSessionFields:
    """Test that ApprovalContext carries session enrichment."""

    def test_approval_context_has_session_fields(self):
        from agentic.agentic_framework.approval_workflow import ApprovalContext
        ctx = ApprovalContext(
            governance_decision_id="test-123",
            action_type="tool_call",
            tool_name="test_tool",
            actor_id="actor-1",
            risk_level="write",
            confidence_score=0.65,
            escalation_level="confirm",
            execution_mode="cautious",
            session_identity_type="self_fragmentation",
            session_identity_unstable=True,
            session_motivation_type="fear_driven",
            session_motivation_risk=True,
            session_temporal_state="TENSE",
            session_temporal_tense=True,
            session_confidence_adjustment=-0.12,
        )
        d = ctx.to_dict()
        assert d["session_identity_type"] == "self_fragmentation"
        assert d["session_identity_unstable"] is True
        assert d["session_motivation_type"] == "fear_driven"
        assert d["session_motivation_risk"] is True
        assert d["session_temporal_state"] == "TENSE"
        assert d["session_temporal_tense"] is True
        assert d["session_confidence_adjustment"] == -0.12

    def test_approval_context_defaults(self):
        from agentic.agentic_framework.approval_workflow import ApprovalContext
        ctx = ApprovalContext(
            governance_decision_id="test-456",
            action_type="tool_call",
            tool_name="test",
            actor_id="a",
            risk_level="read_only",
            confidence_score=0.9,
            escalation_level="none",
            execution_mode="full",
        )
        d = ctx.to_dict()
        assert d["session_identity_type"] is None
        assert d["session_confidence_adjustment"] is None


# =========================================================================
# STRICTER-ONLY INVARIANT
# =========================================================================


class TestStricterOnlyInvariant:
    """Verify that session enrichment only tightens governance, never loosens it."""

    def test_stable_session_does_not_loosen(self):
        """Stable signals should not increase confidence above baseline."""
        res = resolve_session_enrichment(
            identity_signature=FakeIdentitySignature("self_anchoring", 1.0),
            motivation_profile=FakeMotivationProfile("hope_driven", 1.0),
            temporal_summary={"state": "STABLE", "trajectory": {"trend": "stable"}},
        )
        assert res.confidence_adjustment == 0.0  # No loosening

    def test_penalty_is_always_nonpositive(self):
        """Confidence adjustment must always be <= 0."""
        for id_type in ["self_fragmentation", "self_dissonance", "self_anchoring", "neutral_identity"]:
            for mot_type in ["fear_driven", "overcorrection", "hope_driven"]:
                for tmp_state in ["TENSE", "STABLE", "VOLATILE"]:
                    res = resolve_session_enrichment(
                        identity_signature=FakeIdentitySignature(id_type, 0.8),
                        motivation_profile=FakeMotivationProfile(mot_type, 0.8),
                        temporal_summary={"state": tmp_state},
                    )
                    assert res.confidence_adjustment <= 0.0, (
                        f"Positive adjustment for {id_type}/{mot_type}/{tmp_state}: "
                        f"{res.confidence_adjustment}"
                    )


# =========================================================================
# AUDIT TRAIL TESTS
# =========================================================================


class TestAuditTrail:
    """Verify session enrichment appears in audit metadata."""

    def test_reason_codes_prefixed(self):
        """All session reason codes should use SESSION_ prefix."""
        res = resolve_session_enrichment(
            identity_signature=FakeIdentitySignature("self_fragmentation", 0.7),
            motivation_profile=FakeMotivationProfile("fear_driven", 0.65),
            temporal_summary={"state": "TENSE"},
        )
        for rc in res.reason_codes:
            assert rc.startswith("SESSION_"), f"Unexpected prefix: {rc}"

    def test_source_detail_describes_sources(self):
        res = resolve_session_enrichment(
            identity_signature=FakeIdentitySignature(),
        )
        assert "identity" in res.source_detail

    def test_importable_from_signal_adapters(self):
        from agentic.agentic_framework import signal_adapters
        assert hasattr(signal_adapters, "resolve_session_enrichment")
        assert hasattr(signal_adapters, "SessionEnrichmentResolution")
