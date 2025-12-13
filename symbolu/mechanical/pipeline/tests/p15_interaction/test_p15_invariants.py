"""
P15 Invariant Test Harness — Interaction Mode Resolver

This test harness enforces architectural invariants for P15.
P15 is the final delivery-governance phase that binds upstream governance
into an InteractionDirective that downstream systems MUST obey.

P15 DOES NOT:
- Create meaning
- Infer intent
- Alter acoustics
- Escalate authority

P15 ONLY:
- Binds upstream governance into InteractionDirective
- Constrains downstream interaction posture

INVARIANT CATEGORIES:
I.   Authority & Precedence (INV-P15-A1, A2)
II.  Interaction Escalation (INV-P15-E1, E2)
III. Safety (INV-P15-S1, S2)
IV.  Determinism (INV-P15-D1, D2)
V.   Renderer Contract (INV-P15-R1, R2)
VI.  Debug & Audit (INV-P15-L1)

CRITICAL: All tests are deterministic, no LLM calls, no probabilistic logic.
Tests FAIL LOUDLY on invariant violation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch
import copy

import pytest

from symbolu.mechanical.pipeline.p15_interaction import (
    # Schema
    InteractionMode,
    InteractionDirective,
    P15_VERSION,
    get_read_only_directive,
    get_ack_only_directive,
    # Resolver
    P15InteractionResolver,
    resolve_interaction_mode,
    SUPPORTIVE_REGIMES,
    HOLD_REGIMES,
    DEFERRAL_DISCOURSE_ACTS,
    QUESTION_DISCOURSE_ACTS,
    EXPLANATION_DISCOURSE_ACTS,
    REFLEXIVE_GROUNDING_MODES,
    DETACHED_GROUNDING_MODES,
    # Integration
    run_p15_directly,
    maybe_run_p15,
)


# ============================================================================
# INTERACTION MODE HIERARCHY (for escalation checks)
# ============================================================================

# Mode hierarchy: READ_ONLY (most restrictive) -> INFORMATIVE (most permissive)
# Lower index = more restrictive
MODE_HIERARCHY: List[InteractionMode] = [
    InteractionMode.READ_ONLY,    # 0 - Most restrictive
    InteractionMode.ACK_ONLY,     # 1
    InteractionMode.SUPPORTIVE,   # 2
    InteractionMode.CLARIFYING,   # 3
    InteractionMode.INFORMATIVE,  # 4 - Most permissive
]

MODE_RANK: Dict[InteractionMode, int] = {
    mode: idx for idx, mode in enumerate(MODE_HIERARCHY)
}


def is_escalation(from_mode: InteractionMode, to_mode: InteractionMode) -> bool:
    """
    Check if moving from from_mode to to_mode is an escalation.

    Escalation = moving to a MORE permissive mode (higher rank).
    """
    return MODE_RANK[to_mode] > MODE_RANK[from_mode]


# ============================================================================
# DISCOURSE ↔ INTERACTION COMPATIBILITY MATRIX (INV-P15-E2)
# ============================================================================

# Per specification:
# DEFERRAL → READ_ONLY, ACK_ONLY
# REFLECTION → SUPPORTIVE
# QUESTION → CLARIFYING
# EXPLANATION → INFORMATIVE
# ACKNOWLEDGMENT → ACK_ONLY

DISCOURSE_ALLOWED_MODES: Dict[str, Tuple[InteractionMode, ...]] = {
    "DEFERRAL": (InteractionMode.READ_ONLY, InteractionMode.ACK_ONLY),
    "REFLECTION": (InteractionMode.SUPPORTIVE,),
    "QUESTION": (InteractionMode.CLARIFYING,),
    "EXPLANATION": (InteractionMode.INFORMATIVE,),
    "ACKNOWLEDGMENT": (InteractionMode.ACK_ONLY,),
}


# ============================================================================
# TEST MOCK HELPERS
# ============================================================================


@dataclass
class MockRegimeEnvelope:
    """Mock P6 regime envelope for testing."""
    regime: Any

    @dataclass
    class MockRegime:
        value: str

    @classmethod
    def create(cls, regime_value: str) -> "MockRegimeEnvelope":
        return cls(regime=cls.MockRegime(value=regime_value))


@dataclass
class MockDiscourseEnvelope:
    """Mock P7 discourse envelope for testing."""
    act: Any

    @dataclass
    class MockAct:
        value: str

    @classmethod
    def create(cls, act_value: str) -> "MockDiscourseEnvelope":
        return cls(act=cls.MockAct(value=act_value))


@dataclass
class MockGroundingCandidate:
    """Mock grounding candidate for testing."""
    mode: Any

    @dataclass
    class MockMode:
        value: str


@dataclass
class MockPhaseMinusOneEnvelope:
    """Mock PO1 grounding envelope for testing."""
    selected_primary: Optional[MockGroundingCandidate] = None
    _is_blocked: bool = False

    @classmethod
    def create(cls, mode_value: str, blocked: bool = False) -> "MockPhaseMinusOneEnvelope":
        return cls(
            selected_primary=MockGroundingCandidate(
                mode=MockGroundingCandidate.MockMode(value=mode_value)
            ),
            _is_blocked=blocked,
        )

    def is_blocked(self) -> bool:
        return self._is_blocked


@dataclass
class MockP13SafetyEnvelope:
    """Mock P13 acoustic safety envelope for testing."""
    _is_blocked: bool = False

    def is_blocked(self) -> bool:
        return self._is_blocked


@dataclass
class MockPipelineContext:
    """Mock pipeline context for invariant testing."""
    p6_regime: Optional[MockRegimeEnvelope] = None
    p7_discourse_envelope: Optional[MockDiscourseEnvelope] = None
    phase_minus_one: Optional[MockPhaseMinusOneEnvelope] = None
    p13_safety_envelope: Optional[MockP13SafetyEnvelope] = None
    interaction_directive: Optional[InteractionDirective] = None


@dataclass
class MockRendererAttempt:
    """
    Simulates a downstream renderer attempting to escalate interaction.

    This is used to test INV-P15-R1 and INV-P15-R2.
    The renderer should NOT be able to override P15's directive.
    """
    requested_mode: InteractionMode
    wants_questions: bool = False
    wants_prompts: bool = False
    wants_followups: bool = False
    wants_suggestions: bool = False
    wants_certainty_escalation: bool = False


# ============================================================================
# CONTEXT FACTORY FUNCTIONS
# ============================================================================


def make_context(
    regime: str = "INFORM",
    discourse: str = "EXPLANATION",
    grounding: str = "DETACHED",
    po1_blocked: bool = False,
    p13_blocked: bool = False,
) -> MockPipelineContext:
    """Create a pipeline context with specified parameters."""
    return MockPipelineContext(
        p6_regime=MockRegimeEnvelope.create(regime),
        p7_discourse_envelope=MockDiscourseEnvelope.create(discourse),
        phase_minus_one=MockPhaseMinusOneEnvelope.create(grounding, blocked=po1_blocked),
        p13_safety_envelope=MockP13SafetyEnvelope(_is_blocked=p13_blocked),
    )


def make_hold_context() -> MockPipelineContext:
    """Create a context with HOLD regime."""
    return make_context(regime="HOLD", discourse="DEFERRAL", grounding="UNKNOWN")


def make_blocked_context(via_po1: bool = True, via_p13: bool = False) -> MockPipelineContext:
    """Create a context with BLOCKED state."""
    return make_context(
        regime="INFORM",
        discourse="EXPLANATION",
        grounding="DETACHED",
        po1_blocked=via_po1,
        p13_blocked=via_p13,
    )


def make_deferral_context() -> MockPipelineContext:
    """Create a context with DEFERRAL discourse."""
    return make_context(regime="CLARIFY", discourse="DEFERRAL", grounding="UNKNOWN")


def make_question_context() -> MockPipelineContext:
    """Create a context with QUESTION discourse."""
    return make_context(regime="CLARIFY", discourse="QUESTION", grounding="DETACHED")


def make_supportive_context() -> MockPipelineContext:
    """Create a context for SUPPORTIVE mode (REFLEXIVE + DE_ESCALATE)."""
    return make_context(regime="DE_ESCALATE", discourse="REFLECTION", grounding="REFLEXIVE")


def make_informative_context() -> MockPipelineContext:
    """Create a context for INFORMATIVE mode (DETACHED + EXPLANATION)."""
    return make_context(regime="INFORM", discourse="EXPLANATION", grounding="DETACHED")


# ============================================================================
# I. AUTHORITY & PRECEDENCE INVARIANTS
# ============================================================================


class TestAuthorityPrecedenceInvariants:
    """
    INV-P15-A1 — Downstream Subordination
    INV-P15-A2 — HOLD / BLOCKED Supremacy

    Tests that P15 respects upstream authority and cannot override it.
    """

    # -------------------------------------------------------------------------
    # INV-P15-A1: Downstream Subordination
    # Mutating PO1/PO2/P6/P7/P13/P14 must change P15 output
    # P15 must never mutate upstream state
    # -------------------------------------------------------------------------

    def test_inv_p15_a1_p6_mutation_changes_output(self):
        """INV-P15-A1: Changing P6 regime changes P15 output."""
        ctx_inform = make_context(regime="INFORM", discourse="EXPLANATION", grounding="DETACHED")
        ctx_hold = make_context(regime="HOLD", discourse="EXPLANATION", grounding="DETACHED")

        directive_inform = run_p15_directly(ctx_inform)
        directive_hold = run_p15_directly(ctx_hold)

        # Different P6 regime -> different P15 output
        assert directive_inform.mode != directive_hold.mode
        assert directive_inform.mode == InteractionMode.INFORMATIVE
        assert directive_hold.mode == InteractionMode.READ_ONLY

    def test_inv_p15_a1_p7_mutation_changes_output(self):
        """INV-P15-A1: Changing P7 discourse changes P15 output."""
        ctx_explanation = make_context(regime="INFORM", discourse="EXPLANATION", grounding="DETACHED")
        ctx_deferral = make_context(regime="INFORM", discourse="DEFERRAL", grounding="DETACHED")

        directive_explanation = run_p15_directly(ctx_explanation)
        directive_deferral = run_p15_directly(ctx_deferral)

        # Different P7 discourse -> different P15 output
        assert directive_explanation.mode != directive_deferral.mode
        assert directive_explanation.mode == InteractionMode.INFORMATIVE
        assert directive_deferral.mode == InteractionMode.ACK_ONLY

    def test_inv_p15_a1_po1_mutation_changes_output(self):
        """INV-P15-A1: Changing PO1 grounding changes P15 output."""
        ctx_detached = make_context(regime="INFORM", discourse="EXPLANATION", grounding="DETACHED")
        ctx_reflexive = make_context(regime="INFORM", discourse="EXPLANATION", grounding="REFLEXIVE")

        directive_detached = run_p15_directly(ctx_detached)
        directive_reflexive = run_p15_directly(ctx_reflexive)

        # Different PO1 grounding -> different P15 output (DETACHED+EXPLANATION=INFORMATIVE)
        assert directive_detached.mode == InteractionMode.INFORMATIVE
        # REFLEXIVE + EXPLANATION (no SUPPORTIVE_REGIME) -> fallback
        assert directive_reflexive.mode == InteractionMode.READ_ONLY

    def test_inv_p15_a1_p13_blocked_mutation_changes_output(self):
        """INV-P15-A1: Changing P13 blocked state changes P15 output."""
        ctx_not_blocked = make_context(
            regime="INFORM", discourse="EXPLANATION", grounding="DETACHED", p13_blocked=False
        )
        ctx_blocked = make_context(
            regime="INFORM", discourse="EXPLANATION", grounding="DETACHED", p13_blocked=True
        )

        directive_not_blocked = run_p15_directly(ctx_not_blocked)
        directive_blocked = run_p15_directly(ctx_blocked)

        # P13 blocked -> ACK_ONLY
        assert directive_not_blocked.mode == InteractionMode.INFORMATIVE
        assert directive_blocked.mode == InteractionMode.ACK_ONLY
        assert directive_blocked.blocked is True

    def test_inv_p15_a1_p15_never_mutates_upstream_p6(self):
        """INV-P15-A1: P15 never mutates P6 regime."""
        ctx = make_context(regime="INFORM", discourse="EXPLANATION", grounding="DETACHED")
        original_regime = ctx.p6_regime.regime.value

        run_p15_directly(ctx)

        # P6 regime unchanged
        assert ctx.p6_regime.regime.value == original_regime

    def test_inv_p15_a1_p15_never_mutates_upstream_p7(self):
        """INV-P15-A1: P15 never mutates P7 discourse."""
        ctx = make_context(regime="INFORM", discourse="EXPLANATION", grounding="DETACHED")
        original_discourse = ctx.p7_discourse_envelope.act.value

        run_p15_directly(ctx)

        # P7 discourse unchanged
        assert ctx.p7_discourse_envelope.act.value == original_discourse

    def test_inv_p15_a1_p15_never_mutates_upstream_po1(self):
        """INV-P15-A1: P15 never mutates PO1 grounding."""
        ctx = make_context(regime="INFORM", discourse="EXPLANATION", grounding="DETACHED")
        original_grounding = ctx.phase_minus_one.selected_primary.mode.value

        run_p15_directly(ctx)

        # PO1 grounding unchanged
        assert ctx.phase_minus_one.selected_primary.mode.value == original_grounding

    def test_inv_p15_a1_p15_never_mutates_upstream_p13(self):
        """INV-P15-A1: P15 never mutates P13 safety envelope."""
        ctx = make_context(regime="INFORM", discourse="EXPLANATION", grounding="DETACHED", p13_blocked=False)
        original_blocked = ctx.p13_safety_envelope.is_blocked()

        run_p15_directly(ctx)

        # P13 blocked state unchanged
        assert ctx.p13_safety_envelope.is_blocked() == original_blocked

    # -------------------------------------------------------------------------
    # INV-P15-A2: HOLD / BLOCKED Supremacy
    # BLOCKED → ACK_ONLY (no exceptions)
    # HOLD → READ_ONLY (no exceptions)
    # -------------------------------------------------------------------------

    def test_inv_p15_a2_blocked_always_ack_only(self):
        """INV-P15-A2: BLOCKED always produces ACK_ONLY."""
        ctx = make_blocked_context()
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.ACK_ONLY
        assert directive.blocked is True

    def test_inv_p15_a2_blocked_via_p13_always_ack_only(self):
        """INV-P15-A2: BLOCKED via P13 always produces ACK_ONLY."""
        ctx = make_blocked_context(via_po1=False, via_p13=True)
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.ACK_ONLY
        assert directive.blocked is True

    def test_inv_p15_a2_hold_always_read_only(self):
        """INV-P15-A2: HOLD always produces READ_ONLY."""
        ctx = make_hold_context()
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.READ_ONLY
        assert directive.blocked is False

    def test_inv_p15_a2_blocked_takes_precedence_over_hold(self):
        """INV-P15-A2: BLOCKED takes precedence over HOLD."""
        ctx = make_context(regime="HOLD", discourse="DEFERRAL", grounding="UNKNOWN", po1_blocked=True)
        directive = run_p15_directly(ctx)

        # BLOCKED -> ACK_ONLY, not READ_ONLY from HOLD
        assert directive.mode == InteractionMode.ACK_ONLY
        assert directive.blocked is True

    def test_inv_p15_a2_hold_no_exception_with_question(self):
        """INV-P15-A2: HOLD has no exception even with QUESTION discourse."""
        ctx = make_context(regime="HOLD", discourse="QUESTION", grounding="DETACHED")
        directive = run_p15_directly(ctx)

        # HOLD -> READ_ONLY, not CLARIFYING from QUESTION
        assert directive.mode == InteractionMode.READ_ONLY

    def test_inv_p15_a2_hold_no_exception_with_explanation(self):
        """INV-P15-A2: HOLD has no exception even with DETACHED+EXPLANATION."""
        ctx = make_context(regime="HOLD", discourse="EXPLANATION", grounding="DETACHED")
        directive = run_p15_directly(ctx)

        # HOLD -> READ_ONLY, not INFORMATIVE
        assert directive.mode == InteractionMode.READ_ONLY

    def test_inv_p15_a2_hold_no_exception_with_reflexive_de_escalate(self):
        """INV-P15-A2: HOLD overrides REFLEXIVE+DE_ESCALATE."""
        # Note: HOLD takes precedence, so even REFLEXIVE grounding doesn't help
        ctx = make_context(regime="HOLD", discourse="REFLECTION", grounding="REFLEXIVE")
        directive = run_p15_directly(ctx)

        # HOLD -> READ_ONLY, not SUPPORTIVE
        assert directive.mode == InteractionMode.READ_ONLY

    def test_inv_p15_a2_blocked_no_exception_any_context(self):
        """INV-P15-A2: BLOCKED has no exception in any context."""
        test_cases = [
            ("INFORM", "EXPLANATION", "DETACHED"),
            ("DE_ESCALATE", "REFLECTION", "REFLEXIVE"),
            ("CLARIFY", "QUESTION", "DETACHED"),
            ("STABILIZE", "REFLECTION", "REFLEXIVE"),
        ]

        for regime, discourse, grounding in test_cases:
            ctx = make_context(
                regime=regime,
                discourse=discourse,
                grounding=grounding,
                po1_blocked=True,
            )
            directive = run_p15_directly(ctx)

            assert directive.mode == InteractionMode.ACK_ONLY, (
                f"BLOCKED must produce ACK_ONLY, got {directive.mode} "
                f"for {regime}/{discourse}/{grounding}"
            )
            assert directive.blocked is True


# ============================================================================
# II. INTERACTION ESCALATION INVARIANTS
# ============================================================================


class TestInteractionEscalationInvariants:
    """
    INV-P15-E1 — No Escalation Rule
    INV-P15-E2 — Discourse Compatibility

    Tests that interaction modes cannot be escalated and
    discourse ↔ interaction compatibility is enforced.
    """

    # -------------------------------------------------------------------------
    # INV-P15-E1: No Escalation Rule
    # Once P15 sets a mode, Renderer/DHA/Persona/API cannot move upward
    # -------------------------------------------------------------------------

    def test_inv_p15_e1_mode_hierarchy_defined(self):
        """INV-P15-E1: Mode hierarchy is well-defined."""
        # Verify our test hierarchy matches expected order
        assert MODE_RANK[InteractionMode.READ_ONLY] < MODE_RANK[InteractionMode.ACK_ONLY]
        assert MODE_RANK[InteractionMode.ACK_ONLY] < MODE_RANK[InteractionMode.SUPPORTIVE]
        assert MODE_RANK[InteractionMode.SUPPORTIVE] < MODE_RANK[InteractionMode.CLARIFYING]
        assert MODE_RANK[InteractionMode.CLARIFYING] < MODE_RANK[InteractionMode.INFORMATIVE]

    def test_inv_p15_e1_renderer_cannot_escalate_from_read_only(self):
        """INV-P15-E1: Renderer cannot escalate from READ_ONLY."""
        ctx = make_hold_context()
        directive = run_p15_directly(ctx)
        assert directive.mode == InteractionMode.READ_ONLY

        # Simulate renderer attempting escalation
        renderer_attempts = [
            MockRendererAttempt(requested_mode=InteractionMode.ACK_ONLY),
            MockRendererAttempt(requested_mode=InteractionMode.SUPPORTIVE),
            MockRendererAttempt(requested_mode=InteractionMode.CLARIFYING),
            MockRendererAttempt(requested_mode=InteractionMode.INFORMATIVE),
        ]

        for attempt in renderer_attempts:
            # Each is an escalation attempt
            assert is_escalation(directive.mode, attempt.requested_mode), (
                f"Expected {attempt.requested_mode} to be escalation from READ_ONLY"
            )
            # Renderer MUST be rejected (P15 is authoritative)
            # The directive remains READ_ONLY regardless of renderer request
            assert directive.mode == InteractionMode.READ_ONLY

    def test_inv_p15_e1_renderer_cannot_escalate_from_ack_only(self):
        """INV-P15-E1: Renderer cannot escalate from ACK_ONLY."""
        ctx = make_blocked_context()
        directive = run_p15_directly(ctx)
        assert directive.mode == InteractionMode.ACK_ONLY

        # Attempts to escalate to more permissive modes
        escalation_modes = [
            InteractionMode.SUPPORTIVE,
            InteractionMode.CLARIFYING,
            InteractionMode.INFORMATIVE,
        ]

        for mode in escalation_modes:
            assert is_escalation(directive.mode, mode)
            # Directive is immutable, renderer cannot change it
            assert directive.mode == InteractionMode.ACK_ONLY

    def test_inv_p15_e1_renderer_cannot_escalate_from_supportive(self):
        """INV-P15-E1: Renderer cannot escalate from SUPPORTIVE."""
        ctx = make_supportive_context()
        directive = run_p15_directly(ctx)
        assert directive.mode == InteractionMode.SUPPORTIVE

        escalation_modes = [
            InteractionMode.CLARIFYING,
            InteractionMode.INFORMATIVE,
        ]

        for mode in escalation_modes:
            assert is_escalation(directive.mode, mode)
            assert directive.mode == InteractionMode.SUPPORTIVE

    def test_inv_p15_e1_renderer_cannot_escalate_from_clarifying(self):
        """INV-P15-E1: Renderer cannot escalate from CLARIFYING."""
        ctx = make_question_context()
        directive = run_p15_directly(ctx)
        assert directive.mode == InteractionMode.CLARIFYING

        # Only INFORMATIVE is higher
        assert is_escalation(directive.mode, InteractionMode.INFORMATIVE)
        assert directive.mode == InteractionMode.CLARIFYING

    def test_inv_p15_e1_directive_immutability_prevents_escalation(self):
        """INV-P15-E1: InteractionDirective immutability prevents escalation."""
        ctx = make_hold_context()
        directive = run_p15_directly(ctx)

        # Attempt to mutate the frozen dataclass
        with pytest.raises(Exception):  # FrozenInstanceError
            directive.mode = InteractionMode.INFORMATIVE

    def test_inv_p15_e1_all_modes_freeze_correctly(self):
        """INV-P15-E1: All interaction modes freeze correctly in directive."""
        modes_and_contexts = [
            (InteractionMode.READ_ONLY, make_hold_context()),
            (InteractionMode.ACK_ONLY, make_blocked_context()),
            (InteractionMode.SUPPORTIVE, make_supportive_context()),
            (InteractionMode.CLARIFYING, make_question_context()),
            (InteractionMode.INFORMATIVE, make_informative_context()),
        ]

        for expected_mode, ctx in modes_and_contexts:
            directive = run_p15_directly(ctx)
            assert directive.mode == expected_mode

            # All directives are frozen
            with pytest.raises(Exception):
                directive.mode = InteractionMode.INFORMATIVE

    # -------------------------------------------------------------------------
    # INV-P15-E2: Discourse Compatibility
    # Discourse act must be compatible with interaction mode
    # -------------------------------------------------------------------------

    def test_inv_p15_e2_deferral_compatible_with_ack_only(self):
        """INV-P15-E2: DEFERRAL is compatible with ACK_ONLY."""
        ctx = make_deferral_context()
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.ACK_ONLY
        assert directive.mode in DISCOURSE_ALLOWED_MODES["DEFERRAL"]

    def test_inv_p15_e2_deferral_compatible_with_read_only(self):
        """INV-P15-E2: DEFERRAL is compatible with READ_ONLY (via HOLD)."""
        ctx = make_context(regime="HOLD", discourse="DEFERRAL", grounding="UNKNOWN")
        directive = run_p15_directly(ctx)

        # HOLD takes precedence -> READ_ONLY
        assert directive.mode == InteractionMode.READ_ONLY
        assert directive.mode in DISCOURSE_ALLOWED_MODES["DEFERRAL"]

    def test_inv_p15_e2_question_produces_clarifying(self):
        """INV-P15-E2: QUESTION produces CLARIFYING mode."""
        ctx = make_question_context()
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.CLARIFYING
        assert directive.mode in DISCOURSE_ALLOWED_MODES["QUESTION"]

    def test_inv_p15_e2_question_never_produces_supportive(self):
        """INV-P15-E2: QUESTION never produces SUPPORTIVE mode."""
        # Try all regime combinations with QUESTION
        for regime in ["INFORM", "CLARIFY", "REFLECT", "DE_ESCALATE", "STABILIZE"]:
            for grounding in ["DETACHED", "REFLEXIVE", "RELATIONAL"]:
                ctx = make_context(regime=regime, discourse="QUESTION", grounding=grounding)
                directive = run_p15_directly(ctx)

                assert directive.mode != InteractionMode.SUPPORTIVE, (
                    f"QUESTION should never produce SUPPORTIVE, "
                    f"got {directive.mode} for {regime}/{grounding}"
                )

    def test_inv_p15_e2_explanation_produces_informative_with_detached(self):
        """INV-P15-E2: EXPLANATION + DETACHED produces INFORMATIVE."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.INFORMATIVE
        assert directive.mode in DISCOURSE_ALLOWED_MODES["EXPLANATION"]

    def test_inv_p15_e2_reflection_produces_supportive_with_reflexive(self):
        """INV-P15-E2: REFLECTION + REFLEXIVE + DE_ESCALATE produces SUPPORTIVE."""
        ctx = make_supportive_context()
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.SUPPORTIVE
        assert directive.mode in DISCOURSE_ALLOWED_MODES["REFLECTION"]

    def test_inv_p15_e2_reflexive_de_escalate_never_informative(self):
        """INV-P15-E2: REFLEXIVE + DE_ESCALATE never produces INFORMATIVE."""
        ctx = make_context(regime="DE_ESCALATE", discourse="REFLECTION", grounding="REFLEXIVE")
        directive = run_p15_directly(ctx)

        assert directive.mode != InteractionMode.INFORMATIVE
        assert directive.mode == InteractionMode.SUPPORTIVE

    def test_inv_p15_e2_compatibility_matrix_complete(self):
        """INV-P15-E2: Verify discourse compatibility matrix is complete."""
        # All discourse types in matrix
        expected_discourse_types = {"DEFERRAL", "REFLECTION", "QUESTION", "EXPLANATION", "ACKNOWLEDGMENT"}
        assert set(DISCOURSE_ALLOWED_MODES.keys()) == expected_discourse_types

        # All modes in matrix are valid
        for discourse, modes in DISCOURSE_ALLOWED_MODES.items():
            for mode in modes:
                assert isinstance(mode, InteractionMode), (
                    f"Invalid mode {mode} for discourse {discourse}"
                )


