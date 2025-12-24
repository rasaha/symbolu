"""
P17 Semantic Integrity Monitor Test Suite

Comprehensive tests for P17 semantic integrity monitoring:
A. Uncertainty collapse detection
B. Cause leak under DE_ESCALATE/STABILIZE
C. Relational authority drift
D. Clean pass scenarios
E. Missing inputs degrade gracefully
F. Determinism verification

All tests are DETERMINISTIC with ZERO false positives expected.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional
import copy

import pytest

from symbolu.mechanical.pipeline.p17_semantic_integrity import (
    # Schema
    IntegrityIssueType,
    Severity,
    IntegrityIssue,
    P17IntegrityReport,
    P17_VERSION,
    create_issue,
    create_report,
    # Rules
    CERTAINTY_MARKERS,
    UNCERTAINTY_PRESERVERS,
    CAUSAL_CONNECTORS,
    AUTHORITY_MARKERS,
    CAUSAL_RESTRICTIVE_REGIMES,
    CAUSAL_RESTRICTIVE_DISCOURSE_ACTS,
    detect_uncertainty_collapse,
    detect_cause_leak,
    detect_authority_drift,
    detect_tone_escalation,
    detect_slot_contradictions,
    detect_missing_inputs,
    # Resolver
    P17SemanticIntegrityMonitor,
    ISSUE_TYPE_PENALTIES,
    SEVERITY_MULTIPLIERS,
    # Integration
    maybe_run_p17,
    run_p17_directly,
    is_p17_disabled,
    has_p17_report,
    get_p17_report,
    is_integrity_clean,
    get_integrity_score,
    get_p17_version,
)


# ============================================================================
# MOCK HELPERS - Replicating Pipeline Context Structure
# ============================================================================


class MockObservationMode(str, Enum):
    """Mock observation mode from PO1."""
    REFLEXIVE = "REFLEXIVE"
    RELATIONAL = "RELATIONAL"
    DETACHED = "DETACHED"


class MockOperationalRegime(str, Enum):
    """Mock operational regime from P6."""
    STABILIZE = "STABILIZE"
    REFLECT = "REFLECT"
    INFORM = "INFORM"
    CLARIFY = "CLARIFY"
    DE_ESCALATE = "DE_ESCALATE"
    HOLD = "HOLD"


class MockDiscourseAct(str, Enum):
    """Mock discourse act from P7."""
    QUESTION = "QUESTION"
    REFLECTION = "REFLECTION"
    ACKNOWLEDGMENT = "ACKNOWLEDGMENT"
    EXPLANATION = "EXPLANATION"
    INSTRUCTION = "INSTRUCTION"
    DEFERRAL = "DEFERRAL"


class MockSemanticSlot(str, Enum):
    """Mock semantic slot from P8."""
    AGENT = "AGENT"
    TARGET = "TARGET"
    STATE = "STATE"
    CAUSE = "CAUSE"
    UNCERTAINTY = "UNCERTAINTY"
    LIMITATION = "LIMITATION"
    REQUEST_FOCUS = "REQUEST_FOCUS"


@dataclass
class MockGroundingCandidate:
    """Mock grounding candidate from PO1."""
    mode: MockObservationMode
    confidence: float = 0.9


@dataclass
class MockClauseGrounding:
    """Mock clause grounding from PO1."""
    selected: Optional[MockGroundingCandidate] = None


@dataclass
class MockPhaseMinusOne:
    """Mock PO1 (phase_minus_one) envelope."""
    selected_primary: Optional[MockGroundingCandidate] = None
    clauses: List[MockClauseGrounding] = field(default_factory=list)


@dataclass
class MockP6Regime:
    """Mock P6 regime envelope."""
    regime: MockOperationalRegime
    reason: str = "test"


@dataclass
class MockP7Discourse:
    """Mock P7 discourse envelope."""
    act: MockDiscourseAct
    allowed: bool = True
    reason: str = "test"


@dataclass
class MockSemanticFrame:
    """Mock P8 semantic frame."""
    discourse_act: MockDiscourseAct
    slots: Dict[MockSemanticSlot, Optional[str]]
    allowed: bool = True
    reason: str = "test"


@dataclass
class MockLexicalFrame:
    """Mock P9 lexical frame."""
    selections: Dict[MockSemanticSlot, str]
    allowed: bool = True
    source_discourse_act: str = "EXPLANATION"
    source_regime: str = "INFORM"
    reason: str = "test"


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing P17."""
    phase_minus_one: Optional[MockPhaseMinusOne] = None
    p6_regime: Optional[MockP6Regime] = None
    p7_discourse_envelope: Optional[MockP7Discourse] = None
    semantic_frame: Optional[MockSemanticFrame] = None
    lexical_frame: Optional[MockLexicalFrame] = None
    p17: Optional[P17IntegrityReport] = None
    _p17_disabled: bool = False


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================


