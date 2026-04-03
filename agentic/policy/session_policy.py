"""
Session-Level Coherence Influencers v1.0

This module computes trajectory-aware policy hints based on SessionSummary metrics.

Design Principles:
    - Zero-LLM: Pure rule-based deterministic logic
    - Non-invasive: Does NOT modify pipeline, TTOR, MLCR, mappers, Fusion, DHA, or Renderer
    - Additive: Optional extension layer
    - Deterministic: Same input produces same output

Architecture:
    INPUT: SessionSummary (multi-turn metrics)
    OUTPUT: SessionPolicyFlags (trajectory-aware policy hints)

Usage:
    from agentic.policy.session_policy import compute_session_policy_flags
    from symbolu_core.service.sessions import SessionStore, compute_session_summary

    store = SessionStore()
    session = store.get(session_id)
    summary = compute_session_summary(session)
    flags = compute_session_policy_flags(summary)

    # Use flags for UI hints, recommendations, etc.
    if flags.session_needs_grounding:
        # Recommend concrete, stabilizing responses
        pass
"""

from dataclasses import dataclass
from typing import Optional

from symbolu_core.service.sessions.session_models import SessionSummary


# ============================================================================
# SessionPolicyFlags Schema
# ============================================================================


@dataclass
class SessionPolicyFlags:
    """
    Trajectory-aware policy hints derived from SessionSummary.

    These flags provide advisory recommendations for UI behavior, response
    tone, and user experience adaptations based on multi-turn conversation
    patterns.

    Attributes:
        session_needs_grounding: Conversation is unstable, recommend concrete responses
        session_allow_deep_reflection: User is stable, deeper exploration is safe
        session_is_stable: Coherence is healthy and consistent
        session_is_recovering: Coherence is improving from fragmented state
        session_is_fragmented: Coherence is low, conversation lacks continuity
        session_recommended_style: Suggested response style for this session
            - "grounded": Concrete, stabilizing, practical responses
            - "reflective": Deep, exploratory, philosophical responses
            - "exploratory": Curious, open-ended, discovery-oriented responses
            - "neutral": Balanced, adaptive responses
    """
    session_needs_grounding: bool
    session_allow_deep_reflection: bool
    session_is_stable: bool
    session_is_recovering: bool
    session_is_fragmented: bool
    session_recommended_style: str  # "grounded", "reflective", "exploratory", "neutral"

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "session_needs_grounding": self.session_needs_grounding,
            "session_allow_deep_reflection": self.session_allow_deep_reflection,
            "session_is_stable": self.session_is_stable,
            "session_is_recovering": self.session_is_recovering,
            "session_is_fragmented": self.session_is_fragmented,
            "session_recommended_style": self.session_recommended_style,
        }


# ============================================================================
# Core Policy Computation
# ============================================================================


def compute_session_policy_flags(
    session_summary: Optional[SessionSummary]
) -> Optional[SessionPolicyFlags]:
    """
    Compute trajectory-aware policy flags from SessionSummary.

    This is the main entry point for session policy computation. It applies
    deterministic rules to multi-turn metrics to produce advisory flags.

    Deterministic Rules:
        1. Stability Classification:
           - coherence_score >= 0.70 → stable
           - coherence_score >= 0.45 → recovering
           - coherence_score < 0.45 → fragmented

        2. Grounding Requirement:
           - fragmented OR
           - persona_drift_score > 0.55 OR
           - semantic_stability_score < 0.45
           → needs_grounding = True

        3. Deep Reflection Permission:
           - stable AND
           - temporal_arc_score >= 0.55 AND
           - mapper_volatility_score <= 0.40
           → allow_deep_reflection = True

        4. Recommended Style:
           - needs_grounding → "grounded"
           - allow_deep_reflection → "reflective"
           - recovering AND temporal_arc_score > 0.45 → "exploratory"
           - otherwise → "neutral"

    Args:
        session_summary: SessionSummary with multi-turn metrics
            If None, returns None (no session tracking)

    Returns:
        SessionPolicyFlags with trajectory-aware hints
        None if session_summary is None

    Examples:
        >>> summary = SessionSummary(
        ...     session_id="test",
        ...     total_turns=5,
        ...     coherence_trend=0.75,
        ...     persona_drift_avg=0.30,
        ...     temporal_arc_avg=0.60,
        ...     semantic_stability_score=0.70,
        ...     mapper_volatility_score=0.25
        ... )
        >>> flags = compute_session_policy_flags(summary)
        >>> flags.session_is_stable
        True
        >>> flags.session_allow_deep_reflection
        True
        >>> flags.session_recommended_style
        'reflective'
    """
    # If no session summary, return None (no session tracking)
    if session_summary is None:
        return None

    # Extract metrics from summary (use property aliases for clarity)
    coherence_score = session_summary.coherence_score
    persona_drift_score = session_summary.persona_drift_score
    semantic_stability_score = session_summary.semantic_stability_score
    temporal_arc_score = session_summary.temporal_arc_score
    mapper_volatility_score = session_summary.mapper_volatility_score

    # ========================================================================
    # RULE 1: Stability Classification
    # ========================================================================
    stable = False
    recovering = False
    fragmented = False

    if coherence_score >= 0.70:
        stable = True
    elif coherence_score >= 0.45:
        recovering = True
    else:
        fragmented = True

    # ========================================================================
    # RULE 2: Grounding Requirement
    # ========================================================================
    session_needs_grounding = (
        fragmented
        or persona_drift_score > 0.55
        or semantic_stability_score < 0.45
    )

    # ========================================================================
    # RULE 3: Deep Reflection Permission
    # ========================================================================
    session_allow_deep_reflection = (
        stable
        and temporal_arc_score >= 0.55
        and mapper_volatility_score <= 0.40
    )

    # ========================================================================
    # RULE 4: Recommended Style
    # ========================================================================
    if session_needs_grounding:
        recommended_style = "grounded"
    elif session_allow_deep_reflection:
        recommended_style = "reflective"
    elif recovering and temporal_arc_score > 0.45:
        recommended_style = "exploratory"
    else:
        recommended_style = "neutral"

    # ========================================================================
    # Assemble Flags
    # ========================================================================
    return SessionPolicyFlags(
        session_needs_grounding=session_needs_grounding,
        session_allow_deep_reflection=session_allow_deep_reflection,
        session_is_stable=stable,
        session_is_recovering=recovering,
        session_is_fragmented=fragmented,
        session_recommended_style=recommended_style,
    )


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "SessionPolicyFlags",
    "compute_session_policy_flags",
]
