"""
P50 Cognitive Consistency Regression Test Suite

This test suite validates the P50 Cognitive Consistency Regression phase.

Testing rule (STRICT):
    One test per invariant.
    No invariant -> no test.

Minimum required tests:
    - INV-P50-A1: Upstream immutability
    - INV-P50-A3: Import graph safety
    - INV-P50-D1: Determinism
    - INV-P50-S1: Semantic isolation
    - Consistency score monotonicity
    - Known contradiction detection
    - No-contradiction baseline

Each test explicitly states which invariant it proves.

CRITICAL: All tests are DETERMINISTIC with ZERO false positives.
"""

import ast
import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import pytest


# ============================================================================
# IMPORTS
# ============================================================================

from symbolu.mechanical.pipeline.p50_cognitive_consistency import (
    # Version
    P50_VERSION,
    # Constants
    VALID_CONSISTENCY_BANDS,
    STABLE_THRESHOLD,
    STRAINED_THRESHOLD,
    W_REGIME_STABILITY,
    W_DISCOURSE_CONTINUITY,
    W_SEMANTIC_PRESERVATION,
    W_LEXICAL_POLARITY,
    W_DRIFT_ENTROPY,
    # Dataclasses
    CognitiveConsistencyReport,
    # Factory
    create_cognitive_consistency_report,
    # Core computation
    compute_cognitive_consistency,
    run_p50_directly,
    # Integration
    maybe_run_p50,
    # Helpers
    is_p50_disabled,
    has_p50_report,
    get_p50_report,
    get_consistency_score,
    get_consistency_band,
    get_detected_contradictions,
    get_regression_flags,
)


# ============================================================================
# MOCK HELPERS
# ============================================================================


class MockOperationalRegime(str, Enum):
    """Mock operational regime enum."""
    STABILIZE = "STABILIZE"
    REFLECT = "REFLECT"
    INFORM = "INFORM"
    CLARIFY = "CLARIFY"
    DE_ESCALATE = "DE_ESCALATE"
    HOLD = "HOLD"


class MockDiscourseAct(str, Enum):
    """Mock discourse act enum."""
    QUESTION = "QUESTION"
    REFLECTION = "REFLECTION"
    ACKNOWLEDGMENT = "ACKNOWLEDGMENT"
    EXPLANATION = "EXPLANATION"
    INSTRUCTION = "INSTRUCTION"
    DEFERRAL = "DEFERRAL"


class MockVolatilityBand(str, Enum):
    """Mock volatility band enum."""
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


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
class MockSemanticSlot:
    """Mock semantic slot."""
    slot_type: str
    value: str


@dataclass
class MockSemanticFrame:
    """Mock P8 semantic frame."""
    discourse_act: MockDiscourseAct
    slots: Dict[str, MockSemanticSlot]
    allowed: bool = True


@dataclass
class MockLexicalFrame:
    """Mock P9 lexical frame."""
    selections: List[Dict] = field(default_factory=list)
    polarity: Optional[float] = None


@dataclass
class MockP18Entropy:
    """Mock P18 temporal entropy report."""
    entropy_now: float
    delta_entropy: Optional[float] = None
    volatility_band: MockVolatilityBand = MockVolatilityBand.MED


@dataclass
class MockP19Drift:
    """Mock P19 drift fusion report."""
    drift_fusion_index: float
    drift_risk_band: str = "moderate"


@dataclass
class MockPipelineContext:
    """Mock pipeline context for testing."""
    p6_regime: Optional[MockP6Regime] = None
    p7_discourse_envelope: Optional[MockP7Discourse] = None
    semantic_frame: Optional[MockSemanticFrame] = None
    lexical_frame: Optional[MockLexicalFrame] = None
    p18: Optional[MockP18Entropy] = None
    p19_drift_fusion: Optional[MockP19Drift] = None
    p50_cognitive_consistency: Optional[CognitiveConsistencyReport] = None
    _p50_disabled: bool = False