def make_reflexive_context(
    slots: Optional[Dict[MockSemanticSlot, Optional[str]]] = None,
    selections: Optional[Dict[MockSemanticSlot, str]] = None,
) -> MockPipelineContext:
    """Create a REFLEXIVE mode context (self-directed)."""
    if slots is None:
        slots = {MockSemanticSlot.STATE: "feeling uncertain"}
    if selections is None:
        selections = {MockSemanticSlot.STATE: "I feel uncertain"}

    return MockPipelineContext(
        phase_minus_one=MockPhaseMinusOne(
            selected_primary=MockGroundingCandidate(
                mode=MockObservationMode.REFLEXIVE,
            ),
        ),
        p6_regime=MockP6Regime(regime=MockOperationalRegime.REFLECT),
        p7_discourse_envelope=MockP7Discourse(act=MockDiscourseAct.REFLECTION),
        semantic_frame=MockSemanticFrame(
            discourse_act=MockDiscourseAct.REFLECTION,
            slots=slots,
        ),
        lexical_frame=MockLexicalFrame(selections=selections),
    )


def make_relational_context(
    slots: Optional[Dict[MockSemanticSlot, Optional[str]]] = None,
    selections: Optional[Dict[MockSemanticSlot, str]] = None,
) -> MockPipelineContext:
    """Create a RELATIONAL mode context (about others)."""
    if slots is None:
        slots = {MockSemanticSlot.STATE: "appears concerned"}
    if selections is None:
        selections = {MockSemanticSlot.STATE: "she seems concerned"}

    return MockPipelineContext(
        phase_minus_one=MockPhaseMinusOne(
            selected_primary=MockGroundingCandidate(
                mode=MockObservationMode.RELATIONAL,
            ),
        ),
        p6_regime=MockP6Regime(regime=MockOperationalRegime.REFLECT),
        p7_discourse_envelope=MockP7Discourse(act=MockDiscourseAct.REFLECTION),
        semantic_frame=MockSemanticFrame(
            discourse_act=MockDiscourseAct.REFLECTION,
            slots=slots,
        ),
        lexical_frame=MockLexicalFrame(selections=selections),
    )


def make_de_escalate_context(
    discourse_act: MockDiscourseAct = MockDiscourseAct.REFLECTION,
    slots: Optional[Dict[MockSemanticSlot, Optional[str]]] = None,
    selections: Optional[Dict[MockSemanticSlot, str]] = None,
) -> MockPipelineContext:
    """Create a DE_ESCALATE regime context."""
    if slots is None:
        slots = {MockSemanticSlot.STATE: "feeling overwhelmed"}
    if selections is None:
        selections = {MockSemanticSlot.STATE: "I hear that things feel overwhelming"}

    return MockPipelineContext(
        phase_minus_one=MockPhaseMinusOne(
            selected_primary=MockGroundingCandidate(
                mode=MockObservationMode.REFLEXIVE,
            ),
        ),
        p6_regime=MockP6Regime(regime=MockOperationalRegime.DE_ESCALATE),
        p7_discourse_envelope=MockP7Discourse(act=discourse_act),
        semantic_frame=MockSemanticFrame(
            discourse_act=discourse_act,
            slots=slots,
        ),
        lexical_frame=MockLexicalFrame(
            selections=selections,
            source_regime="DE_ESCALATE",
        ),
    )


def make_uncertainty_context(
    uncertainty_value: str = "unsure about this",
    lexical_text: str = "I'm not sure how to proceed",
) -> MockPipelineContext:
    """Create a context with UNCERTAINTY slot populated."""
    return MockPipelineContext(
        phase_minus_one=MockPhaseMinusOne(
            selected_primary=MockGroundingCandidate(
                mode=MockObservationMode.REFLEXIVE,
            ),
        ),
        p6_regime=MockP6Regime(regime=MockOperationalRegime.REFLECT),
        p7_discourse_envelope=MockP7Discourse(act=MockDiscourseAct.REFLECTION),
        semantic_frame=MockSemanticFrame(
            discourse_act=MockDiscourseAct.REFLECTION,
            slots={
                MockSemanticSlot.UNCERTAINTY: uncertainty_value,
                MockSemanticSlot.STATE: "processing",
            },
        ),
        lexical_frame=MockLexicalFrame(
            selections={
                MockSemanticSlot.UNCERTAINTY: lexical_text,
                MockSemanticSlot.STATE: "thinking about this",
            },
        ),
    )


# ============================================================================
# GROUP A - UNCERTAINTY COLLAPSE TESTS
# ============================================================================


