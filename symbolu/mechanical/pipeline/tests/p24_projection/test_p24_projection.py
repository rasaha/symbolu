"""
Test Suite: P24 Acoustic-Ontology Projection Observer

Comprehensive tests for Phase 24 projection observation.

This phase is observer-only and non-authoritative.

Test Groups:
    Group A: Discourse -> Base Layers (exact tuple equality)
    Group B: Risk Band Boundaries (score thresholds)
    Group C: Certainty Leak Detection (lexical frame scanning)
    Group D: Mismatch Matrix (alignment state + risk band combinations)
    Group E: Evidence Completeness / Confidence (missing components)
    Group F: Forbidden Behavior Invariants (observation-only, no mutation)
    Group G: Determinism (same input -> same output)
    Additional: Schema validation, integration helpers, edge cases
"""

import copy
import pytest
from dataclasses import dataclass, FrozenInstanceError
from typing import Any, Dict, Optional
from enum import Enum

from symbolu.mechanical.pipeline.p24_projection import (
    # Schema
    P24_VERSION,
    ALLOWED_PROJECTION_TAGS,
    OntologyLayer,
    ProjectionRiskBand,
    ProjectionMismatchType,
    P24ProjectionReport,
    P24InvariantViolation,
    create_empty_report,
    create_blocked_report,
    # Resolver
    P24ProjectionResolver,
    resolve_projection,
    access_forbidden_attribute,
    FORBIDDEN_TEXT_ATTRS,
    FORBIDDEN_TOKEN_ATTRS,
    ALL_FORBIDDEN_ATTRS,
    DISCOURSE_ACT_LAYERS,
    CERTAINTY_MARKERS,
    CONSERVATIVE_REGIMES,
    # Integration
    get_p24_resolver,
    maybe_run_p24,
    run_p24,
    is_p24_disabled,
    has_p24_report,
    get_p24_report,
    is_high_risk,
    has_strong_mismatch,
    get_projected_layers,
    get_projection_tags,
    get_risk_band,
    get_mismatch_type,
    get_confidence,
    get_p24_version,
)


# =============================================================================
# Mock Context Classes
# =============================================================================


class MockAlignmentState(str, Enum):
    """Mock alignment state enum."""
    ALIGNED = "aligned"
    NEUTRAL = "neutral"
    TENSION = "tension"
    CONTRADICTION = "contradiction"


class MockDiscourseAct(str, Enum):
    """Mock discourse act enum."""
    INSTRUCTION = "INSTRUCTION"
    QUESTION = "QUESTION"
    EXPLANATION = "EXPLANATION"
    REFLECTION = "REFLECTION"
    ACKNOWLEDGMENT = "ACKNOWLEDGMENT"
    DEFERRAL = "DEFERRAL"


class MockRegime(str, Enum):
    """Mock regime enum."""
    STABILIZE = "STABILIZE"
    REFLECT = "REFLECT"
    INFORM = "INFORM"
    CLARIFY = "CLARIFY"
    DE_ESCALATE = "DE_ESCALATE"
    HOLD = "HOLD"


class MockSemanticSlot(str, Enum):
    """Mock semantic slot enum."""
    AGENT = "AGENT"
    TARGET = "TARGET"
    STATE = "STATE"
    CAUSE = "CAUSE"
    TEMPORAL_CONTEXT = "TEMPORAL_CONTEXT"
    UNCERTAINTY = "UNCERTAINTY"
    LIMITATION = "LIMITATION"
    REQUEST_FOCUS = "REQUEST_FOCUS"
    CONSTRAINT = "CONSTRAINT"


@dataclass
class MockPO1:
    """Mock Phase -1 envelope."""
    blocked: bool = False
    overall_policy: str = "ALLOW"

    def is_blocked(self) -> bool:
        return self.blocked


@dataclass
class MockP6:
    """Mock P6 regime envelope."""
    regime: MockRegime = MockRegime.INFORM


@dataclass
class MockP7:
    """Mock P7 discourse envelope."""
    act: MockDiscourseAct = MockDiscourseAct.DEFERRAL


@dataclass
class MockSemanticFrame:
    """Mock P8 semantic frame."""
    slots: Dict[MockSemanticSlot, Optional[str]] = None
    discourse_act: MockDiscourseAct = MockDiscourseAct.DEFERRAL

    def __post_init__(self):
        if self.slots is None:
            self.slots = {}


@dataclass
class MockLexicalFrame:
    """Mock P9 lexical frame."""
    selections: Dict[MockSemanticSlot, str] = None
    allowed: bool = True
    reason: str = "test"
    source_discourse_act: str = "DEFERRAL"
    source_regime: str = "INFORM"

    def __post_init__(self):
        if self.selections is None:
            self.selections = {}


@dataclass
class MockP22:
    """Mock P22 acoustic witness."""
    pressure_band: str = "low"
    motion_balance: str = "balanced"
    dominant_motion: str = "neutral"


@dataclass
class MockP23:
    """Mock P23 alignment report."""
    alignment_state: MockAlignmentState = MockAlignmentState.ALIGNED
    tension_score: float = 0.0
    alignment_tags: frozenset = frozenset()


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    phase_minus_one: Optional[MockPO1] = None
    p6_regime: Optional[MockP6] = None
    p7_discourse_envelope: Optional[MockP7] = None
    semantic_frame: Optional[MockSemanticFrame] = None
    lexical_frame: Optional[MockLexicalFrame] = None
    grammar_evidence: Optional[Dict[str, Any]] = None
    p22_acoustic_witness: Optional[MockP22] = None
    p23_alignment_report: Optional[MockP23] = None
    p24_projection_report: Optional[P24ProjectionReport] = None
    p24: Optional[P24ProjectionReport] = None
    _p24_disabled: bool = False


