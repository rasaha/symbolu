"""
Motivation Flow Engine v1.0 — Deterministic Motivation Driver Classification

This module implements a purely rule-based engine for classifying the motivational
drivers behind multi-turn sessions. The classification is based on:
- SessionSummary metrics (coherence, temporal arc, persona drift, mapper volatility)
- SessionMemory events (breakthrough, fragmentation, stabilization, arc_shift, mapper_flip)
- IntentArc classification (arc types)
- IdentitySignature classification (identity types)
- SessionPolicyFlags (recommended styles, grounding needs)

Design Principles:
    1. Zero-LLM (purely rule-based, deterministic)
    2. Non-invasive (does NOT modify pipeline logic)
    3. Additive (optional analytical layer)
    4. Deterministic (same input → same output)
    5. Session-oriented (uses multi-turn state)

Motivation Types:
    - hope_driven: Upward arc, breakthrough events, improving stability
    - fear_driven: Fragmentation, volatility, defensive mapper patterns
    - avoidance_driven: Flat coherence, suppressed expression, LCM bias
    - expansion_driven: LAM/identity expansion + rising temporal arc
    - stabilization_driven: Coherent stabilization after decline, low volatility
    - overcorrection: Sharp oscillations, rapid mapper flips
    - assertion_driven: Strong symbolic expression, HRM dominance
    - ambiguous_motivation: Fallback for mixed/unclear signals

Usage:
    from agentic.motivation.motivation_engine import compute_motivation_flow

    # Compute motivation profile from session components
    motivation = compute_motivation_flow(
        session_summary=summary,
        session_memory=memory,
        session_policy=policy_flags,
        intent_arc=intent_arc,
        identity_signature=identity_signature,
    )

    # Access motivation classification
    print(f"Motivation Type: {motivation.motivation_type}")
    print(f"Confidence: {motivation.confidence}")
    print(f"Drivers: {motivation.drivers}")
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# ============================================================================
# MotivationProfile Dataclass
# ============================================================================


@dataclass
class MotivationProfile:
    """
    Motivation profile classification result.

    This dataclass encapsulates the deterministic classification of a
    multi-turn session's motivational driver into one of 8 canonical types.

    Attributes:
        motivation_type: One of the 8 motivation types
        confidence: Deterministic confidence score (0.0–1.0)
        drivers: List of rule-based triggers that fired (e.g., ["breakthrough_events", "upward_coherence"])
        markers: List of motivation-related session markers (e.g., ["breakthrough_t3", "coherence_rising"])
        turn_count: Number of turns in the session
        domain: Domain context (e.g., "trading", "therapy", "identity")
    """
    motivation_type: str
    confidence: float
    drivers: List[str] = field(default_factory=list)
    markers: List[str] = field(default_factory=list)
    turn_count: int = 0
    domain: str = "generic"

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize motivation profile to JSON-safe dictionary.

        Returns:
            Dictionary with all motivation profile fields
        """
        return {
            "motivation_type": self.motivation_type,
            "confidence": self.confidence,
            "drivers": self.drivers,
            "markers": self.markers,
            "turn_count": self.turn_count,
            "domain": self.domain,
        }


# ============================================================================
# Main Motivation Flow Computation
# ============================================================================


