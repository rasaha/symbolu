"""
Intent Arc Engine v1.0 — Deterministic Multi-Turn Session Trajectory Classification

This module implements a purely rule-based engine for classifying multi-turn
session trajectories into intent arcs. The classification is based on:
- Coherence and temporal arc patterns (SessionSummary)
- Memory events and turning points (SessionMemory)
- Mapper configuration journeys (HRM/LCM/LAM)
- Policy signals and recommended styles (SessionPolicyFlags)
- Session recap trajectory analysis (SessionRecap)

Design Principles:
    1. Zero-LLM (purely rule-based)
    2. Non-invasive (does NOT modify pipeline logic)
    3. Additive (optional analytical layer)
    4. Deterministic (same input → same output)
    5. Session-oriented (uses multi-turn state)

Arc Types:
    - stabilization_arc: Coherence rising, low volatility
    - insight_arc: Breakthrough events + high temporal arc
    - identity_arc: LAM dominance + improving trajectory
    - resolution_arc: Fragmentation → stabilization → breakthrough
    - dissonance_arc: High persona drift + oscillating trajectory
    - avoidance_arc: Flat coherence + low temporal progression
    - expansion_arc: HRM+LAM synergy + strong upward arc
    - chaotic_arc: High mapper volatility + incoherent patterns

Usage:
    from symbolu_extensions.intent.intent_arc_engine import compute_intent_arc

    # Compute intent arc from session components
    intent_arc = compute_intent_arc(
        session_summary=summary,
        session_memory=memory,
        session_policy=policy_flags,
        session_recap=recap,
    )

    # Access arc classification
    print(f"Arc Type: {intent_arc.arc_type}")
    print(f"Confidence: {intent_arc.confidence}")
    print(f"Reasons: {intent_arc.reasons}")
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set

from .arc_types import INTENT_ARCS, ARC_PRIORITY


# ============================================================================
# IntentArc Dataclass
# ============================================================================


@dataclass
class IntentArc:
    """
    Intent arc classification result.

    This dataclass encapsulates the deterministic classification of a
    multi-turn session trajectory into one of 8 canonical arc types.

    Attributes:
        arc_type: One of the INTENT_ARCS keys (e.g., "stabilization_arc")
        confidence: Deterministic confidence score (0.0–1.0)
        reasons: List of symbolic explanation codes (e.g., ["coherence_rising", "low_volatility"])
        turn_count: Number of turns in the session
        domain: Domain context (e.g., "trading", "therapy", "identity")
    """
    arc_type: str
    confidence: float
    reasons: List[str] = field(default_factory=list)
    turn_count: int = 0
    domain: str = "generic"

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize intent arc to JSON-safe dictionary.

        Returns:
            Dictionary with all intent arc fields
        """
        return {
            "arc_type": self.arc_type,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "turn_count": self.turn_count,
            "domain": self.domain,
        }


# ============================================================================
# Main Intent Arc Computation
# ============================================================================