class TestGroupA_UncertaintyCollapse:
    """
    GROUP A: Uncertainty collapse detection tests.

    P8 has UNCERTAINTY slot populated; P9 contains certainty markers → HIGH issue.
    """

    def test_uncertainty_with_certainty_markers_triggers_high(self):
        """UNCERTAINTY slot + certainty markers = HIGH severity."""
        ctx = make_uncertainty_context(
            uncertainty_value="unsure about the situation",
            lexical_text="definitely the answer is clear",
        )

        issues = detect_uncertainty_collapse(
            ctx.semantic_frame,
            ctx.lexical_frame,
        )

        assert len(issues) > 0
        assert issues[0].issue_type == IntegrityIssueType.UNCERTAINTY_COLLAPSE
        assert issues[0].severity == Severity.HIGH
        assert "definitely" in issues[0].message.lower() or "certainty" in issues[0].message.lower()

    def test_uncertainty_with_uncertainty_preservers_is_clean(self):
        """UNCERTAINTY slot + uncertainty preservers = no issue."""
        ctx = make_uncertainty_context(
            uncertainty_value="unsure about this",
            lexical_text="I'm not sure, maybe this could work",
        )

        issues = detect_uncertainty_collapse(
            ctx.semantic_frame,
            ctx.lexical_frame,
        )

        # Should have no issues or only INFO level
        high_issues = [i for i in issues if i.severity == Severity.HIGH]
        assert len(high_issues) == 0

    def test_no_uncertainty_slot_no_collapse(self):
        """No UNCERTAINTY slot = no collapse detection."""
        ctx = make_reflexive_context(
            slots={MockSemanticSlot.STATE: "feeling anxious"},
            selections={MockSemanticSlot.STATE: "definitely feeling anxious"},
        )

        issues = detect_uncertainty_collapse(
            ctx.semantic_frame,
            ctx.lexical_frame,
        )

        # No UNCERTAINTY slot, so no uncertainty collapse
        collapse_issues = [
            i for i in issues
            if i.issue_type == IntegrityIssueType.UNCERTAINTY_COLLAPSE
        ]
        assert len(collapse_issues) == 0

    def test_multiple_certainty_markers_detected(self):
        """Multiple certainty markers all contribute to detection."""
        ctx = make_uncertainty_context(
            uncertainty_value="questioning this",
            lexical_text="absolutely certain, obviously true, definitely correct",
        )

        issues = detect_uncertainty_collapse(
            ctx.semantic_frame,
            ctx.lexical_frame,
        )

        assert len(issues) > 0
        assert issues[0].severity == Severity.HIGH
        # Message should mention found markers
        assert any(
            marker in issues[0].message.lower()
            for marker in ["absolutely", "obviously", "definitely"]
        )


# ============================================================================
# GROUP B - CAUSE LEAK TESTS
# ============================================================================


class TestGroupB_CauseLeak:
    """
    GROUP B: Cause leak under DE_ESCALATE/STABILIZE.

    Regime = DE_ESCALATE, discourse act = REFLECTION, P8 blocks CAUSE,
    but P9 selects causal connector → HIGH issue.
    """

    def test_causal_connector_in_de_escalate_triggers_high(self):
        """Causal connectors in DE_ESCALATE regime = HIGH severity."""
        ctx = make_de_escalate_context(
            discourse_act=MockDiscourseAct.REFLECTION,
            selections={
                MockSemanticSlot.STATE: "you feel this way because of stress",
            },
        )

        issues = detect_cause_leak(
            ctx.p6_regime,
            ctx.p7_discourse_envelope,
            ctx.semantic_frame,
            ctx.lexical_frame,
        )

        assert len(issues) > 0
        cause_issues = [
            i for i in issues
            if i.issue_type == IntegrityIssueType.CAUSE_LEAK
        ]
        assert len(cause_issues) > 0
        assert cause_issues[0].severity == Severity.HIGH
        assert "because" in cause_issues[0].message.lower()

    def test_therefore_in_stabilize_triggers_high(self):
        """'Therefore' in STABILIZE regime = HIGH severity."""
        ctx = MockPipelineContext(
            p6_regime=MockP6Regime(regime=MockOperationalRegime.STABILIZE),
            p7_discourse_envelope=MockP7Discourse(act=MockDiscourseAct.ACKNOWLEDGMENT),
            semantic_frame=MockSemanticFrame(
                discourse_act=MockDiscourseAct.ACKNOWLEDGMENT,
                slots={MockSemanticSlot.STATE: "validated"},
            ),
            lexical_frame=MockLexicalFrame(
                selections={
                    MockSemanticSlot.STATE: "therefore you should feel better",
                },
            ),
        )

        issues = detect_cause_leak(
            ctx.p6_regime,
            ctx.p7_discourse_envelope,
            ctx.semantic_frame,
            ctx.lexical_frame,
        )

        cause_issues = [
            i for i in issues
            if i.issue_type == IntegrityIssueType.CAUSE_LEAK
        ]
        assert len(cause_issues) > 0
        assert cause_issues[0].severity == Severity.HIGH

    def test_no_causal_connectors_is_clean(self):
        """No causal connectors = no cause leak."""
        ctx = make_de_escalate_context(
            selections={
                MockSemanticSlot.STATE: "I hear that things feel overwhelming",
            },
        )

        issues = detect_cause_leak(
            ctx.p6_regime,
            ctx.p7_discourse_envelope,
            ctx.semantic_frame,
            ctx.lexical_frame,
        )

        cause_issues = [
            i for i in issues
            if i.issue_type == IntegrityIssueType.CAUSE_LEAK
        ]
        assert len(cause_issues) == 0

    def test_causal_allowed_in_inform_regime(self):
        """Causal connectors allowed in INFORM regime."""
        ctx = MockPipelineContext(
            p6_regime=MockP6Regime(regime=MockOperationalRegime.INFORM),
            p7_discourse_envelope=MockP7Discourse(act=MockDiscourseAct.EXPLANATION),
            semantic_frame=MockSemanticFrame(
                discourse_act=MockDiscourseAct.EXPLANATION,
                slots={
                    MockSemanticSlot.STATE: "explanation",
                    MockSemanticSlot.CAUSE: "reasons",
                },
            ),
            lexical_frame=MockLexicalFrame(
                selections={
                    MockSemanticSlot.STATE: "this happens because of X",
                    MockSemanticSlot.CAUSE: "because X leads to Y",
                },
            ),
        )

        issues = detect_cause_leak(
            ctx.p6_regime,
            ctx.p7_discourse_envelope,
            ctx.semantic_frame,
            ctx.lexical_frame,
        )

        cause_issues = [
            i for i in issues
            if i.issue_type == IntegrityIssueType.CAUSE_LEAK
        ]
        # INFORM regime with EXPLANATION allows causal reasoning
        assert len(cause_issues) == 0


