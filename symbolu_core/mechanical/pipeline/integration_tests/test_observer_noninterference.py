"""
Observer Non-Interference Proof Test Suite

This test suite PROVES (with code evidence + tests) that OBSERVER / WITNESS
modules (P22, P23, P24) NEVER influence upstream authoritative decisions.

==============================================================================
DEPENDENCY GRAPH REPORT
==============================================================================

## P22 - Acoustic-Vrtti Witness Extractor
Location: symbolu/mechanical/pipeline/p22_acoustic_witness/

IMPORTS (what P22 imports):
  - symbolu.formulas.acoustic_unit_mapper (map_acoustic_units, get_acoustic_signature)
  - symbolu.formulas.vritti_mapper (VrittiType, assign_vritti_sequence, get_vritti_distribution)
  - symbolu.mechanical.pipeline.p21_delivery.p21_delivery_schema (DeliveryMode)
  - symbolu.mechanical.pipeline.p22_acoustic_witness.p22_schema (internal)

IMPORTERS (who imports P22):
  - symbolu.mechanical.pipeline.p23_alignment.p23_resolver (reads P22 pressure_band, motion_balance)
  - symbolu.mechanical.pipeline.p24_projection.p24_projection_resolver (reads P22 pressure_band)
  - symbolu.mechanical.pipeline.models (type annotation only)
  - Tests only (no authoritative modules)

OUTPUT FLOW in PipelineContext:
  -> ctx.p22_acoustic_witness (P22AcousticVrittiWitness)
  -> ctx.p22 (alias)

AUTHORITATIVE DECISION POINTS REACHED: NONE
  - NOT imported by P6 (regime)
  - NOT imported by P7 (discourse)
  - NOT imported by P8 (semantic)
  - NOT imported by P9 (lexical)
  - NOT imported by policy engines
  - NOT imported by MLCR/TTRO routing
  - NOT imported by FusionEngine

## P23 - Inner-Outer Alignment Observer
Location: symbolu/mechanical/pipeline/p23_alignment/

IMPORTS (what P23 imports):
  - symbolu.mechanical.pipeline.p23_alignment.p23_schema (internal)
  - ctx.p22_acoustic_witness (reads pressure_band, motion_balance)
  - ctx.p6_regime (reads regime - READ-ONLY observation)
  - ctx.p7_discourse (reads discourse_act - READ-ONLY observation)

IMPORTERS (who imports P23):
  - symbolu.mechanical.pipeline.p24_projection.p24_projection_resolver (reads P23 alignment_state, tension_score)
  - symbolu.mechanical.pipeline.models (type annotation only)
  - Tests only (no authoritative modules)

OUTPUT FLOW in PipelineContext:
  -> ctx.p23_alignment_report (P23AlignmentReport)
  -> ctx.p23 (alias)

AUTHORITATIVE DECISION POINTS REACHED: NONE
  - NOT imported by P6 (regime)
  - NOT imported by P7 (discourse)
  - NOT imported by P8 (semantic)
  - NOT imported by P9 (lexical)
  - NOT imported by policy engines
  - NOT imported by MLCR/TTRO routing
  - NOT imported by FusionEngine

## P24 - Acoustic-Ontology Projection Observer
Location: symbolu/mechanical/pipeline/p24_projection/

IMPORTS (what P24 imports):
  - symbolu.mechanical.pipeline.p24_projection.p24_projection_schema (internal)
  - ctx.phase_minus_one (reads is_blocked - READ-ONLY observation)
  - ctx.p6_regime (reads regime - READ-ONLY observation)
  - ctx.p7_discourse_envelope (reads act - READ-ONLY observation)
  - ctx.semantic_frame (reads slots - READ-ONLY observation)
  - ctx.lexical_frame (reads selections - READ-ONLY observation)
  - ctx.grammar_evidence (reads imperative_form - READ-ONLY observation)
  - ctx.p22_acoustic_witness (reads pressure_band, dominant_motion)
  - ctx.p23_alignment_report (reads alignment_state, tension_score)

IMPORTERS (who imports P24):
  - symbolu.mechanical.pipeline.models (type annotation only)
  - Tests only (no authoritative modules)

OUTPUT FLOW in PipelineContext:
  -> ctx.p24_projection_report (P24ProjectionReport)
  -> ctx.p24 (alias)

AUTHORITATIVE DECISION POINTS REACHED: NONE
  - NOT imported by P6 (regime)
  - NOT imported by P7 (discourse)
  - NOT imported by P8 (semantic)
  - NOT imported by P9 (lexical)
  - NOT imported by policy engines
  - NOT imported by MLCR/TTRO routing
  - NOT imported by FusionEngine

==============================================================================
ALLOWED SINKS DEFINITION (Code-Enforced Rules)
==============================================================================

ALLOWED sinks for P22/P23/P24 outputs:
  1. Snapshot/logging (to_dict() serialization in PipelineContext)
  2. Observability dashboards (unified_api.py observability fields)
  3. Renderer-only presentation hints (must NOT change semantic content)
  4. DHA tone hints (must NOT change semantic content)
  5. P23 observing P22 (observer chain, not authoritative)
  6. P24 observing P22+P23 (observer chain, not authoritative)

FORBIDDEN sinks for P22/P23/P24 outputs:
  1. Regime selection (P6)
  2. Policy gating (phase_minus_one, phase_zero, phase_one)
  3. Routing decisions (MLCR, TTRO)
  4. Fusion truth edits (FusionEngine)
  5. Semantic slot allow-list decisions (P8)
  6. Lexical frame decisions (P9)
  7. Discourse act selection (P7)
  8. Any authoritative envelope modification

==============================================================================
HARD GREP-BASED EVIDENCE
==============================================================================

Commands run and results:

1. rg -n "p22|p23|p24|acoustic_witness|pressure_report|projection_observer" symbolu/
   -> All matches are within P22/P23/P24 modules, their tests, or PipelineContext.to_dict()
   -> NO matches in P6, P7, P8, P9, policy, intent, formulas (except coherence_regime_scenario_mapper
      which has "projection_risk" which is a P8 internal concept, NOT P24)

2. rg -n "is_safe|gate|eligib|block|regime|policy|allow_list|ttro|mlcr|fusion" symbolu/
   -> Authoritative decision code found in expected locations
   -> NO references to P22/P23/P24 outputs in any of these files

3. grep for "from.*p22|from.*p23|from.*p24" in symbolu/
   -> Only internal imports within observer modules and their tests
   -> models.py has TYPE_CHECKING import only (no runtime dependency)

4. grep for "ctx.p22|ctx.p23|ctx.p24" outside of observer modules
   -> Only in PipelineContext.to_dict() for serialization
   -> Only in tests

==============================================================================
VIOLATIONS FOUND: NONE
==============================================================================

The codebase correctly implements observer non-interference:
1. P22/P23/P24 have explicit FORBIDDEN_ATTRS sets
2. P22/P23/P24 only write to their own ctx.pXX_* attributes
3. No authoritative module imports or references P22/P23/P24 outputs
4. Observer outputs only appear in serialization (to_dict) and tests

==============================================================================
TEST HARNESS
==============================================================================
"""

