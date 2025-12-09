"""
Symbol-U Session Store (In-Memory, Deterministic)

This module provides in-memory session storage and management.
It is designed to be:
- Deterministic (zero-LLM)
- Non-invasive (no external dependencies)
- Thread-safe for concurrent access
- Efficient for typical enterprise workloads

Usage:
    store = SessionStore()
    session = store.create_session(domain="trading")

    # After each turn:
    store.append_turn(session.session_id, unified_output)

    # Get summary:
    summary = compute_session_summary(session)
"""

from typing import Dict, Optional, Any
from uuid import uuid4
from datetime import datetime
import threading

from .session_models import SessionState, SessionSummary


class SessionStore:
    """
    In-memory session storage with deterministic operations.

    This store maintains a dictionary of SessionState objects keyed by session_id.
    All operations are thread-safe using a lock.

    Methods:
        create_session: Create a new session with unique ID
        get: Retrieve a session by ID
        append_turn: Add a turn's unified output to session history
        delete_session: Remove a session (optional cleanup)
        get_all_sessions: Get list of all active session IDs
    """

    def __init__(self) -> None:
        """Initialize the session store with empty state."""
        self._sessions: Dict[str, SessionState] = {}
        self._lock = threading.Lock()

    def create_session(self, domain: str = "generic") -> SessionState:
        """
        Create a new session with unique identifier.

        Args:
            domain: Domain context for the session (default: "generic")

        Returns:
            SessionState object with fresh session_id and timestamp
        """
        with self._lock:
            session_id = str(uuid4())
            state = SessionState(
                session_id=session_id,
                created_at=datetime.utcnow(),
                domain=domain
            )
            self._sessions[session_id] = state
            return state

    def get(self, session_id: str) -> Optional[SessionState]:
        """
        Retrieve a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            SessionState if found, None otherwise
        """
        with self._lock:
            return self._sessions.get(session_id)

    def append_turn(self, session_id: str, payload: Dict[str, Any]) -> None:
        """
        Append a turn's unified output to session history.

        This method extracts structured data from the unified output and
        appends it to the appropriate history lists:
        - coherence_history: Coherence state from payload
        - temporal_history: Temporal arc data
        - routing_history: MLCR routing decisions
        - mapper_history: HRM/LCM/LAM outputs
        - turns: Complete unified output

        Args:
            session_id: Session identifier
            payload: Unified output dictionary from pipeline

        Raises:
            KeyError: If session_id does not exist
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Session {session_id} not found")

            # Append complete turn
            session.turns.append(payload)

            # Extract and append coherence state
            if "coherence" in payload:
                session.coherence_history.append(payload["coherence"])

            # Extract and append temporal arc
            if "temporal_arc" in payload:
                session.temporal_history.append(payload["temporal_arc"])

            # Extract and append routing/tier info
            if "routing" in payload:
                session.routing_history.append(payload["routing"])

            # Extract and append mapper outputs (HRM/LCM/LAM)
            if "mappers" in payload:
                session.mapper_history.append(payload["mappers"])

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session from the store.

        Args:
            session_id: Session identifier

        Returns:
            True if session was deleted, False if not found
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def get_all_sessions(self) -> list[str]:
        """
        Get list of all active session IDs.

        Returns:
            List of session_id strings
        """
        with self._lock:
            return list(self._sessions.keys())

    def session_count(self) -> int:
        """
        Get total number of active sessions.

        Returns:
            Count of sessions in store
        """
        with self._lock:
            return len(self._sessions)


def compute_session_summary(state: SessionState) -> SessionSummary:
    """
    Compute aggregated statistics and trends from a session.

    This function analyzes the session's history to produce:
    - Average coherence trend
    - Persona drift detection
    - Temporal arc patterns
    - Last routing state

    All computations are deterministic and zero-LLM.

    Args:
        state: SessionState with accumulated history

    Returns:
        SessionSummary with aggregated statistics
    """
    total_turns = len(state.turns)

    # Compute coherence trend (average stability across turns)
    coherence_trend = 0.0
    if state.coherence_history:
        # Extract stability scores from coherence history
        stabilities = []
        for coh in state.coherence_history:
            if isinstance(coh, dict) and "stability" in coh:
                stabilities.append(coh["stability"])
        if stabilities:
            coherence_trend = sum(stabilities) / len(stabilities)

    # Compute persona drift (average drift across turns)
    persona_drift_avg = 0.0
    if state.coherence_history:
        # Extract persona drift scores
        drifts = []
        for coh in state.coherence_history:
            if isinstance(coh, dict) and "persona_drift" in coh:
                drifts.append(coh["persona_drift"])
        if drifts:
            persona_drift_avg = sum(drifts) / len(drifts)

    # Compute temporal arc average
    temporal_arc_avg = 0.0
    if state.temporal_history:
        # Extract temporal arc scores
        arcs = []
        for temp in state.temporal_history:
            if isinstance(temp, dict) and "arc_score" in temp:
                arcs.append(temp["arc_score"])
        if arcs:
            temporal_arc_avg = sum(arcs) / len(arcs)

    # Get last tier and domain
    last_tier = "HYBRID"
    last_domain = state.domain
    if state.routing_history:
        last_routing = state.routing_history[-1]
        if isinstance(last_routing, dict):
            last_tier = last_routing.get("tier", "HYBRID")
            last_domain = last_routing.get("domain", state.domain)

    return SessionSummary(
        session_id=state.session_id,
        total_turns=total_turns,
        coherence_trend=coherence_trend,
        persona_drift_avg=persona_drift_avg,
        temporal_arc_avg=temporal_arc_avg,
        last_tier=last_tier,
        last_domain=last_domain,
        created_at=state.created_at,
    )
