"""
Test Suite: P21 Delivery Mode Resolver

Comprehensive tests for Phase 21 delivery channel governance.

Test Groups:
    1. Schema Tests - DeliveryModeDecision validation and immutability
    2. Blocking Tests - BLOCKED → SUPPRESSED, HOLD → TEXT_ONLY, acoustic_permission_flag=False
    3. Drift Tests - HIGH drift → TEXT_ONLY, MODERATE drift → no escalation
    4. Positive Path Tests - OPEN + safe → TEXT_AND_VOICE
    5. Invariant Tests - Forbidden access, override prevention, determinism
    6. Renderer Subordination Tests - Renderer compliance validation
    7. Integration Tests - Pipeline integration functions
"""

import pytest
from dataclasses import dataclass, FrozenInstanceError
from typing import Any, Optional

from symbolu.mechanical.pipeline.p21_delivery import (
    # Schema
    P21_VERSION,
    DeliveryMode,
    DeliveryModeDecision,
    DeliveryInvariantViolation,
    TAG_BLOCKED_BY_UPSTREAM,
    TAG_HOLD_REGIME,
    TAG_ACOUSTIC_SAFETY_RESTRICTION,
    TAG_HIGH_DRIFT_RISK,
    TAG_CONSERVATIVE_DEFAULT,
    TAG_NORMAL_OPERATION,
    create_decision,
    create_suppressed_decision,
    create_text_only_decision,
    # Resolver
    DeliveryModeResolver,
    access_forbidden_attribute,
    FORBIDDEN_ACOUSTIC_ATTRS,
    ALL_FORBIDDEN_ATTRS,
    # Integration
    get_p21_resolver,
    maybe_run_p21,
    run_p21,
    run_p21_directly,
    is_p21_disabled,
    has_p21_decision,
    get_p21_decision,
    get_delivery_mode,
    is_delivery_allowed,
    allows_voice_delivery,
    allows_text_delivery,
    is_suppressed,
    validate_renderer_compliance,
)


# =============================================================================
# Mock Context Classes
# =============================================================================


@dataclass
class MockPO1:
    """Mock Phase -1 envelope."""
    blocked: bool = False

    def is_blocked(self) -> bool:
        return self.blocked


@dataclass
class MockP6:
    """Mock P6 regime envelope."""
    regime: str = "OPEN"


@dataclass
class MockP0:
    """Mock Phase 0 intent envelope."""
    intent_type: str = "QUERY"


@dataclass
class MockP7:
    """Mock P7 discourse envelope."""
    act: str = "INFORM"


@dataclass
class MockP13:
    """Mock P13 acoustic safety envelope."""
    _is_safe: bool = True
    _is_blocked: bool = False
    allow_emphasis: bool = False
    allow_pitch_contours: bool = False
    allow_rhythm_variation: bool = False
    allow_intonation_shift: bool = False

    def is_safe(self) -> bool:
        return self._is_safe

    def is_blocked(self) -> bool:
        return self._is_blocked


@dataclass
class MockP19:
    """Mock P19 drift fusion report."""
    drift_risk_band: str = "low"


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    phase_minus_one: Optional[MockPO1] = None
    p6_regime: Optional[MockP6] = None
    phase_zero: Optional[MockP0] = None
    p7_discourse_envelope: Optional[MockP7] = None
    p13_safety_envelope: Optional[MockP13] = None
    p19: Optional[MockP19] = None
    p21: Optional[DeliveryModeDecision] = None
    delivery_mode_decision: Optional[DeliveryModeDecision] = None
    _p21_disabled: bool = False


def create_mock_context(
    blocked: bool = False,
    regime: str = "OPEN",
    acoustic_safe: bool = True,
    drift_risk_band: str = "low",
) -> MockPipelineContext:
    """Factory function to create mock contexts for testing."""
    return MockPipelineContext(
        phase_minus_one=MockPO1(blocked=blocked),
        p6_regime=MockP6(regime=regime),
        phase_zero=MockP0(intent_type="QUERY"),
        p7_discourse_envelope=MockP7(act="INFORM"),
        p13_safety_envelope=MockP13(_is_safe=acoustic_safe, _is_blocked=not acoustic_safe),
        p19=MockP19(drift_risk_band=drift_risk_band),
    )


# =============================================================================
# Group 1: Schema Tests
# =============================================================================


