"""
Identity Signature Engine v1.0 — Deterministic Identity Trajectory Classification

This module implements a purely rule-based engine for classifying identity trajectories
in multi-turn sessions. The classification is based on:
- SessionSummary metrics (coherence, temporal arc, persona drift, mapper volatility)
- SessionMemory events (breakthrough, fragmentation, stabilization)
- SessionPolicyFlags (recommended styles, grounding needs)
- IntentArc classification (arc types and reasons)
- Mapper journeys (HRM/LCM/LAM synergy and dominance)
- Domain context (identity, therapy, generic)

Design Principles:
    1. Zero-LLM (purely rule-based, deterministic)
    2. Non-invasive (does NOT modify pipeline logic)
    3. Additive (optional analytical layer)
    4. Deterministic (same input → same output)
    5. Session-oriented (uses multi-turn state)

Identity Signature Types:
    - self_anchoring: Coherence rising, persona drift low, no fragmentation
    - self_expansion: LAM-driven exploration with high temporal arc
    - self_fragmentation: High persona drift with fragmentation events
    - self_suppression: Flat coherence, LCM dominance, avoidance patterns
    - self_integration: Breakthrough + stabilization, HRM+LAM synergy
    - self_dissonance: High persona drift, oscillating coherence, mapper volatility
    - self_discovery: Breakthrough events with improving trajectory
    - neutral_identity: Ambiguous or mixed signals (fallback)

Usage:
    from symbolu.identity.identity_signature_engine import compute_identity_signature

    # Compute identity signature from session components
    identity_signature = compute_identity_signature(
        session_summary=summary,
        session_memory=memory,
        session_policy=policy_flags,
        intent_arc=intent_arc,
        domain=domain,
    )

    # Access signature classification
    print(f"Signature Type: {identity_signature.signature_type}")
    print(f"Confidence: {identity_signature.confidence}")
    print(f"Drivers: {identity_signature.drivers}")
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# ============================================================================
# IdentitySignature Dataclass
# ============================================================================


@dataclass
class IdentitySignature:
    """
    Identity signature classification result.

    This dataclass encapsulates the deterministic classification of a
    multi-turn session's identity trajectory into one of 8 canonical types.

    Attributes:
        signature_type: One of the 8 identity signature types
        confidence: Deterministic confidence score (0.0–1.0)
        drivers: List of rule-based triggers that fired (e.g., ["coherence_rising", "low_drift"])
        markers: List of identity-related session markers (e.g., ["breakthrough_t3", "lam_active"])
        turn_count: Number of turns in the session
        domain: Domain context (e.g., "trading", "therapy", "identity")
    """
    signature_type: str
    confidence: float
    drivers: List[str] = field(default_factory=list)
    markers: List[str] = field(default_factory=list)
    turn_count: int = 0
    domain: str = "generic"

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize identity signature to JSON-safe dictionary.

        Returns:
            Dictionary with all identity signature fields
        """
        return {
            "signature_type": self.signature_type,
            "confidence": self.confidence,
            "drivers": self.drivers,
            "markers": self.markers,
            "turn_count": self.turn_count,
            "domain": self.domain,
        }


# ============================================================================
# Main Identity Signature Computation
# ============================================================================