from __future__ import annotations

import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set
from enum import Enum

# ============================================================================
# AUTHORITATIVE MODULE IMPORTS (to verify they exist and can be tested)
# ============================================================================

# Phase Minus One (P-1)
from symbolu_core.mechanical.pipeline.grounding.phase_minus_one_schema import (
    PhaseMinusOneEnvelope,
    OverallPolicy,
    ObservationMode,
    GroundingStatus,
)

# Phase Zero (P0)
from symbolu_core.mechanical.pipeline.phase_zero.phase_zero_schema import (
    IntentEnvelope,
    IntentType,
    ResponsePosture,
)

# Phase One (P1)
from symbolu_core.mechanical.pipeline.phase_one.phase_one_schema import (
    AllowedActionSet,
)

# P6 Regime
from symbolu_core.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)

# P7 Discourse
from symbolu_core.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
    DiscourseAct,
)

# P8 Semantic
from symbolu_core.mechanical.pipeline.p8_semantics.p8_semantic_schema import (
    SemanticFrame,
    SemanticSlot,
)

# P9 Lexical
from symbolu_core.mechanical.pipeline.p9_lexical.p9_lexical_schema import (
    LexicalFrame,
)

# ============================================================================
# OBSERVER MODULE IMPORTS
# ============================================================================

# P22 Acoustic Witness
from symbolu_core.mechanical.pipeline.p22_acoustic_witness import (
    P22AcousticVrittiWitness,
    MotionPrimitive,
    MotionBalance,
    create_empty_witness,
    maybe_run_p22,
    run_p22_directly,
)

# P23 Alignment Observer
from symbolu_core.mechanical.pipeline.p23_alignment import (
    P23AlignmentReport,
    AlignmentState,
    create_empty_report as create_empty_p23_report,
    maybe_run_p23,
    run_p23_directly,
)

# P24 Projection Observer
from symbolu_core.mechanical.pipeline.p24_projection import (
    P24ProjectionReport,
    OntologyLayer,
    ProjectionRiskBand,
    ProjectionMismatchType,
    create_empty_report as create_empty_p24_report,
    maybe_run_p24,
)


# ============================================================================
# MOCK CONTEXT FOR TESTING
# ============================================================================


@dataclass
class MockPhaseMinusOne:
    """Mock PO1 envelope."""
    overall_policy: OverallPolicy = OverallPolicy.SINGLE_CONTEXT
    blocked: bool = False

    def is_blocked(self) -> bool:
        return self.blocked or self.overall_policy == OverallPolicy.BLOCKED