class TestDeliveryModeSchema:
    """Test DeliveryMode enum."""

    def test_enum_values_exist(self):
        """Test that all expected enum values exist."""
        assert DeliveryMode.SUPPRESSED.value == "SUPPRESSED"
        assert DeliveryMode.TEXT_ONLY.value == "TEXT_ONLY"
        assert DeliveryMode.TEXT_AND_VOICE.value == "TEXT_AND_VOICE"
        assert DeliveryMode.VOICE_PROHIBITED.value == "VOICE_PROHIBITED"

    def test_enum_count(self):
        """Test that enum has exactly 4 values."""
        assert len(DeliveryMode) == 4


class TestDeliveryModeDecisionSchema:
    """Test DeliveryModeDecision dataclass."""

    def test_frozen_dataclass(self):
        """Test that decision is frozen (immutable)."""
        decision = create_decision(
            delivery_mode=DeliveryMode.TEXT_ONLY,
            delivery_allowed=True,
            blocked_reason="test",
            enforcement_tags={TAG_CONSERVATIVE_DEFAULT},
        )
        with pytest.raises(FrozenInstanceError):
            decision.delivery_mode = DeliveryMode.SUPPRESSED

    def test_cannot_modify_delivery_allowed(self):
        """Test that delivery_allowed cannot be modified."""
        decision = create_decision(
            delivery_mode=DeliveryMode.TEXT_ONLY,
            delivery_allowed=True,
            blocked_reason="test",
            enforcement_tags={TAG_CONSERVATIVE_DEFAULT},
        )
        with pytest.raises(FrozenInstanceError):
            decision.delivery_allowed = False

    def test_enforcement_tags_frozenset(self):
        """Test that enforcement_tags is a frozenset."""
        decision = create_decision(
            delivery_mode=DeliveryMode.TEXT_ONLY,
            delivery_allowed=True,
            blocked_reason="test",
            enforcement_tags={TAG_CONSERVATIVE_DEFAULT},
        )
        assert isinstance(decision.enforcement_tags, frozenset)

    def test_to_dict_serialization(self):
        """Test that decision can be serialized to dict."""
        decision = create_decision(
            delivery_mode=DeliveryMode.TEXT_AND_VOICE,
            delivery_allowed=True,
            blocked_reason=None,
            enforcement_tags={TAG_NORMAL_OPERATION},
        )
        data = decision.to_dict()
        assert isinstance(data, dict)
        assert data["delivery_mode"] == "TEXT_AND_VOICE"
        assert data["delivery_allowed"] is True
        assert TAG_NORMAL_OPERATION in data["enforcement_tags"]


class TestDeliveryModeDecisionInvariants:
    """Test DeliveryModeDecision invariant validation."""

    def test_suppressed_requires_delivery_not_allowed(self):
        """Test that SUPPRESSED mode requires delivery_allowed=False."""
        with pytest.raises(ValueError, match="SUPPRESSED mode requires delivery_allowed=False"):
            create_decision(
                delivery_mode=DeliveryMode.SUPPRESSED,
                delivery_allowed=True,  # Invalid!
                blocked_reason="test",
                enforcement_tags={TAG_BLOCKED_BY_UPSTREAM},
            )

    def test_restricted_requires_enforcement_tags(self):
        """Test that restricted delivery requires non-empty enforcement_tags."""
        with pytest.raises(ValueError, match="enforcement_tags must be non-empty"):
            create_decision(
                delivery_mode=DeliveryMode.TEXT_ONLY,
                delivery_allowed=True,
                blocked_reason="test",
                enforcement_tags=set(),  # Invalid - empty!
            )

    def test_not_allowed_requires_blocked_reason(self):
        """Test that delivery_allowed=False requires blocked_reason."""
        with pytest.raises(ValueError, match="blocked_reason must be set"):
            create_decision(
                delivery_mode=DeliveryMode.SUPPRESSED,
                delivery_allowed=False,
                blocked_reason=None,  # Invalid - must be set!
                enforcement_tags={TAG_BLOCKED_BY_UPSTREAM},
            )

    def test_valid_suppressed_decision(self):
        """Test that valid SUPPRESSED decision is accepted."""
        decision = create_decision(
            delivery_mode=DeliveryMode.SUPPRESSED,
            delivery_allowed=False,
            blocked_reason="Blocked by upstream",
            enforcement_tags={TAG_BLOCKED_BY_UPSTREAM},
        )
        assert decision.is_suppressed()
        assert not decision.delivery_allowed