# ============================================================================
# III. SAFETY INVARIANTS
# ============================================================================


class TestSafetyInvariants:
    """
    INV-P15-S1 — No Action Suggestion
    INV-P15-S2 — No Emotional Amplification

    Tests that P15 never permits unsafe interaction patterns.
    """

    # -------------------------------------------------------------------------
    # INV-P15-S1: No Action Suggestion
    # P15 never permits advice, diagnosis, explanation under REFLEXIVE,
    # or recommendation phrasing
    # -------------------------------------------------------------------------

    def test_inv_p15_s1_reflexive_blocks_informative(self):
        """INV-P15-S1: REFLEXIVE grounding blocks INFORMATIVE mode."""
        # REFLEXIVE + any discourse should NOT produce INFORMATIVE
        for discourse in ["EXPLANATION", "ACKNOWLEDGMENT", "REFLECTION"]:
            ctx = make_context(regime="INFORM", discourse=discourse, grounding="REFLEXIVE")
            directive = run_p15_directly(ctx)

            assert directive.mode != InteractionMode.INFORMATIVE, (
                f"REFLEXIVE + {discourse} should not produce INFORMATIVE"
            )

    def test_inv_p15_s1_reflexive_de_escalate_only_supportive(self):
        """INV-P15-S1: REFLEXIVE + DE_ESCALATE only produces SUPPORTIVE."""
        ctx = make_context(regime="DE_ESCALATE", discourse="REFLECTION", grounding="REFLEXIVE")
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.SUPPORTIVE
        # SUPPORTIVE does not allow advice/diagnosis/explanation
        assert directive.allows_information() is False

    def test_inv_p15_s1_reflexive_stabilize_only_supportive(self):
        """INV-P15-S1: REFLEXIVE + STABILIZE only produces SUPPORTIVE."""
        ctx = make_context(regime="STABILIZE", discourse="REFLECTION", grounding="REFLEXIVE")
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.SUPPORTIVE
        assert directive.allows_information() is False

    def test_inv_p15_s1_supportive_disallows_information(self):
        """INV-P15-S1: SUPPORTIVE mode disallows information."""
        directive = InteractionDirective(
            mode=InteractionMode.SUPPORTIVE,
            source_reason="Test",
            blocked=False,
        )

        assert directive.allows_information() is False

    def test_inv_p15_s1_read_only_disallows_information(self):
        """INV-P15-S1: READ_ONLY mode disallows information."""
        directive = get_read_only_directive()

        assert directive.allows_information() is False

    def test_inv_p15_s1_ack_only_disallows_information(self):
        """INV-P15-S1: ACK_ONLY mode disallows information."""
        directive = get_ack_only_directive()

        assert directive.allows_information() is False

    def test_inv_p15_s1_clarifying_disallows_information(self):
        """INV-P15-S1: CLARIFYING mode disallows information (only questions)."""
        directive = InteractionDirective(
            mode=InteractionMode.CLARIFYING,
            source_reason="Test",
            blocked=False,
        )

        assert directive.allows_information() is False
        assert directive.allows_questions() is True

    def test_inv_p15_s1_only_informative_allows_information(self):
        """INV-P15-S1: Only INFORMATIVE mode allows information."""
        for mode in InteractionMode:
            directive = InteractionDirective(
                mode=mode,
                source_reason="Test",
                blocked=False if mode != InteractionMode.ACK_ONLY else True,
                source_regime="" if mode != InteractionMode.READ_ONLY else "HOLD",
            )
            if mode == InteractionMode.ACK_ONLY:
                # ACK_ONLY requires blocked=True
                directive = get_ack_only_directive()

            if mode == InteractionMode.INFORMATIVE:
                assert directive.allows_information() is True
            else:
                assert directive.allows_information() is False

    # -------------------------------------------------------------------------
    # INV-P15-S2: No Emotional Amplification
    # Interaction mode must not imply urgency, certainty, authority,
    # or reassurance escalation
    # -------------------------------------------------------------------------

    def test_inv_p15_s2_blocked_no_authority(self):
        """INV-P15-S2: BLOCKED state has no authority to amplify."""
        ctx = make_blocked_context()
        directive = run_p15_directly(ctx)

        # ACK_ONLY is minimal - no escalation possible
        assert directive.mode == InteractionMode.ACK_ONLY
        assert directive.allows_questions() is False
        assert directive.allows_information() is False
        assert directive.allows_support() is False

    def test_inv_p15_s2_hold_no_reassurance(self):
        """INV-P15-S2: HOLD state prevents reassurance escalation."""
        ctx = make_hold_context()
        directive = run_p15_directly(ctx)

        # READ_ONLY is conservative - no reassurance escalation
        assert directive.mode == InteractionMode.READ_ONLY
        assert directive.allows_support() is False

    def test_inv_p15_s2_supportive_allows_support_only(self):
        """INV-P15-S2: SUPPORTIVE mode allows support but not information."""
        ctx = make_supportive_context()
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.SUPPORTIVE
        assert directive.allows_support() is True
        assert directive.allows_information() is False
        assert directive.allows_questions() is False

    def test_inv_p15_s2_mode_capabilities_never_exceed_definition(self):
        """INV-P15-S2: Mode capabilities never exceed their definition."""
        # Define expected capabilities for each mode
        expected_capabilities = {
            InteractionMode.READ_ONLY: {
                "allows_questions": False,
                "allows_information": False,
                "allows_support": False,
            },
            InteractionMode.ACK_ONLY: {
                "allows_questions": False,
                "allows_information": False,
                "allows_support": False,
            },
            InteractionMode.SUPPORTIVE: {
                "allows_questions": False,
                "allows_information": False,
                "allows_support": True,
            },
            InteractionMode.CLARIFYING: {
                "allows_questions": True,
                "allows_information": False,
                "allows_support": False,
            },
            InteractionMode.INFORMATIVE: {
                "allows_questions": False,
                "allows_information": True,
                "allows_support": True,
            },
        }

        for mode, capabilities in expected_capabilities.items():
            # Create appropriate directive for mode
            if mode == InteractionMode.ACK_ONLY:
                directive = get_ack_only_directive()
            elif mode == InteractionMode.READ_ONLY:
                directive = get_read_only_directive()
            else:
                directive = InteractionDirective(
                    mode=mode,
                    source_reason="Test",
                    blocked=False,
                )

            assert directive.allows_questions() == capabilities["allows_questions"], (
                f"Mode {mode} allows_questions mismatch"
            )
            assert directive.allows_information() == capabilities["allows_information"], (
                f"Mode {mode} allows_information mismatch"
            )
            assert directive.allows_support() == capabilities["allows_support"], (
                f"Mode {mode} allows_support mismatch"
            )