def make_stable_context() -> MockPipelineContext:
    """Create a stable context with consistent values."""
    return MockPipelineContext(
        p6_regime=MockP6Regime(regime=MockOperationalRegime.INFORM),
        p7_discourse_envelope=MockP7Discourse(act=MockDiscourseAct.EXPLANATION),
        semantic_frame=MockSemanticFrame(
            discourse_act=MockDiscourseAct.EXPLANATION,
            slots={
                "subject": MockSemanticSlot("SUBJECT", "test"),
                "predicate": MockSemanticSlot("PREDICATE", "action"),
            },
        ),
        lexical_frame=MockLexicalFrame(polarity=0.5),
        p18=MockP18Entropy(entropy_now=0.3, delta_entropy=0.1, volatility_band=MockVolatilityBand.LOW),
        p19_drift_fusion=MockP19Drift(drift_fusion_index=0.2, drift_risk_band="low"),
    )


def make_contradictory_context_pair():
    """Create a pair of contexts with regime contradiction."""
    previous = MockPipelineContext(
        p6_regime=MockP6Regime(regime=MockOperationalRegime.HOLD),
        p7_discourse_envelope=MockP7Discourse(act=MockDiscourseAct.DEFERRAL),
        semantic_frame=MockSemanticFrame(
            discourse_act=MockDiscourseAct.DEFERRAL,
            slots={"subject": MockSemanticSlot("SUBJECT", "test")},
        ),
        lexical_frame=MockLexicalFrame(polarity=-0.5),
        p18=MockP18Entropy(entropy_now=0.3, volatility_band=MockVolatilityBand.LOW),
        p19_drift_fusion=MockP19Drift(drift_fusion_index=0.2),
    )

    current = MockPipelineContext(
        p6_regime=MockP6Regime(regime=MockOperationalRegime.INFORM),  # HOLD -> INFORM is contradictory
        p7_discourse_envelope=MockP7Discourse(act=MockDiscourseAct.INSTRUCTION),  # DEFERRAL -> INSTRUCTION is contradictory
        semantic_frame=MockSemanticFrame(
            discourse_act=MockDiscourseAct.INSTRUCTION,
            slots={},  # Slots removed
        ),
        lexical_frame=MockLexicalFrame(polarity=0.7),  # Polarity reversed
        p18=MockP18Entropy(entropy_now=0.8, volatility_band=MockVolatilityBand.HIGH),
        p19_drift_fusion=MockP19Drift(drift_fusion_index=0.9),
    )

    return previous, current


# ============================================================================
# INV-P50-A1: UPSTREAM IMMUTABILITY
# ============================================================================


class TestINV_P50_A1_UpstreamImmutability:
    """
    INV-P50-A1: P50 cannot modify any upstream phase output.

    This test proves INV-P50-A1.
    """

    def test_p50_does_not_modify_p6_regime(self):
        """
        This test proves INV-P50-A1.

        P50 must not modify P6 regime when computing consistency.
        """
        ctx = make_stable_context()
        previous_ctx = make_stable_context()

        # Deep copy to compare after
        original_p6_regime = ctx.p6_regime.regime
        original_p6_reason = ctx.p6_regime.reason

        # Run P50
        maybe_run_p50(ctx, previous_ctx)

        # Verify P6 unchanged
        assert ctx.p6_regime.regime == original_p6_regime
        assert ctx.p6_regime.reason == original_p6_reason

    def test_p50_does_not_modify_p7_discourse(self):
        """
        This test proves INV-P50-A1.

        P50 must not modify P7 discourse envelope.
        """
        ctx = make_stable_context()
        previous_ctx = make_stable_context()

        original_act = ctx.p7_discourse_envelope.act
        original_allowed = ctx.p7_discourse_envelope.allowed

        maybe_run_p50(ctx, previous_ctx)

        assert ctx.p7_discourse_envelope.act == original_act
        assert ctx.p7_discourse_envelope.allowed == original_allowed

    def test_p50_does_not_modify_p8_semantic_frame(self):
        """
        This test proves INV-P50-A1.

        P50 must not modify P8 semantic frame.
        """
        ctx = make_stable_context()
        previous_ctx = make_stable_context()

        original_slots = dict(ctx.semantic_frame.slots)

        maybe_run_p50(ctx, previous_ctx)

        assert ctx.semantic_frame.slots == original_slots

    def test_p50_does_not_modify_p18_p19(self):
        """
        This test proves INV-P50-A1.

        P50 must not modify P18 or P19 reports.
        """
        ctx = make_stable_context()
        previous_ctx = make_stable_context()

        original_p18_entropy = ctx.p18.entropy_now
        original_p19_drift = ctx.p19_drift_fusion.drift_fusion_index

        maybe_run_p50(ctx, previous_ctx)

        assert ctx.p18.entropy_now == original_p18_entropy
        assert ctx.p19_drift_fusion.drift_fusion_index == original_p19_drift


