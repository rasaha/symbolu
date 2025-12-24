"""
Test Suite: P23 Inner-Outer Alignment Observer

Comprehensive tests for Phase 23 alignment observation.

This phase is observer-only and non-authoritative.

Test Groups:
    1. Schema Tests - AlignmentState and P23AlignmentReport validation
    2. Alignment Cases - Pressure vs regime alignment rules
    3. Discourse Tension Tests - Discourse compatibility adjustments
    4. Safety Invariant Tests - P23 does not block, modify, or infer
    5. Determinism Tests - Same input → same output
    6. Forbidden Access Tests - P23 never accesses forbidden data
    7. Integration Tests - Pipeline integration functions
    8. Edge Case Tests - Boundary conditions and error handling
"""

import pytest
from dataclasses import dataclass, FrozenInstanceError
from typing import Any, Optional

from symbolu.mechanical.pipeline.p23_alignment import (
    # Schema
    P23_VERSION,
    AlignmentState,
    P23AlignmentReport,
    P23InvariantViolation,
    create_aligned_report,
    create_neutral_report,
    create_tension_report,
    create_contradiction_report,
    create_empty_report,
    # Resolver
    AlignmentObserver,
    observe_alignment,
    access_forbidden_attribute,
    FORBIDDEN_TEXT_ATTRS,
    FORBIDDEN_TOKEN_ATTRS,
    FORBIDDEN_SEMANTIC_ATTRS,
    FORBIDDEN_INTENT_ATTRS,
    FORBIDDEN_ONTOLOGY_ATTRS,
    ALL_FORBIDDEN_ATTRS,
    REGIME_MAX_PRESSURE,
    PRESSURE_ORDER,
    TAG_ALIGNED,
    TAG_TENSION,
    TAG_CONTRADICTION,
    TAG_PRESSURE_EXCEEDS_DISCOURSE,
    TAG_PRESSURE_FORM_MISMATCH,
    TAG_HIGH_PRESSURE_DEFERRAL,
    TAG_CHAOTIC_MOTION,
    TAG_OSCILLATORY_MOTION,
    TAG_CONSERVATIVE_REGIME,
    # Integration
    get_p23_observer,
    maybe_run_p23,
    run_p23,
    run_p23_directly,
    is_p23_disabled,
    has_p23_report,
    get_p23_report,
    get_alignment_state,
    get_tension_score,
    get_alignment_tags,
    is_aligned,
    is_tension,
    get_p23_version,
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
class MockP7:
    """Mock P7 discourse envelope."""
    act: str = "DEFERRAL"


@dataclass
class MockP22:
    """Mock P22 acoustic witness."""
    pressure_band: str = "low"
    motion_balance: str = "balanced"


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    phase_minus_one: Optional[MockPO1] = None
    p6_regime: Optional[MockP6] = None
    p7_discourse_envelope: Optional[MockP7] = None
    p22_acoustic_witness: Optional[MockP22] = None
    p23_alignment_report: Optional[P23AlignmentReport] = None
    p23: Optional[P23AlignmentReport] = None
    _p23_disabled: bool = False


def create_mock_context(
    blocked: bool = False,
    regime: str = "OPEN",
    discourse_act: str = "DEFERRAL",
    pressure_band: str = "low",
    motion_balance: str = "balanced",
) -> MockPipelineContext:
    """Factory function to create mock contexts for testing."""
    return MockPipelineContext(
        phase_minus_one=MockPO1(blocked=blocked),
        p6_regime=MockP6(regime=regime),
        p7_discourse_envelope=MockP7(act=discourse_act),
        p22_acoustic_witness=MockP22(
            pressure_band=pressure_band,
            motion_balance=motion_balance,
        ),
    )


# =============================================================================
# Group 1: Schema Tests
# =============================================================================


class TestAlignmentStateSchema:
    """Test AlignmentState enum."""

    def test_enum_values_exist(self):
        """Test that all expected enum values exist."""
        assert AlignmentState.ALIGNED.value == "aligned"
        assert AlignmentState.NEUTRAL.value == "neutral"
        assert AlignmentState.TENSION.value == "tension"
        assert AlignmentState.CONTRADICTION.value == "contradiction"

    def test_enum_count(self):
        """Test that enum has exactly 4 values."""
        assert len(AlignmentState) == 4


class TestP23AlignmentReportSchema:
    """Test P23AlignmentReport dataclass."""

    def test_frozen_dataclass(self):
        """Test that report is frozen (immutable)."""
        report = create_aligned_report()
        with pytest.raises(FrozenInstanceError):
            report.alignment_state = AlignmentState.TENSION

    def test_cannot_modify_tension_score(self):
        """Test that tension_score cannot be modified."""
        report = create_aligned_report()
        with pytest.raises(FrozenInstanceError):
            report.tension_score = 0.9

    def test_alignment_tags_frozenset(self):
        """Test that alignment_tags is a frozenset."""
        report = create_aligned_report(tags=frozenset({"tag1", "tag2"}))
        assert isinstance(report.alignment_tags, frozenset)

    def test_observer_only_always_true(self):
        """Test that observer_only is always True."""
        report = create_aligned_report()
        assert report.observer_only is True

    def test_observer_only_cannot_be_false(self):
        """Test that observer_only=False raises ValueError."""
        with pytest.raises(ValueError, match="observer_only must be True"):
            P23AlignmentReport(
                alignment_state=AlignmentState.ALIGNED,
                tension_score=0.0,
                alignment_tags=frozenset(),
                observer_only=False,
            )

    def test_to_dict_serialization(self):
        """Test that report can be serialized to dict."""
        report = create_aligned_report(tags=frozenset({"test_tag"}))
        data = report.to_dict()
        assert isinstance(data, dict)
        assert data["alignment_state"] == "aligned"
        assert data["observer_only"] is True
        assert "test_tag" in data["alignment_tags"]

    def test_tension_score_must_be_in_range(self):
        """Test that tension_score must be in [0.0, 1.0]."""
        with pytest.raises(ValueError, match="must be in"):
            P23AlignmentReport(
                alignment_state=AlignmentState.ALIGNED,
                tension_score=1.5,  # Out of range
                alignment_tags=frozenset(),
            )

    def test_tension_score_negative_rejected(self):
        """Test that negative tension_score is rejected."""
        with pytest.raises(ValueError, match="must be in"):
            P23AlignmentReport(
                alignment_state=AlignmentState.ALIGNED,
                tension_score=-0.1,  # Negative
                alignment_tags=frozenset(),
            )

    def test_alignment_tags_must_be_frozenset(self):
        """Test that alignment_tags must be frozenset."""
        with pytest.raises(ValueError, match="must be frozenset"):
            P23AlignmentReport(
                alignment_state=AlignmentState.ALIGNED,
                tension_score=0.0,
                alignment_tags={"not", "frozen"},  # Regular set
            )

    def test_alignment_tags_must_contain_strings(self):
        """Test that alignment_tags must contain only strings."""
        with pytest.raises(ValueError, match="must contain only strings"):
            P23AlignmentReport(
                alignment_state=AlignmentState.ALIGNED,
                tension_score=0.0,
                alignment_tags=frozenset({123, 456}),  # Integers
            )


class TestFactoryFunctions:
    """Test factory functions for creating reports."""

    def test_create_aligned_report(self):
        """Test create_aligned_report factory."""
        report = create_aligned_report()
        assert report.alignment_state == AlignmentState.ALIGNED
        assert report.tension_score == 0.0

    def test_create_neutral_report(self):
        """Test create_neutral_report factory."""
        report = create_neutral_report()
        assert report.alignment_state == AlignmentState.NEUTRAL

    def test_create_tension_report(self):
        """Test create_tension_report factory."""
        report = create_tension_report()
        assert report.alignment_state == AlignmentState.TENSION

    def test_create_contradiction_report(self):
        """Test create_contradiction_report factory."""
        report = create_contradiction_report()
        assert report.alignment_state == AlignmentState.CONTRADICTION

    def test_create_empty_report(self):
        """Test create_empty_report factory."""
        report = create_empty_report()
        assert report.alignment_state == AlignmentState.NEUTRAL
        assert report.tension_score == 0.0
        assert len(report.alignment_tags) == 0


# =============================================================================
# Group 2: Alignment Cases Tests
# =============================================================================


class TestAlignmentCases:
    """Test alignment rules based on pressure vs regime."""

    def test_low_pressure_vs_hold_neutral(self):
        """Test: low pressure vs HOLD → NEUTRAL (pressure == allowed)."""
        report = run_p23_directly(
            pressure_band="low",
            motion_stability="stable",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        # When pressure exactly equals allowed, result is NEUTRAL
        assert report.alignment_state == AlignmentState.NEUTRAL

    def test_low_pressure_vs_careful_neutral(self):
        """Test: low pressure vs CAREFUL → NEUTRAL (pressure == allowed)."""
        report = run_p23_directly(
            pressure_band="low",
            motion_stability="stable",
            regime="CAREFUL",
            discourse_act="DEFERRAL",
        )
        # When pressure exactly equals allowed, result is NEUTRAL
        assert report.alignment_state == AlignmentState.NEUTRAL

    def test_moderate_pressure_vs_de_escalate_neutral(self):
        """Test: moderate pressure vs DE_ESCALATE → NEUTRAL."""
        report = run_p23_directly(
            pressure_band="moderate",
            motion_stability="stable",
            regime="DE_ESCALATE",
            discourse_act="REFLECTION",
        )
        assert report.alignment_state == AlignmentState.NEUTRAL

    def test_high_pressure_vs_open_neutral(self):
        """Test: high pressure vs OPEN → NEUTRAL (both at max)."""
        report = run_p23_directly(
            pressure_band="high",
            motion_stability="stable",
            regime="OPEN",
            discourse_act="EXPLANATION",
        )
        assert report.alignment_state == AlignmentState.NEUTRAL

    def test_high_pressure_vs_careful_contradiction(self):
        """Test: high pressure vs CAREFUL → CONTRADICTION."""
        report = run_p23_directly(
            pressure_band="high",
            motion_stability="stable",
            regime="CAREFUL",
            discourse_act="DEFERRAL",
        )
        assert report.alignment_state == AlignmentState.CONTRADICTION

    def test_high_pressure_vs_hold_contradiction(self):
        """Test: high pressure vs HOLD → CONTRADICTION."""
        report = run_p23_directly(
            pressure_band="high",
            motion_stability="stable",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        assert report.alignment_state == AlignmentState.CONTRADICTION

    def test_moderate_pressure_vs_hold_tension(self):
        """Test: moderate pressure vs HOLD → TENSION (exceeds by 1 band)."""
        report = run_p23_directly(
            pressure_band="moderate",
            motion_stability="stable",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        assert report.alignment_state == AlignmentState.TENSION

    def test_moderate_pressure_vs_careful_tension(self):
        """Test: moderate pressure vs CAREFUL → TENSION (exceeds by 1 band)."""
        report = run_p23_directly(
            pressure_band="moderate",
            motion_stability="stable",
            regime="CAREFUL",
            discourse_act="DEFERRAL",
        )
        assert report.alignment_state == AlignmentState.TENSION

    def test_high_pressure_vs_de_escalate_tension(self):
        """Test: high pressure vs DE_ESCALATE → TENSION (exceeds by 1 band)."""
        report = run_p23_directly(
            pressure_band="high",
            motion_stability="stable",
            regime="DE_ESCALATE",
            discourse_act="REFLECTION",
        )
        assert report.alignment_state == AlignmentState.TENSION

    def test_low_pressure_vs_open_aligned(self):
        """Test: low pressure vs OPEN → ALIGNED (below allowed)."""
        report = run_p23_directly(
            pressure_band="low",
            motion_stability="stable",
            regime="OPEN",
            discourse_act="EXPLANATION",
        )
        assert report.alignment_state == AlignmentState.ALIGNED


# =============================================================================
# Group 3: Discourse Tension Tests
# =============================================================================


class TestDiscourseTension:
    """Test discourse compatibility adjustments."""

    def test_high_pressure_deferral_adds_tag(self):
        """Test: high pressure + DEFERRAL → add pressure_exceeds_discourse tag."""
        report = run_p23_directly(
            pressure_band="high",
            motion_stability="stable",
            regime="OPEN",
            discourse_act="DEFERRAL",
        )
        assert TAG_PRESSURE_EXCEEDS_DISCOURSE in report.alignment_tags
        assert TAG_HIGH_PRESSURE_DEFERRAL in report.alignment_tags

    def test_high_pressure_reflection_no_penalty(self):
        """Test: high pressure + REFLECTION → no penalty tag."""
        report = run_p23_directly(
            pressure_band="high",
            motion_stability="stable",
            regime="OPEN",
            discourse_act="REFLECTION",
        )
        assert TAG_PRESSURE_EXCEEDS_DISCOURSE not in report.alignment_tags
        assert TAG_PRESSURE_FORM_MISMATCH not in report.alignment_tags

    def test_high_pressure_question_adds_mismatch_tag(self):
        """Test: high pressure + QUESTION → add pressure_form_mismatch tag."""
        report = run_p23_directly(
            pressure_band="high",
            motion_stability="stable",
            regime="OPEN",
            discourse_act="QUESTION",
        )
        assert TAG_PRESSURE_FORM_MISMATCH in report.alignment_tags

    def test_low_pressure_deferral_no_tag(self):
        """Test: low pressure + DEFERRAL → no discourse pressure tag."""
        report = run_p23_directly(
            pressure_band="low",
            motion_stability="stable",
            regime="OPEN",
            discourse_act="DEFERRAL",
        )
        assert TAG_PRESSURE_EXCEEDS_DISCOURSE not in report.alignment_tags

    def test_moderate_pressure_question_no_tag(self):
        """Test: moderate pressure + QUESTION → no mismatch tag (only high pressure)."""
        report = run_p23_directly(
            pressure_band="moderate",
            motion_stability="stable",
            regime="OPEN",
            discourse_act="QUESTION",
        )
        assert TAG_PRESSURE_FORM_MISMATCH not in report.alignment_tags


# =============================================================================
# Group 4: Safety Invariant Tests
# =============================================================================


class TestSafetyInvariants:
    """Test that P23 does not block, modify regime, or infer emotion."""

    def test_p23_does_not_block_output(self):
        """Test: P23 does not block output."""
        # P23 should always return a report, never block
        report = run_p23_directly(
            pressure_band="high",
            motion_stability="chaotic",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        # Report should exist even for worst-case tension
        assert report is not None
        assert isinstance(report, P23AlignmentReport)

    def test_p23_does_not_modify_regime(self):
        """Test: P23 does not modify regime."""
        ctx = create_mock_context(regime="HOLD")
        original_regime = ctx.p6_regime.regime

        maybe_run_p23(ctx)

        # Regime should be unchanged
        assert ctx.p6_regime.regime == original_regime

    def test_p23_does_not_modify_discourse(self):
        """Test: P23 does not modify discourse."""
        ctx = create_mock_context(discourse_act="DEFERRAL")
        original_act = ctx.p7_discourse_envelope.act

        maybe_run_p23(ctx)

        # Discourse should be unchanged
        assert ctx.p7_discourse_envelope.act == original_act

    def test_p23_does_not_modify_p22(self):
        """Test: P23 does not modify P22 witness."""
        ctx = create_mock_context(pressure_band="high")
        original_pressure = ctx.p22_acoustic_witness.pressure_band

        maybe_run_p23(ctx)

        # P22 should be unchanged
        assert ctx.p22_acoustic_witness.pressure_band == original_pressure

    def test_p23_does_not_infer_emotion(self):
        """Test: P23 does not infer emotion."""
        report = run_p23_directly(
            pressure_band="high",
            motion_stability="chaotic",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        # Report should not contain emotion labels
        report_dict = report.to_dict()
        assert "emotion" not in str(report_dict).lower()
        assert "angry" not in str(report_dict).lower()
        assert "sad" not in str(report_dict).lower()
        assert "happy" not in str(report_dict).lower()
        assert "fear" not in str(report_dict).lower()

    def test_p23_does_not_infer_intent(self):
        """Test: P23 does not infer intent."""
        report = run_p23_directly(
            pressure_band="high",
            motion_stability="stable",
            regime="OPEN",
            discourse_act="EXPLANATION",
        )
        # Report should not contain intent labels
        report_dict = report.to_dict()
        assert "intent" not in str(report_dict).lower()
        assert "goal" not in str(report_dict).lower()
        assert "want" not in str(report_dict).lower()


# =============================================================================
# Group 5: Determinism Tests
# =============================================================================


class TestDeterminism:
    """Test determinism (same input → same output)."""

    def test_same_input_same_alignment_state(self):
        """Test: Same input → same alignment_state."""
        report1 = run_p23_directly(
            pressure_band="high",
            motion_stability="stable",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        report2 = run_p23_directly(
            pressure_band="high",
            motion_stability="stable",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        assert report1.alignment_state == report2.alignment_state

    def test_same_input_same_tension_score(self):
        """Test: Same input → same tension_score."""
        report1 = run_p23_directly(
            pressure_band="moderate",
            motion_stability="oscillatory",
            regime="CAREFUL",
            discourse_act="QUESTION",
        )
        report2 = run_p23_directly(
            pressure_band="moderate",
            motion_stability="oscillatory",
            regime="CAREFUL",
            discourse_act="QUESTION",
        )
        assert report1.tension_score == report2.tension_score

    def test_same_input_same_tags(self):
        """Test: Same input → same alignment_tags."""
        report1 = run_p23_directly(
            pressure_band="high",
            motion_stability="chaotic",
            regime="OPEN",
            discourse_act="DEFERRAL",
        )
        report2 = run_p23_directly(
            pressure_band="high",
            motion_stability="chaotic",
            regime="OPEN",
            discourse_act="DEFERRAL",
        )
        assert report1.alignment_tags == report2.alignment_tags

    def test_multiple_runs_deterministic(self):
        """Test: Multiple runs with same input → identical output."""
        reports = [
            run_p23_directly(
                pressure_band="moderate",
                motion_stability="stable",
                regime="DE_ESCALATE",
                discourse_act="REFLECTION",
            )
            for _ in range(10)
        ]
        # All reports should have the same state
        states = {r.alignment_state for r in reports}
        assert len(states) == 1

        # All reports should have the same score
        scores = {r.tension_score for r in reports}
        assert len(scores) == 1

        # All reports should have the same tags
        tags = {r.alignment_tags for r in reports}
        assert len(tags) == 1


# =============================================================================
# Group 6: Forbidden Access Tests
# =============================================================================


class TestForbiddenAccess:
    """Test that P23 never accesses forbidden data."""

    def test_access_forbidden_text_raises(self):
        """Test: Attempt to access text data → FAIL."""
        for attr in FORBIDDEN_TEXT_ATTRS:
            with pytest.raises(P23InvariantViolation, match="forbidden attribute"):
                access_forbidden_attribute(None, attr)

    def test_access_forbidden_token_raises(self):
        """Test: Attempt to access token data → FAIL."""
        for attr in FORBIDDEN_TOKEN_ATTRS:
            with pytest.raises(P23InvariantViolation, match="forbidden attribute"):
                access_forbidden_attribute(None, attr)

    def test_access_forbidden_semantic_raises(self):
        """Test: Attempt to access semantic data → FAIL."""
        for attr in FORBIDDEN_SEMANTIC_ATTRS:
            with pytest.raises(P23InvariantViolation, match="forbidden attribute"):
                access_forbidden_attribute(None, attr)

    def test_access_forbidden_intent_raises(self):
        """Test: Attempt to access intent data → FAIL."""
        for attr in FORBIDDEN_INTENT_ATTRS:
            with pytest.raises(P23InvariantViolation, match="forbidden attribute"):
                access_forbidden_attribute(None, attr)

    def test_access_forbidden_ontology_raises(self):
        """Test: Attempt to access ontology data → FAIL."""
        for attr in FORBIDDEN_ONTOLOGY_ATTRS:
            with pytest.raises(P23InvariantViolation, match="forbidden attribute"):
                access_forbidden_attribute(None, attr)

    def test_all_forbidden_attrs_covered(self):
        """Test that ALL_FORBIDDEN_ATTRS contains expected attributes."""
        assert "user_raw_text" in ALL_FORBIDDEN_ATTRS
        assert "tokens" in ALL_FORBIDDEN_ATTRS
        assert "semantic_slots" in ALL_FORBIDDEN_ATTRS
        assert "intent" in ALL_FORBIDDEN_ATTRS
        assert "ontology" in ALL_FORBIDDEN_ATTRS

    def test_p23_never_emits_intent(self):
        """Test: P23 output never contains intent inference."""
        report = run_p23_directly(
            pressure_band="high",
            motion_stability="chaotic",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        # Check tags for intent-related strings
        for tag in report.alignment_tags:
            assert "intent" not in tag.lower()
            assert "goal" not in tag.lower()

    def test_p23_never_emits_emotion(self):
        """Test: P23 output never contains emotion inference."""
        report = run_p23_directly(
            pressure_band="high",
            motion_stability="chaotic",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        # Check tags for emotion-related strings
        for tag in report.alignment_tags:
            assert "emotion" not in tag.lower()
            assert "angry" not in tag.lower()
            assert "sad" not in tag.lower()
            assert "fear" not in tag.lower()


# =============================================================================
# Group 7: Integration Tests
# =============================================================================


class TestIntegrationFunctions:
    """Test integration helper functions."""

    def test_maybe_run_p23_attaches_report(self):
        """Test that maybe_run_p23 attaches report to context."""
        ctx = create_mock_context()

        maybe_run_p23(ctx)

        assert ctx.p23_alignment_report is not None
        assert isinstance(ctx.p23_alignment_report, P23AlignmentReport)

    def test_maybe_run_p23_with_blocked_po1(self):
        """Test that maybe_run_p23 handles blocked PO1."""
        ctx = create_mock_context(blocked=True)

        result = maybe_run_p23(ctx)

        # Should return ctx with an empty report
        assert result is ctx
        assert ctx.p23_alignment_report is not None

    def test_maybe_run_p23_disabled_returns_unchanged(self):
        """Test that maybe_run_p23 returns unchanged when disabled."""
        ctx = create_mock_context()
        ctx._p23_disabled = True

        result = maybe_run_p23(ctx)

        assert result is ctx
        assert ctx.p23_alignment_report is None

    def test_is_p23_disabled(self):
        """Test is_p23_disabled helper."""
        ctx = create_mock_context()
        assert is_p23_disabled(ctx) is False

        ctx._p23_disabled = True
        assert is_p23_disabled(ctx) is True

    def test_has_p23_report(self):
        """Test has_p23_report helper."""
        ctx = create_mock_context()
        assert has_p23_report(ctx) is False

        maybe_run_p23(ctx)
        assert has_p23_report(ctx) is True

    def test_get_p23_report(self):
        """Test get_p23_report helper."""
        ctx = create_mock_context()
        assert get_p23_report(ctx) is None

        maybe_run_p23(ctx)
        report = get_p23_report(ctx)
        assert report is not None

    def test_get_alignment_state_helper(self):
        """Test get_alignment_state helper."""
        ctx = create_mock_context()
        # Default when no report
        assert get_alignment_state(ctx) == AlignmentState.NEUTRAL

        maybe_run_p23(ctx)
        state = get_alignment_state(ctx)
        assert isinstance(state, AlignmentState)

    def test_get_tension_score_helper(self):
        """Test get_tension_score helper."""
        ctx = create_mock_context()
        # Default when no report
        assert get_tension_score(ctx) == 0.0

        maybe_run_p23(ctx)
        score = get_tension_score(ctx)
        assert 0.0 <= score <= 1.0

    def test_get_alignment_tags_helper(self):
        """Test get_alignment_tags helper."""
        ctx = create_mock_context()
        # Default when no report
        assert get_alignment_tags(ctx) == frozenset()

        maybe_run_p23(ctx)
        tags = get_alignment_tags(ctx)
        assert isinstance(tags, frozenset)

    def test_is_aligned_helper(self):
        """Test is_aligned helper."""
        ctx = create_mock_context(
            pressure_band="low",
            regime="OPEN",
        )
        maybe_run_p23(ctx)
        assert is_aligned(ctx) is True

    def test_is_tension_helper(self):
        """Test is_tension helper."""
        ctx = create_mock_context(
            pressure_band="high",
            regime="HOLD",
        )
        maybe_run_p23(ctx)
        assert is_tension(ctx) is True


class TestRunP23Directly:
    """Test run_p23_directly for testing scenarios."""

    def test_aligned_scenario(self):
        """Test run_p23_directly with aligned scenario."""
        report = run_p23_directly(
            pressure_band="low",
            regime="OPEN",
        )
        assert report.is_aligned()

    def test_tension_scenario(self):
        """Test run_p23_directly with tension scenario."""
        report = run_p23_directly(
            pressure_band="moderate",
            regime="HOLD",
        )
        assert report.is_tension()

    def test_contradiction_scenario(self):
        """Test run_p23_directly with contradiction scenario."""
        report = run_p23_directly(
            pressure_band="high",
            regime="HOLD",
        )
        assert report.is_contradiction()


class TestResolverVersion:
    """Test resolver version tracking."""

    def test_observer_has_version(self):
        """Test that observer has version property."""
        observer = get_p23_observer()
        assert observer.version == P23_VERSION

    def test_version_matches_schema(self):
        """Test that observer version matches schema version."""
        observer = AlignmentObserver()
        assert observer.version == P23_VERSION

    def test_get_p23_version(self):
        """Test get_p23_version helper."""
        assert get_p23_version() == P23_VERSION


# =============================================================================
# Group 8: Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_none_context(self):
        """Test that None context is handled gracefully."""
        result = maybe_run_p23(None)
        assert result is None

    def test_empty_context(self):
        """Test that empty context returns default values."""
        ctx = MockPipelineContext()
        result = maybe_run_p23(ctx)
        assert result is ctx
        # Should have attached a report with defaults
        assert ctx.p23_alignment_report is not None

    def test_missing_p22_uses_defaults(self):
        """Test that missing P22 witness uses default values."""
        ctx = MockPipelineContext(
            phase_minus_one=MockPO1(blocked=False),
            p6_regime=MockP6(regime="OPEN"),
            p7_discourse_envelope=MockP7(act="DEFERRAL"),
            # No P22 witness
        )
        result = maybe_run_p23(ctx)
        assert result is ctx
        # Should use default "low" pressure
        assert ctx.p23_alignment_report is not None

    def test_missing_p6_uses_defaults(self):
        """Test that missing P6 regime uses default values."""
        ctx = MockPipelineContext(
            phase_minus_one=MockPO1(blocked=False),
            # No P6 regime
            p7_discourse_envelope=MockP7(act="DEFERRAL"),
            p22_acoustic_witness=MockP22(pressure_band="low"),
        )
        result = maybe_run_p23(ctx)
        assert result is ctx
        assert ctx.p23_alignment_report is not None

    def test_missing_p7_uses_defaults(self):
        """Test that missing P7 discourse uses default values."""
        ctx = MockPipelineContext(
            phase_minus_one=MockPO1(blocked=False),
            p6_regime=MockP6(regime="OPEN"),
            # No P7 discourse
            p22_acoustic_witness=MockP22(pressure_band="low"),
        )
        result = maybe_run_p23(ctx)
        assert result is ctx
        assert ctx.p23_alignment_report is not None

    def test_unknown_regime_uses_conservative_default(self):
        """Test that unknown regime uses conservative (low) pressure allowance."""
        report = run_p23_directly(
            pressure_band="moderate",
            motion_stability="stable",
            regime="UNKNOWN_REGIME",
            discourse_act="DEFERRAL",
        )
        # Unknown regime defaults to "low" allowance
        # So moderate pressure should cause TENSION
        assert report.alignment_state == AlignmentState.TENSION

    def test_chaotic_motion_adds_tag(self):
        """Test that chaotic motion adds appropriate tag."""
        report = run_p23_directly(
            pressure_band="low",
            motion_stability="chaotic",
            regime="OPEN",
            discourse_act="DEFERRAL",
        )
        assert TAG_CHAOTIC_MOTION in report.alignment_tags

    def test_oscillatory_motion_adds_tag(self):
        """Test that oscillatory motion adds appropriate tag."""
        report = run_p23_directly(
            pressure_band="low",
            motion_stability="oscillatory",
            regime="OPEN",
            discourse_act="DEFERRAL",
        )
        assert TAG_OSCILLATORY_MOTION in report.alignment_tags

    def test_conservative_regime_adds_tag(self):
        """Test that conservative regime adds appropriate tag."""
        report = run_p23_directly(
            pressure_band="low",
            motion_stability="stable",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        assert TAG_CONSERVATIVE_REGIME in report.alignment_tags


class TestHelperMethods:
    """Test P23AlignmentReport helper methods."""

    def test_is_aligned_method(self):
        """Test is_aligned() method."""
        report = create_aligned_report()
        assert report.is_aligned() is True
        assert report.is_neutral() is False

    def test_is_neutral_method(self):
        """Test is_neutral() method."""
        report = create_neutral_report()
        assert report.is_neutral() is True
        assert report.is_aligned() is False

    def test_is_tension_method(self):
        """Test is_tension() method."""
        report = create_tension_report()
        assert report.is_tension() is True
        assert report.is_contradiction() is False

    def test_is_contradiction_method(self):
        """Test is_contradiction() method."""
        report = create_contradiction_report()
        assert report.is_contradiction() is True
        assert report.is_tension() is False

    def test_has_tag_method(self):
        """Test has_tag() method."""
        report = create_aligned_report(tags=frozenset({"tag1", "tag2"}))
        assert report.has_tag("tag1") is True
        assert report.has_tag("tag2") is True
        assert report.has_tag("tag3") is False


class TestTensionScoreCalculation:
    """Test tension score calculation."""

    def test_aligned_has_low_score(self):
        """Test that ALIGNED state has low tension score."""
        report = run_p23_directly(
            pressure_band="low",
            motion_stability="stable",
            regime="OPEN",
            discourse_act="DEFERRAL",
        )
        assert report.tension_score < 0.25

    def test_tension_has_moderate_score(self):
        """Test that TENSION state has moderate tension score."""
        report = run_p23_directly(
            pressure_band="moderate",
            motion_stability="stable",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        assert 0.4 <= report.tension_score <= 0.6

    def test_contradiction_has_high_score(self):
        """Test that CONTRADICTION state has high tension score."""
        report = run_p23_directly(
            pressure_band="high",
            motion_stability="stable",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        assert report.tension_score >= 0.8

    def test_chaotic_motion_increases_score(self):
        """Test that chaotic motion increases tension score."""
        stable_report = run_p23_directly(
            pressure_band="moderate",
            motion_stability="stable",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        chaotic_report = run_p23_directly(
            pressure_band="moderate",
            motion_stability="chaotic",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        assert chaotic_report.tension_score > stable_report.tension_score


class TestRegimePressureTable:
    """Test regime pressure allowance table."""

    def test_hold_allows_only_low(self):
        """Test that HOLD allows only low pressure."""
        assert REGIME_MAX_PRESSURE["HOLD"] == "low"

    def test_careful_allows_only_low(self):
        """Test that CAREFUL allows only low pressure."""
        assert REGIME_MAX_PRESSURE["CAREFUL"] == "low"

    def test_de_escalate_allows_moderate(self):
        """Test that DE_ESCALATE allows moderate pressure."""
        assert REGIME_MAX_PRESSURE["DE_ESCALATE"] == "moderate"

    def test_open_allows_high(self):
        """Test that OPEN allows high pressure."""
        assert REGIME_MAX_PRESSURE["OPEN"] == "high"

    def test_pressure_order_correct(self):
        """Test that pressure order is correct."""
        assert PRESSURE_ORDER["low"] < PRESSURE_ORDER["moderate"]
        assert PRESSURE_ORDER["moderate"] < PRESSURE_ORDER["high"]