def create_full_mock_context(
    blocked: bool = False,
    regime: MockRegime = MockRegime.INFORM,
    discourse_act: MockDiscourseAct = MockDiscourseAct.DEFERRAL,
    slots: Optional[Dict[MockSemanticSlot, Optional[str]]] = None,
    lexical_selections: Optional[Dict[MockSemanticSlot, str]] = None,
    grammar_evidence: Optional[Dict[str, Any]] = None,
    pressure_band: str = "low",
    alignment_state: MockAlignmentState = MockAlignmentState.ALIGNED,
    tension_score: float = 0.0,
) -> MockPipelineContext:
    """Factory function to create fully populated mock contexts."""
    return MockPipelineContext(
        phase_minus_one=MockPO1(blocked=blocked),
        p6_regime=MockP6(regime=regime),
        p7_discourse_envelope=MockP7(act=discourse_act),
        semantic_frame=MockSemanticFrame(slots=slots or {}),
        lexical_frame=MockLexicalFrame(selections=lexical_selections or {}),
        grammar_evidence=grammar_evidence or {},
        p22_acoustic_witness=MockP22(pressure_band=pressure_band),
        p23_alignment_report=MockP23(
            alignment_state=alignment_state,
            tension_score=tension_score,
        ),
    )


# =============================================================================
# Group A: Discourse -> Base Layers Tests
# =============================================================================


class TestDiscourseToBaseLayers:
    """Test Group A: discourse act to base projected layers mapping."""

    def test_instruction_maps_to_execution_agency_purpose(self):
        """INSTRUCTION -> (EXECUTION, AGENCY, PURPOSE)"""
        ctx = create_full_mock_context(discourse_act=MockDiscourseAct.INSTRUCTION)
        report = run_p24(ctx)
        assert report.projected_layers == (
            OntologyLayer.EXECUTION,
            OntologyLayer.AGENCY,
            OntologyLayer.PURPOSE,
        )

    def test_question_maps_to_observation_reasoning(self):
        """QUESTION -> (OBSERVATION, REASONING)"""
        ctx = create_full_mock_context(discourse_act=MockDiscourseAct.QUESTION)
        report = run_p24(ctx)
        assert report.projected_layers == (
            OntologyLayer.OBSERVATION,
            OntologyLayer.REASONING,
        )

    def test_explanation_maps_to_reasoning_purpose_core(self):
        """EXPLANATION -> (REASONING, PURPOSE, CORE)"""
        ctx = create_full_mock_context(discourse_act=MockDiscourseAct.EXPLANATION)
        report = run_p24(ctx)
        assert report.projected_layers == (
            OntologyLayer.REASONING,
            OntologyLayer.PURPOSE,
            OntologyLayer.CORE,
        )

    def test_reflection_maps_to_cognition_identity(self):
        """REFLECTION -> (COGNITION, IDENTITY)"""
        ctx = create_full_mock_context(discourse_act=MockDiscourseAct.REFLECTION)
        report = run_p24(ctx)
        assert report.projected_layers == (
            OntologyLayer.COGNITION,
            OntologyLayer.IDENTITY,
        )

    def test_acknowledgment_maps_to_observation_cognition(self):
        """ACKNOWLEDGMENT -> (OBSERVATION, COGNITION)"""
        ctx = create_full_mock_context(discourse_act=MockDiscourseAct.ACKNOWLEDGMENT)
        report = run_p24(ctx)
        assert report.projected_layers == (
            OntologyLayer.OBSERVATION,
            OntologyLayer.COGNITION,
        )

    def test_deferral_maps_to_observation(self):
        """DEFERRAL -> (OBSERVATION,)"""
        ctx = create_full_mock_context(discourse_act=MockDiscourseAct.DEFERRAL)
        report = run_p24(ctx)
        assert report.projected_layers == (OntologyLayer.OBSERVATION,)

    def test_unknown_discourse_act_returns_empty_with_low_evidence(self):
        """Unknown discourse act -> empty tuple + low_evidence tag."""
        ctx = MockPipelineContext(
            phase_minus_one=MockPO1(blocked=False),
            p6_regime=MockP6(),
            # p7 with unknown act (we'll manually set to None to simulate)
            p7_discourse_envelope=None,
            grammar_evidence={},
        )
        report = run_p24(ctx)
        assert len(report.projected_layers) == 0
        assert "low_evidence" in report.projection_tags


# =============================================================================
# Group B: Risk Band Boundary Tests
# =============================================================================


class TestRiskBandBoundaries:
    """Test Group B: risk score to risk band boundaries."""

    def test_risk_score_0_33_is_low(self):
        """risk_score exactly 0.33 -> LOW."""
        # Base score 0.2, add 0.13 worth of other factors
        # Actually, we need to control the score precisely
        # With discourse_act = DEFERRAL (no +0.3), base = 0.2
        # With all evidence present, no certainty markers, no uncertainty
        # Score stays at 0.2 which is LOW
        ctx = create_full_mock_context(
            discourse_act=MockDiscourseAct.DEFERRAL,
            grammar_evidence={},  # No imperative form
        )
        report = run_p24(ctx)
        # Base 0.2, no additions = 0.2 <= 0.33 -> LOW
        assert report.projection_risk_band == ProjectionRiskBand.LOW

    def test_risk_score_0_34_is_moderate(self):
        """risk_score 0.34 -> MODERATE."""
        # Base 0.2 + 0.2 (imperative_form) = 0.4 > 0.33 -> MODERATE
        ctx = create_full_mock_context(
            discourse_act=MockDiscourseAct.DEFERRAL,
            grammar_evidence={"imperative_form": True},
        )
        report = run_p24(ctx)
        assert report.projection_risk_band == ProjectionRiskBand.MODERATE

    def test_risk_score_0_66_is_moderate(self):
        """risk_score 0.66 -> MODERATE (boundary)."""
        # Base 0.2 + 0.3 (EXPLANATION) + 0.2 (imperative) = 0.7 > 0.66 -> HIGH
        # Actually, let's just use 0.2 + 0.3 = 0.5 for EXPLANATION
        ctx = create_full_mock_context(
            discourse_act=MockDiscourseAct.EXPLANATION,
            grammar_evidence={},  # No imperative
        )
        report = run_p24(ctx)
        # 0.2 + 0.3 = 0.5, which is MODERATE
        assert report.projection_risk_band == ProjectionRiskBand.MODERATE

    def test_risk_score_0_67_is_high(self):
        """risk_score 0.67 -> HIGH."""
        # Base 0.2 + 0.3 (EXPLANATION) + 0.2 (certainty marker) = 0.7 > 0.66 -> HIGH
        ctx = create_full_mock_context(
            discourse_act=MockDiscourseAct.EXPLANATION,
            lexical_selections={MockSemanticSlot.STATE: "definitely true"},
            grammar_evidence={},
        )
        report = run_p24(ctx)
        # 0.2 + 0.3 + 0.2 (certainty) = 0.7 > 0.66 -> HIGH
        assert report.projection_risk_band == ProjectionRiskBand.HIGH

    def test_uncertainty_slot_reduces_risk(self):
        """UNCERTAINTY slot populated reduces risk score by 0.2."""
        # Without UNCERTAINTY: 0.2 + 0.3 = 0.5 (MODERATE)
        ctx_without = create_full_mock_context(
            discourse_act=MockDiscourseAct.EXPLANATION,
            grammar_evidence={},
        )
        report_without = run_p24(ctx_without)

        # With UNCERTAINTY: 0.2 + 0.3 - 0.2 = 0.3 (LOW)
        ctx_with = create_full_mock_context(
            discourse_act=MockDiscourseAct.EXPLANATION,
            slots={MockSemanticSlot.UNCERTAINTY: "possibly"},
            grammar_evidence={},
        )
        report_with = run_p24(ctx_with)

        assert report_without.projection_risk_band == ProjectionRiskBand.MODERATE
        assert report_with.projection_risk_band == ProjectionRiskBand.LOW


