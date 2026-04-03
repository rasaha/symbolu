"""
P14 - Expression Surface Realizer Implementation

The core realization engine for P14. This module contains all surface
shaping logic for producing the SurfacePlan.

CRITICAL: This realizer is DETERMINISTIC, zero-LLM, no ML.
It produces a PLAN, not final text.

Resolution Rules (Deterministic):
1. HOLD regime -> DEFERRAL_MINIMAL, requires_question=True
2. DE_ESCALATE/STABILIZE/CAREFUL -> GENTLE, hedging REQUIRED
3. REFLECT posture/REFLECTION discourse -> SAFE_REFLECT persona
4. DETACHED + INFORM -> NEUTRAL or FORMAL
5. RELATIONAL mode -> avoid second-person assertions
6. P13 constraints synchronization

Design Principles:
- Deterministic: No LLM calls, no probabilistic thresholds
- Conservative: Stricter behavior when uncertain
- Authority-Respecting: Cannot override PO1-P13 constraints
- Allow-List Only: Only connectors from curated pools
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from symbolu_core.mechanical.pipeline.p14_surface.p14_surface_schema import (
    SurfaceStyle,
    PunctuationPolicy,
    HedgePolicy,
    LengthPolicy,
    PersonaSignalPolicy,
    SurfacePlan,
    P14_VERSION,
    get_deferral_plan,
    build_forbidden_tokens,
    # Connector pools
    DEFERRAL_CONNECTORS,
    REFLECT_CONNECTORS,
    ACK_CONNECTORS,
    CLARIFY_CONNECTORS,
    # Forbidden tokens
    DEFAULT_FORBIDDEN_TOKENS,
    RELATIONAL_FORBIDDEN_TOKENS,
)


# ============================================================================
# CONSTANTS - Regime and Discourse Mappings
# ============================================================================


# Regimes that require DEFERRAL_MINIMAL style
DEFERRAL_REGIMES = frozenset({"HOLD"})

# Regimes that require GENTLE style with hedging
CAREFUL_REGIMES = frozenset({
    "DE_ESCALATE", "STABILIZE", "CAREFUL", "REFLECT"
})

# Regimes that allow NEUTRAL/FORMAL style
INFORM_REGIMES = frozenset({
    "INFORM", "CLARIFY"
})

# Discourse acts that indicate reflection
REFLECTION_DISCOURSE_ACTS = frozenset({
    "REFLECTION",
})

# Discourse acts that indicate acknowledgment
ACK_DISCOURSE_ACTS = frozenset({
    "ACKNOWLEDGMENT",
})

# Discourse acts that indicate question/clarification
QUESTION_DISCOURSE_ACTS = frozenset({
    "QUESTION", "DEFERRAL",
})

# Discourse acts that allow explanation
EXPLANATION_DISCOURSE_ACTS = frozenset({
    "EXPLANATION", "INSTRUCTION",
})

# Grounding modes that restrict second-person assertions
RELATIONAL_GROUNDING_MODES = frozenset({
    "RELATIONAL",
})

# Grounding modes that restrict authority signaling
AUTHORITY_RESTRICTED_MODES = frozenset({
    "REFLEXIVE", "RELATIONAL",
})


# ============================================================================
# STYLE RESOLUTION FUNCTIONS
# ============================================================================


def resolve_style(
    source_regime: str,
    source_discourse_act: str,
    grounding_mode: str,
    p13_allows_emphasis: bool,
) -> SurfaceStyle:
    """
    Resolve the surface style based on regime and discourse context.

    Rules:
    1. HOLD regime -> DEFERRAL_MINIMAL
    2. CAREFUL regimes (DE_ESCALATE, STABILIZE, CAREFUL, REFLECT) -> GENTLE
    3. If P13 disallows emphasis and style would be more expressive -> clamp to GENTLE
    4. INFORM + DETACHED -> NEUTRAL or FORMAL
    5. Otherwise -> MINIMAL (conservative default)

    Returns:
        SurfaceStyle enum value.
    """
    # Rule 1: HOLD regime always DEFERRAL_MINIMAL
    if source_regime in DEFERRAL_REGIMES:
        return SurfaceStyle.DEFERRAL_MINIMAL

    # Rule 2: CAREFUL regimes -> GENTLE
    if source_regime in CAREFUL_REGIMES:
        return SurfaceStyle.GENTLE

    # Rule 4: INFORM regimes + DETACHED grounding -> NEUTRAL or FORMAL
    if source_regime in INFORM_REGIMES:
        if grounding_mode == "DETACHED":
            # FORMAL for EXPLANATION, NEUTRAL otherwise
            if source_discourse_act in EXPLANATION_DISCOURSE_ACTS:
                style = SurfaceStyle.FORMAL
            else:
                style = SurfaceStyle.NEUTRAL
        else:
            # Non-DETACHED under INFORM -> NEUTRAL
            style = SurfaceStyle.NEUTRAL

        # Rule 3: If P13 disallows emphasis, clamp style
        if not p13_allows_emphasis:
            if style in (SurfaceStyle.FORMAL,):
                # FORMAL is acceptable without emphasis
                return style
            # Clamp to NEUTRAL or below
            return SurfaceStyle.NEUTRAL

        return style

    # Rule 5: Conservative default
    return SurfaceStyle.MINIMAL


def resolve_punctuation(
    source_regime: str,
    source_discourse_act: str,
    p13_allows_emphasis: bool,
) -> PunctuationPolicy:
    """
    Resolve the punctuation policy based on regime and P13 constraints.

    Rules:
    1. HOLD regime -> BASIC_PERIODS only
    2. If P13 disallows emphasis -> NO_EXCLAMATION (no !, no ...)
    3. CAREFUL regimes -> BASIC_PERIODS, NO_EXCLAMATION, NO_ELLIPSIS
    4. INFORM regimes -> LIMITED_COMMAS
    5. Otherwise -> BASIC_PERIODS (conservative)

    Returns:
        PunctuationPolicy enum value.
    """
    # Rule 1: HOLD regime -> BASIC_PERIODS
    if source_regime in DEFERRAL_REGIMES:
        return PunctuationPolicy.BASIC_PERIODS

    # Rule 2 & 3: P13 disallows emphasis OR careful regimes
    if not p13_allows_emphasis or source_regime in CAREFUL_REGIMES:
        return PunctuationPolicy.NO_EXCLAMATION

    # Rule 4: INFORM regimes -> LIMITED_COMMAS
    if source_regime in INFORM_REGIMES:
        return PunctuationPolicy.LIMITED_COMMAS

    # Rule 5: Conservative default
    return PunctuationPolicy.BASIC_PERIODS


def resolve_hedging(
    source_regime: str,
    source_discourse_act: str,
    grounding_mode: str,
    has_uncertainty_slot: bool,
) -> HedgePolicy:
    """
    Resolve the hedging policy based on regime and context.

    Rules:
    1. HOLD regime -> NONE (no hedging, just defer)
    2. CAREFUL regimes with non-factual content -> REQUIRED
    3. RELATIONAL mode with STATE about other -> REQUIRED
    4. Presence of UNCERTAINTY slot -> LIGHT
    5. Otherwise -> NONE

    Returns:
        HedgePolicy enum value.
    """
    # Rule 1: HOLD regime -> NONE
    if source_regime in DEFERRAL_REGIMES:
        return HedgePolicy.NONE

    # Rule 2: CAREFUL regimes -> REQUIRED for non-factual
    if source_regime in CAREFUL_REGIMES:
        # Under careful regimes, require hedging for reflections/explanations
        if source_discourse_act in ("REFLECTION", "EXPLANATION"):
            return HedgePolicy.REQUIRED

    # Rule 3: RELATIONAL mode -> REQUIRED (avoid assertions about others)
    if grounding_mode == "RELATIONAL":
        return HedgePolicy.REQUIRED

    # Rule 4: UNCERTAINTY slot present -> LIGHT
    if has_uncertainty_slot:
        return HedgePolicy.LIGHT

    # Rule 5: Default
    return HedgePolicy.NONE


def resolve_length(
    source_regime: str,
    source_discourse_act: str,
    grounding_mode: str,
) -> LengthPolicy:
    """
    Resolve the length policy based on regime and discourse.

    Rules:
    1. HOLD regime -> ONE_SENTENCE
    2. CAREFUL regimes -> ONE_SENTENCE or TWO_SENTENCES_MAX
    3. INFORM + EXPLANATION + DETACHED -> can use BULLETS_MAX_3
    4. Otherwise -> TWO_SENTENCES_MAX (conservative)

    Returns:
        LengthPolicy enum value.
    """
    # Rule 1: HOLD regime -> ONE_SENTENCE
    if source_regime in DEFERRAL_REGIMES:
        return LengthPolicy.ONE_SENTENCE

    # Rule 2: CAREFUL regimes -> limited
    if source_regime in CAREFUL_REGIMES:
        # DE_ESCALATE/STABILIZE -> ONE_SENTENCE
        if source_regime in ("DE_ESCALATE", "STABILIZE"):
            return LengthPolicy.ONE_SENTENCE
        # CAREFUL/REFLECT -> TWO_SENTENCES_MAX
        return LengthPolicy.TWO_SENTENCES_MAX

    # Rule 3: INFORM + EXPLANATION + DETACHED -> bullets allowed
    if source_regime in INFORM_REGIMES:
        if source_discourse_act in EXPLANATION_DISCOURSE_ACTS and grounding_mode == "DETACHED":
            return LengthPolicy.BULLETS_MAX_3
        # INFORM without DETACHED -> TWO_SENTENCES_MAX
        return LengthPolicy.TWO_SENTENCES_MAX

    # Rule 4: Default
    return LengthPolicy.TWO_SENTENCES_MAX


def resolve_persona_signals(
    source_regime: str,
    source_discourse_act: str,
    grounding_mode: str,
) -> PersonaSignalPolicy:
    """
    Resolve the persona signal policy based on context.

    Rules:
    1. HOLD regime -> SAFE_CLARIFY or NONE
    2. REFLECTION discourse -> SAFE_REFLECT
    3. ACKNOWLEDGMENT discourse -> SAFE_ACK
    4. QUESTION/DEFERRAL discourse -> SAFE_CLARIFY
    5. Otherwise -> NONE

    Returns:
        PersonaSignalPolicy enum value.
    """
    # Rule 1: HOLD regime -> SAFE_CLARIFY
    if source_regime in DEFERRAL_REGIMES:
        return PersonaSignalPolicy.SAFE_CLARIFY

    # Rule 2: REFLECTION discourse -> SAFE_REFLECT
    if source_discourse_act in REFLECTION_DISCOURSE_ACTS:
        return PersonaSignalPolicy.SAFE_REFLECT

    # Rule 3: ACKNOWLEDGMENT discourse -> SAFE_ACK
    if source_discourse_act in ACK_DISCOURSE_ACTS:
        return PersonaSignalPolicy.SAFE_ACK

    # Rule 4: QUESTION/DEFERRAL discourse -> SAFE_CLARIFY
    if source_discourse_act in QUESTION_DISCOURSE_ACTS:
        return PersonaSignalPolicy.SAFE_CLARIFY

    # Rule 5: Default
    return PersonaSignalPolicy.NONE


def resolve_allowed_connectors(
    style: SurfaceStyle,
    persona_signals: PersonaSignalPolicy,
    source_regime: str,
    source_discourse_act: str,
) -> Tuple[str, ...]:
    """
    Resolve the allowed connectors based on style and persona.

    Rules:
    1. DEFERRAL_MINIMAL style -> DEFERRAL_CONNECTORS only
    2. SAFE_REFLECT persona -> REFLECT_CONNECTORS
    3. SAFE_ACK persona -> ACK_CONNECTORS
    4. SAFE_CLARIFY persona -> CLARIFY_CONNECTORS
    5. Otherwise -> empty tuple (no connectors allowed)

    CRITICAL: CAUSE connectors ("because", "therefore", "since") are
    NEVER allowed unless P8 CAUSE slot exists AND regime permits.
    Since we default to conservative, we exclude them.

    Returns:
        Tuple of allowed connector strings.
    """
    # Rule 1: DEFERRAL_MINIMAL
    if style == SurfaceStyle.DEFERRAL_MINIMAL:
        return DEFERRAL_CONNECTORS

    # Rules 2-4: Based on persona signals
    if persona_signals == PersonaSignalPolicy.SAFE_REFLECT:
        return REFLECT_CONNECTORS
    elif persona_signals == PersonaSignalPolicy.SAFE_ACK:
        return ACK_CONNECTORS
    elif persona_signals == PersonaSignalPolicy.SAFE_CLARIFY:
        return CLARIFY_CONNECTORS

    # Rule 5: Default - empty (conservative)
    return ()


def resolve_requires_question(
    source_regime: str,
    source_discourse_act: str,
    persona_signals: PersonaSignalPolicy,
) -> bool:
    """
    Resolve whether output must be a question.

    Rules:
    1. HOLD regime -> True (must clarify)
    2. QUESTION discourse -> True
    3. SAFE_CLARIFY persona -> True
    4. Otherwise -> False

    Returns:
        Boolean indicating if question is required.
    """
    # Rule 1: HOLD regime
    if source_regime in DEFERRAL_REGIMES:
        return True

    # Rule 2: QUESTION discourse
    if source_discourse_act == "QUESTION":
        return True

    # Rule 3: SAFE_CLARIFY persona
    if persona_signals == PersonaSignalPolicy.SAFE_CLARIFY:
        return True

    # Rule 4: Default
    return False


# ============================================================================
# MAIN RESOLVER CLASS
# ============================================================================


class P14SurfaceRealizer:
    """
    Expression Surface Realizer.

    This realizer produces a SurfacePlan based on deterministic rules
    applied to upstream phase outputs (PO1-P13).

    CRITICAL: P14 is DETERMINISTIC, zero-LLM, no ML.
    It produces a PLAN, not final text.
    It cannot override PO1-P13 constraints.
    It must be synchronized with P13 safety constraints.

    Usage:
        realizer = P14SurfaceRealizer()
        plan = realizer.realize(ctx)
    """

    def __init__(self) -> None:
        """Initialize the P14 Surface Realizer."""
        pass

    def _get_timestamp_utc(self) -> str:
        """Get current UTC timestamp in ISO-8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def _extract_context_data(self, ctx: Any) -> Dict[str, Any]:
        """
        Extract relevant data from pipeline context.

        This method safely extracts data without modifying the context.
        Returns a dictionary with all needed fields or safe defaults.
        """
        data: Dict[str, Any] = {
            "source_regime": "UNKNOWN",
            "source_discourse_act": "UNKNOWN",
            "grounding_mode": "UNKNOWN",
            "has_uncertainty_slot": False,
            "has_cause_slot": False,
            "p13_allows_emphasis": False,
            # Upstream presence flags
            "has_po1": False,
            "has_po2": False,
            "has_p6": False,
            "has_p7": False,
            "has_p8": False,
            "has_p9": False,
            "has_p13": False,
        }

        # Extract P6 regime
        if hasattr(ctx, 'p6_regime') and ctx.p6_regime is not None:
            data["has_p6"] = True
            data["source_regime"] = ctx.p6_regime.regime.value

        # Extract P7 discourse act
        if hasattr(ctx, 'p7_discourse_envelope') and ctx.p7_discourse_envelope is not None:
            data["has_p7"] = True
            data["source_discourse_act"] = ctx.p7_discourse_envelope.act.value

        # Extract PO1 grounding mode
        if hasattr(ctx, 'phase_minus_one') and ctx.phase_minus_one is not None:
            data["has_po1"] = True
            if ctx.phase_minus_one.selected_primary is not None:
                data["grounding_mode"] = ctx.phase_minus_one.selected_primary.mode.value

        # Extract PO2 intent
        if hasattr(ctx, 'phase_zero') and ctx.phase_zero is not None:
            data["has_po2"] = True

        # Extract P8 semantic frame (check for UNCERTAINTY and CAUSE slots)
        if hasattr(ctx, 'semantic_frame') and ctx.semantic_frame is not None:
            data["has_p8"] = True
            slots = ctx.semantic_frame.slots
            # Check for UNCERTAINTY slot
            for slot in slots:
                if slot.value == "UNCERTAINTY":
                    if slots.get(slot) is not None:
                        data["has_uncertainty_slot"] = True
                elif slot.value == "CAUSE":
                    if slots.get(slot) is not None:
                        data["has_cause_slot"] = True

        # Extract P9 lexical frame
        if hasattr(ctx, 'lexical_frame') and ctx.lexical_frame is not None:
            data["has_p9"] = True

        # Extract P13 safety envelope
        if hasattr(ctx, 'p13_safety_envelope') and ctx.p13_safety_envelope is not None:
            data["has_p13"] = True
            data["p13_allows_emphasis"] = ctx.p13_safety_envelope.allow_emphasis

        return data

    def _check_required_upstream(self, data: Dict[str, Any]) -> List[str]:
        """
        Check if required upstream phases are present.

        Returns list of missing phase names.
        """
        missing = []

        # P6 regime is required
        if not data["has_p6"]:
            missing.append("P6 regime")

        # P7 discourse is recommended but not strictly required
        # P13 is required for safety synchronization
        if not data["has_p13"]:
            missing.append("P13 safety envelope")

        return missing

    def realize(self, ctx: Any) -> Optional[SurfacePlan]:
        """
        Realize the surface plan from pipeline context.

        This method produces a SurfacePlan based on deterministic rules
        applied to upstream phase outputs.

        CRITICAL: P14 is deterministic and cannot override P13.
        If required upstream phases are missing, returns deferral plan.

        Args:
            ctx: Pipeline context with all phase outputs.

        Returns:
            SurfacePlan with surface shaping policies, or None if critical upstream missing.
        """
        # Extract context data
        data = self._extract_context_data(ctx)
        timestamp = self._get_timestamp_utc()

        # Check required upstream phases
        missing = self._check_required_upstream(data)
        if missing:
            # Return deferral plan for missing upstream
            return get_deferral_plan(
                source_regime=data["source_regime"],
                source_discourse_act=data["source_discourse_act"],
                source_grounding_mode=data["grounding_mode"],
                source_p13_allows_emphasis=data["p13_allows_emphasis"],
                timestamp_utc=timestamp,
            )

        # Resolve each policy component
        style = resolve_style(
            data["source_regime"],
            data["source_discourse_act"],
            data["grounding_mode"],
            data["p13_allows_emphasis"],
        )

        punctuation = resolve_punctuation(
            data["source_regime"],
            data["source_discourse_act"],
            data["p13_allows_emphasis"],
        )

        hedging = resolve_hedging(
            data["source_regime"],
            data["source_discourse_act"],
            data["grounding_mode"],
            data["has_uncertainty_slot"],
        )

        length = resolve_length(
            data["source_regime"],
            data["source_discourse_act"],
            data["grounding_mode"],
        )

        persona_signals = resolve_persona_signals(
            data["source_regime"],
            data["source_discourse_act"],
            data["grounding_mode"],
        )

        allowed_connectors = resolve_allowed_connectors(
            style,
            persona_signals,
            data["source_regime"],
            data["source_discourse_act"],
        )

        requires_question = resolve_requires_question(
            data["source_regime"],
            data["source_discourse_act"],
            persona_signals,
        )

        # Build forbidden tokens
        forbidden_tokens = build_forbidden_tokens(
            data["grounding_mode"],
            include_relational=(data["grounding_mode"] == "RELATIONAL"),
        )

        # Build debug info
        debug_info = {
            "resolution_data": {
                "has_po1": data["has_po1"],
                "has_po2": data["has_po2"],
                "has_p6": data["has_p6"],
                "has_p7": data["has_p7"],
                "has_p8": data["has_p8"],
                "has_p9": data["has_p9"],
                "has_p13": data["has_p13"],
                "has_uncertainty_slot": data["has_uncertainty_slot"],
                "has_cause_slot": data["has_cause_slot"],
            },
        }

        # Build plan
        return SurfacePlan(
            style=style,
            punctuation=punctuation,
            hedging=hedging,
            length=length,
            persona_signals=persona_signals,
            allowed_connectors=allowed_connectors,
            forbidden_tokens=forbidden_tokens,
            requires_question=requires_question,
            source_regime=data["source_regime"],
            source_discourse_act=data["source_discourse_act"],
            source_grounding_mode=data["grounding_mode"],
            source_p13_allows_emphasis=data["p13_allows_emphasis"],
            timestamp_utc=timestamp,
            debug=debug_info,
        )


# Public exports
__all__ = [
    # Constants
    "DEFERRAL_REGIMES",
    "CAREFUL_REGIMES",
    "INFORM_REGIMES",
    "REFLECTION_DISCOURSE_ACTS",
    "ACK_DISCOURSE_ACTS",
    "QUESTION_DISCOURSE_ACTS",
    "EXPLANATION_DISCOURSE_ACTS",
    "RELATIONAL_GROUNDING_MODES",
    "AUTHORITY_RESTRICTED_MODES",
    # Resolution functions
    "resolve_style",
    "resolve_punctuation",
    "resolve_hedging",
    "resolve_length",
    "resolve_persona_signals",
    "resolve_allowed_connectors",
    "resolve_requires_question",
    # Realizer class
    "P14SurfaceRealizer",
]
