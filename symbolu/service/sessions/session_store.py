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

from typing import Dict, Optional, Any, Set
from uuid import uuid4
from datetime import datetime
import threading

from .session_models import SessionState, SessionSummary
from .session_memory import SessionMemory, SessionMemoryExtractor


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
        self._memory_extractor = SessionMemoryExtractor()

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
                domain=domain,
                session_memory=SessionMemory(),
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

    def update_session(self, session_id: str, ctx: Any = None) -> None:
        """
        Update session with memory extraction.

        This method should be called after each turn to:
        1. Compute session summary
        2. Extract memory events using SessionMemoryExtractor

        Args:
            session_id: Session identifier
            ctx: Optional pipeline context (for future use)

        Raises:
            KeyError: If session_id does not exist
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Session {session_id} not found")

            # Compute session summary
            summary = compute_session_summary(session)

            # Update memory using extractor
            self._memory_extractor.update_memory(session, summary)


def compute_session_summary(state: SessionState) -> SessionSummary:
    """
    Compute aggregated statistics and trends from a session.

    This function analyzes the session's history to produce:
    - Average coherence trend
    - Persona drift detection
    - Temporal arc patterns
    - Semantic stability metrics
    - Mapper volatility tracking
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
            elif isinstance(coh, dict) and "coherence_score" in coh:
                stabilities.append(coh["coherence_score"])
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

    # Compute semantic stability score
    # Measures consistency of semantic representation across turns
    # Lower score = more semantic drift, Higher score = more stable
    semantic_stability_score = 0.5  # Default neutral score
    if state.coherence_history:
        semantic_scores = []
        for coh in state.coherence_history:
            if isinstance(coh, dict) and "semantic_stability" in coh:
                semantic_scores.append(coh["semantic_stability"])
        if semantic_scores:
            semantic_stability_score = sum(semantic_scores) / len(semantic_scores)
        elif stabilities:
            # Fallback: use coherence trend as proxy for semantic stability
            semantic_stability_score = coherence_trend

    # Compute mapper volatility score
    # Measures how much mapper outputs (HRM/LCM/LAM) change across turns
    # Higher score = more volatility (unstable mapping)
    mapper_volatility_score = 0.5  # Default neutral score
    if len(state.mapper_history) >= 2:
        # Calculate volatility based on mapper activation changes
        volatilities = []
        for i in range(1, len(state.mapper_history)):
            prev_mapper = state.mapper_history[i - 1]
            curr_mapper = state.mapper_history[i]

            if isinstance(prev_mapper, dict) and isinstance(curr_mapper, dict):
                # Track which mappers are active in each turn
                prev_active = set()
                curr_active = set()

                if prev_mapper.get("hrm_active"):
                    prev_active.add("hrm")
                if prev_mapper.get("lcm_active"):
                    prev_active.add("lcm")
                if prev_mapper.get("lam_active"):
                    prev_active.add("lam")

                if curr_mapper.get("hrm_active"):
                    curr_active.add("hrm")
                if curr_mapper.get("lcm_active"):
                    curr_active.add("lcm")
                if curr_mapper.get("lam_active"):
                    curr_active.add("lam")

                # Compute change ratio (0 = no change, 1 = complete change)
                if prev_active or curr_active:
                    symmetric_diff = len(prev_active.symmetric_difference(curr_active))
                    total_unique = len(prev_active.union(curr_active))
                    if total_unique > 0:
                        volatilities.append(symmetric_diff / total_unique)

        if volatilities:
            mapper_volatility_score = sum(volatilities) / len(volatilities)

    # Get last tier and domain
    last_tier = "HYBRID"
    last_domain = state.domain
    if state.routing_history:
        last_routing = state.routing_history[-1]
        if isinstance(last_routing, dict):
            last_tier = last_routing.get("tier", "HYBRID")
            last_domain = last_routing.get("domain", state.domain)

    # Build coherence timeline (Memory v2.0)
    coherence_timeline = []
    for coh in state.coherence_history:
        if isinstance(coh, dict):
            if "stability" in coh:
                coherence_timeline.append(coh["stability"])
            elif "coherence_score" in coh:
                coherence_timeline.append(coh["coherence_score"])

    # Build temporal arc timeline (Memory v2.0)
    temporal_arc_timeline = []
    for temp in state.temporal_history:
        if isinstance(temp, dict) and "arc_score" in temp:
            temporal_arc_timeline.append(temp["arc_score"])

    # Build mapper sets timeline (Memory v2.0)
    mapper_sets = []
    for mapper in state.mapper_history:
        if isinstance(mapper, dict):
            active_set: Set[str] = set()
            if mapper.get("hrm_active"):
                active_set.add("HRM")
            if mapper.get("lcm_active"):
                active_set.add("LCM")
            if mapper.get("lam_active"):
                active_set.add("LAM")
            mapper_sets.append(active_set)

    # Phase 2: Extract formula aggregates from coherence history
    avg_smi = None
    net_delta_smi = None
    avg_bhava_gap = None
    avg_tension_corridor = None

    if state.coherence_history:
        # Extract SMI values for averaging
        smi_values = []
        delta_smi_values = []
        bhava_gap_values = []
        tension_corridor_values = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract avg_smi if available (from CoherenceState aggregates)
                if "avg_smi" in coh and coh["avg_smi"] is not None:
                    smi_values.append(coh["avg_smi"])

                # Extract delta_smi for net calculation
                # Look for delta_smi_history in coherence state
                if "delta_smi_history" in coh:
                    delta_history = coh["delta_smi_history"]
                    if isinstance(delta_history, list):
                        delta_smi_values.extend([d for d in delta_history if d is not None])

                # Extract bhava_gap_history
                if "bhava_gap_history" in coh:
                    gap_history = coh["bhava_gap_history"]
                    if isinstance(gap_history, list):
                        bhava_gap_values.extend([g for g in gap_history if g is not None])

                # Extract tension_corridor_history
                if "tension_corridor_history" in coh:
                    corridor_history = coh["tension_corridor_history"]
                    if isinstance(corridor_history, list):
                        tension_corridor_values.extend([tc for tc in corridor_history if tc is not None])

        # Compute aggregates
        if smi_values:
            avg_smi = sum(smi_values) / len(smi_values)

        if delta_smi_values:
            net_delta_smi = sum(delta_smi_values)

        if bhava_gap_values:
            avg_bhava_gap = sum(bhava_gap_values) / len(bhava_gap_values)

        if tension_corridor_values:
            avg_tension_corridor = sum(tension_corridor_values) / len(tension_corridor_values)

    # Phase 3: Extract derived formula metrics from coherence history
    avg_resonance_index = None
    avg_tension_index = None
    avg_arc_alignment_index = None

    if state.coherence_history:
        # Extract derived metric values for averaging
        resonance_values = []
        tension_index_values = []
        arc_alignment_values = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract resonance_index
                if "resonance_index" in coh and coh["resonance_index"] is not None:
                    resonance_values.append(coh["resonance_index"])

                # Extract tension_index
                if "tension_index" in coh and coh["tension_index"] is not None:
                    tension_index_values.append(coh["tension_index"])

                # Extract arc_alignment_index
                if "arc_alignment_index" in coh and coh["arc_alignment_index"] is not None:
                    arc_alignment_values.append(coh["arc_alignment_index"])

        # Compute averages
        if resonance_values:
            avg_resonance_index = sum(resonance_values) / len(resonance_values)

        if tension_index_values:
            avg_tension_index = sum(tension_index_values) / len(tension_index_values)

        if arc_alignment_values:
            avg_arc_alignment_index = sum(arc_alignment_values) / len(arc_alignment_values)

    # Phase 8: Extract Guna/Kosha resonance metrics from coherence history
    avg_guna_resonance = None
    avg_kosha_resonance = None

    if state.coherence_history:
        # Extract Guna/Kosha resonance values for averaging
        guna_resonance_values = []
        kosha_resonance_values = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract guna_resonance_index
                if "guna_resonance_index" in coh and coh["guna_resonance_index"] is not None:
                    guna_resonance_values.append(coh["guna_resonance_index"])

                # Extract kosha_resonance_index
                if "kosha_resonance_index" in coh and coh["kosha_resonance_index"] is not None:
                    kosha_resonance_values.append(coh["kosha_resonance_index"])

        # Compute averages
        if guna_resonance_values:
            avg_guna_resonance = sum(guna_resonance_values) / len(guna_resonance_values)

        if kosha_resonance_values:
            avg_kosha_resonance = sum(kosha_resonance_values) / len(kosha_resonance_values)

    return SessionSummary(
        session_id=state.session_id,
        total_turns=total_turns,
        coherence_trend=coherence_trend,
        persona_drift_avg=persona_drift_avg,
        temporal_arc_avg=temporal_arc_avg,
        semantic_stability_score=semantic_stability_score,
        mapper_volatility_score=mapper_volatility_score,
        last_tier=last_tier,
        last_domain=last_domain,
        created_at=state.created_at,
        coherence_timeline=coherence_timeline,
        temporal_arc_timeline=temporal_arc_timeline,
        mapper_sets=mapper_sets,
        avg_smi=avg_smi,
        net_delta_smi=net_delta_smi,
        avg_bhava_gap=avg_bhava_gap,
        avg_tension_corridor=avg_tension_corridor,
        avg_resonance_index=avg_resonance_index,
        avg_tension_index=avg_tension_index,
        avg_arc_alignment_index=avg_arc_alignment_index,
        avg_guna_resonance=avg_guna_resonance,
        avg_kosha_resonance=avg_kosha_resonance,
    )
