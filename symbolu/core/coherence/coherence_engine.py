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
from symbolu.formulas.semantic_integrity import (
    compute_semantic_integrity,
    compute_cognitive_drift_v3,
)
from symbolu.formulas.temporal_entropy_differential import (
    compute_temporal_entropy_snapshot,
)
from symbolu.formulas.drift_fusion import (
    compute_drift_fusion_snapshot,
)


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
                semantic_integrity_history=prev_state.semantic_integrity_history.copy(),
                cognitive_drift_v3_history=prev_state.cognitive_drift_v3_history.copy(),
                enhanced_smi_history=prev_state.enhanced_smi_history.copy(),
                semantic_skeleton_history=prev_state.semantic_skeleton_history.copy(),
                intent_arc_history=prev_state.intent_arc_history.copy(),
                identity_signature_history=prev_state.identity_signature_history.copy(),
                temporal_entropy_diff_history=prev_state.temporal_entropy_diff_history.copy(),
                temporal_entropy_volatility_history=prev_state.temporal_entropy_volatility_history.copy(),
                drift_fusion_index_history=prev_state.drift_fusion_index_history.copy(),
                drift_risk_band_history=prev_state.drift_risk_band_history.copy(),
                drift_pattern_tags_history=prev_state.drift_pattern_tags_history.copy(),
                loop_alignment_history=prev_state.loop_alignment_history.copy(),
                loop_tension_history=prev_state.loop_tension_history.copy(),
                reversal_probability_history=prev_state.reversal_probability_history.copy(),
                stability_band_history=prev_state.stability_band_history.copy(),
                mirror_cycle_history=prev_state.mirror_cycle_history.copy(),
                cause_effect_inversion_history=prev_state.cause_effect_inversion_history.copy(),
                resonance_weighting_history=prev_state.resonance_weighting_history.copy(),
                resonance_weighting_entropy_history=prev_state.resonance_weighting_entropy_history.copy(),
                ucf_history=prev_state.ucf_history.copy(),
                symbolic_harmonization_history=prev_state.symbolic_harmonization_history.copy(),
                harmonization_entropy_history=prev_state.harmonization_entropy_history.copy(),
                identity_harmonics_history=prev_state.identity_harmonics_history.copy(),
                identity_entropy_history=prev_state.identity_entropy_history.copy(),
                identity_stability_history=prev_state.identity_stability_history.copy(),
                identity_flexibility_history=prev_state.identity_flexibility_history.copy(),
                predictive_drift_history=prev_state.predictive_drift_history.copy(),
                drift_magnitude_history=prev_state.drift_magnitude_history.copy(),
                drift_stability_history=prev_state.drift_stability_history.copy(),
                drift_likelihood_band_history=prev_state.drift_likelihood_band_history.copy(),
                identity_resonance_memory_history=prev_state.identity_resonance_memory_history.copy(),
                ims_history=prev_state.ims_history.copy(),
                iep_history=prev_state.iep_history.copy(),
                ida_history=prev_state.ida_history.copy(),
                irm_memory_band_history=prev_state.irm_memory_band_history.copy(),
                adaptive_continuity_history=prev_state.adaptive_continuity_history.copy(),
                ncc_history=prev_state.ncc_history.copy(),
                icc_history=prev_state.icc_history.copy(),
                css_history=prev_state.css_history.copy(),
                continuity_band_history=prev_state.continuity_band_history.copy(),
                forecast_history=prev_state.forecast_history.copy(),
                forecast_band_history=prev_state.forecast_band_history.copy(),
                forecast_strength_history=prev_state.forecast_strength_history.copy(),
                drift_influence_history=prev_state.drift_influence_history.copy(),
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

        # Phase 13: Enhanced SMI (observation only - not used in scoring)
        enhanced_smi_value = self._extract_enhanced_smi(temporal_summary)
        state.enhanced_smi_history.append(enhanced_smi_value)

        # Phase 17: Semantic skeleton, intent arc, identity signature (observation only)
        state.semantic_skeleton_history.append(semantic_signature.copy() if semantic_signature else {})
        state.intent_arc_history.append(self._extract_intent_arc(temporal_summary))
        state.identity_signature_history.append(self._extract_identity_signature(temporal_summary))

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

        # Update Phase 13 formula aggregates (observation only)
        self._update_enhanced_smi_aggregates(state)

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

        # Update Phase 17 semantic integrity and cognitive drift v3 (observation only)
        self._update_semantic_integrity(state, mapper_profile)
        self._update_cognitive_drift_v3(state)

        # Update Phase 18 temporal entropy differential (observation only)
        self._update_temporal_entropy_differential(state)

        # Update Phase 19 drift fusion (observation only - must come after Phase 17 & 18)
        self._update_drift_fusion(state, temporal_summary)

        # Update Phase 21 mirror-time loop (observation only)
        self._update_mirror_time_loop(state)

        # Update Phase 22 mirror-time cycles (observation only)
        self._update_mirror_time_cycles(state)

        # Update Phase 23 cause-effect inversion analytics (observation only)
        self._update_cause_effect_inversion(state)

        # Update Phase 24 resonance weighting function (observation only)
        self._update_resonance_weighting(state)

        # Update Phase 26 unified consciousness formula (observation only)
        self._update_unified_consciousness(state)

        # Update Phase 27 symbolic harmonization formula (observation only)
        self._update_symbolic_harmonization(state)

        # Update Phase 34 identity harmonics layer (observation only)
        self._update_identity_harmonics(state)

        # Update Phase 35 predictive persona drift model (observation only)
        self._update_predictive_persona_drift(state)

        # Update Phase 36 identity resonance memory (observation only)
        self._update_identity_resonance_memory(state)

        # Update Phase 37 adaptive continuity engine (observation only)
        self._update_adaptive_continuity(state)

        # Update Phase 38 temporal coherence forecasting model (observation only)
        self._update_temporal_coherence_forecast(state)

        # Update Phase 39 multi-horizon temporal forecasting engine (observation only)
        self._update_multi_horizon_forecast(state)

        # Update Phase 40 cross-horizon resonance alignment engine (observation only)
        self._update_cross_horizon_resonance(state)

        # Update Phase 41 coherence regime scenario mapper (observation only)
        self._update_coherence_regime(state)

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

    def _extract_intent_arc(self, temporal_summary: Optional[Dict]) -> Optional[str]:
        """Extract intent_arc from temporal summary (Phase 17)."""
        if temporal_summary and "intent_arc" in temporal_summary:
            return temporal_summary["intent_arc"]
        return None

    def _extract_identity_signature(self, temporal_summary: Optional[Dict]) -> Optional[str]:
        """Extract identity_signature from temporal summary (Phase 17)."""
        if temporal_summary and "identity_signature" in temporal_summary:
            return temporal_summary["identity_signature"]
        return None

    def _extract_enhanced_smi(self, temporal_summary: Optional[Dict]) -> Optional[float]:
        """Extract enhanced SMI from temporal summary (Phase 13)."""
        if temporal_summary and "formulas" in temporal_summary:
            return temporal_summary["formulas"].get("enhanced_smi")
        return None

    def _update_enhanced_smi_aggregates(self, state: CoherenceState) -> None:
        """Update enhanced SMI aggregate metrics (Phase 13)."""
        valid_values = [v for v in state.enhanced_smi_history if v is not None]
        if valid_values:
            state.current_enhanced_smi = valid_values[-1]
            state.avg_enhanced_smi = sum(valid_values) / len(valid_values)
            state.max_enhanced_smi = max(valid_values)
            state.min_enhanced_smi = min(valid_values)
        else:
            state.current_enhanced_smi = None
            state.avg_enhanced_smi = None
            state.max_enhanced_smi = None
            state.min_enhanced_smi = None

    def _update_drift_fusion(
        self,
        state: CoherenceState,
        temporal_summary: Optional[Dict]
    ) -> None:
        """Compute and update drift fusion snapshot (Phase 19)."""
        # Extract required inputs from state (populated by Phase 17 & 18)
        semantic_integrity = state.semantic_integrity_score
        cognitive_drift = state.cognitive_drift_v3
        temporal_entropy_diff = state.temporal_entropy_diff
        temporal_entropy_volatility = state.temporal_entropy_volatility
        coherence_fused = state.coherence_fused

        # Compute drift fusion snapshot
        snapshot = compute_drift_fusion_snapshot(
            semantic_integrity_score=semantic_integrity,
            cognitive_drift_v3=cognitive_drift,
            temporal_entropy_diff=temporal_entropy_diff,
            temporal_entropy_volatility=temporal_entropy_volatility,
            coherence_fused=coherence_fused,
        )

        if snapshot is not None:
            state.drift_fusion_index = snapshot.drift_fusion_index
            state.drift_risk_band = snapshot.drift_risk_band
            state.drift_pattern_tags = snapshot.drift_pattern_tags.copy()
            state.drift_fusion_index_history.append(snapshot.drift_fusion_index)
            state.drift_risk_band_history.append(snapshot.drift_risk_band)
            state.drift_pattern_tags_history.append(snapshot.drift_pattern_tags.copy())
        else:
            state.drift_fusion_index = None
            state.drift_risk_band = None
            state.drift_pattern_tags = []
            state.drift_fusion_index_history.append(None)
            state.drift_risk_band_history.append("")
            state.drift_pattern_tags_history.append([])

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

    def _update_semantic_integrity(
        self,
        state: CoherenceState,
        mapper_profile: Dict,
    ) -> None:
        """
        Update Phase 17 Semantic Integrity (observation only).

        This method computes the semantic integrity score by analyzing:
        - Structural consistency (current skeleton vs. previous skeletons)
        - Layer agreement (consistency between symbolic/practical/mirror)
        - Cross-turn consistency (similarity across recent turns)
        - Mapper alignment (mapper profile alignment with structure)
        - Intent-identity alignment (coherence of intent arc + identity signature)

        The semantic integrity metric is stored in state.semantic_integrity_score
        and does NOT affect any existing pipeline behavior. It is purely for
        observation and diagnostics.

        Args:
            state: CoherenceState to update in place
            mapper_profile: MapperProfile dict for alignment scoring
        """
        # Get current semantic skeleton (most recent)
        if not state.semantic_skeleton_history:
            # No skeleton yet - set to None and return
            state.semantic_integrity_score = None
            state.last_semantic_integrity_snapshot = None
            state.semantic_integrity_history.append(None)
            return

        current_skeleton = state.semantic_skeleton_history[-1]

        # Get previous skeletons (all but the last one)
        previous_skeletons = state.semantic_skeleton_history[:-1] if len(state.semantic_skeleton_history) > 1 else []

        # Get most recent intent arc and identity signature
        intent_arc = state.intent_arc_history[-1] if state.intent_arc_history else None
        identity_signature = state.identity_signature_history[-1] if state.identity_signature_history else None

        # Call semantic integrity formula
        snapshot = compute_semantic_integrity(
            current_skeleton=current_skeleton,
            previous_skeletons=previous_skeletons,
            mapper_profile=mapper_profile,
            intent_arc=intent_arc,
            identity_signature=identity_signature,
        )

        # Store results in state
        state.semantic_integrity_score = snapshot.semantic_integrity_score
        state.last_semantic_integrity_snapshot = snapshot

        # Append to history
        state.semantic_integrity_history.append(snapshot.semantic_integrity_score)

    def _update_cognitive_drift_v3(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 17 Cognitive Drift v3 (observation only).

        This method computes the cognitive drift v3 score by analyzing:
        - Structure drift (inconsistency in structural patterns)
        - Topic drift (variation in layer agreement and cross-turn consistency)
        - Mapper drift (changes in mapper activation patterns)
        - Intent-identity drift (changes in intent arc + identity signature)

        The cognitive drift v3 metric is stored in state.cognitive_drift_v3
        and does NOT affect any existing pipeline behavior. It is purely for
        observation and diagnostics.

        Args:
            state: CoherenceState to update in place
        """
        # Collect semantic integrity snapshots (last N)
        # We need at least 2 snapshots to compute drift
        if not state.semantic_integrity_history or len(state.semantic_integrity_history) < 2:
            # Not enough history - set to None and return
            state.cognitive_drift_v3 = None
            state.last_cognitive_drift_snapshot = None
            state.cognitive_drift_v3_history.append(None)
            return

        # Build list of integrity snapshots from last N turns
        # We'll use last 5-10 turns for drift computation
        integrity_snapshots_last_n = []

        # Get last N semantic integrity snapshots
        # We need to reconstruct snapshots from histories if last_semantic_integrity_snapshot is not stored
        # For simplicity, we'll use the current snapshot and assume we have access to component histories
        # In a full implementation, we would store all snapshots or reconstruct from component histories

        # For now, use a simplified approach: only use the last snapshot if available
        if state.last_semantic_integrity_snapshot is not None:
            integrity_snapshots_last_n = [state.last_semantic_integrity_snapshot]

        # Get mapper profile history (last N)
        mapper_history = state.mapper_profile_history[-10:] if state.mapper_profile_history else []

        # Get intent arc history (last N)
        intent_arc_history = state.intent_arc_history[-10:] if state.intent_arc_history else []

        # Get identity signature history (last N)
        identity_signature_history = state.identity_signature_history[-10:] if state.identity_signature_history else []

        # Call cognitive drift v3 formula
        snapshot = compute_cognitive_drift_v3(
            integrity_snapshots_last_n=integrity_snapshots_last_n,
            mapper_history=mapper_history,
            intent_arc_history=intent_arc_history,
            identity_signature_history=identity_signature_history,
        )

        # Store results in state
        state.cognitive_drift_v3 = snapshot.cognitive_drift_v3
        state.last_cognitive_drift_snapshot = snapshot

        # Append to history
        state.cognitive_drift_v3_history.append(snapshot.cognitive_drift_v3)

    def _update_temporal_entropy_differential(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 18 Temporal Entropy Differential (observation only).

        This method computes the temporal entropy snapshot by analyzing:
        - Normalized entropy history (from TTOR/MLCR routing plans)
        - Coherence fused history (from Phase 16)
        - Short-window and long-window entropy averages
        - Entropy differential (short - long)
        - Entropy volatility (variance over time)

        The temporal entropy metrics are stored in state.temporal_entropy_* fields
        and do NOT affect any existing pipeline behavior. They are purely for
        observation and diagnostics.

        Args:
            state: CoherenceState to update in place
        """
        # Build normalized_entropy_history from smi_history as proxy
        # (In production, we would extract normalized_entropy from routing_plan if available)
        # For now, use smi_history as a reasonable proxy for normalized entropy
        normalized_entropy_history = [
            s for s in state.smi_history if s is not None
        ]

        # If no entropy history, set to None and return
        if not normalized_entropy_history:
            state.temporal_entropy_snapshot = None
            state.temporal_entropy_diff = None
            state.temporal_entropy_volatility = None
            state.temporal_entropy_diff_history.append(None)
            state.temporal_entropy_volatility_history.append(None)
            return

        # Get coherence_fused_history for optional blending
        coherence_fused_history = state.coherence_fused_history

        # Compute temporal entropy snapshot
        snapshot = compute_temporal_entropy_snapshot(
            normalized_entropy_history=normalized_entropy_history,
            coherence_fused_history=coherence_fused_history,
            short_window=3,
            long_window=10,
        )

        # Store results in state
        if snapshot is not None:
            state.temporal_entropy_snapshot = snapshot
            state.temporal_entropy_diff = snapshot.normalized_entropy_diff
            state.temporal_entropy_volatility = snapshot.entropy_volatility

            # Append to histories
            state.temporal_entropy_diff_history.append(snapshot.normalized_entropy_diff)
            state.temporal_entropy_volatility_history.append(snapshot.entropy_volatility)
        else:
            # Snapshot computation failed
            state.temporal_entropy_snapshot = None
            state.temporal_entropy_diff = None
            state.temporal_entropy_volatility = None
            state.temporal_entropy_diff_history.append(None)
            state.temporal_entropy_volatility_history.append(None)

    def _update_mirror_time_loop(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 21 Mirror-Time Loop (observation only).

        This method computes the mirror-time loop snapshot by analyzing:
        - Forward vector (from delta_smi + tension_corridor)
        - Mirror vector (from coherence_fused + semantic_integrity)
        - Loop delta (forward - mirror)
        - Loop tension (|forward - mirror|)
        - Loop alignment (cosine similarity-like)
        - Reversal probability
        - Stability band classification

        The mirror-time loop metrics are stored in state.mirror_time_loop_* fields
        and do NOT affect any existing pipeline behavior. They are purely for
        observation and diagnostics.

        Args:
            state: CoherenceState to update in place
        """
        from symbolu.formulas.mirror_time_loop import compute_mirror_time_loop

        # Extract required histories
        delta_smi_history = state.delta_smi_history
        tension_corridor_history = state.tension_corridor_history
        coherence_fused_history = state.coherence_fused_history
        semantic_integrity_history = state.semantic_integrity_history

        # Use resonance_index as a proxy for resonance_index_history
        # Build history from arc_alignment_index (closest proxy available)
        resonance_index_history = []
        if state.resonance_index is not None:
            # For simplicity, use current resonance_index as the latest value
            # In a full implementation, we would maintain a dedicated history
            resonance_index_history = [state.resonance_index]

        # Check if we have any data
        if not delta_smi_history and not tension_corridor_history and not coherence_fused_history:
            # No data available - set to None and return
            state.mirror_time_loop_snapshot = None
            state.avg_loop_alignment = None
            state.avg_loop_tension = None
            state.avg_reversal_probability = None
            state.loop_alignment_history.append(None)
            state.loop_tension_history.append(None)
            state.reversal_probability_history.append(None)
            state.stability_band_history.append(None)
            return

        # Compute mirror-time loop snapshot
        snapshot = compute_mirror_time_loop(
            delta_smi_history=delta_smi_history,
            tension_corridor_history=tension_corridor_history,
            coherence_fused_history=coherence_fused_history,
            semantic_integrity_history=semantic_integrity_history,
            resonance_index_history=resonance_index_history,
            window=5,
        )

        # Store results in state
        if snapshot is not None:
            state.mirror_time_loop_snapshot = snapshot

            # Append to histories
            state.loop_alignment_history.append(snapshot.loop_alignment)
            state.loop_tension_history.append(snapshot.loop_tension)
            state.reversal_probability_history.append(snapshot.reversal_probability)
            state.stability_band_history.append(snapshot.stability_band)

            # Compute aggregates (averages)
            valid_alignments = [a for a in state.loop_alignment_history if a is not None]
            valid_tensions = [t for t in state.loop_tension_history if t is not None]
            valid_reversals = [r for r in state.reversal_probability_history if r is not None]

            if valid_alignments:
                state.avg_loop_alignment = sum(valid_alignments) / len(valid_alignments)
            else:
                state.avg_loop_alignment = None

            if valid_tensions:
                state.avg_loop_tension = sum(valid_tensions) / len(valid_tensions)
            else:
                state.avg_loop_tension = None

            if valid_reversals:
                state.avg_reversal_probability = sum(valid_reversals) / len(valid_reversals)
            else:
                state.avg_reversal_probability = None
        else:
            # Snapshot computation failed
            state.mirror_time_loop_snapshot = None
            state.avg_loop_alignment = None
            state.avg_loop_tension = None
            state.avg_reversal_probability = None
            state.loop_alignment_history.append(None)
            state.loop_tension_history.append(None)
            state.reversal_probability_history.append(None)
            state.stability_band_history.append(None)

    def _update_mirror_time_cycles(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 22 Mirror-Time Cycles (observation only).

        This method computes mirror-time cycles by analyzing the history of
        mirror-time loop snapshots. It segments the loop history into cycles,
        classifies each cycle, and computes aggregate statistics.

        The mirror-time cycle metrics are stored in state.mirror_cycle_* fields
        and do NOT affect any existing pipeline behavior. They are purely for
        observation and diagnostics.

        Args:
            state: CoherenceState to update in place
        """
        from symbolu.formulas.mirror_time_cycle import detect_mirror_time_cycles
        from symbolu.formulas.mirror_time_loop import MirrorTimeLoopSnapshot

        # Build loop_history from individual metric histories
        # We need to reconstruct MirrorTimeLoopSnapshot objects from the histories
        loop_alignment_hist = state.loop_alignment_history
        loop_tension_hist = state.loop_tension_history
        reversal_prob_hist = state.reversal_probability_history
        stability_band_hist = state.stability_band_history

        # Check if we have sufficient data
        if not loop_alignment_hist or len(loop_alignment_hist) < 2:
            # Not enough data to detect cycles
            state.dominant_cycle_type = None
            state.dominant_cycle_stability_band = None
            state.avg_cycle_alignment = None
            state.avg_cycle_tension = None
            state.avg_cycle_reversal_probability = None
            return

        # Reconstruct loop history as list of MirrorTimeLoopSnapshot objects
        # Note: We don't have all fields (forward_vector, mirror_vector, loop_delta),
        # but we have the key metrics needed for cycle detection
        loop_history = []
        min_len = min(
            len(loop_alignment_hist),
            len(loop_tension_hist),
            len(reversal_prob_hist),
            len(stability_band_hist),
        )

        for i in range(min_len):
            alignment = loop_alignment_hist[i]
            tension = loop_tension_hist[i]
            reversal = reversal_prob_hist[i]
            stability = stability_band_hist[i]

            # Skip None entries
            if alignment is None or tension is None or reversal is None or stability is None:
                continue

            # Create a minimal snapshot with the fields needed for cycle detection
            # We'll estimate forward_vector, mirror_vector, and loop_delta from available metrics
            # forward_vector ~ (1 - tension) (higher tension → lower forward)
            # mirror_vector ~ alignment (higher alignment → higher mirror)
            # loop_delta ~ forward - mirror
            forward_vector = max(0.0, min(1.0, 1.0 - tension))
            mirror_vector = alignment
            loop_delta = forward_vector - mirror_vector

            snapshot = MirrorTimeLoopSnapshot(
                forward_vector=forward_vector,
                mirror_vector=mirror_vector,
                loop_delta=loop_delta,
                loop_tension=tension,
                loop_alignment=alignment,
                reversal_probability=reversal,
                stability_band=stability,
            )
            loop_history.append(snapshot)

        # If still not enough data after filtering, return
        if len(loop_history) < 2:
            state.dominant_cycle_type = None
            state.dominant_cycle_stability_band = None
            state.avg_cycle_alignment = None
            state.avg_cycle_tension = None
            state.avg_cycle_reversal_probability = None
            return

        # Detect mirror-time cycles
        cycle_summary = detect_mirror_time_cycles(loop_history)

        # Store results in state
        if cycle_summary and cycle_summary.cycles:
            # Append new cycles to history
            for cycle in cycle_summary.cycles:
                state.mirror_cycle_history.append(cycle)

            # Update aggregate metrics
            state.dominant_cycle_type = cycle_summary.dominant_cycle_type
            state.dominant_cycle_stability_band = cycle_summary.dominant_stability_band

            # Compute averages from cycle summary
            if cycle_summary.cycles:
                alignments = [c.avg_loop_alignment for c in cycle_summary.cycles]
                tensions = [c.avg_loop_tension for c in cycle_summary.cycles]
                reversals = [c.avg_reversal_probability for c in cycle_summary.cycles]

                state.avg_cycle_alignment = sum(alignments) / len(alignments) if alignments else None
                state.avg_cycle_tension = sum(tensions) / len(tensions) if tensions else None
                state.avg_cycle_reversal_probability = (
                    sum(reversals) / len(reversals) if reversals else None
                )
            else:
                state.avg_cycle_alignment = None
                state.avg_cycle_tension = None
                state.avg_cycle_reversal_probability = None
        else:
            # No cycles detected
            state.dominant_cycle_type = None
            state.dominant_cycle_stability_band = None
            state.avg_cycle_alignment = None
            state.avg_cycle_tension = None
            state.avg_cycle_reversal_probability = None

    def _update_cause_effect_inversion(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 23 Cause-Effect Inversion Analytics (observation only).

        This method computes the cause-effect inversion snapshot by analyzing:
        - Forward alignment (coherence trend + semantic integrity)
        - Mirror alignment (mirror-time loop + cycle metrics)
        - Inversion score (alignment difference + drift + entropy)
        - Inversion band classification
        - Cause-chain stability

        The cause-effect inversion metrics are stored in state.cause_effect_inversion_*
        fields and do NOT affect any existing pipeline behavior. They are purely for
        observation and diagnostics.

        Args:
            state: CoherenceState to update in place
        """
        from symbolu.formulas.cause_effect_inversion import compute_cause_effect_inversion

        # Extract required inputs
        coherence_history = state.coherence_fused_history if state.coherence_fused_history else []

        # Fallback to v1 coherence if fused is not available
        if not coherence_history or all(c is None for c in coherence_history):
            # Use v1 coherence score history (reconstruct from state)
            # For now, we'll use whatever we have in coherence_fused_history
            # In a real scenario, we might maintain a separate coherence_score_history
            coherence_history = [c for c in state.coherence_fused_history if c is not None]

        # Mirror-time loop metrics
        mirror_loop_snapshot = state.mirror_time_loop_snapshot
        if mirror_loop_snapshot is not None:
            mirror_loop_stability = mirror_loop_snapshot.loop_alignment
            mirror_loop_tension = mirror_loop_snapshot.loop_tension
        else:
            mirror_loop_stability = None
            mirror_loop_tension = None

        # Cycle types from mirror cycle history
        cycle_types = []
        if state.mirror_cycle_history:
            # Get recent cycle types (last 5)
            recent_cycles = state.mirror_cycle_history[-5:]
            cycle_types = [c.cycle_type for c in recent_cycles if hasattr(c, 'cycle_type')]

        # Drift fusion index (from Phase 19)
        # Note: We need to extract this from state if available
        # For now, we'll use cognitive_drift_v3 as a proxy
        drift_fusion_index = state.cognitive_drift_v3

        # Temporal entropy diff (from Phase 18)
        temporal_entropy_diff = state.temporal_entropy_diff

        # Semantic integrity (from Phase 17)
        semantic_integrity = state.semantic_integrity_score

        # Check if we have minimum data
        if not coherence_history or len(coherence_history) < 2:
            # Not enough data - set to None and return
            state.cause_effect_inversion_history.append(None)
            state.current_inversion_score = None
            state.current_inversion_band = None
            state.avg_inversion_score = None
            state.cause_chain_stability_avg = None
            return

        # Compute cause-effect inversion snapshot
        snapshot = compute_cause_effect_inversion(
            coherence_history=coherence_history,
            mirror_loop_stability=mirror_loop_stability,
            mirror_loop_tension=mirror_loop_tension,
            cycle_types=cycle_types,
            drift_fusion_index=drift_fusion_index,
            temporal_entropy_diff=temporal_entropy_diff,
            semantic_integrity=semantic_integrity,
        )

        # Store results in state
        if snapshot is not None:
            # Append to history
            state.cause_effect_inversion_history.append(snapshot)

            # Update current metrics
            state.current_inversion_score = snapshot.inversion_score
            state.current_inversion_band = snapshot.inversion_band

            # Compute aggregates (averages)
            valid_snapshots = [s for s in state.cause_effect_inversion_history if s is not None]

            if valid_snapshots:
                inversion_scores = [s.inversion_score for s in valid_snapshots]
                stability_scores = [s.cause_chain_stability for s in valid_snapshots]

                state.avg_inversion_score = sum(inversion_scores) / len(inversion_scores)
                state.cause_chain_stability_avg = sum(stability_scores) / len(stability_scores)
            else:
                state.avg_inversion_score = None
                state.cause_chain_stability_avg = None
        else:
            # Snapshot computation failed
            state.cause_effect_inversion_history.append(None)
            state.current_inversion_score = None
            state.current_inversion_band = None
            state.avg_inversion_score = None
            state.cause_chain_stability_avg = None

    def _update_resonance_weighting(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 24 Resonance Weighting Function (observation only).

        This method computes adaptive weights for all major Symbol-U metrics based on
        their "resonance quality," without changing any existing formulas or behavior.

        The resonance weights say: "Given all these signals (coherence, formulas,
        resonance, mirror-time, drift…), which ones are currently most trustworthy?"

        These weights are:
          • Exposed to Unified API and Unified Dashboard
          • Optionally surfaced as DILchat diagnostics
          • NOT used to change any v1/v2/v3/coherence_fused scores

        Args:
            state: CoherenceState to update in place
        """
        from symbolu.formulas.resonance_weighting import compute_resonance_weighting

        # Gather all available metrics from state
        # Coherence variants
        coherence_v1 = state.coherence_score if state.coherence_score > 0.0 else None
        coherence_v2 = state.coherence_score_v2
        coherence_v3 = state.coherence_score_v3
        coherence_fused = state.coherence_fused
        coherence_v3_quality = state.coherence_v3_quality

        # Enhanced SMI (Phase 13)
        enhanced_smi = state.smi_history[-1] if state.smi_history else None

        # Phase 14 formulas
        vritti_momentum = state.vritti_momentum_history[-1] if state.vritti_momentum_history else None
        arc_tension_harmonizer = state.arc_tension_harmonizer_history[-1] if state.arc_tension_harmonizer_history else None

        # Phase 3 derived metrics
        resonance_index = state.resonance_index
        tension_index = state.tension_index
        arc_alignment_index = state.arc_alignment_index

        # Phase 8 Guna/Kosha resonance
        guna_resonance_index = state.guna_resonance_index
        kosha_resonance_index = state.kosha_resonance_index

        # Phase 17 semantic integrity & drift
        semantic_integrity_score = state.semantic_integrity_score
        cognitive_drift_v3 = state.cognitive_drift_v3

        # Phase 18 temporal entropy
        temporal_entropy_volatility = state.temporal_entropy_volatility

        # Phase 19 drift fusion index (if available in state)
        # Note: drift_fusion_index might not be directly stored in state
        # For now, we'll use cognitive_drift_v3 as a proxy
        drift_fusion_index = cognitive_drift_v3

        # Compute resonance weighting snapshot
        snapshot = compute_resonance_weighting(
            coherence_v1=coherence_v1,
            coherence_v2=coherence_v2,
            coherence_v3=coherence_v3,
            coherence_fused=coherence_fused,
            coherence_v3_quality=coherence_v3_quality,
            enhanced_smi=enhanced_smi,
            vritti_momentum=vritti_momentum,
            arc_tension_harmonizer=arc_tension_harmonizer,
            resonance_index=resonance_index,
            tension_index=tension_index,
            arc_alignment_index=arc_alignment_index,
            guna_resonance_index=guna_resonance_index,
            kosha_resonance_index=kosha_resonance_index,
            drift_fusion_index=drift_fusion_index,
            semantic_integrity_score=semantic_integrity_score,
            cognitive_drift_v3=cognitive_drift_v3,
            temporal_entropy_volatility=temporal_entropy_volatility,
        )

        # Store results in state
        if snapshot is not None:
            # Append to history
            state.resonance_weighting_history.append(snapshot)
            state.resonance_weighting_entropy_history.append(snapshot.entropy_of_weights)

            # Update current metrics
            state.current_resonance_weights = snapshot.weights
            state.current_normalized_resonance_weights = snapshot.normalized_weights
            state.current_resonance_entropy = snapshot.entropy_of_weights

            # Update dominant metrics (top 3 keys)
            state.dominant_resonance_metrics = list(snapshot.dominant_metrics.keys())
        else:
            # Snapshot computation failed (insufficient data)
            state.resonance_weighting_history.append(None)
            state.resonance_weighting_entropy_history.append(None)
            state.current_resonance_weights = None
            state.current_normalized_resonance_weights = None
            state.current_resonance_entropy = None
            state.dominant_resonance_metrics = []

    def _update_unified_consciousness(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 26 Unified Consciousness Formula (observation only).

        This method computes the unified consciousness snapshot by integrating ALL
        Symbol-U v3.0 formula signals into three indices:
          - COI (Consciousness Order Index): Structural coherence & organization
          - CSI (Consciousness Stability Index): Temporal stability & resilience
          - CIP (Consciousness Integration Potential): Cross-layer integration readiness

        The UCF is purely observational and does NOT affect any existing pipeline
        behavior. It is designed for dashboard visualization and future v4.0 integration.

        Args:
            state: CoherenceState to update in place
        """
        from symbolu.formulas.unified_consciousness import compute_unified_consciousness

        # Gather all inputs from state

        # Coherence variants (Phase 1-4, 10, 16)
        coherence_v1 = state.coherence_score if state.coherence_score > 0.0 else None
        coherence_v2 = state.coherence_score_v2
        coherence_v3 = state.coherence_score_v3
        coherence_fused = state.coherence_fused

        # Enhanced SMI (Phase 13 placeholder - use most recent SMI from history)
        enhanced_smi = state.smi_history[-1] if state.smi_history else None

        # Semantic integrity & cognitive drift (Phase 17)
        semantic_integrity_score = state.semantic_integrity_score
        cognitive_drift_v3 = state.cognitive_drift_v3

        # Drift fusion index (Phase 19 - if available, use cognitive_drift_v3 as proxy)
        drift_fusion_index = cognitive_drift_v3

        # Vritti momentum (Phase 14)
        vritti_momentum = state.vritti_momentum_history[-1] if state.vritti_momentum_history else None

        # Arc-tension harmonizer (Phase 14)
        arc_tension_harmonizer = state.arc_tension_harmonizer_history[-1] if state.arc_tension_harmonizer_history else None

        # Mirror-time loop metrics (Phase 21)
        mirror_loop_alignment = state.avg_loop_alignment
        mirror_loop_tension = state.avg_loop_tension
        mirror_reversal_probability = state.avg_reversal_probability

        # Mirror-time cycle metrics (Phase 22)
        cycle_alignment = state.avg_cycle_alignment
        cycle_tension = state.avg_cycle_tension
        cycle_reversal_probability = state.avg_cycle_reversal_probability

        # Temporal entropy differential (Phase 18)
        temporal_entropy_diff = state.temporal_entropy_diff
        temporal_entropy_volatility = state.temporal_entropy_volatility

        # Guna/Kosha resonance (Phase 8)
        guna_resonance_index = state.guna_resonance_index
        kosha_resonance_index = state.kosha_resonance_index

        # Resonance weighting (Phase 24)
        resonance_weighting_entropy = state.current_resonance_entropy
        dominant_resonance_metrics = state.dominant_resonance_metrics if state.dominant_resonance_metrics else None

        # Quality metrics (Phase 12, 16)
        coherence_v3_quality = state.coherence_v3_quality
        fusion_stability_weight = state.fusion_stability_weight
        fusion_inertia_factor = state.fusion_inertia_factor

        # Compute unified consciousness snapshot
        snapshot = compute_unified_consciousness(
            coherence_v1=coherence_v1,
            coherence_v2=coherence_v2,
            coherence_v3=coherence_v3,
            coherence_fused=coherence_fused,
            enhanced_smi=enhanced_smi,
            semantic_integrity_score=semantic_integrity_score,
            cognitive_drift_v3=cognitive_drift_v3,
            drift_fusion_index=drift_fusion_index,
            vritti_momentum=vritti_momentum,
            arc_tension_harmonizer=arc_tension_harmonizer,
            mirror_loop_alignment=mirror_loop_alignment,
            mirror_loop_tension=mirror_loop_tension,
            mirror_reversal_probability=mirror_reversal_probability,
            cycle_alignment=cycle_alignment,
            cycle_tension=cycle_tension,
            cycle_reversal_probability=cycle_reversal_probability,
            temporal_entropy_diff=temporal_entropy_diff,
            temporal_entropy_volatility=temporal_entropy_volatility,
            guna_resonance_index=guna_resonance_index,
            kosha_resonance_index=kosha_resonance_index,
            resonance_weighting_entropy=resonance_weighting_entropy,
            dominant_resonance_metrics=dominant_resonance_metrics,
            coherence_v3_quality=coherence_v3_quality,
            fusion_stability_weight=fusion_stability_weight,
            fusion_inertia_factor=fusion_inertia_factor,
        )

        # Store results in state
        if snapshot is not None:
            # Append to history
            state.ucf_history.append(snapshot)

            # Update current metrics
            state.unified_consciousness_snapshot = snapshot
            state.current_coi = snapshot.consciousness_order_index
            state.current_csi = snapshot.consciousness_stability_index
            state.current_cip = snapshot.consciousness_integration_potential
            state.ucf_entropy = snapshot.entropy_of_weights
            state.ucf_notes = snapshot.diagnostic_notes
        else:
            # Snapshot computation failed (insufficient data)
            state.ucf_history.append(None)
            state.unified_consciousness_snapshot = None
            state.current_coi = None
            state.current_csi = None
            state.current_cip = None
            state.ucf_entropy = None
            state.ucf_notes = []

    def _update_symbolic_harmonization(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 27 Symbolic Harmonization Formula (observation only).

        This method computes the symbolic harmonization snapshot by measuring
        alignment across symbolic, practical, and mirror layers, harmonized with
        Guna/Kosha resonance and semantic integrity.

        The SHF is purely observational and does NOT affect any existing pipeline
        behavior. It is designed for dashboard visualization and analytics.

        Args:
            state: CoherenceState to update in place
        """
        from symbolu.formulas.symbolic_harmonization import compute_symbolic_harmonization

        # ====================================================================
        # STEP 1: CONSTRUCT SYMBOLIC LAYER VECTOR
        # ====================================================================
        # Symbolic layer represents meaning, archetypes, and authenticity
        # Components: SMI, bhava states, resonance indices

        symbolic_vector = []

        # SMI (authenticity/tension) - take last 5 values
        if state.smi_history:
            symbolic_vector.extend(state.smi_history[-5:])

        # Bhava states (normalized) - take last 5 values
        if state.bhava_id_history:
            # Normalize bhava IDs to [0, 1] (assuming max bhava ID is 8)
            normalized_bhava = [bid / 8.0 for bid in state.bhava_id_history[-5:]]
            symbolic_vector.extend(normalized_bhava)

        # Guna/Kosha resonance (if available)
        if state.guna_resonance_index is not None:
            symbolic_vector.append(state.guna_resonance_index)
        if state.kosha_resonance_index is not None:
            symbolic_vector.append(state.kosha_resonance_index)

        # Vritti momentum (Phase 14)
        if state.vritti_momentum_history:
            recent_vm = [vm for vm in state.vritti_momentum_history[-3:] if vm is not None]
            symbolic_vector.extend(recent_vm)

        # Use None if insufficient data
        symbolic_layer_vector = symbolic_vector if len(symbolic_vector) >= 3 else None

        # ====================================================================
        # STEP 2: CONSTRUCT PRACTICAL LAYER VECTOR
        # ====================================================================
        # Practical layer represents factual grounding and structural coherence
        # Components: coherence scores, semantic stability, mapper volatility

        practical_vector = []

        # Coherence scores
        if state.coherence_score > 0.0:
            practical_vector.append(state.coherence_score)
        if state.coherence_score_v2 is not None:
            practical_vector.append(state.coherence_score_v2)
        if state.coherence_fused is not None:
            practical_vector.append(state.coherence_fused)

        # Semantic stability
        if state.semantic_stability_score > 0.0:
            practical_vector.append(state.semantic_stability_score)

        # Semantic integrity (Phase 17)
        if state.semantic_integrity_score is not None:
            practical_vector.append(state.semantic_integrity_score)

        # Mapper volatility (inverted - lower volatility = better practical grounding)
        if state.mapper_volatility_score > 0.0:
            practical_vector.append(1.0 - state.mapper_volatility_score)

        # Temporal arc score
        if state.temporal_arc_score > 0.0:
            practical_vector.append(state.temporal_arc_score)

        # Use None if insufficient data
        practical_layer_vector = practical_vector if len(practical_vector) >= 3 else None

        # ====================================================================
        # STEP 3: CONSTRUCT MIRROR LAYER VECTOR
        # ====================================================================
        # Mirror layer represents contradictions, tensions, and reflective coherence
        # Components: drift, tension, mirror-time metrics

        mirror_vector = []

        # Cognitive drift (Phase 17) - inverted for alignment (low drift = good)
        if state.cognitive_drift_v3 is not None:
            mirror_vector.append(1.0 - state.cognitive_drift_v3)

        # Tension history - take recent values
        if state.tension_history:
            # Tension is a challenge metric, normalize and take recent values
            recent_tension = state.tension_history[-3:]
            mirror_vector.extend(recent_tension)

        # Mirror-time loop metrics (Phase 21)
        if state.avg_loop_alignment is not None:
            mirror_vector.append(state.avg_loop_alignment)
        if state.avg_loop_tension is not None:
            # Tension is risk metric - invert it
            mirror_vector.append(1.0 - state.avg_loop_tension)

        # Mirror-time cycle metrics (Phase 22)
        if state.avg_cycle_alignment is not None:
            mirror_vector.append(state.avg_cycle_alignment)

        # Temporal entropy (Phase 18)
        if state.temporal_entropy_diff is not None:
            # Low diff = stable, map to alignment quality
            if state.temporal_entropy_diff <= 0.5:
                quality = 0.5 + state.temporal_entropy_diff
            else:
                quality = 1.5 - state.temporal_entropy_diff
            mirror_vector.append(quality)

        # Use None if insufficient data
        mirror_layer_vector = mirror_vector if len(mirror_vector) >= 3 else None

        # ====================================================================
        # STEP 4: GATHER RESONANCE & SEMANTIC METRICS
        # ====================================================================

        guna_resonance = state.guna_resonance_index
        kosha_resonance = state.kosha_resonance_index
        semantic_integrity = state.semantic_integrity_score

        # ====================================================================
        # STEP 5: COMPUTE SYMBOLIC HARMONIZATION
        # ====================================================================

        snapshot = compute_symbolic_harmonization(
            symbolic_layer_vector=symbolic_layer_vector,
            practical_layer_vector=practical_layer_vector,
            mirror_layer_vector=mirror_layer_vector,
            guna_resonance=guna_resonance,
            kosha_resonance=kosha_resonance,
            semantic_integrity=semantic_integrity,
        )

        # ====================================================================
        # STEP 6: STORE RESULTS IN STATE
        # ====================================================================

        if snapshot is not None:
            # Append to histories
            state.symbolic_harmonization_history.append(snapshot)
            state.harmonization_entropy_history.append(snapshot.harmonization_entropy)

            # Update current metrics
            state.symbolic_harmonization_snapshot = snapshot
            state.current_symbolic_harmonization_index = snapshot.symbolic_harmonization_index
        else:
            # Snapshot computation failed (insufficient data)
            state.symbolic_harmonization_history.append(None)
            state.harmonization_entropy_history.append(None)
            state.symbolic_harmonization_snapshot = None
            state.current_symbolic_harmonization_index = None

    def _update_identity_harmonics(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 34 Identity Harmonics Layer (observation only).

        This method computes the identity harmonics snapshot by measuring identity
        resonance patterns across semantic, emotional, symbolic, and temporal dimensions.

        The IHL produces three harmonics:
          1. Core Identity Harmonic (CIH): Stability of identity signals
          2. Adaptive Identity Harmonic (AIH): Ability to shift identity coherently
          3. Relational Identity Harmonic (RIH): Persona-symbolic resonance

        The IHL is purely observational and does NOT affect any existing pipeline
        behavior. It is designed for persona tone micro-adjustments (±0.02 max) and analytics.

        Args:
            state: CoherenceState to update in place
        """
        from symbolu.formulas.identity_harmonics import compute_identity_harmonics

        # ====================================================================
        # STEP 1: GATHER SEMANTIC + SYMBOLIC SIGNALS (Core Identity)
        # ====================================================================

        semantic_integrity = state.semantic_integrity_score
        symbolic_harmonization_index = state.current_symbolic_harmonization_index
        consciousness_order_index = state.current_coi  # From UCF (Phase 26)

        # ====================================================================
        # STEP 2: GATHER TEMPORAL + ADAPTIVE SIGNALS (Adaptive Identity)
        # ====================================================================

        cognitive_drift_v3 = state.cognitive_drift_v3
        temporal_entropy_volatility = state.temporal_entropy_volatility

        # Loop alignment (from mirror-time loop, Phase 21)
        loop_alignment = state.avg_loop_alignment

        # ====================================================================
        # STEP 3: GATHER PERSONA + RELATIONAL SIGNALS (Relational Identity)
        # ====================================================================

        persona_drift_score = state.persona_drift_score
        guna_resonance_index = state.guna_resonance_index
        kosha_resonance_index = state.kosha_resonance_index

        # ====================================================================
        # STEP 4: GATHER HISTORICAL CONTEXT (For Stability Computation)
        # ====================================================================

        # Extract recent values for variance computation
        semantic_integrity_history = None
        if state.semantic_integrity_history:
            semantic_integrity_history = [
                si for si in state.semantic_integrity_history if si is not None
            ]

        symbolic_harmonization_history = None
        if state.symbolic_harmonization_history:
            # Extract symbolic_harmonization_index from snapshots
            symbolic_harmonization_history = [
                snapshot.symbolic_harmonization_index
                for snapshot in state.symbolic_harmonization_history
                if snapshot is not None
            ]

        cognitive_drift_history = None
        if state.cognitive_drift_v3_history:
            cognitive_drift_history = [
                cd for cd in state.cognitive_drift_v3_history if cd is not None
            ]

        # ====================================================================
        # STEP 5: COMPUTE IDENTITY HARMONICS
        # ====================================================================

        snapshot = compute_identity_harmonics(
            semantic_integrity=semantic_integrity,
            symbolic_harmonization_index=symbolic_harmonization_index,
            consciousness_order_index=consciousness_order_index,
            cognitive_drift_v3=cognitive_drift_v3,
            temporal_entropy_volatility=temporal_entropy_volatility,
            loop_alignment=loop_alignment,
            persona_drift_score=persona_drift_score,
            guna_resonance_index=guna_resonance_index,
            kosha_resonance_index=kosha_resonance_index,
            semantic_integrity_history=semantic_integrity_history,
            symbolic_harmonization_history=symbolic_harmonization_history,
            cognitive_drift_history=cognitive_drift_history,
        )

        # ====================================================================
        # STEP 6: STORE RESULTS IN STATE
        # ====================================================================

        if snapshot is not None:
            # Append to histories
            state.identity_harmonics_history.append(snapshot)
            state.identity_entropy_history.append(snapshot.identity_entropy)
            state.identity_stability_history.append(snapshot.identity_stability_score)
            state.identity_flexibility_history.append(snapshot.identity_flexibility_score)

            # Update current metrics
            state.identity_harmonics_snapshot = snapshot
            state.current_cih = snapshot.core_identity_harmonic
            state.current_aih = snapshot.adaptive_identity_harmonic
            state.current_rih = snapshot.relational_identity_harmonic
            state.current_identity_harmonics_index = snapshot.identity_harmonics_index
        else:
            # Snapshot computation failed (insufficient data)
            state.identity_harmonics_history.append(None)
            state.identity_entropy_history.append(None)
            state.identity_stability_history.append(None)
            state.identity_flexibility_history.append(None)
            state.identity_harmonics_snapshot = None
            state.current_cih = None
            state.current_aih = None
            state.current_rih = None
            state.current_identity_harmonics_index = None

    def _update_predictive_persona_drift(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 35 Predictive Persona Drift Model (observation only).

        This method computes the predictive persona drift snapshot by forecasting
        future drift direction and magnitude using the full Symbol-U v3.0 signal stack.

        The PPDM produces:
          1. Drift Magnitude Prediction (DMP): Estimated future drift intensity
          2. Drift Direction Scores: Direction components (structure, warmth, grounding)
          3. Drift Stability Score (DSS): Confidence in drift trajectory
          4. Drift Likelihood Band: LOW / MEDIUM / HIGH classification
          5. Diagnostic Tags: DRIFT_RISK_RISING, HARMONICS_INFLUENCE_HIGH, etc.

        The PPDM is purely observational and does NOT affect any existing pipeline
        behavior. It is designed for tone-only micro-adjustments (±0.02 max) and analytics.

        This update runs AFTER Phase 34 Identity Harmonics to leverage identity signals.

        Args:
            state: CoherenceState to update in place
        """
        from symbolu.formulas.predictive_persona_drift import compute_predictive_persona_drift

        # ====================================================================
        # STEP 1: GATHER IDENTITY HARMONICS (Phase 34)
        # ====================================================================

        core_identity_harmonic = state.current_cih
        adaptive_identity_harmonic = state.current_aih
        relational_identity_harmonic = state.current_rih
        identity_stability_score = None
        identity_flexibility_score = None
        identity_entropy = None

        # Extract from latest snapshot if available
        if state.identity_harmonics_snapshot is not None:
            identity_stability_score = state.identity_harmonics_snapshot.identity_stability_score
            identity_flexibility_score = state.identity_harmonics_snapshot.identity_flexibility_score
            identity_entropy = state.identity_harmonics_snapshot.identity_entropy

        # ====================================================================
        # STEP 2: GATHER SEMANTIC + COGNITIVE SIGNALS (Phase 17)
        # ====================================================================

        semantic_integrity = state.semantic_integrity_score
        cognitive_drift_v3 = state.cognitive_drift_v3

        # ====================================================================
        # STEP 3: GATHER TEMPORAL ENTROPY (Phase 18)
        # ====================================================================

        temporal_entropy_volatility = state.temporal_entropy_volatility

        # ====================================================================
        # STEP 4: GATHER DRIFT FUSION (Phase 19) - if available
        # ====================================================================

        # Drift Fusion Index (DFI) is not directly stored in CoherenceState
        # We can compute an approximation or leave as None for graceful degradation
        drift_fusion_index = None

        # ====================================================================
        # STEP 5: GATHER RESONANCE WEIGHTING ENTROPY (Phase 24)
        # ====================================================================

        resonance_weighting_entropy = state.current_resonance_entropy

        # ====================================================================
        # STEP 6: GATHER SYMBOLIC HARMONIZATION (Phase 27)
        # ====================================================================

        symbolic_harmonization_index = state.current_symbolic_harmonization_index

        # ====================================================================
        # STEP 7: GATHER COHERENCE + CONSCIOUSNESS SIGNALS
        # ====================================================================

        coherence_fused = state.coherence_fused
        unified_consciousness_order = state.current_coi  # Consciousness Order Index

        # ====================================================================
        # STEP 8: GATHER PERSONA + RELATIONAL SIGNALS
        # ====================================================================

        persona_drift_score = state.persona_drift_score
        guna_resonance_index = state.guna_resonance_index
        kosha_resonance_index = state.kosha_resonance_index

        # ====================================================================
        # STEP 9: GATHER HISTORICAL CONTEXT (For Trend Analysis)
        # ====================================================================

        # Extract recent values for trend/variance computation
        cognitive_drift_history = None
        if state.cognitive_drift_v3_history:
            cognitive_drift_history = [
                cd for cd in state.cognitive_drift_v3_history if cd is not None
            ]

        persona_drift_history = None
        if state.persona_drift_score and state.turn_index >= 1:
            # Reconstruct persona drift history from turn indices
            # For now, we'll use a simple approach: collect recent persona_drift_score values
            # This assumes persona_drift_score is updated each turn
            # In practice, we might need a dedicated persona_drift_history field
            # For Phase 35 v1.0, we'll use cognitive_drift as a proxy if persona history unavailable
            persona_drift_history = cognitive_drift_history  # Proxy

        coherence_fused_history = None
        if state.coherence_fused_history:
            coherence_fused_history = [
                cf for cf in state.coherence_fused_history if cf is not None
            ]

        identity_stability_history = None
        if state.identity_stability_history:
            identity_stability_history = [
                ish for ish in state.identity_stability_history if ish is not None
            ]

        # ====================================================================
        # STEP 10: COMPUTE PREDICTIVE PERSONA DRIFT
        # ====================================================================

        snapshot = compute_predictive_persona_drift(
            # Identity Harmonics (Phase 34)
            core_identity_harmonic=core_identity_harmonic,
            adaptive_identity_harmonic=adaptive_identity_harmonic,
            relational_identity_harmonic=relational_identity_harmonic,
            identity_stability_score=identity_stability_score,
            identity_flexibility_score=identity_flexibility_score,
            identity_entropy=identity_entropy,
            # Semantic + Cognitive (Phase 17)
            semantic_integrity=semantic_integrity,
            cognitive_drift_v3=cognitive_drift_v3,
            # Temporal Entropy (Phase 18)
            temporal_entropy_volatility=temporal_entropy_volatility,
            # Drift Fusion (Phase 19)
            drift_fusion_index=drift_fusion_index,
            # Resonance Weighting (Phase 24)
            resonance_weighting_entropy=resonance_weighting_entropy,
            # Symbolic Harmonization (Phase 27)
            symbolic_harmonization_index=symbolic_harmonization_index,
            # Coherence + Consciousness
            coherence_fused=coherence_fused,
            unified_consciousness_order=unified_consciousness_order,
            # Persona + Relational
            persona_drift_score=persona_drift_score,
            guna_resonance_index=guna_resonance_index,
            kosha_resonance_index=kosha_resonance_index,
            # Historical context
            cognitive_drift_history=cognitive_drift_history,
            persona_drift_history=persona_drift_history,
            coherence_fused_history=coherence_fused_history,
            identity_stability_history=identity_stability_history,
        )

        # ====================================================================
        # STEP 11: STORE RESULTS IN STATE
        # ====================================================================

        if snapshot is not None:
            # Append to histories
            state.predictive_drift_history.append(snapshot)
            state.drift_magnitude_history.append(snapshot.drift_magnitude_prediction)
            state.drift_stability_history.append(snapshot.drift_stability_score)
            state.drift_likelihood_band_history.append(snapshot.drift_likelihood_band)

            # Update current metrics
            state.predictive_drift_snapshot = snapshot
            state.current_drift_magnitude_prediction = snapshot.drift_magnitude_prediction
            state.current_drift_stability_score = snapshot.drift_stability_score
            state.current_drift_likelihood_band = snapshot.drift_likelihood_band
            state.current_drift_direction_scores = snapshot.drift_direction_scores
        else:
            # Snapshot computation failed (insufficient data)
            state.predictive_drift_history.append(None)
            state.drift_magnitude_history.append(None)
            state.drift_stability_history.append(None)
            state.drift_likelihood_band_history.append(None)
            state.predictive_drift_snapshot = None
            state.current_drift_magnitude_prediction = None
            state.current_drift_stability_score = None
            state.current_drift_likelihood_band = None
            state.current_drift_direction_scores = None

    def _update_identity_resonance_memory(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 36 Identity Resonance Memory (observation only).

        This method computes the identity resonance memory snapshot by modeling how
        resonant identity patterns accumulate, persist, decay, and resurface across turns.

        The IRM produces:
          1. Identity Memory Strength (IMS): How strongly identity signals persist
          2. Identity Echo Persistence (IEP): Whether identity themes keep resurfacing
          3. Identity Drift Anchoring (IDA): Identity stabilization vs predictive drift
          4. Memory Band: LOW / MEDIUM / HIGH classification
          5. Diagnostic Tags: IDENTITY_ANCHORING_STRONG, IDENTITY_ECHO_PERSISTENT, etc.

        The IRM is purely observational and does NOT affect any existing pipeline
        behavior. It is designed for tone-only micro-adjustments (±0.02 max) and analytics.

        This update runs AFTER Phase 35 Predictive Drift to leverage drift predictions.

        Args:
            state: CoherenceState to update in place
        """
        from symbolu.formulas.identity_resonance_memory import compute_identity_resonance_memory

        # ====================================================================
        # STEP 1: GATHER IDENTITY HARMONICS (Phase 34)
        # ====================================================================

        core_identity_harmonic = state.current_cih
        adaptive_identity_harmonic = state.current_aih
        relational_identity_harmonic = state.current_rih
        identity_stability_score = None
        identity_flexibility_score = None

        # Extract from latest snapshot if available
        if state.identity_harmonics_snapshot is not None:
            identity_stability_score = state.identity_harmonics_snapshot.identity_stability_score
            identity_flexibility_score = state.identity_harmonics_snapshot.identity_flexibility_score

        # ====================================================================
        # STEP 2: GATHER PREDICTIVE DRIFT (Phase 35)
        # ====================================================================

        drift_magnitude_prediction = state.current_drift_magnitude_prediction
        drift_stability_score = state.current_drift_stability_score
        drift_likelihood_band = state.current_drift_likelihood_band

        # ====================================================================
        # STEP 3: GATHER SEMANTIC INTEGRITY (Phase 17)
        # ====================================================================

        semantic_integrity = state.semantic_integrity_score

        # ====================================================================
        # STEP 4: GATHER SYMBOLIC HARMONIZATION (Phase 27)
        # ====================================================================

        symbolic_harmonization_index = state.current_symbolic_harmonization_index

        # ====================================================================
        # STEP 5: GATHER UNIFIED CONSCIOUSNESS (Phase 26)
        # ====================================================================

        consciousness_order_index = state.current_coi

        # ====================================================================
        # STEP 6: GATHER TEMPORAL ENTROPY (Phase 18)
        # ====================================================================

        temporal_entropy_volatility = state.temporal_entropy_volatility
        temporal_entropy_diff = state.temporal_entropy_diff

        # ====================================================================
        # STEP 7: GATHER RESONANCE WEIGHTING (Phase 24)
        # ====================================================================

        resonance_weighting_entropy = state.current_resonance_entropy

        # ====================================================================
        # STEP 8: GATHER MIRROR-TIME CYCLE (Phase 22) - optional
        # ====================================================================

        cycle_alignment = state.avg_cycle_alignment
        cycle_stability_band = state.dominant_cycle_stability_band

        # ====================================================================
        # STEP 9: GATHER HISTORICAL CONTEXT
        # ====================================================================

        # Identity harmonics histories
        cih_history = None
        aih_history = None
        rih_history = None

        if state.identity_harmonics_history:
            cih_history = [
                snap.core_identity_harmonic
                for snap in state.identity_harmonics_history
                if snap is not None
            ]
            aih_history = [
                snap.adaptive_identity_harmonic
                for snap in state.identity_harmonics_history
                if snap is not None
            ]
            rih_history = [
                snap.relational_identity_harmonic
                for snap in state.identity_harmonics_history
                if snap is not None
            ]

        # Identity stability history
        identity_stability_history = None
        if state.identity_stability_history:
            identity_stability_history = [
                ish for ish in state.identity_stability_history if ish is not None
            ]

        # Semantic integrity history
        semantic_integrity_history = None
        if state.semantic_integrity_history:
            semantic_integrity_history = [
                sih for sih in state.semantic_integrity_history if sih is not None
            ]

        # Symbolic harmonization history
        symbolic_harmonization_history = None
        if state.symbolic_harmonization_history:
            symbolic_harmonization_history = [
                snap.symbolic_harmonization_index
                for snap in state.symbolic_harmonization_history
                if snap is not None
            ]

        # Drift magnitude history
        drift_magnitude_history = None
        if state.drift_magnitude_history:
            drift_magnitude_history = [
                dmh for dmh in state.drift_magnitude_history if dmh is not None
            ]

        # Consciousness order history
        consciousness_order_history = None
        if state.ucf_history:
            consciousness_order_history = [
                snap.consciousness_order_index
                for snap in state.ucf_history
                if snap is not None
            ]

        # ====================================================================
        # STEP 10: COMPUTE IDENTITY RESONANCE MEMORY
        # ====================================================================

        snapshot = compute_identity_resonance_memory(
            # Phase 34: Identity Harmonics
            core_identity_harmonic=core_identity_harmonic,
            adaptive_identity_harmonic=adaptive_identity_harmonic,
            relational_identity_harmonic=relational_identity_harmonic,
            identity_stability_score=identity_stability_score,
            identity_flexibility_score=identity_flexibility_score,
            # Phase 35: Predictive Persona Drift
            drift_magnitude_prediction=drift_magnitude_prediction,
            drift_stability_score=drift_stability_score,
            drift_likelihood_band=drift_likelihood_band,
            # Phase 17: Semantic Integrity
            semantic_integrity=semantic_integrity,
            # Phase 27: Symbolic Harmonization
            symbolic_harmonization_index=symbolic_harmonization_index,
            # Phase 26: Unified Consciousness
            consciousness_order_index=consciousness_order_index,
            # Phase 18: Temporal Entropy
            temporal_entropy_volatility=temporal_entropy_volatility,
            temporal_entropy_diff=temporal_entropy_diff,
            # Phase 24: Resonance Weighting
            resonance_weighting_entropy=resonance_weighting_entropy,
            # Phase 22: Mirror-Time Cycle (optional)
            cycle_alignment=cycle_alignment,
            cycle_stability_band=cycle_stability_band,
            # Historical context
            cih_history=cih_history,
            aih_history=aih_history,
            rih_history=rih_history,
            identity_stability_history=identity_stability_history,
            semantic_integrity_history=semantic_integrity_history,
            symbolic_harmonization_history=symbolic_harmonization_history,
            drift_magnitude_history=drift_magnitude_history,
            consciousness_order_history=consciousness_order_history,
        )

        # ====================================================================
        # STEP 11: STORE RESULTS IN STATE
        # ====================================================================

        if snapshot is not None:
            # Append to histories
            state.identity_resonance_memory_history.append(snapshot)
            state.ims_history.append(snapshot.identity_memory_strength)
            state.iep_history.append(snapshot.identity_echo_persistence)
            state.ida_history.append(snapshot.identity_drift_anchoring)
            state.irm_memory_band_history.append(snapshot.memory_band)

            # Update current metrics
            state.identity_resonance_memory_snapshot = snapshot
            state.current_ims = snapshot.identity_memory_strength
            state.current_iep = snapshot.identity_echo_persistence
            state.current_ida = snapshot.identity_drift_anchoring
            state.current_irm_memory_band = snapshot.memory_band
            state.current_irm_tags = snapshot.diagnostic_tags
        else:
            # Snapshot computation failed (insufficient data)
            state.identity_resonance_memory_history.append(None)
            state.ims_history.append(None)
            state.iep_history.append(None)
            state.ida_history.append(None)
            state.irm_memory_band_history.append(None)
            state.identity_resonance_memory_snapshot = None
            state.current_ims = None
            state.current_iep = None
            state.current_ida = None
            state.current_irm_memory_band = None
            state.current_irm_tags = []

    def _update_adaptive_continuity(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 37 Adaptive Continuity Engine (observation only).

        This method computes the adaptive continuity snapshot by modeling session-wide
        continuity across narrative, identity, and symbolic dimensions.

        The ACE produces:
          1. Narrative Continuity Coefficient (NCC): Theme/intent/symbolic stability
          2. Identity Continuity Coefficient (ICC): Identity pattern continuity
          3. Continuity Stability Score (CSS): Overall session resilience
          4. Continuity Band: LOW / MEDIUM / HIGH classification
          5. Continuity Tags: CONTINUITY_STRONG, CONTINUITY_FRAGMENTED, etc.

        The ACE is purely observational and does NOT affect any existing pipeline
        behavior. It is designed for tone-only micro-adjustments (±0.015 max) and analytics.

        This update runs AFTER Phase 36 IRM to leverage identity resonance memory.

        Args:
            state: CoherenceState to update in place
        """
        from symbolu.formulas.adaptive_continuity_engine import compute_adaptive_continuity

        # ====================================================================
        # STEP 1: GATHER SYMBOLIC HARMONIZATION (Phase 27)
        # ====================================================================

        symbolic_harmonization_index = state.current_symbolic_harmonization_index

        # Extract history
        symbolic_harmonization_history = None
        if state.symbolic_harmonization_history:
            symbolic_harmonization_history = [
                snap.symbolic_harmonization_index
                for snap in state.symbolic_harmonization_history
                if snap is not None
            ]

        # ====================================================================
        # STEP 2: GATHER IDENTITY RESONANCE MEMORY (Phase 36)
        # ====================================================================

        identity_memory_strength = state.current_ims
        identity_echo_persistence = state.current_iep
        identity_drift_anchoring = state.current_ida

        # Extract histories
        ims_history = None
        iep_history = None
        ida_history = None

        if state.ims_history:
            ims_history = [
                ims for ims in state.ims_history if ims is not None
            ]

        if state.iep_history:
            iep_history = [
                iep for iep in state.iep_history if iep is not None
            ]

        if state.ida_history:
            ida_history = [
                ida for ida in state.ida_history if ida is not None
            ]

        # ====================================================================
        # STEP 3: GATHER IDENTITY HARMONICS (Phase 34)
        # ====================================================================

        core_identity_harmonic = state.current_cih
        adaptive_identity_harmonic = state.current_aih
        relational_identity_harmonic = state.current_rih
        identity_stability_score = None
        identity_harmonics_index = state.current_identity_harmonics_index

        # Extract from latest snapshot if available
        if state.identity_harmonics_snapshot is not None:
            identity_stability_score = state.identity_harmonics_snapshot.identity_stability_score

        # Extract identity stability history
        identity_stability_history = None
        if state.identity_stability_history:
            identity_stability_history = [
                ish for ish in state.identity_stability_history if ish is not None
            ]

        # ====================================================================
        # STEP 4: GATHER PREDICTIVE DRIFT (Phase 35)
        # ====================================================================

        drift_magnitude_prediction = state.current_drift_magnitude_prediction
        drift_stability_score = state.current_drift_stability_score
        drift_likelihood_band = state.current_drift_likelihood_band

        # Extract drift histories
        drift_magnitude_history = None
        drift_stability_history = None

        if state.drift_magnitude_history:
            drift_magnitude_history = [
                dmh for dmh in state.drift_magnitude_history if dmh is not None
            ]

        if state.drift_stability_history:
            drift_stability_history = [
                dsh for dsh in state.drift_stability_history if dsh is not None
            ]

        # ====================================================================
        # STEP 5: GATHER UNIFIED CONSCIOUSNESS (Phase 26)
        # ====================================================================

        consciousness_order_index = state.current_coi
        consciousness_stability_index = state.current_csi

        # Extract consciousness histories
        consciousness_order_history = None
        consciousness_stability_history = None

        if state.ucf_history:
            consciousness_order_history = [
                snap.consciousness_order_index
                for snap in state.ucf_history
                if snap is not None
            ]
            consciousness_stability_history = [
                snap.consciousness_stability_index
                for snap in state.ucf_history
                if snap is not None
            ]

        # ====================================================================
        # STEP 6: GATHER TEMPORAL ENTROPY (Phase 18)
        # ====================================================================

        temporal_entropy_volatility = state.temporal_entropy_volatility
        temporal_entropy_diff = state.temporal_entropy_diff

        # Extract temporal entropy volatility history
        temporal_entropy_volatility_history = None
        if state.temporal_entropy_volatility_history:
            temporal_entropy_volatility_history = [
                tev for tev in state.temporal_entropy_volatility_history if tev is not None
            ]

        # ====================================================================
        # STEP 7: GATHER SEMANTIC INTEGRITY (Phase 17)
        # ====================================================================

        semantic_integrity = state.semantic_integrity_score

        # Extract semantic integrity history
        semantic_integrity_history = None
        if state.semantic_integrity_history:
            semantic_integrity_history = [
                sih for sih in state.semantic_integrity_history if sih is not None
            ]

        # ====================================================================
        # STEP 8: GATHER RESONANCE WEIGHTING (Phase 24)
        # ====================================================================

        resonance_weighting_entropy = state.current_resonance_entropy

        # ====================================================================
        # STEP 9: COMPUTE ADAPTIVE CONTINUITY
        # ====================================================================

        snapshot = compute_adaptive_continuity(
            # Phase 27: Symbolic Harmonization
            symbolic_harmonization_index=symbolic_harmonization_index,
            symbolic_harmonization_history=symbolic_harmonization_history,
            # Phase 36: Identity Resonance Memory
            identity_memory_strength=identity_memory_strength,
            identity_echo_persistence=identity_echo_persistence,
            identity_drift_anchoring=identity_drift_anchoring,
            ims_history=ims_history,
            iep_history=iep_history,
            ida_history=ida_history,
            # Phase 34: Identity Harmonics
            core_identity_harmonic=core_identity_harmonic,
            adaptive_identity_harmonic=adaptive_identity_harmonic,
            relational_identity_harmonic=relational_identity_harmonic,
            identity_stability_score=identity_stability_score,
            identity_harmonics_index=identity_harmonics_index,
            identity_stability_history=identity_stability_history,
            # Phase 35: Predictive Persona Drift
            drift_magnitude_prediction=drift_magnitude_prediction,
            drift_stability_score=drift_stability_score,
            drift_likelihood_band=drift_likelihood_band,
            drift_magnitude_history=drift_magnitude_history,
            drift_stability_history=drift_stability_history,
            # Phase 26: Unified Consciousness Formula
            consciousness_order_index=consciousness_order_index,
            consciousness_stability_index=consciousness_stability_index,
            consciousness_order_history=consciousness_order_history,
            consciousness_stability_history=consciousness_stability_history,
            # Phase 18: Temporal Entropy
            temporal_entropy_volatility=temporal_entropy_volatility,
            temporal_entropy_diff=temporal_entropy_diff,
            temporal_entropy_volatility_history=temporal_entropy_volatility_history,
            # Phase 17: Semantic Integrity
            semantic_integrity=semantic_integrity,
            semantic_integrity_history=semantic_integrity_history,
            # Phase 24: Resonance Weighting
            resonance_weighting_entropy=resonance_weighting_entropy,
        )

        # ====================================================================
        # STEP 10: STORE RESULTS IN STATE
        # ====================================================================

        if snapshot is not None:
            # Append to histories
            state.adaptive_continuity_history.append(snapshot)
            state.ncc_history.append(snapshot.ncc)
            state.icc_history.append(snapshot.icc)
            state.css_history.append(snapshot.css)
            state.continuity_band_history.append(snapshot.continuity_band)

            # Update current metrics
            state.adaptive_continuity_snapshot = snapshot
            state.current_ncc = snapshot.ncc
            state.current_icc = snapshot.icc
            state.current_css = snapshot.css
            state.current_continuity_band = snapshot.continuity_band
            state.current_continuity_tags = snapshot.continuity_tags
        else:
            # Snapshot computation failed (insufficient data)
            state.adaptive_continuity_history.append(None)
            state.ncc_history.append(None)
            state.icc_history.append(None)
            state.css_history.append(None)
            state.continuity_band_history.append(None)
            state.adaptive_continuity_snapshot = None
            state.current_ncc = None
            state.current_icc = None
            state.current_css = None
            state.current_continuity_band = None
            state.current_continuity_tags = []

    def _update_temporal_coherence_forecast(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 38 Temporal Coherence Forecasting Model (observation only).

        This method computes the temporal coherence forecast snapshot by predicting how
        coherence, continuity, identity, and drift metrics are expected to evolve across
        future turns.

        The TCFM produces:
          1. Coherence Trajectory Forecast (CTF): Predicts if coherence_fused will rise/fall/remain stable
          2. Continuity Trajectory Forecast (CNF): Projects NCC/ICC/CSS into next-turn estimates
          3. Drift Forecast Probability (DFP): Likelihood of future coherence disruption
          4. Forecast Stability Score (FSS): Confidence in forecast based on variance patterns
          5. Forecast Band: STRONG_UPTREND / MILD_UPTREND / NEUTRAL / MILD_DOWNTREND / STRONG_DOWNTREND
          6. Diagnostic Tags: FORECAST_UPTREND, FORECAST_DOWNTREND, etc.

        The TCFM is purely observational and does NOT affect any existing pipeline
        behavior. It is designed for tone-only micro-adjustments (±0.015 max) and analytics.

        This update runs AFTER Phase 37 ACE to leverage continuity signals.

        Args:
            state: CoherenceState to update in place
        """
        from symbolu.formulas.temporal_coherence_forecasting import compute_temporal_coherence_forecast

        # ====================================================================
        # STEP 1: GATHER COHERENCE FUSION (Phase 16)
        # ====================================================================

        coherence_fused = state.coherence_fused

        # Extract coherence_fused history
        coherence_fused_history = None
        if state.coherence_fused_history:
            coherence_fused_history = [
                cfh for cfh in state.coherence_fused_history if cfh is not None
            ]

        # ====================================================================
        # STEP 2: GATHER ADAPTIVE CONTINUITY ENGINE (Phase 37)
        # ====================================================================

        ncc = state.current_ncc
        icc = state.current_icc
        css = state.current_css

        # Extract continuity histories
        ncc_history = None
        icc_history = None
        css_history = None

        if state.ncc_history:
            ncc_history = [
                ncc_val for ncc_val in state.ncc_history if ncc_val is not None
            ]

        if state.icc_history:
            icc_history = [
                icc_val for icc_val in state.icc_history if icc_val is not None
            ]

        if state.css_history:
            css_history = [
                css_val for css_val in state.css_history if css_val is not None
            ]

        # ====================================================================
        # STEP 3: GATHER PREDICTIVE DRIFT (Phase 35)
        # ====================================================================

        drift_magnitude_prediction = state.current_drift_magnitude_prediction
        drift_stability_score = state.current_drift_stability_score

        # Extract drift histories
        drift_magnitude_history = None
        if state.drift_magnitude_history:
            drift_magnitude_history = [
                dmh for dmh in state.drift_magnitude_history if dmh is not None
            ]

        # ====================================================================
        # STEP 4: GATHER IDENTITY RESONANCE MEMORY (Phase 36)
        # ====================================================================

        identity_memory_strength = state.current_ims
        identity_drift_anchoring = state.current_ida

        # ====================================================================
        # STEP 5: GATHER IDENTITY HARMONICS (Phase 34)
        # ====================================================================

        identity_stability_score = None
        if state.identity_harmonics_snapshot is not None:
            identity_stability_score = state.identity_harmonics_snapshot.identity_stability_score

        # ====================================================================
        # STEP 6: GATHER SYMBOLIC HARMONIZATION (Phase 27)
        # ====================================================================

        symbolic_harmonization_index = state.current_symbolic_harmonization_index

        # Extract symbolic harmonization history
        symbolic_harmonization_history = None
        if state.symbolic_harmonization_history:
            symbolic_harmonization_history = [
                snap.symbolic_harmonization_index
                for snap in state.symbolic_harmonization_history
                if snap is not None
            ]

        # ====================================================================
        # STEP 7: GATHER UNIFIED CONSCIOUSNESS (Phase 26)
        # ====================================================================

        consciousness_order_index = state.current_coi
        consciousness_stability_index = state.current_csi

        # Extract consciousness order history
        consciousness_order_history = None
        if state.ucf_history:
            consciousness_order_history = [
                snap.consciousness_order_index
                for snap in state.ucf_history
                if snap is not None
            ]

        # ====================================================================
        # STEP 8: GATHER TEMPORAL ENTROPY (Phase 18)
        # ====================================================================

        temporal_entropy_volatility = state.temporal_entropy_volatility
        temporal_entropy_diff = state.temporal_entropy_diff

        # Extract temporal entropy volatility history
        temporal_entropy_volatility_history = None
        if state.temporal_entropy_volatility_history:
            temporal_entropy_volatility_history = [
                tev for tev in state.temporal_entropy_volatility_history if tev is not None
            ]

        # ====================================================================
        # STEP 9: COMPUTE TEMPORAL COHERENCE FORECAST
        # ====================================================================

        snapshot = compute_temporal_coherence_forecast(
            # Phase 16: Formula Fusion Stabilizer
            coherence_fused=coherence_fused,
            coherence_fused_history=coherence_fused_history,
            # Phase 37: Adaptive Continuity Engine
            ncc=ncc,
            icc=icc,
            css=css,
            ncc_history=ncc_history,
            icc_history=icc_history,
            css_history=css_history,
            # Phase 35: Predictive Persona Drift
            drift_magnitude_prediction=drift_magnitude_prediction,
            drift_stability_score=drift_stability_score,
            drift_magnitude_history=drift_magnitude_history,
            # Phase 36: Identity Resonance Memory
            identity_memory_strength=identity_memory_strength,
            identity_drift_anchoring=identity_drift_anchoring,
            # Phase 34: Identity Harmonics
            identity_stability_score=identity_stability_score,
            # Phase 27: Symbolic Harmonization
            symbolic_harmonization_index=symbolic_harmonization_index,
            symbolic_harmonization_history=symbolic_harmonization_history,
            # Phase 26: Unified Consciousness Formula
            consciousness_order_index=consciousness_order_index,
            consciousness_stability_index=consciousness_stability_index,
            consciousness_order_history=consciousness_order_history,
            # Phase 18: Temporal Entropy
            temporal_entropy_volatility=temporal_entropy_volatility,
            temporal_entropy_diff=temporal_entropy_diff,
            temporal_entropy_volatility_history=temporal_entropy_volatility_history,
        )

        # ====================================================================
        # STEP 10: STORE RESULTS IN STATE
        # ====================================================================

        if snapshot is not None:
            # Append to histories
            state.forecast_history.append(snapshot)
            state.forecast_band_history.append(snapshot.forecast_band)
            state.forecast_strength_history.append(snapshot.forecast_strength)
            state.drift_influence_history.append(snapshot.drift_influence)

            # Update current metrics
            state.temporal_forecast_snapshot = snapshot
            state.current_forecast_coherence_slope = snapshot.coherence_slope
            state.current_forecast_continuity_slope = snapshot.continuity_slope
            state.current_forecast_drift_influence = snapshot.drift_influence
            state.current_forecast_entropy_forward_risk = snapshot.entropy_forward_risk
            state.current_forecast_strength = snapshot.forecast_strength
            state.current_forecast_band = snapshot.forecast_band
            state.current_forecast_tags = snapshot.diagnostic_tags
        else:
            # Snapshot computation failed (insufficient data)
            state.forecast_history.append(None)
            state.forecast_band_history.append(None)
            state.forecast_strength_history.append(None)
            state.drift_influence_history.append(None)
            state.temporal_forecast_snapshot = None
            state.current_forecast_coherence_slope = None
            state.current_forecast_continuity_slope = None
            state.current_forecast_drift_influence = None
            state.current_forecast_entropy_forward_risk = None
            state.current_forecast_strength = None
            state.current_forecast_band = None
            state.current_forecast_tags = []

    def _update_multi_horizon_forecast(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 39 Multi-Horizon Temporal Forecasting Engine (observation only).

        This method computes the multi-horizon forecast snapshot by predicting how
        coherence, continuity, identity, and drift metrics are expected to evolve across
        three temporal horizons:
          • H1 (Short-Term): 1-3 turns
          • H2 (Mid-Term): 4-8 turns
          • H3 (Long-Term): 9-20 turns

        The MHTFE produces:
          1. Per-Horizon Forecasts (H1, H2, H3): Each with slopes, risks, strength, band
          2. Forecast Consensus Index (FCI): Agreement across horizons [0.0, 1.0]
          3. Future Stability Envelope (FSE): Uncertainty-modulated stability [0.0, 1.0]
          4. Diagnostic Tags: MULTI_HORIZON_AGREEMENT, SHORT_TERM_NOISE, etc.

        The MHTFE is purely observational and does NOT affect any existing pipeline
        behavior. It is designed for tone-only micro-adjustments (±0.015 max) and analytics.

        This update runs AFTER Phase 38 TCFM to leverage forecast signals.

        Args:
            state: CoherenceState to update in place
        """
        from symbolu.formulas.multi_horizon_temporal_forecasting import compute_multi_horizon_forecast

        # ====================================================================
        # STEP 1: GATHER COHERENCE FUSION (Phase 16)
        # ====================================================================

        # Extract coherence_fused history
        coherence_fused_history = None
        if state.coherence_fused_history:
            coherence_fused_history = [
                cfh for cfh in state.coherence_fused_history if cfh is not None
            ]

        # ====================================================================
        # STEP 2: GATHER ADAPTIVE CONTINUITY ENGINE (Phase 37)
        # ====================================================================

        # Extract continuity histories
        ncc_history = None
        icc_history = None
        css_history = None

        if state.ncc_history:
            ncc_history = [
                ncc_val for ncc_val in state.ncc_history if ncc_val is not None
            ]

        if state.icc_history:
            icc_history = [
                icc_val for icc_val in state.icc_history if icc_val is not None
            ]

        if state.css_history:
            css_history = [
                css_val for css_val in state.css_history if css_val is not None
            ]

        # ====================================================================
        # STEP 3: GATHER PREDICTIVE DRIFT (Phase 35)
        # ====================================================================

        drift_magnitude_prediction = state.current_drift_magnitude_prediction
        drift_stability_score = state.current_drift_stability_score

        # ====================================================================
        # STEP 4: GATHER IDENTITY RESONANCE MEMORY (Phase 36)
        # ====================================================================

        identity_memory_strength = state.current_ims
        identity_drift_anchoring = state.current_ida

        # ====================================================================
        # STEP 5: GATHER IDENTITY HARMONICS (Phase 34)
        # ====================================================================

        identity_stability_score = None
        if state.identity_harmonics_snapshot is not None:
            identity_stability_score = state.identity_harmonics_snapshot.identity_stability_score

        # ====================================================================
        # STEP 6: GATHER SYMBOLIC HARMONIZATION (Phase 27)
        # ====================================================================

        symbolic_harmonization_index = state.current_symbolic_harmonization_index

        # Extract symbolic harmonization history
        symbolic_harmonization_history = None
        if state.symbolic_harmonization_history:
            symbolic_harmonization_history = [
                snap.symbolic_harmonization_index
                for snap in state.symbolic_harmonization_history
                if snap is not None
            ]

        # ====================================================================
        # STEP 7: GATHER UNIFIED CONSCIOUSNESS (Phase 26)
        # ====================================================================

        consciousness_order_index = state.current_coi
        consciousness_stability_index = state.current_csi

        # Extract consciousness order history
        consciousness_order_history = None
        if state.ucf_history:
            consciousness_order_history = [
                snap.consciousness_order_index
                for snap in state.ucf_history
                if snap is not None
            ]

        # ====================================================================
        # STEP 8: GATHER TEMPORAL ENTROPY (Phase 18)
        # ====================================================================

        temporal_entropy_volatility = state.temporal_entropy_volatility
        temporal_entropy_diff = state.temporal_entropy_diff

        # ====================================================================
        # STEP 9: COMPUTE MULTI-HORIZON FORECAST
        # ====================================================================

        snapshot = compute_multi_horizon_forecast(
            # Phase 16: Formula Fusion Stabilizer
            coherence_fused_history=coherence_fused_history,
            # Phase 37: Adaptive Continuity Engine
            ncc_history=ncc_history,
            icc_history=icc_history,
            css_history=css_history,
            # Phase 35: Predictive Persona Drift
            drift_magnitude_prediction=drift_magnitude_prediction,
            drift_stability_score=drift_stability_score,
            # Phase 36: Identity Resonance Memory
            identity_memory_strength=identity_memory_strength,
            identity_drift_anchoring=identity_drift_anchoring,
            # Phase 34: Identity Harmonics
            identity_stability_score=identity_stability_score,
            # Phase 27: Symbolic Harmonization
            symbolic_harmonization_index=symbolic_harmonization_index,
            symbolic_harmonization_history=symbolic_harmonization_history,
            # Phase 26: Unified Consciousness Formula
            consciousness_order_index=consciousness_order_index,
            consciousness_stability_index=consciousness_stability_index,
            consciousness_order_history=consciousness_order_history,
            # Phase 18: Temporal Entropy
            temporal_entropy_volatility=temporal_entropy_volatility,
            temporal_entropy_diff=temporal_entropy_diff,
        )

        # ====================================================================
        # STEP 10: STORE RESULTS IN STATE
        # ====================================================================

        if snapshot is not None:
            # Append to histories
            state.multi_horizon_forecast_history.append(snapshot)
            state.forecast_consensus_history.append(snapshot.forecast_consensus_index)
            state.future_stability_envelope_history.append(snapshot.future_stability_envelope)
            state.horizon_band_H1_history.append(snapshot.h1_forecast.forecast_band)
            state.horizon_band_H2_history.append(snapshot.h2_forecast.forecast_band)
            state.horizon_band_H3_history.append(snapshot.h3_forecast.forecast_band)

            # Update current metrics
            state.multi_horizon_forecast_snapshot = snapshot

            # H1 metrics
            state.horizon_slope_H1 = snapshot.h1_forecast.coherence_slope
            state.horizon_continuity_slope_H1 = snapshot.h1_forecast.continuity_slope
            state.horizon_drift_H1 = snapshot.h1_forecast.drift_risk
            state.horizon_entropy_H1 = snapshot.h1_forecast.entropy_risk
            state.horizon_strength_H1 = snapshot.h1_forecast.forecast_strength
            state.horizon_band_H1 = snapshot.h1_forecast.forecast_band

            # H2 metrics
            state.horizon_slope_H2 = snapshot.h2_forecast.coherence_slope
            state.horizon_continuity_slope_H2 = snapshot.h2_forecast.continuity_slope
            state.horizon_drift_H2 = snapshot.h2_forecast.drift_risk
            state.horizon_entropy_H2 = snapshot.h2_forecast.entropy_risk
            state.horizon_strength_H2 = snapshot.h2_forecast.forecast_strength
            state.horizon_band_H2 = snapshot.h2_forecast.forecast_band

            # H3 metrics
            state.horizon_slope_H3 = snapshot.h3_forecast.coherence_slope
            state.horizon_continuity_slope_H3 = snapshot.h3_forecast.continuity_slope
            state.horizon_drift_H3 = snapshot.h3_forecast.drift_risk
            state.horizon_entropy_H3 = snapshot.h3_forecast.entropy_risk
            state.horizon_strength_H3 = snapshot.h3_forecast.forecast_strength
            state.horizon_band_H3 = snapshot.h3_forecast.forecast_band

            # Cross-horizon analytics
            state.forecast_consensus_index = snapshot.forecast_consensus_index
            state.future_stability_envelope = snapshot.future_stability_envelope
            state.current_mh_forecast_tags = snapshot.diagnostic_tags
        else:
            # Snapshot computation failed (insufficient data)
            state.multi_horizon_forecast_history.append(None)
            state.forecast_consensus_history.append(None)
            state.future_stability_envelope_history.append(None)
            state.horizon_band_H1_history.append(None)
            state.horizon_band_H2_history.append(None)
            state.horizon_band_H3_history.append(None)

            state.multi_horizon_forecast_snapshot = None
            state.horizon_slope_H1 = None
            state.horizon_continuity_slope_H1 = None
            state.horizon_drift_H1 = None
            state.horizon_entropy_H1 = None
            state.horizon_strength_H1 = None
            state.horizon_band_H1 = None
            state.horizon_slope_H2 = None
            state.horizon_continuity_slope_H2 = None
            state.horizon_drift_H2 = None
            state.horizon_entropy_H2 = None
            state.horizon_strength_H2 = None
            state.horizon_band_H2 = None
            state.horizon_slope_H3 = None
            state.horizon_continuity_slope_H3 = None
            state.horizon_drift_H3 = None
            state.horizon_entropy_H3 = None
            state.horizon_strength_H3 = None
            state.horizon_band_H3 = None
            state.forecast_consensus_index = None
            state.future_stability_envelope = None
            state.current_mh_forecast_tags = []

    def _update_cross_horizon_resonance(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 40 Cross-Horizon Resonance Alignment Engine (observation only).

        This method computes the cross-horizon resonance alignment snapshot by measuring
        how well the multi-horizon temporal forecasts (H1/H2/H3 from Phase 39) align with
        resonance, identity, and drift metrics.

        CHRAE answers the question:
          "How well do the forecasted trends line up with the resonance, identity,
           and symbolic signals we already trust?"

        The CHRAE produces:
          1. Horizon Alignment Scores (HAS): has_H1, has_H2, has_H3 [0.0, 1.0]
          2. Resonance Alignment Index (RAI): Global alignment [0.0, 1.0]
          3. Identity–Forecast Agreement (IFA): Identity support [0.0, 1.0]
          4. Drift–Forecast Tension (DFT): Forecast/drift conflict [0.0, 1.0]
          5. Alignment Band: HIGH_ALIGNMENT | MIXED_ALIGNMENT | LOW_ALIGNMENT
          6. Diagnostic Tags: FORECAST_RES_ON_TRACK, IDENTITY_SUPPORTS_TREND, etc.

        The CHRAE is purely observational and does NOT affect any existing pipeline
        behavior. It is designed for tone-only micro-adjustments (±0.015 max) and analytics.

        This update runs AFTER Phase 39 MHTFE to leverage multi-horizon forecast signals.

        Args:
            state: CoherenceState to update in place
        """
        from symbolu.formulas.cross_horizon_resonance_alignment import compute_cross_horizon_resonance

        # ====================================================================
        # STEP 1: GATHER MULTI-HORIZON FORECAST (Phase 39) - REQUIRED
        # ====================================================================

        multi_horizon_forecast = state.multi_horizon_forecast_snapshot

        # If no multi-horizon forecast, cannot compute CHRAE
        if multi_horizon_forecast is None:
            # Append None to histories
            state.cross_horizon_resonance_history.append(None)
            state.has_H1_history.append(None)
            state.has_H2_history.append(None)
            state.has_H3_history.append(None)
            state.rai_history.append(None)
            state.ifa_history.append(None)
            state.dft_history.append(None)
            state.chra_alignment_band_history.append(None)

            # Clear current metrics
            state.cross_horizon_resonance_snapshot = None
            state.current_has_H1 = None
            state.current_has_H2 = None
            state.current_has_H3 = None
            state.current_rai = None
            state.current_ifa = None
            state.current_dft = None
            state.current_alignment_band = None
            state.current_chra_alignment_tags = []
            return

        # ====================================================================
        # STEP 2: GATHER RESONANCE WEIGHTING (Phase 24) - OPTIONAL
        # ====================================================================

        resonance_snapshot = None
        if state.resonance_weighting_history and len(state.resonance_weighting_history) > 0:
            # Get latest resonance weighting snapshot
            resonance_snapshot = state.resonance_weighting_history[-1]

        # ====================================================================
        # STEP 3: GATHER SYMBOLIC HARMONIZATION (Phase 27) - OPTIONAL
        # ====================================================================

        symbolic_harmonization = state.symbolic_harmonization_snapshot

        # ====================================================================
        # STEP 4: GATHER IDENTITY HARMONICS (Phase 34) - OPTIONAL
        # ====================================================================

        identity_harmonics = state.identity_harmonics_snapshot

        # ====================================================================
        # STEP 5: GATHER IDENTITY RESONANCE MEMORY (Phase 36) - OPTIONAL
        # ====================================================================

        identity_resonance_memory = state.identity_resonance_memory_snapshot

        # ====================================================================
        # STEP 6: GATHER PREDICTIVE PERSONA DRIFT (Phase 35) - OPTIONAL
        # ====================================================================

        predictive_persona_drift = state.predictive_drift_snapshot

        # ====================================================================
        # STEP 7: COMPUTE CROSS-HORIZON RESONANCE ALIGNMENT
        # ====================================================================

        snapshot = compute_cross_horizon_resonance(
            multi_horizon_forecast=multi_horizon_forecast,
            resonance_snapshot=resonance_snapshot,
            symbolic_harmonization=symbolic_harmonization,
            identity_harmonics=identity_harmonics,
            identity_resonance_memory=identity_resonance_memory,
            predictive_persona_drift=predictive_persona_drift,
        )

        # ====================================================================
        # STEP 8: STORE RESULTS IN STATE
        # ====================================================================

        if snapshot is not None:
            # Append to histories
            state.cross_horizon_resonance_history.append(snapshot)
            state.has_H1_history.append(snapshot.has_H1)
            state.has_H2_history.append(snapshot.has_H2)
            state.has_H3_history.append(snapshot.has_H3)
            state.rai_history.append(snapshot.rai)
            state.ifa_history.append(snapshot.ifa)
            state.dft_history.append(snapshot.dft)
            state.chra_alignment_band_history.append(snapshot.alignment_band)

            # Update current metrics
            state.cross_horizon_resonance_snapshot = snapshot
            state.current_has_H1 = snapshot.has_H1
            state.current_has_H2 = snapshot.has_H2
            state.current_has_H3 = snapshot.has_H3
            state.current_rai = snapshot.rai
            state.current_ifa = snapshot.ifa
            state.current_dft = snapshot.dft
            state.current_alignment_band = snapshot.alignment_band
            state.current_chra_alignment_tags = snapshot.diagnostic_tags
        else:
            # Snapshot computation failed (should not happen if multi_horizon_forecast exists, but safeguard)
            state.cross_horizon_resonance_history.append(None)
            state.has_H1_history.append(None)
            state.has_H2_history.append(None)
            state.has_H3_history.append(None)
            state.rai_history.append(None)
            state.ifa_history.append(None)
            state.dft_history.append(None)
            state.chra_alignment_band_history.append(None)

            state.cross_horizon_resonance_snapshot = None
            state.current_has_H1 = None
            state.current_has_H2 = None
            state.current_has_H3 = None
            state.current_rai = None
            state.current_ifa = None
            state.current_dft = None
            state.current_alignment_band = None
            state.current_chra_alignment_tags = []

    def _update_coherence_regime(
        self,
        state: CoherenceState,
    ) -> None:
        """
        Update Phase 41 Coherence-Regime Scenario Mapper (observation only).

        This method computes the coherence regime snapshot by classifying the session into
        high-level regimes based on the full Symbol-U coherence/identity/drift/entropy stack.

        CRSM answers the question: "What kind of session is this?"
          • Stable therapeutic processing
          • Volatile identity drift
          • Deep reflective exploration
          • Surface level interaction
          • Ambivalent conflicted state
          • Recovery stabilization phase

        The CRSM produces:
          1. Regime scores across canonical regimes [0.0, 1.0]
          2. Dominant regime (highest score)
          3. Secondary regimes (sorted by score)
          4. Regime band: "stable" | "mixed" | "volatile"
          5. Diagnostic tags
          6. Deterministic notes

        The CRSM is purely observational and does NOT affect any existing pipeline
        behavior. It is designed for analytics, dashboards, and UI diagnostics only.

        This update runs AFTER all other phases (esp. Phases 37, 38, 39, 40) to leverage
        the full coherence/continuity/forecast stack.

        Args:
            state: CoherenceState to update in place
        """
        from symbolu.formulas.coherence_regime_scenario_mapper import compute_coherence_regime

        # ====================================================================
        # STEP 1: GATHER CORE REQUIRED SIGNALS
        # ====================================================================

        # Phase 16: Formula Fusion Stabilizer
        coherence_fused = state.coherence_fused
        coherence_fused_history = state.coherence_fused_history if state.coherence_fused_history else None

        # Phase 10 & 12: Coherence v3
        coherence_v3 = state.coherence_score_v3
        coherence_v3_quality = state.coherence_v3_quality

        # Phase 19: Drift Fusion
        drift_fusion_index = state.drift_fusion_index
        drift_fusion_index_history = state.drift_fusion_index_history if state.drift_fusion_index_history else None

        # Phase 37: Adaptive Continuity Engine
        css = state.current_css
        css_history = state.css_history if state.css_history else None

        # ====================================================================
        # STEP 2: GATHER OPTIONAL SIGNALS
        # ====================================================================

        # Phase 26: Unified Consciousness Formula
        ucf_coi = state.current_coi
        ucf_csi = state.current_csi
        ucf_cip = state.current_cip

        # Phase 27: Symbolic Harmonization
        symbolic_harmonization_index = state.current_symbolic_harmonization_index

        # Phase 24: Resonance Weighting
        resonance_weighting_entropy = state.current_resonance_entropy

        # Phase 34: Identity Harmonics
        identity_stability_score = None
        if state.identity_harmonics_snapshot is not None:
            identity_stability_score = state.identity_harmonics_snapshot.identity_stability_score

        # Phase 35: Predictive Persona Drift
        drift_magnitude_prediction = state.current_drift_magnitude_prediction

        # Phase 36: Identity Resonance Memory
        identity_memory_strength = state.current_ims
        identity_echo_persistence = state.current_iep
        identity_drift_anchoring = state.current_ida

        # Phase 17: Semantic Integrity & Cognitive Drift v3
        cognitive_drift_v3 = state.cognitive_drift_v3

        # Phase 18: Temporal Entropy
        temporal_entropy_instant = None
        temporal_entropy_volatility = state.temporal_entropy_volatility
        temporal_entropy_volatility_history = state.temporal_entropy_volatility_history if state.temporal_entropy_volatility_history else None

        # Calculate instant entropy from snapshot if available
        if state.temporal_entropy_snapshot is not None:
            temporal_entropy_instant = state.temporal_entropy_snapshot.instant_entropy

        # Phase 37: Adaptive Continuity Engine (continued)
        ncc = state.current_ncc
        icc = state.current_icc

        # Phase 38: Temporal Coherence Forecasting
        coherence_slope = state.current_forecast_coherence_slope
        continuity_slope = state.current_forecast_continuity_slope

        # Phase 40: Cross-Horizon Resonance Alignment
        drift_forecast_tension = state.current_dft

        # Phase 32: Insight Window Gating (if available)
        insight_window_active = False
        # Check if insight window module exists and is active
        # For now, we'll default to False unless we have access to the insight window state

        # ====================================================================
        # STEP 3: COMPUTE COHERENCE REGIME
        # ====================================================================

        snapshot = compute_coherence_regime(
            coherence_fused=coherence_fused,
            coherence_fused_history=coherence_fused_history,
            coherence_v3=coherence_v3,
            coherence_v3_quality=coherence_v3_quality,
            ucf_coi=ucf_coi,
            ucf_csi=ucf_csi,
            ucf_cip=ucf_cip,
            symbolic_harmonization_index=symbolic_harmonization_index,
            resonance_weighting_entropy=resonance_weighting_entropy,
            identity_stability_score=identity_stability_score,
            drift_magnitude_prediction=drift_magnitude_prediction,
            identity_memory_strength=identity_memory_strength,
            identity_echo_persistence=identity_echo_persistence,
            identity_drift_anchoring=identity_drift_anchoring,
            drift_fusion_index=drift_fusion_index,
            drift_fusion_index_history=drift_fusion_index_history,
            cognitive_drift_v3=cognitive_drift_v3,
            temporal_entropy_instant=temporal_entropy_instant,
            temporal_entropy_volatility=temporal_entropy_volatility,
            temporal_entropy_volatility_history=temporal_entropy_volatility_history,
            ncc=ncc,
            icc=icc,
            css=css,
            css_history=css_history,
            coherence_slope=coherence_slope,
            continuity_slope=continuity_slope,
            drift_forecast_tension=drift_forecast_tension,
            insight_window_active=insight_window_active,
        )

        # ====================================================================
        # STEP 4: STORE RESULTS IN STATE
        # ====================================================================

        if snapshot is not None:
            # Append to history
            state.coherence_regime_history.append(snapshot)

            # Update current metrics
            state.coherence_regime_snapshot = snapshot
            state.current_dominant_regime = snapshot.dominant_regime
            state.current_regime_band = snapshot.regime_band
            state.current_regime_scores = snapshot.regime_scores
        else:
            # Snapshot computation failed (insufficient data)
            state.coherence_regime_history.append(None)

            state.coherence_regime_snapshot = None
            state.current_dominant_regime = None
            state.current_regime_band = None
            state.current_regime_scores = {}