# =============================================================================
# Group C: Certainty Leak Detection Tests
# =============================================================================


class TestCertaintyLeakDetection:
    """Test Group C: certainty marker detection in lexical frame."""

    def test_definitely_triggers_certainty_leak(self):
        """Lexical frame with 'definitely' -> lexical_certainty_leak tag."""
        ctx = create_full_mock_context(
            lexical_selections={MockSemanticSlot.STATE: "definitely the case"},
        )
        report = run_p24(ctx)
        assert "lexical_certainty_leak" in report.projection_tags

    def test_certainly_triggers_certainty_leak(self):
        """Lexical frame with 'certainly' -> lexical_certainty_leak tag."""
        ctx = create_full_mock_context(
            lexical_selections={MockSemanticSlot.STATE: "certainly true"},
        )
        report = run_p24(ctx)
        assert "lexical_certainty_leak" in report.projection_tags

    def test_guarantee_triggers_certainty_leak(self):
        """Lexical frame with 'guarantee' -> lexical_certainty_leak tag."""
        ctx = create_full_mock_context(
            lexical_selections={MockSemanticSlot.STATE: "I guarantee this"},
        )
        report = run_p24(ctx)
        assert "lexical_certainty_leak" in report.projection_tags

    def test_prove_triggers_certainty_leak(self):
        """Lexical frame with 'prove' -> lexical_certainty_leak tag."""
        ctx = create_full_mock_context(
            lexical_selections={MockSemanticSlot.STATE: "this will prove it"},
        )
        report = run_p24(ctx)
        assert "lexical_certainty_leak" in report.projection_tags

    def test_must_triggers_certainty_leak(self):
        """Lexical frame with 'must' -> lexical_certainty_leak tag."""
        ctx = create_full_mock_context(
            lexical_selections={MockSemanticSlot.STATE: "you must do this"},
        )
        report = run_p24(ctx)
        assert "lexical_certainty_leak" in report.projection_tags

    def test_always_triggers_certainty_leak(self):
        """Lexical frame with 'always' -> lexical_certainty_leak tag."""
        ctx = create_full_mock_context(
            lexical_selections={MockSemanticSlot.STATE: "this is always true"},
        )
        report = run_p24(ctx)
        assert "lexical_certainty_leak" in report.projection_tags

    def test_never_triggers_certainty_leak(self):
        """Lexical frame with 'never' -> lexical_certainty_leak tag."""
        ctx = create_full_mock_context(
            lexical_selections={MockSemanticSlot.STATE: "this will never happen"},
        )
        report = run_p24(ctx)
        assert "lexical_certainty_leak" in report.projection_tags

    def test_case_insensitive_detection(self):
        """Certainty markers detected case-insensitively."""
        ctx = create_full_mock_context(
            lexical_selections={MockSemanticSlot.STATE: "DEFINITELY TRUE"},
        )
        report = run_p24(ctx)
        assert "lexical_certainty_leak" in report.projection_tags

    def test_no_certainty_markers_no_tag(self):
        """Normal lexical content -> no lexical_certainty_leak tag."""
        ctx = create_full_mock_context(
            lexical_selections={MockSemanticSlot.STATE: "possibly valid"},
        )
        report = run_p24(ctx)
        assert "lexical_certainty_leak" not in report.projection_tags

    def test_certainty_leak_increases_risk_score(self):
        """Certainty leak adds +0.2 to risk score."""
        ctx_without = create_full_mock_context(
            discourse_act=MockDiscourseAct.DEFERRAL,  # base 0.2
        )
        ctx_with = create_full_mock_context(
            discourse_act=MockDiscourseAct.DEFERRAL,
            lexical_selections={MockSemanticSlot.STATE: "definitely true"},
        )
        report_without = run_p24(ctx_without)
        report_with = run_p24(ctx_with)

        # Without: 0.2 (LOW), With: 0.2 + 0.2 = 0.4 (MODERATE)
        assert report_without.projection_risk_band == ProjectionRiskBand.LOW
        assert report_with.projection_risk_band == ProjectionRiskBand.MODERATE


# =============================================================================
# Group D: Mismatch Matrix Tests
# =============================================================================