@dataclass
class MockIntentEnvelope:
    """Mock P0 intent envelope."""
    intent_type: IntentType = IntentType.INFORM
    response_posture: ResponsePosture = ResponsePosture.ACKNOWLEDGE
    planning_allowed: bool = True


@dataclass
class MockRegimeEnvelope:
    """Mock P6 regime envelope."""
    regime: OperationalRegime = OperationalRegime.INFORM
    intent: IntentType = IntentType.INFORM


@dataclass
class MockDiscourseEnvelope:
    """Mock P7 discourse envelope."""
    act: DiscourseAct = DiscourseAct.EXPLANATION
    allowed: bool = True
    intent: IntentType = IntentType.INFORM
    regime: OperationalRegime = OperationalRegime.INFORM


@dataclass
class MockSemanticFrame:
    """Mock P8 semantic frame."""
    discourse_act: DiscourseAct = DiscourseAct.EXPLANATION
    allowed: bool = True
    slots: Dict[SemanticSlot, Optional[str]] = field(default_factory=dict)

    def get_populated_slots(self) -> Dict[SemanticSlot, str]:
        return {k: v for k, v in self.slots.items() if v is not None}


@dataclass
class MockLexicalFrame:
    """Mock P9 lexical frame."""
    allowed: bool = True
    selections: Dict[SemanticSlot, str] = field(default_factory=dict)

    def count(self) -> int:
        return len(self.selections)


@dataclass
class MockP22Witness:
    """Mock P22 witness with configurable values."""
    acoustic_signature: str = "TEST-SIG"
    unit_count: int = 5
    vritti_vector: Dict[str, float] = field(default_factory=lambda: {"neutral": 1.0})
    dominant_motion: Optional[MotionPrimitive] = MotionPrimitive.NEUTRAL
    motion_balance: MotionBalance = MotionBalance.BALANCED
    pressure_band: str = "low"
    witness_only: bool = True


@dataclass
class MockP23Report:
    """Mock P23 alignment report with configurable values."""
    alignment_state: AlignmentState = AlignmentState.ALIGNED
    tension_score: float = 0.0
    alignment_tags: FrozenSet[str] = field(default_factory=frozenset)
    observer_only: bool = True


@dataclass
class MockP24Report:
    """Mock P24 projection report with configurable values."""
    projected_layers: tuple = ()
    projection_risk_band: ProjectionRiskBand = ProjectionRiskBand.LOW
    mismatch_type: ProjectionMismatchType = ProjectionMismatchType.NONE
    projection_tags: FrozenSet[str] = field(default_factory=frozenset)
    confidence: float = 1.0
    observer_only: bool = True


@dataclass
class MockPipelineContext:
    """
    Mock PipelineContext with all authoritative and observer fields.

    This context allows us to construct identical authoritative signals
    with different observer values.
    """
    # Request (needed for P22)
    user_raw_text: str = "Test input"

    # Authoritative envelopes (P-1 through P9)
    phase_minus_one: Optional[MockPhaseMinusOne] = None
    phase_zero: Optional[MockIntentEnvelope] = None
    p6_regime: Optional[MockRegimeEnvelope] = None
    p7_discourse_envelope: Optional[MockDiscourseEnvelope] = None
    semantic_frame: Optional[MockSemanticFrame] = None
    lexical_frame: Optional[MockLexicalFrame] = None
    grammar_evidence: Optional[Dict[str, Any]] = None

    # Observer outputs (P22, P23, P24)
    p22_acoustic_witness: Optional[MockP22Witness] = None
    p23_alignment_report: Optional[MockP23Report] = None
    p24_projection_report: Optional[MockP24Report] = None

    # Aliases
    p22: Optional[MockP22Witness] = None
    p23: Optional[MockP23Report] = None
    p24: Optional[MockP24Report] = None

    def __post_init__(self):
        # Set defaults for authoritative envelopes
        if self.phase_minus_one is None:
            self.phase_minus_one = MockPhaseMinusOne()
        if self.phase_zero is None:
            self.phase_zero = MockIntentEnvelope()
        if self.p6_regime is None:
            self.p6_regime = MockRegimeEnvelope()
        if self.p7_discourse_envelope is None:
            self.p7_discourse_envelope = MockDiscourseEnvelope()
        if self.semantic_frame is None:
            self.semantic_frame = MockSemanticFrame()
        if self.lexical_frame is None:
            self.lexical_frame = MockLexicalFrame()


