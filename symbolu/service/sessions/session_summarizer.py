"""
Symbol-U Session Summarizer v1.0 — Deterministic Multi-Turn Recap Layer

This module implements a deterministic session-level recap engine that produces
structured summaries of multi-turn sessions using:

- SessionSummary metrics (coherence, drift, arc, volatility)
- SessionMemory events (breakthrough, fragmentation, stabilization, etc.)
- SessionPolicyFlags (grounding, stability, style)
- Turn metadata (count, domain)

Design Principles:
    1. Zero-LLM (purely rule-based)
    2. Non-invasive to the pipeline
    3. Additive (optional)
    4. Deterministic
    5. Fully test-covered
    6. Integrated into Unified API, Session endpoints, and DILchat adapter

Usage:
    from symbolu.service.sessions.session_summarizer import (
        SessionRecap,
        compute_session_recap
    )

    # Compute session recap from session components
    recap = compute_session_recap(
        session_summary=summary,
        session_memory=memory,
        session_policy=policy,
        domain="trading"
    )

    # Serialize for API output
    recap_dict = recap.serialize()
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class SessionRecap:
    """
    Deterministic session-level recap structure.

    This dataclass captures the overall state and trajectory of a multi-turn
    session using purely rule-based analysis of session metrics and memory events.

    Attributes:
        overall_state: Current session state - "stable", "recovering", or "fragmented"
        net_trajectory: Overall trajectory - "improving", "declining", "oscillating", or "ambiguous"
        turning_points: List of significant memory events (serialized MemoryEntry objects)
        mapper_journey: Chronological list of mapper configuration strings (e.g., "HRM+LAM")
        key_patterns: Derived symbolic patterns (deterministic codes)
        recommended_style: Suggested interaction style - "grounded", "reflective", "exploratory", or "neutral"
        turn_count: Total number of turns in session
        domain: Domain context for the session
    """
    overall_state: str                 # "stable", "recovering", "fragmented"
    net_trajectory: str                # "improving", "declining", "oscillating", "ambiguous"
    turning_points: List[Dict]         # serialized MemoryEntry objects
    mapper_journey: List[str]          # chronological list of mapper sets
    key_patterns: List[str]            # derived insights (deterministic codes)
    recommended_style: str             # grounded / reflective / exploratory / neutral
    turn_count: int
    domain: str

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize session recap to JSON-safe dictionary.

        Returns:
            Dictionary with all session recap fields
        """
        return {
            "overall_state": self.overall_state,
            "net_trajectory": self.net_trajectory,
            "turning_points": self.turning_points,
            "mapper_journey": self.mapper_journey,
            "key_patterns": self.key_patterns,
            "recommended_style": self.recommended_style,
            "turn_count": self.turn_count,
            "domain": self.domain,
        }


