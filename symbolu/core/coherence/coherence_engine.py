"""
CoherenceEngine - Main orchestrator for multi-turn coherence tracking.

Updates CoherenceState by:
- Appending latest turn data to histories
- Computing all coherence metrics
- Maintaining sliding window
"""

from typing import Optional, Dict, Any
from symbolu.core.coherence.coherence_state import CoherenceState
from symbolu.core.coherence.persona_drift_monitor import compute_persona_drift
from symbolu.core.coherence.semantic_skeleton import compute_semantic_stability
from symbolu.core.coherence.temporal_arc_tracer import compute_temporal_arc_score


class CoherenceEngine:
    """
    Main engine for tracking and updating conversation-level coherence.

    Maintains sliding window of conversation history and computes
    coherence metrics across multiple dimensions.
    """

    def __init__(self, window: int = 10):
        """
        Initialize CoherenceEngine.

        Args:
            window: Sliding window size for history retention (default: 10 turns)
        """
        self.window = window

    def update_state(
        self,
        prev_state: Optional[CoherenceState],
        convo_id: str,
        turn_index: int,
        routing_plan: Any,  # RoutingPlan from TTOR
        mapper_profile: Dict,
        temporal_summary: Optional[Dict],
        semantic_signature: Dict,
    ) -> CoherenceState:
        """
        Update coherence state with new turn data.

        Args:
            prev_state: Previous CoherenceState (None for first turn)
            convo_id: Conversation identifier
            turn_index: Current turn index
            routing_plan: TTOR RoutingPlan for this turn
            mapper_profile: MapperProfile dict for this turn
            temporal_summary: TemporalBhavaTracker summary (optional)
            semantic_signature: Semantic skeleton for this turn

        Returns:
            Updated CoherenceState with recomputed metrics
        """
        # Initialize or copy previous state
        if prev_state is None:
            state = CoherenceState(convo_id=convo_id, turn_index=turn_index)
        else:
            # Create new state, copying histories
            state = CoherenceState(
                convo_id=convo_id,
                turn_index=turn_index,
                tier_history=prev_state.tier_history.copy(),
                domain_history=prev_state.domain_history.copy(),
                mapper_profile_history=prev_state.mapper_profile_history.copy(),
                smi_history=prev_state.smi_history.copy(),
                bhava_id_history=prev_state.bhava_id_history.copy(),
                bhava_direction_history=prev_state.bhava_direction_history.copy(),
                tension_history=prev_state.tension_history.copy(),
                temporal_flags_history=prev_state.temporal_flags_history.copy(),
                delta_smi_history=prev_state.delta_smi_history.copy(),
                bhava_gap_history=prev_state.bhava_gap_history.copy(),
                tension_corridor_history=prev_state.tension_corridor_history.copy(),
            )

        # Append new turn data to histories
        state.tier_history.append(self._extract_tier(routing_plan))
        state.domain_history.append(self._extract_domain(routing_plan))
        state.mapper_profile_history.append(mapper_profile.copy())
        state.smi_history.append(self._extract_smi(routing_plan, temporal_summary))
        state.bhava_id_history.append(self._extract_bhava_id(temporal_summary))
        state.bhava_direction_history.append(self._extract_bhava_direction(temporal_summary))
        state.tension_history.append(self._extract_tension(routing_plan))
        state.temporal_flags_history.append(self._extract_temporal_flags(temporal_summary))

        # Phase 1 formulas (passive observation - not used in scoring yet)
        state.delta_smi_history.append(self._extract_delta_smi(temporal_summary))
        state.bhava_gap_history.append(self._extract_bhava_gap(temporal_summary))
        state.tension_corridor_history.append(self._extract_tension_corridor(temporal_summary))

        # Trim to sliding window
        state.window_trim(self.window)

        # Recompute all metrics
        state.persona_drift_score = self._compute_persona_drift(state)
        state.semantic_stability_score = self._compute_semantic_stability(state, semantic_signature)
        state.mapper_volatility_score = self._compute_mapper_volatility(state)
        state.temporal_arc_score = self._compute_temporal_arc(state)
        state.coherence_score = self._compute_overall_coherence(state)

        # Update Phase 2 formula aggregates (observation only)
        self._update_formula_aggregates(state)

        # Update Phase 3 derived formula metrics (observation only)
        self._update_derived_formula_metrics(state)

        return state

    def _extract_tier(self, routing_plan: Any) -> str:
        """Extract tier from routing plan."""
        if hasattr(routing_plan, "tier"):
            return routing_plan.tier
        return "hybrid"  # Default

    def _extract_domain(self, routing_plan: Any) -> str:
        """Extract domain from routing plan."""
        if hasattr(routing_plan, "domain"):
            return routing_plan.domain
        return "general"  # Default

    def _extract_smi(self, routing_plan: Any, temporal_summary: Optional[Dict]) -> float:
        """Extract SMI/authenticity index."""
        # Try temporal summary first
        if temporal_summary and "smi" in temporal_summary:
            return temporal_summary["smi"]

        # Fall back to routing plan tension as proxy
        if hasattr(routing_plan, "long_arc_tension"):
            return routing_plan.long_arc_tension

        return 0.5  # Default neutral

    def _extract_bhava_id(self, temporal_summary: Optional[Dict]) -> int:
        """Extract bhava ID from temporal summary."""
        if temporal_summary and "bhava_id" in temporal_summary:
            return temporal_summary["bhava_id"]
        return 0  # Default

    def _extract_bhava_direction(self, temporal_summary: Optional[Dict]) -> str:
        """Extract bhava direction from temporal summary."""
        if temporal_summary and "bhava_direction" in temporal_summary:
            return temporal_summary["bhava_direction"]
        return "stable"  # Default

    def _extract_tension(self, routing_plan: Any) -> float:
        """Extract long_arc_tension from routing plan."""
        if hasattr(routing_plan, "long_arc_tension"):
            return routing_plan.long_arc_tension
        return 0.0  # Default

    def _extract_temporal_flags(self, temporal_summary: Optional[Dict]) -> Dict[str, bool]:
        """Extract temporal flags from temporal summary."""
        if temporal_summary and "flags" in temporal_summary:
            return temporal_summary["flags"].copy()

        # Default empty flags
        return {
            "tension_corridor": False,
            "recovery_trajectory": False,
            "resilience_pattern": False,
            "chronic_stress": False,
            "breakthrough_insight": False,
        }

    def _extract_delta_smi(self, temporal_summary: Optional[Dict]) -> Optional[float]:
        """Extract delta_smi from temporal summary (Phase 1 formula)."""
        if temporal_summary and "delta_smi" in temporal_summary:
            return temporal_summary["delta_smi"]
        return None

    def _extract_bhava_gap(self, temporal_summary: Optional[Dict]) -> Optional[float]:
        """Extract bhava_gap from temporal summary (Phase 1 formula)."""
        if temporal_summary and "bhava_gap" in temporal_summary:
            return temporal_summary["bhava_gap"]
        return None

    def _extract_tension_corridor(self, temporal_summary: Optional[Dict]) -> Optional[float]:
        """Extract tension_corridor from temporal summary (Phase 1 formula)."""
        if temporal_summary and "tension_corridor" in temporal_summary:
            return temporal_summary["tension_corridor"]
        return None

    def _compute_persona_drift(self, state: CoherenceState) -> float:
        """Compute persona drift score."""
        return compute_persona_drift(
            domain_history=state.domain_history,
            mapper_profile_history=state.mapper_profile_history,
            bhava_id_history=state.bhava_id_history,
            bhava_direction_history=state.bhava_direction_history,
        )

    def _compute_semantic_stability(
        self, state: CoherenceState, current_signature: Dict
    ) -> float:
        """Compute semantic stability score."""
        # Build skeleton history (we don't store full skeleton history in state,
        # so we use current signature as the latest data point)
        # For full implementation, we'd need to store skeleton_history in CoherenceState
        # For now, return a placeholder based on available data
        if len(state.domain_history) < 2:
            return 1.0  # Not enough history

        # Heuristic: stability inversely related to domain changes
        # (In production, we'd maintain full skeleton history)
        domain_changes = sum(
            1 for i in range(1, len(state.domain_history))
            if state.domain_history[i] != state.domain_history[i - 1]
        )
        stability = 1.0 - (domain_changes / (len(state.domain_history) - 1))
        return max(0.0, min(1.0, stability))

    def _compute_mapper_volatility(self, state: CoherenceState) -> float:
        """Compute mapper volatility score."""
        if len(state.mapper_profile_history) < 2:
            return 0.0  # No volatility possible

        volatility_sum = 0.0
        num_comparisons = len(state.mapper_profile_history) - 1

        for i in range(1, len(state.mapper_profile_history)):
            prev_profile = state.mapper_profile_history[i - 1]
            curr_profile = state.mapper_profile_history[i]

            # Count resolution_level changes
            if prev_profile.get("resolution_level") != curr_profile.get("resolution_level"):
                volatility_sum += 1.0

            # Count arc_mode changes
            if prev_profile.get("arc_mode") != curr_profile.get("arc_mode"):
                volatility_sum += 1.0

            # Add bias deltas (normalized)
            for bias_key in ["detail_bias", "practical_bias", "reflective_bias"]:
                prev_bias = prev_profile.get(bias_key, 0.0)
                curr_bias = curr_profile.get(bias_key, 0.0)
                volatility_sum += abs(curr_bias - prev_bias)

        # Normalize to 0-1 (heuristic: 5 changes per turn is max volatility)
        volatility = volatility_sum / (num_comparisons * 5.0)
        return max(0.0, min(1.0, volatility))

    def _compute_temporal_arc(self, state: CoherenceState) -> float:
        """Compute temporal arc score."""
        return compute_temporal_arc_score(
            temporal_flags_history=state.temporal_flags_history,
            tension_history=state.tension_history,
        )

    def _compute_overall_coherence(self, state: CoherenceState) -> float:
        """
        Compute overall coherence score from component metrics.

        Formula:
            coherence = 0.30 * semantic_stability
                      + 0.25 * temporal_arc
                      + 0.25 * (1 - persona_drift)
                      + 0.20 * (1 - mapper_volatility)
        """
        coherence = (
            0.30 * state.semantic_stability_score
            + 0.25 * state.temporal_arc_score
            + 0.25 * (1.0 - state.persona_drift_score)
            + 0.20 * (1.0 - state.mapper_volatility_score)
        )

        return max(0.0, min(1.0, coherence))

    def _update_formula_aggregates(self, state: CoherenceState) -> None:
        """
        Update Phase 2 formula aggregates (observation only).

        This method computes aggregate statistics from formula histories:
        - avg_smi, max_smi, min_smi from smi_history
        - avg_tension_corridor, max_tension_corridor from tension_corridor_history

        These aggregates are for observability only and do NOT affect scoring.

        Args:
            state: CoherenceState to update in place
        """
        # Compute SMI aggregates
        valid_smis = [s for s in state.smi_history if s is not None]
        if valid_smis:
            state.avg_smi = sum(valid_smis) / len(valid_smis)
            state.max_smi = max(valid_smis)
            state.min_smi = min(valid_smis)
        else:
            state.avg_smi = None
            state.max_smi = None
            state.min_smi = None

        # Compute tension corridor aggregates
        valid_corridors = [tc for tc in state.tension_corridor_history if tc is not None]
        if valid_corridors:
            state.avg_tension_corridor = sum(valid_corridors) / len(valid_corridors)
            state.max_tension_corridor = max(valid_corridors)
        else:
            state.avg_tension_corridor = None
            state.max_tension_corridor = None

    def _update_derived_formula_metrics(self, state: CoherenceState) -> None:
        """
        Update Phase 3 derived formula metrics (observation only).

        Computes three derived indices from Phase 1 formulas:
        1. resonance_index: overall stabilizing signal (high SMI, small gap, small delta)
        2. tension_index: session tension (from Tension Corridor)
        3. arc_alignment_index: temporal pattern alignment (improving trajectory)

        These metrics are for observability only and do NOT affect existing scoring.

        Args:
            state: CoherenceState to update in place
        """
        # Get most recent formula values
        smi = state.smi_history[-1] if state.smi_history else None
        delta_smi = state.delta_smi_history[-1] if state.delta_smi_history else None
        bhava_gap = state.bhava_gap_history[-1] if state.bhava_gap_history else None
        tension = state.tension_corridor_history[-1] if state.tension_corridor_history else None

        # Only compute if we have formula data
        if smi is None or bhava_gap is None or tension is None:
            state.resonance_index = None
            state.tension_index = None
            state.arc_alignment_index = None
            return

        # Helper: clamp function
        def clamp(value: float, min_val: float, max_val: float) -> float:
            return max(min_val, min(max_val, value))

        # 1. RESONANCE INDEX
        # Intuition: high SMI + small Bhava Gap + small |ΔSMI|
        # Normalize gap: 1 = close (gap=0), 0 = far (gap=1.0)
        gap_norm = 1.0 - bhava_gap

        # Normalize delta: 1 = stable (delta=0), 0 = very jumpy (|delta|=1.0)
        if delta_smi is not None:
            delta_norm = 1.0 - min(abs(delta_smi), 1.0)
        else:
            delta_norm = 1.0  # First turn, assume stable

        state.resonance_index = clamp(
            0.5 * smi + 0.3 * gap_norm + 0.2 * delta_norm,
            0.0,
            1.0,
        )

        # 2. TENSION INDEX
        # Intuition: directly from Tension Corridor, smoothed with delta volatility
        state.tension_index = clamp(
            0.7 * tension + 0.3 * (1.0 - delta_norm),
            0.0,
            1.0,
        )

        # 3. ARC ALIGNMENT INDEX
        # Intuition: how well SMI + ΔSMI + gap match a smooth, improving trajectory
        # improving = 1.0 if delta > 0, else 0.0
        if delta_smi is not None and delta_smi > 0.0:
            improving = 1.0
        else:
            improving = 0.0

        state.arc_alignment_index = clamp(
            0.4 * smi + 0.3 * gap_norm + 0.3 * improving,
            0.0,
            1.0,
        )