# =============================================================================
# Group 2: Blocking Tests
# =============================================================================


class TestBlockingRules:
    """Test blocking decision rules."""

    def test_blocked_returns_suppressed(self):
        """Test: BLOCKED → SUPPRESSED."""
        ctx = create_mock_context(blocked=True)
        decision = run_p21(ctx)

        assert decision.delivery_mode == DeliveryMode.SUPPRESSED
        assert decision.delivery_allowed is False
        assert TAG_BLOCKED_BY_UPSTREAM in decision.enforcement_tags

    def test_hold_regime_returns_text_only(self):
        """Test: HOLD regime → TEXT_ONLY."""
        ctx = create_mock_context(regime="HOLD")
        decision = run_p21(ctx)

        assert decision.delivery_mode == DeliveryMode.TEXT_ONLY
        assert decision.delivery_allowed is True
        assert TAG_HOLD_REGIME in decision.enforcement_tags

    def test_acoustic_permission_false_returns_text_only(self):
        """Test: acoustic_permission_flag=False → TEXT_ONLY."""
        ctx = create_mock_context(acoustic_safe=False)
        decision = run_p21(ctx)

        assert decision.delivery_mode == DeliveryMode.TEXT_ONLY
        assert decision.delivery_allowed is True
        assert TAG_ACOUSTIC_SAFETY_RESTRICTION in decision.enforcement_tags


# =============================================================================
# Group 3: Drift Tests
# =============================================================================


class TestDriftRiskRules:
    """Test drift risk decision rules."""

    def test_high_drift_returns_text_only(self):
        """Test: HIGH drift → TEXT_ONLY."""
        ctx = create_mock_context(drift_risk_band="high")
        decision = run_p21(ctx)

        assert decision.delivery_mode == DeliveryMode.TEXT_ONLY
        assert decision.delivery_allowed is True
        assert TAG_HIGH_DRIFT_RISK in decision.enforcement_tags

    def test_moderate_drift_no_escalation(self):
        """Test: MODERATE drift → no escalation (still TEXT_AND_VOICE if safe)."""
        ctx = create_mock_context(drift_risk_band="moderate")
        decision = run_p21(ctx)

        # Moderate drift should not cause restriction
        assert decision.delivery_mode == DeliveryMode.TEXT_AND_VOICE
        assert decision.delivery_allowed is True
        assert TAG_NORMAL_OPERATION in decision.enforcement_tags

    def test_low_drift_no_escalation(self):
        """Test: LOW drift → no escalation."""
        ctx = create_mock_context(drift_risk_band="low")
        decision = run_p21(ctx)

        assert decision.delivery_mode == DeliveryMode.TEXT_AND_VOICE
        assert decision.delivery_allowed is True


# =============================================================================
# Group 4: Positive Path Tests
# =============================================================================


class TestPositivePath:
    """Test positive (normal operation) paths."""

    def test_open_regime_safe_returns_text_and_voice(self):
        """Test: OPEN + safe → TEXT_AND_VOICE."""
        ctx = create_mock_context(regime="OPEN", acoustic_safe=True, drift_risk_band="low")
        decision = run_p21(ctx)

        assert decision.delivery_mode == DeliveryMode.TEXT_AND_VOICE
        assert decision.delivery_allowed is True
        assert decision.allows_voice()
        assert decision.allows_text()

    def test_careful_regime_safe_returns_text_and_voice(self):
        """Test: CAREFUL + safe → TEXT_AND_VOICE."""
        ctx = create_mock_context(regime="CAREFUL")
        ctx.p6_regime.regime = "CAREFUL"
        decision = run_p21(ctx)

        assert decision.delivery_mode == DeliveryMode.TEXT_AND_VOICE

    def test_de_escalate_regime_safe_returns_text_and_voice(self):
        """Test: DE_ESCALATE + safe → TEXT_AND_VOICE."""
        ctx = create_mock_context(regime="DE_ESCALATE")
        ctx.p6_regime.regime = "DE_ESCALATE"
        decision = run_p21(ctx)

        assert decision.delivery_mode == DeliveryMode.TEXT_AND_VOICE

    def test_reflect_regime_safe_returns_text_and_voice(self):
        """Test: REFLECT + safe → TEXT_AND_VOICE."""
        ctx = create_mock_context(regime="REFLECT")
        ctx.p6_regime.regime = "REFLECT"
        decision = run_p21(ctx)

        assert decision.delivery_mode == DeliveryMode.TEXT_AND_VOICE

    def test_inform_regime_safe_returns_text_and_voice(self):
        """Test: INFORM + safe → TEXT_AND_VOICE."""
        ctx = create_mock_context(regime="INFORM")
        ctx.p6_regime.regime = "INFORM"
        decision = run_p21(ctx)

        assert decision.delivery_mode == DeliveryMode.TEXT_AND_VOICE