def compute_motivation_flow(
    session_summary: Any,
    session_memory: Any,
    session_policy: Optional[Any] = None,
    intent_arc: Optional[Any] = None,
    identity_signature: Optional[Any] = None,
) -> MotivationProfile:
    """
    Compute deterministic motivation flow classification from session components.

    This is the main public API for motivation flow computation. It applies
    8 rule groups to classify the session's motivational driver into one of 8
    canonical motivation types, with deterministic confidence scoring.

    Args:
        session_summary: SessionSummary object with aggregated metrics
        session_memory: SessionMemory object with episodic events
        session_policy: Optional SessionPolicyFlags object
        intent_arc: Optional IntentArc object
        identity_signature: Optional IdentitySignature object

    Returns:
        MotivationProfile object with classification, confidence, drivers, and markers

    Rule Groups:
        A. hope_driven: Upward arc, breakthrough events, improving stability
        B. fear_driven: Fragmentation, volatility, defensive mapper patterns
        C. avoidance_driven: Flat coherence, suppressed expression, LCM bias
        D. expansion_driven: LAM/identity expansion + rising temporal arc
        E. stabilization_driven: Coherent stabilization after decline, low volatility
        F. overcorrection: Sharp oscillations, rapid mapper flips
        G. assertion_driven: Strong symbolic expression, HRM dominance
        H. ambiguous_motivation: Ambiguous or mixed signals (fallback)
    """
    # ========================================================================
    # STEP 1: Extract session data
    # ========================================================================
    turn_count = getattr(session_summary, 'turn_count', 0)
    session_domain = getattr(session_summary, 'last_domain', 'generic')

    # Edge case: Not enough turns to classify
    if turn_count < 1:
        return MotivationProfile(
            motivation_type="ambiguous_motivation",
            confidence=0.30,
            drivers=["insufficient_turns"],
            markers=[],
            turn_count=turn_count,
            domain=session_domain,
        )

    # ========================================================================
    # STEP 2: Apply all 8 rule groups to detect candidate motivations
    # ========================================================================
    candidate_motivations = []

    # Rule Group A: hope_driven
    hope_result = _detect_hope_driven(session_summary, session_memory)
    if hope_result:
        candidate_motivations.append(hope_result)

    # Rule Group B: fear_driven
    fear_result = _detect_fear_driven(session_summary, session_memory, intent_arc)
    if fear_result:
        candidate_motivations.append(fear_result)

    # Rule Group C: avoidance_driven
    avoidance_result = _detect_avoidance_driven(
        session_summary, session_memory, session_policy, intent_arc
    )
    if avoidance_result:
        candidate_motivations.append(avoidance_result)

    # Rule Group D: expansion_driven
    expansion_result = _detect_expansion_driven(
        session_summary, session_memory, identity_signature
    )
    if expansion_result:
        candidate_motivations.append(expansion_result)

    # Rule Group E: stabilization_driven
    stabilization_result = _detect_stabilization_driven(session_summary, session_memory)
    if stabilization_result:
        candidate_motivations.append(stabilization_result)

    # Rule Group F: overcorrection
    overcorrection_result = _detect_overcorrection(session_summary, session_memory)
    if overcorrection_result:
        candidate_motivations.append(overcorrection_result)

    # Rule Group G: assertion_driven
    assertion_result = _detect_assertion_driven(session_summary, session_memory)
    if assertion_result:
        candidate_motivations.append(assertion_result)

    # ========================================================================
    # STEP 3: Select highest-confidence motivation (with deterministic tiebreak)
    # ========================================================================
    if not candidate_motivations:
        # Fallback: No motivations detected, return ambiguous
        return MotivationProfile(
            motivation_type="ambiguous_motivation",
            confidence=0.40,
            drivers=["no_motivation_detected"],
            markers=[],
            turn_count=turn_count,
            domain=session_domain,
        )

    # Sort by confidence (descending), then by priority (defined order)
    selected_motivation = _select_best_motivation(candidate_motivations)

    return selected_motivation


# ============================================================================
# Rule Group A: hope_driven
# ============================================================================


