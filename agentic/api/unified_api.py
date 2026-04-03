"""
Unified Symbol-U API Output Schema (USU-API v1.0)
================================================

This module provides a single JSON output format combining all pipeline components:
- Fusion Renderer symbolic/practical/mirror layers
- DHA insights
- MapperProfile details
- TTOR routing plan
- MLCR activation
- PipelineContext
- CoherenceReport

Design Principles:
- Zero-LLM: All operations are deterministic and rule-based
- Non-invasive: Does not modify pipeline behavior
- Additive: Optional layer that can be enabled without breaking existing code
- JSON-safe: All outputs are JSON-serializable

Usage:
    from agentic.api.unified_api import get_unified_json, get_public_response

    # After pipeline execution:
    unified = get_unified_json(ctx)
    public = get_public_response(ctx)
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class UnifiedOutput:
    """
    Unified output structure combining all pipeline layers.

    This is the complete API contract for Symbol-U AGI responses.

    Fields:
        text: Final rendered text output
        symbolic: Symbolic layer from Fusion renderer
        practical: Practical layer from Fusion renderer
        mirror: Mirror-truth layer from Fusion renderer
        dha: DHA insights and delivery profile
        routing: TTOR routing plan fields
        mappers: Mapper profile details (HRM/LCM/LAM activation)
        entropy: Entropy measures (H_D, H_G, H_K, normalized)
        coherence: Coherence report from CoherenceObserver
        metadata: Turn number, timestamp, domain, etc.
        session_memory: Session memory v2.0 (episodic events)
        session_recap: Session recap v1.0 (multi-turn summary)
        intent_arc: Intent Arc Engine v1.0 (trajectory classification)
        identity_signature: Identity Signature Engine v1.0 (identity trajectory classification)
        motivation_profile: Motivation Flow Engine v1.0 (motivational driver classification)
        formulas: Phase 2 temporal formulas (SMI, ΔSMI, Bhava Gap, Tension Corridor) - observation only
        trading_guardrails: Phase 7 trading formula guardrails (trading safety risk flags)
        interaction_mode: Phase 15 interaction mode (controls formula influence level)
        insight_window: Phase 32 insight window gating (UCF-based UI-layer policy refinement)
    """

    text: str
    symbolic: Dict[str, Any]
    practical: Dict[str, Any]
    mirror: Dict[str, Any]
    dha: Dict[str, Any]
    routing: Dict[str, Any]
    mappers: Dict[str, Any]
    entropy: Dict[str, float]
    coherence: Dict[str, Any]
    metadata: Dict[str, Any]
    session_memory: Dict[str, Any] = field(default_factory=dict)
    session_recap: Dict[str, Any] = field(default_factory=dict)
    intent_arc: Dict[str, Any] = field(default_factory=dict)
    identity_signature: Dict[str, Any] = field(default_factory=dict)
    motivation_profile: Dict[str, Any] = field(default_factory=dict)
    formulas: Optional[Dict[str, Optional[float]]] = None
    trading_guardrails: Optional[Dict[str, bool]] = None
    interaction_mode: Optional[str] = None  # Phase 15: Active interaction mode
    persona_resonance: Optional[Dict[str, Any]] = None  # Phase 29: Persona resonance profile
    persona_resonance_map: Optional[Dict[str, Any]] = None  # Phase 30: Cross-layer resonance persona map
    insight_window: Optional[Dict[str, Any]] = None  # Phase 32: Insight window gating result
    schema_adaptive_map: Optional[Dict[str, Any]] = None  # Phase 33: Persona schema adaptive routing (observation-only)
    identity_harmonics: Optional[Dict[str, Any]] = None  # Phase 34: Identity harmonics layer (observation-only, tone-level only)
    predictive_persona_drift: Optional[Dict[str, Any]] = None  # Phase 35: Predictive persona drift model (observation-only, tone-level only)
    identity_resonance_memory: Optional[Dict[str, Any]] = None  # Phase 36: Identity resonance memory (observation-only, tone-level only)
    adaptive_continuity: Optional[Dict[str, Any]] = None  # Phase 37: Adaptive continuity engine (observation-only, tone-level only)
    temporal_forecast: Optional[Dict[str, Any]] = None  # Phase 38: Temporal coherence forecasting model (observation-only, tone-level only)
    multi_horizon_forecast: Optional[Dict[str, Any]] = None  # Phase 39: Multi-horizon temporal forecasting engine (observation-only, tone-level only)
    cross_horizon_resonance: Optional[Dict[str, Any]] = None  # Phase 40: Cross-Horizon Resonance Alignment Engine (observation-only, tone-level only)
    coherence_regime: Optional[Dict[str, Any]] = None  # Phase 41: Coherence-Regime Scenario Mapper (observation-only, analytics/UI-only)
    scenario_fusion: Optional[Dict[str, Any]] = None  # Phase 42: Scenario Fusion Engine (observation-only, analytics/UI-only)
    coherence_scenario_alignment: Optional[Dict[str, Any]] = None  # Phase 44: Coherence–Scenario Alignment Engine (observation-only, analytics/UI-only)
    multi_trajectory_stability_field: Optional[Dict[str, Any]] = None  # Phase 45: Multi-Trajectory Stability Field (MTSF) (observation-only, analytics/UI-only)
    trajectory_field_convergence: Optional[Dict[str, Any]] = None  # Phase 46: Trajectory Field Convergence Engine (TFCE) (observation-only, analytics/UI-only)
    unified_trajectory_scenario_synthesis: Optional[Dict[str, Any]] = None  # Phase 47: Unified Trajectory–Scenario Synthesis Engine (UTSSE) (observation-only, analytics/UI-only)
    macro_stability_regulator: Optional[Dict[str, Any]] = None  # Phase 48: Macro-Stability Regulator (MSR) (observation-only, analytics/UI-only)
    temporal_stability: Optional[Dict[str, Any]] = None  # Phase 49: Unified Cross-Phase Temporal Stability Engine (UCTSE) (observation-only, analytics/UI-only)
    cognitive_consistency_regression: Optional[Dict[str, Any]] = None  # Phase 50: Cognitive Consistency Regression Engine (CCRE) (observation-only, analytics/UI-only)
    rag_coherence_validation: Optional[Dict[str, Any]] = None  # Phase 51: RAG Coherence Validation Engine (RCVE) (observation-only, analytics/UI-only)
    cognitive_resonance_aggregator: Optional[Dict[str, Any]] = None  # Phase 51: Cognitive Resonance Aggregator (CRA) (observation-only, analytics/UI-only)
    internal_external_reality_verification: Optional[Dict[str, Any]] = None  # Phase 52: Internal–External Reality Cross-Verification Engine (IER-CVE) (observation-only, analytics/UI-only)
    external_reality_trust: Optional[Dict[str, Any]] = None  # Phase 53: External Reality Trust Calibration Engine (ERTCE) (observation-only, analytics/UI-only)
    action_eligibility: Optional[Dict[str, Any]] = None  # Phase 54: Action Eligibility & Commitment Boundary Engine (AECBE) (observation-only, analytics/UI-only)
    persona_echo_profile: Optional[Dict[str, Any]] = None  # Phase 31: Adaptive Persona Echo Layer (APEL) (observation-only, tone-level only)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to JSON-serializable dictionary.

        Removes None values and ensures all keys are snake_case.

        Returns:
            Clean dictionary with all unified output fields
        """
        result = asdict(self)

        # Remove None values recursively
        return _remove_none_values(result)

    def to_json_string(self) -> str:
        """
        Convert to JSON string.

        Returns:
            JSON string representation
        """
        import json
        return json.dumps(self.to_dict(), indent=2)


