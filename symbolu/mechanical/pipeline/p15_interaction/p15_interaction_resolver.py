"""
P15 — Interaction Mode Resolver Implementation

Deterministic resolver for P15 interaction mode selection.
Consumes upstream phase outputs and produces an InteractionDirective.

This resolver is:
- Deterministic: No LLM calls, no probabilistic sampling
- Stateless: Each call is independent
- Conservative: Defaults to READ_ONLY when uncertain
- Non-semantic: Does not alter meaning or content
- Non-acoustic: Does not modify acoustic parameters

Resolution Rules (strict, ordered):
1. If ctx.is_blocked → ACK_ONLY
2. If regime == HOLD → READ_ONLY
3. If discourse == DEFERRAL → ACK_ONLY
4. If discourse == QUESTION → CLARIFYING
5. If reflexive + regime in {DE_ESCALATE, STABILIZE} → SUPPORTIVE
6. If detached + discourse == EXPLANATION → INFORMATIVE
7. Fallback → READ_ONLY

Authority Model:
- P15 consumes P6, P7, PO1 outputs (read-only)
- P15 cannot mutate any upstream output
- P15 cannot override HOLD/BLOCKED states
- P15 produces InteractionDirective (read-only)

CRITICAL: P15 determines interaction posture only.
P15 cannot alter wording, acoustics, or meaning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from symbolu.mechanical.pipeline.p15_interaction.p15_interaction_schema import (
    InteractionMode,
    InteractionDirective,
    P15_VERSION,
    get_read_only_directive,
    get_ack_only_directive,
)


# ============================================================================
# REGIME SETS - For rule matching
# ============================================================================


# Regimes that support SUPPORTIVE interaction mode
SUPPORTIVE_REGIMES = frozenset({"DE_ESCALATE", "STABILIZE"})

# Regimes that force READ_ONLY interaction mode
HOLD_REGIMES = frozenset({"HOLD"})

# Discourse acts that force ACK_ONLY interaction mode
DEFERRAL_DISCOURSE_ACTS = frozenset({"DEFERRAL"})

# Discourse acts that enable CLARIFYING interaction mode
QUESTION_DISCOURSE_ACTS = frozenset({"QUESTION"})

# Discourse acts that enable INFORMATIVE interaction mode (with DETACHED grounding)
EXPLANATION_DISCOURSE_ACTS = frozenset({"EXPLANATION"})

# Grounding modes that support SUPPORTIVE interaction
REFLEXIVE_GROUNDING_MODES = frozenset({"REFLEXIVE"})

# Grounding modes that support INFORMATIVE interaction
DETACHED_GROUNDING_MODES = frozenset({"DETACHED"})


# ============================================================================
# HELPER FUNCTIONS - Extract values from context
# ============================================================================


def _get_regime(ctx: Any) -> str:
    """
    Extract operational regime from context.

    Returns "UNKNOWN" if not available.
    """
    if not hasattr(ctx, 'p6_regime') or ctx.p6_regime is None:
        return "UNKNOWN"

    regime_envelope = ctx.p6_regime
    if hasattr(regime_envelope, 'regime'):
        regime = regime_envelope.regime
        if hasattr(regime, 'value'):
            return regime.value
        return str(regime)

    return "UNKNOWN"


def _get_discourse_act(ctx: Any) -> str:
    """
    Extract discourse act from context.

    Returns "UNKNOWN" if not available.
    """
    if not hasattr(ctx, 'p7_discourse_envelope') or ctx.p7_discourse_envelope is None:
        return "UNKNOWN"

    discourse_envelope = ctx.p7_discourse_envelope
    if hasattr(discourse_envelope, 'act'):
        act = discourse_envelope.act
        if hasattr(act, 'value'):
            return act.value
        return str(act)

    return "UNKNOWN"


def _get_grounding_mode(ctx: Any) -> str:
    """
    Extract grounding mode from context (PO1).

    Returns "UNKNOWN" if not available.
    """
    if not hasattr(ctx, 'phase_minus_one') or ctx.phase_minus_one is None:
        return "UNKNOWN"

    po1_envelope = ctx.phase_minus_one
    if hasattr(po1_envelope, 'selected_primary') and po1_envelope.selected_primary is not None:
        primary = po1_envelope.selected_primary
        if hasattr(primary, 'mode'):
            mode = primary.mode
            if hasattr(mode, 'value'):
                return mode.value
            return str(mode)

    return "UNKNOWN"


def _is_blocked(ctx: Any) -> bool:
    """
    Check if any upstream phase has BLOCKED state.

    Checks:
    - PO1 (phase_minus_one) is_blocked()
    - P13 (p13_safety_envelope) is_blocked()
    """
    # Check PO1 blocked state
    if hasattr(ctx, 'phase_minus_one') and ctx.phase_minus_one is not None:
        if hasattr(ctx.phase_minus_one, 'is_blocked'):
            if ctx.phase_minus_one.is_blocked():
                return True

    # Check P13 blocked state
    if hasattr(ctx, 'p13_safety_envelope') and ctx.p13_safety_envelope is not None:
        if hasattr(ctx.p13_safety_envelope, 'is_blocked'):
            if ctx.p13_safety_envelope.is_blocked():
                return True

    return False


# ============================================================================
# P15 INTERACTION RESOLVER CLASS
# ============================================================================


class P15InteractionResolver:
    """
    Deterministic resolver for P15 interaction mode selection.

    This resolver is stateless and deterministic. Each invocation
    produces the same output for the same input.

    Usage:
        resolver = P15InteractionResolver()
        directive = resolver.resolve(ctx)
    """

    def __init__(self) -> None:
        """Initialize the P15 interaction resolver."""
        pass

    def _get_timestamp_utc(self) -> str:
        """Get current UTC timestamp in ISO-8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def resolve(self, ctx: Any) -> InteractionDirective:
        """
        Resolve interaction mode from pipeline context.

        Applies rules in strict order:
        1. If ctx.is_blocked → ACK_ONLY
        2. If regime == HOLD → READ_ONLY
        3. If discourse == DEFERRAL → ACK_ONLY
        4. If discourse == QUESTION → CLARIFYING
        5. If reflexive + regime in {DE_ESCALATE, STABILIZE} → SUPPORTIVE
        6. If detached + discourse == EXPLANATION → INFORMATIVE
        7. Fallback → READ_ONLY

        Args:
            ctx: Pipeline context with phase outputs.

        Returns:
            InteractionDirective with resolved interaction mode.
        """
        timestamp = self._get_timestamp_utc()

        # Extract values from context
        regime = _get_regime(ctx)
        discourse_act = _get_discourse_act(ctx)
        grounding_mode = _get_grounding_mode(ctx)
        blocked = _is_blocked(ctx)

        # Debug information
        debug = {
            "regime": regime,
            "discourse_act": discourse_act,
            "grounding_mode": grounding_mode,
            "blocked_check": blocked,
            "rule_applied": None,
        }

        # Rule 1: If ctx.is_blocked → ACK_ONLY
        if blocked:
            debug["rule_applied"] = "rule_1_blocked"
            return InteractionDirective(
                mode=InteractionMode.ACK_ONLY,
                source_reason="Upstream BLOCKED state detected",
                blocked=True,
                source_regime=regime,
                source_discourse_act=discourse_act,
                source_grounding_mode=grounding_mode,
                timestamp_utc=timestamp,
                debug=debug,
            )

        # Rule 2: If regime == HOLD → READ_ONLY
        if regime in HOLD_REGIMES:
            debug["rule_applied"] = "rule_2_hold_regime"
            return InteractionDirective(
                mode=InteractionMode.READ_ONLY,
                source_reason="HOLD regime requires READ_ONLY interaction",
                blocked=False,
                source_regime=regime,
                source_discourse_act=discourse_act,
                source_grounding_mode=grounding_mode,
                timestamp_utc=timestamp,
                debug=debug,
            )

        # Rule 3: If discourse == DEFERRAL → ACK_ONLY
        if discourse_act in DEFERRAL_DISCOURSE_ACTS:
            debug["rule_applied"] = "rule_3_deferral_discourse"
            return InteractionDirective(
                mode=InteractionMode.ACK_ONLY,
                source_reason="DEFERRAL discourse requires ACK_ONLY interaction",
                blocked=False,
                source_regime=regime,
                source_discourse_act=discourse_act,
                source_grounding_mode=grounding_mode,
                timestamp_utc=timestamp,
                debug=debug,
            )

        # Rule 4: If discourse == QUESTION → CLARIFYING
        if discourse_act in QUESTION_DISCOURSE_ACTS:
            debug["rule_applied"] = "rule_4_question_discourse"
            return InteractionDirective(
                mode=InteractionMode.CLARIFYING,
                source_reason="QUESTION discourse enables CLARIFYING interaction",
                blocked=False,
                source_regime=regime,
                source_discourse_act=discourse_act,
                source_grounding_mode=grounding_mode,
                timestamp_utc=timestamp,
                debug=debug,
            )

        # Rule 5: If reflexive + regime in {DE_ESCALATE, STABILIZE} → SUPPORTIVE
        if grounding_mode in REFLEXIVE_GROUNDING_MODES and regime in SUPPORTIVE_REGIMES:
            debug["rule_applied"] = "rule_5_reflexive_supportive"
            return InteractionDirective(
                mode=InteractionMode.SUPPORTIVE,
                source_reason=f"REFLEXIVE grounding + {regime} regime enables SUPPORTIVE interaction",
                blocked=False,
                source_regime=regime,
                source_discourse_act=discourse_act,
                source_grounding_mode=grounding_mode,
                timestamp_utc=timestamp,
                debug=debug,
            )

        # Rule 6: If detached + discourse == EXPLANATION → INFORMATIVE
        if grounding_mode in DETACHED_GROUNDING_MODES and discourse_act in EXPLANATION_DISCOURSE_ACTS:
            debug["rule_applied"] = "rule_6_detached_explanation"
            return InteractionDirective(
                mode=InteractionMode.INFORMATIVE,
                source_reason="DETACHED grounding + EXPLANATION discourse enables INFORMATIVE interaction",
                blocked=False,
                source_regime=regime,
                source_discourse_act=discourse_act,
                source_grounding_mode=grounding_mode,
                timestamp_utc=timestamp,
                debug=debug,
            )

        # Rule 7: Fallback → READ_ONLY
        debug["rule_applied"] = "rule_7_fallback"
        return InteractionDirective(
            mode=InteractionMode.READ_ONLY,
            source_reason="Fallback to READ_ONLY (no specific rule matched)",
            blocked=False,
            source_regime=regime,
            source_discourse_act=discourse_act,
            source_grounding_mode=grounding_mode,
            timestamp_utc=timestamp,
            debug=debug,
        )