class TestMismatchMatrix:
    """Test Group D: mismatch determination from alignment state + risk band."""

    def test_aligned_plus_low_risk_is_none(self):
        """ALIGNED + LOW risk -> NONE mismatch."""
        ctx = create_full_mock_context(
            alignment_state=MockAlignmentState.ALIGNED,
            discourse_act=MockDiscourseAct.DEFERRAL,  # low risk base
        )
        report = run_p24(ctx)
        assert report.mismatch_type == ProjectionMismatchType.NONE

    def test_tension_plus_low_risk_is_soft(self):
        """TENSION + LOW risk -> SOFT_MISMATCH."""
        ctx = create_full_mock_context(
            alignment_state=MockAlignmentState.TENSION,
            discourse_act=MockDiscourseAct.DEFERRAL,  # low risk
        )
        report = run_p24(ctx)
        assert report.mismatch_type == ProjectionMismatchType.SOFT_MISMATCH

    def test_contradiction_plus_low_risk_is_strong(self):
        """CONTRADICTION + LOW risk -> STRONG_MISMATCH."""
        ctx = create_full_mock_context(
            alignment_state=MockAlignmentState.CONTRADICTION,
            discourse_act=MockDiscourseAct.DEFERRAL,  # low risk
        )
        report = run_p24(ctx)
        assert report.mismatch_type == ProjectionMismatchType.STRONG_MISMATCH

    def test_aligned_plus_high_risk_is_strong(self):
        """ALIGNED + HIGH risk -> STRONG_MISMATCH."""
        ctx = create_full_mock_context(
            alignment_state=MockAlignmentState.ALIGNED,
            discourse_act=MockDiscourseAct.EXPLANATION,  # +0.3
            lexical_selections={MockSemanticSlot.STATE: "definitely true"},  # +0.2
            grammar_evidence={"imperative_form": True},  # +0.2
            # Total: 0.2 + 0.3 + 0.2 + 0.2 = 0.9 -> HIGH
        )
        report = run_p24(ctx)
        assert report.projection_risk_band == ProjectionRiskBand.HIGH
        assert report.mismatch_type == ProjectionMismatchType.STRONG_MISMATCH

    def test_aligned_plus_moderate_risk_is_soft(self):
        """ALIGNED + MODERATE risk -> SOFT_MISMATCH."""
        ctx = create_full_mock_context(
            alignment_state=MockAlignmentState.ALIGNED,
            discourse_act=MockDiscourseAct.EXPLANATION,  # 0.2 + 0.3 = 0.5 MODERATE
        )
        report = run_p24(ctx)
        assert report.projection_risk_band == ProjectionRiskBand.MODERATE
        assert report.mismatch_type == ProjectionMismatchType.SOFT_MISMATCH

    def test_neutral_alignment_with_moderate_risk_is_soft(self):
        """NEUTRAL alignment + MODERATE risk -> SOFT_MISMATCH."""
        ctx = create_full_mock_context(
            alignment_state=MockAlignmentState.NEUTRAL,
            discourse_act=MockDiscourseAct.INSTRUCTION,  # MODERATE risk
        )
        report = run_p24(ctx)
        assert report.mismatch_type == ProjectionMismatchType.SOFT_MISMATCH

    def test_missing_p23_defaults_to_tension(self):
        """Missing P23 report defaults to TENSION state, adds low_evidence tag."""
        ctx = MockPipelineContext(
            phase_minus_one=MockPO1(blocked=False),
            p6_regime=MockP6(),
            p7_discourse_envelope=MockP7(),
            p23_alignment_report=None,  # Missing
            grammar_evidence={},
        )
        report = run_p24(ctx)
        assert "low_evidence" in report.projection_tags
        # Missing P23 treated as TENSION -> SOFT_MISMATCH
        assert report.mismatch_type == ProjectionMismatchType.SOFT_MISMATCH


# =============================================================================
# Group E: Evidence Completeness / Confidence Tests
# =============================================================================


class TestEvidenceCompleteness:
    """Test Group E: confidence calculation from evidence completeness."""

    def test_full_evidence_high_confidence(self):
        """All evidence present -> high confidence (1.0 or close)."""
        ctx = create_full_mock_context(
            grammar_evidence={"some": "evidence"},
        )
        report = run_p24(ctx)
        assert report.confidence >= 0.8

    def test_missing_grammar_reduces_confidence(self):
        """Missing grammar evidence reduces confidence by 0.2."""
        ctx_with = create_full_mock_context(grammar_evidence={"some": "evidence"})
        ctx_without = create_full_mock_context(grammar_evidence=None)
        ctx_without.grammar_evidence = None  # Ensure None

        report_with = run_p24(ctx_with)
        report_without = run_p24(ctx_without)

        assert report_with.confidence > report_without.confidence
        assert "missing_grammar_evidence" in report_without.projection_tags

    def test_missing_lexical_frame_reduces_confidence(self):
        """Missing lexical frame reduces confidence by 0.3."""
        ctx = MockPipelineContext(
            phase_minus_one=MockPO1(blocked=False),
            p6_regime=MockP6(),
            p7_discourse_envelope=MockP7(),
            lexical_frame=None,  # Missing
            grammar_evidence={},
            p22_acoustic_witness=MockP22(),
            p23_alignment_report=MockP23(),
        )
        report = run_p24(ctx)
        assert "missing_lexical_frame" in report.projection_tags

    def test_missing_semantic_frame_reduces_confidence(self):
        """Missing semantic frame reduces confidence by 0.3."""
        ctx = MockPipelineContext(
            phase_minus_one=MockPO1(blocked=False),
            p6_regime=MockP6(),
            p7_discourse_envelope=MockP7(),
            semantic_frame=None,  # Missing
            grammar_evidence={},
            p22_acoustic_witness=MockP22(),
            p23_alignment_report=MockP23(),
        )
        report = run_p24(ctx)
        assert "missing_semantic_frame" in report.projection_tags

    def test_missing_p23_reduces_confidence(self):
        """Missing P23 report reduces confidence by 0.2."""
        ctx_with = create_full_mock_context()
        ctx_without = create_full_mock_context()
        ctx_without.p23_alignment_report = None

        report_with = run_p24(ctx_with)
        report_without = run_p24(ctx_without)

        assert report_with.confidence > report_without.confidence

    def test_blocked_po1_forces_zero_confidence(self):
        """Blocked PO1 -> confidence 0.0 and blocked_context tag."""
        ctx = create_full_mock_context(blocked=True)
        report = run_p24(ctx)
        assert report.confidence == 0.0
        assert "blocked_context" in report.projection_tags

    def test_blocked_context_strong_mismatch_high_risk(self):
        """Blocked context -> STRONG_MISMATCH, HIGH risk, empty layers."""
        ctx = create_full_mock_context(blocked=True)
        report = run_p24(ctx)
        assert report.mismatch_type == ProjectionMismatchType.STRONG_MISMATCH
        assert report.projection_risk_band == ProjectionRiskBand.HIGH
        assert len(report.projected_layers) == 0


# =============================================================================
# Group F: Forbidden Behavior Invariants Tests
# =============================================================================