def compute_identity_signature(
    session_summary: Any,
    session_memory: Any,
    session_policy: Optional[Any] = None,
    intent_arc: Optional[Any] = None,
    domain: str = "generic",
) -> IdentitySignature:
    """
    Compute deterministic identity signature classification from session components.

    This is the main public API for identity signature computation. It applies
    8 rule groups to classify the session's identity trajectory into one of 8
    canonical signature types, with deterministic confidence scoring.

    Args:
        session_summary: SessionSummary object with aggregated metrics
        session_memory: SessionMemory object with episodic events
        session_policy: Optional SessionPolicyFlags object
        intent_arc: Optional IntentArc object
        domain: Domain context string

    Returns:
        IdentitySignature object with classification, confidence, drivers, and markers

    Rule Groups:
        A. self_anchoring: Coherence rising, low persona drift, stable
        B. self_expansion: LAM-driven identity exploration
        C. self_fragmentation: High drift, fragmentation events, instability
        D. self_suppression: Flat coherence, LCM dominance, avoidance
        E. self_integration: Breakthrough + stabilization, HRM+LAM synergy
        F. self_dissonance: Internal conflict, high volatility, oscillating
        G. self_discovery: Breakthrough with identity turning points
        H. neutral_identity: Ambiguous or mixed signals (fallback)
    """
    # ========================================================================
    # STEP 1: Extract session data
    # ========================================================================
    turn_count = getattr(session_summary, 'turn_count', 0)
    session_domain = getattr(session_summary, 'last_domain', domain)

    # Edge case: Not enough turns to classify
    if turn_count < 1:
        return IdentitySignature(
            signature_type="neutral_identity",
            confidence=0.30,
            drivers=["insufficient_turns"],
            markers=[],
            turn_count=turn_count,
            domain=session_domain,
        )

    # ========================================================================
    # STEP 2: Apply all 8 rule groups to detect candidate signatures
    # ========================================================================
    candidate_signatures = []

    # Rule Group A: self_anchoring
    anchoring_result = _detect_self_anchoring(session_summary, session_memory)
    if anchoring_result:
        candidate_signatures.append(anchoring_result)

    # Rule Group B: self_expansion
    expansion_result = _detect_self_expansion(
        session_summary, session_memory, intent_arc, session_domain
    )
    if expansion_result:
        candidate_signatures.append(expansion_result)

    # Rule Group C: self_fragmentation
    fragmentation_result = _detect_self_fragmentation(session_summary, session_memory)
    if fragmentation_result:
        candidate_signatures.append(fragmentation_result)

    # Rule Group D: self_suppression
    suppression_result = _detect_self_suppression(
        session_summary, session_memory, intent_arc
    )
    if suppression_result:
        candidate_signatures.append(suppression_result)

    # Rule Group E: self_integration
    integration_result = _detect_self_integration(session_summary, session_memory)
    if integration_result:
        candidate_signatures.append(integration_result)

    # Rule Group F: self_dissonance
    dissonance_result = _detect_self_dissonance(session_summary, intent_arc)
    if dissonance_result:
        candidate_signatures.append(dissonance_result)

    # Rule Group G: self_discovery
    discovery_result = _detect_self_discovery(
        session_summary, session_memory, session_domain
    )
    if discovery_result:
        candidate_signatures.append(discovery_result)

    # ========================================================================
    # STEP 3: Select highest-confidence signature (with deterministic tiebreak)
    # ========================================================================
    if not candidate_signatures:
        # Fallback: No signatures detected, return neutral
        return IdentitySignature(
            signature_type="neutral_identity",
            confidence=0.40,
            drivers=["no_signature_detected"],
            markers=[],
            turn_count=turn_count,
            domain=session_domain,
        )

    # Sort by confidence (descending), then by priority (defined order)
    selected_signature = _select_best_signature(candidate_signatures)

    return selected_signature


# ============================================================================
# Rule Group A: self_anchoring
# ============================================================================


