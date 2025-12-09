"""
Symbol-U Session Memory v2.0 — Episodic Memory + Turning Points + Symbolic Anchors

This module implements a deterministic episodic memory system for multi-turn sessions.
It detects and records significant events in conversation trajectories, creating
memory anchors that track breakthroughs, fragmentations, stabilizations, arc shifts,
and mapper configuration changes.

Design Principles:
    1. Zero-LLM (purely rule-based, deterministic)
    2. Non-invasive (does not modify pipeline behavior)
    3. Additive (optional, not required for core operation)
    4. Deterministic (same input produces same output)

Memory Event Types:
    - Breakthrough: Notable upward clarity shift detected
    - Fragmentation: Conversation stability momentarily broke
    - Stabilization: Conversation trajectory stabilizing
    - Arc Shift: Long-arc trajectory shifted direction
    - Mapper Flip: Mapper configuration changed

Usage:
    from symbolu.service.sessions.session_memory import (
        MemoryEntry,
        SessionMemory,
        SessionMemoryExtractor
    )

    # Create memory instance
    memory = SessionMemory()

    # Extract events from session state
    extractor = SessionMemoryExtractor()
    extractor.update_memory(session_state, session_summary)

    # Query memory
    recent_events = memory.get_recent(5)
    breakthroughs = memory.get_by_type("breakthrough")
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set


# ============================================================================
# Memory Entry Dataclass
# ============================================================================


@dataclass
class MemoryEntry:
    """
    Represents a single episodic memory event in a conversation session.

    Memory entries capture significant turning points and state changes
    that occur during multi-turn conversations. Each entry records:
    - When the event occurred (turn index)
    - What type of event it was (breakthrough, fragmentation, etc.)
    - A deterministic description
    - Raw metrics that triggered the event

    Attributes:
        turn_index: The turn number when this event occurred (0-indexed)
        event_type: Type of event (breakthrough, fragmentation, stabilization, arc_shift, mapper_flip)
        description: Human-readable deterministic description of the event
        metrics: Dictionary of raw metrics that triggered this event
                 (e.g., {"coherence_score": 0.85, "coherence_delta": 0.15, ...})
        smi: Optional SMI value at time of event (Phase 2 context)
        tension_corridor: Optional tension corridor at time of event (Phase 2 context)
    """
    turn_index: int
    event_type: str
    description: str
    metrics: Dict[str, float] = field(default_factory=dict)

    # Phase 2 formula context (observation only)
    smi: Optional[float] = None
    tension_corridor: Optional[float] = None

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize memory entry to JSON-safe dictionary.

        Returns:
            Dictionary with all memory entry fields
        """
        result = {
            "turn_index": self.turn_index,
            "event_type": self.event_type,
            "description": self.description,
            "metrics": self.metrics,
        }

        # Include Phase 2 formula context if available
        if self.smi is not None:
            result["smi"] = self.smi
        if self.tension_corridor is not None:
            result["tension_corridor"] = self.tension_corridor

        return result


# ============================================================================
# Session Memory Dataclass
# ============================================================================