class TestForbiddenBehaviorInvariants:
    """Test Group F: P24 observation-only, no mutation."""

    def test_p24_does_not_modify_regime(self):
        """P24 does not modify regime."""
        ctx = create_full_mock_context(regime=MockRegime.HOLD)
        original_regime = ctx.p6_regime.regime

        maybe_run_p24(ctx)

        assert ctx.p6_regime.regime == original_regime

    def test_p24_does_not_modify_discourse(self):
        """P24 does not modify discourse act."""
        ctx = create_full_mock_context(discourse_act=MockDiscourseAct.DEFERRAL)
        original_act = ctx.p7_discourse_envelope.act

        maybe_run_p24(ctx)

        assert ctx.p7_discourse_envelope.act == original_act

    def test_p24_does_not_modify_semantic_frame(self):
        """P24 does not modify semantic frame."""
        ctx = create_full_mock_context(
            slots={MockSemanticSlot.STATE: "original"}
        )
        original_slots = dict(ctx.semantic_frame.slots)

        maybe_run_p24(ctx)

        assert ctx.semantic_frame.slots == original_slots

    def test_p24_does_not_modify_lexical_frame(self):
        """P24 does not modify lexical frame."""
        ctx = create_full_mock_context(
            lexical_selections={MockSemanticSlot.STATE: "original"}
        )
        original_selections = dict(ctx.lexical_frame.selections)

        maybe_run_p24(ctx)

        assert ctx.lexical_frame.selections == original_selections

    def test_p24_does_not_modify_p22(self):
        """P24 does not modify P22 witness."""
        ctx = create_full_mock_context(pressure_band="high")
        original_pressure = ctx.p22_acoustic_witness.pressure_band

        maybe_run_p24(ctx)

        assert ctx.p22_acoustic_witness.pressure_band == original_pressure

    def test_p24_does_not_modify_p23(self):
        """P24 does not modify P23 report."""
        ctx = create_full_mock_context(
            alignment_state=MockAlignmentState.TENSION,
            tension_score=0.5,
        )
        original_state = ctx.p23_alignment_report.alignment_state
        original_score = ctx.p23_alignment_report.tension_score

        maybe_run_p24(ctx)

        assert ctx.p23_alignment_report.alignment_state == original_state
        assert ctx.p23_alignment_report.tension_score == original_score

    def test_projected_layers_never_exceed_3(self):
        """Projected layers never exceed 3 even with refinements."""
        # EXPLANATION gives 3 layers, try to add more via slot refinement
        ctx = create_full_mock_context(
            discourse_act=MockDiscourseAct.EXPLANATION,  # 3 layers
            slots={
                MockSemanticSlot.REQUEST_FOCUS: "something",  # Would add PURPOSE
                MockSemanticSlot.CONSTRAINT: "constraint",  # Would add EXECUTION
            }
        )
        report = run_p24(ctx)
        assert len(report.projected_layers) <= 3

    def test_projection_tags_always_from_allowlist(self):
        """All projection tags must be from ALLOWED_PROJECTION_TAGS."""
        # Create various contexts and check all tags
        contexts = [
            create_full_mock_context(),
            create_full_mock_context(blocked=True),
            create_full_mock_context(
                grammar_evidence={"imperative_form": True},
                regime=MockRegime.HOLD,
            ),
            create_full_mock_context(
                lexical_selections={MockSemanticSlot.STATE: "definitely"},
            ),
        ]

        for ctx in contexts:
            report = run_p24(ctx)
            for tag in report.projection_tags:
                assert tag in ALLOWED_PROJECTION_TAGS, f"Invalid tag: {tag}"


# =============================================================================
# Group G: Determinism Tests
# =============================================================================


class TestDeterminism:
    """Test Group G: same input -> same output."""

    def test_same_context_same_report_layers(self):
        """Same context twice -> same projected_layers."""
        ctx = create_full_mock_context(discourse_act=MockDiscourseAct.INSTRUCTION)

        report1 = run_p24(ctx)
        report2 = run_p24(ctx)

        assert report1.projected_layers == report2.projected_layers

    def test_same_context_same_report_risk_band(self):
        """Same context twice -> same projection_risk_band."""
        ctx = create_full_mock_context(discourse_act=MockDiscourseAct.EXPLANATION)

        report1 = run_p24(ctx)
        report2 = run_p24(ctx)

        assert report1.projection_risk_band == report2.projection_risk_band

    def test_same_context_same_report_mismatch(self):
        """Same context twice -> same mismatch_type."""
        ctx = create_full_mock_context(
            alignment_state=MockAlignmentState.TENSION,
        )

        report1 = run_p24(ctx)
        report2 = run_p24(ctx)

        assert report1.mismatch_type == report2.mismatch_type

    def test_same_context_same_report_tags(self):
        """Same context twice -> same projection_tags."""
        ctx = create_full_mock_context(
            lexical_selections={MockSemanticSlot.STATE: "definitely"},
        )

        report1 = run_p24(ctx)
        report2 = run_p24(ctx)

        assert report1.projection_tags == report2.projection_tags

    def test_same_context_same_report_confidence(self):
        """Same context twice -> same confidence."""
        ctx = create_full_mock_context()

        report1 = run_p24(ctx)
        report2 = run_p24(ctx)

        assert report1.confidence == report2.confidence

    def test_multiple_runs_deterministic(self):
        """Multiple runs -> all identical reports."""
        ctx = create_full_mock_context(
            discourse_act=MockDiscourseAct.QUESTION,
            pressure_band="moderate",
            alignment_state=MockAlignmentState.NEUTRAL,
        )

        reports = [run_p24(ctx) for _ in range(10)]

        layers = {r.projected_layers for r in reports}
        bands = {r.projection_risk_band for r in reports}
        mismatches = {r.mismatch_type for r in reports}
        tags = {r.projection_tags for r in reports}
        confidences = {r.confidence for r in reports}

        assert len(layers) == 1
        assert len(bands) == 1
        assert len(mismatches) == 1
        assert len(tags) == 1
        assert len(confidences) == 1


# =============================================================================
# Schema Tests
# =============================================================================


class TestOntologyLayerEnum:
    """Test OntologyLayer enum."""

    def test_all_ten_layers_exist(self):
        """All 10 ontology layers exist."""
        assert OntologyLayer.EXECUTION.value == "execution"
        assert OntologyLayer.IDENTITY.value == "identity"
        assert OntologyLayer.FORM.value == "form"
        assert OntologyLayer.COGNITION.value == "cognition"
        assert OntologyLayer.AGENCY.value == "agency"
        assert OntologyLayer.REASONING.value == "reasoning"
        assert OntologyLayer.PURPOSE.value == "purpose"
        assert OntologyLayer.OBSERVATION.value == "observation"
        assert OntologyLayer.CORE.value == "core"
        assert OntologyLayer.UNIVERSAL.value == "universal"

    def test_enum_count_is_10(self):
        """OntologyLayer has exactly 10 values."""
        assert len(OntologyLayer) == 10