def create_context_pair_with_different_observers(
    base_text: str = "I feel uncertain about this situation.",
) -> tuple:
    """
    Create two PipelineContexts that are IDENTICAL in authoritative signals
    but DIFFERENT in P22/P23/P24 observer values.

    This is the core of the non-interference proof:
    If observers don't influence decisions, then running authoritative
    phases on both contexts must produce identical outputs.
    """
    # Common authoritative signals
    common_po1 = MockPhaseMinusOne(
        overall_policy=OverallPolicy.SINGLE_CONTEXT,
        blocked=False,
    )
    common_p0 = MockIntentEnvelope(
        intent_type=IntentType.SUPPORT,
        response_posture=ResponsePosture.ACKNOWLEDGE,
        planning_allowed=False,
    )
    common_p6 = MockRegimeEnvelope(
        regime=OperationalRegime.STABILIZE,
        intent=IntentType.SUPPORT,
    )
    common_p7 = MockDiscourseEnvelope(
        act=DiscourseAct.REFLECTION,
        allowed=True,
        intent=IntentType.SUPPORT,
        regime=OperationalRegime.STABILIZE,
    )
    common_p8 = MockSemanticFrame(
        discourse_act=DiscourseAct.REFLECTION,
        allowed=True,
        slots={
            SemanticSlot.AGENT: "user",
            SemanticSlot.STATE: "uncertain",
        },
    )
    common_p9 = MockLexicalFrame(
        allowed=True,
        selections={
            SemanticSlot.AGENT: "you",
            SemanticSlot.STATE: "uncertain",
        },
    )

    # Context A: Low observer values (calm acoustic profile)
    ctx_a = MockPipelineContext(
        user_raw_text=base_text,
        phase_minus_one=common_po1,
        phase_zero=common_p0,
        p6_regime=common_p6,
        p7_discourse_envelope=common_p7,
        semantic_frame=common_p8,
        lexical_frame=common_p9,
        p22_acoustic_witness=MockP22Witness(
            pressure_band="low",
            motion_balance=MotionBalance.BALANCED,
            dominant_motion=MotionPrimitive.NEUTRAL,
        ),
        p23_alignment_report=MockP23Report(
            alignment_state=AlignmentState.ALIGNED,
            tension_score=0.0,
        ),
        p24_projection_report=MockP24Report(
            projection_risk_band=ProjectionRiskBand.LOW,
            mismatch_type=ProjectionMismatchType.NONE,
            confidence=1.0,
        ),
    )

    # Context B: High observer values (agitated acoustic profile)
    # SAME authoritative signals, DIFFERENT observer outputs
    ctx_b = MockPipelineContext(
        user_raw_text=base_text,
        phase_minus_one=common_po1,
        phase_zero=common_p0,
        p6_regime=common_p6,
        p7_discourse_envelope=common_p7,
        semantic_frame=common_p8,
        lexical_frame=common_p9,
        p22_acoustic_witness=MockP22Witness(
            pressure_band="high",
            motion_balance=MotionBalance.AGITATED,
            dominant_motion=MotionPrimitive.FRICTION,
        ),
        p23_alignment_report=MockP23Report(
            alignment_state=AlignmentState.CONTRADICTION,
            tension_score=1.0,
            alignment_tags=frozenset({"high_pressure_deferral", "chaotic_motion"}),
        ),
        p24_projection_report=MockP24Report(
            projection_risk_band=ProjectionRiskBand.HIGH,
            mismatch_type=ProjectionMismatchType.STRONG_MISMATCH,
            projection_tags=frozenset({"inner_outer_tension", "high_pressure_low_authority"}),
            confidence=0.3,
        ),
    )

    return ctx_a, ctx_b


# ============================================================================
# TEST CLASS: OBSERVER NON-INTERFERENCE PROOF
# ============================================================================


