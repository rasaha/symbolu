"""
Symbol-U Session Models (Deterministic)

This module defines data models for multi-turn session management.
It enables DILchat and enterprise clients to run conversations with preserved:
- Coherence state
- Temporal tracker state
- Mapper history (HRM, LCM, LAM)
- Domain continuity
- Routing / tier transitions
- Unified output accumulation

Design Principles:
    1. Zero-LLM (fully deterministic)
    2. Non-invasive (does not modify pipeline behavior)
    3. In-memory storage (no external dependencies)
    4. Preserves complete turn-by-turn state
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set
from datetime import datetime


@dataclass
class SessionState:
    """
    Container for all state accumulated across multiple conversation turns.

    This is the primary storage model for a single session. Each turn appends
    new data to the history lists, enabling trend analysis and coherence tracking.

    Attributes:
        session_id: Unique session identifier (UUID4)
        created_at: UTC timestamp when session was created
        domain: Domain context for the session (e.g., "generic", "trading", "therapy")
        coherence_history: List of coherence states from each turn
        temporal_history: List of temporal arc states from each turn
        routing_history: List of routing/tier decisions from each turn
        mapper_history: List of mapper outputs (HRM/LCM/LAM) from each turn
        turns: Complete list of unified outputs from each turn
    """
    session_id: str
    created_at: datetime
    domain: str = "generic"

    # Rolling state accumulators
    coherence_history: List[Dict[str, Any]] = field(default_factory=list)
    temporal_history: List[Dict[str, Any]] = field(default_factory=list)
    routing_history: List[Dict[str, Any]] = field(default_factory=list)
    mapper_history: List[Dict[str, Any]] = field(default_factory=list)
    turns: List[Dict[str, Any]] = field(default_factory=list)

    # Session memory (episodic memory v2.0)
    session_memory: Optional["SessionMemory"] = None


@dataclass
class SessionSummary:
    """
    Aggregated statistics and trends for a session.

    This is computed on-demand from SessionState to provide:
    - Turn count
    - Average coherence trends
    - Persona drift detection
    - Temporal arc patterns
    - Semantic stability metrics
    - Mapper volatility tracking
    - Last routing state

    Attributes:
        session_id: Session identifier
        total_turns: Number of turns completed
        coherence_trend: Average coherence score across all turns
        persona_drift_avg: Average persona drift/change across turns
        temporal_arc_avg: Average temporal arc score across turns
        semantic_stability_score: Average semantic stability (lower = more drift)
        mapper_volatility_score: Volatility in mapper outputs (HRM/LCM/LAM changes)
        last_tier: Last MLCR tier selected (UPPER/LOWER/HYBRID)
        last_domain: Last detected domain
        created_at: Session creation timestamp
    """
    session_id: str
    total_turns: int
    coherence_trend: float
    persona_drift_avg: float
    temporal_arc_avg: float
    semantic_stability_score: float = 0.5
    mapper_volatility_score: float = 0.5
    last_tier: str = "HYBRID"
    last_domain: str = "generic"
    created_at: Optional[datetime] = None

    # Convenience properties for policy layer compatibility
    @property
    def coherence_score(self) -> float:
        """Alias for coherence_trend for policy layer compatibility."""
        return self.coherence_trend

    @property
    def persona_drift_score(self) -> float:
        """Alias for persona_drift_avg for policy layer compatibility."""
        return self.persona_drift_avg

    @property
    def temporal_arc_score(self) -> float:
        """Alias for temporal_arc_avg for policy layer compatibility."""
        return self.temporal_arc_avg

    @property
    def turn_count(self) -> int:
        """Alias for total_turns for policy layer compatibility."""
        return self.total_turns

    # Memory v2.0 fields (timelines for event detection)
    coherence_timeline: List[float] = field(default_factory=list)
    temporal_arc_timeline: List[float] = field(default_factory=list)
    mapper_sets: List[Set[str]] = field(default_factory=list)

    @property
    def last_mapper_set(self) -> Set[str]:
        """Get the most recent mapper set."""
        return self.mapper_sets[-1] if self.mapper_sets else set()