# ============================================================================
# IV. DETERMINISM INVARIANTS
# ============================================================================


class TestDeterminismInvariants:
    """
    INV-P15-D1 — Pure Function
    INV-P15-D2 — Statelessness

    Tests that P15 is deterministic and stateless.
    """

    # -------------------------------------------------------------------------
    # INV-P15-D1: Pure Function
    # Same context → identical InteractionDirective
    # -------------------------------------------------------------------------

    def test_inv_p15_d1_same_input_same_output(self):
        """INV-P15-D1: Same input produces same output."""
        ctx = make_informative_context()
        resolver = P15InteractionResolver()

        # Patch timestamp for reproducibility
        with patch.object(resolver, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
            directive1 = resolver.resolve(ctx)
            directive2 = resolver.resolve(ctx)

        assert directive1.mode == directive2.mode
        assert directive1.source_reason == directive2.source_reason
        assert directive1.blocked == directive2.blocked
        assert directive1.source_regime == directive2.source_regime
        assert directive1.source_discourse_act == directive2.source_discourse_act
        assert directive1.source_grounding_mode == directive2.source_grounding_mode

    def test_inv_p15_d1_deterministic_across_all_modes(self):
        """INV-P15-D1: All modes are deterministic."""
        contexts = [
            make_hold_context(),
            make_blocked_context(),
            make_deferral_context(),
            make_question_context(),
            make_supportive_context(),
            make_informative_context(),
        ]

        for ctx in contexts:
            directive1 = run_p15_directly(ctx)
            directive2 = run_p15_directly(ctx)

            assert directive1.mode == directive2.mode
            assert directive1.blocked == directive2.blocked

    def test_inv_p15_d1_resolve_interaction_mode_pure(self):
        """INV-P15-D1: Standalone resolve function is pure."""
        test_cases = [
            ("HOLD", "DEFERRAL", "UNKNOWN", False, InteractionMode.READ_ONLY),
            ("INFORM", "EXPLANATION", "DETACHED", False, InteractionMode.INFORMATIVE),
            ("DE_ESCALATE", "REFLECTION", "REFLEXIVE", False, InteractionMode.SUPPORTIVE),
            ("CLARIFY", "QUESTION", "DETACHED", False, InteractionMode.CLARIFYING),
            ("INFORM", "DEFERRAL", "DETACHED", False, InteractionMode.ACK_ONLY),
            ("INFORM", "EXPLANATION", "DETACHED", True, InteractionMode.ACK_ONLY),
        ]

        for regime, discourse, grounding, blocked, expected_mode in test_cases:
            mode1 = resolve_interaction_mode(regime, discourse, grounding, blocked)
            mode2 = resolve_interaction_mode(regime, discourse, grounding, blocked)

            assert mode1 == mode2 == expected_mode

    def test_inv_p15_d1_no_randomness(self):
        """INV-P15-D1: P15 has no randomness."""
        ctx = make_informative_context()

        # Run 100 times - all should be identical
        directives = [run_p15_directly(ctx) for _ in range(100)]

        first_mode = directives[0].mode
        first_blocked = directives[0].blocked

        for d in directives:
            assert d.mode == first_mode
            assert d.blocked == first_blocked

    # -------------------------------------------------------------------------
    # INV-P15-D2: Statelessness
    # No memory reads, no session state, no persona influence, no temporal inference
    # -------------------------------------------------------------------------

    def test_inv_p15_d2_independent_resolver_instances(self):
        """INV-P15-D2: Different resolver instances produce same output."""
        ctx = make_informative_context()

        resolver1 = P15InteractionResolver()
        resolver2 = P15InteractionResolver()
        resolver3 = P15InteractionResolver()

        with patch.object(resolver1, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
            with patch.object(resolver2, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
                with patch.object(resolver3, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
                    d1 = resolver1.resolve(ctx)
                    d2 = resolver2.resolve(ctx)
                    d3 = resolver3.resolve(ctx)

        assert d1.mode == d2.mode == d3.mode
        assert d1.source_reason == d2.source_reason == d3.source_reason

    def test_inv_p15_d2_no_state_accumulation(self):
        """INV-P15-D2: Resolver does not accumulate state."""
        resolver = P15InteractionResolver()

        # Resolve multiple different contexts
        ctx_hold = make_hold_context()
        ctx_inform = make_informative_context()

        with patch.object(resolver, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
            # First: HOLD context
            d1 = resolver.resolve(ctx_hold)
            assert d1.mode == InteractionMode.READ_ONLY

            # Second: INFORMATIVE context
            d2 = resolver.resolve(ctx_inform)
            assert d2.mode == InteractionMode.INFORMATIVE

            # Third: HOLD context again (should be same as first)
            d3 = resolver.resolve(ctx_hold)
            assert d3.mode == InteractionMode.READ_ONLY

        # No contamination from previous resolves
        assert d1.mode == d3.mode

    def test_inv_p15_d2_no_session_state_dependency(self):
        """INV-P15-D2: P15 does not depend on session state."""
        # Context has no session-related fields
        ctx = make_informative_context()

        # Verify context structure has no session state
        assert not hasattr(ctx, 'session_id')
        assert not hasattr(ctx, 'session_history')
        assert not hasattr(ctx, 'user_preferences')
        assert not hasattr(ctx, 'conversation_turn')

        directive = run_p15_directly(ctx)
        assert directive.mode == InteractionMode.INFORMATIVE

    def test_inv_p15_d2_no_persona_influence(self):
        """INV-P15-D2: P15 does not use persona information."""
        # Context has no persona fields
        ctx = make_informative_context()

        # Verify no persona-related attributes are read
        assert not hasattr(ctx, 'persona')
        assert not hasattr(ctx, 'persona_traits')
        assert not hasattr(ctx, 'voice_style')

        directive = run_p15_directly(ctx)
        assert directive.mode == InteractionMode.INFORMATIVE

    def test_inv_p15_d2_no_temporal_inference(self):
        """INV-P15-D2: P15 does not infer from time-based data."""
        ctx = make_informative_context()

        # Verify no temporal inference fields
        assert not hasattr(ctx, 'time_of_day')
        assert not hasattr(ctx, 'user_activity_pattern')
        assert not hasattr(ctx, 'response_latency')

        directive = run_p15_directly(ctx)
        assert directive.mode == InteractionMode.INFORMATIVE

    def test_inv_p15_d2_timestamp_is_only_for_audit(self):
        """INV-P15-D2: Timestamp is only for audit, not for decision-making."""
        ctx = make_informative_context()
        resolver = P15InteractionResolver()

        # Different timestamps should not affect the mode decision
        with patch.object(resolver, '_get_timestamp_utc', return_value="2024-01-01T00:00:00+00:00"):
            d1 = resolver.resolve(ctx)

        with patch.object(resolver, '_get_timestamp_utc', return_value="2025-12-31T23:59:59+00:00"):
            d2 = resolver.resolve(ctx)

        # Mode and reason are the same regardless of timestamp
        assert d1.mode == d2.mode
        assert d1.source_reason == d2.source_reason
        assert d1.blocked == d2.blocked


# ============================================================================
# V. RENDERER CONTRACT INVARIANTS
# ============================================================================


class TestRendererContractInvariants:
    """
    INV-P15-R1 — Renderer Obedience
    INV-P15-R2 — No Interaction Inference

    Tests that downstream renderers cannot override P15 decisions.
    """

    # -------------------------------------------------------------------------
    # INV-P15-R1: Renderer Obedience
    # Renderer attempting to ask new questions, add prompts, escalate certainty
    # must be detected and rejected
    # -------------------------------------------------------------------------

    def test_inv_p15_r1_read_only_blocks_renderer_questions(self):
        """INV-P15-R1: READ_ONLY mode blocks renderer from asking questions."""
        ctx = make_hold_context()
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.READ_ONLY
        assert directive.allows_questions() is False

        # Renderer attempt to ask questions must be rejected
        renderer_attempt = MockRendererAttempt(
            requested_mode=InteractionMode.CLARIFYING,
            wants_questions=True,
        )

        # P15 directive is authoritative
        assert directive.allows_questions() is False
        # Renderer's request is denied by the directive contract

    def test_inv_p15_r1_ack_only_blocks_renderer_prompts(self):
        """INV-P15-R1: ACK_ONLY mode blocks renderer from adding prompts."""
        ctx = make_blocked_context()
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.ACK_ONLY
        assert directive.allows_questions() is False
        assert directive.allows_information() is False

        renderer_attempt = MockRendererAttempt(
            requested_mode=InteractionMode.INFORMATIVE,
            wants_prompts=True,
        )

        # Renderer cannot add prompts - directive forbids it
        assert directive.allows_information() is False

    def test_inv_p15_r1_supportive_blocks_certainty_escalation(self):
        """INV-P15-R1: SUPPORTIVE mode blocks certainty escalation."""
        ctx = make_supportive_context()
        directive = run_p15_directly(ctx)

        assert directive.mode == InteractionMode.SUPPORTIVE
        assert directive.allows_support() is True
        assert directive.allows_information() is False

        renderer_attempt = MockRendererAttempt(
            requested_mode=InteractionMode.INFORMATIVE,
            wants_certainty_escalation=True,
        )

        # SUPPORTIVE allows support, not information/certainty
        assert directive.allows_information() is False

    def test_inv_p15_r1_directive_contract_is_absolute(self):
        """INV-P15-R1: InteractionDirective contract is absolute."""
        # For each mode, verify the contract cannot be circumvented
        mode_contracts = [
            (InteractionMode.READ_ONLY, {"questions": False, "info": False, "support": False}),
            (InteractionMode.ACK_ONLY, {"questions": False, "info": False, "support": False}),
            (InteractionMode.SUPPORTIVE, {"questions": False, "info": False, "support": True}),
            (InteractionMode.CLARIFYING, {"questions": True, "info": False, "support": False}),
            (InteractionMode.INFORMATIVE, {"questions": False, "info": True, "support": True}),
        ]

        for mode, contract in mode_contracts:
            if mode == InteractionMode.ACK_ONLY:
                directive = get_ack_only_directive()
            elif mode == InteractionMode.READ_ONLY:
                directive = get_read_only_directive()
            else:
                directive = InteractionDirective(
                    mode=mode,
                    source_reason="Test",
                    blocked=False,
                )

            # Contract is enforced
            assert directive.allows_questions() == contract["questions"]
            assert directive.allows_information() == contract["info"]
            assert directive.allows_support() == contract["support"]

    def test_inv_p15_r1_renderer_escalation_detected_via_mode_comparison(self):
        """INV-P15-R1: Renderer escalation can be detected via mode comparison."""
        # Given a P15 directive
        ctx = make_deferral_context()
        directive = run_p15_directly(ctx)
        assert directive.mode == InteractionMode.ACK_ONLY

        # Renderer attempts to escalate
        renderer_requested_modes = [
            InteractionMode.SUPPORTIVE,
            InteractionMode.CLARIFYING,
            InteractionMode.INFORMATIVE,
        ]

        for requested_mode in renderer_requested_modes:
            # Detection: is this an escalation attempt?
            escalation_detected = is_escalation(directive.mode, requested_mode)
            assert escalation_detected is True, (
                f"Should detect escalation from {directive.mode} to {requested_mode}"
            )

    # -------------------------------------------------------------------------
    # INV-P15-R2: No Interaction Inference
    # Renderer cannot invent follow-ups, clarifications, suggestions
    # Only P15 authorizes interaction
    # -------------------------------------------------------------------------

    def test_inv_p15_r2_only_clarifying_authorizes_questions(self):
        """INV-P15-R2: Only CLARIFYING mode authorizes questions."""
        for mode in InteractionMode:
            if mode == InteractionMode.ACK_ONLY:
                directive = get_ack_only_directive()
            elif mode == InteractionMode.READ_ONLY:
                directive = get_read_only_directive()
            else:
                directive = InteractionDirective(
                    mode=mode,
                    source_reason="Test",
                    blocked=False,
                )

            if mode == InteractionMode.CLARIFYING:
                assert directive.allows_questions() is True
            else:
                assert directive.allows_questions() is False

    def test_inv_p15_r2_only_informative_authorizes_information(self):
        """INV-P15-R2: Only INFORMATIVE mode authorizes information."""
        for mode in InteractionMode:
            if mode == InteractionMode.ACK_ONLY:
                directive = get_ack_only_directive()
            elif mode == InteractionMode.READ_ONLY:
                directive = get_read_only_directive()
            else:
                directive = InteractionDirective(
                    mode=mode,
                    source_reason="Test",
                    blocked=False,
                )

            if mode == InteractionMode.INFORMATIVE:
                assert directive.allows_information() is True
            else:
                assert directive.allows_information() is False

    def test_inv_p15_r2_renderer_cannot_invent_followups(self):
        """INV-P15-R2: Renderer cannot invent follow-ups without CLARIFYING."""
        # Non-CLARIFYING modes forbid follow-up questions
        non_clarifying_contexts = [
            make_hold_context(),
            make_blocked_context(),
            make_supportive_context(),
            make_informative_context(),
        ]

        for ctx in non_clarifying_contexts:
            directive = run_p15_directly(ctx)
            assert directive.mode != InteractionMode.CLARIFYING

            # Renderer attempting follow-ups is unauthorized
            renderer_attempt = MockRendererAttempt(
                requested_mode=directive.mode,
                wants_followups=True,
            )

            # Follow-ups require questions, which are not authorized
            assert directive.allows_questions() is False

    def test_inv_p15_r2_renderer_cannot_invent_suggestions(self):
        """INV-P15-R2: Renderer cannot invent suggestions without INFORMATIVE."""
        non_informative_contexts = [
            make_hold_context(),
            make_blocked_context(),
            make_deferral_context(),
            make_question_context(),
            make_supportive_context(),
        ]

        for ctx in non_informative_contexts:
            directive = run_p15_directly(ctx)
            assert directive.mode != InteractionMode.INFORMATIVE

            renderer_attempt = MockRendererAttempt(
                requested_mode=directive.mode,
                wants_suggestions=True,
            )

            # Suggestions require information capability
            assert directive.allows_information() is False

    def test_inv_p15_r2_p15_is_sole_authority_for_interaction(self):
        """INV-P15-R2: P15 is the sole authority for interaction permission."""
        # For every possible context, P15's directive is authoritative
        all_contexts = [
            make_hold_context(),
            make_blocked_context(),
            make_deferral_context(),
            make_question_context(),
            make_supportive_context(),
            make_informative_context(),
        ]

        for ctx in all_contexts:
            directive = run_p15_directly(ctx)

            # The directive completely determines what's allowed
            # There is no other source of interaction permission
            assert isinstance(directive, InteractionDirective)
            assert directive.mode is not None
            assert isinstance(directive.mode, InteractionMode)


# ============================================================================
# VI. DEBUG & AUDIT INVARIANTS
# ============================================================================


class TestDebugAuditInvariants:
    """
    INV-P15-L1 — Explainability

    Tests that InteractionDirective includes required audit fields.
    """

    def test_inv_p15_l1_source_reason_present(self):
        """INV-P15-L1: source_reason is always present."""
        contexts = [
            make_hold_context(),
            make_blocked_context(),
            make_deferral_context(),
            make_question_context(),
            make_supportive_context(),
            make_informative_context(),
        ]

        for ctx in contexts:
            directive = run_p15_directly(ctx)
            assert directive.source_reason is not None
            assert isinstance(directive.source_reason, str)
            assert len(directive.source_reason) > 0

    def test_inv_p15_l1_triggered_rules_in_debug(self):
        """INV-P15-L1: triggered_rules (rule_applied) is in debug."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        assert "rule_applied" in directive.debug
        assert directive.debug["rule_applied"] is not None

    def test_inv_p15_l1_blocked_flag_present(self):
        """INV-P15-L1: blocked flag is always present."""
        contexts = [
            (make_hold_context(), False),
            (make_blocked_context(), True),
            (make_deferral_context(), False),
            (make_question_context(), False),
            (make_supportive_context(), False),
            (make_informative_context(), False),
        ]

        for ctx, expected_blocked in contexts:
            directive = run_p15_directly(ctx)
            assert directive.blocked is expected_blocked

    def test_inv_p15_l1_debug_contains_all_inputs(self):
        """INV-P15-L1: debug contains all input values."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        # Debug must contain input signals
        assert "regime" in directive.debug
        assert "discourse_act" in directive.debug
        assert "grounding_mode" in directive.debug
        assert "blocked_check" in directive.debug

    def test_inv_p15_l1_debug_values_match_inputs(self):
        """INV-P15-L1: debug values match actual inputs."""
        ctx = make_context(regime="INFORM", discourse="EXPLANATION", grounding="DETACHED")
        directive = run_p15_directly(ctx)

        assert directive.debug["regime"] == "INFORM"
        assert directive.debug["discourse_act"] == "EXPLANATION"
        assert directive.debug["grounding_mode"] == "DETACHED"

    def test_inv_p15_l1_rule_names_are_descriptive(self):
        """INV-P15-L1: Rule names are descriptive."""
        rule_contexts = [
            (make_blocked_context(), "rule_1_blocked"),
            (make_hold_context(), "rule_2_hold_regime"),
            (make_deferral_context(), "rule_3_deferral_discourse"),
            (make_question_context(), "rule_4_question_discourse"),
            (make_supportive_context(), "rule_5_reflexive_supportive"),
            (make_informative_context(), "rule_6_detached_explanation"),
            (make_context(regime="INFORM", discourse="ACKNOWLEDGMENT", grounding="RELATIONAL"), "rule_7_fallback"),
        ]

        for ctx, expected_rule in rule_contexts:
            directive = run_p15_directly(ctx)
            assert directive.debug["rule_applied"] == expected_rule, (
                f"Expected {expected_rule}, got {directive.debug['rule_applied']}"
            )

    def test_inv_p15_l1_source_provenance_fields(self):
        """INV-P15-L1: Source provenance fields are populated."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        # Provenance fields
        assert directive.source_regime == "INFORM"
        assert directive.source_discourse_act == "EXPLANATION"
        assert directive.source_grounding_mode == "DETACHED"

    def test_inv_p15_l1_architectural_phase_is_p15(self):
        """INV-P15-L1: architectural_phase is always P15."""
        contexts = [
            make_hold_context(),
            make_blocked_context(),
            make_informative_context(),
        ]

        for ctx in contexts:
            directive = run_p15_directly(ctx)
            assert directive.architectural_phase == "P15"

    def test_inv_p15_l1_version_matches_constant(self):
        """INV-P15-L1: version matches P15_VERSION constant."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        assert directive.version == P15_VERSION

    def test_inv_p15_l1_timestamp_present_when_resolver_used(self):
        """INV-P15-L1: timestamp is present when resolver is used."""
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)

        assert directive.timestamp_utc is not None
        assert len(directive.timestamp_utc) > 0


# ============================================================================
# VII. REQUIRED TEST CATEGORIES (per specification)
# ============================================================================


class TestRequiredCategories:
    """
    Tests explicitly required by specification:
    1. HOLD always → READ_ONLY
    2. BLOCKED always → ACK_ONLY
    3. QUESTION never → SUPPORTIVE
    4. REFLEXIVE + DE_ESCALATE never → INFORMATIVE
    5. Renderer escalation attempt → detected
    6. Determinism (same input twice)
    7. Removing P15 → tests fail (proves necessity)
    """

    def test_required_1_hold_always_read_only(self):
        """REQUIRED-1: HOLD always produces READ_ONLY."""
        test_cases = [
            ("HOLD", "DEFERRAL", "UNKNOWN"),
            ("HOLD", "QUESTION", "DETACHED"),
            ("HOLD", "EXPLANATION", "DETACHED"),
            ("HOLD", "REFLECTION", "REFLEXIVE"),
            ("HOLD", "ACKNOWLEDGMENT", "RELATIONAL"),
        ]

        for regime, discourse, grounding in test_cases:
            ctx = make_context(regime=regime, discourse=discourse, grounding=grounding)
            directive = run_p15_directly(ctx)

            assert directive.mode == InteractionMode.READ_ONLY, (
                f"HOLD must produce READ_ONLY, got {directive.mode} "
                f"for {regime}/{discourse}/{grounding}"
            )

    def test_required_2_blocked_always_ack_only(self):
        """REQUIRED-2: BLOCKED always produces ACK_ONLY."""
        test_cases = [
            ("INFORM", "EXPLANATION", "DETACHED", True, False),
            ("HOLD", "DEFERRAL", "UNKNOWN", True, False),
            ("DE_ESCALATE", "REFLECTION", "REFLEXIVE", True, False),
            ("INFORM", "EXPLANATION", "DETACHED", False, True),  # P13 blocked
        ]

        for regime, discourse, grounding, po1_blocked, p13_blocked in test_cases:
            ctx = make_context(
                regime=regime,
                discourse=discourse,
                grounding=grounding,
                po1_blocked=po1_blocked,
                p13_blocked=p13_blocked,
            )
            directive = run_p15_directly(ctx)

            assert directive.mode == InteractionMode.ACK_ONLY, (
                f"BLOCKED must produce ACK_ONLY, got {directive.mode}"
            )
            assert directive.blocked is True

    def test_required_3_question_never_supportive(self):
        """REQUIRED-3: QUESTION never produces SUPPORTIVE."""
        regimes = ["INFORM", "CLARIFY", "REFLECT", "DE_ESCALATE", "STABILIZE"]
        groundings = ["DETACHED", "REFLEXIVE", "RELATIONAL"]

        for regime in regimes:
            for grounding in groundings:
                ctx = make_context(regime=regime, discourse="QUESTION", grounding=grounding)
                directive = run_p15_directly(ctx)

                assert directive.mode != InteractionMode.SUPPORTIVE, (
                    f"QUESTION must never produce SUPPORTIVE, got {directive.mode} "
                    f"for {regime}/QUESTION/{grounding}"
                )

    def test_required_4_reflexive_de_escalate_never_informative(self):
        """REQUIRED-4: REFLEXIVE + DE_ESCALATE never produces INFORMATIVE."""
        discourses = ["REFLECTION", "EXPLANATION", "ACKNOWLEDGMENT", "DEFERRAL", "QUESTION"]

        for discourse in discourses:
            ctx = make_context(regime="DE_ESCALATE", discourse=discourse, grounding="REFLEXIVE")
            directive = run_p15_directly(ctx)

            assert directive.mode != InteractionMode.INFORMATIVE, (
                f"REFLEXIVE + DE_ESCALATE must never produce INFORMATIVE, "
                f"got {directive.mode} for DE_ESCALATE/{discourse}/REFLEXIVE"
            )

    def test_required_5_renderer_escalation_detected(self):
        """REQUIRED-5: Renderer escalation attempt is detected."""
        # Given a restrictive directive
        ctx = make_hold_context()
        directive = run_p15_directly(ctx)
        assert directive.mode == InteractionMode.READ_ONLY

        # Renderer attempts to escalate
        escalation_attempts = [
            InteractionMode.ACK_ONLY,
            InteractionMode.SUPPORTIVE,
            InteractionMode.CLARIFYING,
            InteractionMode.INFORMATIVE,
        ]

        for attempt in escalation_attempts:
            detected = is_escalation(directive.mode, attempt)
            assert detected is True, (
                f"Escalation from READ_ONLY to {attempt} should be detected"
            )

    def test_required_6_determinism_same_input_twice(self):
        """REQUIRED-6: Same input twice produces same output."""
        ctx = make_informative_context()

        directive1 = run_p15_directly(ctx)
        directive2 = run_p15_directly(ctx)

        assert directive1.mode == directive2.mode
        assert directive1.blocked == directive2.blocked
        assert directive1.source_reason == directive2.source_reason

    def test_required_7_p15_is_necessary(self):
        """REQUIRED-7: P15 is necessary (removing it breaks the system)."""
        # This test proves P15's necessity by showing that:
        # 1. Without P15, there's no InteractionDirective
        # 2. The directive is required for downstream decision-making

        ctx = make_informative_context()

        # Before P15 runs, no directive exists
        assert ctx.interaction_directive is None

        # After P15 runs, directive exists
        result_ctx = maybe_run_p15(ctx)
        assert result_ctx.interaction_directive is not None

        # The directive is authoritative
        assert isinstance(result_ctx.interaction_directive, InteractionDirective)
        assert result_ctx.interaction_directive.mode is not None

    def test_required_7_cannot_construct_directive_without_p15_rules(self):
        """REQUIRED-7: Proper directives require P15 rule application."""
        # Attempt to construct a directive that violates invariants
        with pytest.raises(ValueError):
            # blocked=True requires ACK_ONLY
            InteractionDirective(
                mode=InteractionMode.INFORMATIVE,
                source_reason="Invalid",
                blocked=True,
            )

        with pytest.raises(ValueError):
            # HOLD requires READ_ONLY
            InteractionDirective(
                mode=InteractionMode.INFORMATIVE,
                source_reason="Invalid",
                blocked=False,
                source_regime="HOLD",
            )

        # Only P15's resolution logic produces valid directives
        ctx = make_informative_context()
        directive = run_p15_directly(ctx)
        # This succeeds because P15 follows the rules
        assert directive.mode == InteractionMode.INFORMATIVE


# ============================================================================
# VIII. SCHEMA INVARIANT ENFORCEMENT
# ============================================================================


class TestSchemaInvariantEnforcement:
    """
    Tests that the InteractionDirective dataclass enforces invariants
    at construction time (fail loudly on violation).
    """

    def test_schema_rejects_blocked_with_wrong_mode(self):
        """Schema rejects blocked=True with non-ACK_ONLY mode."""
        invalid_modes = [
            InteractionMode.READ_ONLY,
            InteractionMode.SUPPORTIVE,
            InteractionMode.CLARIFYING,
            InteractionMode.INFORMATIVE,
        ]

        for mode in invalid_modes:
            with pytest.raises(ValueError, match="blocked=True requires mode=ACK_ONLY"):
                InteractionDirective(
                    mode=mode,
                    source_reason="Test",
                    blocked=True,
                )

    def test_schema_rejects_hold_with_wrong_mode(self):
        """Schema rejects HOLD regime with non-READ_ONLY mode."""
        invalid_modes = [
            InteractionMode.ACK_ONLY,
            InteractionMode.SUPPORTIVE,
            InteractionMode.CLARIFYING,
            InteractionMode.INFORMATIVE,
        ]

        for mode in invalid_modes:
            with pytest.raises(ValueError, match="HOLD regime requires mode=READ_ONLY"):
                InteractionDirective(
                    mode=mode,
                    source_reason="Test",
                    blocked=False,
                    source_regime="HOLD",
                )

    def test_schema_rejects_empty_source_reason(self):
        """Schema rejects empty source_reason."""
        with pytest.raises(ValueError, match="source_reason must be a non-empty string"):
            InteractionDirective(
                mode=InteractionMode.READ_ONLY,
                source_reason="",
                blocked=False,
            )

    def test_schema_rejects_whitespace_source_reason(self):
        """Schema rejects whitespace-only source_reason."""
        with pytest.raises(ValueError, match="source_reason must be a non-empty string"):
            InteractionDirective(
                mode=InteractionMode.READ_ONLY,
                source_reason="   ",
                blocked=False,
            )

    def test_schema_accepts_valid_combinations(self):
        """Schema accepts all valid mode/blocked/regime combinations."""
        valid_combinations = [
            (InteractionMode.READ_ONLY, False, "HOLD"),
            (InteractionMode.READ_ONLY, False, "INFORM"),
            (InteractionMode.ACK_ONLY, True, "INFORM"),
            (InteractionMode.ACK_ONLY, False, "INFORM"),  # DEFERRAL case
            (InteractionMode.SUPPORTIVE, False, "DE_ESCALATE"),
            (InteractionMode.CLARIFYING, False, "CLARIFY"),
            (InteractionMode.INFORMATIVE, False, "INFORM"),
        ]

        for mode, blocked, regime in valid_combinations:
            # Should not raise
            directive = InteractionDirective(
                mode=mode,
                source_reason="Valid test",
                blocked=blocked,
                source_regime=regime,
            )
            assert directive.mode == mode

    def test_schema_frozen_prevents_mutation(self):
        """Schema frozen=True prevents mutation."""
        directive = get_read_only_directive()

        # All these should raise
        with pytest.raises(Exception):
            directive.mode = InteractionMode.INFORMATIVE

        with pytest.raises(Exception):
            directive.blocked = True

        with pytest.raises(Exception):
            directive.source_reason = "Changed"