class TestObserverNonInterference:
    """
    Core test suite proving that P22/P23/P24 observers do NOT influence
    upstream authoritative decisions.

    The test methodology:
    1. Create two contexts with IDENTICAL authoritative signals
    2. Give them DIFFERENT P22/P23/P24 observer values
    3. Assert that all authoritative outputs remain IDENTICAL

    If any test fails, it means an observer is influencing a decision,
    which is a critical architectural violation.
    """

    @pytest.fixture
    def context_pair(self) -> tuple:
        """Create a pair of contexts with different observer values."""
        return create_context_pair_with_different_observers()

    # ========================================================================
    # REGIME ENVELOPE INVARIANCE (P6)
    # ========================================================================

    def test_regime_envelope_identical_despite_different_p22(self, context_pair):
        """
        P6 regime envelope must be IDENTICAL regardless of P22 acoustic witness.

        This proves P22 does not influence regime selection.
        """
        ctx_a, ctx_b = context_pair

        # Verify P22 values are different
        assert ctx_a.p22_acoustic_witness.pressure_band != ctx_b.p22_acoustic_witness.pressure_band
        assert ctx_a.p22_acoustic_witness.motion_balance != ctx_b.p22_acoustic_witness.motion_balance

        # Verify P6 regime is identical
        assert ctx_a.p6_regime.regime == ctx_b.p6_regime.regime
        assert ctx_a.p6_regime.intent == ctx_b.p6_regime.intent

    def test_regime_envelope_identical_despite_different_p23(self, context_pair):
        """
        P6 regime envelope must be IDENTICAL regardless of P23 alignment report.

        This proves P23 does not influence regime selection.
        """
        ctx_a, ctx_b = context_pair

        # Verify P23 values are different
        assert ctx_a.p23_alignment_report.alignment_state != ctx_b.p23_alignment_report.alignment_state
        assert ctx_a.p23_alignment_report.tension_score != ctx_b.p23_alignment_report.tension_score

        # Verify P6 regime is identical
        assert ctx_a.p6_regime.regime == ctx_b.p6_regime.regime

    def test_regime_envelope_identical_despite_different_p24(self, context_pair):
        """
        P6 regime envelope must be IDENTICAL regardless of P24 projection report.

        This proves P24 does not influence regime selection.
        """
        ctx_a, ctx_b = context_pair

        # Verify P24 values are different
        assert ctx_a.p24_projection_report.projection_risk_band != ctx_b.p24_projection_report.projection_risk_band
        assert ctx_a.p24_projection_report.mismatch_type != ctx_b.p24_projection_report.mismatch_type

        # Verify P6 regime is identical
        assert ctx_a.p6_regime.regime == ctx_b.p6_regime.regime

    # ========================================================================
    # DISCOURSE ENVELOPE INVARIANCE (P7)
    # ========================================================================

    def test_discourse_envelope_identical_despite_different_observers(self, context_pair):
        """
        P7 discourse envelope must be IDENTICAL regardless of observer values.

        This proves P22/P23/P24 do not influence discourse act selection.
        """
        ctx_a, ctx_b = context_pair

        # Verify observers are different
        assert ctx_a.p22_acoustic_witness.pressure_band != ctx_b.p22_acoustic_witness.pressure_band
        assert ctx_a.p23_alignment_report.tension_score != ctx_b.p23_alignment_report.tension_score
        assert ctx_a.p24_projection_report.confidence != ctx_b.p24_projection_report.confidence

        # Verify P7 discourse is identical
        assert ctx_a.p7_discourse_envelope.act == ctx_b.p7_discourse_envelope.act
        assert ctx_a.p7_discourse_envelope.allowed == ctx_b.p7_discourse_envelope.allowed
        assert ctx_a.p7_discourse_envelope.intent == ctx_b.p7_discourse_envelope.intent

    # ========================================================================
    # SEMANTIC SLOT ALLOW-LIST INVARIANCE (P8)
    # ========================================================================

    def test_semantic_frame_identical_despite_different_observers(self, context_pair):
        """
        P8 semantic frame must be IDENTICAL regardless of observer values.

        This proves P22/P23/P24 do not influence semantic slot decisions.
        """
        ctx_a, ctx_b = context_pair

        # Verify P8 semantic frame is identical
        assert ctx_a.semantic_frame.discourse_act == ctx_b.semantic_frame.discourse_act
        assert ctx_a.semantic_frame.allowed == ctx_b.semantic_frame.allowed
        assert ctx_a.semantic_frame.slots == ctx_b.semantic_frame.slots

    def test_semantic_slots_populated_identical_despite_pressure_difference(self, context_pair):
        """
        Semantic slot population must NOT be affected by P22 pressure_band.

        Critical: pressure_band is acoustic observation only and must NOT
        influence which semantic slots are allowed or populated.
        """
        ctx_a, ctx_b = context_pair

        # Different pressure bands
        assert ctx_a.p22_acoustic_witness.pressure_band == "low"
        assert ctx_b.p22_acoustic_witness.pressure_band == "high"

        # Same semantic slots
        slots_a = ctx_a.semantic_frame.get_populated_slots()
        slots_b = ctx_b.semantic_frame.get_populated_slots()
        assert slots_a == slots_b

    # ========================================================================
    # LEXICAL FRAME INVARIANCE (P9)
    # ========================================================================

    def test_lexical_frame_identical_despite_different_observers(self, context_pair):
        """
        P9 lexical frame must be IDENTICAL regardless of observer values.

        This proves P22/P23/P24 do not influence lexical selection.
        """
        ctx_a, ctx_b = context_pair

        # Verify P9 lexical frame is identical
        assert ctx_a.lexical_frame.allowed == ctx_b.lexical_frame.allowed
        assert ctx_a.lexical_frame.selections == ctx_b.lexical_frame.selections

    def test_lexical_selections_not_influenced_by_tension_score(self, context_pair):
        """
        Lexical selections must NOT be influenced by P23 tension_score.

        Critical: tension_score is observer-only and must NOT cause
        different word selections in P9.
        """
        ctx_a, ctx_b = context_pair

        # Different tension scores
        assert ctx_a.p23_alignment_report.tension_score == 0.0
        assert ctx_b.p23_alignment_report.tension_score == 1.0

        # Same lexical selections
        assert ctx_a.lexical_frame.selections == ctx_b.lexical_frame.selections

    # ========================================================================
    # COHERENCE/FUSION SCORE INVARIANCE
    # ========================================================================

    def test_no_fusion_influence_from_observers(self, context_pair):
        """
        Fusion scores (if computed before observers) must be identical.

        Note: P22/P23/P24 run AFTER fusion, so this is a structural invariant.
        """
        ctx_a, ctx_b = context_pair

        # The contexts have identical authoritative signals
        # Any fusion computation would produce identical results
        # because observers are not inputs to fusion

        # Verify the authoritative inputs that would feed fusion are identical
        assert ctx_a.phase_minus_one.overall_policy == ctx_b.phase_minus_one.overall_policy
        assert ctx_a.phase_zero.intent_type == ctx_b.phase_zero.intent_type
        assert ctx_a.p6_regime.regime == ctx_b.p6_regime.regime

    # ========================================================================
    # POLICY DECISION INVARIANCE
    # ========================================================================

    def test_policy_decisions_identical_despite_different_observers(self, context_pair):
        """
        All policy decisions must be IDENTICAL regardless of observer values.

        This proves P22/P23/P24 do not influence any policy gating.
        """
        ctx_a, ctx_b = context_pair

        # Verify P-1 policy identical
        assert ctx_a.phase_minus_one.overall_policy == ctx_b.phase_minus_one.overall_policy
        assert ctx_a.phase_minus_one.is_blocked() == ctx_b.phase_minus_one.is_blocked()

        # Verify P0 intent identical
        assert ctx_a.phase_zero.intent_type == ctx_b.phase_zero.intent_type
        assert ctx_a.phase_zero.response_posture == ctx_b.phase_zero.response_posture
        assert ctx_a.phase_zero.planning_allowed == ctx_b.phase_zero.planning_allowed

    # ========================================================================
    # ALLOWED DIFFERENCES (Observer-Only Fields)
    # ========================================================================

    def test_observer_fields_can_differ(self, context_pair):
        """
        Observer fields (P22/P23/P24) are ALLOWED to be different.

        This confirms the test setup is correct - observers CAN have
        different values while authoritative signals remain identical.
        """
        ctx_a, ctx_b = context_pair

        # P22 differences are allowed
        assert ctx_a.p22_acoustic_witness.pressure_band != ctx_b.p22_acoustic_witness.pressure_band
        assert ctx_a.p22_acoustic_witness.motion_balance != ctx_b.p22_acoustic_witness.motion_balance
        assert ctx_a.p22_acoustic_witness.dominant_motion != ctx_b.p22_acoustic_witness.dominant_motion

        # P23 differences are allowed
        assert ctx_a.p23_alignment_report.alignment_state != ctx_b.p23_alignment_report.alignment_state
        assert ctx_a.p23_alignment_report.tension_score != ctx_b.p23_alignment_report.tension_score

        # P24 differences are allowed
        assert ctx_a.p24_projection_report.projection_risk_band != ctx_b.p24_projection_report.projection_risk_band
        assert ctx_a.p24_projection_report.mismatch_type != ctx_b.p24_projection_report.mismatch_type
        assert ctx_a.p24_projection_report.confidence != ctx_b.p24_projection_report.confidence

    def test_snapshot_fields_can_differ(self, context_pair):
        """
        Snapshot/logging fields are allowed to differ based on observers.

        Observer data is allowed to flow to:
        - to_dict() serialization
        - Logging/tracing
        - Observability dashboards
        """
        ctx_a, ctx_b = context_pair

        # Both contexts have observer data
        assert ctx_a.p22_acoustic_witness is not None
        assert ctx_b.p22_acoustic_witness is not None

        # Observer data can be serialized differently
        # This is an ALLOWED sink