@dataclass
class SessionMemory:
    """
    Container for all episodic memory events in a session.

    SessionMemory maintains an ordered list of MemoryEntry objects
    representing significant events that occurred during the conversation.
    It provides methods for adding events and querying by recency or type.

    Attributes:
        events: Ordered list of MemoryEntry objects (chronological)
    """
    events: List[MemoryEntry] = field(default_factory=list)

    def add_event(self, entry: MemoryEntry) -> None:
        """
        Add a new memory event to the session.

        Events are appended in chronological order.

        Args:
            entry: MemoryEntry to add
        """
        self.events.append(entry)

    def get_recent(self, n: int) -> List[MemoryEntry]:
        """
        Get the N most recent memory events.

        Args:
            n: Number of recent events to retrieve

        Returns:
            List of up to N most recent MemoryEntry objects
        """
        return self.events[-n:] if n > 0 else []

    def get_by_type(self, event_type: str) -> List[MemoryEntry]:
        """
        Get all memory events of a specific type.

        Args:
            event_type: Event type to filter by (breakthrough, fragmentation, etc.)

        Returns:
            List of MemoryEntry objects matching the event type
        """
        return [e for e in self.events if e.event_type == event_type]

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize session memory to JSON-safe dictionary.

        Returns:
            Dictionary with list of serialized events
        """
        return {
            "events": [e.serialize() for e in self.events],
            "event_count": len(self.events),
        }


# ============================================================================
# Session Memory Extractor
# ============================================================================


class SessionMemoryExtractor:
    """
    Deterministic event extraction engine for session memory.

    This class analyzes session state and summary data to detect significant
    events using rule-based thresholds. All detection is deterministic and
    zero-LLM.

    Detection Rules:
        1. Breakthrough: coherence ↑ >= 0.12, temporal_arc >= 0.55, persona_drift <= 0.45
        2. Fragmentation: coherence ↓ >= 0.15 OR semantic_stability < 0.40 OR persona_drift > 0.55
        3. Stabilization: coherence rises across 3 consecutive turns AND mapper_volatility < 0.40
        4. Arc Shift: temporal_arc changes direction (magnitude >= 0.10)
        5. Mapper Flip: Active mapper set changes

    Usage:
        extractor = SessionMemoryExtractor()
        extractor.update_memory(session_state, session_summary)
    """

    # Event detection thresholds
    BREAKTHROUGH_COHERENCE_DELTA = 0.12
    BREAKTHROUGH_TEMPORAL_ARC_MIN = 0.55
    BREAKTHROUGH_PERSONA_DRIFT_MAX = 0.45

    FRAGMENTATION_COHERENCE_DROP = 0.15
    FRAGMENTATION_SEMANTIC_STABILITY_MAX = 0.40
    FRAGMENTATION_PERSONA_DRIFT_MIN = 0.55

    STABILIZATION_MAPPER_VOLATILITY_MAX = 0.40
    STABILIZATION_CONSECUTIVE_RISES = 3

    ARC_SHIFT_MIN_MAGNITUDE = 0.10

    def update_memory(self, state: "SessionState", summary: "SessionSummary") -> None:
        """
        Update session memory by detecting events from current state.

        This is the main public API for memory extraction. It analyzes
        the session's accumulated history to detect new events and appends
        them to state.session_memory.

        Args:
            state: SessionState with accumulated history
            summary: SessionSummary with computed aggregates

        Note:
            Modifies state.session_memory in place by appending new events.
        """
        # Ensure session_memory exists
        if state.session_memory is None:
            state.session_memory = SessionMemory()

        # Get current turn index (0-indexed)
        current_turn = len(state.turns) - 1
        if current_turn < 0:
            return  # No turns yet

        # Detect events using rule-based logic
        events = self._detect_events(state, summary, current_turn)

        # Append new events to memory
        for event in events:
            state.session_memory.add_event(event)

    def _detect_events(
        self,
        state: "SessionState",
        summary: "SessionSummary",
        current_turn: int,
    ) -> List[MemoryEntry]:
        """
        Detect all events for the current turn.

        Args:
            state: SessionState with accumulated history
            summary: SessionSummary with computed aggregates
            current_turn: Current turn index (0-indexed)

        Returns:
            List of MemoryEntry objects for detected events
        """
        events = []

        # Need at least 1 turn to detect events
        if current_turn < 0:
            return events

        # Extract timelines from summary
        coherence_timeline = getattr(summary, 'coherence_timeline', [])
        temporal_arc_timeline = getattr(summary, 'temporal_arc_timeline', [])
        mapper_sets = getattr(summary, 'mapper_sets', [])

        # Detect Breakthrough
        breakthrough = self._detect_breakthrough(
            coherence_timeline,
            temporal_arc_timeline,
            summary.persona_drift_score,
            current_turn,
        )
        if breakthrough:
            events.append(breakthrough)

        # Detect Fragmentation
        fragmentation = self._detect_fragmentation(
            coherence_timeline,
            summary.semantic_stability_score,
            summary.persona_drift_score,
            current_turn,
        )
        if fragmentation:
            events.append(fragmentation)

        # Detect Stabilization (requires at least 3 turns)
        stabilization = self._detect_stabilization(
            coherence_timeline,
            summary.mapper_volatility_score,
            current_turn,
        )
        if stabilization:
            events.append(stabilization)

        # Detect Arc Shift
        arc_shift = self._detect_arc_shift(
            temporal_arc_timeline,
            current_turn,
        )
        if arc_shift:
            events.append(arc_shift)

        # Detect Mapper Flip
        mapper_flip = self._detect_mapper_flip(
            mapper_sets,
            current_turn,
        )
        if mapper_flip:
            events.append(mapper_flip)

        return events

    def _detect_breakthrough(
        self,
        coherence_timeline: List[float],
        temporal_arc_timeline: List[float],
        persona_drift_score: float,
        current_turn: int,
    ) -> Optional[MemoryEntry]:
        """
        Detect breakthrough event.

        Breakthrough occurs when:
        - coherence_score increases by >= 0.12 from previous turn
        - AND temporal_arc_score >= 0.55
        - AND persona_drift_score <= 0.45

        Args:
            coherence_timeline: List of coherence scores per turn
            temporal_arc_timeline: List of temporal arc scores per turn
            persona_drift_score: Current persona drift score
            current_turn: Current turn index

        Returns:
            MemoryEntry if breakthrough detected, None otherwise
        """
        # Need at least 2 turns to compare
        if len(coherence_timeline) < 2 or len(temporal_arc_timeline) < 1:
            return None

        current_coherence = coherence_timeline[-1]
        prev_coherence = coherence_timeline[-2]
        coherence_delta = current_coherence - prev_coherence

        current_temporal_arc = temporal_arc_timeline[-1] if temporal_arc_timeline else 0.0

        # Check breakthrough conditions
        if (coherence_delta >= self.BREAKTHROUGH_COHERENCE_DELTA and
            current_temporal_arc >= self.BREAKTHROUGH_TEMPORAL_ARC_MIN and
            persona_drift_score <= self.BREAKTHROUGH_PERSONA_DRIFT_MAX):

            return MemoryEntry(
                turn_index=current_turn,
                event_type="breakthrough",
                description="Notable upward clarity shift detected.",
                metrics={
                    "coherence_score": current_coherence,
                    "coherence_delta": coherence_delta,
                    "temporal_arc_score": current_temporal_arc,
                    "persona_drift_score": persona_drift_score,
                },
            )

        return None

    def _detect_fragmentation(
        self,
        coherence_timeline: List[float],
        semantic_stability_score: float,
        persona_drift_score: float,
        current_turn: int,
    ) -> Optional[MemoryEntry]:
        """
        Detect fragmentation event.

        Fragmentation occurs when:
        - coherence_score drops by >= 0.15
        - OR semantic_stability_score < 0.40
        - OR persona_drift_score > 0.55

        Args:
            coherence_timeline: List of coherence scores per turn
            semantic_stability_score: Current semantic stability score
            persona_drift_score: Current persona drift score
            current_turn: Current turn index

        Returns:
            MemoryEntry if fragmentation detected, None otherwise
        """
        # Check if we have enough data
        if len(coherence_timeline) < 1:
            return None

        current_coherence = coherence_timeline[-1]
        coherence_drop = 0.0

        # Calculate coherence drop if we have previous turn
        if len(coherence_timeline) >= 2:
            prev_coherence = coherence_timeline[-2]
            coherence_drop = prev_coherence - current_coherence

        # Check fragmentation conditions
        fragmented = False
        reason = ""

        if coherence_drop >= self.FRAGMENTATION_COHERENCE_DROP:
            fragmented = True
            reason = f"coherence_drop={coherence_drop:.2f}"
        elif semantic_stability_score < self.FRAGMENTATION_SEMANTIC_STABILITY_MAX:
            fragmented = True
            reason = f"semantic_stability={semantic_stability_score:.2f}"
        elif persona_drift_score > self.FRAGMENTATION_PERSONA_DRIFT_MIN:
            fragmented = True
            reason = f"persona_drift={persona_drift_score:.2f}"

        if fragmented:
            return MemoryEntry(
                turn_index=current_turn,
                event_type="fragmentation",
                description="Conversation stability momentarily broke.",
                metrics={
                    "coherence_score": current_coherence,
                    "coherence_drop": coherence_drop,
                    "semantic_stability_score": semantic_stability_score,
                    "persona_drift_score": persona_drift_score,
                    "reason": reason,
                },
            )

        return None

    def _detect_stabilization(
        self,
        coherence_timeline: List[float],
        mapper_volatility_score: float,
        current_turn: int,
    ) -> Optional[MemoryEntry]:
        """
        Detect stabilization event.

        Stabilization occurs when:
        - coherence_score rises across 3 consecutive turns
        - AND mapper_volatility_score < 0.40

        Args:
            coherence_timeline: List of coherence scores per turn
            mapper_volatility_score: Current mapper volatility score
            current_turn: Current turn index

        Returns:
            MemoryEntry if stabilization detected, None otherwise
        """
        # Need at least 3 turns for consecutive rises
        if len(coherence_timeline) < self.STABILIZATION_CONSECUTIVE_RISES:
            return None

        # Check if coherence has risen for last 3 turns
        consecutive_rises = True
        for i in range(len(coherence_timeline) - self.STABILIZATION_CONSECUTIVE_RISES + 1, len(coherence_timeline)):
            if i <= 0:
                continue
            if coherence_timeline[i] <= coherence_timeline[i - 1]:
                consecutive_rises = False
                break

        # Check stabilization conditions
        if consecutive_rises and mapper_volatility_score < self.STABILIZATION_MAPPER_VOLATILITY_MAX:
            return MemoryEntry(
                turn_index=current_turn,
                event_type="stabilization",
                description="Conversation trajectory stabilizing.",
                metrics={
                    "coherence_score": coherence_timeline[-1],
                    "mapper_volatility_score": mapper_volatility_score,
                    "consecutive_rises": self.STABILIZATION_CONSECUTIVE_RISES,
                },
            )

        return None

    def _detect_arc_shift(
        self,
        temporal_arc_timeline: List[float],
        current_turn: int,
    ) -> Optional[MemoryEntry]:
        """
        Detect arc shift event.

        Arc shift occurs when:
        - temporal_arc_score changes direction (rise → fall OR fall → rise)
        - change magnitude >= 0.10

        Args:
            temporal_arc_timeline: List of temporal arc scores per turn
            current_turn: Current turn index

        Returns:
            MemoryEntry if arc shift detected, None otherwise
        """
        # Need at least 3 turns to detect direction change
        if len(temporal_arc_timeline) < 3:
            return None

        current_arc = temporal_arc_timeline[-1]
        prev_arc = temporal_arc_timeline[-2]
        prev_prev_arc = temporal_arc_timeline[-3]

        # Calculate deltas
        prev_delta = prev_arc - prev_prev_arc
        current_delta = current_arc - prev_arc

        # Check for direction change
        direction_changed = (
            (prev_delta > 0 and current_delta < 0) or  # Rise → Fall
            (prev_delta < 0 and current_delta > 0)     # Fall → Rise
        )

        # Check magnitude
        magnitude = abs(current_delta)

        if direction_changed and magnitude >= self.ARC_SHIFT_MIN_MAGNITUDE:
            direction = "rise→fall" if prev_delta > 0 else "fall→rise"
            return MemoryEntry(
                turn_index=current_turn,
                event_type="arc_shift",
                description="Long-arc trajectory shifted direction.",
                metrics={
                    "temporal_arc_score": current_arc,
                    "arc_delta": current_delta,
                    "direction": direction,
                    "magnitude": magnitude,
                },
            )

        return None

    def _detect_mapper_flip(
        self,
        mapper_sets: List[Set[str]],
        current_turn: int,
    ) -> Optional[MemoryEntry]:
        """
        Detect mapper flip event.

        Mapper flip occurs when:
        - Active mapper set changes (e.g., LAM → HRM, HRM+LCM → LCM only)

        Args:
            mapper_sets: List of mapper sets per turn (e.g., [{"HRM"}, {"LCM"}, {"LAM", "HRM"}])
            current_turn: Current turn index

        Returns:
            MemoryEntry if mapper flip detected, None otherwise
        """
        # Need at least 2 turns to compare
        if len(mapper_sets) < 2:
            return None

        current_mappers = mapper_sets[-1]
        prev_mappers = mapper_sets[-2]

        # Check if mapper set changed
        if current_mappers != prev_mappers:
            prev_str = ",".join(sorted(prev_mappers)) if prev_mappers else "none"
            current_str = ",".join(sorted(current_mappers)) if current_mappers else "none"

            return MemoryEntry(
                turn_index=current_turn,
                event_type="mapper_flip",
                description="Mapper configuration changed.",
                metrics={
                    "prev_mappers": prev_str,
                    "current_mappers": current_str,
                },
            )

        return None


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    "MemoryEntry",
    "SessionMemory",
    "SessionMemoryExtractor",
]