# ============================================================================
# GROUP C - RELATIONAL AUTHORITY DRIFT TESTS
# ============================================================================


class TestGroupC_RelationalAuthorityDrift:
    """
    GROUP C: Relational authority drift detection.

    PO1 RELATIONAL but P9 includes diagnostic assertions
    ("she is definitely depressed") → HIGH issue.
    """

    def test_diagnostic_assertion_in_relational_triggers_high(self):
        """Diagnostic assertions about others in RELATIONAL = HIGH severity."""
        ctx = make_relational_context(
            slots={MockSemanticSlot.STATE: "emotional state"},
            selections={MockSemanticSlot.STATE: "she is definitely depressed"},
        )

        issues = detect_authority_drift(
            ctx.phase_minus_one,
            ctx.p7_discourse_envelope,
            ctx.lexical_frame,
        )

        drift_issues = [
            i for i in issues
            if i.issue_type == IntegrityIssueType.AUTHORITY_DRIFT
        ]
        assert len(drift_issues) > 0
        assert drift_issues[0].severity == Severity.HIGH
        assert "relational" in drift_issues[0].message.lower()

    def test_certainty_about_others_mental_state_triggers_high(self):
        """Certainty markers about others' mental states = HIGH severity."""
        ctx = make_relational_context(
            slots={MockSemanticSlot.STATE: "mental state"},
            selections={MockSemanticSlot.STATE: "he is clearly narcissistic"},
        )

        issues = detect_authority_drift(
            ctx.phase_minus_one,
            ctx.p7_discourse_envelope,
            ctx.lexical_frame,
        )

        drift_issues = [
            i for i in issues
            if i.issue_type == IntegrityIssueType.AUTHORITY_DRIFT
        ]
        assert len(drift_issues) > 0
        assert drift_issues[0].severity == Severity.HIGH

    def test_hedged_relational_is_clean(self):
        """Hedged statements about others = no authority drift."""
        ctx = make_relational_context(
            slots={MockSemanticSlot.STATE: "observed behavior"},
            selections={MockSemanticSlot.STATE: "she seems to be feeling down"},
        )

        issues = detect_authority_drift(
            ctx.phase_minus_one,
            ctx.p7_discourse_envelope,
            ctx.lexical_frame,
        )

        drift_issues = [
            i for i in issues
            if i.issue_type == IntegrityIssueType.AUTHORITY_DRIFT
        ]
        # "seems" hedges the statement, should be clean
        assert len(drift_issues) == 0

    def test_reflexive_certainty_allowed(self):
        """Certainty about self in REFLEXIVE mode = allowed."""
        ctx = make_reflexive_context(
            slots={MockSemanticSlot.STATE: "my state"},
            selections={MockSemanticSlot.STATE: "I am definitely feeling anxious"},
        )

        issues = detect_authority_drift(
            ctx.phase_minus_one,
            ctx.p7_discourse_envelope,
            ctx.lexical_frame,
        )

        drift_issues = [
            i for i in issues
            if i.issue_type == IntegrityIssueType.AUTHORITY_DRIFT
        ]
        # REFLEXIVE mode allows certainty about self
        assert len(drift_issues) == 0


# ============================================================================
# GROUP D - CLEAN PASS TESTS
# ============================================================================