def _detect_self_anchoring(
    session_summary: Any,
    session_memory: Any,
) -> Optional[IdentitySignature]:
    """
    Detect self_anchoring identity signature.

    Conditions (all must hold):
    - coherence_score >= 0.65
    - persona_drift <= 0.40
    - rising coherence 2+ turns
    - NO fragmentation events in memory

    Confidence: 0.70–0.90

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object

    Returns:
        IdentitySignature if detected, None otherwise
    """
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    persona_drift_score = getattr(session_summary, 'persona_drift_score', 0.5)
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Need at least 2 turns to check rising coherence
    if len(coherence_timeline) < 2:
        return None

    # Check coherence score
    current_coherence = coherence_timeline[-1]
    high_coherence = current_coherence >= 0.65

    # Check persona drift
    low_drift = persona_drift_score <= 0.40

    # Check rising coherence (last 2 turns minimum)
    rising_coherence = False
    if len(coherence_timeline) >= 2:
        last_two = coherence_timeline[-2:]
        rising_coherence = all(last_two[i] <= last_two[i + 1] for i in range(len(last_two) - 1))

    # Check for fragmentation events
    events = getattr(session_memory, 'events', []) if session_memory else []
    fragmentation_events = [e for e in events if getattr(e, 'event_type', None) == 'fragmentation']
    no_fragmentation = len(fragmentation_events) == 0

    if high_coherence and low_drift and rising_coherence and no_fragmentation:
        # Compute confidence based on coherence level and drift
        confidence = 0.70 + min(current_coherence * 0.15, 0.15)  # General pattern - moderate confidence

        drivers = ["high_coherence", "low_persona_drift", "rising_coherence", "no_fragmentation"]

        markers = []
        markers.append(f"coherence_{current_coherence:.2f}")
        markers.append(f"drift_{persona_drift_score:.2f}")

        return IdentitySignature(
            signature_type="self_anchoring",
            confidence=confidence,
            drivers=drivers,
            markers=markers,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group B: self_expansion
# ============================================================================


def _detect_self_expansion(
    session_summary: Any,
    session_memory: Any,
    intent_arc: Optional[Any],
    domain: str,
) -> Optional[IdentitySignature]:
    """
    Detect self_expansion identity signature.

    Strong identity-level exploration:
    - LAM active in >40% of turns
    - temporal arc > 0.55
    - identity-related domain OR arc_shift memory event

    Confidence: 0.65–0.90

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object
        intent_arc: Optional IntentArc object
        domain: Domain context string

    Returns:
        IdentitySignature if detected, None otherwise
    """
    mapper_sets = getattr(session_summary, 'mapper_sets', [])
    temporal_arc_score = getattr(session_summary, 'temporal_arc_score', 0.5)
    turn_count = getattr(session_summary, 'turn_count', 0)
    session_domain = getattr(session_summary, 'last_domain', domain)

    if not mapper_sets or turn_count < 1:
        return None

    # Check LAM activity across turns
    lam_turns = sum(1 for mapper_set in mapper_sets if "LAM" in mapper_set)
    lam_ratio = lam_turns / len(mapper_sets) if mapper_sets else 0.0
    lam_dominant = lam_ratio > 0.40

    # Check temporal arc
    high_temporal = temporal_arc_score > 0.55

    # Check for identity domain or arc_shift events
    identity_related_domain = session_domain in ["identity", "therapy"]

    events = getattr(session_memory, 'events', []) if session_memory else []
    arc_shift_events = [e for e in events if getattr(e, 'event_type', None) == 'arc_shift']
    has_arc_shift = len(arc_shift_events) > 0

    identity_signals = identity_related_domain or has_arc_shift

    if lam_dominant and high_temporal and identity_signals:
        # Compute confidence based on LAM ratio and temporal arc
        confidence = 0.65 + min(lam_ratio * 0.15 + (temporal_arc_score - 0.55) * 0.2, 0.25)

        drivers = ["lam_dominant", "high_temporal_arc"]
        if identity_related_domain:
            drivers.append("identity_domain")
        if has_arc_shift:
            drivers.append("arc_shift_detected")

        markers = []
        markers.append(f"lam_ratio_{lam_ratio:.2f}")
        markers.append(f"temporal_arc_{temporal_arc_score:.2f}")
        if has_arc_shift:
            markers.append(f"arc_shift_t{arc_shift_events[-1].turn_index}")

        return IdentitySignature(
            signature_type="self_expansion",
            confidence=min(confidence, 0.90),
            drivers=drivers,
            markers=markers,
            turn_count=turn_count,
            domain=session_domain,
        )

    return None


# ============================================================================
# Rule Group C: self_fragmentation
# ============================================================================


def _detect_self_fragmentation(
    session_summary: Any,
    session_memory: Any,
) -> Optional[IdentitySignature]:
    """
    Detect self_fragmentation identity signature.

    Identity instability:
    - persona_drift > 0.55
    - fragmentation events present
    - oscillating coherence trajectory

    Confidence: 0.60–0.85

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object

    Returns:
        IdentitySignature if detected, None otherwise
    """
    persona_drift_score = getattr(session_summary, 'persona_drift_score', 0.5)
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check persona drift
    high_drift = persona_drift_score > 0.55

    # Check for fragmentation events
    events = getattr(session_memory, 'events', []) if session_memory else []
    fragmentation_events = [e for e in events if getattr(e, 'event_type', None) == 'fragmentation']
    has_fragmentation = len(fragmentation_events) > 0

    # Check for oscillating coherence (sign changes in deltas)
    coherence_oscillating = False
    if len(coherence_timeline) >= 3:
        deltas = [
            coherence_timeline[i + 1] - coherence_timeline[i]
            for i in range(len(coherence_timeline) - 1)
        ]
        sign_changes = sum(1 for i in range(len(deltas) - 1) if deltas[i] * deltas[i + 1] < 0)
        coherence_oscillating = sign_changes >= 1

    if high_drift and has_fragmentation and coherence_oscillating:
        # Compute confidence based on drift magnitude and event count
        confidence = 0.60 + min((persona_drift_score - 0.55) * 0.5 + len(fragmentation_events) * 0.05, 0.25)

        drivers = ["high_persona_drift", "fragmentation_events", "oscillating_coherence"]

        markers = []
        markers.append(f"drift_{persona_drift_score:.2f}")
        for frag in fragmentation_events[-2:]:  # Last 2 fragmentation events
            markers.append(f"fragmentation_t{frag.turn_index}")

        return IdentitySignature(
            signature_type="self_fragmentation",
            confidence=min(confidence, 0.85),
            drivers=drivers,
            markers=markers,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group D: self_suppression
# ============================================================================


def _detect_self_suppression(
    session_summary: Any,
    session_memory: Any,
    intent_arc: Optional[Any],
) -> Optional[IdentitySignature]:
    """
    Detect self_suppression identity signature.

    Identity avoidance:
    - Flat coherence (<0.05 net delta)
    - mapper dominated by LCM
    - avoidance_arc or low-temporal-arc intent arc classification

    Confidence: 0.55–0.80

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object
        intent_arc: Optional IntentArc object

    Returns:
        IdentitySignature if detected, None otherwise
    """
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    mapper_sets = getattr(session_summary, 'mapper_sets', [])
    temporal_arc_score = getattr(session_summary, 'temporal_arc_score', 0.5)
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check coherence flatness
    flat_coherence = False
    if len(coherence_timeline) >= 2:
        delta = abs(coherence_timeline[-1] - coherence_timeline[0])
        flat_coherence = delta < 0.05

    # Check LCM dominance
    lcm_dominant = False
    if mapper_sets:
        lcm_turns = sum(1 for mapper_set in mapper_sets if "LCM" in mapper_set and "LAM" not in mapper_set)
        lcm_ratio = lcm_turns / len(mapper_sets)
        lcm_dominant = lcm_ratio > 0.50

    # Check intent arc for avoidance patterns
    avoidance_arc = False
    low_temporal = temporal_arc_score < 0.40

    if intent_arc:
        arc_type = getattr(intent_arc, 'arc_type', None)
        avoidance_arc = arc_type == "avoidance_arc"

    avoidance_signals = avoidance_arc or low_temporal

    if flat_coherence and lcm_dominant and avoidance_signals:
        # Compute confidence based on flatness and LCM dominance
        confidence = 0.55 + min((0.05 - abs(coherence_timeline[-1] - coherence_timeline[0])) * 2.0, 0.25)

        drivers = ["flat_coherence", "lcm_dominant"]
        if avoidance_arc:
            drivers.append("avoidance_arc")
        if low_temporal:
            drivers.append("low_temporal_arc")

        markers = []
        markers.append(f"coherence_delta_{abs(coherence_timeline[-1] - coherence_timeline[0]):.3f}")
        markers.append("lcm_dominant")

        return IdentitySignature(
            signature_type="self_suppression",
            confidence=min(confidence, 0.80),
            drivers=drivers,
            markers=markers,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group E: self_integration
# ============================================================================


def _detect_self_integration(
    session_summary: Any,
    session_memory: Any,
) -> Optional[IdentitySignature]:
    """
    Detect self_integration identity signature.

    Coherence + identity integration:
    - breakthrough + stabilization events in memory
    - rising temporal arc
    - HRM + LAM synergy detected
    - NO recent fragmentation

    Confidence: 0.75–0.95

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object

    Returns:
        IdentitySignature if detected, None otherwise
    """
    temporal_arc_timeline = getattr(session_summary, 'temporal_arc_timeline', [])
    mapper_sets = getattr(session_summary, 'mapper_sets', [])
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check for breakthrough + stabilization events
    events = getattr(session_memory, 'events', []) if session_memory else []
    breakthrough_events = [e for e in events if getattr(e, 'event_type', None) == 'breakthrough']
    stabilization_events = [e for e in events if getattr(e, 'event_type', None) == 'stabilization']

    has_breakthrough = len(breakthrough_events) > 0
    has_stabilization = len(stabilization_events) > 0

    # Check for rising temporal arc
    temporal_rising = False
    if len(temporal_arc_timeline) >= 2:
        delta = temporal_arc_timeline[-1] - temporal_arc_timeline[0]
        temporal_rising = delta > 0.10

    # Check for HRM + LAM synergy in recent turns
    hrm_lam_synergy = False
    if mapper_sets:
        recent_mapper_sets = mapper_sets[-3:] if len(mapper_sets) >= 3 else mapper_sets
        synergy_count = sum(1 for ms in recent_mapper_sets if "HRM" in ms and "LAM" in ms)
        hrm_lam_synergy = synergy_count >= 1

    # Check for NO recent fragmentation (last 3 turns, not last 3 events)
    # Only check fragmentation events that occurred in the last 3 turns
    recent_turn_threshold = turn_count - 3
    no_recent_fragmentation = True
    if events:
        fragmentation_events_in_session = [
            e for e in events if getattr(e, 'event_type', None) == 'fragmentation'
        ]
        # Check if any fragmentation event occurred in last 3 turns
        no_recent_fragmentation = not any(
            getattr(e, 'turn_index', 0) > recent_turn_threshold
            for e in fragmentation_events_in_session
        )

    if has_breakthrough and has_stabilization and hrm_lam_synergy and no_recent_fragmentation:
        # Compute confidence based on number of positive signals
        confidence = 0.85  # Higher base confidence for integration (highest priority pattern)
        if len(breakthrough_events) > 1:
            confidence += 0.06
        if temporal_rising:
            confidence += 0.04

        drivers = [
            "breakthrough_stabilization",
            "hrm_lam_synergy",
            "no_recent_fragmentation",
        ]

        if temporal_rising:
            drivers.append("rising_temporal_arc")

        markers = []
        markers.append(f"breakthrough_t{breakthrough_events[-1].turn_index}")
        markers.append(f"stabilization_t{stabilization_events[-1].turn_index}")
        markers.append("hrm_lam_synergy")

        return IdentitySignature(
            signature_type="self_integration",
            confidence=min(confidence, 0.95),
            drivers=drivers,
            markers=markers,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group F: self_dissonance
# ============================================================================


def _detect_self_dissonance(
    session_summary: Any,
    intent_arc: Optional[Any],
) -> Optional[IdentitySignature]:
    """
    Detect self_dissonance identity signature.

    Internal conflict:
    - high mapper volatility
    - persona drift moderate (0.40–0.55)
    - dissonance/chaotic intent arc classification

    Confidence: 0.60–0.85

    Args:
        session_summary: SessionSummary object
        intent_arc: Optional IntentArc object

    Returns:
        IdentitySignature if detected, None otherwise
    """
    mapper_volatility_score = getattr(session_summary, 'mapper_volatility_score', 0.5)
    persona_drift_score = getattr(session_summary, 'persona_drift_score', 0.5)
    turn_count = getattr(session_summary, 'turn_count', 0)
    domain = getattr(session_summary, 'last_domain', 'generic')

    # Check mapper volatility
    high_volatility = mapper_volatility_score > 0.55

    # Check persona drift (moderate range)
    moderate_drift = 0.40 < persona_drift_score <= 0.55

    # Check intent arc for dissonance/chaotic patterns
    dissonance_arc = False
    if intent_arc:
        arc_type = getattr(intent_arc, 'arc_type', None)
        dissonance_arc = arc_type in ["dissonance_arc", "chaotic_arc"]

    if high_volatility and moderate_drift and dissonance_arc:
        # Compute confidence based on volatility and drift
        confidence = 0.61 + min((mapper_volatility_score - 0.55) * 0.5 + (persona_drift_score - 0.40) * 0.3, 0.24)

        drivers = ["high_mapper_volatility", "moderate_persona_drift", "dissonance_arc"]

        markers = []
        markers.append(f"volatility_{mapper_volatility_score:.2f}")
        markers.append(f"drift_{persona_drift_score:.2f}")
        if intent_arc:
            markers.append(f"arc_{getattr(intent_arc, 'arc_type', 'unknown')}")

        return IdentitySignature(
            signature_type="self_dissonance",
            confidence=min(confidence, 0.85),
            drivers=drivers,
            markers=markers,
            turn_count=turn_count,
            domain=domain,
        )

    return None


# ============================================================================
# Rule Group G: self_discovery
# ============================================================================


def _detect_self_discovery(
    session_summary: Any,
    session_memory: Any,
    domain: str,
) -> Optional[IdentitySignature]:
    """
    Detect self_discovery identity signature.

    Identity turning points:
    - breakthrough event present
    - identity-trigger memory markers
    - improving trajectory (>0.10 net rise)

    Confidence: 0.70–0.90

    Args:
        session_summary: SessionSummary object
        session_memory: SessionMemory object
        domain: Domain context string

    Returns:
        IdentitySignature if detected, None otherwise
    """
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    turn_count = getattr(session_summary, 'turn_count', 0)
    session_domain = getattr(session_summary, 'last_domain', domain)

    # Check for breakthrough events
    events = getattr(session_memory, 'events', []) if session_memory else []
    breakthrough_events = [e for e in events if getattr(e, 'event_type', None) == 'breakthrough']

    has_breakthrough = len(breakthrough_events) > 0

    # Check for identity triggers (arc_shift or mapper_flip to LAM)
    arc_shift_events = [e for e in events if getattr(e, 'event_type', None) == 'arc_shift']
    mapper_flip_events = [e for e in events if getattr(e, 'event_type', None) == 'mapper_flip']

    identity_triggers = len(arc_shift_events) > 0 or any(
        'LAM' in getattr(e, 'metrics', {}).get('current_mappers', '') for e in mapper_flip_events
    )

    # Check for improving trajectory
    improving_trajectory = False
    if len(coherence_timeline) >= 2:
        delta = coherence_timeline[-1] - coherence_timeline[0]
        improving_trajectory = delta > 0.10

    if has_breakthrough and identity_triggers:
        # Compute confidence based on trajectory improvement
        delta = coherence_timeline[-1] - coherence_timeline[0] if len(coherence_timeline) >= 2 else 0.0
        confidence = 0.78 + min(delta * 0.3, 0.12)  # Higher base for discovery (specific pattern)

        drivers = ["breakthrough_detected", "identity_triggers"]

        if improving_trajectory:
            drivers.append("improving_trajectory")
            # No additional boost - already captured in delta calculation

        markers = []
        markers.append(f"breakthrough_t{breakthrough_events[-1].turn_index}")
        if arc_shift_events:
            markers.append(f"arc_shift_t{arc_shift_events[-1].turn_index}")
        markers.append(f"trajectory_delta_{delta:.2f}")

        return IdentitySignature(
            signature_type="self_discovery",
            confidence=min(confidence, 0.90),
            drivers=drivers,
            markers=markers,
            turn_count=turn_count,
            domain=session_domain,
        )

    return None


# ============================================================================
# Signature Selection Algorithm
# ============================================================================


# Priority order for tiebreaking (higher priority = earlier in list)
SIGNATURE_PRIORITY = [
    "self_integration",      # Highest priority - positive integration
    "self_discovery",        # Identity breakthrough moments
    "self_anchoring",        # Stable identity
    "self_expansion",        # Active exploration
    "self_fragmentation",    # Critical - needs attention
    "self_dissonance",       # Internal conflict
    "self_suppression",      # Avoidance pattern
    "neutral_identity",      # Fallback
]


def _select_best_signature(candidate_signatures: List[IdentitySignature]) -> IdentitySignature:
    """
    Select the best identity signature from candidates using deterministic rules.

    Selection Rules:
        1. Choose highest confidence
        2. If tie, use SIGNATURE_PRIORITY for deterministic tiebreak

    Args:
        candidate_signatures: List of candidate IdentitySignature objects

    Returns:
        Best IdentitySignature based on confidence and priority
    """
    if not candidate_signatures:
        # Should never happen, but return a fallback
        return IdentitySignature(
            signature_type="neutral_identity",
            confidence=0.30,
            drivers=["no_candidates"],
            markers=[],
        )

    # Sort by confidence (descending), then by priority (ascending)
    def signature_sort_key(sig: IdentitySignature):
        # Higher confidence = better (negate for ascending sort)
        # Lower priority index = better (no negation needed)
        priority_idx = (
            SIGNATURE_PRIORITY.index(sig.signature_type)
            if sig.signature_type in SIGNATURE_PRIORITY
            else 999
        )
        return (-sig.confidence, priority_idx)

    sorted_signatures = sorted(candidate_signatures, key=signature_sort_key)

    return sorted_signatures[0]


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "IdentitySignature",
    "compute_identity_signature",
]