def build_unified_output(text: str, ctx: Any) -> UnifiedOutput:
    """
    Build unified output from pipeline context.

    This is the main assembler function that extracts data from all
    pipeline components and creates a unified output structure.

    Args:
        text: Final rendered text
        ctx: PipelineContext with all pipeline results

    Returns:
        UnifiedOutput with complete pipeline data

    Note:
        This function is deterministic and does not modify ctx.
    """
    # Extract symbolic/practical/mirror layers from Fusion renderer
    symbolic_layer = {}
    practical_layer = {}
    mirror_layer = {}

    # Try to extract from fusion result if available
    if hasattr(ctx, 'fusion') and ctx.fusion is not None:
        fusion_result = ctx.fusion.fused_candidates if ctx.fusion else None

        if fusion_result and hasattr(fusion_result, 'to_dict'):
            fusion_dict = fusion_result.to_dict()

            # Extract layers from fusion metadata or explain
            explain = fusion_dict.get('explain', {})
            symbolic_layer = {
                'fusion_score': fusion_dict.get('fusion_score', 0.0),
                'candidate_count': len(fusion_dict.get('ranked_candidates', [])),
                'selected_source': fusion_dict.get('selected_candidate', {}).get('source', 'unknown'),
                'reasoning': explain.get('reasoning', 'No reasoning available'),
            }

            practical_layer = {
                'text': fusion_dict.get('selected_candidate', {}).get('text', text),
                'confidence': fusion_dict.get('selected_candidate', {}).get('confidence', 0.0),
                'relevance_score': fusion_dict.get('selected_candidate', {}).get('relevance_score', 0.0),
            }

            mirror_layer = {
                'routing': fusion_dict.get('routing', {}),
                'metadata': fusion_dict.get('metadata', {}),
            }

    # Extract DHA insights
    dha_insights = {}
    if hasattr(ctx, 'dha') and ctx.dha is not None:
        dha_insights = {
            'delivery_profile': ctx.dha.tone_profile,
            'readiness_level': ctx.dha.readiness_level,
            'resistance_flags': ctx.dha.resistance_flags,
            'safety_flags': ctx.dha.safety_flags,
            'adaptation_notes': ctx.dha.adaptation_notes,
            'adapted_message': ctx.dha.guarded_text,
        }

    # Extract routing plan from MLCR/TTOR
    routing_plan = {}
    if hasattr(ctx, 'mlcr') and ctx.mlcr is not None:
        # Try to extract routing plan from MLCR entries
        mlcr_entries = ctx.mlcr.entries if ctx.mlcr else {}

        if isinstance(mlcr_entries, dict):
            # Check if there's a routing_plan in the activation_plan
            activation_plan = mlcr_entries.get('activation_plan', {})

            routing_plan = {
                'tier': mlcr_entries.get('explain_log', {}).get('meta', {}).get('tier', 'unknown'),
                'intent': mlcr_entries.get('explain_log', {}).get('meta', {}).get('intent', 'unknown'),
                'domain': mlcr_entries.get('explain_log', {}).get('meta', {}).get('domain', 'unknown'),
                'use_hrm': activation_plan.get('use_hrm', False),
                'use_lcm': activation_plan.get('use_lcm', False),
                'use_lam': activation_plan.get('use_lam', False),
                'flow_mode': 'standard',  # Default
            }

    # Extract mapper profile
    mapper_profile = {}
    if hasattr(ctx, 'mapper_profile') and ctx.mapper_profile is not None:
        mapper_profile = ctx.mapper_profile.to_dict()
    else:
        # Default mapper profile
        mapper_profile = {
            'resolution_level': 'medium',
            'arc_mode': 'none',
            'detail_bias': 0.5,
            'practical_bias': 0.5,
            'reflective_bias': 0.5,
        }

    # Extract entropy values
    entropy_values = {}
    if hasattr(ctx, 'mlcr') and ctx.mlcr is not None:
        mlcr_entries = ctx.mlcr.entries if ctx.mlcr else {}
        if isinstance(mlcr_entries, dict):
            entropy_dict = mlcr_entries.get('explain_log', {}).get('entropy', {})
            entropy_values = {
                'H_D': entropy_dict.get('H_D', 0.0),
                'H_G': entropy_dict.get('H_G', 0.0),
                'H_K': entropy_dict.get('H_K', 0.0),
                'normalized_entropy': entropy_dict.get('normalized_entropy', 0.0),
            }

    # Extract coherence report
    coherence_report = {}
    if hasattr(ctx, 'coherence_report') and ctx.coherence_report is not None:
        coherence_report = ctx.coherence_report
    else:
        # Default coherence report
        coherence_report = {
            'coherence_score': 1.0,
            'persona_drift_score': 0.0,
            'semantic_stability_score': 1.0,
            'temporal_arc_score': 1.0,
            'mapper_volatility_score': 0.0,
            'turn_number': 0,
            'tier': 'unknown',
            'domain': 'unknown',
            'active_mappers': [],
        }

    # Phase 11 & 12: Ensure coherence_score_v2, coherence_score_v3, and coherence_v3_quality are included if available
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        coherence_state = ctx.coherence_state
        coherence_score_v2 = getattr(coherence_state, 'coherence_score_v2', None)
        coherence_score_v3 = getattr(coherence_state, 'coherence_score_v3', None)
        coherence_v3_quality = getattr(coherence_state, 'coherence_v3_quality', None)

        if coherence_score_v2 is not None:
            coherence_report['coherence_score_v2'] = coherence_score_v2
        if coherence_score_v3 is not None:
            coherence_report['coherence_score_v3'] = coherence_score_v3
        if coherence_v3_quality is not None:
            coherence_report['coherence_v3_quality'] = coherence_v3_quality

        # Phase 16: Add Formula Fusion Stabilizer metrics
        coherence_fused = getattr(coherence_state, 'coherence_fused', None)
        fusion_stability_weight = getattr(coherence_state, 'fusion_stability_weight', None)
        fusion_inertia_factor = getattr(coherence_state, 'fusion_inertia_factor', None)
        fusion_quality_factor = getattr(coherence_state, 'fusion_quality_factor', None)

        if coherence_fused is not None:
            coherence_report['coherence_fused'] = coherence_fused

        # Add stabilizer diagnostics if any exist
        if fusion_stability_weight is not None or fusion_inertia_factor is not None or fusion_quality_factor is not None:
            stabilizer_diagnostics = {}
            if fusion_stability_weight is not None:
                stabilizer_diagnostics['stability_weight'] = fusion_stability_weight
            if fusion_inertia_factor is not None:
                stabilizer_diagnostics['inertia_factor'] = fusion_inertia_factor
            if fusion_quality_factor is not None:
                stabilizer_diagnostics['quality_factor'] = fusion_quality_factor
            coherence_report['stabilizer'] = stabilizer_diagnostics

        # Phase 17: Add Semantic Integrity & Cognitive Drift v3 metrics
        semantic_integrity_score = getattr(coherence_state, 'semantic_integrity_score', None)
        cognitive_drift_v3 = getattr(coherence_state, 'cognitive_drift_v3', None)

        # Extract detailed component breakdowns from snapshots
        integrity_snapshot = getattr(coherence_state, 'last_semantic_integrity_snapshot', None)
        drift_snapshot = getattr(coherence_state, 'last_cognitive_drift_snapshot', None)

        # Add semantic integrity & drift to coherence report if available
        if semantic_integrity_score is not None or cognitive_drift_v3 is not None:
            semantic_data = {}

            if semantic_integrity_score is not None:
                semantic_data['integrity_score'] = semantic_integrity_score

            if cognitive_drift_v3 is not None:
                semantic_data['cognitive_drift_v3'] = cognitive_drift_v3

            # Add component diagnostics if snapshots exist
            if integrity_snapshot is not None:
                semantic_data['integrity_components'] = {
                    'structural_consistency': getattr(integrity_snapshot, 'structural_consistency', None),
                    'layer_agreement_score': getattr(integrity_snapshot, 'layer_agreement_score', None),
                    'cross_turn_consistency': getattr(integrity_snapshot, 'cross_turn_consistency', None),
                    'mapper_alignment_score': getattr(integrity_snapshot, 'mapper_alignment_score', None),
                    'intent_identity_alignment': getattr(integrity_snapshot, 'intent_identity_alignment', None),
                }

            if drift_snapshot is not None:
                semantic_data['drift_components'] = {
                    'structure_drift': getattr(drift_snapshot, 'structure_drift', None),
                    'topic_drift': getattr(drift_snapshot, 'topic_drift', None),
                    'mapper_drift': getattr(drift_snapshot, 'mapper_drift', None),
                    'intent_identity_drift': getattr(drift_snapshot, 'intent_identity_drift', None),
                }

            coherence_report['semantic'] = semantic_data

        # Phase 18: Add Temporal Entropy Differential metrics
        temporal_entropy_diff = getattr(coherence_state, 'temporal_entropy_diff', None)
        temporal_entropy_volatility = getattr(coherence_state, 'temporal_entropy_volatility', None)

        # Extract detailed component breakdowns from snapshot
        entropy_snapshot = getattr(coherence_state, 'temporal_entropy_snapshot', None)

        # Add temporal entropy to coherence report if available
        if temporal_entropy_diff is not None or temporal_entropy_volatility is not None:
            temporal_entropy_data = {}

            if temporal_entropy_diff is not None:
                temporal_entropy_data['diff'] = temporal_entropy_diff

            if temporal_entropy_volatility is not None:
                temporal_entropy_data['volatility'] = temporal_entropy_volatility

            # Add component diagnostics if snapshot exists
            if entropy_snapshot is not None:
                temporal_entropy_data['details'] = {
                    'instantaneous_entropy': getattr(entropy_snapshot, 'instantaneous_entropy', None),
                    'short_window_entropy': getattr(entropy_snapshot, 'short_window_entropy', None),
                    'long_window_entropy': getattr(entropy_snapshot, 'long_window_entropy', None),
                    'entropy_diff': getattr(entropy_snapshot, 'entropy_diff', None),
                    'normalized_entropy_diff': getattr(entropy_snapshot, 'normalized_entropy_diff', None),
                    'entropy_volatility': getattr(entropy_snapshot, 'entropy_volatility', None),
                }

            coherence_report['temporal_entropy'] = temporal_entropy_data

        # Phase 21: Add Mirror-Time Loop metrics
        loop_alignment = getattr(coherence_state, 'avg_loop_alignment', None)
        loop_tension = getattr(coherence_state, 'avg_loop_tension', None)
        reversal_probability = getattr(coherence_state, 'avg_reversal_probability', None)

        # Extract detailed component breakdowns from snapshot
        loop_snapshot = getattr(coherence_state, 'mirror_time_loop_snapshot', None)

        # Add mirror-time loop to coherence report if available
        if loop_alignment is not None or loop_tension is not None or reversal_probability is not None:
            mirror_time_loop_data = {}

            if loop_alignment is not None:
                mirror_time_loop_data['loop_alignment'] = loop_alignment

            if loop_tension is not None:
                mirror_time_loop_data['loop_tension'] = loop_tension

            if reversal_probability is not None:
                mirror_time_loop_data['reversal_probability'] = reversal_probability

            # Add component diagnostics if snapshot exists
            if loop_snapshot is not None:
                mirror_time_loop_data['details'] = {
                    'forward_vector': getattr(loop_snapshot, 'forward_vector', None),
                    'mirror_vector': getattr(loop_snapshot, 'mirror_vector', None),
                    'loop_delta': getattr(loop_snapshot, 'loop_delta', None),
                    'loop_tension': getattr(loop_snapshot, 'loop_tension', None),
                    'loop_alignment': getattr(loop_snapshot, 'loop_alignment', None),
                    'reversal_probability': getattr(loop_snapshot, 'reversal_probability', None),
                    'stability_band': getattr(loop_snapshot, 'stability_band', None),
                }

            coherence_report['mirror_time_loop'] = mirror_time_loop_data

        # Phase 22: Add Mirror-Time Cycles metrics
        dominant_cycle_type = getattr(coherence_state, 'dominant_cycle_type', None)
        dominant_cycle_stability_band = getattr(coherence_state, 'dominant_cycle_stability_band', None)
        avg_cycle_alignment = getattr(coherence_state, 'avg_cycle_alignment', None)
        avg_cycle_tension = getattr(coherence_state, 'avg_cycle_tension', None)
        avg_cycle_reversal_probability = getattr(coherence_state, 'avg_cycle_reversal_probability', None)

        # Count cycles from mirror_cycle_history
        cycle_count = 0
        mirror_cycle_history = getattr(coherence_state, 'mirror_cycle_history', None)
        if mirror_cycle_history is not None:
            cycle_count = len(mirror_cycle_history)

        # Add mirror-time cycles to coherence report if available
        if dominant_cycle_type is not None or cycle_count > 0:
            mirror_time_cycles_data = {}

            if dominant_cycle_type is not None:
                mirror_time_cycles_data['dominant_type'] = dominant_cycle_type

            if dominant_cycle_stability_band is not None:
                mirror_time_cycles_data['dominant_stability_band'] = dominant_cycle_stability_band

            if cycle_count > 0:
                mirror_time_cycles_data['cycle_count'] = cycle_count

            if avg_cycle_alignment is not None:
                mirror_time_cycles_data['avg_alignment'] = avg_cycle_alignment

            if avg_cycle_tension is not None:
                mirror_time_cycles_data['avg_tension'] = avg_cycle_tension

            if avg_cycle_reversal_probability is not None:
                mirror_time_cycles_data['avg_reversal_probability'] = avg_cycle_reversal_probability

            coherence_report['mirror_time_cycles'] = mirror_time_cycles_data

        # Phase 23: Add Cause-Effect Inversion Analytics metrics
        current_inversion_score = getattr(coherence_state, 'current_inversion_score', None)
        current_inversion_band = getattr(coherence_state, 'current_inversion_band', None)
        avg_inversion_score = getattr(coherence_state, 'avg_inversion_score', None)
        cause_chain_stability_avg = getattr(coherence_state, 'cause_chain_stability_avg', None)

        # Extract detailed snapshot from inversion history
        inversion_history = getattr(coherence_state, 'cause_effect_inversion_history', None)
        latest_inversion_snapshot = None
        if inversion_history and len(inversion_history) > 0:
            latest_inversion_snapshot = inversion_history[-1]

        # Add cause-effect inversion to coherence report if available
        if current_inversion_score is not None or latest_inversion_snapshot is not None:
            cause_effect_inversion_data = {}

            if current_inversion_score is not None:
                cause_effect_inversion_data['inversion_score'] = current_inversion_score

            if current_inversion_band is not None:
                cause_effect_inversion_data['inversion_band'] = current_inversion_band

            if avg_inversion_score is not None:
                cause_effect_inversion_data['avg_inversion_score'] = avg_inversion_score

            if cause_chain_stability_avg is not None:
                cause_effect_inversion_data['avg_cause_chain_stability'] = cause_chain_stability_avg

            # Add detailed breakdown if snapshot exists
            if latest_inversion_snapshot is not None:
                cause_effect_inversion_data['details'] = {
                    'forward_alignment': getattr(latest_inversion_snapshot, 'forward_alignment', None),
                    'mirror_alignment': getattr(latest_inversion_snapshot, 'mirror_alignment', None),
                    'inversion_score': getattr(latest_inversion_snapshot, 'inversion_score', None),
                    'inversion_band': getattr(latest_inversion_snapshot, 'inversion_band', None),
                    'cause_chain_stability': getattr(latest_inversion_snapshot, 'cause_chain_stability', None),
                    'notes': getattr(latest_inversion_snapshot, 'notes', None),
                }

            coherence_report['cause_effect_inversion'] = cause_effect_inversion_data

        # Phase 24: Resonance Weighting Function (observation only - no behavior changes)
        current_resonance_entropy = getattr(coherence_state, 'current_resonance_entropy', None)
        dominant_resonance_metrics = getattr(coherence_state, 'dominant_resonance_metrics', None)
        current_resonance_weights = getattr(coherence_state, 'current_resonance_weights', None)
        current_normalized_resonance_weights = getattr(coherence_state, 'current_normalized_resonance_weights', None)

        # Extract detailed snapshot from resonance weighting history
        weighting_history = getattr(coherence_state, 'resonance_weighting_history', None)
        latest_weighting_snapshot = None
        if weighting_history and len(weighting_history) > 0:
            latest_weighting_snapshot = weighting_history[-1]

        # Add resonance weighting to coherence report if available
        if current_resonance_entropy is not None or latest_weighting_snapshot is not None:
            resonance_weighting_data = {}

            if current_resonance_entropy is not None:
                resonance_weighting_data['entropy'] = current_resonance_entropy

            if dominant_resonance_metrics:
                resonance_weighting_data['dominant_metrics'] = list(dominant_resonance_metrics) if isinstance(dominant_resonance_metrics, list) else []

            if current_resonance_weights:
                resonance_weighting_data['weights'] = current_resonance_weights

            if current_normalized_resonance_weights:
                resonance_weighting_data['normalized_weights'] = current_normalized_resonance_weights

            # Add detailed breakdown if snapshot exists
            if latest_weighting_snapshot is not None:
                resonance_weighting_data['snapshot'] = {
                    'weights': getattr(latest_weighting_snapshot, 'weights', None),
                    'normalized_weights': getattr(latest_weighting_snapshot, 'normalized_weights', None),
                    'entropy_of_weights': getattr(latest_weighting_snapshot, 'entropy_of_weights', None),
                    'dominant_metrics': getattr(latest_weighting_snapshot, 'dominant_metrics', None),
                    'notes': getattr(latest_weighting_snapshot, 'notes', None),
                }

            coherence_report['resonance_weighting'] = resonance_weighting_data

        # Phase 26: Extract Unified Consciousness Formula (UCF) from coherence_state
        current_coi = getattr(coherence_state, 'current_coi', None)
        current_csi = getattr(coherence_state, 'current_csi', None)
        current_cip = getattr(coherence_state, 'current_cip', None)
        ucf_entropy = getattr(coherence_state, 'ucf_entropy', None)
        ucf_notes = getattr(coherence_state, 'ucf_notes', None)

        # Extract detailed snapshot from UCF history
        ucf_history = getattr(coherence_state, 'ucf_history', None)
        latest_ucf_snapshot = None
        if ucf_history and len(ucf_history) > 0:
            latest_ucf_snapshot = ucf_history[-1]

        # Add unified consciousness to coherence report if available
        if current_coi is not None or current_csi is not None or current_cip is not None or latest_ucf_snapshot is not None:
            unified_consciousness_data = {}

            # Core indices
            if current_coi is not None:
                unified_consciousness_data['consciousness_order_index'] = current_coi
                unified_consciousness_data['coi'] = current_coi  # Alias

            if current_csi is not None:
                unified_consciousness_data['consciousness_stability_index'] = current_csi
                unified_consciousness_data['csi'] = current_csi  # Alias

            if current_cip is not None:
                unified_consciousness_data['consciousness_integration_potential'] = current_cip
                unified_consciousness_data['cip'] = current_cip  # Alias

            # UCF entropy
            if ucf_entropy is not None:
                unified_consciousness_data['entropy'] = ucf_entropy

            # UCF diagnostic notes
            if ucf_notes:
                unified_consciousness_data['notes'] = list(ucf_notes) if isinstance(ucf_notes, list) else []

            # Add detailed breakdown if snapshot exists
            if latest_ucf_snapshot is not None:
                unified_consciousness_data['snapshot'] = {
                    'consciousness_order_index': getattr(latest_ucf_snapshot, 'consciousness_order_index', None),
                    'consciousness_stability_index': getattr(latest_ucf_snapshot, 'consciousness_stability_index', None),
                    'consciousness_integration_potential': getattr(latest_ucf_snapshot, 'consciousness_integration_potential', None),
                    'weighted_component_breakdown': getattr(latest_ucf_snapshot, 'weighted_component_breakdown', None),
                    'normalized_weights': getattr(latest_ucf_snapshot, 'normalized_weights', None),
                    'entropy_of_weights': getattr(latest_ucf_snapshot, 'entropy_of_weights', None),
                    'diagnostic_notes': getattr(latest_ucf_snapshot, 'diagnostic_notes', None),
                }

            coherence_report['unified_consciousness'] = unified_consciousness_data

        # Phase 27: Extract Symbolic Harmonization Formula (SHF) from coherence_state
        current_shi = getattr(coherence_state, 'current_symbolic_harmonization_index', None)
        shf_snapshot = getattr(coherence_state, 'symbolic_harmonization_snapshot', None)

        # Add symbolic harmonization to coherence report if available
        if current_shi is not None or shf_snapshot is not None:
            symbolic_harmonization_data = {}

            # Symbolic Harmonization Index (SHI)
            if current_shi is not None:
                symbolic_harmonization_data['index'] = current_shi
                symbolic_harmonization_data['symbolic_harmonization_index'] = current_shi  # Explicit

            # Add detailed breakdown if snapshot exists
            if shf_snapshot is not None:
                # Extract component alignments
                symbolic_alignment = getattr(shf_snapshot, 'symbolic_alignment', None)
                mirror_alignment = getattr(shf_snapshot, 'mirror_alignment', None)
                guna_symbolic_resonance = getattr(shf_snapshot, 'guna_symbolic_resonance', None)
                kosha_symbolic_resonance = getattr(shf_snapshot, 'kosha_symbolic_resonance', None)
                semantic_integrity_weight = getattr(shf_snapshot, 'semantic_integrity_weight', None)
                harmonization_entropy = getattr(shf_snapshot, 'harmonization_entropy', None)
                notes = getattr(shf_snapshot, 'notes', None)

                if symbolic_alignment is not None:
                    symbolic_harmonization_data['symbolic_alignment'] = symbolic_alignment
                if mirror_alignment is not None:
                    symbolic_harmonization_data['mirror_alignment'] = mirror_alignment
                if guna_symbolic_resonance is not None:
                    symbolic_harmonization_data['guna_symbolic_resonance'] = guna_symbolic_resonance
                if kosha_symbolic_resonance is not None:
                    symbolic_harmonization_data['kosha_symbolic_resonance'] = kosha_symbolic_resonance
                if semantic_integrity_weight is not None:
                    symbolic_harmonization_data['semantic_integrity_weight'] = semantic_integrity_weight
                if harmonization_entropy is not None:
                    symbolic_harmonization_data['entropy'] = harmonization_entropy
                if notes:
                    symbolic_harmonization_data['notes'] = list(notes) if isinstance(notes, list) else []

                # Add full snapshot for detailed analysis
                symbolic_harmonization_data['snapshot'] = {
                    'symbolic_alignment': symbolic_alignment,
                    'mirror_alignment': mirror_alignment,
                    'guna_symbolic_resonance': guna_symbolic_resonance,
                    'kosha_symbolic_resonance': kosha_symbolic_resonance,
                    'semantic_integrity_weight': semantic_integrity_weight,
                    'symbolic_harmonization_index': getattr(shf_snapshot, 'symbolic_harmonization_index', None),
                    'harmonization_entropy': harmonization_entropy,
                    'notes': notes if notes else [],
                }

            coherence_report['symbolic_harmonization'] = symbolic_harmonization_data

    # Build metadata
    metadata = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'turn_index': coherence_report.get('turn_number', 0),
        'domain': routing_plan.get('domain', 'unknown'),
        'api_version': 'USU-API-v1.0',
        'pipeline_version': '3.0',
    }

    # Add user_id if available
    if hasattr(ctx, 'request') and ctx.request is not None:
        metadata['user_id'] = ctx.request.user_id

    # Phase 20: Add optional dashboard-ready bands to metadata
    # This does NOT affect policy flags or behavior - purely informational
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        coherence_state = ctx.coherence_state
        coherence_fused = getattr(coherence_state, 'coherence_fused', None)
        entropy_volatility = getattr(coherence_state, 'temporal_entropy_volatility', None)
        semantic_integrity_score = getattr(coherence_state, 'semantic_integrity_score', None)
        cognitive_drift_v3 = getattr(coherence_state, 'cognitive_drift_v3', None)

        # Compute dashboard bands (deterministic, observation-only)
        bands = {}

        # Stability band
        if coherence_fused is not None and entropy_volatility is not None:
            if coherence_fused >= 0.65 and entropy_volatility <= 0.35:
                bands['stability_band'] = 'stable'
            elif coherence_fused < 0.45 or entropy_volatility > 0.65:
                bands['stability_band'] = 'unstable'
            else:
                bands['stability_band'] = 'transition'

        # Drift band
        if cognitive_drift_v3 is not None:
            if cognitive_drift_v3 <= 0.35:
                bands['drift_band'] = 'low'
            elif cognitive_drift_v3 <= 0.65:
                bands['drift_band'] = 'moderate'
            else:
                bands['drift_band'] = 'high'

        # Semantic band
        if semantic_integrity_score is not None and cognitive_drift_v3 is not None:
            if semantic_integrity_score >= 0.70 and cognitive_drift_v3 <= 0.35:
                bands['semantic_band'] = 'coherent'
            elif semantic_integrity_score < 0.45 or cognitive_drift_v3 > 0.65:
                bands['semantic_band'] = 'fragile'
            else:
                bands['semantic_band'] = 'mixed'

        # Add motivation band if available from context
        if hasattr(ctx, 'motivation_profile') and ctx.motivation_profile is not None:
            motivation_data = ctx.motivation_profile.serialize()
            motivation_type = motivation_data.get('motivation_type')
            if motivation_type:
                motivation_lower = motivation_type.lower()
                if any(kw in motivation_lower for kw in ['fear', 'avoidance', 'overcorrection']):
                    bands['motivation_band'] = 'defensive'
                elif any(kw in motivation_lower for kw in ['hope', 'expansion', 'stabilization']):
                    bands['motivation_band'] = 'expansive'
                elif 'assertion' in motivation_lower:
                    bands['motivation_band'] = 'assertive'

        # Add bands to metadata if any were computed
        if bands:
            metadata['bands'] = bands
            metadata['dashboard_ready'] = True
        else:
            metadata['dashboard_ready'] = False
    else:
        metadata['dashboard_ready'] = False

    # Extract session memory (Memory v2.0)
    session_memory_data = {}
    if hasattr(ctx, 'session_memory') and ctx.session_memory is not None:
        session_memory_data = ctx.session_memory.serialize()

    # Extract session recap (Session Summarizer v1.0)
    session_recap_data = {}
    if hasattr(ctx, 'session_recap') and ctx.session_recap is not None:
        session_recap_data = ctx.session_recap.serialize()

    # Extract intent arc (Intent Arc Engine v1.0)
    intent_arc_data = {}
    if hasattr(ctx, 'intent_arc') and ctx.intent_arc is not None:
        intent_arc_data = ctx.intent_arc.serialize()

    # Extract identity signature (Identity Signature Engine v1.0)
    identity_signature_data = {}
    if hasattr(ctx, 'identity_signature') and ctx.identity_signature is not None:
        identity_signature_data = ctx.identity_signature.serialize()

    # Extract motivation profile (Motivation Flow Engine v1.0)
    motivation_profile_data = {}
    if hasattr(ctx, 'motivation_profile') and ctx.motivation_profile is not None:
        motivation_profile_data = ctx.motivation_profile.serialize()

    # Phase 7: Extract trading guardrails (Trading Formula Guardrails v1.0)
    trading_guardrails_data = None
    if hasattr(ctx, 'trading_guardrails') and ctx.trading_guardrails is not None:
        trading_guardrails_data = ctx.trading_guardrails.to_dict()

    # Phase 2 & 3: Extract formulas from coherence state or pipeline context
    formulas_data = None
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        coherence_state = ctx.coherence_state
        formulas_data = {}

        # Get most recent values from histories
        delta_smi_hist = getattr(coherence_state, 'delta_smi_history', [])
        if delta_smi_hist and delta_smi_hist[-1] is not None:
            formulas_data["delta_smi"] = delta_smi_hist[-1]

        bhava_gap_hist = getattr(coherence_state, 'bhava_gap_history', [])
        if bhava_gap_hist and bhava_gap_hist[-1] is not None:
            formulas_data["bhava_gap"] = bhava_gap_hist[-1]

        tension_corridor_hist = getattr(coherence_state, 'tension_corridor_history', [])
        if tension_corridor_hist and tension_corridor_hist[-1] is not None:
            formulas_data["tension_corridor"] = tension_corridor_hist[-1]

        # Get aggregates
        avg_smi = getattr(coherence_state, 'avg_smi', None)
        if avg_smi is not None:
            formulas_data["avg_smi"] = avg_smi

        max_smi = getattr(coherence_state, 'max_smi', None)
        if max_smi is not None:
            formulas_data["max_smi"] = max_smi

        min_smi = getattr(coherence_state, 'min_smi', None)
        if min_smi is not None:
            formulas_data["min_smi"] = min_smi

        avg_tension_corridor = getattr(coherence_state, 'avg_tension_corridor', None)
        if avg_tension_corridor is not None:
            formulas_data["avg_tension_corridor"] = avg_tension_corridor

        max_tension_corridor = getattr(coherence_state, 'max_tension_corridor', None)
        if max_tension_corridor is not None:
            formulas_data["max_tension_corridor"] = max_tension_corridor

        # Get current SMI from smi_history
        smi_hist = getattr(coherence_state, 'smi_history', [])
        if smi_hist and smi_hist[-1] is not None:
            formulas_data["smi"] = smi_hist[-1]

        # Phase 3: Extract derived metrics
        resonance_index = getattr(coherence_state, 'resonance_index', None)
        tension_index = getattr(coherence_state, 'tension_index', None)
        arc_alignment_index = getattr(coherence_state, 'arc_alignment_index', None)

        # Add derived metrics to formulas dict if any exist
        if resonance_index is not None or tension_index is not None or arc_alignment_index is not None:
            derived = {}
            if resonance_index is not None:
                derived["resonance_index"] = resonance_index
            if tension_index is not None:
                derived["tension_index"] = tension_index
            if arc_alignment_index is not None:
                derived["arc_alignment_index"] = arc_alignment_index
            formulas_data["derived"] = derived

        # Phase 8: Extract Guna/Kosha resonance metrics
        guna_resonance_index = getattr(coherence_state, 'guna_resonance_index', None)
        kosha_resonance_index = getattr(coherence_state, 'kosha_resonance_index', None)
        kosha_activation_vector = getattr(coherence_state, 'kosha_activation_vector', None)

        # Add Guna/Kosha metrics to formulas dict if any exist
        if guna_resonance_index is not None or kosha_resonance_index is not None:
            if guna_resonance_index is not None:
                formulas_data["guna_resonance_index"] = guna_resonance_index
            if kosha_resonance_index is not None:
                formulas_data["kosha_resonance_index"] = kosha_resonance_index
            if kosha_activation_vector is not None:
                formulas_data["kosha_activation_vector"] = kosha_activation_vector

        # Phase 14: Extract Vritti Momentum & Arc-Tension Harmonizer
        # Get most recent values from histories
        vmf_hist = getattr(coherence_state, 'vritti_momentum_history', [])
        if vmf_hist and vmf_hist[-1] is not None:
            formulas_data["vritti_momentum"] = vmf_hist[-1]

        ath_hist = getattr(coherence_state, 'arc_tension_harmonizer_history', [])
        if ath_hist and ath_hist[-1] is not None:
            formulas_data["arc_tension_harmonizer"] = ath_hist[-1]

        # Get Phase 14 aggregates
        avg_vritti_momentum = getattr(coherence_state, 'avg_vritti_momentum', None)
        if avg_vritti_momentum is not None:
            formulas_data["avg_vritti_momentum"] = avg_vritti_momentum

        max_vritti_momentum = getattr(coherence_state, 'max_vritti_momentum', None)
        if max_vritti_momentum is not None:
            formulas_data["max_vritti_momentum"] = max_vritti_momentum

        min_vritti_momentum = getattr(coherence_state, 'min_vritti_momentum', None)
        if min_vritti_momentum is not None:
            formulas_data["min_vritti_momentum"] = min_vritti_momentum

        avg_arc_tension_harmonizer = getattr(coherence_state, 'avg_arc_tension_harmonizer', None)
        if avg_arc_tension_harmonizer is not None:
            formulas_data["avg_arc_tension_harmonizer"] = avg_arc_tension_harmonizer

        max_arc_tension_harmonizer = getattr(coherence_state, 'max_arc_tension_harmonizer', None)
        if max_arc_tension_harmonizer is not None:
            formulas_data["max_arc_tension_harmonizer"] = max_arc_tension_harmonizer

        min_arc_tension_harmonizer = getattr(coherence_state, 'min_arc_tension_harmonizer', None)
        if min_arc_tension_harmonizer is not None:
            formulas_data["min_arc_tension_harmonizer"] = min_arc_tension_harmonizer

        # Phase 21: Extract Mirror-Time Loop metrics
        # Get most recent values from snapshot
        loop_snapshot = getattr(coherence_state, 'mirror_time_loop_snapshot', None)
        if loop_snapshot is not None:
            mirror_time_loop_dict = {
                'forward_vector': getattr(loop_snapshot, 'forward_vector', None),
                'mirror_vector': getattr(loop_snapshot, 'mirror_vector', None),
                'loop_delta': getattr(loop_snapshot, 'loop_delta', None),
                'loop_tension': getattr(loop_snapshot, 'loop_tension', None),
                'loop_alignment': getattr(loop_snapshot, 'loop_alignment', None),
                'reversal_probability': getattr(loop_snapshot, 'reversal_probability', None),
                'stability_band': getattr(loop_snapshot, 'stability_band', None),
            }
            formulas_data["mirror_time_loop"] = mirror_time_loop_dict

        # Get Phase 21 aggregates
        avg_loop_alignment = getattr(coherence_state, 'avg_loop_alignment', None)
        if avg_loop_alignment is not None:
            formulas_data["avg_loop_alignment"] = avg_loop_alignment

        avg_loop_tension = getattr(coherence_state, 'avg_loop_tension', None)
        if avg_loop_tension is not None:
            formulas_data["avg_loop_tension"] = avg_loop_tension

        avg_reversal_probability = getattr(coherence_state, 'avg_reversal_probability', None)
        if avg_reversal_probability is not None:
            formulas_data["avg_reversal_probability"] = avg_reversal_probability

    # Phase 15: Extract interaction mode from policy flags or context
    interaction_mode_data = None
    if hasattr(ctx, 'policy_flags') and ctx.policy_flags is not None:
        interaction_mode_data = ctx.policy_flags.get('interaction_mode')
    elif hasattr(ctx, 'interaction_mode') and ctx.interaction_mode is not None:
        interaction_mode_data = ctx.interaction_mode

    # Phase 32: Extract insight window gating result from policy flags
    insight_window_data = None
    if hasattr(ctx, 'policy_flags') and ctx.policy_flags is not None:
        insight_window_data = ctx.policy_flags.get('insight_window')

    # Phase 29: Extract persona resonance from persona response
    persona_resonance_data = None
    if hasattr(ctx, 'persona_response') and ctx.persona_response is not None:
        # Try to extract persona_resonance from PersonaResponse
        persona_resonance = getattr(ctx.persona_response, 'persona_resonance', None)
        if persona_resonance is not None:
            # Serialize PersonaResonanceProfile to dict
            if hasattr(persona_resonance, 'model_dump'):
                # Pydantic v2 style (new method name)
                persona_resonance_data = persona_resonance.model_dump()
            elif hasattr(persona_resonance, 'dict'):
                # Pydantic v1 style (deprecated in v2)
                persona_resonance_data = persona_resonance.dict()
            elif hasattr(persona_resonance, '__dict__'):
                # Fallback to dict conversion
                persona_resonance_data = dict(persona_resonance.__dict__)

    # Phase 30: Extract cross-layer resonance map from persona response
    persona_resonance_map_data = None
    if hasattr(ctx, 'persona_response') and ctx.persona_response is not None:
        # Try to extract cross_layer_resonance_map from PersonaResponse
        cl_resonance_map = getattr(ctx.persona_response, 'cross_layer_resonance_map', None)
        if cl_resonance_map is not None:
            # Serialize CrossLayerResonanceMap to dict
            if hasattr(cl_resonance_map, 'to_dict'):
                # Use custom to_dict method
                persona_resonance_map_data = cl_resonance_map.to_dict()
            elif hasattr(cl_resonance_map, 'model_dump'):
                # Pydantic v2 style (new method name)
                persona_resonance_map_data = cl_resonance_map.model_dump()
            elif hasattr(cl_resonance_map, 'dict'):
                # Pydantic v1 style (deprecated in v2)
                persona_resonance_map_data = cl_resonance_map.dict()
            elif hasattr(cl_resonance_map, '__dict__'):
                # Fallback to dict conversion
                persona_resonance_map_data = dict(cl_resonance_map.__dict__)

    # Phase 33: Extract persona schema adaptive routing map from persona response
    schema_adaptive_map_data = None
    if hasattr(ctx, 'persona_response') and ctx.persona_response is not None:
        # Try to extract schema_adaptive_map from PersonaResponse
        schema_adaptive_map = getattr(ctx.persona_response, 'schema_adaptive_map', None)
        if schema_adaptive_map is not None:
            # Serialize SchemaAdaptiveRoutingSnapshot to dict
            if hasattr(schema_adaptive_map, 'to_dict'):
                # Use custom to_dict method
                schema_adaptive_map_data = schema_adaptive_map.to_dict()
            elif hasattr(schema_adaptive_map, 'model_dump'):
                # Pydantic v2 style (new method name)
                schema_adaptive_map_data = schema_adaptive_map.model_dump()
            elif hasattr(schema_adaptive_map, 'dict'):
                # Pydantic v1 style (deprecated in v2)
                schema_adaptive_map_data = schema_adaptive_map.dict()
            elif hasattr(schema_adaptive_map, '__dict__'):
                # Fallback to dict conversion
                schema_adaptive_map_data = dict(schema_adaptive_map.__dict__)

    # Phase 34: Extract identity harmonics profile from persona response
    identity_harmonics_data = None
    if hasattr(ctx, 'persona_response') and ctx.persona_response is not None:
        # Try to extract identity_harmonics_profile from PersonaResponse
        identity_harmonics_profile = getattr(ctx.persona_response, 'identity_harmonics_profile', None)
        if identity_harmonics_profile is not None:
            # Identity harmonics profile is already a dict from persona engine
            # Just pass it through (JSON-safe)
            identity_harmonics_data = identity_harmonics_profile

    # Also try to extract from coherence block for observability
    if identity_harmonics_data is None and hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        ihl_snapshot = getattr(ctx.coherence_state, 'identity_harmonics_snapshot', None)
        if ihl_snapshot is not None:
            # Build dict from snapshot fields
            identity_harmonics_data = {
                "cih": getattr(ihl_snapshot, 'core_identity_harmonic', None),
                "aih": getattr(ihl_snapshot, 'adaptive_identity_harmonic', None),
                "rih": getattr(ihl_snapshot, 'relational_identity_harmonic', None),
                "ihi": getattr(ihl_snapshot, 'identity_harmonics_index', None),
                "identity_stability_score": getattr(ihl_snapshot, 'identity_stability_score', None),
                "identity_flexibility_score": getattr(ihl_snapshot, 'identity_flexibility_score', None),
                "notes": getattr(ihl_snapshot, 'notes', []),
            }

    # Phase 35: Extract predictive persona drift profile from persona response
    predictive_drift_data = None
    if hasattr(ctx, 'persona_response') and ctx.persona_response is not None:
        # Try to extract predictive_drift_profile from PersonaResponse
        predictive_drift_profile = getattr(ctx.persona_response, 'predictive_drift_profile', None)
        if predictive_drift_profile is not None:
            # Predictive drift profile is already a dict from persona engine
            # Just pass it through (JSON-safe)
            predictive_drift_data = predictive_drift_profile

    # Also try to extract from coherence block for observability
    if predictive_drift_data is None and hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        ppdm_snapshot = getattr(ctx.coherence_state, 'predictive_drift_snapshot', None)
        if ppdm_snapshot is not None:
            # Build dict from snapshot fields
            drift_direction_scores = getattr(ppdm_snapshot, 'drift_direction_scores', {})
            predictive_drift_data = {
                "magnitude": getattr(ppdm_snapshot, 'drift_magnitude_prediction', None),
                "direction": drift_direction_scores,
                "stability": getattr(ppdm_snapshot, 'drift_stability_score', None),
                "band": getattr(ppdm_snapshot, 'drift_likelihood_band', None),
                "tags": getattr(ppdm_snapshot, 'notes', []),
            }

    # Phase 36: Extract identity resonance memory profile from persona response
    irm_data = None
    if hasattr(ctx, 'persona_response') and ctx.persona_response is not None:
        # Try to extract identity_resonance_memory_profile from PersonaResponse
        irm_profile = getattr(ctx.persona_response, 'identity_resonance_memory_profile', None)
        if irm_profile is not None:
            # IRM profile is already a dict from persona engine
            # Just pass it through (JSON-safe)
            irm_data = irm_profile

    # Also try to extract from coherence block for observability
    if irm_data is None and hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        irm_snapshot = getattr(ctx.coherence_state, 'identity_resonance_memory_snapshot', None)
        if irm_snapshot is not None:
            # Build dict from snapshot fields
            irm_data = {
                "ims": getattr(irm_snapshot, 'identity_memory_strength', None),
                "iep": getattr(irm_snapshot, 'identity_echo_persistence', None),
                "ida": getattr(irm_snapshot, 'identity_drift_anchoring', None),
                "band": getattr(irm_snapshot, 'memory_band', None),
                "tags": getattr(irm_snapshot, 'diagnostic_tags', []),
            }

    # Phase 37: Extract adaptive continuity engine data (observation-only)
    ace_data = None
    # Try to extract from persona response first (if available)
    if hasattr(ctx, 'persona_response') and ctx.persona_response is not None:
        continuity_profile = getattr(ctx.persona_response, 'continuity_profile', None)
        if continuity_profile is not None:
            ace_data = continuity_profile

    # Also try to extract from coherence block for observability
    if ace_data is None and hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        ace_snapshot = getattr(ctx.coherence_state, 'adaptive_continuity_snapshot', None)
        if ace_snapshot is not None:
            # Build dict from snapshot fields
            ace_data = {
                "ncc": getattr(ace_snapshot, 'ncc', None),
                "icc": getattr(ace_snapshot, 'icc', None),
                "css": getattr(ace_snapshot, 'css', None),
                "band": getattr(ace_snapshot, 'continuity_band', None),
                "tags": getattr(ace_snapshot, 'continuity_tags', []),
            }

    # Phase 38: Extract temporal coherence forecasting model data (observation-only)
    tcfm_data = None
    # Try to extract from persona response first (if available)
    if hasattr(ctx, 'persona_response') and ctx.persona_response is not None:
        forecast_profile = getattr(ctx.persona_response, 'temporal_forecast_profile', None)
        if forecast_profile is not None:
            tcfm_data = forecast_profile

    # Also try to extract from coherence block for observability
    if tcfm_data is None and hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        forecast_snapshot = getattr(ctx.coherence_state, 'temporal_forecast_snapshot', None)
        if forecast_snapshot is not None:
            # Build dict from snapshot fields
            tcfm_data = {
                "coherence_slope": getattr(forecast_snapshot, 'coherence_slope', None),
                "continuity_slope": getattr(forecast_snapshot, 'continuity_slope', None),
                "drift_influence": getattr(forecast_snapshot, 'drift_influence', None),
                "entropy_forward_risk": getattr(forecast_snapshot, 'entropy_forward_risk', None),
                "forecast_strength": getattr(forecast_snapshot, 'forecast_strength', None),
                "forecast_band": getattr(forecast_snapshot, 'forecast_band', None),
                "diagnostic_tags": getattr(forecast_snapshot, 'diagnostic_tags', []),
            }

    # Phase 39: Extract multi-horizon temporal forecasting engine data (observation-only)
    mhtfe_data = None
    # Try to extract from persona response first (if available)
    if hasattr(ctx, 'persona_response') and ctx.persona_response is not None:
        mh_forecast_profile = getattr(ctx.persona_response, 'multi_horizon_forecast_profile', None)
        if mh_forecast_profile is not None:
            mhtfe_data = mh_forecast_profile

    # Also try to extract from coherence state for observability
    if mhtfe_data is None and hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        mh_forecast_snapshot = getattr(ctx.coherence_state, 'multi_horizon_forecast_snapshot', None)
        if mh_forecast_snapshot is not None:
            # Build dict from snapshot fields
            mhtfe_data = {
                "horizons": {
                    "h1": {
                        "coherence_slope": getattr(mh_forecast_snapshot.h1_forecast, 'coherence_slope', None),
                        "continuity_slope": getattr(mh_forecast_snapshot.h1_forecast, 'continuity_slope', None),
                        "drift_risk": getattr(mh_forecast_snapshot.h1_forecast, 'drift_risk', None),
                        "entropy_risk": getattr(mh_forecast_snapshot.h1_forecast, 'entropy_risk', None),
                        "forecast_strength": getattr(mh_forecast_snapshot.h1_forecast, 'forecast_strength', None),
                        "forecast_band": getattr(mh_forecast_snapshot.h1_forecast, 'forecast_band', None),
                    },
                    "h2": {
                        "coherence_slope": getattr(mh_forecast_snapshot.h2_forecast, 'coherence_slope', None),
                        "continuity_slope": getattr(mh_forecast_snapshot.h2_forecast, 'continuity_slope', None),
                        "drift_risk": getattr(mh_forecast_snapshot.h2_forecast, 'drift_risk', None),
                        "entropy_risk": getattr(mh_forecast_snapshot.h2_forecast, 'entropy_risk', None),
                        "forecast_strength": getattr(mh_forecast_snapshot.h2_forecast, 'forecast_strength', None),
                        "forecast_band": getattr(mh_forecast_snapshot.h2_forecast, 'forecast_band', None),
                    },
                    "h3": {
                        "coherence_slope": getattr(mh_forecast_snapshot.h3_forecast, 'coherence_slope', None),
                        "continuity_slope": getattr(mh_forecast_snapshot.h3_forecast, 'continuity_slope', None),
                        "drift_risk": getattr(mh_forecast_snapshot.h3_forecast, 'drift_risk', None),
                        "entropy_risk": getattr(mh_forecast_snapshot.h3_forecast, 'entropy_risk', None),
                        "forecast_strength": getattr(mh_forecast_snapshot.h3_forecast, 'forecast_strength', None),
                        "forecast_band": getattr(mh_forecast_snapshot.h3_forecast, 'forecast_band', None),
                    },
                },
                "forecast_consensus_index": getattr(mh_forecast_snapshot, 'forecast_consensus_index', None),
                "future_stability_envelope": getattr(mh_forecast_snapshot, 'future_stability_envelope', None),
                "diagnostic_tags": getattr(mh_forecast_snapshot, 'diagnostic_tags', []),
            }

    # Phase 40: Extract cross-horizon resonance alignment engine data (observation-only)
    chra_data = None
    # Try to extract from persona response first (if available)
    if hasattr(ctx, 'persona_response') and ctx.persona_response is not None:
        chra_profile = getattr(ctx.persona_response, 'cross_horizon_resonance_profile', None)
        if chra_profile is not None:
            chra_data = chra_profile

    # Also try to extract from coherence state for observability
    if chra_data is None and hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        chra_snapshot = getattr(ctx.coherence_state, 'cross_horizon_resonance_snapshot', None)
        if chra_snapshot is not None:
            # Build dict from snapshot fields
            chra_data = {
                "has": {
                    "H1": getattr(chra_snapshot, 'has_H1', None),
                    "H2": getattr(chra_snapshot, 'has_H2', None),
                    "H3": getattr(chra_snapshot, 'has_H3', None),
                },
                "rai": getattr(chra_snapshot, 'rai', None),
                "ifa": getattr(chra_snapshot, 'ifa', None),
                "dft": getattr(chra_snapshot, 'dft', None),
                "alignment_band": getattr(chra_snapshot, 'alignment_band', None),
                "diagnostic_tags": getattr(chra_snapshot, 'diagnostic_tags', []),
            }

    # Phase 41: Extract coherence-regime scenario mapper data (observation-only, analytics/UI-only)
    regime_data = None
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        regime_snapshot = getattr(ctx.coherence_state, 'coherence_regime_snapshot', None)
        if regime_snapshot is not None:
            # Build dict from snapshot fields
            regime_data = {
                "dominant_regime": getattr(regime_snapshot, 'dominant_regime', None),
                "band": getattr(regime_snapshot, 'regime_band', None),
                "scores": getattr(regime_snapshot, 'regime_scores', {}),
                "tags": getattr(regime_snapshot, 'diagnostic_tags', []),
            }

    # Phase 42: Extract scenario fusion engine data (observation-only, analytics/UI-only)
    scenario_fusion_data = None
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        scenario_fusion_snapshot = getattr(ctx.coherence_state, 'scenario_fusion_snapshot', None)
        if scenario_fusion_snapshot is not None:
            # Build dict from snapshot fields
            scenario_fusion_data = {
                "alignment": getattr(scenario_fusion_snapshot, 'scenario_alignment_score', None),
                "divergence": getattr(scenario_fusion_snapshot, 'scenario_divergence_index', None),
                "consensus": getattr(scenario_fusion_snapshot, 'multi_regime_consensus', None),
                "uncertainty_band": getattr(scenario_fusion_snapshot, 'future_uncertainty_band', None),
                "dominant_future_path": getattr(scenario_fusion_snapshot, 'dominant_future_path', None),
                "tags": getattr(scenario_fusion_snapshot, 'diagnostic_tags', []),
            }

    # Phase 44: Extract coherence-scenario alignment engine data (observation-only, analytics/UI-only)
    csae_data = None
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        csae_snapshot = getattr(ctx.coherence_state, 'scenario_alignment_snapshot', None)
        if csae_snapshot is not None:
            # Build dict from snapshot fields
            csae_data = {
                "alignment_score": getattr(csae_snapshot, 'alignment_score', None),
                "conflict_index": getattr(csae_snapshot, 'conflict_index', None),
                "stability_agreement": getattr(csae_snapshot, 'stability_agreement', None),
                "alignment_band": getattr(csae_snapshot, 'overall_alignment_band', None),
                "diagnostic_tags": getattr(csae_snapshot, 'diagnostic_tags', []),
            }

    # Phase 45: Extract multi-trajectory stability field (MTSF) data (observation-only, analytics/UI-only)
    mtsf_data = None
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        mtsf_snapshot = getattr(ctx.coherence_state, 'mtsf_snapshot', None)
        if mtsf_snapshot is not None:
            # Build dict from snapshot fields
            mtsf_data = {
                "tsi": getattr(mtsf_snapshot, 'tsi', 0.0),
                "tvi": getattr(mtsf_snapshot, 'tvi', 0.0),
                "chf": getattr(mtsf_snapshot, 'chf', 0.0),
                "scc": getattr(mtsf_snapshot, 'scc', 0.0),
                "band": getattr(mtsf_snapshot, 'band', None),
                "tags": getattr(mtsf_snapshot, 'tags', []),
            }

    # Phase 46: Extract trajectory field convergence engine (TFCE) data (observation-only, analytics/UI-only)
    tfce_data = None
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        tfce_snapshot = getattr(ctx.coherence_state, 'trajectory_convergence_snapshot', None)
        if tfce_snapshot is not None:
            # Build dict from snapshot fields
            tfce_data = {
                "drift_alignment": getattr(tfce_snapshot, 'drift_alignment', None),
                "identity_alignment": getattr(tfce_snapshot, 'identity_alignment', None),
                "symbolic_alignment": getattr(tfce_snapshot, 'symbolic_alignment', None),
                "continuity_alignment": getattr(tfce_snapshot, 'continuity_alignment', None),
                "scenario_alignment": getattr(tfce_snapshot, 'scenario_alignment', None),
                "horizon_alignment": getattr(tfce_snapshot, 'horizon_alignment', None),
                "convergence_index": getattr(tfce_snapshot, 'convergence_index', 0.0),
                "divergence_index": getattr(tfce_snapshot, 'divergence_index', 0.0),
                "stability_index": getattr(tfce_snapshot, 'stability_index', 0.0),
                "convergence_band": getattr(tfce_snapshot, 'convergence_band', None),
                "dominant_convergence_signal": getattr(tfce_snapshot, 'dominant_convergence_signal', None),
                "diagnostic_tags": getattr(tfce_snapshot, 'diagnostic_tags', []),
            }

    # Phase 47: Extract unified trajectory–scenario synthesis engine (UTSSE) data (observation-only, analytics/UI-only)
    utsse_data = None
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        utsse_snapshot = getattr(ctx.coherence_state, 'trajectory_scenario_synthesis_snapshot', None)
        if utsse_snapshot is not None:
            # Build dict from snapshot fields
            utsse_data = {
                "synthesis_integrity_score": getattr(utsse_snapshot, 'synthesis_integrity_score', 0.0),
                "future_state_alignment_score": getattr(utsse_snapshot, 'future_state_alignment_score', 0.0),
                "future_state_coherence_score": getattr(utsse_snapshot, 'future_state_coherence_score', 0.0),
                "cross_horizon_consistency_score": getattr(utsse_snapshot, 'cross_horizon_consistency_score', 0.0),
                "future_divergence_risk": getattr(utsse_snapshot, 'future_divergence_risk', 0.0),
                "convergence_signal_strength": getattr(utsse_snapshot, 'convergence_signal_strength', 0.0),
                "dominant_future_path": getattr(utsse_snapshot, 'dominant_future_path', None),
                "synthesis_band": getattr(utsse_snapshot, 'synthesis_band', None),
                "diagnostic_tags": getattr(utsse_snapshot, 'diagnostic_tags', []),
            }

    # Phase 48: Extract Macro-Stability Regulator (MSR) data (observation-only, analytics/UI-only)
    msr_data = None
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        msr_snapshot = getattr(ctx.coherence_state, 'macro_stability_snapshot', None)
        if msr_snapshot is not None:
            # Build dict from snapshot fields
            msr_data = {
                "macro_stability_index": getattr(msr_snapshot, 'macro_stability_index', 0.0),
                "macro_divergence_index": getattr(msr_snapshot, 'macro_divergence_index', 0.0),
                "macro_predictive_confidence": getattr(msr_snapshot, 'macro_predictive_confidence', 0.0),
                "macro_identity_resilience": getattr(msr_snapshot, 'macro_identity_resilience', 0.0),
                "stability_band": getattr(msr_snapshot, 'stability_band', None),
                "diagnostic_tags": getattr(msr_snapshot, 'diagnostic_tags', []),
            }

    # Phase 49: Extract Unified Cross-Phase Temporal Stability Engine (UCTSE) data (observation-only, analytics/UI-only)
    uctse_data = None
    if hasattr(ctx, 'coherence_state') and ctx.coherence_state is not None:
        uctse_snapshot = getattr(ctx.coherence_state, 'temporal_stability_snapshot', None)
        if uctse_snapshot is not None:
            # Build dict from snapshot fields
            uctse_data = {
                "temporal_stability_index": getattr(uctse_snapshot, 'temporal_stability_index', 0.0),
                "drift_risk": getattr(uctse_snapshot, 'drift_risk', 0.0),
                "predictive_entropy": getattr(uctse_snapshot, 'predictive_entropy', 0.0),
                "future_consistency": getattr(uctse_snapshot, 'future_consistency', 0.0),
                "dominant_regime": getattr(uctse_snapshot, 'dominant_regime', None),
                "stability_band": getattr(uctse_snapshot, 'stability_band', None),
                "diagnostic_tags": getattr(uctse_snapshot, 'diagnostic_tags', []),
            }

    # Phase 50: Extract Cognitive Consistency Regression Engine (CCRE) (observation-only, analytics/UI-only)
    ccre_data = None
    if ctx.coherence_state is not None:
        ccre_snapshot = getattr(ctx.coherence_state, 'cognitive_consistency_regression_snapshot', None)
        if ccre_snapshot is not None:
            # Build dict from snapshot fields
            ccre_data = {
                "regression_stability_index": getattr(ccre_snapshot, 'regression_stability_index', 0.0),
                "regression_drift_score": getattr(ccre_snapshot, 'regression_drift_score', 0.0),
                "regression_alignment_score": getattr(ccre_snapshot, 'regression_alignment_score', 0.0),
                "prediction_reversal_risk": getattr(ccre_snapshot, 'prediction_reversal_risk', 0.0),
                "internal_consistency_strength": getattr(ccre_snapshot, 'internal_consistency_strength', 0.0),
                "band": getattr(ccre_snapshot, 'band', None),
                "diagnostic_tags": getattr(ccre_snapshot, 'diagnostic_tags', []),
            }

    # Phase 51: Extract RAG Coherence Validation Engine (RCVE) (observation-only, analytics/UI-only)
    rcve_data = None
    if ctx.coherence_state is not None:
        rcve_snapshot = getattr(ctx.coherence_state, 'rag_validation_snapshot', None)
        if rcve_snapshot is not None:
            # Build dict from snapshot fields
            rcve_data = {
                "evidence_alignment": getattr(rcve_snapshot, 'evidence_alignment', 0.0),
                "evidence_conflict_index": getattr(rcve_snapshot, 'evidence_conflict_index', 0.0),
                "evidence_stability": getattr(rcve_snapshot, 'evidence_stability', 0.0),
                "context_relevance_score": getattr(rcve_snapshot, 'context_relevance_score', 0.0),
                "external_support_density": getattr(rcve_snapshot, 'external_support_density', 0.0),
                "alignment_band": getattr(rcve_snapshot, 'alignment_band', None),
                "diagnostic_tags": getattr(rcve_snapshot, 'diagnostic_tags', []),
            }

    # Phase 52: Extract Internal–External Reality Cross-Verification Engine (IER-CVE) (observation-only, analytics/UI-only)
    ier_cve_data = None
    if ctx.coherence_state is not None:
        ier_cve_snapshot = getattr(ctx.coherence_state, 'internal_external_reality_snapshot', None)
        if ier_cve_snapshot is not None:
            # Build dict from snapshot fields
            ier_cve_data = {
                "internal_consistency_index": getattr(ier_cve_snapshot, 'internal_consistency_index', 0.0),
                "external_evidence_consistency_index": getattr(ier_cve_snapshot, 'external_evidence_consistency_index', 0.0),
                "alignment_index": getattr(ier_cve_snapshot, 'alignment_index', 0.0),
                "divergence_index": getattr(ier_cve_snapshot, 'divergence_index', 0.0),
                "evidence_conflict_index": getattr(ier_cve_snapshot, 'evidence_conflict_index', 0.0),
                "stability_projection_index": getattr(ier_cve_snapshot, 'stability_projection_index', 0.0),
                "band": getattr(ier_cve_snapshot, 'band', None),
                "diagnostic_tags": getattr(ier_cve_snapshot, 'diagnostic_tags', []),
            }

    # Phase 53: Extract External Reality Trust Calibration Engine (ERTCE) (observation-only, analytics/UI-only)
    ertce_data = None
    if ctx.coherence_state is not None:
        ertce_snapshot = getattr(ctx.coherence_state, 'external_reality_trust_snapshot', None)
        if ertce_snapshot is not None:
            # Build dict from snapshot fields
            ertce_data = {
                "external_trust_score": getattr(ertce_snapshot, 'external_trust_score', 0.0),
                "internal_override_pressure": getattr(ertce_snapshot, 'internal_override_pressure', 0.0),
                "external_signal_fragility": getattr(ertce_snapshot, 'external_signal_fragility', 0.0),
                "alignment_resilience": getattr(ertce_snapshot, 'alignment_resilience', 0.0),
                "trust_decay_risk": getattr(ertce_snapshot, 'trust_decay_risk', 0.0),
                "trust_band": getattr(ertce_snapshot, 'trust_band', None),
                "diagnostic_tags": getattr(ertce_snapshot, 'diagnostic_tags', []),
            }

    # Phase 54: Extract Action Eligibility & Commitment Boundary Engine (AECBE) (observation-only, analytics/UI-only)
    aecbe_data = None
    if ctx.coherence_state is not None:
        aecbe_snapshot = getattr(ctx.coherence_state, 'action_eligibility_snapshot', None)
        if aecbe_snapshot is not None:
            # Build dict from snapshot fields
            aecbe_data = {
                "action_eligibility_score": getattr(aecbe_snapshot, 'action_eligibility_score', 0.0),
                "eligibility_band": getattr(aecbe_snapshot, 'eligibility_band', None),
                "internal_stability_index": getattr(aecbe_snapshot, 'internal_stability_index', 0.0),
                "external_alignment_index": getattr(aecbe_snapshot, 'external_alignment_index', 0.0),
                "trust_confidence_index": getattr(aecbe_snapshot, 'trust_confidence_index', 0.0),
                "conflict_suppression_index": getattr(aecbe_snapshot, 'conflict_suppression_index', 0.0),
                "temporal_persistence_index": getattr(aecbe_snapshot, 'temporal_persistence_index', 0.0),
                "eligibility_tags": getattr(aecbe_snapshot, 'eligibility_tags', []),
            }

    # Phase 51: Extract Cognitive Resonance Aggregator (CRA) session aggregates (observation-only, analytics/UI-only)
    cra_data = None
    # CRA aggregates are computed from SessionSummary if session_state is available
    if hasattr(ctx, 'request') and ctx.request is not None:
        try:
            # Import session store and compute session summary
            from symbolu_core.service.sessions import SessionStore, compute_session_summary

            # Get session state from store
            user_id = ctx.request.user_id
            convo_id = ctx.request.convo_id
            session_store = SessionStore.get_instance()
            session_state = session_store.get_session(user_id, convo_id)

            if session_state is not None:
                # Compute session summary to get CRA aggregates
                session_summary = compute_session_summary(session_state)

                # Extract CRA fields from SessionSummary
                cra_resonance = session_summary.avg_cra_resonance
                cra_alignment = session_summary.avg_cra_alignment
                cra_stability = session_summary.avg_cra_stability
                cra_consistency = session_summary.avg_cra_consistency
                cra_band = session_summary.dominant_cra_band
                cra_tags = session_summary.cra_pattern_tags if hasattr(session_summary, 'cra_pattern_tags') else []

                # Build CRA dict if any CRA fields are present
                if any([cra_resonance is not None, cra_alignment is not None, cra_stability is not None,
                        cra_consistency is not None, cra_band is not None, cra_tags]):
                    cra_data = {}
                    if cra_resonance is not None:
                        cra_data['avg_resonance'] = cra_resonance
                    if cra_alignment is not None:
                        cra_data['avg_alignment'] = cra_alignment
                    if cra_stability is not None:
                        cra_data['avg_stability'] = cra_stability
                    if cra_consistency is not None:
                        cra_data['avg_consistency'] = cra_consistency
                    if cra_band is not None:
                        cra_data['dominant_band'] = cra_band
                    if cra_tags:
                        cra_data['pattern_tags'] = cra_tags
        except Exception:
            # If session store is not available or CRA computation fails, CRA data remains None
            pass

    # Phase 31: Extract Adaptive Persona Echo Layer (APEL) data (observation-only, tone-level only)
    echo_profile_data = None
    # Try to extract from persona response (if available)
    if hasattr(ctx, 'persona_response') and ctx.persona_response is not None:
        echo_profile = getattr(ctx.persona_response, 'echo_profile', None)
        if echo_profile is not None:
            echo_profile_data = echo_profile

    return UnifiedOutput(
        text=text,
        symbolic=symbolic_layer,
        practical=practical_layer,
        mirror=mirror_layer,
        dha=dha_insights,
        routing=routing_plan,
        mappers=mapper_profile,
        entropy=entropy_values,
        coherence=coherence_report,
        metadata=metadata,
        session_memory=session_memory_data,
        session_recap=session_recap_data,
        intent_arc=intent_arc_data,
        identity_signature=identity_signature_data,
        motivation_profile=motivation_profile_data,
        formulas=formulas_data,
        trading_guardrails=trading_guardrails_data,
        interaction_mode=interaction_mode_data,
        persona_resonance=persona_resonance_data,  # Phase 29
        persona_resonance_map=persona_resonance_map_data,  # Phase 30
        insight_window=insight_window_data,  # Phase 32
        schema_adaptive_map=schema_adaptive_map_data,  # Phase 33
        identity_harmonics=identity_harmonics_data,  # Phase 34
        predictive_persona_drift=predictive_drift_data,  # Phase 35
        identity_resonance_memory=irm_data,  # Phase 36
        adaptive_continuity=ace_data,  # Phase 37
        temporal_forecast=tcfm_data,  # Phase 38
        multi_horizon_forecast=mhtfe_data,  # Phase 39
        cross_horizon_resonance=chra_data,  # Phase 40
        coherence_regime=regime_data,  # Phase 41
        scenario_fusion=scenario_fusion_data,  # Phase 42
        coherence_scenario_alignment=csae_data,  # Phase 44
        multi_trajectory_stability_field=mtsf_data,  # Phase 45
        trajectory_field_convergence=tfce_data,  # Phase 46
        unified_trajectory_scenario_synthesis=utsse_data,  # Phase 47
        macro_stability_regulator=msr_data,  # Phase 48
        temporal_stability=uctse_data,  # Phase 49
        cognitive_consistency_regression=ccre_data,  # Phase 50
        rag_coherence_validation=rcve_data,  # Phase 51
        cognitive_resonance_aggregator=cra_data,  # Phase 51
        internal_external_reality_verification=ier_cve_data,  # Phase 52
        external_reality_trust=ertce_data,  # Phase 53
        action_eligibility=aecbe_data,  # Phase 54
        persona_echo_profile=echo_profile_data,  # Phase 31
    )