class TestConservativeDefault:
    """Test conservative default behavior."""

    def test_unknown_regime_returns_text_only(self):
        """Test: Unknown regime → TEXT_ONLY (conservative default)."""
        ctx = create_mock_context(regime="UNKNOWN_REGIME")
        decision = run_p21(ctx)

        assert decision.delivery_mode == DeliveryMode.TEXT_ONLY
        assert TAG_CONSERVATIVE_DEFAULT in decision.enforcement_tags

    def test_no_regime_returns_text_only(self):
        """Test: No regime → TEXT_ONLY (conservative default)."""
        ctx = MockPipelineContext()
        decision = run_p21(ctx)

        assert decision.delivery_mode == DeliveryMode.TEXT_ONLY
        assert TAG_CONSERVATIVE_DEFAULT in decision.enforcement_tags


# =============================================================================
# Group 5: Invariant Tests
# =============================================================================


class TestForbiddenAccessInvariants:
    """Test that forbidden attribute access raises violations."""

    def test_access_forbidden_acoustic_attribute_raises(self):
        """Test: Attempt to access acoustic data → FAIL."""
        for attr in FORBIDDEN_ACOUSTIC_ATTRS:
            with pytest.raises(DeliveryInvariantViolation, match="forbidden attribute"):
                access_forbidden_attribute(None, attr)

    def test_access_forbidden_lexical_attribute_raises(self):
        """Test: Attempt to access lexical data → FAIL."""
        with pytest.raises(DeliveryInvariantViolation):
            access_forbidden_attribute(None, "lexical_items")

    def test_access_forbidden_semantic_attribute_raises(self):
        """Test: Attempt to access semantic data → FAIL."""
        with pytest.raises(DeliveryInvariantViolation):
            access_forbidden_attribute(None, "semantic_slots")

    def test_access_forbidden_ontology_attribute_raises(self):
        """Test: Attempt to access ontology data → FAIL."""
        with pytest.raises(DeliveryInvariantViolation):
            access_forbidden_attribute(None, "vrtti_mapping")

    def test_all_forbidden_attrs_covered(self):
        """Test that ALL_FORBIDDEN_ATTRS contains all forbidden attributes."""
        assert "acoustic_units" in ALL_FORBIDDEN_ATTRS
        assert "lexical_items" in ALL_FORBIDDEN_ATTRS
        assert "semantic_slots" in ALL_FORBIDDEN_ATTRS
        assert "vrtti_mapping" in ALL_FORBIDDEN_ATTRS


class TestDeterminism:
    """Test determinism (same input → same output)."""

    def test_same_context_same_decision_mode(self):
        """Test: Same context → same delivery_mode."""
        ctx = create_mock_context()

        decision1 = run_p21(ctx)
        decision2 = run_p21(ctx)

        assert decision1.delivery_mode == decision2.delivery_mode

    def test_same_context_same_delivery_allowed(self):
        """Test: Same context → same delivery_allowed."""
        ctx = create_mock_context()

        decision1 = run_p21(ctx)
        decision2 = run_p21(ctx)

        assert decision1.delivery_allowed == decision2.delivery_allowed

    def test_same_context_same_enforcement_tags(self):
        """Test: Same context → same enforcement_tags."""
        ctx = create_mock_context()

        decision1 = run_p21(ctx)
        decision2 = run_p21(ctx)

        assert decision1.enforcement_tags == decision2.enforcement_tags

    def test_multiple_runs_deterministic(self):
        """Test: Multiple runs with same input → identical output."""
        ctx = create_mock_context(regime="HOLD", drift_risk_band="moderate")

        decisions = [run_p21(ctx) for _ in range(10)]

        # All decisions should have the same mode
        modes = {d.delivery_mode for d in decisions}
        assert len(modes) == 1

        # All decisions should have the same allowed status
        allowed = {d.delivery_allowed for d in decisions}
        assert len(allowed) == 1


