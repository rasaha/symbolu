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
from typing import Dict, Any, List, Optional
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


@dataclass
class SessionSummary:
    """
    Aggregated statistics and trends for a session.

    This is computed on-demand from SessionState to provide:
    - Turn count
    - Average coherence trends
    - Persona drift detection
    - Temporal arc patterns
    - Last routing state

    Attributes:
        session_id: Session identifier
        total_turns: Number of turns completed
        coherence_trend: Average coherence score across all turns
        persona_drift_avg: Average persona drift/change across turns
        temporal_arc_avg: Average temporal arc score across turns
        last_tier: Last MLCR tier selected (UPPER/LOWER/HYBRID)
        last_domain: Last detected domain
        created_at: Session creation timestamp
    """
    session_id: str
    total_turns: int
    coherence_trend: float
    persona_drift_avg: float
    temporal_arc_avg: float
    last_tier: str
    last_domain: str
    created_at: datetime
