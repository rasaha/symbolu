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
from symbolu.formulas.guna_kosha_resonance import compute_guna_kosha_resonance
from symbolu.formulas.formula_fusion_stabilizer import compute_coherence_fused


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
                vritti_momentum_history=prev_state.vritti_momentum_history.copy(),
                arc_tension_harmonizer_history=prev_state.arc_tension_harmonizer_history.copy(),
                coherence_fused_history=prev_state.coherence_fused_history.copy(),
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

        # Phase 14 formulas (observation only - not used in scoring)
        state.vritti_momentum_history.append(self._extract_vritti_momentum(temporal_summary))
        state.arc_tension_harmonizer_history.append(self._extract_arc_tension_harmonizer(temporal_summary))

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

        # Update Phase 14 formula aggregates (observation only)
        self._update_phase14_formula_aggregates(state)

        # Update Phase 3 derived formula metrics (observation only)
        self._update_derived_formula_metrics(state)

        # Update Phase 4 coherence v2 (formula-aware, observation only)
        state.coherence_score_v2 = self._compute_coherence_score_v2(state)

        # Update Phase 8 Guna/Kosha resonance (observation only)
        self._update_guna_kosha_resonance(state, routing_plan, temporal_summary)

        # Update Phase 10 coherence v3 (megafusion, observation only)
        state.coherence_score_v3 = self._compute_coherence_score_v3(state, mapper_profile)

        # Update Phase 12 coherence v3 quality (soft stability windows)
        state.coherence_v3_quality = self._compute_coherence_v3_quality(
            base=state.coherence_score,
            v3=state.coherence_score_v3,
            resonance_index=state.resonance_index,
            arc_alignment_index=state.arc_alignment_index,
            tension_index=state.tension_index,
        )

        # Update Phase 16 formula fusion stabilizer (observation only)
        self._update_formula_fusion_stabilizer(state, mapper_profile)

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

    def _extract_vritti_momentum(self, temporal_summary: Optional[Dict]) -> Optional[float]:
        """Extract vritti_momentum from temporal summary (Phase 14 formula)."""
        if temporal_summary and "vritti_momentum" in temporal_summary:
            return temporal_summary["vritti_momentum"]
        return None

    def _extract_arc_tension_harmonizer(self, temporal_summary: Optional[Dict]) -> Optional[float]:
        """Extract arc_tension_harmonizer from temporal summary (Phase 14 formula)."""
        if temporal_summary and "arc_tension_harmonizer" in temporal_summary:
            return temporal_summary["arc_tension_harmonizer"]
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

    def _update_phase14_formula_aggregates(self, state: CoherenceState) -> None:
        """
        Update Phase 14 formula aggregates (observation only).

        This method computes aggregate statistics from Phase 14 formula histories:
        - avg_vritti_momentum, max_vritti_momentum, min_vritti_momentum from vritti_momentum_history
        - avg_arc_tension_harmonizer, max_arc_tension_harmonizer, min_arc_tension_harmonizer
          from arc_tension_harmonizer_history

        These aggregates are for observability only and do NOT affect scoring.

        Args:
            state: CoherenceState to update in place
        """
        # Compute Vritti Momentum aggregates
        valid_vmf = [v for v in state.vritti_momentum_history if v is not None]
        if valid_vmf:
            state.avg_vritti_momentum = sum(valid_vmf) / len(valid_vmf)
            state.max_vritti_momentum = max(valid_vmf)
            state.min_vritti_momentum = min(valid_vmf)
        else:
            state.avg_vritti_momentum = None
            state.max_vritti_momentum = None
            state.min_vritti_momentum = None

        # Compute Arc-Tension Harmonizer aggregates
        valid_ath = [a for a in state.arc_tension_harmonizer_history if a is not None]
        if valid_ath:
            state.avg_arc_tension_harmonizer = sum(valid_ath) / len(valid_ath)
            state.max_arc_tension_harmonizer = max(valid_ath)
            state.min_arc_tension_harmonizer = min(valid_ath)
        else:
            state.avg_arc_tension_harmonizer = None
            state.max_arc_tension_harmonizer = None
            state.min_arc_tension_harmonizer = None

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

    def _compute_coherence_score_v2(self, state: CoherenceState) -> Optional[float]:
        """
        Compute Phase 4 formula-aware coherence score v2.

        This is the formula-aware coherence score that incorporates Phase 1 + Phase 3
        formula signals (SMI, ΔSMI, Bhava Gap, Tension Corridor, Resonance Index,
        Tension Index, Arc Alignment Index).

        Formula:
            coherence_score_v2 = clamp(
                0.55 * base +
                0.20 * resonance_index +
                0.15 * arc_alignment_index +
                0.10 * (1.0 - tension_index),
                0.0,
                1.0
            )

        Where:
            - base = coherence_score (v1 canonical)
            - resonance_index = Phase 3 stabilizing signal
            - arc_alignment_index = Phase 3 temporal pattern alignment
            - tension_index = Phase 3 session tension
            - tension_penalty = 1.0 - tension_index (high tension → low penalty)

        Returns:
            Optional[float]: v2 coherence score (0.0-1.0), or None if required
                           derived metrics are not available

        Note:
            This score is NOT used in existing pipeline behavior unless explicitly
            enabled via domain profile feature flags (Phase 4 policy integration).
        """
        # Get required inputs
        base = state.coherence_score  # v1 canonical
        res = state.resonance_index
        ten = state.tension_index
        arc = state.arc_alignment_index

        # If any required derived metric is missing, return None
        if res is None or ten is None or arc is None:
            return None

        # Helper: clamp function (reuse from Phase 3)
        def clamp(value: float, min_val: float, max_val: float) -> float:
            return max(min_val, min(max_val, value))

        # Normalize tension: higher tension_index → lower coherence
        tension_penalty = 1.0 - ten

        # Compute v2 score with canonical Phase 4 formula
        coherence_score_v2 = clamp(
            0.55 * base + 0.20 * res + 0.15 * arc + 0.10 * tension_penalty,
            0.0,
            1.0,
        )

        return coherence_score_v2

    def _update_guna_kosha_resonance(
        self,
        state: CoherenceState,
        routing_plan: Any,
        temporal_summary: Optional[Dict],
    ) -> None:
        """
        Update Phase 8 Guna/Kosha resonance metrics (observation only).

        This method extracts guna_probs and kosha_probs from available inputs
        (routing_plan or temporal_summary) and computes resonance indices.

        These metrics are for observability only and do NOT affect existing scoring
        or routing behavior. They are purely passive observations.

        Args:
            state: CoherenceState to update in place
            routing_plan: TTOR RoutingPlan (may contain guna/kosha data)
            temporal_summary: TemporalBhavaTracker summary (may contain guna/kosha data)
        """
        # Extract guna_probs (try temporal_summary first, then routing_plan)
        guna_probs = None
        if temporal_summary and "guna_probs" in temporal_summary:
            guna_probs = temporal_summary["guna_probs"]
        elif hasattr(routing_plan, "guna_probs"):
            guna_probs = routing_plan.guna_probs

        # Extract kosha_probs (try temporal_summary first, then routing_plan)
        kosha_probs = None
        if temporal_summary and "kosha_probs" in temporal_summary:
            kosha_probs = temporal_summary["kosha_probs"]
        elif hasattr(routing_plan, "kosha_probs"):
            kosha_probs = routing_plan.kosha_probs

        # If no input data, reset to None and return
        if not guna_probs and not kosha_probs:
            state.guna_resonance_index = None
            state.kosha_resonance_index = None
            state.kosha_activation_vector = None
            return

        # Compute resonance metrics (gracefully handles None inputs)
        try:
            result = compute_guna_kosha_resonance(guna_probs, kosha_probs)

            if result is not None:
                state.guna_resonance_index = result.guna_resonance_index
                state.kosha_resonance_index = result.kosha_resonance_index
                state.kosha_activation_vector = result.kosha_activation_vector
            else:
                # Computation failed (invalid inputs)
                state.guna_resonance_index = None
                state.kosha_resonance_index = None
                state.kosha_activation_vector = None

        except Exception:
            # Graceful degradation: catch any unexpected errors
            state.guna_resonance_index = None
            state.kosha_resonance_index = None
            state.kosha_activation_vector = None

    def _bias_synergy(self, guna_bias: float, kosha_bias: float) -> float:
        """
        Compute bias synergy from guna and kosha resonance biases.

        Phase 10 support function for coherence v3 formula.
        Combines guna_resonance_bias and kosha_resonance_bias into a normalized
        synergy score.

        Formula:
            synergy = clamp((guna_bias + kosha_bias) / 2, -0.10, 0.10)
            return 0.5 + synergy  # Normalize to [0, 1]

        Args:
            guna_bias: Guna resonance bias from mapper profile ([-0.10, +0.10])
            kosha_bias: Kosha resonance bias from mapper profile ([-0.10, +0.10])

        Returns:
            float: Normalized synergy score [0.0, 1.0]
        """
        # Helper: clamp function
        def clamp(value: float, min_val: float, max_val: float) -> float:
            return max(min_val, min(max_val, value))

        # Compute average bias
        synergy = (guna_bias + kosha_bias) / 2.0

        # Clamp to bias range
        synergy = clamp(synergy, -0.10, 0.10)

        # Normalize to [0, 1] range (0.5 = neutral)
        return 0.5 + synergy

    def _harmonics_coherence(self, expression_harmonics: Optional[list]) -> float:
        """
        Compute coherence from expression harmonics.

        Phase 10 support function for coherence v3 formula.
        Computes coherence as inverse of standard deviation of harmonics.
        Lower variance = higher coherence.

        Formula:
            val = 1 - stddev(harmonics)
            return clamp(val, 0.0, 1.0)

        Args:
            expression_harmonics: List of harmonic values from kosha activation

        Returns:
            float: Harmonics coherence score [0.0, 1.0]
                   Returns 1.0 if harmonics is None or empty (neutral)
        """
        # Helper: clamp function
        def clamp(value: float, min_val: float, max_val: float) -> float:
            return max(min_val, min(max_val, value))

        # If no harmonics, return neutral (1.0 = perfect coherence)
        if expression_harmonics is None or len(expression_harmonics) == 0:
            return 1.0

        # If only one harmonic, no variance = perfect coherence
        if len(expression_harmonics) == 1:
            return 1.0

        # Compute standard deviation
        mean = sum(expression_harmonics) / len(expression_harmonics)
        variance = sum((x - mean) ** 2 for x in expression_harmonics) / len(expression_harmonics)
        stddev = variance ** 0.5

        # Coherence = 1 - stddev (clamped to [0, 1])
        coherence = 1.0 - stddev
        return clamp(coherence, 0.0, 1.0)

    def _compute_coherence_score_v3(
        self,
        state: CoherenceState,
        mapper_profile: Dict,
    ) -> Optional[float]:
        """
        Compute Phase 10 Coherence v3 megafusion score (experimental).

        This is the first formula-layer megafusion that integrates:
        - Phase 1 temporal formulas (smi, delta_smi, bhava_gap, tension_corridor)
        - Phase 3 derived metrics (resonance_index, tension_index, arc_alignment_index)
        - Phase 8 resonance metrics (guna_resonance_index, kosha_resonance_index)
        - Phase 9 modulation biases (guna_resonance_bias, kosha_resonance_bias, expression_harmonics)

        Formula (canonical v1.0 draft):
            v3 = clamp(
                0.35 * base
              + 0.15 * resonance_index
              + 0.10 * arc_alignment_index
              + 0.10 * (1 - tension_index)
              + 0.10 * guna_resonance_index
              + 0.10 * kosha_resonance_index
              + 0.05 * _bias_synergy(guna_bias, kosha_bias)
              + 0.05 * _harmonics_coherence(expression_harmonics),
              0.0, 1.0
            )

        Missing Data Rule:
            If ANY required metric is missing → return None.

        Args:
            state: CoherenceState with all metrics
            mapper_profile: MapperProfile dict with Phase 9 biases

        Returns:
            Optional[float]: v3 coherence score (0.0-1.0), or None if required
                           metrics are not available

        Note:
            This score is EXPERIMENTAL and NOT used in existing pipeline behavior
            unless explicitly enabled via domain profile feature flags (Phase 10+).
            By default, use_coherence_v3=False for all domains.
        """
        # Helper: clamp function
        def clamp(value: float, min_val: float, max_val: float) -> float:
            return max(min_val, min(max_val, value))

        # Extract required inputs from CoherenceState
        base = state.coherence_score  # v1 canonical (always available)
        resonance_index = state.resonance_index  # Phase 3
        tension_index = state.tension_index  # Phase 3
        arc_alignment_index = state.arc_alignment_index  # Phase 3
        guna_resonance_index = state.guna_resonance_index  # Phase 8
        kosha_resonance_index = state.kosha_resonance_index  # Phase 8

        # Extract Phase 9 modulation biases from mapper_profile
        guna_bias = mapper_profile.get("guna_resonance_bias", 0.0)
        kosha_bias = mapper_profile.get("kosha_resonance_bias", 0.0)
        expression_harmonics = mapper_profile.get("expression_harmonics", None)

        # Missing data check: If ANY required metric is missing, return None
        if (
            resonance_index is None
            or tension_index is None
            or arc_alignment_index is None
            or guna_resonance_index is None
            or kosha_resonance_index is None
        ):
            return None

        # Compute support metrics
        bias_synergy = self._bias_synergy(guna_bias, kosha_bias)
        harmonics_coherence = self._harmonics_coherence(expression_harmonics)

        # Compute v3 score with canonical Phase 10 formula
        coherence_score_v3 = clamp(
            0.35 * base
            + 0.15 * resonance_index
            + 0.10 * arc_alignment_index
            + 0.10 * (1.0 - tension_index)  # Tension penalty
            + 0.10 * guna_resonance_index
            + 0.10 * kosha_resonance_index
            + 0.05 * bias_synergy
            + 0.05 * harmonics_coherence,
            0.0,
            1.0,
        )

        return coherence_score_v3

    def _compute_coherence_v3_quality(
        self,
        base: Optional[float],
        v3: Optional[float],
        resonance_index: Optional[float],
        arc_alignment_index: Optional[float],
        tension_index: Optional[float],
    ) -> Optional[float]:
        """
        Compute Phase 12 Coherence v3 quality metric (soft stability windows).

        This metric evaluates the STABILITY and RELIABILITY of v3 score by checking:
        1. Soft stability windows for resonance, arc alignment, and tension
        2. Divergence between v1 (base) and v3 scores
        3. Overall quality confidence in [0.0, 1.0]

        The quality score gates v3 usage in policy: if quality is too low, policy
        cascades to v2 or v1 instead of trusting v3.

        Soft Window Logic (piecewise linear, continuous):
        - Resonance window: encourages moderate-high resonance [0.3, 0.7]
        - Arc alignment window: encourages aligned temporal patterns [0.3, 0.7]
        - Tension window: penalizes high tension, prefers low-moderate [0.3, 0.7]

        Divergence Penalty:
        - No penalty if |v3 - base| <= 0.05
        - Max penalty if |v3 - base| >= 0.30
        - Linear interpolation between

        Final Formula:
            stability_core = 0.4 * w_r + 0.3 * w_a + 0.3 * w_t
            divergence_penalty = smooth_penalty(|v3 - base|)
            quality = stability_core * (1.0 - 0.6 * divergence_penalty)
            return clamp(quality, 0.0, 1.0)

        Args:
            base: Coherence score v1 (canonical, always available)
            v3: Coherence score v3 (optional, megafusion)
            resonance_index: Phase 3 resonance index [0.0, 1.0]
            arc_alignment_index: Phase 3 arc alignment index [0.0, 1.0]
            tension_index: Phase 3 tension index [0.0, 1.0]

        Returns:
            Optional[float]: v3 quality score [0.0, 1.0], or None if required inputs missing

        Note:
            This is a ZERO-LLM, deterministic metric. It does NOT modify any existing
            pipeline behavior. It is purely a gating mechanism for v3 usage in policy.
        """
        # Helper: clamp function
        def clamp(value: float, min_val: float, max_val: float) -> float:
            return max(min_val, min(max_val, value))

        # Missing data check: If base or v3 are missing, return None
        if base is None or v3 is None:
            return None

        # Graceful defaults for missing metrics (neutral 0.5 midpoint)
        resonance = resonance_index if resonance_index is not None else 0.5
        arc_alignment = arc_alignment_index if arc_alignment_index is not None else 0.5
        tension = tension_index if tension_index is not None else 0.5

        # ========================================================================
        # SOFT STABILITY WINDOWS (piecewise linear, continuous)
        # ========================================================================

        # Resonance window w_r: encourages moderate-high resonance [0.3, 0.7]
        if resonance <= 0.3:
            w_r = 0.0
        elif resonance >= 0.7:
            w_r = 1.0
        else:
            w_r = (resonance - 0.3) / 0.4

        # Arc alignment window w_a: encourages aligned patterns [0.3, 0.7]
        if arc_alignment <= 0.3:
            w_a = 0.0
        elif arc_alignment >= 0.7:
            w_a = 1.0
        else:
            w_a = (arc_alignment - 0.3) / 0.4

        # Tension window w_t: best when tension is low-moderate [0.0, 0.7]
        # Higher tension reduces quality
        if tension <= 0.3:
            w_t = 1.0
        elif tension >= 0.7:
            w_t = 0.0
        else:
            w_t = (0.7 - tension) / 0.4

        # Compute base stability factor from windows
        stability_core = 0.4 * w_r + 0.3 * w_a + 0.3 * w_t

        # ========================================================================
        # DIVERGENCE PENALTY (soft penalty for v1-v3 disagreement)
        # ========================================================================

        divergence = abs(v3 - base)  # both in [0, 1]

        # Soft penalty: no penalty below 0.05, max penalty above 0.30
        if divergence <= 0.05:
            divergence_penalty = 0.0
        elif divergence >= 0.30:
            divergence_penalty = 1.0
        else:
            divergence_penalty = (divergence - 0.05) / (0.30 - 0.05)

        # ========================================================================
        # FINAL QUALITY SCORE
        # ========================================================================

        # Apply divergence penalty to stability core
        raw_quality = stability_core * (1.0 - 0.6 * divergence_penalty)

        # Clamp to [0.0, 1.0]
        coherence_v3_quality = clamp(raw_quality, 0.0, 1.0)

        return coherence_v3_quality

    def _update_formula_fusion_stabilizer(
        self,
        state: CoherenceState,
        mapper_profile: Dict,
    ) -> None:
        """
        Update Phase 16 Formula Fusion Stabilizer (observation only).

        This method computes the fused coherence score by blending:
        - coherence_score_v1 (baseline)
        - coherence_score_v2 (formula-aware)
        - coherence_score_v3 (megafusion)
        - coherence_v3_quality (Phase 12)
        - enhanced_smi (from SMI history - Phase 13 placeholder)
        - vritti_momentum (Phase 14)
        - arc_tension_harmonizer (Phase 14)
        - guna_resonance_index (Phase 8)
        - kosha_resonance_index (Phase 8)
        - temporal inertia (sliding window)

        The fused metric is stored in state.coherence_fused and does NOT affect
        any existing pipeline behavior. It is purely for observation and future use.

        Args:
            state: CoherenceState to update in place
            mapper_profile: MapperProfile dict (for potential future use)
        """
        # Extract all required inputs from state
        v1 = state.coherence_score  # v1 canonical (always available)
        v2 = state.coherence_score_v2  # Phase 4
        v3 = state.coherence_score_v3  # Phase 10
        v3_quality = state.coherence_v3_quality  # Phase 12

        # Phase 13: Enhanced SMI - use most recent SMI from history as placeholder
        # (Phase 13 may define a more sophisticated enhanced_smi in the future)
        enhanced_smi = None
        if state.smi_history:
            enhanced_smi = state.smi_history[-1]

        # Phase 14: Vritti Momentum & Arc-Tension Harmonizer
        vritti_momentum = None
        if state.vritti_momentum_history:
            vritti_momentum = state.vritti_momentum_history[-1]

        arc_tension_harmonizer = None
        if state.arc_tension_harmonizer_history:
            arc_tension_harmonizer = state.arc_tension_harmonizer_history[-1]

        # Phase 8: Guna/Kosha resonance
        guna_resonance = state.guna_resonance_index
        kosha_resonance = state.kosha_resonance_index

        # Get last 5 v1 scores for temporal inertia baseline
        # Use coherence_score from smi_history (or a dedicated coherence history if available)
        # For now, use the last 5 entries from coherence_fused_history if available,
        # otherwise build from current v1 score
        history_last_5 = state.coherence_fused_history[-5:] if state.coherence_fused_history else []

        # If coherence_fused_history is empty (first turn), use v1 as baseline
        if not history_last_5:
            history_last_5 = [v1] if v1 is not None else []

        # Call formula fusion stabilizer
        snapshot = compute_coherence_fused(
            v1=v1,
            v2=v2,
            v3=v3,
            v3_quality=v3_quality,
            enhanced_smi=enhanced_smi,
            vritti_momentum=vritti_momentum,
            arc_tension_harmonizer=arc_tension_harmonizer,
            guna_resonance=guna_resonance,
            kosha_resonance=kosha_resonance,
            history_last_5=history_last_5,
        )

        # Store results in state
        state.coherence_fused = snapshot.coherence_fused
        state.fusion_stability_weight = snapshot.stability_weight
        state.fusion_inertia_factor = snapshot.inertia_factor
        state.fusion_quality_factor = snapshot.quality_factor

        # Append to history
        state.coherence_fused_history.append(snapshot.coherence_fused)