class TestContextNotModified:
    """Test that resolver does not modify context."""

    def test_resolve_does_not_modify_regime(self):
        """Test: resolve() does not modify ctx.p6_regime."""
        ctx = create_mock_context(regime="OPEN")
        original_regime = ctx.p6_regime.regime

        run_p21(ctx)

        assert ctx.p6_regime.regime == original_regime

    def test_resolve_does_not_modify_blocked(self):
        """Test: resolve() does not modify ctx.phase_minus_one.blocked."""
        ctx = create_mock_context(blocked=False)
        original_blocked = ctx.phase_minus_one.blocked

        run_p21(ctx)

        assert ctx.phase_minus_one.blocked == original_blocked


# =============================================================================
# Group 6: Renderer Subordination Tests
# =============================================================================


class TestRendererSubordination:
    """Test renderer compliance validation."""

    def test_suppressed_renderer_delivers_voice_raises(self):
        """Test: Renderer ignoring SUPPRESSED decision → detected violation."""
        ctx = create_mock_context(blocked=True)
        decision = run_p21(ctx)
        ctx.p21 = decision

        with pytest.raises(DeliveryInvariantViolation, match="RENDERER_OVERRIDE"):
            validate_renderer_compliance(ctx, "voice")

    def test_suppressed_renderer_delivers_text_raises(self):
        """Test: Renderer ignoring SUPPRESSED decision → detected violation."""
        ctx = create_mock_context(blocked=True)
        decision = run_p21(ctx)
        ctx.p21 = decision

        with pytest.raises(DeliveryInvariantViolation, match="RENDERER_OVERRIDE"):
            validate_renderer_compliance(ctx, "text")

    def test_suppressed_renderer_delivers_both_raises(self):
        """Test: Renderer ignoring SUPPRESSED decision → detected violation."""
        ctx = create_mock_context(blocked=True)
        decision = run_p21(ctx)
        ctx.p21 = decision

        with pytest.raises(DeliveryInvariantViolation):
            validate_renderer_compliance(ctx, "both")

    def test_suppressed_renderer_none_passes(self):
        """Test: Renderer respecting SUPPRESSED decision → passes."""
        ctx = create_mock_context(blocked=True)
        decision = run_p21(ctx)
        ctx.p21 = decision

        # Should not raise
        validate_renderer_compliance(ctx, "none")

    def test_text_only_renderer_voice_raises(self):
        """Test: Renderer using voice when TEXT_ONLY → detected violation."""
        ctx = create_mock_context(regime="HOLD")
        decision = run_p21(ctx)
        ctx.p21 = decision

        with pytest.raises(DeliveryInvariantViolation, match="TEXT_ONLY"):
            validate_renderer_compliance(ctx, "voice")

    def test_text_only_renderer_both_raises(self):
        """Test: Renderer using both when TEXT_ONLY → detected violation."""
        ctx = create_mock_context(regime="HOLD")
        decision = run_p21(ctx)
        ctx.p21 = decision

        with pytest.raises(DeliveryInvariantViolation):
            validate_renderer_compliance(ctx, "both")

    def test_text_only_renderer_text_passes(self):
        """Test: Renderer using text when TEXT_ONLY → passes."""
        ctx = create_mock_context(regime="HOLD")
        decision = run_p21(ctx)
        ctx.p21 = decision

        # Should not raise
        validate_renderer_compliance(ctx, "text")

    def test_text_and_voice_renderer_both_passes(self):
        """Test: Renderer using both when TEXT_AND_VOICE → passes."""
        ctx = create_mock_context(regime="OPEN")
        decision = run_p21(ctx)
        ctx.p21 = decision

        # Should not raise
        validate_renderer_compliance(ctx, "both")

    def test_text_and_voice_renderer_voice_passes(self):
        """Test: Renderer using voice when TEXT_AND_VOICE → passes."""
        ctx = create_mock_context(regime="OPEN")
        decision = run_p21(ctx)
        ctx.p21 = decision

        # Should not raise
        validate_renderer_compliance(ctx, "voice")


# =============================================================================
# Group 7: Integration Tests
# =============================================================================