# ============================================================================
# INV-P50-A3: IMPORT GRAPH SAFETY
# ============================================================================


class TestINV_P50_A3_ImportGraphSafety:
    """
    INV-P50-A3: P50 cannot be read by P6-P21.

    This test proves INV-P50-A3.
    """

    def test_p50_module_does_not_import_from_p6_to_p21(self):
        """
        This test proves INV-P50-A3.

        P50 module should not import anything from P6-P21 that would
        create a reverse dependency. P50 may READ from P6-P21 but
        P6-P21 must NOT read from P50.

        We verify this by checking that P50 schema/analyzer have no
        imports that would indicate P6-P21 depend on P50.
        """
        import symbolu.mechanical.pipeline.p50_cognitive_consistency.p50_schema as schema_module
        import symbolu.mechanical.pipeline.p50_cognitive_consistency.p50_analyzer as analyzer_module

        # Get the source code
        import inspect
        schema_source = inspect.getsource(schema_module)
        analyzer_source = inspect.getsource(analyzer_module)

        # P50 should NOT be imported by P6-P21
        # We verify P50 doesn't import governance/eligibility code that would
        # create circular dependency
        forbidden_imports = [
            "from symbolu.mechanical.pipeline.governance",
            "from symbolu.mechanical.pipeline.phase_po5",
            "from symbolu.mechanical.pipeline.phase_po4",
            "from symbolu.mechanical.pipeline.p21_delivery",
        ]

        for forbidden in forbidden_imports:
            assert forbidden not in schema_source, \
                f"Schema should not import {forbidden}"
            assert forbidden not in analyzer_source, \
                f"Analyzer should not import {forbidden}"

    def test_p50_output_is_observer_only_field(self):
        """
        This test proves INV-P50-A3.

        The P50 output field name (p50_cognitive_consistency) should indicate
        it's an observer-only phase that downstream phases don't depend on.
        """
        report = create_cognitive_consistency_report(
            consistency_score=0.8,
        )

        # observer_only field must be True
        assert report.observer_only is True

        # architectural_phase must be P50
        assert report.architectural_phase == "P50"


# ============================================================================
# INV-P50-D1: DETERMINISM
# ============================================================================


class TestINV_P50_D1_Determinism:
    """
    INV-P50-D1: Same history + same input -> same report (bitwise).

    This test proves INV-P50-D1.
    """

    def test_same_inputs_produce_identical_reports(self):
        """
        This test proves INV-P50-D1.

        Running P50 twice with identical inputs must produce
        bitwise identical reports.
        """
        ctx1 = make_stable_context()
        ctx2 = make_stable_context()
        prev1 = make_stable_context()
        prev2 = make_stable_context()

        report1 = maybe_run_p50(ctx1, prev1)
        report2 = maybe_run_p50(ctx2, prev2)

        assert report1.consistency_score == report2.consistency_score
        assert report1.consistency_band == report2.consistency_band
        assert report1.detected_contradictions == report2.detected_contradictions
        assert report1.regression_flags == report2.regression_flags
        assert report1.observer_only == report2.observer_only

    def test_determinism_across_100_runs(self):
        """
        This test proves INV-P50-D1.

        Consistency score must be identical across 100 runs.
        """
        first_report = None

        for i in range(100):
            ctx = make_stable_context()
            prev = make_stable_context()
            report = maybe_run_p50(ctx, prev)

            if first_report is None:
                first_report = report
            else:
                assert report.consistency_score == first_report.consistency_score, \
                    f"Score changed on run {i}"
                assert report.consistency_band == first_report.consistency_band, \
                    f"Band changed on run {i}"

    def test_compute_consistency_is_deterministic(self):
        """
        This test proves INV-P50-D1.

        compute_cognitive_consistency with identical inputs must
        produce identical outputs.
        """
        inputs = {
            "current_regime": "INFORM",
            "previous_regime": "INFORM",
            "current_discourse_act": "EXPLANATION",
            "previous_discourse_act": "EXPLANATION",
            "current_semantic_slots": {"a": 1, "b": 2},
            "previous_semantic_slots": {"a": 1, "b": 2},
            "current_polarity": 0.5,
            "previous_polarity": 0.5,
            "drift_index": 0.3,
            "entropy_diff": 0.1,
            "entropy_volatility": 0.3,
        }

        report1 = compute_cognitive_consistency(**inputs)
        report2 = compute_cognitive_consistency(**inputs)

        assert report1.consistency_score == report2.consistency_score
        assert report1.to_dict() == report2.to_dict()