def get_unified_json(ctx: Any) -> Dict[str, Any]:
    """
    Get complete unified JSON output from pipeline context.

    This is the main public API function for getting the full unified output.

    Args:
        ctx: PipelineContext after pipeline execution

    Returns:
        Dictionary with complete unified output structure

    Usage:
        unified = get_unified_json(ctx)
        print(json.dumps(unified, indent=2))
    """
    # Extract final text
    final_text = ""
    if hasattr(ctx, 'rendered') and ctx.rendered is not None:
        final_text = ctx.rendered.raw_text
    elif hasattr(ctx, 'dha') and ctx.dha is not None:
        final_text = ctx.dha.guarded_text

    unified = build_unified_output(final_text, ctx)
    return unified.to_dict()


def get_public_response(ctx: Any) -> Dict[str, Any]:
    """
    Get trimmed public response for UI/API consumers.

    This function returns a simplified version of the unified output
    suitable for public-facing APIs and UI dashboards.

    Args:
        ctx: PipelineContext after pipeline execution

    Returns:
        Dictionary with public-facing response fields

    Usage:
        public = get_public_response(ctx)
        return jsonify(public)  # Flask example
    """
    unified = get_unified_json(ctx)

    # Extract coherence summary
    coherence = unified.get('coherence', {})
    coherence_summary = {
        'coherence_score': coherence.get('coherence_score', 0.0),
        'state': _get_coherence_state_label(coherence.get('coherence_score', 0.0)),
    }

    # Extract session memory (Memory v2.0) - trim to last 1-2 significant events
    session_memory = unified.get('session_memory', {})
    trimmed_memory = _trim_session_memory_for_public(session_memory)

    # Extract session recap (Session Summarizer v1.0) - trim to public fields
    session_recap = unified.get('session_recap', {})
    trimmed_recap = _trim_session_recap_for_public(session_recap)

    # Extract identity signature (Identity Signature Engine v1.0) - trim to public fields
    identity_signature = unified.get('identity_signature', {})
    trimmed_identity_signature = _trim_identity_signature_for_public(identity_signature)

    # Build public response
    return {
        'text': unified.get('text', ''),
        'symbolic': unified.get('symbolic', {}),
        'practical': unified.get('practical', {}),
        'mirror': unified.get('mirror', {}),
        'dha': {
            'delivery_profile': unified.get('dha', {}).get('delivery_profile', 'unknown'),
            'readiness_level': unified.get('dha', {}).get('readiness_level', 'unknown'),
        },
        'coherence': coherence_summary,
        'mappers': unified.get('mappers', {}),
        'domain': unified.get('metadata', {}).get('domain', 'unknown'),
        'timestamp': unified.get('metadata', {}).get('timestamp', ''),
        'session_memory': trimmed_memory,
        'session_recap': trimmed_recap,
        'identity_signature': trimmed_identity_signature,
    }


