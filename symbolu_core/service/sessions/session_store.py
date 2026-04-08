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
from collections import Counter

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

    # Phase 14: Extract Vritti Momentum & Arc-Tension Harmonizer from coherence history
    avg_vritti_momentum = None
    max_vritti_momentum = None
    min_vritti_momentum = None
    avg_arc_tension_harmonizer = None
    max_arc_tension_harmonizer = None
    min_arc_tension_harmonizer = None

    if state.coherence_history:
        # Extract VMF and ATH values
        vmf_values = []
        ath_values = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract avg_vritti_momentum from CoherenceState aggregates
                if "avg_vritti_momentum" in coh and coh["avg_vritti_momentum"] is not None:
                    vmf_values.append(coh["avg_vritti_momentum"])

                # Extract avg_arc_tension_harmonizer from CoherenceState aggregates
                if "avg_arc_tension_harmonizer" in coh and coh["avg_arc_tension_harmonizer"] is not None:
                    ath_values.append(coh["avg_arc_tension_harmonizer"])

                # Also extract from histories for min/max calculation
                if "vritti_momentum_history" in coh:
                    vmf_history = coh["vritti_momentum_history"]
                    if isinstance(vmf_history, list):
                        vmf_values.extend([v for v in vmf_history if v is not None])

                if "arc_tension_harmonizer_history" in coh:
                    ath_history = coh["arc_tension_harmonizer_history"]
                    if isinstance(ath_history, list):
                        ath_values.extend([a for a in ath_history if a is not None])

        # Compute aggregates
        if vmf_values:
            avg_vritti_momentum = sum(vmf_values) / len(vmf_values)
            max_vritti_momentum = max(vmf_values)
            min_vritti_momentum = min(vmf_values)

        if ath_values:
            avg_arc_tension_harmonizer = sum(ath_values) / len(ath_values)
            max_arc_tension_harmonizer = max(ath_values)
            min_arc_tension_harmonizer = min(ath_values)

    # Phase 18: Extract Temporal Entropy Differential from coherence history
    avg_temporal_entropy_diff = None
    avg_temporal_entropy_volatility = None
    temporal_entropy_regime = None

    if state.coherence_history:
        # Extract temporal entropy diff and volatility values
        entropy_diff_values = []
        entropy_volatility_values = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract temporal_entropy_diff from CoherenceState
                if "temporal_entropy_diff" in coh and coh["temporal_entropy_diff"] is not None:
                    entropy_diff_values.append(coh["temporal_entropy_diff"])

                # Extract temporal_entropy_volatility from CoherenceState
                if "temporal_entropy_volatility" in coh and coh["temporal_entropy_volatility"] is not None:
                    entropy_volatility_values.append(coh["temporal_entropy_volatility"])

                # Also extract from histories for better coverage
                if "temporal_entropy_diff_history" in coh:
                    diff_history = coh["temporal_entropy_diff_history"]
                    if isinstance(diff_history, list):
                        entropy_diff_values.extend([d for d in diff_history if d is not None])

                if "temporal_entropy_volatility_history" in coh:
                    volatility_history = coh["temporal_entropy_volatility_history"]
                    if isinstance(volatility_history, list):
                        entropy_volatility_values.extend([v for v in volatility_history if v is not None])

        # Compute aggregates
        if entropy_diff_values:
            avg_temporal_entropy_diff = sum(entropy_diff_values) / len(entropy_diff_values)

        if entropy_volatility_values:
            avg_temporal_entropy_volatility = sum(entropy_volatility_values) / len(entropy_volatility_values)

        # Classify temporal entropy regime based on average volatility
        if avg_temporal_entropy_volatility is not None:
            if avg_temporal_entropy_volatility < 0.25:
                temporal_entropy_regime = "stable"
            elif avg_temporal_entropy_volatility < 0.60:
                temporal_entropy_regime = "transition"
            else:
                temporal_entropy_regime = "volatile"

    # Phase 21: Extract Mirror-Time Loop from coherence history
    avg_loop_alignment = None
    avg_loop_tension = None
    avg_reversal_probability = None
    dominant_loop_stability_band = None
    reversal_probability_trend = None

    if state.coherence_history:
        # Extract loop alignment, tension, reversal probability values
        loop_alignment_values = []
        loop_tension_values = []
        reversal_probability_values = []
        stability_band_values = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract avg_loop_alignment from CoherenceState
                if "avg_loop_alignment" in coh and coh["avg_loop_alignment"] is not None:
                    loop_alignment_values.append(coh["avg_loop_alignment"])

                # Extract avg_loop_tension from CoherenceState
                if "avg_loop_tension" in coh and coh["avg_loop_tension"] is not None:
                    loop_tension_values.append(coh["avg_loop_tension"])

                # Extract avg_reversal_probability from CoherenceState
                if "avg_reversal_probability" in coh and coh["avg_reversal_probability"] is not None:
                    reversal_probability_values.append(coh["avg_reversal_probability"])

                # Also extract from histories for better coverage
                if "loop_alignment_history" in coh:
                    alignment_history = coh["loop_alignment_history"]
                    if isinstance(alignment_history, list):
                        loop_alignment_values.extend([a for a in alignment_history if a is not None])

                if "loop_tension_history" in coh:
                    tension_history = coh["loop_tension_history"]
                    if isinstance(tension_history, list):
                        loop_tension_values.extend([t for t in tension_history if t is not None])

                if "reversal_probability_history" in coh:
                    reversal_history = coh["reversal_probability_history"]
                    if isinstance(reversal_history, list):
                        reversal_probability_values.extend([r for r in reversal_history if r is not None])

                # Extract stability band values
                if "stability_band_history" in coh:
                    band_history = coh["stability_band_history"]
                    if isinstance(band_history, list):
                        stability_band_values.extend([b for b in band_history if b is not None])

        # Compute aggregates
        if loop_alignment_values:
            avg_loop_alignment = sum(loop_alignment_values) / len(loop_alignment_values)

        if loop_tension_values:
            avg_loop_tension = sum(loop_tension_values) / len(loop_tension_values)

        if reversal_probability_values:
            avg_reversal_probability = sum(reversal_probability_values) / len(reversal_probability_values)

        # Determine dominant stability band (most frequent)
        if stability_band_values:
            from collections import Counter
            band_counts = Counter(stability_band_values)
            dominant_loop_stability_band = band_counts.most_common(1)[0][0]

        # Determine reversal probability trend
        if reversal_probability_values and len(reversal_probability_values) >= 3:
            # Compare first third vs last third to detect trend
            third = len(reversal_probability_values) // 3
            first_third_avg = sum(reversal_probability_values[:third]) / third if third > 0 else 0.0
            last_third_avg = sum(reversal_probability_values[-third:]) / third if third > 0 else 0.0

            # Threshold for detecting trend
            if last_third_avg - first_third_avg > 0.1:
                reversal_probability_trend = "increasing"
            elif first_third_avg - last_third_avg > 0.1:
                reversal_probability_trend = "decreasing"
            else:
                reversal_probability_trend = "stable"

    # Phase 22: Extract Mirror-Time Cycles from coherence history
    dominant_cycle_type = None
    dominant_cycle_stability_band = None
    avg_cycle_alignment = None
    avg_cycle_tension = None
    avg_cycle_reversal_probability = None
    cycle_count = 0

    if state.coherence_history:
        # Extract cycle metrics from CoherenceState
        cycle_type_values = []
        cycle_stability_band_values = []
        cycle_alignment_values = []
        cycle_tension_values = []
        cycle_reversal_probability_values = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract dominant_cycle_type from CoherenceState
                if "dominant_cycle_type" in coh and coh["dominant_cycle_type"] is not None:
                    cycle_type_values.append(coh["dominant_cycle_type"])

                # Extract dominant_cycle_stability_band from CoherenceState
                if "dominant_cycle_stability_band" in coh and coh["dominant_cycle_stability_band"] is not None:
                    cycle_stability_band_values.append(coh["dominant_cycle_stability_band"])

                # Extract avg_cycle_alignment from CoherenceState
                if "avg_cycle_alignment" in coh and coh["avg_cycle_alignment"] is not None:
                    cycle_alignment_values.append(coh["avg_cycle_alignment"])

                # Extract avg_cycle_tension from CoherenceState
                if "avg_cycle_tension" in coh and coh["avg_cycle_tension"] is not None:
                    cycle_tension_values.append(coh["avg_cycle_tension"])

                # Extract avg_cycle_reversal_probability from CoherenceState
                if "avg_cycle_reversal_probability" in coh and coh["avg_cycle_reversal_probability"] is not None:
                    cycle_reversal_probability_values.append(coh["avg_cycle_reversal_probability"])

                # Count cycles from mirror_cycle_history
                if "mirror_cycle_history" in coh:
                    cycle_history = coh["mirror_cycle_history"]
                    if isinstance(cycle_history, list):
                        cycle_count += len(cycle_history)

        # Compute aggregates
        # Determine dominant cycle type (most frequent)
        if cycle_type_values:
            from collections import Counter
            type_counts = Counter(cycle_type_values)
            dominant_cycle_type = type_counts.most_common(1)[0][0]

        # Determine dominant cycle stability band (most frequent)
        if cycle_stability_band_values:
            from collections import Counter
            band_counts = Counter(cycle_stability_band_values)
            dominant_cycle_stability_band = band_counts.most_common(1)[0][0]

        # Compute average cycle alignment
        if cycle_alignment_values:
            avg_cycle_alignment = sum(cycle_alignment_values) / len(cycle_alignment_values)

        # Compute average cycle tension
        if cycle_tension_values:
            avg_cycle_tension = sum(cycle_tension_values) / len(cycle_tension_values)

        # Compute average cycle reversal probability
        if cycle_reversal_probability_values:
            avg_cycle_reversal_probability = sum(cycle_reversal_probability_values) / len(cycle_reversal_probability_values)

    # Phase 23: Extract Cause-Effect Inversion Analytics from coherence history
    avg_inversion_score_val = None
    dominant_inversion_band = None
    cause_chain_stability_avg_val = None
    inversion_pattern_tags = []

    if state.coherence_history:
        # Extract inversion metrics from CoherenceState
        inversion_score_values = []
        inversion_band_values = []
        cause_chain_stability_values = []
        all_inversion_notes = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract avg_inversion_score from CoherenceState
                if "avg_inversion_score" in coh and coh["avg_inversion_score"] is not None:
                    inversion_score_values.append(coh["avg_inversion_score"])

                # Extract current_inversion_band from CoherenceState
                if "current_inversion_band" in coh and coh["current_inversion_band"] is not None:
                    inversion_band_values.append(coh["current_inversion_band"])

                # Extract cause_chain_stability_avg from CoherenceState
                if "cause_chain_stability_avg" in coh and coh["cause_chain_stability_avg"] is not None:
                    cause_chain_stability_values.append(coh["cause_chain_stability_avg"])

                # Also extract from cause_effect_inversion_history for detailed analysis
                if "cause_effect_inversion_history" in coh:
                    inversion_history = coh["cause_effect_inversion_history"]
                    if isinstance(inversion_history, list):
                        for snapshot in inversion_history:
                            if snapshot is not None and hasattr(snapshot, 'inversion_score'):
                                inversion_score_values.append(snapshot.inversion_score)
                            if snapshot is not None and hasattr(snapshot, 'inversion_band'):
                                inversion_band_values.append(snapshot.inversion_band)
                            if snapshot is not None and hasattr(snapshot, 'cause_chain_stability'):
                                cause_chain_stability_values.append(snapshot.cause_chain_stability)
                            if snapshot is not None and hasattr(snapshot, 'notes'):
                                all_inversion_notes.extend(snapshot.notes)

        # Compute aggregates
        # Average inversion score
        if inversion_score_values:
            avg_inversion_score_val = sum(inversion_score_values) / len(inversion_score_values)

        # Dominant inversion band (most frequent)
        if inversion_band_values:
            from collections import Counter
            band_counts = Counter(inversion_band_values)
            dominant_inversion_band = band_counts.most_common(1)[0][0]

        # Average cause-chain stability
        if cause_chain_stability_values:
            cause_chain_stability_avg_val = sum(cause_chain_stability_values) / len(cause_chain_stability_values)

        # Collect unique inversion pattern tags (deduplicate)
        if all_inversion_notes:
            inversion_pattern_tags = list(set(all_inversion_notes))

    # Phase 24: Extract Resonance Weighting metrics from coherence history
    avg_resonance_entropy_val = None
    dominant_resonance_metrics_list = []
    resonance_weighting_notes_list = []

    if state.coherence_history:
        # Extract resonance weighting metrics from CoherenceState
        resonance_entropy_values = []
        all_dominant_metrics = []
        all_resonance_notes = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract current_resonance_entropy from CoherenceState
                if "current_resonance_entropy" in coh and coh["current_resonance_entropy"] is not None:
                    resonance_entropy_values.append(coh["current_resonance_entropy"])

                # Extract dominant_resonance_metrics from CoherenceState
                if "dominant_resonance_metrics" in coh and coh["dominant_resonance_metrics"]:
                    if isinstance(coh["dominant_resonance_metrics"], list):
                        all_dominant_metrics.extend(coh["dominant_resonance_metrics"])

                # Also extract from resonance_weighting_history for detailed analysis
                if "resonance_weighting_history" in coh:
                    weighting_history = coh["resonance_weighting_history"]
                    if isinstance(weighting_history, list):
                        for snapshot in weighting_history:
                            # Handle both dict and object snapshots
                            if snapshot is not None:
                                if isinstance(snapshot, dict):
                                    if "notes" in snapshot and snapshot["notes"]:
                                        all_resonance_notes.extend(snapshot["notes"])
                                    if "dominant_metrics" in snapshot and snapshot["dominant_metrics"]:
                                        if isinstance(snapshot["dominant_metrics"], dict):
                                            all_dominant_metrics.extend(snapshot["dominant_metrics"].keys())
                                elif hasattr(snapshot, "notes") and snapshot.notes:
                                    all_resonance_notes.extend(snapshot.notes)
                                    if hasattr(snapshot, "dominant_metrics") and snapshot.dominant_metrics:
                                        all_dominant_metrics.extend(snapshot.dominant_metrics.keys())

        # Compute aggregates
        # Average resonance entropy
        if resonance_entropy_values:
            avg_resonance_entropy_val = sum(resonance_entropy_values) / len(resonance_entropy_values)

        # Dominant resonance metrics (most frequent, limited to top N)
        if all_dominant_metrics:
            from collections import Counter
            metric_counts = Counter(all_dominant_metrics)
            # Get top 5 most common metrics
            dominant_resonance_metrics_list = [metric for metric, _ in metric_counts.most_common(5)]

        # Collect unique resonance weighting notes (deduplicate and sort for determinism)
        if all_resonance_notes:
            resonance_weighting_notes_list = sorted(set(all_resonance_notes))

    # Phase 26: Extract Unified Consciousness Formula (UCF) metrics from coherence history
    avg_coi_val = None
    avg_csi_val = None
    avg_cip_val = None
    ucf_entropy_band_val = None
    dominant_ucf_signals_list = []
    ucf_notes_list = []

    if state.coherence_history:
        # Extract UCF metrics from CoherenceState
        coi_values = []
        csi_values = []
        cip_values = []
        ucf_entropy_values = []
        all_ucf_notes = []
        all_dominant_signals = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract current_coi, current_csi, current_cip from CoherenceState
                if "current_coi" in coh and coh["current_coi"] is not None:
                    coi_values.append(coh["current_coi"])
                if "current_csi" in coh and coh["current_csi"] is not None:
                    csi_values.append(coh["current_csi"])
                if "current_cip" in coh and coh["current_cip"] is not None:
                    cip_values.append(coh["current_cip"])

                # Extract ucf_entropy from CoherenceState
                if "ucf_entropy" in coh and coh["ucf_entropy"] is not None:
                    ucf_entropy_values.append(coh["ucf_entropy"])

                # Extract ucf_notes from CoherenceState
                if "ucf_notes" in coh and coh["ucf_notes"]:
                    if isinstance(coh["ucf_notes"], list):
                        all_ucf_notes.extend(coh["ucf_notes"])

                # Also extract from ucf_history for detailed analysis
                if "ucf_history" in coh:
                    ucf_history = coh["ucf_history"]
                    if isinstance(ucf_history, list):
                        for snapshot in ucf_history:
                            # Handle both dict and object snapshots
                            if snapshot is not None:
                                if isinstance(snapshot, dict):
                                    if "diagnostic_notes" in snapshot and snapshot["diagnostic_notes"]:
                                        all_ucf_notes.extend(snapshot["diagnostic_notes"])
                                    # Extract top 3 components from normalized_weights
                                    if "normalized_weights" in snapshot and snapshot["normalized_weights"]:
                                        # Sort by value and get top 3 keys
                                        sorted_weights = sorted(
                                            snapshot["normalized_weights"].items(),
                                            key=lambda x: x[1],
                                            reverse=True
                                        )
                                        top_3 = [k for k, v in sorted_weights[:3]]
                                        all_dominant_signals.extend(top_3)
                                elif hasattr(snapshot, "diagnostic_notes"):
                                    if snapshot.diagnostic_notes:
                                        all_ucf_notes.extend(snapshot.diagnostic_notes)
                                    # Extract from normalized_weights
                                    if hasattr(snapshot, "normalized_weights") and snapshot.normalized_weights:
                                        sorted_weights = sorted(
                                            snapshot.normalized_weights.items(),
                                            key=lambda x: x[1],
                                            reverse=True
                                        )
                                        top_3 = [k for k, v in sorted_weights[:3]]
                                        all_dominant_signals.extend(top_3)

        # Compute aggregates
        # Average COI, CSI, CIP
        if coi_values:
            avg_coi_val = sum(coi_values) / len(coi_values)
        if csi_values:
            avg_csi_val = sum(csi_values) / len(csi_values)
        if cip_values:
            avg_cip_val = sum(cip_values) / len(cip_values)

        # UCF entropy band derivation (focused | balanced | diffuse)
        if ucf_entropy_values:
            avg_ucf_entropy = sum(ucf_entropy_values) / len(ucf_entropy_values)
            if avg_ucf_entropy < 0.35:
                ucf_entropy_band_val = "focused"
            elif avg_ucf_entropy < 0.70:
                ucf_entropy_band_val = "balanced"
            else:
                ucf_entropy_band_val = "diffuse"

        # Dominant UCF signals (most frequent, limited to top 3)
        if all_dominant_signals:
            from collections import Counter
            signal_counts = Counter(all_dominant_signals)
            # Get top 3 most common signals
            dominant_ucf_signals_list = [signal for signal, _ in signal_counts.most_common(3)]

        # Collect unique UCF notes (deduplicate and sort for determinism)
        if all_ucf_notes:
            ucf_notes_list = sorted(set(all_ucf_notes))

    # Phase 27: Extract Symbolic Harmonization Formula (SHF) metrics from coherence history
    avg_symbolic_harmonization_val = None
    dominant_symbolic_harmonization_pattern_val = None
    symbolic_harmonization_notes_list = []

    if state.coherence_history:
        # Extract SHF metrics from CoherenceState
        shi_values = []
        all_shf_notes = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract current_symbolic_harmonization_index from CoherenceState
                if "current_symbolic_harmonization_index" in coh and coh["current_symbolic_harmonization_index"] is not None:
                    shi_values.append(coh["current_symbolic_harmonization_index"])

                # Also extract from symbolic_harmonization_history for detailed analysis
                if "symbolic_harmonization_history" in coh:
                    shf_history = coh["symbolic_harmonization_history"]
                    if isinstance(shf_history, list):
                        for snapshot in shf_history:
                            # Handle both dict and object snapshots
                            if snapshot is not None:
                                if isinstance(snapshot, dict):
                                    if "notes" in snapshot and snapshot["notes"]:
                                        all_shf_notes.extend(snapshot["notes"])
                                elif hasattr(snapshot, "notes"):
                                    if snapshot.notes:
                                        all_shf_notes.extend(snapshot.notes)

        # Compute aggregates
        # Average Symbolic Harmonization Index
        if shi_values:
            avg_symbolic_harmonization_val = sum(shi_values) / len(shi_values)

            # Determine dominant pattern using frequency-based band classification
            # High harmony: >= 0.70, Medium harmony: 0.40-0.70, Low harmony: < 0.40
            high_count = sum(1 for v in shi_values if v >= 0.70)
            medium_count = sum(1 for v in shi_values if 0.40 <= v < 0.70)
            low_count = sum(1 for v in shi_values if v < 0.40)

            # Dominant pattern is the most frequent band
            max_count = max(high_count, medium_count, low_count)
            if max_count == high_count:
                dominant_symbolic_harmonization_pattern_val = "high_harmony"
            elif max_count == medium_count:
                dominant_symbolic_harmonization_pattern_val = "medium_harmony"
            else:
                dominant_symbolic_harmonization_pattern_val = "low_harmony"

        # Collect unique SHF notes (deduplicate and sort for determinism)
        if all_shf_notes:
            symbolic_harmonization_notes_list = sorted(set(all_shf_notes))

    # ============================================================================
    # Phase 19: Drift Fusion aggregates (observation only)
    # ============================================================================
    avg_drift_fusion_index = None
    dominant_drift_risk_band = None
    drift_pattern_frequency = {}

    if state.coherence_history:
        # Extract drift fusion indices
        drift_indices = [
            turn.get("drift_fusion_index")
            for turn in state.coherence_history
            if isinstance(turn, dict) and turn.get("drift_fusion_index") is not None
        ]
        if drift_indices:
            avg_drift_fusion_index = sum(drift_indices) / len(drift_indices)

        # Extract drift risk bands
        drift_bands = [
            turn.get("drift_risk_band")
            for turn in state.coherence_history
            if isinstance(turn, dict) and turn.get("drift_risk_band") and turn.get("drift_risk_band") != ""
        ]
        if drift_bands:
            from collections import Counter
            band_counts = Counter(drift_bands)
            dominant_drift_risk_band = band_counts.most_common(1)[0][0]

        # Extract drift pattern tags
        all_tags = []
        for turn in state.coherence_history:
            if isinstance(turn, dict):
                tags = turn.get("drift_pattern_tags", [])
                if tags:
                    all_tags.extend(tags)
        if all_tags:
            from collections import Counter
            tag_counts = Counter(all_tags)
            drift_pattern_frequency = dict(tag_counts)

    # Phase 41: Extract Coherence-Regime Scenario Mapper metrics from coherence history
    dominant_coherence_regime_val = None
    regime_band_val = None
    regime_frequency_val = {}
    regime_notes_list = []

    if state.coherence_history:
        # Extract regime metrics from CoherenceState
        all_regimes = []
        all_regime_bands = []
        all_regime_notes = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract current_dominant_regime from CoherenceState
                if "current_dominant_regime" in coh and coh["current_dominant_regime"] is not None:
                    all_regimes.append(coh["current_dominant_regime"])

                # Extract current_regime_band from CoherenceState
                if "current_regime_band" in coh and coh["current_regime_band"] is not None:
                    all_regime_bands.append(coh["current_regime_band"])

                # Also extract from coherence_regime_history for detailed analysis
                if "coherence_regime_history" in coh:
                    regime_history = coh["coherence_regime_history"]
                    if isinstance(regime_history, list):
                        for snapshot in regime_history:
                            if snapshot is not None and hasattr(snapshot, 'dominant_regime'):
                                all_regimes.append(snapshot.dominant_regime)
                            if snapshot is not None and hasattr(snapshot, 'regime_band'):
                                all_regime_bands.append(snapshot.regime_band)
                            if snapshot is not None and hasattr(snapshot, 'notes'):
                                all_regime_notes.extend(snapshot.notes)

        # Compute aggregates
        # Dominant coherence regime (most frequent)
        if all_regimes:
            from collections import Counter
            regime_counts = Counter(all_regimes)
            dominant_coherence_regime_val = regime_counts.most_common(1)[0][0]
            regime_frequency_val = dict(regime_counts)

        # Regime band (most frequent)
        if all_regime_bands:
            from collections import Counter
            band_counts = Counter(all_regime_bands)
            regime_band_val = band_counts.most_common(1)[0][0]

        # Collect unique regime notes (deduplicate and sort for determinism)
        if all_regime_notes:
            regime_notes_list = sorted(set(all_regime_notes))

    # Phase 42: Extract Scenario Fusion Engine metrics from coherence history
    avg_scenario_alignment_val = None
    avg_scenario_divergence_val = None
    scenario_uncertainty_band_val = None
    dominant_fused_future_path_val = None
    scenario_pattern_tags_list = []

    if state.coherence_history:
        # Extract scenario fusion metrics from CoherenceState
        all_alignment_scores = []
        all_divergence_scores = []
        all_uncertainty_bands = []
        all_future_paths = []
        all_pattern_tags = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract from scenario_alignment_history
                if "scenario_alignment_history" in coh:
                    alignment_history = coh["scenario_alignment_history"]
                    if isinstance(alignment_history, list):
                        for score in alignment_history:
                            if score is not None and isinstance(score, (int, float)):
                                all_alignment_scores.append(score)

                # Extract from scenario_divergence_history
                if "scenario_divergence_history" in coh:
                    divergence_history = coh["scenario_divergence_history"]
                    if isinstance(divergence_history, list):
                        for score in divergence_history:
                            if score is not None and isinstance(score, (int, float)):
                                all_divergence_scores.append(score)

                # Extract from scenario_uncertainty_band_history
                if "scenario_uncertainty_band_history" in coh:
                    band_history = coh["scenario_uncertainty_band_history"]
                    if isinstance(band_history, list):
                        for band in band_history:
                            if band is not None:
                                all_uncertainty_bands.append(band)

                # Extract from dominant_future_path_history
                if "dominant_future_path_history" in coh:
                    path_history = coh["dominant_future_path_history"]
                    if isinstance(path_history, list):
                        for path in path_history:
                            if path is not None:
                                all_future_paths.append(path)

                # Extract tags from scenario_fusion_snapshot
                if "scenario_fusion_snapshot" in coh and coh["scenario_fusion_snapshot"] is not None:
                    snapshot = coh["scenario_fusion_snapshot"]
                    if hasattr(snapshot, 'diagnostic_tags') and isinstance(snapshot.diagnostic_tags, list):
                        all_pattern_tags.extend(snapshot.diagnostic_tags)

        # Compute aggregates
        # Average scenario alignment
        if all_alignment_scores:
            avg_scenario_alignment_val = sum(all_alignment_scores) / len(all_alignment_scores)

        # Average scenario divergence
        if all_divergence_scores:
            avg_scenario_divergence_val = sum(all_divergence_scores) / len(all_divergence_scores)

        # Scenario uncertainty band (most frequent)
        if all_uncertainty_bands:
            from collections import Counter
            band_counts = Counter(all_uncertainty_bands)
            scenario_uncertainty_band_val = band_counts.most_common(1)[0][0]

        # Dominant fused future path (most frequent)
        if all_future_paths:
            from collections import Counter
            path_counts = Counter(all_future_paths)
            # Deterministic tie-breaking: most_common + sorted
            top_paths = path_counts.most_common()
            max_count = top_paths[0][1]
            tied_paths = [path for path, count in top_paths if count == max_count]
            dominant_fused_future_path_val = sorted(tied_paths)[0]  # Deterministic tie-break

        # Collect unique scenario pattern tags (deduplicate and sort for determinism)
        if all_pattern_tags:
            scenario_pattern_tags_list = sorted(set(all_pattern_tags))

    # Phase 44: Extract Coherence–Scenario Alignment Engine metrics from coherence history
    avg_csae_alignment_val = None
    avg_csae_conflict_val = None
    avg_csae_stability_val = None
    csae_alignment_band_val = None
    csae_alignment_tags_list = []

    if state.coherence_history:
        # Extract CSAE metrics from CoherenceState
        all_csae_alignment_scores = []
        all_csae_conflict_scores = []
        all_csae_stability_scores = []
        all_csae_alignment_bands = []
        all_csae_tags = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract from scenario_alignment_score_history
                if "scenario_alignment_score_history" in coh:
                    alignment_history = coh["scenario_alignment_score_history"]
                    if isinstance(alignment_history, list):
                        for score in alignment_history:
                            if score is not None and isinstance(score, (int, float)):
                                all_csae_alignment_scores.append(score)

                # Extract from scenario_conflict_history
                if "scenario_conflict_history" in coh:
                    conflict_history = coh["scenario_conflict_history"]
                    if isinstance(conflict_history, list):
                        for score in conflict_history:
                            if score is not None and isinstance(score, (int, float)):
                                all_csae_conflict_scores.append(score)

                # Extract from scenario_stability_history
                if "scenario_stability_history" in coh:
                    stability_history = coh["scenario_stability_history"]
                    if isinstance(stability_history, list):
                        for score in stability_history:
                            if score is not None and isinstance(score, (int, float)):
                                all_csae_stability_scores.append(score)

                # Extract from scenario_alignment_band_history
                if "scenario_alignment_band_history" in coh:
                    band_history = coh["scenario_alignment_band_history"]
                    if isinstance(band_history, list):
                        for band in band_history:
                            if band is not None:
                                all_csae_alignment_bands.append(band)

                # Extract tags from scenario_tags_history
                if "scenario_tags_history" in coh:
                    tags_history = coh["scenario_tags_history"]
                    if isinstance(tags_history, list):
                        for tag_list in tags_history:
                            if isinstance(tag_list, list):
                                all_csae_tags.extend(tag_list)

        # Compute aggregates
        # Average CSAE alignment score
        if all_csae_alignment_scores:
            avg_csae_alignment_val = sum(all_csae_alignment_scores) / len(all_csae_alignment_scores)

        # Average CSAE conflict index
        if all_csae_conflict_scores:
            avg_csae_conflict_val = sum(all_csae_conflict_scores) / len(all_csae_conflict_scores)

        # Average CSAE stability agreement
        if all_csae_stability_scores:
            avg_csae_stability_val = sum(all_csae_stability_scores) / len(all_csae_stability_scores)

        # CSAE alignment band (most frequent)
        if all_csae_alignment_bands:
            from collections import Counter
            band_counts = Counter(all_csae_alignment_bands)
            # Deterministic tie-breaking: most_common + sorted
            top_bands = band_counts.most_common()
            max_count = top_bands[0][1]
            tied_bands = [band for band, count in top_bands if count == max_count]
            csae_alignment_band_val = sorted(tied_bands)[0]  # Deterministic tie-break

        # Collect unique CSAE alignment tags (deduplicate and sort for determinism)
        if all_csae_tags:
            csae_alignment_tags_list = sorted(set(all_csae_tags))

    # Phase 45: Extract Multi-Trajectory Stability Field (MTSF) metrics from coherence history
    avg_tsi_val = 0.0
    avg_tvi_val = 0.0
    avg_chf_val = 0.0
    avg_scc_val = 0.0
    mtsf_band_val = None
    mtsf_tags_list = []

    # Phase 46: Extract Trajectory Field Convergence Engine (TFCE) metrics from coherence history
    avg_trajectory_convergence_val = None
    avg_trajectory_divergence_val = None
    avg_trajectory_stability_val = None
    dominant_convergence_band_val = None
    tfce_tags_list = []

    # Phase 47: Initialize Unified Trajectory–Scenario Synthesis Engine (UTSSE) variables
    avg_synthesis_integrity_val = None
    avg_synthesis_alignment_val = None
    avg_synthesis_divergence_val = None
    dominant_synthesis_band_val = None
    synthesis_tags_list = []

    # Phase 48: Initialize Macro-Stability Regulator (MSR) variables
    avg_macro_stability_val = None
    avg_macro_divergence_val = None
    avg_macro_predictive_confidence_val = None
    avg_macro_identity_resilience_val = None
    dominant_macro_stability_band_val = None
    macro_stability_tags_list = []

    # Phase 49: Initialize Unified Cross-Phase Temporal Stability Engine (UCTSE) variables
    avg_temporal_stability_val = None
    avg_predictive_entropy_val = None
    avg_future_consistency_val = None
    temporal_stability_band_val = None
    dominant_temporal_regime_val = None

    # Phase 50: Initialize Cognitive Consistency Regression Engine (CCRE) variables
    avg_regression_stability_val = None
    avg_regression_alignment_val = None
    avg_regression_drift_val = None
    avg_prediction_reversal_risk_val = None
    avg_internal_consistency_strength_val = None
    regression_consistency_band_val = None
    regression_consistency_tags_list = []

    # Phase 51: Initialize RAG Coherence Validation Engine (RCVE) variables
    avg_rag_alignment_val = None
    avg_rag_conflict_val = None
    avg_rag_stability_val = None
    avg_rag_relevance_val = None
    avg_rag_support_density_val = None
    dominant_rag_band_val = None
    rag_diagnostic_tags_list = []

    # Phase 51: Initialize CRA (Cognitive Resonance Aggregator) variables
    avg_cra_resonance_val = None
    avg_cra_alignment_val = None
    avg_cra_stability_val = None
    avg_cra_consistency_val = None
    avg_cra_overall_val = None
    dominant_cra_band_val = None
    cra_pattern_tags_list = []

    # Phase 52: Initialize Internal–External Reality Cross-Verification Engine (IER-CVE) variables
    avg_internal_external_alignment_val = None
    avg_internal_external_conflict_val = None
    avg_internal_external_stability_val = None
    dominant_ier_cve_band_val = None
    ier_cve_tags_list = []

    # Phase 53: Initialize External Reality Trust Calibration Engine (ERTCE) variables
    avg_external_trust_score_val = None
    avg_internal_override_pressure_val = None
    avg_external_signal_fragility_val = None
    avg_alignment_resilience_val = None
    avg_trust_decay_risk_val = None
    dominant_trust_band_val = None
    ertce_tags_list = []

    # Phase 54: Initialize Action Eligibility & Commitment Boundary Engine (AECBE) variables
    avg_action_eligibility_score_val = None
    dominant_action_eligibility_band_val = None
    action_eligibility_tags_list = []

    if state.coherence_history:
        # Extract MTSF metrics from CoherenceState
        all_tsi = []
        all_tvi = []
        all_chf = []
        all_scc = []
        all_mtsf_bands = []
        all_mtsf_tags = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract from mtsf_tsi_history
                if "mtsf_tsi_history" in coh:
                    tsi_history = coh["mtsf_tsi_history"]
                    if isinstance(tsi_history, list):
                        for val in tsi_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_tsi.append(val)

                # Extract from mtsf_tvi_history
                if "mtsf_tvi_history" in coh:
                    tvi_history = coh["mtsf_tvi_history"]
                    if isinstance(tvi_history, list):
                        for val in tvi_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_tvi.append(val)

                # Extract from mtsf_chf_history
                if "mtsf_chf_history" in coh:
                    chf_history = coh["mtsf_chf_history"]
                    if isinstance(chf_history, list):
                        for val in chf_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_chf.append(val)

                # Extract from mtsf_scc_history
                if "mtsf_scc_history" in coh:
                    scc_history = coh["mtsf_scc_history"]
                    if isinstance(scc_history, list):
                        for val in scc_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_scc.append(val)

                # Extract from mtsf_band_history
                if "mtsf_band_history" in coh:
                    band_history = coh["mtsf_band_history"]
                    if isinstance(band_history, list):
                        for band in band_history:
                            if band is not None and band != "":
                                all_mtsf_bands.append(band)

                # Extract tags from mtsf_tags_history
                if "mtsf_tags_history" in coh:
                    tags_history = coh["mtsf_tags_history"]
                    if isinstance(tags_history, list):
                        for tag_list in tags_history:
                            if isinstance(tag_list, list):
                                all_mtsf_tags.extend(tag_list)

        # Compute aggregates
        # Average TSI
        if all_tsi:
            avg_tsi_val = sum(all_tsi) / len(all_tsi)

        # Average TVI
        if all_tvi:
            avg_tvi_val = sum(all_tvi) / len(all_tvi)

        # Average CHF
        if all_chf:
            avg_chf_val = sum(all_chf) / len(all_chf)

        # Average SCC
        if all_scc:
            avg_scc_val = sum(all_scc) / len(all_scc)

        # MTSF band (most frequent)
        if all_mtsf_bands:
            from collections import Counter
            band_counts = Counter(all_mtsf_bands)
            # Deterministic tie-breaking: most_common + sorted
            top_bands = band_counts.most_common()
            max_count = top_bands[0][1]
            tied_bands = [band for band, count in top_bands if count == max_count]
            mtsf_band_val = sorted(tied_bands)[0]  # Deterministic tie-break

        # Collect unique MTSF tags (deduplicate and sort for determinism)
        if all_mtsf_tags:
            mtsf_tags_list = sorted(set(all_mtsf_tags))

        # Phase 46: Extract TFCE metrics from CoherenceState
        all_tfce_convergence = []
        all_tfce_divergence = []
        all_tfce_stability = []
        all_tfce_bands = []
        all_tfce_tags = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract from tfce_convergence_index_history
                if "tfce_convergence_index_history" in coh:
                    convergence_history = coh["tfce_convergence_index_history"]
                    if isinstance(convergence_history, list):
                        for val in convergence_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_tfce_convergence.append(val)

                # Extract from tfce_divergence_index_history
                if "tfce_divergence_index_history" in coh:
                    divergence_history = coh["tfce_divergence_index_history"]
                    if isinstance(divergence_history, list):
                        for val in divergence_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_tfce_divergence.append(val)

                # Extract from tfce_stability_index_history
                if "tfce_stability_index_history" in coh:
                    stability_history = coh["tfce_stability_index_history"]
                    if isinstance(stability_history, list):
                        for val in stability_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_tfce_stability.append(val)

                # Extract from tfce_convergence_band_history
                if "tfce_convergence_band_history" in coh:
                    band_history = coh["tfce_convergence_band_history"]
                    if isinstance(band_history, list):
                        for band in band_history:
                            if band is not None and band != "":
                                all_tfce_bands.append(band)

                # Extract tags from tfce_tags_history
                if "tfce_tags_history" in coh:
                    tags_history = coh["tfce_tags_history"]
                    if isinstance(tags_history, list):
                        for tag_list in tags_history:
                            if isinstance(tag_list, list):
                                all_tfce_tags.extend(tag_list)

        # Compute aggregates
        # Average convergence index
        if all_tfce_convergence:
            avg_trajectory_convergence_val = sum(all_tfce_convergence) / len(all_tfce_convergence)

        # Average divergence index
        if all_tfce_divergence:
            avg_trajectory_divergence_val = sum(all_tfce_divergence) / len(all_tfce_divergence)

        # Average stability index
        if all_tfce_stability:
            avg_trajectory_stability_val = sum(all_tfce_stability) / len(all_tfce_stability)

        # Dominant convergence band (most frequent)
        if all_tfce_bands:
            from collections import Counter
            band_counts = Counter(all_tfce_bands)
            # Deterministic tie-breaking: most_common + sorted
            top_bands = band_counts.most_common()
            max_count = top_bands[0][1]
            tied_bands = [band for band, count in top_bands if count == max_count]
            dominant_convergence_band_val = sorted(tied_bands)[0]  # Deterministic tie-break

        # Collect unique TFCE tags (deduplicate and sort for determinism)
        if all_tfce_tags:
            tfce_tags_list = sorted(set(all_tfce_tags))

        # Phase 47: Extract Unified Trajectory–Scenario Synthesis Engine (UTSSE) metrics from CoherenceState
        all_synthesis_integrity = []
        all_synthesis_alignment = []
        all_synthesis_divergence = []
        all_synthesis_bands = []
        all_synthesis_tags = []

        for coh in state.coherence_history:
            if isinstance(coh, dict):
                # Extract from synthesis_integrity_history
                if "synthesis_integrity_history" in coh:
                    integrity_history = coh["synthesis_integrity_history"]
                    if isinstance(integrity_history, list):
                        for val in integrity_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_synthesis_integrity.append(val)

                # Extract from synthesis_alignment_history
                if "synthesis_alignment_history" in coh:
                    alignment_history = coh["synthesis_alignment_history"]
                    if isinstance(alignment_history, list):
                        for val in alignment_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_synthesis_alignment.append(val)

                # Extract from synthesis_divergence_history
                if "synthesis_divergence_history" in coh:
                    divergence_history = coh["synthesis_divergence_history"]
                    if isinstance(divergence_history, list):
                        for val in divergence_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_synthesis_divergence.append(val)

                # Extract from synthesis_band_history
                if "synthesis_band_history" in coh:
                    band_history = coh["synthesis_band_history"]
                    if isinstance(band_history, list):
                        for band in band_history:
                            if band is not None and band != "":
                                all_synthesis_bands.append(band)

                # Extract tags from synthesis_tags_history
                if "synthesis_tags_history" in coh:
                    tags_history = coh["synthesis_tags_history"]
                    if isinstance(tags_history, list):
                        for tag_list in tags_history:
                            if isinstance(tag_list, list):
                                all_synthesis_tags.extend(tag_list)

        # Compute aggregates for Phase 47
        # Average synthesis integrity
        if all_synthesis_integrity:
            avg_synthesis_integrity_val = sum(all_synthesis_integrity) / len(all_synthesis_integrity)

        # Average future state alignment
        if all_synthesis_alignment:
            avg_synthesis_alignment_val = sum(all_synthesis_alignment) / len(all_synthesis_alignment)

        # Average future divergence risk
        if all_synthesis_divergence:
            avg_synthesis_divergence_val = sum(all_synthesis_divergence) / len(all_synthesis_divergence)

        # Dominant synthesis band (most frequent)
        if all_synthesis_bands:
            from collections import Counter
            band_counts = Counter(all_synthesis_bands)
            # Deterministic tie-breaking: most_common + sorted
            top_bands = band_counts.most_common()
            max_count = top_bands[0][1]
            tied_bands = [band for band, count in top_bands if count == max_count]
            dominant_synthesis_band_val = sorted(tied_bands)[0]  # Deterministic tie-break

        # Collect unique UTSSE tags (deduplicate and sort for determinism)
        if all_synthesis_tags:
            synthesis_tags_list = sorted(set(all_synthesis_tags))

        # Phase 48: Extract Macro-Stability Regulator (MSR) metrics from CoherenceState
        all_macro_stability = []
        all_macro_divergence = []
        all_macro_predictive_confidence = []
        all_macro_identity_resilience = []
        all_macro_stability_bands = []
        all_macro_stability_tags = []

        for coh in state.coherence_history:
            if coh is not None and isinstance(coh, dict):
                # Extract from macro_stability_index_history
                if "macro_stability_index_history" in coh:
                    stability_history = coh["macro_stability_index_history"]
                    if isinstance(stability_history, list):
                        for val in stability_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_macro_stability.append(val)

                # Extract from macro_divergence_history
                if "macro_divergence_history" in coh:
                    divergence_history = coh["macro_divergence_history"]
                    if isinstance(divergence_history, list):
                        for val in divergence_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_macro_divergence.append(val)

                # Extract from macro_predictive_confidence_history
                if "macro_predictive_confidence_history" in coh:
                    confidence_history = coh["macro_predictive_confidence_history"]
                    if isinstance(confidence_history, list):
                        for val in confidence_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_macro_predictive_confidence.append(val)

                # Extract from macro_identity_resilience_history
                if "macro_identity_resilience_history" in coh:
                    resilience_history = coh["macro_identity_resilience_history"]
                    if isinstance(resilience_history, list):
                        for val in resilience_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_macro_identity_resilience.append(val)

                # Extract from macro_stability_band_history
                if "macro_stability_band_history" in coh:
                    band_history = coh["macro_stability_band_history"]
                    if isinstance(band_history, list):
                        for band in band_history:
                            if band is not None and band != "":
                                all_macro_stability_bands.append(band)

                # Extract tags from macro_stability_tags_history
                if "macro_stability_tags_history" in coh:
                    tags_history = coh["macro_stability_tags_history"]
                    if isinstance(tags_history, list):
                        for tag_list in tags_history:
                            if isinstance(tag_list, list):
                                all_macro_stability_tags.extend(tag_list)

        # Compute aggregates for Phase 48
        # Average macro-stability index
        if all_macro_stability:
            avg_macro_stability_val = sum(all_macro_stability) / len(all_macro_stability)

        # Average macro-divergence index
        if all_macro_divergence:
            avg_macro_divergence_val = sum(all_macro_divergence) / len(all_macro_divergence)

        # Average macro-predictive confidence
        if all_macro_predictive_confidence:
            avg_macro_predictive_confidence_val = sum(all_macro_predictive_confidence) / len(all_macro_predictive_confidence)

        # Average macro-identity resilience
        if all_macro_identity_resilience:
            avg_macro_identity_resilience_val = sum(all_macro_identity_resilience) / len(all_macro_identity_resilience)

        # Dominant macro-stability band (most frequent)
        if all_macro_stability_bands:
            from collections import Counter
            band_counts = Counter(all_macro_stability_bands)
            # Deterministic tie-breaking: most_common + sorted
            top_bands = band_counts.most_common()
            max_count = top_bands[0][1]
            tied_bands = [band for band, count in top_bands if count == max_count]
            dominant_macro_stability_band_val = sorted(tied_bands)[0]  # Deterministic tie-break

        # Collect unique MSR tags (deduplicate and sort for determinism)
        if all_macro_stability_tags:
            macro_stability_tags_list = sorted(set(all_macro_stability_tags))

        # Phase 49: Extract Unified Cross-Phase Temporal Stability Engine (UCTSE) metrics from CoherenceState
        all_temporal_stability = []
        all_predictive_entropy = []
        all_future_consistency = []
        all_temporal_stability_bands = []
        all_temporal_regimes = []

        for coh in state.coherence_history:
            if coh is not None and isinstance(coh, dict):
                # Extract from temporal_stability_index_history
                if "temporal_stability_index_history" in coh:
                    stability_history = coh["temporal_stability_index_history"]
                    if isinstance(stability_history, list):
                        for val in stability_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_temporal_stability.append(val)

                # Extract from temporal_stability_entropy_history
                if "temporal_stability_entropy_history" in coh:
                    entropy_history = coh["temporal_stability_entropy_history"]
                    if isinstance(entropy_history, list):
                        for val in entropy_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_predictive_entropy.append(val)

                # Extract from temporal_stability_consistency_history
                if "temporal_stability_consistency_history" in coh:
                    consistency_history = coh["temporal_stability_consistency_history"]
                    if isinstance(consistency_history, list):
                        for val in consistency_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_future_consistency.append(val)

                # Extract from temporal_stability_band_history
                if "temporal_stability_band_history" in coh:
                    band_history = coh["temporal_stability_band_history"]
                    if isinstance(band_history, list):
                        for band in band_history:
                            if band is not None and band != "":
                                all_temporal_stability_bands.append(band)

                # Extract dominant regime from temporal_stability_snapshot
                if "temporal_stability_snapshot" in coh:
                    snapshot = coh["temporal_stability_snapshot"]
                    if snapshot is not None:
                        if isinstance(snapshot, dict) and "dominant_regime" in snapshot:
                            regime = snapshot["dominant_regime"]
                            if regime is not None and regime != "unknown":
                                all_temporal_regimes.append(regime)
                        elif hasattr(snapshot, "dominant_regime"):
                            regime = snapshot.dominant_regime
                            if regime is not None and regime != "unknown":
                                all_temporal_regimes.append(regime)

        # Compute aggregates for Phase 49
        # Average temporal stability index
        if all_temporal_stability:
            avg_temporal_stability_val = sum(all_temporal_stability) / len(all_temporal_stability)

        # Average predictive entropy
        if all_predictive_entropy:
            avg_predictive_entropy_val = sum(all_predictive_entropy) / len(all_predictive_entropy)

        # Average future consistency
        if all_future_consistency:
            avg_future_consistency_val = sum(all_future_consistency) / len(all_future_consistency)

        # Temporal stability band (most frequent)
        if all_temporal_stability_bands:
            from collections import Counter
            band_counts = Counter(all_temporal_stability_bands)
            # Deterministic tie-breaking: most_common + sorted
            top_bands = band_counts.most_common()
            max_count = top_bands[0][1]
            tied_bands = [band for band, count in top_bands if count == max_count]
            temporal_stability_band_val = sorted(tied_bands)[0]  # Deterministic tie-break

        # Dominant temporal regime (most frequent)
        if all_temporal_regimes:
            from collections import Counter
            regime_counts = Counter(all_temporal_regimes)
            # Deterministic tie-breaking: most_common + sorted
            top_regimes = regime_counts.most_common()
            max_count = top_regimes[0][1]
            tied_regimes = [regime for regime, count in top_regimes if count == max_count]
            dominant_temporal_regime_val = sorted(tied_regimes)[0]  # Deterministic tie-break

        # Phase 50: Extract Cognitive Consistency Regression Engine (CCRE) metrics from CoherenceState
        all_regression_stability = []
        all_regression_alignment = []
        all_regression_drift = []
        all_prediction_reversal_risk = []
        all_internal_consistency_strength = []
        all_regression_consistency_bands = []
        all_regression_consistency_tags = []

        for coh in state.coherence_history:
            if coh is not None and isinstance(coh, dict):
                # Extract from regression_stability_history (RSI)
                if "regression_stability_history" in coh:
                    stability_history = coh["regression_stability_history"]
                    if isinstance(stability_history, list):
                        for val in stability_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_regression_stability.append(val)

                # Extract from regression_alignment_history (CLRA)
                if "regression_alignment_history" in coh:
                    alignment_history = coh["regression_alignment_history"]
                    if isinstance(alignment_history, list):
                        for val in alignment_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_regression_alignment.append(val)

                # Extract from regression_drift_history (CDR)
                if "regression_drift_history" in coh:
                    drift_history = coh["regression_drift_history"]
                    if isinstance(drift_history, list):
                        for val in drift_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_regression_drift.append(val)

                # Extract from regression_prr_history (PRR)
                if "regression_prr_history" in coh:
                    prr_history = coh["regression_prr_history"]
                    if isinstance(prr_history, list):
                        for val in prr_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_prediction_reversal_risk.append(val)

                # Extract from regression_ics_history (ICS)
                if "regression_ics_history" in coh:
                    ics_history = coh["regression_ics_history"]
                    if isinstance(ics_history, list):
                        for val in ics_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_internal_consistency_strength.append(val)

                # Extract from regression_band_history
                if "regression_band_history" in coh:
                    band_history = coh["regression_band_history"]
                    if isinstance(band_history, list):
                        for band in band_history:
                            if band is not None and band != "":
                                all_regression_consistency_bands.append(band)

                # Extract tags from regression_tags_history
                if "regression_tags_history" in coh:
                    tags_history = coh["regression_tags_history"]
                    if isinstance(tags_history, list):
                        for tag_list in tags_history:
                            if isinstance(tag_list, list):
                                all_regression_consistency_tags.extend(tag_list)

        # Compute aggregates for Phase 50
        # Average regression stability index (RSI)
        if all_regression_stability:
            avg_regression_stability_val = sum(all_regression_stability) / len(all_regression_stability)

        # Average regression alignment score (CLRA)
        if all_regression_alignment:
            avg_regression_alignment_val = sum(all_regression_alignment) / len(all_regression_alignment)

        # Average regression drift score (CDR)
        if all_regression_drift:
            avg_regression_drift_val = sum(all_regression_drift) / len(all_regression_drift)

        # Average prediction reversal risk (PRR)
        if all_prediction_reversal_risk:
            avg_prediction_reversal_risk_val = sum(all_prediction_reversal_risk) / len(all_prediction_reversal_risk)

        # Average internal consistency strength (ICS)
        if all_internal_consistency_strength:
            avg_internal_consistency_strength_val = sum(all_internal_consistency_strength) / len(all_internal_consistency_strength)

        # Regression consistency band (most frequent)
        if all_regression_consistency_bands:
            from collections import Counter
            band_counts = Counter(all_regression_consistency_bands)
            # Deterministic tie-breaking: most_common + sorted
            # Priority order for tie-breaking: high_consistency > medium_consistency > low_consistency > internal_conflict
            top_bands = band_counts.most_common()
            max_count = top_bands[0][1]
            tied_bands = [band for band, count in top_bands if count == max_count]
            # Use priority order for deterministic tie-breaking
            priority_order = ["high_consistency", "medium_consistency", "low_consistency", "internal_conflict"]
            for priority_band in priority_order:
                if priority_band in tied_bands:
                    regression_consistency_band_val = priority_band
                    break
            if regression_consistency_band_val is None:
                regression_consistency_band_val = sorted(tied_bands)[0]  # Fallback to alphabetical

        # Collect unique CCRE tags (deduplicate and sort for determinism)
        if all_regression_consistency_tags:
            regression_consistency_tags_list = sorted(set(all_regression_consistency_tags))

        # Phase 51: Extract RAG Coherence Validation Engine (RCVE) metrics from CoherenceState
        all_rag_alignment = []
        all_rag_conflict = []
        all_rag_stability = []
        all_rag_relevance = []
        all_rag_support_density = []
        all_rag_bands = []
        all_rag_tags = []

        for coh in state.coherence_history:
            if coh is not None and isinstance(coh, dict):
                # Extract from rag_alignment_history
                if "rag_alignment_history" in coh:
                    alignment_history = coh["rag_alignment_history"]
                    if isinstance(alignment_history, list):
                        for val in alignment_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_rag_alignment.append(val)

                # Extract from rag_conflict_history
                if "rag_conflict_history" in coh:
                    conflict_history = coh["rag_conflict_history"]
                    if isinstance(conflict_history, list):
                        for val in conflict_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_rag_conflict.append(val)

                # Extract from rag_stability_history
                if "rag_stability_history" in coh:
                    stability_history = coh["rag_stability_history"]
                    if isinstance(stability_history, list):
                        for val in stability_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_rag_stability.append(val)

                # Extract from rag_relevance_history
                if "rag_relevance_history" in coh:
                    relevance_history = coh["rag_relevance_history"]
                    if isinstance(relevance_history, list):
                        for val in relevance_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_rag_relevance.append(val)

                # Extract from rag_support_history
                if "rag_support_history" in coh:
                    support_history = coh["rag_support_history"]
                    if isinstance(support_history, list):
                        for val in support_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_rag_support_density.append(val)

                # Extract from rag_band_history
                if "rag_band_history" in coh:
                    band_history = coh["rag_band_history"]
                    if isinstance(band_history, list):
                        for band in band_history:
                            if band is not None and band != "":
                                all_rag_bands.append(band)

                # Extract tags from rag_tag_history
                if "rag_tag_history" in coh:
                    tags_history = coh["rag_tag_history"]
                    if isinstance(tags_history, list):
                        for tag_list in tags_history:
                            if isinstance(tag_list, list):
                                all_rag_tags.extend(tag_list)

        # Compute aggregates for Phase 51
        # Average RAG alignment
        if all_rag_alignment:
            avg_rag_alignment_val = sum(all_rag_alignment) / len(all_rag_alignment)

        # Average RAG conflict
        if all_rag_conflict:
            avg_rag_conflict_val = sum(all_rag_conflict) / len(all_rag_conflict)

        # Average RAG stability
        if all_rag_stability:
            avg_rag_stability_val = sum(all_rag_stability) / len(all_rag_stability)

        # Average RAG relevance
        if all_rag_relevance:
            avg_rag_relevance_val = sum(all_rag_relevance) / len(all_rag_relevance)

        # Average RAG support density
        if all_rag_support_density:
            avg_rag_support_density_val = sum(all_rag_support_density) / len(all_rag_support_density)

        # Dominant RAG band (most frequent)
        if all_rag_bands:
            from collections import Counter
            band_counts = Counter(all_rag_bands)
            # Deterministic tie-breaking: most_common + sorted
            # Priority order for tie-breaking: HIGH_ALIGNMENT > MEDIUM_ALIGNMENT > LOW_ALIGNMENT > CONTRADICTION
            top_bands = band_counts.most_common()
            max_count = top_bands[0][1]
            tied_bands = [band for band, count in top_bands if count == max_count]
            # Use priority order for deterministic tie-breaking
            priority_order = ["HIGH_ALIGNMENT", "MEDIUM_ALIGNMENT", "LOW_ALIGNMENT", "CONTRADICTION"]
            for priority_band in priority_order:
                if priority_band in tied_bands:
                    dominant_rag_band_val = priority_band
                    break
            if dominant_rag_band_val is None:
                dominant_rag_band_val = sorted(tied_bands)[0]  # Fallback to alphabetical

        # Collect unique RAG tags (deduplicate and sort for determinism)
        if all_rag_tags:
            rag_diagnostic_tags_list = sorted(set(all_rag_tags))

        # Phase 52: Extract Internal–External Reality Cross-Verification Engine (IER-CVE) metrics from CoherenceState
        all_ier_cve_alignment = []
        all_ier_cve_conflict = []
        all_ier_cve_stability = []
        all_ier_cve_bands = []
        all_ier_cve_tags = []

        for coh in state.coherence_history:
            if coh is not None and isinstance(coh, dict):
                # Extract from ier_cve_alignment_history
                if "ier_cve_alignment_history" in coh:
                    alignment_history = coh["ier_cve_alignment_history"]
                    if isinstance(alignment_history, list):
                        for val in alignment_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_ier_cve_alignment.append(val)

                # Extract from ier_cve_conflict_history
                if "ier_cve_conflict_history" in coh:
                    conflict_history = coh["ier_cve_conflict_history"]
                    if isinstance(conflict_history, list):
                        for val in conflict_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_ier_cve_conflict.append(val)

                # Extract from ier_cve_stability_history
                if "ier_cve_stability_history" in coh:
                    stability_history = coh["ier_cve_stability_history"]
                    if isinstance(stability_history, list):
                        for val in stability_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_ier_cve_stability.append(val)

                # Extract from ier_cve_band_history
                if "ier_cve_band_history" in coh:
                    band_history = coh["ier_cve_band_history"]
                    if isinstance(band_history, list):
                        for band in band_history:
                            if band is not None and isinstance(band, str) and band:
                                all_ier_cve_bands.append(band)

                # Extract from ier_cve_tag_history
                if "ier_cve_tag_history" in coh:
                    tag_history = coh["ier_cve_tag_history"]
                    if isinstance(tag_history, list):
                        for tags in tag_history:
                            if tags is not None and isinstance(tags, list):
                                all_ier_cve_tags.extend(tags)

        # Compute aggregates for Phase 52
        # Average IER-CVE alignment
        if all_ier_cve_alignment:
            avg_internal_external_alignment_val = sum(all_ier_cve_alignment) / len(all_ier_cve_alignment)

        # Average IER-CVE conflict
        if all_ier_cve_conflict:
            avg_internal_external_conflict_val = sum(all_ier_cve_conflict) / len(all_ier_cve_conflict)

        # Average IER-CVE stability
        if all_ier_cve_stability:
            avg_internal_external_stability_val = sum(all_ier_cve_stability) / len(all_ier_cve_stability)

        # Dominant IER-CVE band (most frequent)
        if all_ier_cve_bands:
            from collections import Counter
            band_counts = Counter(all_ier_cve_bands)
            # Deterministic tie-breaking: most_common + sorted
            # Priority order for tie-breaking: high_alignment > medium_alignment > low_alignment > conflict
            top_bands = band_counts.most_common()
            max_count = top_bands[0][1]
            tied_bands = [band for band, count in top_bands if count == max_count]
            # Use priority order for deterministic tie-breaking
            priority_order = ["high_alignment", "medium_alignment", "low_alignment", "conflict"]
            for priority_band in priority_order:
                if priority_band in tied_bands:
                    dominant_ier_cve_band_val = priority_band
                    break
            if dominant_ier_cve_band_val is None:
                dominant_ier_cve_band_val = sorted(tied_bands)[0]  # Fallback to alphabetical

        # Collect unique IER-CVE tags (deduplicate and sort for determinism)
        if all_ier_cve_tags:
            ier_cve_tags_list = sorted(set(all_ier_cve_tags))

        # Phase 53: Extract External Reality Trust Calibration Engine (ERTCE) metrics from CoherenceState
        all_ertce_trust_score = []
        all_ertce_override_pressure = []
        all_ertce_fragility = []
        all_ertce_resilience = []
        all_ertce_decay_risk = []
        all_ertce_bands = []
        all_ertce_tags = []

        for coh in state.coherence_history:
            if coh is not None and isinstance(coh, dict):
                # Extract from ertce_trust_score_history
                if "ertce_trust_score_history" in coh:
                    trust_score_history = coh["ertce_trust_score_history"]
                    if isinstance(trust_score_history, list):
                        for val in trust_score_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_ertce_trust_score.append(val)

                # Extract from ertce_override_pressure_history
                if "ertce_override_pressure_history" in coh:
                    override_pressure_history = coh["ertce_override_pressure_history"]
                    if isinstance(override_pressure_history, list):
                        for val in override_pressure_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_ertce_override_pressure.append(val)

                # Extract from ertce_fragility_history
                if "ertce_fragility_history" in coh:
                    fragility_history = coh["ertce_fragility_history"]
                    if isinstance(fragility_history, list):
                        for val in fragility_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_ertce_fragility.append(val)

                # Extract from ertce_resilience_history
                if "ertce_resilience_history" in coh:
                    resilience_history = coh["ertce_resilience_history"]
                    if isinstance(resilience_history, list):
                        for val in resilience_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_ertce_resilience.append(val)

                # Extract from ertce_decay_risk_history
                if "ertce_decay_risk_history" in coh:
                    decay_risk_history = coh["ertce_decay_risk_history"]
                    if isinstance(decay_risk_history, list):
                        for val in decay_risk_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_ertce_decay_risk.append(val)

                # Extract from ertce_band_history
                if "ertce_band_history" in coh:
                    band_history = coh["ertce_band_history"]
                    if isinstance(band_history, list):
                        for band in band_history:
                            if band is not None and isinstance(band, str) and band:
                                all_ertce_bands.append(band)

                # Extract from ertce_tag_history
                if "ertce_tag_history" in coh:
                    tag_history = coh["ertce_tag_history"]
                    if isinstance(tag_history, list):
                        for tags in tag_history:
                            if tags is not None and isinstance(tags, list):
                                all_ertce_tags.extend(tags)

        # Compute aggregates for Phase 53
        # Average external trust score
        if all_ertce_trust_score:
            avg_external_trust_score_val = sum(all_ertce_trust_score) / len(all_ertce_trust_score)

        # Average internal override pressure
        if all_ertce_override_pressure:
            avg_internal_override_pressure_val = sum(all_ertce_override_pressure) / len(all_ertce_override_pressure)

        # Average external signal fragility
        if all_ertce_fragility:
            avg_external_signal_fragility_val = sum(all_ertce_fragility) / len(all_ertce_fragility)

        # Average alignment resilience
        if all_ertce_resilience:
            avg_alignment_resilience_val = sum(all_ertce_resilience) / len(all_ertce_resilience)

        # Average trust decay risk
        if all_ertce_decay_risk:
            avg_trust_decay_risk_val = sum(all_ertce_decay_risk) / len(all_ertce_decay_risk)

        # Dominant trust band (most frequent)
        if all_ertce_bands:
            from collections import Counter
            band_counts = Counter(all_ertce_bands)
            # Deterministic tie-breaking: most_common + sorted
            # Priority order for tie-breaking: HIGH_EXTERNAL_TRUST > CONDITIONAL_EXTERNAL_TRUST > LOW_EXTERNAL_TRUST > EXTERNAL_CONFLICT_ZONE
            top_bands = band_counts.most_common()
            max_count = top_bands[0][1]
            tied_bands = [band for band, count in top_bands if count == max_count]
            # Use priority order for deterministic tie-breaking
            priority_order = ["HIGH_EXTERNAL_TRUST", "CONDITIONAL_EXTERNAL_TRUST", "LOW_EXTERNAL_TRUST", "EXTERNAL_CONFLICT_ZONE"]
            for priority_band in priority_order:
                if priority_band in tied_bands:
                    dominant_trust_band_val = priority_band
                    break
            if dominant_trust_band_val is None:
                dominant_trust_band_val = sorted(tied_bands)[0]  # Fallback to alphabetical

        # Collect unique ERTCE tags (deduplicate and sort for determinism)
        if all_ertce_tags:
            ertce_tags_list = sorted(set(all_ertce_tags))

        # ====================================================================
        # Phase 54: Action Eligibility & Commitment Boundary Engine (AECBE)
        # ====================================================================

        all_action_eligibility_scores = []
        all_action_eligibility_bands = []
        all_action_eligibility_tags = []

        for coh in state.coherence_history:
            if coh is not None and isinstance(coh, dict):
                # Extract from action_eligibility_score_history
                if "action_eligibility_score_history" in coh:
                    score_history = coh["action_eligibility_score_history"]
                    if isinstance(score_history, list):
                        for val in score_history:
                            if val is not None and isinstance(val, (int, float)):
                                all_action_eligibility_scores.append(val)

                # Extract from action_eligibility_band_history
                if "action_eligibility_band_history" in coh:
                    band_history = coh["action_eligibility_band_history"]
                    if isinstance(band_history, list):
                        for band in band_history:
                            if band is not None and isinstance(band, str) and band:
                                all_action_eligibility_bands.append(band)

                # Extract from action_eligibility_tags_history
                if "action_eligibility_tags_history" in coh:
                    tag_history = coh["action_eligibility_tags_history"]
                    if isinstance(tag_history, list):
                        for tags in tag_history:
                            if tags is not None and isinstance(tags, list):
                                all_action_eligibility_tags.extend(tags)

        # Compute aggregates for Phase 54
        # Average action eligibility score
        if all_action_eligibility_scores:
            avg_action_eligibility_score_val = sum(all_action_eligibility_scores) / len(all_action_eligibility_scores)

        # Dominant eligibility band (most frequent with deterministic tie-breaking)
        if all_action_eligibility_bands:
            from collections import Counter
            band_counts = Counter(all_action_eligibility_bands)
            # Deterministic tie-breaking with priority order
            top_bands = band_counts.most_common()
            max_count = top_bands[0][1]
            tied_bands = [band for band, count in top_bands if count == max_count]
            # Priority order: ELIGIBLE > CONDITIONALLY_ELIGIBLE > NOT_ELIGIBLE > BLOCKED
            priority_order = ["ELIGIBLE", "CONDITIONALLY_ELIGIBLE", "NOT_ELIGIBLE", "BLOCKED"]
            for priority_band in priority_order:
                if priority_band in tied_bands:
                    dominant_action_eligibility_band_val = priority_band
                    break
            if dominant_action_eligibility_band_val is None:
                dominant_action_eligibility_band_val = sorted(tied_bands)[0]  # Fallback to alphabetical

        # Collect unique action eligibility tags (deduplicate and sort for determinism)
        if all_action_eligibility_tags:
            action_eligibility_tags_list = sorted(set(all_action_eligibility_tags))

        # Phase 51: CRA (Cognitive Resonance Aggregator) - Pre-RAG internal cognition aggregation
        # CRA aggregates ONLY internal metrics from implemented phases (NO RAG data)

        # Extract CRA resonance from Phases 3, 8, 24 (resonance metrics)
        cra_resonance_values = []
        if avg_resonance_index is not None:  # Phase 3
            cra_resonance_values.append(avg_resonance_index)
        if avg_guna_resonance is not None:  # Phase 8
            cra_resonance_values.append(avg_guna_resonance)
        if avg_kosha_resonance is not None:  # Phase 8
            cra_resonance_values.append(avg_kosha_resonance)
        if avg_resonance_entropy_val is not None:  # Phase 24
            # Invert entropy: lower entropy = better resonance
            cra_resonance_values.append(1.0 - avg_resonance_entropy_val)

        if cra_resonance_values:
            avg_cra_resonance_val = sum(cra_resonance_values) / len(cra_resonance_values)

        # Extract CRA alignment from Phases 3, 21, 22, 42, 44, 47 (alignment metrics)
        cra_alignment_values = []
        if avg_arc_alignment_index is not None:  # Phase 3
            cra_alignment_values.append(avg_arc_alignment_index)
        if avg_loop_alignment is not None:  # Phase 21
            cra_alignment_values.append(avg_loop_alignment)
        if avg_cycle_alignment is not None:  # Phase 22
            cra_alignment_values.append(avg_cycle_alignment)
        if avg_scenario_alignment_val is not None:  # Phase 42
            cra_alignment_values.append(avg_scenario_alignment_val)
        if avg_csae_alignment_val is not None:  # Phase 44
            cra_alignment_values.append(avg_csae_alignment_val)
        if avg_synthesis_alignment_val is not None:  # Phase 47
            cra_alignment_values.append(avg_synthesis_alignment_val)

        if cra_alignment_values:
            avg_cra_alignment_val = sum(cra_alignment_values) / len(cra_alignment_values)

        # Extract CRA stability from Phases 23, 26, 45, 46, 47, 48, 49 (stability metrics)
        cra_stability_values = []
        if cause_chain_stability_avg_val is not None:  # Phase 23
            cra_stability_values.append(cause_chain_stability_avg_val)
        if avg_csi_val is not None:  # Phase 26 - Consciousness Stability Index
            cra_stability_values.append(avg_csi_val)
        if avg_tsi_val > 0.0:  # Phase 45 - Trajectory Stability Index
            cra_stability_values.append(avg_tsi_val)
        if avg_trajectory_stability_val is not None:  # Phase 46
            cra_stability_values.append(avg_trajectory_stability_val)
        if avg_synthesis_integrity_val is not None:  # Phase 47
            cra_stability_values.append(avg_synthesis_integrity_val)
        if avg_macro_stability_val is not None:  # Phase 48
            cra_stability_values.append(avg_macro_stability_val)
        if avg_temporal_stability_val is not None:  # Phase 49
            cra_stability_values.append(avg_temporal_stability_val)

        if cra_stability_values:
            avg_cra_stability_val = sum(cra_stability_values) / len(cra_stability_values)

        # Extract CRA consistency from Phases 27, 50 (internal consistency)
        cra_consistency_values = []
        if avg_symbolic_harmonization_val is not None:  # Phase 27
            cra_consistency_values.append(avg_symbolic_harmonization_val)
        if avg_internal_consistency_strength_val is not None:  # Phase 50
            cra_consistency_values.append(avg_internal_consistency_strength_val)
        if avg_regression_alignment_val is not None:  # Phase 50 - Cross-layer regression alignment
            cra_consistency_values.append(avg_regression_alignment_val)

        if cra_consistency_values:
            avg_cra_consistency_val = sum(cra_consistency_values) / len(cra_consistency_values)

        # Compute CRA overall score and determine dominant_cra_band
        avg_cra_overall_val = None
        cra_overall_values = []
        if avg_cra_resonance_val is not None:
            cra_overall_values.append(avg_cra_resonance_val)
        if avg_cra_alignment_val is not None:
            cra_overall_values.append(avg_cra_alignment_val)
        if avg_cra_stability_val is not None:
            cra_overall_values.append(avg_cra_stability_val)
        if avg_cra_consistency_val is not None:
            cra_overall_values.append(avg_cra_consistency_val)

        if cra_overall_values:
            avg_cra_overall_val = sum(cra_overall_values) / len(cra_overall_values)
            if avg_cra_overall_val >= 0.70:
                dominant_cra_band_val = "HIGH_ALIGNMENT"
            elif avg_cra_overall_val >= 0.40:
                dominant_cra_band_val = "MEDIUM_ALIGNMENT"
            else:
                dominant_cra_band_val = "LOW_ALIGNMENT"

        # Aggregate CRA pattern tags from Phases 23-50 (diagnostic tags)
        all_cra_tags = []
        if inversion_pattern_tags:  # Phase 23
            all_cra_tags.extend(inversion_pattern_tags)
        if resonance_weighting_notes_list:  # Phase 24
            all_cra_tags.extend(resonance_weighting_notes_list)
        if ucf_notes_list:  # Phase 26
            all_cra_tags.extend(ucf_notes_list)
        if symbolic_harmonization_notes_list:  # Phase 27
            all_cra_tags.extend(symbolic_harmonization_notes_list)
        if regime_notes_list:  # Phase 41
            all_cra_tags.extend(regime_notes_list)
        if scenario_pattern_tags_list:  # Phase 42
            all_cra_tags.extend(scenario_pattern_tags_list)
        if csae_alignment_tags_list:  # Phase 44
            all_cra_tags.extend(csae_alignment_tags_list)
        if mtsf_tags_list:  # Phase 45
            all_cra_tags.extend(mtsf_tags_list)
        if tfce_tags_list:  # Phase 46
            all_cra_tags.extend(tfce_tags_list)
        if synthesis_tags_list:  # Phase 47
            all_cra_tags.extend(synthesis_tags_list)
        if macro_stability_tags_list:  # Phase 48
            all_cra_tags.extend(macro_stability_tags_list)
        if regression_consistency_tags_list:  # Phase 50
            all_cra_tags.extend(regression_consistency_tags_list)

        # Deduplicate and sort CRA tags for determinism
        if all_cra_tags:
            cra_pattern_tags_list = sorted(set(all_cra_tags))

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
        avg_vritti_momentum=avg_vritti_momentum,
        max_vritti_momentum=max_vritti_momentum,
        min_vritti_momentum=min_vritti_momentum,
        avg_arc_tension_harmonizer=avg_arc_tension_harmonizer,
        max_arc_tension_harmonizer=max_arc_tension_harmonizer,
        min_arc_tension_harmonizer=min_arc_tension_harmonizer,
        avg_temporal_entropy_diff=avg_temporal_entropy_diff,
        avg_temporal_entropy_volatility=avg_temporal_entropy_volatility,
        temporal_entropy_regime=temporal_entropy_regime,
        avg_loop_alignment=avg_loop_alignment,
        avg_loop_tension=avg_loop_tension,
        avg_reversal_probability=avg_reversal_probability,
        dominant_loop_stability_band=dominant_loop_stability_band,
        reversal_probability_trend=reversal_probability_trend,
        dominant_cycle_type=dominant_cycle_type,
        dominant_cycle_stability_band=dominant_cycle_stability_band,
        avg_cycle_alignment=avg_cycle_alignment,
        avg_cycle_tension=avg_cycle_tension,
        avg_cycle_reversal_probability=avg_cycle_reversal_probability,
        cycle_count=cycle_count,
        avg_inversion_score=avg_inversion_score_val,
        dominant_inversion_band=dominant_inversion_band,
        cause_chain_stability_avg=cause_chain_stability_avg_val,
        inversion_pattern_tags=inversion_pattern_tags,
        avg_resonance_entropy=avg_resonance_entropy_val,
        dominant_resonance_metrics=dominant_resonance_metrics_list,
        resonance_weighting_notes=resonance_weighting_notes_list,
        avg_coi=avg_coi_val,
        avg_csi=avg_csi_val,
        avg_cip=avg_cip_val,
        ucf_entropy_band=ucf_entropy_band_val,
        dominant_ucf_signals=dominant_ucf_signals_list,
        ucf_notes=ucf_notes_list,
        avg_symbolic_harmonization=avg_symbolic_harmonization_val,
        dominant_symbolic_harmonization_pattern=dominant_symbolic_harmonization_pattern_val,
        symbolic_harmonization_notes=symbolic_harmonization_notes_list,
        avg_drift_fusion_index=avg_drift_fusion_index,
        dominant_drift_risk_band=dominant_drift_risk_band,
        drift_pattern_frequency=drift_pattern_frequency,
        dominant_coherence_regime=dominant_coherence_regime_val,
        regime_band=regime_band_val,
        regime_frequency=regime_frequency_val,
        regime_notes=regime_notes_list,
        avg_scenario_alignment=avg_scenario_alignment_val,
        avg_scenario_divergence=avg_scenario_divergence_val,
        scenario_uncertainty_band=scenario_uncertainty_band_val,
        dominant_fused_future_path=dominant_fused_future_path_val,
        scenario_pattern_tags=scenario_pattern_tags_list,
        avg_csae_alignment=avg_csae_alignment_val,
        avg_csae_conflict=avg_csae_conflict_val,
        avg_csae_stability=avg_csae_stability_val,
        csae_alignment_band=csae_alignment_band_val,
        csae_alignment_tags=csae_alignment_tags_list,
        avg_tsi=avg_tsi_val,
        avg_tvi=avg_tvi_val,
        avg_chf=avg_chf_val,
        avg_scc=avg_scc_val,
        mtsf_band=mtsf_band_val,
        mtsf_tags=mtsf_tags_list,
        avg_trajectory_convergence=avg_trajectory_convergence_val,
        avg_trajectory_divergence=avg_trajectory_divergence_val,
        avg_trajectory_stability=avg_trajectory_stability_val,
        dominant_convergence_band=dominant_convergence_band_val,
        dominant_convergence_tags=tfce_tags_list,
        avg_synthesis_integrity=avg_synthesis_integrity_val,
        avg_future_alignment=avg_synthesis_alignment_val,
        avg_future_divergence_risk=avg_synthesis_divergence_val,
        dominant_synthesis_band=dominant_synthesis_band_val,
        synthesis_tags=synthesis_tags_list,
        avg_macro_stability=avg_macro_stability_val,
        avg_macro_divergence=avg_macro_divergence_val,
        avg_macro_predictive_confidence=avg_macro_predictive_confidence_val,
        avg_macro_identity_resilience=avg_macro_identity_resilience_val,
        dominant_macro_stability_band=dominant_macro_stability_band_val,
        macro_stability_tags=macro_stability_tags_list,
        avg_temporal_stability=avg_temporal_stability_val,
        avg_predictive_entropy=avg_predictive_entropy_val,
        avg_future_consistency=avg_future_consistency_val,
        dominant_temporal_regime=dominant_temporal_regime_val,
        temporal_stability_band=temporal_stability_band_val,
        avg_regression_stability=avg_regression_stability_val,
        avg_regression_alignment=avg_regression_alignment_val,
        avg_regression_drift=avg_regression_drift_val,
        avg_prediction_reversal_risk=avg_prediction_reversal_risk_val,
        avg_internal_consistency_strength=avg_internal_consistency_strength_val,
        regression_consistency_band=regression_consistency_band_val,
        regression_consistency_tags=regression_consistency_tags_list,
        avg_rag_alignment=avg_rag_alignment_val,
        avg_rag_conflict=avg_rag_conflict_val,
        avg_rag_stability=avg_rag_stability_val,
        avg_rag_relevance=avg_rag_relevance_val,
        avg_rag_support_density=avg_rag_support_density_val,
        dominant_rag_band=dominant_rag_band_val,
        rag_diagnostic_tags=rag_diagnostic_tags_list,
        avg_cra_resonance=avg_cra_resonance_val,
        avg_cra_alignment=avg_cra_alignment_val,
        avg_cra_stability=avg_cra_stability_val,
        avg_cra_consistency=avg_cra_consistency_val,
        dominant_cra_band=dominant_cra_band_val,
        cra_pattern_tags=cra_pattern_tags_list,
        avg_internal_external_alignment=avg_internal_external_alignment_val,
        avg_internal_external_conflict=avg_internal_external_conflict_val,
        avg_internal_external_stability=avg_internal_external_stability_val,
        dominant_ier_cve_band=dominant_ier_cve_band_val,
        ier_cve_tags=ier_cve_tags_list,
        avg_external_trust_score=avg_external_trust_score_val,
        avg_internal_override_pressure=avg_internal_override_pressure_val,
        avg_external_signal_fragility=avg_external_signal_fragility_val,
        avg_alignment_resilience=avg_alignment_resilience_val,
        avg_trust_decay_risk=avg_trust_decay_risk_val,
        dominant_trust_band=dominant_trust_band_val,
        ertce_tags=ertce_tags_list,
        avg_action_eligibility_score=avg_action_eligibility_score_val,
        dominant_action_eligibility_band=dominant_action_eligibility_band_val,
        action_eligibility_tags=action_eligibility_tags_list,
    )