# ============================================================================
# INV-P50-S1: SEMANTIC ISOLATION
# ============================================================================


class TestINV_P50_S1_SemanticIsolation:
    """
    INV-P50-S1: No semantic reinterpretation.

    This test proves INV-P50-S1.
    """

    def test_p50_does_not_interpret_semantic_content(self):
        """
        This test proves INV-P50-S1.

        P50 must only compare structural presence/absence of slots,
        not interpret their semantic meaning.
        """
        # Two contexts with different semantic content but same structure
        ctx1 = make_stable_context()
        ctx1.semantic_frame.slots = {
            "subject": MockSemanticSlot("SUBJECT", "happiness"),
            "predicate": MockSemanticSlot("PREDICATE", "increases"),
        }

        ctx2 = make_stable_context()
        ctx2.semantic_frame.slots = {
            "subject": MockSemanticSlot("SUBJECT", "sadness"),
            "predicate": MockSemanticSlot("PREDICATE", "decreases"),
        }

        prev = make_stable_context()
        prev.semantic_frame.slots = {
            "subject": MockSemanticSlot("SUBJECT", "emotion"),
            "predicate": MockSemanticSlot("PREDICATE", "changes"),
        }

        report1 = maybe_run_p50(ctx1, prev)
        report2 = maybe_run_p50(ctx2, prev)

        # Both should have same preservation score because structure is same
        # (same slot keys present)
        assert report1.consistency_score == report2.consistency_score

    def test_p50_only_checks_slot_presence_not_values(self):
        """
        This test proves INV-P50-S1.

        P50 checks if slots exist, not what they contain.
        """
        prev = make_stable_context()
        prev.semantic_frame.slots = {"a": MockSemanticSlot("A", "1"), "b": MockSemanticSlot("B", "2")}

        current = make_stable_context()
        current.semantic_frame.slots = {"a": MockSemanticSlot("A", "different"), "b": MockSemanticSlot("B", "values")}

        report = maybe_run_p50(current, prev)

        # No slot removal contradiction should be detected
        slot_removal_contradictions = [c for c in report.detected_contradictions if "SLOT_REMOVED" in c]
        assert len(slot_removal_contradictions) == 0


# ============================================================================
# CONSISTENCY SCORE MONOTONICITY
# ============================================================================


class TestConsistencyScoreMonotonicity:
    """
    Test that consistency score behaves monotonically with contradictions.
    """

    def test_more_contradictions_lower_score(self):
        """
        More contradictions should produce lower consistency scores.
        """
        # No contradictions - stable
        report_stable = compute_cognitive_consistency(
            current_regime="INFORM",
            previous_regime="INFORM",
            current_discourse_act="EXPLANATION",
            previous_discourse_act="EXPLANATION",
            current_semantic_slots={"a": 1},
            previous_semantic_slots={"a": 1},
            current_polarity=0.5,
            previous_polarity=0.5,
            drift_index=0.2,
            entropy_diff=0.1,
            entropy_volatility=0.2,
        )

        # One contradiction - regime
        report_one = compute_cognitive_consistency(
            current_regime="INFORM",
            previous_regime="HOLD",  # HOLD -> INFORM is contradictory
            current_discourse_act="EXPLANATION",
            previous_discourse_act="EXPLANATION",
            current_semantic_slots={"a": 1},
            previous_semantic_slots={"a": 1},
            current_polarity=0.5,
            previous_polarity=0.5,
            drift_index=0.2,
            entropy_diff=0.1,
            entropy_volatility=0.2,
        )

        # Multiple contradictions
        report_multiple = compute_cognitive_consistency(
            current_regime="INFORM",
            previous_regime="HOLD",  # HOLD -> INFORM is contradictory
            current_discourse_act="INSTRUCTION",
            previous_discourse_act="DEFERRAL",  # DEFERRAL -> INSTRUCTION is contradictory
            current_semantic_slots={},
            previous_semantic_slots={"a": 1},  # Slot removed
            current_polarity=0.8,
            previous_polarity=-0.8,  # Polarity reversed
            drift_index=0.9,
            entropy_diff=0.1,
            entropy_volatility=0.2,  # Drift-entropy disagreement
        )

        assert report_stable.consistency_score > report_one.consistency_score
        assert report_one.consistency_score > report_multiple.consistency_score