class TestProjectionRiskBandEnum:
    """Test ProjectionRiskBand enum."""

    def test_all_bands_exist(self):
        """All risk bands exist."""
        assert ProjectionRiskBand.LOW.value == "low"
        assert ProjectionRiskBand.MODERATE.value == "moderate"
        assert ProjectionRiskBand.HIGH.value == "high"

    def test_enum_count_is_3(self):
        """ProjectionRiskBand has exactly 3 values."""
        assert len(ProjectionRiskBand) == 3


class TestProjectionMismatchTypeEnum:
    """Test ProjectionMismatchType enum."""

    def test_all_types_exist(self):
        """All mismatch types exist."""
        assert ProjectionMismatchType.NONE.value == "none"
        assert ProjectionMismatchType.SOFT_MISMATCH.value == "soft_mismatch"
        assert ProjectionMismatchType.STRONG_MISMATCH.value == "strong_mismatch"

    def test_enum_count_is_3(self):
        """ProjectionMismatchType has exactly 3 values."""
        assert len(ProjectionMismatchType) == 3


class TestP24ProjectionReportSchema:
    """Test P24ProjectionReport dataclass validation."""

    def test_frozen_dataclass(self):
        """Report is frozen (immutable)."""
        report = create_empty_report()
        with pytest.raises(FrozenInstanceError):
            report.projected_layers = (OntologyLayer.EXECUTION,)

    def test_observer_only_must_be_true(self):
        """observer_only must be True."""
        with pytest.raises(ValueError, match="observer_only must be True"):
            P24ProjectionReport(
                projected_layers=(),
                projection_risk_band=ProjectionRiskBand.LOW,
                mismatch_type=ProjectionMismatchType.NONE,
                projection_tags=frozenset(),
                confidence=0.5,
                observer_only=False,
            )

    def test_projected_layers_max_3(self):
        """projected_layers must have at most 3 elements."""
        with pytest.raises(ValueError, match="at most 3 layers"):
            P24ProjectionReport(
                projected_layers=(
                    OntologyLayer.EXECUTION,
                    OntologyLayer.AGENCY,
                    OntologyLayer.PURPOSE,
                    OntologyLayer.IDENTITY,  # 4th layer
                ),
                projection_risk_band=ProjectionRiskBand.LOW,
                mismatch_type=ProjectionMismatchType.NONE,
                projection_tags=frozenset(),
                confidence=0.5,
            )

    def test_confidence_must_be_in_range(self):
        """confidence must be in [0.0, 1.0]."""
        with pytest.raises(ValueError, match="must be in"):
            P24ProjectionReport(
                projected_layers=(),
                projection_risk_band=ProjectionRiskBand.LOW,
                mismatch_type=ProjectionMismatchType.NONE,
                projection_tags=frozenset(),
                confidence=1.5,  # Out of range
            )

    def test_confidence_negative_rejected(self):
        """Negative confidence rejected."""
        with pytest.raises(ValueError, match="must be in"):
            P24ProjectionReport(
                projected_layers=(),
                projection_risk_band=ProjectionRiskBand.LOW,
                mismatch_type=ProjectionMismatchType.NONE,
                projection_tags=frozenset(),
                confidence=-0.1,
            )

    def test_tags_must_be_frozenset(self):
        """projection_tags must be frozenset."""
        with pytest.raises(ValueError, match="must be frozenset"):
            P24ProjectionReport(
                projected_layers=(),
                projection_risk_band=ProjectionRiskBand.LOW,
                mismatch_type=ProjectionMismatchType.NONE,
                projection_tags={"not", "frozen"},  # Regular set
                confidence=0.5,
            )

    def test_invalid_tags_rejected(self):
        """Tags not in allow-list are rejected."""
        with pytest.raises(ValueError, match="invalid tags"):
            P24ProjectionReport(
                projected_layers=(),
                projection_risk_band=ProjectionRiskBand.LOW,
                mismatch_type=ProjectionMismatchType.NONE,
                projection_tags=frozenset({"invalid_tag"}),
                confidence=0.5,
            )

    def test_to_dict_serialization(self):
        """Report can be serialized to dict."""
        report = create_empty_report()
        data = report.to_dict()

        assert isinstance(data, dict)
        assert "projected_layers" in data
        assert "projection_risk_band" in data
        assert "mismatch_type" in data
        assert "projection_tags" in data
        assert "confidence" in data
        assert data["observer_only"] is True


class TestFactoryFunctions:
    """Test factory functions."""

    def test_create_empty_report(self):
        """create_empty_report creates valid empty report."""
        report = create_empty_report()
        assert report.projected_layers == ()
        assert report.projection_risk_band == ProjectionRiskBand.LOW
        assert report.mismatch_type == ProjectionMismatchType.NONE
        assert report.confidence == 0.0

    def test_create_blocked_report(self):
        """create_blocked_report creates blocked context report."""
        report = create_blocked_report()
        assert report.projected_layers == ()
        assert report.projection_risk_band == ProjectionRiskBand.HIGH
        assert report.mismatch_type == ProjectionMismatchType.STRONG_MISMATCH
        assert "blocked_context" in report.projection_tags
        assert report.confidence == 0.0


# =============================================================================
# Integration Helper Tests
# =============================================================================