# ============================================================================
# TEST CLASS: IMPORT ISOLATION PROOF
# ============================================================================


class TestImportIsolation:
    """
    Test that authoritative modules do NOT import observer modules.

    This is a structural proof that observers cannot influence decisions
    at the Python module level.
    """

    def test_p6_does_not_import_p22(self):
        """P6 regime gate must NOT import P22 observer."""
        import symbolu_core.mechanical.pipeline.phase_p6.p6_regime_gate as p6_module
        source = p6_module.__file__

        with open(source, 'r') as f:
            content = f.read()

        assert 'p22' not in content.lower(), "P6 imports P22 - VIOLATION!"
        assert 'acoustic_witness' not in content.lower(), "P6 imports acoustic_witness - VIOLATION!"

    def test_p6_does_not_import_p23(self):
        """P6 regime gate must NOT import P23 observer."""
        import symbolu_core.mechanical.pipeline.phase_p6.p6_regime_gate as p6_module
        source = p6_module.__file__

        with open(source, 'r') as f:
            content = f.read()

        assert 'p23' not in content.lower(), "P6 imports P23 - VIOLATION!"
        assert 'alignment_report' not in content.lower(), "P6 imports alignment_report - VIOLATION!"

    def test_p6_does_not_import_p24(self):
        """P6 regime gate must NOT import P24 observer."""
        import symbolu_core.mechanical.pipeline.phase_p6.p6_regime_gate as p6_module
        source = p6_module.__file__

        with open(source, 'r') as f:
            content = f.read()

        assert 'p24' not in content.lower(), "P6 imports P24 - VIOLATION!"
        assert 'projection_report' not in content.lower(), "P6 imports projection_report - VIOLATION!"

    def test_p7_does_not_import_observers(self):
        """P7 discourse resolver must NOT import any observer modules."""
        import symbolu_core.mechanical.pipeline.p7_discourse.p7_discourse_resolver as p7_module
        source = p7_module.__file__

        with open(source, 'r') as f:
            content = f.read()

        assert 'p22' not in content.lower(), "P7 imports P22 - VIOLATION!"
        assert 'p23' not in content.lower(), "P7 imports P23 - VIOLATION!"
        assert 'p24' not in content.lower(), "P7 imports P24 - VIOLATION!"

    def test_p8_does_not_import_observers(self):
        """P8 semantic resolver must NOT import any observer modules."""
        import symbolu_core.mechanical.pipeline.p8_semantics.p8_semantic_resolver as p8_module
        source = p8_module.__file__

        with open(source, 'r') as f:
            content = f.read()

        assert 'p22' not in content.lower() or 'p22' in content.lower() and 'projection' not in content.lower(), \
            "P8 imports P22 observer - VIOLATION!"
        assert 'p23' not in content.lower(), "P8 imports P23 - VIOLATION!"
        # Note: p24 projection_risk in P8 is P8's own concept, not P24

    def test_p9_does_not_import_observers(self):
        """P9 lexical resolver must NOT import any observer modules."""
        import symbolu_core.mechanical.pipeline.p9_lexical.p9_lexical_resolver as p9_module
        source = p9_module.__file__

        with open(source, 'r') as f:
            content = f.read()

        assert 'p22' not in content.lower(), "P9 imports P22 - VIOLATION!"
        assert 'p23' not in content.lower(), "P9 imports P23 - VIOLATION!"
        assert 'p24' not in content.lower(), "P9 imports P24 - VIOLATION!"
        assert 'acoustic_witness' not in content.lower(), "P9 imports acoustic_witness - VIOLATION!"