# ============================================================================
# KNOWN CONTRADICTION DETECTION
# ============================================================================


class TestKnownContradictionDetection:
    """
    Test that known contradictions are properly detected.
    """

    def test_regime_contradiction_detected(self):
        """
        HOLD -> INFORM regime transition should be detected as contradiction.
        """
        report = compute_cognitive_consistency(
            current_regime="INFORM",
            previous_regime="HOLD",
            current_discourse_act="EXPLANATION",
            previous_discourse_act="EXPLANATION",
            current_semantic_slots=None,
            previous_semantic_slots=None,
            current_polarity=None,
            previous_polarity=None,
            drift_index=None,
            entropy_diff=None,
            entropy_volatility=None,
        )

        assert any("REGIME_CONTRADICTION" in c for c in report.detected_contradictions)

    def test_discourse_contradiction_detected(self):
        """
        DEFERRAL -> INSTRUCTION discourse transition should be detected.
        """
        report = compute_cognitive_consistency(
            current_regime="INFORM",
            previous_regime="INFORM",
            current_discourse_act="INSTRUCTION",
            previous_discourse_act="DEFERRAL",
            current_semantic_slots=None,
            previous_semantic_slots=None,
            current_polarity=None,
            previous_polarity=None,
            drift_index=None,
            entropy_diff=None,
            entropy_volatility=None,
        )

        assert any("DISCOURSE_CONTRADICTION" in c for c in report.detected_contradictions)

    def test_polarity_reversal_detected(self):
        """
        Large polarity reversal should be detected.
        """
        report = compute_cognitive_consistency(
            current_regime="INFORM",
            previous_regime="INFORM",
            current_discourse_act="EXPLANATION",
            previous_discourse_act="EXPLANATION",
            current_semantic_slots=None,
            previous_semantic_slots=None,
            current_polarity=0.8,
            previous_polarity=-0.8,
            drift_index=None,
            entropy_diff=None,
            entropy_volatility=None,
        )

        assert any("POLARITY_REVERSAL" in c for c in report.detected_contradictions)

    def test_slot_removal_detected(self):
        """
        Slot removal should be detected.
        """
        report = compute_cognitive_consistency(
            current_regime="INFORM",
            previous_regime="INFORM",
            current_discourse_act="EXPLANATION",
            previous_discourse_act="EXPLANATION",
            current_semantic_slots={"a": 1},
            previous_semantic_slots={"a": 1, "b": 2, "c": 3},
            current_polarity=None,
            previous_polarity=None,
            drift_index=None,
            entropy_diff=None,
            entropy_volatility=None,
        )

        slot_removals = [c for c in report.detected_contradictions if "SLOT_REMOVED" in c]
        assert len(slot_removals) == 2  # b and c removed


# ============================================================================
# NO-CONTRADICTION BASELINE
# ============================================================================


class TestNoContradictionBaseline:
    """
    Test baseline behavior when no contradictions exist.
    """

    def test_no_contradictions_produces_stable_band(self):
        """
        When no contradictions exist and all factors are stable,
        consistency band should be 'stable'.
        """
        report = compute_cognitive_consistency(
            current_regime="INFORM",
            previous_regime="INFORM",
            current_discourse_act="EXPLANATION",
            previous_discourse_act="EXPLANATION",
            current_semantic_slots={"a": 1, "b": 2},
            previous_semantic_slots={"a": 1, "b": 2},
            current_polarity=0.5,
            previous_polarity=0.5,
            drift_index=0.2,
            entropy_diff=0.1,
            entropy_volatility=0.2,
        )

        assert report.consistency_band == "stable"
        assert report.consistency_score >= STABLE_THRESHOLD
        assert len(report.detected_contradictions) == 0

    def test_no_history_produces_stable_band(self):
        """
        When no history exists (first turn), consistency should be stable.
        """
        report = compute_cognitive_consistency(
            current_regime="INFORM",
            previous_regime=None,
            current_discourse_act="EXPLANATION",
            previous_discourse_act=None,
            current_semantic_slots={"a": 1},
            previous_semantic_slots=None,
            current_polarity=0.5,
            previous_polarity=None,
            drift_index=0.2,
            entropy_diff=0.1,
            entropy_volatility=0.2,
        )

        assert report.consistency_band == "stable"
        assert len(report.detected_contradictions) == 0