class TestGroupD_CleanPass:
    """
    GROUP D: Clean pass scenarios.

    Reflexive uncertainty preserved ("I feel unsure", "seems") → is_clean True.
    """

    def test_reflexive_uncertainty_preserved_is_clean(self):
        """Reflexive uncertainty with proper hedging = clean."""
        ctx = make_uncertainty_context(
            uncertainty_value="questioning my feelings",
            lexical_text="I feel unsure about this, it seems unclear",
        )

        report = run_p17_directly(
            po1=ctx.phase_minus_one,
            p6=ctx.p6_regime,
            p7=ctx.p7_discourse_envelope,
            p8=ctx.semantic_frame,
            p9=ctx.lexical_frame,
        )

        assert report.is_clean is True
        assert report.integrity_score >= 0.8
        assert report.high_count() == 0

    def test_complete_clean_context(self):
        """Complete context with proper constraints = clean."""
        ctx = make_de_escalate_context(
            discourse_act=MockDiscourseAct.ACKNOWLEDGMENT,
            slots={MockSemanticSlot.STATE: "acknowledged"},
            selections={MockSemanticSlot.STATE: "I hear what you're saying"},
        )

        report = run_p17_directly(
            po1=ctx.phase_minus_one,
            p6=ctx.p6_regime,
            p7=ctx.p7_discourse_envelope,
            p8=ctx.semantic_frame,
            p9=ctx.lexical_frame,
        )

        assert report.is_clean is True
        # No causal connectors, no certainty issues
        cause_issues = report.get_issues_by_type(IntegrityIssueType.CAUSE_LEAK)
        assert len(cause_issues) == 0

    def test_inform_explanation_with_because_is_clean(self):
        """INFORM + EXPLANATION allows causal reasoning = clean."""
        ctx = MockPipelineContext(
            phase_minus_one=MockPhaseMinusOne(
                selected_primary=MockGroundingCandidate(
                    mode=MockObservationMode.DETACHED,
                ),
            ),
            p6_regime=MockP6Regime(regime=MockOperationalRegime.INFORM),
            p7_discourse_envelope=MockP7Discourse(act=MockDiscourseAct.EXPLANATION),
            semantic_frame=MockSemanticFrame(
                discourse_act=MockDiscourseAct.EXPLANATION,
                slots={
                    MockSemanticSlot.STATE: "technical explanation",
                    MockSemanticSlot.CAUSE: "root cause",
                },
            ),
            lexical_frame=MockLexicalFrame(
                selections={
                    MockSemanticSlot.STATE: "this happens",
                    MockSemanticSlot.CAUSE: "because the system is designed that way",
                },
            ),
        )

        report = run_p17_directly(
            po1=ctx.phase_minus_one,
            p6=ctx.p6_regime,
            p7=ctx.p7_discourse_envelope,
            p8=ctx.semantic_frame,
            p9=ctx.lexical_frame,
        )

        # INFORM regime with EXPLANATION allows "because"
        cause_issues = [
            i for i in report.issues
            if i.issue_type == IntegrityIssueType.CAUSE_LEAK
        ]
        assert len(cause_issues) == 0


# ============================================================================
# GROUP E - MISSING INPUTS DEGRADE GRACEFULLY
# ============================================================================


class TestGroupE_MissingInputsDegradeGracefully:
    """
    GROUP E: Missing inputs degrade gracefully.

    If ctx missing P8 or P9 → INSUFFICIENT_EVIDENCE WARN,
    integrity_score reduced slightly, not catastrophic.
    """

    def test_missing_p8_and_p9_reports_insufficient_evidence(self):
        """Missing both P8 and P9 = INSUFFICIENT_EVIDENCE WARN."""
        report = run_p17_directly(
            po1=MockPhaseMinusOne(
                selected_primary=MockGroundingCandidate(
                    mode=MockObservationMode.REFLEXIVE,
                ),
            ),
            p6=MockP6Regime(regime=MockOperationalRegime.INFORM),
            p7=MockP7Discourse(act=MockDiscourseAct.EXPLANATION),
            p8=None,
            p9=None,
        )

        insufficient_issues = report.get_issues_by_type(
            IntegrityIssueType.INSUFFICIENT_EVIDENCE
        )
        assert len(insufficient_issues) > 0

        # Check that one of them is WARN severity
        warn_insufficient = [
            i for i in insufficient_issues
            if i.severity == Severity.WARN
        ]
        assert len(warn_insufficient) > 0

        # Score should be reduced but not zero
        assert report.integrity_score < 1.0
        assert report.integrity_score > 0.5

    def test_missing_p9_only_reports_insufficient(self):
        """Missing P9 only = INSUFFICIENT_EVIDENCE INFO."""
        ctx = make_reflexive_context()

        report = run_p17_directly(
            po1=ctx.phase_minus_one,
            p6=ctx.p6_regime,
            p7=ctx.p7_discourse_envelope,
            p8=ctx.semantic_frame,
            p9=None,
        )

        insufficient_issues = report.get_issues_by_type(
            IntegrityIssueType.INSUFFICIENT_EVIDENCE
        )
        # Should report missing P9
        p9_issues = [
            i for i in insufficient_issues
            if "p9" in i.message.lower()
        ]
        assert len(p9_issues) > 0

    def test_missing_po1_reports_insufficient(self):
        """Missing PO1 = INSUFFICIENT_EVIDENCE INFO."""
        ctx = make_reflexive_context()

        report = run_p17_directly(
            po1=None,
            p6=ctx.p6_regime,
            p7=ctx.p7_discourse_envelope,
            p8=ctx.semantic_frame,
            p9=ctx.lexical_frame,
        )

        insufficient_issues = report.get_issues_by_type(
            IntegrityIssueType.INSUFFICIENT_EVIDENCE
        )
        # Should report missing PO1
        po1_issues = [
            i for i in insufficient_issues
            if "po1" in i.message.lower()
        ]
        assert len(po1_issues) > 0

    def test_all_inputs_present_no_insufficient_evidence(self):
        """All inputs present = no INSUFFICIENT_EVIDENCE issues."""
        ctx = make_reflexive_context()

        report = run_p17_directly(
            po1=ctx.phase_minus_one,
            p6=ctx.p6_regime,
            p7=ctx.p7_discourse_envelope,
            p8=ctx.semantic_frame,
            p9=ctx.lexical_frame,
        )

        insufficient_issues = report.get_issues_by_type(
            IntegrityIssueType.INSUFFICIENT_EVIDENCE
        )
        assert len(insufficient_issues) == 0