class TestIntegrationFunctions:
    """Test integration helper functions."""

    def test_maybe_run_p21_attaches_decision(self):
        """Test that maybe_run_p21 attaches decision to context."""
        ctx = create_mock_context()

        maybe_run_p21(ctx)

        assert ctx.p21 is not None
        assert isinstance(ctx.p21, DeliveryModeDecision)

    def test_maybe_run_p21_disabled_returns_none(self):
        """Test that maybe_run_p21 returns None when disabled."""
        ctx = create_mock_context()
        ctx._p21_disabled = True

        result = maybe_run_p21(ctx)

        assert result is None

    def test_is_p21_disabled(self):
        """Test is_p21_disabled helper."""
        ctx = create_mock_context()
        assert is_p21_disabled(ctx) is False

        ctx._p21_disabled = True
        assert is_p21_disabled(ctx) is True

    def test_has_p21_decision(self):
        """Test has_p21_decision helper."""
        ctx = create_mock_context()
        assert has_p21_decision(ctx) is False

        maybe_run_p21(ctx)
        assert has_p21_decision(ctx) is True

    def test_get_p21_decision(self):
        """Test get_p21_decision helper."""
        ctx = create_mock_context()
        assert get_p21_decision(ctx) is None

        maybe_run_p21(ctx)
        decision = get_p21_decision(ctx)
        assert decision is not None

    def test_get_delivery_mode(self):
        """Test get_delivery_mode helper."""
        ctx = create_mock_context()
        # Default when no decision
        assert get_delivery_mode(ctx) == DeliveryMode.TEXT_ONLY

        maybe_run_p21(ctx)
        mode = get_delivery_mode(ctx)
        assert mode == DeliveryMode.TEXT_AND_VOICE

    def test_is_delivery_allowed(self):
        """Test is_delivery_allowed helper."""
        ctx = create_mock_context()
        # Default when no decision
        assert is_delivery_allowed(ctx) is True

        ctx = create_mock_context(blocked=True)
        maybe_run_p21(ctx)
        assert is_delivery_allowed(ctx) is False

    def test_allows_voice_delivery(self):
        """Test allows_voice_delivery helper."""
        ctx = create_mock_context()
        # Default when no decision
        assert allows_voice_delivery(ctx) is False

        maybe_run_p21(ctx)
        assert allows_voice_delivery(ctx) is True

        ctx = create_mock_context(regime="HOLD")
        maybe_run_p21(ctx)
        assert allows_voice_delivery(ctx) is False

    def test_allows_text_delivery(self):
        """Test allows_text_delivery helper."""
        ctx = create_mock_context()
        # Default when no decision
        assert allows_text_delivery(ctx) is True

        maybe_run_p21(ctx)
        assert allows_text_delivery(ctx) is True

    def test_is_suppressed(self):
        """Test is_suppressed helper."""
        ctx = create_mock_context()
        assert is_suppressed(ctx) is False

        ctx = create_mock_context(blocked=True)
        maybe_run_p21(ctx)
        assert is_suppressed(ctx) is True


class TestRunP21Directly:
    """Test run_p21_directly for testing scenarios."""

    def test_blocked_directly(self):
        """Test run_p21_directly with blocked=True."""
        decision = run_p21_directly(blocked=True)
        assert decision.is_suppressed()

    def test_hold_regime_directly(self):
        """Test run_p21_directly with regime=HOLD."""
        decision = run_p21_directly(regime="HOLD")
        assert decision.is_text_only()

    def test_acoustic_false_directly(self):
        """Test run_p21_directly with acoustic_permission_flag=False."""
        decision = run_p21_directly(acoustic_permission_flag=False)
        assert decision.is_text_only()

    def test_high_drift_directly(self):
        """Test run_p21_directly with drift_risk_band=high."""
        decision = run_p21_directly(drift_risk_band="high")
        assert decision.is_text_only()

    def test_normal_directly(self):
        """Test run_p21_directly with safe parameters."""
        decision = run_p21_directly(
            blocked=False,
            regime="OPEN",
            acoustic_permission_flag=True,
            drift_risk_band="low",
        )
        assert decision.allows_voice()


class TestResolverVersion:
    """Test resolver version tracking."""

    def test_resolver_has_version(self):
        """Test that resolver has version property."""
        resolver = get_p21_resolver()
        assert resolver.version == P21_VERSION

    def test_version_matches_schema(self):
        """Test that resolver version matches schema version."""
        resolver = DeliveryModeResolver()
        assert resolver.version == P21_VERSION