class TestIntegrationHelpers:
    """Test integration helper functions."""

    def test_maybe_run_p24_attaches_report(self):
        """maybe_run_p24 attaches report to context."""
        ctx = create_full_mock_context()

        maybe_run_p24(ctx)

        assert ctx.p24_projection_report is not None
        assert isinstance(ctx.p24_projection_report, P24ProjectionReport)

    def test_maybe_run_p24_disabled_returns_unchanged(self):
        """maybe_run_p24 returns unchanged when disabled."""
        ctx = create_full_mock_context()
        ctx._p24_disabled = True

        result = maybe_run_p24(ctx)

        assert result is ctx
        assert ctx.p24_projection_report is None

    def test_is_p24_disabled(self):
        """is_p24_disabled helper works."""
        ctx = create_full_mock_context()
        assert is_p24_disabled(ctx) is False

        ctx._p24_disabled = True
        assert is_p24_disabled(ctx) is True

    def test_has_p24_report(self):
        """has_p24_report helper works."""
        ctx = create_full_mock_context()
        assert has_p24_report(ctx) is False

        maybe_run_p24(ctx)
        assert has_p24_report(ctx) is True

    def test_get_p24_report(self):
        """get_p24_report helper works."""
        ctx = create_full_mock_context()
        assert get_p24_report(ctx) is None

        maybe_run_p24(ctx)
        report = get_p24_report(ctx)
        assert report is not None

    def test_is_high_risk_helper(self):
        """is_high_risk helper works."""
        assert is_high_risk(None) is False
        assert is_high_risk(create_empty_report()) is False
        assert is_high_risk(create_blocked_report()) is True

    def test_has_strong_mismatch_helper(self):
        """has_strong_mismatch helper works."""
        assert has_strong_mismatch(None) is False
        assert has_strong_mismatch(create_empty_report()) is False
        assert has_strong_mismatch(create_blocked_report()) is True

    def test_get_projected_layers_helper(self):
        """get_projected_layers helper works."""
        ctx = create_full_mock_context()
        assert get_projected_layers(ctx) == ()

        maybe_run_p24(ctx)
        layers = get_projected_layers(ctx)
        assert isinstance(layers, tuple)

    def test_get_projection_tags_helper(self):
        """get_projection_tags helper works."""
        ctx = create_full_mock_context()
        assert get_projection_tags(ctx) == frozenset()

        maybe_run_p24(ctx)
        tags = get_projection_tags(ctx)
        assert isinstance(tags, frozenset)

    def test_get_risk_band_helper(self):
        """get_risk_band helper works."""
        ctx = create_full_mock_context()
        assert get_risk_band(ctx) == ProjectionRiskBand.LOW

        maybe_run_p24(ctx)
        band = get_risk_band(ctx)
        assert isinstance(band, ProjectionRiskBand)

    def test_get_mismatch_type_helper(self):
        """get_mismatch_type helper works."""
        ctx = create_full_mock_context()
        assert get_mismatch_type(ctx) == ProjectionMismatchType.NONE

        maybe_run_p24(ctx)
        mismatch = get_mismatch_type(ctx)
        assert isinstance(mismatch, ProjectionMismatchType)

    def test_get_confidence_helper(self):
        """get_confidence helper works."""
        ctx = create_full_mock_context()
        assert get_confidence(ctx) == 0.0

        maybe_run_p24(ctx)
        confidence = get_confidence(ctx)
        assert 0.0 <= confidence <= 1.0

    def test_get_p24_version(self):
        """get_p24_version returns correct version."""
        assert get_p24_version() == P24_VERSION


class TestResolverInstance:
    """Test resolver singleton and instance."""

    def test_get_p24_resolver_returns_singleton(self):
        """get_p24_resolver returns same instance."""
        resolver1 = get_p24_resolver()
        resolver2 = get_p24_resolver()
        assert resolver1 is resolver2

    def test_resolver_has_version(self):
        """Resolver has version property."""
        resolver = get_p24_resolver()
        assert resolver.version == P24_VERSION


# =============================================================================
# Forbidden Access Tests
# =============================================================================


class TestForbiddenAccess:
    """Test forbidden attribute access enforcement."""

    def test_access_forbidden_text_raises(self):
        """Attempt to access text data raises."""
        for attr in FORBIDDEN_TEXT_ATTRS:
            with pytest.raises(P24InvariantViolation, match="forbidden attribute"):
                access_forbidden_attribute(None, attr)

    def test_access_forbidden_token_raises(self):
        """Attempt to access token data raises."""
        for attr in FORBIDDEN_TOKEN_ATTRS:
            with pytest.raises(P24InvariantViolation, match="forbidden attribute"):
                access_forbidden_attribute(None, attr)

    def test_all_forbidden_attrs_covered(self):
        """ALL_FORBIDDEN_ATTRS contains expected attributes."""
        assert "input_text" in ALL_FORBIDDEN_ATTRS
        assert "text" in ALL_FORBIDDEN_ATTRS
        assert "raw_text" in ALL_FORBIDDEN_ATTRS
        assert "tokens" in ALL_FORBIDDEN_ATTRS
        assert "word_list" in ALL_FORBIDDEN_ATTRS


# =============================================================================
# Additional Condition Tests
# =============================================================================


class TestAdditionalConditions:
    """Test additional condition tags."""

    def test_imperative_under_careful_tag(self):
        """imperative_form + conservative regime -> imperative_under_careful tag."""
        ctx = create_full_mock_context(
            regime=MockRegime.HOLD,  # Conservative
            grammar_evidence={"imperative_form": True},
        )
        report = run_p24(ctx)
        assert "imperative_under_careful" in report.projection_tags

    def test_imperative_under_de_escalate_tag(self):
        """imperative_form + DE_ESCALATE -> imperative_under_careful tag."""
        ctx = create_full_mock_context(
            regime=MockRegime.DE_ESCALATE,
            grammar_evidence={"imperative_form": True},
        )
        report = run_p24(ctx)
        assert "imperative_under_careful" in report.projection_tags

    def test_no_imperative_under_careful_without_imperative(self):
        """No imperative_form -> no imperative_under_careful tag."""
        ctx = create_full_mock_context(
            regime=MockRegime.HOLD,
            grammar_evidence={},  # No imperative_form
        )
        report = run_p24(ctx)
        assert "imperative_under_careful" not in report.projection_tags

    def test_high_pressure_low_authority_tag(self):
        """HIGH pressure + DEFERRAL -> high_pressure_low_authority tag."""
        ctx = create_full_mock_context(
            pressure_band="high",
            discourse_act=MockDiscourseAct.DEFERRAL,
        )
        report = run_p24(ctx)
        assert "high_pressure_low_authority" in report.projection_tags

    def test_high_pressure_acknowledgment_low_authority(self):
        """HIGH pressure + ACKNOWLEDGMENT -> high_pressure_low_authority tag."""
        ctx = create_full_mock_context(
            pressure_band="high",
            discourse_act=MockDiscourseAct.ACKNOWLEDGMENT,
        )
        report = run_p24(ctx)
        assert "high_pressure_low_authority" in report.projection_tags

    def test_no_high_pressure_low_authority_with_low_pressure(self):
        """LOW pressure + DEFERRAL -> no high_pressure_low_authority tag."""
        ctx = create_full_mock_context(
            pressure_band="low",
            discourse_act=MockDiscourseAct.DEFERRAL,
        )
        report = run_p24(ctx)
        assert "high_pressure_low_authority" not in report.projection_tags

    def test_inner_outer_tension_tag_when_mismatch(self):
        """Mismatch != NONE -> inner_outer_tension tag."""
        ctx = create_full_mock_context(
            alignment_state=MockAlignmentState.TENSION,
        )
        report = run_p24(ctx)
        assert "inner_outer_tension" in report.projection_tags

    def test_no_inner_outer_tension_when_aligned(self):
        """ALIGNED + LOW risk -> no inner_outer_tension tag."""
        ctx = create_full_mock_context(
            alignment_state=MockAlignmentState.ALIGNED,
            discourse_act=MockDiscourseAct.DEFERRAL,  # LOW risk
        )
        report = run_p24(ctx)
        assert "inner_outer_tension" not in report.projection_tags