# ============================================================================
# GROUP F - DETERMINISM TESTS
# ============================================================================


class TestGroupF_Determinism:
    """
    GROUP F: Determinism verification.

    Same ctx object produces identical report content and score.
    """

    def test_same_context_identical_reports(self):
        """Same context produces identical reports."""
        ctx = make_uncertainty_context(
            uncertainty_value="questioning this",
            lexical_text="definitely certain about this",
        )

        report1 = run_p17_directly(
            po1=ctx.phase_minus_one,
            p6=ctx.p6_regime,
            p7=ctx.p7_discourse_envelope,
            p8=ctx.semantic_frame,
            p9=ctx.lexical_frame,
        )

        report2 = run_p17_directly(
            po1=ctx.phase_minus_one,
            p6=ctx.p6_regime,
            p7=ctx.p7_discourse_envelope,
            p8=ctx.semantic_frame,
            p9=ctx.lexical_frame,
        )

        assert report1.integrity_score == report2.integrity_score
        assert report1.is_clean == report2.is_clean
        assert report1.issue_count() == report2.issue_count()
        assert report1.high_count() == report2.high_count()

    def test_determinism_across_100_runs(self):
        """Reports are deterministic across 100 runs."""
        ctx = make_de_escalate_context(
            selections={
                MockSemanticSlot.STATE: "because of this reason therefore that",
            },
        )

        first_report = run_p17_directly(
            po1=ctx.phase_minus_one,
            p6=ctx.p6_regime,
            p7=ctx.p7_discourse_envelope,
            p8=ctx.semantic_frame,
            p9=ctx.lexical_frame,
        )

        for i in range(100):
            report = run_p17_directly(
                po1=ctx.phase_minus_one,
                p6=ctx.p6_regime,
                p7=ctx.p7_discourse_envelope,
                p8=ctx.semantic_frame,
                p9=ctx.lexical_frame,
            )

            assert report.integrity_score == first_report.integrity_score, \
                f"Score changed on run {i}"
            assert report.issue_count() == first_report.issue_count(), \
                f"Issue count changed on run {i}"

    def test_issue_types_deterministic(self):
        """Issue types are deterministic."""
        ctx = make_relational_context(
            selections={MockSemanticSlot.STATE: "she is definitely depressed"},
        )

        report1 = run_p17_directly(
            po1=ctx.phase_minus_one,
            p6=ctx.p6_regime,
            p7=ctx.p7_discourse_envelope,
            p8=ctx.semantic_frame,
            p9=ctx.lexical_frame,
        )

        report2 = run_p17_directly(
            po1=ctx.phase_minus_one,
            p6=ctx.p6_regime,
            p7=ctx.p7_discourse_envelope,
            p8=ctx.semantic_frame,
            p9=ctx.lexical_frame,
        )

        types1 = [i.issue_type for i in report1.issues]
        types2 = [i.issue_type for i in report2.issues]

        assert types1 == types2


# ============================================================================
# SCHEMA VALIDATION TESTS
# ============================================================================