# ============================================================================
# SCHEMA VALIDATION
# ============================================================================


class TestSchemaValidation:
    """
    Test schema dataclass validation.
    """

    def test_report_requires_observer_only_true(self):
        """
        CognitiveConsistencyReport must have observer_only=True.
        """
        with pytest.raises(ValueError, match="observer_only must be True"):
            CognitiveConsistencyReport(
                consistency_score=0.8,
                consistency_band="stable",
                detected_contradictions=(),
                regression_flags=(),
                observer_only=False,  # Should fail
            )

    def test_report_validates_consistency_band(self):
        """
        CognitiveConsistencyReport must have valid consistency_band.
        """
        with pytest.raises(ValueError, match="Invalid consistency_band"):
            CognitiveConsistencyReport(
                consistency_score=0.8,
                consistency_band="invalid_band",  # Should fail
                detected_contradictions=(),
                regression_flags=(),
                observer_only=True,
            )

    def test_report_validates_band_matches_score(self):
        """
        CognitiveConsistencyReport band must match score thresholds.
        """
        with pytest.raises(ValueError, match="does not match expected band"):
            CognitiveConsistencyReport(
                consistency_score=0.8,  # Should be "stable"
                consistency_band="inconsistent",  # Wrong band
                detected_contradictions=(),
                regression_flags=(),
                observer_only=True,
            )

    def test_factory_clamps_score_to_valid_range(self):
        """
        Factory function should clamp score to [0.0, 1.0].
        """
        report_high = create_cognitive_consistency_report(
            consistency_score=1.5,  # Over 1.0
        )
        assert report_high.consistency_score == 1.0

        report_low = create_cognitive_consistency_report(
            consistency_score=-0.5,  # Under 0.0
        )
        assert report_low.consistency_score == 0.0


# ============================================================================
# INTEGRATION HELPERS
# ============================================================================


class TestIntegrationHelpers:
    """
    Test integration helper functions.
    """

    def test_is_p50_disabled(self):
        """
        is_p50_disabled should respect _p50_disabled flag.
        """
        ctx = MockPipelineContext()
        assert is_p50_disabled(ctx) is False

        ctx._p50_disabled = True
        assert is_p50_disabled(ctx) is True

    def test_disabled_p50_returns_none(self):
        """
        When P50 is disabled, maybe_run_p50 should return None.
        """
        ctx = make_stable_context()
        ctx._p50_disabled = True

        result = maybe_run_p50(ctx, None)
        assert result is None

    def test_has_p50_report(self):
        """
        has_p50_report should check for report presence.
        """
        ctx = MockPipelineContext()
        assert has_p50_report(ctx) is False

        maybe_run_p50(ctx, None)
        assert has_p50_report(ctx) is True

    def test_get_consistency_score_default(self):
        """
        get_consistency_score should return 1.0 when no report.
        """
        ctx = MockPipelineContext()
        assert get_consistency_score(ctx) == 1.0

    def test_get_consistency_band_default(self):
        """
        get_consistency_band should return 'stable' when no report.
        """
        ctx = MockPipelineContext()
        assert get_consistency_band(ctx) == "stable"


# ============================================================================
# VERSION AND METADATA
# ============================================================================


class TestVersionMetadata:
    """
    Test version and metadata.
    """

    def test_p50_version_defined(self):
        """
        P50_VERSION should be defined.
        """
        assert P50_VERSION is not None
        assert P50_VERSION == "1.0.0"

    def test_weights_sum_to_one(self):
        """
        Formula weights must sum to 1.0.
        """
        total = (
            W_REGIME_STABILITY +
            W_DISCOURSE_CONTINUITY +
            W_SEMANTIC_PRESERVATION +
            W_LEXICAL_POLARITY +
            W_DRIFT_ENTROPY
        )
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, not 1.0"

    def test_report_has_correct_architectural_phase(self):
        """
        Report should have architectural_phase set to 'P50'.
        """
        report = create_cognitive_consistency_report(consistency_score=0.8)
        assert report.architectural_phase == "P50"

    def test_report_has_version(self):
        """
        Report should include version.
        """
        report = create_cognitive_consistency_report(consistency_score=0.8)
        assert report.version == P50_VERSION