class TestHelperMethods:
    """Test DeliveryModeDecision helper methods."""

    def test_is_suppressed_method(self):
        """Test is_suppressed() method."""
        decision = create_suppressed_decision(
            reason="test",
            enforcement_tags={TAG_BLOCKED_BY_UPSTREAM},
        )
        assert decision.is_suppressed() is True

    def test_is_text_only_method(self):
        """Test is_text_only() method."""
        decision = create_text_only_decision(
            reason="test",
            enforcement_tags={TAG_HOLD_REGIME},
        )
        assert decision.is_text_only() is True

    def test_allows_voice_method(self):
        """Test allows_voice() method."""
        decision = create_decision(
            delivery_mode=DeliveryMode.TEXT_AND_VOICE,
            delivery_allowed=True,
            blocked_reason=None,
            enforcement_tags={TAG_NORMAL_OPERATION},
        )
        assert decision.allows_voice() is True

        text_only = create_text_only_decision(
            reason="test",
            enforcement_tags={TAG_CONSERVATIVE_DEFAULT},
        )
        assert text_only.allows_voice() is False

    def test_allows_text_method(self):
        """Test allows_text() method."""
        for mode in [DeliveryMode.TEXT_ONLY, DeliveryMode.TEXT_AND_VOICE, DeliveryMode.VOICE_PROHIBITED]:
            decision = create_decision(
                delivery_mode=mode,
                delivery_allowed=True,
                blocked_reason="test" if mode != DeliveryMode.TEXT_AND_VOICE else None,
                enforcement_tags={TAG_CONSERVATIVE_DEFAULT},
            )
            assert decision.allows_text() is True

    def test_is_fully_blocked_method(self):
        """Test is_fully_blocked() method."""
        decision = create_suppressed_decision(
            reason="test",
            enforcement_tags={TAG_BLOCKED_BY_UPSTREAM},
        )
        assert decision.is_fully_blocked() is True

        allowed = create_text_only_decision(
            reason="test",
            enforcement_tags={TAG_CONSERVATIVE_DEFAULT},
        )
        assert allowed.is_fully_blocked() is False

    def test_has_enforcement_tag_method(self):
        """Test has_enforcement_tag() method."""
        decision = create_decision(
            delivery_mode=DeliveryMode.TEXT_ONLY,
            delivery_allowed=True,
            blocked_reason="test",
            enforcement_tags={TAG_HOLD_REGIME, TAG_ACOUSTIC_SAFETY_RESTRICTION},
        )
        assert decision.has_enforcement_tag(TAG_HOLD_REGIME) is True
        assert decision.has_enforcement_tag(TAG_ACOUSTIC_SAFETY_RESTRICTION) is True
        assert decision.has_enforcement_tag(TAG_BLOCKED_BY_UPSTREAM) is False


# =============================================================================
# Group 8: Rule Priority Tests
# =============================================================================


class TestRulePriority:
    """Test that rules are applied in the correct priority order."""

    def test_blocked_takes_priority_over_regime(self):
        """Test: blocked=True takes priority over regime."""
        ctx = create_mock_context(blocked=True, regime="OPEN")
        decision = run_p21(ctx)

        # Should be SUPPRESSED (rule 1) not TEXT_AND_VOICE (rule 5)
        assert decision.is_suppressed()

    def test_hold_takes_priority_over_acoustic(self):
        """Test: HOLD regime takes priority over acoustic permission."""
        ctx = create_mock_context(regime="HOLD", acoustic_safe=True)
        decision = run_p21(ctx)

        # Should be TEXT_ONLY (rule 2 - HOLD)
        assert decision.is_text_only()
        assert TAG_HOLD_REGIME in decision.enforcement_tags

    def test_acoustic_takes_priority_over_drift(self):
        """Test: acoustic_permission_flag=False takes priority over high drift."""
        ctx = create_mock_context(regime="OPEN", acoustic_safe=False, drift_risk_band="high")
        decision = run_p21(ctx)

        # Should be TEXT_ONLY with acoustic tag (rule 3) not drift tag (rule 4)
        assert decision.is_text_only()
        assert TAG_ACOUSTIC_SAFETY_RESTRICTION in decision.enforcement_tags

    def test_drift_takes_priority_over_normal(self):
        """Test: high drift takes priority over normal operation."""
        ctx = create_mock_context(regime="OPEN", acoustic_safe=True, drift_risk_band="high")
        decision = run_p21(ctx)

        # Should be TEXT_ONLY (rule 4 - high drift) not TEXT_AND_VOICE (rule 5)
        assert decision.is_text_only()
        assert TAG_HIGH_DRIFT_RISK in decision.enforcement_tags