def compute_intent_arc(
    session_summary: Any,
    session_memory: Any,
    session_policy: Optional[Any] = None,
    session_recap: Optional[Any] = None,
) -> IntentArc:
    """
    Compute deterministic intent arc classification from session components.

    This is the main public API for intent arc computation. It applies
    8 rule groups to classify the session trajectory into one of 8 canonical
    arc types, with deterministic confidence scoring and symbolic reasoning.

    Args:
        session_summary: SessionSummary object with aggregated metrics
        session_memory: SessionMemory object with episodic events
        session_policy: Optional SessionPolicyFlags object
        session_recap: Optional SessionRecap object

    Returns:
        IntentArc object with classification, confidence, and reasons

    Rule Groups:
        A. Stabilization Arc - Coherence rising, low volatility
        B. Insight Arc - Breakthrough events + high temporal arc
        C. Identity Arc - LAM dominance + improving trajectory
        D. Resolution Arc - Fragmentation → stabilization → breakthrough
        E. Dissonance Arc - High persona drift + oscillating trajectory
        F. Avoidance Arc - Flat coherence + low temporal progression
        G. Expansion Arc - HRM+LAM synergy + strong upward arc
        H. Chaotic Arc - High mapper volatility + incoherent patterns
    """
    # ========================================================================
    # STEP 1: Extract session data
    # ========================================================================
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Edge case: Not enough turns to classify
    if turn_count < 1:
        return IntentArc(
            arc_type="avoidance_arc",
            confidence=0.30,
            reasons=["insufficient_turns"],
            turn_count=turn_count,
            domain=domain,
        )

    # ========================================================================
    # STEP 2: Apply all 8 rule groups to detect candidate arcs
    # ========================================================================
    candidate_arcs = []

    # Rule Group A: Stabilization Arc
    stabilization_result = _detect_stabilization_arc(session_summary, session_recap)
    if stabilization_result:
        candidate_arcs.append(stabilization_result)

    # Rule Group B: Insight Arc
    insight_result = _detect_insight_arc(session_summary, session_memory, session_recap)
    if insight_result:
        candidate_arcs.append(insight_result)

    # Rule Group C: Identity Arc
    identity_result = _detect_identity_arc(session_summary, session_recap)
    if identity_result:
        candidate_arcs.append(identity_result)

    # Rule Group D: Resolution Arc
    resolution_result = _detect_resolution_arc(session_memory, session_recap)
    if resolution_result:
        candidate_arcs.append(resolution_result)

    # Rule Group E: Dissonance Arc
    dissonance_result = _detect_dissonance_arc(session_summary, session_recap)
    if dissonance_result:
        candidate_arcs.append(dissonance_result)

    # Rule Group F: Avoidance Arc
    avoidance_result = _detect_avoidance_arc(session_summary, session_memory, session_recap)
    if avoidance_result:
        candidate_arcs.append(avoidance_result)

    # Rule Group G: Expansion Arc
    expansion_result = _detect_expansion_arc(session_summary, session_recap)
    if expansion_result:
        candidate_arcs.append(expansion_result)

    # Rule Group H: Chaotic Arc
    chaotic_result = _detect_chaotic_arc(session_summary, session_memory, session_recap)
    if chaotic_result:
        candidate_arcs.append(chaotic_result)

    # ========================================================================
    # STEP 3: Select highest-confidence arc (with deterministic tiebreak)
    # ========================================================================
    if not candidate_arcs:
        # Fallback: No arcs detected, return neutral avoidance arc
        return IntentArc(
            arc_type="avoidance_arc",
            confidence=0.40,
            reasons=["no_arc_detected"],
            turn_count=turn_count,
            domain=domain,
        )

    # Sort by confidence (descending), then by priority (ascending)
    selected_arc = _select_best_arc(candidate_arcs)

    return selected_arc


# ============================================================================
# Rule Group A: Stabilization Arc
# ============================================================================