def get_internal_diagnostics(ctx: Any) -> Dict[str, Any]:
    """
    Get complete internal diagnostics for debugging and observability.

    This function returns the full unified output with additional
    debug information for internal use.

    Args:
        ctx: PipelineContext after pipeline execution

    Returns:
        Dictionary with complete diagnostics including all raw data

    Usage:
        diagnostics = get_internal_diagnostics(ctx)
        logger.debug(f"Pipeline diagnostics: {diagnostics}")
    """
    unified = get_unified_json(ctx)

    # Add additional diagnostics
    diagnostics = unified.copy()

    # Add raw context summary
    diagnostics['_internal'] = {
        'has_fusion': hasattr(ctx, 'fusion') and ctx.fusion is not None,
        'has_dha': hasattr(ctx, 'dha') and ctx.dha is not None,
        'has_mlcr': hasattr(ctx, 'mlcr') and ctx.mlcr is not None,
        'has_coherence': hasattr(ctx, 'coherence_report') and ctx.coherence_report is not None,
        'has_rendered': hasattr(ctx, 'rendered') and ctx.rendered is not None,
        'router_mode': ctx.router_mode if hasattr(ctx, 'router_mode') else 'unknown',
    }

    return diagnostics


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _remove_none_values(d: Any) -> Any:
    """
    Recursively remove None values from dictionary.

    Args:
        d: Dictionary or value to process

    Returns:
        Cleaned dictionary or value
    """
    if isinstance(d, dict):
        return {k: _remove_none_values(v) for k, v in d.items() if v is not None}
    elif isinstance(d, list):
        return [_remove_none_values(item) for item in d]
    else:
        return d