# ============================================================================
# STANDALONE RESOLUTION FUNCTIONS
# ============================================================================


def resolve_interaction_mode(
    regime: str,
    discourse_act: str,
    grounding_mode: str,
    blocked: bool,
) -> InteractionMode:
    """
    Resolve interaction mode from individual parameters.

    Applies rules in strict order:
    1. If blocked → ACK_ONLY
    2. If regime == HOLD → READ_ONLY
    3. If discourse == DEFERRAL → ACK_ONLY
    4. If discourse == QUESTION → CLARIFYING
    5. If reflexive + regime in {DE_ESCALATE, STABILIZE} → SUPPORTIVE
    6. If detached + discourse == EXPLANATION → INFORMATIVE
    7. Fallback → READ_ONLY

    Args:
        regime: Operational regime from P6.
        discourse_act: Discourse act from P7.
        grounding_mode: Grounding mode from PO1.
        blocked: Whether upstream is blocked.

    Returns:
        Resolved InteractionMode.
    """
    # Rule 1: blocked → ACK_ONLY
    if blocked:
        return InteractionMode.ACK_ONLY

    # Rule 2: HOLD → READ_ONLY
    if regime in HOLD_REGIMES:
        return InteractionMode.READ_ONLY

    # Rule 3: DEFERRAL → ACK_ONLY
    if discourse_act in DEFERRAL_DISCOURSE_ACTS:
        return InteractionMode.ACK_ONLY

    # Rule 4: QUESTION → CLARIFYING
    if discourse_act in QUESTION_DISCOURSE_ACTS:
        return InteractionMode.CLARIFYING

    # Rule 5: REFLEXIVE + DE_ESCALATE/STABILIZE → SUPPORTIVE
    if grounding_mode in REFLEXIVE_GROUNDING_MODES and regime in SUPPORTIVE_REGIMES:
        return InteractionMode.SUPPORTIVE

    # Rule 6: DETACHED + EXPLANATION → INFORMATIVE
    if grounding_mode in DETACHED_GROUNDING_MODES and discourse_act in EXPLANATION_DISCOURSE_ACTS:
        return InteractionMode.INFORMATIVE

    # Rule 7: Fallback → READ_ONLY
    return InteractionMode.READ_ONLY


# Public exports
__all__ = [
    # Classes
    "P15InteractionResolver",
    # Standalone functions
    "resolve_interaction_mode",
    # Constants - regime sets
    "SUPPORTIVE_REGIMES",
    "HOLD_REGIMES",
    "DEFERRAL_DISCOURSE_ACTS",
    "QUESTION_DISCOURSE_ACTS",
    "EXPLANATION_DISCOURSE_ACTS",
    "REFLEXIVE_GROUNDING_MODES",
    "DETACHED_GROUNDING_MODES",
]