def _detect_stabilization_arc(
    session_summary: Any,
    session_recap: Optional[Any],
) -> Optional[IntentArc]:
    """
    Detect Stabilization Arc.

    Occurs when:
    - Coherence score rising across last 3+ turns
    - Mapper volatility score < 0.40

    Confidence: 0.70–0.90 depending on slope magnitude

    Args:
        session_summary: SessionSummary object
        session_recap: Optional SessionRecap object

    Returns:
        IntentArc if detected, None otherwise
    """
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    mapper_volatility_score = getattr(session_summary, 'mapper_volatility_score', 0.5)
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Need at least 3 turns to check for rising coherence
    if len(coherence_timeline) < 3:
        return None

    # Check if coherence is rising across last 3 turns
    last_three = coherence_timeline[-3:]
    is_rising = all(last_three[i] < last_three[i + 1] for i in range(len(last_three) - 1))

    # Check mapper volatility
    low_volatility = mapper_volatility_score < 0.40

    if is_rising and low_volatility:
        # Compute confidence based on slope magnitude
        slope = last_three[-1] - last_three[0]
        confidence = 0.70 + min(slope * 0.5, 0.20)  # 0.70 to 0.90

        reasons = ["coherence_rising", "low_volatility"]

        # Add trajectory hint from recap if available
        if session_recap and hasattr(session_recap, 'net_trajectory'):
            if session_recap.net_trajectory == "improving":
                reasons.append("improving_trajectory")

        return IntentArc(
            arc_type="stabilization_arc",
            confidence=confidence,
            reasons=reasons,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group B: Insight Arc
# ============================================================================


def _detect_insight_arc(
    session_summary: Any,
    session_memory: Any,
    session_recap: Optional[Any],
) -> Optional[IntentArc]:
    """
    Detect Insight Arc.

    Occurs when:
    - Breakthrough events exist
    - Temporal arc score >= 0.55
    - Coherence improving at least mildly

    Confidence: 0.75–0.95

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object
        session_recap: Optional SessionRecap object

    Returns:
        IntentArc if detected, None otherwise
    """
    temporal_arc_score = getattr(session_summary, 'temporal_arc_score', 0.5)
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check for breakthrough events
    events = getattr(session_memory, 'events', []) if session_memory else []
    breakthrough_events = [e for e in events if getattr(e, 'event_type', None) == 'breakthrough']

    if not breakthrough_events:
        return None

    # Check temporal arc score
    strong_arc = temporal_arc_score >= 0.55

    # Check if coherence is improving (mildly)
    coherence_improving = False
    if len(coherence_timeline) >= 2:
        delta = coherence_timeline[-1] - coherence_timeline[0]
        coherence_improving = delta >= -0.05  # Allow slight decline

    if strong_arc and coherence_improving:
        # Compute confidence based on temporal arc strength
        confidence = 0.75 + min((temporal_arc_score - 0.55) * 0.5, 0.20)  # 0.75 to 0.95

        reasons = ["breakthrough_detected", "strong_upward_arc"]

        if len(breakthrough_events) > 1:
            reasons.append("multiple_breakthroughs")

        return IntentArc(
            arc_type="insight_arc",
            confidence=confidence,
            reasons=reasons,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group C: Identity Arc
# ============================================================================


def _detect_identity_arc(
    session_summary: Any,
    session_recap: Optional[Any],
) -> Optional[IntentArc]:
    """
    Detect Identity Arc.

    Occurs when:
    - LAM active in latest mapper set
    - Recommended style == "reflective" or "exploratory"
    - Net trajectory == "improving"

    Confidence: 0.60–0.85

    Args:
        session_summary: SessionSummary object
        session_recap: Optional SessionRecap object

    Returns:
        IntentArc if detected, None otherwise
    """
    mapper_sets = getattr(session_summary, 'mapper_sets', [])
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check if LAM is in the last mapper set
    if not mapper_sets:
        return None

    last_mapper_set = mapper_sets[-1] if mapper_sets else set()
    lam_active = "LAM" in last_mapper_set

    if not lam_active:
        return None

    # Check recommended style from recap
    recommended_style = None
    net_trajectory = None
    if session_recap:
        recommended_style = getattr(session_recap, 'recommended_style', None)
        net_trajectory = getattr(session_recap, 'net_trajectory', None)

    # Check if style is reflective or exploratory
    style_match = recommended_style in ["reflective", "exploratory"]

    # Check if trajectory is improving
    trajectory_improving = net_trajectory == "improving"

    if lam_active and (style_match or trajectory_improving):
        # Compute confidence based on conditions met
        confidence = 0.60
        if style_match:
            confidence += 0.10
        if trajectory_improving:
            confidence += 0.15

        reasons = ["lam_active", "identity_exploration"]

        if style_match:
            reasons.append(f"style_{recommended_style}")
        if trajectory_improving:
            reasons.append("improving_trajectory")

        return IntentArc(
            arc_type="identity_arc",
            confidence=confidence,
            reasons=reasons,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group D: Resolution Arc
# ============================================================================


def _detect_resolution_arc(
    session_memory: Any,
    session_recap: Optional[Any],
) -> Optional[IntentArc]:
    """
    Detect Resolution Arc.

    Occurs when:
    - Fragmentation event occurred earlier
    - Stabilization event occurred later
    - Trajectory improving

    Confidence: 0.65–0.90

    Args:
        session_memory: SessionMemory object
        session_recap: Optional SessionRecap object

    Returns:
        IntentArc if detected, None otherwise
    """
    if not session_memory:
        return None

    events = getattr(session_memory, 'events', [])

    # Find fragmentation and stabilization events
    fragmentation_events = [e for e in events if getattr(e, 'event_type', None) == 'fragmentation']
    stabilization_events = [e for e in events if getattr(e, 'event_type', None) == 'stabilization']

    if not fragmentation_events or not stabilization_events:
        return None

    # Check if stabilization occurred after fragmentation
    last_frag_turn = max(getattr(e, 'turn_index', 0) for e in fragmentation_events)
    last_stab_turn = max(getattr(e, 'turn_index', 0) for e in stabilization_events)

    if last_stab_turn <= last_frag_turn:
        return None

    # Check trajectory from recap
    net_trajectory = None
    if session_recap:
        net_trajectory = getattr(session_recap, 'net_trajectory', None)

    trajectory_improving = net_trajectory == "improving"

    # Compute confidence
    confidence = 0.65
    if trajectory_improving:
        confidence += 0.15
    if last_stab_turn - last_frag_turn >= 2:
        confidence += 0.10  # Clear separation between events

    reasons = ["fragmentation_to_stabilization", "recovery_trajectory"]

    if trajectory_improving:
        reasons.append("improving_trajectory")

    # Get domain and turn count from any event
    turn_count = events[-1].turn_index + 1 if events else 0
    domain = "generic"  # Default, could be enhanced

    return IntentArc(
        arc_type="resolution_arc",
        confidence=min(confidence, 0.90),
        reasons=reasons,
        turn_count=turn_count,
        domain=domain,
    )


# ============================================================================
# Rule Group E: Dissonance Arc
# ============================================================================


def _detect_dissonance_arc(
    session_summary: Any,
    session_recap: Optional[Any],
) -> Optional[IntentArc]:
    """
    Detect Dissonance Arc.

    Occurs when:
    - Persona drift score > 0.55
    - Trajectory oscillating or declining

    Confidence: 0.55–0.80

    Args:
        session_summary: SessionSummary object
        session_recap: Optional SessionRecap object

    Returns:
        IntentArc if detected, None otherwise
    """
    persona_drift_score = getattr(session_summary, 'persona_drift_score', 0.5)
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check persona drift
    high_drift = persona_drift_score > 0.55

    if not high_drift:
        return None

    # Check trajectory from recap
    net_trajectory = None
    if session_recap:
        net_trajectory = getattr(session_recap, 'net_trajectory', None)

    trajectory_unstable = net_trajectory in ["oscillating", "declining"]

    if high_drift and trajectory_unstable:
        # Compute confidence based on drift magnitude
        confidence = 0.55 + min((persona_drift_score - 0.55) * 0.5, 0.25)

        reasons = ["high_persona_drift", "trajectory_instability"]

        if net_trajectory == "declining":
            reasons.append("declining_trajectory")
        elif net_trajectory == "oscillating":
            reasons.append("oscillating_trajectory")

        return IntentArc(
            arc_type="dissonance_arc",
            confidence=confidence,
            reasons=reasons,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group F: Avoidance Arc
# ============================================================================


def _detect_avoidance_arc(
    session_summary: Any,
    session_memory: Any,
    session_recap: Optional[Any],
) -> Optional[IntentArc]:
    """
    Detect Avoidance Arc.

    Occurs when:
    - Coherence timeline mostly flat (|Δ| < 0.05)
    - Temporal arc score < 0.40
    - No breakthrough events

    Confidence: 0.50–0.75

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object
        session_recap: Optional SessionRecap object

    Returns:
        IntentArc if detected, None otherwise
    """
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    temporal_arc_score = getattr(session_summary, 'temporal_arc_score', 0.5)
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check coherence flatness
    flat_coherence = False
    if len(coherence_timeline) >= 2:
        delta = abs(coherence_timeline[-1] - coherence_timeline[0])
        flat_coherence = delta < 0.05

    # Check temporal arc
    low_temporal = temporal_arc_score < 0.40

    # Check for breakthrough events
    events = getattr(session_memory, 'events', []) if session_memory else []
    breakthrough_events = [e for e in events if getattr(e, 'event_type', None) == 'breakthrough']
    no_breakthroughs = len(breakthrough_events) == 0

    if flat_coherence and low_temporal and no_breakthroughs:
        # Compute confidence based on how flat and low
        confidence = 0.50 + min((0.40 - temporal_arc_score) * 0.5, 0.25)

        reasons = ["low_temporal_progress", "flat_coherence", "no_breakthroughs"]

        return IntentArc(
            arc_type="avoidance_arc",
            confidence=confidence,
            reasons=reasons,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group G: Expansion Arc
# ============================================================================


def _detect_expansion_arc(
    session_summary: Any,
    session_recap: Optional[Any],
) -> Optional[IntentArc]:
    """
    Detect Expansion Arc.

    Occurs when:
    - HRM + LAM synergy (mapper_sets include both)
    - Temporal arc score strongly rising
    - Coherence improving

    Confidence: 0.70–0.95

    Args:
        session_summary: SessionSummary object
        session_recap: Optional SessionRecap object

    Returns:
        IntentArc if detected, None otherwise
    """
    mapper_sets = getattr(session_summary, 'mapper_sets', [])
    temporal_arc_timeline = getattr(session_summary, 'temporal_arc_timeline', [])
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check for HRM + LAM synergy
    if not mapper_sets:
        return None

    last_mapper_set = mapper_sets[-1] if mapper_sets else set()
    hrm_lam_synergy = "HRM" in last_mapper_set and "LAM" in last_mapper_set

    if not hrm_lam_synergy:
        return None

    # Check temporal arc rising
    temporal_rising = False
    if len(temporal_arc_timeline) >= 2:
        delta = temporal_arc_timeline[-1] - temporal_arc_timeline[0]
        temporal_rising = delta >= 0.10

    # Check coherence improving
    coherence_improving = False
    if len(coherence_timeline) >= 2:
        delta = coherence_timeline[-1] - coherence_timeline[0]
        coherence_improving = delta >= 0.05

    if hrm_lam_synergy and (temporal_rising or coherence_improving):
        # Compute confidence based on conditions met
        confidence = 0.70
        if temporal_rising:
            confidence += 0.15
        if coherence_improving:
            confidence += 0.10

        reasons = ["lam_hrm_synergy", "expanding_context"]

        if temporal_rising:
            reasons.append("strong_upward_arc")
        if coherence_improving:
            reasons.append("coherence_improving")

        return IntentArc(
            arc_type="expansion_arc",
            confidence=min(confidence, 0.95),
            reasons=reasons,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group H: Chaotic Arc
# ============================================================================


def _detect_chaotic_arc(
    session_summary: Any,
    session_memory: Any,
    session_recap: Optional[Any],
) -> Optional[IntentArc]:
    """
    Detect Chaotic Arc.

    Occurs when:
    - Mapper volatility score > 0.55
    - Multiple fragmentation or arc-shift events
    - Coherence unstable

    Confidence: 0.60–0.85

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object
        session_recap: Optional SessionRecap object

    Returns:
        IntentArc if detected, None otherwise
    """
    mapper_volatility_score = getattr(session_summary, 'mapper_volatility_score', 0.5)
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check mapper volatility
    high_volatility = mapper_volatility_score > 0.55

    if not high_volatility:
        return None

    # Check for multiple instability events
    events = getattr(session_memory, 'events', []) if session_memory else []
    instability_events = [
        e for e in events
        if getattr(e, 'event_type', None) in ['fragmentation', 'arc_shift']
    ]
    multiple_instabilities = len(instability_events) >= 2

    # Check coherence stability
    coherence_unstable = False
    if len(coherence_timeline) >= 3:
        # Check for oscillation (ups and downs)
        deltas = [coherence_timeline[i+1] - coherence_timeline[i] for i in range(len(coherence_timeline)-1)]
        sign_changes = sum(1 for i in range(len(deltas)-1) if deltas[i] * deltas[i+1] < 0)
        coherence_unstable = sign_changes >= 2

    if high_volatility and (multiple_instabilities or coherence_unstable):
        # Compute confidence based on volatility magnitude
        confidence = 0.60 + min((mapper_volatility_score - 0.55) * 0.5, 0.25)

        reasons = ["high_volatility"]

        if multiple_instabilities:
            reasons.append("multiple_instability_events")
        if coherence_unstable:
            reasons.append("coherence_oscillating")

        return IntentArc(
            arc_type="chaotic_arc",
            confidence=confidence,
            reasons=reasons,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Arc Selection Algorithm
# ============================================================================


def _select_best_arc(candidate_arcs: List[IntentArc]) -> IntentArc:
    """
    Select the best arc from candidates using deterministic rules.

    Selection Rules:
        1. Choose highest confidence
        2. If tie, use ARC_PRIORITY for deterministic tiebreak

    Args:
        candidate_arcs: List of candidate IntentArc objects

    Returns:
        Best IntentArc based on confidence and priority
    """
    if not candidate_arcs:
        # Should never happen, but return a fallback
        return IntentArc(
            arc_type="avoidance_arc",
            confidence=0.30,
            reasons=["no_candidates"],
        )

    # Sort by confidence (descending), then by priority (ascending)
    def arc_sort_key(arc: IntentArc):
        # Higher confidence = better (negate for ascending sort)
        # Lower priority index = better (no negation needed)
        priority_idx = ARC_PRIORITY.index(arc.arc_type) if arc.arc_type in ARC_PRIORITY else 999
        return (-arc.confidence, priority_idx)

    sorted_arcs = sorted(candidate_arcs, key=arc_sort_key)

    return sorted_arcs[0]


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "IntentArc",
    "compute_intent_arc",
]