def _get_coherence_state_label(score: float) -> str:
    """
    Get human-readable coherence state label.

    Args:
        score: Coherence score (0-1)

    Returns:
        State label (Excellent/Good/Fair/Poor)
    """
    if score >= 0.85:
        return "Excellent"
    elif score >= 0.7:
        return "Good"
    elif score >= 0.5:
        return "Fair"
    else:
        return "Poor"


def _trim_session_memory_for_public(session_memory: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trim session memory to only significant events for public API.

    Shows only last 1-2 memory entries of types:
    - breakthrough
    - stabilization
    - mapper_flip

    Filters out raw metrics for public consumption.

    Args:
        session_memory: Full session memory dictionary

    Returns:
        Trimmed session memory dictionary
    """
    if not session_memory or 'events' not in session_memory:
        return {}

    events = session_memory.get('events', [])

    # Filter to significant event types
    significant_types = {'breakthrough', 'stabilization', 'mapper_flip'}
    significant_events = [
        e for e in events
        if e.get('event_type') in significant_types
    ]

    # Get last 2 significant events
    recent_significant = significant_events[-2:] if len(significant_events) >= 2 else significant_events

    # Remove raw metrics for public API (keep only description and type)
    trimmed_events = []
    for event in recent_significant:
        trimmed_events.append({
            'turn_index': event.get('turn_index'),
            'event_type': event.get('event_type'),
            'description': event.get('description'),
        })

    return {
        'events': trimmed_events,
        'event_count': len(events),
    }


def _trim_session_recap_for_public(session_recap: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trim session recap to public-safe fields.

    Exposes only:
    - overall_state
    - net_trajectory
    - last 1-2 turning points (breakthrough, stabilization, fragmentation)
    - recommended_style

    Never exposes raw metrics or full mapper journey.

    Args:
        session_recap: Full session recap dictionary

    Returns:
        Trimmed session recap dictionary for public API
    """
    if not session_recap:
        return {}

    # Extract public fields
    overall_state = session_recap.get('overall_state')
    net_trajectory = session_recap.get('net_trajectory')
    recommended_style = session_recap.get('recommended_style')
    turning_points = session_recap.get('turning_points', [])

    # Filter turning points to significant types only
    significant_types = {'breakthrough', 'stabilization', 'fragmentation'}
    significant_turning_points = [
        tp for tp in turning_points
        if tp.get('event_type') in significant_types
    ]

    # Get last 1-2 significant turning points
    recent_turning_points = significant_turning_points[-2:] if len(significant_turning_points) >= 2 else significant_turning_points

    # Remove metrics from turning points for public API
    trimmed_turning_points = []
    for tp in recent_turning_points:
        trimmed_turning_points.append({
            'turn_index': tp.get('turn_index'),
            'event_type': tp.get('event_type'),
            'description': tp.get('description'),
        })

    return {
        'overall_state': overall_state,
        'net_trajectory': net_trajectory,
        'recommended_style': recommended_style,
        'recent_turning_points': trimmed_turning_points,
    }


def _trim_identity_signature_for_public(identity_signature: Dict[str, Any]) -> Dict[str, Any]:
    """
    Trim identity signature to public-safe fields.

    Exposes only:
    - signature_type
    - confidence
    - last 2 markers (identity-related session markers)
    - driver summary (count of drivers, not full list)

    Never exposes full driver list or all markers.

    Args:
        identity_signature: Full identity signature dictionary

    Returns:
        Trimmed identity signature dictionary for public API
    """
    if not identity_signature:
        return {}

    # Extract public fields
    signature_type = identity_signature.get('signature_type')
    confidence = identity_signature.get('confidence')
    markers = identity_signature.get('markers', [])
    drivers = identity_signature.get('drivers', [])

    # Get last 2 markers
    recent_markers = markers[-2:] if len(markers) >= 2 else markers

    # Driver summary (count only, not full list)
    driver_summary = {
        'count': len(drivers),
        'primary': drivers[0] if drivers else None,
    }

    return {
        'signature_type': signature_type,
        'confidence': confidence,
        'recent_markers': recent_markers,
        'driver_summary': driver_summary,
    }


# Public API
__all__ = [
    'UnifiedOutput',
    'build_unified_output',
    'get_unified_json',
    'get_public_response',
    'get_internal_diagnostics',
]