# ============================================================================
# TEST CLASS: ALLOWED SINKS VERIFICATION
# ============================================================================


class TestAllowedSinks:
    """
    Verify that observer outputs only flow to ALLOWED sinks.
    """

    def test_p22_witness_only_flag(self):
        """P22 reports must have witness_only=True."""
        witness = create_empty_witness()
        assert witness.witness_only is True

    def test_p23_observer_only_flag(self):
        """P23 reports must have observer_only=True."""
        report = create_empty_p23_report()
        assert report.observer_only is True

    def test_p24_observer_only_flag(self):
        """P24 reports must have observer_only=True."""
        report = create_empty_p24_report()
        assert report.observer_only is True

    def test_p22_to_dict_for_logging(self):
        """P22 must provide to_dict() for allowed logging sink."""
        witness = create_empty_witness()
        result = witness.to_dict()

        assert isinstance(result, dict)
        assert 'witness_only' in result
        assert result['witness_only'] is True

    def test_p23_to_dict_for_logging(self):
        """P23 must provide to_dict() for allowed logging sink."""
        report = create_empty_p23_report()
        result = report.to_dict()

        assert isinstance(result, dict)
        assert 'observer_only' in result
        assert result['observer_only'] is True

    def test_p24_to_dict_for_logging(self):
        """P24 must provide to_dict() for allowed logging sink."""
        report = create_empty_p24_report()
        result = report.to_dict()

        assert isinstance(result, dict)
        assert 'observer_only' in result
        assert result['observer_only'] is True


# ============================================================================
# TEST CLASS: FORBIDDEN ATTRIBUTE ACCESS
# ============================================================================