def compute_session_recap(
    session_summary: Any,
    session_memory: Any,
    session_policy: Optional[Any] = None,
    domain: str = "generic"
) -> SessionRecap:
    """
    Compute deterministic session recap from session components.

    This is the main public API for session recap computation. It applies
    purely rule-based logic to determine:
    1. Overall session state (stable/recovering/fragmented)
    2. Net trajectory (improving/declining/oscillating/ambiguous)
    3. Turning points (significant memory events)
    4. Mapper journey (chronological mapper configuration history)
    5. Key patterns (symbolic insights from data)
    6. Recommended style (interaction mode suggestion)

    Args:
        session_summary: SessionSummary object with aggregated metrics
        session_memory: SessionMemory object with episodic events
        session_policy: Optional SessionPolicyFlags object
        domain: Domain context (e.g., "trading", "therapy", "identity")

    Returns:
        SessionRecap object with complete deterministic analysis

    Rules:
        Overall State:
            - coherence_score >= 0.70 → "stable"
            - coherence_score >= 0.45 → "recovering"
            - coherence_score < 0.45 → "fragmented"

        Net Trajectory:
            - Use coherence timeline to compute delta between last and first
            - abs(delta) < 0.05 → "ambiguous"
            - delta >= 0.10 → "improving"
            - delta <= -0.10 → "declining"
            - Otherwise → "oscillating"

        Turning Points:
            - Extract all MemoryEntry events of types:
              • breakthrough
              • fragmentation
              • stabilization
              • arc_shift
              • mapper_flip

        Mapper Journey:
            - Convert mapper sets to sorted strings (e.g., {"HRM", "LAM"} → "HRM+LAM")

        Key Patterns:
            - breakthrough_detected: If any breakthrough event exists
            - instability_present: If any fragmentation event exists
            - recovery_in_progress: If stabilization after fragmentation
            - deepening_arc: If net trajectory improving AND LAM active
            - volatile_strategy_shift: If mapper_volatility_score > 0.55

        Recommended Style:
            - Use session_policy.session_recommended_style if available
            - Otherwise fallback:
              • overall_state == "stable" → "reflective"
              • overall_state == "recovering" → "exploratory"
              • overall_state == "fragmented" → "grounded"
    """
    # ========================================================================
    # STEP 1: Extract coherence score and timeline
    # ========================================================================
    coherence_score = getattr(session_summary, 'coherence_score', 0.5)
    coherence_timeline = getattr(session_summary, 'coherence_timeline', [])
    temporal_arc_timeline = getattr(session_summary, 'temporal_arc_timeline', [])
    mapper_sets = getattr(session_summary, 'mapper_sets', [])
    mapper_volatility_score = getattr(session_summary, 'mapper_volatility_score', 0.0)
    turn_count = getattr(session_summary, 'turn_count', 0)

    # ========================================================================
    # STEP 2: Compute overall state from coherence score
    # ========================================================================
    if coherence_score >= 0.70:
        overall_state = "stable"
    elif coherence_score >= 0.45:
        overall_state = "recovering"
    else:
        overall_state = "fragmented"

    # ========================================================================
    # STEP 3: Compute net trajectory from coherence timeline
    # ========================================================================
    net_trajectory = _compute_net_trajectory(coherence_timeline)

    # ========================================================================
    # STEP 4: Extract turning points from session memory
    # ========================================================================
    turning_points = _extract_turning_points(session_memory)

    # ========================================================================
    # STEP 5: Build mapper journey from mapper sets
    # ========================================================================
    mapper_journey = _build_mapper_journey(mapper_sets)

    # ========================================================================
    # STEP 6: Detect key patterns from session data
    # ========================================================================
    key_patterns = _detect_key_patterns(
        session_memory=session_memory,
        net_trajectory=net_trajectory,
        mapper_sets=mapper_sets,
        mapper_volatility_score=mapper_volatility_score,
    )

    # ========================================================================
    # STEP 7: Determine recommended style
    # ========================================================================
    recommended_style = _determine_recommended_style(
        session_policy=session_policy,
        overall_state=overall_state,
    )

    # ========================================================================
    # STEP 8: Assemble and return SessionRecap
    # ========================================================================
    return SessionRecap(
        overall_state=overall_state,
        net_trajectory=net_trajectory,
        turning_points=turning_points,
        mapper_journey=mapper_journey,
        key_patterns=key_patterns,
        recommended_style=recommended_style,
        turn_count=turn_count,
        domain=domain,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _compute_net_trajectory(coherence_timeline: List[float]) -> str:
    """
    Compute net trajectory from coherence timeline.

    Args:
        coherence_timeline: List of coherence scores per turn

    Returns:
        Trajectory classification string

    Rules:
        - abs(delta) < 0.05 → "ambiguous"
        - delta >= 0.10 → "improving"
        - delta <= -0.10 → "declining"
        - Otherwise → "oscillating"
    """
    if len(coherence_timeline) < 2:
        return "ambiguous"

    first_score = coherence_timeline[0]
    last_score = coherence_timeline[-1]
    delta = last_score - first_score

    if abs(delta) < 0.05:
        return "ambiguous"
    elif delta >= 0.10:
        return "improving"
    elif delta <= -0.10:
        return "declining"
    else:
        return "oscillating"


def _extract_turning_points(session_memory: Any) -> List[Dict[str, Any]]:
    """
    Extract turning points from session memory.

    Turning points are significant memory events of types:
    - breakthrough
    - fragmentation
    - stabilization
    - arc_shift
    - mapper_flip

    Args:
        session_memory: SessionMemory object with events

    Returns:
        List of serialized memory events (chronological order)
    """
    if session_memory is None:
        return []

    # Get all events
    events = getattr(session_memory, 'events', [])

    # Filter to turning point types
    turning_point_types = {
        'breakthrough',
        'fragmentation',
        'stabilization',
        'arc_shift',
        'mapper_flip',
    }

    turning_points = []
    for event in events:
        event_type = getattr(event, 'event_type', None)
        if event_type in turning_point_types:
            # Serialize the event
            if hasattr(event, 'serialize'):
                turning_points.append(event.serialize())
            else:
                # Fallback manual serialization
                turning_points.append({
                    'turn_index': getattr(event, 'turn_index', 0),
                    'event_type': event_type,
                    'description': getattr(event, 'description', ''),
                    'metrics': getattr(event, 'metrics', {}),
                })

    return turning_points


def _build_mapper_journey(mapper_sets: List[Any]) -> List[str]:
    """
    Build chronological mapper journey from mapper sets.

    Converts sets to sorted strings for readability:
    - {"HRM", "LAM"} → "HRM+LAM"
    - {"LCM"} → "LCM"
    - set() → "none"

    Args:
        mapper_sets: List of mapper sets per turn

    Returns:
        List of mapper configuration strings (chronological)
    """
    journey = []

    for mapper_set in mapper_sets:
        if not mapper_set:
            journey.append("none")
        else:
            # Sort and join with "+"
            sorted_mappers = sorted(mapper_set)
            journey.append("+".join(sorted_mappers))

    return journey


def _detect_key_patterns(
    session_memory: Any,
    net_trajectory: str,
    mapper_sets: List[Any],
    mapper_volatility_score: float,
) -> List[str]:
    """
    Detect key symbolic patterns from session data.

    Pattern Rules:
        1. breakthrough_detected: If any breakthrough event exists
        2. instability_present: If any fragmentation event exists
        3. recovery_in_progress: If stabilization event occurred after fragmentation
        4. deepening_arc: If net trajectory improving AND LAM active
        5. volatile_strategy_shift: If mapper_volatility_score > 0.55

    Args:
        session_memory: SessionMemory object with events
        net_trajectory: Net trajectory classification
        mapper_sets: List of mapper sets per turn
        mapper_volatility_score: Mapper volatility score (0-1)

    Returns:
        List of pattern code strings
    """
    patterns = []

    # Extract events from session memory
    events = []
    if session_memory is not None:
        events = getattr(session_memory, 'events', [])

    # Get event types
    event_types = [getattr(e, 'event_type', None) for e in events]

    # Pattern 1: Breakthrough detected
    if 'breakthrough' in event_types:
        patterns.append("breakthrough_detected")

    # Pattern 2: Instability present
    if 'fragmentation' in event_types:
        patterns.append("instability_present")

    # Pattern 3: Recovery in progress
    # Check if stabilization occurred after fragmentation
    frag_indices = [i for i, et in enumerate(event_types) if et == 'fragmentation']
    stab_indices = [i for i, et in enumerate(event_types) if et == 'stabilization']

    if frag_indices and stab_indices:
        # Check if any stabilization occurred after any fragmentation
        last_frag = max(frag_indices)
        last_stab = max(stab_indices)
        if last_stab > last_frag:
            patterns.append("recovery_in_progress")

    # Pattern 4: Deepening arc
    # Check if trajectory improving AND LAM is in the last mapper set
    if net_trajectory == "improving" and mapper_sets:
        last_mapper_set = mapper_sets[-1] if mapper_sets else set()
        if "LAM" in last_mapper_set:
            patterns.append("deepening_arc")

    # Pattern 5: Volatile strategy shift
    if mapper_volatility_score > 0.55:
        patterns.append("volatile_strategy_shift")

    return patterns


def _determine_recommended_style(
    session_policy: Optional[Any],
    overall_state: str,
) -> str:
    """
    Determine recommended interaction style.

    Args:
        session_policy: Optional SessionPolicyFlags object
        overall_state: Overall state classification

    Returns:
        Style recommendation string

    Rules:
        1. Use session_policy.session_recommended_style if available
        2. Otherwise fallback:
           - overall_state == "stable" → "reflective"
           - overall_state == "recovering" → "exploratory"
           - overall_state == "fragmented" → "grounded"
    """
    # Try to get from session policy first
    if session_policy is not None:
        style = getattr(session_policy, 'session_recommended_style', None)
        if style:
            return style

    # Fallback based on overall state
    if overall_state == "stable":
        return "reflective"
    elif overall_state == "recovering":
        return "exploratory"
    elif overall_state == "fragmented":
        return "grounded"
    else:
        return "neutral"


# ============================================================================
# PUBLIC API
# ============================================================================

__all__ = [
    "SessionRecap",
    "compute_session_recap",
]