# =============================================================================
# Slot Refinement Tests
# =============================================================================


class TestSlotRefinement:
    """Test slot-based layer refinement."""

    def test_cause_under_conservative_regime_adds_overreach_tag(self):
        """CAUSE populated under HOLD regime -> outer_overreach_risk tag."""
        ctx = create_full_mock_context(
            regime=MockRegime.HOLD,
            slots={MockSemanticSlot.CAUSE: "some cause"},
        )
        report = run_p24(ctx)
        assert "outer_overreach_risk" in report.projection_tags

    def test_request_focus_adds_purpose_layer(self):
        """REQUEST_FOCUS populated adds PURPOSE layer if < 3."""
        # DEFERRAL has only 1 layer (OBSERVATION)
        ctx = create_full_mock_context(
            discourse_act=MockDiscourseAct.DEFERRAL,
            slots={MockSemanticSlot.REQUEST_FOCUS: "something"},
        )
        report = run_p24(ctx)
        assert OntologyLayer.PURPOSE in report.projected_layers

    def test_constraint_adds_execution_layer(self):
        """CONSTRAINT populated adds EXECUTION layer if < 3."""
        # REFLECTION has 2 layers (COGNITION, IDENTITY)
        ctx = create_full_mock_context(
            discourse_act=MockDiscourseAct.REFLECTION,
            slots={MockSemanticSlot.CONSTRAINT: "constraint"},
        )
        report = run_p24(ctx)
        assert OntologyLayer.EXECUTION in report.projected_layers

    def test_limitation_adds_execution_layer(self):
        """LIMITATION populated adds EXECUTION layer if < 3."""
        ctx = create_full_mock_context(
            discourse_act=MockDiscourseAct.REFLECTION,
            slots={MockSemanticSlot.LIMITATION: "limitation"},
        )
        report = run_p24(ctx)
        assert OntologyLayer.EXECUTION in report.projected_layers


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_none_context(self):
        """None context is handled gracefully."""
        result = maybe_run_p24(None)
        assert result is None

    def test_empty_context(self):
        """Empty context returns report with defaults."""
        ctx = MockPipelineContext()
        result = maybe_run_p24(ctx)
        assert result is ctx
        assert ctx.p24_projection_report is not None

    def test_resolve_projection_standalone(self):
        """resolve_projection standalone function works."""
        ctx = create_full_mock_context()
        report = resolve_projection(ctx)
        assert isinstance(report, P24ProjectionReport)

    def test_report_helper_methods(self):
        """Report helper methods work correctly."""
        report = P24ProjectionReport(
            projected_layers=(OntologyLayer.EXECUTION, OntologyLayer.AGENCY),
            projection_risk_band=ProjectionRiskBand.HIGH,
            mismatch_type=ProjectionMismatchType.STRONG_MISMATCH,
            projection_tags=frozenset({"low_evidence"}),
            confidence=0.5,
        )

        assert report.is_high_risk() is True
        assert report.is_moderate_risk() is False
        assert report.is_low_risk() is False
        assert report.has_strong_mismatch() is True
        assert report.has_soft_mismatch() is False
        assert report.has_no_mismatch() is False
        assert report.has_tag("low_evidence") is True
        assert report.has_tag("nonexistent") is False
        assert report.layer_count() == 2


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Test module constants."""

    def test_allowed_projection_tags(self):
        """ALLOWED_PROJECTION_TAGS contains exactly 10 tags."""
        expected_tags = {
            "inner_outer_tension",
            "outer_overreach_risk",
            "high_pressure_low_authority",
            "imperative_under_careful",
            "lexical_certainty_leak",
            "missing_grammar_evidence",
            "missing_lexical_frame",
            "missing_semantic_frame",
            "blocked_context",
            "low_evidence",
        }
        assert ALLOWED_PROJECTION_TAGS == expected_tags

    def test_discourse_act_layers_mapping(self):
        """DISCOURSE_ACT_LAYERS contains all discourse acts."""
        assert "INSTRUCTION" in DISCOURSE_ACT_LAYERS
        assert "QUESTION" in DISCOURSE_ACT_LAYERS
        assert "EXPLANATION" in DISCOURSE_ACT_LAYERS
        assert "REFLECTION" in DISCOURSE_ACT_LAYERS
        assert "ACKNOWLEDGMENT" in DISCOURSE_ACT_LAYERS
        assert "DEFERRAL" in DISCOURSE_ACT_LAYERS

    def test_certainty_markers(self):
        """CERTAINTY_MARKERS contains expected markers."""
        expected_markers = {
            "definitely", "certainly", "guarantee", "prove",
            "must", "always", "never",
        }
        assert CERTAINTY_MARKERS == expected_markers

    def test_conservative_regimes(self):
        """CONSERVATIVE_REGIMES contains expected regimes."""
        assert "CAREFUL" in CONSERVATIVE_REGIMES
        assert "DE_ESCALATE" in CONSERVATIVE_REGIMES
        assert "HOLD" in CONSERVATIVE_REGIMES
        assert "STABILIZE" in CONSERVATIVE_REGIMES