def _detect_hope_driven(
    session_summary: Any,
    session_memory: Any,
) -> Optional[MotivationProfile]:
    """
    Detect hope_driven motivation.

    Conditions:
    - Upward coherence trajectory (net rise > 0.12)
    - Breakthrough events present
    - Improving semantic stability (low volatility)
    - Rising temporal arc

    Confidence: 0.75–0.95

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object

    Returns:
        MotivationProfile if detected, None otherwise
    """
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    temporal_arc_timeline = getattr(session_summary, 'temporal_arc_timeline', [])
    mapper_volatility_score = getattr(session_summary, 'mapper_volatility_score', 0.5)
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Need at least 2 turns to check trajectory
    if len(coherence_timeline) < 2:
        return None

    # Check upward coherence trajectory
    coherence_delta = coherence_timeline[-1] - coherence_timeline[0]
    upward_coherence = coherence_delta > 0.12

    # Check for breakthrough events
    events = getattr(session_memory, 'events', []) if session_memory else []
    breakthrough_events = [e for e in events if getattr(e, 'event_type', None) == 'breakthrough']
    has_breakthrough = len(breakthrough_events) > 0

    # Check improving stability (low volatility)
    low_volatility = mapper_volatility_score < 0.45

    # Check rising temporal arc
    temporal_rising = False
    if len(temporal_arc_timeline) >= 2:
        temporal_delta = temporal_arc_timeline[-1] - temporal_arc_timeline[0]
        temporal_rising = temporal_delta > 0.08

    if upward_coherence and has_breakthrough and low_volatility:
        # Compute confidence based on coherence rise and breakthrough count
        confidence = 0.75 + min(coherence_delta * 0.3 + len(breakthrough_events) * 0.05, 0.20)

        drivers = ["upward_coherence", "breakthrough_events", "low_volatility"]
        if temporal_rising:
            drivers.append("rising_temporal_arc")

        markers = []
        markers.append(f"coherence_delta_{coherence_delta:.2f}")
        for bt in breakthrough_events[-2:]:  # Last 2 breakthrough events
            markers.append(f"breakthrough_t{bt.turn_index}")

        return MotivationProfile(
            motivation_type="hope_driven",
            confidence=min(confidence, 0.95),
            drivers=drivers,
            markers=markers,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group B: fear_driven
# ============================================================================


def _detect_fear_driven(
    session_summary: Any,
    session_memory: Any,
    intent_arc: Optional[Any],
) -> Optional[MotivationProfile]:
    """
    Detect fear_driven motivation.

    Conditions:
    - Fragmentation events present
    - High mapper volatility (> 0.55)
    - Defensive mapper patterns (LCM dominance without LAM)
    - Dissonance/chaotic intent arc

    Confidence: 0.65–0.90

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object
        intent_arc: Optional IntentArc object

    Returns:
        MotivationProfile if detected, None otherwise
    """
    mapper_volatility_score = getattr(session_summary, 'mapper_volatility_score', 0.5)
    mapper_sets = getattr(session_summary, 'mapper_sets', [])
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check for fragmentation events
    events = getattr(session_memory, 'events', []) if session_memory else []
    fragmentation_events = [e for e in events if getattr(e, 'event_type', None) == 'fragmentation']
    has_fragmentation = len(fragmentation_events) > 0

    # Check high volatility
    high_volatility = mapper_volatility_score > 0.55

    # Check defensive mapper patterns (LCM without LAM)
    defensive_pattern = False
    if mapper_sets:
        lcm_only_turns = sum(1 for ms in mapper_sets if "LCM" in ms and "LAM" not in ms)
        lcm_only_ratio = lcm_only_turns / len(mapper_sets)
        defensive_pattern = lcm_only_ratio > 0.40

    # Check intent arc for dissonance/chaotic patterns
    dissonance_arc = False
    if intent_arc:
        arc_type = getattr(intent_arc, 'arc_type', None)
        dissonance_arc = arc_type in ["dissonance_arc", "chaotic_arc"]

    if has_fragmentation and high_volatility and defensive_pattern:
        # Compute confidence based on fragmentation count and volatility
        confidence = 0.65 + min(
            len(fragmentation_events) * 0.08 + (mapper_volatility_score - 0.55) * 0.4,
            0.25
        )

        drivers = ["fragmentation_events", "high_volatility", "defensive_patterns"]
        if dissonance_arc:
            drivers.append("dissonance_arc")

        markers = []
        for frag in fragmentation_events[-2:]:  # Last 2 fragmentation events
            markers.append(f"fragmentation_t{frag.turn_index}")
        markers.append(f"volatility_{mapper_volatility_score:.2f}")

        return MotivationProfile(
            motivation_type="fear_driven",
            confidence=min(confidence, 0.90),
            drivers=drivers,
            markers=markers,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group C: avoidance_driven
# ============================================================================


def _detect_avoidance_driven(
    session_summary: Any,
    session_memory: Any,
    session_policy: Optional[Any],
    intent_arc: Optional[Any],
) -> Optional[MotivationProfile]:
    """
    Detect avoidance_driven motivation.

    Conditions:
    - Flat coherence (< 0.05 net delta)
    - Suppressed expression (prefer_concrete policy flag)
    - LCM bias (> 50% LCM dominance)
    - Avoidance arc classification

    Confidence: 0.60–0.85

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object
        session_policy: Optional SessionPolicyFlags object
        intent_arc: Optional IntentArc object

    Returns:
        MotivationProfile if detected, None otherwise
    """
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    mapper_sets = getattr(session_summary, 'mapper_sets', [])
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check flat coherence
    flat_coherence = False
    if len(coherence_timeline) >= 2:
        coherence_delta = abs(coherence_timeline[-1] - coherence_timeline[0])
        flat_coherence = coherence_delta < 0.05

    # Check suppressed expression via policy flags
    suppressed_expression = False
    if session_policy:
        prefer_concrete = getattr(session_policy, 'prefer_concrete', False)
        suppressed_expression = prefer_concrete

    # Check LCM bias
    lcm_bias = False
    if mapper_sets:
        lcm_turns = sum(1 for ms in mapper_sets if "LCM" in ms)
        lcm_ratio = lcm_turns / len(mapper_sets)
        lcm_bias = lcm_ratio > 0.50

    # Check avoidance arc
    avoidance_arc = False
    if intent_arc:
        arc_type = getattr(intent_arc, 'arc_type', None)
        avoidance_arc = arc_type == "avoidance_arc"

    if flat_coherence and lcm_bias and (suppressed_expression or avoidance_arc):
        # Compute confidence based on flatness
        coherence_delta = abs(coherence_timeline[-1] - coherence_timeline[0]) if len(coherence_timeline) >= 2 else 0.0
        confidence = 0.60 + min((0.05 - coherence_delta) * 3.0, 0.25)

        drivers = ["flat_coherence", "lcm_bias"]
        if suppressed_expression:
            drivers.append("suppressed_expression")
        if avoidance_arc:
            drivers.append("avoidance_arc")

        markers = []
        markers.append(f"coherence_delta_{coherence_delta:.3f}")
        markers.append("lcm_dominant")

        return MotivationProfile(
            motivation_type="avoidance_driven",
            confidence=min(confidence, 0.85),
            drivers=drivers,
            markers=markers,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group D: expansion_driven
# ============================================================================


def _detect_expansion_driven(
    session_summary: Any,
    session_memory: Any,
    identity_signature: Optional[Any],
) -> Optional[MotivationProfile]:
    """
    Detect expansion_driven motivation.

    Conditions:
    - LAM active in > 40% of turns
    - Rising temporal arc (> 0.10 net rise)
    - Identity expansion signature (self_expansion or self_discovery)
    - Arc shift events

    Confidence: 0.70–0.95

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object
        identity_signature: Optional IdentitySignature object

    Returns:
        MotivationProfile if detected, None otherwise
    """
    mapper_sets = getattr(session_summary, 'mapper_sets', [])
    temporal_arc_timeline = getattr(session_summary, 'temporal_arc_timeline', [])
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check LAM activity
    lam_active = False
    lam_ratio = 0.0
    if mapper_sets:
        lam_turns = sum(1 for ms in mapper_sets if "LAM" in ms)
        lam_ratio = lam_turns / len(mapper_sets)
        lam_active = lam_ratio > 0.40

    # Check rising temporal arc
    temporal_rising = False
    temporal_delta = 0.0
    if len(temporal_arc_timeline) >= 2:
        temporal_delta = temporal_arc_timeline[-1] - temporal_arc_timeline[0]
        temporal_rising = temporal_delta > 0.10

    # Check identity expansion signature
    identity_expansion = False
    if identity_signature:
        sig_type = getattr(identity_signature, 'signature_type', None)
        identity_expansion = sig_type in ["self_expansion", "self_discovery"]

    # Check arc shift events
    events = getattr(session_memory, 'events', []) if session_memory else []
    arc_shift_events = [e for e in events if getattr(e, 'event_type', None) == 'arc_shift']
    has_arc_shift = len(arc_shift_events) > 0

    if lam_active and temporal_rising and (identity_expansion or has_arc_shift):
        # Compute confidence based on LAM ratio and temporal delta
        confidence = 0.70 + min(lam_ratio * 0.15 + temporal_delta * 0.25, 0.25)

        drivers = ["lam_active", "rising_temporal_arc"]
        if identity_expansion:
            drivers.append("identity_expansion")
        if has_arc_shift:
            drivers.append("arc_shift_events")

        markers = []
        markers.append(f"lam_ratio_{lam_ratio:.2f}")
        markers.append(f"temporal_delta_{temporal_delta:.2f}")
        if has_arc_shift:
            markers.append(f"arc_shift_t{arc_shift_events[-1].turn_index}")

        return MotivationProfile(
            motivation_type="expansion_driven",
            confidence=min(confidence, 0.95),
            drivers=drivers,
            markers=markers,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group E: stabilization_driven
# ============================================================================


def _detect_stabilization_driven(
    session_summary: Any,
    session_memory: Any,
) -> Optional[MotivationProfile]:
    """
    Detect stabilization_driven motivation.

    Conditions:
    - Stabilization events present
    - Previous decline followed by recovery (coherence valley pattern)
    - Low mapper volatility (< 0.40)
    - NO recent fragmentation

    Confidence: 0.70–0.90

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object

    Returns:
        MotivationProfile if detected, None otherwise
    """
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    mapper_volatility_score = getattr(session_summary, 'mapper_volatility_score', 0.5)
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check for stabilization events
    events = getattr(session_memory, 'events', []) if session_memory else []
    stabilization_events = [e for e in events if getattr(e, 'event_type', None) == 'stabilization']
    has_stabilization = len(stabilization_events) > 0

    # Check for valley pattern (decline then recovery)
    valley_pattern = False
    if len(coherence_timeline) >= 3:
        # Find if there's a dip and then recovery
        for i in range(1, len(coherence_timeline) - 1):
            if coherence_timeline[i] < coherence_timeline[i - 1] and coherence_timeline[i] < coherence_timeline[i + 1]:
                valley_pattern = True
                break

    # Check low volatility
    low_volatility = mapper_volatility_score < 0.40

    # Check NO recent fragmentation (last 3 turns)
    recent_turn_threshold = max(0, turn_count - 3)
    no_recent_fragmentation = True
    if events:
        fragmentation_events = [
            e for e in events
            if getattr(e, 'event_type', None) == 'fragmentation'
            and getattr(e, 'turn_index', 0) > recent_turn_threshold
        ]
        no_recent_fragmentation = len(fragmentation_events) == 0

    if has_stabilization and valley_pattern and low_volatility and no_recent_fragmentation:
        # Compute confidence based on stabilization count and volatility
        confidence = 0.70 + min(len(stabilization_events) * 0.08 + (0.40 - mapper_volatility_score) * 0.3, 0.20)

        drivers = [
            "stabilization_events",
            "recovery_pattern",
            "low_volatility",
            "no_recent_fragmentation"
        ]

        markers = []
        for stab in stabilization_events[-2:]:  # Last 2 stabilization events
            markers.append(f"stabilization_t{stab.turn_index}")
        markers.append(f"volatility_{mapper_volatility_score:.2f}")

        return MotivationProfile(
            motivation_type="stabilization_driven",
            confidence=min(confidence, 0.90),
            drivers=drivers,
            markers=markers,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group F: overcorrection
# ============================================================================


def _detect_overcorrection(
    session_summary: Any,
    session_memory: Any,
) -> Optional[MotivationProfile]:
    """
    Detect overcorrection motivation.

    Conditions:
    - Sharp coherence oscillations (>= 2 sign changes)
    - Rapid mapper flips (>= 2 mapper_flip events)
    - High mapper volatility (> 0.60)
    - Moderate-to-high persona drift (> 0.45)

    Confidence: 0.65–0.85

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object

    Returns:
        MotivationProfile if detected, None otherwise
    """
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    mapper_volatility_score = getattr(session_summary, 'mapper_volatility_score', 0.5)
    persona_drift_score = getattr(session_summary, 'persona_drift_score', 0.5)
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check sharp oscillations in coherence
    sharp_oscillations = False
    oscillation_count = 0
    if len(coherence_timeline) >= 3:
        deltas = [
            coherence_timeline[i + 1] - coherence_timeline[i]
            for i in range(len(coherence_timeline) - 1)
        ]
        sign_changes = sum(1 for i in range(len(deltas) - 1) if deltas[i] * deltas[i + 1] < 0)
        oscillation_count = sign_changes
        sharp_oscillations = sign_changes >= 2

    # Check rapid mapper flips
    events = getattr(session_memory, 'events', []) if session_memory else []
    mapper_flip_events = [e for e in events if getattr(e, 'event_type', None) == 'mapper_flip']
    rapid_flips = len(mapper_flip_events) >= 2

    # Check high volatility
    high_volatility = mapper_volatility_score > 0.60

    # Check moderate-to-high persona drift
    moderate_high_drift = persona_drift_score > 0.45

    if sharp_oscillations and rapid_flips and high_volatility:
        # Compute confidence based on oscillation count and flip count
        confidence = 0.65 + min(
            oscillation_count * 0.05 + len(mapper_flip_events) * 0.05,
            0.20
        )

        drivers = ["sharp_oscillations", "rapid_mapper_flips", "high_volatility"]
        if moderate_high_drift:
            drivers.append("moderate_high_drift")

        markers = []
        markers.append(f"oscillations_{oscillation_count}")
        for flip in mapper_flip_events[-2:]:  # Last 2 mapper flips
            markers.append(f"mapper_flip_t{flip.turn_index}")

        return MotivationProfile(
            motivation_type="overcorrection",
            confidence=min(confidence, 0.85),
            drivers=drivers,
            markers=markers,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group G: assertion_driven
# ============================================================================


def _detect_assertion_driven(
    session_summary: Any,
    session_memory: Any,
) -> Optional[MotivationProfile]:
    """
    Detect assertion_driven motivation.

    Conditions:
    - HRM dominance (> 60% of turns)
    - High coherence (> 0.65)
    - Low persona drift (< 0.35)
    - NO avoidance patterns (temporal arc > 0.45)

    Confidence: 0.70–0.90

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object

    Returns:
        MotivationProfile if detected, None otherwise
    """
    mapper_sets = getattr(session_summary, 'mapper_sets', [])
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    persona_drift_score = getattr(session_summary, 'persona_drift_score', 0.5)
    temporal_arc_score = getattr(session_summary, 'temporal_arc_score', 0.5)
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check HRM dominance
    hrm_dominant = False
    hrm_ratio = 0.0
    if mapper_sets:
        hrm_turns = sum(1 for ms in mapper_sets if "HRM" in ms)
        hrm_ratio = hrm_turns / len(mapper_sets)
        hrm_dominant = hrm_ratio > 0.60

    # Check high coherence
    current_coherence = coherence_timeline[-1] if coherence_timeline else 0.5
    high_coherence = current_coherence > 0.65

    # Check low persona drift
    low_drift = persona_drift_score < 0.35

    # Check NO avoidance (temporal arc > 0.45)
    no_avoidance = temporal_arc_score > 0.45

    if hrm_dominant and high_coherence and low_drift and no_avoidance:
        # Compute confidence based on HRM ratio and coherence
        confidence = 0.70 + min(hrm_ratio * 0.15 + (current_coherence - 0.65) * 0.25, 0.20)

        drivers = ["hrm_dominant", "high_coherence", "low_drift", "no_avoidance"]

        markers = []
        markers.append(f"hrm_ratio_{hrm_ratio:.2f}")
        markers.append(f"coherence_{current_coherence:.2f}")

        return MotivationProfile(
            motivation_type="assertion_driven",
            confidence=min(confidence, 0.90),
            drivers=drivers,
            markers=markers,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Motivation Selection Algorithm
# ============================================================================


# Priority order for tiebreaking (higher priority = earlier in list)
MOTIVATION_PRIORITY = [
    "hope_driven",           # Highest priority - positive breakthrough
    "expansion_driven",      # Active exploration and growth
    "stabilization_driven",  # Recovery and healing
    "assertion_driven",      # Strong self-expression
    "fear_driven",           # Critical - needs support
    "overcorrection",        # Instability needing attention
    "avoidance_driven",      # Defensive pattern
    "ambiguous_motivation",  # Fallback
]


def _select_best_motivation(candidate_motivations: List[MotivationProfile]) -> MotivationProfile:
    """
    Select the best motivation from candidates using deterministic rules.

    Selection Rules:
        1. Choose highest confidence
        2. If tie, use MOTIVATION_PRIORITY for deterministic tiebreak

    Args:
        candidate_motivations: List of candidate MotivationProfile objects

    Returns:
        Best MotivationProfile based on confidence and priority
    """
    if not candidate_motivations:
        # Should never happen, but return a fallback
        return MotivationProfile(
            motivation_type="ambiguous_motivation",
            confidence=0.30,
            drivers=["no_candidates"],
            markers=[],
        )

    # Sort by confidence (descending), then by priority (ascending)
    def motivation_sort_key(mot: MotivationProfile):
        # Higher confidence = better (negate for ascending sort)
        # Lower priority index = better (no negation needed)
        priority_idx = (
            MOTIVATION_PRIORITY.index(mot.motivation_type)
            if mot.motivation_type in MOTIVATION_PRIORITY
            else 999
        )
        return (-mot.confidence, priority_idx)

    sorted_motivations = sorted(candidate_motivations, key=motivation_sort_key)

    return sorted_motivations[0]


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "MotivationProfile",
    "compute_motivation_flow",
]