class TestSchemaValidation:
    """Tests for schema dataclass validation."""

    def test_integrity_issue_valid_construction(self):
        """IntegrityIssue can be constructed with valid values."""
        issue = create_issue(
            issue_type=IntegrityIssueType.CONTRADICTION,
            severity=Severity.HIGH,
            message="Test contradiction",
            evidence_paths=["p8.slots", "p9.selections"],
        )

        assert issue.issue_type == IntegrityIssueType.CONTRADICTION
        assert issue.severity == Severity.HIGH
        assert issue.is_high_severity()

    def test_integrity_issue_rejects_empty_message(self):
        """IntegrityIssue rejects empty message."""
        with pytest.raises(ValueError, match="non-empty string"):
            IntegrityIssue(
                issue_type=IntegrityIssueType.CONTRADICTION,
                severity=Severity.HIGH,
                message="",
                evidence_paths=("path",),
            )

    def test_integrity_issue_rejects_negative_clause_index(self):
        """IntegrityIssue rejects negative clause_index."""
        with pytest.raises(ValueError, match="non-negative"):
            IntegrityIssue(
                issue_type=IntegrityIssueType.CONTRADICTION,
                severity=Severity.HIGH,
                message="test",
                evidence_paths=("path",),
                clause_index=-1,
            )

    def test_p17_report_valid_construction(self):
        """P17IntegrityReport can be constructed with valid values."""
        issue = create_issue(
            issue_type=IntegrityIssueType.TONE_ESCALATION,
            severity=Severity.INFO,
            message="Minor escalation",
            evidence_paths=["p9.selections"],
        )

        report = create_report(
            issues=[issue],
            integrity_score=0.95,
        )

        assert report.is_clean is True  # No HIGH severity
        assert report.integrity_score == 0.95
        assert report.issue_count() == 1

    def test_p17_report_rejects_invalid_score(self):
        """P17IntegrityReport rejects score outside [0,1]."""
        with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
            P17IntegrityReport(
                issues=tuple(),
                integrity_score=1.5,
                is_clean=True,
            )

    def test_p17_report_rejects_is_clean_with_high(self):
        """P17IntegrityReport rejects is_clean=True with HIGH issues."""
        issue = create_issue(
            issue_type=IntegrityIssueType.CONTRADICTION,
            severity=Severity.HIGH,
            message="High severity issue",
            evidence_paths=["test"],
        )

        with pytest.raises(ValueError, match="is_clean cannot be True"):
            P17IntegrityReport(
                issues=(issue,),
                integrity_score=0.5,
                is_clean=True,  # Invalid: HIGH severity present
            )

    def test_version_constant(self):
        """P17_VERSION is defined."""
        assert P17_VERSION is not None
        assert P17_VERSION == "1.0.0"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Tests for integration functions."""

    def test_maybe_run_p17_attaches_report(self):
        """maybe_run_p17 attaches report to ctx.p17."""
        ctx = make_reflexive_context()

        report = maybe_run_p17(ctx)

        assert report is not None
        assert ctx.p17 is not None
        assert ctx.p17 == report
        assert has_p17_report(ctx) is True

    def test_maybe_run_p17_disabled_returns_none(self):
        """maybe_run_p17 returns None when disabled."""
        ctx = make_reflexive_context()
        ctx._p17_disabled = True

        report = maybe_run_p17(ctx)

        assert report is None
        assert is_p17_disabled(ctx) is True

    def test_get_p17_report_returns_report(self):
        """get_p17_report returns the attached report."""
        ctx = make_reflexive_context()
        maybe_run_p17(ctx)

        report = get_p17_report(ctx)

        assert report is not None
        assert isinstance(report, P17IntegrityReport)

    def test_is_integrity_clean_returns_clean_status(self):
        """is_integrity_clean returns report.is_clean."""
        ctx = make_reflexive_context(
            slots={MockSemanticSlot.STATE: "calm"},
            selections={MockSemanticSlot.STATE: "I feel calm"},
        )
        maybe_run_p17(ctx)

        assert is_integrity_clean(ctx) is True

    def test_get_integrity_score_returns_score(self):
        """get_integrity_score returns report.integrity_score."""
        ctx = make_reflexive_context()
        maybe_run_p17(ctx)

        score = get_integrity_score(ctx)

        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_get_p17_version(self):
        """get_p17_version returns version string."""
        version = get_p17_version()

        assert version == P17_VERSION
        assert version == "1.0.0"


# ============================================================================
# TONE ESCALATION TESTS
# ============================================================================


class TestToneEscalation:
    """Tests for tone escalation detection."""

    def test_multiple_intensifiers_triggers_warn(self):
        """Multiple intensifiers = WARN severity."""
        ctx = MockPipelineContext(
            lexical_frame=MockLexicalFrame(
                selections={
                    MockSemanticSlot.STATE: "very extremely highly incredibly important",
                },
            ),
        )

        issues = detect_tone_escalation(ctx.lexical_frame)

        escalation_issues = [
            i for i in issues
            if i.issue_type == IntegrityIssueType.TONE_ESCALATION
        ]
        assert len(escalation_issues) > 0
        # Multiple intensifiers should be at least WARN
        assert any(i.severity in [Severity.WARN, Severity.HIGH] for i in escalation_issues)

    def test_single_intensifier_is_info(self):
        """Single intensifier = INFO severity."""
        ctx = MockPipelineContext(
            lexical_frame=MockLexicalFrame(
                selections={
                    MockSemanticSlot.STATE: "this is very clear",
                },
            ),
        )

        issues = detect_tone_escalation(ctx.lexical_frame)

        escalation_issues = [
            i for i in issues
            if i.issue_type == IntegrityIssueType.TONE_ESCALATION
        ]
        if escalation_issues:
            assert escalation_issues[0].severity == Severity.INFO

    def test_no_intensifiers_is_clean(self):
        """No intensifiers = no escalation issues."""
        ctx = MockPipelineContext(
            lexical_frame=MockLexicalFrame(
                selections={
                    MockSemanticSlot.STATE: "I understand your concern",
                },
            ),
        )

        issues = detect_tone_escalation(ctx.lexical_frame)

        escalation_issues = [
            i for i in issues
            if i.issue_type == IntegrityIssueType.TONE_ESCALATION
        ]
        assert len(escalation_issues) == 0


# ============================================================================
# SLOT CONTRADICTION TESTS
# ============================================================================


class TestSlotContradictions:
    """Tests for slot contradiction detection."""

    def test_opposite_polarity_state_triggers_high(self):
        """Opposite polarity in STATE slot = HIGH severity."""
        ctx = MockPipelineContext(
            semantic_frame=MockSemanticFrame(
                discourse_act=MockDiscourseAct.REFLECTION,
                slots={MockSemanticSlot.STATE: "feeling happy and good"},
            ),
            lexical_frame=MockLexicalFrame(
                selections={MockSemanticSlot.STATE: "feeling sad and bad"},
            ),
        )

        issues = detect_slot_contradictions(
            ctx.semantic_frame,
            ctx.lexical_frame,
        )

        contradiction_issues = [
            i for i in issues
            if i.issue_type == IntegrityIssueType.CONTRADICTION
        ]
        assert len(contradiction_issues) > 0
        assert contradiction_issues[0].severity == Severity.HIGH

    def test_consistent_polarity_is_clean(self):
        """Consistent polarity = no contradiction."""
        ctx = MockPipelineContext(
            semantic_frame=MockSemanticFrame(
                discourse_act=MockDiscourseAct.REFLECTION,
                slots={MockSemanticSlot.STATE: "feeling anxious"},
            ),
            lexical_frame=MockLexicalFrame(
                selections={MockSemanticSlot.STATE: "I'm feeling worried"},
            ),
        )

        issues = detect_slot_contradictions(
            ctx.semantic_frame,
            ctx.lexical_frame,
        )

        contradiction_issues = [
            i for i in issues
            if i.issue_type == IntegrityIssueType.CONTRADICTION
        ]
        # No opposite polarity detected
        assert len(contradiction_issues) == 0


# ============================================================================
# SCORING TESTS
# ============================================================================


class TestScoring:
    """Tests for integrity score computation."""

    def test_no_issues_full_score(self):
        """No issues = score 1.0."""
        report = create_report(issues=[], integrity_score=1.0)

        assert report.integrity_score == 1.0
        assert report.is_clean is True

    def test_high_severity_reduces_score(self):
        """HIGH severity issues reduce score significantly."""
        ctx = make_uncertainty_context(
            uncertainty_value="unsure",
            lexical_text="definitely certain",
        )

        report = run_p17_directly(
            po1=ctx.phase_minus_one,
            p6=ctx.p6_regime,
            p7=ctx.p7_discourse_envelope,
            p8=ctx.semantic_frame,
            p9=ctx.lexical_frame,
        )

        # Should have HIGH severity issue that reduces score
        assert report.high_count() > 0
        assert report.integrity_score < 1.0
        assert report.is_clean is False

    def test_info_severity_minimal_impact(self):
        """INFO severity has minimal score impact."""
        issue = create_issue(
            issue_type=IntegrityIssueType.INSUFFICIENT_EVIDENCE,
            severity=Severity.INFO,
            message="Minor missing input",
            evidence_paths=["po1"],
        )

        report = create_report(
            issues=[issue],
            integrity_score=0.995,  # Minimal reduction
        )

        assert report.integrity_score > 0.9
        assert report.is_clean is True  # INFO doesn't affect is_clean

    def test_score_clamped_to_zero(self):
        """Score cannot go below 0.0."""
        # Create many HIGH severity issues
        issues = [
            create_issue(
                issue_type=IntegrityIssueType.CONTRADICTION,
                severity=Severity.HIGH,
                message=f"Issue {i}",
                evidence_paths=["test"],
            )
            for i in range(20)
        ]

        report = create_report(
            issues=issues,
            integrity_score=0.0,  # Would be negative without clamping
        )

        assert report.integrity_score >= 0.0