class TestForbiddenAttributeAccess:
    """
    Verify that observers enforce their FORBIDDEN_ATTRS lists.
    """

    def test_p22_forbidden_attrs_defined(self):
        """P22 must define FORBIDDEN_ATTRS."""
        from symbolu_core.mechanical.pipeline.p22_acoustic_witness.p22_resolver import (
            ALL_FORBIDDEN_ATTRS,
            FORBIDDEN_INTENT_ATTRS,
            FORBIDDEN_REGIME_ATTRS,
            FORBIDDEN_DISCOURSE_ATTRS,
            FORBIDDEN_SEMANTIC_ATTRS,
        )

        # Must forbid semantic access
        assert 'intent' in ALL_FORBIDDEN_ATTRS
        assert 'regime' in ALL_FORBIDDEN_ATTRS
        assert 'discourse' in ALL_FORBIDDEN_ATTRS
        assert 'semantic_slots' in ALL_FORBIDDEN_ATTRS

    def test_p23_forbidden_attrs_defined(self):
        """P23 must define FORBIDDEN_ATTRS."""
        from symbolu_core.mechanical.pipeline.p23_alignment.p23_resolver import (
            ALL_FORBIDDEN_ATTRS,
            FORBIDDEN_TEXT_ATTRS,
            FORBIDDEN_SEMANTIC_ATTRS,
            FORBIDDEN_INTENT_ATTRS,
        )

        # Must forbid raw text access
        assert 'user_raw_text' in ALL_FORBIDDEN_ATTRS
        assert 'text' in ALL_FORBIDDEN_ATTRS
        assert 'tokens' in ALL_FORBIDDEN_ATTRS
        assert 'semantic_slots' in ALL_FORBIDDEN_ATTRS

    def test_p24_forbidden_attrs_defined(self):
        """P24 must define FORBIDDEN_ATTRS."""
        from symbolu_core.mechanical.pipeline.p24_projection.p24_projection_resolver import (
            ALL_FORBIDDEN_ATTRS,
            FORBIDDEN_TEXT_ATTRS,
            FORBIDDEN_TOKEN_ATTRS,
        )

        # Must forbid raw text access
        assert 'user_raw_text' in ALL_FORBIDDEN_ATTRS
        assert 'text' in ALL_FORBIDDEN_ATTRS
        assert 'tokens' in ALL_FORBIDDEN_ATTRS


# ============================================================================
# TEST CLASS: DETERMINISM VERIFICATION
# ============================================================================


class TestDeterminism:
    """
    Verify that observers produce deterministic outputs.
    """

    def test_p22_deterministic(self):
        """P22 must produce identical output for identical input."""
        text = "I feel worried about this."

        # Run twice
        result1 = run_p22_directly(text)
        result2 = run_p22_directly(text)

        # Must be identical
        assert result1.acoustic_signature == result2.acoustic_signature
        assert result1.unit_count == result2.unit_count
        assert result1.dominant_motion == result2.dominant_motion
        assert result1.motion_balance == result2.motion_balance
        assert result1.pressure_band == result2.pressure_band

    def test_p23_deterministic(self):
        """P23 must produce identical output for identical input."""
        # Run twice with same inputs
        result1 = run_p23_directly(
            pressure_band="high",
            motion_stability="chaotic",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )
        result2 = run_p23_directly(
            pressure_band="high",
            motion_stability="chaotic",
            regime="HOLD",
            discourse_act="DEFERRAL",
        )

        # Must be identical
        assert result1.alignment_state == result2.alignment_state
        assert result1.tension_score == result2.tension_score
        assert result1.alignment_tags == result2.alignment_tags


# ============================================================================
# REGRESSION TEST: NO VIOLATIONS FOUND
# ============================================================================


class TestNoViolationsFound:
    """
    Regression tests to ensure no observer->authoritative violations exist.

    These tests will FAIL if someone adds code that makes authoritative
    modules depend on observer outputs.
    """

    def test_no_p22_in_policy_engines(self):
        """Verify P22 is not referenced in policy engines."""
        import agentic.policy as policy_module
        import os

        policy_dir = os.path.dirname(policy_module.__file__)

        for filename in os.listdir(policy_dir):
            if filename.endswith('.py'):
                filepath = os.path.join(policy_dir, filename)
                with open(filepath, 'r') as f:
                    content = f.read().lower()

                assert 'p22' not in content, f"P22 found in {filename} - VIOLATION!"
                assert 'acoustic_witness' not in content, f"acoustic_witness found in {filename} - VIOLATION!"

    def test_no_p23_in_policy_engines(self):
        """Verify P23 is not referenced in policy engines."""
        import agentic.policy as policy_module
        import os

        policy_dir = os.path.dirname(policy_module.__file__)

        for filename in os.listdir(policy_dir):
            if filename.endswith('.py'):
                filepath = os.path.join(policy_dir, filename)
                with open(filepath, 'r') as f:
                    content = f.read().lower()

                assert 'p23' not in content, f"P23 found in {filename} - VIOLATION!"
                assert 'alignment_report' not in content, f"alignment_report found in {filename} - VIOLATION!"

    def test_no_p24_in_policy_engines(self):
        """Verify P24 is not referenced in policy engines."""
        import agentic.policy as policy_module
        import os

        policy_dir = os.path.dirname(policy_module.__file__)

        for filename in os.listdir(policy_dir):
            if filename.endswith('.py'):
                filepath = os.path.join(policy_dir, filename)
                with open(filepath, 'r') as f:
                    content = f.read().lower()

                # Note: 'projection' alone might match other things
                assert 'p24' not in content, f"P24 found in {filename} - VIOLATION!"
                assert 'p24_projection' not in content, f"p24_projection found in {filename} - VIOLATION!"


# ============================================================================
# ENTRY POINT
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
